import pytest

from superconductor.lattice import Lattice, edge


def test_square_lattice_couples_every_grid_neighbour():
    lat = Lattice("square", 5, 5)
    assert len(lat.edges) == 2 * 5 * 4
    assert lat.neighbor((2, 2), "up") == (1, 2)
    assert lat.neighbor((2, 2), "right") == (2, 3)
    assert lat.neighbor((0, 0), "up") is None
    assert lat.neighbor((0, 0), "left") is None


def test_brick_lattice_has_hex_connectivity():
    lat = Lattice("brick", 5, 5)
    # all horizontals, but only every other vertical, staggered per row
    assert all(lat.has_edge((r, c), (r, c + 1)) for r in range(5) for c in range(4))
    assert lat.has_edge((0, 0), (1, 0))
    assert not lat.has_edge((0, 1), (1, 1))
    assert lat.has_edge((1, 1), (2, 1))
    assert max(len(lat.neighbors(n)) for n in lat.nodes) == 3


def test_brick_lattice_is_connected():
    lat = Lattice("brick", 5, 5)
    assert all(lat.distance((0, 0), n) >= 0 for n in lat.nodes)


def test_distance_follows_couplers():
    square = Lattice("square", 5, 5)
    brick = Lattice("brick", 5, 5)
    assert square.distance((0, 1), (1, 1)) == 1
    # no vertical coupler at (0,1): go round via column 0 or 2
    assert brick.distance((0, 1), (1, 1)) == 3


def test_edge_is_unordered():
    assert edge((0, 0), (0, 1)) == edge((0, 1), (0, 0))


def test_unknown_kind_rejected():
    with pytest.raises(ValueError):
        Lattice("triangle", 3, 3)


def test_bottleneck_joins_its_halves_only_through_the_middle_columns():
    lat = Lattice("bottleneck")
    assert (lat.rows, lat.cols) == (6, 4)
    crossing = [e for e in lat.edges if len({n[0] // 3 for n in e}) == 2]
    assert sorted(min(e) for e in crossing) == [(2, 1), (2, 2)]
    assert set(crossing) == lat.bridges
    assert lat.distance((2, 0), (3, 0)) == 3  # round via column 1


def test_distributed_has_four_modules_with_single_links():
    lat = Lattice("distributed")
    assert len(lat.nodes) == 36
    assert len(lat.bridges) == 4
    between = [e for e in lat.edges if len({(n[0] // 3, n[1] // 3) for n in e}) == 2]
    assert set(between) == lat.bridges
    # each link joins the middle qubits of the two facing sides
    assert edge((1, 2), (1, 3)) in lat.bridges and edge((2, 4), (3, 4)) in lat.bridges
    assert lat.distance((0, 0), (5, 5)) == 10


def test_every_layout_is_connected_and_grid_local():
    from superconductor.lattice import LAYOUTS
    for kind in LAYOUTS:
        lat = Lattice(kind)
        assert all(lat.distance(lat.nodes[0], n) >= 0 for n in lat.nodes)
        for e in lat.edges:
            (r0, c0), (r1, c1) = tuple(e)
            assert abs(r0 - r1) + abs(c0 - c1) == 1  # so the stick can reach it


def test_module_gaps_only_move_the_drawing():
    lat = Lattice("distributed")
    assert lat.positions[(0, 0)] == (0.0, 0.0)
    assert lat.positions[(3, 3)][0] > 3 and lat.positions[(3, 3)][1] > 3
