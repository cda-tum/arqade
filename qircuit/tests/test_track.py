import math

import pytest

from qircuit import config, tracks
from qircuit.track import Gate, Track, TrackDef, in_range, piece_starts

TRACKS = [Track(d) for d in tracks.ALL]


def oval() -> Track:
    return Track(TrackDef("OVAL", (120.0, 80.0), 0.0,
                          (("S", 400.0), ("A", 100.0, 180), ("S", 400.0), ("A", 100.0, 180)), 0.0))


@pytest.mark.parametrize("track", TRACKS, ids=lambda t: t.name)
def test_every_track_closes_on_itself(track):
    assert track.closure_error < 0.5
    assert track.heading_error < 1e-3


@pytest.mark.parametrize("track", TRACKS, ids=lambda t: t.name)
def test_no_part_of_a_track_runs_into_another_except_over_a_bridge(track):
    """Two stretches of track that come close (closer than their width) must
    be at different heights: the figure 8's bridge."""
    width = config.LANES * config.LANE_W + 8
    step = 12
    ks = range(0, track.n, step)
    for a in ks:
        for b in ks:
            apart = min(abs(a - b), track.n - abs(a - b)) * track.ds
            if apart < 4 * width:
                continue
            if math.hypot(track.cx[a] - track.cx[b], track.cy[a] - track.cy[b]) < width:
                assert abs(track.elev[a] - track.elev[b]) > 20, (a * track.ds, b * track.ds)


@pytest.mark.parametrize("track", TRACKS, ids=lambda t: t.name)
def test_gates_sit_on_real_wires(track):
    for g in track.gates:
        assert all(0 <= lane < config.LANES for lane in g.lanes)
        if g.kind in ("CNOT", "SWAP"):
            assert len(g.lanes) == 2 and abs(g.lanes[0] - g.lanes[1]) == 1
        else:
            assert len(g.lanes) == 1


def test_lane_three_is_on_the_cars_right():
    t = oval()
    x, y, h = t.pose(1.5, 100.0)  # heading right along the top straight
    assert h == pytest.approx(0.0, abs=1e-6)
    assert t.pose(3, 100.0)[1] > y > t.pose(0, 100.0)[1]  # right of a car heading right is down


def test_inner_wires_are_shorter_and_tighter_in_a_corner():
    t = oval()
    s = 400.0 + 0.5 * math.pi * 100  # middle of the first (right-hand) turn
    assert t.factor(3, s) < t.factor(0, s)
    assert t.curvature(3, s) > t.curvature(0, s) > 0
    assert t.curvature(3, s) == pytest.approx(1 / (100 - 1.5 * config.LANE_W), rel=0.02)
    assert t.factor(0, 100.0) == pytest.approx(1.0)


def test_the_figure_eight_is_fair_every_wire_is_as_long():
    fig8 = TRACKS[0]  # (its bridge adds a little height, the same to every wire)
    lengths = [sum(fig8.lf[i]) * fig8.ds for i in range(config.LANES)]
    assert max(lengths) - min(lengths) < 1.0


def test_wires_one_and_two_cannot_be_changed_between_where_the_track_splits():
    split = next(t for t in TRACKS if t.d.split)
    a, b = split.d.split
    mid = (a + b) / 2
    assert split.split_at(mid) == pytest.approx(1.0)
    assert not split.can_switch(mid, 1, 2) and not split.can_switch(mid, 2, 1)
    assert split.can_switch(mid, 0, 1) and split.can_switch(mid, 2, 3)
    assert split.can_switch(a - 10, 1, 2)
    assert split.lf[0][split._index(mid)[0]] == pytest.approx(1.0)  # parted, but parallel again


def test_no_switching_off_the_edge_or_by_two():
    t = oval()
    assert not t.can_switch(10, 0, -1) and not t.can_switch(10, 3, 4)
    assert not t.can_switch(10, 0, 2)
    assert t.can_switch(10, 0, 1)


def test_ranges_can_wrap_past_the_start():
    assert in_range(5, (-10, 10), 100) and in_range(95, (-10, 10), 100)
    assert not in_range(50, (-10, 10), 100)
    assert in_range(50, (40, 60), 100)


def test_piece_starts_add_up():
    pieces = (("S", 10), ("A", 10, 90))
    assert piece_starts(pieces) == pytest.approx([0, 10, 10 + math.pi * 5])


def test_a_gate_is_frozen_data():
    g = Gate("H", 10.0, (1,))
    with pytest.raises(Exception):
        g.s = 3


def test_humps_and_kickers_give_the_track_its_height():
    from qircuit.track import TrackDef as TD
    t = Track(TD("H", (120.0, 80.0), 0.0, (("S", 400.0), ("A", 100.0, 180), ("S", 400.0), ("A", 100.0, 180)), 0.0,
                 humps=((100.0, 400.0, 12.0),), kickers=(600.0,)))
    assert t.height(50) == 0 and t.height(250) == pytest.approx(12.0)
    assert 0 < t.height(130) < 12
    assert t.height(600 - 1) == pytest.approx(config.KICKER_HEIGHT, rel=0.1)
    assert t.height(600 + 2) == 0


@pytest.mark.parametrize("track", TRACKS, ids=lambda t: t.name)
def test_every_track_has_a_scene_and_its_pads_sit_on_real_wires(track):
    from qircuit import scenes
    assert track.d.env in scenes.PAINTERS and scenes.scene_for(track).key == track.d.env
    for s, lanes in track.d.boosts:
        assert all(0 <= lane < config.LANES for lane in lanes) and 0 <= s < track.length
