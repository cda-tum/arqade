"""The noise storm: each racer's own decoherence hazards on the final lap."""

import random

import pytest

from gate_prix import config, storm
from gate_prix.car import Controls
from gate_prix.race import Event, Race

DT = 1 / 60
TOP = config.TOP_SPEED


def to_the_check(race, racer, slots_right=16):
    """Fill a car's circuit (the first `slots_right` right, the rest missed) and put it just
    short of the line into the final lap, at top speed."""
    c = racer.circuit
    for slot in range(config.SLOTS):
        c.take(slot, c.target[slot] if slot < slots_right else None)
    racer.next_row = len(race.rows)
    racer.laps = config.LAPS - 2
    racer.next_box = len(race.box_lines)  # no boxes in the way
    racer.car.z = (config.LAPS - 1) * race.lap_length - 20.0
    racer.car.x, racer.car.speed = 0.0, TOP


def into_the_storm(seed=3, slots_right=12, players=1, car_id="p1"):
    race = Race(seed=seed, players=players)
    racer = race.racer(car_id)
    to_the_check(race, racer, slots_right)
    race.update(DT, {})
    return race, racer


# --- How many, and where ---------------------------------------------------------------------


@pytest.mark.parametrize("right, n", [(16, 4), (15, 6), (12, 12), (8, 20), (6, 24), (0, 24)])
def test_the_count_is_4_plus_2_per_wrong_gate_capped_at_24(right, n):
    assert storm.count(right) == n


def test_the_constants():
    assert (config.STORM_BASE, config.STORM_PER_WRONG, config.STORM_MAX) == (4, 2, 24)
    assert config.STORM_END == 1.0
    assert config.STORM_GAP >= config.CAR_WIDTH  # the clear line is at least a car wide
    assert (config.CLOUD_CAP, config.CLOUD_TIME) == (0.7, 1.0)
    assert (config.SPIN_SPEED, config.SPIN_TIME) == (0.4, 0.8)
    assert config.HAZARD_SIZE["cloud"] > config.HAZARD_SIZE["mine"]  # wide and soft, small


def test_each_racer_gets_its_hazards_as_it_starts_the_final_lap_from_its_own_check():
    race = Race(seed=3, players=2)
    p1, p2 = race.racer("p1"), race.racer("p2")
    assert race.hazards_for("p1") == [] and race.hazards_for("p2") == []
    to_the_check(race, p1, slots_right=12)
    race.update(DT, {})
    assert len(race.hazards_for("p1")) == 12
    assert race.hazards_for("p2") == []  # not on its final lap yet
    to_the_check(race, p2, slots_right=16)
    p2.car.x = 0.8  # beside p1, which has just crossed
    race.update(DT, {})
    assert len(race.hazards_for("p2")) == 4
    assert len(race.hazards_for("p1")) == 12
    assert race.hazards_for("p1") != race.hazards_for("p2")


def test_the_cpus_get_their_storms_too():
    race, green = into_the_storm(car_id="green", slots_right=10)
    assert len(race.hazards_for("green")) == 16


def test_hazards_are_the_renderers_z_x_kind_alive():
    race, p1 = into_the_storm()
    hazards = race.hazards_for("p1")
    for z, x, kind, alive in hazards:
        assert kind in ("cloud", "mine") and alive is True
    assert [h[0] for h in hazards] == sorted(h[0] for h in hazards)


def test_a_storm_is_the_same_for_the_same_seed_and_car():
    a, _ = into_the_storm(seed=5)
    b, _ = into_the_storm(seed=5)
    c, _ = into_the_storm(seed=6)
    assert a.hazards_for("p1") == b.hazards_for("p1") != c.hazards_for("p1")


def test_hazards_are_spread_over_the_lap_on_the_road_and_clear_of_the_line():
    race = Race(seed=1, players=1)
    lap = race.lap_length
    start, finish = (config.LAPS - 1) * lap, config.LAPS * lap
    kinds = set()
    for seed in range(40):
        for right in (16, 12, 8, 0):
            rng = random.Random(seed)
            hazards = storm.storm(rng, right, start, finish, race.track)
            assert len(hazards) == storm.count(right)
            zs = [h.z for h in hazards]
            assert zs == sorted(zs)
            assert zs[0] >= start + config.STORM_START * TOP  # after the freeze, and a beat
            assert zs[-1] <= finish - config.STORM_END * TOP  # never within 1 s of the line
            # spread out: no half of the storm's stretch holds more than 3/4 of it
            mid = (zs[0] + zs[-1]) / 2
            assert sum(z < mid for z in zs) <= 0.75 * len(zs) + 1
            for h in hazards:
                assert abs(h.x) + h.size <= 1.0  # on the road
                kinds.add(h.kind)
    assert kinds == {"cloud", "mine"}


def _free(intervals, lo, hi):
    """The parts of [lo, hi] outside every interval, as (a, b) pairs."""
    free, x = [], lo
    for a, b in sorted(intervals):
        if a > x:
            free.append((x, min(a, hi)))
        x = max(x, b)
        if x >= hi:
            break
    if x < hi:
        free.append((x, hi))
    return [(a, b) for a, b in free if b > a]


def _groups(hazards):
    """Hazards near enough in z to be passed at once (within a car's length)."""
    groups = []
    for h in hazards:
        if groups and h.z - groups[-1][0].z < config.CAR_LENGTH:
            groups[-1].append(h)
        else:
            groups.append([h])
    return groups


def test_a_storm_always_leaves_a_clear_line_one_car_wide_that_half_stick_can_follow():
    """Over many seeds and every count: at every hazard there is a gap on the road at least a
    car wide between the hazards' edges, and the gaps join into one line a car can drive
    with half stick (ignoring the curves, which a car can always cancel)."""
    race = Race(seed=1, players=1)
    lap = race.lap_length
    start, finish = (config.LAPS - 1) * lap, config.LAPS * lap
    half = config.CAR_WIDTH / 2
    for seed in range(300):
        right = seed % 17
        hazards = storm.storm(random.Random(seed), right, start, finish, race.track)
        reach, z_prev = None, None
        for group in _groups(hazards):
            edges = [(h.x - h.size, h.x + h.size) for h in group]
            gaps = _free(edges, -1.0, 1.0)
            assert max(b - a for a, b in gaps) >= config.CAR_WIDTH, (seed, group)
            # where the car's centre can be without touching any of them
            centres = _free([(h.x - h.reach, h.x + h.reach) for h in group], -1 + half, 1 - half)
            assert centres, (seed, group)
            z = group[0].z
            if reach is None:
                reach = centres
            else:
                move = 0.5 * config.STEER_RATE * (z - z_prev) / TOP
                grown = [(a - move, b + move) for a, b in reach]
                reach = [(max(a, c), min(b, d)) for a, b in grown for c, d in centres
                         if max(a, c) < min(b, d)]
                assert reach, f"seed {seed}: no line through the hazards at z={z:.0f}"
            z_prev = group[-1].z


def test_bigger_storms_come_partly_in_pairs():
    race = Race(seed=1, players=1)
    lap = race.lap_length
    pairs = 0
    for seed in range(20):
        hazards = storm.storm(random.Random(seed), 4, 2 * lap, 3 * lap, race.track)
        pairs += sum(len(g) == 2 for g in _groups(hazards))
    assert pairs > 0


# --- Hitting them ----------------------------------------------------------------------------


def hazard_ahead(race, racer, kind):
    """Its first hazard of this kind, with the car put just before it at its x."""
    h = next(h for h in race.racer(racer.car.id).hazards if h.kind == kind)
    racer.car.z = h.z - 50.0
    racer.car.x = h.x
    racer.car.speed = TOP
    racer.next_hazard = racer.hazards.index(h)
    return h


def step(race, racer, controls=None):
    return [e for e in race.update(DT, controls or {}) if e.car == racer.car.id]


def test_a_static_cloud_takes_the_boosts_and_caps_the_speed_at_70_percent_for_1_s():
    race, p1 = into_the_storm(slots_right=4)
    p1.car.give_boost(0.8, 5.0)
    h = hazard_ahead(race, p1, "cloud")
    events = step(race, p1)
    assert Event("hazard", "p1", "cloud") in events
    assert not h.alive
    assert p1.car.boost == 0.0
    assert p1.car.speed == pytest.approx(config.CLOUD_CAP * TOP)
    for _ in range(round(0.9 / DT)):
        race.update(DT, {})
    assert p1.car.speed == pytest.approx(config.CLOUD_CAP * TOP)
    for _ in range(round(1.0 / DT)):
        race.update(DT, {})
    assert p1.car.speed > config.CLOUD_CAP * TOP


def test_a_bit_flip_mine_spins_the_car_out():
    race, p1 = into_the_storm(slots_right=4)
    p1.circuit.streak = 5
    h = hazard_ahead(race, p1, "mine")
    events = step(race, p1, {"p1": Controls(steer=1.0)})
    assert Event("hazard", "p1", "mine") in events and not h.alive
    assert p1.car.spinning and p1.car.speed == pytest.approx(config.SPIN_SPEED * TOP, rel=0.02)
    assert p1.circuit.streak == 0
    x = p1.car.x
    race.update(DT, {"p1": Controls(steer=1.0)})
    assert p1.car.x == pytest.approx(x, abs=0.01)  # no steering (only the curve's push)


def test_a_hazard_is_missed_by_driving_clear_of_it():
    race, p1 = into_the_storm(slots_right=4)
    h = hazard_ahead(race, p1, "cloud")
    p1.car.x = h.x + h.reach + 0.05 if h.x < 0 else h.x - h.reach - 0.05
    assert not [e for e in step(race, p1) if e.kind == "hazard"]
    assert h.alive and p1.car.speed == pytest.approx(TOP)


def test_a_hazard_is_only_that_racers():
    race = Race(seed=3, players=2)
    p1, p2 = race.racer("p1"), race.racer("p2")
    to_the_check(race, p1, slots_right=4)
    to_the_check(race, p2, slots_right=16)
    p2.car.x = 1.9  # out of the way on the grid line
    race.update(DT, {})
    h = hazard_ahead(race, p1, "mine")
    p1.car.x = 1.9
    p2.car.z, p2.car.x, p2.car.speed = h.z - 50.0, h.x, TOP  # p2 drives through p1's mine
    p2.next_hazard = next(i for i, g in enumerate(p2.hazards) if g.z > h.z) if any(
        g.z > h.z for g in p2.hazards) else len(p2.hazards)
    events = race.update(DT, {})
    assert not [e for e in events if e.kind == "hazard"]
    assert h.alive and not p2.car.spinning


def test_tunnelling_is_immune_to_the_storm():
    race, p1 = into_the_storm(slots_right=4)
    for kind in ("cloud", "mine"):
        p1.car.tunnel(config.TUNNEL_TIME)
        p1.car.give_boost(0.5, 3.0)
        h = hazard_ahead(race, p1, kind)
        events = step(race, p1)
        assert not [e for e in events if e.kind == "hazard"]
        assert Event("immune", "p1", kind) in events
        assert h.alive and p1.car.boost == 0.5 and not p1.car.spinning


def test_the_warp_still_comes_on_top_of_the_storm():
    race, p1 = into_the_storm(slots_right=12)
    events = []
    for _ in range(round(1.2 / DT)):
        events += step(race, p1)
    assert [e for e in events if e.kind == "warp"]


def test_a_hit_in_a_drift_ends_it_with_no_turbo():
    race, p1 = into_the_storm(slots_right=4)
    hazard_ahead(race, p1, "cloud")
    p1.car.drifting, p1.car.drift_dir, p1.car.drift_time = True, 1, 1.0
    step(race, p1, {"p1": Controls(steer=0.6, brake=1.0)})  # still holding the drift
    assert not p1.car.drifting and p1.car.boost == 0.0
