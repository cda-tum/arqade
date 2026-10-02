"""Qurves: a light-cycle duel on the game's own arena, seen in perspective.

The board is built exactly the way the game builds it -- render.make_background()
for the floor, grid and walls, the Renderer's own trail stamps (solid capsules,
dashed ghost copies), gate tokens and Fx rings -- and then laid down as a floor
running off to a horizon, one scanline at a time ("mode 7"). On it, P1's blue
trail drives into an H gate and forks into two mirrored ghost copies while
P2's red rival swings in from the right to cut them off. The heads are the
game's own glow sprites, stood upright and sized by depth. QURVES sits in the
sky above, blue to red like the cabinet's two sides, with the two players'
trails racing along its edges the way the title screen's do.
"""

from __future__ import annotations

import functools
import random
import sys

import kit
import pygame

sys.path.insert(0, str(kit.ROOT / "qurves/src"))
from qurves import config, render  # noqa: E402
from qurves.fx import Fx  # noqa: E402

ROM = "qurves"
BLUE, RED = config.PLAYER_COLORS["p1"], config.PLAYER_COLORS["p2"]
PURPLE = config.PLAYER_COLORS["p4"]
CELL, HUD = config.CELL, config.HUD_HEIGHT
UP, DOWN, LEFT, RIGHT = (0, -1), (0, 1), (-1, 0), (1, 0)

# The camera: horizon height, focal length and eye height, in screen px and
# cells. CAM_U is the arena column straight ahead.
HORIZON = 0.34
FOCAL = 0.62
NEAR = 19.0  # distance in cells from the eye to the bottom screen row...
NEAR_ROW = config.GRID_H - 1.6  # ...which shows this arena row, just inside the wall
CAM_U = 82.0
UPSCALE = 3  # the board is smoothscaled up this much before projecting


# --- the board (game pixels, the game's own drawing) ----------------------------


def _path(start, *moves):
    """Cells along a trail: from `start`, (direction, length) per leg."""
    cells = [start]
    for (dx, dy), n in moves:
        for _ in range(n):
            x, y = cells[-1]
            cells.append((x + dx, y + dy))
    return cells


# Grid cells of the duel. y grows towards the camera, so UP drives away.
FORK = (71, 62)
BLUE_IN = _path((71, 84), (UP, 22))
COPY_L = _path(FORK, (LEFT, 12), (UP, 13), (LEFT, 10))  # the bike turns left at the H...
COPY_R = _path(FORK, (RIGHT, 12), (UP, 13), (RIGHT, 10))  # ...its mirrored twin right
RED_RUN = _path((111, 1), (DOWN, 77), (LEFT, 24))
OLD_RED = _path((150, 30), (LEFT, 14), (UP, 18))  # an older stretch, far off
# (kind, cell, billboard scale): the H being taken, and two more further on
GATES = [("H", FORK, 1.25), ("Z", (50, 22), 0.8), ("X", (122, 30), 0.8)]


@functools.cache
def renderer() -> render.Renderer:
    """The game's renderer, only for its pre-rendered stamps, heads and tokens."""
    return render.Renderer(pygame.Surface((render.W, render.H)))


def board() -> pygame.Surface:
    """The arena, game pixels, with every trail stamped on as the game would."""
    r = renderer()
    b = render.make_background()
    # make_background() darkens the edges for a flat screen; brighten the grid
    # back up so it still reads once it recedes into the distance.
    b.blit(b, (0, 0), special_flags=pygame.BLEND_ADD)
    for cells, player in ((BLUE_IN, "p1"), (RED_RUN, "p2"), (OLD_RED, "p2")):
        for a, c in zip(cells, cells[1:]):
            r._stamp(b, r.solid_stamps[player], a, c, pygame.BLEND_MAX)
    ghost = pygame.Surface((render.W, render.H), pygame.SRCALPHA)
    for cells in (COPY_L, COPY_R):
        for a, c in zip(cells, cells[1:]):
            if (c[0] + c[1]) % 2 == 0:  # dashed, like Renderer._apply's ghost trails
                r._stamp(ghost, r.ghost_stamps["p1"], a, c, pygame.BLEND_RGBA_MAX)
    b.blit(ghost, (0, 0))
    for kind, pos, _ in GATES:
        token = r.tokens[kind][7]
        b.blit(token, token.get_rect(center=render.cell_px(pos)), special_flags=pygame.BLEND_ADD)
    # the Split's measurement rings and sparks, mid-animation, from the game's Fx
    fx = Fx(random.Random(4))
    fx.ring(render.cell_px(FORK), BLUE, life=0.9)
    fx.burst(render.cell_px(FORK), render.lighten(BLUE, 0.4), count=60, speed=150, life=0.8)
    fx.update(0.12)
    fx.ring(render.cell_px(FORK), render.lighten(BLUE, 0.5), life=0.45)
    fx.update(0.1)
    fx.draw(b)
    return b.subsurface((0, HUD, render.W, config.GRID_H * CELL)).copy()


# --- projection ----------------------------------------------------------------


class Camera:
    def __init__(self, size: int) -> None:
        self.size = size
        self.hy = round(size * HORIZON)
        self.f = size * FOCAL
        self.h = NEAR * (size - self.hy) / self.f  # eye height, in cells

    def depth(self, y: float) -> float:
        """Distance in cells of the floor seen at screen row y."""
        return self.h * self.f / (y - self.hy)

    def project(self, u: float, v: float) -> tuple[float, float, float]:
        """Arena cell (u, v) -> (screen x, screen y, px per cell there)."""
        d = NEAR + (NEAR_ROW - v)
        k = self.f / d
        return self.size / 2 + (u - CAM_U) * k, self.hy + self.h * k, k


def floor(cam: Camera, src: pygame.Surface) -> pygame.Surface:
    """Lay `src` (the arena, game px) down as a floor: one strip per screen row,
    scaled to that row's width, darkening into the distance."""
    size = cam.size
    big = pygame.transform.smoothscale(src, (src.get_width() * UPSCALE, src.get_height() * UPSCALE))
    px = CELL * UPSCALE  # board px per cell
    out = pygame.Surface((size, size))
    out.fill((0, 0, 0))
    for y in range(cam.hy + 1, size):
        d = cam.depth(y + 0.5)
        v = NEAR_ROW - (d - NEAR)  # arena row seen here
        if v < 0:  # past the far wall
            continue
        sy = min(big.get_height() - 1, int(v * px))
        k = cam.f / d  # screen px per cell
        w = round(big.get_width() / px * k)
        if w < 2:
            continue
        strip = pygame.transform.smoothscale(big.subsurface((0, sy, big.get_width(), 1)), (w, 1))
        fog = max(0.0, min(1.0, 1.4 - d / 100))
        if fog < 1:
            strip.fill(kit.shade((255, 255, 255), fog), special_flags=pygame.BLEND_MULT)
        out.blit(strip, (round(size / 2 - CAM_U * k), y))
    return out


def glow_alpha(color, radius: int, k: float = 1.0) -> pygame.Surface:
    """render.make_glow() on transparency instead of black: the same falloff,
    carried in alpha, so it can go onto the marquee too."""
    surf = pygame.Surface((2 * radius + 1, 2 * radius + 1), pygame.SRCALPHA)
    for r in range(radius, 0, -1):
        f = (1 - r / (radius + 1)) ** 1.1
        pygame.draw.circle(surf, (*render.lighten(color, 0.6 * f), round(255 * min(1.0, f * k * 1.4))),
                           (radius, radius), r)
    pygame.draw.circle(surf, render.lighten(color, 0.5), (radius, radius), max(2, radius // 4))
    pygame.draw.circle(surf, render.lighten(color, 0.9), (radius, radius), max(2, radius // 6))
    return surf


def billboard(cam: Camera, sprite: pygame.Surface, cell, cells: float, lift: float = 0.0):
    """`sprite` stood upright on arena cell `cell`, `cells` wide, its centre
    `lift` sprite-heights above the floor. Returns (image, screen centre)."""
    x, y, ppc = cam.project(cell[0] + 0.5, cell[1] + 0.5)
    w = max(4, round(ppc * cells))
    img = pygame.transform.smoothscale(sprite, (w, round(w * sprite.get_height() / sprite.get_width())))
    return img, (x, y - lift * img.get_height())


# --- lettering --------------------------------------------------------------------


def neon(size, points, color, width: int, glow_r: int = 18) -> pygame.Surface:
    """A light trail on transparency: soft colour halo, then a near-white core
    (the same two-tone look as render.TitleTrails)."""
    shape = pygame.Surface(size, pygame.SRCALPHA)
    pygame.draw.lines(shape, (255, 255, 255), False, points, width)
    for p in points:
        pygame.draw.circle(shape, (255, 255, 255), p, width // 2)
    out = kit.glow(shape, color, glow_r, 1.0)
    out.blit(kit.glow(shape, render.lighten(color, 0.3), glow_r // 3, 1.0), (0, 0))
    out.blit(kit.tint(shape, render.lighten(color, 0.6)), (0, 0))
    return out


def title(scale: int = 18) -> pygame.Surface:
    """QURVES in the ARQADE style, shading blue to red across the word like
    the cabinet's two sides (the game's own logo, render.make_logo, runs
    through all four player colours)."""
    shape = kit.text_shape("QURVES", kit.PIXEL_FONT, 8 * scale, tracking=1)
    return kit.wordmark(
        shape,
        [render.lighten(BLUE, 0.25), BLUE, PURPLE, RED, render.lighten(RED, 0.2)],
        vertical=False,
        gap=max(3, scale // 4),
        outline=max(4, scale // 3),
        extrude=max(6, scale // 2),
        extrude_color=(26, 22, 70),
        glow_color=(120, 90, 255),
        glow_radius=max(18, scale * 2),
        glow_strength=0.75,
        square=True,
    )


def framed_title(scale: int = 18) -> pygame.Surface:
    """The wordmark with a blue trail racing in along its top and a red one
    along its bottom, heads glowing -- the title screen's chasing trails."""
    word = title(scale)
    w, h = word.get_size()
    m = scale * 4
    out = pygame.Surface((w + 2 * m, h + 2 * m), pygame.SRCALPHA)
    ox, oy = m, m
    lw = max(4, scale // 3)
    top, bot = oy + scale * 2, oy + h - scale * 2
    blue = [(ox - m // 2, top), (ox + w * 0.55, top)]
    red = [(ox + w + m // 2, bot), (ox + w * 0.45, bot)]
    out.blit(neon(out.get_size(), blue, BLUE, lw, scale), (0, 0))
    out.blit(neon(out.get_size(), red, RED, lw, scale), (0, 0))
    out.blit(word, (ox, oy))
    for (x, y), c in ((blue[-1], BLUE), (red[-1], RED)):
        kit.blit_center(out, glow_alpha(c, round(scale * 1.6)), (x, y))
    return kit.trim(out)


# --- the art --------------------------------------------------------------------


def art(size: int) -> pygame.Surface:
    cam = Camera(size)
    far_y = round(cam.project(0, 0)[1])  # where the far arena wall meets the sky
    surf = pygame.Surface((size, size))
    # sky: the game's background colour, deepening to a violet haze at the wall
    surf.fill(config.COLOR_BACKGROUND)
    surf.blit(kit.gradient((size, far_y), [config.COLOR_BACKGROUND, config.COLOR_BACKGROUND,
                                          (30, 22, 72)]), (0, 0))
    surf.blit(kit.radial((size, size), (size * 0.5, far_y), size * 0.6, (80, 50, 170), 0.8),
              (0, 0), special_flags=pygame.BLEND_ADD)

    ground = floor(cam, board())
    surf.blit(ground, (0, 0), special_flags=pygame.BLEND_ADD)
    surf.blit(kit.blur(ground, 24), (0, 0), special_flags=pygame.BLEND_ADD)  # bloom

    # the far wall's edge catching the light, brightest straight ahead
    line = kit.gradient((size, 3), [(0, 0, 0), config.COLOR_WALL, (200, 190, 255), config.COLOR_WALL,
                                    (0, 0, 0)], vertical=False)
    surf.blit(line, (0, far_y - 2), special_flags=pygame.BLEND_ADD)

    # Gates and bikes stand up off the floor, far ones first.
    r = renderer()
    things = [(pos[1], "gate", kind, pos, sc) for kind, pos, sc in GATES]
    things += [(cells[-1][1], "bike", color, cells[-1], sc)
               for cells, color, sc in ((COPY_L, BLUE, 7.0), (COPY_R, BLUE, 7.0), (RED_RUN, RED, 6.0))]
    for _, what, a, cell, sc in sorted(things):
        if what == "gate":
            token = r.tokens[a][7]
            img, pos = billboard(cam, token, cell, 5.6 * sc, lift=0.5)
            surf.blit(img, img.get_rect(center=(round(pos[0]), round(pos[1]))), special_flags=pygame.BLEND_ADD)
        else:
            img, pos = billboard(cam, glow_alpha(a, 40), cell, sc)
            w = img.get_width()
            surf.blit(kit.radial((size, size), pos, w * 1.4, a, 0.6), (0, 0), special_flags=pygame.BLEND_ADD)
            kit.blit_center(surf, img, pos)
            hot = render.make_glow(a, max(3, w // 9))  # the game's head sprite, at this size
            surf.blit(hot, hot.get_rect(center=(round(pos[0]), round(pos[1]))), special_flags=pygame.BLEND_ADD)
            # an anamorphic flare across the head, like a light seen through glass
            fw, fh = round(w * 2.2), max(3, w // 14)
            flare = pygame.Surface((fw, fh * 3))
            flare.fill((0, 0, 0))
            flare.blit(kit.gradient((fw, fh), [(0, 0, 0), render.lighten(a, 0.6), (0, 0, 0)], vertical=False),
                       (0, fh))
            flare = kit.blur(flare, 2)
            surf.blit(flare, flare.get_rect(center=(round(pos[0]), round(pos[1]))), special_flags=pygame.BLEND_ADD)

    surf = kit.finish(surf, vignette_strength=0.55, scan=True)

    word = framed_title(19)
    if word.get_width() > size:
        word = kit.fit(word, size, size * 0.4)
    kit.blit_center(surf, word, (size / 2, size * 0.2))
    tag = kit.tagline("light cycles in superposition", size=round(size * 0.026),
                      color=(215, 220, 255), tracking=round(size * 0.006))
    kit.blit_center(surf, tag, (size / 2, size * 0.375))
    return surf


def marquee() -> pygame.Surface:
    return framed_title(24)
