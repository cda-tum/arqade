"""Superconductor: the chip as a metro map, the title on a station sign.

Two station pairs in the game's GREEN and YELLOW pair colours, each joined
by its route along the chip's lattice, drawn like transit lines: thick,
straight, corners cut at 45 degrees, in a dark casing. The two routes meet
at one shared qubit -- not an interchange but a clash: the game's red
collision warning sits on it (the X in a ring that draw_board puts where
predict_collision() finds two routes claiming the same qubit), so the icon
reads as conflicting paths rather than a rail network. The rest of the chip is the game's own lattice
(`Lattice("square", 4, 6)`) with its couplers and idle Xmon qubits
(`draw_xmon()`) kept faint, like the grey streets under a metro map. Each
station is the game's waiting station, an Xmon inside its coherence ring,
set as a metro terminus on a white disc; the yellow rings are already
running down.

The title is a white enamel station sign below, with the two lines'
roundels on it. The marquee is that same sign on its own.
"""

from __future__ import annotations

import math
import sys

import kit
import pygame

sys.path.insert(0, str(kit.ROOT / "superconductor/src"))

from superconductor import game  # noqa: E402
from superconductor.lattice import Lattice  # noqa: E402

ROM = "superconductor"

# Colours from superconductor/game.py
BG, COUPLER, QUBIT_IDLE = game.BG, game.COUPLER, game.QUBIT_IDLE
GREEN, YELLOW = game.PAIR_COLORS[1], game.PAIR_COLORS[2]
SIGN = (240, 242, 248)  # enamel white
INK = (14, 20, 44)  # sign lettering: a deep version of the game's BG

LATTICE = Lattice("square", 4, 6)
# (route through the lattice, colour, coherence left); only the corners are
# listed, the stops in between follow from them
ROUTES = [
    ([(3, 0), (3, 3), (1, 3), (1, 5)], YELLOW, 0.7),
    ([(0, 0), (0, 2), (2, 2), (2, 5)], GREEN, 1.0),
]


def _stops(corners):
    """Every lattice node along a corner-to-corner route."""
    out = [corners[0]]
    for (r0, c0), (r1, c1) in zip(corners, corners[1:]):
        n = abs(r1 - r0) + abs(c1 - c0)
        out += [(r0 + (r1 - r0) * i // n, c0 + (c1 - c0) * i // n) for i in range(1, n + 1)]
    return out


def _chamfer(pts, cut: float):
    """Cut every corner of a right-angled polyline at 45 degrees, metro-map style."""
    out = [pts[0]]
    for (x0, y0), (x1, y1), (x2, y2) in zip(pts, pts[1:], pts[2:]):
        d0 = math.hypot(x1 - x0, y1 - y0)
        d1 = math.hypot(x2 - x1, y2 - y1)
        out.append((x1 - (x1 - x0) / d0 * cut, y1 - (y1 - y0) / d0 * cut))
        out.append((x1 + (x2 - x1) / d1 * cut, y1 + (y2 - y1) / d1 * cut))
    return out + [pts[-1]]


def _polyline(surf: pygame.Surface, col, pts, width: float) -> None:
    """A thick line with clean round joins (pygame's own thick lines notch at bends)."""
    h = width / 2
    for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
        d = math.hypot(x1 - x0, y1 - y0)
        nx, ny = -(y1 - y0) / d * h, (x1 - x0) / d * h
        pygame.draw.polygon(surf, col, [(x0 + nx, y0 + ny), (x1 + nx, y1 + ny), (x1 - nx, y1 - ny),
                                        (x0 - nx, y0 - ny)])
    for p in pts:
        pygame.draw.circle(surf, col, p, h)


def _map(sp: float, origin: tuple[float, float]) -> pygame.Surface:
    """The chip at spacing `sp` px, on a transparent surface (drawn at 2x by art())."""
    ox, oy = origin

    def xy(n):
        return ox + n[1] * sp, oy + n[0] * sp

    size = (round(ox * 2 + (LATTICE.cols - 1) * sp), round(oy * 2 + (LATTICE.rows - 1) * sp))
    surf = pygame.Surface(size, pygame.SRCALPHA)
    ends = {n for corners, _, _ in ROUTES for n in (corners[0], corners[-1])}
    # the faint chip underneath: the game's couplers and idle qubits
    for e in LATTICE.edges:
        a, b = tuple(e)
        pygame.draw.line(surf, kit.shade(COUPLER, 0.75), xy(a), xy(b), round(sp * 0.035))
    for n in LATTICE.nodes:
        if n not in ends:
            game.draw_xmon(surf, *xy(n), sp * 0.62, kit.shade(QUBIT_IDLE, 0.6))

    line_w = round(sp * 0.2)
    for corners, col, _ in ROUTES:
        pts = _chamfer([xy(n) for n in corners], sp * 0.4)
        # casing first, in the background colour, so a later line cuts cleanly over an earlier one
        for w, c in ((line_w + round(sp * 0.14), BG), (line_w, col)):
            _polyline(surf, c, pts, w)
    # where the two lines claim the same qubit: the game's collision warning
    # (draw_board: draw_x at sp*0.2 plus a ring at sp*0.34, both RED)
    shared = set(_stops(ROUTES[0][0])) & set(_stops(ROUTES[1][0]))
    for n in shared:
        x, y = xy(n)
        pygame.draw.circle(surf, BG, (x, y), sp * 0.42)
        game.draw_x(surf, x, y, sp * 0.2, game.RED, round(sp * 0.09))
        pygame.draw.circle(surf, game.RED, (x, y), sp * 0.34, round(sp * 0.06))

    # the stations: the game's waiting station (draw_board) -- an Xmon inside
    # its coherence ring, in the pair's colour -- set as a metro terminus:
    # white disc, thick coloured ring
    for corners, col, frac in ROUTES:
        for n in (corners[0], corners[-1]):
            x, y = xy(n)
            r = sp * 0.34
            pygame.draw.circle(surf, BG, (x, y), r + sp * 0.07)
            pygame.draw.circle(surf, SIGN, (x, y), r)
            ring = pygame.Rect(0, 0, 2 * r, 2 * r)
            ring.center = (round(x), round(y))
            width = round(sp * 0.1)
            pygame.draw.arc(surf, kit.lerp(SIGN, col, 0.35), ring, 0, 2 * math.pi, width)
            pygame.draw.arc(surf, col, ring, math.pi / 2, math.pi / 2 + 2 * math.pi * frac - 1e-3, width)
            game.draw_xmon(surf, x, y, sp * 0.68, kit.shade(col, 0.55))
    return surf


def _roundel(d: int, col) -> pygame.Surface:
    """A line bullet for the sign: the line's colour with a dark Xmon in it."""
    s = pygame.Surface((d, d), pygame.SRCALPHA)
    pygame.draw.circle(s, col, (d / 2, d / 2), d / 2)
    game.draw_xmon(s, d / 2, d / 2, d * 1.45, INK)
    return s


def _sign(width: int) -> pygame.Surface:
    """SUPERCONDUCTOR on a white enamel plate: dark band, roundels, name."""
    k = width / 880
    h = round(150 * k)
    d = round(56 * k)
    bullets = [_roundel(d, YELLOW), _roundel(d, GREEN)]
    word = kit.tint(kit.text_shape("SUPERCONDUCTOR", kit.RUBIK_FONT, round(80 * k), pixel=False,
                                   tracking=round(2 * k)), INK)
    room = width - round(84 * k) - 2 * d - round(30 * k)  # what the name may span
    word = kit.fit(kit.trim(word), room, h)
    inner = 2 * (d + round(12 * k)) + round(18 * k) + word.get_width()
    w = width
    plate = pygame.Surface((w, h), pygame.SRCALPHA)
    r = round(18 * k)
    pygame.draw.rect(plate, SIGN, plate.get_rect(), 0, r)
    pygame.draw.rect(plate, INK, plate.get_rect().inflate(-round(16 * k), -round(16 * k)), round(4 * k),
                     r - round(6 * k))
    x = (w - inner) // 2
    for b in bullets:
        plate.blit(b, (x, (h - d) // 2))
        x += d + round(12 * k)
    plate.blit(word, (x + round(18 * k), (h - word.get_height()) // 2))
    return plate


def _shadowed(surf: pygame.Surface, offset: int) -> pygame.Surface:
    """A hard dark drop shadow under a sign (no glow)."""
    out = pygame.Surface((surf.get_width() + offset, surf.get_height() + offset), pygame.SRCALPHA)
    out.blit(kit.tint(surf, (0, 0, 0)), (offset, offset))
    out.blit(surf, (0, 0))
    return out


def art(size: int) -> pygame.Surface:
    ss = size * 2  # draw at double size, smoothscale down: antialiased lines
    big = pygame.Surface((ss, ss))
    big.fill(BG)
    sp = ss * 0.145
    chip = _map(sp, (sp * 0.6, sp * 0.6))
    kit.blit_center(big, chip, (ss / 2, ss * 0.375))
    kit.blit_center(big, _shadowed(_sign(round(ss * 0.86)), round(ss * 0.008)), (ss / 2, ss * 0.805))
    return pygame.transform.smoothscale(big, (size, size))


def marquee() -> pygame.Surface:
    big = _shadowed(_sign(2800), 20)
    return pygame.transform.smoothscale(big, (big.get_width() // 2, big.get_height() // 2))
