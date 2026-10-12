"""The little 2D pictures the 3D scene uses, drawn with pygame into one
texture atlas: Gate Drop's error bugs, the gate glyphs, the item boxes, a
soft shadow, a ring, smoke and flame. The renderer stands them up as
billboards (bugs, glyphs, items) or lays them on the track (shadows, rings).
"""

from __future__ import annotations

import pygame

from qircuit import config

INK = config.COLOR_INK
WHITE = (255, 255, 255)


def shade(c, k: float):
    return tuple(max(0, min(255, int(v * k))) for v in c)


def lighten(c, k: float):
    return tuple(int(v + (255 - v) * k) for v in c)


def bug(font: pygame.font.Font, kind: str, frame: int) -> pygame.Surface:
    """Gate Drop's grumpy Pauli-error bug in its gate's colour: angry eyes on
    top, shuffling legs, and its letter in dark ink on its back."""
    size = 16
    color = config.GATE_COLORS[kind]
    leg = shade(color, 0.55)
    s = pygame.Surface((size, size), pygame.SRCALPHA)
    bob = frame
    for i, ly in enumerate((8, 11, 14)):
        step = (i + frame) % 2
        s.fill(leg, (0, ly - step, 2, 1))
        s.fill(leg, (size - 2, ly - 1 + step, 2, 1))
    body = pygame.Rect(1, 4 + bob, 14, 12 - bob)
    pygame.draw.ellipse(s, INK, body)
    pygame.draw.ellipse(s, shade(color, 0.75), body.inflate(-2, -2))
    back = body.inflate(-2, -4)
    back.y = body.y + 1
    pygame.draw.ellipse(s, lighten(color, 0.15), back)
    for ex in (5, 10):
        pygame.draw.circle(s, INK, (ex, 3 + bob), 3)
        pygame.draw.circle(s, WHITE, (ex, 3 + bob), 2)
        s.fill(INK, (ex + (1 if ex < 8 else -1), 3 + bob, 1, 2))
    s.fill(INK, (3, 0 + bob, 3, 1))
    s.fill(INK, (10, 0 + bob, 3, 1))
    img = font.render(kind, False, INK)
    s.blit(img, img.get_rect(center=(size // 2 + 1, 10 + bob)))
    return s


def _item(kind: str) -> pygame.Surface:
    s = pygame.Surface((18, 18), pygame.SRCALPHA)
    s.fill(INK)
    if kind == "err":
        pygame.draw.rect(s, config.GATE_COLORS["X"], s.get_rect(), 2)
        pygame.draw.line(s, config.GATE_COLORS["Z"], (2, 15), (15, 15), 2)
        pygame.draw.circle(s, config.GATE_COLORS["X"], (9, 10), 4)
        s.fill(WHITE, (7, 7, 1, 1))
        s.fill(WHITE, (10, 7, 1, 1))
    else:
        pygame.draw.rect(s, config.COLOR_ZENO, s.get_rect(), 2)
        s.fill(WHITE, (6, 5, 2, 8))
        s.fill(WHITE, (10, 5, 2, 8))
    return s


def _glyph(kind: str) -> pygame.Surface:
    s = pygame.Surface((16, 16), pygame.SRCALPHA)
    c = config.CNOT_COLOR
    if kind == "swap":
        for a, b in (((2, 2), (13, 13)), ((2, 13), (13, 2))):
            pygame.draw.line(s, INK, a, b, 5)
            pygame.draw.line(s, c, a, b, 3)
    elif kind == "control":
        pygame.draw.circle(s, INK, (8, 8), 6)
        pygame.draw.circle(s, c, (8, 8), 5)
    else:  # target: a circled plus
        pygame.draw.circle(s, lighten(c, 0.5), (8, 8), 7)
        pygame.draw.circle(s, INK, (8, 8), 7, 1)
        s.fill(INK, (3, 8, 11, 1))
        s.fill(INK, (8, 3, 1, 11))
    return s


def _soft(size: int, inner: float, color=(0, 0, 0)) -> pygame.Surface:
    s = pygame.Surface((size, size), pygame.SRCALPHA)
    r = size / 2
    for y in range(size):
        for x in range(size):
            d = ((x + 0.5 - r) ** 2 + (y + 0.5 - r) ** 2) ** 0.5 / r
            a = 0 if d >= 1 else (255 if d < inner else int(255 * (1 - (d - inner) / (1 - inner))))
            s.set_at((x, y), (*color, a))
    return s


def _ring(size: int) -> pygame.Surface:
    s = pygame.Surface((size, size), pygame.SRCALPHA)
    pygame.draw.ellipse(s, (255, 255, 255, 70), s.get_rect())
    pygame.draw.ellipse(s, (255, 255, 255, 255), s.get_rect(), 3)
    return s


class Atlas:
    """Every picture in one surface, and where each one is (as uv)."""

    def __init__(self, font: pygame.font.Font) -> None:
        pieces = {
            "shadow": _soft(32, 0.35),
            "ring": _ring(32),
            "smoke": _soft(16, 0.2, (210, 210, 220)),
            "flame": _soft(16, 0.3, (255, 190, 80)),
            "item_err": _item("err"),
            "item_zeno": _item("zeno"),
            "swap": _glyph("swap"),
            "control": _glyph("control"),
            "target": _glyph("target"),
        }
        for kind in "XZ":
            for frame in (0, 1):
                pieces[f"bug_{kind}_{frame}"] = bug(font, kind, frame)
        self.surface = pygame.Surface((128, 128), pygame.SRCALPHA)
        self.uv: dict[str, tuple[float, float, float, float]] = {}
        x = y = row = 0
        for name, img in pieces.items():
            w, h = img.get_size()
            if x + w > 128:
                x, y, row = 0, y + row + 1, 0
            self.surface.blit(img, (x, y))
            self.uv[name] = (x / 128, y / 128, (x + w) / 128, (y + h) / 128)
            x += w + 1
            row = max(row, h)
