"""Bundled assets: the pixel font (Press Start 2P, OFL-licensed; see assets/fonts/OFL.txt),
for the same crisp text on every host, and images."""

from __future__ import annotations

from pathlib import Path

import pygame

_FONT_PATH = Path(__file__).parent / "assets" / "fonts" / "PressStart2P-Regular.ttf"


def load_font(size: int) -> pygame.font.Font:
    return pygame.font.Font(str(_FONT_PATH), size)


def load_image(name: str) -> pygame.Surface:
    """A bundled image from assets/ (no conversion: it may load before a display exists)."""
    return pygame.image.load(str(Path(__file__).parent / "assets" / name))
