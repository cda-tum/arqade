import math

import pytest

from brawl_ket import qec
from brawl_ket.config import FLOOR_Y, SWITCH_FRAMES
from brawl_ket.fight import SHOT_SPAWN_OFFSET
from brawl_ket.fighter import Fighter
from brawl_ket.moves import CHARACTERS, TRIO, Move
from brawl_ket.poses import POSE_NAMES, POSES, SCALE, Pose, joints, lerp, pose_for

BUILDS = tuple(SCALE)
FEET = (320.0, float(FLOOR_Y))
ACTIONS = ("idle", "walk", "crouch", "switch", "jump", "attack", "hitstun", "knockdown")
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
    f = Fighter(TRIO, 300, 1)
    f.action = action
    for k, v in kw.items():
        setattr(f, k, v)
    return f


@pytest.mark.parametrize("action", ACTIONS)
def test_pose_for_every_action(action):
    f = fighter(action)
    if action == "attack":
        f.move, f.slot = TRIO.moves["stand.A"], "stand.A"
    if action == "switch":
        f.switch_left = SWITCH_FRAMES
    if action in ("hitstun", "knockdown"):
        f.stun = 10
    for frame in range(40):
        f.frame = frame
        assert isinstance(pose_for(f), Pose)


def test_pose_for_every_move_and_frame():
    for char in CHARACTERS.values():
        for slot, move in char.moves.items():
            f = fighter("attack", move=move, slot=slot)
            for frame in range(move.startup + move.active + move.recovery):
                f.frame = frame
                assert isinstance(pose_for(f), Pose), (slot, frame)


def test_a_move_reaches_its_keyframes():
    move = TRIO.moves["stand.B"]
    f = fighter("attack", move=move, slot="stand.B")
    f.frame = move.startup + 3      # three frames into the active phase: fully eased in
    assert pose_for(f) == POSES[move.poses[1]]
    f.frame = move.startup          # the first active frame is still blending
    assert pose_for(f) != POSES[move.poses[1]]


def test_walking_alternates_with_distance():
    names = set()
    for x in range(200, 264, 1):
        p = pose_for(fighter("walk", x=float(x)))
        if p == POSES["walk1"]:
            names.add("walk1")
        if p == POSES["walk2"]:
            names.add("walk2")
    assert names == {"walk1", "walk2"}


def test_switch_blends_towards_the_new_stance():
    f = fighter("switch", switch_left=SWITCH_FRAMES)
    f.code.switch()                 # standing -> crouching: the code is already PHASE
    assert f.code.basis == qec.PHASE
    f.frame = 0
    early = joints(pose_for(f), "lean", FEET, 1)["head"][1]
    f.frame = SWITCH_FRAMES - 1
    late = joints(pose_for(f), "lean", FEET, 1)["head"][1]
    assert late > early             # the head sinks as the crouch comes in


def test_knockdown_lies_low():
    head = joints(pose_for(fighter("knockdown", stun=20, frame=20)), "lean", FEET, 1)["head"][1]
    assert head > FEET[1] - 40


# --- the art matches the frame data ---------------------------------------------------------

# which joint lands each move's hit (the active pose)
STRIKER = {
    "jab": "hand_f", "heavy": "hand_f", "low jab": "hand_f", "sweep": "foot_f",
    "air jab": "hand_f", "jump-in": "foot_f", "throw": "hand_f",
    "PHASE SLIDE": "foot_f", "DIVE": "foot_f",
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


@pytest.mark.parametrize("slot", [s for s, m in TRIO.moves.items() if m.name in STRIKER])
def test_the_striking_limb_reaches_the_hitbox(slot):
    move = TRIO.moves[slot]
    j = joints(POSES[move.poses[1]], TRIO.build, FEET, 1)
    point = j[STRIKER[move.name]]
    assert distance_to_box(point, screen_box(move)) <= REACH, (move.name, point)


def test_photon_leaves_from_the_hand():
    move = TRIO.moves["stand.X"]
    j = joints(POSES[move.poses[1]], TRIO.build, FEET, 1)
    box = move.projectile.box
    spawn = (FEET[0] + SHOT_SPAWN_OFFSET + box.x, FEET[1] - (box.y + box.h), box.w, box.h)
    assert distance_to_box(j["hand_f"], spawn) <= REACH
