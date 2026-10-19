"""Bundled pixel font (Press Start 2P, OFL-licensed; see assets/fonts/OFL.txt),
for the same crisp text on every host."""

from __future__ import annotations

from pathlib import Path

import pygame

_FONT_PATH = Path(__file__).parent / "assets" / "fonts" / "PressStart2P-Regular.ttf"


def load_font(size: int) -> pygame.font.Font:
    return pygame.font.Font(str(_FONT_PATH), size)
