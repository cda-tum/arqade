"""The AI: its three levels and the ladder, steering, gates, braking, items, pace, and whole
races over many seeds (who beats which level)."""

import dataclasses
import random
import statistics

import pytest

from gate_prix import ai, config
from gate_prix.ai import SKILLS, Driver
from gate_prix.car import Controls, aim
from gate_prix.race import Cloud, Race

DT = 1 / 60
TOP = config.TOP_SPEED
SEEDS = range(20)


def custom(level="TOUGH", **numbers):
    """A level's Skill with some of its numbers changed (for testing one part alone)."""
    return dataclasses.replace(SKILLS[level], **numbers)


class Scripted:
    """A scripted player: the right arch of a row with probability `right` (decided per row,
    from 1.5 s out; otherwise a decoy or a gap), clear of the hazards and clouds it sees
    (each with probability `sees`). It never drifts and never uses an item. right = sees =
    1 is the perfect player; 0.6 a mediocre first-time visitor."""

    def __init__(self, seed, right=1.0, sees=1.0):
        self.rng = random.Random(f"{seed}:scripted")
        self.right, self.sees = right, sees
        self.picks, self.seen = {}, {}

    def _sees(self, key):
        if key not in self.seen:
            self.seen[key] = self.rng.random() < self.sees
        return self.seen[key]

    def __call__(self, race, racer):
        car = racer.car
        goal = race.track.segment_at(car.z + 600.0).line
        arch = None
        if racer.next_row < len(race.rows):
            row = race.rows[racer.next_row]
            if row.z - car.z < 1.5 * TOP:
                if racer.next_row not in self.picks:
                    if self.rng.random() < self.right:
                        pick = next(a for a in row.arches if a.right)
                    else:
                        decoys = [a for a in row.arches if not a.right]
                        pick = self.rng.choice(decoys) if decoys and self.rng.random() < 0.5 else None
                    self.picks[racer.next_row] = (pick, ai._gap(row, goal))
                arch, gap = self.picks[racer.next_row]
                goal = arch.offset if arch is not None else gap
        goal = ai.dodge(race, racer, goal, arch, self._sees)
        return Controls(*aim(car, goal, race.track.segment_at(car.z)))


def perfect(race, racer):
    """The perfect scripted player: every right arch, every hazard seen."""
    return Scripted(0)(race, racer)


def park(race, racer):
    car = racer.car
    return Controls(*aim(car, 2.1 if car.lane > 0 else -2.1, race.track.segment_at(car.z)))


def alone(race, car_id):
    """Park every other car off the road."""
    return {r.car.id: park(race, r) for r in race.racers if r.car.id != car_id}


def race_to_the_end(seed, p1=perfect, level="TOUGH"):
    """A 1P race, P1 driven by `p1` (None: the AI at `level`, as in the attract race), the
    five bots at `level`, until all finish."""
    race = Race(seed=seed, players=1, finish_all=True)
    drivers = ai.field(race, seed, level, players=level if p1 is None else None)
    events = []
    while not race.over and race.time < 300.0:
        controls = ai.drive(race, drivers)
        if p1 is not None:
            controls["p1"] = p1(race, race.racer("p1"))
        events += race.update(DT, controls)
    return race, drivers, events


@pytest.fixture(scope="module")
def races():
    """20 races of the perfect scripted player against five TOUGH bots."""
    return [race_to_the_end(seed) for seed in SEEDS]


# --- The levels ----------------------------------------------------------------------------


def test_the_levels_are_the_three_and_named_alike_everywhere():
    assert config.LEVELS == ("EASY", "TOUGH", "BRUTAL")
    assert tuple(SKILLS) == config.LEVELS
    assert all(s.name == name for name, s in SKILLS.items())
    assert config.DEFAULT_LEVEL == config.ATTRACT_LEVEL == "TOUGH"


def test_each_level_is_better_than_the_one_below_at_every_number():
    easy, tough, brutal = (SKILLS[k] for k in config.LEVELS)
    for name in ("aim", "pace", "drift", "sees", "items"):
        assert getattr(easy, name) < getattr(tough, name) <= getattr(brutal, name), name
    assert easy.think > tough.think > brutal.think == 0  # BRUTAL looks every frame
    assert easy.weave > tough.weave > brutal.weave == 0
    assert easy.brake > 0 and tough.brake == brutal.brake == 0  # the better ones drift
    assert (brutal.aim, brutal.pace, brutal.drift, brutal.sees, brutal.items) == (1, 1, 1, 1, 1)
    assert brutal.informed and not tough.informed and not easy.informed
    for s in SKILLS.values():
        assert s.pace <= 1.0  # no level outruns a person on the same line
        assert config.PACE_LIMITS[0] <= s.pace * min(s.rubber)
        assert max(s.rubber) * s.pace <= config.PACE_LIMITS[1]


def test_a_driver_takes_a_level_by_name_or_a_skill_of_its_own():
    assert Driver("cpu1", "EASY").skill is SKILLS["EASY"]
    assert Driver("cpu1").level == config.DEFAULT_LEVEL
    mine = custom(aim=0.3)
    assert Driver("cpu1", mine).skill is mine


# --- The ladder: alone on the track --------------------------------------------------------


def time_trial(seed, level):
    """One bot alone on the track for the whole race: its finish time, its rows' outcomes
    with the arch it meant to take, the hazards it hit and whether it had seen them, and its
    off-road frames (TUNNEL's aside: off the road is its point)."""
    race = Race(seed=seed, players=0, bots=1, finish_all=True)
    d = Driver("cpu1", level, seed)
    me = race.racer("cpu1")
    rows, offroad = [], 0
    while not race.over and race.time < 300.0:
        for e in race.update(DT, {"cpu1": d.controls(race)}):
            if e.kind in ("right", "wrong", "miss"):
                rows.append((e.kind, d._aims[len(rows)][1]))  # rows come in order
        offroad += me.car.offroad and not me.car.tunnelling
    hits = [d._seen[("hazard", i)] for i, h in enumerate(me.hazards) if not h.alive]
    return me.finish_time, rows, hits, offroad


@pytest.fixture(scope="module")
def ladder():
    return {level: [time_trial(seed, level) for seed in range(8)] for level in config.LEVELS}


def test_alone_brutal_is_faster_than_tough_and_tough_than_easy_clearly(ladder):
    times = {level: statistics.median(t for t, _, _, _ in runs) for level, runs in ladder.items()}
    assert times["BRUTAL"] < times["TOUGH"] < times["EASY"]
    assert times["EASY"] > 1.1 * times["TOUGH"]  # EASY is clearly easier
    assert max(t for t, _, _, _ in ladder["BRUTAL"]) < min(t for t, _, _, _ in ladder["TOUGH"])


def test_alone_no_level_makes_a_mistake_it_did_not_mean_to(ladder):
    for level, runs in ladder.items():
        for _, rows, hits, offroad in runs:
            assert offroad == 0, level  # never off the road
            # every row it lined up for the right arch of, it took (a miss it meant can still
            # come right: a SPLIT clone, or a gap that happened to be on the arch)
            assert all(kind == "right" for kind, arch in rows if arch is not None and arch.right)
            assert not any(hits), level  # and every hazard it hit, it never saw coming


def test_alone_brutal_is_perfect_and_easy_and_tough_miss_by_their_aim(ladder):
    for _, rows, hits, _ in ladder["BRUTAL"]:
        assert [kind for kind, _ in rows] == ["right"] * config.SLOTS
        assert hits == []
    for level in ("EASY", "TOUGH"):
        meant = [arch is not None and arch.right for _, rows, _, _ in ladder[level]
                 for _, arch in rows]
        assert sum(meant) / len(meant) == pytest.approx(SKILLS[level].aim, abs=0.1), level
    easy_hits = sum(len(h) for _, _, h, _ in ladder["EASY"])
    tough_hits = sum(len(h) for _, _, h, _ in ladder["TOUGH"])
    assert easy_hits > tough_hits  # EASY misses half the hazards on purpose


# --- The field -----------------------------------------------------------------------------


@pytest.mark.parametrize("players, bots", [(1, 5), (2, 4), (1, 2), (2, 1), (1, 0)])
def test_every_bot_gets_a_driver_at_the_level(players, bots):
    race = Race(seed=1, players=players, bots=bots)
    for level in config.LEVELS:
        drivers = ai.field(race, 1, level)
        ids = [r.car.id for r in race.racers if not r.player]
        assert list(drivers) == ids and len(drivers) == bots
        assert all(d.car_id == car_id and d.level == level for car_id, d in drivers.items())


def test_inside_a_level_the_bots_differ_a_little_the_best_at_the_front():
    race = Race(seed=1, players=1)
    for level in ("EASY", "TOUGH"):
        aims = [d.skill.aim for d in ai.field(race, 1, level).values()]
        assert aims == sorted(aims, reverse=True) and len(set(aims)) == 5
        assert max(aims) - min(aims) == pytest.approx(2 * ai.AIM_JITTER)
        assert statistics.mean(aims) == pytest.approx(SKILLS[level].aim)
    brutal = ai.field(race, 1, "BRUTAL").values()
    assert all(d.skill.aim == 1.0 and d.skill.pace <= 1.0 for d in brutal)  # still perfect
    assert len({d.skill.pace for d in brutal}) > 1  # but not in lockstep


def test_a_bot_drives_any_car_even_a_player():
    race = Race(seed=2, players=2)
    p1 = Driver("p1", "TOUGH", seed=2)
    for _ in range(600):
        race.update(DT, {"p1": p1.controls(race)})
    assert race.racer("p1").car.z > race.racer("p2").car.z + 10_000
    assert race.racer("p1").next_row >= 1


@pytest.mark.parametrize("level", config.LEVELS)
def test_controls_are_in_range_and_deterministic(level):
    def trace(seed):
        race = Race(seed=seed, players=1)
        drivers = ai.field(race, seed, level)
        out = []
        for _ in range(900):
            controls = ai.drive(race, drivers)
            out.append(tuple(controls.values()))
            race.update(DT, controls)
        return out
    a = trace(3)
    assert a == trace(3)
    assert a != trace(4)
    for frame in a:
        for c in frame:
            assert -1 <= c.steer <= 1 and 0 <= c.brake <= 1
            assert config.PACE_LIMITS[0] <= c.pace <= config.PACE_LIMITS[1]


def test_bots_hold_their_own_offsets_from_the_line_spread_across_the_field():
    for seed in range(5):
        race = Race(seed=seed, players=2)
        offsets = sorted(d.offset for d in ai.field(race, seed, players="TOUGH").values())
        assert len(offsets) == config.CARS
        assert offsets[0] == pytest.approx(-config.BOT_OFFSET_MAX)
        assert offsets[-1] == pytest.approx(config.BOT_OFFSET_MAX)
        gaps = [b - a for a, b in zip(offsets, offsets[1:])]
        assert min(gaps) == pytest.approx(2 * config.BOT_OFFSET_MAX / (config.CARS - 1))
    assert abs(Driver("cpu1", "TOUGH", 1).offset) <= config.BOT_OFFSET_MAX  # alone: random


def test_the_attract_field_has_a_driver_for_every_car():
    race = Race(seed=1, players=2)
    drivers = ai.field(race, 1, "TOUGH", players="TOUGH")
    assert list(drivers) == [r.car.id for r in race.racers]
    assert drivers["p1"].skill is drivers["p2"].skill is SKILLS["TOUGH"]
    assert all(d.level == "TOUGH" for d in drivers.values())


# --- Gates ---------------------------------------------------------------------------------


def lap_alone(seed, skill, car_id="cpu1"):
    """One lap of rows for one bot driving alone, with empty boxes (no SPLIT or QEC)."""
    race = Race(seed=seed, players=1)
    race.roll_item = lambda place, **kw: None
    b = Driver(car_id, skill, seed)
    events = []
    while race.racer(car_id).next_row < config.ROWS_PER_LAP:
        controls = alone(race, car_id)
        controls[car_id] = b.controls(race)
        events += [e for e in race.update(DT, controls) if e.car == car_id]
    return events


def count(events, kind):
    return sum(e.kind == kind for e in events)


@pytest.mark.parametrize("level", config.LEVELS)
def test_a_bot_takes_the_right_arch_by_its_aim(level):
    rows = 20 * config.ROWS_PER_LAP
    got = sum(count(lap_alone(seed, level), "right") for seed in range(20)) / rows
    if level == "BRUTAL":
        assert got == 1.0
    else:
        assert got == pytest.approx(SKILLS[level].aim, abs=0.1)


def test_a_bot_that_misses_goes_through_a_decoy_or_the_gap():
    events = [e for seed in range(20) for e in lap_alone(seed, custom(aim=0.0))]
    assert count(events, "right") == 0
    assert count(events, "wrong") > 0 and count(events, "miss") > 0


# --- Braking, pace and avoidance ------------------------------------------------------------


def brake_frames(level):
    race = Race(seed=1, players=1)
    b = Driver("cpu1", level, 1)
    braked = 0
    while race.racer("cpu1").laps < 1:
        controls = alone(race, "cpu1")
        controls["cpu1"] = c = b.controls(race)
        braked += c.brake > 0 and abs(c.steer) < config.DRIFT_STEER  # a brake, not a drift
        race.update(DT, controls)
    return braked


def test_only_easy_brakes_into_sharp_curves():
    # (the better ones drift there instead: stick back *and* steered)
    assert brake_frames("EASY") > 0
    assert brake_frames("TOUGH") == brake_frames("BRUTAL") == 0


def test_rubber_banding_is_mild_the_leader_slower_the_last_faster():
    race = Race(seed=1, players=1)
    c1 = race.racer("cpu1")
    paces = {}
    for level in config.LEVELS:
        b = Driver("cpu1", level, 1)
        c1.place = 1
        first = b.pace(race)
        c1.place = config.CARS
        paces[level] = (first, b.pace(race))
    first, last = paces["TOUGH"]
    assert first < last and 0.95 <= first and last <= 1.05
    assert paces["EASY"][1] <= SKILLS["EASY"].pace  # EASY never speeds up to catch you
    assert paces["BRUTAL"][0] == 1.0  # BRUTAL never eases off in front


def test_a_better_level_has_a_better_pace():
    race = Race(seed=1, players=1)
    race.racer("cpu1").place = 3
    easy, tough, brutal = (Driver("cpu1", k, 1).pace(race) for k in config.LEVELS)
    assert easy < tough < brutal


def test_easy_looks_at_the_traffic_now_and_then_brutal_every_frame():
    looks = {}
    for level in config.LEVELS:
        race = Race(seed=1, players=1)
        b = Driver("cpu1", level, 1)
        calls = []
        real = b._avoid
        b._avoid = lambda *a, real=real, calls=calls: calls.append(1) or real(*a)
        for _ in range(120):  # two seconds
            controls = alone(race, "cpu1")
            controls["cpu1"] = b.controls(race)
            race.update(DT, controls)
        looks[level] = len(calls)
    assert looks["BRUTAL"] == 120
    assert 6 <= looks["EASY"] <= 16  # about every 0.2 s (and on every new arch)
    assert looks["EASY"] < looks["TOUGH"] < looks["BRUTAL"]


def test_easy_weaves_off_its_line_brutal_holds_it():
    def sway(level):
        race = Race(seed=1, players=1, finish_all=True)
        b = Driver("cpu1", level, 1, offset=0.0)
        ahead_of(race, "cpu1", {})
        offs = []
        looked = b._looked

        def spy(race, me, goal, arch):
            offs.append(goal - race.track.segment_at(me.car.z + config.BOT_LOOK).line)
            return looked(race, me, goal, arch)
        b._looked = spy
        for _ in range(300):  # five seconds
            race.update(DT, {"cpu1": b.controls(race)})
        return max(offs) - min(offs)
    assert sway("EASY") > SKILLS["EASY"].weave  # more than half its sway's swing
    assert sway("BRUTAL") == 0.0


def test_a_bot_steers_round_a_slower_car_ahead_of_it():
    race = Race(seed=1, players=1, finish_all=True)
    b = Driver("cpu1", "BRUTAL", 1)
    c1, p1 = race.racer("cpu1"), race.racer("p1")
    for i, r in enumerate(race.racers):
        if r.car.id not in ("cpu1", "p1"):
            r.car.z = -50_000.0 - 1000.0 * i  # out of the way
    z = race.track.segments[_straight(race)].z
    c1.car.z, c1.car.x, c1.car.speed = z, b.offset, TOP
    p1.car.z, p1.car.x, p1.car.speed = z + 4000.0, b.offset, 0.6 * TOP  # ~0.9 s ahead
    c1.next_row = p1.next_row = len(race.rows)  # no gates to aim for
    bumps = []
    for _ in range(120):
        steer, brake = aim(p1.car, b.offset, race.track.segment_at(p1.car.z))
        controls = {"cpu1": b.controls(race), "p1": Controls(steer, brake)}
        p1.car.speed = min(p1.car.speed, 0.6 * TOP)
        bumps += [e for e in race.update(DT, controls) if e.kind == "bump"]
    assert c1.car.z > p1.car.z  # it got past
    assert bumps == []


def test_a_bot_drops_behind_a_car_alongside_that_stands_between_it_and_its_arch():
    for seed in range(50):
        race = Race(seed=seed, players=1)
        k = next((i for i, row in enumerate(race.rows[:8]) if len(row.arches) == 1
                  and row.arches[0].offset < -0.4), None)
        if k is not None:
            break
    row = race.rows[k]
    b = Driver("cpu1", "BRUTAL", seed, offset=0.0)
    c1, p1 = race.racer("cpu1"), race.racer("p1")
    for i, r in enumerate(race.racers):
        _skip_rows(r, k)
        if r.car.id not in ("cpu1", "p1"):
            r.car.z = -50_000.0 - 1000.0 * i
    z = row.z - 1.4 * TOP
    c1.car.z, c1.car.x, c1.car.speed = z, 0.6, TOP
    p1.car.z, p1.car.x, p1.car.speed = z + 100.0, 0.2, TOP  # alongside, a nose ahead
    events = []
    while c1.next_row == k:
        steer, brake = aim(p1.car, 0.2, race.track.segment_at(p1.car.z))
        events += race.update(DT, {"cpu1": b.controls(race), "p1": Controls(steer, brake)})
    assert ("right", "cpu1") in [(e.kind, e.car) for e in events]


def test_a_bot_makes_way_for_a_faster_car_closing_from_behind():
    race = Race(seed=1, players=1, finish_all=True)
    b = Driver("cpu1", "BRUTAL", 1, offset=0.0)
    c1, p1 = race.racer("cpu1"), race.racer("p1")
    for i, r in enumerate(race.racers):
        r.next_row = len(race.rows)
        if r.car.id not in ("cpu1", "p1"):
            r.car.z = -50_000.0 - 1000.0 * i
    z = race.track.segments[_straight(race)].z
    c1.car.z, c1.car.x, c1.car.speed = z + 3500.0, 0.0, TOP
    p1.car.z, p1.car.x, p1.car.speed = z, 0.0, 1.4 * TOP
    p1.car.give_boost(0.4, 10.0)  # a boosted player who doesn't steer round anything
    bumps = []
    for _ in range(90):
        steer, brake = aim(p1.car, 0.0, race.track.segment_at(p1.car.z))
        controls = {"cpu1": b.controls(race), "p1": Controls(steer, brake)}
        bumps += [e for e in race.update(DT, controls) if e.kind == "bump"]
    assert p1.car.z > c1.car.z  # it got by
    assert bumps == []


def test_two_bots_share_one_arch_side_by_side():
    for seed in range(50):
        race = Race(seed=seed, players=1)
        k = next((i for i, row in enumerate(race.rows[:8]) if len(row.arches) == 1
                  and abs(row.arches[0].offset) < 0.3), None)
        if k is not None:
            break
    row = race.rows[k]
    c1, c2 = race.racer("cpu1"), race.racer("cpu2")
    bots = {"cpu1": Driver("cpu1", "BRUTAL", seed, offset=-0.3),
            "cpu2": Driver("cpu2", "BRUTAL", seed, offset=0.3)}
    for i, r in enumerate(race.racers):
        _skip_rows(r, k)
        if r.car.id not in bots:
            r.car.z = -50_000.0 - 1000.0 * i
    z = row.z - 2.0 * TOP
    for r, x in ((c1, -0.3), (c2, 0.3)):
        r.car.z, r.car.x, r.car.speed = z, x, TOP
    events = []
    while c1.next_row == k or c2.next_row == k:
        events += race.update(DT, ai.drive(race, bots))
    gates = [(e.kind, e.car) for e in events if e.kind in ("right", "wrong", "miss")]
    assert sorted(gates) == [("right", "cpu1"), ("right", "cpu2")]
    assert not [e for e in events if e.kind == "bump"]


def _skip_rows(racer, k):
    """Make row k the car's next, its slots before it missed."""
    while racer.circuit.filled < k:
        racer.circuit.take(racer.circuit.filled, None)
    racer.next_row = k


def _straight(race):
    """A segment starting 40 straight segments with no gate row or box near."""
    segs = race.track.segments
    for i in range(len(segs) - 40):
        if all(segs[j].curve == 0 for j in range(i, i + 40)):
            return i
    raise AssertionError("no straight")


# --- Items ---------------------------------------------------------------------------------


def test_a_bot_uses_qec_only_when_it_has_a_mistake():
    race = Race(seed=3, players=1)
    c1 = race.racer("cpu1")
    b = Driver("cpu1", "TOUGH", 3)
    c1.item = "QEC"
    assert not b.controls(race).item
    c1.circuit.take(0, None)
    assert b.controls(race).item


def test_a_bot_uses_split_just_before_a_row_with_decoys():
    race = Race(seed=3, players=1)
    c1 = race.racer("cpu1")
    b = Driver("cpu1", "TOUGH", 3)
    many = next(i for i, row in enumerate(race.rows) if len(row.arches) > 1)
    lone = next(i for i, row in enumerate(race.rows) if len(row.arches) == 1)
    c1.item = "SPLIT"
    c1.car.speed = TOP
    for index, want in ((many, True), (lone, False)):
        c1.next_row = index
        c1.car.z = race.rows[index].z - 0.3 * TOP
        assert b.controls(race).item is want
        c1.car.z = race.rows[index].z - 3 * TOP  # too far yet
        assert not b.controls(race).item


def ahead_of(race, me, gaps, x=0.0):
    """Put `me` on a straight at top speed and the cars in `gaps` (id: dz) around it, the
    rest far behind; no rows or boxes near."""
    z = race.track.segments[_straight(race)].z
    for i, r in enumerate(race.racers):
        r.next_row, r.next_box = len(race.rows), len(race.box_lines)
        r.car.speed, r.car.x = TOP, x
        r.car.z = z + gaps.get(r.car.id, -200_000.0 - 1000.0 * i)
    race.racer(me).car.z = z
    return race.racer(me)


def test_a_bot_fires_measure_only_at_a_car_ahead_in_range():
    race = Race(seed=3, players=1, finish_all=True)
    b = Driver("cpu1", "TOUGH", 3)
    c1 = ahead_of(race, "cpu1", {"p1": config.MEASURE_RANGE + 3000.0, "cpu2": -2000.0})
    c1.item = "MEASURE"
    assert not b.controls(race).item
    race.racer("p1").car.z -= 6000.0
    assert b.controls(race).item
    race.racer("p1").car.tunnel(1.0)  # no use: it is immune
    assert not b.controls(race).item


def test_a_bot_drops_decoherence_with_a_car_close_behind_it():
    race = Race(seed=3, players=1, finish_all=True)
    b = Driver("cpu1", "TOUGH", 3)
    c1 = ahead_of(race, "cpu1", {"p1": -12_000.0})
    c1.item = "DECOHERENCE"
    assert not b.controls(race).item
    race.racer("p1").car.z = c1.car.z - 2500.0
    assert b.controls(race).item
    race.racer("p1").car.x = 0.9  # well to the side: it would miss the cloud
    assert not b.controls(race).item


def test_a_bot_tunnels_in_traffic_before_a_hazard_or_a_shot():
    race = Race(seed=3, players=1, finish_all=True)
    b = Driver("cpu1", "TOUGH", 3)
    c1 = ahead_of(race, "cpu1", {"p1": 20_000.0})
    c1.item = "TUNNEL"
    assert not b.controls(race).item
    # in traffic: a car just ahead in its path
    race.racer("p1").car.z = c1.car.z + 500.0
    assert b.controls(race).item
    race.racer("p1").car.z = c1.car.z + 20_000.0
    # a shot coming for it
    race.racer("cpu2").car.z = c1.car.z - 5000.0
    race.racer("cpu2").item = "MEASURE"
    race.update(DT, {"cpu2": Controls(item=True)})
    assert race.shots and race.shots[0].target == "cpu1"
    assert b.controls(race).item


def test_a_bot_tunnels_through_a_cloud_it_cannot_steer_round():
    race = Race(seed=3, players=1, finish_all=True)
    b = Driver("cpu1", "TOUGH", 3)
    c1 = ahead_of(race, "cpu1", {"p1": 30_000.0})
    c1.item = "TUNNEL"
    race.clouds.append(Cloud(0, c1.car.z + 0.3 * TOP, c1.car.x, "p1", 5.0))
    assert b.controls(race).item
    race.clouds[0].z = c1.car.z + 2.0 * TOP  # far yet: it can still steer round it
    assert not b.controls(race).item


def test_a_bot_that_fumbles_an_item_uses_it_soon_wherever_it_is():
    race = Race(seed=3, players=1, finish_all=True)
    b = Driver("cpu1", custom(items=0.0), 3)
    c1 = ahead_of(race, "cpu1", {})  # nobody ahead: a smart MEASURE would wait
    c1.item = "MEASURE"
    events = []
    for _ in range(round(config.BOT_FUMBLE / DT) + 2):
        events += race.update(DT, {"cpu1": b.controls(race)})
    assert ("item", "MEASURE") in [(e.kind, e.value) for e in events]
    assert "fizzle" in [e.kind for e in events]  # wasted (a smart one would have waited)


def test_easy_fumbles_about_half_its_items_tough_and_brutal_none():
    for level, lo, hi in (("EASY", 0.3, 0.7), ("TOUGH", 0, 0), ("BRUTAL", 0, 0)):
        fumbled = 0
        for seed in range(40):
            race = Race(seed=seed, players=1)
            b = Driver("cpu1", level, seed)
            race.racer("cpu1").item = "QEC"
            b.controls(race)
            fumbled += not b._plan[1]
        assert lo <= fumbled / 40 <= hi, level


def test_brutal_knows_the_rivals_items_and_never_measures_a_car_that_can_tunnel():
    race = Race(seed=3, players=1, finish_all=True)
    c1 = ahead_of(race, "cpu1", {"p1": 6000.0})
    c1.item = "MEASURE"
    race.racer("p1").item = "TUNNEL"
    assert Driver("cpu1", "TOUGH", 3).controls(race).item
    assert not Driver("cpu1", "BRUTAL", 3).controls(race).item
    race.racer("p1").item = None
    assert Driver("cpu1", "BRUTAL", 3).controls(race).item


def test_a_bot_uses_a_spare_qec_once_its_rows_are_over():
    race = Race(seed=3, players=1)
    c1 = race.racer("cpu1")
    c1.item = "QEC"
    b = Driver("cpu1", "BRUTAL", 3)
    assert not b.controls(race).item  # no mistake yet, and rows to come
    c1.next_row = len(race.rows)
    assert b.controls(race).item  # nothing left to fix: it frees the slot for another item


def lap_of_drifts(seed, skill):
    race = Race(seed=seed, players=1)
    race.roll_item = lambda place, **kw: None
    b = Driver("cpu1", skill, seed)
    turbos = 0
    c1 = race.racer("cpu1")
    while c1.laps < 1:
        controls = alone(race, "cpu1")
        controls["cpu1"] = b.controls(race)
        turbos += sum(e.kind == "turbo" and e.car == "cpu1"
                      for e in race.update(DT, controls))
    return turbos


def test_a_bot_drifts_the_sharpest_curves_by_its_level():
    # THE FRIDGE has three: the two halves of the s-bend and the coax corner
    assert lap_of_drifts(1, "BRUTAL") == 3
    drifted = sum(lap_of_drifts(seed, custom(drift=0.6)) for seed in range(12))
    assert 0.4 * 36 <= drifted <= 0.8 * 36
    # EASY brakes instead (it drifts only when boosted too fast to hold a curve otherwise)
    assert sum(lap_of_drifts(seed, "EASY") for seed in range(4)) <= 2


def test_boosted_into_a_sharp_curve_every_level_drifts_to_stay_on_the_road():
    race = Race(seed=3, players=1, finish_all=True)
    seg = next(s for s in race.track.segments if s.curve > config.SHARP_CURVE)
    for level in config.LEVELS:
        b = Driver("cpu1", custom(level, drift=0.0), 3)
        me = race.racer("cpu1")
        me.next_row = len(race.rows)
        me.car.z, me.car.x, me.car.speed = seg.z, 0.0, 2.0 * TOP
        me.car.give_boost(1.0, 5.0)
        race.clouds[:] = [Cloud(0, seg.z + 0.5 * TOP, 0.6, "p1", 5.0)]  # it is dodging, too
        c = b.controls(race)
        assert c.brake == 1.0 and c.steer >= config.DRIFT_STEER, level


def storm_alone(seed, skill, right=4):
    """A bot driving alone through its own final-lap storm: the hazards it hits."""
    race = Race(seed=seed, players=1)
    race.roll_item = lambda place, **kw: None
    b = Driver("cpu1", skill, seed)
    c1 = race.racer("cpu1")
    c = c1.circuit
    for slot in range(config.SLOTS):
        c.take(slot, c.target[slot] if slot < right else None)
    c1.next_row, c1.laps = len(race.rows), config.LAPS - 1 - 1
    c1.next_box = len(race.box_lines)
    c1.car.z = (config.LAPS - 1) * race.lap_length - 20.0
    c1.car.speed = TOP
    hits = 0
    while not c1.finished:
        controls = alone(race, "cpu1")
        controls["cpu1"] = b.controls(race)
        hits += sum(e.kind == "hazard" and e.car == "cpu1" for e in race.update(DT, controls))
    return hits, len(c1.hazards)


def test_a_bot_dodges_the_storm_by_what_it_sees():
    best = [storm_alone(seed, "BRUTAL") for seed in range(6)]
    worst = [storm_alone(seed, custom(sees=0.0)) for seed in range(6)]
    assert all(n == 24 for _, n in best)
    assert sum(h for h, _ in best) <= 1
    assert sum(h for h, _ in worst) >= 10


def test_a_blind_bot_picks_its_arch_at_half_its_aim():
    right = picks = 0
    for seed in range(200):
        race = Race(seed=seed, players=1)
        b = Driver("cpu1", custom(aim=0.8), seed)
        race.racer("cpu1").blind_time = 1.0
        _, arch = b._row_aim(0, race.rows[0], 0.0, race.racer("cpu1"))
        picks += 1
        right += arch is not None and arch.right
    assert right / picks == pytest.approx(0.8 * config.BOT_BLIND_SKILL, abs=0.08)


def test_a_bot_queueing_behind_a_car_brakes_rather_than_drifts():
    race = Race(seed=3, players=1, finish_all=True)
    b = Driver("cpu1", "TOUGH", 3)
    c1 = ahead_of(race, "cpu1", {}, x=-0.5)
    b._avoid = lambda race, me, goal, arch: (0.9, 0.6)  # far to the side, and easing off
    c = b.controls(race)
    assert c.brake == pytest.approx(0.6) and abs(c.steer) < config.DRIFT_STEER
    race.update(DT, {"cpu1": c})
    assert not c1.car.drifting


def test_the_curves_are_kept_per_track_object():
    import gc

    from gate_prix.track import Track
    gentle = Track([0.0] * 50 + [3.0] * 20 + [0.0] * 30, [0.0] * 100)
    assert ai._curves(gentle) == {i: 0 for i in range(50, 70)}
    assert gentle in ai._CURVES
    other = Track([3.0] * 10 + [0.0] * 90, [0.0] * 100)
    assert ai._curves(other) == {i: 0 for i in range(10)}
    n = len(ai._CURVES)
    del gentle
    gc.collect()
    assert len(ai._CURVES) == n - 1  # held weakly: a new track can't inherit its map


# --- Whole races: who beats which level ---------------------------------------------------


def test_every_bot_finishes_every_race(races):
    for race, drivers, _ in races:
        assert all(race.racer(car_id).finished for car_id in drivers)


def test_the_tough_bots_take_about_three_rows_in_four_right(races):
    # gates driven through right (a SPLIT clone's count), not the slots QEC repaired
    bots = [k for k in races[0][1]]
    right = sum(e.kind == "right" and e.car in bots for _, _, events in races for e in events)
    assert 0.68 <= right / (len(races) * len(bots) * config.SLOTS) <= 0.85


def test_a_perfect_scripted_player_beats_tough_nearly_always(races):
    # every right arch, no drifting and no items: it has to work for it (by a few seconds)
    wins = sum(race.results()[0] == "p1" for race, _, _ in races)
    assert wins >= 18
    # every right arch, but for the odd collapse just before a row (a bot's MEASURE)
    right = [sum(race.racer("p1").circuit.results) for race, _, _ in races]
    assert statistics.mean(right) >= 15.5 and min(right) >= 14


def test_a_first_time_visitor_beats_easy_most_of_the_time():
    # the right arch on 60% of the rows, 60% of the hazards seen, no drifting, no items
    wins = sum(race_to_the_end(seed, Scripted(seed, 0.6, 0.6), "EASY")[0].results()[0] == "p1"
               for seed in range(10))
    assert wins >= 8


def test_the_same_visitor_loses_to_tough_and_a_perfect_player_to_brutal():
    tough = sum(race_to_the_end(seed, Scripted(seed, 0.6, 0.6))[0].results()[0] == "p1"
                for seed in range(6))
    brutal = sum(race_to_the_end(seed, level="BRUTAL")[0].results()[0] == "p1"
                 for seed in range(6))
    assert tough <= 1 and brutal <= 2


def test_races_stay_close_at_tough():
    gaps = []
    for seed in SEEDS:
        race, _, _ = race_to_the_end(seed, p1=None)  # P1 driven by the AI too
        times = sorted(r.finish_time for r in race.racers)
        gaps.append(times[-1] - times[0])
    assert statistics.median(gaps) < 15.0


def test_the_bots_use_their_items(races):
    # the bots' items (the scripted player never uses any)
    used = sum(e.kind == "item" and e.car != "p1" for _, _, events in races for e in events)
    got = sum(e.kind == "box" and e.value is not None and e.car != "p1"
              for _, _, events in races for e in events)
    assert got > 0 and used >= 0.8 * got
    kinds = {e.value for _, _, events in races for e in events if e.kind == "item"}
    assert kinds == set(config.ITEMS)  # every one of them
