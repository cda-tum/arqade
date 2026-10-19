import pytest

from gate_prix import config, track
from gate_prix.car import Car, aim, bump
from gate_prix.track import Segment

TOP = config.TOP_SPEED
DT = 1 / 60
STRAIGHT = Segment(0, 0.0, 0.0, 0.0, 0.0, 0.0)
LAP = 100_000.0


def bend(curve: float) -> Segment:
    return Segment(0, 0.0, curve, 0.0, 0.0, 0.0)


def drive(car: Car, seconds: float, steer=0.0, brake=0.0, segment=STRAIGHT) -> None:
    for _ in range(round(seconds / DT)):
        car.update(DT, steer, brake, segment)


def at_speed(x=0.0, speed=TOP) -> Car:
    car = Car("p1", "p1", x)
    car.speed = speed
    return car


# --- Speed --------------------------------------------------------------------------------


def test_a_new_car_stands_in_its_lane():
    car = Car("cpu1", "white", -0.4)
    assert (car.id, car.colour, car.x, car.z, car.speed) == ("cpu1", "white", -0.4, 0.0, 0.0)
    assert car.kind == "car:white"
    assert (car.boost, car.boost_time) == (0.0, 0.0)


def test_it_auto_accelerates_to_top_speed_and_holds_it():
    car = Car("p1", "p1", 0.0)
    drive(car, 1.0)
    assert 0.3 * TOP < car.speed < TOP
    drive(car, 2.0)
    assert car.speed == pytest.approx(TOP)
    z = car.z
    drive(car, 1.0)
    assert car.z - z == pytest.approx(TOP, rel=1e-6)


def test_the_stick_steers_and_driving_straight_keeps_the_line():
    car = at_speed()
    drive(car, 0.25, steer=1.0)
    assert car.x == pytest.approx(0.25 * config.STEER_RATE)
    drive(car, 0.25, steer=-1.0)
    assert car.x == pytest.approx(0.0, abs=1e-9)
    drive(car, 1.0)
    assert car.x == pytest.approx(0.0, abs=1e-9)
    assert car.steer == 0.0


def test_steering_never_takes_the_car_past_the_limit():
    car = at_speed()
    drive(car, 3.0, steer=1.0)
    assert car.x == config.X_LIMIT


def test_braking_decelerates_down_to_the_floor():
    car = at_speed()
    drive(car, 0.5, brake=1.0)
    assert car.speed == pytest.approx(TOP - 0.5 * config.BRAKE)
    drive(car, 3.0, brake=1.0)
    assert car.speed == pytest.approx(config.BRAKE_FLOOR * TOP)
    drive(car, 3.0)
    assert car.speed == pytest.approx(TOP)


def test_braking_below_the_floor_holds_the_speed():
    car = at_speed(speed=0.1 * TOP)
    drive(car, 0.5, brake=1.0)
    assert car.speed == pytest.approx(0.1 * TOP)


def test_off_road_caps_the_speed_at_60_percent():
    car = at_speed(x=1.4)
    drive(car, 1.0)
    assert car.offroad
    assert car.speed == pytest.approx(config.OFFROAD_SPEED_FACTOR * TOP)
    car.x = 0.5
    drive(car, 2.0)
    assert not car.offroad
    assert car.speed == pytest.approx(TOP)


def test_the_road_ends_at_one_half_width():
    car = at_speed(x=0.99)
    drive(car, 1.0)
    assert not car.offroad and car.speed == pytest.approx(TOP)
    car = at_speed(x=-1.01)
    drive(car, 1.0)
    assert car.offroad and car.speed < TOP


# --- Boosts -------------------------------------------------------------------------------


def test_a_boost_raises_the_top_speed_for_its_time():
    car = at_speed()
    assert car.give_boost(0.2, 1.0)
    drive(car, 0.5)
    assert car.speed == pytest.approx(1.2 * TOP)
    assert car.boost == 0.2 and car.boost_time == pytest.approx(0.5)
    drive(car, 0.6)
    assert (car.boost, car.boost_time) == (0.0, 0.0)
    drive(car, 1.0)
    assert car.speed == pytest.approx(TOP)


def test_a_boost_lifts_the_off_road_cap_too():
    car = at_speed(x=1.5)
    car.give_boost(0.5, 3.0)
    drive(car, 1.0)
    assert car.speed == pytest.approx(config.OFFROAD_SPEED_FACTOR * 1.5 * TOP)


def test_a_stronger_boost_takes_over_and_the_weaker_one_runs_on_after_it():
    car = at_speed()
    car.give_boost(0.3, 1.0)
    assert car.give_boost(0.4, 0.5)  # stronger: it takes over at once
    assert (car.boost, car.boost_time) == (0.4, 0.5)
    drive(car, 0.6)  # the 0.4 is over; what is left of the 0.3 runs on
    assert car.boost == 0.3 and car.boost_time == pytest.approx(0.4)
    drive(car, 0.5)
    assert (car.boost, car.boost_time) == (0.0, 0.0)


def test_a_weaker_longer_boost_is_a_tail_that_never_weakens_or_shortens_anything():
    car = at_speed()
    car.give_boost(0.8, 0.5)
    assert car.give_boost(0.2, 2.0)  # weaker but outlasts it
    assert (car.boost, car.boost_time) == (0.8, 0.5)  # the 0.8 is untouched
    drive(car, 0.5)
    assert car.speed == pytest.approx(1.8 * TOP)
    drive(car, 0.1)  # the 0.8 has ended: the tail carries on at 0.2
    assert car.boost == 0.2 and car.boost_time == pytest.approx(1.4)
    drive(car, 1.5)
    assert (car.boost, car.boost_time) == (0.0, 0.0)
    assert car.boosts == ()


def test_the_boost_is_never_below_what_it_would_be_without_a_new_one():
    with_new, without = at_speed(), at_speed()
    for car in (with_new, without):
        car.give_boost(0.8, 1.55)
    with_new.give_boost(0.6, 2.0)  # a streak gate arriving during the CIRCUIT CHECK's boost
    for _ in range(200):
        drive(with_new, DT)
        drive(without, DT)
        assert with_new.boost >= without.boost
        assert with_new.z >= without.z


def test_a_weaker_shorter_boost_is_ignored():
    car = at_speed()
    car.give_boost(0.8, 5.0)
    assert not car.give_boost(0.6, 2.0)
    assert not car.give_boost(0.8, 4.0)  # as strong, but over sooner
    assert (car.boost, car.boost_time) == (0.8, 5.0)


def test_an_empty_boost_does_nothing():
    car = at_speed()
    assert not car.give_boost(0.0, 1.0)
    assert (car.boost, car.boost_time) == (0.0, 0.0)


# --- Curves -------------------------------------------------------------------------------


def test_a_right_bend_pushes_the_car_out_to_the_left():
    car = at_speed()
    drive(car, 0.5, segment=bend(2.0))
    assert car.x == pytest.approx(-0.5 * config.CURVE_PUSH * 2.0)
    car = at_speed()
    drive(car, 0.5, segment=bend(-2.0))
    assert car.x == pytest.approx(0.5 * config.CURVE_PUSH * 2.0)


def test_the_push_grows_with_speed_squared_and_the_curve():
    fast, slow = at_speed(), at_speed(speed=TOP / 2)
    assert fast.push(2.0) == pytest.approx(-config.CURVE_PUSH * 2.0)
    assert slow.push(2.0) == pytest.approx(fast.push(2.0) / 4)
    assert fast.push(4.0) == pytest.approx(2 * fast.push(2.0))
    assert fast.push(-2.0) == pytest.approx(-fast.push(2.0))
    assert slow.steer_rate() == pytest.approx(fast.steer_rate() / 2)


def test_a_brake_held_through_a_curve_takes_some_push_away():
    plain = at_speed()
    plain.update(DT, 0.0, 0.0, bend(3.0))
    braked = at_speed()
    braked.update(DT, 0.0, 1.0, bend(3.0))
    assert not braked.drifting and not plain.drifting  # straight back is the brake
    # less push, and not only because of the speed it shed
    unbraked = -config.CURVE_PUSH * (braked.speed / TOP) ** 2 * 3.0 * DT
    assert braked.x == pytest.approx(unbraked * (1 - config.BRAKE_PUSH))
    assert plain.x < unbraked < braked.x < 0


def test_no_drift_on_a_straight_with_the_stick_straight_back():
    car = at_speed()
    car.update(DT, 0.0, 1.0, STRAIGHT)
    assert not car.drifting
    assert car.speed == pytest.approx(TOP - config.BRAKE * DT)


# --- Drifting -------------------------------------------------------------------------------


def test_the_drift_thresholds():
    assert config.DRIFT_STEER == 0.4
    assert config.DRIFT_PULL == 0.0  # any pull past the stick's deadzone, as the brake
    assert (config.DRIFT_MIN_SPEED, config.DRIFT_END_SPEED) == (0.6, 0.5)
    assert config.DRIFT_SPEED == 0.92
    assert config.DRIFT_LEVELS == (0.7, 1.5)
    assert config.DRIFT_TURBOS == ((0.25, 0.6), (0.40, 1.0))
    assert 0 < config.DRIFT_PUSH < 1


def test_stick_back_and_steer_drifts_and_straight_back_brakes():
    car = at_speed()
    car.update(DT, 0.5, 1.0, bend(3.0))
    assert car.drifting and car.drift_dir == 1
    assert car.speed > TOP - config.BRAKE * DT  # a drift is not a brake
    car = at_speed()
    car.update(DT, -0.4, 0.3, bend(-3.0))
    assert car.drifting and car.drift_dir == -1
    car = at_speed()
    car.update(DT, 0.39, 1.0, bend(3.0))  # not enough steer: the brake
    assert not car.drifting
    assert car.speed == pytest.approx(TOP - config.BRAKE * DT)
    car = at_speed()
    car.update(DT, 1.0, 0.0, bend(3.0))  # steering alone is steering
    assert not car.drifting


def test_a_drift_starts_only_at_60_percent_of_top_speed():
    car = at_speed(speed=0.59 * TOP)
    car.update(DT, 1.0, 1.0, bend(3.0))
    assert not car.drifting
    car = at_speed(speed=0.61 * TOP)
    car.update(DT, 1.0, 1.0, bend(3.0))
    assert car.drifting


def test_a_drift_runs_at_92_percent_and_the_curve_pushes_less():
    car = at_speed()
    drive(car, 1.0, steer=0.5, brake=1.0, segment=bend(3.0))
    assert car.drifting
    assert car.speed == pytest.approx(config.DRIFT_SPEED * TOP)
    assert car.push(3.0) == pytest.approx(
        -config.CURVE_PUSH * config.DRIFT_SPEED ** 2 * 3.0 * config.DRIFT_PUSH)
    # turning tighter: the same stick holds a tighter line than without the drift
    plain = at_speed()
    drive(plain, 1.0, steer=0.5, segment=bend(3.0))
    assert car.x > plain.x


def test_a_boosted_drift_runs_at_92_percent_of_the_boosted_speed():
    car = at_speed(speed=1.3 * TOP)
    car.give_boost(0.3, 5.0)
    drive(car, 1.0, steer=0.5, brake=1.0, segment=bend(3.0))
    assert car.speed == pytest.approx(config.DRIFT_SPEED * 1.3 * TOP)


def drift_for(seconds, steer=0.6, segment=None):
    car = at_speed()
    drive(car, seconds, steer=steer, brake=1.0, segment=segment or bend(3.0))
    return car


@pytest.mark.parametrize("seconds, level", [(0.5, 0), (0.75, 1), (1.4, 1), (1.55, 2), (3.0, 2)])
def test_the_charge_levels(seconds, level):
    car = drift_for(seconds)
    assert car.drifting and car.drift_level == level
    assert car.drift_time == pytest.approx(seconds, abs=DT)


@pytest.mark.parametrize("seconds, turbo", [(0.5, None), (0.75, (0.25, 0.6)), (1.55, (0.40, 1.0))])
def test_letting_go_gives_the_mini_turbo_of_its_level(seconds, turbo):
    car = drift_for(seconds)
    car.update(DT, 0.6, 0.0, bend(3.0))  # the stick no longer back: let go
    assert not car.drifting and car.drift_level == 0
    if turbo is None:
        assert car.boost == 0.0 and ("turbo", 1) not in car.cues
    else:
        assert car.boosts == ((turbo[0], pytest.approx(turbo[1])),)
        level = 1 if turbo[0] == 0.25 else 2
        assert ("turbo", level) in car.cues
        assert car.turbo_level == level and car.turbo_flash == pytest.approx(config.TURBO_FLASH)


def test_easing_the_steer_below_the_threshold_lets_go_too():
    car = drift_for(0.8)
    car.update(DT, 0.2, 1.0, bend(3.0))
    assert not car.drifting and car.boost == pytest.approx(0.25)


def test_steering_the_other_way_lets_go_and_starts_a_new_drift():
    car = drift_for(0.8)
    car.update(DT, -0.6, 1.0, bend(3.0))
    assert car.boost == pytest.approx(0.25)
    assert car.drifting and car.drift_dir == -1
    assert car.drift_time == 0.0  # against the bend: no charge


def test_the_charge_threshold():
    assert config.DRIFT_CHARGE_CURVE == 1.0


def test_a_drift_charges_only_into_a_real_bend():
    for segment, steer in ((STRAIGHT, 0.6), (bend(0.9), 0.6), (bend(3.0), -0.6)):
        car = at_speed()
        drive(car, 2.0, steer=steer, brake=1.0, segment=segment)
        assert car.drifting and car.drift_time == 0.0 and car.drift_level == 0
        car.update(DT, steer, 0.0, segment)
        assert car.boost == 0.0  # let go: nothing
    car = at_speed()
    drive(car, 0.8, steer=-0.6, brake=1.0, segment=bend(-1.2))
    assert car.drift_level == 1


def test_a_charge_built_in_a_bend_is_held_on_a_straight_but_does_not_grow():
    car = drift_for(0.8)
    charge = car.drift_time
    drive(car, 1.0, steer=0.6, brake=1.0, segment=STRAIGHT)
    assert car.drifting and car.drift_time == charge and car.drift_level == 1
    drive(car, 0.75, steer=0.6, brake=1.0, segment=bend(3.0))
    assert car.drift_level == 2


def test_snaking_on_a_straight_earns_no_turbo_and_loses_ground():
    """Weaving with the stick back (a drift each way, over and over) on a straight is no
    way to go faster: no charge, so no turbo, and the drift's 92% speed."""
    snake, plain = at_speed(), at_speed()
    cues = []
    for i in range(round(10.0 / DT)):
        side = 1.0 if (i // 48) % 2 else -1.0  # 0.8 s each way: past level 1's 0.7 s
        snake.update(DT, side, 1.0, STRAIGHT)
        cues += snake.cues
        plain.update(DT, 0.0, 0.0, STRAIGHT)
    assert not [c for c in cues if c[0] in ("drift", "turbo")]
    assert snake.boost == 0.0 and snake.z < plain.z



def test_the_charge_cues_each_level_once():
    car = at_speed()
    cues = []
    for _ in range(round(2.0 / DT)):
        car.update(DT, 0.6, 1.0, bend(3.0))
        cues += car.cues
    assert cues == [("drift", 1), ("drift", 2)]


def test_slowing_below_half_speed_ends_a_drift_with_no_turbo():
    car = drift_for(1.0)
    car.speed = 0.45 * TOP
    car.update(DT, 0.6, 1.0, bend(3.0))
    assert not car.drifting and car.boost == 0.0
    car.update(DT, 0.6, 1.0, bend(3.0))  # and it cannot start again that slow
    assert not car.drifting


def test_a_bump_ends_a_drift_with_no_turbo():
    a = drift_for(1.0)
    b = at_speed(x=a.x + 0.1)
    b.z = a.z
    assert bump(a, b, LAP) == "side"
    assert not a.drifting and a.drift_time == 0.0 and a.boost == 0.0


def test_the_drift_angle_leans_into_the_slide_and_back():
    car = drift_for(1.0)
    assert car.drift_angle == pytest.approx(config.DRIFT_ANGLE)
    left = drift_for(1.0, steer=-0.6, segment=bend(-3.0))
    assert left.drift_angle == pytest.approx(-config.DRIFT_ANGLE)
    drive(car, 1.0)
    assert car.drift_angle == 0.0


# --- Spin-outs, slowdowns and tunnelling ---------------------------------------------------


def test_a_spin_out_drops_to_40_percent_and_the_stick_does_nothing_for_0_8_s():
    car = drift_for(1.0)
    speed = car.speed
    car.spin()
    assert car.speed == pytest.approx(config.SPIN_SPEED * speed)
    assert not car.drifting and car.boost == 0.0  # no turbo
    assert car.spinning and car.spin_time == config.SPIN_TIME == 0.8
    x = car.x
    for _ in range(round(config.SPIN_TIME / DT)):
        car.update(DT, 1.0, 1.0, STRAIGHT)
        assert car.x == x and not car.drifting
    assert not car.spinning
    car.update(DT, 1.0, 0.0, STRAIGHT)
    assert car.x > x


def test_a_slowdown_caps_the_speed_for_its_time():
    car = at_speed()
    car.slow(config.CLOUD_CAP, config.CLOUD_TIME)
    assert car.speed == pytest.approx(0.7 * TOP)
    drive(car, config.CLOUD_TIME - DT)
    assert car.speed == pytest.approx(0.7 * TOP) and car.slow_time > 0
    drive(car, 2 * DT)
    assert car.slow_time == 0.0
    drive(car, 1.0)
    assert car.speed > 0.7 * TOP


def test_clearing_the_boosts():
    car = at_speed()
    car.give_boost(0.5, 3.0)
    car.give_boost(0.2, 6.0)
    car.clear_boosts()
    assert car.boosts == () and car.boost == 0.0


def test_a_tunnelling_car_drives_off_road_at_full_speed_for_its_time():
    car = at_speed(x=1.5)
    car.tunnel(config.TUNNEL_TIME)
    assert car.tunnelling and car.tunnel_time == 3.0
    drive(car, 1.0)
    assert car.offroad and car.speed == pytest.approx(TOP)
    cues = []
    for _ in range(round(2.5 / DT)):
        car.update(DT, 0.0, 0.0, STRAIGHT)
        cues += car.cues
    assert not car.tunnelling and cues.count(("tunnel_end", None)) == 1
    assert car.speed < TOP


# --- Handling round THE FRIDGE ---------------------------------------------------------------


def line_driver(fridge, car, lookahead=600.0):
    """Follow the racing line with `aim`, as a human would: look a little ahead."""
    seg = fridge.segment_at(car.z)
    goal = fridge.segment_at(car.z + lookahead).line
    return aim(car, goal, seg), seg


def drive_lap(stick=1.0, brakes=True):
    """One lap of THE FRIDGE from top speed on the racing line: the segments it braked
    on, the most stick it used, its slowest speed and the furthest it strayed."""
    fridge = track.fridge()
    car = at_speed(x=0.0)
    braked_at, steer_most, slowest, widest = set(), 0.0, TOP, 0.0
    while car.z < fridge.lap_length():
        (steer, brake), seg = line_driver(fridge, car)
        steer = max(-stick, min(stick, steer))
        brake = brake if brakes else 0.0
        if brake:
            braked_at.add(seg.index)
        car.update(DT, steer, brake, seg)
        steer_most = max(steer_most, abs(steer))
        slowest = min(slowest, car.speed)
        widest = max(widest, abs(car.x))
    return braked_at, steer_most, slowest, widest


def test_the_racing_line_holds_every_curve_at_top_speed():
    braked_at, _, slowest, widest = drive_lap()
    assert widest < 0.65  # the line is within 0.6, and the driver keeps to it
    # only the coax corner (curve 4.4, segments 844-949) needs a touch of brake
    assert braked_at, "the sharpest corner should need a little brake"
    assert all(844 <= i < 949 for i in braked_at), sorted(braked_at)
    assert slowest > 0.9 * TOP


def test_braking_is_optional_and_moderate_stick_is_enough():
    # never braking, never more than three quarters of the stick: still on the road
    braked_at, steer_most, slowest, widest = drive_lap(stick=0.75, brakes=False)
    assert not braked_at and steer_most <= 0.75
    assert widest < 1.0 and slowest == pytest.approx(TOP)


def test_every_curve_but_the_coax_corner_holds_with_moderate_stick():
    fridge = track.fridge()
    sharpest = max(abs(seg.curve) for seg in fridge.segments)
    for seg in fridge.segments:
        hold = config.CURVE_PUSH * abs(seg.curve) / config.STEER_RATE  # of full stick
        if abs(seg.curve) <= 3.3:  # the sweepers, the kink and the S-bend
            assert hold <= 0.75, (seg.index, seg.curve)
    # the coax corner: full stick only just holds it, so it takes a touch of brake
    assert config.CURVE_PUSH * sharpest / config.STEER_RATE > 0.95


def test_aim_closes_on_its_goal_and_cancels_the_push():
    car = at_speed(x=-0.5)
    for _ in range(120):
        steer, brake = aim(car, 0.3, bend(2.0))
        car.update(DT, steer, brake, bend(2.0))
    assert car.x == pytest.approx(0.3, abs=0.01)
    assert brake == 0.0


# --- Bumps ----------------------------------------------------------------------------------


def test_side_by_side_cars_bump_apart():
    a, b = at_speed(x=0.0), at_speed(x=0.1)
    a.z = b.z = 5000.0
    assert bump(a, b, LAP) == "side"
    assert b.x - a.x == pytest.approx(config.CAR_WIDTH)
    assert a.x < 0.0 < b.x
    assert a.knock < 0 < b.knock
    drive(a, 0.1)
    drive(b, 0.1)
    assert b.x - a.x > config.CAR_WIDTH  # the knock carries them further apart
    assert a.speed == b.speed == pytest.approx(TOP)


def test_a_rear_bump_slows_the_car_behind_only():
    front, back = at_speed(x=0.0, speed=0.8 * TOP), at_speed(x=0.05)
    front.z, back.z = 5000.0, 5000.0 - 0.5 * config.CAR_LENGTH
    assert bump(front, back, LAP) == "rear"
    assert back.speed == pytest.approx(config.BUMP_SLOW * 0.8 * TOP)
    assert front.speed == pytest.approx(0.8 * TOP)
    assert front.z == 5000.0
    assert front.z - back.z == pytest.approx(config.CAR_LENGTH)
    assert back.knock == config.BUMP_NUDGE and front.knock == 0.0  # back is to the right


def test_cars_apart_do_not_bump():
    a, b = at_speed(x=-0.5), at_speed(x=0.5)
    assert bump(a, b, LAP) is None
    b.x = -0.5
    b.z = config.CAR_LENGTH + 1
    assert bump(a, b, LAP) is None
    assert (a.x, b.x, a.z, b.z) == (-0.5, -0.5, 0.0, config.CAR_LENGTH + 1)


def test_a_lapped_car_bumps_where_it_really_is():
    leader, lapped = at_speed(x=0.0), at_speed(x=0.1)
    leader.z = LAP + 5000.0
    lapped.z = 5000.0 + 50.0
    assert bump(leader, lapped, LAP) == "side"
    assert lapped.x > leader.x


def test_identical_positions_still_part():
    a, b = at_speed(), at_speed()
    assert bump(a, b, LAP) == "side"
    assert b.x - a.x == pytest.approx(config.CAR_WIDTH)
