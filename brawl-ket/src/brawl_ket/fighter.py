"""One fighter's state machine: movement, stance, attacks, input buffer, getting hit.

Pure logic, no pygame. The fight (fight.py) runs two of these: it feeds each one
a FighterInput per frame, resolves hitboxes, works out each hit's error from the
attack's colour rule (basis.py) and calls take_hit, which hurts only if the error
changes the fighter's basis state. Everything is counted in integer frames at 60 Hz.
THE BOX (ERWIN) is the "boxed" action: superposed in two boxes, with no body; the fight measures him.
AMPLITUDE AMPLIFICATION (M-CUTIE) is the "charging" action: she stands still while X presses grow
the wave, then fires it as an ordinary move.

Coordinates: x is in screen px; y is the height above the floor (>= 0), and
vy > 0 means moving up. world_box() turns a Box (relative to the feet) into
screen px, where y points down.
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from typing import NamedTuple

from . import basis
from .config import (
    BLOCK_PUSH,
    BOX_FRAMES,
    BOX_SPLIT,
    BUFFER_FRAMES,
    CHAIN_MAX,
    CHARGE_CAP,
    CHARGE_WAIT,
    COPY_CAUGHT_RECOVERY,
    FLOOR_Y,
    STAGE_LEFT,
    STAGE_RIGHT,
    SUPER_WINDOW,
    SWITCH_RECOVERY,
    THROW_RANGE,
    TUNNEL_EXPOSED,
    TUNNEL_PAST,
)
from .moves import BOX_HURT, Box, Character, Move

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
        self.basis = char.fixed_basis or basis.Z_BASIS      # green: |0>, |1> (DOS: for good)
        self.switch_lock = 0            # frames left after a switch in which you can't attack
        self.switch_pending = False     # Y pressed in a hitstop freeze: applied on the next step
        self.wakeup = 0                 # frames left of the invulnerability after getting up
        self.attack_basis = self.basis  # the basis the move in progress started in (its colour)
        self.crouching = False
        self.action = "idle"        # idle walk crouch jump attack hitstun knockdown boxed charging
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
        self.body_width: float = THROW_RANGE    # ... and the push box itself (TUNNEL needs room)
        self.clipboard: tuple[Move, str] | None = None      # DOS: the shot COPY caught, and its basis
        self.rival_x = x                # where the rival stood at the start of this frame
        self.tunnel_from = self.x       # TUNNEL: where she dissolved, and where she re-forms
        self.tunnel_to = self.x
        self.air_used: set[str] = set()     # once-per-jump moves used in this jump (LASER)
        self.rng = random.Random(0)     # the fight gives every fighter its own seeded source
        self.stick = (0, False, False)  # last frame's stick (dx, up, down): THE BOX waits for a new one
        self.boxes: tuple[float, float] = (self.x, self.x)  # THE BOX: where he stood, the far box
        self.box_real = 0               # ... the box a collapse found him in (0 or 1)
        self.box_t = 0                  # ... frames superposed
        self.rival_boxes: tuple[float, float] | None = None   # the rival's two boxes while it is boxed
        self.charge = 0                 # AMPLITUDE AMPLIFICATION: steps charged (0: not charging)
        self.charge_wait = 0            # ... frames since the last step's press
        self.paired = False             # ALICE & BOB: Bob is here (the fight sets it every frame)
        self.super_ready = False        # SUPERposition: the bar is full (the fight sets it every frame)

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
    def intangible(self) -> bool:
        """TUNNEL: from the end of its exposed frames until it re-forms, she has no hurtbox:
        nothing can touch her, shots and hits pass through."""
        m = self.move
        return (
            self.action == "attack" and m is not None and m.tunnel
            and TUNNEL_EXPOSED <= self.frame < self.startup + m.active
        )

    @property
    def hovering(self) -> bool:
        m = self.move
        return self.action == "attack" and m is not None and m.hover and self.phase in ("startup", "active")

    @property
    def boxed(self) -> bool:
        """THE BOX: superposed in two boxes, with no body (the fight measures him)."""
        return self.action == "boxed"

    def box_rects(self) -> list[tuple[float, float, int, int]]:
        """THE BOX: each box as a hurtbox (left, top, w, h) in screen px, box 1 first."""
        b = BOX_HURT
        return [(x + b.x, FLOOR_Y - (b.y + b.h), b.w, b.h) for x in self.boxes]

    @property
    def hurtbox(self) -> tuple[float, float, int, int]:
        if self.boxed:              # for whoever asks for one box: box 1, where he stood
            return self.box_rects()[0]
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
        self.rival_x = rival_x
        for slot in self.cooldowns:
            if self.cooldowns[slot] > 0:
                self.cooldowns[slot] -= 1
        self.frame += 1
        if self.switch_lock > 0:
            self.switch_lock -= 1
        if self.wakeup > 0:
            self.wakeup -= 1
        if not self.char.copy_paste and (inp.y or self.switch_pending):
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

        self.stick = (inp.dx, inp.up, inp.down)
        self.buffer = [
            Press(p.button, p.age + 1) for p in self.buffer if p.age + 1 < BUFFER_FRAMES
        ]
        return events

    def buffer_presses(self, inp: FighterInput) -> None:
        """Buffer this frame's presses without ageing or advancing anything else.

        The fight calls it during hitstop, when step() is not run, so a press made
        in the freeze (the chain-cancel window) is not lost.
        """
        buttons = ("a", "b", "x", "y") if self.char.copy_paste else ("a", "b", "x")   # DOS: Y is a move
        for btn in buttons:
            if getattr(inp, btn):
                self.buffer.append(Press(btn, 0))

    def hold_switch(self, inp: FighterInput) -> None:
        """A Y pressed in a hitstop freeze (when step() isn't run) switches on the next step."""
        if inp.y and not self.char.copy_paste:
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
        self.charge = self.charge_wait = 0      # a charge hit is lost: it never fires
        self.move = None
        self.slot = None
        self.chained = False
        self.move_hit = False
        self.bounced = False
        self.buffer = []
        self.vx = (move.knockback if hurt else max(move.knockback, BLOCK_PUSH)) * from_facing
        if move.hold:               # a trap holds them where they stand, hurt or not
            self.vx = 0.0
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
        """An H on yourself: the basis (and so the body's colour) swaps at once. A fixed basis
        (DOS: a classical bit can't be in superposition) never changes."""
        if self.char.fixed_basis is not None:
            return
        self.basis = basis.hadamard(self.basis)

    def measured_into(self, b: str) -> bool:
        """MEASURE projects this fighter onto basis b; True if that changed it. A fixed basis
        never changes."""
        if self.char.fixed_basis is not None or self.basis == b:
            return False
        self.basis = b
        return True

    def caught(self, move: Move, shot_basis: str) -> None:
        """COPY caught a shot: it goes into the clipboard (with the basis it was fired in), and
        the recovery is cut to COPY_CAUGHT_RECOVERY frames."""
        m = self.move
        assert m is not None
        self.clipboard = (move, shot_basis)
        self.frame = max(self.frame, self.startup + m.active + m.recovery - COPY_CAUGHT_RECOVERY)

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
        self.charge = self.charge_wait = 0
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

    def collapse(self, k: int, swipe: bool, events: list) -> None:
        """THE BOX collapses: he turns out to be in box k (0: where he stood, 1: the far one)
        and is free at once, facing the rival. `swipe`: he collapsed it himself and pops out
        with the move's swipe. The cooldown runs from now."""
        box = self.char.moves["stand.X"]
        self.box_real = k
        self.x = float(self.boxes[k])
        self.box_t = 0
        self.cooldowns["stand.X"] = box.cooldown
        if self.rival_x != self.x:
            self.facing = 1 if self.rival_x > self.x else -1
        self.action = "idle"
        self.frame = 0
        events.append(("box_collapse", {}))
        if swipe:
            assert box.pop_out is not None
            self._start_move("stand.X", box.pop_out, False, events)

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
            if self.y > 0 and (self.bounced or (m.floor_recovery and self.frame >= self.startup + m.active)):
                self.frame = self.startup + m.active    # the recovery starts on the floor
            if self.frame >= self.startup + m.active + m.recovery:
                self._end_move()
            else:
                self._move_effects(m, events)
        elif self.action == "boxed":
            self.box_t += 1

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
                if m.superpose:         # THE BOX: one cat, two boxes
                    self._split(events)
                    return
                if m.leap is not None:  # POUNCE: off along an arc; gravity does the rest
                    self.vx, self.vy = m.leap[0] * self.facing, m.leap[1]
                if m.kind == "projectile":
                    events.append(("projectile", {"move": m}))
                if m.trap is not None:  # ION TRAP: the fight sets it on the floor
                    events.append(("trap", {"move": m}))
                if m.toss is not None:  # KEY EXCHANGE: the fight tosses the photon to Bob
                    events.append(("pass", {"move": m}))
                if m.swap:              # TELEPORT: the fight swaps the two
                    events.append(("swap", {}))
                if m.paste and self.clipboard is not None:
                    shot, shot_basis = self.clipboard
                    self.clipboard = None
                    events.append(("projectile", {"move": shot, "basis": shot_basis, "paste": True}))
                if m.cue is not None:
                    events.append((m.cue, {}))
                if m.tunnel:            # gone: she is already where she will re-form
                    self.x = self.tunnel_to
                    events.append(("tunnel", {}))
            if m.tunnel and self.frame == self.startup + m.active - 1 and self.rival_x != self.x:
                self.facing = 1 if self.rival_x > self.x else -1    # re-form facing the rival
            if m.dive is not None:
                self.vx = m.dive[0] * self.facing
                self.vy = -m.dive[1]
            elif m.lunge:
                self.vx = m.lunge * self.facing
        elif self.y == 0:
            self.vx = 0.0
        elif (m.dive is not None or m.floor_recovery) and self.frame == self.startup + m.active \
                and not self.bounced:
            self.vx = 0.0           # the dive (or SPIN) ran out before the floor: she drops (a bounce keeps its drift)

    def _slot_for(self, btn: str, dx: int, rival_x: float) -> str:
        if self.y > 0:
            return f"air.{btn.upper()}"
        reach = abs(rival_x - self.x)
        if self.rival_boxes is not None:    # a throw in reach of either of the rival's boxes
            reach = min(abs(bx - self.x) for bx in self.rival_boxes)
        if btn == "b" and dx == self.facing and reach <= self.throw_range:
            return "throw"
        prefix = "crouch" if self.stance == "crouch" else "stand"
        return f"{prefix}.{btn.upper()}"

    def _act(self, inp: FighterInput, rival_x: float, events: list) -> None:
        if self.boxed:
            self._boxed(inp, events)
            return
        if self.action == "charging":
            self._charging(events)
            return
        on_ground_free = self.action in _GROUND_FREE
        if on_ground_free:
            self._face(rival_x)

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
            self.vx = inp.dx * (self.char.air or self.char.walk)
            self._set_action("jump")
        elif self.crouching:
            self.vx = 0.0           # crouching doesn't walk
            self._set_action("crouch")
        else:
            self.vx = inp.dx * self.char.walk
            self._set_action("walk" if inp.dx else "idle")

    def _face(self, rival_x: float) -> None:
        """On the ground and free, turn to face the rival. (Bob, echo.py, faces as Alice does.)"""
        if rival_x != self.x:
            self.facing = 1 if rival_x > self.x else -1

    def _try_buffer(self, dx: int, rival_x: float, free: bool, events: list) -> None:
        if self.super_ready and self.action in _GROUND_FREE and self._try_super(events):
            return
        for entry in reversed(self.buffer):
            if entry.button == "y":     # DOS: COPY, or PASTE with a shot in the clipboard; free, on the ground
                if not free or self.y > 0:
                    continue
                slot = "paste" if self.clipboard is not None else "copy"
                move = self.char.extra.get(slot)
            else:
                slot = self._slot_for(entry.button, dx, rival_x)
                move = self.char.moves.get(slot)
            if move is not None and not self.paired:    # ALICE & BOB with Bob decohered:
                if move.swap:
                    continue                            # no TELEPORT ...
                move = move.alone or move               # ... and X fires her own photon
            if move is None or self.cooldowns.get(slot, 0) > 0 or slot in self.air_used:
                continue
            cancel = not free
            if cancel and not self.can_cancel(slot):
                continue
            if move.charge:             # AMPLITUDE AMPLIFICATION: the first press is its first step
                self._start_charge(events)
                return
            if slot == "paste" and self.clipboard is not None and self.clipboard[0].projectile is None:
                self._paste_field(events)
                return
            self._start_move(slot, move, cancel, events)
            return

    def _try_super(self, events: list) -> bool:
        """SUPERposition: with the bar full, A and B pressed within SUPER_WINDOW frames of each
        other fire the super. A lone A or B waits up to SUPER_WINDOW - 1 frames for its partner
        (True: nothing else may start meanwhile), then comes out as ever."""
        move = self.char.extra.get("super")
        if move is None:
            return False
        ages = {p.button: p.age for p in self.buffer if p.button in ("a", "b")}
        if len(ages) == 2 and abs(ages["a"] - ages["b"]) < SUPER_WINDOW:
            self._start_move("super", move, False, events)
            events.append(("super", {}))
            return True
        return bool(ages) and max(ages.values()) < SUPER_WINDOW - 1

    def _paste_field(self, events: list) -> None:
        """PASTE with a field in the clipboard (CHARGE NOISE): he does the move himself, in the
        colour it was copied in, and the clipboard is empty again."""
        field, field_basis = self.clipboard
        self.clipboard = None
        self._start_move("paste", field, False, events)
        self.attack_basis = field_basis     # its colour, not his: a classical copy of the noise
        self.cooldowns.pop("paste", None)   # the field's own cooldown isn't his
        events.append(("paste", {}))

    def _start_move(self, slot: str, move: Move, cancel: bool, events: list) -> None:
        self.move = move
        self.slot = slot
        self.attack_basis = self.basis  # the move's colour is fixed now, whatever comes next
        self.chained = cancel       # a cancel uses the move's chain_startup, if it has one
        self.move_hit = False
        self.bounced = False
        self.buffer = []            # an older press must not fire a cancel nobody made
        self.chain = self.chain + 1 if cancel else 1
        if move.cooldown > 0 and not move.superpose:     # THE BOX's runs from its collapse
            self.cooldowns[slot] = move.cooldown
        if move.once_per_jump:
            self.air_used.add(slot)
        if move.tunnel:
            self.tunnel_from = self.x
            self.tunnel_to = self._tunnel_target()
        if move.catch is not None or move.paste:
            self.crouching = False      # COPY and PASTE stand him up
        if self.y == 0:
            self.vx = 0.0
        self.action = "attack"
        self.frame = 0
        events.append(("attack", {"slot": slot}))

    def _tunnel_target(self) -> float:
        """TUNNEL_PAST px past the rival (or the push box, if that is wider: DOS's case), on
        their far side; if the stage has no room there (the rival in a corner), as far in front
        of them, on her own side."""
        past = max(TUNNEL_PAST, self.body_width)
        side = 1 if self.rival_x > self.x else -1 if self.rival_x < self.x else self.facing
        far = min(max(self.rival_x + side * past, STAGE_LEFT), STAGE_RIGHT)
        if (far - self.rival_x) * side >= self.body_width:
            return far
        return min(max(self.rival_x - side * past, STAGE_LEFT), STAGE_RIGHT)

    def _split(self, events: list) -> None:
        """THE BOX splits: box 1 where he stands, box 2 BOX_SPLIT px towards the rival (kept on
        the stage, so it can land behind a rival who is close). He has no body until it collapses."""
        side = 1 if self.rival_x > self.x else -1 if self.rival_x < self.x else self.facing
        far = min(max(self.x + side * BOX_SPLIT, STAGE_LEFT), STAGE_RIGHT)
        if far == self.x:           # a wall in the way: the second box goes the other side
            far = min(max(self.x - side * BOX_SPLIT, STAGE_LEFT), STAGE_RIGHT)
        self.boxes = (self.x, far)
        self.move = None
        self.slot = None
        self.chained = False
        self.move_hit = False
        self.crouching = False
        self.buffer = []            # a press from the ducking-in mustn't collapse it at once
        self.vx = 0.0
        self.action = "boxed"
        self.frame = 0
        self.box_t = 0
        events.append(("box_split", {}))

    def _start_charge(self, events: list) -> None:
        """AMPLITUDE AMPLIFICATION starts: one step charged, and she stands still. The cooldown
        waits for the wave to fire."""
        self.move = None
        self.slot = None
        self.chained = False
        self.move_hit = False
        self.crouching = False
        self.buffer = []
        self.vx = 0.0
        self.action = "charging"
        self.frame = 0
        self.charge, self.charge_wait = 1, 0
        events.append(("charge1", {}))

    def _charging(self, events: list) -> None:
        """Charging: every X press (buffered, so one in a hitstop freeze counts too) grows the
        wave a step; A and B do nothing. It fires CHARGE_WAIT frames after the last press, or
        at once on reaching CHARGE_CAP, as the step's own wave move (its colour fixed now),
        towards the rival wherever they are by then. Not in a switch's lock, as no attack is:
        it fires as the lock runs out."""
        pressed = any(p.button == "x" for p in self.buffer)
        self.buffer = []
        if pressed and self.charge < CHARGE_CAP:
            self.charge += 1
            self.charge_wait = 0
            events.append((f"charge{self.charge}", {}))
        else:
            self.charge_wait += 1
        if (self.charge >= CHARGE_CAP or self.charge_wait >= CHARGE_WAIT) and self.switch_lock == 0:
            if self.rival_x != self.x:      # a rival who crossed over her meanwhile: she turns
                self.facing = 1 if self.rival_x > self.x else -1
            wave = self.char.moves["stand.X"].charge[self.charge - 1]
            self.charge = self.charge_wait = 0
            self._start_move("stand.X", wave, False, events)

    def _boxed(self, inp: FighterInput, events: list) -> None:
        """Superposed: any button (A, B or X; Y only switches) or a new stick direction collapses
        it, or BOX_FRAMES at the latest. He lands in a random box, 50/50, with a swipe."""
        stick = (inp.dx, inp.up, inp.down)
        fresh = stick != self.stick and stick != (0, False, False)
        if fresh or self.buffer or self.box_t >= BOX_FRAMES:
            self.collapse(0 if self.rng.random() < 0.5 else 1, True, events)

    def _physics(self, events: list) -> None:
        landed = False
        if self.hovering:               # LASER: she hangs in the air while she aims and fires
            self.vy = 0.0
            if not (self.move.lunge and self.phase == "active"):
                self.vx = 0.0           # (SPIN hangs at her height, but spins forward)
        elif self.y > 0 or self.vy > 0:
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
        self.air_used.clear()
        # "dive": the fighter reached the floor in a dive's active frames (a landing
        # shockwave, like COLLAPSE's, needs the slam; pressed too late, it lands without one)
        events.append(("land", {"dive": self._diving()}))
        m = self.move
        if self.action == "attack" and m is not None:
            self.vx = 0.0
            if m.dive is not None or m.leap is not None or m.floor_recovery:
                # a dive, a leap or a SPIN that reaches the floor skips to its recovery
                self.frame = max(self.frame, self.startup + m.active)
            else:
                self._end_move()    # any other air move is land-cancelled
        elif self.action == "jump":
            self.vx = 0.0
            self._neutral()
