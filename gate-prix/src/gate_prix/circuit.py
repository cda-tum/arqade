"""The race's quantum side: single-qubit gates, exact simulation, targets and scoring.

Pure Python, no pygame. A state is the pair of amplitudes (a, b) of a|0> + b|1>.
"""

from __future__ import annotations

import math
import random

GATES = ("H", "X", "Y", "Z")

_S = 1 / math.sqrt(2)

State = tuple[complex, complex]
ZERO: State = (1 + 0j, 0j)


def apply(state: State, gate: str) -> State:
    """Apply one gate to a state, with the exact 2x2 matrix."""
    a, b = state
    if gate == "H":
        return ((a + b) * _S, (a - b) * _S)
    if gate == "X":
        return (b, a)
    if gate == "Y":
        return (-1j * b, 1j * a)
    if gate == "Z":
        return (a, -b)
    raise ValueError(f"unknown gate {gate!r}")


def run(gates: list[str | None]) -> State:
    """The state after the gates, from |0>. None (an empty slot) is the identity."""
    state = ZERO
    for gate in gates:
        if gate is not None:
            state = apply(state, gate)
    return state


def bloch(state: State) -> tuple[float, float, float]:
    """The Bloch vector (x, y, z) of a state, which is independent of its global phase."""
    a, b = state
    cross = a.conjugate() * b
    return (2 * cross.real, 2 * cross.imag, abs(a) ** 2 - abs(b) ** 2)


def random_target(rng: random.Random, n: int) -> list[str]:
    """n random gates, never the same gate twice in a row (so no slot is free)."""
    target: list[str] = []
    for _ in range(n):
        options = [g for g in GATES if not target or g != target[-1]]
        target.append(rng.choice(options))
    return target


def hamming(mine: list[str | None], target: list[str], upto: int) -> int:
    """How many of the first `upto` slots differ from the target. Empty counts as different."""
    return sum(
        1 for i in range(upto) if i >= len(mine) or mine[i] is None or mine[i] != target[i]
    )


class Circuit:
    """One car's circuit: the target, the gates it took so far, and its streak.

    Slots are filled strictly in order, one per gate row. `results[i]` is None until slot i
    is filled, then True (right) or False (wrong or empty).
    """

    def __init__(self, target: list[str]) -> None:
        self.target = list(target)
        self.slots: list[str | None] = [None] * len(target)
        self.results: list[bool | None] = [None] * len(target)
        self.streak = 0
        self._filled = 0

    @property
    def filled(self) -> int:
        """How many slots are already decided (taken or missed)."""
        return self._filled

    def take(self, slot: int, gate: str | None) -> bool:
        """Fill the next slot with a gate (None: the row was missed). True when it is right."""
        if slot != self._filled or not 0 <= slot < len(self.target):
            raise ValueError(f"slot {slot} cannot be filled now (next is {self._filled})")
        right = gate is not None and gate == self.target[slot]
        self.slots[slot] = gate
        self.results[slot] = right
        self._filled += 1
        self.streak = self.streak + 1 if right else 0
        return right

    def qec(self) -> int | None:
        """Error correction: the most recent wrong or empty slot becomes right.

        Returns its index, or None when no filled slot is wrong. The streak is untouched.
        """
        for slot in range(self._filled - 1, -1, -1):
            if not self.results[slot]:
                self.slots[slot] = self.target[slot]
                self.results[slot] = True
                return slot
        return None
