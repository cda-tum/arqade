"""TILE! (the colour code): a patch of the 2D colour code, a honeycomb of hexagonal
tiles, each red, green or blue, with a dot at every corner for the data qubits.
One tile is blank and pulses: pick its colour from the three swatches with the
stick and paint it with A.

It is a real 3-colouring, the colour code's own: a tile's colour is (q - r) mod 3
in axial hex coordinates, under a shuffled choice of which class is which colour.
Neighbouring tiles always differ, so the six neighbours round a tile alternate
between the other two colours, and every corner touches one tile of each colour
(that is what lets each tile be a stabiliser check of both kinds). So the blank's
colour is forced: the one its neighbours don't have. Even at the patch's edge,
with only 3 or 4 neighbours, two neighbours next to each other already show both
other colours, so the answer stays unique (tests/test_code_microgames.py).

Each swatch and each tile also carries a shape (triangle, circle, square), so the
colours can be told apart without colour vision.

Later appearances: first one interior blank; then two blanks, never neighbours,
so each is still forced by its own neighbours (painted one after the other); then
blanks on the patch's edge.
"""

from __future__ import annotations

import math

import pygame

from planck_time import palette as P
from planck_time.microgames.base import IDLE, H, W, Microgame, PlayerInput, register
from planck_time.pixel import backdrop, blit_center, outlined, result_overlay

RADIUS = 2                      # the patch: every hex within 2 steps of the centre (19 tiles)
SIZE = 13                       # a tile's circumradius, px (pointy-top hexes)
CENTRE = (W // 2, 62)
SWATCH_Y = 130
SWATCH_X = (84, 120, 156)
COLOURS = (P.BAD, P.GOOD, P.SKY)    # red, green, blue
NAMES = ("RED", "GREEN", "BLUE")
SHAPES = ("triangle", "circle", "square")
READY = 0.6                     # input counts from here (level 0): the first decision's moment
THINK = 0.25                    # the bot looks before it moves...
BOT_STEP = 0.12                 # ...steps a swatch this often...
BOT_SETTLE = 0.1                # ...and checks once more before painting
OFFSETS = ((1, 0), (-1, 0), (0, 1), (0, -1), (1, -1), (-1, 1))


def neighbours(tile: tuple[int, int]) -> list[tuple[int, int]]:
    q, r = tile
    return [(q + dq, r + dr) for dq, dr in OFFSETS]


def ring(tile: tuple[int, int]) -> int:
    """How many steps from the patch's centre."""
    q, r = tile
    return max(abs(q), abs(r), abs(q + r))


def inside(tile, cells) -> int:
    """How many of a tile's neighbours are in the patch (6 inside, 3 or 4 on the edge)."""
    return sum(1 for n in neighbours(tile) if n in cells)


def patch() -> list[tuple[int, int]]:
    return [(q, r) for r in range(-RADIUS, RADIUS + 1) for q in range(-RADIUS, RADIUS + 1)
            if ring((q, r)) <= RADIUS]


def pixel(tile: tuple[int, int]) -> tuple[float, float]:
    q, r = tile
    return (CENTRE[0] + SIZE * math.sqrt(3) * (q + r / 2), CENTRE[1] + SIZE * 1.5 * r)


def corners(tile: tuple[int, int], size: float = SIZE) -> list[tuple[float, float]]:
    cx, cy = pixel(tile)
    return [(cx + size * math.cos(math.radians(60 * i - 30)), cy + size * math.sin(math.radians(60 * i - 30)))
            for i in range(6)]


def shape(surf: pygame.Surface, kind: str, centre, r: int, colour) -> None:
    x, y = round(centre[0]), round(centre[1])
    if kind == "triangle":
        pygame.draw.polygon(surf, colour, [(x, y - r), (x + r, y + r - 1), (x - r, y + r - 1)])
    elif kind == "circle":
        pygame.draw.circle(surf, colour, (x, y), r)
    else:
        surf.fill(colour, (x - r + 1, y - r + 1, 2 * r - 1, 2 * r - 1))


@register
class Tile(Microgame):
    VERB = "TILE!"
    INPUT = "stick+a"
    STEPS = True
    CAPTION = "Each corner touches one tile of every colour"

    def __init__(self, seed: int, level: int, duration: float) -> None:
        super().__init__(seed, level, duration)
        self.cells = patch()
        perm = [0, 1, 2]
        self.rng.shuffle(perm)
        self.colours = {t: perm[(t[0] - t[1]) % 3] for t in self.cells}
        self.blanks = self._pick_blanks()
        self.painted: dict[tuple[int, int], int] = {}
        self.cursor = 1
        self.ready = READY / self.speed
        self.moved_at = 0.0
        self.wrong: tuple[tuple[int, int], int] | None = None
        self.backdrop = P.BACKDROPS[self.rng.randrange(len(P.BACKDROPS))]

    def _pick_blanks(self) -> list[tuple[int, int]]:
        inner = [t for t in self.cells if ring(t) <= 1]
        edge = [t for t in self.cells if ring(t) == RADIUS]
        if self.appearance == 0:
            return [self.rng.choice(inner)]
        pool = inner if self.appearance == 1 else edge
        while True:
            a, b = self.rng.sample(pool, 2)
            if b not in neighbours(a):
                return sorted((a, b), key=lambda t: (pixel(t)[1], pixel(t)[0]))   # top one first

    @property
    def active(self) -> tuple[int, int] | None:
        """The blank to paint now: the first one not painted yet."""
        return next((b for b in self.blanks if b not in self.painted), None)

    def answer(self) -> int:
        return self.colours[self.active]

    # --- the rules -----------------------------------------------------------------------

    def step(self, dt: float, inp: PlayerInput) -> None:
        if self.t < self.ready:
            return
        if inp.step[0]:
            self.cursor = max(0, min(2, self.cursor + inp.step[0]))
            self.moved_at = self.t
        if inp.a:
            tile = self.active
            if self.cursor != self.colours[tile]:
                self.wrong = (tile, self.cursor)
                self.fail()
                return
            self.painted[tile] = self.cursor
            if self.active is None:
                self.win()

    def bot(self) -> PlayerInput:
        if self.t < self.ready + THINK or self.active is None:
            return IDLE
        since = self.t - self.moved_at
        want = self.answer()
        if self.cursor != want:
            return PlayerInput(step=(1 if want > self.cursor else -1, 0)) if since >= BOT_STEP else IDLE
        if since >= BOT_SETTLE:
            self.moved_at = self.t      # a fresh look before the next blank
            return PlayerInput(a=True, a_held=True)
        return IDLE

    # --- drawing -------------------------------------------------------------------------

    def draw(self, surf: pygame.Surface) -> None:
        backdrop(surf, self.backdrop, self.t)
        pulse = 0.5 + 0.5 * math.sin(self.t * 9)
        active = self.active
        clash = set()
        if self.wrong is not None:
            tile, colour = self.wrong
            clash = {n for n in neighbours(tile) if self.colours.get(n) == colour and n not in self.blanks}
        for t in self.cells:
            pts = corners(t)
            pygame.draw.polygon(surf, P.INK, corners(t, SIZE + 1.5))
            if t in self.painted:
                colour = COLOURS[self.painted[t]]
            elif self.wrong is not None and t == self.wrong[0]:
                colour = COLOURS[self.wrong[1]]
            elif t in self.blanks:
                colour = P.NIGHT
            else:
                colour = COLOURS[self.colours[t]]
            flash = t in clash and int(self.since_end * 10) % 2 == 0
            pygame.draw.polygon(surf, P.WHITE if flash else colour, pts)
            if t in self.blanks and t not in self.painted and (self.wrong is None or t != self.wrong[0]):
                edge = P.lighten(P.GOLD, pulse) if t == active else P.SLATE
                pygame.draw.polygon(surf, edge, corners(t, SIZE - 1.5), 2)
                if t == active:
                    blit_center(surf, outlined("?", 8, P.WHITE), pixel(t))
            else:
                shown = self.painted.get(t, self.wrong[1] if self.wrong and t == self.wrong[0] else self.colours[t])
                shape(surf, SHAPES[shown], pixel(t), 3, P.shade(COLOURS[shown], 0.45))
            if t in clash:
                self._cross(surf, pixel(t))
        for t in self.cells:            # the data qubits: a dot at every corner
            for x, y in corners(t):
                surf.fill(P.INK, (round(x) - 1, round(y) - 1, 3, 3))
                surf.fill(P.CREAM, (round(x), round(y), 1, 1))
        if self.result is True:
            self._lit_corners(surf)
        self._swatches(surf)
        if self.result is False:
            hint = "NEIGHBOURS CLASH!" if self.wrong else "TOO SLOW!"
        elif self.result is True:
            hint = "EVERY CORNER SEES ALL 3"
        else:
            hint = "PAINT THE MISSING COLOUR"
        blit_center(surf, outlined(hint, 8, P.WHITE), (W // 2, H - 9))
        result_overlay(surf, self.result, self.since_end, seed=29)

    def _swatches(self, surf: pygame.Surface) -> None:
        for i, x in enumerate(SWATCH_X):
            on = i == self.cursor and self.result is None
            box = pygame.Rect(0, 0, 20, 20)
            box.center = (x, SWATCH_Y - (2 if on else 0))
            pygame.draw.rect(surf, P.WHITE if on else P.INK, box.inflate(4, 4), border_radius=4)
            pygame.draw.rect(surf, COLOURS[i], box, border_radius=3)
            shape(surf, SHAPES[i], box.center, 4, P.shade(COLOURS[i], 0.45))

    def _lit_corners(self, surf: pygame.Surface) -> None:
        """The win: the corners round the painted tiles light up, each touching all 3 colours."""
        k = min(1.0, self.since_end / 0.3)
        for t in self.painted:
            for x, y in corners(t):
                r = round(2 + 2 * k)
                pygame.draw.circle(surf, P.INK, (round(x), round(y)), r + 1)
                pygame.draw.circle(surf, P.WHITE, (round(x), round(y)), r)

    @staticmethod
    def _cross(surf: pygame.Surface, centre) -> None:
        x, y = round(centre[0]), round(centre[1])
        for d in (-1, 1):
            pygame.draw.line(surf, P.INK, (x - 5, y - 5 * d), (x + 5, y + 5 * d), 4)
            pygame.draw.line(surf, P.BAD, (x - 5, y - 5 * d), (x + 5, y + 5 * d), 2)
