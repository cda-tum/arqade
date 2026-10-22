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
