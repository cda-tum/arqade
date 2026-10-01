"""CANCEL!: gates scroll along a wire past a fixed gate in a slot. Press A
while the slot gate's twin is over the slot: a gate followed by its inverse
(X, Y, Z and H are each their own) cancels out.

Pressing at any other moment fails, and so does letting the twin go by. The
twin always arrives with time to spare, and every other gate on the wire is
a different kind, so there is exactly one right moment.
"""

from __future__ import annotations

import math

import pygame

from planck_time import palette as P
from planck_time.microgames.base import H, W, Microgame, PlayerInput, register
from planck_time.pixel import backdrop, blit_center, card, outlined, result_overlay

KINDS = ("X", "Y", "Z", "H")
SLOT_X = W // 2
WIRE_Y = 86
CARD = 22
WINDOW = 9  # px either side of the slot that count as "over it"
SCROLL = 62  # px per second at level 0


@register
class Cancel(Microgame):
    VERB = "CANCEL!"
    INPUT = "a"
    CAPTION = "A gate and its inverse cancel out. Compilers do this!"

    def __init__(self, seed: int, level: int, duration: float) -> None:
        super().__init__(seed, level, duration)
        self.slot = self.rng.choice(KINDS)
        self.v = SCROLL * self.speed
        spacing = max(30, 40 - 3 * level)
        arrive = self.rng.uniform(1.0, max(1.1, duration - 0.8))
        twin_x = SLOT_X + self.v * arrive
        others = [k for k in KINDS if k != self.slot]
        # gates at regular spacing, the twin among them; the rest are look-alikes
        self.gates = []  # [x, kind, is_twin]
        x = twin_x - spacing * math.ceil((twin_x + CARD) / spacing)
        while x < twin_x + 4 * spacing:
            twin = abs(x - twin_x) < 1
            self.gates.append([x, self.slot if twin else self.rng.choice(others), twin])
            x += spacing
        self.backdrop = P.BACKDROPS[self.rng.randrange(len(P.BACKDROPS))]

    @property
    def twin(self):
        return next(g for g in self.gates if g[2])

    def step(self, dt: float, inp: PlayerInput) -> None:
        for g in self.gates:
            g[0] -= self.v * dt
        twin_x = self.twin[0]
        if inp.a:
            if abs(twin_x - SLOT_X) <= WINDOW:
                self.win()
            else:
                self.fail()
        elif twin_x < SLOT_X - WINDOW:
            self.fail()  # it went by

    def bot(self) -> PlayerInput:
        return PlayerInput(a=abs(self.twin[0] - SLOT_X) <= 3)

    # --- drawing ----------------------------------------------------------------------

    def draw(self, surf: pygame.Surface) -> None:
        backdrop(surf, self.backdrop, self.t)
        surf.fill(P.INK, (0, WIRE_Y - 2, W, 5))
        surf.fill(P.MIST, (0, WIRE_Y - 1, W, 3))
        slot = pygame.Rect(0, 0, CARD + 10, CARD + 10)
        slot.center = (SLOT_X, WIRE_Y)
        flash = self.result is None and abs(self.twin[0] - SLOT_X) <= WINDOW and int(self.t * 12) % 2
        pygame.draw.rect(surf, P.GOLD if flash else P.WHITE, slot, 2, border_radius=6)
        gone = self.result is True
        if not gone:
            r = pygame.Rect(0, 0, CARD, CARD)
            r.center = (SLOT_X, WIRE_Y)
            card(surf, r, P.GATE[self.slot], self.slot)
        for x, kind, twin in self.gates:
            if gone and twin:
                continue
            r = pygame.Rect(0, 0, CARD, CARD)
            r.center = (round(x), WIRE_Y - 34)
            if -CARD < r.x < W:
                card(surf, r, P.GATE[kind], kind)
                pygame.draw.line(surf, P.MIST, (r.centerx, r.bottom + 1), (r.centerx, WIRE_Y - 13), 1)
        if gone:  # the pair cancels: two rings popping
            k = min(1.0, self.since_end / 0.3)
            pygame.draw.circle(surf, P.GOLD, (SLOT_X, WIRE_Y), round(8 + 26 * k), 2)
        blit_center(surf, outlined("A WHEN THEY MATCH", 8, P.WHITE),
                    (W // 2, H - 14))
        result_overlay(surf, self.result, self.since_end, seed=3)
