from quantum_towers.input import axis_indicates_up, pressed_edge, should_quit


def test_pressed_edge_true_only_on_rising_edge():
    assert pressed_edge(previous=False, current=True) is True
    assert pressed_edge(previous=True, current=True) is False
    assert pressed_edge(previous=True, current=False) is False
    assert pressed_edge(previous=False, current=False) is False


def test_axis_indicates_up_true_past_the_negative_deadzone():
    # SDL convention: negative vertical axis means the stick is pushed up.
    assert axis_indicates_up(-0.9, deadzone=0.25) is True


def test_axis_indicates_up_false_within_the_deadzone():
    assert axis_indicates_up(-0.1, deadzone=0.25) is False
    assert axis_indicates_up(0.0, deadzone=0.25) is False


def test_axis_indicates_up_false_when_pushed_down():
    assert axis_indicates_up(0.9, deadzone=0.25) is False


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
