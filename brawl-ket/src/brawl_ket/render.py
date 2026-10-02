"""The 640x360 game: chunky GBA puppets on a quantum-lab stage, with the HUD,
the hit effects and the match's screens (title, select, round calls, result, pause).

The puppets are drawn from poses.joints() every frame as thick capsules with a
2 px ink outline (back limbs a darker shade, a highlight stripe on the torso,
a visor in the character's accent colour). Everything static, the lab wall,
the floor, the ring sprites and every piece of text, is drawn once and blitted,
so a frame costs well under 2 ms of CPU on the dev machine.

The renderer only reads the fight. Effects (sparks, pop-ups, the LOGICAL ERROR!
banner, the shake, the light flashes) are started by the frame's events and
timed in frames, advanced once per draw_fight call.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from functools import lru_cache

import pygame

from . import match as M
from . import palette as P
from . import shor
from .config import (
    FLOOR_Y,
    FPS,
    INTERNAL_HEIGHT,
    INTERNAL_WIDTH,
    MATCH_RESULT_LOCK,
    PLAYER_COLORS,
    ROUNDS_TO_WIN,
)
from .fight import Fight
from .fighter import TELEGRAPH_FRAMES, Fighter
from .fonts import load_font
from .moves import Character
from .poses import HEAD_R, LIMB_W, POSES, Pose, joints, pose_for

W, H = INTERNAL_WIDTH, INTERNAL_HEIGHT
MARGIN = 8                  # the stage is this much bigger on every side, for the shake
PLAYERS = ("p1", "p2")
ACCENT = {"TRIO": P.CREAM, "QUINT": P.GOLD}

# how each build is drawn (the skeleton's proportions are in poses.py)
TORSO_EXTRA = {"lean": 5, "heavy": 8}      # the lean torso is this much thicker than a limb
PLATES = {"lean": False, "heavy": True}    # armour: the heavy's wedge torso, plates, helm, gauntlets
# the heavy's wedge torso: half its width (px) at the shoulders, the waist and the belt
CHEST_HALF, WAIST_HALF, BELT_HALF = 21, 13, 14

DANGER_BEAT = 24            # frames in one pulse of the danger cells and rows
GLINT_BEAT = 2              # frames per blink phase of the telegraph glint on a heavy's wind-up
GLINT_MIN, GLINT_MAX = 8, 16    # the star's reach in px: it grows as the strike gets closer
TAG_ABOVE_HEAD = 46         # the grid sits this far above the head's centre
RING_STEPS = 24             # pre-drawn cycle-ring sprites
RING_R = 7                  # the ring's radius, px
CELL, CELL_GAP = 6, 3       # a grid cell and the gap between cells, px
GRID = 3 * CELL + 2 * CELL_GAP              # 24: the 3x3 grid
PLATE = GRID + 8                            # the plate around it
TAG_HALF = PLATE / 2 + 2 + 2 * RING_R + 1   # half a tag's width: the plate, then the ring
BAR_W, BAR_H, BAR_Y = 250, 12, 14

# effect lengths, in frames
SPARK_FRAMES = 10
POPUP_FRAMES = 40
BANNER_FRAMES = 75
SHAKE_FRAMES = 20
SHAKE_PX = 6
FLASH_FRAMES = 24           # the grid after a correction (green) or a logical error (red)
WAVE_FRAMES = 18            # a landing shockwave's rings spreading along the floor
WAVE_REACH = 50             # px either side they spread to (COLLAPSE's shockwave box is 45)
PULSE_FRAMES = 20           # RE-ENCODE: a ring of light growing out of the fighter
HIT_FLASH_FRAMES = 3        # the body flashes pale on the first frames of a hit
TRAIL_DELAY = 20            # the damage trail waits this long, then drains
TRAIL_SPEED = 0.6           # health per frame
TAG_FOLLOW = 0.3            # the grid eases towards the head by this much per frame
TAG_EDGE = 4                # a tag keeps this far from the screen's edges
BANNER_Y = 80
BANNER_TEXT = "LOGICAL ERROR!"
CALL_Y = 150                # the round calls (ROUND 1, FIGHT!, K.O., ...) are centred here
BLINK = 40                  # frames per on/off cycle of a "PRESS START" prompt

# the select screen: what each fighter is, in a line, and how its X moves are entered
TRAITS = {"TRIO": "FAST AND LIGHT", "QUINT": "SLOW AND HEAVY"}
X_INPUTS = (("stand.X", "X"), ("crouch.X", "DOWN+X"), ("air.X", "AIR X"))

WALL = (40, 32, 80)
WALL_TILE = (48, 40, 96)
RACK = (56, 48, 112)
RACK_SLOT = (88, 80, 152)
FLOOR_TOP = (72, 64, 128)
FLOOR_TILE = (56, 48, 104)
FLOOR_SHINE = (96, 88, 160)
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


def draw_puppet(surf: pygame.Surface, pose, build: str, feet, facing: int, body, accent) -> dict:
    """One fighter, back limbs first. Returns the joints (screen px)."""
    j = joints(pose, build, feet, facing)
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


# --- static art ----------------------------------------------------------------------------------


def make_stage() -> tuple[pygame.Surface, list[tuple[pygame.Rect, tuple]]]:
    """The lab, MARGIN px bigger than the screen on every side. Also returns the racks'
    status lights, which blink on top of it."""
    m = MARGIN
    surf = pygame.Surface((W + 2 * m, H + 2 * m))
    surf.fill(WALL)
    floor = FLOOR_Y + m
    for y in range(0, floor, 16):              # the tiled wall
        for x in range(-(y // 16 % 2) * 16, W + 2 * m, 32):
            surf.fill(WALL_TILE, (x, y, 30, 14))
    lights: list[tuple[pygame.Rect, tuple]] = []
    for i, x in enumerate(range(40 + m, W + m, 120)):     # racks of qubit chips
        rack = pygame.Rect(x, 82 + m, 60, 172)
        pygame.draw.rect(surf, P.INK, rack.inflate(4, 4), border_radius=5)
        pygame.draw.rect(surf, RACK, rack, border_radius=4)
        surf.fill(P.lighten(RACK, 0.15), (rack.x + 4, rack.y + 2, rack.w - 8, 2))
        for k in range(5):
            slot = pygame.Rect(rack.x + 8, rack.y + 14 + k * 30, 44, 8)
            surf.fill(P.INK, slot.inflate(2, 2))
            surf.fill(P.GOLD if (i + k) % 3 == 0 else RACK_SLOT, slot)
            for q in range(3):                  # status lights under each chip
                spot = pygame.Rect(slot.x + 4 + q * 7, slot.bottom + 5, 4, 3)
                surf.fill(P.INK, spot.inflate(2, 2))
                lights.append((spot.move(-m, -m), (P.GOOD, P.SKY, P.GOLD)[(i + k + q) % 3]))
        # a cable down to the floor
        pygame.draw.line(surf, P.INK, (rack.centerx, rack.bottom), (rack.centerx, floor), 3)
    pygame.draw.line(surf, P.shade(WALL, 0.8), (0, floor - 18), (W + 2 * m, floor - 18), 2)
    surf.fill(P.INK, (0, floor - 4, W + 2 * m, H + 2 * m - floor + 4))
    for x in range(-16, W + 2 * m, 32):     # the chip-tile floor
        pygame.draw.rect(surf, FLOOR_TOP, (x + 1, floor - 2, 30, 14))
        surf.fill(FLOOR_SHINE, (x + 3, floor, 26, 2))
        pygame.draw.rect(surf, FLOOR_TILE, (x + 1, floor + 14, 30, H + 2 * m - floor - 14))
        surf.fill(P.shade(FLOOR_TILE, 0.8), (x + 13, floor + 22, 6, 6))
    return surf, lights


def make_ring(k: float) -> pygame.Surface:
    """The cycle ring at progress k: a dark disc with a pie of white filling clockwise."""
    s = pygame.Surface((2 * RING_R + 1, 2 * RING_R + 1), pygame.SRCALPHA)
    c = (RING_R, RING_R)
    pygame.draw.circle(s, P.INK, c, RING_R)
    pygame.draw.circle(s, P.SLATE, c, 5)
    if k > 0:
        pts = [c] + [(c[0] + 5.5 * math.sin(2 * math.pi * k * i / 12), c[1] - 5.5 * math.cos(2 * math.pi * k * i / 12))
                     for i in range(13)]
        pygame.draw.polygon(s, P.WHITE, pts)
    pygame.draw.circle(s, P.INK, c, 2)
    return s


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
        stage, self.lights = make_stage()
        try:
            self.stage = stage.convert(surface)     # the same pixel format: the cheapest blit
        except pygame.error:    # no display (a headless benchmark on the cabinet, whose SDL has
            self.stage = stage  # no dummy driver): both are plain surfaces in the default format
        self.rings = [make_ring(i / RING_STEPS) for i in range(RING_STEPS + 1)]
        self.dim = pygame.Surface((W, H), pygame.SRCALPHA)     # darkens the game under a menu
        self.dim.fill((*P.INK, 150))
        self.bands: dict[int, pygame.Surface] = {}
        self.effects: list[Effect] = []
        self.shake = 0              # frames of shake left
        self.t = 0                  # frames drawn
        self.show_boxes = False     # debug: hurtboxes and live hitboxes
        self._fight: Fight | None = None
        self._reset()
        # render the effects' text now, so the first hit doesn't stall a frame
        for e in (shor.X, shor.Y, shor.Z):
            outlined(f"{e}!", 16, P.GATE[e], thick=2)
        outlined("I", 16, P.WHITE, thick=2)
        outlined(BANNER_TEXT, 32, P.BAD, thick=2)

    def _reset(self) -> None:
        self.trail = {p: 0.0 for p in PLAYERS}          # the damage trail on each bar
        self.trail_wait = {p: 0 for p in PLAYERS}
        self.last_health = {p: 0.0 for p in PLAYERS}
        self.tag_y: dict[str, float | None] = {p: None for p in PLAYERS}
        self.pose_seen: dict[str, tuple] = {p: (None, 0) for p in PLAYERS}
        self.pose_start: dict[str, Pose | None] = {p: None for p in PLAYERS}
        self.pose_last: dict[str, Pose | None] = {p: None for p in PLAYERS}
        self.flash = {p: (None, 0) for p in PLAYERS}    # (colour, frames left) on the lights
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
            self._shadow(fight.fighters[p], ox, oy)
        heads = {}
        for p in order:
            heads[p] = self._fighter(p, fight.fighters[p], ox, oy)
        for s in fight.shots:
            self._shot(s, ox, oy)
        if self.show_boxes:
            self._boxes(fight, ox, oy)
        self._draw_effects(ox, oy, world=True)
        tags = {p: self._tag_place(p, fight.fighters[p], heads[p]) for p in PLAYERS}
        self._separate(tags, fight)
        for p in PLAYERS:
            self._code_tag(p, fight.fighters[p], tags[p], ox, oy)
        self._hud(fight, wins)
        self._draw_effects(0, 0, world=False)
        self._advance()

    # --- effects ----------------------------------------------------------------------------

    def _start_effects(self, events: list) -> None:
        for e in events:
            if e.kind in ("hit", "logical", "cancel"):
                color = P.WHITE if e.kind == "cancel" else P.GATE.get(e.error or "X", P.WHITE)
                text = "I" if e.kind == "cancel" else f"{e.error}!"
                self.effects.append(Effect("spark", e.x, e.y, SPARK_FRAMES, SPARK_FRAMES, color))
                self.effects.append(Effect("popup", e.x, e.y - 18, POPUP_FRAMES, POPUP_FRAMES, color, text))
            if e.kind == "logical":
                self.effects = [fx for fx in self.effects if fx.kind != "banner"]
                self.effects.append(Effect("banner", W / 2, BANNER_Y, BANNER_FRAMES, BANNER_FRAMES, P.BAD,
                                           BANNER_TEXT))
                self.shake = SHAKE_FRAMES
                if e.player:
                    self.flash[e.player] = (P.BAD, FLASH_FRAMES)
            elif e.kind == "corrected" and e.player:
                self.flash[e.player] = (P.GOOD, FLASH_FRAMES)
            elif e.kind == "shockwave":
                color = P.GATE.get(e.error or "Z", P.WHITE)
                self.effects.append(Effect("wave", e.x, e.y, WAVE_FRAMES, WAVE_FRAMES, color))
                self.shake = max(self.shake, SHAKE_FRAMES // 2)
            elif e.kind == "reencode" and e.player and self._fight is not None:
                f = self._fight.fighters[e.player]
                self.flash[e.player] = (P.WHITE, FLASH_FRAMES)
                self.effects.append(Effect("pulse", f.x, FLOOR_Y - f.y, PULSE_FRAMES, PULSE_FRAMES, P.SKY))

    def _advance(self) -> None:
        for fx in self.effects:
            fx.left -= 1
        self.effects = [fx for fx in self.effects if fx.left > 0]
        self.shake = max(0, self.shake - 1)
        for p in PLAYERS:
            color, left = self.flash[p]
            self.flash[p] = (color, left - 1) if left > 1 else (None, 0)

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
            elif world and fx.kind == "pulse":
                k = age / fx.life
                rect = pygame.Rect(0, 0, round(40 + 80 * k), round(60 + 120 * k))
                rect.midbottom = (round(fx.x) + ox, round(fx.y) + 6 + oy)
                width = 3 if k < 0.5 else 2 if k < 0.8 else 1
                pygame.draw.ellipse(surf, P.INK, rect.inflate(2, 2), width + 2)
                pygame.draw.ellipse(surf, fx.color if age % 4 < 2 else P.WHITE, rect, width)
            elif world and fx.kind == "popup":
                if fx.left < 10 and fx.left % 4 < 2:
                    continue
                rise = min(age, 12) * 1.2 + age * 0.15
                blit_center(surf, outlined(fx.text, 16, fx.color, thick=2), (fx.x + ox, fx.y + oy - rise))
            elif not world and fx.kind == "banner":
                if fx.left < 16 and fx.left % 4 < 2:
                    continue
                bounce = (6 - age) * 3 if age < 6 else 0
                blit_center(surf, outlined(fx.text, 32, fx.color, thick=2), (fx.x, fx.y - bounce))

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

    def _shadow(self, f: Fighter, ox: int, oy: int) -> None:
        w = max(18, 52 - f.y * 0.2)
        rect = pygame.Rect(0, 0, round(w), 8)
        rect.center = (round(f.x) + ox, FLOOR_Y + 2 + oy)
        pygame.draw.ellipse(self.surface, SHADOW, rect)

    def _fighter(self, key: str, f: Fighter, ox: int, oy: int) -> tuple[float, float]:
        body = PLAYER_COLORS[key]
        accent = ACCENT.get(f.char.name, P.CREAM)
        if f.action in ("hitstun", "knockdown") and f.frame < HIT_FLASH_FRAMES:
            body, accent = P.lighten(body, 0.6), P.WHITE
        feet = (f.x + ox, FLOOR_Y - f.y + oy)
        j = draw_puppet(self.surface, self._pose(key, f), f.char.build, feet, f.facing, body, accent)
        if f.telegraphing and (f.frame // GLINT_BEAT) % 2 == 0:
            self._glint(f, j)
        return j["head"][0] - ox, j["head"][1] - oy

    def _glint(self, f: Fighter, j: dict) -> None:
        """A blinking 4-point white star on the striking hand (the foot, for a sweep), in the
        last frames of a neutral heavy's wind-up: the cue that the strike is coming."""
        cx, cy = _pt(j["foot_f" if f.slot == "crouch.B" else "hand_f"])
        left = f.startup - f.frame                    # frames until impact (16 .. 1)
        r = GLINT_MIN + round((GLINT_MAX - GLINT_MIN) * (1 - left / TELEGRAPH_FRAMES))
        waist = max(2, r // 3)
        star = [(cx, cy - r), (cx + waist, cy - waist), (cx + r, cy), (cx + waist, cy + waist),
                (cx, cy + r), (cx - waist, cy + waist), (cx - r, cy), (cx - waist, cy - waist)]
        pygame.draw.polygon(self.surface, P.INK, star, 3)
        pygame.draw.polygon(self.surface, P.WHITE, star)

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
        color = P.GATE["X"]
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

    def _tag_place(self, key: str, f: Fighter, head) -> list[float]:
        """Where a fighter's code tag goes: over the head, easing after it vertically."""
        target = max(70.0, head[1] - TAG_ABOVE_HEAD)
        y = self.tag_y[key]
        y = target if y is None else y + (target - y) * TAG_FOLLOW
        self.tag_y[key] = y
        lo, hi = TAG_HALF + TAG_EDGE, W - TAG_HALF - TAG_EDGE
        return [min(max(head[0], lo), hi), y, head[0]]     # x, y, the head's x

    @staticmethod
    def _separate(tags: dict[str, list[float]], fight: Fight) -> None:
        """Two tags never overlap across, however far apart vertically (each code's tag has
        its own width): each moves out to its own fighter's side, and both stay on screen
        (at a wall too)."""
        a, b = tags["p1"], tags["p2"]
        f1, f2 = fight.fighters["p1"], fight.fighters["p2"]
        ha = hb = TAG_HALF
        need = ha + hb
        if abs(a[0] - b[0]) >= need:
            return
        if f2.x != f1.x:
            side = 1 if f2.x > f1.x else -1     # p2 stands on this side of p1
        else:
            side = 1 if b[0] >= a[0] else -1
        left_half, right_half = (ha, hb) if side > 0 else (hb, ha)
        mid = (a[0] + b[0]) / 2
        mid = min(max(mid, left_half + TAG_EDGE + need / 2), W - right_half - TAG_EDGE - need / 2)
        a[0], b[0] = mid - side * need / 2, mid + side * need / 2

    def _code_tag(self, key: str, f: Fighter, at, ox: int, oy: int) -> None:
        """The code over the head: a 3x3 grid (rows HIGH, MID, LOW; columns A, B, THROW)
        on a plate in the player's colour, and the cycle ring beside it.

        An X lights its cell in the X gate's red; a row flipped by a Z glows behind in the
        Z gate's blue (its cells drop their ink outline, so the blue fills the gaps; a Z-danger row's
        orange backing does the same on the beat). Danger pulses orange: the other cells of a row holding one X (a
        different button there breaks the code), or the other rows once one is flipped
        (a special there breaks it)."""
        code = f.code
        surf = self.surface
        cx, cy = round(at[0]) + ox, round(at[1]) + oy
        color = PLAYER_COLORS[key]
        plate = pygame.Rect(0, 0, PLATE, PLATE)
        plate.center = (cx, cy)
        tick = min(max(round(at[2] + ox), plate.left + 4), plate.right - 4)
        pygame.draw.polygon(surf, P.INK, ((tick - 5, plate.bottom), (tick + 5, plate.bottom), (tick, plate.bottom + 6)))
        pygame.draw.polygon(surf, color, ((tick - 3, plate.bottom), (tick + 3, plate.bottom), (tick, plate.bottom + 3)))
        pygame.draw.rect(surf, P.INK, plate.inflate(2, 2), border_radius=5)
        pygame.draw.rect(surf, color, plate, border_radius=4)
        pygame.draw.rect(surf, P.NIGHT, plate.inflate(-4, -4), border_radius=3)
        flash, left = self.flash[key]
        lit = flash is not None and left % 6 >= 2
        beat = (self.t // (DANGER_BEAT // 2)) % 2 == 0
        x_danger, z_danger = code.x_danger_rows(), code.z_danger_rows()
        for row in range(3):
            y = plate.top + 4 + row * (CELL + CELL_GAP)
            backed = row in code.z_rows or (row in z_danger and beat)
            if row in code.z_rows:
                surf.fill(P.GATE[shor.Z], (plate.left + 2, y - 1, PLATE - 4, CELL + 2))
            elif backed:
                surf.fill(P.shade(P.ORANGE, 0.6), (plate.left + 2, y - 1, PLATE - 4, CELL + 2))
            for col in range(3):
                x = plate.left + 4 + col * (CELL + CELL_GAP)
                if lit:
                    c = flash
                elif (row, col) in code.x_cells:
                    c = P.GATE[shor.X]
                elif row in x_danger and beat:
                    c = P.ORANGE
                else:
                    c = P.SLATE
                if not backed:                  # a backed row's colour shows through its gaps
                    surf.fill(P.INK, (x - 1, y - 1, CELL + 2, CELL + 2))
                surf.fill(c, (x, y, CELL, CELL))
                surf.fill(P.lighten(c, 0.5), (x, y, 2, 2))
        ring = self.rings[min(RING_STEPS, int(code.progress * RING_STEPS))]
        blit_center(surf, ring, (plate.right + 2 + RING_R, cy))

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
                col = color or (P.GOOD if frac > 0.5 else P.GOLD if frac > 0.25 else P.BAD)
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
        events (hits, logical errors, ...) start the effects."""
        fight_events = [e for e in events if not isinstance(e, M.Cue)]
        state = match.state
        if state == M.TITLE:
            if match.attract is not None:
                self.draw_fight(match.attract, fight_events)
                self._attract_overlay()
            else:
                self._title()
        elif state == M.SELECT:
            self._select(match)
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
            draw_puppet(surf, POSES["idle"], char.build, (x, FLOOR_Y), facing, PLAYER_COLORS[key],
                        ACCENT.get(char.name, P.CREAM))
        self._band(32, 156)
        self._logo(72)
        blit_center(surf, outlined("SHOR CODE  VS  SHOR CODE", 8, P.MIST), (W / 2, 114))
        self._prompt("PRESS START", 138, P.GOLD)

    def _attract_overlay(self) -> None:
        self._band(H - 58, H)
        self._logo(H - 36, size=24)
        self._prompt("PRESS START", H - 12, P.GOLD)
        blit_center(self.surface, outlined("DEMO", 8, P.MIST), (W / 2, 64))

    def _select(self, match: M.Match) -> None:
        self._backdrop()
        self._call("CHOOSE YOUR CODE", P.WHITE, y=24, size=16)
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
        draw_puppet(surf, POSES["jab_hit" if ready else "idle"], char.build, (cx, floor), -side, color,
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
        lines = ("SHOR CODE  |0>_L", TRAITS.get(char.name, ""))
        for i, line in enumerate(lines):
            blit_center(surf, outlined(line, 8, P.MIST), (cx, floor + 40 + 12 * i))
        # the X moves: the buttons, then the names
        for i, (slot, how) in enumerate(X_INPUTS):
            y = floor + 70 + 12 * i
            surf.blit(outlined(how, 8, P.GOLD), (panel.x + 30, y))
            surf.blit(outlined(char.moves[slot].name, 8, P.WHITE), (panel.x + 118, y))
        if ready:
            self._stamp("READY!", (panel.right - 58, panel.y + 20), P.GOOD)

    def _stamp(self, text: str, center, color) -> None:
        img = outlined(text, 16, color, thick=2)
        box = img.get_rect(center=_pt(center)).inflate(12, 8)
        pygame.draw.rect(self.surface, P.INK, box, border_radius=4)
        pygame.draw.rect(self.surface, color, box, 2, border_radius=4)
        blit_center(self.surface, img, center)

    def _round_intro(self, match: M.Match) -> None:
        self._band(CALL_Y - 26, CALL_Y + 26)
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
