import pygame

from overquqed.config import (
    EVMAPY_P1_KEYS,
    EVMAPY_UNUSED_BUTTONS,
    GRID_H,
    GRID_W,
    INPUT_CONFIG,
    INTERNAL_HEIGHT,
    INTERNAL_WIDTH,
    KEYBOARD_QUIT,
    KEYMAP,
    TILE,
)


def test_all_key_names_exist_in_pygame():
    names = [KEYBOARD_QUIT] + list(EVMAPY_P1_KEYS.values())
    for mapping in KEYMAP.values():
        for keys in mapping.values():
            names += keys
    for name in names:
        assert hasattr(pygame, name), name


def test_resolution_is_4_3_and_tiles_fit_exactly():
    assert INTERNAL_WIDTH * 3 == INTERNAL_HEIGHT * 4
    assert GRID_W * TILE == INTERNAL_WIDTH
    assert GRID_H * TILE == INTERNAL_HEIGHT


def test_start_and_select_are_not_action_buttons():
    system = {INPUT_CONFIG["system"]["start_button"], INPUT_CONFIG["system"]["select_button"]}
    assert len(system) == 2
    for player in ("p1", "p2"):
        for buttons in INPUT_CONFIG[player]["buttons"].values():
            assert not set(buttons) & system


def test_each_raw_button_maps_to_one_action():
    for player in ("p1", "p2"):
        raw = [b for buttons in INPUT_CONFIG[player]["buttons"].values() for b in buttons]
        assert len(raw) == len(set(raw))


def test_players_use_different_joysticks():
    assert INPUT_CONFIG["p1"]["joystick_index"] != INPUT_CONFIG["p2"]["joystick_index"]


def test_p1_dev_keys_only_ever_collide_with_evmapy_for_the_same_action():
    # evmapy turns P1's pad into keystrokes. A P1 dev key that evmapy also
    # emits must come from the very same control, so a double-fire is harmless.
    evmapy_key_to_control = {v: k for k, v in EVMAPY_P1_KEYS.items()}
    control_for_action = {
        "left": {"left", "stick_left"}, "right": {"right", "stick_right"},
        "up": {"up", "stick_up"}, "down": {"down", "stick_down"},
        "pick": {"a"}, "use": {"b"}, "swap": {"y"},
        "start": {"start"}, "select": {"select"},
    }
    for action, keys in KEYMAP["p1"].items():
        for key in keys:
            control = evmapy_key_to_control.get(key)
            if control is not None:
                assert control in control_for_action[action], (action, key)


def test_p2_dev_keys_avoid_everything_evmapy_emits_for_p1():
    used = {v for k, v in EVMAPY_P1_KEYS.items() if k not in EVMAPY_UNUSED_BUTTONS}
    for action, keys in KEYMAP["p2"].items():
        assert not set(keys) & used, action
