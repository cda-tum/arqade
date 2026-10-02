import math

import pytest

from brawl_ket import qec
from brawl_ket.config import FLOOR_Y, SWITCH_FRAMES
from brawl_ket.fight import SHOT_SPAWN_OFFSET
from brawl_ket.fighter import Fighter
from brawl_ket.moves import CHARACTERS, TRIO, Move
from brawl_ket.poses import (
    EASE_FRAMES,
    POSE_NAMES,
    POSES,
    SCALE,
    Pose,
    joints,
    lerp,
    pose_for,
)

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
    move = TRIO.moves["stand.B"]
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
    for basis, name in ((qec.BIT, "idle"), (qec.PHASE, "crouch")):
        f = fighter("knockdown", stun=1, frame=39)
        if f.code.basis != basis:
            f.code.switch()
        near = pose_for(f)
        target = POSES[name]
        assert abs(near.lean - target.lean) < 3 and abs(near.thigh_b - target.thigh_b) < 6, basis


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

# which joint lands each move's hit; every move with a hitbox must be listed
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


@pytest.mark.parametrize(("char", "slot"), [
    (c.name, s) for c in CHARACTERS.values() for s, m in c.moves.items() if m.hitbox is not None
])
def test_the_striking_limb_reaches_the_hitbox_on_impact(char, slot):
    c = CHARACTERS[char]
    move = c.moves[slot]
    f = Fighter(c, FEET[0], 1)
    f.action, f.move, f.slot, f.frame = "attack", move, slot, move.startup   # the first active frame
    j = joints(pose_for(f), c.build, FEET, 1)
    point = j[STRIKER[move.name]]
    assert distance_to_box(point, screen_box(move)) <= REACH, (move.name, point)


def test_photon_leaves_from_the_hand():
    move = TRIO.moves["stand.X"]
    j = joints(POSES[move.poses[1]], TRIO.build, FEET, 1)
    box = move.projectile.box
    spawn = (FEET[0] + SHOT_SPAWN_OFFSET + box.x, FEET[1] - (box.y + box.h), box.w, box.h)
    assert distance_to_box(j["hand_f"], spawn) <= REACH


# --- the long wind-up of a neutral heavy ------------------------------------------------------


def test_a_chained_move_eases_into_its_wind_up_over_its_own_short_startup():
    heavy = TRIO.moves["stand.B"]
    f = fighter("attack", move=heavy, slot="stand.B", chained=True)
    f.frame = heavy.chain_startup - 1
    assert pose_for(f) == POSES[heavy.poses[0]]         # ends on the keyframe after 8 frames
    f.frame = heavy.chain_startup                       # and 8 is already the impact
    assert pose_for(f) == POSES[heavy.poses[1]]


def test_a_neutral_heavy_holds_its_wind_up_until_frame_20():
    heavy = TRIO.moves["stand.B"]
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
