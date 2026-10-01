"""One round between two fighters: hits, projectiles, hitstop, the clock.

Pure logic, no pygame, no randomness: the same inputs always give the same
round. The fight drives two Fighters (fighter.py), spawns and moves the shots,
resolves hitboxes against hurtboxes under the qec rules (the defender's own
code decides whether a hit is corrected or a logical error), ticks both codes
and reports everything that happened as Events for the renderer and audio.

Everything is counted in integer frames at 60 Hz. Positions are screen px with
y pointing down for boxes (see Fighter.world_box).
"""

from __future__ import annotations

from dataclasses import dataclass, replace

from . import qec
from .config import (
    FLOOR_Y,
    HITSTOP,
    HITSTOP_LOGICAL,
    ROUND_FRAMES,
    STAGE_LEFT,
    STAGE_RIGHT,
    START_X,
)
from .fighter import IDLE, Fighter, FighterInput
from .moves import Box, Character, Move

BODY_WIDTH = 28             # fighters can't stand closer than this (push-box), px
SHOT_SPAWN_OFFSET = 24      # a shot appears this far in front of its owner, px
LANDING_FRAMES = 4          # how long a landing shockwave stays live

_STUNNED = ("hitstun", "knockdown")

Rect = tuple[float, float, float, float]    # (left, top, w, h), y down


@dataclass(frozen=True)
class Event:
    # attack, hit, logical, corrected, projectile, switch, ko, timeout, land, reencode
    kind: str
    player: str | None = None       # who it happened TO (hit/logical: the defender)
    error: str | None = None        # X / Z / Y for hit and logical
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
    defender: str
    move: Move                  # what take_hit gets (a landing hit has its error swapped in)
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


def _other(key: str) -> str:
    return "p2" if key == "p1" else "p1"


class Fight:
    def __init__(self, chars: dict[str, Character]) -> None:
        self.fighters: dict[str, Fighter] = {
            "p1": Fighter(chars["p1"], START_X["p1"], 1),
            "p2": Fighter(chars["p2"], START_X["p2"], -1),
        }
        self.shots: list[Shot] = []
        self.frames_left = ROUND_FRAMES
        self.hitstop = 0
        self.over = False
        self.winner: str | None = None      # None with over: a draw round
        self._landings: dict[str, _Landing] = {}

    # --- the frame --------------------------------------------------------------------

    def step(self, inputs: dict[str, FighterInput]) -> list[Event]:
        if self.over:
            return []
        if self.hitstop > 0:
            self.hitstop -= 1
            return []

        events: list[Event] = []
        self._step_fighters(inputs, events)
        self._push_apart()
        self._move_shots()
        self._resolve_hits(events)
        for key, f in self.fighters.items():
            if f.code.tick():
                events.append(Event("corrected", key))
        self.frames_left -= 1
        self._check_end(events)
        return events

    # --- fighters, shots --------------------------------------------------------------

    def _step_fighters(self, inputs: dict[str, FighterInput], events: list[Event]) -> None:
        for key, f in self.fighters.items():
            rival = self.fighters[_other(key)]
            for kind, data in f.step(inputs.get(key, IDLE), rival.x):
                if kind == "projectile":
                    move = data["move"]
                    assert move.projectile is not None
                    self.shots.append(Shot(
                        key, move, f.x + f.facing * SHOT_SPAWN_OFFSET, f.y,
                        move.projectile.speed * f.facing, move.projectile.lifetime,
                    ))
                    events.append(Event("projectile", key))
                else:
                    if kind == "land" and f.move is not None and f.move.landing is not None:
                        self._landings[key] = _Landing(f.move)
                    events.append(Event(kind, key))

    def _push_apart(self) -> None:
        """The bodies are solid: two grounded fighters never stand closer than BODY_WIDTH."""
        a, b = self.fighters["p1"], self.fighters["p2"]
        if a.y > 0 or b.y > 0 or abs(b.x - a.x) >= BODY_WIDTH:
            return
        side = 1 if b.x > a.x else -1 if b.x < a.x else a.facing   # b is on this side of a
        half = (BODY_WIDTH - abs(b.x - a.x)) / 2
        a.x = _clamp(a.x - side * half)
        b.x = _clamp(b.x + side * half)
        gap = BODY_WIDTH - abs(b.x - a.x)
        if gap > 0:     # one of them is against a wall: the other takes all of it
            if a.x in (STAGE_LEFT, STAGE_RIGHT):
                b.x = _clamp(b.x + side * gap)
            else:
                a.x = _clamp(a.x - side * gap)

    def _move_shots(self) -> None:
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
            where = _overlap(s.box, self.fighters[rival_key].hurtbox)
            if where is not None:
                strikes.append(_Strike(None, rival_key, s.move, s.facing, where, s))

        # Every strike was found against the state at the start of the resolution,
        # so a trade (both fighters connecting on the same frame) applies both.
        for st in strikes:
            if st.attacker is not None:
                self.fighters[st.attacker].move_hit = True
        landed_shots = {id(st.shot) for st in strikes if st.shot is not None}
        self.shots = [s for s in self.shots if id(s) not in landed_shots]

        for st in strikes:
            defender = self.fighters[st.defender]
            result = defender.take_hit(st.move, st.from_facing)
            self._landings.pop(st.defender, None)   # a hit fighter's shockwave is gone
            kind = "hit" if result == qec.FLIPPED else "logical"
            events.append(Event(kind, st.defender, st.move.error, st.where[0], st.where[1]))
            stop = HITSTOP if result == qec.FLIPPED else HITSTOP_LOGICAL
            self.hitstop = max(self.hitstop, stop)

    def _move_strike(
        self, key: str, f: Fighter, rival_key: str, rival: Fighter, strikes: list[_Strike],
    ) -> None:
        m = f.move
        if m is None or m.hitbox is None or f.move_hit or f.phase != "active":
            return
        if m.kind == "throw" and (rival.y != 0 or rival.action in _STUNNED):
            return
        where = _overlap(f.world_box(m.hitbox), rival.hurtbox)
        if where is not None:
            strikes.append(_Strike(key, rival_key, m, f.facing, where))

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
        assert move.landing is not None and move.landing_error is not None
        if not win.hit:
            where = _overlap(f.world_box(move.landing), rival.hurtbox)
            if where is not None:
                win.hit = True
                strikes.append(_Strike(
                    None, rival_key, replace(move, error=move.landing_error), f.facing, where,
                ))
        win.left -= 1
        if win.left <= 0:
            del self._landings[key]

    # --- the end of the round -----------------------------------------------------------

    def _check_end(self, events: list[Event]) -> None:
        h1 = self.fighters["p1"].health
        h2 = self.fighters["p2"].health
        if h1 <= 0 or h2 <= 0:
            self.over = True
            events.append(Event("ko"))
            self.winner = None if h1 <= 0 and h2 <= 0 else ("p2" if h1 <= 0 else "p1")
        elif self.frames_left <= 0:
            self.over = True
            events.append(Event("timeout"))
            self.winner = None if h1 == h2 else ("p1" if h1 > h2 else "p2")


def _clamp(x: float) -> float:
    return min(max(x, STAGE_LEFT), STAGE_RIGHT)
