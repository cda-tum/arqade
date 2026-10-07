"""The rules of CLIMB! (Qlimbers) and DROP! (Gate Drop)
that the contract tests can't see: exactly one right answer, never a free
win at the start, and the source games' own gate semantics."""

import random

import pytest

from planck_time.microgames import PlayerInput
from planck_time.microgames.climb import GATES as CLIMB_GATES
from planck_time.microgames.climb import PLAIN, Climb, ket, same, same_direction
from planck_time.microgames.drop import INVERSE, Drop, sandwich

DT = 1 / 60
SEEDS = range(200)


def rounds(cls, levels=(0, 1, 3, 6), appearances=(0, 1, 3)):
    for seed in SEEDS:
        for level in levels:
            for appearance in appearances:
                yield cls.spawn(seed, level, cls.duration_for(level), appearance)


# --- CLIMB! -------------------------------------------------------------------------------

def test_climb_exactly_one_card_reaches_the_target_and_the_target_is_new():
    for g in rounds(Climb):
        hits = [k for k in g.cards if same(CLIMB_GATES[k](g.start), g.target)]
        assert hits == [g.right]
        assert len(set(g.cards)) == 3
        assert not same(g.start, g.target)


def test_climb_what_is_shown_is_what_is_compared():
    """Every ket is drawn with its phase, so two states with the same label
    are the same state, and two different states never share a label."""
    for g in rounds(Climb):
        for k in g.cards:
            after = CLIMB_GATES[k](g.start)
            assert (ket(after) == ket(g.target)) == same(after, g.target)


def test_climb_starts_phase_free_and_with_no_near_miss_decoys():
    for g in rounds(Climb, levels=(0, 1), appearances=(0,)):
        assert not g.phased
        assert ket(g.start) in PLAIN and ket(g.target) in PLAIN
        for k in g.cards:
            if k != g.right:
                assert not same_direction(CLIMB_GATES[k](g.start), g.target)


def test_climb_later_the_phase_matters():
    phase_only = sum(
        same_direction(g.start, g.target) or any(
            k != g.right and same_direction(CLIMB_GATES[k](g.start), g.target) for k in g.cards)
        for g in rounds(Climb, levels=(3,), appearances=(1,)))
    assert phase_only > 20  # Z on |1> and friends: decoys that only miss by a phase


def test_climb_a_card_applied_twice_undoes_itself():
    for g in rounds(Climb, levels=(0, 3), appearances=(0, 1)):
        for k in g.cards:
            assert same(CLIMB_GATES[k](CLIMB_GATES[k](g.start)), g.start)


def push(g, inp, frames=1):
    for _ in range(frames):
        g.update(DT, inp)
        g.update(DT, PlayerInput())


def test_climb_pushing_up_on_the_wrong_state_stuns_and_two_stuns_still_fit():
    g = Climb(4, 0, 5.0)
    while g.t < g.ready:
        g.update(DT, PlayerInput())
    push(g, PlayerInput(step=(0, -1), stick=(0, -1)))
    assert g.stunned and g.result is None
    cursor = g.cursor
    push(g, PlayerInput(step=(1, 0), a=True))
    assert g.cursor == cursor and same(g.state, g.start)  # locked out while stunned
    # a second stun, and then the bot still has time to win
    while g.stunned:
        g.update(DT, PlayerInput())
    push(g, PlayerInput(step=(0, -1), stick=(0, -1)))
    assert g.stunned
    while g.t < g.duration and g.result is None:
        g.update(DT, g.bot())
    assert g.result is True


# --- DROP! --------------------------------------------------------------------------------

def test_drop_exactly_one_wire_is_right_and_the_pill_never_starts_over_it():
    for g in rounds(Drop):
        tops = [col[-1] for col in g.columns]
        assert [c for c, top in enumerate(tops) if top == INVERSE[g.pill]] == [g.right]
        assert g.col != g.right


def test_drop_the_stacks_are_as_gate_drop_would_leave_them():
    for g in rounds(Drop):
        for c, col in enumerate(g.columns):
            for i in range(1, len(col)):
                assert INVERSE[col[i - 1]] != col[i]
                assert not (i >= 2 and sandwich(col[i - 2], col[i - 1], col[i]))
            if c != g.right:  # no wrong wire folds the pill into a sandwich either
                assert not sandwich(col[-2] if len(col) > 1 else None, col[-1], g.pill)
            if g.bugs[c]:
                assert col[0] in "XYZ" and len(col) > 1
            assert g.floor(c) >= 0


def test_drop_t_gates_come_on_later_appearances_with_a_t_decoy():
    assert not any(k in ("T", "Td") for g in rounds(Drop, appearances=(0,)) for col in g.columns for k in col + [g.pill])
    t_rounds = [g for g in rounds(Drop, appearances=(1,)) if g.t_round]
    assert t_rounds
    for g in t_rounds:
        assert g.pill in ("T", "Td")
        assert any(col[-1] == g.pill for col in g.columns)  # T on T looks right and is not


def test_drop_landing_anywhere_else_fails():
    g = Drop(3, 0, 5.0)
    while g.result is None:
        g.update(DT, PlayerInput())
    assert g.result is False and g.landed_on != g.right


# --- both ---------------------------------------------------------------------------------

def snapshot(g):
    if isinstance(g, Climb):
        return g.cursor, ket(g.state), g.stunned
    return g.col, g.row, g.fast


@pytest.mark.parametrize("cls", (Climb, Drop), ids=lambda c: c.__name__)
def test_nothing_counts_for_the_first_six_tenths_of_a_second(cls):
    for seed in range(20):
        rng = random.Random(seed)
        g = cls(seed, 0, cls.duration_for(0))
        before = snapshot(g)
        while g.t + DT < 0.6:
            g.update(DT, PlayerInput(stick=(rng.uniform(-1, 1), rng.uniform(-1, 1)),
                                     step=(rng.choice((-1, 0, 1)), rng.choice((-1, 0, 1))), a=True, a_held=True))
        assert g.result is None and snapshot(g) == before
