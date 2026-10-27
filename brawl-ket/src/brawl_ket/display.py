"""Fixed internal-resolution rendering, scaled onto the real display.

Fullscreen (the cabinet) uses pygame's SCALED mode, so SDL does the x3
upscale on the GPU (nearest-neighbour, set in main.py). Windowed dev mode
scales and blits manually, because pygame 2.5.2's SCALED mode has no way to
pick the window size. Same approach as the sibling games.
"""

from __future__ import annotations

import pygame
from arqade_common import runtime

from brawl_ket.config import INTERNAL_HEIGHT, INTERNAL_WIDTH


def compute_scaled_rect(
    internal_size: tuple[int, int], window_size: tuple[int, int]
) -> pygame.Rect:
    """Largest rect of internal_size's aspect ratio that fits in window_size, centered."""
    internal_w, internal_h = internal_size
    window_w, window_h = window_size
    scale = min(window_w / internal_w, window_h / internal_h)
    scaled_w = round(internal_w * scale)
    scaled_h = round(internal_h * scale)
    return pygame.Rect((window_w - scaled_w) // 2, (window_h - scaled_h) // 2, scaled_w, scaled_h)


def make_display(fullscreen: bool, window_size: str) -> tuple[pygame.Surface, pygame.Surface | None]:
    """Returns (surface_to_draw_on, window_or_None). In fullscreen the surface
    is what gets presented, so window is None and present() is a no-op."""
    if runtime.is_browser():
        # The page scales the canvas to fit (pixelated), so draw straight
        # onto a display of the internal size: no SCALED, no manual blit.
        return pygame.display.set_mode((INTERNAL_WIDTH, INTERNAL_HEIGHT)), None
    if fullscreen:
        surface = pygame.display.set_mode(
            (INTERNAL_WIDTH, INTERNAL_HEIGHT), pygame.SCALED | pygame.FULLSCREEN
        )
        return surface, None
    width_str, height_str = window_size.lower().split("x")
    window = pygame.display.set_mode((int(width_str), int(height_str)), pygame.RESIZABLE)
    return pygame.Surface((INTERNAL_WIDTH, INTERNAL_HEIGHT)), window


def present(internal_surface: pygame.Surface, window: pygame.Surface | None) -> None:
    """Scale internal_surface onto window, letterboxed. No-op in fullscreen."""
    if window is None:
        return
    rect = compute_scaled_rect(internal_surface.get_size(), window.get_size())
    window.fill((0, 0, 0))
    window.blit(pygame.transform.scale(internal_surface, rect.size), rect)
