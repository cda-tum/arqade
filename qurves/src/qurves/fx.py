"""Particles, measurement rings and screen shake. Purely cosmetic: the
renderer feeds it from rules and match events and draws it on top."""

from __future__ import annotations

import math
import random

import pygame


def _scaled(color, k: float) -> tuple[int, int, int]:
    return tuple(max(0, min(255, round(c * k))) for c in color)


class Fx:
    MAX_DISSOLVE = 48

    def __init__(self, rng: random.Random | None = None) -> None:
        self.rng = rng or random.Random()
        self.particles: list[list] = []  # [x, y, vx, vy, life, max_life, color]
        self.rings: list[list] = []  # [x, y, life, max_life, color]
        self.shake = 0.0

    def clear(self) -> None:
        self.particles.clear()
        self.rings.clear()
        self.shake = 0.0

    def burst(self, pos, color, count: int = 40, speed: float = 160.0, life: float = 0.6) -> None:
        x, y = pos
        for _ in range(count):
            angle = self.rng.uniform(0, 2 * math.pi)
            v = self.rng.uniform(0.2, 1.0) * speed
            t = self.rng.uniform(0.5, 1.0) * life
            self.particles.append([x, y, math.cos(angle) * v, math.sin(angle) * v, t, t, color])

    def dissolve(self, points, color) -> None:
        """Sparks drifting up off a dissolving trail, sampled from its cells."""
        points = list(points)
        if len(points) > self.MAX_DISSOLVE:
            points = self.rng.sample(points, self.MAX_DISSOLVE)
        for x, y in points:
            t = self.rng.uniform(0.5, 0.9)
            self.particles.append([
                x + self.rng.uniform(-2, 2), y,
                self.rng.uniform(-15, 15), self.rng.uniform(-55, -15), t, t, color,
            ])

    def ring(self, pos, color, life: float = 0.45) -> None:
        self.rings.append([pos[0], pos[1], life, life, color])

    def kick(self, amount: float) -> None:
        self.shake = max(self.shake, amount)

    def update(self, dt: float) -> None:
        damping = max(0.0, 1.0 - 2.5 * dt)
        alive = []
        for p in self.particles:
            p[4] -= dt
            if p[4] > 0:
                p[0] += p[2] * dt
                p[1] += p[3] * dt
                p[2] *= damping
                p[3] *= damping
                alive.append(p)
        self.particles = alive
        for r in self.rings:
            r[2] -= dt
        self.rings = [r for r in self.rings if r[2] > 0]
        self.shake = max(0.0, self.shake - 30.0 * dt)

    def offset(self) -> tuple[int, int]:
        if self.shake <= 0:
            return (0, 0)
        return (round(self.rng.uniform(-self.shake, self.shake)),
                round(self.rng.uniform(-self.shake, self.shake)))

    def draw(self, surface: pygame.Surface) -> None:
        for x, y, _vx, _vy, life, max_life, color in self.particles:
            k = life / max_life
            size = 2 if k > 0.5 else 1
            surface.fill(_scaled(color, k), (round(x), round(y), size, size), special_flags=pygame.BLEND_ADD)
        for x, y, life, max_life, color in self.rings:
            k = life / max_life
            pygame.draw.circle(surface, _scaled(color, k), (round(x), round(y)), round(4 + (1 - k) * 28), 2)
