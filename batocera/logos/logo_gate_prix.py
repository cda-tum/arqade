"""GATE PRIX: a racing livery, the P1 car through the glowing H gate.

The hero is the game's one move: steering through the right arch. Seen from
behind, as the game is, P1's blue car (the game's own draw_car, boosting,
its draw_flame jets lit) drives into the semicircular H arch (draw_arch, lit:
its glow, its light curtain and the gold badge at its crown), on the game's
own road: the dark anodised deck, the gold and white rumble, the cyan
waveguide dashes. The road bends away to the right past the gate, so
the race reads left to right, and the LIGHT SPEED! warp's own star streaks
(Renderer._tunnel_frame, sparser) rush out of the arch round it. Behind is
the deep cryo-blue of the fridge's shield wall with its cold mist at the
horizon.

The look is a motorsport livery, which no other icon has: GATE PRIX in heavy
italic race lettering (the game's own DejaVu Sans Condensed Bold), white with
speed cuts trailing off to the left, over the finish line's chequer, and the
gold of the H gate as its one accent.
"""

from __future__ import annotations

import math
import random
import sys

import kit
import pygame

sys.path.insert(0, str(kit.ROOT / "gate-prix/src"))
from gate_prix import config, road  # noqa: E402
from gate_prix.sprites import draw_arch, draw_car, draw_flame  # noqa: E402

ROM = "gate_prix"
FONT = kit.ROOT / "gate-prix/src/gate_prix/assets/fonts/DejaVuSansCondensed-Bold.ttf"
SS = 2                       # every scene is drawn at SS times its size, then smoothscaled
BLUE = config.PLAYER_COLORS["p1"]
GOLD = config.GATE_COLORS["H"]
WHITE = (255, 255, 255)
INK = (8, 10, 24)
SKY = [(6, 8, 24), (10, 14, 34), (26, 44, 92), (96, 150, 200)]  # the shield wall, darkest overhead
GROUND = [(10, 14, 34), (16, 22, 48)]
MIST = (180, 220, 255)
STREAK = (150, 200, 255)  # the warp's pale blue streaks (the rest are white)
STREAKS = 44
SLANT = 0.24


# --- the scene ------------------------------------------------------------------------------


def scene(size: tuple[int, int], horizon: float, arch_at: tuple[float, float], arch_r: float,
          keep_out: tuple[float, float, float, float]) -> pygame.Surface:
    """The road, the H arch and the car, at SS times `size`.

    `arch_at` is the arch's foot (its centre on the road), `arch_r` its outer
    radius, both in output pixels; the road's vanishing point is under it.
    No streak crosses `keep_out` (x, y, w, h, in output pixels): the title goes there.
    """
    w, h = size[0] * SS, size[1] * SS
    hy = round(horizon * SS)
    ax, ay, r = arch_at[0] * SS, arch_at[1] * SS, arch_r * SS
    keep_out = [pygame.Rect(*(round(v * SS) for v in keep_out))]
    s = pygame.Surface((w, h), pygame.SRCALPHA)
    s.blit(kit.gradient((w, hy + 1), SKY), (0, 0))
    s.blit(kit.gradient((w, h - hy), GROUND), (0, hy))
    # the road: its half-width grows in proportion to the depth below the horizon; at the
    # arch's foot it is RW arch radii, so the arch spans most of it
    rw = 1.55 * r / (ay - hy)
    seg = 0.9  # segments alternate every `seg` of 1/depth
    for y in range(hy + 1, h):
        d = y - hy
        z = (ay - hy) / d  # 1 at the arch, growing into the distance
        cx = ax + (0.18 * (z - 1) ** 2 * r / z if z > 1 else 0)  # bending right past the arch
        hw = rw * d
        band = int(z / seg * 4) % 2
        rumble = road.RUMBLE[band]
        deck = road.ROAD[int(z / seg * 2) % 2]
        edge = hw * config.RUMBLE
        pygame.draw.line(s, rumble, (cx - edge, y), (cx + edge, y))
        pygame.draw.line(s, deck, (cx - hw, y), (cx + hw, y))
        if int(z / seg * 3) % 2 == 0:
            cw = max(1.0, hw * road.CENTRE_HALF_WIDTH)
            pygame.draw.line(s, road.CENTRE, (cx - cw, y), (cx + cw, y))
    # the cold mist at the horizon
    band = round(h * 0.035)
    mist = pygame.Surface((w, 2 * band), pygame.SRCALPHA)
    for y in range(2 * band):
        a = round(120 * (1 - abs(y - band) / band) ** 1.5)
        pygame.draw.line(mist, (*MIST, a), (0, y), (w, y))
    s.blit(mist, (0, hy - band))
    # the LIGHT SPEED! warp's star streaks, rushing out of the arch
    warp(s, (ax, hy), r, keep_out)
    # the lit arch's glow, then the arch and, passing through it, the car
    s.blit(kit.radial((w, h), (ax, ay - r * 0.55), r * 2.0, kit.shade(GOLD, 0.55)), (0, 0),
           special_flags=pygame.BLEND_RGB_ADD)
    u_arch = r / config.ARCH_HALF_WIDTH
    draw_arch(s, ax, ay, u_arch, "H", True)
    car_y = ay + 0.06 * r
    u_car = u_arch * (car_y - hy) / (ay - hy) * 0.86  # a little under the game's size: more arch shows
    car_x = ax - 0.02 * r
    draw_car(s, car_x, car_y, u_car, BLUE)
    draw_flame(s, car_x, car_y, u_car, 1)
    return s


def warp(s: pygame.Surface, vp: tuple[float, float], r: float, keep_out: list[pygame.Rect]) -> None:
    """The warp's star-streak tunnel (Renderer._tunnel_frame): white and pale blue streaks
    from round the vanishing point out towards the edges, squashed to the view's ellipse.
    Sparser than the game's, and none crossing the `keep_out` rects (the title)."""
    rnd = random.Random(11)
    lay = pygame.Surface(s.get_size(), pygame.SRCALPHA)
    cx, cy = vp
    reach = max(s.get_size())
    drawn = 0
    while drawn < STREAKS:
        a = rnd.uniform(0, 2 * math.pi)
        phase = rnd.uniform(0.2, 1.0)
        r0 = r * 0.9 + reach * 0.5 * phase ** 1.6
        r1 = r0 + reach * (0.1 + 0.3 * phase)
        p0 = (cx + r0 * math.cos(a), cy + r0 * 0.55 * math.sin(a))
        p1 = (cx + r1 * math.cos(a), cy + r1 * 0.55 * math.sin(a))
        if any(k.clipline(p0, p1) for k in keep_out):
            continue
        col = WHITE if rnd.random() < 0.6 else STREAK
        width = max(2, round(reach / 1024 * (1.5 + 3.5 * phase)))
        pygame.draw.line(lay, (*col, round(70 + 150 * phase)), p0, p1, width)
        drawn += 1
    s.blit(lay, (0, 0))


# --- the lettering ----------------------------------------------------------------------


def _shear(surf: pygame.Surface, slant: float) -> pygame.Surface:
    """Italicise: shift each row right by slant * its height above the baseline."""
    w, h = surf.get_size()
    out = pygame.Surface((w + round(h * slant), h), pygame.SRCALPHA)
    for y in range(h):
        out.blit(surf, (round((h - y) * slant), y), (0, y, w, 1))
    return out


def chequer(width: int, rows: int, cell: int) -> pygame.Surface:
    """The finish line's chequer, `rows` squares high, fading out to the left."""
    cols = math.ceil(width / cell)
    s = pygame.Surface((cols * cell, rows * cell), pygame.SRCALPHA)
    for j in range(rows):
        for i in range(cols):
            col = road.CHEQUER[(i + j) % 2]
            pygame.draw.rect(s, col, (i * cell, j * cell, cell, cell))
    fade = pygame.Surface(s.get_size(), pygame.SRCALPHA)
    for x in range(fade.get_width()):
        t = x / fade.get_width()
        a = round(255 * min(1.0, t / 0.45) ** 1.3)
        pygame.draw.line(fade, (255, 255, 255, a), (x, 0), (x, fade.get_height()))
    s.blit(fade, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
    return s


def title(width: int) -> pygame.Surface:
    """GATE PRIX in heavy italic race lettering, speed cuts trailing left, on the chequer."""
    px = 300
    shape = kit.text_shape("GATE PRIX", FONT, px, pixel=False, tracking=4)
    shape = kit.trim(shape)
    tw, th = shape.get_size()
    # two speed cuts through the lower third of the letters, running out to the left
    lead = round(th * 0.9)
    letters = pygame.Surface((tw + lead, th), pygame.SRCALPHA)
    letters.blit(shape, (lead, 0))
    cuts = [(0.70, 0.045), (0.83, 0.045)]  # below the bowls of P and R, so no sliver is left
    for cy, ch in cuts:
        pygame.draw.rect(letters, (0, 0, 0, 0), (lead, round(th * cy), tw, max(2, round(th * ch))))
    lines = pygame.Surface(letters.get_size(), pygame.SRCALPHA)
    for k, (cy, ch) in enumerate(cuts):
        y = round(th * cy)
        length = round(lead * (0.95 - 0.3 * k))
        for x in range(length):
            a = round(255 * (x / length) ** 1.5)
            pygame.draw.line(lines, (255, 255, 255, a), (lead - length + x, y), (lead - length + x,
                             y + max(2, round(th * ch)) - 1))
    # the ink: an outline round the letters and a hard drop to the lower left
    margin = 40
    body = kit.pad(letters, margin)
    outline = kit.dilate(body, 9, INK)
    out = pygame.Surface(body.get_size(), pygame.SRCALPHA)
    d = 14
    drop = kit.tint(outline, GOLD)
    out.blit(drop, (-d // 2, d))
    out.blit(outline, (0, 0))
    paint = kit.gradient(body.get_size(), [WHITE, WHITE, (210, 228, 255)])
    out.blit(kit.tint(body, paint), (0, 0))
    out.blit(kit.pad(lines, margin), (0, 0))
    out = _shear(out, SLANT)
    # the chequer under it, slanted with it
    cell = round(th * 0.13)
    flag = chequer(round(tw * 1.02), 2, cell)
    fl = pygame.Surface((flag.get_width() + 2 * margin, flag.get_height() + 2 * margin), pygame.SRCALPHA)
    fl.blit(flag, (margin, margin))
    fl = _shear(fl, SLANT)
    total = pygame.Surface((max(out.get_width(), fl.get_width() + lead) + 20,
                            out.get_height() + fl.get_height()), pygame.SRCALPHA)
    total.blit(fl, (lead + margin * 0 - round(fl.get_height() * SLANT * 0.5) - 20,
                    out.get_height() - margin - 6))
    total.blit(out, (0, 0))
    total = kit.trim(total)
    return kit.fit(total, width, width)


# --- the three layouts --------------------------------------------------------------------


def art(size: int, pad: int = 0) -> pygame.Surface:
    """The square logo, `size` px; with `pad`, on a canvas `pad` px bigger on every side
    (see generate_logos.py: extended/), the road, the wall and the warp running on."""
    full = size + 2 * pad
    big = scene((full, full), pad + size * 0.5, (pad + size * 0.53, pad + size * 0.77), size * 0.245,
                (0, 0, full, pad + size * 0.34))
    out = pygame.transform.smoothscale(big, (full, full)).convert()
    out = kit.finish(out, vignette_strength=0.45)
    kit.blit_center(out, title(round(size * 0.86)), (pad + size * 0.5, pad + size * 0.2))
    return out


def wide(width: int, height: int) -> pygame.Surface:
    big = scene((width, height), height * 0.44, (width * 0.27, height * 0.78), height * 0.3,
                (width * 0.38, 0, width * 0.6, height * 0.5))
    out = pygame.transform.smoothscale(big, (width, height)).convert()
    out = kit.finish(out, vignette_strength=0.45)
    kit.blit_center(out, title(round(width * 0.52)), (width * 0.655, height * 0.27))
    return out


def marquee() -> pygame.Surface:
    return title(1400)
