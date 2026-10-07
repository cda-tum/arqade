"""Gate Drop app icon: a toy-box sunburst, one gate pill about to land on its bug.

The look is an SNES puzzle-game box: a two-tone sunburst behind one big
glossy pill, and the title in chunky letters, each a different candy colour,
bouncing along the line, everything with a hard ink drop shadow. The hero is
the game's central move, Dr. Mario style: an H-X gate pill drops straight
down, its red X half leading, onto a grumpy red X error bug -- a gate a
moment from landing on its own inverse and cancelling. The sunburst radiates
from the gap between them, where a soft light is already building, and two
speed lines down each side trail the pill.

Everything is the game's own: the pill halves and the bug are
sprites.Sprites().gate() and .bug(), joined the way render.Renderer._board
joins a pill's halves, at native size and upscaled by one whole-number
factor. The rays are round 3's tile pair from config.BACKGROUNDS (the teal
the background turns to in the third round), and the speed lines are its
tile-centre dot colour (render.make_background). The title follows the
game's own logo (render.make_logo): each letter drawn by render.outlined in
the H, X, Y and Z gate colours in turn, with a bounce, but built at the
font's native 8 px with one pixel more spacing and a one-pixel bounce, so it
stays legible when it is scaled up whole. The marquee is that title with the
pill-and-bug as a small emblem in front.
"""

from __future__ import annotations

import math
import sys

import kit
import pygame

sys.path.insert(0, str(kit.ROOT / "gate-drop/src"))

from gate_drop import config, render  # noqa: E402
from gate_drop.fonts import load_font  # noqa: E402
from gate_drop.sprites import INK, Sprites, lighten  # noqa: E402

ROM = "gate_drop"

CELL = config.CELL  # 16: one board cell, the size of every sprite
DARK, LIGHT = config.BACKGROUNDS[2]  # round 3's teal tile pair
DOT = lighten(LIGHT, 0.25)  # the tile-centre dot colour (render.make_background)
TITLE_COLORS = [config.GATE_COLORS[k] for k in ("H", "X", "Y", "Z")]  # as make_logo cycles them

K = 12  # hero: one game pixel is K x K icon pixels (at 1024)
TK = 10  # title: one font pixel is TK x TK
GAP = 4  # game px between the falling pill and the bug: just short of landing
RAYS = 16
# Speed lines trailing the pill, two down each side: (x, top, length) in game
# px, relative to the pill's top-left corner (the pill spans x 0..15).
SPEED = ((-3, -4, 14), (-6, 2, 7), (18, -8, 15), (21, 1, 8))


def hero(gap: int = GAP) -> pygame.Surface:
    """The H-X pill standing on its X end, `gap` px above an X bug, at the
    game's own size (16 px wide), with the same one-pixel ink drop shadow
    render.outlined gives the title's letters."""
    sp = Sprites()
    s = pygame.Surface((CELL, 3 * CELL + gap), pygame.SRCALPHA)
    s.blit(sp.gate("H", "d"), (0, 0))  # joint "d": its partner is below
    s.blit(sp.gate("X", "u"), (0, CELL))
    s.blit(sp.bug("X", 0), (0, 2 * CELL + gap))
    out = pygame.Surface((CELL + 1, 3 * CELL + gap + 1), pygame.SRCALPHA)
    out.blit(kit.tint(s, INK), (1, 1))
    out.blit(s, (0, 0))
    return out


def title(step: int = 9, bounce: int = 1) -> pygame.Surface:
    """GATE DROP the way render.make_logo builds it, at the font's native
    8 px: every letter outlined in ink by render.outlined, in the gate
    colours in turn, every other one dropped by `bounce`."""
    font = load_font(8)
    out = pygame.Surface((step * 9 + 8, 16), pygame.SRCALPHA)
    i = 0
    for k, ch in enumerate("GATE DROP"):
        if ch == " ":
            continue
        out.blit(render.outlined(font, ch, TITLE_COLORS[i % len(TITLE_COLORS)]), (k * step, (k % 2) * bounce))
        i += 1
    return kit.trim(out)


def sunburst(size: int, center: tuple[float, float]) -> pygame.Surface:
    """Two-tone rays from `center`, drawn at twice the size and smoothscaled
    down so their edges are clean."""
    ss = 2 * size
    big = pygame.Surface((ss, ss))
    big.fill(DARK)
    cx, cy = center[0] * 2, center[1] * 2
    r = ss * 2
    for i in range(RAYS):
        a0 = (i - 0.25) / RAYS * 2 * math.pi - math.pi / 2  # a light ray straight up and down
        a1 = (i + 0.25) / RAYS * 2 * math.pi - math.pi / 2
        pygame.draw.polygon(big, LIGHT, [(cx, cy), (cx + r * math.cos(a0), cy + r * math.sin(a0)),
                                         (cx + r * math.cos(a1), cy + r * math.sin(a1))])
    return pygame.transform.smoothscale(big, (size, size))


def art(size: int) -> pygame.Surface:
    S = 1024
    figure = kit.nearest(hero(), K)
    word = kit.nearest(title(), TK)
    top = 112
    x = (S - CELL * K) // 2  # the sprites themselves centred, not their shadow
    impact = (S / 2, top + (2 * CELL + GAP / 2) * K)  # the middle of the gap

    surf = sunburst(S, impact)
    surf.blit(kit.radial((S, S), impact, 380, kit.shade(LIGHT, 0.9), 0.7), (0, 0),
              special_flags=pygame.BLEND_ADD)
    surf = kit.finish(surf, vignette_strength=0.55)
    for dx, dy, n in SPEED:
        surf.fill(DOT, (x + dx * K, top + dy * K, K, n * K))
    surf.blit(figure, (x, top))
    kit.blit_center(surf, word, (S / 2, top + figure.get_height() + 64 + word.get_height() / 2))
    return surf if size == S else pygame.transform.smoothscale(surf, (size, size))


def marquee() -> pygame.Surface:
    """The title on transparency, with the pill-and-bug as a small emblem in front."""
    word = kit.nearest(title(), 16)
    emblem = kit.nearest(hero(), 4)
    gap = 40
    h = max(word.get_height(), emblem.get_height())
    out = pygame.Surface((emblem.get_width() + gap + word.get_width(), h), pygame.SRCALPHA)
    out.blit(emblem, (0, (h - emblem.get_height()) // 2))
    out.blit(word, (emblem.get_width() + gap, (h - word.get_height()) // 2))
    return kit.trim(out)
