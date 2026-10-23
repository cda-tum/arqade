"""Frame data: the dataclasses and each character's move table.

Pure data, no pygame. The fighter state machine (fighter.py) and the fight read
these numbers; nothing here runs. Every duration is an integer count of frames
at 60 Hz.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field, replace
from types import MappingProxyType

from . import config
from .basis import BOTH, OPPOSITE, OWN, Z_BASIS
from .config import CRASH_HOLD, CRASH_LEAP, DRIVE_SLOT_Y

HIGH, MID, LOW = 0, 1, 2     # a move's height: a crouch ducks HIGH, a jump clears LOW
HEIGHTS = ("HIGH", "MID", "LOW")


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
    speed: float                        # px per frame across, the way the owner faces
    box: Box
    lifetime: int
    vy: float = 0.0                     # px per frame up (< 0: down, like PHOEBE's LASER)
    floor: bool = False                 # it runs along the floor (M-CUTIE's wave): a PASTE keeps it
                                        # there, and it cancels any rival shot it meets across (fight.py)


@dataclass(frozen=True)
class Move:
    name: str
    startup: int
    active: int
    recovery: int                       # frames, all >= 1
    hitbox: Box | None                  # None: no hitbox here (PHOTON's box is the projectile's)
    # The colour rule (basis.py): OWN is the attacker's basis colour when the move started,
    # OPPOSITE the other one; BOTH (a Y) is fixed. A and every special are OWN, B is OPPOSITE,
    # throws are BOTH.
    colour: str
    height: int                         # HIGH / MID / LOW: who dodges it
    damage: int                         # on a hit whose colour matches the defender's
    hitstun: int
    knockback: float                    # px per frame, decaying
    knockdown: bool = False
    cancels: tuple[str, ...] = ()       # slot keys this can be cancelled into on hit
    kind: str = "normal"                # normal / throw / projectile / special / super (SUPERposition:
                                        # a Character's extra["super"], colour BOTH, fired with A+B)
    lunge: float = 0.0                  # vx during active frames (slides, grabs)
    dive: tuple[float, float] | None = None   # (vx, vy) air dive until landing
    projectile: Projectile | None = None
    landing: Box | None = None          # a shockwave hitbox on landing (COLLAPSE)
    landing_colour: str | None = None
    landing_height: int = LOW
    cooldown: int = 0
    hurt_active: Box | None = None      # the body's hurtbox in the active frames, if it changes
                                        # (PHASE SLIDE lies low: photons pass over it)
    poses: tuple[str, str, str] = ("idle", "idle", "idle")   # startup / active / recovery
    # Startup when a cancel starts the move (None: the same as `startup`): a heavy comes out
    # faster inside a chain.
    chain_startup: int | None = None
    # The specials' twists (fight.py applies them when the move lands):
    switch_self_on_hit: bool = False    # HADAMARD DIVE: H on the attacker
    measure_rival: bool = False         # MEASURE: the rival collapses into the attacker's basis
    hit_every: int = 0                  # > 0: hits again this many frames after each hit (CHARGE NOISE, SPIN)
    field: bool = False                 # a field round the body (CHARGE NOISE): COPY catches it, bots back off
    tunnel: bool = False                # TUNNEL: vanish, re-form past the rival (fighter.py)
    hover: bool = False                 # the fall stops through startup and active (LASER)
    once_per_jump: bool = False         # usable once per jump (LASER)
    cue: str | None = None              # a sound event fired on the first active frame
    superpose: bool = False             # THE BOX: he splits into two boxes (fighter.py) until a collapse
    pop_out: Move | None = None         # ... and the swipe he pops out with when he collapses himself
    leap: tuple[float, float] | None = None   # (vx, vy) on the first active frame: an arc (POUNCE)
    pull: bool = False                  # its shot reels the rival in, hit or bounced (MOUSE CABLE: fight.py)
    catch: Box | None = None            # COPY: the window that catches a rival's shot or field (fight.py, _catch)
    paste: bool = False                 # PASTE: fires the clipboard's shot on its first active frame
    # AMPLITUDE AMPLIFICATION: the press starts a charge ("charging", fighter.py) that every
    # further X press grows a step; it fires charge[steps - 1], one wave per step
    charge: tuple[Move, ...] = ()
    trap: Move | None = None            # ION TRAP: sets a trap (fight.py, Trap) that closes with this move
    hold: bool = False                  # a trap's hold: hitstun with no push at all, hurt or not
    floor_recovery: bool = False        # SPIN: its recovery waits for the floor (a miss lands into it)
    # ALICE & BOB (fight.py, Toss; echo.py):
    toss: Move | None = None            # KEY EXCHANGE: a photon tossed back to Bob, who fires this move
    alone: Move | None = None           # ... and the move a press makes instead while Bob is decohered
    swap: bool = False                  # TELEPORT: Alice and Bob swap places (not while he is gone)
    # SUPERposition's twists (fight.py, fighter.py):
    crash: Move | None = None           # BLUE SCREEN OF DEATH: on its first active frame every rival body
                                        # on the ground within CRASH_REACH is held by this move
    seek: int = 0                       # > 0: on its first active frame a leap that comes down on the
                                        # rival this many frames later
    lock: int = -1                      # >= 0: this many frames before the active ones the fight fixes the
                                        # target, the rival's x then (Fighter.target_x) ...
    lock_range: int = 0                 # ... missing a rival further than this (0: any distance) ...
    lock_ground: bool = False           # ... or one in the air (target_x None: a whiff)
    lock_hold: Move | None = None       # a hold the lock puts on the rival it catches (ONE-TIME PAD)
    flank: int = 0                      # ... and the pair re-forms this far either side of them
    remote: bool = False                # the hitbox sits at target_x, not round the fighter
    hits: int = 0                       # > 0: a repeating move (hit_every) hits at most this many times
    follow: Move | None = None          # a move that starts as this one's active frames end (or its
                                        # hits are spent), keeping the target
    warp: int = 0                       # > 0: a follow-up starts this far in front of the target


@dataclass(frozen=True)
class Character:
    name: str
    build: str                          # "lean" / "heavy" / "toy" / "cat" / "dos" / "cutie" / "alice" / "bob"
    health: int
    walk: float
    jump_vy: float
    gravity: float
    hurt_stand: Box
    hurt_crouch: Box
    moves: Mapping[str, Move]           # slot -> Move (read-only)
    fixed_basis: str | None = None      # DOS: always this basis; Y and MEASURE never change it
    copy_paste: bool = False            # DOS: Y is COPY / PASTE (`extra`), not a switch
    extra: Mapping[str, Move] = field(default_factory=lambda: MappingProxyType({}))   # moves outside SLOTS
    pair: Character | None = None       # ALICE & BOB: the second body (BOB), an echo of this one (echo.py)
    # px per frame across in a jump (None: the walk). Every forward jump carries at least 135 px
    # and peaks at least 150 px, so anyone can jump over anyone (the widest stand-off is 64 px,
    # the tallest rival DOS's 140); the heavies' jumps are still the lowest and the shortest.
    air: float | None = None


SLOTS = (
    "stand.A", "stand.B", "stand.X",
    "crouch.A", "crouch.B", "crouch.X",
    "air.A", "air.B", "air.X",
    "throw",
)

ROBERT = Character(
    name="ROBERT",
    build="lean",
    health=100,
    walk=2.4,
    jump_vy=12.95,
    gravity=0.5,
    air=2.9,
    hurt_stand=Box(-14, 0, 28, 120),
    hurt_crouch=Box(-16, 0, 32, 100),
    moves=MappingProxyType({
        "stand.A": Move(
            "jab", 4, 3, 12, Box(14, 70, 44, 14), OWN, HIGH,
            damage=4, hitstun=12, knockback=0.8, lunge=1.5,
            cancels=("stand.B",),
            poses=("jab_wind", "jab_hit", "jab_wind"),
        ),
        "stand.B": Move(
            "heavy", 10, 4, 16, Box(14, 64, 40, 18), OPPOSITE, HIGH,
            damage=8, hitstun=20, knockback=4.0, chain_startup=7, lunge=3.0,
            poses=("heavy_wind", "heavy_hit", "heavy_recover"),
        ),
        "crouch.A": Move(
            "low jab", 4, 3, 13, Box(12, 20, 44, 12), OWN, LOW,
            damage=4, hitstun=12, knockback=0.8, lunge=1.5,
            cancels=("crouch.B", "stand.B"),
            poses=("low_wind", "low_hit", "low_wind"),
        ),
        "crouch.B": Move(
            "sweep", 10, 4, 18, Box(10, 6, 56, 12), OPPOSITE, LOW,
            damage=8, hitstun=22, knockback=2.0, knockdown=True, chain_startup=7, lunge=3.0,
            poses=("sweep_wind", "sweep_hit", "crouch"),
        ),
        "air.A": Move(
            "air jab", 4, 6, 8, Box(10, 50, 26, 18), OWN, MID,
            damage=4, hitstun=14, knockback=1.0,
            poses=("jump", "air_jab", "jump"),
        ),
        "air.B": Move(
            "jump-in", 6, 6, 6, Box(8, 30, 34, 24), OPPOSITE, MID,
            damage=8, hitstun=18, knockback=2.5,
            poses=("jump", "air_kick", "jump"),
        ),
        "throw": Move(
            "throw", 5, 2, 20, Box(0, 40, 40, 60), BOTH, MID,
            damage=10, hitstun=30, knockback=5.0, knockdown=True,
            kind="throw",
            poses=("throw_reach", "throw_hold", "idle"),
        ),
        # PHOTON has no hitbox of its own: the projectile carries the box, and
        # the fight applies error/chip/bonus/hitstun/knockback when the shot hits.
        "stand.X": Move(
            "PHOTON", 14, 1, 20, None, OWN, HIGH,
            damage=10, hitstun=18, knockback=3.0,
            kind="projectile", cooldown=config.frames(2.5),
            projectile=Projectile(4.0, Box(0, 56, 16, 14), 180),
            poses=("cast_wind", "cast", "cast"),
        ),
        "crouch.X": Move(
            "PHASE SLIDE", 8, 14, 14, Box(6, 4, 40, 14), OWN, LOW,
            damage=10, hitstun=20, knockback=3.0, knockdown=True,
            kind="special", lunge=5.0, hurt_active=Box(-74, 0, 130, 50),
            poses=("crouch", "slide", "crouch"),
        ),
        # When it lands, ROBERT switches basis (an H on itself, at once and
        # with no recovery), so its follow-up's colours flip with it: ROBERT's mix-up tool.
        "air.X": Move(
            "HADAMARD DIVE", 3, 40, 8, Box(6, 0, 26, 20), OWN, MID,
            damage=10, hitstun=18, knockback=3.0, switch_self_on_hit=True,
            # Steep and fast: 16 px/frame lands about 14 frames after the apex, startup
            # included (ROBERT's jump now peaks at about 168 px: 11 frames of fall, 3 of startup).
            kind="special", dive=(3.0, 16.0),
            poses=("jump", "dive", "crouch"),
        ),
    }),
)

BOHR = Character(
    name="BOHR",
    build="heavy",
    health=115,                         # slower and broader, so a little sturdier
    walk=1.65,
    jump_vy=13.0,
    gravity=0.55,                       # an apex of about 154 px: lower and heavier than ROBERT's 168
    air=2.9,
    hurt_stand=Box(-18, 0, 36, 132),
    hurt_crouch=Box(-20, 0, 40, 104),   # to about the drawn head's centre, as ROBERT's
    moves=MappingProxyType({
        "stand.A": Move(
            "jab", 6, 3, 14, Box(16, 76, 46, 16), OWN, HIGH,
            damage=4, hitstun=17, knockback=1.0, lunge=1.5,
            cancels=("stand.B",),
            poses=("jab_wind", "jab_hit", "jab_wind"),
        ),
        "stand.B": Move(
            "heavy", 13, 5, 20, Box(16, 70, 48, 22), OPPOSITE, HIGH,
            damage=8, hitstun=22, knockback=6.0, chain_startup=9, lunge=3.0,
            poses=("heavy_wind", "heavy_hit", "heavy_recover"),
        ),
        "crouch.A": Move(
            "low jab", 6, 3, 15, Box(14, 22, 46, 14), OWN, LOW,
            damage=4, hitstun=16, knockback=1.0, lunge=1.5,
            cancels=("crouch.B",),
            poses=("low_wind", "low_hit", "low_wind"),
        ),
        "crouch.B": Move(
            "sweep", 13, 4, 22, Box(12, 6, 64, 14), OPPOSITE, LOW,
            damage=8, hitstun=24, knockback=2.5, knockdown=True, chain_startup=9, lunge=3.0,
            poses=("sweep_wind", "sweep_hit", "crouch"),
        ),
        "air.A": Move(
            "air jab", 5, 6, 9, Box(12, 54, 30, 20), OWN, MID,
            damage=4, hitstun=15, knockback=1.5,
            poses=("jump", "air_jab", "jump"),
        ),
        "air.B": Move(
            "jump-in", 8, 6, 8, Box(10, 30, 40, 28), OPPOSITE, MID,
            damage=8, hitstun=20, knockback=3.0,
            poses=("jump", "air_kick", "jump"),
        ),
        "throw": Move(
            "throw", 6, 2, 24, Box(0, 40, 44, 70), BOTH, MID,
            damage=10, hitstun=30, knockback=6.0, knockdown=True,
            kind="throw",
            poses=("throw_reach", "throw_hold", "idle"),
        ),
        # A dashing command throw: a Y like any throw (it hurts either colour), and it measures
        # the rival into BOHR's basis, so BOHR's A (its own colour) matches them next. Much
        # further than a throw, but a whiff leaves a long recovery. Reach is measured as the largest starting gap (between the two
        # fighters' x, from a standing start) at which the grab still connects, as the
        # playtest measured "about 75 px": 13 active frames dashing at 6 px/frame, plus the
        # box's 40 px and the rival's hurtbox, reach about 130 px.
        "stand.X": Move(
            "MEASURE", 16, 13, 30, Box(10, 40, 30, 70), BOTH, MID,
            damage=12, hitstun=30, knockback=6.0, knockdown=True, measure_rival=True,
            kind="throw", lunge=6.0,
            poses=("grab_wind", "grab", "throw_hold"),
        ),
        # BOHR plants itself and crackles with charge noise (a real source of qubit errors): a
        # field about 60 px all round its body that shocks whoever is inside every 12 frames, for
        # 1 s, in BOHR's colour. MID: it can't be ducked or jumped; the way out is distance (each
        # shock pushes the victim back, and its 8-frame stun leaves 4 free frames before the
        # next) or being the other colour.
        "crouch.X": Move(
            "CHARGE NOISE", 8, 60, 16, Box(-60, 0, 120, 120), OWN, MID,
            damage=3, hitstun=8, knockback=2.0, hit_every=12, field=True,
            kind="special", cooldown=config.frames(3.0),
            poses=("crouch", "brace", "crouch"),
        ),
        # A body slam that drifts towards the rival: the slam and the landing shockwave (60 px
        # either side; fight.py, _Landing) are both BOHR's colour. The slam's box is the legs as
        # drawn, feet to hip; it is MID (a body falling on you can't be ducked), the shockwave
        # LOW (a jump clears it).
        "air.X": Move(
            "COLLAPSE", 6, 60, 20, Box(-28, 0, 56, 75), OWN, MID,
            damage=10, hitstun=20, knockback=3.0,
            kind="special", dive=(2.0, 9.0),
            landing=Box(-60, 0, 120, 14), landing_colour=OWN,
            poses=("jump", "slam", "crouch"),
        ),
    }),
)

PHOEBE = Character(
    name="PHOEBE",
    build="toy",
    health=95,                          # the easiest to hurt: she wins by angles, not by trading
    walk=2.1,
    jump_vy=12.65,
    gravity=0.5,                        # an apex of about 160 px
    air=2.75,
    hurt_stand=Box(-14, 0, 28, 128),
    hurt_crouch=Box(-16, 0, 32, 104),
    moves=MappingProxyType({
        # ROBERT's normals, a frame or two slower and longer: her jab and heavy are long pokes
        "stand.A": Move(
            "jab", 5, 3, 13, Box(14, 84, 60, 14), OWN, HIGH,
            damage=4, hitstun=13, knockback=0.8, lunge=1.5,
            cancels=("stand.B",),
            poses=("jab_wind", "poke_hit", "jab_wind"),
        ),
        "stand.B": Move(
            "heavy", 11, 4, 18, Box(14, 74, 56, 18), OPPOSITE, HIGH,
            damage=8, hitstun=21, knockback=4.0, chain_startup=8, lunge=3.0,
            poses=("heavy_wind", "lunge_hit", "heavy_recover"),
        ),
        "crouch.A": Move(
            "low jab", 5, 3, 14, Box(12, 22, 52, 12), OWN, LOW,
            damage=4, hitstun=13, knockback=0.8, lunge=1.5,
            cancels=("crouch.B", "stand.B"),
            poses=("low_wind", "low_hit", "low_wind"),
        ),
        "crouch.B": Move(
            "sweep", 11, 4, 20, Box(10, 6, 66, 12), OPPOSITE, LOW,
            damage=8, hitstun=23, knockback=2.0, knockdown=True, chain_startup=8, lunge=3.0,
            poses=("sweep_wind", "sweep_hit", "crouch"),
        ),
        "air.A": Move(
            "air jab", 5, 6, 9, Box(10, 52, 34, 18), OWN, MID,
            damage=4, hitstun=14, knockback=1.0,
            poses=("jump", "air_jab", "jump"),
        ),
        "air.B": Move(
            "jump-in", 7, 6, 7, Box(8, 30, 40, 24), OPPOSITE, MID,
            damage=8, hitstun=18, knockback=2.5,
            poses=("jump", "air_kick", "jump"),
        ),
        "throw": Move(
            "throw", 6, 2, 22, Box(0, 40, 44, 64), BOTH, MID,
            damage=10, hitstun=30, knockback=5.0, knockdown=True,
            kind="throw",
            poses=("throw_reach", "throw_hold", "idle"),
        ),
        # A thick laser beam straight up from her raised palms. Its box is the beam, from 150 px
        # up: above every standing hurtbox (BOHR's is the tallest, 132), so it only ever catches
        # someone in the air. The geometry alone makes it an anti-air.
        "stand.X": Move(
            "LIGHT PILLAR", 7, 10, 18, Box(2, 150, 44, 210), OWN, MID,
            damage=10, hitstun=20, knockback=2.0, knockdown=True,
            kind="special", cooldown=config.frames(1.5), cue="pillar",
            poses=("trap_wind", "trap", "trap_wind"),
        ),
        # She tunnels through the rival and re-forms on their far side (fighter.py, _tunnel_target).
        # Startup: she dissolves, hittable for its first TUNNEL_EXPOSED frames; active: gone,
        # with no hurtbox at all; recovery: she re-forms, hittable, the punish window.
        "crouch.X": Move(
            "TUNNEL", 10, 12, 16, None, OWN, MID,
            damage=0, hitstun=1, knockback=0.0,
            kind="special", tunnel=True, cooldown=config.frames(1.8),
            poses=("tunnel", "tunnel", "tunnel"),
        ),
        # She stops in the air for a moment and fires a fast laser down and forward at 45
        # degrees, once per jump. Drawn as a beam from her hand to the shot's head.
        "air.X": Move(
            "LASER", 5, 4, 12, None, OWN, MID,
            damage=8, hitstun=16, knockback=2.0,
            kind="projectile", hover=True, once_per_jump=True, cue="laser",
            projectile=Projectile(14.0, Box(16, 50, 20, 20), 30, vy=-14.0),
            poses=("jump", "laser", "jump"),
        ),
    }),
)

NORMALS = ("stand.A", "stand.B", "crouch.A", "crouch.B", "air.A", "air.B", "throw")
# ... ERWIN's, M-CUTIE's and (fitted to their size) ALICE & BOB's: ROBERT's as they were before his
# own buff (ROBERT_OWN, below)
SHARED_NORMALS = MappingProxyType({slot: ROBERT.moves[slot] for slot in NORMALS})

# THE BOX's two boxes, each around its own x: the drawn box (70 px wide, 48 tall) and his ears
# over its rim. Every standing normal, PHOTON and FLOPPY touch it.
BOX_HURT = Box(-36, 0, 72, 86)

# The quick swipe ERWIN pops out of THE BOX with when he collapses it himself: MID, his colour,
# a short reach (60 px ahead, about a jab's).
BOX_SWIPE = Move(
    "BOX SWIPE", 3, 4, 14, Box(14, 50, 46, 36), OWN, MID,
    damage=8, hitstun=16, knockback=2.5, kind="special",
    poses=("crouch", "swipe", "jab_wind"),
)

ERWIN = Character(
    name="ERWIN",
    build="cat",
    health=90,                          # the least: quick and slippery, and THE BOX is a gamble
    walk=2.55,
    jump_vy=13.05,
    gravity=0.5,                        # an apex of about 170 px: the highest (180 made him win 72%
    air=2.8,                            # against ALICE & BOB: tools/balance.py)
    hurt_stand=Box(-14, 0, 28, 120),    # ROBERT's height
    hurt_crouch=Box(-16, 0, 32, 100),
    moves=MappingProxyType({
        **SHARED_NORMALS,                                   # the shared normals
        # One cat, two places: he ducks into a box (startup, hittable), and on the first active
        # frame it splits into two (fighter.py, _split). Collapsed by him (a press, a new stick
        # direction, or BOX_FRAMES) he pops out with BOX_SWIPE; by the rival, it's a measurement
        # (fight.py, _measure). The cooldown runs from the collapse.
        "stand.X": Move(
            "THE BOX", 8, 1, 4, None, OWN, MID,
            damage=0, hitstun=1, knockback=0.0,
            kind="special", superpose=True, pop_out=BOX_SWIPE, cooldown=config.frames(3.0),
            poses=("box_duck", "box_duck", "box_duck"),
        ),
        # A long, low leap along an arc, which hits on the way. MID: a crouch doesn't save the
        # rival. The active frames outlast the 28-frame arc, so it always lands into its recovery.
        "crouch.X": Move(
            "POUNCE", 8, 30, 20, Box(10, 10, 70, 44), OWN, MID,
            damage=10, hitstun=20, knockback=4.0, knockdown=True,
            kind="special", leap=(6.0, 7.0), cooldown=config.frames(2.0), cue="pounce",
            poses=("crouch", "pounce", "crouch"),
        ),
        # He drops a little cardboard box from the air: it falls straight down just in front of
        # him (MID, his colour) and ends on the floor. Once per jump. It's a shot, so DOS can COPY it.
        "air.X": Move(
            "BOX DROP", 5, 1, 12, None, OWN, MID,
            damage=8, hitstun=16, knockback=2.0,
            kind="projectile", once_per_jump=True, cue="box_drop",
            projectile=Projectile(0.5, Box(-18, 8, 22, 20), 90, vy=-7.0),
            poses=("jump", "drop", "jump"),
        ),
    }),
)

# DOS's super, BLUE SCREEN OF DEATH (SUPERposition, docs/superpowers/specs/2026-10-22-brawl-ket-superposition-
# design.md, 4): every rival on the ground within CRASH_REACH is frozen (a hold, no damage) while an
# error window pops up over them; then he leaps and comes down on them with a giant CRT DROP: MID, 25,
# a knockdown, in either colour (30 since the playtest: section 9). Nobody frozen, he comes down where he stands.
BSOD_HOLD = Move(
    "BLUE SCREEN", 0, 1, 1, None, BOTH, MID,
    damage=0, hitstun=CRASH_HOLD, knockback=0.0, hold=True,
)
BLUE_SCREEN = Move(
    "BLUE SCREEN OF DEATH", 8, CRASH_LEAP + 4, 30, Box(-44, -10, 88, 40), BOTH, MID,
    damage=30, hitstun=30, knockback=3.0, knockdown=True,
    kind="super", crash=BSOD_HOLD, seek=CRASH_LEAP, floor_recovery=True,
    poses=("crouch", "stomp", "crouch"),
)

DOS = Character(
    name="DOS",
    build="dos",
    health=125,                         # the most: big and slow
    walk=1.75,
    jump_vy=12.85,
    gravity=0.55,                       # an apex of about 150 px: the lowest
    air=2.9,
    hurt_stand=Box(-24, 0, 48, 140),    # the case: 54 px wide, its top 144 px up
    hurt_crouch=Box(-26, 0, 52, 112),
    fixed_basis=Z_BASIS,                # a classical bit: always green
    copy_paste=True,
    moves=MappingProxyType({
        # BOHR's frame numbers, but slower jabs (8, not 6: with 125 health, 6 made him too strong);
        # the boxes fit his fists, which come out of the case's sides
        "stand.A": Move(
            "jab", 8, 3, 14, Box(20, 58, 50, 16), OWN, HIGH,
            damage=4, hitstun=17, knockback=1.0, lunge=1.5,
            cancels=("stand.B",),
            poses=("jab_wind", "jab_hit", "jab_wind"),
        ),
        "stand.B": Move(
            "heavy", 13, 5, 20, Box(20, 60, 54, 22), OPPOSITE, HIGH,
            damage=8, hitstun=22, knockback=6.0, chain_startup=9, lunge=3.0,
            poses=("heavy_wind", "heavy_hit", "heavy_recover"),
        ),
        "crouch.A": Move(
            "low jab", 8, 3, 15, Box(18, 20, 48, 14), OWN, LOW,
            damage=4, hitstun=16, knockback=1.0, lunge=1.5,
            cancels=("crouch.B",),
            poses=("low_wind", "low_hit", "low_wind"),
        ),
        "crouch.B": Move(
            "sweep", 13, 4, 22, Box(14, 6, 62, 14), OPPOSITE, LOW,
            damage=8, hitstun=24, knockback=2.5, knockdown=True, chain_startup=9, lunge=3.0,
            poses=("sweep_wind", "sweep_hit", "crouch"),
        ),
        "air.A": Move(
            "air jab", 5, 6, 9, Box(16, 34, 44, 20), OWN, MID,
            damage=4, hitstun=15, knockback=1.5,
            poses=("jump", "air_jab", "jump"),
        ),
        "air.B": Move(
            "jump-in", 8, 6, 8, Box(10, 16, 40, 26), OPPOSITE, MID,
            damage=8, hitstun=20, knockback=3.0,
            poses=("jump", "air_kick", "jump"),
        ),
        "throw": Move(
            "throw", 6, 2, 24, Box(0, 40, 56, 70), BOTH, MID,     # 56: it must reach past his broad push box
            damage=10, hitstun=30, knockback=6.0, knockdown=True,
            kind="throw",
            poses=("throw_reach", "throw_hold", "idle"),
        ),
        # A spinning 3.5" disk out of his drive slot: slower than PHOTON, HIGH like it.
        "stand.X": Move(
            "FLOPPY", 14, 1, 22, None, OWN, HIGH,
            damage=9, hitstun=18, knockback=3.0,
            kind="projectile", cooldown=config.frames(2.5), cue="floppy",
            projectile=Projectile(3.0, Box(0, DRIVE_SLOT_Y, 18, 18), 240),
            poses=("cast_wind", "eject", "eject"),
        ),
        # He flings his mouse out along the floor on its cable (LOW: a jump clears it), about
        # 180 px, and reels in whoever it touches, to just in front of him. The pull happens
        # whatever their colour; the colour rule still decides the damage. He stays planted
        # while the mouse is out (fight.py cuts the cable if he is hit).
        "crouch.X": Move(
            "MOUSE CABLE", 9, 1, 26, None, OWN, LOW,
            damage=6, hitstun=30, knockback=0.0, pull=True,
            kind="projectile", cooldown=config.frames(3.0), cue="mouse",
            projectile=Projectile(12.0, Box(0, 4, 18, 12), 13),
            poses=("crouch", "fling", "crouch"),
        ),
        # A fast stomp straight down; no shockwave. A miss lands into its long recovery.
        "air.X": Move(
            "CRT DROP", 4, 60, 20, Box(-44, 0, 88, 64), OWN, MID,     # his whole case's width, and then some
            damage=12, hitstun=20, knockback=3.0, knockdown=True,
            kind="special", dive=(0.0, 14.0), cue="crt_drop",
            poses=("jump", "stomp", "crouch"),
        ),
    }),
    extra=MappingProxyType({
        # Y with an empty clipboard: a CTRL+C window in front of him for 0.2 s; a rival's shot
        # that meets it is caught (fight.py). A miss leaves him 0.3 s of recovery. The window
        # starts 16 px up: low enough for M-CUTIE's smallest wave (20 px), above the mouse's 16.
        "copy": Move(
            "COPY", 2, 12, 18, None, OWN, MID,
            damage=0, hitstun=1, knockback=0.0, kind="special", catch=Box(14, 16, 40, 114),
            poses=("copy", "copy", "idle"),
        ),
        # Y with a shot in the clipboard: fired straight ahead from his drive slot, at its own
        # speed, in the colour it was fired in.
        "paste": Move(
            "PASTE", 6, 1, 12, None, OWN, HIGH,
            damage=0, hitstun=1, knockback=0.0, kind="special", paste=True, cue="paste",
            poses=("cast_wind", "eject", "eject"),
        ),
        "super": BLUE_SCREEN,
    }),
)

# AMPLITUDE AMPLIFICATION's waves, one per step: (height px, damage). Taller with every step, from
# the floor up, so a small one can be jumped and a big one hardly; MID, so a crouch never ducks it.
AMP_STEPS = ((20, 7), (28, 8), (36, 10), (44, 11), (52, 13), (60, 15))


def _wave(step: int, height: int, damage: int) -> Move:
    """The wave fired at `step`: a microwave drive pulse along the floor, a little slower than
    PHOTON, its box as wide as the pulse's bright middle (cutie.py draws it)."""
    w = 2 * round((12 + 0.42 * height) / 2)
    return Move(
        "AMPLITUDE AMPLIFICATION", 3, 1, 16, None, OWN, MID,
        damage=damage, hitstun=18, knockback=3.0,
        kind="projectile", cooldown=config.frames(2.0), cue=f"wave{step}",
        projectile=Projectile(3.5, Box(-w // 2, 0, w, height), 180, floor=True),
        poses=("charge", "cast", "cast"),
    )


AMP_WAVES = tuple(_wave(n, h, d) for n, (h, d) in enumerate(AMP_STEPS, start=1))

# ION TRAP's hold, round the trap's x: it closes on a rival on the ground who steps between its
# electrodes (LOW: a jump clears it) and holds them for 0.5 s, with no push. The colour rule
# decides the damage, not the hold.
TRAP_HOLD = Move(
    "ION TRAP", 1, 1, 1, Box(-18, 0, 36, 26), OWN, LOW,
    damage=4, hitstun=config.frames(0.5), knockback=0.0, hold=True, kind="special",
)

M_CUTIE = Character(
    name="M-CUTIE",
    build="cutie",
    health=105,                         # in the middle
    walk=2.0,                           # a little slower than ROBERT
    jump_vy=12.65,
    gravity=0.5,                        # an apex of about 160 px: in the middle
    air=2.75,
    hurt_stand=Box(-16, 0, 32, 116),    # a little shorter than ROBERT, and wider: her cage skirt
    hurt_crouch=Box(-18, 0, 36, 92),    # is 60 px across at its hem
    moves=MappingProxyType({
        **SHARED_NORMALS,                                   # the shared normals
        # Each X press is a step: the first starts the charge, she stands still, and the wave
        # fires CHARGE_WAIT frames after the last press or at once at CHARGE_CAP. A hit loses it.
        # The slot's own numbers are the 1-step wave's.
        "stand.X": replace(AMP_WAVES[0], charge=AMP_WAVES),
        # A trap on the floor TRAP_REACH px in front of her (fight.py, Trap): it arms after
        # TRAP_ARM frames and closes on the first rival on the ground who steps in.
        "crouch.X": Move(
            "ION TRAP", 10, 1, 14, None, OWN, LOW,
            damage=0, hitstun=1, knockback=0.0,
            kind="special", trap=TRAP_HOLD, cooldown=config.frames(1.0), cue="trap_set",
            poses=("crouch", "place", "crouch"),
        ),
        # She stops falling and spins forward at her height, the front leg out: 24 frames at
        # 4 px a frame (96 px), hitting every 8 (at most three times). Then she drops, and the
        # recovery waits for the floor.
        "air.X": Move(
            "SPIN", 4, 24, 10, Box(6, 34, 66, 34), OWN, MID,
            damage=4, hitstun=10, knockback=1.0, hit_every=8, lunge=4.0,
            kind="special", hover=True, once_per_jump=True, floor_recovery=True, cue="spin",
            poses=("jump", "spin", "jump"),
        ),
    }),
)

# ALICE & BOB's normals: ROBERT's frame data, every box fitted to the kids' smaller bodies (their
# fists and feet land about 0.7 of ROBERT's height up, and reach about 10 px less far)
KID_BOXES = {
    "stand.A": Box(12, 50, 40, 12), "stand.B": Box(12, 48, 36, 16), "crouch.A": Box(10, 14, 36, 12),
    "crouch.B": Box(8, 4, 44, 12), "air.A": Box(8, 30, 24, 16), "air.B": Box(6, 18, 28, 20),
    "throw": Box(0, 30, 40, 44),
}
KID_NORMALS = MappingProxyType({slot: replace(SHARED_NORMALS[slot], hitbox=box) for slot, box in KID_BOXES.items()})

# KEY EXCHANGE's shot, as Bob fires it once he has caught Alice's toss (fight.py, Toss): one strong
# photon, a little faster than PHOTON and bigger, from his throwing hand, in the colour it was
# tossed in. HIGH, as PHOTON: a crouch ducks it and a jump clears it; DOS can COPY it.
KEY_SHOT = Move(
    "KEY EXCHANGE", 6, 1, 16, None, OWN, HIGH,
    damage=12, hitstun=20, knockback=4.0,
    kind="projectile", cue="key_shot",
    projectile=Projectile(4.5, Box(0, 60, 22, 22), 160),
    poses=("catch", "fire", "fire"),
)

# X while Bob is decohered: Alice fires a plain small photon herself, so X is never dead.
SOLO_PHOTON = Move(
    "PHOTON", 12, 1, 18, None, OWN, HIGH,
    damage=6, hitstun=16, knockback=2.5,
    kind="projectile", cooldown=config.frames(2.5),
    projectile=Projectile(4.0, Box(0, 48, 14, 14), 180),
    poses=("cast_wind", "cast", "cast"),
)

# A steep diving kick, once per jump; Bob's echo of it comes a beat later, so the dive comes twice.
BELL_DIVE = Move(
    "BELL DIVE", 4, 40, 10, Box(6, 0, 24, 18), OWN, MID,
    damage=8, hitstun=18, knockback=3.0,
    kind="special", dive=(3.5, 11.0), once_per_jump=True, cue="bell_dive",
    poses=("jump", "dive", "crouch"),
)

# Bob, the receiver: the second body of ALICE & BOB, never picked on his own. He has the kids'
# normals and BELL DIVE (his echo of Alice's); not her ground specials: he receives KEY EXCHANGE
# (KEY_SHOT) and TELEPORT moves them both.
BOB = Character(
    name="BOB",
    build="bob",
    health=100,                         # the pair's one bar (echo.py: his health is Alice's)
    walk=2.65,
    jump_vy=12.5,
    gravity=0.5,
    air=3.0,
    hurt_stand=Box(-13, 0, 26, 93),     # to about his drawn head's centre (104 px up), as ROBERT's
    hurt_crouch=Box(-15, 0, 30, 77),
    moves=MappingProxyType({**KID_NORMALS, "air.X": BELL_DIVE}),
    extra=MappingProxyType({"catch": KEY_SHOT}),
)

ALICE_BOB = Character(
    name="ALICE & BOB",
    build="alice",                      # Alice's skeleton; Bob is drawn on his own ("bob")
    health=100,                         # one shared bar
    walk=2.65,                          # a little faster than ROBERT (2.4) ...
    jump_vy=12.5,                       # ... and lighter: a quicker, smaller hop, an apex of about 156 px
    gravity=0.5,                        # (ROBERT's 168) and 50 frames in the air (his 52)
    air=3.0,
    hurt_stand=Box(-13, 0, 26, 86),     # to about her drawn head's centre (97 px up), as ROBERT's
    hurt_crouch=Box(-15, 0, 30, 70),
    moves=MappingProxyType({
        **KID_NORMALS,
        # Alice flicks a photon back underhand from her satchel side, along a short arc, into
        # Bob's raised hand (fight.py, Toss: TOSS_FRAMES in the air); he fires KEY_SHOT. A rival's
        # body or attack touching it in flight takes it out; DOS's COPY catches it. Its numbers
        # are the shot's: the toss itself hurts nobody.
        "stand.X": Move(
            "KEY EXCHANGE", 8, 1, 18, None, OWN, HIGH,
            damage=12, hitstun=20, knockback=4.0,
            kind="special", toss=KEY_SHOT, alone=SOLO_PHOTON, cooldown=config.frames(2.5), cue="toss",
            poses=("idle", "toss", "toss"),
        ),
        # Alice and Bob swap places at once, a flash at both ends (fight.py). With the rival
        # between them it crosses them up; away from the rival, a quick step back.
        "crouch.X": Move(
            "TELEPORT", 6, 1, 14, None, OWN, MID,
            damage=0, hitstun=1, knockback=0.0,
            kind="special", swap=True, cooldown=config.frames(2.0),
            poses=("crouch", "idle", "idle"),
        ),
        "air.X": BELL_DIVE,
    }),
    extra=MappingProxyType({"catch": KEY_SHOT, "alone": SOLO_PHOTON}),
    pair=BOB,
)
# --- SUPERposition: the six other supers (docs/superpowers/specs/2026-10-22-brawl-ket-superposition-design.md,
# 4; their look: 2026-10-22-brawl-ket-superposition-looks.py). All BOTH: they hurt either colour.

# ROBERT: BLOCH SPHERE. A Bloch sphere 100 px across forms round him and he rolls in inside it, MID
# (section 9: only a jump whose top clears 100 px gets over it), 4 hits of 5; then an H-gate uppercut (10) flips its arrow to |1>, and him with it.
H_UPPERCUT = Move(
    "H-GATE UPPERCUT", 4, 6, 24, Box(6, 50, 36, 80), BOTH, MID,
    damage=10, hitstun=30, knockback=3.0, knockdown=True, kind="super", switch_self_on_hit=True,
    cue="h_gate", poses=("crouch", "slam", "slam"),
)
BLOCH_SPHERE = Move(
    "BLOCH SPHERE", 8, 50, 1, Box(-50, 0, 100, 100), BOTH, MID,
    damage=5, hitstun=16, knockback=1.0, kind="super", hit_every=6, hits=4, lunge=6.0,
    hurt_active=Box(-50, 0, 100, 100), follow=H_UPPERCUT, cue="bloch",
    poses=("brace", "crouch", "crouch"),
)
# BOHR: WAVEFUNCTION COLLAPSE. A probability cloud spreads over the floor; 12 frames before it
# falls it locks on the rival's x, and a pillar of light falls there: 30, a knockdown.
WAVE_COLLAPSE = Move(
    "WAVEFUNCTION COLLAPSE", 36, 6, 30, Box(-30, 0, 60, 320), BOTH, MID,
    damage=30, hitstun=30, knockback=0.0, knockdown=True, kind="super", lock=12, remote=True,
    cue="collapse", poses=("stomp", "slam", "slam"),
)
# PHOEBE: COHERENT BEAM. A laser straight forward to the screen's edge, floor to 110 px up:
# 5 hits of 6. Only a jump above it passes over.
COHERENT_BEAM = Move(
    "COHERENT BEAM", 12, 60, 30, Box(20, 0, 660, 110), BOTH, MID,
    damage=6, hitstun=16, knockback=1.0, kind="super", hit_every=12, hits=5,
    cue="beam", poses=("throw_reach", "throw_reach", "throw_reach"),
)
# ERWIN: NINE LIVES. Into THE BOX, which splits into nine ERWINs round a rival within 160 px:
# eight ghost pounces, LOW, 2 each, one every 14 frames (section 9: every 8 didn't read); then the real one warps in and swipes (14, a knockdown).
NINE_SWIPE = Move(
    "NINE LIVES", 2, 6, 30, Box(10, 20, 60, 90), BOTH, MID,
    damage=14, hitstun=30, knockback=3.0, knockdown=True, kind="super", warp=40,
    cue="swipe", poses=("swipe", "swipe", "idle"),
)
NINE_LIVES = Move(
    "NINE LIVES", 10, 8 * 14, 1, Box(-40, 0, 80, 40), BOTH, LOW,
    damage=2, hitstun=14, knockback=0.0, kind="super", hit_every=14, hits=8,
    lock=0, lock_range=160, remote=True, follow=NINE_SWIPE, cue="ghosts",
    poses=("box_duck", "box_duck", "box_duck"),
)
# M-CUTIE: DILUTION FRIDGE. A shadow follows the rival and locks 12 frames before a giant gold
# dilution refrigerator lands there (25, a knockdown); then a frosty shockwave, LOW, 150 px
# either side (5) for whoever got out of the shadow.
FROST_WAVE = Move(
    "DILUTION FRIDGE", 1, 6, 30, Box(-150, 0, 300, 30), BOTH, LOW,
    damage=5, hitstun=14, knockback=3.0, kind="super", remote=True,
    poses=("idle", "idle", "idle"),
)
DILUTION_FRIDGE = Move(
    "DILUTION FRIDGE", 42, 4, 1, Box(-35, 0, 70, 320), BOTH, MID,
    damage=25, hitstun=30, knockback=3.0, knockdown=True, kind="super", lock=12, remote=True,
    follow=FROST_WAVE, cue="fridge", poses=("slam", "slam", "slam"),
)
# ALICE & BOB: ONE-TIME PAD. A rival on the ground within 100 px of Alice is held, and the two
# re-form either side of them; the key passes through them six times (3 each), then a padlock
# snaps shut (12, a knockdown).
OTP_HOLD = Move(
    "ONE-TIME PAD", 0, 1, 1, None, BOTH, MID,
    damage=0, hitstun=75, knockback=0.0, hold=True,
)
PADLOCK = Move(
    "ONE-TIME PAD", 2, 4, 30, Box(-30, 0, 60, 140), BOTH, MID,
    damage=12, hitstun=30, knockback=3.0, knockdown=True, kind="super", remote=True,
    cue="padlock", poses=("fire", "fire", "idle"),
)
ONE_TIME_PAD = Move(
    "ONE-TIME PAD", 6, 60, 1, Box(-20, 20, 40, 100), BOTH, MID,
    damage=3, hitstun=14, knockback=0.0, kind="super", hit_every=10, hits=6,
    lock=0, lock_range=100, lock_ground=True, lock_hold=OTP_HOLD, flank=50, remote=True,
    follow=PADLOCK, cue="key_pass", poses=("catch", "fire", "fire"),
)


def _with_super(char: Character, move: Move) -> Character:
    return replace(char, extra=MappingProxyType({**char.extra, "super": move}))


# ROBERT's own numbers (the user's ruling, 2026-10-23: a jab that can't chain into a jab cost his
# jab strings most; this buys some of it back). ERWIN, M-CUTIE and ALICE & BOB were given his
# normals above, before this, and keep them as they were.
ROBERT_OWN = {
    "stand.B": replace(ROBERT.moves["stand.B"], startup=8),        # his heavy 2 frames faster (10)
    "stand.A": replace(ROBERT.moves["stand.A"], recovery=10),      # his jabs 2 frames back of the feel
    "crouch.A": replace(ROBERT.moves["crouch.A"], recovery=11),    # tuning's +4 (12 and 13)
}
ROBERT = replace(ROBERT, moves=MappingProxyType({**ROBERT.moves, **ROBERT_OWN}))
ROBERT = _with_super(ROBERT, BLOCH_SPHERE)
BOHR = _with_super(BOHR, WAVE_COLLAPSE)
PHOEBE = _with_super(PHOEBE, COHERENT_BEAM)
ERWIN = _with_super(ERWIN, NINE_LIVES)
M_CUTIE = _with_super(M_CUTIE, DILUTION_FRIDGE)
ALICE_BOB = _with_super(ALICE_BOB, ONE_TIME_PAD)


CHARACTERS: dict[str, Character] = {"ROBERT": ROBERT, "BOHR": BOHR, "PHOEBE": PHOEBE, "ERWIN": ERWIN, "DOS": DOS,
                                    "M-CUTIE": M_CUTIE, "ALICE & BOB": ALICE_BOB}
