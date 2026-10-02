"""The puppet skeleton: keyframe poses, interpolation, and joint positions.

Pure code, no pygame. A Pose is a set of joint angles; joints() turns one into
screen positions for a build and a facing; pose_for() picks (and blends) the
pose a Fighter should show this frame, from its action, move phase and frame.

Angles are degrees from straight down, positive towards the way the fighter
faces: 90 points straight ahead, 180 straight up, -90 straight behind. Every
limb segment's angle is absolute (not relative to its parent), so a pose reads
the same in the table as on screen. The torso points at 180 - lean, so a
positive lean tips the upper body forwards.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, fields

from . import qec
from .config import SWITCH_FRAMES
from .fighter import Fighter

EASE_FRAMES = 3         # at most this many frames to blend into a keyframe
_STUNNED = ("hitstun", "knockdown")
WALK_STRIDE = 8         # px of x travel from walk1 to walk2
BREATH_FRAMES = 72      # one idle breath
GET_UP_FRAMES = 12      # the end of a knockdown blends into the stance
FALL_FRAMES = 6         # the start of a knockdown blends from the hit


@dataclass(frozen=True)
class Pose:
    """Degrees, 0 = straight down, positive = towards facing (see the module doc)."""

    lean: float
    thigh_f: float
    shin_f: float
    thigh_b: float
    shin_b: float
    arm_f: float
    fore_f: float
    arm_b: float
    fore_b: float
    drop: float = 0.0   # px the whole puppet is lifted after its lowest foot is planted; 0 = feet on the floor


_FIELDS = tuple(f.name for f in fields(Pose))

POSES: dict[str, Pose] = {
    #                lean thigh_f shin_f thigh_b shin_b arm_f fore_f arm_b fore_b
    "idle": Pose(4, 24, -4, -22, -12, 40, 160, 20, 150),
    "walk1": Pose(6, 34, 8, -30, -20, 38, 158, 24, 150),
    "walk2": Pose(6, 6, -14, -4, -34, 44, 162, 16, 148),
    "crouch": Pose(16, 95, -4, 30, -86, 50, 165, 30, 155),
    "jump": Pose(10, 105, 15, 40, -50, 80, 160, 30, 150),
    "hitstun": Pose(-28, 14, -8, -26, -14, -30, -70, -60, -100),
    "knockdown": Pose(-80, 72, 92, 62, 96, 140, 170, 120, 160),
    # stand.A jab: a quick straight punch at the chest, leaning in (the fist reaches the 44 px jab box)
    "jab_wind": Pose(0, 26, -4, -24, -12, 30, 130, 24, 150),
    "jab_hit": Pose(12, 32, 0, -28, -14, 56, 56, 30, 150),
    # stand.B heavy: a big stepping straight. The wind-up is the telegraph (24 frames from neutral):
    # the whole body coiled back, the striking fist cocked far behind the hip, the guard hand up
    "heavy_wind": Pose(-26, 14, -6, -36, -16, -100, -125, 60, 150),
    "heavy_hit": Pose(8, 46, 6, -40, -26, 68, 68, -30, -60),
    # ...and the modest guard the heavy recovers into, so the big coil only ever means "a heavy
    # is starting" (the old wind-up pose)
    "heavy_recover": Pose(-14, 20, -6, -30, -14, -20, 80, 50, 140),
    # crouch.A low jab: a punch at the shins from the crouch
    "low_wind": Pose(24, 95, -4, 30, -86, 20, 120, 30, 155),
    "low_hit": Pose(20, 95, -4, 30, -86, 44, 44, 30, 155),
    # crouch.B sweep: a low kick along the floor, a hand down for balance. The wind-up (the
    # telegraph, 24 frames from neutral) rocks back on the planted leg with the kicking foot
    # cocked far behind the hip
    "sweep_wind": Pose(35, -75, -140, 70, 0, -40, -20, 10, 0),
    "sweep_hit": Pose(50, 70, 78, 20, -85, -60, -40, 10, 20),
    # air
    "air_jab": Pose(16, 100, 15, 40, -50, 40, 40, 30, 150),
    "air_kick": Pose(-6, 110, 20, 50, -40, 40, 140, -30, 0),
    # throw: reach out, then grab and heave
    "throw_reach": Pose(16, 36, 0, -30, -16, 84, 92, 74, 96),
    "throw_hold": Pose(-12, 28, -4, -28, -14, 75, 40, 70, 50),
    # stand.X PHOTON: draw back, then push both palms out
    "cast_wind": Pose(-10, 24, -6, -26, -14, -10, 40, -30, 40),
    "cast": Pose(10, 45, 5, -40, -25, 30, 90, 25, 88),
    # crouch.X PHASE SLIDE: feet first along the floor, the lead knee bent
    "slide": Pose(-58, 125, 55, 150, 70, 150, 170, -110, -150, drop=6),
    # air.X DIVE: a steep diving kick, foot first
    "dive": Pose(-30, 30, 30, -10, 70, 120, 160, -60, -30),
    # QUINT's stand.X SYNDROME GRAB: both arms drawn back low, then a lunging two-handed grab
    # round the waist (the lunge carries it into the rival)
    "grab_wind": Pose(-8, 26, -6, -30, -16, -40, 30, -60, 20),
    "grab": Pose(18, 44, 2, -36, -20, 10, 100, 0, 95),
    # QUINT's crouch.X RE-ENCODE: braced low, forearms crossed in front, a reset
    "brace": Pose(10, 95, -4, 30, -86, 70, 150, 60, 170),
    # QUINT's air.X COLLAPSE: falling feet first, knees braced, arms flung up
    "slam": Pose(4, 30, -6, -30, 6, 150, 170, -150, -170),
}
POSE_NAMES = tuple(POSES)

BASE_BONES = {"torso": 26, "neck": 9, "shoulder": 22, "upper_arm": 13, "forearm": 13, "thigh": 17, "shin": 17}
BUILD_BONES = {"heavy": {"neck": 6}}        # the heavy's helmet sits down between its shoulders
SCALE = {"lean": 2.0, "heavy": 2.3}         # the mockup's proportions: about 130 px tall
HEAD_R = {"lean": 13, "heavy": 15}
LIMB_W = {"lean": 12, "heavy": 16}


def lerp(a: Pose, b: Pose, k: float) -> Pose:
    if k <= 0:
        return a
    if k >= 1:
        return b
    return Pose(*(getattr(a, n) + (getattr(b, n) - getattr(a, n)) * k for n in _FIELDS))


def joints(pose: Pose, build: str, feet: tuple[float, float], facing: int) -> dict[str, tuple[float, float]]:
    """Screen positions of every joint. The hip stands over feet[0]; the lowest foot
    sits exactly on feet[1] (then the whole puppet is lifted by pose.drop)."""
    s = SCALE[build]
    bone = {k: v * s for k, v in {**BASE_BONES, **BUILD_BONES.get(build, {})}.items()}

    def at(p: tuple[float, float], angle: float, length: float) -> tuple[float, float]:
        a = math.radians(angle)
        return (p[0] + facing * math.sin(a) * length, p[1] + math.cos(a) * length)

    hip = (0.0, 0.0)
    up = 180 - pose.lean
    pts = {"hip": hip}
    pts["neck"] = at(hip, up, bone["torso"])
    pts["head"] = at(pts["neck"], up, bone["neck"])
    shoulder = at(hip, up, bone["shoulder"])
    for side in ("f", "b"):
        pts[f"shoulder_{side}"] = shoulder
        elbow = at(shoulder, getattr(pose, f"arm_{side}"), bone["upper_arm"])
        pts[f"elbow_{side}"] = elbow
        pts[f"hand_{side}"] = at(elbow, getattr(pose, f"fore_{side}"), bone["forearm"])
        knee = at(hip, getattr(pose, f"thigh_{side}"), bone["thigh"])
        pts[f"knee_{side}"] = knee
        pts[f"foot_{side}"] = at(knee, getattr(pose, f"shin_{side}"), bone["shin"])

    dx = feet[0]
    dy = feet[1] - max(pts["foot_f"][1], pts["foot_b"][1]) - pose.drop
    return {k: (x + dx, y + dy) for k, (x, y) in pts.items()}


# --- which pose, this frame -----------------------------------------------------------------


def _smooth(k: float) -> float:
    return k * k * (3 - 2 * k)


def _rest(slot: str | None, f: Fighter) -> str:
    """The pose a move starts from and settles back into."""
    if slot is not None and slot.startswith("air"):
        return "jump"
    if slot is not None and slot.startswith("crouch"):
        return "crouch"
    if slot is None and f.code.basis == qec.PHASE:
        return "crouch"
    return "idle"


def _stance_pose(f: Fighter) -> Pose:
    return POSES["crouch" if f.code.basis == qec.PHASE else "idle"]


def _ease(frame: int, length: int) -> float:
    """How far into a phase's keyframe on this frame (0-based) of a phase `length` long:
    1 on the phase's last eased frame, so every phase ends exactly on its keyframe."""
    return (frame + 1) / min(EASE_FRAMES, length)


def _move_pose(f: Fighter, start: Pose | None) -> Pose:
    """Startup eases in from the pose the fighter was in when the move began (the rest
    pose if unknown); the active phase IS its keyframe from its first frame, because
    that frame is the impact, held through hitstop; recovery eases out of the strike
    and, at the very end, back towards the rest pose."""
    m = f.move
    assert m is not None
    rest = POSES[_rest(f.slot, f)]
    startup = f.startup         # a cancelled-into heavy winds up faster than one from neutral
    active, end = startup, startup + m.active
    if f.frame < active:
        return lerp(start or rest, POSES[m.poses[0]], _ease(f.frame, startup))
    if f.frame < end:
        return POSES[m.poses[1]]
    pose = lerp(POSES[m.poses[1]], POSES[m.poses[2]], _ease(f.frame - end, m.recovery))
    left = end + m.recovery - f.frame
    if left <= EASE_FRAMES:
        pose = lerp(pose, rest, 1 - left / (EASE_FRAMES + 1))
    return pose


def pose_for(f: Fighter, start: Pose | None = None) -> Pose:
    """The pose to draw this frame. `start` is the pose the fighter was drawn in when
    its current action (or move) began, if known: the first frames blend out of it, so
    cancels and landings don't pop. A hit shows at once, without a blend."""
    if f.action == "attack" and f.move is not None:
        return _move_pose(f, start)
    pose = _action_pose(f)
    if start is not None and f.action not in _STUNNED and f.frame < EASE_FRAMES:
        pose = lerp(start, pose, (f.frame + 1) / (EASE_FRAMES + 1))
    return pose


def _action_pose(f: Fighter) -> Pose:
    a = f.action
    if a == "walk":
        k = (f.x / WALK_STRIDE) % 2
        return lerp(POSES["walk1"], POSES["walk2"], _smooth(k if k <= 1 else 2 - k))
    if a == "switch":
        # GAME RULE (visual): the SWITCH_FRAMES window shows the stance change
        to_crouch = f.code.basis == qec.PHASE
        k = _smooth(min(1.0, (f.frame + 1) / SWITCH_FRAMES))
        return lerp(POSES["idle"], POSES["crouch"], k if to_crouch else 1 - k)
    if a == "jump":
        return POSES["jump"]
    if a == "hitstun":
        if f.stun <= EASE_FRAMES:
            return lerp(_stance_pose(f), POSES["hitstun"], f.stun / (EASE_FRAMES + 1))
        return POSES["hitstun"]
    if a == "knockdown":
        down = lerp(POSES["hitstun"], POSES["knockdown"], (f.frame + 1) / FALL_FRAMES)
        if f.stun <= GET_UP_FRAMES:      # get up into the stance the code is in
            return lerp(_stance_pose(f), down, _smooth(f.stun / GET_UP_FRAMES))
        return down
    # idle and crouch breathe: a small dip towards the crouch
    base = _stance_pose(f) if a == "crouch" else POSES["idle"]
    k = 0.5 - 0.5 * math.cos(2 * math.pi * f.frame / BREATH_FRAMES)
    return lerp(base, POSES["crouch"] if a != "crouch" else POSES["low_wind"], 0.05 * k)
