"""The repetition code each fighter carries. Pure and exact.

A distance-d repetition code corrects t = (d - 1) // 2 errors of one kind:
the bit-flip code (|0..0>, |1..1>) corrects X errors and cannot see Z; the
phase-flip code (|+..+>, |-..->) corrects Z and cannot see X. A transversal
H maps one code onto the other, and X errors onto Z errors. Y = iXZ always
has a part the code can't see, so it is always a logical error.

The code is corrected on a fixed cycle (the majority vote). Errors landing
within one cycle accumulate; more than t means the vote will fail, so the
logical error is reported as soon as it is certain.
"""

from __future__ import annotations

X, Z, Y = "X", "Z", "Y"
BIT, PHASE = "bit", "phase"
FLIPPED, LOGICAL = "flipped", "logical"
_CORRECTS = {BIT: X, PHASE: Z}


class Code:
    def __init__(self, distance: int, cycle_frames: int) -> None:
        assert distance % 2 == 1 and distance >= 3
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
        return _CORRECTS[self.basis] == error

    def hit(self, error: str) -> str:
        if not self.corrects(error):
            return self.logical_error()
        # the next unflipped qubit: hitting a flipped one again would undo it (XX = I)
        self.flipped.add(min(set(range(self.distance)) - self.flipped))
        if len(self.flipped) > self.t:
            return self.logical_error()
        return FLIPPED

    def logical_error(self) -> str:
        self.flipped.clear()  # the code is re-encoded
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
