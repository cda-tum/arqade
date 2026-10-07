"""One fighter's state machine: movement, stance, attacks, input buffer, getting hit.

Pure logic, no pygame. The fight (fight.py) runs two of these: it feeds each one
a FighterInput per frame, resolves hitboxes, works out each hit's error from the
attack's colour rule (basis.py) and calls take_hit, which hurts only if the error
changes the fighter's basis state. Everything is counted in integer frames at 60 Hz.

Coordinates: x is in screen px; y is the height above the floor (>= 0), and
vy > 0 means moving up. world_box() turns a Box (relative to the feet) into
screen px, where y points down.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import NamedTuple

from . import basis
from .config import (
    BLOCK_PUSH,
    BUFFER_FRAMES,
    CHAIN_MAX,
    FLOOR_Y,
    STAGE_LEFT,
    STAGE_RIGHT,
    SWITCH_RECOVERY,
    THROW_RANGE,
)
from .moves import Box, Character, Move

KNOCKDOWN_FRAMES = 40
# GAME RULE: a fighter getting up can't be hit for this long, so a knockdown can't be repeated on
# the first frame back up (a sweep that lands every time the rival stands is an infinite).
WAKEUP_FRAMES = 8
KO_STUN = 1 << 30          # a knocked-out fighter's knockdown never runs out
STUN_DECAY = 0.85          # vx multiplier per frame of hitstun / knockdown

_STUNNED = ("hitstun", "knockdown")
_GROUND_FREE = ("idle", "walk", "crouch")


@dataclass(frozen=True)
class FighterInput:
    dx: int = 0             # -1 / 0 / 1 (stick, deadzoned)
    up: bool = False
    down: bool = False
    a: bool = False         # a, b, x, y: pressed this frame
    b: bool = False
    x: bool = False
    y: bool = False         # switch basis (an H on yourself)


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
        self.basis = basis.Z_BASIS      # green: |0>, |1>
        self.switch_lock = 0            # frames left after a switch in which you can't attack
        self.switch_pending = False     # Y pressed in a hitstop freeze: applied on the next step
        self.wakeup = 0                 # frames left of the invulnerability after getting up
        self.attack_basis = self.basis  # the basis the move in progress started in (its colour)
        self.crouching = False
        self.action = "idle"        # idle walk crouch jump attack hitstun knockdown
        self.frame = 0              # frames into the action (0 on its first frame)
        self.move: Move | None = None
        self.slot: str | None = None
        self.chained = False        # the move in progress was started by a cancel
        self.move_hit = False       # the fight sets this when the move connects
        self.hit_frame = 0          # ... and the frame it last connected on
        self.bounced = False        # a DIVE sprang back off a hit: its recovery waits for the floor
        self.chain = 0              # moves in the current string
        self.stun = 0
        self.cooldowns: dict[str, int] = {}
        self.buffer: list[Press] = []   # oldest first
        self.throw_range: float = THROW_RANGE   # the fight sets it from the pairing's push box

    # --- derived state ----------------------------------------------------------------

    @property
    def stance(self) -> str:
        if self.y > 0:
            return "air"
        return "crouch" if self.crouching else "stand"

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

        A Y press switches basis at once, whatever the fighter is doing: walking, attacking,
        reeling from a hit or knocked down.
        """
        events: list[tuple[str, dict]] = []
        for slot in self.cooldowns:
            if self.cooldowns[slot] > 0:
                self.cooldowns[slot] -= 1
        self.frame += 1
        if self.switch_lock > 0:
            self.switch_lock -= 1
        if self.wakeup > 0:
            self.wakeup -= 1
        if inp.y or self.switch_pending:
            self.switch_pending = False
            self.switch()
            self.switch_lock = SWITCH_RECOVERY
            events.append(("switch", {}))

        # Presses are buffered even during hitstun, so one made in the last frames
        # of stun comes out on the first free frame.
        self.buffer_presses(inp)

        was_stunned = self.action in _STUNNED
        self._advance(events)
        if not was_stunned:         # a stunned fighter is inert for exactly `stun` steps
            self._act(inp, rival_x, events)
        self._physics(events)

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

    def hold_switch(self, inp: FighterInput) -> None:
        """A Y pressed in a hitstop freeze (when step() isn't run) switches on the next step."""
        if inp.y:
            self.switch_pending = not self.switch_pending   # two presses in a freeze cancel out

    def take_hit(self, move: Move, error: str, from_facing: int) -> str:
        """An attack dealing `error` reaches this fighter. Returns "hit" if the error changes
        its basis state (damage, stun, knockback, maybe a knockdown), else "block": no damage
        and its state unchanged, but (GAME RULE) block-stun for the move's hitstun and a
        pushback, never a knockdown."""
        hurt = basis.hurts(error, self.basis)
        was_down = self.action == "knockdown"
        if hurt:
            self.health = max(0, self.health - move.damage)

        if self.bounced:            # a diver hit in a trade stops springing up
            self.vy = min(self.vy, 0.0)
        self.move = None
        self.slot = None
        self.chained = False
        self.move_hit = False
        self.bounced = False
        self.buffer = []
        self.vx = (move.knockback if hurt else max(move.knockback, BLOCK_PUSH)) * from_facing
        self.frame = 0
        if was_down:                # a knockdown is never cut short into hitstun
            self.stun = max(self.stun, KNOCKDOWN_FRAMES)
        elif hurt and move.knockdown:
            self.action = "knockdown"
            self.stun = KNOCKDOWN_FRAMES
        else:
            self.action = "hitstun"
            self.stun = move.hitstun
        return "hit" if hurt else "block"

    def switch(self) -> None:
        """An H on yourself: the basis (and so the body's colour) swaps at once."""
        self.basis = basis.hadamard(self.basis)

    BOUNCE_VX, BOUNCE_VY = 2.0, 5.0     # px per frame: a DIVE springs back off what it hit

    def bounce(self) -> None:
        """A dive that connects springs back up and away, and its active frames end.

        The recovery is held at its first frame while the fighter is in the air (_advance),
        so a bounced dive can't attack again in the same jump and always gets its full
        landing recovery.
        """
        m = self.move
        assert m is not None
        self.frame = self.startup + m.active        # straight into the recovery
        self.vx = -self.BOUNCE_VX * self.facing
        self.vy = self.BOUNCE_VY
        self.bounced = True

    def knock_out(self, away: int, push: float) -> None:
        """Down for good: the round is over. Flies off `away` (+1 / -1) at least `push`
        px per frame, whatever hit it, and never gets up."""
        self.move = None
        self.slot = None
        self.chained = False
        self.bounced = False
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
        elif self.crouching:
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
        """Move the current action along: stun, move frames."""
        if self.action in _STUNNED:
            self.stun -= 1
            self.vx *= STUN_DECAY
            if self.stun <= 0:
                self.stun = 0
                if self.y == 0:
                    self.vx = 0.0
                if self.action == "knockdown":
                    self.wakeup = WAKEUP_FRAMES
                self._neutral()
        elif self.action == "attack":
            m = self.move
            assert m is not None
            if self.bounced and self.y > 0:
                self.frame = self.startup + m.active    # the recovery starts on the floor
            if self.frame >= self.startup + m.active + m.recovery:
                self._end_move()
            else:
                self._move_effects(m, events)

    def _end_move(self) -> None:
        self.move = None
        self.slot = None
        self.chained = False
        self.move_hit = False
        self.bounced = False
        if self.y == 0:
            self.vx = 0.0
        self._neutral()

    def _move_effects(self, m: Move, events: list) -> None:
        if self.phase == "active":
            if self.frame == self.startup:
                if m.kind == "projectile":
                    events.append(("projectile", {"move": m}))
            if m.dive is not None:
                self.vx = m.dive[0] * self.facing
                self.vy = -m.dive[1]
            elif m.lunge:
                self.vx = m.lunge * self.facing
        elif self.y == 0:
            self.vx = 0.0
        elif m.dive is not None and self.frame == self.startup + m.active and not self.bounced:
            self.vx = 0.0           # the dive ran out before the floor (a bounce keeps its drift)

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

        if on_ground_free:
            self.crouching = inp.down and not inp.up    # crouching is instant: it's ducking

        free = on_ground_free or self.action == "jump"
        if (free or self.action == "attack") and self.switch_lock == 0:
            self._try_buffer(inp.dx, rival_x, free, events)

        if self.action not in _GROUND_FREE:
            return
        if inp.up:
            self.crouching = False
            self.vy = self.char.jump_vy
            self.vx = inp.dx * self.char.walk
            self._set_action("jump")
        elif self.crouching:
            self.vx = 0.0           # crouching doesn't walk
            self._set_action("crouch")
        else:
            self.vx = inp.dx * self.char.walk
            self._set_action("walk" if inp.dx else "idle")

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
        self.attack_basis = self.basis  # the move's colour is fixed now, whatever comes next
        self.chained = cancel       # a cancel uses the move's chain_startup, if it has one
        self.move_hit = False
        self.bounced = False
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
