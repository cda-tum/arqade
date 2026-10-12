"""Brawl-Ket: TRIO against QUINT, both fought by the game's own CPU.

A on the title (on PLAY: the bot never moves the stick there, so never onto
QUIT), then A on each pad at the character select, which keeps the game's
default pairing: P1 TRIO on the left (blue ring), P2 QUINT on the right (red
ring), then A again to take the HOW TO PLAY card away. In a round the game's CPU (brawl_ket.bot.Bot, the one its
title demo uses) reads the fight and answers with a FighterInput per
fighter, and this bot presses exactly that on the two pads: the stick to
walk, jump and crouch, A, B, X and Y tapped for one frame each. The game
sees two people playing. Start is never pressed, so nothing pauses.

The demo CPU is patient: in reach it starts a string on 2% of frames, and a
round takes ~40 s. Here it is keener, the way two players who know the
colour rule are: in reach it presses the matching colour (A against its own,
B against the other) four times as often, jumps in more, and TRIO slides in
with PHASE SLIDE. Everything else is the game's own CPU: the dodge switches
(Y), the throws on a rival who keeps switching, CHARGE NOISE and MEASURE,
the height reads.

Two such CPUs would still trade rounds at random, so each round has a
script, as in bots/qurves.py: who wins it, and a line each fighter's health
should follow (the loser's down to 0 in ROUND_SECONDS, the winner's to
WINNER_LEFT). A fighter whose rival is above its line presses harder and
stops dodging; one whose rival is below it now and then presses the wrong
colour, which bounces off with the game's ping, and never finishes off the
round's winner. QUINT takes round 1 and TRIO comes back to win 2-1 (with
seed 1: K.O.s at 23.5, 52 and 78 s, then P1 WINS! to the end). The demo CPU
can also flicker, Y and straight back, so switches are kept SWITCH_GAP apart.
"""

from dataclasses import replace

from brawl_ket import match as M
from brawl_ket.bot import STRIKE_RANGE, Bot as CPU
from brawl_ket.fighter import FighterInput

SECONDS = 85.0
SKIP = 3.45  # title 0.4 s, select 0.7 s, HOW TO PLAY 0.35 s, then ROUND 1 / FIGHT!; the fight
             # starts at 3.45 s
HIGHLIGHTS = [  # 2 s windows with seed 1, best first (HOW TO PLAY moved them all 0.35 s on)
    35.65,  # QUINT's CHARGE NOISE shocks TRIO, TRIO switches (H) and the shocks bounce off,
            # then TRIO knocks QUINT down
    22.25,  # end of round 1: TRIO sweeps QUINT down, QUINT switches, throws TRIO: K.O.
    57.35,  # round 3: a green hit, QUINT switches and the next one bounces, CHARGE NOISE
            # against a HADAMARD DIVE
    3.85,  # the opening: both switch, a PHOTON, a PHASE SLIDE knocks QUINT down
    76.85,  # match point: purple hits on QUINT, K.O. in slow motion, TRIO WINS THE ROUND
    67.55,  # knockdowns traded: QUINT down, TRIO thrown, QUINT down again
    38.55,  # a sweep, QUINT's MEASURE, TRIO knocked down
    50.75,  # end of round 2: TRIO lands the last purple hits, K.O.
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

    def _on_ground(self, me, rival, toward, dist):
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
        return super()._on_ground(me, rival, toward, dist)

    def input(self, fight):
        """The CPU's answer, but while the rival is behind the script an attack now and
        then comes out in the wrong colour and bounces off, the round's winner is never
        finished off, and a switch is never undone at once."""
        inp = super().input(fight)
        me, rival = fight.fighters[self.player], fight.fighters[self.rival]
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
