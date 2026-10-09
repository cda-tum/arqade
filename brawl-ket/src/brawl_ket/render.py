"""The 640x360 game: chunky GBA puppets on a quantum-lab stage, with the HUD,
the hit effects and the match's screens (title, select, round calls, result, pause).

The puppets are drawn from poses.joints() every frame as thick capsules with a
2 px ink outline (back limbs a darker shade, a highlight stripe on the torso,
a visor in the character's accent colour), the whole body in the colour of
its basis: green for the Z basis, purple for the X basis. Everything static,
the lab wall, the floor and every piece of text, is drawn once and blitted, so
a frame costs well under 2 ms of CPU on the dev machine.

The renderer only reads the fight. Effects (sparks, pop-ups, pings, the shake)
are started by the frame's events and timed in frames, advanced once per
draw_fight call.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from functools import lru_cache

import pygame

from . import match as M
from . import palette as P
from . import basis
from .config import (
    CARD_FRAMES,
    FLOOR_Y,
    FPS,
    INTERNAL_HEIGHT,
    INTERNAL_WIDTH,
    MATCH_RESULT_LOCK,
    PLAYER_COLORS,
    ROUNDS_TO_WIN,
    STAGE_NAMES,
    STAGES,
)
from .fight import Fight
from .fighter import Fighter
from .fonts import load_font
from .moves import Character
from .stages import MARGIN, make_stage
from .poses import BASE_BONES, HEAD_R, LIMB_W, POSES, SCALE, Pose, joints, pose_for

W, H = INTERNAL_WIDTH, INTERNAL_HEIGHT
PLAYERS = ("p1", "p2")
ACCENT = {"ROBERT": P.CREAM, "BOHR": P.GOLD, "PHOEBE": P.TEAL}

# how each build is drawn (the skeleton's proportions are in poses.py)
TORSO_EXTRA = {"lean": 5, "heavy": 8, "toy": 5}   # the lean torso is this much thicker than a limb
PLATES = {"lean": False, "heavy": True, "toy": False}   # armour: the heavy's wedge torso, plates, helm
# PHOEBE (the "toy" build): a scientist, not a puppet. Her neutral colours; the coat, the lining
# and her trousers are shades of her basis colour (docs/.../2026-10-09-brawl-ket-phoebe-design.md)
SKIN = (232, 176, 128)
HAIR = (88, 48, 40)
SHOE = (40, 32, 48)
SHIRT = P.WHITE
MAX_FLARE = 14              # px: how far her coat's hem can blow out behind her
# the heavy's wedge torso: half its width (px) at the shoulders, the waist and the belt
CHEST_HALF, WAIST_HALF, BELT_HALF = 21, 13, 14

BAR_W, BAR_H, BAR_Y = 236, 12, 14     # the bars leave room for the basis badges by the clock

# The bases' colours: a body is drawn in its basis's, an attack in the colour of the basis it
# changes (an X is green, a Z purple; a Y, a throw, both).
GREEN = (72, 200, 96)
PURPLE = (160, 88, 232)
BASIS_BODY = {basis.Z_BASIS: GREEN, basis.X_BASIS: PURPLE}
ERROR_COLOUR = {basis.X: GREEN, basis.Z: PURPLE, basis.Y: P.WHITE}
BADGE = {basis.Z_BASIS: "0/1", basis.X_BASIS: "+/-"}     # the basis's states, on the health bar
# the striking limb's joints, from the shoulder or hip out to the hand or foot that lands
STRIKE_LIMB = {"hand_f": ("shoulder_f", "elbow_f", "hand_f"), "foot_f": ("hip", "knee_f", "foot_f")}
TRAIL_LEN = 5               # a live strike's hand or foot leaves this many fading echoes
LEGEND_CHIP = 14            # the A / B colour chips under each health bar, px
LEGEND_W = 2 * LEGEND_CHIP + 4
# which joint lands each move's hit (its glow shows the attack's colour before contact)
STRIKER = {
    "jab": "hand_f", "heavy": "hand_f", "low jab": "hand_f", "sweep": "foot_f",
    "air jab": "hand_f", "jump-in": "foot_f", "throw": "hand_f",
    "PHOTON": "hand_f", "PHASE SLIDE": "foot_f", "HADAMARD DIVE": "foot_f",
    "MEASURE": "hand_f", "COLLAPSE": "foot_f",
    "LIGHT PILLAR": "hand_f", "LASER": "hand_f",
}

# effect lengths, in frames
SPARK_FRAMES = 10
POPUP_FRAMES = 40
PING_FRAMES = 16            # a wrong-colour hit: a ring bouncing off
SHAKE_FRAMES = 20
SHAKE_PX = 6
POPUP_ROOM = 40             # a new pop-up replaces any older one this close across (px)
WAVE_FRAMES = 18            # a landing shockwave's rings spreading along the floor
WAVE_REACH = 50             # px either side they spread to (COLLAPSE's shockwave box is 45)
HIT_FLASH_FRAMES = 3        # the body flashes pale on the first frames of a hit
SWITCH_FLASH_FRAMES = 8     # a switch (an H): the body flashes white as its colour changes
MEASURE_FLASH_FRAMES = 12   # MEASURE: the rival flashes in BOHR's colour as it collapses
COLLAPSE_FRAMES = 14        # ... with a ring closing in on it
TRAIL_DELAY = 20            # the damage trail waits this long, then drains
TRAIL_SPEED = 0.6           # health per frame
PREVIEW_W, PREVIEW_H = 320, 180     # CHOOSE YOUR STAGE's preview: the stage at half size
PREVIEW_Y = 148                     # ... centred here
CALL_Y = 150                # the round calls (ROUND 1, FIGHT!, K.O., ...) are centred here
BLINK = 40                  # frames per on/off cycle of a "PRESS START" prompt

# the select screen: what each fighter is, in a line, and how its X moves are entered
TRAITS = {"ROBERT": "FAST AND LIGHT", "BOHR": "SLOW AND HEAVY", "PHOEBE": "TALL AND TRICKY"}
X_INPUTS = (("stand.X", "X"), ("crouch.X", "DOWN+X"), ("air.X", "AIR X"))
RULE_LINES = ("A AND X: YOUR COLOUR, B: THE OTHER", "Y SWITCHES YOUR COLOUR")
HINT = "MATCH THEIR COLOUR TO HURT - Y SWITCHES"
# the title's COLOUR MUST MATCH card: three beats, each a line of (text, colour) parts
CARD_LINES = (
    (("GREEN", GREEN), (" HITS ", P.WHITE), ("GREEN", GREEN), (": HURTS", P.WHITE)),
    (("GREEN", GREEN), (" HITS ", P.WHITE), ("PURPLE", PURPLE), (": BOUNCES", P.WHITE)),
    (("Y", P.GOLD), (" SWITCHES YOUR COLOUR", P.WHITE)),
)

SHADOW = (32, 24, 64)


# --- text ------------------------------------------------------------------------------------

_FONTS: dict[int, pygame.font.Font] = {}


def font(size: int) -> pygame.font.Font:
    if size not in _FONTS:
        _FONTS[size] = load_font(size)
    return _FONTS[size]


@lru_cache(maxsize=512)
def outlined(text: str, size: int, color, outline=P.INK, thick: int = 1) -> pygame.Surface:
    """Text with a `thick` px outline and a drop shadow. Cached: blit it, never draw on it."""
    f = font(size)
    core = f.render(text, False, color)
    ink = f.render(text, False, outline)
    t = thick
    s = pygame.Surface((core.get_width() + 2 * t + 1, core.get_height() + 2 * t + 2), pygame.SRCALPHA)
    s.blit(ink, (t + 1, t + 2))
    for dx in range(-t, t + 1):
        for dy in range(-t, t + 1):
            s.blit(ink, (t + dx, t + dy))
    s.blit(core, (t, t))
    return s


def legend_colours(f) -> dict[str, tuple]:
    """The colour each of a fighter's buttons hits in now: A its own basis's, B the other's."""
    return {"A": BASIS_BODY[f.basis], "B": BASIS_BODY[basis.hadamard(f.basis)]}


def blit_center(surf: pygame.Surface, img: pygame.Surface, center) -> None:
    surf.blit(img, img.get_rect(center=(round(center[0]), round(center[1]))))


# --- the puppet --------------------------------------------------------------------------------


def _pt(p) -> tuple[int, int]:
    return (round(p[0]), round(p[1]))


def limb(surf: pygame.Surface, a, b, w: int, color, ink=P.INK) -> None:
    """A capsule from a to b, w px thick, with a 2 px ink outline."""
    a, b = _pt(a), _pt(b)
    for c, ww in ((ink, w + 4), (color, w)):
        pygame.draw.line(surf, c, a, b, ww)
        pygame.draw.circle(surf, c, a, ww // 2)
        pygame.draw.circle(surf, c, b, ww // 2)


def _ball(surf: pygame.Surface, p, r: int, color) -> None:
    p = _pt(p)
    pygame.draw.circle(surf, P.INK, p, r + 2)
    pygame.draw.circle(surf, color, p, r)


def draw_puppet(surf: pygame.Surface, pose, build: str, feet, facing: int, body, accent,
                flare: float = 0.0) -> dict:
    """One fighter, back limbs first. Returns the joints (screen px). `flare` (px) blows a
    coat's hem out behind (PHOEBE's; the puppets ignore it)."""
    j = joints(pose, build, feet, facing)
    if build == "toy":
        _draw_scientist(surf, j, pose, facing, body, accent, flare)
        return j
    if PLATES[build]:
        _draw_armoured(surf, j, build, facing, body, accent)
        return j
    w = LIMB_W[build]
    dark = P.shade(body, 0.65)
    # the back leg and arm, in shadow
    limb(surf, j["hip"], j["knee_b"], w + 1, dark)
    limb(surf, j["knee_b"], j["foot_b"], w, dark)
    limb(surf, j["shoulder_b"], j["elbow_b"], w - 1, dark)
    limb(surf, j["elbow_b"], j["hand_b"], w - 2, dark)
    _ball(surf, j["hand_b"], w // 2 + 1, P.shade(accent, 0.7))
    # the torso, with a highlight stripe down its front
    limb(surf, j["hip"], j["neck"], w + TORSO_EXTRA[build], body)
    hip, neck = j["hip"], j["neck"]
    tx, ty = neck[0] - hip[0], neck[1] - hip[1]
    n = math.hypot(tx, ty) or 1.0
    ox, oy = -ty / n * 3 * facing, tx / n * 3 * facing      # 3 px towards the front
    pygame.draw.line(surf, P.lighten(body, 0.4), _pt((hip[0] + ox + tx * 0.15, hip[1] + oy + ty * 0.15)),
                     _pt((neck[0] + ox - tx * 0.15, neck[1] + oy - ty * 0.15)), 2)
    # the front leg
    limb(surf, j["hip"], j["knee_f"], w + 1, body)
    limb(surf, j["knee_f"], j["foot_f"], w, body)
    # the head: a helmet with a visor on the facing side and a shine behind it
    hx, hy = _pt(j["head"])
    r = HEAD_R[build]
    pygame.draw.circle(surf, P.INK, (hx, hy), r + 2)
    pygame.draw.circle(surf, body, (hx, hy), r)
    visor = pygame.Rect(0, 0, r, 6)
    visor.midleft = (hx - 2, hy) if facing > 0 else (hx - r + 2, hy)
    surf.fill(accent, visor)
    surf.fill(P.lighten(accent, 0.6), (visor.x + (visor.w - 4 if facing > 0 else 1), visor.y + 1, 3, 2))
    pygame.draw.circle(surf, P.lighten(body, 0.5), (hx - 4 * facing, hy - 5), 3)
    # the front arm, in front of everything
    limb(surf, j["shoulder_f"], j["elbow_f"], w - 1, body)
    limb(surf, j["elbow_f"], j["hand_f"], w - 2, body)
    _ball(surf, j["hand_f"], w // 2 + 1, accent)
    return j


def _block(surf: pygame.Surface, p, half: int, color, radius: int = 3) -> None:
    """A square (a gauntlet), `half` px from its centre to each side, with a 2 px ink outline."""
    rect = pygame.Rect(0, 0, 2 * half, 2 * half)
    rect.center = _pt(p)
    pygame.draw.rect(surf, P.INK, rect.inflate(4, 4), border_radius=radius + 2)
    pygame.draw.rect(surf, color, rect, border_radius=radius)
    surf.fill(P.lighten(color, 0.5), (rect.x + 2, rect.y + 2, max(2, half - 2), 2))


def _boot(surf: pygame.Surface, foot, facing: int, w: int, color) -> None:
    """A heavy boot: a block on the foot, its toe pointing the way the fighter faces."""
    rect = pygame.Rect(0, 0, w + 10, w - 2)
    rect.midbottom = _pt((foot[0] + 3 * facing, foot[1] + w // 2 + 1))
    pygame.draw.rect(surf, P.INK, rect.inflate(4, 4), border_radius=4)
    pygame.draw.rect(surf, color, rect, border_radius=3)


def _draw_armoured(surf: pygame.Surface, j: dict, build: str, facing: int, body, accent) -> None:
    """The heavy build: thick limbs, a broad wedge torso with a chest plate and a belt,
    plates on both shoulders, gauntlets, boots and a flat-topped helm with a slit visor."""
    w = LIMB_W[build]
    dark = P.shade(body, 0.65)
    boot = P.shade(body, 0.45)
    metal = P.shade(accent, 0.85)
    # the back leg and arm, in shadow
    limb(surf, j["hip"], j["knee_b"], w + 4, dark)
    limb(surf, j["knee_b"], j["foot_b"], w + 2, dark)
    _boot(surf, j["foot_b"], facing, w, P.shade(boot, 0.8))
    limb(surf, j["shoulder_b"], j["elbow_b"], w, dark)
    limb(surf, j["elbow_b"], j["hand_b"], w - 1, dark)
    _block(surf, j["hand_b"], w // 2 + 1, P.shade(accent, 0.65))
    # the torso: a wedge, broad at the shoulders
    hip, neck, sh = j["hip"], j["neck"], j["shoulder_f"]
    tx, ty = neck[0] - hip[0], neck[1] - hip[1]
    n = math.hypot(tx, ty) or 1.0
    ux, uy = tx / n, ty / n                         # up the spine
    fx, fy = -uy * facing, ux * facing              # towards the front

    def at(base, up: float, front: float) -> tuple[float, float]:
        return (base[0] + ux * up + fx * front, base[1] + uy * up + fy * front)

    def wedge(pad: float) -> list[tuple[float, float]]:
        rows = ((neck, 4 + pad, CHEST_HALF - 5), (sh, 0, CHEST_HALF), (hip, 10, WAIST_HALF),
                (hip, -6 - pad, BELT_HALF))
        front = [at(b, up, half + pad) for b, up, half in rows]
        back = [at(b, up, -half - pad) for b, up, half in reversed(rows)]
        return front + back

    pygame.draw.polygon(surf, P.INK, wedge(2))
    pygame.draw.polygon(surf, body, wedge(0))
    # the chest plate, in a paler shade of the body, and a highlight down its front
    plate = [at(sh, 2, CHEST_HALF - 4), at(sh, -14, CHEST_HALF - 6), at(sh, -20, 2), at(sh, -14, -8),
             at(sh, 2, -8)]
    pygame.draw.polygon(surf, P.INK, plate, 2)
    pygame.draw.polygon(surf, P.lighten(body, 0.35), plate)
    pygame.draw.polygon(surf, P.INK, plate, 1)
    pygame.draw.line(surf, P.lighten(body, 0.6), _pt(at(sh, 0, CHEST_HALF - 7)),
                     _pt(at(sh, -11, CHEST_HALF - 8)), 2)
    # the belt, with a buckle in the accent colour
    pygame.draw.line(surf, P.INK, _pt(at(hip, 2, -BELT_HALF)), _pt(at(hip, 2, BELT_HALF)), 6)
    _block(surf, at(hip, 2, BELT_HALF - 7), 3, accent, radius=1)
    # the back shoulder plate, behind the arm's line
    _ball(surf, at(sh, 2, -CHEST_HALF + 6), w // 2 + 4, P.shade(metal, 0.7))
    # the front leg
    limb(surf, j["hip"], j["knee_f"], w + 4, body)
    limb(surf, j["knee_f"], j["foot_f"], w + 2, body)
    _boot(surf, j["foot_f"], facing, w, boot)
    # the front upper arm under a big shoulder plate, then the helm over the plate's top
    limb(surf, j["shoulder_f"], j["elbow_f"], w, body)
    _ball(surf, at(sh, -3, 4), w // 2 + 4, metal)
    pygame.draw.circle(surf, P.lighten(accent, 0.5), _pt(at(sh, 1, 1)), 3)
    # the helm: flat-topped, with a slit visor across its front and a crest
    hx, hy = _pt(j["head"])
    r = HEAD_R[build]
    helm = pygame.Rect(0, 0, 2 * r + 2, 2 * r)
    helm.center = (hx, hy)
    pygame.draw.rect(surf, P.INK, helm.inflate(4, 4), border_radius=8)
    pygame.draw.rect(surf, body, helm, border_radius=7)
    surf.fill(P.lighten(body, 0.45), (helm.x + 4 if facing > 0 else helm.right - 10, helm.y + 3, 6, 3))
    crest = pygame.Rect(0, 0, 6, 6)
    crest.midbottom = (hx - 3 * facing, helm.top + 2)
    pygame.draw.rect(surf, P.INK, crest.inflate(4, 2), border_radius=2)
    surf.fill(metal, crest)
    slit = pygame.Rect(0, 0, r + 6, 5)
    slit.midleft = (hx - 4, hy - 1) if facing > 0 else (hx - r - 2, hy - 1)
    surf.fill(P.INK, slit.inflate(2, 2))
    surf.fill(accent, slit)
    surf.fill(P.lighten(accent, 0.6), (slit.x + (slit.w - 5 if facing > 0 else 2), slit.y + 1, 3, 2))
    # the forearm and gauntlet, in front of everything
    limb(surf, j["elbow_f"], j["hand_f"], w - 1, body)
    _block(surf, j["hand_f"], w // 2 + 2, accent)


def _towards(a, b, k: float) -> tuple[float, float]:
    return (a[0] + (b[0] - a[0]) * k, a[1] + (b[1] - a[1]) * k)


def _poly(surf: pygame.Surface, pts, color, ink: int = 2) -> None:
    pts = [_pt(p) for p in pts]
    pygame.draw.polygon(surf, color, pts)
    pygame.draw.polygon(surf, P.INK, pts, ink)


def _shoe(surf: pygame.Surface, foot, facing: int) -> None:
    r = pygame.Rect(0, 0, 16, 7)
    r.midbottom = _pt((foot[0] + 4 * facing, foot[1] + 6))
    pygame.draw.rect(surf, P.INK, r.inflate(4, 4), border_radius=4)
    pygame.draw.rect(surf, SHOE, r, border_radius=3)


def _draw_scientist(surf: pygame.Surface, j: dict, pose, facing: int, coat, accent, flare: float) -> None:
    """PHOEBE: a long lab coat, open over a white shirt, almost to her ankles, in her basis
    colour; trousers a deep shade of it; white cuffs, a ponytail, round glasses. The coat is
    one shape with a single outline (no seams), and hangs by gravity, never through the floor."""
    lining = P.shade(coat, 0.5)
    legs = P.shade(coat, 0.6)
    w = LIMB_W["toy"]
    hip, neck, sh = j["hip"], j["neck"], j["shoulder_f"]
    tx, ty = neck[0] - hip[0], neck[1] - hip[1]
    n = math.hypot(tx, ty) or 1.0
    ux, uy = tx / n, ty / n                         # up the spine
    fx, fy = -uy * facing, ux * facing              # towards the front

    def at(base, up: float, front: float) -> tuple[float, float]:
        return (base[0] + ux * up + fx * front, base[1] + uy * up + fy * front)

    floor = max(j["foot_f"][1], j["foot_b"][1])
    leg = (BASE_BONES["thigh"] + BASE_BONES["shin"]) * SCALE["toy"]
    # the hem: just above the ankles; it spreads with the stride and flares out behind
    hem_y = min(hip[1] + 0.86 * leg, floor - 7)
    spread = abs(j["foot_f"][0] - j["foot_b"][0])
    back_x = min(hip[0] * facing, j["knee_b"][0] * facing) * facing - facing * (20 + 0.25 * spread + flare)
    front_x = hip[0] + facing * (8 + 0.2 * spread)
    hb = (back_x, hem_y + 2)
    hm = ((back_x + front_x) / 2, hem_y + 5)
    hf = (front_x, hem_y)
    # the inside of the coat, behind everything
    _poly(surf, [at(sh, 0, -12), at(hip, 6, -15), hb, hm, hf, at(hip, 10, 10), at(sh, 0, 10)], lining)
    # the back leg and arm, in shadow
    limb(surf, hip, j["knee_b"], w, P.shade(legs, 0.8))
    limb(surf, j["knee_b"], j["foot_b"], w - 1, P.shade(legs, 0.8))
    _shoe(surf, j["foot_b"], facing)
    dark = P.shade(coat, 0.7)
    limb(surf, j["shoulder_b"], j["elbow_b"], w + 1, dark)
    limb(surf, j["elbow_b"], j["hand_b"], w, dark)
    _ball(surf, _towards(j["elbow_b"], j["hand_b"], 0.82), 7, P.shade(SHIRT, 0.75))
    _ball(surf, j["hand_b"], 5, P.shade(SKIN, 0.8))
    # the shirt, then the front leg: the coat goes over both
    _poly(surf, [at(neck, 5, -7), at(neck, 5, 8), at(sh, 0, 12), at(hip, 6, 12), at(hip, 0, 10),
                 at(hip, 0, -12), at(sh, 0, -12)], SHIRT)
    limb(surf, hip, j["knee_f"], w, legs)
    limb(surf, j["knee_f"], j["foot_f"], w - 1, legs)
    _shoe(surf, j["foot_f"], facing)
    # the coat: its back panel and the front panel hanging open. Both outlines first, then
    # both fills, so only the silhouette keeps an ink line
    panels = [
        [at(neck, 3, -9), at(sh, 0, -14), at(hip, 6, -17), hb, hm,
         _towards(hm, hf, 0.45), at(hip, 14, 2), at(sh, 0, 6)],
        [at(neck, 2, -3), at(sh, 0, -2), at(hip, 12, 0), hf,
         _towards(hf, hm, 0.75), at(hip, 4, -10), at(sh, -8, -6), at(neck, 2, -8)],
    ]
    panels = [[_pt(q) for q in pts] for pts in panels]
    for pts in panels:
        pygame.draw.polygon(surf, P.INK, pts, 4)
    for pts in panels:
        pygame.draw.polygon(surf, coat, pts)
    # the head: hair and a ponytail swinging with her lean, the face, two round lenses
    hx, hy = _pt(j["head"])
    r = HEAD_R["toy"]
    swing = max(-6.0, min(10.0, pose.lean * 0.3)) + flare * 0.3
    tie = (hx - 9 * facing, hy - 9)
    limb(surf, tie, (hx - (19 + swing) * facing, hy - 3), 10, HAIR)
    limb(surf, (hx - (19 + swing) * facing, hy - 3), (hx - (21 + swing) * facing, hy + 9), 7, HAIR)
    pygame.draw.circle(surf, P.INK, (hx, hy), r + 2)
    pygame.draw.circle(surf, HAIR, (hx, hy), r)
    pygame.draw.circle(surf, SKIN, (hx + 4 * facing, hy + 3), r - 4)
    pygame.draw.circle(surf, P.lighten(HAIR, 0.45), (hx - 4 * facing, hy - 8), 3)
    pygame.draw.line(surf, P.INK, (hx - 3 * facing, hy + 2), (hx - 9 * facing, hy), 2)  # the glasses' arm
    for gx, rr in ((hx + 11 * facing, 4), (hx + 2 * facing, 5)):
        pygame.draw.circle(surf, P.INK, (gx, hy + 2), rr + 1)
        pygame.draw.circle(surf, P.lighten(accent, 0.6), (gx, hy + 2), rr - 1)
    surf.fill(P.WHITE, (hx + facing - 1, hy, 2, 2))
    # the front arm: sleeve, a big turned-back white cuff, hand
    limb(surf, j["shoulder_f"], j["elbow_f"], w + 1, coat)
    limb(surf, j["elbow_f"], j["hand_f"], w, coat)
    _ball(surf, _towards(j["elbow_f"], j["hand_f"], 0.8), 7, SHIRT)
    _ball(surf, j["hand_f"], 5, SKIN)


def tunnel_visibility(f: Fighter) -> float:
    """How much of a tunnelling fighter is drawn: 1 down to 0 as she dissolves, 0 while gone,
    then back up to 1 over the first part of re-forming."""
    m = f.move
    if f.frame < f.startup:
        return 1 - (f.frame + 1) / f.startup
    if f.frame < f.startup + m.active:
        return 0.0
    return min(1.0, (f.frame - f.startup - m.active + 1) / max(1, round(m.recovery * 0.6)))


# --- static art ----------------------------------------------------------------------------------


# --- effects -------------------------------------------------------------------------------------


@dataclass
class Effect:
    kind: str           # spark / popup / banner
    x: float
    y: float
    left: int           # frames still to show
    life: int
    color: tuple = P.WHITE
    text: str = ""


class Renderer:
    def __init__(self, surface: pygame.Surface) -> None:
        self.surface = surface
        self._stages: dict[str, tuple[pygame.Surface, list]] = {}
        self._previews: dict[str, pygame.Surface] = {}     # CHOOSE YOUR STAGE's, scaled once each
        self.preview_dim = pygame.Surface((PREVIEW_W, PREVIEW_H), pygame.SRCALPHA)
        self.preview_dim.fill((*P.INK, 110))                # under RANDOM's "?"
        self.stage_name = ""
        self.use_stage("lab")
        self.dim = pygame.Surface((W, H), pygame.SRCALPHA)     # darkens the game under a menu
        self.dim.fill((*P.INK, 150))
        self.ghost = pygame.Surface((200, 220), pygame.SRCALPHA)    # TUNNEL: a body to dissolve
        self.bands: dict[int, pygame.Surface] = {}
        self.effects: list[Effect] = []
        self.shake = 0              # frames of shake left
        self.t = 0                  # frames drawn
        self.show_boxes = False     # debug: hurtboxes and live hitboxes
        self._fight: Fight | None = None
        self._reset()
        # render the effects' text now, so the first hit doesn't stall a frame
        for e in (basis.X, basis.Y, basis.Z):
            outlined(f"{e}!", 16, ERROR_COLOUR[e], thick=2)

    def use_stage(self, name: str) -> None:
        """Fight in front of the named backdrop (stages.py). Each is drawn once, when first used."""
        if name == self.stage_name:
            return
        self.stage, self.lights = self._stage(name)
        self.stage_name = name

    def _stage(self, name: str) -> tuple[pygame.Surface, list]:
        if name not in self._stages:
            stage, lights = make_stage(name)
            try:
                stage = stage.convert(self.surface)     # the same pixel format: the cheapest blit
            except pygame.error:    # no display (a headless benchmark on the cabinet, whose SDL has
                pass                # no dummy driver): both are plain surfaces in the default format
            self._stages[name] = (stage, lights)
        return self._stages[name]

    def _preview(self, name: str) -> pygame.Surface:
        """The stage as the screen shows it (without the shake margin), at half size."""
        if name not in self._previews:
            view = self._stage(name)[0].subsurface((MARGIN, MARGIN, W, H))
            try:        # averaged, so the 1 px lines and windows don't drop out as they would
                small = pygame.transform.smoothscale(view, (PREVIEW_W, PREVIEW_H))
            except ValueError:      # smoothscale wants 24 or 32 bit pixels
                small = pygame.transform.scale(view, (PREVIEW_W, PREVIEW_H))
            self._previews[name] = small
        return self._previews[name]

    def _reset(self) -> None:
        self.trail = {p: 0.0 for p in PLAYERS}          # the damage trail on each bar
        self.trail_wait = {p: 0 for p in PLAYERS}
        self.last_health = {p: 0.0 for p in PLAYERS}
        self.pose_seen: dict[str, tuple] = {p: (None, 0) for p in PLAYERS}
        self.pose_start: dict[str, Pose | None] = {p: None for p in PLAYERS}
        self.pose_last: dict[str, Pose | None] = {p: None for p in PLAYERS}
        self.body_flash: dict[str, tuple[tuple | None, int]] = {p: (None, 0) for p in PLAYERS}
        self.trails: dict[str, list[tuple[tuple[int, int], tuple]]] = {p: [] for p in PLAYERS}
        self.legend_rects: dict[str, dict[str, pygame.Rect]] = {p: {} for p in PLAYERS}
        self.effects.clear()
        self.shake = 0

    # --- the frame -------------------------------------------------------------------------

    def draw_fight(self, fight: Fight, events: list, wins: dict[str, int] | None = None) -> None:
        if fight is not self._fight:
            self._fight = fight
            self._reset()
            for p in PLAYERS:
                self.trail[p] = self.last_health[p] = fight.fighters[p].health
        self.t += 1
        self._start_effects(events)

        surf = self.surface
        ox, oy = self._shake_offset()
        surf.blit(self.stage, (ox - MARGIN, oy - MARGIN))
        self._blink(ox, oy)

        order = sorted(PLAYERS, key=lambda p: fight.fighters[p].action == "attack")
        for p in PLAYERS:
            self._shadow(p, fight.fighters[p], ox, oy)
        heads = {}
        for p in order:
            heads[p] = self._fighter(p, fight.fighters[p], ox, oy)
        for s in fight.shots:
            self._shot(s, ox, oy)
        if self.show_boxes:
            self._boxes(fight, ox, oy)
        self._draw_effects(ox, oy, world=True)
        self._hud(fight, wins)
        self._draw_effects(0, 0, world=False)
        self._advance()

    # --- effects ----------------------------------------------------------------------------

    def _start_effects(self, events: list) -> None:
        older = [fx for fx in self.effects if fx.kind == "popup"]     # from earlier frames
        for e in events:
            if e.kind == "hit":
                color = ERROR_COLOUR.get(e.error or basis.X, P.WHITE)
                self.effects.append(Effect("spark", e.x, e.y, SPARK_FRAMES, SPARK_FRAMES, color))
                # the newest wins: an older pop-up still rising here would sit over this one
                stale = {id(fx) for fx in older if abs(fx.x - e.x) < POPUP_ROOM}
                if stale:
                    self.effects = [fx for fx in self.effects if id(fx) not in stale]
                self.effects.append(Effect("popup", e.x, e.y - 18, POPUP_FRAMES, POPUP_FRAMES, color,
                                           f"{e.error}!"))
            elif e.kind == "block":
                color = ERROR_COLOUR.get(e.error or basis.X, P.WHITE)
                self.effects.append(Effect("ping", e.x, e.y, PING_FRAMES, PING_FRAMES, color))
            elif e.kind == "switch" and e.player:
                self.body_flash[e.player] = (P.WHITE, SWITCH_FLASH_FRAMES)
                if self._fight is not None:
                    f = self._fight.fighters[e.player]
                    self.effects.append(Effect("popup", f.x, FLOOR_Y - f.y - 150, POPUP_FRAMES, POPUP_FRAMES,
                                               P.WHITE, "H"))
            elif e.kind == "measure" and e.player and self._fight is not None:
                f = self._fight.fighters[e.player]
                colour = P.lighten(BASIS_BODY[f.basis], 0.5)
                self.body_flash[e.player] = (colour, MEASURE_FLASH_FRAMES)
                self.effects.append(Effect("collapse", f.x, FLOOR_Y - f.y - 60, COLLAPSE_FRAMES,
                                           COLLAPSE_FRAMES, BASIS_BODY[f.basis]))
            elif e.kind == "fizzle":          # a LASER reaching the floor
                self.effects.append(Effect("spark", e.x, e.y - 3, SPARK_FRAMES // 2, SPARK_FRAMES // 2, P.WHITE))
            elif e.kind == "shockwave":
                color = ERROR_COLOUR.get(e.error or basis.Z, P.WHITE)
                self.effects.append(Effect("wave", e.x, e.y, WAVE_FRAMES, WAVE_FRAMES, color))
                self.shake = max(self.shake, SHAKE_FRAMES // 2)

    def _advance(self) -> None:
        for fx in self.effects:
            fx.left -= 1
        self.effects = [fx for fx in self.effects if fx.left > 0]
        self.shake = max(0, self.shake - 1)
        for p in PLAYERS:
            colour, left = self.body_flash[p]
            self.body_flash[p] = (colour, left - 1) if left > 1 else (None, 0)

    def _shake_offset(self) -> tuple[int, int]:
        if self.shake <= 0:
            return 0, 0
        a = SHAKE_PX * self.shake / SHAKE_FRAMES
        return round(a * math.sin(self.t * 2.9)), round(a * math.cos(self.t * 2.1) * 0.6)

    def _draw_effects(self, ox: int, oy: int, world: bool) -> None:
        surf = self.surface
        for fx in self.effects:
            age = fx.life - fx.left
            if world and fx.kind == "spark":
                cx, cy = fx.x + ox, fx.y + oy
                k = age / fx.life
                inner, outer = 4 + 10 * k, 10 + 10 * (1 - (1 - k) ** 2)
                width = 3 if k < 0.6 else 2
                for i in range(8):
                    ang = i * math.pi / 4 + 0.2
                    c, s = math.cos(ang), math.sin(ang)
                    length = outer * (1.0 if i % 2 == 0 else 0.6)
                    pygame.draw.line(surf, P.WHITE, (cx + c * inner * 0.5, cy + s * inner * 0.5),
                                     (cx + c * length, cy + s * length), width)
                if age < 4:
                    pygame.draw.circle(surf, P.WHITE, _pt((cx, cy)), 8 - age)
                    pygame.draw.circle(surf, fx.color, _pt((cx, cy)), 5 - age)
            elif world and fx.kind == "wave":
                self._wave(fx, age, ox, oy)
            elif world and fx.kind == "ping":
                # the attack bounces off: a ring in its colour springing out
                k = age / fx.life
                r = round(6 + 16 * (1 - (1 - k) ** 2))
                width = 3 if k < 0.5 else 2
                pygame.draw.circle(surf, P.INK, _pt((fx.x + ox, fx.y + oy)), r + 1, width + 2)
                pygame.draw.circle(surf, P.WHITE if age < 3 else fx.color, _pt((fx.x + ox, fx.y + oy)), r, width)
            elif world and fx.kind == "collapse":
                # MEASURE: a ring closing in on the rival, in the basis it collapsed into
                k = age / fx.life
                r = round(46 * (1 - k)) + 4
                pygame.draw.circle(surf, P.INK, _pt((fx.x + ox, fx.y + oy)), r + 1, 4)
                pygame.draw.circle(surf, fx.color, _pt((fx.x + ox, fx.y + oy)), r, 2)
            elif world and fx.kind == "popup":
                if fx.left < 10 and fx.left % 4 < 2:
                    continue
                rise = min(age, 12) * 1.2 + age * 0.15
                if fx.text == "Y!":         # a Y is both colours: green with a purple outline
                    img = outlined(fx.text, 16, GREEN, outline=PURPLE, thick=2)
                else:
                    img = outlined(fx.text, 16, fx.color, thick=2)
                blit_center(surf, img, (fx.x + ox, fx.y + oy - rise))

    def _wave(self, fx: Effect, age: int, ox: int, oy: int) -> None:
        """A landing shockwave: two flat rings racing out along the floor, with chips of
        the floor kicked up between them, in the colour of the error it deals."""
        surf = self.surface
        k = (age + 1) / fx.life
        cx, floor = round(fx.x) + ox, round(fx.y) + oy
        for lag, height in ((0.0, 22), (0.25, 14)):
            kk = max(0.0, k - lag) / (1 - lag)
            if kk <= 0:
                continue
            reach = round(14 + (WAVE_REACH - 14) * (1 - (1 - kk) ** 2))
            rect = pygame.Rect(0, 0, 2 * reach, height)
            rect.center = (cx, floor - 2)
            width = 4 if kk < 0.6 else 3 if kk < 0.85 else 2
            color = P.lighten(fx.color, 0.35) if lag == 0 else fx.color
            if lag == 0 and age < 3:
                color = P.WHITE                 # the impact flash
            pygame.draw.ellipse(surf, P.INK, rect.inflate(4, 4), width + 2)
            pygame.draw.ellipse(surf, color, rect, width)
        if k < 0.7:                     # the kicked-up floor chips, rising and falling
            for side in (-1, 1):
                for i, d in enumerate((18, 30, 42)):
                    x = cx + side * round(d * (0.4 + 0.6 * k))
                    y = floor - 6 - round(26 * math.sin(math.pi * min(1.0, k / 0.7)) * (1 - i * 0.25))
                    surf.fill(P.INK, (x - 2, y - 2, 5, 5))
                    surf.fill(P.WHITE if i == 0 else P.lighten(fx.color, 0.4), (x - 1, y - 1, 3, 3))

    # --- the world -----------------------------------------------------------------------------

    def _blink(self, ox: int, oy: int) -> None:
        """The racks' status lights: each blinks on its own slow beat."""
        for i, (rect, color) in enumerate(self.lights):
            on = (self.t // 16 + i * 7 + (i * i) % 5) % 9 < 6
            self.surface.fill(color if on else P.shade(color, 0.45), rect.move(ox, oy))

    def _shadow(self, key: str, f: Fighter, ox: int, oy: int) -> None:
        """The shadow, ringed in the player's colour (P1 blue, P2 red, as the cabinet's sides):
        who is who, now that the bodies are the colours of their bases. Gone in a TUNNEL."""
        if f.action == "attack" and f.move is not None and f.move.tunnel and tunnel_visibility(f) <= 0:
            return
        w = max(18, 52 - f.y * 0.2)
        rect = pygame.Rect(0, 0, round(w) + 8, 12)
        rect.center = (round(f.x) + ox, FLOOR_Y + 2 + oy)
        pygame.draw.ellipse(self.surface, SHADOW, rect)
        pygame.draw.ellipse(self.surface, P.INK, rect.inflate(2, 2), 3)
        pygame.draw.ellipse(self.surface, PLAYER_COLORS[key], rect, 2)

    def _fighter(self, key: str, f: Fighter, ox: int, oy: int) -> tuple[float, float]:
        body = BASIS_BODY[f.basis]
        accent = ACCENT.get(f.char.name, P.CREAM)
        flash, left = self.body_flash[key]
        if flash is not None and left % 4 >= 1:
            body, accent = flash, P.WHITE
        elif f.action in ("hitstun", "knockdown") and f.frame < HIT_FLASH_FRAMES:
            body, accent = P.lighten(body, 0.6), P.WHITE
        feet = (f.x + ox, FLOOR_Y - f.y + oy)
        pose = self._pose(key, f)
        # a long coat blows out behind her as she moves, and trails in a jump
        flare = min(MAX_FLARE, abs(f.vx) * 2.5 + (6 if f.y > 0 else 0))
        m = f.move
        if f.action == "attack" and m is not None and m.tunnel:
            self._tunnel_line(f, ox, oy)
            seen = tunnel_visibility(f)
            if seen < 1:
                j = self._dissolved(pose, f, feet, body, accent, flare, seen)
                return j["head"][0] - ox, j["head"][1] - oy
        j = draw_puppet(self.surface, pose, f.char.build, feet, f.facing, body, accent, flare)
        self._striker(key, f, j)
        if f.action == "attack" and m is not None and m.name == "LIGHT PILLAR":
            self._pillar(f, m, j, ox, oy)
        if f.action == "attack" and m is not None and m.projectile is not None and m.projectile.vy \
                and f.phase == "startup":
            self._laser_aim(f, j, oy)
        return j["head"][0] - ox, j["head"][1] - oy

    # --- PHOEBE's specials ------------------------------------------------------------------

    def _tunnel_line(self, f: Fighter, ox: int, oy: int) -> None:
        """TUNNEL's tell: from the first frame, a dotted line along the floor from where she
        dissolves to where she will re-form, and a ring on the floor there, in her colour."""
        if f.frame >= f.startup + f.move.active:
            return
        colour = BASIS_BODY[f.basis]
        y = FLOOR_Y + oy + 4
        a, b = sorted((f.tunnel_from, f.tunnel_to))
        march = (self.t // 2) % 8
        for x in range(round(a) + march, round(b), 8):
            self.surface.fill(P.INK, (x + ox - 1, y - 1, 6, 4))
            self.surface.fill(P.lighten(colour, 0.3), (x + ox, y, 4, 2))
        ring = pygame.Rect(0, 0, 40, 10)
        ring.center = (round(f.tunnel_to) + ox, y)
        pygame.draw.ellipse(self.surface, P.INK, ring.inflate(4, 4), 4)
        pygame.draw.ellipse(self.surface, P.lighten(colour, 0.4) if self.t // 4 % 2 else colour, ring, 2)

    def _dissolved(self, pose, f: Fighter, feet, body, accent, flare, seen: float) -> dict:
        """Her body as horizontal scanlines, `seen` of them shown (0: gone), each shifted
        sideways a little: dissolving into the tunnel, or re-forming out of it."""
        ghost = self.ghost
        ghost.fill((0, 0, 0, 0))
        gw, gh = ghost.get_size()
        local = (gw / 2, gh - 12)
        j = draw_puppet(ghost, pose, f.char.build, local, f.facing, body, accent, flare)
        if seen <= 0:
            return {k: (x - local[0] + feet[0], y - local[1] + feet[1]) for k, (x, y) in j.items()}
        left, top = round(feet[0] - local[0]), round(feet[1] - local[1])
        for row in range(0, gh, 2):
            if ((row // 2) * 7 + self.t) % 10 >= seen * 10:
                continue
            shift = round((1 - seen) * 10 * math.sin(row * 0.7 + self.t * 0.9))
            self.surface.blit(ghost, (left + shift, top + row), (0, row, gw, 2))
        return {k: (x - local[0] + feet[0], y - local[1] + feet[1]) for k, (x, y) in j.items()}

    def _pillar(self, f: Fighter, m, j: dict, ox: int, oy: int) -> None:
        """LIGHT PILLAR: in the wind-up, light gathers at her palms and a thin guide line
        flickers straight up; then a thick laser beam shoots up from her palms off the top of
        the screen, a white-hot core in the attack's colour, and thins out as it ends."""
        surf = self.surface
        colour = ERROR_COLOUR[basis.error_for(m.colour, f.attack_basis)]
        left, _, w, _ = f.world_box(m.hitbox)
        x = round(left + ox + w / 2)
        hands = _towards(j["hand_f"], j["hand_b"], 0.5)
        base = round(hands[1])
        if f.phase == "startup":
            k = (f.frame + 1) / f.startup
            if self.t % 3:
                pygame.draw.line(surf, P.lighten(colour, 0.5), (x, base), (x, 0), 1)
            r = round(3 + 7 * k)
            pygame.draw.circle(surf, P.INK, _pt(hands), r + 2)
            pygame.draw.circle(surf, P.lighten(colour, 0.3), _pt(hands), r)
            pygame.draw.circle(surf, P.WHITE, _pt(hands), max(1, r - 4))
            return
        age = f.frame - f.startup
        if f.phase == "active":
            width = 22 if age else 30                   # a flash as it fires
        else:                                           # thinning out in the recovery
            width = 22 - 5 * (age - m.active)
            if width <= 2:
                return
        reach = base if age else base // 2              # it shoots up off the screen
        top = base - reach - 4
        flick = self.t % 2
        pygame.draw.line(surf, P.INK, (x, base), (x, top), width + 4)
        pygame.draw.line(surf, P.lighten(colour, 0.3), (x, base), (x, top), width)
        pygame.draw.line(surf, colour, (x, base), (x, top), max(2, width - 8))
        pygame.draw.line(surf, P.WHITE if flick else P.lighten(colour, 0.8), (x, base), (x, top), max(1, width // 3))
        for i in range(4):                              # light racing up the beam
            y = base - ((age * 14 + i * 47) % max(1, base))
            surf.fill(P.WHITE, (x - width // 2 + 2, y, 2, 6))
            surf.fill(P.WHITE, (x + width // 2 - 4, y - 20, 2, 6))
        r = width // 3 + 3                              # the flare at her palms
        pygame.draw.circle(surf, P.INK, (x, base), r + 2)
        pygame.draw.circle(surf, P.lighten(colour, 0.5), (x, base), r)
        pygame.draw.circle(surf, P.WHITE, (x, base), r - 4)

    def _laser_aim(self, f: Fighter, j: dict, oy: int) -> None:
        """LASER: while she aims, a thin flickering line from her hand down and forward at 45
        degrees to the floor, where the beam will go, and light gathering at her hand."""
        colour = ERROR_COLOUR[basis.error_for(f.move.colour, f.attack_basis)]
        hx, hy = j["hand_f"]
        n = max(0.0, FLOOR_Y + oy - hy)
        end = (hx + f.facing * n, hy + n)
        if self.t % 4 < 3:
            pygame.draw.line(self.surface, P.lighten(colour, 0.5), _pt((hx, hy)), _pt(end), 1)
        r = 2 + round(4 * (f.frame + 1) / f.startup)
        pygame.draw.circle(self.surface, P.INK, _pt((hx, hy)), r + 2)
        pygame.draw.circle(self.surface, P.lighten(colour, 0.4), _pt((hx, hy)), r)

    def _striker(self, key: str, f: Fighter, j: dict) -> None:
        """The whole arm or leg an attack lands with is drawn in the attack's colour, from its
        wind-up to the end of its active frames, so a player sees before contact whether it
        will match; while it is live, its hand or foot leaves a fading trail. A throw (both
        colours) is green outlined in purple. A repeating field (CHARGE NOISE) crackles instead."""
        m = f.move
        trail = self.trails[key]
        if f.action != "attack" or m is None or f.phase not in ("startup", "active"):
            trail.clear()
            return
        if m.hit_every:
            trail.clear()
            self._charge_noise(f, m, j)
            return
        joint = STRIKER.get(m.name)
        if joint is None:
            trail.clear()
            return
        error = basis.error_for(m.colour, f.attack_basis)
        fill = GREEN if error == basis.Y else ERROR_COLOUR[error]
        edge = PURPLE if error == basis.Y else P.INK
        surf = self.surface
        w = LIMB_W[f.char.build]
        if f.phase == "active":         # the trail, oldest first, under the limb
            trail.append((_pt(j[joint]), fill))
            del trail[:-TRAIL_LEN]
            for n, (p, c) in enumerate(trail[:-1]):
                r = 3 + n * 2
                pygame.draw.circle(surf, P.INK, p, r + 1)
                pygame.draw.circle(surf, P.lighten(c, 0.5), p, r)
        else:
            trail.clear()
        a, b, c = (j[name] for name in STRIKE_LIMB[joint])
        limb(surf, a, b, w, fill, ink=edge)
        limb(surf, b, c, w - 1, fill, ink=edge)
        tip = _pt(c)
        r = w // 2 + (4 if f.phase == "active" else 2)
        pygame.draw.circle(surf, edge, tip, r + 2)
        pygame.draw.circle(surf, fill, tip, r)
        pygame.draw.circle(surf, P.lighten(fill, 0.5), (tip[0] - 2, tip[1] - 2), max(2, r // 3))

    def _charge_noise(self, f: Fighter, m, j: dict) -> None:
        """CHARGE NOISE: jagged arcs crackling out from the body to the edge of the field, in
        the field's colour; in the wind-up only a few short sparks, then the field's full reach
        (its hitbox) flickering, with a bright ring on each shock's frame."""
        surf = self.surface
        colour = ERROR_COLOUR[basis.error_for(m.colour, f.attack_basis)]
        box = m.hitbox
        cx = round(f.x)
        cy = round(FLOOR_Y - f.y - box.h / 2)
        reach = box.w / 2
        active = f.phase == "active"
        n = 7 if active else 3
        seed = f.frame // 2                         # the arcs re-form every other frame
        for i in range(n):
            ang = (i * 2.4 + seed * 1.3 + (i * seed) % 3) % (2 * math.pi)
            length = (reach if active else reach * 0.4) * (0.75 + 0.25 * ((i * 7 + seed) % 4) / 3)
            pts = [(cx, cy)]
            for k in range(1, 5):
                r = length * k / 4
                wob = ((i * 13 + k * 5 + seed * 3) % 9 - 4) * 2.2
                pts.append((cx + math.cos(ang) * r - math.sin(ang) * wob,
                            cy + math.sin(ang) * r * 0.8 + math.cos(ang) * wob))
            pts = [_pt(p) for p in pts]
            pygame.draw.lines(surf, P.INK, False, pts, 5)
            pygame.draw.lines(surf, colour, False, pts, 3)
            pygame.draw.lines(surf, P.lighten(colour, 0.6), False, pts, 1)
        if active:
            ring = pygame.Rect(0, 0, round(2 * reach), round(box.h))
            ring.center = (cx, cy)
            shock = (f.frame - f.startup) % m.hit_every == 0
            pygame.draw.ellipse(surf, P.lighten(colour, 0.5) if shock else colour, ring, 3 if shock else 1)

    def _pose(self, key: str, f: Fighter) -> Pose:
        """pose_for, told which pose the fighter was drawn in when its action began,
        so a cancel, a landing or a recovery into the stance blends instead of popping."""
        now = (f.action, f.slot, id(f.move))
        seen, frame = self.pose_seen[key]
        if now != seen or f.frame < frame:
            self.pose_start[key] = self.pose_last[key]
        self.pose_seen[key] = (now, f.frame)
        pose = pose_for(f, self.pose_start[key])
        self.pose_last[key] = pose
        return pose

    def _shot(self, s, ox: int, oy: int) -> None:
        left, top, w, h = s.box
        cx, cy = left + w / 2 + ox, top + h / 2 + oy
        color = ERROR_COLOUR[basis.error_for(s.move.colour, s.basis)]
        if s.vy:            # a LASER: a beam from where it left her hand to its head
            n = math.hypot(s.vx, s.vy) or 1.0
            dx, dy = s.vx / n, -s.vy / n
            flown = (s.move.projectile.lifetime - s.life) * n
            length = min(flown, 110.0)
            tail = (cx - dx * length, cy - dy * length)
            head = (cx + dx * 6, cy + dy * 6)
            pygame.draw.line(self.surface, P.INK, _pt(tail), _pt(head), 9)
            pygame.draw.line(self.surface, P.lighten(color, 0.3), _pt(tail), _pt(head), 7)
            pygame.draw.line(self.surface, color, _pt(_towards(tail, head, 0.15)), _pt(head), 4)
            pygame.draw.line(self.surface, P.WHITE, _pt(_towards(tail, head, 0.45)), _pt(head), 2)
            pygame.draw.circle(self.surface, P.INK, _pt(head), 6)
            pygame.draw.circle(self.surface, P.WHITE, _pt(head), 4)
            return
        back = -s.facing
        for i, r in ((3, 2), (2, 3), (1, 4)):       # the trail
            pygame.draw.circle(self.surface, P.shade(color, 0.5 + 0.12 * (3 - i)),
                               _pt((cx + back * (6 + i * 6), cy)), r)
        r = 7 + (self.t // 3) % 2
        pygame.draw.circle(self.surface, P.lighten(color, 0.45), _pt((cx, cy)), r + 2, 1)
        pygame.draw.circle(self.surface, P.INK, _pt((cx, cy)), r)
        pygame.draw.circle(self.surface, color, _pt((cx, cy)), r - 1)
        pygame.draw.circle(self.surface, P.lighten(color, 0.6), _pt((cx, cy)), r - 4)
        self.surface.fill(P.WHITE, (round(cx) - 2 - s.facing, round(cy) - 3, 2, 2))

    def _boxes(self, fight: Fight, ox: int, oy: int) -> None:
        for f in fight.fighters.values():
            pygame.draw.rect(self.surface, P.GOOD, pygame.Rect(f.hurtbox).move(ox, oy), 1)
            m = f.move
            if m is not None and m.hitbox is not None and f.phase == "active":
                pygame.draw.rect(self.surface, P.BAD, pygame.Rect(f.world_box(m.hitbox)).move(ox, oy), 1)
        for s in fight.shots:
            pygame.draw.rect(self.surface, P.BAD, pygame.Rect(s.box).move(ox, oy), 1)

    # --- the HUD -------------------------------------------------------------------------------

    def _hud(self, fight: Fight, wins: dict[str, int] | None) -> None:
        surf = self.surface
        for key, side in (("p1", -1), ("p2", 1)):
            f = fight.fighters[key]
            rect = pygame.Rect(0, BAR_Y, BAR_W, BAR_H)
            if side < 0:
                rect.left = 20
            else:
                rect.right = W - 20
            pygame.draw.rect(surf, P.INK, rect.inflate(4, 4), border_radius=3)
            frac = max(0.0, f.health / f.char.health)
            self._trail(key, f.health)
            for value, color in ((self.trail[key], P.WHITE), (f.health, None)):
                width = round(BAR_W * max(0.0, value / f.char.health))
                if width <= 0:
                    continue
                fill = pygame.Rect(rect.x, rect.y, width, BAR_H)
                if side > 0:
                    fill.right = rect.right
                col = color or (PLAYER_COLORS[key] if frac > 0.25 else P.lighten(PLAYER_COLORS[key], 0.4))
                pygame.draw.rect(surf, col, fill, border_radius=2)
                if color is None and fill.w > 4:
                    surf.fill(P.lighten(col, 0.5), (fill.x + 2, fill.y + 2, fill.w - 4, 2))
            name = outlined(f.char.name, 8, PLAYER_COLORS[key])
            tag = outlined(key.upper(), 8, P.MIST)
            y = rect.bottom + 6
            if side < 0:
                surf.blit(name, (rect.left + 2, y))
                surf.blit(tag, (rect.left + name.get_width() + 8, y))
            else:
                surf.blit(name, (rect.right - name.get_width() - 2, y))
                surf.blit(tag, (rect.right - name.get_width() - tag.get_width() - 8, y))
            self._badge(f, rect.right + 4 if side < 0 else rect.left - 4, rect.centery, side)
            if side < 0:
                lx = rect.left + name.get_width() + tag.get_width() + 20
            else:
                lx = rect.right - name.get_width() - tag.get_width() - 20 - LEGEND_W
            self._legend(key, f, lx, y)
        # the clock and the round pips
        cx = W // 2
        box = pygame.Rect(0, 0, 44, 30)
        box.midtop = (cx, 6)
        pygame.draw.rect(surf, P.INK, box, border_radius=5)
        pygame.draw.rect(surf, P.NIGHT, box.inflate(-4, -4), border_radius=4)
        secs = max(0, math.ceil(fight.frames_left / FPS))
        blit_center(surf, outlined(f"{secs:02d}", 16, P.GOLD if secs > 10 else P.BAD), (cx + 1, box.centery + 1))
        won = wins or {}
        for key, side in (("p1", -1), ("p2", 1)):
            for i in range(ROUNDS_TO_WIN):
                x = cx + side * (12 + i * 12)
                y = box.bottom + 8
                pygame.draw.circle(surf, P.INK, (x, y), 5)
                full = i < won.get(key, 0)
                pygame.draw.circle(surf, PLAYER_COLORS[key] if full else P.NIGHT, (x, y), 4)
                if full:
                    surf.fill(P.lighten(PLAYER_COLORS[key], 0.6), (x - 2, y - 2, 2, 2))

    def _legend(self, key: str, f: Fighter, x: int, y: int) -> None:
        """Which colour this player's buttons hit in right now: A their own, B the other."""
        rects = {}
        for i, (button, colour) in enumerate(legend_colours(f).items()):
            label = outlined(button, 8, P.WHITE)
            box = pygame.Rect(x + i * (LEGEND_CHIP + 4), y - 2, LEGEND_CHIP, 12)
            pygame.draw.rect(self.surface, P.INK, box.inflate(2, 2), border_radius=3)
            pygame.draw.rect(self.surface, colour, box, border_radius=2)
            blit_center(self.surface, label, box.center)
            rects[button] = box
        self.legend_rects[key] = rects

    def _badge(self, f: Fighter, x: int, cy: int, side: int) -> None:
        """The basis on the health bar: 0/1 on green or +/- on purple, at the bar's inner end."""
        colour = BASIS_BODY[f.basis]
        label = outlined(BADGE[f.basis], 8, P.WHITE)
        box = pygame.Rect(0, 0, label.get_width() + 8, 16)
        box.centery = cy
        if side < 0:
            box.left = x
        else:
            box.right = x
        pygame.draw.rect(self.surface, P.INK, box.inflate(4, 4), border_radius=4)
        pygame.draw.rect(self.surface, colour, box, border_radius=3)
        blit_center(self.surface, label, box.center)

    def _trail(self, key: str, health: float) -> None:
        """The white part of a bar: lost health, shown for a moment before it drains."""
        if health < self.last_health[key]:
            self.trail_wait[key] = 0            # fresh damage: hold the trail again
        self.last_health[key] = health
        if health >= self.trail[key]:
            self.trail[key] = health
            return
        if self.trail_wait[key] < TRAIL_DELAY:
            self.trail_wait[key] += 1
            return
        self.trail[key] = max(health, self.trail[key] - TRAIL_SPEED)

    # --- the match's screens -------------------------------------------------------------------

    def draw(self, match: M.Match, events: list) -> None:
        """The whole frame for the match's state. Cues are the match's own; the fight's
        events (hits, blocks, switches, ...) start the effects."""
        fight_events = [e for e in events if not isinstance(e, M.Cue)]
        self.use_stage(match.stage)
        state = match.state
        if state == M.TITLE:
            if match.card:
                self._rules_card(match)
            elif match.attract is not None:
                self.draw_fight(match.attract, fight_events)
                self._attract_overlay()
            else:
                self._title()
        elif state == M.SELECT:
            self._select(match)
        elif state == M.STAGE_SELECT:
            self._stage_select(match)
        else:
            self.draw_fight(match.fight, fight_events, match.wins)
            if state == M.ROUND_INTRO:
                self._round_intro(match)
            elif state == M.ROUND_END:
                self._round_end(match)
            elif state == M.MATCH_RESULT:
                self._match_result(match)
            if match.paused:
                self._pause(match)

    def _backdrop(self, dim: bool = True) -> None:
        """The lab, empty and still, as the menus' background."""
        self.t += 1
        self.surface.blit(self.stage, (-MARGIN, -MARGIN))
        self._blink(0, 0)
        if dim:
            self.surface.blit(self.dim, (0, 0))

    def _band(self, top: int, bottom: int) -> None:
        """A dark see-through strip across the screen, so text reads over the fight."""
        h = bottom - top
        if h not in self.bands:
            band = pygame.Surface((W, h), pygame.SRCALPHA)
            band.fill((*P.INK, 170))
            band.fill((*P.MIST, 120), (0, 0, W, 1))
            band.fill((*P.MIST, 120), (0, h - 1, W, 1))
            self.bands[h] = band
        self.surface.blit(self.bands[h], (0, top))

    def _call(self, text: str, color, y: float = CALL_Y, size: int = 32, age: int | None = None) -> None:
        """A big centred call. With `age` it drops in over its first frames."""
        drop = 0 if age is None or age >= 6 else (6 - age) * 4
        blit_center(self.surface, outlined(text, size, color, thick=2), (W / 2, y - drop))

    def _prompt(self, text: str, y: float, color=P.WHITE) -> None:
        if (self.t // (BLINK // 2)) % 2 == 0:
            blit_center(self.surface, outlined(text, 8, color), (W / 2, y))

    def _logo(self, center_y: float, size: int = 48) -> None:
        """BRAWL-KET: BRAWL in P1's blue, KET in P2's red, the cabinet's two sides."""
        left = outlined("BRAWL-", size, PLAYER_COLORS["p1"], thick=3)
        right = outlined("KET", size, PLAYER_COLORS["p2"], thick=3)
        x = (W - left.get_width() - right.get_width()) // 2
        y = round(center_y - left.get_height() / 2)
        self.surface.blit(left, (x, y))
        self.surface.blit(right, (x + left.get_width(), y))

    def _title(self) -> None:
        self._backdrop(dim=False)
        surf = self.surface
        for char, key, x, facing in ((M.ROSTER[0], "p1", 236, 1), (M.ROSTER[-1], "p2", 404, -1)):
            rect = pygame.Rect(0, 0, 52, 8)
            rect.center = (x, FLOOR_Y + 2)
            pygame.draw.ellipse(surf, SHADOW, rect)
            body = GREEN if key == "p1" else PURPLE
            draw_puppet(surf, POSES["idle"], char.build, (x, FLOOR_Y), facing, body,
                        ACCENT.get(char.name, P.CREAM))
        self._band(32, 156)
        self._logo(72)
        blit_center(surf, outlined("COLOUR MUST MATCH TO HURT", 8, P.MIST), (W / 2, 114))
        self._prompt("PRESS START", 138, P.GOLD)

    def _attract_overlay(self) -> None:
        self._band(H - 58, H)
        self._logo(H - 36, size=24)
        self._prompt("PRESS START", H - 12, P.GOLD)
        blit_center(self.surface, outlined("DEMO", 8, P.MIST), (W / 2, 64))

    def _select(self, match: M.Match) -> None:
        self._backdrop()
        self._call("CHOOSE YOUR FIGHTER", P.WHITE, y=24, size=16)
        for key, side in (("p1", -1), ("p2", 1)):
            self._select_panel(key, side, M.ROSTER[match.picks[key]], match.ready[key])
        blit_center(self.surface, outlined("STICK: CHOOSE   A: READY   B: BACK", 8, P.MIST), (W / 2, H - 12))

    def _select_panel(self, key: str, side: int, char: Character, ready: bool) -> None:
        surf = self.surface
        color = PLAYER_COLORS[key]
        cx = W / 2 + side * 156
        panel = pygame.Rect(0, 0, 296, 290)
        panel.center = (round(cx), 186)
        pygame.draw.rect(surf, P.INK, panel.inflate(4, 4), border_radius=8)
        pygame.draw.rect(surf, P.NIGHT, panel, border_radius=7)
        pygame.draw.rect(surf, color if ready else P.shade(color, 0.6), panel, 2, border_radius=7)
        surf.blit(outlined(key.upper(), 8, color), (panel.x + 8, panel.y + 8))
        # the fighter, facing the middle, flexing once ready
        floor = panel.y + 176
        rect = pygame.Rect(0, 0, 52, 8)
        rect.center = (round(cx), floor + 2)
        pygame.draw.ellipse(surf, SHADOW, rect)
        draw_puppet(surf, POSES["jab_hit" if ready else "idle"], char.build, (cx, floor), -side, GREEN,
                    ACCENT.get(char.name, P.CREAM))
        # the name between arrows (the arrows go once the pick is locked in)
        name = outlined(char.name, 16, color, thick=2)
        blit_center(surf, name, (cx, floor + 20))
        if not ready:
            nudge = 2 if (self.t // 15) % 2 else 0
            for d in (-1, 1):
                arrow = outlined("<" if d < 0 else ">", 16, P.WHITE, thick=2)
                blit_center(surf, arrow, (cx + d * (name.get_width() / 2 + 18 + nudge), floor + 20))
        # what it is: its code and its build
        lines = (TRAITS.get(char.name, ""), *RULE_LINES)
        for i, line in enumerate(lines):
            blit_center(surf, outlined(line, 8, P.MIST), (cx, floor + 36 + 11 * i))
        # the X moves: the buttons, the names, and the colour each one hits in
        for i, (slot, how) in enumerate(X_INPUTS):
            y = floor + 76 + 12 * i
            move = char.moves[slot]
            surf.blit(outlined(how, 8, P.GOLD), (panel.x + 14, y))
            surf.blit(outlined(move.name, 8, P.WHITE), (panel.x + 82, y))
            self._colour_chip(move, (panel.right - 12, y + 4))
        if ready:
            self._stamp("READY!", (panel.right - 58, panel.y + 20), P.GOOD)

    def _stage_select(self, match: M.Match) -> None:
        """CHOOSE YOUR STAGE: a big preview of the backdrop, its name between arrows, and a
        pip for each place in the list. RANDOM is a "?" over the stages, cycling once a second."""
        self._backdrop()
        surf = self.surface
        self._call("CHOOSE YOUR STAGE", P.WHITE, y=24, size=16)
        pick = M.STAGE_OPTIONS[match.stage_pick]
        random_pick = pick == M.RANDOM_STAGE
        shown = STAGES[(match.t // FPS) % len(STAGES)] if random_pick else pick
        frame = pygame.Rect(0, 0, PREVIEW_W, PREVIEW_H)
        frame.center = (W // 2, PREVIEW_Y)
        pygame.draw.rect(surf, P.INK, frame.inflate(12, 12), border_radius=8)
        pygame.draw.rect(surf, P.NIGHT, frame.inflate(8, 8), border_radius=7)
        pygame.draw.rect(surf, P.GOLD, frame.inflate(8, 8), 2, border_radius=7)
        surf.blit(self._preview(shown), frame)
        if random_pick:
            surf.blit(self.preview_dim, frame)
            blit_center(surf, outlined("?", 64, P.GOLD, thick=3), frame.center)
        # the name between arrows, as on CHOOSE YOUR FIGHTER
        name_y = frame.bottom + 28
        name = outlined("RANDOM" if random_pick else STAGE_NAMES[pick], 16, P.GOLD, thick=2)
        blit_center(surf, name, (W / 2, name_y))
        nudge = 2 if (self.t // 15) % 2 else 0
        for d in (-1, 1):
            arrow = outlined("<" if d < 0 else ">", 16, P.WHITE, thick=2)
            blit_center(surf, arrow, (W / 2 + d * (name.get_width() / 2 + 18 + nudge), name_y))
        # where in the list: a pip each, the picked one lit
        n = len(M.STAGE_OPTIONS)
        for i in range(n):
            pip = pygame.Rect(0, 0, 8, 8)
            pip.center = (round(W / 2 + (i - (n - 1) / 2) * 16), name_y + 24)
            pygame.draw.rect(surf, P.INK, pip.inflate(2, 2))
            pygame.draw.rect(surf, P.GOLD if i == match.stage_pick else P.SLATE, pip)
        blit_center(surf, outlined("STICK: CHOOSE   A: FIGHT!   B: BACK", 8, P.MIST), (W / 2, H - 12))

    def _colour_chip(self, move, right_mid) -> None:
        """The colour a move hits in, as a word: YOURS (your basis's), OTHER, or BOTH (a Y)."""
        text, fill, edge = {
            basis.GREEN: ("GREEN", GREEN, P.INK), basis.PURPLE: ("PURPLE", PURPLE, P.INK),
            basis.OWN: ("YOURS", P.WHITE, P.INK), basis.OPPOSITE: ("OTHER", P.WHITE, P.INK),
            basis.BOTH: ("BOTH", GREEN, PURPLE),
        }[move.colour]
        img = outlined(text, 8, fill, outline=edge)
        self.surface.blit(img, img.get_rect(midright=_pt(right_mid)))

    def _parts(self, parts, center) -> None:
        """A line of differently coloured parts, centred."""
        imgs = [outlined(text, 8, colour) for text, colour in parts]
        x = round(center[0] - sum(i.get_width() for i in imgs) / 2)
        for img in imgs:
            self.surface.blit(img, img.get_rect(midleft=(x, round(center[1]))))
            x += img.get_width()

    def _rules_card(self, match: M.Match) -> None:
        """COLOUR MUST MATCH: three beats of 3 s, each a tiny scene and its line (the others
        dim): a green jab hurting green, the same jab bouncing off purple, Y switching."""
        self._backdrop()
        surf = self.surface
        self._logo(34, size=24)
        self._call("COLOUR MUST MATCH", P.WHITE, y=74, size=16)
        beat_len = CARD_FRAMES // 3
        beat = min(2, match._title_phase // beat_len)
        k = (match._title_phase % beat_len) / beat_len
        floor = 236
        for x in (260, 380):
            rect = pygame.Rect(0, 0, 52, 8)
            rect.center = (x, floor + 2)
            pygame.draw.ellipse(surf, SHADOW, rect)
        if beat < 2:
            struck = k > 0.4
            j = draw_puppet(surf, POSES["jab_hit" if struck else "jab_wind"], "lean", (260, floor), 1, GREEN,
                            P.CREAM)
            fist = _pt(j["hand_f"])
            pygame.draw.circle(surf, P.INK, fist, 9)
            pygame.draw.circle(surf, P.lighten(GREEN, 0.5), fist, 8)
            pygame.draw.circle(surf, GREEN, fist, 6)
            target = GREEN if beat == 0 else PURPLE
            hurt = beat == 0 and struck
            draw_puppet(surf, POSES["hitstun" if hurt else "idle"], "lean", (380, floor), -1, target, P.CREAM)
            if struck and beat == 0:
                blit_center(surf, outlined("X!", 16, GREEN, thick=2), (380, floor - 150))
            elif struck:
                r = 8 + round(20 * min(1.0, (k - 0.4) / 0.3))
                pygame.draw.circle(surf, P.INK, fist, r + 1, 4)
                pygame.draw.circle(surf, GREEN, fist, r, 2)
        else:
            switched = k > 0.4
            white = 0.4 < k < 0.5
            colour = P.WHITE if white else PURPLE if switched else GREEN
            draw_puppet(surf, POSES["idle"], "lean", (320, floor), 1, colour, P.CREAM)
            if switched:
                blit_center(surf, outlined("H", 16, P.WHITE, thick=2), (320, floor - 150))
        for i, parts in enumerate(CARD_LINES):
            y = 274 + 18 * i
            if i == beat:
                self._parts(parts, (W / 2, y))
            else:
                text = "".join(t for t, _ in parts)
                blit_center(surf, outlined(text, 8, P.SLATE), (W / 2, y))
        self._prompt("PRESS START", H - 14, P.GOLD)

    def _stamp(self, text: str, center, color) -> None:
        img = outlined(text, 16, color, thick=2)
        box = img.get_rect(center=_pt(center)).inflate(12, 8)
        pygame.draw.rect(self.surface, P.INK, box, border_radius=4)
        pygame.draw.rect(self.surface, color, box, 2, border_radius=4)
        blit_center(self.surface, img, center)

    def _round_intro(self, match: M.Match) -> None:
        self._band(CALL_Y - 26, CALL_Y + (52 if match.hint else 26))
        if match.hint:
            blit_center(self.surface, outlined(HINT, 8, P.GOLD), (W / 2, CALL_Y + 38))
        if match.t < M.FIGHT_CALL:
            self._call(f"ROUND {match.round_no}", P.WHITE, age=match.t)
        else:
            self._call("FIGHT!", P.GOLD, age=match.t - M.FIGHT_CALL)

    def _round_end(self, match: M.Match) -> None:
        fight = match.fight
        winner = match.round_winner
        self._band(CALL_Y - 26, CALL_Y + (26 if winner is None else 80 if match.perfect else 54))
        if winner is None:
            self._call("DRAW", P.MIST, age=match.t)
            return
        ko = any(f.health <= 0 for f in fight.fighters.values())
        self._call("K.O." if ko else "TIME", P.BAD if ko else P.GOLD, age=match.t)
        if match.t >= FPS // 2:
            line = f"{fight.fighters[winner].char.name} WINS THE ROUND"
            blit_center(self.surface, outlined(line, 16, PLAYER_COLORS[winner], thick=2), (W / 2, CALL_Y + 36))
        if match.perfect and match.t >= FPS:
            self._call("PERFECT", P.GOLD, y=CALL_Y + 64, size=16, age=match.t - FPS)

    def _match_result(self, match: M.Match) -> None:
        self.surface.blit(self.dim, (0, 0))
        winner = match.winner
        self._band(CALL_Y - 48, CALL_Y + 76)
        name = match.fight.fighters[winner].char.name
        self._call(f"{winner.upper()} WINS!", PLAYER_COLORS[winner], y=CALL_Y - 20, age=match.t)
        blit_center(self.surface, outlined(f"{name}  {match.wins['p1']} - {match.wins['p2']}", 16, P.WHITE,
                                           thick=2), (W / 2, CALL_Y + 20))
        if match.t >= MATCH_RESULT_LOCK:
            self._prompt("A: REMATCH     B: TITLE", CALL_Y + 60, P.GOLD)

    def _pause(self, match: M.Match) -> None:
        surf = self.surface
        surf.blit(self.dim, (0, 0))
        box = pygame.Rect(0, 0, 220, 104)
        box.center = (W // 2, H // 2)
        pygame.draw.rect(surf, P.INK, box.inflate(4, 4), border_radius=8)
        pygame.draw.rect(surf, P.NIGHT, box, border_radius=7)
        pygame.draw.rect(surf, P.MIST, box, 2, border_radius=7)
        blit_center(surf, outlined("PAUSED", 16, P.WHITE, thick=2), (W / 2, box.y + 20))
        for i, item in enumerate(M.PAUSE_ITEMS):
            on = i == match.pause_index
            y = box.y + 50 + 18 * i
            blit_center(surf, outlined(item, 8, P.GOLD if on else P.MIST), (W / 2, y))
            if on:
                blit_center(surf, outlined(">", 8, P.GOLD), (W / 2 - 70, y))
        blit_center(surf, outlined("A: PICK   START: RESUME", 8, P.lighten(P.SLATE, 0.3)), (W / 2, box.bottom - 10))
