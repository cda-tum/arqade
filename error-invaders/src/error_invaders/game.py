"""
PAULI INVADERS - Retro meets quantum error correction
Munich Quantum Software Forum arcade edition (pygame 2.5)

Game state, rules, sprites and drawing. CLI / entry point: main.py; input
mapping and tunables: config.py.
"""
import asyncio, json, math, random
from array import array
from pathlib import Path

import pygame
from arqade_common import runtime, web
from arqade_common.input import KEYBOARD, PAD

from error_invaders.config import (
    BACK_HOLD_TO_QUIT,
    FPS,
    GLOW,
    HISCORE_FILE,
    INTERNAL_HEIGHT,
    INTERNAL_WIDTH,
    MASTER_VOLUME,
    QUIT_FROM_MENU,
    SHOW_SCANLINES,
)
from error_invaders import bosses
from error_invaders.display import make_display, present
from error_invaders.input import Input
from error_invaders.pause import ITEMS as PAUSE_ITEMS, PauseMenu
from error_invaders import tutorial
from error_invaders.tutorial import Tutorial

# =====================================================================
# Constants
# =====================================================================
W, H = INTERNAL_WIDTH, INTERNAL_HEIGHT
BG = (5, 6, 13)
COL = {"X": (255, 77, 94), "Z": (63, 169, 255), "Y": (197, 107, 255)}
SPECIAL = {"bomb": (255, 210, 63), "bias": (77, 255, 160), "spread": (255, 159, 64), "lattice": (255, 255, 255)}
WHITE = (255, 255, 255)
YELLOW = (255, 224, 102)
ZONE_TOP, ZONE_BOT, DEATH_LINE = 548, 695, 525
COLS, ROWS, SX, SY, EW, EH = 10, 5, 62, 46, 36, 29
BOMB_CHARGE = 1.5
MARCH = [98, 87, 78, 73]

rand = random.uniform
pick = random.choice
def clamp(v, a, b): return max(a, min(b, v))
def fade(c, a):
    a = clamp(a, 0, 1)
    return (int(BG[0] + (c[0]-BG[0])*a), int(BG[1] + (c[1]-BG[1])*a), int(BG[2] + (c[2]-BG[2])*a))
def hue(h, s=100, v=100):
    c = pygame.Color(0); c.hsva = (h % 360, s, v, 100); return (c.r, c.g, c.b)
def now(): return pygame.time.get_ticks() / 1000.0

# =====================================================================
# Init (done by setup(), so importing this module has no side effects)
# =====================================================================
screen = window = canvas = clock = inp = None
AUDIO = False

def setup(fullscreen, window_size, pad_layout=None):
    global screen, window, canvas, clock, inp, AUDIO
    pygame.mixer.pre_init(22050, -16, 1, 512)
    pygame.init()
    pygame.joystick.init()
    screen, window = make_display(fullscreen, window_size)
    pygame.display.set_caption("Pauli Invaders")
    pygame.mouse.set_visible(not fullscreen)
    clock = pygame.time.Clock()
    canvas = pygame.Surface((W, H)).convert()
    AUDIO = True
    try:
        if not pygame.mixer.get_init(): pygame.mixer.init(22050, -16, 1, 512)
        pygame.mixer.set_num_channels(24)
    except Exception:
        AUDIO = False
    inp = Input(pad_layout)

# ---------------- Fonts / text ----------------
FONT_PATH = str(Path(__file__).parent / "assets" / "fonts" / "PressStart2P-Regular.ttf")
_fonts, _text_cache = {}, {}
def font(size):
    if size not in _fonts:
        try: _fonts[size] = pygame.font.Font(FONT_PATH, size)
        except Exception: _fonts[size] = pygame.font.Font(None, int(size * 1.9))
    return _fonts[size]

def text(S, s, size, col, x, y, align="center", valign="middle", alpha=1.0):
    key = (s, size, col)
    surf = _text_cache.get(key)
    if surf is None:
        if len(_text_cache) > 600: _text_cache.clear()
        surf = font(size).render(s, True, col)
        _text_cache[key] = surf
    r = surf.get_rect()
    if align == "center": r.centerx = int(x)
    elif align == "left": r.left = int(x)
    else: r.right = int(x)
    if valign == "middle": r.centery = int(y)
    elif valign == "top": r.top = int(y)
    else: r.bottom = int(y)
    surf.set_alpha(int(255 * clamp(alpha, 0, 1)))
    S.blit(surf, r)
    return r

# ---------------- Glow (additive radial gradient) ----------------
_glow_cache = {}
def glow(S, x, y, r, col, strength=0.6):
    if not GLOW: return
    r = max(2, int(r) // 2 * 2)
    col = (col[0] // 24 * 24, col[1] // 24 * 24, col[2] // 24 * 24)   # quantize to keep the cache small
    strength = round(strength * 20) / 20
    if strength <= 0: return
    key = (r, col, strength)
    g = _glow_cache.get(key)
    if g is None:
        g = pygame.Surface((2*r, 2*r)).convert()
        g.fill((0, 0, 0))
        for i in range(r, 0, -2):
            k = (1 - i / r) ** 2 * strength
            pygame.draw.circle(g, (int(col[0]*k), int(col[1]*k), int(col[2]*k)), (r, r), i)
        _glow_cache[key] = g
    S.blit(g, (int(x - r), int(y - r)), special_flags=pygame.BLEND_ADD)

# ---------------- Sound synthesis ----------------
SR = 22050
def synth(f, d, wave="square", vol=0.05, slide=0.0):
    if not AUDIO: return None
    n = int(SR * d); buf = array("h"); phase = 0.0
    f1 = max(30.0, f + slide)
    amp = min(1.0, vol * 6 * MASTER_VOLUME) * 32767
    for i in range(n):
        t = i / n
        fr = f * (f1 / f) ** t if slide else f
        phase += fr / SR
        ph = phase % 1.0
        if wave == "square": v = 1.0 if ph < 0.5 else -1.0
        elif wave == "sawtooth": v = 2 * ph - 1
        elif wave == "triangle": v = 4 * abs(ph - 0.5) - 1
        else: v = math.sin(2 * math.pi * ph)
        buf.append(int(v * amp * 10 ** (-4 * t)))
    return pygame.mixer.Sound(buffer=buf.tobytes())

def synth_noise(d, vol=0.15):
    if not AUDIO: return None
    n = int(SR * d); buf = array("h")
    amp = min(1.0, vol * 3 * MASTER_VOLUME) * 32767
    for i in range(n):
        buf.append(int((random.random() * 2 - 1) * (1 - i / n) * amp))
    return pygame.mixer.Sound(buffer=buf.tobytes())

SFX = {}
def build_sounds():
    if not AUDIO: return
    s = SFX
    s["shoot_tri"] = synth(880, 0.06, "square", 0.03, -500)
    s["shoot_patch"] = synth(1100, 0.06, "square", 0.03, -500)
    s["shoot_all"] = synth(1300, 0.04, "square", 0.02, -600)
    s["kill"] = synth(220, 0.12, "square", 0.05, -150)
    s["convert"] = synth(440, 0.08, "triangle", 0.05, 200)
    s["hard_rot"] = synth(160, 0.08, "triangle", 0.05, -60)
    s["block"] = synth(120, 0.05, "square", 0.03)
    for i, f in enumerate([660, 880, 1100]): s["swap%d" % i] = synth(f, 0.05, "triangle", 0.05)
    s["menu_move"] = synth(520, 0.05, "square", 0.04)
    s["menu_ok"] = synth(780, 0.07, "square", 0.05)
    s["menu_back"] = synth(300, 0.07, "square", 0.05)
    for i, f in enumerate(MARCH): s["march%d" % i] = synth(f, 0.09, "square", 0.07)
    for i in range(8): s["ufo%d" % i] = synth(500 + i * 57, 0.06, "sine", 0.025)
    for i in range(12): s["charge%d" % i] = synth(200 + i * 45, 0.04, "square", 0.03)
    s["bomb_launch"] = synth(180, 0.3, "sawtooth", 0.07, -100)
    s["bias"] = synth(300, 0.3, "triangle", 0.08, 600)
    s["boom_s"] = synth_noise(0.3, 0.15)
    s["boom_m"] = synth_noise(0.5, 0.2)
    s["boom_l"] = synth_noise(0.9, 0.25)
    for f in [392, 523, 659, 784, 1047, 1319]:
        s["n%d" % f] = synth(f, 0.08, "square", 0.04)
        s["nl%d" % f] = synth(f, 0.12, "sawtooth", 0.04)
    for i in range(5): s["pop%d" % i] = synth(500 + i * 160, 0.08, "square", 0.04)
    s["absorb"] = synth(660, 0.09, "triangle", 0.05, 500)
    s["shield"] = synth(1500, 0.03, "square", 0.015)
    s["boss_hit"] = synth(140, 0.1, "sawtooth", 0.05, -60)
    s["telegraph"] = synth(300, 0.25, "sine", 0.05, 300)

_sfx_queue = []  # (time, name)
def play(name, delay=0.0):
    if not AUDIO or name not in SFX or SFX[name] is None: return
    if delay > 0: _sfx_queue.append((now() + delay, name)); return
    SFX[name].play()
def arp(names, step, delay=0.0):
    for i, n in enumerate(names): play(n, delay + i * step)
def pump_sfx():
    t = now()
    for item in _sfx_queue[:]:
        if item[0] <= t:
            _sfx_queue.remove(item); play(item[1])

# ---------------- Hiscores ----------------
hiscores = {"easy": 0, "hard": 0, "rush": 0}
MODES = ["easy", "hard", "rush"]   # rush: every wave a boss, EASY color rules
def load_hiscores():
    try:
        with open(HISCORE_FILE) as f: hiscores.update(json.load(f))
    except Exception: pass
def save_hiscores():
    try:
        with open(HISCORE_FILE, "w") as f: json.dump(hiscores, f)
    except Exception: pass

# =====================================================================
# Sprites (pre-rendered)
# =====================================================================
SPR = [
    ["...####...", ".########.", "##########", "##########", "##########", ".########.", ".#.#..#.#.", "#..#..#..#"],
    ["...####...", ".########.", "##########", "##########", "##########", ".########.", "#.#.##.#.#", ".#......#."],
]
_enemy_cache = {}
def enemy_sprite(col, frame, flash):
    key = (col, frame, flash)
    s = _enemy_cache.get(key)
    if s is None:
        s = pygame.Surface((EW + 2, EH + 2), pygame.SRCALPHA)
        c = WHITE if flash else COL[col]
        px = 3.6
        for r in range(8):
            for cc in range(10):
                if SPR[frame][r][cc] == "#":
                    x0, y0 = int(cc * px), int(r * px)
                    x1, y1 = int((cc + 1) * px + 0.5), int((r + 1) * px + 0.5)
                    s.fill(c, (x0, y0, x1 - x0, y1 - y0))
        t = font(12).render(col, True, BG)
        s.blit(t, t.get_rect(center=(int(5 * px) + 1, int(4 * px) - 2)))
        _enemy_cache[key] = s
    return s

def draw_enemy(S, x, y, col, frame, flash=0):
    S.blit(enemy_sprite(col, frame, flash > 0), (int(x - 5 * 3.6), int(y - 4 * 3.6)))

def _tri_points(cx, cy, size):
    return [(cx, cy - size), (cx + size * 0.87, cy + size * 0.5), (cx - size * 0.87, cy + size * 0.5)]

_ship_cache = {}
def triangle_sprite(active, size=22):
    key = ("tri", active, size)
    if key in _ship_cache: return _ship_cache[key]
    d = size * 2 + 8; S = pygame.Surface((d, d), pygame.SRCALPHA); cx = cy = d / 2
    p = _tri_points(cx, cy, size)
    mid = lambda a, b: ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2)
    faces = [("X", [p[0], mid(p[0], p[1]), (cx, cy), mid(p[2], p[0])]),
             ("Z", [p[1], mid(p[1], p[2]), (cx, cy), mid(p[0], p[1])]),
             ("Y", [p[2], mid(p[2], p[0]), (cx, cy), mid(p[1], p[2])])]
    for col, poly in faces:
        c = COL[col]
        pygame.draw.polygon(S, c + ((255,) if col == active else (64,)), poly)
    pygame.draw.polygon(S, COL[active], p, 3)
    for q in p: S.fill(WHITE, (int(q[0] - 2.5), int(q[1] - 2.5), 5, 5))
    _ship_cache[key] = S
    return S

def patch_sprite(active, size=36, n=2):
    key = ("patch", active, size, n)
    if key in _ship_cache: return _ship_cache[key]
    cell = size / n; o = int(cell / 2) + 4      # margin for the half-round boundary checks
    d = size + 2 * o; S = pygame.Surface((d, d), pygame.SRCALPHA)
    alpha = lambda col: 242 if (col == active or active == "all") else 56
    # weight-2 boundary stabilizers (rotated surface code): X half-discs on the
    # top/bottom edges, Z on the left/right, each on the edge whose bulk
    # plaquette is the other type -- so every other edge segment gets one
    r = cell / 2
    for k in range(n):
        for col, (cx, cy), half, bulk in (
                ("X", (o + (k + 0.5) * cell, o), "top", (k, 0)),
                ("X", (o + (k + 0.5) * cell, o + size), "bottom", (k, n - 1)),
                ("Z", (o, o + (k + 0.5) * cell), "left", (0, k)),
                ("Z", (o + size, o + (k + 0.5) * cell), "right", (n - 1, k))):
            if ("Z" if sum(bulk) % 2 else "X") == col: continue
            flags = {"top": dict(draw_top_left=True, draw_top_right=True),
                     "bottom": dict(draw_bottom_left=True, draw_bottom_right=True),
                     "left": dict(draw_top_left=True, draw_bottom_left=True),
                     "right": dict(draw_top_right=True, draw_bottom_right=True)}[half]
            pygame.draw.circle(S, COL[col] + (alpha(col),), (int(cx), int(cy)), int(r - 1), **flags)
    for i in range(n):
        for j in range(n):
            col = "Z" if (i + j) % 2 else "X"
            S.fill(COL[col] + (alpha(col),), (int(o + i * cell + 1), int(o + j * cell + 1), int(cell - 2), int(cell - 2)))
    pygame.draw.rect(S, WHITE if active == "all" else COL[active], (o, o, size, size), 3)
    for i in range(n + 1):
        for j in range(n + 1):
            S.fill(WHITE, (int(o + i * cell - 2.5), int(o + j * cell - 2.5), 5, 5))
    _ship_cache[key] = S
    return S

def blit_center(S, spr, x, y, alpha=1.0):
    spr.set_alpha(int(255 * alpha))
    S.blit(spr, spr.get_rect(center=(int(x), int(y))))
    spr.set_alpha(255)

_scan = None
def scanlines():
    global _scan
    if _scan is None:
        _scan = pygame.Surface((W, H), pygame.SRCALPHA)
        for y in range(0, H, 3): _scan.fill((0, 0, 0, 46), (0, y, W, 1))
    return _scan

def dashed_line(S, col, a, b, dash=6, gap=8, width=1):
    x0, y0 = a; x1, y1 = b
    L = math.hypot(x1 - x0, y1 - y0)
    if L == 0: return
    ux, uy = (x1 - x0) / L, (y1 - y0) / L
    t = 0
    while t < L:
        t2 = min(L, t + dash)
        pygame.draw.line(S, col, (x0 + ux * t, y0 + uy * t), (x0 + ux * t2, y0 + uy * t2), width)
        t += dash + gap

def dashed_rect(S, col, r, dash=10, gap=6, width=3):
    x, y, w, h = r
    for a, b in (((x, y), (x + w, y)), ((x + w, y), (x + w, y + h)), ((x + w, y + h), (x, y + h)), ((x, y + h), (x, y))):
        dashed_line(S, col, a, b, dash, gap, width)

# =====================================================================
# Game state
# =====================================================================
state = "title"          # title | tutorial | play | paused | over | inputtest
mode = "easy"            # easy | hard | rush
menu = {"step": 0, "two": False, "row": 0}   # step 0: players (row), step 1: mode
TITLE_ROWS = ("1 PLAYER", "2 PLAYERS", "QUIT")
title_t = over_t = 0.0
g = None
pause_menu = PauseMenu()
how_to = Tutorial()      # the HOW TO PLAY card before every match

class Obj:
    def __init__(self, **kw): self.__dict__.update(kw)
    def get(self, k, default=None): return self.__dict__.get(k, default)

def make_player(pid, typ, x):
    tri = typ == "tri"
    return Obj(id=pid, type=typ, x=x, y=650, homeX=x,
               colors=["X", "Z", "Y"] if tri else ["X", "Z"], ci=0,
               cd=0.0, rate=0.30 if tri else 0.20, maxB=2 if tri else 3, speed=310 if tri else 280,
               alive=True, out=False, respawn=0.0, inv=2.0, spreadT=0.0, bombT=0.0, magic=0, absorbT=0.0)

def new_game(two):
    global g, state
    g = Obj(two=two, mode=mode, score=0, wave=0, lives=4 if two else 3,
            players=[make_player("p1", "tri", W/2 - 120), make_player("p2", "patch", W/2 + 120)] if two
                    else [make_player("p1", "tri", W/2)],
            pb=[], eb=[], caps=[], parts=[], pops=[], ufo=None, ufoT=rand(12, 20),
            lattice=None, merged=None, shake=0.0, chainId=1, waveT=0.0, overDelay=0.0, reason="", newHi=False,
            F=None, efT=1.5, boss=None, minions=[], skipped=False)
    next_wave()
    state = "play"

def next_wave():
    g.wave += 1
    n = g.wave
    # Out of lives, one ship lost: the next stage brings it back (still with no
    # lives to spare), so a two-player game never turns into a solo one.
    for p in g.players:
        if p.out:
            p.out = False; p.alive = True; p.x = p.homeX; p.y = 650; p.inv = 2.0
            burst(p.x, p.y, COL[p.colors[p.ci]], 24, 200)
            pop(p.x, p.y - 50, "%s IS BACK!" % p.id.upper(), WHITE, 12, 1.8)
    fight = bosses.boss_for_wave(n, g.mode)
    if fight:
        g.boss = bosses.make_boss(fight[0], fight[1], g.two)
        g.F = Obj(en=[], total=1, ox=0, oy=0, dir=1, stepT=0.5, frame=0, note=0)
        g.eb = []; g.ufo = None
        return
    y_chance = min(0.06 + 0.08 * (n - 1), 0.45)
    en = []
    for r in range(ROWS):
        c = 0
        while c < COLS:
            ln = int(rand(2, 5))
            col = "Y" if random.random() < y_chance else pick(["X", "Z"])
            k = 0
            while k < ln and c < COLS:
                en.append(Obj(c=c, r=r, col=col, alive=True, chain=0, flash=0.0)); k += 1; c += 1
    min_y = min(3 + n, 12)
    y_count = sum(1 for e in en if e.col == "Y")
    while y_count < min_y:
        pick([e for e in en if e.col != "Y"]).col = "Y"; y_count += 1
    g.F = Obj(en=en, total=len(en), ox=(W - (COLS - 1) * SX) / 2, oy=92 + min(n - 1, 6) * 12,
              dir=1, stepT=0.5, frame=0, note=0)
    g.efT = 1.5; g.eb = []
    pop(W/2, 330, "WAVE %d" % n, WHITE, 24, 1.8)
    if n > 1: pop(W/2, 370, "Error rate rising!", (170, 170, 170), 12, 1.8)

def ex(e): return g.F.ox + e.c * SX
def ey(e): return g.F.oy + e.r * SY

def burst(x, y, col, n=14, sp=180):
    for _ in range(n):
        a = rand(0, math.pi * 2); s = rand(40, sp)
        g.parts.append(Obj(x=x, y=y, vx=math.cos(a) * s, vy=math.sin(a) * s, life=rand(0.3, 0.7), col=col, ring=False))
def pop(x, y, txt, col=WHITE, size=10, life=1.0):
    g.pops.append(Obj(x=x, y=y, text=txt, col=col, size=size, life=life))

# ---------------- Player actions ----------------
def fire(p):
    if p.cd > 0: return
    mine = sum(1 for b in g.pb if b.owner == p.id and b.kind == "n")
    col = p.colors[p.ci]
    if p.spreadT > 0:
        if mine >= p.maxB * 3: return
        for a in (-0.2, 0, 0.2):
            g.pb.append(Obj(x=p.x, y=p.y - 20, vx=math.sin(a) * 620, vy=-math.cos(a) * 620, kind="n", col=col, owner=p.id))
    else:
        if mine >= p.maxB: return
        g.pb.append(Obj(x=p.x, y=p.y - 20, vx=0, vy=-640, kind="n", col=col, owner=p.id))
    p.cd = p.rate
    play("shoot_tri" if p.type == "tri" else "shoot_patch")

def kill_player(p):
    if p.inv > 0 or not p.alive: return
    burst(p.x, p.y, COL[p.colors[p.ci]], 30, 260); burst(p.x, p.y, WHITE, 12, 160)
    play("boom_m"); g.shake = 0.35
    p.alive = False; p.spreadT = 0; p.bombT = 0
    if g.lives > 0: g.lives -= 1; p.respawn = 1.6
    else: p.out = True
    if all(q.out for q in g.players): g.overDelay = 1.6; g.reason = "All qubits decohered"

# ---------------- Enemy hit logic ----------------
PAULI = {"XZ": "Y", "ZX": "Y", "XY": "Z", "YX": "Z", "YZ": "X", "ZY": "X"}

def pauli_hit(target, shot, hard):
    """What a shot of color `shot` does to an error `target`.

    ("kill", None) if it corrects it, ("convert", new color) if the error
    changes (Y hit by X or Z; in HARD any wrong color multiplies), else
    ("block", None). Used by the bosses; enemy_hit spells the same rules out.
    """
    if shot == "all" or shot == target: return "kill", None
    if hard: return "convert", PAULI[target + shot]
    if target == "Y": return "convert", "Z" if shot == "X" else "X"
    return "block", None

def kill_enemy(e, base):
    e.alive = False
    g.score += int(round(base * (1 + 0.25 * (g.wave - 1))))
    burst(ex(e), ey(e), COL.get(e.col, WHITE), 14)
    if random.random() < 0.045: g.caps.append(make_cap(ex(e), ey(e)))

def enemy_hit(e, b):
    x, y = ex(e), ey(e)
    if b.kind == "bomb":
        burst(x, y, SPECIAL["bomb"], 60, 380); play("boom_l"); g.shake = 0.5
        k = 0
        for o in g.F.en:
            if o.alive and math.hypot(ex(o) - x, ey(o) - y) < 125: kill_enemy(o, 20); k += 1
        g.eb = [q for q in g.eb if math.hypot(q.x - x, q.y - y) > 200]
        g.parts.append(Obj(ring=True, x=x, y=y, r=10, life=0.4, col=SPECIAL["bomb"]))
        pop(x, y, "MAGIC STATE x%d" % k, SPECIAL["bomb"], 12)
        return
    if b.kind == "all" or b.col == e.col:
        if e.chain:
            members = [o for o in g.F.en if o.alive and o.chain == e.chain]
            for o in members: kill_enemy(o, 20)
            if len(members) > 1:
                g.score += 25 * len(members) ** 2
                pop(x, y, "BUBBLE POP x%d" % len(members), SPECIAL["bias"], 14, 1.3)
                arp(["pop%d" % i for i in range(5)], 0.05)
                return
        else:
            kill_enemy(e, (40 if e.col == "Y" else 20) * (1.5 if g.mode == "hard" else 1))
        play("kill")
        return
    if g.mode == "hard":
        # Pauli product E*C: X*Z ~ Y, X*Y ~ Z, Y*Z ~ X -> a wrong color rotates the error
        prev = e.col
        e.col = PAULI[prev + b.col]; e.chain = 0; e.flash = 0.2
        if prev == "Y": g.score += 10
        burst(x, y, COL[e.col], 8, 120)
        play("convert" if prev == "Y" else "hard_rot")
        return
    if e.col == "Y" and b.col in ("X", "Z"):
        e.col = "Z" if b.col == "X" else "X"; e.chain = 0; e.flash = 0.2
        g.score += 10
        burst(x, y, COL[b.col], 8, 120); play("convert")
        return
    e.flash = 0.12
    burst(x, y + EH / 2, (136, 136, 136), 5, 80); play("block")

# ---------------- Power-ups ----------------
CAP_INFO = {
    "spread":  ("T", "TRANSVERSAL GATE", "Spread-Shot!"),
    "bomb":    ("M", "MAGIC STATE", "Charging bomb..."),
    "bias":    ("B", "NOISE BIAS", "Errors correlate!"),
    "lattice": ("L", "LATTICE SURGERY", "Both into the field!"),
}
def make_cap(x, y):
    types = ["spread", "spread", "bomb", "bias", "bias"]
    if g.two and not g.lattice and not g.merged and all(not p.out for p in g.players): types += ["lattice", "lattice"]
    return Obj(x=x, y=y, type=pick(types), t=0.0)

def apply_bias():
    """Correlate up to 3 random regions into chains of 3-6 adjacent same-colored errors."""
    grid = {(e.c, e.r): e for e in g.F.en if e.alive}
    made = tries = 0
    while made < 3 and tries < 40:
        tries += 1
        free = [e for e in g.F.en if e.alive and not e.chain]
        if not free: break
        seed = pick(free); size = int(rand(3, 7)); cid = g.chainId; g.chainId += 1
        members, queue = [seed], [seed]; seed.chain = cid
        while queue and len(members) < size:
            cur = queue.pop(random.randrange(len(queue)))
            nb = [grid.get((cur.c + dc, cur.r + dr)) for dc, dr in ((1, 0), (-1, 0), (0, 1), (0, -1))]
            nb = [o for o in nb if o is not None and not o.chain]
            random.shuffle(nb)
            for o in nb:
                if len(members) >= size: break
                o.chain = cid; members.append(o); queue.append(o)
        if len(members) < 3:
            for o in members: o.chain = 0
            continue
        for o in members:
            o.col = seed.col; o.flash = 0.3; burst(ex(o), ey(o), SPECIAL["bias"], 5, 90)
        made += 1
    if made: play("bias")
    return made

def collect(p, c):
    letter, name, desc = CAP_INFO[c.type]
    if c.type == "spread": p.spreadT = 8
    elif c.type == "bomb": p.bombT = BOMB_CHARGE
    elif c.type == "bias":
        if not apply_bias(): p.spreadT = 8
    elif c.type == "lattice":
        if g.lattice or g.merged: p.spreadT = 8
        else: g.lattice = Obj(t=7.0, x=W/2 - 110, y=ZONE_TOP + 20, w=220, h=110)
    g.score += 50
    pop(p.x, p.y - 50, name, SPECIAL[c.type], 10, 1.4)
    pop(p.x, p.y - 34, desc, (221, 221, 221), 8, 1.4)
    arp(["n523", "n659", "n784", "n1047"], 0.055)

def start_merge():
    a, b = g.players
    g.merged = Obj(x=(a.x + b.x) / 2, y=(a.y + b.y) / 2, angle=0.0, t=8.0, cd=0.0)
    g.lattice = None
    pop(W/2, 330, "LATTICE SURGERY!", WHITE, 20, 1.6)
    pop(W/2, 365, "P1 steers  ·  P2 aims", (187, 187, 187), 10, 1.6)
    arp(["nl392", "nl523", "nl659", "nl784", "nl1047"], 0.07)

def end_merge(hit_by_bullet):
    m = g.merged; a, b = g.players
    a.x = clamp(m.x - 35, 25, W - 25); b.x = clamp(m.x + 35, 25, W - 25); a.y = b.y = m.y
    a.inv = b.inv = 1.5
    g.merged = None
    if hit_by_bullet:
        burst(m.x, m.y, WHITE, 40, 300); play("boom_s"); g.shake = 0.3; pop(m.x, m.y - 40, "SPLIT!", WHITE, 12)

# =====================================================================
# Update
# =====================================================================
def update(dt):
    global state, over_t
    F = g.F
    g.shake = max(0.0, g.shake - dt)
    D, Hh = inp.down, inp.hit

    # --- players ---
    if g.merged:
        m = g.merged
        mx = D("p1", "right") - D("p1", "left"); my = D("p1", "down") - D("p1", "up")
        m.x = clamp(m.x + mx * 280 * dt, 40, W - 40); m.y = clamp(m.y + my * 240 * dt, ZONE_TOP + 20, ZONE_BOT - 10)
        m.angle = clamp(m.angle + (D("p2", "right") - D("p2", "left")) * 1.8 * dt, -0.9, 0.9)
        m.cd -= dt; m.t -= dt
        if (D("p1", "fire") or D("p2", "fire")) and m.cd <= 0:
            m.cd = 0.15
            for off in (-0.04, 0.04):
                a = m.angle + off
                g.pb.append(Obj(x=m.x + math.sin(a) * 30, y=m.y - math.cos(a) * 30,
                                vx=math.sin(a) * 700, vy=-math.cos(a) * 700, kind="all", col="all", owner="m"))
            play("shoot_all")
        if m.t <= 0: end_merge(False)
    else:
        for p in g.players:
            if p.out: continue
            if not p.alive:
                p.respawn -= dt
                if p.respawn <= 0: p.alive = True; p.x = p.homeX; p.y = 650; p.inv = 2.0
                continue
            dx = D(p.id, "right") - D(p.id, "left"); dy = D(p.id, "down") - D(p.id, "up")
            p.x = clamp(p.x + dx * p.speed * dt, 25, W - 25)
            p.y = clamp(p.y + dy * p.speed * 0.75 * dt, ZONE_TOP, ZONE_BOT)
            p.cd -= dt; p.inv = max(0.0, p.inv - dt); p.spreadT = max(0.0, p.spreadT - dt)
            p.absorbT = max(0.0, p.absorbT - dt)
            if Hh(p.id, "swap"):
                p.ci = (p.ci + 1) % len(p.colors); play("swap%d" % p.ci)
            if D(p.id, "fire"): fire(p)
            if p.bombT > 0:
                before = p.bombT; p.bombT -= dt
                if math.floor(before * 8) != math.floor(p.bombT * 8):
                    play("charge%d" % clamp(int((1 - p.bombT / BOMB_CHARGE) * 12), 0, 11))
                if p.bombT <= 0:
                    p.bombT = 0
                    g.pb.append(Obj(x=p.x, y=p.y - 40, vx=0, vy=-480, kind="bomb", col="bomb", owner=p.id))
                    play("bomb_launch")

    # --- lattice field ---
    if g.lattice:
        L = g.lattice; L.t -= dt
        inside = lambda p: p.alive and L.x < p.x < L.x + L.w and L.y < p.y < L.y + L.h
        if all(inside(p) for p in g.players): start_merge()
        elif L.t <= 0: g.lattice = None; pop(W/2, ZONE_TOP - 10, "Surgery missed...", (136, 136, 136), 10)

    # --- formation (classic step march, speeds up) ---
    alive = [e for e in F.en if e.alive]
    if g.boss:
        bosses.update(dt)
    elif alive:
        F.stepT -= dt
        if F.stepT <= 0:
            frac = len(alive) / F.total
            F.stepT = max(0.016, (0.02 + 0.6 * frac ** 1.4) * 0.88 ** (g.wave - 1))
            min_x = min(ex(e) - EW / 2 for e in alive); max_x = max(ex(e) + EW / 2 for e in alive)
            step = 10 * F.dir
            if max_x + step > W - 20 or min_x + step < 20: F.oy += 18; F.dir *= -1
            else: F.ox += step
            F.frame ^= 1
            play("march%d" % (F.note % 4)); F.note += 1
        for e in alive:
            e.flash = max(0.0, e.flash - dt)
            if ey(e) + EH / 2 > DEATH_LINE and not g.overDelay:
                g.overDelay = 1.2; g.reason = "Errors reached the qubits"; g.shake = 0.8; play("boom_l")

        # --- enemy fire (colorless) ---
        g.efT -= dt
        if g.efT <= 0 and not g.overDelay:
            n = g.wave
            g.efT = max(0.16, (0.95 - 0.08 * n) * rand(0.6, 1.4)) * (0.8 if g.two else 1)
            cols = {}
            for e in alive:
                if e.c not in cols or e.r > cols[e.c].r: cols[e.c] = e
            sh = pick(list(cols.values()))
            sx, sy, sp = ex(sh), ey(sh) + EH / 2, min(195 + 22 * n, 400)
            targets = [g.merged] if g.merged else [p for p in g.players if p.alive]
            roll = random.random()
            if n >= 3 and roll < min(0.1 + 0.04 * n, 0.35):
                for a in (-0.35, 0, 0.35): g.eb.append(Obj(x=sx, y=sy, vx=math.sin(a) * sp, vy=math.cos(a) * sp))
            elif n >= 2 and roll < min(0.35 + 0.05 * n, 0.7) and targets:
                t = pick(targets); d = math.hypot(t.x - sx, t.y - sy) or 1
                g.eb.append(Obj(x=sx, y=sy, vx=(t.x - sx) / d * sp, vy=(t.y - sy) / d * sp))
            else:
                g.eb.append(Obj(x=sx, y=sy, vx=0, vy=sp))
    elif not g.waveT and not g.overDelay and not g.minions:
        g.waveT = 2.2; g.eb = []
        bonus = 500 * g.wave; g.score += bonus
        pop(W/2, 300, "SYNDROME CLEAN!", SPECIAL["bias"], 18, 2)
        pop(W/2, 335, "+%d" % bonus, WHITE, 12, 2)
        arp(["n523", "n659", "n784", "n1047", "n1319"], 0.09)
    if g.waveT:
        g.waveT -= dt
        if g.waveT <= 0: g.waveT = 0; next_wave()
    if not g.boss and g.minions: bosses.update_minions(dt, bool(g.overDelay))

    # --- cosmic ray ---
    if g.boss: pass       # no cosmic ray in boss fights; bosses drop the capsules
    elif not g.ufo:
        g.ufoT -= dt
        if g.ufoT <= 0:
            left = random.random() < 0.5
            g.ufo = Obj(x=-40 if left else W + 40, y=58, vx=150 if left else -150, t=0.0)
    else:
        u = g.ufo; u.x += u.vx * dt; u.t += dt
        if math.floor(u.t * 8) != math.floor((u.t - dt) * 8):
            play("ufo%d" % int(clamp((math.sin(u.t * 10) + 1) * 4, 0, 7)))
        if u.x < -80 or u.x > W + 80: g.ufo = None; g.ufoT = rand(14, 24)

    # --- player projectiles ---
    for b in g.pb:
        b.x += b.vx * dt; b.y += b.vy * dt
        if b.y < 30 or b.x < -10 or b.x > W + 10: b.dead = True; continue
        if g.ufo and abs(b.x - g.ufo.x) < 32 and abs(b.y - g.ufo.y) < 18:
            b.dead = True; g.score += 150
            burst(g.ufo.x, g.ufo.y, YELLOW, 30, 260); play("boom_s")
            pop(g.ufo.x, g.ufo.y + 20, "COSMIC RAY +150", YELLOW, 10)
            g.caps.append(make_cap(g.ufo.x, g.ufo.y)); g.ufo = None; g.ufoT = rand(14, 24)
            continue
        if (g.boss or g.minions) and bosses.bullet_hit(b):
            b.dead = True; continue
        for e in F.en:
            if not e.alive: continue
            if b.kind == "bomb" and math.hypot(b.x - ex(e), b.y - ey(e)) < 34:
                b.dead = True; enemy_hit(e, b); break
            if abs(b.x - ex(e)) < EW / 2 + 2 and abs(b.y - ey(e)) < EH / 2 + 4:
                b.dead = True; enemy_hit(e, b); break
    g.pb = [b for b in g.pb if not b.get("dead")]

    # --- enemy projectiles ---
    for b in g.eb:
        b.x += b.vx * dt; b.y += b.vy * dt
        if b.y > H + 10 or b.y < -20 or b.x < -10 or b.x > W + 10: b.dead = True; continue
        col = b.get("col")
        if g.merged:
            m = g.merged
            if col and math.hypot(b.x - m.x, b.y - m.y) < 34: b.dead = True; bosses.absorb(m, b)
            elif abs(b.x - m.x) < 30 and abs(b.y - m.y) < 22: b.dead = True; end_merge(True)
        else:
            for p in g.players:
                if not p.alive: continue
                d = math.hypot(b.x - p.x, b.y - p.y)
                # a boss shot of the ship's own color is absorbed (Clifford Core)
                if col == p.colors[p.ci] and d < 20: b.dead = True; bosses.absorb(p, b); break
                if d < 11: b.dead = True; kill_player(p); break
    g.eb = [b for b in g.eb if not b.get("dead")]

    # --- capsules ---
    for c in g.caps:
        c.y += 115 * dt; c.t += dt
        if c.y > H + 20: c.dead = True
        if not g.merged:
            for p in g.players:
                if not c.get("dead") and p.alive and math.hypot(c.x - p.x, c.y - p.y) < 32:
                    c.dead = True; collect(p, c)
    g.caps = [c for c in g.caps if not c.get("dead")]

    # --- particles & popups ---
    for q in g.parts:
        q.life -= dt
        if q.ring: q.r += 500 * dt
        else:
            q.x += q.vx * dt; q.y += q.vy * dt; q.vx *= 0.96; q.vy *= 0.96
    g.parts = [q for q in g.parts if q.life > 0]
    for q in g.pops: q.life -= dt; q.y -= 18 * dt
    g.pops = [q for q in g.pops if q.life > 0]

    if g.overDelay:
        g.overDelay -= dt
        if g.overDelay <= 0:
            state = "over"; over_t = 0.0
            arp(["nl784", "nl659", "nl523", "nl392"], 0.14)
            if g.score > hiscores.get(g.mode, 0) and not g.skipped:   # a skipped boss doesn't count
                hiscores[g.mode] = g.score; g.newHi = True; save_hiscores()
                arp(["n523", "n659", "n784", "n1047", "n1319"], 0.08, 0.8)

# =====================================================================
# Drawing
# =====================================================================
def draw_player(S, p):
    if not p.alive: return
    blink = p.inv > 0 and int(p.inv * 12) % 2
    alpha = 0.3 if blink else 1.0
    col = p.colors[p.ci]
    glow(S, p.x, p.y, 34, COL[col], 0.35 * alpha)
    spr = triangle_sprite(col) if p.type == "tri" else patch_sprite(col)
    blit_center(S, spr, p.x, p.y, alpha)
    if p.bombT > 0:
        k = 1 - p.bombT / BOMB_CHARGE; r = 4 + 12 * k
        flash = p.bombT < 0.45 and int(now() / 0.06) % 2
        glow(S, p.x, p.y - 40, 20 + 20 * k, SPECIAL["bomb"], 0.5 + 0.4 * k)
        pygame.draw.circle(S, WHITE if flash else SPECIAL["bomb"], (int(p.x), int(p.y - 40)), int(r))
        rr = pygame.Rect(0, 0, int(2 * (r + 6)), int(2 * (r + 6))); rr.center = (int(p.x), int(p.y - 40))
        if k > 0.01: pygame.draw.arc(S, SPECIAL["bomb"], rr, math.pi / 2 - 2 * math.pi * k, math.pi / 2, 2)
    if p.absorbT > 0:
        glow(S, p.x, p.y, 44, COL[col], p.absorbT * 3)
        pygame.draw.circle(S, WHITE, (int(p.x), int(p.y)), int(30 - p.absorbT * 40), 2)
    if p.magic or (g.boss and g.boss.kind == "clifford"):
        # magic-state charge: pips on an arc above the ship
        for k in range(bosses.MAGIC_NEEDED):
            a = math.pi * (1.2 + 0.6 * k / (bosses.MAGIC_NEEDED - 1))
            q = (int(p.x + math.cos(a) * 34), int(p.y + math.sin(a) * 34))
            if k < p.magic: pygame.draw.circle(S, SPECIAL["bomb"], q, 4)
            else: pygame.draw.circle(S, fade(SPECIAL["bomb"], 0.4), q, 4, 1)
    if p.spreadT > 0:
        rr = pygame.Rect(0, 0, 60, 60); rr.center = (int(p.x), int(p.y))
        a0 = math.pi * 0.85
        pygame.draw.arc(S, SPECIAL["spread"], rr, a0 - math.pi * 0.7 * (p.spreadT / 8), a0, 2)
    text(S, p.id.upper(), 8, WHITE, p.x, p.y + 34)

def draw_merged(S, m):
    t = now(); hc = hue(t * 200)
    glow(S, m.x, m.y, 60, hc, 0.5)
    blit_center(S, patch_sprite("all", 54, 4), m.x, m.y)
    dashed_line(S, hue(t * 200, 70, 100), (m.x, m.y - 30),
                (m.x + math.sin(m.angle) * 120, m.y - 30 - math.cos(m.angle) * 120), 4, 6, 2)
    text(S, "P1+P2  %.1fs" % max(0, m.t), 8, WHITE, m.x, m.y + 44)

def draw_hud(S):
    text(S, "SCORE %06d" % g.score, 12, WHITE, 16, 14, "left", "top")
    hi = max(hiscores.get(g.mode, 0), g.score)
    text(S, "HI %06d%s" % (hi, {"hard": " · HARD", "rush": " · RUSH"}.get(g.mode, "")), 12, WHITE, W/2, 14, "center", "top")
    text(S, ("BOSS %d" if g.mode == "rush" else "WAVE %d") % g.wave, 12, WHITE, W - 16, 14, "right", "top")
    text(S, "LIVES", 8, (153, 170, 170), 16, 36, "left", "top")
    for i in range(g.lives): pygame.draw.rect(S, SPECIAL["bias"], (84 + i * 16, 34, 10, 10), 2)
    text(S, "%s: PAUSE" % inp.devices.shared_label("start"), 8, (68, 68, 85), W - 16, 36, "right", "top")
    dashed_line(S, fade(COL["X"], 0.4), (0, DEATH_LINE), (W, DEATH_LINE), 6, 8, 1)
    text(S, "LOGICAL ERROR THRESHOLD", 8, fade(COL["X"], 0.55), W - 10, DEATH_LINE - 4, "right", "bottom")
    bosses.draw_overlay(S)
    for i, p in enumerate(g.players):
        bx = 16 if i == 0 else W - 16 - len(p.colors) * 26 - 40
        text(S, p.id.upper(), 8, WHITE, bx, 708, "left")
        for k, c in enumerate(p.colors):
            x = bx + 32 + k * 26
            S.fill(COL[c] if k == p.ci else fade(COL[c], 0.3), (x, 700, 20, 16))
            text(S, c, 8, BG, x + 10, 708)
            if k == p.ci: pygame.draw.rect(S, WHITE, (x - 2, 698, 24, 20), 2)

def draw_game(S):
    F = g.F
    S.fill(BG)
    S.fill((8, 14, 16), (0, ZONE_TOP - 25, W, ZONE_BOT - ZONE_TOP + 50))
    t = now()

    if g.lattice:
        L = g.lattice
        c = fade(hue(t * 240, 60, 100), 0.6 + 0.4 * math.sin(t * 10))
        S.fill((18, 19, 26), (L.x, L.y, L.w, L.h))
        dashed_rect(S, c, (L.x, L.y, L.w, L.h))
        text(S, "LATTICE SURGERY", 10, WHITE, L.x + L.w / 2, L.y + L.h / 2 - 10)
        text(S, "%.1f" % max(0, L.t), 10, WHITE, L.x + L.w / 2, L.y + L.h / 2 + 12)

    # chains
    pulse = 0.6 + 0.3 * math.sin(t / 0.12)
    chain_col = fade(SPECIAL["bias"], pulse)
    chained = [e for e in F.en if e.alive and e.chain]
    for a in chained:
        for b in chained:
            if a.chain == b.chain and (b.c > a.c or b.r > a.r) and abs(a.c - b.c) + abs(a.r - b.r) == 1:
                pygame.draw.line(S, chain_col, (ex(a), ey(a)), (ex(b), ey(b)), 2)

    for e in F.en:
        if not e.alive: continue
        if e.chain:
            pygame.draw.rect(S, chain_col, (ex(e) - EW / 2 - 4, ey(e) - EH / 2 - 4, EW + 8, EH + 8), 2)
        draw_enemy(S, ex(e), ey(e), e.col, F.frame, e.flash)

    bosses.draw(S)

    # cosmic ray: Gaussian wave packet
    if g.ufo:
        draw_cosmic_ray(S, g.ufo.x, g.ufo.y, g.ufo.t * (1 if g.ufo.vx > 0 else -1))

    # capsules
    for c in g.caps:
        col = SPECIAL[c.type]; pz = 1 + 0.12 * math.sin(c.t * 10)
        glow(S, c.x, c.y, 26, col, 0.4)
        r = pygame.Rect(0, 0, int(26 * pz), int(22 * pz)); r.center = (int(c.x), int(c.y))
        S.fill(col, r)
        text(S, CAP_INFO[c.type][0], 12, BG, c.x + 1, c.y + 1)

    # player projectiles
    for b in g.pb:
        if b.kind == "bomb":
            glow(S, b.x, b.y, 22, SPECIAL["bomb"], 0.7)
            pygame.draw.circle(S, SPECIAL["bomb"], (int(b.x), int(b.y)), 7)
        else:
            col = hue(t * 500 + b.x, 60, 100) if b.kind == "all" else COL[b.col]
            glow(S, b.x, b.y, 10, col, 0.5)
            S.fill(col, (int(b.x - 2), int(b.y - 8), 4, 16))

    # enemy projectiles: colorless zigzags, the bosses' round orbs, and the
    # Clifford Core's colored shots (absorbed by a ship of the same color)
    zz = int(t / 0.08) % 2
    for b in g.eb:
        kind = b.get("kind")
        if b.get("col"):
            c = COL[b.col]
            glow(S, b.x, b.y, 18, c, 0.6)
            pygame.draw.circle(S, c, (int(b.x), int(b.y)), 8)
            pygame.draw.circle(S, WHITE, (int(b.x), int(b.y)), 3)
        elif kind == "orb":
            pygame.draw.circle(S, (225, 225, 235), (int(b.x), int(b.y)), 5)
            pygame.draw.circle(S, BG, (int(b.x), int(b.y)), 2)
        else:
            for i in range(4):
                S.fill((232, 232, 232), (int(b.x - 3 + ((i + zz) % 2) * 3), int(b.y - 8 + i * 4), 3, 4))

    if g.merged: draw_merged(S, g.merged)
    else:
        for p in g.players: draw_player(S, p)

    for q in g.parts:
        a = min(1.0, q.life * 2)
        if q.ring:
            if q.r > 4: pygame.draw.circle(S, fade(q.col, a), (int(q.x), int(q.y)), int(q.r), 4)
        else:
            S.fill(fade(q.col, a), (int(q.x - 2), int(q.y - 2), 4, 4))

    for q in g.pops:
        text(S, q.text, q.size, q.col, q.x, q.y, alpha=min(1.0, q.life * 1.5))

def draw_cosmic_ray(S, x, y, t, half=70, amp=16):
    """The Cosmic Ray: a Gaussian wave packet (also drawn small on the title)."""
    glow(S, x, y, 46 * half // 70, YELLOW, 0.35)
    sig = 18 * half / 70
    env = lambda dx: math.exp(-(dx * dx) / (2 * sig * sig))
    xs = range(-half, half + 1, 2)
    pts = [(x + dx, y - amp * env(dx) * math.cos(dx * 0.38 * 70 / half - t * 18)) for dx in xs]
    up = [(x + dx, y - amp * env(dx)) for dx in xs]
    dn = [(x + dx, y + amp * env(dx)) for dx in reversed(xs)]
    pygame.draw.lines(S, fade(YELLOW, 0.3), True, up + dn, 1)
    pygame.draw.lines(S, YELLOW, False, pts, 3)

GREY, DIM = (153, 170, 170), (68, 68, 85)

def legend_heading(S, label, x0, x1, y):
    """A legend group's heading: a short line of text over a thin rule."""
    text(S, label, 8, GREY, x0, y, "left")
    pygame.draw.line(S, DIM, (x0, y + 10), (x1, y + 10), 1)

def draw_title(S):
    t = title_t
    S.fill(BG)
    for i, c in enumerate("XYZXZYX"):
        draw_enemy(S, W/2 - 180 + i * 60, 52 + math.sin(t * 2 + i) * 5, c, int(t * 2) % 2)
    glow(S, W/2, 126, 150, COL["X"], 0.25); glow(S, W/2, 182, 170, COL["Z"], 0.25)
    text(S, "PAULI", 44, COL["X"], W/2, 126)
    text(S, "INVADERS", 44, COL["Z"], W/2, 182)
    text(S, "RETRO MEETS QUANTUM ERROR CORRECTION", 10, GREY, W/2, 224)

    # The legend: two groups, read top to bottom, one sprite and one short
    # line each. Everything else is on the HOW TO PLAY card or in the game.
    LX, RX, Y0, DY = 96, 544, 300, 52
    legend_heading(S, "MATCH THE COLOR", LX - 26, LX + 360, Y0 - 38)
    for i, (c, label) in enumerate((("X", "RED SHOT"), ("Z", "BLUE SHOT"), ("Y", "PURPLE, OR RED+BLUE"))):
        draw_enemy(S, LX, Y0 + i * DY, c, int(t * 2) % 2)
        text(S, label, 16, COL[c], LX + 40, Y0 + i * DY, "left")
    legend_heading(S, "SHIPS", RX - 30, RX + 340, Y0 - 38)
    blit_center(S, triangle_sprite("XZY"[int(t) % 3]), RX, Y0)
    text(S, "P1  3 COLORS", 16, WHITE, RX + 44, Y0, "left")
    blit_center(S, patch_sprite("XZ"[int(t) % 2], 30), RX, Y0 + DY)
    text(S, "P2  2 COLORS", 16, WHITE, RX + 44, Y0 + DY, "left")
    draw_cosmic_ray(S, RX, Y0 + 2 * DY, t, 30, 12)
    text(S, "SHOOT IT: POWER-UP", 16, YELLOW, RX + 44, Y0 + 2 * DY, "left")

    if menu["step"] == 0:
        items = [(label, i == menu["row"], DIM if label == "QUIT" and i != menu["row"] else WHITE)
                 for i, label in enumerate(TITLE_ROWS)]
        note = "BACK TO THE GAME LIST" if TITLE_ROWS[menu["row"]] == "QUIT" else ""
        note_col = GREY
    else:
        items = [("EASY", mode == "easy", SPECIAL["bias"]), ("HARD", mode == "hard", COL["X"]),
                 ("BOSS RUSH", mode == "rush", YELLOW)]
        note = {"easy": "MATCH THE COLOR TO CORRECT AN ERROR",
                "hard": "A WRONG COLOR CHANGES THE ERROR!",
                "rush": "ONLY BOSSES, ONE AFTER ANOTHER"}[mode]
        note_col = dict(easy=SPECIAL["bias"], hard=COL["X"], rush=YELLOW)[mode]
        text(S, ("2 PLAYERS" if menu["two"] else "1 PLAYER") + " >", 8, (102, 102, 102), W/2 - 210, 528)
    blink = int(t * 3) % 2
    for i, (label, on, col) in enumerate(items):
        y = 500 + i * 28
        text(S, label, 16, col if on else DIM, W/2, y)
        if on and blink:
            text(S, ">", 16, col, W/2 - 120, y); text(S, "<", 16, col, W/2 + 120, y)
    if note: text(S, note, 8, note_col, W/2, 600)
    stick, a, b, start = (button_name(k) for k in ("stick", "a", "b", "start"))
    hint = ("%s select  ·  %s ok  ·  %s go" % (stick, a, start) if menu["step"] == 0
            else "%s select  ·  %s/%s play  ·  %s back" % (stick, a, start, b))
    text(S, hint, 8, (119, 119, 119), W/2, 664)
    text(S, "HI %06d (%s)   ·   MUNICH QUANTUM SOFTWARE FORUM" % (hiscores.get(mode, 0), mode.upper()),
         8, (85, 85, 102), W/2, 700)

KEYBOARD_STICKS = {"p1": "WASD", "p2": "ARROWS"}   # the keys that stand in for each player's stick

def button_name(name, player=None):
    """A control's on-screen name for one player's keys or pad, or for both
    players' when player is None (e.g. "SPACE / ENTER"). "stick" is the
    stick or the direction keys."""
    if player is None:
        return " / ".join(dict.fromkeys(button_name(name, p) for p in ("p1", "p2")))
    if name == "stick":
        return KEYBOARD_STICKS[player] if inp.devices[player] == KEYBOARD else "STICK"
    return inp.devices.label(name, player)

# ---------------- HOW TO PLAY ----------------
DEMO = pygame.Rect(56, 232, 440, 330)   # the demo scene's panel
TUT_MODE_LINE = {"hard": ("HARD: A WRONG COLOR CHANGES IT!", COL["X"]),
                 "rush": ("BOSS RUSH: ONLY BOSSES!", YELLOW)}

def draw_button(S, x, y, label, used, lit):
    """One of the cabinet's round buttons, with its printed label."""
    if lit:
        glow(S, x, y, 40, YELLOW, 0.6)
        pygame.draw.circle(S, YELLOW, (x, y), 18)
        text(S, label, 16, BG, x + 1, y + 1)
    elif used:
        pygame.draw.circle(S, WHITE, (x, y), 18)
        text(S, label, 16, BG, x + 1, y + 1)
    else:
        pygame.draw.circle(S, DIM, (x, y), 18, 2)
        text(S, label, 8, DIM, x + 1, y + 1)

def draw_tutorial(S):
    """The HOW TO PLAY card: goal, a looping demo, the controls."""
    t = how_to.t
    S.fill(BG)
    glow(S, W/2 - 80, 52, 120, COL["X"], 0.25); glow(S, W/2 + 112, 52, 100, COL["Z"], 0.25)
    text(S, "HOW TO", 32, COL["X"], W/2 - 176, 52, "left")    # "HOW TO PLAY", centred, in two colors
    text(S, "PLAY", 32, COL["Z"], W/2 + 176, 52, "right")

    text(S, "GOAL", 16, YELLOW, W/2, 108)
    text(S, "SHOOT EACH ERROR IN ITS OWN COLOR.", 16, WHITE, W/2, 140)
    text(S, "DON'T LET THEM CROSS THE RED LINE.", 16, WHITE, W/2, 168)
    if mode in TUT_MODE_LINE:
        line, col = TUT_MODE_LINE[mode]
        text(S, line, 16, col, W/2, 196)

    # the demo, on its own little field
    d = tutorial.demo(t)
    cx, cy = DEMO.centerx, DEMO.centery
    S.fill((8, 14, 16), (DEMO.x, cy + 40, DEMO.w, DEMO.bottom - cy - 40))
    pygame.draw.rect(S, DIM, DEMO, 2)
    dashed_line(S, fade(COL["X"], 0.6), (DEMO.x + 2, cy + 22), (DEMO.right - 2, cy + 22), 6, 8, 1)
    for x, y, col, flash in d["invaders"]:
        draw_enemy(S, cx + x, cy + y, col, int(t * 2) % 2, flash)
    for x, y, col, age in d["bursts"]:
        c = fade(COL[col], 1 - age / tutorial.BURST)
        for k in range(10):
            a = k * math.pi / 5 + 0.3
            S.fill(c, (int(cx + x + math.cos(a) * age * 220 - 2), int(cy + y + math.sin(a) * age * 220 - 2), 4, 4))
    for x, y, col in d["shots"]:
        glow(S, cx + x, cy + y, 10, COL[col], 0.5)
        S.fill(COL[col], (int(cx + x - 2), int(cy + y - 8), 4, 16))
    sx, sy = cx + d["ship_x"], cy + tutorial.SHIP_Y
    glow(S, sx, sy, 34, COL[d["ship_col"]], 0.35)
    blit_center(S, triangle_sprite(d["ship_col"]), sx, sy)
    text(S, "P1", 8, WHITE, sx, sy + 34)
    cap_col = SPECIAL["bias"] if d["caption"] == "WAVE CLEAN!" else WHITE
    text(S, d["caption"], 16, cap_col, cx, DEMO.bottom + 26)

    # the controls: the stick and the 2x3 button cluster as printed on the
    # pads (L X R / Y B A), the buttons the game uses lit, the demo's presses
    # flashing
    kx = 728
    text(S, "CONTROLS", 16, YELLOW, kx, 252)
    jx, jy = 590, 330
    pygame.draw.circle(S, DIM, (jx, jy), 30, 2)
    pygame.draw.line(S, GREY, (jx, jy), (jx + int(math.sin(t * 2.4) * 12), jy - 14), 6)
    pygame.draw.circle(S, WHITE, (jx + int(math.sin(t * 2.4) * 12), jy - 16), 12)
    for r, row in enumerate(("LXR", "YBA")):
        for c, label in enumerate(row):
            draw_button(S, 680 + c * 52, 306 + r * 50, label, label in "AB", label.lower() in d["lit"])
    who = None if g is not None and g.two else inp.devices.latest   # whose keys or pad to name
    keys = [button_name(k, who) for k in ("stick", "a", "b", "start")]
    size = 16 if max(font(16).size(k)[0] for k in keys) <= 92 else 8   # long key names: smaller
    action_x = 556 + max(100, max(font(size).size(k)[0] for k in keys) + 16)
    for i, (key, action) in enumerate(zip(keys, ("MOVE", "FIRE", "SWITCH COLOR", "PAUSE"))):
        y = 422 + i * 34
        text(S, key, size, WHITE, 556, y, "left")
        text(S, action, 16, GREY, action_x, y, "left")
    if g is not None and g.two:
        text(S, "SAME ON BOTH PADS" if inp.devices.everyone_on(PAD) else "SAME FOR BOTH PLAYERS", 8, GREY, kx, 562)

    if int(t / 0.45) % 3 != 2:
        any_button = "ANY KEY" if inp.devices.everyone_on(KEYBOARD) else "ANY BUTTON"
        text(S, "PRESS %s TO START" % any_button, 16, WHITE, W/2, 668)

def draw_over(S):
    draw_game(S)
    shade = pygame.Surface((W, H), pygame.SRCALPHA); shade.fill((0, 0, 0, 178)); S.blit(shade, (0, 0))
    glow(S, W/2, 260, 180, COL["X"], 0.3)
    text(S, "LOGICAL ERROR", 40, COL["X"], W/2, 260)
    text(S, g.reason, 10, (170, 170, 170), W/2, 305)
    text(S, "SCORE %d" % g.score, 16, WHITE, W/2, 360)
    text(S, "WAVE %d" % g.wave, 16, WHITE, W/2, 392)
    if g.newHi: text(S, "NEW HIGH SCORE!", 16, SPECIAL["bomb"], W/2, 435)
    if over_t > 1.5 and int(over_t * 2.5) % 2: text(S, "PRESS FIRE", 12, WHITE, W/2, 500)

def draw_pause(S):
    """The pause menu, centred over the frozen game."""
    shade = pygame.Surface((W, H), pygame.SRCALPHA); shade.fill((0, 0, 0, 178)); S.blit(shade, (0, 0))
    box = pygame.Rect(0, 0, 420, 210); box.center = (W // 2, H // 2)
    S.fill(BG, box); pygame.draw.rect(S, COL["Z"], box, 3)
    glow(S, W/2, box.y + 46, 120, COL["Z"], 0.3)
    text(S, "PAUSED", 28, COL["Z"], W/2, box.y + 46)
    blink = int(now() * 3) % 2
    for i, label in enumerate(PAUSE_ITEMS):
        y = box.y + 106 + i * 28
        on = i == pause_menu.index
        text(S, label, 14, WHITE if on else (68, 68, 68), W/2, y)
        if on and blink:
            text(S, ">", 14, WHITE, W/2 - 150, y); text(S, "<", 14, WHITE, W/2 + 150, y)
    p = inp.devices.latest   # one player works the menu
    if inp.devices[p] == PAD:
        hint = "UP/DOWN select  ·  FIRE pick  ·  START resume"
    else:
        hint = "UP/DOWN select  ·  %s pick  ·  %s resume" % (button_name("a", p), button_name("start", p))
    text(S, hint, 8, (119, 119, 119), W/2, box.bottom - 20)

def draw_input_test(S):
    S.fill(BG)
    text(S, "INPUT TEST", 20, WHITE, W/2, 40)
    text(S, "Press buttons / move sticks. ESC or hold SELECT 2s to leave.", 8, (170, 170, 170), W/2, 70)
    y = 110
    if not inp.joys: text(S, "No joysticks detected.", 10, COL["X"], 40, y, "left"); y += 30
    for i, j in inp.joys.items():
        slot = inp.pads.slot_of(j.get_instance_id())
        who = "-> P%d" % (slot + 1) if slot is not None else ""
        text(S, "JOY %d: %s %s" % (i, j.get_name()[:40], who), 10, SPECIAL["bias"], 40, y, "left"); y += 22
        axes = "  ".join("a%d:%+.2f" % (k, j.get_axis(k)) for k in range(j.get_numaxes()))
        text(S, "axes " + axes, 8, WHITE, 60, y, "left"); y += 18
        hats = "  ".join("h%d:%s" % (k, j.get_hat(k)) for k in range(j.get_numhats()))
        text(S, "hats " + (hats or "-"), 8, WHITE, 60, y, "left"); y += 18
        btn = " ".join(str(k) for k in range(j.get_numbuttons()) if j.get_button(k))
        text(S, "buttons down: " + (btn or "-"), 8, WHITE, 60, y, "left"); y += 30
    text(S, "last keys: " + (", ".join(inp.last_keys) or "-"), 10, YELLOW, 40, y + 10, "left")
    for i, p in enumerate(("p1", "p2")):
        text(S, "%s actions: %s" % (p.upper(), ", ".join(sorted(inp.held[p])) or "-"), 10, WHITE, 40, y + 50 + i * 24, "left")
    text(S, "Mapping lives in arqade_common/input.py (shared by all games)", 8, (119, 119, 119), W/2, H - 30)

# =====================================================================
# Main loop
# =====================================================================
def to_menu():
    global state, title_t
    state = "title"; title_t = 0.0; menu["step"] = 0; menu["row"] = 1 if menu["two"] else 0

def step_title(dt):
    """One frame of the title menu. Page 0 picks the players (or QUIT), page 1
    the mode. The stick moves, A picks, B (or Select) goes back a page, and
    Start goes on with what is selected -- it never quits, on QUIT it keeps
    the last player count. Returns False to quit the game."""
    global state, mode, title_t
    title_t += dt
    moved = inp.any_hit("down") - inp.any_hit("up")
    a, start = inp.any_hit("fire"), inp.confirm      # confirm: Start (or Enter)
    back = inp.any_hit("swap") or inp.back
    if moved:
        if menu["step"] == 0: menu["row"] = (menu["row"] + moved) % len(TITLE_ROWS)
        else: mode = MODES[(MODES.index(mode) + moved) % len(MODES)]
        play("menu_move")
    if menu["step"] == 0:
        if a and TITLE_ROWS[menu["row"]] == "QUIT":
            return False                                 # out to the game list, like Start + Select
        if a or start:
            if TITLE_ROWS[menu["row"]] != "QUIT": menu["two"] = menu["row"] == 1
            menu["step"] = 1; play("menu_ok")
        elif QUIT_FROM_MENU and inp.back_held > BACK_HOLD_TO_QUIT:
            return False
    elif a or start:
        menu["step"] = 0; new_game(menu["two"]); open_tutorial(); play("menu_ok")
    elif back:
        menu["step"] = 0; play("menu_back")
    if pygame.K_F1 in inp.ev_keys: state = "inputtest"
    return True

def open_tutorial():
    """Show the HOW TO PLAY card; the match (already set up) waits behind it."""
    global state
    state = "tutorial"; how_to.open()

def step_tutorial(dt):
    """One frame of the HOW TO PLAY card. Any new button press (after its
    first moments) starts play; whatever is held then is swallowed, so the
    press doesn't also fire or switch color."""
    global state
    if how_to.step(dt, inp.any_button):
        state = "play"; inp.swallow(); play("menu_ok")

def step_play(dt):
    """One frame of play: Start pauses, otherwise the game runs."""
    global state
    if inp.pause:
        state = "paused"; pause_menu.open(); play("menu_ok")
    else:
        # PC-only dev shortcut: the cabinet runs --no-keyboard, so ev_keys stays empty there
        if pygame.K_n in inp.ev_keys and pygame.key.get_mods() & pygame.KMOD_CTRL: bosses.skip()
        update(dt)

def step_paused():
    """One frame of the pause menu. update() isn't called, so everything in
    the game stays where it is. A picks; Start and B both resume."""
    global state
    act = pause_menu.step(move=inp.any_hit("down") - inp.any_hit("up"),
                          pick=inp.any_hit("fire") or (inp.confirm and not inp.pause),
                          resume=inp.pause or inp.any_hit("swap"))
    if act == "resume": state = "play"; play("menu_back")
    elif act == "title": to_menu(); play("menu_back")   # no score recorded
    elif act == "move": play("menu_move")

# Same as the folder name in the web build and the "id" in game.json.
GAME_ID = "error-invaders"
_playing = False   # a game is on (for the page's game-start / game-end events)

def _note_playing():
    global _playing
    now = state in ("play", "paused")
    if now != _playing:
        _playing = now
        web.post_event(web.GAME_START if now else web.GAME_END, GAME_ID)

async def _leave():
    """A player asked to quit: True ends the program. In the browser there is
    nothing to hand back to, so instead the game tells the page (which may
    take the player back to its game list) and returns to its title -- once
    the quit buttons are let go, or the title would quit again at once."""
    if not runtime.is_browser():
        return True
    if state in ("play", "paused"):   # the game ends before the player leaves
        to_menu(); _note_playing()
    web.post_event(web.QUIT, GAME_ID)
    while inp.quit_combo or inp.back_held > 0:
        for e in pygame.event.get(): inp.handle(e)
        inp.update(0.0); inp.end_frame()
        present(screen, window); pygame.display.flip()
        await asyncio.sleep(0)
    to_menu()
    return False

async def run(*, fullscreen=False, window_size="960x720", show_fps=False, input_test=False, pad_layout=None):
    global state, mode, title_t, over_t
    setup(fullscreen, window_size, pad_layout)
    load_hiscores()
    build_sounds()
    if input_test: state = "inputtest"
    frozen = None   # the game frame shown behind the pause menu
    running = True
    while running:
        dt = min(0.033, clock.tick(FPS) / 1000.0)
        for e in pygame.event.get():
            if e.type == pygame.QUIT: running = False
            elif e.type == pygame.KEYDOWN and e.key == pygame.K_F3: show_fps = not show_fps
            inp.handle(e)
        inp.update(dt)
        if inp.quit_combo and state != "inputtest":
            if await _leave(): break
            inp.end_frame(); continue
        pump_sfx()

        if state == "title":
            if not step_title(dt):
                if await _leave(): break
                inp.end_frame(); continue
            (draw_tutorial if state == "tutorial" else draw_title)(canvas)
            screen.blit(canvas, (0, 0))
        elif state == "tutorial":
            step_tutorial(dt)
            if state == "tutorial":
                draw_tutorial(canvas); screen.blit(canvas, (0, 0))
            else:
                draw_game(canvas); screen.blit(canvas, (0, 0)); draw_hud(screen)
        elif state in ("play", "paused"):
            was = state
            if state == "play": step_play(dt)
            else: step_paused()
            if state == "title":
                draw_title(canvas); screen.blit(canvas, (0, 0))
            elif state == "paused":
                if was == "play" or frozen is None:   # just paused: draw the game once, then keep that frame
                    draw_game(canvas); draw_hud(canvas); frozen = canvas.copy()
                screen.blit(frozen, (0, 0))
                draw_pause(screen)
            else:
                draw_game(canvas)
                ox = oy = 0
                if g.shake > 0:
                    ox = int(rand(-6, 6) * g.shake * 2); oy = int(rand(-6, 6) * g.shake * 2)
                screen.fill(BG); screen.blit(canvas, (ox, oy))
                draw_hud(screen)
        elif state == "over":
            over_t += dt
            draw_over(canvas); screen.blit(canvas, (0, 0))
            if inp.back or (over_t > 1.5 and (inp.any_hit("fire") or inp.confirm)): to_menu()
        elif state == "inputtest":
            draw_input_test(canvas); screen.blit(canvas, (0, 0))
            if pygame.K_ESCAPE in inp.ev_keys or inp.back_held > BACK_HOLD_TO_QUIT:
                inp.back_held = 0.0; to_menu()

        if SHOW_SCANLINES: screen.blit(scanlines(), (0, 0))
        if show_fps:
            text(screen, "%d FPS" % clock.get_fps(), 8, YELLOW, 8, H - 8, "left", "bottom")
        present(screen, window)
        pygame.display.flip()
        inp.end_frame()
        _note_playing()
        await asyncio.sleep(0)  # hand the frame to the browser (pygbag); no-op elsewhere
