"""Fixed internal-resolution rendering, scaled onto the real display.

Fullscreen (the actual cabinet) uses pygame's SCALED display mode: pygame/SDL
does the upscale itself, hardware-accelerated where the platform supports it
(confirmed: Batocera's Pi builds use a real renderer backend, unlike this
project's headless dev/test environment, which falls back to "no fast
renderer available" and can't exercise that acceleration -- the API
correctness is verified here, the hardware speedup isn't). This replaces a
manual `pygame.transform.scale()` blit every frame, which was a real, sizeable
per-frame CPU cost on a Pi 4 upscaling ~130K to ~2M pixels in software.

Windowed dev mode keeps the old manual scale+blit path instead, since it
needs a specific initial window size (`--window-size`) that pygame 2.5.2's
SCALED mode has no API to set directly, and performance isn't a concern for
local testing.
"""

from __future__ import annotations

import pygame

from error_invaders.config import INTERNAL_HEIGHT, INTERNAL_WIDTH


def compute_scaled_rect(
    internal_size: tuple[int, int], window_size: tuple[int, int]
) -> pygame.Rect:
    """Largest rect of internal_size's aspect ratio that fits in window_size, centered."""
    internal_w, internal_h = internal_size
    window_w, window_h = window_size
    scale = min(window_w / internal_w, window_h / internal_h)
    scaled_w = round(internal_w * scale)
    scaled_h = round(internal_h * scale)
    x = (window_w - scaled_w) // 2
    y = (window_h - scaled_h) // 2
    return pygame.Rect(x, y, scaled_w, scaled_h)


def make_internal_surface() -> pygame.Surface:
    return pygame.Surface((INTERNAL_WIDTH, INTERNAL_HEIGHT))


def make_display(fullscreen: bool, window_size: str) -> tuple[pygame.Surface, pygame.Surface | None]:
    """Set up the display. Returns (surface_to_draw_on, window_or_None).

    Fullscreen: SDL scales for us: the returned surface is both what to draw
    on and what gets presented, so `window` is None and `present()` becomes a
    no-op -- there's nothing left to manually blit/scale.

    Windowed: returns a separate low-res `surface` to draw on and the actual
    `window`; `present()` does the manual scale+blit as before.
    """
    if fullscreen:
        surface = pygame.display.set_mode(
            (INTERNAL_WIDTH, INTERNAL_HEIGHT), pygame.SCALED | pygame.FULLSCREEN
        )
        return surface, None

    width_str, height_str = window_size.lower().split("x")
    window = pygame.display.set_mode((int(width_str), int(height_str)), pygame.RESIZABLE)
    return make_internal_surface(), window


def present(internal_surface: pygame.Surface, window: pygame.Surface | None) -> None:
    """Scale internal_surface onto window, letterboxed. No-op if window is
    None (SCALED fullscreen mode already draws directly to the real display)."""
    if window is None:
        return
    rect = compute_scaled_rect(internal_surface.get_size(), window.get_size())
    window.fill((0, 0, 0))
    scaled = pygame.transform.scale(internal_surface, (rect.width, rect.height))
    window.blit(scaled, rect)
