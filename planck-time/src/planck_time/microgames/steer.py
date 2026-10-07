"""STEER!: a photon beam comes in from the left along the bench and hits a
mirror, which reflects it up towards the top of the screen. Stick x turns
the mirror: push right and the reflected beam swings right, left and it
swings left (stick x, because the target sits along the top, so the beam's
spot moves the way the stick is pushed). Keeping the beam on the detector's
window for 0.4 s wins; the detector's meter shows the hold.

The beam starts well clear of the detector, farther than the detector ever
drifts, so doing nothing loses. From level 1 the detector drifts from side
to side, wider and faster with every level.
"""

from __future__ import annotations

import math

import pygame

from planck_time import palette as P
from planck_time.microgames.base import H, W, Microgame, PlayerInput, register
from planck_time.pixel import backdrop, blit_center, dither, orb, outlined, result_overlay

EMIT = (16, 118)  # the emitter's nozzle
MIRROR = (120, 118)
BENCH_Y = 134
DET_Y = 22  # the detector's centre
DET_W, DET_H = 30, 16
FACE_Y = DET_Y + DET_H // 2  # its window, facing down: the beam has to cross it
LO, HI = math.radians(-165), math.radians(-15)  # the reflected beam always heads up
TURN = math.radians(80)  # beam radians per second at full stick, level 0
HOLD = 0.4
DRIFT_PX = 12  # px of drift amplitude per level
DRIFT_RATE = 1.0  # radians per second of the drift's sine, level 0


def face_x(angle: float) -> float:
    """Where a beam leaving the mirror at `angle` crosses the detector's window line."""
    return MIRROR[0] + (FACE_Y - MIRROR[1]) / math.tan(angle)


@register
class Steer(Microgame):
    VERB = "STEER!"
    INPUT = "stick"
    CAPTION = "Mirrors steer photons, which can carry qubits"

    def __init__(self, seed: int, level: int, duration: float) -> None:
        super().__init__(seed, level, duration)
        self.amp = DRIFT_PX * level
        self.x0 = self.rng.uniform(32 + self.amp, W - 32 - self.amp)
        self.phase = self.rng.uniform(0, 2 * math.pi)
        self.rate = DRIFT_RATE * self.speed
        # the beam starts farther from the detector than its drift ever reaches
        off = self.amp + DET_W / 2 + self.rng.uniform(35, 70)
        side = self.rng.choice((-1, 1))
        start = self.x0 + side * off
        self.angle = math.atan2(FACE_Y - MIRROR[1], start - MIRROR[0])
        self.held = 0.0
        self.backdrop = P.BACKDROPS[self.rng.randrange(len(P.BACKDROPS))]

    @property
    def det_x(self) -> float:
        return self.x0 + self.amp * math.sin(self.phase + self.rate * self.t)

    @property
    def on_target(self) -> bool:
        return abs(face_x(self.angle) - self.det_x) <= DET_W / 2 - 2

    def step(self, dt: float, inp: PlayerInput) -> None:
        turn = TURN * self.speed * max(-1.0, min(1.0, inp.stick[0])) * dt
        self.angle = max(LO, min(HI, self.angle + turn))
        if self.on_target:
            self.held += dt
            if self.held >= HOLD:
                self.win()
        else:
            self.held = 0.0

    def bot(self) -> PlayerInput:
        want = math.atan2(FACE_Y - MIRROR[1], self.det_x - MIRROR[0])
        return PlayerInput(stick=(max(-1.0, min(1.0, (want - self.angle) / math.radians(6))), 0.0))

    # --- drawing ----------------------------------------------------------------------

    def beam_end(self) -> tuple[float, float]:
        """Where the reflected beam stops: the detector's window, the detector's
        side, or the edge of the screen."""
        dx, dy = math.cos(self.angle), math.sin(self.angle)
        mx, my = MIRROR
        if self.on_target or self.result:
            return face_x(self.angle), FACE_Y
        t = (-2 - my) / dy
        if dx:
            t = min(t, ((W + 1 if dx > 0 else -2) - mx) / dx)
        end = (mx + t * dx, my + t * dy)
        body = pygame.Rect(0, 0, DET_W, DET_H)
        body.center = (round(self.det_x), DET_Y)
        hit = body.clipline(MIRROR, end)
        return hit[1] if hit else end

    def draw(self, surf: pygame.Surface) -> None:
        backdrop(surf, self.backdrop, self.t)
        mx, my = MIRROR
        dx, dy = math.cos(self.angle), math.sin(self.angle)

        # the bench, the emitter and the mirror's stand
        surf.fill(P.INK, (0, BENCH_Y - 1, W, 6))
        dither(surf, (0, BENCH_Y, W, 4), P.SLATE, P.NIGHT)
        surf.fill(P.MIST, (0, BENCH_Y, W, 1))
        surf.fill(P.INK, (mx - 2, my, 5, BENCH_Y - my))
        surf.fill(P.SLATE, (mx - 1, my, 3, BENCH_Y - my))
        surf.fill(P.INK, (mx - 9, BENCH_Y - 4, 19, 5))
        surf.fill(P.SLATE, (mx - 8, BENCH_Y - 3, 17, 3))
        emitter = pygame.Rect(0, 0, 18, 18)
        emitter.midright = (EMIT[0] - 2, EMIT[1])
        pygame.draw.rect(surf, P.INK, emitter.inflate(2, 2), border_radius=3)
        pygame.draw.rect(surf, P.VIOLET, emitter, border_radius=3)
        surf.fill(P.lighten(P.VIOLET, 0.5), (emitter.x + 2, emitter.y + 2, 6, 1))
        surf.fill(P.INK, (EMIT[0] - 3, EMIT[1] - 3, 5, 7))
        surf.fill(P.MIST, (EMIT[0] - 2, EMIT[1] - 2, 3, 5))
        surf.fill(P.INK, (emitter.centerx - 3, emitter.bottom, 7, BENCH_Y - emitter.bottom))

        # the detector: a box with a window underneath, a hold meter, target brackets
        det = pygame.Rect(0, 0, DET_W, DET_H)
        det.center = (round(self.det_x), DET_Y)
        lit = self.on_target or self.result is True
        pygame.draw.rect(surf, P.INK, det.inflate(2, 2), border_radius=3)
        pygame.draw.rect(surf, P.SLATE, det, border_radius=3)
        surf.fill(P.lighten(P.SLATE, 0.4), (det.x + 2, det.y + 1, det.width - 4, 1))
        meter = pygame.Rect(det.x + 3, det.y + 3, det.width - 6, 5)
        surf.fill(P.INK, meter)
        k = 1.0 if self.result else min(1.0, self.held / HOLD)
        if k > 0:
            surf.fill(P.GOOD, (meter.x, meter.y, round(meter.width * k), meter.height))
        window = pygame.Rect(det.x + 5, det.bottom - 4, det.width - 10, 4)
        surf.fill(P.GOOD if lit else P.NIGHT, window)
        if lit:
            surf.fill(P.WHITE, (window.x + 2, window.y, 4, 1))
        if self.result is None:
            gap = 4 + round(1.5 * math.sin(self.t * 10))
            box = det.inflate(2 * gap, 2 * gap)
            for cx, cy, sx, sy in ((box.left, box.top, 1, 1), (box.right - 1, box.top, -1, 1),
                                   (box.left, box.bottom - 1, 1, -1), (box.right - 1, box.bottom - 1, -1, -1)):
                surf.fill(P.GOLD, (min(cx, cx + 5 * sx), cy, 6, 2))
                surf.fill(P.GOLD, (cx, min(cy, cy + 5 * sy), 2, 6))

        # the beam, in to the mirror and back out
        end = self.beam_end()
        dead = self.result is False
        glow, mid, core = ((P.SLATE, P.MIST, P.MIST) if dead else
                           (P.shade(P.PINK, 0.8), P.lighten(P.PINK, 0.4), P.WHITE))
        for a, b in ((EMIT, MIRROR), (MIRROR, end)):
            pygame.draw.line(surf, glow, a, b, 5)
            pygame.draw.line(surf, mid, a, b, 3)
            pygame.draw.line(surf, core, a, b, 1)
        if not dead:  # photons running along it
            first = mx - EMIT[0]
            length = first + math.hypot(end[0] - mx, end[1] - my)
            s = (self.t * 140) % 14
            while s < length:
                if s < first:
                    p = (EMIT[0] + s, EMIT[1])
                else:
                    p = (mx + (s - first) * dx, my + (s - first) * dy)
                surf.fill(P.WHITE, (round(p[0]) - 1, round(p[1]) - 1, 3, 3))
                s += 14
        if lit:
            pygame.draw.circle(surf, P.lighten(P.GOOD, 0.5), (round(end[0]), round(end[1])), 5, 1)
        if self.result and self.since_end < 0.4:  # the detector clicks: a green ring popping off
            pygame.draw.circle(surf, P.GOOD, det.center, round(18 + 60 * self.since_end), 2)

        # the mirror: a silver face towards the beams, a dark back
        tx, ty = math.cos(self.angle / 2), math.sin(self.angle / 2)
        nx, ny = dx - 1, dy
        n = math.hypot(nx, ny)
        nx, ny = nx / n, ny / n
        half = 14
        a = (mx - tx * half, my - ty * half)
        b = (mx + tx * half, my + ty * half)
        back = lambda p, k: (p[0] - nx * k, p[1] - ny * k)  # noqa: E731
        pygame.draw.line(surf, P.INK, back(a, 2), back(b, 2), 7)
        pygame.draw.line(surf, P.SLATE, back(a, 2), back(b, 2), 3)
        pygame.draw.line(surf, P.MIST, a, b, 3)
        pygame.draw.line(surf, P.WHITE, a, b, 1)
        orb(surf, back(MIRROR, 4), 2, P.GOLD)

        blit_center(surf, outlined("BEAM INTO THE DETECTOR", 8, P.WHITE), (W // 2, H - 12))
        result_overlay(surf, self.result, self.since_end, seed=11)
