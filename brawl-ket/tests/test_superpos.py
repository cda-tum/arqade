"""Tests for SUPERposition (superpos.py, and the fight's and the fighter's part in it)."""

from __future__ import annotations

from dataclasses import replace

from brawl_ket import basis
from brawl_ket.fight import Fight
from brawl_ket.fighter import FighterInput
from brawl_ket.moves import CHARACTERS, ROBERT
from brawl_ket.superpos import FULL, Meter

Z, X = basis.Z_BASIS, basis.X_BASIS
A = FighterInput(a=True)
B = FighterInput(b=True)
DOS = CHARACTERS["DOS"]


def fight_of(a=ROBERT, b=ROBERT, gap: float = 50.0) -> Fight:
    fight = Fight({"p1": a, "p2": b}, seed=1)
    fight.fighters["p1"].x = 300.0
    fight.fighters["p2"].x = 300.0 + gap
    return fight


def until(fight: Fight, kind: str, first: dict | None = None, frames: int = 60) -> list:
    """Step once with `first`, then idle until an event of `kind` (or `frames` run out)."""
    events = fight.step(first or {})
    for _ in range(frames):
        if any(e.kind == kind for e in events):
            break
        events += fight.step({})
    return events


# --- the bar ---------------------------------------------------------------------------------


def test_a_half_takes_40_points_dealt_or_80_taken():
    assert FULL == 80
    m = Meter()
    assert m.fill == {Z: 0, X: 0} and not m.full
    assert m.dealt(Z, 39) == [] and m.share(Z) == 78 / 80
    assert m.dealt(Z, 1) == ["half"] and m.share(Z) == 1.0 and not m.full
    m.empty()
    assert m.taken(X, 40) == [] and m.share(X) == 0.5


def test_the_bar_is_full_only_with_both_halves_and_says_so_once():
    m = Meter()
    assert m.dealt(Z, 50) == ["half"]           # the overflow is lost
    assert m.fill[Z] == FULL
    assert m.dealt(Z, 10) == []                 # already full: nothing new
    assert m.dealt(X, 40) == ["half", "full"]
    assert m.full
    m.empty()
    assert m.fill == {Z: 0, X: 0} and not m.full


# --- filling in a fight ----------------------------------------------------------------------


def test_a_hit_fills_the_attackers_half_of_its_basis_and_the_hit_ones_at_half_rate():
    fight = fight_of()
    until(fight, "hit", {"p1": A})                  # green ROBERT jabs green ROBERT: 4
    assert fight.meters["p1"].fill == {Z: 8, X: 0}
    assert fight.meters["p2"].fill == {Z: 4, X: 0}


def test_the_half_is_the_attackers_basis_not_the_colour_of_the_hit():
    fight = fight_of()
    fight.fighters["p1"].basis = X                  # purple ROBERT's B is green: it hurts green p2
    until(fight, "hit", {"p1": B})
    assert fight.fighters["p2"].health == ROBERT.health - 8
    assert fight.meters["p1"].fill == {Z: 0, X: 16}
    assert fight.meters["p2"].fill == {Z: 8, X: 0}


def test_dos_fills_the_half_of_the_hits_colour():
    fight = fight_of(DOS, ROBERT, gap=60.0)
    fight.fighters["p2"].basis = X                  # DOS's B is purple: it hurts purple ROBERT
    until(fight, "hit", {"p1": B})
    dealt = ROBERT.health - fight.fighters["p2"].health
    assert dealt > 0
    assert fight.meters["p1"].fill == {Z: 0, X: 2 * dealt}


def test_a_blocked_hit_fills_nothing():
    fight = fight_of()
    fight.fighters["p2"].basis = X                  # a green jab bounces off purple
    events = until(fight, "block", {"p1": A})
    assert any(e.kind == "block" for e in events)
    assert fight.meters["p1"].fill == {Z: 0, X: 0} and fight.meters["p2"].fill == {Z: 0, X: 0}


def test_filling_a_half_and_the_bar_are_events():
    fight = fight_of()
    fight.meters["p1"].fill = {Z: FULL - 2, X: FULL}
    events = until(fight, "hit", {"p1": A})
    kinds = [(e.kind, e.player) for e in events if e.kind.startswith("super_")]
    assert kinds == [("super_half", "p1"), ("super_full", "p1")]
    assert fight.meters["p1"].full


def test_a_fight_can_be_handed_its_meters():
    meters = {"p1": Meter(), "p2": Meter()}
    meters["p1"].fill[Z] = 12
    fight = Fight({"p1": ROBERT, "p2": ROBERT}, seed=1, meters=meters)
    assert fight.meters is meters and fight.meters["p1"].fill[Z] == 12


# --- firing ------------------------------------------------------------------------------------

from types import MappingProxyType  # noqa: E402

from brawl_ket.basis import BOTH  # noqa: E402
from brawl_ket.config import SUPER_FREEZE  # noqa: E402
from brawl_ket.moves import ALICE_BOB, MID, Box, Move  # noqa: E402

AB = FighterInput(a=True, b=True)
# a plain test super: a big strike in front, both colours
TEST_SUPER = Move("TEST SUPER", 4, 4, 10, Box(14, 40, 60, 60), BOTH, MID,
                  damage=25, hitstun=30, knockback=3.0, knockdown=True, kind="super")
SUPER_ROBERT = replace(ROBERT, extra=MappingProxyType({"super": TEST_SUPER}))


def full(fight: Fight, key: str = "p1") -> None:
    fight.meters[key].fill = {Z: FULL, X: FULL}


def kinds(events: list) -> list[str]:
    return [e.kind for e in events]


def test_a_and_b_together_with_a_full_bar_fire_it_and_empty_the_bar():
    fight = fight_of(SUPER_ROBERT)
    full(fight)
    events = fight.step({"p1": AB})
    assert "super" in kinds(events) and fight.fighters["p1"].slot == "super"
    assert not fight.meters["p1"].full and fight.meters["p1"].fill == {Z: 0, X: 0}
    assert fight.freeze == SUPER_FREEZE and fight.supers == ["p1"]


def test_the_freeze_stops_everything_for_its_call():
    fight = fight_of(SUPER_ROBERT)
    full(fight)
    fight.fighters["p2"].vx = 2.0
    fight.step({"p1": AB})
    clock, frame, x = fight.frames_left, fight.fighters["p1"].frame, fight.fighters["p2"].x
    for _ in range(SUPER_FREEZE - 1):
        assert fight.step({"p2": FighterInput(dx=1)}) == []
    assert (fight.frames_left, fight.fighters["p1"].frame, fight.fighters["p2"].x) == (clock, frame, x)
    fight.step({})                                  # the last frame of the call
    assert fight.freeze == 0 and fight.supers == []
    fight.step({})
    assert fight.fighters["p1"].frame == frame + 1  # and on it goes


def test_a_then_b_two_frames_later_still_fires_but_three_is_a_jab():
    fight = fight_of(SUPER_ROBERT)
    full(fight)
    fight.step({"p1": A})
    fight.step({})
    assert "super" in kinds(fight.step({"p1": B}))
    fight = fight_of(SUPER_ROBERT)
    full(fight)
    fight.step({"p1": A})
    fight.step({})
    events = fight.step({})                         # a lone A waited 2 frames: now it's a jab
    assert fight.fighters["p1"].slot == "stand.A" and "super" not in kinds(events)


def test_without_a_full_bar_a_and_b_are_as_ever():
    fight = fight_of(SUPER_ROBERT)
    fight.step({"p1": A})
    assert fight.fighters["p1"].slot == "stand.A"   # at once, no waiting
    fight = fight_of(SUPER_ROBERT)
    events = fight.step({"p1": AB})
    assert "super" not in kinds(events) and fight.fighters["p1"].slot != "super"


def test_a_fighter_with_no_super_never_waits():
    fight = fight_of(replace(ROBERT, extra=MappingProxyType({})))
    full(fight)
    fight.step({"p1": A})
    assert fight.fighters["p1"].slot == "stand.A"


def test_not_from_the_air():
    fight = fight_of(SUPER_ROBERT)
    full(fight)
    fight.step({"p1": FighterInput(up=True)})
    events = fight.step({"p1": AB})
    assert "super" not in kinds(events) and fight.meters["p1"].full


def test_it_hurts_either_colour_and_fills_no_bar():
    for rival_basis in (Z, X):
        fight = fight_of(SUPER_ROBERT)
        full(fight)
        fight.fighters["p2"].basis = rival_basis
        until(fight, "hit", {"p1": AB}, frames=SUPER_FREEZE + 20)
        assert fight.fighters["p2"].health == ROBERT.health - 25
        assert fight.meters["p1"].fill == {Z: 0, X: 0} and fight.meters["p2"].fill == {Z: 0, X: 0}


def test_a_ko_by_a_super_is_marked():
    fight = fight_of(SUPER_ROBERT)
    full(fight)
    fight.fighters["p2"].health = 20
    until(fight, "ko", {"p1": AB}, frames=SUPER_FREEZE + 20)
    assert fight.over and fight.super_ko


def test_both_on_the_same_frame_freeze_one_after_the_other():
    fight = fight_of(SUPER_ROBERT, SUPER_ROBERT, gap=200.0)
    full(fight, "p1")
    full(fight, "p2")
    fight.step({"p1": AB, "p2": AB})
    assert fight.supers == ["p1", "p2"]
    for _ in range(SUPER_FREEZE):
        fight.step({})
    assert fight.supers == ["p2"] and fight.freeze == SUPER_FREEZE
    for _ in range(SUPER_FREEZE):
        fight.step({})
    assert fight.supers == [] and fight.freeze == 0


def test_bob_never_echoes_a_supers_a_and_b():
    pair = replace(ALICE_BOB, extra=MappingProxyType({**ALICE_BOB.extra, "super": TEST_SUPER}))
    fight = fight_of(pair, ROBERT, gap=300.0)
    full(fight)
    fight.step({"p1": A})
    fight.step({"p1": B})                           # A, then B a frame later
    assert fight.fighters["p1"].slot == "super"
    bob = fight.echoes["p1"]
    for _ in range(SUPER_FREEZE + 30):
        fight.step({})
        assert bob.action != "attack"


# --- DOS: BLUE SCREEN OF DEATH -------------------------------------------------------------------

from brawl_ket.config import CRASH_HOLD, CRASH_LEAP, CRASH_REACH  # noqa: E402
from brawl_ket.moves import BLUE_SCREEN, BSOD_HOLD, ERWIN  # noqa: E402

STARTUP = BLUE_SCREEN.startup


def bsod(rival=ROBERT, gap: float = 150.0) -> Fight:
    """DOS with a full bar fires; the call is skipped and the startup run."""
    fight = fight_of(DOS, rival, gap)
    full(fight)
    fight.step({"p1": AB})
    for _ in range(SUPER_FREEZE):
        fight.step({})
    return fight


def run(fight: Fight, frames: int, inp: dict | None = None) -> list:
    events = []
    for _ in range(frames):
        events += fight.step(inp or {})
    return events


def test_dos_has_it_and_it_is_both_colours():
    assert DOS.extra["super"] is BLUE_SCREEN
    assert BLUE_SCREEN.kind == "super" and BLUE_SCREEN.colour == BOTH and BLUE_SCREEN.name == "BLUE SCREEN OF DEATH"
    assert BLUE_SCREEN.crash is BSOD_HOLD and BSOD_HOLD.hold and BSOD_HOLD.damage == 0
    assert BLUE_SCREEN.seek == CRASH_LEAP and BSOD_HOLD.hitstun == CRASH_HOLD


def test_it_freezes_a_rival_on_the_ground_in_reach():
    fight = bsod(gap=150.0)
    events = run(fight, STARTUP)
    rival = fight.fighters["p2"]
    crash = [e for e in events if e.kind == "crash"]
    assert crash and crash[0].player == "p2"
    assert rival.action == "hitstun" and rival.glitch > 0 and rival.vx == 0.0
    assert rival.health == ROBERT.health                # the freeze itself does no damage


def test_then_he_comes_down_on_them_for_25_whatever_their_colour():
    for colour in (Z, X):
        fight = bsod(gap=150.0)
        fight.fighters["p2"].basis = colour
        events = run(fight, STARTUP + CRASH_LEAP + 20)     # (the hit's hitstop holds the landing back)
        rival = fight.fighters["p2"]
        assert rival.health == ROBERT.health - 25 and rival.action == "knockdown"
        assert rival.glitch == 0
        assert any(e.kind == "bsod_land" for e in events)


def test_he_lands_about_crash_leap_frames_after_the_crash():
    fight = bsod(gap=CRASH_REACH + 20)                  # nobody frozen, so no hit and no hitstop
    dos = fight.fighters["p1"]
    run(fight, STARTUP)
    landed = None
    for n in range(1, CRASH_LEAP + 10):
        if any(e.kind == "bsod_land" for e in fight.step({})):
            landed = n
            break
    assert landed is not None and CRASH_LEAP - 3 <= landed <= CRASH_LEAP + 1
    assert dos.phase == "recovery"


def test_a_rival_in_the_air_is_not_frozen_and_he_drops_where_he_stands():
    fight = fight_of(DOS, ROBERT, 150.0)
    full(fight)
    fight.step({"p1": AB})
    for _ in range(SUPER_FREEZE):
        fight.step({})
    fight.step({"p2": FighterInput(up=True)})           # up in its startup
    events = run(fight, STARTUP - 1)
    assert [e.player for e in events if e.kind == "crash"] == [None]
    x = fight.fighters["p1"].x
    run(fight, CRASH_LEAP + 4)
    assert fight.fighters["p1"].x == x


def test_a_rival_out_of_reach_is_not_frozen():
    fight = bsod(gap=CRASH_REACH + 20)
    events = run(fight, STARTUP + CRASH_LEAP + 4)
    assert [e.player for e in events if e.kind == "crash"] == [None]
    assert fight.fighters["p2"].health == ROBERT.health


def test_the_box_dodges_it():
    fight = fight_of(DOS, ERWIN, 150.0)
    fight.fighters["p2"].action = "boxed"
    fight.fighters["p2"].boxes = (450.0, 450.0)
    full(fight)
    fight.step({"p1": AB})
    for _ in range(SUPER_FREEZE):
        fight.step({})
    events = run(fight, STARTUP)
    assert [e.player for e in events if e.kind == "crash"] == [None]


def test_both_of_alice_and_bob_in_reach_are_frozen():
    fight = bsod(ALICE_BOB, gap=120.0)
    events = run(fight, STARTUP)
    assert [e.player for e in events if e.kind == "crash"] == ["p2", "p2"]
    assert fight.echoes["p2"].glitch > 0 and fight.fighters["p2"].glitch > 0


def test_the_glitch_runs_down_a_frame_at_a_time_and_a_hit_ends_it():
    fight = fight_of()
    rival = fight.fighters["p2"]
    rival.glitch = 3
    run(fight, 3)
    assert rival.glitch == 0
    rival.glitch = 30
    until(fight, "hit", {"p1": A})
    assert rival.glitch == 0


# --- part 2: the twists (lock, remote, hits, follow, warp, flank) ----------------------------------



def with_super(char, move):
    return replace(char, extra=MappingProxyType({**char.extra, "super": move}))


def fire(fight: Fight, key: str = "p1") -> None:
    """Fill the bar, fire, and sit out the call."""
    full(fight, key)
    fight.step({key: AB})
    for _ in range(SUPER_FREEZE):
        fight.step({})


# a remote strike that locks 4 frames before it lands
REMOTE = Move("REMOTE", 10, 4, 10, Box(-30, 0, 60, 300), BOTH, MID, damage=25, hitstun=30, knockback=0.0,
              knockdown=True, kind="super", lock=4, remote=True)


def test_a_lock_fixes_the_target_where_the_rival_stood_then():
    fight = fight_of(with_super(ROBERT, REMOTE), ROBERT, gap=200.0)
    fire(fight)
    events = run(fight, REMOTE.startup - REMOTE.lock)
    assert fight.fighters["p1"].target_x == 500.0
    assert [(e.kind, e.player, e.x) for e in events if e.kind == "lock"] == [("lock", "p1", 500.0)]


def test_a_remote_hitbox_lands_on_the_target_not_round_the_fighter():
    fight = fight_of(with_super(ROBERT, REMOTE), ROBERT, gap=200.0)
    fire(fight)
    run(fight, REMOTE.startup + 2)
    assert fight.fighters["p2"].health == ROBERT.health - 25


def test_who_moves_away_after_the_lock_is_missed():
    fight = fight_of(with_super(ROBERT, REMOTE), ROBERT, gap=200.0)
    fire(fight)
    run(fight, REMOTE.startup - REMOTE.lock)
    fight.fighters["p2"].x = 600.0
    run(fight, REMOTE.lock + 4)
    assert fight.fighters["p2"].health == ROBERT.health


def test_a_lock_with_a_range_misses_one_too_far_or_in_the_air():
    near = replace(REMOTE, lock=0, lock_range=100, lock_ground=True)
    fight = fight_of(with_super(ROBERT, near), ROBERT, gap=150.0)
    fire(fight)
    events = run(fight, near.startup + 4)
    assert fight.fighters["p1"].target_x is None and "lock_miss" in kinds(events)
    assert fight.fighters["p2"].health == ROBERT.health
    fight = fight_of(with_super(ROBERT, near), ROBERT, gap=80.0)
    fire(fight)
    fight.step({"p2": FighterInput(up=True)})
    run(fight, near.startup + 4)
    assert fight.fighters["p2"].health == ROBERT.health


def test_hits_caps_a_repeating_move():
    ROLL = Move("ROLL", 2, 60, 1, Box(-40, 0, 120, 120), BOTH, MID, damage=4, hitstun=16, knockback=0.0,
                kind="super", hit_every=6, hits=3)
    fight = fight_of(with_super(ROBERT, ROLL), ROBERT, gap=60.0)
    fire(fight)
    run(fight, 80)
    assert fight.fighters["p2"].health == ROBERT.health - 12
    assert fight.fighters["p1"].hit_count == 3 or fight.fighters["p1"].move is None


def test_a_follow_up_starts_when_the_hits_are_spent_and_keeps_the_target():
    after = Move("AFTER", 2, 4, 10, Box(-30, 0, 60, 300), BOTH, MID, damage=9, hitstun=30, knockback=0.0,
                 knockdown=True, kind="super", remote=True)
    first = replace(REMOTE, damage=4, hitstun=16, knockdown=False, active=40, hit_every=6, hits=4, follow=after)
    fight = fight_of(with_super(ROBERT, first), ROBERT, gap=200.0)
    fire(fight)
    run(fight, first.startup + 40 + 6 * 10)        # (every hit's hitstop holds the frames back)
    assert fight.fighters["p2"].health == ROBERT.health - 4 * 4 - 9
    assert fight.fighters["p1"].move in (after, None)


def test_a_warp_starts_the_follow_up_in_front_of_the_target():
    after = Move("WARPED", 2, 4, 10, Box(10, 20, 60, 90), BOTH, MID, damage=9, hitstun=30, knockback=0.0,
                 knockdown=True, kind="super", warp=40)
    first = replace(REMOTE, remote=False, follow=after)     # (it hits nothing: no hitstop)
    fight = fight_of(with_super(ROBERT, first), ROBERT, gap=200.0)
    fire(fight)
    run(fight, first.startup + first.active)
    assert abs(fight.fighters["p1"].x - 460.0) <= 3 and fight.fighters["p1"].move is after   # (the push box nudges)


def test_a_lock_hold_holds_the_rival_and_a_flank_puts_the_pair_either_side():
    hold = Move("HELD", 0, 1, 1, None, BOTH, MID, damage=0, hitstun=70, knockback=0.0, hold=True)
    pad = replace(REMOTE, lock=0, lock_range=100, lock_ground=True, lock_hold=hold, flank=50, remote=False)
    fight = fight_of(with_super(ALICE_BOB, pad), ROBERT, gap=90.0)
    fire(fight)
    run(fight, pad.startup)
    rival, alice, bob = fight.fighters["p2"], fight.fighters["p1"], fight.echoes["p1"]
    assert rival.action == "hitstun" and rival.stun > 60
    assert (alice.x, bob.x) == (390.0 - 50, 390.0 + 50) and bob.anchored


def test_a_decohered_bob_comes_back_for_their_super():
    fight = fight_of(with_super(ALICE_BOB, REMOTE), ROBERT, gap=200.0)
    fight.echoes["p1"].decohere()
    full(fight)
    events = fight.step({"p1": AB})
    assert fight.echoes["p1"].here and "recohere" in kinds(events)


# --- part 2: the six supers --------------------------------------------------------------------------

from brawl_ket.config import FLOOR_Y  # noqa: E402
from brawl_ket.moves import (  # noqa: E402
    BLOCH_SPHERE,
    COHERENT_BEAM,
    DILUTION_FRIDGE,
    H_UPPERCUT,
    NINE_LIVES,
    NINE_SWIPE,
    ONE_TIME_PAD,
    WAVE_COLLAPSE,
)

ALL_SUPERS = {"ROBERT": "BLOCH SPHERE", "BOHR": "WAVEFUNCTION COLLAPSE", "PHOEBE": "COHERENT BEAM",
              "ERWIN": "NINE LIVES", "DOS": "BLUE SCREEN OF DEATH", "M-CUTIE": "DILUTION FRIDGE",
              "ALICE & BOB": "ONE-TIME PAD"}


def test_everyone_has_their_super_and_it_is_both_colours():
    for name, sup in ALL_SUPERS.items():
        m = CHARACTERS[name].extra["super"]
        assert m.name == sup and m.kind == "super" and m.colour == BOTH, name
        part = m
        while part is not None:                     # its follow-ups too
            assert part.kind == "super" and part.colour == BOTH, part.name
            part = part.follow


def total(m) -> int:
    n = 0
    while m is not None:
        n += m.damage * (m.hits or 1)
        m = m.follow
    return n


def test_each_is_about_25_in_all():
    for name in ALL_SUPERS:
        m = CHARACTERS[name].extra["super"]
        if m.name == "DILUTION FRIDGE":
            assert total(m) == 25                   # the fridge and the frost don't both land on one rival
        else:
            assert total(m) == 25, name


def landed(name: str, rival=ROBERT, gap=60.0, frames=200, setup=None) -> Fight:
    fight = fight_of(CHARACTERS[name], rival, gap)
    if setup:
        setup(fight)
    fire(fight)
    run(fight, frames)
    return fight


def test_bloch_sphere_rolls_in_for_4_hits_then_the_uppercut_and_he_switches():
    fight = landed("ROBERT", gap=200.0)
    assert fight.fighters["p2"].health == ROBERT.health - 25
    assert fight.fighters["p1"].basis == X


def test_bloch_sphere_rolls_six_px_a_frame_and_a_jump_clears_it():
    fight = fight_of(CHARACTERS["ROBERT"], ROBERT, 300.0)
    fire(fight)
    x = fight.fighters["p1"].x
    run(fight, BLOCH_SPHERE.startup + 5)               # its first active frame is the startup's last
    assert fight.fighters["p1"].x == x + 6 * 6
    fight = fight_of(CHARACTERS["ROBERT"], ROBERT, 150.0)
    fire(fight)
    run(fight, BLOCH_SPHERE.startup + 8)
    fight.step({"p2": FighterInput(up=True)})
    run(fight, 14)
    assert fight.fighters["p2"].health >= ROBERT.health - H_UPPERCUT.damage    # the roll passed under


def test_wavefunction_collapse_falls_where_they_stood_at_the_lock():
    fight = landed("BOHR", gap=300.0)
    assert fight.fighters["p2"].health == ROBERT.health - 25
    fight = fight_of(CHARACTERS["BOHR"], ROBERT, 300.0)
    fire(fight)
    run(fight, WAVE_COLLAPSE.startup - WAVE_COLLAPSE.lock + 1)
    fight.fighters["p2"].x -= 120                   # walked off the ring (towards him: the stage ends behind)
    run(fight, 40)
    assert fight.fighters["p2"].health == ROBERT.health


def test_coherent_beam_hits_five_times_crouching_or_not_and_its_top_is_110_px():
    fight = landed("PHOEBE", gap=300.0, setup=lambda f: setattr(f.fighters["p2"], "crouching", True))
    assert fight.fighters["p2"].health == ROBERT.health - 25
    phoebe = fight.fighters["p1"]
    _, top, _, h = phoebe.world_box(COHERENT_BEAM.hitbox)
    assert top + h == FLOOR_Y and h == 110


def test_nine_lives_eight_pounces_then_the_swipe_from_right_in_front():
    fight = landed("ERWIN", gap=120.0)
    assert fight.fighters["p2"].health == ROBERT.health - 25
    fight = fight_of(CHARACTERS["ERWIN"], ROBERT, 120.0)
    fire(fight)
    for _ in range(200):                            # (the pounces' hitstop holds the frames back)
        if fight.fighters["p1"].move is NINE_SWIPE:
            break
        fight.step({})
    assert fight.fighters["p1"].move is NINE_SWIPE
    assert abs(fight.fighters["p1"].x - (420.0 - NINE_SWIPE.warp)) <= 4     # (the push box nudges)


def test_nine_lives_misses_a_rival_out_of_its_reach():
    fight = landed("ERWIN", gap=NINE_LIVES.lock_range + 30.0)
    assert fight.fighters["p2"].health == ROBERT.health


def test_dilution_fridge_crushes_who_stays_and_frosts_who_got_out_but_not_who_jumps():
    fight = landed("M-CUTIE", gap=300.0)
    assert fight.fighters["p2"].health == ROBERT.health - 20
    fight = fight_of(CHARACTERS["M-CUTIE"], ROBERT, 300.0)
    fire(fight)
    run(fight, DILUTION_FRIDGE.startup - DILUTION_FRIDGE.lock + 1)
    fight.fighters["p2"].x -= 90                    # out of the shadow, into the frost
    run(fight, 60)
    assert fight.fighters["p2"].health == ROBERT.health - 5


def test_one_time_pad_holds_the_rival_between_them_for_25():
    fight = landed("ALICE & BOB", gap=80.0)
    rival, alice, bob = fight.fighters["p2"], fight.fighters["p1"], fight.echoes["p1"]
    assert rival.health == ROBERT.health - 25
    assert alice.x < rival.x < bob.x or bob.x < rival.x < alice.x


def test_one_time_pad_misses_out_of_reach_or_in_the_air():
    fight = landed("ALICE & BOB", gap=ONE_TIME_PAD.lock_range + 30.0)
    assert fight.fighters["p2"].health == ROBERT.health


def test_a_supers_startup_cant_be_hit_so_a_jab_never_wastes_the_bar():
    fight = fight_of(CHARACTERS["BOHR"], ROBERT, gap=50.0)
    fire(fight)
    bohr = fight.fighters["p1"]
    assert bohr.intangible
    for _ in range(10):
        fight.step({"p2": A})
        run(fight, 3)
    assert bohr.health == CHARACTERS["BOHR"].health and bohr.move is not None
    run(fight, WAVE_COLLAPSE.startup)
    assert fight.fighters["p2"].health < ROBERT.health      # and it lands
