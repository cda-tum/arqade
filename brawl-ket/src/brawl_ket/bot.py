"""A simple, deterministic CPU fighter for the attract demo and the bot-vs-bot tests.

Pure logic, no pygame. It is never a playable mode. Everything random comes from
one random.Random(seed), so the same seed against the same opponent plays the
same round.

The bot reads the Fight directly and answers with a FighterInput each frame. It
follows ordered rules: react, finish a chain, then walk in / strike / throw / jump.
Colour must match to hurt, so it strikes with A when the rival is in its own basis
and with B when not, sometimes switches (Y) to dodge an attack that would hurt it,
and throws a rival who keeps switching (a throw hurts either colour).
"""

from __future__ import annotations

import random
from collections import deque

from . import basis
from .fight import Fight
from .fighter import FighterInput

STRIKE_RANGE = 66       # px between the fighters' x where a ground normal can reach (the jab: about 72)
AIR_RANGE = 50          # the same for an air attack, whose boxes are shorter
GRAB_RANGE = 120        # MEASURE (a dashing command throw) connects from about this far
WAVE_RANGE = 66         # HADAMARD WAVE reaches about 70 px in front
PRESS_GAP = 4           # frames between two presses, so every press is a fresh edge
LONG_CROUCH = 40        # a rival crouched this long gets thrown
SWITCH_MEMORY = 180     # frames over which the rival's switches are counted
SWITCHER = 2            # a rival who switched this often in SWITCH_MEMORY gets thrown

_BUSY = ("hitstun", "knockdown")


class Bot:
    def __init__(self, player: str, seed: int, skill: float = 0.8) -> None:
        self.player = player
        self.rival = "p2" if player == "p1" else "p1"
        self.skill = skill
        self.rng = random.Random(seed)
        # Reaction memory: the rival's stance as it was `delay` frames ago.
        self.delay = round(12 / skill)
        self.seen: deque[str] = deque(maxlen=self.delay + 1)
        self.noticed = "stand"
        self.react = round(5 / skill)       # frames into a rival's attack before a dodge switch
        self.down = False           # the stance the bot wants to be in
        self.chain: list[str] = []  # buttons still to press in the current string
        self.gap = 0                # frames until the next press is allowed
        self.rival_crouched = 0     # how long the rival has been crouching
        self.rival_basis: str | None = None
        self.switches: deque[int] = deque()     # the frames the rival switched on
        self.t = 0
        self.air_pressed = False

    def input(self, fight: Fight) -> FighterInput:
        me, rival = fight.fighters[self.player], fight.fighters[self.rival]
        self.t += 1
        self.gap = max(0, self.gap - 1)
        self.rival_crouched = self.rival_crouched + 1 if rival.stance == "crouch" else 0
        self._watch(rival.stance)
        self._count_switches(rival)

        if me.action in _BUSY:
            self.chain.clear()
            return FighterInput(down=self.down)
        toward = 1 if rival.x > me.x else -1
        dist = abs(rival.x - me.x)

        if self._wants_dodge(me, rival):
            self.gap = PRESS_GAP
            return FighterInput(down=self.down, y=True)
        if me.stance == "air":
            return self._in_air(me, rival, toward, dist)
        self.air_pressed = False
        if me.action == "attack":
            return self._continue_chain(me, toward)
        if self.chain and not me.buffer:
            self.chain.clear()      # the string ended (or whiffed): start afresh
        return self._on_ground(me, rival, toward, dist)

    # --- what the bot knows ---------------------------------------------------------------

    @staticmethod
    def matching(me, rival) -> str:
        """The button whose colour hurts the rival: A is the bot's own colour, B the other."""
        return "a" if rival.basis == me.basis else "b"

    @staticmethod
    def would_hurt(attacker, move, target) -> bool:
        return basis.hurts(basis.error_for(move.colour, attacker.basis), target.basis)

    def _count_switches(self, rival) -> None:
        if self.rival_basis is not None and rival.basis != self.rival_basis:
            self.switches.append(self.t)
        self.rival_basis = rival.basis
        while self.switches and self.switches[0] < self.t - SWITCH_MEMORY:
            self.switches.popleft()

    # --- rules, in order ----------------------------------------------------------------

    def _watch(self, stance: str) -> None:
        """Defence by height: after the reaction delay, with probability `skill`, take the
        stance the rival took (a crouching rival's lows and a standing one's highs are best
        met at the same height)."""
        self.seen.append(stance)
        old = self.seen[0]
        if old != self.noticed:
            self.noticed = old
            if self.rng.random() < self.skill:
                self.down = old == "crouch"

    def _wants_dodge(self, me, rival) -> bool:
        """Switch basis `react` frames into a rival attack whose colour would hurt, if free."""
        m = rival.move
        if m is None or rival.action != "attack" or rival.phase != "startup" or rival.frame != self.react:
            return False
        if m.switch_rival or m.colour == basis.BOTH or not self.would_hurt(rival, m, me):
            return False
        free = me.action in ("idle", "walk", "crouch", "jump")
        return free and self.gap == 0 and self.rng.random() < self.skill * 0.5

    def _continue_chain(self, me, toward: int) -> FighterInput:
        # Press the next button of the string once the current move has connected.
        if self.chain and me.move_hit and self.gap == 0 and me.can_cancel(self._next_slot(me)):
            return self._press(self.chain.pop(0), toward)
        return FighterInput(dx=toward, down=self.down)

    def _next_slot(self, me) -> str:
        return f"{'crouch' if me.stance == 'crouch' else 'stand'}.{self.chain[0].upper()}"

    def _in_air(self, me, rival, toward: int, dist: float) -> FighterInput:
        if not self.air_pressed and self.gap == 0 and dist <= AIR_RANGE:
            self.air_pressed = True
            button = "x" if self.rng.random() < 0.3 else self.matching(me, rival)
            return self._press(button, toward)
        return FighterInput(dx=toward)

    def _on_ground(self, me, rival, toward: int, dist: float) -> FighterInput:
        roll = self.rng.random()
        if self.chain:              # a buffered first press is about to come out
            return FighterInput(down=self.down)
        special = me.char.moves["stand.X"]
        wave = me.char.moves["crouch.X"]
        ready = self.gap == 0
        switcher = len(self.switches) >= SWITCHER
        if dist <= me.throw_range and ready and (switcher or self.rival_crouched > LONG_CROUCH) and roll < 0.1:
            return self._press("b", toward)                     # a throw hurts either colour
        if wave.switch_rival and dist <= WAVE_RANGE and rival.basis != me.basis and ready \
                and me.cooldowns.get("crouch.X", 0) == 0 and roll < 0.05:
            self.down = True                                    # a WAVE: their colour flips to ours
            return self._press("x", 0)
        if special.measure_rival and me.throw_range < dist <= GRAB_RANGE and not self.down and ready \
                and roll < 0.01:
            return self._press("x", 0)                          # MEASURE
        if dist <= STRIKE_RANGE:
            if roll < 0.02 and ready:
                if self.rng.random() < 0.2:
                    self.down = not self.down   # strike at the other height
                button = self.matching(me, rival)
                self.chain = [button, button] if button == "a" else [button]
                return self._press(self.chain.pop(0), 0)
            return FighterInput(down=self.down)
        # Out of range. Crouching can't walk, so stand up and approach.
        self.down = False
        if roll < 0.01:
            return FighterInput(up=True, dx=toward)             # jump in
        if roll < 0.03 and dist > 90 and ready and special.kind == "projectile" \
                and me.cooldowns.get("stand.X", 0) == 0 and self.would_hurt(me, special, rival):
            return self._press("x", 0)                          # a PHOTON that will hurt
        if roll < 0.04 and ready:
            self.gap = PRESS_GAP
            return FighterInput(dx=toward, y=True)              # a feint: switch colour at range
        return FighterInput(dx=toward)

    def _press(self, button: str, dx: int) -> FighterInput:
        self.gap = PRESS_GAP
        return FighterInput(dx=dx, down=self.down, a=button == "a", b=button == "b",
                            x=button == "x")
