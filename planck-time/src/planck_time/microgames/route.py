"""ROUTE!: a Superconductor crossover. A small chip of Xmon qubits joined by
couplers. Your pair (yellow) waits at the chip's two sides, its coherence
ring running down with the clock. A rival route (violet), already committed,
cuts across the chip between them. Steer your route from the ringed station
one coupler per stick push, as in Superconductor: pushing back the way you
came takes a step back, and a push off the chip or into your own route just
bumps. Reach the partner to win. Stepping onto the rival route is a
collision, Superconductor's red X, and fails.

The rival route lays itself down first (0.6 s at level 0) and the stick
waits for it. It always stands in the way, so the straight route crashes,
but it never cuts the chip in two: there is always a free way round, and it
is never too long for the time. Higher levels have a bigger chip and a
longer, bendier rival route.
"""

from __future__ import annotations

import math
from collections import deque

import pygame

from planck_time import palette as P
from planck_time.microgames.base import IDLE, H, W, Microgame, PlayerInput, register
from planck_time.pixel import blit_center, outlined, result_overlay

SIZES = ((5, 3), (5, 4), (6, 4), (6, 4))  # columns, rows by level
RIVAL_NODES = (3, 4, 5, 6)  # qubits on the rival route by level
MAX_STEPS = (8, 9, 11, 11)  # the longest free route allowed, by level
BEND = (0.5, 0.4, 0.45, 0.55)  # how often the rival route turns sideways
CENTER = (W // 2, 68)
MAX_SPACING = 40
LAY = 0.6  # seconds the rival route takes to lay itself down at level 0
THINK = 0.3  # the bot looks after the rival is down...
BOT_STEP = 0.2  # ...then steps at a human pace

# Superconductor's colours, on the GBA grid
SPACE = (8, 8, 24)
SUBSTRATE = (16, 16, 32)
SUBSTRATE_EDGE = (40, 48, 88)
PAD = (32, 40, 64)
COUPLER = (48, 64, 96)
QUBIT = (88, 104, 144)
YOURS = (248, 200, 64)  # Superconductor's yellow pair...
RIVAL = (184, 112, 248)  # ...and its violet one
CRASH = (248, 72, 88)


def mix(a, b, k: float) -> tuple[int, int, int]:
    return tuple(round((x + (y - x) * k) / 8) * 8 for x, y in zip(a, b))


def xmon(surf: pygame.Surface, x: float, y: float, size: float, color) -> None:
    """Superconductor's qubit: an Xmon, a plus-shaped transmon."""
    arm, thick = round(size * 0.24), max(3, round(size * 0.09))
    x, y = round(x), round(y)
    surf.fill(color, (x - arm, y - thick // 2, 2 * arm, thick))
    surf.fill(color, (x - thick // 2, y - arm, thick, 2 * arm))


def cross(surf: pygame.Surface, x: float, y: float, k: float, color, width: int) -> None:
    pygame.draw.line(surf, color, (x - k, y - k), (x + k, y + k), width)
    pygame.draw.line(surf, color, (x - k, y + k), (x + k, y - k), width)


def bfs(start, goal, ok) -> list | None:
    """The shortest grid path from start to goal through nodes ok() allows."""
    back = {start: None}
    todo = deque([start])
    while todo:
        n = todo.popleft()
        if n == goal:
            path = []
            while n is not None:
                path.append(n)
                n = back[n]
            return path[::-1]
        c, r = n
        for m in ((c + 1, r), (c - 1, r), (c, r + 1), (c, r - 1)):
            if m not in back and ok(m):
                back[m] = n
                todo.append(m)
    return None


@register
class Route(Microgame):
    VERB = "ROUTE!"
    INPUT = "stick"
    CAPTION = "Two-qubit gates need a free route"

    def __init__(self, seed: int, level: int, duration: float) -> None:
        super().__init__(seed, level, duration)
        lv = min(level, 3)
        self.cols, self.rows = SIZES[lv]
        self.lay = LAY / self.speed
        for _ in range(300):
            if self.layout(lv):
                break
        else:  # a known good one: a wall down the middle with the bottom row free
            mid = self.cols // 2
            self.start, self.partner = (0, 0), (self.cols - 1, 0)
            self.rival = [(mid, r) for r in range(self.rows - 1)]
        self.path = [self.start]
        self.came_from = self.start
        self.moved_at = -1.0
        self.bumped_at = -1.0
        self.bump = (0, 0)
        self.crash: tuple[int, int] | None = None
        self.spacing = min(MAX_SPACING, 196 // (self.cols - 1), 100 // (self.rows - 1))

    def inside(self, n) -> bool:
        return 0 <= n[0] < self.cols and 0 <= n[1] < self.rows

    def layout(self, lv: int) -> bool:
        """Draw a pair and a rival route; True if the rival stands in the pair's way
        but leaves a free route round it that fits the time."""
        rng = self.rng
        self.start = (0, rng.randrange(self.rows))
        self.partner = (self.cols - 1, rng.randrange(self.rows))
        if rng.random() < 0.5:
            self.start, self.partner = self.partner, self.start
        # the rival comes in from the top or the bottom edge, in the middle columns
        top = rng.random() < 0.5
        node = (rng.randrange(1, self.cols - 1), 0 if top else self.rows - 1)
        rival = [node]
        down = 1 if top else -1
        while len(rival) < RIVAL_NODES[lv]:
            c, r = rival[-1]
            moves = [(c, r + down)]
            if rng.random() < BEND[lv]:
                moves = [(c + rng.choice((-1, 1)), r)] + moves
            moves = [m for m in moves if self.inside(m) and 1 <= m[0] <= self.cols - 2 and m not in rival]
            if not moves:
                return False
            rival.append(moves[0])
        if self.start in rival or self.partner in rival:
            return False
        free = bfs(self.start, self.partner, lambda m: self.inside(m) and m not in rival)
        if free is None or len(free) - 1 > MAX_STEPS[lv]:
            return False
        direct = abs(self.start[0] - self.partner[0]) + abs(self.start[1] - self.partner[1])
        if len(free) - 1 <= direct:
            return False  # the rival isn't in the way: some straight route misses it
        self.rival = rival
        return True

    @property
    def laid(self) -> bool:
        return self.t >= self.lay

    # --- the rules ----------------------------------------------------------------------

    def step(self, dt: float, inp: PlayerInput) -> None:
        if not self.laid:
            return
        dx, dy = inp.step
        tries = [d for d in ((dx, 0), (0, dy)) if d != (0, 0)]
        if not tries:
            return
        head = self.path[-1]
        crash = None
        for mx, my in tries:  # a diagonal push takes whichever way is free
            nxt = (head[0] + mx, head[1] + my)
            if len(self.path) >= 2 and nxt == self.path[-2]:  # back the way it came: undo
                self.came_from = self.path.pop()
                self.moved_at = self.t
                return
            if not self.inside(nxt) or nxt in self.path:
                continue
            if nxt in self.rival:
                crash = crash or nxt
                continue
            self.came_from = head
            self.path.append(nxt)
            self.moved_at = self.t
            if nxt == self.partner:
                self.win()
            return
        if crash is not None:  # the only way that push could go is onto the rival route
            self.came_from = head
            self.path.append(crash)
            self.moved_at = self.t
            self.crash = crash
            self.fail()
            return
        self.bumped_at = self.t
        self.bump = tries[0]

    def bot(self) -> PlayerInput:
        if self.t < self.lay + THINK or self.t - self.moved_at < BOT_STEP:
            return IDLE
        head = self.path[-1]
        way = bfs(head, self.partner, lambda m: self.inside(m) and m not in self.rival and m not in self.path)
        if not way or len(way) < 2:
            return IDLE
        return PlayerInput(step=(way[1][0] - head[0], way[1][1] - head[1]))

    # --- drawing ----------------------------------------------------------------------

    def screen(self, n) -> tuple[float, float]:
        c, r = n
        return (CENTER[0] + (c - (self.cols - 1) / 2) * self.spacing,
                CENTER[1] + (r - (self.rows - 1) / 2) * self.spacing)

    def edges(self):
        for r in range(self.rows):
            for c in range(self.cols):
                if c + 1 < self.cols:
                    yield (c, r), (c + 1, r)
                if r + 1 < self.rows:
                    yield (c, r), (c, r + 1)

    def committed(self, surf, nodes, color, upto: float | None = None) -> None:
        """A committed route: a broad dim band with a bright core, as Superconductor draws it."""
        pts = [self.screen(n) for n in nodes]
        if upto is not None:  # still being laid: only the first `upto` couplers
            whole, part = int(upto), upto - int(upto)
            pts = pts[:whole + 1] + ([] if whole + 1 >= len(pts) else
                                    [(pts[whole][0] + (pts[whole + 1][0] - pts[whole][0]) * part,
                                      pts[whole][1] + (pts[whole + 1][1] - pts[whole][1]) * part)])
        if len(pts) < 2:
            return
        pygame.draw.lines(surf, mix(color, SUBSTRATE, 0.55), False, pts, 7)
        pygame.draw.lines(surf, color, False, pts, 3)

    def draw(self, surf: pygame.Surface) -> None:
        surf.fill(SPACE)
        sp = self.spacing
        x0, y0 = self.screen((0, 0))
        x1, y1 = self.screen((self.cols - 1, self.rows - 1))
        chip = pygame.Rect(round(x0) - 16, round(y0) - 16, round(x1 - x0) + 33, round(y1 - y0) + 33)
        crashed = self.crash is not None
        hurt = crashed and self.since_end < 0.8 and int(self.since_end * 10) % 2 == 0
        pygame.draw.rect(surf, SUBSTRATE, chip, border_radius=8)
        pygame.draw.rect(surf, CRASH if hurt else SUBSTRATE_EDGE, chip, 2, border_radius=8)
        for i in range(1, 8):  # the bond pads round the rim
            for bx, by in ((chip.x + chip.w * i / 8, chip.y + 5), (chip.x + chip.w * i / 8, chip.bottom - 5),
                           (chip.x + 5, chip.y + chip.h * i / 8), (chip.right - 5, chip.y + chip.h * i / 8)):
                surf.fill(PAD, (round(bx) - 2, round(by) - 2, 4, 4))
        for a, b in self.edges():
            pygame.draw.line(surf, COUPLER, self.screen(a), self.screen(b), 2)

        # the rival route, laying itself down at the start
        laid = min(1.0, self.t / self.lay) * (len(self.rival) - 1)
        self.committed(surf, self.rival, RIVAL, None if self.laid else laid)
        # your route: marching dashes while it's drawn, solid once committed
        if self.result is True:
            self.committed(surf, self.path, YOURS)
        else:
            col = mix(YOURS, P.WHITE, 0.35)
            for a, b in zip(self.path, self.path[1:]):
                (ax, ay), (bx, by) = self.screen(a), self.screen(b)
                n = 6
                for k in range(n):
                    if (k + int(self.t * 12)) % 2:
                        continue
                    f0, f1 = k / n, (k + 1) / n
                    pygame.draw.line(surf, col, (ax + (bx - ax) * f0, ay + (by - ay) * f0),
                                     (ax + (bx - ax) * f1, ay + (by - ay) * f1), 3)

        # the qubits
        ends = {self.rival[0], self.rival[-1]}
        for r in range(self.rows):
            for c in range(self.cols):
                n = (c, r)
                x, y = self.screen(n)
                if n in (self.start, self.partner):
                    pulse = 0.5 + 0.5 * math.sin(self.t * 5 + c)
                    pygame.draw.circle(surf, mix(SUBSTRATE, YOURS, 0.3 + 0.2 * pulse), (round(x), round(y)),
                                       round(sp * 0.42))
                    xmon(surf, x, y, sp * 1.1, mix(YOURS, P.WHITE, 0.2 * pulse))
                    self.coherence(surf, x, y)
                elif n in self.rival and (self.laid or self.rival.index(n) <= laid):
                    xmon(surf, x, y, sp * (1.05 if n in ends else 0.95), RIVAL if n in ends else mix(RIVAL, QUBIT, 0.45))
                else:
                    xmon(surf, x, y, sp, QUBIT)

        # you: a rounded square on your station, a smaller one on the route's head
        # (sliding along a step, shaking after a bump)
        k = min(1.0, (self.t - self.moved_at) / 0.08)
        (fx, fy), (tx, ty) = self.screen(self.came_from), self.screen(self.path[-1])
        hx, hy = fx + (tx - fx) * k, fy + (ty - fy) * k
        if self.t - self.bumped_at < 0.15:
            wob = 3 * math.sin((self.t - self.bumped_at) * 60)
            hx, hy = hx + self.bump[0] * wob, hy + self.bump[1] * wob
        at_start = len(self.path) == 1
        sx, sy = (hx, hy) if at_start else self.screen(self.start)
        size = round(sp * 0.7 * (1 + 0.08 * math.sin(self.t * 6)))
        box = pygame.Rect(0, 0, size, size)
        box.center = (round(sx), round(sy))
        pygame.draw.rect(surf, P.WHITE, box, 2, border_radius=5)
        if not at_start and not crashed:
            box = pygame.Rect(0, 0, round(sp * 0.45), round(sp * 0.45))
            box.center = (round(hx), round(hy))
            pygame.draw.rect(surf, P.WHITE, box, 2, border_radius=4)
        # the target: spinning arcs, blinking
        if self.result is None and int(self.t * 3) % 2 == 0:
            tx, ty = self.screen(self.partner)
            r = sp * 0.42
            rect = pygame.Rect(0, 0, round(2 * r), round(2 * r))
            rect.center = (round(tx), round(ty))
            for k in range(4):
                a = k * math.pi / 2 + self.t * 2
                pygame.draw.arc(surf, P.WHITE, rect, a, a + 0.7, 2)
        if self.result is True:  # the qubit travels the route and the gate fires
            k = min(1.0, self.since_end / 0.4) * (len(self.path) - 1)
            i = min(int(k), len(self.path) - 2)
            (ax, ay), (bx, by) = self.screen(self.path[i]), self.screen(self.path[i + 1])
            qx, qy = ax + (bx - ax) * (k - i), ay + (by - ay) * (k - i)
            pygame.draw.circle(surf, mix(YOURS, P.WHITE, 0.5), (round(qx), round(qy)), 5)
            pygame.draw.circle(surf, P.WHITE, (round(qx), round(qy)), 5, 1)
        if crashed:  # Superconductor's collision: a big red X in a ring
            cx, cy = self.screen(self.crash)
            cross(surf, cx, cy, sp * 0.22, P.INK, 7)
            cross(surf, cx, cy, sp * 0.22, CRASH, 4)
            pygame.draw.circle(surf, CRASH, (round(cx), round(cy)), round(sp * 0.36), 2)
        blit_center(surf, outlined("JOIN THE PAIR, NO CROSSING", 8, P.WHITE), (W // 2, H - 9))
        result_overlay(surf, self.result, self.since_end, seed=17)

    def coherence(self, surf: pygame.Surface, x: float, y: float) -> None:
        """The pair's coherence ring: it runs down with the time left."""
        frac = max(0.0, 1 - self.t / self.duration) if self.result is None else 1.0
        r = self.spacing * 0.36
        rect = pygame.Rect(0, 0, round(2 * r), round(2 * r))
        rect.center = (round(x), round(y))
        pygame.draw.arc(surf, mix(SUBSTRATE, YOURS, 0.25), rect, 0, 2 * math.pi, 1)
        urgent = frac < 0.3 and int(self.t * 7) % 2 == 0
        if frac > 0.01:
            pygame.draw.arc(surf, CRASH if urgent else YOURS, rect, math.pi / 2, math.pi / 2 + 2 * math.pi * frac, 2)
