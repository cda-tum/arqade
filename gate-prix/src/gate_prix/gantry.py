"""The start and finish gantry over the lap line, drawn at its exact size every frame.

Every other sprite is a blit of the nearest of SPRITE_SIZES pre-drawn sizes, 18% apart.
That is invisible on a car or an arch, but the gantry spans the whole road: at the start
the cars accelerate under it from just behind the line, and it swept through six cached
sizes in under a second, jumping by up to ~100 px at its posts each time, while its start
lights (placed exactly) slid in and out of their sockets. On the cabinet it flickered.

So it is drawn from its parts at the exact scale the road reports, like the road itself:
two posts and a banner as filled rectangles, its chequered ends as squares, and the
pre-rendered pieces it needs blitted onto that frame: the "GATE PRIX" lettering (at
TEXT_SIZES, a few percent apart and centred, so a size step never shows), the posts'
shadows, and the five start lights, lit or unlit, at LIGHT_RADII. The lights and their
sockets are one and the same disc, so a light can never leave its socket. About thirty
fills and blits, and only while a gantry is in sight.

`RoadView.draw_sprites` calls `Gantry.shared().draw` for every "gantry" sprite, in its
place in the far-to-near order, so a car nearer than the gantry is drawn over it (and its
lights). Set `lights` to ("red", n) or ("green", 5) before drawing a view.
"""

from __future__ import annotations

from collections import deque

import pygame

from gate_prix import config
from gate_prix.sprites import font, mix

POST = 1.3  # the posts stand this far out (road half-widths), past the rumble
POST_W = 0.07  # their width
TOP = 1.62  # the banner's top, above the road
BANNER = 1.18  # and its bottom
EDGE = 0.03  # the gold edges along the banner
OVERHANG = 0.08  # the banner reaches this far past the posts
LIGHT_Y = 1.07  # the start lights' centres, above the road
LIGHT_X = (-0.3, -0.15, 0.0, 0.15, 0.3)
LIGHT_R = 0.055
HOUSING = 0.09  # the lights' housing reaches this far past the outer lights
CHEQUER_CELL = 0.05  # the banner's chequered ends: 7 squares across, 2 rows, each end
CHEQUER_COLUMNS = 7
CHEQUER_ROW = 0.17
CHEQUER_INSET = 0.05
TEXT = 0.3  # the lettering's size, road half-widths
REACH = POST + OVERHANG  # its half-width: past this either side nothing of it is drawn

NAVY = (18, 22, 44)
GOLD = (220, 170, 60)
LETTERS = (255, 230, 120)
STEEL = (90, 96, 116)
SHINE = (200, 206, 224)
HOUSING_INK = (12, 12, 20)
CHEQUER = ((240, 240, 246), (30, 30, 40))
LIGHT_COLOURS = {"red": (255, 40, 50), "green": (60, 255, 120)}
LIGHT_RADII = tuple(range(2, 42, 2))  # px
TEXT_SIZES = tuple(sorted({round(6 * 1.06 ** k) for k in range(60) if 6 * 1.06 ** k <= 190}))
SHADOW_WIDTHS = tuple(sorted({round(3 * 1.12 ** k) for k in range(40) if 3 * 1.12 ** k <= 260}))


def _nearest(values: tuple[int, ...], want: float) -> int:
    """The index of the value nearest to `want` (values ascending)."""
    best = 0
    for i, v in enumerate(values):
        if abs(v - want) < abs(values[best] - want):
            best = i
    return best


class Gantry:
    _shared: Gantry | None = None

    def __init__(self) -> None:
        self.lights: tuple[str, int] = ("green", config.GANTRY_LIGHTS)
        # the last few gantries drawn, (rect, scale), for the tests (the renderer clears it
        # every frame; bounded, so a tool that never does can't grow it)
        self.drawn: deque[tuple[pygame.Rect, float]] = deque(maxlen=8)
        self._discs = {name: [self._disc(r, col) for r in LIGHT_RADII]
                       for name, col in LIGHT_COLOURS.items()}
        self._discs["off"] = [self._socket(r) for r in LIGHT_RADII]
        self._text = [self._letters(px) for px in TEXT_SIZES]
        self._shadows = [self._shadow(w) for w in SHADOW_WIDTHS]

    @classmethod
    def shared(cls) -> Gantry:
        if cls._shared is None:
            cls._shared = cls()
        return cls._shared

    # --- Drawn once ---------------------------------------------------------------------

    @staticmethod
    def _disc(r: int, col) -> pygame.Surface:
        """A lit start light: a glowing disc, its glow 3 radii out."""
        n = r * 6
        s = pygame.Surface((n, n), pygame.SRCALPHA)
        c = n // 2
        for k in range(3 * r, r, -1):
            pygame.draw.circle(s, (*col, round(110 * (1 - (k - r) / (2 * r)) ** 2)), (c, c), k)
        pygame.draw.circle(s, col, (c, c), r)
        pygame.draw.circle(s, mix(col, (255, 255, 255), 0.6), (c - r // 3, c - r // 3), max(1, r // 2))
        return s

    @staticmethod
    def _socket(r: int) -> pygame.Surface:
        """An unlit start light: a dark disc with a dim ring, the same size as a lit one's
        surface, so both centre on the same point."""
        n = r * 6
        s = pygame.Surface((n, n), pygame.SRCALPHA)
        c = n // 2
        pygame.draw.circle(s, (50, 30, 34), (c, c), r)
        pygame.draw.circle(s, (90, 70, 74), (c, c), r, max(1, round(r * 0.22)))
        return s

    @staticmethod
    def _letters(px: int) -> pygame.Surface:
        face = font(px)
        fg = face.render("GATE PRIX", True, LETTERS)
        d = max(1, px // 14)
        s = pygame.Surface((fg.get_width() + d, fg.get_height() + d), pygame.SRCALPHA)
        s.blit(face.render("GATE PRIX", True, (8, 8, 20)), (d, d))
        s.blit(fg, (0, 0))
        return s

    @staticmethod
    def _shadow(w: int) -> pygame.Surface:
        h = max(1, round(w * 0.19))
        s = pygame.Surface((w, h), pygame.SRCALPHA)
        pygame.draw.ellipse(s, (0, 0, 0, 100), s.get_rect())
        return s

    # --- Per frame ----------------------------------------------------------------------

    def draw(self, view: pygame.Surface, x: float, y: float, u: float, clip_y: float) -> bool:
        """Draw a gantry with its foot at (x, y), u pixels per road half-width, hidden below
        clip_y (a crest). Whether any of it was in sight."""
        w, h = view.get_size()
        reach = REACH * u
        top = y - TOP * u
        if x + reach < 0 or x - reach > w or top > min(h, clip_y) or y < 0:
            return False
        old = view.get_clip()
        clip = pygame.Rect(0, 0, w, max(0, min(h, round(clip_y)))).clip(old)
        view.set_clip(clip)

        def fill(col, rect) -> None:
            # pygame 2.5.2's fill moves a rect that starts above or left of the surface to
            # 0 instead of cutting it off, so every rect is clipped here first
            r = clip.clip(rect)
            if r.w and r.h:
                view.fill(col, r)

        post = POST_W * u
        for side in (-1, 1):  # the posts, their shadows and gold feet
            px = x + side * POST * u
            sh = self._shadows[_nearest(SHADOW_WIDTHS, 3.2 * post)]
            view.blit(sh, (round(px - sh.get_width() / 2), round(y - sh.get_height() / 2)))
            left = round(px - post / 2)
            fill(STEEL, (left, round(top), max(1, round(px + post / 2) - left), round(y) - round(top)))
            fill(SHINE, (left, round(top), max(1, round(post * 0.3)), round(y) - round(top)))
            foot = round(px - 0.8 * post)
            fill(GOLD, (foot, round(y - 0.06 * u), max(1, round(px + 0.8 * post) - foot),
                        max(1, round(y) - round(y - 0.06 * u))))
        left, right = round(x - reach), round(x + reach)
        bottom = y - BANNER * u
        t, b = round(top), round(bottom)
        fill(NAVY, (left, t, right - left, b - t))
        edge = max(1, round(EDGE * u))
        fill(GOLD, (left, t, right - left, edge))
        fill(GOLD, (left, b - edge, right - left, edge))
        self._chequer(fill, x - reach + CHEQUER_INSET * u, top, u)
        span = CHEQUER_COLUMNS * CHEQUER_CELL * u
        self._chequer(fill, x + reach - CHEQUER_INSET * u - span, top, u)
        want = TEXT * u
        if want >= 5:
            img = self._text[_nearest(TEXT_SIZES, want)]
            view.blit(img, img.get_rect(center=(round(x), round((top + bottom) / 2))))
        # the lights' housing under the banner, and the five lights in it
        hx0, hx1 = round(x + (LIGHT_X[0] - HOUSING) * u), round(x + (LIGHT_X[-1] + HOUSING) * u)
        hb = round(y - (LIGHT_Y - 0.08) * u)
        fill(HOUSING_INK, (hx0, b, hx1 - hx0, max(1, hb - b)))
        r = LIGHT_R * u
        i = max(0, min(len(LIGHT_RADII) - 1, round(r / 2) - 1))
        colour, lit = self.lights
        ly = round(y - LIGHT_Y * u)
        for k, lx in enumerate(LIGHT_X):
            img = self._discs[colour if k < lit else "off"][i]
            half = img.get_width() // 2
            view.blit(img, (round(x + lx * u) - half, ly - half))
        view.set_clip(old)
        self.drawn.append((pygame.Rect(left, t, right - left, round(y) - t), u))
        return True

    @staticmethod
    def _chequer(fill, x0: float, top: float, u: float) -> None:
        """One chequered end of the banner: CHEQUER_COLUMNS squares across in 2 rows, each
        square's edges rounded on their own so the squares meet without gaps."""
        cell = CHEQUER_CELL * u
        y0 = top + CHEQUER_INSET * u
        ys = [round(y0 + k * CHEQUER_ROW * u) for k in range(3)]
        xs = [round(x0 + k * cell) for k in range(CHEQUER_COLUMNS + 1)]
        fill(CHEQUER[0], (xs[0], ys[0], xs[-1] - xs[0], ys[2] - ys[0]))
        for row in range(2):
            for k in range(row % 2, CHEQUER_COLUMNS, 2):
                fill(CHEQUER[1], (xs[k], ys[row], xs[k + 1] - xs[k], ys[row + 1] - ys[row]))
