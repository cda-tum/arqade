"""Brawl-Ket: the clash, as a comic-book impact panel.

The hero is the game's one rule, colour must match to hurt, in one hit: P1's
BOHR (on the left, its blue player ring under it), the big armoured fighter,
is green, in the Z basis, and lands a heavy, its other colour, square on the
upper chest of P2's ROBERT (on the right, its red ring under it). ROBERT is
purple, in the X basis, so the purple hit matches and ROBERT reels back. The
two stand a fighter's reach apart: only the fist meets. (It is BOHR that
hits because it is the taller: ROBERT's strikes can only reach BOHR's middle,
which reads wrong.) Both are the game's own puppets, drawn by its own
draw_puppet from its own poses at the game's pixel size and scaled up
nearest-neighbour, with the game's striker glow and hit spark in purple.
Behind them is the look none of the other icons has: a comic panel split on
the diagonal into each player's side, with halftone dots and speed lines
bursting out of the impact. BRAWL-KET sits below in the game's thick ink
outline, in the fighters' own colours as they stand: BRAWL in BOHR's green,
KET in ROBERT's purple, and the hyphen white, belonging to neither.
"""

from __future__ import annotations

import math
import sys

import kit
import pygame

sys.path.insert(0, str(kit.ROOT / "brawl-ket/src"))
from brawl_ket import palette as P  # noqa: E402
from brawl_ket.config import PLAYER_COLORS  # noqa: E402
from brawl_ket.moves import BOHR, ROBERT  # noqa: E402
from brawl_ket.poses import POSES, joints  # noqa: E402
from brawl_ket.render import ACCENT, GREEN, PURPLE, draw_puppet  # noqa: E402

ROM = "brawl_ket"
BLUE, RED = PLAYER_COLORS["p1"], PLAYER_COLORS["p2"]
ZOOM = 4                    # game px -> icon px
NATIVE = (260, 200)         # the hero's canvas, in game px (cropped to the puppets)
FLOOR = 196
CHEST = 0.62                # where on ROBERT the fist lands: 0 hip .. 1 neck
REACH = 18                  # game px from the fist to ROBERT's spine: they stand apart


def hero() -> tuple[pygame.Surface, tuple[int, int]]:
    """The two puppets at game resolution on transparency, cropped to them, and
    where the fist lands."""
    s = pygame.Surface(NATIVE, pygame.SRCALPHA)
    bohr_at = (60, FLOOR)
    # ROBERT stands where BOHR's fist meets its chest, a little in from its front
    fist0 = joints(POSES["heavy_hit"], BOHR.build, bohr_at, 1)["hand_f"]
    t = joints(POSES["hitstun"], ROBERT.build, (0, FLOOR), -1)
    chest_x = t["hip"][0] + (t["neck"][0] - t["hip"][0]) * CHEST
    robert_at = (round(fist0[0] - chest_x + REACH), FLOOR)
    # the players' rings under their feet (Renderer._shadow): P1 blue, P2 red
    for x, colour in ((bohr_at[0], BLUE), (robert_at[0], RED)):
        ring = pygame.Rect(0, 0, 60, 12)
        ring.center = (x, FLOOR + 2)
        pygame.draw.ellipse(s, P.INK, ring.inflate(2, 2), 3)
        pygame.draw.ellipse(s, colour, ring, 2)
    # ROBERT first, behind: the one being hit, purple (the X basis)
    draw_puppet(s, POSES["hitstun"], ROBERT.build, robert_at, -1, PURPLE, ACCENT["ROBERT"])
    # BOHR green (the Z basis); its heavy is the other colour, purple
    j = draw_puppet(s, POSES["heavy_hit"], BOHR.build, bohr_at, 1, GREEN, ACCENT["BOHR"])
    fist = (round(j["hand_f"][0]) + 3, round(j["hand_f"][1]))
    # the striker glow and the game's hit spark (Renderer._striker, _draw_effects), purple
    pygame.draw.circle(s, P.INK, fist, 10)
    pygame.draw.circle(s, P.WHITE, fist, 8)
    pygame.draw.circle(s, PURPLE, fist, 5)
    pygame.draw.circle(s, P.WHITE, fist, 2)
    box = s.get_bounding_rect()
    return s.subsurface(box).copy(), (fist[0] - box.x, fist[1] - box.y)


def burst(center, r_in: float, r_out: float, points: int, color, phase: float = 0.0) -> list:
    pts = []
    for i in range(points * 2):
        a = phase + math.pi * i / points
        r = r_out if i % 2 == 0 else r_in
        pts.append((center[0] + r * math.cos(a), center[1] + r * math.sin(a)))
    return pts


def panel(size: int | tuple[int, int], impact: tuple[float, float], k: float = 1.0,
          reach: float | None = None) -> pygame.Surface:
    """The comic panel: each player's side of a diagonal split, halftone dots
    growing towards the impact, and speed lines bursting out of it. `size` is
    a side, or (width, height); `k` scales the dots, lines and burst, which
    are sized for puppets at ZOOM. The dots fade out `reach` px from the
    impact (by default 3/4 of the longer side)."""
    W, H = (size, size) if isinstance(size, int) else size
    surf = pygame.Surface((W, H))
    surf.fill(P.INK)
    left = kit.shade(BLUE, 0.42)
    right = kit.shade(RED, 0.42)
    # the split runs through the impact, leaning like a punch landing
    lean = 0.35
    top_x = impact[0] + impact[1] * lean
    bottom_x = impact[0] - (H - impact[1]) * lean
    pygame.draw.polygon(surf, left, [(0, 0), (top_x, 0), (bottom_x, H), (0, H)])
    pygame.draw.polygon(surf, right, [(top_x, 0), (W, 0), (W, H), (bottom_x, H)])
    # halftone: dots on a 45-degree grid, bigger near the impact
    dots = pygame.Surface((W, H), pygame.SRCALPHA)
    step = round(26 * k)
    reach = reach or max(W, H) * 0.75
    for gy in range(-1, H // step + 2):
        for gx in range(-1, W // step + 2):
            x = gx * step + (step // 2 if gy % 2 else 0)
            y = gy * step
            d = math.hypot(x - impact[0], y - impact[1])
            r = 11 * k * max(0.0, 1 - d / reach)
            if r >= 1.5:
                side = left if x < impact[0] + (impact[1] - y) * lean else right
                pygame.draw.circle(dots, (*kit.shade(side, 1.7), 255), (x, y), round(r))
    surf.blit(dots, (0, 0))
    # speed lines from the impact out to the edges
    lines = pygame.Surface((W, H), pygame.SRCALPHA)
    for i in range(28):
        a = 2 * math.pi * i / 28 + (0.05 if i % 2 else -0.04)
        r0, r1 = (150 + (i % 3) * 30) * k, max(W, H)
        w = round((10 if i % 3 == 0 else 5) * k)
        p0 = (impact[0] + r0 * math.cos(a), impact[1] + r0 * math.sin(a))
        p1 = (impact[0] + r1 * math.cos(a), impact[1] + r1 * math.sin(a))
        pygame.draw.line(lines, (*P.CREAM, 70), p0, p1, w)
    surf.blit(lines, (0, 0))
    # the impact burst, in the comic's POW colours: a cream star over an ink one
    pygame.draw.polygon(surf, P.INK, burst(impact, 96 * k, 190 * k, 12, P.INK, 0.1))
    pygame.draw.polygon(surf, P.GOLD, burst(impact, 84 * k, 170 * k, 12, P.GOLD, 0.1))
    pygame.draw.polygon(surf, P.CREAM, burst(impact, 60 * k, 120 * k, 12, P.CREAM, 0.36))
    return surf


def title(scale: int) -> pygame.Surface:
    """BRAWL-KET in a thick ink outline (and room for a shadow, which the
    marquee's transparency needs), in the fighters' colours as they stand:
    BRAWL in BOHR's green, KET in ROBERT's purple, and the hyphen white."""
    parts = [(kit.text_shape(text, kit.PIXEL_FONT, 8 * scale), color)
             for text, color in (("BRAWL", GREEN), ("-", P.WHITE), ("KET", PURPLE))]
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


def art(size: int, pad: int = 0) -> pygame.Surface:
    """The square logo, `size` px; with `pad`, on a canvas `pad` px bigger on
    every side, the panel and the title band running on (see generate_logos.py: extended/)."""
    full = size + 2 * pad
    h, fist = hero()
    big = kit.nearest(h, ZOOM)
    pos = (pad + round(size / 2 - big.get_width() / 2), pad + round(size * 0.035))
    impact = (pos[0] + fist[0] * ZOOM, pos[1] + fist[1] * ZOOM)
    surf = panel(full, impact, reach=size * 0.75)
    # the puppets on top, with a thin ink drop shadow so they stand off the burst
    shadow = kit.tint(big, P.INK)
    shadow.set_alpha(150)
    surf.blit(shadow, (pos[0] + 10, pos[1] + 10))
    surf.blit(big, pos)
    # the title band along the bottom
    band = pygame.Rect(0, pad + round(size * 0.74), size, round(size * 0.26))
    surf.fill(P.INK, (0, band.y, full, full - band.y))
    surf.fill(P.CREAM, (0, band.y, full, 6))
    word = title(15)
    word = kit.fit(word, size - 80, band.h - 40, smooth=False) if word.get_width() > size - 80 else word
    kit.blit_center(surf, word, (full / 2, band.centery + 4))
    return surf


def wide(width: int, height: int) -> pygame.Surface:
    """The same panel opened out sideways: the clash in the middle, the
    split, halftone and speed lines running out to both sides, and the
    title band along the bottom."""
    W, H = 1024, 512
    zoom = 2  # the whole of both puppets, rings and all, above the band
    k = zoom / ZOOM  # the panel's dots, lines and burst shrink with them
    h, fist = hero()
    big = kit.nearest(h, zoom)
    band = pygame.Rect(0, H - 150, W, 150)
    content = h.get_bounding_rect()
    pos = (round(W / 2 - big.get_width() / 2), 20 - content.top * zoom)
    impact = (pos[0] + fist[0] * zoom, pos[1] + fist[1] * zoom)
    surf = panel((W, H), impact, k)
    shadow = kit.tint(big, P.INK)
    shadow.set_alpha(150)
    surf.blit(shadow, (pos[0] + round(10 * k), pos[1] + round(10 * k)))
    surf.blit(big, pos)
    surf.fill(P.INK, band)
    surf.fill(P.CREAM, (0, band.y, W, max(3, round(6 * k))))
    word = title(11)
    visible = H - round(H * 0.04)  # ES trims a little off the bottom
    kit.blit_center(surf, word, (W / 2, (band.y + visible) / 2 + 3))
    return surf if (width, height) == (W, H) else pygame.transform.smoothscale(surf, (width, height))


def marquee() -> pygame.Surface:
    return kit.trim(title(16))
