"""Bundled pixel font (Press Start 2P, OFL-licensed) for consistent, crisp
text at the game's low internal resolution -- same approach as Quantum Pong.
Note: this font's Unicode angle-bracket glyphs (U+27E8/E9) are missing (they
silently render as an invisible box), which is why notation.py uses ASCII
"|0>" style kets instead. See assets/fonts/OFL.txt for the license.
"""

from __future__ import annotations

from pathlib import Path

import pygame

_FONT_PATH = Path(__file__).parent / "assets" / "fonts" / "PressStart2P-Regular.ttf"


def load_font(size: int, bold: bool = False) -> pygame.font.Font:
    font = pygame.font.Font(str(_FONT_PATH), size)
    if bold:
        font.set_bold(True)
    return font
