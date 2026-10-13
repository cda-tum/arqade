"""The items: item boxes, SPLIT and QEC, the pace multiplier, and racing to the end."""

from collections import Counter

import pytest

from gate_prix import config
from gate_prix.car import Controls
from gate_prix.race import Event, Race

DT = 1 / 60
TOP = config.TOP_SPEED
USE = Controls(item=True)


def through_box(race, racer, k=0, j=0, lap=0, x=None):
    """Put a car just before box line k of `lap` at box j's offset (or x), step a frame."""
    z, offsets = race.track.boxes[k]
    racer.car.z = lap * race.lap_length + z - 50.0
    racer.car.x = offsets[j] if x is None else x
    racer.car.speed = TOP
    racer.next_box = race.box_index(racer.car.z)
    return [e for e in race.update(DT, {}) if e.car == racer.car.id]


def before_row(race, racer, x):
    """Put a car just before its next row at x, at top speed (no frame stepped)."""
    row = race.rows[racer.next_row]
    racer.car.z = row.z - 50.0
    racer.car.x = x
    racer.car.speed = TOP
    return row


def cross(race, racer, x, controls=None):
    before_row(race, racer, x)
    return [e for e in race.update(DT, controls or {}) if e.car == racer.car.id]


def arch(row, right):
    return next(a for a in row.arches if a.right == right)


def find_row(race, want):
    """The index of the first row that `want(row)` accepts."""
    return next(i for i, row in enumerate(race.rows) if want(row))


def skip_to(race, racer, index):
    """Fill the slots before row `index` as misses, so that it is the car's next row."""
    while racer.next_row < index:
        cross(race, racer, 1.9)


def clear_of(row, x):
    return all(abs(x - a.offset) > config.ARCH_HALF_WIDTH for a in row.arches)


# --- Boxes ---------------------------------------------------------------------------------


def test_the_item_table_is_one_row_per_place_over_the_five_items():
    assert config.ITEMS == ("SPLIT", "QEC", "MEASURE", "TUNNEL", "DECOHERENCE")
    assert config.GATE_ITEMS == ("SPLIT", "QEC")
    assert len(config.ITEM_ODDS) == config.CARS
    for odds in config.ITEM_ODDS:
        assert len(odds) == len(config.ITEMS) and all(w >= 0 for w in odds)
        # never empty, on any lap: something is left once SPLIT and QEC are out
        assert sum(w for item, w in zip(config.ITEMS, odds) if item not in config.GATE_ITEMS) > 0
    share = [dict(zip(config.ITEMS, (w / sum(odds) for w in odds))) for odds in config.ITEM_ODDS]
    for front, back in zip(share, share[1:]):
        for item in ("MEASURE", "TUNNEL", "SPLIT"):  # the back gets more of these
            assert back[item] >= front[item], item
        for item in ("DECOHERENCE", "QEC"):  # the front more of these
            assert back[item] <= front[item], item
    assert share[-1]["MEASURE"] > share[0]["MEASURE"]
    assert share[0]["DECOHERENCE"] > share[-1]["DECOHERENCE"]


def test_driving_through_a_box_gives_an_item_and_cues_it():
    race = Race(seed=1, players=1)
    p1 = race.racer("p1")
    events = through_box(race, p1)
    boxes = [e for e in events if e.kind == "box"]
    assert len(boxes) == 1 and boxes[0].value == p1.item
    assert p1.item in config.ITEMS + (None,)


def test_a_box_gives_nothing_new_while_an_item_is_held_but_still_breaks():
    race = Race(seed=1, players=1)
    p1 = race.racer("p1")
    p1.item = "QEC"
    events = through_box(race, p1)
    assert not [e for e in events if e.kind == "box"]
    assert p1.item == "QEC"
    assert not race.box_present(0, 0)
    # it is still cued, for the sound and the HUD: the box broke, the item is still held
    assert [e for e in events if e.kind == "box_full"] == [Event("box_full", "p1", "QEC")]


def test_missing_every_box_gives_nothing():
    race = Race(seed=1, players=1)
    p1 = race.racer("p1")
    offsets = race.track.boxes[0][1]
    gap = (offsets[0] + offsets[1]) / 2
    assert abs(gap - offsets[0]) > config.BOX_REACH
    assert not [e for e in through_box(race, p1, x=gap) if e.kind == "box"]
    assert not [e for e in through_box(race, p1, k=1, x=1.9) if e.kind == "box"]
    assert p1.item is None
    assert all(race.box_present(k, j) for k in range(2) for j in range(3))


def test_a_box_reaches_box_reach_either_side():
    race = Race(seed=1, players=1)
    p1 = race.racer("p1")
    x = race.track.boxes[0][1][2]
    # 0.02 is more than the curve pushes the car in the frame
    assert [e for e in through_box(race, p1, x=x - config.BOX_REACH + 0.02) if e.kind == "box"]
    p1.item = None
    assert not [e for e in through_box(race, p1, k=1, j=2, x=x - config.BOX_REACH - 0.02)
                if e.kind == "box"]


def test_a_taken_box_is_gone_until_it_respawns_after_3_s():
    race = Race(seed=1, players=1)
    p1, green = race.racer("p1"), race.racer("green")
    through_box(race, p1)
    assert not race.box_present(0, 0)
    assert len([o for o in race.box_objects() if o[2] == "box"]) == (
        config.LAPS * sum(len(off) for _, off in race.track.boxes) - config.LAPS)
    # the same box is the same object on every lap: gone for green on lap 2 as well
    assert not [e for e in through_box(race, green, lap=1) if e.kind == "box"]
    assert green.item is None
    taken = DT  # the first frame's time
    while race.time + DT < taken + config.BOX_RESPAWN - DT / 2:
        race.update(DT, {})
        assert not race.box_present(0, 0)
    race.update(DT, {})
    race.update(DT, {})
    assert race.box_present(0, 0)
    assert [e for e in through_box(race, green, lap=1) if e.kind == "box"]


def test_every_box_line_is_crossed_once_in_order():
    race = Race(seed=1, players=1)
    p1 = race.racer("p1")
    through_box(race, p1)
    p1.item = None
    race.update(DT, {})  # still past the line: no second box from it
    assert p1.item is None


def test_box_odds_by_place_statistically_over_seeds():
    counts = {1: Counter(), config.CARS: Counter()}
    for seed in range(40):
        race = Race(seed=seed, players=1)
        for place in counts:
            for _ in range(100):
                counts[place][race.roll_item(place)] += 1
    for place, got in counts.items():
        odds = config.ITEM_ODDS[place - 1]
        total = sum(got.values())
        assert got[None] == 0  # a box is never empty
        for item, w in zip(config.ITEMS, odds):
            assert got[item] / total == pytest.approx(w / sum(odds), abs=0.03)
    assert counts[config.CARS]["MEASURE"] > counts[1]["MEASURE"]
    assert counts[1]["DECOHERENCE"] > counts[config.CARS]["DECOHERENCE"]


def test_every_box_gives_an_item():
    for seed in range(20):
        for k in range(len(Race(seed=seed, players=1).track.boxes)):
            for lap in range(config.LAPS):
                race = Race(seed=seed, players=1)
                p1 = race.racer("p1")
                events = [e for e in through_box(race, p1, k=k, j=seed % 3, lap=lap)
                          if e.kind == "box"]
                assert len(events) == 1 and events[0].value in config.ITEMS


def test_with_no_gate_left_a_box_never_gives_split_or_qec():
    """SPLIT takes a second gate and QEC fixes one for the check; on the gate-free final
    lap neither has anything to do, so the other three share the odds."""
    got = Counter()
    for seed in range(30):
        race = Race(seed=seed, players=1)
        p1 = race.racer("p1")
        p1.next_row = len(race.rows)  # past its last row
        for k in range(len(race.track.boxes)):
            p1.item = None
            events = through_box(race, p1, k=k, lap=config.LAPS - 1)
            got.update(e.value for e in events if e.kind == "box")
    assert got["SPLIT"] == got["QEC"] == 0 and sum(got.values()) == 60
    race = Race(seed=1, players=1)
    rolls = Counter(race.roll_item(3, gates_left=False) for _ in range(3000))
    assert set(rolls) == {"MEASURE", "TUNNEL", "DECOHERENCE"}
    odds = dict(zip(config.ITEMS, config.ITEM_ODDS[2]))
    rest = sum(odds[i] for i in rolls)
    for item, n in rolls.items():  # renormalised over what is left
        assert n / 3000 == pytest.approx(odds[item] / rest, abs=0.03)
    assert "SPLIT" in {race.roll_item(config.CARS) for _ in range(200)}


def test_a_box_rolls_with_the_drivers_place(monkeypatch):
    race = Race(seed=2, players=1)
    seen = []
    monkeypatch.setattr(race, "roll_item", lambda place, **kw: seen.append(place) or "QEC")
    green, p1 = race.racer("green"), race.racer("p1")
    through_box(race, green, lap=1)  # far ahead of everyone
    p1.car.z = green.car.z - 30_000  # still behind the others
    through_box(race, race.racer("black"), k=1, j=2)
    assert seen[0] == 1 and seen[1] == race.racer("black").place


# --- Using items ---------------------------------------------------------------------------


def test_using_nothing_does_nothing():
    race = Race(seed=1, players=1)
    assert not [e for e in race.update(DT, {"p1": USE}) if e.kind == "item"]


def test_qec_repairs_the_most_recent_mistake_but_not_the_streak():
    race = Race(seed=3, players=1)
    p1 = race.racer("p1")
    row = race.rows[0]
    cross(race, p1, arch(row, True).offset)
    cross(race, p1, 1.9)  # a miss: slot 1 empty
    assert p1.circuit.results[:2] == [True, False]
    p1.item = "QEC"
    events = race.update(DT, {"p1": USE})
    assert Event("item", "p1", "QEC") in events
    assert p1.item is None
    assert p1.circuit.results[:2] == [True, True]
    assert p1.circuit.slots[1] == race.target[1]
    assert p1.circuit.streak == 0


def test_qec_without_a_mistake_is_still_used_up():
    race = Race(seed=3, players=1)
    p1 = race.racer("p1")
    cross(race, p1, arch(race.rows[0], True).offset)
    p1.item = "QEC"
    events = race.update(DT, {"p1": USE})
    assert Event("item", "p1", "QEC") in events
    assert p1.item is None
    assert p1.circuit.results[0] is True and p1.circuit.streak == 1


def test_split_makes_a_clone_mirrored_across_the_centre_line():
    race = Race(seed=3, players=1)
    p1 = race.racer("p1")
    p1.item = "SPLIT"
    assert not p1.split and p1.clone_x is None and race.clone_objects() == []
    events = race.update(DT, {"p1": USE})
    assert Event("item", "p1", "SPLIT") in events
    assert p1.item is None
    assert p1.split and p1.split_rows == config.SPLIT_ROWS == 2
    assert p1.clone_x == -p1.car.x
    assert race.clone_objects() == [(p1.car.z, -p1.car.x, "clone")]


def split_case(car_x_of, clone_x_of, want):
    """Find a row where the car at car_x_of(row) and its clone at -x give the case, cross it
    with SPLIT running, and return (row, events)."""
    for seed in range(200):
        race = Race(seed=seed, players=1)
        p1 = race.racer("p1")
        for i, row in enumerate(race.rows[:8]):
            x = car_x_of(row)
            if x is not None and clone_x_of(row, x) and want(row, x):
                skip_to(race, p1, i)
                p1.item = "SPLIT"
                race.update(DT, {"p1": USE})
                before_row(race, p1, x)
                events = [e for e in race.update(DT, {}) if e.car == "p1"]
                return race, p1, row, events
    raise AssertionError("no such row in 200 seeds")


def test_split_the_clone_alone_takes_the_right_arch():
    # the car misses every arch; the clone, at -x, is in the right one
    race, p1, row, events = split_case(
        lambda row: -arch(row, True).offset,
        lambda row, x: clear_of(row, x),
        lambda row, x: True)
    assert [e.kind for e in events if e.kind in ("right", "wrong", "miss")] == ["right"]
    assert p1.circuit.slots[row.slot] == race.target[row.slot]


def test_split_the_car_right_and_the_clone_wrong_is_right():
    def clone_wrong(row, x):
        return any(not a.right and abs(-x - a.offset) <= config.ARCH_HALF_WIDTH
                   for a in row.arches)
    race, p1, row, events = split_case(lambda row: arch(row, True).offset, clone_wrong,
                                       lambda row, x: True)
    assert "right" in [e.kind for e in events]


def test_split_the_clone_wrong_and_the_car_missing_is_wrong_with_the_clones_gate():
    def wrong_x(row):
        decoys = [a for a in row.arches if not a.right]
        return -decoys[0].offset if decoys else None
    race, p1, row, events = split_case(wrong_x, lambda row, x: clear_of(row, x),
                                       lambda row, x: True)
    decoy = next(a for a in row.arches if not a.right and a.offset == -wrong_x(row))
    assert Event("wrong", "p1", row.slot) in events
    assert p1.circuit.slots[row.slot] == decoy.gate


def test_split_both_missing_leaves_the_slot_empty():
    race, p1, row, events = split_case(
        lambda row: 1.9, lambda row, x: clear_of(row, -x), lambda row, x: True)
    assert Event("miss", "p1", row.slot) in events


def test_split_lasts_two_rows_then_cues_its_end():
    race = Race(seed=3, players=1)
    p1 = race.racer("p1")
    p1.item = "SPLIT"
    race.update(DT, {"p1": USE})
    first = cross(race, p1, 1.9)
    assert p1.split and p1.split_rows == 1
    assert not [e for e in first if e.kind == "split_end"]
    second = cross(race, p1, 1.9)
    assert Event("split_end", "p1") in second
    assert not p1.split and p1.clone_x is None and race.clone_objects() == []
    # the third row is the car's alone: its clone's spot no longer counts
    row = race.rows[p1.next_row]
    x = -arch(row, True).offset
    if clear_of(row, x):
        assert "miss" in [e.kind for e in cross(race, p1, x)]


def test_a_new_split_while_one_runs_starts_again_from_two_rows():
    race = Race(seed=3, players=1)
    p1 = race.racer("p1")
    p1.item = "SPLIT"
    race.update(DT, {"p1": USE})
    cross(race, p1, 1.9)
    p1.item = "SPLIT"
    race.update(DT, {"p1": USE})
    assert p1.split_rows == 2


def test_the_split_is_over_with_the_last_gate_row():
    """No gate is left after row 16: a clone still out goes, and a SPLIT still held is
    dropped, so the HUD never offers one for the gate-free final lap."""
    race = Race(seed=3, players=1)
    p1 = race.racer("p1")
    skip_to(race, p1, len(race.rows) - 1)
    p1.item = "SPLIT"
    race.update(DT, {"p1": USE})
    assert p1.split_rows == 2
    p1.item = "SPLIT"  # and another one held
    events = cross(race, p1, 1.9)
    assert p1.next_row == len(race.rows)
    assert Event("split_end", "p1") in events
    assert not p1.split and p1.item is None
    p2 = Race(seed=3, players=1)
    q = p2.racer("p1")
    skip_to(p2, q, len(p2.rows) - 1)
    q.item = "SPLIT"  # a SPLIT held, never used: it runs out of rows too, and says so
    events = cross(p2, q, 1.9)
    assert q.item is None and events.count(Event("split_end", "p1")) == 1
    p2 = Race(seed=3, players=1)
    q = p2.racer("p1")
    skip_to(p2, q, len(p2.rows) - 1)
    q.item = "QEC"
    cross(p2, q, 1.9)
    assert q.item == "QEC"  # a QEC still fixes a gate on the final lap


def test_the_clone_ends_at_the_finish():
    race = Race(seed=3, players=1)
    p1 = race.racer("p1")
    p1.item = "SPLIT"
    race.update(DT, {"p1": USE})
    p1.next_row = len(race.rows)
    p1.laps = config.LAPS - 1
    p1.car.z = config.LAPS * race.lap_length - 10.0
    p1.car.speed = TOP
    events = race.update(DT, {})
    assert Event("split_end", "p1") in events and not p1.split


def finish(race, racer):
    """Put a car just short of the line on its last lap and step a frame."""
    racer.next_row = len(race.rows)
    racer.next_box = len(race.box_lines)
    racer.laps = config.LAPS - 1
    racer.car.z = config.LAPS * race.lap_length - 10.0
    racer.car.speed = TOP
    return race.update(DT, {})


def test_a_finished_car_cannot_use_an_item():
    race = Race(seed=3, players=1, finish_all=True)
    p1 = race.racer("p1")
    finish(race, p1)
    assert p1.finished
    for item in config.ITEMS:
        p1.item = item
        p1.circuit.results[0] = False  # something for a QEC to repair
        events = race.update(DT, {"p1": USE})
        assert not [e for e in events if e.kind == "item"]
        assert not p1.split and p1.circuit.results[0] is False
        assert not p1.car.tunnelling and race.shots == [] and race.clouds == []


def test_an_item_held_at_the_finish_is_dropped():
    race = Race(seed=3, players=1, finish_all=True)
    p1 = race.racer("p1")
    p1.item = "QEC"
    finish(race, p1)
    assert p1.finished and p1.item is None


# --- MEASURE --------------------------------------------------------------------------------


def lineup(race, gaps, x=0.0):
    """Put p1 on a straight at top speed and the cars in `gaps` (id: dz from p1) around it,
    everyone else far behind; no rows or boxes near."""
    p1 = race.racer("p1")
    z = race.lap_length * 0.3
    for i, r in enumerate(race.racers):
        r.next_row, r.next_box = len(race.rows), len(race.box_lines)
        r.car.speed, r.car.x = TOP, x
        r.car.z = z + gaps.get(r.car.id, -200_000.0 - 1000.0 * i)
    p1.car.z = z
    return p1


def fly(race, seconds, controls=None):
    events = []
    for _ in range(round(seconds / DT)):
        events += race.update(DT, controls or {})
    return events


def test_the_item_constants():
    assert config.MEASURE_RANGE == 30_000.0
    assert config.TUNNEL_TIME == 3.0
    assert config.DECO_TIME == 10.0
    assert config.BLIND_TIME == 1.5
    assert 0.2 <= config.MEASURE_FLIGHT <= 0.6  # a short flight you can see


def test_measure_flies_to_the_nearest_car_ahead_and_collapses_it():
    race = Race(seed=1, players=1, finish_all=True)
    p1 = lineup(race, {"green": 20_000.0, "white": 8_000.0, "lime": -3_000.0}, x=-0.5)
    white = race.racer("white")
    white.car.x = 0.5
    white.circuit.streak = 4
    white.car.give_boost(0.5, 3.0)
    p1.item = "MEASURE"
    events = race.update(DT, {"p1": USE})
    assert Event("item", "p1", "MEASURE") in events
    assert len(race.shots) == 1
    shot = race.shots[0]
    assert (shot.owner, shot.target) == ("p1", "white")
    # in flight it is between the two cars, seen by the renderer
    fly(race, config.MEASURE_FLIGHT / 2)
    (z, x, kind), = race.shot_objects()
    assert kind == "shot" and p1.car.z < z < white.car.z and -0.5 < x < 0.5
    assert 0.3 < shot.progress < 0.7
    assert not white.car.spinning
    events = fly(race, config.MEASURE_FLIGHT / 2 + DT)
    assert Event("collapse", "white", "p1") in events
    assert race.shots == [] and race.shot_objects() == []
    assert white.car.spinning and white.circuit.streak == 0 and white.car.boost == 0.0
    assert white.car.speed < 0.5 * TOP
    assert not race.racer("green").car.spinning


def test_measure_with_no_car_ahead_in_range_fizzles():
    race = Race(seed=1, players=1, finish_all=True)
    p1 = lineup(race, {"green": config.MEASURE_RANGE + 2_000.0, "white": -2_000.0})
    p1.item = "MEASURE"
    events = race.update(DT, {"p1": USE})
    assert Event("item", "p1", "MEASURE") in events and Event("fizzle", "p1") in events
    assert race.shots == [] and p1.item is None
    assert race.measure_target("p1") is None
    race.racer("green").car.z -= 4_000.0
    assert race.measure_target("p1").car.id == "green"


def test_a_tunnelling_car_is_immune_to_measure():
    race = Race(seed=1, players=1, finish_all=True)
    p1 = lineup(race, {"green": 5_000.0})
    green = race.racer("green")
    p1.item = "MEASURE"
    race.update(DT, {"p1": USE})
    green.car.tunnel(config.TUNNEL_TIME)
    events = fly(race, config.MEASURE_FLIGHT + 2 * DT)
    assert Event("immune", "green", "shot") in events
    assert not green.car.spinning and race.shots == []


# --- TUNNEL ---------------------------------------------------------------------------------


def test_tunnel_passes_through_cars_for_3_s():
    race = Race(seed=1, players=1, finish_all=True)
    p1 = lineup(race, {"green": 100.0})
    green = race.racer("green")
    green.car.x = 0.05
    p1.item = "TUNNEL"
    events = race.update(DT, {"p1": USE})
    assert Event("item", "p1", "TUNNEL") in events and p1.car.tunnelling
    assert p1.effects["tunnel"] == pytest.approx(config.TUNNEL_TIME - DT, abs=DT)
    events += fly(race, config.TUNNEL_TIME)
    end = events.index(Event("tunnel_end", "p1"))
    assert not p1.car.tunnelling
    assert not [e for e in events[:end] if e.kind == "bump"]
    assert [e for e in events[end:] if e.kind == "bump"]  # solid again, still side by side


def test_tunnel_drives_off_road_at_full_speed():
    race = Race(seed=1, players=1, finish_all=True)
    p1 = lineup(race, {}, x=1.6)
    p1.item = "TUNNEL"
    race.update(DT, {"p1": USE})
    fly(race, 1.5)
    assert p1.car.offroad and p1.car.speed == pytest.approx(TOP)


# --- DECOHERENCE ----------------------------------------------------------------------------


def drop_cloud(race, p1):
    p1.item = "DECOHERENCE"
    events = race.update(DT, {"p1": USE})
    assert Event("item", "p1", "DECOHERENCE") in events
    return race.clouds[-1]


def test_decoherence_drops_a_cloud_just_behind_that_any_car_can_hit():
    race = Race(seed=1, players=1, finish_all=True)
    p1 = lineup(race, {"green": -3_000.0}, x=0.2)
    green = race.racer("green")
    cloud = drop_cloud(race, p1)
    assert cloud.owner == "p1" and cloud.x == pytest.approx(0.2)
    assert p1.car.z - 1000.0 < cloud.z < p1.car.z - config.CAR_LENGTH
    assert (cloud.z, cloud.x, "deco") in race.deco_objects()
    green.car.give_boost(0.6, 4.0)
    events = fly(race, 0.5)
    assert Event("decohered", "green", "p1") in events
    assert green.car.boost == 0.0
    assert green.blind and green.effects["blind"] <= config.BLIND_TIME
    assert race.clouds == []  # used up
    fly(race, config.BLIND_TIME)
    assert not green.blind and "blind" not in green.effects


def test_a_cloud_on_the_final_lap_slows_instead_of_blinding():
    race = Race(seed=1, players=1, finish_all=True)
    p1 = lineup(race, {"green": -3_000.0})
    green = race.racer("green")
    for r in (p1, green):
        r.laps = config.LAPS - 1
        r.car.z += (config.LAPS - 1) * race.lap_length
    drop_cloud(race, p1)
    events = fly(race, 0.5)
    assert Event("decohered", "green", "p1") in events
    assert not green.blind
    assert green.car.slow_time > 0 and green.car.speed <= config.CLOUD_CAP * TOP + 1e-6


def test_a_cloud_lasts_10_s_and_a_car_beside_it_or_tunnelling_is_untouched():
    race = Race(seed=1, players=1, finish_all=True)
    p1 = lineup(race, {"green": -3_000.0, "white": -3_000.0})
    green, white = race.racer("green"), race.racer("white")
    green.car.x, white.car.x = -0.9, 0.0
    white.car.tunnel(config.TUNNEL_TIME)
    drop_cloud(race, p1)
    events = fly(race, 1.0, {"green": Controls(steer=-0.0)})
    assert not [e for e in events if e.kind == "decohered"]
    assert Event("immune", "white", "deco") in events
    assert len(race.clouds) == 1
    fly(race, config.DECO_TIME - 1.0 + 2 * DT)
    assert race.clouds == [] and race.deco_objects() == []


def test_the_effects_and_blindness_show_what_is_running():
    race = Race(seed=1, players=1)
    p1 = race.racer("p1")
    assert p1.effects == {} and not p1.blind
    p1.car.spin()
    p1.car.tunnel(1.0)
    assert set(p1.effects) == {"spin", "tunnel"}


# --- Pace and racing to the end ------------------------------------------------------------


def test_pace_scales_the_top_speed_within_its_limits():
    race = Race(seed=1, players=2)
    p1, p2 = race.racer("p1"), race.racer("p2")
    for _ in range(240):
        race.update(DT, {"p1": Controls(pace=0.95), "p2": Controls(pace=5.0)})
    assert p1.car.speed == pytest.approx(0.95 * TOP)
    assert p2.car.speed == pytest.approx(config.PACE_LIMITS[1] * TOP)


def test_a_race_to_the_end_waits_for_every_car():
    race = Race(seed=1, players=1, finish_all=True)
    p1 = race.racer("p1")
    p1.laps = config.LAPS - 1
    p1.car.z = config.LAPS * race.lap_length - 10.0
    p1.car.speed = TOP
    race.update(DT, {})
    assert p1.finished and not race.over
    for r in race.racers[1:]:
        r.laps = config.LAPS
    race.update(DT, {})
    assert race.over
