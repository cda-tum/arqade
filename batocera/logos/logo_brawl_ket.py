"""Brawl-Ket: the clash, as a comic-book impact panel.

The hero is the game's one rule, colour must match to hurt, in one hit: P1's
TRIO (on the left, its blue player ring under it) is purple, in the X basis,
and lands a heavy, its other colour, so its fist glows green; P2's QUINT (on
the right, its red ring under it) is green, in the Z basis, so the green hit
matches and QUINT reels back. Both are the game's own puppets, drawn by its own
draw_puppet from its own poses at the game's pixel size and scaled up
nearest-neighbour, with the game's striker glow and hit spark in green. Behind them is the look none of the other icons
has: a comic panel split on the diagonal into each player's side, with
halftone dots and speed lines bursting out of the impact. BRAWL-KET sits
below as the title screen draws it: BRAWL- in P1's blue and KET in P2's red,
in the game's thick ink outline.
"""

from __future__ import annotations

import math
import sys

import kit
import pygame

sys.path.insert(0, str(kit.ROOT / "brawl-ket/src"))
from brawl_ket import palette as P  # noqa: E402
from brawl_ket.config import PLAYER_COLORS  # noqa: E402
from brawl_ket.moves import QUINT, TRIO  # noqa: E402
from brawl_ket.poses import POSES  # noqa: E402
from brawl_ket.render import ACCENT, GREEN, PURPLE, draw_puppet  # noqa: E402

ROM = "brawl_ket"
BLUE, RED = PLAYER_COLORS["p1"], PLAYER_COLORS["p2"]
ZOOM = 4                    # game px -> icon px
NATIVE = (184, 172)         # the hero's canvas, in game px
FLOOR = 168


def hero() -> tuple[pygame.Surface, tuple[int, int]]:
    """The two puppets at game resolution on transparency, and where the fist lands."""
    s = pygame.Surface(NATIVE, pygame.SRCALPHA)
    # the players' rings under their feet (Renderer._shadow): P1 blue, P2 red
    for x, colour in ((52, BLUE), (128, RED)):
        ring = pygame.Rect(0, 0, 60, 12)
        ring.center = (x, FLOOR + 2)
        pygame.draw.ellipse(s, P.INK, ring.inflate(2, 2), 3)
        pygame.draw.ellipse(s, colour, ring, 2)
    # QUINT first, behind: the one being hit, green (the Z basis)
    draw_puppet(s, POSES["hitstun"], QUINT.build, (128, FLOOR), -1, GREEN, ACCENT["QUINT"])
    # TRIO purple (the X basis); its heavy is the other colour, green
    j = draw_puppet(s, POSES["heavy_hit"], TRIO.build, (52, FLOOR), 1, PURPLE, ACCENT["TRIO"])
    fist = (round(j["hand_f"][0]) + 3, round(j["hand_f"][1]))
    # the striker glow and the game's hit spark (Renderer._striker, _draw_effects), green
    pygame.draw.circle(s, P.INK, fist, 10)
    pygame.draw.circle(s, P.WHITE, fist, 8)
    pygame.draw.circle(s, GREEN, fist, 5)
    pygame.draw.circle(s, P.WHITE, fist, 2)
    return s, fist


def burst(center, r_in: float, r_out: float, points: int, color, phase: float = 0.0) -> list:
    pts = []
    for i in range(points * 2):
        a = phase + math.pi * i / points
        r = r_out if i % 2 == 0 else r_in
        pts.append((center[0] + r * math.cos(a), center[1] + r * math.sin(a)))
    return pts


def panel(size: int, impact: tuple[float, float]) -> pygame.Surface:
    """The comic panel: each player's side of a diagonal split, halftone dots
    growing towards the impact, and speed lines bursting out of it."""
    surf = pygame.Surface((size, size))
    surf.fill(P.INK)
    left = kit.shade(BLUE, 0.42)
    right = kit.shade(RED, 0.42)
    # the split runs through the impact, leaning like a punch landing
    lean = 0.35
    top_x = impact[0] + impact[1] * lean
    bottom_x = impact[0] - (size - impact[1]) * lean
    pygame.draw.polygon(surf, left, [(0, 0), (top_x, 0), (bottom_x, size), (0, size)])
    pygame.draw.polygon(surf, right, [(top_x, 0), (size, 0), (size, size), (bottom_x, size)])
    # halftone: dots on a 45-degree grid, bigger near the impact
    dots = pygame.Surface((size, size), pygame.SRCALPHA)
    step = 26
    reach = size * 0.75
    for gy in range(-1, size // step + 2):
        for gx in range(-1, size // step + 2):
            x = gx * step + (step // 2 if gy % 2 else 0)
            y = gy * step
            d = math.hypot(x - impact[0], y - impact[1])
            r = 11 * max(0.0, 1 - d / reach)
            if r >= 1.5:
                side = left if x < impact[0] + (impact[1] - y) * lean else right
                pygame.draw.circle(dots, (*kit.shade(side, 1.7), 255), (x, y), round(r))
    surf.blit(dots, (0, 0))
    # speed lines from the impact out to the edges
    lines = pygame.Surface((size, size), pygame.SRCALPHA)
    for i in range(28):
        a = 2 * math.pi * i / 28 + (0.05 if i % 2 else -0.04)
        r0, r1 = 150 + (i % 3) * 30, size
        w = 10 if i % 3 == 0 else 5
        p0 = (impact[0] + r0 * math.cos(a), impact[1] + r0 * math.sin(a))
        p1 = (impact[0] + r1 * math.cos(a), impact[1] + r1 * math.sin(a))
        pygame.draw.line(lines, (*P.CREAM, 70), p0, p1, w)
    surf.blit(lines, (0, 0))
    # the impact burst, in the comic's POW colours: a cream star over an ink one
    pygame.draw.polygon(surf, P.INK, burst(impact, 96, 190, 12, P.INK, 0.1))
    pygame.draw.polygon(surf, P.GOLD, burst(impact, 84, 170, 12, P.GOLD, 0.1))
    pygame.draw.polygon(surf, P.CREAM, burst(impact, 60, 120, 12, P.CREAM, 0.36))
    return surf


def title(scale: int) -> pygame.Surface:
    """BRAWL-KET as the title screen draws it: BRAWL- blue, KET red, in a thick ink
    outline (and room for a shadow, which the marquee's transparency needs)."""
    parts = [(kit.text_shape(text, kit.PIXEL_FONT, 8 * scale), color)
             for text, color in (("BRAWL-", BLUE), ("KET", RED))]
    w = sum(s.get_width() for s, _ in parts)
    h = parts[0][0].get_height()
    o = max(2, scale // 2)          # the ink outline
    sh = max(3, scale * 3 // 4)     # the drop shadow
    out = pygame.Surface((w + 2 * o + sh, h + 2 * o + sh), pygame.SRCALPHA)
    shape = pygame.Surface((w, h), pygame.SRCALPHA)
    x = 0
    for s, _ in parts:
        shape.blit(s, (x, 0))
        x += s.get_width()
    ink = kit.dilate(kit.pad(shape, o), o, P.INK, square=True)
    out.blit(ink, (0, 0))
    x = o
    for s, color in parts:
        out.blit(kit.tint(s, color), (x, o))
        # a pale highlight along the top of each letter, as the HUD's bars have
        hi = kit.tint(s, kit.lerp(color, P.WHITE, 0.45))
        out.blit(hi, (x, o), (0, 0, s.get_width(), max(1, scale)))
        x += s.get_width()
    return out


def art(size: int) -> pygame.Surface:
    h, fist = hero()
    big = kit.nearest(h, ZOOM)
    pos = (round(size / 2 - big.get_width() / 2), round(size * 0.035))
    impact = (pos[0] + fist[0] * ZOOM, pos[1] + fist[1] * ZOOM)
    surf = panel(size, impact)
    # the puppets on top, with a thin ink drop shadow so they stand off the burst
    shadow = kit.tint(big, P.INK)
    shadow.set_alpha(150)
    surf.blit(shadow, (pos[0] + 10, pos[1] + 10))
    surf.blit(big, pos)
    # the title band along the bottom
    band = pygame.Rect(0, round(size * 0.74), size, round(size * 0.26))
    surf.fill(P.INK, band)
    surf.fill(P.CREAM, (0, band.y, size, 6))
    word = title(15)
    word = kit.fit(word, size - 80, band.h - 40, smooth=False) if word.get_width() > size - 80 else word
    kit.blit_center(surf, word, (size / 2, band.centery + 4))
    return surf


def marquee() -> pygame.Surface:
    return kit.trim(title(16))
