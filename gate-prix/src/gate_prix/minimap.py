"""The minimap: the lap seen from above, with a dot for every car.

`Minimap(track, size)` draws the outline once (`track.plan()`, the curves integrated into
x/y and scaled to fit the box): the road as a light line on a dark edge, a small tick
across it at every gate row and item box, and the chequered finish line. Per frame only
the dots are blitted (`draw`): a small one per car in its colour, a bigger ringed one for
each player's own car, each with its name beside it (P1, P2, CPU1 ...; drawn once, at
start-up, like the dots). A car's place on it is its race distance along the plan.
"""

from __future__ import annotations

import math

import pygame

from gate_prix import config
from gate_prix.race import label
from gate_prix.sprites import font

SS = 3
EDGE = (10, 12, 26)
ROAD = (150, 170, 210)
ROW_TICK = (255, 230, 120)
BOX_TICK = (110, 200, 255)
WHITE = (255, 255, 255)


class Minimap:
    _cache: dict[tuple[int, tuple[int, int]], Minimap] = {}

    def __init__(self, track, size: tuple[int, int]) -> None:
        self.size = w, h = size
        self.lap = track.lap_length()
        plan = track.plan()
        xs, ys = [p[0] for p in plan], [p[1] for p in plan]
        pad = 12
        k = min((w - 2 * pad) / (max(xs) - min(xs)), (h - 2 * pad) / (max(ys) - min(ys)))
        ox = (w - k * (max(xs) - min(xs))) / 2 - k * min(xs)
        oy = (h - k * (max(ys) - min(ys))) / 2 + k * max(ys)
        # every segment's start on the map, the lap line again at the end (north is up)
        self.points = [(ox + k * x, oy - k * y) for x, y in plan]
        self.surface = self._outline(track)
        self._dots: dict[tuple[str, bool], tuple[pygame.Surface, int]] = {}
        for colour, col in config.CAR_COLORS.items():
            for big in (False, True):
                self._dots[(colour, big)] = self._dot(col, big)
        self._labels = {car_id: self._label(car_id) for car_id in
                        ("p1", "p2", *config.CPU_IDS)}

    @classmethod
    def for_track(cls, track, size: tuple[int, int]) -> Minimap:
        key = (id(track), tuple(size))
        if key not in cls._cache:
            cls._cache[key] = cls(track, size)
        return cls._cache[key]

    def point(self, z: float) -> tuple[float, float]:
        """Where race distance z is on the map (in the map's own pixels)."""
        f = (z % self.lap) / config.SEG
        i = min(len(self.points) - 2, int(f))
        f -= i
        (x0, y0), (x1, y1) = self.points[i], self.points[i + 1]
        return x0 + (x1 - x0) * f, y0 + (y1 - y0) * f

    def _across(self, z: float, half: float):
        """A short line across the track at z, `half` pixels either side (at SS x)."""
        x, y = self.point(z)
        x2, y2 = self.point(z + config.SEG)
        d = math.hypot(x2 - x, y2 - y) or 1.0
        nx, ny = -(y2 - y) / d, (x2 - x) / d
        return ((x + nx * half) * SS, (y + ny * half) * SS), ((x - nx * half) * SS, (y - ny * half) * SS)

    def _outline(self, track) -> pygame.Surface:
        w, h = self.size
        big = pygame.Surface((w * SS, h * SS), pygame.SRCALPHA)
        pts = [(x * SS, y * SS) for x, y in self.points]
        pygame.draw.lines(big, EDGE, True, pts, 7 * SS)
        pygame.draw.lines(big, ROAD, True, pts, 3 * SS)
        for z in track.rows:
            a, b = self._across(z, 3.5)
            pygame.draw.line(big, ROW_TICK, a, b, round(1.5 * SS))
        for z, _ in track.boxes:
            a, b = self._across(z, 3.5)
            pygame.draw.line(big, BOX_TICK, a, b, round(1.5 * SS))
        # the finish line: a little chequered bar across the lap line
        a, b = self._across(0.0, 6)
        for i in range(4):
            p = (a[0] + (b[0] - a[0]) * i / 4, a[1] + (b[1] - a[1]) * i / 4)
            q = (a[0] + (b[0] - a[0]) * (i + 1) / 4, a[1] + (b[1] - a[1]) * (i + 1) / 4)
            pygame.draw.line(big, EDGE, a if i == 0 else p, q, 4 * SS)
            pygame.draw.line(big, WHITE if i % 2 else (30, 30, 40), p, q, round(2.5 * SS))
        img = pygame.transform.smoothscale(big, (w, h))
        img.set_alpha(255, pygame.RLEACCEL)
        return img

    @staticmethod
    def _dot(col, big: bool) -> tuple[pygame.Surface, int]:
        r = 5 if big else 3
        n = (r + 3) * 2 * SS
        s = pygame.Surface((n, n), pygame.SRCALPHA)
        c = n // 2
        if big:
            pygame.draw.circle(s, WHITE, (c, c), (r + 2) * SS)
        pygame.draw.circle(s, EDGE, (c, c), (r + 1) * SS if big else (r + 1) * SS)
        pygame.draw.circle(s, col, (c, c), r * SS)
        img = pygame.transform.smoothscale(s, (n // SS, n // SS))
        return img, n // SS // 2

    @staticmethod
    def _label(car_id: str) -> pygame.Surface:
        """A car's name, small, with a dark edge so it reads over the road."""
        col = config.PLAYER_COLORS.get(car_id, (225, 228, 238))
        face = font(9)
        fg = face.render(label(car_id), True, col)
        edge = face.render(label(car_id), True, EDGE)
        img = pygame.Surface((fg.get_width() + 2, fg.get_height() + 2), pygame.SRCALPHA)
        for dx, dy in ((0, 1), (2, 1), (1, 0), (1, 2)):
            img.blit(edge, (dx, dy))
        img.blit(fg, (1, 1))
        img.set_alpha(255, pygame.RLEACCEL)
        return img

    def layout(self, topleft: tuple[int, int], cars, players=()):
        """Where each dot and name goes: ({id: (x, y, colour, mine)}, [(id, name's rect)]).
        A name goes right of its dot, else left of it, else (in a bunch) is left out; the
        people's are placed first, so theirs always show."""
        x0, y0 = topleft
        spots = {}
        for mine in (True, False):
            for car_id, colour, z in cars:
                if (car_id in players) == mine:
                    x, y = self.point(z)
                    spots[car_id] = (x0 + round(x), y0 + round(y), colour, mine)
        taken: list[pygame.Rect] = []
        names = []
        for car_id, (px, py, colour, mine) in spots.items():  # people first
            half = self._dots[(colour, mine)][1]
            w, h = self._labels[car_id].get_size()
            for x in (px + half - 1, px - half + 1 - w):
                rect = pygame.Rect(x, py - h // 2, w, h)
                if rect.collidelist(taken) < 0:
                    taken.append(rect)
                    names.append((car_id, rect))
                    break
        return spots, names

    def draw(self, surface: pygame.Surface, topleft: tuple[int, int], cars, players=()) -> None:
        """The outline at topleft, then a dot per car with its name (`layout`): `cars` is
        (id, colour, race distance), the `players`' own dots (bigger, ringed) on top."""
        surface.blit(self.surface, topleft)
        spots, names = self.layout(topleft, cars, players)
        for mine in (False, True):
            for px, py, colour, own in spots.values():
                if own == mine:
                    img, half = self._dots[(colour, own)]
                    surface.blit(img, (px - half, py - half))
        for car_id, rect in names:
            surface.blit(self._labels[car_id], rect)
