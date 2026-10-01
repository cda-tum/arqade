import pygame

from qurves import config


def test_grid_fills_the_screen_below_the_hud():
    assert config.GRID_W * config.CELL == config.INTERNAL_WIDTH
    assert config.HUD_HEIGHT + config.GRID_H * config.CELL == config.INTERNAL_HEIGHT


def test_internal_size_scales_onto_1080p_by_a_whole_number():
    # AGENTS.md: pick an internal height that divides 1080, so SDL's SCALED
    # upscale is an exact integer factor.
    assert 1080 % config.INTERNAL_HEIGHT == 0
    assert 1920 // config.INTERNAL_WIDTH == 1080 // config.INTERNAL_HEIGHT


def test_menu_buttons_follow_the_cabinet_convention():
    # AGENTS.md "Button convention": printed A = raw 1 confirms, B = raw 2
    # goes back; Start = raw 9 and Select = raw 8 (not the other way round).
    system = config.INPUT_CONFIG["system"]
    assert system["confirm_buttons"] == [1] and system["back_buttons"] == [2]
    assert system["start_button"] == 9 and system["select_button"] == 8


def test_the_face_buttons_steer_like_wasd():
    # Printed L X R / Y B A = raw 4 0 5 / 3 2 1: X is up, Y B A are left, down, right.
    for pad in config.INPUT_CONFIG["pads"]:
        assert pad["buttons"] == {"up": [0], "left": [3], "down": [2], "right": [1]}
        assert pad["axes"] == (0, 1)


def test_all_key_names_exist_in_pygame():
    names = [config.INPUT_CONFIG["system"]["keyboard_quit"], *config.KEYS_CONFIRM, *config.KEYS_BACK]
    for mapping in config.KEYMAP.values():
        for keys in mapping.values():
            names += keys
    for name in names:
        assert hasattr(pygame, name), name


def test_every_mode_has_starts_controls_and_colours_for_each_player():
    for mode in config.MODES:
        players = config.PLAYERS_BY_MODE[mode]
        assert len(players) == mode
        assert set(config.START[mode]) == set(players)
        assert set(config.CONTROLS[mode]) == set(players)
        for (x, y), _heading in config.START[mode].values():
            assert 0 < x < config.GRID_W - 1 and 0 < y < config.GRID_H - 1
        assert all(p in config.PLAYER_COLORS for p in players)


def test_four_players_each_get_one_input_and_none_is_shared():
    used = [src for sources in config.CONTROLS[4].values() for src in sources]
    assert len(used) == len(set(used)) == 4


def test_gate_kinds_all_have_a_weight_and_a_colour():
    assert set(config.GATE_WEIGHTS) == set(config.GATE_COLORS) == {"H", "X", "Z"}


def test_the_left_player_is_blue_and_the_right_one_red():
    # AGENTS.md "Player colours": the cabinet's left side is blue, its right side red.
    r, g, b = config.PLAYER_COLORS["p1"]
    assert b > r and b > g
    r, g, b = config.PLAYER_COLORS["p2"]
    assert r > g and r > b
