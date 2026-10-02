"""The Shor code each fighter carries: [[9,1,3]], drawn as a 3x3 grid.

Exact physics: three blocks of three qubits. Inside a block a bit-flip code
guards against X errors; across the blocks a phase-flip code guards against Z
errors. It corrects any single-qubit error, X, Y or Z.

The grid: rows are blocks (the hit heights HIGH, MID, LOW), columns are the
qubits in a block (A, B, THROW).
- X on a qubit lights its cell. X twice on one qubit cancels (XX = I).
- Two different X cells in one row can't be corrected: the block's majority
  vote completes them to XXX, a logical operator.
- Z on any qubit of a block acts the same on the code, so it flips the whole
  row. Z twice in one block cancels (Z_i Z_j is a stabiliser: degeneracy).
- Z on two different rows can't be corrected: the vote across the blocks
  completes them to a logical operator.
- X and Z are decoded independently (the Shor code is CSS); Y = X and Z.
tests/test_shor.py checks all of this against the stabiliser formalism.

GAME RULES:
- An uncorrectable state is reported as a logical error at once (the decoder
  would fail at the next tick if nothing else landed before it), and the
  qubit is then re-encoded.
- Correction runs on a fixed beat of cycle_frames.
"""

from __future__ import annotations

HIGH, MID, LOW = 0, 1, 2
ROWS = ("HIGH", "MID", "LOW")
A_COL, B_COL, THROW_COL = 0, 1, 2
X, Z, Y = "X", "Z", "Y"
FLIPPED, CANCEL, LOGICAL = "flipped", "cancel", "logical"
_RANK = {CANCEL: 0, FLIPPED: 1, LOGICAL: 2}


def _check(row: int, col: int = 0) -> None:
    if not (0 <= row < 3 and 0 <= col < 3):
        raise ValueError(f"no such cell: row {row}, col {col}")


class ShorCode:
    def __init__(self, cycle_frames: int) -> None:
        if cycle_frames < 1:
            raise ValueError(f"cycle_frames must be >= 1, not {cycle_frames}")
        self.cycle_frames = cycle_frames
        self.x_cells: set[tuple[int, int]] = set()
        self.z_rows: set[int] = set()
        self.timer = 0

    # --- reading ----------------------------------------------------------------------

    @property
    def progress(self) -> float:
        return self.timer / self.cycle_frames

    @property
    def lights(self) -> int:
        return len(self.x_cells) + len(self.z_rows)

    def x_danger_rows(self) -> set[int]:
        """Rows where one more X on a different cell is a logical error."""
        return {r for r in range(3) if sum(1 for rr, _ in self.x_cells if rr == r) == 1}

    def z_danger_rows(self) -> set[int]:
        """Rows where a Z is a logical error: every other row, once one is flipped."""
        return {r for r in range(3) if self.z_rows and r not in self.z_rows}

    # --- errors -----------------------------------------------------------------------

    def apply(self, error: str, row: int, col: int) -> str:
        if error == X:
            return self.apply_x(row, col)
        if error == Z:
            _check(row, col)        # the column is ignored, but must still be a real one
            return self.apply_z(row)
        if error == Y:
            return self.apply_y(row, col)
        raise ValueError(f"unknown error type: {error}")

    def apply_x(self, row: int, col: int) -> str:
        _check(row, col)
        cell = (row, col)
        if cell in self.x_cells:
            self.x_cells.remove(cell)
            return CANCEL
        self.x_cells.add(cell)
        if sum(1 for r, _ in self.x_cells if r == row) >= 2:
            return self.logical_error()
        return FLIPPED

    def apply_z(self, row: int) -> str:
        _check(row)
        if row in self.z_rows:
            self.z_rows.remove(row)
            return CANCEL
        self.z_rows.add(row)
        if len(self.z_rows) >= 2:
            return self.logical_error()
        return FLIPPED

    def apply_y(self, row: int, col: int) -> str:
        """Y = X and Z on one qubit: the worse of the two outcomes."""
        first = self.apply_x(row, col)
        if first == LOGICAL:
            return LOGICAL
        second = self.apply_z(row)
        return max(first, second, key=_RANK.__getitem__)

    def logical_error(self) -> str:
        self.reset()            # GAME RULE: the qubit is re-encoded
        return LOGICAL

    # --- correction -------------------------------------------------------------------

    def reset(self) -> None:
        self.x_cells.clear()
        self.z_rows.clear()

    def reencode(self) -> bool:
        """An extra correction round, now: clears every (correctable) error."""
        repaired = self.lights > 0
        self.reset()
        return repaired

    def tick(self) -> bool:
        """One frame of the cycle; on its last frame the decoder clears every error
        (all of them are correctable: an uncorrectable state was reported at once)."""
        self.timer += 1
        if self.timer < self.cycle_frames:
            return False
        self.timer = 0
        repaired = self.lights > 0
        self.reset()
        return repaired
