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


def draw_arch(surf, x, y, u, gate, lit):
    """A gate: a semicircular arch standing on the track, both feet on the road, a light
    curtain under it and the gate's letter on a badge at its crown."""
    col = config.GATE_COLORS[gate]
    r = config.ARCH_HALF_WIDTH * u  # its outer radius: the feet are 2r apart
    t = max(2.0, 0.16 * r)  # its thickness
    if lit:
        _glow(surf, x, y - r * 0.55, r * 1.3, col, 110)
    _ellipse(surf, (0, 0, 0, 110), x - r * 1.05, y - r * 0.05, r * 2.1, r * 0.14)
    # the light curtain: the upper half of the inner disc
    lay = _layer(surf)
    pygame.draw.polygon(lay, (*col, 85 if lit else 50), _band(x, y, r - t, 0))
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
    bw = 0.4267 * r  # the badge at the crown
    _circle(surf, (14, 16, 30), x, y - r, bw * 0.55)
    _circle(surf, col, x, y - r, bw * 0.48)
    _text(surf, gate, max(6, round(0.36 * r)), WHITE, x, y - r + 1)


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

# kind: (draw(surf, x, y, u), extents (left, top, right, bottom) in road half-widths)
_A = config.ARCH_HALF_WIDTH
_ARCH_EXT = (-1.06 * _A, -1.27 * _A, 1.06 * _A, 0.1 * _A)
_LIT_EXT = (-1.31 * _A, -1.86 * _A, 1.31 * _A, 0.76 * _A)


def _kinds():
    kinds = {
        "coax": (draw_coax, (-0.03, -0.51, 0.03, 0.01)),
        "attenuator": (draw_attenuator, (-0.04, -0.13, 0.04, 0.01)),
        "standoff": (draw_standoff, (-0.04, -0.9, 0.04, 0.01)),
        "box": (draw_box, (-0.24, -0.55, 0.24, 0.03)),
        "clone": (lambda s, x, y, u: draw_car(s, x, y, u, GHOST, ghost=True), (-0.21, -0.15, 0.21, 0.03)),
    }
    for g in GATES:
        kinds[f"arch:{g}"] = (lambda s, x, y, u, g=g: draw_arch(s, x, y, u, g, False), _ARCH_EXT)
        kinds[f"arch:{g}:lit"] = (lambda s, x, y, u, g=g: draw_arch(s, x, y, u, g, True), _LIT_EXT)
    for name, col in config.CAR_COLORS.items():
        kinds[f"car:{name}"] = (lambda s, x, y, u, col=col: draw_car(s, x, y, u, col), (-0.21, -0.15, 0.21, 0.03))
    return kinds


_KIND_TABLE = _kinds()
KINDS = tuple(_KIND_TABLE)


def sprite_scales() -> list[float]:
    lo, hi, n = config.SPRITE_SCALE_MIN, config.SPRITE_SCALE_MAX, config.SPRITE_SIZES
    return [lo * (hi / lo) ** (i / (n - 1)) for i in range(n)]


def render_sprite(kind: str, scale: float) -> tuple[pygame.Surface, int, int]:
    """One sprite at one scale: drawn at 2x, cropped, smoothscaled. Its surface and anchor."""
    draw, (left, top, right, bottom) = _KIND_TABLE[kind]
    u = scale * SS
    pad = 4 * SS
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
        self.images: dict[str, list[tuple[pygame.Surface, int, int]]] = {
            kind: [render_sprite(kind, s) for s in self.scales] for kind in KINDS
        }

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
        img, ax, ay = self.images[kind][i]
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
