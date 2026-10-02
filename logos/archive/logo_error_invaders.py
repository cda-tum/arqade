"""Pauli Invaders key art: the formation marching at the viewer, a boss above.

The Clifford Core boss looms at the top, its hexagon shield half behind the
title, spraying the orb spiral it fires in the game. Below the title an
invader formation comes forward in perspective (small rows at the back, big
ones at the front), and the two ships fire back: P1's colour-code triangle
on the left in blue, P2's surface patch on the right in red -- each shot
bursting on an invader of its own colour, while a purple Y error, hit by
blue, flashes white as it converts. The Cosmic Ray's wave packet, two boss
minions, power-up capsules and the formation's zigzag shots fill the edges.
The marquee is the title on one line between a red and a blue invader.

Built from the game's own pieces: SPR, COL, SPECIAL, BG, CAP_INFO,
YELLOW, triangle_sprite(), patch_sprite(), glow() and fade() come from
error_invaders.game, the Clifford Core's proportions from bosses.py
(CORE_R, SHIELD_R). The invaders and the boss are redrawn here at the
art's scale (see invader() and clifford()) because the game draws them at a
fixed 3.6 px per sprite pixel, and the title uses the game's own colours:
PAULI in X red, INVADERS in Z blue, like draw_title().
"""

from __future__ import annotations

import math
import random
import sys

import kit
import pygame

sys.path.insert(0, str(kit.ROOT / "error-invaders/src"))
from error_invaders import bosses  # noqa: E402
from error_invaders import game as G  # noqa: E402

ROM = "error_invaders"

BG = G.BG
COL = G.COL
WHITE = G.WHITE

# Wordmark fills: a light top, the game colour, a deep base.
FILL = {
    "X": [(255, 196, 202), (255, 77, 94), (176, 24, 52)],
    "Z": [(196, 232, 255), (63, 169, 255), (22, 78, 186)],
}
GLOW_R = 30   # the title's halo


# --- sprites, redrawn at any scale -------------------------------------------


def invader(col: str, px: int, frame: int = 0, flash: bool = False, letter: bool = True) -> pygame.Surface:
    """game.enemy_sprite() at `px` screen pixels per sprite pixel (the game
    uses 3.6), with its Pauli letter in the bundled pixel font."""
    rows = G.SPR[frame]
    s = pygame.Surface((10 * px, 8 * px), pygame.SRCALPHA)
    c = WHITE if flash else COL[col]
    for r, row in enumerate(rows):
        for cc, ch in enumerate(row):
            if ch == "#":
                s.fill(c, (cc * px, r * px, px, px))
    if letter:
        add_letter(s, col, px)
    return s


def add_letter(s: pygame.Surface, col: str, px: int, offset: tuple[int, int] = (0, 0)) -> None:
    """The Pauli letter on an invader, sized and placed like enemy_sprite()
    does it (font(12) on a 3.6 px grid, centred 2 px above the 4th row)."""
    k = max(1, round(px * 12 / 3.6 / 8))
    glyph = kit.tint(kit.text_shape(col, kit.PIXEL_FONT, 8 * k), BG)
    s.blit(glyph, glyph.get_rect(center=(offset[0] + 5 * px, offset[1] + round(4 * px - 2 * px / 3.6))))


def clifford(S: pygame.Surface, x: float, y: float, k: float, t: float) -> None:
    """bosses.Clifford.draw() scaled by `k`: glow, rotating hexagon shield,
    core with its inner ring, four spokes and the 'C'."""
    core_r, shield_r = bosses.CORE_R * k, bosses.SHIELD_R * k
    core = COL["Y"]   # Clifford.draw(): the core flashes in the colour it just fired
    S.blit(kit.radial(S.get_size(), (x, y), shield_r * 2.4, (120, 130, 190), 0.55), (0, 0),
           special_flags=pygame.BLEND_ADD)
    hexa = [(x + shield_r * math.cos(t * 0.6 + i * math.pi / 3), y + shield_r * math.sin(t * 0.6 + i * math.pi / 3))
            for i in range(6)]
    halo = pygame.Surface(S.get_size(), pygame.SRCALPHA)
    pygame.draw.polygon(halo, (170, 200, 255), hexa, round(3 * k))
    S.blit(kit.glow(halo, (120, 160, 255), 24, 0.9), (0, 0))
    S.blit(halo, (0, 0))
    pygame.draw.circle(S, core, (x, y), core_r)
    pygame.draw.circle(S, BG, (x, y), core_r - 8 * k, round(2 * k))
    for i in range(4):
        a = -t * 2 + i * math.pi / 2
        pygame.draw.line(S, BG, (x, y), (x + (core_r - 10 * k) * math.cos(a), y + (core_r - 10 * k) * math.sin(a)),
                         round(3 * k))
    # a hub behind the 'C' so it doesn't merge with the spokes at this size
    pygame.draw.circle(S, core, (x, y), core_r * 0.36)
    c = kit.tint(kit.text_shape("C", kit.PIXEL_FONT, 8 * round(16 * k / 8)), BG)
    kit.blit_center(S, c, (x + k, y + k))


def orb(S: pygame.Surface, x: float, y: float, k: float) -> None:
    """A boss orb bullet (game.draw_game: light disc, BG centre)."""
    pygame.draw.circle(S, (225, 225, 235), (x, y), 5 * k)
    pygame.draw.circle(S, BG, (x, y), 2 * k)


def colour_orb(S: pygame.Surface, x: float, y: float, col: str, k: float) -> None:
    """The Clifford Core's coloured shot: glow, colour disc, white centre."""
    G.glow(S, x, y, 18 * k, COL[col], 0.6)
    pygame.draw.circle(S, COL[col], (x, y), 8 * k)
    pygame.draw.circle(S, WHITE, (x, y), 3 * k)


def bolt(S: pygame.Surface, x: float, y: float, col: tuple, k: float, length: float = 1.0) -> None:
    """A player shot (a 4x16 bar with a small glow), plus a motion trail."""
    w, h = 4 * k, 16 * k * length
    for i in range(5):   # additive, so it never darkens what it crosses
        S.fill(kit.shade(col, 0.55 * 0.7 ** i), (x - w / 2, y + h / 2 + i * h * 0.5, w, h * 0.5),
               special_flags=pygame.BLEND_ADD)
    G.glow(S, x, y, 14 * k, col, 0.55)
    S.fill(col, (x - w / 2, y - h / 2, w, h))
    S.fill(kit.lerp(col, WHITE, 0.6), (x - w / 4, y - h / 2, w / 2, h))


def zigzag(S: pygame.Surface, x: float, y: float, k: float) -> None:
    """The formation's colourless zigzag shot."""
    for i in range(4):
        S.fill((232, 232, 232), (x - 3 * k + (i % 2) * 3 * k, y - 8 * k + i * 4 * k, 3 * k, 4 * k))


def burst(S: pygame.Surface, x: float, y: float, col: tuple, n: int, spread: float, k: float,
          rng: random.Random) -> None:
    """game.burst() frozen mid-flight: square particles fading outwards."""
    G.glow(S, x, y, spread * 0.9, col, 0.55)
    for _ in range(n):
        a = rng.uniform(0, 2 * math.pi)
        d = spread * rng.random() ** 0.6
        f = 1 - 0.6 * d / spread
        s = max(2, round(4 * k * f))
        S.fill(G.fade(col, f), (x + math.cos(a) * d - s / 2, y + math.sin(a) * d - s / 2, s, s))
    G.glow(S, x, y, spread * 0.35, WHITE, 0.5)


def capsule(S: pygame.Surface, x: float, y: float, kind: str, k: float) -> None:
    """A power-up capsule: a coloured block with its letter (game.draw_game)."""
    col = G.SPECIAL[kind]
    G.glow(S, x, y, 26 * k, col, 0.5)
    r = pygame.Rect(0, 0, round(26 * k), round(22 * k))
    r.center = (round(x), round(y))
    S.fill(col, r)
    letter = kit.tint(kit.text_shape(G.CAP_INFO[kind][0], kit.PIXEL_FONT, 8 * round(12 * k / 8)), BG)
    kit.blit_center(S, letter, (x + k, y + k))


def cosmic_ray(S: pygame.Surface, x: float, y: float, k: float, t: float) -> None:
    """The Cosmic Ray (the game's UFO): a Gaussian wave packet in yellow."""
    G.glow(S, x, y, 46 * k, G.YELLOW, 0.4)
    env = lambda dx: math.exp(-(dx * dx) / (2 * (18 * k) ** 2))  # noqa: E731
    xs = range(round(-70 * k), round(70 * k) + 1, 2)
    up = [(x + dx, y - 16 * k * env(dx)) for dx in xs]
    dn = [(x + dx, y + 16 * k * env(dx)) for dx in reversed(xs)]
    pygame.draw.lines(S, G.fade(G.YELLOW, 0.3), True, up + dn, max(1, round(k)))
    pts = [(x + dx, y - 16 * k * env(dx) * math.cos(dx / k * 0.38 - t * 18)) for dx in xs]
    pygame.draw.lines(S, G.YELLOW, False, pts, round(3 * k))


# --- the scene ---------------------------------------------------------------


def stars(S: pygame.Surface, rng: random.Random) -> None:
    w, h = S.get_size()
    for _ in range(260):
        x, y = rng.uniform(0, w), rng.uniform(0, h)
        b = rng.random() ** 2
        c = kit.lerp((40, 44, 70), (220, 225, 255), b)
        s = 2 if b < 0.7 else 3
        S.fill(c, (x, y, s, s))


# The formation, back row first: (centre y, px per sprite pixel, colours).
# Colours come in runs, like game.next_wave() deals them. Lower case marks
# the invaders being hit: "z"/"x" burst (a matching shot), "y" flashes white
# (a blue shot converting it -- Y = X * Z).
ROWS = [
    (588, 4, "XXZZZYYXXZZ"),
    (642, 5, "ZZYYXXXZZ"),
    (712, 7, "YXXXZZY"),
    (792, 9, "XzyxZ"),
]


def scene(size: int) -> pygame.Surface:
    u = size / 1024
    rng = random.Random(7)
    S = pygame.Surface((size, size)).convert()
    S.fill(BG)
    S.blit(kit.gradient((size, size), [(16, 12, 38), BG, BG, (8, 14, 16)]), (0, 0))
    stars(S, rng)

    # coloured light: the players' sides at the bottom, the boss above
    S.blit(kit.radial((size, size), (0, size), 640 * u, COL["Z"], 0.5), (0, 0), special_flags=pygame.BLEND_ADD)
    S.blit(kit.radial((size, size), (size, size), 640 * u, COL["X"], 0.5), (0, 0), special_flags=pygame.BLEND_ADD)

    # the boss, mid-spiral, and the Cosmic Ray crossing above the formation
    bx, by, bk = size / 2, 165 * u, 2.4 * u
    for arm in range(4):
        for j in range(10):
            d = (bosses.SHIELD_R + 18 + j * 30) * bk
            a = arm * math.pi / 2 + j * 0.28 + 0.55
            x, y = bx + math.cos(a) * d, by + math.sin(a) * d
            if 0 < x < size and 0 < y < 0.55 * size:
                orb(S, x, y, 1.5 * u * (1 + j * 0.06))
    clifford(S, bx, by, bk, 0.35)
    cosmic_ray(S, 150 * u, 95 * u, 1.8 * u, 0.4)
    # two minions wavering down beside the boss
    for x, y, col in ((870, 92, "Y"), (905, 210, "Z")):
        G.glow(S, x * u, y * u, 40 * u, COL[col], 0.3)
        kit.blit_center(S, invader(col, round(5 * u), 1), (x * u, y * u))
    colour_orb(S, 70 * u, 545 * u, "X", 1.6 * u)
    colour_orb(S, 960 * u, 330 * u, "Z", 1.6 * u)

    # the formation
    hits = {}
    for ri, (y, px, cols) in enumerate(ROWS):
        px = max(2, round(px * u))
        y *= u
        gap = 10 * px * (1.75 if ri == len(ROWS) - 1 else 1.55)
        for i, c in enumerate(cols):
            x = size / 2 + (i - (len(cols) - 1) / 2) * gap
            if c in "xz":
                hits[c] = (x, y, px)
                continue
            spr = invader(c.upper(), px, (ri + i) % 2, flash=c == "y")
            G.glow(S, x, y, 9 * px, WHITE if c == "y" else COL[c], 0.45 if c == "y" else 0.22)
            kit.blit_center(S, spr, (x, y))
            if c == "y":
                hits["y"] = (x, y, px)

    # ships at the bottom: P1 blue (left), P2 red (right), each straight
    # below its target (the game's ships fire straight up). The sprites are
    # the game's own, built at 1.4x and then doubled pixel for pixel.
    p1 = (hits["z"][0], size * 0.905)
    p2 = (hits["x"][0], size * 0.905)
    k = max(1, round(2 * u))
    tri = kit.nearest(G.triangle_sprite("Z", 31), k)
    patch = kit.nearest(G.patch_sprite("X", 50), k)

    # each ship's shot bursting on an invader of its own colour, a third
    # (blue) one turning the purple Y white, and the formation firing back
    for (sx, sy), key, col in ((p1, "z", "Z"), (p2, "x", "X")):
        tx, ty, px = hits[key]
        burst(S, tx, ty, COL[col], 50, 10 * px, px / 3.6, rng)
        bolt(S, sx, ty + 7 * px, COL[col], 2.4 * u, 0.8)
    yx, yy, ypx = hits["y"]
    bolt(S, yx, yy + 8 * ypx, COL["Z"], 2.4 * u)

    G.glow(S, *p1, 100 * u, COL["Z"], 0.6)
    G.glow(S, *p2, 100 * u, COL["X"], 0.6)
    kit.blit_center(S, tri, p1)
    kit.blit_center(S, patch, p2)
    for x, y in ((0.07, 0.93), (0.565, 0.965), (0.14, 0.84), (0.89, 0.87), (0.95, 0.97)):
        zigzag(S, x * size, y * size, 2 * u)

    capsule(S, size * 0.09, size * 0.64, "spread", 2.0 * u)
    capsule(S, size * 0.91, size * 0.68, "bomb", 2.0 * u)
    return S


# --- lettering ---------------------------------------------------------------


def word(text: str, col: str, k: int) -> pygame.Surface:
    """One word of the title, ARQADE-style, without its glow (see lettering())."""
    shape = kit.text_shape(text, kit.PIXEL_FONT, 8 * k, tracking=1)
    return kit.wordmark(shape, FILL[col], gap=5, outline=7, extrude=12,
                        extrude_color=kit.shade(COL[col], 0.3), square=True)


def lettering(parts: list[tuple[pygame.Surface, tuple[int, int]]], size: tuple[int, int],
             split: float, vertical: bool) -> pygame.Surface:
    """Words placed at their top-left positions under one shared glow, red
    before `split` (a fraction of the width or height) and blue after it.

    One glow for the whole title, rather than one per word: stacking two
    words that each carry their own glow leaves a hard seam where one
    transparent surface lands on the other.
    """
    m = GLOW_R * 3
    full = (size[0] + 2 * m, size[1] + 2 * m)
    letters = pygame.Surface(full, pygame.SRCALPHA)
    for surf, (x, y) in parts:
        letters.blit(surf, (x + m, y + m))
    paint = pygame.Surface(full)
    paint.fill(COL["Z"])
    cut = m + round(split * size[1 if vertical else 0])
    paint.fill(COL["X"], (0, 0, full[0], cut) if vertical else (0, 0, cut, full[1]))
    out = kit.tint(kit.glow(letters, WHITE, GLOW_R, 0.85), kit.blur(paint, 32))
    out.blit(letters, (0, 0))
    return kit.trim(out)


def title() -> pygame.Surface:
    """PAULI over INVADERS (red over blue, as on the game's title screen)."""
    pauli = word("PAULI", "X", 16)
    invaders = word("INVADERS", "Z", 12)
    w = max(pauli.get_width(), invaders.get_width())
    top = pauli.get_height() - 6
    return lettering([(pauli, ((w - pauli.get_width()) // 2, 0)),
                      (invaders, ((w - invaders.get_width()) // 2, top))],
                     (w, top + invaders.get_height()), (top + 10) / (top + invaders.get_height()), True)


def art(size: int) -> pygame.Surface:
    S = kit.finish(scene(size), vignette_strength=0.55)
    t = title()
    if t.get_width() > size:   # only when rendering smaller than 1024
        t = kit.fit(t, size, size)
    r = kit.blit_center(S, t, (size / 2, size * 0.36))
    tag = kit.tagline("Retro meets quantum error correction", round(20 * size / 1024), (200, 215, 220))
    kit.blit_center(S, tag, (size / 2, r.bottom - GLOW_R * 1.2 + 4))
    return S


def emblem(col: str, frame: int) -> pygame.Surface:
    """An invader in the title's lettering style, its letter put back on top."""
    px = 9
    out = kit.wordmark(invader(col, px, frame, letter=False), FILL[col], gap=4, outline=6, extrude=10,
                       extrude_color=kit.shade(COL[col], 0.3), square=True, highlight=False)
    add_letter(out, col, px, (10, 10))   # trimmed: the sprite starts gap + outline in
    return out


def marquee() -> pygame.Surface:
    """PAULI INVADERS on one line, a red and a blue invader as end caps."""
    pauli = word("PAULI", "X", 10)
    invaders = word("INVADERS", "Z", 10)
    left, right = emblem("X", 0), emblem("Z", 1)
    h = pauli.get_height()
    sp = 20
    x1 = left.get_width() + sp
    x2 = x1 + pauli.get_width() + sp
    x3 = x2 + invaders.get_width() + sp
    cy = lambda s: (h - s.get_height()) // 2  # noqa: E731
    w = x3 + right.get_width()
    return lettering([(left, (0, cy(left))), (pauli, (x1, 0)), (invaders, (x2, 0)), (right, (x3, cy(right)))],
                     (w, h), (x2 - sp / 2) / w, False)
