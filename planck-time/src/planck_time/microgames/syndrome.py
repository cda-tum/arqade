"""SYNDROME! (boss): keep a logical qubit alive until the time runs out.

Five data qubits sit in a row on a chip: a distance-5 repetition code. On
each link between neighbours is a parity check, a ZZ stabilizer read out by
an ancilla, so there are four. From time to time an X error lands on a data
qubit. The qubit looks unchanged (you never see an error directly, that is
the point of syndrome measurement), but it flips the checks on both sides of
it: an error in the middle lights the two checks either side, one on an end
qubit lights the one check next to it. The noise itself is a crackle over
the whole chip, with no position.

The noise has a face: DECOHERENCE, the monster above the chip (its art is in
decoherence.py). It winds up before every error and spits a bolt that
splashes over the whole chip, the same wherever the error landed, so the
checks stay the only clue. It flinches at a fix, grins at a wrong press,
laughs at a logical error and dissolves when the qubit survives.

The stick steps a cursor along the qubits and A applies an X. On a flipped
qubit that undoes the error and its checks go dark; on any other qubit it is
a new error, and the checks change accordingly. Once 3 of the 5 qubits are
flipped, the majority vote reads the wrong value: a logical error, and a
fail. Surviving to the end wins.

  phase 1: one error at a time, in the middle three qubits. The next lands
           2.0 s after the chip is clean, or 3.0 s after the last one if it's
           left alone (that is how idle loses: 3 flips by about 40% of the time).
  phase 2: faster (1.3 s), and its second error comes with a second one: a
           lit pair plus a lone check at an end.
  phase 3: the cases that need reading, with room to think (2.2 s): first
           an end qubit (one lit check, next to the edge), then an adjacent
           pair, whose shared check cancels, so the lit checks are two links
           apart and the fix is both qubits in between.
All the times shrink with the level's speed, like the fight itself.

Every pattern that lands is one a player can read: with only five qubits,
two errors one apart in the middle (qubits 1 and 3) would light all four
checks, so a press on the qubit between them would be a third error. That
case and its kin never land (see READABLE); a player's own wrong press can
still make them, which is exact.
"""

from __future__ import annotations

import math
import random

import pygame

from planck_time import decoherence
from planck_time import palette as P
from planck_time.microgames.base import IDLE, Boss, H, PlayerInput, W, register_boss
from planck_time.pixel import backdrop, blit_center, card, control_hint, outlined, result_overlay

N = 5  # data qubits
LOSE_AT = 3  # flipped qubits that outvote the rest
ROW_Y = 95
SPACING = 44
ORB_R = 9
CHECK = 14  # a check's square
DIE = pygame.Rect(10, 68, W - 20, 58)
MONSTER = (W // 2, 30)  # DECOHERENCE, in the top 60 px

FIRST = 0.8  # seconds before the first error
PAUSE = (2.0, 1.3, 2.2)  # after the chip is clean, by phase...
PATIENCE = (3.0, 2.6, 3.4)  # ...or this long after the last error, fixed or not
# What lands on a clean chip, by phase. Each phase opens with its own cases
# in a fixed order, so every fight shows them all; after that it's a draw.
DOUBLE_AT = 1  # phase 2: its second error comes with a second one...
DOUBLE = 0.1  # ...and so do this many of the later ones
PAIRED = 0.3  # phase 3, after an end qubit and then an adjacent pair: the chance of a pair...
BOTH_ENDS = 0.1  # ...or of both end qubits at once (the rest: one end qubit)
CRACKLE = 0.3  # seconds the noise crackles
PULSE = 0.35
ZAP = 0.25
FLIP_TIME = 0.4  # the logical error turning every qubit over
WINDUP = 0.5  # the monster winds up this long before an error lands...
BOLT = CRACKLE  # ...then its bolt crackles over the chip
FLINCH = 0.4  # it flinches this long at a fix...
GRIN = 0.6  # ...and grins this long at a wrong press
WIN_FLASH = 0.2

# The two-error patterns whose lit checks point at their qubits unmistakably.
# The rest are traps for a reader: {0,1} lights one check that is not next to
# an edge, {0,2} and {2,4} three checks in a row, {1,3} all four.
READABLE = ({0, 3}, {1, 4}, {0, 4}, {1, 2}, {2, 3})
SPLIT = ((0, 3), (1, 4))  # phase 2's two at once: a lit pair and a lone end check
ADJACENT = ((1, 2), (2, 3))  # phase 3: the shared check cancels
ENDS = (0, 4)
MIDDLE = (1, 2, 3)

BOT_THINK = 0.2  # the bot looks before it moves...
BOT_STEP = 0.12  # ...then steps at a human pace


def syndrome(flips) -> list[int]:
    """The four checks: check i compares qubits i and i+1."""
    return [int((i in flips) != (i + 1 in flips)) for i in range(N - 1)]


def qubit_x(i: float) -> int:
    return round(W // 2 + (i - (N - 1) / 2) * SPACING)


@register_boss
class Syndrome(Boss):
    VERB = "SYNDROME!"
    INPUT = "stick+a"
    STEPS = True
    CAPTION = "Parity checks find errors without measuring the qubits"
    BOSS_NAME = "DECOHERENCE"
    BOSS_TITLE = "THE NOISE"

    def __init__(self, seed: int, level: int, duration: float) -> None:
        super().__init__(seed, level, duration)
        self.flips: set[int] = set()  # hidden: only the checks show it
        self.cursor = N // 2
        self.next_at = FIRST / self.speed
        self.landed_at = -1.0
        self.bot_stepped_at = -1.0
        self.landings = [0, 0, 0]  # errors landed on a clean chip, by phase
        self.pulses: list[tuple[int, float]] = []  # qubits fixed, and when
        self.zaps: list[tuple[int, float]] = []  # X presses, and when
        self.fixed_at = -1.0  # the last right press and the last wrong one,
        self.wrong_at = -1.0  # for the monster's face only
        self.backdrop = P.BACKDROPS[self.rng.randrange(len(P.BACKDROPS))]

    # --- the rules ----------------------------------------------------------------------

    @property
    def phase(self) -> int:
        """0, 1 or 2: the thirds of the fight (phases 1 to 3 above)."""
        return min(2, int(3 * self.t / self.duration))

    def step(self, dt: float, inp: PlayerInput) -> None:
        if inp.step[0]:
            self.cursor = max(0, min(N - 1, self.cursor + inp.step[0]))
        if inp.a:
            q = self.cursor
            self.zaps = [z for z in self.zaps if self.t - z[1] < ZAP] + [(q, self.t)]
            if q in self.flips:
                self.flips.discard(q)
                self.pulses = [p for p in self.pulses if self.t - p[1] < PULSE] + [(q, self.t)]
                self.fixed_at = self.t
                if not self.flips:  # clean: the next one after a pause
                    pause = PAUSE[self.phase] * self.rng.uniform(0.85, 1.15) / self.speed
                    self.next_at = min(self.next_at, self.t + pause)
            else:
                self.flips.add(q)  # a wrong press is a new error
                self.wrong_at = self.t
        if self.t >= self.next_at and len(self.flips) < LOSE_AT:
            self._land()
        if len(self.flips) >= LOSE_AT:
            self.fail()

    def _land(self) -> None:
        """Noise: one or two X errors, drawn for the phase, never a trap."""
        rng = self.rng
        phase = self.phase
        free = [q for q in range(N) if q not in self.flips]
        if len(self.flips) == 1:  # one left alone: its partner keeps it readable
            hits = [rng.choice([q for q in free if self.flips | {q} in READABLE])]
        elif self.flips:  # two left alone: the third one is fatal
            hits = [rng.choice(free)]
        else:
            hits = self._fresh(phase, self.landings[phase])
            self.landings[phase] += 1
        self.flips.update(hits)
        self.landed_at = self.t
        self.next_at = self.t + PATIENCE[phase] / self.speed

    def _fresh(self, phase: int, k: int) -> list[int]:
        """The k-th error of a phase to land on a clean chip."""
        rng = self.rng
        if phase == 1 and (k == DOUBLE_AT or k > DOUBLE_AT and rng.random() < DOUBLE):
            return list(rng.choice(SPLIT))
        if phase == 2:
            kind = 1.0 if k == 0 else 0.0 if k == 1 else rng.random()
            if kind < PAIRED:
                return list(rng.choice(ADJACENT))
            if kind < PAIRED + BOTH_ENDS:
                return list(ENDS)
            return [rng.choice([q for q in ENDS if q != self.cursor])]
        return [rng.choice([q for q in MIDDLE if q != self.cursor])]

    def timeout(self) -> None:
        self.win()  # the logical qubit survived

    # --- the bot (it cheats: it knows which qubits are flipped) ---------------------------

    def bot(self) -> PlayerInput:
        """Look for 0.2 s, step towards the nearest flipped qubit every 0.12 s, press A.
        It keeps its own step clock, so a stray push in between doesn't hold it up."""
        if not self.flips or self.t - self.landed_at < BOT_THINK:
            return IDLE
        target = min(self.flips, key=lambda q: (abs(q - self.cursor), q))
        if target == self.cursor:
            return PlayerInput(a=True, a_held=True)
        if self.t - self.bot_stepped_at < BOT_STEP - 1e-9:
            return IDLE
        self.bot_stepped_at = self.t
        return PlayerInput(step=(1 if target > self.cursor else -1, 0))

    # --- drawing ----------------------------------------------------------------------

    @classmethod
    def portrait(cls, surf: pygame.Surface, center, t: float) -> None:
        decoherence.portrait(surf, center, t)

    def windup(self) -> float:
        """0..1 through the monster's wind-up before the next error lands (0 when
        none is coming before the end). It hangs on the landing time alone."""
        left = self.next_at - self.t
        if self.result is not None or self.next_at >= self.duration or left >= WINDUP:
            return 0.0
        return max(0.0, min(1.0, 1.0 - left / WINDUP))

    def draw(self, surf: pygame.Surface) -> None:
        backdrop(surf, self.backdrop, self.t)
        t = self.t
        failed = self.result is False
        flip = min(1.0, self.since_end / FLIP_TIME) if failed else 0.0
        self._die(surf, failed)
        # a logical error: every qubit turns over, which is a codeword again,
        # so the checks go dark. Nothing can see it any more, and it's wrong.
        checks = [0] * (N - 1) if flip >= 0.5 else syndrome(self.flips)
        # the links, a wire through every qubit and check
        x0, x1 = qubit_x(0), qubit_x(N - 1)
        surf.fill(P.INK, (x0, ROW_Y - 3, x1 - x0, 7))
        surf.fill(P.SLATE, (x0, ROW_Y - 2, x1 - x0, 5))
        surf.fill(P.MIST, (x0, ROW_Y - 1, x1 - x0, 1))
        glow = int(t * 6) % 2
        for i, lit in enumerate(checks):
            cx = (qubit_x(i) + qubit_x(i + 1)) // 2
            r = pygame.Rect(0, 0, CHECK, CHECK)
            r.center = (cx, ROW_Y)
            if lit:  # a red half-wire to each neighbour, and a glow
                for side in (-1, 1):
                    a, b = sorted((cx, cx + side * (SPACING // 2 - ORB_R - 1)))
                    surf.fill(P.INK, (a, ROW_Y - 3, b - a, 7))
                    surf.fill(P.BAD, (a, ROW_Y - 2, b - a, 5))
                    surf.fill(P.lighten(P.BAD, 0.5), (a, ROW_Y - 1, b - a, 1))
                halo = r.inflate(5 + 2 * glow, 5 + 2 * glow)
                pygame.draw.rect(surf, P.INK, halo.inflate(2, 2), 3, border_radius=5)
                pygame.draw.rect(surf, P.lighten(P.BAD, 0.4), halo, 1, border_radius=5)
                card(surf, r, P.BAD)
                blit_center(surf, outlined("1", 8, P.WHITE, shadow=False), (r.centerx + 1, r.centery))
            else:
                card(surf, r, P.NIGHT)
                blit_center(surf, outlined("0", 8, P.SLATE, shadow=False), (r.centerx + 1, r.centery))
            # the ancilla's readout line down to the die's edge
            surf.fill(P.INK, (cx - 1, r.bottom + 1, 3, DIE.bottom - r.bottom - 4))
            surf.fill(P.BAD if lit else P.SLATE, (cx, r.bottom + 1, 1, DIE.bottom - r.bottom - 5))

        for i in range(N):
            self._qubit(surf, i, flip)
        if self.result is None:
            self._cursor(surf)
        for q, at in self.zaps:  # the X just applied, popping up
            k = (t - at) / ZAP
            if 0 <= k < 1:
                r = pygame.Rect(0, 0, 13, 13)
                r.center = (qubit_x(q), ROW_Y - 22 - round(6 * k))
                card(surf, r, P.GATE["X"])
                blit_center(surf, outlined("X", 8, P.WHITE, shadow=False), (r.centerx + 1, r.centery))
        # the attack: nothing in it depends on which qubit was hit
        attack = t - self.landed_at < BOLT and self.result is not True
        if t - self.landed_at < CRACKLE and self.result is None:
            self._crackle(surf)
        if attack:
            decoherence.splash(surf, DIE, t - self.landed_at, t)
        if not failed:
            self._monster(surf)
        if attack:
            decoherence.bolt(surf, decoherence.mouth(MONSTER), (W // 2, DIE.y), t)
        self._danger(surf, failed)
        if failed:
            blit_center(surf, outlined("LOGICAL ERROR!", 8, P.BAD), (W // 2, H - 14))
        elif self.result:
            blit_center(surf, outlined("QUBIT SAVED!", 8, P.GOOD), (W // 2, H - 14))
        else:
            blit_center(surf, control_hint("{a} BETWEEN THE RED CHECKS", 8, P.WHITE), (W // 2, H - 14))
        if self.result and self.since_end < WIN_FLASH:
            flash = _white()
            flash.set_alpha(round(220 * (1 - self.since_end / WIN_FLASH)))
            surf.blit(flash, (0, 0))
        result_overlay(surf, self.result, self.since_end, seed=23)
        if failed:  # laughing in front of the cracks, so its face reads
            self._monster(surf)

    def _monster(self, surf) -> None:
        """DECOHERENCE, reacting to the fight. Its face only ever hangs on the
        time, the cursor and the player's own presses, never on the hidden flips."""
        t = self.t
        if self.result is True:
            decoherence.dissolve(surf, MONSTER, self.since_end)
            return
        if self.result is False:
            decoherence.draw(surf, MONSTER, t, "laugh", self.since_end)
            return
        look = (qubit_x(self.cursor), ROW_Y)
        windup = self.windup()
        if t - self.fixed_at < FLINCH:
            decoherence.draw(surf, MONSTER, t, "flinch", (t - self.fixed_at) / FLINCH, look)
        elif t - self.landed_at < BOLT:
            decoherence.draw(surf, MONSTER, t, "spit", (t - self.landed_at) / BOLT, look)
        elif windup > 0:
            decoherence.draw(surf, MONSTER, t, "windup", windup, look)
        elif t - self.wrong_at < GRIN:
            decoherence.draw(surf, MONSTER, t, "grin", (t - self.wrong_at) / GRIN, look)
        else:
            decoherence.draw(surf, MONSTER, t, "idle", 0.0, look)
        if windup > 0:
            decoherence.charge(surf, MONSTER, windup, t)

    def _die(self, surf, failed: bool) -> None:
        """The chip: a dark die with pins top and bottom, flashing red on a logical error."""
        for x in range(DIE.x + 8, DIE.right - 6, 12):
            surf.fill(P.INK, (x - 1, DIE.y - 6, 6, DIE.h + 12))
            surf.fill(P.MIST, (x, DIE.y - 5, 4, DIE.h + 10))
        color = P.NIGHT
        if failed:
            color = P.BAD if self.since_end < 0.6 and int(self.since_end * 10) % 2 == 0 else (88, 24, 48)
        pygame.draw.rect(surf, P.INK, DIE.inflate(4, 4), border_radius=5)
        pygame.draw.rect(surf, color, DIE, border_radius=4)
        surf.fill(P.SLATE, (DIE.x + 4, DIE.y + 2, DIE.w - 8, 1))

    def _qubit(self, surf, i: int, flip: float) -> None:
        """A data qubit, an orb that always reads |0>; it turns over to |1> on a logical error."""
        x = qubit_x(i)
        h = abs(math.cos(math.pi * flip))  # the turn: squash to an edge, open out again
        over = flip >= 0.5
        color = P.ORANGE if over else P.TEAL
        for q, at in self.pulses:  # fixed: a green ring and a green orb
            k = (self.t - at) / PULSE
            if q == i and 0 <= k < 1:
                rad = round(ORB_R + 3 + 9 * k)
                pygame.draw.circle(surf, P.INK, (x, ROW_Y), rad + 1, 3)
                pygame.draw.circle(surf, P.GOOD, (x, ROW_Y), rad, 1)
                color = P.GOOD
        saved = self.result is True
        if saved:
            color = P.GOLD
        ry = max(1, round(ORB_R * h))
        body = pygame.Rect(0, 0, 2 * ORB_R + 2, 2 * ry + 2)
        body.center = (x, ROW_Y)
        if saved:
            pygame.draw.circle(surf, P.lighten(color, 0.5), (x, ROW_Y), ORB_R + 3, 1)
        pygame.draw.ellipse(surf, P.INK, body.inflate(2, 2))
        pygame.draw.ellipse(surf, P.shade(color, 0.7), body)
        if ry > 3:
            hi = pygame.Rect(0, 0, 2 * ORB_R - 4, 2 * ry - 4)
            hi.center = (x - 2, ROW_Y - 2 * ry // ORB_R)
            pygame.draw.ellipse(surf, color, hi)
            surf.fill(P.lighten(color, 0.7), (x - ORB_R // 2 - 1, ROW_Y - ry // 2 - 1, 3, 2))
        label = outlined("|1>" if over else "|0>", 8, P.ORANGE if over else P.WHITE)
        blit_center(surf, label, (x + 1, ROW_Y + ORB_R + 9))

    def _cursor(self, surf) -> None:
        """A gold bracket round the qubit under the cursor, breathing."""
        x = qubit_x(self.cursor)
        s = ORB_R + 6 + (int(self.t * 4) % 2)
        box = pygame.Rect(0, 0, 2 * s, 2 * s)
        box.center = (x, ROW_Y)
        arm = 5
        for color, width in ((P.INK, 5), (P.GOLD, 2)):
            for (cx, cy), (dx, dy) in (((box.left, box.top), (1, 1)), ((box.right, box.top), (-1, 1)),
                                       ((box.left, box.bottom), (1, -1)), ((box.right, box.bottom), (-1, -1))):
                pygame.draw.line(surf, color, (cx, cy), (cx + dx * arm, cy), width)
                pygame.draw.line(surf, color, (cx, cy), (cx, cy + dy * arm), width)

    def _crackle(self, surf) -> None:
        """Static over the whole chip, with no position: only the checks say where it hit."""
        rng = random.Random(int(self.t * 30))  # the draw's own: never the game's rng
        for _ in range(70):
            x = rng.randrange(DIE.x, DIE.right - 2)
            y = rng.randrange(DIE.y, DIE.bottom - 1)
            surf.fill(rng.choice((P.WHITE, P.MIST, P.SKY)), (x, y, rng.choice((1, 2, 4)), 1))
        for _ in range(3):
            y = rng.randrange(DIE.y + 2, DIE.bottom - 2)
            surf.fill(P.MIST, (DIE.x + 2, y, DIE.w - 4, 1))

    def _danger(self, surf, failed: bool) -> None:
        """Three pips, top left: one lights per flipped qubit, and three is a logical error."""
        lit = LOSE_AT if failed else len(self.flips)
        label = outlined("DANGER", 8, P.MIST)
        surf.blit(label, (4, 4))
        x = 4 + label.get_width() + 2
        for k in range(LOSE_AT):
            c = (x + 4 + k * 11, 9)
            on = k < lit
            pygame.draw.circle(surf, P.INK, c, 5)
            pygame.draw.circle(surf, P.BAD if on else P.SLATE, c, 4)
            if on:
                surf.fill(P.lighten(P.BAD, 0.6), (c[0] - 2, c[1] - 2, 2, 1))


_WHITE: list = []


def _white() -> pygame.Surface:
    """A whole screen of white, for the win's flash (made once)."""
    if not _WHITE:
        surf = pygame.Surface((W, H))
        surf.fill(P.WHITE)
        _WHITE.append(surf)
    return _WHITE[0]
