"""FIX!: a qubit orb has caught an error bug, X, Y or Z, in its gate's
colour. Three gate cards (X, Y and Z) sit below it. Step the cursor with the
stick and press A to apply a card: the same Pauli undoes the error (each is
its own inverse) and wins; any other card fails.

From level 1 the cards shuffle once, early on, like a shell game: each card
slides to its new place along an arc, so the matching one can be followed
with the eye. A is ignored while they move. Doing nothing runs out the clock.
"""

from __future__ import annotations

import math
from itertools import permutations

import pygame

from planck_time import palette as P
from planck_time.microgames.base import H, W, Microgame, PlayerInput, register
from planck_time.pixel import backdrop, blit_center, card, orb, outlined, result_overlay

KINDS = ("X", "Y", "Z")
ORB = (W // 2, 48)
ORB_R = 28
ORB_COLOR = P.TEAL
CARD_Y = 116
CARD = 26
SPACING = 54
SHUFFLE_TIME = 0.6  # seconds the shuffle takes at level 0
BOT_THINK = 0.4  # the bot looks before it moves...
BOT_STEP = 0.15  # ...and moves the cursor this often


def slot_x(i: float) -> float:
    return W // 2 + (i - 1) * SPACING


def smooth(k: float) -> float:
    return k * k * (3 - 2 * k)


def bug(surf: pygame.Surface, center, color, letter: str, t: float) -> None:
    """A beetle in the error's gate colour, its letter on its back, legs scuttling."""
    cx, cy = round(center[0]), round(center[1])
    wig = 1 if int(t * 10) % 2 else -1
    for i, dy in enumerate((-6, 1, 8)):
        w = wig if i % 2 else -wig
        for side in (-1, 1):
            pygame.draw.line(surf, P.INK, (cx + side * 8, cy + dy), (cx + side * 15, cy + dy + 2 * w), 3)
    for side in (-1, 1):
        pygame.draw.line(surf, P.INK, (cx + side * 3, cy - 14), (cx + side * 8, cy - 21 + wig), 2)
    pygame.draw.circle(surf, P.INK, (cx, cy - 12), 6)
    pygame.draw.circle(surf, P.shade(color, 0.5), (cx, cy - 12), 5)
    surf.fill(P.WHITE, (cx - 3, cy - 14, 2, 2))
    surf.fill(P.WHITE, (cx + 2, cy - 14, 2, 2))
    body = pygame.Rect(0, 0, 22, 24)
    body.center = (cx, cy + 2)
    pygame.draw.ellipse(surf, P.INK, body.inflate(4, 4))
    pygame.draw.ellipse(surf, P.shade(color, 0.7), body)
    top = body.inflate(-4, -6).move(-1, -2)
    pygame.draw.ellipse(surf, color, top)
    surf.fill(P.lighten(color, 0.6), (body.x + 5, body.y + 4, 3, 2))
    blit_center(surf, outlined(letter, 16, P.WHITE, shadow=False), (cx + 1, cy + 3))


def pointer(surf: pygame.Surface, x: float, y: float, color) -> None:
    """A chunky down-pointing arrow with its tip at (x, y)."""
    x, y = round(x), round(y)
    pygame.draw.polygon(surf, P.INK, ((x - 8, y - 9), (x + 8, y - 9), (x, y + 1)))
    pygame.draw.polygon(surf, color, ((x - 5, y - 7), (x + 5, y - 7), (x, y - 2)))


@register
class Fix(Microgame):
    VERB = "FIX!"
    INPUT = "stick+a"
    CAPTION = "Undo an error by applying the same Pauli"

    def __init__(self, seed: int, level: int, duration: float) -> None:
        super().__init__(seed, level, duration)
        self.error = self.rng.choice(KINDS)
        self.order = self.rng.sample(KINDS, 3)  # the card at each slot
        self.cursor = 1
        self.picked: int | None = None
        self.moved_at = 0.0
        self.shuffle_at: float | None = None
        if level >= 1:
            here = self.order.index(self.error)
            # dest[i] = where the card now at slot i goes; the error's twin always moves
            self.dest = self.rng.choice([p for p in permutations(range(3)) if p[here] != here])
            self.shuffle_at = self.rng.uniform(0.6, 0.9)
            self.shuffle_len = SHUFFLE_TIME / self.speed
        self.backdrop = P.BACKDROPS[self.rng.randrange(len(P.BACKDROPS))]

    @property
    def shuffling(self) -> bool:
        return (self.result is None and self.shuffle_at is not None
                and self.shuffle_at <= self.t < self.shuffle_at + self.shuffle_len)

    @property
    def shuffle_pending(self) -> bool:
        return self.shuffle_at is not None and self.t < self.shuffle_at + self.shuffle_len

    def step(self, dt: float, inp: PlayerInput) -> None:
        if self.shuffle_at is not None and self.t + dt >= self.shuffle_at + self.shuffle_len and self.dest:
            new = [""] * 3
            for i, kind in enumerate(self.order):
                new[self.dest[i]] = kind
            self.order, self.dest = new, None
        if inp.step[0]:
            self.cursor = max(0, min(2, self.cursor + inp.step[0]))
            self.moved_at = self.t
        if inp.a and not self.shuffling:
            self.picked = self.cursor
            if self.order[self.cursor] == self.error:
                self.win()
            else:
                self.fail()

    def bot(self) -> PlayerInput:
        if self.t < BOT_THINK or self.shuffle_pending:
            return PlayerInput()
        goal = self.order.index(self.error)
        if goal == self.cursor:
            return PlayerInput(a=True, a_held=True)
        if self.t - self.moved_at < BOT_STEP:
            return PlayerInput()
        return PlayerInput(step=(1 if goal > self.cursor else -1, 0))

    # --- drawing ----------------------------------------------------------------------

    def card_pos(self, i: int) -> tuple[float, float]:
        """Where the card at slot i is drawn, mid-shuffle included."""
        if not self.shuffling or self.dest is None:
            return slot_x(i), CARD_Y
        k = smooth((self.t - self.shuffle_at) / self.shuffle_len)
        to = self.dest[i]
        x = slot_x(i) + (slot_x(to) - slot_x(i)) * k
        # leftward cards hop over, rightward ones duck under, so they never overlap
        lift = 12 * abs(to - i) * math.sin(math.pi * k)
        return x, CARD_Y + (lift if to > i else -lift)

    def draw(self, surf: pygame.Surface) -> None:
        backdrop(surf, self.backdrop, self.t)
        won = self.result is True
        # the qubit, with the bug on it (flying off once fixed)
        orb(surf, ORB, ORB_R, ORB_COLOR, glow=won)
        if won:
            k = self.since_end
            pygame.draw.circle(surf, P.GOOD, ORB, ORB_R + 4 + round(30 * min(1.0, k / 0.3)), 2)
            if k < 0.6:
                bug(surf, (ORB[0] + 4 + 60 * k, ORB[1] + 4 - 140 * k), P.shade(P.GATE[self.error], 0.7),
                    self.error, self.t)
        else:
            bug(surf, (ORB[0] + 4, ORB[1] + 4), P.GATE[self.error], self.error, self.t)

        # the cards; the one under the cursor is ringed, with an arrow over it
        for i, kind in enumerate(self.order):
            x, y = self.card_pos(i)
            r = pygame.Rect(0, 0, CARD, CARD)
            r.center = (round(x), round(y))
            here = i == self.cursor
            if self.picked == i:
                ring = P.GOOD if won else P.BAD
                pygame.draw.rect(surf, P.INK, r.inflate(10, 10), border_radius=7)
                pygame.draw.rect(surf, ring, r.inflate(8, 8), border_radius=7)
            card(surf, r, P.GATE[kind], kind, selected=here and self.picked is None)
            if self.picked == i and self.result is False:  # a red X over the wrong card
                for a, b in (((r.left, r.top), (r.right, r.bottom)), ((r.right, r.top), (r.left, r.bottom))):
                    pygame.draw.line(surf, P.INK, a, b, 6)
                    pygame.draw.line(surf, P.BAD, a, b, 3)
        bob = 0 if self.result is not None else round(2 * math.sin(self.t * 9))
        pointer(surf, slot_x(self.cursor), CARD_Y - CARD // 2 - 6 + bob, P.GOLD)
        blit_center(surf, outlined("PICK THE MATCHING GATE", 8, P.WHITE), (W // 2, H - 9))
        result_overlay(surf, self.result, self.since_end, seed=11)
