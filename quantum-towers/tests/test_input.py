import pygame

from quantum_towers.input import (
    axis_indicates_down,
    axis_indicates_up,
    keyboard_enabled,
    pressed_edge,
    read_keys,
    set_keyboard_enabled,
    should_quit,
)


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


def test_axis_indicates_down_mirrors_up():
    # Only the pause menu reads "down": positive is down in SDL's convention.
    assert axis_indicates_down(0.9, deadzone=0.25) is True
    assert axis_indicates_down(0.1, deadzone=0.25) is False
    assert axis_indicates_down(-0.9, deadzone=0.25) is False


def test_should_quit_requires_start_and_select_on_same_pad():
    assert not should_quit(
        p1_start=True, p1_select=False, p2_start=False, p2_select=False
    )
    assert should_quit(
        p1_start=True, p1_select=True, p2_start=False, p2_select=False
    )
    assert should_quit(
        p1_start=False, p1_select=False, p2_start=True, p2_select=True
    )


def test_nothing_held_does_not_quit():
    assert not should_quit(p1_start=False, p1_select=False, p2_start=False, p2_select=False)

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


def test_the_shared_keyboard_plays_each_gate_from_its_place():
    """P1's 2x3 keys F G H / C V B are the pad's L X R / Y B A: F is gate X,
    G gate Y, H gate Z, V gate H, B RESET (and A); W climbs, Space is Start."""
    import pygame

    from quantum_towers.input import read_player_raw_input

    class Keys:
        def __init__(self, *held):
            self.held = held

        def __getitem__(self, key):
            return key in self.held

    raw = read_player_raw_input("p1", Keys(pygame.K_f, pygame.K_v, pygame.K_w, pygame.K_SPACE))
    assert raw.button_held == {"X": True, "Y": False, "Z": False, "H": True, "RESET": False}
    assert raw.up_held and raw.start_held and raw.back_held and not raw.confirm_held
    assert read_player_raw_input("p2", Keys(pygame.K_l)).button_held["RESET"]
