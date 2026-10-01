import pygame

from superconductor.input import (
    DirectionRepeater,
    keyboard_enabled,
    read_keys,
    set_keyboard_enabled,
    should_quit,
    stick_direction,
)


def test_stick_direction_respects_deadzone():
    assert stick_direction(0.0, 0.0, 0.5) is None
    assert stick_direction(0.4, -0.4, 0.5) is None
    assert stick_direction(0.9, 0.0, 0.5) == "right"
    assert stick_direction(-0.9, 0.0, 0.5) == "left"
    assert stick_direction(0.0, -0.9, 0.5) == "up"  # SDL: negative y = up
    assert stick_direction(0.0, 0.9, 0.5) == "down"


def test_stick_diagonal_resolves_to_dominant_axis():
    assert stick_direction(0.9, 0.6, 0.5) == "right"
    assert stick_direction(0.6, -0.9, 0.5) == "up"


def test_repeater_fires_on_push_then_repeats_after_delay():
    r = DirectionRepeater(delay=0.3, interval=0.1)
    assert r.update("up", 0.016) == "up"
    assert r.update("up", 0.2) is None
    assert r.update("up", 0.15) == "up"  # delay passed
    assert r.update("up", 0.04) is None
    assert r.update("up", 0.06) == "up"  # one interval later
    assert r.update(None, 0.016) is None
    assert r.update("left", 0.016) == "left"


def test_should_quit_requires_start_and_select_on_same_pad():
    assert not should_quit(p1_start=True, p1_select=False, p2_start=False, p2_select=True)
    assert should_quit(p1_start=True, p1_select=True, p2_start=False, p2_select=False)
    assert should_quit(p1_start=False, p1_select=False, p2_start=True, p2_select=True)


def test_read_keys_reports_nothing_held_with_keyboard_disabled():
    set_keyboard_enabled(False)
    try:
        keys = read_keys()
        assert not keys[pygame.K_a]
        assert not keyboard_enabled()
    finally:
        set_keyboard_enabled(True)
