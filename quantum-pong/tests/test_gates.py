import itertools
import math
import random

from quantum_pong.config import (
    GATE_CAP_STEP_SECONDS,
    GATE_MIN_GAP,
    GATE_RADIUS,
    GATE_SPAWN_INTERVAL,
    GATE_SPAWN_INTERVAL_MIN,
    GATE_SPAWN_MARGIN_X,
    GATE_SPAWN_MARGIN_Y,
    GATE_SPAWN_RAMP_SECONDS,
    GATE_WARNING_SECONDS,
    INTERNAL_HEIGHT,
    INTERNAL_WIDTH,
    MAX_BALLS_ON_SCREEN,
    MAX_GATES_ON_SCREEN,
    MAX_GATES_ON_SCREEN_LATE,
)
from quantum_pong.gates import (
    Gate,
    apply_h,
    apply_swap,
    apply_x,
    apply_z,
    check_gate_collisions,
    gate_cap,
    is_live,
    maybe_spawn_gate,
    spawn_gate,
    spawn_interval,
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


def _squares_clear(a: Gate, b: Gate) -> bool:
    return max(abs(a.x - b.x), abs(a.y - b.y)) >= 2 * GATE_RADIUS + GATE_MIN_GAP


def test_spawn_gate_never_overlaps_existing_gates():
    rng = random.Random(9)
    existing = [Gate(kind="X", x=240.0, y=135.0, spawned_at=0.0)]
    for _ in range(200):
        gate = spawn_gate(rng, now=0.0, existing_gates=existing)
        assert gate is not None
        assert _squares_clear(gate, existing[0])


def test_repeated_spawns_up_to_the_cap_never_overlap():
    for seed in range(200):
        rng = random.Random(seed)
        gates: list[Gate] = []
        for _ in range(MAX_GATES_ON_SCREEN):
            gate = spawn_gate(rng, now=0.0, existing_gates=gates)
            assert gate is not None
            gates.append(gate)
        for i, a in enumerate(gates):
            for b in gates[i + 1 :]:
                assert _squares_clear(a, b)


def test_spawn_gate_is_spread_out_further_than_plain_uniform():
    # Best-candidate sampling should push the second gate noticeably further
    # from the first on average than a single uniform sample would.
    first = Gate(kind="X", x=160.0, y=80.0, spawned_at=0.0)
    rng = random.Random(3)
    spread = [spawn_gate(rng, 0.0, [first]) for _ in range(300)]
    rng = random.Random(3)
    uniform = [
        (rng.uniform(GATE_SPAWN_MARGIN_X, INTERNAL_WIDTH - GATE_SPAWN_MARGIN_X),
         rng.uniform(GATE_SPAWN_MARGIN_Y, INTERNAL_HEIGHT - GATE_SPAWN_MARGIN_Y))
        for _ in range(300)
    ]
    avg_spread = sum(math.hypot(g.x - first.x, g.y - first.y) for g in spread) / 300
    avg_uniform = sum(math.hypot(x - first.x, y - first.y) for x, y in uniform) / 300
    assert avg_spread > avg_uniform * 1.2


def test_spawn_gate_returns_none_when_field_is_crowded():
    rng = random.Random(10)
    # Pack the whole spawn area with gates so no spot is clear of all of them
    # -- spawning must give up (not overlap, not hang).
    existing = [
        Gate(kind="X", x=x, y=y, spawned_at=0.0)
        for x in range(int(GATE_SPAWN_MARGIN_X), int(INTERNAL_WIDTH - GATE_SPAWN_MARGIN_X) + 1, 20)
        for y in range(int(GATE_SPAWN_MARGIN_Y), int(INTERNAL_HEIGHT - GATE_SPAWN_MARGIN_Y) + 1, 20)
    ]
    assert spawn_gate(rng, now=0.0, existing_gates=existing) is None


def test_maybe_spawn_gate_respects_max_on_screen():
    rng = random.Random(4)
    gates = [Gate(kind="H", x=200.0, y=100.0, spawned_at=0.0)] * MAX_GATES_ON_SCREEN
    new_gates, last_spawn_at = maybe_spawn_gate(gates, now=10.0, last_spawn_at=0.0, rng=rng)
    assert new_gates == gates
    assert last_spawn_at == 0.0


def test_maybe_spawn_gate_respects_the_late_cap():
    rng = random.Random(4)
    gates = [Gate(kind="H", x=200.0, y=100.0, spawned_at=0.0)] * MAX_GATES_ON_SCREEN_LATE
    new_gates, last_spawn_at = maybe_spawn_gate(gates, now=1000.0, last_spawn_at=0.0, rng=rng)
    assert new_gates == gates
    assert last_spawn_at == 0.0


def test_maybe_spawn_gate_counts_announced_gates_against_the_cap():
    rng = random.Random(4)
    announced = [Gate(kind="X", x=200.0, y=100.0, spawned_at=99.0)] * MAX_GATES_ON_SCREEN
    new_gates, _ = maybe_spawn_gate(announced, now=10.0, last_spawn_at=0.0, rng=rng)
    assert new_gates == announced


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


# --- Announcement: a gate shows up as a warning before it appears ---


def test_new_gate_is_announced_before_it_appears():
    rng = random.Random(6)
    now = GATE_SPAWN_INTERVAL + 0.1
    new_gates, _ = maybe_spawn_gate([], now=now, last_spawn_at=0.0, rng=rng)
    gate = new_gates[0]
    assert gate.spawned_at == now + GATE_WARNING_SECONDS
    assert not is_live(gate, now)
    assert not is_live(gate, now + GATE_WARNING_SECONDS - 0.01)
    assert is_live(gate, now + GATE_WARNING_SECONDS)


def test_announced_gate_appears_at_the_same_spot_and_kind():
    # The warning *is* the gate: same object, so the same kind and position,
    # only not yet live. Nothing re-rolls it when it appears.
    rng = random.Random(12)
    gates: list[Gate] = []
    last = 0.0
    now = 0.0
    while not gates:
        now += 1 / 60
        gates, last = maybe_spawn_gate(gates, now, last, rng)
    announced = gates[0]
    while now < announced.spawned_at:
        now += 1 / 60
        gates, last = maybe_spawn_gate(gates, now, last, rng)
    assert gates[0] is announced
    assert is_live(gates[0], now)
    assert (gates[0].kind, gates[0].x, gates[0].y) == (announced.kind, announced.x, announced.y)


def test_spawning_is_always_preceded_by_its_warning():
    # Over a whole simulated match, every gate is in the list (announced) for
    # GATE_WARNING_SECONDS before it goes live -- never live on first sight.
    rng = random.Random(13)
    gates: list[Gate] = []
    last = 0.0
    first_seen: dict[int, float] = {}
    now = 0.0
    for _ in range(60 * 120):
        now += 1 / 60
        gates, last = maybe_spawn_gate(gates, now, last, rng)
        for gate in gates:
            first_seen.setdefault(id(gate), now)
            if is_live(gate, now):
                assert now - first_seen[id(gate)] >= GATE_WARNING_SECONDS - 1e-9
        gates = [g for g in gates if not is_live(g, now) or rng.random() > 0.01]
    assert len(first_seen) > 10


def test_balls_pass_through_an_announced_gate():
    balls = [Ball(x=300.0, y=200.0, vx=140.0, vy=0.0)]
    gates = [Gate(kind="X", x=302.0, y=201.0, spawned_at=5.0)]
    new_balls, remaining = check_gate_collisions(balls, gates, ball_radius=4, now=4.9)
    assert new_balls == balls
    assert remaining == gates
    new_balls, remaining = check_gate_collisions(balls, gates, ball_radius=4, now=5.0)
    assert new_balls[0].vx == -140.0
    assert remaining == []


def test_new_gates_never_overlap_announced_ones():
    rng = random.Random(14)
    announced = [Gate(kind="Z", x=240.0, y=135.0, spawned_at=50.0)]
    for _ in range(100):
        gate = spawn_gate(rng, now=0.0, existing_gates=announced)
        assert _squares_clear(gate, announced[0])


# --- Ramp: gates come faster, and more of them, as a match goes on ---


def test_spawn_interval_starts_at_the_base_interval():
    assert spawn_interval(0.0) == GATE_SPAWN_INTERVAL


def test_spawn_interval_shrinks_steadily_over_the_match():
    times = [0.0, 15.0, 30.0, 45.0, 60.0, 75.0, GATE_SPAWN_RAMP_SECONDS]
    intervals = [spawn_interval(t) for t in times]
    assert all(a > b for a, b in itertools.pairwise(intervals))


def test_spawn_interval_is_capped_at_the_minimum():
    assert spawn_interval(GATE_SPAWN_RAMP_SECONDS) == GATE_SPAWN_INTERVAL_MIN
    assert spawn_interval(10 * GATE_SPAWN_RAMP_SECONDS) == GATE_SPAWN_INTERVAL_MIN
    assert GATE_SPAWN_INTERVAL_MIN < GATE_SPAWN_INTERVAL


def test_spawn_interval_ramp_is_gentle():
    # "Funny, not overwhelming": a minute in, still at least 60% of the start.
    assert spawn_interval(60.0) >= 0.6 * GATE_SPAWN_INTERVAL
    assert GATE_SPAWN_INTERVAL_MIN >= GATE_SPAWN_INTERVAL / 2


def test_gate_cap_grows_one_step_at_a_time_up_to_the_late_cap():
    assert gate_cap(0.0) == MAX_GATES_ON_SCREEN
    assert gate_cap(GATE_CAP_STEP_SECONDS - 0.1) == MAX_GATES_ON_SCREEN
    assert gate_cap(GATE_CAP_STEP_SECONDS) == MAX_GATES_ON_SCREEN + 1
    caps = [gate_cap(t / 2) for t in range(2000)]
    assert all(0 <= b - a <= 1 for a, b in itertools.pairwise(caps))
    assert max(caps) == MAX_GATES_ON_SCREEN_LATE
    assert gate_cap(10_000.0) == MAX_GATES_ON_SCREEN_LATE


def test_late_match_spawns_more_often_than_early():
    # Clear every gate as soon as it appears, so only the interval limits
    # spawning: the last 30 s of a long match see more gates than the first 30.
    def spawns_between(start: float, end: float) -> int:
        rng = random.Random(15)
        gates: list[Gate] = []
        last = start
        count = 0
        now = start
        while now < end:
            now += 1 / 60
            before = len(gates)
            gates, last = maybe_spawn_gate(gates, now, last, rng)
            count += len(gates) - before
            gates = []
        return count

    assert spawns_between(120.0, 150.0) > spawns_between(0.0, 30.0)


def test_late_cap_gates_still_fit_without_overlap():
    for seed in range(50):
        rng = random.Random(seed)
        gates: list[Gate] = []
        for _ in range(MAX_GATES_ON_SCREEN_LATE):
            gate = spawn_gate(rng, now=0.0, existing_gates=gates)
            if gate is not None:
                gates.append(gate)
        for i, a in enumerate(gates):
            for b in gates[i + 1 :]:
                assert _squares_clear(a, b)


def test_maybe_spawn_gate_keeps_new_gate_away_from_existing_ones():
    rng = random.Random(11)
    existing = [Gate(kind="Z", x=240.0, y=135.0, spawned_at=0.0)]
    new_gates, _ = maybe_spawn_gate(existing, now=GATE_SPAWN_INTERVAL + 0.1, last_spawn_at=0.0, rng=rng)
    assert len(new_gates) == 2
    spawned = next(g for g in new_gates if g is not existing[0])
    assert _squares_clear(spawned, existing[0])


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
