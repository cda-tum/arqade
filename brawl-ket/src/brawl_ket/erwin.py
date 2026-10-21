"""ERWIN's look: Schrodinger's cat on the shared skeleton, and THE BOX.

Ported from his approved look, docs/superpowers/specs/2026-10-21-brawl-ket-erwin-look.py:
draw_erwin and everything it calls are the look's own code, given the joints instead of a
pose (tests/test_render.py checks him against the look pixel for pixel). The holographic
and cardboard boxes are the look's too, but each is drawn once per colour, facing and
shimmer phase onto a small sprite (the look drew a full-screen layer every call), then only
blitted: the superposition costs four blits a frame.
"""

from __future__ import annotations

import math
from functools import lru_cache

import pygame

from . import palette as P
from .ink import _ball, _pt, frame, limb, poly
from .ink import _towards as towards
from .poses import HEAD_R, LIMB_W

NOSE = (240, 136, 168)
EYE = (248, 208, 64)            # amber: the one warm accent, as BOHR's gold
CARD = (200, 144, 88)
CARD_DARK = (152, 104, 64)
CARD_DEEP = (104, 64, 40)
CARD_LIGHT = (224, 176, 120)
TAPE = (232, 208, 160)

BOX_W, BOX_H = 70, 52           # a box as drawn
KEY = (255, 0, 255)             # the see-through colour of the box sprites
OFF = (1, 2, 3)                 # ... and of the dither stencil
SPRITE_W, SPRITE_H = 140, 130   # a box sprite, with its box centred at SPRITE_X on its floor line
SPRITE_X, SPRITE_FLOOR = 60, 120
HOLO_PHASES = 4                 # the shimmer's slipped rows: this many variants, cycled
FADE_STEPS = 4                  # a box dissolving: this many dither steps
FLASH_FRAMES = 6                # the collapse's white rim and rays


# --- shared helpers (the look's) -----------------------------------------------------------


def blob(surf, pts, color):
    """A filled shape with a 2 px ink outline all round, its corners rounded off."""
    pts = [_pt(p) for p in pts]
    pygame.draw.polygon(surf, P.INK, pts, 5)
    for p in pts:
        pygame.draw.circle(surf, P.INK, p, 2)
    pygame.draw.polygon(surf, color, pts)


def chain(surf, pts, widths, colors):
    """A bendy tube through pts (a tail): all its ink first, then all its fill, so there is
    one outline round the whole tube and no seams between its segments."""
    pts = [_pt(p) for p in pts]
    for k in (0, 1):
        for i in range(len(pts) - 1):
            w = widths[i] + (4 if k == 0 else 0)
            c = P.INK if k == 0 else colors[i]
            pygame.draw.line(surf, c, pts[i], pts[i + 1], w)
            pygame.draw.circle(surf, c, pts[i], w // 2)
            pygame.draw.circle(surf, c, pts[i + 1], w // 2)


def curve(p0, p1, p2, p3, n):
    """n+1 points along a cubic Bezier."""
    out = []
    for i in range(n + 1):
        t = i / n
        a, b, c, d = (1 - t) ** 3, 3 * t * (1 - t) ** 2, 3 * t * t * (1 - t), t ** 3
        out.append((a * p0[0] + b * p1[0] + c * p2[0] + d * p3[0], a * p0[1] + b * p1[1] + c * p2[1] + d * p3[1]))
    return out


# --- cat parts (the look's) -----------------------------------------------------------------


def paw(surf, p, r, color):
    """A round mitten paw with two toe creases."""
    _ball(surf, p, r, color)
    x, y = _pt(p)
    for dx in (-2, 2):
        pygame.draw.line(surf, P.shade(color, 0.6), (x + dx, y + 1), (x + dx, y + r - 1), 1)


def cat_head(surf, c, r, facing, fur, light, peek=False):
    """The head: wide cheeks with a tuft behind, two tall ears, a pale muzzle with a pink
    nose, big amber eyes with slit pupils, and whiskers. `peek` stops after the eyes (all
    that shows over the box's rim)."""
    hx, hy = _pt(c)
    f = facing

    def X(dx):
        return hx + dx * f

    dark = P.shade(fur, 0.72)
    inner = P.lighten(fur, 0.3)
    for base_a, base_b, tip, col, ins in (
            ((X(-r - 1), hy - r + 9), (X(-3), hy - r + 1), (X(-r + 1), hy - r - 13), dark, P.shade(inner, 0.75)),
            ((X(-5), hy - r + 1), (X(r - 1), hy - r + 7), (X(4), hy - r - 15), fur, inner)):
        pts = [_pt(base_a), _pt(tip), _pt(base_b)]
        pygame.draw.polygon(surf, P.INK, pts, 0)
        pygame.draw.lines(surf, P.INK, True, pts, 5)
        pygame.draw.polygon(surf, col, pts)
        mid = towards(base_a, base_b, 0.5)
        poly(surf, [towards(base_a, mid, 0.45), towards(tip, mid, 0.28), towards(base_b, mid, 0.45)], ins, ink=0)
    head = pygame.Rect(0, 0, 2 * r + 8, 2 * r - 2)
    head.center = (hx, hy)
    for tip, y0, y1 in (((X(-r - 9), hy + 3), hy - 3, hy + 6), ((X(-r - 6), hy + 11), hy + 4, hy + 12)):
        pts = [_pt((X(-r + 3), y0)), _pt(tip), _pt((X(-r + 5), y1))]
        pygame.draw.polygon(surf, P.INK, pts)
        pygame.draw.lines(surf, P.INK, True, pts, 5)
        pygame.draw.polygon(surf, fur, pts)
    pygame.draw.ellipse(surf, P.INK, head.inflate(4, 4))
    pygame.draw.ellipse(surf, fur, head)
    surf.fill(P.lighten(fur, 0.5), (X(-8) - (2 if f < 0 else 0), hy - r + 5, 3, 3))
    muz = pygame.Rect(0, 0, 22, 14)
    muz.center = (X(9), hy + 7)
    pygame.draw.ellipse(surf, light, muz)
    for ex, ew in ((X(0), 10), (X(13), 8)):
        eye = pygame.Rect(0, 0, ew, 12)
        eye.center = (ex, hy - 2)
        pygame.draw.ellipse(surf, P.INK, eye.inflate(4, 4))
        pygame.draw.ellipse(surf, EYE, eye)
        surf.fill(P.INK, (ex - 1 + (1 if f > 0 else 0), hy - 6, 2, 9))
        surf.fill(P.WHITE, (ex - 3 * f - (1 if f < 0 else 0), hy - 6, 2, 2))
    if peek:
        return
    nx, ny = X(16), hy + 4
    pygame.draw.polygon(surf, P.INK, [(nx - 5 * f, ny - 2), (nx + 2 * f, ny - 2), (nx - f, ny + 3)])
    pygame.draw.polygon(surf, NOSE, [(nx - 4 * f, ny - 1), (nx + 1 * f, ny - 1), (nx - f, ny + 1)])
    pygame.draw.line(surf, P.INK, (nx - f, ny + 3), (nx - f, ny + 5), 1)
    pygame.draw.lines(surf, P.INK, False, [(nx - 6 * f, ny + 6), (nx - 3 * f, ny + 7), (nx - f, ny + 5),
                                            (nx + 1 * f, ny + 7)], 1)
    for y0, dy in ((ny + 2, -3), (ny + 5, 1)):
        pygame.draw.line(surf, P.WHITE, (nx - 2 * f, y0), (nx + 11 * f, y0 + dy), 1)


def tail(surf, base, facing, fur, swish=0.0, scale=1.0, width=10):
    """A tail curling up from the hip: thick at the root, a paler tip curling forward."""
    s = scale
    bx, by = base
    pts = curve((bx, by), (bx - 26 * s * facing, by + 4 * s), (bx - (44 + swish) * s * facing, by - 26 * s),
                (bx - (30 + swish) * s * facing, by - 58 * s), 14)
    tip_curl = (pts[-1][0] + 8 * s * facing, pts[-1][1] - 5 * s)
    pts.append(tip_curl)
    n = len(pts) - 1
    widths = [max(6, round(width - i * 0.3)) for i in range(n)]
    colors = [fur] * (n - 3) + [P.lighten(fur, 0.45)] * 3
    chain(surf, pts, widths, colors)


def cat_leg_points(j, side, facing):
    """The cat leg over the skeleton's hip, knee and foot: the knee nudged forward, a hock
    added halfway down the knee-foot line and pushed well off it towards the back, so the leg
    reads thigh forward, long lower leg back to a high heel, the long foot down to the toes."""
    k, ft = j[f"knee_{side}"], j[f"foot_{side}"]
    dx, dy = ft[0] - k[0], ft[1] - k[1]
    n = math.hypot(dx, dy) or 1.0
    bx, by = -dy / n * facing, dx / n * facing
    knee = (k[0] - bx * n * 0.14, k[1] - by * n * 0.14)
    hk = (k[0] + dx * 0.52 + bx * n * 0.42, k[1] + dy * 0.52 + by * n * 0.42)
    return knee, hk


def toes(surf, p, facing, color):
    """Standing on the toe pads: a small round paw, toes forward, two creases."""
    r = pygame.Rect(0, 0, 15, 9)
    r.midbottom = _pt((p[0] + 3 * facing, p[1] + 5))
    pygame.draw.ellipse(surf, P.INK, r.inflate(4, 4))
    pygame.draw.ellipse(surf, color, r)
    tx = r.right - 4 if facing > 0 else r.left + 4
    for dx in (0, -4 * facing):
        pygame.draw.line(surf, P.shade(color, 0.6), (tx + dx, r.top + 3), (tx + dx, r.bottom - 2), 1)


def cat_leg(surf, j, side, facing, color, paw_color, w):
    """Haunch and thigh forward to the knee, the lower leg back to the hock, the long foot
    down to the toes. All its ink first, then its fill: one outline, no seams."""
    hip, foot_p = j["hip"], j[f"foot_{side}"]
    knee, hk = cat_leg_points(j, side, facing)
    toe = (foot_p[0], foot_p[1] - 2)
    segs = ((hip, knee, w + 6), (knee, hk, w - 1), (hk, toe, w - 5))
    for c, pad in ((P.INK, 4), (color, 0)):
        for a, b, ww in segs:
            a, b = _pt(a), _pt(b)
            pygame.draw.line(surf, c, a, b, ww + pad)
            pygame.draw.circle(surf, c, a, (ww + pad) // 2)
            pygame.draw.circle(surf, c, b, (ww + pad) // 2)
    toes(surf, foot_p, facing, paw_color)


def draw_erwin(surf, j, facing, fur, strike=None):
    """ERWIN at the joints `j` (poses.joints, build "cat"), in his basis colour `fur`.
    `strike` = (joint, colour) lights an attack's whole arm ("hand_f") or leg ("foot_f") in its
    colour, as on every fighter. Returns j."""
    light = P.lighten(fur, 0.55)                # belly, muzzle, paws: a pale shade of his fur
    dark = P.shade(fur, 0.68)
    at = frame(j, facing)
    w = LIMB_W["cat"]
    hip, neck, sh = j["hip"], j["neck"], j["shoulder_f"]
    # 1. the tail, behind everything
    tail(surf, at(hip, 6, -10), facing, fur)
    # 2. the back leg and arm, in shadow
    cat_leg(surf, j, "b", facing, P.shade(dark, 0.9), P.shade(light, 0.8), w)
    limb(surf, j["shoulder_b"], j["elbow_b"], w - 1, dark)
    limb(surf, j["elbow_b"], j["hand_b"], w - 2, dark)
    paw(surf, j["hand_b"], 6, P.shade(light, 0.8))
    # 3. the body: a soft pear, narrow at the shoulders, round at the belly
    rows = ((neck, 2, 8), (sh, 0, 11), (hip, 16, 15), (hip, 6, 15), (hip, -4, 12), (hip, -9, 5))
    front = [at(b, up, half) for b, up, half in rows]
    back = [at(b, up, -half) for b, up, half in reversed(rows)]
    blob(surf, front + back, fur)
    bib = [at(neck, 0, 2), at(sh, -2, 9), at(hip, 14, 13), at(hip, 2, 12), at(hip, -5, 6),
           at(hip, 2, 1), at(sh, -6, 1)]
    poly(surf, bib, light, ink=0)
    pygame.draw.circle(surf, P.lighten(fur, 0.35), _pt(at(sh, -1, -6)), 2)
    # 4. the front leg (lit when it kicks)
    lit = strike[1] if strike and strike[0] == "foot_f" else None
    cat_leg(surf, j, "f", facing, lit or fur, P.lighten(lit, 0.5) if lit else light, w)
    hx, hy = _pt(towards(hip, j["knee_f"], 0.25))
    pygame.draw.arc(surf, P.shade(lit or fur, 0.78), (hx - 9, hy - 9, 18, 18),
                    math.radians(60 if facing > 0 else 0), math.radians(180 if facing > 0 else 120), 2)
    # 5. the head
    cat_head(surf, j["head"], HEAD_R["cat"], facing, fur, light)
    # 6. the front arm, in front of everything
    arm = strike[1] if strike and strike[0] == "hand_f" else fur
    limb(surf, j["shoulder_f"], j["elbow_f"], w - 1, arm)
    limb(surf, j["elbow_f"], j["hand_f"], w - 2, arm)
    paw(surf, j["hand_f"], 7, light if arm is fur else P.lighten(arm, 0.5))
    return j


# --- THE BOX ---------------------------------------------------------------------------------


def box(surf, x, w, h, facing, fur, floor, peek=True, head_r=16):
    """A cardboard box on the floor, its flaps open; his ears and eyes peek over the rim.
    Drawn in 3/4: the front face, the side face going back, the open top (the look's)."""
    d = 10
    f = facing
    left, top = round(x - w / 2), floor - h + 4
    front = pygame.Rect(left, top, w, h)
    bl, br = (left + d, top - d), (left + w + d, top - d)
    poly(surf, [bl, (bl[0] + 4, bl[1] - 22), (br[0] - 4, br[1] - 22), br], CARD_DARK)
    poly(surf, [(left, top), bl, br, (left + w, top)], CARD_DEEP)
    if peek:
        hx = x + d / 2 + 2 * f
        layer = surf.subsurface(pygame.Rect(0, 0, surf.get_width(), top + 1))
        cat_head(layer, (hx, top - 7), head_r, facing, fur, P.lighten(fur, 0.55), peek=True)
    poly(surf, [(left + w, top), (left + w + d, top - d), (left + w + d, top - d + h), (left + w, top + h)], CARD_DARK)
    poly(surf, [(left + w, top), (left + w + d, top - d), (left + w + d + 17, top - d + 3), (left + w + 17, top + 3)],
         CARD_LIGHT)
    poly(surf, [front.topleft, front.topright, front.bottomright, front.bottomleft], CARD)
    surf.fill(CARD_LIGHT, (left + 3, top + 3, w - 6, 2))
    tx = left + w // 2
    surf.fill(TAPE, (tx - 4, top + 2, 8, 16))
    surf.fill(P.shade(TAPE, 0.85), (tx - 4, top + 16, 8, 2))
    poly(surf, [(left, top), (left - 14, top - 14), (left - 4, top - 18), (left + d, top - d)], CARD_LIGHT)
    poly(surf, [(left + 2, top), (left + w - 2, top), (left + w - 6, top + 12), (left + 6, top + 12)], CARD_LIGHT)
    surf.fill(TAPE, (tx - 4, top + 2, 8, 9))
    pygame.draw.line(surf, P.INK, (left + 6, top + 12), (left + w - 6, top + 12), 2)
    for ax in (left + 10, left + w - 18):
        ay = top + h - 14
        pygame.draw.polygon(surf, CARD_DEEP, [(ax + 4, ay - 5), (ax, ay), (ax + 8, ay)])
        surf.fill(CARD_DEEP, (ax + 3, ay, 2, 6))
    return front


def _layer() -> pygame.Surface:
    s = pygame.Surface((SPRITE_W, SPRITE_H))
    s.fill(KEY)
    s.set_colorkey(KEY)
    return s


def _anchor(facing: int) -> int:
    """Where a box's centre is across its sprite (the sprite is mirrored for facing left)."""
    return SPRITE_X if facing > 0 else SPRITE_W - 1 - SPRITE_X


def _flat_box(fur, facing: int, peek: bool = True) -> pygame.Surface:
    """The cardboard box (with his ears and eyes over the rim if `peek`), on its own sprite."""
    layer = _layer()
    box(layer, SPRITE_X, BOX_W, BOX_H, 1, fur, SPRITE_FLOOR, peek)
    if facing < 0:
        layer = pygame.transform.flip(layer, True, False)
    return layer


@lru_cache(maxsize=FADE_STEPS)
def _dither(fade_step: int) -> pygame.Surface:
    """An ordered dither, fade_step / FADE_STEPS of its pixels KEY (the rest see-through):
    blitted over a box sprite, it eats that much of it. The pattern repeats every 10 px."""
    tile = pygame.Surface((10, 10))
    tile.fill(OFF)
    tile.set_colorkey(OFF)
    for y in range(10):
        for x in range(10):
            if ((x * 7 + y * 13) % 10) / 10 < fade_step / FADE_STEPS:
                tile.set_at((x, y), KEY)
    s = pygame.Surface((SPRITE_W, SPRITE_H))
    s.fill(OFF)
    s.set_colorkey(OFF)
    for y in range(0, SPRITE_H, 10):
        for x in range(0, SPRITE_W, 10):
            s.blit(tile, (x, y))
    return s


@lru_cache(maxsize=64)
def holo_sprite(fur, facing: int, phase: int, fade_step: int = 0) -> tuple[pygame.Surface, pygame.Surface]:
    """A holographic box (the look's holo_box): the box recoloured into his basis colour with
    glowing edges, see-through, with scanline gaps and a few rows slipped sideways by `phase`;
    `fade_step` / FADE_STEPS of it dissolved. Returns (the box, the pale pool it stands in),
    both SPRITE_W x SPRITE_H, to blit at (x - _anchor(facing), floor - SPRITE_FLOOR)."""
    fade = fade_step / FADE_STEPS
    layer = _flat_box(fur, facing)
    glow = P.lighten(fur, 0.75)
    pa = pygame.PixelArray(layer)
    for src, dst in ((P.INK, glow), (CARD, fur), (CARD_LIGHT, P.lighten(fur, 0.3)), (CARD_DARK, P.shade(fur, 0.7)),
                     (CARD_DEEP, P.shade(fur, 0.4)), (TAPE, P.lighten(fur, 0.45)),
                     (P.shade(TAPE, 0.85), P.lighten(fur, 0.25)), (EYE, P.WHITE)):
        pa.replace(src, dst)
    del pa
    gaps = (fur, P.lighten(fur, 0.3), P.shade(fur, 0.7), P.shade(fur, 0.4), P.lighten(fur, 0.45),
            P.lighten(fur, 0.25), P.lighten(fur, 0.55))
    out = _layer()
    seed = phase * 3
    for y in range(SPRITE_H):
        if y % 3 == 0:                                 # a scanline gap: only the glowing edges
            row = layer.subsurface((0, y, SPRITE_W, 1)).copy()
            pa = pygame.PixelArray(row)
            for c in gaps:
                pa.replace(c, KEY)
            del pa
            row.set_colorkey(KEY)
            out.blit(row, (0, y))
            continue
        slip = 2 if (y // 2 + seed) % 9 == 0 else (-1 if (y + seed) % 13 == 0 else 0)
        out.blit(layer, (slip, y), (0, y, SPRITE_W, 1))
    if fade_step:
        out.blit(_dither(fade_step), (0, 0))
    pool = _layer()
    base = pygame.Rect(0, 0, BOX_W + 26, 12)
    base.center = (_anchor(facing) + 4 * facing, SPRITE_FLOOR + 2)
    pygame.draw.ellipse(pool, P.lighten(fur, 0.3), base, 2)
    pool.set_alpha(round(140 * (1 - fade)))
    out.set_alpha(round(215 * (1 - 0.5 * fade)))
    return out, pool


def draw_holo_box(surf, x, floor, facing, fur, phase, fade_step=0):
    """One holographic box standing on `floor` at x."""
    out, pool = holo_sprite(fur, facing, 0 if fade_step else phase % HOLO_PHASES, fade_step)
    pos = (round(x) - _anchor(facing), round(floor) - SPRITE_FLOOR)
    surf.blit(pool, pos)
    surf.blit(out, pos)


@lru_cache(maxsize=16)
def card_sprite(fur, facing: int) -> tuple[pygame.Surface, pygame.Surface]:
    """The real cardboard box he turned out to be in, and its white silhouette (the rim). No
    ears over its rim: in the game his real body is there, popping out of it."""
    card = _flat_box(fur, facing, peek=False)
    rim = pygame.mask.from_surface(card).to_surface(setcolor=(*P.WHITE, 255), unsetcolor=(0, 0, 0, 0))
    return card, rim


def dotted_arc(surf, a, b, peak, color):
    """A dashed arc from a to b, its top `peak` px above them: one cat, two places."""
    n = 28
    pts = []
    for i in range(n + 1):
        t = i / n
        pts.append((a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t - 4 * peak * t * (1 - t)))
    for i in range(0, n, 2):
        pygame.draw.line(surf, P.INK, _pt(pts[i]), _pt(pts[i + 1]), 5)
    for i in range(0, n, 2):
        pygame.draw.line(surf, color, _pt(pts[i]), _pt(pts[i + 1]), 2)


def star(surf, c, r, color):
    """A four-pointed glint: a thin cross that tapers to points."""
    x, y = _pt(c)
    for k in range(r):
        half = max(0, (r - k) // 3)
        surf.fill(color, (x - half, y - k, 2 * half + 1, 1))
        surf.fill(color, (x - half, y + k, 2 * half + 1, 1))
        surf.fill(color, (x - k, y - half, 1, 2 * half + 1))
        surf.fill(color, (x + k, y - half, 1, 2 * half + 1))


def draw_superposed(surf, boxes, floor, facing, fur, t):
    """THE BOX superposed: the two holographic boxes, each shimmering on its own beat, and the
    dashed arc between them."""
    a, b = boxes
    y = floor - BOX_H - 34
    dotted_arc(surf, (a + 5, y), (b + 5, y), 24 + abs(b - a) * 0.12, P.lighten(fur, 0.45))
    for i, x in enumerate(boxes):
        draw_holo_box(surf, x, floor, facing, fur, t // 3 + 2 * i)


def draw_collapse(surf, x, floor, facing, fur, age):
    """The collapse, `age` frames on: the box he is in is real cardboard, for its first
    FLASH_FRAMES in a white rim with rays bursting off it and two glints (the look's
    collapse_flash)."""
    card, rim = card_sprite(fur, facing)
    pos = (round(x) - _anchor(facing), round(floor) - SPRITE_FLOOR)
    if age < FLASH_FRAMES:
        for dx, dy in ((-2, 0), (2, 0), (0, -2), (0, 2), (-1, -1), (1, 1), (-1, 1), (1, -1)):
            surf.blit(rim, (pos[0] + dx, pos[1] + dy))
        cx, cy = x + 5 * facing, floor - BOX_H / 2 - 8
        for k in range(9):
            a = math.radians(-180 + k * 22.5)               # only upwards and sideways
            r0, r1 = 54, 74 + (k % 2) * 12
            p0 = (cx + math.cos(a) * r0, cy + math.sin(a) * r0 * 0.85)
            p1 = (cx + math.cos(a) * r1, cy + math.sin(a) * r1 * 0.85)
            pygame.draw.line(surf, P.INK, _pt(p0), _pt(p1), 6)
            pygame.draw.line(surf, P.WHITE if k % 2 else P.lighten(fur, 0.5), _pt(p0), _pt(p1), 3)
        star(surf, (x - (BOX_W / 2 + 4) * facing, floor - BOX_H - 10), 9, P.WHITE)
        star(surf, (x + (BOX_W / 2 + 16) * facing, floor - BOX_H - 22), 6, P.lighten(fur, 0.6))
    surf.blit(card, pos)


def draw_little_box(surf, center, color, tilt: int) -> None:
    """BOX DROP's box: a little cardboard box in the attack's colour, flaps open on top, a tape
    stripe down its front, rocking a pixel from side to side as it falls (`tilt` 0 or 1)."""
    cx, cy = round(center[0]), round(center[1])
    body = pygame.Rect(0, 0, 20, 14)
    body.midtop = (cx + (1 if tilt else -1), cy - 5)
    flaps = [((body.left, body.top), (body.left - 4, body.top - 5), (body.left + 8, body.top - 4), (body.left + 9, body.top)),
             ((body.right, body.top), (body.right + 4, body.top - 5), (body.right - 8, body.top - 4), (body.right - 9, body.top))]
    for flap in flaps:
        pygame.draw.polygon(surf, P.INK, flap)
        pygame.draw.polygon(surf, P.shade(color, 0.75), [(x, y + 1) for x, y in flap[:3]] + [flap[3]])
    pygame.draw.rect(surf, P.INK, body.inflate(4, 4), border_radius=2)
    pygame.draw.rect(surf, color, body)
    surf.fill(P.shade(color, 0.7), (body.x, body.bottom - 4, body.w, 4))              # its shaded side
    surf.fill(P.lighten(color, 0.45), (body.centerx - 2, body.y, 4, body.h - 4))      # the tape

