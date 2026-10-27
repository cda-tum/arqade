"""Planck Time app icon: a handheld mid-microgame, its fuse lit, as a sticker.

The look is a sheet of die-cut vinyl stickers, the kind a party game comes
with: the hero and the title are each cut out with a thick white border and
a soft shadow, and stuck onto the title screen's purple checker. The hero is
the game's one rule in one picture: P1's handheld playing MEASURE! at the
instant its needle swings into the |1> zone, which lights up green, while the
fuse under the screen burns down and its spark lights up the shell.

Everything is the game's own: the handheld is render.make_bezel in P1's blue
with the power LED where Renderer._handheld puts it; its screen is
microgames.measure.Measure drawing itself at the frame the needle enters the
zone, on the plain NIGHT an empty screen is filled with (its checker
backdrop and caption line taken out, so the dial and the fuse carry the
icon); and the fuse and its sparks are Renderer._fuse itself. All of it is
drawn at the game's 300x200 and scaled up whole (by x3, the cabinet's own). The
checker is Renderer.title_tiles. The title follows Renderer._logo: every
letter outlined in ink by pixel.outlined, coloured in the game's own cycle
(the X and H gate colours, green, the Z and Y gate colours, pink), riding its
wave, and ending in its stopwatch -- built at the font's native 8 px and
upscaled whole, so it stays legible on a small tile.

The wide tile is the same sheet turned landscape: the handheld at x2 on the
left and the title, stacked into two lines, stuck on beside it. The marquee
is the title sticker alone.
"""

from __future__ import annotations

import math
import random
import sys

import kit
import pygame

sys.path.insert(0, str(kit.ROOT / "planck-time/src"))

from planck_time import config, render  # noqa: E402
from planck_time import palette as P  # noqa: E402
from planck_time.microgames.base import PlayerInput  # noqa: E402
from planck_time.microgames.measure import Measure  # noqa: E402
from planck_time.pixel import outlined  # noqa: E402

ROM = "planck_time"

SW, SH = config.SCREEN_W, config.SCREEN_H  # one GBA screen, 240x160
SCREEN_AT = (30, 18)  # where render.Renderer._handheld puts the screen in the bezel
FUSE_AT = (30, 18 + SH + 6)  # ...and the fuse under it
LED_AT = (14, 34)
SEED = 5  # which MEASURE! round: it only sets the needle's exact speed
FUSE_LEFT = 0.42  # of the play time: the fuse burns orange from here down to a quarter
TITLE_TILES = ((64, 40, 120), (80, 48, 144))  # render.Renderer.title_tiles
TITLE_COLORS = (P.GATE["X"], P.GATE["H"], P.GOOD, P.GATE["Z"], P.GATE["Y"], P.PINK)  # as _logo cycles them
WAVE_T = 0.3  # the moment of the title's wave (render._logo's self.t)
SPARK_FRAMES = 5  # the fuse's sparks over a few frames, as the eye sees them


# --- the hero -------------------------------------------------------------------------


def screen() -> pygame.Surface:
    """MEASURE! at the frame its needle first swings into the zone round |1>,
    which lights up green: the instant to press A."""
    game = Measure(SEED, 0, config.PLAY_TIME)
    while not game.in_zone:
        game.update(1 / 60, PlayerInput())
    surf = pygame.Surface((SW, SH))
    game.draw(surf)
    # its checker backdrop swapped for an empty screen's NIGHT, and its
    # caption line ("A WHEN IT POINTS AT |1>") cleared
    pixels = pygame.PixelArray(surf)
    for tile in game.backdrop:
        pixels.replace(tile, P.NIGHT)
    pixels.close()
    surf.fill(P.NIGHT, (0, SH - 20, SW, 20))
    return surf


def handheld() -> tuple[pygame.Surface, tuple[int, int]]:
    """P1's handheld at the game's own size (300x200), MEASURE! on its screen
    and its fuse burning, and where the fuse's spark is."""
    hh = pygame.Surface((render.BEZEL_W, render.BEZEL_H), pygame.SRCALPHA)
    hh.blit(render.make_bezel(config.PLAYER_COLORS["p1"]), (0, 0))
    hh.blit(screen(), SCREEN_AT)
    pygame.draw.circle(hh, P.INK, LED_AT, 3)  # the power LED, as _handheld draws it
    pygame.draw.circle(hh, P.shade(P.BAD, 0.8), LED_AT, 2)
    r = render.Renderer.__new__(render.Renderer)  # only _fuse's own state, no window
    r.surface, r.t, r.rng = hh, 0.0, random.Random(4)
    for _ in range(SPARK_FRAMES):
        r._fuse(FUSE_LEFT, True, *FUSE_AT)  # a game in play
    spark = (FUSE_AT[0] + round(SW * FUSE_LEFT), FUSE_AT[1] + 2)
    return hh, spark


# --- the title ------------------------------------------------------------------------


# render._logo's stopwatch -- an ink ring, a cream face, an ink crown on top and a
# red hand racing round -- redrawn on the 8 px letters' pixel grid (the game
# draws it with circles at 32 px, which come out lumpy this small).
STOPWATCH = (
    "....ooo....",
    "....ooo....",
    "...ooooo...",
    ".ooCCCCCoo.",
    ".oCCCCCCCo.",
    "oCCCCCCRCCo",
    "oCCCCCRCCCo",
    "oCCCCRCCCCo",
    "oCCCCCCCCCo",
    "oCCCCCCCCCo",
    ".oCCCCCCCo.",
    ".ooCCCCCoo.",
    "...ooooo...",
)


def stopwatch() -> pygame.Surface:
    """The stopwatch, at native size (11x13)."""
    return render.bitmap(STOPWATCH, {"o": P.INK, "C": P.CREAM, "R": P.BAD})


def line(text: str, start: int = 0, watch: bool = False) -> pygame.Surface:
    """Letters as render._logo draws them, at the font's native 8 px: each
    outlined in ink, in the next colour of the cycle (counting from `start`,
    spaces included) and lifted by the wave; then, if `watch`, the stopwatch,
    centred on the letters as _logo centres it."""
    out = pygame.Surface((8 * len(text) + 16, 24), pygame.SRCALPHA)
    for k, ch in enumerate(text):
        i = start + k
        if ch == " ":
            continue
        y = 5 - round(math.sin(WAVE_T * 4 + i * 0.6))
        out.blit(outlined(ch, 8, TITLE_COLORS[i % len(TITLE_COLORS)]), (k * 8, y))
    if watch:
        # the letters' middle is 4 px down their 8 px cell; the face's is row 7
        out.blit(stopwatch(), (8 * len(text) + 3, 5 + 1 + 4 - 7))
    return kit.trim(fill_gaps(out))


def fill_gaps(surf: pygame.Surface) -> pygame.Surface:
    """Ink in the one-pixel gaps the 8 px outlines leave in and between
    letters (the C's mouth, round the I's serifs), so the sticker's white
    doesn't show through them: a closing of the shape with a 3x3 square."""
    w, h = surf.get_size()
    solid = {(x, y) for y in range(h) for x in range(w) if surf.get_at((x, y)).a}
    near = [(dx, dy) for dy in (-1, 0, 1) for dx in (-1, 0, 1)]
    grown = {(x + dx, y + dy) for x, y in solid for dx, dy in near}
    for y in range(h):
        for x in range(w):
            if (x, y) not in solid and all((x + dx, y + dy) in grown for dx, dy in near):
                surf.set_at((x, y), P.INK)
    return surf


def title() -> pygame.Surface:
    """PLANCK TIME and the stopwatch, on one line, at native size."""
    return line("PLANCK TIME", watch=True)


def title_stacked() -> pygame.Surface:
    """PLANCK over TIME and the stopwatch, for the wide tile; every letter keeps
    its colour and wave from the one-line title."""
    top, bottom = line("PLANCK"), line("TIME", start=7, watch=True)
    lead = 1  # close enough that the two lines make one sticker
    w = max(top.get_width(), bottom.get_width())
    out = pygame.Surface((w, top.get_height() + lead + bottom.get_height()), pygame.SRCALPHA)
    out.blit(top, ((w - top.get_width()) // 2, 0))
    out.blit(bottom, ((w - bottom.get_width()) // 2, top.get_height() + lead))
    return out


# --- the sticker sheet ----------------------------------------------------------------


def sticker(img: pygame.Surface, border: int, shadow: tuple[int, int] = (8, 12)) -> tuple[pygame.Surface, int]:
    """`img` cut out with a white border and a soft shadow under it. Returns the
    sticker and its margin (where `img`'s top-left sits inside it)."""
    margin = border + 28
    shape = kit.pad(img, margin)
    cut = kit.dilate(shape, border, P.WHITE)
    out = pygame.Surface(shape.get_size(), pygame.SRCALPHA)
    soft = kit.blur(kit.tint(cut, P.INK), 12)
    fade = pygame.Surface(soft.get_size(), pygame.SRCALPHA)
    fade.fill((255, 255, 255, 140))
    soft.blit(fade, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
    out.blit(soft, shadow)
    out.blit(cut, (0, 0))
    out.blit(shape, (0, 0))
    return out, margin


def sheet(size: tuple[int, int], tile: int) -> pygame.Surface:
    """The title screen's purple checker."""
    surf = pygame.Surface(size)
    surf.fill(TITLE_TILES[0])
    for ty in range(0, size[1], tile):
        for tx in range(0, size[0], tile):
            if (tx // tile + ty // tile) % 2 == 0:
                surf.fill(TITLE_TILES[1], (tx, ty, tile, tile))
    return surf


# --- the three images -----------------------------------------------------------------

K = 3  # hero: one game pixel is K x K icon pixels, the cabinet's own x3
TK = 9  # title: one font pixel is TK x TK
BORDER = 14  # the sticker's white cut line, in icon px
LIGHT = (96, 64, 176)  # a soft light on the sheet behind the handheld


def lay_out(surf: pygame.Surface, hero_at: tuple[int, int], k: int, title_img: pygame.Surface,
            title_at: tuple[int, int], border: int, shadow: tuple[int, int]) -> pygame.Surface:
    """The sheet with the handheld (scaled by `k`, top-left at `hero_at`) and
    the title stuck on, and the fuse's spark lighting both."""
    hh, spark = handheld()
    big = kit.nearest(hh, k)
    hero, hm = sticker(big, border, shadow)
    label, lm = sticker(title_img, border - 2, shadow)
    w, h = surf.get_size()
    hx, hy = hero_at
    surf.blit(kit.radial((w, h), (hx + big.get_width() / 2, hy + big.get_height() / 2), 0.62 * w, LIGHT, 0.45),
              (0, 0), special_flags=pygame.BLEND_ADD)
    surf = kit.finish(surf, vignette_strength=0.5)
    surf.blit(hero, (hx - hm, hy - hm))
    surf.blit(kit.radial((w, h), (hx + spark[0] * k, hy + spark[1] * k), 40 * k, P.ORANGE, 1.0), (0, 0),
              special_flags=pygame.BLEND_ADD)
    surf.blit(label, (title_at[0] - lm, title_at[1] - lm))
    return surf


def art(size: int, pad: int = 0) -> pygame.Surface:
    """The square logo, `size` px; with `pad`, on a canvas `pad` px bigger on
    every side, the checker running on (see generate_logos.py: extended/)."""
    S = 1024
    E = S + 2 * pad
    word = kit.nearest(title(), TK)
    hero_w, hero_h = render.BEZEL_W * K, render.BEZEL_H * K
    gap = 56
    top = pad + (S - (word.get_height() + gap + hero_h)) // 2
    surf = lay_out(sheet((E, E), 16 * K), ((E - hero_w) // 2, top + word.get_height() + gap), K,
                   word, ((E - word.get_width()) // 2, top), BORDER, (8, 12))
    return surf if size == S else pygame.transform.smoothscale(surf, (round(E * size / S),) * 2)


def wide(width: int, height: int) -> pygame.Surface:
    """The same sheet turned landscape: the handheld sticker on the left at
    x2, and the title, stacked into two lines, stuck on beside it."""
    W, H = 1024, 512
    k, tk = 2, 6
    word = kit.nearest(title_stacked(), tk)
    hero_w, hero_h = render.BEZEL_W * k, render.BEZEL_H * k
    gap = 22  # between the handheld and the title, inside their white borders
    left = (W - (hero_w + gap + word.get_width())) // 2
    surf = lay_out(sheet((W, H), 16 * k), (left, (H - hero_h) // 2), k,
                   word, (left + hero_w + gap, (H - word.get_height()) // 2), BORDER - 4, (6, 9))
    return surf if (width, height) == (W, H) else pygame.transform.smoothscale(surf, (width, height))


def marquee() -> pygame.Surface:
    """The title sticker on transparency."""
    label, _ = sticker(kit.nearest(title(), 16), 20)
    return kit.trim(label)
