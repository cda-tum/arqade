import random

from gate_drop import config, levels
from gate_drop import match as m
from gate_drop.board import Event, Gate, PlayerInput
from gate_drop.hiscores import Hiscores
from gate_drop.match import Cue, FrameInput, Match, NameEntry, Setup

LEFT, RIGHT, UP, DOWN = (-1, 0), (1, 0), (0, -1), (0, 1)


def press(confirm=(), back=(), nav=None, players=None):
    """A frame where the given players press A/Start, B, or push the stick."""
    fi = FrameInput(activity=True)
    for p in confirm:
        fi.confirms[p] = True
    for p in back:
        fi.backs[p] = True
    for p, d in (nav or {}).items():
        fi.nav[p] = d
    for p, inp in (players or {}).items():
        fi.players[p] = inp
    return fi


def run(mt, seconds, inp=None, dt=1 / 60):
    events = []
    for _ in range(round(seconds / dt)):
        events += mt.update(dt, inp or FrameInput())
    return events


def new_match(mode=2):
    mt = Match(random.Random(0), Hiscores(None))
    if mode == 1:
        mt.update(1 / 60, press(nav={"p1": UP}))
    assert mt.mode == mode
    mt.update(1 / 60, press(confirm=["p1"]))
    assert mt.state == m.SETUP
    return mt


def ready_all(mt):
    mt.update(1 / 60, press(confirm=list(mt.players)))
    assert mt.state == m.TUTORIAL


def any_button():
    fi = FrameInput(activity=True)
    fi.any_button = True
    return fi


def skip_tutorial(mt):
    """Wait out the HOW TO PLAY card's lock, then press a button."""
    run(mt, config.TUTORIAL_LOCK)
    events = mt.update(1 / 60, any_button())
    assert mt.state == m.COUNTDOWN
    return events


def in_round(mode=2):
    mt = new_match(mode)
    ready_all(mt)
    skip_tutorial(mt)
    run(mt, config.COUNTDOWN + 0.05)
    assert mt.state == m.ROUND
    return mt


def clear_errors(board):
    for pos, c in list(board.grid.items()):
        if isinstance(c, Gate) and c.error:
            board.grid.set(pos, None)


# --- speed and setup ------------------------------------------------------------------


def test_each_speed_has_its_own_start_and_floor():
    assert m.fall_interval(0, "LOW") > m.fall_interval(0, "MED") > m.fall_interval(0, "HI")
    assert abs(m.fall_interval(30, "MED") - config.SPEED_FALL["MED"][0] * 0.9) < 1e-9
    for speed, (_start, floor) in config.SPEED_FALL.items():
        assert m.fall_interval(10_000, speed) == floor


def test_a_setup_row_changes_level_or_speed_within_bounds():
    s = Setup()
    s.update(-1, 0, False, False)
    assert s.level == config.LEVEL_MIN
    for _ in range(20):
        s.update(1, 0, False, False)
    assert s.level == config.LEVEL_MAX
    s.update(0, 1, False, False)  # down to the speed row
    s.update(1, 0, False, False)
    assert s.speed == "HI"
    s.update(1, 0, False, False)
    assert s.speed == "HI"
    assert s.update(0, 0, True, False) == "ready" and s.ready
    assert s.update(1, 0, False, False) is None and s.speed == "HI"  # ready: locked in
    assert s.update(0, 0, False, True) == "changed" and not s.ready
    assert s.update(0, 0, False, True) == "back"


def test_the_stick_picks_one_or_two_players_on_the_title():
    mt = Match(random.Random(0), Hiscores(None))
    assert mt.mode == 2 and m.TITLE_ITEMS[mt.title_index] == "2 PLAYERS"
    events = mt.update(1 / 60, press(nav={"p2": UP}))
    assert mt.mode == 1 and Cue("blip") in events
    mt.update(1 / 60, press(nav={"p1": RIGHT}))
    assert mt.mode == 2


def test_quit_is_the_last_title_row_and_a_on_it_quits():
    mt = Match(random.Random(0), Hiscores(None))
    assert m.TITLE_ITEMS[-1] == "QUIT"
    mt.update(1 / 60, press(nav={"p1": DOWN}))
    assert m.TITLE_ITEMS[mt.title_index] == "QUIT" and mt.mode == 2  # the mode stays as it was
    mt.update(1 / 60, press(nav={"p1": LEFT}))  # left/right only flip between the modes
    assert m.TITLE_ITEMS[mt.title_index] == "QUIT"
    mt.update(1 / 60, press(back=["p1"]))  # B on the title does nothing
    assert mt.state == m.TITLE and not mt.quit_requested
    mt.update(1 / 60, press(confirm=["p2"]))  # A
    assert mt.quit_requested


def test_start_on_quit_still_plays():
    mt = Match(random.Random(0), Hiscores(None))
    mt.update(1 / 60, press(nav={"p1": UP}))  # 1 PLAYER
    mt.update(1 / 60, press(nav={"p1": UP}))  # wraps round to QUIT
    assert m.TITLE_ITEMS[mt.title_index] == "QUIT"
    fi = press(confirm=["p1"])
    fi.pauses["p1"] = True  # Start (it counts as a confirm too)
    events = mt.update(1 / 60, fi)
    assert mt.state == m.SETUP and mt.mode == 1 and not mt.quit_requested and Cue("confirm") in events


def test_a_on_a_mode_row_goes_to_the_setup_and_the_title_never_comes_back_on_quit():
    mt = Match(random.Random(0), Hiscores(None))
    mt.update(1 / 60, press(nav={"p1": DOWN}))
    mt.update(1 / 60, press(nav={"p1": UP}))
    mt.update(1 / 60, press(confirm=["p1"]))
    assert mt.state == m.SETUP and mt.mode == 2
    mt.title_index = m.QUIT_ROW  # however it got there,
    mt.update(1 / 60, press(back=["p1"]))
    assert mt.state == m.TITLE and m.TITLE_ITEMS[mt.title_index] == "2 PLAYERS"  # back on the mode


# --- how to play ----------------------------------------------------------------------------


def test_readying_up_opens_how_to_play_and_any_button_starts_the_match():
    mt = new_match()
    ready_all(mt)
    assert mt.boards == {}
    mt.update(1 / 60, any_button())  # the A that readied up, bouncing: too soon
    assert mt.state == m.TUTORIAL
    run(mt, config.TUTORIAL_LOCK)
    run(mt, 5.0, press(nav={"p1": LEFT, "p2": DOWN}))  # the stick never skips it
    assert mt.state == m.TUTORIAL
    events = mt.update(1 / 60, any_button())
    assert mt.state == m.COUNTDOWN and Cue("confirm") in events and set(mt.boards) == {"p1", "p2"}


def test_a_b_or_start_dismiss_how_to_play_too():
    for fi in (press(confirm=["p2"]), press(back=["p1"])):
        mt = new_match()
        ready_all(mt)
        run(mt, config.TUTORIAL_LOCK)
        mt.update(1 / 60, fi)
        assert mt.state == m.COUNTDOWN


def test_how_to_play_times_out_to_the_title():
    mt = new_match()
    ready_all(mt)
    run(mt, config.IDLE_TIMEOUT + 1.0, dt=0.5)
    assert mt.state == m.TITLE


def test_how_to_play_shows_again_after_quit_to_title_but_not_on_a_new_level():
    mt = in_round()
    mt.update(1 / 60, pause_press())
    mt.update(1 / 60, press(nav={"p1": DOWN}))
    mt.update(1 / 60, press(confirm=["p1"]))  # QUIT TO TITLE
    assert mt.state == m.TITLE
    mt.update(1 / 60, press(confirm=["p1"]))
    ready_all(mt)  # asserts the card is up again
    solo = in_round(mode=1)
    clear_errors(solo.boards["p1"])
    run(solo, config.LEVEL_CLEAR_TIME + 0.2)
    assert solo.state == m.COUNTDOWN and solo.level == 2


def test_each_player_sets_their_own_level_and_the_round_waits_for_both():
    mt = new_match()
    mt.update(1 / 60, press(nav={"p1": RIGHT}))  # p1: level 2
    mt.update(1 / 60, press(nav={"p1": RIGHT}))  # p1: level 3
    mt.update(1 / 60, press(confirm=["p1"]))
    assert mt.state == m.SETUP  # p2 isn't ready yet
    mt.update(1 / 60, press(confirm=["p2"]))
    assert mt.state == m.TUTORIAL
    skip_tutorial(mt)
    assert mt.boards["p1"].errors_left() == levels.errors_for_level(3)
    assert mt.boards["p2"].errors_left() == levels.errors_for_level(1)
    assert mt.boards["p1"].next.halves == mt.boards["p2"].next.halves


def test_players_on_the_same_level_get_the_same_layout():
    mt = new_match()
    ready_all(mt)
    skip_tutorial(mt)
    assert list(mt.boards["p1"].grid.items()) == list(mt.boards["p2"].grid.items())


def test_b_on_the_setup_screen_goes_back_to_the_title():
    mt = new_match()
    mt.update(1 / 60, press(back=["p2"]))
    assert mt.state == m.TITLE


def test_the_countdown_beeps_three_times_then_goes():
    mt = new_match()
    mt.update(1 / 60, press(confirm=["p1"]))
    mt.update(1 / 60, press(confirm=["p2"]))
    events = skip_tutorial(mt)
    events += run(mt, config.COUNTDOWN + 0.05)
    assert [e.kind for e in events if isinstance(e, Cue)] == ["confirm", "beep", "beep", "beep", "go"]


# --- versus ------------------------------------------------------------------------------


def test_clearing_every_error_wins_the_round_and_the_level_stays():
    mt = in_round()
    clear_errors(mt.boards["p2"])
    events = run(mt, 0.1)
    assert Cue("round_won", "p2") in events and mt.scores == {"p1": 0, "p2": 1}
    run(mt, config.ROUND_RESULT_TIME + 0.05)
    assert mt.state == m.COUNTDOWN and mt.round_no == 2
    assert mt.boards["p1"].errors_left() == levels.errors_for_level(config.DEFAULT_LEVEL)


def test_topping_out_loses_and_both_at_once_is_a_draw():
    mt = in_round()
    mt.boards["p1"].topped_out = True
    assert Cue("round_won", "p2") in run(mt, 0.1)
    mt = in_round()
    clear_errors(mt.boards["p1"])
    clear_errors(mt.boards["p2"])
    assert Cue("draw") in run(mt, 0.1)


def test_attacks_drop_t_gates_on_the_opponent():
    mt = in_round()
    mt.boards["p1"].outgoing = 3
    run(mt, 1 / 60)
    assert mt.boards["p1"].outgoing == 0
    assert mt.boards["p2"].noise_queue == [config.NOISE_KIND] * 3


def won_match():
    mt = in_round()
    for i in range(config.ROUNDS_TO_WIN):
        clear_errors(mt.boards["p1"])
        run(mt, 0.1)
        run(mt, config.ROUND_RESULT_TIME + 0.05)
        if i < config.ROUNDS_TO_WIN - 1:
            run(mt, config.COUNTDOWN + 0.05)
    assert mt.state == m.MATCH_RESULT and mt.match_winner == "p1"
    return mt


def test_a_rematch_skips_the_setup_and_b_goes_to_the_title():
    mt = won_match()
    mt.update(1 / 60, press(confirm=["p1"]))
    assert mt.state == m.MATCH_RESULT  # mashed buttons don't skip the result
    run(mt, config.MATCH_RESULT_LOCK)
    mt.update(1 / 60, press(confirm=["p2"]))  # straight back in: no HOW TO PLAY
    assert mt.state == m.COUNTDOWN and mt.scores == {"p1": 0, "p2": 0}
    mt2 = won_match()
    run(mt2, config.MATCH_RESULT_LOCK)
    mt2.update(1 / 60, press(back=["p1"]))
    assert mt2.state == m.TITLE


# --- single player -------------------------------------------------------------------------


def test_single_player_has_one_board_and_either_pad_plays_it():
    mt = new_match(mode=1)
    mt.update(1 / 60, press(confirm=["p2"]))  # the right-hand pad readies it too
    skip_tutorial(mt)
    assert set(mt.boards) == {"p1"}
    run(mt, config.COUNTDOWN + 0.05)
    x = mt.boards["p1"].piece.x
    mt.update(1 / 60, press(players={"p2": PlayerInput(move=-1)}))
    assert mt.boards["p1"].piece.x == x - 1


def test_single_player_scoring_doubles_per_chain_step():
    mt = in_round(mode=1)
    mt.score_events([Event("clear", value=1), Event("errors", value=1)])
    assert mt.score == config.ERROR_POINTS * config.SPEED_SCORE["MED"]
    mt.score = 0
    mt.score_events([Event("clear", value=3), Event("errors", value=2)])
    assert mt.score == 2 * config.ERROR_POINTS * config.SPEED_SCORE["MED"] * 4


def test_clearing_the_board_moves_on_to_the_next_level_with_a_bonus():
    mt = in_round(mode=1)
    clear_errors(mt.boards["p1"])
    events = run(mt, 0.1)
    assert Cue("level_clear") in events and mt.state == m.LEVEL_CLEAR
    assert mt.score == config.LEVEL_CLEAR_BONUS * 1 * config.SPEED_SCORE["MED"]
    run(mt, config.LEVEL_CLEAR_TIME + 0.05)
    assert mt.state == m.COUNTDOWN and mt.level == 2
    assert mt.boards["p1"].errors_left() == levels.errors_for_level(2)


def test_game_over_with_a_high_score_asks_for_initials():
    mt = in_round(mode=1)
    mt.score = 4321
    mt.boards["p1"].topped_out = True
    assert Cue("game_over") in run(mt, 0.1)
    run(mt, config.GAME_OVER_TIME + 0.05)
    assert mt.state == m.NAME_ENTRY
    mt.update(1 / 60, press(nav={"p1": UP}))  # A -> B
    for _ in range(3):
        mt.update(1 / 60, press(confirm=["p2"]))
    assert mt.state == m.HISCORES and mt.new_rank == 0
    assert (mt.hiscores.entries[0].name, mt.hiscores.entries[0].score) == ("BAA", 4321)
    run(mt, config.HISCORES_TIME + 0.05)
    assert mt.state == m.TITLE


def test_a_new_high_score_is_posted_to_the_page(monkeypatch):
    posted = []
    monkeypatch.setattr(m.web, "post_score", lambda *a: posted.append(a))
    mt = in_round(mode=1)
    mt.score = 4321
    mt.boards["p1"].topped_out = True
    run(mt, 0.1)
    run(mt, config.GAME_OVER_TIME + 0.05)
    for _ in range(3):
        mt.update(1 / 60, press(confirm=["p1"]))
    assert posted == [("gate-drop", "default", 4321, "AAA")]


def test_game_over_without_a_high_score_shows_the_table():
    mt = in_round(mode=1)
    mt.boards["p1"].topped_out = True
    run(mt, 0.1)
    run(mt, config.GAME_OVER_TIME + 0.05)
    assert mt.state == m.HISCORES and mt.new_rank is None


def test_idling_on_the_initials_screen_saves_them():
    mt = in_round(mode=1)
    mt.score = 100
    mt.boards["p1"].topped_out = True
    run(mt, 0.1)
    run(mt, config.GAME_OVER_TIME + 0.05)
    run(mt, config.IDLE_TIMEOUT + 1.0, dt=0.5)
    assert mt.state == m.TITLE and mt.hiscores.entries[0].name == "AAA"


def test_name_entry_letters_wrap_and_the_cursor_moves():
    n = NameEntry()
    n.update(0, 1, False, False)  # down from A wraps to Z
    assert n.name == "ZAA"
    n.update(1, 0, False, False)
    n.update(0, -1, False, False)
    assert n.name == "ZBA" and n.pos == 1
    n.update(0, 0, False, True)
    assert n.pos == 0 and not n.done


def test_a_minute_without_input_returns_to_the_title():
    mt = in_round()
    run(mt, config.IDLE_TIMEOUT + 1.0, dt=0.5)
    assert mt.state == m.TITLE


# --- pausing ---------------------------------------------------------------------------


def pause_press(player="p1"):
    fi = press(confirm=[player])  # Start counts as a confirm in menus...
    fi.pauses[player] = True  # ...and pauses in game
    return fi


def test_start_pauses_the_round_and_everything_freezes():
    mt = in_round()
    events = mt.update(1 / 60, pause_press("p2"))
    assert mt.paused and Cue("pause") in events
    y = mt.boards["p1"].piece.y
    run(mt, 3.0)
    assert mt.boards["p1"].piece.y == y and mt.state == m.ROUND


def test_start_or_b_resumes():
    mt = in_round()
    mt.update(1 / 60, pause_press())
    mt.update(1 / 60, pause_press())
    assert not mt.paused
    mt.update(1 / 60, pause_press())
    mt.update(1 / 60, press(back=["p2"]))
    assert not mt.paused


def test_a_on_resume_resumes_and_quit_to_title_goes_home():
    mt = in_round()
    mt.update(1 / 60, pause_press())
    mt.update(1 / 60, press(confirm=["p1"]))  # A on RESUME
    assert not mt.paused and mt.state == m.ROUND
    mt.update(1 / 60, pause_press())
    mt.update(1 / 60, press(nav={"p2": DOWN}))
    assert m.PAUSE_ITEMS[mt.pause_index] == "QUIT TO TITLE"
    mt.update(1 / 60, press(confirm=["p2"]))
    assert mt.state == m.TITLE and not mt.paused and mt.boards == {}


def test_single_player_pauses_too():
    mt = in_round(mode=1)
    mt.update(1 / 60, pause_press("p2"))
    assert mt.paused
