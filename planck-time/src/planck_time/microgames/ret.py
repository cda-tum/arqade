"""RETURN! (from Quantum Pong): your white paddle is on the left. A ball comes from
the right, and on its way passes a Z gate in midfield, which bounces it as if off an
invisible horizontal wall: its vertical direction flips (Quantum Pong's Z). Move the
paddle to where the ball really arrives. The ball's path is not drawn ahead.

Every round is built so the Z matters: where the ball would arrive without the gate
is out of the paddle's reach, and so is where the paddle starts. Pong's catch grace
applies. (The module is ret.py: `return` is a keyword.)
"""

from __future__ import annotations

import pygame

from planck_time import palette as P
from planck_time.microgames.base import H, W, Microgame, PlayerInput, register
from planck_time.pixel import blit_center, font, outlined, result_overlay

FIELD_TOP, FIELD_BOTTOM = 8, H - 20     # the ball bounces off these; the hint sits below
BALL_R = 3
PADDLE_X = 10                           # the paddle's front face
PADDLE_W = 4
PADDLE_H = 26
PADDLE_START = (FIELD_TOP + FIELD_BOTTOM) / 2
PADDLE_SPEED = 150.0                    # px/s at full stick
GRACE = 3.0                             # Quantum Pong's PADDLE_CATCH_GRACE, scaled down
GATE = 18                               # the gate's square, px
GATE_X = 124
START_X = 232
VX = 66.0                               # px/s at level 0
STEP = 1 / 240                          # the trajectory's integration step


def q(c) -> tuple[int, int, int]:
    """A Quantum Pong colour snapped onto the GBA's 15-bit grid."""
    return tuple(min(248, round(v / 8) * 8) for v in c)


BACKGROUND = q((10, 10, 20))
MIDLINE = q((60, 60, 80))
WHITE = q((230, 230, 230))
Z_COLOR = q((200, 110, 255))            # Quantum Pong's GATE_COLORS["Z"]


def move(x: float, y: float, vx: float, vy: float, dt: float, gate, used: bool, z: bool):
    """One step of the ball: it moves, bounces off the top and bottom, and flips its
    vertical direction once as it crosses the Z gate's square. Returns the new state."""
    nx, ny = x + vx * dt, y + vy * dt
    if ny < FIELD_TOP + BALL_R:
        ny = 2 * (FIELD_TOP + BALL_R) - ny
        vy = -vy
    elif ny > FIELD_BOTTOM - BALL_R:
        ny = 2 * (FIELD_BOTTOM - BALL_R) - ny
        vy = -vy
    if z and not used and x > gate[0] >= nx and abs(ny - gate[1]) <= GATE / 2 + BALL_R:
        vy = -vy
        used = True
    return nx, ny, vx, vy, used


def trajectory(start, v, gate, z: bool) -> list[tuple[float, float]]:
    x, y = start
    vx, vy = v
    used = False
    out = []
    while x > PADDLE_X + BALL_R:
        x, y, vx, vy, used = move(x, y, vx, vy, STEP, gate, used, z)
        out.append((x, y))
    return out


def arrival(start, v, gate, z: bool) -> float:
    """Where the ball reaches the paddle's line, with or without the Z gate."""
    return trajectory(start, v, gate, z)[-1][1]


@register
class Return(Microgame):
    VERB = "RETURN!"
    INPUT = "stick"
    CAPTION = "Z flips the ball: gates change its path"

    def __init__(self, seed: int, level: int, duration: float) -> None:
        super().__init__(seed, level, duration)
        reach = PADDLE_H / 2 + GRACE + 4
        while True:
            y0 = self.rng.uniform(FIELD_TOP + 20, FIELD_BOTTOM - 20)
            vy = self.rng.choice((-1, 1)) * self.rng.uniform(22, 40) * self.speed
            vx = -VX * self.speed
            # the gate sits where the ball crosses midfield, so it always meets it
            path = trajectory((START_X, y0), (vx, vy), (-999, -999), z=False)
            gy = next(y for x, y in path if x <= GATE_X)
            if not FIELD_TOP + GATE / 2 + 4 <= gy <= FIELD_BOTTOM - GATE / 2 - 4:
                continue
            gate = (GATE_X, gy)
            real = arrival((START_X, y0), (vx, vy), gate, z=True)
            naive = arrival((START_X, y0), (vx, vy), gate, z=False)
            if abs(real - naive) > reach and abs(real - PADDLE_START) > reach:
                break
        self.ball_start = (START_X, y0)
        self.v_start = (vx, vy)
        self.gate = gate
        self.ball = [START_X, y0, vx, vy]
        self.used = False
        self.paddle = PADDLE_START
        self.target = real              # the bot's aim: it reads the real trajectory

    def step(self, dt: float, inp: PlayerInput) -> None:
        self.paddle += inp.stick[1] * PADDLE_SPEED * dt
        half = PADDLE_H / 2
        self.paddle = max(FIELD_TOP + half, min(FIELD_BOTTOM - half, self.paddle))
        x, y, vx, vy = self.ball
        sub = max(1, round(dt / STEP))
        for _ in range(sub):
            x, y, vx, vy, self.used = move(x, y, vx, vy, dt / sub, self.gate, self.used, True)
            if x <= PADDLE_X + BALL_R:
                self.ball = [PADDLE_X + BALL_R, y, vx, vy]
                if abs(y - self.paddle) <= half + GRACE:
                    self.win()
                else:
                    self.fail()
                return
        self.ball = [x, y, vx, vy]

    def bot(self) -> PlayerInput:
        diff = self.target - self.paddle
        return PlayerInput(stick=(0.0, max(-1.0, min(1.0, diff / 6))))

    def draw(self, surf: pygame.Surface) -> None:
        surf.fill(BACKGROUND)
        for y in range(FIELD_TOP, FIELD_BOTTOM, 6):
            surf.fill(MIDLINE, (W // 2, y, 1, 3))
        surf.fill(MIDLINE, (0, FIELD_TOP - 1, W, 1))
        surf.fill(MIDLINE, (0, FIELD_BOTTOM, W, 1))
        # the Z gate, as Quantum Pong draws it: a rounded square in its colour, a white
        # border, the letter in the background's colour; it stays lit once used
        rect = pygame.Rect(0, 0, GATE, GATE)
        rect.center = (round(self.gate[0]), round(self.gate[1]))
        color = Z_COLOR if not self.used or int(self.t * 10) % 2 else P.lighten(Z_COLOR, 0.4)
        pygame.draw.rect(surf, color, rect, border_radius=4)
        pygame.draw.rect(surf, WHITE, rect, 1, border_radius=4)
        label = font(8).render("Z", False, BACKGROUND)
        surf.blit(label, label.get_rect(center=(rect.centerx + 1, rect.centery + 1)))
        # the paddle and the ball
        pygame.draw.rect(surf, WHITE, (PADDLE_X - PADDLE_W, round(self.paddle - PADDLE_H / 2), PADDLE_W, PADDLE_H),
                         border_radius=1)
        bx, by = round(self.ball[0]), round(self.ball[1])
        pygame.draw.circle(surf, WHITE, (bx, by), BALL_R)
        pygame.draw.circle(surf, BACKGROUND, (bx, by), BALL_R, 1)
        if self.result is True and self.since_end < 0.25:      # Pong's catch flash
            r = BALL_R + round(self.since_end / 0.25 * 8)
            pygame.draw.circle(surf, P.WHITE, (bx, by), r, 1)
        if self.result is True:
            hint = "RETURNED!"
        elif self.result is False:
            hint = "THE Z FLIPPED IT!"
        else:
            hint = "Z FLIPS IT: CATCH THE BALL"
        blit_center(surf, outlined(hint, 8, P.WHITE), (W // 2, H - 9))
        result_overlay(surf, self.result, self.since_end, seed=37)
