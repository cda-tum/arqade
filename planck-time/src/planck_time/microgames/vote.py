"""VOTE!: a row of copies of one bit, and one of them has flipped. Step the
cursor with the stick and press A on the odd one out: the majority wins the
vote, the flipped copy flips back and glows. Picking any other copy fails,
and so does running out the clock.

There are 3 copies, 5 from level 2, and from level 1 they jiggle in place,
more with each level. The flipped copy is never the one the cursor starts
on, so it always takes a move.
"""

from __future__ import annotations

import math

import pygame

from planck_time import palette as P
from planck_time.microgames.base import H, W, Microgame, PlayerInput, register
from planck_time.pixel import backdrop, blit_center, card, outlined, result_overlay

ROW_Y = 78
BIT_COLOR = {0: P.SKY, 1: P.ORANGE}
JIGGLE = 1.5  # px of jiggle per level above 0...
JIGGLE_MAX = 5  # ...up to this
JIGGLE_RATE = 9.0  # radians per second at level 0
BOT_THINK = 0.4  # the bot looks before it moves...
BOT_STEP = 0.15  # ...and moves the cursor this often


def pointer(surf: pygame.Surface, x: float, y: float, color) -> None:
    """A chunky down-pointing arrow with its tip at (x, y)."""
    x, y = round(x), round(y)
    pygame.draw.polygon(surf, P.INK, ((x - 8, y - 9), (x + 8, y - 9), (x, y + 1)))
    pygame.draw.polygon(surf, color, ((x - 5, y - 7), (x + 5, y - 7), (x, y - 2)))


@register
class Vote(Microgame):
    VERB = "VOTE!"
    INPUT = "stick+a"
    STEPS = True
    CAPTION = "A majority vote corrects a bit flip"

    def __init__(self, seed: int, level: int, duration: float) -> None:
        super().__init__(seed, level, duration)
        self.n = 5 if level >= 2 else 3
        self.size = 34 if self.n == 3 else 30
        self.spacing = 64 if self.n == 3 else 44
        self.bit = self.rng.choice((0, 1))
        self.cursor = self.n // 2
        self.odd = self.rng.choice([i for i in range(self.n) if i != self.cursor])
        self.picked: int | None = None
        self.moved_at = 0.0
        self.jiggle = min(JIGGLE_MAX, JIGGLE * level)
        # each copy jiggles to its own beat
        self.beats = [(self.rng.uniform(0, 2 * math.pi), self.rng.uniform(0.8, 1.3)) for _ in range(self.n)]
        self.backdrop = P.BACKDROPS[self.rng.randrange(len(P.BACKDROPS))]

    def step(self, dt: float, inp: PlayerInput) -> None:
        if inp.step[0]:
            self.cursor = max(0, min(self.n - 1, self.cursor + inp.step[0]))
            self.moved_at = self.t
        if inp.a:
            self.picked = self.cursor
            if self.cursor == self.odd:
                self.win()
            else:
                self.fail()

    def bot(self) -> PlayerInput:
        if self.t < BOT_THINK:
            return PlayerInput()
        if self.cursor == self.odd:
            return PlayerInput(a=True, a_held=True)
        if self.t - self.moved_at < BOT_STEP:
            return PlayerInput()
        return PlayerInput(step=(1 if self.odd > self.cursor else -1, 0))

    # --- drawing ----------------------------------------------------------------------

    def slot_x(self, i: int) -> float:
        return W // 2 + (i - (self.n - 1) / 2) * self.spacing

    def bit_at(self, i: int) -> int:
        """What copy i shows: the odd one is flipped until it's fixed."""
        if i == self.odd and self.result is not True:
            return 1 - self.bit
        return self.bit

    def card_center(self, i: int) -> tuple[int, int]:
        """Copy i's centre, jiggling to its own beat (still once it's over)."""
        x, y = round(self.slot_x(i)), ROW_Y
        if self.jiggle and self.result is None:
            phase, beat = self.beats[i]
            rate = JIGGLE_RATE * self.speed * beat
            x += round(self.jiggle * math.sin(self.t * rate + phase))
            y += round(self.jiggle * 0.6 * math.cos(self.t * rate * 1.3 + phase))
        return x, y

    def draw(self, surf: pygame.Surface) -> None:
        backdrop(surf, self.backdrop, self.t)
        still = self.result is not None
        # the copies sit on one wire, like a repetition code
        surf.fill(P.INK, (0, ROW_Y - 2, W, 5))
        surf.fill(P.MIST, (0, ROW_Y - 1, W, 3))
        for i in range(self.n):
            r = pygame.Rect(0, 0, self.size, self.size)
            r.center = self.card_center(i)
            if self.picked == i:  # green for the fixed copy, red for a wrong pick
                ring = P.GOOD if self.result else P.BAD
                pygame.draw.rect(surf, P.INK, r.inflate(10, 10), border_radius=7)
                pygame.draw.rect(surf, ring, r.inflate(8, 8), border_radius=7)
            bit = self.bit_at(i)
            card(surf, r, BIT_COLOR[bit], str(bit), selected=i == self.cursor and self.picked is None)
            if self.picked == i and self.result is True:
                k = min(1.0, self.since_end / 0.3)
                pygame.draw.rect(surf, P.GOOD, r.inflate(12 + round(20 * k), 12 + round(20 * k)), 2,
                                 border_radius=8)
            elif self.picked == i and self.result is False:
                for a, b in (((r.left, r.top), (r.right, r.bottom)), ((r.right, r.top), (r.left, r.bottom))):
                    pygame.draw.line(surf, P.INK, a, b, 6)
                    pygame.draw.line(surf, P.BAD, a, b, 3)
        bob = 0 if still else round(2 * math.sin(self.t * 9))
        px, py = self.card_center(self.cursor)
        pointer(surf, px, py - self.size // 2 - 9 + bob, P.GOLD)
        blit_center(surf, outlined("A ON THE ODD ONE OUT", 8, P.WHITE), (W // 2, H - 9))
        result_overlay(surf, self.result, self.since_end, seed=17)
