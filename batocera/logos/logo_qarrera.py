"""Qarrera app icon: two slot racers neck and neck through a curve.

The look is a slot-car racing set's box lid: one sweeping curve of track as
the swoosh, two racers on it seen from above and behind, and the title in a
leaning pixel italic, as if it were moving too, over a band of the track's
own kerb stripes. No other icon leans, and none has the race-livery stripe.

The hero is the game's core contest, the lead: the blue Light Cycle (from
Qurves, on the cabinet's blue side) sits in the red Pauli Jelly's
slipstream one wire over, about to pass, both on the ring a person's racer
rides on, in that person's colour. They drive left to right, into the
curve.

Everything is the game's own: the racers are its voxel models
(voxels.RACERS), drawn by sprite stacking (each layer of voxels a flat
slice, turned and stacked upwards), the track is the space scene's palette
(scenes.scene_for) with its glowing wires, red-and-blue kerbs and dark
slab sides, at the game's lane width and voxel size (config), the stars are
scenes.paint_space, and the streaks are the slipstream's colour
(render.STREAK). It is all drawn at half size and upscaled x2, like the
game's own 960x540 frame on the cabinet.
"""

from __future__ import annotations

import math
import random
import sys

import kit
import pygame

sys.path.insert(0, str(kit.ROOT / "qarrera/src"))

from qarrera import config, voxels  # noqa: E402
from qarrera.scenes import paint_space, scene_for  # noqa: E402

ROM = "qarrera"

K = 2  # every canvas pixel is K x K icon pixels
SQUASH = 0.62  # the camera's tilt: the ground plane, seen from above and in front
STREAK = (191, 230, 255)  # render.STREAK
SHADOW = (30, 34, 110)  # the track's blue, deepened under the white title


class _Track:
    """Stand-in for a Track, enough for scene_for to give the space palette."""

    class d:
        env = "space"

    cx = cy = [0.0]
    n = 1


PAL = scene_for(_Track()).palette


# --- racers -------------------------------------------------------------------------------

def stacked(model: voxels.Model, heading: float, v: int) -> tuple[pygame.Surface, tuple[int, int]]:
    """A voxel model by sprite stacking, `v` canvas pixels per voxel, turned
    to `heading` (radians on the ground plane, 0 = right, positive =
    clockwise on screen). Returns the sprite and where the model's origin,
    on the ground, sits in it."""
    layer = max(2, round(v * 0.66))  # how far each voxel layer rises
    xs = [k[0] for k in model]
    ys = [k[1] for k in model]
    zs = [k[2] for k in model]
    x0, y0, z0, z1 = min(xs), min(ys), min(zs), max(zs)
    w, h = (max(xs) - x0 + 1) * v, (max(ys) - y0 + 1) * v
    pivot = ((-x0 + 0.5) * v, (-y0 + 0.5) * v)
    side = 2 * math.ceil(max(pivot[0], w - pivot[0], pivot[1], h - pivot[1])) + 2
    sprite_h = round(side * SQUASH)
    out = pygame.Surface((side, sprite_h + (z1 + 1) * layer + 2), pygame.SRCALPHA)
    base = out.get_height() - sprite_h
    for z in range(z0, z1 + 1):
        s = pygame.Surface((side, side), pygame.SRCALPHA)
        for (x, y, zz), c in model.items():
            if zz == z:
                s.fill((*c, 255), (side / 2 - pivot[0] + (x - x0) * v, side / 2 - pivot[1] + (y - y0) * v, v, v))
        turned = pygame.transform.rotate(s, -math.degrees(heading))  # grows the surface: crop back
        flat = pygame.Surface((side, side), pygame.SRCALPHA)
        flat.blit(turned, turned.get_rect(center=(side / 2, side / 2)))
        flat = pygame.transform.scale(flat, (side, sprite_h))
        dark = flat.copy()
        dark.fill((120, 120, 150, 255), special_flags=pygame.BLEND_RGBA_MULT)
        lit = flat.copy()
        lit.fill((40, 40, 36, 0), special_flags=pygame.BLEND_RGB_ADD)  # the sun on the tops
        top = base - z * layer
        for k in range(layer, 0, -1):  # the layer's side, then its lit top
            out.blit(dark, (0, top + k))
        out.blit(lit, (0, top))
    return out, (side // 2, base + sprite_h // 2)


def ring(color, radius: float, width: int) -> pygame.Surface:
    """The ring a person's racer rides on (render.py's "ring" decal)."""
    w, h = round(2 * radius) + 4, round(2 * radius * SQUASH) + 4
    s = pygame.Surface((w, h), pygame.SRCALPHA)
    pygame.draw.ellipse(s, (*color, 255), (2, 2, w - 4, h - 4), width)
    return s


# --- the curve ----------------------------------------------------------------------------

class Curve:
    """A circular curve of track on the ground plane, `v` canvas pixels per
    voxel: centre (cx, cy) on the canvas, radius r (canvas px, before the
    squash), drawn from angle a0 to a1. Racers drive it with the angle going
    down: along its bottom to the right, then up."""

    def __init__(self, cx: float, cy: float, r: float, a0: float, a1: float, v: int):
        self.cx, self.cy, self.r, self.a0, self.a1, self.v = cx, cy, r, a0, a1, v
        unit = v / config.VOXEL_SIZE  # canvas pixels per world unit
        self.lane_w = config.LANE_W * unit
        self.half = config.LANES / 2 * self.lane_w  # from the centre line to an edge
        self.slab = 8.0 * unit * SQUASH  # mesh.SLAB, the track's thickness

    def at(self, a: float, offset: float = 0.0) -> tuple[float, float]:
        """Screen point at angle a, `offset` out from the centre line."""
        r = self.r + offset
        return self.cx + r * math.cos(a), self.cy + r * math.sin(a) * SQUASH

    def heading(self, a: float) -> float:
        """The direction of travel at angle a, on the ground plane."""
        return math.atan2(-math.cos(a), math.sin(a))

    def lane(self, i: int) -> float:
        """Wire i's offset (0 is the outer wire)."""
        return self.half - self.lane_w / 2 - i * self.lane_w

    def angle(self, t: float) -> float:
        return self.a0 + (self.a1 - self.a0) * t

    def arc(self, offset: float, steps: int = 200, drop: float = 0.0) -> list[tuple[float, float]]:
        return [(x, y + drop) for x, y in (self.at(self.angle(i / steps), offset) for i in range(steps + 1))]

    def draw(self, surf: pygame.Surface) -> None:
        kerb = max(4, round(self.v * 0.8))
        outer, inner = self.arc(self.half + 2), self.arc(-self.half - 2)
        # The slab's sides: the outer one faces the camera along the bottom.
        pygame.draw.polygon(surf, PAL.side, outer + self.arc(self.half + 2, drop=self.slab)[::-1])
        pygame.draw.polygon(surf, PAL.bed, outer + inner[::-1])
        for edge in (self.half, -self.half):
            pygame.draw.lines(surf, PAL.edge, False, self.arc(edge), 2)
        steps = 72
        for side in (self.half, -self.half):  # the kerbs, red and blue
            pts = self.arc(side, steps)
            band = self.arc(side - kerb if side > 0 else side + kerb, steps)
            for i in range(steps):
                c = PAL.kerb if i % 2 else PAL.kerb_alt
                pygame.draw.polygon(surf, c, [pts[i], pts[i + 1], band[i + 1], band[i]])
        glow = pygame.Surface(surf.get_size(), pygame.SRCALPHA)
        for i in range(config.LANES):  # the wires glow
            pygame.draw.lines(glow, (*PAL.wire, 60), False, self.arc(self.lane(i)), max(3, self.v - 1))
        surf.blit(glow, (0, 0))
        for i in range(config.LANES):
            pygame.draw.lines(surf, kit.lerp(PAL.wire, (255, 255, 255), 0.35), False, self.arc(self.lane(i)),
                              max(1, self.v // 4))


def stars(size: tuple[int, int]) -> pygame.Surface:
    tile = paint_space(random.Random(7))
    s = pygame.Surface(size)
    for x in range(0, size[0], tile.get_width()):
        for y in range(0, size[1], tile.get_height()):
            s.blit(tile, (x, y))
    return s


def race(surf: pygame.Surface, curve: Curve, cycle_at: float, jelly_at: float) -> None:
    """The two racers on the curve at those angles, back to front: the cycle
    on wire 2, in the slipstream of the jelly ahead on wire 1."""
    v = curve.v
    placed = []
    for model, wire, a, color in ((voxels.cycle, 2, cycle_at, config.PLAYER_COLORS["p1"]),
                                  (voxels.jelly, 1, jelly_at, config.PLAYER_COLORS["p2"])):
        x, y = curve.at(a, curve.lane(wire))
        placed.append((y, model, a, x, wire, color))
    for y, model, a, x, wire, color in sorted(placed, key=lambda p: p[0]):
        r = ring(color, 11 * v, max(3, v // 2))
        surf.blit(r, r.get_rect(center=(round(x), round(y))))
        if model is voxels.cycle:  # drafting: streaks off its sides
            h = curve.heading(a)
            dx, dy = math.cos(h), math.sin(h) * SQUASH
            for side, length, back in ((-1, 6, 3), (1, 5, 4), (-1, 4, 9), (1, 6, 10)):
                ox, oy = curve.at(a, curve.lane(wire) + side * 4.5 * v)
                bx, by = ox - dx * back * v, oy - dy * back * v
                pygame.draw.line(surf, STREAK, (bx, by - v), (bx - dx * length * v, by - dy * length * v - v),
                                 max(2, v // 3))
        sprite, (px, py) = stacked(model(), curve.heading(a), v)
        surf.blit(sprite, (round(x - px), round(y - py)))


# --- the title ----------------------------------------------------------------------------

def italic(shape: pygame.Surface, every: int = 3) -> pygame.Surface:
    """Lean a pixel shape: every `every` rows up shift one pixel right, so
    the stair-steps stay whole pixels."""
    w, h = shape.get_size()
    out = pygame.Surface((w + (h - 1) // every, h), pygame.SRCALPHA)
    for y in range(h):
        out.blit(shape, ((h - 1 - y) // every, y), (0, y, w, 1))
    return out


def kerb_band(width: int, height: int, block: int) -> pygame.Surface:
    """The kerb's red and blue blocks, leaning like the title."""
    s = pygame.Surface((width, height), pygame.SRCALPHA)
    for i, x in enumerate(range(-height, width + height, block)):
        c = PAL.kerb if i % 2 else PAL.kerb_alt
        pygame.draw.polygon(s, c, [(x + height // 3, 0), (x + block + height // 3, 0), (x + block, height - 1),
                                   (x, height - 1)])
    return s


def title() -> pygame.Surface:
    """QARRERA leaning, white over a hard shadow in the track's blue, with a
    kerb band below. Built at the font's 8 px doubled (so the lean can step
    every third half-pixel), for a whole-number upscale."""
    word = italic(kit.nearest(kit.text_shape("QARRERA", kit.PIXEL_FONT, 8, tracking=1), 2))
    w, h = word.get_size()
    band = kerb_band(w - 4, 4, 9)
    out = pygame.Surface((w, h + 2 + 4 + band.get_height()), pygame.SRCALPHA)
    out.blit(kit.tint(word, SHADOW), (0, 2))
    out.blit(kit.tint(word, (255, 255, 255)), (0, 0))
    out.blit(band, (0, h + 6))
    return out


# --- the tiles ----------------------------------------------------------------------------

def art(size: int, pad: int = 0) -> pygame.Surface:
    """The square logo, `size` px; with `pad`, on a canvas `pad` px bigger on
    every side, the stars and the curve running on (see generate_logos.py: extended/)."""
    C = 512
    o = pad // K  # the pad on the canvas
    canvas = stars((C + 2 * o, C + 2 * o))
    curve = Curve(o + C * 0.22, o - C * 0.11, 520, math.radians(150), math.radians(-15), 8)
    at = curve.angle(0.385), curve.angle(0.555)
    if o:  # the same circle, on past the bigger canvas's edges
        curve = Curve(curve.cx, curve.cy, curve.r, math.radians(185), math.radians(-40), curve.v)
    curve.draw(canvas)
    race(canvas, curve, *at)
    word = kit.nearest(title(), 3)
    canvas.blit(word, word.get_rect(midbottom=(o + C // 2, o + C - 40)))
    surf = kit.finish(kit.nearest(canvas, K), vignette_strength=0.45)
    E = (C + 2 * o) * K
    return surf if size == C * K else pygame.transform.smoothscale(surf, (round(E * size / (C * K)),) * 2)


def wide(width: int, height: int) -> pygame.Surface:
    """The box lid turned landscape: a flatter, wider curve across the top,
    the racers on it, the title under it."""
    W, H = 512, 256
    canvas = stars((W, H))
    curve = Curve(W * 0.42, -H * 0.62, 470, math.radians(140), math.radians(30), 5)
    curve.draw(canvas)
    race(canvas, curve, curve.angle(0.38), curve.angle(0.60))
    word = kit.nearest(title(), 2)
    canvas.blit(word, word.get_rect(midbottom=(W // 2, H - 22)))
    surf = kit.finish(kit.nearest(canvas, K), vignette_strength=0.4)
    return surf if (width, height) == (W * K, H * K) else pygame.transform.smoothscale(surf, (width, height))


def marquee() -> pygame.Surface:
    return kit.trim(kit.nearest(title(), 8))
