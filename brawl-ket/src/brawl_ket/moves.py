"""Frame data: the dataclasses and each character's move table.

Pure data, no pygame. The fighter state machine (fighter.py) and the fight read
these numbers; nothing here runs. Every duration is an integer count of frames
at 60 Hz.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType

from . import config, qec


@dataclass(frozen=True)
class Box:
    """A rectangle relative to the fighter's feet, facing right (mirrored when facing left).

    x is the left edge; y is the height of the BOTTOM edge above the feet, so
    the box spans x..x+w across and y..y+h upwards.
    """

    x: int
    y: int
    w: int
    h: int


@dataclass(frozen=True)
class Projectile:
    speed: float
    box: Box
    lifetime: int


@dataclass(frozen=True)
class Move:
    name: str
    startup: int
    active: int
    recovery: int                       # frames, all >= 1
    hitbox: Box | None                  # None: no hitbox here (RE-ENCODE; PHOTON's box is the projectile's)
    error: str                          # qec.X / qec.Z / qec.Y
    chip: int                           # damage on a corrected hit
    bonus: int                          # added to LOGICAL_DAMAGE on a logical error
    hitstun: int
    knockback: float                    # px per frame, decaying
    knockdown: bool = False
    cancels: tuple[str, ...] = ()       # slot keys this can be cancelled into on hit
    kind: str = "normal"                # normal / throw / projectile / special / reencode
    lunge: float = 0.0                  # vx during active frames (slides, grabs)
    dive: tuple[float, float] | None = None   # (vx, vy) air dive until landing
    projectile: Projectile | None = None
    landing: Box | None = None          # a shockwave hitbox on landing (COLLAPSE)
    landing_error: str | None = None
    cooldown: int = 0
    poses: tuple[str, str, str] = ("idle", "idle", "idle")   # startup / active / recovery


@dataclass(frozen=True)
class Character:
    name: str
    build: str                          # "lean" / "heavy" (poses scale)
    distance: int
    cycle_frames: int
    health: int
    walk: float
    jump_vy: float
    gravity: float
    hurt_stand: Box
    hurt_crouch: Box
    moves: Mapping[str, Move]           # slot -> Move (read-only)


SLOTS = (
    "stand.A", "stand.B", "stand.X",
    "crouch.A", "crouch.B", "crouch.X",
    "air.A", "air.B", "air.X",
    "throw",
)

TRIO = Character(
    name="TRIO",
    build="lean",
    distance=3,
    cycle_frames=config.frames(2.0),
    health=100,
    walk=2.2,
    jump_vy=12.0,
    gravity=0.5,
    hurt_stand=Box(-14, 0, 28, 120),
    hurt_crouch=Box(-16, 0, 32, 100),
    moves=MappingProxyType({
        "stand.A": Move(
            "jab", 4, 3, 8, Box(14, 70, 44, 14), qec.X,
            chip=2, bonus=0, hitstun=16, knockback=1.5,
            cancels=("stand.A", "stand.B", "crouch.A"),
            poses=("jab_wind", "jab_hit", "jab_wind"),
        ),
        "stand.B": Move(
            "heavy", 8, 4, 16, Box(14, 64, 40, 18), qec.X,
            chip=6, bonus=14, hitstun=20, knockback=4.0,
            poses=("heavy_wind", "heavy_hit", "heavy_wind"),
        ),
        "crouch.A": Move(
            "low jab", 5, 3, 9, Box(12, 20, 44, 12), qec.Z,
            chip=2, bonus=0, hitstun=15, knockback=1.5,
            cancels=("crouch.A", "crouch.B", "stand.B"),
            poses=("low_wind", "low_hit", "low_wind"),
        ),
        "crouch.B": Move(
            "sweep", 9, 4, 18, Box(10, 6, 46, 12), qec.Z,
            chip=6, bonus=14, hitstun=22, knockback=2.0, knockdown=True,
            poses=("sweep_wind", "sweep_hit", "crouch"),
        ),
        "air.A": Move(
            "air jab", 4, 6, 4, Box(10, 50, 26, 18), qec.X,
            chip=2, bonus=0, hitstun=14, knockback=1.0,
            poses=("jump", "air_jab", "jump"),
        ),
        "air.B": Move(
            "jump-in", 6, 6, 6, Box(8, 30, 34, 24), qec.X,
            chip=6, bonus=14, hitstun=18, knockback=2.5,
            poses=("jump", "air_kick", "jump"),
        ),
        "throw": Move(
            "throw", 5, 2, 20, Box(0, 40, 40, 60), qec.Y,
            chip=0, bonus=14, hitstun=30, knockback=5.0, knockdown=True,
            kind="throw",
            poses=("throw_reach", "throw_hold", "idle"),
        ),
        # PHOTON has no hitbox of its own: the projectile carries the box, and
        # the fight applies error/chip/bonus/hitstun/knockback when the shot hits.
        "stand.X": Move(
            "PHOTON", 14, 1, 20, None, qec.X,
            chip=6, bonus=16, hitstun=18, knockback=3.0,
            kind="projectile",
            projectile=Projectile(4.0, Box(0, 56, 16, 14), 180),
            poses=("cast_wind", "cast", "cast"),
        ),
        "crouch.X": Move(
            "PHASE SLIDE", 8, 14, 14, Box(6, 4, 40, 14), qec.Z,
            chip=6, bonus=16, hitstun=20, knockback=3.0, knockdown=True,
            kind="special", lunge=5.0,
            poses=("crouch", "slide", "crouch"),
        ),
        "air.X": Move(
            "DIVE", 4, 40, 10, Box(6, 0, 26, 20), qec.X,
            chip=6, bonus=16, hitstun=18, knockback=3.0,
            kind="special", dive=(4.0, 6.0),
            poses=("jump", "dive", "crouch"),
        ),
    }),
)

CHARACTERS: dict[str, Character] = {"TRIO": TRIO}
