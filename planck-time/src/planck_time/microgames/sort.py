"""SORT!: |0> and |1> tokens fall one at a time from the middle of the top.
Stick x slides the falling token left or right; the |0> bin is on the left,
the |1> bin on the right, and between them is a solid floor. Win once every
token is in its own bin; a token landing in the wrong bin, or on the floor,
fails.

Tokens spawn over the floor, so a token nobody steers always fails, and
doing nothing loses on the first one. There are always three tokens, and
the fall speed is set so all of them land within 90% of the play time,
which makes them fall faster at higher levels. Tokens drop from the very
top onto low bins, so there is a long fall to read the ket and steer.
"""

from __future__ import annotations

import pygame

from planck_time import palette as P
from planck_time.microgames.base import H, W, Microgame, PlayerInput, register
from planck_time.pixel import backdrop, blit_center, card, dither, outlined, result_overlay

KINDS = ("|0>", "|1>")
COLORS = (P.SKY, P.ORANGE)
BIN_TOP = 122
BIN_BOTTOM = 142
FLOOR = (80, 160)  # the solid stretch between the bins
TOKEN = (30, 20)
SPAWN_Y = 12  # a token's centre when it appears: right at the top, for a long fall
GAP = 0.12  # seconds between one token landing and the next appearing
BUDGET = 0.9  # of the play time, for all the tokens to land in
TOKENS = 3
SLIDE = 140  # px per second at full stick, level 0
TARGETS = (42, W - 42)  # each bin's middle


def bin_at(x: float) -> int | None:
    """The bin under a token's centre: 0, 1, or None for the floor."""
    return 0 if x < FLOOR[0] else 1 if x > FLOOR[1] else None


@register
class Sort(Microgame):
    VERB = "SORT!"
    INPUT = "stick"
    CAPTION = "Every measurement gives 0 or 1"

    def __init__(self, seed: int, level: int, duration: float) -> None:
        super().__init__(seed, level, duration)
        n = TOKENS
        self.kinds = [self.rng.randrange(2) for _ in range(n)]
        if len(set(self.kinds)) == 1:  # always some of each
            self.kinds[self.rng.randrange(n)] ^= 1
        self.starts = [W // 2 + self.rng.randint(-6, 6) for _ in range(n)]  # all over the floor
        drop = BIN_TOP - TOKEN[1] / 2 - SPAWN_Y
        self.v = drop / (BUDGET * duration / n - GAP)
        self.slide = SLIDE * self.speed
        self.i = 0
        self.x, self.y = float(self.starts[0]), float(SPAWN_Y)
        self.wait = 0.0
        self.landed: list[tuple[int, float]] = []  # (kind, x) of every sorted token
        self.missed: tuple[float, float] | None = None
        self.backdrop = P.BACKDROPS[self.rng.randrange(len(P.BACKDROPS))]

    def step(self, dt: float, inp: PlayerInput) -> None:
        if self.wait > 0:
            self.wait -= dt
            return
        half = TOKEN[0] / 2 + 1
        self.x = max(half, min(W - half, self.x + self.slide * inp.stick[0] * dt))
        self.y += self.v * dt
        if self.y + TOKEN[1] / 2 < BIN_TOP:
            return
        self.y = BIN_TOP - TOKEN[1] / 2
        kind = self.kinds[self.i]
        if bin_at(self.x) != kind:
            self.missed = (self.x, self.y)
            self.fail()
            return
        self.landed.append((kind, self.x))
        self.i += 1
        if self.i == len(self.kinds):
            self.win()
        else:
            self.x, self.y = float(self.starts[self.i]), float(SPAWN_Y)
            self.wait = GAP

    def bot(self) -> PlayerInput:
        if self.i >= len(self.kinds):
            return PlayerInput()
        d = TARGETS[self.kinds[self.i]] - self.x
        return PlayerInput(stick=(max(-1.0, min(1.0, d / 8)), 0.0))

    # --- drawing ----------------------------------------------------------------------

    def token(self, surf: pygame.Surface, kind: int, center, glow=None) -> None:
        r = pygame.Rect((0, 0), TOKEN)
        r.center = (round(center[0]), round(center[1]))
        if glow:
            pygame.draw.rect(surf, glow, r.inflate(6, 6), border_radius=6)
        card(surf, r, COLORS[kind])
        blit_center(surf, outlined(KINDS[kind], 8, P.WHITE), (r.centerx + 1, r.centery - 1))

    def draw(self, surf: pygame.Surface) -> None:
        backdrop(surf, self.backdrop, self.t)
        bins = [pygame.Rect(4, BIN_TOP, FLOOR[0] - 4, BIN_BOTTOM - BIN_TOP),
                pygame.Rect(FLOOR[1], BIN_TOP, W - 4 - FLOOR[1], BIN_BOTTOM - BIN_TOP)]
        for kind, rect in enumerate(bins):  # the backs of the bins
            surf.fill(P.INK, rect.inflate(2, 2))
            surf.fill(P.shade(COLORS[kind], 0.45), rect)

        # sorted tokens sit in their bins, stacked a little if they pile up
        count = [0, 0]
        for kind, x in self.landed:
            lo, hi = bins[kind].left + TOKEN[0] // 2 + 3, bins[kind].right - TOKEN[0] // 2 - 3
            done = self.result is True and self.since_end < 0.3 and (kind, x) == self.landed[-1]
            self.token(surf, kind, (max(lo, min(hi, x)), BIN_TOP + 4 - 5 * count[kind]),
                       glow=P.GOOD if done else None)
            count[kind] += 1

        for kind, rect in enumerate(bins):  # the fronts, with their labels
            front = pygame.Rect(rect.x, BIN_TOP + 7, rect.width, BIN_BOTTOM - BIN_TOP - 7)
            surf.fill(P.INK, front.inflate(2, 2))
            surf.fill(COLORS[kind], front)
            surf.fill(P.lighten(COLORS[kind], 0.5), (front.x, front.y, front.width, 1))
            surf.fill(P.shade(COLORS[kind], 0.7), (front.x, front.bottom - 3, front.width, 3))
            surf.fill(P.INK, (rect.x - 1, BIN_TOP - 1, 3, BIN_BOTTOM - BIN_TOP + 2))
            surf.fill(P.INK, (rect.right - 2, BIN_TOP - 1, 3, BIN_BOTTOM - BIN_TOP + 2))
            blit_center(surf, outlined(KINDS[kind], 8, P.WHITE), (front.centerx + 1, front.centery))

        # the floor between them: a solid block with hazard stripes on top
        floor = pygame.Rect(FLOOR[0], BIN_TOP, FLOOR[1] - FLOOR[0], BIN_BOTTOM - BIN_TOP)
        surf.fill(P.INK, floor.inflate(2, 2))
        dither(surf, floor, P.SLATE, P.NIGHT)
        surf.fill(P.GOLD, (floor.x, floor.y, floor.width, 4))
        for x in range(floor.x - 4, floor.right, 8):
            for dy in range(4):
                px = x + dy
                surf.fill(P.INK, (max(floor.x, px), floor.y + dy, max(0, min(4, floor.right - px)), 1))
        surf.fill(P.INK, (floor.x, floor.y + 4, floor.width, 1))

        # the tokens still to come, as little chips in the top-right corner
        for j, kind in enumerate(self.kinds[self.i + 1:]):
            surf.fill(P.INK, (W - 15 - 11 * j, 5, 10, 8))
            surf.fill(COLORS[kind], (W - 14 - 11 * j, 6, 8, 6))

        if self.missed:  # the one that fell wrong, with a red X on it
            mx, my = self.missed
            self.token(surf, self.kinds[self.i], (mx, my))
            for s in (1, -1):
                pygame.draw.line(surf, P.INK, (mx - 9, my - 9 * s), (mx + 9, my + 9 * s), 6)
                pygame.draw.line(surf, P.BAD, (mx - 8, my - 8 * s), (mx + 8, my + 8 * s), 3)
        elif self.result is None and self.wait <= 0:
            for y in range(round(self.y + TOKEN[1] / 2) + 4, BIN_TOP - 2, 6):  # where it'll land
                surf.fill(P.WHITE, (round(self.x), y, 1, 3))
            self.token(surf, self.kinds[self.i], (self.x, self.y), glow=P.WHITE)

        blit_center(surf, outlined("PUSH EACH INTO ITS BIN", 8, P.WHITE), (W // 2, H - 8))
        result_overlay(surf, self.result, self.since_end, seed=12)
