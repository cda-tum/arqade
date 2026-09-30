import pygame

from error_invaders.config import INPUT_CONFIG, KEY_PRESETS, KEYS_BACK, KEYS_CONFIRM


def test_all_key_names_exist_in_pygame():
    names = list(KEYS_CONFIRM) + list(KEYS_BACK)
    for preset in KEY_PRESETS.values():
        for mapping in preset.values():
            for keys in mapping.values():
                names += keys
    for name in names:
        assert hasattr(pygame, name), name


def test_joystick_buttons_do_not_overlap():
    system = {INPUT_CONFIG["system"]["start_button"], INPUT_CONFIG["system"]["select_button"]}
    assert len(system) == 2
    for player in ("p1", "p2"):
        fire = set(INPUT_CONFIG[player]["buttons"]["fire"])
        swap = set(INPUT_CONFIG[player]["buttons"]["swap"])
        assert not fire & swap
        assert not (fire | swap) & system


def test_players_use_different_joysticks():
    assert INPUT_CONFIG["p1"]["joystick_index"] != INPUT_CONFIG["p2"]["joystick_index"]
