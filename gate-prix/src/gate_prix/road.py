"""The classic pseudo-3D road: one player's view of the track from behind their car.

`RoadView(rect).draw(surface, track, cam_z, cam_x, sprites_out, objects)` draws the
background and the road into `rect` and reports every visible sprite (the track's roadside
sprites plus `objects`) through `sprites_out`, far to near, for `draw_sprites` to blit.

The projection, as in the look file: DRAW_SEGMENTS segments ahead of the camera, each
segment's curve accumulated into a sideways offset and its hill into a height. Segments are
clipped near to far by the highest road drawn so far, so a crest hides the road behind it,
then painted far to near as flat polygons: the copper plate (alternating rings), the rumble
strip (gold and white), the road (two tones) and a cyan centre line. Nothing is scaled per
frame: only fills, polygons and blits of pre-rendered surfaces.
"""

from __future__ import annotations

import math

import pygame

from gate_prix import config
from gate_prix.sprites import Background, SpriteCache

SEG = config.SEG
NEAR = 30.0  # nearer than this a point is not projected: it is far below the view
_FAR = 1e6  # keeps polygons of points just past NEAR within pygame's integer range

PLATE = ((168, 104, 56), (184, 116, 64))  # machined in rings, alternating every 2 segments
RUMBLE = ((220, 170, 60), (250, 240, 220))  # gold and white
ROAD = ((40, 42, 62), (34, 36, 54))  # dark anodised, a faint sheen
CENTRE = (120, 220, 255)  # thin cyan dashes, like a waveguide
CENTRE_HALF_WIDTH = 0.015  # in road half-widths
AA_ROWS = 2  # segments at least this many rows tall get anti-aliased edges

Sprite = tuple[str, float, float, float, float]  # kind, x, y (its foot), scale, clip y


class RoadView:
    """One view rectangle (960x270 for 2P, 960x540 for 1P) and its projection."""

    def __init__(self, rect) -> None:
        self.rect = pygame.Rect(rect)
        self.width, self.height = self.rect.size
        self.horizon = round(self.height * config.HORIZON)
        self.background = Background.for_size(self.rect.size)
        n = config.DRAW_SEGMENTS
        self.segments = n
        # per point k (the start of the k-th segment from the camera's own): distance from
        # the camera, the accumulated world offset and height, and the screen x, y, half-width
        self.z = [0.0] * (n + 1)
        self.wx = [0.0] * (n + 1)
        self.wy = [0.0] * (n + 1)
        self.sx = [0.0] * (n + 1)
        self.sy = [0.0] * (n + 1)
        self.sw = [0.0] * (n + 1)
        # per segment k: the highest road nearer than it (its sprites are hidden below that),
        # and whether any of it shows
        self.clip = [0.0] * n
        self.visible = [False] * n
        self.base = 0  # the track index of segment 0, the camera's own
        self._count = 1  # the track's segment count
        self.cam_x = 0.0
        self.cam_y = 0.0

    # --- Projection -------------------------------------------------------------------------

    def project(self, track, cam_z: float, cam_x: float) -> None:
        """Project the road ahead of a camera at race distance cam_z, cam_x road half-widths
        to the side of the centre line."""
        segs = track.segments
        count = len(segs)
        n = self.segments
        b = math.floor(cam_z / SEG)
        phase = cam_z / SEG - b
        bi = b % count
        here = segs[bi]
        # the camera rides above its own car, so the car keeps its place over the hills
        cam_y = config.CAMERA_HEIGHT + track.height_at(cam_z + config.CAR_AHEAD)
        cam_w = cam_x * config.ROAD_HALF_WIDTH
        hw = self.width / 2
        hh = self.height / 2
        hz = self.horizon
        depth = config.CAMERA_DEPTH
        road = config.ROAD_HALF_WIDTH * hw
        zs, wxs, wys, sxs, sys_, sws = self.z, self.wx, self.wy, self.sx, self.sy, self.sw
        curves, heights = track.curves, track.heights  # these run on past the lap line
        x = 0.0
        dx = -here.curve * phase
        z = -phase * SEG
        for k in range(n + 1):
            y = heights[bi + k]
            zs[k] = z
            wxs[k] = x
            wys[k] = y
            if z > NEAR:
                p = depth / z
                sxs[k] = hw + p * (x - cam_w) * hw
                sys_[k] = hz - p * (y - cam_y) * hh
                sws[k] = p * road
            else:
                sxs[k] = hw
                sys_[k] = _FAR
                sws[k] = _FAR
            x += dx
            dx += curves[bi + k]
            z += SEG
        # near to far: a segment shows if its far edge is above all the road nearer to it
        height = float(self.height)
        maxy = height
        clip, visible = self.clip, self.visible
        for k in range(n):
            clip[k] = maxy
            y2 = sys_[k + 1]
            if zs[k] > NEAR and y2 < maxy and y2 < sys_[k]:
                visible[k] = True
                maxy = y2
            else:
                visible[k] = False
        self.base = bi
        self.cam_x = cam_w
        self.cam_y = cam_y
        self._count = count

    def place(self, rel_z: float, offset: float) -> tuple[float, float, float, float] | None:
        """Where something stands rel_z ahead of the camera, offset road half-widths from the
        centre line: its screen (x, y), its scale (pixels per road half-width) and the clip
        y below which a crest hides it. None when it is behind the camera or too far."""
        zs = self.z
        if rel_z <= NEAR or rel_z >= zs[-1]:
            return None
        k = int((rel_z - zs[0]) // SEG)
        k = min(self.segments - 1, max(0, k))
        f = (rel_z - zs[k]) / SEG
        wx = self.wx[k] + (self.wx[k + 1] - self.wx[k]) * f
        wy = self.wy[k] + (self.wy[k + 1] - self.wy[k]) * f
        hw = self.width / 2
        p = config.CAMERA_DEPTH / rel_z
        scale = p * config.ROAD_HALF_WIDTH * hw
        x = hw + p * (wx - self.cam_x) * hw + offset * scale
        y = self.horizon - p * (wy - self.cam_y) * self.height / 2
        return x, y, scale, self.clip[k]

    # --- Drawing ----------------------------------------------------------------------------

    def draw(self, surface: pygame.Surface, track, cam_z: float, cam_x: float,
             sprites_out: list[Sprite], objects=()) -> None:
        """Draw the background and the road into this view's rect of `surface`.

        `sprites_out` is cleared and filled with every visible sprite, far to near:
        (kind, x, y, scale, clip_y) in the view's own coordinates. `objects` are extra
        (z, x, kind) things to project (arches, item boxes, cars), with z a race distance
        like cam_z and x in road half-widths.
        """
        view = surface if self.rect == surface.get_rect() else surface.subsurface(self.rect)
        self.project(track, cam_z, cam_x)
        offset = track.heading_at(cam_z) / track.turn * config.PARALLAX_TILES * self.width
        self.background.draw(view, offset)
        self._draw_road(view)
        self._collect(track, cam_z, sprites_out, objects)

    def _draw_road(self, view: pygame.Surface) -> None:
        sxs, sys_, sws = self.sx, self.sy, self.sw
        visible = self.visible
        bi, count = self.base, self._count
        width = self.width
        rumble = config.RUMBLE
        centre = CENTRE_HALF_WIDTH
        fill = view.fill
        polygon = pygame.draw.polygon
        aaline = pygame.draw.aaline
        for k in range(self.segments - 1, -1, -1):
            if not visible[k]:
                continue
            y1 = round(min(_FAR, sys_[k]))
            y2 = round(sys_[k + 1])
            if y1 <= y2:
                continue  # thinner than a pixel row: the segments nearer cover it
            x1, w1 = sxs[k], sws[k]
            x2, w2 = sxs[k + 1], sws[k + 1]
            ring = (((bi + k) % count) >> 1) & 1
            fill(PLATE[ring], (0, y2, width, y1 - y2 + 1))
            r1, r2 = w1 * rumble, w2 * rumble
            polygon(view, RUMBLE[ring], ((x1 - r1, y1), (x2 - r2, y2), (x2 + r2, y2), (x1 + r1, y1)))
            polygon(view, ROAD[ring], ((x1 - w1, y1), (x2 - w2, y2), (x2 + w2, y2), (x1 + w1, y1)))
            if y1 - y2 >= AA_ROWS:  # smooth the long edges where their steps would show
                aaline(view, RUMBLE[ring], (x1 - r1, y1), (x2 - r2, y2))
                aaline(view, RUMBLE[ring], (x1 + r1, y1), (x2 + r2, y2))
                aaline(view, ROAD[ring], (x1 - w1, y1), (x2 - w2, y2))
                aaline(view, ROAD[ring], (x1 + w1, y1), (x2 + w2, y2))
            if ring:
                c1, c2 = w1 * centre, w2 * centre
                polygon(view, CENTRE, ((x1 - c1, y1), (x2 - c2, y2), (x2 + c2, y2), (x1 + c1, y1)))

    def _collect(self, track, cam_z: float, sprites_out: list[Sprite], objects) -> None:
        found: list[tuple[float, Sprite]] = []
        hi = config.SPRITE_SCALE_MAX * 1.1
        lo = config.SPRITE_SCALE_MIN / 1.2
        zs, sxs, sys_, sws, clip = self.z, self.sx, self.sy, self.sw, self.clip
        roadside = track.roadside
        bi, count = self.base, self._count
        for k in range(self.segments):
            here = roadside[(bi + k) % count]
            if not here or zs[k] <= NEAR:
                continue
            scale = sws[k]
            if not lo <= scale <= hi:
                continue
            x, y = sxs[k], sys_[k]
            for offset, kind in here:
                found.append((zs[k], (kind, x + offset * scale, y, scale, clip[k])))
        far = zs[-1]
        for z, offset, kind in objects:
            rel = z - cam_z
            if rel <= NEAR or rel >= far:
                continue
            placed = self.place(rel, offset)
            if placed is None or not lo <= placed[2] <= hi:
                continue
            x, y, scale, clip_y = placed
            found.append((rel, (kind, x, y, scale, clip_y)))
        found.sort(key=lambda item: -item[0])
        sprites_out.clear()
        sprites_out.extend(sprite for _, sprite in found)

    def draw_sprites(self, surface: pygame.Surface, sprites: list[Sprite],
                     cache: SpriteCache | None = None) -> None:
        """Blit the sprites `draw` reported, in order, into this view's rect."""
        view = surface if self.rect == surface.get_rect() else surface.subsurface(self.rect)
        cache = cache or SpriteCache.shared()
        w = self.width
        for kind, x, y, scale, clip_y in sprites:
            if -scale < x < w + scale:
                cache.blit(view, kind, x, y, scale, clip_y)
