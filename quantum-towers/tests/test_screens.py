import os

import pygame
import pytest
from arqade_common.input import KEYBOARD, PAD

from quantum_towers import config, fonts, screens, tutorial
from quantum_towers.config import ACTION_NAMES, BUTTON_LABELS
from quantum_towers.input import last_device
from quantum_towers.screens import blink_visible, button_grid


def test_button_grid_is_two_rows_of_three():
    grid = button_grid()
    assert len(grid) == 2
    assert all(len(row) == 3 for row in grid)


def test_button_grid_covers_every_action_and_button_label_exactly_once():
    grid = button_grid()
    cells = [cell for row in grid for cell in row]
    labels = [label for label, _ in cells]
    gates = [gate for _, gate in cells if gate is not None]
    assert sorted(labels) == sorted(BUTTON_LABELS)
    assert sorted(gates) == sorted(ACTION_NAMES)


def test_button_grid_has_exactly_one_unmapped_button():
    grid = button_grid()
    cells = [cell for row in grid for cell in row]
    unmapped = [label for label, gate in cells if gate is None]
    assert unmapped == ["Y"]


def test_button_grid_reflects_the_printed_layout_not_raw_hardware_numbers():
    # Regression test for the first real-hardware mapping bug: the legend
    # must show gates by their fixed GATE_AT_POSITION layout, never by
    # inverting INPUT_CONFIG's wiring-specific raw button numbers (which
    # can freely differ from the print/position order on real hardware).
    grid = button_grid()
    assert [cell for row in grid for cell in row] == list(
        zip(config.BUTTON_LABELS, config.GATE_AT_POSITION)
    )


def test_blink_visible_true_at_start_of_period():
    assert blink_visible(0.0, period=1.0) is True


def test_blink_visible_false_at_half_period():
    assert blink_visible(0.5, period=1.0) is False


def test_blink_visible_wraps_around_across_multiple_periods():
    assert blink_visible(2.1, period=1.0) is True
    assert blink_visible(2.6, period=1.0) is False


@pytest.mark.parametrize("on", [(PAD, PAD), (KEYBOARD, KEYBOARD), (KEYBOARD, PAD), (PAD, KEYBOARD)])
def test_the_hint_screens_draw_for_pads_keys_and_both(on, monkeypatch):
    """Keyboard players get keycaps where pads get button names and drawings."""
    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
    pygame.init()
    devices = last_device()
    monkeypatch.setitem(devices._devices, "p1", on[0])
    monkeypatch.setitem(devices._devices, "p2", on[1])
    surface = pygame.Surface((config.INTERNAL_WIDTH, config.INTERNAL_HEIGHT))
    f = fonts.load_font
    for mode in ("1p", "2p"):
        card = tutorial.Card(mode)
        for t in (0.5, 2.0, 3.5, 5.0):
            tutorial.draw_tutorial(surface, card, t, True)
    screens.draw_title_screen(surface, f(22), f(9), f(12), f(8), True, choice_font=f(10))
    screens.draw_pause_menu(surface, f(16), f(10), f(7), ("RESUME", "QUIT TO TITLE"), 0, True)
    screens.draw_initials(surface, f(18), f(32), f(12), screens.NameEntry(), "1:23.45", 0.1)
    screens.draw_times_table(surface, f(18), f(10), f(12), [], None, config.TIMES_TABLE_LOCK)
