"""One round between two fighters: hits, projectiles, hitstop, the clock.

Pure logic, no pygame, no randomness: the same inputs always give the same
round. The fight drives two Fighters (fighter.py), spawns and moves the shots,
resolves hitboxes against hurtboxes, turns each attack's colour rule into an error
using its attacker's basis at the moment of the hit (basis.py), lets the defender's
basis decide between damage and a block, applies the specials' twists, and reports
everything that happened as Events for the renderer and audio.

Everything is counted in integer frames at 60 Hz. Positions are screen px with
y pointing down for boxes (see Fighter.world_box).
"""

from __future__ import annotations

from dataclasses import dataclass, replace

from . import basis
from .config import (
    BLOCK_HITSTOP,
    BODY_MARGIN,
    FLOOR_Y,
    HITSTOP,
    HITSTOP_KNOCKDOWN,
    ROUND_FRAMES,
    STAGE_LEFT,
    STAGE_RIGHT,
    START_X,
    THROW_SLACK,
)
from .fighter import IDLE, Fighter, FighterInput
from .moves import HIGH, LOW, Box, Character, Move

SHOT_SPAWN_OFFSET = 24      # a shot appears this far in front of its owner, px
LANDING_FRAMES = 4          # how long a landing shockwave stays live

_STUNNED = ("hitstun", "knockdown")

Rect = tuple[float, float, float, float]    # (left, top, w, h), y down


@dataclass(frozen=True)
class Event:
    # attack, hit, block (a wrong-colour hit bounced off), switch (a basis changed: Y, a DIVE
    # that lands, a WAVE), measure (MEASURE collapsed the rival into its basis), projectile,
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

    @property
    def facing(self) -> int:
        return 1 if self.vx >= 0 else -1

    @property
    def box(self) -> Rect:
        proj = self.move.projectile
        assert proj is not None
        return _world_box(self.x, self.y, self.facing, proj.box)


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
    def __init__(self, chars: dict[str, Character]) -> None:
        self.fighters: dict[str, Fighter] = {
            "p1": Fighter(chars["p1"], START_X["p1"], 1),
            "p2": Fighter(chars["p2"], START_X["p2"], -1),
        }
        self.body_width = body_width(chars["p1"], chars["p2"])
        for f in self.fighters.values():   # a throw reaches a little past the push box
            f.throw_range = self.body_width + THROW_SLACK
        self.shots: list[Shot] = []
        self.frames_left = ROUND_FRAMES
        self.hitstop = 0
        self.over = False
        self.winner: str | None = None      # None with over: a draw round
        self._landings: dict[str, _Landing] = {}

    # --- the frame --------------------------------------------------------------------

    def step(self, inputs: dict[str, FighterInput]) -> list[Event]:
        if self.over:
            self._settle()
            return []
        if self.hitstop > 0:
            self.hitstop -= 1
            # Nothing moves in the freeze, but presses still count (chain cancels).
            for key, f in self.fighters.items():
                f.buffer_presses(inputs.get(key, IDLE))
            return []

        events: list[Event] = []
        self._step_fighters(inputs, events)
        self._push_apart()
        self._move_shots()
        self._resolve_hits(events)
        self.frames_left -= 1
        self._check_end(events)
        return events

    # --- fighters, shots --------------------------------------------------------------

    def _step_fighters(self, inputs: dict[str, FighterInput], events: list[Event]) -> None:
        # Both fighters see where the rival stood at the START of the frame, so p1 and
        # p2 are treated alike (p1 stepping first must not change what p2 sees).
        start_x = {key: f.x for key, f in self.fighters.items()}
        for key, f in self.fighters.items():
            for kind, data in f.step(inputs.get(key, IDLE), start_x[_other(key)]):
                if kind == "projectile":
                    move = data["move"]
                    assert move.projectile is not None
                    self.shots.append(Shot(
                        key, move, f.x + f.facing * SHOT_SPAWN_OFFSET, f.y,
                        move.projectile.speed * f.facing, move.projectile.lifetime,
                    ))
                    events.append(Event("projectile", key))
                else:
                    events.append(Event(kind, key))
                    if kind == "land" and data["dive"] and f.move is not None \
                            and f.move.landing is not None:
                        self._landings[key] = _Landing(f.move)
                        error = basis.error_for(f.move.landing_colour, f.basis)
                        events.append(Event("shockwave", key, error, f.x, FLOOR_Y))

    def _push_apart(self) -> None:
        """The bodies are solid: two grounded fighters never stand closer than body_width."""
        a, b = self.fighters["p1"], self.fighters["p2"]
        width = self.body_width
        if a.y > 0 or b.y > 0 or abs(b.x - a.x) >= width:
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

    def _move_shots(self) -> None:
        # Collisions are overlap-only after each move, with no sweep, so a projectile
        # faster than about half the combined box widths per frame would tunnel
        # through its target (tests/test_fight.py checks every projectile's speed).
        for s in self.shots:
            s.x += s.vx
            s.life -= 1
        # shots of different owners cancel each other, with no event
        dead: set[int] = set()
        for i, s in enumerate(self.shots):
            for j in range(i + 1, len(self.shots)):
                t = self.shots[j]
                if s.owner != t.owner and _overlap(s.box, t.box) is not None:
                    dead.update((i, j))
        self.shots = [
            s for i, s in enumerate(self.shots)
            if i not in dead and s.life > 0 and not self._off_stage(s)
        ]

    @staticmethod
    def _off_stage(s: Shot) -> bool:
        left, _, w, _ = s.box
        return left + w < STAGE_LEFT or left > STAGE_RIGHT

    # --- hits ---------------------------------------------------------------------------

    def _resolve_hits(self, events: list[Event]) -> None:
        strikes: list[_Strike] = []
        for key, f in self.fighters.items():
            rival_key = _other(key)
            rival = self.fighters[rival_key]
            self._move_strike(key, f, rival_key, rival, strikes)
            self._landing_strike(key, f, rival_key, rival, strikes)
        for s in self.shots:
            rival_key = _other(s.owner)
            target = self.fighters[rival_key]
            if target.action == "knockdown":     # a downed fighter can't be hit; shots fly over
                continue
            if not can_reach(s.move.height, target):
                continue
            where = _overlap(s.box, target.hurtbox)
            if where is not None:
                strikes.append(_Strike(None, s.owner, rival_key, s.move, s.facing, where, s))

        # Every strike was found against the state at the start of the resolution,
        # so a trade (both fighters connecting on the same frame) applies both.
        for st in strikes:
            if st.attacker is not None:
                self.fighters[st.attacker].move_hit = True

        # A strike on a fighter already knocked down this frame (by a sweep, say) is dropped
        # whole, as if the fighter had been down from the start: no event, no damage, and a
        # shot flies on over them.
        landed_shots: set[int] = set()
        downed: set[str] = set()
        for st in strikes:
            if st.defender in downed:
                continue
            if st.shot is not None:
                landed_shots.add(id(st.shot))
            self._apply_strike(st, events, downed)
        self.shots = [s for s in self.shots if id(s) not in landed_shots]

    def _apply_strike(self, st: _Strike, events: list[Event], downed: set[str]) -> None:
        defender = self.fighters[st.defender]
        owner = self.fighters[st.owner]
        x, y = st.where
        m = st.move
        if m.switch_rival:                  # HADAMARD WAVE: an H on the rival, nothing else
            defender.switch()
            events.append(Event("switch", st.defender, None, x, y))
            self.hitstop = max(self.hitstop, BLOCK_HITSTOP)
            return
        # The colour rule against the attacker's basis now: a DIVE's or an A's colour is
        # whatever the attacker is in at the moment of the hit.
        error = basis.error_for(m.colour, owner.basis)
        if defender.take_hit(m, error, st.from_facing) == "block":
            events.append(Event("block", st.defender, error, x, y))
            self.hitstop = max(self.hitstop, BLOCK_HITSTOP)
            return
        self._landings.pop(st.defender, None)   # a hit fighter's shockwave is gone
        events.append(Event("hit", st.defender, error, x, y))
        knocked = defender.action == "knockdown"
        if knocked:
            downed.add(st.defender)
        self.hitstop = max(self.hitstop, HITSTOP_KNOCKDOWN if knocked else HITSTOP)
        if m.measure_rival and defender.basis != owner.basis:
            # MEASURE projects the rival onto QUINT's basis
            defender.basis = owner.basis
            events.append(Event("measure", st.defender, None, x, y))
        if st.attacker is not None and owner.move is m:
            if m.switch_self_on_hit:        # HADAMARD DIVE: an H on the diver, at once
                owner.switch()
                events.append(Event("switch", st.attacker, None, owner.x, FLOOR_Y - owner.y - 60))
            if m.dive is not None and m.landing is None:
                owner.bounce()              # a DIVE springs back off what it hit

    def _move_strike(
        self, key: str, f: Fighter, rival_key: str, rival: Fighter, strikes: list[_Strike],
    ) -> None:
        m = f.move
        if m is None or m.hitbox is None or f.move_hit or f.phase != "active":
            return
        if rival.action == "knockdown":
            return
        if not can_reach(m.height, rival):
            return
        # GAME RULE: a throw (MEASURE too) can't take a rival already reeling from
        # a hit. A throw is MID, so it catches a jumping rival as well as a crouching one.
        if m.kind == "throw" and rival.action in _STUNNED:
            return
        where = _overlap(f.world_box(m.hitbox), rival.hurtbox)
        if where is not None:
            strikes.append(_Strike(key, key, rival_key, m, f.facing, where))

    def _landing_strike(
        self, key: str, f: Fighter, rival_key: str, rival: Fighter, strikes: list[_Strike],
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
        if not win.hit and rival.action != "knockdown" and can_reach(move.landing_height, rival):
            where = _overlap(f.world_box(move.landing), rival.hurtbox)
            if where is not None:
                win.hit = True
                strikes.append(_Strike(
                    None, key, rival_key, replace(move, colour=move.landing_colour, height=move.landing_height),
                    f.facing, where,
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
        start_x = {key: f.x for key, f in self.fighters.items()}
        for key, f in self.fighters.items():
            f.step(IDLE, start_x[_other(key)])
        self._push_apart()

    def _check_end(self, events: list[Event]) -> None:
        h1 = self.fighters["p1"].health
        h2 = self.fighters["p2"].health
        if h1 <= 0 or h2 <= 0:
            self.over = True
            events.append(Event("ko"))
            self.winner = None if h1 <= 0 and h2 <= 0 else ("p2" if h1 <= 0 else "p1")
            self.shots.clear()
            for key, f in self.fighters.items():
                if f.health <= 0:
                    rival = self.fighters[_other(key)]
                    away = 1 if f.x > rival.x else -1 if f.x < rival.x else -f.facing
                    f.knock_out(away, KO_PUSH)
        elif self.frames_left <= 0:
            self.over = True
            events.append(Event("timeout"))
            self.winner = None if h1 == h2 else ("p1" if h1 > h2 else "p2")


def _clamp(x: float) -> float:
    return min(max(x, STAGE_LEFT), STAGE_RIGHT)
