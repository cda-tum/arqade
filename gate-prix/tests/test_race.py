import random

import pytest

from gate_prix import circuit, config, track
from gate_prix.car import Controls, aim
from gate_prix.race import Event, Race, arch_at

DT = 1 / 60
TOP = config.TOP_SPEED


# --- Drivers ------------------------------------------------------------------------------


def hold(race, racer, x):
    """Controls that keep a car at x."""
    car = racer.car
    steer, brake = aim(car, x, race.track.segment_at(car.z))
    return Controls(steer, brake)


def perfect(race, racer):
    """The racing line, and the right arch of every row from 1.5 s out."""
    car = racer.car
    goal = race.track.segment_at(car.z + 600.0).line
    if racer.next_row < len(race.rows):
        row = race.rows[racer.next_row]
        if row.z - car.z < 1.5 * TOP:
            goal = next(a.offset for a in row.arches if a.right)
    steer, brake = aim(car, goal, race.track.segment_at(car.z))
    return Controls(steer, brake)


def park(race, racer):
    """Off the road on its own lane's side, out of everyone's way."""
    return hold(race, racer, 2.1 if racer.car.lane > 0 else -2.1)


def run(race, p1_driver, until=None, limit=200.0):
    """Drive p1 with p1_driver, every other car parked off the road."""
    events = []
    while not race.over and race.time < limit:
        controls = {
            r.car.id: (p1_driver(race, r) if r.car.id == "p1" else park(race, r))
            for r in race.racers
        }
        events += race.update(DT, controls)
        if until and until(events):
            break
    return events


@pytest.fixture(scope="module")
def perfect_race():
    race = Race(seed=7, players=1)
    return race, run(race, perfect)


@pytest.fixture(scope="module")
def missing_race():
    race = Race(seed=7, players=1)
    return race, run(race, lambda race, r: hold(race, r, 1.5),
                     until=lambda ev: any(e.kind == "check" and e.car == "p1" for e in ev))


def of(events, car, kind=None):
    return [e for e in events if e.car == car and (kind is None or e.kind == kind)]


def put(racer, z, x=None):
    """Teleport a car to race distance z, at top speed."""
    racer.car.z = z
    racer.car.speed = TOP
    if x is not None:
        racer.car.x = x


def cross(race, racer, x, dt=DT):
    """Put a car just before its next row at x, at top speed, and step one frame."""
    row = race.rows[racer.next_row]
    racer.car.z = row.z - 50.0
    racer.car.x = x
    racer.car.speed = TOP
    return [e for e in race.update(dt, {}) if e.car == racer.car.id]


# --- Building -----------------------------------------------------------------------------


def test_a_race_has_six_cars_players_first():
    race = Race(seed=1, players=2)
    ids = [r.car.id for r in race.racers]
    assert ids == ["p1", "p2", "green", "white", "lime", "steel"]
    assert [r.player for r in race.racers] == [True, True, False, False, False, False]
    race = Race(seed=1, players=1)
    assert [r.car.id for r in race.racers] == ["p1", "green", "white", "lime", "steel", "black"]
    assert len(race.racers) == config.CARS


def test_the_target_rows_and_circuits():
    race = Race(seed=3, players=1)
    assert race.target == circuit.random_target(random.Random(3), config.SLOTS)
    assert race.rows == track.gate_rows(race.track, race.target, 3)
    for r in race.racers:
        assert r.circuit.target == race.target
        assert r.circuit.filled == 0
        assert r.next_row == 0 and r.laps == 0 and r.lap == 1


def test_the_grid_is_behind_the_line_players_at_the_back_in_their_colours():
    race = Race(seed=1, players=2)
    cars = {r.car.id: r.car for r in race.racers}
    assert all(c.z < 0 for c in cars.values())
    assert cars["p1"].x < 0 < cars["p2"].x  # P1 blue on the left, P2 red on the right
    assert cars["p1"].z == cars["p2"].z  # side by side: neither player starts ahead
    assert max(cars["p1"].z, cars["p2"].z) < min(c.z for k, c in cars.items() if k[0] != "p")
    assert (cars["p1"].colour, cars["p2"].colour) == ("p1", "p2")
    # no two cars overlap on the grid
    cs = list(cars.values())
    for i, a in enumerate(cs):
        for b in cs[i + 1:]:
            assert abs(a.x - b.x) >= config.CAR_WIDTH or abs(a.z - b.z) >= config.CAR_LENGTH


def test_the_rng_is_kept_for_the_items():
    rng = random.Random(5)
    assert Race(seed=1, players=1, rng=rng).rng is rng
    assert isinstance(Race(seed=1, players=1).rng, random.Random)


def test_the_item_rng_is_its_own_stream_not_the_targets():
    a, b = Race(seed=1, players=1), Race(seed=1, players=1)
    assert a.rng.random() == b.rng.random()  # deterministic per seed
    assert Race(seed=1, players=1).rng.random() != random.Random(1).random()


# --- Arches -------------------------------------------------------------------------------


def test_arch_at_uses_the_arch_half_width():
    row = track.GateRow(0, 0.0, (track.Arch("H", -0.5, True), track.Arch("X", 0.3, False)))
    h = config.ARCH_HALF_WIDTH
    assert arch_at(row, -0.5).gate == "H"
    assert arch_at(row, -0.5 + h * 0.99).gate == "H"
    assert arch_at(row, -0.5 - h * 1.01) is None
    assert arch_at(row, 0.0) is None
    # a decoy is drawn smaller, and only what is drawn counts
    d = config.DECOY_HALF_WIDTH
    assert arch_at(row, 0.3 + d * 0.99).gate == "X"
    assert arch_at(row, 0.3 - d * 1.01) is None
    assert arch_at(row, 0.3 + (d + h) / 2) is None  # inside a right arch's width, not a decoy's


def test_an_arch_knows_its_own_half_width():
    assert track.Arch("H", 0.0, True).half_width == config.ARCH_HALF_WIDTH
    assert track.Arch("X", 0.0, False).half_width == config.DECOY_HALF_WIDTH


def right_x(race, racer):
    return next(a.offset for a in race.rows[racer.next_row].arches if a.right)


def test_a_right_arch_extends_the_streak_and_boosts_by_the_table():
    race = Race(seed=11, players=1)
    p1 = race.racers[0]
    for n in (1, 2, 3):
        events = cross(race, p1, right_x(race, p1))
        assert events == [Event("right", "p1", n)]
        assert p1.circuit.streak == n
        strength, seconds = config.streak_boost(n)
        assert p1.car.boost == strength
        assert p1.car.boost_time == pytest.approx(seconds)
    assert p1.circuit.results[:3] == [True, True, True]


def test_a_wrong_arch_resets_the_streak_and_a_missed_row_leaves_an_empty_slot():
    for seed in range(50):  # a race whose second row has a decoy
        race = Race(seed=seed, players=1)
        if len(race.rows[1].arches) > 1:
            break
    p1 = race.racers[0]
    cross(race, p1, right_x(race, p1))
    decoy = next(a for a in race.rows[1].arches if not a.right)
    assert cross(race, p1, decoy.offset) == [Event("wrong", "p1", 1)]
    assert p1.circuit.streak == 0 and p1.circuit.slots[1] == decoy.gate
    assert cross(race, p1, 1.5) == [Event("miss", "p1", 2)]
    assert p1.circuit.slots[2] is None and p1.circuit.results[2] is False


def test_the_arch_counts_where_the_car_is_as_it_crosses_the_row():
    race = Race(seed=11, players=1)
    p1 = race.racers[0]
    row = race.rows[0]  # on the start straight
    goal = right_x(race, p1)
    # over one long frame the car sweeps across the arch: it is outside it at both ends of
    # the frame, and inside it only as it crosses the row, half way through
    dt = 0.3
    put(p1, row.z - TOP * dt / 2, goal - 0.15 * config.STEER_RATE)
    events = race.update(dt, {"p1": Controls(steer=1.0)})
    assert abs(p1.car.x - goal) > config.ARCH_HALF_WIDTH
    assert of(events, "p1") == [Event("right", "p1", 1)]


def test_every_car_fills_its_own_circuit():
    race = Race(seed=11, players=2)
    p1, p2 = race.racers[:2]
    cross(race, p1, right_x(race, p1))
    assert p1.circuit.filled == 1 and p2.circuit.filled == 0


# --- Laps, the CIRCUIT CHECK and the finish ----------------------------------------------


def test_a_perfect_driver_gets_a_perfect_check_and_the_biggest_boost(perfect_race):
    race, events = perfect_race
    p1 = race.racers[0]
    checks = of(events, "p1", "check")
    assert checks == [Event("check", "p1", 0)]
    assert p1.check == 0
    assert config.check_boost(0) == (pytest.approx(1.0), pytest.approx(6.0))
    # the boost the check gave, read off the frame it happened
    assert p1.check_boost == config.check_boost(0)
    assert of(events, "p1", "warp") == [Event("warp", "p1", config.check_boost(0))]
    assert all(p1.circuit.results)
    assert [e.value for e in of(events, "p1", "right")] == list(range(1, 17))


def test_the_check_comes_at_the_start_of_lap_3(perfect_race):
    race, events = perfect_race
    kinds = [e.kind for e in of(events, "p1") if e.kind in ("lap", "check", "warp", "finish")]
    assert kinds == ["lap", "lap", "check", "warp", "finish"]
    i = [e.kind for e in of(events, "p1")].index("check")
    rights_before = [e for e in of(events, "p1")[:i] if e.kind == "right"]
    assert len(rights_before) == config.CHECK_SLOTS == config.SLOTS
    # the final lap is a gate-free sprint: no gate after the check
    assert not [e for e in of(events, "p1")[i:] if e.kind in ("right", "wrong", "miss")]


def to_the_check(race, racer, slots_right=16):
    """Fill a car's circuit (the first `slots_right` right, the rest missed) and put it just
    short of the line into the final lap, at top speed."""
    c = racer.circuit
    for slot in range(config.SLOTS):
        c.take(slot, c.target[slot] if slot < slots_right else None)
    racer.next_row = len(race.rows)
    racer.laps = config.LAPS - 2
    racer.next_box = race.box_index((config.LAPS - 1) * race.lap_length)
    put(racer, (config.LAPS - 1) * race.lap_length - 20.0, 0.0)


def test_the_check_boost_starts_after_the_freeze_and_the_car_keeps_moving():
    race = Race(seed=3, players=1)
    p1 = race.racers[0]
    to_the_check(race, p1, slots_right=14)
    events = of(race.update(DT, {}), "p1")
    assert Event("check", "p1", 2) in events
    assert p1.check_wait == pytest.approx(config.CHECK_FREEZE)
    assert p1.car.boost == 0.0
    z, frames, warp = p1.car.z, 0, []
    while not warp:
        frames += 1
        warp = of(race.update(DT, {}), "p1", "warp")
        assert frames <= round(config.CHECK_FREEZE / DT)
    assert frames == round(config.CHECK_FREEZE / DT)
    assert warp == [Event("warp", "p1", config.check_boost(2))]
    assert p1.check_wait == 0.0 and p1.warp_time == pytest.approx(race.time)
    assert p1.car.boost == pytest.approx(config.check_boost(2)[0])
    # all through the freeze the car drove on at top speed: no distance lost
    assert p1.car.z - z == pytest.approx(frames * DT * TOP, rel=0.01)


def test_the_cpus_get_the_check_by_their_own_circuits():
    race = Race(seed=3, players=1)
    green = race.racer("green")
    to_the_check(race, green, slots_right=11)
    events = of(race.update(DT, {}), "green")
    assert Event("check", "green", 5) in events
    events = []
    for _ in range(round(config.CHECK_FREEZE / DT)):
        events += of(race.update(DT, {}), "green", "warp")
    assert events == [Event("warp", "green", config.check_boost(5))]


def test_a_better_circuits_warp_passes_a_cpu_that_crossed_earlier():
    """The warp is strong and long enough to pass cars: a perfect circuit catches and
    passes a CPU with a typical 13/16 that crossed into the final lap 1.5 s earlier."""
    race = Race(seed=3, players=1)
    p1, green = race.racer("p1"), race.racer("green")
    to_the_check(race, p1, slots_right=16)
    to_the_check(race, green, slots_right=13)
    green.car.z += 1.5 * TOP
    p1.car.x, green.car.x = -0.3, 0.3
    for r in race.racers[2:]:
        put(r, race.lap_length / 2, 2.1)
    lanes = {"p1": -0.3, "green": 0.3}
    passed = None
    while race.time < 9.0 and passed is None:
        race.update(DT, {r.car.id: (hold(race, r, lanes[r.car.id]) if r.car.id in lanes
                                    else park(race, r)) for r in race.racers})
        p1.hazards = green.hazards = []  # the warp alone: no storm in either lane
        if p1.car.z > green.car.z:
            passed = race.time
    assert passed is not None
    assert passed < config.CHECK_FREEZE + config.check_boost(0)[1]  # while it still warps


def test_no_warp_without_a_check_boost():
    race = Race(seed=3, players=1)
    p1 = race.racers[0]
    to_the_check(race, p1, slots_right=0)
    events = []
    for _ in range(round(2 * config.CHECK_FREEZE / DT)):
        events += of(race.update(DT, {}), "p1")
    assert Event("check", "p1", 16) in events
    assert not [e for e in events if e.kind == "warp"] and p1.car.boost == 0.0


def test_a_check_under_5_percent_is_no_boost_and_no_warp():
    for right, none in ((3, True), (4, False), (16, False)):
        race = Race(seed=3, players=1)
        p1 = race.racers[0]
        to_the_check(race, p1, slots_right=right)
        events = []
        for _ in range(round(2 * config.CHECK_FREEZE / DT)):
            events += of(race.update(DT, {}), "p1")
        assert p1.check_right == right
        assert p1.check_boost_none is none
        assert bool([e for e in events if e.kind == "warp"]) is not none
        assert (p1.warp_time is None) is none
    assert config.CHECK_SHOW_MIN == 0.05
    assert config.check_boost(16 - 3)[0] < 0.05 <= config.check_boost(16 - 4)[0]
    assert Race(seed=1, players=1).racers[0].check_right is None


def test_a_right_gate_never_lowers_the_boost():
    race = Race(seed=7, players=1)
    p1 = race.racers[0]
    rights = 0
    while not race.over:
        # what the boost would be after this frame without a new gate
        survives = [s for s, t in p1.car.boosts if t > DT]
        expected = max(survives, default=0.0)
        controls = {r.car.id: (perfect(race, r) if r.car.id == "p1" else park(race, r))
                    for r in race.racers}
        events = race.update(DT, controls)
        if Event("right", "p1", p1.circuit.streak) in events:
            rights += 1
            assert p1.car.boost >= expected
    assert rights == config.SLOTS


def test_a_car_missing_every_row_gets_distance_16_and_the_smallest_boost(missing_race):
    race, events = missing_race
    p1 = race.racers[0]
    assert of(events, "p1", "check") == [Event("check", "p1", 16)]
    assert [e.kind for e in of(events, "p1") if e.kind in ("right", "wrong", "miss")] == ["miss"] * 16
    assert p1.check_boost == config.check_boost(16) == (0.0, 2.0)
    assert p1.car.boost == 0.0


def test_the_finish_and_the_end_of_the_race(perfect_race):
    race, events = perfect_race
    p1 = race.racers[0]
    assert race.over and p1.finished
    assert race.finish_order == ["p1"]
    assert p1.place == 1
    assert p1.finish_time == pytest.approx(race.time)
    # three laps of THE FRIDGE, well under the 120 s they take at top speed: the boosts
    assert 3 * race.track.lap_length() / TOP * 0.7 < p1.finish_time < 3 * race.track.lap_length() / TOP
    results = race.results()
    assert results[0] == "p1" and sorted(results) == sorted(r.car.id for r in race.racers)


def test_the_race_is_not_over_until_every_player_finishes():
    race = Race(seed=2, players=2)
    p1, p2 = race.racers[:2]
    end = 3 * race.track.lap_length()
    put(p1, end - 10.0)
    events = race.update(DT, {})
    assert Event("finish", "p1", 1) in events
    assert not race.over
    green = race.racers[2]
    put(green, end - 10.0, 1.9)
    events = race.update(DT, {})
    assert Event("finish", "green", 2) in events and not race.over
    put(p2, end - 10.0, -1.9)
    events = race.update(DT, {})
    assert Event("finish", "p2", 3) in events
    assert race.over
    assert race.finish_order == ["p1", "green", "p2"]
    assert race.results()[:3] == ["p1", "green", "p2"]


def test_a_finished_race_stops_changing():
    race = Race(seed=2, players=1)
    p1 = race.racers[0]
    put(p1, 3 * race.track.lap_length() - 10.0)
    race.update(DT, {})
    assert race.over
    snapshot = [(r.car.z, r.car.x) for r in race.racers]
    assert race.update(DT, {}) == []
    assert [(r.car.z, r.car.x) for r in race.racers] == snapshot


def test_the_check_fires_once_even_if_a_car_is_bumped_back_over_the_line():
    race = Race(seed=2, players=1)
    p1 = race.racers[0]
    lap = race.track.lap_length()
    put(p1, 2 * lap - 10.0)
    events = of(race.update(DT, {}), "p1")
    assert [e.kind for e in events].count("check") == 1
    put(p1, 2 * lap - 30.0)
    race.update(DT, {})
    race.update(DT, {})
    later = of(race.update(DT, {}), "p1")
    assert not [e for e in later if e.kind in ("check", "lap")]


# --- Places -------------------------------------------------------------------------------


def test_places_are_ordered_by_laps_then_distance():
    race = Race(seed=4, players=2)
    lap = race.track.lap_length()
    spots = {"p1": 1.5 * lap, "p2": 0.2 * lap, "green": 1.1 * lap, "white": 0.9 * lap,
             "lime": 5000.0, "steel": 2.2 * lap}
    for r in race.racers:
        r.car.z = spots[r.car.id]
        r.car.x = -1.9 + 0.75 * race.racers.index(r)  # nobody bumps
    race.update(1e-6, {})
    assert race.places() == ["steel", "p1", "green", "white", "p2", "lime"]
    assert {r.car.id: r.place for r in race.racers} == {
        "steel": 1, "p1": 2, "green": 3, "white": 4, "p2": 5, "lime": 6}


def test_a_finished_car_keeps_its_place_whoever_passes_it():
    race = Race(seed=4, players=2)
    lap = race.track.lap_length()
    p1 = race.racers[0]
    put(p1, 3 * lap - 10.0)
    race.update(DT, {})
    green = race.racers[2]
    put(green, 3 * lap + 5000.0, 1.9)  # further along now, but it crossed the line later
    race.update(DT, {})
    assert green.finished
    assert race.places()[:2] == ["p1", "green"]


# --- Bumps and determinism ----------------------------------------------------------------


def test_cars_that_touch_bump_once_and_cue_it():
    race = Race(seed=4, players=2)
    p1, p2 = race.racers[:2]
    p1.car.z = p2.car.z = 4000.0
    p1.car.x, p2.car.x = 0.0, 0.1
    p1.car.speed = p2.car.speed = TOP
    events = race.update(DT, {})
    assert Event("bump", "p1", "p2") in events and Event("bump", "p2", "p1") in events
    assert p2.car.x - p1.car.x >= config.CAR_WIDTH
    assert not [e for e in race.update(DT, {}) if e.kind == "bump"]


def test_cars_pressed_together_cue_one_bump_per_cooldown():
    race = Race(seed=4, players=2)
    p1, p2 = race.racers[:2]
    p1.car.z = p2.car.z = 4000.0
    p1.car.x, p2.car.x = 2.0, config.X_LIMIT  # P2 against the limit, P1 steering into it
    p1.car.speed = p2.car.speed = TOP
    bumps = []
    for _ in range(round(config.BUMP_COOLDOWN / DT) - 2):
        bumps += [e for e in race.update(DT, {"p1": Controls(steer=1.0)}) if e.kind == "bump"]
    assert bumps == [Event("bump", "p1", "p2"), Event("bump", "p2", "p1")]
    assert p2.car.x - p1.car.x > 0.5 * config.CAR_WIDTH  # still kept apart


def test_the_same_seed_and_inputs_give_the_same_race(perfect_race):
    race, events = perfect_race
    again = Race(seed=7, players=1)
    events2 = run(again, perfect)
    assert events2 == events
    assert [(r.car.z, r.car.x, r.car.speed) for r in again.racers] == [
        (r.car.z, r.car.x, r.car.speed) for r in race.racers]
    assert Race(seed=8, players=1).target != race.target


# --- Drifting in the race --------------------------------------------------------------------


def test_drifting_comes_from_the_stick_and_cues_its_charge_and_turbo():
    race = Race(seed=1, players=1, finish_all=True)
    p1 = race.racer("p1")
    for r in race.racers[1:]:
        put(r, -100_000.0 - 1000 * race.racers.index(r), 2.1)
    p1.next_row, p1.next_box = len(race.rows), len(race.box_lines)
    put(p1, race.lap_length * 0.3, 0.0)
    events = []
    for _ in range(round(1.6 / DT)):
        events += of(race.update(DT, {"p1": Controls(steer=-0.5, brake=1.0)}), "p1")
    assert p1.car.drifting
    assert [e for e in events if e.kind == "drift"] == [Event("drift", "p1", 1),
                                                          Event("drift", "p1", 2)]
    events = of(race.update(DT, {"p1": Controls(steer=-0.5)}), "p1")
    assert Event("turbo", "p1", 2) in events and p1.car.boost == pytest.approx(0.40)


def test_a_bump_in_the_race_ends_a_drift_with_no_turbo():
    race = Race(seed=1, players=1, finish_all=True)
    p1, green = race.racer("p1"), race.racer("green")
    for r in race.racers[2:]:
        put(r, -100_000.0 - 1000 * race.racers.index(r), 2.1)
    for r in (p1, green):
        r.next_row, r.next_box = len(race.rows), len(race.box_lines)
    put(p1, race.lap_length * 0.3, 0.0)
    put(green, race.lap_length * 0.3 + 3000.0, 0.6)
    drift = Controls(steer=0.5, brake=1.0)
    for _ in range(round(1.0 / DT)):
        race.update(DT, {"p1": drift})
    assert p1.car.drift_level == 1
    green.car.z, green.car.x = p1.car.z + 100.0, p1.car.x + 0.1
    green.car.speed = p1.car.speed
    events = race.update(DT, {"p1": drift})
    assert [e for e in events if e.kind == "bump"]
    assert not p1.car.drifting
    events = race.update(DT, {"p1": Controls(steer=0.5)})
    assert not [e for e in events if e.kind == "turbo"] and p1.car.boost == 0.0
