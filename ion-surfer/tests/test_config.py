import pygame

from ion_surfer.config import INPUT_CONFIG, KEYMAP, SELECT_KEYS


def test_all_key_names_exist_in_pygame():
    names = list(SELECT_KEYS) + [INPUT_CONFIG["system"]["keyboard_quit"]]
    for mapping in KEYMAP.values():
        for keys in mapping.values():
            names += keys
    for name in names:
        assert hasattr(pygame, name), name


def test_start_and_select_are_not_action_buttons():
    system = {INPUT_CONFIG["system"]["start_button"], INPUT_CONFIG["system"]["select_button"]}
    assert len(system) == 2
    for player in ("p1", "p2"):
        for buttons in INPUT_CONFIG[player]["buttons"].values():
            assert not set(buttons) & system


SANDBOX_ONLY = ("remove_ion", "add_ion")  # reuse the confirm buttons, only active in SANDBOX


def test_each_raw_button_maps_to_one_action():
    for player in ("p1", "p2"):
        raw = [b for act, buttons in INPUT_CONFIG[player]["buttons"].items()
               if act not in SANDBOX_ONLY for b in buttons]
        assert len(raw) == len(set(raw))


def test_sandbox_ion_buttons_sit_on_the_confirm_buttons_not_on_movement():
    for player in ("p1", "p2"):
        buttons = INPUT_CONFIG[player]["buttons"]
        ion_buttons = set(buttons["remove_ion"]) | set(buttons["add_ion"])
        assert ion_buttons <= set(buttons["a"])
        assert not set(buttons["remove_ion"]) & set(buttons["add_ion"])
