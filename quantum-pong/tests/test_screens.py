from quantum_pong.screens import blink_visible


def test_blink_visible_true_at_start_of_period():
    assert blink_visible(0.0, period=1.0) is True


def test_blink_visible_false_at_half_period():
    assert blink_visible(0.5, period=1.0) is False


def test_blink_visible_wraps_around_across_multiple_periods():
    assert blink_visible(2.1, period=1.0) is True
    assert blink_visible(2.6, period=1.0) is False
