"""Tests for the match flow: title, select, stage select, HOW TO PLAY, rounds, result, pause,
idle and attract."""

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
    STAGE_LOCK,
    STAGE_SELECT,
    TITLE,
    TITLE_ITEMS,
    TUTORIAL,
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


def any_button(**extra) -> FrameInput:
    """Any button at all (on the HOW TO PLAY card, L or Select counts as much as A)."""
    return FrameInput(activity=True, any_button=True, **extra)


def past_tutorial(m: Match) -> list:
    """Read the HOW TO PLAY card for its lock, then press a button."""
    assert m.state == TUTORIAL
    run(m, config.TUTORIAL_LOCK)
    events = m.update(any_button())
    assert m.state == ROUND_INTRO
    return events


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
    run(m, STAGE_LOCK)


def to_fight(m: Match, p1: int = 0, p2: int = 0, stage: str | None = None) -> None:
    """From the title, both players pick and ready up, a stage is picked (RANDOM unless
    `stage` is named), then the intro runs out."""
    to_stage_select(m, p1, p2)
    want = STAGE_OPTIONS.index(stage) if stage else 0
    while m.stage_pick != want:
        m.update(press("right", "p2"))
    m.update(press("confirm"))
    past_tutorial(m)
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
        assert m.state == TITLE and TITLE_ITEMS[m.title_index] == "PLAY"
        events = m.update(press(kind, "p2"))
        assert m.state == SELECT and "confirm" in cues(events)


def test_the_title_menu_ends_with_quit_and_the_stick_moves_through_it() -> None:
    assert TITLE_ITEMS == ("PLAY", "CPU VS CPU", "QUIT")
    m = Match(random.Random(1))
    assert "blip" in cues(m.update(press("down", "p2")))
    assert TITLE_ITEMS[m.title_index] == "CPU VS CPU"
    m.update(press("down"))
    assert TITLE_ITEMS[m.title_index] == "QUIT"
    m.update(press("down"))                 # round again
    assert TITLE_ITEMS[m.title_index] == "PLAY"
    m.update(press("up"))
    assert TITLE_ITEMS[m.title_index] == "QUIT" and not m.quit


def test_a_on_quit_quits_at_once() -> None:
    m = Match(random.Random(1))
    m.update(press("up"))
    m.update(press("confirm", "p2"))
    assert m.quit and m.state == TITLE


def test_start_always_plays_and_b_never_quits() -> None:
    m = Match(random.Random(1))
    m.update(press("up"))
    m.update(press("back"))
    assert not m.quit and m.state == TITLE
    m.update(press("start"))                # QUIT is selected, but Start starts
    assert not m.quit and m.state == SELECT and not any(m.cpu.values())


def test_the_demo_puts_the_title_back_on_play() -> None:
    """Whoever stops the demo with A must not find QUIT under it."""
    m = Match(random.Random(1))
    m.update(press("down"))
    run(m, config.ATTRACT_DELAY + 1)
    assert m.attract is not None
    m.update(press("confirm"))              # stops the demo
    m.update(press("confirm"))
    assert m.state == SELECT and not m.quit


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
    m.update(press("confirm", "p2"))
    events = past_tutorial(m)
    assert "round" in cues(events)
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
    assert m.state == TUTORIAL and not m.paused and "confirm" in cues(events)
    events = past_tutorial(m)
    assert not m.paused and "round" in cues(events)
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


def test_each_round_gets_its_seed_from_the_matchs_rng() -> None:
    seeds = []
    for _ in range(2):
        m = Match(random.Random(4))
        to_fight(m)
        seeds.append(m.fight.seed)
    assert seeds[0] == seeds[1]
    m = Match(random.Random(4))
    to_fight(m)
    first = m.fight.seed
    ko(m, "p2")                             # round 2: a fresh fight, a fresh seed
    assert m.state == ROUND_INTRO and m.fight.seed != first


def test_the_demo_fight_is_seeded_from_the_matchs_rng() -> None:
    a, b = Match(random.Random(9)), Match(random.Random(9))
    for m in (a, b):
        run(m, config.ATTRACT_DELAY + 1)
    assert a.attract is not None and a.attract.seed == b.attract.seed


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
    past_tutorial(m)
    assert m.hint
    run(m, config.ROUND_INTRO_FRAMES)
    assert m.state == FIGHT
    ko(m, "p2")
    assert m.state == ROUND_INTRO and not m.hint


def test_a_mashed_a_cannot_skip_the_stage_screen():
    m = Match(random.Random(1))
    m.update(press("confirm"))
    for p in ("p1", "p2"):
        m.update(press("confirm", p))
    assert m.state == STAGE_SELECT
    m.update(press("confirm"))                  # the very next frame: still choosing
    assert m.state == STAGE_SELECT
    run(m, STAGE_LOCK)
    m.update(press("confirm"))
    assert m.state == TUTORIAL


# --- HOW TO PLAY -------------------------------------------------------------------------


def to_tutorial(m: Match, stage: str | None = None) -> None:
    to_stage_select(m)
    want = STAGE_OPTIONS.index(stage) if stage else 0
    while m.stage_pick != want:
        m.update(press("right", "p2"))
    m.update(press("confirm"))


def test_a_stage_picked_shows_how_to_play_in_that_room_before_the_round() -> None:
    m = Match(random.Random(1))
    to_tutorial(m, stage="cryo")
    assert m.state == TUTORIAL and m.lesson is not None and m.fight is None and m.stage == "cryo"
    past_tutorial(m)
    assert m.stage == "cryo"


def test_on_random_the_card_shows_the_room_the_match_is_fought_in() -> None:
    for seed in range(8):
        m = Match(random.Random(seed))
        to_tutorial(m)
        shown = m.stage
        past_tutorial(m)
        assert m.stage == shown


def test_how_to_play_ignores_buttons_at_first_then_any_button_goes_on() -> None:
    m = Match(random.Random(1))
    to_tutorial(m)
    for _ in range(config.TUTORIAL_LOCK - 1):   # the A that picked the stage, bouncing
        m.update(any_button())
    assert m.state == TUTORIAL
    m.update(idle())
    events = m.update(any_button())
    assert m.state == ROUND_INTRO and "confirm" in cues(events) and "round" in cues(events)
    assert m.lesson is None and m.wins == {"p1": 0, "p2": 0} and m.hint


def test_the_stick_and_holding_do_not_take_how_to_play_away() -> None:
    m = Match(random.Random(1))
    to_tutorial(m)
    run(m, config.TUTORIAL_LOCK + 1)
    for kind in ("left", "right", "up", "down"):
        m.update(press(kind, "p2"))
    m.update(FrameInput(activity=True, held=True))
    assert m.state == TUTORIAL


def test_how_to_play_plays_its_scene_and_cannot_be_paused() -> None:
    m = Match(random.Random(1))
    to_tutorial(m)
    events = run(m, 60)
    assert any(getattr(e, "kind", None) == "hit" for e in events)   # the scene's first jab
    m.update(press("start", held=True))
    assert m.state == TUTORIAL and not m.paused


def test_idle_on_how_to_play_returns_to_the_title() -> None:
    m = Match(random.Random(1))
    to_tutorial(m)
    run(m, config.IDLE_TIMEOUT)
    assert m.state == TITLE and m.lesson is None


def test_a_rematch_skips_how_to_play_but_a_new_match_shows_it_again() -> None:
    m = Match(random.Random(1))
    to_fight(m, stage="optics")
    finish(m)
    m.update(press("confirm"))              # rematch: the same people, the same room, straight in
    assert m.state == ROUND_INTRO and m.stage == "optics"
    m.update(press("start"))                # QUIT TO TITLE
    m.update(press("down"))
    m.update(press("confirm"))
    assert m.state == TITLE
    m.update(idle())
    to_tutorial(m)
    assert m.state == TUTORIAL


def test_dos_starts_every_round_with_an_empty_clipboard() -> None:
    from brawl_ket.moves import DOS
    m = Match(random.Random(1))
    to_fight(m, p1=4)
    dos = m.fight.fighters["p1"]
    assert dos.char is DOS and dos.clipboard is None
    dos.clipboard = (ROBERT.moves["stand.X"], "Z")
    ko(m, "p2")
    assert m.state == ROUND_INTRO and m.fight.fighters["p1"].clipboard is None


def test_choose_your_fighter_cycles_through_all_seven_in_order() -> None:
    from brawl_ket.match import ROSTER
    order = ["ROBERT", "BOHR", "PHOEBE", "ERWIN", "DOS", "M-CUTIE", "ALICE & BOB"]
    assert [c.name for c in ROSTER] == order
    m = Match(random.Random(1))
    m.update(press("confirm"))
    seen = []
    for _ in range(len(ROSTER)):
        seen.append(ROSTER[m.picks["p1"]].name)
        m.update(press("right", "p1"))
    assert seen == order and m.picks["p1"] == 0         # and round again


def test_the_demo_picks_its_fighters_from_all_seven() -> None:
    from brawl_ket.match import ROSTER
    m = Match(random.Random(3))
    seen = set()
    for _ in range(40):
        m._start_attract()
        seen |= {f.char.name for f in m.attract.fighters.values()}
    assert len(ROSTER) == 7 and seen == {c.name for c in ROSTER}


def test_the_fighter_cursor_goes_round_the_row_and_stops_at_the_grids_edge() -> None:
    from brawl_ket.match import ROSTER, ROSTER_COLS, grid_move
    last = len(ROSTER) - 1
    assert grid_move(0, -1, 0) == last and grid_move(last, 1, 0) == 0      # left and right wrap
    assert grid_move(2, 0, -1) == 2                                         # no row above
    below = 2 + ROSTER_COLS
    assert grid_move(2, 0, 1) == (below if below <= last else 2)            # a row down, if there is one


def test_up_and_down_on_select_move_by_a_row() -> None:
    m = Match(random.Random(1))
    m.update(press("confirm"))
    assert m.state == SELECT
    before = m.picks["p1"]
    m.update(FrameInput(activity=True, nav={"p1": (0, 1), "p2": (0, 0)}))
    from brawl_ket.match import ROSTER, ROSTER_COLS
    assert m.picks["p1"] == (before + ROSTER_COLS if before + ROSTER_COLS < len(ROSTER) else before)


def test_m_cutie_starts_every_round_with_no_traps() -> None:
    from brawl_ket.fight import Trap
    from brawl_ket.moves import M_CUTIE, TRAP_HOLD
    m = Match(random.Random(1))
    to_fight(m, p1=5)
    assert m.fight.fighters["p1"].char is M_CUTIE and m.fight.traps == []
    m.fight.traps.append(Trap("p1", TRAP_HOLD, 300.0, "Z"))
    ko(m, "p2")
    assert m.state == ROUND_INTRO and m.fight.traps == []


def test_m_cutie_is_down_a_row_from_robert_and_back_up() -> None:
    from brawl_ket.match import ROSTER, grid_move
    assert ROSTER[5].name == "M-CUTIE"
    assert grid_move(0, 0, 1) == 5 and grid_move(5, 0, -1) == 0 and grid_move(2, 0, 1) == 2
    assert grid_move(5, 1, 0) == 6 and grid_move(6, 1, 0) == 0 and grid_move(0, -1, 0) == 6   # and round the roster


def test_alice_and_bob_are_down_a_row_from_bohr() -> None:
    from brawl_ket.match import ROSTER, grid_move
    assert ROSTER[6].name == "ALICE & BOB"
    assert grid_move(1, 0, 1) == 6 and grid_move(6, 0, -1) == 1 and grid_move(2, 0, 1) == 2


def test_a_pair_starts_every_round_together() -> None:
    from brawl_ket.config import ECHO_GAP
    from brawl_ket.match import ROSTER
    assert len(ROSTER) == 7                     # (to_fight would never reach a seventh pick)
    m = Match(random.Random(1))
    to_fight(m, p1=6)
    alice, bob = m.fight.fighters["p1"], m.fight.echoes["p1"]
    bob.decohere()
    ko(m, "p2")
    alice, bob = m.fight.fighters["p1"], m.fight.echoes["p1"]
    assert m.state == ROUND_INTRO and bob.here and bob.x == alice.x - ECHO_GAP


def test_the_demo_plays_alice_and_bob_with_their_bot() -> None:
    m = Match(random.Random(3))
    for _ in range(100):
        m._start_attract()
        keys = [k for k, f in m.attract.fighters.items() if f.char.pair is not None]
        if keys:
            break
    key = keys[0]
    bob = m.attract.echoes[key]
    echoed = False
    for _ in range(900):
        m._step_attract()
        if m.attract is None or key not in m.attract.echoes:
            break
        bob = m.attract.echoes[key]
        echoed = echoed or bob.action == "attack"
    assert echoed                       # the bot drove Alice, and Bob echoed her


# --- CPU VS CPU ---------------------------------------------------------------------------------


def to_cpu_select(m: Match, kind: str = "confirm") -> None:
    m.update(press("down"))
    assert TITLE_ITEMS[m.title_index] == "CPU VS CPU"
    m.update(press(kind))
    assert m.state == SELECT and m.watching


def to_cpu_fight(m: Match, p1: int = 0, p2: int = 1) -> None:
    """From the title, CPU VS CPU: pick both fighters with P1's pad, RANDOM stage, intro."""
    to_cpu_select(m)
    for p, want in (("p1", p1), ("p2", p2)):
        assert m.picking == p
        while m.picks[p] != want:
            m.update(press("right"))
        m.update(press("confirm"))
    assert m.state == STAGE_SELECT
    run(m, STAGE_LOCK)
    m.update(press("confirm"))
    assert m.state == ROUND_INTRO           # no HOW TO PLAY: nobody plays
    run(m, config.ROUND_INTRO_FRAMES)
    assert m.state == FIGHT


@pytest.mark.parametrize("kind", ["confirm", "start"])
def test_a_or_start_on_cpu_vs_cpu_starts_it(kind) -> None:
    m = Match(random.Random(1))
    to_cpu_select(m, kind)
    assert m.cpu == {"p1": True, "p2": True} and m.picking == "p1"


def test_play_is_people_on_both_sides() -> None:
    m = Match(random.Random(1))
    m.update(press("confirm"))
    assert not m.watching and m.cpu == {"p1": False, "p2": False}


def test_either_pad_picks_the_left_cpu_then_the_right_one() -> None:
    m = Match(random.Random(1))
    to_cpu_select(m)
    m.update(press("right", "p2"))
    assert m.picks["p1"] == 1               # p2's pad works the one cursor too
    m.update(press("confirm", "p2"))
    assert m.ready["p1"] and m.picking == "p2"
    before = m.picks["p2"]
    m.update(press("right"))
    assert m.picks["p2"] == before + 1 and m.picks["p1"] == 1


def test_b_takes_the_last_cpu_pick_back_then_goes_to_the_title() -> None:
    m = Match(random.Random(1))
    to_cpu_select(m)
    m.update(press("confirm"))
    m.update(press("back", "p2"))
    assert m.state == SELECT and m.picking == "p1"
    m.update(press("back"))
    assert m.state == TITLE and not m.watching


def test_back_from_the_stage_select_one_a_goes_on() -> None:
    m = Match(random.Random(1))
    to_cpu_select(m)
    m.update(press("confirm"))
    m.update(press("confirm"))
    assert m.state == STAGE_SELECT
    m.update(press("back"))
    assert m.state == SELECT and m.picking is None
    m.update(press("confirm"))
    assert m.state == STAGE_SELECT


def test_the_cpu_fights_both_sides_and_the_pads_do_nothing() -> None:
    m = Match(random.Random(1))
    to_cpu_fight(m, p1=0, p2=1)
    assert m.fight.fighters["p1"].char is ROBERT and m.fight.fighters["p2"].char is BOHR
    start = {p: f.x for p, f in m.fight.fighters.items()}
    walk = FrameInput(activity=True)
    walk.fighters["p1"] = FighterInput(dx=-1)       # a person pushing left: ignored
    run(m, 120, walk)
    moved = {p: m.fight.fighters[p].x != start[p] for p in start}
    assert moved == {"p1": True, "p2": True}
    assert m.fight.fighters["p1"].x > start["p1"]   # the bot walked in, not left


def test_a_cpu_match_plays_to_the_end_untouched_and_names_the_winner_cpu() -> None:
    m = Match(random.Random(3))
    to_cpu_fight(m)
    for _ in range(config.FPS * 60 * 6):
        m.update(idle())
        if m.state in (MATCH_RESULT, TITLE):
            break
    assert m.state == MATCH_RESULT          # the idle timeout never cut it short
    assert m.wins[m.winner] == config.ROUNDS_TO_WIN


def test_a_paused_cpu_match_still_times_out() -> None:
    m = Match(random.Random(1))
    to_cpu_fight(m)
    m.update(press("start"))
    assert m.paused
    run(m, config.IDLE_TIMEOUT)
    assert m.state == TITLE and not m.watching


def test_a_cpu_rematch_is_cpu_again_and_the_title_clears_it() -> None:
    m = Match(random.Random(1))
    to_cpu_fight(m)
    finish(m)
    run(m, config.MATCH_RESULT_LOCK)
    m.update(press("confirm"))
    assert m.state == ROUND_INTRO and m.watching and set(m.cpu_bots) == {"p1", "p2"}
    m._to_title()
    assert not m.watching and m.cpu_bots == {}
