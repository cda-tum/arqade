"""DROP! (from Gate Drop): a gate pill hangs over a small Gate Drop well, a
few qubit wires wide, with gates already stacked on each wire. Slide the
pill with the stick to the wire whose top gate is its inverse and it lands
there: the pair cancels with Gate Drop's pop. A drops it fast. It lands by
itself as well, so it must be over the right wire by then.

Gate Drop's own gates and inverses: H, X, Y and Z are each their own, and T
undoes T-dagger. Exactly one wire's top gate is the inverse, and the pill
never starts over it. From the second appearance on, the pill can be a T or
a T-dagger, and a wire topped with the same T is the decoy: T T is an S
gate, not the identity, so it doesn't cancel.

The stacks are built as Gate Drop would leave them: nothing in them cancels
already (no gate on its inverse, no H X H or H Z H sandwich), and no wrong
wire makes a sandwich with the pill either. The pill can't slide into a
stack, as in Gate Drop, but it starts high enough to reach every wire.
"""

from __future__ import annotations

import math
import random

import pygame

from planck_time import palette as P
from planck_time.microgames.base import IDLE, H, W, Microgame, PlayerInput, register
from planck_time.pixel import blit_center, font, outlined, result_overlay

INVERSE = {"H": "H", "X": "X", "Y": "Y", "Z": "Z", "T": "Td", "Td": "T"}  # Gate Drop's config.INVERSE
CLIFFORD = ("H", "X", "Y", "Z")
PAULIS = ("X", "Y", "Z")  # what an error bug can be
T_FROM = 1  # the appearance from which the pill can be a T or a T-dagger

ROWS = 7
CELL = 16
TOP = 12  # the well's top edge
WELL_CX = 92  # the well's centre; the PAIRS panel is to its right
PANEL = pygame.Rect(162, TOP - 4, 70, 128)
READY = 0.6  # the pill hangs at the top this long before it falls (level 0); input counts after
FALL = 0.6  # seconds per row at level 0, as Gate Drop's LOW speed
FAST = 0.035  # seconds per row once A drops it
POP = 0.35  # Gate Drop's CLEAR_TIME: the pair flashes, then bursts
THINK = 0.3  # the bot looks before it moves...
BOT_STEP = 0.12  # ...steps a wire this often...
BOT_SETTLE = 0.1  # ...and checks once more before pressing A


def q(c) -> tuple[int, int, int]:
    """A Gate Drop colour snapped onto the GBA's 15-bit grid."""
    return tuple(min(248, round(v / 8) * 8) for v in c)


INK = q((24, 18, 40))
WHITE = (248, 248, 248)
COLORS = {k: q(c) for k, c in {
    "H": (250, 196, 40), "X": (232, 64, 72), "Y": (170, 82, 220), "Z": (56, 124, 236),
    "T": (52, 190, 108), "Td": (240, 132, 40)}.items()}
WELL = q((18, 22, 46))
WIRE = q((44, 54, 96))
FRAME = q((170, 182, 204))  # the steel of Gate Drop's CNOT pills: no player's colour
BACKGROUNDS = tuple((q(a), q(b)) for a, b in (
    ((40, 44, 120), (54, 60, 152)), ((92, 40, 110), (116, 54, 140)),
    ((22, 92, 96), (30, 116, 120)), ((110, 62, 30), (138, 82, 42))))


def sandwich(below2: str | None, below: str | None, kind: str) -> bool:
    """H X H or H Z H: Gate Drop folds these into one gate."""
    return below2 == "H" and below in ("X", "Z") and kind == "H"


def stable(column: list[str], kind: str) -> bool:
    """Can `kind` sit on top of `column` (bottom first) without anything cancelling?"""
    below = column[-1] if column else None
    below2 = column[-2] if len(column) > 1 else None
    return below is None or (INVERSE[below] != kind and not sandwich(below2, below, kind))


# --- the round ---------------------------------------------------------------------------

def build(rng: random.Random, n: int, t_round: bool, use_t: bool, max_h: int):
    """(pill, right wire, the wires' gates bottom first, which bottoms are bugs)."""
    kinds = CLIFFORD + (("T", "Td") if use_t else ())
    while True:
        pill = rng.choice(("T", "Td")) if t_round else rng.choice(CLIFFORD)
        right = rng.randrange(n)
        tops = {right: INVERSE[pill]}
        wrong = [k for k in kinds if k != INVERSE[pill]]
        rng.shuffle(wrong)
        if t_round:  # the decoy: the same T, which looks like a match and isn't
            wrong.remove(pill)
            wrong.insert(0, pill)
        others = [c for c in range(n) if c != right]
        rng.shuffle(others)
        for i, c in enumerate(others):
            tops[c] = wrong[i % len(wrong)]
        columns, bugs = [], []
        for c in range(n):
            col = build_column(rng, rng.randint(1, max_h), tops[c])
            if col is None:
                break
            columns.append(col)
            bugs.append(rng.random() < 0.6 and len(col) > 1 and col[0] in PAULIS)
        else:
            if all(c == right or not sandwich(col[-2] if len(col) > 1 else None, col[-1], pill)
                   for c, col in enumerate(columns)):
                return pill, right, columns, bugs


def build_column(rng: random.Random, height: int, top: str):
    """A stable stack of `height` gates ending in `top`, or None."""
    for _ in range(50):
        col: list[str] = []
        for _ in range(height - 1):
            options = [k for k in CLIFFORD if stable(col, k)]
            col.append(rng.choice(options))
        if stable(col, top):
            return col + [top]
    return None


# --- Gate Drop's sprites (sprites.py), redrawn small ---------------------------------------

_CACHE: dict = {}


def capsule(kind: str) -> pygame.Surface:
    """A loose gate half: an ink outline, a fill shading darker at the bottom, a glint, the letter."""
    key = ("gate", kind)
    if key not in _CACHE:
        color = COLORS[kind]
        s = pygame.Surface((CELL, CELL), pygame.SRCALPHA)
        pygame.draw.rect(s, INK, (0, 0, CELL, CELL), border_radius=7)
        inner = pygame.Rect(1, 1, CELL - 2, CELL - 2)
        pygame.draw.rect(s, P.shade(color, 0.7), inner, border_radius=6)
        top = inner.copy()
        top.height -= 3
        pygame.draw.rect(s, color, top, border_radius=6)
        glint = P.lighten(color, 0.6)
        s.fill(glint, (3, 3, 3, 1))
        s.fill(glint, (3, 4, 1, 2))
        f = font(8)
        if kind == "Td":  # T-dagger: the font has no dagger, so draw one
            letter(s, f, "T", (CELL // 2 - 1, CELL // 2))
            for x, y, w, h in ((12, 2, 1, 7), (11, 4, 3, 1)):
                s.fill(INK, (x + 1, y + 1, w, h))
                s.fill(WHITE, (x, y, w, h))
        else:
            letter(s, f, kind, (CELL // 2 + 1, CELL // 2))
        _CACHE[key] = s
    return _CACHE[key]


def letter(s: pygame.Surface, f, text: str, centre) -> None:
    img = f.render(text, False, WHITE)
    rect = img.get_rect(center=centre)
    s.blit(f.render(text, False, INK), rect.move(1, 1))
    s.blit(img, rect)


def bug(kind: str, frame: int) -> pygame.Surface:
    """A grumpy Pauli-error bug: angry eyes, shuffling legs, its letter in ink on its back."""
    key = ("bug", kind, frame)
    if key not in _CACHE:
        color = COLORS[kind]
        leg = P.shade(color, 0.55)
        s = pygame.Surface((CELL, CELL), pygame.SRCALPHA)
        bob = frame
        for i, ly in enumerate((8, 11, 14)):
            st = (i + frame) % 2
            s.fill(leg, (0, ly - st, 2, 1))
            s.fill(leg, (CELL - 2, ly - 1 + st, 2, 1))
        body = pygame.Rect(1, 4 + bob, 14, 12 - bob)
        pygame.draw.ellipse(s, INK, body)
        pygame.draw.ellipse(s, P.shade(color, 0.75), body.inflate(-2, -2))
        back = body.inflate(-2, -4)
        back.y = body.y + 1
        pygame.draw.ellipse(s, P.lighten(color, 0.15), back)
        for ex in (5, 10):
            pygame.draw.circle(s, INK, (ex, 3 + bob), 3)
            pygame.draw.circle(s, WHITE, (ex, 3 + bob), 2)
            s.fill(INK, (ex + (1 if ex < 8 else -1), 3 + bob, 1, 2))
        s.fill(INK, (3, bob, 3, 1))
        s.fill(INK, (10, bob, 3, 1))
        img = font(8).render(kind, False, INK)
        s.blit(img, img.get_rect(center=(CELL // 2 + 1, 10 + bob)))
        _CACHE[key] = s
    return _CACHE[key]


_GLYPH_Q = (".###.", "#..#.", "#..#.", ".###.", "...#.", "...##")
_GLYPH_DIGITS = (
    ("###", "#.#", "#.#", "#.#", "###"), (".#.", "##.", ".#.", ".#.", "###"),
    ("###", "..#", "###", "#..", "###"), ("###", "..#", "###", "..#", "###"),
    ("#.#", "#.#", "###", "..#", "..#"), ("###", "#..", "###", "..#", "###"),
)
_GLYPH_KET = ("#..", ".#.", ".#.", "..#", ".#.", ".#.", "#..")


def ket(wire: int, color) -> pygame.Surface:
    """|q_n>, the label under wire n, in pixels to fit one 16 px column."""
    key = ("ket", wire, color)
    if key not in _CACHE:
        s = pygame.Surface((CELL, 7), pygame.SRCALPHA)
        parts = ((0, 0, ("#",) * 7), (2, 1, _GLYPH_Q), (8, 2, _GLYPH_DIGITS[wire]), (12, 0, _GLYPH_KET))
        for left, top, rows in parts:
            for y, row in enumerate(rows):
                for x, bit in enumerate(row):
                    if bit == "#":
                        s.fill(color, (left + x, top + y, 1, 1))
        _CACHE[key] = s
    return _CACHE[key]


def tiles(colors) -> pygame.Surface:
    """Gate Drop's two-tone diamond tiles, one tile larger than the screen to scroll."""
    key = ("bg", colors)
    if key not in _CACHE:
        a, b = colors
        s = pygame.Surface((W + 32, H + 32))
        s.fill(a)
        for ty in range(0, H + 32, 32):
            for tx in range(0, W + 32, 32):
                pygame.draw.polygon(s, b, [(tx + 16, ty + 3), (tx + 29, ty + 16), (tx + 16, ty + 29), (tx + 3, ty + 16)])
                s.fill(P.lighten(b, 0.25), (tx + 15, ty + 15, 2, 2))
        _CACHE[key] = s
    return _CACHE[key]


@register
class Drop(Microgame):
    VERB = "DROP!"
    INPUT = "stick+a"
    CAPTION = "A gate next to its inverse vanishes"

    def __init__(self, seed: int, level: int, duration: float) -> None:
        super().__init__(seed, level, duration)
        self.n = min(6, 4 + level // 2)  # wires
        use_t = self.appearance >= T_FROM
        self.t_round = use_t and self.rng.random() < 0.5
        self.pill, self.right, self.columns, self.bugs = build(
            self.rng, self.n, self.t_round, use_t, max_h=3 if level < 3 else 4)
        self.col = self.rng.choice([c for c in range(self.n) if c != self.right])
        self.row = 0
        self.ready = READY / self.speed
        self.fall = FALL / self.speed
        self.next_fall = self.ready + self.fall
        self.fast = False
        self.moved_at = 0.0
        self.landed_on: int | None = None
        self.backdrop = BACKGROUNDS[self.rng.randrange(len(BACKGROUNDS))]
        self.origin = (WELL_CX - self.n * CELL // 2, TOP)
        self.pairs = CLIFFORD + (("T",) if use_t else ())

    # --- the rules -----------------------------------------------------------------------

    def floor(self, col: int) -> int:
        """The row the pill lands in on wire `col`: just above its stack."""
        return ROWS - len(self.columns[col]) - 1

    def step(self, dt: float, inp: PlayerInput) -> None:
        if self.t < self.ready:
            return
        if inp.step[0] and not self.fast:
            to = self.col + inp.step[0]
            if 0 <= to < self.n and self.row <= self.floor(to):  # it can't slide into a stack
                self.col = to
                self.moved_at = self.t
        if inp.a and not self.fast:
            self.fast = True
            self.next_fall = min(self.next_fall, self.t + FAST)
        while self.t + dt >= self.next_fall and self.result is None:
            if self.row >= self.floor(self.col):
                self.land()
            else:
                self.row += 1
                self.next_fall += FAST if self.fast else self.fall

    def land(self) -> None:
        self.landed_on = self.col
        if self.columns[self.col][-1] == INVERSE[self.pill]:
            self.win()
        else:
            self.fail()

    def bot(self) -> PlayerInput:
        if self.t < self.ready + THINK:
            return IDLE
        since = self.t - self.moved_at
        if self.col != self.right:
            return PlayerInput(step=(1 if self.right > self.col else -1, 0)) if since >= BOT_STEP else IDLE
        return PlayerInput(a=True, a_held=True) if since >= BOT_SETTLE else IDLE

    # --- drawing -------------------------------------------------------------------------

    def cell(self, col: int, row: int) -> tuple[int, int]:
        return self.origin[0] + col * CELL, self.origin[1] + row * CELL

    def draw(self, surf: pygame.Surface) -> None:
        off = int(self.t * 8) % 32
        surf.blit(tiles(self.backdrop), (-off, -off))
        ox, oy = self.origin
        well = pygame.Rect(ox, oy, self.n * CELL, ROWS * CELL)
        plate = 8

        def framed(grow: int) -> pygame.Rect:  # the frame runs on round the label plate
            r = well.inflate(grow, grow)
            r.height += plate
            return r

        pygame.draw.rect(surf, INK, framed(16), border_radius=5)
        pygame.draw.rect(surf, P.shade(FRAME, 0.6), framed(12), border_radius=4)
        pygame.draw.rect(surf, FRAME, framed(10), border_radius=4)
        pygame.draw.rect(surf, P.lighten(FRAME, 0.5), framed(10), 1, border_radius=4)
        surf.fill(INK, well.inflate(2, 2))
        surf.fill(WELL, well)
        surf.fill(INK, (well.x, well.bottom + 1, well.w, plate + 1))
        for c in range(self.n):
            surf.fill(WIRE, (ox + c * CELL + CELL // 2 - 1, oy, 2, well.h))
            surf.blit(ket(c, P.lighten(FRAME, 0.7)), (ox + c * CELL, well.bottom + 2))

        won = self.result is True
        popping = won and self.since_end < POP
        flash = popping and int(self.t * 20) % 2 == 0
        frame = int(self.t * 3) % 2
        for c, col in enumerate(self.columns):
            for i, kind in enumerate(col):
                top = i == len(col) - 1
                if won and c == self.landed_on and top and not popping:
                    continue  # cancelled
                x, y = self.cell(c, ROWS - 1 - i)
                surf.blit(bug(kind, frame) if i == 0 and self.bugs[c] else capsule(kind), (x, y))
                if flash and c == self.landed_on and top:
                    surf.fill(WHITE, (x + 2, y + 2, CELL - 4, CELL - 4))
        if not (won and not popping):
            x, y = self.cell(self.col, self.row)
            squish = 1 if self.result is not None and self.since_end < 0.1 else 0
            surf.blit(capsule(self.pill), (x, y + squish))
            if flash:
                surf.fill(WHITE, (x + 2, y + 2, CELL - 4, CELL - 4))
        if won and not popping:
            self._stars(surf)
        self._panel(surf)
        if self.result is False and self.landed_on is not None:
            below = self.columns[self.landed_on][-1]
            hint = "T T IS S: NO CANCEL!" if below == self.pill else "THOSE DON'T CANCEL!"
        elif self.result is True:
            hint = "CANCELLED!"
        elif self.t_round:
            hint = "T CANCELS ONLY T-DAGGER"
        else:
            hint = "DROP IT ON THE SAME GATE"
        blit_center(surf, outlined(hint, 8, WHITE), (W // 2, H - 9))
        result_overlay(surf, self.result, self.since_end, seed=17)

    def _panel(self, surf: pygame.Surface) -> None:
        """A Gate Drop HUD panel with its rule card: each gate over its inverse."""
        pygame.draw.rect(surf, INK, PANEL, border_radius=5)
        pygame.draw.rect(surf, P.shade(FRAME, 0.55), PANEL, 1, border_radius=5)
        blit_center(surf, outlined("PAIRS", 8, WHITE, shadow=False), (PANEL.centerx, PANEL.y + 10))
        cols = 2 if len(self.pairs) <= 4 else 3
        pitch = PANEL.w // cols
        for i, kind in enumerate(self.pairs):
            r, c = divmod(i, cols)
            x = PANEL.x + pitch * c + (pitch - CELL) // 2
            y = PANEL.y + 22 + r * 50
            surf.fill(WIRE, (x + CELL // 2 - 1, y - 2, 2, 2 * CELL + 4))
            surf.blit(capsule(INVERSE[kind]), (x, y))
            surf.blit(capsule(kind), (x, y + CELL))
            blit_center(surf, outlined("=I", 8, P.MIST, shadow=False), (x + CELL // 2 + 1, y + 2 * CELL + 9))

    def _stars(self, surf: pygame.Surface) -> None:
        """Gate Drop's clear: star bursts flying out of the two cells, falling."""
        k = self.since_end - POP
        if k > 0.6:
            return
        rng = random.Random(self.right * 7 + self.n)
        for row in (self.row, self.row + 1):
            x0, y0 = self.cell(self.landed_on, row)
            for _ in range(6):
                a = rng.uniform(0, 2 * math.pi)
                v = rng.uniform(40, 110)
                x = x0 + 8 + math.cos(a) * v * k
                y = y0 + 8 + (math.sin(a) * v - 60) * k + 130 * k * k
                color = rng.choice((WHITE, COLORS["H"], P.lighten(FRAME, 0.5)))
                size = 2 if k < 0.35 else 1
                surf.fill(color, (round(x), round(y), size, size))
