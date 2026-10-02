"""Shared drawing helpers for the per-game logos (see generate_logos.py).

Everything here works on plain pygame Surfaces, so a game's logo module can
mix its own sprites (imported from the game's package) with these effects.
The look is borrowed from the ARQADE wordmark in ../../logos/: a gradient
fill, a thin black gap, then a white outline -- plus a hard extruded shadow
and a soft glow, which a pixel font carries well.
"""

from __future__ import annotations

import math
import os
from pathlib import Path

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")

import pygame  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
PIXEL_FONT = ROOT / "quantum-pong/src/quantum_pong/assets/fonts/PressStart2P-Regular.ttf"
BUNGEE_FONT = ROOT / "ion-surfer/src/ion_surfer/assets/fonts/Bungee-Regular.ttf"
RUBIK_FONT = ROOT / "ion-surfer/src/ion_surfer/assets/fonts/Rubik-Medium.ttf"

Color = tuple[int, int, int]


def lerp(a: Color, b: Color, t: float) -> Color:
    return tuple(round(x + (y - x) * t) for x, y in zip(a, b))


def shade(color: Color, factor: float) -> Color:
    return tuple(max(0, min(255, round(c * factor))) for c in color)


def gradient(size: tuple[int, int], stops: list[Color], vertical: bool = True) -> pygame.Surface:
    """A linear gradient through evenly spaced colour stops."""
    w, h = size
    surf = pygame.Surface(size, pygame.SRCALPHA)
    n = h if vertical else w
    for i in range(n):
        t = i / max(1, n - 1) * (len(stops) - 1)
        k = min(int(t), len(stops) - 2)
        c = lerp(stops[k], stops[k + 1], t - k) if len(stops) > 1 else stops[0]
        if vertical:
            pygame.draw.line(surf, c, (0, i), (w - 1, i))
        else:
            pygame.draw.line(surf, c, (i, 0), (i, h - 1))
    return surf


def tint(mask_surf: pygame.Surface, color: Color | pygame.Surface) -> pygame.Surface:
    """Recolour a shape (any surface with alpha) to a flat colour or a fill surface."""
    if isinstance(color, pygame.Surface):
        out = pygame.transform.scale(color, mask_surf.get_size()).convert_alpha()
    else:
        out = pygame.Surface(mask_surf.get_size(), pygame.SRCALPHA)
        out.fill((*color, 255))
    alpha = mask_surf.copy()
    alpha.fill((255, 255, 255, 0), special_flags=pygame.BLEND_RGBA_MAX)
    out.blit(alpha, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
    return out


def pad(surf: pygame.Surface, margin: int) -> pygame.Surface:
    out = pygame.Surface((surf.get_width() + 2 * margin, surf.get_height() + 2 * margin), pygame.SRCALPHA)
    out.blit(surf, (margin, margin))
    return out


def dilate(shape: pygame.Surface, radius: int, color: Color, square: bool = False) -> pygame.Surface:
    """`shape` grown by `radius` px in a flat colour (same size as `shape`).

    `square` grows it into hard corners, which suits a pixel font.
    """
    solid = tint(shape, color)
    if square:
        row = pygame.Surface(shape.get_size(), pygame.SRCALPHA)
        for dx in range(-radius, radius + 1):
            row.blit(solid, (dx, 0))
        out = pygame.Surface(shape.get_size(), pygame.SRCALPHA)
        for dy in range(-radius, radius + 1):
            out.blit(row, (0, dy))
        return out
    out = pygame.Surface(shape.get_size(), pygame.SRCALPHA)
    r2 = radius * radius
    for dy in range(-radius, radius + 1):
        for dx in range(-radius, radius + 1):
            if dx * dx + dy * dy <= r2 + radius:
                out.blit(solid, (dx, dy))
    return out


def blur(surf: pygame.Surface, radius: int) -> pygame.Surface:
    """Soft blur: halve the image step by step, then double it back up.

    Smoothscaling in one big jump leaves visible blocks; going in halves
    approximates a gaussian well enough for glows.
    """
    w, h = surf.get_size()
    sizes = [(w, h)]
    f = 1
    while f * 2 <= max(1, radius):
        f *= 2
        sizes.append((max(1, w // f), max(1, h // f)))
    out = surf
    for size in sizes[1:]:
        out = pygame.transform.smoothscale(out, size)
    for size in reversed(sizes[:-1]):
        out = pygame.transform.smoothscale(out, size)
    return out


def glow(shape: pygame.Surface, color: Color, radius: int, strength: float = 1.0) -> pygame.Surface:
    """A soft halo in `color` around `shape` (same size; pad the shape first)."""
    halo = blur(dilate(shape, max(1, radius // 4), color), radius)
    if strength != 1.0:
        a = pygame.Surface(halo.get_size(), pygame.SRCALPHA)
        a.fill((255, 255, 255, max(0, min(255, round(255 * strength)))))
        halo.blit(a, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
    return halo


def text_shape(text: str, font_path: Path | str, size: int, pixel: bool | None = None,
               tracking: int = 0) -> pygame.Surface:
    """White text with alpha. Pixel fonts render unsmoothed at a multiple of 8 px."""
    if pixel is None:
        pixel = Path(font_path) == PIXEL_FONT
    if pixel:
        native = pygame.font.Font(str(font_path), 8)
        k = max(1, round(size / 8))
        glyphs = [native.render(ch, False, (255, 255, 255)) for ch in text]
        w = sum(g.get_width() for g in glyphs) + tracking * (len(glyphs) - 1)
        line = pygame.Surface((w, native.get_height()), pygame.SRCALPHA)
        x = 0
        for g in glyphs:
            line.blit(g, (x, 0))
            x += g.get_width() + tracking
        return pygame.transform.scale(line, (line.get_width() * k, line.get_height() * k))
    font = pygame.font.Font(str(font_path), size)
    if not tracking:
        return font.render(text, True, (255, 255, 255))
    glyphs = [font.render(ch, True, (255, 255, 255)) for ch in text]
    w = sum(g.get_width() for g in glyphs) + tracking * (len(glyphs) - 1)
    line = pygame.Surface((w, font.get_height()), pygame.SRCALPHA)
    x = 0
    for g in glyphs:
        line.blit(g, (x, 0))
        x += g.get_width() + tracking
    return line


def wordmark(
    shape: pygame.Surface,
    fill: list[Color] | Color,
    *,
    vertical: bool = True,
    gap: int = 4,
    outline: int = 5,
    outline_color: Color = (255, 255, 255),
    extrude: int = 0,
    extrude_color: Color | None = None,
    glow_color: Color | None = None,
    glow_radius: int = 28,
    glow_strength: float = 0.9,
    highlight: bool = True,
    square: bool = False,
) -> pygame.Surface:
    """ARQADE-style lettering from a white `shape` (text_shape() or any sprite).

    Layers, bottom to top: glow, extruded 3D shadow, white outline, black
    gap, gradient-filled letters with a light sheen across the top half.
    Pass `square=True` for a pixel font so the outline keeps hard corners.
    """
    margin = gap + outline + extrude + (glow_radius * 2 if glow_color else 0) + 4
    s = pad(shape, margin)
    out = pygame.Surface(s.get_size(), pygame.SRCALPHA)
    ring = dilate(s, gap + outline, outline_color, square) if outline else None
    edge = dilate(s, gap, (0, 0, 0), square) if gap else None
    base = ring or edge or s
    if glow_color:
        out.blit(glow(base, glow_color, glow_radius, glow_strength), (0, 0))
    if extrude:
        ec = extrude_color or shade(fill if isinstance(fill, tuple) else fill[-1], 0.35)
        solid = tint(base, ec)
        for i in range(extrude, 0, -1):
            out.blit(tint(base, shade(ec, 0.75 + 0.25 * (1 - i / extrude))) if i == 1 else solid, (i, i))
    if ring:
        out.blit(ring, (0, 0))
    if edge:
        out.blit(edge, (0, 0))
    # gradient spans the letters, not the padding
    bbox = s.get_bounding_rect()
    paint = pygame.Surface(s.get_size(), pygame.SRCALPHA)
    paint.blit(gradient(bbox.size, fill if isinstance(fill, list) else [fill, fill], vertical), bbox.topleft)
    letters = tint(s, paint)
    if highlight:
        sheen = pygame.Surface(s.get_size(), pygame.SRCALPHA)
        sheen.fill((255, 255, 255, 70), pygame.Rect(0, bbox.top, s.get_width(), round(bbox.height * 0.42)))
        sheen.blit(s, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
        letters.blit(sheen, (0, 0))
    out.blit(letters, (0, 0))
    return trim(out)


def trim(surf: pygame.Surface, margin: int = 0) -> pygame.Surface:
    r = surf.get_bounding_rect().inflate(2 * margin, 2 * margin)
    out = pygame.Surface(r.size, pygame.SRCALPHA)
    out.blit(surf, (0, 0), r)
    return out


def fit(surf: pygame.Surface, max_w: int, max_h: int, smooth: bool = True) -> pygame.Surface:
    k = min(max_w / surf.get_width(), max_h / surf.get_height())
    size = (max(1, round(surf.get_width() * k)), max(1, round(surf.get_height() * k)))
    return (pygame.transform.smoothscale if smooth else pygame.transform.scale)(surf, size)


def tagline(text: str, size: int = 22, color: Color = (230, 235, 255),
            font_path: Path | str = RUBIK_FONT, tracking: int = 6) -> pygame.Surface:
    """Small spaced-out caps line, like 'MUNICH QUANTUM' on the ARQADE logo."""
    return tint(text_shape(text.upper(), font_path, size, pixel=False, tracking=tracking), color)


# --- backgrounds --------------------------------------------------------------


def radial(size: tuple[int, int], center: tuple[float, float], radius: float,
           color: Color, strength: float = 1.0) -> pygame.Surface:
    """An additive radial light; blit with special_flags=pygame.BLEND_ADD."""
    surf = pygame.Surface(size)
    steps = 48
    for i in range(steps, 0, -1):
        t = i / steps
        f = (1 - t) ** 2 * strength
        pygame.draw.circle(surf, shade(color, f), center, radius * t)
    return blur(surf, 6)


def vignette(size: tuple[int, int], strength: float = 0.75) -> pygame.Surface:
    """Darkening towards the corners; blit with special_flags=pygame.BLEND_MULT."""
    w, h = size
    small = pygame.Surface((64, 64))
    for y in range(64):
        for x in range(64):
            d = math.hypot((x - 31.5) / 32, (y - 31.5) / 32) / math.sqrt(2)
            v = 1 - strength * max(0.0, d - 0.25) / 0.75
            small.set_at((x, y), shade((255, 255, 255), v))
    return pygame.transform.smoothscale(small, (w, h))


def scanlines(size: tuple[int, int], every: int = 4, darkness: float = 0.82) -> pygame.Surface:
    """CRT scanlines; blit with special_flags=pygame.BLEND_MULT."""
    surf = pygame.Surface(size)
    surf.fill((255, 255, 255))
    for y in range(0, size[1], every):
        pygame.draw.line(surf, shade((255, 255, 255), darkness), (0, y), (size[0], y))
    return surf


def finish(surf: pygame.Surface, *, vignette_strength: float = 0.7, scan: bool = False) -> pygame.Surface:
    """Vignette and (optionally) faint scanlines. Run it on the background
    scene *before* the wordmark goes on, so the lettering stays clean."""
    out = surf.convert()
    if vignette_strength:
        out.blit(vignette(out.get_size(), vignette_strength), (0, 0), special_flags=pygame.BLEND_MULT)
    if scan:
        out.blit(scanlines(out.get_size()), (0, 0), special_flags=pygame.BLEND_MULT)
    return out


def blit_center(dst: pygame.Surface, src: pygame.Surface, center: tuple[float, float]) -> pygame.Rect:
    r = src.get_rect(center=(round(center[0]), round(center[1])))
    dst.blit(src, r)
    return r


def nearest(surf: pygame.Surface, k: int) -> pygame.Surface:
    """Integer upscale for pixel art."""
    return pygame.transform.scale(surf, (surf.get_width() * k, surf.get_height() * k))
