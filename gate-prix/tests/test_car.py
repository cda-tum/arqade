import pytest

from gate_prix import config, track
from gate_prix.car import Car, aim, bump
from gate_prix.track import Segment

TOP = config.TOP_SPEED
DT = 1 / 60
STRAIGHT = Segment(0, 0.0, 0.0, 0.0, 0.0, 0.0)


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
    car = Car("green", "green", -0.4)
    assert (car.id, car.colour, car.x, car.z, car.speed) == ("green", "green", -0.4, 0.0, 0.0)
    assert car.kind == "car:green"
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


def test_a_stronger_or_longer_boost_replaces_the_current_one():
    car = at_speed()
    car.give_boost(0.3, 1.0)
    assert car.give_boost(0.4, 0.5)  # stronger
    assert (car.boost, car.boost_time) == (0.4, 0.5)
    assert car.give_boost(0.2, 2.0)  # weaker but outlasts it
    assert (car.boost, car.boost_time) == (0.2, 2.0)


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


def test_a_brake_held_through_a_curve_drifts_the_push_down():
    plain = at_speed()
    plain.update(DT, 0.0, 0.0, bend(3.0))
    drift = at_speed()
    drift.update(DT, 0.0, 1.0, bend(3.0))
    assert drift.drifting and not plain.drifting
    # less push, and not only because of the speed it shed
    undrifted = -config.CURVE_PUSH * (drift.speed / TOP) ** 2 * 3.0 * DT
    assert drift.x == pytest.approx(undrifted * (1 - config.DRIFT))
    assert plain.x < undrifted < drift.x < 0


def test_no_drift_on_a_straight():
    car = at_speed()
    car.update(DT, 0.0, 1.0, STRAIGHT)
    assert not car.drifting


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


LAP = 100_000.0


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
