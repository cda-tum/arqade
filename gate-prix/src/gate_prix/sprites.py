"""Every picture of the road's world, drawn once at start-up in the look file's style.

`SpriteCache` holds each sprite kind at SPRITE_SIZES sizes. Each size is drawn as vector
shapes at 2x and smoothscaled down once, so per frame a sprite is a single blit of the
nearest size: never a rescale. `Background` is the far wall, coax and haze (scrolled
sideways for parallax) and the gold plate overhead, pre-rendered once per view size.

Sizes are "scales": pixels per road half-width at the sprite's distance, which is what the
road renderer reports for every sprite it projects.

Only plain surfaces are used (no display needed), so the benchmark runs on the cabinet.
"""

from __future__ import annotations

import math
import random
from importlib import resources

import pygame

from gate_prix import config
from gate_prix.circuit import GATES

WHITE = (255, 255, 255)
INK = (10, 10, 20)
LOOK = 0.9 / 480  # the look file's sprite scale per pixel of road half-width
SS = 2  # every sprite and background is drawn at 2x, then smoothscaled down once


def mix(a, b, k):
    return tuple(round(x + (y - x) * k) for x, y in zip(a, b))


_FONTS: dict[int, pygame.font.Font] = {}


def font(px: int) -> pygame.font.Font:
    """The bundled DejaVu Sans Condensed Bold at a pixel size (needs pygame.font.init())."""
    px = max(4, px)
    if not pygame.font.get_init():  # after a pygame.quit(), every cached Font is dead
        pygame.font.init()
        _FONTS.clear()
    if px not in _FONTS:
        path = resources.files("gate_prix") / "assets" / "fonts" / "DejaVuSansCondensed-Bold.ttf"
        _FONTS[px] = pygame.font.Font(str(path), px)
    return _FONTS[px]


# --- Drawing helpers (in pixels, on SRCALPHA surfaces) ---------------------------------------


def _rect(surf, col, x, y, w, h, rad=0):
    r = pygame.Rect(round(x), round(y), max(1, round(w)), max(1, round(h)))
    pygame.draw.rect(surf, col, r, border_radius=max(0, round(rad)))


def _circle(surf, col, x, y, r, width=0):
    pygame.draw.circle(surf, col, (round(x), round(y)), max(1, round(r)), round(width))


def _layer(surf):
    return pygame.Surface(surf.get_size(), pygame.SRCALPHA)


def _glow(surf, x, y, r, col, a=140):
    """The look's soft glow: concentric discs, more opaque towards the middle."""
    big = max(2, round(r))
    g = pygame.Surface((2 * big, 2 * big), pygame.SRCALPHA)
    step = max(2, big // 48)
    for k in range(big, 0, -step):
        alpha = min(255, round(a * (1 - k / big) ** 1.4))
        pygame.draw.circle(g, (*col, alpha), (big, big), k)
    surf.blit(g, (round(x) - big, round(y) - big))


def _ellipse(surf, rgba, x, y, w, h):
    lay = _layer(surf)
    pygame.draw.ellipse(lay, rgba, pygame.Rect(round(x), round(y), max(1, round(w)), max(1, round(h))))
    surf.blit(lay, (0, 0))


def _band(cx, cy, r_out, r_in, a0=0.0, a1=math.pi, steps=None):
    """A polygon for the part of an annulus between two angles (0 = right, pi = left)."""
    steps = steps or max(8, min(96, round(r_out / 3)))
    outer = [(cx + r_out * math.cos(a0 + (a1 - a0) * i / steps),
              cy - r_out * math.sin(a0 + (a1 - a0) * i / steps)) for i in range(steps + 1)]
    inner = [(cx + r_in * math.cos(a1 - (a1 - a0) * i / steps),
              cy - r_in * math.sin(a1 - (a1 - a0) * i / steps)) for i in range(steps + 1)]
    return outer + inner


def _text(surf, text, px, col, cx, cy, shadow=True):
    img = font(px).render(text, True, col)
    r = img.get_rect(center=(round(cx), round(cy)))
    if shadow:
        sh = font(px).render(text, True, (8, 8, 20))
        d = max(1, px // 14)
        surf.blit(sh, r.move(d, d))
    surf.blit(img, r)


# --- The sprites: each drawn with its foot at (x, y), u pixels per road half-width ----------


def draw_coax(surf, x, y, u):
    """A semi-rigid coax line rising from the plate, with an SMA nut and an attenuator."""
    s = u * LOOK
    h = 260 * s
    w = max(1.0, 9 * s)
    _ellipse(surf, (0, 0, 0, 90), x - w * 2.2, y - w * 0.5, w * 4.4, w)
    _rect(surf, (210, 200, 180), x - w / 2, y - h, w, h)
    _rect(surf, (250, 245, 230), x - w / 2, y - h, w * 0.35, h)
    _rect(surf, (220, 170, 60), x - w, y - h * 0.62, w * 2, h * 0.08)
    _rect(surf, (196, 150, 60), x - w * 1.2, y - h * 0.3, w * 2.4, h * 0.12, rad=2 * s)
    _rect(surf, (255, 230, 150), x - w * 1.2, y - h * 0.3, w * 2.4, h * 0.03)
    _circle(surf, (255, 220, 140), x, y - h, w * 0.9)


def draw_attenuator(surf, x, y, u):
    """A stubby gold SMA attenuator standing on the plate, knurled, with its thread on top."""
    s = u * LOOK
    w, h = 30 * s, 46 * s
    _ellipse(surf, (0, 0, 0, 100), x - w * 0.95, y - w * 0.18, w * 1.9, w * 0.36)
    _rect(surf, (196, 150, 60), x - w / 2, y - h, w, h, rad=3 * s)
    _rect(surf, (255, 230, 150), x - w / 2, y - h, w * 0.28, h, rad=3 * s)
    for k in (0.22, 0.5, 0.78):
        _rect(surf, (150, 110, 40), x - w / 2, y - h * k - h * 0.04, w, h * 0.08)
    _rect(surf, (210, 200, 180), x - w * 0.22, y - h - 12 * s, w * 0.44, 12 * s)
    _rect(surf, (250, 245, 230), x - w * 0.22, y - h - 12 * s, w * 0.12, 12 * s)
    _circle(surf, (240, 220, 160), x, y - h - 12 * s, w * 0.24)


def draw_standoff(surf, x, y, u):
    """A tall stainless standoff holding the stages apart, with hex nuts."""
    s = u * LOOK
    w, h = 16 * s, 470 * s
    _ellipse(surf, (0, 0, 0, 100), x - w * 2, y - w * 0.4, w * 4, w * 0.8)
    _rect(surf, (170, 172, 180), x - w / 2, y - h, w, h)
    _rect(surf, (235, 238, 245), x - w / 2, y - h, w * 0.3, h)
    for k in (0.0, 0.62):
        _rect(surf, (120, 124, 136), x - w, y - h * k - 26 * s, w * 2, 26 * s, rad=2 * s)
        _rect(surf, (210, 214, 224), x - w, y - h * k - 26 * s, w * 0.5, 26 * s)
    _circle(surf, (240, 220, 160), x, y - h, w * 0.8)


BADGE_LETTER_MIN = 10  # px: a gate's letter never shrinks below this, so a row reads early
ARCH_PAD = 16  # px around the arch's extents, for the badge and glow kept big at small sizes


DECOY_DIM = 0.5  # a decoy's colours, this far towards the dark


def draw_arch(surf, x, y, u, gate, lit):
    """A gate: a semicircular arch standing on the track, both feet on the road, a light
    curtain under it and the gate's letter on a badge at its crown.

    The right arch (`lit`) is unmissable: a bright glow and a bright curtain, its colours
    lifted towards white. A decoy is drawn dimmer and smaller (DECOY_HALF_WIDTH, which is
    also all of it that counts as going through it). Far away (a second ahead the arch is
    only ~12 px high) the badge and its letter keep a minimum size and the lit arch's glow
    grows stronger, so the gate reads in time. All of it is drawn once, into the cache:
    nothing here costs anything per frame. (The bouncing marker over the right arch is
    `markers`, drawn by the renderer.)"""
    col = config.GATE_COLORS[gate]
    half = config.ARCH_HALF_WIDTH if lit else config.DECOY_HALF_WIDTH
    r = half * u  # its outer radius: the feet are 2r apart
    t = max(2.0, 0.16 * r)  # its thickness
    # 0 when the arch is big on screen, 1 when it is far away and small (u is at SS x)
    small = min(1.0, max(0.0, (44 * SS - r) / (32 * SS)))
    if lit:
        glow_r = r * (1.3 + 0.3 * small) + small * 10 * SS  # widest far away, cheap near
        _glow(surf, x, y - r * 0.55, glow_r, mix(col, WHITE, 0.25), round(150 + 60 * small))
        col = mix(col, WHITE, 0.2)
    else:
        col = mix(col, (24, 26, 40), DECOY_DIM)
    _ellipse(surf, (0, 0, 0, 110), x - r * 1.05, y - r * 0.05, r * 2.1, r * 0.14)
    # the light curtain: the upper half of the inner disc
    lay = _layer(surf)
    pygame.draw.polygon(lay, (*col, 130 if lit else 35), _band(x, y, r - t, 0))
    surf.blit(lay, (0, 0))
    # the arch: a dark rim, its colour, a bright highlight along its upper left
    pygame.draw.polygon(surf, mix(col, INK, 0.55), _band(x, y, r, r - t))
    pygame.draw.polygon(surf, col, _band(x, y, r - t * 0.12, r - t * 0.84))
    lay = _layer(surf)
    pygame.draw.polygon(lay, (*mix(col, WHITE, 0.6), 230),
                        _band(x, y, r - t * 0.3, r - t * 0.52, math.radians(100), math.radians(165)))
    surf.blit(lay, (0, 0))
    for fx in (-1, 1):  # its feet on the road
        _rect(surf, mix(col, (20, 20, 30), 0.45), x + fx * (r - t / 2) - t * 0.65, y - t * 0.5,
              t * 1.3, t * 0.6, rad=2)
    letter = max(round(0.36 * r), BADGE_LETTER_MIN * SS)  # the badge at the crown
    bw = max(0.4267 * r, letter * 1.6)
    if lit and small:  # a white ring round the right gate's badge, far away
        _circle(surf, WHITE, x, y - r, bw * 0.55 + small * 1.5 * SS)
    _circle(surf, (14, 16, 30), x, y - r, bw * 0.55)
    _circle(surf, col, x, y - r, bw * 0.48)
    _text(surf, gate, letter, WHITE if lit else (176, 178, 196), x, y - r + 1)


def badge_top(scale: float) -> float:
    """How far above the right arch's foot its badge reaches, in pixels at a sprite scale:
    where the marker over it goes."""
    r = config.ARCH_HALF_WIDTH * scale
    letter = max(0.36 * r, BADGE_LETTER_MIN)
    return r + 0.55 * max(0.4267 * r, letter * 1.6)


MARKER_SIZES = (16, 20, 24, 28, 32, 36)  # px wide: never smaller, even over a far arch
_MARKERS: list[pygame.Surface] = []


def markers() -> list[pygame.Surface]:
    """The bouncing marker over the right arch: a bright downward triangle with a dark
    edge, drawn once at a few sizes (built on first use, at start-up)."""
    if not _MARKERS:
        for w in MARKER_SIZES:
            big = pygame.Surface((w * SS + 4 * SS, w * SS + 4 * SS), pygame.SRCALPHA)
            m = 2 * SS
            tip = (m + w * SS / 2, m + w * SS * 0.86)
            pts = [(m, m), (m + w * SS, m), tip]
            _glow(big, tip[0], m + w * SS * 0.4, w * SS * 0.75, (255, 240, 150), 120)
            pygame.draw.polygon(big, (255, 238, 120), pts)
            pygame.draw.polygon(big, INK, pts, max(2, SS * 2 * w // 20))
            img = pygame.transform.smoothscale(big, (w + 4, w + 4))
            _rle(img)
            _MARKERS.append(img)
    return _MARKERS


def marker_for(scale: float) -> pygame.Surface:
    """The marker size for a right arch at this sprite scale."""
    images = markers()
    want = config.ARCH_HALF_WIDTH * scale * 0.5
    i = sum(1 for w in MARKER_SIZES if w <= want) - 1
    return images[max(0, min(len(images) - 1, i))]


def draw_box(surf, x, y, u):
    """An item box: a floating glass cube with a glowing question mark."""
    b = 0.24 * u
    lift = 0.07 * u
    _ellipse(surf, (0, 0, 0, 100), x - b * 0.6, y - b * 0.08, b * 1.2, b * 0.16)
    top = y - lift - b
    _glow(surf, x, top + b / 2, b * 0.9, (150, 230, 255), 110)
    lay = _layer(surf)
    pygame.draw.rect(lay, (70, 190, 250, 170), pygame.Rect(round(x - b / 2), round(top), round(b), round(b)),
                     border_radius=round(b * 0.18))
    pygame.draw.rect(lay, (200, 245, 255, 120),
                     pygame.Rect(round(x - b / 2 + b * 0.1), round(top + b * 0.08), round(b * 0.8), round(b * 0.3)),
                     border_radius=round(b * 0.12))
    surf.blit(lay, (0, 0))
    pygame.draw.rect(surf, WHITE, pygame.Rect(round(x - b / 2), round(top), round(b), round(b)),
                     max(1, round(b * 0.06)), border_radius=round(b * 0.18))
    _text(surf, "?", max(6, round(b * 0.72)), WHITE, x, top + b * 0.52)


FLAME_FRAMES = 4  # flickering exhaust flames, cycled while a car boosts


def draw_flame(surf, x, y, u, frame):
    """A boosting car's exhaust: two blue-white jets from under its rear wing, flickering
    over FLAME_FRAMES frames. Its foot is the car's, and it is drawn just in front of it."""
    w = config.CAR_WIDTH * u
    h = 0.4 * w
    rnd = random.Random(frame * 7 + 1)
    for sx in (-0.2, 0.2):
        n = 0.85 + 0.3 * rnd.random()
        px, py = x + sx * w, y - h * 0.24
        _glow(surf, px, py + h * 0.08 * n, w * 0.14 * n, (90, 170, 255), 170)
        _ellipse(surf, (120, 200, 255, 210), px - w * 0.055, py - h * 0.06, w * 0.11, h * 0.34 * n)
        _ellipse(surf, (235, 250, 255, 255), px - w * 0.03, py - h * 0.03, w * 0.06, h * 0.2 * n)


def draw_car(surf, x, y, u, col, ghost=False):
    """A racer from behind: a low wedge, a rear wing, glowing tail lights and its Bloch orb."""
    w = config.CAR_WIDTH * u
    s = w / 300
    h = 120 * s
    _ellipse(surf, (0, 0, 0, 120), x - w * 0.6, y - h * 0.12, w * 1.2, h * 0.3)
    body = [(x - w / 2, y), (x - w * 0.44, y - h * 0.55), (x - w * 0.25, y - h * 0.8),
            (x + w * 0.25, y - h * 0.8), (x + w * 0.44, y - h * 0.55), (x + w / 2, y)]
    pygame.draw.polygon(surf, mix(col, INK, 0.35), body)
    pygame.draw.polygon(surf, col, [(x - w * 0.44, y - h * 0.55), (x - w * 0.25, y - h * 0.8),
                                    (x + w * 0.25, y - h * 0.8), (x + w * 0.44, y - h * 0.55)])
    pygame.draw.polygon(surf, (30, 40, 70), [(x - w * 0.22, y - h * 0.78), (x + w * 0.22, y - h * 0.78),
                                             (x + w * 0.16, y - h * 0.95), (x - w * 0.16, y - h * 0.95)])
    pygame.draw.polygon(surf, (140, 180, 230), [(x - w * 0.2, y - h * 0.8), (x - w * 0.05, y - h * 0.8),
                                                (x - w * 0.1, y - h * 0.92), (x - w * 0.16, y - h * 0.92)])
    _rect(surf, mix(col, INK, 0.2), x - w * 0.5, y - h * 1.08, w, h * 0.12, rad=3 * s)
    _rect(surf, mix(col, WHITE, 0.5), x - w * 0.5, y - h * 1.08, w, h * 0.04, rad=3 * s)
    for sx in (-0.42, 0.38):
        _rect(surf, (40, 40, 60), x + w * sx, y - h * 1.0, w * 0.04, h * 0.45)
    for sx in (-1, 1):
        _rect(surf, (255, 60, 70), x + sx * w * 0.33 - w * 0.08, y - h * 0.45, w * 0.16, h * 0.12, rad=2 * s)
        if not ghost:
            _glow(surf, x + sx * w * 0.33, y - h * 0.39, 24 * s, (255, 80, 90), 140)
        _rect(surf, (18, 18, 26), x + sx * w * 0.5 - w * 0.07, y - h * 0.32, w * 0.14, h * 0.34, rad=4 * s)
    if not ghost:
        _glow(surf, x, y - h * 0.62, 26 * s, (200, 240, 255), 160)
    _circle(surf, (230, 248, 255), x, y - h * 0.62, 12 * s)
    _circle(surf, (90, 160, 220), x, y - h * 0.62, 12 * s, max(1, round(1.5 * s)))


GHOST = (170, 230, 255)


# --- The second playtest's sprites: the gantry, drifting, the storm, the items --------------

GANTRY_POST = 1.3  # the gantry's posts stand this far out (road half-widths), past the rumble
GANTRY_TOP = 1.62  # its banner's top, above the road
GANTRY_BANNER = 1.18  # and its bottom
LIGHT_Y = 1.07  # the start lights' centres, above the road
LIGHT_X = (-0.3, -0.15, 0.0, 0.15, 0.3)
LIGHT_R = 0.055
GANTRY_MAX_SCALE = 560.0  # nearer than this its banner is above the view: not drawn


def draw_gantry(surf, x, y, u):
    """The start and finish gantry over the lap line: two posts, a "GATE PRIX" banner and
    a dark housing hanging under it with five unlit start lights (lit by the renderer)."""
    post = 0.07 * u
    for side in (-1, 1):
        px = x + side * GANTRY_POST * u
        _ellipse(surf, (0, 0, 0, 100), px - post * 1.6, y - post * 0.3, post * 3.2, post * 0.6)
        _rect(surf, (90, 96, 116), px - post / 2, y - GANTRY_TOP * u, post, GANTRY_TOP * u)
        _rect(surf, (200, 206, 224), px - post / 2, y - GANTRY_TOP * u, post * 0.3, GANTRY_TOP * u)
        _rect(surf, (220, 170, 60), px - post * 0.8, y - 0.06 * u, post * 1.6, 0.06 * u)
    left, right = x - (GANTRY_POST + 0.08) * u, x + (GANTRY_POST + 0.08) * u
    top, bottom = y - GANTRY_TOP * u, y - GANTRY_BANNER * u
    _rect(surf, (18, 22, 44), left, top, right - left, bottom - top, rad=0.03 * u)
    _rect(surf, (220, 170, 60), left, top, right - left, 0.03 * u)
    _rect(surf, (220, 170, 60), left, bottom - 0.03 * u, right - left, 0.03 * u)
    for k in range(14):  # chequer strips at both ends of the banner
        cx0 = left + 0.05 * u
        cy0 = top + 0.05 * u + (k % 2) * 0.17 * u
        for end in (0, 1):
            ox = cx0 + end * (right - left - 0.44 * u) + (k // 2) * 0.05 * u
            if ox < cx0 + end * (right - left - 0.44 * u) + 0.34 * u:
                _rect(surf, (240, 240, 246) if (k // 2) % 2 == 0 else (30, 30, 40),
                      ox, cy0, 0.05 * u, 0.17 * u)
    _text(surf, "GATE PRIX", max(5, round(0.3 * u)), (255, 230, 120), x, (top + bottom) / 2)
    # the start lights' housing, under the middle of the banner
    hx0, hx1 = x + (LIGHT_X[0] - 0.09) * u, x + (LIGHT_X[-1] + 0.09) * u
    _rect(surf, (12, 12, 20), hx0, bottom, hx1 - hx0, (GANTRY_BANNER - LIGHT_Y + 0.08) * u, rad=0.03 * u)
    for lx in LIGHT_X:
        _circle(surf, (50, 30, 34), x + lx * u, y - LIGHT_Y * u, LIGHT_R * u)
        _circle(surf, (90, 70, 74), x + lx * u, y - LIGHT_Y * u, LIGHT_R * u, max(1, 0.012 * u))


SPARK_COLOURS = ((255, 250, 225), (90, 170, 255), (255, 200, 60))  # drift charge 0, 1, 2
SPARK_FRAMES = 3


def draw_sparks(surf, x, y, u, level, frame):
    """A drifting car's sparks, a fan rising out and up from both rear wheels: white, then
    blue at charge 1 and gold at charge 2. Drawn just in front of the car."""
    col = SPARK_COLOURS[level]
    w = config.CAR_WIDTH * u
    rnd = random.Random(frame * 31 + level * 7 + 3)
    for side in (-1, 1):
        wx, wy = x + side * w * 0.47, y - w * 0.06
        _glow(surf, wx, wy, w * (0.13 + 0.05 * level), col, 170)
        for _ in range(8 + 4 * level):
            a = rnd.uniform(0.1, 1.1)  # radians from straight up, outwards
            n = rnd.uniform(0.12, 0.26 + 0.08 * level) * w
            ex, ey = wx + side * math.sin(a) * n, wy - math.cos(a) * n * 0.8
            pygame.draw.line(surf, (*mix(col, WHITE, 0.25), 255), (round(wx), round(wy)),
                             (round(ex), round(ey)), max(1, round(w * 0.016)))
            _circle(surf, mix(col, WHITE, 0.6), ex, ey, max(1.0, w * 0.014))


def draw_turbo(surf, x, y, u, level):
    """The mini-turbo's flash at the exhaust as a drift pays out: blue (1) or gold (2)."""
    col = SPARK_COLOURS[level]
    w = config.CAR_WIDTH * u
    cy = y - w * 0.16
    _glow(surf, x, cy, w * 0.55, col, 190)
    for k in range(10):
        a = math.pi * (0.1 + 0.8 * k / 9)
        r0, r1 = w * 0.12, w * (0.42 + 0.12 * (k % 2))
        pygame.draw.line(surf, (*mix(col, WHITE, 0.4), 230),
                         (round(x + r0 * math.cos(a)), round(cy + r0 * 0.5 * math.sin(a))),
                         (round(x + r1 * math.cos(a)), round(cy + r1 * 0.5 * math.sin(a))),
                         max(1, round(w * 0.02)))
    _ellipse(surf, (255, 255, 255, 230), x - w * 0.12, cy - w * 0.04, w * 0.24, w * 0.08)


STATIC_FRAMES = 3
STORM_CLOUD = ((150, 140, 190), (225, 215, 255))  # the storm's static: grey-violet, crackling
DECO_CLOUD = ((150, 80, 190), (255, 170, 240))  # a DECOHERENCE cloud: deeper, pinker


def draw_static(surf, x, y, u, frame, palette=STORM_CLOUD, radius=None):
    """A static cloud hanging over the road: soft blobs with crackling bolts through them."""
    body, crackle = palette
    r = (radius or config.HAZARD_SIZE["cloud"]) * u
    cy = y - r * 0.55
    rnd = random.Random(17 + frame)
    _ellipse(surf, (0, 0, 0, 70), x - r, y - r * 0.08, 2 * r, r * 0.16)
    lay = _layer(surf)
    for k in range(9):
        a = k / 9 * 2 * math.pi
        bx, by = x + 0.55 * r * math.cos(a), cy + 0.3 * r * math.sin(a)
        br = r * (0.36 + 0.12 * ((k * 7 + frame) % 3) / 2)
        pygame.draw.circle(lay, (*body, 120), (round(bx), round(by)), max(1, round(br)))
    pygame.draw.circle(lay, (*mix(body, crackle, 0.3), 150), (round(x), round(cy)), max(1, round(r * 0.45)))
    surf.blit(lay, (0, 0))
    for _ in range(4):  # crackle: short zigzag bolts, different every frame
        px, py = x + rnd.uniform(-0.6, 0.6) * r, cy + rnd.uniform(-0.3, 0.3) * r
        pts = [(px, py)]
        for _ in range(4):
            px += rnd.uniform(-0.18, 0.18) * r
            py += rnd.uniform(-0.12, 0.12) * r
            pts.append((px, py))
        pygame.draw.lines(surf, (*crackle, 255), False, [(round(a), round(b)) for a, b in pts],
                          max(1, round(r * 0.025)))
    for _ in range(14):  # static speckles
        _circle(surf, (*crackle, 255), x + rnd.uniform(-0.75, 0.75) * r,
                cy + rnd.uniform(-0.35, 0.35) * r, max(1.0, r * 0.018))


MINE_FRAMES = 2


def draw_mine(surf, x, y, u, frame):
    """A bit-flip mine: a small dark spiked orb, a red glow and a white X on it."""
    r = config.HAZARD_SIZE["mine"] * u
    cy = y - r * 1.4
    _ellipse(surf, (0, 0, 0, 110), x - r, y - r * 0.12, 2 * r, r * 0.24)
    _glow(surf, x, cy, r * 2.0, (255, 60, 90), 120)
    for k in range(10):
        a = (k + 0.5 * frame) / 10 * 2 * math.pi
        tip = (x + 1.45 * r * math.cos(a), cy + 1.45 * r * math.sin(a))
        b1 = (x + 0.8 * r * math.cos(a - 0.22), cy + 0.8 * r * math.sin(a - 0.22))
        b2 = (x + 0.8 * r * math.cos(a + 0.22), cy + 0.8 * r * math.sin(a + 0.22))
        pygame.draw.polygon(surf, (200, 205, 220), [tip, b1, b2])
    _circle(surf, (40, 30, 52), x, cy, r)
    _circle(surf, (230, 60, 80), x, cy, r, max(1, r * 0.12))
    d = r * 0.45
    for a, b in (((x - d, cy - d), (x + d, cy + d)), ((x - d, cy + d), (x + d, cy - d))):
        pygame.draw.line(surf, WHITE, (round(a[0]), round(a[1])), (round(b[0]), round(b[1])),
                         max(1, round(r * 0.2)))


def draw_shot(surf, x, y, u):
    """A MEASURE shot: a bright gold orb with a ring, flying at the height of a car."""
    r = 0.05 * u
    cy = y - 0.12 * u
    _glow(surf, x, cy, r * 3.2, (255, 200, 90), 200)
    _circle(surf, (255, 240, 190), x, cy, r)
    _circle(surf, (255, 200, 90), x, cy, r * 1.7, max(1, r * 0.25))


def _kinds_v2(kinds):
    kinds["gantry"] = (draw_gantry, (-(GANTRY_POST + 0.1), -GANTRY_TOP - 0.02, GANTRY_POST + 0.1, 0.03))
    for level in range(3):
        for f in range(SPARK_FRAMES):
            kinds[f"spark:{level}:{f}"] = (lambda s, x, y, u, lv=level, f=f: draw_sparks(s, x, y, u, lv, f),
                                           (-0.26, -0.18, 0.26, 0.02))
    for level in (1, 2):
        kinds[f"turbo:{level}"] = (lambda s, x, y, u, lv=level: draw_turbo(s, x, y, u, lv),
                                   (-0.2, -0.2, 0.2, 0.03))
    c = config.HAZARD_SIZE["cloud"]
    d = config.DECO_SIZE
    for f in range(STATIC_FRAMES):
        kinds[f"static:{f}"] = (lambda s, x, y, u, f=f: draw_static(s, x, y, u, f),
                                (-1.0 * c, -1.0 * c, 1.0 * c, 0.1 * c))
        kinds[f"deco:{f}"] = (lambda s, x, y, u, f=f: draw_static(s, x, y, u, f, DECO_CLOUD, d),
                              (-1.0 * d, -1.0 * d, 1.0 * d, 0.1 * d))
    m = config.HAZARD_SIZE["mine"]
    for f in range(MINE_FRAMES):
        kinds[f"mine:{f}"] = (lambda s, x, y, u, f=f: draw_mine(s, x, y, u, f), (-2.1 * m, -3.5 * m, 2.1 * m, 0.2 * m))
    kinds["shot"] = (draw_shot, (-0.17, -0.3, 0.17, 0.0))

# kind: (draw(surf, x, y, u), extents (left, top, right, bottom) in road half-widths)
_A = config.ARCH_HALF_WIDTH
_D = config.DECOY_HALF_WIDTH
_ARCH_EXT = (-1.06 * _D, -1.27 * _D, 1.06 * _D, 0.1 * _D)  # a decoy
_LIT_EXT = (-1.61 * _A, -2.16 * _A, 1.61 * _A, 1.06 * _A)  # the right arch and its glow


def _kinds():
    kinds = {
        "coax": (draw_coax, (-0.03, -0.51, 0.03, 0.01)),
        "attenuator": (draw_attenuator, (-0.04, -0.13, 0.04, 0.01)),
        "standoff": (draw_standoff, (-0.04, -0.9, 0.04, 0.01)),
        "box": (draw_box, (-0.24, -0.55, 0.24, 0.03)),
        "clone": (lambda s, x, y, u: draw_car(s, x, y, u, GHOST, ghost=True), (-0.21, -0.15, 0.21, 0.03)),
    }
    for i in range(FLAME_FRAMES):
        kinds[f"flame:{i}"] = (lambda s, x, y, u, i=i: draw_flame(s, x, y, u, i), (-0.12, -0.08, 0.12, 0.07))
    for g in GATES:
        kinds[f"arch:{g}"] = (lambda s, x, y, u, g=g: draw_arch(s, x, y, u, g, False), _ARCH_EXT)
        kinds[f"arch:{g}:lit"] = (lambda s, x, y, u, g=g: draw_arch(s, x, y, u, g, True), _LIT_EXT)
    for name, col in config.CAR_COLORS.items():
        kinds[f"car:{name}"] = (lambda s, x, y, u, col=col: draw_car(s, x, y, u, col), (-0.21, -0.15, 0.21, 0.03))
    _kinds_v2(kinds)
    return kinds


_KIND_TABLE = _kinds()
KINDS = tuple(_KIND_TABLE)
MAX_SCALE = {"gantry": GANTRY_MAX_SCALE}  # kinds never drawn nearer than this

# Every car also comes tilted (a drift: TILT_STEP degrees a step, TILTS steps either way) and
# as a tunnelling ghost (translucent, with GHOST_FRAMES of a shimmer). These are made from the
# finished car sprites at start-up, so they cost nothing per frame either.
TILTS = 2
TILT_STEP = 4.0  # degrees
TILT_MAX_SCALE = 850.0  # nearer than this (a car beside the camera) the car stays upright
GHOST_FRAMES = 2
CAR_KINDS = tuple(f"car:{name}" for name in config.CAR_COLORS)


def tilt_kind(kind: str, degrees: float) -> str:
    """The car sprite tilted nearest to `degrees` (positive: its top to the right)."""
    k = max(-TILTS, min(TILTS, round(degrees / TILT_STEP)))
    return kind if k == 0 else f"{kind}:t{k}"


def _tilted(entry, degrees):
    """A sprite rotated about its foot (anchor), smoothly, once."""
    img, ax, ay = entry
    out = pygame.transform.rotozoom(img, -degrees, 1.0)
    w, h = img.get_size()
    w2, h2 = out.get_width() / 2, out.get_height() / 2
    vx, vy = ax - w / 2, ay - h / 2
    a = math.radians(-degrees)  # rotozoom turns counter-clockwise for positive angles
    rx = vx * math.cos(a) + vy * math.sin(a)
    ry = -vx * math.sin(a) + vy * math.cos(a)
    box = out.get_bounding_rect()
    if box.w and box.h:  # rotozoom pads the corners: crop to what is drawn
        out = out.subsurface(box).copy()
    else:
        box = pygame.Rect(0, 0, 0, 0)
    _rle(out)
    return out, round(w2 + rx) - box.x, round(h2 + ry) - box.y


def _ghost(entry, frame):
    """A tunnelling car: see-through and violet, with bright shimmer lines across it."""
    img, ax, ay = entry
    out = img.copy()
    out.fill((215, 200, 255, 120), special_flags=pygame.BLEND_RGBA_MULT)
    lines = pygame.Surface(out.get_size(), pygame.SRCALPHA)
    step = max(3, out.get_height() // 6)
    for y in range(frame * step // 2, out.get_height(), step):
        pygame.draw.line(lines, (230, 220, 255, 255), (0, y), (out.get_width(), y), max(1, step // 4))
    mask = img.copy()
    mask.fill((255, 255, 255, 150), special_flags=pygame.BLEND_RGBA_MULT)
    lines.blit(mask, (0, 0), special_flags=pygame.BLEND_RGBA_MIN)
    out.blit(lines, (0, 0))
    _rle(out)
    return out, ax, ay


def sprite_scales() -> list[float]:
    lo, hi, n = config.SPRITE_SCALE_MIN, config.SPRITE_SCALE_MAX, config.SPRITE_SIZES
    return [lo * (hi / lo) ** (i / (n - 1)) for i in range(n)]


def render_sprite(kind: str, scale: float) -> tuple[pygame.Surface, int, int]:
    """One sprite at one scale: drawn at 2x, cropped, smoothscaled. Its surface and anchor."""
    draw, (left, top, right, bottom) = _KIND_TABLE[kind]
    u = scale * SS
    pad = (ARCH_PAD if kind.startswith("arch:") else 4) * SS
    cw = math.ceil((right - left) * u) + 2 * pad
    ch = math.ceil((bottom - top) * u) + 2 * pad
    cx = math.ceil(-left * u) + pad
    cy = math.ceil(-top * u) + pad
    canvas = pygame.Surface((cw, ch), pygame.SRCALPHA)
    draw(canvas, cx, cy, u)
    if kind == "clone":
        canvas.fill((255, 255, 255, 140), special_flags=pygame.BLEND_RGBA_MULT)
    box = canvas.get_bounding_rect()
    if box.w == 0 or box.h == 0:
        box = pygame.Rect(cx, cy, 2, 2)
    # crop to even edges, so the anchor halves exactly
    x0, y0 = box.x // 2 * 2, box.y // 2 * 2
    x1, y1 = min(cw, (box.right + 1) // 2 * 2), min(ch, (box.bottom + 1) // 2 * 2)
    cropped = canvas.subsurface(pygame.Rect(x0, y0, max(2, x1 - x0), max(2, y1 - y0)))
    size = (max(1, cropped.get_width() // SS), max(1, cropped.get_height() // SS))
    img = pygame.transform.smoothscale(cropped, size)
    _rle(img)
    return img, (cx - x0) // SS, (cy - y0) // SS


def _rle(img: pygame.Surface) -> None:
    """Run-length encode a finished sprite: its blits then skip the transparent runs and
    copy the opaque ones, 2-7x faster than blending every pixel (within 1/255 of it)."""
    img.set_alpha(255, pygame.RLEACCEL)


class SpriteCache:
    """Every sprite kind at every size, built once. `blit` picks the nearest size."""

    _shared: SpriteCache | None = None

    def __init__(self) -> None:
        self.scales = sprite_scales()
        self._log_lo = math.log(self.scales[0])
        self._log_step = math.log(self.scales[1] / self.scales[0])
        self.images: dict[str, list[tuple[pygame.Surface, int, int] | None]] = {
            kind: [render_sprite(kind, s) if s <= MAX_SCALE.get(kind, s) else None
                   for s in self.scales] for kind in KINDS
        }
        for kind in CAR_KINDS:
            base = self.images[kind]
            for k in range(1, TILTS + 1):
                for sign in (-1, 1):
                    self.images[f"{kind}:t{sign * k}"] = [
                        _tilted(e, sign * k * TILT_STEP) if sc <= TILT_MAX_SCALE else e
                        for e, sc in zip(base, self.scales)]
            for f in range(GHOST_FRAMES):
                self.images[f"{kind}:ghost{f}"] = [_ghost(e, f) for e in base]

    @classmethod
    def shared(cls) -> SpriteCache:
        """The one cache the game uses: built on first use, never again."""
        if cls._shared is None:
            cls._shared = cls()
        return cls._shared

    def index(self, scale: float) -> int | None:
        """The nearest size for a scale, or None when it is too near or too far to draw."""
        if scale > self.scales[-1] * 1.1 or scale < self.scales[0] / 1.2:
            return None
        i = round((math.log(scale) - self._log_lo) / self._log_step)
        return min(len(self.scales) - 1, max(0, i))

    def blit(self, surface: pygame.Surface, kind: str, x: float, y: float, scale: float,
             clip_y: float | None = None) -> bool:
        """Draw a sprite with its foot at (x, y). Below clip_y (a hill's crest) is hidden."""
        i = self.index(scale)
        if i is None:
            return False
        entry = self.images[kind][i]
        if entry is None:
            return False
        img, ax, ay = entry
        left, top = round(x) - ax, round(y) - ay
        if clip_y is not None:
            visible = round(clip_y) - top
            if visible <= 0:
                return False
            if visible < img.get_height():
                surface.blit(img, (left, top), (0, 0, img.get_width(), visible))
                return True
        surface.blit(img, (left, top))
        return True


# --- Backgrounds ----------------------------------------------------------------------------


class Background:
    """The inside of the fridge behind the road, for one view size.

    `far` (twice the view's width, repeating every view width) is the radiation-shield wall,
    the hanging coax and the cold haze at the horizon; it scrolls sideways with the road's
    heading. `plate` is the next stage's gold plate overhead, which stays put.
    """

    _cache: dict[tuple[int, int], Background] = {}

    def __init__(self, size: tuple[int, int]) -> None:
        self.width, self.height = size
        self.horizon = round(self.height * config.HORIZON)
        self.far = self._far()
        self.plate = self._plate()

    @classmethod
    def for_size(cls, size: tuple[int, int]) -> Background:
        size = (int(size[0]), int(size[1]))
        if size not in cls._cache:
            cls._cache[size] = cls(size)
        return cls._cache[size]

    def _far(self) -> pygame.Surface:
        W, H, hz = self.width, self.height, self.horizon
        k = H / 270 * SS  # the look's 270-high coordinates, at 2x
        big = pygame.Surface((2 * W * SS, H * SS))
        bw = big.get_width()
        # the cold radiation-shield wall, darker overhead
        for y in range(0, round(hz * SS) + 1):
            t = y / (hz * SS)
            pygame.draw.line(big, mix((10, 14, 34), (96, 150, 200), t ** 2.2), (0, y), (bw, y))
        # the next stage's plate far below, seen past a crest: copper fading into the haze
        top, depth = round(hz * SS), round(48 * k)
        for y in range(top, big.get_height()):
            t = min(1.0, (y - top) / depth)
            col = mix((150, 160, 170), (150, 92, 50), t ** 0.7)
            pygame.draw.line(big, col, (0, y), (bw, y))
        # the wall's panel seams: 20 per view width, so the picture repeats
        seam = mix((20, 30, 60), (110, 160, 210), 0.35)
        for i in range(40):
            x = round((i + 0.5) * W * SS / 20)
            pygame.draw.line(big, seam, (x, round(30 * k)), (x, round(hz * SS)), SS)
        # hanging coax far away, repeated every view width
        rnd = random.Random(3)
        for _ in range(26):
            x = rnd.uniform(0, W)
            y1 = rnd.uniform(60, 108) * k
            col = mix((70, 90, 120), (150, 170, 190), rnd.random())
            for rep in (-W, 0, W, 2 * W):
                px = round((x + rep) * SS)
                pygame.draw.line(big, col, (px, 0), (px, round(y1)), max(1, round(1.2 * SS)))
                pygame.draw.circle(big, (200, 170, 90), (px, round(y1)), round(1.6 * SS))
        # cold mist at the horizon
        band = round(20 * k)
        mist = pygame.Surface((bw, 2 * band), pygame.SRCALPHA)
        for y in range(2 * band):
            a = round(110 * (1 - abs(y - band) / band))
            pygame.draw.line(mist, (180, 220, 255, a), (0, y), (bw, y))
        big.blit(mist, (0, round(hz * SS) - band))
        return pygame.transform.smoothscale(big, (2 * W, H))

    def _plate(self) -> pygame.Surface:
        W = self.width
        k = self.height / 270 * SS
        sx = W / 960 * SS
        h = round(76 * k)
        big = pygame.Surface((W * SS, h), pygame.SRCALPHA)

        def P(px, py):
            return (round(px * sx), round(py * k))

        # a gold disc seen from below, with its standoffs
        pygame.draw.polygon(big, (150, 110, 40), [P(*p) for p in (
            (0, 0), (960, 0), (960, 26), (960 * 0.82, 40), (480, 46), (960 * 0.18, 40), (0, 26))])
        pygame.draw.polygon(big, (196, 150, 60), [P(*p) for p in (
            (0, 0), (960, 0), (960, 18), (480, 34), (0, 18))])
        for i in range(9):
            x = 40 + i * 110
            top = 30 + 8 * math.sin(i)
            pygame.draw.line(big, (210, 200, 180), P(x, top), P(x, 70), max(1, round(2 * SS)))
            pygame.draw.circle(big, (240, 220, 160), P(x, top), round(3 * SS))
        rim = [(0, 26), (960 * 0.18, 40), (480, 46), (960 * 0.82, 40), (960, 26)]
        pygame.draw.lines(big, (240, 210, 120), False, [P(*p) for p in rim], SS)
        plate = pygame.transform.smoothscale(big, (W, h // SS))
        _rle(plate)
        return plate

    def draw(self, surface: pygame.Surface, offset: float) -> None:
        """The far layer scrolled `offset` pixels to the left, then the plate on top."""
        off = int(offset) % self.width
        surface.blit(self.far, (0, 0), (off, 0, self.width, self.height))
        surface.blit(self.plate, (0, 0))
