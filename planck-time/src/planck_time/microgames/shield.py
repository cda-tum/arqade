"""SHIELD!: steer a fragile qubit round a walled arena while noise particles
bounce about. Win if nothing touches it until the time is up; one touch and
it decoheres.

Every particle starts on the arena's edge, well away from the qubit, and
one of them (it looks like the rest) heads straight for the qubit's starting
point, arriving long before the end. So standing still always loses, and
the only way to win is to move.
"""

from __future__ import annotations

import math

import pygame

from planck_time import palette as P
from planck_time.microgames.base import H, W, Microgame, PlayerInput, register
from planck_time.pixel import backdrop, blit_center, orb, outlined, result_overlay

LEFT, TOP, RIGHT, BOTTOM = 8, 8, W - 8, H - 22  # the arena's walls
START = ((LEFT + RIGHT) / 2, (TOP + BOTTOM) / 2)
QUBIT_R = 6
NOISE_R = 3
HIT = QUBIT_R + NOISE_R - 1  # centres closer than this touch (a pixel of mercy)
QUBIT_SPEED = 100  # px per second, at full stick
NOISE_SPEED = 40  # px per second at level 0
NOISE_COUNT = 4  # at level 0, plus one per level...
NOISE_MAX = 9  # ...up to this

# the bot's lookahead: candidate directions, and how far ahead it simulates
BOT_DIRS = [(0.0, 0.0)] + [(math.cos(2 * math.pi * i / 16), math.sin(2 * math.pi * i / 16)) for i in range(16)]
BOT_DT = 0.04
BOT_STEPS = 15


def edge_point(angle: float) -> tuple[float, float]:
    """Where a ray from START at `angle` meets the arena's edge (inset for the particle)."""
    dx, dy = math.cos(angle), math.sin(angle)
    hw, hh = (RIGHT - LEFT) / 2 - NOISE_R - 1, (BOTTOM - TOP) / 2 - NOISE_R - 1
    k = min(hw / abs(dx) if dx else math.inf, hh / abs(dy) if dy else math.inf)
    return START[0] + dx * k, START[1] + dy * k


def bounce(p: list[float], dt: float) -> None:
    """Move a particle [x, y, vx, vy] for dt, bouncing off the walls."""
    p[0] += p[2] * dt
    p[1] += p[3] * dt
    if p[0] < LEFT + NOISE_R:
        p[0], p[2] = LEFT + NOISE_R, abs(p[2])
    elif p[0] > RIGHT - NOISE_R:
        p[0], p[2] = RIGHT - NOISE_R, -abs(p[2])
    if p[1] < TOP + NOISE_R:
        p[1], p[3] = TOP + NOISE_R, abs(p[3])
    elif p[1] > BOTTOM - NOISE_R:
        p[1], p[3] = BOTTOM - NOISE_R, -abs(p[3])


def clamp_qubit(x: float, y: float) -> tuple[float, float]:
    return (max(LEFT + QUBIT_R, min(RIGHT - QUBIT_R, x)),
            max(TOP + QUBIT_R, min(BOTTOM - QUBIT_R, y)))


@register
class Shield(Microgame):
    VERB = "SHIELD!"
    INPUT = "stick"
    CAPTION = "Noise destroys quantum states (decoherence)"

    def __init__(self, seed: int, level: int, duration: float) -> None:
        super().__init__(seed, level, duration)
        self.x, self.y = START
        self.noise = []  # [x, y, vx, vy]
        count = min(NOISE_MAX, NOISE_COUNT + level)
        for i in range(count):
            v = NOISE_SPEED * self.speed * self.rng.uniform(0.85, 1.15)
            angle = self.rng.uniform(0, 2 * math.pi)
            x, y = edge_point(angle)
            # the first one aims dead at the start; the rest head inwards, give or take
            heading = angle + math.pi + (0 if i == 0 else self.rng.uniform(-1.0, 1.0))
            self.noise.append([x, y, v * math.cos(heading), v * math.sin(heading)])
        self.hit_by: list[float] | None = None
        self.backdrop = P.BACKDROPS[self.rng.randrange(len(P.BACKDROPS))]

    def step(self, dt: float, inp: PlayerInput) -> None:
        sx, sy = inp.stick
        n = math.hypot(sx, sy)
        if n > 1:
            sx, sy = sx / n, sy / n
        self.x, self.y = clamp_qubit(self.x + sx * QUBIT_SPEED * dt, self.y + sy * QUBIT_SPEED * dt)
        for p in self.noise:
            bounce(p, dt)
            if math.hypot(p[0] - self.x, p[1] - self.y) < HIT:
                self.hit_by = p
                self.fail()
                return

    def timeout(self) -> None:
        self.win()  # it survived

    def bot(self) -> PlayerInput:
        """Try each direction for 0.6 s against where the noise will be, and take
        the one that keeps the most room (and stays off the walls)."""
        future = []
        ps = [p[:] for p in self.noise]
        for _ in range(BOT_STEPS):
            for p in ps:
                bounce(p, BOT_DT)
            future.append([(p[0], p[1]) for p in ps])
        best, best_dir = -math.inf, (0.0, 0.0)
        for dx, dy in BOT_DIRS:
            x, y = self.x, self.y
            room = math.inf
            for k, spots in enumerate(future):
                x, y = clamp_qubit(x + dx * QUBIT_SPEED * BOT_DT, y + dy * QUBIT_SPEED * BOT_DT)
                near = min(math.hypot(px - x, py - y) for px, py in spots)
                if near < HIT + 4:  # a touch on this path: the later the better, but never good
                    room = k - 1000
                    break
                room = min(room, near)
            wall = min(x - LEFT, RIGHT - x, y - TOP, BOTTOM - y)
            score = min(room, 30) + 0.6 * min(wall, 40)
            if score > best:
                best, best_dir = score, (dx, dy)
        return PlayerInput(stick=best_dir)

    # --- drawing ----------------------------------------------------------------------

    def draw(self, surf: pygame.Surface) -> None:
        backdrop(surf, self.backdrop, self.t)
        arena = pygame.Rect(LEFT, TOP, RIGHT - LEFT, BOTTOM - TOP)
        pygame.draw.rect(surf, P.INK, arena.inflate(6, 6), 3, border_radius=4)
        pygame.draw.rect(surf, P.MIST, arena.inflate(2, 2), 1, border_radius=3)

        # the noise: red sparks with flickering spikes
        flick = int(self.t * 14) % 2
        for i, (x, y, _, _) in enumerate(self.noise):
            cx, cy = round(x), round(y)
            spikes = ((5, 0), (-5, 0), (0, 5), (0, -5)) if (i + flick) % 2 else ((4, 4), (-4, -4), (4, -4), (-4, 4))
            for dx, dy in spikes:
                pygame.draw.line(surf, P.INK, (cx, cy), (cx + dx, cy + dy), 3)
                pygame.draw.line(surf, P.PINK, (cx, cy), (cx + dx, cy + dy), 1)
            orb(surf, (cx, cy), NOISE_R, P.BAD)

        # the qubit in its bubble: grey and cracked once it decoheres
        qx, qy = round(self.x), round(self.y)
        if self.result is False:
            k = min(1.0, self.since_end / 0.3)
            pygame.draw.circle(surf, P.BAD, (qx, qy), round(QUBIT_R + 4 + 14 * k), 2)
            orb(surf, (qx, qy), QUBIT_R, P.SLATE)
            pygame.draw.line(surf, P.INK, (qx - 3, qy - 5), (qx + 1, qy), 2)
            pygame.draw.line(surf, P.INK, (qx + 1, qy), (qx - 1, qy + 5), 2)
        else:
            won = self.result is True
            bubble = QUBIT_R + 4 + (round(math.sin(self.t * 8)) if not won else 0)
            pygame.draw.circle(surf, P.INK, (qx, qy), bubble + 1, 1)
            pygame.draw.circle(surf, P.GOLD if won else P.SKY, (qx, qy), bubble, 1)
            orb(surf, (qx, qy), QUBIT_R, P.TEAL, glow=won)
        blit_center(surf, outlined("DODGE THE NOISE", 8, P.WHITE), (W // 2, H - 9))
        result_overlay(surf, self.result, self.since_end, seed=13)
