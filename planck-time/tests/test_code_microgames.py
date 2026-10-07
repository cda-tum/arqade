"""The rules TILE! and MERGE! need beyond the shared contract: TILE!'s colourings are
real colour-code colourings with a unique answer for every blank, and MERGE! has
exactly one winning way to merge. Both are checked at every appearance."""

import pytest

from planck_time.microgames import PlayerInput
from planck_time.microgames import merge as M
from planck_time.microgames import tile as T
from planck_time.microgames.merge import Merge
from planck_time.microgames.tile import Tile

DT = 1 / 60
SEEDS = range(60)
APPEARANCES = (0, 1, 2, 3)


def run(game, policy, until=None):
    frames = round((until or game.duration) / DT)
    for _ in range(frames):
        game.update(DT, policy(game))
        if game.result is not None:
            break
    return game.result


# --- TILE! ------------------------------------------------------------------------------


def test_the_colouring_is_a_colour_code_colouring():
    # neighbouring tiles always differ, and every corner of the honeycomb where three tiles
    # meet touches one tile of each colour
    for seed in SEEDS:
        for app in APPEARANCES:
            game = Tile.spawn(seed, 0, Tile.duration_for(0), app)
            for tile, colour in game.colours.items():
                for n in T.neighbours(tile):
                    if n in game.colours:
                        assert game.colours[n] != colour, (seed, app, tile, n)
            for a in game.colours:
                for b in T.neighbours(a):
                    for c in T.neighbours(b):
                        if c in T.neighbours(a) and {a, b, c} <= set(game.colours):
                            assert {game.colours[t] for t in (a, b, c)} == {0, 1, 2}


def test_every_blank_has_exactly_one_answer():
    for seed in SEEDS:
        for app in APPEARANCES:
            game = Tile.spawn(seed, 0, Tile.duration_for(0), app)
            for blank in game.blanks:
                seen = {game.colours[n] for n in T.neighbours(blank)
                        if n in game.colours and n not in game.blanks}
                assert len(seen) == 2, (seed, app, blank, seen)     # so the third is forced
                assert {0, 1, 2} - seen == {game.colours[blank]}


def test_the_blanks_by_appearance():
    for seed in SEEDS:
        first = Tile.spawn(seed, 0, Tile.duration_for(0), 0)
        assert len(first.blanks) == 1 and T.inside(first.blanks[0], first.cells) == 6
        second = Tile.spawn(seed, 0, Tile.duration_for(0), 1)
        a, b = second.blanks
        assert len(second.blanks) == 2 and b not in T.neighbours(a)
        later = Tile.spawn(seed, 0, Tile.duration_for(0), 2)
        assert any(T.inside(t, later.cells) in (3, 4) for t in later.blanks)


def test_tile_input_waits_for_the_first_moment():
    game = Tile(0, 0, Tile.duration_for(0))
    run(game, lambda g: PlayerInput(a=True), until=0.55)
    assert game.result is None and not game.painted


def test_painting_the_wrong_colour_fails_and_the_right_one_wins():
    for seed in range(10):
        game = Tile(seed, 0, Tile.duration_for(0))
        game.t = T.READY
        blank = game.blanks[0]
        wrong = next(c for c in range(3) if c != game.colours[blank])
        game.cursor = wrong
        game.update(DT, PlayerInput(a=True))
        assert game.result is False
        game = Tile(seed, 0, Tile.duration_for(0))
        game.t = T.READY
        game.cursor = game.colours[blank]
        game.update(DT, PlayerInput(a=True))
        assert game.result is True


@pytest.mark.parametrize("app", APPEARANCES)
def test_tile_bot_wins_and_idle_loses_at_every_appearance(app):
    for seed in range(20):
        for level in (0, 3):
            game = Tile.spawn(seed, level, Tile.duration_for(level), app)
            assert run(game, lambda g: g.bot()) is True, (seed, level)
            game = Tile.spawn(seed, level, Tile.duration_for(level), app)
            if run(game, lambda g: PlayerInput()) is None:
                game.timeout()
            assert game.result is False


# --- MERGE! -----------------------------------------------------------------------------


def test_opposite_edges_match_and_neighbouring_edges_differ():
    for rot in (0, 1):
        edges = M.edges(rot)
        assert edges["left"] == edges["right"] and edges["top"] == edges["bottom"]
        assert edges["left"] != edges["top"]
    assert M.edges(0)["left"] != M.edges(1)["left"]     # a quarter turn swaps the facing type


@pytest.mark.parametrize("app", APPEARANCES)
def test_exactly_one_way_to_merge_wins(app):
    for seed in SEEDS:
        game = Merge.spawn(seed, 0, Merge.duration_for(0), app)
        wins = [(rot, lane) for rot in (0, 1) for lane in range(len(game.fixed))
                if game.wins(rot, lane)]
        assert len(wins) == 1, (seed, app, wins)
        if app >= 1:
            assert len(game.fixed) == 2 and game.fixed[0] != game.fixed[1]
            assert game.order in ("X", "Z")
        else:
            assert len(game.fixed) == 1 and game.order is None


def test_merge_input_waits_for_the_first_moment():
    game = Merge(0, 0, Merge.duration_for(0))
    run(game, lambda g: PlayerInput(step=(-1, 0), a=True), until=0.55)
    assert game.result is None and game.spins == 0 and not game.pushed


def test_pushing_in_on_a_mismatch_fails():
    for seed in SEEDS:
        game = Merge(seed, 0, Merge.duration_for(0))
        game.t = M.READY
        if game.wins(game.rot, game.lane):
            game.update(DT, PlayerInput(a=True))       # spin to the mismatch
            run(game, lambda g: PlayerInput(), until=M.SPIN + 0.05)
        game.update(DT, PlayerInput(step=(-1, 0)))
        assert run(game, lambda g: PlayerInput(), until=1.5) is False, seed


@pytest.mark.parametrize("app", APPEARANCES)
def test_merge_bot_wins_and_idle_loses_at_every_appearance(app):
    for seed in range(20):
        for level in (0, 3):
            game = Merge.spawn(seed, level, Merge.duration_for(level), app)
            assert run(game, lambda g: g.bot()) is True, (seed, level)
            game = Merge.spawn(seed, level, Merge.duration_for(level), app)
            if run(game, lambda g: PlayerInput()) is None:
                game.timeout()
            assert game.result is False


def test_the_label_is_the_joint_measurement():
    for seed in range(10):
        game = Merge(seed, 0, Merge.duration_for(0))
        assert game.label() == game.fixed[0] * 2      # XX along X edges, ZZ along Z edges


def drawn_stabilisers(rot, phase):
    """The stabilisers as drawn: (type, set of qubits), qubits (column, row) on the vertices."""
    out = []
    for i in range(M.FACES):
        for j in range(M.FACES):
            out.append((M.face_type(i, j, rot, phase), {(i, j), (i + 1, j), (i, j + 1), (i + 1, j + 1)}))
    for side, k, kind in M.moons(rot, phase):
        if side == "left":
            q = {(0, k), (0, k + 1)}
        elif side == "right":
            q = {(M.D - 1, k), (M.D - 1, k + 1)}
        elif side == "top":
            q = {(k, 0), (k + 1, 0)}
        else:
            q = {(k, M.D - 1), (k + 1, M.D - 1)}
        out.append((kind, q))
    return out


def edge_qubits(side):
    n = M.D - 1
    return {"left": {(0, j) for j in range(M.D)}, "right": {(n, j) for j in range(M.D)},
            "top": {(i, 0) for i in range(M.D)}, "bottom": {(i, n) for i in range(M.D)}}[side]


@pytest.mark.parametrize("rot", (0, 1))
@pytest.mark.parametrize("phase", (0, 1))
def test_the_drawn_patch_is_a_surface_code_with_litinskis_edges(rot, phase):
    stabs = drawn_stabilisers(rot, phase)
    # the stabilisers commute: an X and a Z one overlap on an even number of qubits
    for ka, qa in stabs:
        for kb, qb in stabs:
            if ka != kb:
                assert len(qa & qb) % 2 == 0
    # a distance-5 rotated code: 25 qubits, 24 stabilisers (12 of each type), so one logical qubit
    assert len(stabs) == M.D * M.D - 1 and sum(k == "X" for k, _ in stabs) == 12
    edges = M.edges(rot)
    # Litinski: the product of X (Z) along a dashed X (solid Z) edge is the logical X (Z)
    logical = {}
    for side, kind in edges.items():
        string = edge_qubits(side)
        for k, q in stabs:
            if k != kind:
                assert len(q & string) % 2 == 0, (side, kind)   # commutes with every stabiliser
        logical.setdefault(kind, string)
    assert len(logical["X"] & logical["Z"]) % 2 == 1            # X_L and Z_L anticommute


def test_merged_patches_continue_the_checkerboard_across_the_seam():
    for kind in ("X", "Z"):
        rot = 0 if kind == "X" else 1           # the fixed patch, and yours when the edges match
        for j in range(M.FACES):
            fixed = M.face_type(M.FACES - 1, j, rot, 0)
            yours = M.face_type(0, j, rot, M.YOUR_PHASE)
            assert fixed == yours                # so the seam face between them differs from both
