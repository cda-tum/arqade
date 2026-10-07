"""ALIGN!: turn the arrow on a Bloch sphere onto the glowing target.

The arrow is a qubit state, swung around the great circle that faces the
player (through |0>, |1>, |+> and |->), so its tip is always readable on
screen. It turns towards wherever the stick points: the stick direction is
the arrow direction, no mapping to learn. Holding the tip within 15 degrees
of the target for 0.3 s wins. The arrow starts at |0>, and the target is
never within 45 degrees of it, so doing nothing loses.
"""

from __future__ import annotations

import math

import pygame

from planck_time import palette as P
from planck_time.microgames.base import H, W, Microgame, PlayerInput, register
from planck_time.pixel import backdrop, blit_center, orb, outlined, result_overlay

CENTER = (W // 2, H // 2 + 6)
RADIUS = 56
TILT = math.radians(18)  # how far we look down onto the sphere (the equator ellipse)
TURN_RATE = 4.0  # radians per second
WIN_ANGLE = math.radians(15)
HOLD = 0.3


def wrap(a: float) -> float:
    """An angle difference folded into -pi..pi."""
    return (a + math.pi) % (2 * math.pi) - math.pi


def tip(angle: float, r: float = RADIUS) -> tuple[float, float]:
    """Screen point at `angle` clockwise from straight up (|0>)."""
    return CENTER[0] + r * math.sin(angle), CENTER[1] - r * math.cos(angle)


@register
class Align(Microgame):
    VERB = "ALIGN!"
    INPUT = "stick"
    CAPTION = "You prepared a qubit state!"

    def __init__(self, seed: int, level: int, duration: float) -> None:
        super().__init__(seed, level, duration)
        self.angle = 0.0
        away = math.radians(min(150, 45 + 20 * level))
        self.target = self.rng.choice((-1, 1)) * self.rng.uniform(away, math.pi)
        self.held = 0.0
        self.backdrop = P.BACKDROPS[self.rng.randrange(len(P.BACKDROPS))]

    @property
    def on_target(self) -> bool:
        return abs(wrap(self.angle - self.target)) < WIN_ANGLE

    def step(self, dt: float, inp: PlayerInput) -> None:
        sx, sy = inp.stick
        if math.hypot(sx, sy) > 0.5:
            want = math.atan2(sx, -sy)
            d = wrap(want - self.angle)
            turn = TURN_RATE * self.speed * dt
            self.angle = wrap(self.angle + max(-turn, min(turn, d)))
        if self.on_target:
            self.held += dt
            if self.held >= HOLD:
                self.win()
        else:
            self.held = 0.0

    def bot(self) -> PlayerInput:
        return PlayerInput(stick=(math.sin(self.target), -math.cos(self.target)))

    # --- drawing ----------------------------------------------------------------------

    def draw(self, surf: pygame.Surface) -> None:
        backdrop(surf, self.backdrop, self.t)
        cx, cy = CENTER
        pygame.draw.circle(surf, P.INK, CENTER, RADIUS + 3)
        pygame.draw.circle(surf, P.NIGHT, CENTER, RADIUS + 1)
        pygame.draw.circle(surf, P.SLATE, (cx - 8, cy - 8), RADIUS - 14)
        pygame.draw.circle(surf, P.MIST, CENTER, RADIUS + 1, 1)
        eq = pygame.Rect(0, 0, RADIUS * 2, round(RADIUS * 2 * math.sin(TILT)))
        eq.center = CENTER
        pygame.draw.ellipse(surf, P.MIST, eq, 1)
        top, bottom = tip(0), tip(math.pi)
        pygame.draw.line(surf, P.MIST, top, bottom, 1)
        blit_center(surf, outlined("|0>", 8, P.WHITE), (top[0], top[1] - 10))
        blit_center(surf, outlined("|1>", 8, P.WHITE), (bottom[0], bottom[1] + 10))

        # the target: a pulsing star
        tx, ty = tip(self.target)
        pulse = 4 + round(1.5 * math.sin(self.t * 10))
        for dx, dy in ((pulse, 0), (-pulse, 0), (0, pulse), (0, -pulse)):
            pygame.draw.line(surf, P.GOLD, (tx, ty), (tx + dx, ty + dy), 2)
        pygame.draw.circle(surf, P.WHITE, (round(tx), round(ty)), 2)

        # the arrow, green once it's on target
        ax, ay = tip(self.angle, RADIUS - 4)
        close = self.on_target or self.result
        color = P.GOOD if close else P.ORANGE
        pygame.draw.line(surf, P.INK, CENTER, (ax, ay), 5)
        pygame.draw.line(surf, color, CENTER, (ax, ay), 3)
        orb(surf, (ax, ay), 5, color, glow=bool(close))
        orb(surf, CENTER, 3, P.MIST)
        if self.held > 0 and not self.result:  # the hold timer, a ring closing round the target
            ring = pygame.Rect(0, 0, 22, 22)
            ring.center = (round(tx), round(ty))
            end = math.pi / 2 + 2 * math.pi * self.held / HOLD
            pygame.draw.arc(surf, P.INK, ring.inflate(2, 2), math.pi / 2, end, 4)
            pygame.draw.arc(surf, P.GOOD, ring, math.pi / 2, end, 2)
        result_overlay(surf, self.result, self.since_end, seed=7)
