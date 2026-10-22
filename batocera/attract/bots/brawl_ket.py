"""Brawl-Ket: ROBERT against BOHR, both fought by the game's own CPU.

A on the title (on PLAY: the bot never moves the stick there, so never onto
QUIT), then A on each pad at the character select, which keeps the game's
default pairing: P1 ROBERT on the left (blue ring), P2 BOHR on the right (red
ring), A on CHOOSE YOUR STAGE (RANDOM: the lab, with seed 1), and A again to
take the HOW TO PLAY card away. In a round the game's CPU (brawl_ket.bot.Bot,
the one its title demo uses) reads the fight and answers with a FighterInput per
fighter, and this bot presses exactly that on the two pads: the stick to
walk, jump and crouch, A, B, X and Y tapped for one frame each. The game
sees two people playing. Start is never pressed, so nothing pauses.

The demo CPU is patient: in reach it starts a string on 2% of frames, and a
round takes ~40 s. Here it is keener, the way two players who know the
colour rule are: in reach it presses the matching colour (A against its own,
B against the other) four times as often, jumps in more, and ROBERT slides in
with PHASE SLIDE. Everything else is the game's own CPU: the dodge switches
(Y), the throws on a rival who keeps switching, CHARGE NOISE and MEASURE,
the height reads, and SUPERposition: with a full bar the CPU fires its super
(A and B on the same frame) where it will land.

Two such CPUs would still trade rounds at random, so each round has a
script, as in bots/qurves.py: who wins it, and a line each fighter's health
should follow (the loser's down to 0 in ROUND_SECONDS, the winner's to
WINNER_LEFT). A fighter whose rival is above its line presses harder and
stops dodging; one whose rival is below it now and then presses the wrong
colour, which bounces off with the game's ping, and never finishes off the
round's winner (a super is never fired at the round's winner with 25 or less
left). BOHR takes round 1 and ROBERT comes back to win 2-1 (with seed 1: K.O.s
at 28.5, 55.5 and 87.5 s; the bars carry over into round 2, where BOHR fires
WAVEFUNCTION COLLAPSE at 34.5 s and ROBERT answers with BLOCH SPHERE at 37.5 s).
The demo CPU can also flicker, Y and straight back, so switches are kept
SWITCH_GAP apart.

To re-cut HIGHLIGHTS after a change, capture with BRAWL_REEL_LOG=<file>: the
bot writes each super, knockdown and round end there with its time (the bot's
clock, about 0.3 s behind the clip's).
"""

import os
from dataclasses import replace

from brawl_ket import match as M
from brawl_ket.bot import STRIKE_RANGE, Bot as CPU
from brawl_ket.fighter import FighterInput

SECONDS = 90.0
SKIP = 3.8  # title 0.4 s, select 0.7 s, stage 0.35 s, HOW TO PLAY 0.35 s, then ROUND 1 / FIGHT!;
            # the fight starts at 3.77 s
HIGHLIGHTS = [  # 2 s windows with seed 1, best first (checked frame by frame, 2026-10-22)
    37.4,   # SUPERposition! ROBERT's BLOCH SPHERE: the call, the sphere rolls in, the H-gate
            # uppercut flips its arrow to |1> and ROBERT from purple to green
    34.3,   # SUPERposition! BOHR's WAVEFUNCTION COLLAPSE: the call, the cloud, the pillar
    26.6,   # BOHR's CHARGE NOISE crackles round ROBERT, then K.O.: BOHR WINS THE ROUND
    21.6,   # ROBERT jumps clean over BOHR, lands and sweeps him down
    85.8,   # match point: the last kicks, K.O. in slow motion, ROBERT WINS THE ROUND
    54.0,   # end of round 2: purple hits on BOHR, K.O.
    4.0,    # the opening: both switch, BOHR's purple CHARGE NOISE
    80.0,   # CHARGE NOISE against ROBERT's kicks; BOHR knocked down
]

MENU_GAP = 20  # frames between two menu presses
STRIKE = 0.08  # chance per frame in reach of starting a string (the demo CPU: 0.02)
JUMP_IN = 0.012  # chance per frame, well out of reach, of jumping in (the demo CPU: 0.01)
SLIDE = 0.015  # chance per frame, just out of reach, of a PHASE SLIDE
SLIDE_RANGE = 105  # px: PHASE SLIDE's lunge reaches about this far

# The script: who wins each round, and the health both should have as it goes.
ROUND_WINNERS = ("p2", "p1", "p1")
ROUND_SECONDS = 20.0  # the loser's health runs down to 0 over this long ...
WINNER_LEFT = 0.3  # ... and the winner's to this (a share of its health)
GAIN = 5.0  # strike rate x (1 + GAIN * how far the rival is above its line)
MISREAD = 3.0  # misread the colour (the attack bounces off) with chance MISREAD x how far the
               # rival is below its line, beyond 0.05 ...
SPARE = 0.25  # ... and always, against the round's winner with less health than this left
DODGE_AT = 0.12  # this far above its own line, a fighter stops dodging
SWITCH_GAP = 40  # frames between two switches (the demo CPU can flicker: Y, and Y back)
DICE = 5  # added to the CPUs' dice (from the capture's seed): picks a good match


class Keen(CPU):
    """The game's CPU, quicker to strike, and following the round's script."""

    def __init__(self, player, seed, winner):
        super().__init__(player, seed)
        self.winner = winner
        self.switched = -SWITCH_GAP  # when it last pressed Y

    def excess(self, key, f):
        """How far `f` (player `key`) is above the health the script wants it to have now."""
        left = WINNER_LEFT if key == self.winner else 0.0
        line = 1 - (1 - left) * min(1.0, self.t / 60 / ROUND_SECONDS)
        return f.health / f.char.health - line

    def _on_ground(self, fight, me, rival, toward, dist):
        if not self.chain and self.gap == 0:
            roll = self.rng.random()
            push = self.excess(self.rival, rival)
            if dist <= STRIKE_RANGE and roll < STRIKE * min(2.0, max(0.3, 1 + GAIN * push)):
                if self.rng.random() < 0.25:
                    self.down = not self.down  # strike at the other height
                button = self.matching(me, rival)
                self.chain = [button, button] if button == "a" else [button]
                return self._press(self.chain.pop(0), 0)
            slide = me.char.moves["crouch.X"]
            if slide.lunge and STRIKE_RANGE < dist <= SLIDE_RANGE and roll < SLIDE \
                    and self.would_hurt(me, slide, rival):
                self.down = True
                return self._press("x", 0)
            if dist > STRIKE_RANGE + 30 and roll < JUMP_IN:
                self.down = False
                return FighterInput(up=True, dx=toward)
        return super()._on_ground(fight, me, rival, toward, dist)

    def input(self, fight):
        """The CPU's answer, but while the rival is behind the script an attack now and
        then comes out in the wrong colour and bounces off, the round's winner is never
        finished off, and a switch is never undone at once."""
        inp = super().input(fight)
        me, rival = fight.fighters[self.player], fight.fighters[self.rival]
        if inp.a and inp.b:     # SUPERposition: the CPU fires its super (never at the round's winner, low)
            if self.rival == self.winner and rival.health < SPARE * rival.char.health + 25:
                inp = replace(inp, a=False, b=False)
            return inp
        if inp.a or inp.b or inp.x:
            chance = MISREAD * (-self.excess(self.rival, rival) - 0.05)
            if self.rival == self.winner and rival.health < SPARE * rival.char.health:
                chance = 1.0
            if self.rng.random() < chance:
                wrong = "b" if self.matching(me, rival) == "a" else "a"
                inp = replace(inp, dx=0, a=wrong == "a", b=wrong == "b", x=False)
        if inp.y:
            if self.t - self.switched < SWITCH_GAP:
                inp = replace(inp, y=False)
            else:
                self.switched = self.t
        return inp

    def _wants_dodge(self, me, rival):
        return self.excess(self.player, me) < DODGE_AT and super()._wants_dodge(me, rival)


class Bot:
    def __init__(self, pads, rng):
        self.pads, self.rng = pads, rng
        self.dice = rng.randrange(1 << 30) + DICE
        self.wait = MENU_GAP
        self.fight = None
        self.cpus = {}

    def update(self, t):
        game = self.pads.loop.get("match")
        if game is None:
            return
        if game.state in (M.ROUND_INTRO, M.FIGHT, M.ROUND_END) and not game.paused:
            self.play(game)
            log = os.environ.get("BRAWL_REEL_LOG")      # (for picking HIGHLIGHTS: what happened when)
            if log:
                f = game.fight
                with open(log, "a") as out:
                    frozen = f.freeze > 0
                    if frozen and not getattr(self, "_frozen", False):
                        out.write(f"{t:.2f} super {f.supers[0]} {f.fighters[f.supers[0]].char.name}\n")
                    self._frozen = frozen
                    for k, fi in f.fighters.items():
                        if fi.action == "knockdown" and fi.frame == 1:
                            out.write(f"{t:.2f} down {k} health {fi.health}\n")
                    if f.over and not getattr(self, "_logged_over", None) is f:
                        self._logged_over = f
                        out.write(f"{t:.2f} over winner {f.winner}\n")
            return
        # Menus: one press (a single frame) every MENU_GAP frames.
        self.pads.release_all()
        if self.wait > 0:
            self.wait -= 1
            return
        self.wait = MENU_GAP
        if game.state == M.TITLE:
            self.pads.tap(0, "a", 1)
        elif game.state == M.SELECT:
            self.pads.tap(1 if game.ready["p1"] else 0, "a", 1)
        elif game.state == M.STAGE_SELECT:  # RANDOM; MENU_GAP is past STAGE_LOCK
            self.pads.tap(0, "a", 1)
        elif game.state == M.TUTORIAL:     # any button goes on; MENU_GAP is past its lock
            self.pads.tap(0, "a", 1)

    def play(self, game):
        fight = game.fight
        if fight is not self.fight:  # a new round: fresh CPUs
            self.fight = fight
            winner = ROUND_WINNERS[min(game.round_no, len(ROUND_WINNERS)) - 1]
            self.cpus = {p: Keen(p, self.dice + 10 * game.round_no + i, winner)
                         for i, p in enumerate(M.PLAYERS)}
        if game.state != M.FIGHT:
            self.pads.release_all()
            return
        for player, cpu in enumerate(self.cpus.values()):
            inp = cpu.input(fight)
            self.pads.stick(player, inp.dx, -1.0 if inp.up else 1.0 if inp.down else 0.0)
            for button in "abxy":
                if getattr(inp, button):
                    self.pads.tap(player, button, 1)
