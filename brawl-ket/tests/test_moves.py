import importlib.util

import pytest

from brawl_ket import config, qec
from brawl_ket.moves import CHARACTERS, SLOTS, Box


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


def test_error_types_follow_the_stance():
    for _c, slot, m in all_moves():
        if slot == "throw" or m.kind == "throw":
            assert m.error == qec.Y
        elif slot.startswith("crouch.") and m.kind != "reencode":
            assert m.error == qec.Z
        elif slot.startswith(("stand.", "air.")) and m.kind not in ("throw", "reencode"):
            assert m.error in (qec.X, qec.Y)


def test_every_chain_link_really_combos():
    # cancelling on the hit frame, the next move's first active frame lands inside the hitstun
    for c, _slot, m in all_moves():
        for nxt in m.cancels:
            assert c.moves[nxt].startup < m.hitstun - 1, (c.name, m.name, nxt)


@pytest.mark.skipif(importlib.util.find_spec("brawl_ket.poses") is None, reason="Task 7")
def test_poses_exist():
    from brawl_ket.poses import POSE_NAMES  # created in Task 7; skipped until then
    for _c, _slot, m in all_moves():
        assert set(m.poses) <= set(POSE_NAMES)


def test_cycle_is_in_frames():
    assert CHARACTERS["TRIO"].cycle_frames == config.frames(2.0)


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


def test_a_heavy_logical_error_costs_at_least_twice_a_light_one():
    trio = CHARACTERS["TRIO"].moves
    for light in LIGHTS:
        for heavy in HEAVIES + SPECIALS + ("throw",):
            assert logical_cost(trio[heavy]) >= 2 * logical_cost(trio[light]), (light, heavy)


def test_the_damage_tiers():
    trio = CHARACTERS["TRIO"].moves
    assert config.LOGICAL_DAMAGE == 12
    for slot in LIGHTS:
        assert (trio[slot].chip, logical_cost(trio[slot])) == (2, 12), slot
    for slot in HEAVIES:
        assert (trio[slot].chip, logical_cost(trio[slot])) == (6, 26), slot
    for slot in SPECIALS:
        assert (trio[slot].chip, logical_cost(trio[slot])) == (6, 28), slot
    assert (trio["throw"].chip, logical_cost(trio["throw"])) == (0, 26)


def test_trio_jump_numbers():
    trio = CHARACTERS["TRIO"]
    assert (trio.jump_vy, trio.gravity) == (12.0, 0.5)


def test_the_jab_boxes_are_long():
    trio = CHARACTERS["TRIO"].moves
    assert trio["stand.A"].hitbox == Box(14, 70, 44, 14)
    assert trio["crouch.A"].hitbox == Box(12, 20, 44, 12)
