"""M-CUTIE (docs/superpowers/specs/2026-10-21-brawl-ket-m-cutie-design.md, sections 2, 3 and 6):
AMPLITUDE AMPLIFICATION charges a step per X press and fires a wave along the floor, taller and
harder with every step, lost if she is hit while charging; ION TRAP sets a trap on the floor that
arms, then closes on a rival who steps in and holds them; SPIN hangs at her height and spins
forward, hitting up to three times. And how they meet the others' specials."""

import random

import pytest

from brawl_ket import basis
from brawl_ket.basis import X_BASIS, Z_BASIS
from brawl_ket.config import CHARGE_CAP, CHARGE_WAIT, STAGE_RIGHT, TRAP_ARM, TRAP_GRACE, TRAP_LIFE, TRAP_MAX, TRAP_REACH
from brawl_ket.fight import Fight, Shot, Trap
from brawl_ket.fighter import IDLE, FighterInput
from brawl_ket.moves import AMP_STEPS, AMP_WAVES, BOHR, DOS, ERWIN, M_CUTIE, PHOEBE, ROBERT, TRAP_HOLD

X = FighterInput(x=True)
DOWN_X = FighterInput(down=True, x=True)
UP = FighterInput(up=True)
AMP, TRAP, SPIN = (M_CUTIE.moves[s] for s in ("stand.X", "crouch.X", "air.X"))
PHOTON, LASER = ROBERT.moves["stand.X"], PHOEBE.moves["air.X"]
FLOPPY, MOUSE, COPY = DOS.moves["stand.X"], DOS.moves["crouch.X"], DOS.extra["copy"]
FIRE = AMP_WAVES[0].startup     # frames from the wave move's start to the shot


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


def mash(fight, steps, gap=4):
    """M-CUTIE (p1) presses X `steps` times, `gap` frames apart, then lets go; returns the
    events up to the frame her wave leaves (or 60 frames after the last press)."""
    events = []
    for i in range((steps - 1) * gap + 1):
        events += step(fight, FighterInput(x=i % gap == 0))
    for _ in range(60):
        if fight.shots:
            break
        events += step(fight)
    return events


def heads_seed(heads: bool) -> int:
    """A fight seed whose first 50/50 comes up heads (random() < 0.5) or tails."""
    return next(s for s in range(100) if (random.Random(s).random() < 0.5) == heads)


def set_trap(fight, key="p1"):
    """M-CUTIE (`key`) sets a trap and is stepped until it is armed; returns it."""
    other = "p2" if key == "p1" else "p1"
    step(fight, **{key: DOWN_X, other: IDLE})
    for _ in range(TRAP.startup + TRAP_ARM + 2):
        step(fight, **{key: FighterInput(down=True), other: IDLE})
    (trap,) = fight.traps
    assert trap.armed
    return trap


# --- AMPLITUDE AMPLIFICATION: the charge --------------------------------------------------------


def test_x_starts_a_charge_of_one_step_and_she_stands_still():
    fight = versus(M_CUTIE, ROBERT, 300)
    me = fight.fighters["p1"]
    events = step(fight, X)
    x0 = me.x
    for _ in range(5):
        events += step(fight, FighterInput(dx=1, up=True))   # no walking, no jumping
    assert me.action == "charging" and me.charge == 1 and "charge1" in kinds(events)
    assert me.x == x0 and me.y == 0 and fight.shots == []


def test_each_press_is_a_step_and_the_sixth_fires_at_once():
    fight = versus(M_CUTIE, ROBERT, 400)
    me = fight.fighters["p1"]
    events = []
    for n in range(1, CHARGE_CAP):
        events += step(fight, X)
        events += step(fight)
        assert me.action == "charging" and me.charge == n
    events += step(fight, X)                               # the sixth: no waiting
    assert me.action == "attack" and me.move is AMP_WAVES[-1] and me.charge == 0
    assert [k for k in kinds(events) if k.startswith("charge")] == [f"charge{n}" for n in range(1, 7)]


def test_the_wave_leaves_when_15_frames_pass_without_a_press():
    fight = versus(M_CUTIE, ROBERT, 400)
    me = fight.fighters["p1"]
    step(fight, X)
    for _ in range(10):
        step(fight)
    step(fight, X)                                         # a second step resets the wait
    for _ in range(CHARGE_WAIT - 1):
        step(fight)
    assert me.action == "charging" and me.charge == 2
    step(fight)                                            # the 15th frame without one: it fires
    assert me.action == "attack" and me.move is AMP_WAVES[1]
    for _ in range(FIRE):
        step(fight)
    (shot,) = fight.shots
    assert shot.move is AMP_WAVES[1]


@pytest.mark.parametrize("steps", range(1, 7))
def test_every_step_makes_the_wave_taller_and_harder(steps):
    height, damage = AMP_STEPS[steps - 1]
    fight = versus(M_CUTIE, ROBERT, 300)
    rival = fight.fighters["p2"]
    mash(fight, steps)
    (shot,) = fight.shots
    assert shot.move.projectile.box.h == height and shot.move.damage == damage
    events = []
    for _ in range(120):
        events += step(fight)
    assert kinds(hits_on(events, "p2")) == ["hit"] and rival.health == ROBERT.health - damage


def test_the_table_grows_every_step():
    heights, damages = zip(*AMP_STEPS)
    assert heights == (20, 28, 36, 44, 52, 60) and damages == (7, 8, 10, 11, 13, 15)
    assert [w.projectile.box.h for w in AMP_WAVES] == list(heights)
    assert [w.damage for w in AMP_WAVES] == list(damages)


def test_a_hit_while_charging_loses_the_charge():
    fight = versus(M_CUTIE, ROBERT, 50)
    me = fight.fighters["p1"]
    step(fight, X)
    step(fight, X)
    events = []
    for i in range(40):
        events += step(fight, FighterInput(x=i < 6 and i % 3 == 0), FighterInput(a=i == 0))
    assert kinds(hits_on(events, "p1"))[0] == "hit" and me.charge == 0
    assert not fight.shots and me.cooldowns.get("stand.X", 0) == 0     # it never fired


def test_the_cooldown_runs_from_the_fire():
    fight = versus(M_CUTIE, ROBERT, 400)
    me = fight.fighters["p1"]
    step(fight, X)
    for _ in range(CHARGE_WAIT - 1):
        step(fight)
        assert me.cooldowns.get("stand.X", 0) == 0
    step(fight)
    assert me.cooldowns["stand.X"] == AMP.cooldown == 120


def test_the_wave_runs_along_the_floor_a_little_slower_than_a_photon():
    fight = versus(M_CUTIE, ROBERT, 400)
    me = fight.fighters["p1"]
    mash(fight, 3)
    (shot,) = fight.shots
    assert shot.y == 0 and shot.vx == 3.5 == AMP.projectile.speed < PHOTON.projectile.speed
    assert shot.facing == me.facing


def test_its_colour_is_fixed_when_it_fires():
    fight = versus(M_CUTIE, ROBERT, 400)
    me = fight.fighters["p1"]
    step(fight, X)
    step(fight, FighterInput(y=True))          # purple while charging: the wave fires purple
    for _ in range(CHARGE_WAIT + FIRE + 2):
        step(fight)
    (shot,) = fight.shots
    assert me.basis == X_BASIS and shot.basis == X_BASIS
    step(fight, FighterInput(y=True))          # a switch after it fired changes nothing
    assert shot.basis == X_BASIS


def test_a_crouch_never_ducks_it():
    fight = versus(M_CUTIE, ROBERT, 160)
    mash(fight, 1)
    events = []
    for _ in range(60):
        events += step(fight, IDLE, FighterInput(down=True))
    assert kinds(hits_on(events, "p2")) == ["hit"]


@pytest.mark.parametrize("steps,hit", [(1, False), (6, True)])
def test_a_rival_30_px_up_clears_a_small_wave_but_not_a_big_one(steps, hit):
    fight = versus(M_CUTIE, ROBERT, 300)
    rival = fight.fighters["p2"]
    rival.y, rival.action = 30.0, "jump"        # rising off the floor, 30 px up
    wave = AMP_WAVES[steps - 1]
    fight.shots.append(Shot("p1", wave, rival.x - 40, 0.0, wave.projectile.speed, 60))
    events = []
    for _ in range(5):
        events += step(fight)
    assert bool(hits_on(events, "p2")) == hit


@pytest.mark.parametrize("move,y,vy", [(PHOTON, 0.0, 0.0), (FLOPPY, 0.0, 0.0), (LASER, 60.0, -14.0)])
def test_her_smallest_wave_cancels_a_rival_shot_passing_over_it(move, y, vy):
    fight = versus(M_CUTIE, DOS, 400)
    mash(fight, 1)
    (wave,) = fight.shots
    fight.shots.append(Shot("p2", move, wave.x + 30, y, -abs(move.projectile.speed), 60, "Z", vy))
    for _ in range(10):
        step(fight)
    assert fight.shots == []


def test_dos_copies_her_wave_and_pastes_it_along_the_floor_at_its_size():
    fight = versus(M_CUTIE, DOS, 200)
    cutie, dos = fight.fighters["p1"], fight.fighters["p2"]
    mash(fight, 4)
    events = []
    for _ in range(80):
        if dos.clipboard is not None:
            break
        near = fight.shots and abs(fight.shots[0].x - dos.x) < 60
        events += step(fight, IDLE, FighterInput(y=bool(near) and dos.action != "attack"))
    assert dos.clipboard == (AMP_WAVES[3], Z_BASIS) and "copy" in kinds(events)
    for _ in range(30):
        step(fight)
    step(fight, IDLE, FighterInput(y=True))     # PASTE
    for _ in range(10):
        step(fight)
    (shot,) = fight.shots
    assert shot.owner == "p2" and shot.move is AMP_WAVES[3] and shot.y == 0 and shot.vx < 0
    assert cutie.health == M_CUTIE.health


def test_copy_catches_even_the_smallest_wave():
    assert COPY.catch.y < AMP_STEPS[0][0] and COPY.catch.y >= MOUSE.projectile.box.y + MOUSE.projectile.box.h
    fight = versus(DOS, M_CUTIE, 300)
    dos = fight.fighters["p1"]
    wave = AMP_WAVES[0]
    fight.shots.append(Shot("p2", wave, dos.x + 60, 0.0, -wave.projectile.speed, 100))
    for i in range(20):
        step(fight, FighterInput(y=i == 0))
    assert dos.clipboard == (wave, Z_BASIS)


# --- ION TRAP -----------------------------------------------------------------------------------


def test_down_x_sets_a_trap_70_px_in_front_in_her_colour():
    fight = versus(M_CUTIE, ROBERT, 300)
    me = fight.fighters["p1"]
    me.basis = X_BASIS
    events = step(fight, DOWN_X)
    for _ in range(TRAP.startup):
        events += step(fight, FighterInput(down=True))
    (trap,) = fight.traps
    assert (trap.owner, trap.x, trap.basis, trap.state) == ("p1", me.x + TRAP_REACH, X_BASIS, "arming")
    assert "trap_set" in kinds(events) and TRAP.cooldown == 60 and me.cooldowns["crouch.X"] > 0


def test_it_arms_18_frames_after_it_is_set_and_cannot_catch_before():
    fight = versus(M_CUTIE, ROBERT, 300)
    rival = fight.fighters["p2"]
    step(fight, DOWN_X)
    for _ in range(TRAP.startup - 1):
        step(fight, FighterInput(down=True))
    rival.x = fight.fighters["p1"].x + TRAP_REACH       # standing right where it lands
    step(fight, FighterInput(down=True))                # set (and arming) on this frame
    (trap,) = fight.traps
    events = []
    for _ in range(TRAP_ARM - 1):
        assert trap.state == "arming"
        events += step(fight)
    assert hits_on(events, "p2") == [] and trap.armed
    events = step(fight)
    assert kinds(hits_on(events, "p2")) == ["hit"] and trap.state == "closed"


def test_it_closes_on_a_rival_who_walks_in_and_holds_them():
    fight = versus(M_CUTIE, ROBERT, 300)
    rival = fight.fighters["p2"]
    trap = set_trap(fight)
    events = []
    for _ in range(150):
        ev = step(fight, IDLE, FighterInput(dx=-1))
        events += ev
        if "trap_close" in kinds(ev):
            break
    held_at = rival.x
    assert kinds(hits_on(events, "p2")) == ["hit"] and rival.health == ROBERT.health - TRAP_HOLD.damage
    assert rival.action == "hitstun" and rival.stun == TRAP_HOLD.hitstun == 30 and rival.vx == 0
    for _ in range(25):
        step(fight, IDLE, FighterInput(dx=-1))
    assert rival.x == held_at and trap.held == "p2" and trap.state == "closed"


def test_a_trap_of_the_other_colour_holds_but_does_not_hurt():
    fight = versus(M_CUTIE, ROBERT, 300)
    rival = fight.fighters["p2"]
    rival.basis = X_BASIS
    set_trap(fight)
    events = []
    for _ in range(150):
        events += step(fight, IDLE, FighterInput(dx=-1))
    assert kinds(hits_on(events, "p2")) == ["block"] and rival.health == ROBERT.health
    assert "trap_close" in kinds(events)


def test_a_jump_clears_it():
    fight = versus(M_CUTIE, ROBERT, 140)
    trap = set_trap(fight)
    rival = fight.fighters["p2"]
    events = []
    for i in range(40):
        events += step(fight, IDLE, FighterInput(up=i == 0, dx=-1 if i == 0 else 0))
        if rival.y == 0 and i:
            break
    assert hits_on(events, "p2") == [] and trap.armed and rival.x < trap.x   # over it


def test_a_trap_is_used_up_and_never_catches_her():
    fight = versus(M_CUTIE, ROBERT, 300)
    me, rival = fight.fighters["p1"], fight.fighters["p2"]
    trap = set_trap(fight)
    me.x = trap.x                               # her own trap: nothing
    for _ in range(5):
        step(fight)
    assert trap.armed and me.action != "hitstun"
    me.x = 220
    rival.x = trap.x
    step(fight)
    assert trap.state == "closed"
    for _ in range(TRAP_HOLD.hitstun + 5):
        step(fight)
    assert fight.traps == []


def test_a_third_trap_replaces_the_oldest():
    fight = versus(M_CUTIE, ROBERT, 400)
    me = fight.fighters["p1"]
    xs = []
    for k in range(3):
        me.x = 100.0 + 60 * k
        step(fight, DOWN_X)
        for _ in range(TRAP.cooldown + 2):
            step(fight)
        xs.append(me.x + TRAP_REACH)
    assert TRAP_MAX == 2 and [t.x for t in fight.traps] == xs[1:]


def test_traps_go_after_10_s():
    fight = versus(M_CUTIE, ROBERT, 400)
    trap = set_trap(fight)
    while trap.age < TRAP_LIFE - 1:
        step(fight)
    assert fight.traps == [trap]
    step(fight)
    assert fight.traps == []


def test_her_traps_go_when_she_is_knocked_down():
    fight = versus(M_CUTIE, ROBERT, 300)
    me, rival = fight.fighters["p1"], fight.fighters["p2"]
    set_trap(fight)
    rival.x = me.x - 46                         # behind her, clear of the trap
    for i in range(10):
        step(fight, IDLE, FighterInput(dx=1, b=True) if i == 0 else IDLE)      # a throw
    assert me.action == "knockdown" and fight.traps == []


def test_a_trap_under_a_superposed_erwin_closes_on_a_box_and_measures_him():
    for heads in (True, False):
        fight = versus(M_CUTIE, ERWIN, 200, seed=heads_seed(heads))
        erwin = fight.fighters["p2"]
        trap = set_trap(fight)
        erwin.x = 520.0                          # both boxes clear of the trap
        step(fight, IDLE, X)
        for _ in range(ERWIN.moves["stand.X"].startup):
            step(fight)
        assert erwin.boxed
        erwin.boxes = (trap.x, trap.x + 120)    # then box 1 right on it
        events = step(fight)
        assert "box_collapse" in kinds(events) and "trap_close" in kinds(events)
        assert not erwin.boxed and trap.state == "closed"
        if heads:       # he was in that box: held, and hurt (both green)
            assert erwin.x == trap.x and erwin.action == "hitstun" and trap.held == "p2"
            assert erwin.health == ERWIN.health - TRAP_HOLD.damage
        else:           # in the other one: the trap closed on nothing
            assert erwin.x == trap.x + 120 and trap.held is None and erwin.health == ERWIN.health


def test_a_tunnelling_phoebe_has_no_body_and_the_trap_stays_armed():
    fight = versus(M_CUTIE, PHOEBE, 300)
    phoebe = fight.fighters["p2"]
    trap = set_trap(fight)
    step(fight, IDLE, DOWN_X)                   # TUNNEL
    while not phoebe.intangible:
        step(fight, IDLE, FighterInput(down=True))
    phoebe.x = trap.x                           # gone, right over the trap
    for _ in range(4):
        step(fight, IDLE, FighterInput(down=True))
        phoebe.x = trap.x
    assert phoebe.intangible and trap.armed and phoebe.health == PHOEBE.health


def test_a_rival_knocked_into_a_trap_is_caught_once_they_come_to_rest():
    fight = versus(M_CUTIE, ROBERT, 300)
    rival = fight.fighters["p2"]
    trap = set_trap(fight)
    rival.x = trap.x
    rival.action, rival.stun = "hitstun", 12    # reeling across it: not yet
    events = []
    for _ in range(11):
        events += step(fight)
    assert hits_on(events, "p2") == [] and trap.armed
    for _ in range(3):
        events += step(fight)
    assert kinds(hits_on(events, "p2")) == ["hit"] and trap.held == "p2"


def test_dos_pulling_her_across_her_own_trap_never_springs_it():
    fight = versus(M_CUTIE, DOS, 160)
    me, dos = fight.fighters["p1"], fight.fighters["p2"]
    trap = set_trap(fight)
    me.x, dos.x = 180.0, 350.0                  # the trap (at 290) between them
    step(fight, IDLE, DOWN_X)                   # MOUSE CABLE
    for _ in range(60):
        step(fight, IDLE, FighterInput(down=True))
    assert me.x > trap.x and trap.armed         # dragged right across it: her own
    assert trap is fight.traps[0]


def test_measure_collapses_her_colour_as_anyones():
    fight = versus(BOHR, M_CUTIE, 80)
    bohr, cutie = fight.fighters["p1"], fight.fighters["p2"]
    bohr.basis = X_BASIS
    events = []
    for i in range(70):
        events += step(fight, FighterInput(x=i == 0))
    assert [(e.kind, e.error) for e in hits_on(events, "p2")] == [("hit", basis.Y)]
    assert cutie.basis == X_BASIS and "measure" in kinds(events)


def test_a_trap_is_its_own_object_in_the_fight():
    t = Trap("p1", TRAP_HOLD, 300.0, Z_BASIS)
    assert t.state == "arming" and not t.armed
    t.age = TRAP_ARM
    assert t.state == "armed" and t.box == (282.0, 274.0, 36, 26)


# --- SPIN ---------------------------------------------------------------------------------------


def spin_fight(gap=400):
    """M-CUTIE (p1) jumps and spins 8 frames after take-off."""
    fight = versus(M_CUTIE, ROBERT, gap)
    me = fight.fighters["p1"]
    events = step(fight, UP)
    for _ in range(7):
        events += step(fight)
    return fight, me, events + step(fight, X)


def test_spin_hangs_at_her_height_and_spins_96_px_forward():
    fight, me, _ = spin_fight()
    x0, y0 = me.x, me.y
    for _ in range(SPIN.startup + SPIN.active - 1):
        step(fight)
        assert me.y == y0                       # no falling, from the press to its last active frame
    assert me.phase == "active" and me.x - x0 == pytest.approx(SPIN.lunge * SPIN.active) == 96


def test_spin_hits_at_most_three_times():
    fight = versus(M_CUTIE, ROBERT, 60)
    rival = fight.fighters["p2"]
    events = step(fight, UP)
    for _ in range(3):
        events += step(fight)
    events += step(fight, X)
    for _ in range(60):
        events += step(fight)
    hits = kinds(hits_on(events, "p2"))
    assert hits == ["hit"] * 3 and rival.health == ROBERT.health - 3 * SPIN.damage
    assert SPIN.height == 1 and -(-SPIN.active // SPIN.hit_every) == 3


def test_spin_once_per_jump():
    fight, me, _ = spin_fight()
    for _ in range(SPIN.startup + SPIN.active + 2):
        step(fight)
    assert me.y > 0 and "air.X" in me.air_used
    events = step(fight, X)                     # again, in the same jump: nothing
    assert "attack" not in kinds(events) and me.phase == "recovery"
    while me.action != "idle":
        step(fight)
    assert "air.X" not in me.air_used           # landed: the next jump has its own


def test_a_missed_spin_drops_and_lands_into_its_recovery():
    fight, me, _ = spin_fight()
    for _ in range(SPIN.startup + SPIN.active):
        step(fight)
    x_end = me.x
    while me.y > 0:
        step(fight)
        assert me.move is SPIN and me.phase == "recovery"
    assert me.x == x_end                        # straight down
    for _ in range(SPIN.recovery - 1):
        step(fight)
        assert me.move is SPIN and me.vx == 0
    step(fight)
    assert me.move is None and me.action == "idle"


def test_the_stage_edge_stops_her_trap():
    fight = versus(M_CUTIE, ROBERT, 30)
    me = fight.fighters["p1"]
    me.x, fight.fighters["p2"].x = STAGE_RIGHT - 30.0, STAGE_RIGHT - 80.0
    step(fight, DOWN_X)
    for _ in range(TRAP.startup):
        step(fight, FighterInput(down=True))
    assert fight.traps[0].x == STAGE_RIGHT - 30.0 - TRAP_REACH


def test_a_rival_let_go_of_a_hold_has_a_grace_before_the_next_trap_catches_them():
    fight = versus(M_CUTIE, ROBERT, 300)
    rival = fight.fighters["p2"]
    first = set_trap(fight)
    fight.traps.append(Trap("p1", TRAP_HOLD, first.x, first.basis, age=TRAP_ARM))   # a second, stacked and armed
    second = fight.traps[1]
    rival.x = first.x
    caught = []
    for _ in range(TRAP_HOLD.hitstun + TRAP_GRACE + 30):
        ev = step(fight)
        if "trap_close" in kinds(ev):
            caught.append(fight.frames_left)
    assert len(caught) == 2 and caught[0] - caught[1] >= TRAP_HOLD.hitstun + TRAP_GRACE
    assert second.state == "closed"


def test_the_grace_ends_with_the_hold_plus_0_3_s_and_lets_them_walk_out():
    fight = versus(M_CUTIE, ROBERT, 300)
    rival = fight.fighters["p2"]
    first = set_trap(fight)
    fight.traps.append(Trap("p1", TRAP_HOLD, first.x, first.basis, age=TRAP_ARM))
    rival.x = first.x
    while first in fight.traps:
        step(fight)
    assert rival.action in ("hitstun", "idle")
    for _ in range(TRAP_GRACE - 2):
        events = step(fight, IDLE, FighterInput(dx=1))
        assert "trap_close" not in kinds(events)
    assert fight.traps[0].armed and fight.traps[0].held is None and rival.x > first.x
