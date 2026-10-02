"""Pauli Invaders app icon: a flat 8-bit arcade screen, one red X invader.

The whole icon is drawn on a coarse 256x256 grid and blown up with
nearest-neighbour, so every edge -- invader, stars, lettering, shadows -- is
the same hard pixel: no gradients, no glows, nothing soft. The red X
invader fills the top half with its Pauli letter cut out in the background
colour and a hard drop-shadow; a sparse starfield of single pixels sits
behind it. Below it PAULI over INVADERS in Press Start 2P, red over blue as
on the game's title screen, each letter in flat colour bands (light top,
base, dark foot) with a solid pixel shadow like an old arcade marquee. The
marquee is the title on one line with a small invader in front.

Built from the game's own SPR, COL and BG (error_invaders.game); the letter
sits where enemy_sprite() puts it, at a whole number of grid pixels per
sprite pixel (the game uses 3.6 screen px).
"""

from __future__ import annotations

import random
import sys

import kit
import pygame

sys.path.insert(0, str(kit.ROOT / "error-invaders/src"))
from error_invaders import game as G  # noqa: E402

ROM = "error_invaders"

GRID = 256   # the icon's pixel grid; art() scales it up to the real size
BG = G.BG
COL = G.COL

# Flat colour bands per title colour, top to bottom, and the shadow colour.
BANDS = {
    "X": [(255, 170, 178), (255, 77, 94), (196, 36, 62)],
    "Z": [(160, 214, 255), (63, 169, 255), (30, 104, 206)],
}
SHADOW = {"X": (120, 18, 42), "Z": (16, 58, 132)}


def invader(col: str, px: int, frame: int = 0, color: tuple | None = None, letter: bool = True) -> pygame.Surface:
    """game.enemy_sprite() at `px` grid pixels per sprite pixel, with its
    Pauli letter (font(12) on a 3.6 px grid, centred 2 px above the 4th row)."""
    s = pygame.Surface((10 * px, 8 * px), pygame.SRCALPHA)
    for r, row in enumerate(G.SPR[frame]):
        for c, ch in enumerate(row):
            if ch == "#":
                s.fill(color or COL[col], (c * px, r * px, px, px))
    if letter:
        k = max(1, round(px * 12 / 3.6 / 8))
        glyph = kit.tint(kit.text_shape(col, kit.PIXEL_FONT, 8 * k), BG)
        s.blit(glyph, glyph.get_rect(center=(5 * px, round(4 * px - 2 * px / 3.6))))
    return s


def shadowed(fg: pygame.Surface, shadow: pygame.Surface, d: int) -> pygame.Surface:
    """`fg` over a solid copy of itself shifted `d` pixels down and right."""
    out = pygame.Surface((fg.get_width() + d, fg.get_height() + d), pygame.SRCALPHA)
    out.blit(shadow, (d, d))
    out.blit(fg, (0, 0))
    return out


def word(text: str, col: str, k: int, d: int) -> pygame.Surface:
    """Pixel-font text at k x 8 px in flat colour bands, with a hard shadow."""
    shape = kit.text_shape(text, kit.PIXEL_FONT, 8 * k)
    h = shape.get_height()
    paint = pygame.Surface(shape.get_size())
    light, base, dark = BANDS[col]
    paint.fill(base)
    paint.fill(light, (0, 0, shape.get_width(), 3 * k))       # top 3 font rows
    paint.fill(dark, (0, h - 2 * k, shape.get_width(), 2 * k))  # bottom 2 rows
    return shadowed(kit.tint(shape, paint), kit.tint(shape, SHADOW[col]), d)


def stars(S: pygame.Surface, keep_out: list[pygame.Rect]) -> None:
    """A sparse starfield of single grid pixels, a few brighter crosses."""
    rng = random.Random(3)
    w, h = S.get_size()
    placed = 0
    while placed < 46:
        x, y = rng.randrange(6, w - 6), rng.randrange(6, h - 6)
        if any(r.inflate(10, 10).collidepoint(x, y) for r in keep_out):
            continue
        placed += 1
        c = rng.choice([(70, 76, 110), (70, 76, 110), (120, 128, 170), (210, 214, 240)])
        S.set_at((x, y), c)
        if placed % 9 == 0:   # a twinkle
            for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                S.set_at((x + dx, y + dy), (90, 96, 140))


def art(size: int) -> pygame.Surface:
    S = pygame.Surface((GRID, GRID))
    S.fill(BG)
    hero = shadowed(invader("X", 12), invader("X", 12, color=SHADOW["X"], letter=False), 4)
    hero_r = hero.get_rect(center=(GRID // 2 + 2, 90))
    pauli = word("PAULI", "X", 4, 2)
    invaders = word("INVADERS", "Z", 3, 2)
    pauli_r = pauli.get_rect(midtop=(GRID // 2 + 1, 158))
    invaders_r = invaders.get_rect(midtop=(GRID // 2 + 1, pauli_r.bottom + 6))
    stars(S, [hero_r, pauli_r, invaders_r])
    S.blit(hero, hero_r)
    S.blit(pauli, pauli_r)
    S.blit(invaders, invaders_r)
    return pygame.transform.scale(S, (size, size))


def marquee() -> pygame.Surface:
    """The title on one line, a small invader in front, at 4 px per pixel."""
    icon = shadowed(invader("X", 3), invader("X", 3, color=SHADOW["X"], letter=False), 1)
    parts = [icon, word("PAULI", "X", 3, 2), word("INVADERS", "Z", 3, 2)]
    gaps = [10, 12]
    w = sum(p.get_width() for p in parts) + sum(gaps)
    h = max(p.get_height() for p in parts)
    out = pygame.Surface((w, h), pygame.SRCALPHA)
    x = 0
    for p, g in zip(parts, gaps + [0]):
        out.blit(p, (x, (h - p.get_height()) // 2))
        x += p.get_width() + g
    return kit.nearest(out, 4)
