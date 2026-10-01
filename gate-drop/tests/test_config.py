import pygame

from gate_drop import config


def test_internal_size_scales_onto_1080p_by_a_whole_number():
    assert 1080 % config.INTERNAL_HEIGHT == 0
    assert 1920 // config.INTERNAL_WIDTH == 1080 // config.INTERNAL_HEIGHT


def test_both_boards_fit_on_screen_without_overlapping():
    w, h = config.COLS * config.CELL, config.ROWS * config.CELL
    (x1, y1), (x2, y2) = config.BOARD_ORIGIN["p1"], config.BOARD_ORIGIN["p2"]
    assert x1 + w < x2 and x2 + w <= config.INTERNAL_WIDTH
    assert y1 + h <= config.INTERNAL_HEIGHT and y2 + h <= config.INTERNAL_HEIGHT


def test_buttons_follow_the_cabinet_convention():
    # AGENTS.md: printed A = raw 1 confirms, B = raw 2 goes back, Start = 9, Select = 8.
    system = config.INPUT_CONFIG["system"]
    assert system["confirm_buttons"] == [1] and system["back_buttons"] == [2]
    assert system["start_button"] == 9 and system["select_button"] == 8
    assert config.INPUT_CONFIG["buttons"] == {"cw": [1], "ccw": [2]}


def test_the_left_player_is_blue_and_the_right_one_red():
    # AGENTS.md "Player colours".
    r, g, b = config.PLAYER_COLORS["p1"]
    assert b > r and b > g
    r, g, b = config.PLAYER_COLORS["p2"]
    assert r > g and r > b


def test_all_key_names_exist_in_pygame():
    names = [config.INPUT_CONFIG["system"]["keyboard_quit"]]
    for mapping in config.KEYMAP.values():
        for keys in mapping.values():
            names += keys
    for name in names:
        assert hasattr(pygame, name), name


def test_the_gate_set():
    assert set(config.PAULIS) < set(config.GATE_KINDS)
    assert set(config.GATE_COLORS) == set(config.GATE_KINDS)
