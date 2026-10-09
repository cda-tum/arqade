"""Cut the QUANTUMSPACE decal's letters out of a photo of the office's glass wall.

    cd brawl-ket && uv run python tools/make_decal.py PHOTO.jpg

Keeps the letters (UANTUM in charcoal, SPACE in blue): the Q, its tail, the orbit and the
TUM logo are drawn as clean shapes in stages.py, fitted to the same photo, because the
concrete and the lamp behind the glass get in the way there. Keeps only the two inks, drops everything
(concrete, the lamp, reflections), scales it down to the stage's size by coverage (so thin
gaps such as the lamp's reflection across the letters close up) and saves it, flat-coloured
on a transparent background, as src/brawl_ket/assets/quantum_space.png. The crop is for the
photo taken in October 2026 (1920x1080); a new photo needs a new CROP.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pygame

CROP = pygame.Rect(530, 270, 1060, 280)     # the decal, in the photo
WIDTH = 392                                 # px across in the game (a 100 px Q ring)
COVER = 0.25                                # how much of a game pixel must be ink
GAP = 9                                     # px: thinner light streaks across an ink are closed...
GAP_DOWN = 16                               # ... and down a column (the lamp's reflection)
LETTERS = pygame.Rect(225, 105, 835, 100)   # the band of letters, in the crop
LAMP = (136, 164)                           # rows the lamp's reflection (and its glow) crosses
MIN_BLOB = 30                               # game px: smaller dark blobs are concrete, not decal
CHARCOAL = (56, 56, 64)
TUM_BLUE = (48, 96, 176)
OUT = Path(__file__).parent.parent / "src" / "brawl_ket" / "assets" / "quantum_space.png"


def ink(c, x: int, y: int) -> str | None:
    r, g, b = c[:3]
    if b - r > 50 and b > 90 and LETTERS.collidepoint(x, y):
        return "blue"
    if LETTERS.collidepoint(x, y) and max(r, g, b) < 92 and max(r, g, b) - min(r, g, b) < 40:
        return "charcoal"
    return None


def close_gaps(g) -> None:
    """Fill runs of up to GAP non-ink pixels between ink, down each column and along each row:
    the lamp's reflection and the glass's frame cross the decal as thin light lines."""
    h, w = len(g), len(g[0])
    for x in range(w):
        last = None
        for y in range(h):
            if g[y][x]:
                if last is not None and 1 < y - last <= GAP_DOWN + 1:
                    for k in range(last + 1, y):
                        g[k][x] = True
                last = y
    for y in range(h):
        last = None
        for x in range(w):
            if g[y][x]:
                if last is not None and 1 < x - last <= GAP + 1:
                    for k in range(last + 1, x):
                        g[y][k] = True
                last = x


def bridge_lamp(g) -> None:
    """The lamp's reflection is a bright band across every letter: in each column, join the
    ink just above it to the ink just below it."""
    top, bottom = LAMP
    for x in range(len(g[0])):
        above = [y for y in range(top, (top + bottom) // 2) if g[y][x]]
        below = [y for y in range((top + bottom) // 2, bottom + 1) if g[y][x]]
        if above and below:
            for y in range(max(above), min(below)):
                g[y][x] = True


def drop_specks(out: pygame.Surface) -> None:
    """Clear every blob of ink smaller than MIN_BLOB pixels (8-connected)."""
    w, h = out.get_size()
    seen = set()
    for y in range(h):
        for x in range(w):
            if (x, y) in seen or out.get_at((x, y))[3] == 0:
                continue
            blob, todo = [], [(x, y)]
            seen.add((x, y))
            while todo:
                px, py = todo.pop()
                blob.append((px, py))
                for dx in (-1, 0, 1):
                    for dy in (-1, 0, 1):
                        q = (px + dx, py + dy)
                        if 0 <= q[0] < w and 0 <= q[1] < h and q not in seen and out.get_at(q)[3]:
                            seen.add(q)
                            todo.append(q)
            if len(blob) < MIN_BLOB:
                for p in blob:
                    out.set_at(p, (0, 0, 0, 0))


def main(photo: str) -> None:
    pygame.init()
    src = pygame.image.load(photo).subsurface(CROP)
    masks = {name: pygame.Surface(CROP.size) for name in ("charcoal", "blue")}
    for m in masks.values():
        m.fill((0, 0, 0))
    grid = {name: [[False] * CROP.w for _ in range(CROP.h)] for name in masks}
    for y in range(CROP.h):
        for x in range(CROP.w):
            kind = ink(src.get_at((x, y)), x, y)
            if kind:
                grid[kind][y][x] = True
    for kind, g in grid.items():
        bridge_lamp(g)
        close_gaps(g)
        for y in range(CROP.h):
            for x in range(CROP.w):
                if g[y][x]:
                    masks[kind].set_at((x, y), (255, 255, 255))
    size = (WIDTH, round(CROP.h * WIDTH / CROP.w))
    out = pygame.Surface(size, pygame.SRCALPHA)
    out.fill((0, 0, 0, 0))
    for kind, colour in (("charcoal", CHARCOAL), ("blue", TUM_BLUE)):
        small = pygame.transform.smoothscale(masks[kind], size)
        for y in range(size[1]):
            for x in range(size[0]):
                if small.get_at((x, y))[0] >= 255 * COVER:
                    out.set_at((x, y), colour)
    drop_specks(out)
    pygame.image.save(out, OUT)
    print(f"saved {OUT} ({size[0]}x{size[1]})")


if __name__ == "__main__":
    main(sys.argv[1])
