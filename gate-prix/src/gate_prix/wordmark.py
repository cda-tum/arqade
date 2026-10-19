"""The GATE PRIX wordmark over the title: the logo's lettering, drawn once at start-up.

As on the cabinet's logo (batocera/logos/logo_gate_prix.py, a motorsport livery): heavy
italic race lettering in the game's own font, white fading to ice blue, two speed cuts
through its lower third trailing off to the left, a dark ink outline with a hard gold drop
to the lower left, and the finish line's chequer under it, slanted with it and fading out to
the left. Plain pygame (the logo's kit is not on the cabinet), at 2x, smoothed down once.
"""

from __future__ import annotations

import math

import pygame

from gate_prix import config, road
from gate_prix.sprites import font

WHITE = (255, 255, 255)
ICE = (210, 228, 255)
INK = (8, 10, 24)
GOLD = config.GATE_COLORS["H"]
SLANT = 0.24  # the italic: each row shifted right by this times its height above the base
SS = 2


def _trim(surf: pygame.Surface) -> pygame.Surface:
    r = surf.get_bounding_rect()
    out = pygame.Surface(r.size, pygame.SRCALPHA)
    out.blit(surf, (0, 0), r)
    return out


def _pad(surf: pygame.Surface, margin: int) -> pygame.Surface:
    out = pygame.Surface((surf.get_width() + 2 * margin, surf.get_height() + 2 * margin),
                         pygame.SRCALPHA)
    out.blit(surf, (margin, margin))
    return out


def _tint(shape: pygame.Surface, fill: tuple | pygame.Surface) -> pygame.Surface:
    """The shape (its alpha) in a flat colour, or painted with a surface its size."""
    if isinstance(fill, pygame.Surface):
        out = fill.copy()
    else:
        out = pygame.Surface(shape.get_size(), pygame.SRCALPHA)
        out.fill((*fill, 255))
    alpha = shape.copy()
    alpha.fill((255, 255, 255, 0), special_flags=pygame.BLEND_RGBA_MAX)
    out.blit(alpha, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
    return out


def _dilate(shape: pygame.Surface, radius: int, col) -> pygame.Surface:
    """The shape grown by `radius` px in a flat colour (one mask convolution: fast)."""
    disc = pygame.mask.Mask((2 * radius + 1, 2 * radius + 1))
    for y in range(2 * radius + 1):
        for x in range(2 * radius + 1):
            if (x - radius) ** 2 + (y - radius) ** 2 <= radius * radius + radius:
                disc.set_at((x, y))
    grown = pygame.mask.from_surface(shape, 8).convolve(disc)
    out = pygame.Surface(shape.get_size(), pygame.SRCALPHA)
    out.blit(grown.to_surface(setcolor=(*col, 255), unsetcolor=(0, 0, 0, 0)), (-radius, -radius))
    return out


def _shear(surf: pygame.Surface, slant: float) -> pygame.Surface:
    w, h = surf.get_size()
    out = pygame.Surface((w + round(h * slant), h), pygame.SRCALPHA)
    for y in range(h):
        out.blit(surf, (round((h - y) * slant), y), (0, y, w, 1))
    return out


def _gradient(size, top, bottom) -> pygame.Surface:
    w, h = size
    s = pygame.Surface(size, pygame.SRCALPHA)
    for y in range(h):
        t = y / max(1, h - 1)
        pygame.draw.line(s, tuple(round(a + (b - a) * t) for a, b in zip(top, bottom)), (0, y), (w, y))
    return s


def _chequer(width: int, rows: int, cell: int) -> pygame.Surface:
    cols = math.ceil(width / cell)
    s = pygame.Surface((cols * cell, rows * cell), pygame.SRCALPHA)
    for j in range(rows):
        for i in range(cols):
            pygame.draw.rect(s, road.CHEQUER[(i + j) % 2], (i * cell, j * cell, cell, cell))
    fade = pygame.Surface(s.get_size(), pygame.SRCALPHA)
    for x in range(fade.get_width()):
        a = round(255 * min(1.0, x / fade.get_width() / 0.45) ** 1.3)
        pygame.draw.line(fade, (255, 255, 255, a), (x, 0), (x, fade.get_height()))
    s.blit(fade, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
    return s


def build(width: int) -> pygame.Surface:
    """The wordmark, `width` px wide."""
    px = round(width * 0.29) * SS
    shape = _trim(font(px).render("GATE PRIX", True, WHITE))
    tw, th = shape.get_size()
    lead = round(th * 0.9)  # room on the left for the speed cuts' tails
    letters = pygame.Surface((tw + lead, th), pygame.SRCALPHA)
    letters.blit(shape, (lead, 0))
    cuts = ((0.70, 0.045), (0.83, 0.045))  # under the bowls of P and R: no sliver is left
    lines = pygame.Surface(letters.get_size(), pygame.SRCALPHA)
    for k, (cy, ch) in enumerate(cuts):
        y, hh = round(th * cy), max(2, round(th * ch))
        letters.fill((0, 0, 0, 0), (lead, y, tw, hh))
        length = round(lead * (0.95 - 0.3 * k))
        for x in range(length):
            a = round(255 * (x / length) ** 1.5)
            pygame.draw.line(lines, (255, 255, 255, a), (lead - length + x, y),
                             (lead - length + x, y + hh - 1))
    margin = round(th * 0.14)
    body = _pad(letters, margin)
    outline = _dilate(body, max(2, round(th * 0.042)), INK)
    out = pygame.Surface(body.get_size(), pygame.SRCALPHA)
    d = max(2, round(th * 0.065))
    out.blit(_tint(outline, GOLD), (-d // 2, d))
    out.blit(outline, (0, 0))
    out.blit(_tint(body, _gradient(body.get_size(), WHITE, ICE)), (0, 0))
    out.blit(_pad(lines, margin), (0, 0))
    out = _shear(out, SLANT)
    cell = max(2, round(th * 0.13))
    flag = _pad(_chequer(round(tw * 1.02), 2, cell), margin)
    flag = _shear(flag, SLANT)
    total = pygame.Surface((max(out.get_width(), flag.get_width() + lead) + 20,
                            out.get_height() + flag.get_height()), pygame.SRCALPHA)
    total.blit(flag, (lead - round(flag.get_height() * SLANT * 0.5) - 20,
                      out.get_height() - margin - 6))
    total.blit(out, (0, 0))
    total = _trim(total)
    k = width / total.get_width()
    return pygame.transform.smoothscale(total, (width, max(1, round(total.get_height() * k))))
