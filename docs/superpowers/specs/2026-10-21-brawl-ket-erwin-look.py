"""ERWIN's approved look (2026-10-21): Schrodinger's cat, the upright mascot, the reference for render.py.

A prototype, not game code, in the manner of PHOEBE's look script: it draws on Brawl-Ket's
own skeleton (poses.joints, POSES) and render helpers (limb, _ball, _pt, make_stage), at
the game's 640x360 scale. Run it from brawl-ket/:

    uv run python ../docs/superpowers/specs/2026-10-21-brawl-ket-erwin-look.py OUT.png

New in v2:
- real cat legs, on the shared skeleton: each leg's hip, knee and foot joints come from
  poses.joints as for everyone; a hock is added between knee and foot, pushed back off the
  knee-foot line, so the leg reads thigh forward, long lower leg back, heel high, standing
  on the toe pads. Every shared pose still works.
- THE BOX as a superposition: two holographic boxes in her basis colour at once, one cat in
  two places, then the collapse: one turns into real cardboard in a flash while the other
  fades out.
"""

import math
import sys

import pygame

from brawl_ket import palette as P
from brawl_ket import poses as PS
from brawl_ket.config import FLOOR_Y, PLAYER_COLORS
from brawl_ket.fonts import load_font
from brawl_ket.poses import POSES, joints
from brawl_ket.render import GREEN, PURPLE, SHADOW, _ball, _pt, draw_puppet, limb, make_stage

# ERWIN's build: ROBERT's height, a bigger head on a short neck; the shin is long because it
# holds two leg segments (the cat's lower leg and its long foot, up to the hock)
PS.SCALE["cat"] = 2.1
PS.BUILD_BONES["cat"] = {"torso": 24, "neck": 7, "thigh": 15, "shin": 18, "upper_arm": 12, "forearm": 12}
PS.HEAD_R["cat"] = 17
PS.LIMB_W["cat"] = 13

NOSE = (240, 136, 168)
EYE = (248, 208, 64)            # amber: the one warm accent, as BOHR's gold
CARD = (200, 144, 88)
CARD_DARK = (152, 104, 64)
CARD_DEEP = (104, 64, 40)
CARD_LIGHT = (224, 176, 120)
TAPE = (232, 208, 160)


# --- shared helpers ------------------------------------------------------------------------


def frame(j, facing):
    """at(base, up, front): a point `up` px along the spine and `front` px towards the face."""
    hip, neck = j["hip"], j["neck"]
    tx, ty = neck[0] - hip[0], neck[1] - hip[1]
    n = math.hypot(tx, ty) or 1.0
    ux, uy = tx / n, ty / n
    fx, fy = -uy * facing, ux * facing

    def at(base, up, front):
        return (base[0] + ux * up + fx * front, base[1] + uy * up + fy * front)
    return at


def towards(a, b, k):
    return (a[0] + (b[0] - a[0]) * k, a[1] + (b[1] - a[1]) * k)


def poly(surf, pts, color, ink=2):
    pts = [_pt(p) for p in pts]
    pygame.draw.polygon(surf, color, pts)
    if ink:
        pygame.draw.polygon(surf, P.INK, pts, ink)


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


def ring(surf, x, key, width=52):
    """The game's shadow under a fighter, ringed in the player's colour (P1 blue, P2 red)."""
    rect = pygame.Rect(0, 0, width + 8, 12)
    rect.center = (round(x), FLOOR_Y + 2)
    pygame.draw.ellipse(surf, SHADOW, rect)
    pygame.draw.ellipse(surf, P.INK, rect.inflate(2, 2), 3)
    pygame.draw.ellipse(surf, PLAYER_COLORS[key], rect, 2)


def label(surf, text, center, color=P.WHITE):
    f = load_font(8)
    ink, core = f.render(text, False, P.INK), f.render(text, False, color)
    r = core.get_rect(center=center)
    for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1), (1, 1)):
        surf.blit(ink, r.move(dx, dy))
    surf.blit(core, r)


def ghost(surf, draw, alpha=130):
    """Draw something see-through: onto a scratch layer, then thinned out and blitted."""
    layer = pygame.Surface(surf.get_size())
    key = (255, 0, 255)
    layer.fill(key)
    layer.set_colorkey(key)
    draw(layer)
    # every third row a little more see-through: it shimmers, like a state not yet real
    thin = layer.copy()
    for y in range(0, thin.get_height(), 3):
        thin.fill(key, (0, y, thin.get_width(), 1))
    layer.set_alpha(alpha // 2)
    thin.set_alpha(alpha + 40)
    surf.blit(layer, (0, 0))
    surf.blit(thin, (0, 0))


# --- cat parts -----------------------------------------------------------------------------


def paw(surf, p, r, color):
    """A round mitten paw with two toe creases."""
    _ball(surf, p, r, color)
    x, y = _pt(p)
    for dx in (-2, 2):
        pygame.draw.line(surf, P.shade(color, 0.6), (x + dx, y + 1), (x + dx, y + r - 1), 1)


def foot(surf, f, facing, color):
    """A hind paw: an oval pad, toes forward, with two toe creases."""
    r = pygame.Rect(0, 0, 20, 10)
    r.midbottom = _pt((f[0] + 4 * facing, f[1] + 7))
    pygame.draw.ellipse(surf, P.INK, r.inflate(4, 4))
    pygame.draw.ellipse(surf, color, r)
    tx = r.right - 5 if facing > 0 else r.left + 5
    for dx in (0, -4 * facing):
        pygame.draw.line(surf, P.shade(color, 0.6), (tx + dx, r.top + 2), (tx + dx, r.bottom - 2), 1)


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
    # ears: the far one (in shade), the near one, each with a pale inside
    for base_a, base_b, tip, col, ins in (
            ((X(-r - 1), hy - r + 9), (X(-3), hy - r + 1), (X(-r + 1), hy - r - 13), dark, P.shade(inner, 0.75)),
            ((X(-5), hy - r + 1), (X(r - 1), hy - r + 7), (X(4), hy - r - 15), fur, inner)):
        pts = [_pt(base_a), _pt(tip), _pt(base_b)]
        pygame.draw.polygon(surf, P.INK, pts, 0)
        pygame.draw.lines(surf, P.INK, True, pts, 5)
        pygame.draw.polygon(surf, col, pts)
        mid = towards(base_a, base_b, 0.5)
        poly(surf, [towards(base_a, mid, 0.45), towards(tip, mid, 0.28), towards(base_b, mid, 0.45)], ins, ink=0)
    # the skull: an oval, wider than tall, with a cheek tuft behind
    head = pygame.Rect(0, 0, 2 * r + 8, 2 * r - 2)
    head.center = (hx, hy)
    # the cheek ruff: two soft points at the back of the jaw, under the skull's outline
    for tip, y0, y1 in (((X(-r - 9), hy + 3), hy - 3, hy + 6), ((X(-r - 6), hy + 11), hy + 4, hy + 12)):
        pts = [_pt((X(-r + 3), y0)), _pt(tip), _pt((X(-r + 5), y1))]
        pygame.draw.polygon(surf, P.INK, pts)
        pygame.draw.lines(surf, P.INK, True, pts, 5)
        pygame.draw.polygon(surf, fur, pts)
    pygame.draw.ellipse(surf, P.INK, head.inflate(4, 4))
    pygame.draw.ellipse(surf, fur, head)
    # a shine on the crown
    surf.fill(P.lighten(fur, 0.5), (X(-8) - (2 if f < 0 else 0), hy - r + 5, 3, 3))
    # the muzzle: pale, low and forward, breaking the outline at the front
    muz = pygame.Rect(0, 0, 22, 14)
    muz.center = (X(9), hy + 7)
    pygame.draw.ellipse(surf, light, muz)
    # eyes: big ovals, the far one narrower, slit pupils, a white shine
    for ex, ew in ((X(0), 10), (X(13), 8)):
        eye = pygame.Rect(0, 0, ew, 12)
        eye.center = (ex, hy - 2)
        pygame.draw.ellipse(surf, P.INK, eye.inflate(4, 4))
        pygame.draw.ellipse(surf, EYE, eye)
        surf.fill(P.INK, (ex - 1 + (1 if f > 0 else 0), hy - 6, 2, 9))
        surf.fill(P.WHITE, (ex - 3 * f - (1 if f < 0 else 0), hy - 6, 2, 2))
    if peek:
        return
    # nose and mouth: a pink nose at the muzzle's top front, a small ink "w" under it
    nx, ny = X(16), hy + 4
    pygame.draw.polygon(surf, P.INK, [(nx - 5 * f, ny - 2), (nx + 2 * f, ny - 2), (nx - f, ny + 3)])
    pygame.draw.polygon(surf, NOSE, [(nx - 4 * f, ny - 1), (nx + 1 * f, ny - 1), (nx - f, ny + 1)])
    pygame.draw.line(surf, P.INK, (nx - f, ny + 3), (nx - f, ny + 5), 1)
    pygame.draw.lines(surf, P.INK, False, [(nx - 6 * f, ny + 6), (nx - 3 * f, ny + 7), (nx - f, ny + 5),
                                            (nx + 1 * f, ny + 7)], 1)
    # whiskers: two fine pale lines fanning forward off the muzzle, past the head's outline
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


# --- THE BOX ---------------------------------------------------------------------------------


def box(surf, x, w, h, facing, fur, peek=True, floor=FLOOR_Y, head_r=16):
    """A cardboard box on the floor, its flaps open; her ears and eyes peek over the rim.
    Drawn in 3/4: the front face, the side face going back, the open top."""
    d = 10                                       # depth: the side face's slant
    f = facing
    left, top = round(x - w / 2), floor - h + 4
    front = pygame.Rect(left, top, w, h)
    # the back rim of the opening (up and back by the depth), and the back flap standing up
    bl, br = (left + d, top - d), (left + w + d, top - d)
    poly(surf, [bl, (bl[0] + 4, bl[1] - 22), (br[0] - 4, br[1] - 22), br], CARD_DARK)
    # the dark inside
    poly(surf, [(left, top), bl, br, (left + w, top)], CARD_DEEP)
    if peek:
        # her head, sunk in: only the ears and eyes clear the front rim
        hx = x + d / 2 + 2 * f
        layer = surf.subsurface(pygame.Rect(0, 0, surf.get_width(), top + 1))
        cat_head(layer, (hx, top - 7), head_r, facing, fur, P.lighten(fur, 0.55), peek=True)
    # the side face, going back, in shade
    poly(surf, [(left + w, top), (left + w + d, top - d), (left + w + d, top - d + h), (left + w, top + h)], CARD_DARK)
    # the far side flap, hinged on the side face's top edge and swung out and up
    poly(surf, [(left + w, top), (left + w + d, top - d), (left + w + d + 17, top - d + 3), (left + w + 17, top + 3)],
         CARD_LIGHT)
    # the front face, a fold line and a strip of tape down the middle
    poly(surf, [front.topleft, front.topright, front.bottomright, front.bottomleft], CARD)
    surf.fill(CARD_LIGHT, (left + 3, top + 3, w - 6, 2))
    tx = left + w // 2
    surf.fill(TAPE, (tx - 4, top + 2, 8, 16))
    surf.fill(P.shade(TAPE, 0.85), (tx - 4, top + 16, 8, 2))
    # the near side flap, swung out towards us, and the front flap folded down over the face
    poly(surf, [(left, top), (left - 14, top - 14), (left - 4, top - 18), (left + d, top - d)], CARD_LIGHT)
    poly(surf, [(left + 2, top), (left + w - 2, top), (left + w - 6, top + 12), (left + 6, top + 12)], CARD_LIGHT)
    surf.fill(TAPE, (tx - 4, top + 2, 8, 9))
    pygame.draw.line(surf, P.INK, (left + 6, top + 12), (left + w - 6, top + 12), 2)
    # a printed "this side up": two arrows on the front face, the one marking a box carries
    for ax in (left + 10, left + w - 18):
        ay = top + h - 14
        pygame.draw.polygon(surf, CARD_DEEP, [(ax + 4, ay - 5), (ax, ay), (ax + 8, ay)])
        surf.fill(CARD_DEEP, (ax + 3, ay, 2, 6))
    # its shadow on the floor
    return front


# --- ERWIN: the upright cat on cat legs ------------------------------------------------------


def cat_leg_points(j, side, facing):
    """The cat leg drawn over the skeleton's hip, knee and foot: the knee nudged forward, a
    hock added halfway down the knee-foot line and pushed well off it towards the back (for a
    standing leg; under it for a kick), so the leg reads thigh forward, long lower leg back to
    a high heel, the long foot forward and down to the toe pads on the foot joint."""
    k, ft = j[f"knee_{side}"], j[f"foot_{side}"]
    dx, dy = ft[0] - k[0], ft[1] - k[1]
    n = math.hypot(dx, dy) or 1.0
    bx, by = -dy / n * facing, dx / n * facing        # perpendicular, towards the back
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


def draw_erwin(surf, pose, feet, facing, fur, strike=None):
    """ERWIN on the shared skeleton. `strike` ("hand_f" or "foot_f", colour) lights an attack's
    whole arm or leg in its colour, as the game does."""
    light = P.lighten(fur, 0.55)                # belly, muzzle, paws: a pale shade of her fur
    dark = P.shade(fur, 0.68)
    j = joints(pose, "cat", feet, facing)
    at = frame(j, facing)
    w = PS.LIMB_W["cat"]
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
    # the haunch's curve, where the thigh meets the hip
    hx, hy = _pt(towards(hip, j["knee_f"], 0.25))
    pygame.draw.arc(surf, P.shade(lit or fur, 0.78), (hx - 9, hy - 9, 18, 18),
                    math.radians(60 if facing > 0 else 0), math.radians(180 if facing > 0 else 120), 2)
    # 5. the head
    cat_head(surf, j["head"], PS.HEAD_R["cat"], facing, fur, light)
    # 6. the front arm, in front of everything
    arm = strike[1] if strike and strike[0] == "hand_f" else fur
    limb(surf, j["shoulder_f"], j["elbow_f"], w - 1, arm)
    limb(surf, j["elbow_f"], j["hand_f"], w - 2, arm)
    paw(surf, j["hand_f"], 7, light if arm is fur else P.lighten(arm, 0.5))
    return j


# --- THE BOX, in superposition ------------------------------------------------------------------

KEY = (255, 0, 255)
BOX_W, BOX_H = 70, 52


def _layer(size):
    s = pygame.Surface(size)
    s.fill(KEY)
    s.set_colorkey(KEY)
    return s


def holo_box(surf, x, facing, fur, alpha=215, fade=0.0, seed=0):
    """A holographic box: the same box with her ears and eyes over the rim, recoloured into
    her basis colour with glowing edges, see-through, with scanline gaps and a few rows
    slipped sideways (it shimmers). `fade` 0..1 dissolves it away."""
    layer = _layer(surf.get_size())
    box(layer, x, BOX_W, BOX_H, facing, fur)
    glow = P.lighten(fur, 0.75)
    pa = pygame.PixelArray(layer)
    for src, dst in ((P.INK, glow), (CARD, fur), (CARD_LIGHT, P.lighten(fur, 0.3)), (CARD_DARK, P.shade(fur, 0.7)),
                     (CARD_DEEP, P.shade(fur, 0.4)), (TAPE, P.lighten(fur, 0.45)),
                     (P.shade(TAPE, 0.85), P.lighten(fur, 0.25)), (EYE, P.WHITE)):
        pa.replace(src, dst)
    del pa
    out = _layer(surf.get_size())
    top = FLOOR_Y - BOX_H - 40
    width = surf.get_width()
    for y in range(top, FLOOR_Y + 8):
        if y % 3 == 0:                                 # a scanline gap: only the glowing edges
            row = layer.subsurface((0, y, width, 1)).copy()
            pa = pygame.PixelArray(row)
            for c in (fur, P.lighten(fur, 0.3), P.shade(fur, 0.7), P.shade(fur, 0.4), P.lighten(fur, 0.45),
                      P.lighten(fur, 0.25), P.lighten(fur, 0.55)):
                pa.replace(c, KEY)
            del pa
            row.set_colorkey(KEY)
            out.blit(row, (0, y))
            continue
        slip = 2 if (y // 2 + seed) % 9 == 0 else (-1 if (y + seed) % 13 == 0 else 0)
        out.blit(layer, (slip, y), (0, y, width, 1))
    if fade > 0:                                       # dissolving: an ordered dither eats it
        for y in range(top, FLOOR_Y + 8):
            for xx in range(round(x) - 50, round(x) + 50):
                if ((xx * 7 + y * 13) % 10) / 10 < fade:
                    out.set_at((xx, y), KEY)
    # the light it stands in: a pale ellipse on the floor
    base = pygame.Rect(0, 0, BOX_W + 26, 12)
    base.center = (round(x) + 4, FLOOR_Y + 2)
    pool = _layer(surf.get_size())
    pygame.draw.ellipse(pool, P.lighten(fur, 0.3), base, 2)
    pool.set_alpha(round(140 * (1 - fade)))
    surf.blit(pool, (0, 0))
    out.set_alpha(round(alpha * (1 - 0.5 * fade)))
    surf.blit(out, (0, 0))


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


def collapse_flash(surf, x, fur):
    """The moment it collapses: a white rim round the now-real box, rays bursting off it and
    two glints, in white and her colour."""
    layer = _layer(surf.get_size())
    box(layer, x, BOX_W, BOX_H, 1, fur)
    mask = pygame.mask.from_surface(layer)
    rim = mask.to_surface(setcolor=(*P.WHITE, 255), unsetcolor=(0, 0, 0, 0))
    for dx, dy in ((-2, 0), (2, 0), (0, -2), (0, 2), (-1, -1), (1, 1), (-1, 1), (1, -1)):
        surf.blit(rim, (dx, dy))
    cx, cy = x + 5, FLOOR_Y - BOX_H / 2 - 8
    for k in range(9):
        a = math.radians(-180 + k * 22.5)               # only upwards and sideways
        r0, r1 = 54, 74 + (k % 2) * 12
        p0 = (cx + math.cos(a) * r0, cy + math.sin(a) * r0 * 0.85)
        p1 = (cx + math.cos(a) * r1, cy + math.sin(a) * r1 * 0.85)
        pygame.draw.line(surf, P.INK, _pt(p0), _pt(p1), 6)
        pygame.draw.line(surf, P.WHITE if k % 2 else P.lighten(fur, 0.5), _pt(p0), _pt(p1), 3)
    star(surf, (x - BOX_W / 2 - 4, FLOOR_Y - BOX_H - 10), 9, P.WHITE)
    star(surf, (x + BOX_W / 2 + 16, FLOOR_Y - BOX_H - 22), 6, P.lighten(fur, 0.6))


# --- the sheet ---------------------------------------------------------------------------------


def robert(surf, x, facing=1, key="p1", pose="idle"):
    ring(surf, x, key)
    draw_puppet(surf, POSES[pose], "lean", (x, FLOOR_Y), facing, GREEN, P.CREAM)


def row_stance(sub):
    robert(sub, 46)
    label(sub, "ROBERT", (46, 128))
    for x, name, fur, facing, key, strike, text in (
            (150, "idle", GREEN, 1, "p1", None, "ERWIN"), (250, "idle", PURPLE, -1, "p2", None, "ERWIN"),
            (370, "heavy_hit", GREEN, 1, "p1", ("hand_f", PURPLE), "HEAVY HIT"),
            (530, "heavy_hit", PURPLE, -1, "p2", ("hand_f", GREEN), "HEAVY HIT")):
        ring(sub, x, key)
        draw_erwin(sub, POSES[name], (x, FLOOR_Y), facing, fur, strike)
        label(sub, text, (x, 124))


def row_moves(sub):
    for x, name, fur, facing, key, dy, strike, ly in (
            (56, "crouch", GREEN, 1, "p1", 0, None, 168), (166, "crouch", PURPLE, -1, "p2", 0, None, 168),
            (284, "jump", GREEN, 1, "p1", -56, None, 70), (404, "jump", PURPLE, -1, "p2", -56, None, 70),
            (532, "sweep_hit", GREEN, 1, "p1", 0, ("foot_f", PURPLE), 168)):
        ring(sub, x, key)
        draw_erwin(sub, POSES[name], (x, FLOOR_Y + dy), facing, fur, strike)
        label(sub, name.upper().replace("_HIT", ""), (x, ly))


def row_superposed(sub, fur):
    """(a) THE BOX in superposition: the same box, ears and eyes over its rim, at two places
    at once, one on each side of ROBERT, joined by a dotted arc. Neither can be hit."""
    near, far = 150, 486
    dotted_arc(sub, (near + 5, FLOOR_Y - BOX_H - 34), (far + 5, FLOOR_Y - BOX_H - 34), 66, P.lighten(fur, 0.45))
    robert(sub, 318, -1, "p2", "heavy_hit")
    holo_box(sub, near, 1, fur, seed=0)
    holo_box(sub, far, 1, fur, seed=5)
    label(sub, "BOX: TWO PLACES AT ONCE", (320, 40))


def row_collapse(sub, fur):
    """(b) The collapse: the far box (behind ROBERT) becomes real cardboard in a flash; the
    near one dissolves."""
    near, far = 150, 486
    robert(sub, 318, -1, "p2", "heavy_recover")
    holo_box(sub, near, 1, fur, fade=0.6, seed=2)
    ring(sub, far, "p1", width=BOX_W + 6)
    collapse_flash(sub, far, fur)
    box(sub, far, BOX_W, BOX_H, 1, fur)
    label(sub, "COLLAPSE: ONE REAL BOX", (320, 40))


def main(out: str) -> None:
    pygame.init()
    stage, _ = make_stage("lab")
    rows = (row_stance, row_moves, lambda s: row_superposed(s, GREEN), lambda s: row_collapse(s, GREEN),
            lambda s: row_superposed(s, PURPLE), lambda s: row_collapse(s, PURPLE))
    sheet = pygame.Surface((640, 360 * len(rows)))
    for i, draw in enumerate(rows):
        sub = sheet.subsurface((0, i * 360, 640, 360))
        sub.blit(stage, (-8, -8))
        draw(sub)
    pygame.image.save(pygame.transform.scale(sheet, (1280, 720 * len(rows))), out)


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "cat_sheet_v2.png")
