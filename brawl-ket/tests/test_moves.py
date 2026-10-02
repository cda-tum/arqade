import importlib.util

import pytest

from brawl_ket import config, shor
from brawl_ket.moves import CHARACTERS, QUINT, SLOTS, TRIO, Box


def all_moves():
    for c in CHARACTERS.values():
        for slot, m in c.moves.items():
            yield c, slot, m


def test_every_character_has_every_slot():
    for c in CHARACTERS.values():
        assert set(c.moves) == set(SLOTS)


def test_frame_counts_are_positive():
    for _c, _slot, m in all_moves():
        assert m.startup >= 1 and m.active >= 1 and m.recovery >= 1


def chain_startup(move):
    """The startup a move has when a cancel starts it (what a chain really waits for)."""
    return move.startup if move.chain_startup is None else move.chain_startup


def test_every_chain_link_really_combos():
    # cancelling on the hit frame, the next move's first active frame lands inside the hitstun
    for c, _slot, m in all_moves():
        for nxt in m.cancels:
            assert chain_startup(c.moves[nxt]) < m.hitstun - 1, (c.name, m.name, nxt)


def test_a_chain_startup_is_never_slower_than_the_neutral_one():
    for _c, slot, m in all_moves():
        if m.chain_startup is not None:
            assert 1 <= m.chain_startup <= m.startup, slot


TELEGRAPHED = {"TRIO": {"stand.B": (24, 8), "crouch.B": (24, 9)},
               "QUINT": {"stand.B": (28, 11), "crouch.B": (28, 12)}}


def test_the_heavies_telegraph_from_neutral_and_stay_fast_in_a_chain():
    assert set(TELEGRAPHED) == set(CHARACTERS)
    for name, wanted in TELEGRAPHED.items():
        moves = CHARACTERS[name].moves
        for slot, startups in wanted.items():
            assert (moves[slot].startup, moves[slot].chain_startup) == startups, (name, slot)
        # every other move starts the same way however it begins
        for slot, m in moves.items():
            if slot not in wanted:
                assert m.chain_startup is None, (name, slot)
        # the telegraph leaves room for a human reaction
        for slot in wanted:
            assert moves[slot].startup - config.REACTION_FRAMES >= 2, (name, slot)


def test_quint_winds_up_slower_than_trio():
    for slot in ("stand.B", "crouch.B"):
        assert CHARACTERS["QUINT"].moves[slot].startup > CHARACTERS["TRIO"].moves[slot].startup


def test_no_telegraphed_move_recovers_into_its_wind_up_pose():
    # the big coil must mean "a heavy is starting", never "a heavy just ended"
    for _c, slot, m in all_moves():
        if m.chain_startup is not None:
            assert m.poses[2] != m.poses[0], slot


@pytest.mark.skipif(importlib.util.find_spec("brawl_ket.poses") is None, reason="Task 7")
def test_poses_exist():
    from brawl_ket.poses import POSE_NAMES  # created in Task 7; skipped until then
    for _c, _slot, m in all_moves():
        assert set(m.poses) <= set(POSE_NAMES)


def test_cycle_is_in_frames():
    assert CHARACTERS["TRIO"].cycle_frames == config.frames(1.0) == 60
    assert CHARACTERS["QUINT"].cycle_frames == config.frames(1.5) == 90


def test_every_kind_is_known():
    kinds = {"normal", "throw", "projectile", "special", "reencode"}
    for _c, _slot, m in all_moves():
        assert m.kind in kinds


LIGHTS = ("stand.A", "crouch.A", "air.A")
HEAVIES = ("stand.B", "crouch.B", "air.B")
SPECIALS = ("stand.X", "crouch.X", "air.X")


def logical_cost(m):
    """Health a logical error from move m takes (the same sum Fighter.take_hit does)."""
    return config.LOGICAL_DAMAGE + m.bonus


def hitting(moves, slots):
    """The slots among `slots` whose move can hit (RE-ENCODE never does)."""
    return [s for s in slots if moves[s].kind != "reencode"]


def test_a_heavy_logical_error_costs_at_least_twice_a_light_one():
    for c in CHARACTERS.values():
        moves = c.moves
        for light in LIGHTS:
            for heavy in hitting(moves, HEAVIES + SPECIALS + ("throw",)):
                assert logical_cost(moves[heavy]) >= 2 * logical_cost(moves[light]), (c.name, light, heavy)


# (light, heavy, special, throw) logical costs. QUINT's are lower: its d=5 code means a TRIO
# breaks after 2 hits in a cycle, so nearly every QUINT string ends in a logical error.
DAMAGE_TIERS = {"TRIO": (12, 26, 28, 26), "QUINT": (12, 24, 24, 24)}


def test_the_damage_tiers():
    assert config.LOGICAL_DAMAGE == 12
    assert set(DAMAGE_TIERS) == set(CHARACTERS)
    for c in CHARACTERS.values():
        moves = c.moves
        light, heavy, special, throw = DAMAGE_TIERS[c.name]
        for slot in LIGHTS:
            assert (moves[slot].chip, logical_cost(moves[slot])) == (2, light), (c.name, slot)
        for slot in HEAVIES:
            assert (moves[slot].chip, logical_cost(moves[slot])) == (6, heavy), (c.name, slot)
        for slot in hitting(moves, SPECIALS):
            # a command throw (SYNDROME GRAB) has no chip
            chip = 0 if moves[slot].kind == "throw" else 6
            assert (moves[slot].chip, logical_cost(moves[slot])) == (chip, special), (c.name, slot)
        assert (moves["throw"].chip, logical_cost(moves["throw"])) == (0, throw), c.name


def test_quint_hits_no_harder_than_trio():
    for slot, move in QUINT.moves.items():
        if slot in TRIO.moves and move.kind != "reencode" and TRIO.moves[slot].kind != "reencode":
            assert logical_cost(move) <= logical_cost(TRIO.moves[slot]), slot


def test_photon_has_a_cooldown():
    assert TRIO.moves["stand.X"].cooldown == config.frames(2.5)


def test_trio_jump_numbers():
    trio = CHARACTERS["TRIO"]
    assert (trio.jump_vy, trio.gravity) == (12.0, 0.5)


def test_the_jab_boxes_are_long():
    trio = CHARACTERS["TRIO"].moves
    assert trio["stand.A"].hitbox == Box(14, 70, 44, 14)
    assert trio["crouch.A"].hitbox == Box(12, 20, 44, 12)


# --- cross-field invariants -------------------------------------------------------------------


def test_a_projectile_move_and_only_one_has_a_projectile():
    for c, slot, m in all_moves():
        assert (m.kind == "projectile") == (m.projectile is not None), (c.name, slot)


def test_only_a_projectile_or_a_reencode_has_no_hitbox():
    for c, slot, m in all_moves():
        if m.hitbox is None:
            assert m.kind in ("projectile", "reencode"), (c.name, slot)


def test_a_dive_is_only_ever_an_air_move():
    for c, slot, m in all_moves():
        if m.dive is not None:
            assert slot.startswith("air."), (c.name, slot)


def test_a_landing_shockwave_always_has_its_error():
    for c, slot, m in all_moves():
        assert (m.landing is None) == (m.landing_error is None), (c.name, slot)
        if m.landing is not None:
            assert m.dive is not None, (c.name, slot)     # it is opened by a dive's landing


# --- QUINT ------------------------------------------------------------------------------------


def test_quint_stats():
    q = CHARACTERS["QUINT"]
    assert (q.build, q.health) == ("heavy", 100)
    assert (q.walk, q.jump_vy, q.gravity) == (1.5, 10.5, 0.55)
    assert q.hurt_stand == Box(-18, 0, 36, 132)
    assert q.hurt_crouch == Box(-20, 0, 40, 104)


def test_the_crouch_hurtbox_covers_the_drawn_crouch():
    # up to about the head's centre, as TRIO's does: a hit on the drawn shoulders must land
    from brawl_ket.poses import POSES, joints
    for c in CHARACTERS.values():
        j = joints(POSES["crouch"], c.build, (0.0, 0.0), 1)
        assert -j["shoulder_f"][1] < c.hurt_crouch.h and abs(c.hurt_crouch.h + j["head"][1]) <= 4, c.name


def apex(c):
    return c.jump_vy ** 2 / (2 * c.gravity)


def test_quint_is_the_slower_heavier_fighter():
    trio, quint = CHARACTERS["TRIO"], CHARACTERS["QUINT"]
    assert quint.cycle_frames > trio.cycle_frames
    assert quint.walk < trio.walk
    assert 95 <= apex(quint) <= 105 < apex(trio)        # about 100 px: lower and heavier
    assert quint.hurt_stand.w > trio.hurt_stand.w and quint.hurt_stand.h > trio.hurt_stand.h


QUINT_FRAMES = {
    # slot: (name, startup, active, recovery, hitbox, error, hitstun, knockback)
    "stand.A": ("jab", 6, 3, 10, Box(16, 76, 46, 16), shor.X, 17, 1.0),
    "stand.B": ("heavy", 28, 5, 20, Box(16, 70, 48, 22), shor.X, 22, 6.0),
    "crouch.A": ("low jab", 7, 3, 11, Box(14, 22, 46, 14), shor.X, 16, 1.0),
    "crouch.B": ("sweep", 28, 4, 22, Box(12, 6, 64, 14), shor.X, 24, 2.5),
    "air.A": ("air jab", 5, 6, 5, Box(12, 54, 30, 20), shor.X, 15, 1.5),
    "air.B": ("jump-in", 8, 6, 8, Box(10, 30, 40, 28), shor.X, 20, 3.0),
    "throw": ("throw", 6, 2, 24, Box(0, 40, 44, 70), shor.Y, 30, 6.0),
    "stand.X": ("SYNDROME GRAB", 16, 13, 30, Box(10, 40, 30, 70), shor.Z, 30, 6.0),
    "crouch.X": ("RE-ENCODE", 6, 1, 18, None, shor.Z, 0, 0.0),
    "air.X": ("COLLAPSE", 6, 60, 20, Box(-20, 0, 40, 30), shor.Z, 20, 3.0),
}


def test_quint_frame_data():
    moves = CHARACTERS["QUINT"].moves
    assert set(QUINT_FRAMES) == set(moves)
    for slot, row in QUINT_FRAMES.items():
        m = moves[slot]
        got = (m.name, m.startup, m.active, m.recovery, m.hitbox, m.error, m.hitstun, m.knockback)
        assert got == row, slot


def test_quint_specials():
    moves = CHARACTERS["QUINT"].moves
    assert moves["stand.A"].cancels == ("stand.A", "stand.B")
    assert moves["crouch.A"].cancels == ("crouch.A", "crouch.B")
    assert moves["crouch.B"].knockdown and moves["throw"].knockdown
    grab = moves["stand.X"]
    assert (grab.kind, grab.lunge, grab.knockdown) == ("throw", 6.0, True)
    reencode = moves["crouch.X"]
    assert (reencode.kind, reencode.cooldown) == ("reencode", config.frames(4.0))
    collapse = moves["air.X"]
    assert collapse.dive == (2.0, 9.0)
    assert (collapse.landing, collapse.landing_error) == (Box(-60, 0, 120, 14), shor.Z)


def test_quint_light_reach_is_long():
    moves = CHARACTERS["QUINT"].moves
    assert moves["stand.A"].hitbox == Box(16, 76, 46, 16)
    assert moves["crouch.A"].hitbox == Box(14, 22, 46, 14)


HEIGHTS = {"stand.A": shor.HIGH, "stand.B": shor.HIGH, "crouch.A": shor.LOW, "crouch.B": shor.LOW,
           "air.A": shor.MID, "air.B": shor.MID, "throw": shor.MID}
COLUMNS = {"stand.A": shor.A_COL, "crouch.A": shor.A_COL, "air.A": shor.A_COL,
           "stand.B": shor.B_COL, "crouch.B": shor.B_COL, "air.B": shor.B_COL, "throw": shor.THROW_COL}


def test_normals_deal_x_in_their_buttons_column_at_their_height():
    for c in CHARACTERS.values():
        for slot, height in HEIGHTS.items():
            m = c.moves[slot]
            want = shor.Y if slot == "throw" else shor.X
            assert (m.error, m.height, m.column) == (want, height, COLUMNS[slot]), (c.name, slot)


def test_every_height_has_an_a_and_a_b():
    for height in (shor.HIGH, shor.MID, shor.LOW):
        cols = {COLUMNS[s] for s, h in HEIGHTS.items() if h == height and s != "throw"}
        assert cols == {shor.A_COL, shor.B_COL}


SPECIALS_ZH = {   # (character, slot): height of its Z
    ("TRIO", "stand.X"): shor.HIGH, ("TRIO", "crouch.X"): shor.LOW, ("TRIO", "air.X"): shor.MID,
    ("QUINT", "stand.X"): shor.MID, ("QUINT", "air.X"): shor.HIGH,
}


def test_specials_deal_z_at_their_height():
    for (name, slot), height in SPECIALS_ZH.items():
        m = CHARACTERS[name].moves[slot]
        assert (m.error, m.height) == (shor.Z, height), (name, slot)
    collapse = CHARACTERS["QUINT"].moves["air.X"]
    assert (collapse.landing_error, collapse.landing_height) == (shor.Z, shor.LOW)
    assert CHARACTERS["QUINT"].moves["crouch.X"].kind == "reencode"
