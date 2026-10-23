"""SUPERposition: the supers' drawing (their approved look:
docs/superpowers/specs/2026-10-22-brawl-ket-superposition-looks.py, which drew these first).

Each function draws one piece at a size and phase the renderer works out from the super's
frames (render.py, _super_art and _super_body). DOS's BLUE SCREEN OF DEATH has its own in dos.py.
"""

from __future__ import annotations

import math
from functools import lru_cache

import pygame

from . import palette as P
from .config import FLOOR_Y, INTERNAL_WIDTH as W
from .fonts import load_font
from .kids import glow
from .poses import POSES

FROST = (168, 224, 248)
GOLD_PLATE = (232, 184, 72)
COAX = (176, 200, 216)


def _outlined(text: str, size: int, colour, outline=P.INK):
    font = load_font(size)
    img = font.render(text, False, colour)
    out = pygame.Surface((img.get_width() + 2, img.get_height() + 2), pygame.SRCALPHA)
    edge = font.render(text, False, outline)
    for dx, dy in ((0, 1), (2, 1), (1, 0), (1, 2)):
        out.blit(edge, (dx, dy))
    out.blit(img, (1, 1))
    return out


def _centred(surf, img, c) -> None:
    surf.blit(img, img.get_rect(center=(round(c[0]), round(c[1]))))


def star(surf, c, r, colour) -> None:
    cx, cy = c
    for width, col in ((5, P.INK), (2, colour)):
        for a in range(4):
            ang = a * math.pi / 4
            dx, dy = math.cos(ang) * r, math.sin(ang) * r
            pygame.draw.line(surf, col, (cx - dx, cy - dy), (cx + dx, cy + dy), width)
    pygame.draw.circle(surf, P.WHITE, (round(cx), round(cy)), 3)


def counter(surf, c, text) -> None:
    _centred(surf, _outlined(text, 16, P.GOLD), c)


# --- ROBERT: BLOCH SPHERE ----------------------------------------------------------------------------


def bloch(surf, c, r, colour, up=True, spin=0.4, fill=40) -> None:
    """A Bloch sphere: a glowing wireframe ball (rim, equator, a meridian turned `spin`), its z
    axis with |0> on top and |1> below (when big enough to read), and the state arrow."""
    cx, cy = round(c[0]), round(c[1])
    glow(surf, (cx, cy), r + 10, colour, 70)
    disc = pygame.Surface((2 * r + 2, 2 * r + 2), pygame.SRCALPHA)
    pygame.draw.circle(disc, (*P.lighten(colour, 0.3), fill), (r + 1, r + 1), r)
    surf.blit(disc, (cx - r - 1, cy - r - 1))
    light = P.lighten(colour, 0.55)
    eq = pygame.Rect(0, 0, 2 * r, max(6, r // 2))
    eq.center = (cx, cy)
    mer = pygame.Rect(0, 0, max(4, round(2 * r * abs(math.cos(spin)))), 2 * r)
    mer.center = (cx, cy)
    for rect in (eq, mer):
        pygame.draw.ellipse(surf, P.INK, rect.inflate(2, 2), 3)
        pygame.draw.ellipse(surf, light, rect, 1)
    pygame.draw.circle(surf, P.INK, (cx, cy), r + 1, 4)
    pygame.draw.circle(surf, light, (cx, cy), r, 2)
    for y in range(cy - r, cy + r, 6):
        pygame.draw.line(surf, P.MIST, (cx, y), (cx, min(y + 3, cy + r)), 1)
    if r >= 50:
        _centred(surf, _outlined("|0>", 8, P.WHITE if up else P.MIST), (cx, cy - r - 9))
        _centred(surf, _outlined("|1>", 8, P.MIST if up else P.WHITE), (cx, cy + r + 9))
    tip = (cx, cy - round(0.85 * r) if up else cy + round(0.85 * r))
    pygame.draw.line(surf, P.INK, (cx, cy), tip, 5)
    pygame.draw.line(surf, P.WHITE, (cx, cy), tip, 2)
    d = -1 if up else 1
    pygame.draw.polygon(surf, P.INK, [(tip[0] - 6, tip[1] - d * 7), (tip[0] + 6, tip[1] - d * 7), (tip[0], tip[1] + d * 3)])
    pygame.draw.polygon(surf, P.WHITE, [(tip[0] - 4, tip[1] - d * 6), (tip[0] + 4, tip[1] - d * 6), (tip[0], tip[1] + d)])
    pygame.draw.circle(surf, P.INK, (cx, cy), 4)
    pygame.draw.circle(surf, colour, (cx, cy), 2)


@lru_cache(maxsize=8)
def curled(colour, facing: int) -> pygame.Surface:
    """ROBERT tucked into a ball, at 0.7, for the inside of the rolling sphere."""
    from .render import draw_puppet
    layer = pygame.Surface((160, 160), pygame.SRCALPHA)
    draw_puppet(layer, POSES["crouch"], "lean", (80, 150), facing, colour, P.CREAM, 0.0)
    return pygame.transform.scale_by(layer, 0.7)


def h_gate(surf, c, size=28) -> None:
    box = pygame.Rect(0, 0, size, size)
    box.center = (round(c[0]), round(c[1]))
    glow(surf, box.center, size, P.GOLD, 110)
    pygame.draw.rect(surf, P.INK, box.inflate(4, 4), border_radius=4)
    pygame.draw.rect(surf, P.GOLD, box, border_radius=3)
    _centred(surf, _outlined("H", 16, P.INK, outline=P.GOLD), box.center)


# --- BOHR: WAVEFUNCTION COLLAPSE ----------------------------------------------------------------------


def cloud(surf, centre, sigma, colour, t=0.0, amp=26) -> None:
    """A probability cloud on the floor: a dotted wave under a Gaussian envelope, and faint bars
    of |psi|^2 under it, motes rising."""
    bars = pygame.Surface((W, 90), pygame.SRCALPHA)
    for x in range(0, W, 6):
        env = math.exp(-((x - centre) / sigma) ** 2)
        h = round(70 * env * env)
        if h > 1:
            bars.fill((*P.lighten(colour, 0.2), 70), (x, 90 - h, 4, h))
    surf.blit(bars, (0, FLOOR_Y - 88))
    light = P.lighten(colour, 0.5)
    for x in range(0, W, 3):
        env = math.exp(-((x - centre) / sigma) ** 2)
        if env > 0.04:
            y = round(FLOOR_Y - 30 - env * amp * math.sin(x / 9 + t))
            surf.fill(P.INK, (x - 1, y - 1, 4, 4))
            surf.fill(light if (x // 3) % 2 else P.WHITE, (x, y, 2, 2))
    for k in range(14):
        x = centre + sigma * math.sin(k * 2.4) * 0.9
        y = FLOOR_Y - 40 - (k * 23 + round(t * 6)) % 90
        surf.fill(light, (round(x), y, 2, 2))


def lock_ring(surf, x, colour=P.WHITE) -> None:
    x = round(x)
    rect = pygame.Rect(0, 0, 76, 14)
    rect.center = (x, FLOOR_Y + 2)
    pygame.draw.ellipse(surf, P.INK, rect.inflate(4, 4), 4)
    pygame.draw.ellipse(surf, colour, rect, 2)
    for sx in (-1, 1):
        for sy in (-1, 1):
            cx, cy = x + sx * 46, FLOOR_Y - 60 + sy * 64
            pygame.draw.lines(surf, colour, False, [(cx, cy - sy * 12), (cx, cy), (cx - sx * 12, cy)], 2)


def pillar(surf, x, colour, top=40, k=1.0) -> None:
    """The collapse: a pillar of light on the locked spot (`k`: how much of it is left), dots
    sucked inward, a ring on the floor."""
    x = round(x)
    glow(surf, (x, FLOOR_Y - 40), 70, colour, round(90 * k))
    for w, a, c in ((70, 110, colour), (46, 170, P.lighten(colour, 0.4)), (18, 240, P.WHITE)):
        w = max(2, round(w * k))
        col = pygame.Surface((w, FLOOR_Y - top), pygame.SRCALPHA)
        col.fill((*c, a))
        surf.blit(col, (x - w // 2, top))
    for sx in (-1, 1):
        edge = x + sx * round(35 * k)
        pygame.draw.line(surf, P.INK, (edge, top), (edge, FLOOR_Y), 2)
    for n in range(10):
        ang = n * math.tau / 10
        a = (x + math.cos(ang) * 110 * k, FLOOR_Y - 90 + math.sin(ang) * 66 * k)
        b = (x + math.cos(ang) * 44 * k, FLOOR_Y - 90 + math.sin(ang) * 26 * k)
        pygame.draw.line(surf, P.lighten(colour, 0.5), a, b, 1)
        pygame.draw.circle(surf, P.WHITE, (round(a[0]), round(a[1])), 2)
    rect = pygame.Rect(0, 0, 96, 16)
    rect.center = (x, FLOOR_Y + 2)
    pygame.draw.ellipse(surf, P.WHITE, rect, 3)


# --- PHOEBE: COHERENT BEAM ----------------------------------------------------------------------------


def flare(surf, c, r, colour) -> None:
    glow(surf, c, r, colour, 150)
    glow(surf, c, max(2, r // 2), P.WHITE, 200)
    cx, cy = c
    for ang, ln in ((0, r * 2), (math.pi / 2, r), (math.pi / 4, r * 0.7), (-math.pi / 4, r * 0.7)):
        dx, dy = math.cos(ang) * ln, math.sin(ang) * ln
        pygame.draw.line(surf, P.WHITE, (cx - dx, cy - dy), (cx + dx, cy + dy), 1)


def beam(surf, x0, facing, colour, t=0, height=110, k=1.0) -> None:
    """COHERENT BEAM from x0 to the screen's edge the way she faces, floor to `height` px up (`k`
    of it while it narrows): colour edges, a lighter body, a white core, interference fringes."""
    x0 = round(x0)
    left, w = (x0, W - x0) if facing > 0 else (0, x0)
    if w <= 0:
        return
    full = max(2, round(height * k))
    for inset, a, c in ((0, 150, colour), (10, 190, P.lighten(colour, 0.35)), (34, 240, P.WHITE)):
        h = round((height - 2 * inset) * k)
        if h <= 0:
            continue
        band = pygame.Surface((w, h), pygame.SRCALPHA)
        band.fill((*c, a))
        surf.blit(band, (left, FLOOR_Y - full + round(inset * k)))
    fringe = pygame.Surface((w, full), pygame.SRCALPHA)
    for x in range(-14, w, 14):
        fringe.fill((*P.INK, 40), (x + (t * facing) % 14, 0, 6, full))
    surf.blit(fringe, (left, FLOOR_Y - full))
    pygame.draw.line(surf, P.INK, (left, FLOOR_Y - full - 1), (left + w, FLOOR_Y - full - 1), 2)


# --- M-CUTIE: DILUTION FRIDGE -------------------------------------------------------------------------


def fridge(surf, cx, bottom, s=1.2, falling=False) -> None:
    """The dilution refrigerator (the cryo stage's chandelier made a weapon, bigger and glowing
    with frost so it never reads as the stage's own), its mixing chamber's bottom at `bottom`."""
    cx, bottom = round(cx), round(bottom)
    glow(surf, (cx, bottom - round(90 * s)), round(150 * s), FROST, 70)
    if falling:
        for dx in range(-round(100 * s), round(100 * s) + 1, round(28 * s)):
            top = bottom - round(260 * s)
            pygame.draw.line(surf, P.INK, (cx + dx, top - 60), (cx + dx, top), 4)
            pygame.draw.line(surf, P.WHITE, (cx + dx, top - 60), (cx + dx, top), 2)
    plates = [(bottom + round(dy * s) - 30, round(w * s)) for dy, w in
              ((-150, 200), (-115, 164), (-82, 132), (-52, 104), (-26, 80))]
    for (y0, w0), (y1, w1) in zip(plates, plates[1:]):
        for side in (-1, 1):
            a, b = (cx + side * (w0 // 2 - 10), y0), (cx + side * (w1 // 2 - 8), y1)
            pygame.draw.line(surf, P.INK, a, b, 5)
            pygame.draw.line(surf, P.shade(GOLD_PLATE, 0.85), a, b, 3)
        for k in range(-3, 4):
            a, b = (cx + k * (w0 // 8), y0 + 4), (cx + k * (w1 // 8), y1)
            pygame.draw.line(surf, P.INK, a, b, 3)
            pygame.draw.line(surf, COAX, a, b, 1)
    pygame.draw.line(surf, P.INK, (cx, plates[0][0]), (cx, -10), 7)
    pygame.draw.line(surf, P.MIST, (cx, plates[0][0]), (cx, -10), 3)
    for y, w in plates:
        plate = pygame.Rect(cx - w // 2, y, w, 10)
        pygame.draw.rect(surf, P.INK, plate.inflate(4, 4), border_radius=4)
        pygame.draw.rect(surf, GOLD_PLATE, plate, border_radius=3)
        surf.fill(P.lighten(GOLD_PLATE, 0.5), (plate.x + 4, plate.y + 1, plate.w - 8, 2))
    chamber = pygame.Rect(cx - round(18 * s), bottom - round(26 * s), round(36 * s), round(26 * s))
    pygame.draw.rect(surf, P.INK, chamber.inflate(4, 4), border_radius=4)
    pygame.draw.rect(surf, P.shade(GOLD_PLATE, 0.9), chamber, border_radius=3)
    for k in range(8):
        surf.fill(FROST, (cx - 90 + (k * 37) % 180, plates[k % 5][0] + 12, 3, 2))


def shadow_mark(surf, x, w=110, locked=False, colour=(160, 88, 232)) -> None:
    """The fridge's shadow: a dark disc, ringed dashed in her colour while it follows, solid
    white once it locks."""
    rect = pygame.Rect(0, 0, w, 18)
    rect.center = (round(x), FLOOR_Y + 2)
    sh = pygame.Surface(rect.size, pygame.SRCALPHA)
    pygame.draw.ellipse(sh, (*P.INK, 190), sh.get_rect())
    surf.blit(sh, rect)
    ring = rect.inflate(8, 6)
    if locked:
        pygame.draw.ellipse(surf, P.INK, ring.inflate(4, 4), 4)
        pygame.draw.ellipse(surf, P.WHITE, ring, 2)
        return
    for k in range(16):
        a0 = k * math.tau / 16
        pygame.draw.arc(surf, P.lighten(colour, 0.3), ring, a0, a0 + math.tau / 32, 3)


def frost_wave(surf, x, reach=150, k=1.0) -> None:
    """The frosty shockwave either side of the fridge: ice spikes along the floor (`k`: how far
    out it has rolled) and snow."""
    x = round(x)
    for side in (-1, 1):
        for n in range(9):
            sx = x + side * (30 + n * reach / 9 * k)
            h = 26 - n * 2
            pygame.draw.polygon(surf, P.INK, [(sx - 5, FLOOR_Y), (sx, FLOOR_Y - h), (sx + 5, FLOOR_Y)])
            pygame.draw.polygon(surf, FROST, [(sx - 3, FLOOR_Y - 1), (sx, FLOOR_Y - h + 3), (sx + 3, FLOOR_Y - 1)])
    for n in range(18):
        surf.fill(P.WHITE, (x - reach + (n * 53) % (2 * reach), FLOOR_Y - 20 - (n * 29) % 90, 2, 2))


# --- ALICE & BOB: ONE-TIME PAD ------------------------------------------------------------------------


def padlock(surf, c, closed=True) -> None:
    cx, cy = round(c[0]), round(c[1])
    shackle = pygame.Rect(0, 0, 44, 52)
    shackle.midbottom = (cx, cy - 4 if closed else cy - 24)
    pygame.draw.arc(surf, P.INK, shackle.inflate(8, 8), 0, math.pi, 12)
    pygame.draw.arc(surf, P.MIST, shackle, 0, math.pi, 6)
    for sx in (shackle.left + 3, shackle.right - 3):
        pygame.draw.line(surf, P.INK, (sx, shackle.centery), (sx, cy + 4), 10)
        pygame.draw.line(surf, P.MIST, (sx, shackle.centery), (sx, cy + 4), 5)
    body = pygame.Rect(0, 0, 70, 54)
    body.midtop = (cx, cy)
    glow(surf, body.center, 50, P.GOLD, 120)
    pygame.draw.rect(surf, P.INK, body.inflate(6, 6), border_radius=8)
    pygame.draw.rect(surf, P.GOLD, body, border_radius=6)
    surf.fill(P.lighten(P.GOLD, 0.5), (body.x + 6, body.y + 4, body.w - 12, 3))
    pygame.draw.circle(surf, P.INK, (cx, body.y + 22), 7)
    pygame.draw.rect(surf, P.INK, (cx - 3, body.y + 24, 6, 16))
