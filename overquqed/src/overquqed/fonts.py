"""Bundled pixel font (Press Start 2P, OFL-licensed), same as the sibling
games. Its native size is 8 px; use multiples of 8 so glyphs stay crisp.

Missing from this font (they render as an invisible box): the ket bracket
U+27E9, the superscripts U+207A/B and the Unicode minus. `ket.py` draws those
as pixel art instead. Greek capitals (Phi, Psi) are present. See
assets/fonts/OFL.txt for the license.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import pygame

_FONT_PATH = Path(__file__).parent / "assets" / "fonts" / "PressStart2P-Regular.ttf"


@lru_cache(maxsize=None)
def load_font(size: int) -> pygame.font.Font:
    return pygame.font.Font(str(_FONT_PATH), size)


_text_cache: dict[tuple, pygame.Surface] = {}


def text(s: str, size: int = 8, color=(255, 255, 255), shadow=None) -> pygame.Surface:
    """Rendered (non-antialiased) text, cached. `shadow` adds a 1 px drop
    shadow in that colour, which keeps small text readable on busy tiles."""
    key = (s, size, color, shadow)
    surf = _text_cache.get(key)
    if surf is None:
        if len(_text_cache) > 2000:
            _text_cache.clear()
        font = load_font(size)
        fg = font.render(s, False, color)
        if shadow is None:
            surf = fg
        else:
            surf = pygame.Surface((fg.get_width() + 1, fg.get_height() + 1), pygame.SRCALPHA)
            surf.blit(font.render(s, False, shadow), (1, 1))
            surf.blit(fg, (0, 0))
        _text_cache[key] = surf
    return surf
