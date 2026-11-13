"""MERGE! (lattice surgery on the surface code): two surface-code patches, drawn as in
Litinski's "A Game of Surface Codes" (arXiv:1808.02892, Fig. 37): a distance-5 patch
with a physical qubit on every vertex, bright faces for Z stabilisers and dark faces
for X stabilisers, and the weight-2 boundary stabilisers as half-moons. Every edge
is an X edge (dashed, red, an X beside it) or a Z edge (solid, blue, a Z beside it):
"each of the two dashed (solid) edges represent the qubit's X (Z) operator", the
product of X (Z) along it. Opposite edges have the same type, neighbouring edges
differ. For that, the half-moons on an X edge are Z stabilisers and those on a Z
edge X stabilisers: the logical X string along an X edge ends on the Z edges, where
it must commute with the boundary stabilisers.

The left patch is fixed; the right one is yours. A turns it a quarter, which swaps
which edge type faces left; pushing the stick left slides it in to merge. In this
convention an edge's type is the logical operator running along it, and merging
two patches along their X edges measures the joint operator XX, along their Z
edges ZZ: that is how lattice surgery builds logical two-qubit operations. The merge
fills the seam with new faces, and the product of the new stabilisers of the measured
type (they glow) is the measurement's outcome, as in Litinski's Fig. 40a. Merging
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
from planck_time.pixel import backdrop, blit_center, control_hint, outlined, result_overlay

D = 5                           # the code distance: D x D qubits, (D-1) x (D-1) faces
FACES = D - 1
CELL = 9                        # a face, px
SQUARE = FACES * CELL
MOON = CELL // 2                # a boundary half-moon's radius
PAD = 14                        # room round the square for the half-moons and the edge letters
FIXED_X = 64                    # the fixed patches' centres
START_X = 186                   # where your patch floats
GAP = CELL                      # the seam a merge fills with one column of new faces
TARGET_X = FIXED_X + SQUARE + GAP     # your patch's centre once pushed in
LANES = {1: (72,), 2: (46, 112)}
READY = 0.6                     # input counts from here (level 0): the first decision's moment
SPIN = 0.25                     # a quarter turn, s (level 0)
SLIDE = 0.3                     # pushing in, s (level 0)
LANE_MOVE = 0.12                # changing lane, s
THINK = 0.25                    # the bot looks before it moves...
BOT_STEP = 0.15                 # ...and waits this long between moves
EDGE_COLOUR = {"X": P.GATE["X"], "Z": P.GATE["Z"]}
# Your patch's checkerboard is shifted by one against the fixed ones', so that when the two
# meet along matching edges the faces alternate right across the seam.
YOUR_PHASE = (FACES - 1) % 2
FACE = {"Z": P.CREAM, "X": (176, 160, 128)}    # Litinski's bright Z faces and dark X faces


def edges(rot: int) -> dict[str, str]:
    """The edge types of a patch turned `rot` quarters: opposite edges match, neighbours differ."""
    side, top = ("X", "Z") if rot % 2 == 0 else ("Z", "X")
    return {"left": side, "right": side, "top": top, "bottom": top}


_CACHE: dict = {}


def face_type(i: int, j: int, rot: int, phase: int) -> str:
    """The stabiliser on face (column i, row j): a checkerboard. Turning a patch a quarter
    flips the checkerboard, so rot and phase both shift it."""
    return "X" if (i + j + rot + phase) % 2 == 0 else "Z"


def moons(rot: int, phase: int):
    """The boundary half-moons: (side, segment, type). An X edge carries Z half-moons and a
    Z edge X half-moons, on the segments whose face inside is of the other type."""
    e = edges(rot)
    out = []
    for k in range(FACES):
        for side, (i, j) in (("left", (0, k)), ("right", (FACES - 1, k)),
                             ("top", (k, 0)), ("bottom", (k, FACES - 1))):
            moon = "Z" if e[side] == "X" else "X"
            if face_type(i, j, rot, phase) != moon:
                out.append((side, k, moon))
    return out


def patch_image(rot: int, phase: int = 0, letters: bool = True) -> pygame.Surface:
    """A distance-5 patch as Litinski draws it: faces, half-moons, a qubit on every vertex,
    and the edges, X dashed and red, Z solid and blue, each with its letter (a merged patch
    is drawn without: its seam edges aren't edges any more)."""
    key = ("patch", rot % 2, phase % 2, letters)
    if key not in _CACHE:
        size = SQUARE + 2 * PAD
        s = pygame.Surface((size, size), pygame.SRCALPHA)
        o = PAD
        for side, k, kind in moons(rot, phase):        # the half-moons, under the edge lines
            if side in ("left", "right"):
                c = (o if side == "left" else o + SQUARE, o + k * CELL + CELL // 2)
                quads = {"draw_top_left": side == "left", "draw_bottom_left": side == "left",
                         "draw_top_right": side == "right", "draw_bottom_right": side == "right"}
            else:
                c = (o + k * CELL + CELL // 2, o if side == "top" else o + SQUARE)
                quads = {"draw_top_left": side == "top", "draw_top_right": side == "top",
                         "draw_bottom_left": side == "bottom", "draw_bottom_right": side == "bottom"}
            pygame.draw.circle(s, P.INK, c, MOON + 1, **quads)
            pygame.draw.circle(s, FACE[kind], c, MOON, **quads)
        for i in range(FACES):
            for j in range(FACES):
                s.fill(FACE[face_type(i, j, rot, phase)], (o + i * CELL, o + j * CELL, CELL, CELL))
        for k in range(1, FACES):                       # faint face borders
            s.fill(P.shade(FACE["X"], 0.8), (o + k * CELL, o, 1, SQUARE))
            s.fill(P.shade(FACE["X"], 0.8), (o, o + k * CELL, SQUARE, 1))
        e = edges(rot)
        lines = {"top": ((o, o), (o + SQUARE, o)), "bottom": ((o, o + SQUARE), (o + SQUARE, o + SQUARE)),
                 "left": ((o, o), (o, o + SQUARE)), "right": ((o + SQUARE, o), (o + SQUARE, o + SQUARE))}
        for side, (a, b) in lines.items():
            kind = e[side]
            colour = EDGE_COLOUR[kind]
            if kind == "Z":                 # solid
                pygame.draw.line(s, P.INK, a, b, 4)
                pygame.draw.line(s, colour, a, b, 2)
            else:                           # dashed
                n = 8
                for k in range(0, n, 2):
                    p = (a[0] + (b[0] - a[0]) * k / n, a[1] + (b[1] - a[1]) * k / n)
                    q = (a[0] + (b[0] - a[0]) * (k + 1) / n, a[1] + (b[1] - a[1]) * (k + 1) / n)
                    pygame.draw.line(s, P.INK, p, q, 4)
                    pygame.draw.line(s, colour, p, q, 2)
            if letters:
                mid = ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2)
                out = {"top": (0, -10), "bottom": (0, 10), "left": (-10, 0), "right": (10, 0)}[side]
                blit_center(s, outlined(kind, 8, colour, shadow=False), (mid[0] + out[0], mid[1] + out[1]))
        for i in range(D):                  # the physical qubits, on the vertices
            for j in range(D):
                x, y = o + i * CELL, o + j * CELL
                s.fill(P.INK, (x - 1, y - 1, 3, 3))
        _CACHE[key] = s
    return _CACHE[key]


def smooth(k: float) -> float:
    k = max(0.0, min(1.0, k))
    return k * k * (3 - 2 * k)


@register
class Merge(Microgame):
    VERB = "MERGE!"
    INPUT = "stick+a"
    STEPS = True
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
        won = self.result is True
        for lane, kind in enumerate(self.fixed):
            rot = 0 if kind == "X" else 1           # a fixed patch shows `kind` facing right
            merged = won and lane == self.lane
            blit_center(surf, patch_image(rot, 0, letters=not merged), (FIXED_X, lanes[lane]))
        x, y = self.your_pos()
        img = patch_image(self.rot, YOUR_PHASE, letters=not won)
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
            hint = "LANE, {a} TURNS, < PUSHES IN"
        else:
            hint = "{a} TURNS, < PUSHES IN"
        blit_center(surf, control_hint(hint, 8, P.WHITE), (W // 2, H - 9))
        result_overlay(surf, self.result, self.since_end, seed=31)

    def _bridge(self, surf: pygame.Surface, y: float) -> None:
        """The merge: one column of new faces fills the seam, continuing the checkerboard.
        Where a half-moon was, it grows into a whole face; the faces in between are the new
        stabilisers of the measured type, and they glow: their product is the outcome."""
        kind = self.fixed[self.lane]
        rot = 0 if kind == "X" else 1
        left = FIXED_X + SQUARE // 2
        top = round(y - SQUARE / 2)
        glow = 0.3 + 0.3 * math.sin(self.since_end * 12)
        for j in range(FACES):
            seam = "Z" if face_type(FACES - 1, j, rot, 0) == "X" else "X"
            colour = FACE[seam]
            if seam == kind:                            # a new stabiliser of the measured type
                colour = P.lighten(P.GOLD, glow)
            surf.fill(colour, (left + 1, top + j * CELL, GAP - 1, CELL))
        for j in range(D):
            surf.fill(P.INK, (left + GAP - 1, top + j * CELL - 1, 3, 3))
        outline = pygame.Rect(FIXED_X - SQUARE // 2 - 3, top - 3, TARGET_X - FIXED_X + SQUARE + 6, SQUARE + 6)
        pygame.draw.rect(surf, P.lighten(P.GOLD, glow), outline, 1, border_radius=3)

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
