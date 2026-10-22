"""SUPERposition: look mockups for the six supers still to build (DOS's is agreed and built).

    cd brawl-ket && SDL_VIDEODRIVER=dummy uv run python ../docs/superpowers/specs/2026-10-22-brawl-ket-superposition-looks.py OUT_DIR

One sheet per super, OUT_DIR/super_look_<name>.png: four panels at the game's 640x360, drawn over
a real stage and HUD with the game's own fighters, poses and art. Panels 1-3 are the super's
beats; panel 4 is how to dodge it. The captions are mockup labels, not game text.
"""

from __future__ import annotations

import math
import os
import sys

import pygame

pygame.init()

from brawl_ket import palette as P  # noqa: E402
from brawl_ket.config import FLOOR_Y, PLAYER_COLORS  # noqa: E402
from brawl_ket.erwin import box as erwin_box  # noqa: E402
from brawl_ket.fight import Fight  # noqa: E402
from brawl_ket.kids import draw_kid, flash, glow, key_sprite  # noqa: E402
from brawl_ket.moves import CHARACTERS  # noqa: E402
from brawl_ket.poses import POSES, joints  # noqa: E402
from brawl_ket.render import GREEN, PURPLE, SHADOW, Renderer, blit_center, draw_character, outlined  # noqa: E402

W, H = 640, 360
FROST = (168, 224, 248)
GOLD_PLATE = (232, 184, 72)
COAX = (176, 200, 216)


# --- the shared pieces --------------------------------------------------------------------------


def backdrop(hero: str, rival: str, stage: str) -> pygame.Surface:
    """The stage and the HUD of a real fight between the two, with nobody standing on it."""
    surf = pygame.Surface((W, H))
    fight = Fight({"p1": CHARACTERS[hero], "p2": CHARACTERS[rival]})
    for f in (*fight.fighters.values(), *fight.echoes.values()):
        f.x = -900.0
    r = Renderer(surf)
    r.use_stage(stage)
    r.draw_fight(fight, [], {"p1": 0, "p2": 0})
    return surf


def ring(surf, x, key, y=0.0):
    rect = pygame.Rect(0, 0, 54, 9)
    rect.center = (round(x), FLOOR_Y + 2)
    pygame.draw.ellipse(surf, SHADOW, rect)
    if y < 20:
        pygame.draw.ellipse(surf, PLAYER_COLORS[key], rect, 2)


def body(surf, name, pose, x, facing, colour, y=0.0, key="p1", scale=1.0, alpha=255, rings=True):
    """A fighter as the game draws them (draw_character), feet at x and y px up; scaled or
    see-through through a layer of its own."""
    if rings:
        ring(surf, x, key, y)
    if scale == 1.0 and alpha == 255:
        draw_character(surf, CHARACTERS[name], POSES[pose], (x, FLOOR_Y - y), facing, colour)
        return
    layer = pygame.Surface((320, 320), pygame.SRCALPHA)
    draw_character(layer, CHARACTERS[name], POSES[pose], (160, 300), facing, colour)
    if scale != 1.0:
        layer = pygame.transform.scale_by(layer, scale)
    layer.set_alpha(alpha)
    surf.blit(layer, (round(x - 160 * scale), round(FLOOR_Y - y - 300 * scale)))


def caption(surf, n, text):
    band = pygame.Surface((W, 22), pygame.SRCALPHA)
    band.fill((*P.INK, 210))
    surf.blit(band, (0, H - 22))
    surf.blit(outlined(f"{n}  {text}" if n else text, 8, P.GOLD if n else P.SKY), (8, H - 16))


def star(surf, c, r, colour):
    cx, cy = c
    for a in range(4):
        ang = a * math.pi / 4
        dx, dy = math.cos(ang) * r, math.sin(ang) * r
        pygame.draw.line(surf, P.INK, (cx - dx, cy - dy), (cx + dx, cy + dy), 5)
    for a in range(4):
        ang = a * math.pi / 4
        dx, dy = math.cos(ang) * r, math.sin(ang) * r
        pygame.draw.line(surf, colour, (cx - dx, cy - dy), (cx + dx, cy + dy), 2)
    pygame.draw.circle(surf, P.WHITE, (round(cx), round(cy)), 3)


def counter(surf, c, text):
    blit_center(surf, outlined(text, 16, P.GOLD, thick=2), c)


def speed_lines(surf, x, y, facing, colour, n=4, length=46):
    for i in range(n):
        yy = y + (i - n / 2) * 12
        x0 = x - facing * (10 + (i % 2) * 8)
        pygame.draw.line(surf, P.INK, (x0, yy), (x0 - facing * length, yy), 4)
        pygame.draw.line(surf, P.lighten(colour, 0.4), (x0, yy), (x0 - facing * length, yy), 2)


def sheet(panels) -> pygame.Surface:
    out = pygame.Surface((W * 2 + 8, H * 2 + 8))
    out.fill(P.INK)
    for k, p in enumerate(panels):
        out.blit(p, ((k % 2) * (W + 8), (k // 2) * (H + 8)))
    return out


# --- ROBERT: BLOCH SPHERE -------------------------------------------------------------------------


def bloch(surf, c, r, colour, up=True, spin=0.4, fill=40):
    """A Bloch sphere: a glowing wireframe ball (rim, equator, a meridian turned `spin`), its z
    axis with |0> on top and |1> below, and the state arrow."""
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
    for y in range(cy - r, cy + r, 6):                  # the z axis, dashed
        pygame.draw.line(surf, P.MIST, (cx, y), (cx, min(y + 3, cy + r)), 1)
    if r >= 50:
        blit_center(surf, outlined("|0>", 8, P.WHITE if up else P.MIST), (cx, cy - r - 9))
        blit_center(surf, outlined("|1>", 8, P.MIST if up else P.WHITE), (cx, cy + r + 9))
    tip = (cx, cy - round(0.85 * r) if up else cy + round(0.85 * r))
    pygame.draw.line(surf, P.INK, (cx, cy), tip, 5)
    pygame.draw.line(surf, P.WHITE, (cx, cy), tip, 2)
    d = -1 if up else 1
    pygame.draw.polygon(surf, P.INK, [(tip[0] - 6, tip[1] - d * 7), (tip[0] + 6, tip[1] - d * 7), (tip[0], tip[1] + d * 3)])
    pygame.draw.polygon(surf, P.WHITE, [(tip[0] - 4, tip[1] - d * 6), (tip[0] + 4, tip[1] - d * 6), (tip[0], tip[1] + d)])
    pygame.draw.circle(surf, P.INK, (cx, cy), 4)
    pygame.draw.circle(surf, colour, (cx, cy), 2)


def h_gate(surf, c, size=28):
    box = pygame.Rect(0, 0, size, size)
    box.center = (round(c[0]), round(c[1]))
    glow(surf, box.center, size, P.GOLD, 110)
    pygame.draw.rect(surf, P.INK, box.inflate(4, 4), border_radius=4)
    pygame.draw.rect(surf, P.GOLD, box, border_radius=3)
    blit_center(surf, outlined("H", 16, P.INK, outline=P.GOLD), box.center)


def bloch_sheet():
    hero, rival, stage = "ROBERT", "BOHR", "lab"
    p1 = backdrop(hero, rival, stage)
    body(p1, rival, "idle", 450, -1, GREEN, key="p2")
    body(p1, hero, "brace", 200, 1, GREEN)
    bloch(p1, (200, FLOOR_Y - 66), 72, GREEN, up=True, spin=0.9, fill=34)
    caption(p1, 1, "THE SPHERE FORMS ROUND HIM: |0>, HIS ARROW UP")

    p2 = backdrop(hero, rival, stage)
    body(p2, rival, "hitstun", 420, -1, GREEN, key="p2")
    ring(p2, 330, "p1")
    body(p2, hero, "crouch", 330, 1, GREEN, y=10, scale=0.5, rings=False)
    bloch(p2, (330, FLOOR_Y - 36), 36, GREEN, up=True, spin=0.3, fill=70)
    speed_lines(p2, 294, FLOOR_Y - 36, 1, GREEN)
    for k in range(3):                                  # dust behind it
        pygame.draw.circle(p2, P.MIST, (250 - 18 * k, FLOOR_Y - 4 - 3 * k), 5 - k)
    star(p2, (392, FLOOR_Y - 56), 14, GREEN)
    counter(p2, (330, FLOOR_Y - 104), "2/4")
    caption(p2, 2, "IT ROLLS IN LIKE A WRECKING BALL: 4 HITS OF 4")

    p3 = backdrop(hero, rival, stage)
    body(p3, rival, "knockdown", 470, -1, GREEN, y=70, key="p2")
    body(p3, hero, "slam", 390, 1, PURPLE, y=24)
    h_gate(p3, (402, FLOOR_Y - 196))
    bloch(p3, (300, FLOOR_Y - 190), 52, PURPLE, up=False, spin=1.2, fill=30)
    star(p3, (440, FLOOR_Y - 150), 16, PURPLE)
    caption(p3, 3, "H-GATE UPPERCUT (9): THE ARROW FLIPS TO |1>, HE TURNS PURPLE")

    p4 = backdrop(hero, rival, stage)
    ring(p4, 300, "p1")
    body(p4, hero, "crouch", 300, 1, GREEN, y=10, scale=0.5, rings=False)
    bloch(p4, (300, FLOOR_Y - 36), 36, GREEN, up=True, spin=1.1, fill=70)
    speed_lines(p4, 264, FLOOR_Y - 36, 1, GREEN)
    body(p4, rival, "jump", 330, -1, GREEN, y=118, key="p2")
    caption(p4, 0, "DODGE: JUMP THE SPHERE (IT IS LOW)")
    return sheet((p1, p2, p3, p4))


# --- BOHR: WAVEFUNCTION COLLAPSE --------------------------------------------------------------------


def cloud(surf, centre, sigma, colour, t=0.0, amp=26):
    """A probability cloud on the floor: a dotted wave under a Gaussian envelope, and faint bars
    of |psi|^2 under it."""
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
        y = FLOOR_Y - 30 - env * amp * math.sin(x / 9 + t)
        if env > 0.04:
            surf.fill(P.INK, (x - 1, round(y) - 1, 4, 4))
            surf.fill(light if (x // 3) % 2 else P.WHITE, (x, round(y), 2, 2))
    for k in range(14):                                 # motes rising
        x = centre + sigma * math.sin(k * 2.4) * 0.9
        y = FLOOR_Y - 40 - (k * 23) % 90
        surf.fill(light, (round(x), y, 2, 2))


def lock_ring(surf, x, colour=P.WHITE):
    rect = pygame.Rect(0, 0, 76, 14)
    rect.center = (x, FLOOR_Y + 2)
    pygame.draw.ellipse(surf, P.INK, rect.inflate(4, 4), 4)
    pygame.draw.ellipse(surf, colour, rect, 2)
    for sx in (-1, 1):                                  # the lock-on's brackets
        for sy in (-1, 1):
            cx, cy = x + sx * 46, FLOOR_Y - 60 + sy * 64
            pygame.draw.lines(surf, colour, False, [(cx, cy - sy * 12), (cx, cy), (cx - sx * 12, cy)], 2)


def pillar(surf, x, colour, top=40):
    glow(surf, (x, FLOOR_Y - 40), 70, colour, 90)
    for w, a, c in ((70, 110, colour), (46, 170, P.lighten(colour, 0.4)), (18, 240, P.WHITE)):
        col = pygame.Surface((w, FLOOR_Y - top), pygame.SRCALPHA)
        col.fill((*c, a))
        surf.blit(col, (x - w // 2, top))
    for sx in (-35, 35):                                # its ink edges
        pygame.draw.line(surf, P.INK, (x + sx, top), (x + sx, FLOOR_Y), 2)
    for k in range(10):                                 # dots sucked inward
        ang = k * math.tau / 10
        r0, r1 = 110, 44
        a = (x + math.cos(ang) * r0, FLOOR_Y - 90 + math.sin(ang) * r0 * 0.6)
        b = (x + math.cos(ang) * r1, FLOOR_Y - 90 + math.sin(ang) * r1 * 0.6)
        pygame.draw.line(surf, P.lighten(colour, 0.5), a, b, 1)
        pygame.draw.circle(surf, P.WHITE, (round(a[0]), round(a[1])), 2)
    rect = pygame.Rect(0, 0, 96, 16)
    rect.center = (x, FLOOR_Y + 2)
    pygame.draw.ellipse(surf, P.WHITE, rect, 3)


def collapse_sheet():
    hero, rival, stage = "BOHR", "PHOEBE", "lab"       # (the bright office drowned the cloud)
    p1 = backdrop(hero, rival, stage)
    cloud(p1, 330, 260, GREEN, amp=22)
    body(p1, rival, "idle", 440, -1, PURPLE, key="p2")
    body(p1, hero, "stomp", 170, 1, GREEN)
    caption(p1, 1, "ARMS UP: A PROBABILITY CLOUD SPREADS ACROSS THE FLOOR")

    p2 = backdrop(hero, rival, stage)
    cloud(p2, 440, 60, GREEN, t=1.5, amp=34)
    body(p2, rival, "walk1", 440, -1, PURPLE, key="p2")
    body(p2, hero, "stomp", 170, 1, GREEN)
    lock_ring(p2, 440)
    caption(p2, 2, "IT LOCKS ON: A WHITE RING WHERE THEY STAND")

    p3 = backdrop(hero, rival, stage)
    body(p3, hero, "slam", 170, 1, GREEN)
    body(p3, rival, "hitstun", 440, -1, PURPLE, key="p2")
    pillar(p3, 440, GREEN)
    star(p3, (440, FLOOR_Y - 80), 18, GREEN)
    caption(p3, 3, "COLLAPSE: A PILLAR OF LIGHT ON THE LOCKED SPOT (25, KNOCKDOWN)")

    p4 = backdrop(hero, rival, stage)
    body(p4, hero, "slam", 170, 1, GREEN)
    pillar(p4, 400, GREEN)
    body(p4, rival, "walk2", 520, -1, PURPLE, key="p2")
    caption(p4, 0, "DODGE: MOVE AFTER THE LOCK; IT FALLS WHERE YOU WERE")
    return sheet((p1, p2, p3, p4))


# --- PHOEBE: COHERENT BEAM -------------------------------------------------------------------------


def flare(surf, c, r, colour):
    glow(surf, c, r, colour, 150)
    glow(surf, c, r // 2, P.WHITE, 200)
    cx, cy = c
    for ang, ln in ((0, r * 2), (math.pi / 2, r), (math.pi / 4, r * 0.7), (-math.pi / 4, r * 0.7)):
        dx, dy = math.cos(ang) * ln, math.sin(ang) * ln
        pygame.draw.line(surf, P.WHITE, (cx - dx, cy - dy), (cx + dx, cy + dy), 1)


def beam(surf, x0, colour, t=0, height=110, k=1.0):
    """COHERENT BEAM: from her hands to the screen's edge, floor to `height` px up; colour edges,
    a lighter body, a white core, and interference fringes."""
    top = FLOOR_Y - round(height * k)
    w = W - x0
    for inset, a, c in ((0, 150, colour), (10, 190, P.lighten(colour, 0.35)), (34, 240, P.WHITE)):
        h = round((height - 2 * inset) * k)
        if h <= 0:
            continue
        band = pygame.Surface((w, h), pygame.SRCALPHA)
        band.fill((*c, a))
        surf.blit(band, (x0, FLOOR_Y - round(height * k) + round(inset * k)))
    fringe = pygame.Surface((w, round(height * k)), pygame.SRCALPHA)
    for x in range(-14, w, 14):
        fringe.fill((*P.INK, 40), (x + (t % 14), 0, 6, fringe.get_height()))
    surf.blit(fringe, (x0, top))
    pygame.draw.line(surf, P.INK, (x0, top - 1), (W, top - 1), 2)


def beam_sheet():
    hero, rival, stage = "PHOEBE", "DOS", "optics"
    hands = (200, FLOOR_Y - 92)
    p1 = backdrop(hero, rival, stage)
    body(p1, rival, "idle", 470, -1, GREEN, key="p2")
    body(p1, hero, "throw_reach", 150, 1, PURPLE)
    flare(p1, hands, 26, PURPLE)
    caption(p1, 1, "SHE PLANTS HER FEET: THE FLARE GROWS IN HER HANDS")

    p2 = backdrop(hero, rival, stage)
    body(p2, rival, "hitstun", 470, -1, GREEN, key="p2")
    body(p2, hero, "throw_reach", 150, 1, PURPLE)
    beam(p2, hands[0], PURPLE, t=3)
    flare(p2, hands, 34, PURPLE)
    star(p2, (446, FLOOR_Y - 70), 16, PURPLE)
    counter(p2, (470, FLOOR_Y - 170), "3/5")
    caption(p2, 2, "THE BEAM: FLOOR TO 110 PX, TO THE SCREEN'S EDGE: 5 HITS OF 5")

    p3 = backdrop(hero, rival, stage)
    body(p3, rival, "knockdown", 540, -1, GREEN, key="p2")
    body(p3, hero, "throw_reach", 150, 1, PURPLE)
    beam(p3, hands[0], PURPLE, t=9, k=0.35)
    flare(p3, hands, 16, PURPLE)
    caption(p3, 3, "IT NARROWS AND FADES; SHE RECOVERS")

    p4 = backdrop(hero, rival, stage)
    body(p4, hero, "throw_reach", 150, 1, PURPLE)
    beam(p4, hands[0], PURPLE, t=6)
    flare(p4, hands, 34, PURPLE)
    body(p4, rival, "jump", 430, -1, GREEN, y=128, key="p2")
    caption(p4, 0, "DODGE: BE ABOVE IT (EVERY JUMP PEAKS OVER 110 PX)")
    return sheet((p1, p2, p3, p4))


# --- ERWIN: NINE LIVES ------------------------------------------------------------------------------


def ghost(surf, pose, x, facing, y=0.0, alpha=120):
    body(surf, "ERWIN", pose, x, facing, P.lighten(GREEN, 0.45), y=y, alpha=alpha, rings=False)


def nine_sheet():
    hero, rival, stage = "ERWIN", "ROBERT", "lab"
    target = 420
    p1 = backdrop(hero, rival, stage)
    body(p1, rival, "idle", target, -1, GREEN, key="p2")
    ring(p1, 200, "p1")
    erwin_box(p1, 200, 70, 48, 1, GREEN, FLOOR_Y)
    spots = [(target + dx, y) for dx, y in ((-150, 0), (150, 0), (-110, 60), (110, 60), (-70, 110),
                                            (70, 110), (-170, 90), (170, 90))]
    for k, (x, y) in enumerate(spots):
        pygame.draw.line(p1, P.lighten(GREEN, 0.5), (200, FLOOR_Y - 50), (x, FLOOR_Y - y - 60), 1)
        ghost(p1, "idle" if y == 0 else "jump", x, 1 if x < target else -1, y=y, alpha=110)
    counter(p1, (target, FLOOR_Y - 220), "x9")
    caption(p1, 1, "INTO THE BOX, AND IT SPLITS INTO NINE ERWINS ROUND THE RIVAL")

    p2 = backdrop(hero, rival, stage)
    body(p2, rival, "hitstun", target, -1, GREEN, key="p2")
    ghost(p2, "pounce", target - 40, 1, alpha=150)
    ghost(p2, "pounce", target + 120, -1, y=20, alpha=110)
    speed_lines(p2, target + 150, FLOOR_Y - 40, -1, GREEN)
    ghost(p2, "idle", target - 160, 1, y=80, alpha=70)
    star(p2, (target - 6, FLOOR_Y - 40), 14, GREEN)
    counter(p2, (target, FLOOR_Y - 180), "4/9")
    caption(p2, 2, "EIGHT GHOST POUNCES, LOW, FROM ALTERNATING SIDES (2 EACH)")

    p3 = backdrop(hero, rival, stage)
    body(p3, rival, "knockdown", target + 50, -1, GREEN, key="p2", y=20)
    body(p3, hero, "swipe", target - 50, 1, GREEN)
    for k in range(3):                                  # the claw marks
        a = (target - 4 + 14 * k, FLOOR_Y - 150)
        b = (target + 40 + 14 * k, FLOOR_Y - 40)
        pygame.draw.line(p3, P.INK, a, b, 6)
        pygame.draw.line(p3, P.WHITE, a, b, 3)
    counter(p3, (target, FLOOR_Y - 190), "9/9")
    caption(p3, 3, "THE NINTH IS THE REAL ERWIN: A BIG SWIPE (9, KNOCKDOWN)")

    p4 = backdrop(hero, rival, stage)
    body(p4, rival, "jump", target, -1, GREEN, y=90, key="p2")
    ghost(p4, "pounce", target - 10, 1, alpha=150)
    ghost(p4, "pounce", target + 140, -1, alpha=100)
    caption(p4, 0, "DODGE: PARTLY: JUMP IN TIME WITH THE POUNCES")
    return sheet((p1, p2, p3, p4))


# --- M-CUTIE: DILUTION FRIDGE -----------------------------------------------------------------------


def fridge(surf, cx, bottom, s=1.2, falling=False):
    """The dilution refrigerator (the cryo stage's chandelier, made a weapon, half as big again
    and glowing with frost so it never reads as the stage's own): gold plates getting smaller
    downwards, rods and coax lines between them, the mixing chamber at the bottom."""
    glow(surf, (cx, bottom - round(90 * s)), round(150 * s), FROST, 70)
    if falling:                                         # fall streaks above it
        for dx in range(-round(100 * s), round(100 * s) + 1, round(28 * s)):
            top = bottom - round(260 * s)
            pygame.draw.line(surf, P.INK, (cx + dx, top - 60), (cx + dx, top), 4)
            pygame.draw.line(surf, P.WHITE, (cx + dx, top - 60), (cx + dx, top), 2)
    plates = [(-150, 200), (-115, 164), (-82, 132), (-52, 104), (-26, 80)]
    plates = [(bottom + round(dy * s) - 30, round(w * s)) for dy, w in plates]
    for (y0, w0), (y1, w1) in zip(plates, plates[1:]):
        for side in (-1, 1):
            a, b = (cx + side * (w0 // 2 - 10), y0), (cx + side * (w1 // 2 - 8), y1)
            pygame.draw.line(surf, P.INK, a, b, 5)
            pygame.draw.line(surf, P.shade(GOLD_PLATE, 0.85), a, b, 3)
        for k in range(-3, 4):
            a = (cx + k * (w0 // 8), y0 + 4)
            b = (cx + k * (w1 // 8), y1)
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
    for k in range(8):                                  # frost
        surf.fill(FROST, (cx - 90 + (k * 37) % 180, plates[k % 5][0] + 12, 3, 2))


def shadow_mark(surf, x, w=110, locked=False, colour=PURPLE):
    """The fridge's shadow: a dark disc ringed in her colour, dashed while it follows, solid white
    once it locks."""
    rect = pygame.Rect(0, 0, w, 18)
    rect.center = (x, FLOOR_Y + 2)
    sh = pygame.Surface(rect.size, pygame.SRCALPHA)
    pygame.draw.ellipse(sh, (*P.INK, 190), sh.get_rect())
    surf.blit(sh, rect)
    ring_rect = rect.inflate(8, 6)
    if locked:
        pygame.draw.ellipse(surf, P.INK, ring_rect.inflate(4, 4), 4)
        pygame.draw.ellipse(surf, P.WHITE, ring_rect, 2)
        return
    for k in range(16):                                 # dashed
        a0 = k * math.tau / 16
        pygame.draw.arc(surf, P.lighten(colour, 0.3), ring_rect, a0, a0 + math.tau / 32, 3)


def frost_wave(surf, x, reach=120):
    for side in (-1, 1):
        for k in range(9):
            sx = x + side * (30 + k * reach / 9)
            h = 26 - k * 2
            pts = [(sx - 5, FLOOR_Y), (sx, FLOOR_Y - h), (sx + 5, FLOOR_Y)]
            pygame.draw.polygon(surf, P.INK, pts)
            pygame.draw.polygon(surf, FROST, [(sx - 3, FLOOR_Y - 1), (sx, FLOOR_Y - h + 3), (sx + 3, FLOOR_Y - 1)])
    for k in range(18):                                 # snow
        surf.fill(P.WHITE, (x - reach + (k * 53) % (2 * reach), FLOOR_Y - 20 - (k * 29) % 90, 2, 2))


def fridge_sheet():
    hero, rival, stage = "M-CUTIE", "ERWIN", "cryo"
    target = 500                                        # (clear of the stage's own fridge, in the middle)
    p1 = backdrop(hero, rival, stage)
    shadow_mark(p1, target)
    body(p1, rival, "walk1", target, -1, GREEN, key="p2")
    body(p1, hero, "slam", 160, 1, PURPLE)
    caption(p1, 1, "SHE POINTS STRAIGHT UP: A SHADOW FOLLOWS THE RIVAL")

    p2 = backdrop(hero, rival, stage)
    shadow_mark(p2, target, w=130, locked=True)
    body(p2, rival, "idle", target, -1, GREEN, key="p2")
    body(p2, hero, "slam", 180, 1, PURPLE)
    fridge(p2, target, 150, falling=True)
    caption(p2, 2, "IT LOCKS: A GIANT GOLD DILUTION FRIDGE DROPS FROM ABOVE")

    p3 = backdrop(hero, rival, stage)
    body(p3, hero, "idle", 180, 1, PURPLE)
    body(p3, rival, "knockdown", target + 30, -1, GREEN, key="p2")
    fridge(p3, target, FLOOR_Y + 6)
    frost_wave(p3, target)
    caption(p3, 3, "CRASH (20, KNOCKDOWN), AND A FROSTY SHOCKWAVE EITHER SIDE (5, LOW)")

    p4 = backdrop(hero, rival, stage)
    body(p4, hero, "idle", 180, 1, PURPLE)
    fridge(p4, target, FLOOR_Y + 6)
    frost_wave(p4, target)
    body(p4, rival, "jump", target - 170, 1, GREEN, y=60, key="p2")
    caption(p4, 0, "DODGE: WALK OUT OF THE SHADOW, JUMP THE FROST")
    return sheet((p1, p2, p3, p4))


# --- ALICE & BOB: ONE-TIME PAD ----------------------------------------------------------------------


def kid(surf, who, pose, x, facing, colour, y=0.0):
    ring(surf, x, "p1", y)
    draw_kid(surf, joints(POSES[pose], who, (x, FLOOR_Y - y), facing), facing, colour, who)


def padlock(surf, c, closed=True):
    cx, cy = c
    shackle = pygame.Rect(0, 0, 44, 52)
    shackle.midbottom = (cx, cy - 4 if closed else cy - 24)
    pygame.draw.arc(surf, P.INK, shackle.inflate(8, 8), 0, math.pi, 12)
    pygame.draw.arc(surf, P.MIST, shackle, 0, math.pi, 6)
    for sx in (shackle.left + 3, shackle.right - 3):
        pygame.draw.line(surf, P.INK, (sx, shackle.centery), (sx, cy + 4), 10)
        pygame.draw.line(surf, P.MIST, (sx, shackle.centery), (sx, cy + 4), 5)
    body_rect = pygame.Rect(0, 0, 70, 54)
    body_rect.midtop = (cx, cy)
    glow(surf, body_rect.center, 50, P.GOLD, 120)
    pygame.draw.rect(surf, P.INK, body_rect.inflate(6, 6), border_radius=8)
    pygame.draw.rect(surf, P.GOLD, body_rect, border_radius=6)
    surf.fill(P.lighten(P.GOLD, 0.5), (body_rect.x + 6, body_rect.y + 4, body_rect.w - 12, 3))
    pygame.draw.circle(surf, P.INK, (cx, body_rect.y + 22), 7)
    pygame.draw.rect(surf, P.INK, (cx - 3, body_rect.y + 24, 6, 16))


def otp_sheet():
    hero, rival, stage = "ALICE & BOB", "BOHR", "toronto"
    target = 400
    alice, bob = GREEN, PURPLE                          # always opposite colours
    p1 = backdrop(hero, rival, stage)
    flash(p1, 200, GREEN, 0.5)
    flash(p1, 160, PURPLE, 0.5)
    flash(p1, target - 70, GREEN)
    flash(p1, target + 70, PURPLE)
    body(p1, rival, "idle", target, -1, GREEN, key="p2")
    kid(p1, "alice", "catch", target - 70, 1, alice)
    kid(p1, "bob", "catch", target + 70, -1, bob)
    caption(p1, 1, "THEY VANISH, AND RE-FORM EITHER SIDE OF THE RIVAL")

    p2 = backdrop(hero, rival, stage)
    body(p2, rival, "hitstun", target, -1, GREEN, key="p2")
    kid(p2, "alice", "fire", target - 70, 1, alice)
    kid(p2, "bob", "catch", target + 70, -1, bob)
    for x in range(target - 50, target + 52, 8):        # the key's path, through the rival
        p2.fill(P.INK, (x - 1, FLOOR_Y - 77, 5, 4))
        p2.fill(P.GOLD, (x, FLOOR_Y - 76, 3, 2))
    key = key_sprite(GREEN, True, 1)
    p2.blit(key, key.get_rect(center=(target + 26, FLOOR_Y - 76)))
    star(p2, (target, FLOOR_Y - 76), 14, P.GOLD)
    counter(p2, (target, FLOOR_Y - 180), "3/6")
    caption(p2, 2, "THE KEY FLIES BACK AND FORTH THROUGH THEM: 6 PASSES (3 EACH)")

    p3 = backdrop(hero, rival, stage)
    body(p3, rival, "hitstun", target, -1, GREEN, key="p2")
    kid(p3, "alice", "toss", target - 80, 1, alice)
    kid(p3, "bob", "fire", target + 80, -1, bob)
    padlock(p3, (target, FLOOR_Y - 120))
    blit_center(p3, outlined("CLICK!", 16, P.WHITE, thick=2), (target + 70, FLOOR_Y - 190))
    caption(p3, 3, "A GIANT PADLOCK SNAPS SHUT ON THEM: CLICK (7, KNOCKDOWN)")

    p4 = backdrop(hero, rival, stage)
    flash(p4, 250, GREEN, 0.7)
    kid(p4, "alice", "fire", 250, 1, alice)
    kid(p4, "bob", "fire", 210, 1, bob)
    body(p4, rival, "jump", 330, -1, GREEN, y=100, key="p2")
    blit_center(p4, outlined("MISS", 16, P.MIST, thick=2), (250, FLOOR_Y - 170))
    caption(p4, 0, "DODGE: BE OUT OF ITS 100 PX, OR IN THE AIR, WHEN IT STARTS")
    return sheet((p1, p2, p3, p4))


SHEETS = {
    "bloch_sphere": bloch_sheet,
    "wavefunction_collapse": collapse_sheet,
    "coherent_beam": beam_sheet,
    "nine_lives": nine_sheet,
    "dilution_fridge": fridge_sheet,
    "one_time_pad": otp_sheet,
}


def main(argv: list[str]) -> None:
    if len(argv) != 1:
        sys.exit(__doc__)
    os.makedirs(argv[0], exist_ok=True)
    for name, make in SHEETS.items():
        pygame.image.save(make(), os.path.join(argv[0], f"super_look_{name}.png"))


if __name__ == "__main__":
    main(sys.argv[1:])
