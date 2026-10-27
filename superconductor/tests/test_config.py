from superconductor.input import ACTION_BUTTONS


def test_each_pad_button_does_one_thing():
    used = [b for buttons in ACTION_BUTTONS.values() for b in buttons]
    assert len(used) == len(set(used))
    assert ACTION_BUTTONS["next"] == ("a", "r") and ACTION_BUTTONS["other"] == ("b",)
