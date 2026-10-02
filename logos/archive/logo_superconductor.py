"""Superconductor: a chip mid-game, tilted away into the dark, under the title.

The chip is the game's own: a `Lattice("distributed")` (four 3x3 modules
joined by hollow waveguide bridges) with a scripted `Board` on it -- two
qubits racing along committed routes, one gate just firing, stations
waiting with their coherence arcs running down, both players' cursors
drawing routes, plus a speed qubit, a Bell link and a miscalibrated
coupler. All of it is drawn flat by the game's `draw_board()` onto a large
surface, which is then rotated and laid back in perspective (`floor()`),
so the near corner fills the frame and the far side fades out behind the
lettering. Bloom on top makes the routes and qubits glow.

The marquee is the title on one line between two of the game's Xmon
crosses (`draw_xmon()`), the two ends of a pair, in P1 blue and P2 red.
"""

from __future__ import annotations

import math
import random
import sys

import kit
import pygame

sys.path.insert(0, str(kit.ROOT / "superconductor/src"))

from superconductor import game  # noqa: E402
from superconductor.lattice import Lattice  # noqa: E402
from superconductor.rules import Board, Pair  # noqa: E402

ROM = "superconductor"

# Colours from superconductor/game.py
BG, CYAN = game.BG, game.CYAN
RED, GREEN, BLUE = game.PAIR_COLORS[0], game.PAIR_COLORS[1], game.PAIR_COLORS[4]

# Title lettering: icy white into the game's CYAN, a deep blue extrusion.
FILL = [(255, 255, 255), (200, 246, 255), CYAN, (40, 130, 235)]
EXTRUDE = (16, 40, 110)

FLAT = 1800  # side of the flat chip render, before the perspective warp


# --- the scene --------------------------------------------------------------


def _scene() -> game.View:
    """A Board in a busy, readable moment (no update(): state is set by hand)."""
    lat = Lattice("distributed")
    board = Board(lat, 7, ("p1", "p2"), specials=False)
    pairs = [
        # (a, b, colour, coherence left)
        ((0, 0), (5, 4), 0, 1.0),     # red: committed, racing across two bridges
        ((5, 0), (3, 5), 4, 1.0),     # blue: committed, along the near modules
        ((3, 2), (0, 4), 1, 0.62),    # green: waiting
        ((5, 5), (2, 0), 2, 0.22),    # yellow: waiting, nearly decohered
        ((1, 1), (4, 1), 3, 0.8),     # violet: P1 is drawing its route
        ((0, 5), (3, 0), 6, 0.45),    # pink: P2 is drawing its route
    ]
    for i, (a, b, col, frac) in enumerate(pairs):
        pair = Pair(i, a, b, col, 30.0, 30.0 * frac)
        board.pairs[i] = pair
        board.endpoint_owner[a] = board.endpoint_owner[b] = i
    board.place_special("speed", nodes=((5, 2),))
    board.place_special("miscal", edge_=frozenset({(2, 3), (2, 4)}))
    board.place_special("bell", nodes=((0, 2), (3, 3)))
    board.commit_route(0, [(0, 0), (0, 1), (1, 1), (1, 2), (1, 3), (1, 4), (2, 4), (3, 4),
                           (4, 4), (5, 4)])
    board.pairs[0].progress = 4.55
    board.commit_route(1, [(5, 0), (5, 1), (5, 2), (4, 2), (4, 3), (4, 4), (4, 5), (3, 5)])
    board.pairs[1].progress = 1.4
    # commit_route() autoselects stations; put the cursors where we want them
    board.cursors["p1"].pair_id, board.cursors["p1"].path = 4, [(1, 1), (2, 1), (3, 1)]
    board.cursors["p2"].pair_id, board.cursors["p2"].path = 5, [(0, 5), (1, 5)]
    board.events.clear()

    view = game.View(board, FLAT / 2, FLAT / 2, FLAT * 0.86, FLAT * 0.86, max_spacing=10 ** 4)
    # a gate going off on the green station: the game's own burst and rings,
    # run forward a little so the sparks have spread out
    random.seed(3)
    for n in ((3, 2),):
        view.burst(n, GREEN, 40, 360)
        view.ring(n, game.WHITE, 8, view.spacing * 0.9, 0.5)
        view.ring(n, GREEN, 6, view.spacing * 0.6, 0.6)
    for _ in range(9):
        view.update_fx(1 / 60)
    return view


def _flash(surf: pygame.Surface, view: game.View) -> None:
    """Light from the gate that is firing on the green station."""
    x, y = view.xy((3, 2))
    game.glow(surf, x, y, view.spacing * 1.5, GREEN, 0.7)
    game.glow(surf, x, y, view.spacing * 0.5, (255, 255, 255), 0.6)


def _trails(surf: pygame.Surface, view: game.View) -> None:
    """Additive light streaks behind each travelling qubit (bloom bait)."""
    for pair in view.board.travelling_pairs():
        col = game.PAIR_COLORS[pair.color]
        pts = [view.xy(n) for n in pair.route[: int(pair.progress) + 1]] + [view.qubit_xy(pair)]
        # walk back from the qubit along the route, fading out
        length = view.spacing * 2.2
        seg = []
        d = 0.0
        for (x1, y1), (x0, y0) in zip(pts[::-1], pts[::-1][1:]):
            ln = math.hypot(x1 - x0, y1 - y0)
            seg.append(((x1, y1), (x0, y0), d, ln))
            d += ln
        layer = pygame.Surface(surf.get_size())
        for (x1, y1), (x0, y0), d0, ln in seg:
            steps = max(1, int(ln / 6))
            for i in range(steps):
                f0, f1 = i / steps, (i + 1) / steps
                k = 1 - (d0 + ln * f0) / length
                if k <= 0:
                    break
                a = (x1 + (x0 - x1) * f0, y1 + (y0 - y1) * f0)
                b = (x1 + (x0 - x1) * f1, y1 + (y0 - y1) * f1)
                pygame.draw.line(layer, kit.shade(col, k ** 1.5), a, b, max(2, round(26 * k)))
                pygame.draw.line(layer, kit.shade((255, 255, 255), k ** 2), a, b, max(1, round(8 * k)))
        surf.blit(kit.blur(layer, 4), (0, 0), special_flags=pygame.BLEND_ADD)
        surf.blit(layer, (0, 0), special_flags=pygame.BLEND_ADD)
        # and a flare on the qubit itself, with the game's own glow()
        x, y = view.qubit_xy(pair)
        game.glow(surf, x, y, view.spacing * 1.1, col, 0.8)
        game.glow(surf, x, y, view.spacing * 0.4, (255, 255, 255), 0.7)


def _chip() -> pygame.Surface:
    surf = pygame.Surface((FLAT, FLAT), pygame.SRCALPHA)  # only the substrate is opaque
    view = _scene()
    game.draw_board(surf, view, 0.25)
    _trails(surf, view)
    _flash(surf, view)
    return surf


# --- perspective ------------------------------------------------------------


def floor(src: pygame.Surface, size: int, horizon: float, z_far: float, width_near: float,
          y_near: float) -> pygame.Surface:
    """Lay `src` back like a floor seen from above, one scaled row at a time.

    A row at depth z lands at y = horizon + G / z and is scaled by F / z,
    which is exactly the plane's projection. The near edge (z = 1) sits at
    `y_near` and spans `width_near`; the far edge is at depth `z_far`.
    """
    sw, sh = src.get_size()
    out = pygame.Surface((size, size), pygame.SRCALPHA)
    g = y_near - horizon
    f = width_near / sw
    y_top = horizon + g / z_far
    for y in range(max(0, int(y_top)), min(size, int(y_near) + 1)):
        z = g / max(1e-6, y - horizon)
        u = (z_far - z) / (z_far - 1)  # 0 far, 1 near
        if not 0 <= u <= 1:
            continue
        row = src.subsurface((0, min(sh - 1, int(u * (sh - 1))), sw, 1))
        w = max(1, round(sw * f / z))
        out.blit(pygame.transform.scale(row, (w, 1)), (size / 2 - w / 2, y))
    return out


def _fade(size: int, top: float, bottom: float) -> pygame.Surface:
    """Multiply mask: black above `top`, white below `bottom`, eased between."""
    m = pygame.Surface((size, size))
    for y in range(size):
        t = min(1.0, max(0.0, (y - top) / (bottom - top)))
        m.fill(kit.shade((255, 255, 255), t * t * (3 - 2 * t)), (0, y, size, 1))
    return m


# --- the pieces -------------------------------------------------------------


def _title(scale: float = 1.0) -> pygame.Surface:
    """SUPER over CONDUCTOR, the short word bigger, both in the pixel font."""
    common = dict(gap=round(5 * scale), outline=round(6 * scale), extrude=round(14 * scale),
                  extrude_color=EXTRUDE, square=True)
    top = kit.wordmark(kit.text_shape("SUPER", kit.PIXEL_FONT, round(136 * scale), tracking=1),
                       FILL, **common)
    bottom = kit.wordmark(kit.text_shape("CONDUCTOR", kit.PIXEL_FONT, round(88 * scale), tracking=1),
                          FILL, **common)
    gap = round(18 * scale)
    w = max(top.get_width(), bottom.get_width())
    out = pygame.Surface((w, top.get_height() + gap + bottom.get_height()), pygame.SRCALPHA)
    out.blit(top, ((w - top.get_width()) // 2, 0))
    out.blit(bottom, ((w - bottom.get_width()) // 2, top.get_height() + gap))
    return out


def _with_glow(surf: pygame.Surface, color, radius: int, strength: float) -> pygame.Surface:
    p = kit.pad(surf, radius * 2)
    out = kit.glow(p, color, radius, strength)
    out.blit(p, (0, 0))
    return out


def art(size: int) -> pygame.Surface:
    ss = size * 2  # warp at double size, then smoothscale down (antialiasing)
    chip = pygame.transform.rotozoom(_chip(), -27, 1.0)
    # far corner tucked under the title, near corner just off the bottom edge
    slab = floor(chip, ss, horizon=-0.42 * ss, z_far=2.0, width_near=1.62 * ss, y_near=1.03 * ss)
    slab = pygame.transform.smoothscale(slab, (size, size))

    surf = pygame.Surface((size, size))
    surf.fill(BG)
    surf.blit(kit.radial((size, size), (size * 0.5, size * 0.3), size * 0.8, (18, 40, 96), 0.9),
              (0, 0), special_flags=pygame.BLEND_ADD)
    # a cold rim light around the chip, then its edge: the substrate's thickness
    surf.blit(kit.glow(slab, (30, 90, 200), 40, 0.55), (0, 0))
    side = kit.tint(slab, kit.shade(game.SUBSTRATE_EDGE, 0.55))
    for dy in range(18, 0, -1):
        surf.blit(side if dy > 2 else kit.tint(slab, game.SUBSTRATE_EDGE), (0, dy))
    surf.blit(slab, (0, 0))
    # bloom: only what is brighter than the substrate bleeds light
    bright = surf.copy()
    bright.fill((60, 60, 60), special_flags=pygame.BLEND_SUB)
    bright.blit(bright, (0, 0), special_flags=pygame.BLEND_ADD)
    surf.blit(kit.blur(bright, 8), (0, 0), special_flags=pygame.BLEND_ADD)
    surf.blit(kit.blur(bright, 32), (0, 0), special_flags=pygame.BLEND_ADD)
    # the far side sinks into the dark behind the title
    surf.blit(_fade(size, size * 0.12, size * 0.5), (0, 0), special_flags=pygame.BLEND_MULT)
    surf = kit.finish(surf, vignette_strength=0.55, scan=True)

    title = _with_glow(kit.fit(_title(), size * 0.9, size * 0.4, smooth=False), kit.shade(CYAN, 0.6), 28, 0.4)
    kit.blit_center(surf, title, (size / 2, size * 0.215))
    tag = kit.tagline("Route the gates before they decohere", 26, (210, 230, 255), tracking=4)
    tag = _with_glow(tag, BG, 10, 1.0)
    kit.blit_center(surf, tag, (size / 2, size * 0.95))
    return surf


def _xmon_emblem(size: int, col) -> pygame.Surface:
    """The game's Xmon cross (draw_xmon), outlined like the lettering."""
    shape = pygame.Surface((size, size), pygame.SRCALPHA)
    game.draw_xmon(shape, size // 2, size // 2, size * 2.6, (255, 255, 255))
    return kit.wordmark(kit.trim(shape), [kit.lerp(col, (255, 255, 255), 0.5), col], gap=5, outline=6,
                        extrude=12, extrude_color=kit.shade(col, 0.3), square=True,
                        glow_color=col, glow_radius=26, glow_strength=0.8)


def marquee() -> pygame.Surface:
    word = kit.wordmark(kit.text_shape("SUPERCONDUCTOR", kit.PIXEL_FONT, 72, tracking=1), FILL,
                        gap=5, outline=6, extrude=12, extrude_color=EXTRUDE, square=True,
                        glow_color=CYAN, glow_radius=26, glow_strength=0.7)
    # the two ends of a pair, in the cabinet's P1 blue and P2 red
    left, right = _xmon_emblem(108, BLUE), _xmon_emblem(108, RED)
    tag = kit.tagline("Route the gates before they decohere", 28, (210, 230, 255), tracking=6)
    tag = _with_glow(tag, BG, 8, 1.0)
    w = left.get_width() + word.get_width() + right.get_width() - 110
    h = max(word.get_height(), left.get_height()) + tag.get_height() - 30
    out = pygame.Surface((w, h), pygame.SRCALPHA)
    cy = max(word.get_height(), left.get_height()) // 2
    out.blit(left, (0, cy - left.get_height() // 2))
    out.blit(right, (w - right.get_width(), cy - right.get_height() // 2))
    out.blit(word, (left.get_width() - 55, cy - word.get_height() // 2))
    kit.blit_center(out, tag, (w / 2, cy + word.get_height() / 2 - 6))
    return kit.trim(out)
