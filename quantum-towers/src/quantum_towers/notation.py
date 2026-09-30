"""Render a 1-qubit State as ket notation, using only glyphs confirmed
present in the bundled pixel font -- Unicode ket brackets (the U+27E8/E9
characters) turned out to be missing from that font (render as an invisible
box), so this uses the standard ASCII "|0>" convention instead.

Global phase is part of the game state now (see quantum.py's module
docstring for why), so it's part of what gets rendered too: a state is
matched against each of the 6 Bloch-sphere cardinal directions at each of
the 4 clean phases (1, -1, i, -i) reachable with the current gate set,
rendering as e.g. "|1>", "-|1>", "i|1>", "-i|1>". Everything else
(currently unreachable in normal play -- only possible via the excluded T
gate) renders in a general magnitude+angle fallback form.
"""

from __future__ import annotations

import cmath
import math

from quantum_towers.quantum import State, normalize_global_phase, states_equal

_INV_SQRT2 = 1 / math.sqrt(2)

_SYMBOLS: dict[str, State] = {
    "|0>": State(1 + 0j, 0 + 0j),
    "|1>": State(0 + 0j, 1 + 0j),
    "|+>": State(_INV_SQRT2 + 0j, _INV_SQRT2 + 0j),
    "|->": State(_INV_SQRT2 + 0j, -_INV_SQRT2 + 0j),
    "|+i>": State(_INV_SQRT2 + 0j, _INV_SQRT2 * 1j),
    "|-i>": State(_INV_SQRT2 + 0j, -_INV_SQRT2 * 1j),
}

# The 4 clean global phases reachable with the current gate set -- only Y
# ever introduces an imaginary phase at all, so these are the only ones that
# come up. Order matters only for iteration; each (symbol, phase) pair is
# mutually exclusive so there's no ambiguity in which one matches.
_PHASE_PREFIXES: dict[complex, str] = {
    1 + 0j: "",
    -1 + 0j: "-",
    1j: "i",
    -1j: "-i",
}


def _match_symbol(state: State) -> str | None:
    for symbol, reference in _SYMBOLS.items():
        for phase, prefix in _PHASE_PREFIXES.items():
            phased = State(reference.a0 * phase, reference.a1 * phase)
            if states_equal(state, phased):
                return f"{prefix}{symbol}"
    return None


def _format_coefficient(magnitude: float) -> str:
    """1/sqrt(2) is by far the most common non-trivial magnitude this game's
    reachable states ever have -- show it exactly ("1/√2"), not as a rounded
    decimal ("0.71"), matching how it'd actually be written by hand. A
    coefficient of 1 is omitted entirely; anything else genuinely irrational
    (only possible via H after an odd T-phase) falls back to 2-decimal form.
    """
    if abs(magnitude - 1.0) < 1e-6:
        return ""
    if abs(magnitude - _INV_SQRT2) < 1e-6:
        return "1/√2"
    return f"{magnitude:.2f}"


def _render_general(normalized: State) -> str:
    """Fallback for a state that isn't one of the 16 clean (direction,
    phase) combinations above -- currently unreachable in normal play (only
    the excluded T gate can produce one), kept as a defensive fallback
    rather than ripped out. Takes an already phase-normalized state (a0
    real and non-negative), unlike `_match_symbol` which works on the raw,
    non-normalized state."""
    a0, a1 = normalized
    left = f"{_format_coefficient(a0.real)}|0>"

    magnitude = abs(a1)
    if magnitude < 1e-9:
        return left

    angle_deg = round(math.degrees(cmath.phase(a1))) % 360
    right = f"{_format_coefficient(magnitude)}|1>"
    if angle_deg != 0:
        right += f"@{angle_deg}°"
    return f"{left} + {right}"


def render_state(state: State) -> str:
    return _match_symbol(state) or _render_general(normalize_global_phase(state))
