"""SERVE! (from Overquqed): a guest comes to the pass and orders a state,
|1> or |+>. You are the chef, carrying a fresh Bloch bowl, |0>. On the back
counter stand two of Overquqed's appliances: the Pauli-X Flipper (a pan on a
stove) and the Hadamard Blender. Walk to the right one and press A, then
walk to the pass and press A to serve.

Exactly one appliance makes the order: X|0> = |1> and H|0> = |+>. Using the
wrong one gives a wrong state, which only fails once it is served, and
using the same appliance again undoes it (X X = H H = I), as in Overquqed.
States are compared up to a global phase, as Overquqed's fidelity does.

The guest walks in first, so nothing counts for the first 0.6 s at level 0.
Doing nothing never serves, so it runs out the clock.
"""

from __future__ import annotations

import math
from functools import lru_cache

import pygame

from planck_time import palette as P
from planck_time.microgames.base import IDLE, H, W, Microgame, PlayerInput, register
from planck_time.pixel import blit_center, outlined, result_overlay


def q(c) -> tuple[int, int, int]:
    """An Overquqed colour snapped onto the GBA's 15-bit grid."""
    return tuple(min(248, round(v / 8) * 8) for v in c)


def mix(a, b, t: float) -> tuple[int, int, int]:
    return q(tuple(x + (y - x) * t for x, y in zip(a, b)))


# --- the qubit ---------------------------------------------------------------------------

R2 = 1 / math.sqrt(2)
GATES = {"X": lambda s: (s[1], s[0]), "H": lambda s: (R2 * (s[0] + s[1]), R2 * (s[0] - s[1]))}
APPLIANCES = {"X": "FLIPPER", "H": "BLENDER"}
KETS = {"0": (1, 0), "1": (0, 1), "+": (R2, R2), "-": (R2, -R2)}
ORDERS = ("1", "+")
ZERO = KETS["0"]
# a gate turns the bowl's arrow by pi about its axis, as Overquqed animates it
AXES = {"X": (1.0, 0.0, 0.0), "H": (R2, 0.0, R2)}


def same(a, b) -> bool:
    """The same state up to a global phase (fidelity 1)."""
    return abs(abs(a[0] * b[0] + a[1] * b[1]) - 1) < 1e-6


def name(s) -> str:
    return next(k for k, v in KETS.items() if same(s, v))


def bloch(s) -> tuple[float, float, float]:
    a0, a1 = s
    c = a0 * a1
    return 2 * c, 0.0, a0 * a0 - a1 * a1


def rotate(v, axis, angle: float):
    """Rodrigues: v turned by `angle` about the unit `axis`."""
    (x, y, z), (kx, ky, kz) = v, axis
    c, s = math.cos(angle), math.sin(angle)
    dot = kx * x + ky * y + kz * z
    cross = (ky * z - kz * y, kz * x - kx * z, kx * y - ky * x)
    return tuple(vi * c + ci * s + ki * dot * (1 - c) for vi, ci, ki in zip(v, cross, (kx, ky, kz)))


# --- tuning ------------------------------------------------------------------------------

READY = 0.6  # the guest walks in to the pass (at level 0); input counts after that
WALK = 105.0  # chef px per second at level 0...
WALK_PER_LEVEL = 0.05  # ...and this much faster per level (the clock shrinks faster)
REACH = 14  # px either side of an appliance the chef can use it from
SLOTS = (36, 84, 156, 204)  # appliance centres along the back counter
PASS_X = 120
GATE_ANIM = 0.3
THINK = 0.25  # the bot looks before it walks...
BOT_SETTLE = 0.12  # ...and pauses before each press

# --- the kitchen, in Overquqed's colours ----------------------------------------------------

INK = q((28, 22, 40))
KET_COLOR = {"0": q((86, 156, 255)), "1": q((255, 110, 64)), "+": q((96, 214, 110)), "-": q((186, 116, 255))}
GOLD = q((255, 206, 72))
FLOOR_A, FLOOR_B = q((232, 214, 176)), q((214, 192, 150))
WALL, WALL_TOP = q((92, 72, 100)), q((130, 104, 138))
SPLASH = q((176, 214, 206))
BRICK = q((150, 70, 64))
COUNTER, COUNTER_TOP = q((186, 122, 76)), q((226, 170, 110))
DINING_A, DINING_B = q((120, 70, 60)), q((104, 60, 52))
PASS_TOP, PASS_FRONT = q((210, 214, 222)), q((200, 60, 60))
GLASS = q((214, 238, 255))
GATE_BOX = {"X": KET_COLOR["1"], "H": KET_COLOR["+"]}  # circuit.GATE_COLORS

COUNTER_Y, COUNTER_H = 18, 26  # the back counter: top 16 px, then its front
FLOOR_TOP, FLOOR_BOTTOM = 44, 104
WALL_Y = 104  # the low service wall, with the pass in it
DINING_Y = 120
FEET_MIN, FEET_MAX = 56, 102  # the chef's feet stay on the floor
NEAR_COUNTER = 64  # feet at or above this can use an appliance...
NEAR_PASS = 92  # ...and at or below this, the pass
PASS_REACH = 22
GUEST_FEET = 146

# --- Overquqed's sprites (sprites.py), one char per pixel -----------------------------------

CHEF = [  # facing down: hat, head, body
    "....ooo..ooo....",
    "...oWWWooHHHo...",
    "..oWWHHHHHHHHo..",
    ".oWWHHHhHHhHHho.",
    ".oWHHHHhHHhHHho.",
    "..ohhhhhhhhhho..",
    "...obbbbbbbbo...",
    "..okssssssssko..",
    "..osseesseesso..",
    "..osseesseesso..",
    "..osrsssssssro..",
    "...oossssssoo...",
    "...occccccccco..",
    ".oocaacccccaacoo",
    ".oscaaaaaaaacso.",
    ".ooaaaaaaaaaaoo.",
    "..oaaaaaaaaaao..",
]
LEGS = [
    ["..oppppppppppo..", "...oppo..oppo...", "...oppo..oppo...", "...offo..offo...", "...oooo..oooo..."],
    ["..oppppppppppo..", "...oppo..oppo...", "...offo..oppo...", "...oooo..offo...", "..........oooo.."],
    ["..oppppppppppo..", "...oppo..oppo...", "...oppo..offo...", "...offo..oooo...", "..oooo.........."],
]
# a neutral chef: Overquqed's hats are the players' colours, so this one is
# white with Chef Ket's gold band
CHEF_COLORS = {
    "o": INK, "H": (248, 248, 248), "h": (200, 200, 216), "W": (248, 248, 248), "b": GOLD,
    "s": q((255, 206, 160)), "r": q((246, 140, 130)), "e": INK, "k": q((110, 66, 44)),
    "c": q((250, 248, 244)), "a": q((204, 208, 222)), "p": q((60, 56, 84)), "f": q((40, 30, 34)),
}
GUEST = [
    ".....oooooo.....",
    "....okkkkkko....",
    "...okkkkkkkko...",
    "...okssssssko...",
    "...osseesseso...",
    "...osseesseso...",
    "...osrssssrso...",
    "....ossssssoo...",
    "...oJJJJJJJJo...",
    "..oJJjJJJJjJJo..",
    "..osJJJJJJJJso..",
    "..ooJJJJJJJJoo..",
    "...oJJJJJJJJo...",
    "...oLLLLLLLLo...",
    "...oLLo..oLLo...",
    "...oLLo..oLLo...",
    "...offo..offo...",
    "...oooo..oooo...",
]
GUEST_STEP = ["...oLLo..oLLo...", "...offo..oLLo...", "...oooo..offo...", "..........oooo.."]
# (skin, hair, jumper, jumper detail, legs), from sprites._GUEST_LOOKS
LOOKS = {
    "surface": ((255, 206, 160), (40, 40, 60), (90, 150, 250), (250, 250, 255), (60, 60, 90)),
    "grover": ((255, 214, 170), (150, 90, 40), (60, 150, 90), (120, 200, 140), (70, 60, 50)),
    "dj": ((200, 150, 110), (30, 30, 30), (220, 120, 60), (250, 190, 110), (60, 50, 60)),
    "shor": ((255, 214, 190), (240, 150, 60), (200, 70, 80), (250, 140, 140), (70, 50, 60)),
}
HEART = [".oo.oo.", "oRRoRRo", "oRRRRRo", ".oRRRo.", "..oRo..", "...o..."]
ANGRY = ["o.o.o", ".ooo.", "ooRoo", ".ooo.", "o.o.o"]
BANG = [".ooooo.", "oWWRWWo", "oWWRWWo", "oWWRWWo", "oWWWWWo", "oWWRWWo", ".ooooo.", "...oo..", "...o..."]


def grid(rows: list[str], cmap: dict) -> pygame.Surface:
    surf = pygame.Surface((max(len(r) for r in rows), len(rows)), pygame.SRCALPHA)
    for y, row in enumerate(rows):
        for x, ch in enumerate(row):
            if ch not in ". ":
                surf.set_at((x, y), cmap[ch])
    return surf


@lru_cache(maxsize=None)
def chef(frame: int) -> pygame.Surface:
    return grid(CHEF + LEGS[frame], CHEF_COLORS)


@lru_cache(maxsize=None)
def guest(key: str, stepping: bool) -> pygame.Surface:
    skin, hair, jumper, detail, legs = (q(c) for c in LOOKS[key])
    cmap = {"o": INK, "k": hair, "s": skin, "e": INK, "r": mix(skin, (240, 110, 110), 0.5),
            "J": jumper, "j": detail, "L": legs, "f": q((40, 30, 34))}
    surf = grid(GUEST, cmap)
    if stepping:
        surf.fill((0, 0, 0, 0), (3, 14, 10, 4))
        surf.blit(grid(GUEST_STEP, cmap), (0, 14))
    if key == "surface":  # a checkerboard jumper: a surface-code lattice
        for y in range(8, 13):
            for x in range(3, 13):
                if surf.get_at((x, y))[:3] == jumper and (x + y) % 2:
                    surf.set_at((x, y), q((250, 250, 255)))
    elif key == "grover":  # a magnifying glass
        pygame.draw.circle(surf, INK, (14, 8), 3)
        pygame.draw.circle(surf, q((170, 220, 255)), (14, 8), 2)
        pygame.draw.line(surf, INK, (13, 11), (12, 13))
    elif key == "dj":  # the two-faced coin badge
        pygame.draw.circle(surf, INK, (8, 10), 3)
        surf.fill(q((255, 210, 70)), (6, 9, 2, 3))
        surf.fill(q((200, 205, 215)), (8, 9, 2, 3))
    elif key == "shor":  # cat ears
        for x0 in (3, 10):
            pygame.draw.polygon(surf, INK, [(x0, 3), (x0 + 1, -1), (x0 + 3, 2)])
    return surf


ICONS = {  # sprites.heart(), angry() and bubble_bang()
    "heart": (HEART, {"o": INK, "R": q((250, 80, 110))}),
    "angry": (ANGRY, {"o": q((230, 50, 50)), "R": q((255, 200, 60))}),
    "bang": (BANG, {"o": INK, "W": (248, 248, 248), "R": q((230, 50, 60))}),
}


@lru_cache(maxsize=None)
def icon(kind: str) -> pygame.Surface:
    rows, cmap = ICONS[kind]
    return grid(rows, cmap)


_BG: dict = {}


def kitchen() -> pygame.Surface:
    """The static kitchen, drawn once: Overquqed's back wall and backsplash, the
    counter, the tiled floor, the brick service wall and the dining room."""
    if "bg" in _BG:
        return _BG["bg"]
    s = pygame.Surface((W, H))
    s.fill(WALL, (0, 0, W, 6))
    s.fill(WALL_TOP, (0, 4, W, 2))
    s.fill(SPLASH, (0, 6, W, COUNTER_Y - 6))
    for x in range(6, W, 12):
        s.fill(P.shade(SPLASH, 0.85), (x, 6, 1, COUNTER_Y - 6))
    s.fill(P.shade(SPLASH, 0.85), (0, 12, W, 1))
    # the back counter
    s.fill(COUNTER_TOP, (0, COUNTER_Y, W, 16))
    s.fill(mix(COUNTER_TOP, (255, 255, 255), 0.25), (0, COUNTER_Y, W, 1))
    for x in range(0, W, 24):
        s.fill(P.shade(COUNTER_TOP, 0.92), (x + 2, COUNTER_Y + 5, 9, 1))
        s.fill(P.shade(COUNTER_TOP, 0.92), (x + 14, COUNTER_Y + 11, 8, 1))
        s.fill(P.shade(COUNTER, 0.75), (x, COUNTER_Y + 17, 1, COUNTER_H - 17))
    s.fill(INK, (0, COUNTER_Y + 16, W, 1))
    s.fill(COUNTER, (0, COUNTER_Y + 17, W, COUNTER_H - 17))
    s.fill(P.shade(COUNTER, 0.75), (0, FLOOR_TOP - 1, W, 1))
    # the floor
    tile = 20
    for ty in range(FLOOR_TOP, WALL_Y, tile):
        for tx in range(0, W, tile):
            base = FLOOR_A if (tx // tile + ty // tile) % 2 == 0 else FLOOR_B
            s.fill(base, (tx, ty, tile, min(tile, WALL_Y - ty)))
            s.fill(P.shade(base, 0.93), (tx, ty, tile, 1))
            s.fill(P.shade(base, 0.93), (tx, ty, 1, min(tile, WALL_Y - ty)))
    # the low service wall towards the dining room
    s.fill(WALL_TOP, (0, WALL_Y, W, 6))
    s.fill(mix(WALL_TOP, (255, 255, 255), 0.2), (0, WALL_Y, W, 1))
    s.fill(INK, (0, WALL_Y + 6, W, 1))
    s.fill(BRICK, (0, WALL_Y + 7, W, DINING_Y - WALL_Y - 7))
    for row, gy in enumerate(range(WALL_Y + 7, DINING_Y, 5)):
        s.fill(P.shade(BRICK, 0.78), (0, gy, W, 1))
        for gx in range(0 if row % 2 else 6, W, 12):
            s.fill(P.shade(BRICK, 0.78), (gx, gy, 1, 5))
    s.fill(INK, (0, DINING_Y - 1, W, 1))
    # the pass: a steel top, a striped red front and the bell
    top = pygame.Rect(PASS_X - 24, WALL_Y - 4, 48, 12)
    s.fill(INK, top.inflate(2, 2))
    s.fill(PASS_TOP, top)
    s.fill(mix(PASS_TOP, (255, 255, 255), 0.25), (top.x, top.y, top.w, 1))
    front = pygame.Rect(top.x, top.bottom, top.w, DINING_Y - 1 - top.bottom)
    s.fill(PASS_FRONT, front)
    for gx in range(front.x, front.right, 6):
        s.fill(q((250, 240, 230)), (gx, front.y + 2, 3, front.h - 3))
    bx, by = PASS_X + 12, top.y + 6
    pygame.draw.circle(s, INK, (bx, by - 2), 4)
    pygame.draw.circle(s, GOLD, (bx, by - 2), 3)
    s.fill(INK, (bx - 4, by + 1, 9, 2))
    s.set_at((bx - 1, by - 4), (248, 248, 232))
    # the dining room
    for ty in range(DINING_Y, H, 20):
        for tx in range(0, W, 20):
            s.fill(DINING_A if (tx // 20 + ty // 20) % 2 == 0 else DINING_B, (tx, ty, 20, 20))
    _BG["bg"] = s
    return s


def gate_box(surf: pygame.Surface, gate: str, cx: int, cy: int, box: int = 13) -> None:
    """Overquqed's circuit gate box: ink, the gate's colour, a white face and the letter."""
    r = pygame.Rect(cx - box // 2, cy - box // 2, box, box)
    pygame.draw.rect(surf, INK, r)
    pygame.draw.rect(surf, GATE_BOX[gate], r.inflate(-2, -2))
    pygame.draw.rect(surf, (248, 248, 248), r.inflate(-4, -4))
    blit_center(surf, outlined(gate, 8, INK, outline=(248, 248, 248), shadow=False), (cx + 1, cy + 1))


def project(v, r: float) -> tuple[float, float]:
    """Overquqed's view of the Bloch sphere: |0> up, |1> down, |+> down-left."""
    x, y, z = v
    return r * (0.92 * y - 0.5 * x), r * (0.42 * x - 0.92 * z)


def arrow_color(v):
    x, _, z = v
    if z > 0.55:
        return KET_COLOR["0"]
    if z < -0.55:
        return KET_COLOR["1"]
    if x > 0.55:
        return KET_COLOR["+"]
    if x < -0.55:
        return KET_COLOR["-"]
    return q((140, 140, 150))


def bowl(surf: pygame.Surface, cx: int, cy: int, v, r: int = 8) -> None:
    """A Bloch bowl: a glass sphere on a little stand, its arrow in the state's colour."""
    pygame.draw.rect(surf, INK, (cx - 4, cy + r, 9, 4))
    pygame.draw.rect(surf, q((176, 124, 84)), (cx - 3, cy + r, 7, 2))
    pygame.draw.circle(surf, GLASS, (cx, cy), r)
    lower = pygame.Rect(cx - r, cy, 2 * r + 1, r + 1)
    surf.set_clip(lower)
    pygame.draw.circle(surf, P.shade(GLASS, 0.88), (cx, cy), r)
    surf.set_clip(None)
    eq = pygame.Rect(cx - r, cy - round(r * 0.42), 2 * r + 1, round(r * 0.84) + 1)
    pygame.draw.ellipse(surf, P.shade(GLASS, 0.62), eq, 1)
    pygame.draw.circle(surf, INK, (cx, cy), r, 1)
    dx, dy = project(v, r - 1)
    tip = (round(cx + dx), round(cy + dy))
    col = arrow_color(v)
    pygame.draw.line(surf, INK, (cx, cy + 1), (tip[0], tip[1] + 1), 2)
    pygame.draw.line(surf, col, (cx, cy), tip, 2)
    surf.fill(mix(col, (255, 255, 255), 0.5), (tip[0] - 1, tip[1] - 1, 2, 2))
    surf.fill((248, 248, 248), (cx - r // 2, cy - r // 2 - 1, 2, 1))


def ket_label(k: str, size: int = 8) -> pygame.Surface:
    return outlined(f"|{k}>", size, KET_COLOR[k], shadow=False)


def ease(p: float) -> float:
    p = min(1.0, max(0.0, p))
    return p * p * (3 - 2 * p)


@register
class Serve(Microgame):
    VERB = "SERVE!"
    INPUT = "stick+a"
    CAPTION = "Kitchen appliances are gates"

    def __init__(self, seed: int, level: int, duration: float) -> None:
        super().__init__(seed, level, duration)
        self.order = self.rng.choice(ORDERS)
        self.right = "X" if self.order == "1" else "H"
        slots = self.rng.sample(SLOTS, 2)
        self.stations = dict(zip(self.rng.sample(("X", "H"), 2), slots))  # gate -> x
        self.x = float(self.rng.uniform(100, 140))
        self.y = 80.0
        self.facing = 1
        self.walked = 0.0
        self.moving = False
        self.state = ZERO
        self.anim: tuple[str, float, tuple] | None = None  # (gate, when, arrow before)
        self.used: tuple[str, float] | None = None  # the appliance last used, for its flash
        self.served = False
        self.pressed_at = -9.0
        self.guest = self.rng.choice(tuple(LOOKS))
        self.ready = READY / self.speed
        self.walk = WALK * (1 + WALK_PER_LEVEL * level)

    # --- the rules -----------------------------------------------------------------------

    def at_station(self) -> str | None:
        if self.y > NEAR_COUNTER:
            return None
        return next((g for g, x in self.stations.items() if abs(self.x - x) <= REACH), None)

    @property
    def at_pass(self) -> bool:
        return self.y >= NEAR_PASS and abs(self.x - PASS_X) <= PASS_REACH

    def step(self, dt: float, inp: PlayerInput) -> None:
        if self.t < self.ready:
            return
        sx, sy = inp.stick
        self.moving = bool(sx or sy)
        if self.moving:
            self.x = max(10.0, min(W - 10.0, self.x + sx * self.walk * dt))
            self.y = max(FEET_MIN, min(FEET_MAX, self.y + sy * self.walk * dt))
            self.walked += math.hypot(sx, sy) * dt
            if abs(sx) > 0.3:
                self.facing = 1 if sx > 0 else -1
        if not inp.a:
            return
        self.pressed_at = self.t
        gate = self.at_station()
        if gate is not None:
            self.anim = (gate, self.t, self.arrow())
            self.state = GATES[gate](self.state)
            self.used = (gate, self.t)
        elif self.at_pass:
            self.served = True
            if same(self.state, KETS[self.order]):
                self.win()
            else:
                self.fail()

    def bot(self) -> PlayerInput:
        if self.t < self.ready + THINK:
            return IDLE
        cooked = same(self.state, KETS[self.order])
        if cooked:
            goal, there = (PASS_X, FEET_MAX), self.at_pass
        else:
            goal, there = (self.stations[self.right], FEET_MIN), self.at_station() == self.right
        if there:
            return PlayerInput(a=True, a_held=True) if self.t - self.pressed_at > BOT_SETTLE else IDLE
        dx, dy = goal[0] - self.x, goal[1] - self.y
        d = math.hypot(dx, dy)
        k = min(1.0, d / 6) / d
        return PlayerInput(stick=(dx * k, dy * k))

    # --- drawing -------------------------------------------------------------------------

    def arrow(self):
        """The bowl's arrow, mid-swing if an appliance just turned it."""
        if self.anim is not None and self.t - self.anim[1] < GATE_ANIM:
            gate, when, before = self.anim
            return rotate(before, AXES[gate], math.pi * ease((self.t - when) / GATE_ANIM))
        return bloch(self.state)

    def draw(self, surf: pygame.Surface) -> None:
        surf.blit(kitchen(), (0, 0))
        for gate, x in self.stations.items():
            self._appliance(surf, gate, x)
        self._guest(surf)
        self._chef(surf)
        gate = self.at_station() if self.result is None else None
        if gate is not None or (self.result is None and self.at_pass):
            hx, hy = (self.stations[gate] + 17, COUNTER_Y + 4) if gate else (PASS_X + 31, WALL_Y + 2)
            pygame.draw.circle(surf, INK, (hx, hy), 6)  # Overquqed's button hint
            pygame.draw.circle(surf, P.GOLD, (hx, hy), 5)
            blit_center(surf, outlined("A", 8, INK, outline=P.GOLD, shadow=False), (hx + 1, hy + 1))
        if self.result is None and same(self.state, ZERO):
            hint = "A AT THE RIGHT APPLIANCE"
        elif self.result is None:
            hint = "SERVE IT: A AT THE PASS"
        else:
            hint = "SERVED!" if self.result else ("WRONG ORDER!" if self.served else "TOO SLOW!")
        blit_center(surf, outlined(hint, 8, P.WHITE), (W // 2, H - 7))
        result_overlay(surf, self.result, self.since_end, seed=13)

    def _appliance(self, surf: pygame.Surface, gate: str, x: int) -> None:
        px, py = x - 12, COUNTER_Y
        if gate == "X":  # the Flipper: a stove with a flip pan
            pygame.draw.rect(surf, INK, (px + 2, py + 1, 20, 14))
            pygame.draw.rect(surf, q((70, 70, 84)), (px + 3, py + 2, 18, 12))
            pygame.draw.circle(surf, INK, (px + 11, py + 8), 6)
            pygame.draw.circle(surf, q((230, 90, 40)), (px + 11, py + 8), 6, 1)
            pygame.draw.circle(surf, q((60, 64, 76)), (px + 11, py + 8), 4)
            pygame.draw.line(surf, INK, (px + 17, py + 8), (px + 23, py + 5), 3)
            pygame.draw.line(surf, q((150, 100, 70)), (px + 17, py + 8), (px + 22, py + 5), 1)
        else:  # the Blender: a green base and its glass jar
            jar = pygame.Rect(px + 5, py - 10, 14, 16)
            pygame.draw.rect(surf, q((200, 230, 240)), jar)
            pygame.draw.rect(surf, INK, jar, 1)
            surf.fill((248, 248, 248), (jar.x + 2, jar.y + 2, 1, 6))
            pygame.draw.rect(surf, INK, (px + 6, jar.y - 2, 12, 3))
            pygame.draw.rect(surf, INK, (px + 4, py + 6, 16, 9))
            pygame.draw.rect(surf, q((80, 170, 110)), (px + 5, py + 7, 14, 7))
            surf.fill((248, 248, 248), (px + 7, py + 10, 2, 1))
            surf.fill(q((255, 90, 80)), (px + 15, py + 10, 2, 1))
        gate_box(surf, gate, x, py + 21)  # the gate on the counter's front, as in Overquqed
        if self.used and self.used[0] == gate and self.t - self.used[1] < 0.9:
            age = self.t - self.used[1]  # the gate floats up off the appliance
            cy = py - 2 - round(age * 12)
            pygame.draw.line(surf, (248, 248, 248), (x - 12, cy), (x + 12, cy))
            gate_box(surf, gate, x, cy)

    def _chef(self, surf: pygame.Surface) -> None:
        x, y = round(self.x), round(self.y)
        frame = 1 + int(self.walked * 8) % 2 if self.moving and self.result is None else 0
        pygame.draw.ellipse(surf, P.shade(FLOOR_B, 0.7), (x - 7, y - 3, 14, 5))
        img = chef(frame)
        if self.facing < 0:
            img = pygame.transform.flip(img, True, False)
        surf.blit(img, (x - 8, y - 22))
        # carried overhead, as in Overquqed, until it is put on the pass
        bx, by = (PASS_X - 4, WALL_Y - 12) if self.served else (x + 2 * self.facing, y - 31)
        bowl(surf, bx, by, self.arrow())
        label = ket_label(name(self.state))
        surf.blit(label, label.get_rect(midbottom=(bx, by - 9)))

    def _guest(self, surf: pygame.Surface) -> None:
        arrive = ease(self.t / self.ready) if self.ready else 1.0
        x = round(-12 + (PASS_X - 4 + 12) * arrive)
        walking = arrive < 1
        hop = 0
        if self.result is True and self.since_end < 0.6:
            hop = -2 if int(self.since_end * 10) % 2 else 0
        img = guest(self.guest, walking and int(self.t * 8) % 2 == 1)
        pygame.draw.ellipse(surf, q((70, 40, 34)), (x - 6, GUEST_FEET - 3, 12, 4))
        surf.blit(img, (x - 8, GUEST_FEET - 18 + hop))
        top = GUEST_FEET - 18
        if self.result is True and self.since_end < 1.2:
            surf.blit(icon("heart"), (x - 3, top - 8 - round(self.since_end * 10)))
        elif self.result is False:
            surf.blit(icon("angry"), (x + 4, top - 4))
        elif not walking and self.t - self.ready < 0.5:
            surf.blit(icon("bang"), (x - 3, top - 10))
        if not walking:  # the order, in a speech bubble
            b = pygame.Rect(x + 12, GUEST_FEET - 28, 44, 22)
            pygame.draw.rect(surf, INK, b)
            pygame.draw.rect(surf, (248, 248, 248), b.inflate(-2, -2))
            pygame.draw.polygon(surf, INK, [(b.x, b.bottom - 9), (b.x - 6, b.bottom - 3), (b.x, b.bottom - 4)])
            pygame.draw.polygon(surf, (248, 248, 248), [(b.x + 1, b.bottom - 8), (b.x - 3, b.bottom - 4), (b.x + 1, b.bottom - 5)])
            blit_center(surf, ket_label(self.order, 16), (b.centerx + 1, b.centery + 1))
