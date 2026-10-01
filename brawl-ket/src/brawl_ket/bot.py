"""A simple, deterministic CPU fighter for the attract demo and the bot-vs-bot tests.

Pure logic, no pygame. It is never a playable mode. Everything random comes from
one random.Random(seed), so the same seed against the same opponent plays the
same round.

The bot reads the Fight directly and answers with a FighterInput each frame. It
follows ordered rules: react, finish a chain, then walk in / strike / throw / jump.
"""

from __future__ import annotations

import random
from collections import deque

from .config import THROW_RANGE
from .fight import Fight
from .fighter import FighterInput

STRIKE_RANGE = 50       # px between the fighters' x where a normal can reach
PRESS_GAP = 4           # frames between two presses, so every press is a fresh edge
LONG_CROUCH = 40        # a rival crouched this long gets thrown (a throw ignores the code)

_BUSY = ("hitstun", "knockdown", "switch")


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
        self.down = False           # the stance the bot wants to be in
        self.chain: list[str] = []  # buttons still to press in the current string
        self.gap = 0                # frames until the next press is allowed
        self.rival_crouched = 0     # how long the rival has been crouching
        self.air_pressed = False

    def input(self, fight: Fight) -> FighterInput:
        me, rival = fight.fighters[self.player], fight.fighters[self.rival]
        self.gap = max(0, self.gap - 1)
        self.rival_crouched = self.rival_crouched + 1 if rival.stance == "crouch" else 0
        self._watch(rival.stance)

        if me.action in _BUSY:
            if me.action != "switch":       # a switch keeps its buffered press and string
                self.chain.clear()
            return FighterInput(down=self.down)
        toward = 1 if rival.x > me.x else -1
        dist = abs(rival.x - me.x)

        if me.stance == "air":
            return self._in_air(me, toward, dist)
        self.air_pressed = False
        if me.action == "attack":
            return self._continue_chain(me, toward)
        if self.chain and not me.buffer:
            self.chain.clear()      # the string ended (or whiffed): start afresh
        return self._on_ground(fight, me, toward, dist)

    # --- rules, in order ----------------------------------------------------------------

    def _watch(self, stance: str) -> None:
        """Defence: after the reaction delay, take the stance the rival's attacks need.

        The rival's crouching attacks are Z errors and the crouch code corrects Z; its
        standing and air attacks are X errors, which the standing code corrects.
        So copying what it did `delay` frames ago, with probability `skill`, is the
        right defence.
        """
        self.seen.append(stance)
        old = self.seen[0]
        if old != self.noticed:
            self.noticed = old
            if self.rng.random() < self.skill:
                self.down = old == "crouch"

    def _continue_chain(self, me, toward: int) -> FighterInput:
        # Press the next button of the string once the current move has connected.
        if self.chain and me.move_hit and self.gap == 0 and me.can_cancel(self._next_slot(me)):
            return self._press(self.chain.pop(0), toward)
        return FighterInput(dx=toward, down=self.down)

    def _next_slot(self, me) -> str:
        return f"{'crouch' if me.stance == 'crouch' else 'stand'}.{self.chain[0].upper()}"

    def _in_air(self, me, toward: int, dist: float) -> FighterInput:
        if not self.air_pressed and self.gap == 0 and dist <= STRIKE_RANGE:
            self.air_pressed = True
            return self._press(self.rng.choice("bbx"), toward)
        return FighterInput(dx=toward)

    def _on_ground(self, fight: Fight, me, toward: int, dist: float) -> FighterInput:
        roll = self.rng.random()
        if self.chain:              # a buffered first press is about to come out
            return FighterInput(down=self.down)
        if dist <= THROW_RANGE and self.rival_crouched > LONG_CROUCH and roll < 0.1 \
                and self.gap == 0:
            return self._press("b", toward)
        if dist <= STRIKE_RANGE:
            if roll < 0.02 and self.gap == 0:
                if self.rng.random() < 0.2:
                    self.down = not self.down   # strike from the other code
                self.chain = self.rng.choice((["a", "b"], ["a", "a", "b"]))
                return self._press(self.chain.pop(0), 0)
            return FighterInput(down=self.down)
        # Out of range. Crouching can't walk, so stand up and approach.
        self.down = False
        if roll < 0.01:
            return FighterInput(up=True, dx=toward)             # jump in
        if roll < 0.03 and dist > 90 and self.gap == 0 \
                and not any(s.owner == self.player for s in fight.shots):
            return self._press("x", 0)                          # a PHOTON from range
        return FighterInput(dx=toward)

    def _press(self, button: str, dx: int) -> FighterInput:
        self.gap = PRESS_GAP
        return FighterInput(dx=dx, down=self.down, a=button == "a", b=button == "b",
                            x=button == "x")
