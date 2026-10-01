import random

from qurves import config, rules
from qurves import match as m
from qurves.match import Cue, FrameInput, Match


def run(mt, seconds, inp=None, dt=1 / 60):
    events = []
    for _ in range(round(seconds / dt)):
        events += mt.update(dt, inp or FrameInput())
    return events


def confirm():
    return FrameInput(confirm=True, activity=True)


def started():
    mt = Match(random.Random(0))
    mt.update(1 / 60, confirm())
    return mt


def in_round():
    mt = started()
    run(mt, config.COUNTDOWN + 0.05)
    assert mt.state == m.ROUND
    return mt


def wall_in_front_of(mt, player):
    bike = mt.round.players[player].bikes[0]
    mt.round.arena.set(rules.add(bike.pos, bike.heading), rules.WALL)


def won_match():
    mt = in_round()
    for i in range(config.ROUNDS_TO_WIN):
        wall_in_front_of(mt, "p2")
        run(mt, 0.2)
        run(mt, config.ROUND_RESULT_TIME + 0.05)
        if i < config.ROUNDS_TO_WIN - 1:
            run(mt, config.COUNTDOWN + 0.05)
    assert mt.state == m.MATCH_RESULT
    return mt


def test_speed_ramps_up_every_ten_seconds_to_a_cap():
    assert m.speed_at(0) == 14
    assert m.speed_at(9.99) == 14
    assert m.speed_at(10) == 16
    assert m.speed_at(35) == 20
    assert m.speed_at(1000) == 24


def test_confirm_on_the_title_starts_a_countdown_with_a_fresh_round():
    mt = Match(random.Random(0))
    assert mt.state == m.TITLE and mt.round is None
    mt.update(1 / 60, confirm())
    assert mt.state == m.COUNTDOWN and mt.round is not None
    assert mt.scores == {"p1": 0, "p2": 0}


def test_the_countdown_beeps_three_times_then_goes():
    mt = Match(random.Random(0))
    events = mt.update(1 / 60, confirm())
    events += run(mt, config.COUNTDOWN + 0.05)
    assert [e.kind for e in events if isinstance(e, Cue)] == ["beep", "beep", "beep", "go"]
    assert mt.state == m.ROUND


def test_the_round_ticks_at_the_current_speed():
    mt = in_round()
    x0 = mt.round.players["p1"].bikes[0].pos[0]
    run(mt, 1.0)
    assert mt.round.players["p1"].bikes[0].pos[0] - x0 in (13, 14, 15)


def test_a_quick_tap_between_ticks_still_steers():
    mt = in_round()
    mt.update(0.001, FrameInput(direction={"p1": (0, -1), "p2": None}, activity=True))
    run(mt, 0.1)  # the stick is back at rest; the next tick still uses the tap
    assert mt.round.players["p1"].bikes[0].heading == (0, -1)


def test_a_split_press_is_kept_until_the_next_tick():
    mt = in_round()
    mt.round.players["p1"].meter = 100.0
    mt.update(0.001, FrameInput(split={"p1": True, "p2": False}, activity=True))
    run(mt, 0.1)
    assert mt.round.players["p1"].is_split


def test_winning_a_round_scores_and_starts_the_next_countdown():
    mt = in_round()
    wall_in_front_of(mt, "p2")
    events = run(mt, 0.2)
    assert mt.state == m.ROUND_RESULT
    assert mt.scores == {"p1": 1, "p2": 0} and mt.last_winner == "p1"
    assert Cue("round_won", "p1") in events
    old = mt.round
    run(mt, config.ROUND_RESULT_TIME + 0.05)
    assert mt.state == m.COUNTDOWN and mt.round is not old


def test_a_draw_scores_nobody_and_replays_the_round():
    mt = in_round()
    wall_in_front_of(mt, "p1")
    wall_in_front_of(mt, "p2")
    events = run(mt, 0.2)
    assert mt.state == m.ROUND_RESULT and mt.scores == {"p1": 0, "p2": 0}
    assert Cue("draw") in events
    run(mt, config.ROUND_RESULT_TIME + 0.05)
    assert mt.state == m.COUNTDOWN


def test_first_to_three_wins_the_match():
    mt = won_match()
    assert mt.match_winner == "p1"
    assert mt.scores["p1"] == config.ROUNDS_TO_WIN


def test_the_match_result_waits_a_moment_then_offers_a_rematch():
    mt = won_match()
    mt.update(1 / 60, confirm())
    assert mt.state == m.MATCH_RESULT  # mashed buttons don't skip the result
    run(mt, config.MATCH_RESULT_LOCK)
    mt.update(1 / 60, confirm())
    assert mt.state == m.COUNTDOWN and mt.scores == {"p1": 0, "p2": 0}


def test_b_on_the_match_result_goes_back_to_the_title():
    mt = won_match()
    run(mt, config.MATCH_RESULT_LOCK)
    mt.update(1 / 60, FrameInput(back=True, activity=True))
    assert mt.state == m.TITLE and mt.round is None


def test_a_minute_without_input_returns_to_the_title():
    mt = won_match()
    run(mt, config.IDLE_TIMEOUT + 1.0, dt=0.5)
    assert mt.state == m.TITLE
