"""The racers and scenery props as voxel models. Pure (no pygame).

A model is a dict {(x, y, z): (r, g, b)}: x points forward, y to the
racer's right, z up, one unit per voxel. stacking.py draws them by sprite
stacking. Every racer is built from its own game's look: its sprites,
shapes and colours (see the logo notes in ../../../AGENTS.md), turned into
something that reads from above and drives.
"""

from __future__ import annotations

import math
import random

Color = tuple[int, int, int]
Model = dict[tuple[int, int, int], Color]

WHITE = (255, 255, 255)
INK = (10, 10, 24)
PAULI = {"X": (255, 77, 94), "Z": (63, 169, 255), "Y": (197, 107, 255)}  # Pauli Invaders' COL
INVADER_LEGS = ".#.#..#.#."  # the bottom row of Pauli Invaders' sprite


def shade(c: Color, k: float) -> Color:
    return tuple(max(0, min(255, int(v * k))) for v in c)


def mix(a: Color, b: Color, t: float) -> Color:
    return tuple(int(x + (y - x) * t) for x, y in zip(a, b))


def _sphere(vox: Model, cx: float, cy: float, cz: float, r2: float, dark: Color, lit: Color,
            glint: Color | None = None) -> None:
    span = int(math.ceil(math.sqrt(r2)))
    for x in range(int(cx) - span, int(cx) + span + 1):
        for y in range(int(cy) - span, int(cy) + span + 1):
            for z in range(max(0, int(cz) - span), int(cz) + span + 1):
                if (x - cx) ** 2 + (y - cy) ** 2 + (z - cz) ** 2 <= r2:
                    vox[(x, y, z)] = lit if (z - cz) + 0.5 * (x - cx) > 0.45 * math.sqrt(r2) else dark
    if glint:
        vox[(int(cx) + 1, int(cy) - 1, int(cz + math.sqrt(r2) * 0.8))] = glint


# --- the racers -------------------------------------------------------------------------

def chandelier() -> Model:
    """Superconductor: a little loco whose whole front is a dilution-fridge
    chandelier on its side: gold plates shrinking to a point, held by gold
    rods, wound with copper and silver coax, the chip at the very tip."""
    vox: Model = {}
    body, roof = (40, 52, 84), (90, 104, 146)  # the game's SUBSTRATE_EDGE and QUBIT_IDLE
    gold, rim, rod = (236, 178, 52), (255, 226, 128), (176, 122, 30)
    copper, silver = (214, 120, 70), (200, 204, 220)
    for x in range(-12, 2):
        for y in range(-4, 5):
            vox[(x, y, 1)] = (24, 28, 44)
    for wx in (-10, -6, -2):
        for y in (-5, 5):
            for dx in (0, 1):
                for z in (0, 1, 2):
                    vox[(wx + dx, y, z)] = (20, 20, 30)
            vox[(wx, y, 1)] = rod
    for x in range(-12, -5):
        for y in range(-4, 5):
            for z in range(2, 10):
                vox[(x, y, z)] = roof if z == 9 else body
    for x in (-10, -9, -8):
        for z in (6, 7):
            vox[(x, -4, z)] = vox[(x, 4, z)] = (90, 220, 255)  # the game's CYAN, as windows
    cz = 5.5
    plates = [(-4, 5.6), (-1, 4.9), (2, 4.1), (5, 3.3), (8, 2.5), (11, 1.6)]
    for px, r in plates:
        for y in range(-6, 7):
            for z in range(0, 12):
                d = math.hypot(y, z - cz)
                if d <= r:
                    vox[(px, y, z)] = rim if d > r - 1.1 else gold
    for (a, ra), (b, rb) in zip(plates, plates[1:]):
        for x in range(a + 1, b):
            r = (ra + (rb - ra) * (x - a) / (b - a)) * 0.85
            for k in range(3):
                ang = math.radians(90 + 120 * k)
                vox[(x, round(r * math.cos(ang)), round(cz + r * math.sin(ang)))] = rod
            for ang0, col in ((0.0, copper), (math.pi, silver)):
                ang = x * 1.1 + ang0
                vox[(x, round(1.6 * math.cos(ang)), round(cz + 1.6 * math.sin(ang)))] = col
    vox[(12, 0, 5)] = vox[(12, 0, 6)] = (40, 40, 56)
    vox[(13, 0, 5)] = (255, 84, 104)
    return vox


def ion() -> Model:
    """Ion Surfer: the ion, dark blue with a highlight, riding a green-blue
    swell that rises to a crest curling over behind it, spray off both
    sides and a few droplets in the air."""
    rng = random.Random(4)
    deep, mid, light, foam = (18, 128, 136), (34, 182, 166), (96, 224, 198), (238, 255, 250)
    vox: Model = {}
    for x in range(-9, 8):
        for y in range(-8, 9):
            if (x / 8.5) ** 2 + (y / 8.5) ** 2 > 1:
                continue
            crest = 7.0 * math.exp(-((x + 5) / (1.6 if x < -5 else 3.4)) ** 2)
            ripple = 0.6 * math.sin(y * 1.1 + x * 0.7)
            h = max(0, round(1 + crest * (1 - 0.35 * (y / 8.5) ** 2) + ripple))
            for z in range(h + 1):
                if z == h:
                    c = foam if h >= 6 else (light if (x + 2 * y) % 5 == 0 or h >= 4 else mid)
                else:
                    c = mid if z >= h - 1 else deep
                vox[(x, y, z)] = c
    for y in range(-6, 7):
        vox[(-3, y, 8)] = foam
        if abs(y) < 5:
            vox[(-2, y, 8)] = light
    for side in (-1, 1):
        for i in range(7):
            vox[(i - 2, side * (8 + i // 3), 2 + (i % 3))] = foam if i % 2 else light
    for _ in range(6):
        vox[(rng.randint(-7, -3), rng.randint(-6, 6), rng.randint(9, 11))] = foam
    _sphere(vox, 1, 0, 4, 11.5, (30, 44, 128), (62, 92, 188), (214, 228, 255))
    return vox


def jelly(kind: str = "X") -> Model:
    """Pauli Invaders: the invader as a jellyfish. A round, glossy bell in its
    Pauli colour, big eyes on top at the front, and its sprite's legs as
    tentacles streaming out behind, hovering over its shadow."""
    color = PAULI[kind]
    light, dark = mix(color, WHITE, 0.45), shade(color, 0.62)
    vox: Model = {}
    base = 5
    for x in range(-6, 7):
        for y in range(-6, 7):
            for z in range(base, base + 6):
                e = (x / 5.6) ** 2 + (y / 5.6) ** 2 + ((z - base) / 4.6) ** 2
                if e <= 1:
                    vox[(x, y, z)] = light if (z - base) + 0.5 * x > 3.5 else color
    for x in range(-6, 7):
        for y in range(-6, 7):
            if 4.8 <= math.hypot(x, y) <= 6.3 and (round(math.degrees(math.atan2(y, x))) // 30) % 2 == 0:
                vox[(x, y, base)] = dark
    for ey in (-2, 2):
        vox[(2, ey, base + 4)] = vox[(3, ey, base + 4)] = WHITE
        vox[(3, ey, base + 5)] = INK
    for i, ch in enumerate(INVADER_LEGS):
        if ch != "#":
            continue
        y0 = (i - 4.5) * 1.1
        for k in range(10):
            z = max(1, base - 1 - k // 3)
            vox[(-4 - k, round(y0 + 0.9 * math.sin(k * 0.9 + i)), z)] = light if k % 3 == 0 else color
    return vox


def colorcode() -> Model:
    """Pauli Invaders' P1 ship: the 3-colour colour-code triangle, flat, two
    voxels thick, hovering. The nose is the X face, the back corners Z
    (right) and Y (left), as in the game, with white qubits at the corners."""
    p = [(10.0, 0.0), (-6.0, 9.2), (-6.0, -9.2)]
    faces = ("X", "Z", "Y")
    vox: Model = {}
    (x0, y0), (x1, y1), (x2, y2) = p
    det = (y1 - y2) * (x0 - x2) + (x2 - x1) * (y0 - y2)
    for x in range(-7, 12):
        for y in range(-10, 11):
            a = ((y1 - y2) * (x - x2) + (x2 - x1) * (y - y2)) / det
            b = ((y2 - y0) * (x - x2) + (x0 - x2) * (y - y2)) / det
            w = (a, b, 1 - a - b)
            if min(w) < -0.02:
                continue
            c = PAULI[faces[max(range(3), key=lambda i: w[i])]]
            edge = min(w) < 0.07
            vox[(x, y, 2)] = shade(c, 0.7)
            vox[(x, y, 3)] = mix(c, WHITE, 0.5) if edge else c
    for qx, qy in p:
        sx = -1 if qx > 0 else 1
        sy = 0 if qy == 0 else (-1 if qy > 0 else 1)
        for z in (3, 4):
            vox[(round(qx) + sx, round(qy) + sy, z)] = WHITE
    return vox


def cycle() -> Model:
    """Qurves: a light cycle, dark with a glowing blue stripe and rims, and
    the start of its light trail behind it."""
    neon, dim = (60, 145, 255), (30, 70, 140)
    vox: Model = {}
    for x in range(-8, 9):
        for y in range(-2, 3):
            for z in range(1, 4):
                vox[(x, y, z)] = (22, 26, 44)
            vox[(x, y, 4 if -4 < x < 5 else 3)] = neon if abs(y) < 2 else dim
    for x in range(-4, 3):  # the rider's low hump
        for y in (-1, 0, 1):
            vox[(x, y, 5)] = (22, 26, 44) if x < 1 else neon
    for wx in (-7, 6):
        for dx in (-1, 0, 1):
            for y in range(-3, 4):
                for z in (0, 1, 2):
                    rim = abs(dx) == 1 or z != 1
                    vox[(wx + dx, y, z)] = neon if (rim and abs(y) == 3) else (14, 14, 24)
    for x in range(-18, -9):  # the trail: a thin glowing wall, fading
        fade = (x + 18) / 9
        for z in (1, 2, 3):
            vox[(x, 0, z)] = mix((10, 20, 50), neon, 0.3 + 0.7 * fade)
    return vox


def paddle() -> Model:
    """Quantum Pong: stark white on black. The two paddles are the runners
    of a sled, the ball rides between them up front, with its faded copies
    trailing behind as the game draws a moving ball."""
    white, dark = (236, 236, 236), (40, 40, 48)
    vox: Model = {}
    for x in range(-9, 10):
        for y in (-6, -5, 5, 6):
            for z in (0, 1, 2):
                vox[(x, y, z)] = white
    for x in (-6, 0, 6):  # struts joining the paddles
        for y in range(-4, 5):
            vox[(x, y, 1)] = dark
    for x in range(-3, 4, 2):  # a dashed midline along the middle
        vox[(x, 0, 2)] = (150, 150, 150)
    for x in (5, 6, 7):
        for y in (-1, 0, 1):
            for z in (2, 3, 4):
                vox[(x, y, z)] = white
    for i, x in enumerate((1, -3, -7)):
        g = 150 - 40 * i
        for y in (-1, 0, 1):
            vox[(x, y, 3)] = (g, g, g)
    return vox


def chef() -> Model:
    """Overquqed: P1's teal chef riding a steel kitchen trolley, a white hat
    on top and a Bloch Bowl at the front, with a gold sparkle."""
    teal, teal_d = (40, 190, 180), (24, 130, 124)
    steel, steel_d = (184, 190, 206), (120, 126, 146)
    skin, hat = (255, 206, 160), (250, 248, 244)
    vox: Model = {}
    for x in range(-7, 8):
        for y in range(-4, 5):
            vox[(x, y, 2)] = steel if abs(y) < 4 and -7 < x < 7 else steel_d
    for wx in (-6, 5):
        for y in (-4, 4):
            vox[(wx, y, 0)] = vox[(wx, y, 1)] = (30, 30, 40)
    for x in range(-6, -1):  # the chef: apron and jacket
        for y in range(-2, 3):
            for z in range(3, 8):
                vox[(x, y, z)] = teal if abs(y) < 2 else teal_d
    for y in (-3, 3):  # arms reaching for the handle
        for x in (-4, -3, -2):
            vox[(x, y, 6)] = teal
    for x in range(-5, -2):
        for y in (-1, 0, 1):
            for z in (8, 9):
                vox[(x, y, z)] = skin
    vox[(-2, -1, 9)] = vox[(-2, 1, 9)] = INK
    for x in range(-6, -1):
        for y in range(-2, 3):
            vox[(x, y, 10)] = hat
    for x in range(-5, -2):
        for y in (-1, 0, 1):
            for z in (11, 12):
                vox[(x, y, z)] = hat
    for x in range(1, 7):  # the Bloch Bowl
        for y in range(-3, 4):
            for z in (3, 4, 5):
                r = math.hypot(x - 3.5, y)
                if r <= 3.2 and (z == 3 or r >= 2.3):
                    vox[(x, y, z)] = (250, 248, 244) if z < 5 else (210, 214, 230)
    vox[(3, 0, 4)] = vox[(4, 0, 5)] = (255, 84, 104)  # its state arrow
    vox[(5, 2, 7)] = vox[(1, -2, 8)] = (255, 210, 60)  # sparkle
    return vox


def rook() -> Model:
    """Qlimbers: a stone tower on wheels: warm grey stone with darker trim,
    the gold target band near the top, crenellations on the roof, and P1's
    cyan climber hanging on its side."""
    stone, trim, gold = (128, 120, 110), (90, 84, 76), (235, 175, 60)
    vox: Model = {}
    for x in range(-5, 6):
        for y in range(-5, 6):
            edge = abs(x) == 5 or abs(y) == 5
            for z in range(1, 11):
                if z == 8:
                    vox[(x, y, z)] = gold
                elif z in (4, 7) and edge:
                    vox[(x, y, z)] = trim
                else:
                    vox[(x, y, z)] = stone
            if edge and ((x + y) % 4 in (0, 1)):
                vox[(x, y, 11)] = vox[(x, y, 12)] = stone
    for y in (-1, 0, 1):  # a window in the band facing forward
        vox[(5, y, 9)] = (40, 30, 30)
        vox[(5, y, 5)] = (40, 30, 30)
    for wx in (-4, 4):
        for wy in (-6, 6):
            vox[(wx, wy, 0)] = vox[(wx, wy, 1)] = (30, 30, 36)
    climber = (0, 190, 210)
    for z in (5, 6, 7):
        vox[(0, 6, z)] = climber
    vox[(1, 6, 8)] = vox[(-1, 6, 8)] = climber  # arms reaching up
    vox[(0, 6, 8)] = (255, 220, 190)
    return vox


def photon() -> Model:
    """Qlinko: a gold photon, glowing, with its wave packet rippling out
    behind it."""
    gold, glow = (255, 196, 70), (255, 236, 170)
    vox: Model = {}
    _sphere(vox, 2, 0, 4, 10.5, (230, 150, 40), gold, (255, 255, 230))
    for x in range(-14, -1):
        amp = 3.0 * math.exp(-((x + 7) / 4.5) ** 2)
        y = round(amp * math.sin(x * 1.3))
        c = mix((120, 70, 20), glow, 0.35 + 0.65 * (x + 14) / 13)
        vox[(x, y, 4)] = c
        vox[(x, y, 3)] = shade(c, 0.7)
    for x in (-4, 0, 4):  # a beam splitter plate it rides over
        for y in range(-5, 6):
            vox[(x, y, 0)] = (80, 88, 140)
    return vox


def _capsule(vox: Model, a: tuple, b: tuple, r: float, color: Color) -> None:
    """A thick limb from joint a to joint b, as Brawl-Ket draws its puppets'
    capsules. A voxel (x, y, z) has its centre at (x, y, z + 0.5)."""
    lo = [math.floor(min(p, q) - r) for p, q in zip(a, b)]
    hi = [math.ceil(max(p, q) + r) for p, q in zip(a, b)]
    d = [q - p for p, q in zip(a, b)]
    dd = sum(v * v for v in d) or 1.0
    for x in range(lo[0], hi[0] + 1):
        for y in range(lo[1], hi[1] + 1):
            for z in range(max(0, lo[2] - 1), hi[2] + 1):
                p = (x - a[0], y - a[1], z + 0.5 - a[2])
                t = max(0.0, min(1.0, sum(u * v for u, v in zip(p, d)) / dd))
                if sum((u - t * v) ** 2 for u, v in zip(p, d)) <= r * r:
                    vox[(x, y, z)] = color


# Brawl-Ket's ROBERT: a lean puppet in the colour of its basis (green, the Z
# basis it starts a round in), its accent cream (render.py's GREEN and ACCENT).
ROBERT_BODY, ROBERT_ACCENT = (72, 200, 96), (248, 232, 192)
SPARK = (248, 200, 48)  # Brawl-Ket's GOLD


def robert() -> Model:
    """Brawl-Ket: ROBERT, the lean green puppet, grinding the wire like
    Sonic on a rail. He stands side on, facing his right, feet apart along
    the wire (front foot ahead, back foot behind), knees bent, leaning into
    the run with his arms out for balance. Back limbs a darker green, a pale
    stripe down the torso, a shine on the round head, and his cream visor
    and fists, looking ahead."""
    body = ROBERT_BODY
    dark, pale = shade(body, 0.65), mix(body, WHITE, 0.4)
    cream, cream_d = ROBERT_ACCENT, shade(ROBERT_ACCENT, 0.8)
    vox: Model = {}
    hip, chest = (0.0, 0.4, 4.4), (1.4, 0.6, 7.8)
    knee_f, knee_b = (3.4, 1.8, 3.9), (-2.8, 1.8, 3.7)
    foot_f, foot_b = (5.6, 0.0, 0.6), (-5.6, 0.0, 0.6)
    # the back leg, then the back arm: the darker shade, as Brawl-Ket's far limbs
    _capsule(vox, hip, knee_b, 1.1, dark)
    _capsule(vox, knee_b, foot_b, 1.05, dark)
    _capsule(vox, foot_b, (foot_b[0] - 1.6, 0.0, 0.6), 0.8, dark)
    _capsule(vox, chest, (-2.4, 0.2, 8.4), 1.0, dark)
    _capsule(vox, (-2.4, 0.2, 8.4), (-5.6, 0.0, 9.4), 1.0, dark)
    _sphere(vox, -6.6, 0.0, 9.4, 2.6, cream_d, cream_d)
    # the front leg: thigh forward, the knee bent over the front foot
    _capsule(vox, hip, knee_f, 1.1, body)
    _capsule(vox, knee_f, foot_f, 1.05, body)
    _capsule(vox, foot_f, (foot_f[0] + 1.6, 0.0, 0.6), 0.8, body)
    # the torso, leaning into the run, with its pale stripe down the front
    _capsule(vox, hip, chest, 1.55, body)
    _capsule(vox, (0.3, 1.9, 5.0), (1.5, 2.1, 7.6), 0.5, pale)
    # the front arm reaching ahead, a little low
    _capsule(vox, chest, (5.0, 0.8, 8.6), 1.0, body)
    _capsule(vox, (5.0, 0.8, 8.6), (8.2, 0.8, 8.0), 1.0, body)
    _sphere(vox, 9.2, 0.8, 8.0, 2.6, cream, cream)
    # the round head, ahead of the chest on a short neck: a shine at the
    # back, and the visor across the face, looking ahead past the front
    # shoulder
    hx, hy, hz, r2 = 3.4, 0.6, 11.0, 6.3
    _capsule(vox, chest, (hx, hy, hz - 1.0), 0.8, body)
    _sphere(vox, hx, hy, hz, r2, body, body)
    r = math.sqrt(r2)
    for (x, y, z) in [k for k in vox if k[2] == 11]:
        if (x - hx) * 0.55 + (y - hy) * 0.84 > r - 1.2 and (x - hx) ** 2 + (y - hy) ** 2 + (z - hz) ** 2 <= r2:
            vox[(x, y, z)] = cream
    vox[(2, -1, 13)] = vox[(2, 0, 13)] = pale
    # grind sparks off the back foot, where he scrapes along the wire
    for x, y, z, c in ((-8, 0, 0, SPARK), (-9, -1, 1, WHITE), (-10, 1, 0, SPARK), (-11, 0, 2, SPARK)):
        vox[(x, y, z)] = c
    return vox


# Racers with no car under them, standing on the wire: the renderer leans
# them into corners and lets them sway (config.RIDER_*).
RIDERS = frozenset({"robert"})

RACERS = {
    "chandelier": chandelier,
    "ion": ion,
    "jelly": jelly,
    "colorcode": colorcode,
    "cycle": cycle,
    "paddle": paddle,
    "chef": chef,
    "rook": rook,
    "photon": photon,
    "robert": robert,
}


# --- scenery props -------------------------------------------------------------------------

def xmon(color: Color = (86, 104, 146)) -> Model:
    """Superconductor's Xmon qubit: a raised plus, one voxel high."""
    vox: Model = {}
    for i in range(-4, 5):
        for w in (-1, 0, 1):
            vox[(i, w, 0)] = vox[(w, i, 0)] = color
            vox[(i, w, 1)] = vox[(w, i, 1)] = mix(color, WHITE, 0.2)
    return vox


def invader_ship(kind: str) -> Model:
    """A small hovering jellyfish invader, for the space scene's formation."""
    return jelly(kind)
