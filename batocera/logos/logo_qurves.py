"""Qurves: one light trail meeting an H gate and splitting in two, as an icon.

The hero is the game's central move, seen flat on as in the game: P1's blue
trail rises from below into an H gate and forks into two mirrored, dashed
ghost copies -- a symmetric fork glyph -- and P2's red trail cuts across just
ahead of the right-hand copy, which crashes into it in a burst of sparks.
Every piece of it is the game's own pre-rendered art (the Renderer's trail
and ghost stamps, its H gate token and head glows, Fx's crash burst), drawn
at the game's own pixel size and scaled up nearest-neighbour. Behind it is
the arena's background colour; the stem rises off the horizon of a synthwave
floor (the arena's grid in perspective), and QURVES stands on that floor as a
neon sign -- hollow tubes, QUR in P1's blue and VES in P2's red.
"""

from __future__ import annotations

import random
import sys

import kit
import pygame

sys.path.insert(0, str(kit.ROOT / "qurves/src"))
from qurves import config, render  # noqa: E402
from qurves.fx import Fx  # noqa: E402

ROM = "qurves"
BLUE, RED = config.PLAYER_COLORS["p1"], config.PLAYER_COLORS["p2"]
CELL = config.CELL
UP, LEFT, RIGHT = (0, -1), (-1, 0), (1, 0)
ZOOM = 5  # game px -> icon px


def _path(start, *moves):
    """Cells along a trail: from `start`, (direction, length) per leg."""
    cells = [start]
    for (dx, dy), n in moves:
        for _ in range(n):
            x, y = cells[-1]
            cells.append((x + dx, y + dy))
    return cells


# Grid cells of the fork. At the H the bike turns left and its mirrored twin
# right (rules._split); then both steer up again, mirroring each other.
FORK = (80, 46)
STEM = _path((80, 53), (UP, 7))
COPIES = [_path(FORK, (LEFT, 7), (UP, 7)), _path(FORK, (RIGHT, 7), (UP, 7))]
# P2 cuts across just ahead of the right-hand copy, which crashes into the
# red wall; the left copy lives on, so P1 still has a bike.
RED_RUN = _path((97, 38), (LEFT, 15))


def to_alpha(surf: pygame.Surface) -> pygame.Surface:
    """Light on black -> the same light on transparency (alpha = brightness).
    Per pixel, which is fine at the game's own resolution."""
    w, h = surf.get_size()
    out = pygame.Surface((w, h), pygame.SRCALPHA)
    for y in range(h):
        for x in range(w):
            r, g, b, _ = surf.get_at((x, y))
            a = max(r, g, b)
            if a:
                out.set_at((x, y), (r * 255 // a, g * 255 // a, b * 255 // a, a))
    return out


def faded(r: render.Renderer, player: str, cells, tail: tuple[int, int]) -> pygame.Surface:
    """A solid trail on black, fading out towards its first cell, so it seems
    to come in from off the icon. `tail` is the screen direction of that end."""
    s = pygame.Surface((render.W, render.H))
    s.fill((0, 0, 0))
    for a, b in zip(cells, cells[1:]):
        r._stamp(s, r.solid_stamps[player], a, b, pygame.BLEND_MAX)
    (x0, y0), (x1, y1) = render.cell_px(cells[0]), render.cell_px(cells[-1])
    fade = pygame.Surface((render.W, render.H))
    fade.fill((255, 255, 255))
    g = render.GLOW_R
    if tail == (0, 1):  # fades downwards
        fade.blit(kit.gradient((render.W, y0 - y1 + g), [(255, 255, 255), (0, 0, 0)]), (0, y1))
        fade.fill((0, 0, 0), (0, y0 + g, render.W, render.H))
    else:  # fades to the right
        fade.blit(kit.gradient((x0 - x1 + g, render.H), [(255, 255, 255), (0, 0, 0)], vertical=False), (x1, 0))
        fade.fill((0, 0, 0), (x0 + g, 0, render.W, render.H))
    s.blit(fade, (0, 0), special_flags=pygame.BLEND_MULT)
    return s


def hero() -> pygame.Surface:
    """The duel at game resolution, on transparency, cropped symmetrically
    about the H so the fork stays centred."""
    r = render.Renderer(pygame.Surface((render.W, render.H)))
    s = pygame.Surface((render.W, render.H))
    s.fill((0, 0, 0))
    s.blit(faded(r, "p1", STEM, (0, 1)), (0, 0), special_flags=pygame.BLEND_MAX)
    s.blit(faded(r, "p2", RED_RUN, (1, 0)), (0, 0), special_flags=pygame.BLEND_MAX)
    # the two copies: dashed ghost trails, like Renderer._apply draws them
    ghost = pygame.Surface((render.W, render.H), pygame.SRCALPHA)
    for cells in COPIES:
        for a, b in zip(cells, cells[1:]):
            if (b[0] + b[1]) % 2 == 0:
                r._stamp(ghost, r.ghost_stamps["p1"], a, b, pygame.BLEND_RGBA_MAX)
    s.blit(ghost, (0, 0))
    token = r.tokens["H"][7]
    s.blit(token, token.get_rect(center=render.cell_px(FORK)), special_flags=pygame.BLEND_ADD)
    for player, cell in (("p1", COPIES[0][-1]), ("p1", COPIES[1][-1]), ("p2", RED_RUN[-1])):
        glow = r.heads[(player, False)]
        s.blit(glow, glow.get_rect(center=render.cell_px(cell)), special_flags=pygame.BLEND_ADD)
    # the cut-off copy's crash, a moment after: the burst Renderer._apply
    # fires on a rules.Crash, from the game's own Fx
    fx = Fx(random.Random(2))
    fx.burst(render.cell_px(COPIES[1][-1]), render.lighten(BLUE, 0.3), count=40)
    fx.update(0.1)
    fx.draw(s)
    pts = [render.cell_px(c) for c in STEM + RED_RUN + COPIES[0] + COPIES[1]]
    cx, m = render.cell_px(FORK)[0], 20  # m: room for the glows round the cells
    half = max(abs(x - cx) for x, _ in pts) + m
    top, bottom = min(y for _, y in pts) - m, max(y for _, y in pts) + m
    return to_alpha(s.subsurface((cx - half, top, 2 * half, bottom - top)).copy())


def halo(shape: pygame.Surface, color, radius: int, strength: float) -> pygame.Surface:
    """kit.glow(), averaged with its mirror image: the halving blur drifts
    slightly towards one corner, which shows round thin neon strokes."""
    a = kit.glow(shape, color, radius, strength)
    b = pygame.transform.flip(kit.glow(pygame.transform.flip(shape, True, True), color, radius, strength),
                              True, True)
    b.set_alpha(128)
    a.blit(b, (0, 0))
    return a


def title(scale: int) -> pygame.Surface:
    """QURVES as a neon sign: no filled letters, only a glass tube bent round
    each glyph's outline -- a colour stroke with a near-white core, the same
    two-tone look the game gives its trails (render.make_stamps) -- in a glow.
    QUR is lit in P1's blue, VES in P2's red."""
    margin = scale * 5
    shape = kit.pad(kit.text_shape("QURVES", kit.PIXEL_FONT, 8 * scale, tracking=1), margin)
    t = max(3, scale // 2)  # tube thickness, just outside the glyph

    def ring(outer: int, inner: int) -> pygame.Surface:
        out = kit.dilate(shape, outer, (255, 255, 255), square=True)
        if inner:
            out.blit(kit.dilate(shape, inner, (255, 255, 255), square=True), (0, 0),
                     special_flags=pygame.BLEND_RGBA_SUB)
        else:
            out.blit(shape, (0, 0), special_flags=pygame.BLEND_RGBA_SUB)
        return out

    stroke = ring(t, 0)
    third = max(1, t // 3)
    core = ring(t - third, third)
    split = margin + 3 * 9 * scale - scale // 2  # between R and V (9 native px a glyph)
    w, h = shape.get_size()
    out = pygame.Surface((w, h), pygame.SRCALPHA)
    for x0, x1, color in ((0, split, BLUE), (split, w, RED)):
        part, part_core = (pygame.Surface((w, h), pygame.SRCALPHA) for _ in range(2))
        part.blit(stroke, (x0, 0), (x0, 0, x1 - x0, h))
        part_core.blit(core, (x0, 0), (x0, 0, x1 - x0, h))
        out.blit(halo(part, color, round(scale * 1.5), 0.35), (0, 0))
        out.blit(halo(part, color, max(4, scale // 2), 0.8), (0, 0))
        out.blit(kit.tint(part, color), (0, 0))
        out.blit(kit.tint(part_core, render.lighten(color, 0.8)), (0, 0))
    return kit.trim(out)


def scene(w: int, h: int, hy: int, spread: tuple[float, float] = (18, 260), lines: int = 14,
          haze: int = 220) -> pygame.Surface:
    """The arena's background colour with the floor below the horizon at `hy`.

    The arena's grid (render.make_background) as a synthwave floor: laid flat
    and running off to a horizon behind the title, fading out upwards. Its
    2 * `lines` + 1 lines fan out from `spread[0]` px apart at the horizon to
    `spread[1]` at the bottom edge."""
    surf = pygame.Surface((w, h))
    surf.fill(config.COLOR_BACKGROUND)
    floor = pygame.Surface((w, h - hy))
    floor.fill((0, 0, 0))
    grid = kit.shade(config.COLOR_GRID, 3.6)
    vx = w / 2
    for i in range(-lines, lines + 1):
        pygame.draw.aaline(floor, grid, (vx + i * spread[0], 0), (vx + i * spread[1], h - hy))
    z = 1.0
    while z < 40:
        y = (h - hy) / z
        pygame.draw.line(floor, grid, (0, round(y)), (w, round(y)))
        z *= 1.35
    floor.blit(kit.gradient(floor.get_size(), [(0, 0, 0), (110, 110, 110), (255, 255, 255)]), (0, 0),
               special_flags=pygame.BLEND_MULT)
    surf.blit(floor, (0, hy), special_flags=pygame.BLEND_ADD)
    # the horizon: the arena wall's colour, as a thin line in a low haze
    glow = pygame.transform.smoothscale(kit.radial((256, 256), (128, 128), 128, (60, 40, 140)), (w, haze))
    surf.blit(glow, (0, hy - haze // 2), special_flags=pygame.BLEND_ADD)
    surf.blit(kit.gradient((w, 2), [(0, 0, 0), config.COLOR_WALL, (0, 0, 0)], vertical=False), (0, hy),
              special_flags=pygame.BLEND_ADD)
    return surf


def art(size: int, pad: int = 0) -> pygame.Surface:
    """The square logo, `size` px; with `pad`, on a canvas `pad` px bigger on
    every side, the floor running on (fanning out as far again
    at the canvas's bottom edge) (see generate_logos.py: extended/)."""
    full = size + 2 * pad
    hy = pad + round(size * 0.6)
    fan = 18 + (260 - 18) * (full - hy) / (size - round(size * 0.6))  # the square's lines, carried on down
    surf = scene(full, full, hy, spread=(18, fan))

    h = kit.nearest(hero(), ZOOM)
    kit.blit_center(surf, kit.blur(kit.pad(h, 40), 12), (full / 2, pad + size * 0.38))
    kit.blit_center(surf, h, (full / 2, pad + size * 0.38))

    word = title(16)
    word = kit.fit(word, 880, 260) if word.get_width() > 880 else word
    kit.blit_center(surf, word, (full / 2, pad + size * 0.79))
    return surf


# Where the stem's first cell sits, in game px below hero()'s top edge (its
# highest cell, less the 20 px margin hero() leaves for the glows): the stem
# rises off the horizon there.
STEM_FOOT = (render.cell_px(STEM[0])[1]
             - min(render.cell_px(c)[1] for c in STEM + RED_RUN + COPIES[0] + COPIES[1]) + 20)


def wide(width: int, height: int) -> pygame.Surface:
    """The same scene laid out wide: a lower horizon with a broader, shallower
    floor running out to both sides, the fork above it at a smaller whole
    zoom, and QURVES on the floor below."""
    zoom = max(1, round(height * 3 / 512))
    hy = round(height * 0.66)
    surf = scene(width, height, hy, spread=(18 * height / 512, 260 * height / 512 * 1.4), lines=28,
                 haze=round(height * 0.3))

    h = kit.nearest(hero(), zoom)
    top = hy - STEM_FOOT * zoom
    centre = (width / 2, top + h.get_height() / 2)
    kit.blit_center(surf, kit.blur(kit.pad(h, 8 * zoom), 8), centre)
    kit.blit_center(surf, h, centre)

    word = title(max(1, round(height * 11 / 512)))
    kit.blit_center(surf, word, (width / 2, hy + (height - hy) * 0.5))
    return surf


def marquee() -> pygame.Surface:
    word = title(18)
    emblem = kit.trim(kit.nearest(hero(), 3))
    gap = 40
    w = emblem.get_width() + gap + word.get_width()
    out = pygame.Surface((w, max(emblem.get_height(), word.get_height())), pygame.SRCALPHA)
    out.blit(emblem, (0, (out.get_height() - emblem.get_height()) // 2))
    out.blit(word, (emblem.get_width() + gap, (out.get_height() - word.get_height()) // 2))
    return kit.trim(out)
