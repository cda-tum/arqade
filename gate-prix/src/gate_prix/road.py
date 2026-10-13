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

The boost's wider field of view is only a smaller projection constant (`depth`), with the
camera pulled in towards its car by the same factor (`ahead`): the car stays where it is
and the same size while the road and everything on it stretch away. `lift` raises the
camera a little, for the shake at speed.
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
CHEQUER = ((18, 18, 26), (240, 240, 246))  # the finish line's squares
CHEQUER_COLUMNS = 10
AA_ROWS = 2  # segments at least this many rows tall get anti-aliased edges

Sprite = tuple[str, float, float, float, float]  # kind, x, y (its foot), scale, clip y


class RoadView:
    """One view rectangle (480x540 for each of 2P's two, 960x540 for 1P) and its projection.

    `spread` is the horizontal projection's half-width in pixels: by default half the view's
    width. A narrow view sets it wider than that, so its road and cars are not squeezed to
    half their width (the view then shows the middle of a wider picture)."""

    def __init__(self, rect, spread: float | None = None) -> None:
        self.rect = pygame.Rect(rect)
        self.width, self.height = self.rect.size
        self.spread = self.width / 2 if spread is None else float(spread)
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
        self.depth = config.CAMERA_DEPTH

    # --- Projection -------------------------------------------------------------------------

    def project(self, track, cam_z: float, cam_x: float, depth: float | None = None,
                ahead: float | None = None, lift: float = 0.0) -> None:
        """Project the road ahead of a camera at race distance cam_z, cam_x road half-widths
        to the side of the centre line. `depth` is the projection constant (CAMERA_DEPTH
        when None), `ahead` the camera's distance to its car (CAR_AHEAD), whose road height
        it rides above, and `lift` extra camera height."""
        segs = track.segments
        count = len(segs)
        n = self.segments
        b = math.floor(cam_z / SEG)
        phase = cam_z / SEG - b
        bi = b % count
        here = segs[bi]
        # the camera rides above its own car, so the car keeps its place over the hills
        ahead = config.CAR_AHEAD if ahead is None else ahead
        cam_y = config.CAMERA_HEIGHT + lift + track.height_at(cam_z + ahead)
        cam_w = cam_x * config.ROAD_HALF_WIDTH
        cx = self.width / 2
        hw = self.spread
        hh = self.height / 2
        hz = self.horizon
        depth = self.depth = config.CAMERA_DEPTH if depth is None else depth
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
                sxs[k] = cx + p * (x - cam_w) * hw
                sys_[k] = hz - p * (y - cam_y) * hh
                sws[k] = p * road
            else:
                sxs[k] = cx
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
        p = self.depth / rel_z
        scale = p * config.ROAD_HALF_WIDTH * self.spread
        x = self.width / 2 + p * (wx - self.cam_x) * self.spread + offset * scale
        y = self.horizon - p * (wy - self.cam_y) * self.height / 2
        return x, y, scale, self.clip[k]

    # --- Drawing ----------------------------------------------------------------------------

    def draw(self, surface: pygame.Surface, track, cam_z: float, cam_x: float,
             sprites_out: list[Sprite], objects=(), depth: float | None = None,
             ahead: float | None = None, lift: float = 0.0) -> None:
        """Draw the background and the road into this view's rect of `surface`.

        `sprites_out` is cleared and filled with every visible sprite, far to near:
        (kind, x, y, scale, clip_y) in the view's own coordinates. `objects` are extra
        (z, x, kind) things to project (arches, item boxes, cars), with z a race distance
        like cam_z and x in road half-widths. `depth`, `ahead` and `lift` are `project`'s.
        """
        view = surface if self.rect == surface.get_rect() else surface.subsurface(self.rect)
        self.project(track, cam_z, cam_x, depth, ahead, lift)
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
            if (bi + k) % count in (0, count - 1):  # the lap line: a chequered band
                self._chequer(view, x1, y1, w1, x2, y2, w2)
            elif ring:
                c1, c2 = w1 * centre, w2 * centre
                polygon(view, CENTRE, ((x1 - c1, y1), (x2 - c2, y2), (x2 + c2, y2), (x1 + c1, y1)))

    @staticmethod
    def _chequer(view, x1, y1, w1, x2, y2, w2) -> None:
        """The finish line over the segments either side of the lap line: CHEQUER_COLUMNS
        squares across in two rows each, white on black (a dozen polygons a segment, only
        while it is in sight)."""
        polygon = pygame.draw.polygon
        polygon(view, CHEQUER[0], ((x1 - w1, y1), (x2 - w2, y2), (x2 + w2, y2), (x1 + w1, y1)))
        ym, xm, wm = (y1 + y2) / 2, (x1 + x2) / 2, (w1 + w2) / 2
        n = CHEQUER_COLUMNS
        for row, (ya, xa, wa, yb, xb, wb) in enumerate(((y1, x1, w1, ym, xm, wm),
                                                        (ym, xm, wm, y2, x2, w2))):
            for i in range(row % 2, n, 2):
                u0, u1 = -1 + 2 * i / n, -1 + 2 * (i + 1) / n
                polygon(view, CHEQUER[1], ((xa + u0 * wa, ya), (xb + u0 * wb, yb),
                                           (xb + u1 * wb, yb), (xa + u1 * wa, ya)))

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
