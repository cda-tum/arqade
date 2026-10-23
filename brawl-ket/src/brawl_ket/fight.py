"""One round between two fighters: hits, projectiles, hitstop, the clock.

Pure logic, no pygame. Its only randomness is THE BOX's 50/50s, drawn from the fight's own
random.Random(seed): the same inputs and the same seed always give the same round. The
fight drives two Fighters (fighter.py), spawns and moves the shots, keeps M-CUTIE's traps,
resolves hitboxes against hurtboxes, turns each attack's colour rule into an error
using its attacker's basis at the moment of the hit (basis.py), lets the defender's
basis decide between damage and a block, applies the specials' twists, and reports
everything that happened as Events for the renderer and audio.

Everything is counted in integer frames at 60 Hz. Positions are screen px with
y pointing down for boxes (see Fighter.world_box).
"""

from __future__ import annotations

import random
from dataclasses import dataclass, replace

from . import basis
from .config import (
    BLOCH_EARLY,
    BLOCH_HOP_REACH,
    BLOCK_HITSTOP,
    BODY_MARGIN,
    CRASH_LIVE,
    CRASH_REACH,
    DRIVE_SLOT_Y,
    FLOOR_Y,
    HITSTOP,
    HITSTOP_KNOCKDOWN,
    PASTE_SPEED,
    ROUND_FRAMES,
    STAGE_LEFT,
    STAGE_RIGHT,
    START_X,
    SUPER_FREEZE,
    THROW_SLACK,
    TRAP_ARM,
    TRAP_GRACE,
    TRAP_LIFE,
    TRAP_MAX,
    TRAP_REACH,
    TOSS_ARC,
    TOSS_FRAMES,
    TOSS_FROM,
    TOSS_SIZE,
    TOSS_TO,
)
from .echo import Echo
from .fighter import IDLE, STUN_DECAY, Fighter, FighterInput
from .moves import HIGH, LOW, Box, Character, Move
from .superpos import Meter

SHOT_SPAWN_OFFSET = 24      # a shot appears this far in front of its owner, px
LANDING_FRAMES = 4          # how long a landing shockwave stays live

_STUNNED = ("hitstun", "knockdown")

Rect = tuple[float, float, float, float]    # (left, top, w, h), y down


@dataclass(frozen=True)
class Event:
    # attack, hit, block (a wrong-colour hit bounced off), switch (a basis changed: Y, or a
    # DIVE that lands), measure (MEASURE collapsed the rival into its basis), projectile,
    # ko, timeout, land, shockwave (a landing shockwave opens: x/y where it spreads from)
    kind: str
    player: str | None = None       # who it happened TO (hit/block/switch/measure: the one hit)
    error: str | None = None        # X / Z / Y for hit and block (shockwave: its error)
    x: float = 0.0                  # where, for sparks (screen px)
    y: float = 0.0


@dataclass
class Shot:
    owner: str
    move: Move
    x: float
    y: float            # height above the floor, like a fighter's
    vx: float
    life: int
    basis: str = "Z"    # the basis its owner was in when it was fired: its colour, for good
    vy: float = 0.0     # px per frame up (a LASER flies down at 45 degrees)

    @property
    def facing(self) -> int:
        return 1 if self.vx >= 0 else -1

    @property
    def box(self) -> Rect:
        proj = self.move.projectile
        assert proj is not None
        return _world_box(self.x, self.y, self.facing, proj.box)


@dataclass
class Trap:
    """M-CUTIE's ION TRAP on the floor: arming for its first TRAP_ARM frames, then armed until a
    rival on the ground stands in it; then closed (used up), shown for the hold's length. Its
    colour is the basis she was in when she set it, for good. Gone after TRAP_LIFE frames, or
    when its owner is knocked down."""

    owner: str
    move: Move          # the hold it closes with; its hitbox is the catch box, round x
    x: float
    basis: str
    age: int = 0        # frames since it was set
    closed: int = 0     # > 0: closed, this many frames still shown
    held: str | None = None     # ... on whom (None: on an empty box)
    body: Fighter | None = None     # ... and which of their bodies (ALICE & BOB: Alice or Bob)

    @property
    def armed(self) -> bool:
        return not self.closed and self.age >= TRAP_ARM

    @property
    def state(self) -> str:
        return "closed" if self.closed else "armed" if self.armed else "arming"

    @property
    def box(self) -> Rect:
        assert self.move.hitbox is not None
        return _world_box(self.x, 0.0, 1, self.move.hitbox)


@dataclass
class Toss:
    """ALICE & BOB's KEY EXCHANGE in flight: the photon Alice tossed back, flying from her hand to
    Bob's raised one along an arc for TOSS_FRAMES, in the colour she tossed it in. Then he fires
    `shot` (Echo.receive). A rival's body or attack touching it takes it out, as does a rival's
    shot; COPY catches it."""

    owner: str
    shot: Move          # what Bob fires once he has it (KEY_SHOT)
    basis: str
    x0: float           # where it left her hand: x, and height above the floor
    y0: float
    age: int = 0        # frames in the air
    x: float = 0.0      # where its middle is now: x, and height above the floor
    y: float = 0.0

    @property
    def box(self) -> Rect:
        half = TOSS_SIZE / 2
        return (self.x - half, FLOOR_Y - self.y - half, TOSS_SIZE, TOSS_SIZE)


@dataclass
class _Landing:
    """A COLLAPSE-style shockwave window opened when a fighter lands."""

    move: Move
    left: int = LANDING_FRAMES
    hit: bool = False


@dataclass
class _Strike:
    attacker: str | None        # whose move connected; None for a shot or a shockwave
    owner: str                  # whose attack it is (a shot's or a shockwave's too)
    defender: str
    move: Move                  # what take_hit gets (a landing hit has its colour swapped in)
    from_facing: int
    where: tuple[float, float]
    shot: Shot | None = None
    box: frozenset[int] | None = None   # THE BOX: which of the defender's boxes it touched
    trap: Trap | None = None            # ION TRAP: the trap that closes
    target: Fighter | None = None       # the body it lands on (the defender's, or Bob)
    body: Fighter | None = None         # the attacker's body whose move connected (theirs, or Bob)


def _world_box(x: float, y: float, facing: int, box: Box) -> Rect:
    # the same rule as Fighter.world_box
    left = x + box.x if facing >= 0 else x - box.x - box.w
    return (left, FLOOR_Y - (y + box.y + box.h), box.w, box.h)


def _overlap(a: Rect, b: Rect) -> tuple[float, float] | None:
    """The centre of the overlap of two rects, or None if they don't overlap."""
    left = max(a[0], b[0])
    right = min(a[0] + a[2], b[0] + b[2])
    top = max(a[1], b[1])
    bottom = min(a[1] + a[3], b[1] + b[3])
    if right <= left or bottom <= top:
        return None
    return ((left + right) / 2, (top + bottom) / 2)


def body_width(a: Character, b: Character) -> float:
    """How close two grounded fighters may stand (px between their x): the push box, each
    standing hurtbox plus BODY_MARGIN. A heavy is broader, so it keeps a lean rival further off."""
    return (a.hurt_stand.w + b.hurt_stand.w) / 2 + 2 * BODY_MARGIN


KO_PUSH = 4.0       # px per frame: a knocked-out fighter flies off at least this fast


def _other(key: str) -> str:
    return "p2" if key == "p1" else "p1"


def can_reach(height: int, target: Fighter) -> bool:
    """Which heights can touch a fighter: a crouch ducks HIGH, a jump clears LOW.

    GAME RULE: on top of the boxes overlapping, a HIGH move never hits a crouching
    fighter and a LOW one never hits an airborne one; MID can't be dodged this way.
    """
    if height == HIGH and target.stance == "crouch":
        return False
    if height == LOW and target.y > 0:
        return False
    return True


class Fight:
    def __init__(self, chars: dict[str, Character], seed: int = 0,
                 meters: dict[str, Meter] | None = None) -> None:
        self.seed = seed
        self.rng = random.Random(seed)      # THE BOX's 50/50s
        # SUPERposition's bars (superpos.py): the match's, so they carry over between rounds
        self.meters = meters if meters is not None else {"p1": Meter(), "p2": Meter()}
        for key, char in chars.items():
            if char.fixed_basis is not None:    # DOS: one green bar
                self.meters[key].one_colour(char.fixed_basis)
        self.fighters: dict[str, Fighter] = {
            "p1": Fighter(chars["p1"], START_X["p1"], 1),
            "p2": Fighter(chars["p2"], START_X["p2"], -1),
        }
        # ALICE & BOB: the second body, Bob, an echo of Alice's inputs (echo.py)
        self.echoes: dict[str, Echo] = {key: Echo(chars[key].pair, f) for key, f in self.fighters.items()
                                        if chars[key].pair is not None}
        self.body_width = body_width(chars["p1"], chars["p2"])
        for f in (*self.fighters.values(), *self.echoes.values()):   # a throw reaches a little past the push box
            f.throw_range = self.body_width + THROW_SLACK
            f.body_width = self.body_width
            f.rng = self.rng
        self.shots: list[Shot] = []
        self.traps: list[Trap] = []         # M-CUTIE's, oldest first
        self.tosses: list[Toss] = []        # ALICE & BOB's KEY EXCHANGE photons in flight
        self.trap_grace: dict[Fighter, int] = {}    # a body just let go of a hold: frames no trap can catch it
        self.frames_left = ROUND_FRAMES
        self.ticks = 0                      # frames the fight has moved (not a call's freeze or a hitstop):
                                            # what the renderer ages its lingering art by
        self.hitstop = 0
        self.freeze = 0                     # SUPERposition: frames of the call left (nothing moves)
        self.supers: list[str] = []         # ... whose call it is, and who fired on the same frame after them
        self.super_ko = False               # the round ended on a super
        self._fired: set[str] = set()       # who fired this frame (Bob forgets those presses)
        self._up = {"p1": False, "p2": False}   # who was in the air last frame (a BLOCH SPHERE's hop)
        self.over = False
        self.winner: str | None = None      # None with over: a draw round
        self._landings: dict[str, _Landing] = {}

    def bodies(self, key: str) -> list[Fighter]:
        """A player's bodies in the fight: their fighter, and Bob while he is here."""
        echo = self.echoes.get(key)
        f = self.fighters[key]
        return [f, echo] if echo is not None and echo.here else [f]

    # --- the frame --------------------------------------------------------------------

    def step(self, inputs: dict[str, FighterInput]) -> list[Event]:
        if self.over:
            self._settle()
            return []
        if self.freeze > 0:                 # a super's call: nothing moves, the clock included
            self.freeze -= 1
            if self.freeze == 0:
                self.supers.pop(0)
                if self.supers:             # another super fired on the same frame: its call
                    self.freeze = SUPER_FREEZE
            return []
        if self.hitstop > 0:
            self.hitstop -= 1
            # Nothing moves in the freeze, but presses still count (chain cancels).
            for key, f in self.fighters.items():
                f.buffer_presses(inputs.get(key, IDLE))
                f.hold_switch(inputs.get(key, IDLE))
            for key, echo in self.echoes.items():      # Bob's echo runs on through the freeze
                late = echo.replay(inputs.get(key, IDLE))
                if self._in_super(key):
                    echo.forget_presses()
                    continue
                if echo.here:
                    echo.buffer_presses(late)
                    echo.hold_switch(late)
            return []

        events: list[Event] = []
        self.ticks += 1
        self._move_tosses(events)       # first: a toss thrown this frame shows in her hand
        self._step_fighters(inputs, events)
        self._push_apart()
        self._hop_spheres()
        self._move_shots(events)
        self._catch(events)
        self._intercept(events)
        self._deliver(events)
        self._resolve_hits(events)
        self._step_traps()
        self.frames_left -= 1
        self._check_end(events)
        return events

    # --- fighters, shots --------------------------------------------------------------

    def _step_fighters(self, inputs: dict[str, FighterInput], events: list[Event]) -> None:
        # Both fighters see where the rival stood at the START of the frame, so p1 and
        # p2 are treated alike (p1 stepping first must not change what p2 sees).
        start_x = {key: f.x for key, f in self.fighters.items()}
        for key, echo in self.echoes.items():
            self.fighters[key].paired = echo.here     # her X and TELEPORT need Bob
        self._fired = set()
        for key, f in self.fighters.items():
            f.rival_boxes = self._reach(_other(key))
            f.super_ready = self.meters[key].full
            self._fighter_events(key, f, f.step(inputs.get(key, IDLE), start_x[_other(key)]), events)
        for key, echo in self.echoes.items():     # Bob after Alice: he faces as she now does
            late = echo.replay(inputs.get(key, IDLE))
            if key in self._fired or self._in_super(key):
                echo.forget_presses()                   # a super is one move for both: Bob echoes none of it
                late = replace(late, a=False, b=False, x=False)
            echo.rival_boxes = self._reach(_other(key))
            self._fighter_events(key, echo, echo.step(late, start_x[_other(key)]), events)

    def _hop_spheres(self) -> None:
        """BLOCH SPHERE (the user's ruling after the second playtest): a rival who takes off more than
        BLOCH_EARLY frames before the sphere would reach them jumped early, and once they are within
        BLOCH_HOP_REACH px it hops at them, rising to meet them; one who jumps as it arrives sees it
        roll under them. One hop a jump."""
        for key, f in self.fighters.items():
            m, rival = f.move, self.fighters[_other(key)]
            took_off = rival.y > 0 and not self._up[_other(key)]
            if f.action == "attack" and m is not None and m.hop and f.phase in ("startup", "active"):
                ahead = (rival.x - f.x) * f.facing
                if took_off:            # frames until its front reaches their body
                    reach = m.hitbox.x + m.hitbox.w + rival.char.hurt_stand.w / 2
                    arrive = max(0, f.startup - f.frame) + max(0.0, ahead - reach) / m.lunge
                    f.early_jump = arrive > BLOCH_EARLY
                if f.early_jump and f.phase == "active" and f.y == 0 and rival.y > 0 \
                        and 0 < ahead <= BLOCH_HOP_REACH:
                    f.vy = (2 * f.char.gravity * max(30.0, rival.y)) ** 0.5     # up to where they are
                    f.early_jump = False
        self._up = {key: f.y > 0 for key, f in self.fighters.items()}

    def _in_super(self, key: str) -> bool:
        """This player's fighter is doing their super (ALICE & BOB: Bob echoes no press meanwhile)."""
        m = self.fighters[key].move
        return m is not None and m.kind == "super"

    def _reach(self, key: str) -> tuple[float, ...] | None:
        """Where a throw can reach this player's fighter: either of THE BOX's boxes, or any of
        their bodies (ALICE & BOB); None when it is just their x."""
        f = self.fighters[key]
        if f.boxed:
            return f.boxes
        bodies = self.bodies(key)
        return tuple(b.x for b in bodies) if len(bodies) > 1 else None

    def _fighter_events(self, key: str, f: Fighter, local: list[tuple[str, dict]], events: list[Event]) -> None:
        """A body's own events this frame, turned into the fight's: shots, traps and the rest."""
        for kind, data in local:
            if kind == "projectile":
                move = data["move"]
                proj = move.projectile
                assert proj is not None
                speed = proj.speed
                if data.get("paste"):   # PASTE: level, from his drive slot, in the colour it was fired in
                    slot_y = f.y if proj.floor else f.y + DRIVE_SLOT_Y - proj.box.y    # a wave stays on the floor
                    y, vy, shot_basis = slot_y, 0.0, data["basis"]
                    speed = max(speed, PASTE_SPEED)     # a pasted BOX DROP flies too
                else:
                    y, vy, shot_basis = f.y, proj.vy, f.attack_basis
                self.shots.append(Shot(
                    key, move, f.x + f.facing * SHOT_SPAWN_OFFSET, y,
                    speed * f.facing, proj.lifetime, shot_basis, vy,
                ))
                events.append(Event("projectile", key))
            elif kind == "trap":
                self._set_trap(key, f, data["move"])
            elif kind == "pass":        # KEY EXCHANGE: the toss leaves her hand
                x0, y0 = f.x + f.facing * TOSS_FROM[0], f.y + TOSS_FROM[1]
                self.tosses.append(Toss(key, data["move"].toss, f.attack_basis, x0, y0, x=x0, y=y0))
            elif kind == "super":
                self._fire(key, events)
            elif kind == "crash":
                self._crash(key, f, data["move"], events)
            elif kind == "lock":
                self._lock(key, f, data["move"], events)
            elif kind == "swap":
                self._teleport(key, events)
            else:
                events.append(Event(kind, key))
                if kind == "land" and data["dive"] and f.move is not None \
                        and f.move.landing is not None:
                    self._landings[key] = _Landing(f.move)
                    error = basis.error_for(f.move.landing_colour, f.attack_basis)
                    events.append(Event("shockwave", key, error, f.x, FLOOR_Y))
                if kind == "land" and f.action == "attack" and f.move is not None and f.move.crash is not None:
                    events.append(Event("bsod_land", key, None, f.x, FLOOR_Y))
                    if f.move_hit:              # ... on someone: the full blue screen (render.py)
                        events.append(Event("bsod_crash", key, None, f.x, FLOOR_Y))

    def _fire(self, key: str, events: list[Event]) -> None:
        """SUPERposition: the bar empties and the fight freezes SUPER_FREEZE frames for the call
        (a second super fired on the same frame plays its call after this one)."""
        self.meters[key].empty()
        echo = self.echoes.get(key)
        if echo is not None and not echo.here:      # their super brings a decohered Bob back at once
            echo.recohere()
            events.append(Event("recohere", key, None, echo.x, FLOOR_Y))
        self.supers.append(key)
        self.freeze = SUPER_FREEZE
        self._fired.add(key)
        events.append(Event("super", key))
        f = self.fighters[key]
        if f.move is not None and f.move.lock_hold is not None:     # ONE-TIME PAD: caught when it starts
            self._catch_on_fire(key, f, f.move)

    def _lock_missed(self, f: Fighter, rival: Fighter, m: Move) -> bool:
        """A lock misses a rival out of its reach (lock_range), in the air (lock_ground), down,
        getting up, tunnelling or in THE BOX."""
        return rival.action == "knockdown" or bool(rival.wakeup) or rival.intangible or rival.boxed \
            or bool(m.lock_range and abs(rival.x - f.x) > m.lock_range) or (m.lock_ground and rival.y > 0)

    def _catch_on_fire(self, key: str, f: Fighter, m: Move) -> None:
        """ONE-TIME PAD decides its catch the moment A+B fire it, before the call: a rival on the
        ground and in its reach then is held (as a throw holds) through the call and the startup, so
        the call can't warn them off. The flank, or the whiff, comes on its first active frame."""
        rival_key = _other(key)
        rival = self.fighters[rival_key]
        if self._lock_missed(f, rival, m):
            f.target_x = None
            return
        f.target_x = rival.x
        assert m.lock_hold is not None
        for body in self.bodies(rival_key):
            body.take_hit(m.lock_hold, basis.Y, f.facing)

    def _crash(self, key: str, f: Fighter, hold: Move, events: list[Event]) -> None:
        """BLUE SCREEN OF DEATH: every rival body within CRASH_REACH is frozen (the hold: no damage,
        no push) and glitches, on the ground or in the air (the user's ruling: a crash stops
        everything; one frozen in the air hangs there); one beyond it, down, getting up or out of
        reach (TUNNEL, THE BOX) is not. DOS's leap is re-aimed over the highest body frozen in the
        air, to drop straight down on it. With nobody frozen, he comes down where he stands."""
        frozen: list[Fighter] = []
        for body in self.bodies(_other(key)):
            if abs(body.x - f.x) > CRASH_REACH or body.action == "knockdown" \
                    or body.wakeup or body.intangible or body.boxed:
                continue
            body.take_hit(hold, basis.Y, f.facing)
            body.vx = body.vy = 0.0
            body.glitch = hold.hitstun
            frozen.append(body)
            events.append(Event("crash", _other(key), None, body.x, FLOOR_Y - body.y - 140))
        if not frozen:
            f.vx = 0.0
            events.append(Event("crash", None, None, f.x, FLOOR_Y))
        aloft = [b for b in frozen if b.y > 0]
        if aloft:
            b = max(aloft, key=lambda b: b.y)
            g = f.char.gravity
            rise = max(20.0, b.y + 30 - f.y)        # his drop meets their legs (and he stays on screen)
            f.vy = (2 * g * rise) ** 0.5
            f.vx = (b.x - f.x) * g / f.vy           # at them at the top of the leap ...
            f.seek_x, f.drop_air = b.x, True        # ... then straight down (Fighter._move_effects)

    def _lock(self, key: str, f: Fighter, m: Move, events: list[Event]) -> None:
        """A super locks on: its target is where the rival stands now, unless the rival is out of
        reach of it (lock_range), in the air (lock_ground), down, getting up, tunnelling or in THE
        BOX: then it misses (target None). A catch may hold the rival (lock_hold) and put the pair
        either side of them (flank)."""
        rival_key = _other(key)
        rival = self.fighters[rival_key]
        if m.lock_hold is not None:         # ONE-TIME PAD: caught (or not) when it was fired
            missed = f.target_x is None
        else:
            missed = self._lock_missed(f, rival, m)
            f.target_x = None if missed else rival.x
        if missed:
            events.append(Event("lock_miss", key, None, f.x, FLOOR_Y))
            if m.lock_hold is not None:     # they flash and nothing happens: on to its short end
                f.hit_count = m.hits
            return
        assert f.target_x is not None
        events.append(Event("lock", key, None, f.target_x, FLOOR_Y))
        echo = self.echoes.get(key)
        if m.flank and echo is not None:
            side = 1 if rival.x >= f.x else -1
            f.x = _clamp(rival.x - side * m.flank)
            echo.x, echo.y, echo.vy = _clamp(rival.x + side * m.flank), 0.0, 0.0
            f.facing, echo.facing = side, -side
            echo.anchored = True
            events.append(Event("teleport", key, None, f.x, FLOOR_Y))

    def _teleport(self, key: str, events: list[Event]) -> None:
        """Down + X, in two steps. With Bob following, it ANCHORS him: he stays where he stands
        (still echoing her attacks, facing the rival) and the cooldown is given back. With Bob
        anchored, it is TELEPORT: Alice and Bob swap places at once, she turns to face the rival,
        and he follows her again. Nothing happens if Bob decohered in its startup."""
        echo = self.echoes.get(key)
        if echo is None or not echo.here:
            return
        f, rival = self.fighters[key], self.fighters[_other(key)]
        if not echo.anchored:
            echo.anchored = True
            f.cooldowns.pop(f.slot or "crouch.X", None)     # the cooldown runs from the swap
            events.append(Event("anchor", key, None, echo.x, FLOOR_Y))
            return
        echo.anchored = False
        (f.x, f.y), (echo.x, echo.y) = (echo.x, echo.y), (f.x, f.y)
        if rival.x != f.x:
            f.facing = 1 if rival.x > f.x else -1
        echo.facing = f.facing
        events.append(Event("teleport", key, None, f.x, FLOOR_Y))

    def _push_apart(self) -> None:
        """The bodies are solid: two grounded fighters never stand closer than body_width."""
        a, b = self.fighters["p1"], self.fighters["p2"]
        width = self.body_width
        if a.y > 0 or b.y > 0 or a.intangible or b.intangible or a.boxed or b.boxed \
                or abs(b.x - a.x) >= width:
            return
        side = 1 if b.x > a.x else -1 if b.x < a.x else a.facing   # b is on this side of a
        half = (width - abs(b.x - a.x)) / 2
        a.x = _clamp(a.x - side * half)
        b.x = _clamp(b.x + side * half)
        gap = width - abs(b.x - a.x)
        if gap > 0:     # one of them is against a wall: the other takes all of it
            if a.x in (STAGE_LEFT, STAGE_RIGHT):
                b.x = _clamp(b.x + side * gap)
            else:
                a.x = _clamp(a.x - side * gap)

    def _move_shots(self, events: list[Event]) -> None:
        # Collisions are overlap-only after each move, with no sweep, so a projectile
        # faster than about half the combined box widths per frame would tunnel
        # through its target (tests/test_fight.py checks every projectile's speed).
        for s in self.shots:
            s.x += s.vx
            s.y += s.vy
            s.life -= 1
            if s.vy < 0 and s.y + s.move.projectile.box.y <= 0:     # a LASER or a BOX DROP reaches the floor
                s.life = 0
                left, _, w, _ = s.box
                events.append(Event("fizzle", s.owner, None, left + w / 2, FLOOR_Y))
        # shots of different owners cancel each other, with no event; a wave on the floor
        # (M-CUTIE's) cancels any rival shot across its whole column, whatever its height
        dead: set[int] = set()
        for i, s in enumerate(self.shots):
            for j in range(i + 1, len(self.shots)):
                t = self.shots[j]
                if s.owner != t.owner and _overlap(_cancel_box(s), _cancel_box(t)) is not None:
                    dead.update((i, j))
        self.shots = [
            s for i, s in enumerate(self.shots)
            if i not in dead and s.life > 0 and not self._off_stage(s)
        ]

    def _move_tosses(self, events: list[Event]) -> None:
        """KEY EXCHANGE photons fly on towards Bob's raised hand, wherever he is now; one whose
        catcher is gone (decohered) or reeling from a hit fizzles."""
        kept = []
        for t in self.tosses:
            bob = self.echoes[t.owner]
            if not bob.here or bob.action in _STUNNED:
                events.append(Event("fizzle", t.owner, None, t.x, FLOOR_Y - t.y))
                continue
            t.age += 1
            k = min(1.0, t.age / TOSS_FRAMES)
            ex, ey = bob.x + bob.facing * TOSS_TO[0], bob.y + TOSS_TO[1]
            t.x = t.x0 + (ex - t.x0) * k
            t.y = t.y0 + (ey - t.y0) * k + TOSS_ARC * 4 * k * (1 - k)
            kept.append(t)
        self.tosses = kept

    def _intercept(self, events: list[Event]) -> None:
        """Eve listens in: a toss that touches a rival's body (not one downed, getting up or
        tunnelling), a rival's live hitbox or a rival's shot is taken out (the shot with it), and
        nothing fires."""
        kept = []
        for t in self.tosses:
            rival_key = _other(t.owner)
            box = t.box
            hit = None
            for body in self.bodies(rival_key):
                if body.action == "knockdown" or body.wakeup or body.intangible:
                    continue
                rects = body.box_rects() if body.boxed else [body.hurtbox]
                m = body.move
                if m is not None and m.hitbox is not None and body.phase == "active":
                    rects.append(body.world_box(m.hitbox))
                if any(_overlap(box, r) is not None for r in rects):
                    hit = body
                    break
            shot = next((s for s in self.shots if s.owner == rival_key and _overlap(box, s.box) is not None), None)
            if hit is None and shot is None:
                kept.append(t)
                continue
            if shot is not None and hit is None:
                self.shots.remove(shot)
            events.append(Event("intercept", t.owner, None, t.x, FLOOR_Y - t.y))
        self.tosses = kept

    def _deliver(self, events: list[Event]) -> None:
        """A toss that reached Bob's hand: he fires its shot (Echo.receive)."""
        kept = []
        for t in self.tosses:
            if t.age < TOSS_FRAMES:
                kept.append(t)
                continue
            bob = self.echoes[t.owner]
            local: list[tuple[str, dict]] = []
            bob.receive(t.shot, t.basis, local)
            events.append(Event("catch", t.owner, None, t.x, FLOOR_Y - t.y))
            self._fighter_events(t.owner, bob, local, events)
        self.tosses = kept

    def _set_trap(self, key: str, f: Fighter, move: Move) -> None:
        """ION TRAP: a trap on the floor TRAP_REACH px in front of her, in her colour; a third
        of hers replaces the oldest."""
        assert move.trap is not None
        mine = [t for t in self.traps if t.owner == key and not t.closed]
        if len(mine) >= TRAP_MAX:
            self.traps.remove(mine[0])
        self.traps.append(Trap(key, move.trap, _clamp(f.x + f.facing * TRAP_REACH), f.attack_basis))

    def _step_traps(self) -> None:
        """Traps age; a closed one shows for its hold, then goes; all of a knocked-down owner's
        go at once, and an open one after TRAP_LIFE frames."""
        self.trap_grace = {b: n - 1 for b, n in self.trap_grace.items() if n > 1}
        kept = []
        for t in self.traps:
            if self.fighters[t.owner].action == "knockdown":
                continue
            t.age += 1
            if t.closed:
                t.closed -= 1
                if t.closed == 0:
                    if t.body is not None:      # let go: a moment to get away before any trap can close
                        self.trap_grace[t.body] = TRAP_GRACE
                    continue
            elif t.age >= TRAP_LIFE:
                continue
            kept.append(t)
        self.traps = kept

    def _close(self, trap: Trap, held: str | None, events: list[Event], body: Fighter | None = None) -> None:
        trap.closed, trap.held, trap.body = trap.move.hitstun, held, body
        events.append(Event("trap_close", held, None, trap.x, FLOOR_Y))

    @staticmethod
    def _off_stage(s: Shot) -> bool:
        left, _, w, _ = s.box
        return left + w < STAGE_LEFT or left > STAGE_RIGHT

    def _catch(self, events: list[Event]) -> None:
        """COPY: a rival's shot that meets the catch window while it is open is caught, before
        it can hit him: gone from the stage and into his clipboard. So is a rival's crackling
        field (CHARGE NOISE): it stops, and he has it."""
        for key, f in self.fighters.items():
            m = f.move
            if f.action != "attack" or m is None or m.catch is None or f.phase != "active":
                continue
            window = f.world_box(m.catch)
            for s in self.shots:
                where = _overlap(s.box, window) if s.owner != key else None
                if where is not None:
                    self.shots.remove(s)
                    f.caught(s.move, s.basis)
                    events.append(Event("copy", key, None, *where))
                    break
            else:
                for t in self.tosses:       # KEY EXCHANGE's toss, in flight: the shot it would become
                    where = _overlap(t.box, window) if t.owner != key else None
                    if where is not None:
                        self.tosses.remove(t)
                        f.caught(t.shot, t.basis)
                        events.append(Event("copy", key, None, *where))
                        break
                else:
                    self._catch_field(key, f, window, events)

    def _catch_field(self, key: str, f: Fighter, window: Rect, events: list[Event]) -> None:
        """COPY taking a rival's crackling field (CHARGE NOISE)."""
        for rival in self.bodies(_other(key)):
            rm = rival.move
            if rival.action == "attack" and rm is not None and rm.field and rm.hitbox is not None \
                    and rival.phase == "active":
                where = _overlap(rival.world_box(rm.hitbox), window)
                if where is not None:
                    f.caught(rm, rival.attack_basis)
                    rival.frame = rival.startup + rm.active     # its field is gone: into its recovery
                    events.append(Event("copy", key, None, *where))
                    break

    # --- hits ---------------------------------------------------------------------------

    def _resolve_hits(self, events: list[Event]) -> None:
        # Every body of a player strikes at every body of the rival's (ALICE & BOB have two):
        # a move, a shot or a trap lands on the first body it touches, Alice before Bob; a field
        # (CHARGE NOISE) on every body inside it, each its own target.
        strikes: list[_Strike] = []
        for key in self.fighters:
            rival_key = _other(key)
            targets = self.bodies(rival_key)
            for f in self.bodies(key):
                self._move_strike(key, f, rival_key, targets, strikes)
            self._landing_strike(key, self.fighters[key], rival_key, targets, strikes)
        for s in self.shots:
            rival_key = _other(s.owner)
            for target in self.bodies(rival_key):
                if target.action == "knockdown" or target.wakeup or target.intangible:
                    continue        # downed, getting up or tunnelling: shots fly over or through
                if not can_reach(s.move.height, target):
                    continue
                touch = self._touch(s.box, target)
                if touch is not None:
                    strikes.append(_Strike(None, s.owner, rival_key, s.move, s.facing, touch[0], s, box=touch[1],
                                           target=target))
                    break

        caught: set[Fighter] = set()
        for t in self.traps:
            rival_key = _other(t.owner)
            for target in self.bodies(rival_key):
                # a rival on the ground and free to move (one reeling across it is caught once they
                # come to rest in it); not one tunnelling, getting up or knocked down
                if not t.armed or target in caught or target.y > 0 or target.action in _STUNNED \
                        or target.wakeup or target.intangible or self.trap_grace.get(target):
                    continue
                touch = self._touch(t.box, target)
                if touch is not None:
                    caught.add(target)
                    side = 1 if target.x >= t.x else -1
                    strikes.append(_Strike(None, t.owner, rival_key, t.move, side, touch[0], box=touch[1], trap=t,
                                           target=target))
                    break

        traps = [st.trap for st in strikes if st.trap is not None]
        strikes = self._measure(strikes, events)
        for t in traps:         # a trap that measured a box and found him in the other closes empty
            if not any(st.trap is t for st in strikes):
                self._close(t, None, events)

        # Every strike was found against the state at the start of the resolution,
        # so a trade (both fighters connecting on the same frame) applies both.
        for st in strikes:
            if st.body is not None:
                f = st.body
                f.move_hit = True
                f.hit_frame = f.frame       # a repeating move (CHARGE NOISE) counts from here
                f.hit_count += 1

        # A strike on a fighter already knocked down this frame (by a sweep, say) is dropped
        # whole, as if the fighter had been down from the start: no event, no damage, and a
        # shot flies on over them.
        landed_shots: set[int] = set()
        downed: set[Fighter] = set()
        for st in strikes:
            if st.target in downed:
                continue
            if st.shot is not None:
                landed_shots.add(id(st.shot))
            self._apply_strike(st, events, downed)
        self.shots = [s for s in self.shots if id(s) not in landed_shots]

    @staticmethod
    def _touch(rect: Rect, target: Fighter) -> tuple[tuple[float, float], frozenset[int] | None] | None:
        """Where an attack's rect meets the target: its body, or (THE BOX) the first box it
        touches (the set of boxes: an attack can cover both)."""
        if target.boxed:
            hits = {k: w for k, box in enumerate(target.box_rects())
                    if (w := _overlap(rect, box)) is not None}
            if not hits:
                return None
            return hits[min(hits)], frozenset(hits)
        where = _overlap(rect, target.hurtbox)
        return None if where is None else (where, None)

    def _measure(self, strikes: list[_Strike], events: list[Event]) -> list[_Strike]:
        """THE BOX: the first strike that touches a box (a hit, a shot, a throw, a field, a
        shockwave) measures him, 50/50. An attack touching one box: he is in it (it lands on
        him as normal, the colour rule included) or in the other one (it finds nothing: a shot
        flies on). An attack touching both boxes always finds him, whichever he is in. Either way he is free at once, with no swipe. A repeating move's shock that found
        nothing is still spent (CHARGE NOISE: later shocks hit his body)."""
        kept: list[_Strike] = []
        real: dict[str, int] = {}
        for st in strikes:
            if st.box is None:
                kept.append(st)
                continue
            d = st.target
            if st.defender not in real:
                if len(st.box) == 2:
                    k = 0 if self.rng.random() < 0.5 else 1
                else:
                    (only,) = st.box
                    k = only if self.rng.random() < 0.5 else 1 - only
                real[st.defender] = k
                d.collapse(k, False, [])
                events.append(Event("box_collapse", st.defender, None, d.x, FLOOR_Y))
            if real[st.defender] in st.box:
                kept.append(st)
            elif st.body is not None and st.move.hit_every:
                a = st.body
                a.move_hit, a.hit_frame = True, a.frame
        return kept

    def _apply_strike(self, st: _Strike, events: list[Event], downed: set[Fighter]) -> None:
        defender = st.target
        owner = st.body or self.fighters[st.owner]      # the body whose move it is (a shot's: its player)
        x, y = st.where
        m = st.move
        # The colour rule against the basis the attack started in: a move's colour is fixed
        # when it starts (a switch mid-swing doesn't recolour it), as its limb has shown; a
        # shot keeps the colour it was fired in, a shockwave its slam's.
        attack_basis = st.shot.basis if st.shot is not None else st.trap.basis if st.trap is not None \
            else owner.attack_basis
        error = basis.error_for(m.colour, attack_basis)
        before = defender.health
        result = defender.take_hit(m, error, st.from_facing)
        if st.trap is not None:             # ION TRAP: it closes round them, hurt or not
            self._close(st.trap, st.defender, events, defender)
        if defender.char.copy_paste:        # DOS hit: his mouse's cable is cut
            self.shots = [s for s in self.shots if not (s.owner == st.defender and s.move.pull)]
        if m.pull and st.shot is not None:  # MOUSE CABLE: reeled in to just in front of him, hit or not
            to = _clamp(owner.x + owner.facing * self.body_width)
            defender.vx = (to - defender.x) * (1 - STUN_DECAY) / STUN_DECAY   # the stun's slow-down carries it there
        if result == "block":
            events.append(Event("block", st.defender, error, x, y))
            self.hitstop = max(self.hitstop, BLOCK_HITSTOP)
            return
        if defender is self.fighters[st.defender]:
            self._landings.pop(st.defender, None)   # a hit fighter's shockwave is gone
        events.append(Event("hit", st.defender, error, x, y))
        if before > defender.health and m.kind != "super":
            self._fill(st.owner, owner, st.defender, defender, before - defender.health, events)
        knocked = defender.action == "knockdown"
        if m.kind == "super" and defender.health <= 0:
            self.super_ko = True
        if knocked:
            downed.add(defender)
            if isinstance(defender, Echo):  # Bob knocked down decoheres: gone for a while
                defender.decohere()
                events.append(Event("decohere", st.defender, None, defender.x, FLOOR_Y))
        self.hitstop = max(self.hitstop, HITSTOP_KNOCKDOWN if knocked else HITSTOP)
        if m.measure_rival and defender.measured_into(owner.basis):
            # MEASURE projects the rival onto BOHR's basis (never DOS: a classical bit)
            events.append(Event("measure", st.defender, None, x, y))
        if st.body is not None and owner.move is m:
            if m.switch_self_on_hit:        # HADAMARD DIVE: an H on the diver, at once
                owner.switch()
                events.append(Event("switch", st.attacker, None, owner.x, FLOOR_Y - owner.y - 60))
            if m.dive is not None and m.landing is None:
                owner.bounce()              # a DIVE springs back off what it hit

    def _fill(self, key: str, owner: Fighter, defender_key: str, defender: Fighter, damage: int,
              events: list[Event]) -> None:
        """SUPERposition's bars (superpos.py): the attacker's half of the basis it is in (DOS: his one
        green bar), and the one hit's own half at half the rate."""
        for kind in self.meters[key].dealt(owner.basis, damage):
            events.append(Event(f"super_{kind}", key))
        for kind in self.meters[defender_key].taken(defender.basis, damage):
            events.append(Event(f"super_{kind}", defender_key))

    def _move_strike(
        self, key: str, f: Fighter, rival_key: str, targets: list[Fighter], strikes: list[_Strike],
    ) -> None:
        m = f.move
        if m is None or m.hitbox is None or f.phase != "active":
            return
        # a move hits once, except one that repeats (hit_every frames after its last hit, at most
        # `hits` times)
        if f.move_hit and not (m.hit_every and f.frame - f.hit_frame >= m.hit_every):
            return
        if m.hits and f.hit_count >= m.hits:
            return
        if m.remote and f.target_x is None:         # a super's lock that missed: nothing to hit
            return
        if m.seek and (f.vy >= 0 if f.drop_air else f.frame < f.startup + m.seek - 1 - CRASH_LIVE):
            return          # a leap's drop: only as it comes down (on the ground, its last frames)
        for rival in targets:
            if rival.action == "knockdown" or rival.wakeup or rival.intangible:   # downed, getting up, gone
                continue
            if not can_reach(m.height, rival):
                continue
            # GAME RULE: a throw (MEASURE too) can't take a rival already reeling from
            # a hit. A throw is MID, so it catches a jumping rival as well as a crouching one.
            if m.kind == "throw" and rival.action in _STUNNED:
                continue
            box = _world_box(f.target_x, 0.0, f.facing, m.hitbox) if m.remote else f.world_box(m.hitbox)
            touch = self._touch(box, rival)
            if touch is not None:
                where, box = touch
                strikes.append(_Strike(key, key, rival_key, m, f.facing, where, box=box, target=rival, body=f))
                if not m.field:     # a field hits every body inside it
                    return

    def _landing_strike(
        self, key: str, f: Fighter, rival_key: str, targets: list[Fighter], strikes: list[_Strike],
    ) -> None:
        win = self._landings.get(key)
        if win is None:
            return
        if f.action in _STUNNED:
            del self._landings[key]
            return
        move = win.move
        assert move.landing is not None and move.landing_colour is not None
        # the shockwave hits any rival still on its feet, one reeling from the slam itself
        # too (slam and shockwave are opposite colours: a standing rival takes one). A jump
        # clears it.
        for rival in targets:
            if not win.hit and rival.action != "knockdown" and not rival.wakeup and not rival.intangible \
                    and can_reach(move.landing_height, rival):
                touch = self._touch(f.world_box(move.landing), rival)
                if touch is not None:
                    win.hit = True
                    strikes.append(_Strike(
                        None, key, rival_key, replace(move, colour=move.landing_colour, height=move.landing_height),
                        f.facing, touch[0], box=touch[1], target=rival,
                    ))
        win.left -= 1
        if win.left <= 0:
            del self._landings[key]

    # --- the end of the round -----------------------------------------------------------

    def _settle(self) -> None:
        """After the round, the bodies play out (the KO's flight and fall, a move
        finishing) with nobody's input, while nothing else moves: no hits, no clock. The match shows this in slow motion after a KO."""
        if self.hitstop > 0:
            self.hitstop -= 1
            return
        self.ticks += 1
        start_x = {key: f.x for key, f in self.fighters.items()}
        for key, f in self.fighters.items():
            f.step(IDLE, start_x[_other(key)])
        for key, echo in self.echoes.items():
            echo.step(IDLE, start_x[_other(key)])
        self._push_apart()

    def _check_end(self, events: list[Event]) -> None:
        h1 = self.fighters["p1"].health
        h2 = self.fighters["p2"].health
        if h1 <= 0 or h2 <= 0:
            self.over = True
            events.append(Event("ko"))
            self.winner = None if h1 <= 0 and h2 <= 0 else ("p2" if h1 <= 0 else "p1")
            self.shots.clear()
            self.tosses.clear()
            for key, f in self.fighters.items():
                if f.health <= 0:
                    rival = self.fighters[_other(key)]
                    for body in self.bodies(key):       # Bob goes down with her, wherever he is
                        away = 1 if body.x > rival.x else -1 if body.x < rival.x else -body.facing
                        body.knock_out(away, KO_PUSH)
        elif self.frames_left <= 0:
            self.over = True
            events.append(Event("timeout"))
            self.winner = None if h1 == h2 else ("p1" if h1 > h2 else "p2")


def _cancel_box(s: Shot) -> Rect:
    """The box a shot cancels a rival's with: its own, or for a wave on the floor its whole
    column, floor to sky."""
    left, top, w, h = s.box
    if s.move.projectile is not None and s.move.projectile.floor:
        return (left, 0.0, w, float(FLOOR_Y))
    return (left, top, w, h)


def _clamp(x: float) -> float:
    return min(max(x, STAGE_LEFT), STAGE_RIGHT)
