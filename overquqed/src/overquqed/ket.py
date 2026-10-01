"""Proper ket labels like |Φ⁺⟩ in the bundled pixel font.

Press Start 2P has Φ and Ψ (checked by rendering and hashing the glyph
bitmaps) but no ⟩ bracket and no superscripts, so those are drawn here as
pixel masks. Everything is composed at the font's native 8 px, tightly
cropped, given a 1 px dark outline for readability on any background, and
integer-scaled (nearest) for the bigger ticket kets -- so a ket looks
identical at every size, just chunkier.
"""

from __future__ import annotations

import pygame

from overquqed import palette
from overquqed.fonts import load_font

_BRACKET = [  # the closing angle bracket, 2 px stroke like the font
    "#...",
    "##..",
    ".##.",
    "..##",
    ".##.",
    "##..",
    "#...",
]
_BAR = ["##"] * 7
_SUP_PLUS = [".#.", "###", ".#."]
_SUP_MINUS = ["...", "###", "..."]
_MINUS = ["......", "......", "......", ".####.", ".####.", "......", "......"]  # padded so |-> never reads as an arrow

# token -> (base text, superscript or None)
_TOKEN_PARTS = {
    "Phi+": ("Φ", "+"), "Phi-": ("Φ", "-"),
    "Psi+": ("Ψ", "+"), "Psi-": ("Ψ", "-"),
    "GHZ": ("GHZ", None), "GHZ-": ("GHZ", "-"),
}


def ascii_ket(tokens: tuple[str, ...], prefix: str = "") -> str:
    """Plain-ASCII form, e.g. ~|Phi+> (logs, tests)."""
    return f"{prefix}|{''.join(tokens)}>"


def token_color(tokens: tuple[str, ...]) -> tuple[int, int, int]:
    """Colour by meaning: |0> blue, |1> orange, |+> green, |-> purple,
    entangled states gold, unknown grey. Products take their first bowl's."""
    first = tokens[0]
    if first == "?":
        return palette.NOISE
    if len(tokens) > 1 or first in _TOKEN_PARTS:
        return palette.GOLD
    return {"0": palette.KET_0, "1": palette.KET_1, "+": palette.KET_PLUS, "-": palette.KET_MINUS}[first]


def _mask_surface(rows: list[str], color) -> pygame.Surface:
    surf = pygame.Surface((len(rows[0]), len(rows)), pygame.SRCALPHA)
    for y, row in enumerate(rows):
        for x, ch in enumerate(row):
            if ch == "#":
                surf.set_at((x, y), color)
    return surf


def _glyphs(s: str, color) -> pygame.Surface:
    """Font text cropped to its ink, keeping the 8 px line box vertically."""
    font = load_font(8)
    out = []
    for ch in s:
        g = font.render(ch, False, color)
        r = g.get_bounding_rect()
        out.append(g.subsurface(pygame.Rect(r.x, 0, r.width, 7)).copy())
    width = sum(g.get_width() for g in out) + max(0, len(out) - 1)
    surf = pygame.Surface((width, 7), pygame.SRCALPHA)
    x = 0
    for g in out:
        surf.blit(g, (x, 0))
        x += g.get_width() + 1
    return surf


def _outline(inner: pygame.Surface, color) -> pygame.Surface:
    w, h = inner.get_size()
    mask = pygame.mask.from_surface(inner)
    shadow = mask.to_surface(setcolor=color, unsetcolor=(0, 0, 0, 0))
    out = pygame.Surface((w + 2, h + 2), pygame.SRCALPHA)
    for dx in (0, 1, 2):
        for dy in (0, 1, 2):
            if (dx, dy) != (1, 1):
                out.blit(shadow, (dx, dy))
    out.blit(inner, (1, 1))
    return out


_cache: dict[tuple, pygame.Surface] = {}


def ket_surface(
    tokens: tuple[str, ...],
    prefix: str = "",
    scale: int = 1,
    color=None,
    outline=palette.INK,
) -> pygame.Surface:
    key = (tokens, prefix, scale, color, outline)
    surf = _cache.get(key)
    if surf is not None:
        return surf
    color = color or token_color(tokens)

    pieces: list[tuple[pygame.Surface, int]] = []  # (surface, y offset)
    if prefix:
        pieces.append((_glyphs(prefix, color), 0))
    pieces.append((_mask_surface(_BAR, color), 0))
    if tokens == ("?",):
        pieces.append((_glyphs("?", color), 0))
    else:
        for tok in tokens:
            base, sup = _TOKEN_PARTS.get(tok, (tok, None))
            if base == "-":
                pieces.append((_mask_surface(_MINUS, color), 0))
            else:
                pieces.append((_glyphs(base, color), 0))
            if sup is not None:
                pieces.append((_mask_surface(_SUP_PLUS if sup == "+" else _SUP_MINUS, color), -1))
    pieces.append((_mask_surface(_BRACKET, color), 0))

    width = sum(p.get_width() for p, _ in pieces) + len(pieces) - 1
    inner = pygame.Surface((width, 8), pygame.SRCALPHA)
    x = 0
    for p, dy in pieces:
        inner.blit(p, (x, 1 + dy))
        x += p.get_width() + 1
    surf = _outline(inner, outline) if outline is not None else inner
    if scale != 1:
        surf = pygame.transform.scale(surf, (surf.get_width() * scale, surf.get_height() * scale))
    if len(_cache) > 800:
        _cache.clear()
    _cache[key] = surf
    return surf
