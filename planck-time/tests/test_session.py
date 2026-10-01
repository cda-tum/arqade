"""The session flow, driven with tiny scripted microgames so every outcome
is under the test's control."""

import random

import pytest

from planck_time import config, session
from planck_time.hiscores import Hiscores
from planck_time.microgames import Microgame, PlayerInput, play_time
from planck_time.session import FrameInput, Session

DT = 1 / 60
PRESS = PlayerInput(a=True)


class WinOnA(Microgame):
    """Wins the moment A is pressed; doing nothing loses on timeout."""

    VERB = "PRESS!"
    INPUT = "a"

    def step(self, dt, inp):
        if inp.a:
            self.win()


class FailOnA(Microgame):
    VERB = "DONT!"
    INPUT = "a"

    def step(self, dt, inp):
        if inp.a:
            self.fail()

    def timeout(self):
        self.win()


class Other(WinOnA):
    VERB = "OTHER!"


def make(registry=(WinOnA, Other), seed=0, mode=1, hiscores=None):
    s = Session(random.Random(seed), hiscores, list(registry))
    s.mode = mode
    return s


def frame(p1=PlayerInput(), p2=PlayerInput(), activity=True, **kw):
    inp = FrameInput(activity=activity, **kw)
    inp.players = {"p1": p1, "p2": p2}
    return inp


def confirm():
    return frame(confirms={"p1": True, "p2": False})


def start_button():
    return frame(confirms={"p1": True, "p2": False}, pauses={"p1": True, "p2": False})


def run(s, seconds, inp=None):
    events = []
    for _ in range(round(seconds / DT)):
        events += s.update(DT, inp or frame())
    return events


def to_play(s):
    while s.state != session.PLAY:
        s.update(DT, frame())


def play_one(s, p1=PlayerInput(), p2=PlayerInput(), press_at=0.5):
    """Play the current microgame, pressing at press_at seconds, through its result."""
    to_play(s)
    events = run(s, press_at)
    events += s.update(DT, frame(p1, p2))
    while s.state == session.PLAY:
        events += s.update(DT, frame())
    while s.state == session.RESULT:
        events += s.update(DT, frame())
    return events


# --- beats and timing -----------------------------------------------------------------


def test_title_starts_on_confirm_with_an_intro():
    s = make()
    events = s.update(DT, confirm())
    assert s.state == session.INTRO
    assert {e.kind for e in events} >= {"start", "intro"}


def test_beats_follow_their_timing():
    s = make()
    s.update(DT, confirm())
    run(s, config.INTRO_TIME - 0.05)
    assert s.state == session.INTRO
    run(s, 0.1)
    assert s.state == session.PLAY
    run(s, play_time(0) - 0.1)
    assert s.state == session.PLAY
    run(s, 0.15)
    assert s.state == session.RESULT
    run(s, config.RESULT_TIME + 0.05)
    assert s.state == session.INTRO


def test_play_ends_early_once_every_player_failed_but_not_on_a_win():
    s = make([FailOnA])
    s.update(DT, confirm())
    to_play(s)
    s.update(DT, frame(PRESS))
    assert s.state == session.RESULT  # failed: no need to wait

    s = make([WinOnA])
    s.update(DT, confirm())
    to_play(s)
    s.update(DT, frame(PRESS))
    assert s.state == session.PLAY  # won: the win animation plays out the timer
    assert s.games["p1"].result is True


def test_timeout_is_called_at_the_end():
    s = make([FailOnA])  # wins on timeout
    s.update(DT, confirm())
    to_play(s)
    events = run(s, play_time(0) + 0.1)
    assert s.games["p1"].result is True
    assert s.score == 1
    assert any(e.kind == "win" for e in events)


def test_time_left_runs_down_during_play():
    s = make()
    s.update(DT, confirm())
    to_play(s)
    assert s.time_left == pytest.approx(1.0, abs=0.02)
    run(s, play_time(0) / 2)
    assert s.time_left == pytest.approx(0.5, abs=0.02)


# --- the order --------------------------------------------------------------------------


def test_the_deck_never_repeats_until_all_have_come_up_and_never_back_to_back():
    games = [type(f"G{i}", (WinOnA,), {}) for i in range(5)]
    deck = session.Deck(games, random.Random(4))
    drawn = [deck.draw() for _ in range(50)]
    for i in range(0, 50, 5):
        assert set(drawn[i : i + 5]) == set(games)
    assert all(a is not b for a, b in zip(drawn, drawn[1:]))


# --- speed --------------------------------------------------------------------------------


def test_the_duration_formula():
    assert play_time(0) == pytest.approx(5.0)
    assert play_time(1) == pytest.approx(4.5)
    assert play_time(30) == pytest.approx(2.5)


def test_level_ramps_every_four_microgames_with_a_speed_up_card():
    s = make()
    s.update(DT, confirm())
    for i in range(config.GAMES_PER_LEVEL):
        assert s.level == 0
        events = play_one(s, PRESS)
    assert s.state == session.SPEED_UP
    assert any(e.kind == "speed_up" for e in events)
    run(s, config.SPEED_UP_TIME + 0.05)
    assert s.state == session.INTRO
    assert s.level == 1
    assert s.games["p1"].level == 1
    assert s.games["p1"].duration == pytest.approx(play_time(1))


# --- single player ----------------------------------------------------------------------


def test_single_player_scores_wins_and_loses_lives():
    s = make()
    s.update(DT, confirm())
    play_one(s, PRESS)
    assert (s.score, s.lives["p1"]) == (1, config.LIVES)
    play_one(s)  # did nothing
    assert (s.score, s.lives["p1"]) == (1, config.LIVES - 1)


def test_either_pad_plays_in_single_player():
    s = make()
    s.update(DT, confirm())
    play_one(s, p2=PRESS)
    assert s.score == 1
    assert list(s.games) == ["p1"]


def test_game_over_goes_to_initials_when_the_score_qualifies(tmp_path):
    s = make(hiscores=Hiscores(tmp_path / "s.json"))
    s.update(DT, confirm())
    play_one(s, PRESS)
    for _ in range(config.LIVES):
        events = play_one(s)
    assert s.state == session.GAME_OVER
    assert any(e.kind == "game_over" for e in events)
    run(s, config.GAME_OVER_TIME + 0.05)
    assert s.state == session.NAME_ENTRY
    for _ in range(3):
        s.update(DT, confirm())
    assert s.state == session.HISCORES
    assert s.new_rank == 0
    assert s.hiscores.entries[0].score == 1


def test_game_over_goes_straight_to_the_table_otherwise(tmp_path):
    scores = Hiscores(tmp_path / "s.json")
    for _ in range(config.HISCORE_SLOTS):
        scores.add("TOP", 50, 3)
    s = make(hiscores=scores)
    s.update(DT, confirm())
    for _ in range(config.LIVES):
        play_one(s)
    run(s, config.GAME_OVER_TIME + 0.05)
    assert s.state == session.HISCORES
    assert s.new_rank is None
    run(s, config.HISCORES_TIME + 0.05)
    assert s.state == session.TITLE


# --- versus -------------------------------------------------------------------------------


def test_versus_both_players_get_the_same_microgame_from_the_same_seed():
    s = make(mode=2)
    s.update(DT, confirm())
    a, b = s.games["p1"], s.games["p2"]
    assert a is not b
    assert type(a) is type(b)
    assert a.rng.random() == b.rng.random()


def test_versus_a_success_scores_one_and_finishing_first_one_more():
    s = make(mode=2)
    s.update(DT, confirm())
    to_play(s)
    run(s, 0.3)
    s.update(DT, frame(PRESS))  # p1 first
    run(s, 0.3)
    s.update(DT, frame(p2=PRESS))
    while s.state != session.RESULT:
        s.update(DT, frame())
    assert s.scores == {"p1": 2, "p2": 1}
    assert s.first == "p1"


def test_versus_no_bonus_when_only_one_succeeds_and_the_other_loses_a_life():
    s = make(mode=2)
    s.update(DT, confirm())
    play_one(s, p2=PRESS)
    assert s.scores == {"p1": 0, "p2": 1}
    assert s.lives == {"p1": config.LIVES - 1, "p2": config.LIVES}


def test_versus_no_bonus_for_simultaneous_finishes():
    s = make(mode=2)
    s.update(DT, confirm())
    play_one(s, PRESS, PRESS)
    assert s.scores == {"p1": 1, "p2": 1}
    assert s.first is None


def test_versus_last_player_standing_wins():
    s = make(mode=2)
    s.update(DT, confirm())
    events = []
    for _ in range(config.LIVES):
        events += play_one(s, p2=PRESS)
    assert s.state == session.MATCH_RESULT
    assert s.winner == "p2"
    assert any(e.kind == "match_won" and e.player == "p2" for e in events)


def test_versus_both_out_together_higher_score_wins_else_draw():
    s = make(mode=2)
    s.update(DT, confirm())
    play_one(s, PRESS)  # p1 +1, p2 loses a life
    for _ in range(config.LIVES - 1):
        play_one(s)  # both lose a life each
    assert s.lives["p2"] == 0 and s.lives["p1"] == 1
    assert s.winner == "p1"

    s = make(mode=2)
    s.update(DT, confirm())
    events = []
    for _ in range(config.LIVES):
        events += play_one(s)
    assert s.state == session.MATCH_RESULT
    assert s.winner is None
    assert any(e.kind == "draw" for e in events)


def test_versus_rematch_and_back_to_title():
    s = make(mode=2)
    s.update(DT, confirm())
    for _ in range(config.LIVES):
        play_one(s)
    s.update(DT, confirm())
    assert s.state == session.MATCH_RESULT  # locked for a moment
    run(s, config.MATCH_RESULT_LOCK)
    s.update(DT, confirm())
    assert s.state == session.INTRO
    assert s.lives == {"p1": config.LIVES, "p2": config.LIVES}
    assert s.scores == {"p1": 0, "p2": 0}

    for _ in range(config.LIVES):
        play_one(s)
    run(s, config.MATCH_RESULT_LOCK)
    s.update(DT, frame(backs={"p1": False, "p2": True}))
    assert s.state == session.TITLE


# --- first appearance ------------------------------------------------------------------


def test_first_appearance_flag_drives_the_intro_demo():
    s = make()
    s.update(DT, confirm())
    flags = []
    for _ in range(4):
        flags.append((s.game_cls, s.first_time))
        play_one(s, PRESS)
    assert [f for _, f in flags] == [True, True, False, False]


# --- title, pause and idle -------------------------------------------------------------


def test_title_stick_toggles_the_player_count():
    s = make()
    assert s.mode == 1
    s.update(DT, frame(nav={"p1": (0, 1), "p2": (0, 0)}))
    assert s.mode == 2


def test_attract_mode_starts_when_the_title_is_left_alone():
    s = make(registry=[WinOnA, Other])
    run(s, config.ATTRACT_DELAY - 0.1, frame(activity=False))
    assert not s.attract
    run(s, 0.2, frame(activity=False))
    assert set(s.attract) == {"p1", "p2"}
    s.update(DT, frame())  # any input stops it
    assert not s.attract


def test_pause_freezes_play_and_resumes():
    s = make()
    s.update(DT, confirm())
    to_play(s)
    run(s, 1.0)
    t, game_t = s.t, s.games["p1"].t
    events = s.update(DT, start_button())
    assert s.paused and any(e.kind == "pause" for e in events)
    run(s, 3.0)
    assert (s.t, s.games["p1"].t) == (t, game_t)
    s.update(DT, start_button())
    assert not s.paused
    run(s, 0.1)
    assert s.t > t


def test_pause_menu_quits_to_title():
    s = make()
    s.update(DT, confirm())
    s.update(DT, start_button())
    assert s.paused
    s.update(DT, frame(nav={"p1": (0, 1), "p2": (0, 0)}))
    assert session.PAUSE_ITEMS[s.pause_index] == "QUIT TO TITLE"
    s.update(DT, confirm())
    assert s.state == session.TITLE and not s.paused


def test_idle_timeout_returns_to_the_title():
    s = make(registry=[FailOnA])  # survivable by doing nothing, so the run never ends
    s.update(DT, confirm())
    run(s, config.IDLE_TIMEOUT - 1, frame(activity=False))
    assert s.state != session.TITLE
    run(s, 1.1, frame(activity=False))
    assert s.state == session.TITLE


def test_real_registry_plays_through():
    """The real microgames, with their bots, run cleanly inside a session."""
    s = Session(random.Random(1))
    s.update(DT, confirm())
    for _ in range(6):
        to_play(s)
        while s.state == session.PLAY:
            g = s.games["p1"]
            s.update(DT, frame(g.bot()))
        assert s.games["p1"].result is True
        while s.state in (session.RESULT, session.SPEED_UP):
            s.update(DT, frame())
