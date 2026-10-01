"""REFRESH!: a qubit's glow bar drains steadily, and every press of A tops it
up. Keep the bar above the line until the time is up.

The bar starts above the line and drains past it in under 1.4 s, so doing
nothing loses well before the end. It is capped at full, so mashing early
only banks so much: about three presses a second keep it up at level 3,
which leaves plenty of room for a player mashing at five or six.
"""

from __future__ import annotations

import pygame

from planck_time import palette as P
from planck_time.microgames.base import H, W, Microgame, PlayerInput, register
from planck_time.pixel import backdrop, blit_center, dither, orb, outlined, result_overlay

START = 0.7
LINE = 0.3  # falling below this fails
DRAIN = 0.3  # of the bar per second at level 0
PUMP = 0.1  # added by each press
ORB = (82, 72)
ORB_R = 20
BAR = pygame.Rect(140, 20, 22, 104)  # the inside of the glow bar
BUTTON = (198, 100)


@register
class Refresh(Microgame):
    VERB = "REFRESH!"
    INPUT = "mash"
    CAPTION = "Error correction has to run again and again"

    def __init__(self, seed: int, level: int, duration: float) -> None:
        super().__init__(seed, level, duration)
        self.glow = START
        self.drain = DRAIN * self.speed
        self.since_press = 1.0  # for the pump animations
        self.backdrop = P.BACKDROPS[self.rng.randrange(len(P.BACKDROPS))]

    def step(self, dt: float, inp: PlayerInput) -> None:
        self.since_press += dt
        if inp.a:
            self.glow = min(1.0, self.glow + PUMP)
            self.since_press = 0.0
        self.glow -= self.drain * dt
        if self.glow < LINE:
            self.fail()

    def timeout(self) -> None:
        self.win()  # it stayed lit the whole time

    def bot(self) -> PlayerInput:
        # a steady eight presses a second, whenever the bar isn't nearly full
        return PlayerInput(a=self.since_press >= 0.12 and self.glow < 0.9)

    # --- drawing ----------------------------------------------------------------------

    def draw(self, surf: pygame.Surface) -> None:
        backdrop(surf, self.backdrop, self.t)
        lit = self.result is not False
        k = max(0.0, (self.glow - LINE) / (1 - LINE)) if lit else 0.0
        pump = max(0.0, 1 - self.since_press / 0.15) if lit else 0.0

        # the qubit: a halo that shrinks as the glow drains
        color = P.GOLD if k > 0.35 else P.ORANGE if k > 0.12 else P.BAD
        if not lit:
            color = P.SLATE
        halo = round(ORB_R + 4 + 16 * k + 3 * pump)
        if lit:
            pygame.draw.circle(surf, P.INK, ORB, halo + 1, 1)
            for r in range(halo, ORB_R, -4):
                pygame.draw.circle(surf, P.lighten(color, 0.3), ORB, r, 1)
        orb(surf, ORB, ORB_R + round(2 * pump), color, glow=lit)
        if self.result and self.since_end < 0.4:  # it made it: a green ring popping off
            pygame.draw.circle(surf, P.GOOD, ORB, round(ORB_R + 6 + 60 * self.since_end), 2)
        blit_center(surf, outlined("|1>", 8, P.WHITE), (ORB[0], ORB[1] + ORB_R + 14))

        # the glow bar, with the line it must stay above
        pygame.draw.rect(surf, P.INK, BAR.inflate(6, 6), border_radius=3)
        dither(surf, BAR, P.NIGHT, P.INK)
        line_y = BAR.bottom - round(BAR.height * LINE)
        dither(surf, (BAR.x, line_y, BAR.width, BAR.bottom - line_y), P.shade(P.BAD, 0.4), P.INK)
        fill_h = round(BAR.height * max(0.0, min(1.0, self.glow)))
        fill = pygame.Rect(BAR.x, BAR.bottom - fill_h, BAR.width, fill_h)
        bar_color = P.GOOD if k > 0.35 else P.GOLD if k > 0.12 else P.BAD
        if not lit:
            bar_color = P.SLATE
        surf.fill(P.shade(bar_color, 0.7), fill)
        surf.fill(bar_color, fill.inflate(-6, 0))
        if fill_h > 2:
            surf.fill(P.lighten(bar_color, 0.6), (fill.x + 4, fill.y + 1, 3, fill_h - 2))
            surf.fill(P.WHITE, (fill.x, fill.y, fill.width, 1))
        blink = k < 0.15 and lit and int(self.t * 10) % 2
        line_color = P.WHITE if blink else P.BAD
        surf.fill(P.INK, (BAR.x - 8, line_y - 2, BAR.width + 16, 4))
        surf.fill(line_color, (BAR.x - 7, line_y - 1, BAR.width + 14, 2))
        for dy in range(-3, 4):  # a pointer on the line, from the left
            surf.fill(P.INK, (BAR.x - 14, line_y + dy, 5 - abs(dy), 1))

        # a big A that squashes on every press, with rising sparks
        bx, by = BUTTON
        down = 2 if pump > 0.5 else 0
        pygame.draw.circle(surf, P.INK, (bx, by + 3), 15)
        orb(surf, (bx, by + down), 13, P.BAD)
        blit_center(surf, outlined("A", 16, P.WHITE, shadow=False), (bx + 1, by + down))
        if pump > 0:
            rise = round(14 * (1 - pump))
            for dx in (-12, 0, 12):
                blit_center(surf, outlined("+", 8, P.GOLD), (BAR.centerx + dx, fill.y - 6 - rise))

        blit_center(surf, outlined("MASH A!", 8, P.WHITE), (W // 2, H - 14))
        result_overlay(surf, self.result, self.since_end, seed=10)
