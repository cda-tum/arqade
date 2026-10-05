"""MERGE! (lattice surgery on the surface code): two surface-code patches, drawn in
the convention of Litinski's "A Game of Surface Codes". Each is a distance-3
rotated surface code: a small square checkerboarded with X and Z plaquettes, and
every edge is an X edge (dashed, red, an X beside it) or a Z edge (solid, blue, a
Z beside it). Opposite edges have the same type, neighbouring edges differ.

The left patch is fixed; the right one is yours. A turns it a quarter, which swaps
which edge type faces left; pushing the stick left slides it in to merge. In this
convention an edge's type is the logical operator running along it, and merging
two patches along their X edges measures the joint operator XX, along their Z
edges ZZ: that is how lattice surgery builds logical two-qubit operations. Merging
along edges of different types isn't a merge at all: the patches bounce apart.

From the second appearance on there are two fixed patches, upper and lower, with
different edge types facing you, and an order at the top: MEASURE XX or MEASURE
ZZ. The stick, up and down, picks the lane. Exactly one lane and turn wins
(tests/test_code_microgames.py).
"""

from __future__ import annotations

import math

import pygame

from planck_time import palette as P
from planck_time.microgames.base import IDLE, H, W, Microgame, PlayerInput, register
from planck_time.pixel import backdrop, blit_center, outlined, result_overlay

CELL = 22                       # a plaquette, px: a distance-3 patch is 2 x 2 of them
SQUARE = 2 * CELL
PAD = 10                        # room round the square for the edge letters
FIXED_X = 64                    # the fixed patches' centres
START_X = 186                   # where your patch floats
GAP = 10                        # the gap a merge fills with new plaquettes
TARGET_X = FIXED_X + SQUARE + GAP     # your patch's centre once pushed in
LANES = {1: (72,), 2: (42, 112)}
READY = 0.6                     # input counts from here (level 0): the first decision's moment
SPIN = 0.25                     # a quarter turn, s (level 0)
SLIDE = 0.3                     # pushing in, s (level 0)
LANE_MOVE = 0.12                # changing lane, s
THINK = 0.25                    # the bot looks before it moves...
BOT_STEP = 0.15                 # ...and waits this long between moves
EDGE_COLOUR = {"X": P.GATE["X"], "Z": P.GATE["Z"]}


def edges(rot: int) -> dict[str, str]:
    """The edge types of a patch turned `rot` quarters: opposite edges match, neighbours differ."""
    side, top = ("X", "Z") if rot % 2 == 0 else ("Z", "X")
    return {"left": side, "right": side, "top": top, "bottom": top}


_CACHE: dict = {}


def patch_image(rot: int) -> pygame.Surface:
    """A patch: the checkerboard of X (red) and Z (blue) plaquettes, the data qubits at the
    lattice points, and the edges, X dashed and red, Z solid and blue, each with its letter."""
    key = ("patch", rot % 2)
    if key not in _CACHE:
        size = SQUARE + 2 * PAD
        s = pygame.Surface((size, size), pygame.SRCALPHA)
        o = PAD
        for i in range(2):
            for j in range(2):
                kind = "X" if (i + j + rot) % 2 == 0 else "Z"
                s.fill(P.lighten(EDGE_COLOUR[kind], 0.55), (o + i * CELL, o + j * CELL, CELL, CELL))
        e = edges(rot)
        lines = {"top": ((o, o), (o + SQUARE, o)), "bottom": ((o, o + SQUARE), (o + SQUARE, o + SQUARE)),
                 "left": ((o, o), (o, o + SQUARE)), "right": ((o + SQUARE, o), (o + SQUARE, o + SQUARE))}
        for side, (a, b) in lines.items():
            kind = e[side]
            colour = EDGE_COLOUR[kind]
            if kind == "Z":                 # solid
                pygame.draw.line(s, P.INK, a, b, 5)
                pygame.draw.line(s, colour, a, b, 3)
            else:                           # dashed
                n = 6
                for k in range(0, n, 2):
                    p = (a[0] + (b[0] - a[0]) * k / n, a[1] + (b[1] - a[1]) * k / n)
                    q = (a[0] + (b[0] - a[0]) * (k + 1) / n, a[1] + (b[1] - a[1]) * (k + 1) / n)
                    pygame.draw.line(s, P.INK, p, q, 5)
                    pygame.draw.line(s, colour, p, q, 3)
            mid = ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2)
            out = {"top": (0, -6), "bottom": (0, 6), "left": (-6, 0), "right": (6, 0)}[side]
            blit_center(s, outlined(kind, 8, colour, shadow=False), (mid[0] + out[0], mid[1] + out[1]))
        for i in range(3):                  # the data qubits
            for j in range(3):
                x, y = o + i * CELL, o + j * CELL
                s.fill(P.INK, (x - 2, y - 2, 5, 5))
                s.fill(P.WHITE, (x - 1, y - 1, 3, 3))
        _CACHE[key] = s
    return _CACHE[key]


def smooth(k: float) -> float:
    k = max(0.0, min(1.0, k))
    return k * k * (3 - 2 * k)


@register
class Merge(Microgame):
    VERB = "MERGE!"
    INPUT = "stick+a"
    CAPTION = "Code patches merge along matching edges"

    def __init__(self, seed: int, level: int, duration: float) -> None:
        super().__init__(seed, level, duration)
        if self.appearance == 0:
            self.fixed = [self.rng.choice("XZ")]
            self.order: str | None = None
        else:
            first = self.rng.choice("XZ")
            self.fixed = [first, "Z" if first == "X" else "X"]
            self.order = self.rng.choice("XZ")
        self.lane = self.rng.randrange(len(self.fixed))
        self.rot = self.rng.randrange(2)
        self.ready = READY / self.speed
        self.spin = SPIN / self.speed
        self.slide = SLIDE / self.speed
        self.spins = 0                  # quarter turns started
        self.spin_at: float | None = None
        self.lane_from = self.lane
        self.lane_at = -1.0
        self.pushed = False
        self.push_at = 0.0
        self.moved_at = 0.0
        self.backdrop = P.BACKDROPS[self.rng.randrange(len(P.BACKDROPS))]

    # --- the rules -----------------------------------------------------------------------

    def facing(self, rot: int) -> str:
        return edges(rot)["left"]

    def wins(self, rot: int, lane: int) -> bool:
        """Would pushing in with this turn into this lane win?"""
        side = self.facing(rot)
        return side == self.fixed[lane] and (self.order is None or side == self.order)

    def label(self) -> str:
        """The joint measurement a merge in the current lane makes: XX or ZZ."""
        return self.fixed[self.lane] * 2

    @property
    def spinning(self) -> bool:
        return self.spin_at is not None

    def step(self, dt: float, inp: PlayerInput) -> None:
        if self.spin_at is not None and self.t - self.spin_at >= self.spin:
            self.rot = (self.rot + 1) % 2       # the quarter turn completes
            self.spin_at = None
        if self.pushed:
            if self.t - self.push_at >= self.slide:
                if self.wins(self.rot, self.lane):
                    self.win()
                else:
                    self.fail()
            return
        if self.t < self.ready:
            return
        if inp.a and not self.spinning:
            self.spins += 1
            self.spin_at = self.t
            self.moved_at = self.t
        if inp.step[1] and len(self.fixed) > 1 and not self.spinning:
            to = max(0, min(len(self.fixed) - 1, self.lane + inp.step[1]))
            if to != self.lane:
                self.lane_from, self.lane, self.lane_at = self.lane, to, self.t
                self.moved_at = self.t
        if inp.step[0] < 0 and not self.spinning:
            self.pushed = True
            self.push_at = self.t

    def bot(self) -> PlayerInput:
        if self.t < self.ready + THINK or self.pushed or self.spinning:
            return IDLE
        if self.t - self.moved_at < BOT_STEP:
            return IDLE
        lane = next(lane for lane in range(len(self.fixed))
                    if any(self.wins(rot, lane) for rot in (0, 1)))
        if lane != self.lane:
            return PlayerInput(step=(0, 1 if lane > self.lane else -1))
        if not self.wins(self.rot, self.lane):
            return PlayerInput(a=True, a_held=True)
        return PlayerInput(step=(-1, 0))

    # --- drawing -------------------------------------------------------------------------

    def your_pos(self) -> tuple[float, float]:
        lanes = LANES[len(self.fixed)]
        k = smooth((self.t - self.lane_at) / LANE_MOVE) if self.lane_at >= 0 else 1.0
        y = lanes[self.lane_from] + (lanes[self.lane] - lanes[self.lane_from]) * k
        x = START_X
        if self.pushed:
            k = smooth((self.t - self.push_at) / self.slide)
            x = START_X + (TARGET_X - START_X) * k
            if self.result is False:        # the bounce: back out again
                x = TARGET_X + (START_X - TARGET_X) * smooth(self.since_end / 0.3) * 0.6
        return x, y

    def draw(self, surf: pygame.Surface) -> None:
        backdrop(surf, self.backdrop, self.t)
        lanes = LANES[len(self.fixed)]
        for lane, kind in enumerate(self.fixed):
            rot = 0 if kind == "X" else 1           # a fixed patch shows `kind` facing right
            blit_center(surf, patch_image(rot), (FIXED_X, lanes[lane]))
        won = self.result is True
        x, y = self.your_pos()
        img = patch_image(self.rot)
        if self.spinning:
            k = smooth((self.t - self.spin_at) / self.spin)
            img = pygame.transform.rotate(img, -90 * k)
        if self.result is None and len(self.fixed) > 1:    # your lane, marked by its arrows
            for d in (-1, 1):
                ay = round(y + d * (SQUARE / 2 + 12))
                pygame.draw.polygon(surf, P.GOLD, [(x - 4, ay - 2 * d), (x + 4, ay - 2 * d), (x, ay + 2 * d)])
        blit_center(surf, img, (x, y))
        if won:                 # over both patches' seam edges, which aren't edges any more
            self._bridge(surf, lanes[self.lane])
            # the joint measurement, right of the merged patch, where yours floated
            blit_center(surf, outlined(self.label(), 16, P.GOLD), (TARGET_X + SQUARE // 2 + 30, lanes[self.lane]))
        elif self.result is False and self.pushed:
            self._cross(surf, ((FIXED_X + SQUARE / 2 + x - SQUARE / 2) / 2, lanes[self.lane]))
        if self.order is not None:
            self._order(surf)
        if self.result is False:
            hint = "THOSE EDGES DON'T MATCH!" if self.pushed else "TOO SLOW!"
            if self.pushed and self.order and self.facing(self.rot) == self.fixed[self.lane]:
                hint = "THAT MEASURED THE WRONG ONE!"
        elif won:
            hint = "MERGED: " + self.label() + " MEASURED"
        elif self.order is not None:
            hint = "LANE, A TURNS, < PUSHES IN"
        else:
            hint = "A TURNS, < PUSHES IN"
        blit_center(surf, outlined(hint, 8, P.WHITE), (W // 2, H - 9))
        result_overlay(surf, self.result, self.since_end, seed=31)

    def _bridge(self, surf: pygame.Surface, y: float) -> None:
        """The merge: the gap fills with new plaquettes (hiding the two seam edges and their
        letters, which aren't edges any more), and the joined patch glows."""
        left = FIXED_X + SQUARE // 2 - 1
        top = round(y - SQUARE / 2)
        for j in range(2):
            kind = "X" if j % 2 == 0 else "Z"
            surf.fill(P.lighten(EDGE_COLOUR[kind], 0.55), (left, top + j * CELL, GAP + 3, CELL))
        glow = pygame.Rect(FIXED_X - SQUARE // 2 - 4, top - 4, TARGET_X - FIXED_X + SQUARE + 8, SQUARE + 8)
        k = 0.5 + 0.5 * math.sin(self.since_end * 12)
        pygame.draw.rect(surf, P.lighten(P.GOLD, k * 0.5), glow, 2, border_radius=4)

    def _order(self, surf: pygame.Surface) -> None:
        parts = (("MEASURE ", P.WHITE), (self.order * 2, EDGE_COLOUR[self.order]))
        imgs = [outlined(t, 8, c) for t, c in parts]
        x = W // 2 - sum(i.get_width() for i in imgs) // 2
        for img in imgs:
            surf.blit(img, (x, 4))
            x += img.get_width()

    @staticmethod
    def _cross(surf: pygame.Surface, centre) -> None:
        x, y = round(centre[0]), round(centre[1])
        for d in (-1, 1):
            pygame.draw.line(surf, P.INK, (x - 6, y - 6 * d), (x + 6, y + 6 * d), 5)
            pygame.draw.line(surf, P.BAD, (x - 6, y - 6 * d), (x + 6, y + 6 * d), 3)
