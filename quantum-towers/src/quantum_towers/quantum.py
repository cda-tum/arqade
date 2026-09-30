"""Pure 1-qubit state functions. No pygame, no I/O, no numpy.

Five actions a player can take: the Pauli gates (X, Y, Z), Hadamard (H), and
reset (not unitary -- forces the state back to |0>, modeled as a same-shape
action so it participates uniformly in gate-press counting and the search
in search.py).

Global phase MATTERS here -- states are compared with `states_equal`, exact
complex equality (within tolerance), not the usual physics convention of
identifying states that differ only by an overall phase. This is a
deliberate departure from real quantum mechanics (where global phase truly
is unobservable) made for gameplay reasons: under the physics-standard
equivalence, Y is entirely redundant (Y = iXZ up to global phase, so any
X/Z combo always substitutes for it), and Z does nothing distinguishable to
|1> (Z|1> = -|1>, identified with |1>). Treating raw state vectors as the
actual game state fixes both: X, Z, and H are real-valued matrices, so
starting from the real |0>, only Y can ever introduce an imaginary
component at all -- without Y, at most half the reachable states (those
with real overall phase) are within reach. Z now genuinely changes |1>
(-> -|1>, a different target) while still exactly fixing |0> (Z|0> = |0>,
unchanged, since |0>'s second amplitude is already 0).

Starting from |0>, X/Y/Z/H/RESET reach exactly 16 states: each of the 4
"real" cardinal directions (|0>, |1>, |+>, |->) times each of the 4 clean
phases (1, -1, i, -i) -- see notation.py for how these render.

`apply_t` (the pi/8 phase gate) is still defined and tested here since it's
a real, useful single-qubit gate, but it's deliberately left out of
`ACTIONS` -- it pushes a state to an arbitrary phase angle outside that
clean 16-state set, which played badly as a target players had to "guess"
their way back to. The S gate was tried and removed for a related reason:
it made all 6 Bloch-sphere *directions* reachable, but did nothing to fix
Y's redundancy (Y = iXZ regardless of which other Clifford phase gates
exist) -- exact state comparison is the fix that actually works, and it
doesn't need S to make Y matter.
"""

from __future__ import annotations

import cmath
import math
from typing import Callable, NamedTuple

_INV_SQRT2 = 1 / math.sqrt(2)
_ZERO_AMPLITUDE_EPSILON = 1e-9
_T_PHASE = cmath.exp(1j * math.pi / 4)


class State(NamedTuple):
    a0: complex
    a1: complex


def zero_state() -> State:
    return State(1 + 0j, 0 + 0j)


def apply_x(state: State) -> State:
    return State(state.a1, state.a0)


def apply_y(state: State) -> State:
    return State(-1j * state.a1, 1j * state.a0)


def apply_z(state: State) -> State:
    return State(state.a0, -state.a1)


def apply_h(state: State) -> State:
    return State(
        _INV_SQRT2 * (state.a0 + state.a1),
        _INV_SQRT2 * (state.a0 - state.a1),
    )


def apply_t(state: State) -> State:
    return State(state.a0, state.a1 * _T_PHASE)


def apply_reset(state: State) -> State:
    return zero_state()


def normalize_global_phase(state: State) -> State:
    """Rotate global phase so a0 is non-negative real (a1 if a0 is ~0).

    Not used for gameplay comparisons any more (see module docstring) --
    kept because it's still the right tool for asking "are these the same
    *physical* state", which some tests and the general notation fallback
    still legitimately want.
    """
    reference = state.a0 if abs(state.a0) > _ZERO_AMPLITUDE_EPSILON else state.a1
    if abs(reference) <= _ZERO_AMPLITUDE_EPSILON:
        return state
    phase_factor = reference / abs(reference)
    return State(state.a0 / phase_factor, state.a1 / phase_factor)


def states_equal_up_to_global_phase(a: State, b: State, tol: float = 1e-6) -> bool:
    na = normalize_global_phase(a)
    nb = normalize_global_phase(b)
    return abs(na.a0 - nb.a0) <= tol and abs(na.a1 - nb.a1) <= tol


def states_equal(a: State, b: State, tol: float = 1e-6) -> bool:
    """Exact state equality (within numerical tolerance) -- global phase
    included. This is what gameplay actually uses: target-matching, the BFS
    search, and target generation all compare states this way, so a global
    phase difference is a genuinely different target, not the same one."""
    return abs(a.a0 - b.a0) <= tol and abs(a.a1 - b.a1) <= tol


# The five actions a player can take, in a fixed order (used by search.py's
# BFS and by anything that needs to enumerate/display them consistently).
# T is deliberately excluded -- see the module docstring.
ACTIONS: dict[str, Callable[[State], State]] = {
    "X": apply_x,
    "Y": apply_y,
    "Z": apply_z,
    "H": apply_h,
    "RESET": apply_reset,
}
