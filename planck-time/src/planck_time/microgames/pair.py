"""PAIR!: particles jiggle around their spots, and two of them jiggle in
perfect sync: the same hop, in the same direction, at the same moment. The
stick jumps a cursor to the nearest particle in the pushed direction, and A
picks. Picking either of the two wins; any other particle fails, and so does
never picking.

Every particle hops to a fresh offset several times a second, never the same
one twice in a row, so each is always visibly moving. The others hop to
their own random offsets and at their own distinct rates, so none of them
keeps in step with the pair for more than a moment. Higher levels have 8
particles instead of 6, with bigger, faster hops.
"""

from __future__ import annotations

import math
from collections import deque
from itertools import combinations

import pygame

from planck_time import palette as P
from planck_time.microgames.base import IDLE, H, W, Microgame, PlayerInput, register
from planck_time.pixel import backdrop, blit_center, orb, outlined, result_overlay

COLORS = (P.SKY, P.TEAL, P.VIOLET, P.ORANGE)  # one per game, shared by every particle
HOP = 0.17  # seconds between the pair's hops at level 0
RATES = (0.62, 0.74, 1.3, 1.48, 1.7, 1.92, 0.84)  # the others' hop intervals, x HOP
SIMILAR = 0.25  # the most two different jiggles may coincide
EASE = 0.35  # the part of a hop spent sliding to the new offset
RADIUS = 7
DIRS = [(math.cos(a * math.pi / 4), math.sin(a * math.pi / 4)) for a in range(8)]
THINK = 0.9  # the bot watches before it moves...
BOT_STEP = 0.2  # ...moves at a human pace...
BOT_SETTLE = 0.25  # ...and looks once more before pressing A


@register
class Pair(Microgame):
    VERB = "PAIR!"
    INPUT = "stick+a"
    CAPTION = "Entangled qubits behave as one"

    def __init__(self, seed: int, level: int, duration: float) -> None:
        super().__init__(seed, level, duration)
        cols = 3 if level < 2 else 4
        gap = 192 // cols
        self.spots = []  # each particle's resting place, a loose grid
        for r in range(2):
            for c in range(cols):
                x = W // 2 + (c - (cols - 1) / 2) * gap + self.rng.randint(-4, 4)
                y = 72 + (r - 0.5) * 52 + self.rng.randint(-4, 4)
                self.spots.append((round(x), round(y)))
        n = len(self.spots)
        self.pair = self.rng.sample(range(n), 2)
        # one jiggle per particle; the pair share jiggle 0
        rates = self.rng.sample(RATES, n - 2)
        self.jiggle_of = [0] * n
        others = iter(range(1, n - 1))
        for i in range(n):
            if i not in self.pair:
                self.jiggle_of[i] = next(others)
        self.amp = 5 + level
        hop = HOP / self.speed
        self.jiggles = []  # (interval, phase, offsets)
        for j in range(n - 1):
            interval = hop if j == 0 else hop * rates[j - 1]
            self.jiggles.append(self.jiggle(interval, duration))
        # no two jiggles may look alike for long: redo any that sits on the same
        # offset as another for over a quarter of the first 1.5 s (never the pair's)
        for _ in range(60):
            traces = [[self.at(j, s / 30) for s in range(45)] for j in range(n - 1)]
            alike = [k for j, k in combinations(range(n - 1), 2)
                     if sum(a == b for a, b in zip(traces[j], traces[k])) > len(traces[j]) * SIMILAR]
            if not alike:
                break
            self.jiggles[alike[0]] = self.jiggle(self.jiggles[alike[0]][0], duration)
        self.cursor = self.rng.choice([i for i in range(n) if i not in self.pair])
        self.moved_at = 0.0
        self.picked: int | None = None
        self.color = self.rng.choice(COLORS)
        self.backdrop = P.BACKDROPS[self.rng.randrange(len(P.BACKDROPS))]

    def jiggle(self, interval: float, duration: float) -> tuple:
        """A hop interval, a phase and enough random offsets for the game,
        never the same direction twice in a row."""
        ticks = int((duration + 3) / interval) + 2
        offsets, last = [], -1
        for _ in range(ticks):
            d = self.rng.choice([k for k in range(8) if k != last])
            last = d
            offsets.append((round(DIRS[d][0] * self.amp), round(DIRS[d][1] * self.amp)))
        return interval, self.rng.random(), offsets

    def at(self, j: int, t: float) -> tuple[int, int]:
        """Jiggle j's offset at time t: a quick slide into each new offset."""
        interval, phase, offsets = self.jiggles[j]
        beat = t / interval + phase
        k = int(beat)
        (ax, ay), (bx, by) = offsets[(k - 1) % len(offsets)], offsets[k % len(offsets)]
        e = min(1.0, (beat - k) / EASE)
        return round(ax + (bx - ax) * e), round(ay + (by - ay) * e)

    def offset(self, i: int) -> tuple[int, int]:
        return self.at(self.jiggle_of[i], self.t)

    def nearest(self, i: int, d: tuple[int, int]) -> int:
        """The closest particle in direction d from particle i (i if none)."""
        dl = math.hypot(*d)
        ux, uy = d[0] / dl, d[1] / dl
        best, score = i, math.inf
        x0, y0 = self.spots[i]
        for j, (x, y) in enumerate(self.spots):
            along = (x - x0) * ux + (y - y0) * uy
            side = abs((x - x0) * uy - (y - y0) * ux)
            if j != i and along > 0 and side <= along * 1.5 and along + 2 * side < score:
                best, score = j, along + 2 * side
        return best

    def step(self, dt: float, inp: PlayerInput) -> None:
        if inp.step != (0, 0):
            j = self.nearest(self.cursor, inp.step)
            if j != self.cursor:
                self.cursor = j
                self.moved_at = self.t
        if inp.a:
            self.picked = self.cursor
            if self.cursor in self.pair:
                self.win()
            else:
                self.fail()

    def bot(self) -> PlayerInput:
        since = self.t - self.moved_at
        if self.t < THINK:
            return IDLE
        if self.cursor in self.pair:
            return PlayerInput(a=True, a_held=True) if since >= BOT_SETTLE else IDLE
        if since < BOT_STEP:
            return IDLE
        # breadth first over the cursor's jumps to the nearest of the pair
        first = {self.cursor: None}
        todo = deque([self.cursor])
        while todo:
            i = todo.popleft()
            for d in ((1, 0), (-1, 0), (0, 1), (0, -1), (1, 1), (1, -1), (-1, 1), (-1, -1)):
                j = self.nearest(i, d)
                if j not in first:
                    first[j] = first[i] or d
                    if j in self.pair:
                        return PlayerInput(step=first[j])
                    todo.append(j)
        return IDLE

    # --- drawing ----------------------------------------------------------------------

    def draw(self, surf: pygame.Surface) -> None:
        backdrop(surf, self.backdrop, self.t)
        shadow = P.shade(self.backdrop[0], 0.6)
        for x, y in self.spots:  # each particle's resting spot, so the hops show
            pygame.draw.ellipse(surf, shadow, (x - 9, y + 6, 18, 6))
        where = [(x + dx, y + dy) for (x, y), (dx, dy) in zip(self.spots, map(self.offset, range(len(self.spots))))]
        if self.result is not None:  # the reveal: the pair, linked by a wavy bond
            (ax, ay), (bx, by) = where[self.pair[0]], where[self.pair[1]]
            steps = max(2, round(math.hypot(bx - ax, by - ay) / 4))
            nx, ny = (ay - by) / (steps * 4), (bx - ax) / (steps * 4)
            pts = []
            for s in range(steps + 1):
                k, wave = s / steps, 3 * math.sin(s * 1.6 + self.t * 14)
                pts.append((round(ax + (bx - ax) * k + nx * wave), round(ay + (by - ay) * k + ny * wave)))
            pygame.draw.lines(surf, P.INK, False, pts, 4)
            pygame.draw.lines(surf, P.GOOD if self.result else P.GOLD, False, pts, 2)
        for i, p in enumerate(where):
            won = self.result and i in self.pair
            orb(surf, p, RADIUS, P.GOOD if won else self.color, glow=bool(won))
        if self.result is None:  # the cursor: gold corners round the spot, and an arrow
            x, y = self.spots[self.cursor]
            pulse = round(math.sin(self.t * 10))
            s = 15 + pulse
            for cx, cy in ((-1, -1), (1, -1), (-1, 1), (1, 1)):
                px, py = x + cx * s, y + cy * s
                for color, w in ((P.INK, 5), (P.GOLD, 3)):
                    pygame.draw.line(surf, color, (px, py), (px - cx * 7, py), w)
                    pygame.draw.line(surf, color, (px, py), (px, py - cy * 7), w)
            top = y - s - 4 + pulse
            tri = [(x - 5, top - 6), (x + 5, top - 6), (x, top)]
            pygame.draw.polygon(surf, P.INK, [(a, b + 1) for a, b in tri])
            pygame.draw.polygon(surf, P.GOLD, tri)
        elif self.result is False and self.picked is not None:  # a red X on the wrong pick
            x, y = where[self.picked]
            for d in (-1, 1):
                pygame.draw.line(surf, P.INK, (x - 9, y - 9 * d), (x + 9, y + 9 * d), 7)
                pygame.draw.line(surf, P.BAD, (x - 9, y - 9 * d), (x + 9, y + 9 * d), 3)
        blit_center(surf, outlined("A ON THE TWO IN SYNC", 8, P.WHITE), (W // 2, H - 14))
        result_overlay(surf, self.result, self.since_end, seed=9)
