"""The CPU racers: steering, gates, braking, items, pace, and whole races over 20 seeds."""

import statistics

import pytest

from gate_prix import bot, config
from gate_prix.bot import Bot
from gate_prix.car import Controls, aim
from gate_prix.race import Race

DT = 1 / 60
TOP = config.TOP_SPEED
SEEDS = range(20)


def perfect(race, racer):
    """A scripted player: the racing line, and the right arch of every row from 1.5 s out."""
    car = racer.car
    goal = race.track.segment_at(car.z + 600.0).line
    if racer.next_row < len(race.rows):
        row = race.rows[racer.next_row]
        if row.z - car.z < 1.5 * TOP:
            goal = next(a.offset for a in row.arches if a.right)
    return Controls(*aim(car, goal, race.track.segment_at(car.z)))


def park(race, racer):
    car = racer.car
    return Controls(*aim(car, 2.1 if car.lane > 0 else -2.1, race.track.segment_at(car.z)))


def alone(race, car_id):
    """Park every other car off the road."""
    return {r.car.id: park(race, r) for r in race.racers if r.car.id != car_id}


def race_to_the_end(seed, p1=perfect):
    """A 1P race, P1 driven by `p1`, the five CPU racers by their bots, until all finish."""
    race = Race(seed=seed, players=1, finish_all=True)
    if p1 is None:  # a bot of the field's middle skill, as in the attract race
        bots = bot.field(race, seed, players=statistics.median(bot.skills(config.CPU_CARS_1P)))
    else:
        bots = bot.cpu_bots(race, seed)
    events = []
    while not race.over and race.time < 300.0:
        controls = bot.drive(race, bots)
        if p1 is not None:
            controls["p1"] = p1(race, race.racer("p1"))
        events += race.update(DT, controls)
    return race, bots, events


@pytest.fixture(scope="module")
def races():
    return [race_to_the_end(seed) for seed in SEEDS]


# --- The field -----------------------------------------------------------------------------


def test_skills_spread_from_085_down_to_06():
    assert bot.skills(5) == pytest.approx([0.85, 0.7875, 0.725, 0.6625, 0.6])
    assert bot.skills(4) == pytest.approx([0.85, 0.85 - 0.25 / 3, 0.6 + 0.25 / 3, 0.6])
    assert bot.skills(1) == pytest.approx([0.85])


@pytest.mark.parametrize("players, cpus", [(1, config.CPU_CARS_1P), (2, config.CPU_CARS_2P)])
def test_every_cpu_racer_gets_a_bot_the_best_at_the_front(players, cpus):
    race = Race(seed=1, players=players)
    bots = bot.cpu_bots(race, 1)
    cpu_ids = [r.car.id for r in race.racers if not r.player]
    assert list(bots) == cpu_ids and len(bots) == cpus
    assert [b.skill for b in bots.values()] == pytest.approx(bot.skills(cpus))
    assert all(b.car_id == car_id for car_id, b in bots.items())


def test_a_bot_drives_any_car_even_a_player():
    race = Race(seed=2, players=2)
    p1 = Bot("p1", 0.7, seed=2)
    for _ in range(600):
        race.update(DT, {"p1": p1.controls(race)})
    assert race.racer("p1").car.z > race.racer("p2").car.z + 10_000
    assert race.racer("p1").next_row >= 1


def test_bot_controls_are_in_range_and_deterministic():
    def trace(seed):
        race = Race(seed=seed, players=1)
        bots = bot.cpu_bots(race, seed)
        out = []
        for _ in range(900):
            controls = bot.drive(race, bots)
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
        offsets = sorted(b.offset for b in bot.field(race, seed, players=0.7).values())
        assert len(offsets) == config.CARS
        assert offsets[0] == pytest.approx(-config.BOT_OFFSET_MAX)
        assert offsets[-1] == pytest.approx(config.BOT_OFFSET_MAX)
        gaps = [b - a for a, b in zip(offsets, offsets[1:])]
        assert min(gaps) == pytest.approx(2 * config.BOT_OFFSET_MAX / (config.CARS - 1))
    assert abs(Bot("green", 0.7, 1).offset) <= config.BOT_OFFSET_MAX  # alone: random


def test_the_attract_field_has_a_bot_for_every_car():
    race = Race(seed=1, players=2)
    bots = bot.field(race, 1, players=0.7)
    assert list(bots) == [r.car.id for r in race.racers]
    assert bots["p1"].skill == bots["p2"].skill == 0.7
    assert bots["green"].skill == pytest.approx(config.BOT_SKILL_BEST)


# --- Gates ---------------------------------------------------------------------------------


def lap_alone(seed, skill, car_id="green"):
    """One lap of rows for one bot driving alone, with empty boxes (no SPLIT or QEC)."""
    race = Race(seed=seed, players=1)
    race.roll_item = lambda place, **kw: None
    b = Bot(car_id, skill, seed)
    events = []
    while race.racer(car_id).next_row < config.ROWS_PER_LAP:
        controls = alone(race, car_id)
        controls[car_id] = b.controls(race)
        events += [e for e in race.update(DT, controls) if e.car == car_id]
    return events


def count(events, kind):
    return sum(e.kind == kind for e in events)


def test_a_bot_takes_the_right_arch_with_its_skill():
    rows = 20 * config.ROWS_PER_LAP
    assert sum(count(lap_alone(seed, 1.0), "right") for seed in range(20)) == rows
    got = sum(count(lap_alone(seed, 0.6), "right") for seed in range(20)) / rows
    assert got == pytest.approx(0.6, abs=0.1)


def test_a_bot_that_misses_goes_through_a_decoy_or_the_gap():
    events = [e for seed in range(20) for e in lap_alone(seed, 0.0)]
    assert count(events, "right") == 0
    assert count(events, "wrong") > 0 and count(events, "miss") > 0


# --- Braking, pace and avoidance ------------------------------------------------------------


def brake_frames(skill):
    race = Race(seed=1, players=1)
    b = Bot("green", skill, 1)
    braked = 0
    while race.racer("green").laps < 1:
        controls = alone(race, "green")
        controls["green"] = c = b.controls(race)
        braked += c.brake > 0
        race.update(DT, controls)
    return braked


def test_only_low_skill_bots_brake_into_sharp_curves():
    assert brake_frames(0.6) > 0
    assert brake_frames(0.85) == 0


def test_rubber_banding_is_mild_the_leader_slower_the_last_faster():
    race = Race(seed=1, players=1)
    b = Bot("green", 0.75, 1)
    green = race.racer("green")
    green.place = 1
    first = b.pace(race)
    green.place = config.CARS
    last = b.pace(race)
    assert first < last
    assert 0.95 <= first and last <= 1.05


def test_a_better_bot_has_a_better_pace():
    race = Race(seed=1, players=1)
    race.racer("green").place = 3
    assert Bot("green", 0.6, 1).pace(race) < Bot("green", 0.85, 1).pace(race)


def test_a_bot_steers_round_a_slower_car_ahead_of_it():
    race = Race(seed=1, players=1, finish_all=True)
    b = Bot("green", 0.85, 1)
    green, p1 = race.racer("green"), race.racer("p1")
    for i, r in enumerate(race.racers):
        if r.car.id not in ("green", "p1"):
            r.car.z = -50_000.0 - 1000.0 * i  # out of the way
    z = race.track.segments[_straight(race)].z
    green.car.z, green.car.x, green.car.speed = z, b.offset, TOP
    p1.car.z, p1.car.x, p1.car.speed = z + 4000.0, b.offset, 0.6 * TOP  # ~0.9 s ahead
    green.next_row = p1.next_row = len(race.rows)  # no gates to aim for
    bumps = []
    for _ in range(120):
        steer, brake = aim(p1.car, b.offset, race.track.segment_at(p1.car.z))
        controls = {"green": b.controls(race), "p1": Controls(steer, brake)}
        p1.car.speed = min(p1.car.speed, 0.6 * TOP)
        bumps += [e for e in race.update(DT, controls) if e.kind == "bump"]
    assert green.car.z > p1.car.z  # it got past
    assert bumps == []


def test_a_bot_drops_behind_a_car_alongside_that_stands_between_it_and_its_arch():
    for seed in range(50):
        race = Race(seed=seed, players=1)
        k = next((i for i, row in enumerate(race.rows[:8]) if len(row.arches) == 1
                  and row.arches[0].offset < -0.4), None)
        if k is not None:
            break
    row = race.rows[k]
    b = Bot("green", 1.0, seed, offset=0.0)
    green, p1 = race.racer("green"), race.racer("p1")
    for i, r in enumerate(race.racers):
        _skip_rows(r, k)
        if r.car.id not in ("green", "p1"):
            r.car.z = -50_000.0 - 1000.0 * i
    z = row.z - 1.4 * TOP
    green.car.z, green.car.x, green.car.speed = z, 0.6, TOP
    p1.car.z, p1.car.x, p1.car.speed = z + 100.0, 0.2, TOP  # alongside, a nose ahead
    events = []
    while green.next_row == k:
        steer, brake = aim(p1.car, 0.2, race.track.segment_at(p1.car.z))
        events += race.update(DT, {"green": b.controls(race), "p1": Controls(steer, brake)})
    assert ("right", "green") in [(e.kind, e.car) for e in events]


def test_a_bot_makes_way_for_a_faster_car_closing_from_behind():
    race = Race(seed=1, players=1, finish_all=True)
    b = Bot("green", 0.85, 1, offset=0.0)
    green, p1 = race.racer("green"), race.racer("p1")
    for i, r in enumerate(race.racers):
        r.next_row = len(race.rows)
        if r.car.id not in ("green", "p1"):
            r.car.z = -50_000.0 - 1000.0 * i
    z = race.track.segments[_straight(race)].z
    green.car.z, green.car.x, green.car.speed = z + 3500.0, 0.0, TOP
    p1.car.z, p1.car.x, p1.car.speed = z, 0.0, 1.4 * TOP
    p1.car.give_boost(0.4, 10.0)  # a boosted player who doesn't steer round anything
    bumps = []
    for _ in range(90):
        steer, brake = aim(p1.car, 0.0, race.track.segment_at(p1.car.z))
        controls = {"green": b.controls(race), "p1": Controls(steer, brake)}
        bumps += [e for e in race.update(DT, controls) if e.kind == "bump"]
    assert p1.car.z > green.car.z  # it got by
    assert bumps == []


def test_two_bots_share_one_arch_side_by_side():
    for seed in range(50):
        race = Race(seed=seed, players=1)
        k = next((i for i, row in enumerate(race.rows[:8]) if len(row.arches) == 1
                  and abs(row.arches[0].offset) < 0.3), None)
        if k is not None:
            break
    row = race.rows[k]
    green, white = race.racer("green"), race.racer("white")
    bots = {"green": Bot("green", 1.0, seed, offset=-0.3), "white": Bot("white", 1.0, seed, offset=0.3)}
    for i, r in enumerate(race.racers):
        _skip_rows(r, k)
        if r.car.id not in bots:
            r.car.z = -50_000.0 - 1000.0 * i
    z = row.z - 2.0 * TOP
    for r, x in ((green, -0.3), (white, 0.3)):
        r.car.z, r.car.x, r.car.speed = z, x, TOP
    events = []
    while green.next_row == k or white.next_row == k:
        events += race.update(DT, bot.drive(race, bots))
    gates = [(e.kind, e.car) for e in events if e.kind in ("right", "wrong", "miss")]
    assert sorted(gates) == [("right", "green"), ("right", "white")]
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
    green = race.racer("green")
    b = Bot("green", 0.7, 3)
    green.item = "QEC"
    assert not b.controls(race).item
    green.circuit.take(0, None)
    assert b.controls(race).item


def test_a_bot_uses_split_just_before_a_row_with_decoys():
    race = Race(seed=3, players=1)
    green = race.racer("green")
    b = Bot("green", 0.7, 3)
    many = next(i for i, row in enumerate(race.rows) if len(row.arches) > 1)
    lone = next(i for i, row in enumerate(race.rows) if len(row.arches) == 1)
    green.item = "SPLIT"
    green.car.speed = TOP
    for index, want in ((many, True), (lone, False)):
        green.next_row = index
        green.car.z = race.rows[index].z - 0.3 * TOP
        assert b.controls(race).item is want
        green.car.z = race.rows[index].z - 3 * TOP  # too far yet
        assert not b.controls(race).item


# --- Whole races, 20 seeds ------------------------------------------------------------------


def test_every_cpu_finishes_every_race(races):
    for race, bots, _ in races:
        assert all(race.racer(car_id).finished for car_id in bots)


def test_the_best_cpus_right_gate_rate_is_80_to_90_percent(races):
    # gates it drove through right (a SPLIT clone's count), not the slots QEC repaired
    right = sum(e.kind == "right" and e.car == "green" for _, _, events in races for e in events)
    assert 0.80 <= right / (len(races) * config.SLOTS) <= 0.90


def test_a_perfect_scripted_player_wins_every_race(races):
    for race, _, _ in races:
        assert race.results()[0] == "p1"
        assert all(race.racer("p1").circuit.results)


def test_races_stay_close():
    gaps = []
    for seed in SEEDS:
        race, _, _ = race_to_the_end(seed, p1=None)  # a bot of the field's middle skill
        times = sorted(r.finish_time for r in race.racers)
        gaps.append(times[-1] - times[0])
    assert statistics.median(gaps) < 15.0


def test_the_bots_use_their_items(races):
    used = sum(e.kind == "item" for _, _, events in races for e in events)
    got = sum(e.kind == "box" and e.value is not None for _, _, events in races for e in events)
    assert got > 0 and used >= 0.8 * got
