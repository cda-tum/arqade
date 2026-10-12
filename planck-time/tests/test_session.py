"""The session flow, driven with tiny scripted microgames so every outcome
is under the test's control."""

import random

import pytest

from planck_time import config, session, tutorial
from planck_time.hiscores import Hiscores
from planck_time.microgames import REGISTRY, Boss, Microgame, PlayerInput, play_time
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


class BossOnA(Boss):
    """A boss that is won by pressing A; doing nothing loses on timeout."""

    VERB = "BOSS!"
    INPUT = "a"

    def step(self, dt, inp):
        if inp.a:
            self.win()


def make(registry=(WinOnA, Other), seed=0, mode=1, hiscores=None, bosses=(BossOnA,)):
    s = Session(random.Random(seed), hiscores, list(registry), list(bosses))
    s.mode = mode
    return s


def frame(p1=PlayerInput(), p2=PlayerInput(), activity=True, **kw):
    inp = FrameInput(activity=activity, **kw)
    inp.players = {"p1": p1, "p2": p2}
    return inp


def confirm():  # A
    return frame(confirms={"p1": True, "p2": False}, presses={"p1": True, "p2": False})


def start_button():
    return frame(confirms={"p1": True, "p2": False}, pauses={"p1": True, "p2": False},
                 presses={"p1": True, "p2": False})


def any_button(player="p1"):
    return frame(presses={p: p == player for p in session.PLAYERS})


def begin(s):
    """From the title through the HOW TO PLAY card, to the first intro."""
    s.update(DT, confirm())
    assert s.state == session.TUTORIAL
    run(s, config.TUTORIAL_LOCK)
    events = s.update(DT, any_button())
    assert s.state == session.INTRO
    return events


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


def test_title_opens_the_how_to_play_card_then_the_first_intro():
    s = make()
    s.update(DT, confirm())
    assert s.state == session.TUTORIAL and s.tutorial is not None
    events = begin(make())
    assert {e.kind for e in events} >= {"start", "intro"}


# --- the HOW TO PLAY card ---------------------------------------------------------------


def test_the_card_ignores_presses_at_first_then_any_button_dismisses_it():
    s = make()
    s.update(DT, confirm())
    s.update(DT, any_button())  # the confirm's bounce
    run(s, config.TUTORIAL_LOCK - 0.1, any_button())
    assert s.state == session.TUTORIAL
    run(s, 0.15)
    s.update(DT, any_button("p2"))  # any button on either pad: B, X, Select...
    assert s.state == session.INTRO


def test_the_stick_does_not_dismiss_the_card():
    s = make()
    s.update(DT, confirm())
    run(s, 2.0, frame(nav={"p1": (0, 1), "p2": (1, 0)},
                      p1=PlayerInput(stick=(0.0, 1.0), step=(0, 1))))
    assert s.state == session.TUTORIAL
    assert s.mode == 1  # nor change anything behind it


def test_the_card_demo_plays_real_microgames_and_loops():
    s = make()
    s.update(DT, confirm())
    verbs = set()
    results = []
    for _ in range(round(12 / DT)):
        s.update(DT, frame(activity=False))
        demo = s.tutorial
        verbs.add(demo.game.VERB)
        if demo.phase == tutorial.RESULT:
            results.append(demo.game.result)
    assert verbs == set(tutorial.DEMO_GAMES)
    assert results and all(results)  # the demo always wins


def test_start_dismisses_the_card_without_pausing_and_mashing_doesnt_pause_either():
    s = make()
    s.update(DT, confirm())
    run(s, config.TUTORIAL_LOCK)
    s.update(DT, start_button())
    assert s.state == session.INTRO and not s.paused
    run(s, 0.1)
    s.update(DT, start_button())  # still mashing
    assert not s.paused
    run(s, config.PAUSE_GRACE)
    s.update(DT, start_button())  # a real pause, a moment later
    assert s.paused


def test_the_card_times_out_to_the_title_like_any_screen():
    s = make()
    s.update(DT, confirm())
    run(s, config.IDLE_TIMEOUT + 0.1, frame(activity=False))
    assert s.state == session.TITLE and s.tutorial is None


def test_no_card_on_a_rematch_but_again_after_quitting_to_the_title():
    s = make(mode=2)
    begin(s)
    for _ in range(config.LIVES):
        play_one(s)
    run(s, config.MATCH_RESULT_LOCK)
    s.update(DT, confirm())  # rematch
    assert s.state == session.INTRO
    s.update(DT, start_button())
    s.update(DT, frame(nav={"p1": (0, 1), "p2": (0, 0)}))
    s.update(DT, confirm())  # QUIT TO TITLE
    assert s.state == session.TITLE
    s.update(DT, confirm())
    assert s.state == session.TUTORIAL


# --- the title menu ---------------------------------------------------------------------


def nav(dy):
    return frame(nav={"p1": (0, dy), "p2": (0, 0)})


def test_the_title_rows_end_with_quit_and_the_stick_doesnt_wrap():
    assert session.TITLE_ITEMS[-1] == "QUIT"
    s = make()
    s.update(DT, nav(-1))
    assert s.title_index == 0  # no wrap from the top to QUIT
    s.update(DT, nav(1))
    s.update(DT, nav(1))
    assert session.TITLE_ITEMS[s.title_index] == "QUIT"
    s.update(DT, nav(1))
    assert session.TITLE_ITEMS[s.title_index] == "QUIT"
    assert s.mode == 2  # QUIT keeps the player count last picked


def test_a_on_quit_quits_at_once():
    s = make()
    s.update(DT, nav(1))
    s.update(DT, nav(1))
    s.update(DT, confirm())
    assert s.quit_requested
    assert s.state == session.TITLE


def test_start_never_quits_it_starts_with_the_player_count():
    s = make()
    s.update(DT, nav(1))
    s.update(DT, nav(1))
    s.update(DT, start_button())
    assert not s.quit_requested
    assert s.state == session.TUTORIAL and s.mode == 2


def test_b_on_the_title_does_nothing():
    s = make()
    s.update(DT, nav(1))
    s.update(DT, nav(1))
    s.update(DT, frame(backs={"p1": True, "p2": False}))
    assert s.state == session.TITLE and not s.quit_requested


def test_a_on_a_player_row_starts_with_that_many():
    s = make()
    s.update(DT, nav(1))
    s.update(DT, confirm())
    assert s.state == session.TUTORIAL and s.mode == 2


def test_the_attract_demo_never_leaves_quit_selected():
    s = make()
    s.update(DT, nav(1))
    s.update(DT, nav(1))
    run(s, config.ATTRACT_DELAY + 0.5, frame(activity=False))
    assert s.attract
    assert session.TITLE_ITEMS[s.title_index] != "QUIT"
    s.update(DT, confirm())  # the A that wakes it starts a game, never quits
    assert not s.quit_requested


def test_beats_follow_their_timing():
    s = make()
    begin(s)
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


def test_play_ends_at_once_on_a_failure_and_a_short_beat_after_a_win():
    s = make([FailOnA])
    begin(s)
    to_play(s)
    s.update(DT, frame(PRESS))
    assert s.state == session.RESULT  # failed: no need to wait

    s = make([WinOnA])
    begin(s)
    to_play(s)
    events = s.update(DT, frame(PRESS))
    assert s.state == session.PLAY  # won: a beat so the win registers...
    assert s.games["p1"].result is True
    assert any(e.kind == "win" for e in events)
    run(s, config.WIN_LINGER - 0.05)
    assert s.state == session.PLAY
    run(s, 0.1)
    assert s.state == session.RESULT  # ...then on, long before the fuse is out
    assert s.score == 1
    assert 0.5 < s.time_left < 1.0  # the fuse left over stays on the result card


def test_a_survival_game_still_runs_to_the_end_of_the_fuse():
    s = make([FailOnA])  # won by not pressing: only the timer can decide it
    begin(s)
    to_play(s)
    run(s, play_time(0) - 0.1)
    assert s.state == session.PLAY


def test_versus_ends_once_both_are_decided():
    s = make(mode=2)
    begin(s)
    to_play(s)
    s.update(DT, frame(PRESS))  # p1 wins...
    run(s, 1.0)
    assert s.state == session.PLAY  # ...but p2 could still win: wait
    s.update(DT, frame(p2=PRESS))  # p2 wins too
    run(s, config.WIN_LINGER + 0.05)
    assert s.state == session.RESULT
    assert s.scores == {"p1": 2, "p2": 1}


def test_versus_a_win_and_a_failure_end_it_after_the_win_beat():
    class FailOnB(WinOnA):
        """Wins on A, fails on a stick push."""

        def step(self, dt, inp):
            if inp.a:
                self.win()
            elif inp.step != (0, 0):
                self.fail()

    s = make([FailOnB], mode=2)
    begin(s)
    to_play(s)
    s.update(DT, frame(PRESS, PlayerInput(step=(1, 0))))
    run(s, config.WIN_LINGER + 0.05)
    assert s.state == session.RESULT
    assert s.scores == {"p1": 1, "p2": 0}
    assert s.lives["p2"] == config.LIVES - 1


def test_presses_in_a_microgame_click():
    class Cursor(FailOnA):
        STEPS = True

    s = make([Cursor])
    begin(s)
    to_play(s)
    events = s.update(DT, frame(PlayerInput(step=(1, 0))))
    assert [e.kind for e in events] == ["tick"]
    s = make([FailOnA])  # a stick game without steps: no tick
    begin(s)
    to_play(s)
    assert s.update(DT, frame(PlayerInput(step=(1, 0)))) == []
    events = s.update(DT, frame(PRESS))  # an A that ends it: only the result's sound
    assert [e.kind for e in events] == ["fail"]


def test_timeout_is_called_at_the_end():
    s = make([FailOnA])  # wins on timeout
    begin(s)
    to_play(s)
    events = run(s, play_time(0) + 0.1)
    assert s.games["p1"].result is True
    assert s.score == 1
    assert any(e.kind == "win" for e in events)


def test_time_left_runs_down_during_play():
    s = make()
    begin(s)
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
    begin(s)
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
    begin(s)
    play_one(s, PRESS)
    assert (s.score, s.lives["p1"]) == (1, config.LIVES)
    play_one(s)  # did nothing
    assert (s.score, s.lives["p1"]) == (1, config.LIVES - 1)


def test_either_pad_plays_in_single_player():
    s = make()
    begin(s)
    play_one(s, p2=PRESS)
    assert s.score == 1
    assert list(s.games) == ["p1"]


def test_game_over_goes_to_initials_when_the_score_qualifies(tmp_path):
    s = make(hiscores=Hiscores(tmp_path / "s.json"))
    begin(s)
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
    begin(s)
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
    begin(s)
    a, b = s.games["p1"], s.games["p2"]
    assert a is not b
    assert type(a) is type(b)
    assert a.rng.random() == b.rng.random()


def test_versus_a_success_scores_one_and_finishing_first_one_more():
    s = make(mode=2)
    begin(s)
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
    begin(s)
    play_one(s, p2=PRESS)
    assert s.scores == {"p1": 0, "p2": 1}
    assert s.lives == {"p1": config.LIVES - 1, "p2": config.LIVES}


def test_versus_no_bonus_for_simultaneous_finishes():
    s = make(mode=2)
    begin(s)
    play_one(s, PRESS, PRESS)
    assert s.scores == {"p1": 1, "p2": 1}
    assert s.first is None


def test_versus_last_player_standing_wins():
    s = make(mode=2)
    begin(s)
    events = []
    for _ in range(config.LIVES):
        events += play_one(s, p2=PRESS)
    assert s.state == session.MATCH_RESULT
    assert s.winner == "p2"
    assert any(e.kind == "match_won" and e.player == "p2" for e in events)


def test_versus_both_out_together_higher_score_wins_else_draw():
    s = make(mode=2)
    begin(s)
    play_one(s, PRESS)  # p1 +1, p2 loses a life
    for _ in range(config.LIVES - 1):
        play_one(s)  # both lose a life each
    assert s.lives["p2"] == 0 and s.lives["p1"] == 1
    assert s.winner == "p1"

    s = make(mode=2)
    begin(s)
    events = []
    for _ in range(config.LIVES):
        events += play_one(s)
    assert s.state == session.MATCH_RESULT
    assert s.winner is None
    assert any(e.kind == "draw" for e in events)


def test_versus_rematch_and_back_to_title():
    s = make(mode=2)
    begin(s)
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
    begin(s)
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
    begin(s)
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
    begin(s)
    run(s, config.PAUSE_GRACE + 0.05)
    s.update(DT, start_button())
    assert s.paused
    s.update(DT, frame(nav={"p1": (0, 1), "p2": (0, 0)}))
    assert session.PAUSE_ITEMS[s.pause_index] == "QUIT TO TITLE"
    s.update(DT, confirm())
    assert s.state == session.TITLE and not s.paused


def test_idle_timeout_returns_to_the_title():
    s = make(registry=[FailOnA])  # survivable by doing nothing, so the run never ends
    begin(s)
    run(s, config.IDLE_TIMEOUT - 1, frame(activity=False))
    assert s.state != session.TITLE
    run(s, 1.1, frame(activity=False))
    assert s.state == session.TITLE


def test_real_registry_plays_through():
    """The real microgames, with their bots, run cleanly inside a session."""
    s = Session(random.Random(1))
    begin(s)
    for _ in range(6):
        to_play(s)
        while s.state == session.PLAY:
            g = s.games["p1"]
            s.update(DT, frame(g.bot()))
        assert s.games["p1"].result is True
        while s.state in (session.RESULT, session.SPEED_UP):
            s.update(DT, frame())


# --- bosses -------------------------------------------------------------------------------


def win_until_boss(s, p1=PRESS, p2=PlayerInput()):
    events = []
    while not (s.state == session.INTRO and s.boss):
        if s.state == session.PLAY:
            events += play_one(s, p1, p2)
        else:
            events += s.update(DT, frame())
    return events


def test_a_boss_comes_after_every_twelve_wins_with_a_warning():
    s = make()
    begin(s)
    events = win_until_boss(s)
    assert s.score == config.BOSS_EVERY
    assert any(e.kind == "boss" for e in events)
    assert s.game_cls is BossOnA
    assert s.games["p1"].duration == pytest.approx(BossOnA.duration_for(s.level))


def test_losses_dont_count_towards_the_boss():
    s = make()
    begin(s)
    play_one(s)  # a loss
    for _ in range(config.BOSS_EVERY - 1):
        play_one(s, PRESS)
    assert not s.boss and s.state != session.BOSS_CARD
    while s.state != session.PLAY:
        s.update(DT, frame())
    assert not s.boss  # still a microgame: only 11 wins so far


def test_a_boss_scores_three_and_ends_once_everyone_is_done():
    s = make(mode=2)
    begin(s)
    win_until_boss(s, PRESS, PRESS)
    before = dict(s.scores)
    to_play(s)
    s.update(DT, frame(PRESS))  # p1 first
    run(s, 0.2)
    s.update(DT, frame(p2=PRESS))
    run(s, config.BOSS_LINGER + 0.1)
    assert s.state == session.RESULT  # long before the boss's own timer
    assert s.t < 1.0
    assert s.scores["p1"] - before["p1"] == BossOnA.POINTS + 1
    assert s.scores["p2"] - before["p2"] == BossOnA.POINTS


def test_after_a_boss_the_microgames_carry_on_and_it_costs_a_life_if_lost():
    s = make()
    begin(s)
    win_until_boss(s)
    lives = s.lives["p1"]
    play_one(s)  # lose the boss
    assert s.lives["p1"] == lives - 1
    while s.state != session.INTRO:
        s.update(DT, frame())
    assert not s.boss


def test_the_real_boss_plays_through_inside_a_session():
    s = Session(random.Random(2), Hiscores(None))
    begin(s)
    s.toward_boss = config.BOSS_EVERY - 1
    while s.state != session.PLAY:
        s.update(DT, frame())
    while s.state == session.PLAY:  # the microgame that makes 12
        s.update(DT, frame(s.games["p1"].bot()))
    while not (s.state == session.PLAY and s.boss):
        s.update(DT, frame())
    while s.state == session.PLAY:
        s.update(DT, frame(s.games["p1"].bot()))
    assert s.games["p1"].result is True


class OtherBoss(BossOnA):
    VERB = "OTHER BOSS!"


def test_the_boss_card_knows_its_boss_and_the_bosses_come_in_order():
    s = make(bosses=(BossOnA, OtherBoss))
    begin(s)
    for expected in (BossOnA, OtherBoss, BossOnA):
        while s.state != session.BOSS_CARD:
            if s.state == session.PLAY:
                play_one(s, PRESS)
            else:
                s.update(DT, frame())
        assert s.next_boss is expected  # chosen as the card goes up, for the card to show
        assert not s.boss  # the last microgame is still the current game
        while s.state == session.BOSS_CARD:
            s.update(DT, frame())
        assert s.game_cls is expected and s.boss


# --- ending early on a win, with the real microgames -------------------------------------

TIMER_ONLY = {"SHIELD!", "REFRESH!"}  # won by surviving: only the fuse can decide them


@pytest.mark.parametrize("cls", REGISTRY, ids=lambda c: c.VERB)
def test_every_microgame_won_early_ends_a_beat_after_the_win(cls):
    s = Session(random.Random(5), Hiscores(None), [cls], [])
    begin(s)
    to_play(s)
    while s.state == session.PLAY:
        ended = s.t + DT
        s.update(DT, frame(s.games["p1"].bot()))
    g = s.games["p1"]
    assert g.result is True
    if cls.VERB in TIMER_ONLY:
        assert ended == pytest.approx(s.duration, abs=2 * DT)
    else:
        assert g.won_at < s.duration - 0.5
        assert ended == pytest.approx(g.won_at + config.WIN_LINGER, abs=2 * DT)
