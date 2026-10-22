"""ALICE & BOB (docs/superpowers/specs/2026-10-21-brawl-ket-alice-bob-design.md, sections 2, 6, 7
and 8): two small fighters played as one. Bob replays Alice's inputs 12 frames later, 40 px
behind her, with his own hurtbox and hitboxes; the pair shares one health bar and one colour; a
knockdown decoheres Bob for 3 s; the round ends when the bar is empty."""

import pytest

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
from brawl_ket.moves import ALICE_BOB, BOB, BOHR, KID_NORMALS, NORMALS, ROBERT

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
