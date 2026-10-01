import random
from dataclasses import replace
from types import MappingProxyType

from brawl_ket import qec
from brawl_ket.config import (
    BODY_WIDTH,
    HITSTOP,
    HITSTOP_LOGICAL,
    LOGICAL_DAMAGE,
    ROUND_FRAMES,
    STAGE_LEFT,
    STAGE_RIGHT,
    START_X,
    THROW_RANGE,
)
from brawl_ket.fight import Event, Fight, Shot, _overlap
from brawl_ket.fighter import IDLE, FighterInput
from brawl_ket.moves import CHARACTERS, TRIO, Box

A = FighterInput(a=True)
B = FighterInput(b=True)
X = FighterInput(x=True)
JAB = TRIO.moves["stand.A"]
PHOTON = TRIO.moves["stand.X"]

JAB_HIT_STEP = JAB.startup     # 0-based step on which a jab pressed at step 0 first hits


def new(gap=40.0):
    """A fresh fight with the fighters `gap` px apart (p1 stays at its start)."""
    fight = Fight({"p1": TRIO, "p2": TRIO})
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


# --- hits and the qec rules -----------------------------------------------------------

def test_jab_hits_a_standing_rival_and_flips_a_light():
    fight = new()
    events = script(fight, 20, p1={0: A})
    hits = of(events, "hit", "logical")
    assert [(e.kind, e.player, e.error) for e in hits] == [("hit", "p2", qec.X)]
    p2 = fight.fighters["p2"]
    assert p2.health == 100 - JAB.chip == 97
    assert len(p2.code.flipped) == 1
    assert fight.fighters["p1"].health == 100


def test_hit_event_is_where_the_boxes_overlap():
    fight = new()
    (hit,) = of(script(fight, 20, p1={0: A}), "hit")
    # jab box 14..44 px in front of p1 (x=220), p2's hurtbox starts at 246
    assert 246 <= hit.x <= 264
    assert 200 <= hit.y <= 240      # screen px, y down: the jab is 70..84 up from the floor


def test_jab_jab_breaks_trio_with_a_logical_error():
    fight = new()
    events = script(fight, 40, p1={0: A, JAB_HIT_STEP: A})
    hits = of(events, "hit", "logical")
    assert [e.kind for e in hits] == ["hit", "logical"]
    assert fight.fighters["p2"].health == 100 - JAB.chip - (LOGICAL_DAMAGE + JAB.bonus)
    assert fight.fighters["p2"].health == 100 - 3 - 22
    assert fight.fighters["p2"].code.flipped == set()       # a logical error re-encodes


def test_a_standing_attack_on_a_croucher_is_logical_at_once():
    fight = new()
    fight.fighters["p2"].code.switch()      # |+++>: crouching
    assert fight.fighters["p2"].stance == "crouch"
    events = script(fight, 20, p1={0: A})
    assert [(e.kind, e.error) for e in of(events, "hit", "logical")] == [("logical", qec.X)]
    assert fight.fighters["p2"].health == 100 - LOGICAL_DAMAGE


def test_low_attack_on_a_stander_is_logical_at_once():
    fight = new()
    fight.fighters["p1"].code.switch()      # p1 crouches and uses crouch.A (a Z error)
    events = script(fight, 20, p1=FighterInput(down=True, a=True))
    assert [(e.kind, e.error) for e in of(events, "hit", "logical")] == [("logical", qec.Z)]
    assert fight.fighters["p2"].health == 100 - LOGICAL_DAMAGE


def test_throw_is_always_logical():
    for crouching in (False, True):
        fight = new(gap=float(BODY_WIDTH))
        if crouching:
            fight.fighters["p2"].code.switch()
        events = script(fight, 20, p1={0: FighterInput(dx=1, b=True)})
        hits = of(events, "hit", "logical")
        assert [(e.kind, e.error) for e in hits] == [("logical", qec.Y)], crouching
        assert fight.fighters["p2"].health == 100 - LOGICAL_DAMAGE - TRIO.moves["throw"].bonus
        assert fight.fighters["p2"].action == "knockdown"


def test_the_cycle_repairs_between_spaced_hits():
    fight = new()
    events = script(fight, 200, p1={0: A, 130: A})
    assert of(events, "logical") == []
    assert len(of(events, "hit")) == 2
    corrected = of(events, "corrected")
    assert [e.player for e in corrected] == ["p2"]
    assert fight.fighters["p2"].health == 100 - 2 * JAB.chip


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
    assert fight.fighters["p1"].health == fight.fighters["p2"].health == 97
    # both moves count as having connected, and both fighters are stunned
    assert fight.fighters["p1"].action == fight.fighters["p2"].action == "hitstun"


def test_a_downed_fighter_cannot_be_hit():
    SWEEP = TRIO.moves["crouch.B"]
    fight = new()
    p2 = fight.fighters["p2"]
    p2.take_hit(replace(SWEEP, chip=0, error=qec.X, bonus=0), 1)
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
    p2.take_hit(replace(TRIO.moves["crouch.B"], chip=0, error=qec.X, bonus=0), 1)
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
        broken = bool(of(events, "logical"))
        inp = A if not broken and (i == 0 or fight.hitstop > 0) else IDLE   # A on every hitstop frame
        events += fight.step({"p1": inp, "p2": IDLE})
    hits = of(events, "hit", "logical")
    assert [e.kind for e in hits] == ["hit", "logical"]         # TRIO breaks on the second jab
    assert fight.fighters["p2"].health == 100 - 3 - 22


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
    fight.fighters["p2"].code.switch()
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
    assert [(e.kind, e.player, e.error) for e in hits] == [("hit", "p2", qec.X)]
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


def test_projectiles_are_too_slow_to_tunnel():
    # collisions are overlap-only after each move (see Fight._move_shots)
    for char in CHARACTERS.values():
        for move in char.moves.values():
            if move.projectile is not None:
                assert move.projectile.speed * 2 < move.projectile.box.w + 16


# --- landing shockwave ----------------------------------------------------------------

SHOCK_DIVE = replace(
    TRIO.moves["air.X"], landing=Box(-70, 0, 140, 16), landing_error=qec.Z,
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
    assert [(e.kind, e.player, e.error) for e in of(events, "hit", "logical")] == [
        ("logical", "p2", qec.Z),       # Z against a |000> stander
    ]
    assert p2.health == 100 - LOGICAL_DAMAGE - SHOCK_DIVE.bonus


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
    fight.fighters["p2"].health = 3
    events = script(fight, 20, p1={0: A})
    assert kinds(events)[-1] == "ko" and kinds(events).count("ko") == 1
    assert fight.over and fight.winner == "p1"
    assert fight.fighters["p2"].health == 0
    assert fight.step({"p1": A, "p2": A}) == []         # once over, nothing happens
    assert fight.frames_left == ROUND_FRAMES - JAB_HIT_STEP - 1     # the clock stopped at the KO


def test_a_double_ko_is_a_draw():
    fight = new()
    fight.fighters["p1"].health = fight.fighters["p2"].health = 3
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
    fight.fighters["p2"].health = 3
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
    assert Event("switch", "p2") in events
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
        state = [(f.x, f.y, f.health, f.action, sorted(f.code.flipped), f.code.basis)
                 for f in fight.fighters.values()]
        results.append((events, state, fight.frames_left, fight.over, fight.winner))
    assert results[0] == results[1]
    assert any(e.kind in ("hit", "logical") for e in results[0][0])      # the run did fight


def test_a_jab_connects_at_the_closest_spacing():
    # Walked all the way in, the push box holds the fighters BODY_WIDTH apart: a jab
    # (either side, standing or crouching rival) must still reach.
    for crouching in (False, True):
        for attacker, rival in (("p1", "p2"), ("p2", "p1")):
            fight = new(gap=200.0)
            for _ in range(120):
                fight.step({"p1": FighterInput(dx=1), "p2": FighterInput(dx=-1)})
            assert abs(fight.fighters["p2"].x - fight.fighters["p1"].x) == BODY_WIDTH
            if crouching:
                fight.fighters[rival].code.switch()
            events = script(fight, 20, **{attacker: {0: A}})
            assert [e.player for e in of(events, "hit", "logical")] == [rival], (attacker, crouching)
