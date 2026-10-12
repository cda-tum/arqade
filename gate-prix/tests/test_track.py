import math
import random

import pytest

from gate_prix import circuit, config, track
from gate_prix.track import SEG


@pytest.fixture(scope="module")
def fridge():
    return track.fridge()


# --- The lap ----------------------------------------------------------------------------


def test_a_lap_takes_about_45_seconds_at_top_speed(fridge):
    assert 43.0 <= fridge.lap_length() / config.TOP_SPEED <= 47.0
    assert track.lap_length() == fridge.lap_length()


def test_segments_are_seg_long_and_a_multiple_of_four(fridge):
    # the plate's rings and the rumble alternate every 2 segments: seamless at the lap line
    assert SEG == 200
    assert len(fridge.segments) % 4 == 0
    assert fridge.lap_length() == len(fridge.segments) * SEG
    for i, seg in enumerate(fridge.segments):
        assert seg.index == i and seg.z == i * SEG


def test_the_lap_closes_into_a_drivable_loop(fridge):
    plan = fridge.plan()
    (x0, y0), (x1, y1) = plan[0], plan[-1]
    assert math.hypot(x1 - x0, y1 - y0) < 4 * SEG  # back where it started
    total_turn = sum(seg.curve for seg in fridge.segments) / SEG
    assert total_turn == pytest.approx(2 * math.pi, abs=1e-6)  # one full turn, no seam
    assert sum(seg.hill for seg in fridge.segments) == pytest.approx(0.0, abs=1e-6)


def test_heights_follow_the_hills(fridge):
    segs = fridge.segments
    for a, b in zip(segs, segs[1:]):
        assert b.y == pytest.approx(a.y + a.hill)


def test_it_has_straights_sweepers_an_s_bend_and_two_stage_drops(fridge):
    curves = [seg.curve for seg in fridge.segments]
    assert sum(1 for c in curves if c == 0) > len(curves) // 4  # plenty of straight
    assert max(curves) > config.SHARP_CURVE  # one sharp corner
    assert any(0.5 < c <= config.SHARP_CURVE for c in curves)  # sweepers
    # the S-bend: a left and a right turn within 100 segments of each other
    lefts = [i for i, c in enumerate(curves) if c < -1]
    rights = [i for i, c in enumerate(curves) if c > 1]
    assert any(0 < r - left < 100 for left in lefts for r in rights)
    # two stage drops: steep descents of at least 3000 units
    assert len(fridge.drops) == 2
    for start, end in fridge.drops:
        drop = fridge.segments[start].y - fridge.segments[end].y
        assert drop >= 3000


def test_segment_at_wraps_round_the_lap(fridge):
    lap = fridge.lap_length()
    assert fridge.segment_at(0).index == 0
    assert fridge.segment_at(SEG * 3.5).index == 3
    assert fridge.segment_at(lap + SEG * 5).index == 5
    assert fridge.segment_at(-1).index == len(fridge.segments) - 1
    assert track.segment_at(SEG * 7).index == 7


def test_the_racing_line_stays_on_the_road_and_takes_the_inside(fridge):
    for seg in fridge.segments:
        assert -1.0 <= seg.line <= 1.0
    sharp = [seg for seg in fridge.segments if abs(seg.curve) > 2]
    assert sharp
    for seg in sharp:
        assert seg.line * seg.curve > 0  # right turn: the right side


def test_the_heading_accumulates_the_curve(fridge):
    lap = fridge.lap_length()
    assert fridge.heading_at(0) == 0
    assert fridge.heading_at(lap) == pytest.approx(2 * math.pi)
    assert fridge.heading_at(lap + 1000) == pytest.approx(2 * math.pi + fridge.heading_at(1000))
    assert fridge.heading_at(-1e-12) == pytest.approx(0.0, abs=1e-9)  # just before the line


# --- What stands on it --------------------------------------------------------------------


def test_eight_gate_rows_per_lap_never_on_a_sharp_curve(fridge):
    assert len(fridge.rows) == config.ROWS_PER_LAP
    assert fridge.rows == sorted(fridge.rows)
    for z in fridge.rows:
        i = int(z // SEG)
        near = [fridge.segments[(i + d) % len(fridge.segments)] for d in range(-15, 16)]
        assert all(abs(seg.curve) <= config.SHARP_CURVE for seg in near)
        assert not any(start - 5 <= i <= end + 5 for start, end in fridge.drops)


def test_gate_rows_are_well_over_a_second_apart(fridge):
    lap = fridge.lap_length()
    zs = fridge.rows + [fridge.rows[0] + lap]
    for a, b in zip(zs, zs[1:]):
        assert b - a >= 2 * config.TOP_SPEED


def test_two_item_box_lines_per_lap_clear_of_the_rows(fridge):
    assert len(fridge.boxes) == config.ITEM_BOXES_PER_LAP
    for z, offsets in fridge.boxes:
        assert 0 <= z < fridge.lap_length()
        assert all(abs(x) < 1 for x in offsets)
        assert all(abs(z - row) >= 0.5 * config.TOP_SPEED for row in fridge.rows)


def test_roadside_sprites_stand_off_the_road(fridge):
    kinds = set()
    for seg_sprites in fridge.roadside:
        for offset, kind in seg_sprites:
            assert abs(offset) > config.RUMBLE
            kinds.add(kind)
    assert kinds == {"coax", "attenuator", "standoff"}
    assert len(fridge.roadside) == len(fridge.segments)


# --- Gate rows per race ---------------------------------------------------------------------


def _rows(seed, fridge):
    target = circuit.random_target(random.Random(seed), config.SLOTS)
    return target, track.gate_rows(fridge, target, seed)


def test_a_race_has_one_gate_row_per_slot_at_the_lap_positions(fridge):
    target, rows = _rows(1, fridge)
    assert len(rows) == config.SLOTS
    lap = fridge.lap_length()
    for row in rows:
        lap_no, k = divmod(row.slot, config.ROWS_PER_LAP)
        assert row.z == pytest.approx(lap_no * lap + fridge.rows[k])
    assert [row.slot for row in rows] == list(range(config.SLOTS))


@pytest.mark.parametrize("seed", range(40))
def test_each_row_has_exactly_one_right_arch_and_distinct_decoys(seed, fridge):
    target, rows = _rows(seed, fridge)
    for row in rows:
        assert config.ARCHES_MIN <= len(row.arches) <= config.ARCHES_MAX
        right = [a for a in row.arches if a.right]
        assert len(right) == 1 and right[0].gate == target[row.slot]
        gates = [a.gate for a in row.arches]
        assert len(set(gates)) == len(gates)
        assert set(gates) <= set(circuit.GATES)


@pytest.mark.parametrize("seed", range(40))
def test_arches_fit_the_road_with_a_gap_of_one_arch_width(seed, fridge):
    h = config.ARCH_HALF_WIDTH
    _, rows = _rows(seed, fridge)
    for row in rows:
        offsets = [a.offset for a in row.arches]
        assert offsets == sorted(offsets)
        assert all(abs(x) <= config.ARCH_OFFSET_MAX for x in offsets)
        edges = [-1.0] + [e for x in offsets for e in (x - h, x + h)] + [1.0]
        gaps = [edges[i + 1] - edges[i] for i in range(0, len(edges), 2)]
        assert all(g >= config.ARCH_MIN_GAP - 1e-9 for g in gaps[1:-1])  # no overlaps
        assert max(gaps) >= 2 * h - 1e-9  # room to drive past every arch


def test_rows_use_one_two_and_three_arches(fridge):
    counts = {len(row.arches) for seed in range(10) for row in _rows(seed, fridge)[1]}
    assert counts == {1, 2, 3}


def test_gate_rows_are_deterministic_per_seed(fridge):
    target = circuit.random_target(random.Random(5), config.SLOTS)
    assert track.gate_rows(fridge, target, 7) == track.gate_rows(fridge, target, 7)
    assert track.gate_rows(fridge, target, 7) != track.gate_rows(fridge, target, 8)


def test_rows_and_boxes_become_objects_for_the_renderer(fridge):
    target, rows = _rows(3, fridge)
    objects = track.arch_objects(rows)
    assert len(objects) == sum(len(row.arches) for row in rows)
    lit = [o for o in objects if o[2].endswith(":lit")]
    assert len(lit) == len(rows)
    for z, x, kind in objects:
        assert kind.startswith("arch:")
    boxes = track.box_objects(fridge, laps=3)
    assert len(boxes) == 3 * sum(len(offsets) for _, offsets in fridge.boxes)
    assert all(kind == "box" for _, _, kind in boxes)
