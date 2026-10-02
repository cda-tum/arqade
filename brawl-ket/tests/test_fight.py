import random
import pytest
from dataclasses import replace
from types import MappingProxyType

from brawl_ket import shor
from brawl_ket.config import (
    FLOOR_Y,
    HITSTOP,
    HITSTOP_LOGICAL,
    LOGICAL_DAMAGE,
    ROUND_FRAMES,
    STAGE_LEFT,
    STAGE_RIGHT,
    START_X,
    THROW_RANGE,
    THROW_SLACK,
)
from brawl_ket.fight import KO_PUSH, Event, Fight, Shot, _overlap, body_width
from brawl_ket.fighter import IDLE, FighterInput
from brawl_ket.moves import CHARACTERS, QUINT, TRIO, Box

A = FighterInput(a=True)
B = FighterInput(b=True)
X = FighterInput(x=True)
JAB = TRIO.moves["stand.A"]
PHOTON = TRIO.moves["stand.X"]

BODY_WIDTH = body_width(TRIO, TRIO)     # the push box between two TRIOs
JAB_HIT_STEP = JAB.startup     # 0-based step on which a jab pressed at step 0 first hits


def new(gap=40.0):
    """A fresh fight with the fighters `gap` px apart (p1 stays at its start)."""
    fight = Fight({"p1": TRIO, "p2": TRIO})
    fight.fighters["p2"].x = fight.fighters["p1"].x + gap
    return fight


def versus(c1, c2, gap):
    """A fresh fight between characters c1 (p1) and c2 (p2), `gap` px apart."""
    fight = Fight({"p1": c1, "p2": c2})
    fight.fighters["p2"].x = fight.fighters["p1"].x + gap
    return fight


def script(fight, frames, p1=IDLE, p2=IDLE):
    """Step `frames` frames and return every event, in order.

    p1 / p2 are a FighterInput given on every frame, or a {frame: FighterInput}
    dict (frame numbers count from this call; other frames are IDLE).
    """
    events = []
    for i in range(frames):
        ins = {}
        for key, spec in (("p1", p1), ("p2", p2)):
            ins[key] = spec.get(i, IDLE) if isinstance(spec, dict) else spec
        events.extend(fight.step(ins))
    return events


def kinds(events):
    return [e.kind for e in events]


def of(events, *wanted):
    return [e for e in events if e.kind in wanted]


def snapshot(fight):
    return (
        fight.frames_left,
        [(f.x, f.y, f.frame, f.stun, f.code.timer) for f in fight.fighters.values()],
        [(s.x, s.life) for s in fight.shots],
    )


def with_move(slot, move):
    return replace(TRIO, moves=MappingProxyType({**TRIO.moves, slot: move}))


# --- construction ---------------------------------------------------------------------

def test_a_new_round():
    fight = Fight({"p1": TRIO, "p2": TRIO})
    assert fight.fighters["p1"].x == START_X["p1"] and fight.fighters["p1"].facing == 1
    assert fight.fighters["p2"].x == START_X["p2"] and fight.fighters["p2"].facing == -1
    assert fight.frames_left == ROUND_FRAMES and fight.hitstop == 0
    assert not fight.over and fight.winner is None and fight.shots == []


# --- hits and the Shor code's rules ----------------------------------------------------

def test_jab_hits_a_standing_rival_and_flips_a_light():
    fight = new()
    events = script(fight, 20, p1={0: A})
    hits = of(events, "hit", "logical")
    assert [(e.kind, e.player, e.error) for e in hits] == [("hit", "p2", shor.X)]
    p2 = fight.fighters["p2"]
    assert p2.health == 100 - JAB.chip
    assert p2.code.x_cells == {(shor.HIGH, shor.A_COL)}
    assert fight.fighters["p1"].health == 100


def test_the_jab_reaches_70_px_but_not_80():
    # the jab box ends 58 px ahead; the rival's hurtbox starts 14 px before its x
    hit = of(script(new(gap=70.0), 20, p1={0: A}), "hit", "logical")
    miss = of(script(new(gap=80.0), 20, p1={0: A}), "hit", "logical")
    assert [e.kind for e in hit] == ["hit"]
    assert miss == []


def test_hit_event_is_where_the_boxes_overlap():
    fight = new()
    (hit,) = of(script(fight, 20, p1={0: A}), "hit")
    # the push box moves them to x=218 and 262: the jab box spans 232..276 (14..58 px ahead of
    # p1) and p2's hurtbox 248..276, so the overlap's centre is at 262
    assert 248 <= hit.x <= 276
    assert 200 <= hit.y <= 240      # screen px, y down: the jab is 70..84 up from the floor


def test_jab_jab_cancels():
    fight = new()
    events = script(fight, 40, p1={0: A, JAB_HIT_STEP: A})
    hits = of(events, "hit", "cancel", "logical")
    assert [e.kind for e in hits] == ["hit", "cancel"]       # XX = I
    assert fight.fighters["p2"].health == 100 - 2 * JAB.chip  # the chip is not refunded
    assert fight.fighters["p2"].code.lights == 0


def test_the_cycle_repairs_between_spaced_hits():
    fight = new()
    gap = TRIO.cycle_frames + 10        # more than one whole cycle apart
    events = script(fight, gap + 80, p1={0: A, gap: A})
    assert of(events, "logical") == []
    assert len(of(events, "hit")) == 2
    corrected = of(events, "corrected")
    assert [e.player for e in corrected] == ["p2", "p2"]    # one repair after each hit
    assert fight.fighters["p2"].health == 100 - 2 * JAB.chip


def test_two_hits_within_one_cycle_still_count_against_each_other():
    fight = new()
    gap = TRIO.cycle_frames - 20        # the second jab lands inside the same 1 s cycle
    events = script(fight, gap + 40, p1={0: A, gap: A})
    assert [e.kind for e in of(events, "hit", "cancel", "logical")] == ["hit", "cancel"]


def test_a_jab_into_a_heavy_still_combos():
    HEAVY = TRIO.moves["stand.B"]
    fight = new()
    events = script(fight, 60, p1={0: A, JAB_HIT_STEP: B})
    hits = of(events, "hit", "logical")
    assert [(e.kind, e.error) for e in hits] == [("hit", shor.X), ("logical", shor.X)]
    assert fight.fighters["p1"].chain == 2
    assert fight.fighters["p2"].health == 100 - JAB.chip - (LOGICAL_DAMAGE + HEAVY.bonus)


def test_a_lone_heavy_from_neutral_is_only_a_correctable_hit():
    fight = new()
    events = script(fight, 60, p1={0: B})
    assert [(e.kind, e.error) for e in of(events, "hit", "logical")] == [("hit", shor.X)]
    assert fight.fighters["p2"].health == 100 - TRIO.moves["stand.B"].chip


def test_a_throw_whiffs_on_an_airborne_rival():
    fight = new(gap=float(BODY_WIDTH))
    p2 = fight.fighters["p2"]
    p2.y = 20.0                 # in the air, but still level with the throw box
    events = script(fight, 20, p1={0: FighterInput(dx=1, b=True)})
    assert of(events, "hit", "logical") == [] and p2.health == 100


def test_a_throw_whiffs_on_a_stunned_rival():
    fight = new(gap=float(BODY_WIDTH))
    p2 = fight.fighters["p2"]
    p2.take_hit(replace(JAB, knockback=0.0, hitstun=30, chip=0), 1)
    assert p2.action == "hitstun"
    events = script(fight, 20, p1={0: FighterInput(dx=1, b=True)})
    assert of(events, "hit", "logical") == [] and p2.health == 100


def test_a_trade_applies_both_hits():
    fight = new()
    events = script(fight, 20, p1={0: A}, p2={0: A})
    hits = of(events, "hit", "logical")
    assert sorted((e.kind, e.player) for e in hits) == [("hit", "p1"), ("hit", "p2")]
    assert fight.fighters["p1"].health == fight.fighters["p2"].health == 100 - JAB.chip
    # both moves count as having connected, and both fighters are stunned
    assert fight.fighters["p1"].action == fight.fighters["p2"].action == "hitstun"


def test_a_downed_fighter_cannot_be_hit():
    SWEEP = TRIO.moves["crouch.B"]
    fight = new()
    p2 = fight.fighters["p2"]
    p2.take_hit(replace(SWEEP, chip=0, error=shor.X, bonus=0), 1)
    # a knockdown with a corrected hit: no health lost
    assert p2.action == "knockdown" and p2.health == 100
    events = script(fight, 12, p1={0: A})
    assert of(events, "hit", "logical") == [] and p2.health == 100 and p2.action == "knockdown"
    # a shot flies over a downed fighter
    fight.shots.append(Shot("p1", PHOTON, p2.x - 10, 0.0, 4.0, 100))
    assert of(script(fight, 3), "hit", "logical") == [] and p2.health == 100
    assert len(fight.shots) == 1


def test_the_landing_shockwave_skips_a_downed_rival():
    fight = Fight({"p1": COLLAPSE, "p2": TRIO})
    fight.fighters["p2"].x = fight.fighters["p1"].x + 60
    p2 = fight.fighters["p2"]
    p2.take_hit(replace(TRIO.moves["crouch.B"], chip=0, error=shor.X, bonus=0), 1)
    p1 = fight.fighters["p1"]
    events = []
    for i in range(300):
        inp = FighterInput(up=True) if i == 0 else X if p1.y > 20 and p1.action == "jump" else IDLE
        events += fight.step({"p1": inp, "p2": IDLE})
        if p1.action == "attack":
            p1.move_hit = True
        if of(events, "land"):
            break
    events += script(fight, 3)
    assert of(events, "hit", "logical") == [] and p2.health == 100


# --- hitstop ----------------------------------------------------------------------------

def test_hitstop_freezes_everything():
    fight = new()
    fight.shots.append(Shot("p1", PHOTON, 100.0, 200.0, 4.0, 50))    # high above the fighters
    first = []
    for i in range(30):
        first = fight.step({"p1": A if i == 0 else IDLE, "p2": IDLE})
        if of(first, "hit"):
            break
    assert fight.hitstop == HITSTOP
    snap = snapshot(fight)
    assert snap[2]      # the shot is still there to be frozen
    for _ in range(HITSTOP):
        assert fight.step({"p1": A, "p2": A}) == []
        assert snapshot(fight) == snap
    assert fight.hitstop == 0
    fight.step({"p1": IDLE, "p2": IDLE})
    assert fight.frames_left == snap[0] - 1
    assert fight.shots[0].x == snap[2][0][0] + 4.0


def test_presses_in_hitstop_are_buffered_so_the_chain_cancel_comes_out():
    fight = new()
    events = []
    for i in range(80):
        done = bool(of(events, "cancel", "logical"))
        inp = A if not done and (i == 0 or fight.hitstop > 0) else IDLE   # A on every hitstop frame
        events += fight.step({"p1": inp, "p2": IDLE})
    hits = of(events, "hit", "cancel", "logical")
    assert [e.kind for e in hits] == ["hit", "cancel"]          # the second jab came out and landed
    assert fight.fighters["p2"].health == 100 - 2 * JAB.chip


def test_a_press_in_hitstop_does_not_age():
    fight = new()
    for i in range(30):
        fight.step({"p1": A if i == 0 else IDLE, "p2": IDLE})
        if fight.hitstop:
            break
    fight.step({"p1": A, "p2": IDLE})
    buffered = list(fight.fighters["p1"].buffer)
    fight.step({"p1": IDLE, "p2": IDLE})
    assert [p.age for p in buffered] == [0] and buffered[0].button == "a"


def test_a_logical_error_stops_the_game_for_longer():
    fight = new()
    fight.fighters["p2"].code.apply_x(shor.HIGH, shor.B_COL)   # a jab on HIGH A now breaks it
    for i in range(30):
        if of(fight.step({"p1": A if i == 0 else IDLE, "p2": IDLE}), "logical"):
            break
    assert fight.hitstop == HITSTOP_LOGICAL


# --- projectiles ------------------------------------------------------------------------

def test_photon_travels_and_hits():
    fight = new(gap=200.0)
    events = script(fight, 120, p1={0: X})
    assert [e.player for e in of(events, "projectile")] == ["p1"]
    hits = of(events, "hit", "logical")
    assert [(e.kind, e.player, e.error, e.row) for e in hits] == [("hit", "p2", shor.Z, shor.HIGH)]
    assert fight.fighters["p2"].health == 100 - PHOTON.chip
    assert fight.shots == []            # removed on hitting


def test_photon_spawns_in_front_of_its_owner_and_moves_every_frame():
    fight = new(gap=300.0)
    for i in range(PHOTON.startup + 1):
        events = fight.step({"p1": X if i == 0 else IDLE, "p2": IDLE})
    assert of(events, "projectile")
    (shot,) = fight.shots
    p1 = fight.fighters["p1"]
    assert shot.owner == "p1" and shot.vx == 4.0
    assert shot.x == p1.x + 24 + 4.0        # spawned 24 px ahead, then moved this frame
    assert shot.life == PHOTON.projectile.lifetime - 1


def test_photon_expires_off_stage():
    fight = new(gap=60.0)
    fight.fighters["p1"].x = 500.0
    fight.fighters["p2"].x = 560.0
    for i in range(PHOTON.startup + 1):
        fight.step({"p1": X if i == 0 else IDLE, "p2": IDLE})
    assert len(fight.shots) == 1
    fight.fighters["p2"].x = STAGE_LEFT + 10    # out of its way
    events = script(fight, 60)
    assert fight.shots == []
    assert of(events, "hit", "logical") == []
    assert fight.fighters["p2"].health == 100


def test_photon_expires_when_its_life_runs_out():
    fight = new(gap=100.0)
    fight.shots.append(Shot("p1", PHOTON, 300.0, 200.0, 0.0, 3))    # high above the fighters
    script(fight, 2)
    assert len(fight.shots) == 1
    script(fight, 1)
    assert fight.shots == []


def test_shots_from_different_owners_cancel_each_other():
    fight = new(gap=240.0)
    events = script(fight, 90, p1={0: X}, p2={0: X})
    assert len(of(events, "projectile")) == 2
    assert fight.shots == []
    assert of(events, "hit", "logical") == []
    assert fight.fighters["p1"].health == fight.fighters["p2"].health == 100


def test_a_shot_cannot_hit_its_own_owner():
    fight = new(gap=300.0)
    p1 = fight.fighters["p1"]
    fight.shots.append(Shot("p1", PHOTON, p1.x, 0.0, 4.0, 100))     # inside p1's own hurtbox
    assert _overlap(fight.shots[0].box, p1.hurtbox) is not None
    events = script(fight, 3)
    assert of(events, "hit", "logical") == []
    assert p1.health == 100 and len(fight.shots) == 1


def photon_run(jump_at, gap=80.0, frames=120):
    """A PHOTON `gap` px from a standing p1, flying at it; p1 jumps straight up on frame jump_at
    (None: it stays put). Returns every hit or logical event."""
    fight = new(gap=300.0)
    p1 = fight.fighters["p1"]
    fight.shots.append(Shot("p2", PHOTON, p1.x + gap, 0.0, -PHOTON.projectile.speed, 200))
    return of(script(fight, frames, p1={jump_at: FighterInput(up=True)} if jump_at is not None else IDLE),
              "hit", "logical")


def test_a_jump_clears_a_photon_80_px_away():
    assert [e.kind for e in photon_run(None)] == ["hit"]        # standing still it connects
    assert photon_run(0) == []
    assert photon_run(0, gap=60.0) == []        # even a late jump: the old 9.5 jump needed 70 px


def test_projectiles_are_too_slow_to_tunnel():
    # collisions are overlap-only after each move (see Fight._move_shots)
    for char in CHARACTERS.values():
        for move in char.moves.values():
            if move.projectile is not None:
                assert move.projectile.speed * 2 < move.projectile.box.w + 16


# --- landing shockwave ----------------------------------------------------------------

SHOCK_DIVE = replace(
    TRIO.moves["air.X"], landing=Box(-70, 0, 140, 16), landing_error=shor.Z,
)
COLLAPSE = with_move("air.X", SHOCK_DIVE)


def dive_and_land(rival_dx):
    """p1 jumps and dives; the rival stands rival_dx px to p1's right. Returns (fight, events)."""
    fight = Fight({"p1": COLLAPSE, "p2": TRIO})
    fight.fighters["p2"].x = fight.fighters["p1"].x + rival_dx
    p1 = fight.fighters["p1"]
    events = []
    for i in range(300):
        inp = FighterInput(up=True) if i == 0 else X if p1.y > 20 and p1.action == "jump" else IDLE
        events += fight.step({"p1": inp, "p2": IDLE})
        if p1.action == "attack":
            p1.move_hit = True      # isolate the shockwave from the dive's own hitbox
        if of(events, "land") and p1.y == 0 and p1.move is not None and p1.move.landing:
            events += script(fight, 6)
            break
    return fight, events


def test_the_landing_shockwave_hits_a_nearby_rival_with_its_own_error():
    fight, events = dive_and_land(rival_dx=60)
    p2 = fight.fighters["p2"]
    assert [(e.kind, e.player, e.error, e.row) for e in of(events, "hit", "logical")] == [
        ("hit", "p2", shor.Z, shor.LOW),     # the shockwave's own error, on its own row
    ]
    assert p2.health == 100 - SHOCK_DIVE.chip
    assert p2.code.z_rows == {shor.LOW}


def test_the_landing_shockwave_misses_a_far_rival():
    fight, events = dive_and_land(rival_dx=300)
    assert of(events, "hit", "logical") == []
    assert fight.fighters["p2"].health == 100


def test_the_landing_shockwave_hits_once():
    fight, events = dive_and_land(rival_dx=60)
    events += script(fight, 30)
    assert len(of(events, "hit", "logical")) == 1


def test_an_ordinary_dive_has_no_shockwave():
    fight = Fight({"p1": TRIO, "p2": TRIO})
    fight.fighters["p2"].x = fight.fighters["p1"].x + 60
    p1 = fight.fighters["p1"]
    events = []
    for i in range(300):
        inp = FighterInput(up=True) if i == 0 else X if p1.y > 20 and p1.action == "jump" else IDLE
        events += fight.step({"p1": inp, "p2": IDLE})
        if p1.action == "attack":
            p1.move_hit = True
    assert of(events, "hit", "logical") == []


# --- p1 and p2 are treated alike ----------------------------------------------------------

def test_a_throw_against_a_walking_rival_is_the_same_for_p1_and_p2():
    # Just in range at the start of the frame; the rival walks away, out of range.
    # Both fighters read the rival's x from the START of the frame, so both get a throw.
    outcomes = []
    for attacker, rival, side in (("p1", "p2", 1), ("p2", "p1", -1)):
        fight = new(gap=THROW_RANGE - 1.0)
        inputs = {attacker: FighterInput(dx=side, b=True), rival: FighterInput(dx=side)}
        events = list(fight.step(inputs))
        assert fight.fighters[attacker].slot == "throw", attacker
        for _ in range(20):
            events += fight.step({attacker: IDLE, rival: FighterInput(dx=side)})
        hits = [(e.kind, e.player, e.error) for e in of(events, "hit", "logical")]
        outcomes.append((
            [(k, "rival" if p == rival else "attacker", err) for k, p, err in hits],
            fight.fighters[rival].health,
            fight.fighters[attacker].health,
        ))
    assert outcomes[0] == outcomes[1]


# --- bodies -----------------------------------------------------------------------------

def test_walking_into_each_other_never_overlaps_closer_than_the_body_width():
    fight = new(gap=200.0)
    closest = 1e9
    for _ in range(200):
        fight.step({"p1": FighterInput(dx=1), "p2": FighterInput(dx=-1)})
        closest = min(closest, abs(fight.fighters["p2"].x - fight.fighters["p1"].x))
    assert closest >= BODY_WIDTH - 1e-9


def test_the_push_is_shared_and_a_wall_makes_the_other_take_it_all():
    fight = new(gap=10.0)
    p1, p2 = fight.fighters["p1"], fight.fighters["p2"]
    mid = (p1.x + p2.x) / 2
    fight.step({"p1": IDLE, "p2": IDLE})
    assert (p1.x, p2.x) == (mid - BODY_WIDTH / 2, mid + BODY_WIDTH / 2)

    fight = new()
    p1, p2 = fight.fighters["p1"], fight.fighters["p2"]
    p2.x = STAGE_RIGHT
    p1.x = STAGE_RIGHT - 5
    fight.step({"p1": IDLE, "p2": IDLE})
    assert p2.x == STAGE_RIGHT and p1.x == STAGE_RIGHT - BODY_WIDTH
    p1.x, p2.x = STAGE_LEFT, STAGE_LEFT + 4
    fight.step({"p1": IDLE, "p2": IDLE})
    assert p1.x == STAGE_LEFT and p2.x == STAGE_LEFT + BODY_WIDTH


def test_fighters_in_the_air_pass_through_each_other():
    fight = new(gap=10.0)
    fight.fighters["p2"].y = 80.0
    fight.step({"p1": IDLE, "p2": IDLE})
    assert fight.fighters["p2"].x - fight.fighters["p1"].x == 10.0


# --- the end of a round --------------------------------------------------------------

def test_ko_ends_the_round():
    fight = new()
    fight.fighters["p2"].health = JAB.chip
    events = script(fight, 20, p1={0: A})
    assert kinds(events)[-1] == "ko" and kinds(events).count("ko") == 1
    assert fight.over and fight.winner == "p1"
    assert fight.fighters["p2"].health == 0
    assert fight.step({"p1": A, "p2": A}) == []         # once over, nothing happens
    assert fight.frames_left == ROUND_FRAMES - JAB_HIT_STEP - 1     # the clock stopped at the KO


def test_a_double_ko_is_a_draw():
    fight = new()
    fight.fighters["p1"].health = fight.fighters["p2"].health = JAB.chip
    events = script(fight, 20, p1={0: A}, p2={0: A})
    assert "ko" in kinds(events)
    assert fight.over and fight.winner is None


def test_timeout_higher_health_wins_and_equal_is_a_draw():
    for h1, h2, winner in ((80, 50, "p1"), (50, 80, "p2"), (60, 60, None)):
        fight = new(gap=300.0)
        fight.fighters["p1"].health, fight.fighters["p2"].health = h1, h2
        fight.frames_left = 3
        events = script(fight, 2)
        assert not fight.over and events == []
        events = script(fight, 1)
        assert kinds(events) == ["timeout"]
        assert fight.over and fight.winner == winner and fight.frames_left == 0
        assert script(fight, 5) == []


def test_ko_beats_timeout_on_the_same_frame():
    fight = new()
    fight.fighters["p2"].health = JAB.chip
    fight.frames_left = JAB_HIT_STEP + 1
    events = script(fight, 20, p1={0: A})
    assert "ko" in kinds(events) and "timeout" not in kinds(events)
    assert fight.winner == "p1"


def test_the_clock_counts_down_one_per_frame():
    fight = new(gap=300.0)
    script(fight, 10)
    assert fight.frames_left == ROUND_FRAMES - 10


# --- local events pass through ---------------------------------------------------------

def test_local_events_pass_through_with_the_player():
    fight = new(gap=300.0)
    events = script(fight, 2, p1={0: A}, p2={0: FighterInput(down=True)})
    assert Event("attack", "p1") in events
    assert not any(e.kind == "switch" for e in events)     # crouching is not an event
    fight = new(gap=300.0)
    events = script(fight, 80, p2={0: FighterInput(up=True)})
    assert Event("land", "p2") in events


# --- determinism -----------------------------------------------------------------------

def random_inputs(rng):
    return {
        key: FighterInput(
            dx=rng.choice((-1, 0, 1)), up=rng.random() < 0.05, down=rng.random() < 0.2,
            a=rng.random() < 0.1, b=rng.random() < 0.05, x=rng.random() < 0.05,
        )
        for key in ("p1", "p2")
    }


def test_same_inputs_same_fight():
    results = []
    for _ in range(2):
        rng = random.Random(1)
        fight = Fight({"p1": TRIO, "p2": TRIO})
        events = []
        for _ in range(600):
            events.extend(fight.step(random_inputs(rng)))
        state = [(f.x, f.y, f.health, f.action, sorted(f.code.x_cells), sorted(f.code.z_rows),
                  f.crouching)
                 for f in fight.fighters.values()]
        results.append((events, state, fight.frames_left, fight.over, fight.winner))
    assert results[0] == results[1]
    assert any(e.kind in ("hit", "logical") for e in results[0][0])      # the run did fight


PAIRINGS = [(a, b) for a in CHARACTERS.values() for b in CHARACTERS.values()]


def test_a_jab_connects_at_the_closest_spacing():
    # Walked all the way in, the push box holds the fighters body_width apart: a jab
    # (either side, standing or crouching rival, every pairing) must still reach.
    for (c1, c2), crouching in ((pair, c) for pair in PAIRINGS for c in (False, True)):
        for attacker, rival in (("p1", "p2"), ("p2", "p1")):
            fight = versus(c1, c2, 200.0)
            for _ in range(120):
                fight.step({"p1": FighterInput(dx=1), "p2": FighterInput(dx=-1)})
            assert abs(fight.fighters["p2"].x - fight.fighters["p1"].x) == body_width(c1, c2)
            events = script(fight, 20, **{attacker: {0: A}, rival: FighterInput(down=crouching)})
            assert [e.player for e in of(events, "hit", "logical")] == [rival], (
                c1.name, c2.name, attacker, crouching)


# --- QUINT ------------------------------------------------------------------------------------

GRAB = QUINT.moves["stand.X"]
DOWN = FighterInput(down=True)


def results(events):
    return [(e.kind, e.error) for e in of(events, "hit", "logical")]


def grab_lands(gap, press, crouching=False):
    """QUINT (p1) presses `press` once at `gap` px from a TRIO; returns the fight and its hits."""
    fight = versus(QUINT, TRIO, gap)
    events = script(fight, 70, p1={0: press}, p2=DOWN if crouching else IDLE)
    return fight, results(events)


def test_syndrome_grab_lands_on_trio_in_either_stance():
    for crouching in (False, True):
        fight, hits = grab_lands(64.0, X, crouching)        # well outside a throw's reach
        assert hits == [("hit", shor.Z)], crouching          # a Z on MID: alone, correctable
        trio = fight.fighters["p2"]
        assert trio.health == 100 - GRAB.chip


def test_the_syndrome_grab_reaches_further_than_a_throw():
    def longest(press, error):
        return max(g for g in range(int(BODY_WIDTH), 140)
                   if grab_lands(float(g), press)[1] == [("hit", error)])

    grab, throw = longest(X, shor.Z), longest(FighterInput(dx=1, b=True), shor.Y)
    assert throw <= body_width(QUINT, TRIO) + THROW_SLACK
    assert grab >= throw + 15, (grab, throw)


def test_a_whiffed_syndrome_grab_leaves_quint_open():
    fight = versus(QUINT, TRIO, 140.0)
    events = script(fight, GRAB.startup + GRAB.active + 5, p1={0: X})
    assert results(events) == []
    quint = fight.fighters["p1"]
    assert (quint.slot, quint.phase) == ("stand.X", "recovery")    # stuck in its long recovery


def test_reencode_clears_flipped_lights_and_has_a_cooldown():
    reencode = QUINT.moves["crouch.X"]
    fight = versus(TRIO, QUINT, 200.0)
    quint = fight.fighters["p2"]
    quint.code.apply_x(shor.HIGH, shor.A_COL)
    quint.code.apply_z(shor.MID)             # every row in danger
    hold = {i: DOWN for i in range(400)}
    events = script(fight, reencode.startup + 1, p2={**hold, 0: FighterInput(down=True, x=True)})
    assert [(e.kind, e.player) for e in of(events, "attack", "reencode")] == [
        ("attack", "p2"), ("reencode", "p2")]
    assert quint.code.lights == 0            # wiped before the cycle got to it
    assert quint.code.timer < quint.char.cycle_frames
    assert quint.code.apply_z(shor.LOW) == shor.FLIPPED     # so the next hit is only correctable again
    # on cooldown: another press does nothing for 4 s
    events = script(fight, 60, p2={**hold, 40: FighterInput(down=True, x=True)})
    assert of(events, "attack", "reencode") == []
    assert quint.cooldowns["crouch.X"] > 0
    events = script(fight, reencode.cooldown, p2=hold)
    events = script(fight, 20, p2={**hold, 0: FighterInput(down=True, x=True)})
    assert [e.kind for e in of(events, "attack", "reencode")] == ["attack", "reencode"]


def collapse(trio_dx, crouching=False, press_at=60):
    """QUINT (p1) jumps straight up and presses X once it is higher than `press_at` px
    (on the way up), or, with a negative press_at, once it is falling and lower than
    -press_at. A TRIO stands (or crouches) trio_dx px to its right. Returns the hits."""
    fight = versus(QUINT, TRIO, trio_dx)
    trio = fight.fighters["p2"]
    quint = fight.fighters["p1"]
    events, pressed = [], False
    for i in range(200):
        due = quint.y > press_at if press_at > 0 else 0 < quint.y < -press_at and quint.vy < 0
        inp = FighterInput(up=True) if i == 0 else IDLE
        if not pressed and quint.action == "jump" and due:
            inp, pressed = X, True
        events += fight.step({"p1": inp, "p2": DOWN if crouching else IDLE})
    assert pressed
    return results(events), trio


def test_collapse_hits_z_high_directly_and_z_low_with_the_shockwave():
    collapse_move = QUINT.moves["air.X"]
    # straight onto a crouching TRIO: the slam is a Z on HIGH, and the shockwave does not
    # hit it again while it reels
    hits, trio = collapse(10.0, crouching=True)
    assert hits == [("hit", shor.Z)]
    assert trio.health == 100 - collapse_move.chip
    # next to a standing TRIO: the slam misses, and the shockwave is a Z on LOW
    hits, trio = collapse(48.0)
    assert hits == [("hit", shor.Z)]
    assert trio.health == 100 - collapse_move.chip
    # far away: nothing
    hits, trio = collapse(150.0)
    assert hits == [] and trio.health == 100


def test_a_collapse_that_lands_before_it_dives_has_no_shockwave():
    hits, trio = collapse(48.0, press_at=-25)
    assert hits == [] and trio.health == 100


def chain_on(fight, attacker, buttons):
    """`attacker` presses the buttons as a chain: each one once the move before it has hit."""
    f = fight.fighters[attacker]
    queue, events = list(buttons), []
    for i in range(150):
        inp = IDLE
        if queue and (i == 0 or (f.action == "attack" and f.move_hit
                                 and f.chain == len(buttons) - len(queue))):
            inp = FighterInput(**{queue.pop(0): True})
        events += fight.step({attacker: inp})
    return results(events)


def test_a_then_b_at_one_height_breaks_either_fighter():
    for c1, c2 in PAIRINGS:
        fight = versus(c1, c2, 40.0)
        assert chain_on(fight, "p1", "ab") == [("hit", shor.X), ("logical", shor.X)], (c1.name, c2.name)


def test_a_collapse_landing_reports_its_shockwave():
    fight = versus(QUINT, TRIO, 150.0)
    quint = fight.fighters["p1"]
    events = []
    for i in range(120):
        inp = FighterInput(up=True) if i == 0 else X if quint.action == "jump" and quint.y > 60 else IDLE
        events += fight.step({"p1": inp})
    (wave,) = of(events, "shockwave")
    assert (wave.player, wave.error) == ("p1", shor.Z)
    assert wave.x == quint.x and wave.y == FLOOR_Y
    # a plain jump's landing has none
    fight = versus(QUINT, TRIO, 150.0)
    assert of(script(fight, 80, p1={0: FighterInput(up=True)}), "shockwave") == []


def test_the_push_box_fits_each_pairing():
    assert BODY_WIDTH == 44 and THROW_RANGE == BODY_WIDTH + THROW_SLACK
    assert body_width(TRIO, QUINT) == body_width(QUINT, TRIO) > BODY_WIDTH
    assert body_width(QUINT, QUINT) > body_width(TRIO, QUINT)
    for c1, c2 in PAIRINGS:
        fight = versus(c1, c2, 200.0)
        for _ in range(150):
            fight.step({"p1": FighterInput(dx=1), "p2": FighterInput(dx=-1)})
        gap = fight.fighters["p2"].x - fight.fighters["p1"].x
        assert gap == body_width(c1, c2), (c1.name, c2.name)
        for f in fight.fighters.values():
            assert f.throw_range == gap + THROW_SLACK, (c1.name, c2.name)


def test_a_throw_works_from_the_closest_spacing_to_the_end_of_its_range():
    for (c1, c2), crouching in ((pair, c) for pair in PAIRINGS for c in (False, True)):
        for gap in (body_width(c1, c2), body_width(c1, c2) + THROW_SLACK):
            fight = versus(c1, c2, float(gap))
            events = script(fight, 20, p1={0: FighterInput(dx=1, b=True)},
                            p2=FighterInput(down=True) if crouching else IDLE)
            assert results(events) == [("hit", shor.Y)], (c1.name, c2.name, gap, crouching)


# --- PHASE SLIDE passes under photons ---------------------------------------------------

SLIDE = TRIO.moves["crouch.X"]
DOWN_X = FighterInput(down=True, x=True)


def photon_at(fight, owner, x):
    """A photon from `owner`, placed at x and flying towards the other fighter."""
    target = fight.fighters["p1" if owner == "p2" else "p2"]
    vx = PHOTON.projectile.speed * (1 if target.x > x else -1)
    shot = Shot(owner, PHOTON, x, 0.0, vx, PHOTON.projectile.lifetime)
    fight.shots.append(shot)
    return shot


def test_a_phase_slide_passes_under_a_photon():
    fight = new(gap=300.0)
    p1 = fight.fighters["p1"]
    script(fight, 30, p1=FighterInput(down=True))           # crouched
    script(fight, SLIDE.startup + 2, p1={0: DOWN_X}, p2=FighterInput())
    assert p1.slot == "crouch.X" and p1.phase == "active"
    photon_at(fight, "p2", p1.x + 30)
    events = script(fight, 12, p1=FighterInput(down=True))
    assert not of(events, "hit", "logical")


def test_a_plain_crouch_is_still_hit_by_a_photon():
    fight = new(gap=300.0)
    script(fight, 30, p1=FighterInput(down=True))
    photon_at(fight, "p2", fight.fighters["p1"].x + 30)
    events = script(fight, 12, p1=FighterInput(down=True))
    assert of(events, "hit", "logical")


def test_the_slides_hurtbox_is_below_a_photon_only_while_it_slides():
    fight = new(gap=300.0)
    p1 = fight.fighters["p1"]
    script(fight, 30, p1=FighterInput(down=True))
    photon_bottom = PHOTON.projectile.box.y
    lows = []
    for i in range(SLIDE.startup + SLIDE.active + SLIDE.recovery):
        script(fight, 1, p1=DOWN_X if i == 0 else FighterInput(down=True))
        left, top, w, h = p1.hurtbox
        lows.append((p1.phase, FLOOR_Y - top < photon_bottom))
    assert all(low for phase, low in lows if phase == "active")
    assert not any(low for phase, low in lows if phase != "active")


# --- after the round: the bodies settle -------------------------------------------------


def ko_by_jab(fight):
    """KO p2 with one jab from p1 (p2 on its last point of health)."""
    fight.fighters["p2"].health = 1
    events = []
    for i in range(30):
        events += fight.step({"p1": A if i == 0 else IDLE, "p2": IDLE})
        if fight.over:
            break
    assert fight.over and fight.winner == "p1"
    return events


def test_a_knocked_out_fighter_goes_down_and_stays_down():
    fight = new(gap=40.0)
    ko_by_jab(fight)
    p2 = fight.fighters["p2"]
    assert p2.action == "knockdown"
    script(fight, 600)
    assert p2.action == "knockdown"


def test_after_the_round_the_bodies_move_but_nothing_else_does():
    fight = new(gap=40.0)
    ko_by_jab(fight)
    p2 = fight.fighters["p2"]
    x, frames_left = p2.x, fight.frames_left
    health = {k: f.health for k, f in fight.fighters.items()}
    lights = {k: (sorted(f.code.x_cells), sorted(f.code.z_rows)) for k, f in fight.fighters.items()}
    events = script(fight, 120, p1=A, p2=A)          # presses after the end do nothing
    assert events == []
    assert p2.x > x                                  # the KO's knockback carries it away
    assert fight.frames_left == frames_left
    assert {k: f.health for k, f in fight.fighters.items()} == health
    assert {k: (sorted(f.code.x_cells), sorted(f.code.z_rows)) for k, f in fight.fighters.items()} == lights
    assert fight.fighters["p1"].action == "idle"     # the winner finishes its move and stands


def test_the_ko_push_is_away_from_the_winner_even_off_a_light_hit():
    fight = new(gap=40.0)
    ko_by_jab(fight)
    p2 = fight.fighters["p2"]
    assert p2.vx * (p2.x - fight.fighters["p1"].x) > 0
    assert abs(p2.vx) >= KO_PUSH * 0.5


# --- a chain started by a jab that connects connects all the way -------------------------


def run_chain(c1, c2, gap, buttons, crouch=False):
    """p1 starts `buttons` with a jab at `gap`, pressing each next button the frame
    after the previous one hits. Returns how many of them hit."""
    fight = versus(c1, c2, gap)
    held = FighterInput(down=crouch)
    if crouch:
        script(fight, 20, p1=held)
        fight.fighters["p2"].x = fight.fighters["p1"].x + gap
    hits, i, press_next = 0, 0, True
    for _ in range(200):
        btn = buttons[i] if press_next and i < len(buttons) else None
        if btn:
            i += 1
        press_next = False
        events = fight.step({"p1": replace(held, **({btn: True} if btn else {})), "p2": IDLE})
        if of(events, "hit", "cancel", "logical"):
            hits += 1
            press_next = True
        if hits == len(buttons) or fight.over:
            break
    return hits


def jab_reach(c1, c2, crouch=False):
    return max(g for g in range(20, 120) if run_chain(c1, c2, g, ["a"], crouch) == 1)


@pytest.mark.parametrize("c1,c2", [(TRIO, TRIO), (TRIO, QUINT), (QUINT, TRIO), (QUINT, QUINT)],
                         ids=["TRIO-TRIO", "TRIO-QUINT", "QUINT-TRIO", "QUINT-QUINT"])
@pytest.mark.parametrize("crouch", [False, True], ids=["stand", "crouch"])
def test_a_chain_that_starts_with_a_hit_lands_every_hit(c1, c2, crouch):
    lo = round(body_width(c1, c2))
    for gap in range(lo, jab_reach(c1, c2, crouch) + 1, 2):
        for buttons in (["a", "b"], ["a", "a", "b"]):
            assert run_chain(c1, c2, gap, buttons, crouch) == len(buttons), (gap, buttons)


# --- the Shor grid ----------------------------------------------------------------------

from brawl_ket import shor  # noqa: E402


def press_at(fight, frames, **buttons):
    """p1 presses the given buttons on the given frames ({button: frame}), down held if `down`."""
    down = buttons.pop("down", False)
    events = []
    for i in range(frames):
        pressed = {b: f == i for b, f in buttons.items()}
        events += fight.step({"p1": FighterInput(down=down, **pressed), "p2": IDLE})
    return events


def test_a_jab_lights_its_cell_on_the_rivals_grid():
    fight = new(gap=50.0)
    events = press_at(fight, 30, a=0)
    hit = of(events, "hit")[0]
    assert (hit.error, hit.row, hit.col) == (shor.X, shor.HIGH, shor.A_COL)
    assert fight.fighters["p2"].code.x_cells == {(shor.HIGH, shor.A_COL)}


def test_two_jabs_at_one_height_cancel():
    fight = new(gap=50.0)
    events = press_at(fight, 40, a=0)
    events += press_at(fight, 40, a=0)
    assert kinds(of(events, "hit", "cancel", "logical")) == ["hit", "cancel"]
    assert fight.fighters["p2"].code.lights == 0


def test_jab_then_heavy_at_one_height_is_a_logical_error():
    fight = new(gap=50.0)
    events = run_chain_events(fight, ["a", "b"])
    assert kinds(of(events, "hit", "cancel", "logical")) == ["hit", "logical"]


def run_chain_events(fight, buttons, crouch=False):
    """Like run_chain, but returns the events."""
    held = FighterInput(down=crouch)
    events, i, press_next = [], 0, True
    for _ in range(200):
        btn = buttons[i] if press_next and i < len(buttons) else None
        if btn:
            i += 1
        press_next = False
        step = fight.step({"p1": replace(held, **({btn: True} if btn else {})), "p2": IDLE})
        events += step
        if of(step, "hit", "cancel", "logical"):
            press_next = True
        if i == len(buttons) and not press_next and of(step, "hit", "cancel", "logical"):
            break
    return events
