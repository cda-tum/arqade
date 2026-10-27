import numpy as np
import pytest

from qarrera import mesh, tracks, voxels
from qarrera.scenes import scene_for
from qarrera.track import Track


def test_a_lone_voxel_is_a_cube_and_a_buried_one_shows_nothing():
    one = mesh.voxel_mesh({(0, 0, 0): (255, 0, 0)})
    assert one.shape == (36, mesh.STRIDE)
    assert one[:, 2].min() == 0 and one[:, 2].max() == 1  # it stands on z = 0
    solid = {(x, y, z): (255, 255, 255) for x in range(3) for y in range(3) for z in range(3)}
    assert len(mesh.voxel_mesh(solid)) == 6 * 9 * 6  # only the outside


def test_every_racer_and_track_builds_a_sane_mesh():
    for build in voxels.RACERS.values():
        m = mesh.voxel_mesh(build())
        assert len(m) % 6 == 0 and np.isfinite(m).all()
    for d in tracks.ALL:
        t = Track(d)
        m = mesh.track_mesh(t, scene_for(t).palette, -10.0)
        assert len(m) > 1000 and np.isfinite(m).all()
        assert ((0 <= m[:, 6:9]) & (m[:, 6:9] <= 1)).all()


def test_a_placed_mesh_moves_into_the_world():
    m = mesh.voxel_mesh({(0, 0, 0): (255, 0, 0)})
    placed = mesh.place(m, 100, 50, 3, 0.0, 2.0)
    assert placed[:, 0].min() == pytest.approx(99) and placed[:, 1].max() == pytest.approx(-49)
    assert placed[:, 2].min() == pytest.approx(3)
