"""Ion Surfer key art: the blue ion surfing over the crest of a big trap wave.

The scene is built from the game's own pieces. The potential is the game's
real Catmull-Rom curve (Game.potential) through a set of electrode voltages
picked to make one tall swell; under it sits the gold electrode strip with
its voltage bars and P1's blue cursor. The ion is drawn twice over: as the
game's glowing classical ion with its trail, and as the sandbox's quantum
wave packet -- a real quantum.WavePacket, kicked forward and evolved a few
steps on that same potential, drawn as phase-coloured density bars the way
Sandbox.draw_packet does. P2's red curve and ion chase it from behind (the
versus mode), a violet laser beam stands on the right, and a string of
photons arcs ahead. Far, blurred copies of the curve give depth.

The title is ION SURFER in the game's own Bungee and GOLD, set in kit's
ARQADE-style wordmark.
"""

from __future__ import annotations

import cmath
import math
import random
import sys

import kit
import pygame

sys.path.insert(0, str(kit.ROOT / "ion-surfer/src"))

from ion_surfer import game as g  # noqa: E402
from ion_surfer.quantum import WavePacket  # noqa: E402
from ion_surfer.sandbox import DENSITY_SCALE, Q_COUPLING, Q_HBAR_M, _phase_palette  # noqa: E402

ROM = "ion_surfer"

SS = 2  # the scene is drawn at twice the size and smoothscaled down (anti-aliasing)
VIEW_W = 800  # world px across the picture (8 electrodes)
STRIP = 108  # height of the electrode strip in art px (at 1024)

# Electrode voltages (curve heights in world px) for one big swell. Node i
# sits over electrode i, at x = (i + 0.5) * EW, exactly as in the game.
BLUE_V = [150, 104, 112, 214, 312, 272, 150, 96, 110, 150, 190, 200, 190]
RED_V = [190, 150, 120, 150, 230, 240, 190, 140, 130, 150, 180, 200, 190]
ION_X = 492  # world x of the surfing blue ion, just over the crest
RED_ION_X = 150  # P2's ion, chasing on its own curve
LASER_I = 7  # electrode with the laser on it (its plate is drawn lit, as in the game)
PACKET_GAIN = 1.0  # packet height relative to the sandbox's DENSITY_SCALE
BEAM = 0.6  # the beam narrower than the game's, so it doesn't swallow the right edge


def _game() -> g.Game:
    """A real Game instance, used only for its potential curve."""
    return g.Game(pygame.Surface((g.W, g.H)))


def _curve(game: g.Game, color, volts) -> g.Curve:
    c = g.Curve(color)
    c.v = list(volts)
    game.caps, game.defects = [], []
    return c


class View:
    """World (x right, height up) -> picture pixels."""

    def __init__(self, size: int):
        self.size = size
        self.k = size / VIEW_W
        self.ground = size - STRIP * size / 1024

    def X(self, x: float) -> float:
        return x * self.k

    def Y(self, h: float) -> float:
        return self.ground - h * self.k


def _packet(game: g.Game, curve: g.Curve) -> WavePacket:
    """The sandbox's quantum ion on this curve: a gaussian kicked to the right
    and left to evolve a few steps, so it leans into the slope it is on."""
    wp = WavePacket(400, VIEW_W, Q_HBAR_M)
    hs = [game.potential(curve, x) for x in wp.xs]
    base = min(hs)
    wp.set_potential([Q_COUPLING * (h - base) for h in hs])
    wp.set_gaussian(ION_X - 6, 24.0, 0.035)
    for _ in range(8):
        wp.step(g.STEP)
    return wp


def _bg_layer(size: int, game: g.Game, view: View) -> pygame.Surface:
    """Game sky gradient + grid + two far, blurred swells for depth."""
    s = g.make_vgrad(size, size, (6, 10, 24), (16, 26, 58))
    # the radial glow of the trap, where the action is
    s.blit(kit.radial((size, size), (view.X(ION_X), view.Y(330)), size * 0.62, (40, 70, 150), 0.9),
           (0, 0), special_flags=pygame.BLEND_ADD)
    grid = (20, 30, 60)
    step = 60 * view.k
    x = 0.0
    while x < size:
        pygame.draw.line(s, grid, (x, 0), (x, view.ground), max(1, SS // 2))
        x += step
    y = view.ground
    while y > 0:
        pygame.draw.line(s, grid, (0, y), (size, y), max(1, SS // 2))
        y -= step
    # far swells: the same curve maths, other voltages, shrunk and blurred
    rng = random.Random(7)
    for depth, (col, alpha, lift) in enumerate((((60, 90, 170), 70, 0.50), ((50, 120, 220), 95, 0.36))):
        far = _curve(game, col, [140 + rng.uniform(-90, 120) for _ in range(14)])
        layer = pygame.Surface((size, size), pygame.SRCALPHA)
        kk = 0.55 + 0.2 * depth
        base = view.ground - size * lift
        pts = [(sx, base - game.potential(far, sx / view.k / kk * 0.9 + 40 * depth) * view.k * kk)
               for sx in range(0, size + 8, 8)]
        pygame.draw.polygon(layer, (*col, alpha // 3), pts + [(size, size), (0, size)])
        pygame.draw.lines(layer, (*col, alpha + 60), False, pts, 3 * SS)
        s.blit(kit.blur(layer, 6 * SS // (depth + 1)), (0, 0))
    return s


def _laser(s: pygame.Surface, view: View) -> None:
    """The game's laser envelope (beam_half) and upward streaks, scaled."""
    x = view.X((LASER_I + 0.5) * g.EW)
    fx = pygame.Surface(s.get_size(), pygame.SRCALPHA)
    top = view.ground / view.k
    left = [(x - g.beam_half(y) * BEAM * view.k, view.Y(y)) for y in range(0, int(top) + 16, 16)]
    right = [(x + g.beam_half(y) * BEAM * view.k, view.Y(y)) for y in range(int(top), -16, -16)]
    pygame.draw.polygon(fx, (170, 125, 255, 30), left + right)
    inner = [(px - (px - x) * 0.55, py) for px, py in left + right]
    pygame.draw.polygon(fx, (200, 165, 255, 40), inner)
    s.blit(fx, (0, 0))
    s.blit(kit.blur(fx, 16 * SS), (0, 0), special_flags=pygame.BLEND_ADD)
    streaks = pygame.Surface(s.get_size())
    for k in range(40):
        y = g.hsh(k * 7.7) * top
        u = g.hsh(k * 31.7) * 2 - 1
        ln = (14 + 30 * g.hsh(k * 1.3)) * 1.6
        col = g.scale_col((235, 222, 255), 0.3 + 0.55 * g.hsh(k * 5.1))
        pygame.draw.line(streaks, col, (x + u * g.beam_half(y) * BEAM * view.k * 0.85, view.Y(y)),
                         (x + u * g.beam_half(y + ln) * BEAM * view.k * 0.85, view.Y(y + ln)), 2 * SS)
    s.blit(streaks, (0, 0), special_flags=pygame.BLEND_ADD)


def _curve_draw(s, game, view, curve, fill_a, glow_strength=1.0, nodes=True):
    """Filled potential with a soft halo and a bright line, like draw_world."""
    size = s.get_width()
    pts = [(sx, view.Y(game.potential(curve, sx / view.k))) for sx in range(0, size + 4, 4)]
    layer = pygame.Surface(s.get_size(), pygame.SRCALPHA)
    pygame.draw.polygon(layer, (*curve.color, fill_a), pts + [(size, size), (0, size)])
    fade = kit.gradient((size, size), [(255, 255, 255), (255, 255, 255), (120, 120, 140)])
    layer.blit(fade, (0, 0), special_flags=pygame.BLEND_RGB_MULT)
    s.blit(layer, (0, 0))
    line = pygame.Surface(s.get_size(), pygame.SRCALPHA)
    pygame.draw.lines(line, (*curve.color, 255), False, pts, 8 * SS)
    s.blit(kit.blur(line, 14 * SS), (0, 0), special_flags=pygame.BLEND_ADD)
    if glow_strength > 0.6:
        s.blit(kit.blur(line, 40 * SS), (0, 0), special_flags=pygame.BLEND_ADD)
    pygame.draw.lines(s, curve.color, False, pts, 5 * SS)
    pygame.draw.lines(s, kit.lerp(curve.color, (255, 255, 255), 0.6), False, pts, 2 * SS)
    if nodes:
        for i in range(len(curve.v)):
            pygame.draw.circle(s, g.scale_col(curve.color, 0.6),
                               (view.X((i + 0.5) * g.EW), view.Y(curve.v[i])), 4 * SS)
    return pts


def _glow_at(s, color, radius, pos, strength=1.0):
    gl = g.make_glow(kit.shade(color, strength), radius)
    s.blit(gl, (pos[0] - radius, pos[1] - radius), special_flags=pygame.BLEND_ADD)


def _ion(s, view, game, curve, x, color, trail_len, big=1.0, lift=24, ride=0.0):
    """The game's ion: glow, body, specular dot and '+', plus its trail --
    here a long arc back along the curve with speed streaks."""
    r = g.R * view.k * 1.9 * big
    def h(xx):  # centre height; `ride` lifts the ion onto its wave packet
        return game.potential(curve, xx) + g.R * 1.9 * big + ride * math.exp(-((xx - x) / 45) ** 2)
    # trail: the game's fading circles, sampled back along an airborne arc
    path = []
    n = 30
    for i in range(n + 1):
        a = i / n
        tx = x - trail_len * (1 - a)
        path.append((view.X(tx), view.Y(h(tx) + lift * math.sin(a * math.pi) * big)))
    trail = pygame.Surface(s.get_size())
    for i, p in enumerate(path[:-1]):
        a = i / n
        pygame.draw.circle(trail, g.scale_col(color, a * 0.55), p, max(1, r * (0.25 + 0.7 * a)))
    s.blit(kit.blur(trail, 3 * SS), (0, 0), special_flags=pygame.BLEND_ADD)
    cx, cy = path[-1]
    # speed streaks, pointing back along the direction of flight
    (px, py), (qx, qy) = path[-4], path[-1]
    d = math.hypot(qx - px, qy - py)
    ux, uy = (qx - px) / d, (qy - py) / d
    rng = random.Random(int(x))
    streaks = pygame.Surface(s.get_size())
    for _ in range(16):
        off = rng.uniform(-1.1, 1.1) * r
        start = r * rng.uniform(0.8, 1.6)
        ln = rng.uniform(1.5, 4.5) * r
        ox, oy = cx - uy * off - ux * start, cy + ux * off - uy * start
        pygame.draw.line(streaks, kit.shade(kit.lerp(color, (255, 255, 255), 0.5), rng.uniform(0.35, 0.9)),
                         (ox, oy), (ox - ux * ln, oy - uy * ln), max(1, round(rng.uniform(1, 2.5) * SS)))
    s.blit(streaks, (0, 0), special_flags=pygame.BLEND_ADD)
    # the game's burst particles: little squares shed along the way
    for i in range(18):
        t = rng.uniform(0.35, 0.95)
        bx, by = path[int(t * n)]
        bx += rng.uniform(-1.6, 1.6) * r
        by += rng.uniform(-1.6, 1.6) * r
        sz = rng.uniform(1.5, 4) * view.k * big
        pygame.draw.rect(s, kit.lerp(color, (255, 255, 255), rng.uniform(0.2, 0.8)), (bx - sz / 2, by - sz / 2, sz, sz))
    _glow_at(s, color, int(r * 4.2), (cx, cy), 0.8)
    _glow_at(s, color, int(r * 2), (cx, cy))
    pygame.draw.circle(s, color, (cx, cy), r)
    pygame.draw.circle(s, kit.lerp(color, (255, 255, 255), 0.35), (cx, cy), r, max(1, SS * 2))
    pygame.draw.circle(s, (255, 255, 255), (cx - r * 0.3, cy - r * 0.3), r * 0.36)
    # the '+' charge, in the game's Rubik
    plus = kit.tint(kit.text_shape("+", kit.RUBIK_FONT, round(r * 1.15)), (255, 255, 255))
    kit.blit_center(s, plus, (cx + r * 0.1, cy + r * 0.1))
    return cx, cy


def _packet_draw(s, view, game, curve, wp) -> float:
    """Sandbox.draw_packet, scaled: phase-coloured density bars on the curve
    with a white envelope line, plus an additive glow under it."""
    pal = _phase_palette()
    rho = wp.density()
    peak = max(range(len(rho)), key=rho.__getitem__)
    ref = cmath.phase(wp.psi[peak])
    bars = pygame.Surface(s.get_size(), pygame.SRCALPHA)
    top = []
    for i, x in enumerate(wp.xs):
        hgt = rho[i] * DENSITY_SCALE * PACKET_GAIN * view.k
        y0 = view.Y(game.potential(curve, x)) - 2 * SS
        if hgt >= 1:
            ph = (cmath.phase(wp.psi[i]) - ref) / (2 * math.pi)
            col = pal[int(ph * len(pal)) % len(pal)]
            pygame.draw.line(bars, (*col, 235), (view.X(x), y0), (view.X(x), y0 - hgt), math.ceil(view.k * 2) + 1)
            top.append((view.X(x), y0 - hgt))
    s.blit(kit.blur(bars, 24 * SS), (0, 0), special_flags=pygame.BLEND_ADD)
    s.blit(bars, (0, 0))
    if len(top) > 1:
        pygame.draw.lines(s, (250, 250, 255), False, top, 2 * SS)
    return max(rho) * DENSITY_SCALE * PACKET_GAIN  # peak height, world px


def _photons(s, view, game, curve) -> None:
    """A spawn_at photon string: gold dots on a sine arc, ahead of the ion."""
    n = 5
    for i in range(n):
        x = 560 + i * 40
        y = game.potential(curve, x) + 70 + math.sin(i / (n - 1) * math.pi) * 60
        p = (view.X(x), view.Y(y))
        _glow_at(s, (255, 215, 110), int(26 * view.k), p)
        pygame.draw.circle(s, (255, 250, 210), p, 5 * view.k)


def _strip(s, view, curves, cursor_i) -> None:
    """The electrode strip, as drawn at the bottom of draw_world."""
    size = s.get_width()
    k = view.k
    pygame.draw.rect(s, (8, 13, 29), (0, view.ground, size, size - view.ground))
    pygame.draw.rect(s, (42, 55, 100), (0, view.ground, size, 2 * SS))
    w = (g.EW - 16) * k
    ph = 28 * k
    gold = g.make_vgrad(round(w), round(ph), (242, 207, 115), (138, 100, 32))
    lit = g.make_vgrad(round(w), round(ph), (230, 214, 255), (138, 92, 240))
    for i in range(VIEW_W // g.EW + 1):
        x = (i * g.EW + 8) * k
        y = view.ground + 14 * k
        s.blit(lit if i == LASER_I else gold, (x, y))
        pygame.draw.rect(s, (255, 240, 200), (x, y, w, 2 * SS))  # top bevel
        for j, c in enumerate(curves):
            lv = (c.v[i] - g.VMIN) / (g.VMAX - g.VMIN)
            by = y + ph + (6 + j * 9) * k
            pygame.draw.rect(s, (26, 36, 70), (x, by, w, 6 * k))
            pygame.draw.rect(s, c.color, (x, by, w * lv, 6 * k))
    # P1's cursor: blue frame, pointer and the dashed line up to its node
    c = curves[-1]
    x = (cursor_i * g.EW + 8) * k
    y = view.ground + 14 * k
    pygame.draw.rect(s, g.BLUE, (x - 3 * k, y - 3 * k, w + 6 * k, ph + 6 * k), round(3 * k))
    cx = x + w / 2
    pygame.draw.polygon(s, g.BLUE, [(cx, view.ground + 3 * k), (cx - 7 * k, view.ground + 11 * k),
                                    (cx + 7 * k, view.ground + 11 * k)])
    y1 = view.Y(c.v[cursor_i])
    yy = view.ground - 4 * k
    while yy > y1 + 8 * k:
        pygame.draw.line(s, g.scale_col(g.BLUE, 0.85), (cx, yy), (cx, max(y1, yy - 5 * k)), round(2 * k))
        yy -= 12 * k
    pygame.draw.circle(s, (255, 255, 255), (cx, y1), 7 * k)


def scene(size: int) -> pygame.Surface:
    big = size * SS
    view = View(big)
    game = _game()
    red = _curve(game, g.RED, RED_V)
    blue = _curve(game, g.BLUE, BLUE_V)
    s = _bg_layer(big, game, view)
    _laser(s, view)
    _curve_draw(s, game, view, red, 26, glow_strength=0.4, nodes=False)
    _ion(s, view, game, red, RED_ION_X, g.RED, 150, big=0.8, lift=30)
    _curve_draw(s, game, view, blue, 60)
    _photons(s, view, game, blue)
    ride = _packet_draw(s, view, game, blue, _packet(game, blue))
    _ion(s, view, game, blue, ION_X, g.BLUE, 300, big=1.5, lift=60, ride=ride)
    _strip(s, view, [red, blue], ION_X // g.EW)
    return pygame.transform.smoothscale(s, (size, size))


def title(width: int) -> pygame.Surface:
    shape = kit.text_shape("ION SURFER", kit.BUNGEE_FONT, 200, tracking=4)
    mark = kit.wordmark(
        shape,
        [(255, 246, 210), g.GOLD, (255, 150, 60)],
        gap=6, outline=9, extrude=16, extrude_color=(18, 34, 92),
        glow_color=(78, 168, 255), glow_radius=40, glow_strength=0.8,
    )
    return kit.fit(mark, width, width)


def art(size: int) -> pygame.Surface:
    out = kit.finish(scene(size), vignette_strength=0.45)
    mark = title(round(size * 0.92))
    r = kit.blit_center(out, mark, (size / 2, size * 0.16))
    tag = kit.tagline("Shape the trap. Ride the wave.", round(size * 0.03), (195, 203, 232))
    kit.blit_center(out, tag, (size / 2, r.bottom + size * 0.012))
    return out


def marquee() -> pygame.Surface:
    """The wordmark over a strip of the blue potential, the ion on its crest."""
    mark = title(1500)
    w, mh = mark.get_size()
    # where the solid letters end (the rest of the height is glow)
    solid = mark.copy()
    solid.fill((0, 0, 0, 200), special_flags=pygame.BLEND_RGBA_SUB)
    letters_bottom = solid.get_bounding_rect().bottom
    r, band = 30, 110  # ion radius, height of the wave
    crest = letters_bottom + 2 * r + 14
    out = pygame.Surface((w, crest + band + 50), pygame.SRCALPHA)
    game = _game()
    blue = _curve(game, g.BLUE, BLUE_V)
    lo, hi = min(BLUE_V), max(BLUE_V)

    def y_at(px: float) -> float:
        return crest + band - (game.potential(blue, px / w * VIEW_W) - lo) / (hi - lo) * band

    pts = [(px, y_at(px)) for px in range(0, w + 4, 4)]
    line = pygame.Surface(out.get_size(), pygame.SRCALPHA)
    pygame.draw.lines(line, (255, 255, 255), False, pts, 10)
    out.blit(kit.glow(line, g.BLUE, 30, 0.9), (0, 0))
    out.blit(mark, (0, 0))
    pygame.draw.lines(out, g.BLUE, False, pts, 9)
    pygame.draw.lines(out, kit.lerp(g.BLUE, (255, 255, 255), 0.6), False, pts, 3)
    # the ion on the crest, with a few speed streaks behind it
    cx = max(range(w), key=lambda px: -y_at(px))
    cy = y_at(cx) - r - 4
    rng = random.Random(3)
    for _ in range(7):
        dy = rng.uniform(-0.8, 0.8) * r
        x0 = cx - r * rng.uniform(1.1, 1.6)
        pygame.draw.line(out, (*kit.lerp(g.BLUE, (255, 255, 255), 0.6), rng.randint(120, 230)),
                         (x0, cy + dy), (x0 - rng.uniform(2, 4.5) * r, cy + dy), rng.choice((2, 3, 4)))
    dot = pygame.Surface(out.get_size(), pygame.SRCALPHA)
    pygame.draw.circle(dot, (255, 255, 255), (cx, cy), r)
    out.blit(kit.glow(dot, g.BLUE, 44, 1.0), (0, 0))
    pygame.draw.circle(out, g.BLUE, (cx, cy), r)
    pygame.draw.circle(out, kit.lerp(g.BLUE, (255, 255, 255), 0.35), (cx, cy), r, 3)
    pygame.draw.circle(out, (255, 255, 255), (cx - r * 0.3, cy - r * 0.3), r * 0.36)
    kit.blit_center(out, kit.text_shape("+", kit.RUBIK_FONT, round(r * 1.15)), (cx + r * 0.1, cy + r * 0.1))
    return kit.trim(out)
