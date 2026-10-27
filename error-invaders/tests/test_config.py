from error_invaders.input import ACTION_BUTTONS


def test_a_fires_and_b_switches_color():
    # AGENTS.md "Button convention": in play a button may mean anything; here
    # printed A fires and B switches color, and the stick (or d-pad) moves.
    assert ACTION_BUTTONS["fire"] == "a" and ACTION_BUTTONS["swap"] == "b"
    assert all(ACTION_BUTTONS[d] == d for d in ("left", "right", "up", "down"))
