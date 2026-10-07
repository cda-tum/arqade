"""CORRECT!: a Pauli Invaders crossover. One error invader, an X (red), a Z
(blue) or a Y (purple), wavers down towards the logical error threshold the
way Pauli Invaders' minions do. Your colour-code ship's shot colour cycles
X, Z, Y on a beat. Slide under the invader with the stick and fire with A
while your colour matches it: the matching Pauli corrects the error and
wins. A shot in the wrong colour that hits it fails, and so does letting it
reach the threshold. A shot that misses just flies off, and you can fire
again once it has gone.

A shot keeps the colour it was fired in. The beat starts on a colour that
doesn't match, so the first chance comes a beat in (0.7 s at level 0, and
every colour lasts that long), and the invader falls slowly enough for at
least two whole cycles. The invader starts well to one side of the ship.
Higher levels beat faster and sway the invader wider.
"""

from __future__ import annotations

import math
import random

import pygame

from planck_time import palette as P
from planck_time.microgames.base import IDLE, H, W, Microgame, PlayerInput, register
from planck_time.pixel import blit_center, outlined, result_overlay

ORDER = ("X", "Z", "Y")  # the colour code ship's cycle, as in Pauli Invaders
COL = {k: P.GATE[k] for k in ORDER}
SPACE = (8, 8, 24)  # Pauli Invaders' near-black sky...
ZONE = (8, 16, 24)  # ...and the darker band the ship flies in
BEAT = 0.7  # seconds each colour lasts at level 0
FALL = 0.95  # of the play time, for the invader to reach the threshold
THRESHOLD = 110  # the logical error threshold's y
SHIP_Y = 129
SHIP_R = 14  # the triangle's centre-to-corner size
SHIP_SPEED = 140  # px per second at full stick
SHOT_SPEED = 260
SHOT = (3, 10)
SPAWN_Y = 12  # the invader's centre at the start
SWAY = 18  # px either side at level 0...
SWAY_PER_LEVEL = 6  # ...wider by this per level...
SWAY_MAX = 40  # ...up to this
SWAY_RATE = 1.4  # radians per second at level 0 (Pauli Invaders' minions)
PX = 3  # the invader's sprite is 10x8 cells of this many pixels
SPRITE = (
    ("...####...", ".########.", "##########", "##########", "##########", ".########.", ".#.#..#.#.",
     "#..#..#..#"),
    ("...####...", ".########.", "##########", "##########", "##########", ".########.", "#.#.##.#.#",
     ".#......#."),
)
EW, EH = 10 * PX, 8 * PX
BOT_THINK = 0.3


def blend(c, k: float) -> tuple[int, int, int]:
    """A colour faded k of the way into the sky, snapped to the GBA grid."""
    return tuple(round((s + (a - s) * k) / 8) * 8 for a, s in zip(c, SPACE))


def invader(surf: pygame.Surface, x: float, y: float, kind: str, frame: int, flash: bool = False) -> None:
    """Pauli Invaders' error sprite, with its letter on its body in the sky's colour."""
    color = P.WHITE if flash else COL[kind]
    x0, y0 = round(x - EW / 2), round(y - EH / 2)
    for r, row in enumerate(SPRITE[frame]):
        for c, cell in enumerate(row):
            if cell == "#":
                surf.fill(color, (x0 + c * PX, y0 + r * PX, PX, PX))
    blit_center(surf, outlined(kind, 8, SPACE, outline=color, shadow=False), (x0 + EW // 2 + 1, y0 + 10))


def ship(surf: pygame.Surface, x: float, y: float, active: str) -> None:
    """P1's colour code triangle: three faces X, Z and Y, the active one lit and the
    others dim, its rim in the active colour, a white qubit on every corner."""
    s = SHIP_R
    p = [(x, y - s), (x + s * 0.87, y + s * 0.5), (x - s * 0.87, y + s * 0.5)]
    c = (x, y)

    def mid(a, b):
        return ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2)

    faces = (("X", [p[0], mid(p[0], p[1]), c, mid(p[2], p[0])]),
             ("Z", [p[1], mid(p[1], p[2]), c, mid(p[0], p[1])]),
             ("Y", [p[2], mid(p[2], p[0]), c, mid(p[1], p[2])]))
    for kind, poly in faces:
        pygame.draw.polygon(surf, COL[kind] if kind == active else blend(COL[kind], 0.3), poly)
    pygame.draw.polygon(surf, COL[active], p, 2)
    for qx, qy in p:
        surf.fill(P.WHITE, (round(qx) - 2, round(qy) - 2, 4, 4))


def dashed(surf: pygame.Surface, color, y: int, dash: int = 4, gap: int = 4) -> None:
    for x in range(0, W, dash + gap):
        surf.fill(color, (x, y, dash, 1))


@register
class Correct(Microgame):
    VERB = "CORRECT!"
    INPUT = "stick+a"
    CAPTION = "Only the matching Pauli corrects it"

    def __init__(self, seed: int, level: int, duration: float) -> None:
        super().__init__(seed, level, duration)
        self.kind = self.rng.choice(ORDER)
        target = ORDER.index(self.kind)
        # start on a colour that doesn't match, so the first chance is a beat or two in
        self.start = (target + self.rng.choice((1, 2))) % 3
        self.beat = BEAT / self.speed
        self.amp = min(SWAY_MAX, SWAY + SWAY_PER_LEVEL * level)
        self.rate = SWAY_RATE * self.speed
        self.phase = self.rng.uniform(0, 2 * math.pi)
        side = self.rng.choice((-1, 1))
        self.x0 = W / 2 + side * self.rng.uniform(60, 76)  # well to one side of the ship
        self.vy = (THRESHOLD - EH / 2 - SPAWN_Y) / (FALL * duration)
        self.ship_x = W / 2
        self.shot: list[float] | None = None  # [x, y] of the shot in flight
        self.shot_kind = ""
        self.hit_at: tuple[float, float] | None = None
        self.how = ""  # "fixed", "wrong" or "threshold", once it ends
        self.inv_x, self.inv_y = self.invader_at(0.0)

    # --- the rules ----------------------------------------------------------------------

    def color_at(self, t: float) -> str:
        return ORDER[(self.start + int(t / self.beat)) % 3]

    @property
    def color(self) -> str:
        return self.color_at(self.t)

    def invader_at(self, t: float) -> tuple[float, float]:
        x = self.x0 + self.amp * math.sin(self.rate * t + self.phase)
        return max(EW / 2 + 4, min(W - EW / 2 - 4, x)), SPAWN_Y + self.vy * t

    def step(self, dt: float, inp: PlayerInput) -> None:
        now = self.t + dt
        self.inv_x, self.inv_y = self.invader_at(now)
        self.ship_x = max(SHIP_R, min(W - SHIP_R, self.ship_x + inp.stick[0] * SHIP_SPEED * dt))
        if self.shot is not None:
            self.shot[1] -= SHOT_SPEED * dt
            sx, sy = self.shot
            if abs(sx - self.inv_x) < EW / 2 + 2 and abs(sy - self.inv_y) < EH / 2 + 4:
                self.hit_at = (sx, sy)
                self.shot = None
                if self.shot_kind == self.kind:
                    self.how = "fixed"
                    self.win()
                else:
                    self.how = "wrong"
                    self.fail()
                return
            if sy < -SHOT[1]:
                self.shot = None
        if self.inv_y + EH / 2 >= THRESHOLD:
            self.how = "threshold"
            self.fail()
            return
        if inp.a and self.shot is None:
            self.shot = [self.ship_x, SHIP_Y - SHIP_R]
            self.shot_kind = self.color

    def bot(self) -> PlayerInput:
        if self.t < BOT_THINK:
            return IDLE
        # aim where the invader will be when a shot fired now would reach it
        flight = max(0.0, (SHIP_Y - SHIP_R - self.inv_y) / (SHOT_SPEED + self.vy))
        aim, _ = self.invader_at(self.t + flight)
        gap = aim - self.ship_x
        stick = max(-1.0, min(1.0, gap / 10))
        fire = abs(gap) < 4 and self.color == self.kind and self.shot is None
        return PlayerInput(stick=(stick, 0.0), a=fire, a_held=fire)

    # --- drawing ----------------------------------------------------------------------

    def draw(self, surf: pygame.Surface) -> None:
        surf.fill(SPACE)
        surf.fill(ZONE, (0, THRESHOLD + 2, W, SHIP_Y + SHIP_R + 6 - THRESHOLD))
        # the threshold, flashing red once the error has crossed it
        crossed = self.how == "threshold"
        line = P.BAD if crossed and int(self.since_end * 8) % 2 == 0 else blend(COL["X"], 0.45)
        dashed(surf, line, THRESHOLD)
        label = outlined("THRESHOLD", 8, blend(COL["X"], 0.55), outline=SPACE, shadow=False)
        surf.blit(label, (W - label.get_width() - 3, THRESHOLD - label.get_height()))

        # the colour cycle, as Pauli Invaders' HUD shows it: the lit chip is your colour
        active = self.color_at(self.ended_at if self.ended_at is not None else self.t)
        for i, kind in enumerate(ORDER):
            r = pygame.Rect(6 + i * 20, 6, 16, 12)
            lit = kind == active
            if lit:
                pygame.draw.rect(surf, P.WHITE, r.inflate(4, 4), 2)
            surf.fill(COL[kind] if lit else blend(COL[kind], 0.3), r)
            blit_center(surf, outlined(kind, 8, SPACE, outline=COL[kind] if lit else blend(COL[kind], 0.3),
                                       shadow=False), (r.centerx + 1, r.centery + 1))

        frame = int(self.t * 2) % 2
        if self.how == "fixed":  # corrected: it bursts in its own colour
            rng = random.Random(7)
            k = self.since_end
            for _ in range(16):
                a = rng.uniform(0, 2 * math.pi)
                v = rng.uniform(40, 110)
                x, y = self.inv_x + math.cos(a) * v * k, self.inv_y + math.sin(a) * v * k
                surf.fill(COL[self.kind] if rng.random() < 0.7 else P.WHITE, (round(x), round(y), 3, 3))
            if k < 0.12:
                invader(surf, self.inv_x, self.inv_y, self.kind, frame, flash=True)
        else:
            flash = self.how == "wrong" and int(self.since_end * 10) % 2 == 0
            invader(surf, self.inv_x, self.inv_y, self.kind, frame, flash=flash)
            if self.how == "wrong" and self.hit_at:  # it bounces off: grey sparks
                rng = random.Random(3)
                hx, hy = self.hit_at
                k = min(self.since_end, 0.4)
                for _ in range(6):
                    a = rng.uniform(0.2, math.pi - 0.2)
                    surf.fill(P.MIST, (round(hx + math.cos(a) * 50 * k), round(hy + math.sin(a) * 50 * k), 2, 2))

        if self.shot is not None:
            sx, sy = self.shot
            c = COL[self.shot_kind]
            surf.fill(P.lighten(c, 0.3), (round(sx) - 2, round(sy) - SHOT[1] // 2 - 1, SHOT[0] + 2, SHOT[1] + 2))
            surf.fill(c, (round(sx) - 1, round(sy) - SHOT[1] // 2, SHOT[0], SHOT[1]))
        ship(surf, self.ship_x, SHIP_Y, active)
        blit_center(surf, outlined("A WHEN YOUR COLOUR MATCHES", 8, P.WHITE), (W // 2, H - 9))
        result_overlay(surf, self.result, self.since_end, seed=13)
