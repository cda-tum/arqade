"""The measurement basis each fighter is in, and which attacks change its state.

Exact physics, one qubit:
- Z basis (|0>, |1>): an X flips |0> and |1>; a Z leaves both alone (up to phase).
- X basis (|+>, |->): a Z flips |+> and |->; an X leaves both alone (up to phase).
- Y = iXZ flips the states of both bases.
- H maps the Z basis onto the X basis and back.
tests/test_basis.py checks this against explicit 2x2 matrices.

The game draws a basis as a colour, and an attack in the colour of the basis it
changes: the Z basis and X errors are green, the X basis and Z errors are purple,
and a Y is both. So the one rule a player reads is: colour must match to hurt.
"""

from __future__ import annotations

Z_BASIS, X_BASIS = "Z", "X"         # green, purple
X, Z, Y = "X", "Z", "Y"
GREEN, PURPLE, BOTH = "green", "purple", "both"
OWN, OPPOSITE = "own", "opposite"   # colour rules relative to the attacker's own basis

BASIS_COLOUR = {Z_BASIS: GREEN, X_BASIS: PURPLE}
_FLIPS = {X: {Z_BASIS}, Z: {X_BASIS}, Y: {Z_BASIS, X_BASIS}}   # which bases an error changes
_ERROR_OF = {GREEN: X, PURPLE: Z, BOTH: Y}


def _check_basis(b: str) -> None:
    if b not in (Z_BASIS, X_BASIS):
        raise ValueError(f"unknown basis: {b}")


def hurts(error: str, b: str) -> bool:
    """Does the error change a fighter's state in basis b?"""
    if error not in _FLIPS:
        raise ValueError(f"unknown error: {error}")
    _check_basis(b)
    return b in _FLIPS[error]


def hadamard(b: str) -> str:
    _check_basis(b)
    return X_BASIS if b == Z_BASIS else Z_BASIS


def colour_of(error: str) -> str:
    return {X: GREEN, Z: PURPLE, Y: BOTH}[error]


def error_for(rule: str, attacker_basis: str) -> str:
    """The error an attack deals, from its colour rule and its attacker's basis at the
    moment of the hit: OWN is the attacker's colour, OPPOSITE the other one."""
    _check_basis(attacker_basis)
    if rule == OWN:
        return _ERROR_OF[BASIS_COLOUR[attacker_basis]]
    if rule == OPPOSITE:
        return _ERROR_OF[BASIS_COLOUR[hadamard(attacker_basis)]]
    if rule in _ERROR_OF:
        return _ERROR_OF[rule]
    raise ValueError(f"unknown colour rule: {rule}")
