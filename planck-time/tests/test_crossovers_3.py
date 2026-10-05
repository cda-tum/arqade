"""The rules CORRECT!, ROUTE! and MATCH! need beyond the shared contract:
fair timing for a first-time player, and ROUTE!'s rival route always standing
in the way without ever cutting the pair off."""

import pytest

from planck_time.microgames import PlayerInput
from planck_time.microgames import correct as C
from planck_time.microgames import route as R
from planck_time.microgames.correct import Correct
from planck_time.microgames.match import Match
from planck_time.microgames.route import Route, bfs

DT = 1 / 60
SEEDS = range(100)


# --- CORRECT! -------------------------------------------------------------------------------


def windows(game, until):
    """The (start, end) times the ship's colour matches the invader, up to `until`."""
    out, t, start = [], 0.0, None
    while t < until:
        on = game.color_at(t) == game.kind
        if on and start is None:
            start = t
        if not on and start is not None:
            out.append((start, t))
            start = None
        t += 0.001
    return out


def test_correct_level_0_is_fair():
    for seed in SEEDS:
        game = Correct(seed, 0, Correct.duration_for(0))
        assert game.beat >= 0.5  # every colour, the matching one too, lasts at least 0.5 s
        reach = (C.THRESHOLD - C.EH / 2 - C.SPAWN_Y) / game.vy  # when it hits the threshold
        assert reach >= 6 * game.beat  # two whole cycles of X, Z, Y
        found = windows(game, reach)
        assert found[0][0] >= 0.6, f"seed {seed}"
        assert len(found) >= 2, f"seed {seed}"
        assert abs(game.inv_x - game.ship_x) >= 40  # you have to move to get under it


@pytest.mark.parametrize("level", (0, 3))
def test_correct_has_two_chances_at_every_level(level):
    for seed in SEEDS:
        game = Correct(seed, level, Correct.duration_for(level))
        reach = (C.THRESHOLD - C.EH / 2 - C.SPAWN_Y) / game.vy
        assert len(windows(game, reach)) >= 2, f"seed {seed}"


def aim_and_fire(game, when_matching: bool):
    """Track the invader like the bot does, and fire once the colour does (or doesn't) match."""
    while game.result is None and game.t < game.duration:
        inp = game.bot()
        match = game.color == game.kind
        if game.t > C.BOT_THINK and abs(inp.stick[0]) < 0.4 and match == when_matching and game.shot is None:
            inp = PlayerInput(stick=inp.stick, a=True)
        else:
            inp = PlayerInput(stick=inp.stick)
        game.update(DT, inp)
    return game.result


def test_correct_a_wrong_colour_shot_that_hits_fails():
    for seed in range(20):
        game = Correct(seed, 0, Correct.duration_for(0))
        assert aim_and_fire(game, when_matching=False) is False
        assert game.how == "wrong", f"seed {seed}"


def test_correct_a_shot_that_misses_just_flies_off():
    game = Correct(0, 0, Correct.duration_for(0))
    game.update(DT, PlayerInput(a=True))  # the ship starts well to one side of the invader
    while game.shot is not None:
        game.update(DT, PlayerInput())
    assert game.result is None


# --- ROUTE! ---------------------------------------------------------------------------------


@pytest.mark.parametrize("level", range(5))
def test_route_the_rival_is_in_the_way_but_never_cuts_the_pair_off(level):
    layouts = set()
    for seed in SEEDS:
        game = Route(seed, level, Route.duration_for(level))
        rival = set(game.rival)
        assert game.start not in rival and game.partner not in rival
        free = bfs(game.start, game.partner, lambda m: game.inside(m) and m not in rival)
        assert free is not None, f"seed {seed}"
        direct = abs(game.start[0] - game.partner[0]) + abs(game.start[1] - game.partner[1])
        assert direct < len(free) - 1 <= R.MAX_STEPS[min(level, 3)], f"seed {seed}"
        layouts.add((game.start, game.partner, tuple(game.rival)))
    assert len(layouts) >= 50  # a different chip nearly every time


def route_from_start(game, step):
    game.update(game.lay + DT, PlayerInput())
    game.update(DT, PlayerInput(step=step))


def test_route_waits_for_the_rival_to_be_laid():
    game = Route(1, 0, Route.duration_for(0))
    free = next(d for d in ((1, 0), (-1, 0), (0, 1), (0, -1))
                if game.inside((game.start[0] + d[0], game.start[1] + d[1])))
    game.update(DT, PlayerInput(step=free))
    assert game.path == [game.start]
    assert game.lay >= 0.6  # level 0: the first move is at least 0.6 s in


def test_route_stepping_onto_the_rival_route_is_a_collision():
    for seed in range(40):
        game = Route(seed, 0, Route.duration_for(0))
        # walk the free route up to the rival, then step onto it
        rival = set(game.rival)
        head = game.start
        def ok(m, n):
            return game.inside(m) and m != game.partner and (m not in rival or m == n)

        target = next(n for n in sorted(rival) if bfs(game.start, n, lambda m: ok(m, n)))
        way = bfs(game.start, target, lambda m: ok(m, target))
        game.update(game.lay + DT, PlayerInput())
        for nxt in way[1:]:
            game.update(DT, PlayerInput(step=(nxt[0] - head[0], nxt[1] - head[1])))
            head = nxt
        assert game.result is False and game.crash == target, f"seed {seed}"


def test_route_pushing_back_the_way_it_came_undoes_a_step():
    game = Route(2, 0, Route.duration_for(0))
    rival = set(game.rival)
    d = next(d for d in ((1, 0), (-1, 0), (0, 1), (0, -1))
             if game.inside(n := (game.start[0] + d[0], game.start[1] + d[1])) and n not in rival)
    route_from_start(game, d)
    assert len(game.path) == 2
    game.update(DT, PlayerInput(step=(-d[0], -d[1])))
    assert game.path == [game.start] and game.result is None


# --- MATCH! ---------------------------------------------------------------------------------


def test_match_level_0_never_switches_faster_than_0_4_s():
    for seed in SEEDS:
        game = Match(seed, 0, Match.duration_for(0))
        times = [0.0] + game.switches
        assert game.switches[0] >= 0.6  # the first matching moment
        assert min(b - a for a, b in zip(times, times[1:])) >= 0.4, f"seed {seed}"
        assert game.basis_at(0.0) != game.mine


@pytest.mark.parametrize("level", (0, 3))
def test_match_has_two_chances(level):
    for seed in SEEDS:
        game = Match(seed, level, Match.duration_for(level))
        chances = game.switches[0::2]  # every other switch turns the rival into your colour
        assert len(chances) >= 2, f"seed {seed}"


def test_match_a_strike_is_judged_when_a_is_pressed():
    for seed in range(20):
        hit = Match(seed, 0, Match.duration_for(0))
        while hit.basis_at(hit.t) != hit.mine:
            hit.update(DT, PlayerInput())
        hit.update(DT, PlayerInput(a=True))
        assert hit.result is True
        blocked = Match(seed, 0, Match.duration_for(0))
        blocked.update(DT, PlayerInput(a=True))  # the rival starts in the other colour
        assert blocked.result is False
