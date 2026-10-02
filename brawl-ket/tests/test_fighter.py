from dataclasses import replace
from types import MappingProxyType

from brawl_ket import shor
from brawl_ket.config import (
    BUFFER_FRAMES,
    CHAIN_MAX,
    FLOOR_Y,
    LOGICAL_DAMAGE,
    STAGE_LEFT,
    THROW_RANGE,
)
from brawl_ket.fighter import IDLE, Fighter, FighterInput
from brawl_ket.moves import TRIO, Box

JAB = TRIO.moves["stand.A"]
LOW_JAB = TRIO.moves["crouch.A"]
SWEEP = TRIO.moves["crouch.B"]
PHOTON = TRIO.moves["stand.X"]
HEAVY = TRIO.moves["stand.B"]
JAB_TOTAL = JAB.startup + JAB.active + JAB.recovery

FAR = 500.0   # a rival far to the right of a fighter at x=300


def make(x=300.0, facing=1):
    return Fighter(TRIO, x, facing)


def run(f, inp=IDLE, n=1, rival_x=FAR):
    """Step n frames with the same input; return all events, in order."""
    events = []
    for _ in range(n):
        events.extend(f.step(inp, rival_x))
    return events


def names(events):
    return [name for name, _ in events]


def start_jab(f):
    ev = run(f, FighterInput(a=True))
    assert ("attack", {"slot": "stand.A"}) in ev
    return ev


def tap(btn):
    return FighterInput(**{btn: True})


def test_walks_and_is_clamped_to_the_stage():
    f = make()
    run(f, FighterInput(dx=-1), 200)
    assert f.x == STAGE_LEFT
    assert f.action == "walk"


def test_facing_turns_towards_the_rival_on_the_ground():
    f = make(facing=1)
    run(f, IDLE, 1, rival_x=100)
    assert f.facing == -1
    run(f, IDLE, 1, rival_x=500)
    assert f.facing == 1


def test_jump_arcs_and_lands():
    f = make()
    ys, events = [], []
    events += f.step(FighterInput(up=True), FAR)
    ys.append(f.y)
    assert f.action == "jump" and f.stance == "air"
    for _ in range(59):
        events += f.step(IDLE, FAR)
        ys.append(f.y)
    assert max(ys) > 20
    assert ys.index(max(ys)) > 0
    assert ys[1] > ys[0]                # rises
    assert all(y >= 0 for y in ys)
    assert f.y == 0 and f.action == "idle" and f.stance == "stand"
    assert names(events).count("land") == 1
    # it lands well inside 60 frames
    assert ys[-5:] == [0.0] * 5


def test_the_jump_is_high_and_still_short():
    f = make()
    f.step(FighterInput(up=True), FAR)
    ys = [f.y]
    while not (f.y == 0 and len(ys) > 3):
        f.step(IDLE, FAR)
        ys.append(f.y)
    assert 130 <= max(ys) <= 150        # the apex (jump_vy 12, gravity 0.5): about 144 px
    assert 44 <= len(ys) <= 52          # the airtime: about 48 frames


def test_jump_keeps_horizontal_speed_from_dx():
    f = make()
    run(f, FighterInput(up=True, dx=1))
    assert f.vx == TRIO.walk
    x0 = f.x
    run(f, FighterInput(), 5)
    assert f.x > x0


def test_down_in_the_air_does_not_crouch():
    f = make()
    run(f, FighterInput(up=True))
    run(f, FighterInput(down=True), 5)
    assert not f.crouching and f.stance == "air"


def test_fighter_step_does_not_tick_the_code():
    f = make()
    run(f, IDLE, 30)
    assert f.code.timer == 0


def test_a_press_starts_a_jab_and_it_runs_its_frames():
    f = make()
    ev = start_jab(f)
    assert names(ev) == ["attack"]
    phases = [f.phase]
    for _ in range(JAB_TOTAL - 1):
        run(f)
        phases.append(f.phase)
    assert phases == (
        ["startup"] * JAB.startup + ["active"] * JAB.active + ["recovery"] * JAB.recovery
    )
    assert phases == ["startup"] * 4 + ["active"] * 3 + ["recovery"] * 8
    run(f)
    assert f.action == "idle" and f.phase is None and f.move is None


def test_buffered_press_comes_out_when_free():
    f = make()
    start_jab(f)                       # step 1
    run(f, IDLE, JAB_TOTAL - 4)        # through step 12
    run(f, tap("a"))                   # step 13: 3 frames before the end of recovery
    assert f.phase == "recovery"
    run(f, IDLE, 2)                    # steps 14, 15: still recovering
    assert f.phase == "recovery"
    ev = run(f)                        # step 16: the first free frame
    assert ev == [("attack", {"slot": "stand.A"})]
    assert f.phase == "startup" and f.frame == 0 and f.chain == 1


def test_buffer_presses_only_buffers():
    f = make()
    f.buffer_presses(FighterInput(a=True, x=True, dx=1, up=True))
    assert [(p.button, p.age) for p in f.buffer] == [("a", 0), ("x", 0)]
    assert (f.x, f.y, f.frame, f.action) == (300.0, 0.0, 0, "idle")
    f.buffer_presses(IDLE)
    assert [p.age for p in f.buffer] == [0, 0]          # nothing ages
    assert "attack" in names(run(f))                    # and the press comes out later


def test_a_stale_buffered_press_is_dropped():
    f = make()
    start_jab(f)                       # step 1
    run(f, IDLE, 3)                    # steps 2..4
    run(f, tap("a"))                   # step 5, ttl BUFFER_FRAMES
    run(f, IDLE, BUFFER_FRAMES - 2)    # steps 6..9: still buffered
    assert len(f.buffer) == 1
    run(f, IDLE, 1)                    # step 10 was its last chance to come out
    assert f.buffer == []
    ev = run(f, IDLE, JAB_TOTAL)
    assert "attack" not in names(ev)


def test_newest_buffered_press_wins():
    f = make()
    start_jab(f)                       # step 1
    run(f, IDLE, JAB_TOTAL - 4)        # through step 12
    assert run(f, tap("a")) == []      # step 13
    assert run(f, tap("b")) == []      # step 14
    run(f)                             # step 15
    ev = run(f)                        # step 16: both are buffered, B is newer
    assert ev == [("attack", {"slot": "stand.B"})]
    assert f.buffer == []              # starting a move clears the older press too
    assert run(f, IDLE, JAB_TOTAL + 20) == []


def test_crouching_buttons_use_crouch_slots():
    f = make()
    run(f, FighterInput(down=True))
    assert f.stance == "crouch"
    ev = run(f, FighterInput(down=True, a=True))
    assert ev == [("attack", {"slot": "crouch.A"})]
    assert f.slot == "crouch.A" and f.move is LOW_JAB
    # a crouch attack ends back in crouch
    run(f, FighterInput(down=True), LOW_JAB.startup + LOW_JAB.active + LOW_JAB.recovery)
    assert f.action == "crouch" and f.move is None


def test_up_and_down_together_is_a_jump_not_a_crouch():
    f = make()
    run(f, FighterInput(down=True, up=True))
    assert f.action == "jump" and not f.crouching


def test_releasing_down_plus_a_from_crouch_is_a_standing_attack_at_once():
    f = make()
    run(f, FighterInput(down=True))
    assert f.stance == "crouch"
    ev = run(f, tap("a"))                            # down released this frame
    assert ev == [("attack", {"slot": "stand.A"})]


def test_standing_buttons_use_stand_slots():
    for btn, slot in (("a", "stand.A"), ("b", "stand.B"), ("x", "stand.X")):
        f = make()
        assert run(f, tap(btn)) == [("attack", {"slot": slot})]


def test_b_up_close_towards_the_rival_is_a_throw():
    f = make(300, 1)
    ev = run(f, FighterInput(dx=1, b=True), rival_x=300 + THROW_RANGE)
    assert ev == [("attack", {"slot": "throw"})]
    assert f.move is TRIO.moves["throw"]


def test_b_far_from_the_rival_is_the_standing_heavy():
    f = make(300, 1)
    ev = run(f, FighterInput(dx=1, b=True), rival_x=FAR)
    assert ev == [("attack", {"slot": "stand.B"})]


def test_b_close_but_not_pushing_towards_is_the_standing_heavy():
    f = make(300, 1)
    assert run(f, FighterInput(dx=0, b=True), rival_x=320) == [("attack", {"slot": "stand.B"})]
    f = make(300, 1)
    assert run(f, FighterInput(dx=-1, b=True), rival_x=320) == [("attack", {"slot": "stand.B"})]


def test_throw_works_facing_left():
    f = make(300, -1)
    ev = run(f, FighterInput(dx=-1, b=True), rival_x=300 - THROW_RANGE)
    assert ev == [("attack", {"slot": "throw"})]


def test_ground_attacks_stand_still_and_lunge_only_when_active():
    f = make()
    run(f, FighterInput(down=True))         # now in crouch
    run(f, FighterInput(down=True, x=True))
    assert f.move is TRIO.moves["crouch.X"]
    x0 = f.x
    run(f, FighterInput(down=True), 3)      # startup: no lunge
    assert f.x == x0
    run(f, FighterInput(down=True), 6)      # into the active frames (startup 8)
    assert f.phase == "active"
    assert f.vx == 5.0 * f.facing
    x1 = f.x
    run(f, FighterInput(down=True), 3)
    assert f.x > x1


def test_take_hit_chips_or_logical():
    f = make()
    h0 = f.health
    assert f.take_hit(JAB, 1) == shor.FLIPPED
    assert f.health == h0 - JAB.chip
    assert f.code.x_cells == {(shor.HIGH, shor.A_COL)}
    assert f.take_hit(JAB, 1) == shor.CANCEL          # XX = I: chip, no refund
    assert f.health == h0 - 2 * JAB.chip
    assert f.code.lights == 0
    assert f.take_hit(JAB, 1) == shor.FLIPPED
    assert f.take_hit(HEAVY, 1) == shor.LOGICAL       # A then B at one height
    assert f.health == h0 - 3 * JAB.chip - LOGICAL_DAMAGE - HEAVY.bonus
    assert f.code.lights == 0
    g = make()
    assert g.take_hit(LOW_JAB, 1) == shor.FLIPPED     # any lone hit is correctable
    assert g.health == g.char.health - LOW_JAB.chip


def test_logical_damage_includes_the_move_bonus_and_health_clamps():
    heavy = TRIO.moves["stand.B"]
    f = make()
    f.take_hit(JAB, 1)                      # flipped
    assert f.take_hit(heavy, 1) == shor.LOGICAL
    assert f.health == 100 - JAB.chip - LOGICAL_DAMAGE - heavy.bonus
    f.health = 5
    f.take_hit(heavy, 1)
    assert f.health == 0


def test_take_hit_interrupts_a_move_and_stuns():
    f = make()
    start_jab(f)
    run(f, tap("b"))                                # something sits in the buffer
    assert f.buffer
    f.take_hit(JAB, -1)
    assert f.move is None and f.slot is None and f.phase is None
    assert f.buffer == []
    assert f.action == "hitstun" and f.stun == JAB.hitstun
    assert f.vx == JAB.knockback * -1
    x0 = f.x
    run(f, FighterInput(dx=1, up=True), JAB.hitstun - 1)   # direction inputs are ignored
    assert f.action == "hitstun" and f.y == 0 and f.stun == 1
    assert f.x < x0                                  # knocked back to the left
    assert abs(f.vx) < abs(JAB.knockback)            # decaying
    ev = run(f, FighterInput(dx=1, up=True))         # the last inert step
    assert f.action == "idle" and f.stun == 0 and names(ev) == []
    assert f.y == 0 and f.vx == 0


def test_stun_is_inert_for_exactly_its_value_and_acts_on_the_next_step():
    f = make()
    f.take_hit(JAB, 1)
    n = JAB.hitstun
    held = FighterInput(dx=1)
    run(f, held, n)                                  # N inert steps
    assert f.action == "idle" and f.vx == 0          # not walking yet
    run(f, held)                                     # step N+1 acts
    assert f.action == "walk" and f.vx == TRIO.walk


def test_knockdown_is_inert_for_forty_steps():
    f = make()
    f.take_hit(SWEEP, 1)
    assert f.action == "knockdown" and f.stun == 40
    run(f, IDLE, 39)
    assert f.action == "knockdown"
    run(f, FighterInput(dx=1))                       # step 40: inert
    assert f.action == "idle" and f.vx == 0
    run(f, FighterInput(dx=1))                       # step 41: walks
    assert f.action == "walk"


def test_a_press_in_the_last_frames_of_stun_comes_out_on_the_first_free_frame():
    f = make()
    f.take_hit(JAB, 1)
    n = JAB.hitstun
    run(f, IDLE, n - 3)
    assert run(f, tap("a")) == []                    # step N-2, buffered during stun
    assert len(f.buffer) == 1
    assert run(f, IDLE, 2) == []                     # steps N-1, N: still inert
    assert f.action == "idle"
    assert run(f) == [("attack", {"slot": "stand.A"})]   # step N+1


def test_an_early_press_in_stun_expires():
    f = make()
    f.take_hit(JAB, 1)
    run(f, tap("a"))                                 # step 1 of 16
    ev = run(f, IDLE, JAB.hitstun + 5)
    assert "attack" not in names(ev)
    assert f.buffer == []


def test_hit_while_crouched_recovers_to_crouch():
    f = make()
    run(f, FighterInput(down=True))
    f.take_hit(SWEEP, 1)
    run(f, FighterInput(down=True), 40)
    assert f.action == "crouch"


def test_photon_emits_a_projectile_on_its_first_active_frame():
    f = make()
    ev = run(f, tap("x"))
    assert ev == [("attack", {"slot": "stand.X"})]
    seen = []
    for i in range(PHOTON.startup + PHOTON.active + PHOTON.recovery):
        ev = run(f)
        if ev:
            seen.append((i + 2, ev, f.phase))      # i+2 = step number
    assert seen == [(PHOTON.startup + 1, [("projectile", {"move": PHOTON})], "active")]


def test_reencode_move_repairs_on_its_first_active_frame():
    reencode = replace(
        JAB, name="re-encode", kind="reencode", hitbox=None, startup=2, active=2, recovery=2,
    )
    char = replace(TRIO, moves=MappingProxyType({**TRIO.moves, "stand.X": reencode}))
    f = Fighter(char, 300, 1)
    f.code.apply_x(shor.HIGH, shor.A_COL)
    ev = run(f, tap("x"))
    assert ev == [("attack", {"slot": "stand.X"})]
    ev = run(f, IDLE, 2)                           # steps 2, 3: step 3 is the first active frame
    assert ev == [("reencode", {"repaired": True})]
    assert f.code.lights == 0
    assert run(f, IDLE, 3) == []                   # not again on the later active frame


def test_world_box_mirrors_with_facing():
    box = Box(14, 70, 30, 14)
    right = make(300, 1)
    assert right.world_box(box) == (314, FLOOR_Y - 84, 30, 14)
    left = make(300, -1)
    assert left.world_box(box) == (300 - 14 - 30, FLOOR_Y - 84, 30, 14)
    right.y = 10
    assert right.world_box(box) == (314, FLOOR_Y - 94, 30, 14)


def test_hurtbox_follows_the_stance():
    f = make()
    assert f.hurtbox == f.world_box(TRIO.hurt_stand)
    run(f, FighterInput(down=True))
    assert f.hurtbox == f.world_box(TRIO.hurt_crouch)
    assert f.hurtbox[1] > make().hurtbox[1]          # lower, so a larger screen y


def test_cooldown_blocks_a_slot_until_it_expires():
    jab = replace(JAB, cooldown=30)
    char = replace(TRIO, moves=MappingProxyType({**TRIO.moves, "stand.A": jab}))
    f = Fighter(char, 300, 1)
    run(f, tap("a"))                                 # step 1
    assert f.cooldowns["stand.A"] == 30
    run(f, IDLE, JAB_TOTAL)                          # move over, still cooling down
    assert f.action == "idle"
    ev = run(f, tap("a"))                            # step 17
    assert "attack" not in names(ev) and f.action == "idle"
    ev = run(f, IDLE, 12)                            # steps 18..29
    assert "attack" not in names(ev)
    # the cooldown reaches 0 on step 31; a press buffered at step 30 comes out then
    ev = run(f, tap("a"))                            # step 30
    assert "attack" not in names(ev)
    ev = run(f)                                      # step 31
    assert ev == [("attack", {"slot": "stand.A"})]


def test_other_slots_are_not_blocked_by_a_cooldown():
    jab = replace(JAB, cooldown=30)
    char = replace(TRIO, moves=MappingProxyType({**TRIO.moves, "stand.A": jab}))
    f = Fighter(char, 300, 1)
    run(f, tap("a"))
    run(f, IDLE, JAB_TOTAL)
    assert run(f, tap("b")) == [("attack", {"slot": "stand.B"})]


def jump_until(f, pred, limit=80, rival_x=FAR):
    run(f, FighterInput(up=True), rival_x=rival_x)
    for _ in range(limit):
        if pred(f):
            return
        run(f, rival_x=rival_x)
    raise AssertionError("never reached the wanted airborne state")


def test_dive_dives_and_lands_into_its_recovery():
    f = make()
    dive = TRIO.moves["air.X"]
    jump_until(f, lambda f: f.y > 40)
    ev = run(f, tap("x"))
    assert ev == [("attack", {"slot": "air.X"})]
    assert f.move is dive and f.stance == "air"
    x0 = f.x
    landed_at = None
    for i in range(60):
        ev = run(f)
        if f.phase == "active" and f.y > 0:
            assert f.vx == dive.dive[0] * f.facing and f.vy == -dive.dive[1]
        if "land" in names(ev):
            landed_at = i
            break
    assert landed_at is not None
    assert f.x > x0
    assert f.y == 0 and f.vx == 0 and f.vy == 0
    assert f.phase == "recovery" and f.action == "attack"
    for _ in range(dive.recovery):
        assert f.action == "attack"
        run(f)
    assert f.action == "idle"
    assert f.move is None


def test_dive_keeps_its_speed_when_facing_left():
    f = make(300, -1)
    jump_until(f, lambda f: f.y > 40, rival_x=0)
    run(f, tap("x"), rival_x=0)
    run(f, IDLE, TRIO.moves["air.X"].startup, rival_x=0)
    assert f.facing == -1 and f.vx == -TRIO.moves["air.X"].dive[0]


def test_an_air_jab_is_cancelled_by_landing():
    f = make()
    # jump, then fall until close to the floor
    jump_until(f, lambda f: f.vy < 0 and 0 < f.y < 45)
    ev = run(f, tap("a"))
    assert ev == [("attack", {"slot": "air.A"})]
    assert f.action == "attack"
    ev = []
    for _ in range(20):
        ev = run(f)
        if "land" in names(ev):
            break
    assert "land" in names(ev)
    assert f.action == "idle" and f.move is None and f.phase is None
    assert f.y == 0 and f.vx == 0


def test_air_slots_are_used_while_airborne():
    f = make()
    jump_until(f, lambda f: f.y > 30)
    assert run(f, tap("b")) == [("attack", {"slot": "air.B"})]


def test_every_air_attack_is_reachable_from_the_apex_and_ends_on_the_floor():
    for slot, button in (("air.A", "a"), ("air.B", "b"), ("air.X", "x")):
        f = make()
        jump_until(f, lambda f: f.vy <= 0 and f.y > 120)        # at the top of the higher jump
        assert run(f, tap(button)) == [("attack", {"slot": slot})], slot
        events = []
        for _ in range(80):
            events += run(f)
            if "land" in names(events):
                break
        assert "land" in names(events), slot
        assert f.y == 0, slot


def test_can_cancel_requires_a_hit_the_right_slot_and_chain_room():
    f = make()
    start_jab(f)
    run(f, IDLE, JAB.startup - 1)
    assert f.phase == "startup" and not f.can_cancel("stand.A")      # not yet active
    run(f)
    assert f.phase == "active"
    assert not f.can_cancel("stand.A")                               # has not hit
    f.move_hit = True
    assert f.can_cancel("stand.A") and f.can_cancel("stand.B") and f.can_cancel("crouch.A")
    assert not f.can_cancel("stand.X")                               # not in cancels
    f.chain = CHAIN_MAX
    assert not f.can_cancel("stand.A")
    f.chain = CHAIN_MAX - 1
    assert f.can_cancel("stand.A")
    g = make()
    assert not g.can_cancel("stand.A")                               # no move at all


def test_cancelling_chains_up_to_the_cap():
    f = make()
    start_jab(f)
    run(f, IDLE, JAB.startup - 1)
    for expected in range(2, CHAIN_MAX + 1):
        f.move_hit = True
        ev = run(f, tap("a"))
        assert ev == [("attack", {"slot": "stand.A"})], expected
        assert f.chain == expected and not f.move_hit and f.frame == 0
        run(f, IDLE, JAB.startup)                    # on to the next move's active frames
    f.move_hit = True
    ev = run(f, tap("a"))
    assert "attack" not in names(ev)
    assert f.chain == CHAIN_MAX


def test_a_move_started_from_neutral_resets_the_chain():
    f = make()
    start_jab(f)
    f.chain = CHAIN_MAX
    run(f, IDLE, JAB_TOTAL)
    start_jab(f)
    assert f.chain == 1


def test_cancel_with_the_press_held_and_move_hit_set_on_the_first_active_frame():
    f = make()
    start_jab(f)                                      # step 1; the player now holds A
    cancelled_at = None
    for step in range(2, 1 + JAB.active + JAB.recovery + JAB.startup):
        ev = f.step(tap("a"), FAR)
        if ("attack", {"slot": "stand.A"}) in ev:
            cancelled_at = step
            break
        if f.phase == "active" and not f.move_hit:
            f.move_hit = True                         # what the fight does when it connects
    assert cancelled_at == JAB.startup + 2            # the step after the first active frame
    assert f.chain == 2 and f.frame == 0 and not f.move_hit
    assert f.phase == "startup"
    assert f.buffer == []


def phases_of(f):
    """The phase on every step of the move that has just started, until it ends."""
    seen = [f.phase]
    while f.action == "attack":
        run(f)
        if f.action == "attack":
            seen.append(f.phase)
    return seen


def test_a_neutral_heavy_telegraphs_for_24_startup_frames():
    f = make()
    run(f, tap("b"))
    assert f.slot == "stand.B" and f.chain == 1
    assert f.startup == HEAVY.startup == 24
    assert phases_of(f) == (
        ["startup"] * 24 + ["active"] * HEAVY.active + ["recovery"] * HEAVY.recovery
    )


def test_a_heavy_cancelled_from_a_jab_that_hit_takes_8_startup_frames():
    f = make()
    start_jab(f)
    run(f, IDLE, JAB.startup)
    assert f.phase == "active"
    f.move_hit = True
    run(f, tap("b"))
    assert f.slot == "stand.B" and f.chain == 2 and f.frame == 0
    assert f.startup == HEAVY.chain_startup == 8
    assert phases_of(f) == (
        ["startup"] * 8 + ["active"] * HEAVY.active + ["recovery"] * HEAVY.recovery
    )


def test_the_chained_startup_is_forgotten_when_the_move_ends():
    f = make()
    start_jab(f)
    run(f, IDLE, JAB.startup)
    f.move_hit = True
    run(f, tap("b"))
    assert f.startup == 8
    run(f, IDLE, 8 + HEAVY.active + HEAVY.recovery)
    assert f.move is None
    run(f, tap("b"))                    # the next heavy starts from neutral again
    assert f.startup == 24


def test_the_sweep_telegraphs_from_neutral_and_chains_fast():
    sweep = TRIO.moves["crouch.B"]
    f = make()
    run(f, FighterInput(down=True, b=True))
    assert f.slot == "crouch.B" and f.startup == sweep.startup == 24
    g = make()
    run(g, FighterInput(down=True, a=True))
    run(g, FighterInput(down=True), LOW_JAB.startup)
    assert g.phase == "active"
    g.move_hit = True
    run(g, FighterInput(down=True, b=True))
    assert g.slot == "crouch.B" and g.startup == sweep.chain_startup == 9


def test_only_a_neutral_heavy_telegraphs_and_only_in_its_last_16_startup_frames():
    f = make()
    run(f, tap("b"))
    flags = [f.telegraphing]
    for _ in range(HEAVY.startup + HEAVY.active):
        run(f)
        flags.append(f.telegraphing)
    assert flags == [False] * (HEAVY.startup - 16) + [True] * 16 + [False] * (HEAVY.active + 1)
    j = make()                          # a jab never does
    run(j, tap("a"))
    assert not j.telegraphing
    c = make()                          # nor does a chained heavy
    start_jab(c)
    run(c, IDLE, JAB.startup)
    c.move_hit = True
    run(c, tap("b"))
    assert not any((run(c), c.telegraphing)[1] for _ in range(8))


def test_crouching_is_instant_and_has_no_switch():
    f = Fighter(TRIO, 200, 1)
    f.step(FighterInput(down=True), 400)
    assert f.crouching and f.stance == "crouch" and f.action == "crouch"
    f.step(FighterInput(), 400)
    assert not f.crouching and f.stance == "stand"


def test_down_a_from_standing_is_a_low_jab_at_once():
    f = Fighter(TRIO, 200, 1)
    f.step(FighterInput(down=True, a=True), 400)
    assert f.slot == "crouch.A"
