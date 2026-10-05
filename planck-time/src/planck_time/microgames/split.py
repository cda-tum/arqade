"""SPLIT! (from Qurves): your light cycle races right, towards a wall of the rival's
trail. An H gate sits straight ahead: drive over it and you split into two mirrored
copies, as in Qurves: one follows the stick, the other the stick mirrored across the
line it split on. You lose only when every copy has crashed.

The wall has two spots that might be open, one above and one below, drawn as
flickering ghost trail. Which one stays open is decided only when your bike is a few
cells from the wall, far too late for one bike to change sides: like a measurement
in Qurves, it collapses at the last moment. With the H, one copy is on each side,
and one always gets through. Without it you could only guess. Doing nothing drives
both copies into the wall's solid middle.
"""

from __future__ import annotations

import pygame

from planck_time import palette as P
from planck_time.microgames.base import H, W, Microgame, PlayerInput, register
from planck_time.pixel import blit_center, font, outlined, result_overlay

CELL = 6
COLS = W // CELL                # 40
ROWS = 24
TOP = 4                         # the arena's top edge, px
MID = ROWS // 2                 # your row
START_X = 2
H_X = 8                         # the H gate's column, on your row
WALL_X = 26                     # the rival's wall
OFFSET = 6                      # the two maybe-open spots: MID - OFFSET and MID + OFFSET
REVEAL_X = WALL_X - 4           # the spot collapses once a copy gets this close
TICK = 0.1                      # seconds per cell at level 0


def q(c) -> tuple[int, int, int]:
    """A Qurves colour snapped onto the GBA's 15-bit grid."""
    return tuple(min(248, round(v / 8) * 8) for v in c)


BACKGROUND = q((5, 6, 14))
GRID = q((17, 21, 42))
WALL = q((110, 120, 200))
YOU = q((60, 230, 110))         # Qurves' green bike (P3): no blue-against-red in one game
RIVAL = q((190, 90, 255))       # Qurves' purple bike (P4)
H_COLOR = q((235, 240, 255))    # Qurves' GATE_COLORS["H"]


class Copy:
    def __init__(self, x: int, y: int, mirror: bool, trail: list[tuple[int, int]]) -> None:
        self.x, self.y = x, y
        self.dir = (1, 0)
        self.mirror = mirror        # follows the stick mirrored across the split line
        self.alive = True
        self.trail = list(trail)


def cell_px(c) -> tuple[int, int]:
    return c[0] * CELL + CELL // 2, TOP + c[1] * CELL + CELL // 2


@register
class Split(Microgame):
    VERB = "SPLIT!"
    INPUT = "stick"
    CAPTION = "You lose only when every copy crashes"

    def __init__(self, seed: int, level: int, duration: float) -> None:
        super().__init__(seed, level, duration)
        self.open_row = MID + self.rng.choice((-1, 1)) * OFFSET   # decided now, revealed late
        self.revealed = False
        self.reveal_at = 0.0
        self.h_live = True
        self.split_at: float | None = None
        self.copies = [Copy(START_X, MID, False, [(START_X - 1, MID), (START_X, MID)])]
        self.tick = TICK / self.speed
        self.next_tick = self.tick
        self.want = (1, 0)

    # --- the rules -----------------------------------------------------------------------

    def wall(self, row: int) -> bool:
        """Is the wall solid at this row? Before the collapse both spots are open."""
        spots = (MID - OFFSET, MID + OFFSET)
        if row not in spots:
            return True
        return self.revealed and row != self.open_row

    def step(self, dt: float, inp: PlayerInput) -> None:
        sx, sy = inp.stick
        if abs(sy) > 0.5 and abs(sy) >= abs(sx):
            self.want = (0, 1 if sy > 0 else -1)
        elif sx > 0.5:
            self.want = (1, 0)
        while self.t + dt >= self.next_tick and self.result is None:
            self.next_tick += self.tick
            self._advance()

    def _advance(self) -> None:
        for c in self.copies:
            if not c.alive:
                continue
            want = (self.want[0], -self.want[1]) if c.mirror else self.want
            if want != (-c.dir[0], -c.dir[1]):  # no reversing into yourself
                c.dir = want
            c.x += c.dir[0]
            c.y += c.dir[1]
            c.trail.append((c.x, c.y))
            if not (0 <= c.x < COLS and 0 <= c.y < ROWS) or (c.x == WALL_X and self.wall(c.y)):
                c.alive = False
            elif c.x > WALL_X:
                self.win()
                return
        lead = max((c.x for c in self.copies if c.alive), default=0)
        if not self.revealed and lead >= REVEAL_X:
            self.revealed = True
            self.reveal_at = self.t
            for c in self.copies:       # a copy sitting in the closed spot crashes with it
                if c.alive and c.x == WALL_X and self.wall(c.y):
                    c.alive = False
        first = self.copies[0]
        if self.h_live and self.split_at is None and first.alive and (first.x, first.y) == (H_X, MID):
            self.split_at = self.t
            self.copies.append(Copy(first.x, first.y, True, first.trail))
        if not any(c.alive for c in self.copies):
            self.fail()

    def steer_policy(self, side: int) -> PlayerInput:
        """Drive straight over the H, then steer the stick's copy to the spot on `side`
        (-1 above, 1 below), then on to the wall. The mirrored copy goes the other way."""
        lead = self.copies[0]
        if lead.x < H_X:
            return PlayerInput(stick=(1.0, 0.0))
        target = MID + side * OFFSET
        if lead.y != target:
            return PlayerInput(stick=(0.0, 1.0 if target > lead.y else -1.0))
        return PlayerInput(stick=(1.0, 0.0))

    def bot(self) -> PlayerInput:
        return self.steer_policy(-1)

    # --- drawing -------------------------------------------------------------------------

    def draw(self, surf: pygame.Surface) -> None:
        surf.fill(BACKGROUND)
        arena = pygame.Rect(0, TOP, COLS * CELL, ROWS * CELL)
        for x in range(0, arena.w, CELL):
            surf.fill(GRID, (x, arena.y, 1, arena.h))
        for y in range(arena.y, arena.bottom, CELL):
            surf.fill(GRID, (0, y, arena.w, 1))
        pygame.draw.rect(surf, WALL, arena.inflate(2, 2), 1)
        # the rival's wall, and its two maybe-open spots
        wx = WALL_X * CELL
        flicker = int(self.t * 12) % 2
        for row in range(ROWS):
            y = TOP + row * CELL
            if self.wall(row):
                just = self.revealed and row in (MID - OFFSET, MID + OFFSET) and self.t - self.reveal_at < 0.3
                surf.fill(P.WHITE if just and flicker else RIVAL, (wx + 1, y, CELL - 2, CELL))
                surf.fill(P.lighten(RIVAL, 0.5), (wx + 2, y, 1, CELL))
            elif not self.revealed and flicker:     # ghost trail: open or not, nobody knows yet
                for yy in range(y, y + CELL, 2):
                    surf.fill(P.shade(RIVAL, 0.7), (wx + 1, yy, CELL - 2, 1))
        if not self.revealed:
            for row in (MID - OFFSET, MID + OFFSET):
                blit_center(surf, outlined("?", 8, P.lighten(RIVAL, 0.5)), (wx + CELL // 2 + 8, TOP + row * CELL + 3))
        # the H gate, until it is driven over
        if self.h_live and self.split_at is None:
            gx, gy = cell_px((H_X, MID))
            rect = pygame.Rect(0, 0, 13, 13)
            rect.center = (gx, gy)
            pygame.draw.rect(surf, H_COLOR, rect, 1, border_radius=2)
            label = font(8).render("H", False, H_COLOR)
            surf.blit(label, label.get_rect(center=(gx + 1, gy + 1)))
        # the trails: the stick's copy solid, the mirrored one as ghost trail, as in Qurves
        for c in self.copies:
            colour = YOU if c.alive else P.shade(YOU, 0.45)
            for i, (a, b) in enumerate(zip(c.trail, c.trail[1:])):
                if c.mirror and i % 2:
                    continue
                pygame.draw.line(surf, colour, cell_px(a), cell_px(b), 2)
            hx, hy = cell_px((c.x, c.y))
            if c.alive:
                pygame.draw.circle(surf, P.lighten(YOU, 0.4), (hx, hy), 4)
                pygame.draw.circle(surf, P.WHITE, (hx, hy), 2)
            else:
                for d in (-1, 1):
                    pygame.draw.line(surf, P.BAD, (hx - 3, hy - 3 * d), (hx + 3, hy + 3 * d), 2)
        if self.result is True:
            hint = "ONE COPY MADE IT!"
        elif self.result is False:
            hint = "EVERY COPY CRASHED"
        elif self.split_at is None:
            hint = "DRIVE OVER THE H"
        else:
            hint = "STEER: ONE COPY GETS THROUGH"
        blit_center(surf, outlined(hint, 8, P.WHITE), (W // 2, H - 9))
        result_overlay(surf, self.result, self.since_end, seed=41)
