import dataclasses
import math
import random

import pytest

from qarrera import config
from qarrera.race import Bug, Controls, Item, Race, Trap, grid
from qarrera.track import Gate, Track, TrackDef

DT = 1 / 60
CORNER = 400.0  # the oval's first turn starts here


def oval(*gates: Gate, **kw) -> Track:
    return Track(TrackDef("OVAL", (120.0, 80.0), 0.0,
                          (("S", 400.0), ("A", 100.0, 180), ("S", 400.0), ("A", 100.0, 180)),
                          0.0, gates=tuple(gates), **kw))


def race_on(track: Track, players=("p1", "p2"), seed=1, **kw) -> Race:
    return Race(track, players, random.Random(seed), **kw)


def place(race: Race, player: str, p: float, lane: int, v: float = 0.0):
    """A racer here, cruising at v (or crawling, from a standstill)."""
    b = race.bodies_of(player)[0]
    b.p = b.reach = p
    b.lane, b.u, b.v = lane, float(lane), v
    b.cruise = max(config.CRUISE_MIN, v / race.racers[player].stats.max_speed)
    b.z = race.track.height(race.s_of(p))
    return b


def until(race: Race, kind: str, seconds: float = 1.0, **controls) -> list:
    """Run until a cue of this kind (and stop on that frame)."""
    events = []
    for _ in range(round(seconds / DT)):
        events += race.update(DT, controls)
        if kind in kinds(events):
            break
    return events


def run(race: Race, seconds: float, **controls) -> list:
    events = []
    for _ in range(round(seconds / DT)):
        events += race.update(DT, controls)
    return events


def kinds(events) -> list[str]:
    return [e.kind for e in events]


# --- driving --------------------------------------------------------------------------

def test_up_from_a_standstill_accelerates_to_top_speed_and_no_further():
    race = race_on(oval())
    b = place(race, "p1", 0, 1)
    run(race, 1.0, p1=Controls(throttle=True))
    assert b.v == pytest.approx(config.CAR.accel, rel=0.05)
    run(race, 1.1, p1=Controls(throttle=True))
    assert b.p < CORNER and b.v == pytest.approx(config.CAR.max_speed)


def test_it_sets_off_flat_out_and_cruises_at_its_speed_with_no_input():
    race = race_on(oval())
    b = race.bodies_of("p1")[0]
    assert b.v == 0 and b.cruise == config.CRUISE_START == 1.0
    run(race, 2.2)
    assert b.v == pytest.approx(config.CAR.max_speed)
    race = race_on(oval())
    b = place(race, "p1", 0, 1, v=150)
    run(race, 1.0)
    assert b.v == pytest.approx(150)


def test_down_brakes_hard_and_it_holds_the_speed_it_is_let_go_at():
    race = race_on(oval())
    b = place(race, "p1", 0, 1, v=200)
    run(race, 0.25, p1=Controls(brake=True))
    assert b.v == pytest.approx(200 - 0.25 * config.CAR.brake, abs=1)
    held = b.v
    run(race, 0.5)
    assert b.v == pytest.approx(held, abs=0.5)
    run(race, 1.0, p1=Controls(brake=True))  # a crawl, never a stop
    assert b.v == pytest.approx(config.CRUISE_MIN * config.CAR.max_speed)


def test_a_short_push_up_raises_the_speed_it_cruises_at_and_it_gets_there_by_itself():
    race = race_on(oval())
    b = place(race, "p1", 0, 1, v=110)
    run(race, 0.25, p1=Controls(throttle=True))
    assert b.cruise == pytest.approx(0.5 + 0.25 * config.CRUISE_RISE, abs=0.02)
    assert b.v < race.cruise_speed(b, config.CAR)  # it set its sights faster than it can go
    run(race, 1.0)
    assert b.v == pytest.approx(race.cruise_speed(b, config.CAR))
    run(race, 1.0, p1=Controls(throttle=True))
    assert b.cruise == 1.0  # up to its top speed, no further


def test_down_brakes_at_once_even_while_it_is_still_speeding_up():
    race = race_on(oval())
    b = place(race, "p1", 0, 1, v=100)
    b.cruise = 1.0
    run(race, 0.1)
    v = b.v
    run(race, 0.05, p1=Controls(brake=True))
    assert b.v < v and b.cruise * config.CAR.max_speed == pytest.approx(b.v, abs=1)


def test_over_its_setting_it_eases_down_by_its_coast():
    race = race_on(oval())
    b = place(race, "p1", 0, 1, v=150)
    b.v = 250  # off a boost pad, say
    run(race, 0.5)
    assert b.v == pytest.approx(250 - 0.5 * config.CAR.coast, abs=1)
    run(race, 0.4, p1=Controls(throttle=True))  # up from over it starts from its speed, capped at the top
    assert b.cruise == 1.0


def test_after_a_spin_out_it_gets_going_no_faster_than_the_corner_allows():
    race = race_on(oval())
    b = place(race, "p1", CORNER - 60, 1, v=config.CAR.max_speed)
    events = until(race, "spin", 3.0)
    assert "spin" in kinds(events)
    hold = race.safe_speed(b.lane, b.p, config.CAR, brake=0.0)
    assert race.cruise_speed(b, config.CAR) <= hold + 1e-6
    assert "spin" not in kinds(run(race, 2.0))


def test_right_changes_to_the_wire_on_the_racers_right():
    race = race_on(oval())
    b = place(race, "p1", 900.0, 1)
    race.update(DT, {"p1": Controls(right=True)})
    assert b.lane == 2
    race.update(DT, {"p1": Controls(left=True)})
    assert b.lane == 1
    place(race, "p1", 0, 3)
    race.update(DT, {"p1": Controls(right=True)})
    assert b.lane == 3  # no wire beyond the edge


# --- corners ----------------------------------------------------------------------------

def test_a_corner_taken_slowly_neither_drifts_nor_warns():
    race = race_on(oval())
    b = place(race, "p1", CORNER + 100, 0, v=100)
    run(race, 0.5, p1=Controls(throttle=True))
    assert b.load < config.DRIFT_LOAD and b.slip == 0


def test_too_fast_into_a_corner_drifts_then_spins_out_and_stalls():
    race = race_on(oval())
    b = place(race, "p1", CORNER - 20, 3, v=config.CAR.max_speed)
    events = run(race, 1.0, p1=Controls(throttle=True))
    assert "drift" in kinds(events) and "warn" in kinds(events) and "spin" in kinds(events)
    assert b in race.bodies  # still in: just slow


def test_on_a_wider_corner_full_speed_on_the_outside_wire_only_drifts():
    wide = Track(TrackDef("WIDE", (120.0, 80.0), 0.0,
                          (("S", 400.0), ("A", 140.0, 180), ("S", 400.0), ("A", 140.0, 180)), 0.0))
    race = race_on(wide)
    place(race, "p1", CORNER - 20, 0, v=config.CAR.max_speed)
    events = run(race, 1.5, p1=Controls(throttle=True))
    assert "drift" in kinds(events) and "spin" not in kinds(events)


# --- contact ----------------------------------------------------------------------------

def test_running_into_a_racer_from_behind_slows_you_just_below_it():
    race = race_on(oval())
    rear = place(race, "p1", 100, 1, v=200)
    front = place(race, "p2", 100 + config.CAR_LEN - 4, 1, v=100)
    events = race.update(DT, {})
    assert "bump" in kinds(events)
    assert rear.v <= front.v * (1 - config.BUMP_REAR_SLOW) + 1e-6


def test_close_behind_on_the_same_wire_the_slipstream_lifts_top_speed():
    race = race_on(oval())
    rear = place(race, "p1", 0, 1, v=config.CAR.max_speed)
    place(race, "p2", 40, 1, v=config.CAR.max_speed)
    run(race, 0.5, p1=Controls(throttle=True), p2=Controls(throttle=True))
    assert rear.draft > 0.9 and rear.v > config.CAR.max_speed


def test_a_full_slipstream_lasts_a_moment_after_pulling_out_to_pass():
    race = race_on(oval())
    rear = place(race, "p1", 0, 1, v=config.CAR.max_speed)
    front = place(race, "p2", 40, 1, v=config.CAR.max_speed)
    run(race, 0.5, p1=Controls(throttle=True), p2=Controls(throttle=True))
    race.update(1e-4, {"p1": Controls(right=True)})  # pull out
    run(race, config.DRAFT_HOLD * 0.8, p1=Controls(throttle=True), p2=Controls(throttle=True))
    assert rear.lane == 2 and rear.draft == 1.0 and rear.v > front.v + 10
    run(race, 0.6, p1=Controls(throttle=True), p2=Controls(throttle=True))
    assert rear.draft < 1.0


def test_changing_wires_into_a_racer_pushes_it_over_and_costs_both_a_little():
    race = race_on(oval())
    pusher = place(race, "p1", 100, 1, v=100)
    pushed = place(race, "p2", 104, 2, v=100)
    events = race.update(1e-4, {"p1": Controls(right=True)})
    assert "push" in kinds(events)
    assert (pusher.lane, pushed.lane) == (2, 3)
    assert pusher.v == pytest.approx(90, abs=0.1) and pushed.v == pytest.approx(90, abs=0.1)


def test_a_light_racer_cant_shove_a_heavy_one_but_a_heavy_one_can():
    light = dataclasses.replace(config.CAR, mass=0.7)
    heavy = dataclasses.replace(config.CAR, mass=1.3)
    race = race_on(oval(), stats={"p1": light, "p2": heavy})
    a, b = place(race, "p1", 100, 1, v=100), place(race, "p2", 104, 2, v=100)
    race.update(1e-4, {"p1": Controls(right=True)})
    assert (a.lane, b.lane) == (1, 2) and a.v < b.v
    race = race_on(oval(), stats={"p1": heavy, "p2": light})
    a, b = place(race, "p1", 100, 1, v=100), place(race, "p2", 104, 2, v=100)
    race.update(1e-4, {"p1": Controls(right=True)})
    assert (a.lane, b.lane) == (2, 3)


# --- gates and items -----------------------------------------------------------------------

def test_a_swap_trades_the_two_wires():
    race = race_on(oval(Gate("SWAP", 100, (1, 2))))
    a, b = place(race, "p1", 90, 1, v=100), place(race, "p2", 90, 2, v=100)
    events = run(race, 0.3, p1=Controls(throttle=True), p2=Controls(throttle=True))
    assert "swap" in kinds(events) and (a.lane, b.lane) == (2, 1)


def test_a_cnot_copies_a_racer_on_its_control_wire_only_once():
    race = race_on(oval(Gate("CNOT", 100, (1, 2)), Gate("CNOT", 200, (2, 3))))
    place(race, "p1", 90, 1, v=150)
    place(race, "p2", 600, 0)
    events = run(race, 1.0, p1=Controls(throttle=True))
    assert kinds(events).count("copy") == 1  # one extra life at a time
    assert sorted(b.lane for b in race.bodies_of("p1")) == [1, 2]


def test_copies_collapse_onto_the_leading_one_after_a_while():
    race = race_on(oval())
    b = place(race, "p1", 100, 1)
    ahead = race._body("p1", 130, 2)
    race.bodies.append(ahead)
    race.racers["p1"].copy_time = 0.01
    events = run(race, 0.05)
    assert "decohered" in kinds(events) and race.bodies_of("p1") == [ahead] and b not in race.bodies


def test_an_error_gate_puts_a_bug_in_front_that_hovers_then_shoots_off_faster_than_its_racer():
    race = race_on(oval())
    race.items = [Item(race._id(), "ERR", 100, 1)]
    car = place(race, "p1", 90, 1, v=100)
    place(race, "p2", 80, 1, v=100)
    gas = {"p1": Controls(throttle=True)}
    assert "err_armed" in kinds(run(race, 0.2, **gas))
    bug = race.bugs[0]
    assert bug.owner == "p1" and bug.hold > 0 and race.items == []
    assert race.gap(bug.p, car.p) == pytest.approx(config.CAR_LEN)
    assert "launch" in kinds(run(race, config.ERR_HOLD, **gas))
    assert bug.hold == 0 and car.v < bug.v <= car.v + max(config.BUG_EXTRA.values()) + 5


def test_a_hovering_bug_follows_its_racer_onto_another_wire_to_aim_it():
    race = race_on(oval())
    race.items = [Item(race._id(), "ERR", 100, 1)]
    car = place(race, "p1", 90, 1, v=100)
    place(race, "p2", 400, 3, v=0)
    run(race, 0.15)
    race.update(DT, {"p1": Controls(right=True)})
    run(race, 0.2)
    race.update(DT, {"p1": Controls(right=True)})
    run(race, config.ERR_HOLD)
    assert car.lane == 3 and race.bugs[0].lane == 3
    events = run(race, 3.0)  # p2 crawls on, out of the way
    assert {"bitflip", "phaseflip"} & set(kinds(events)) and race.bugs == []


def test_an_x_error_knocks_a_racer_onto_another_wire_and_a_z_takes_its_speed():
    race = race_on(oval())
    b = place(race, "p1", 100, 1, v=100)
    place(race, "p2", 300, 3)
    race.bugs.append(Bug(race._id(), "X", 1, 85, None, 5.0))
    assert "bitflip" in kinds(run(race, 0.1)) and b.lane in (0, 2)
    race = race_on(oval())
    b = place(race, "p1", 100, 1, v=200)
    place(race, "p2", 300, 3)
    race.bugs.append(Bug(race._id(), "Z", 1, 106, None, 5.0))
    assert "phaseflip" in kinds(until(race, "phaseflip", 0.05)) and b.v < 200 * config.BUG_HIT_KEEP["Z"] + 3


def test_a_bug_never_hits_the_racer_that_launched_it():
    race = race_on(oval())
    b = place(race, "p1", 100, 1, v=100)
    race.bugs.append(Bug(race._id(), "Z", 1, 106, "p1", 5.0))
    run(race, 0.2, p1=Controls(throttle=True))
    assert b.v > 100


def test_a_zeno_trap_rides_behind_its_racer_then_drops_and_slows_whoever_hits_it():
    race = race_on(oval())
    race.items = [Item(race._id(), "ZENO", 100, 1)]
    owner = place(race, "p1", 90, 1, v=120)
    victim = place(race, "p2", 0, 1, v=0)
    assert "zeno_armed" in kinds(run(race, 0.2, p1=Controls(throttle=True)))
    trap = race.traps[0]
    run(race, config.ZENO_ARM, p1=Controls(throttle=True))
    assert trap.arm <= 0 and trap.body_id is None
    victim.p = victim.reach = trap.p - 30
    victim.v, victim.cruise = 150, 150 / config.CAR.max_speed
    events = until(race, "zeno", 0.5)
    assert "zeno" in kinds(events) and victim.measured > 0
    assert 50 < victim.v <= 150 * config.ZENO_KEEP + 3  # slowed, not stopped
    assert owner.v > 100


def test_gates_come_and_go_and_new_ones_appear_elsewhere():
    race = race_on(oval(dynamic_gates=4))
    first = list(race.gates)
    assert len(first) == 4 and all(g.kind in config.GATE_KINDS and len(g.lanes) == 2 for g in first)
    run(race, config.GATE_LIFE[1] + config.GATE_RESPAWN + 0.6)
    assert len(race.gates) == 4 and not set(map(id, first)) & set(map(id, race.gates))


def test_nothing_spawns_on_a_boost_pad_or_a_kicker():
    track = oval(dynamic_gates=8, items=6, boosts=((300.0, (0, 1)),), kickers=(700.0,))
    for seed in range(5):
        race = race_on(track, seed=seed)
        for s in [g.s for g in race.gates] + [it.s for it in race.items]:
            assert abs(race.gap(s, 300.0)) >= config.ITEM_GATE_CLEAR - 1e-6
            assert abs(race.gap(s, 700.0)) >= config.ITEM_GATE_CLEAR - 1e-6


# --- boost pads and kickers -------------------------------------------------------------------

def test_a_boost_pad_puts_a_racer_over_its_top_speed_on_its_wires_only():
    race = race_on(oval(boosts=((100.0, (1,)),)))
    b, other = place(race, "p1", 90, 1, v=150), place(race, "p2", 90, 2, v=150)
    assert "boost" in kinds(run(race, 0.1, p1=Controls(throttle=True), p2=Controls(throttle=True)))
    assert b.v > config.CAR.max_speed * (1 + config.BOOST) - 5 and other.v < config.CAR.max_speed


def test_a_kicker_throws_a_fast_racer_into_the_air_and_it_lands_further_on():
    race = race_on(oval(kickers=(150.0,)))
    b = place(race, "p1", 100, 1, v=200)
    assert "jump" in kinds(run(race, 0.3, p1=Controls(throttle=True))) and b.air and b.z > config.KICKER_HEIGHT
    race.update(DT, {"p1": Controls(right=True)})
    assert b.lane == 1  # no changing wires in the air
    assert "land" in kinds(run(race, 0.6)) and not b.air


def test_in_the_air_a_racer_flies_over_a_zeno_trap():
    race = race_on(oval(kickers=(150.0,)))
    b = place(race, "p1", 100, 1, v=200)
    race.traps.append(Trap(race._id(), "p2", 1, 175, 0.0, None))
    assert "zeno" not in kinds(run(race, 0.4, p1=Controls(throttle=True))) and b.measured == 0


# --- the grid, who leads, resets ------------------------------------------------------------------

def test_people_start_in_the_front_row_and_a_race_can_start_anywhere():
    players = ("p1", "p2") + config.BOTS[:6]
    slots = grid(players, ("p1", "p2"), start_p=500.0)
    assert slots["p1"] == (500 - config.GRID_BEHIND, 1) and slots["p2"] == (500 - config.GRID_BEHIND, 2)
    assert len(set(slots.values())) == len(players)


def test_a_reset_puts_a_racer_back_on_a_free_wire_moving_and_passing_through_everything():
    race = race_on(oval(), players=("p1", "p2", "cpu1"))
    race.bodies.append(race._body("p1", 0, 3))
    place(race, "p1", 10, 1)
    place(race, "p2", 300, 1)
    place(race, "cpu1", 300, 2)
    events = []
    b = race.reset("p1", 300, 150, events)
    assert kinds(events) == ["reset"] and race.bodies_of("p1") == [b]  # its copy is gone
    assert b.p == 300 and b.lane == 0 and b.v == 150 and b.ghost > 0  # the free wire nearest its own
    events = race.update(DT, {"p1": Controls(right=True)}) + run(race, 0.2)
    assert b.lane == 1 and not {"push", "bump"} & set(kinds(events))  # straight through p2


def test_a_reset_before_a_corner_comes_back_slow_enough_to_make_it():
    race = race_on(oval())
    b = race.reset("p1", CORNER - 30, 400, [])
    assert b.v < 400 and b.v <= race.safe_speed(b.lane, b.p, config.CAR) + 1e-6
    assert "spin" not in kinds(run(race, 1.5))
