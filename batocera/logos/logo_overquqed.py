"""Overquqed icon: one chef holding up one Bloch Bowl, in the game's kitchen.

The one light, warm icon of the set. The lower part is the game's own
checkered kitchen floor (render._floor, at x8), the top a band of the dark
kitchen wall with the title on it. The hero is P1's teal chef from
sprites.chef_frames(), facing the viewer, with a |+> Bloch Bowl carried
overhead where the game carries it (render.held_item_pos), drawn by
render.draw_bowl, plus a few of the gold sparkle squares a fresh CNOT link
throws (render.draw_item). Hero x14, all nearest-neighbour.

The lettering follows the in-game logo (scenes.draw_logo) rather than the
kit's neon wordmark: Press Start 2P, cream with gold Qs, and a hard ink drop
shadow, built at the font's native 8 px and integer-scaled, like ket.py
builds its labels.

The wide tile (wide(), for the cabinet's 2:1 game list) is the same kitchen
seen from further back: the wall and its title across the full width, the
chef centred on the floor below, floor and chef at half the square's scale.
"""

from __future__ import annotations

import sys

import kit
import pygame

sys.path.insert(0, str(kit.ROOT / "overquqed/src"))

from overquqed import palette as P, render, sprites  # noqa: E402
from overquqed.config import TILE  # noqa: E402

ROM = "overquqed"

FLOOR_SCALE = 8
HERO_SCALE = 14
WALL_H = 264  # px of dark wall behind the title
# the wide tile at 1024x512 (wide() scales these with its height): floor
# and chef at half the square's scale, the title only a little smaller
WIDE_FLOOR_SCALE = 4
WIDE_HERO_SCALE = 7
WIDE_TITLE_K = 10
WIDE_WALL_H = 160

# two-band pixel fills, light top / deeper bottom (no smooth gradients)
CREAM = ((255, 252, 240), (250, 224, 180))
GOLD = ((255, 226, 110), (240, 160, 40))
VEC_PLUS = (1.0, 0.0, 0.0)  # |+>: Bloch arrow toward the viewer


def _title(k: int) -> pygame.Surface:
    """OVERQUQED drawn at the font's native 8 px with two-band fills, scaled
    by k, with a hard shadow."""
    font = pygame.font.Font(str(kit.PIXEL_FONT), 8)
    text = "OVERQUQED"
    w = 8 * len(text)
    letters = pygame.Surface((w, 8), pygame.SRCALPHA)
    for i, ch in enumerate(text):
        top, bottom = GOLD if ch == "Q" else CREAM
        g = font.render(ch, False, (255, 255, 255)).convert_alpha()
        fill = pygame.Surface(g.get_size(), pygame.SRCALPHA)
        fill.fill(top, (0, 0, 8, 4))
        fill.fill(bottom, (0, 4, 8, 4))
        fill.blit(g, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
        letters.blit(fill, (8 * i, 0))
    letters = kit.nearest(letters, k)
    # the in-game logo's ink drop shadow: 3 px on 32 px letters there, so
    # under one font pixel; half a font pixel keeps the counters open
    d = k // 2
    ink = pygame.mask.from_surface(letters).to_surface(setcolor=P.INK, unsetcolor=(0, 0, 0, 0))
    out = pygame.Surface((letters.get_width() + d, letters.get_height() + d), pygame.SRCALPHA)
    out.blit(ink, (d, d))
    out.blit(letters, (0, 0))
    return kit.trim(out)


def _floor(width: int, height: int, scale: int = FLOOR_SCALE, wall_h: int = WALL_H,
           shift: int = 4) -> pygame.Surface:
    """The kitchen: wall band on top, the game's checkered floor below (at
    x`scale`, the tiles moved `shift` native px to the left)."""
    nw, nh = -(-width // scale), -(-height // scale)
    native = pygame.Surface((nw, nh))
    for ty in range(nh // TILE + 1):
        for tx in range((nw + shift) // TILE + 1):
            render._floor(native, tx, ty, tx * TILE - shift, ty * TILE)
    surf = pygame.Surface((width, height))
    surf.blit(kit.nearest(native, scale), (0, 0))
    # the wall: the game's dark cap colour, its lighter lip, an ink edge
    surf.fill(P.WALL, (0, 0, width, wall_h))
    surf.fill(P.WALL_TOP, (0, wall_h - 3 * scale, width, 2 * scale))
    surf.fill(P.INK, (0, wall_h - scale, width, scale))
    return surf


def _hero() -> pygame.Surface:
    """Chef with a bowl overhead, at native size (26 x 44)."""
    r = render.BOWL_R
    chef = sprites.chef_frames(P.P1)[("down", 0)]
    surf = pygame.Surface((26, 44), pygame.SRCALPHA)
    cx = 13
    sprite_top = 2 * r + 4
    # floor shadow, as KitchenView.draw puts it under the feet
    shadow = pygame.Surface((14, 5), pygame.SRCALPHA)
    pygame.draw.ellipse(shadow, (*kit.shade(P.FLOOR_B, 0.6), 255), (0, 0, 14, 5))
    surf.blit(shadow, (cx - 7, sprite_top + 22 - 4))
    surf.blit(chef, (cx - 8, sprite_top))
    # held overhead: the bowl's centre sits 8 px above the sprite's top
    render.draw_bowl(surf, cx, sprite_top - 8, VEC_PLUS, r, 1.0, 0.0, 0)
    for x, y, c in ((2, 4, P.GOLD), (23, 2, P.WHITE), (24, 9, P.GOLD), (0, 11, P.WHITE)):
        surf.fill(c, (x, y, 2, 2))
    return surf


def art(size: int) -> pygame.Surface:
    surf = _floor(size, size)
    title = _title(12)
    kit.blit_center(surf, title, (size / 2, WALL_H / 2 - 6))
    hero = kit.nearest(_hero(), HERO_SCALE)
    surf.blit(hero, hero.get_rect(midbottom=(size // 2, size - 66)))
    return surf


def wide(width: int, height: int) -> pygame.Surface:
    """The same kitchen for a 2:1 tile, seen from further back: the wall
    with the title runs the full width, the chef stands centred below."""
    u = height / 512
    scale = max(1, round(WIDE_FLOOR_SCALE * u))
    wall_h = round(WIDE_WALL_H * u)
    # the floor tiles lined up on the chef: a tile edge runs down the middle
    shift = (TILE - (width // 2 // scale) % TILE) % TILE
    surf = _floor(width, height, scale, wall_h, shift)
    kit.blit_center(surf, _title(max(1, round(WIDE_TITLE_K * u))), (width / 2, wall_h / 2 - scale))
    hero = kit.nearest(_hero(), max(1, round(WIDE_HERO_SCALE * u)))
    surf.blit(hero, hero.get_rect(midbottom=(width // 2, height - round(height * 0.05))))
    return surf


def marquee() -> pygame.Surface:
    """The title with the chef-and-bowl as a small emblem on the left."""
    title = _title(16)
    hero = kit.nearest(_hero(), 5)
    gap = 24
    h = max(title.get_height(), hero.get_height())
    out = pygame.Surface((hero.get_width() + gap + title.get_width(), h), pygame.SRCALPHA)
    out.blit(hero, (0, h - hero.get_height()))
    out.blit(title, (hero.get_width() + gap, (h - title.get_height()) // 2))
    return kit.trim(out)
