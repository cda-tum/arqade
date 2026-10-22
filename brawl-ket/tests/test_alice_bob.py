"""ALICE & BOB (docs/superpowers/specs/2026-10-21-brawl-ket-alice-bob-design.md, sections 2, 6, 7
and 8): two small fighters played as one. Bob replays Alice's inputs 12 frames later, 40 px
behind her, with his own hurtbox and hitboxes; the pair shares one health bar and one colour; a
knockdown decoheres Bob for 3 s; the round ends when the bar is empty."""

import pytest

from brawl_ket import basis
from brawl_ket.basis import X_BASIS, Z_BASIS
from brawl_ket.config import (
    DECOHERE_FRAMES,
    ECHO_DELAY,
    ECHO_GAP,
    FLOOR_Y,
    SWITCH_RECOVERY,
)
from brawl_ket.echo import Echo
from brawl_ket.fight import Fight
from brawl_ket.fighter import IDLE, FighterInput
from brawl_ket.moves import ALICE_BOB, BOB, BOHR, KID_NORMALS, MID, NORMALS, ROBERT

A = FighterInput(a=True)
B = FighterInput(b=True)
Y = FighterInput(y=True)
RIGHT = FighterInput(dx=1)
SWEEP = FighterInput(down=True, b=True)


def pair_fight(rival=ROBERT, alice_x=300.0, rival_x=420.0, seed=0):
    """ALICE & BOB (p1, facing right) against `rival` (p2); Bob on his spot behind Alice."""
    fight = Fight({"p1": ALICE_BOB, "p2": rival}, seed=seed)
    alice, bob, other = fight.fighters["p1"], fight.echoes["p1"], fight.fighters["p2"]
    alice.x, other.x = alice_x, rival_x
    bob.x = bob.spot
    return fight, alice, bob, other


def bob_caught(fight, alice, bob, other, at=232.0):
    """The rival 100 px to Alice's left and Bob on his way round her (his spot is on her right),
    between them: the one place the rival can reach him and not her. Alice faces left."""
    alice.x, other.x, bob.x = 300.0, 200.0, at
    alice.facing = bob.facing = -1


def run(fight, n, p1=IDLE, p2=IDLE):
    events = []
    for i in range(n):
        events += fight.step({"p1": p1(i) if callable(p1) else p1, "p2": p2(i) if callable(p2) else p2})
    return events


def once(inp):
    return lambda i: inp if i == 0 else IDLE


# --- the data ---------------------------------------------------------------------------------


def test_the_pair_is_two_kids_with_one_bar():
    assert ALICE_BOB.name == "ALICE & BOB" and ALICE_BOB.pair is BOB and BOB.pair is None
    assert (ALICE_BOB.build, BOB.build) == ("alice", "bob")
    assert ALICE_BOB.health == BOB.health == 100
    for c in (ALICE_BOB, BOB):          # a little faster and lighter than ROBERT: a quicker, smaller hop
        assert c.walk > ROBERT.walk and c.jump_vy < ROBERT.jump_vy and c.gravity == ROBERT.gravity
        assert c.hurt_stand.h < ROBERT.hurt_stand.h and c.hurt_crouch.h < ROBERT.hurt_crouch.h
    assert BOB.hurt_stand.h > ALICE_BOB.hurt_stand.h     # his face shows over her head


def test_their_normals_are_the_shared_ones_fitted_to_their_size():
    assert set(KID_NORMALS) == set(NORMALS)
    for slot in NORMALS:
        ours, roberts = KID_NORMALS[slot], ROBERT.moves[slot]
        assert ours.name == roberts.name and ours.hitbox != roberts.hitbox
        assert (ours.startup, ours.active, ours.recovery, ours.damage, ours.colour, ours.height) == \
            (roberts.startup, roberts.active, roberts.recovery, roberts.damage, roberts.colour, roberts.height)
    assert all(BOB.moves[slot] is ALICE_BOB.moves[slot] for slot in NORMALS)


def test_about_0_78_of_roberts_height():
    from brawl_ket.poses import HEAD_R, POSES, joints
    feet = (300.0, float(FLOOR_Y))

    def top(build):
        return FLOOR_Y - joints(POSES["idle"], build, feet, 1)["head"][1] + HEAD_R[build] + 2

    for build in ("alice", "bob"):
        assert 0.74 <= top(build) / top("lean") <= 0.82, build
    assert top("bob") > top("alice") + 4


# --- the second body -----------------------------------------------------------------------------


def test_a_pair_gets_a_second_body_and_nobody_else_does():
    fight = Fight({"p1": ALICE_BOB, "p2": ROBERT})
    assert set(fight.echoes) == {"p1"} and isinstance(fight.echoes["p1"], Echo)
    bob = fight.echoes["p1"]
    assert bob.char is BOB and bob.lead is fight.fighters["p1"]
    assert bob.x == fight.fighters["p1"].x - ECHO_GAP and bob.facing == 1
    assert fight.bodies("p1") == [fight.fighters["p1"], bob] and fight.bodies("p2") == [fight.fighters["p2"]]
    assert Fight({"p1": ROBERT, "p2": BOHR}).echoes == {}
    p2 = Fight({"p1": ROBERT, "p2": ALICE_BOB}).echoes["p2"]
    assert p2.facing == -1 and p2.x == p2.lead.x + ECHO_GAP


def test_bob_replays_alices_inputs_exactly_12_frames_later():
    fight, alice, bob, _ = pair_fight()
    pressed = [FighterInput(dx=(i // 7) % 3 - 1, a=i % 9 == 0, down=i % 11 < 3) for i in range(60)]
    seen = []
    real = bob.step
    bob.step = lambda inp, rival_x: (seen.append(inp), real(inp, rival_x))[1]
    run(fight, 60, lambda i: pressed[i])
    assert ECHO_DELAY == 12
    assert seen == [IDLE] * 12 + pressed[:48]


def test_every_attack_comes_twice_the_second_a_beat_late():
    fight, alice, bob, _ = pair_fight()
    starts = {}
    for i in range(30):
        fight.step({"p1": A if i == 0 else IDLE})
        for name, f in (("alice", alice), ("bob", bob)):
            if f.action == "attack" and f.frame == 0:
                starts[name] = i
    assert starts == {"alice": 0, "bob": 12}
    assert bob.move is None and bob.slot is None


def test_he_follows_40_px_behind_her():
    fight, alice, bob, _ = pair_fight(alice_x=200.0, rival_x=600.0)
    run(fight, 50, RIGHT)
    assert alice.x - bob.x > ECHO_GAP        # he set off 12 frames after her
    run(fight, 30)
    assert alice.x - bob.x == pytest.approx(ECHO_GAP)


def test_he_never_walks_into_her_when_she_is_held_up():
    """Walking into the rival, Alice stops at the push box; Bob's echo of her walk stops on his spot."""
    fight, alice, bob, other = pair_fight(alice_x=300.0, rival_x=360.0)
    for _ in range(90):
        fight.step({"p1": RIGHT})
        assert alice.x - bob.x >= ECHO_GAP - ALICE_BOB.walk     # (the push box nudges her back a step)
    assert other.x - alice.x == pytest.approx(fight.body_width)


def test_pushed_off_his_spot_he_walks_back_to_it():
    fight, alice, bob, _ = pair_fight()
    bob.x -= 30
    run(fight, 20)
    assert bob.x == pytest.approx(bob.spot)
    assert bob.facing == alice.facing


def test_his_facing_follows_hers_even_with_the_rival_between_them():
    fight, alice, bob, other = pair_fight(alice_x=300.0, rival_x=280.0)
    bob.x = 260.0                       # the rival stands between them
    run(fight, 2)
    assert alice.facing == -1 and bob.facing == -1


def test_bob_has_no_push_box():
    fight, alice, bob, other = pair_fight(alice_x=300.0, rival_x=250.0)
    bob.x = 250.0
    run(fight, 1)
    assert other.x == 250.0 and abs(other.x - bob.x) < 5     # the rival stands in Bob: nothing pushes
    other.x = 280.0
    run(fight, 1)
    assert abs(other.x - alice.x) == pytest.approx(fight.body_width)    # ... but Alice does


def test_the_echo_runs_on_through_a_hitstop_freeze():
    """A jab that connects freezes the fight; Bob's echo of it still starts 12 fight frames after hers."""
    fight, alice, bob, other = pair_fight(alice_x=300.0, rival_x=345.0)
    start = None
    for i in range(40):
        fight.step({"p1": A if i == 0 else IDLE})
        if start is None and bob.action == "attack":
            start = i
    assert start == ECHO_DELAY


# --- what the pair shares --------------------------------------------------------------------------


def test_y_switches_both_at_once_and_bob_only_echoes_its_lock():
    fight, alice, bob, _ = pair_fight()
    fight.step({"p1": Y})
    assert alice.basis == bob.basis == X_BASIS
    for i in range(1, 30):
        fight.step({"p1": IDLE})
        assert alice.basis == bob.basis == X_BASIS, i          # his replay of the Y never switches back
        if i == ECHO_DELAY:
            assert bob.switch_lock == SWITCH_RECOVERY          # ... it only locks his attacks, as hers were


def test_one_health_bar():
    fight, alice, bob, other = pair_fight()
    bob_caught(fight, alice, bob, other)        # ROBERT jabs Bob (the pair is green, so is ROBERT)
    events = run(fight, 12, p2=once(A))
    hits = [e for e in events if e.kind == "hit" and e.player == "p1"]
    assert len(hits) == 1 and alice.health == bob.health == 100 - ROBERT.moves["stand.A"].damage
    assert bob.action == "hitstun" and alice.action == "idle"


def test_a_colour_change_on_either_collapses_both():
    fight, alice, bob, _ = pair_fight()
    assert bob.measured_into(X_BASIS) and alice.basis == X_BASIS
    alice.switch()
    assert bob.basis == Z_BASIS


# --- decoherence ------------------------------------------------------------------------------------


def sweep_bob(fight, bob, other):
    """ROBERT sweeps Bob (bob_caught): a knockdown. (A sweep is the other colour: ROBERT purple
    sweeps green.)"""
    bob_caught(fight, fight.fighters["p1"], bob, other)
    other.basis = X_BASIS
    return run(fight, 20, p2=lambda i: SWEEP if i == 0 else FighterInput(down=True))


def test_a_knockdown_on_bob_decoheres_him_for_3_s():
    fight, alice, bob, other = pair_fight()
    events = sweep_bob(fight, bob, other)
    assert [e.kind for e in events if e.player == "p1" and e.kind in ("hit", "decohere")] == ["hit", "decohere"]
    assert not bob.here and bob.action == "decohered" and fight.bodies("p1") == [alice]
    assert alice.health == 100 - ROBERT.moves["crouch.B"].damage
    run(fight, 2)                       # out of the knockdown's hitstop freeze
    gone = bob.decohered
    alice.x = 400.0
    events = run(fight, DECOHERE_FRAMES - gone - 1)
    assert not bob.here
    events = run(fight, 1)
    assert [e.kind for e in events if e.player == "p1"] == ["recohere"]
    assert bob.here and bob.x == alice.x - alice.facing * ECHO_GAP and bob.action == "idle"
    assert bob.facing == alice.facing == -1 and bob.reform > 0


def test_while_bob_is_gone_nothing_touches_him_and_alice_fights_alone():
    fight, alice, bob, other = pair_fight()
    sweep_bob(fight, bob, other)
    seen = []
    real = bob.step
    bob.step = lambda inp, rival_x: (seen.append(inp), real(inp, rival_x))[1]
    run(fight, 30, lambda i: A if i == 0 else IDLE)
    assert bob.move is None and bob.action == "decohered"
    assert alice.slot is None and any(s.a for s in seen)       # the queue runs on, but he does nothing


def test_he_comes_back_with_nothing_of_hers_still_to_replay():
    fight, alice, bob, other = pair_fight()
    sweep_bob(fight, bob, other)
    run(fight, 2)
    run(fight, DECOHERE_FRAMES - bob.decohered - 3)
    run(fight, 3, A)                                # Alice jabs as he comes back
    run(fight, ECHO_DELAY - 1)
    assert bob.here and bob.action != "attack"


# --- the round ----------------------------------------------------------------------------------------


def test_the_round_ends_when_the_shared_bar_is_empty_wherever_bob_is():
    fight, alice, bob, other = pair_fight()
    alice.health = 4
    bob_caught(fight, alice, bob, other)
    events = run(fight, 12, p2=once(A))             # a jab on Bob empties the bar
    assert fight.over and fight.winner == "p2" and "ko" in [e.kind for e in events]
    assert alice.action == "knockdown" and bob.action == "knockdown"


def test_bob_hits_with_his_own_hitbox():
    """With the rival standing in Bob's reach and out of Alice's, only Bob's echo connects."""
    fight, alice, bob, other = pair_fight()
    bob_caught(fight, alice, bob, other)    # Bob 40 px in front of the rival, both kids facing left
    events = run(fight, 20, once(A))
    hits = [e for e in events if e.kind == "hit" and e.player == "p2"]
    assert len(hits) == 1 and other.health == ROBERT.health - KID_NORMALS["stand.A"].damage


def test_a_decohered_bob_is_drawn_standing():
    """The look: he decoheres standing, not lying on the floor (rejected: it didn't read)."""
    from brawl_ket.poses import POSES, pose_for
    fight, alice, bob, other = pair_fight()
    sweep_bob(fight, bob, other)
    assert bob.action == "decohered" and bob.y == 0
    assert pose_for(bob).lean == pytest.approx(POSES["idle"].lean, abs=1)


# --- every interaction with a pair (spec section 7) -----------------------------------------------


def test_a_throw_on_bob_costs_the_bar_and_decoheres_him():
    fight, alice, bob, other = pair_fight()
    bob_caught(fight, alice, bob, other)      # Bob in a throw's reach (Alice is far out of it)
    assert fight._reach("p1") == (alice.x, bob.x)
    events = run(fight, 15, p2=lambda i: FighterInput(dx=1, b=i == 0) if i < 2 else IDLE)
    hits = [e for e in events if e.kind == "hit" and e.player == "p1"]
    assert hits and hits[0].error == basis.Y and not bob.here
    assert alice.health == 100 - ROBERT.moves["throw"].damage


def test_bohrs_measure_on_bob_collapses_both():
    fight, alice, bob, other = pair_fight(rival=BOHR)
    bob_caught(fight, alice, bob, other)
    other.basis = X_BASIS                       # BOHR purple, the pair green
    events = run(fight, 40, p2=once(FighterInput(x=True)))
    assert [e.kind for e in events if e.player == "p1" and e.kind in ("hit", "measure")] == ["hit", "measure"]
    assert alice.basis == bob.basis == X_BASIS and not bob.here


def test_charge_noise_hits_each_body_inside_it():
    fight, alice, bob, other = pair_fight(rival=BOHR)
    alice.x, bob.x, other.x = 300.0, 232.0, 262.0   # BOHR between them, both kids in his field
    alice.facing = bob.facing = -1
    first = []
    for i in range(30):
        events = fight.step({"p1": FighterInput(down=True), "p2": FighterInput(down=True, x=i == 0)})
        first = [e for e in events if e.kind == "hit" and e.player == "p1"]
        if first:
            break
    assert len(first) == 2                       # one shock, two targets ...
    assert alice.health == 100 - 2 * BOHR.moves["crouch.X"].damage     # ... both on the one bar


def test_an_ion_trap_under_bob_catches_him_and_leaves_alice_free():
    from brawl_ket.config import TRAP_ARM, TRAP_GRACE
    from brawl_ket.fight import Trap
    from brawl_ket.moves import M_CUTIE, TRAP_HOLD
    fight, alice, bob, other = pair_fight(rival=M_CUTIE, rival_x=500.0)
    trap = Trap("p2", TRAP_HOLD, bob.x, Z_BASIS, age=TRAP_ARM)
    fight.traps.append(trap)
    events = run(fight, 1, FighterInput(down=True))
    assert trap.state == "closed" and trap.held == "p1" and trap.body is bob
    assert bob.action == "hitstun" and alice.action == "crouch"
    assert [e.kind for e in events if e.kind == "trap_close"] == ["trap_close"]
    graced = set()
    for _ in range(TRAP_HOLD.hitstun + 20):         # (the hit's hitstop freeze included)
        run(fight, 1, FighterInput(down=True))
        graced |= set(fight.trap_grace)
    assert graced == {bob} and TRAP_GRACE > 0         # the moment to get away is Bob's, not Alice's


def test_the_mouse_cable_reels_in_whichever_body_it_hooks():
    from brawl_ket.moves import DOS
    fight, alice, bob, other = pair_fight(rival=DOS)
    bob_caught(fight, alice, bob, other)
    other.x = 120.0                             # the mouse reels its catch in to just in front of DOS
    start = bob.x
    events = run(fight, 30, FighterInput(down=True), once(FighterInput(down=True, x=True)))
    assert [e.player for e in events if e.kind == "hit"] == ["p1"]
    assert bob.x < start - 30 and alice.x == 300.0      # Bob reeled in towards DOS; Alice untouched


def test_bobs_attack_measures_the_box_as_any_attack():
    from brawl_ket.moves import ERWIN
    fight, alice, bob, other = pair_fight(rival=ERWIN)
    bob_caught(fight, alice, bob, other)
    run(fight, 1, A)                            # Bob's echo of this jab comes 12 frames on ...
    other.action, other.boxes, other.box_t = "boxed", (200.0, 80.0), 0     # ... into box 1
    events = run(fight, 20)
    assert [e.kind for e in events if e.kind == "box_collapse"] == ["box_collapse"] and not other.boxed


def test_tunnel_re_forms_past_alice_the_pairs_x():
    from brawl_ket.config import TUNNEL_PAST
    from brawl_ket.moves import PHOEBE
    fight, alice, bob, other = pair_fight(rival=PHOEBE, alice_x=300.0, rival_x=420.0)
    run(fight, 1, p2=FighterInput(down=True, x=True))
    assert other.tunnel_to == alice.x - TUNNEL_PAST     # Bob, 40 px behind Alice, is no part of it


def test_a_shot_lands_on_one_body_alice_first():
    fight, alice, bob, other = pair_fight(rival_x=420.0)
    bob.x = alice.x                             # both in the photon's way
    events = run(fight, 60, p2=once(FighterInput(x=True)))
    assert [e.kind for e in events if e.player == "p1" and e.kind == "hit"] == ["hit"]
    assert alice.health == 100 - ROBERT.moves["stand.X"].damage


def pair_script(fight, key):
    """A stand-in for the pair's bot (their own comes with their specials): walk in, jab or sweep
    up close, now and then switch."""
    me, rival = fight.fighters[key], fight.fighters["p2" if key == "p1" else "p1"]
    t = fight.frames_left
    toward = 1 if rival.x > me.x else -1
    if abs(rival.x - me.x) > 50:
        return FighterInput(dx=toward, y=t % 97 == 0)
    return FighterInput(a=t % 20 == 0, b=t % 20 == 10, down=t % 60 < 20)


@pytest.mark.parametrize("name", ["ROBERT", "BOHR", "PHOEBE", "ERWIN", "DOS", "M-CUTIE"])
@pytest.mark.parametrize("side", ["p1", "p2"])
def test_every_bot_plays_a_round_against_a_pair(name, side):
    from brawl_ket.bot import Bot
    from brawl_ket.config import ROUND_FRAMES
    from brawl_ket.moves import CHARACTERS
    pair_key = "p2" if side == "p1" else "p1"
    fight = Fight({side: CHARACTERS[name], pair_key: ALICE_BOB}, seed=3)
    bot = Bot(side, 3)
    for _ in range(ROUND_FRAMES + 10):
        if fight.over:
            break
        fight.step({side: bot.input(fight), pair_key: pair_script(fight, pair_key)})
    assert fight.over


# --- their specials (spec section 3) ---------------------------------------------------------------

X = FighterInput(x=True)
DOWN_X = FighterInput(down=True, x=True)


def test_their_specials():
    from brawl_ket.moves import BELL_DIVE, KEY_SHOT, SOLO_PHOTON
    toss, teleport, dive = (ALICE_BOB.moves[s] for s in ("stand.X", "crouch.X", "air.X"))
    assert (toss.name, teleport.name, dive.name) == ("KEY EXCHANGE", "TELEPORT", "BELL DIVE")
    assert toss.toss is KEY_SHOT and toss.alone is SOLO_PHOTON and toss.cooldown == 150
    assert teleport.swap and teleport.cooldown == 120 and teleport.damage == 0
    assert dive is BELL_DIVE and BOB.moves["air.X"] is BELL_DIVE and dive.once_per_jump
    assert (dive.damage, dive.height, dive.colour) == (8, MID, basis.OWN)
    assert (KEY_SHOT.damage, KEY_SHOT.kind, SOLO_PHOTON.damage, SOLO_PHOTON.kind) == (12, "projectile", 6, "projectile")
    for c in (toss, teleport, dive, KEY_SHOT, SOLO_PHOTON):
        assert c.colour == basis.OWN                        # every special in their own colour
    assert "stand.X" not in BOB.moves and "crouch.X" not in BOB.moves     # Bob echoes neither
    for shot in (KEY_SHOT, SOLO_PHOTON):                    # too slow to fly through anyone
        assert shot.projectile.speed * 2 < shot.projectile.box.w + 16


def key_exchange(rival=ROBERT, rival_x=520.0, frames=60, p1=None, p2=IDLE):
    """Alice presses X once, facing right, the rival far off; returns (fight, events by frame)."""
    fight, alice, bob, other = pair_fight(rival=rival, rival_x=rival_x)
    log = []
    for i in range(frames):
        log.append(fight.step({"p1": (p1(i) if p1 else (X if i == 0 else IDLE)),
                               "p2": p2(i) if callable(p2) else p2}))
    return fight, log


def first(log, kind, player="p1"):
    return next((i for i, events in enumerate(log) for e in events if e.kind == kind and e.player == player), None)


def test_key_exchange_tosses_to_bob_who_fires_one_strong_shot():
    from brawl_ket.config import TOSS_FRAMES
    from brawl_ket.moves import KEY_SHOT
    fight, log = key_exchange(frames=140)
    toss_at, caught_at, fired_at = first(log, "toss"), first(log, "catch"), first(log, "key_shot")
    assert toss_at == ALICE_BOB.moves["stand.X"].startup
    assert caught_at == toss_at + TOSS_FRAMES
    assert fired_at == caught_at + KEY_SHOT.startup
    assert sum(1 for events in log for e in events if e.kind == "projectile") == 1     # Bob doesn't echo it
    hit = first(log, "hit", "p2")
    assert hit is not None and fight.fighters["p2"].health == ROBERT.health - KEY_SHOT.damage


def test_the_toss_flies_from_her_back_hand_to_his_raised_one():
    from brawl_ket.config import TOSS_FRAMES, TOSS_FROM, TOSS_TO
    fight, alice, bob, other = pair_fight(rival_x=520.0)
    seen = []
    for i in range(40):
        fight.step({"p1": X if i == 0 else IDLE})
        seen += [(t.age, t.x, t.y) for t in fight.tosses]
    assert seen[0][1:] == pytest.approx((alice.x + TOSS_FROM[0], TOSS_FROM[1]), abs=8)
    last_age, x, y = seen[-1]
    assert last_age == TOSS_FRAMES - 1
    assert (x, y) == pytest.approx((bob.x + TOSS_TO[0], TOSS_TO[1]), abs=8)
    assert max(y for _a, _x, y in seen) > TOSS_TO[1]               # along an arc, over the line


def test_bobs_shot_keeps_the_colour_it_was_tossed_in():
    fight, log = key_exchange(frames=40, p1=lambda i: X if i == 0 else Y if i == 12 else IDLE)
    alice = fight.fighters["p1"]
    assert alice.basis == X_BASIS
    (shot,) = fight.shots
    assert shot.owner == "p1" and shot.basis == Z_BASIS


def tossed(fight, x, y):
    """A KEY EXCHANGE photon of p1's in flight at (x, height y), half way to Bob. (Each test then
    runs the one check it is about, Fight._intercept or Fight._catch, on it where it is.)"""
    from brawl_ket.config import TOSS_FRAMES
    from brawl_ket.fight import Toss
    from brawl_ket.moves import KEY_SHOT
    t = Toss("p1", KEY_SHOT, Z_BASIS, x, y, age=TOSS_FRAMES // 2, x=x, y=y)
    fight.tosses.append(t)
    return t


def test_a_rival_body_in_its_way_takes_it_out():
    fight, alice, bob, other = pair_fight(rival_x=520.0)
    tossed(fight, other.x, 60.0)
    events = []
    fight._intercept(events)
    assert fight.tosses == [] and [e.kind for e in events] == ["intercept"]
    run(fight, 30)
    assert fight.shots == [] and bob.action != "attack"         # nothing fires


def test_a_rival_shot_takes_it_out_and_is_gone_too():
    from brawl_ket.fight import Shot
    fight, alice, bob, other = pair_fight(rival_x=520.0)
    photon = ROBERT.moves["stand.X"]
    t = tossed(fight, 400.0, 100.0)
    fight.shots.append(Shot("p2", photon, t.x, t.y - 63, 0.0, 30))
    events = []
    fight._intercept(events)
    assert fight.tosses == [] and fight.shots == [] and [e.kind for e in events] == ["intercept"]


def test_an_attack_in_its_way_takes_it_out():
    fight, alice, bob, other = pair_fight(rival_x=520.0)
    other.facing = -1
    run(fight, 5, p2=once(A))                   # ROBERT's jab, live
    assert other.phase == "active"
    left, top, w, h = other.world_box(other.move.hitbox)
    tossed(fight, left + w / 2, FLOOR_Y - (top + h / 2))
    fight._intercept([])
    assert fight.tosses == []


def test_copy_catches_the_toss_in_flight():
    from brawl_ket.moves import DOS, KEY_SHOT
    fight, alice, bob, other = pair_fight(rival=DOS, rival_x=520.0)
    run(fight, 4, p2=once(FighterInput(y=True)))
    assert other.move.catch is not None and other.phase == "active"
    left, top, w, h = other.world_box(other.move.catch)
    tossed(fight, left + w / 2, FLOOR_Y - (top + h / 2))
    events = []
    fight._catch(events)
    assert fight.tosses == [] and other.clipboard == (KEY_SHOT, Z_BASIS)
    assert [e.kind for e in events if e.kind == "copy"] == ["copy"]


def test_copy_catches_bobs_shot():
    from brawl_ket.moves import DOS, KEY_SHOT
    fight, log = key_exchange(rival=DOS, rival_x=420.0, frames=80,
                              p2=lambda i: FighterInput(y=True) if i == 36 else IDLE)
    assert fight.fighters["p2"].clipboard == (KEY_SHOT, Z_BASIS) and first(log, "copy", "p2") is not None


def test_the_toss_fizzles_when_bob_is_hit_or_gone():
    fight, alice, bob, other = pair_fight(rival_x=520.0)
    tossed(fight, 280.0, 100.0)
    bob.decohere()
    events = run(fight, 1)
    assert fight.tosses == [] and "fizzle" in [e.kind for e in events]


def test_while_bob_is_gone_x_is_her_own_small_photon():
    from brawl_ket.moves import SOLO_PHOTON
    fight, alice, bob, other = pair_fight(rival_x=420.0)
    bob.decohere()
    events = run(fight, 90, once(X))
    assert fight.tosses == [] and alice.cooldowns["stand.X"] > 0
    assert [e.kind for e in events if e.player == "p1" and e.kind == "projectile"] == ["projectile"]
    assert other.health == ROBERT.health - SOLO_PHOTON.damage


def test_teleport_swaps_them_at_once_with_a_flash_at_both_ends():
    fight, alice, bob, other = pair_fight(rival_x=520.0)
    a0, b0 = alice.x, bob.x
    log = [fight.step({"p1": DOWN_X if i == 0 else IDLE}) for i in range(10)]
    at = first(log, "teleport")
    assert at == ALICE_BOB.moves["crouch.X"].startup
    assert (alice.x, bob.x) == (b0, a0) and alice.facing == bob.facing == 1     # a step back out of trouble
    assert other.health == ROBERT.health


def test_teleport_crosses_up_a_rival_standing_between_them():
    fight, alice, bob, other = pair_fight(rival_x=520.0)
    run(fight, 1, DOWN_X)
    other.x = alice.x - 20.0                # the rival steps in between them, in the startup
    run(fight, ALICE_BOB.moves["crouch.X"].startup)
    assert alice.x < other.x < bob.x        # Alice is suddenly on the far side ...
    assert alice.facing == 1 and bob.facing == 1        # ... facing the rival, and Bob as ever as she does


def test_no_teleport_while_bob_is_gone_and_he_never_echoes_it():
    fight, alice, bob, other = pair_fight(rival_x=520.0)
    bob.decohere()
    events = run(fight, 20, once(DOWN_X))
    assert "teleport" not in [e.kind for e in events] and "crouch.X" not in alice.cooldowns
    fight, alice, bob, other = pair_fight(rival_x=520.0)
    events = run(fight, 40, once(DOWN_X))
    assert [e.kind for e in events].count("teleport") == 1      # one swap for both


def test_bell_dive_comes_twice_once_per_jump_each():
    fight, alice, bob, other = pair_fight(rival_x=520.0)
    starts = []
    for i in range(80):
        inp = FighterInput(up=True) if i == 0 else X if i in (10, 14) else IDLE
        fight.step({"p1": inp})
        for name, f in (("alice", alice), ("bob", bob)):
            if f.action == "attack" and f.frame == 0 and f.move.name == "BELL DIVE":
                starts.append((name, i))
    assert starts == [("alice", 10), ("bob", 22)]           # the second press: once per jump
