"""Frame data: the dataclasses and each character's move table.

Pure data, no pygame. The fighter state machine (fighter.py) and the fight read
these numbers; nothing here runs. Every duration is an integer count of frames
at 60 Hz.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType

from . import config, shor


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
    error: str                          # shor.X (normals) / shor.Z (specials) / shor.Y (throws)
    # GAME RULE: each hit is exactly one error, on the qubit its move and button choose:
    # the row is the move's height, the column its button's (a Z acts on the whole row).
    height: int                         # shor.HIGH / MID / LOW: the row it lands in, and who dodges it
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
    landing_height: int = shor.LOW      # the shockwave's row
    column: int = shor.A_COL            # the X's column: A, B or THROW (specials: unused)
    cooldown: int = 0
    hurt_active: Box | None = None      # the body's hurtbox in the active frames, if it changes
                                        # (PHASE SLIDE lies low: photons pass over it)
    poses: tuple[str, str, str] = ("idle", "idle", "idle")   # startup / active / recovery
    # Startup when a cancel starts the move (None: the same as `startup`). A heavy has a long,
    # telegraphed wind-up from neutral, so a defender can read it, and a fast one inside a chain,
    # where the hit before it has already stunned the rival.
    chain_startup: int | None = None


@dataclass(frozen=True)
class Character:
    name: str
    build: str                          # "lean" / "heavy" (poses scale)
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
    cycle_frames=config.frames(1.0),
    health=100,
    walk=2.2,
    jump_vy=12.0,
    gravity=0.5,
    hurt_stand=Box(-14, 0, 28, 120),
    hurt_crouch=Box(-16, 0, 32, 100),
    moves=MappingProxyType({
        "stand.A": Move(
            "jab", 4, 3, 8, Box(14, 70, 44, 14), shor.X, shor.HIGH,
            chip=2, bonus=0, hitstun=16, knockback=0.8, lunge=1.5, column=shor.A_COL,
            cancels=("stand.A", "stand.B", "crouch.A"),
            poses=("jab_wind", "jab_hit", "jab_wind"),
        ),
        "stand.B": Move(
            "heavy", 24, 4, 16, Box(14, 64, 40, 18), shor.X, shor.HIGH,
            chip=6, bonus=14, hitstun=20, knockback=4.0, chain_startup=8, lunge=3.0, column=shor.B_COL,
            poses=("heavy_wind", "heavy_hit", "heavy_recover"),
        ),
        "crouch.A": Move(
            "low jab", 5, 3, 9, Box(12, 20, 44, 12), shor.X, shor.LOW,
            chip=2, bonus=0, hitstun=15, knockback=0.8, lunge=1.5, column=shor.A_COL,
            cancels=("crouch.A", "crouch.B", "stand.B"),
            poses=("low_wind", "low_hit", "low_wind"),
        ),
        "crouch.B": Move(
            "sweep", 24, 4, 18, Box(10, 6, 56, 12), shor.X, shor.LOW,
            chip=6, bonus=14, hitstun=22, knockback=2.0, knockdown=True, chain_startup=9, lunge=3.0, column=shor.B_COL,
            poses=("sweep_wind", "sweep_hit", "crouch"),
        ),
        "air.A": Move(
            "air jab", 4, 6, 4, Box(10, 50, 26, 18), shor.X, shor.MID,
            chip=2, bonus=0, hitstun=14, knockback=1.0, column=shor.A_COL,
            poses=("jump", "air_jab", "jump"),
        ),
        "air.B": Move(
            "jump-in", 6, 6, 6, Box(8, 30, 34, 24), shor.X, shor.MID,
            chip=6, bonus=14, hitstun=18, knockback=2.5, column=shor.B_COL,
            poses=("jump", "air_kick", "jump"),
        ),
        "throw": Move(
            "throw", 5, 2, 20, Box(0, 40, 40, 60), shor.Y, shor.MID,
            chip=0, bonus=14, hitstun=30, knockback=5.0, knockdown=True, column=shor.THROW_COL,
            kind="throw",
            poses=("throw_reach", "throw_hold", "idle"),
        ),
        # PHOTON has no hitbox of its own: the projectile carries the box, and
        # the fight applies error/chip/bonus/hitstun/knockback when the shot hits.
        "stand.X": Move(
            "PHOTON", 14, 1, 20, None, shor.Z, shor.HIGH,
            chip=6, bonus=16, hitstun=18, knockback=3.0,
            kind="projectile", cooldown=config.frames(2.5),
            projectile=Projectile(4.0, Box(0, 56, 16, 14), 180),
            poses=("cast_wind", "cast", "cast"),
        ),
        "crouch.X": Move(
            "PHASE SLIDE", 8, 14, 14, Box(6, 4, 40, 14), shor.Z, shor.LOW,
            chip=6, bonus=16, hitstun=20, knockback=3.0, knockdown=True,
            kind="special", lunge=5.0, hurt_active=Box(-74, 0, 130, 50),
            poses=("crouch", "slide", "crouch"),
        ),
        "air.X": Move(
            "DIVE", 3, 40, 8, Box(6, 0, 26, 20), shor.Z, shor.MID,
            chip=6, bonus=16, hitstun=18, knockback=3.0,
            # Steep and fast: 13 px/frame lands about 14 frames after the apex, startup
            # included. The spec's 10 px/frame can't make its ~12 frames: TRIO's jump peaks
            # at about 138 px, so the fall alone would take 14 frames (17 with the startup).
            kind="special", dive=(3.0, 13.0),
            poses=("jump", "dive", "crouch"),
        ),
    }),
)

QUINT = Character(
    name="QUINT",
    build="heavy",
    cycle_frames=config.frames(1.5),    # a bigger code takes longer to measure
    health=100,
    walk=1.5,
    jump_vy=10.5,
    gravity=0.55,                       # an apex of about 100 px: lower and heavier than TRIO's
    hurt_stand=Box(-18, 0, 36, 132),
    hurt_crouch=Box(-20, 0, 40, 104),   # to about the drawn head's centre, as TRIO's
    moves=MappingProxyType({
        "stand.A": Move(
            "jab", 6, 3, 10, Box(16, 76, 46, 16), shor.X, shor.HIGH,
            chip=2, bonus=0, hitstun=17, knockback=1.0, lunge=1.5, column=shor.A_COL,
            cancels=("stand.A", "stand.B"),
            poses=("jab_wind", "jab_hit", "jab_wind"),
        ),
        "stand.B": Move(
            "heavy", 28, 5, 20, Box(16, 70, 48, 22), shor.X, shor.HIGH,
            chip=6, bonus=12, hitstun=22, knockback=6.0, chain_startup=11, lunge=3.0, column=shor.B_COL,
            poses=("heavy_wind", "heavy_hit", "heavy_recover"),
        ),
        "crouch.A": Move(
            "low jab", 7, 3, 11, Box(14, 22, 46, 14), shor.X, shor.LOW,
            chip=2, bonus=0, hitstun=16, knockback=1.0, lunge=1.5, column=shor.A_COL,
            cancels=("crouch.A", "crouch.B"),
            poses=("low_wind", "low_hit", "low_wind"),
        ),
        "crouch.B": Move(
            "sweep", 28, 4, 22, Box(12, 6, 64, 14), shor.X, shor.LOW,
            chip=6, bonus=12, hitstun=24, knockback=2.5, knockdown=True, chain_startup=12, lunge=3.0, column=shor.B_COL,
            poses=("sweep_wind", "sweep_hit", "crouch"),
        ),
        "air.A": Move(
            "air jab", 5, 6, 5, Box(12, 54, 30, 20), shor.X, shor.MID,
            chip=2, bonus=0, hitstun=15, knockback=1.5, column=shor.A_COL,
            poses=("jump", "air_jab", "jump"),
        ),
        "air.B": Move(
            "jump-in", 8, 6, 8, Box(10, 30, 40, 28), shor.X, shor.MID,
            chip=6, bonus=12, hitstun=20, knockback=3.0, column=shor.B_COL,
            poses=("jump", "air_kick", "jump"),
        ),
        "throw": Move(
            "throw", 6, 2, 24, Box(0, 40, 44, 70), shor.Y, shor.MID,
            chip=0, bonus=12, hitstun=30, knockback=6.0, knockdown=True, column=shor.THROW_COL,
            kind="throw",
            poses=("throw_reach", "throw_hold", "idle"),
        ),
        # A dashing command throw: a Z on MID, much further than a throw, but a whiff leaves
        # a long recovery. Reach is measured as the largest starting gap (between the two
        # fighters' x, from a standing start) at which the grab still connects, as the
        # playtest measured "about 75 px": 13 active frames dashing at 6 px/frame, plus the
        # box's 40 px and the rival's hurtbox, reach about 130 px.
        "stand.X": Move(
            "SYNDROME GRAB", 16, 13, 30, Box(10, 40, 30, 70), shor.Z, shor.MID,
            chip=0, bonus=12, hitstun=30, knockback=6.0, knockdown=True,
            kind="throw", lunge=6.0,
            poses=("grab_wind", "grab", "throw_hold"),
        ),
        # An extra correction round, now: it clears every correctable error on QUINT's own
        # grid. It never hits, so it has no hitbox; its error and height are unused.
        "crouch.X": Move(
            "RE-ENCODE", 6, 1, 18, None, shor.Z, shor.MID,
            chip=0, bonus=0, hitstun=0, knockback=0.0,
            kind="reencode", cooldown=config.frames(4.0),
            poses=("crouch", "brace", "crouch"),
        ),
        # A body slam that drifts towards the rival: the body is a Z on HIGH, and the landing
        # shockwave (60 px either side) a Z on LOW (fight.py, _Landing). A rival caught
        # standing takes both, two rows flipped: a logical error.
        "air.X": Move(
            "COLLAPSE", 6, 60, 20, Box(-20, 0, 40, 30), shor.Z, shor.HIGH,
            chip=6, bonus=12, hitstun=20, knockback=3.0,
            kind="special", dive=(2.0, 9.0),
            landing=Box(-60, 0, 120, 14), landing_error=shor.Z,
            poses=("jump", "slam", "crouch"),
        ),
    }),
)

CHARACTERS: dict[str, Character] = {"TRIO": TRIO, "QUINT": QUINT}
