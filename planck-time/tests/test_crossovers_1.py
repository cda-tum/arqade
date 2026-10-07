"""The rules RETURN! needs beyond the shared contract: the Z gate really changes where
the ball arrives, there is time to react after it, and a caught ball flies back."""

from planck_time.microgames import PlayerInput
from planck_time.microgames import ret as R
from planck_time.microgames.ret import Return

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


def test_a_caught_ball_flies_back_and_a_missed_one_flies_on():
    for seed in range(20):
        game = Return(seed, 0, Return.duration_for(0))
        assert run(game, lambda g: g.bot()) is True
        caught = game.ball_pos()
        for _ in range(24):
            game.update(DT, PlayerInput())
        back = game.ball_pos()
        assert back[0] > caught[0] + 20, seed          # returned to the right, not frozen
        assert R.FIELD_TOP <= back[1] <= R.FIELD_BOTTOM
        game = Return(seed, 0, Return.duration_for(0))
        assert run(game, lambda g: PlayerInput(), until=game.duration) is False
        missed = game.ball_pos()
        for _ in range(12):
            game.update(DT, PlayerInput())
        assert game.ball_pos()[0] < missed[0], seed     # it flies on past the paddle
