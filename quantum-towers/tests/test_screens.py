from quantum_towers.config import ACTION_NAMES, BUTTON_LABELS
from quantum_towers.screens import blink_visible, button_grid


def test_button_grid_is_two_rows_of_three():
    grid = button_grid("p1")
    assert len(grid) == 2
    assert all(len(row) == 3 for row in grid)


def test_button_grid_covers_every_action_and_button_label_exactly_once():
    grid = button_grid("p1")
    cells = [cell for row in grid for cell in row]
    labels = [label for label, _ in cells]
    gates = [gate for _, gate in cells if gate is not None]
    assert sorted(labels) == sorted(BUTTON_LABELS)
    assert sorted(gates) == sorted(ACTION_NAMES)


def test_button_grid_has_exactly_one_unmapped_button():
    grid = button_grid("p1")
    cells = [cell for row in grid for cell in row]
    unmapped = [label for label, gate in cells if gate is None]
    assert unmapped == ["Y"]


def test_blink_visible_true_at_start_of_period():
    assert blink_visible(0.0, period=1.0) is True


def test_blink_visible_false_at_half_period():
    assert blink_visible(0.5, period=1.0) is False


def test_blink_visible_wraps_around_across_multiple_periods():
    assert blink_visible(2.1, period=1.0) is True
    assert blink_visible(2.6, period=1.0) is False
