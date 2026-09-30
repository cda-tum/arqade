"""
ERROR INVADERS - Retro meets quantum error correction
Munich Quantum Software Forum arcade edition (pygame 2.5)

Game state, rules, sprites and drawing. CLI / entry point: main.py; input
mapping and tunables: config.py.
"""
import json, math, random
from array import array
from pathlib import Path

import pygame

from error_invaders.config import (
    BACK_HOLD_TO_QUIT,
    FPS,
    GLOW,
    HISCORE_FILE,
    INPUT_CONFIG,
    INTERNAL_HEIGHT,
    INTERNAL_WIDTH,
    KEY_PRESET,
    MASTER_VOLUME,
    QUIT_FROM_MENU,
    SHOW_SCANLINES,
)
from error_invaders.display import make_display, present
from error_invaders.input import Input

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

def setup(fullscreen, window_size):
    global screen, window, canvas, clock, inp, AUDIO
    pygame.mixer.pre_init(22050, -16, 1, 512)
    pygame.init()
    pygame.joystick.init()
    screen, window = make_display(fullscreen, window_size)
    pygame.display.set_caption("Error Invaders")
    pygame.mouse.set_visible(not fullscreen)
    clock = pygame.time.Clock()
    canvas = pygame.Surface((W, H)).convert()
    AUDIO = True
    try:
        if not pygame.mixer.get_init(): pygame.mixer.init(22050, -16, 1, 512)
        pygame.mixer.set_num_channels(24)
    except Exception:
        AUDIO = False
    inp = Input()

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

_sfx_queue = []  # (time, name)
def play(name, delay=0.0):
    if not AUDIO or name not in SFX or SFX[name] is None: return
    if delay > 0: _sfx_queue.append((now() + delay, name)); return
    SFX[name].play()
def arp(names, step):
    for i, n in enumerate(names): play(n, i * step)
def pump_sfx():
    t = now()
    for item in _sfx_queue[:]:
        if item[0] <= t:
            _sfx_queue.remove(item); play(item[1])

# ---------------- Hiscores ----------------
hiscores = {"easy": 0, "hard": 0}
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
    d = size + 8; S = pygame.Surface((d, d), pygame.SRCALPHA)
    o = 4; cell = size / n
    for i in range(n):
        for j in range(n):
            col = "Z" if (i + j) % 2 else "X"
            a = 242 if (col == active or active == "all") else 56
            S.fill(COL[col] + (a,), (int(o + i * cell + 1), int(o + j * cell + 1), int(cell - 2), int(cell - 2)))
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
state = "title"          # title | play | over | inputtest
mode = "easy"
menu = {"step": 0, "two": False}
title_t = over_t = 0.0
g = None

class Obj:
    def __init__(self, **kw): self.__dict__.update(kw)
    def get(self, k, default=None): return self.__dict__.get(k, default)

def make_player(pid, typ, x):
    tri = typ == "tri"
    return Obj(id=pid, type=typ, x=x, y=650, homeX=x,
               colors=["X", "Z", "Y"] if tri else ["X", "Z"], ci=0,
               cd=0.0, rate=0.30 if tri else 0.20, maxB=2 if tri else 3, speed=310 if tri else 280,
               alive=True, out=False, respawn=0.0, inv=2.0, spreadT=0.0, bombT=0.0)

def new_game(two):
    global g, state
    g = Obj(two=two, mode=mode, score=0, wave=0, lives=4 if two else 3,
            players=[make_player("p1", "tri", W/2 - 120), make_player("p2", "patch", W/2 + 120)] if two
                    else [make_player("p1", "tri", W/2)],
            pb=[], eb=[], caps=[], parts=[], pops=[], ufo=None, ufoT=rand(12, 20),
            lattice=None, merged=None, shake=0.0, chainId=1, waveT=0.0, overDelay=0.0, reason="", newHi=False,
            F=None, efT=1.5)
    next_wave()
    state = "play"

def next_wave():
    g.wave += 1
    n = g.wave
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
    if alive:
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
    elif not g.waveT and not g.overDelay:
        g.waveT = 2.2; g.eb = []
        bonus = 500 * g.wave; g.score += bonus
        pop(W/2, 300, "SYNDROME CLEAN!", SPECIAL["bias"], 18, 2)
        pop(W/2, 335, "+%d" % bonus, WHITE, 12, 2)
        arp(["n523", "n659", "n784", "n1047", "n1319"], 0.09)
    if g.waveT:
        g.waveT -= dt
        if g.waveT <= 0: g.waveT = 0; next_wave()

    # --- cosmic ray ---
    if not g.ufo:
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
        if b.y > H + 10 or b.x < -10 or b.x > W + 10: b.dead = True; continue
        if g.merged:
            if abs(b.x - g.merged.x) < 30 and abs(b.y - g.merged.y) < 22: b.dead = True; end_merge(True)
        else:
            for p in g.players:
                if p.alive and math.hypot(b.x - p.x, b.y - p.y) < 11: b.dead = True; kill_player(p)
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
            if g.score > hiscores.get(g.mode, 0):
                hiscores[g.mode] = g.score; g.newHi = True; save_hiscores()

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
    text(S, "HI %06d%s" % (hi, " · HARD" if g.mode == "hard" else ""), 12, WHITE, W/2, 14, "center", "top")
    text(S, "WAVE %d" % g.wave, 12, WHITE, W - 16, 14, "right", "top")
    text(S, "LIVES", 8, (153, 170, 170), 16, 36, "left", "top")
    for i in range(g.lives): pygame.draw.rect(S, SPECIAL["bias"], (84 + i * 16, 34, 10, 10), 2)
    text(S, "ESC: MENU", 8, (68, 68, 85), W - 16, 36, "right", "top")
    dashed_line(S, fade(COL["X"], 0.4), (0, DEATH_LINE), (W, DEATH_LINE), 6, 8, 1)
    text(S, "LOGICAL ERROR THRESHOLD", 8, fade(COL["X"], 0.55), W - 10, DEATH_LINE - 4, "right", "bottom")
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

    # cosmic ray: Gaussian wave packet
    if g.ufo:
        u = g.ufo; d = 1 if u.vx > 0 else -1
        glow(S, u.x, u.y, 46, YELLOW, 0.35)
        env = lambda dx: math.exp(-(dx * dx) / (2 * 18 * 18))
        pts = [(u.x + dx, u.y - 16 * env(dx) * math.cos(dx * 0.38 - d * u.t * 18)) for dx in range(-70, 71, 2)]
        up = [(u.x + dx, u.y - 16 * env(dx)) for dx in range(-70, 71, 2)]
        dn = [(u.x + dx, u.y + 16 * env(dx)) for dx in range(70, -71, -2)]
        pygame.draw.lines(S, fade(YELLOW, 0.3), True, up + dn, 1)
        pygame.draw.lines(S, YELLOW, False, pts, 3)

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

    # enemy projectiles (colorless zigzag)
    zz = int(t / 0.08) % 2
    for b in g.eb:
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

def draw_title(S):
    t = title_t
    S.fill(BG)
    for i, c in enumerate("XYZXZYX"):
        draw_enemy(S, W/2 - 180 + i * 60, 90 + math.sin(t * 2 + i) * 6, c, int(t * 2) % 2)
    glow(S, W/2, 180, 150, COL["X"], 0.25); glow(S, W/2, 240, 170, COL["Z"], 0.25)
    text(S, "ERROR", 44, COL["X"], W/2, 180)
    text(S, "INVADERS", 44, COL["Z"], W/2, 240)
    text(S, "RETRO MEETS QUANTUM ERROR CORRECTION", 10, (153, 170, 170), W/2, 285)

    if mode == "easy":
        text(S, "Only the matching color corrects an error.", 10, (221, 221, 221), W/2, 330)
        draw_enemy(S, W/2 - 150, 372, "Y", 0)
        text(S, "= X * Z  ->  hit it twice:", 10, (221, 221, 221), W/2 - 120, 366, "left")
        text(S, "red + blue, or purple directly", 10, (221, 221, 221), W/2 - 120, 384, "left")
    else:
        text(S, "HARD: a wrong color multiplies the error!", 10, COL["X"], W/2, 330)
        for a, b, c, y in (("Z", "X", "Y", 362), ("X", "Y", "Z", 400)):
            draw_enemy(S, W/2 - 210, y, a, 0)
            S.fill(COL[b], (W/2 - 172, y - 7, 4, 14))
            text(S, "+ %s  ->" % b, 10, (221, 221, 221), W/2 - 160, y, "left")
            draw_enemy(S, W/2 - 50, y, c, 0)
        text(S, "Pauli algebra:", 10, (153, 170, 170), W/2 + 20, 356, "left")
        text(S, "any two colors", 10, (153, 170, 170), W/2 + 20, 376, "left")
        text(S, "make the third", 10, (153, 170, 170), W/2 + 20, 394, "left")

    blit_center(S, triangle_sprite("XZY"[int(t) % 3]), W/2 - 200, 450)
    blit_center(S, patch_sprite("XZ"[int(t) % 2]), W/2 + 200, 450)
    text(S, "P1  COLOR CODE", 10, WHITE, W/2 - 200, 490)
    text(S, "P2  SURFACE PATCH", 10, WHITE, W/2 + 200, 490)
    text(S, "3 colors", 8, (153, 170, 170), W/2 - 200, 508)
    text(S, "2 colors · faster fire", 8, (153, 170, 170), W/2 + 200, 508)
    if KEY_PRESET == "default":
        text(S, "WASD · Y fire · X color", 8, (153, 170, 170), W/2 - 200, 526)
        text(S, "Arrows · , fire · . color", 8, (153, 170, 170), W/2 + 200, 526)
    else:
        text(S, "Stick · B1 fire · B2 color", 8, (153, 170, 170), W/2 - 200, 526)
        text(S, "Stick · B1 fire · B2 color", 8, (153, 170, 170), W/2 + 200, 526)

    for i, c in enumerate(("spread", "bomb", "bias", "lattice")):
        x, y = 150 + i * 220, 585
        S.fill(SPECIAL[c], (x - 11, y - 10, 22, 20))
        text(S, CAP_INFO[c][0], 10, BG, x + 1, y + 1)
        text(S, CAP_INFO[c][1], 8, (187, 187, 187), x, y + 24)
    text(S, "Power-ups: shoot the Cosmic Ray, catch the capsule", 8, (119, 119, 119), W/2, 624)

    if menu["step"] == 0:
        items = [("1 PLAYER", not menu["two"], WHITE), ("2 PLAYERS", menu["two"], WHITE)]
    else:
        items = [("EASY", mode == "easy", SPECIAL["bias"]), ("HARD", mode == "hard", COL["X"])]
    blink = int(t * 3) % 2
    for i, (label, on, col) in enumerate(items):
        y = 650 + i * 24
        text(S, label, 14, col if on else (68, 68, 68), W/2, y)
        if on and blink:
            text(S, ">", 14, col, W/2 - 110, y); text(S, "<", 14, col, W/2 + 110, y)
    if menu["step"] == 1:
        text(S, ("2 PLAYERS" if menu["two"] else "1 PLAYER") + " >", 8, (102, 102, 102), W/2 - 190, 662)
    hint = "UP/DOWN select  ·  FIRE confirm" if menu["step"] == 0 else "UP/DOWN select  ·  FIRE start  ·  COLOR back"
    text(S, hint, 8, (119, 119, 119), W/2, 696)
    text(S, "HI %06d (%s)   ·   MUNICH QUANTUM SOFTWARE FORUM" % (hiscores.get(mode, 0), mode.upper()),
         8, (85, 85, 102), W/2, 712)

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

def draw_input_test(S):
    S.fill(BG)
    text(S, "INPUT TEST", 20, WHITE, W/2, 40)
    text(S, "Press buttons / move sticks. ESC or hold SELECT 2s to leave.", 8, (170, 170, 170), W/2, 70)
    y = 110
    if not inp.joys: text(S, "No joysticks detected.", 10, COL["X"], 40, y, "left"); y += 30
    for i, j in inp.joys.items():
        who = [p for p in ("p1", "p2") if INPUT_CONFIG[p]["joystick_index"] == i]
        text(S, "JOY %d: %s %s" % (i, j.get_name()[:40], ("-> " + who[0].upper()) if who else ""), 10, SPECIAL["bias"], 40, y, "left"); y += 22
        axes = "  ".join("a%d:%+.2f" % (k, j.get_axis(k)) for k in range(j.get_numaxes()))
        text(S, "axes " + axes, 8, WHITE, 60, y, "left"); y += 18
        hats = "  ".join("h%d:%s" % (k, j.get_hat(k)) for k in range(j.get_numhats()))
        text(S, "hats " + (hats or "-"), 8, WHITE, 60, y, "left"); y += 18
        btn = " ".join(str(k) for k in range(j.get_numbuttons()) if j.get_button(k))
        text(S, "buttons down: " + (btn or "-"), 8, WHITE, 60, y, "left"); y += 30
    text(S, "last keys: " + (", ".join(inp.last_keys) or "-"), 10, YELLOW, 40, y + 10, "left")
    for i, p in enumerate(("p1", "p2")):
        text(S, "%s actions: %s" % (p.upper(), ", ".join(sorted(inp.held[p])) or "-"), 10, WHITE, 40, y + 50 + i * 24, "left")
    text(S, "Mapping lives in error_invaders/config.py (INPUT_CONFIG)", 8, (119, 119, 119), W/2, H - 30)

# =====================================================================
# Main loop
# =====================================================================
def to_menu():
    global state, title_t
    state = "title"; title_t = 0.0; menu["step"] = 0

def run(*, fullscreen=False, window_size="960x720", show_fps=False, input_test=False):
    global state, mode, title_t, over_t
    setup(fullscreen, window_size)
    load_hiscores()
    build_sounds()
    if input_test: state = "inputtest"
    running = True
    while running:
        dt = min(0.033, clock.tick(FPS) / 1000.0)
        for e in pygame.event.get():
            if e.type == pygame.QUIT: running = False
            elif e.type == pygame.KEYDOWN and e.key == pygame.K_F3: show_fps = not show_fps
            inp.handle(e)
        inp.update(dt)
        if inp.quit_combo and state != "inputtest": break
        pump_sfx()

        if state == "title":
            title_t += dt
            moved = any(inp.any_hit(a) for a in ("up", "down"))
            ok = inp.any_hit("fire") or inp.confirm
            back = inp.any_hit("swap") or inp.back
            if moved:
                if menu["step"] == 0: menu["two"] = not menu["two"]
                else: mode = "hard" if mode == "easy" else "easy"
                play("menu_move")
            if ok:
                if menu["step"] == 0: menu["step"] = 1; play("menu_ok")
                else: menu["step"] = 0; new_game(menu["two"])
            elif back and menu["step"] == 1:
                menu["step"] = 0; play("menu_back")
            elif menu["step"] == 0 and QUIT_FROM_MENU and (pygame.K_ESCAPE in inp.ev_keys or inp.back_held > BACK_HOLD_TO_QUIT):
                running = False
            if pygame.K_F1 in inp.ev_keys: state = "inputtest"
            draw_title(canvas); screen.blit(canvas, (0, 0))
        elif state == "play":
            if inp.back: to_menu()
            else:
                update(dt)
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
