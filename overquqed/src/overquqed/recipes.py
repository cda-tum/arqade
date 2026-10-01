"""Orderable target states, their tier and one hint circuit each.

The ticket always shows `hint` as a mini circuit; *any* circuit that makes
the state is accepted (serving checks fidelity, not the gate sequence).
Hint ops use QState.ops notation: ("H", q), ("CNOT", control, target).
"""

from __future__ import annotations

from dataclasses import dataclass

from overquqed.quantum import NAMED_STATES, QState, Vector, merge


@dataclass(frozen=True)
class Recipe:
    key: str  # also the ket token, e.g. "Phi+"
    n: int
    tier: int
    hint: tuple[tuple, ...]
    concept: str

    @property
    def target(self) -> Vector:
        return NAMED_STATES[self.key]


RECIPES: dict[str, Recipe] = {
    r.key: r
    for r in (
        Recipe("0", 1, 1, (), "Qubits start in |0>"),
        Recipe("1", 1, 1, (("X", 0),), "Bit flip"),
        Recipe("+", 1, 1, (("H", 0),), "Superposition"),
        Recipe("-", 1, 2, (("X", 0), ("H", 0)), "Gate order matters"),
        Recipe("Phi+", 2, 2, (("H", 0), ("CNOT", 0, 1)), "Entanglement"),
        Recipe("Phi-", 2, 3, (("H", 0), ("CNOT", 0, 1), ("Z", 0)), "Phase on a Bell pair"),
        Recipe("Psi+", 2, 3, (("H", 0), ("CNOT", 0, 1), ("X", 0)), "Bell basis"),
        Recipe("GHZ", 3, 3, (("H", 0), ("CNOT", 0, 1), ("CNOT", 0, 2)), "Cat state"),
        Recipe("Psi-", 2, 3, (("H", 0), ("CNOT", 0, 1), ("X", 0), ("Z", 0)), "The singlet"),
    )
}

TIER_POINTS = {1: 20, 2: 40, 3: 60}


def run_circuit(ops: tuple[tuple, ...], n: int) -> QState:
    """Noise-free: start from |0...0> and apply ops (for tests and hints)."""
    state = QState.fresh()
    for _ in range(n - 1):
        state = merge(state, QState.fresh())
    for op in ops:
        if op[0] == "CNOT":
            state.cnot(op[1], op[2])
        else:
            state.apply(op[0], op[1])
    return state
