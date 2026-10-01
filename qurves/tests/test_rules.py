import random

import pytest

from qurves import config, rules
from qurves.rules import PlayerInput, Trail

UP, DOWN, LEFT, RIGHT = (0, -1), (0, 1), (-1, 0), (1, 0)


class PickRng:
    """Stands in for random.Random wherever a rule picks a branch at random."""

    def __init__(self, index):
        self.index = index
        self.calls = 0

    def choice(self, seq):
        self.calls += 1
        return seq[self.index]


def state_with(p1=((20, 42), RIGHT), p2=((139, 42), LEFT)):
    """A round with no pickups and the two bikes wherever a test wants them."""
    arena = rules.Arena()
    players = {}
    for name, (pos, heading) in (("p1", p1), ("p2", p2)):
        arena.set(pos, Trail(name, None))
        players[name] = rules.Player(name, [rules.Bike(pos, heading, prev=pos)])
    return rules.RoundState(arena, players)


def step(state, rng=None, **inputs):
    return rules.tick(state, inputs, rng or random.Random(0))


def go(direction=None, split=False):
    return PlayerInput(direction, split)


def split_p1(state):
    """Split p1 right away (meter topped up), return the player."""
    state.players["p1"].meter = 100.0
    step(state, p1=go(split=True))
    return state.players["p1"]


# --- geometry ---------------------------------------------------------------------


def test_turn_helpers_follow_screen_coordinates():
    assert rules.left_of(RIGHT) == UP
    assert rules.right_of(RIGHT) == DOWN
    assert rules.left_of(UP) == LEFT
    assert rules.right_of(UP) == RIGHT


def test_mirror_keeps_the_axis_component_and_flips_the_other():
    assert rules.mirror(UP, RIGHT) == DOWN
    assert rules.mirror(RIGHT, RIGHT) == RIGHT
    assert rules.mirror(LEFT, UP) == RIGHT
    assert rules.mirror(DOWN, UP) == DOWN


# --- a new round ----------------------------------------------------------------------


def test_new_round_layout():
    s = rules.new_round(random.Random(1))
    p1, p2 = s.players["p1"], s.players["p2"]
    assert (p1.bikes[0].pos, p1.bikes[0].heading) == ((20, 42), RIGHT)
    assert (p2.bikes[0].pos, p2.bikes[0].heading) == ((139, 42), LEFT)
    for wall in [(0, 10), (config.GRID_W - 1, 10), (50, 0), (50, config.GRID_H - 1), (-1, 5)]:
        assert s.arena.get(wall) == rules.WALL
    assert s.arena.get((50, 50)) is None
    assert s.arena.get((20, 42)) == Trail("p1", None)
    assert len(s.pickups) == config.MAX_PICKUPS
    assert all(pl.meter == 0.0 and pl.alive for pl in s.players.values())


def test_pickups_spawn_on_empty_cells_away_from_the_heads():
    for seed in range(20):
        s = rules.new_round(random.Random(seed))
        for c in s.pickups:
            assert s.arena.get(c) is None
            for pl in s.players.values():
                h = pl.bikes[0].pos
                assert max(abs(c[0] - h[0]), abs(c[1] - h[1])) >= config.PICKUP_MIN_DIST


# --- moving and crashing ------------------------------------------------------------


def test_a_bike_moves_one_cell_and_leaves_solid_trail():
    s = state_with()
    events = step(s)
    bike = s.players["p1"].bikes[0]
    assert bike.pos == (21, 42) and bike.prev == (20, 42)
    assert s.arena.get((21, 42)) == Trail("p1", None)
    assert rules.Moved("p1", None, (20, 42), (21, 42)) in events


def test_steering_turns_and_reversing_is_ignored():
    s = state_with()
    step(s, p1=go(LEFT))
    assert s.players["p1"].bikes[0].pos == (21, 42)
    step(s, p1=go(UP))
    assert s.players["p1"].bikes[0].pos == (21, 41)


def test_driving_into_a_wall_loses_the_round():
    s = state_with(p1=((1, 10), LEFT))
    events = step(s)
    assert not s.players["p1"].alive
    assert s.over and s.winner == "p2"
    assert rules.RoundOver("p2") in events


def test_driving_into_any_solid_trail_crashes():
    for owner in ("p1", "p2"):  # the opponent's trail, and your own
        s = state_with()
        s.arena.set((21, 42), Trail(owner, None))
        step(s)
        assert not s.players["p1"].alive


def test_head_on_into_the_same_cell_is_a_draw():
    s = state_with(p1=((10, 10), RIGHT), p2=((12, 10), LEFT))
    events = step(s)
    assert s.over and s.winner is None
    assert rules.RoundOver(None) in events


def test_swapping_cells_is_a_draw():
    s = state_with(p1=((10, 10), RIGHT), p2=((11, 10), LEFT))
    step(s)
    assert s.over and s.winner is None


def test_nothing_happens_after_the_round_is_over():
    s = state_with(p1=((1, 10), LEFT))
    step(s)
    assert step(s) == []
    assert rules.advance(s, 1.0, random.Random(0)) == []


# --- splitting ----------------------------------------------------------------------


def test_splitting_needs_half_a_meter():
    s = state_with()
    s.players["p1"].meter = 49.9
    step(s, p1=go(split=True))
    assert not s.players["p1"].is_split

    s = state_with()
    s.players["p1"].meter = 50.0
    events = step(s, p1=go(split=True))
    assert s.players["p1"].is_split
    assert rules.Split("p1", (20, 42)) in events


def test_the_split_forks_left_and_right_of_the_heading():
    s = state_with()
    s.players["p1"].meter = 50.0
    step(s, p1=go(RIGHT, split=True))  # steering is ignored on the split tick
    c0, c1 = s.players["p1"].bikes
    assert (c0.branch, c0.pos, c0.heading) == (0, (20, 41), UP)
    assert (c1.branch, c1.pos, c1.heading) == (1, (20, 43), DOWN)
    assert s.arena.get((20, 41)) == Trail("p1", 0)
    assert s.arena.get((20, 43)) == Trail("p1", 1)
    assert s.players["p1"].split_axis == RIGHT


def test_you_cannot_split_twice():
    s = state_with()
    pl = split_p1(s)
    step(s, p1=go(split=True))
    assert len(pl.bikes) == 2


def test_copy_one_steers_mirrored_across_the_split_axis():
    s = state_with()
    pl = split_p1(s)  # copies at (20, 41) heading up and (20, 43) heading down
    step(s, p1=go(RIGHT))
    assert [b.heading for b in pl.bikes] == [RIGHT, RIGHT]
    step(s, p1=go(UP))
    assert [b.heading for b in pl.bikes] == [UP, DOWN]
    assert [b.pos for b in pl.bikes] == [(21, 40), (21, 44)]


def test_mirroring_across_a_vertical_split_axis():
    s = state_with(p1=((50, 50), UP))
    pl = split_p1(s)
    assert [b.heading for b in pl.bikes] == [LEFT, RIGHT]
    step(s, p1=go(UP))
    assert [b.heading for b in pl.bikes] == [UP, UP]
    step(s, p1=go(LEFT))
    assert [b.heading for b in pl.bikes] == [LEFT, RIGHT]


def test_a_copy_cannot_reverse_either():
    s = state_with()
    pl = split_p1(s)
    step(s, p1=go(DOWN))  # the reverse of copy 0; mirrored, also the reverse of copy 1
    assert [b.heading for b in pl.bikes] == [UP, DOWN]


def test_your_two_copies_pass_through_each_other():
    s = state_with()
    pl = split_p1(s)
    step(s, p1=go(RIGHT))  # (21, 41) and (21, 43)
    step(s, p1=go(DOWN))  # both enter (21, 42)
    step(s, p1=go(DOWN))  # and drive on through each other's ghost cells
    assert pl.alive and pl.is_split
    assert [b.pos for b in pl.bikes] == [(21, 43), (21, 41)]


# --- how a superposition ends ------------------------------------------------------


def test_a_copy_crashes_into_its_own_branch():
    s = state_with()
    pl = split_p1(s)
    s.arena.set((20, 40), Trail("p1", 0))  # right in front of copy 0
    events = step(s)
    assert len(pl.bikes) == 1 and pl.bikes[0].pos == (20, 44)
    collapse = next(e for e in events if isinstance(e, rules.Collapse))
    assert collapse.reason == "crash"


def test_losing_a_copy_dissolves_its_trail_and_solidifies_the_other():
    s = state_with(p1=((20, 3), RIGHT))
    pl = split_p1(s)  # copies at (20, 2) and (20, 4)
    step(s)  # (20, 1) and (20, 5)
    events = step(s)  # copy 0 hits the top wall
    assert pl.alive and not pl.is_split
    survivor = pl.bikes[0]
    assert survivor.branch is None and survivor.pos == (20, 6)
    for c in [(20, 2), (20, 1)]:
        assert s.arena.get(c) is None
    for c in [(20, 3), (20, 4), (20, 5), (20, 6)]:
        assert s.arena.get(c) == Trail("p1", None)
    collapse = next(e for e in events if isinstance(e, rules.Collapse))
    assert collapse.reason == "crash"
    assert set(collapse.dissolved) == {(20, 2), (20, 1)}
    assert collapse.solidified == ((20, 3), (20, 4), (20, 5))
    assert any(isinstance(e, rules.Crash) and e.branch == 0 for e in events)


def test_both_copies_crashing_on_one_tick_loses_the_round():
    s = state_with(p1=((20, 1), RIGHT))
    s.players["p1"].meter = 100.0
    s.arena.set((20, 2), Trail("p2", None))
    step(s, p1=go(split=True))  # forks into the top wall and into p2's trail
    assert not s.players["p1"].alive
    assert s.winner == "p2"


def test_measurement_collapses_onto_the_untouched_branch():
    s = state_with(p2=((22, 41), LEFT))
    pl = split_p1(s)  # copies at (20, 41) and (20, 43); p2 moved to (21, 41)
    events = step(s)  # p2 drives into copy 0's ghost cell (20, 41)
    assert not pl.is_split
    assert pl.bikes[0].pos == (20, 44)
    assert rules.Measured("p1", "p2", (20, 41)) in events
    assert any(isinstance(e, rules.Collapse) and e.reason == "measurement" for e in events)
    assert s.arena.get((20, 41)) == Trail("p2", None)  # p2 drove on through
    assert s.arena.get((20, 40)) is None  # copy 0 never got there
    assert s.players["p2"].alive


def test_measuring_both_branches_at_once_collapses_at_random():
    s = state_with(p1=((30, 10), RIGHT), p2=((32, 10), LEFT))
    for pl in s.players.values():
        pl.meter = 100.0
    rng = PickRng(0)
    step(s, rng, p1=go(split=True), p2=go(split=True))
    # p1's copies: (30, 9) up, (30, 11) down. p2's: (32, 11) down, (32, 9) up.
    step(s, rng, p2=go(LEFT))  # p2's copies turn left: (31, 11) and (31, 9)
    step(s, rng, p2=go(LEFT))  # and enter both of p1's ghost cells at once
    p1 = s.players["p1"]
    assert not p1.is_split
    assert rng.calls == 1
    assert p1.bikes[0].pos == (30, 7)  # branch 0 was picked; it kept going up


def test_heads_count_as_trail_of_their_kind():
    s = state_with(p1=((10, 10), RIGHT), p2=((13, 11), LEFT))
    s.players["p2"].meter = 100.0
    step(s, p2=go(split=True))  # p1 to (11, 10); p2's copies (13, 12) down and (13, 10) up
    step(s, p2=go(LEFT))  # p1 and p2's copy 1 both enter (12, 10)
    p1, p2 = s.players["p1"], s.players["p2"]
    # p1 met a ghost head: a measurement, it passes. The ghost met a solid head: a crash.
    assert p1.alive and p1.bikes[0].pos == (12, 10)
    assert p2.alive and not p2.is_split
    assert p2.bikes[0].pos == (12, 12)


def test_a_crash_is_applied_before_a_measurement_on_the_same_tick():
    s = state_with(p1=((20, 2), RIGHT), p2=((22, 3), LEFT))
    pl = split_p1(s)  # copies at (20, 1) and (20, 3); p2 to (21, 3)
    events = step(s)  # copy 0 hits the wall while p2 enters copy 1's ghost cell
    reasons = [e.reason for e in events if isinstance(e, rules.Collapse)]
    assert reasons == ["crash"]
    assert pl.alive and pl.bikes[0].pos == (20, 4)


def test_the_meter_drains_while_split_and_decoheres_at_zero():
    s = state_with()
    pl = split_p1(s)  # meter 100
    rules.advance(s, 1.5, PickRng(1))
    assert pl.meter == pytest.approx(75.0) and pl.is_split
    events = rules.advance(s, 4.5, PickRng(1))
    assert pl.meter == 0.0 and not pl.is_split
    assert pl.bikes[0].pos == (20, 43)  # branch 1 survived
    assert any(isinstance(e, rules.Collapse) and e.reason == "decoherence" for e in events)


def test_the_meter_does_not_drain_when_not_split():
    s = state_with()
    s.players["p1"].meter = 60.0
    rules.advance(s, 10.0, random.Random(0))
    assert s.players["p1"].meter == 60.0


# --- pickups --------------------------------------------------------------------------


def test_pickups_add_half_a_meter_capped_at_full():
    s = state_with()
    s.pickups = [(21, 42), (22, 42), (23, 42)]
    events = step(s)
    assert s.players["p1"].meter == 50.0
    assert rules.PickedUp("p1", (21, 42)) in events
    step(s)
    step(s)
    assert s.players["p1"].meter == 100.0
    assert s.pickups == []
    assert s.respawns == [config.PICKUP_RESPAWN] * 3


def test_a_copy_collects_pickups_too():
    s = state_with()
    pl = split_p1(s)
    pl.meter = 60.0
    s.pickups = [(20, 40)]
    step(s)
    assert pl.meter == 100.0


def test_a_pickup_respawns_after_two_seconds():
    s = state_with()
    s.respawns = [config.PICKUP_RESPAWN]
    rules.advance(s, 1.9, random.Random(0))
    assert s.pickups == []
    rules.advance(s, 0.2, random.Random(0))
    assert len(s.pickups) == 1 and s.respawns == []
