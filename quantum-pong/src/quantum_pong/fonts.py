"""Bundled pixel font (Press Start 2P, OFL-licensed) for consistent, crisp
text at the game's low internal resolution -- the default SysFont lookup
produced inconsistent, blurry-looking text depending on what's installed on
the host. See assets/fonts/OFL.txt for the license.
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
