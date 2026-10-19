"""The item icons, one per item, for the HUD's slot, the first-pickup tip and the box reveal.

Each is a rounded tile in the item's colour with one picture on it, drawn at 4x in vector
shapes and smoothscaled down once per size (on first use, at start-up: `Renderer` asks for
every size it draws), so per frame an icon is a single blit:

- SPLIT: two overlapping car silhouettes, the second the clone's pale cyan;
- QEC: a shield with a check mark;
- MEASURE: a meter, its needle swung over onto a dot;
- TUNNEL: a see-through car passing through a brick wall;
- DECOHERENCE: a static cloud with a crackle through it.
"""

from __future__ import annotations

import math
import random

import pygame

from gate_prix import config

SS = 4
WHITE = (255, 255, 255)
INK = (10, 10, 20)
COLOURS = {"SPLIT": (170, 230, 255), "QEC": (120, 230, 160), "MEASURE": (255, 200, 90),
           "TUNNEL": (200, 170, 255), "DECOHERENCE": (180, 160, 210)}

_CACHE: dict[tuple[str, int], pygame.Surface] = {}


def mix(a, b, k):
    return tuple(round(x + (y - x) * k) for x, y in zip(a, b))


def _car(s, cx, cy, w, col, alpha=255):
    """A car from behind, as a silhouette: body, cabin, wing and wheels."""
    h = w * 0.42
    lay = pygame.Surface(s.get_size(), pygame.SRCALPHA)
    body = [(cx - w / 2, cy + h / 2), (cx - w * 0.42, cy - h * 0.05), (cx - w * 0.24, cy - h * 0.35),
            (cx + w * 0.24, cy - h * 0.35), (cx + w * 0.42, cy - h * 0.05), (cx + w / 2, cy + h / 2)]
    pygame.draw.polygon(lay, (*col, alpha), body)
    pygame.draw.rect(lay, (*mix(col, WHITE, 0.4), alpha),
                     (round(cx - w / 2), round(cy - h * 0.62), round(w), max(2, round(h * 0.16))))
    for sx in (-1, 1):
        pygame.draw.rect(lay, (*INK, alpha), (round(cx + sx * w * 0.42 - w * 0.08), round(cy + h * 0.25),
                                              round(w * 0.16), round(h * 0.34)))
        pygame.draw.rect(lay, (255, 70, 80, alpha), (round(cx + sx * w * 0.26 - w * 0.07),
                                                     round(cy + h * 0.05), round(w * 0.14), round(h * 0.13)))
    s.blit(lay, (0, 0))


def _split(s, n, col):
    _car(s, n * 0.6, n * 0.56, n * 0.56, (170, 230, 255), 170)
    _car(s, n * 0.4, n * 0.5, n * 0.56, (80, 170, 255))


def _qec(s, n, col):
    c = n / 2
    pts = [(c, n * 0.14), (n * 0.8, n * 0.26), (n * 0.76, n * 0.56), (c, n * 0.88),
           (n * 0.24, n * 0.56), (n * 0.2, n * 0.26)]
    pygame.draw.polygon(s, mix(col, INK, 0.45), pts)
    inner = [(c + (x - c) * 0.8, n * 0.5 + (y - n * 0.5) * 0.8) for x, y in pts]
    pygame.draw.polygon(s, col, inner)
    pygame.draw.lines(s, WHITE, False, [(n * 0.34, n * 0.5), (n * 0.46, n * 0.63), (n * 0.68, n * 0.36)],
                      max(2, round(n * 0.09)))


def _measure(s, n, col):
    cx, cy, r = n / 2, n * 0.66, n * 0.36
    rect = pygame.Rect(round(cx - r), round(cy - r), round(2 * r), round(2 * r))
    pygame.draw.arc(s, col, rect, 0, math.pi, max(2, round(n * 0.07)))
    for k in range(7):
        a = math.pi * k / 6
        pygame.draw.line(s, mix(col, WHITE, 0.5), (cx + r * 0.72 * math.cos(a), cy - r * 0.72 * math.sin(a)),
                         (cx + r * 0.88 * math.cos(a), cy - r * 0.88 * math.sin(a)), max(1, round(n * 0.025)))
    a = math.radians(38)  # the needle, collapsed over to one side
    tip = (cx + r * 0.95 * math.cos(a), cy - r * 0.95 * math.sin(a))
    pygame.draw.line(s, WHITE, (cx, cy), tip, max(2, round(n * 0.05)))
    pygame.draw.circle(s, WHITE, (round(cx), round(cy)), max(2, round(n * 0.06)))
    pygame.draw.circle(s, (255, 90, 96), (round(tip[0]), round(tip[1])), max(2, round(n * 0.07)))


def _tunnel(s, n, col):
    brick = (150, 92, 60)
    x0, x1 = n * 0.44, n * 0.6
    for row in range(6):
        y = n * (0.16 + row * 0.12)
        off = (row % 2) * n * 0.04
        pygame.draw.rect(s, brick, (round(x0 - off), round(y), round(x1 - x0), round(n * 0.1)))
        pygame.draw.rect(s, mix(brick, WHITE, 0.3), (round(x0 - off), round(y), round(x1 - x0), round(n * 0.1)),
                         max(1, round(n * 0.015)))
    _car(s, n * 0.5, n * 0.52, n * 0.6, col, 150)
    for k in range(3):  # its shimmer
        y = n * (0.42 + 0.08 * k)
        pygame.draw.line(s, (240, 230, 255), (n * 0.24, y), (n * 0.76, y), max(1, round(n * 0.02)))


def _decoherence(s, n, col):
    body = (150, 80, 190)
    lay = pygame.Surface(s.get_size(), pygame.SRCALPHA)
    for bx, by, br in ((0.34, 0.56, 0.16), (0.52, 0.44, 0.2), (0.68, 0.56, 0.15), (0.5, 0.6, 0.16)):
        pygame.draw.circle(lay, (*mix(body, col, 0.4), 235), (round(bx * n), round(by * n)), round(br * n))
    s.blit(lay, (0, 0))
    pts = [(0.4, 0.44), (0.5, 0.56), (0.46, 0.6), (0.6, 0.74)]
    pygame.draw.lines(s, (255, 190, 245), False, [(x * n, y * n) for x, y in pts], max(2, round(n * 0.04)))
    rnd = random.Random(5)
    for _ in range(12):
        pygame.draw.circle(s, WHITE, (round(rnd.uniform(0.24, 0.78) * n), round(rnd.uniform(0.32, 0.72) * n)),
                           max(1, round(n * 0.015)))


_PICTURES = {"SPLIT": _split, "QEC": _qec, "MEASURE": _measure, "TUNNEL": _tunnel,
             "DECOHERENCE": _decoherence}


def icon(item: str, size: int) -> pygame.Surface:
    """The item's icon, size pixels square (built once per size)."""
    key = (item, size)
    img = _CACHE.get(key)
    if img is None:
        n = size * SS
        s = pygame.Surface((n, n), pygame.SRCALPHA)
        col = COLOURS[item]
        rad = round(n * 0.2)
        pygame.draw.rect(s, (14, 16, 32), s.get_rect(), border_radius=rad)
        pygame.draw.rect(s, mix(col, INK, 0.55), s.get_rect().inflate(-n * 0.08, -n * 0.08),
                         border_radius=rad)
        pygame.draw.rect(s, col, s.get_rect(), max(2, round(n * 0.05)), border_radius=rad)
        _PICTURES[item](s, n, col)
        img = pygame.transform.smoothscale(s, (size, size))
        _CACHE[key] = img
    return img


def build(sizes) -> None:
    """Every item's icon at these sizes, now (at start-up)."""
    for item in config.ITEMS:
        for size in sizes:
            icon(item, size)
