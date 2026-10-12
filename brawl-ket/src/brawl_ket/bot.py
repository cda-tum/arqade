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
FIELD_RANGE = 70        # CHARGE NOISE shocks anything within about this far
PILLAR_REACH = (-4, 56)     # LIGHT PILLAR: where a rival in the air is in the beam (ahead of her, px)
SHOT_DANGER = 90        # a rival's shot this close and coming is worth TUNNELling through
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

        if self._wants_dodge(me, rival):     # a switch works in any state, hitstun included
            self.gap = PRESS_GAP
            return FighterInput(down=self.down, y=True)
        if me.action in _BUSY:
            self.chain.clear()
            return FighterInput(down=self.down)
        toward = 1 if rival.x > me.x else -1
        dist = abs(rival.x - me.x)
        m = rival.move
        if m is not None and m.hit_every and rival.action == "attack" and dist <= FIELD_RANGE + 20 \
                and self.would_hurt(rival, m, me) and me.action in ("idle", "walk", "crouch"):
            self.down = False
            return FighterInput(dx=-toward)                     # back out of a field that hurts
        if me.stance == "air":
            return self._in_air(me, rival, toward, dist)
        phoebe = self._phoebe(fight, me, rival, toward, dist)
        if phoebe is not None:
            return phoebe
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
        """Would `move` hurt `target`? Its colour is fixed when it starts: an attack already
        under way keeps the basis it started in."""
        b = attacker.attack_basis if attacker.move is move else attacker.basis
        return basis.hurts(basis.error_for(move.colour, b), target.basis)

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
        """Switch basis `react` frames into a rival attack whose colour would hurt: from neutral
        a dodge, mid-string (in hitstun) a way to turn the rest of it away."""
        m = rival.move
        if m is None or rival.action != "attack" or rival.phase != "startup" or rival.frame != self.react:
            return False
        if m.colour == basis.BOTH or not self.would_hurt(rival, m, me):
            return False
        return self.gap == 0 and self.rng.random() < self.skill * 0.5

    def _continue_chain(self, me, toward: int) -> FighterInput:
        # Press the next button of the string once the current move has connected.
        if self.chain and me.move_hit and self.gap == 0 and me.can_cancel(self._next_slot(me)):
            return self._press(self.chain.pop(0), toward)
        return FighterInput(dx=toward, down=self.down)

    def _next_slot(self, me) -> str:
        return f"{'crouch' if me.stance == 'crouch' else 'stand'}.{self.chain[0].upper()}"

    def _phoebe(self, fight: Fight, me, rival, toward: int, dist: float) -> FighterInput | None:
        """PHOEBE's two ground specials: LIGHT PILLAR on a rival in the air above her, TUNNEL
        through an incoming shot or, now and then, to cross the rival up."""
        if me.action not in ("idle", "walk", "crouch") or self.gap > 0:
            return None
        pillar, tunnel = me.char.moves["stand.X"], me.char.moves["crouch.X"]
        ahead = (rival.x - me.x) * me.facing
        if pillar.name == "LIGHT PILLAR" and rival.y > 20 and PILLAR_REACH[0] <= ahead <= PILLAR_REACH[1] \
                and me.cooldowns.get("stand.X", 0) == 0 and self.would_hurt(me, pillar, rival) \
                and self.rng.random() < self.skill * 0.6:
            self.down = False
            return self._press("x", 0)
        if not tunnel.tunnel or me.cooldowns.get("crouch.X", 0) > 0:
            return None
        coming = any(s.owner == self.rival and (s.x - me.x) * s.vx < 0 and abs(s.x - me.x) <= SHOT_DANGER
                     and self.would_hurt_shot(s, me) for s in fight.shots)
        if (coming and self.rng.random() < self.skill * 0.3) or (90 < dist < 200 and self.rng.random() < 0.004):
            self.down = True
            return self._press("x", 0)
        return None

    @staticmethod
    def would_hurt_shot(shot, target) -> bool:
        return basis.hurts(basis.error_for(shot.move.colour, shot.basis), target.basis)

    def _in_air(self, me, rival, toward: int, dist: float) -> FighterInput:
        laser = me.char.moves["air.X"]
        if laser.hover and not self.air_pressed and self.gap == 0 and "air.X" not in me.air_used \
                and abs(dist - (me.y + 50)) < 45 and self.would_hurt(me, laser, rival):
            # the shot leaves 50 px ahead at hand height (59 px) and falls one px per px, so it
            # meets a standing body about y + 50 px ahead, give or take its height: fire
            self.air_pressed = True
            return self._press("x", toward)
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
        field = me.char.moves["crouch.X"]
        ready = self.gap == 0
        switcher = len(self.switches) >= SWITCHER
        if dist <= me.throw_range and ready and (switcher or self.rival_crouched > LONG_CROUCH) and roll < 0.1:
            return self._press("b", toward)                     # a throw hurts either colour
        if field.hit_every and dist <= FIELD_RANGE and self.would_hurt(me, field, rival) and ready \
                and me.cooldowns.get("crouch.X", 0) == 0 and roll < 0.05:
            self.down = True                                    # CHARGE NOISE on a rival it hurts
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
