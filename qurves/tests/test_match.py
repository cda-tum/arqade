import random

from qurves import config, rules
from qurves import match as m
from qurves.match import Cue, FrameInput, Match, direction_for

UP, DOWN, LEFT, RIGHT = (0, -1), (0, 1), (-1, 0), (1, 0)


def run(mt, seconds, inp=None, dt=1 / 60):
    events = []
    for _ in range(round(seconds / dt)):
        events += mt.update(dt, inp or FrameInput())
    return events


def confirm():
    return FrameInput(confirm=True, pick=True, activity=True)


def any_button():
    return FrameInput(any_button=True, activity=True)


def at_tutorial(mode=2):
    mt = Match(random.Random(0))
    if mode == 4:
        mt.update(1 / 60, FrameInput(nav=RIGHT, activity=True))
    mt.update(1 / 60, confirm())
    assert mt.state == m.TUTORIAL
    return mt


def started(mode=2):
    mt = at_tutorial(mode)
    run(mt, config.TUTORIAL_GUARD)
    mt.update(1 / 60, any_button())
    return mt


def in_round(mode=2):
    mt = started(mode)
    run(mt, config.COUNTDOWN + 0.05)
    assert mt.state == m.ROUND
    return mt


def wall_in_front_of(mt, player):
    for bike in mt.round.players[player].bikes:
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


def test_with_two_players_either_the_stick_or_the_buttons_steer():
    assert direction_for(2, "p1", FrameInput(stick=(UP, None))) == UP
    assert direction_for(2, "p1", FrameInput(pad=(LEFT, None))) == LEFT
    assert direction_for(2, "p2", FrameInput(pad=(None, DOWN))) == DOWN
    assert direction_for(2, "p1", FrameInput(pad=(None, DOWN))) is None


def test_with_four_players_each_pads_stick_and_buttons_are_separate_players():
    inp = FrameInput(stick=(UP, DOWN), pad=(LEFT, RIGHT))
    assert [direction_for(4, p, inp) for p in ("p1", "p2", "p3", "p4")] == [UP, DOWN, LEFT, RIGHT]


def test_the_stick_picks_two_or_four_players_on_the_title():
    mt = Match(random.Random(0))
    assert mt.mode == 2
    events = mt.update(1 / 60, FrameInput(nav=RIGHT, activity=True))
    assert mt.mode == 4 and Cue("blip") in events
    mt.update(1 / 60, FrameInput(nav=RIGHT, activity=True))
    assert mt.mode == 2
    mt.update(1 / 60, FrameInput(nav=LEFT, activity=True))
    assert mt.mode == 4


def test_confirm_on_the_title_starts_a_countdown_with_a_fresh_round():
    mt = started()
    assert mt.state == m.COUNTDOWN and mt.round is not None
    assert set(mt.round.players) == {"p1", "p2"}
    assert mt.scores == {"p1": 0, "p2": 0}
    mt4 = started(4)
    assert set(mt4.round.players) == {"p1", "p2", "p3", "p4"}
    assert mt4.scores == {"p1": 0, "p2": 0, "p3": 0, "p4": 0}


def test_the_countdown_beeps_three_times_then_goes():
    mt = at_tutorial()
    run(mt, config.TUTORIAL_GUARD)
    events = mt.update(1 / 60, any_button())
    events += run(mt, config.COUNTDOWN + 0.05)
    assert [e.kind for e in events if isinstance(e, Cue)] == ["ready", "beep", "beep", "beep", "go"]
    assert mt.state == m.ROUND


def test_the_round_ticks_at_the_current_speed():
    mt = in_round()
    x0 = mt.round.players["p1"].bikes[0].pos[0]
    run(mt, 1.0)
    assert mt.round.players["p1"].bikes[0].pos[0] - x0 in (13, 14, 15)


def test_a_quick_tap_between_ticks_still_steers():
    mt = in_round()
    mt.update(0.001, FrameInput(pad=(UP, None), activity=True))
    run(mt, 0.1)  # the button is let go; the next tick still uses the tap
    assert mt.round.players["p1"].bikes[0].heading == UP


def test_in_four_player_mode_the_button_player_steers_their_own_bike():
    mt = in_round(4)
    mt.update(0.001, FrameInput(pad=(DOWN, None), activity=True))
    run(mt, 0.1)
    assert mt.round.players["p3"].bikes[0].heading == DOWN
    assert mt.round.players["p1"].bikes[0].heading == RIGHT


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


def test_a_rematch_skips_the_how_to_play_card():
    mt = won_match()
    run(mt, config.MATCH_RESULT_LOCK)
    mt.update(1 / 60, confirm())
    assert mt.state == m.COUNTDOWN


def test_b_on_the_match_result_goes_back_to_the_title():
    mt = won_match()
    run(mt, config.MATCH_RESULT_LOCK)
    mt.update(1 / 60, FrameInput(back=True, activity=True))
    assert mt.state == m.TITLE and mt.round is None


def test_a_minute_without_input_returns_to_the_title():
    mt = won_match()
    run(mt, config.IDLE_TIMEOUT + 1.0, dt=0.5)
    assert mt.state == m.TITLE


# --- pausing ---------------------------------------------------------------------------


def test_start_pauses_the_round_and_everything_freezes():
    mt = in_round()
    events = mt.update(1 / 60, FrameInput(pause=True, confirm=True, activity=True))
    assert mt.paused and Cue("pause") in events
    pos = mt.round.players["p1"].bikes[0].pos
    run(mt, 2.0)
    assert mt.round.players["p1"].bikes[0].pos == pos and mt.state == m.ROUND


def test_start_or_b_resumes():
    mt = in_round()
    mt.update(1 / 60, FrameInput(pause=True, activity=True))
    mt.update(1 / 60, FrameInput(pause=True, activity=True))
    assert not mt.paused
    mt.update(1 / 60, FrameInput(pause=True, activity=True))
    mt.update(1 / 60, FrameInput(back=True, activity=True))
    assert not mt.paused


def test_a_picks_resume_or_quit_to_title():
    mt = in_round()
    mt.update(1 / 60, FrameInput(pause=True, activity=True))
    mt.update(1 / 60, FrameInput(pick=True, confirm=True, activity=True))
    assert not mt.paused and mt.state == m.ROUND
    mt.update(1 / 60, FrameInput(pause=True, activity=True))
    mt.update(1 / 60, FrameInput(nav=DOWN, activity=True))
    assert m.PAUSE_ITEMS[mt.pause_index] == "QUIT TO TITLE"
    mt.update(1 / 60, FrameInput(pick=True, confirm=True, activity=True))
    assert mt.state == m.TITLE and not mt.paused and mt.round is None


# --- the title menu ----------------------------------------------------------------------


def test_the_title_menu_ends_with_quit():
    assert m.TITLE_ITEMS[-1] == "QUIT"


def test_stick_up_and_down_moves_between_the_title_rows():
    mt = Match(random.Random(0))
    events = mt.update(1 / 60, FrameInput(nav=DOWN, activity=True))
    assert m.TITLE_ITEMS[mt.title_index] == "QUIT" and Cue("blip") in events
    mt.update(1 / 60, FrameInput(nav=DOWN, activity=True))
    assert mt.title_index == 0
    mt.update(1 / 60, FrameInput(nav=UP, activity=True))
    assert m.TITLE_ITEMS[mt.title_index] == "QUIT"


def test_on_the_quit_row_the_stick_does_not_change_the_player_count():
    mt = Match(random.Random(0))
    mt.update(1 / 60, FrameInput(nav=DOWN, activity=True))
    mt.update(1 / 60, FrameInput(nav=RIGHT, activity=True))
    assert mt.mode == 2


def test_a_on_quit_quits_at_once():
    mt = Match(random.Random(0))
    mt.update(1 / 60, FrameInput(nav=DOWN, activity=True))
    mt.update(1 / 60, confirm())
    assert mt.quit_requested and mt.state == m.TITLE


def test_start_always_starts_even_on_quit():
    mt = Match(random.Random(0))
    mt.update(1 / 60, FrameInput(nav=DOWN, activity=True))
    events = mt.update(1 / 60, FrameInput(pause=True, confirm=True, activity=True))
    assert mt.state == m.TUTORIAL and not mt.quit_requested and Cue("start") in events


def test_b_on_the_title_does_nothing():
    mt = Match(random.Random(0))
    mt.update(1 / 60, FrameInput(nav=DOWN, activity=True))
    mt.update(1 / 60, FrameInput(back=True, activity=True))
    assert mt.state == m.TITLE and not mt.quit_requested


def test_back_on_the_title_the_first_row_is_selected_again():
    mt = in_round()
    mt.title_index = 1
    mt.update(1 / 60, FrameInput(pause=True, activity=True))
    mt.update(1 / 60, FrameInput(nav=DOWN, activity=True))
    mt.update(1 / 60, FrameInput(pick=True, confirm=True, activity=True))
    assert mt.state == m.TITLE and mt.title_index == 0


# --- how to play -------------------------------------------------------------------------


def test_a_match_from_the_title_opens_on_how_to_play():
    mt = at_tutorial(4)
    assert mt.round is None and mt.mode == 4
    assert mt.scores == {"p1": 0, "p2": 0, "p3": 0, "p4": 0}


def test_how_to_play_ignores_buttons_at_first():
    mt = at_tutorial()
    mt.update(1 / 60, any_button())  # the press that opened it, bouncing
    run(mt, config.TUTORIAL_GUARD - 0.1)
    mt.update(1 / 60, any_button())
    assert mt.state == m.TUTORIAL


def test_any_button_then_dismisses_it_and_the_countdown_starts():
    mt = at_tutorial()
    run(mt, config.TUTORIAL_GUARD)
    events = mt.update(1 / 60, any_button())
    assert mt.state == m.COUNTDOWN and mt.round is not None
    assert Cue("ready") in events


def test_the_stick_does_not_dismiss_how_to_play():
    mt = at_tutorial()
    run(mt, 1.0)
    for nav in (UP, DOWN, LEFT, RIGHT):
        mt.update(1 / 60, FrameInput(nav=nav, stick=(nav, nav), activity=True))
    assert mt.state == m.TUTORIAL and mt.mode == 2


def test_how_to_play_times_out_to_the_title():
    mt = at_tutorial()
    run(mt, config.IDLE_TIMEOUT + 1.0, dt=0.5)
    assert mt.state == m.TITLE


def test_quit_to_title_then_a_new_match_shows_how_to_play_again():
    mt = in_round()
    mt.update(1 / 60, FrameInput(pause=True, activity=True))
    mt.update(1 / 60, FrameInput(nav=DOWN, activity=True))
    mt.update(1 / 60, FrameInput(pick=True, confirm=True, activity=True))
    assert mt.state == m.TITLE
    mt.update(1 / 60, confirm())
    assert mt.state == m.TUTORIAL
