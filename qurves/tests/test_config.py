from qurves import config


def test_grid_fills_the_screen_below_the_hud():
    assert config.GRID_W * config.CELL == config.INTERNAL_WIDTH
    assert config.HUD_HEIGHT + config.GRID_H * config.CELL == config.INTERNAL_HEIGHT


def test_internal_size_scales_onto_1080p_by_a_whole_number():
    # AGENTS.md: pick an internal height that divides 1080, so SDL's SCALED
    # upscale is an exact integer factor.
    assert 1080 % config.INTERNAL_HEIGHT == 0
    assert 1920 // config.INTERNAL_WIDTH == 1080 // config.INTERNAL_HEIGHT


def test_the_face_buttons_steer_like_wasd():
    # Printed L X R / Y B A: X is up, Y B A are left, down, right.
    from qurves.input import FACE_DIRECTIONS

    assert FACE_DIRECTIONS == {"x": "up", "y": "left", "b": "down", "a": "right"}


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
