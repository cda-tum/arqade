"""A simple, deterministic CPU fighter for the attract demo and the bot-vs-bot tests.

Pure logic, no pygame. It is never a playable mode. Everything random comes from
one random.Random(seed), so the same seed against the same opponent plays the
same round.

The bot reads the Fight directly and answers with a FighterInput each frame. It
follows ordered rules: react, finish a chain, then walk in / strike / throw / jump.
Colour must match to hurt, so it strikes with A when the rival is in its own basis
and with B when not, sometimes switches (Y) to dodge an attack that would hurt it,
and throws a rival who keeps switching (a throw hurts either colour).

ERWIN boxes against a shot or a heavy that would hurt him and pops out when the rival comes
near a box, pounces on crouchers and drops a box on rivals below him; DOS COPYs incoming shots
and BOHR's crackling field, PASTEs (a field only up close), FLOPPYs at range, reels in rivals
out of reach with MOUSE CABLE and CRT DROPs on one under him. DOS never switches, so he never
uses Y to dodge or feint. M-CUTIE sets traps while the rival is far (more often when they walk
in) and hits a rival one holds, charges a wave at range for a random 2 to 6 steps, and jumps at
a rival in the air at mid range to SPIN into them, or at one winding up a dashing grab close by.
ALICE & BOB's bot controls Alice only (Bob follows by himself, as he does for a person): KEY
EXCHANGE at range while the rival isn't standing between them, TELEPORT when the rival is, and
now and then a jump at the rival, to BELL DIVE on them below.
"""

from __future__ import annotations

import random
from collections import deque

from . import basis
from .config import TRAP_MAX
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
BOX_DANGER = 60         # ERWIN boxes against a shot or a heavy this close (90 made him win 65% against DOS)
BOX_POP = 50            # ... and pops out once the rival is this close to either box
POUNCE_RANGE = (60, 170)    # ERWIN pounces on a crouching rival this far away
COPY_REACH = (30, 110)  # a rival's shot this far from DOS, coming, is worth a COPY
MOUSE_RANGE = (70, 180)     # DOS flings his mouse at a rival on the ground this far away
FIELD_PASTE = 70        # ... and pastes a copied field only with the rival this close
MOUSE_FOLLOW = 60       # ... and strikes a rival its mouse reeled in, this many frames after the fling
DROP_RANGE = 30         # DOS stomps on a rival this close under him
TRAP_RANGE = 150        # M-CUTIE sets a trap with the rival at least this far away
TRAP_ODDS = (0.003, 0.008)  # ... a chance a frame (the second: while the rival walks in)
CHARGE_RANGE = 160      # ... and charges a wave with the rival at least this far away
CHARGE_ODDS = 0.01      # ... a chance a frame
CHARGE_STEPS = (2, 6)   # ... mashing for this many steps, picked at random each time
SPIN_RANGE = (40, 110)  # ... and jumps at a rival in the air this far away, to SPIN into them
ANTI_AIR_ODDS = 0.02    # ... a chance a frame (never at one on the ground: no bot answers that)
SPIN_REACH = (20, 100)  # ... spinning in that jump once they are this far ahead of her
SPIN_HEIGHT = (-60, 80)     # ... and her height over theirs puts her leg on their body
GRAB_JUMP = 0.8         # ... and this often jumps at a rival winding up a dashing grab (MEASURE) ...
GRAB_SPIN = 70          # ... this close, to SPIN them out of it before it dashes (from further, it would catch her)
KEY_RANGE = 110         # ALICE & BOB: KEY EXCHANGE with the rival at least this far from Alice ...
KEY_ODDS = 0.03         # ... a chance a frame
TELEPORT_ODDS = 0.15    # ... TELEPORT, a chance a frame while the rival stands between them
DIVE_JUMP = (50, 120)   # ... a jump at a rival on the ground this far away, to BELL DIVE on them ...
DIVE_JUMP_ODDS = 0.004  # ... a chance a frame (no bot answers a dive: at 0.01 they won 65-76%)
DIVE_REACH = (10, 60)   # ... diving once they are this far ahead of her, below her
KIDS_GRAB_JUMP = 0.8    # ... and this often jumps a dashing grab (MEASURE) winding up in its reach
# ... and starts a string up close a little less often than anyone (0.02): every attack of theirs
# comes twice, and at 0.02 they won 60-72% against all but BOHR (tools/balance.py)
KIDS_STRIKE_ODDS = 0.017

_BUSY = ("hitstun", "knockdown")


def keep_clear_of(move) -> bool:
    """Moves a bot on the ground backs away from while they would hurt it: a field round the
    body (CHARGE NOISE), and M-CUTIE's SPIN, which sweeps 96 px forward hitting every 8 frames.
    SPIN is no field (COPY can't catch it), but walking out of its path is still the bot's
    answer to it; without that BOHR's bot beats hers 62/38 (tools/balance.py)."""
    return move.field or is_spin(move)


def is_spin(move) -> bool:
    """SPIN: a move that hits again and again, sweeping forward from a hover, but is no field."""
    return bool(move.hit_every) and not move.field and move.hover and bool(move.lunge)


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
        self.box_hold = 0               # THE BOX: how long this bot stays in the boxes
        self.mouse_t = -1000            # DOS: when it last flung the mouse (to follow up a pull)
        self.charge_goal = 0            # M-CUTIE: the steps this charge is mashed up to
        self.spin_jump = False          # ... this jump is one to SPIN in (her other jumps don't)
        self.dive_jump = False          # ALICE & BOB: this jump is one to BELL DIVE in

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
        if me.boxed:
            return self._in_box(me, rival)
        if me.action == "charging":
            return self._charging(me)
        if me.action in _BUSY:
            self.chain.clear()
            return FighterInput(down=self.down)
        toward = 1 if rival.x > me.x else -1
        dist = abs(rival.x - me.x)
        m = rival.move
        if m is not None and keep_clear_of(m) and rival.action == "attack" and dist <= FIELD_RANGE + 20 \
                and self.would_hurt(rival, m, me) and me.action in ("idle", "walk", "crouch"):
            self.down = False
            return FighterInput(dx=-toward)                     # back out of a field (or a SPIN) that hurts
        if me.stance == "air":
            return self._in_air(me, rival, toward, dist)
        self.spin_jump = False
        self.dive_jump = False
        for rule in (self._phoebe, self._erwin, self._dos, self._cutie, self._kids):
            special = rule(fight, me, rival, toward, dist)
            if special is not None:
                return special
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
        if me.char.fixed_basis is not None:     # DOS can't switch: his Y is COPY / PASTE
            return False
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
        air = me.char.moves["air.X"]
        ready = not self.air_pressed and self.gap == 0 and "air.X" not in me.air_used
        if me.char.pair is not None and self.dive_jump:     # BELL DIVE, in a jump made for it
            ahead = (rival.x - me.x) * me.facing
            if ready and DIVE_REACH[0] <= ahead <= DIVE_REACH[1] and me.y > rival.y + 30 \
                    and self.would_hurt(me, air, rival):
                self.air_pressed = True
                return self._press("x", 0)
            return FighterInput(dx=toward)
        if air.hover and air.projectile is not None and ready and abs(dist - (me.y + 50)) < 45 \
                and self.would_hurt(me, air, rival):
            # LASER: the shot leaves 50 px ahead at hand height (59 px) and falls one px per px, so
            # it meets a standing body about y + 50 px ahead, give or take its height: fire
            self.air_pressed = True
            return self._press("x", toward)
        if air.projectile is not None and not air.hover and air.projectile.vy and ready and me.y > 30 \
                and abs((rival.x - me.x) * me.facing - (17 + me.y / 14)) <= 26 and self.would_hurt(me, air, rival):
            # BOX DROP: the box falls from about 17 px in front of him, drifting half a px a frame
            # for every 7 it falls: it lands about 17 + y / 14 px ahead
            self.air_pressed = True
            return self._press("x", 0)
        if air.hover and air.lunge:     # SPIN: only in a jump made for it, once they are in reach
            if self.spin_jump and self.would_hurt(me, air, rival):
                if ready and SPIN_REACH[0] <= (rival.x - me.x) * me.facing <= SPIN_REACH[1] \
                        and SPIN_HEIGHT[0] <= me.y - rival.y <= SPIN_HEIGHT[1]:
                    self.air_pressed = True
                    return self._press("x", 0)
                return FighterInput(dx=toward)                  # ... and nothing else in it
            if not self.air_pressed and self.gap == 0 and dist <= AIR_RANGE:
                self.air_pressed = True
                return self._press(self.matching(me, rival), toward)   # a normal air attack
            return FighterInput(dx=toward)
        if air.dive is not None and air.dive[0] == 0 and ready and abs(rival.x - me.x) <= DROP_RANGE \
                and me.y > rival.y + 30:
            self.air_pressed = True
            return self._press("x", 0)                          # CRT DROP on a rival under him
        if not self.air_pressed and self.gap == 0 and dist <= AIR_RANGE:
            self.air_pressed = True
            button = "x" if self.rng.random() < 0.3 else self.matching(me, rival)
            return self._press(button, toward)
        return FighterInput(dx=toward)

    def _in_box(self, me, rival) -> FighterInput:
        """THE BOX: pop out (A, with the swipe) once the rival comes near either box, or after a
        while of its own choosing."""
        if me.box_t == 0:
            self.box_hold = self.rng.randrange(20, 70)
        near = min(abs(rival.x - x) for x in me.boxes) <= BOX_POP
        if self.gap == 0 and (near or me.box_t >= self.box_hold):
            return self._press("a", 0)
        return FighterInput()

    def _erwin(self, fight: Fight, me, rival, toward: int, dist: float) -> FighterInput | None:
        """ERWIN on the ground: THE BOX against a shot or a heavy that would hurt him, POUNCE on a
        crouching rival, and now and then a jump at the rival, to drop a box on them."""
        box, pounce = me.char.moves["stand.X"], me.char.moves["crouch.X"]
        if not box.superpose or me.action not in ("idle", "walk", "crouch") or self.gap > 0:
            return None
        if me.cooldowns.get("stand.X", 0) == 0:
            shot = any(s.owner == self.rival and (s.x - me.x) * s.vx < 0 and abs(s.x - me.x) <= BOX_DANGER
                       and self.would_hurt_shot(s, me) for s in fight.shots)
            m = rival.move
            heavy = rival.action == "attack" and m is not None and rival.phase == "startup" and m.damage >= 8 \
                and m.kind != "throw" and dist <= BOX_DANGER and self.would_hurt(rival, m, me)
            if (shot and self.rng.random() < self.skill * 0.5) or (heavy and self.rng.random() < self.skill * 0.3):
                self.down = False
                return self._press("x", 0)
        if rival.stance == "crouch" and POUNCE_RANGE[0] <= dist <= POUNCE_RANGE[1] \
                and me.cooldowns.get("crouch.X", 0) == 0 and self.would_hurt(me, pounce, rival) \
                and self.rng.random() < 0.05:
            self.down = True
            press = self._press("x", 0)                         # POUNCE, from a crouch ...
            self.down = False                                   # ... and up again: no sitting there
            return press
        if 30 <= dist <= 110 and rival.y == 0 and self.rng.random() < 0.02:
            self.down = False
            return FighterInput(up=True, dx=toward)             # a jump at them, to drop a box
        return None

    def _dos(self, fight: Fight, me, rival, toward: int, dist: float) -> FighterInput | None:
        """DOS: PASTE (a shot at once, a field once the rival is close), COPY a rival's shot that
        is about to arrive or a field crackling at him, MOUSE CABLE at a rival out of reach, and
        now and then a hop to CRT DROP on them."""
        if not me.char.copy_paste or me.action not in ("idle", "walk", "crouch") or self.gap > 0:
            return None
        if me.clipboard is not None:
            if me.clipboard[0].projectile is not None or dist <= FIELD_PASTE:
                self.down = False
                return self._press("y", 0)                      # PASTE
            return FighterInput(dx=toward)                      # in close first, with the noise
        coming = any(s.owner == self.rival and (s.x - me.x) * s.vx < 0
                     and COPY_REACH[0] <= abs(s.x - me.x) <= COPY_REACH[1] for s in fight.shots)
        m = rival.move
        near = rival.action == "attack" and m is not None and m.hit_every and dist <= 100
        field = near and m.field
        # (a repeating move in reach that is no field, SPIN, still takes its roll, so the bot's
        # random draws stay where they were; COPY can't catch it)
        if (coming or near) and self.rng.random() < self.skill * 0.8 and (coming or field):
            self.down = False
            return self._press("y", 0)                          # COPY
        if rival.action == "hitstun" and dist <= STRIKE_RANGE and self.t - self.mouse_t <= MOUSE_FOLLOW \
                and not self.chain:
            self.mouse_t = -1000
            button = self.matching(me, rival)               # reeled in by the mouse: punish at once
            self.down = False
            self.chain = [button, button] if button == "a" else [button]
            return self._press(self.chain.pop(0), 0)
        mouse = me.char.moves["crouch.X"]
        if mouse.pull and MOUSE_RANGE[0] < dist <= MOUSE_RANGE[1] and rival.y == 0 \
                and me.cooldowns.get("crouch.X", 0) == 0 and self.rng.random() < 0.12:
            self.down = True
            self.mouse_t = self.t
            press = self._press("x", 0)                         # MOUSE CABLE, from a crouch ...
            self.down = False                                   # ... and up again (a crouching DOS invites POUNCE)
            return press
        if dist <= 60 and rival.y == 0 and self.rng.random() < 0.01:
            self.down = False
            return FighterInput(up=True, dx=toward)             # a hop, to come down on them
        return None

    def _charging(self, me) -> FighterInput:
        """AMPLITUDE AMPLIFICATION: mash X up to this charge's goal, then let it fire."""
        if me.charge < self.charge_goal and self.gap == 0:
            return self._press("x", 0)
        return FighterInput()

    def _cutie(self, fight: Fight, me, rival, toward: int, dist: float) -> FighterInput | None:
        """M-CUTIE: up to SPIN a rival out of a dashing grab winding up close by; in to hit a rival
        her trap holds; ION TRAP while the rival is far (fewer than two down; more often when they
        walk in); AMPLITUDE AMPLIFICATION at range; and a jump at a rival in the air at mid range,
        to SPIN into them."""
        amp, spin = me.char.moves["stand.X"], me.char.moves["air.X"]
        if not amp.charge or me.action not in ("idle", "walk", "crouch") or self.gap > 0:
            return None
        m = rival.move
        if m is not None and rival.action == "attack" and rival.phase == "startup" and m.kind == "throw" \
                and m.lunge and dist <= GRAB_SPIN and rival.frame == self.react and self.rng.random() < GRAB_JUMP:
            self.down = False
            self.spin_jump = True
            return FighterInput(up=True, dx=toward)             # up, and SPIN them out of the grab
        held = rival.action == "hitstun" and any(t.held == self.rival for t in fight.traps)
        if held and not self.chain:     # a rival her trap holds: in, and hit them before it lets go
            if dist <= STRIKE_RANGE:
                button = self.matching(me, rival)
                self.down = False
                self.chain = [button, button] if button == "a" else [button]
                return self._press(self.chain.pop(0), 0)
            return FighterInput(dx=toward)
        mine = sum(1 for t in fight.traps if t.owner == self.player and not t.closed)
        walking_in = rival.action == "walk" and (rival.x - me.x) * rival.vx < 0
        if dist >= TRAP_RANGE and mine < TRAP_MAX and me.cooldowns.get("crouch.X", 0) == 0 \
                and self.rng.random() < TRAP_ODDS[walking_in]:
            self.down = True
            press = self._press("x", 0)                         # ION TRAP, from a crouch ...
            self.down = False                                   # ... and up again
            return press
        if dist >= CHARGE_RANGE and me.cooldowns.get("stand.X", 0) == 0 and self.would_hurt(me, amp, rival) \
                and self.rng.random() < CHARGE_ODDS:
            self.charge_goal = self.rng.randint(*CHARGE_STEPS)
            self.down = False
            return self._press("x", 0)                          # the first step
        if rival.y > 0 and SPIN_RANGE[0] <= dist <= SPIN_RANGE[1] and self.would_hurt(me, spin, rival) \
                and self.rng.random() < ANTI_AIR_ODDS:
            self.down = False
            self.spin_jump = True
            return FighterInput(up=True, dx=toward)             # up after them, to SPIN
        return None

    def _kids(self, fight: Fight, me, rival, toward: int, dist: float) -> FighterInput | None:
        """ALICE & BOB (the bot is Alice): TELEPORT when the rival stands between her and Bob, KEY
        EXCHANGE at range when they don't (Alice's own photon while Bob is gone), and now and then
        a jump at a rival on the ground, to BELL DIVE on them."""
        if me.char.pair is None or me.action not in ("idle", "walk", "crouch") or self.gap > 0:
            return None
        m = rival.move
        if m is not None and rival.action == "attack" and rival.phase == "startup" and m.kind == "throw" \
                and m.lunge and dist <= GRAB_RANGE and rival.frame == self.react and self.rng.random() < KIDS_GRAB_JUMP:
            self.down = False
            self.dive_jump = True
            return FighterInput(up=True, dx=toward)             # over a dashing grab, and dive on them
        bob = fight.echoes[self.player]
        between = bob.here and min(me.x, bob.x) < rival.x < max(me.x, bob.x)
        if between:
            if me.cooldowns.get("crouch.X", 0) == 0 and self.rng.random() < TELEPORT_ODDS:
                self.down = True
                press = self._press("x", 0)                     # TELEPORT, from a crouch ...
                self.down = False                               # ... and up again
                return press
            return None
        key = me.char.moves["stand.X"]
        if dist >= KEY_RANGE and me.cooldowns.get("stand.X", 0) == 0 and self.would_hurt(me, key, rival) \
                and self.rng.random() < KEY_ODDS:
            self.down = False
            return self._press("x", 0)                          # KEY EXCHANGE (her own photon while Bob is gone)
        if DIVE_JUMP[0] <= dist <= DIVE_JUMP[1] and rival.y == 0 and self.rng.random() < DIVE_JUMP_ODDS:
            self.down = False
            self.dive_jump = True
            return FighterInput(up=True, dx=toward)             # up, to come down on them
        return None

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
        if field.field and dist <= FIELD_RANGE and self.would_hurt(me, field, rival) and ready \
                and me.cooldowns.get("crouch.X", 0) == 0 and roll < 0.05:
            self.down = True                                    # CHARGE NOISE on a rival it hurts
            return self._press("x", 0)
        if special.measure_rival and me.throw_range < dist <= GRAB_RANGE and not self.down and ready \
                and roll < 0.01:
            return self._press("x", 0)                          # MEASURE
        if dist <= STRIKE_RANGE:
            if roll < (KIDS_STRIKE_ODDS if me.char.pair is not None else 0.02) and ready:
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
        if roll < 0.03 and dist > 90 and ready and special.kind == "projectile" and not special.charge \
                and me.cooldowns.get("stand.X", 0) == 0 and self.would_hurt(me, special, rival):
            return self._press("x", 0)                          # a PHOTON that will hurt
        if roll < 0.04 and ready and me.char.fixed_basis is None:
            self.gap = PRESS_GAP
            return FighterInput(dx=toward, y=True)              # a feint: switch colour at range
        return FighterInput(dx=toward)

    def _press(self, button: str, dx: int) -> FighterInput:
        self.gap = PRESS_GAP
        return FighterInput(dx=dx, down=self.down, a=button == "a", b=button == "b",
                            x=button == "x", y=button == "y")
