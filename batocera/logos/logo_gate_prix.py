"""Gate Prix app icon: lights out under the start gantry, the right gate glowing ahead.

The look is a behind-the-car arcade racer's attract screen, Super Scaler style: one-point
perspective down the road into the dilution fridge, gold plate overhead, and the title
where the game itself writes it, on the start gantry's banner across the road. Its five
start lights are all green: GO. Under it the right gate's arch glows, H on its badge, a dim
decoy beside it, and the player's blue car is about to drive through. No other icon is a
first-person scene or a sign hung over the action.

Everything is the game's own and drawn by its own code: the fridge, the road, the roadside
coax and standoffs and the chequered lap line are road.RoadView projecting track.fridge()
(the lap line under the gantry, where the race starts); the gantry, the arches and the car
are sprites.render_sprite at the exact scale the projection gives them (the game's sprite
cache stops at its own view's sizes); the lit lights are render.Renderer._light_discs.

The scene is drawn once, big, on a canvas PAD_MAX px wider than the square on every side;
the square logo and its extended version (generate_logos.py) are crops of that same
picture, so the margin simply shows more of the fridge.
"""

from __future__ import annotations

import sys

import kit
import pygame

sys.path.insert(0, str(kit.ROOT / "gate-prix/src"))

from gate_prix import sprites, track  # noqa: E402
from gate_prix.render import Renderer  # noqa: E402
from gate_prix.road import RoadView  # noqa: E402

ROM = "gate_prix"

S = 1024
PAD_MAX = 512  # the picture runs on this far past the square on every side
HORIZON_AT = 0.5  # the horizon's height in the square
ZOOM = 1234.0  # the projection's half-height for the square, px (the game's view: 270)
CEILING = (196, 150, 60)  # the gold plate overhead, where the view runs out above
# What stands on the road, as (distance ahead of the camera, offset in road half-widths,
# sprite kind), far to near. The gantry stands on the lap line, so it comes first.
SQUARE = (
    (8000.0, 0.0, "gantry"),
    (4000.0, -0.5, "arch:Z"),
    (4000.0, 0.0, "arch:H:lit"),
    (2670.0, 0.0, "car:p1"),
)
WIDE = (  # the same, closer together, to fit under the wide tile's banner
    (5440.0, 0.0, "gantry"),
    (4300.0, -0.6, "arch:Z"),
    (4300.0, 0.0, "arch:H:lit"),
    (3200.0, 0.0, "car:p1"),
)


def scene(size: tuple[int, int], horizon: float, zoom: float, things) -> pygame.Surface:
    """The road scene on a `size` canvas: the horizon at y = `horizon`, the projection's
    half-height `zoom` px at the game's own 960x540 aspect, and `things` on the road."""
    width, height = size
    view = RoadView((0, 0, width, round(2 * zoom)), spread=zoom * 480 / 270)
    surf = pygame.Surface(view.rect.size)
    found: list = []
    view.draw(surf, track.fridge(), -things[0][0], 0.0, found, ())
    cache: dict = {}

    def put(kind, x, y, scale, clip_y=None):
        key = (kind, round(scale, 1))
        if key not in cache:
            cache[key] = sprites.render_sprite(kind, scale)
        img, ax, ay = cache[key]
        top = round(y) - ay
        rows = img.get_height() if clip_y is None else min(img.get_height(), round(clip_y) - top)
        if rows > 0:
            surf.blit(img, (round(x) - ax, top), (0, 0, img.get_width(), rows))

    for kind, x, y, scale, clip_y in found:  # the roadside, far to near
        if -scale < x < width + scale:
            put(kind, x, y, scale, clip_y)
    discs = Renderer._light_discs()["green"]
    for z, offset, kind in things:
        x, y, scale, _ = view.place(z, offset)
        put(kind, x, y, scale)
        if kind == "gantry":  # its lights, all lit: GO
            r = sprites.LIGHT_R * scale
            disc = min(discs, key=lambda d: abs(d.get_width() / 6 - r))
            half = disc.get_width() // 2
            for lx in sprites.LIGHT_X:
                surf.blit(disc, (round(x + lx * scale) - half, round(y - sprites.LIGHT_Y * scale) - half))
    out = pygame.Surface(size)
    out.fill(CEILING)
    out.blit(surf, (0, round(horizon - view.horizon)))
    return out


def art(size: int, pad: int = 0) -> pygame.Surface:
    """The square logo, `size` px; with `pad`, on a canvas `pad` px bigger on every side
    (see generate_logos.py: extended/), the same picture with more of the fridge round it."""
    assert pad <= PAD_MAX
    full = scene((S + 2 * PAD_MAX, S + 2 * PAD_MAX), PAD_MAX + HORIZON_AT * S, ZOOM, SQUARE)
    out = full.subsurface((PAD_MAX - pad, PAD_MAX - pad, S + 2 * pad, S + 2 * pad)).copy()
    return out if size == S else pygame.transform.smoothscale(out, (round((S + 2 * pad) * size / S),) * 2)


def wide(width: int, height: int) -> pygame.Surface:
    W, H = 1024, 512
    out = scene((W, H), 331, ZOOM / 2, WIDE)
    return out if (width, height) == (W, H) else pygame.transform.smoothscale(out, (width, height))


def marquee() -> pygame.Surface:
    """The gantry's banner alone, its title and chequers, on transparency."""
    u = 600
    img, ax, ay = sprites.render_sprite("gantry", u)
    half = round((sprites.GANTRY_POST + 0.08) * u) - 1
    top = ay - round(sprites.GANTRY_TOP * u) + 1
    bottom = ay - round(sprites.GANTRY_BANNER * u) - 1
    return img.subsurface((ax - half, top, 2 * half, bottom - top)).copy()
