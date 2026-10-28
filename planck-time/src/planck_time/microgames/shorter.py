"""SHORTER!: two small circuits sit side by side, and they need not do the
same thing. A compiler optimises both by cancelling gates: two identical
self-inverse gates next to each other on a wire (X X, Y Y, Z Z or H H) are
the identity, and cancelling a pair can bring two more together (X H H X
goes all the way). Push the stick left or right and press A on the circuit
that is SHORTER AFTER OPTIMISING. After the pick, the cancellations play out
on both circuits, with the gate counts, so the player sees why.

The idea is taught over the session (`appearance`, see base.spawn):
  1st time: one circuit is plainly shorter; the other carries one pair, and
            even with that pair cancelled it is still longer. The reveal
            shows that pairs cancel.
  2nd time: the circuit with more gates as written is the shorter one once
            its pairs cancel, so counting gates by eye picks wrong.
  3rd time on: both sides have pairs, some nested, and the written counts
            say nothing either way.
Picking the longer one fails, and so does never picking. The two compiled
lengths always differ.
"""

from __future__ import annotations

import math

import pygame

from planck_time import palette as P
from planck_time.microgames.base import IDLE, H, Microgame, PlayerInput, register
from planck_time.pixel import backdrop, blit_center, card, control_hint, outlined, result_overlay

KINDS = ("X", "Y", "Z", "H")  # all self-inverse: a pair of any of them cancels
SLOTS = 4  # gates per wire
WIRES = 2
CARD = 16
PITCH = 18  # px from one gate to the next
PANEL_X = (4, 128)  # left and right circuits
PANEL_Y, PANEL_W, PANEL_H = 22, 108, 96
WIRE_GAP = 36
REVEAL_FLASH = 0.45  # seconds the cancelling gates flash before they go
THINK = 0.7  # the bot looks before it moves...
BOT_STEP = 0.25  # ...moves at a human pace...
BOT_SETTLE = 0.3  # ...and checks once more before pressing A


def cancelled(wire: list[str]) -> set[int]:
    """Indices of the gates a compiler removes from a wire: adjacent identical
    pairs, repeatedly, so a cancellation can bring the next pair together."""
    stack: list[int] = []
    gone: set[int] = set()
    for i, kind in enumerate(wire):
        if stack and wire[stack[-1]] == kind:
            gone.update((stack.pop(), i))
        else:
            stack.append(i)
    return gone


def written(circuit) -> int:
    return sum(len(w) for w in circuit)


def compiled(circuit) -> int:
    return sum(len(w) - len(cancelled(w)) for w in circuit)


def plain(rng, n: int) -> list[str]:
    """n gates with no two identical in a row: nothing cancels."""
    seq: list[str] = []
    while len(seq) < n:
        k = rng.choice(KINDS)
        if not seq or seq[-1] != k:
            seq.append(k)
    return seq


def build(rng, cores: list[int], pairs: list[int], nest: bool = False) -> list[list[str]] | None:
    """A circuit from irreducible wire lengths and pairs per wire, or None if
    a wire would not fit."""
    circuit = []
    for n, p in zip(cores, pairs):
        wire = plain(rng, n)
        for _ in range(p):
            k = rng.choice(KINDS)
            if nest and len(wire) >= 2 and rng.random() < 0.5:
                # a cascade: k (a pair that already cancels) k
                j = rng.randrange(len(wire) - 1)
                if wire[j] == wire[j + 1]:
                    wire[j:j] = [k]
                    wire[j + 3:j + 3] = [k]
                    continue
            wire[rng.randrange(len(wire) + 1):0] = [k, k]
        if len(wire) > SLOTS:
            return None
        circuit.append(wire)
    return circuit


def split(rng, total: int) -> list[int]:
    """`total` spread over the wires, each at most SLOTS."""
    while True:
        parts = [0] * WIRES
        for _ in range(total):
            parts[rng.randrange(WIRES)] += 1
        if all(p <= SLOTS for p in parts):
            return parts


@register
class Shorter(Microgame):
    VERB = "SHORTER!"
    INPUT = "stick+a"
    STEPS = True
    CAPTION = "Compilers cancel gates to make circuits shorter"

    def __init__(self, seed: int, level: int, duration: float) -> None:
        super().__init__(seed, level, duration)
        stage = min(self.appearance, 2)
        self.looks = self.rng.choice((1, 1, 0, -1))  # stage 3 on: answer looks longer / same / shorter
        for _ in range(2000):
            pair = self._candidate(stage)
            if pair is not None:
                answer, decoy = pair
                break
        else:  # never seen in testing; fail loudly rather than build a broken round
            raise RuntimeError(f"no SHORTER! round found for seed {seed}, stage {stage}")
        self.stage = stage
        self.short = self.rng.randrange(2)  # which side is the right answer
        self.circuits = [answer, decoy] if self.short == 0 else [decoy, answer]
        self.gone = [[cancelled(w) for w in c] for c in self.circuits]
        self.cursor = self.rng.randrange(2)
        self.moved_at = 0.0
        self.picked: int | None = None
        self.backdrop = P.BACKDROPS[self.rng.randrange(len(P.BACKDROPS))]

    def _candidate(self, stage: int):
        """(answer, decoy) for this stage, or None to try again."""
        rng = self.rng
        if stage == 0:  # plainly shorter vs. longer-with-one-pair, still longer after it
            n = rng.choice((2, 3))
            answer = build(rng, split(rng, n), [0] * WIRES)
            core = n + rng.choice((1, 2))
            pairs = [0] * WIRES
            pairs[rng.randrange(WIRES)] = 1
            decoy = build(rng, split(rng, core), pairs)
        elif stage == 1:  # more gates as written, fewer once its pairs cancel
            n = rng.choice((3, 4, 5))
            decoy = build(rng, split(rng, n), [0] * WIRES)
            core = rng.randrange(1, n)
            pairs = split(rng, rng.choice((1, 2)))
            answer = build(rng, split(rng, core), pairs)
            if answer is not None and decoy is not None and written(answer) <= written(decoy):
                return None
        else:  # pairs on both sides, some nested: the counts as written say nothing
            nest = self.level >= 2 or stage >= 2
            a_core, d_core = rng.randrange(1, 5), rng.randrange(1, 5)
            answer = build(rng, split(rng, a_core), split(rng, rng.choice((1, 2))), nest)
            decoy = build(rng, split(rng, d_core), split(rng, rng.choice((1, 2))), nest)
            if answer is None or decoy is None:
                return None
            # how the answer looks as written: longer half the time, the same a quarter,
            # honestly shorter a quarter, so neither counting nor "pick the longer" works
            want = self.looks
            have = (written(answer) > written(decoy)) - (written(answer) < written(decoy))
            if have != want:
                return None
        if answer is None or decoy is None:
            return None
        if compiled(answer) >= compiled(decoy):
            return None
        if stage == 0 and written(answer) >= written(decoy):
            return None
        return answer, decoy

    def step(self, dt: float, inp: PlayerInput) -> None:
        dx = inp.step[0]
        if dx:
            side = 0 if dx < 0 else 1
            if side != self.cursor:
                self.cursor = side
                self.moved_at = self.t
        if inp.a:
            self.picked = self.cursor
            if self.cursor == self.short:
                self.win()
            else:
                self.fail()

    def bot(self) -> PlayerInput:
        since = self.t - self.moved_at
        if self.t < THINK:
            return IDLE
        if self.cursor != self.short:
            return PlayerInput(step=(1 if self.short else -1, 0)) if since >= BOT_STEP else IDLE
        return PlayerInput(a=True, a_held=True) if since >= BOT_SETTLE else IDLE

    # --- drawing ----------------------------------------------------------------------

    def wire_ys(self) -> list[int]:
        mid = PANEL_Y + PANEL_H // 2
        return [round(mid + (i - (WIRES - 1) / 2) * WIRE_GAP) for i in range(WIRES)]

    def draw(self, surf: pygame.Surface) -> None:
        backdrop(surf, self.backdrop, self.t)
        blink = int(self.t * 6) % 2
        revealing = self.result is not None
        compact = revealing and self.since_end >= REVEAL_FLASH
        for side, x in enumerate(PANEL_X):
            panel = pygame.Rect(x, PANEL_Y, PANEL_W, PANEL_H)
            chosen = side == self.cursor if self.picked is None else side == self.picked
            pygame.draw.rect(surf, P.INK, panel.inflate(4, 4), border_radius=6)
            pygame.draw.rect(surf, P.NIGHT, panel, border_radius=5)
            surf.fill(P.SLATE, (panel.x + 4, panel.y + 2, panel.w - 8, 1))
            if chosen:
                if self.result is None:
                    edge = P.GOLD if blink else P.WHITE
                else:
                    edge = P.GOOD if self.result else P.BAD
                pygame.draw.rect(surf, edge, panel.inflate(4, 4), 3, border_radius=6)
            else:
                pygame.draw.rect(surf, P.SLATE, panel, 1, border_radius=5)
            for y, wire, gone in zip(self.wire_ys(), self.circuits[side], self.gone[side]):
                blit_center(surf, outlined("|0>", 8, P.WHITE), (x + 15, y))
                surf.fill(P.INK, (x + 29, y - 2, PANEL_W - 33, 5))
                surf.fill(P.MIST, (x + 29, y - 1, PANEL_W - 33, 3))
                slot = 0
                for i, kind in enumerate(wire):
                    if compact and i in gone:
                        continue  # optimised away
                    r = pygame.Rect(0, 0, CARD, CARD)
                    r.center = (x + 39 + PITCH * slot, y)
                    slot += 1
                    card(surf, r, P.GATE[kind])
                    blit_center(surf, outlined(kind, 8, P.WHITE, shadow=False), (r.centerx + 1, r.centery))
                    if revealing and not compact and i in gone and blink:
                        pygame.draw.rect(surf, P.GOLD, r.inflate(4, 4), 2, border_radius=5)
            if revealing:  # the gate counts, as written and after optimising
                before, after = written(self.circuits[side]), compiled(self.circuits[side])
                label = f"{before}->{after} GATES" if compact else f"{before} GATES"
                blit_center(surf, outlined(label, 8, P.GOLD if compact else P.WHITE), (panel.centerx, panel.bottom - 8))
            if chosen and self.result is None:  # a bouncing arrow over the picked side
                cx, top = panel.centerx, PANEL_Y - 6 + round(2 * math.sin(self.t * 8))
                tri = [(cx - 6, top - 6), (cx + 6, top - 6), (cx, top)]
                pygame.draw.polygon(surf, P.INK, [(px, py + 1) for px, py in tri])
                pygame.draw.polygon(surf, P.GOLD, tri)
            if chosen and self.result is False and not compact:  # a red X over the wrong pick
                c = panel.center
                for d in ((-1, -1), (1, -1)):
                    a, b = (c[0] - 22 * d[0], c[1] - 22 * d[1]), (c[0] + 22 * d[0], c[1] + 22 * d[1])
                    pygame.draw.line(surf, P.INK, a, b, 9)
                    pygame.draw.line(surf, P.BAD, a, b, 5)
        hint = "{a} ON THE SHORTER ONE" if self.stage == 0 else "PAIRS CANCEL! PICK SHORTER"
        blit_center(surf, control_hint(hint, 8, P.WHITE), (120, H - 14))
        result_overlay(surf, self.result, self.since_end, seed=11)
