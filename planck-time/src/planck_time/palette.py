"""The Game Boy Advance-style palette. The GBA's screen was 15-bit (5 bits
per channel), so every channel here is a multiple of 8. Microgames, cards
and screens all pick their colours from this one list, which is what keeps
twelve different microgames looking like one game."""

from __future__ import annotations

from functools import lru_cache

INK = (24, 16, 40)  # outlines and the darkest shadows
NIGHT = (40, 32, 72)
SLATE = (72, 72, 112)
MIST = (168, 168, 200)
WHITE = (248, 248, 248)
CREAM = (248, 232, 192)

GOLD = (248, 200, 48)
ORANGE = (240, 136, 40)
GOOD = (88, 208, 104)  # success
GOOD_DARK = (40, 136, 72)
BAD = (232, 64, 72)  # failure
SKY = (96, 168, 248)
TEAL = (64, 200, 192)
PINK = (240, 120, 184)
VIOLET = (152, 96, 232)

# The gate colours, shared with Gate Drop and Pauli Invaders.
GATE = {"X": (232, 64, 72), "Y": (168, 80, 216), "Z": (56, 120, 232), "H": (248, 192, 40)}

# Two-tone background tiles; each microgame picks one pair.
BACKDROPS = (
    ((48, 56, 136), (64, 72, 160)),  # blue
    ((96, 48, 120), (120, 64, 144)),  # purple
    ((32, 96, 104), (40, 120, 128)),  # teal
    ((120, 72, 40), (144, 96, 56)),  # brown
    ((40, 104, 64), (56, 128, 80)),  # green
    ((128, 48, 72), (152, 64, 88)),  # wine
)


@lru_cache(maxsize=4096)
def shade(color, k: float) -> tuple[int, int, int]:
    """Darker (k < 1) or brighter, snapped back onto the 15-bit grid."""
    return tuple(max(0, min(248, round(c * k / 8) * 8)) for c in color)


@lru_cache(maxsize=4096)
def lighten(color, k: float) -> tuple[int, int, int]:
    return tuple(max(0, min(248, round((c + (248 - c) * k) / 8) * 8)) for c in color)
