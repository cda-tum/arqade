import random

from gate_drop import config
from gate_drop.board import (
    Board, Cnot, Gate, Grid, Piece, PlayerInput, apply_matches, attack_size, find_matches,
    random_piece, settle_step,
)

B = config.ROWS - 1  # the bottom row


def grid_from(*rows):
    """The bottom rows of a board, listed top to bottom: '.' empty, H X Y Z T
    gates, D a T-dagger, x y z errors, c and t a CNOT's control and target
    (each paired with the t or c right next to it)."""
    g = Grid()
    top = config.ROWS - len(rows)
    pill = 100
    for dy, row in enumerate(rows):
        y, x = top + dy, 0
        while x < len(row):
            ch = row[x]
            if ch in "HXYZT":
                g.set((x, y), Gate(ch))
            elif ch == "D":
                g.set((x, y), Gate("Td"))
            elif ch in "xyz":
                g.set((x, y), Gate(ch.upper(), error=True))
            elif ch in "ct":
                g.set((x, y), Cnot(pill, ch))
                g.set((x + 1, y), Cnot(pill, row[x + 1]))
                pill += 1
                x += 1
            x += 1
    return g


def column(g, x):
    """A wire's contents from the bottom up, as letters (errors lower-case)."""
    out = []
    for y in range(config.ROWS - 1, -1, -1):
        c = g.get((x, y))
        if isinstance(c, Gate):
            out.append("D" if c.kind == "Td" else c.kind.lower() if c.error else c.kind)
        elif isinstance(c, Cnot):
            out.append(c.role)
    return "".join(out)


def settle_all(g):
    while settle_step(g):
        pass


def resolve(g):
    """Run every match pass to the end, settling between, as the board does."""
    passes = 0
    settle_all(g)
    while (matches := find_matches(g)):
        apply_matches(g, matches)
        settle_all(g)
        passes += 1
    return passes


# --- what cancels -------------------------------------------------------------------------


def test_two_identical_gates_on_a_wire_cancel():
    for kind in "HXYZ":
        g = grid_from(kind + ".....", kind + ".....")
        assert [m.kind for m in find_matches(g)] == ["pair"]
        resolve(g)
        assert column(g, 0) == ""


def test_t_cancels_with_t_dagger_but_not_with_itself():
    assert [m.kind for m in find_matches(grid_from("T.....", "D....."))] == ["pair"]
    assert [m.kind for m in find_matches(grid_from("D.....", "T....."))] == ["pair"]
    assert find_matches(grid_from("T.....", "T.....")) == []  # T T = S, not the identity
    assert find_matches(grid_from("D.....", "D.....")) == []


def test_t_and_t_dagger_are_rarer_than_the_other_gates():
    rng = random.Random(0)
    counts = {}
    for i in range(3000):
        piece = random_piece(rng, i)
        if not piece.is_cnot:
            for half in piece.halves:
                counts[half.kind] = counts.get(half.kind, 0) + 1
    assert set(counts) == set(config.GATE_KINDS)
    assert counts["T"] < 0.3 * counts["H"] and counts["Td"] < 0.3 * counts["X"]


def test_attack_sizes():
    # A 2-step chain (or one pass with 3+ matches) sends 2 T gates, a 3-step
    # chain 3; a big pass inside a chain adds one; never more than 4.
    assert attack_size(1, False) == 0
    assert attack_size(1, True) == 2
    assert attack_size(2, False) == 2
    assert attack_size(2, True) == 3
    assert attack_size(3, False) == 3
    assert attack_size(6, True) == config.MAX_ATTACK


def test_an_x_on_a_control_clears_an_x_under_each_half_of_the_cnot():
    # CNOT then X on the control = X on both wires, then CNOT (error propagation).
    g = grid_from("X.....", "ct....", "Xx....")
    assert [m.kind for m in find_matches(g)] == ["propagate"]
    _, errors = apply_matches(g, find_matches(g))
    assert errors == 1
    resolve(g)
    assert column(g, 0) == "c" and column(g, 1) == "t"  # the CNOT stays


def test_a_z_on_a_target_clears_a_z_under_each_half():
    g = grid_from(".Z....", "ct....", "Zz....")
    assert [m.kind for m in find_matches(g)] == ["propagate"]


def test_propagation_works_whichever_way_round_and_across_gaps():
    assert [m.kind for m in find_matches(grid_from(".X....", "tc....", "XX...."))] == ["propagate"]
    assert [m.kind for m in find_matches(grid_from("X.....", "ct....", ".x....", "X....."))] == ["propagate"]


def test_propagation_needs_the_right_gate_on_the_right_half_and_a_full_pair():
    assert find_matches(grid_from("X.....", "ct....", "XZ....")) == []  # only one side matches
    assert find_matches(grid_from(".X....", "ct....", "XX....")) == []  # X on the target passes through
    assert find_matches(grid_from("Z.....", "ct....", "ZZ....")) == []  # Z on the control too


def test_different_gates_or_different_wires_do_not_cancel():
    assert find_matches(grid_from("X.....", "Z.....")) == []
    assert find_matches(grid_from("XX....")) == []


def test_gaps_on_a_wire_are_skipped():
    assert [m.kind for m in find_matches(grid_from("X.....", "......", "X....."))] == ["pair"]


def test_a_gate_clears_a_matching_error():
    g = grid_from("Y.....", "y.....")
    changed, errors = apply_matches(g, find_matches(g))
    assert errors == 1 and column(g, 0) == ""


def test_an_h_sandwich_turns_x_into_z_and_z_into_x():
    g = grid_from("H.....", "X.....", "H.....")
    resolve(g)
    assert column(g, 0) == "Z"
    g = grid_from("H.....", "Z.....", "H.....")
    resolve(g)
    assert column(g, 0) == "X"


def test_h_y_h_changes_nothing():
    assert find_matches(grid_from("H.....", "Y.....", "H.....")) == []


def test_a_sandwiched_error_stays_an_error():
    g = grid_from("H.....", "x.....", "H.....")
    _, errors = apply_matches(g, find_matches(g))
    assert errors == 0
    assert column(g, 0) == "z"


def test_wires_are_scanned_from_the_bottom_without_overlap():
    g = grid_from("X.....", "X.....", "X.....")
    matches = find_matches(g)
    assert len(matches) == 1 and matches[0].removed == ((0, B), (0, B - 1))
    g = grid_from("H.....", "H.....", "X.....", "H.....")  # bottom up: H X H H
    resolve(g)
    assert column(g, 0) == "ZH"


def test_nothing_cancels_across_a_cnot():
    assert find_matches(grid_from("X.....", "ct....", "X.....")) == []


def test_two_stacked_cnots_cancel():
    g = grid_from("ct....", "ct....")
    assert [m.kind for m in find_matches(g)] == ["cnot"]
    resolve(g)
    assert column(g, 0) == column(g, 1) == ""


def test_cnots_cancel_across_a_gap_but_not_across_a_gate_or_when_flipped():
    assert [m.kind for m in find_matches(grid_from("ct....", "......", "ct...."))] == ["cnot"]
    assert find_matches(grid_from("ct....", ".X....", "ct....")) == []
    assert find_matches(grid_from("tc....", "ct....")) == []


# --- settling -----------------------------------------------------------------------------


def test_a_loose_gate_falls_one_row_per_step():
    g = grid_from("X.....", "......", "......")
    assert settle_step(g) == [((0, B - 2), (0, B - 1))]
    assert settle_step(g) == [((0, B - 1), (0, B))]
    assert settle_step(g) == []


def test_a_stack_falls_together():
    g = grid_from("X.....", "Z.....", "......")
    assert len(settle_step(g)) == 2
    assert column(g, 0) == "ZX" and isinstance(g.get((0, B)), Gate)


def test_errors_never_fall():
    g = grid_from("x.....", "......")
    assert settle_step(g) == []


def test_a_cnot_falls_rigidly_and_bridges_a_gap():
    g = grid_from("ct....", "......")
    settle_all(g)
    assert isinstance(g.get((0, B)), Cnot) and isinstance(g.get((1, B)), Cnot)
    g = grid_from("ct....", "X.....")  # held up by its left half
    assert settle_step(g) == []
    assert g.get((1, B)) is None


def test_halves_that_end_up_apart_come_unjoined():
    g = Grid()
    g.set((0, B - 2), Gate("X", pill=7))
    g.set((1, B - 2), Gate("Z", pill=7))
    g.set((0, B - 1), Gate("Y"))
    g.set((0, B), Gate("Z"))
    settle_all(g)
    assert g.get((0, B - 2)) == Gate("X")
    assert g.get((1, B)) == Gate("Z")


# --- the board ----------------------------------------------------------------------------


def make_board(errors=(), piece=None):
    b = Board(list(errors), seed=1)
    b.update(0.0, PlayerInput())  # spawns the first pill
    if piece is not None:
        b.piece = piece
    return b


def run(b, seconds, inp=PlayerInput(), dt=1 / 60):
    events = []
    for _ in range(round(seconds / dt)):
        events += b.update(dt, inp)
    return events


def drop(b):
    """Soft-drop the current pill, then let everything resolve until the next
    pill is falling (without touching it)."""
    events = []
    for _ in range(2000):
        if any(e.kind == "land" for e in events):
            break
        events += b.update(1 / 60, PlayerInput(soft=True))
    for _ in range(2000):
        if b.phase in ("fall", "over"):
            break
        events += b.update(1 / 60, PlayerInput())
    return events


def test_the_first_pill_spawns_lying_flat_over_the_middle_wires():
    b = make_board()
    assert b.phase == "fall"
    assert [pos for pos, _ in b.piece.cells()] == [(2, 0), (3, 0)]


def test_moving_stops_at_the_walls():
    b = make_board()
    for _ in range(5):
        b.update(0.0, PlayerInput(move=-1))
    assert b.piece.x == 0
    for _ in range(9):
        b.update(0.0, PlayerInput(move=1))
    assert b.piece.x == config.COLS - 2


def test_rotating_cycles_through_four_orientations():
    piece = Piece((Gate("X", pill=9), Gate("Z", pill=9)), 2, 5)
    b = make_board(piece=piece)
    seen = []
    for _ in range(4):
        b.update(0.0, PlayerInput(cw=True))
        seen.append([pos for pos, _ in b.piece.cells()])
    assert seen == [[(2, 4), (2, 5)], [(3, 5), (2, 5)], [(2, 5), (2, 4)], [(2, 5), (3, 5)]]


def test_rotating_against_the_right_wall_kicks_left():
    piece = Piece((Gate("X", pill=9), Gate("Z", pill=9)), config.COLS - 1, 5, rot=1)
    b = make_board(piece=piece)
    b.update(0.0, PlayerInput(cw=True))
    assert (b.piece.x, b.piece.rot) == (config.COLS - 2, 2)


def test_a_cnot_only_swaps_its_sides():
    piece = Piece((Cnot(9, "c"), Cnot(9, "t")), 2, 5)
    b = make_board(piece=piece)
    b.update(0.0, PlayerInput(cw=True))
    assert [half.role for _, half in sorted(b.piece.cells())] == ["t", "c"]


def test_gravity_and_soft_drop():
    b = make_board()
    run(b, b.fall_interval + 0.01)
    assert b.piece.y == 1
    run(b, 0.2, PlayerInput(soft=True))
    assert b.piece.y >= 4


def test_a_landed_pill_locks_and_the_next_one_spawns():
    b = make_board(piece=Piece((Gate("Y", pill=9), Gate("Z", pill=9)), 2, 0))
    events = drop(b)
    assert any(e.kind == "land" for e in events)
    assert b.grid.get((2, B)) == Gate("Y", pill=9) and b.grid.get((3, B)) == Gate("Z", pill=9)
    assert b.piece is not None and b.phase == "fall"


def test_a_pill_that_cancels_clears_after_a_flash():
    b = make_board(errors=[((2, B), "X")], piece=Piece((Gate("Z", pill=9), Gate("X", pill=9)), 2, 0, rot=1))
    events = drop(b)
    kinds = [e.kind for e in events]
    assert "flash" in kinds and "clear" in kinds and "errors" in kinds
    assert b.errors_left() == 0
    assert column(b.grid, 2) == "Z"  # the top half fell into place


def test_a_two_step_chain_sends_two_noise_gates():
    b = make_board(piece=Piece((Gate("Z", pill=9), Gate("X", pill=9)), 0, 0, rot=1))
    b.grid.set((0, B), Gate("Z"))
    b.grid.set((0, B - 1), Gate("X"))
    events = drop(b)  # X lands on X; then the Z on top falls onto the Z
    assert [e.value for e in events if e.kind == "chain"] == [2]
    assert b.outgoing == 2
    assert column(b.grid, 0) == ""


def test_incoming_noise_drops_after_the_pill_locks():
    b = make_board(piece=Piece((Gate("Y", pill=9), Gate("Y", pill=9)), 2, 0))
    b.noise_queue = ["X", "Z"]
    events = drop(b)
    noise = [e for e in events if e.kind == "noise"]
    assert len(noise) == 1 and len({x for x, _ in noise[0].cells}) == 2
    assert b.noise_queue == []


def test_blocked_spawn_cells_top_out():
    b = Board([], seed=1)
    b.grid.set((2, 0), Gate("X"))
    events = b.update(0.0, PlayerInput())
    assert b.topped_out and [e.kind for e in events] == ["topout"]


def test_errors_left_and_stack_top():
    b = make_board(errors=[((0, B), "X"), ((5, B - 3), "Z")])
    assert b.errors_left() == 2
    assert b.stack_top() == B - 3  # the falling pill doesn't count
    assert Board([], seed=1).stack_top() == config.ROWS


def test_two_boards_with_the_same_seed_get_the_same_pills():
    a, b = Board([], seed=5), Board([], seed=5)
    for _ in range(5):
        assert a.next.halves == b.next.halves
        a.next, b.next = a._new_piece(), b._new_piece()
