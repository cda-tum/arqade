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
