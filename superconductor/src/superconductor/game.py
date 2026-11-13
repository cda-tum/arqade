"""
SUPERCONDUCTOR - route two-qubit gates across a superconducting chip
Munich Quantum Software Forum arcade edition (pygame 2.5)

Menus, drawing, sound and the main loop. The rules live in rules.py (pure,
unit tested), the chip graph in lattice.py, input mapping and tunables in
config.py / input.py.
"""

from __future__ import annotations

import asyncio
import json
import math
import random
from array import array
from dataclasses import dataclass, field
from pathlib import Path

import pygame
from arqade_common import runtime, web
from arqade_common.input import KEYBOARD, PAD

from superconductor import config, tutorial
from superconductor.display import make_display, present
from superconductor.input import ACTION_BUTTONS, Input, keyboard_enabled
from superconductor.lattice import LAYOUTS, Lattice
from superconductor.rules import Board

# =====================================================================
# Look
# =====================================================================
W, H = config.INTERNAL_WIDTH, config.INTERNAL_HEIGHT
# Layout numbers below are written for a 1280x720 design and multiplied by U,
# so the game renders natively at the panel's 1920x1080 (no SDL upscale).
U = H / 720


def px(n):
    """A design-pixel length (line width, offset, radius) in real pixels."""
    return max(1, round(n * U))


BG = (6, 8, 18)
SUBSTRATE = (13, 17, 32)
SUBSTRATE_EDGE = (40, 52, 84)
COUPLER = (48, 62, 96)
BRIDGE = (78, 100, 150)  # couplers linking blocks / modules
QUBIT_IDLE = (86, 104, 146)
WHITE = (255, 255, 255)
GREY = (150, 156, 176)
DIM = (90, 96, 116)
RED = (255, 70, 90)
GOLD = (255, 214, 102)
CYAN = (90, 220, 255)
PAIR_COLORS = [
    (255, 84, 104),   # red
    (84, 226, 128),   # green
    (255, 204, 64),   # yellow
    (186, 112, 255),  # violet
    (64, 176, 255),   # blue
    (255, 140, 48),   # orange
    (255, 116, 206),  # pink
    (110, 240, 226),  # teal
]
PLAYER_COLORS = {"p1": WHITE, "p2": GOLD}
# CO-OP: the cursors take the cabinet's sides -- left pad blue, right pad red
COOP_PLAYER_COLORS = {"p1": (70, 140, 255), "p2": (255, 60, 60)}


def player_color(board, player):
    return (COOP_PLAYER_COLORS if len(board.cursors) > 1 else PLAYER_COLORS)[player]
MISCAL_COL = (255, 150, 40)
BELL_COL = (150, 160, 255)
SPECIAL_ON_TEXT = {"miscal": ("MISCALIBRATED", MISCAL_COL), "defect": ("COUPLER DEFECT", RED),
                   "speed": ("SPEED QUBIT", GOLD), "bell": ("BELL PAIR", BELL_COL)}
SPECIAL_OFF_TEXT = {"miscal": ("RECALIBRATED", GREY), "defect": ("COUPLER RESTORED", GREY)}
MODES = ("single", "coop", "versus")
MODE_LABEL = {"single": "1 PLAYER", "coop": "CO-OP", "versus": "VERSUS"}
MODE_DESC = {
    "single": "One chip, one router.",
    "coop": "Two routers share one chip and three lives.",
    "versus": "Same pairs on two chips. Highest score wins.",
}
LATTICE_LABEL = {"square": "SQUARE", "brick": "BRICK", "bottleneck": "BOTTLENECK",
                 "distributed": "DISTRIBUTED"}
LATTICE_DESC = {
    "square": "5x5, 4 couplers per qubit, Google-style grid",
    "brick": "5x5, 3 couplers per qubit, hex / heavy-hex wiring",
    "bottleneck": "Two halves joined by just two couplers",
    "distributed": "Four 3x3 modules, one link between neighbours",
}


MENU_ROWS = ("mode", "chip", "quit")  # the title's rows, QUIT always last
# what the HOW TO PLAY card and the title's legend call each caption colour
CAPTION_COL = {"pair": PAIR_COLORS[1], "cyan": CYAN, "red": RED, "gold": GOLD,
               "miscal": MISCAL_COL, "bell": BELL_COL}


def clamp(v, a, b):
    return max(a, min(b, v))


def mix(c1, c2, k):
    k = clamp(k, 0.0, 1.0)
    return tuple(int(a + (b - a) * k) for a, b in zip(c1, c2))


def now():
    return pygame.time.get_ticks() / 1000.0


# ---------------- Fonts / text ----------------
FONT_PATH = str(Path(__file__).parent / "assets" / "fonts" / "PressStart2P-Regular.ttf")
_fonts: dict[int, pygame.font.Font] = {}
_text_cache: dict = {}


def font(size):
    if size not in _fonts:
        try:
            _fonts[size] = pygame.font.Font(FONT_PATH, size)
        except Exception:
            _fonts[size] = pygame.font.Font(None, int(size * 1.9))
    return _fonts[size]


def crisp(size):
    """A design text size that renders at a whole multiple of the font's
    native 8 px, so Press Start 2P stays sharp (used by the newer screens)."""
    return max(8, round(size * U / 8) * 8) / U


def text(S, s, size, col, x, y, align="center", valign="middle", alpha=1.0):
    """Draw text at real-pixel (x, y); `size` is in design pixels (scaled by U)."""
    size = round(size * U)
    key = (s, size, col)
    surf = _text_cache.get(key)
    if surf is None:
        if len(_text_cache) > 600:
            _text_cache.clear()
        surf = font(size).render(s, True, col)
        _text_cache[key] = surf
    r = surf.get_rect()
    if align == "center":
        r.centerx = int(x)
    elif align == "left":
        r.left = int(x)
    else:
        r.right = int(x)
    if valign == "middle":
        r.centery = int(y)
    elif valign == "top":
        r.top = int(y)
    else:
        r.bottom = int(y)
    surf.set_alpha(int(255 * clamp(alpha, 0, 1)))
    S.blit(surf, r)
    return r


# ---------------- Glow (additive radial gradient) ----------------
_glow_cache: dict = {}


def glow(S, x, y, r, col, strength=0.6):
    if not config.GLOW:
        return
    r = max(2, int(r) // 2 * 2)
    col = (col[0] // 24 * 24, col[1] // 24 * 24, col[2] // 24 * 24)  # keep the cache small
    strength = round(strength * 20) / 20
    if strength <= 0:
        return
    key = (r, col, strength)
    g = _glow_cache.get(key)
    if g is None:
        g = pygame.Surface((2 * r, 2 * r)).convert()
        g.fill((0, 0, 0))
        for i in range(r, 0, -2):
            k = (1 - i / r) ** 2 * strength
            pygame.draw.circle(g, (int(col[0] * k), int(col[1] * k), int(col[2] * k)), (r, r), i)
        _glow_cache[key] = g
    S.blit(g, (int(x - r), int(y - r)), special_flags=pygame.BLEND_ADD)


_scanlines = None


def draw_scanlines(S):
    """Darken every third row. A multiply blit of an opaque surface is much
    cheaper than an alpha blit at 1920x1080."""
    global _scanlines
    if _scanlines is None:
        _scanlines = pygame.Surface((W, H)).convert()
        _scanlines.fill((255, 255, 255))
        for y in range(0, H, 3):
            pygame.draw.line(_scanlines, (205, 205, 205), (0, y), (W, y))
    S.blit(_scanlines, (0, 0), special_flags=pygame.BLEND_RGB_MULT)


_tints: dict = {}


def tint(S, rect, col, alpha):
    """Wash a rect in a colour (one cached surface per size, alpha set per call)."""
    rect = pygame.Rect(rect)
    key = (rect.size, col)
    surf = _tints.get(key)
    if surf is None:
        surf = pygame.Surface(rect.size).convert()
        surf.fill(col)
        _tints[key] = surf
    surf.set_alpha(clamp(alpha, 0, 255))
    S.blit(surf, rect)


_veils: dict = {}


def veil(S, rect, alpha):
    """Darken a rect (cached, these are full-screen at 1080p)."""
    rect = pygame.Rect(rect)
    key = (rect.size, alpha)
    surf = _veils.get(key)
    if surf is None:
        surf = pygame.Surface(rect.size, pygame.SRCALPHA)
        surf.fill((*BG, alpha))
        _veils[key] = surf
    S.blit(surf, rect)


def dashed_path(S, col, pts, width, dash=10, gap=8, phase=0.0):
    """A dashed polyline whose dashes march along it as `phase` grows.

    `width`, `dash`, `gap` and `phase` are in design pixels (scaled by U).
    """
    width, dash, gap, phase = px(width), dash * U, gap * U, phase * U
    seglens = [math.hypot(x1 - x0, y1 - y0) for (x0, y0), (x1, y1) in zip(pts, pts[1:])]
    total = sum(seglens)
    if total <= 0:
        return

    def point(d):
        for (x0, y0), (x1, y1), length in zip(pts, pts[1:], seglens):
            if d <= length and length > 0:
                f = d / length
                return x0 + (x1 - x0) * f, y0 + (y1 - y0) * f
            d -= length
        return pts[-1]

    corners = []
    acc = 0.0
    for length in seglens[:-1]:
        acc += length
        corners.append(acc)
    period = dash + gap
    d0 = (phase % period) - period
    while d0 < total:  # one dash per iteration, so this always ends
        a, b = max(0.0, d0), min(total, d0 + dash)
        if b > a:
            # split at the polyline's corners so bends stay on the path
            cuts = [a] + [c for c in corners if a < c < b] + [b]
            for c0, c1 in zip(cuts, cuts[1:]):
                pygame.draw.line(S, col, point(c0), point(c1), width)
        d0 += period


# =====================================================================
# Sound (synthesized, no asset files)
# =====================================================================
SR = 22050
AUDIO = False
SFX: dict[str, pygame.mixer.Sound | None] = {}
_sfx_queue: list[tuple[float, str]] = []


def synth(f, d, wave="square", vol=0.05, slide=0.0):
    n = int(SR * d)
    buf = array("h")
    phase = 0.0
    f1 = max(30.0, f + slide)
    amp = min(1.0, vol * 6 * config.MASTER_VOLUME) * 32767
    for i in range(n):
        t = i / n
        fr = f * (f1 / f) ** t if slide else f
        phase += fr / SR
        ph = phase % 1.0
        if wave == "square":
            v = 1.0 if ph < 0.5 else -1.0
        elif wave == "triangle":
            v = 4 * abs(ph - 0.5) - 1
        else:
            v = math.sin(2 * math.pi * ph)
        buf.append(int(v * amp * 10 ** (-4 * t)))
    return pygame.mixer.Sound(buffer=buf.tobytes())


def synth_noise(d, vol=0.15):
    n = int(SR * d)
    buf = array("h")
    amp = min(1.0, vol * 3 * config.MASTER_VOLUME) * 32767
    for i in range(n):
        buf.append(int((random.random() * 2 - 1) * (1 - i / n) * amp))
    return pygame.mixer.Sound(buffer=buf.tobytes())


def build_sounds():
    if not AUDIO:
        return
    SFX["step"] = synth(620, 0.04, "triangle", 0.05)
    SFX["back"] = synth(420, 0.04, "triangle", 0.04)
    SFX["blocked"] = synth(110, 0.07, "square", 0.03)
    SFX["select"] = synth(900, 0.03, "square", 0.025)
    SFX["spawn"] = synth(330, 0.18, "sine", 0.06, 330)
    SFX["routed"] = synth(500, 0.16, "triangle", 0.06, 500)
    SFX["decohere"] = synth_noise(0.6, 0.18)
    SFX["menu_move"] = synth(520, 0.05, "square", 0.04)
    SFX["menu_ok"] = synth(780, 0.07, "square", 0.05)
    SFX["pause"] = synth(660, 0.12, "triangle", 0.05, -260)
    SFX["over"] = synth(300, 0.9, "triangle", 0.08, -220)
    SFX["teleport"] = synth(400, 0.25, "sine", 0.07, 1200)
    SFX["boost"] = synth(700, 0.15, "square", 0.04, 700)
    SFX["special"] = synth(240, 0.25, "triangle", 0.06, -80)
    SFX["crash"] = synth_noise(0.9, 0.25)
    for f in (523, 659, 784, 1047):
        SFX[f"n{f}"] = synth(f, 0.09, "square", 0.04)


def play(name, delay=0.0):
    if not AUDIO or SFX.get(name) is None:
        return
    if delay > 0:
        _sfx_queue.append((now() + delay, name))
    else:
        SFX[name].play()


def pump_sfx():
    t = now()
    for item in _sfx_queue[:]:
        if item[0] <= t:
            _sfx_queue.remove(item)
            play(item[1])


_play = play  # View.consume_events wraps it to stay quiet in the demo scenes


# =====================================================================
# Board view: where a chip sits on screen, plus its eye candy
# =====================================================================
@dataclass
class View:
    """Where a chip sits on screen: centred in a box, as large as fits."""

    board: Board
    cx: float
    cy: float
    box_w: float
    box_h: float
    label: str = ""
    max_spacing: float = 112 * U
    particles: list = field(default_factory=list)  # [x, y, vx, vy, life, max_life, col]
    rings: list = field(default_factory=list)  # [x, y, r0, r1, life, max_life, col]
    popups: list = field(default_factory=list)  # [x, y, text, col, size, life, max_life]
    shake: float = 0.0
    flash: float = 0.0
    hurt: float = 0.0  # 1 -> 0 after a life is lost
    quiet: bool = False  # the title legend and HOW TO PLAY scenes make no sound

    PAD = 0.62  # substrate margin around the outer qubits, in spacings

    def __post_init__(self):
        y0, x0, y1, x1 = self.board.lattice.extent()
        self._mid = ((y0 + y1) / 2, (x0 + x1) / 2)
        self._span = (y1 - y0, x1 - x0)
        self.spacing = min(self.box_w / (self._span[1] + 2 * self.PAD),
                           self.box_h / (self._span[0] + 2 * self.PAD), self.max_spacing)

    def xy(self, where) -> tuple[float, float]:
        """Screen position of a node, the middle of a tuple of nodes, or a
        point (n0, n1, f) f of the way from n0 to n1 (a crash on a coupler)."""
        if isinstance(where[-1], float):
            (x0, y0), (x1, y1) = self.xy(where[0]), self.xy(where[1])
            f = where[2]
            return x0 + (x1 - x0) * f, y0 + (y1 - y0) * f
        if isinstance(where[0], tuple):
            pts = [self.xy(n) for n in where]
            return sum(p[0] for p in pts) / len(pts), sum(p[1] for p in pts) / len(pts)
        y, x = self.board.lattice.positions[where]
        return (self.cx + (x - self._mid[1]) * self.spacing,
                self.cy + (y - self._mid[0]) * self.spacing)

    def qubit_xy(self, pair) -> tuple[float, float]:
        n0, n1, f, jump = pair.segment()
        if jump:
            return self.xy(n0 if f < 0.5 else n1)
        return self.xy((n0, n1, float(f)))

    def substrate_rect(self) -> pygame.Rect:
        w = (self._span[1] + 2 * self.PAD) * self.spacing
        h = (self._span[0] + 2 * self.PAD) * self.spacing
        return pygame.Rect(int(self.cx - w / 2), int(self.cy - h / 2), int(w), int(h))

    # ------------------------------------------------------------ effects
    def burst(self, node, col, n=18, speed=160):
        x, y = self.xy(node)
        for _ in range(n):
            a = random.uniform(0, 2 * math.pi)
            v = random.uniform(0.3, 1.0) * speed * U
            life = random.uniform(0.4, 0.9)
            self.particles.append([x, y, math.cos(a) * v, math.sin(a) * v, life, life, col])

    def ring(self, node, col, r0, r1, life=0.5):
        """An expanding ring; r0 in design pixels, r1 usually spacing-based."""
        x, y = self.xy(node)
        self.rings.append([x, y, r0 * U, r1, life, life, col])

    def popup(self, node, txt, col, size=12, life=1.2, dy=0):
        x, y = self.xy(node)
        self.popups.append([x, y + (dy - 30) * U, txt, col, size, life, life])

    def consume_events(self):
        def play(name, delay=0.0):
            if not self.quiet:
                _play(name, delay)

        for e in self.board.events:
            pair = e.pair
            col = PAIR_COLORS[pair.color] if pair else WHITE
            if e.kind == "spawn":
                for n in (pair.a, pair.b):
                    self.ring(n, col, 6, self.spacing * 0.5, 0.6)
                play("spawn")
            elif e.kind == "select":
                if e.player is not None:
                    self.ring(e.node, player_color(self.board, e.player), self.spacing * 0.45 / U, self.spacing * 0.3, 0.25)
                play("select")
            elif e.kind == "step":
                play("step")
            elif e.kind == "back":
                play("back")
            elif e.kind == "blocked":
                if e.node is not None:
                    self.ring(e.node, RED, self.spacing * 0.2 / U, self.spacing * 0.35, 0.25)
                play("blocked")
            elif e.kind == "routed":
                for n in (pair.a, pair.b):
                    self.ring(n, col, 8, self.spacing * 0.4, 0.4)
                # the superposition collapses onto the start: gone from the far end
                self.ring(pair.route[-1], WHITE, self.spacing * 0.3 / U, self.spacing * 0.05, 0.3)
                play("routed")
            elif e.kind == "gate":
                for n in (pair.a, pair.b):
                    self.burst(n, col)
                    self.ring(n, WHITE, 8, self.spacing * 0.7, 0.5)
                self.popup(e.node, f"+{e.points}", WHITE, 14)
                self.popup(e.node, f"F {round(e.fidelity * 100)}%", col, 8, dy=20)
                for i, f in enumerate((523, 659, 784, 1047)):
                    play(f"n{f}", i * 0.05)
            elif e.kind == "teleport":
                self.ring(e.node, BELL_COL, 6, self.spacing * 0.6, 0.5)
                play("teleport")
            elif e.kind == "boost":
                self.ring(e.node, GOLD, 6, self.spacing * 0.5, 0.4)
                self.popup(e.node, "x%g" % pair.boost, GOLD, 10, 0.9)
                play("boost")
            elif e.kind == "crash":
                self.burst(e.node, WHITE, 40, 220)
                for p in e.pairs:
                    self.burst(e.node, PAIR_COLORS[p.color], 20, 160)
                    for n in (p.a, p.b):
                        self.ring(n, RED, 6, self.spacing * 0.6, 0.6)
                self.ring(e.node, RED, 6, self.spacing * 1.2, 0.8)
                self.popup(e.node, "COLLISION", RED, 14, 1.8)
                self.shake = 0.5
                self.flash = 0.3
                self.hurt = 1.0
                play("crash")
            elif e.kind in ("special_on", "special_off"):
                table = SPECIAL_ON_TEXT if e.kind == "special_on" else SPECIAL_OFF_TEXT
                if e.special.kind in table:
                    label, tcol = table[e.special.kind]
                    self.popup(e.special.anchor(), label, tcol, 8, 1.8)
                    for n in e.special.nodes:
                        self.ring(n, tcol, 6, self.spacing * 0.6, 0.6)
                    play("special")
            elif e.kind == "decohere":
                for n in (pair.a, pair.b):
                    self.burst(n, (120, 120, 140), 26, 110)
                    self.ring(n, RED, 6, self.spacing * 0.8, 0.7)
                mid = pair.a if pair.a[0] <= pair.b[0] else pair.b
                self.popup(mid, "DECOHERED", RED, 12, 1.6)
                self.shake = 0.35
                self.flash = 0.25
                self.hurt = 1.0
                play("decohere")
        self.board.events.clear()

    def update_fx(self, dt):
        for p in self.particles:
            p[0] += p[2] * dt
            p[1] += p[3] * dt
            p[2] *= 0.92
            p[3] *= 0.92
            p[4] -= dt
        self.particles = [p for p in self.particles if p[4] > 0]
        for r in self.rings:
            r[4] -= dt
        self.rings = [r for r in self.rings if r[4] > 0]
        for p in self.popups:
            p[1] -= 22 * U * dt
            p[5] -= dt
        self.popups = [p for p in self.popups if p[5] > 0]
        self.shake = max(0.0, self.shake - dt)
        self.flash = max(0.0, self.flash - dt)
        self.hurt = max(0.0, self.hurt - dt / config.HURT_SECONDS)


# =====================================================================
# Drawing a chip
# =====================================================================
def draw_xmon(S, x, y, size, col, fill=True):
    """An Xmon-style cross-shaped transmon qubit."""
    arm = int(size * 0.24)
    thick = max(4, int(size * 0.09))
    pygame.draw.rect(S, col, (x - arm, y - thick // 2, 2 * arm, thick), 0 if fill else 2, px(2))
    pygame.draw.rect(S, col, (x - thick // 2, y - arm, thick, 2 * arm), 0 if fill else 2, px(2))


def draw_qubit(S, x, y, r, col, presence=1.0):
    """The pair's qubit: a light disc ringed in white, fainter as `presence` drops."""
    pygame.draw.circle(S, mix(col, mix(col, WHITE, 0.5), presence), (int(x), int(y)), int(r))
    pygame.draw.circle(S, mix(col, WHITE, presence), (int(x), int(y)), int(r), px(2))


def draw_x(S, x, y, k, col, width):
    pygame.draw.line(S, col, (x - k, y - k), (x + k, y + k), width)
    pygame.draw.line(S, col, (x - k, y + k), (x + k, y - k), width)


def draw_board(S, v: View, t: float):
    b = v.board
    lat = b.lattice
    ox = oy = 0
    if v.shake > 0:
        ox = random.uniform(-5, 5) * v.shake * 2 * U
        oy = random.uniform(-5, 5) * v.shake * 2 * U
    sp = v.spacing

    def xy(n):
        x, y = v.xy(n)
        return x + ox, y + oy

    rect = v.substrate_rect().move(int(ox), int(oy))
    pygame.draw.rect(S, SUBSTRATE, rect, 0, px(18))
    edge_col = mix(SUBSTRATE_EDGE, RED, v.flash * 3)
    pygame.draw.rect(S, edge_col, rect, px(3), px(18))
    # bond pads around the rim, purely decorative
    inset, pad = px(9), px(4)
    for i in range(1, 8):
        for (bx, by) in ((rect.left + rect.w * i / 8, rect.top + inset), (rect.left + rect.w * i / 8, rect.bottom - inset),
                         (rect.left + inset, rect.top + rect.h * i / 8), (rect.right - inset, rect.top + rect.h * i / 8)):
            pygame.draw.rect(S, (30, 38, 62), (bx - pad, by - pad, 2 * pad, 2 * pad), 0, px(2))

    # couplers
    committed = b.route_edges()
    for e in lat.edges:
        n0, n1 = tuple(e)
        p0, p1 = xy(n0), xy(n1)
        routes = committed.get(e)
        special = b.edge_special(e)
        blink = special is not None and special.life < 3 and int(t * 6) % 2 == 0
        if routes:
            # routes sharing a coupler run side by side, so each color shows
            dx, dy = p1[0] - p0[0], p1[1] - p0[1]
            length = math.hypot(dx, dy)
            nx, ny = -dy / length, dx / length
            shared = len(routes) > 1
            for i, pair in enumerate(routes):
                off = (i - (len(routes) - 1) / 2) * px(9)
                q0 = (p0[0] + nx * off, p0[1] + ny * off)
                q1 = (p1[0] + nx * off, p1[1] + ny * off)
                col = PAIR_COLORS[pair.color]
                pygame.draw.line(S, mix(col, SUBSTRATE, 0.55), q0, q1, px(8 if shared else 12))
                pygame.draw.line(S, col, q0, q1, px(4 if shared else 5))
        elif special is not None and special.kind == "defect" and not blink:
            # broken in the middle, with an X over the gap
            mx, my = (p0[0] + p1[0]) / 2, (p0[1] + p1[1]) / 2
            for a in (p0, p1):
                pygame.draw.line(S, mix(RED, SUBSTRATE, 0.4), a,
                                 (a[0] + (mx - a[0]) * 0.6, a[1] + (my - a[1]) * 0.6), px(4))
            draw_x(S, mx, my, sp * 0.09, RED, px(4))
            continue
        elif e in lat.bridges:
            # links between blocks / modules: a hollow "waveguide" line
            pygame.draw.line(S, BRIDGE, p0, p1, px(9))
            pygame.draw.line(S, SUBSTRATE, p0, p1, px(3))
        else:
            pygame.draw.line(S, COUPLER, p0, p1, px(4))
        if special is not None and special.kind == "miscal" and not blink:
            # a wobbly orange trace on top: slow, noisy coupler
            dx, dy = p1[0] - p0[0], p1[1] - p0[1]
            length = math.hypot(dx, dy)
            nx, ny = -dy / length, dx / length
            pts = []
            for i in range(25):
                f = i / 24
                w = math.sin(f * math.pi * 6 + t * 5) * sp * 0.06 * math.sin(f * math.pi)
                pts.append((p0[0] + dx * f + nx * w, p0[1] + dy * f + ny * w))
            pygame.draw.lines(S, MISCAL_COL, False, pts, px(3))

    # Bell links: a faint marching line between the two qubits
    for special in b.specials:
        if special.kind != "bell" or (special.life < 3 and int(t * 6) % 2 == 0):
            continue
        (ax, ay), (cx, cy) = (xy(n) for n in special.nodes)
        # bowed, so it never reads as a coupler even along a row
        mx, my = (ax + cx) / 2 - (cy - ay) * 0.25, (ay + cy) / 2 + (cx - ax) * 0.25
        pts = [((1 - f) ** 2 * ax + 2 * (1 - f) * f * mx + f * f * cx,
                (1 - f) ** 2 * ay + 2 * (1 - f) * f * my + f * f * cy) for f in (i / 20 for i in range(21))]
        col = BELL_COL if special.claimed_by is None else PAIR_COLORS[b.pairs[special.claimed_by].color]
        dashed_path(S, mix(col, SUBSTRATE, 0.45), pts, 2, 6, 10, t * 30)

    # routes being drawn (marching dashes) -- under the qubits
    for player, cur in b.cursors.items():
        if cur.pair_id is None or len(cur.path) < 2:
            continue
        col = mix(PAIR_COLORS[b.pairs[cur.pair_id].color], WHITE, 0.35)
        for n0, n1 in zip(cur.path, cur.path[1:]):
            if lat.has_edge(n0, n1):  # a Bell jump has no line, the link shows it
                dashed_path(S, col, [xy(n0), xy(n1)], 6, 12, 7, t * 40)

    # qubits
    on_route = {}
    for pair in b.travelling_pairs():
        for n in pair.route[int(pair.progress):]:
            on_route.setdefault(n, pair)
    for n in lat.nodes:
        x, y = xy(n)
        owner = b.endpoint_owner.get(n)
        pair = b.pairs.get(owner) if owner is not None else None
        special = b.node_special(n)
        if pair is not None and pair.waiting:
            col = PAIR_COLORS[pair.color]
            frac = clamp(pair.life / pair.coherence, 0, 1)
            urgent = frac < 0.3
            pulse = 0.5 + 0.5 * math.sin(t * (14 if urgent else 5) + pair.id)
            glow(S, x, y, sp * 0.55, col, 0.35 + 0.35 * pulse)
            draw_xmon(S, x, y, sp * (1.08 + 0.06 * pulse), mix(col, WHITE, 0.2 * pulse))
            arc_col = mix(col, RED, 1.0 if urgent and pulse > 0.5 else 0.0)
            r = sp * 0.36
            arc_rect = pygame.Rect(0, 0, 2 * r, 2 * r)
            arc_rect.center = (int(x), int(y))
            pygame.draw.arc(S, mix(SUBSTRATE, col, 0.25), arc_rect, 0, 2 * math.pi, px(2))
            if frac > 0.01:
                pygame.draw.arc(S, arc_col, arc_rect, math.pi / 2, math.pi / 2 + 2 * math.pi * frac, px(4))
            # The pair's qubit, in superposition: it is in both stations until
            # the pair is routed, so it shows in both, swelling in one as it
            # shrinks in the other. Running into either one crashes.
            amp = 0.5 + 0.5 * math.sin(t * 3 + pair.id * 1.7 + (math.pi if n == pair.b else 0.0))
            draw_qubit(S, x, y, sp * (0.105 + 0.035 * amp), col, 0.6 + 0.4 * amp)
            continue
        if pair is not None:
            # routed: the qubit has collapsed onto the route, the station is empty
            draw_xmon(S, x, y, sp * 1.05, mix(PAIR_COLORS[pair.color], SUBSTRATE, 0.55))
        elif n in on_route:
            draw_xmon(S, x, y, sp * 0.95, mix(PAIR_COLORS[on_route[n].color], QUBIT_IDLE, 0.45))
        else:
            draw_xmon(S, x, y, sp, QUBIT_IDLE)
        if special is None or (special.life < 3 and int(t * 6) % 2 == 0):
            continue
        if special.kind == "speed":
            glow(S, x, y, sp * 0.45, GOLD, 0.35)
            k = sp * 0.11
            for dx in (-k * 1.1, k * 0.5):
                cx = x + dx + math.sin(t * 6) * 2 * U
                pygame.draw.polygon(S, GOLD, [(cx - k * 0.6, y - k), (cx + k * 0.6, y), (cx - k * 0.6, y + k),
                                              (cx - k * 0.1, y)])
        elif special.kind == "bell":
            r = sp * (0.3 + 0.03 * math.sin(t * 4))
            col = BELL_COL if special.claimed_by is None else PAIR_COLORS[b.pairs[special.claimed_by].color]
            glow(S, x, y, sp * 0.5, col, 0.3)
            pygame.draw.circle(S, col, (int(x), int(y)), int(r), px(2))
            pygame.draw.circle(S, col, (int(x), int(y)), int(r * 0.7), px(2))

    # travelling qubits
    for pair in b.travelling_pairs():
        col = PAIR_COLORS[pair.color]
        x, y = v.qubit_xy(pair)
        x, y = x + ox, y + oy
        glow(S, x, y, sp * 0.6, col, 0.8)
        draw_qubit(S, x, y, sp * 0.13, col)
        if pair.boost > 1:
            pygame.draw.circle(S, GOLD, (int(x), int(y)), int(sp * 0.19), px(2))

    # stations a committed route is about to run into: route that pair away
    # from there in time, or it crashes. A blinking X on the station.
    if int(t * 4) % 2 == 0:
        for n in b.station_threats():
            cx, cy = xy(n)
            draw_x(S, cx, cy, sp * 0.14, RED, px(3))

    # cursors: a wobbling rounded square on the chosen station (and a smaller
    # one on the route's head), a spinning marker on the target, and a
    # warning where the route as drawn would crash
    for player, cur in b.cursors.items():
        if cur.pair_id is None:
            continue
        pcol = player_color(b, player)
        pair = b.pairs[cur.pair_id]
        phase = 0 if player == "p1" else math.pi
        sx, sy = xy(cur.path[0])
        size = sp * 0.88 * (1 + 0.08 * math.sin(t * 6 + phase))
        box = pygame.Rect(0, 0, int(size), int(size))
        box.center = (int(sx), int(sy))
        pygame.draw.rect(S, pcol, box, px(4), int(size * 0.28))
        if len(b.cursors) > 1:
            text(S, "P1" if player == "p1" else "P2", 8, pcol, sx, sy - sp * 0.56)
        if len(cur.path) > 1:
            hx, hy = xy(cur.path[-1])
            size = sp * 0.5 * (1 + 0.1 * math.sin(t * 8 + phase))
            box = pygame.Rect(0, 0, int(size), int(size))
            box.center = (int(hx), int(hy))
            pygame.draw.rect(S, pcol, box, px(3), int(size * 0.28))
        tx, ty = xy(pair.other(cur.path[0]))
        if int(t * 3) % 2 == 0:
            r = sp * 0.42
            for k in range(4):
                a0 = k * math.pi / 2 + t * 2
                arc_rect = pygame.Rect(0, 0, 2 * r, 2 * r)
                arc_rect.center = (int(tx), int(ty))
                pygame.draw.arc(S, pcol, arc_rect, a0, a0 + 0.7, px(2))
        crash = b.predict_collision(player)
        if crash is not None and int(t * 5) % 2 == 0:
            cx, cy = xy(crash)
            draw_x(S, cx, cy, sp * 0.2, RED, px(5))
            pygame.draw.circle(S, RED, (int(cx), int(cy)), int(sp * 0.34), px(3))

    # a life was just lost: the whole chip flashes red, fading out
    if v.hurt > 0:
        blink = 0.6 + 0.4 * math.sin(t * 28)
        tint(S, rect, RED, int(130 * v.hurt * blink))
        pygame.draw.rect(S, RED, rect.inflate(px(10), px(10)), px(6), px(22))

    # effects
    for p in v.particles:
        k = p[4] / p[5]
        pygame.draw.circle(S, mix(BG, p[6], k), (int(p[0] + ox), int(p[1] + oy)), max(1, int(3 * U * k)))
    for rg in v.rings:
        k = 1 - rg[4] / rg[5]
        rad = rg[2] + (rg[3] - rg[2]) * k
        pygame.draw.circle(S, mix(rg[6], SUBSTRATE, k), (int(rg[0] + ox), int(rg[1] + oy)), max(1, int(rad)), px(2))
    for p in v.popups:
        text(S, p[2], p[4], p[3], p[0] + ox, p[1] + oy, alpha=min(1.0, p[5] / p[6] * 2))


def draw_lives(S, x, y, lives, total, align="left", hurt=0.0, t=0.0):
    """Life icons; the one just lost (index `lives`) swells and blinks red while `hurt`."""
    step = 34 * U
    x0 = x if align == "left" else x - (total - 1) * step
    for i in range(total):
        if i < lives:
            draw_xmon(S, x0 + i * step, y, 56 * U, CYAN)
        elif i == lives and hurt > 0:
            on = int(t * 10) % 2 == 0
            glow(S, x0 + i * step, y, 60 * U * hurt, RED, 0.8 * hurt)
            draw_xmon(S, x0 + i * step, y, 56 * U * (1 + 0.9 * hurt), RED if on else WHITE)
        else:
            draw_xmon(S, x0 + i * step, y, 56 * U, (40, 46, 66))


def draw_board_hud(S, v: View, title: str, t: float = 0.0):
    b = v.board
    rect = v.substrate_rect()
    y = rect.top - 30 * U
    text(S, title, 12, GREY, rect.left, y - 22 * U, "left")
    text(S, f"{b.score:06d}", 20, WHITE, rect.left, y + 4 * U, "left")
    draw_lives(S, rect.right - 8 * U, y + 4 * U, b.lives, config.LIVES, "right", v.hurt, t)
    if v.hurt > 0:
        text(S, "LIFE LOST", 14, RED, rect.centerx, y + 4 * U, alpha=min(1.0, v.hurt * 2))
    text(S, f"GATES {b.gates}", 8, GREY, rect.right, y - 22 * U, "right")


# =====================================================================
# Scripted scenes (title legend, HOW TO PLAY) and the cabinet's buttons
# =====================================================================
class SceneView:
    """A tutorial.ScenePlayer on screen: a small chip in a box, captioned."""

    def __init__(self, order, cx, cy, box_w, box_h):
        self.player = tutorial.ScenePlayer(order)
        self.box = (cx, cy, box_w, box_h)
        self.view = None
        self._fit()

    def _fit(self):
        self.view = View(self.player.board, *self.box, quiet=True)

    def update(self, dt):
        self.player.update(dt)
        if self.view.board is not self.player.board:  # the next scene began
            self._fit()
        self.view.consume_events()
        self.view.update_fx(dt)

    def draw(self, S, t, caption_y, dots=True):
        """The chip, then the scene's name and two lines under it, centred."""
        draw_board(S, self.view, t)
        scene = self.player.scene
        cx = self.box[0]
        # fade the caption in with each new scene
        alpha = min(1.0, self.player.time * 3)
        text(S, scene.name, crisp(16), CAPTION_COL[scene.color], cx, caption_y, alpha=alpha)
        for i, line in enumerate(scene.lines):
            text(S, line, crisp(11), WHITE if i == 0 else GREY, cx, caption_y + (34 + i * 22) * U, alpha=alpha)
        if dots and len(self.player.order) > 1:
            n = len(self.player.order)
            for i in range(n):
                x = cx + (i - (n - 1) / 2) * 16 * U
                on = i == self.player.index
                pygame.draw.circle(S, WHITE if on else (40, 46, 66), (int(x), int(caption_y + 92 * U)), px(3))


# The pad's printed 2x3 cluster, as on the cabinet: top row L X R, bottom Y B A.
PAD_LAYOUT = (("L", "X", "R"), ("Y", "B", "A"))
# what each button does in a match (Y is not used)
PAD_ACTIONS = ((("STICK",), "DRAW ROUTE"), (("A", "R"), "NEXT PAIR"), (("L",), "PREVIOUS PAIR"),
               (("B",), "OTHER END"), (("X",), "UNDO A STEP"), (("START",), "PAUSE"))
BUTTON_COL = {"A": PAIR_COLORS[1], "R": PAIR_COLORS[1], "L": PAIR_COLORS[4], "B": GOLD, "X": MISCAL_COL}
KEYBOARD_STICKS = {"p1": "WASD", "p2": "ARROWS"}  # the keys that stand in for each player's stick
# Same as the folder name in the web build and the "id" in game.json.
GAME_ID = "superconductor"


def draw_button(S, x, y, label, col, r=None):
    """One round cabinet button with its printed letter; `col` None = unused."""
    r = r or 17 * U
    if col is None:
        pygame.draw.circle(S, (40, 46, 66), (int(x), int(y)), int(r), px(2))
        text(S, label, crisp(11), (60, 66, 90), x + U, y + U)
        return
    pygame.draw.circle(S, mix(col, SUBSTRATE, 0.35), (int(x), int(y)), int(r))
    pygame.draw.circle(S, col, (int(x), int(y)), int(r), px(3))
    text(S, label, crisp(11), BG, x + U, y + U)


def draw_stick(S, x, y, t, r=None):
    """The joystick from above, nudged round the four directions."""
    r = r or 22 * U
    pygame.draw.circle(S, (30, 38, 62), (int(x), int(y)), int(r))
    pygame.draw.circle(S, SUBSTRATE_EDGE, (int(x), int(y)), int(r), px(2))
    dx, dy = ((1, 0), (0, 1), (-1, 0), (0, -1))[int(t * 1.5) % 4]
    k = r * 0.45 if (t * 1.5) % 1 < 0.6 else 0.0
    pygame.draw.circle(S, WHITE, (int(x + dx * k), int(y + dy * k)), int(r * 0.5))


ARROW_KEYS = {"UP": (0, -1), "DOWN": (0, 1), "LEFT": (-1, 0), "RIGHT": (1, 0)}


def draw_keycap(S, x, y, size, label, col):
    """One keyboard key centred on (x, y), coloured like the pad button it
    stands in for (`col` None = unused); the arrow keys show an arrow."""
    rect = pygame.Rect(0, 0, int(size), int(size))
    rect.center = (int(x), int(y))
    radius = px(6)
    if col is None:
        pygame.draw.rect(S, (40, 46, 66), rect, px(2), radius)
        fg = (60, 66, 90)
    else:
        pygame.draw.rect(S, mix(col, SUBSTRATE, 0.35), rect, 0, radius)
        pygame.draw.rect(S, col, rect, px(3), radius)
        fg = BG
    if label in ARROW_KEYS:
        dx, dy = ARROW_KEYS[label]
        k = size * 0.2
        tip = (x + dx * k, y + dy * k)
        pygame.draw.polygon(S, fg, (tip, (x - dx * k - dy * k, y - dy * k - dx * k),
                                    (x - dx * k + dy * k, y - dy * k + dx * k)))
    else:
        text(S, label, crisp(11), fg, x + U, y + U)


def draw_keys(S, devices, player, x, y, cap, pitch):
    """A keyboard player's keys, top-left at (x, y): the four direction keys,
    then the six keys laid out like the pad's cluster (L X R over Y B A),
    each in its button's colour."""
    step = cap + 3 * U
    dirs = (("up", 1, 0), ("left", 0, 1), ("down", 1, 1), ("right", 2, 1))
    for name, c, r in dirs:
        draw_keycap(S, x + (c + 0.5) * step, y + cap / 2 + r * pitch, cap, devices.label(name, player), WHITE)
    gx = x + 3 * step + cap / 2 + 12 * U
    for r, letters in enumerate(PAD_LAYOUT):
        for c, letter in enumerate(letters):
            draw_keycap(S, gx + c * pitch, y + cap / 2 + r * pitch, cap,
                        devices.label(letter.lower(), player), BUTTON_COL.get(letter))


def draw_pad_names(S, names, x0, y):
    """A row's pad controls as small icons from x0: the stick, round
    buttons, or the START pill."""
    for k, name in enumerate(names):
        x = x0 + (16 + 32 * k) * U
        if name == "STICK":
            draw_stick(S, x, y, 0.0, 13 * U)
        elif name == "START":
            rect = pygame.Rect(0, 0, int(70 * U), int(22 * U))
            rect.midleft = (int(x0), int(y))
            pygame.draw.rect(S, WHITE, rect, px(2), px(11))
            text(S, "START", crisp(11), WHITE, rect.centerx + U, y + U)
        else:
            draw_button(S, x, y, name, BUTTON_COL[name], 13 * U)


# =====================================================================
# The game
# =====================================================================
class Game:
    def __init__(self, fullscreen, window_size, show_fps, pad_layout=None):
        global AUDIO
        pygame.mixer.pre_init(SR, -16, 1, 512)
        pygame.init()
        pygame.joystick.init()
        self.screen, self.window = make_display(fullscreen, window_size)
        pygame.display.set_caption("Superconductor")
        pygame.mouse.set_visible(not fullscreen)
        self.clock = pygame.time.Clock()
        AUDIO = True
        try:
            if not pygame.mixer.get_init():
                pygame.mixer.init(SR, -16, 1, 512)
            pygame.mixer.set_num_channels(16)
        except Exception:
            AUDIO = False
        build_sounds()
        self.inp = Input(pad_layout)
        self.playing = False  # a match is on (for the page's game-start / game-end events)
        self.show_fps = show_fps
        self.state = "title"
        self.mode = "single"
        self.lattice_kind = "square"
        self.menu_row = 0
        self.quit_requested = False  # QUIT on the title: leave like Start + Select
        self.t = 0.0
        self.state_t = 0.0
        self.views: list[View] = []
        self.hiscores: dict[str, int] = {}
        self.new_best = False
        self._load_hiscores()
        self._make_demo()
        # the title's legend: what each thing on the chip is, one at a time
        self.legend = SceneView(tutorial.LEGEND, 900 * U, 318 * U, 420 * U, 236 * U)

    # ------------------------------------------------------------ hiscores
    def _hiscore_key(self):
        return f"{self.mode}-{self.lattice_kind}"

    def _load_hiscores(self):
        try:
            with open(config.HISCORE_FILE) as f:
                self.hiscores.update(json.load(f))
        except Exception:
            pass

    def _save_hiscores(self):
        try:
            with open(config.HISCORE_FILE, "w") as f:
                json.dump(self.hiscores, f)
        except Exception:
            pass

    # ------------------------------------------------------------ setup
    def _make_demo(self):
        lat = Lattice(self.lattice_kind, config.GRID_ROWS, config.GRID_COLS)
        board = Board(lat, random.randrange(1 << 30), (), lives=10 ** 9)
        self.demo = View(board, 900 * U, 400 * U, 400 * U, 400 * U)
        self.demo_timer = 0.0

    def start_game(self):
        seed = random.randrange(1 << 30)
        lat = Lattice(self.lattice_kind, config.GRID_ROWS, config.GRID_COLS)
        if self.mode == "versus":
            lat2 = Lattice(self.lattice_kind, config.GRID_ROWS, config.GRID_COLS)
            self.views = [View(Board(lat, seed, ("p1",)), W * 0.25, 400 * U, 580 * U, 530 * U, "P1"),
                          View(Board(lat2, seed, ("p2",)), W * 0.75, 400 * U, 580 * U, 530 * U, "P2")]
        else:
            players = ("p1", "p2") if self.mode == "coop" else ("p1",)
            self.views = [View(Board(lat, seed, players), W / 2, 395 * U, 640 * U, 590 * U,
                               "CO-OP" if self.mode == "coop" else "")]
        self.player_view = {p: v for v in self.views for p in v.board.players}
        self.new_best = False
        # every match from the title opens on the HOW TO PLAY card
        self.how_to = SceneView(tutorial.HOW_TO_PLAY, 350 * U, 382 * U, 470 * U, 250 * U)
        self.set_state("tutorial")
        play("menu_ok")

    def set_state(self, state):
        self.state = state
        self.state_t = 0.0

    # ------------------------------------------------------------ per-state update
    def update_title(self, dt):
        inp = self.inp
        move = inp.any_move()
        row = MENU_ROWS[self.menu_row]
        if move in ("up", "down"):
            new = clamp(self.menu_row + (1 if move == "down" else -1), 0, len(MENU_ROWS) - 1)
            if new != self.menu_row:
                self.menu_row = new
                play("menu_move")
        elif move in ("left", "right") and row != "quit":
            step = 1 if move == "right" else -1
            if row == "mode":
                self.mode = MODES[(MODES.index(self.mode) + step) % len(MODES)]
            else:
                kinds = LAYOUTS
                self.lattice_kind = kinds[(kinds.index(self.lattice_kind) + step) % len(kinds)]
                self._make_demo()
            play("menu_move")
        # Start always plays, whatever row is picked; A plays too, or quits on QUIT
        if inp.confirm or (inp.any_hit("next") and row != "quit"):
            self.start_game()
            return
        if inp.any_hit("next"):
            self.quit_requested = True
            return
        if row != "chip":
            self.legend.update(dt)
        # the title chip plays itself
        demo = self.demo.board
        demo.update(dt)
        self.demo_timer -= dt
        if self.demo_timer <= 0:
            self.demo_timer = 1.4
            for pair in demo.waiting_pairs():
                if pair.life < pair.coherence - 1.5:
                    route = demo.free_route(pair, random.choice((pair.a, pair.b)))
                    if route:
                        demo.commit_route(pair.id, route)
                        break
        demo.events.clear()
        self.demo.update_fx(dt)

    def update_tutorial(self, dt):
        """The HOW TO PLAY card: any button after MIN_SHOW starts the match."""
        self.how_to.update(dt)
        kb = keyboard_enabled()
        if any(tutorial.dismisses(kind, self.state_t, kb) for kind in self.inp.presses):
            # The buttons held now count as already pressed (Input's edges),
            # so this press does nothing in the match itself.
            play("menu_ok")
            self.set_state("play")

    def update_play(self, dt):
        inp = self.inp
        if inp.pause or inp.back:
            self.set_state("paused")
            play("pause")
            return
        for player, view in self.player_view.items():
            b = view.board
            if b.over:
                continue
            if inp.move[player]:
                b.move(player, inp.move[player])
            if inp.hit(player, "next"):
                b.select(player, 1)
            if inp.hit(player, "prev"):
                b.select(player, -1)
            if inp.hit(player, "other"):
                b.other_end(player)
            if inp.hit(player, "undo"):
                b.undo(player)
        for v in self.views:
            was_over = v.board.over
            v.board.update(dt)
            v.consume_events()
            v.update_fx(dt)
            if v.board.over and not was_over and len(self.views) > 1:
                play("over")
        if all(v.board.over for v in self.views):
            self.finish()

    def finish(self):
        if self.mode != "versus":
            score = self.views[0].board.score
            key = self._hiscore_key()
            if score > self.hiscores.get(key, 0):
                self.hiscores[key] = score
                self.new_best = True
                self._save_hiscores()
        play("over")
        if self.new_best:
            for i, f in enumerate((523, 659, 784, 1047)):
                play(f"n{f}", 0.9 + i * 0.08)
        self.set_state("over")

    def update_paused(self, dt):
        if self.inp.back and self.state_t > 0.1:
            self.to_menu()
        elif (self.inp.pause or self.inp.any_hit("next") or self.inp.any_hit("other")) \
                and self.state_t > 0.1:
            # B resumes rather than leaving: it is also the in-game "other end"
            # button, so a stray press must not throw the round away.
            self.set_state("play")
            play("menu_ok")

    def update_over(self, dt):
        for v in self.views:
            v.update_fx(dt)
        leave = self.inp.any_hit("next") or self.inp.any_hit("other") or self.inp.confirm
        if self.inp.back or (self.state_t > 1.5 and leave):
            self.to_menu()

    def to_menu(self):
        self.set_state("title")
        self._make_demo()
        if MENU_ROWS[self.menu_row] == "quit":
            self.menu_row = 0  # a stray A must not quit the next visitor out
        play("back")

    # ------------------------------------------------------------ drawing
    def draw_title(self, S):
        t = self.t
        glow(S, W / 2, 84 * U, 260 * U, CYAN, 0.25)
        text(S, "SUPERCONDUCTOR", 44, WHITE, W / 2, 84 * U)
        text(S, "Route the two-qubit gates before they decohere", 10, GREY, W / 2, 132 * U)

        # Right: what the picked chip looks like while CHIP is picked, and
        # otherwise the legend, one thing on the chip at a time.
        row = MENU_ROWS[self.menu_row]
        if row == "chip":
            draw_board(S, self.demo, t)
        else:
            self.legend.draw(S, t, 478 * U)

        mx = 340 * U
        rows = [("MODE", MODE_LABEL[self.mode], MODE_DESC[self.mode]),
                ("CHIP", LATTICE_LABEL[self.lattice_kind], LATTICE_DESC[self.lattice_kind])]
        for i, (label, value, desc) in enumerate(rows):
            y = (245 + i * 105) * U
            sel = i == self.menu_row
            col = WHITE if sel else DIM
            text(S, label, 10, GREY if sel else DIM, mx, y - 26 * U)
            text(S, value, 20, col, mx, y + 4 * U)
            if sel and int(t * 3) % 2 == 0:
                text(S, "<", 20, GOLD, mx - 160 * U, y + 4 * U)
                text(S, ">", 20, GOLD, mx + 160 * U, y + 4 * U)
            text(S, desc, 8, GREY if sel else DIM, mx, y + 34 * U)
        # QUIT: back to the cabinet's game list (A; Start still plays)
        y = 440 * U
        sel = row == "quit"
        text(S, "QUIT", 20, WHITE if sel else DIM, mx, y)
        if sel:
            if int(t * 3) % 2 == 0:
                text(S, ">", 20, GOLD, mx - 80 * U, y)
                text(S, "<", 20, GOLD, mx + 80 * U, y)
            lines = self.hint_lines(lambda p: f"{self.name('a', p)}: back to the game list")
            for i, line in enumerate(lines):
                text(S, line, 8, GREY, mx, y + (30 + i * 14) * U)

        if self.mode != "versus":
            best = self.hiscores.get(self._hiscore_key(), 0)
            text(S, f"BEST {best:06d}", 10, GOLD, mx, 530 * U)
        if int(t * 2) % 2 == 0:
            text(S, f"PRESS {self.name('start')} TO PLAY", 14, WHITE, W / 2, 640 * U)
        lines = self.hint_lines(lambda p: f"{self.name('stick', p)}: CHOOSE    {self.name('a', p)}: OK    "
                                          f"{self.name('start', p)}: PLAY")
        for i, line in enumerate(lines):
            text(S, line, 8, DIM, W / 2, (690 - (len(lines) - 1 - i) * 14) * U)

    def draw_tutorial(self, S):
        """HOW TO PLAY: the goal, a scene playing it, the buttons, then go."""
        t = self.t
        glow(S, W / 2, 62 * U, 220 * U, CYAN, 0.22)
        text(S, "HOW TO PLAY", crisp(32), WHITE, W / 2, 62 * U)
        goal = ("Each pair of same-colour qubits is a gate to run.",
                "Join them with a route before the ring runs out.",
                "Two qubits that meet crash: both gates are lost.")
        for i, line in enumerate(goal):
            text(S, line, crisp(11), WHITE if i < 2 else mix(RED, WHITE, 0.35), W / 2, (118 + i * 24) * U)

        # left: the scenes, played by the game's own rules
        self.how_to.draw(S, t, 540 * U)

        # right: the stick and the printed 2x3 cluster, the used buttons lit
        x0 = 760 * U
        text(S, "CONTROLS", crisp(11), CYAN, x0, 226 * U, "left")
        players = (self.inp.devices.latest,) if self.mode == "single" else ("p1", "p2")
        if len(players) == 2 and not self.inp.devices.everyone_on(PAD):
            self.draw_controls_two(S, x0)
        else:
            self.draw_controls_one(S, x0, t)

        if self.state_t >= tutorial.MIN_SHOW and int(t * 2.5) % 2 == 0:
            any_button = "ANY KEY" if self.inp.devices.everyone_on(KEYBOARD) else "ANY BUTTON"
            text(S, f"PRESS {any_button} TO START", crisp(16), WHITE, W / 2, 668 * U)

    def draw_controls_one(self, S, x0, t):
        """The HOW TO PLAY controls for one player, or two on pads: the pad's
        stick and cluster (or, on the keyboard, its keys in the same places),
        then what each does."""
        cy = 276 * U
        who = self.inp.devices.latest if self.mode == "single" else None  # whose keys or pad to name
        bx = x0 + 110 * U
        if who is not None and self.inp.devices[who] == KEYBOARD:
            draw_keys(S, self.inp.devices, who, x0, cy - 4 * U, 30 * U, 34 * U)
        else:
            draw_stick(S, x0 + 24 * U, cy + 22 * U, t)
            for r, letters in enumerate(PAD_LAYOUT):
                for c, letter in enumerate(letters):
                    draw_button(S, bx + c * 44 * U, cy + r * 44 * U, letter, BUTTON_COL.get(letter))
        if self.mode != "single":
            both = "BOTH PADS" if self.inp.devices.everyone_on(PAD) else "BOTH PLAYERS"
            text(S, both, crisp(11), GREY, bx + 124 * U, cy + 22 * U, "left")
        on_keys = self.inp.devices.everyone_on(KEYBOARD) if who is None else self.inp.devices[who] == KEYBOARD
        y = 384 * U
        if on_keys:  # the keys by name, not the pad's buttons
            rows = [(self.name(names[0].lower(), who) if names[0] in ("STICK", "START")
                     else self.name("/".join(names).lower(), who), action) for names, action in PAD_ACTIONS]
            imgs = [font(round(crisp(11) * U)).render(f"{keys}:", True, GOLD) for keys, _ in rows]
            action_x = x0 + max(78 * U, max(img.get_width() for img in imgs) + 12 * U)
            for (keys, action), img in zip(rows, imgs):
                S.blit(img, img.get_rect(midleft=(int(x0), int(y))))
                text(S, action, crisp(11), WHITE, action_x, y, "left")
                y += 36 * U
        for names, action in () if on_keys else PAD_ACTIONS:
            draw_pad_names(S, names, x0, y)
            text(S, action, crisp(11), WHITE, x0 + 78 * U, y, "left")
            y += 36 * U

    def draw_controls_two(self, S, x0):
        """The HOW TO PLAY controls for two players when someone is on the
        keyboard: each player's keys (or pad) under their name, then a table
        with a column of keys or buttons per player."""
        heads = {p: f"{p.upper()} {'KEYS' if self.inp.devices[p] == KEYBOARD else 'PAD'}" for p in ("p1", "p2")}
        for i, p in enumerate(("p1", "p2")):
            gx = x0 + i * 176 * U
            text(S, heads[p], 8, GREY, gx, 258 * U, "left")
            if self.inp.devices[p] == KEYBOARD:
                draw_keys(S, self.inp.devices, p, gx, 272 * U, 22 * U, 25 * U)
            else:
                draw_stick(S, gx + 20 * U, 296 * U, self.t, 17 * U)
                for r, letters in enumerate(PAD_LAYOUT):
                    for c, letter in enumerate(letters):
                        draw_button(S, gx + (62 + c * 25) * U, (283 + r * 25) * U, letter,
                                    BUTTON_COL.get(letter), 11 * U)
        f = font(round(crisp(11) * U))
        x, y0 = x0, 384 * U
        for p in ("p1", "p2"):
            text(S, heads[p], 8, GREY, x, y0, "left")
            y = y0 + 32 * U
            if self.inp.devices[p] == KEYBOARD:
                keys = [self.name(names[0].lower() if names[0] in ("STICK", "START") else "/".join(names).lower(), p)
                        for names, _ in PAD_ACTIONS]
                for k in keys:
                    text(S, k, crisp(11), GOLD, x, y, "left")
                    y += 36 * U
                width = max(f.size(k)[0] for k in keys)
            else:
                for names, _ in PAD_ACTIONS:
                    draw_pad_names(S, names, x, y)
                    y += 36 * U
                width = 70 * U
            x += max(width, font(round(8 * U)).size(heads[p])[0]) + 18 * U
        y = y0 + 32 * U
        for _, action in PAD_ACTIONS:
            text(S, action, crisp(11), WHITE, x, y, "left")
            y += 36 * U

    def draw_play(self, S):
        t = self.t
        for v in self.views:
            draw_board(S, v, t)
            title = v.label or "SCORE"
            draw_board_hud(S, v, title, t)
            if v.board.over and len(self.views) > 1:
                rect = v.substrate_rect()
                veil(S, rect, 170)
                text(S, "DECOHERED", 20, RED, rect.centerx, rect.centery - 14 * U)
                text(S, "waiting for the other chip", 8, GREY, rect.centerx, rect.centery + 18 * U)
        if len(self.views) > 1:
            pygame.draw.line(S, SUBSTRATE_EDGE, (W / 2, 40 * U), (W / 2, H - 40 * U), px(1))
        who = self.inp.devices.latest if self.mode == "single" else None

        def hint(p):
            n = lambda k: self.name(k, p)  # noqa: E731
            return (f"{n('stick')}: ROUTE   {n('a/r')}: NEXT   {n('l')}: PREV   {n('b')}: OTHER END   "
                    f"{n('x')}: UNDO   {n('start')}: PAUSE")
        lines = [hint(who)] if who is not None else self.hint_lines(hint)
        # one line sits 14 up; two (a line per device) pack into the strip below the co-op chip
        bottom, step = (14, 14) if len(lines) == 1 else (10, 13)
        for i, line in enumerate(lines):
            text(S, line, 8, DIM, W / 2, H - (bottom + (len(lines) - 1 - i) * step) * U)

    def draw_paused(self, S):
        self.draw_play(S)
        veil(S, (0, 0, W, H), 170)
        text(S, "PAUSED", 32, WHITE, W / 2, H / 2 - 30 * U)
        p = self.inp.devices.latest  # one player works the menu
        n = lambda k: self.name(k, p)  # noqa: E731
        text(S, f"{n('start')} / {n('a')} / {n('b')}: RESUME     {n('select')}: MENU", 10, GREY, W / 2, H / 2 + 20 * U)

    def draw_over(self, S):
        self.draw_play(S)
        veil(S, (0, 0, W, H), 200)
        if self.mode == "versus":
            s1, s2 = (v.board.score for v in self.views)
            if s1 == s2:
                head, col = "DRAW", WHITE
            else:
                head, col = ("P1 WINS", WHITE) if s1 > s2 else ("P2 WINS", GOLD)
            text(S, head, 40, col, W / 2, 250 * U)
            text(S, f"P1  {s1:06d}", 16, WHITE, W / 2, 340 * U)
            text(S, f"P2  {s2:06d}", 16, GOLD, W / 2, 378 * U)
        else:
            b = self.views[0].board
            text(S, "CHIP DECOHERED", 36, RED, W / 2, 230 * U)
            text(S, f"SCORE {b.score:06d}", 18, WHITE, W / 2, 310 * U)
            mins, secs = divmod(int(b.time), 60)
            text(S, f"GATES {b.gates}    TIME {mins}:{secs:02d}", 10, GREY, W / 2, 350 * U)
            if self.new_best:
                text(S, "NEW BEST!", 16, GOLD, W / 2, 400 * U)
            else:
                text(S, f"BEST {self.hiscores.get(self._hiscore_key(), 0):06d}", 10, GOLD, W / 2, 400 * U)
        if self.state_t > 1.5 and int(self.state_t * 2.5) % 2:
            if self.inp.devices.everyone_on(PAD):
                text(S, f"PRESS {self.name('a')} OR {self.name('b')}", 12, WHITE, W / 2, 500 * U)
            else:  # keys: "B / V: CONTINUE", never "PRESS B"
                lines = self.hint_lines(lambda p: f"{self.name('a', p)} / {self.name('b', p)}: CONTINUE")
                for i, line in enumerate(lines):
                    text(S, line, 12, WHITE, W / 2, (500 + i * 24) * U)

    def draw_input_test(self, S):
        inp = self.inp
        text(S, "INPUT TEST", 20, WHITE, W / 2, 40 * U)
        text(S, "Press buttons / move sticks. ESC or hold SELECT 2s to leave.", 8, GREY, W / 2, 70 * U)
        y = 110 * U
        if not inp.joys:
            text(S, "No joysticks detected.", 10, RED, 40 * U, y, "left")
            y += 30 * U
        for i, j in inp.joys.items():
            slot = inp.pads.slot_of(j.get_instance_id())
            who = "-> P%d" % (slot + 1) if slot is not None else ""
            text(S, "JOY %d: %s %s" % (i, j.get_name()[:40], who), 10, CYAN, 40 * U, y, "left")
            y += 22 * U
            axes = "  ".join("a%d:%+.2f" % (k, j.get_axis(k)) for k in range(j.get_numaxes()))
            text(S, "axes " + axes, 8, WHITE, 60 * U, y, "left")
            y += 18 * U
            hats = "  ".join("h%d:%s" % (k, j.get_hat(k)) for k in range(j.get_numhats()))
            text(S, "hats " + (hats or "-"), 8, WHITE, 60 * U, y, "left")
            y += 18 * U
            btn = " ".join(str(k) for k in range(j.get_numbuttons()) if j.get_button(k))
            text(S, "buttons down: " + (btn or "-"), 8, WHITE, 60 * U, y, "left")
            y += 30 * U
        text(S, "last keys: " + (", ".join(inp.last_keys) or "-"), 10, GOLD, 40 * U, y + 10 * U, "left")
        if not keyboard_enabled():
            text(S, "(keyboard ignored: --no-keyboard)", 8, GREY, 40 * U, y + 30 * U, "left")
        for i, p in enumerate(("p1", "p2")):
            held = sorted(inp.prev_buttons[p]) + ([inp.dir[p]] if inp.dir[p] else [])
            text(S, "%s actions: %s" % (p.upper(), ", ".join(held) or "-"), 10, WHITE, 40 * U, y + (60 + i * 24) * U, "left")
        text(S, "Mapping lives in arqade_common/input.py (shared by all games)", 8, DIM, W / 2, H - 30 * U)

    # ------------------------------------------------------------ button names
    def name(self, control, player=None):
        """A control's on-screen name for one player's keys or pad, or for
        both players' when player is None (e.g. "SPACE / ENTER"). "stick" is
        the stick or the direction keys; "a/r" names both buttons."""
        if player is None:
            return " / ".join(dict.fromkeys(self.name(control, p) for p in ("p1", "p2")))
        if control == "stick":
            return KEYBOARD_STICKS[player] if self.inp.devices[player] == KEYBOARD else "STICK"
        return "/".join(self.inp.devices.label(b, player) for b in control.split("/"))

    def hint_lines(self, fmt):
        """A hint both players read: fmt(None) when they're on the same kind of
        device ("B / L: OK"); with one on keys and one on a pad, a line each,
        so a key letter never stands next to a button letter."""
        devices = self.inp.devices
        if devices.everyone_on(PAD) or devices.everyone_on(KEYBOARD):
            return [fmt(None)]
        return [f"{p.upper()} {'KEYS' if devices[p] == KEYBOARD else 'PAD'}  {fmt(p)}" for p in ("p1", "p2")]

    # ------------------------------------------------------------ loop
    def _note_playing(self):
        now = self.state in ("play", "paused")
        if now != self.playing:
            self.playing = now
            web.post_event(web.GAME_START if now else web.GAME_END, GAME_ID)

    async def _leave(self):
        """A player asked to quit: True ends the program. In the browser there
        is nothing to hand back to, so instead the game tells the page (which
        may take the player back to its game list) and returns to its title --
        once the quit buttons are let go, or the title would quit again at once."""
        if not runtime.is_browser():
            return True
        if self.state in ("play", "paused"):  # the match ends before the player leaves
            self.to_menu()
            self._note_playing()
        web.post_event(web.QUIT, GAME_ID)
        while self.inp.quit_combo or self.inp.back_held > 0:
            for e in pygame.event.get():
                self.inp.handle(e)
            self.inp.update(0.0)
            self.inp.end_frame()
            present(self.screen, self.window)
            pygame.display.flip()
            await asyncio.sleep(0)
        self.quit_requested = False
        self.to_menu()
        return False

    async def run(self, input_test=False):
        if input_test:
            self.set_state("inputtest")
        S = self.screen
        running = True
        while running:
            dt = min(0.05, self.clock.tick(config.FPS) / 1000.0)
            self.t += dt
            self.state_t += dt
            for e in pygame.event.get():
                if e.type == pygame.QUIT:
                    running = False
                elif e.type == pygame.KEYDOWN and e.key == pygame.K_F3:
                    self.show_fps = not self.show_fps
                self.inp.handle(e)
            self.inp.update(dt)
            if self.inp.quit_combo and self.state != "inputtest":
                if await self._leave():
                    break
                self.inp.end_frame()
                continue
            pump_sfx()

            S.fill(BG)
            if self.state == "title":
                if pygame.K_F1 in self.inp.ev_keys:
                    self.set_state("inputtest")
                elif self.inp.back_held > config.BACK_HOLD_TO_QUIT:
                    self.quit_requested = True
                else:
                    self.update_title(dt)
                if self.quit_requested:  # QUIT, or holding Select: the same clean exit as Start + Select
                    if await self._leave():
                        break
                    self.inp.end_frame()
                    continue
                if self.state == "title":
                    self.draw_title(S)
                elif self.state == "tutorial":
                    self.draw_tutorial(S)
            elif self.state == "tutorial":
                self.update_tutorial(dt)
                if self.state == "tutorial":
                    self.draw_tutorial(S)
                else:
                    self.draw_play(S)
            elif self.state == "play":
                self.update_play(dt)
                self.draw_play(S)
            elif self.state == "paused":
                self.update_paused(dt)
                if self.state == "paused":
                    self.draw_paused(S)
            elif self.state == "over":
                self.update_over(dt)
                if self.state == "over":
                    self.draw_over(S)
            elif self.state == "inputtest":
                self.draw_input_test(S)
                if pygame.K_ESCAPE in self.inp.ev_keys or self.inp.back_held > config.BACK_HOLD_TO_QUIT:
                    self.inp.back_held = 0.0
                    self.to_menu()

            if config.SHOW_SCANLINES:
                draw_scanlines(S)
            if self.show_fps:
                text(S, "%d FPS" % self.clock.get_fps(), 8, GOLD, 8 * U, H - 8 * U, "left", "bottom")
            present(S, self.window)
            pygame.display.flip()
            self.inp.end_frame()
            self._note_playing()
            await asyncio.sleep(0)  # hand the frame to the browser (pygbag); no-op elsewhere


async def run(*, fullscreen=False, window_size="1280x720", show_fps=False, input_test=False, pad_layout=None):
    await Game(fullscreen, window_size, show_fps, pad_layout).run(input_test)
