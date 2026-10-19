import pytest

from gate_prix import config


def test_race_shape():
    assert config.CARS == 6
    assert config.LAPS == 3
    assert config.ROWS_PER_LAP == 8
    assert config.GATE_LAPS == 2  # the final lap has no gates
    assert config.SLOTS == 16
    assert config.CHECK_SLOTS == config.SLOTS  # the check covers the whole target
    assert (config.ARCHES_MIN, config.ARCHES_MAX) == (1, 3)
    assert config.MAX_PLAYERS == 2  # people; bots fill the rest of the CARS
    assert config.CPU_IDS == ("cpu1", "cpu2", "cpu3", "cpu4", "cpu5")
    assert config.ITEM_BOXES_PER_LAP == 2


def test_resolution_divides_the_panel_exactly():
    assert (config.INTERNAL_WIDTH, config.INTERNAL_HEIGHT) == (960, 540)
    assert 1920 % config.INTERNAL_WIDTH == 0 and 1080 % config.INTERNAL_HEIGHT == 0
    assert config.VIEW_2P == (480, 540)  # side by side: two of them fill the screen


@pytest.mark.parametrize(
    "streak, strength, seconds",
    [(1, 0.30, 1.5), (2, 0.40, 1.75), (3, 0.50, 2.0), (4, 0.60, 2.25), (5, 0.70, 2.5)],
)
def test_streak_boost_table(streak, strength, seconds):
    got_strength, got_seconds = config.streak_boost(streak)
    assert got_strength == pytest.approx(strength)
    assert got_seconds == pytest.approx(seconds)


@pytest.mark.parametrize("streak", [6, 12, 16])
def test_streak_boost_is_capped(streak):
    strength, seconds = config.streak_boost(streak)
    assert strength == pytest.approx(0.70)
    assert seconds == pytest.approx(2.5)


def test_streak_boost_of_zero_is_nothing():
    assert config.streak_boost(0) == (0.0, 0.0)


@pytest.mark.parametrize(
    "distance, strength, seconds",
    [(0, 1.00, 6.0), (16, 0.0, 2.0), (3, (13 / 16) ** 2, 2.0 + 13 * 0.25), (8, 0.25, 4.0),
     (4, 0.5625, 5.0)],
)
def test_circuit_check_boost(distance, strength, seconds):
    got_strength, got_seconds = config.check_boost(distance)
    assert got_strength == pytest.approx(strength)
    assert got_seconds == pytest.approx(seconds)


def test_the_top_speed_is_12_percent_up_and_the_rates_keep_their_timing():
    assert config.TOP_SPEED == 11_200.0
    top = config.TOP_SPEED
    assert config.ACCEL == pytest.approx(top / 2)  # standing to top speed in 2 s
    assert config.BOOST_ACCEL == pytest.approx(2 * top)
    assert config.COAST_DECEL == pytest.approx(top / 2)
    assert config.BRAKE == pytest.approx(0.6 * top)


def test_the_check_freezes_a_view_for_about_a_second():
    assert config.CHECK_FREEZE == 1.0
    assert 0.6 <= config.FLASH_TIME <= 1.0


def test_decoys_are_smaller_than_the_right_arch():
    assert config.DECOY_HALF_WIDTH == pytest.approx(0.8 * config.ARCH_HALF_WIDTH)


def test_a_better_circuit_out_boosts_a_worse_one_by_more_than_in_proportion():
    """The check rewards accuracy steeply, so a good circuit's warp passes the CPUs (whose
    own checks are 10-14 of 16 right): 2 more right gates are worth at least +15% (in
    proportion they would be +12.5%), and more the better the circuit already is."""
    for right in range(10, 15):
        better, worse = config.check_boost(16 - right - 2), config.check_boost(16 - right)
        assert better[0] - worse[0] >= 0.15 and better[1] > worse[1]
    gains = [config.check_boost(d - 1)[0] - config.check_boost(d)[0] for d in range(16, 0, -1)]
    assert gains == sorted(gains)


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


def _hue(rgb):
    import colorsys

    h, s, v = colorsys.rgb_to_hsv(*(c / 255 for c in rgb))
    return h * 360, s, v


def test_the_cars_take_their_colours_from_one_place():
    for p in ("p1", "p2"):
        assert config.CAR_COLORS[p] == config.PLAYER_COLORS[p]
    assert set(config.CAR_COLORS) == {"p1", "p2", *config.CPU_COLORS}
    assert len(config.CPU_COLORS) == config.CARS - 1  # a lone player's full field


# Hue bands that belong to the players (AGENTS.md): P1 is blue or blue-leaning (cyan,
# teal), P2 red or red-leaning (orange, pink), P3 green and P4 purple. A bot's colour is
# none of them: neutral (a grey) or a pale warm tone (tan, cream) between orange and green.
P1_BAND = (165, 265)
P2_BAND = (315, 35)  # wraps round 0
P3_BAND = (65, 165)  # lime to emerald
P4_BAND = (265, 315)
WARM = (35, 65)  # tan, sand, cream: allowed, but only pale
NEUTRAL_SAT = 0.15  # below this a colour is a grey, whatever its hue
PALE_SAT = 0.45  # a warm tone stays below this


def _in_band(h, band):
    lo, hi = band
    return lo <= h <= hi if lo < hi else h >= lo or h <= hi


def _neutral(rgb):
    h, s, _ = _hue(rgb)
    return s < NEUTRAL_SAT or (_in_band(h, WARM) and s < PALE_SAT)


@pytest.mark.parametrize("rgb, ok", [
    ((30, 196, 178), False),  # teal
    ((40, 220, 240), False),  # cyan
    ((255, 112, 24), False),  # orange
    ((255, 110, 200), False),  # pink
    ((30, 180, 90), False),  # emerald (P3's green)
    ((150, 220, 40), False),  # lime
    ((168, 80, 216), False),  # purple (P4)
    ((248, 192, 40), False),  # the H gate's gold: too strong
    ((236, 238, 246), True),  # white
    ((150, 154, 166), True),  # grey
    ((176, 148, 106), True),  # tan
    ((238, 228, 150), True),  # cream
])
def test_neutral_means_a_grey_or_a_pale_warm_tone(rgb, ok):
    assert _neutral(rgb) == ok


def test_bot_colours_are_neutral_and_clear_of_the_players_the_gates_and_each_other():
    def dist(a, b):
        return sum((x - y) ** 2 for x, y in zip(a, b)) ** 0.5

    bots = list(config.CPU_COLORS.values())
    for name, rgb in config.CPU_COLORS.items():
        h, s, v = _hue(rgb)
        assert _neutral(rgb), name
        if s >= NEUTRAL_SAT:  # a hue at all: none of the players' bands
            for band in (P1_BAND, P2_BAND, P3_BAND, P4_BAND):
                assert not _in_band(h, band), name
        for other in (*config.PLAYER_COLORS.values(), *config.GATE_COLORS.values()):
            assert dist(rgb, other) >= 80, name
        # the H gate's gold is the nearest hue: the cream is far paler
        assert s < _hue(config.GATE_COLORS["H"])[1] - 0.35, name
    for i, a in enumerate(bots):
        for b in bots[i + 1:]:
            assert dist(a, b) >= 60, (a, b)  # every two apart on the road


def test_idle_timeout_is_a_minute():
    assert config.IDLE_TIMEOUT == 60.0


@pytest.mark.parametrize("distance, clamped", [(-3, 0), (17, 16), (99, 16)])
def test_circuit_check_boost_clamps_the_distance(distance, clamped):
    assert config.check_boost(distance) == config.check_boost(clamped)


def test_the_graphite_bot_stands_out_from_the_road():
    r, g, b = config.CPU_COLORS["graphite"]
    assert min(r, g, b) >= 55  # the road is (40, 42, 62) and (34, 36, 54)
