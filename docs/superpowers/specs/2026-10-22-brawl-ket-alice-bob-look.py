"""ALICE & BOB's approved look (2026-10-22): variant A, COURIERS, with Bob 40 px behind Alice
(GAP), the reference for porting them into the game. The user picked A, COURIERS. Row 1 is A as in v1,
row 2 compares Bob 30 px and 40 px behind Alice, row 3 is the specials on A, with a new
decoherence (Bob standing, see-through, breaking up into scanlines and motes).

v1 notes follow. two small fighters played as one, cryptography's pair.
Alice sends, Bob receives; Bob echoes her inputs 0.2 s later, about 30 px behind her. Both are
always in the same basis colour (entangled), so the pair reads green or purple as one.

A prototype, not game code, in the manner of PHOEBE's, ERWIN's, DOS's and M-CUTIE's look
scripts: it draws on Brawl-Ket's own skeleton (poses.joints, POSES) and ink helpers (limb,
_ball, _pt, make_stage), at the game's 640x360 scale, on the SERVER RACK stage. Run it from
brawl-ket/:

    uv run python ../docs/superpowers/specs/2026-10-22-brawl-ket-alice-bob-look.py OUT.png

Both are a new, smaller build, "kid": about 0.78 of ROBERT's height, a big head on a short
body, the toy/puppet language of the others.

- A, COURIERS: kid messengers in matching hoodies of their colour. Alice the sender: a white
  hair bow on a blonde bob, and a courier satchel with a letter in it. Bob the receiver: a cap
  and big headphones with a little aerial on one cup.
- B, BATTERY: a baseball pitcher and catcher in one team's kit (jersey of their colour, white
  piping, pale trousers, dark socks). Alice the pitcher: a cap with a blonde ponytail through
  it, a small glove. Bob the catcher, the receiver: helmet and face cage, chest protector, shin
  guards and the big round catcher's mitt.

Row 3 shows the specials and decoherence (on MOVES_VARIANT): KEY EXCHANGE (Alice lobs a photon
back to Bob, Bob fires it forward as one strong shot), TELEPORT (they swap places past a rival,
a flash at both ends), BELL DIVE (two dives on one line, Bob 0.2 s behind) and Bob decohered
(knocked down, dissolving for 3 s).
"""

import math
import sys

import pygame

from brawl_ket import palette as P
from brawl_ket import poses as PS
from brawl_ket.config import FLOOR_Y, PLAYER_COLORS
from brawl_ket.fonts import load_font
from brawl_ket.poses import POSES, Pose, joints
from brawl_ket.render import GREEN, PURPLE, SHADOW, _ball, _pt, draw_puppet, limb, make_stage

# the "kid" builds: a short body and a big head, about 0.8 of ROBERT's height; Bob a little
# taller than Alice (a longer back and neck), so his head clears hers when he stands behind
for build, torso_len, neck in (("alice", 19, 7), ("bob", 21, 8.5)):
    PS.SCALE[build] = 1.85
    PS.BUILD_BONES[build] = {"torso": torso_len, "shoulder": torso_len - 3, "neck": neck, "thigh": 14,
                             "shin": 14, "upper_arm": 11, "forearm": 11}
    PS.HEAD_R[build] = 15
    PS.LIMB_W[build] = 11
PS.SCALE["kid"], PS.HEAD_R["kid"], PS.LIMB_W["kid"] = 1.85, 15, 11

GAP = 40                         # Bob stands this far behind Alice (approved: 40 px)

SKIN_A = (240, 184, 136)         # Alice
SKIN_B = (192, 128, 88)          # Bob
BLONDE = (240, 200, 104)
DARK_HAIR = (64, 40, 40)
BLUSH = (240, 136, 152)
SNEAKER = (240, 232, 216)
SOLE = (120, 104, 112)
LEATHER = (184, 120, 64)         # the satchel, the gloves
LEATHER_DARK = (128, 80, 48)
PHONES = (64, 64, 96)            # the headphones: dark slate
CUSHION = (200, 192, 208)
CAGE = (168, 168, 192)           # the catcher's face cage
CLEAT = (48, 40, 64)

# KEY EXCHANGE: Alice lobs the photon back over her shoulder (back arm flung up behind her)
TOSS = Pose(-6, 26, -4, -24, -12, 30, 110, -150, -170)
# v2, on A: an underhand flick back from the satchel, the back hand low behind her hip
TOSS_A = Pose(4, 26, -4, -24, -12, 40, 150, -70, -110)
# ... Bob, mitt raised to receive it
CATCH = Pose(-6, 26, -4, -24, -12, 150, 175, 30, 140)
# ... and his strong shot: a big stepping throw, the arm straight out
FIRE = Pose(14, 48, 8, -40, -26, 82, 84, -40, -70)


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


def fx_rect(surf, color, hx, f, dx, y, w, h):
    """A w x h rect `dx` px in front of hx (towards the face), mirrored for facing left."""
    x = hx + dx if f > 0 else hx - dx - w + 1
    surf.fill(color, (round(x), round(y), w, h))


def ring(surf, x, key, width=44, thin=False):
    """The game's shadow ringed in the player's colour; Bob's ring is the thinner one."""
    rect = pygame.Rect(0, 0, width + 8, 12)
    rect.center = (round(x), FLOOR_Y + 2)
    pygame.draw.ellipse(surf, SHADOW, rect)
    pygame.draw.ellipse(surf, P.INK, rect.inflate(2, 2), 3)
    pygame.draw.ellipse(surf, PLAYER_COLORS[key], rect, 1 if thin else 2)


def label(surf, text, center, color=P.WHITE):
    f = load_font(8)
    ink, core = f.render(text, False, P.INK), f.render(text, False, color)
    r = core.get_rect(center=center)
    for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1), (1, 1)):
        surf.blit(ink, r.move(dx, dy))
    surf.blit(core, r)


def glow(surf, c, r, color, alpha=90):
    """A soft round glow, added onto what is under it (light, not paint)."""
    g = pygame.Surface((2 * r + 2, 2 * r + 2))
    k0 = alpha / 255
    for k, a in ((1.0, 0.25), (0.7, 0.45), (0.42, 0.8)):
        pygame.draw.circle(g, tuple(round(v * a * k0) for v in color), (r + 1, r + 1), max(1, round(r * k)))
    surf.blit(g, g.get_rect(center=_pt(c)), special_flags=pygame.BLEND_RGB_ADD)


def other(base):
    return PURPLE if base == GREEN else GREEN


# --- the bodies --------------------------------------------------------------------------------


def sneaker(surf, foot, facing, color=SNEAKER):
    r = pygame.Rect(0, 0, 14, 7)
    r.midbottom = _pt((foot[0] + 3 * facing, foot[1] + 6))
    pygame.draw.rect(surf, P.INK, r.inflate(4, 4), border_radius=4)
    pygame.draw.rect(surf, color, r, border_radius=3)
    surf.fill(SOLE if color == SNEAKER else P.shade(color, 0.6), (r.x + 1, r.bottom - 2, r.w - 2, 2))


def cleat(surf, foot, facing):
    sneaker(surf, foot, facing, CLEAT)


def kit(base, variant):
    """The pair's shared outfit colours: (top, sleeve, thigh, shin)."""
    if variant == "A":                      # hoodie and trousers
        return base, base, P.shade(base, 0.6), P.shade(base, 0.6)
    return base, P.shade(base, 0.8), P.lighten(base, 0.45), P.shade(base, 0.55)   # jersey, pale trousers, socks


def lit_limb(surf, a, b, c, w, fill):
    """A strike's limb in the attack's colour (as render._striker): green edged in purple for a
    throw, else inked; the tip a bright ball."""
    limb(surf, a, b, w, fill)
    limb(surf, b, c, w - 1, fill)


def tip(surf, p, w, fill, active):
    p = _pt(p)
    r = w // 2 + (4 if active else 2)
    pygame.draw.circle(surf, P.INK, p, r + 2)
    pygame.draw.circle(surf, fill, p, r)
    pygame.draw.circle(surf, P.lighten(fill, 0.5), (p[0] - 2, p[1] - 2), max(2, r // 3))


def torso(surf, at, j, top, who, variant, base):
    hip, neck, sh = j["hip"], j["neck"], j["shoulder_f"]
    pts = [at(neck, 0, -8), at(sh, 0, -11), at(hip, 3, -11), at(hip, -6, -12), at(hip, -6, 12),
           at(hip, 3, 11), at(sh, 0, 11), at(neck, 0, 8)]
    poly(surf, pts, top)
    pygame.draw.line(surf, P.lighten(top, 0.4), _pt(at(sh, -2, 8)), _pt(at(hip, 0, 9)), 2)
    pygame.draw.line(surf, P.shade(top, 0.72), _pt(at(sh, 0, -9)), _pt(at(hip, 0, -9)), 2)
    if variant == "A":
        # a hoodie: the hood bunched behind the neck, a pouch pocket, white drawstrings
        _ball(surf, at(neck, -3, -8), 6, P.shade(top, 0.8))
        pygame.draw.line(surf, P.shade(top, 0.7), _pt(at(hip, 8, -2)), _pt(at(hip, 8, 11)), 1)
        for k in (4, 8):
            pygame.draw.line(surf, P.WHITE, _pt(at(neck, -1, k)), _pt(at(neck, -9, k + 1)), 1)
        pygame.draw.line(surf, P.shade(top, 0.7), _pt(at(hip, -4, -11)), _pt(at(hip, -4, 11)), 2)  # the ribbed hem
    else:
        # a baseball jersey: white piping down the button placket and round the collar, a belt
        pygame.draw.line(surf, P.WHITE, _pt(at(neck, -1, 7)), _pt(at(hip, -5, 7)), 2)
        pygame.draw.line(surf, P.WHITE, _pt(at(neck, 0, -6)), _pt(at(neck, -2, 7)), 2)
        pygame.draw.line(surf, P.INK, _pt(at(hip, -5, -11)), _pt(at(hip, -5, 11)), 4)
        surf.set_at(_pt(at(hip, -5, 6)), P.lighten(LEATHER, 0.3))
        if who == "bob":
            # the catcher's chest protector over the jersey: padded, in a deep shade
            pad = P.shade(base, 0.62)
            pts = [at(neck, -1, -2), at(neck, -1, 9), at(sh, -2, 13), at(hip, 2, 12), at(hip, 2, -1),
                   at(sh, -2, -3)]
            poly(surf, pts, pad)
            for up in (24, 16, 8):
                pygame.draw.line(surf, P.shade(pad, 0.7), _pt(at(hip, up, 0)), _pt(at(hip, up, 11)), 1)
                pygame.draw.line(surf, P.lighten(pad, 0.3), _pt(at(hip, up + 1, 1)), _pt(at(hip, up + 1, 10)), 1)
            pygame.draw.line(surf, P.shade(LEATHER, 0.9), _pt(at(sh, 0, -10)), _pt(at(sh, 4, -2)), 2)  # the harness strap


def skirt(surf, j, at, base):
    """Alice's short pleated skirt (A), hanging by gravity over the hoodie's hem."""
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
    """Alice the sender (A): a courier satchel on a strap across her chest, a letter sticking
    out of it."""
    hip, sh = j["hip"], j["shoulder_f"]
    a, b = at(sh, 2, 9), at(hip, 2, -11)
    pygame.draw.line(surf, P.INK, _pt(a), _pt(b), 5)
    pygame.draw.line(surf, LEATHER, _pt(a), _pt(b), 3)
    cx, cy = _pt(at(hip, -2, -12))
    # the letter, behind the flap: white, its own flap a V
    env = pygame.Rect(0, 0, 11, 8)
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


def mitt(surf, c, facing, lit=None):
    """Bob the catcher's mitt (B): big and round, a dark pocket facing out, laced at the edge."""
    x, y = _pt(c)
    pygame.draw.circle(surf, P.INK, (x, y), 10)
    pygame.draw.circle(surf, lit or LEATHER, (x, y), 8)
    pygame.draw.circle(surf, LEATHER_DARK if lit is None else P.shade(lit, 0.7), (x + 2 * facing, y), 4)
    pygame.draw.circle(surf, P.lighten(LEATHER, 0.45) if lit is None else P.lighten(lit, 0.5), (x - 3 * facing, y - 4), 2)
    for a in (-1.9, -1.2, 1.2, 1.9):          # lacing round the back of the rim
        surf.set_at((x - round(7 * math.cos(a)) * facing, y + round(7 * math.sin(a))), LEATHER_DARK)


def glove(surf, c, color=LEATHER):
    _ball(surf, c, 5, color)
    pygame.draw.circle(surf, LEATHER_DARK, _pt(c), 2)


def back_limbs(surf, j, kitc, who, variant, base, facing, w):
    top, sleeve, thigh, shin = kitc
    limb(surf, j["hip"], j["knee_b"], w + 1, P.shade(thigh, 0.78))
    limb(surf, j["knee_b"], j["foot_b"], w, P.shade(shin, 0.78))
    if variant == "B" and who == "bob":
        limb(surf, towards(j["knee_b"], j["foot_b"], 0.1), towards(j["knee_b"], j["foot_b"], 0.85), w + 2,
             P.shade(base, 0.5))
    (cleat if variant == "B" else sneaker)(surf, j["foot_b"], facing,
                                           *(() if variant == "B" else (P.shade(SNEAKER, 0.8),)))
    limb(surf, j["shoulder_b"], j["elbow_b"], w - 1, P.shade(top, 0.68))
    limb(surf, j["elbow_b"], j["hand_b"], w - 2, P.shade(sleeve, 0.68))
    skin = SKIN_A if who == "alice" else SKIN_B
    if variant == "B" and who == "alice":
        glove(surf, j["hand_b"], P.shade(LEATHER, 0.8))      # the pitcher's glove
    else:
        _ball(surf, j["hand_b"], 5, P.shade(skin, 0.8))


def front_leg(surf, j, kitc, who, variant, base, facing, w, strike):
    top, sleeve, thigh, shin = kitc
    if strike and strike[0] == "foot_f":
        lit_limb(surf, j["hip"], j["knee_f"], j["foot_f"], w + 1, strike[1])
    else:
        limb(surf, j["hip"], j["knee_f"], w + 1, thigh)
        limb(surf, j["knee_f"], j["foot_f"], w, shin)
        if variant == "B" and who == "bob":           # the shin guard and its knee cup
            g = P.shade(base, 0.7)
            limb(surf, towards(j["knee_f"], j["foot_f"], 0.1), towards(j["knee_f"], j["foot_f"], 0.85), w + 2, g)
            _ball(surf, j["knee_f"], 5, P.lighten(g, 0.2))
            pygame.draw.line(surf, P.lighten(g, 0.35), _pt(towards(j["knee_f"], j["foot_f"], 0.3)),
                             _pt(towards(j["knee_f"], j["foot_f"], 0.75)), 1)
    (cleat if variant == "B" else sneaker)(surf, j["foot_f"], facing)
    if strike and strike[0] == "foot_f":
        tip(surf, j["foot_f"], w, strike[1], strike[2])


def front_arm(surf, j, kitc, who, variant, base, facing, w, strike):
    top, sleeve, thigh, shin = kitc
    skin = SKIN_A if who == "alice" else SKIN_B
    hand = j["hand_f"]
    if strike and strike[0] == "hand_f":
        lit_limb(surf, j["shoulder_f"], j["elbow_f"], hand, w, strike[1])
    else:
        limb(surf, j["shoulder_f"], j["elbow_f"], w - 1, top)
        limb(surf, j["elbow_f"], hand, w - 2, sleeve)
        if variant == "A":
            _ball(surf, towards(j["elbow_f"], hand, 0.82), 5, P.shade(top, 0.75))      # the ribbed cuff
        else:
            _ball(surf, j["elbow_f"], 4, P.WHITE if False else sleeve)
            pygame.draw.circle(surf, P.WHITE, _pt(towards(j["shoulder_f"], j["elbow_f"], 0.8)), 2)  # sleeve piping
    if variant == "B" and who == "bob":
        mitt(surf, hand, facing, lit=None)
    elif strike and strike[0] == "hand_f":
        tip(surf, hand, w, strike[1], strike[2])
    else:
        _ball(surf, hand, 5, skin)


# --- the heads ------------------------------------------------------------------------------


def face(surf, hx, hy, f, skin, eyes=True):
    r = PS.HEAD_R["kid"]
    pygame.draw.circle(surf, skin, (hx + 4 * f, hy + 3), r - 4)
    if not eyes:
        return
    for dx in (5, 12):                     # two big eyes, a glint in each
        fx_rect(surf, P.INK, hx, f, dx, hy + 1, 3, 5)
        fx_rect(surf, P.WHITE, hx, f, dx + 1, hy + 1, 1, 2)
    fx_rect(surf, BLUSH, hx, f, 2, hy + 7, 3, 2)
    fx_rect(surf, BLUSH, hx, f, 14, hy + 7, 2, 2)
    fx_rect(surf, P.shade(skin, 0.55), hx, f, 9, hy + 9, 2, 1)       # the mouth


def head_shell(surf, hx, hy, color):
    r = PS.HEAD_R["kid"]
    pygame.draw.circle(surf, P.INK, (hx, hy), r + 2)
    pygame.draw.circle(surf, color, (hx, hy), r)


def cap(surf, hx, hy, f, color, brim=True):
    """A cap of the pair's colour over the top of the head, its brim forward."""
    r = PS.HEAD_R["kid"]
    crown = pygame.Rect(0, 0, 2 * r + 4, 2 * r + 2)
    crown.center = (hx, hy - 1)
    pts = [(hx - (r + 2), hy - 1), (hx + (r + 2), hy - 1)]
    pygame.draw.circle(surf, P.INK, (hx, hy - 1), r + 3, draw_top_left=True, draw_top_right=True)
    pygame.draw.circle(surf, color, (hx, hy - 1), r + 1, draw_top_left=True, draw_top_right=True)
    pygame.draw.line(surf, P.INK, pts[0], pts[1], 2)
    pygame.draw.circle(surf, P.lighten(color, 0.5), (hx - 4 * f, hy - 10), 3)          # the shine
    _ball(surf, (hx, hy - r - 1), 2, P.shade(color, 0.8))                              # the button
    if brim:
        b = pygame.Rect(0, 0, 13, 4)
        if f > 0:
            b.midleft = (hx + r - 4, hy - 1)
        else:
            b.midright = (hx - r + 4, hy - 1)
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


def head_alice(surf, j, base, f, swing, variant, part):
    hx, hy = _pt(j["head"])
    r = PS.HEAD_R["kid"]
    s = swing
    if variant == "A":
        if part == "back":
            # the back of a chin-length bob
            pygame.draw.circle(surf, P.INK, (hx - 4 * f, hy + 4), 11)
            pygame.draw.circle(surf, P.shade(BLONDE, 0.85), (hx - 4 * f, hy + 4), 9)
            return
        head_shell(surf, hx, hy, BLONDE)
        face(surf, hx, hy, f, SKIN_A)
        fringe = [(hx - 8 * f, hy - 12), (hx + 12 * f, hy - 9), (hx + 16 * f, hy - 1), (hx + 7 * f, hy - 3),
                  (hx + 3 * f, hy), (hx - 2 * f, hy - 4)]
        pygame.draw.polygon(surf, BLONDE, [_pt(p) for p in fringe])
        pygame.draw.circle(surf, P.lighten(BLONDE, 0.55), (hx - 5 * f, hy - 8), 3)          # the shine
        # the side of the bob down past the ear
        pygame.draw.line(surf, BLONDE, (hx - 1 * f, hy + 2), (hx - 3 * f, hy + 12), 5)
        bow(surf, (hx - 4 * f, hy - r - 3))
        return
    # B: a ponytail through the back of her cap
    if part == "back":
        root = (hx - 13 * f, hy - 5)
        mid = (hx - (21 + s) * f, hy - 7)
        end = (hx - (26 + s) * f, hy + 3)
        limb(surf, root, mid, 9, BLONDE)
        limb(surf, mid, end, 6, BLONDE)
        return
    head_shell(surf, hx, hy, BLONDE)
    face(surf, hx, hy, f, SKIN_A)
    pygame.draw.line(surf, BLONDE, (hx - 1 * f, hy + 1), (hx - 2 * f, hy + 9), 4)
    cap(surf, hx, hy, f, P.shade(base, 0.8))
    _ball(surf, (hx - 13 * f, hy - 3), 3, P.WHITE)           # the scrunchie
    # a little fringe under the brim
    pygame.draw.polygon(surf, BLONDE, [(hx + 3 * f, hy), (hx + 11 * f, hy), (hx + 7 * f, hy + 3)])


def head_bob(surf, j, base, f, swing, variant, part):
    hx, hy = _pt(j["head"])
    r = PS.HEAD_R["kid"]
    if part == "back":
        return
    if variant == "A":
        head_shell(surf, hx, hy, DARK_HAIR)
        face(surf, hx, hy, f, SKIN_B)
        cap(surf, hx, hy, f, P.shade(base, 0.8))
        # big headphones over the cap: the band, a cup over the ear, a little aerial on it
        band = pygame.Rect(0, 0, 2 * r + 8, 2 * r + 8)
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
        return
    # B: the catcher's helmet and face cage
    helm = P.shade(base, 0.62)
    head_shell(surf, hx, hy, helm)
    face(surf, hx, hy, f, SKIN_B)
    pygame.draw.circle(surf, P.INK, (hx, hy - 1), r + 3, draw_top_left=True, draw_top_right=True)
    pygame.draw.circle(surf, helm, (hx, hy - 1), r + 1, draw_top_left=True, draw_top_right=True)
    pygame.draw.circle(surf, P.lighten(helm, 0.45), (hx - 4 * f, hy - 10), 3)
    _ball(surf, (hx - 3 * f, hy + 3), 6, P.shade(helm, 0.85))           # the ear guard
    pygame.draw.circle(surf, P.INK, (hx - 3 * f, hy + 3), 2)
    # the cage: a frame round the face, two bars across and one down, a throat guard below
    cage = pygame.Rect(0, 0, 17, 20)
    if f > 0:
        cage.topleft = (hx + 1, hy - 6)
    else:
        cage.topright = (hx, hy - 6)
    pygame.draw.rect(surf, P.INK, cage.inflate(4, 4), 4, border_radius=6)
    pygame.draw.rect(surf, CAGE, cage, 2, border_radius=5)
    for y in (cage.y + 7, cage.y + 13):
        pygame.draw.line(surf, P.INK, (cage.x + 1, y), (cage.right - 2, y), 3)
        pygame.draw.line(surf, CAGE, (cage.x + 1, y), (cage.right - 2, y), 1)
    vx = cage.centerx + 1 * f
    pygame.draw.line(surf, P.INK, (vx, cage.y + 1), (vx, cage.bottom - 2), 3)
    pygame.draw.line(surf, CAGE, (vx, cage.y + 1), (vx, cage.bottom - 2), 1)
    pygame.draw.line(surf, P.lighten(CAGE, 0.6), (cage.x + 2, cage.y + 1), (cage.x + 6, cage.y + 1), 1)
    throat = pygame.Rect(0, 0, 7, 5)
    throat.midtop = (cage.centerx, cage.bottom)
    pygame.draw.rect(surf, P.INK, throat.inflate(2, 2), border_radius=2)
    pygame.draw.rect(surf, P.shade(CAGE, 0.75), throat, border_radius=2)


# --- ALICE and BOB ------------------------------------------------------------------------------


def draw_kid(surf, pose, feet, facing, base, who, variant, strike=None, swing=0.0):
    """One of the pair. `strike` = (joint, colour, active) lights an attack's arm or leg."""
    j = joints(pose, who, feet, facing)
    at = frame(j, facing)
    w = PS.LIMB_W["kid"]
    kitc = kit(base, variant)
    head = head_alice if who == "alice" else head_bob
    swing += max(-4.0, min(8.0, pose.lean * 0.3))
    head(surf, j, base, facing, swing, variant, "back")
    back_limbs(surf, j, kitc, who, variant, base, facing, w)
    front_leg(surf, j, kitc, who, variant, base, facing, w, strike)
    torso(surf, at, j, kitc[0], who, variant, base)
    if variant == "A" and who == "alice":
        skirt(surf, j, at, base)
        satchel(surf, at, j, facing)
    head(surf, j, base, facing, swing, variant, "front")
    front_arm(surf, j, kitc, who, variant, base, facing, w, strike)
    return j


def pair(surf, x, facing, base, variant, key, a_pose="idle", b_pose=None, a_dy=0, b_dy=0,
         a_strike=None, b_strike=None, rings=True, gap=GAP):
    """Alice at x, Bob `gap` px behind her (drawn first, behind her), both on their player's
    ring, Bob's the thinner."""
    bx = x - facing * gap
    if rings:
        ring(surf, bx, key, 38 - b_dy * 0.2, thin=True)
        ring(surf, x, key, 40 - a_dy * 0.2)
    ap = POSES[a_pose] if isinstance(a_pose, str) else a_pose
    bp = POSES[b_pose or a_pose] if isinstance(b_pose or a_pose, str) else (b_pose or a_pose)
    jb = draw_kid(surf, bp, (bx, FLOOR_Y - b_dy), facing, base, "bob", variant, b_strike,
                  swing=6 if b_dy else 0)
    ja = draw_kid(surf, ap, (x, FLOOR_Y - a_dy), facing, base, "alice", variant, a_strike,
                  swing=6 if a_dy else 0)
    return ja, jb


def trail(surf, pts, color):
    for n, p in enumerate(pts):
        r = 3 + n * 2
        pygame.draw.circle(surf, P.INK, _pt(p), r + 1)
        pygame.draw.circle(surf, P.lighten(color, 0.5), _pt(p), r)


# --- their specials --------------------------------------------------------------------------


def photon(surf, c, color, facing, big=False):
    """The game's photon (render._shot); `big` is KEY EXCHANGE's strong shot: larger, a longer
    trail, speed lines."""
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
        pygame.draw.circle(surf, P.shade(color, 0.5 + 0.12 * (3 - i)), _pt((cx + back * ((8 if big else 6) + i * (8 if big else 6)), cy)), r)
    r = 11 if big else 7
    pygame.draw.circle(surf, P.lighten(color, 0.45), _pt(c), r + 2, 1)
    pygame.draw.circle(surf, P.INK, _pt(c), r)
    pygame.draw.circle(surf, color, _pt(c), r - 1)
    pygame.draw.circle(surf, P.lighten(color, 0.6), _pt(c), r - (5 if big else 4))
    surf.fill(P.WHITE, (round(cx) - 2 - facing, round(cy) - 3, 2, 2))


def lob(surf, a, b, color, k_at=0.62, height=34):
    """KEY EXCHANGE's toss: a dotted arc from Alice's hand back to Bob's, the photon on it."""
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
    # where it will land: a ring round Bob's mitt
    rr = pygame.Rect(0, 0, 26, 26)
    rr.center = _pt(b)
    pygame.draw.arc(surf, P.INK, rr.inflate(2, 2), 0.3, 2.8, 3)
    pygame.draw.arc(surf, P.lighten(color, 0.5), rr, 0.3, 2.8, 1)


def dissolve(surf, draw, seen, t=0, shift=8, alpha=255):
    """What `draw` paints, as horizontal 2 px scanlines, `seen` (0..1) of them kept, each
    shifted sideways a little (TUNNEL's dissolve), at `alpha`."""
    tmp = pygame.Surface(surf.get_size(), pygame.SRCALPHA)
    out = draw(tmp)
    if alpha < 255:
        tmp.fill((255, 255, 255, alpha), special_flags=pygame.BLEND_RGBA_MULT)
    w, h = surf.get_size()
    for row in range(0, h, 2):
        if ((row // 2) * 7 + t) % 10 >= seen * 10:
            continue
        dx = round((1 - seen) * shift * math.sin(row * 0.7 + t * 0.9))
        surf.blit(tmp, (dx, row), (0, row, w, 2))
    return out


def flash(surf, x, color, k=1.0):
    """TELEPORT's flash: a column of light on the spot, a ring on the floor, a four-point
    star."""
    col = pygame.Surface((36, 150))
    for ww, a in ((36, 0.18), (22, 0.32), (10, 0.6)):
        r = pygame.Rect(0, 0, ww, 150)
        r.centerx = 18
        pygame.draw.rect(col, tuple(round(v * a * k) for v in P.lighten(color, 0.4)), r, border_radius=ww // 2)
    surf.blit(col, (round(x) - 18, FLOOR_Y - 140), special_flags=pygame.BLEND_RGB_ADD)
    fl = pygame.Rect(0, 0, 54, 12)
    fl.center = (round(x), FLOOR_Y + 2)
    pygame.draw.ellipse(surf, P.INK, fl.inflate(4, 4), 4)
    pygame.draw.ellipse(surf, P.lighten(color, 0.6), fl, 2)
    sx, sy = round(x), FLOOR_Y - 128
    for (dx, dy), n in (((1, 0), 9), ((0, 1), 9)):
        pygame.draw.line(surf, P.INK, (sx - dx * n, sy - dy * n), (sx + dx * n, sy + dy * n), 4)
        pygame.draw.line(surf, P.WHITE, (sx - dx * n, sy - dy * n), (sx + dx * n, sy + dy * n), 2)
    pygame.draw.circle(surf, P.WHITE, (sx, sy), 2)


def swap_arc(surf, a, b, y, color):
    """The swap's path: a dotted arc over the rival between the two flashes, arrowheads at
    both ends."""
    pts = []
    for i in range(0, 21):
        k = i / 20
        pts.append((a + (b - a) * k, y - 22 * 4 * k * (1 - k)))
    for i, p in enumerate(pts[1:-1]):
        if i % 2 == 0:
            q = _pt(p)
            surf.fill(P.INK, (q[0] - 2, q[1] - 2, 4, 4))
            surf.fill(P.lighten(color, 0.5), (q[0] - 1, q[1] - 1, 2, 2))
    for end, d in ((pts[0], 1), (pts[-1], -1)):
        x, yy = _pt(end)
        tri = [(x, yy + 1), (x + d * 3 - 3, yy - 6), (x + d * 3 + 3, yy - 6)]
        tri = [(x, yy + 2), (x - 4, yy - 5), (x + 4, yy - 5)]
        pygame.draw.polygon(surf, P.INK, tri, 0)
        pygame.draw.polygon(surf, P.INK, tri, 3)
        pygame.draw.polygon(surf, P.lighten(color, 0.5), [(x, yy), (x - 2, yy - 4), (x + 2, yy - 4)])


def streaks(surf, a, b, color, n=3):
    """Motion lines along a dive."""
    dx, dy = b[0] - a[0], b[1] - a[1]
    L = math.hypot(dx, dy) or 1
    px, py = -dy / L, dx / L
    for k, off in enumerate((-9, 0, 9)[:n]):
        s = (a[0] + px * off, a[1] + py * off)
        e = (s[0] + dx * (0.55 + 0.15 * (k == 1)), s[1] + dy * (0.55 + 0.15 * (k == 1)))
        pygame.draw.line(surf, P.INK, _pt(s), _pt(e), 4)
        pygame.draw.line(surf, P.lighten(color, 0.45), _pt(s), _pt(e), 2)


def motes(surf, c, color, t=0):
    """Decoherence: bits of him drifting up and fading."""
    import random
    rnd = random.Random(7 + t)
    for i in range(14):
        x = c[0] + rnd.uniform(-30, 30)
        y = c[1] - rnd.uniform(0, 70)
        s = rnd.choice((2, 2, 3))
        k = 1 - (c[1] - y) / 80
        col = P.lighten(color, 0.3 + 0.4 * (1 - k))
        g = pygame.Surface((s, s))
        g.fill(tuple(round(v * (0.35 + 0.5 * k)) for v in col))
        surf.blit(g, (round(x), round(y)), special_flags=pygame.BLEND_RGB_ADD)


# --- the sheet ---------------------------------------------------------------------------------


def robert(surf, x, facing=1, key="p1", pose="idle", body=GREEN):
    rect = pygame.Rect(0, 0, 60, 12)
    rect.center = (round(x), FLOOR_Y + 2)
    pygame.draw.ellipse(surf, SHADOW, rect)
    pygame.draw.ellipse(surf, P.INK, rect.inflate(2, 2), 3)
    pygame.draw.ellipse(surf, PLAYER_COLORS[key], rect, 2)
    return draw_puppet(surf, POSES[pose], "lean", (x, FLOOR_Y), facing, body, P.CREAM)


NAMES = {"A": "A: COURIERS", "B": "B: BATTERY"}


def row_look(sub, variant):
    robert(sub, 40)
    label(sub, "ROBERT", (40, 132))
    label(sub, NAMES[variant], (320, 20), P.GOLD)
    ly = 160
    # P1, green: facing right
    pair(sub, 150, 1, GREEN, variant, "p1")
    label(sub, "P1 GREEN", (135, ly))
    # P2, purple: facing left, red rings
    pair(sub, 248, -1, PURPLE, variant, "p2")
    label(sub, "P2", (263, ly))
    # mid-echo: Alice lands a heavy (B: the other colour, purple), Bob still winding it up
    lit = PURPLE
    ja, jb = None, None
    bx = 395 - GAP
    ring(sub, bx, "p1", 38, thin=True)
    ring(sub, 395, "p1", 40)
    jb = draw_kid(sub, POSES["heavy_wind"], (bx, FLOOR_Y), 1, GREEN, "bob", variant, ("hand_f", lit, False))
    pre = joints(POSES["heavy_wind"], "alice", (395, FLOOR_Y), 1)["hand_f"]
    hit = joints(POSES["heavy_hit"], "alice", (395, FLOOR_Y), 1)["hand_f"]
    trail(sub, [towards(pre, hit, 0.45), towards(pre, hit, 0.75)], lit)
    draw_kid(sub, POSES["heavy_hit"], (395, FLOOR_Y), 1, GREEN, "alice", variant, ("hand_f", lit, True))
    label(sub, "ECHO 0.2 S", (385, ly))
    # jumping: Bob leaves the floor 0.2 s after her, so he is lower on the way up
    pair(sub, 540, 1, GREEN, variant, "p1", "jump", "jump", a_dy=70, b_dy=28)
    label(sub, "JUMP", (530, 108))


def decohered(surf, feet, facing, base, variant, t=0):
    """Bob decohering: standing, see-through, the top of him already breaking into scanlines
    and motes that drift up, his outline flickering in a pale tint of their colour."""
    tmp = pygame.Surface(surf.get_size(), pygame.SRCALPHA)
    j = draw_kid(tmp, POSES["idle"], feet, facing, base, "bob", variant)
    outline = pygame.mask.from_surface(tmp).outline()
    tmp.fill((255, 255, 255, 140), special_flags=pygame.BLEND_RGBA_MULT)
    w, h = surf.get_size()
    top = round(j["head"][1]) - 22
    cut = round(j["head"][1]) + 4           # above this he is breaking up
    for row in range(0, h, 2):
        if row < top:
            continue
        if row < cut:
            k = (row - top) / max(1, cut - top)          # 0 at the top of his head, 1 at the cut
            if ((row // 2) * 7 + t) % 10 >= 6 + 3 * k:
                continue
            dx = round((1 - k) * 5 * math.sin(row * 0.9 + t))
        else:
            dx = 0
        surf.blit(tmp, (dx, row), (0, row, w, 2))
    lit = P.lighten(base, 0.6)
    for i, p in enumerate(outline):
        if p[1] < cut - 10 or (i // 5 + t) % 3 == 0:
            continue                        # the flicker: a dashed, broken edge
        surf.set_at(p, lit)
    import random
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


def dim_ring(surf, x, key, width=38):
    """Bob's ring while he is gone: still there, dimmed, so the player knows he comes back."""
    rect = pygame.Rect(0, 0, width + 8, 12)
    rect.center = (round(x), FLOOR_Y + 2)
    pygame.draw.ellipse(surf, SHADOW, rect)
    pygame.draw.ellipse(surf, P.INK, rect.inflate(2, 2), 3)
    c = P.shade(PLAYER_COLORS[key], 0.5)
    for i, a in enumerate(range(0, 360, 30)):
        if i % 2 == 0:
            pygame.draw.arc(surf, c, rect, math.radians(a), math.radians(a + 20), 1)


def row_gap(sub, variant):
    """The gap question: Bob 30 px behind Alice (agreed) or 40 px, idle and mid-echo."""
    robert(sub, 40)
    label(sub, "ROBERT", (40, 132))
    label(sub, "HOW FAR BEHIND IS BOB?", (320, 20), P.GOLD)
    for x0, gap, text in ((175, 30, "30 PX"), (470, 40, "40 PX")):
        pair(sub, x0 - 30, 1, GREEN, variant, "p1", gap=gap)
        bx = x0 + 105 - gap
        ring(sub, bx, "p1", 38, thin=True)
        ring(sub, x0 + 105, "p1", 40)
        draw_kid(sub, POSES["heavy_wind"], (bx, FLOOR_Y), 1, GREEN, "bob", variant, ("hand_f", PURPLE, False))
        pre = joints(POSES["heavy_wind"], "alice", (x0 + 105, FLOOR_Y), 1)["hand_f"]
        hit = joints(POSES["heavy_hit"], "alice", (x0 + 105, FLOOR_Y), 1)["hand_f"]
        trail(sub, [towards(pre, hit, 0.45), towards(pre, hit, 0.75)], PURPLE)
        draw_kid(sub, POSES["heavy_hit"], (x0 + 105, FLOOR_Y), 1, GREEN, "alice", variant, ("hand_f", PURPLE, True))
        label(sub, text, (x0 + 30, 150), P.GOLD)
        label(sub, "IDLE", (x0 - 45, 332))
        label(sub, "ECHO", (x0 + 90, 332))
    # a divider between the two
    for y in range(60, 340, 6):
        sub.fill(P.INK, (339, y, 3, 3))
        sub.fill(P.MIST, (340, y + 1, 1, 1))


def row_moves(sub, variant):
    label(sub, "SPECIALS (" + variant + ")", (320, 20), P.GOLD)
    base = GREEN
    ly = 332
    # KEY EXCHANGE 1: Alice tosses the photon back over her shoulder, Bob's hand up for it
    ring(sub, 40, "p1", 38, thin=True)
    ring(sub, 40 + GAP, "p1", 40)
    jb = draw_kid(sub, CATCH, (40, FLOOR_Y), 1, base, "bob", variant)
    ja = draw_kid(sub, TOSS_A, (40 + GAP, FLOOR_Y), 1, base, "alice", variant)
    lob(sub, ja["hand_b"], jb["hand_f"], base, k_at=0.55, height=40)
    label(sub, "1 TOSS", (55, 322))
    # KEY EXCHANGE 2: Bob fires it forward, one strong shot past her
    ring(sub, 142, "p1", 38, thin=True)
    ring(sub, 142 + GAP, "p1", 40)
    draw_kid(sub, POSES["idle"], (142 + GAP, FLOOR_Y), 1, base, "alice", variant)
    jb = draw_kid(sub, FIRE, (142, FLOOR_Y), 1, base, "bob", variant, ("hand_f", base, True))
    photon(sub, (222, jb["hand_f"][1] - 1), base, 1, big=True)
    label(sub, "2 SHOT", (172, 322))
    label(sub, "KEY EXCHANGE", (122, 342), P.GOLD)
    # TELEPORT: a rival walked between them; they swap, Alice now behind the rival
    ax, rx, bx = 276, 338, 400
    robert(sub, rx, -1, "p2", "idle", PURPLE)
    flash(sub, ax, base)
    flash(sub, bx, base)
    ring(sub, ax, "p1", 40)
    ring(sub, bx, "p1", 38, thin=True)
    dissolve(sub, lambda s: draw_kid(s, POSES["idle"], (ax, FLOOR_Y), 1, base, "alice", variant), 0.88, t=3)
    dissolve(sub, lambda s: draw_kid(s, POSES["idle"], (bx, FLOOR_Y), -1, base, "bob", variant), 0.88, t=6)
    swap_arc(sub, ax, bx, FLOOR_Y - 150, base)
    label(sub, "TELEPORT", (338, ly), P.GOLD)
    # BELL DIVE: both dives on one line, Bob 0.2 s behind and higher
    path_a, path_b = (484, FLOOR_Y - 34), (444, FLOOR_Y - 108)
    ring(sub, path_b[0] + 8, "p1", 24, thin=True)
    ring(sub, path_a[0] + 12, "p1", 32)
    jb = joints(POSES["dive"], "bob", path_b, 1)
    streaks(sub, (path_b[0] - 34, path_b[1] - 56), jb["hip"], base)
    draw_kid(sub, POSES["dive"], path_b, 1, base, "bob", variant, ("foot_f", base, False), swing=6)
    ja = joints(POSES["dive"], "alice", path_a, 1)
    streaks(sub, (path_a[0] - 34, path_a[1] - 56), ja["hip"], base)
    draw_kid(sub, POSES["dive"], path_a, 1, base, "alice", variant, ("foot_f", base, True), swing=6)
    label(sub, "BELL DIVE", (466, ly), P.GOLD)
    # Bob decohered: standing see-through and breaking up, Alice fights on alone
    dim_ring(sub, 588, "p1")
    ring(sub, 618, "p1", 40)
    decohered(sub, (588, FLOOR_Y), 1, base, variant, t=1)
    draw_kid(sub, POSES["idle"], (618, FLOOR_Y), 1, base, "alice", variant)
    label(sub, "DECOHERED", (590, ly), P.GOLD)


MOVES_VARIANT = "A"


def main(out: str) -> None:
    pygame.init()
    stage, _ = make_stage("lab")
    rows = (lambda s: row_look(s, "A"), lambda s: row_gap(s, "A"), lambda s: row_moves(s, MOVES_VARIANT))
    sheet = pygame.Surface((640, 360 * len(rows)))
    for i, draw in enumerate(rows):
        sub = sheet.subsurface((0, i * 360, 640, 360))
        sub.blit(stage, (-8, -8))
        draw(sub)
    pygame.image.save(pygame.transform.scale(sheet, (1280, 720 * len(rows))), out)
    pygame.image.save(sheet, out.replace(".png", "_1x.png"))


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "alicebob_sheet_v2.png")
