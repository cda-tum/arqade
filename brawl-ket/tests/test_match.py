"""Tests for the match flow: title, select, rounds, result, pause, idle and attract."""

from __future__ import annotations

import random

import pytest

from brawl_ket import config
from brawl_ket.fighter import FighterInput
from brawl_ket.match import (
    FIGHT,
    MATCH_RESULT,
    PAUSE_ITEMS,
    ROUND_END,
    ROUND_INTRO,
    SELECT,
    STAGE_OPTIONS,
    STAGE_SELECT,
    TITLE,
    Cue,
    FrameInput,
    Match,
)
from brawl_ket.moves import BOHR, ROBERT


def press(kind: str, player: str = "p1", **extra) -> FrameInput:
    """One frame with a single press: confirm (A), start, back (B), left/right/up/down."""
    inp = FrameInput(activity=True, **extra)
    if kind == "confirm":
        inp.confirms[player] = True
    elif kind == "start":
        inp.confirms[player] = inp.pauses[player] = True
    elif kind == "back":
        inp.backs[player] = True
    else:
        inp.nav[player] = {"left": (-1, 0), "right": (1, 0), "up": (0, -1), "down": (0, 1)}[kind]
    return inp


def idle() -> FrameInput:
    return FrameInput()


def run(m: Match, frames: int, inp: FrameInput | None = None) -> list:
    events: list = []
    for _ in range(frames):
        events += m.update(inp or idle())
    return events


def cues(events: list) -> list[str]:
    return [e.kind for e in events if isinstance(e, Cue)]


def to_stage_select(m: Match, p1: int = 0, p2: int = 0) -> None:
    """From the title, both players pick and ready up: CHOOSE YOUR STAGE."""
    m.update(press("confirm"))
    assert m.state == SELECT
    for p, want in (("p1", p1), ("p2", p2)):
        while m.picks[p] != want:
            m.update(press("right", p))
        m.update(press("confirm", p))
    assert m.state == STAGE_SELECT


def to_fight(m: Match, p1: int = 0, p2: int = 0, stage: str | None = None) -> None:
    """From the title, both players pick and ready up, a stage is picked (RANDOM unless
    `stage` is named), then the intro runs out."""
    to_stage_select(m, p1, p2)
    want = STAGE_OPTIONS.index(stage) if stage else 0
    while m.stage_pick != want:
        m.update(press("right", "p2"))
    m.update(press("confirm"))
    assert m.state == ROUND_INTRO
    run(m, config.ROUND_INTRO_FRAMES)
    assert m.state == FIGHT


def ko(m: Match, loser: str) -> list:
    """End the current round with a KO on `loser`, then let the round end run out."""
    m.fight.fighters[loser].health = 0
    events = m.update(idle())
    assert m.state == ROUND_END
    events += run(m, config.ROUND_END_FRAMES)
    return events


# --- title and select -------------------------------------------------------------------


def test_a_or_start_on_the_title_goes_to_select() -> None:
    for kind in ("confirm", "start"):
        m = Match(random.Random(1))
        assert m.state == TITLE
        events = m.update(press(kind, "p2"))
        assert m.state == SELECT and "blip" in cues(events)


def test_select_starts_the_fight_with_the_picked_fighters() -> None:
    m = Match(random.Random(1))
    to_fight(m, p1=1, p2=0)
    assert m.fight.fighters["p1"].char is BOHR
    assert m.fight.fighters["p2"].char is ROBERT
    assert m.round_no == 1 and m.wins == {"p1": 0, "p2": 0}


def test_each_player_moves_only_their_own_pick() -> None:
    m = Match(random.Random(1))
    m.update(press("confirm"))
    before = dict(m.picks)
    m.update(press("right", "p1"))
    assert m.picks["p1"] != before["p1"] and m.picks["p2"] == before["p2"]
    m.update(press("left", "p1"))
    assert m.picks == before


def test_a_ready_player_cannot_change_their_pick() -> None:
    m = Match(random.Random(1))
    m.update(press("confirm"))
    m.update(press("confirm", "p1"))
    pick = m.picks["p1"]
    m.update(press("right", "p1"))
    assert m.ready["p1"] and m.picks["p1"] == pick


def test_b_unreadies_then_goes_back_to_the_title() -> None:
    m = Match(random.Random(1))
    m.update(press("confirm"))
    m.update(press("confirm", "p1"))
    assert m.ready["p1"]
    m.update(press("back", "p1"))
    assert m.state == SELECT and not m.ready["p1"]
    m.update(press("back", "p1"))
    assert m.state == TITLE


def test_the_round_intro_calls_the_round_then_fight() -> None:
    m = Match(random.Random(1))
    to_stage_select(m)
    events = m.update(press("confirm", "p2"))
    assert m.state == ROUND_INTRO and "round" in cues(events)
    frames_left = m.fight.frames_left
    events = run(m, config.ROUND_INTRO_FRAMES)
    assert cues(events).count("fight") == 1
    assert m.fight.frames_left == frames_left       # nobody moves during the intro


# --- CHOOSE YOUR STAGE ---------------------------------------------------------------------


def test_the_stage_list_is_random_then_every_stage() -> None:
    assert STAGE_OPTIONS == ("random", *config.STAGES)


def test_both_ready_goes_to_the_stage_select_on_random() -> None:
    m = Match(random.Random(1))
    m.update(press("confirm"))
    m.update(press("confirm", "p1"))
    assert m.state == SELECT
    events = m.update(press("confirm", "p2"))
    assert m.state == STAGE_SELECT and m.stage_pick == 0 and "blip" in cues(events)
    assert m.fight is None


def test_either_stick_flips_through_the_stages_and_wraps() -> None:
    m = Match(random.Random(1))
    to_stage_select(m)
    events = m.update(press("right", "p1"))
    assert m.stage_pick == 1 and "blip" in cues(events)
    m.update(press("right", "p2"))
    assert m.stage_pick == 2
    m.update(press("up", "p1"))             # only left and right move it
    assert m.stage_pick == 2
    for _ in range(2):
        m.update(press("left", "p2"))
    m.update(press("left", "p1"))
    assert m.stage_pick == len(STAGE_OPTIONS) - 1


@pytest.mark.parametrize("kind", ["confirm", "start"])
def test_a_or_start_on_the_stage_select_starts_the_match(kind) -> None:
    m = Match(random.Random(1))
    to_stage_select(m)
    events = m.update(press(kind, "p1"))
    assert m.state == ROUND_INTRO and not m.paused and "round" in cues(events)
    assert m.round_no == 1 and m.hint


def test_a_held_a_from_the_fighter_screen_does_not_pick_the_stage() -> None:
    # presses are edges: the A that readied the last player is spent, holding it does nothing
    m = Match(random.Random(1))
    to_stage_select(m)
    run(m, 30, FrameInput(activity=True, held=True))
    assert m.state == STAGE_SELECT


def test_b_on_the_stage_select_goes_back_with_both_still_ready() -> None:
    m = Match(random.Random(1))
    to_stage_select(m, p1=1)
    m.update(press("right"))
    events = m.update(press("back", "p2"))
    assert m.state == SELECT and m.ready == {"p1": True, "p2": True} and "blip" in cues(events)
    run(m, 30)
    assert m.state == SELECT                # both ready, but nobody pressed A
    events = m.update(press("confirm", "p2"))   # one A goes on again, to the same stage
    assert m.state == STAGE_SELECT and "blip" in cues(events) and m.stage_pick == 1 and m.picks["p1"] == 1


def test_b_on_the_fighter_screen_with_both_ready_unreadies_as_before() -> None:
    m = Match(random.Random(1))
    to_stage_select(m)
    m.update(press("back"))
    m.update(press("back", "p1"))
    assert m.state == SELECT and m.ready == {"p1": False, "p2": True}
    m.update(press("confirm", "p2"))        # the ready one can't go on alone
    assert m.state == SELECT
    m.update(press("confirm", "p1"))
    assert m.state == STAGE_SELECT


@pytest.mark.parametrize("stage", config.STAGES)
def test_a_picked_stage_is_used_for_every_round(stage) -> None:
    m = Match(random.Random(1))
    to_fight(m, stage=stage)
    assert m.stage == stage
    ko(m, "p2")
    assert m.state == ROUND_INTRO and m.stage == stage


def test_random_picks_from_the_stages_and_varies() -> None:
    seen = set()
    for seed in range(20):
        m = Match(random.Random(seed))
        to_fight(m)
        assert m.stage_pick == 0 and m.stage in config.STAGES
        seen.add(m.stage)
    assert len(seen) >= 3


def finish(m: Match) -> None:
    """Win the match for p1 and wait out the result's lock."""
    for _ in range(config.ROUNDS_TO_WIN):
        ko(m, "p2")
        if m.state == ROUND_INTRO:
            run(m, config.ROUND_INTRO_FRAMES)
    assert m.state == MATCH_RESULT
    run(m, config.MATCH_RESULT_LOCK)


def test_a_rematch_keeps_the_picked_stage() -> None:
    m = Match(random.Random(1))
    to_fight(m, stage="optics")
    finish(m)
    m.update(press("confirm"))
    assert m.state == ROUND_INTRO and m.stage == "optics" and m.stage_pick == STAGE_OPTIONS.index("optics")


def test_a_rematch_on_random_rolls_again() -> None:
    seen = set()
    m = Match(random.Random(5))
    to_fight(m)
    for _ in range(12):
        finish(m)
        m.update(press("confirm"))
        assert m.stage_pick == 0 and m.stage in config.STAGES
        seen.add(m.stage)
        run(m, config.ROUND_INTRO_FRAMES)
    assert len(seen) >= 2


def test_the_pick_is_remembered_until_the_title() -> None:
    m = Match(random.Random(1))
    to_fight(m, stage="cryo")
    finish(m)
    m.update(press("back"))                 # the result's B: the title
    assert m.state == TITLE and m.stage_pick == 0
    to_stage_select(m)
    assert m.stage_pick == 0


def test_quit_to_title_and_the_idle_timeout_reset_the_pick() -> None:
    m = Match(random.Random(1))
    to_fight(m, stage="lab")
    run(m, config.IDLE_TIMEOUT)
    assert m.state == TITLE and m.stage_pick == 0
    m = Match(random.Random(1))
    to_stage_select(m)
    m.update(press("right"))
    run(m, config.IDLE_TIMEOUT)
    assert m.state == TITLE and m.stage_pick == 0


def test_the_demo_still_picks_a_random_stage() -> None:
    m = Match(random.Random(1))
    to_fight(m, stage="office")
    run(m, config.IDLE_TIMEOUT)
    seen = set()
    for _ in range(8):
        run(m, config.ATTRACT_DELAY + 2)
        assert m.attract is not None
        seen.add(m.stage)
        m.update(press("confirm"))          # stops the demo
    assert len(seen) >= 2 and m.stage_pick == 0


# --- rounds and the match ----------------------------------------------------------------


def test_a_fight_steps_with_the_players_inputs() -> None:
    m = Match(random.Random(1))
    to_fight(m)
    x = m.fight.fighters["p1"].x
    run(m, 10, FrameInput(fighters={"p1": FighterInput(dx=1), "p2": FighterInput()}, activity=True))
    assert m.fight.fighters["p1"].x > x


def test_a_match_won_two_rounds_to_nil() -> None:
    m = Match(random.Random(1))
    to_fight(m)
    events = ko(m, "p2")
    assert "ko" in cues(events) and m.wins == {"p1": 1, "p2": 0}
    assert m.state == ROUND_INTRO and m.round_no == 2
    run(m, config.ROUND_INTRO_FRAMES)
    events = ko(m, "p2")
    assert m.state == MATCH_RESULT and m.winner == "p1"
    assert Cue("match_won", "p1") in events


def test_a_match_won_two_rounds_to_one() -> None:
    m = Match(random.Random(1))
    to_fight(m)
    for loser in ("p1", "p2"):
        ko(m, loser)
        run(m, config.ROUND_INTRO_FRAMES)
    assert m.wins == {"p1": 1, "p2": 1} and m.round_no == 3
    ko(m, "p1")
    assert m.state == MATCH_RESULT and m.winner == "p2"


def test_a_draw_round_counts_for_nobody() -> None:
    m = Match(random.Random(1))
    to_fight(m)
    m.fight.frames_left = 1             # time runs out at equal health
    events = m.update(idle())
    assert m.state == ROUND_END and m.round_winner is None
    assert "timeout" in cues(events) and "draw" in cues(events)
    run(m, config.ROUND_END_FRAMES)
    assert m.wins == {"p1": 0, "p2": 0} and m.round_no == 2 and m.state == ROUND_INTRO


def test_a_win_at_full_health_is_perfect() -> None:
    m = Match(random.Random(1))
    to_fight(m)
    m.fight.fighters["p2"].health = 0
    events = m.update(idle())
    assert Cue("perfect", "p1") in events and m.perfect


def test_a_win_with_damage_taken_is_not_perfect() -> None:
    m = Match(random.Random(1))
    to_fight(m)
    m.fight.fighters["p1"].health -= 10
    m.fight.fighters["p2"].health = 0
    events = m.update(idle())
    assert "perfect" not in cues(events) and not m.perfect


def test_the_result_waits_then_a_rematches_with_the_same_picks() -> None:
    m = Match(random.Random(1))
    to_fight(m, p1=1, p2=1)
    ko(m, "p2")
    run(m, config.ROUND_INTRO_FRAMES)
    ko(m, "p2")
    assert m.state == MATCH_RESULT
    m.update(press("confirm"))
    assert m.state == MATCH_RESULT          # locked for a moment
    run(m, config.MATCH_RESULT_LOCK)
    m.update(press("confirm", "p2"))
    assert m.state == ROUND_INTRO and m.wins == {"p1": 0, "p2": 0} and m.round_no == 1
    assert m.fight.fighters["p1"].char is BOHR and m.fight.fighters["p2"].char is BOHR


def test_b_on_the_result_goes_to_the_title() -> None:
    m = Match(random.Random(1))
    to_fight(m)
    ko(m, "p2")
    run(m, config.ROUND_INTRO_FRAMES)
    ko(m, "p2")
    run(m, config.MATCH_RESULT_LOCK)
    m.update(press("back", "p1"))
    assert m.state == TITLE and m.fight is None


# --- pause ---------------------------------------------------------------------------------


@pytest.mark.parametrize("state", [ROUND_INTRO, FIGHT, ROUND_END])
def test_start_pauses_and_everything_freezes(state) -> None:
    m = Match(random.Random(1))
    to_fight(m)
    if state == ROUND_INTRO:
        ko(m, "p2")
    elif state == ROUND_END:
        m.fight.fighters["p2"].health = 0
        m.update(idle())
    assert m.state == state
    events = m.update(press("start", "p2"))
    assert m.paused and "pause" in cues(events)
    t, frames_left = m.t, m.fight.frames_left
    run(m, 300, FrameInput(fighters={"p1": FighterInput(dx=1), "p2": FighterInput()}, activity=True))
    assert m.state == state and m.t == t and m.fight.frames_left == frames_left


def test_start_or_b_resumes() -> None:
    for kind in ("start", "back"):
        m = Match(random.Random(1))
        to_fight(m)
        m.update(press("start"))
        m.update(press(kind, "p2"))
        assert not m.paused and m.state == FIGHT


def test_resume_and_quit_to_title_are_picked_with_the_stick_and_a() -> None:
    assert PAUSE_ITEMS == ("RESUME", "QUIT TO TITLE")
    m = Match(random.Random(1))
    to_fight(m)
    m.update(press("start"))
    m.update(press("confirm"))              # RESUME
    assert not m.paused and m.state == FIGHT
    m.update(press("start"))
    assert m.pause_index == 0
    m.update(press("down"))
    assert m.pause_index == 1
    m.update(press("confirm", "p2"))        # QUIT TO TITLE
    assert m.state == TITLE and not m.paused and m.fight is None


def test_the_title_after_quit_waits_for_the_buttons_to_be_let_go() -> None:
    m = Match(random.Random(1))
    to_fight(m)
    m.update(press("start"))
    m.update(press("down"))
    m.update(press("confirm"))
    assert m.state == TITLE
    m.update(press("confirm", held=True))   # the A that picked QUIT is still down
    assert m.state == TITLE
    m.update(idle())                        # let go
    m.update(press("confirm"))
    assert m.state == SELECT


# --- idle and attract ----------------------------------------------------------------------


def test_idle_returns_to_the_title_even_while_paused() -> None:
    m = Match(random.Random(1))
    to_fight(m)
    m.update(press("start"))
    run(m, config.IDLE_TIMEOUT)
    assert m.state == TITLE and not m.paused


def test_idle_on_select_returns_to_the_title() -> None:
    m = Match(random.Random(1))
    m.update(press("confirm"))
    run(m, config.IDLE_TIMEOUT)
    assert m.state == TITLE


def test_input_keeps_the_idle_timer_down() -> None:
    m = Match(random.Random(1))
    to_fight(m)
    for _ in range(config.IDLE_TIMEOUT + 10):
        m.update(FrameInput(activity=True))
        if m.state != FIGHT:
            break
    assert m.idle == 0


def test_an_untouched_title_runs_a_bot_demo_and_any_input_stops_it() -> None:
    m = Match(random.Random(1))
    run(m, config.ATTRACT_DELAY - 1)
    assert m.attract is None
    run(m, 2)
    assert m.attract is not None
    fight = m.attract
    run(m, 120)
    moved = {p: fight.fighters[p].x for p in ("p1", "p2")}
    assert moved != {"p1": config.START_X["p1"], "p2": config.START_X["p2"]}
    m.update(press("confirm"))              # the press that stops the demo does only that
    assert m.attract is None and m.state == TITLE
    m.update(press("confirm"))
    assert m.state == SELECT


def test_the_demo_starts_a_new_fight_when_one_ends() -> None:
    m = Match(random.Random(1))
    run(m, config.ATTRACT_DELAY + 1)
    first = m.attract
    first.fighters["p1"].health = 0
    run(m, config.ROUND_END_FRAMES + 2)
    assert m.attract is not None and m.attract is not first and m.state == TITLE


# --- the K.O. slow-down --------------------------------------------------------------------


def steps_of(m: Match, frames: int) -> int:
    """How many times the fight was stepped over `frames` match frames."""
    count = 0
    real = m.fight.step

    def counted(inputs):
        nonlocal count
        count += 1
        return real(inputs)

    m.fight.step = counted
    run(m, frames)
    m.fight.step = real
    return count


def test_a_ko_plays_out_in_slow_motion_then_at_full_speed() -> None:
    m = Match(random.Random(1))
    to_fight(m)
    m.fight.fighters["p2"].health = 0
    m.update(idle())
    assert m.state == ROUND_END and m.ko
    slow = steps_of(m, config.KO_SLOW_FRAMES)
    assert slow == config.KO_SLOW_FRAMES // config.KO_SLOW_RATE
    assert steps_of(m, 30) == 30


def test_a_timeout_is_not_slowed_down() -> None:
    m = Match(random.Random(1))
    to_fight(m)
    m.fight.frames_left = 1
    m.update(idle())
    assert m.state == ROUND_END and not m.ko
    assert steps_of(m, 30) == 30


# --- teaching: the rules card and the first-round hint -----------------------------------


def test_the_title_alternates_the_demo_and_the_rules_card() -> None:
    m = Match(random.Random(1))
    run(m, config.ATTRACT_DELAY + 1)
    assert m.attract is not None and not m.card
    run(m, config.DEMO_FRAMES)
    assert m.card and m.attract is None
    run(m, config.CARD_FRAMES)
    assert not m.card and m.attract is not None
    run(m, config.DEMO_FRAMES)
    assert m.card
    m.update(press("confirm"))              # any input ends the card, and does nothing else
    assert not m.card and m.attract is None and m.state == TITLE
    m.update(press("confirm"))
    assert m.state == SELECT


def test_only_a_matchs_first_round_intro_shows_the_hint() -> None:
    m = Match(random.Random(1))
    to_stage_select(m)
    m.update(press("confirm", "p2"))
    assert m.state == ROUND_INTRO and m.hint
    run(m, config.ROUND_INTRO_FRAMES)
    assert m.state == FIGHT
    ko(m, "p2")
    assert m.state == ROUND_INTRO and not m.hint
