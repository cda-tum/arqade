import math
import random

from quantum_pong.config import (
    GATE_LIFETIME,
    GATE_MIN_SPACING,
    GATE_SPAWN_INTERVAL,
    GATE_SPAWN_MARGIN_X,
    GATE_SPAWN_MARGIN_Y,
    INTERNAL_HEIGHT,
    INTERNAL_WIDTH,
    MAX_BALLS_ON_SCREEN,
    MAX_GATES_ON_SCREEN,
)
from quantum_pong.gates import (
    Gate,
    apply_h,
    apply_swap,
    apply_x,
    apply_z,
    check_gate_collisions,
    expire_gates,
    maybe_spawn_gate,
    spawn_gate,
)
from quantum_pong.pong import Ball


def test_spawn_gate_kind_is_one_of_h_x_z_swap():
    rng = random.Random(1)
    for _ in range(30):
        gate = spawn_gate(rng, now=0.0)
        assert gate.kind in ("H", "X", "Z", "SWAP")


def test_spawn_gate_stays_within_spawn_margins():
    rng = random.Random(2)
    for _ in range(50):
        gate = spawn_gate(rng, now=0.0)
        assert GATE_SPAWN_MARGIN_X <= gate.x <= INTERNAL_WIDTH - GATE_SPAWN_MARGIN_X
        assert GATE_SPAWN_MARGIN_Y <= gate.y <= INTERNAL_HEIGHT - GATE_SPAWN_MARGIN_Y


def test_spawn_gate_records_spawn_time():
    rng = random.Random(3)
    gate = spawn_gate(rng, now=12.5)
    assert gate.spawned_at == 12.5


def test_spawn_gate_kind_respects_zero_weight_exclusion():
    rng = random.Random(7)
    for _ in range(30):
        gate = spawn_gate(rng, now=0.0, weights={"H": 1, "X": 0, "Z": 0, "SWAP": 0})
        assert gate.kind == "H"


def test_spawn_gate_h_is_more_frequent_than_others_with_default_weights():
    rng = random.Random(8)
    kinds = [spawn_gate(rng, now=0.0).kind for _ in range(2000)]
    h_share = kinds.count("H") / len(kinds)
    # Equal weighting would give ~25%; the default config favors H, so this
    # should be comfortably higher without being a flaky exact-ratio check.
    assert h_share > 0.3


def test_spawn_gate_avoids_existing_gates_when_field_has_room():
    rng = random.Random(9)
    existing = [Gate(kind="X", x=240.0, y=135.0, spawned_at=0.0)]
    for _ in range(30):
        gate = spawn_gate(rng, now=0.0, existing_gates=existing)
        distance = math.hypot(gate.x - 240.0, gate.y - 135.0)
        assert distance >= GATE_MIN_SPACING


def test_spawn_gate_falls_back_to_some_position_when_field_is_crowded():
    rng = random.Random(10)
    # Pack the whole spawn area with close-together gates so no spot is far
    # enough from all of them -- spawning must still return a Gate, not hang.
    existing = [
        Gate(kind="X", x=x, y=y, spawned_at=0.0)
        for x in range(int(GATE_SPAWN_MARGIN_X), int(INTERNAL_WIDTH - GATE_SPAWN_MARGIN_X), 20)
        for y in range(int(GATE_SPAWN_MARGIN_Y), int(INTERNAL_HEIGHT - GATE_SPAWN_MARGIN_Y), 20)
    ]
    gate = spawn_gate(rng, now=0.0, existing_gates=existing)
    assert gate.kind in ("H", "X", "Z", "SWAP")
    assert GATE_SPAWN_MARGIN_X <= gate.x <= INTERNAL_WIDTH - GATE_SPAWN_MARGIN_X


def test_expire_gates_drops_gates_older_than_lifetime():
    gates = [Gate(kind="H", x=200.0, y=100.0, spawned_at=0.0)]
    remaining = expire_gates(gates, now=GATE_LIFETIME + 0.1)
    assert remaining == []


def test_expire_gates_keeps_fresh_gates():
    gates = [Gate(kind="H", x=200.0, y=100.0, spawned_at=10.0)]
    remaining = expire_gates(gates, now=10.0 + GATE_LIFETIME - 0.1)
    assert remaining == gates


def test_maybe_spawn_gate_respects_max_on_screen():
    rng = random.Random(4)
    gates = [Gate(kind="H", x=200.0, y=100.0, spawned_at=0.0)] * MAX_GATES_ON_SCREEN
    new_gates, last_spawn_at = maybe_spawn_gate(gates, now=100.0, last_spawn_at=0.0, rng=rng)
    assert new_gates == gates
    assert last_spawn_at == 0.0


def test_maybe_spawn_gate_respects_spawn_interval():
    rng = random.Random(5)
    new_gates, last_spawn_at = maybe_spawn_gate([], now=1.0, last_spawn_at=0.0, rng=rng)
    assert new_gates == []
    assert last_spawn_at == 0.0


def test_maybe_spawn_gate_spawns_after_interval_elapses():
    rng = random.Random(6)
    new_gates, last_spawn_at = maybe_spawn_gate(
        [], now=GATE_SPAWN_INTERVAL + 0.1, last_spawn_at=0.0, rng=rng
    )
    assert len(new_gates) == 1
    assert last_spawn_at == GATE_SPAWN_INTERVAL + 0.1


def test_maybe_spawn_gate_keeps_new_gate_away_from_existing_ones():
    rng = random.Random(11)
    existing = [Gate(kind="Z", x=240.0, y=135.0, spawned_at=0.0)]
    new_gates, _ = maybe_spawn_gate(existing, now=GATE_SPAWN_INTERVAL + 0.1, last_spawn_at=0.0, rng=rng)
    assert len(new_gates) == 2
    spawned = next(g for g in new_gates if g is not existing[0])
    distance = math.hypot(spawned.x - 240.0, spawned.y - 135.0)
    assert distance >= GATE_MIN_SPACING


def test_apply_h_returns_two_balls_one_continuing_one_reversed():
    ball = Ball(x=200.0, y=100.0, vx=140.0, vy=5.0)
    result = apply_h(ball)
    assert len(result) == 2
    assert ball in result
    reversed_ball = next(b for b in result if b is not ball)
    assert reversed_ball.x == 200.0
    assert reversed_ball.y == 100.0
    assert reversed_ball.vx == -140.0
    assert reversed_ball.vy == 5.0


def test_apply_x_reverses_horizontal_direction():
    ball = Ball(x=200.0, y=100.0, vx=140.0, vy=5.0)
    result = apply_x(ball)
    assert result.vx == -140.0
    assert result.vy == 5.0
    assert (result.x, result.y) == (200.0, 100.0)


def test_apply_x_on_leftward_ball_becomes_rightward():
    ball = Ball(x=200.0, y=100.0, vx=-140.0, vy=5.0)
    result = apply_x(ball)
    assert result.vx == 140.0


def test_apply_z_reverses_vertical_direction():
    ball = Ball(x=200.0, y=100.0, vx=140.0, vy=5.0)
    result = apply_z(ball)
    assert result.vy == -5.0
    assert result.vx == 140.0
    assert (result.x, result.y) == (200.0, 100.0)


def test_apply_swap_mirrors_position_and_reverses_horizontal_momentum():
    ball = Ball(x=100.0, y=50.0, vx=140.0, vy=5.0)
    result = apply_swap(ball)
    assert result.x == INTERNAL_WIDTH - 100.0
    assert result.y == 50.0
    assert result.vx == -140.0
    assert result.vy == 5.0


def test_check_gate_collisions_no_hit_leaves_state_unchanged():
    balls = [Ball(x=50.0, y=50.0, vx=140.0, vy=0.0)]
    gates = [Gate(kind="H", x=300.0, y=200.0, spawned_at=0.0)]
    new_balls, remaining = check_gate_collisions(balls, gates, ball_radius=4)
    assert new_balls == balls
    assert remaining == gates


def test_check_gate_collisions_h_touch_splits_and_consumes_gate():
    balls = [Ball(x=300.0, y=200.0, vx=140.0, vy=0.0)]
    gates = [Gate(kind="H", x=302.0, y=201.0, spawned_at=0.0)]
    new_balls, remaining = check_gate_collisions(balls, gates, ball_radius=4)
    assert len(new_balls) == 2
    assert remaining == []


def test_check_gate_collisions_x_touch_transforms_and_consumes_gate():
    balls = [Ball(x=300.0, y=200.0, vx=140.0, vy=0.0)]
    gates = [Gate(kind="X", x=302.0, y=201.0, spawned_at=0.0)]
    new_balls, remaining = check_gate_collisions(balls, gates, ball_radius=4)
    assert len(new_balls) == 1
    assert new_balls[0].vx == -140.0
    assert remaining == []


def test_check_gate_collisions_h_at_ball_cap_is_a_no_op_and_gate_stays():
    balls = [Ball(x=300.0, y=200.0, vx=140.0, vy=0.0) for _ in range(MAX_BALLS_ON_SCREEN)]
    gates = [Gate(kind="H", x=302.0, y=201.0, spawned_at=0.0)]
    new_balls, remaining = check_gate_collisions(balls, gates, ball_radius=4)
    assert new_balls == balls
    assert remaining == gates


def test_check_gate_collisions_h_below_cap_with_one_ball_short_still_splits():
    balls = [Ball(x=300.0, y=200.0, vx=140.0, vy=0.0) for _ in range(MAX_BALLS_ON_SCREEN - 1)]
    gates = [Gate(kind="H", x=302.0, y=201.0, spawned_at=0.0)]
    new_balls, remaining = check_gate_collisions(balls, gates, ball_radius=4)
    assert len(new_balls) == MAX_BALLS_ON_SCREEN
    assert remaining == []
