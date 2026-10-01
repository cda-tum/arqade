import pygame

from qurves import config


def test_grid_fills_the_screen_below_the_hud():
    assert config.GRID_W * config.CELL == config.INTERNAL_WIDTH
    assert config.HUD_HEIGHT + config.GRID_H * config.CELL == config.INTERNAL_HEIGHT


def test_internal_size_scales_onto_1080p_by_a_whole_number():
    # AGENTS.md: pick an internal height that divides 1080, so SDL's SCALED
    # upscale is an exact integer factor.
    assert 1080 % config.INTERNAL_HEIGHT == 0
    assert 1920 % config.INTERNAL_WIDTH == 0
    assert 1920 // config.INTERNAL_WIDTH == 1080 // config.INTERNAL_HEIGHT


def test_buttons_follow_the_cabinet_convention():
    # AGENTS.md "Button convention": printed A = raw 1, B = raw 2,
    # Select = raw 8, Start = raw 9 (not the other way round).
    for player in ("p1", "p2"):
        buttons = config.INPUT_CONFIG[player]["buttons"]
        assert buttons["split"] == [1]
        assert buttons["back"] == [2]
    assert config.INPUT_CONFIG["system"]["start_button"] == 9
    assert config.INPUT_CONFIG["system"]["select_button"] == 8


def test_stick_axes_are_horizontal_then_vertical():
    for player in ("p1", "p2"):
        assert config.INPUT_CONFIG[player]["axes"] == (0, 1)


def test_all_key_names_exist_in_pygame():
    names = [config.INPUT_CONFIG["system"]["keyboard_quit"]]
    for mapping in config.KEYMAP.values():
        for keys in mapping.values():
            names += keys
    for name in names:
        assert hasattr(pygame, name), name


def test_players_start_inside_the_walls_facing_each_other():
    for player, (x, y) in config.START_CELLS.items():
        assert 0 < x < config.GRID_W - 1 and 0 < y < config.GRID_H - 1
    assert config.START_HEADINGS["p1"] == (1, 0)
    assert config.START_HEADINGS["p2"] == (-1, 0)


def test_one_pickup_is_exactly_the_split_threshold():
    assert config.METER_PER_PICKUP == config.SPLIT_MIN_METER
    assert config.METER_MAX == 2 * config.METER_PER_PICKUP
    assert config.METER_PER_PICKUP / config.METER_DRAIN_PER_S == 3.0
