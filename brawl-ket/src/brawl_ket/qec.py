"""The repetition code each fighter carries.

Exact physics: a distance-d repetition code corrects t = (d - 1) // 2 errors
of one kind: the bit-flip code (|0..0>, |1..1>) corrects X errors and cannot
see Z; the phase-flip code (|+..+>, |-..->) corrects Z and cannot see X.
A transversal H maps one code onto the other. Y = iXZ always has a part the
code can't see, so it is always a logical error.

Game rules simplify the physics:
- Errors always hit distinct qubits (the lowest unflipped one).
- A logical error re-encodes the code (clears all lights).
- The logical error is reported as soon as more than t errors are pending,
  rather than at the next majority-vote cycle.
"""

from __future__ import annotations

X, Z, Y = "X", "Z", "Y"
BIT, PHASE = "bit", "phase"
FLIPPED, LOGICAL = "flipped", "logical"
_CORRECTS = {BIT: X, PHASE: Z}


class Code:
    def __init__(self, distance: int, cycle_frames: int) -> None:
        if distance % 2 == 0 or distance < 3:
            raise ValueError(f"distance must be odd and >= 3, not {distance}")
        if cycle_frames < 1:
            raise ValueError(f"cycle_frames must be >= 1, not {cycle_frames}")
        self.distance = distance
        self.cycle_frames = cycle_frames
        self.basis = BIT
        self.flipped: set[int] = set()
        self.timer = 0

    @property
    def t(self) -> int:
        return (self.distance - 1) // 2

    @property
    def progress(self) -> float:
        return self.timer / self.cycle_frames

    def corrects(self, error: str) -> bool:
        if error not in (X, Y, Z):
            raise ValueError(f"unknown error type: {error}")
        return _CORRECTS[self.basis] == error

    def hit(self, error: str) -> str:
        if error not in (X, Y, Z):
            raise ValueError(f"unknown error type: {error}")
        if not self.corrects(error):
            return self.logical_error()
        # GAME RULE: errors always hit distinct qubits (the lowest unflipped one)
        self.flipped.add(min(set(range(self.distance)) - self.flipped))
        # GAME RULE: report logical error as soon as more than t errors are pending
        if len(self.flipped) > self.t:
            return self.logical_error()
        return FLIPPED

    def logical_error(self) -> str:
        self.flipped.clear()  # GAME RULE: the code is re-encoded
        return LOGICAL

    def tick(self) -> bool:
        self.timer += 1
        if self.timer < self.cycle_frames:
            return False
        self.timer = 0
        repaired = bool(self.flipped)
        self.flipped.clear()
        return repaired

    def switch(self) -> None:
        self.basis = PHASE if self.basis == BIT else BIT

    def reencode(self) -> bool:
        repaired = bool(self.flipped)
        self.flipped.clear()
        return repaired

    def label(self) -> str:
        return "|" + ("0" if self.basis == BIT else "+") * self.distance + ">"
