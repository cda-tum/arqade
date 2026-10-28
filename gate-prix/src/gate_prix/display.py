"""The fixed 960x540 internal surface, put on the real display.

Fullscreen (the cabinet) uses pygame's SCALED mode, so SDL does the exact x2 upscale onto
the 1920x1080 panel on the GPU. Windowed dev runs scale and blit by hand, because pygame
2.5.2's SCALED mode can't pick the window's size: a whole-number scale is a plain scale,
any other is smoothed (the art is smooth, not pixel art). Same approach as the sibling
games. In the browser the page scales the canvas, so the display is the internal size.
"""

from __future__ import annotations

import pygame
from arqade_common import runtime

from gate_prix.config import INTERNAL_HEIGHT, INTERNAL_WIDTH


def parse_size(text: str) -> tuple[int, int]:
    """'1440x810' -> (1440, 810)."""
    w, h = text.lower().split("x")
    return max(1, int(w)), max(1, int(h))


def compute_scaled_rect(internal_size: tuple[int, int], window_size: tuple[int, int]) -> pygame.Rect:
    """The largest rect of internal_size's aspect ratio that fits in window_size, centred."""
    iw, ih = internal_size
    ww, wh = window_size
    scale = min(ww / iw, wh / ih)
    sw, sh = round(iw * scale), round(ih * scale)
    return pygame.Rect((ww - sw) // 2, (wh - sh) // 2, sw, sh)


def make_display(fullscreen: bool, window_size: str) -> tuple[pygame.Surface, pygame.Surface | None]:
    """(the surface to draw on, the window or None). Fullscreen draws straight onto the
    SCALED display, so the window is None and `present` does nothing."""
    if runtime.is_browser():
        # The page scales the canvas to fit (by whole pixels where it can), so draw
        # straight onto a display of the internal size: no SCALED, no manual blit.
        return pygame.display.set_mode((INTERNAL_WIDTH, INTERNAL_HEIGHT)), None
    if fullscreen:
        surface = pygame.display.set_mode((INTERNAL_WIDTH, INTERNAL_HEIGHT),
                                          pygame.SCALED | pygame.FULLSCREEN)
        return surface, None
    window = pygame.display.set_mode(parse_size(window_size), pygame.RESIZABLE)
    return pygame.Surface((INTERNAL_WIDTH, INTERNAL_HEIGHT)), window


def present(internal: pygame.Surface, window: pygame.Surface | None) -> None:
    """Scale the internal surface onto the window, letterboxed. Nothing in fullscreen."""
    if window is None:
        return
    rect = compute_scaled_rect(internal.get_size(), window.get_size())
    if rect.size == internal.get_size():
        window.blit(internal, rect)
        return
    window.fill((0, 0, 0))
    whole = rect.w % internal.get_width() == 0 and rect.h % internal.get_height() == 0
    scale = pygame.transform.scale if whole else pygame.transform.smoothscale
    window.blit(scale(internal, rect.size), rect)
