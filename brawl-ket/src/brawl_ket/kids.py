"""ALICE & BOB's look: kid couriers in matching hoodies (variant A, COURIERS), and their specials.

Ported from their approved look, docs/superpowers/specs/2026-10-22-brawl-ket-alice-bob-look.py:
everything here is the look's own code (variant A only), given the joints instead of a pose.
tests/test_render.py checks both kids, KEY EXCHANGE's toss and big photon, TELEPORT's flash and
swap arc, BELL DIVE's streaks and a decohered Bob against the look pixel for pixel.

The look drew a decohered Bob through a full-screen layer and its outline every call; here the
layer is the size of his body, made once per colour, facing and spot (he stands still while he
fades), and its rows are put down on the screen's own rows, as the look did: the same pixels.
"""

from __future__ import annotations

import math
import random
from functools import lru_cache

import pygame

from . import palette as P
from .config import FLOOR_Y
from .ink import _ball, _pt, frame, limb, poly
from .ink import _towards as towards
from .poses import HEAD_R, LIMB_W, POSES, joints

SKIN_A = (240, 184, 136)         # Alice
SKIN_B = (192, 128, 88)          # Bob
BLONDE = (240, 200, 104)
DARK_HAIR = (64, 40, 40)
BLUSH = (240, 136, 152)
SNEAKER = (240, 232, 216)
SOLE = (120, 104, 112)
LEATHER = (184, 120, 64)         # the satchel
LEATHER_DARK = (128, 80, 48)
PHONES = (64, 64, 96)            # the headphones: dark slate
CUSHION = (200, 192, 208)

R = HEAD_R["alice"]              # the look's "kid" head (both kids': 15)
W = LIMB_W["alice"]              # ... and limbs (11)
DECOHERED_SIZE = (160, 200)      # a decohered Bob's layer, his feet DECOHERED_AT in it
DECOHERED_AT = (80, 180)


# --- helpers (the look's) ------------------------------------------------------------------------


def fx_rect(surf, color, hx, f, dx, y, w, h):
    """A w x h rect `dx` px in front of hx (towards the face), mirrored for facing left."""
    x = hx + dx if f > 0 else hx - dx - w + 1
    surf.fill(color, (round(x), round(y), w, h))


@lru_cache(maxsize=64)
def _glow_disc(r: int, color, alpha: int) -> pygame.Surface:
    g = pygame.Surface((2 * r + 2, 2 * r + 2))
    k0 = alpha / 255
    for k, a in ((1.0, 0.25), (0.7, 0.45), (0.42, 0.8)):
        pygame.draw.circle(g, tuple(round(v * a * k0) for v in color), (r + 1, r + 1), max(1, round(r * k)))
    return g


def glow(surf, c, r, color, alpha=90):
    """A soft round glow, added onto what is under it (light, not paint). (The look's, its disc cached.)"""
    g = _glow_disc(r, color, alpha)
    surf.blit(g, g.get_rect(center=_pt(c)), special_flags=pygame.BLEND_RGB_ADD)


# --- the bodies (the look's variant A) -------------------------------------------------------------


def sneaker(surf, foot, facing, color=SNEAKER):
    r = pygame.Rect(0, 0, 14, 7)
    r.midbottom = _pt((foot[0] + 3 * facing, foot[1] + 6))
    pygame.draw.rect(surf, P.INK, r.inflate(4, 4), border_radius=4)
    pygame.draw.rect(surf, color, r, border_radius=3)
    surf.fill(SOLE if color == SNEAKER else P.shade(color, 0.6), (r.x + 1, r.bottom - 2, r.w - 2, 2))


def kit(base):
    """The pair's shared outfit colours: (top, sleeve, thigh, shin): hoodie and trousers."""
    return base, base, P.shade(base, 0.6), P.shade(base, 0.6)


def lit_limb(surf, a, b, c, w, fill):
    """A strike's limb in the attack's colour: inked, the tip a bright ball (tip)."""
    limb(surf, a, b, w, fill)
    limb(surf, b, c, w - 1, fill)


def tip(surf, p, w, fill, active):
    p = _pt(p)
    r = w // 2 + (4 if active else 2)
    pygame.draw.circle(surf, P.INK, p, r + 2)
    pygame.draw.circle(surf, fill, p, r)
    pygame.draw.circle(surf, P.lighten(fill, 0.5), (p[0] - 2, p[1] - 2), max(2, r // 3))


def torso(surf, at, j, top):
    """The hoodie: the hood bunched behind the neck, a pouch pocket, white drawstrings, the ribbed hem."""
    hip, neck, sh = j["hip"], j["neck"], j["shoulder_f"]
    pts = [at(neck, 0, -8), at(sh, 0, -11), at(hip, 3, -11), at(hip, -6, -12), at(hip, -6, 12),
           at(hip, 3, 11), at(sh, 0, 11), at(neck, 0, 8)]
    poly(surf, pts, top)
    pygame.draw.line(surf, P.lighten(top, 0.4), _pt(at(sh, -2, 8)), _pt(at(hip, 0, 9)), 2)
    pygame.draw.line(surf, P.shade(top, 0.72), _pt(at(sh, 0, -9)), _pt(at(hip, 0, -9)), 2)
    _ball(surf, at(neck, -3, -8), 6, P.shade(top, 0.8))
    pygame.draw.line(surf, P.shade(top, 0.7), _pt(at(hip, 8, -2)), _pt(at(hip, 8, 11)), 1)
    for k in (4, 8):
        pygame.draw.line(surf, P.WHITE, _pt(at(neck, -1, k)), _pt(at(neck, -9, k + 1)), 1)
    pygame.draw.line(surf, P.shade(top, 0.7), _pt(at(hip, -4, -11)), _pt(at(hip, -4, 11)), 2)


def skirt(surf, j, at, base):
    """Alice's short pleated skirt, hanging by gravity over the hoodie's hem."""
    hip = j["hip"]
    knees = (j["knee_f"][0] + j["knee_b"][0]) / 2
    shift = 0.35 * (knees - hip[0])
    a, b = at(hip, -2, -12), at(hip, -2, 12)
    y = max(a[1], b[1]) + 14
    cx = hip[0] + shift
    pts = [a, b, (cx + 16, y - 1), (cx + 8, y + 1), (cx, y), (cx - 8, y + 1), (cx - 16, y - 1)]
    s = P.shade(base, 0.78)
    poly(surf, pts, s)
    for k in (-8, 0, 8):            # the pleats
        pygame.draw.line(surf, P.shade(s, 0.75), _pt(towards(a, b, 0.5 + k / 26)), _pt((cx + k, y - 1)), 1)


def satchel(surf, at, j, facing):
    """Alice the sender: a courier satchel on a strap across her chest, a letter sticking out of it."""
    hip, sh = j["hip"], j["shoulder_f"]
    a, b = at(sh, 2, 9), at(hip, 2, -11)
    pygame.draw.line(surf, P.INK, _pt(a), _pt(b), 5)
    pygame.draw.line(surf, LEATHER, _pt(a), _pt(b), 3)
    cx, cy = _pt(at(hip, -2, -12))
    env = pygame.Rect(0, 0, 11, 8)          # the letter, behind the flap: white, its own flap a V
    env.midbottom = (cx - 2 * facing, cy - 3)
    pygame.draw.rect(surf, P.INK, env.inflate(2, 2))
    surf.fill(P.WHITE, env)
    pygame.draw.lines(surf, P.MIST, False, [env.topleft, (env.centerx, env.y + 4), (env.right - 1, env.y)], 1)
    bag = pygame.Rect(0, 0, 16, 13)
    bag.center = (cx, cy + 3)
    pygame.draw.rect(surf, P.INK, bag.inflate(4, 4), border_radius=4)
    pygame.draw.rect(surf, LEATHER, bag, border_radius=3)
    flap = pygame.Rect(bag.x, bag.y, bag.w, 7)
    pygame.draw.rect(surf, LEATHER_DARK, flap, border_top_left_radius=3, border_top_right_radius=3)
    surf.fill(P.lighten(LEATHER, 0.5), (bag.centerx - 1, flap.bottom - 1, 3, 3))      # the buckle
    surf.fill(P.lighten(LEATHER, 0.3), (bag.x + 2, bag.y + 1, bag.w - 4, 1))


def back_limbs(surf, j, kitc, who, facing, w):
    top, sleeve, thigh, shin = kitc
    limb(surf, j["hip"], j["knee_b"], w + 1, P.shade(thigh, 0.78))
    limb(surf, j["knee_b"], j["foot_b"], w, P.shade(shin, 0.78))
    sneaker(surf, j["foot_b"], facing, P.shade(SNEAKER, 0.8))
    limb(surf, j["shoulder_b"], j["elbow_b"], w - 1, P.shade(top, 0.68))
    limb(surf, j["elbow_b"], j["hand_b"], w - 2, P.shade(sleeve, 0.68))
    _ball(surf, j["hand_b"], 5, P.shade(SKIN_A if who == "alice" else SKIN_B, 0.8))


def front_leg(surf, j, kitc, facing, w, strike):
    top, sleeve, thigh, shin = kitc
    if strike and strike[0] == "foot_f":
        lit_limb(surf, j["hip"], j["knee_f"], j["foot_f"], w + 1, strike[1])
    else:
        limb(surf, j["hip"], j["knee_f"], w + 1, thigh)
        limb(surf, j["knee_f"], j["foot_f"], w, shin)
    sneaker(surf, j["foot_f"], facing)
    if strike and strike[0] == "foot_f":
        tip(surf, j["foot_f"], w, strike[1], strike[2])


def front_arm(surf, j, kitc, who, w, strike):
    top, sleeve, thigh, shin = kitc
    hand = j["hand_f"]
    if strike and strike[0] == "hand_f":
        lit_limb(surf, j["shoulder_f"], j["elbow_f"], hand, w, strike[1])
        tip(surf, hand, w, strike[1], strike[2])
        return
    limb(surf, j["shoulder_f"], j["elbow_f"], w - 1, top)
    limb(surf, j["elbow_f"], hand, w - 2, sleeve)
    _ball(surf, towards(j["elbow_f"], hand, 0.82), 5, P.shade(top, 0.75))      # the ribbed cuff
    _ball(surf, hand, 5, SKIN_A if who == "alice" else SKIN_B)


# --- the heads (the look's variant A) --------------------------------------------------------------


def face(surf, hx, hy, f, skin):
    pygame.draw.circle(surf, skin, (hx + 4 * f, hy + 3), R - 4)
    for dx in (5, 12):                     # two big eyes, a glint in each
        fx_rect(surf, P.INK, hx, f, dx, hy + 1, 3, 5)
        fx_rect(surf, P.WHITE, hx, f, dx + 1, hy + 1, 1, 2)
    fx_rect(surf, BLUSH, hx, f, 2, hy + 7, 3, 2)
    fx_rect(surf, BLUSH, hx, f, 14, hy + 7, 2, 2)
    fx_rect(surf, P.shade(skin, 0.55), hx, f, 9, hy + 9, 2, 1)       # the mouth


def head_shell(surf, hx, hy, color):
    pygame.draw.circle(surf, P.INK, (hx, hy), R + 2)
    pygame.draw.circle(surf, color, (hx, hy), R)


def cap(surf, hx, hy, f, color):
    """A cap of the pair's colour over the top of the head, its brim forward."""
    pts = [(hx - (R + 2), hy - 1), (hx + (R + 2), hy - 1)]
    pygame.draw.circle(surf, P.INK, (hx, hy - 1), R + 3, draw_top_left=True, draw_top_right=True)
    pygame.draw.circle(surf, color, (hx, hy - 1), R + 1, draw_top_left=True, draw_top_right=True)
    pygame.draw.line(surf, P.INK, pts[0], pts[1], 2)
    pygame.draw.circle(surf, P.lighten(color, 0.5), (hx - 4 * f, hy - 10), 3)          # the shine
    _ball(surf, (hx, hy - R - 1), 2, P.shade(color, 0.8))                              # the button
    b = pygame.Rect(0, 0, 13, 4)
    if f > 0:
        b.midleft = (hx + R - 4, hy - 1)
    else:
        b.midright = (hx - R + 4, hy - 1)
    pygame.draw.rect(surf, P.INK, b.inflate(4, 4), border_radius=3)
    pygame.draw.rect(surf, P.shade(color, 0.72), b, border_radius=2)


def bow(surf, c, color=P.WHITE):
    """Alice's big hair bow: two loops and a knot."""
    x, y = _pt(c)
    for side in (-1, 1):
        pts = [(x, y), (x + side * 10, y - 6), (x + side * 11, y + 4)]
        pygame.draw.polygon(surf, P.INK, pts, 0)
        pygame.draw.polygon(surf, P.INK, pts, 4)
        inner = [(x + side * 1, y), (x + side * 9, y - 4), (x + side * 9, y + 2)]
        pygame.draw.polygon(surf, color, inner)
        pygame.draw.line(surf, P.shade(color, 0.75), (x + side * 3, y + 1), (x + side * 8, y + 1), 1)
    pygame.draw.circle(surf, P.INK, (x, y), 4)
    pygame.draw.circle(surf, color, (x, y), 2)


def head_alice(surf, j, f, part):
    """A blonde bob (its back drawn first, behind her), the face, the fringe, the big white bow."""
    hx, hy = _pt(j["head"])
    if part == "back":
        pygame.draw.circle(surf, P.INK, (hx - 4 * f, hy + 4), 11)
        pygame.draw.circle(surf, P.shade(BLONDE, 0.85), (hx - 4 * f, hy + 4), 9)
        return
    head_shell(surf, hx, hy, BLONDE)
    face(surf, hx, hy, f, SKIN_A)
    fringe = [(hx - 8 * f, hy - 12), (hx + 12 * f, hy - 9), (hx + 16 * f, hy - 1), (hx + 7 * f, hy - 3),
              (hx + 3 * f, hy), (hx - 2 * f, hy - 4)]
    pygame.draw.polygon(surf, BLONDE, [_pt(p) for p in fringe])
    pygame.draw.circle(surf, P.lighten(BLONDE, 0.55), (hx - 5 * f, hy - 8), 3)          # the shine
    pygame.draw.line(surf, BLONDE, (hx - 1 * f, hy + 2), (hx - 3 * f, hy + 12), 5)      # the bob past the ear
    bow(surf, (hx - 4 * f, hy - R - 3))


def head_bob(surf, j, base, f, part):
    """Dark hair under a cap of the pair's colour, and big headphones with a little aerial on one cup."""
    if part == "back":
        return
    hx, hy = _pt(j["head"])
    head_shell(surf, hx, hy, DARK_HAIR)
    face(surf, hx, hy, f, SKIN_B)
    cap(surf, hx, hy, f, P.shade(base, 0.8))
    band = pygame.Rect(0, 0, 2 * R + 8, 2 * R + 8)
    band.center = (hx - 2 * f, hy + 1)
    a0, a1 = (math.pi * 0.42, math.pi * 1.0) if f > 0 else (0.0, math.pi * 0.58)
    pygame.draw.arc(surf, P.INK, band.inflate(2, 2), a0, a1, 6)
    pygame.draw.arc(surf, PHONES, band, a0, a1, 3)
    cup = (hx - 3 * f, hy + 2)
    ant0 = (cup[0] - 5 * f, cup[1] - 6)
    ant1 = (cup[0] - 11 * f, cup[1] - 18)
    pygame.draw.line(surf, P.INK, _pt(ant0), _pt(ant1), 4)
    pygame.draw.line(surf, P.MIST, _pt(ant0), _pt(ant1), 2)
    _ball(surf, ant1, 3, P.lighten(base, 0.5))
    surf.set_at(_pt((ant1[0] - 1, ant1[1] - 1)), P.WHITE)
    e = pygame.Rect(0, 0, 12, 15)
    e.center = _pt(cup)
    pygame.draw.ellipse(surf, P.INK, e.inflate(4, 4))
    pygame.draw.ellipse(surf, PHONES, e)
    pygame.draw.ellipse(surf, CUSHION, e.inflate(-6, -6))
    pygame.draw.arc(surf, P.lighten(PHONES, 0.4), e.inflate(-2, -2), 1.6, 2.6, 1)


# --- ALICE and BOB ------------------------------------------------------------------------------------


def draw_kid(surf, j, facing, base, who, strike=None) -> dict:
    """One of the pair at the joints `j` (poses.joints, build "alice" or "bob") in the pair's basis
    colour `base`. `strike` = (joint, colour) or (joint, colour, active) lights an attack's arm
    or leg (active: the big tip of its live frames). Returns j."""
    if strike is not None and len(strike) == 2:
        strike = (*strike, False)
    at = frame(j, facing)
    kitc = kit(base)
    if who == "alice":
        head_alice(surf, j, facing, "back")
    back_limbs(surf, j, kitc, who, facing, W)
    front_leg(surf, j, kitc, facing, W, strike)
    torso(surf, at, j, kitc[0])
    if who == "alice":
        skirt(surf, j, at, base)
        satchel(surf, at, j, facing)
        head_alice(surf, j, facing, "front")
    else:
        head_bob(surf, j, base, facing, "front")
    front_arm(surf, j, kitc, who, W, strike)
    return j


def draw_pair(surf, pose, feet, facing, base, gap=40, bob_base=None) -> tuple[dict, dict]:
    """Both at once, Bob `gap` px behind Alice (drawn first, behind her), as the screens show
    them, Bob in `bob_base` (their other colour) if given. Returns Alice's joints and Bob's."""
    bx = feet[0] - facing * gap
    jb = draw_kid(surf, joints(pose, "bob", (bx, feet[1]), facing), facing, bob_base or base, "bob")
    ja = draw_kid(surf, joints(pose, "alice", feet, facing), facing, base, "alice")
    return ja, jb


# --- their specials (the look's) -------------------------------------------------------------------


def photon(surf, c, color, facing, big=False):
    """A photon (render._shot's); `big` is KEY EXCHANGE's strong shot: larger, a longer trail,
    speed lines."""
    cx, cy = c
    back = -facing
    if big:
        for dy, ln in ((-7, 20), (0, 30), (7, 18)):
            x0 = cx + back * 14
            pygame.draw.line(surf, P.INK, _pt((x0, cy + dy)), _pt((x0 + back * ln, cy + dy)), 4)
            pygame.draw.line(surf, P.lighten(color, 0.4), _pt((x0, cy + dy)), _pt((x0 + back * ln, cy + dy)), 2)
        glow(surf, c, 22, color, 150)
    steps = ((4, 3), (3, 4), (2, 5), (1, 6)) if big else ((3, 2), (2, 3), (1, 4))
    for i, r in steps:
        pygame.draw.circle(surf, P.shade(color, 0.5 + 0.12 * (3 - i)),
                           _pt((cx + back * ((8 if big else 6) + i * (8 if big else 6)), cy)), r)
    r = 11 if big else 7
    pygame.draw.circle(surf, P.lighten(color, 0.45), _pt(c), r + 2, 1)
    pygame.draw.circle(surf, P.INK, _pt(c), r)
    pygame.draw.circle(surf, color, _pt(c), r - 1)
    pygame.draw.circle(surf, P.lighten(color, 0.6), _pt(c), r - (5 if big else 4))
    surf.fill(P.WHITE, (round(cx) - 2 - facing, round(cy) - 3, 2, 2))


def lob(surf, a, b, color, k_at=0.62, height=34):
    """KEY EXCHANGE's toss: a dotted arc from Alice's hand back to Bob's, the photon on it at
    `k_at` of the way, and a ring round his hand where it will land."""
    def on(k):
        return (a[0] + (b[0] - a[0]) * k, a[1] + (b[1] - a[1]) * k - height * 4 * k * (1 - k))
    for i in range(1, 16):
        k = i / 16
        if k < k_at - 0.04:
            p = _pt(on(k))
            surf.fill(P.INK, (p[0] - 2, p[1] - 2, 4, 4))
            surf.fill(P.lighten(color, 0.4), (p[0] - 1, p[1] - 1, 2, 2))
    c = on(k_at)
    glow(surf, c, 12, color, 150)
    pygame.draw.circle(surf, P.INK, _pt(c), 7)
    pygame.draw.circle(surf, color, _pt(c), 6)
    pygame.draw.circle(surf, P.lighten(color, 0.6), _pt(c), 2)
    surf.set_at((round(c[0]) - 1, round(c[1]) - 2), P.WHITE)
    rr = pygame.Rect(0, 0, 26, 26)
    rr.center = _pt(b)
    pygame.draw.arc(surf, P.INK, rr.inflate(2, 2), 0.3, 2.8, 3)
    pygame.draw.arc(surf, P.lighten(color, 0.5), rr, 0.3, 2.8, 1)


@lru_cache(maxsize=16)
def _column(color, k: float) -> pygame.Surface:
    col = pygame.Surface((36, 150))
    for ww, a in ((36, 0.18), (22, 0.32), (10, 0.6)):
        r = pygame.Rect(0, 0, ww, 150)
        r.centerx = 18
        pygame.draw.rect(col, tuple(round(v * a * k) for v in P.lighten(color, 0.4)), r, border_radius=ww // 2)
    return col


def flash(surf, x, color, k=1.0, floor=FLOOR_Y):
    """TELEPORT's flash: a column of light on the spot, a ring on the floor, a four-point star.
    `k` (0..1): how bright the column still is."""
    surf.blit(_column(color, round(k, 2)), (round(x) - 18, floor - 140), special_flags=pygame.BLEND_RGB_ADD)
    fl = pygame.Rect(0, 0, 54, 12)
    fl.center = (round(x), floor + 2)
    pygame.draw.ellipse(surf, P.INK, fl.inflate(4, 4), 4)
    pygame.draw.ellipse(surf, P.lighten(color, 0.6), fl, 2)
    sx, sy = round(x), floor - 128
    for (dx, dy), n in (((1, 0), 9), ((0, 1), 9)):
        pygame.draw.line(surf, P.INK, (sx - dx * n, sy - dy * n), (sx + dx * n, sy + dy * n), 4)
        pygame.draw.line(surf, P.WHITE, (sx - dx * n, sy - dy * n), (sx + dx * n, sy + dy * n), 2)
    pygame.draw.circle(surf, P.WHITE, (sx, sy), 2)


def swap_arc(surf, a, b, y, color):
    """The swap's path: a dotted arc between the two flashes, over whoever stands between them,
    an arrowhead at each end."""
    pts = []
    for i in range(0, 21):
        k = i / 20
        pts.append((a + (b - a) * k, y - 22 * 4 * k * (1 - k)))
    for i, p in enumerate(pts[1:-1]):
        if i % 2 == 0:
            q = _pt(p)
            surf.fill(P.INK, (q[0] - 2, q[1] - 2, 4, 4))
            surf.fill(P.lighten(color, 0.5), (q[0] - 1, q[1] - 1, 2, 2))
    for end in (pts[0], pts[-1]):
        x, yy = _pt(end)
        tri = [(x, yy + 2), (x - 4, yy - 5), (x + 4, yy - 5)]
        pygame.draw.polygon(surf, P.INK, tri, 0)
        pygame.draw.polygon(surf, P.INK, tri, 3)
        pygame.draw.polygon(surf, P.lighten(color, 0.5), [(x, yy), (x - 2, yy - 4), (x + 2, yy - 4)])


def streaks(surf, a, b, color, n=3):
    """Motion lines along a dive, from a towards b."""
    dx, dy = b[0] - a[0], b[1] - a[1]
    L = math.hypot(dx, dy) or 1
    px, py = -dy / L, dx / L
    for k, off in enumerate((-9, 0, 9)[:n]):
        s = (a[0] + px * off, a[1] + py * off)
        e = (s[0] + dx * (0.55 + 0.15 * (k == 1)), s[1] + dy * (0.55 + 0.15 * (k == 1)))
        pygame.draw.line(surf, P.INK, _pt(s), _pt(e), 4)
        pygame.draw.line(surf, P.lighten(color, 0.45), _pt(s), _pt(e), 2)


def dive_streaks(surf, j, feet, facing, color):
    """BELL DIVE's streaks behind a diver whose feet are at `feet`: from up and behind to the hip."""
    streaks(surf, (feet[0] - facing * 34, feet[1] - 56), j["hip"], color)


# --- Bob decohered --------------------------------------------------------------------------------


@lru_cache(maxsize=16)
def _decohered_body(base, facing: int, feet: tuple[float, float]):
    """Bob standing at `feet` (in a layer DECOHERED_SIZE big, placed so `feet` falls on
    DECOHERED_AT plus its fraction), see-through, and his outline: (layer, outline, joints, left, top)."""
    left, top = math.floor(feet[0]) - DECOHERED_AT[0], math.floor(feet[1]) - DECOHERED_AT[1]
    local = (feet[0] - left, feet[1] - top)
    tmp = pygame.Surface(DECOHERED_SIZE, pygame.SRCALPHA)
    j = draw_kid(tmp, joints(POSES["idle"], "bob", local, facing), facing, base, "bob")
    outline = pygame.mask.from_surface(tmp).outline()
    tmp.fill((255, 255, 255, 140), special_flags=pygame.BLEND_RGBA_MULT)
    jj = {k: (x + left, y + top) for k, (x, y) in j.items()}
    return tmp, tuple((x + left, y + top) for x, y in outline), jj, left, top


def draw_decohered(surf, feet, facing, base, t=0) -> dict:
    """Bob decohering: standing, see-through, the top of him breaking into scanlines and motes
    that drift up, his outline flickering in a pale tint of their colour; `t` moves the flicker
    and the motes on. Returns his joints."""
    tmp, outline, j, left, top_y = _decohered_body(base, facing, (float(feet[0]), float(feet[1])))
    w, h = tmp.get_size()
    sw, sh = surf.get_size()
    top = round(j["head"][1]) - 22
    cut = round(j["head"][1]) + 4           # above this he is breaking up
    for row in range(max(0, top_y + (top_y & 1)), min(sh, top_y + h), 2):
        if row < top:
            continue
        if row < cut:
            k = (row - top) / max(1, cut - top)          # 0 at the top of his head, 1 at the cut
            if ((row // 2) * 7 + t) % 10 >= 6 + 3 * k:
                continue
            dx = round((1 - k) * 5 * math.sin(row * 0.9 + t))
        else:
            dx = 0
        surf.blit(tmp, (left + dx, row), (0, row - top_y, w, 2))
    lit = P.lighten(base, 0.6)
    for i, p in enumerate(outline):
        if p[1] < cut - 10 or (i // 5 + t) % 3 == 0:
            continue                        # the flicker: a dashed, broken edge
        if 0 <= p[0] < sw and 0 <= p[1] < sh:
            surf.set_at(p, lit)
    rnd = random.Random(11 + t)
    for i in range(22):                     # the motes: bits of him rising off the top
        x = j["head"][0] + rnd.uniform(-18, 18) - facing * rnd.uniform(0, 8)
        y = j["head"][1] - rnd.uniform(-14, 46)
        size = rnd.choice((2, 2, 3, 4))
        k = max(0.15, 1 - (j["head"][1] + 14 - y) / 60)
        c = P.lighten(base, 0.25 + 0.5 * (1 - k)) if i % 3 else P.shade(DARK_HAIR, 1.4)
        q = pygame.Surface((size, size))
        q.fill(c)
        q.set_alpha(round(255 * k))
        surf.blit(q, (round(x), round(y)))
    return j


# --- the shared bar's Bob ------------------------------------------------------------------------

BOB_ICON = 20                    # px square, by the pair's A / B chips


@lru_cache(maxsize=8)
def bob_icon(base, gone: bool) -> pygame.Surface:
    """Bob's head (cap and headphones, in the pair's colour `base`) for the HUD, BOB_ICON px;
    greyed and faint while he is decohered."""
    big = pygame.Surface((48, 48), pygame.SRCALPHA)
    head_bob(big, {"head": (24, 27)}, base, 1, "front")
    icon = pygame.transform.scale(big, (BOB_ICON, BOB_ICON))
    if gone:
        icon = pygame.transform.grayscale(icon)
        icon.fill((255, 255, 255, 110), special_flags=pygame.BLEND_RGBA_MULT)
    return icon
