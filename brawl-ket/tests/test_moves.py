import importlib.util

import pytest

from brawl_ket import config
from brawl_ket.basis import BOTH, OPPOSITE, OWN, Z_BASIS
from brawl_ket.moves import HIGH, LOW, MID
from brawl_ket.moves import CHARACTERS, DOS, ERWIN, NORMALS, PHOEBE, ROBERT, SLOTS, Box


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


STARTUPS = {   # spec section 3: (A, B on its own, B cancelled from a hit A)
    "ROBERT": (4, 10, 7),
    "BOHR": (6, 13, 9),
    "PHOEBE": (5, 11, 8),
    "ERWIN": (4, 10, 7),
    "DOS": (8, 13, 9),
}


def test_heavies_are_fast():
    for c in CHARACTERS.values():
        a, b, chained = STARTUPS[c.name]
        for light, heavy in (("stand.A", "stand.B"), ("crouch.A", "crouch.B")):
            assert c.moves[light].startup == a, (c.name, light)
            assert (c.moves[heavy].startup, c.moves[heavy].chain_startup) == (b, chained), (c.name, heavy)


def test_bohr_winds_up_slower_than_robert():
    for slot in ("stand.B", "crouch.B"):
        assert CHARACTERS["BOHR"].moves[slot].startup > CHARACTERS["ROBERT"].moves[slot].startup


def test_no_heavy_recovers_into_its_wind_up_pose():
    # the big coil must mean "a heavy is starting", never "a heavy just ended"
    for _c, slot, m in all_moves():
        if m.chain_startup is not None:
            assert m.poses[2] != m.poses[0], slot


@pytest.mark.skipif(importlib.util.find_spec("brawl_ket.poses") is None, reason="Task 7")
def test_poses_exist():
    from brawl_ket.poses import POSE_NAMES  # created in Task 7; skipped until then
    for _c, _slot, m in all_moves():
        assert set(m.poses) <= set(POSE_NAMES)


def test_every_kind_is_known():
    kinds = {"normal", "throw", "projectile", "special"}
    for _c, _slot, m in all_moves():
        assert m.kind in kinds


DAMAGE = {"A": 4, "B": 8, "X": 10, "throw": 10}     # spec section 1; MEASURE 12, CHARGE NOISE 3 a shock


# by name: the specials whose damage isn't a special's 10 (MEASURE 12; TUNNEL only moves her; LASER a
# little less; CHARGE NOISE a shock; THE BOX itself nothing, its swipe 8; SCRATCH a claw)
SPECIAL_DAMAGE = {"MEASURE": 12, "TUNNEL": 0, "LASER": 8, "CHARGE NOISE": 3, "THE BOX": 0, "SCRATCH": 4,
                  "FLOPPY": 9, "BLUE SCREEN": 6, "CRT DROP": 12}


def test_the_damage():
    for c, slot, m in all_moves():
        if m.name in SPECIAL_DAMAGE:
            assert m.damage == SPECIAL_DAMAGE[m.name], (c.name, slot)
        else:
            key = "throw" if slot == "throw" else slot.split(".")[1]
            assert m.damage == DAMAGE[key], (c.name, slot)


def test_health():
    assert {c.name: c.health for c in CHARACTERS.values()} == {
        "ROBERT": 100, "BOHR": 115, "PHOEBE": 95, "ERWIN": 90, "DOS": 125}


def test_photon_has_a_cooldown():
    assert ROBERT.moves["stand.X"].cooldown == config.frames(2.5)


def test_robert_jump_numbers():
    robert = CHARACTERS["ROBERT"]
    assert (robert.jump_vy, robert.gravity) == (12.0, 0.5)


def test_the_jab_boxes_are_long():
    robert = CHARACTERS["ROBERT"].moves
    assert robert["stand.A"].hitbox == Box(14, 70, 44, 14)
    assert robert["crouch.A"].hitbox == Box(12, 20, 44, 12)


# --- cross-field invariants -------------------------------------------------------------------


def test_a_projectile_move_and_only_one_has_a_projectile():
    for c, slot, m in all_moves():
        assert (m.kind == "projectile") == (m.projectile is not None), (c.name, slot)


def test_only_a_projectile_has_no_hitbox():
    for c, slot, m in all_moves():
        if m.hitbox is None:
            assert m.kind == "projectile" or m.tunnel or m.superpose, (c.name, slot)


def test_a_dive_is_only_ever_an_air_move():
    for c, slot, m in all_moves():
        if m.dive is not None:
            assert slot.startswith("air."), (c.name, slot)


def test_a_landing_shockwave_always_has_its_colour():
    for c, slot, m in all_moves():
        assert (m.landing is None) == (m.landing_colour is None), (c.name, slot)
        if m.landing is not None:
            assert m.dive is not None, (c.name, slot)     # it is opened by a dive's landing


# --- BOHR ------------------------------------------------------------------------------------


def test_bohr_stats():
    q = CHARACTERS["BOHR"]
    assert (q.build, q.health) == ("heavy", 115)
    assert (q.walk, q.jump_vy, q.gravity) == (1.5, 10.5, 0.55)
    assert q.hurt_stand == Box(-18, 0, 36, 132)
    assert q.hurt_crouch == Box(-20, 0, 40, 104)


def test_the_crouch_hurtbox_covers_the_drawn_crouch():
    # up to about the head's centre, as ROBERT's does: a hit on the drawn shoulders must land
    from brawl_ket.poses import POSES, drawn_joints
    for c in CHARACTERS.values():
        j = drawn_joints(POSES["crouch"], c.build, (0.0, 0.0), 1)
        assert -j["shoulder_f"][1] < c.hurt_crouch.h and abs(c.hurt_crouch.h + j["head"][1]) <= 4, c.name


def apex(c):
    return c.jump_vy ** 2 / (2 * c.gravity)


def test_bohr_is_the_slower_heavier_fighter():
    robert, bohr = CHARACTERS["ROBERT"], CHARACTERS["BOHR"]
    assert bohr.walk < robert.walk
    assert 95 <= apex(bohr) <= 105 < apex(robert)        # about 100 px: lower and heavier
    assert bohr.hurt_stand.w > robert.hurt_stand.w and bohr.hurt_stand.h > robert.hurt_stand.h


BOHR_FRAMES = {
    # slot: (name, startup, active, recovery, hitbox, hitstun, knockback)
    "stand.A": ("jab", 6, 3, 10, Box(16, 76, 46, 16), 17, 1.0),
    "stand.B": ("heavy", 13, 5, 20, Box(16, 70, 48, 22), 22, 6.0),
    "crouch.A": ("low jab", 6, 3, 11, Box(14, 22, 46, 14), 16, 1.0),
    "crouch.B": ("sweep", 13, 4, 22, Box(12, 6, 64, 14), 24, 2.5),
    "air.A": ("air jab", 5, 6, 5, Box(12, 54, 30, 20), 15, 1.5),
    "air.B": ("jump-in", 8, 6, 8, Box(10, 30, 40, 28), 20, 3.0),
    "throw": ("throw", 6, 2, 24, Box(0, 40, 44, 70), 30, 6.0),
    "stand.X": ("MEASURE", 16, 13, 30, Box(10, 40, 30, 70), 30, 6.0),
    "crouch.X": ("CHARGE NOISE", 8, 60, 16, Box(-60, 0, 120, 120), 8, 2.0),
    "air.X": ("COLLAPSE", 6, 60, 20, Box(-28, 0, 56, 75), 20, 3.0),
}


def test_bohr_frame_data():
    moves = CHARACTERS["BOHR"].moves
    assert set(BOHR_FRAMES) == set(moves)
    for slot, row in BOHR_FRAMES.items():
        m = moves[slot]
        got = (m.name, m.startup, m.active, m.recovery, m.hitbox, m.hitstun, m.knockback)
        assert got == row, slot


def test_bohr_specials():
    moves = CHARACTERS["BOHR"].moves
    assert moves["stand.A"].cancels == ("stand.A", "stand.B")
    assert moves["crouch.A"].cancels == ("crouch.A", "crouch.B")
    assert moves["crouch.B"].knockdown and moves["throw"].knockdown
    grab = moves["stand.X"]
    assert (grab.kind, grab.lunge, grab.knockdown) == ("throw", 6.0, True)
    assert grab.measure_rival and grab.colour == BOTH
    noise = moves["crouch.X"]
    assert (noise.cooldown, noise.hit_every, noise.height) == (config.frames(3.0), 12, MID)
    collapse = moves["air.X"]
    assert collapse.dive == (2.0, 9.0)
    assert (collapse.landing, collapse.colour, collapse.landing_colour) == (Box(-60, 0, 120, 14), OWN, OWN)


def test_bohr_light_reach_is_long():
    moves = CHARACTERS["BOHR"].moves
    assert moves["stand.A"].hitbox == Box(16, 76, 46, 16)
    assert moves["crouch.A"].hitbox == Box(14, 22, 46, 14)


HEIGHTS = {"stand.A": HIGH, "stand.B": HIGH, "crouch.A": LOW, "crouch.B": LOW,
           "air.A": MID, "air.B": MID, "throw": MID}


def test_a_is_your_colour_b_the_other_and_throws_both():
    for c in CHARACTERS.values():
        for slot, height in HEIGHTS.items():
            m = c.moves[slot]
            want = BOTH if slot == "throw" else OWN if slot.endswith(".A") else OPPOSITE
            assert (m.colour, m.height) == (want, height), (c.name, slot)


SPECIALS = {   # (character, slot): (colour rule, height, twists): every special is your colour
    ("ROBERT", "stand.X"): (OWN, HIGH, ()),
    ("ROBERT", "crouch.X"): (OWN, LOW, ()),
    ("ROBERT", "air.X"): (OWN, MID, ("switch_self_on_hit",)),
    ("BOHR", "stand.X"): (BOTH, MID, ("measure_rival",)),     # a throw: both, like every throw
    ("BOHR", "crouch.X"): (OWN, MID, ("hit_every",)),
    ("BOHR", "air.X"): (OWN, MID, ()),
    ("PHOEBE", "stand.X"): (OWN, MID, ()),
    ("PHOEBE", "crouch.X"): (OWN, MID, ("tunnel",)),
    ("PHOEBE", "air.X"): (OWN, MID, ("hover",)),
    ("ERWIN", "stand.X"): (OWN, MID, ("superpose",)),
    ("ERWIN", "crouch.X"): (OWN, MID, ("leap",)),
    ("ERWIN", "air.X"): (OWN, MID, ("hit_every", "hover")),
    ("DOS", "stand.X"): (OWN, HIGH, ()),
    ("DOS", "crouch.X"): (OWN, MID, ("push_out",)),
    ("DOS", "air.X"): (OWN, MID, ()),
}
TWISTS = ("switch_self_on_hit", "measure_rival", "hit_every", "tunnel", "hover", "superpose", "leap", "push_out")


def test_the_specials_colours_and_twists():
    for (name, slot), (colour, height, twists) in SPECIALS.items():
        m = CHARACTERS[name].moves[slot]
        assert (m.colour, m.height) == (colour, height), (name, slot)
        assert tuple(t for t in TWISTS if getattr(m, t)) == twists, (name, slot)
    names = {n: [CHARACTERS[n].moves[s].name for s in ("stand.X", "crouch.X", "air.X")] for n in CHARACTERS}
    assert names == {"ROBERT": ["PHOTON", "PHASE SLIDE", "HADAMARD DIVE"],
                     "BOHR": ["MEASURE", "CHARGE NOISE", "COLLAPSE"],
                     "PHOEBE": ["LIGHT PILLAR", "TUNNEL", "LASER"],
                     "ERWIN": ["THE BOX", "POUNCE", "SCRATCH"],
                     "DOS": ["FLOPPY", "BLUE SCREEN", "CRT DROP"]}


def test_only_specials_have_twists():
    for c, slot, m in all_moves():
        if any(getattr(m, t) for t in TWISTS):
            assert slot.endswith(".X"), (c.name, slot)


# --- PHOEBE ----------------------------------------------------------------------------------


def test_phoebe_stats():
    p = CHARACTERS["PHOEBE"]
    assert (p.build, p.health) == ("toy", 95)
    assert (p.walk, p.jump_vy, p.gravity) == (1.9, 11.5, 0.5)


def test_phoebe_has_the_longest_pokes():
    for slot in ("stand.A", "stand.B", "crouch.A", "crouch.B"):
        reach = {c.name: c.moves[slot].hitbox.x + c.moves[slot].hitbox.w for c in CHARACTERS.values()}
        assert reach["PHOEBE"] >= max(reach["ROBERT"], reach["BOHR"]), (slot, reach)
        assert reach["PHOEBE"] >= reach["ROBERT"] + 6, (slot, reach)


def test_light_pillar_only_reaches_the_air():
    # its beam starts above every standing hurtbox: a grounded rival walks under it
    trap = PHOEBE.moves["stand.X"]
    assert trap.knockdown and trap.cooldown == config.frames(1.5)
    for c in CHARACTERS.values():
        assert trap.hitbox.y > c.hurt_stand.y + c.hurt_stand.h, c.name


def test_tunnel_and_laser_numbers():
    tunnel, laser = PHOEBE.moves["crouch.X"], PHOEBE.moves["air.X"]
    assert (tunnel.startup, tunnel.active, tunnel.recovery) == (10, 12, 16)
    assert tunnel.cooldown == config.frames(1.8)
    assert laser.startup == 5 and laser.once_per_jump and laser.hover
    assert laser.projectile.vy == -laser.projectile.speed        # 45 degrees, down


# --- ERWIN -----------------------------------------------------------------------------------


def test_erwin_stats():
    e = CHARACTERS["ERWIN"]
    assert (e.build, e.health, e.walk, e.jump_vy, e.gravity) == ("cat", 90, 2.3, 12.5, 0.5)
    others = [c for c in CHARACTERS.values() if c is not e]
    assert apex(e) > max(apex(c) for c in others) and e.health < min(c.health for c in others)
    for slot in NORMALS:
        assert e.moves[slot] is ROBERT.moves[slot], slot


def test_erwin_specials():
    box, pounce, scratch = (ERWIN.moves[s] for s in ("stand.X", "crouch.X", "air.X"))
    assert box.superpose and box.hitbox is None and box.cooldown == config.frames(3.0)
    swipe = box.pop_out
    assert (swipe.damage, swipe.height, swipe.colour, swipe.kind) == (8, MID, OWN, "special")
    assert swipe.hitbox.x + swipe.hitbox.w <= 64                 # short range
    assert pounce.leap is not None and (pounce.damage, pounce.height, pounce.knockdown) == (10, MID, True)
    assert pounce.cooldown == config.frames(2.0) and 18 <= pounce.recovery <= 22
    assert pounce.active > 2 * pounce.leap[1] / ERWIN.gravity    # it always lands in its active frames
    assert scratch.hover and scratch.once_per_jump and (scratch.damage, scratch.height) == (4, MID)
    assert -(-scratch.active // scratch.hit_every) == 3          # three claws

# --- DOS -------------------------------------------------------------------------------------


def test_dos_stats():
    d = CHARACTERS["DOS"]
    assert (d.build, d.health, d.walk, d.jump_vy, d.gravity) == ("dos", 125, 1.6, 10.0, 0.55)
    others = [c for c in CHARACTERS.values() if c is not d]
    assert apex(d) < min(apex(c) for c in others) and d.health > max(c.health for c in others)
    assert d.fixed_basis == Z_BASIS and d.copy_paste and set(d.extra) == {"copy", "paste"}
    assert all(not c.copy_paste and c.fixed_basis is None for c in others)


def test_dos_specials():
    floppy, screen, drop = (DOS.moves[s] for s in ("stand.X", "crouch.X", "air.X"))
    assert (floppy.damage, floppy.kind, floppy.cooldown) == (9, "projectile", config.frames(2.5))
    assert floppy.projectile.speed == 3.0 < ROBERT.moves["stand.X"].projectile.speed
    assert (screen.damage, screen.height, screen.hitstun, screen.cooldown) == (6, MID, config.frames(0.6),
                                                                              config.frames(3.0))
    half = DOS.hurt_stand.w / 2
    assert screen.push_out and screen.hitbox.x == -(half + 50) and screen.hitbox.x + screen.hitbox.w == half + 50
    assert (drop.damage, drop.height, drop.knockdown, drop.dive[0]) == (12, MID, True, 0.0)
    assert drop.landing is None and 18 <= drop.recovery <= 22


def test_copy_and_paste_numbers():
    copy, paste = DOS.extra["copy"], DOS.extra["paste"]
    assert copy.catch is not None and copy.active == config.frames(0.2) and copy.recovery == config.frames(0.3)
    assert paste.paste and paste.startup <= 6 and paste.recovery <= 12
