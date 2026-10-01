import random

import pytest

from overquqed import scoring
from overquqed.guests import GUESTS, OrderBook
from overquqed.levels import LEVELS, star_thresholds
from overquqed.quantum import QState, cnot_merge
from overquqed.recipes import TIER_POINTS


def test_tip_is_zero_at_threshold_and_max_at_perfect():
    assert scoring.fidelity_tip(0.8) == 0
    assert scoring.fidelity_tip(1.0) == scoring.MAX_TIP
    assert scoring.fidelity_tip(0.9) == scoring.MAX_TIP // 2
    assert scoring.fidelity_tip(0.5) == 0
    assert scoring.fidelity_tip(1.0, tip_mult=1.5) == round(scoring.MAX_TIP * 1.5)


def test_delivery_points_add_base_tip_and_speed():
    base, tip, speed = scoring.delivery_points(2, 1.0, 1.0)
    assert (base, tip, speed) == (TIER_POINTS[2], scoring.MAX_TIP, scoring.MAX_SPEED_BONUS)
    assert scoring.delivery_points(1, 0.8, 0.0) == (TIER_POINTS[1], 0, 0)


def test_best_fidelity_wins_and_ties_go_to_the_oldest():
    orders = ["old", "mid", "new"]
    f = {"old": 0.9, "mid": 0.95, "new": 0.95}
    assert scoring.choose_order(orders, f.get) == ("mid", 0.95)
    assert scoring.choose_order(orders, {"old": 1.0, "mid": 1.0, "new": 1.0}.get)[0] == "old"


def test_stars():
    assert scoring.stars(0, (10, 20, 30)) == 0
    assert scoring.stars(20, (10, 20, 30)) == 2
    assert scoring.stars(99, (10, 20, 30)) == 3


@pytest.mark.parametrize("level", LEVELS, ids=lambda lv: lv.key)
def test_star_thresholds_increase_and_solo_is_easier(level):
    a, b, c = level.stars
    assert 0 < a < b < c
    assert star_thresholds(level, True)[2] <= c


def book(**kw):
    defaults = dict(recipes=("0", "+"), guests=("surface",), duration=100.0,
                    spawn_interval=10.0, spawn_interval_end=5.0, rng=random.Random(1))
    defaults.update(kw)
    return OrderBook(**defaults)


def test_spawn_interval_speeds_up_over_the_round():
    b = book()
    assert b.interval_at(0) == 10.0
    assert b.interval_at(50) == 7.5
    assert b.interval_at(100) == 5.0


def test_orders_only_use_the_levels_recipes_and_guests():
    b = book(recipes=("+",), guests=("surface", "shor"))
    for _ in range(20):
        o = b.spawn(0.0)
        assert o.recipe.key == "+" and o.guest.key == "surface"


def test_max_tickets_caps_open_orders():
    b = book(spawn_interval=0.1, spawn_interval_end=0.1, max_tickets=4)
    t = 0.0
    for _ in range(600):
        t += 0.05
        b.update(0.05, t)
    assert len(b.orders) <= 4


def test_serving_matches_the_right_order_and_refuses_below_threshold():
    b = book()
    b.spawn(0.0, "0", "surface")
    b.spawn(0.0, "+", "surface")
    plus = QState.fresh()
    plus.apply("H")
    r = b.serve(plus)
    assert r.accepted and r.order.recipe.key == "+"
    bad = QState.fresh()
    bad.apply("X")
    r = b.serve(bad)
    assert not r.accepted and r.reason == "below-threshold" and r.points == scoring.REFUSE_PENALTY
    assert len(b.orders) == 1  # the |0> order is still open


def test_two_qubit_items_never_match_one_qubit_orders():
    b = book()
    b.spawn(0.0, "0", "surface")
    tray = cnot_merge(QState.fresh(), QState.fresh())
    assert b.serve(tray).reason == "no-order"


def test_first_visit_flag_is_per_guest():
    b = book()
    assert b.spawn(0.0, "0", "surface").first_visit
    assert not b.spawn(0.0, "0", "surface").first_visit


def test_every_guest_orders_something_that_exists():
    from overquqed.recipes import RECIPES

    for g in GUESTS.values():
        assert set(g.orders) <= set(RECIPES)


def test_every_level_guest_can_order_in_that_level():
    for lv in LEVELS:
        for g in lv.guests:
            assert set(GUESTS[g].orders) & set(lv.recipes), (lv.key, g)
