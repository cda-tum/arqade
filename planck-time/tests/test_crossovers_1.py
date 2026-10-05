"""The rules RETURN!, SPLIT! and SURF! need beyond the shared contract: the Z gate really
changes where the ball arrives, the H is the only reliable way past the rival's wall,
and the loss hole takes an untouched ion but a player who reacts at the first moment
can keep it out."""

from planck_time.microgames import PlayerInput
from planck_time.microgames import ret as R
from planck_time.microgames import split as S
from planck_time.microgames import surf as F
from planck_time.microgames.ret import Return
from planck_time.microgames.split import Split
from planck_time.microgames.surf import Surf

DT = 1 / 60
SEEDS = range(100)
LEVELS = (0, 3)


def run(game, policy, until=None):
    for _ in range(round((until or game.duration) / DT)):
        game.update(DT, policy(game))
        if game.result is not None:
            break
    if game.result is None and until is None:
        game.timeout()
    return game.result


# --- RETURN! ----------------------------------------------------------------------------


def test_the_ball_always_crosses_the_z_gate():
    for seed in SEEDS:
        for level in LEVELS:
            game = Return(seed, level, Return.duration_for(level))
            path = R.trajectory(game.ball_start, game.v_start, game.gate, z=True)
            assert any(abs(x - game.gate[0]) < 2 and abs(y - game.gate[1]) < R.GATE / 2 for x, y in path)


def test_the_z_gate_really_changes_where_the_ball_arrives():
    for seed in SEEDS:
        for level in LEVELS:
            game = Return(seed, level, Return.duration_for(level))
            real = R.arrival(game.ball_start, game.v_start, game.gate, z=True)
            naive = R.arrival(game.ball_start, game.v_start, game.gate, z=False)
            reach = R.PADDLE_H / 2 + R.GRACE
            assert abs(real - naive) > reach + 4, seed         # ignoring the Z misses
            assert abs(real - R.PADDLE_START) > reach + 4, seed  # standing still misses


def test_return_level_0_leaves_time_to_react_after_the_z():
    for seed in SEEDS:
        game = Return(seed, 0, Return.duration_for(0))
        to_gate = (game.ball_start[0] - game.gate[0]) / abs(game.v_start[0])
        assert to_gate >= 0.6
        to_paddle = (game.ball_start[0] - R.PADDLE_X) / abs(game.v_start[0])
        assert to_paddle - to_gate >= 1.0                  # a second to get there after the bounce


# --- SPLIT! -----------------------------------------------------------------------------


def test_the_open_gap_is_decided_too_late_for_one_bike():
    # when the gap is decided, a bike lined up with the closed spot can't reach the open one
    assert 2 * S.OFFSET > S.WALL_X - S.REVEAL_X
    for seed in SEEDS:
        for level in LEVELS:
            game = Split(seed, level, Split.duration_for(level))
            while game.result is None and not game.revealed:
                assert max(c.x for c in game.copies) < S.REVEAL_X     # still undecided
                game.update(DT, game.bot())
            assert game.revealed and max(c.x for c in game.copies if c.alive) == S.REVEAL_X


def test_a_single_bike_guessing_a_side_fails_half_the_time():
    results = []
    for seed in SEEDS:
        game = Split(seed, 0, Split.duration_for(0))
        game.h_live = False                     # no H: one bike, steered up after the gate's spot
        results.append(run(game, lambda g: g.steer_policy(-1)))
    assert 20 < sum(1 for r in results if r) < 80


def test_with_the_h_one_copy_always_gets_through():
    for seed in SEEDS:
        for level in LEVELS:
            for side in (-1, 1):
                game = Split(seed, level, Split.duration_for(level))
                assert run(game, lambda g: g.steer_policy(side)) is True, (seed, level, side)


# --- SURF! ------------------------------------------------------------------------------


def test_an_untouched_ion_falls_into_the_hole_but_not_too_soon():
    for seed in SEEDS:
        for level in LEVELS:
            game = Surf(seed, level, Surf.duration_for(level))
            t = 0.0
            while game.result is None and t < game.duration:
                game.update(DT, PlayerInput())
                t += DT
            assert game.result is False, (seed, level)
            if level == 0:
                assert game.ended_at >= 1.4, seed       # well after the first moment to react


def raise_from_first_moment(game):
    return PlayerInput(stick=(0.0, -1.0)) if game.t >= F.READY else PlayerInput()


def test_raising_the_electrode_from_the_first_moment_keeps_the_ion_out():
    for seed in SEEDS:
        for level in LEVELS:
            game = Surf(seed, level, Surf.duration_for(level))
            assert run(game, raise_from_first_moment) is True, (seed, level)


def test_lowering_the_electrode_does_not_help():
    for seed in range(20):
        game = Surf(seed, 0, Surf.duration_for(0))
        assert run(game, lambda g: PlayerInput(stick=(0.0, 1.0))) is False
