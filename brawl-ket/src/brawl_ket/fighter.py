"""One fighter's state machine: movement, stance, attacks, input buffer, getting hit.

Pure logic, no pygame. The fight (fight.py) runs two of these: it feeds each one
a FighterInput per frame, ticks each fighter's qec.Code (so it can emit the
cycle events), resolves hitboxes and calls take_hit. Everything is counted in
integer frames at 60 Hz.

Coordinates: x is in screen px; y is the height above the floor (>= 0), and
vy > 0 means moving up. world_box() turns a Box (relative to the feet) into
screen px, where y points down.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import NamedTuple

from . import qec
from .config import (
    BUFFER_FRAMES,
    CHAIN_MAX,
    FLOOR_Y,
    LOGICAL_DAMAGE,
    STAGE_LEFT,
    STAGE_RIGHT,
    SWITCH_FRAMES,
    THROW_RANGE,
)
from .moves import Box, Character, Move

TELEGRAPH_FRAMES = 16      # the last frames of a neutral heavy's startup show a glint on the striker
KNOCKDOWN_FRAMES = 40
KO_STUN = 1 << 30          # a knocked-out fighter's knockdown never runs out
STUN_DECAY = 0.85          # vx multiplier per frame of hitstun / knockdown

_STUNNED = ("hitstun", "knockdown")
_GROUND_FREE = ("idle", "walk", "crouch")


@dataclass(frozen=True)
class FighterInput:
    dx: int = 0             # -1 / 0 / 1 (stick, deadzoned)
    up: bool = False
    down: bool = False
    a: bool = False         # a, b, x: pressed this frame
    b: bool = False
    x: bool = False


IDLE = FighterInput()


class Press(NamedTuple):
    """A buffered button press: which button, and how many frames old it is."""

    button: str
    age: int


class Fighter:
    def __init__(self, char: Character, x: float, facing: int) -> None:
        self.char = char
        self.x = float(x)
        self.y = 0.0
        self.vx = 0.0
        self.vy = 0.0
        self.facing = facing
        self.health = char.health
        self.code = qec.Code(char.distance, char.cycle_frames)
        self.action = "idle"        # idle walk crouch switch jump attack hitstun knockdown
        self.frame = 0              # frames into the action (0 on its first frame)
        self.move: Move | None = None
        self.slot: str | None = None
        self.chained = False        # the move in progress was started by a cancel
        self.move_hit = False       # the fight sets this when the move connects
        self.chain = 0              # moves in the current string
        self.stun = 0
        self.switch_left = 0
        self.cooldowns: dict[str, int] = {}
        self.buffer: list[Press] = []   # oldest first
        self.throw_range: float = THROW_RANGE   # the fight sets it from the pairing's push box

    # --- derived state ----------------------------------------------------------------

    @property
    def stance(self) -> str:
        if self.y > 0:
            return "air"
        return "crouch" if self.code.basis == qec.PHASE else "stand"

    @property
    def startup(self) -> int:
        """The startup of the move in progress: its chain_startup when a cancel started it
        (and it has one), else its own. Every phase is computed from this, never from
        move.startup."""
        m = self.move
        assert m is not None
        return m.chain_startup if self.chained and m.chain_startup is not None else m.startup

    @property
    def phase(self) -> str | None:
        m = self.move
        if m is None:
            return None
        startup = self.startup
        if self.frame < startup:
            return "startup"
        if self.frame < startup + m.active:
            return "active"
        if self.frame < startup + m.active + m.recovery:
            return "recovery"
        return None

    @property
    def telegraphing(self) -> bool:
        """In the last TELEGRAPH_FRAMES of the startup of a move that has a long wind-up
        from neutral (not one cancelled into, which comes out fast)."""
        m = self.move
        return (
            m is not None
            and m.chain_startup is not None
            and not self.chained
            and self.action == "attack"
            and self.startup - TELEGRAPH_FRAMES <= self.frame < self.startup
        )

    @property
    def hurtbox(self) -> tuple[float, float, int, int]:
        m = self.move
        if self.action == "attack" and m is not None and m.hurt_active is not None \
                and self.phase == "active":
            return self.world_box(m.hurt_active)
        crouching = self.stance == "crouch"
        return self.world_box(self.char.hurt_crouch if crouching else self.char.hurt_stand)

    def world_box(self, box: Box) -> tuple[float, float, int, int]:
        """(left, top, w, h) in screen px (y down), mirrored when facing left."""
        if self.facing >= 0:
            left = self.x + box.x
        else:
            left = self.x - box.x - box.w
        top = FLOOR_Y - (self.y + box.y + box.h)
        return (left, top, box.w, box.h)

    def can_cancel(self, slot: str) -> bool:
        m = self.move
        return (
            m is not None
            and self.move_hit
            and self.phase in ("active", "recovery")
            and slot in m.cancels
            and self.chain < CHAIN_MAX
        )

    # --- the frame --------------------------------------------------------------------

    def step(self, inp: FighterInput, rival_x: float) -> list[tuple[str, dict]]:
        """Advance one frame; returns local events.

        The qec code's own cycle is NOT ticked here: the fight ticks each code so
        it can report the repairs.
        """
        events: list[tuple[str, dict]] = []
        for slot in self.cooldowns:
            if self.cooldowns[slot] > 0:
                self.cooldowns[slot] -= 1
        self.frame += 1

        # Presses are buffered even during hitstun, so one made in the last frames
        # of stun comes out on the first free frame.
        self.buffer_presses(inp)

        was_stunned = self.action in _STUNNED
        self._advance(events)
        if not was_stunned:         # a stunned fighter is inert for exactly `stun` steps
            self._act(inp, rival_x, events)
        self._physics(events)

        # GAME RULE: presses do not age during the stance switch window, which is
        # longer than BUFFER_FRAMES, so a press made mid-switch comes out when it ends.
        if self.action != "switch":
            self.buffer = [
                Press(p.button, p.age + 1) for p in self.buffer if p.age + 1 < BUFFER_FRAMES
            ]
        return events

    def buffer_presses(self, inp: FighterInput) -> None:
        """Buffer this frame's presses without ageing or advancing anything else.

        The fight calls it during hitstop, when step() is not run, so a press made
        in the freeze (the chain-cancel window) is not lost.
        """
        for btn in ("a", "b", "x"):
            if getattr(inp, btn):
                self.buffer.append(Press(btn, 0))

    def take_hit(self, move: Move, from_facing: int) -> str:
        if self.switch_left > 0:
            # GAME RULE: mid-switch the code is unprotected (see SWITCH_FRAMES)
            result = self.code.logical_error()
            self.switch_left = 0
        else:
            result = self.code.hit(move.error)
        damage = move.chip if result == qec.FLIPPED else LOGICAL_DAMAGE + move.bonus
        self.health = max(0, self.health - damage)

        self.move = None
        self.slot = None
        self.chained = False
        self.move_hit = False
        self.buffer = []
        self.vx = move.knockback * from_facing
        self.frame = 0
        if move.knockdown:
            self.action = "knockdown"
            self.stun = KNOCKDOWN_FRAMES
        else:
            self.action = "hitstun"
            self.stun = move.hitstun
        return result

    def knock_out(self, away: int, push: float) -> None:
        """Down for good: the round is over. Flies off `away` (+1 / -1) at least `push`
        px per frame, whatever hit it, and never gets up."""
        self.move = None
        self.slot = None
        self.chained = False
        self.buffer = []
        if self.action != "knockdown":
            self.action = "knockdown"
            self.frame = 0
        self.stun = KO_STUN
        if self.vx * away < push:
            self.vx = push * away

    # --- internals --------------------------------------------------------------------

    def _set_action(self, action: str) -> None:
        if action != self.action:
            self.action = action
            self.frame = 0

    def _neutral(self) -> None:
        """Go to whatever the fighter does when nothing is happening."""
        if self.y > 0:
            self._set_action("jump")
        elif self.code.basis == qec.PHASE:
            self._set_action("crouch")
        else:
            self._set_action("idle")

    def _diving(self) -> bool:
        m = self.move
        return (
            self.action == "attack" and m is not None and m.dive is not None
            and self.phase == "active"
        )

    def _advance(self, events: list) -> None:
        """Move the current action along: stun, switch window, move frames."""
        if self.action in _STUNNED:
            self.stun -= 1
            self.vx *= STUN_DECAY
            if self.stun <= 0:
                self.stun = 0
                if self.y == 0:
                    self.vx = 0.0
                self._neutral()
        elif self.action == "switch":
            self.switch_left -= 1
            if self.switch_left <= 0:
                self.switch_left = 0
                self._neutral()
        elif self.action == "attack":
            m = self.move
            assert m is not None
            if self.frame >= self.startup + m.active + m.recovery:
                self._end_move()
            else:
                self._move_effects(m, events)

    def _end_move(self) -> None:
        self.move = None
        self.slot = None
        self.chained = False
        self.move_hit = False
        if self.y == 0:
            self.vx = 0.0
        self._neutral()

    def _move_effects(self, m: Move, events: list) -> None:
        if self.phase == "active":
            if self.frame == self.startup:
                if m.kind == "projectile":
                    events.append(("projectile", {"move": m}))
                elif m.kind == "reencode":
                    events.append(("reencode", {"repaired": self.code.reencode()}))
            if m.dive is not None:
                self.vx = m.dive[0] * self.facing
                self.vy = -m.dive[1]
            elif m.lunge:
                self.vx = m.lunge * self.facing
        elif self.y == 0:
            self.vx = 0.0
        elif m.dive is not None and self.frame == self.startup + m.active:
            self.vx = 0.0           # the dive ran out before the floor

    def _slot_for(self, btn: str, dx: int, rival_x: float) -> str:
        if self.y > 0:
            return f"air.{btn.upper()}"
        if btn == "b" and dx == self.facing and abs(rival_x - self.x) <= self.throw_range:
            return "throw"
        prefix = "crouch" if self.stance == "crouch" else "stand"
        return f"{prefix}.{btn.upper()}"

    def _act(self, inp: FighterInput, rival_x: float, events: list) -> None:
        on_ground_free = self.action in _GROUND_FREE
        if on_ground_free and rival_x != self.x:
            self.facing = 1 if rival_x > self.x else -1

        basis = self.code.basis
        wants_switch = (inp.down and basis == qec.BIT) or (not inp.down and basis == qec.PHASE)
        if on_ground_free and wants_switch and not inp.up:
            # Down+A from standing means a LOW attack: the switch goes first and the
            # press stays buffered, to come out as crouch.A when the switch ends.
            self._start_switch(events)
            return

        free = on_ground_free or self.action == "jump"
        if free or self.action == "attack":
            self._try_buffer(inp.dx, rival_x, free, events)

        if self.action not in _GROUND_FREE:
            return
        if inp.up:
            self.vy = self.char.jump_vy
            self.vx = inp.dx * self.char.walk
            self._set_action("jump")
        elif basis == qec.PHASE:
            self.vx = 0.0           # crouching doesn't walk
            self._set_action("crouch")
        else:
            self.vx = inp.dx * self.char.walk
            self._set_action("walk" if inp.dx else "idle")

    def _start_switch(self, events: list) -> None:
        # GAME RULE: the stance switch takes SWITCH_FRAMES during which a hit is a
        # logical error. Physically a transversal H is instantaneous.
        self.code.switch()
        self.switch_left = SWITCH_FRAMES
        self.vx = 0.0
        self._set_action("switch")
        events.append(("switch", {}))

    def _try_buffer(self, dx: int, rival_x: float, free: bool, events: list) -> None:
        for entry in reversed(self.buffer):
            slot = self._slot_for(entry.button, dx, rival_x)
            move = self.char.moves.get(slot)
            if move is None or self.cooldowns.get(slot, 0) > 0:
                continue
            cancel = not free
            if cancel and not self.can_cancel(slot):
                continue
            self._start_move(slot, move, cancel, events)
            return

    def _start_move(self, slot: str, move: Move, cancel: bool, events: list) -> None:
        self.move = move
        self.slot = slot
        self.chained = cancel       # a cancel uses the move's chain_startup, if it has one
        self.move_hit = False
        self.buffer = []            # an older press must not fire a cancel nobody made
        self.chain = self.chain + 1 if cancel else 1
        if move.cooldown > 0:
            self.cooldowns[slot] = move.cooldown
        if self.y == 0:
            self.vx = 0.0
        self.action = "attack"
        self.frame = 0
        events.append(("attack", {"slot": slot}))

    def _physics(self, events: list) -> None:
        landed = False
        if self.y > 0 or self.vy > 0:
            if not self._diving():
                self.vy -= self.char.gravity
            self.y += self.vy
            if self.y <= 0:
                self.y = 0.0
                self.vy = 0.0
                landed = True
        self.x = min(max(self.x + self.vx, STAGE_LEFT), STAGE_RIGHT)
        if landed:
            self._land(events)

    def _land(self, events: list) -> None:
        # "dive": the fighter reached the floor in a dive's active frames (a landing
        # shockwave, like COLLAPSE's, needs the slam; pressed too late, it lands without one)
        events.append(("land", {"dive": self._diving()}))
        m = self.move
        if self.action == "attack" and m is not None:
            self.vx = 0.0
            if m.dive is not None:
                # a dive that reaches the floor skips to its recovery
                self.frame = max(self.frame, self.startup + m.active)
            else:
                self._end_move()    # any other air move is land-cancelled
        elif self.action == "jump":
            self.vx = 0.0
            self._neutral()
