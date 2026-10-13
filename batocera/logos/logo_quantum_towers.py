"""Qlimbers (quantum-towers): the title *is* the tower.

The icon is one tall stone tower standing in a dusk sky. Its floors are
the letters Q-L-I-M-B-E-R-S, carved in gold into the stone where the game
draws a cleared floor's window. Above them is the gold target band with
its ket and the crenellated roof. P1's cyan climber is on the right wall,
a few floors below the top and reaching for it. The tower runs off the
bottom edge, so the eye starts at the base and climbs, the way the
players do.

The top of the tower is the game's own drawing code, drawn at the game's
internal resolution and nearest-upscaled: `visuals._draw_tower_body`
(roof, gold "current" band and its `notation.render_state` ket) and
`visuals.draw_climber` in its climbing pose. The lettered floors below are
drawn here in the same style, since the game's bands are a fixed 46 px
tall. That style is the stone body with a darker drop shadow, the trim
border and inner wall lines, a trim line between floors, and a recess in
the window colour. Colours all come from `config`. The marquee puts the
same carved letters along a horizontal stone parapet, with the gold ket
block as its emblem. The wide tile is too shallow for eight floors, so its
letters go on that parapet, as a battlement in front of the tower's base.
"""

from __future__ import annotations

import math
import random
import sys

import kit
import pygame

sys.path.insert(0, str(kit.ROOT / "quantum-towers/src"))

from quantum_towers import config, fonts, visuals  # noqa: E402
from quantum_towers.quantum import State  # noqa: E402

ROM = "quantum_towers"
TITLE = "QLIMBERS"
TARGET = State(1 / math.sqrt(2) + 0j, 1 / math.sqrt(2) + 0j)  # |+>

K = 3  # upscale factor: one internal pixel is 3x3 on the icon
WIDTH = 64  # tower body width, internal px
FLOOR_H = 30  # a lettered floor, internal px (the game's bands are 46)
GLYPH = 3  # the letters are Press Start 2P at 3x its native 8 px, internally
TRIM = config.COLOR_TOWER_TRIM
RECESS = visuals._darken(config.COLOR_TOWER, 0.4)  # the game's window colour
GOLD_TOP, GOLD_BOTTOM = config.COLOR_HINT, config.COLOR_TARGET


def _carved(ch: str) -> pygame.Surface:
    """One gold letter carved into stone: a dark recess offset down-right
    (the letter's cut edge), then the letter with a top-to-bottom gold fill."""
    shape = kit.text_shape(ch, kit.PIXEL_FONT, 8 * GLYPH)
    gold = kit.tint(shape, kit.gradient(shape.get_size(), [GOLD_TOP, GOLD_BOTTOM]))
    out = pygame.Surface((shape.get_width() + 2, shape.get_height() + 2), pygame.SRCALPHA)
    out.blit(kit.tint(shape, RECESS), (2, 2))
    out.blit(kit.tint(shape, visuals._darken(GOLD_BOTTOM, 0.45)), (1, 1))
    out.blit(gold, (0, 0))
    return out


def _lettered_floors(height: int) -> pygame.Surface:
    """The tower's body below the gold band: one floor per letter, then
    plain stone to `height`. Mirrors _draw_tower_body's construction."""
    surf = pygame.Surface((WIDTH + 3, height), pygame.SRCALPHA)
    body = pygame.Rect(0, 0, WIDTH, height)
    pygame.draw.rect(surf, visuals._darken(config.COLOR_TOWER, 0.55), body.move(3, 0))
    pygame.draw.rect(surf, config.COLOR_TOWER, body)
    for i, ch in enumerate(TITLE):
        band = pygame.Rect(0, i * FLOOR_H, WIDTH, FLOOR_H)
        letter = _carved(ch)
        surf.blit(letter, letter.get_rect(center=(band.centerx + 1, band.centery + 1)))
        pygame.draw.line(surf, TRIM, (band.left + 5, band.bottom), (band.right - 5, band.bottom), 2)
    # the game's 3 px outer border plus its inner wall lines (no top edge:
    # the gold band above closes the body off)
    for x in (body.left + 1, body.right - 2, body.left + 3, body.right - 3):
        pygame.draw.line(surf, TRIM, (x, 0), (x, height), 3)
    return surf


def _tower(height: int) -> tuple[pygame.Surface, pygame.Rect]:
    """The whole tower at internal resolution, `height` px tall, plus the
    gold band's rect (for the light behind it)."""
    margin = 26  # room beside the right wall for the climber
    band = config.TOWER_BAND_HEIGHT
    surf = pygame.Surface((WIDTH + margin + 4, height), pygame.SRCALPHA)
    top = pygame.Rect(0, 12, WIDTH, band)  # 12 px headroom for the crenellations
    surf.blit(_lettered_floors(height - top.bottom), (0, top.bottom))
    # player on floor 15, camera on 16: the gold band is the only band, with
    # the roof directly on it, which is how the game draws the final climb
    floor = config.TOWER_HEIGHT - 1
    visuals._draw_tower_body(surf, top, floor, floor + 1, TARGET, TARGET, [fonts.load_font(8)])

    # the climber, two and a half floors down the lettered wall (alongside
    # L and I), still reaching up towards the gold band
    _climber(surf, top.right, top.bottom + FLOOR_H * 5 // 2)
    return surf, top


def _climber(surf: pygame.Surface, wall_x: int, feet_y: int) -> None:
    """P1 in its climbing pose on a right-hand wall, reaching up, with a
    1 px dark outline so it holds its shape against the sky."""
    fig = pygame.Surface(surf.get_size(), pygame.SRCALPHA)
    visuals.draw_climber(fig, wall_x, feet_y, config.COLOR_PLAYER_1, 0.0, -1, climb_progress=0.5)
    surf.blit(kit.dilate(fig, 1, config.COLOR_TEXT_SHADOW, square=True), (0, 0))
    surf.blit(fig, (0, 0))


def _title_row(surf: pygame.Surface, left: int, centery: int, cell: int) -> None:
    """The carved letters in a row, one per `cell` px, from x=left."""
    for i, ch in enumerate(TITLE):
        letter = _carved(ch)
        surf.blit(letter, letter.get_rect(center=(left + cell * i + cell // 2 + 1, centery + 1)))


def _sky(width: int, height: int) -> pygame.Surface:
    """Dusk: the title screen's night navy overhead, warming towards the
    horizon behind the tower's base, with a sparse scatter of stars."""
    sky = kit.gradient((width, height), [
        config.COLOR_BACKGROUND, (24, 22, 54), (62, 40, 88), (150, 74, 84), (214, 120, 70),
    ]).convert()
    rng = random.Random(3)
    for _ in range(round(46 * height / width)):
        x, y = rng.randrange(width), rng.randrange(round(height * 0.45))
        b = round(rng.randint(120, 220) * (1 - y / (height * 0.5)))
        pygame.draw.rect(sky, (b, b, min(255, b + 20)), (x // K * K, y // K * K, K, K))
    return sky


def art(size: int) -> pygame.Surface:
    canvas = _sky(size, size)
    top_y = 66
    tower, gold = _tower((size - top_y) // K + 1)
    tower = kit.nearest(tower, K)
    # centre the tower body itself, so the climber hangs out to the right
    x = size // 2 - WIDTH * K // 2
    light = (x + gold.centerx * K, top_y + gold.centery * K)
    canvas.blit(kit.radial((size, size), light, 300, (150, 96, 20), 0.9), (0, 0),
                special_flags=pygame.BLEND_ADD)
    canvas.blit(tower, (x, top_y))
    return canvas


def wide(width: int, height: int) -> pygame.Surface:
    """Eight lettered floors don't fit a 2:1 tile at a readable size, so the
    title moves down onto a battlement in front of the tower's base (the
    marquee's parapet), and the tower above it is the game's own: roof, gold
    band and ket, a cleared floor with its window, and P1 reaching up the
    right wall. At 512 px tall the pixels are the square icon's size."""
    k = max(1, round(K * height / 512))
    cw, ch = -(-width // k), -(-height // k)
    canvas = _sky(width, height)
    scene = pygame.Surface((cw, ch), pygame.SRCALPHA)

    # player on floor 15, the camera placed so the roof sits on tower.top:
    # the gold band, then cleared floors running off the bottom
    band = config.TOWER_BAND_HEIGHT
    floors = ch // band + 1
    tower = pygame.Rect((cw - WIDTH) // 2, 17, WIDTH, band * floors)
    visuals._draw_tower_body(scene, tower, config.TOWER_HEIGHT - 1, config.TOWER_HEIGHT + 1 - floors,
                             TARGET, TARGET, [fonts.load_font(8)])
    _climber(scene, tower.right, tower.top + band + 42)  # one floor below the band

    # the battlement, built like the marquee's parapet, running off the bottom
    cell = 28
    wall = pygame.Rect(0, ch - 53, cell * len(TITLE) + 36, 53 + 10)
    wall.centerx = cw // 2
    pygame.draw.rect(scene, visuals._darken(config.COLOR_TOWER, 0.55), wall.move(3, 4))
    pygame.draw.rect(scene, config.COLOR_TOWER, wall)
    visuals._draw_crenellations(scene, wall, TRIM)
    course = pygame.Rect(0, wall.top + 3, cell * len(TITLE), FLOOR_H)
    course.centerx = cw // 2
    _title_row(scene, course.left, course.centery, cell)
    pygame.draw.line(scene, TRIM, (wall.left + 5, course.bottom + 2), (wall.right - 5, course.bottom + 2), 2)
    pygame.draw.rect(scene, TRIM, wall, width=3)

    light = (tower.centerx * k, (tower.top + band / 2) * k)
    canvas.blit(kit.radial((width, height), light, 100 * k, (150, 96, 20), 0.9), (0, 0),
                special_flags=pygame.BLEND_ADD)
    canvas.blit(kit.nearest(scene, k), (0, 0))
    return canvas


def marquee() -> pygame.Surface:
    """A horizontal stone parapet: the gold ket block as the emblem on the
    left, then the carved letters, under one row of crenellations."""
    cell, height, ket_w = 30, 36, 46
    w = ket_w + cell * len(TITLE) + 6
    surf = pygame.Surface((w + 3, height + 13), pygame.SRCALPHA)
    body = pygame.Rect(0, 9, w, height)
    pygame.draw.rect(surf, visuals._darken(config.COLOR_TOWER, 0.55), body.move(3, 4))
    pygame.draw.rect(surf, config.COLOR_TOWER, body)
    visuals._draw_crenellations(surf, body, TRIM)
    gold = pygame.Rect(body.left + 6, body.top + 6, ket_w - 8, height - 12)
    pygame.draw.rect(surf, RECESS, gold.inflate(6, 6), border_radius=3)
    pygame.draw.rect(surf, config.COLOR_TARGET, gold, border_radius=3)
    ket = fonts.load_font(8).render("|+>", False, config.COLOR_TEXT_SHADOW)
    surf.blit(ket, ket.get_rect(center=gold.center))
    _title_row(surf, body.left + ket_w, body.centery, cell)
    pygame.draw.rect(surf, TRIM, body, width=3)
    return kit.nearest(surf, 4)
