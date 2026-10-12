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


def test_the_item_table_is_one_row_per_place_and_the_back_does_better():
    assert config.ITEMS == ("SPLIT", "QEC")
    assert len(config.ITEM_ODDS) == config.CARS
    for odds in config.ITEM_ODDS:
        assert len(odds) == len(config.ITEMS) + 1 and all(w >= 0 for w in odds)
    share = [[w / sum(odds) for w in odds] for odds in config.ITEM_ODDS]
    for front, back in zip(share, share[1:]):
        assert back[0] >= front[0] and back[1] >= front[1]  # more SPLIT and more QEC
        assert back[2] <= front[2]  # fewer empty boxes
    assert share[-1][2] == 0  # last place always gets something


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
        for item, w in zip(config.ITEMS + (None,), odds):
            assert got[item] / total == pytest.approx(w / sum(odds), abs=0.03)
    assert counts[config.CARS]["SPLIT"] > counts[1]["SPLIT"]
    assert counts[config.CARS]["QEC"] > counts[1]["QEC"]


def test_a_box_rolls_with_the_drivers_place(monkeypatch):
    race = Race(seed=2, players=1)
    seen = []
    monkeypatch.setattr(race, "roll_item", lambda place: seen.append(place) or "QEC")
    green, p1 = race.racer("green"), race.racer("p1")
    through_box(race, green, lap=1)  # far ahead of everyone
    p1.car.z = green.car.z - 30_000  # still behind the others
    through_box(race, race.racer("graphite"), k=1, j=2)
    assert seen[0] == 1 and seen[1] == race.racer("graphite").place


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


def test_an_item_held_at_the_finish_is_dropped():
    race = Race(seed=3, players=1, finish_all=True)
    p1 = race.racer("p1")
    p1.item = "QEC"
    finish(race, p1)
    assert p1.finished and p1.item is None


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
