import math

import pytest

from qircuit import camera, config
from qircuit.camera import Director


def test_the_leader_sits_near_the_middle_and_what_trails_far_behind_is_off():
    d = Director()
    d.snap(500, 500, 0, 0.0)  # heading east
    x, y, _ = d.project(500, 500)
    assert abs(x) < 0.3 and abs(y) < 0.3
    assert d.on_screen(500 - 100, 500)  # a racer a little behind
    assert not d.on_screen(500 - 900, 500)  # one far behind


def test_it_never_turns_it_only_slides_after_the_leader():
    d = Director()
    d.snap(0, 0, 0, 0.0)
    yaw, view = d.yaw, d.view[:3]
    for _ in range(300):
        d.update(1 / 60, 400, 300, 0, math.pi / 2)  # heading south now
    assert d.yaw == yaw and d.view[:3] == pytest.approx(view)
    assert d.project(400, 300)[0] == pytest.approx(0, abs=0.2)


def test_it_is_isometric_east_and_south_both_lean_across_the_screen():
    d = Director()
    d.snap(0, 0, 0, 0.0)
    ex, ey, _ = d.project(100, 0)  # east: to the right, and up the screen
    sx, sy, _ = d.project(0, 100)  # south: to the right, and down
    ox, oy, _ = d.project(0, 0)
    assert ex > ox and ey > oy and sx > ox and sy < oy


def test_under_the_hud_band_counts_as_off():
    d = Director()
    d.snap(0, 0, 0, 0.0)
    fx, fy, fz = d.focus
    for k in range(1, 400):  # walk up the screen (north-east) until it is off
        if not d.on_screen(fx + k, -fy - k, fz):
            break
    assert d.project(fx + k, -fy - k, fz)[1] < 1.0  # off before the top edge itself


def test_a_model_matrix_points_the_model_along_its_heading():
    m = camera.model_matrix(10, 20, 0, math.pi / 2, 1.0)  # heading south
    nose = camera.apply(m, (5, 0, 0))
    assert nose[:3] == pytest.approx((10, -25, 0))  # gl(): south is -y
    right = camera.apply(m, (0, 5, 0))
    assert right[:3] == pytest.approx((5, -20, 0))  # its right is west when it heads south


def test_pixels_put_the_middle_of_the_screen_in_the_middle():
    d = Director()
    d.snap(0, 0, 0, 0.0)
    fx, fy, fz = d.focus
    px, py = d.to_pixels(fx, -fy, fz)
    assert px == pytest.approx(config.INTERNAL_WIDTH / 2) and py == pytest.approx(config.INTERNAL_HEIGHT / 2)
