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
        assert not set(INPUT_CONFIG[player]["buttons"]["a"]) & system
