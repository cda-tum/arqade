import pygame

from ion_surfer.config import INPUT_CONFIG, KEYMAP, PAUSE_KEYS


def test_all_key_names_exist_in_pygame():
    names = list(PAUSE_KEYS) + [INPUT_CONFIG["system"]["keyboard_quit"]]
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


SANDBOX_ONLY = ("remove_ion", "add_ion", "cool", "passive_cool")  # L/R, only active in SANDBOX
MOVEMENT = ("left", "right", "up", "down")


def test_each_raw_button_drives_one_movement_action():
    for player in ("p1", "p2"):
        raw = [b for act in MOVEMENT for b in INPUT_CONFIG[player]["buttons"][act]]
        assert len(raw) == len(set(raw))


def test_confirm_and_back_are_the_printed_A_and_B():
    # Cabinet convention (see "Button convention" in ../AGENTS.md): A confirms,
    # B goes back, in every game. Printed A is raw 1 and printed B is raw 2.
    for player in ("p1", "p2"):
        buttons = INPUT_CONFIG[player]["buttons"]
        assert buttons["confirm"] == [1]
        assert buttons["back"] == [2]


def test_menu_buttons_deliberately_share_the_movement_buttons():
    # A is also "right" and B also "down" in-game. That overlap is intended:
    # the menu code tests confirm/back first and returns, so a single press
    # never both scrolls and confirms. If this ever stops holding, the menus
    # need re-checking, not this test relaxing.
    for player in ("p1", "p2"):
        buttons = INPUT_CONFIG[player]["buttons"]
        assert set(buttons["confirm"]) <= set(buttons["right"])
        assert set(buttons["back"]) <= set(buttons["down"])


def test_sandbox_buttons_sit_on_L_and_R_clear_of_everything_else():
    # L/R no longer confirm, so the sandbox owns them outright.
    for player, (left, right) in (("p1", ("remove_ion", "add_ion")), ("p2", ("cool", "passive_cool"))):
        buttons = INPUT_CONFIG[player]["buttons"]
        assert buttons[left] == [4] and buttons[right] == [5]
        movement = {b for act in MOVEMENT for b in buttons[act]}
        assert not (set(buttons[left]) | set(buttons[right])) & movement
