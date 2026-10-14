import dataclasses
import random

import pytest

from qircuit import config, tracks
from qircuit.ai import SKILLS, Driver
from qircuit.race import Bug, Race, Trap
from qircuit.track import Gate, Track, TrackDef

DT = 1 / 60
PLAIN = [Track(dataclasses.replace(d, gates=(), items=0, dynamic_gates=0)) for d in tracks.ALL]


def straight_oval(*gates: Gate) -> Track:
    return Track(TrackDef("OVAL", (120.0, 80.0), 0.0,
                          (("S", 400.0), ("A", 100.0, 180), ("S", 400.0), ("A", 100.0, 180)),
                          0.0, gates=tuple(gates)))


def time_trial(track: Track, level: str, distance_laps: float = 2) -> tuple[float, int]:
    """Seconds to cover the distance alone, and how often it spun out."""
    race = Race(track, ("cpu1",), random.Random(0))
    driver = Driver("cpu1", level, random.Random(1))
    body = race.bodies[0]
    goal = body.p + distance_laps * track.length
    spins = 0
    while body.p < goal and race.time < 120:
        events = race.update(DT, {"cpu1": driver.controls(race, DT)})
        spins += sum(e.kind == "spin" for e in events)
    return race.time, spins


def test_every_level_is_one():
    assert set(SKILLS) == set(config.LEVELS)


@pytest.mark.parametrize("track", PLAIN, ids=lambda t: t.name)
def test_alone_every_level_laps_without_spinning_and_the_harder_ones_are_faster(track):
    times = {}
    for level in config.LEVELS:
        times[level], spins = time_trial(track, level)
        assert spins == 0, level
    assert times["BRUTAL"] < times["TOUGH"] < times["EASY"]
    assert times["EASY"] > 1.1 * times["TOUGH"]  # easy is clearly easier


@pytest.mark.parametrize("track_def", tracks.ALL, ids=lambda d: d.name)
def test_in_a_full_race_with_gates_brutal_gets_further_than_easy(track_def):
    track = Track(track_def)
    wins = 0
    for seed in range(4):
        rng = random.Random(seed)
        players = ("cpu1", "cpu2", "cpu3", "cpu4")
        levels = ("EASY", "BRUTAL", "EASY", "BRUTAL")
        race = Race(track, players, rng)
        drivers = [Driver(p, lv, rng) for p, lv in zip(players, levels)]
        while race.time < 40:
            race.update(1 / 30, {d.player: d.controls(race, 1 / 30) for d in drivers})
        order = race.standings()
        wins += order.index("cpu2") < order.index("cpu1") and order.index("cpu4") < order.index("cpu3")
    assert wins >= 3


def test_it_overtakes_a_slower_car_on_its_wire():
    race = Race(straight_oval(), ("cpu1", "cpu2"), random.Random(0))
    me, slow = race.bodies
    me.p = me.reach = 0
    me.lane, me.u, me.v = 1, 1.0, 200
    slow.p = slow.reach = 60
    slow.lane, slow.u, slow.v = 1, 1.0, 60
    assert Driver("cpu1", "TOUGH", random.Random(0)).choose_wire(race, me) != 0


def test_in_a_slipstream_it_pulls_out_to_pass_a_car_no_slower_than_it_is_now():
    race = Race(straight_oval(), ("cpu1", "cpu2"), random.Random(0))
    me, ahead = race.bodies
    me.p = me.reach = 0
    me.lane, me.u, me.v, me.draft = 1, 1.0, 180, 1.0
    ahead.p = ahead.reach = 30
    ahead.lane, ahead.u, ahead.v = 1, 1.0, 180
    assert Driver("cpu1", "TOUGH", random.Random(0)).choose_wire(race, me) != 0


def test_brutal_aims_its_hovering_bug_at_a_rival():
    race = Race(straight_oval(), ("cpu1", "cpu2"), random.Random(0))
    me, rival = race.bodies
    me.p = me.reach = 0
    me.lane, me.u, me.v = 1, 1.0, 150
    rival.p = rival.reach = 150
    rival.lane, rival.u, rival.v = 2, 2.0, 150
    race.bugs.append(Bug(race._id(), "X", 1, 14, "cpu1", 5.0, hold=0.8, carrier=me.id))
    assert Driver("cpu1", "BRUTAL", random.Random(0)).choose_wire(race, me) == 1


def test_brutal_dodges_a_trap_and_errors_about_to_meet_it():
    race = Race(straight_oval(), ("cpu1", "cpu2"), random.Random(0))
    me, other = race.bodies
    me.p = me.reach = 0
    me.lane, me.u, me.v = 1, 1.0, 150
    other.p = other.reach = 300
    other.lane, other.u = 3, 3.0
    race.traps.append(Trap(race._id(), "cpu2", 1, 100, 0.0, None))
    assert Driver("cpu1", "BRUTAL", random.Random(0)).choose_wire(race, me) != 0
    race.traps.clear()
    race.bugs.append(Bug(race._id(), "Z", 1, 80, "cpu2", 5.0, v=100))  # ahead, slower: we'd catch it
    assert Driver("cpu1", "BRUTAL", random.Random(0)).choose_wire(race, me) != 0
    race.bugs[0] = Bug(race._id(), "X", 1, -60, "cpu2", 5.0, v=220)  # behind, faster: it catches us
    assert Driver("cpu1", "BRUTAL", random.Random(0)).choose_wire(race, me) != 0
    race.bugs[0] = Bug(race._id(), "X", 1, 80, "cpu2", 5.0, v=220)  # ahead and pulling away: no matter
    assert Driver("cpu1", "BRUTAL", random.Random(0)).choose_wire(race, me) == 0


def test_brutal_goes_for_a_cnot_copy():
    race = Race(straight_oval(Gate("CNOT", 150, (2, 3))), ("cpu1", "cpu2"), random.Random(0))
    me, other = race.bodies
    me.p = me.reach = 0
    me.lane, me.u, me.v = 1, 1.0, 150
    other.p = other.reach = 300
    other.lane, other.u = 3, 3.0
    assert Driver("cpu1", "BRUTAL", random.Random(0)).choose_wire(race, me) == 1


def test_it_never_changes_wires_mid_change():
    race = Race(straight_oval(), ("cpu1",), random.Random(0))
    me = race.bodies[0]
    me.lane, me.u = 2, 1.4
    assert Driver("cpu1", "BRUTAL", random.Random(0)).choose_wire(race, me) == 0


def test_it_drives_through_the_same_cruise_control_and_holds_its_pace_on_a_straight():
    """A bot's speed comes only from up and down on the cruise setting, as a
    person's does: EASY brings the start's flat-out setting down to its pace
    and then mostly lets the cruise control hold it."""
    race = Race(straight_oval(), ("cpu1",), random.Random(0))
    me = race.bodies[0]
    me.p = me.reach = -300.0
    me.lane, me.u = 1, 1.0
    driver = Driver("cpu1", "EASY", random.Random(0))
    driver.wait = 99.0  # no wire changes
    pressed = 0
    for i in range(round(3.5 / DT)):
        c = driver.controls(race, DT)
        pressed += i > 3 / DT and (c.throttle or c.brake)
        race.update(DT, {"cpu1": c})
    pace = SKILLS["EASY"].pace * config.CAR.max_speed
    assert me.p < 400 and me.v == pytest.approx(pace, abs=4)
    assert race.cruise_speed(me, config.CAR) == pytest.approx(pace, abs=4)
    assert pressed <= 3  # hands off, once it is there
