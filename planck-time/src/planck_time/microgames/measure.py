"""MEASURE!: a qubit orb's needle swings like a pendulum between |0>
(straight down) and |1> (straight up), overshooting the top a little. Press
A while it is inside the glowing zone round |1>: the qubit collapses to 1
and you win. A press anywhere else fails, and so does never pressing.

The needle starts at |0>, so the first chance comes after most of a second.
It passes through the zone twice per swing (up past the top, and back).
"""

from __future__ import annotations

import math

import pygame

from planck_time import palette as P
from planck_time.microgames.base import H, W, Microgame, PlayerInput, register
from planck_time.pixel import backdrop, blit_center, control_hint, orb, outlined, result_overlay

CENTER = (W // 2, 78)
RADIUS = 42
PERIOD = 2.2  # seconds per swing (up and back) at level 0
OVERSHOOT = math.radians(34)  # how far past the top the needle swings
MID = (math.pi - OVERSHOOT) / 2  # the swing, as an angle clockwise from straight up
AMP = (math.pi + OVERSHOOT) / 2
ZONE = math.radians(26)  # half-width of the zone at level 0...
ZONE_PER_LEVEL = math.radians(2.5)  # ...narrowing this much per level...
ZONE_MIN = math.radians(12)  # ...down to this


def tip(angle: float, r: float) -> tuple[float, float]:
    """Screen point at `angle` clockwise from straight up (|1>)."""
    return CENTER[0] + r * math.sin(angle), CENTER[1] - r * math.cos(angle)


@register
class Measure(Microgame):
    VERB = "MEASURE!"
    INPUT = "a"
    CAPTION = "Measuring collapses a qubit to 0 or 1"

    def __init__(self, seed: int, level: int, duration: float) -> None:
        super().__init__(seed, level, duration)
        self.omega = 2 * math.pi / PERIOD * self.speed * self.rng.uniform(0.95, 1.05)
        self.zone = max(ZONE_MIN, ZONE - ZONE_PER_LEVEL * level)
        self.phase = 0.0
        self.angle = math.pi  # straight down, |0>
        self.backdrop = P.BACKDROPS[self.rng.randrange(len(P.BACKDROPS))]

    @property
    def in_zone(self) -> bool:
        return abs(self.angle) <= self.zone

    def step(self, dt: float, inp: PlayerInput) -> None:
        self.phase += self.omega * dt
        self.angle = MID + AMP * math.cos(self.phase)
        if inp.a:
            if self.in_zone:
                self.win()
            else:
                self.fail()

    def bot(self) -> PlayerInput:
        # the needle moves at most ~6 degrees a frame, so pressing in the middle
        # half of the zone still lands inside it after this frame's swing
        return PlayerInput(a=abs(self.angle) < self.zone / 2)

    # --- drawing ----------------------------------------------------------------------

    def draw(self, surf: pygame.Surface) -> None:
        backdrop(surf, self.backdrop, self.t)
        cx, cy = CENTER
        orb(surf, CENTER, RADIUS, P.SLATE, glow=self.result is True)
        pygame.draw.circle(surf, P.NIGHT, CENTER, RADIUS - 8)
        pygame.draw.circle(surf, P.INK, CENTER, RADIUS - 8, 1)

        # the zone round |1>: a wedge that lights up while the needle is in it
        lit = self.result is True or (self.result is None and self.in_zone)
        steps = 8
        wedge = [CENTER] + [tip(-self.zone + 2 * self.zone * i / steps, RADIUS - 9) for i in range(steps + 1)]
        pygame.draw.polygon(surf, P.GOOD if lit else P.GOOD_DARK, wedge)
        pygame.draw.polygon(surf, P.INK, wedge, 1)

        # ticks along the swing, from |0> round the right to |1>
        for i in range(9):
            a = math.pi * i / 8
            pygame.draw.line(surf, P.MIST, tip(a, RADIUS - 7), tip(a, RADIUS - 3), 1)
        blit_center(surf, outlined("|1>", 8, P.WHITE), (cx, cy - RADIUS - 9))
        blit_center(surf, outlined("|0>", 8, P.WHITE), (cx, cy + RADIUS + 9))

        # the needle: green and collapsed on a win, red where it stopped on a miss
        angle = 0.0 if self.result is True else self.angle
        color = {True: P.GOOD, False: P.BAD}.get(self.result, P.ORANGE)
        nx, ny = tip(angle, RADIUS - 12)
        pygame.draw.line(surf, P.INK, CENTER, (nx, ny), 5)
        pygame.draw.line(surf, color, CENTER, (nx, ny), 3)
        orb(surf, (nx, ny), 4, color, glow=self.result is True)
        orb(surf, CENTER, 4, P.MIST)
        if self.result is True:  # the collapse: a ring popping out of the orb
            k = min(1.0, self.since_end / 0.3)
            pygame.draw.circle(surf, P.GOLD, CENTER, round(RADIUS + 2 + 20 * k), 2)
            blit_center(surf, outlined("1", 16, P.GOLD), (cx + 28, cy - 28))
        elif self.result is False:
            x, y = round(nx), round(ny)
            for a, b in (((x - 6, y - 6), (x + 6, y + 6)), ((x + 6, y - 6), (x - 6, y + 6))):
                pygame.draw.line(surf, P.INK, a, b, 5)
                pygame.draw.line(surf, P.BAD, a, b, 2)
        blit_center(surf, control_hint("{a} WHEN IT POINTS AT |1>", 8, P.WHITE), (W // 2, H - 9))
        result_overlay(surf, self.result, self.since_end, seed=5)
