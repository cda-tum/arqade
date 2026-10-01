"""Regenerate the per-game icons shown in EmulationStation's game list.

    python3 generate_icons.py            # writes all seven PNGs next to this file

Output names match the gamelist.xml <image> convention Batocera/ES expects
(`<rom-basename>-image.png`), so the results can be copied straight to
/userdata/roms/pygame/images/ on the cabinet -- see ../gamelist.xml and the
"Per-game icons" section of ../../AGENTS.md.

Self-contained on purpose: it only needs pygame, not any of the game
packages (each lives in its own uv project/venv, so importing all of them from
one script isn't possible). The few constants borrowed from a game's own
source are copied below and marked with where they came from, so a tweak
there is easy to mirror here.

The mathematical ket on the Qlimbers icon needs a font with both a Greek psi
and the U+27E9 bracket. TeX Gyre Pagella Math has both; most fonts have
neither (pygame's default font and the games' bundled Press Start 2P are
each missing the bracket, which is why in-game notation uses ASCII "|0>").
If that font is missing, the ket falls back to ASCII and a warning is shown.
"""

from __future__ import annotations

import math
import os
from pathlib import Path

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")

import pygame  # noqa: E402

SIZE = 512
OUT_DIR = Path(__file__).resolve().parent
MATH_FONT = Path(
    "/usr/share/texmf/fonts/opentype/public/tex-gyre-math/texgyrepagella-math.otf"
)


def shade(color: tuple[int, int, int], factor: float) -> tuple[int, int, int]:
    return tuple(max(0, min(255, round(c * factor))) for c in color)


# --- Qlimbers (quantum-towers) ----------------------------------------------
# Isometric block tower: stone body, one lit "target" block with a climber
# beside it, an overhanging roof, and a |psi> ket badge.


def qlimbers() -> pygame.Surface:
    surf = pygame.Surface((SIZE, SIZE))
    surf.fill((20, 22, 30))

    tile_w, tile_h, block_h = 140, 54, 62
    origin_x, origin_y = SIZE // 2 - 24, 392

    def iso(gx: float, gy: float, gz: float) -> tuple[float, float]:
        return (
            origin_x + (gx - gy) * (tile_w / 2),
            origin_y + (gx + gy) * (tile_h / 2) - gz * block_h,
        )

    def box(gx, gy, gz, sx, sy, sz, color):
        top = iso(gx, gy, gz + sz)
        right_t = iso(gx + sx, gy, gz + sz)
        front_t = iso(gx + sx, gy + sy, gz + sz)
        left_t = iso(gx, gy + sy, gz + sz)
        right_b = iso(gx + sx, gy, gz)
        front_b = iso(gx + sx, gy + sy, gz)
        left_b = iso(gx, gy + sy, gz)
        faces = [
            (shade(color, 0.72), [left_t, front_t, front_b, left_b]),
            (shade(color, 0.92), [right_t, front_t, front_b, right_b]),
            (shade(color, 1.18), [top, right_t, front_t, left_t]),
        ]
        for fill, poly in faces:
            pygame.draw.polygon(surf, fill, poly)
            pygame.draw.polygon(surf, shade(color, 0.5), poly, 1)

    stone, stone_dark = (128, 120, 110), (100, 94, 86)
    gold, climber_c, roof = (235, 175, 60), (70, 210, 220), (86, 78, 150)

    levels = 4
    gold_pos = (1, 0, 1)
    cells = [(x, y, z) for z in range(levels) for x in range(2) for y in range(2)]
    for gx, gy, gz in sorted(cells, key=lambda p: (p[2], p[0] + p[1])):
        color = gold if (gx, gy, gz) == gold_pos else (
            stone if (gx + gy + gz) % 2 == 0 else stone_dark
        )
        box(gx, gy, gz, 1, 1, 1, color)

    # Roof overhangs the walls -- flush with them reads as "too small".
    overhang = 0.22
    box(-overhang, -overhang, levels, 2 + 2 * overhang, 2 + 2 * overhang, 0.40, roof)
    band_top = levels + 0.40
    front_c = iso(2 + overhang, 2 + overhang, band_top)
    left_c = iso(-overhang, 2 + overhang, band_top)
    right_c = iso(2 + overhang, -overhang, band_top)
    apex = iso(1, 1, band_top + 1.7)
    pygame.draw.polygon(surf, shade(roof, 0.75), [left_c, front_c, apex])
    pygame.draw.polygon(surf, shade(roof, 0.95), [right_c, front_c, apex])
    for poly in ([left_c, front_c, apex], [right_c, front_c, apex]):
        pygame.draw.polygon(surf, shade(roof, 0.45), poly, 2)
    pygame.draw.line(surf, shade(roof, 1.35), front_c, apex, 2)

    gx, gy, gz = gold_pos
    wall_x, wall_y = iso(gx + 1, gy + 0.5, gz + 0.5)
    body_x, body_y = wall_x + 44, wall_y + 6

    def limb(p1, p2, width):
        pygame.draw.line(surf, climber_c, p1, p2, width)
        for p in (p1, p2):
            pygame.draw.circle(surf, climber_c, (round(p[0]), round(p[1])), width // 2)

    hip, shoulder = (body_x, body_y), (body_x - 6, body_y - 26)
    limb(hip, (body_x + 6, body_y + 34), 8)
    limb(hip, (wall_x, wall_y + 30), 8)
    limb(hip, shoulder, 10)
    limb(shoulder, (wall_x, wall_y - 28), 8)
    limb(shoulder, (wall_x, wall_y + 4), 8)
    pygame.draw.circle(surf, climber_c, (round(body_x - 10), round(body_y - 40)), 10)

    contact = pygame.Surface((26, 10), pygame.SRCALPHA)
    pygame.draw.ellipse(contact, (0, 0, 0, 80), contact.get_rect())
    surf.blit(contact, (wall_x - 13, wall_y + 34))

    if MATH_FONT.exists():
        font, ket = pygame.font.Font(str(MATH_FONT), 86), "|ψ⟩"
    else:
        print(f"WARNING: {MATH_FONT} missing -- ket falls back to ASCII")
        font, ket = pygame.font.Font(None, 80), "|ψ>"
    label = font.render(ket, True, (150, 235, 250))
    pos = (SIZE - label.get_width() - 36, 26)
    glow = pygame.Surface((label.get_width() + 46, label.get_height() + 26), pygame.SRCALPHA)
    pygame.draw.ellipse(glow, (110, 220, 235, 42), glow.get_rect())
    surf.blit(glow, (pos[0] - 23, pos[1] - 13))
    surf.blit(label, pos)
    return surf


# --- Quantum Pong -----------------------------------------------------------
# Classic paddle/ball silhouette plus the lettered gate power-up squares.


def quantum_pong() -> pygame.Surface:
    surf = pygame.Surface((SIZE, SIZE))
    surf.fill((8, 8, 16))

    for y in range(0, SIZE, 34):
        pygame.draw.rect(surf, (60, 60, 80), (SIZE // 2 - 2, y, 4, 18))
    pygame.draw.rect(surf, (235, 235, 245), (36, SIZE // 2 - 55, 16, 110), border_radius=6)
    pygame.draw.rect(surf, (235, 235, 245), (SIZE - 52, SIZE // 2 - 55, 16, 110), border_radius=6)
    # Two balls: the H gate's signature "split the ball in two".
    pygame.draw.circle(surf, (90, 200, 220), (SIZE // 2 - 14, SIZE // 2 + 40), 10)
    pygame.draw.circle(surf, (235, 235, 245), (SIZE // 2 + 14, SIZE // 2 - 20), 12)

    font = pygame.font.Font(None, 46)

    def gate(cx, cy, color, letter):
        rect = pygame.Rect(0, 0, 64, 64)
        rect.center = (cx, cy)
        pygame.draw.rect(surf, color, rect, border_radius=10)
        pygame.draw.rect(surf, (255, 255, 255), rect, width=3, border_radius=10)
        glyph = font.render(letter, True, (20, 20, 25))
        surf.blit(glyph, glyph.get_rect(center=rect.center))

    gate(150, 150, (197, 120, 235), "Z")
    gate(SIZE - 150, SIZE - 130, (235, 120, 130), "X")
    return surf


# --- Error Invaders ---------------------------------------------------------
# Sprite pattern and palette copied from error-invaders/src/error_invaders/game.py
# (SPR / COL / BG) so this script stays standalone.

_INVADER_ROWS = [
    "...####...",
    ".########.",
    "##########",
    "##########",
    "##########",
    ".########.",
    ".#.#..#.#.",
    "#..#..#..#",
]
_EI_BG = (5, 6, 13)
_EI_COL = {"X": (255, 77, 94), "Z": (63, 169, 255), "Y": (197, 107, 255)}


def error_invaders() -> pygame.Surface:
    surf = pygame.Surface((SIZE, SIZE))
    surf.fill(_EI_BG)

    px = 8  # chunky pixels so the sprites fill an icon-sized frame
    label_font = pygame.font.Font(None, 34)

    def invader(letter: str) -> pygame.Surface:
        w, h = len(_INVADER_ROWS[0]) * px, len(_INVADER_ROWS) * px
        spr = pygame.Surface((w, h), pygame.SRCALPHA)
        for r, row in enumerate(_INVADER_ROWS):
            for c, ch in enumerate(row):
                if ch == "#":
                    spr.fill(_EI_COL[letter], (c * px, r * px, px, px))
        glyph = label_font.render(letter, True, _EI_BG)
        spr.blit(glyph, glyph.get_rect(center=(w // 2, h // 2 - px)))
        return spr

    letters = ["X", "Y", "Z", "Y", "X"]
    spacing = SIZE // (len(letters) + 1)
    for i, letter in enumerate(letters):
        spr = invader(letter)
        surf.blit(spr, spr.get_rect(center=(spacing * (i + 1), 190)))

    # Player ship: a tri-color triangle, one face per Pauli color.
    size = 110
    cx, cy = SIZE // 2, SIZE - 140
    tri = [(cx, cy - size), (cx + size * 0.87, cy + size * 0.5), (cx - size * 0.87, cy + size * 0.5)]
    mid = lambda a, b: ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2)  # noqa: E731
    for letter, poly in (
        ("X", [tri[0], mid(tri[0], tri[1]), (cx, cy), mid(tri[2], tri[0])]),
        ("Z", [tri[1], mid(tri[1], tri[2]), (cx, cy), mid(tri[0], tri[1])]),
        ("Y", [tri[2], mid(tri[2], tri[0]), (cx, cy), mid(tri[1], tri[2])]),
    ):
        pygame.draw.polygon(surf, _EI_COL[letter], poly)
    pygame.draw.polygon(surf, (255, 255, 255), tri, 4)
    return surf


# --- Ion Surfer -------------------------------------------------------------
# Palette from ion-surfer/src/ion_surfer/game.py (BLUE) and config.py.


def ion_surfer() -> pygame.Surface:
    surf = pygame.Surface((SIZE, SIZE))
    blue = (78, 168, 255)
    top, bot = (10, 14, 30), shade(blue, 0.12)
    for y in range(SIZE):
        f = y / (SIZE - 1)
        pygame.draw.line(
            surf, tuple(round(top[i] + (bot[i] - top[i]) * f) for i in range(3)), (0, y), (SIZE, y)
        )

    for g in range(0, SIZE, 48):
        pygame.draw.line(surf, (30, 36, 58), (g, 0), (g, SIZE))
        pygame.draw.line(surf, (30, 36, 58), (0, g), (SIZE, g))

    def wave_y(x: float) -> float:
        return SIZE * 0.55 + math.sin(x / SIZE * 3.4 * math.pi) * 120

    points = [(x, wave_y(x)) for x in range(0, SIZE + 4, 4)]
    glow = pygame.Surface((SIZE, SIZE), pygame.SRCALPHA)
    pygame.draw.lines(glow, (*blue, 90), False, points, 14)
    pygame.draw.lines(glow, (*blue, 160), False, points, 6)
    pygame.draw.lines(glow, (220, 235, 255, 255), False, points, 2)
    surf.blit(glow, (0, 0))

    ion_x = SIZE * 0.62
    ion_y = wave_y(ion_x)
    halo = pygame.Surface((92, 92), pygame.SRCALPHA)
    for r in range(46, 0, -2):
        pygame.draw.circle(halo, (*blue, int(70 * (1 - r / 46) ** 2)), (46, 46), r)
    surf.blit(halo, (ion_x - 46, ion_y - 46))
    pygame.draw.circle(surf, (235, 245, 255), (int(ion_x), int(ion_y)), 12)
    return surf


# --- Ion Trap Sandbox (ion-surfer --sandbox) ---------------------------------
# A harmonic well with a wave packet coloured by its phase (as drawn in the
# sandbox), plus a squeezed phase-space ellipse orbiting the origin.


def ion_surfer_sandbox() -> pygame.Surface:
    surf = pygame.Surface((SIZE, SIZE))
    surf.fill((8, 12, 28))
    for g in range(0, SIZE, 48):
        pygame.draw.line(surf, (24, 32, 56), (g, 0), (g, SIZE))
        pygame.draw.line(surf, (24, 32, 56), (0, g), (SIZE, g))

    purple = (199, 155, 255)  # ion_surfer game.py COOP
    cx, floor = SIZE / 2, SIZE * 0.86

    def well(x: float) -> float:
        return floor - ((x - cx) / (SIZE * 0.5)) ** 2 * SIZE * 0.42

    curve = [(x, well(x)) for x in range(0, SIZE + 4, 4)]
    fill = pygame.Surface((SIZE, SIZE), pygame.SRCALPHA)
    pygame.draw.polygon(fill, (*purple, 60), curve + [(SIZE, SIZE), (0, SIZE)])
    surf.blit(fill, (0, 0))

    # wave packet: displaced gaussian with a phase gradient -> rainbow stripes
    x0, sigma, k = cx + 34, 38.0, 0.11
    top = []
    for x in range(int(x0 - 4 * sigma), int(x0 + 4 * sigma), 3):
        h = math.exp(-0.5 * ((x - x0) / sigma) ** 2) * 190
        y0 = well(x) - 3
        c = pygame.Color(0)
        c.hsva = (((x - x0) * k * 180 / math.pi) % 360, 55, 100, 100)
        if h > 1:
            pygame.draw.line(surf, c, (x, y0), (x, y0 - h), 4)
        top.append((x, y0 - h))
    pygame.draw.lines(surf, (250, 250, 255), False, top, 3)
    pygame.draw.lines(surf, purple, False, curve, 5)
    pygame.draw.lines(surf, (235, 225, 255), False, curve, 2)

    # phase-space inset: axes, vacuum circle, squeezed blob on its orbit
    ox, oy, r = SIZE * 0.24, SIZE * 0.24, 78
    pygame.draw.line(surf, (60, 74, 120), (ox - r, oy), (ox + r, oy), 2)
    pygame.draw.line(surf, (60, 74, 120), (ox, oy - r), (ox, oy + r), 2)
    pygame.draw.circle(surf, (90, 105, 160), (ox, oy), 46, 2)
    bx, by = ox + 32, oy - 32
    blob = pygame.Surface((SIZE, SIZE), pygame.SRCALPHA)
    cyan = (110, 220, 255)
    ang = math.radians(-45)
    for level, alpha in ((2.2, 50), (1.6, 90), (1.0, 150), (0.5, 220)):
        poly = []
        for j in range(40):
            t = j * math.tau / 40
            u, v = 26 * level * math.cos(t), 9 * level * math.sin(t)
            poly.append((bx + u * math.cos(ang) - v * math.sin(ang),
                         by + u * math.sin(ang) + v * math.cos(ang)))
        pygame.draw.polygon(blob, (*cyan, alpha), poly)
    surf.blit(blob, (0, 0))
    pygame.draw.line(surf, (255, 211, 107), (ox, oy), (bx, by), 3)
    pygame.draw.circle(surf, (255, 255, 255), (int(bx), int(by)), 5)
    return surf


# --- Superconductor ---------------------------------------------------------
# Colors from superconductor/src/superconductor/game.py (SUBSTRATE, COUPLER,
# QUBIT_IDLE, PAIR_COLORS). A 4x4 chip of Xmon crosses with two routed pairs.


def superconductor() -> pygame.Surface:
    surf = pygame.Surface((SIZE, SIZE))
    surf.fill((6, 8, 18))
    chip = pygame.Rect(36, 36, SIZE - 72, SIZE - 72)
    pygame.draw.rect(surf, (13, 17, 32), chip, 0, 28)
    pygame.draw.rect(surf, (40, 52, 84), chip, 5, 28)

    n, sp = 4, 112
    x0 = SIZE // 2 - sp * (n - 1) // 2

    def xy(r: int, c: int) -> tuple[int, int]:
        return x0 + c * sp, x0 + r * sp

    for r in range(n):
        for c in range(n):
            if c + 1 < n:
                pygame.draw.line(surf, (48, 62, 96), xy(r, c), xy(r, c + 1), 6)
            if r + 1 < n:
                pygame.draw.line(surf, (48, 62, 96), xy(r, c), xy(r + 1, c), 6)

    red, green = (255, 84, 104), (84, 226, 128)
    routes = {red: [(0, 0), (0, 1), (1, 1), (2, 1), (2, 2), (2, 3)],
              green: [(3, 0), (3, 1), (3, 2), (3, 3)]}
    on_route = {}
    for col, route in routes.items():
        for a, b in zip(route, route[1:]):
            pygame.draw.line(surf, shade(col, 0.45), xy(*a), xy(*b), 22)
            pygame.draw.line(surf, col, xy(*a), xy(*b), 9)
        for node in route:
            on_route[node] = (col, node in (route[0], route[-1]))

    def xmon(x: int, y: int, size: int, col: tuple[int, int, int]) -> None:
        arm, thick = size * 24 // 100, max(6, size * 9 // 100)
        pygame.draw.rect(surf, col, (x - arm, y - thick // 2, 2 * arm, thick), 0, 3)
        pygame.draw.rect(surf, col, (x - thick // 2, y - arm, thick, 2 * arm), 0, 3)

    for r in range(n):
        for c in range(n):
            x, y = xy(r, c)
            col, end = on_route.get((r, c), ((86, 104, 146), False))
            if end:
                pygame.draw.circle(surf, col, (x, y), 40, 6)
            xmon(x, y, 150 if end else 120, col if (r, c) in on_route else (86, 104, 146))

    # the travelling qubit, mid-route
    qx, qy = xy(1, 1)
    qy += sp // 2
    for rad, k in ((44, 0.15), (32, 0.3), (22, 0.6)):
        pygame.draw.circle(surf, shade(red, k), (qx, qy), rad)
    pygame.draw.circle(surf, (255, 200, 210), (qx, qy), 16)
    pygame.draw.circle(surf, (255, 255, 255), (qx, qy), 16, 4)
    return surf


# --- Overquqed (overquqed) -------------------------------------------------
# A Bloch Bowl wearing a chef's toque: glass sphere with the |+> arrow on the
# equator, on a kitchen-tile floor. Drawn at 64x64 and scaled by 8 (nearest)
# so it matches the game's chunky pixel art. Colours copied from
# overquqed/src/overquqed/palette.py.


def overquqed() -> pygame.Surface:
    ink = (28, 22, 40)
    floor_a, floor_b = (232, 214, 176), (214, 192, 150)
    teal = (40, 200, 190)
    green = (96, 214, 110)
    gold = (255, 206, 72)
    s = pygame.Surface((64, 64))
    for ty in range(0, 64, 8):
        for tx in range(0, 64, 8):
            s.fill(floor_a if (tx + ty) // 8 % 2 == 0 else floor_b, (tx, ty, 8, 8))
    # shadow + wooden stand
    pygame.draw.ellipse(s, shade(floor_b, 0.7), (16, 52, 32, 7))
    pygame.draw.rect(s, ink, (24, 48, 16, 6))
    pygame.draw.rect(s, (176, 124, 84), (25, 49, 14, 3))
    # the glass sphere
    c, r = (32, 34), 16
    pygame.draw.circle(s, (214, 238, 255), c, r)
    lower = pygame.Surface((64, 64), pygame.SRCALPHA)
    pygame.draw.circle(lower, (188, 210, 228, 255), c, r)
    s.blit(lower, (0, c[1]), pygame.Rect(0, c[1], 64, r + 1))
    pygame.draw.ellipse(s, (132, 150, 170), (c[0] - r + 1, c[1] - 6, 2 * r - 1, 13), 1)
    pygame.draw.circle(s, ink, c, r, 2)
    # |+> arrow: towards the viewer on the equator (down-left)
    tip = (c[0] - 8, c[1] + 6)
    pygame.draw.line(s, ink, (c[0], c[1] + 1), (tip[0], tip[1] + 1), 3)
    pygame.draw.line(s, green, c, tip, 3)
    s.fill((200, 250, 200), (tip[0] - 1, tip[1] - 1, 3, 3))
    for dx, dy in ((-9, -9), (-8, -9), (-9, -8)):
        s.set_at((c[0] + dx, c[1] + dy), (255, 255, 255))
    # chef's toque in the player-1 teal, perched on top
    pygame.draw.rect(s, ink, (20, 12, 24, 7))
    pygame.draw.rect(s, shade(teal, 0.45), (21, 13, 22, 5))
    for x0 in (18, 26, 34):
        pygame.draw.circle(s, ink, (x0 + 6, 9), 7)
    for x0 in (18, 26, 34):
        pygame.draw.circle(s, teal, (x0 + 6, 9), 6)
    pygame.draw.circle(s, (150, 240, 230), (23, 7), 2)
    pygame.draw.line(s, shade(teal, 0.72), (28, 5), (28, 12))
    pygame.draw.line(s, shade(teal, 0.72), (36, 5), (36, 12))
    # a gold entanglement sparkle
    for x, y in ((50, 20), (52, 18), (54, 20), (52, 22), (52, 20)):
        s.set_at((x, y), gold)
    return pygame.transform.scale(s, (SIZE, SIZE))


# --- Qurves (qurves) ------------------------------------------------------------
# A cyan light trail that forks into two mirrored, dashed ghost copies, an
# orange rival trail and an H gate, on the game's dark grid. Colours copied
# from qurves/src/qurves/config.py.


def qurves() -> pygame.Surface:
    cyan, orange, white = (40, 230, 255), (255, 140, 40), (235, 240, 255)
    surf = pygame.Surface((SIZE, SIZE))
    surf.fill((5, 6, 14))
    for i in range(0, SIZE + 1, 32):
        pygame.draw.line(surf, (17, 21, 42), (i, 0), (i, SIZE))
        pygame.draw.line(surf, (17, 21, 42), (0, i), (SIZE, i))

    def dashes(a, b, on=22, off=14):
        (ax, ay), (bx, by) = a, b
        length = math.hypot(bx - ax, by - ay)
        d = 0.0
        while d < length:
            e = min(length, d + on)
            yield ((ax + (bx - ax) * d / length, ay + (by - ay) * d / length),
                   (ax + (bx - ax) * e / length, ay + (by - ay) * e / length))
            d = e + off

    def neon(points, color, dashed=False, k=1.0):
        layer = pygame.Surface((SIZE, SIZE))
        layer.fill((0, 0, 0))
        for width, f in ((30, 0.16), (18, 0.38), (8, 1.0)):
            hue = tuple(round(c + (255 - c) * 0.55) for c in color) if f == 1.0 else color
            paint = shade(hue, f * k)
            for a, b in zip(points, points[1:]):
                for p, q in (dashes(a, b) if dashed else [(a, b)]):
                    pygame.draw.line(layer, paint, p, q, width)
                    pygame.draw.circle(layer, paint, p, width // 2)
                    pygame.draw.circle(layer, paint, q, width // 2)
        surf.blit(layer, (0, 0), special_flags=pygame.BLEND_MAX)

    def head(pos, color, k=1.0):
        glow = pygame.Surface((SIZE, SIZE))
        glow.fill((0, 0, 0))
        for r in range(34, 0, -1):
            f = (1 - r / 35) ** 1.1
            pygame.draw.circle(glow, shade(tuple(round(c + (255 - c) * 0.6 * f) for c in color), f * k), pos, r)
        pygame.draw.circle(glow, shade(tuple(round(c + (255 - c) * 0.85) for c in color), k), pos, 7)
        surf.blit(glow, (0, 0), special_flags=pygame.BLEND_ADD)

    fork = (210, 300)
    neon([(30, 300), fork], cyan)
    neon([fork, (210, 170), (380, 170), (380, 96)], cyan, dashed=True, k=0.75)
    neon([fork, (210, 430), (380, 430), (380, 470)], cyan, dashed=True, k=0.75)
    neon([(512, 250), (300, 250)], orange)
    head((380, 96), cyan, 0.8)
    head((380, 470), cyan, 0.8)
    head((300, 250), orange)
    # an H gate token
    box = pygame.Rect(0, 0, 70, 70)
    box.center = (110, 150)
    pygame.draw.rect(surf, white, box, 5, border_radius=12)
    pygame.draw.line(surf, white, (box.left + 20, box.top + 16), (box.left + 20, box.bottom - 17), 7)
    pygame.draw.line(surf, white, (box.right - 21, box.top + 16), (box.right - 21, box.bottom - 17), 7)
    pygame.draw.line(surf, white, (box.left + 20, box.centery), (box.right - 21, box.centery), 7)
    return surf


ICONS = {
    "quantum_towers-image.png": qlimbers,
    "quantum_pong-image.png": quantum_pong,
    "error_invaders-image.png": error_invaders,
    "ion_surfer-image.png": ion_surfer,
    "ion_surfer_sandbox-image.png": ion_surfer_sandbox,
    "superconductor-image.png": superconductor,
    "overquqed-image.png": overquqed,
    "qurves-image.png": qurves,
}


def main() -> None:
    pygame.init()
    pygame.font.init()
    for name, build in ICONS.items():
        pygame.image.save(build(), OUT_DIR / name)
        print(f"wrote {OUT_DIR / name}")


if __name__ == "__main__":
    main()
