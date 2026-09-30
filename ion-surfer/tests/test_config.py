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


SANDBOX_ONLY = ("remove_ion", "add_ion", "cool", "passive_cool")  # reuse the confirm buttons, only active in SANDBOX


def test_each_raw_button_maps_to_one_action():
    for player in ("p1", "p2"):
        raw = [b for act, buttons in INPUT_CONFIG[player]["buttons"].items()
               if act not in SANDBOX_ONLY for b in buttons]
        assert len(raw) == len(set(raw))


def test_sandbox_buttons_sit_on_the_confirm_buttons_not_on_movement():
    # blue adds/removes ions, red cools -- both on L/R, which confirm in menus
    for player, (left, right) in (("p1", ("remove_ion", "add_ion")), ("p2", ("cool", "passive_cool"))):
        buttons = INPUT_CONFIG[player]["buttons"]
        assert set(buttons[left]) | set(buttons[right]) <= set(buttons["a"])
        assert not set(buttons[left]) & set(buttons[right])
