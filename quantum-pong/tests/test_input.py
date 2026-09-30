from quantum_pong.input import (
    axis_to_direction,
    pressed_edge,
    resolve_paddle_direction,
    should_quit,
)


def test_axis_to_direction_within_deadzone_is_zero():
    assert axis_to_direction(0.1, deadzone=0.25) == 0
    assert axis_to_direction(-0.1, deadzone=0.25) == 0


def test_axis_to_direction_beyond_deadzone_is_signed():
    assert axis_to_direction(0.5, deadzone=0.25) == 1
    assert axis_to_direction(-0.5, deadzone=0.25) == -1


def test_resolve_paddle_direction_prefers_digital_when_held():
    direction = resolve_paddle_direction(
        up_held=True, down_held=False, axis_value=0.9, deadzone=0.25
    )
    assert direction == -1


def test_resolve_paddle_direction_falls_back_to_axis():
    direction = resolve_paddle_direction(
        up_held=False, down_held=False, axis_value=-0.9, deadzone=0.25
    )
    assert direction == -1


def test_resolve_paddle_direction_both_keys_held_cancels_out():
    direction = resolve_paddle_direction(
        up_held=True, down_held=True, axis_value=0.0, deadzone=0.25
    )
    assert direction == 0


def test_pressed_edge_true_only_on_rising_edge():
    assert pressed_edge(previous=False, current=True) is True
    assert pressed_edge(previous=True, current=True) is False
    assert pressed_edge(previous=True, current=False) is False
    assert pressed_edge(previous=False, current=False) is False


def test_should_quit_requires_start_and_select_on_same_pad():
    assert not should_quit(
        p1_start=True, p1_select=False, p2_start=False, p2_select=False, keyboard_quit=False
    )
    assert should_quit(
        p1_start=True, p1_select=True, p2_start=False, p2_select=False, keyboard_quit=False
    )
    assert should_quit(
        p1_start=False, p1_select=False, p2_start=True, p2_select=True, keyboard_quit=False
    )


def test_should_quit_on_keyboard_escape():
    assert should_quit(
        p1_start=False, p1_select=False, p2_start=False, p2_select=False, keyboard_quit=True
    )
