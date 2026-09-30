import pygame

from error_invaders.input import (
    axis_to_direction,
    keyboard_enabled,
    pressed_edge,
    read_keys,
    set_keyboard_enabled,
    should_quit,
)


def test_axis_to_direction_respects_deadzone():
    assert axis_to_direction(0.0, 0.5) == 0
    assert axis_to_direction(0.4, 0.5) == 0
    assert axis_to_direction(-0.4, 0.5) == 0
    assert axis_to_direction(0.9, 0.5) == 1
    assert axis_to_direction(-0.9, 0.5) == -1


def test_pressed_edge_true_only_on_rising_edge():
    assert pressed_edge(previous=False, current=True) is True
    assert pressed_edge(previous=True, current=True) is False
    assert pressed_edge(previous=True, current=False) is False
    assert pressed_edge(previous=False, current=False) is False


def test_should_quit_requires_start_and_select_on_same_pad():
    assert not should_quit(p1_start=True, p1_select=False, p2_start=False, p2_select=False)
    assert not should_quit(p1_start=True, p1_select=False, p2_start=False, p2_select=True)
    assert should_quit(p1_start=True, p1_select=True, p2_start=False, p2_select=False)
    assert should_quit(p1_start=False, p1_select=False, p2_start=True, p2_select=True)

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
