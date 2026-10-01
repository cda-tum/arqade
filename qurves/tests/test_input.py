import pygame

from qurves import input as qinput
from qurves.input import Input, hat_direction, latest_direction, should_quit, stick_direction


def test_the_stick_reads_its_dominant_axis_past_the_deadzone():
    assert stick_direction(0.1, -0.2, 0.25) is None
    assert stick_direction(0.0, -0.9, 0.25) == (0, -1)  # SDL: negative y is up
    assert stick_direction(0.9, 0.3, 0.25) == (1, 0)
    assert stick_direction(-0.5, 0.6, 0.25) == (0, 1)
    assert stick_direction(-0.8, 0.1, 0.25) == (-1, 0)


def test_the_hat_reads_positive_y_as_up():
    assert hat_direction((0, 1)) == (0, -1)
    assert hat_direction((-1, 0)) == (-1, 0)
    assert hat_direction((0, 0)) is None


def test_holding_two_direction_buttons_steers_by_the_newer_one():
    order, d = latest_direction([], {"up"})
    assert d == (0, -1)
    order, d = latest_direction(order, {"up", "left"})
    assert d == (-1, 0)
    order, d = latest_direction(order, {"up"})  # left let go: back to up
    assert d == (0, -1)
    order, d = latest_direction(order, set())
    assert d is None and order == []


def test_quitting_needs_start_and_select_on_the_same_pad():
    assert should_quit(p1_start=True, p1_select=True, p2_start=False, p2_select=False)
    assert should_quit(p1_start=False, p1_select=False, p2_start=True, p2_select=True)
    assert not should_quit(p1_start=True, p1_select=False, p2_start=False, p2_select=True)


def test_no_keyboard_reads_nothing():
    qinput.set_keyboard_enabled(False)
    try:
        keys = qinput.read_keys()
        assert not keys[pygame.K_w]
        assert not keys[pygame.K_ESCAPE]
    finally:
        qinput.set_keyboard_enabled(True)


def test_with_no_pads_and_no_keys_the_frame_is_idle():
    pygame.init()
    inp = Input()
    inp.update(1 / 60)
    fi = inp.frame_input()
    assert fi.stick == (None, None) and fi.pad == (None, None) and fi.nav is None
    assert not fi.confirm and not fi.back and not fi.activity
