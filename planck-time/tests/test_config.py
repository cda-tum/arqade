import pygame

from planck_time import config


def test_internal_size_scales_onto_1080p_by_a_whole_number():
    assert 1080 % config.INTERNAL_HEIGHT == 0
    assert 1920 // config.INTERNAL_WIDTH == 1080 // config.INTERNAL_HEIGHT == 3


def test_both_gba_screens_fit_side_by_side():
    w, h = config.SCREEN_W, config.SCREEN_H
    (x1, y1), (x2, y2) = config.SCREEN_CENTERS["p1"], config.SCREEN_CENTERS["p2"]
    assert x1 + w // 2 < x2 - w // 2  # room for the bezels between them
    assert x1 - w // 2 >= 0 and x2 + w // 2 <= config.INTERNAL_WIDTH
    assert y1 == y2 and y1 + h // 2 <= config.INTERNAL_HEIGHT


def test_buttons_follow_the_cabinet_convention():
    system = config.INPUT_CONFIG["system"]
    assert (system["a_button"], system["back_button"]) == (1, 2)
    assert (system["start_button"], system["select_button"]) == (9, 8)


def test_the_left_player_is_blue_and_the_right_one_red():
    r, g, b = config.PLAYER_COLORS["p1"]
    assert b > r and b > g
    r, g, b = config.PLAYER_COLORS["p2"]
    assert r > g and r > b


def test_the_play_time_floor_is_reachable():
    assert config.PLAY_TIME * config.PLAY_TIME_FACTOR ** 20 < config.PLAY_TIME_MIN


def test_all_key_names_exist_in_pygame():
    names = [config.INPUT_CONFIG["system"]["keyboard_quit"]]
    for mapping in config.KEYMAP.values():
        for keys in mapping.values():
            names += keys
    for name in names:
        assert hasattr(pygame, name), name
