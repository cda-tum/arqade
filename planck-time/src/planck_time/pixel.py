"""Pixel-art helpers shared by every microgame and screen: outlined text,
dithering, tiled backdrops, shaded orbs, gate cards, and the win/fail
overlay. All drawing is unantialiased, so it stays crisp at x3.

Fonts are loaded lazily, after pygame.init(), and cached.
"""

from __future__ import annotations

import math
import random
from functools import lru_cache

import pygame

from arqade_common import keycaps
from planck_time import palette as P
from planck_time.fonts import load_font

_FONTS: dict[int, pygame.font.Font] = {}

# What the controls are called on the screen being drawn: the renderer sets
# them before each player's screen, so a hint says "A" and "STICK" to a pad
# player and names the keys ("B", "WASD") to one on the keyboard ("keys" set;
# then also "up", "down", "left" and "right", the keys the stick stands for).
_BUTTONS = {"a": "A", "stick": "STICK", "keys": ""}


def button(name: str) -> str:
    """The on-screen name of "a" or "stick" for the player being drawn."""
    return _BUTTONS[name]


def set_buttons(names: dict[str, str]) -> None:
    _BUTTONS.update(names)


def on_keys() -> bool:
    """Whether the player being drawn is on the keyboard: then their keys are
    drawn as keycaps, never as the pad's stick or A button."""
    return bool(_BUTTONS["keys"])


KEY_COLORS = (P.CREAM, P.INK, P.INK)  # a keycap's face, edge and letter
KEY_LIT = P.GOLD  # the face of a key the demo is pressing


def draw_keycap(surf: pygame.Surface, name: str, size: int, topleft, lit: bool = False) -> pygame.Rect:
    """One key as a keycap in the game's colours, gold while pressed."""
    face, edge, ink = KEY_COLORS
    return keycaps.draw_keycap(surf, font(size), name, topleft, KEY_LIT if lit else face, edge, ink)


def control_hint(template: str, size: int, color, outline=P.INK, shadow: bool = True) -> pygame.Surface:
    """outlined() for a hint naming the controls, e.g. "{a} WHEN THEY MATCH":
    {a} and {stick} become the player's names for them, and on the keyboard
    the {a} key is a keycap, so "B" reads as the B key, not the pad's B button."""
    text = template.replace("{stick}", button("stick"))
    if not on_keys() or "{a}" not in text:
        return outlined(text.replace("{a}", button("a")), size, color, outline, shadow)
    pieces = text.split("{a}")
    w, h = keycaps.keycap_size(font(size), button("a"))
    parts: list[tuple[str, pygame.Surface | None, int]] = []  # (kind, image, gap before)
    for i, piece in enumerate(pieces):
        if i:
            parts.append(("key", None, 4 if pieces[i - 1].endswith(" ") else 1))
        if piece.strip():
            gap = 4 if i and piece.startswith(" ") else 1 if i else 0
            parts.append(("text", outlined(piece.strip(), size, color, outline, shadow), gap))
    height = max([h + 1] + [img.get_height() for _, img, _ in parts if img])
    width = sum(gap + (img.get_width() if img else w) for _, img, gap in parts)
    out = pygame.Surface((width, height), pygame.SRCALPHA)
    x = 0
    for kind, img, gap in parts:
        x += gap
        if img is None:
            x = draw_keycap(out, button("a"), size, (x, (height - h) // 2)).right
        else:
            out.blit(img, (x, (height - img.get_height()) // 2))
            x += img.get_width()
    return out


def font(size: int) -> pygame.font.Font:
    if size not in _FONTS:
        _FONTS[size] = load_font(size)
    return _FONTS[size]


@lru_cache(maxsize=1024)
def outlined(text: str, size: int, color, outline=P.INK, shadow: bool = True) -> pygame.Surface:
    """Text with a one-pixel outline (and a drop shadow), readable on any backdrop.
    Cached, since the same labels are drawn every frame: blit the result, never draw on it."""
    f = font(size)
    core = f.render(text, False, color)
    ink = f.render(text, False, outline)
    s = pygame.Surface((core.get_width() + 3, core.get_height() + 3), pygame.SRCALPHA)
    if shadow:
        s.blit(ink, (2, 3))
    for dx, dy in ((0, 1), (2, 1), (1, 0), (1, 2), (0, 0), (2, 0), (0, 2), (2, 2)):
        s.blit(ink, (dx, dy))
    s.blit(core, (1, 1))
    return s


def blit_center(surf: pygame.Surface, img: pygame.Surface, center) -> None:
    surf.blit(img, img.get_rect(center=(round(center[0]), round(center[1]))))


_DITHERS: dict = {}


def dither(surf: pygame.Surface, rect, c1, c2) -> None:
    """A two-colour checkerboard: the GBA way to shade with few colours.
    Each size and colour pair is drawn once, then blitted."""
    rect = pygame.Rect(rect)
    key = (rect.w, rect.h, rect.y & 1, tuple(c1), tuple(c2))
    patch = _DITHERS.get(key)
    if patch is None:
        patch = pygame.Surface(rect.size)
        patch.fill(c1)
        for y in range(rect.h):
            for x in range((y + rect.y) & 1, rect.w, 2):
                patch.set_at((x, y), c2)
        if len(_DITHERS) > 256:
            _DITHERS.clear()
        _DITHERS[key] = patch
    surf.blit(patch, rect)


_TILES: dict = {}


def backdrop(surf: pygame.Surface, colors, t: float, speed: float = 8.0) -> None:
    """A slowly scrolling 8x8 checker of two colours, behind every microgame.
    Drawn once per colour pair and size, then blitted at the scroll offset."""
    w, h = surf.get_size()
    key = (tuple(colors[0]), tuple(colors[1]), w, h)
    tiles = _TILES.get(key)
    if tiles is None:
        a, b = colors
        tiles = pygame.Surface((w + 16, h + 16))
        tiles.fill(a)
        for ty in range(0, h + 16, 8):
            for tx in range(0, w + 16, 8):
                if ((tx + ty) // 8) % 2 == 0:
                    tiles.fill(b, (tx, ty, 8, 8))
        _TILES[key] = tiles
    off = int(t * speed) % 16
    surf.blit(tiles, (off - 16, off - 16))


def orb(surf: pygame.Surface, center, r: int, color, glow: bool = False) -> None:
    """A shaded sphere: an ink outline, a dithered dark side, a highlight."""
    cx, cy = round(center[0]), round(center[1])
    if glow:
        pygame.draw.circle(surf, P.lighten(color, 0.5), (cx, cy), r + 3, 1)
    pygame.draw.circle(surf, P.INK, (cx, cy), r + 1)
    pygame.draw.circle(surf, P.shade(color, 0.7), (cx, cy), r)
    pygame.draw.circle(surf, color, (cx - r // 5, cy - r // 5), max(1, r - r // 4))
    hl = max(1, r // 4)
    pygame.draw.circle(surf, P.lighten(color, 0.7), (cx - r // 2, cy - r // 2), hl)


def card(surf: pygame.Surface, rect, color, letter: str = "", selected: bool = False) -> None:
    """A gate card: a rounded tile in the gate's colour with its letter."""
    rect = pygame.Rect(rect)
    if selected:
        pygame.draw.rect(surf, P.WHITE, rect.inflate(6, 6), border_radius=6)
    pygame.draw.rect(surf, P.INK, rect.inflate(2, 2), border_radius=5)
    pygame.draw.rect(surf, P.shade(color, 0.7), rect, border_radius=4)
    top = rect.copy()
    top.height -= 3
    pygame.draw.rect(surf, color, top, border_radius=4)
    surf.fill(P.lighten(color, 0.6), (rect.x + 3, rect.y + 3, 4, 1))
    if letter:
        blit_center(surf, outlined(letter, 16, P.WHITE, shadow=False), (rect.centerx + 1, rect.centery))


def result_overlay(surf: pygame.Surface, result: bool | None, since: float, seed: int = 0) -> None:
    """The shared win/fail juice, drawn on top of a finished microgame:
    confetti bursting out for a win, cracks and a red flash for a failure."""
    if result is None:
        return
    w, h = surf.get_size()
    rng = random.Random(seed)
    if result:
        for _ in range(28):
            angle = rng.uniform(0, 2 * math.pi)
            speed = rng.uniform(60, 150)
            x = w / 2 + math.cos(angle) * speed * since
            y = h / 2 + math.sin(angle) * speed * since + 90 * since * since
            color = rng.choice((P.GOLD, P.WHITE, P.GOOD, P.SKY, P.PINK))
            surf.fill(color, (round(x), round(y), 3, 2))
    else:
        if since < 0.12:
            flash = pygame.Surface((w, h), pygame.SRCALPHA)
            flash.fill((*P.BAD, 120))
            surf.blit(flash, (0, 0))
        for _ in range(4):
            x, y = rng.uniform(40, w - 40), rng.uniform(30, h - 30)
            for _ in range(5):
                nx, ny = x + rng.uniform(-26, 26), y + rng.uniform(-18, 18)
                pygame.draw.line(surf, P.INK, (x, y), (nx, ny), 2)
                pygame.draw.line(surf, P.WHITE, (x, y - 1), (nx, ny - 1), 1)
                x, y = nx, ny
