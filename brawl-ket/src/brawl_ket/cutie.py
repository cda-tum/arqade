"""M-CUTIE's look: the android in a chandelier dress (variant B, the cage), and her specials.

Ported from her approved look, docs/superpowers/specs/2026-10-21-brawl-ket-m-cutie-look.py:
everything here is the look's own code (variant B only), given the joints instead of a pose and
a floor line instead of FLOOR_Y. tests/test_render.py checks her, her wave, her trap and her
SPIN against the look pixel for pixel.

The look drew everything every call. Her head, the wave and the trap are drawn once each onto
a small cached layer instead (`bake`): a see-through layer of what they paint, and a second
one of the light their additive glows throw on pixels they leave bare, which is added, not
painted. Each is anchored at the same pixel parity as where it is blitted, so Python's
round-half-to-even lands every point on the same pixel as a direct draw would: the result is
the same pixels, at two blits. The charge's halo is the one approximation: the look blended a
silhouette 16 times; here each pixel gets one blend with the alpha those 16 add up to.
"""

from __future__ import annotations

import math
from functools import lru_cache

import pygame

from . import palette as P
from .config import FLOOR_Y
from .ink import _ball, _pt, frame, limb, poly
from .ink import _towards as towards
from .poses import HEAD_R, LIMB_W, POSES, Pose, joints

# the stage's own chandelier colours (stages.py)
GOLD_PLATE = (232, 184, 72)
COAX = (176, 192, 216)
PORCELAIN = (240, 232, 232)
JOINT = (216, 208, 224)        # the pale ball joints at elbows and knees: a doll's joints
BLUSH = (240, 136, 168)
SHOE = (40, 32, 56)
GLASS = (24, 24, 56)

SPIN_SWING, SPIN_SPREAD, SPIN_SQUASH = 10, 1.2, 0.75    # SPIN: her hair blown back, the skirt flattened
JUMP_SWING = 6                  # ... and in a jump, her hair a little
HEAD_SIZE, HEAD_AT = (128, 104), (64, 40)       # a head layer, and where the head joint sits in it
PULSE_SIZE, PULSE_AT = (112, 80), (56, 72)      # a wave's layer: its middle, and the floor line
TRAP_SIZE, TRAP_AT = (56, 56), (28, 50)         # a trap's layer: its middle, and the floor line
CHARGE_SIZE, CHARGE_AT = (200, 232), (100, 216)  # the charge's halo: where her feet stand in it
HALO_SHIFTS = tuple((dx * r, dy * r) for r in (4, 2) for dx, dy in
                    ((-1, 0), (1, 0), (0, -1), (0, 1), (-1, -1), (1, -1), (-1, 1), (1, 1)))
GHOST_SIZE = (240, 200)         # SPIN's leg ghosts: drawn on a layer this big, her feet 40 px over its bottom


# --- shared helpers (the look's) -----------------------------------------------------------------


@lru_cache(maxsize=64)
def _glow_disc(r: int, color, alpha: int) -> pygame.Surface:
    g = pygame.Surface((2 * r + 2, 2 * r + 2))
    k0 = alpha / 255
    for k, a in ((1.0, 0.25), (0.7, 0.45), (0.42, 0.8)):
        pygame.draw.circle(g, tuple(round(v * a * k0) for v in color), (r + 1, r + 1), max(1, round(r * k)))
    return g


def glow(surf, c, r, color, alpha=90):
    """A soft round glow, added onto what is under it (light, not paint): three discs, the
    brightest in the middle. `alpha` (0..255) is how strong. (The look's, its disc cached.)"""
    g = _glow_disc(r, color, alpha)
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


# --- the cached layers ---------------------------------------------------------------------------


def bake(size, draw):
    """`draw(surface)` once onto a see-through layer and once onto black: the layer keeps
    every pixel it paints, `spill` (None if dark) the light its additive glows throw on the
    pixels it leaves bare; both cut to what they cover, with where that sits. blit_baked puts
    them down: the same pixels as drawing it there."""
    layer = pygame.Surface(size, pygame.SRCALPHA)
    draw(layer)
    spill = pygame.Surface(size)
    draw(spill)
    pygame.mask.from_surface(layer).to_surface(spill, setcolor=(0, 0, 0), unsetcolor=None)
    box = layer.get_bounding_rect()
    lit = spill.get_bounding_rect()
    return ((layer.subsurface(box).copy(), box.topleft),
            (spill.subsurface(lit).copy(), lit.topleft) if lit.w else None)


def blit_baked(surf, layers, topleft) -> None:
    (layer, (lx, ly)), spill = layers
    surf.blit(layer, (topleft[0] + lx, topleft[1] + ly))
    if spill is not None:
        light, (sx, sy) = spill
        surf.blit(light, (topleft[0] + sx, topleft[1] + sy), special_flags=pygame.BLEND_RGB_ADD)


def _parity(x: int, y: int) -> tuple[int, int]:
    return x & 1, y & 1


# --- the body (the look's) -----------------------------------------------------------------------


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


HOOPS = ((0, 26, 6), (13, 44, 9), (26, 60, 12))   # (drop below the waist, width, height) px
HEM = 10            # the fringe's tails and plugs below the last hoop's bottom (and a px spare)
MIN_FIT = 0.3       # the flattest the cage gets; lower than that it is lifted instead


def cage_hoops(j, at, spread=1.0, squash=1.0, floor=None):
    """The skirt's three hoops (x, y, w, h), hanging from the waist. Given the floor line, a cage
    that would sink into it (lying down, sliding, a pounce) is squashed flat onto it instead:
    the hoops' drops and heights shrink together until the hem's fringe rests on the floor, and
    a cage already as flat as it gets is lifted. Standing, crouching or in the air it never
    touches the floor, so it hangs exactly as the look draws it."""
    (wx, wy), shift = waist(j, at)
    fit, lift = None, 0.0
    if floor is not None:
        drop, h = HOOPS[-1][0], HOOPS[-1][2]
        room = floor - HEM - wy
        if drop * squash + h / 2 > room:
            fit = max(MIN_FIT, room / (drop + h / 2))
            lift = min(0.0, room - fit * (drop + h / 2))
    if fit is None:
        return [(wx + shift * u / 26, wy + u * squash, w * spread, hh) for u, w, hh in HOOPS]
    return [(wx + shift * u / 26, wy + lift + u * fit, w * spread, max(2, math.floor(hh * fit)))
            for u, w, hh in HOOPS]


def skirt_cage_back(surf, j, at, base, bright=0.0, spread=1.0, squash=1.0, floor=None):
    """The hoop skirt, behind the legs: the glow filling the bell, the far halves of the hoops."""
    hoops = cage_hoops(j, at, spread, squash, floor)
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


def skirt_cage_front(surf, j, at, base, facing, sway=0.0, spread=1.0, squash=1.0, floor=None):
    """...and in front of the legs: the rods and coax lines between the hoops, the near halves
    of the hoops, and a coax fringe with gold plugs hanging from the hem."""
    hoops = cage_hoops(j, at, spread, squash, floor)

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


# --- the head (the look's head_b) ----------------------------------------------------------------


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


def head(surf, j, base, facing, swing, part):
    """A shell of her colour with a dark glass face and soft LED eyes, two buns of coiled
    coax with an ion in each, a plug hanging from each bun. `part` "back" is the two hanging
    cables (drawn first), "front" the rest."""
    hx, hy = _pt(j["head"])
    r = HEAD_R["cutie"]
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


@lru_cache(maxsize=1024)  # the cables follow her lean to 0.1 px: a few hundred of them, about 7 kB each
def head_layers(base, facing: int, swing: float, part: str, odd: tuple[int, int]):
    """One half of her head (its cables, or the rest), baked at a head joint of parity `odd`."""
    at = (HEAD_AT[0] + odd[0], HEAD_AT[1] + odd[1])
    return bake(HEAD_SIZE, lambda s: head(s, {"head": at}, base, facing, swing, part))


def draw_head(surf, j, base, facing, swing, part) -> None:
    """head(), from its cached layers (the front never depends on `swing`)."""
    hx, hy = _pt(j["head"])
    odd = _parity(hx, hy)
    layers = head_layers(base, facing, round(swing, 1) if part == "back" else 0.0, part, odd)
    blit_baked(surf, layers, (hx - HEAD_AT[0] - odd[0], hy - HEAD_AT[1] - odd[1]))


# --- M-CUTIE -------------------------------------------------------------------------------------


def draw_cutie(surf, j, lean, facing, base, strike=None, bright=0.0, swing=0.0, spread=1.0, squash=1.0,
               floor=None):
    """M-CUTIE at the joints `j` (poses.joints, build "cutie") of a pose leaning `lean`, in her
    basis colour `base`. `strike` = (joint, colour) lights an attack's arm or leg; `bright`
    (0..1) is the charge's glow in the skirt; `swing` blows the hair back; `spread`/`squash`
    flare the skirt (SPIN); `floor` (the floor line's y, if any) keeps the skirt out of the
    floor (cage_hoops). Returns j."""
    at = frame(j, facing)
    w = LIMB_W["cutie"]
    swing += max(-4.0, min(8.0, lean * 0.3))
    draw_head(surf, j, base, facing, swing, "back")
    limbs_back(surf, j, base, facing, w)
    skirt_cage_back(surf, j, at, base, bright, spread, squash, floor)
    leg_front(surf, j, base, facing, w, strike)
    bodice(surf, at, j, base)
    skirt_cage_front(surf, j, at, base, facing, 2 + swing * 0.3, spread, squash, floor)
    draw_head(surf, j, base, facing, swing, "front")
    arm_front(surf, j, base, w, strike)
    return j


# --- AMPLITUDE AMPLIFICATION ---------------------------------------------------------------------


def drive_pulse(surf, x, h, color, facing, floor_y=FLOOR_Y):
    """AMPLITUDE AMPLIFICATION's wave: a microwave drive pulse running along the floor, a
    Gaussian envelope with the carrier oscillating inside it. Taller with every step."""
    half = 12 + h * 0.42
    sig = half / 2.1
    xs = [x + k for k in range(-round(half), round(half) + 1)]
    env = [h * math.exp(-((xx - x) / sig) ** 2) for xx in xs]
    floor = floor_y - 1
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


@lru_cache(maxsize=64)
def pulse_layers(h: int, color, facing: int, odd: tuple[int, int]):
    at = (PULSE_AT[0] + odd[0], PULSE_AT[1] + odd[1])
    return bake(PULSE_SIZE, lambda s: drive_pulse(s, at[0], h, color, facing, at[1]))


def draw_wave(surf, x: int, floor_y: int, h: int, color, facing: int) -> None:
    """A wave of height `h` with its middle at x, on the floor line floor_y: drive_pulse, cached."""
    odd = _parity(x, floor_y)
    blit_baked(surf, pulse_layers(h, color, facing, odd), (x - PULSE_AT[0] - odd[0], floor_y - PULSE_AT[1] - odd[1]))


def pips(surf, c, n, color):
    """The charge's steps above her head: one lit diamond per step."""
    x0 = c[0] - (n - 1) * 5
    for i in range(n):
        x, y = round(x0 + i * 10), round(c[1])
        d = [(x, y - 4), (x + 4, y), (x, y + 4), (x - 4, y)]
        pygame.draw.polygon(surf, P.INK, [(px, py) for px, py in ((x, y - 6), (x + 6, y), (x, y + 6), (x - 6, y))])
        pygame.draw.polygon(surf, P.lighten(color, 0.45), d)
        surf.set_at((x - 1, y - 1), P.WHITE)


def aura(surf, draw, color, k=1.0):
    """The look's charge glow, kept as the reference: whatever `draw` paints, ringed by a soft
    halo of her colour, blended 16 times over a full-screen layer. The game uses halo()."""
    tmp = pygame.Surface(surf.get_size(), pygame.SRCALPHA)
    j = draw(tmp)
    sil = pygame.mask.from_surface(tmp).to_surface(setcolor=(*P.lighten(color, 0.5), round(70 * k)),
                                                    unsetcolor=(0, 0, 0, 0))
    for dx, dy in HALO_SHIFTS:
        surf.blit(sil, (dx, dy))
    surf.blit(tmp, (0, 0))
    return j


def charge_look(steps: int) -> tuple[float, float]:
    """(bright, halo strength) after `steps` steps: the skirt brightest from 5 steps on, the
    halo growing with every one (the look's sheet shows 4 steps: 0.8 and 1.0)."""
    return min(1.0, steps / 5), steps / 4


@lru_cache(maxsize=48)
def halo(color, facing: int, steps: int) -> tuple[pygame.Surface, tuple[int, int]]:
    """The charge's halo round her charging silhouette (feet at CHARGE_AT), as one layer (cut
    to what it covers, and where that sits): each pixel the 16 shifted silhouettes cover gets
    the alpha their blends add up to."""
    bright, k = charge_look(steps)
    body = pygame.Surface(CHARGE_SIZE, pygame.SRCALPHA)
    pose = POSES["charge"]
    draw_cutie(body, joints(pose, "cutie", CHARGE_AT, facing), pose.lean, facing, color, bright=bright)
    sil = pygame.mask.from_surface(body)
    size = sil.get_size()
    counts = [pygame.mask.Mask(size) for _ in HALO_SHIFTS]    # counts[n]: covered more than n times
    for dx, dy in HALO_SHIFTS:
        for n in range(len(counts) - 1, 0, -1):
            counts[n].draw(counts[n - 1].overlap_mask(sil, (dx, dy)), (0, 0))
        counts[0].draw(sil, (dx, dy))
    out = pygame.Surface(CHARGE_SIZE, pygame.SRCALPHA)
    a = round(70 * k) / 255
    rgb = P.lighten(color, 0.5)
    for n, mask in enumerate(counts):
        only = mask.copy()
        if n + 1 < len(counts):
            only.erase(counts[n + 1], (0, 0))
        only.erase(sil, (0, 0))                 # under her body: she is drawn over it
        alpha = round(255 * (1 - (1 - a) ** (n + 1)))
        only.to_surface(out, setcolor=(*rgb, alpha), unsetcolor=None)
    box = out.get_bounding_rect()
    return out.subsurface(box).copy(), box.topleft


def draw_charging(surf, pose, feet, facing, base, steps, floor=None) -> dict:
    """Charging: the halo, her body (in `pose`) glowing `steps` steps bright, her front hand
    alight, and a pip per step above her head (the look's row of specials). Returns the joints."""
    bright, _k = charge_look(steps)
    fx, fy = round(feet[0]), round(feet[1])
    layer, (lx, ly) = halo(base, facing, steps)
    surf.blit(layer, (fx - CHARGE_AT[0] + lx, fy - CHARGE_AT[1] + ly))
    j = draw_cutie(surf, joints(pose, "cutie", feet, facing), pose.lean, facing, base, bright=bright, floor=floor)
    glow(surf, j["hand_f"], 9, P.lighten(base, 0.6), 160)
    pips(surf, (j["head"][0], j["head"][1] - 30), steps, base)
    return j


# --- ION TRAP ------------------------------------------------------------------------------------


def ion_trap(surf, x, color, armed, floor=FLOOR_Y):
    """ION TRAP on the floor: two gold electrodes on a dark chip, the ion floating between.
    Dim while it arms; lit (the ion bright, the electrode tips glowing, the field round the
    ion) once armed."""
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


@lru_cache(maxsize=16)
def trap_layers(color, armed: bool):
    return bake(TRAP_SIZE, lambda s: ion_trap(s, TRAP_AT[0], color, armed, TRAP_AT[1]))


def draw_trap(surf, x: int, floor: int, color, armed: bool) -> None:
    """A trap with its middle at x on the floor line `floor`: ion_trap, cached."""
    blit_baked(surf, trap_layers(color, armed), (x - TRAP_AT[0], floor - TRAP_AT[1]))


# --- SPIN ----------------------------------------------------------------------------------------


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


@lru_cache(maxsize=32)
def ghost_layers(pose: Pose, feet: tuple[float, float], facing: int, base) -> tuple[pygame.Surface, ...]:
    """The two faint copies of her front leg, each on its own layer, for her feet at `feet`
    in it (SPIN holds one pose and one height, so a spin draws these once)."""
    out = []
    for k, a in ((2, 60), (1, 110)):
        p = Pose(pose.lean, pose.thigh_f - 40 * k, pose.shin_f - 40 * k, *[getattr(pose, n) for n in
                 ("thigh_b", "shin_b", "arm_f", "fore_f", "arm_b", "fore_b")])
        j = joints(p, "cutie", feet, facing)
        s = pygame.Surface(GHOST_SIZE, pygame.SRCALPHA)
        colour = (*P.lighten(base, 0.4), a)
        limb(s, j["hip"], j["knee_f"], LIMB_W["cutie"], colour, ink=colour)
        limb(s, j["knee_f"], j["foot_f"], LIMB_W["cutie"] - 1, colour, ink=colour)
        out.append(s)
    return tuple(out)


def leg_ghosts(surf, pose, feet, facing, base):
    """Faint copies of her front leg sweeping behind it (the look's, on small cached layers
    round her feet instead of full-screen ones, shifted by an even number of px: the same pixels)."""
    ox = math.floor(feet[0]) - GHOST_SIZE[0] // 2
    oy = math.floor(feet[1]) - GHOST_SIZE[1] + 40
    ox, oy = ox - (ox & 1), oy - (oy & 1)
    for s in ghost_layers(pose, (feet[0] - ox, feet[1] - oy), facing, base):
        surf.blit(s, (ox, oy))


def draw_spin(surf, pose, feet, facing, base, strike=None, floor=None) -> dict:
    """SPIN as the look draws it: the leg's ghosts and the far whirl behind her, her skirt
    flattened and widened, the near whirl in front. Returns the joints."""
    leg_ghosts(surf, pose, feet, facing, base)
    j = joints(pose, "cutie", feet, facing)
    spin_whirl(surf, j, base, "back")
    draw_cutie(surf, j, pose.lean, facing, base, strike, swing=SPIN_SWING, spread=SPIN_SPREAD, squash=SPIN_SQUASH,
               floor=floor)
    spin_whirl(surf, j, base, "front")
    return j
