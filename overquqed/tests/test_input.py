import pygame

from overquqed import input as inp_mod
from overquqed.config import INPUT_CONFIG, REPEAT_DELAY, REPEAT_INTERVAL
from overquqed.input import Repeater, axis_to_direction, joystick_actions, read_keys, should_quit


def test_axis_deadzone():
    assert axis_to_direction(0.3, 0.5) == 0
    assert axis_to_direction(-0.9, 0.5) == -1
    assert axis_to_direction(0.9, 0.5) == 1


def test_quit_needs_start_and_select_on_the_same_pad():
    assert should_quit(p1_start=True, p1_select=True, p2_start=False, p2_select=False)
    assert should_quit(p1_start=False, p1_select=False, p2_start=True, p2_select=True)
    assert not should_quit(p1_start=True, p1_select=False, p2_start=False, p2_select=True)


def test_confirmed_face_buttons_map_to_pick_use_swap():
    # Printed A = raw 1, B = raw 2, Y = raw 3 (confirmed on the cabinet).
    for p in ("p1", "p2"):
        assert joystick_actions(p, {1}, (0.0, 0.0), (0, 0)) == {"pick"}
        assert joystick_actions(p, {2}, (0.0, 0.0), (0, 0)) == {"use"}
        assert joystick_actions(p, {3}, (0.0, 0.0), (0, 0)) == {"swap"}


def test_start_and_select_resolve_from_system_buttons():
    system = INPUT_CONFIG["system"]
    held = joystick_actions("p1", {system["start_button"], system["select_button"]}, (0, 0), (0, 0))
    assert held == {"start", "select"}


def test_stick_is_an_analog_axis_negative_up():
    assert joystick_actions("p1", set(), (0.0, -1.0), (0, 0)) == {"up"}
    assert joystick_actions("p1", set(), (1.0, 1.0), (0, 0)) == {"right", "down"}
    assert joystick_actions("p1", set(), (0.2, -0.2), (0, 0)) == set()


def test_hat_is_a_fallback_and_positive_up():
    assert joystick_actions("p2", set(), (0.0, 0.0), (-1, 1)) == {"left", "up"}


def test_repeater_fires_on_press_then_after_delay_then_interval():
    r = Repeater()
    assert r.update(0.016, True, True)
    assert not r.update(REPEAT_DELAY - 0.05, True, False)
    assert r.update(0.06, True, False)
    assert not r.update(REPEAT_INTERVAL - 0.03, True, False)
    assert r.update(0.04, True, False)
    assert not r.update(0.5, False, False)


def test_no_keyboard_reads_nothing():
    inp_mod.set_keyboard_enabled(False)
    try:
        keys = read_keys()
        assert not keys[pygame.K_a]
        assert not keys[pygame.K_RETURN]
    finally:
        inp_mod.set_keyboard_enabled(True)
