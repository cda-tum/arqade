"""One player's board: a small quantum circuit with gate pills falling onto it.

Pure Python, no pygame, so every rule is unit tested (tests/test_board.py).

The board is COLS wires (columns) by ROWS rows, with row 0 at the top. Each
column is one qubit wire, and the gates stacked on it are that qubit's
circuit. Cancellation only ever happens along a wire. Each wire is read from
the bottom up, skipping empty cells, because an idle stretch of wire is the
identity. A CNOT half is an item too, and nothing cancels across it, since
there is no commuting.

Board.update() runs the falling pill and, after it locks, the resolve
sequence: settle everything unsupported a row at a time, find the matches,
flash them, clear them, settle again, and so on until nothing matches. Then
any incoming noise drops, and the next pill spawns.
"""

from __future__ import annotations

import random
from dataclasses import dataclass

from gate_drop import config

Pos = tuple[int, int]


@dataclass(frozen=True)
class Gate:
    """A single-qubit gate. error=True marks one of the round's Pauli errors,
    anchored in place. pill is set while the gate is still joined to the
    other half of the pill it came in (for drawing them as one capsule)."""

    kind: str
    error: bool = False
    pill: int | None = None


@dataclass(frozen=True)
class Cnot:
    """One half of a CNOT: role "c" (control) or "t" (target). The two halves
    share a pill id and always sit side by side, at the same height."""

    pill: int
    role: str


# Where a pill's two halves sit relative to its pivot (its lower-left cell)
# in each rotation. Turning clockwise takes the first half from the left to
# the top, to the right, to the bottom. A CNOT only uses 0 and 2.
ROTATIONS = {0: ((0, 0), (1, 0)), 1: ((0, -1), (0, 0)), 2: ((1, 0), (0, 0)), 3: ((0, 0), (0, -1))}
SANDWICH = {"X": "Z", "Z": "X"}  # H X H = Z and H Z H = X


@dataclass
class Piece:
    halves: tuple  # (first half, second half): two Gates or two Cnots
    x: int
    y: int
    rot: int = 0

    @property
    def is_cnot(self) -> bool:
        return isinstance(self.halves[0], Cnot)

    def cells(self, x: int | None = None, y: int | None = None, rot: int | None = None) -> list:
        x = self.x if x is None else x
        y = self.y if y is None else y
        offsets = ROTATIONS[self.rot if rot is None else rot]
        return [((x + dx, y + dy), half) for (dx, dy), half in zip(offsets, self.halves)]


@dataclass(frozen=True)
class PlayerInput:
    move: int = 0  # -1 left, 1 right (already auto-repeated)
    cw: bool = False
    ccw: bool = False
    soft: bool = False  # held: soft drop


@dataclass(frozen=True)
class Event:
    kind: str
    cells: tuple[Pos, ...] = ()
    value: int = 0


@dataclass(frozen=True)
class Match:
    kind: str  # "pair", "sandwich" or "cnot"
    removed: tuple[Pos, ...]
    rewrite: tuple[Pos, str] | None = None  # the sandwiched gate and its new kind

    @property
    def cells(self) -> tuple[Pos, ...]:
        return self.removed + ((self.rewrite[0],) if self.rewrite else ())


class Grid:
    def __init__(self, cols: int = config.COLS, rows: int = config.ROWS) -> None:
        self.cols, self.rows = cols, rows
        self.cells: list[list] = [[None] * cols for _ in range(rows)]

    def get(self, p: Pos):
        x, y = p
        if 0 <= x < self.cols and 0 <= y < self.rows:
            return self.cells[y][x]
        return None

    def set(self, p: Pos, value) -> None:
        self.cells[p[1]][p[0]] = value

    def free(self, p: Pos) -> bool:
        """Can a falling pill occupy p? The rows above the top are free (the
        spawn chute); the side walls and the floor are not."""
        x, y = p
        if not 0 <= x < self.cols or y >= self.rows:
            return False
        return y < 0 or self.cells[y][x] is None

    def items(self):
        for y in range(self.rows):
            for x in range(self.cols):
                c = self.cells[y][x]
                if c is not None:
                    yield (x, y), c


def random_piece(rng: random.Random, pill: int) -> Piece:
    if rng.random() < config.CNOT_SHARE:
        halves = (Cnot(pill, "c"), Cnot(pill, "t"))
    else:
        halves = (Gate(rng.choice(config.GATE_KINDS), pill=pill), Gate(rng.choice(config.GATE_KINDS), pill=pill))
    return Piece(halves, config.SPAWN_X, 0)


# --- cancellation ----------------------------------------------------------------------


def _wire(grid: Grid, x: int) -> list:
    """A wire's items from the bottom up, skipping gaps: [(y, cell), ...]."""
    return [(y, grid.cells[y][x]) for y in range(grid.rows - 1, -1, -1) if grid.cells[y][x] is not None]


def _cnot_pair(grid: Grid, x: int, lower: tuple, upper: tuple) -> Match | None:
    """Two CNOT halves directly stacked on wire x: do the whole CNOTs cancel?"""
    (y0, c0), (y1, c1) = lower, upper
    if not (isinstance(c0, Cnot) and isinstance(c1, Cnot)) or c0.pill == c1.pill or c0.role != c1.role:
        return None
    for dx in (1, -1):
        p0, p1 = grid.get((x + dx, y0)), grid.get((x + dx, y1))
        if isinstance(p0, Cnot) and p0.pill == c0.pill and isinstance(p1, Cnot) and p1.pill == c1.pill:
            if all(grid.get((x + dx, y)) is None for y in range(y1 + 1, y0)):
                return Match("cnot", ((x, y0), (x + dx, y0), (x, y1), (x + dx, y1)))
            return None
    return None


def find_matches(grid: Grid) -> list[Match]:
    """Every match on the board, scanning each wire from the bottom: at each
    position a sandwich first, then a pair. Matches never overlap."""
    matches: list[Match] = []
    taken: set[Pos] = set()
    for x in range(grid.cols):
        seq = _wire(grid, x)
        i = 0
        while i < len(seq):
            y0, c0 = seq[i]
            if (x, y0) in taken:
                i += 1
                continue
            if i + 2 < len(seq):
                (y1, c1), (y2, c2) = seq[i + 1], seq[i + 2]
                if (_is_h(c0) and _is_h(c2) and isinstance(c1, Gate) and c1.kind in SANDWICH
                        and not {(x, y1), (x, y2)} & taken):
                    matches.append(Match("sandwich", ((x, y0), (x, y2)), ((x, y1), SANDWICH[c1.kind])))
                    taken |= {(x, y0), (x, y1), (x, y2)}
                    i += 3
                    continue
            if i + 1 < len(seq):
                y1, c1 = seq[i + 1]
                if (x, y1) not in taken:
                    if isinstance(c0, Gate) and isinstance(c1, Gate) and c0.kind == c1.kind:
                        matches.append(Match("pair", ((x, y0), (x, y1))))
                        taken |= {(x, y0), (x, y1)}
                        i += 2
                        continue
                    m = _cnot_pair(grid, x, seq[i], seq[i + 1])
                    if m is not None and not set(m.removed) & taken:
                        matches.append(m)
                        taken |= set(m.removed)
                        i += 2
                        continue
            i += 1
    return matches


def _is_h(c) -> bool:
    return isinstance(c, Gate) and c.kind == "H"


def apply_matches(grid: Grid, matches: list[Match]) -> tuple[list[Pos], int]:
    """Clear the matches. Returns (every cell that changed, errors cleared)."""
    changed: list[Pos] = []
    errors = 0
    for m in matches:
        for p in m.removed:
            c = grid.get(p)
            if isinstance(c, Gate) and c.error:
                errors += 1
            grid.set(p, None)
            changed.append(p)
        if m.rewrite is not None:
            p, kind = m.rewrite
            old = grid.get(p)
            grid.set(p, Gate(kind, error=old.error))
            changed.append(p)
    _fix_joins(grid)
    return changed, errors


# --- settling -------------------------------------------------------------------------


def settle_step(grid: Grid) -> list[tuple[Pos, Pos]]:
    """Move everything unsupported down one row. Rows are processed from the
    bottom up, so a whole stack falls together. Loose gates fall alone, a
    CNOT falls only when both of its halves can, and errors never move."""
    moves: list[tuple[Pos, Pos]] = []
    for y in range(grid.rows - 2, -1, -1):
        for x in range(grid.cols):
            c = grid.cells[y][x]
            if c is None:
                continue
            if isinstance(c, Gate):
                if not c.error and grid.cells[y + 1][x] is None:
                    grid.cells[y + 1][x], grid.cells[y][x] = c, None
                    moves.append(((x, y), (x, y + 1)))
            elif x + 1 < grid.cols and isinstance(grid.cells[y][x + 1], Cnot) and grid.cells[y][x + 1].pill == c.pill:
                if grid.cells[y + 1][x] is None and grid.cells[y + 1][x + 1] is None:
                    grid.cells[y + 1][x], grid.cells[y][x] = c, None
                    grid.cells[y + 1][x + 1], grid.cells[y][x + 1] = grid.cells[y][x + 1], None
                    moves += [((x, y), (x, y + 1)), ((x + 1, y), (x + 1, y + 1))]
    _fix_joins(grid)
    return moves


def _fix_joins(grid: Grid) -> None:
    """A pill half whose partner is gone, or no longer next to it, is loose."""
    for (x, y), c in list(grid.items()):
        if isinstance(c, Gate) and c.pill is not None:
            near = (grid.get(q) for q in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)))
            if not any(isinstance(n, Gate) and n.pill == c.pill for n in near):
                grid.set((x, y), Gate(c.kind, c.error))


# --- the board --------------------------------------------------------------------------


class Board:
    def __init__(self, errors: list[tuple[Pos, str]], seed: int) -> None:
        self.grid = Grid()
        for pos, kind in errors:
            self.grid.set(pos, Gate(kind, error=True))
        self.rng = random.Random(seed)  # pills only, so both boards get the same ones
        self.noise_rng = random.Random(seed + 1)
        self._pill = 0
        self.piece: Piece | None = None
        self.next = self._new_piece()
        self.phase = "spawn"  # spawn, fall, settle, flash or over
        self.timer = 0.0
        self.fall_timer = 0.0
        self.fall_interval = config.FALL_START
        self.chain = 0
        self.big_pass = False
        self.pending: list[Match] = []
        self.noise_queue: list[str] = []
        self.noise_dropped = False
        self.outgoing = 0  # noise gates to send to the opponent (the match collects them)
        self.topped_out = False

    def _new_piece(self) -> Piece:
        self._pill += 1
        return random_piece(self.rng, self._pill)

    def errors_left(self) -> int:
        return sum(1 for _, c in self.grid.items() if isinstance(c, Gate) and c.error)

    def stack_top(self) -> int:
        """The highest occupied row (ROWS if the board is empty)."""
        for y in range(self.grid.rows):
            if any(c is not None for c in self.grid.cells[y]):
                return y
        return self.grid.rows

    def update(self, dt: float, inp: PlayerInput = PlayerInput()) -> list[Event]:
        events: list[Event] = []
        if self.topped_out:
            return events
        if self.phase == "spawn":
            self._spawn(events)
        elif self.phase == "fall":
            self._fall(dt, inp, events)
        elif self.phase == "flash":
            self.timer -= dt
            if self.timer <= 0:
                self._clear(events)
        elif self.phase == "settle":
            self.timer -= dt
            while self.phase == "settle" and self.timer <= 0:
                self._resolve_step(events)
        return events

    # --- the falling pill ---------------------------------------------------------------

    def _fits(self, piece: Piece, x: int | None = None, y: int | None = None, rot: int | None = None) -> bool:
        return all(self.grid.free(p) for p, _ in piece.cells(x, y, rot))

    def _spawn(self, events: list[Event]) -> None:
        self.piece, self.next = self.next, self._new_piece()
        if not self._fits(self.piece):
            self.piece = None
            self._top_out(events)
            return
        self.phase = "fall"
        self.fall_timer = 0.0
        events.append(Event("spawn"))

    def _fall(self, dt: float, inp: PlayerInput, events: list[Event]) -> None:
        piece = self.piece
        if inp.move and self._fits(piece, x=piece.x + inp.move):
            piece.x += inp.move
            events.append(Event("move"))
        for turn, pressed in ((1, inp.cw), (-1, inp.ccw)):
            if pressed:
                self._rotate(turn, events)
        interval = config.SOFT_DROP_INTERVAL if inp.soft else self.fall_interval
        self.fall_timer += dt
        while self.fall_timer >= interval:
            self.fall_timer -= interval
            if self._fits(piece, y=piece.y + 1):
                piece.y += 1
            else:
                self._lock(events)
                return

    def _rotate(self, turn: int, events: list[Event]) -> None:
        piece = self.piece
        rot = (piece.rot + 2) % 4 if piece.is_cnot else (piece.rot + turn) % 4
        for x in (piece.x, piece.x - 1):  # in place, else a one-cell wall kick to the left
            if self._fits(piece, x=x, rot=rot):
                piece.x, piece.rot = x, rot
                events.append(Event("rotate"))
                return

    def _lock(self, events: list[Event]) -> None:
        cells = self.piece.cells()
        self.piece = None
        if any(y < 0 for (_, y), _ in cells):
            self._top_out(events)
            return
        for pos, half in cells:
            self.grid.set(pos, half)
        events.append(Event("land", tuple(pos for pos, _ in cells)))
        self.phase = "settle"
        self.timer = 0.0
        self.chain = 0
        self.big_pass = False

    def _top_out(self, events: list[Event]) -> None:
        self.topped_out = True
        self.phase = "over"
        events.append(Event("topout"))

    # --- resolving ----------------------------------------------------------------------

    def _resolve_step(self, events: list[Event]) -> None:
        moves = settle_step(self.grid)
        if moves:
            events.append(Event("settle", tuple(to for _, to in moves)))
            self.timer += config.SETTLE_STEP
            return
        matches = find_matches(self.grid)
        if matches:
            self.chain += 1
            self.big_pass |= len(matches) >= config.BIG_PASS
            self.pending = matches
            self.phase = "flash"
            self.timer = config.CLEAR_TIME
            events.append(Event("flash", tuple(c for m in matches for c in m.cells), self.chain))
            return
        if self.chain:
            sent = min(config.MAX_ATTACK, self.chain - 1) + (1 if self.big_pass else 0)
            events.append(Event("chain", value=self.chain))
            if sent:
                self.outgoing += sent
                events.append(Event("attack", value=sent))
            self.chain = 0
            self.big_pass = False
        if self.noise_queue and not self.noise_dropped:
            self.noise_dropped = True
            self._drop_noise(events)
            self.timer += config.SETTLE_STEP
            return
        self.noise_dropped = False
        self.phase = "spawn"
        self._spawn(events)

    def _clear(self, events: list[Event]) -> None:
        changed, errors = apply_matches(self.grid, self.pending)
        self.pending = []
        events.append(Event("clear", tuple(changed), self.chain))
        if errors:
            events.append(Event("errors", value=errors))
        self.phase = "settle"
        self.timer = config.SETTLE_STEP

    def _drop_noise(self, events: list[Event]) -> None:
        """Up to one noise gate per wire, into the top row, on distinct wires."""
        count = min(len(self.noise_queue), self.grid.cols)
        landed = []
        for x in self.noise_rng.sample(range(self.grid.cols), count):
            kind = self.noise_queue.pop(0)
            if self.grid.get((x, 0)) is None:
                self.grid.set((x, 0), Gate(kind))
                landed.append((x, 0))
        events.append(Event("noise", tuple(landed)))
