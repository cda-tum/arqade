import pygame

from gate_drop import config


def test_internal_size_scales_onto_1080p_by_a_whole_number():
    assert 1080 % config.INTERNAL_HEIGHT == 0
    assert 1920 // config.INTERNAL_WIDTH == 1080 // config.INTERNAL_HEIGHT


def test_both_boards_fit_on_screen_without_overlapping():
    w, h = config.COLS * config.CELL, config.ROWS * config.CELL
    (x1, y1), (x2, y2) = config.BOARD_ORIGIN["p1"], config.BOARD_ORIGIN["p2"]
    assert x1 + w < x2 and x2 + w <= config.INTERNAL_WIDTH
    # each well, its 8 px frame, and the |q_n> label plate under it fit on screen
    for _x, y in (*config.BOARD_ORIGIN.values(), config.SOLO_ORIGIN):
        assert y + h + config.LABEL_PLATE + 8 <= config.INTERNAL_HEIGHT


def test_the_left_player_is_blue_and_the_right_one_red():
    # AGENTS.md "Player colours".
    r, g, b = config.PLAYER_COLORS["p1"]
    assert b > r and b > g
    r, g, b = config.PLAYER_COLORS["p2"]
    assert r > g and r > b


def test_the_gate_set():
    assert set(config.PAULIS) < set(config.GATE_KINDS)
    assert set(config.GATE_COLORS) == set(config.GATE_KINDS)
