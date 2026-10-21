"""ERWIN (docs/superpowers/specs/2026-10-21-brawl-ket-erwin-dos-design.md, section 2): THE BOX
splits him into two boxes and any attack that touches one measures him, 50/50; he collapses
himself with a press, a new stick direction or after 1.5 s, popping out with a swipe; POUNCE
leaps and knocks down; BOX DROP lets a little box fall from the air. And the fight's seeded
random source, which the 50/50s come from."""

import random
from dataclasses import replace

import pytest

from brawl_ket import basis
from brawl_ket.basis import X_BASIS
from brawl_ket.config import BOX_FRAMES, BOX_SPLIT, STAGE_RIGHT, TUNNEL_PAST
from brawl_ket.fight import Fight, Shot
from brawl_ket.fighter import IDLE, FighterInput
from brawl_ket.moves import BOHR, ERWIN, PHOEBE, ROBERT, Box

X = FighterInput(x=True)
A = FighterInput(a=True)
DOWN_X = FighterInput(down=True, x=True)
UP = FighterInput(up=True)
BOX, POUNCE, DROP = (ERWIN.moves[s] for s in ("stand.X", "crouch.X", "air.X"))
SWIPE = BOX.pop_out
PHOTON = ROBERT.moves["stand.X"]


def heads_seed(heads: bool) -> int:
    """A fight seed whose first 50/50 comes up heads (random() < 0.5) or tails. Heads: a
    measured box is the one he is in; his own collapse picks box 1 (where he stood)."""
    return next(s for s in range(100) if (random.Random(s).random() < 0.5) == heads)


def versus(c1, c2, gap, seed=0):
    fight = Fight({"p1": c1, "p2": c2}, seed=seed)
    fight.fighters["p2"].x = fight.fighters["p1"].x + gap
    return fight


def step(fight, p1=IDLE, p2=IDLE):
    return fight.step({"p1": p1, "p2": p2})


def kinds(events):
    return [e.kind for e in events]


def hits_on(events, player):
    return [e for e in events if e.kind in ("hit", "block") and e.player == player]


def boxed(gap=300, seed=0, rival=ROBERT):
    """ERWIN (p1) presses X `gap` px from the rival and is stepped until he splits."""
    fight = versus(ERWIN, rival, gap, seed)
    me = fight.fighters["p1"]
    events = step(fight, X)
    for _ in range(20):
        if me.boxed:
            break
        events += step(fight)
    assert me.boxed
    return fight, me, events


# --- the seeded fight -------------------------------------------------------------------------


def test_a_fight_takes_a_seed_and_owns_its_random_source():
    a = Fight({"p1": ERWIN, "p2": ROBERT}, seed=7)
    b = Fight({"p1": ERWIN, "p2": ROBERT}, seed=7)
    assert a.seed == 7 and [a.rng.random() for _ in range(3)] == [b.rng.random() for _ in range(3)]
    assert Fight({"p1": ROBERT, "p2": ROBERT}).seed == 0
    assert all(f.rng is a.rng for f in a.fighters.values())


def test_the_same_seed_gives_the_same_collapse_and_seeds_differ():
    def where(seed):
        fight, me, _ = boxed(seed=seed)
        step(fight, A)
        return me.box_real

    assert where(3) == where(3)
    assert {where(s) for s in range(10)} == {0, 1}


# --- THE BOX: the split -----------------------------------------------------------------------


def test_the_box_splits_where_she_stood_and_120_px_towards_the_rival():
    fight, me, events = boxed(gap=200)
    x0 = me.boxes[0]
    assert me.boxes == (x0, x0 + BOX_SPLIT) and me.x == x0
    assert "box_split" in kinds(events)
    assert me.cooldowns.get("stand.X", 0) == 0          # the cooldown waits for the collapse


def test_box_2_can_land_behind_a_close_rival_and_stays_on_the_stage():
    fight, me, _ = boxed(gap=60)
    assert me.boxes[1] > fight.fighters["p2"].x         # behind the rival
    fight = versus(ERWIN, ROBERT, 50)
    me, rival = fight.fighters["p1"], fight.fighters["p2"]
    me.x, rival.x = STAGE_RIGHT - 60.0, STAGE_RIGHT - 10.0
    step(fight, X)
    for _ in range(BOX.startup):
        step(fight)
    assert me.boxed and me.boxes == (STAGE_RIGHT - 60.0, STAGE_RIGHT)


def test_while_superposed_she_has_no_body_and_the_rival_walks_through_a_box():
    fight, me, _ = boxed(gap=200)
    rival = fight.fighters["p2"]
    for _ in range(40):
        step(fight, IDLE, FighterInput(dx=-1))
    assert me.boxed and rival.x < me.boxes[1]           # walked straight through box 2


# --- THE BOX: measured by the rival -----------------------------------------------------------


@pytest.mark.parametrize("k", [0, 1])
@pytest.mark.parametrize("heads", [True, False])
def test_a_strike_on_a_box_measures_her(k, heads):
    fight, me, _ = boxed(seed=heads_seed(heads))
    rival = fight.fighters["p2"]
    rival.x = me.boxes[k] + 40              # beside box k, jabbing it
    events = []
    for i in range(12):
        events += step(fight, IDLE, FighterInput(a=i == 0))
    where = k if heads else 1 - k
    (collapse,) = [e for e in events if e.kind == "box_collapse"]    # once, where he turned out to be
    assert not me.boxed and me.box_real == where and collapse.x == me.boxes[where]
    if heads:       # he is in that box: the jab resolves against him as normal
        assert kinds(hits_on(events, "p1")) == ["hit"] and me.health == ERWIN.health - 4
    else:           # he is in the other one: it finds nothing
        assert hits_on(events, "p1") == [] and me.health == ERWIN.health


def test_measured_into_the_other_box_she_is_free_at_once():
    fight, me, _ = boxed(seed=heads_seed(False))
    rival = fight.fighters["p2"]
    rival.x = me.boxes[0] + 40
    for i in range(12):
        events = step(fight, IDLE, FighterInput(a=i == 0))
        if "box_collapse" in kinds(events):
            break
    assert me.action == "idle" and me.move is None      # no swipe: he just appears


def test_a_wrong_colour_strike_on_the_box_she_is_in_bounces():
    fight, me, _ = boxed(seed=heads_seed(True))
    rival = fight.fighters["p2"]
    rival.basis = X_BASIS                   # a purple jab: green ERWIN isn't hurt by it
    rival.x = me.boxes[0] + 40
    events = []
    for i in range(12):
        events += step(fight, IDLE, FighterInput(a=i == 0))
    assert kinds(hits_on(events, "p1")) == ["block"] and me.health == ERWIN.health


@pytest.mark.parametrize("heads", [True, False])
def test_a_shot_into_a_box_measures_her_and_flies_on_if_she_is_not_there(heads):
    fight, me, _ = boxed(seed=heads_seed(heads))
    shot = Shot("p2", PHOTON, me.boxes[0] + 40, 0.0, -PHOTON.projectile.speed, 200)
    fight.shots.append(shot)
    events = step(fight)
    assert not me.boxed
    if heads:
        assert me.x == me.boxes[0] and kinds(hits_on(events, "p1")) == ["hit"] and shot not in fight.shots
    else:
        assert me.x == me.boxes[1] and hits_on(events, "p1") == [] and shot in fight.shots


@pytest.mark.parametrize("k", [0, 1])
@pytest.mark.parametrize("heads", [True, False])
def test_a_throw_in_reach_of_a_box_measures_her(heads, k):
    fight, me, _ = boxed(seed=heads_seed(heads))
    rival = fight.fighters["p2"]
    rival.x = me.boxes[k] + 46              # in throw range of box k (box 2 too, not just his x)
    events = []
    for i in range(10):
        events += step(fight, IDLE, FighterInput(dx=-1, b=True) if i == 0 else IDLE)
    got = [(e.kind, e.error) for e in hits_on(events, "p1")]
    where = k if heads else 1 - k
    assert not me.boxed and me.x == me.boxes[where]
    if heads:
        assert got == [("hit", basis.Y)] and me.action == "knockdown"
    else:
        assert got == []


@pytest.mark.parametrize("heads", [True, False])
def test_an_attack_touching_both_boxes_always_finds_her(heads):
    fight, me, _ = boxed(seed=heads_seed(heads))
    rival = fight.fighters["p2"]
    rival.x = me.boxes[0] + 40
    big = replace(PHOTON, projectile=replace(PHOTON.projectile, box=Box(-100, 0, 220, 100)))
    wide = Shot("p2", big, me.boxes[0] + 60, 0.0, -1.0, 200)    # a wall of light over both boxes
    fight.shots.append(wide)
    events = step(fight)
    assert not me.boxed and kinds(hits_on(events, "p1")) == ["hit"] and wide not in fight.shots


@pytest.mark.parametrize("heads", [True, False])
def test_charge_noise_over_both_boxes_finds_her_with_its_first_shock(heads):
    fight, me, _ = boxed(seed=heads_seed(heads), rival=BOHR)
    bohr = fight.fighters["p2"]
    bohr.x = me.boxes[0] + 50               # its field covers box 1 and the edge of box 2
    noise = BOHR.moves["crouch.X"]
    events = []
    for i in range(noise.startup + 5):
        events += step(fight, IDLE, FighterInput(down=True, x=i == 0))
    assert not me.boxed and "box_collapse" in kinds(events)
    assert kinds(hits_on(events, "p1"))[:1] == ["hit"]


def test_tunnel_past_a_superposed_erwin_goes_past_box_1():
    fight = versus(ERWIN, PHOEBE, 200)
    erwin, phoebe = fight.fighters["p1"], fight.fighters["p2"]
    step(fight, X)
    for _ in range(BOX.startup):
        step(fight)
    assert erwin.boxed
    step(fight, IDLE, DOWN_X)
    for _ in range(25):
        step(fight, IDLE, FighterInput(down=True))
    assert phoebe.x == erwin.boxes[0] - TUNNEL_PAST


# --- THE BOX: collapsed by himself ------------------------------------------------------------


@pytest.mark.parametrize("heads", [True, False])
def test_she_collapses_herself_with_a_press_and_pops_out_with_a_swipe(heads):
    fight, me, _ = boxed(seed=heads_seed(heads))
    events = step(fight, A)
    assert not me.boxed and me.x == me.boxes[0 if heads else 1]
    assert me.move is SWIPE and "box_collapse" in kinds(events)
    assert me.cooldowns["stand.X"] == BOX.cooldown      # the cooldown runs from the collapse


def test_a_new_stick_direction_collapses_her_but_one_held_from_before_does_not():
    fight = versus(ERWIN, ROBERT, 300)
    me = fight.fighters["p1"]
    hold = FighterInput(dx=-1)
    step(fight, FighterInput(dx=-1, x=True))
    for _ in range(BOX.startup + 5):
        step(fight, hold)
    assert me.boxed
    step(fight, UP)
    assert not me.boxed and me.move is SWIPE


def test_she_pops_out_by_herself_after_1_5_s():
    fight, me, _ = boxed()
    for _ in range(BOX_FRAMES - 1):
        step(fight)
    assert me.boxed
    events = step(fight)
    assert not me.boxed and me.move is SWIPE and "box_collapse" in kinds(events)


def test_the_swipe_hits_a_rival_beside_her_box_for_8():
    fight, me, _ = boxed(seed=heads_seed(True))         # heads: he pops out of box 1
    rival = fight.fighters["p2"]
    rival.x = me.boxes[0] + 50
    events = step(fight, A)
    for _ in range(SWIPE.startup + SWIPE.active):
        events += step(fight)
    assert kinds(hits_on(events, "p2")) == ["hit"] and rival.health == ROBERT.health - SWIPE.damage == 92


def test_the_cooldown_runs_from_the_collapse():
    fight, me, _ = boxed()
    for _ in range(40):
        step(fight)                         # time in the boxes doesn't count
    step(fight, A)
    events = []
    for i in range(BOX.cooldown - 1):
        events += step(fight, X if i % 5 == 0 else IDLE)
    assert "box_split" not in kinds(events)
    for i in range(BOX.startup + 6):
        step(fight, X if i == 0 else IDLE)
    assert me.boxed


def test_y_switches_her_basis_while_superposed_and_does_not_collapse_her():
    fight, me, _ = boxed()
    events = step(fight, FighterInput(y=True))
    assert me.boxed and me.basis == X_BASIS and "switch" in kinds(events)


# --- POUNCE and BOX DROP -----------------------------------------------------------------------


def test_pounce_leaps_low_and_knocks_down_a_crouching_rival():
    fight = versus(ERWIN, ROBERT, 120)
    me, rival = fight.fighters["p1"], fight.fighters["p2"]
    events, top = [], 0.0
    for i in range(60):
        events += step(fight, DOWN_X if i == 0 else FighterInput(down=True), FighterInput(down=True))
        top = max(top, me.y)
    assert 30 < top < 60                                # a long, low arc
    assert kinds(hits_on(events, "p2")) == ["hit"] and rival.action == "knockdown"
    assert "pounce" in kinds(events)


def test_a_missed_pounce_lands_into_a_long_recovery():
    fight = versus(ERWIN, ROBERT, 400)
    me = fight.fighters["p1"]
    step(fight, DOWN_X)
    airborne = False
    for _ in range(80):
        step(fight)
        airborne |= me.y > 0
        if airborne and me.y == 0:
            break
    assert me.action == "attack" and me.phase == "recovery"
    stuck = 0
    while me.action == "attack":
        step(fight)
        stuck += 1
    assert POUNCE.recovery - 1 <= stuck <= POUNCE.recovery


def test_box_drop_falls_on_a_rival_below_him():
    fight = versus(ERWIN, ROBERT, 30)
    rival = fight.fighters["p2"]
    events = step(fight, UP)
    for _ in range(14):
        events += step(fight)
    events += step(fight, X)
    box = None
    for _ in range(40):
        events += step(fight)
        box = box or next((s for s in fight.shots if s.owner == "p1"), None)
    assert box is not None and box.vy < 0 and box.move is DROP          # a box, falling
    assert "box_drop" in kinds(events) and kinds(hits_on(events, "p2")) == ["hit"]
    assert rival.health == ROBERT.health - DROP.damage


def test_box_drop_lands_on_the_floor_and_is_once_per_jump():
    fight = versus(ERWIN, ROBERT, 400)
    me = fight.fighters["p1"]
    events = step(fight, UP)
    for _ in range(10):
        events += step(fight)
    while me.y > 0:
        events += step(fight, X)            # mashing X in the air: one box only
    for _ in range(40):
        events += step(fight)
    assert kinds(events).count("box_drop") == 1 and kinds(events).count("fizzle") == 1
    assert not fight.shots
