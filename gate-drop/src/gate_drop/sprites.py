"""Procedural pixel sprites in the style of an SNES puzzle game: capsule halves
for gates, steel CNOT halves with the circuit symbols, grumpy error bugs.
Everything is drawn once at 16x16 and cached; nothing is anti-aliased, so it
stays crisp at the cabinet's x4 scale.

A joint is the side a half's partner sits on ("l", "r", "u", "d"), or None
for a loose half. The joined side is drawn square, so two halves read as one
capsule.
"""

from __future__ import annotations

import pygame

from gate_drop import config
from gate_drop.fonts import load_font

INK = config.COLOR_INK
WHITE = (255, 255, 255)
S = config.CELL


def shade(color, k: float) -> tuple[int, int, int]:
    return tuple(max(0, min(255, round(c * k))) for c in color)


def lighten(color, k: float) -> tuple[int, int, int]:
    return tuple(round(c + (255 - c) * k) for c in color)


# Tiny glyphs for the |q_n> wire labels: q (with its descender), a lowered
# digit for the subscript, and the closing ket bracket.
_GLYPH_Q = (".###.", "#..#.", "#..#.", ".###.", "...#.", "...##")  # the tail hook stops it reading as a 9
_GLYPH_DIGITS = (
    ("###", "#.#", "#.#", "#.#", "###"), (".#.", "##.", ".#.", ".#.", "###"),
    ("###", "..#", "###", "#..", "###"), ("###", "..#", "###", "..#", "###"),
    ("#.#", "#.#", "###", "..#", "..#"), ("###", "#..", "###", "..#", "###"),
)
_GLYPH_KET = ("#..", ".#.", ".#.", "..#", ".#.", ".#.", "#..")

_SQUARE = {"r": ("tr", "br"), "l": ("tl", "bl"), "u": ("tl", "tr"), "d": ("bl", "br"), None: ()}
_CORNERS = (("tl", "top_left"), ("tr", "top_right"), ("bl", "bottom_left"), ("br", "bottom_right"))


def _radii(joint, r: int) -> dict:
    square = _SQUARE[joint]
    return {f"border_{name}_radius": (0 if key in square else r) for key, name in _CORNERS}


def _capsule(color, joint) -> pygame.Surface:
    """One capsule half: an ink outline, a bright fill shading darker at the
    bottom, and a glint. On the joined side the fill runs to the edge."""
    s = pygame.Surface((S, S), pygame.SRCALPHA)
    pygame.draw.rect(s, INK, (0, 0, S, S), **_radii(joint, 7))
    inner = pygame.Rect(1, 1, S - 2, S - 2)
    if joint == "r":
        inner.width += 1
    elif joint == "l":
        inner.x, inner.width = 0, inner.width + 1
    elif joint == "d":
        inner.height += 1
    elif joint == "u":
        inner.y, inner.height = 0, inner.height + 1
    pygame.draw.rect(s, shade(color, 0.7), inner, **_radii(joint, 6))
    top = inner.copy()
    top.height -= 3
    pygame.draw.rect(s, color, top, **_radii(joint, 6))
    glint = lighten(color, 0.6)
    s.fill(glint, (3, 3, 3, 1))
    s.fill(glint, (3, 4, 1, 2))
    return s


class Sprites:
    def __init__(self) -> None:
        self.font = load_font(8)
        self._cache: dict = {}

    def _letter(self, s: pygame.Surface, text: str, centre: tuple[int, int], color=WHITE) -> None:
        img = self.font.render(text, False, color)
        rect = img.get_rect(center=centre)
        s.blit(self.font.render(text, False, INK), rect.move(1, 1))
        s.blit(img, rect)

    def gate(self, kind: str, joint=None) -> pygame.Surface:
        key = ("gate", kind, joint)
        if key not in self._cache:
            s = _capsule(config.GATE_COLORS[kind], joint)
            if kind == "Td":  # T-dagger: the font has no dagger, so draw one
                self._letter(s, "T", (S // 2 - 1, S // 2))
                for x, y, w, h in ((12, 2, 1, 7), (11, 4, 3, 1)):
                    s.fill(INK, (x + 1, y + 1, w, h))
                    s.fill(WHITE, (x, y, w, h))
            else:
                self._letter(s, kind, (S // 2 + 1, S // 2))
            self._cache[key] = s
        return self._cache[key]

    def cnot(self, role: str, joint: str) -> pygame.Surface:
        """A steel half with the circuit symbol: a dot for the control, a
        circled plus for the target, joined by the wire between them."""
        key = ("cnot", role, joint)
        if key not in self._cache:
            s = _capsule(config.CNOT_COLOR, joint)
            cx, cy = S // 2, S // 2 - 1
            if joint == "r":
                s.fill(INK, (cx, cy - 1, S - cx, 2))
            else:
                s.fill(INK, (0, cy - 1, cx, 2))
            if role == "c":
                pygame.draw.circle(s, INK, (cx, cy), 3)
            else:
                pygame.draw.circle(s, lighten(config.CNOT_COLOR, 0.5), (cx, cy), 5)
                pygame.draw.circle(s, INK, (cx, cy), 5, 1)
                s.fill(INK, (cx - 4, cy - 1, 9, 2))
                s.fill(INK, (cx - 1, cy - 4, 2, 9))
            self._cache[key] = s
        return self._cache[key]

    def bug(self, kind: str, frame: int) -> pygame.Surface:
        """A grumpy Pauli-error bug in its gate's colour: angry eyes on top,
        legs that shuffle between the two frames, and its letter in dark ink
        on its back (gates have white letters, so errors read differently)."""
        key = ("bug", kind, frame)
        if key not in self._cache:
            color = config.GATE_COLORS[kind]
            leg = shade(color, 0.55)
            s = pygame.Surface((S, S), pygame.SRCALPHA)
            bob = frame
            for i, ly in enumerate((8, 11, 14)):
                step = (i + frame) % 2
                s.fill(leg, (0, ly - step, 2, 1))
                s.fill(leg, (S - 2, ly - 1 + step, 2, 1))
            body = pygame.Rect(1, 4 + bob, 14, 12 - bob)
            pygame.draw.ellipse(s, INK, body)
            pygame.draw.ellipse(s, shade(color, 0.75), body.inflate(-2, -2))
            back = body.inflate(-2, -4)
            back.y = body.y + 1
            pygame.draw.ellipse(s, lighten(color, 0.15), back)
            for ex in (5, 10):  # eyes, with pupils looking inwards and angry brows
                pygame.draw.circle(s, INK, (ex, 3 + bob), 3)
                pygame.draw.circle(s, WHITE, (ex, 3 + bob), 2)
                s.fill(INK, (ex + (1 if ex < 8 else -1), 3 + bob, 1, 2))
            s.fill(INK, (3, 0 + bob, 3, 1))
            s.fill(INK, (10, 0 + bob, 3, 1))
            img = self.font.render(kind, False, INK)
            s.blit(img, img.get_rect(center=(S // 2 + 1, 10 + bob)))
            self._cache[key] = s
        return self._cache[key]

    def ket(self, wire: int, color) -> pygame.Surface:
        """|q_n>, the label under wire n, drawn in pixels to fit one 16 px column
        (the font's glyphs are 8 px each, and it has no ket bracket at all)."""
        key = ("ket", wire, color)
        if key not in self._cache:
            s = pygame.Surface((S, 7), pygame.SRCALPHA)
            parts = ((0, 0, ("#",) * 7), (2, 1, _GLYPH_Q), (8, 2, _GLYPH_DIGITS[wire]), (12, 0, _GLYPH_KET))
            for left, top, rows in parts:
                for y, row in enumerate(rows):
                    for x, bit in enumerate(row):
                        if bit == "#":
                            s.fill(color, (left + x, top + y, 1, 1))
            self._cache[key] = s
        return self._cache[key]

    def dot(self, kind: str) -> pygame.Surface:
        """A small round noise-gate icon for the incoming queue."""
        key = ("dot", kind)
        if key not in self._cache:
            color = config.GATE_COLORS[kind]
            s = pygame.Surface((10, 10), pygame.SRCALPHA)
            pygame.draw.circle(s, INK, (5, 5), 5)
            pygame.draw.circle(s, color, (5, 4), 3)
            s.fill(lighten(color, 0.6), (3, 2, 2, 1))
            self._cache[key] = s
        return self._cache[key]
