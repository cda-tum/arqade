"""CONNECT!: a chip of qubits on a grid, neighbours joined by couplers. Your
qubit (gold) steps along a coupler with each stick push; a push where there
is no working coupler just bumps. Win once you sit next to your partner
(pink), joined to it by one working coupler: then a two-qubit gate can run.

The partner is always reachable and never next to you at the start, so
doing nothing loses. Higher levels have a bigger chip, a farther partner,
and broken couplers (red, with a gap) to route around. Breaking one never
cuts the chip in two.
"""

from __future__ import annotations

import math
from collections import deque

import pygame

from planck_time import palette as P
from planck_time.microgames.base import IDLE, H, W, Microgame, PlayerInput, register
from planck_time.pixel import backdrop, blit_center, orb, outlined, result_overlay

SIZES = ((3, 3), (4, 3), (4, 4), (5, 4))  # columns, rows by level
BROKEN = (0, 2, 3, 5)  # broken couplers by level
MIN_DIST = (2, 3, 4, 4)  # couplers between you and the partner at the start
CENTER = (W // 2, 70)
MAX_SPACING = 56
SLIDE = 0.08  # seconds a step's slide takes on screen
THINK = 0.4  # the bot looks before it moves...
BOT_STEP = 0.2  # ...then steps at a human pace


def edge(a, b) -> tuple:
    return (a, b) if a < b else (b, a)


@register
class Connect(Microgame):
    VERB = "CONNECT!"
    INPUT = "stick"
    CAPTION = "Two-qubit gates need neighbours: compilers add SWAPs"

    def __init__(self, seed: int, level: int, duration: float) -> None:
        super().__init__(seed, level, duration)
        lv = min(level, 3)
        self.cols, self.rows = SIZES[lv]
        self.nodes = [(c, r) for r in range(self.rows) for c in range(self.cols)]
        self.working = set()
        for c, r in self.nodes:
            if c + 1 < self.cols:
                self.working.add(edge((c, r), (c + 1, r)))
            if r + 1 < self.rows:
                self.working.add(edge((c, r), (c, r + 1)))
        self.broken = set()
        for _ in range(BROKEN[lv] * 4):  # a few tries each
            if len(self.broken) == BROKEN[lv]:
                break
            e = self.rng.choice(sorted(self.working))
            self.working.discard(e)
            if len(self.distances(self.nodes[0])) == len(self.nodes):
                self.broken.add(e)
            else:
                self.working.add(e)  # that one would cut the chip in two
        for _ in range(20):
            self.pos = self.rng.choice(self.nodes)
            dist = self.distances(self.pos)
            far = [n for n in self.nodes if dist[n] >= MIN_DIST[lv]]
            if far:
                self.partner = self.rng.choice(far)
                break
        else:
            self.partner = max(self.nodes, key=lambda n: dist[n])
        self.came_from = self.pos
        self.moved_at = -1.0
        self.bumped_at = -1.0
        self.bump = (0, 0)
        self.spacing = min(MAX_SPACING, 200 // (self.cols - 1), 96 // (self.rows - 1))
        self.backdrop = P.BACKDROPS[self.rng.randrange(len(P.BACKDROPS))]

    def linked(self, a, b) -> bool:
        return edge(a, b) in self.working

    def neighbours(self, n) -> list:
        c, r = n
        near = ((c + 1, r), (c - 1, r), (c, r + 1), (c, r - 1))
        return [m for m in near if self.linked(n, m)]

    def distances(self, start) -> dict:
        """Couplers from `start` to every node it can reach (breadth first)."""
        dist = {start: 0}
        todo = deque([start])
        while todo:
            n = todo.popleft()
            for m in self.neighbours(n):
                if m not in dist:
                    dist[m] = dist[n] + 1
                    todo.append(m)
        return dist

    def step(self, dt: float, inp: PlayerInput) -> None:
        dx, dy = inp.step
        tries = [d for d in ((dx, 0), (0, dy)) if d != (0, 0)]
        if not tries:
            return
        for mx, my in tries:  # a diagonal push takes whichever way has a coupler
            nxt = (self.pos[0] + mx, self.pos[1] + my)
            if self.linked(self.pos, nxt):
                self.came_from, self.pos = self.pos, nxt
                self.moved_at = self.t
                break
        else:
            self.bumped_at = self.t
            self.bump = tries[0]
        if self.linked(self.pos, self.partner):
            self.win()

    def bot(self) -> PlayerInput:
        if self.t < THINK or self.t - self.moved_at < BOT_STEP:
            return IDLE
        # breadth first towards any node next to the partner, never through it
        back = {self.pos: None}
        todo = deque([self.pos])
        while todo:
            n = todo.popleft()
            if self.linked(n, self.partner):
                while back[n] != self.pos and back[n] is not None:
                    n = back[n]
                return PlayerInput(step=(n[0] - self.pos[0], n[1] - self.pos[1]))
            for m in self.neighbours(n):
                if m not in back and m != self.partner:
                    back[m] = n
                    todo.append(m)
        return IDLE

    # --- drawing ----------------------------------------------------------------------

    def screen(self, n) -> tuple[float, float]:
        c, r = n
        return (CENTER[0] + (c - (self.cols - 1) / 2) * self.spacing,
                CENTER[1] + (r - (self.rows - 1) / 2) * self.spacing)

    def coupler(self, surf, a, b, color, width: int = 3) -> None:
        pa, pb = self.screen(a), self.screen(b)
        pygame.draw.line(surf, P.INK, pa, pb, width + 2)
        pygame.draw.line(surf, color, pa, pb, width)

    def draw(self, surf: pygame.Surface) -> None:
        backdrop(surf, self.backdrop, self.t)
        # the chip: a dark die with pins along its edges
        x0, y0 = self.screen((0, 0))
        x1, y1 = self.screen((self.cols - 1, self.rows - 1))
        die = pygame.Rect(round(x0) - 16, round(y0) - 16, round(x1 - x0) + 33, round(y1 - y0) + 33)
        for x in range(die.x + 8, die.right - 6, 10):
            surf.fill(P.INK, (x - 1, die.y - 5, 6, die.h + 10))
            surf.fill(P.MIST, (x, die.y - 4, 4, die.h + 8))
        for y in range(die.y + 8, die.bottom - 6, 10):
            surf.fill(P.INK, (die.x - 5, y - 1, die.w + 10, 6))
            surf.fill(P.MIST, (die.x - 4, y, die.w + 8, 4))
        pygame.draw.rect(surf, P.INK, die.inflate(4, 4), border_radius=5)
        pygame.draw.rect(surf, P.NIGHT, die, border_radius=4)
        surf.fill(P.SLATE, (die.x + 4, die.y + 2, die.w - 8, 1))

        pulse = int(self.t * 4) % 2
        for a, b in sorted(self.working):
            hot = self.partner in (a, b)
            color = P.PINK if hot and pulse else (P.lighten(P.PINK, 0.4) if hot else P.MIST)
            self.coupler(surf, a, b, color)
        for a, b in sorted(self.broken):  # two red stubs with a gap between
            (ax, ay), (bx, by) = self.screen(a), self.screen(b)
            for (sx, sy), (ex, ey) in (((ax, ay), (bx, by)), ((bx, by), (ax, ay))):
                mid = (sx + (ex - sx) * 0.34, sy + (ey - sy) * 0.34)
                pygame.draw.line(surf, P.INK, (sx, sy), mid, 5)
                pygame.draw.line(surf, P.BAD, (sx, sy), mid, 3)
            mx, my = (ax + bx) / 2, (ay + by) / 2
            if (int(self.t * 8) + a[0] + b[1]) % 3:  # a crackling spark in the gap
                surf.fill(P.GOLD, (round(mx) - 1, round(my) - 1, 2, 2))
        if self.result:  # the gate runs: the coupler to the partner lights up
            self.coupler(surf, self.pos, self.partner, P.GOOD, 5)

        for n in self.nodes:
            if n not in (self.pos, self.partner):
                orb(surf, self.screen(n), 4, P.SKY)
        ring = 10 + round(2 * math.sin(self.t * 9))
        px, py = self.screen(self.partner)
        pygame.draw.circle(surf, P.INK, (round(px), round(py)), ring + 1, 3)
        pygame.draw.circle(surf, P.PINK, (round(px), round(py)), ring, 1)
        orb(surf, (px, py), 6, P.PINK, glow=bool(self.result))

        # you: sliding between nodes, shaking after a bump
        k = min(1.0, (self.t - self.moved_at) / SLIDE)
        (fx, fy), (tx, ty) = self.screen(self.came_from), self.screen(self.pos)
        x, y = fx + (tx - fx) * k, fy + (ty - fy) * k
        if self.t - self.bumped_at < 0.15:
            wob = 3 * math.sin((self.t - self.bumped_at) * 60)
            x, y = x + self.bump[0] * wob, y + self.bump[1] * wob
        if self.result is False:
            orb(surf, (x, y), 6, P.SLATE)
        else:
            orb(surf, (x, y), 6, P.GOLD, glow=True)
        blit_center(surf, outlined("GO NEXT TO THE PINK ONE", 8, P.WHITE), (W // 2, H - 14))
        result_overlay(surf, self.result, self.since_end, seed=5)
