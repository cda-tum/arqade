import random

from gate_drop import config
from gate_drop import match as m
from gate_drop.board import Gate
from gate_drop.match import Cue, FrameInput, Match


def run(mt, seconds, inp=None, dt=1 / 60):
    events = []
    for _ in range(round(seconds / dt)):
        events += mt.update(dt, inp or FrameInput())
    return events


def confirm():
    return FrameInput(confirm=True, activity=True)


def in_round():
    mt = Match(random.Random(0))
    mt.update(1 / 60, confirm())
    run(mt, config.COUNTDOWN + 0.05)
    assert mt.state == m.ROUND
    return mt


def clear_errors(board):
    for pos, c in list(board.grid.items()):
        if isinstance(c, Gate) and c.error:
            board.grid.set(pos, None)


def win_round(mt, player="p1"):
    clear_errors(mt.boards[player])
    events = run(mt, 0.1)
    run(mt, config.ROUND_RESULT_TIME + 0.05)
    return events


def test_the_fall_speed_ramps_up_to_a_floor():
    assert m.fall_interval(0) == config.FALL_START
    assert abs(m.fall_interval(30) - config.FALL_START * 0.9) < 1e-9
    assert m.fall_interval(10_000) == config.FALL_MIN


def test_confirm_starts_a_countdown_with_identical_boards():
    mt = Match(random.Random(0))
    assert mt.state == m.TITLE
    mt.update(1 / 60, confirm())
    assert mt.state == m.COUNTDOWN
    b1, b2 = mt.boards["p1"], mt.boards["p2"]
    assert b1.errors_left() == b2.errors_left() == config.ERRORS_FIRST
    assert list(b1.grid.items()) == list(b2.grid.items())
    assert b1.next.halves == b2.next.halves


def test_the_countdown_beeps_three_times_then_goes():
    mt = Match(random.Random(0))
    events = mt.update(1 / 60, confirm())
    events += run(mt, config.COUNTDOWN + 0.05)
    assert [e.kind for e in events if isinstance(e, Cue)] == ["beep", "beep", "beep", "go"]


def test_the_boards_play_during_the_round():
    mt = in_round()
    assert mt.boards["p1"].piece is not None
    run(mt, config.FALL_START + 0.05)
    assert mt.boards["p1"].piece.y == 1


def test_clearing_every_error_wins_the_round():
    mt = in_round()
    events = win_round(mt, "p2")
    assert Cue("round_won", "p2") in events
    assert mt.scores == {"p1": 0, "p2": 1}
    assert mt.state == m.COUNTDOWN and mt.round_no == 2
    assert mt.boards["p1"].errors_left() == config.ERRORS_FIRST + config.ERRORS_STEP


def test_topping_out_loses_the_round():
    mt = in_round()
    mt.boards["p1"].topped_out = True
    events = run(mt, 0.1)
    assert Cue("round_won", "p2") in events


def test_both_at_once_is_a_draw_and_the_round_is_replayed():
    mt = in_round()
    clear_errors(mt.boards["p1"])
    clear_errors(mt.boards["p2"])
    events = run(mt, 0.1)
    assert Cue("draw") in events and mt.scores == {"p1": 0, "p2": 0}
    run(mt, config.ROUND_RESULT_TIME + 0.05)
    assert mt.round_no == 1


def test_chains_send_noise_to_the_opponent():
    mt = in_round()
    mt.boards["p1"].outgoing = 3
    run(mt, 1 / 60)
    assert mt.boards["p1"].outgoing == 0
    assert len(mt.boards["p2"].noise_queue) == 3
    assert set(mt.boards["p2"].noise_queue) <= set(config.PAULIS)


def won_match():
    mt = in_round()
    for i in range(config.ROUNDS_TO_WIN):
        events = win_round(mt, "p1")
        if i < config.ROUNDS_TO_WIN - 1:
            run(mt, config.COUNTDOWN + 0.05)
    assert mt.state == m.MATCH_RESULT and mt.match_winner == "p1"
    return mt


def test_first_to_two_wins_the_match_then_rematch_or_title():
    mt = won_match()
    mt.update(1 / 60, confirm())
    assert mt.state == m.MATCH_RESULT  # mashed buttons don't skip the result
    run(mt, config.MATCH_RESULT_LOCK)
    mt.update(1 / 60, confirm())
    assert mt.state == m.COUNTDOWN and mt.scores == {"p1": 0, "p2": 0} and mt.round_no == 1
    mt2 = won_match()
    run(mt2, config.MATCH_RESULT_LOCK)
    mt2.update(1 / 60, FrameInput(back=True, activity=True))
    assert mt2.state == m.TITLE


def test_a_minute_without_input_returns_to_the_title():
    mt = in_round()
    run(mt, config.IDLE_TIMEOUT + 1.0, dt=0.5)
    assert mt.state == m.TITLE


def test_danger_when_a_stack_nears_the_top():
    mt = in_round()
    assert not mt.danger
    mt.boards["p1"].grid.set((0, config.DANGER_ROWS - 1), Gate("X", error=True))
    assert mt.danger
