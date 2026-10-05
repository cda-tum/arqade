"""SURF! (from Ion Surfer): your ion rolls on the trap potential, drawn as Ion
Surfer's curve over its strip of gold electrode plates. Ahead of it, in a dip of
the potential, is a loss hole. The stick, up and down, raises or lowers the one
electrode under the hole (left and right do nothing): raise it into a hill and the
ion rolls back; leave it and the ion rolls into the hole. Keep it out until time's
up (a survive game: the timeout wins).

The potential is a sum of one bump per electrode, as in Ion Surfer, and the ion
rolls on it with a little damping.
"""

from __future__ import annotations

import math

import pygame

from planck_time import palette as P
from planck_time.microgames.base import H, W, Microgame, PlayerInput, register
from planck_time.pixel import blit_center, outlined, result_overlay

GROUND = 120                    # the curve's zero, px; the electrode strip is below it
N = 8                           # electrodes
EW = W / N                      # an electrode's width, px
BUMP = 20.0                     # each electrode's bump's width, px
VMAX = 80.0                     # an electrode's highest voltage (its bump's height, px)
RATE = 180.0                    # voltage change at full stick, per s
GRAVITY = 200.0                 # px/s^2 per unit slope at level 0: untouched, the ion falls in after ~1.6-1.9 s
DAMPING = 1.0                   # per s
CAPTURE = 7                     # px: the hole takes an ion this close...
DEEP = 10.0                     # ...while the curve over it is no higher than this above its bottom
READY = 0.6                     # the first moment a decision is possible (level 0)


def q(c) -> tuple[int, int, int]:
    """An Ion Surfer colour snapped onto the GBA's 15-bit grid."""
    return tuple(min(248, round(v / 8) * 8) for v in c)


BACKGROUND = q((6, 10, 24))
GRID = q((20, 30, 60))
STRIP = q((8, 13, 29))
STRIP_EDGE = q((42, 55, 100))
GOLD = q((210, 170, 80))
CURVE = P.TEAL
ION = q((120, 200, 255))
HOLE_RING = q((210, 180, 255))
HOLE_ARC = q((200, 160, 255))


def centre(i: int) -> float:
    return (i + 0.5) * EW


def height(v: list[float], x: float) -> float:
    """The potential's height above GROUND at x: one Gaussian bump per electrode."""
    return sum(vi * math.exp(-((x - centre(i)) / BUMP) ** 2) for i, vi in enumerate(v))


def slope(v: list[float], x: float) -> float:
    return sum(-2 * vi * (x - centre(i)) / BUMP ** 2 * math.exp(-((x - centre(i)) / BUMP) ** 2)
               for i, vi in enumerate(v))


@register
class Surf(Microgame):
    VERB = "SURF!"
    INPUT = "stick"
    CAPTION = "You shape the trap that holds the ion"

    def __init__(self, seed: int, level: int, duration: float) -> None:
        super().__init__(seed, level, duration)
        jitter = lambda: self.rng.uniform(-4, 4)   # noqa: E731
        # high walls at both ends; a slope down from the ion towards the hole; the hole's
        # electrode low, so it sits in a dip
        v = [VMAX + 10, 64 + jitter(), 50 + jitter(), 36 + jitter(), 24 + jitter(), 0.0, 44 + jitter(), VMAX + 10]
        self.flip = self.rng.random() < 0.5         # mirrored: the hole on the left
        if self.flip:
            v.reverse()
        self.v = v
        self.k = N - 1 - 5 if self.flip else 5     # the electrode under the hole
        self.x = centre(N - 1 - 1) if self.flip else centre(1)
        self.vx = 0.0
        self.hole = (centre(self.k), GROUND - height(self.v, centre(self.k)))
        self.bottom = height(self.v, centre(self.k))
        self.gravity = GRAVITY * self.speed ** 2
        self.trail: list[tuple[float, float]] = []

    def step(self, dt: float, inp: PlayerInput) -> None:
        self.v[self.k] = max(0.0, min(VMAX, self.v[self.k] - inp.stick[1] * RATE * dt))
        sub = 4
        for _ in range(sub):
            h = dt / sub
            self.vx += (-self.gravity * slope(self.v, self.x) - DAMPING * self.vx) * h
            self.x += self.vx * h
        self.trail = (self.trail + [(self.x, GROUND - height(self.v, self.x))])[-8:]
        deep = height(self.v, self.hole[0]) <= self.bottom + DEEP
        if abs(self.x - self.hole[0]) < CAPTURE and deep:
            self.fail()
        elif not 0 <= self.x <= W:
            self.fail()

    def timeout(self) -> None:
        self.win()              # kept it out to the end

    def bot(self) -> PlayerInput:
        return PlayerInput(stick=(0.0, -1.0))

    # --- drawing -------------------------------------------------------------------------

    def draw(self, surf: pygame.Surface) -> None:
        surf.fill(BACKGROUND)
        for x in range(0, W, 30):
            surf.fill(GRID, (x, 0, 1, GROUND))
        for y in range(GROUND, 0, -30):
            surf.fill(GRID, (0, y, W, 1))
        pts = [(x, GROUND - height(self.v, x)) for x in range(0, W + 1, 4)]
        layer = pygame.Surface((W, GROUND + 1), pygame.SRCALPHA)
        pygame.draw.polygon(layer, (*CURVE, 60), pts + [(W, GROUND), (0, GROUND)])
        surf.blit(layer, (0, 0))
        pygame.draw.lines(surf, CURVE, False, pts, 2)
        for i in range(N):
            x = centre(i)
            y = GROUND - height(self.v, x)
            sel = i == self.k
            pygame.draw.circle(surf, P.WHITE if sel else P.shade(CURVE, 0.6), (round(x), round(y)), 3 if sel else 2)
        self._hole(surf)
        for i, (tx, ty) in enumerate(self.trail):
            a = (i + 1) / max(1, len(self.trail))
            pygame.draw.circle(surf, P.shade(ION, 0.25 + 0.3 * a), (round(tx), round(ty) - 4), max(1, round(4 * a)))
        if self.result is not False:
            ix, iy = round(self.x), round(GROUND - height(self.v, self.x) - 5)
            pygame.draw.circle(surf, P.shade(ION, 0.45), (ix, iy), 8)
            pygame.draw.circle(surf, ION, (ix, iy), 5)
            surf.fill(P.WHITE, (ix - 2, iy - 1, 5, 1))
            surf.fill(P.WHITE, (ix, iy - 3, 1, 5))
        self._strip(surf)
        if self.result is True:
            hint = "THE ION STAYED OUT!"
        elif self.result is False:
            hint = "LOST IN THE HOLE!"
        else:
            hint = "UP: RAISE THE ELECTRODE"
        blit_center(surf, outlined(hint, 8, P.WHITE), (W // 2, H - 9))
        result_overlay(surf, self.result, self.since_end, seed=43)

    def _hole(self, surf: pygame.Surface) -> None:
        x, y = round(self.hole[0]), round(self.hole[1])
        for k in range(3):
            a0 = self.t * (1.5 + k * 0.4) + k * 1.7
            r = 9 + k * 5
            pygame.draw.arc(surf, P.shade(HOLE_ARC, 0.9 - k * 0.2), (x - r, y - r, 2 * r, 2 * r), a0, a0 + math.pi * 0.9, 1)
        pygame.draw.circle(surf, (0, 0, 0), (x, y), CAPTURE - 1)
        pygame.draw.circle(surf, HOLE_RING, (x, y), CAPTURE - 1, 1)
        blit_center(surf, outlined("LOSS", 8, HOLE_RING), (x, y - 26))

    def _strip(self, surf: pygame.Surface) -> None:
        """Ion Surfer's electrode strip: gold plates, each with its voltage bar; the one you
        drive (under the hole) framed, with an arrow up to the curve."""
        surf.fill(STRIP, (0, GROUND, W, 30))
        surf.fill(STRIP_EDGE, (0, GROUND, W, 1))
        for i in range(N):
            x = round(i * EW) + 4
            w = round(EW) - 8
            surf.fill(GOLD if i == self.k else P.shade(GOLD, 0.55), (x, GROUND + 4, w, 8))
            lv = self.v[i] / (VMAX + 10)
            surf.fill(GRID, (x, GROUND + 15, w, 4))
            surf.fill(CURVE, (x, GROUND + 15, round(w * lv), 4))
        x = round(self.k * EW) + 4
        w = round(EW) - 8
        pygame.draw.rect(surf, P.WHITE, (x - 2, GROUND + 2, w + 4, 19), 1)
        cx = x + w // 2
        pygame.draw.polygon(surf, P.WHITE, [(cx, GROUND - 3), (cx - 3, GROUND + 1), (cx + 3, GROUND + 1)])
