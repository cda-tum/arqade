"""Regenerate the per-game icons shown in EmulationStation's game list.

    python3 generate_icons.py            # writes all five PNGs next to this file

Output names match the gamelist.xml <image> convention Batocera/ES expects
(`<rom-basename>-image.png`), so the results can be copied straight to
/userdata/roms/pygame/images/ on the cabinet -- see ../gamelist.xml and the
"Per-game icons" section of ../../AGENTS.md.

Self-contained on purpose: it only needs pygame, not any of the four game
packages (each lives in its own uv project/venv, so importing all four from
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


ICONS = {
    "quantum_towers-image.png": qlimbers,
    "quantum_pong-image.png": quantum_pong,
    "error_invaders-image.png": error_invaders,
    "ion_surfer-image.png": ion_surfer,
    "ion_surfer_sandbox-image.png": ion_surfer_sandbox,
}


def main() -> None:
    pygame.init()
    pygame.font.init()
    for name, build in ICONS.items():
        pygame.image.save(build(), OUT_DIR / name)
        print(f"wrote {OUT_DIR / name}")


if __name__ == "__main__":
    main()
