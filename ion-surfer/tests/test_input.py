import pygame

from ion_surfer.input import (
    Pad,
    axis_to_direction,
    keyboard_enabled,
    read_keys,
    set_keyboard_enabled,
    should_quit,
)


def test_axis_to_direction_respects_deadzone():
    assert axis_to_direction(0.4, 0.5) == 0
    assert axis_to_direction(0.9, 0.5) == 1
    assert axis_to_direction(-0.9, 0.5) == -1


def test_should_quit_requires_start_and_select_on_same_pad():
    assert not should_quit(p1_start=True, p1_select=False, p2_start=False, p2_select=True)
    assert should_quit(p1_start=True, p1_select=True, p2_start=False, p2_select=False)
    assert should_quit(p1_start=False, p1_select=False, p2_start=True, p2_select=True)


def test_pad_action_stays_held_until_every_source_releases():
    pad = Pad()
    pad.set("a", "key", True)
    pad.set("a", "button", True)
    pad.set("a", "key", False)
    assert pad.held("a")
    pad.set("a", "button", False)
    assert not pad.held("a")


def test_pad_registers_press_once_then_auto_repeats_directions():
    pad = Pad()
    pad.set("up", "hat", True)
    assert "up" in pad.pressed
    pad.pressed.clear()
    pad.update(0.2)  # still inside the initial repeat delay
    assert "up" not in pad.pressed
    pad.update(0.1)  # past it
    assert "up" in pad.pressed

def test_read_keys_reports_nothing_held_with_keyboard_disabled():
    set_keyboard_enabled(False)
    try:
        keys = read_keys()
        assert not keys[pygame.K_a]
        assert not keys[pygame.K_UP]
        assert not keyboard_enabled()
    finally:
        set_keyboard_enabled(True)
    assert keyboard_enabled()
