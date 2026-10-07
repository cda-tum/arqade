"""basis.py, checked against explicit 2x2 matrices on the four basis states (not against
the game's own tables)."""

from __future__ import annotations

import math

import pytest

from brawl_ket import basis
from brawl_ket.basis import BOTH, GREEN, OPPOSITE, OWN, PURPLE, X, X_BASIS, Y, Z, Z_BASIS

R = 1 / math.sqrt(2)
STATES = {   # basis -> its two states, as (amplitude of |0>, amplitude of |1>)
    Z_BASIS: [(1, 0), (0, 1)],              # |0>, |1>
    X_BASIS: [(R, R), (R, -R)],             # |+>, |->
}
GATES = {
    X: ((0, 1), (1, 0)),
    Z: ((1, 0), (0, -1)),
    Y: ((0, -1j), (1j, 0)),                 # Y = iXZ
}
H = ((R, R), (R, -R))


def apply(m, v):
    return (m[0][0] * v[0] + m[0][1] * v[1], m[1][0] * v[0] + m[1][1] * v[1])


def same_state(u, v) -> bool:
    """Equal up to a global phase: |<u|v>| = 1."""
    overlap = sum(complex(a).conjugate() * b for a, b in zip(u, v))
    return abs(abs(overlap) - 1) < 1e-9


def changes_basis(error, b) -> bool:
    """The error changes every state of the basis (and leaves none alone up to phase)."""
    changed = [not same_state(s, apply(GATES[error], s)) for s in STATES[b]]
    assert all(changed) or not any(changed)     # a Pauli acts alike on both states of a basis
    return all(changed)


@pytest.mark.parametrize("error", [X, Z, Y])
@pytest.mark.parametrize("b", [Z_BASIS, X_BASIS])
def test_hurts_means_the_attack_changes_the_state(error, b):
    assert basis.hurts(error, b) == changes_basis(error, b)


def test_the_spec_lines():
    zero, one = STATES[Z_BASIS]
    plus, minus = STATES[X_BASIS]
    assert same_state(apply(GATES[X], zero), one)           # X on |0> gives |1>
    assert same_state(apply(GATES[X], plus), plus)          # X on |+> leaves |+>
    assert same_state(apply(GATES[Z], plus), minus)         # Z on |+> gives |->
    assert same_state(apply(GATES[Z], zero), zero)          # Z on |0> leaves |0>
    assert basis.hurts(Y, Z_BASIS) and basis.hurts(Y, X_BASIS)


def test_h_swaps_the_bases():
    for b, other in ((Z_BASIS, X_BASIS), (X_BASIS, Z_BASIS)):
        mapped = [apply(H, s) for s in STATES[b]]
        assert all(any(same_state(m, t) for t in STATES[other]) for m in mapped)
        assert basis.hadamard(b) == other


def test_colours():
    assert basis.colour_of(X) == GREEN and basis.colour_of(Z) == PURPLE and basis.colour_of(Y) == BOTH
    assert basis.BASIS_COLOUR == {Z_BASIS: GREEN, X_BASIS: PURPLE}
    # a green attack hurts a green fighter, a purple one a purple fighter
    for b in (Z_BASIS, X_BASIS):
        own = basis.error_for(OWN, b)
        assert basis.colour_of(own) == basis.BASIS_COLOUR[b] and basis.hurts(own, b)
        opposite = basis.error_for(OPPOSITE, b)
        assert basis.colour_of(opposite) != basis.BASIS_COLOUR[b] and not basis.hurts(opposite, b)
    assert basis.error_for(GREEN, X_BASIS) == X and basis.error_for(PURPLE, Z_BASIS) == Z
    assert basis.error_for(BOTH, Z_BASIS) == Y


def test_bad_arguments_are_rejected():
    with pytest.raises(ValueError):
        basis.hurts("W", Z_BASIS)
    with pytest.raises(ValueError):
        basis.hurts(X, "Q")
    with pytest.raises(ValueError):
        basis.error_for("red", Z_BASIS)
