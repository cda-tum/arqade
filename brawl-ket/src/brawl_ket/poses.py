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
from dataclasses import dataclass, fields, replace

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
    # stand.B heavy: a big stepping straight, wound up with the whole body coiled back, the
    # striking fist cocked far behind the hip and the guard hand up
    "heavy_wind": Pose(-26, 14, -6, -36, -16, -100, -125, 60, 150),
    "heavy_hit": Pose(8, 46, 6, -40, -26, 68, 68, -30, -60),
    # ...and the modest guard the heavy recovers into, so the big coil only ever means "a heavy
    # is starting" (the old wind-up pose)
    "heavy_recover": Pose(-14, 20, -6, -30, -14, -20, 80, 50, 140),
    # crouch.A low jab: a punch at the shins from the crouch
    "low_wind": Pose(24, 95, -4, 30, -86, 20, 120, 30, 155),
    "low_hit": Pose(20, 95, -4, 30, -86, 44, 44, 30, 155),
    # crouch.B sweep: a low kick along the floor, a hand down for balance. A big wind-up
    # rocks back on the planted leg with the kicking foot cocked far behind the hip
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
    # crouch.X PHASE SLIDE: feet first along the floor, the lead knee bent, the back hand on
    # the floor behind and the front arm along the legs: all of it under a photon
    "slide": Pose(-62, 125, 55, 150, 70, 70, 95, -45, -75, drop=6),
    # air.X DIVE: a steep diving kick, foot first
    "dive": Pose(-30, 30, 30, -10, 70, 120, 160, -60, -30),
    # BOHR's stand.X MEASURE: both arms drawn back low, then a lunging two-handed grab
    # round the waist (the lunge carries it into the rival)
    "grab_wind": Pose(-8, 26, -6, -30, -16, -40, 30, -60, 20),
    "grab": Pose(18, 44, 2, -36, -20, 10, 100, 0, 95),
    # BOHR's crouch.X CHARGE NOISE: braced low, forearms crossed in front, crackling
    "brace": Pose(10, 95, -4, 30, -86, 70, 150, 60, 170),
    # BOHR's air.X COLLAPSE: falling feet first, knees braced, arms flung up
    "slam": Pose(4, 30, -6, -30, 6, 150, 170, -150, -170),
    # PHOEBE's long pokes: her jab and heavy reach further, the arm straight out (Dhalsim-style)
    "poke_hit": Pose(18, 38, 2, -30, -16, 66, 70, 30, 150),
    "lunge_hit": Pose(16, 54, 8, -44, -28, 64, 68, -30, -60),
    # PHOEBE's stand.X LIGHT PILLAR: hands together at the chest, gathering the light, then
    # raised up and forward: the beam leaves her palms straight up
    "trap_wind": Pose(4, 24, -4, -22, -12, 50, 150, 40, 160),
    "trap": Pose(-8, 26, -4, -24, -12, 140, 160, 130, 150),
    # PHOEBE's crouch.X TUNNEL: arms wrapped round herself as she dissolves and re-forms
    "tunnel": Pose(6, 20, -6, -20, -12, 70, 165, 60, 175),
    # PHOEBE's air.X LASER: hanging in the air, the front arm pointing down and forward at 45
    "laser": Pose(14, 100, 15, 40, -50, 45, 45, -40, 60),
    # ERWIN's stand.X THE BOX: ducking down into the box, paws tucked in
    "box_duck": Pose(24, 95, -4, 30, -86, 60, 170, 40, 160),
    # ... and the swipe he pops out of it with: a paw raking low and forward
    "swipe": Pose(18, 70, 10, -20, -50, 80, 75, 30, 150),
    # ERWIN's crouch.X POUNCE: stretched out along the leap, paws first, hind legs trailing
    "pounce": Pose(40, 140, 90, -70, -110, 100, 95, 85, 95),
    # ERWIN's air.X BOX DROP: in the air, a paw reaching down in front to let the box go
    "drop": Pose(12, 100, 15, 40, -50, 25, 10, 30, 150),
    # DOS's stand.X FLOPPY (and PASTE): braced, the front fist raised and the back one flung
    # back, out of the drive slot's way (the look's EJECT)
    "eject": Pose(-6, 30, -4, -26, -14, 150, 175, -60, -20),
    # DOS's crouch.X MOUSE CABLE: low, his arm flung forward along the floor after the mouse
    "fling": Pose(18, 95, -4, 30, -86, 75, 85, 20, 150),
    # DOS's air.X CRT DROP: feet together straight down, arms up
    "stomp": Pose(0, 8, 0, -8, 0, 130, 160, -130, -160),
    # DOS's COPY: both fists up in front of the case, holding up the CTRL+C frame
    "copy": Pose(4, 26, -4, -24, -12, 105, 120, 95, 115),
    # M-CUTIE's stand.X AMPLITUDE AMPLIFICATION, charging: hands cupped together in front of her
    # chest (her approved look's CHARGE); the wave leaves with PHOTON's push ("cast")
    "charge": Pose(2, 26, -4, -24, -12, 62, 150, 52, 158),
    # M-CUTIE's crouch.X ION TRAP: crouched, the front hand reaching down to set it on the floor
    "place": Pose(28, 95, -4, 30, -86, 40, 15, 30, 155),
    # M-CUTIE's air.X SPIN: in the air, the front leg straight out, arms flung wide (the look's SPIN)
    "spin": Pose(-4, 92, 92, 24, -60, 60, 150, 30, 150),
}
POSE_NAMES = tuple(POSES)

BASE_BONES = {"torso": 26, "neck": 9, "shoulder": 22, "upper_arm": 13, "forearm": 13, "thigh": 17, "shin": 17}
BUILD_BONES = {
    "heavy": {"neck": 6},                   # the heavy's helmet sits down between its shoulders
    "toy": {"thigh": 18, "shin": 18, "forearm": 13, "upper_arm": 13, "neck": 8},   # PHOEBE: long limbs
    # ERWIN: ROBERT's height, a big head on a short neck; the long shin holds two cat-leg
    # segments (the lower leg and the long foot, up to the hock: erwin.py draws the hock)
    "cat": {"torso": 24, "neck": 7, "thigh": 15, "shin": 18, "upper_arm": 12, "forearm": 12},
    # DOS: a tall case on short legs, stubby arms; his "head" joint is the top of the case
    "dos": {"torso": 33, "shoulder": 15, "thigh": 14, "shin": 15, "upper_arm": 10, "forearm": 10, "neck": 4.5},
    # M-CUTIE: PHOEBE's long-limbed build, a little shorter in the body and legs, thinner limbs
    "cutie": {"torso": 22, "shoulder": 19, "thigh": 17, "shin": 17, "upper_arm": 12, "forearm": 12, "neck": 7},
}
SCALE = {"lean": 2.0, "heavy": 2.3, "toy": 2.1, "cat": 2.1, "dos": 2.2, "cutie": 2.1}   # the mockup's proportions: about 130 px tall
HEAD_R = {"lean": 13, "heavy": 15, "toy": 14, "cat": 17, "dos": 15, "cutie": 15}
LIMB_W = {"lean": 12, "heavy": 16, "toy": 12, "cat": 13, "dos": 13, "cutie": 12}
CASE_TILT = 0.3         # DOS's case leans only this much of a pose's lean: the legs do the work
LEAN_SCALE = {"dos": CASE_TILT}
# DOS's arms come out of the case's sides, under the screen: each arm's joints move `front` px
# across the body (towards the face) and `down` px down the screen (the look's numbers)
ARM_SOCKETS = {"dos": {"f": (27.0, 0.0), "b": (-25.0, -4.0)}}


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


def drawn_joints(pose: Pose, build: str, feet: tuple[float, float], facing: int) -> dict[str, tuple[float, float]]:
    """joints() as the build is drawn, and as its hit- and hurtboxes are fitted. DOS: the case
    leans only CASE_TILT of the pose's lean and his arms come out of the case's sides
    (ARM_SOCKETS). Every other build: joints() itself."""
    if build in LEAN_SCALE:
        pose = replace(pose, lean=pose.lean * LEAN_SCALE[build])
    j = joints(pose, build, feet, facing)
    sockets = ARM_SOCKETS.get(build)
    if sockets:
        hip, neck = j["hip"], j["neck"]
        tx, ty = neck[0] - hip[0], neck[1] - hip[1]
        n = math.hypot(tx, ty) or 1.0
        ux, uy = tx / n, ty / n
        fx, fy = -uy * facing, ux * facing
        for side, (front, down) in sockets.items():
            for name in ("shoulder", "elbow", "hand"):
                x, y = j[f"{name}_{side}"]
                j[f"{name}_{side}"] = (x + fx * front, y + fy * front + down)
    return j


# --- which pose, this frame -----------------------------------------------------------------


def _smooth(k: float) -> float:
    return k * k * (3 - 2 * k)


def _rest(slot: str | None, f: Fighter) -> str:
    """The pose a move starts from and settles back into."""
    if slot is not None and slot.startswith("air"):
        return "jump"
    if slot is not None and slot.startswith("crouch"):
        return "crouch"
    if slot is None and f.crouching:
        return "crouch"
    return "idle"


def _stance_pose(f: Fighter) -> Pose:
    return POSES["crouch" if f.crouching else "idle"]


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
    if a == "jump":
        return POSES["jump"]
    if a == "charging":         # AMPLITUDE AMPLIFICATION: held, hands cupped, while it charges
        return POSES["charge"]
    if a == "hitstun":
        if f.stun <= EASE_FRAMES:
            return lerp(_stance_pose(f), POSES["hitstun"], f.stun / (EASE_FRAMES + 1))
        return POSES["hitstun"]
    if a == "knockdown":
        down = lerp(POSES["hitstun"], POSES["knockdown"], (f.frame + 1) / FALL_FRAMES)
        if f.stun <= GET_UP_FRAMES:      # get up into the stance
            return lerp(_stance_pose(f), down, _smooth(f.stun / GET_UP_FRAMES))
        return down
    # idle and crouch breathe: a small dip towards the crouch
    base = _stance_pose(f) if a == "crouch" else POSES["idle"]
    k = 0.5 - 0.5 * math.cos(2 * math.pi * f.frame / BREATH_FRAMES)
    return lerp(base, POSES["crouch"] if a != "crouch" else POSES["low_wind"], 0.05 * k)
