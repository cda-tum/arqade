"""Classic Pong entities and physics. Pure data + pure update functions."""

from __future__ import annotations

import math
from dataclasses import dataclass

from quantum_pong.config import (
    BALL_MAX_BOUNCE_ANGLE_DEG,
    BALL_MAX_SPEED,
    BALL_SPEED_INCREMENT,
    BALL_START_SPEED,
    INTERNAL_HEIGHT,
    INTERNAL_WIDTH,
    PADDLE_SPEED,
)


@dataclass(frozen=True)
class Paddle:
    y: float  # top edge, internal-resolution px
    height: float


@dataclass(frozen=True)
class Ball:
    x: float
    y: float
    vx: float
    vy: float


def move_paddle(paddle: Paddle, direction: float, dt: float, field_height: int) -> Paddle:
    """direction: -1 (up), 0 (still), or 1 (down)."""
    new_y = paddle.y + direction * PADDLE_SPEED * dt
    max_y = field_height - paddle.height
    new_y = max(0.0, min(new_y, max_y))
    return Paddle(y=new_y, height=paddle.height)


def step_ball(ball: Ball, dt: float, field_height: int, radius: float) -> Ball:
    """Advance the ball and bounce it off the top/bottom walls."""
    x = ball.x + ball.vx * dt
    y = ball.y + ball.vy * dt
    vy = ball.vy
    if y - radius < 0:
        y = radius + (radius - y)
        vy = -vy
    elif y + radius > field_height:
        overshoot = (y + radius) - field_height
        y = field_height - radius - overshoot
        vy = -vy
    return Ball(x=x, y=y, vx=ball.vx, vy=vy)


def ball_within_paddle(ball_y: float, paddle: Paddle, grace: float = 0.0) -> bool:
    """grace extends the catch range on both edges (a small forgiveness zone
    so a paddle moved into place at the last instant still counts)."""
    return paddle.y - grace <= ball_y <= paddle.y + paddle.height + grace


def hit_offset_for(ball_y: float, paddle: Paddle) -> float:
    """Where the ball hit the paddle, from -1 (top edge) to +1 (bottom edge)."""
    return ((ball_y - paddle.y) / paddle.height) * 2 - 1


def serve_ball(direction: int) -> Ball:
    """A fresh ball at center field, traveling toward `direction` (+1 or -1)."""
    return Ball(
        x=INTERNAL_WIDTH / 2,
        y=INTERNAL_HEIGHT / 2,
        vx=direction * BALL_START_SPEED,
        vy=0.0,
    )


def reached_left_paddle_line(ball: Ball, paddle_x: float, paddle_width: float, radius: float) -> bool:
    return ball.vx < 0 and ball.x - radius <= paddle_x + paddle_width


def reached_right_paddle_line(ball: Ball, paddle_x: float, radius: float) -> bool:
    return ball.vx > 0 and ball.x + radius >= paddle_x


def resolve_ball_at_paddle(
    ball: Ball, paddle: Paddle, bounce_direction: int, grace: float = 0.0
) -> tuple[Ball, bool]:
    """If the ball is within the paddle's y-range (plus `grace`), bounce it;
    otherwise leave it untouched and report a miss."""
    if not ball_within_paddle(ball.y, paddle, grace):
        return ball, False
    offset = hit_offset_for(ball.y, paddle)
    return bounce_off_paddle(ball, hit_offset=offset, direction=bounce_direction), True


def bounce_off_paddle(ball: Ball, hit_offset: float, direction: int) -> Ball:
    """Reflect the ball off a paddle.

    hit_offset in [-1, 1]: where on the paddle it hit (top to bottom edge).
    direction: +1 or -1, the new horizontal travel direction.
    """
    hit_offset = max(-1.0, min(1.0, hit_offset))
    speed = math.hypot(ball.vx, ball.vy)
    speed = min(speed + BALL_SPEED_INCREMENT, BALL_MAX_SPEED)
    angle = math.radians(hit_offset * BALL_MAX_BOUNCE_ANGLE_DEG)
    vx = direction * speed * math.cos(angle)
    vy = speed * math.sin(angle)
    return Ball(x=ball.x, y=ball.y, vx=vx, vy=vy)
