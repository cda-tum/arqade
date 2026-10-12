import pytest

from gate_prix import config


def test_race_shape():
    assert config.CARS == 6
    assert config.LAPS == 3
    assert config.ROWS_PER_LAP == 8
    assert config.SLOTS == 24
    assert config.CHECK_SLOTS == 16
    assert (config.ARCHES_MIN, config.ARCHES_MAX) == (1, 3)
    assert config.CPU_CARS_2P == 4 and config.CPU_CARS_1P == 5
    assert config.ITEM_BOXES_PER_LAP == 2


def test_resolution_divides_the_panel_exactly():
    assert (config.INTERNAL_WIDTH, config.INTERNAL_HEIGHT) == (960, 540)
    assert 1920 % config.INTERNAL_WIDTH == 0 and 1080 % config.INTERNAL_HEIGHT == 0
    assert config.VIEW_2P == (960, 270)


@pytest.mark.parametrize(
    "streak, strength, seconds",
    [(1, 0.20, 1.0), (2, 0.28, 1.2), (3, 0.36, 1.4), (4, 0.44, 1.6), (5, 0.52, 1.8), (6, 0.60, 2.0)],
)
def test_streak_boost_table(streak, strength, seconds):
    got_strength, got_seconds = config.streak_boost(streak)
    assert got_strength == pytest.approx(strength)
    assert got_seconds == pytest.approx(seconds)


@pytest.mark.parametrize("streak", [7, 12, 24])
def test_streak_boost_is_capped(streak):
    strength, seconds = config.streak_boost(streak)
    assert strength == pytest.approx(0.60)
    assert seconds == pytest.approx(2.0)


def test_streak_boost_of_zero_is_nothing():
    assert config.streak_boost(0) == (0.0, 0.0)


@pytest.mark.parametrize(
    "distance, strength, seconds",
    [(0, 0.80, 5.0), (16, 0.0, 1.0), (3, 13 / 16 * 0.80, 1.0 + 13 * 0.25), (8, 0.40, 3.0)],
)
def test_circuit_check_boost(distance, strength, seconds):
    got_strength, got_seconds = config.check_boost(distance)
    assert got_strength == pytest.approx(strength)
    assert got_seconds == pytest.approx(seconds)


def test_off_road_top_speed_is_60_percent():
    assert config.OFFROAD_SPEED_FACTOR == 0.6


def test_gate_colours_are_shared_with_the_other_games():
    assert config.GATE_COLORS == {
        "H": (248, 192, 40), "X": (232, 64, 72), "Z": (56, 120, 232), "Y": (168, 80, 216),
    }


def test_input_config_follows_the_cabinet():
    ic = config.INPUT_CONFIG
    assert ic["p1"]["joystick_index"] == 0 and ic["p2"]["joystick_index"] == 1
    assert ic["p1"]["axes"] == (0, 1) and ic["p2"]["axes"] == (0, 1)
    assert ic["axis_deadzone"] == 0.25
    system = ic["system"]
    assert (system["a_button"], system["back_button"]) == (1, 2)
    assert (system["start_button"], system["select_button"]) == (9, 8)


def test_p1_dev_keys_avoid_the_pads_own_letters():
    forbidden = {"K_l", "K_x", "K_r", "K_b", "K_y", "K_a"}
    for key_list in config.KEYMAP["p1"].values():
        assert not forbidden & set(key_list)


def test_player_colours_left_blue_right_red():
    r1, g1, b1 = config.PLAYER_COLORS["p1"]
    r2, g2, b2 = config.PLAYER_COLORS["p2"]
    assert b1 > r1 and r2 > b2


def test_idle_timeout_is_a_minute():
    assert config.IDLE_TIMEOUT == 60.0


@pytest.mark.parametrize("distance, clamped", [(-3, 0), (17, 16), (99, 16)])
def test_circuit_check_boost_clamps_the_distance(distance, clamped):
    assert config.check_boost(distance) == config.check_boost(clamped)
