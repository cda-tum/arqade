"""M-CUTIE's look (2026-10-21): the android in a "chandelier" dress. The user approved variant B
(the cage skirt, with B's own glass face), the reference for porting her into the game; A is kept
for the record.

A prototype, not game code, in the manner of PHOEBE's, ERWIN's and DOS's look scripts: it
draws on Brawl-Ket's own skeleton (poses.joints, POSES) and ink helpers (limb, _ball, _pt,
make_stage), at the game's 640x360 scale, on the SUPERCONDUCTOR stage. Run it from brawl-ket/:

    uv run python ../docs/superpowers/specs/2026-10-21-brawl-ket-m-cutie-look.py OUT.png

- A, TIERED: a short dress whose skirt is three gold plates of the stage's dilution
  refrigerator, stacked and widening downwards, with her colour glowing between them and the
  fridge's rods and coax lines crossing the glow. Coax-cable pigtails ending in gold SMA
  plugs, an ion-trap hair clip at each root, a porcelain doll face with LED eyes.
- B, CAGE: the chandelier as an open hoop skirt: three gold hoops on gold rods, the glow
  inside it and her legs seen through it. Coiled-coax buns with a plug hanging from each, an
  ion clip in each bun, and a dark glass face with soft LED eyes.

Row 3 shows her three specials (on B, MOVES_VARIANT): AMPLITUDE AMPLIFICATION charging and its wave (a
microwave drive pulse: a Gaussian envelope with the carrier inside it), the ION TRAP arming and
armed, and SPIN.
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

# M-CUTIE's build: PHOEBE's long-limbed toy, a slightly shorter torso and thinner limbs
PS.SCALE["cutie"] = 2.1
PS.BUILD_BONES["cutie"] = {"torso": 22, "shoulder": 19, "thigh": 17, "shin": 17, "upper_arm": 12, "forearm": 12, "neck": 7}
PS.HEAD_R["cutie"] = 15
PS.LIMB_W["cutie"] = 12

# the stage's own chandelier colours (stages.py)
GOLD_PLATE = (232, 184, 72)
COAX = (176, 192, 216)
PORCELAIN = (240, 232, 232)
JOINT = (216, 208, 224)        # the pale ball joints at elbows and knees: a doll's joints
BLUSH = (240, 136, 168)
SHOE = (40, 32, 56)
GLASS = (24, 24, 56)

# SPIN: in the air, the front leg straight out, arms flung wide
SPIN = Pose(-4, 92, 92, 24, -60, 60, 150, 30, 150)
# AMPLITUDE AMPLIFICATION charging: hands cupped together in front of the chest
CHARGE = Pose(2, 26, -4, -24, -12, 62, 150, 52, 158)


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


def glow(surf, c, r, color, alpha=90):
    """A soft round glow, added onto what is under it (light, not paint): three discs, the
    brightest in the middle. `alpha` (0..255) is how strong."""
    g = pygame.Surface((2 * r + 2, 2 * r + 2))
    k0 = alpha / 255
    for k, a in ((1.0, 0.25), (0.7, 0.45), (0.42, 0.8)):
        pygame.draw.circle(g, tuple(round(v * a * k0) for v in color), (r + 1, r + 1), max(1, round(r * k)))
    surf.blit(g, g.get_rect(center=_pt(c)), special_flags=pygame.BLEND_RGB_ADD)


def cable(surf, pts, w, color, plug=True):
    """A coax cable through pts: a capsule chain with a darker braid band every 4 px, and a
    gold SMA plug (the ferrule and its hex nut) on the last point."""
    for a, b in zip(pts, pts[1:]):
        limb(surf, a, b, w, color)
    for a, b in zip(pts, pts[1:]):
        pygame.draw.line(surf, color, _pt(a), _pt(b), w)
    band = P.shade(color, 0.72)
    for a, b in zip(pts, pts[1:]):
        dx, dy = b[0] - a[0], b[1] - a[1]
        n = math.hypot(dx, dy) or 1.0
        px, py = -dy / n, dx / n
        for k in range(1, int(n // 5) + 1):
            c = (a[0] + dx * k * 5 / n, a[1] + dy * k * 5 / n)
            pygame.draw.line(surf, band, _pt((c[0] - px * (w / 2 - 0.5), c[1] - py * (w / 2 - 0.5))),
                             _pt((c[0] + px * (w / 2 - 0.5), c[1] + py * (w / 2 - 0.5))), 1)
    if plug:
        a, b = pts[-2], pts[-1]
        dx, dy = b[0] - a[0], b[1] - a[1]
        n = math.hypot(dx, dy) or 1.0
        ux, uy = dx / n, dy / n
        nut = (b[0] + ux * 2, b[1] + uy * 2)
        tip = (b[0] + ux * 7, b[1] + uy * 7)
        limb(surf, nut, tip, 2, P.lighten(GOLD_PLATE, 0.3))
        _ball(surf, nut, 3, GOLD_PLATE)
        surf.set_at(_pt((nut[0] - 1, nut[1] - 1)), P.lighten(GOLD_PLATE, 0.6))


def ion_clip(surf, c, color, lit=True):
    """A hair clip that is a tiny ion trap: two gold electrode prongs and the glowing ion
    held between them."""
    x, y = _pt(c)
    for side in (-1, 1):
        r = pygame.Rect(0, 0, 3, 6)
        r.center = (x + side * 4, y)
        pygame.draw.rect(surf, P.INK, r.inflate(2, 2), border_radius=1)
        pygame.draw.rect(surf, GOLD_PLATE, r)
    if lit:
        glow(surf, (x, y), 7, P.lighten(color, 0.5), 110)
    pygame.draw.circle(surf, P.INK, (x, y), 3)
    pygame.draw.circle(surf, P.lighten(color, 0.55 if lit else 0.1), (x, y), 2)
    surf.set_at((x, y - 1), P.WHITE)


def shoe(surf, foot, facing, color=SHOE):
    r = pygame.Rect(0, 0, 14, 7)
    r.midbottom = _pt((foot[0] + 3 * facing, foot[1] + 6))
    pygame.draw.rect(surf, P.INK, r.inflate(4, 4), border_radius=4)
    pygame.draw.rect(surf, color, r, border_radius=3)
    surf.fill(GOLD_PLATE, (r.x + 2, r.y, r.w - 4, 1))          # a gold strap
    surf.fill(P.lighten(color, 0.3), (r.x + (r.w - 5 if facing > 0 else 2), r.y + 2, 3, 1))


# --- the body ------------------------------------------------------------------------------------


def limbs_back(surf, j, base, facing, w):
    dark = P.shade(base, 0.62)
    limb(surf, j["hip"], j["knee_b"], w + 1, dark)
    limb(surf, j["knee_b"], j["foot_b"], w, dark)
    _ball(surf, j["knee_b"], 3, P.shade(JOINT, 0.7))
    shoe(surf, j["foot_b"], facing, P.shade(SHOE, 0.8))
    limb(surf, j["shoulder_b"], j["elbow_b"], w - 1, dark)
    limb(surf, j["elbow_b"], j["hand_b"], w - 2, dark)
    _ball(surf, j["elbow_b"], 3, P.shade(JOINT, 0.7))
    _ball(surf, j["hand_b"], 5, P.shade(PORCELAIN, 0.72))


def leg_front(surf, j, base, facing, w, strike):
    leg = strike[1] if strike and strike[0] == "foot_f" else P.shade(base, 0.85)
    limb(surf, j["hip"], j["knee_f"], w + 1, leg)
    limb(surf, j["knee_f"], j["foot_f"], w, leg)
    _ball(surf, j["knee_f"], 3, JOINT)
    shoe(surf, j["foot_f"], facing)


def arm_front(surf, j, base, w, strike):
    arm = strike[1] if strike and strike[0] == "hand_f" else base
    limb(surf, j["shoulder_f"], j["elbow_f"], w - 1, arm)
    limb(surf, j["elbow_f"], j["hand_f"], w - 2, arm)
    _ball(surf, j["elbow_f"], 3, JOINT)
    _ball(surf, towards(j["elbow_f"], j["hand_f"], 0.8), 5, GOLD_PLATE)     # a gold cuff
    _ball(surf, j["hand_f"], 5, PORCELAIN if arm is base else P.lighten(arm, 0.55))
    # the puffed sleeve, over the shoulder joint, trimmed in gold
    sh = j["shoulder_f"]
    _ball(surf, sh, 7, arm)
    pygame.draw.circle(surf, P.lighten(arm, 0.4), _pt((sh[0] - 2, sh[1] - 3)), 2)


def bodice(surf, at, j, base):
    """The dress's top: a fitted bodice, a gold collar (the fridge's top plate) at the neck,
    an android's panel seam down the front."""
    hip, neck, sh = j["hip"], j["neck"], j["shoulder_f"]
    pts = [at(neck, 2, -7), at(sh, 2, -11), at(sh, -6, -12), at(hip, 16, -8), at(hip, 9, -10),
           at(hip, 9, 10), at(hip, 16, 8), at(sh, -6, 13), at(sh, 2, 12), at(neck, 2, 8)]
    poly(surf, pts, base)
    pygame.draw.line(surf, P.lighten(base, 0.4), _pt(at(sh, -2, 9)), _pt(at(hip, 16, 7)), 2)
    pygame.draw.line(surf, P.shade(base, 0.7), _pt(at(sh, 0, -9)), _pt(at(hip, 15, -7)), 2)
    pygame.draw.line(surf, P.shade(base, 0.78), _pt(at(sh, -4, 2)), _pt(at(hip, 14, 2)), 1)
    poly(surf, [at(neck, 4, -8), at(neck, 4, 9), at(neck, -1, 10), at(neck, -1, -9)], GOLD_PLATE)
    pygame.draw.line(surf, P.lighten(GOLD_PLATE, 0.5), _pt(at(neck, 2.5, -6)), _pt(at(neck, 2.5, 7)), 1)


def waist(j, at):
    """Where the skirt hangs from, and the x its hem centres on: the skirt hangs by gravity,
    pulled a little towards the knees so a crouch or a jump sits over the thighs."""
    wx, wy = at(j["hip"], 12, 0)
    knees = (j["knee_f"][0] + j["knee_b"][0]) / 2
    return (wx, wy), 0.3 * (knees - j["hip"][0])


def hplate(surf, cx, y, half, thick=5):
    """One of the chandelier's gold plates, edge on: highlight on top, shadow under."""
    r = pygame.Rect(0, 0, round(2 * half), thick)
    r.midtop = (round(cx), round(y))
    pygame.draw.rect(surf, P.INK, r.inflate(4, 4), border_radius=4)
    pygame.draw.rect(surf, GOLD_PLATE, r, border_radius=3)
    surf.fill(P.lighten(GOLD_PLATE, 0.5), (r.x + 3, r.y + 1, r.w - 6, 1))
    surf.fill(P.shade(GOLD_PLATE, 0.7), (r.x + 2, r.bottom - 2, r.w - 4, 1))


def skirt_tiers(surf, j, at, base, bright=0.0, spread=1.0, squash=1.0):
    """Variant A's skirt: three gold plates widening downwards, her colour glowing between
    them, crossed by the fridge's rods (at the edges) and its coax lines (kinked at each
    stage)."""
    (wx, wy), shift = waist(j, at)
    tiers = [(0, 12), (15, 20), (30, 28)]
    tiers = [(wy + u * squash, wx + shift * u / 30, h * spread) for u, h in tiers]
    lit = P.lighten(base, 0.12 + 0.3 * bright)
    core = P.lighten(base, 0.5 + 0.35 * bright)
    for (y0, x0, h0), (y1, x1, h1) in zip(tiers, tiers[1:]):
        # each tier bells out a little under its plate, like a ruffle
        band = [(x0 - h0 + 1, y0 + 5), (x0 + h0 - 1, y0 + 5), (x1 + h1 - 1, y1 - 3), (x1 + h1 - 3, y1 + 1),
                (x1 - h1 + 3, y1 + 1), (x1 - h1 + 1, y1 - 3)]
        poly(surf, band, lit)
        pygame.draw.line(surf, core, _pt((x0 - h0 + 3, y0 + 8)), _pt((x0 + h0 - 3, y0 + 8)), 3)
        for side in (-1, 1):                     # the rods, plate edge to plate edge
            a, b = (x0 + side * (h0 - 3), y0 + 5), (x1 + side * (h1 - 5), y1)
            pygame.draw.line(surf, P.INK, _pt(a), _pt(b), 4)
            pygame.draw.line(surf, P.shade(GOLD_PLATE, 0.85), _pt(a), _pt(b), 2)
        for k in (-0.45, 0, 0.45):               # the coax lines, kinked half way
            a = (x0 + k * h0, y0 + 5)
            m = ((x0 + x1) / 2 + k * (h0 + h1) / 2 + (2 if k else -2), (y0 + 5 + y1) / 2)
            c = (x1 + k * h1, y1)
            pygame.draw.lines(surf, P.INK, False, [_pt(a), _pt(m), _pt(c)], 3)
            pygame.draw.lines(surf, P.shade(COAX, 0.85) if k else P.shade(COAX, 0.7), False, [_pt(a), _pt(m), _pt(c)], 1)
    if bright:
        glow(surf, ((tiers[0][1] + tiers[-1][1]) / 2, (tiers[0][0] + tiers[-1][0]) / 2 + 4), 26, base, 120 * bright)
    for y, x, h in tiers:
        hplate(surf, x, y, h)


def cage_hoops(j, at, spread=1.0, squash=1.0):
    (wx, wy), shift = waist(j, at)
    return [(wx + shift * u / 26, wy + u * squash, w * spread, hh)
            for u, w, hh in ((0, 26, 6), (13, 44, 9), (26, 60, 12))]


def skirt_cage_back(surf, j, at, base, bright=0.0, spread=1.0, squash=1.0):
    """Variant B's hoop skirt, behind the legs: the glow filling the bell, the far halves of the
    hoops."""
    hoops = cage_hoops(j, at, spread, squash)
    lit = P.lighten(base, 0.28 + 0.3 * bright)
    bell = ([(x - w / 2, y) for x, y, w, h in hoops] + [(x + w / 2, y) for x, y, w, h in reversed(hoops)])
    x, y, w, h = hoops[-1]
    under = pygame.Rect(0, 0, round(w), h)
    under.center = _pt((x, y))
    pygame.draw.polygon(surf, P.INK, [_pt(p) for p in bell], 5)
    pygame.draw.ellipse(surf, P.INK, under.inflate(4, 4))
    pygame.draw.polygon(surf, lit, [_pt(p) for p in bell])
    pygame.draw.ellipse(surf, lit, under)
    # the mixing chamber's light inside it: brighter down the middle
    x0, y0 = hoops[0][0], hoops[0][1]
    core = [(x0 - 6, y0), (x0 + 6, y0), (x + 14, y), (x - 14, y)]
    pygame.draw.polygon(surf, P.lighten(base, 0.5 + 0.3 * bright), [_pt(p) for p in core])
    for x, y, w, h in hoops:
        r = pygame.Rect(0, 0, round(w), h)
        r.center = _pt((x, y))
        pygame.draw.arc(surf, P.INK, r.inflate(2, 2), 0, math.pi, 4)
        pygame.draw.arc(surf, P.shade(GOLD_PLATE, 0.7), r, 0, math.pi, 2)


def skirt_cage_front(surf, j, at, base, facing, sway=0.0, spread=1.0, squash=1.0):
    """...and in front of the legs: the rods and coax lines between the hoops, the near halves
    of the hoops, and a coax fringe with gold plugs hanging from the hem."""
    hoops = cage_hoops(j, at, spread, squash)

    def rim(hp, k):
        x, y, w, h = hp
        return (x + k * (w / 2 - 1), y + h / 2 * math.sqrt(max(0.0, 1 - k * k)))
    for h0, h1 in zip(hoops, hoops[1:]):
        for k in (-1, -0.3, 0.4, 1):
            a, b = rim(h0, k), rim(h1, k)
            if abs(k) == 1:
                pygame.draw.line(surf, P.INK, _pt(a), _pt(b), 4)
                pygame.draw.line(surf, P.shade(GOLD_PLATE, 0.85), _pt(a), _pt(b), 2)
            else:
                m = towards(a, b, 0.5)
                m = (m[0] + 2, m[1])
                pygame.draw.lines(surf, P.INK, False, [_pt(a), _pt(m), _pt(b)], 3)
                pygame.draw.lines(surf, COAX, False, [_pt(a), _pt(m), _pt(b)], 1)
    for k in (-0.75, -0.25, 0.25, 0.75):         # the fringe: short coax tails with plugs
        x0, y0 = rim(hoops[-1], k)
        x1 = x0 - facing * sway
        pygame.draw.line(surf, P.INK, _pt((x0, y0)), _pt((x1, y0 + 7)), 4)
        pygame.draw.line(surf, COAX, _pt((x0, y0)), _pt((x1, y0 + 7)), 2)
        pygame.draw.circle(surf, P.INK, _pt((x1, y0 + 8)), 2)
        surf.set_at(_pt((x1, y0 + 8)), GOLD_PLATE)
    for x, y, w, h in hoops:
        r = pygame.Rect(0, 0, round(w), h)
        r.center = _pt((x, y))
        pygame.draw.arc(surf, P.INK, r.inflate(4, 4), math.pi, 2 * math.pi, 5)
        pygame.draw.arc(surf, GOLD_PLATE, r.inflate(1, 1), math.pi, 2 * math.pi, 3)
        surf.fill(P.lighten(GOLD_PLATE, 0.55), (r.centerx - r.w // 6, r.bottom - 1, r.w // 3, 1))


# --- the heads ----------------------------------------------------------------------------------


def led_eyes(surf, hx, hy, f, base, on_glass=False):
    for ex, ew in ((hx + 12 * f, 4), (hx + 3 * f, 5)):
        e = pygame.Rect(0, 0, ew, 8)
        e.center = (ex, hy + 3)
        if not on_glass:
            pygame.draw.rect(surf, P.INK, e.inflate(2, 0), border_radius=2)
        if on_glass:
            lit = pygame.Rect(e.x + 1, e.y + 1, ew - 1 if ew > 4 else ew - 1, 6)
            glow(surf, lit.center, 5, base, 140)
        else:
            lit = pygame.Rect(e.x + (1 if ew > 4 else 0), e.y + 3, ew - (2 if ew > 4 else 1), 4)
        surf.fill(P.lighten(base, 0.5), lit)
        surf.fill(P.lighten(base, 0.8), (lit.x, lit.bottom - 1, lit.w, 1))
        surf.fill(P.WHITE, (e.x + (1 if f > 0 else e.w - 2), e.y + 1, 1, 2))


def head_a(surf, j, base, facing, swing, part):
    """A: a porcelain doll face under a shell of her colour with a cut fringe, LED eyes, coax
    twin tails plugged in at the back of the head, an ion-trap clip at each root."""
    hx, hy = _pt(j["head"])
    r = PS.HEAD_R["cutie"]
    f = facing
    s = swing
    if part == "back":
        far = [(hx - 9 * f, hy - 12), (hx - 20 * f, hy - 10), (hx - (27 + s) * f, hy + 1),
               (hx - (28 + s) * f, hy + 14), (hx - (24 + s) * f, hy + 23)]
        near = [(hx - 9 * f, hy - 5), (hx - 18 * f, hy - 1), (hx - (21 + s) * f, hy + 11),
                (hx - (20 + s) * f, hy + 23), (hx - (15 + s) * f, hy + 31)]
        cable(surf, far, 6, P.shade(COAX, 0.68))
        cable(surf, near, 6, COAX)
        return
    pygame.draw.circle(surf, P.INK, (hx, hy), r + 2)
    pygame.draw.circle(surf, base, (hx, hy), r)
    pygame.draw.circle(surf, PORCELAIN, (hx + 4 * f, hy + 3), r - 4)
    fringe = [(hx - 9 * f, hy - 12), (hx + 12 * f, hy - 9), (hx + 15 * f, hy - 2),
              (hx + 3 * f, hy - 2), (hx, hy + 2), (hx - 5 * f, hy - 2)]
    pygame.draw.polygon(surf, base, [_pt(p) for p in fringe])
    pygame.draw.circle(surf, P.lighten(base, 0.5), (hx - 4 * f, hy - 8), 3)          # the shine
    led_eyes(surf, hx, hy, f, base)
    surf.fill(BLUSH, (hx + 6 * f - (2 if f < 0 else 0) - 3 * f, hy + 9, 3, 1))
    surf.fill(BLUSH, (hx + 14 * f - (2 if f < 0 else 0), hy + 9, 2, 1))
    surf.fill(P.shade(PORCELAIN, 0.5), (hx + 9 * f - (1 if f < 0 else 0), hy + 11, 2, 1))     # the mouth
    # the seam where the face plate meets the shell, down the cheek: the one android tell
    pygame.draw.line(surf, P.shade(PORCELAIN, 0.7), (hx - 1 * f, hy + 4), (hx + 1 * f, hy + 10), 1)
    ion_clip(surf, (hx - 10 * f, hy - 7), base)


def head_b(surf, j, base, facing, swing, part):
    """B: a shell of her colour with a dark glass face and soft LED eyes, two buns of coiled
    coax with an ion in each, a plug hanging from each bun."""
    hx, hy = _pt(j["head"])
    r = PS.HEAD_R["cutie"]
    f = facing
    s = swing
    buns = ((hx - 12 * f, hy - 11), (hx + 1 * f, hy - 16))
    if part == "back":
        bx, by = buns[0]
        cable(surf, [(bx - 3 * f, by + 4), (bx - (10 + s) * f, by + 13), (bx - (10 + s) * f, by + 24),
                     (bx - (6 + s) * f, by + 31)], 5, COAX)
        bx, by = buns[1]
        cable(surf, [(bx - 3 * f, by), (bx - (20 + s) * f, by + 4), (bx - (25 + s) * f, by + 14),
                     (bx - (23 + s) * f, by + 24)], 5, P.shade(COAX, 0.68))
        return
    for k, (bx, by) in enumerate(buns):          # the far bun first, under the head
        rr = 8 if k == 0 else 7
        pygame.draw.circle(surf, P.INK, (bx, by), rr + 2)
        pygame.draw.circle(surf, COAX if k == 0 else P.shade(COAX, 0.85), (bx, by), rr)
        pygame.draw.circle(surf, P.shade(COAX, 0.6), (bx, by), rr - 2, 1)       # the coil's turns
        pygame.draw.circle(surf, P.shade(COAX, 0.6), (bx, by), rr - 4, 1)
        if k == 0:
            pygame.draw.circle(surf, P.INK, (hx, hy), r + 2)
            pygame.draw.circle(surf, base, (hx, hy), r)
    pygame.draw.circle(surf, P.INK, (hx, hy), r + 2)
    pygame.draw.circle(surf, base, (hx, hy), r)
    pygame.draw.circle(surf, P.lighten(base, 0.5), (hx - 5 * f, hy - 7), 3)
    face = pygame.Rect(0, 0, 20, 16)
    face.center = (hx + 5 * f, hy + 3)
    pygame.draw.ellipse(surf, P.INK, face.inflate(4, 4))
    pygame.draw.ellipse(surf, GLASS, face)
    pygame.draw.arc(surf, P.lighten(GLASS, 0.45), face.inflate(-4, -4), 1.7, 2.7, 1)
    led_eyes(surf, hx + f, hy, f, base, on_glass=True)
    for ex, ey in ((hx + 13 * f, hy + 9), (hx + 1 * f, hy + 9)):
        glow(surf, (ex, ey), 3, BLUSH, 200)
    for bx, by in buns:
        ion_clip(surf, (bx, by), base)


# --- M-CUTIE ------------------------------------------------------------------------------------


def draw_cutie(surf, pose, feet, facing, base=GREEN, variant="A", strike=None, bright=0.0,
               swing=0.0, spread=1.0, squash=1.0):
    """`strike` = (joint, colour) lights an attack's arm or leg; `bright` (0..1) is the charge's
    glow in the skirt; `swing` blows the hair back; `spread`/`squash` flare the skirt (SPIN)."""
    j = joints(pose, "cutie", feet, facing)
    at = frame(j, facing)
    w = PS.LIMB_W["cutie"]
    head = head_a if variant == "A" else head_b
    swing += max(-4.0, min(8.0, pose.lean * 0.3))
    head(surf, j, base, facing, swing, "back")
    limbs_back(surf, j, base, facing, w)
    if variant == "B":
        skirt_cage_back(surf, j, at, base, bright, spread, squash)
    leg_front(surf, j, base, facing, w, strike)
    bodice(surf, at, j, base)
    if variant == "A":
        skirt_tiers(surf, j, at, base, bright, spread, squash)
    else:
        skirt_cage_front(surf, j, at, base, facing, 2 + swing * 0.3, spread, squash)
    head(surf, j, base, facing, swing, "front")
    arm_front(surf, j, base, w, strike)
    return j


# --- her specials ----------------------------------------------------------------------------


def drive_pulse(surf, x, h, color, facing):
    """AMPLITUDE AMPLIFICATION's wave: a microwave drive pulse running along the floor, a
    Gaussian envelope with the carrier oscillating inside it. Taller with every step."""
    half = 12 + h * 0.42
    sig = half / 2.1
    xs = [x + k for k in range(-round(half), round(half) + 1)]
    env = [h * math.exp(-((xx - x) / sig) ** 2) for xx in xs]
    floor = FLOOR_Y - 1
    # a pool of light on the floor, and speed lines behind
    pool = pygame.Surface((round(2 * half + 16), 10))
    for k, a in ((1.0, 0.18), (0.6, 0.35)):
        rr = pygame.Rect(0, 0, round(pool.get_width() * k), round(10 * k))
        rr.center = (pool.get_width() // 2, 5)
        pygame.draw.ellipse(pool, tuple(round(v * a) for v in color), rr)
    surf.blit(pool, pool.get_rect(center=(round(x), floor + 1)), special_flags=pygame.BLEND_RGB_ADD)
    for dy, ln in ((-0.25, 16), (-0.55, 10)):
        y = floor + dy * h
        x0 = x - facing * (half * 0.9)
        pygame.draw.line(surf, P.lighten(color, 0.45), _pt((x0, y)), _pt((x0 - facing * ln, y)), 2)
    outline = [(xx, floor - e) for xx, e in zip(xs, env)] + [(xs[-1], floor), (xs[0], floor)]
    pygame.draw.polygon(surf, P.INK, [_pt(p) for p in outline], 5)
    pygame.draw.polygon(surf, P.shade(color, 0.8), [_pt(p) for p in outline])
    inner = [(xx, floor - e * 0.82) for xx, e in zip(xs, env)] + [(xs[-1], floor), (xs[0], floor)]
    pygame.draw.polygon(surf, color, [_pt(p) for p in inner])
    # the carrier: a bright line swinging between the floor and the envelope
    k = 2 * math.pi / max(7.0, half * 0.55)
    carrier = [(xx, floor - e * 0.82 * (0.5 + 0.5 * math.cos(k * (xx - x)))) for xx, e in zip(xs, env)]
    pygame.draw.lines(surf, P.lighten(color, 0.75), False, [_pt(p) for p in carrier], 2)
    top = [(xx, floor - e) for xx, e in zip(xs, env) if e > 3]
    if len(top) > 1:
        pygame.draw.lines(surf, P.lighten(color, 0.55), False, [_pt(p) for p in top], 1)


def pips(surf, c, n, color):
    """The charge's steps above her head: one lit diamond per step."""
    x0 = c[0] - (n - 1) * 5
    for i in range(n):
        x, y = round(x0 + i * 10), round(c[1])
        d = [(x, y - 4), (x + 4, y), (x, y + 4), (x - 4, y)]
        pygame.draw.polygon(surf, P.INK, [(px, py) for px, py in ((x, y - 6), (x + 6, y), (x, y + 6), (x - 6, y))])
        pygame.draw.polygon(surf, P.lighten(color, 0.45), d)
        surf.set_at((x - 1, y - 1), P.WHITE)


def ion_trap(surf, x, color, armed):
    """ION TRAP on the floor: two gold electrodes on a dark chip, the ion floating between.
    Dim while it arms; lit (the ion bright, the electrode tips glowing, the field round the
    ion) once armed."""
    floor = FLOOR_Y
    base = pygame.Rect(0, 0, 46, 6)
    base.midbottom = (x, floor + 1)
    pygame.draw.rect(surf, P.INK, base.inflate(4, 4), border_radius=2)
    pygame.draw.rect(surf, P.shade(COAX, 0.45), base, border_radius=1)
    surf.fill(P.shade(COAX, 0.65), (base.x + 2, base.y, base.w - 4, 1))
    gold = GOLD_PLATE if armed else P.shade(GOLD_PLATE, 0.6)
    ion = (x, floor - 17)
    if armed:
        glow(surf, ion, 20, color, 200)
        for side in (-1, 1):                         # the trapping field, curving round the ion
            r = pygame.Rect(0, 0, 18, 18)
            r.center = ion
            a0 = -0.9 if side > 0 else math.pi - 0.9
            pygame.draw.arc(surf, P.lighten(color, 0.5), r, a0, a0 + 1.8, 1)
    for side in (-1, 1):
        e = pygame.Rect(0, 0, 6, 26)
        e.midbottom = (x + side * 15, base.top)
        pygame.draw.rect(surf, P.INK, e.inflate(4, 4), border_radius=3)
        pygame.draw.rect(surf, gold, e, border_radius=2)
        surf.fill(P.lighten(gold, 0.45), (e.x + 1, e.y + 2, 1, e.h - 4))
        tip = pygame.Rect(e.x, e.y, 6, 5)
        pygame.draw.rect(surf, P.lighten(color, 0.3) if armed else P.shade(color, 0.45), tip, border_radius=2)
    pygame.draw.circle(surf, P.INK, _pt(ion), 6)
    pygame.draw.circle(surf, P.lighten(color, 0.6) if armed else P.shade(color, 0.5), _pt(ion), 4)
    if armed:
        surf.set_at((ion[0] - 1, ion[1] - 1), P.WHITE)


def spin_whirl(surf, j, color, part):
    """SPIN's motion: rings of light whirling round her skirt, the far half behind her
    (`part` "back"), the near half in front ("front"), with a bright head on each ring."""
    hx, hy = j["hip"]
    lit = P.lighten(color, 0.5)
    for rw, rh, dy in ((92, 18, -2), (74, 14, 14)):
        r = pygame.Rect(0, 0, rw, rh)
        r.center = (round(hx), round(hy + dy))
        if part == "back":
            pygame.draw.arc(surf, P.shade(color, 0.7), r, math.pi * 0.15, math.pi * 0.85, 2)
        else:
            pygame.draw.arc(surf, P.INK, r.inflate(2, 2), math.pi * 1.05, math.pi * 1.85, 4)
            pygame.draw.arc(surf, lit, r, math.pi * 1.05, math.pi * 1.85, 2)
            tip = (r.centerx + round(rw / 2 * math.cos(math.pi * 1.85)), r.centery - round(rh / 2 * math.sin(math.pi * 1.85)))
            pygame.draw.circle(surf, P.INK, tip, 3)
            pygame.draw.circle(surf, P.lighten(color, 0.75), tip, 2)


def aura(surf, draw, color, k=1.0):
    """The charge's glow: whatever `draw` paints, ringed by a soft halo of her colour."""
    tmp = pygame.Surface(surf.get_size(), pygame.SRCALPHA)
    j = draw(tmp)
    sil = pygame.mask.from_surface(tmp).to_surface(setcolor=(*P.lighten(color, 0.5), round(70 * k)),
                                                    unsetcolor=(0, 0, 0, 0))
    for r in (4, 2):
        for dx, dy in ((-r, 0), (r, 0), (0, -r), (0, r), (-r, -r), (r, -r), (-r, r), (r, r)):
            surf.blit(sil, (dx, dy))
    surf.blit(tmp, (0, 0))
    return j


def leg_ghosts(surf, pose, feet, facing, base):
    for k, a in ((2, 60), (1, 110)):
        p = Pose(pose.lean, pose.thigh_f - 40 * k, pose.shin_f - 40 * k, *[getattr(pose, n) for n in
                 ("thigh_b", "shin_b", "arm_f", "fore_f", "arm_b", "fore_b")])
        j = joints(p, "cutie", feet, facing)
        s = pygame.Surface(surf.get_size(), pygame.SRCALPHA)
        limb(s, j["hip"], j["knee_f"], PS.LIMB_W["cutie"], (*P.lighten(base, 0.4), a), ink=(*P.lighten(base, 0.4), a))
        limb(s, j["knee_f"], j["foot_f"], PS.LIMB_W["cutie"] - 1, (*P.lighten(base, 0.4), a), ink=(*P.lighten(base, 0.4), a))
        surf.blit(s, (0, 0))


# --- the sheet ---------------------------------------------------------------------------------


def robert(surf, x, facing=1, key="p1", pose="idle", body=GREEN):
    ring(surf, x, key)
    draw_puppet(surf, POSES[pose], "lean", (x, FLOOR_Y), facing, body, P.CREAM)


def row_look(sub, variant):
    robert(sub, 48)
    label(sub, "ROBERT", (48, 132))
    name = "A: TIERED" if variant == "A" else "B: CAGE"
    label(sub, name, (320, 20), P.GOLD)
    for x, posename, facing, key, dy, base, strike, ly, text in (
            (150, "idle", 1, "p1", 0, GREEN, None, 132, "M-CUTIE P1"),
            (252, "idle", -1, "p2", 0, PURPLE, None, 132, "P2"),
            (362, "heavy_hit", 1, "p1", 0, GREEN, ("hand_f", PURPLE), 132, "HEAVY HIT"),
            (478, "crouch", -1, "p2", 0, PURPLE, None, 166, "CROUCH"),
            (582, "jump", -1, "p1", -58, GREEN, None, 74, "JUMP")):
        ring(sub, x, key)
        draw_cutie(sub, POSES[posename], (x, FLOOR_Y + dy), facing, base, variant, strike,
                   swing=6 if posename == "jump" else 0)
        label(sub, text, (x, ly))


def row_moves(sub, variant="A"):
    label(sub, "HER SPECIALS (" + variant + ")", (320, 20), P.GOLD)
    # AMPLITUDE AMPLIFICATION: charging, 4 steps in
    ring(sub, 64, "p1")
    j = aura(sub, lambda s: draw_cutie(s, CHARGE, (64, FLOOR_Y), 1, GREEN, variant, bright=0.8), GREEN)
    glow(sub, j["hand_f"], 9, P.lighten(GREEN, 0.6), 160)
    pips(sub, (j["head"][0], j["head"][1] - 30), 4, GREEN)
    label(sub, "AMP. AMPLIFICATION", (82, 108))
    label(sub, "CHARGING", (64, 330))
    # two fired waves: 2 steps and 6 steps
    drive_pulse(sub, 172, 28, GREEN, 1)
    label(sub, "2 STEPS", (172, 330))
    drive_pulse(sub, 260, 60, GREEN, 1)
    label(sub, "6 STEPS", (260, 330))
    # ION TRAP: arming and armed
    ion_trap(sub, 360, GREEN, armed=False)
    label(sub, "ARMING", (360, 330))
    ion_trap(sub, 430, GREEN, armed=True)
    label(sub, "ARMED", (430, 330))
    label(sub, "ION TRAP", (395, 250))
    # SPIN in the air
    ring(sub, 560, "p1")
    feet = (556, FLOOR_Y - 70)
    leg_ghosts(sub, SPIN, feet, 1, GREEN)
    j = joints(SPIN, "cutie", feet, 1)
    spin_whirl(sub, j, GREEN, "back")
    draw_cutie(sub, SPIN, feet, 1, GREEN, variant, swing=10, spread=1.2, squash=0.75)
    spin_whirl(sub, j, GREEN, "front")
    label(sub, "SPIN", (560, 80))


def main(out: str) -> None:
    pygame.init()
    stage, _ = make_stage("cryo")
    rows = (lambda s: row_look(s, "A"), lambda s: row_look(s, "B"), lambda s: row_moves(s, MOVES_VARIANT))
    sheet = pygame.Surface((640, 360 * len(rows)))
    for i, draw in enumerate(rows):
        sub = sheet.subsurface((0, i * 360, 640, 360))
        sub.blit(stage, (-8, -8))
        draw(sub)
    pygame.image.save(pygame.transform.scale(sheet, (1280, 720 * len(rows))), out)
    pygame.image.save(sheet, out.replace(".png", "_1x.png"))


MOVES_VARIANT = "B"

if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "mcutie_sheet.png")
