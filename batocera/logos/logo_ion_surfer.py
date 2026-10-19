"""Ion Surfer app icon: a retro surf poster -- the ion riding one big swell.

The swell is the game's own potential: Game.potential, the game's Catmull-Rom
curve through the electrode voltages, here through voltages that make a
trough and one big crest. It is drawn as a single bold foam-white line over
flat poster bands of ocean blue. The game's blue ion (glow, body, highlight
and '+', as draw_world draws it, plus a white rim) drops down the flank of
the well, to the right and down, with three speed lines trailing up the slope
behind it. The scene is the curve mirrored (crest on the left), so the ion
moves in reading direction; the ion sprite and the title are not mirrored.

The rest is a flat-colour surf poster made from the game's palette: a sunset
sky running from the game's night blue through COOP violet, RED and orange
into GOLD, a striped GOLD sun on the horizon, and a blue sea. The title is
ION SURFER in the game's Bungee, sheared into italics for speed, in a
GOLD-to-orange fill over a hard navy drop shadow -- no outline ring or glow.
The marquee puts the title beside a round surf-patch emblem cut from the scene.
The wide tile (wide(), for the cabinet's 2:1 game list) is the same poster
with the swell stretched sideways and run on past both edges -- more of the
same curve behind the crest, flat water ahead -- and the title below it.
"""

from __future__ import annotations

import math
import sys

import kit
import pygame

sys.path.insert(0, str(kit.ROOT / "ion-surfer/src"))

from ion_surfer import game as g  # noqa: E402

ROM = "ion_surfer"

SS = 2  # the scene is drawn at twice the size and smoothscaled down (anti-aliasing)
NAVY = (6, 10, 24)  # the game's sky (Game.bg, top)
NIGHT = (16, 26, 58)  # ... and its bottom
ORANGE = (255, 150, 60)
SEA_TOP, SEA_BOT = (30, 74, 150), (8, 16, 44)
WATER = [(120, 200, 255), g.BLUE, (36, 92, 190), (14, 36, 96)]  # near the line .. deep
FOAM = (235, 246, 255)

HORIZON = 0.60  # of the height
# Voltages (curve heights in world px): a trough, then one big swell.
# Node i sits at x = (i + 0.5) * EW, as in the game.
VOLTS = [40, 36, 38, 55, 110, 200, 310, 410, 460, 430, 350, 290, 260]
FACE_X = (0, 1200)  # world x range of the curve
K = 0.86  # art px per world px (at 1024)
ORIGIN = (-6, 640)  # art position of world (FACE_X[0], 0)
ION_X = 554  # art x where the ion rides, on the flank of the (mirrored) swell
ION_R = 40  # ion radius, art px

# The wide tile (wide()) is the square poster with its swell stretched
# sideways: the square's art px map to a 1024x512 tile scaled by WIDE_SX
# and WIDE_SY, the crest landing at WIDE_CREST, and the curve runs on past
# both sides of the square (more voltages behind the crest, flat water ahead)
WIDE_SX, WIDE_SY = 0.8, 0.57
WIDE_K = 0.72  # the line, the water bands and the ion, against the square's
WIDE_CREST = (330, 58)
WIDE_VOLTS = VOLTS + [250, 248, 252, 258, 262, 262]  # enough that none is generated
WIDE_SPAN = (-260, 1460)  # world x sampled: past both edges of the tile
WIDE_TITLE = 0.66  # title width, of the tile's


def _face(volts: list[int] = VOLTS, span: tuple[int, int] = FACE_X) -> list[tuple[float, float]]:
    """The wave face in art px (at 1024): the game's potential, sampled and
    mirrored left-right, so the crest is on the left and the slope falls to
    the right. `span` is the world x range to sample (wide() samples more of
    it than the square shows, off both sides)."""
    game = g.Game(pygame.Surface((g.W, g.H)))
    c = g.Curve(g.BLUE)
    c.v = list(volts)
    game.caps, game.defects = [], []
    x0 = FACE_X[0]
    pts = [(ORIGIN[0] + (x - x0) * K, ORIGIN[1] - game.potential(c, x) * K)
           for x in range(span[0], span[1] + 1, 4)]
    return [(1024 - x, y) for x, y in reversed(pts)]


def _ion(s, center, r):
    """The game's ion sprite, with a white rim so it reads on the blue water."""
    cx, cy = center
    dot = pygame.Surface(s.get_size(), pygame.SRCALPHA)
    pygame.draw.circle(dot, (255, 255, 255), center, r)
    s.blit(kit.glow(dot, (200, 235, 255), round(r * 0.9), 0.9), (0, 0))
    pygame.draw.circle(s, FOAM, center, r * 1.14)
    pygame.draw.circle(s, g.BLUE, center, r)
    pygame.draw.circle(s, (255, 255, 255), (cx - r * 0.3, cy - r * 0.3), r * 0.34)
    kit.blit_center(s, kit.text_shape("+", kit.RUBIK_FONT, round(r * 1.25)), (cx + r * 0.12, cy + r * 0.08))


def wave(size: int) -> pygame.Surface:
    """The swell and its ion on transparency, for a `size` square."""
    k = size / 1024

    def T(p):
        return (p[0] * k, p[1] * k)

    face = _face()
    i = min(range(len(face)), key=lambda q: abs(face[q][0] - ION_X))
    return _wave((size, size), [T(p) for p in face], i, k)


def _wave(size: tuple[int, int], pts: list[tuple[float, float]], i: int, k: float) -> pygame.Surface:
    """The swell along `pts` (surface px) and the ion riding it at pts[i];
    `k` scales the line, the water bands and the ion (1 = the 1024 square)."""
    s = pygame.Surface(size, pygame.SRCALPHA)
    far = max(size) * 2
    # the water under the curve, in flat poster bands: lighter near the line
    mask = pygame.Surface(size, pygame.SRCALPHA)
    pygame.draw.polygon(mask, (255, 255, 255), pts + [(far, pts[-1][1]), (far, far), (-far, far), (-far, pts[0][1])])
    paint = pygame.Surface(size, pygame.SRCALPHA)
    paint.fill((*WATER[-1], 255))
    for j, d in enumerate((150, 90, 40)):  # the curve, dropped by d px
        band = [(x, y + d * k) for x, y in pts]
        pygame.draw.polygon(paint, WATER[2 - j], band + [(far, band[-1][1]), (far, -far), (-far, -far), (-far, band[0][1])])
    paint.blit(mask, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
    s.blit(paint, (0, 0))
    # the potential itself: one bold foam-white line
    lw = round(10 * k)
    pygame.draw.lines(s, FOAM, False, pts, lw)
    for p in pts:  # round joins, so the thick line has no notches at the crest
        pygame.draw.circle(s, FOAM, p, lw / 2)
    # the ion on the flank, with speed lines trailing up the slope behind it
    r = ION_R * k
    (ax, ay), (bx, by) = pts[i - 3], pts[i + 3]
    d = math.hypot(bx - ax, by - ay)
    ux, uy = (bx - ax) / d, (by - ay) / d  # along the slope, rightwards: downhill, the way it moves
    nx, ny = uy, -ux  # out of the water
    cx, cy = pts[i][0] + nx * (r + 9 * k), pts[i][1] + ny * (r + 9 * k)
    for off, start, ln in ((-0.55, 1.5, 2.6), (0.0, 1.35, 3.6), (0.55, 1.5, 2.2)):
        ox, oy = cx + nx * off * r - ux * start * r, cy + ny * off * r - uy * start * r
        pygame.draw.line(s, FOAM, (ox, oy), (ox - ux * ln * r, oy - uy * ln * r), round(7 * k))
    _ion(s, (cx, cy), r)
    return s


def sky(size: int) -> pygame.Surface:
    hy = round(size * HORIZON)
    return _sky((size, size), 0, hy, (size * 0.66, hy - size * 0.1, size * 0.19), size)


def _sky(size: tuple[int, int], top: float, hy: int, sun_at: tuple[float, float, float],
         unit: float) -> pygame.Surface:
    """The sunset sky running from `top` (may be above the surface) down to
    the horizon at `hy`, the sun (centre x, y, radius) and the sea below.
    `unit` is the size of the square the stripes and glints are measured in."""
    w, h = size
    s = pygame.Surface(size)
    s.fill(NAVY)  # above `top`, if it is inside
    s.blit(kit.gradient((w, round(hy - top)), [NAVY, NIGHT, (110, 70, 160), g.RED, ORANGE, g.GOLD]), (0, top))
    # the sun: GOLD disc sitting on the horizon, cut by poster stripes
    cx, cy, r = sun_at
    sun = pygame.Surface(size, pygame.SRCALPHA)
    pygame.draw.circle(sun, (255, 236, 170), (cx, cy), r)
    for j in range(5):
        y = cy + r * (0.12 + 0.19 * j)
        sun.fill((0, 0, 0, 0), (0, y, w, unit * (0.008 + 0.006 * j)))
    s.blit(sun, (0, 0))
    s.blit(kit.gradient((w, h - hy), [SEA_TOP, SEA_BOT]), (0, hy))
    # glints of the sun on the water
    for j in range(6):
        y = hy + unit * (0.02 + 0.03 * j)
        gw = r * (1.2 - 0.15 * j)
        pygame.draw.rect(s, kit.lerp(g.GOLD, SEA_TOP, 0.3 + 0.12 * j), (cx - gw / 2, y, gw, unit * 0.006))
    return s


def _shear(surf: pygame.Surface, slant: float) -> pygame.Surface:
    """Italicise: shift each row right by slant * its height above the baseline."""
    w, h = surf.get_size()
    out = pygame.Surface((w + round(h * slant), h), pygame.SRCALPHA)
    for y in range(h):
        out.blit(surf, (round((h - y) * slant), y), (0, y, w, 1))
    return out


def title(width: int) -> pygame.Surface:
    shape = _shear(kit.text_shape("ION SURFER", kit.BUNGEE_FONT, 220, tracking=6), 0.22)
    fill = kit.tint(shape, kit.gradient(shape.get_size(), [(255, 240, 190), g.GOLD, ORANGE]))
    d = 16  # hard poster shadow, down and to the left (against the motion)
    out = pygame.Surface((shape.get_width() + d, shape.get_height() + d), pygame.SRCALPHA)
    shadow = kit.tint(shape, NAVY)
    for i in range(d, 0, -2):
        out.blit(shadow, (d - i, i))
    out.blit(fill, (d, 0))
    return kit.fit(kit.trim(out), width, width)


def scene(size: int, pad: int = 0) -> pygame.Surface:
    """Sky, sun, sea and the wave, drawn at SS times the size; with `pad`,
    `pad` px more of them on every side, the swell running on past both
    edges (wide()'s voltages)."""
    if not pad:
        s = sky(size * SS)
        s.blit(wave(size * SS), (0, 0))
        return pygame.transform.smoothscale(s, (size, size))
    n, o = size * SS, pad * SS
    full = (n + 2 * o, n + 2 * o)
    hy = round(n * HORIZON)
    s = _sky(full, o, hy + o, (n * 0.66 + o, hy - n * 0.1 + o, n * 0.19), n)
    # world x sampled: past both edges of the padded canvas (the curve is mirrored)
    span = (math.floor((ORIGIN[0] - pad) / K) - 8, math.ceil((1024 + pad - ORIGIN[0]) / K) + 8)
    face = _face(WIDE_VOLTS, span)
    i = min(range(len(face)), key=lambda q: abs(face[q][0] - ION_X))
    k = n / 1024
    s.blit(_wave(full, [(x * k + o, y * k + o) for x, y in face], i, k), (0, 0))
    return pygame.transform.smoothscale(s, (size + 2 * pad, size + 2 * pad))


def art(size: int, pad: int = 0) -> pygame.Surface:
    """The square logo, `size` px; with `pad`, on a canvas `pad` px bigger on
    every side, the sky, sea and swell running on (see generate_logos.py: extended/)."""
    out = scene(size, pad)
    kit.blit_center(out, title(round(size * 0.84)), (pad + size / 2, pad + size * 0.855))
    return out


def wide(width: int, height: int) -> pygame.Surface:
    """The same poster for a 2:1 tile: the swell, ion and sun stretched
    sideways over the sky and sea, the title below across the deep water."""
    ux, uy = width / 1024 * SS, height / 512 * SS  # drawn at SS times the size, like scene()
    face = _face(WIDE_VOLTS, WIDE_SPAN)
    i = min(range(len(face)), key=lambda q: abs(face[q][0] - ION_X))
    crest = min(face, key=lambda p: p[1])
    sx, sy = WIDE_SX * ux, WIDE_SY * uy
    ax, ay = WIDE_CREST[0] * ux - crest[0] * sx, WIDE_CREST[1] * uy - crest[1] * sy

    def T(x, y):
        return ax + x * sx, ay + y * sy

    big = (width * SS, height * SS)
    hy = round(T(0, 1024 * HORIZON)[1])
    sun = (*T(1024 * 0.66, 1024 * (HORIZON - 0.1)), 1024 * 0.19 * (sx + sy) / 2)
    s = _sky(big, T(0, 0)[1], hy, sun, 1024 * sy)
    s.blit(_wave(big, [T(*p) for p in face], i, WIDE_K * uy), (0, 0))
    out = pygame.transform.smoothscale(s, (width, height))
    kit.blit_center(out, title(round(width * WIDE_TITLE)), (width / 2, height * 0.855))
    return out


def marquee() -> pygame.Surface:
    """The italic title beside a round surf-patch emblem cut from the scene."""
    t = title(1200)
    d = round(t.get_height() * 1.35)
    view = scene(1024)
    # the patch frames the sun, the ion and the crest: a square crop, then a circle
    crop = pygame.Surface((600, 600))
    crop.blit(view, (0, 0), pygame.Rect(274, 150, 600, 600))
    patch = pygame.Surface((d, d), pygame.SRCALPHA)
    disc = pygame.Surface((d, d), pygame.SRCALPHA)
    pygame.draw.circle(disc, (255, 255, 255), (d / 2, d / 2), d / 2 - 4)
    patch.blit(pygame.transform.smoothscale(crop, (d, d)), (0, 0))
    patch.blit(disc, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
    pygame.draw.circle(patch, g.GOLD, (d / 2, d / 2), d / 2 - 3, 6)
    out = pygame.Surface((d + 40 + t.get_width(), max(d, t.get_height())), pygame.SRCALPHA)
    out.blit(patch, (0, (out.get_height() - d) // 2))
    out.blit(t, (d + 40, (out.get_height() - t.get_height()) // 2))
    return out
