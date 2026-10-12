"""PAIR!: particles sway around their spots, and two of them sway in
perfect sync: the same loop, at the same moment. The stick jumps a cursor to
the nearest particle in the pushed direction, and A picks. Picking either of
the two wins; any other particle fails, and so does never picking.

Every particle traces a smooth loop (a little Lissajous figure). The pair
share one; each of the others either runs at a clearly different tempo or a
quarter turn or more out of step, so none of them ever looks nearly in sync
-- moving together is something eyes pick out at once, where comparing
random hops is not. Levels 0-1 have 4 particles, then 6, and 8 from level 4.
"""

from __future__ import annotations

import math
from collections import deque

import pygame

from planck_time import palette as P
from planck_time.microgames.base import IDLE, H, W, Microgame, PlayerInput, register
from planck_time.pixel import backdrop, blit_center, orb, outlined, result_overlay

COLORS = (P.SKY, P.TEAL, P.VIOLET, P.ORANGE)  # one per game, shared by every particle
OMEGA = 6.0  # radians per second of the pair's loop at level 0 (about 1 s a loop)
AMP = 12  # px of sway at level 0
TEMPOS = (1.0, 1.0, 1.0, 0.6, 1.65)  # the decoys' tempo, x the pair's
PHASES = (0.0, 0.5 * math.pi, math.pi, 1.5 * math.pi)  # out of step by a quarter turn or more
SHAPES = ((1.0, 2.0), (2.0, 1.0), (1.0, 1.0))  # x and y frequency ratios of a loop
RADIUS = 8
TRAIL = (0.05, 0.1, 0.15, 0.2)  # seconds back, for the fading trail behind each particle
THINK = 0.9  # the bot watches before it moves...
BOT_STEP = 0.2  # ...moves at a human pace...
BOT_SETTLE = 0.25  # ...and looks once more before pressing A


@register
class Pair(Microgame):
    VERB = "PAIR!"
    INPUT = "stick+a"
    STEPS = True
    CAPTION = "Entangled qubits behave as one"

    def __init__(self, seed: int, level: int, duration: float) -> None:
        super().__init__(seed, level, duration)
        cols = 2 if level < 2 else 3 if level < 4 else 4
        gap = 192 // cols if cols > 2 else 80
        self.spots = []  # each particle's resting place, a loose grid
        for r in range(2):
            for c in range(cols):
                x = W // 2 + (c - (cols - 1) / 2) * gap + self.rng.randint(-4, 4)
                y = 72 + (r - 0.5) * 56 + self.rng.randint(-4, 4)
                self.spots.append((round(x), round(y)))
        n = len(self.spots)
        self.pair = self.rng.sample(range(n), 2)
        self.amp = min(AMP + level // 2, 14) if level < 4 else 11  # 8 particles sit closer together
        # a loop is (tempo, phase, shape); the pair share one, and every decoy
        # gets its own, never the pair's tempo *and* phase
        shape = self.rng.choice(SHAPES)
        phase = self.rng.choice(PHASES)
        pair_loop = (1.0, phase, shape)
        options = [(t, p, shape) for t in sorted(set(TEMPOS)) for p in PHASES if (t, p) != (1.0, phase)]
        self.rng.shuffle(options)
        self.loops = [pair_loop if i in self.pair else options.pop() for i in range(n)]
        self.omega = OMEGA * self.speed
        self.cursor = self.rng.choice([i for i in range(n) if i not in self.pair])
        self.moved_at = 0.0
        self.picked: int | None = None
        self.color = self.rng.choice(COLORS)
        self.backdrop = P.BACKDROPS[self.rng.randrange(len(P.BACKDROPS))]

    def offset(self, i: int, t: float | None = None) -> tuple[int, int]:
        tempo, phase, (fx, fy) = self.loops[i]
        a = self.omega * tempo * (self.t if t is None else t) + phase
        return round(self.amp * math.sin(fx * a)), round(self.amp * 0.8 * math.sin(fy * a + math.pi / 2))

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
        if self.result is None:  # fading trails: the pair's two are the same shape
            for k, back in enumerate(TRAIL):
                color = P.lighten(self.color, 0.25) if k < 2 else P.shade(self.color, 0.8)
                for i, (x, y) in enumerate(self.spots):
                    dx, dy = self.offset(i, self.t - back)
                    size = 4 - k
                    surf.fill(color, (x + dx - size // 2, y + dy - size // 2, size, size))
        for i, p in enumerate(where):
            won = self.result and i in self.pair
            orb(surf, p, RADIUS, P.GOOD if won else self.color, glow=bool(won))
        if self.result is None:  # the cursor: gold corners round the particle, and an arrow
            x, y = where[self.cursor]
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
