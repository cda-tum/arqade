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
