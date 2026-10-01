import itertools

import pytest

from superconductor import config, rules
from superconductor.lattice import Lattice, edge
from superconductor.rules import Board, Spawn


def scripted(*spawns):
    """Replace the random schedule with a fixed list of (t, a, b) spawns."""
    def schedule(lattice, seed, rate=1.0):
        for t, a, b in spawns:
            yield Spawn(t, a, b, 20.0)
        yield Spawn(float("inf"), (0, 0), (4, 4), 20.0)  # never arrives
    return schedule


@pytest.fixture
def board_with(monkeypatch):
    def make(*spawns, players=("p1",), kind="square"):
        monkeypatch.setattr(rules, "spawn_schedule", scripted(*spawns))
        b = Board(Lattice(kind), 0, players, specials=False)
        b.update(0.01)
        return b
    return make


def walk(board, player, *dirs):
    for d in dirs:
        board.move(player, d)


def test_pair_spawns_and_cursor_autoselects_it(board_with):
    b = board_with((0, (0, 0), (0, 3)))
    assert len(b.pairs) == 1
    cur = b.cursors["p1"]
    assert cur.path == [(0, 0)]
    assert b.target("p1") == (0, 3)
    assert b.endpoint_owner[(0, 0)] == b.endpoint_owner[(0, 3)] == cur.pair_id


def test_reaching_the_partner_commits_and_reserves_the_route(board_with):
    b = board_with((0, (0, 0), (0, 2)))
    walk(b, "p1", "right", "right")
    pair = next(iter(b.pairs.values()))
    assert pair.route == [(0, 0), (0, 1), (0, 2)]
    assert edge((0, 0), (0, 1)) in b.edge_owner
    assert (0, 1) in b.busy_nodes()
    assert b.cursors["p1"].pair_id is None


def test_stepping_back_undoes_and_missing_couplers_block(board_with):
    b = board_with((0, (0, 0), (0, 3)))
    walk(b, "p1", "right", "left")
    assert b.cursors["p1"].path == [(0, 0)]
    b.move("p1", "up")  # off the chip
    assert b.cursors["p1"].path == [(0, 0)]
    assert b.events[-1].kind == "blocked"


def test_brick_lattice_blocks_missing_vertical(board_with):
    b = board_with((0, (0, 1), (2, 1)), kind="brick")
    b.move("p1", "down")
    assert b.cursors["p1"].path == [(0, 1)]


def test_routes_may_cross_at_a_qubit_but_not_share_couplers(board_with):
    b = board_with((0, (0, 0), (0, 2)), (0, (1, 1), (4, 1)))
    walk(b, "p1", "right", "right")  # commit pair 0 along row 0
    assert b.cursors["p1"].path[0] == (1, 1)
    b.move("p1", "up")  # onto (0,1), the middle of the committed route: allowed
    assert b.cursors["p1"].path == [(1, 1), (0, 1)]
    b.move("p1", "left")  # but its coupler (0,0)-(0,1) is reserved
    assert b.cursors["p1"].path == [(1, 1), (0, 1)]
    b.move("p1", "right")
    assert b.cursors["p1"].path == [(1, 1), (0, 1)]


def test_routes_may_run_through_other_stations(board_with):
    b = board_with((0, (0, 0), (0, 3)), (0, (0, 1), (4, 1)))
    b.move("p1", "right")
    assert b.cursors["p1"].path == [(0, 0), (0, 1)]
    assert b.predict_collision("p1") == (0, 1)  # that qubit is still sitting there


def test_running_into_a_waiting_station_crashes_both_pairs(board_with):
    b = board_with((0, (0, 0), (0, 3)), (0, (0, 1), (4, 1)))
    walk(b, "p1", "right", "right", "right")
    assert b.station_threats() == {(0, 1)}
    b.update(1.0 / config.QUBIT_SPEED)
    crash = [e for e in b.events if e.kind == "crash"]
    assert crash and crash[0].node == (0, 1)
    assert b.pairs == {} and b.lives == config.LIVES - config.CRASH_LIFE_COST


def test_running_through_a_station_is_safe_once_its_qubit_left(board_with):
    b = board_with((0, (0, 0), (0, 3)), (0, (0, 1), (4, 1)))
    walk(b, "p1", "right", "right", "right")  # through (0,1), the other pair's start
    assert b.station_threats() == {(0, 1)}
    walk(b, "p1", "down", "down", "down", "down")  # route that pair away from (0,1) right now
    assert b.station_threats() == set()
    b.update(10.0)
    assert b.gates == 2 and b.lives == config.LIVES


def test_running_through_a_routes_destination_crashes(board_with):
    # pair 1 is routed *towards* (0,1): its partner qubit sits there until the gate fires
    b = board_with((0, (0, 0), (0, 3)), (0, (4, 1), (0, 1)))
    walk(b, "p1", "right", "right", "right")
    walk(b, "p1", "up", "up", "up", "up")
    assert b.station_threats() == set()  # both routes committed: nothing left to avert
    for _ in range(200):  # frame-sized steps, as in the game
        b.update(0.05)
    assert [e.node for e in b.events if e.kind == "crash"] == [(0, 1)]


def test_qubit_travels_and_releases_couplers_behind_it(board_with):
    b = board_with((0, (0, 0), (0, 3)))
    walk(b, "p1", "right", "right", "right")
    pair = next(iter(b.pairs.values()))
    b.update(1.0 / config.QUBIT_SPEED + 0.01)  # one coupler done
    assert edge((0, 0), (0, 1)) not in b.edge_owner
    assert (0, 0) not in b.endpoint_owner
    assert edge((0, 1), (0, 2)) in b.edge_owner
    n0, n1, f, jump = pair.segment()
    assert (n0, n1, jump) == ((0, 1), (0, 2), False) and f == pytest.approx(0.0, abs=0.05)


def test_arrival_executes_the_gate_and_scores(board_with):
    b = board_with((0, (0, 0), (0, 2)))
    walk(b, "p1", "right", "right")
    b.update(3.0 / config.QUBIT_SPEED)
    assert b.pairs == {}
    assert b.gates == 1
    assert not b.endpoint_owner and not b.edge_owner
    gate = [e for e in b.events if e.kind == "gate"][0]
    assert gate.fidelity == 1.0
    assert b.score == gate.points > config.GATE_BASE_POINTS


def test_detours_cost_fidelity(board_with):
    b = board_with((0, (0, 0), (0, 1)))
    walk(b, "p1", "down", "right", "up")
    b.update(10.0)
    gate = [e for e in b.events if e.kind == "gate"][0]
    assert gate.fidelity == pytest.approx(config.DETOUR_FIDELITY ** 2)


def test_waiting_pair_decoheres_and_costs_a_life(board_with):
    b = board_with((0, (0, 0), (0, 3)))
    b.update(21.0)
    assert b.lives == config.LIVES - 1
    assert b.pairs == {}
    assert b.cursors["p1"].pair_id is None


def test_game_over_after_last_life(monkeypatch):
    b = Board(Lattice("square"), 7, ("p1",))
    for _ in range(4000):
        b.update(0.1)
        if b.over:
            break
    assert b.over and b.lives == 0
    # no cursor may point at a pair that is gone (game.py draws them)
    assert all(c.pair_id is None or c.pair_id in b.pairs for c in b.cursors.values())


def test_select_cycles_through_every_endpoint(board_with):
    b = board_with((0, (0, 0), (0, 3)), (0, (4, 0), (4, 4)))
    seen = []
    for _ in range(4):
        b.select("p1", 1)
        seen.append(b.cursors["p1"].path[0])
    assert set(seen) == {(0, 0), (0, 3), (4, 0), (4, 4)}
    b.select("p1", -1)
    assert b.cursors["p1"].path[0] == seen[-2]


def test_other_end_and_undo(board_with):
    b = board_with((0, (0, 0), (0, 3)))
    walk(b, "p1", "right", "down")
    b.undo("p1")
    assert b.cursors["p1"].path == [(0, 0), (0, 1)]
    b.undo("p1")
    b.undo("p1")
    assert b.cursors["p1"].path == [(0, 0)]
    b.other_end("p1")
    assert b.cursors["p1"].path == [(0, 3)]
    assert b.target("p1") == (0, 0)


def test_coop_players_never_share_a_pair(board_with):
    b = board_with((0, (0, 0), (0, 3)), (0, (4, 0), (4, 4)), players=("p1", "p2"))
    p1, p2 = b.cursors["p1"], b.cursors["p2"]
    assert p1.pair_id is not None and p2.pair_id is not None
    assert p1.pair_id != p2.pair_id
    for _ in range(4):
        b.select("p2", 1)
        assert b.cursors["p2"].pair_id != p1.pair_id


def test_committing_cuts_the_other_players_draft_at_a_shared_coupler(board_with):
    b = board_with((0, (2, 0), (2, 4)), (0, (1, 1), (4, 4)), players=("p1", "p2"))
    assert b.cursors["p1"].path == [(2, 0)]
    assert b.cursors["p2"].path == [(1, 1)]
    walk(b, "p2", "down", "right", "right")  # P2 drafts along (2,1)-(2,2)-(2,3)
    walk(b, "p1", "right", "right", "right", "right")  # P1 commits row 2 first
    assert b.cursors["p2"].path == [(1, 1), (2, 1)]  # crossing qubit kept, coupler cut


def test_spawn_waits_while_an_endpoint_is_busy(board_with):
    b = board_with((0, (0, 0), (0, 2)), (0.5, (0, 1), (4, 4)))
    walk(b, "p1", "right", "right")  # route through (0,1)
    b.update(0.6)
    assert len(b.queue) == 1  # (0,1) is on a route in progress
    b.update(3.0 / config.QUBIT_SPEED)
    b.update(0.01)
    assert not b.queue
    assert any(p.a == (0, 1) for p in b.pairs.values())


def test_free_route_finds_shortest_unreserved_path(board_with):
    b = board_with((0, (0, 0), (0, 4)), (0, (1, 0), (1, 4)))
    pair0, pair1 = b.pairs.values()
    b.commit_route(pair0.id, b.free_route(pair0, pair0.a))
    route = b.free_route(pair1, pair1.a)
    assert route[0] == (1, 0) and route[-1] == (1, 4) and len(route) == 5


def test_same_seed_gives_same_pairs():
    lat = Lattice("square")
    s1 = list(itertools.islice(rules.spawn_schedule(lat, 42), 20))
    s2 = list(itertools.islice(rules.spawn_schedule(lat, 42), 20))
    assert s1 == s2
    assert all(lat.distance(s.a, s.b) >= config.MIN_PAIR_DISTANCE for s in s1)


def test_game_starts_with_several_pairs():
    b = Board(Lattice("square"), 3, ("p1",), specials=False)
    b.update(0.6)
    assert len(b.pairs) == config.INITIAL_PAIRS


def test_difficulty_ramps_up():
    lat = Lattice("square")
    s = list(itertools.islice(rules.spawn_schedule(lat, 1), 200))
    assert s[0].coherence == pytest.approx(config.COHERENCE_START, abs=0.1)
    assert s[-1].coherence == pytest.approx(config.COHERENCE_MIN)
    assert s[-1].t - s[-2].t == pytest.approx(config.SPAWN_INTERVAL_MIN)


# ---------------------------------------------------------------- crossing


def crossing_board(board_with, *, p2_delay=0.0):
    """Pair 0 along row 2, pair 1 down column 2: both cross at (2,2)."""
    b = board_with((0, (2, 0), (2, 4)), (0, (0, 2), (4, 2)), players=("p1", "p2"))
    walk(b, "p1", "right", "right", "right", "right")
    if p2_delay:
        b.update(p2_delay)
    walk(b, "p2", "down", "down")
    return b


def test_crossing_at_the_same_time_is_predicted_and_crashes(board_with):
    b = crossing_board(board_with)
    assert b.predict_collision("p2") == (2, 2)
    walk(b, "p2", "down", "down")  # commit anyway
    b.update(2.0 / config.QUBIT_SPEED)
    crash = [e for e in b.events if e.kind == "crash"]
    assert crash and crash[0].node == (2, 2)
    assert b.lives == config.LIVES - config.CRASH_LIFE_COST
    assert b.pairs == {} and not b.edge_owner and not b.endpoint_owner


def test_crossing_with_enough_gap_is_safe(board_with):
    b = crossing_board(board_with, p2_delay=1.5 / config.QUBIT_SPEED)
    assert b.predict_collision("p2") is None
    walk(b, "p2", "down", "down")
    b.update(10.0)
    assert b.gates == 2 and b.lives == config.LIVES


def test_prediction_counts_the_head_of_a_draft(board_with):
    b = board_with((0, (2, 0), (2, 4)), (0, (0, 2), (4, 2)), players=("p1", "p2"))
    walk(b, "p1", "right", "right", "right", "right")
    walk(b, "p2", "down", "down")  # head is the crossing qubit itself
    assert b.cursors["p2"].path[-1] == (2, 2)
    assert b.predict_collision("p2") == (2, 2)


# ---------------------------------------------------------------- specials


def test_defect_coupler_blocks_until_restored(board_with):
    b = board_with((0, (0, 0), (0, 3)))
    b.place_special("defect", edge_=edge((0, 0), (0, 1)))
    b.move("p1", "right")
    assert b.cursors["p1"].path == [(0, 0)]
    b.update(config.SPECIAL_DURATION["defect"] + 0.1)
    assert not b.specials
    b.move("p1", "right")
    assert b.cursors["p1"].path == [(0, 0), (0, 1)]


def test_miscalibrated_coupler_is_slower_and_costs_fidelity(board_with):
    b = board_with((0, (0, 0), (0, 2)))
    b.place_special("miscal", edge_=edge((0, 0), (0, 1)))
    walk(b, "p1", "right", "right")
    pair = next(iter(b.pairs.values()))
    b.update(1.0 / config.QUBIT_SPEED)
    assert pair.progress == pytest.approx(1 / config.MISCAL_SLOWDOWN)
    b.update(10.0)
    gate = [e for e in b.events if e.kind == "gate"][0]
    assert gate.fidelity == pytest.approx(config.MISCAL_FIDELITY)


def test_speed_qubit_boosts_whoever_passes(board_with):
    b = board_with((0, (0, 0), (0, 4)))
    b.place_special("speed", nodes=((0, 1),))
    walk(b, "p1", "right", "right", "right", "right")
    pair = next(iter(b.pairs.values()))
    b.update(1.0 / config.QUBIT_SPEED + 1e-6)
    assert pair.boost == config.SPEED_BOOST
    b.update(1.0 / config.QUBIT_SPEED)
    assert pair.progress == pytest.approx(1 + config.SPEED_BOOST, abs=0.01)


def test_bell_pair_teleports_once(board_with):
    b = board_with((0, (0, 0), (4, 4)), (5, (2, 0), (2, 4)))
    bell = b.place_special("bell", nodes=((0, 1), (4, 3)))
    b.move("p1", "right")  # into (0,1): jumps to (4,3)
    assert b.cursors["p1"].path == [(0, 0), (0, 1), (4, 3)]
    b.undo("p1")  # the jump is undone as a whole
    assert b.cursors["p1"].path == [(0, 0)]
    walk(b, "p1", "right", "right")  # jump, then (4,3) -> (4,4) commits
    pair = next(iter(b.pairs.values()))
    assert pair.route == [(0, 0), (0, 1), (4, 3), (4, 4)]
    assert pair.teleports == {1}
    assert bell.claimed_by == pair.id
    b.update(10.0)
    assert bell not in b.specials  # used up
    gate = [e for e in b.events if e.kind == "gate"][0]
    assert gate.fidelity == 1.0


def test_specials_never_land_on_busy_spots(board_with):
    b = board_with((0, (0, 0), (0, 4)), (0, (4, 0), (4, 4)))
    walk(b, "p1", "right", "right")  # draft on row 0
    for kind in ("speed", "bell", "miscal", "defect") * 3:
        busy_n, busy_e = b.busy_nodes(), b.busy_edges()
        s = b.place_special(kind)
        if s is None:
            continue
        assert not set(s.nodes) & busy_n
        assert s.edge not in busy_e


def test_stations_never_spawn_on_specials(board_with):
    b = board_with((0, (0, 0), (0, 4)), (1, (2, 2), (4, 4)))
    b.place_special("speed", nodes=((2, 2),))
    b.update(1.5)
    assert len(b.queue) == 1  # waits for the speed qubit to vanish
    b.update(config.SPECIAL_DURATION["speed"])
    b.update(0.01)
    assert not b.queue


def test_specials_appear_by_themselves():
    b = Board(Lattice("square"), 5, ("p1",))
    kinds = set()
    for _ in range(int(150 / 0.1)):
        b.update(0.1)
        kinds |= {e.special.kind for e in b.events if e.kind == "special_on"}
        b.events.clear()
        b.lives = config.LIVES  # keep it alive, nobody is playing
    assert kinds == set(rules.SPECIAL_KINDS)


# ---------------------------------------------------------------- co-op


def test_new_pair_goes_to_whoever_did_not_route_last(board_with):
    b = board_with((0, (0, 0), (0, 2)), (0, (4, 0), (4, 2)), (1, (2, 0), (2, 2)),
                   players=("p1", "p2"))
    walk(b, "p2", "right", "right")  # P2 routes; nothing free for P2 to take
    assert b.cursors["p2"].pair_id is None
    walk(b, "p1", "right", "right")  # now P1 routed last
    b.update(1.5)  # third pair arrives
    assert b.cursors["p2"].path == [(2, 0)]
    assert b.cursors["p1"].pair_id is None


def test_coop_pairs_come_more_often():
    lat = Lattice("square")
    solo = list(itertools.islice(rules.spawn_schedule(lat, 4), 30))
    coop = list(itertools.islice(rules.spawn_schedule(lat, 4, config.COOP_SPAWN_RATE), 30))
    assert [(s.a, s.b) for s in solo] == [(s.a, s.b) for s in coop]  # same pairs
    assert coop[-1].t < solo[-1].t
    assert coop[2].t - coop[1].t == pytest.approx((solo[2].t - solo[1].t) / config.COOP_SPAWN_RATE)
