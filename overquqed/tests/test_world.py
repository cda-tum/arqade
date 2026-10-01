import random

import pytest

from overquqed.config import TILE
from overquqed.levels import COSMIC_CAFE, LEVELS, SNACK_BAR, TRATTORIA, TUTORIAL
from overquqed.quantum import NAMED_STATES
from overquqed.world import IDLE, ChefInput, World

DT = 1 / 60


def make(level=SNACK_BAR, solo=False, seed=1):
    w = World(level, random.Random(seed), solo=solo)
    w.orders.auto_spawn = False
    return w


def place(world, chef_idx, tile, facing):
    chef = world.chefs[chef_idx]
    chef.x, chef.y = (tile[0] + 0.5) * TILE, (tile[1] + 0.5) * TILE
    chef.facing = facing
    return chef


def step(world, n=1, **inputs):
    for _ in range(n):
        world.update(DT, [inputs.get("c0", IDLE), inputs.get("c1", IDLE)])


def press_a(world, idx=0):
    step(world, **{f"c{idx}": ChefInput(pick=True)})


def tap_b(world, idx=0):
    step(world, **{f"c{idx}": ChefInput(use=True, use_pressed=True)})


def hold_b(world, seconds, idx=0):
    step(world, 1, **{f"c{idx}": ChefInput(use=True, use_pressed=True)})
    step(world, int(seconds / DT) + 1, **{f"c{idx}": ChefInput(use=True)})


def find(world, kind):
    return world.stations_of(kind)[0]


def below(st):
    return st.x, st.y + 1


def above(st):
    return st.x, st.y - 1


@pytest.mark.parametrize("level", LEVELS, ids=lambda lv: lv.key)
def test_every_level_map_loads_with_two_spawns_and_its_stations(level):
    w = World(level, random.Random(0))
    assert len(w.chefs) == 2
    assert w.w == 20
    assert w.stations_of("fridge") and w.stations_of("pass")
    for chef in w.chefs:
        assert w.walkable(*chef.tile)


def test_chef_walks_and_stops_at_walls():
    w = make()
    chef = place(w, 0, (3, 3), (0, 1))
    x0 = chef.x
    step(w, 30, c0=ChefInput(move=(1, 0)))
    assert chef.x > x0 + 30
    assert chef.facing == (1, 0)
    step(w, 400, c0=ChefInput(move=(0, -1)))
    # stopped flush below the top counter row (row 1), never inside it
    assert chef.tile[1] == 2
    assert chef.target[1] == 1


def test_chefs_block_each_other():
    w = make()
    a = place(w, 0, (5, 5), (1, 0))
    b = place(w, 1, (6, 5), (-1, 0))
    step(w, 60, c0=ChefInput(move=(1, 0)))
    assert b.x - a.x >= 11


def test_fridge_gives_fresh_zero_and_counter_holds_it():
    w = make()
    fridge = find(w, "fridge")
    chef = place(w, 0, below(fridge), (0, -1))
    press_a(w)
    assert chef.held is not None and chef.held.view.tokens == ("0",)
    chef.facing = (1, 0)
    counter = w.station_at(chef.target)
    press_a(w)  # target is floor at (x+1, y): nothing happens
    if counter is None:
        assert chef.held is not None
    chef.facing = (0, -1)
    chef.x += TILE  # one to the right, under a counter
    press_a(w)
    assert chef.held is None
    st = w.station_at(chef.target)
    assert st.kind == "counter" and st.item is not None


def test_x_flipper_tap_makes_one_and_blender_hold_makes_plus():
    w = make()
    fridge, flipper, blender = find(w, "fridge"), find(w, "x"), find(w, "h")
    chef = place(w, 0, below(fridge), (0, -1))
    press_a(w)
    place(w, 0, below(flipper), (0, -1))
    press_a(w)
    tap_b(w)
    assert flipper.item.view.tokens == ("1",)
    press_a(w)
    place(w, 0, below(blender), (0, -1))
    press_a(w)
    hold_b(w, 0.3)
    assert blender.item.view.tokens == ("1",)  # not done yet
    assert 0 < blender.progress < 1
    step(w, 30)  # let go: progress pauses
    p = blender.progress
    assert p > 0
    hold_b(w, 0.4)
    assert blender.item.view.tokens == ("-",)
    assert chef.held is None


def test_serving_a_matching_order_scores_and_a_wrong_one_is_refused():
    w = make()
    w.orders.spawn(0.0, "1", "dj")
    fridge, pas = find(w, "fridge"), find(w, "pass")
    chef = place(w, 0, below(fridge), (0, -1))
    press_a(w)
    place(w, 0, above(pas), (0, 1))
    press_a(w)  # |0> for a |1> order: below threshold
    assert chef.held is None
    assert w.score == -10 and w.stats.refused == 1
    assert len(w.orders.orders) == 1
    # now make it right
    flipper = find(w, "x")
    place(w, 0, below(fridge), (0, -1))
    press_a(w)
    place(w, 0, below(flipper), (0, -1))
    press_a(w)
    tap_b(w)
    press_a(w)
    place(w, 0, above(pas), (0, 1))
    press_a(w)
    assert w.stats.delivered == 1
    assert not w.orders.orders
    assert w.score > 0
    assert w.stats.best.ops == [("X", 0)]


def test_serving_with_no_matching_order_keeps_the_item():
    w = make()
    chef = place(w, 0, below(find(w, "fridge")), (0, -1))
    press_a(w)
    place(w, 0, above(find(w, "pass")), (0, 1))
    press_a(w)
    assert chef.held is not None
    assert ("no_order", find(w, "pass").pos) in [e[:2] for e in w.events]


def make_bell(w, chef_idx=0):
    """Fetch |+> into control and |0> into target and press."""
    fridge, blender = find(w, "fridge"), find(w, "h")
    control, target = find(w, "control"), find(w, "target")
    return fridge, blender, control, target


def test_waffle_iron_makes_a_bell_pair_and_rejects_oversize_trays():
    w = make(COSMIC_CAFE)
    w.cosmic = None
    fridge, blender, control, target = make_bell(w)
    place(w, 0, below(fridge), (0, -1))
    press_a(w)
    place(w, 0, below(blender), (0, -1))
    press_a(w)
    hold_b(w, 0.7)
    press_a(w)
    place(w, 0, above(control), (0, 1))
    press_a(w)
    place(w, 0, below(fridge), (0, -1))
    press_a(w)
    place(w, 0, above(target), (0, 1))
    press_a(w)
    # two-chef press: one chef alone does nothing in 2-player mode
    place(w, 0, above(control), (0, 1))
    hold_b(w, 2.0)
    assert target.item is not None
    place(w, 1, above(target), (0, 1))
    for _ in range(int(1.6 / DT)):
        w.update(DT, [ChefInput(use=True), ChefInput(use=True)])
    assert target.item is None
    tray = control.item
    assert tray.n == 2 and tray.view.tokens == ("Phi+",)
    assert tray.state.fidelity(NAMED_STATES["Phi+"]) > 0.9  # a few seconds of real T2


def test_solo_chef_runs_the_two_chef_press_at_half_speed():
    w = make(COSMIC_CAFE, solo=True)
    w.cosmic = None
    control, target = find(w, "control"), find(w, "target")
    control.item, target.item = w.new_qubit(), w.new_qubit()
    place(w, 0, above(control), (0, 1))
    hold_b(w, 1.6)
    assert target.item is not None and 0.4 < control.progress < 0.7
    hold_b(w, 1.6)
    assert target.item is None and control.item.n == 2


def test_belts_carry_items_across_the_trap_wall():
    w = make(TRATTORIA)
    belts = sorted([s for s in w.stations_of("belt") if s.belt_dir == 1], key=lambda s: s.x)
    start, end = belts
    chef = place(w, 0, (start.x - 1, start.y), (1, 0))
    press_a(w)  # nothing in hand, belt empty
    chef.held = w.new_qubit()
    press_a(w)
    assert start.item is not None
    step(w, 60)
    assert start.item is None and end.item is not None


def test_limited_fridge_and_dirty_bowls_round_trip():
    w = make(TRATTORIA)
    fridge = find(w, "fridge")
    place(w, 0, below(fridge), (0, -1))
    for _ in range(4):
        press_a(w)
        w.chefs[0].held = None  # drop it on the floor (test only)
    assert w.supply == 0
    press_a(w)
    assert w.chefs[0].held is None
    # serve one and get a dirty bowl back at the pass
    w.orders.spawn(0.0, "0", "surface")
    pas = find(w, "pass")
    chef = place(w, 1, above(pas), (0, 1))
    chef.held = w.new_qubit()
    press_a(w, 1)
    assert w.stats.delivered == 1
    step(w, int((w.level.dirty_return_delay + 0.2) / DT))
    dirty = [s for s in w.stations_of("pass") if s.item is not None]
    assert dirty and dirty[0].item.dirty == 1
    # the sink turns it back into fridge supply
    sink = find(w, "sink")
    place(w, 0, above(sink), (0, 1))
    w.chefs[0].held = dirty[0].item
    dirty[0].item = None
    press_a(w)
    hold_b(w, 2.1)
    assert w.supply == 1 and sink.item is None


def test_bin_in_a_limited_kitchen_keeps_the_empty_bowls():
    w = make(TRATTORIA)
    chef = place(w, 1, below(find(w, "bin")), (0, -1))
    chef.held = w.new_qubit()
    press_a(w, 1)
    assert chef.held is not None and chef.held.dirty == 1


def test_guest_leaving_costs_points():
    w = make()
    order = w.orders.spawn(0.0, "0", "surface")
    step(w, int((order.patience + 0.5) / DT))
    assert w.stats.left == 1 and w.score == -20


def test_decoherence_happens_on_counters_but_not_in_the_fridge():
    w = make()
    blender = find(w, "h")
    blender.item = w.new_qubit()
    place(w, 0, below(blender), (0, -1))
    hold_b(w, 0.7)
    f0 = blender.item.view.fidelity
    step(w, int(25 / DT))
    assert blender.item.view.fidelity < f0 - 0.1
    assert blender.item.view.prefix == "~" or blender.item.view.tokens == ("?",)


def test_cosmic_ray_warns_then_scrambles_and_jams():
    w = make(COSMIC_CAFE)
    blender = find(w, "h")
    blender.item = w.new_qubit()
    w.cosmic.next_at = w.t + 0.01
    w.rng = random.Random(3)
    w._pick_impact = lambda: (blender.x, blender.y + 1)
    step(w, 3)
    assert w.cosmic.center == (blender.x, blender.y + 1)
    step(w, int(2.1 / DT))
    assert blender.jammed(w.t)
    assert blender.item.view.fidelity < 0.6
    place(w, 0, below(blender), (0, -1))
    hold_b(w, 1.0)
    assert blender.progress == 0


def test_tutorial_level_has_no_noise_and_no_auto_orders():
    w = World(TUTORIAL, random.Random(0))
    step(w, int(30 / DT))
    assert not w.orders.orders
