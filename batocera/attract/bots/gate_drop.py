"""Gate Drop: a 2-player versus where both players place every pill to cancel.

Sets P1 to level 3 and P2 to level 4 (so the two boards get different error
layouts), both at MED speed, and plays the match, rematching when it ends.
For each new pill a player tries every column and rotation it can reach,
runs the board's own settle-and-cancel rules on a copy of the grid for each,
and looks one pill ahead (the NEXT pill) the same way. It scores errors
fixed and gates cancelled, against a tall stack and errors buried under gates
that don't cancel them. Chains, and the T gates they send across, come
naturally from that; chasing them on purpose flooded both boards with T's.
Then it turns the pill, steers it over and soft-drops it, a beat after it
appears, like a quick human.
"""

from gate_drop import board as gd
from gate_drop import config
from gate_drop.match import MATCH_RESULT, ROUND, SETUP, TITLE

SECONDS = 85.0
SKIP = 3.1
# 2 s windows, best first: chains, FIXED!s and a CNOT on both boards (4.3),
# 2-chains both ways (55.1), both boards clearing (15.0), the full layouts of
# round 3 being worked (49.0), round 2 clears (36.0), T gates traded (63.8),
# an H pair chaining (7.6), round 2 clears on both sides (33.1).
HIGHLIGHTS = [4.3, 55.1, 15.0, 49.0, 36.0, 63.8, 7.6, 33.1]

LEVELS = {"p1": 3, "p2": 4}  # different levels: different error layouts
SPEED = "MED"
PLAYERS = ("p1", "p2")
THINK = 0.15  # seconds before a new pill starts moving


def copy_grid(grid):
    g = gd.Grid(grid.cols, grid.rows)
    g.cells = [row[:] for row in grid.cells]
    return g


def resolve(grid):
    """Settle and cancel until nothing moves, as the board does after a pill
    locks. Returns (errors fixed, matches)."""
    errors = matches = 0
    while True:
        while gd.settle_step(grid):
            pass
        found = gd.find_matches(grid)
        if not found:
            return errors, matches
        matches += len(found)
        errors += gd.apply_matches(grid, found)[1]


def shape(grid):
    """How healthy a board looks: short stacks, errors not buried."""
    score = 0.0
    for x in range(grid.cols):
        wire = [grid.cells[y][x] for y in range(grid.rows) if grid.cells[y][x] is not None]  # top down
        if not wire:
            continue
        top = next(y for y in range(grid.rows) if grid.cells[y][x] is not None)
        height = grid.rows - top
        score -= 6.0 * height + (60.0 * (height - 8) ** 2 if height > 8 else 0.0)
        covering = 0
        for c in wire:
            if isinstance(c, gd.Gate) and c.error:
                score -= 70.0 * covering  # a buried error
                covering = 0
            else:
                covering += 1
    return score


def placements(grid, piece, x0, y0, rot0):
    """Every (rot, x, landed cells) the piece can reach from (x0, y0, rot0):
    turn first (with the board's one-cell wall kick), then slide, then drop."""
    def fits(x, y, rot):
        return all(grid.free(p) for p, _ in piece.cells(x, y, rot))

    rots = (0, 2) if piece.is_cnot else (0, 1, 2, 3)
    out = []
    for rot in rots:
        x, r = x0, rot0
        ok = True
        turns = (rot - rot0) % 4
        step = 2 if piece.is_cnot else (1 if turns <= 2 else -1)
        while r != rot and ok:
            r2 = (r + step) % 4
            for kx in (x, x - 1):
                if fits(kx, y0, r2) and fits(kx, y0 + 1, r2):
                    x, r = kx, r2
                    break
            else:
                ok = False
        if not ok:
            continue
        for tx in range(-1, grid.cols):
            cx, path_ok = x, True
            while cx != tx:
                cx += 1 if tx > cx else -1
                if not (fits(cx, y0, rot) and fits(cx, y0 + 1, rot)):
                    path_ok = False
                    break
            if not path_ok:
                continue
            y = y0
            while fits(tx, y + 1, rot):
                y += 1
            out.append((rot, tx, piece.cells(tx, y, rot)))
    return out


def outcome(grid, cells):
    """Lock `cells` into a copy of `grid` and resolve. None if it tops out."""
    if any(y < 0 for (_, y), _ in cells):
        return None
    g = copy_grid(grid)
    for pos, half in cells:
        g.set(pos, half)
    errors, matches = resolve(g)
    return g, 1000.0 * errors + 120.0 * matches


class Bot:
    def __init__(self, pads, rng):
        self.pads, self.rng = pads, rng
        self.last_press = -10.0
        self.plans = {}  # player -> (pill id, target rot, target x, when it appeared)

    def update(self, t):
        match = self.pads.loop.get("match")
        if match is None:
            return
        if match.state == ROUND and not match.paused:
            for i, p in enumerate(PLAYERS):
                self.drive(i, match.boards[p], t)
            return
        for i in (0, 1):
            self.pads.stick(i, 0.0, 0.0)
        self.plans = {}
        even = self.pads.frame % 2 == 0
        if match.paused:  # never meant to happen; B resumes
            self.press(0, "b", t)
        elif match.state == TITLE:
            if match.mode != 2:
                self.pads.stick(0, 1.0 if even else 0.0, 0.0)
            else:
                self.press(0, "a", t)
        elif match.state == SETUP and even:
            for i, p in enumerate(PLAYERS):
                s = match.setups[p]
                if s.ready:
                    continue
                if s.row == 0 and s.level != LEVELS[p]:
                    self.pads.stick(i, 1.0 if s.level < LEVELS[p] else -1.0, 0.0)
                elif s.row == 1 and s.speed != SPEED:
                    want = config.SPEEDS.index(SPEED)
                    self.pads.stick(i, 1.0 if config.SPEEDS.index(s.speed) < want else -1.0, 0.0)
                elif s.row == 0 and s.speed != SPEED:
                    self.pads.stick(i, 0.0, 1.0)
                else:
                    self.pads.tap(i, "a", 1)
        elif match.state == MATCH_RESULT:
            self.press(0, "a", t)

    def press(self, player, button, t):
        if t - self.last_press > 0.5:
            self.pads.tap(player, button, 1)
            self.last_press = t

    # --- playing ------------------------------------------------------------------

    def drive(self, i, board, t):
        piece = board.piece
        if piece is None or board.phase != "fall":
            self.pads.stick(i, 0.0, 0.0)
            return
        pill = piece.halves[0].pill
        plan = self.plans.get(i)
        if plan is None or plan[0] != pill:
            rot, x = self.plan(board, piece)
            plan = self.plans[i] = (pill, rot, x, t)
        _, rot, x, since = plan
        if t - since < THINK:
            self.pads.stick(i, 0.0, 0.0)
            return
        even = self.pads.frame % 2 == 0
        if piece.rot != rot:
            self.pads.stick(i, 0.0, 0.0)
            if even:
                turns = (rot - piece.rot) % 4
                self.pads.tap(i, "b" if turns == 3 else "a", 1)
        elif piece.x != x:
            self.pads.stick(i, (1.0 if x > piece.x else -1.0) if even else 0.0, 0.0)
        else:
            self.pads.stick(i, 0.0, 1.0)  # soft drop

    def plan(self, board, piece):
        grid = board.grid
        best, best_score = (piece.rot, piece.x), None
        nxt = board.next
        for rot, x, cells in placements(grid, piece, piece.x, piece.y, piece.rot):
            first = outcome(grid, cells)
            if first is None:
                continue
            g1, reward = first
            # One pill ahead: the best the NEXT pill can do from its spawn.
            follow = None
            spawn = gd.Piece(nxt.halves, config.SPAWN_X, 0)
            for _, _, cells2 in placements(g1, spawn, spawn.x, spawn.y, spawn.rot):
                second = outcome(g1, cells2)
                if second is None:
                    continue
                g2, reward2 = second
                value = 0.8 * reward2 + shape(g2)
                if follow is None or value > follow:
                    follow = value
            if follow is None:
                follow = shape(g1) - 5000.0
            score = reward + follow + self.rng.uniform(-25.0, 25.0)
            if best_score is None or score > best_score:
                best, best_score = (rot, x), score
        return best
