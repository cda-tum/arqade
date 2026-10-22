"""Tests for SUPERposition (superpos.py, and the fight's and the fighter's part in it)."""

from __future__ import annotations

from dataclasses import replace

from brawl_ket import basis
from brawl_ket.fight import Fight
from brawl_ket.fighter import FighterInput
from brawl_ket.moves import CHARACTERS, ROBERT
from brawl_ket.superpos import FULL, Meter

Z, X = basis.Z_BASIS, basis.X_BASIS
A = FighterInput(a=True)
B = FighterInput(b=True)
DOS = CHARACTERS["DOS"]


def fight_of(a=ROBERT, b=ROBERT, gap: float = 50.0) -> Fight:
    fight = Fight({"p1": a, "p2": b}, seed=1)
    fight.fighters["p1"].x = 300.0
    fight.fighters["p2"].x = 300.0 + gap
    return fight


def until(fight: Fight, kind: str, first: dict | None = None, frames: int = 60) -> list:
    """Step once with `first`, then idle until an event of `kind` (or `frames` run out)."""
    events = fight.step(first or {})
    for _ in range(frames):
        if any(e.kind == kind for e in events):
            break
        events += fight.step({})
    return events


# --- the bar ---------------------------------------------------------------------------------


def test_a_half_takes_40_points_dealt_or_80_taken():
    assert FULL == 80
    m = Meter()
    assert m.fill == {Z: 0, X: 0} and not m.full
    assert m.dealt(Z, 39) == [] and m.share(Z) == 78 / 80
    assert m.dealt(Z, 1) == ["half"] and m.share(Z) == 1.0 and not m.full
    m.empty()
    assert m.taken(X, 40) == [] and m.share(X) == 0.5


def test_the_bar_is_full_only_with_both_halves_and_says_so_once():
    m = Meter()
    assert m.dealt(Z, 50) == ["half"]           # the overflow is lost
    assert m.fill[Z] == FULL
    assert m.dealt(Z, 10) == []                 # already full: nothing new
    assert m.dealt(X, 40) == ["half", "full"]
    assert m.full
    m.empty()
    assert m.fill == {Z: 0, X: 0} and not m.full


# --- filling in a fight ----------------------------------------------------------------------


def test_a_hit_fills_the_attackers_half_of_its_basis_and_the_hit_ones_at_half_rate():
    fight = fight_of()
    until(fight, "hit", {"p1": A})                  # green ROBERT jabs green ROBERT: 4
    assert fight.meters["p1"].fill == {Z: 8, X: 0}
    assert fight.meters["p2"].fill == {Z: 4, X: 0}


def test_the_half_is_the_attackers_basis_not_the_colour_of_the_hit():
    fight = fight_of()
    fight.fighters["p1"].basis = X                  # purple ROBERT's B is green: it hurts green p2
    until(fight, "hit", {"p1": B})
    assert fight.fighters["p2"].health == ROBERT.health - 8
    assert fight.meters["p1"].fill == {Z: 0, X: 16}
    assert fight.meters["p2"].fill == {Z: 8, X: 0}


def test_dos_fills_the_half_of_the_hits_colour():
    fight = fight_of(DOS, ROBERT, gap=60.0)
    fight.fighters["p2"].basis = X                  # DOS's B is purple: it hurts purple ROBERT
    until(fight, "hit", {"p1": B})
    dealt = ROBERT.health - fight.fighters["p2"].health
    assert dealt > 0
    assert fight.meters["p1"].fill == {Z: 0, X: 2 * dealt}


def test_a_blocked_hit_fills_nothing():
    fight = fight_of()
    fight.fighters["p2"].basis = X                  # a green jab bounces off purple
    events = until(fight, "block", {"p1": A})
    assert any(e.kind == "block" for e in events)
    assert fight.meters["p1"].fill == {Z: 0, X: 0} and fight.meters["p2"].fill == {Z: 0, X: 0}


def test_filling_a_half_and_the_bar_are_events():
    fight = fight_of()
    fight.meters["p1"].fill = {Z: FULL - 2, X: FULL}
    events = until(fight, "hit", {"p1": A})
    kinds = [(e.kind, e.player) for e in events if e.kind.startswith("super_")]
    assert kinds == [("super_half", "p1"), ("super_full", "p1")]
    assert fight.meters["p1"].full


def test_a_fight_can_be_handed_its_meters():
    meters = {"p1": Meter(), "p2": Meter()}
    meters["p1"].fill[Z] = 12
    fight = Fight({"p1": ROBERT, "p2": ROBERT}, seed=1, meters=meters)
    assert fight.meters is meters and fight.meters["p1"].fill[Z] == 12


# --- firing ------------------------------------------------------------------------------------

from types import MappingProxyType  # noqa: E402

from brawl_ket.basis import BOTH  # noqa: E402
from brawl_ket.config import SUPER_FREEZE  # noqa: E402
from brawl_ket.moves import ALICE_BOB, MID, Box, Move  # noqa: E402

AB = FighterInput(a=True, b=True)
# a plain test super: a big strike in front, both colours
TEST_SUPER = Move("TEST SUPER", 4, 4, 10, Box(14, 40, 60, 60), BOTH, MID,
                  damage=25, hitstun=30, knockback=3.0, knockdown=True, kind="super")
SUPER_ROBERT = replace(ROBERT, extra=MappingProxyType({"super": TEST_SUPER}))


def full(fight: Fight, key: str = "p1") -> None:
    fight.meters[key].fill = {Z: FULL, X: FULL}


def kinds(events: list) -> list[str]:
    return [e.kind for e in events]


def test_a_and_b_together_with_a_full_bar_fire_it_and_empty_the_bar():
    fight = fight_of(SUPER_ROBERT)
    full(fight)
    events = fight.step({"p1": AB})
    assert "super" in kinds(events) and fight.fighters["p1"].slot == "super"
    assert not fight.meters["p1"].full and fight.meters["p1"].fill == {Z: 0, X: 0}
    assert fight.freeze == SUPER_FREEZE and fight.supers == ["p1"]


def test_the_freeze_stops_everything_for_its_call():
    fight = fight_of(SUPER_ROBERT)
    full(fight)
    fight.fighters["p2"].vx = 2.0
    fight.step({"p1": AB})
    clock, frame, x = fight.frames_left, fight.fighters["p1"].frame, fight.fighters["p2"].x
    for _ in range(SUPER_FREEZE - 1):
        assert fight.step({"p2": FighterInput(dx=1)}) == []
    assert (fight.frames_left, fight.fighters["p1"].frame, fight.fighters["p2"].x) == (clock, frame, x)
    fight.step({})                                  # the last frame of the call
    assert fight.freeze == 0 and fight.supers == []
    fight.step({})
    assert fight.fighters["p1"].frame == frame + 1  # and on it goes


def test_a_then_b_two_frames_later_still_fires_but_three_is_a_jab():
    fight = fight_of(SUPER_ROBERT)
    full(fight)
    fight.step({"p1": A})
    fight.step({})
    assert "super" in kinds(fight.step({"p1": B}))
    fight = fight_of(SUPER_ROBERT)
    full(fight)
    fight.step({"p1": A})
    fight.step({})
    events = fight.step({})                         # a lone A waited 2 frames: now it's a jab
    assert fight.fighters["p1"].slot == "stand.A" and "super" not in kinds(events)


def test_without_a_full_bar_a_and_b_are_as_ever():
    fight = fight_of(SUPER_ROBERT)
    fight.step({"p1": A})
    assert fight.fighters["p1"].slot == "stand.A"   # at once, no waiting
    fight = fight_of(SUPER_ROBERT)
    events = fight.step({"p1": AB})
    assert "super" not in kinds(events) and fight.fighters["p1"].slot != "super"


def test_a_fighter_with_no_super_never_waits():
    fight = fight_of()
    full(fight)
    fight.step({"p1": A})
    assert fight.fighters["p1"].slot == "stand.A"


def test_not_from_the_air():
    fight = fight_of(SUPER_ROBERT)
    full(fight)
    fight.step({"p1": FighterInput(up=True)})
    events = fight.step({"p1": AB})
    assert "super" not in kinds(events) and fight.meters["p1"].full


def test_it_hurts_either_colour_and_fills_no_bar():
    for rival_basis in (Z, X):
        fight = fight_of(SUPER_ROBERT)
        full(fight)
        fight.fighters["p2"].basis = rival_basis
        until(fight, "hit", {"p1": AB}, frames=SUPER_FREEZE + 20)
        assert fight.fighters["p2"].health == ROBERT.health - 25
        assert fight.meters["p1"].fill == {Z: 0, X: 0} and fight.meters["p2"].fill == {Z: 0, X: 0}


def test_a_ko_by_a_super_is_marked():
    fight = fight_of(SUPER_ROBERT)
    full(fight)
    fight.fighters["p2"].health = 20
    until(fight, "ko", {"p1": AB}, frames=SUPER_FREEZE + 20)
    assert fight.over and fight.super_ko


def test_both_on_the_same_frame_freeze_one_after_the_other():
    fight = fight_of(SUPER_ROBERT, SUPER_ROBERT, gap=200.0)
    full(fight, "p1")
    full(fight, "p2")
    fight.step({"p1": AB, "p2": AB})
    assert fight.supers == ["p1", "p2"]
    for _ in range(SUPER_FREEZE):
        fight.step({})
    assert fight.supers == ["p2"] and fight.freeze == SUPER_FREEZE
    for _ in range(SUPER_FREEZE):
        fight.step({})
    assert fight.supers == [] and fight.freeze == 0


def test_bob_never_echoes_a_supers_a_and_b():
    pair = replace(ALICE_BOB, extra=MappingProxyType({**ALICE_BOB.extra, "super": TEST_SUPER}))
    fight = fight_of(pair, ROBERT, gap=300.0)
    full(fight)
    fight.step({"p1": A})
    fight.step({"p1": B})                           # A, then B a frame later
    assert fight.fighters["p1"].slot == "super"
    bob = fight.echoes["p1"]
    for _ in range(SUPER_FREEZE + 30):
        fight.step({})
        assert bob.action != "attack"


# --- DOS: BLUE SCREEN OF DEATH -------------------------------------------------------------------

from brawl_ket.config import CRASH_HOLD, CRASH_LEAP, CRASH_REACH  # noqa: E402
from brawl_ket.moves import BLUE_SCREEN, BSOD_HOLD, ERWIN  # noqa: E402

STARTUP = BLUE_SCREEN.startup


def bsod(rival=ROBERT, gap: float = 150.0) -> Fight:
    """DOS with a full bar fires; the call is skipped and the startup run."""
    fight = fight_of(DOS, rival, gap)
    full(fight)
    fight.step({"p1": AB})
    for _ in range(SUPER_FREEZE):
        fight.step({})
    return fight


def run(fight: Fight, frames: int, inp: dict | None = None) -> list:
    events = []
    for _ in range(frames):
        events += fight.step(inp or {})
    return events


def test_dos_has_it_and_it_is_both_colours():
    assert DOS.extra["super"] is BLUE_SCREEN
    assert BLUE_SCREEN.kind == "super" and BLUE_SCREEN.colour == BOTH and BLUE_SCREEN.name == "BLUE SCREEN OF DEATH"
    assert BLUE_SCREEN.crash is BSOD_HOLD and BSOD_HOLD.hold and BSOD_HOLD.damage == 0
    assert BLUE_SCREEN.seek == CRASH_LEAP and BSOD_HOLD.hitstun == CRASH_HOLD


def test_it_freezes_a_rival_on_the_ground_in_reach():
    fight = bsod(gap=150.0)
    events = run(fight, STARTUP)
    rival = fight.fighters["p2"]
    crash = [e for e in events if e.kind == "crash"]
    assert crash and crash[0].player == "p2"
    assert rival.action == "hitstun" and rival.glitch > 0 and rival.vx == 0.0
    assert rival.health == ROBERT.health                # the freeze itself does no damage


def test_then_he_comes_down_on_them_for_25_whatever_their_colour():
    for colour in (Z, X):
        fight = bsod(gap=150.0)
        fight.fighters["p2"].basis = colour
        events = run(fight, STARTUP + CRASH_LEAP + 20)     # (the hit's hitstop holds the landing back)
        rival = fight.fighters["p2"]
        assert rival.health == ROBERT.health - 25 and rival.action == "knockdown"
        assert rival.glitch == 0
        assert any(e.kind == "bsod_land" for e in events)


def test_he_lands_about_crash_leap_frames_after_the_crash():
    fight = bsod(gap=CRASH_REACH + 20)                  # nobody frozen, so no hit and no hitstop
    dos = fight.fighters["p1"]
    run(fight, STARTUP)
    landed = None
    for n in range(1, CRASH_LEAP + 10):
        if any(e.kind == "bsod_land" for e in fight.step({})):
            landed = n
            break
    assert landed is not None and CRASH_LEAP - 3 <= landed <= CRASH_LEAP + 1
    assert dos.phase == "recovery"


def test_a_rival_in_the_air_is_not_frozen_and_he_drops_where_he_stands():
    fight = fight_of(DOS, ROBERT, 150.0)
    full(fight)
    fight.step({"p1": AB})
    for _ in range(SUPER_FREEZE):
        fight.step({})
    fight.step({"p2": FighterInput(up=True)})           # up in its startup
    events = run(fight, STARTUP - 1)
    assert [e.player for e in events if e.kind == "crash"] == [None]
    x = fight.fighters["p1"].x
    run(fight, CRASH_LEAP + 4)
    assert fight.fighters["p1"].x == x


def test_a_rival_out_of_reach_is_not_frozen():
    fight = bsod(gap=CRASH_REACH + 20)
    events = run(fight, STARTUP + CRASH_LEAP + 4)
    assert [e.player for e in events if e.kind == "crash"] == [None]
    assert fight.fighters["p2"].health == ROBERT.health


def test_the_box_dodges_it():
    fight = fight_of(DOS, ERWIN, 150.0)
    fight.fighters["p2"].action = "boxed"
    fight.fighters["p2"].boxes = (450.0, 450.0)
    full(fight)
    fight.step({"p1": AB})
    for _ in range(SUPER_FREEZE):
        fight.step({})
    events = run(fight, STARTUP)
    assert [e.player for e in events if e.kind == "crash"] == [None]


def test_both_of_alice_and_bob_in_reach_are_frozen():
    fight = bsod(ALICE_BOB, gap=120.0)
    events = run(fight, STARTUP)
    assert [e.player for e in events if e.kind == "crash"] == ["p2", "p2"]
    assert fight.echoes["p2"].glitch > 0 and fight.fighters["p2"].glitch > 0


def test_the_glitch_runs_down_a_frame_at_a_time_and_a_hit_ends_it():
    fight = fight_of()
    rival = fight.fighters["p2"]
    rival.glitch = 3
    run(fight, 3)
    assert rival.glitch == 0
    rival.glitch = 30
    until(fight, "hit", {"p1": A})
    assert rival.glitch == 0
