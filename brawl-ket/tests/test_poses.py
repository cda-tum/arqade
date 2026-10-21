import math

import pytest

from brawl_ket.config import FLOOR_Y
from brawl_ket.fight import SHOT_SPAWN_OFFSET
from brawl_ket.fighter import Fighter
from brawl_ket.moves import CHARACTERS, BOHR, ROBERT, Move
from brawl_ket.poses import (
    EASE_FRAMES,
    HEAD_R,
    POSE_NAMES,
    POSES,
    SCALE,
    Pose,
    drawn_joints,
    joints,
    lerp,
    pose_for,
)

BUILDS = tuple(SCALE)
FEET = (320.0, float(FLOOR_Y))
ACTIONS = ("idle", "walk", "crouch", "jump", "attack", "hitstun", "knockdown", "boxed")
KEYS = {"hip", "neck", "head", "shoulder_f", "elbow_f", "hand_f", "shoulder_b", "elbow_b",
        "hand_b", "knee_f", "foot_f", "knee_b", "foot_b"}


def every_pose():
    for build in BUILDS:
        for facing in (1, -1):
            for name in POSE_NAMES:
                yield name, build, facing


def test_joints_has_every_key():
    assert set(joints(POSES["idle"], "lean", FEET, 1)) == KEYS


@pytest.mark.parametrize(("name", "build", "facing"), list(every_pose()))
def test_feet_never_go_below_the_floor(name, build, facing):
    j = joints(POSES[name], build, FEET, facing)
    assert j["foot_f"][1] <= FEET[1] + 1
    assert j["foot_b"][1] <= FEET[1] + 1


@pytest.mark.parametrize(("name", "build", "facing"), list(every_pose()))
def test_the_lowest_foot_is_planted(name, build, facing):
    pose = POSES[name]
    j = joints(pose, build, FEET, facing)
    lowest = max(j["foot_f"][1], j["foot_b"][1])
    assert lowest == pytest.approx(FEET[1] - pose.drop)


def test_facing_right_reaches_right():
    j = joints(POSES["jab_hit"], "lean", FEET, 1)
    assert j["hand_f"][0] > j["hip"][0] + 20


def test_facing_left_is_the_mirror_image():
    for name in POSE_NAMES:
        right = joints(POSES[name], "lean", FEET, 1)
        left = joints(POSES[name], "lean", FEET, -1)
        for key in KEYS:
            assert left[key][0] - FEET[0] == pytest.approx(FEET[0] - right[key][0])
            assert left[key][1] == pytest.approx(right[key][1])


def test_every_move_with_a_hitbox_names_its_striker():
    for _slot, move in all_moves():
        if move.hitbox is not None:
            assert move.name in STRIKER, move.name


def test_bohrs_specials_have_their_own_poses():
    moves = BOHR.moves
    assert moves["stand.X"].poses[:2] == ("grab_wind", "grab")
    assert moves["crouch.X"].poses[1] == "brace"
    assert moves["air.X"].poses[1] == "slam"


def test_the_slam_falls_feet_first_under_the_hip():
    j = joints(POSES["slam"], "heavy", FEET, 1)
    for foot in ("foot_f", "foot_b"):
        assert abs(j[foot][0] - j["hip"][0]) <= 20, foot


def test_the_hip_stands_over_the_fighters_x():
    for name in POSE_NAMES:
        assert joints(POSES[name], "lean", FEET, 1)["hip"][0] == pytest.approx(FEET[0])


def test_heavy_is_bigger_than_lean():
    lean = joints(POSES["idle"], "lean", FEET, 1)
    heavy = joints(POSES["idle"], "heavy", FEET, 1)
    assert heavy["head"][1] < lean["head"][1]


def test_crouch_head_is_lower_than_idle():
    for build in BUILDS:
        idle = joints(POSES["idle"], build, FEET, 1)["head"][1]
        crouch = joints(POSES["crouch"], build, FEET, 1)["head"][1]
        assert crouch > idle + 25


def test_lerp_endpoints():
    a, b = POSES["idle"], POSES["crouch"]
    assert lerp(a, b, 0) == a
    assert lerp(a, b, 1) == b


def test_lerp_midpoint():
    a, b = POSES["idle"], POSES["jab_hit"]
    mid = lerp(a, b, 0.5)
    assert mid.arm_f == pytest.approx((a.arm_f + b.arm_f) / 2)
    assert mid.drop == pytest.approx((a.drop + b.drop) / 2)


# --- pose_for -----------------------------------------------------------------------------


def fighter(action="idle", **kw):
    f = Fighter(ROBERT, 300, 1)
    f.action = action
    for k, v in kw.items():
        setattr(f, k, v)
    return f


@pytest.mark.parametrize("action", ACTIONS)
def test_pose_for_every_action(action):
    f = fighter(action)
    if action == "attack":
        f.move, f.slot = ROBERT.moves["stand.A"], "stand.A"
    if action in ("hitstun", "knockdown"):
        f.stun = 10
    for frame in range(40):
        f.frame = frame
        assert isinstance(pose_for(f), Pose)


def test_pose_for_every_move_and_frame():
    for slot, move in all_moves():
        f = fighter("attack", move=move, slot=slot)
        for frame in range(move.startup + move.active + move.recovery):
            f.frame = frame
            assert isinstance(pose_for(f), Pose), (slot, frame)


def all_moves():
    for char in CHARACTERS.values():
        yield from char.moves.items()


def test_the_active_phase_snaps_to_its_keyframe():
    # the impact frame is held through hitstop, so it must be the full strike
    for slot, move in all_moves():
        f = fighter("attack", move=move, slot=slot)
        for frame in range(move.startup, move.startup + move.active):
            f.frame = frame
            assert pose_for(f) == POSES[move.poses[1]], (slot, frame)


def test_startup_and_recovery_end_on_their_keyframes():
    for slot, move in all_moves():
        f = fighter("attack", move=move, slot=slot)
        f.frame = move.startup - 1
        assert pose_for(f) == POSES[move.poses[0]], slot


def test_startup_eases_in_from_the_pose_reached():
    move = ROBERT.moves["stand.B"]
    f = fighter("attack", move=move, slot="stand.B", frame=0)
    start = POSES["jab_hit"]        # cancelled out of a jab's strike
    n = min(EASE_FRAMES, move.startup)
    assert pose_for(f, start) == lerp(start, POSES[move.poses[0]], 1 / n)
    assert pose_for(f) == lerp(POSES["idle"], POSES[move.poses[0]], 1 / n)


def test_recovery_eases_out_of_the_strike():
    for slot, move in all_moves():
        f = fighter("attack", move=move, slot=slot, frame=move.startup + move.active)
        n = min(EASE_FRAMES, move.recovery)
        assert pose_for(f) == lerp(POSES[move.poses[1]], POSES[move.poses[2]], 1 / n), slot


def test_other_actions_ease_in_from_the_pose_reached():
    start = POSES["air_kick"]       # landing out of an air move
    f = fighter("idle", frame=0)
    first = pose_for(f, start)
    assert first != pose_for(f) and first != start
    f.frame = EASE_FRAMES
    assert pose_for(f, start) == pose_for(f)


def test_a_hit_shows_at_once():
    f = fighter("hitstun", stun=16, frame=0)
    assert pose_for(f, POSES["jab_hit"]) == POSES["hitstun"]


def test_knockdown_gets_up_into_the_stance():
    for crouching, name in ((False, "idle"), (True, "crouch")):
        f = fighter("knockdown", stun=1, frame=39, crouching=crouching)
        near = pose_for(f)
        target = POSES[name]
        assert abs(near.lean - target.lean) < 3 and abs(near.thigh_b - target.thigh_b) < 6, crouching


def test_walking_alternates_with_distance():
    names = set()
    for x in range(200, 264, 1):
        p = pose_for(fighter("walk", x=float(x)))
        if p == POSES["walk1"]:
            names.add("walk1")
        if p == POSES["walk2"]:
            names.add("walk2")
    assert names == {"walk1", "walk2"}


def test_knockdown_lies_low():
    head = joints(pose_for(fighter("knockdown", stun=20, frame=20)), "lean", FEET, 1)["head"][1]
    assert head > FEET[1] - 40


# --- the art matches the frame data ---------------------------------------------------------

# which joint lands each move's hit; every move with a hitbox must be listed
STRIKER = {
    "jab": "hand_f", "heavy": "hand_f", "low jab": "hand_f", "sweep": "foot_f",
    "air jab": "hand_f", "jump-in": "foot_f", "throw": "hand_f",
    "PHASE SLIDE": "foot_f", "HADAMARD DIVE": "foot_f",
    "MEASURE": "hand_f", "CHARGE NOISE": "hand_f", "COLLAPSE": "foot_f",
    "LIGHT PILLAR": "hand_f",
    "POUNCE": "hand_f", "CRT DROP": "foot_f",
}
REACH = 12      # px: a joint is drawn with a fist/foot about this big around it


def distance_to_box(point, box):
    left, top, w, h = box
    dx = max(left - point[0], 0, point[0] - (left + w))
    dy = max(top - point[1], 0, point[1] - (top + h))
    return math.hypot(dx, dy)


def screen_box(move: Move):
    b = move.hitbox
    return (FEET[0] + b.x, FEET[1] - (b.y + b.h), b.w, b.h)


@pytest.mark.parametrize(("char", "slot"), [
    (c.name, s) for c in CHARACTERS.values() for s, m in c.moves.items() if m.hitbox is not None
])
def test_the_striking_limb_reaches_the_hitbox_on_impact(char, slot):
    c = CHARACTERS[char]
    move = c.moves[slot]
    f = Fighter(c, FEET[0], 1)
    f.action, f.move, f.slot, f.frame = "attack", move, slot, move.startup   # the first active frame
    j = drawn_joints(pose_for(f), c.build, FEET, 1)
    point = j[STRIKER[move.name]]
    assert distance_to_box(point, screen_box(move)) <= REACH, (move.name, point)


def test_photon_leaves_from_the_hand():
    move = ROBERT.moves["stand.X"]
    j = joints(POSES[move.poses[1]], ROBERT.build, FEET, 1)
    box = move.projectile.box
    spawn = (FEET[0] + SHOT_SPAWN_OFFSET + box.x, FEET[1] - (box.y + box.h), box.w, box.h)
    assert distance_to_box(j["hand_f"], spawn) <= REACH


def test_the_box_swipe_reaches_its_hitbox():
    from brawl_ket.moves import ERWIN
    swipe = ERWIN.moves["stand.X"].pop_out
    f = Fighter(ERWIN, FEET[0], 1)
    f.action, f.move, f.slot, f.frame = "attack", swipe, "stand.X", swipe.startup
    j = joints(pose_for(f), ERWIN.build, FEET, 1)
    assert distance_to_box(j["hand_f"], screen_box(swipe)) <= REACH


# --- the wind-up of a heavy: shorter in a chain ---------------------------------------------


def test_a_chained_move_eases_into_its_wind_up_over_its_own_short_startup():
    heavy = ROBERT.moves["stand.B"]
    f = fighter("attack", move=heavy, slot="stand.B", chained=True)
    f.frame = heavy.chain_startup - 1
    assert pose_for(f) == POSES[heavy.poses[0]]         # ends on the keyframe
    f.frame = heavy.chain_startup                       # and the next frame is the impact
    assert pose_for(f) == POSES[heavy.poses[1]]


def test_a_neutral_heavy_holds_its_wind_up_until_its_startup_ends():
    heavy = ROBERT.moves["stand.B"]
    f = fighter("attack", move=heavy, slot="stand.B")
    for frame in range(EASE_FRAMES, heavy.startup):
        f.frame = frame
        assert pose_for(f) == POSES["heavy_wind"], frame
    f.frame = heavy.startup
    assert pose_for(f) == POSES["heavy_hit"]


def test_the_heavy_wind_up_draws_the_fist_far_back_and_the_sweep_the_foot():
    heavy = joints(POSES["heavy_wind"], "lean", FEET, 1)
    hit = joints(POSES["heavy_hit"], "lean", FEET, 1)
    assert heavy["hand_f"][0] <= heavy["hip"][0] - 40            # the fist behind the hip
    assert hit["hand_f"][0] - heavy["hand_f"][0] >= 100          # a long way to travel
    sweep = joints(POSES["sweep_wind"], "lean", FEET, 1)
    sweep_hit = joints(POSES["sweep_hit"], "lean", FEET, 1)
    assert sweep["foot_f"][0] <= sweep["hip"][0] - 20            # the striking foot cocked behind
    assert sweep_hit["foot_f"][0] - sweep["foot_f"][0] >= 60


def test_the_slide_is_drawn_under_a_photon():
    """PHASE SLIDE passes under photons, so its drawn body (head and outline included)
    must stay below a photon's bottom edge, as its active hurtbox does."""
    j = joints(POSES["slide"], "lean", (0, 0), 1)
    top = max(-y for _, y in j.values())
    head_top = -j["head"][1] + HEAD_R["lean"] + 2      # the ink outline
    photon_bottom = ROBERT.moves["stand.X"].projectile.box.y
    assert head_top < photon_bottom and top < photon_bottom
    assert ROBERT.moves["crouch.X"].hurt_active.h < photon_bottom


def test_dos_leans_only_a_little_and_his_arms_come_out_of_the_case():
    from brawl_ket.poses import CASE_TILT
    pose = POSES["crouch"]
    j = drawn_joints(pose, "dos", FEET, 1)
    tilt = math.degrees(math.atan2(j["neck"][0] - j["hip"][0], j["hip"][1] - j["neck"][1]))
    assert tilt == pytest.approx(pose.lean * CASE_TILT)
    idle, plain = drawn_joints(POSES["idle"], "dos", FEET, 1), joints(POSES["idle"], "dos", FEET, 1)
    assert idle["foot_f"] == plain["foot_f"] and idle["hand_f"][0] > plain["hand_f"][0] + 20
    for name in POSE_NAMES:                 # every other build is drawn on joints() itself
        assert drawn_joints(POSES[name], "lean", FEET, 1) == joints(POSES[name], "lean", FEET, 1)
