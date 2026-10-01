"""SHORTER!: two small circuits sit side by side and do the same thing, but
one carries redundant gates: an adjacent pair of the same self-inverse gate
(X X, Z Z or H H), which cancels out. Push the stick left or right to pick a
side and press A on the circuit with fewer gates.

Picking the longer one fails, and so does never picking. The shorter
circuit's own wires never hold two identical gates in a row, so it has
nothing left to remove. At level 0 the longer circuit has two pairs more (or
one, on a single wire); from level 2 it has just one more, among more gates.

From level 2, half the rounds are a twist: the circuit with the redundant
pairs is the one that *looks* longer but compiles shorter. The other one
does the same thing with a gate swapped for an equal sandwich (Z = H X H,
X = H Z H): longer, and nothing on it is a pair that cancels. Still exact,
so the "=" between them still holds, and the rule is the same: fewest gates
once identical neighbours cancel.
"""

from __future__ import annotations

import math

import pygame

from planck_time import palette as P
from planck_time.microgames.base import IDLE, H, Microgame, PlayerInput, register
from planck_time.pixel import backdrop, blit_center, card, outlined, result_overlay

KINDS = ("X", "Y", "Z", "H")
PAIRS = ("X", "Z", "H")  # the self-inverse pairs that get inserted
SANDWICH = {"Z": ("H", "X", "H"), "X": ("H", "Z", "H")}  # H X H = Z and H Z H = X, exactly
TWIST_FROM = 2  # the level from which the pairs can be the shorter side
SLOTS = 4  # gates per wire
CARD = 16
PITCH = 18  # px from one gate to the next
PANEL_X = (4, 128)  # left and right circuits
PANEL_Y, PANEL_W, PANEL_H = 24, 108, 96
WIRE_GAP = 36
THINK = 0.7  # the bot looks before it moves...
BOT_STEP = 0.25  # ...moves at a human pace...
BOT_SETTLE = 0.3  # ...and checks once more before pressing A


def sequence(rng, n: int) -> list[str]:
    """n random gates with no two identical in a row: nothing that cancels."""
    seq: list[str] = []
    while len(seq) < n:
        k = rng.choice(KINDS)
        if not seq or seq[-1] != k:
            seq.append(k)
    return seq


def with_pairs(rng, wire: list[str], pairs: int) -> list[tuple[str, bool]]:
    """The wire with `pairs` redundant pairs slotted in between its gates, each
    a kind its neighbours aren't, so it reads as one clear pair. Returns
    (kind, redundant) per gate."""
    units = [[(k, False)] for k in wire]
    for _ in range(pairs):
        i = rng.randrange(len(units) + 1)
        near = {units[i - 1][-1][0] if i > 0 else None, units[i][0][0] if i < len(units) else None}
        k = rng.choice([p for p in PAIRS if p not in near])
        units.insert(i, [(k, True), (k, True)])
    return [g for u in units for g in u]


def sandwiched(rng, wire: list[str], count: int) -> list[str] | None:
    """The wire with `count` of its X/Z gates swapped for the equal H.H
    sandwich, or None if that would put two identical gates side by side."""
    spots = [i for i, k in enumerate(wire) if k in SANDWICH]
    if len(spots) < count:
        return None
    out = list(wire)
    for i in sorted(rng.sample(spots, count), reverse=True):
        out[i:i + 1] = SANDWICH[out[i]]
    if any(a == b for a, b in zip(out, out[1:])):
        return None
    return out


def no_pairs(wire) -> bool:
    return all(a != b for a, b in zip(wire, wire[1:]))


@register
class Shorter(Microgame):
    VERB = "SHORTER!"
    INPUT = "stick+a"
    CAPTION = "Compilers find shorter circuits"

    def __init__(self, seed: int, level: int, duration: float) -> None:
        super().__init__(seed, level, duration)
        self.twist = level >= TWIST_FROM and self.rng.random() < 0.5
        if self.twist:
            pairs_side, other = self._twisted()
        else:
            pairs_side, other = self._plain(level)
        # the right answer is whichever is shorter once identical neighbours cancel
        self.short = self.rng.randrange(2)
        answer, decoy = (pairs_side, other) if self.twist else (other, pairs_side)
        self.circuits = [answer, decoy] if self.short == 0 else [decoy, answer]
        self.cursor = self.rng.randrange(2)
        self.moved_at = 0.0
        self.picked: int | None = None
        self.backdrop = P.BACKDROPS[self.rng.randrange(len(P.BACKDROPS))]

    def _plain(self, level: int):
        """(the circuit with pairs, the plain one): the pairs make it longer."""
        wires = 1 if level == 0 and self.rng.random() < 0.5 else 2
        if wires == 1:
            base, pairs = 1, 1
        else:
            base, pairs = (2, 3, 4, 5)[min(level, 3)], 2 if level < 2 else 1
        while True:  # split the gates over the wires so every wire fits
            split = [1] * wires
            for _ in range(base - wires):
                split[self.rng.randrange(wires)] += 1
            extra = [0] * wires
            for _ in range(pairs):
                extra[self.rng.randrange(wires)] += 1
            if all(b + 2 * p <= SLOTS for b, p in zip(split, extra)):
                break
        plain = [sequence(self.rng, n) for n in split]
        return [with_pairs(self.rng, w, p) for w, p in zip(plain, extra)], [[(k, False) for k in w] for w in plain]

    def _twisted(self):
        """(the circuit with pairs, the sandwiched one): the same gates
        underneath, two pairs on one side and one sandwich on the other, so
        the pairs side shows more gates (n + 4 > n + 2) but compiles to n."""
        while True:
            split = [self.rng.choice((1, 2)) for _ in range(2)]
            plain = [sequence(self.rng, n) for n in split]
            extra = [1, 1]
            sand_wire = self.rng.randrange(2)
            sand = [sandwiched(self.rng, w, 1 if i == sand_wire else 0) for i, w in enumerate(plain)]
            fits = all(len(w) + 2 * p <= SLOTS for w, p in zip(plain, extra))
            if fits and all(w is not None and len(w) <= SLOTS and no_pairs(w) for w in sand):
                break
        with_redundant = [with_pairs(self.rng, w, p) for w, p in zip(plain, extra)]
        return with_redundant, [[(k, False) for k in w] for w in sand]

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
        n = len(self.circuits[0])
        return [round(mid + (i - (n - 1) / 2) * WIRE_GAP) for i in range(n)]

    def draw(self, surf: pygame.Surface) -> None:
        backdrop(surf, self.backdrop, self.t)
        # "=" between the two: they do the same thing
        for y in (PANEL_Y + PANEL_H // 2 - 4, PANEL_Y + PANEL_H // 2 + 2):
            surf.fill(P.INK, (113, y - 1, 14, 4))
            surf.fill(P.WHITE, (114, y, 12, 2))
        blink = int(self.t * 6) % 2
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
            for y, wire in zip(self.wire_ys(), self.circuits[side]):
                blit_center(surf, outlined("|0>", 8, P.WHITE), (x + 15, y))
                surf.fill(P.INK, (x + 29, y - 2, PANEL_W - 33, 5))
                surf.fill(P.MIST, (x + 29, y - 1, PANEL_W - 33, 3))
                for i, (kind, redundant) in enumerate(wire):
                    r = pygame.Rect(0, 0, CARD, CARD)
                    r.center = (x + 39 + PITCH * i, y)
                    card(surf, r, P.GATE[kind])
                    blit_center(surf, outlined(kind, 8, P.WHITE, shadow=False), (r.centerx + 1, r.centery))
                    if redundant and self.result is not None and i and wire[i - 1][1] and blink:
                        pair = pygame.Rect(r.x - PITCH, r.y, CARD + PITCH, CARD).inflate(6, 6)
                        pygame.draw.rect(surf, P.GOLD, pair, 2, border_radius=5)
            if chosen and self.result is None:  # a bouncing arrow over the picked side
                cx, top = panel.centerx, PANEL_Y - 6 + round(2 * math.sin(self.t * 8))
                tri = [(cx - 6, top - 6), (cx + 6, top - 6), (cx, top)]
                pygame.draw.polygon(surf, P.INK, [(px, py + 1) for px, py in tri])
                pygame.draw.polygon(surf, P.GOLD, tri)
            if chosen and self.result is False:  # a red X over the wrong pick
                c = panel.center
                for d in ((-1, -1), (1, -1)):
                    a, b = (c[0] - 22 * d[0], c[1] - 22 * d[1]), (c[0] + 22 * d[0], c[1] + 22 * d[1])
                    pygame.draw.line(surf, P.INK, a, b, 9)
                    pygame.draw.line(surf, P.BAD, a, b, 5)
        blit_center(surf, outlined("A ON THE SHORTER ONE", 8, P.WHITE), (120, H - 14))
        result_overlay(surf, self.result, self.since_end, seed=11)
