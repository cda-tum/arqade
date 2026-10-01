import random

import pytest

from qurves import config, rules
from qurves.rules import Gate, Trail

UP, DOWN, LEFT, RIGHT = (0, -1), (0, 1), (-1, 0), (1, 0)
W = config.GRID_W


class PickRng(random.Random):
    """A seeded random.Random whose choice() always picks seq[index], for the
    rules that pick a copy at random."""

    def __init__(self, index):
        super().__init__(0)
        self.index = index
        self.calls = 0

    def choice(self, seq):
        self.calls += 1
        return list(seq)[self.index]


def state_with(**players):
    """A round with no gates and bikes wherever a test wants them.
    Defaults to the two-player starting positions."""
    players = players or {"p1": ((20, 42), RIGHT), "p2": ((139, 42), LEFT)}
    arena = rules.Arena()
    built = {}
    for name, (pos, heading) in players.items():
        arena.set(pos, Trail(name, None))
        built[name] = rules.Player(name, [rules.Bike(pos, heading, prev=pos)])
    return rules.RoundState(arena, built)


def step(state, rng=None, **directions):
    return rules.tick(state, directions, rng or random.Random(0))


def gate_ahead(state, name, kind, bike=0):
    """Put a gate right on the next cell of one of `name`'s bikes."""
    b = state.players[name].bikes[bike]
    state.gates.append(Gate(kind, rules.add(b.pos, b.heading)))


def split_p1(state):
    """Drive p1 into an H gate, then through the fork tick. Returns the player."""
    gate_ahead(state, "p1", "H")
    step(state)
    step(state)
    return state.players["p1"]


# --- geometry ---------------------------------------------------------------------------


def test_turn_helpers_follow_screen_coordinates():
    assert rules.left_of(RIGHT) == UP and rules.right_of(RIGHT) == DOWN
    assert rules.left_of(UP) == LEFT and rules.right_of(UP) == RIGHT


def test_a_split_reflects_steering_across_the_heading():
    assert rules.reflect_flip((1, 1), RIGHT) == (1, -1)  # horizontal axis: flip up/down
    assert rules.reflect_flip((1, 1), UP) == (-1, 1)  # vertical axis: flip left/right
    assert rules.reflect_flip((1, -1), UP) == (-1, -1)
    assert rules.steer(UP, (1, -1)) == DOWN
    assert rules.steer(RIGHT, (-1, 1)) == LEFT


# --- a new round ------------------------------------------------------------------------


@pytest.mark.parametrize("mode", config.MODES)
def test_new_round_layout(mode):
    s = rules.new_round(random.Random(1), config.PLAYERS_BY_MODE[mode])
    assert set(s.players) == set(config.PLAYERS_BY_MODE[mode])
    for name, (pos, heading) in config.START[mode].items():
        bike = s.players[name].bikes[0]
        assert (bike.pos, bike.heading) == (pos, heading)
        assert s.arena.get(pos) == Trail(name, None)
    for wall in [(0, 10), (W - 1, 10), (50, 0), (50, config.GRID_H - 1), (-1, 5)]:
        assert s.arena.get(wall) == rules.WALL
    assert len(s.gates) == config.MAX_GATES[mode]


def test_gates_spawn_on_empty_cells_away_from_heads_and_each_other():
    for seed in range(20):
        s = rules.new_round(random.Random(seed), config.PLAYERS_BY_MODE[4])
        heads = [pl.bikes[0].pos for pl in s.players.values()]
        for g in s.gates:
            assert g.kind in config.GATE_WEIGHTS
            assert s.arena.get(g.pos) is None
            assert all(rules.dist(g.pos, h) >= config.GATE_MIN_DIST for h in heads)
            assert all(rules.dist(g.pos, o.pos) >= config.GATE_GAP for o in s.gates if o is not g)


# --- moving and crashing ------------------------------------------------------------------


def test_a_bike_moves_one_cell_and_leaves_solid_trail():
    s = state_with()
    events = step(s)
    bike = s.players["p1"].bikes[0]
    assert bike.pos == (21, 42) and bike.prev == (20, 42)
    assert s.arena.get((21, 42)) == Trail("p1", None)
    assert rules.Moved("p1", None, (20, 42), (21, 42)) in events


def test_steering_turns_and_reversing_is_ignored():
    s = state_with()
    step(s, p1=LEFT)
    assert s.players["p1"].bikes[0].pos == (21, 42)
    step(s, p1=UP)
    assert s.players["p1"].bikes[0].pos == (21, 41)


def test_driving_into_a_wall_loses_the_round():
    s = state_with(p1=((1, 10), LEFT), p2=((139, 42), LEFT))
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


def test_head_on_and_swapping_cells_are_draws():
    for p2_start in ((12, 10), (11, 10)):
        s = state_with(p1=((10, 10), RIGHT), p2=(p2_start, LEFT))
        events = step(s)
        assert s.over and s.winner is None
        assert rules.RoundOver(None) in events


def test_the_last_of_four_standing_wins():
    s = state_with(p1=((1, 10), LEFT), p2=((1, 20), LEFT), p3=((50, 50), RIGHT), p4=((70, 50), RIGHT))
    step(s)
    assert not s.over  # two players are out, two remain
    s.arena.set((52, 50), rules.WALL)
    step(s)
    assert s.over and s.winner == "p4"


def test_nothing_happens_after_the_round_is_over():
    s = state_with(p1=((1, 10), LEFT), p2=((139, 42), LEFT))
    step(s)
    assert step(s) == []
    assert rules.advance(s, 1.0, random.Random(0)) == []


# --- H: splitting -------------------------------------------------------------------------


def test_an_h_gate_splits_you_at_once_and_starts_the_bar():
    s = state_with()
    gate_ahead(s, "p1", "H")
    events = step(s)
    pl = s.players["p1"]
    assert pl.is_split and pl.meter == config.H_TIME
    assert [b.pos for b in pl.bikes] == [(21, 42), (21, 42)]
    assert [b.heading for b in pl.bikes] == [UP, DOWN]
    assert rules.PickedUp("p1", "H", (21, 42)) in events
    assert rules.Split("p1", (21, 42)) in events
    assert s.gates == [] and s.respawns == [config.GATE_RESPAWN]


def test_a_gate_is_taken_from_up_to_two_cells_away():
    s = state_with()
    s.gates = [Gate("Z", (23, 44)), Gate("Z", (24, 42))]  # bike enters (21, 42)
    step(s)
    assert s.gates == [Gate("Z", (24, 42))]


def test_the_fork_ignores_the_stick_for_one_tick():
    s = state_with()
    gate_ahead(s, "p1", "H")
    step(s)
    step(s, p1=RIGHT)
    assert [b.pos for b in s.players["p1"].bikes] == [(21, 41), (21, 43)]


def test_the_second_copy_steers_mirrored():
    s = state_with()
    pl = split_p1(s)  # copies at (21, 41) heading up and (21, 43) heading down
    step(s, p1=RIGHT)
    assert [b.heading for b in pl.bikes] == [RIGHT, RIGHT]
    step(s, p1=UP)
    assert [b.heading for b in pl.bikes] == [UP, DOWN]
    assert [b.pos for b in pl.bikes] == [(22, 40), (22, 44)]


def test_a_copy_cannot_reverse_either():
    s = state_with()
    pl = split_p1(s)
    step(s, p1=DOWN)  # the reverse of copy 0, and mirrored the reverse of copy 1
    assert [b.heading for b in pl.bikes] == [UP, DOWN]


def test_your_copies_pass_through_each_other():
    s = state_with()
    pl = split_p1(s)
    step(s, p1=RIGHT)  # (22, 41) and (22, 43)
    step(s, p1=DOWN)  # both enter (22, 42)
    step(s, p1=DOWN)  # and drive on through each other's ghost cells
    assert pl.alive and len(pl.bikes) == 2
    assert [b.pos for b in pl.bikes] == [(22, 43), (22, 41)]


def test_another_h_splits_only_the_copy_that_took_it_and_extends_the_bar():
    s = state_with()
    pl = split_p1(s)
    gate_ahead(s, "p1", "H", bike=0)  # in front of the copy heading up
    step(s)
    assert len(pl.bikes) == 3
    assert pl.meter == 2 * config.H_TIME
    assert [b.heading for b in pl.bikes] == [LEFT, RIGHT, DOWN]
    assert [b.flip for b in pl.bikes] == [(1, 1), (-1, 1), (1, -1)]


def test_the_bar_is_capped(monkeypatch):
    s = state_with()
    pl = split_p1(s)
    pl.meter = config.SUPERPOSITION_MAX - 1
    gate_ahead(s, "p1", "H", bike=0)
    step(s)
    assert pl.meter == config.SUPERPOSITION_MAX


def test_at_the_copy_limit_an_h_only_extends_the_bar(monkeypatch):
    monkeypatch.setattr(config, "MAX_COPIES", 2)
    s = state_with()
    pl = split_p1(s)
    gate_ahead(s, "p1", "H", bike=0)
    step(s)
    assert len(pl.bikes) == 2 and pl.meter == 2 * config.H_TIME


# --- how copies end -----------------------------------------------------------------------


def test_losing_a_copy_dissolves_its_trail_and_solidifies_the_other():
    s = state_with(p1=((20, 3), RIGHT), p2=((139, 42), LEFT))
    pl = split_p1(s)  # split at (21, 3); copies at (21, 2) and (21, 4)
    step(s)  # (21, 1) and (21, 5)
    events = step(s)  # copy 0 hits the top wall
    assert not pl.is_split and pl.alive
    survivor = pl.bikes[0]
    assert survivor.node is None and survivor.pos == (21, 6) and survivor.flip == (1, 1)
    for c in [(21, 2), (21, 1)]:
        assert s.arena.get(c) is None
    for c in [(21, 3), (21, 4), (21, 5), (21, 6)]:
        assert s.arena.get(c) == Trail("p1", None)
    collapse = next(e for e in events if isinstance(e, rules.Collapse))
    assert collapse.reason == "crash"
    assert set(collapse.dissolved) == {(21, 2), (21, 1)}
    assert collapse.solidified == (((21, 3), (21, 4), (21, 5)),)


def test_both_copies_crashing_on_one_tick_loses_the_round():
    s = state_with(p1=((20, 1), RIGHT), p2=((139, 42), LEFT))
    gate_ahead(s, "p1", "H")
    step(s)  # split at (21, 1), right under the top wall
    s.arena.set((21, 2), Trail("p2", None))
    step(s)  # the fork drives one copy into the wall, the other into p2's trail
    assert not s.players["p1"].alive and s.winner == "p2"


def three_copies():
    """p1 splits at (41, 42) into a (up) and b (down); a splits again at
    (41, 40) into a1 (left) and a2 (right). Ends after the second fork."""
    s = state_with(p1=((40, 42), RIGHT), p2=((139, 10), LEFT))
    pl = split_p1(s)
    gate_ahead(s, "p1", "H", bike=0)
    step(s)
    step(s)  # a1 at (40, 40), a2 at (42, 40), b at (41, 45)
    assert [b.pos for b in pl.bikes] == [(40, 40), (42, 40), (41, 45)]
    return s, pl


def test_losing_one_of_three_copies_keeps_the_shared_trail_as_a_ghost():
    s, pl = three_copies()
    a = pl.nodes[pl.bikes[0].node].parent
    s.arena.set((39, 40), rules.WALL)
    step(s)  # a1 crashes
    assert len(pl.bikes) == 2
    assert s.arena.get((40, 40)) is None  # a1's own segment dissolved
    assert s.arena.get((41, 41)) == Trail("p1", a)  # a's segment is still shared by a2
    s.arena.set((41, 47), rules.WALL)
    step(s)  # b crashes: a2 is all that is left, so a's and a2's trail turn solid
    assert not pl.is_split
    for c in [(41, 41), (41, 40), (42, 40), (43, 40), (44, 40)]:
        assert s.arena.get(c) == Trail("p1", None)
    for c in [(41, 43), (41, 46)]:
        assert s.arena.get(c) is None


def test_measurement_eliminates_the_copy_whose_trail_was_touched():
    s = state_with(p1=((20, 42), RIGHT), p2=((24, 41), LEFT))
    pl = split_p1(s)  # copies at (21, 41) and (21, 43); p2 at (22, 41)
    events = step(s)  # p2 drives into copy 0's ghost cell (21, 41)
    assert not pl.is_split and pl.bikes[0].pos == (21, 44)
    assert rules.Measured("p1", "p2", (21, 41)) in events
    assert any(isinstance(e, rules.Collapse) and e.reason == "measurement" for e in events)
    assert s.arena.get((21, 41)) == Trail("p2", None)  # p2 drove on through
    assert s.arena.get((21, 40)) is None  # copy 0 never got there
    assert s.players["p2"].alive


def test_measuring_a_shared_segment_eliminates_every_copy_after_it():
    s, pl = three_copies()
    p2 = s.players["p2"].bikes[0]
    p2.pos = p2.prev = (42, 41)
    p2.heading = LEFT
    step(s)  # p2 enters (41, 41), on a's segment: a1 and a2 never happened
    assert not pl.is_split and pl.bikes[0].pos == (41, 46)
    for c in [(41, 40), (40, 40), (42, 40)]:
        assert s.arena.get(c) is None


def test_measuring_every_copy_at_once_leaves_one_at_random():
    s = state_with(p1=((30, 42), RIGHT), p2=((34, 41), LEFT), p4=((34, 43), LEFT))
    rng = PickRng(1)
    gate_ahead(s, "p1", "H")
    step(s, rng)  # split at (31, 42)
    step(s, rng)  # copies at (31, 41) and (31, 43)
    step(s, rng)  # p2 and p4 enter both of those cells at once
    pl = s.players["p1"]
    assert not pl.is_split and rng.calls == 1
    assert pl.bikes[0].pos == (31, 44)  # copy 1 was picked


def test_heads_count_as_trail_of_their_kind():
    s = state_with(p1=((9, 10), RIGHT), p2=((14, 11), LEFT))
    gate_ahead(s, "p2", "H")
    step(s)  # p2 splits at (13, 11)
    step(s)  # fork: p2's copies at (13, 12) and (13, 10)
    step(s, p2=LEFT)  # p1 and p2's second copy both enter (12, 10)
    p1, p2 = s.players["p1"], s.players["p2"]
    # p1 met a ghost head: a measurement, it passes. The ghost met a solid head: a crash.
    assert p1.alive and p1.bikes[0].pos == (12, 10)
    assert p2.alive and not p2.is_split and p2.bikes[0].pos == (12, 12)


def test_a_crash_is_applied_before_a_measurement_on_the_same_tick():
    s = state_with(p1=((20, 2), RIGHT), p2=((24, 3), LEFT))
    pl = split_p1(s)  # copies at (21, 1) and (21, 3); p2 at (22, 3)
    events = step(s)  # copy 0 hits the wall while p2 enters copy 1's ghost cell
    assert [e.reason for e in events if isinstance(e, rules.Collapse)] == ["crash"]
    assert pl.alive and pl.bikes[0].pos == (21, 4)


def test_the_bar_drains_in_real_time_and_decoheres_at_zero():
    s = state_with()
    pl = split_p1(s)
    rules.advance(s, 1.0, PickRng(1))
    assert pl.meter == pytest.approx(config.H_TIME - 1.0) and pl.is_split
    events = rules.advance(s, config.H_TIME, PickRng(1))
    assert pl.meter == 0.0 and not pl.is_split
    assert pl.bikes[0].pos == (21, 43)  # copy 1 survived
    assert any(isinstance(e, rules.Collapse) and e.reason == "decoherence" for e in events)


# --- Z and X: shields and jumps -------------------------------------------------------------


def test_a_z_gate_shields_you_through_trails_but_not_walls():
    s = state_with()
    gate_ahead(s, "p1", "Z")
    step(s)
    bike = s.players["p1"].bikes[0]
    assert bike.shield == config.SHIELD_Z
    s.arena.set((22, 42), Trail("p2", None))
    s.arena.set((23, 42), Trail("p1", None))
    step(s)
    step(s)
    assert s.players["p1"].alive and bike.pos == (23, 42)
    s2 = state_with(p1=((1, 10), LEFT), p2=((139, 42), LEFT))
    s2.players["p1"].bikes[0].shield = 5.0
    step(s2)
    assert not s2.players["p1"].alive


def test_shields_wear_off():
    s = state_with()
    s.players["p1"].bikes[0].shield = config.SHIELD_Z
    rules.advance(s, config.SHIELD_Z + 0.1, random.Random(0))
    assert s.players["p1"].bikes[0].shield == 0.0


def test_a_shielded_copy_cannot_be_measured():
    s = state_with(p1=((20, 42), RIGHT), p2=((24, 41), LEFT))
    pl = split_p1(s)
    pl.bikes[0].shield = 5.0
    step(s)  # p2 drives into the shielded copy's ghost cell
    assert len(pl.bikes) == 2


def test_an_x_gate_mirrors_you_across_the_map_and_shields_you():
    s = state_with(p1=((20, 42), RIGHT), p2=((139, 10), LEFT))
    gate_ahead(s, "p1", "X")
    events = step(s)
    bike = s.players["p1"].bikes[0]
    assert bike.pos == bike.prev == (W - 1 - 21, 42)
    assert bike.shield == config.SHIELD_X and bike.heading == RIGHT
    assert s.arena.get((W - 1 - 21, 42)) == Trail("p1", None)
    assert rules.Teleported("p1", (21, 42), (W - 1 - 21, 42)) in events


def test_an_x_gate_moves_only_the_copy_that_took_it():
    s = state_with(p1=((20, 42), RIGHT), p2=((139, 10), LEFT))
    pl = split_p1(s)
    gate_ahead(s, "p1", "X", bike=0)
    step(s)
    a, b = pl.bikes
    assert a.pos == (W - 1 - 21, 40) and a.shield == config.SHIELD_X
    assert b.pos == (21, 44) and b.shield == 0.0
    assert s.arena.get(a.pos) == Trail("p1", a.node)


def test_a_gate_respawns_after_two_seconds():
    s = state_with()
    s.respawns = [config.GATE_RESPAWN]
    rules.advance(s, 1.9, random.Random(0))
    assert s.gates == []
    rules.advance(s, 0.2, random.Random(0))
    assert len(s.gates) == 1 and s.respawns == []
