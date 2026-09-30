import math

import pytest

from quantum_pong.pong import (
    Ball,
    Paddle,
    ball_within_paddle,
    bounce_off_paddle,
    hit_offset_for,
    move_paddle,
    reached_left_paddle_line,
    reached_right_paddle_line,
    resolve_ball_at_paddle,
    serve_ball,
    step_ball,
)


def test_move_paddle_moves_down_by_speed_times_dt():
    paddle = Paddle(y=50.0, height=40)
    moved = move_paddle(paddle, direction=1, dt=1.0, field_height=270)
    assert moved.y == pytest.approx(50.0 + moved_speed_for(dt=1.0))


def moved_speed_for(dt: float) -> float:
    from quantum_pong.config import PADDLE_SPEED

    return PADDLE_SPEED * dt


def test_move_paddle_clamps_to_top_of_field():
    paddle = Paddle(y=2.0, height=40)
    moved = move_paddle(paddle, direction=-1, dt=1.0, field_height=270)
    assert moved.y == 0.0


def test_move_paddle_clamps_to_bottom_of_field():
    paddle = Paddle(y=268.0, height=40)
    moved = move_paddle(paddle, direction=1, dt=1.0, field_height=270)
    assert moved.y == 270 - 40


def test_move_paddle_direction_zero_does_not_move():
    paddle = Paddle(y=100.0, height=40)
    moved = move_paddle(paddle, direction=0, dt=1.0, field_height=270)
    assert moved.y == 100.0


def test_step_ball_moves_in_a_straight_line_with_no_wall_contact():
    ball = Ball(x=100.0, y=100.0, vx=50.0, vy=20.0)
    moved = step_ball(ball, dt=1.0, field_height=270, radius=4)
    assert moved.x == pytest.approx(150.0)
    assert moved.y == pytest.approx(120.0)
    assert moved.vy == pytest.approx(20.0)


def test_step_ball_bounces_off_top_wall():
    ball = Ball(x=100.0, y=3.0, vx=0.0, vy=-20.0)
    moved = step_ball(ball, dt=1.0, field_height=270, radius=4)
    assert moved.vy > 0  # reflected
    assert moved.y >= 4  # stayed inside the field (radius clearance)


def test_step_ball_bounces_off_bottom_wall():
    ball = Ball(x=100.0, y=267.0, vx=0.0, vy=20.0)
    moved = step_ball(ball, dt=1.0, field_height=270, radius=4)
    assert moved.vy < 0  # reflected
    assert moved.y <= 270 - 4  # stayed inside the field


def test_bounce_off_paddle_center_hit_goes_straight_horizontal():
    ball = Ball(x=10.0, y=100.0, vx=-140.0, vy=0.0)
    bounced = bounce_off_paddle(ball, hit_offset=0.0, direction=1)
    assert bounced.vx > 0
    assert bounced.vy == pytest.approx(0.0, abs=1e-9)


def test_bounce_off_paddle_edge_hit_deflects_at_max_angle():
    from quantum_pong.config import BALL_MAX_BOUNCE_ANGLE_DEG

    ball = Ball(x=10.0, y=100.0, vx=-140.0, vy=0.0)
    bounced = bounce_off_paddle(ball, hit_offset=1.0, direction=1)
    speed = math.hypot(bounced.vx, bounced.vy)
    angle = math.degrees(math.atan2(bounced.vy, bounced.vx))
    assert angle == pytest.approx(BALL_MAX_BOUNCE_ANGLE_DEG)
    assert speed > 140.0


def test_ball_within_paddle_is_true_inside_range():
    paddle = Paddle(y=100.0, height=40.0)
    assert ball_within_paddle(ball_y=110.0, paddle=paddle) is True


def test_ball_within_paddle_is_true_at_exact_edges():
    paddle = Paddle(y=100.0, height=40.0)
    assert ball_within_paddle(ball_y=100.0, paddle=paddle) is True
    assert ball_within_paddle(ball_y=140.0, paddle=paddle) is True


def test_ball_within_paddle_is_false_outside_range():
    paddle = Paddle(y=100.0, height=40.0)
    assert ball_within_paddle(ball_y=99.0, paddle=paddle) is False
    assert ball_within_paddle(ball_y=141.0, paddle=paddle) is False


def test_ball_within_paddle_grace_extends_catch_range_on_both_edges():
    paddle = Paddle(y=100.0, height=40.0)
    assert ball_within_paddle(ball_y=94.0, paddle=paddle, grace=8.0) is True
    assert ball_within_paddle(ball_y=146.0, paddle=paddle, grace=8.0) is True


def test_ball_within_paddle_grace_still_excludes_far_misses():
    paddle = Paddle(y=100.0, height=40.0)
    assert ball_within_paddle(ball_y=80.0, paddle=paddle, grace=8.0) is False
    assert ball_within_paddle(ball_y=160.0, paddle=paddle, grace=8.0) is False


def test_ball_within_paddle_defaults_to_no_grace():
    paddle = Paddle(y=100.0, height=40.0)
    assert ball_within_paddle(ball_y=99.0, paddle=paddle) is False


def test_bounce_off_paddle_increases_speed_up_to_cap():
    from quantum_pong.config import BALL_MAX_SPEED

    ball = Ball(x=10.0, y=100.0, vx=-BALL_MAX_SPEED, vy=0.0)
    bounced = bounce_off_paddle(ball, hit_offset=0.0, direction=1)
    speed = math.hypot(bounced.vx, bounced.vy)
    assert speed == pytest.approx(BALL_MAX_SPEED)


def test_hit_offset_for_center_of_paddle_is_zero():
    paddle = Paddle(y=100.0, height=40.0)
    assert hit_offset_for(ball_y=120.0, paddle=paddle) == pytest.approx(0.0)


def test_hit_offset_for_top_edge_is_minus_one():
    paddle = Paddle(y=100.0, height=40.0)
    assert hit_offset_for(ball_y=100.0, paddle=paddle) == pytest.approx(-1.0)


def test_hit_offset_for_bottom_edge_is_plus_one():
    paddle = Paddle(y=100.0, height=40.0)
    assert hit_offset_for(ball_y=140.0, paddle=paddle) == pytest.approx(1.0)


def test_serve_ball_travels_toward_given_direction():
    from quantum_pong.config import BALL_START_SPEED, INTERNAL_HEIGHT, INTERNAL_WIDTH

    ball = serve_ball(direction=1)
    assert ball.x == pytest.approx(INTERNAL_WIDTH / 2)
    assert ball.y == pytest.approx(INTERNAL_HEIGHT / 2)
    assert ball.vx == pytest.approx(BALL_START_SPEED)
    assert ball.vy == pytest.approx(0.0)

    ball = serve_ball(direction=-1)
    assert ball.vx == pytest.approx(-BALL_START_SPEED)


def test_reached_left_paddle_line_true_when_crossing_threshold_moving_left():
    ball = Ball(x=20.0, y=100.0, vx=-140.0, vy=0.0)
    assert reached_left_paddle_line(ball, paddle_x=16.0, paddle_width=8.0, radius=4.0)


def test_reached_left_paddle_line_false_when_moving_away():
    ball = Ball(x=20.0, y=100.0, vx=140.0, vy=0.0)
    assert not reached_left_paddle_line(ball, paddle_x=16.0, paddle_width=8.0, radius=4.0)


def test_reached_left_paddle_line_false_when_not_yet_at_threshold():
    ball = Ball(x=100.0, y=100.0, vx=-140.0, vy=0.0)
    assert not reached_left_paddle_line(ball, paddle_x=16.0, paddle_width=8.0, radius=4.0)


def test_reached_right_paddle_line_true_when_crossing_threshold_moving_right():
    ball = Ball(x=455.0, y=100.0, vx=140.0, vy=0.0)
    assert reached_right_paddle_line(ball, paddle_x=456.0, radius=4.0)


def test_reached_right_paddle_line_false_when_moving_away():
    ball = Ball(x=455.0, y=100.0, vx=-140.0, vy=0.0)
    assert not reached_right_paddle_line(ball, paddle_x=456.0, radius=4.0)


def test_resolve_ball_at_paddle_catch_bounces():
    paddle = Paddle(y=80.0, height=40.0)  # covers y in [80, 120]
    ball = Ball(x=20.0, y=100.0, vx=-140.0, vy=0.0)
    bounced, caught = resolve_ball_at_paddle(ball, paddle, bounce_direction=1)
    assert caught is True
    assert bounced.vx > 0


def test_resolve_ball_at_paddle_miss_is_not_caught_and_ball_unchanged():
    paddle = Paddle(y=0.0, height=1.0)  # effectively unreachable
    ball = Ball(x=20.0, y=100.0, vx=-140.0, vy=0.0)
    result, caught = resolve_ball_at_paddle(ball, paddle, bounce_direction=1)
    assert caught is False
    assert result == ball


def test_resolve_ball_at_paddle_grace_catches_a_near_miss():
    paddle = Paddle(y=80.0, height=40.0)  # covers y in [80, 120]
    ball = Ball(x=20.0, y=125.0, vx=-140.0, vy=0.0)  # 5px below the paddle
    result, caught = resolve_ball_at_paddle(ball, paddle, bounce_direction=1, grace=8.0)
    assert caught is True
    assert result.vx > 0


def test_resolve_ball_at_paddle_grace_still_misses_far_outside():
    paddle = Paddle(y=80.0, height=40.0)
    ball = Ball(x=20.0, y=160.0, vx=-140.0, vy=0.0)
    result, caught = resolve_ball_at_paddle(ball, paddle, bounce_direction=1, grace=8.0)
    assert caught is False
    assert result == ball
