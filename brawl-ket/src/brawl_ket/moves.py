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
    # Startup when a cancel starts the move (None: the same as `startup`). A heavy has a long,
    # telegraphed wind-up from neutral, so a defender can read it, and a fast one inside a chain,
    # where the hit before it has already stunned the rival.
    chain_startup: int | None = None


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
    cycle_frames=config.frames(1.0),
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
            "heavy", 24, 4, 16, Box(14, 64, 40, 18), qec.X,
            chip=6, bonus=14, hitstun=20, knockback=4.0, chain_startup=8,
            poses=("heavy_wind", "heavy_hit", "heavy_recover"),
        ),
        "crouch.A": Move(
            "low jab", 5, 3, 9, Box(12, 20, 44, 12), qec.Z,
            chip=2, bonus=0, hitstun=15, knockback=1.5,
            cancels=("crouch.A", "crouch.B", "stand.B"),
            poses=("low_wind", "low_hit", "low_wind"),
        ),
        "crouch.B": Move(
            "sweep", 24, 4, 18, Box(10, 6, 46, 12), qec.Z,
            chip=6, bonus=14, hitstun=22, knockback=2.0, knockdown=True, chain_startup=9,
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
            kind="projectile", cooldown=config.frames(2.5),
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

QUINT = Character(
    name="QUINT",
    build="heavy",
    distance=5,                         # t = 2: three hits in one cycle to break it
    cycle_frames=config.frames(1.5),    # a bigger code takes longer to measure
    health=100,
    walk=1.5,
    jump_vy=10.5,
    gravity=0.55,                       # an apex of about 100 px: lower and heavier than TRIO's
    hurt_stand=Box(-18, 0, 36, 132),
    hurt_crouch=Box(-20, 0, 40, 104),   # to about the drawn head's centre, as TRIO's
    moves=MappingProxyType({
        "stand.A": Move(
            "jab", 6, 3, 10, Box(16, 76, 46, 16), qec.X,
            chip=2, bonus=0, hitstun=17, knockback=2.0,
            cancels=("stand.A", "stand.B"),
            poses=("jab_wind", "jab_hit", "jab_wind"),
        ),
        "stand.B": Move(
            "heavy", 28, 5, 20, Box(16, 70, 48, 22), qec.X,
            chip=6, bonus=12, hitstun=22, knockback=6.0, chain_startup=11,
            poses=("heavy_wind", "heavy_hit", "heavy_recover"),
        ),
        "crouch.A": Move(
            "low jab", 7, 3, 11, Box(14, 22, 46, 14), qec.Z,
            chip=2, bonus=0, hitstun=16, knockback=2.0,
            cancels=("crouch.A", "crouch.B"),
            poses=("low_wind", "low_hit", "low_wind"),
        ),
        "crouch.B": Move(
            "sweep", 28, 4, 22, Box(12, 6, 54, 14), qec.Z,
            chip=6, bonus=12, hitstun=24, knockback=2.5, knockdown=True, chain_startup=12,
            poses=("sweep_wind", "sweep_hit", "crouch"),
        ),
        "air.A": Move(
            "air jab", 5, 6, 5, Box(12, 54, 30, 20), qec.X,
            chip=2, bonus=0, hitstun=15, knockback=1.5,
            poses=("jump", "air_jab", "jump"),
        ),
        "air.B": Move(
            "jump-in", 8, 6, 8, Box(10, 30, 40, 28), qec.X,
            chip=6, bonus=12, hitstun=20, knockback=3.0,
            poses=("jump", "air_kick", "jump"),
        ),
        "throw": Move(
            "throw", 6, 2, 24, Box(0, 40, 44, 70), qec.Y,
            chip=0, bonus=12, hitstun=30, knockback=6.0, knockdown=True,
            kind="throw",
            poses=("throw_reach", "throw_hold", "idle"),
        ),
        # A lunging command throw: a Y error, so a logical error in either stance. It
        # reaches much further than a throw, but whiffs into a long recovery.
        "stand.X": Move(
            "SYNDROME GRAB", 18, 6, 30, Box(10, 40, 30, 70), qec.Y,
            chip=0, bonus=12, hitstun=30, knockback=6.0, knockdown=True,
            kind="throw", lunge=3.0,
            poses=("grab_wind", "grab", "throw_hold"),
        ),
        # Wipes every flipped light at once (an early correction cycle). It never hits, so
        # it has no hitbox; its error is unused.
        "crouch.X": Move(
            "RE-ENCODE", 6, 1, 18, None, qec.Z,
            chip=0, bonus=0, hitstun=0, knockback=0.0,
            kind="reencode", cooldown=config.frames(4.0),
            poses=("crouch", "brace", "crouch"),
        ),
        # A body slam straight down: the body is an X error, and the landing shockwave
        # deals a Z error to a rival standing near (fight.py, _Landing).
        "air.X": Move(
            "COLLAPSE", 6, 60, 16, Box(-20, 0, 40, 30), qec.X,
            chip=6, bonus=12, hitstun=20, knockback=3.0,
            kind="special", dive=(0.0, 9.0),
            landing=Box(-45, 0, 90, 14), landing_error=qec.Z,
            poses=("jump", "slam", "crouch"),
        ),
    }),
)

CHARACTERS: dict[str, Character] = {"TRIO": TRIO, "QUINT": QUINT}
