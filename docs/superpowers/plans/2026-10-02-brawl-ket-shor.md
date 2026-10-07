# Brawl-Ket v2 (Shor code) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace Brawl-Ket's repetition-code rules with the Shor-code design in
`docs/superpowers/specs/2026-10-02-brawl-ket-shor-design.md`: every fighter's
health is a 3×3 Shor grid, normals deal X to a cell, specials Z to a row,
throws Y; heights decide rows and dodges.

**Architecture:** A new pure module `shor.py` replaces `qec.py` and is verified
against an independent Pauli-algebra reference in its tests. The engine
(`fighter.py`, `fight.py`, `match.py`, `render.py`) keeps its structure:
`Move` gains a `height` and a `column`, the fighter keeps its own crouch flag
instead of a code basis, and the renderer draws a grid tag instead of a row of
lights.

**Tech Stack:** Python 3.11, pygame 2.5.2, uv, pytest. All commands run from
`brawl-ket/`.

## Global Constraints

- `requires-python = ">=3.11,<3.12"`; `pygame==2.5.2` exactly. No new dependencies (no numpy).
- LF line endings in every file.
- The simulation counts integer frames at 60 Hz; seconds appear only in `config.py` via `config.frames()`.
- Kets and labels are ASCII: Press Start 2P has no ⟩, no Unicode minus, no `·`. Write `XX = I`, never `X·X`.
- Exact physics stays exact; anything that is a game rule is labelled `GAME RULE:` in a code comment (spec section 1, "Physics, and what is a game rule").
- Buttons: A = raw 1, B = 2, X = 0, Start = 9, Select = 8. P1 blue on the left, P2 red on the right.
- Commit messages follow the repo's gitmoji style (`feat: :sparkles: Brawl-Ket: ...`) and end with `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.
- The suite must pass at the end of every task: `uv run pytest -q`.

## File structure

| File | Responsibility after this plan |
|---|---|
| `src/brawl_ket/shor.py` (new) | The Shor code: grid state, applying X/Z/Y, cancel/flip/logical verdicts, the correction cycle, danger queries. Pure. |
| `src/brawl_ket/qec.py` (deleted) | Replaced by `shor.py`. |
| `src/brawl_ket/moves.py` | Frame data; `Move.height`, `Move.column`, `Move.landing_height`; no `Character.distance`. |
| `src/brawl_ket/fighter.py` | State machine with a `crouching` flag; no stance switch; hits go to `ShorCode`. |
| `src/brawl_ket/fight.py` | Hit resolution with the height whiff rules, `cancel` events, cell/row on events, DIVE bounce, COLLAPSE double hit. |
| `src/brawl_ket/poses.py` | Reads `f.crouching`; no switch pose. |
| `src/brawl_ket/render.py` | The grid tag, its effects, the select screen's move list, the rules card, the ROUND 1 hint. |
| `src/brawl_ket/match.py` | The title alternates demo and rules card; first-round hint flag. |
| `src/brawl_ket/bot.py` | Reads the rival's grid. |
| `src/brawl_ket/audio.py` | A sound for `cancel`. |
| `tests/test_shor.py` (new), `tests/test_qec.py` (deleted) | The code and its reference. |

---

### Task 1: `shor.py` and its reference test

**Files:**
- Create: `src/brawl_ket/shor.py`
- Create: `tests/test_shor.py`

**Interfaces:**
- Produces (used by every later task):
  - constants `HIGH, MID, LOW = 0, 1, 2`, `ROWS = ("HIGH", "MID", "LOW")`, `A_COL, B_COL, THROW_COL = 0, 1, 2`, `X, Z, Y = "X", "Z", "Y"`, `FLIPPED, CANCEL, LOGICAL = "flipped", "cancel", "logical"`
  - `class ShorCode(cycle_frames: int)` with attributes `x_cells: set[tuple[int, int]]`, `z_rows: set[int]`, `timer: int`, `cycle_frames: int`
  - `ShorCode.apply(error: str, row: int, col: int) -> str` (X → cell, Z → row (col ignored), Y → both); `apply_x(row, col)`, `apply_z(row)`, `apply_y(row, col)`
  - `ShorCode.logical_error() -> str`, `tick() -> bool`, `reencode() -> bool`, `reset() -> None`
  - properties `progress: float`, `lights: int`; methods `x_danger_rows() -> set[int]`, `z_danger_rows() -> set[int]`

- [ ] **Step 1: Write the failing test** `tests/test_shor.py`:

```python
"""The Shor code, checked against an independent reference: the [[9,1,3]] code
built from its 8 stabilisers in the Pauli (symplectic) formalism, with the
standard decoder (majority inside each block, then across the blocks)."""

from __future__ import annotations

from itertools import product

import pytest

from brawl_ket import shor
from brawl_ket.shor import CANCEL, FLIPPED, HIGH, LOGICAL, LOW, MID, ShorCode

# --- the reference: Paulis on 9 qubits as (x bits, z bits), qubit = 3 * row + col ---


def _x(*qs):
    return (sum(1 << q for q in qs), 0)


def _z(*qs):
    return (0, sum(1 << q for q in qs))


def _mul(a, b):                         # up to a phase
    return (a[0] ^ b[0], a[1] ^ b[1])


def _commute(a, b):
    return (bin(a[0] & b[1]).count("1") + bin(a[1] & b[0]).count("1")) % 2 == 0


I = (0, 0)
STABS = [_z(0, 1), _z(1, 2), _z(3, 4), _z(4, 5), _z(6, 7), _z(7, 8),
         _x(0, 1, 2, 3, 4, 5), _x(3, 4, 5, 6, 7, 8)]
GROUP = {I}
for _s in STABS:
    GROUP |= {_mul(g, _s) for g in GROUP}
_MAJ = {(1, 0): 0, (1, 1): 1, (0, 1): 2}     # syndrome pair -> the odd one out


def ref_logical(e) -> bool:
    """True if the standard decoder leaves a logical operator behind."""
    s = [0 if _commute(e, st) else 1 for st in STABS]
    corr = I
    for r in range(3):                          # X errors: majority inside block r
        q = _MAJ.get((s[2 * r], s[2 * r + 1]))
        if q is not None:
            corr = _mul(corr, _x(3 * r + q))
    r = _MAJ.get((s[6], s[7]))                  # Z errors: majority across the blocks
    if r is not None:
        corr = _mul(corr, _z(3 * r))
    residual = _mul(e, corr)
    assert all(_commute(residual, st) for st in STABS)
    return residual not in GROUP


def ref_state(code: ShorCode):
    """The Pauli the game's grid stands for (Z drawn on a row = Z on its first qubit)."""
    e = I
    for r, c in code.x_cells:
        e = _mul(e, _x(3 * r + c))
    for r in code.z_rows:
        e = _mul(e, _z(3 * r))
    return e


# A hit in the reference alphabet: ("X", row, col), ("Z", row, qubit-in-row), ("Y", row, col)
HITS = [(k, r, c) for k in "XZY" for r in range(3) for c in range(3)]


def ref_pauli(hit):
    k, r, c = hit
    q = 3 * r + c
    return {"X": _x(q), "Z": _z(q), "Y": _mul(_x(q), _z(q))}[k]


def game_apply(code: ShorCode, hit) -> str:
    k, r, c = hit
    return code.apply(k, r, c)      # for Z the column is ignored: any qubit of the row


@pytest.mark.parametrize("n", [1, 2, 3])
def test_every_sequence_of_hits_matches_the_reference(n):
    """For every sequence of up to 3 hits: the game reports LOGICAL exactly when the
    accumulated error is one the decoder can't correct (then re-encodes), and otherwise
    its grid stands for the same error, up to stabilisers."""
    for seq in product(HITS, repeat=n):
        code = ShorCode(60)
        acc = I
        for hit in seq:
            acc = _mul(acc, ref_pauli(hit))
            verdict = game_apply(code, hit)
            if ref_logical(acc):
                assert verdict == LOGICAL, seq
                assert code.lights == 0
                acc = I                     # GAME RULE: re-encoded
            else:
                assert verdict in (FLIPPED, CANCEL), seq
                assert _mul(ref_state(code), acc) in GROUP, seq


SPEC_TABLE = [   # spec section 1: errors in one cycle -> logical?
    ([("X", MID, 0), ("X", MID, 0)], False),
    ([("X", MID, 0), ("X", MID, 1)], True),
    ([("X", HIGH, 0), ("X", MID, 1)], False),
    ([("Z", LOW, 0), ("Z", LOW, 1)], False),
    ([("Z", HIGH, 0), ("Z", LOW, 0)], True),
    ([("Y", MID, 2)], False),
    ([("X", MID, 0), ("Y", MID, 2)], True),
    ([("X", HIGH, 0), ("Y", MID, 2)], False),
    ([("X", MID, 0), ("Z", MID, 0)], False),
]


@pytest.mark.parametrize("hits,logical", SPEC_TABLE)
def test_the_spec_table(hits, logical):
    code = ShorCode(60)
    verdicts = [game_apply(code, h) for h in hits]
    assert (verdicts[-1] == LOGICAL) == logical
    acc = I
    for h in hits:
        acc = _mul(acc, ref_pauli(h))
    assert ref_logical(acc) == logical


def test_cancel_is_reported_when_a_hit_undoes_a_light():
    code = ShorCode(60)
    assert code.apply_x(MID, 0) == FLIPPED
    assert code.apply_x(MID, 0) == CANCEL and code.lights == 0
    assert code.apply_z(LOW) == FLIPPED
    assert code.apply_z(LOW) == CANCEL and code.lights == 0


def test_a_throw_on_a_clean_grid_lights_its_cell_and_row():
    code = ShorCode(60)
    assert code.apply_y(MID, shor.THROW_COL) == FLIPPED
    assert code.x_cells == {(MID, shor.THROW_COL)} and code.z_rows == {MID}


def test_the_cycle_clears_correctable_errors_on_its_tick():
    code = ShorCode(3)
    code.apply_x(HIGH, 0)
    code.apply_z(LOW)
    assert [code.tick(), code.tick()] == [False, False]
    assert code.progress == pytest.approx(2 / 3)
    assert code.tick() is True and code.lights == 0 and code.timer == 0
    assert code.tick() is False             # nothing to repair: no correction reported


def test_reencode_is_an_extra_correction_round():
    code = ShorCode(60)
    assert code.reencode() is False
    code.apply_x(HIGH, 1)
    assert code.reencode() is True and code.lights == 0


def test_danger_rows():
    code = ShorCode(60)
    code.apply_x(HIGH, 0)
    assert code.x_danger_rows() == {HIGH}       # one more different X there breaks it
    assert code.z_danger_rows() == set()
    code.apply_z(MID)
    assert code.z_danger_rows() == {HIGH, LOW}  # a Z on either other row breaks it


def test_bad_arguments_are_rejected():
    with pytest.raises(ValueError):
        ShorCode(0)
    code = ShorCode(60)
    with pytest.raises(ValueError):
        code.apply("W", 0, 0)
    with pytest.raises(ValueError):
        code.apply_x(3, 0)
```

- [ ] **Step 2: Run it to verify it fails**

Run: `uv run pytest -q tests/test_shor.py`
Expected: FAIL (`ModuleNotFoundError: No module named 'brawl_ket.shor'`).

- [ ] **Step 3: Implement** `src/brawl_ket/shor.py`:

```python
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
  is certain to fail at the next tick), and the qubit is then re-encoded.
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
```

- [ ] **Step 4: Run the tests**

Run: `uv run pytest -q tests/test_shor.py`
Expected: all pass (the n=3 case runs 27³ ≈ 20 000 sequences; it takes about a second).

- [ ] **Step 5: Commit**

```bash
git add src/brawl_ket/shor.py tests/test_shor.py
git commit -m "feat: :atom_symbol: Brawl-Ket: the Shor code (shor.py), checked against the stabiliser formalism"
```

---

### Task 2: Swap the code into the engine

The fighter carries a `ShorCode`; moves gain a height and a column; the stance
switch goes; the tag over each head becomes a grid. Numbers (startups, damage)
stay as they are until Task 4, so only the rules change here.

**Files:**
- Modify: `src/brawl_ket/moves.py`, `src/brawl_ket/fighter.py`, `src/brawl_ket/fight.py`, `src/brawl_ket/poses.py`, `src/brawl_ket/render.py`, `src/brawl_ket/bot.py`, `src/brawl_ket/config.py`, `tools/snapshot.py`
- Delete: `src/brawl_ket/qec.py`, `tests/test_qec.py`
- Modify tests: `tests/test_moves.py`, `tests/test_fighter.py`, `tests/test_fight.py`, `tests/test_poses.py`, `tests/test_render.py`, `tests/test_bot.py`

**Interfaces:**
- Consumes: everything from Task 1.
- Produces:
  - `Move` fields `error: str` (`shor.X`/`Z`/`Y`), `height: int` (`shor.HIGH`/`MID`/`LOW`), `column: int = 0`, `landing_height: int = shor.LOW`; `Character` loses `distance`.
  - `Fighter.code: ShorCode`, `Fighter.crouching: bool`; `Fighter.take_hit(move, from_facing) -> str` returns `shor.FLIPPED`/`CANCEL`/`LOGICAL`. Actions no longer include `"switch"`.
  - `Event` gains `row: int | None = None`, `col: int | None = None`; hit events have kind `"hit"`, `"cancel"` or `"logical"`.
  - `render.TAG_HALF: float` (half a tag's width) replaces `tag_half()`, `tag_bounds()`, `tag_row()`, `light_xs()`, `tag_state()`.

- [ ] **Step 1: Write the new rule tests** (they fail until Step 4). Append to `tests/test_fight.py`:

```python
# --- the Shor grid ----------------------------------------------------------------------

from brawl_ket import shor  # noqa: E402


def press_at(fight, frames, **buttons):
    """p1 presses the given buttons on the given frames ({button: frame}), down held if `down`."""
    down = buttons.pop("down", False)
    events = []
    for i in range(frames):
        pressed = {b: f == i for b, f in buttons.items()}
        events += fight.step({"p1": FighterInput(down=down, **pressed), "p2": IDLE})
    return events


def test_a_jab_lights_its_cell_on_the_rivals_grid():
    fight = new(gap=50.0)
    events = press_at(fight, 30, a=0)
    hit = of(events, "hit")[0]
    assert (hit.error, hit.row, hit.col) == (shor.X, shor.HIGH, shor.A_COL)
    assert fight.fighters["p2"].code.x_cells == {(shor.HIGH, shor.A_COL)}


def test_two_jabs_at_one_height_cancel():
    fight = new(gap=50.0)
    events = press_at(fight, 40, a=0)
    events += press_at(fight, 40, a=0)
    assert kinds(of(events, "hit", "cancel", "logical")) == ["hit", "cancel"]
    assert fight.fighters["p2"].code.lights == 0


def test_jab_then_heavy_at_one_height_is_a_logical_error():
    fight = new(gap=50.0)
    events = run_chain_events(fight, ["a", "b"])
    assert kinds(of(events, "hit", "cancel", "logical")) == ["hit", "logical"]


def run_chain_events(fight, buttons, crouch=False):
    """Like run_chain, but returns the events."""
    held = FighterInput(down=crouch)
    events, i, press_next = [], 0, True
    for _ in range(200):
        btn = buttons[i] if press_next and i < len(buttons) else None
        if btn:
            i += 1
        press_next = False
        step = fight.step({"p1": replace(held, **({btn: True} if btn else {})), "p2": IDLE})
        events += step
        if of(step, "hit", "cancel", "logical"):
            press_next = True
        if i == len(buttons) and not press_next and of(step, "hit", "cancel", "logical"):
            break
    return events
```

Append to `tests/test_fighter.py`:

```python
def test_crouching_is_instant_and_has_no_switch():
    f = Fighter(TRIO, 200, 1)
    f.step(FighterInput(down=True), 400)
    assert f.crouching and f.stance == "crouch" and f.action == "crouch"
    f.step(FighterInput(), 400)
    assert not f.crouching and f.stance == "stand"


def test_down_a_from_standing_is_a_low_jab_at_once():
    f = Fighter(TRIO, 200, 1)
    f.step(FighterInput(down=True, a=True), 400)
    assert f.slot == "crouch.A"
```

Append to `tests/test_moves.py`:

```python
from brawl_ket import shor  # noqa: E402

HEIGHTS = {"stand.A": shor.HIGH, "stand.B": shor.HIGH, "crouch.A": shor.LOW, "crouch.B": shor.LOW,
           "air.A": shor.MID, "air.B": shor.MID, "throw": shor.MID}
COLUMNS = {"stand.A": shor.A_COL, "crouch.A": shor.A_COL, "air.A": shor.A_COL,
           "stand.B": shor.B_COL, "crouch.B": shor.B_COL, "air.B": shor.B_COL, "throw": shor.THROW_COL}


def test_normals_deal_x_in_their_buttons_column_at_their_height():
    for c in CHARACTERS.values():
        for slot, height in HEIGHTS.items():
            m = c.moves[slot]
            want = shor.Y if slot == "throw" else shor.X
            assert (m.error, m.height, m.column) == (want, height, COLUMNS[slot]), (c.name, slot)


def test_every_height_has_an_a_and_a_b():
    for height in (shor.HIGH, shor.MID, shor.LOW):
        cols = {COLUMNS[s] for s, h in HEIGHTS.items() if h == height and s != "throw"}
        assert cols == {shor.A_COL, shor.B_COL}


SPECIALS_ZH = {   # (character, slot): height of its Z
    ("TRIO", "stand.X"): shor.HIGH, ("TRIO", "crouch.X"): shor.LOW, ("TRIO", "air.X"): shor.MID,
    ("QUINT", "stand.X"): shor.MID, ("QUINT", "air.X"): shor.HIGH,
}


def test_specials_deal_z_at_their_height():
    for (name, slot), height in SPECIALS_ZH.items():
        m = CHARACTERS[name].moves[slot]
        assert (m.error, m.height) == (shor.Z, height), (name, slot)
    collapse = CHARACTERS["QUINT"].moves["air.X"]
    assert (collapse.landing_error, collapse.landing_height) == (shor.Z, shor.LOW)
    assert CHARACTERS["QUINT"].moves["crouch.X"].kind == "reencode"
```

- [ ] **Step 2: Run them to verify they fail**

Run: `uv run pytest -q tests/test_fight.py tests/test_fighter.py tests/test_moves.py -k "grid or cancel or logical_error or crouching_is_instant or low_jab_at_once or column or a_and_a_b or specials_deal_z"`
Expected: FAIL (no `shor` attributes on moves, no `crouching`).

- [ ] **Step 3a: `moves.py`.** Replace `from . import qec` with `from . import shor`. In `Move`, replace the `error` comment and add fields after `error`:

```python
    error: str                          # shor.X (normals) / shor.Z (specials) / shor.Y (throws)
    height: int                         # shor.HIGH / MID / LOW: the row it lands in, and who dodges it
```

and, after `landing_error`:

```python
    landing_height: int = shor.LOW      # the shockwave's row
    column: int = shor.A_COL            # the X's column: A, B or THROW (specials: unused)
```

`height` has no default, so it must come before the defaulted fields: place it directly after `error`, and keep `column`/`landing_height` among the defaulted fields. Remove `distance` from `Character` and from both `Character(...)` calls. Then set every move's error/height/column (only these arguments change; keep all other numbers as they are):

| Slot | TRIO / QUINT error, height, column |
|---|---|
| `stand.A` | `shor.X, shor.HIGH`, `column=shor.A_COL` |
| `stand.B` | `shor.X, shor.HIGH`, `column=shor.B_COL` |
| `crouch.A` | `shor.X, shor.LOW`, `column=shor.A_COL` |
| `crouch.B` | `shor.X, shor.LOW`, `column=shor.B_COL` |
| `air.A` | `shor.X, shor.MID`, `column=shor.A_COL` |
| `air.B` | `shor.X, shor.MID`, `column=shor.B_COL` |
| `throw` | `shor.Y, shor.MID`, `column=shor.THROW_COL` |
| TRIO `stand.X` PHOTON | `shor.Z, shor.HIGH` |
| TRIO `crouch.X` PHASE SLIDE | `shor.Z, shor.LOW` |
| TRIO `air.X` DIVE | `shor.Z, shor.MID` |
| QUINT `stand.X` SYNDROME GRAB | `shor.Z, shor.MID` |
| QUINT `crouch.X` RE-ENCODE | `shor.Z, shor.MID` (never hits; unused) |
| QUINT `air.X` COLLAPSE | `shor.Z, shor.HIGH`, `landing_error=shor.Z` (and `landing_height` defaults to LOW) |

Example (TRIO's jab):

```python
        "stand.A": Move(
            "jab", 4, 3, 8, Box(14, 70, 44, 14), shor.X, shor.HIGH,
            chip=2, bonus=0, hitstun=16, knockback=0.8, lunge=1.5, column=shor.A_COL,
            cancels=("stand.A", "stand.B", "crouch.A"),
            poses=("jab_wind", "jab_hit", "jab_wind"),
        ),
```

- [ ] **Step 3b: `fighter.py`.** Replace `from . import qec` with `from . import shor`; drop `SWITCH_FRAMES` from the config import. In `__init__`: `self.code = shor.ShorCode(char.cycle_frames)`, add `self.crouching = False`, delete `self.switch_left`, and change the action comment to `# idle walk crouch jump attack hitstun knockdown`. Then:

```python
    @property
    def stance(self) -> str:
        if self.y > 0:
            return "air"
        return "crouch" if self.crouching else "stand"
```

In `step()`, the buffer always ages (delete the `if self.action != "switch":` guard and its comment, keep the list comprehension). Replace `take_hit`'s first lines:

```python
    def take_hit(self, move: Move, from_facing: int) -> str:
        result = self.code.apply(move.error, move.height, move.column)
        damage = LOGICAL_DAMAGE + move.bonus if result == shor.LOGICAL else move.chip
        self.health = max(0, self.health - damage)
```

`_neutral()`: `elif self.crouching:` instead of the basis test. `_advance()`: delete the `elif self.action == "switch":` branch. Delete `_start_switch`. In `_act()`, replace the basis/switch block (from `basis = self.code.basis` to its `return`) with:

```python
        if on_ground_free:
            # Crouching is instant: it is ducking, not a change of code.
            self.crouching = inp.down and not inp.up
```

and at the end of `_act()` replace `elif basis == qec.PHASE:` with `elif self.crouching:`. In `_physics`/`_act` where a jump starts (`if inp.up:`), also set `self.crouching = False`. Update the module docstring's "ticks each fighter's qec.Code" to "ticks each fighter's shor.ShorCode".

- [ ] **Step 3c: `fight.py`.** Replace `from . import qec` with `from . import shor`. In `Event` add, after `y`:

```python
    row: int | None = None          # hit / cancel / logical: the grid row (and the X's column)
    col: int | None = None
```

and extend the kinds comment with `cancel`. In `_resolve_hits`, replace the event/hitstop lines with:

```python
            kind = {shor.FLIPPED: "hit", shor.CANCEL: "cancel", shor.LOGICAL: "logical"}[result]
            events.append(Event(kind, st.defender, st.move.error, st.where[0], st.where[1],
                                st.move.height, st.move.column))
            stop = HITSTOP_LOGICAL if result == shor.LOGICAL else HITSTOP
            self.hitstop = max(self.hitstop, stop)
```

In `_landing_strike`, the swapped-in move also takes the landing height: `replace(move, error=move.landing_error, height=move.landing_height)`.

- [ ] **Step 3d: `poses.py`.** Replace `from . import qec` usage: in `_rest` use `if slot is None and f.crouching:`; `_stance_pose` uses `f.crouching`; delete the `if a == "switch":` branch and the `SWITCH_FRAMES` import. The knockdown get-up comment "into the stance the code is in" becomes "into the stance".

- [ ] **Step 3e: `config.py`.** Delete `SWITCH_FRAMES` and its comment line.

- [ ] **Step 3f: `bot.py`.** Remove `"switch"` from `_BUSY` and the `if me.action != "switch":` guard (always `self.chain.clear()`). Replace the chain choice with `self.chain = ["a", "b"]` (Task 6 makes the bot read the grid) and `_wants_reencode` with:

```python
    def _wants_reencode(self, me) -> bool:
        """RE-ENCODE (crouch.X) once a row is in danger, if it is ready."""
        move = me.char.moves["crouch.X"]
        danger = me.code.x_danger_rows() or me.code.z_danger_rows()
        return (move.kind == "reencode" and bool(danger)
                and me.cooldowns.get("crouch.X", 0) == 0 and self.rng.random() < self.skill)
```

Delete the comment "the switch to the crouch comes first; the press waits".

- [ ] **Step 3g: `render.py`.** Replace `from . import qec` with `from . import shor`. Delete `LIGHT_GAP`, `DIVIDER_GAP`, `tag_state`, `tag_row`, `tag_half`, `tag_bounds`, `light_xs`. Add:

```python
CELL, CELL_GAP = 6, 3       # a grid cell and the gap between cells, px
GRID = 3 * CELL + 2 * CELL_GAP              # 24: the 3x3 grid
PLATE = GRID + 8                            # the plate around it
TAG_HALF = PLATE / 2 + 2 + 2 * RING_R + 1   # half a tag's width: the plate, then the ring
```

(`RING_R` must be defined above these lines.) Set `TAG_ABOVE_HEAD = 46` (the grid plate is taller than the old row). In `_tag_place` use `lo, hi = TAG_HALF + TAG_EDGE, W - TAG_HALF - TAG_EDGE` and `target = max(70.0, head[1] - TAG_ABOVE_HEAD)`. In `_separate` use `ha = hb = TAG_HALF`. Replace `_code_tag` with:

```python
    def _code_tag(self, key: str, f: Fighter, at, ox: int, oy: int) -> None:
        """The code over the head: a 3x3 grid (rows HIGH, MID, LOW; columns A, B, THROW)
        on a plate in the player's colour, and the cycle ring beside it.

        An X lights its cell in the X gate's red; a row flipped by a Z glows behind in the
        Z gate's blue. Danger pulses orange: the other cells of a row holding one X (a
        different button there breaks the code), or the other rows once one is flipped
        (a special there breaks it)."""
        code = f.code
        surf = self.surface
        cx, cy = round(at[0]) + ox, round(at[1]) + oy
        color = PLAYER_COLORS[key]
        plate = pygame.Rect(0, 0, PLATE, PLATE)
        plate.center = (cx, cy)
        tick = min(max(round(at[2] + ox), plate.left + 4), plate.right - 4)
        pygame.draw.polygon(surf, P.INK, ((tick - 5, plate.bottom), (tick + 5, plate.bottom), (tick, plate.bottom + 6)))
        pygame.draw.polygon(surf, color, ((tick - 3, plate.bottom), (tick + 3, plate.bottom), (tick, plate.bottom + 3)))
        pygame.draw.rect(surf, P.INK, plate.inflate(2, 2), border_radius=5)
        pygame.draw.rect(surf, color, plate, border_radius=4)
        pygame.draw.rect(surf, P.NIGHT, plate.inflate(-4, -4), border_radius=3)
        flash, left = self.flash[key]
        lit = flash is not None and left % 6 >= 2
        beat = (self.t // (DANGER_BEAT // 2)) % 2 == 0
        x_danger, z_danger = code.x_danger_rows(), code.z_danger_rows()
        for row in range(3):
            y = plate.top + 4 + row * (CELL + CELL_GAP)
            if row in code.z_rows:
                surf.fill(P.GATE[shor.Z], (plate.left + 2, y - 1, PLATE - 4, CELL + 2))
            elif row in z_danger and beat:
                surf.fill(P.shade(P.ORANGE, 0.6), (plate.left + 2, y - 1, PLATE - 4, CELL + 2))
            for col in range(3):
                x = plate.left + 4 + col * (CELL + CELL_GAP)
                if lit:
                    c = flash
                elif (row, col) in code.x_cells:
                    c = P.GATE[shor.X]
                elif row in x_danger and beat:
                    c = P.ORANGE
                else:
                    c = P.SLATE
                surf.fill(P.INK, (x - 1, y - 1, CELL + 2, CELL + 2))
                surf.fill(c, (x, y, CELL, CELL))
                surf.fill(P.lighten(c, 0.5), (x, y, 2, 2))
        ring = self.rings[min(RING_STEPS, int(code.progress * RING_STEPS))]
        blit_center(surf, ring, (plate.right + 2 + RING_R, cy))
```

In `Renderer.__init__`, `for e in (shor.X, shor.Y, shor.Z):` replaces the `qec` loop. Also render the cancel pop-up text once there: `outlined("I", 16, P.WHITE, thick=2)`. In `_start_effects`, treat `"cancel"` like a hit for the spark (white) and pop-up `I`:

```python
            if e.kind in ("hit", "logical", "cancel"):
                color = P.WHITE if e.kind == "cancel" else P.GATE.get(e.error or "X", P.WHITE)
                text = "I" if e.kind == "cancel" else f"{e.error}!"
                self.effects.append(Effect("spark", e.x, e.y, SPARK_FRAMES, SPARK_FRAMES, color))
                self.effects.append(Effect("popup", e.x, e.y - 18, POPUP_FRAMES, POPUP_FRAMES, color, text))
```

On the select screen (`_select_panel`), the line `ket = ...; t = ...; lines = (f"{ket}  FIXES ..."` becomes `lines = ("SHOR CODE  |0>_L", TRAITS.get(char.name, ""))`. On the title, `"|000>  VS  |00000>"` becomes `"SHOR CODE  VS  SHOR CODE"`.

- [ ] **Step 3h: `tools/snapshot.py`.** `tag_sheet(char)` draws a tag in its states; rewrite its states to: clean; one X at (HIGH, A) (danger in HIGH, two beats); Z on MID (danger rows, two beats); the green flash; the red flash. Use `f.code.apply_x(shor.HIGH, shor.A_COL)` / `f.code.apply_z(shor.MID)` in place of the old `_flip_t`, and delete `_flip_t`. Update its docstring line for `code_tags*.png` accordingly.

- [ ] **Step 3i: Delete** `src/brawl_ket/qec.py` and `tests/test_qec.py`.

- [ ] **Step 4: Bring the old tests in line.** Run `uv run pytest -q 2>&1 | tail -40` and fix every failure by one of these rules:
  - **Delete** tests of removed rules: the stance switch window (`SWITCH_FRAMES`, `"switch"` action, "a hit mid-switch is logical", presses not ageing mid-switch), the code basis (`basis`, `qec.BIT`/`PHASE`, `label()`), "a hit of the wrong kind for the stance is logical", "a throw is always logical", the repetition code's `t`/distance (`code.t`, `distance`, `test_quint_needs_three_hits_in_a_cycle`, `test_quint_breaks_trio_with_two_hits`), and the old tag geometry (`tag_half`, `tag_bounds`, `light_xs`, `tag_state`, majority line, `!` bang, "a bigger code has a wider tag").
  - **Rename** names: `qec.X/Z/Y` → `shor.X/Z/Y`; `qec.FLIPPED` → `shor.FLIPPED`; `qec.LOGICAL` → `shor.LOGICAL`; `code.flipped` → `code.x_cells` (or `code.lights` for counts); `tag_half(...)` → `TAG_HALF`.
  - **Re-derive** expectations that depended on the old rules: a test asserting "two jabs make a logical error" now asserts `["hit", "cancel"]`; damage assertions use `LOGICAL_DAMAGE + move.bonus` only on a `logical` event.
  - The render tests for tags keep their intent (tags stay on screen, on their own side, don't overlap) with `TAG_HALF`, and gain:

```python
def test_the_grid_lights_an_x_cell_and_a_z_row(surface):
    from brawl_ket import shor
    r = Renderer(surface)
    fight = Fight({"p1": TRIO, "p2": TRIO})
    f = fight.fighters["p1"]
    f.code.apply_x(shor.HIGH, shor.B_COL)
    f.code.apply_z(shor.LOW)
    r.draw_fight(fight, [])
    tag = r._tag_place("p1", f, (f.x, 200))
    surface.fill((0, 0, 0))
    r._code_tag("p1", f, (160, 120, 160), 0, 0)
    from brawl_ket.render import CELL, CELL_GAP, PLATE
    left, top = 160 - PLATE // 2, 120 - PLATE // 2
    x_cell = (left + 4 + 1 * (CELL + CELL_GAP) + 3, top + 4 + 3)          # (HIGH, B)
    z_back = (left + 3, top + 4 + 2 * (CELL + CELL_GAP) + 3)              # LOW row, left edge
    assert tuple(surface.get_at(x_cell))[:3] == P.GATE[shor.X]
    assert tuple(surface.get_at(z_back))[:3] == P.GATE[shor.Z]
```

  - The bot fairness tests in `tests/test_bot.py` must still pass; if `test_neither_side_is_favoured` or `test_neither_character_always_wins` fail only because the old chain no longer breaks codes, keep them: Task 6 restores code-breaking bots, and Step 3f's `["a", "b"]` chain already breaks codes.

Run: `uv run pytest -q`
Expected: all pass.

- [ ] **Step 5: Look at it.** Run `uv run python tools/snapshot.py /tmp/brawl-snaps` and open `code_tags.png`, `fight_hit.png`, `vs_danger.png`: the grid sits over each head, X cells red, a Z row blue.

- [ ] **Step 6: Commit**

```bash
git add -A src/brawl_ket tests tools
git commit -m "feat: :atom_symbol: Brawl-Ket: every fighter is a Shor code (the grid replaces the lights)"
```

---

### Task 3: Heights decide dodges; the specials rework

**Files:**
- Modify: `src/brawl_ket/fight.py`, `src/brawl_ket/fighter.py`, `src/brawl_ket/moves.py`
- Test: `tests/test_fight.py`, `tests/test_moves.py`

**Interfaces:**
- Consumes: `Move.height`, `Move.landing_height`, `Fighter.stance`, `Fighter.crouching` (Task 2).
- Produces: `fight.can_reach(height: int, target: Fighter) -> bool`; `Fighter.bounce() -> None`.

- [ ] **Step 1: Write the failing tests.** Append to `tests/test_fight.py`:

```python
from brawl_ket.fight import can_reach  # noqa: E402


def test_high_whiffs_on_a_crouch_and_low_on_a_jump():
    f = Fight({"p1": TRIO, "p2": TRIO}).fighters["p2"]
    assert can_reach(shor.HIGH, f) and can_reach(shor.MID, f) and can_reach(shor.LOW, f)
    f.crouching = True
    assert not can_reach(shor.HIGH, f) and can_reach(shor.MID, f) and can_reach(shor.LOW, f)
    f.crouching, f.y = False, 30.0
    assert can_reach(shor.HIGH, f) and can_reach(shor.MID, f) and not can_reach(shor.LOW, f)


def test_a_standing_jab_whiffs_over_a_crouching_rival():
    fight = new(gap=50.0)
    script(fight, 2, p2=FighterInput(down=True))
    events = script(fight, 30, p1={0: A}, p2=FighterInput(down=True))
    assert not of(events, "hit", "cancel", "logical")


def test_a_crouching_rival_ducks_a_photon():
    fight = new(gap=300.0)
    script(fight, 2, p1=FighterInput(down=True))
    photon_at(fight, "p2", fight.fighters["p1"].x + 30)
    events = script(fight, 12, p1=FighterInput(down=True))
    assert not of(events, "hit", "cancel", "logical")


def test_the_syndrome_grab_reaches_130_px():
    fight = versus(QUINT, TRIO, 130.0)
    events = script(fight, 60, p1={0: X})
    assert [(e.kind, e.error, e.row) for e in of(events, "hit", "logical")] == [("hit", shor.Z, shor.MID)]


def test_the_dive_lands_within_14_frames_of_the_apex():
    fight = new(gap=300.0)
    p1 = fight.fighters["p1"]
    script(fight, 1, p1=FighterInput(up=True))
    while p1.vy > 0:
        script(fight, 1)
    for n in range(1, 60):
        script(fight, 1, p1=X if n == 1 else IDLE)
        if p1.y == 0:
            break
    assert n <= 14


def test_a_dive_that_hits_bounces_back():
    fight = new(gap=60.0)
    p1 = fight.fighters["p1"]
    script(fight, 1, p1=FighterInput(up=True, dx=1))
    for _ in range(12):
        script(fight, 1)
    events = script(fight, 30, p1={0: X})
    assert of(events, "hit", "logical")
    assert p1.action != "attack" or p1.phase != "active"


def test_collapse_slam_and_shockwave_together_are_a_logical_error():
    fight = versus(QUINT, TRIO, 40.0)
    p1 = fight.fighters["p1"]
    script(fight, 1, p1=FighterInput(up=True))
    for _ in range(14):
        script(fight, 1)
    events = script(fight, 60, p1={0: X})
    hits = of(events, "hit", "logical")
    assert [e.kind for e in hits] == ["hit", "logical"]
    assert [e.row for e in hits] == [shor.HIGH, shor.LOW]


def test_collapse_shockwave_reaches_60_px_either_side():
    m = QUINT.moves["air.X"]
    assert m.landing == Box(-60, 0, 120, 14) and m.dive == (2.0, 9.0)
```

- [ ] **Step 2: Run them to verify they fail.**

Run: `uv run pytest -q tests/test_fight.py -k "whiff or ducks or grab_reaches_130 or dive_lands or bounces or slam_and_shockwave or shockwave_reaches"`
Expected: FAIL (`can_reach` missing; GRAB too short; DIVE too slow).

- [ ] **Step 3: Implement.** In `fight.py`, add above `class Fight`:

```python
def can_reach(height: int, target: Fighter) -> bool:
    """Which heights can touch a fighter: a crouch ducks HIGH, a jump clears LOW."""
    if height == shor.HIGH and target.stance == "crouch":
        return False
    if height == shor.LOW and target.y > 0:
        return False
    return True
```

Use it in `_move_strike` (after the knockdown check: `if not can_reach(m.height, rival): return`), in the shot loop (`if not can_reach(s.move.height, target): continue`) and in `_landing_strike` (`if not can_reach(move.landing_height, rival): ...` skip the strike but still count `win.left` down). In `_landing_strike`, let the shockwave hit a rival reeling from the slam: change `rival.action not in _STUNNED` to `rival.action != "knockdown"`. After `move_hit = True` is set for each strike in `_resolve_hits`, bounce a diving attacker that has no landing shockwave:

```python
        for st in strikes:
            if st.attacker is not None:
                f = self.fighters[st.attacker]
                f.move_hit = True
                if f.move is not None and f.move.dive is not None and f.move.landing is None:
                    f.bounce()
```

In `fighter.py`, add:

```python
    BOUNCE_VX, BOUNCE_VY = 2.0, 5.0     # px per frame: a DIVE springs back off what it hit

    def bounce(self) -> None:
        """A dive that connects springs back up and away, and its active frames end."""
        m = self.move
        assert m is not None
        self.frame = self.startup + m.active        # straight into the recovery
        self.vx = -self.BOUNCE_VX * self.facing
        self.vy = self.BOUNCE_VY
```

In `moves.py`: TRIO's DIVE becomes `"DIVE", 3, 40, 8, Box(6, 0, 26, 20), shor.Z, shor.MID, ..., dive=(3.0, 10.0)`; QUINT's SYNDROME GRAB becomes `"SYNDROME GRAB", 16, 22, 30, Box(10, 40, 30, 70), shor.Z, shor.MID, ..., kind="throw", lunge=6.0` (22 active frames at 6 px/frame: about 130 px); COLLAPSE becomes `dive=(2.0, 9.0), landing=Box(-60, 0, 120, 14)` with recovery 20. Update the matching rows in `tests/test_moves.py`'s `QUINT_FRAMES` and the specials tests (`test_quint_specials`: `grab.lunge == 6.0`; `collapse.dive == (2.0, 9.0)`, `collapse.landing == Box(-60, 0, 120, 14)`).

- [ ] **Step 4: Run the suite.**

Run: `uv run pytest -q`
Expected: all pass. If an older test asserted that the shockwave skips a rival in hitstun (`test_the_landing_shockwave_skips_a_downed_rival` keeps passing: knockdown still skips), update any test that expected the slam-stunned rival to be skipped: the spec now makes that a logical error.

- [ ] **Step 5: Commit**

```bash
git add -A src/brawl_ket tests
git commit -m "feat: :dart: Brawl-Ket: heights decide dodges; GRAB reaches, DIVE drops, COLLAPSE hits twice"
```

---

### Task 4: Feel: fast heavies, new damage, no telegraph

**Files:**
- Modify: `src/brawl_ket/moves.py`, `src/brawl_ket/config.py`, `src/brawl_ket/fighter.py`, `src/brawl_ket/render.py`, `src/brawl_ket/poses.py`, `tools/snapshot.py`
- Test: `tests/test_moves.py`, `tests/test_fighter.py`, `tests/test_render.py`, `tests/test_poses.py`

**Interfaces:**
- Consumes: Tasks 2–3.
- Produces: `config.LOGICAL_DAMAGE == 25`; a logical error leaves the defender in `"knockdown"`; `Fighter.telegraphing` and `fighter.TELEGRAPH_FRAMES` no longer exist.

- [ ] **Step 1: Write the failing tests.** In `tests/test_moves.py`, replace `DAMAGE_TIERS`, `test_the_damage_tiers`, `test_quint_hits_no_harder_than_trio`, `test_a_heavy_logical_error_costs_at_least_twice_a_light_one` and `test_the_heavies_telegraph_from_neutral_and_stay_fast_in_a_chain` with:

```python
STARTUPS = {   # spec section 3: (A, B on its own, B cancelled from a hit A)
    "TRIO": (4, 10, 7),
    "QUINT": (6, 13, 9),
}


def test_heavies_are_fast():
    for c in CHARACTERS.values():
        a, b, chained = STARTUPS[c.name]
        for light, heavy in (("stand.A", "stand.B"), ("crouch.A", "crouch.B")):
            assert c.moves[light].startup == a, (c.name, light)
            assert (c.moves[heavy].startup, c.moves[heavy].chain_startup) == (b, chained), (c.name, heavy)


def test_the_damage():
    assert config.LOGICAL_DAMAGE == 25
    for c in CHARACTERS.values():
        for slot, m in c.moves.items():
            if m.kind == "reencode":
                continue
            assert m.chip == 2, (c.name, slot)
            heavy_or_special = slot.endswith(".B") or slot.endswith(".X")
            assert m.bonus == (5 if heavy_or_special else 0), (c.name, slot)


def test_health_and_cycles():
    assert (TRIO.health, TRIO.cycle_frames) == (100, config.frames(1.0))
    assert (QUINT.health, QUINT.cycle_frames) == (115, config.frames(1.5))
```

In `tests/test_fighter.py` add:

```python
def test_a_logical_error_knocks_down():
    from brawl_ket import shor
    f = Fighter(TRIO, 200, 1)
    jab, heavy = TRIO.moves["stand.A"], TRIO.moves["stand.B"]
    assert f.take_hit(jab, -1) == shor.FLIPPED and f.action == "hitstun"
    assert f.take_hit(heavy, -1) == shor.LOGICAL and f.action == "knockdown"
    assert f.health == 100 - 2 - (25 + 5)
```

- [ ] **Step 2: Run to verify they fail.**

Run: `uv run pytest -q tests/test_moves.py tests/test_fighter.py -k "fast or damage or health_and_cycles or knocks_down"`
Expected: FAIL.

- [ ] **Step 3: Implement.**
  - `config.py`: `LOGICAL_DAMAGE = 25         # plus Move.bonus (5 for heavies and specials)`. Delete `REACTION_FRAMES` (it only justified the telegraph).
  - `moves.py`: for both characters set every hitting move's `chip=2`; `bonus=5` on every `.B` and `.X` slot, `bonus=0` on `.A` slots and `throw`. Startups: TRIO `stand.A`/`crouch.A` 4, `stand.B`/`crouch.B` `10` with `chain_startup=7`; QUINT `stand.A`/`crouch.A` 6, `stand.B`/`crouch.B` `13` with `chain_startup=9`. QUINT `health=115`. Rewrite the `chain_startup` comment in `Move`: "Startup when a cancel starts the move (None: the same as `startup`): a heavy comes out faster inside a chain."
  - `fighter.py`: delete `TELEGRAPH_FRAMES` and `telegraphing`. In `take_hit`, a logical error knocks down:

```python
        if move.knockdown or result == shor.LOGICAL:
            self.action = "knockdown"
            self.stun = KNOCKDOWN_FRAMES
```

  - `render.py`: delete `GLINT_BEAT`, `GLINT_MIN`, `GLINT_MAX`, `_glint`, the `telegraphing` call in `_fighter`, and the `TELEGRAPH_FRAMES` import.
  - `poses.py`: reword the `heavy_wind`/`sweep_wind` comments ("The wind-up is the telegraph (24 frames from neutral)" → "A big wind-up").
  - `tools/snapshot.py`: delete `glint_frames` and its calls, and the `fight_glint*`/`quint_glint*` lines from the docstring.
  - Tests: delete the glint tests in `tests/test_render.py` (`test_the_glint_blinks_...`, `test_the_sweeps_glint_is_at_the_foot`) and the telegraph test in `tests/test_poses.py` if any asserts 24-frame wind-ups; update `QUINT_FRAMES` startups in `tests/test_moves.py` (`stand.B` 13, `crouch.B` 13). Any fight test that hard-codes a heavy's old 24/28-frame startup reads it from the move (`TRIO.moves["stand.B"].startup`) instead.

- [ ] **Step 4: Run the suite.** `uv run pytest -q` → all pass. Then balance-check with bots (prints win counts; QUINT should win 40–60 %):

```bash
uv run python - <<'EOF'
from collections import Counter
from brawl_ket.bot import Bot
from brawl_ket.fight import Fight
from brawl_ket.moves import TRIO, QUINT
wins = Counter()
for seed in range(200):
    chars = {"p1": TRIO, "p2": QUINT} if seed % 2 else {"p1": QUINT, "p2": TRIO}
    f = Fight(chars); bots = {p: Bot(p, seed * 7 + i) for i, p in enumerate(("p1", "p2"))}
    while not f.over:
        f.step({p: b.input(f) for p, b in bots.items()})
    wins[f.fighters[f.winner].char.name if f.winner else "draw"] += 1
print(wins)
EOF
```

- [ ] **Step 5: Commit**

```bash
git add -A src/brawl_ket tests tools
git commit -m "tune: :control_knobs: Brawl-Ket: fast heavies, 25-point breaks that knock down, no telegraph"
```

---

### Task 5: The grid's effects, then the playtest checkpoint

**Files:**
- Modify: `src/brawl_ket/render.py`, `tools/snapshot.py`
- Test: `tests/test_render.py`

**Interfaces:**
- Consumes: `Event.kind == "cancel"`, `Event.row/col` (Task 2).
- Produces: `Renderer.pops: dict[str, list[tuple[int, int, int]]]` (per player: `(row, col, frames_left)`, `col == -1` for a whole row).

- [ ] **Step 1: Write the failing test** in `tests/test_render.py`:

```python
def test_a_cancel_pops_its_cell_white_on_the_tag(surface):
    from brawl_ket import shor
    from brawl_ket.render import CELL, CELL_GAP, PLATE
    r = Renderer(surface)
    fight = Fight({"p1": TRIO, "p2": TRIO})
    r.draw_fight(fight, [Event("cancel", "p2", shor.X, 400, 200, shor.MID, shor.B_COL)])
    assert r.pops["p2"] and r.pops["p2"][0][:2] == (shor.MID, shor.B_COL)
    surface.fill((0, 0, 0))
    r._code_tag("p2", fight.fighters["p2"], (160, 120, 160), 0, 0)
    left, top = 160 - PLATE // 2, 120 - PLATE // 2
    cell = (left + 4 + shor.B_COL * (CELL + CELL_GAP) + 3, top + 4 + shor.MID * (CELL + CELL_GAP) + 3)
    assert tuple(surface.get_at(cell))[:3] == P.WHITE
    for _ in range(30):
        r.draw_fight(fight, [])
    assert r.pops["p2"] == []
```

- [ ] **Step 2: Run to verify it fails.** `uv run pytest -q tests/test_render.py -k cancel_pops` → FAIL (`pops` missing).

- [ ] **Step 3: Implement.** In `render.py` add `POP_FRAMES = 12  # a cancelled light pops white this long`. In `_reset`: `self.pops: dict[str, list[tuple[int, int, int]]] = {p: [] for p in PLAYERS}`. In `_start_effects`, for `e.kind == "cancel"` and `e.player`: `self.pops[e.player].append((e.row, e.col if e.error == shor.X else -1, POP_FRAMES))`. In `_advance`: `self.pops = {p: [(r, c, n - 1) for r, c, n in v if n > 1] for p, v in self.pops.items()}`. In `_code_tag`, after a cell's colour is chosen and before it is drawn: if `(row, col)` is in this player's pops (or `(row, -1)` is), use `P.WHITE`. The logical red flash and the correction green flash already work through `self.flash`.

  In `tools/snapshot.py` add `fight_cancel.png`: a fight where p1 jabs twice at 50 px; save the frame of the second hit plus 2 frames. Add it to the docstring.

- [ ] **Step 4: Run** `uv run pytest -q` → all pass. Run the snapshot tool and look at `fight_cancel.png`, `code_tags.png`, `code_tags_quint.png`.

- [ ] **Step 5: Commit**

```bash
git add -A src/brawl_ket tests tools
git commit -m "feat: :sparkles: Brawl-Ket: cancelled lights pop white with an I"
```

- [ ] **Step 6: Playtest checkpoint.** Deploy (`./deploy_batocera.sh`) and ask the user to play a few rounds of each pairing on the cabinet. Write their notes down before Task 6; adjust Task 6–8 if they change the rules.

---

### Task 6: Bots read the grid

**Files:**
- Modify: `src/brawl_ket/bot.py`
- Test: `tests/test_bot.py`

**Interfaces:**
- Consumes: `ShorCode.x_cells`, `z_rows`, `x_danger_rows()`, `z_danger_rows()`; `Move.height`, `Move.column`.
- Produces: `Bot.plan_chain(rival) -> list[str]` (buttons) and `Bot.special_wanted(me, rival) -> bool`.

- [ ] **Step 1: Write the failing tests** in `tests/test_bot.py`:

```python
from brawl_ket import shor  # noqa: E402


def test_the_bot_finishes_a_row_with_the_other_button():
    fight = Fight({"p1": TRIO, "p2": TRIO})
    bot = Bot("p1", 1)
    rival = fight.fighters["p2"]
    rival.code.apply_x(shor.HIGH, shor.A_COL)
    assert bot.plan_chain(rival) == ["b"]          # standing B is HIGH, column B: a break
    rival.code.reset()
    rival.code.apply_x(shor.HIGH, shor.B_COL)
    assert bot.plan_chain(rival) == ["a"]
    rival.code.reset()
    assert bot.plan_chain(rival) == ["a", "b"]     # a clean grid: the classic break


def test_the_bot_fires_a_special_on_a_second_row():
    fight = Fight({"p1": TRIO, "p2": TRIO})
    bot = Bot("p1", 1)
    me, rival = fight.fighters["p1"], fight.fighters["p2"]
    assert not bot.special_wanted(me, rival)
    rival.code.apply_z(shor.LOW)                   # PHOTON (Z HIGH) would break it now
    assert bot.special_wanted(me, rival)


@pytest.mark.parametrize("pairing", PAIRINGS)
def test_bots_break_codes(pairing):
    breaks = 0
    for seed in SEEDS:
        fight, events = play(seed, pairing)
        breaks += sum(1 for e in events if e.kind == "logical")
    assert breaks >= len(SEEDS)
```

(`play`, `PAIRINGS`, `SEEDS` already exist in `tests/test_bot.py`; if `play` doesn't return events, make it return `(fight, events)` as `test_bots_are_deterministic` already expects.)

- [ ] **Step 2: Run to verify they fail.** `uv run pytest -q tests/test_bot.py -k "finishes or second_row or break_codes"` → FAIL.

- [ ] **Step 3: Implement** in `bot.py`:

```python
    def plan_chain(self, rival) -> list[str]:
        """Standing buttons that break the rival's code at HIGH (the standing normals'
        height): the other button on a row holding one X, or A then B on a clean row."""
        lit = {col for row, col in rival.code.x_cells if row == shor.HIGH}
        if lit == {shor.A_COL}:
            return ["b"]
        if lit == {shor.B_COL}:
            return ["a"]
        return ["a", "b"]

    def special_wanted(self, me, rival) -> bool:
        """A special whose Z row would break the rival's code (a flipped row elsewhere)."""
        m = me.char.moves["stand.X"]
        return m.kind != "reencode" and m.height in rival.code.z_danger_rows() \
            and me.cooldowns.get("stand.X", 0) == 0
```

In `_on_ground`, inside `if dist <= STRIKE_RANGE:` before the roll-based chain, add `if self.special_wanted(me, rival) and self.gap == 0: return self._press("x", 0)`, and replace the chain choice with `self.chain = self.plan_chain(rival)`. Keep crouching chains: when `self.down`, mirror `plan_chain` for `shor.LOW`. Add `from . import shor`.

- [ ] **Step 4: Run** `uv run pytest -q` → all pass, then rerun Task 4's balance script.

- [ ] **Step 5: Commit**

```bash
git add src/brawl_ket/bot.py tests/test_bot.py
git commit -m "feat: :robot: Brawl-Ket: bots read the grid and break codes"
```

---

### Task 7: Teaching: the rules card, the move list, the ROUND 1 hint

**Files:**
- Modify: `src/brawl_ket/match.py`, `src/brawl_ket/render.py`, `src/brawl_ket/config.py`, `tools/snapshot.py`
- Test: `tests/test_match.py`, `tests/test_render.py`

**Interfaces:**
- Consumes: `match.Match`, `render.Renderer.draw`.
- Produces: `Match.card: bool` (the title shows the rules card instead of the demo), `Match.hint: bool` (this round intro shows the hint); config `CARD_FRAMES = frames(8.0)`, `DEMO_FRAMES = frames(20.0)`; render constants `HINT = "A THEN B AT ONE HEIGHT BREAKS THE CODE"`, `CARD_LINES` (three strings).

- [ ] **Step 1: Write the failing tests.** In `tests/test_match.py`:

```python
def test_the_title_alternates_the_demo_and_the_rules_card() -> None:
    m = Match(random.Random(1))
    run(m, config.ATTRACT_DELAY + 1)
    assert m.attract is not None and not m.card
    run(m, config.DEMO_FRAMES)
    assert m.card and m.attract is None
    run(m, config.CARD_FRAMES)
    assert not m.card and m.attract is not None
    m.update(press("confirm"))
    assert not m.card and m.attract is None and m.state == TITLE


def test_only_a_matchs_first_round_intro_shows_the_hint() -> None:
    m = Match(random.Random(1))
    m.update(press("confirm"))
    m.update(press("confirm", "p1"))
    m.update(press("confirm", "p2"))
    assert m.state == ROUND_INTRO and m.hint
    run(m, config.ROUND_INTRO_FRAMES)
    m.fight.fighters["p2"].health = 0
    run(m, config.ROUND_END_FRAMES + 2)
    assert m.state == ROUND_INTRO and not m.hint
```

In `tests/test_render.py`:

```python
def test_the_card_hint_and_move_list_text_use_only_ascii():
    from brawl_ket.render import CARD_LINES, HINT
    for text in (HINT, *CARD_LINES):
        assert text.isascii() and text == text.upper()


def test_the_rules_card_draws(surface):
    import random
    from brawl_ket import config
    from brawl_ket import match as M
    r = Renderer(surface)
    m = M.Match(random.Random(1))
    for _ in range(config.ATTRACT_DELAY + config.DEMO_FRAMES + 30):
        r.draw(m, m.update(M.FrameInput()))
    assert m.card
```

- [ ] **Step 2: Run to verify they fail.** `uv run pytest -q tests/test_match.py tests/test_render.py -k "card or hint"` → FAIL.

- [ ] **Step 3: Implement.**
  - `config.py`: `DEMO_FRAMES = frames(20.0)    # the title's bot demo runs this long, then the rules card` and `CARD_FRAMES = frames(8.0)`.
  - `match.py`: `self.card = False`, `self.hint = False`, `self._title_phase = 0` (frames in the current demo or card). In `_on_title`, when `self.attract is not None or self.card`: any `inp.activity` stops both (`self.card = False`, `_stop_attract()`), else count `_title_phase`; after `DEMO_FRAMES` of demo switch to the card (`_stop_attract`, `card = True`), after `CARD_FRAMES` of card switch back (`card = False`, `_start_attract()`), resetting `_title_phase` each time. `_start_match` sets `self.hint = True`; `_start_round` is called from `_on_round_end` for later rounds, so set `self.hint = False` there before `_start_round`.
  - `render.py`:

```python
HINT = "A THEN B AT ONE HEIGHT BREAKS THE CODE"
CARD_LINES = ("SAME HIT TWICE: CANCELS", "A THEN B AT ONE HEIGHT: BREAK", "SPECIALS AT TWO HEIGHTS: BREAK")
```

    In `draw`, the TITLE branch: `if match.card: self._rules_card(match)` before the attract check. `_rules_card` draws `_backdrop()`, the small logo at the top (`self._logo(40, size=24)`), the title `HOW THE CODE WORKS` (16 px), and three rows, one per rule: a big grid (cells 16 px) on the left animating the rule (rule 1: one cell lights then goes dark; rule 2: A cell then B cell in one row, then the whole grid flashes red; rule 3: two rows glow blue, then red) and the rule's line on the right, each rule taking `CARD_FRAMES // 3` frames and the others shown dim. `_round_intro` blits `HINT` (8 px, `P.GOLD`) at `CALL_Y + 40` when `match.hint`, inside a band `self._band(CALL_Y - 26, CALL_Y + 52)`.
    The select panel's move list: each line is the input, the name and the error with its height, e.g. `X  PHOTON  Z HIGH`, built from `char.moves[slot]` (`shor.ROWS[m.height]`, and `"FIX ALL"` for `kind == "reencode"`); below the traits line add `"MIX A AND B AT ONE HEIGHT"`. Check every new string fits its panel at 8 px (296 px wide → at most 34 characters).
  - `tools/snapshot.py`: save `screen_card.png` (the card mid-rule 2) and `screen_round_hint.png`.

- [ ] **Step 4: Run** `uv run pytest -q` → all pass; look at `screen_card.png`, `screen_select.png`, `screen_round_hint.png`.

- [ ] **Step 5: Commit**

```bash
git add -A src/brawl_ket tests tools
git commit -m "feat: :teacher: Brawl-Ket: HOW THE CODE WORKS card, move list with heights, ROUND 1 hint"
```

---

### Task 8: Sound, docs, deploy

**Files:**
- Modify: `src/brawl_ket/audio.py`, `brawl-ket/README.md`, `batocera/gamelist.xml`
- Test: `tests/test_audio.py`

- [ ] **Step 1: Write the failing test** in `tests/test_audio.py`:

```python
def test_a_cancel_has_its_own_sound() -> None:
    assert audio.EVENT_SOUNDS["cancel"] == "cancel"
    assert "cancel" in audio.build_sfx()
    assert audio.sounds_for([Event("cancel", "p2", "X")]) == ["cancel"]
```

- [ ] **Step 2: Run** `uv run pytest -q tests/test_audio.py -k cancel` → FAIL.

- [ ] **Step 3: Implement.** In `build_sfx`: `"cancel": concat(tone(1320, 0.03, 0.18, "triangle"), tone(660, 0.06, 0.16, "triangle", decay=20))` (a falling two-note "undo"); in `EVENT_SOUNDS`: `"cancel": "cancel"`. Remove `"switch": None` from `EVENT_SOUNDS` (the event no longer exists) and update the comment.

  README: rewrite "The rules: a fighter is a code" and "The fighters" from the spec (sections 1–2): the grid, what deals what, cancel/break, the height triangle, both move lists with heights. Remove every mention of the repetition code, stance switching and telegraphs. `batocera/gamelist.xml`: Brawl-Ket's `<desc>` becomes "Two-player fighting game where every fighter is a Shor code: normal hits flip qubits, specials flip whole blocks, and hits that the decoder can't untangle land a logical error." (also on the cabinet's gamelist at the next deploy, with ES stopped, as in `../AGENTS.md`).

- [ ] **Step 4: Run** `uv run pytest -q` → all pass; `uv run python tools/benchmark.py` → mean under 2 ms.

- [ ] **Step 5: Commit, deploy, benchmark on the Pi**

```bash
git add -A src/brawl_ket tests README.md ../batocera/gamelist.xml
git commit -m "feat: :sound: Brawl-Ket: a cancel sound; README and menu text for the Shor rules"
./deploy_batocera.sh
scp tools/benchmark.py root@batocera.local:/tmp/brawl_benchmark.py
ssh root@batocera.local "python3 /tmp/brawl_benchmark.py /userdata/games/brawl_ket"
```

Expected on the Pi: worst frame under 8 ms.

---

### Task 9: Tuning (driven by playtests)

No fixed code. Expect rounds of: startups, chip and break damage, cycle lengths, the GRAB's reach, COLLAPSE's drift, the DIVE's fall speed, bot habits. Keep `tests/test_shor.py` untouched (it is the physics) and every other test green; when a number moves, update its test table in the same commit (`tune: :control_knobs: Brawl-Ket: ...`).
