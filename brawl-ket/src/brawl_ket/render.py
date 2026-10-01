"""The 640x360 fight: chunky GBA puppets on a quantum-lab stage, with the HUD
and the hit effects.

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

from . import palette as P
from . import qec
from .config import (
    FLOOR_Y,
    FPS,
    INTERNAL_HEIGHT,
    INTERNAL_WIDTH,
    PLAYER_COLORS,
    ROUNDS_TO_WIN,
)
from .fight import Fight
from .fighter import Fighter
from .fonts import load_font
from .poses import HEAD_R, LIMB_W, Pose, joints, pose_for

W, H = INTERNAL_WIDTH, INTERNAL_HEIGHT
MARGIN = 8                  # the stage is this much bigger on every side, for the shake
PLAYERS = ("p1", "p2")
ACCENT = {"TRIO": P.CREAM, "QUINT": P.GOLD}

# how each build is drawn (the skeleton's proportions are in poses.py)
TORSO_EXTRA = {"lean": 5, "heavy": 8}      # the torso is this much thicker than a limb
PLATES = {"lean": False, "heavy": True}    # shoulder plates

LIGHT_GAP = 11
TAG_ABOVE_HEAD = 34         # the code lights sit this far above the head's centre
RING_STEPS = 24             # pre-drawn cycle-ring sprites
BAR_W, BAR_H, BAR_Y = 250, 12, 14

# effect lengths, in frames
SPARK_FRAMES = 10
POPUP_FRAMES = 40
BANNER_FRAMES = 75
SHAKE_FRAMES = 20
SHAKE_PX = 6
FLASH_FRAMES = 24           # the lights after a correction (green) or a logical error (red)
HIT_FLASH_FRAMES = 3        # the body flashes pale on the first frames of a hit
TRAIL_DELAY = 20            # the damage trail waits this long, then drains
TRAIL_SPEED = 0.6           # health per frame
TAG_FOLLOW = 0.3            # the code lights ease towards the head by this much per frame
TAG_W = 66                  # the width one code tag (ket, plate of lights and ring) needs
TAG_LO, TAG_HI = TAG_W / 2 + 4, W - TAG_W / 2 - 4   # where a tag's centre may go
BANNER_Y = 80
BANNER_TEXT = "LOGICAL ERROR!"

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
    if PLATES[build]:
        _ball(surf, j["shoulder_f"], w // 2 + 4, P.shade(accent, 0.85))
        pygame.draw.circle(surf, P.lighten(accent, 0.5), _pt((j["shoulder_f"][0] - 2 * facing, j["shoulder_f"][1] - 3)), 2)
    limb(surf, j["elbow_f"], j["hand_f"], w - 2, body)
    _ball(surf, j["hand_f"], w // 2 + 1, accent)
    return j


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
    s = pygame.Surface((15, 15), pygame.SRCALPHA)
    c = (7, 7)
    pygame.draw.circle(s, P.INK, c, 7)
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
        self.stage = stage.convert(surface)     # the same pixel format: the cheapest blit
        self.rings = [make_ring(i / RING_STEPS) for i in range(RING_STEPS + 1)]
        self.effects: list[Effect] = []
        self.shake = 0              # frames of shake left
        self.t = 0                  # frames drawn
        self.show_boxes = False     # debug: hurtboxes and live hitboxes
        self._fight: Fight | None = None
        self._reset()
        # render the effects' text now, so the first hit doesn't stall a frame
        for e in (qec.X, qec.Y, qec.Z):
            outlined(f"{e}!", 16, P.GATE[e], thick=2)
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
            if e.kind in ("hit", "logical"):
                color = P.GATE.get(e.error or "X", P.WHITE)
                self.effects.append(Effect("spark", e.x, e.y, SPARK_FRAMES, SPARK_FRAMES, color))
                self.effects.append(Effect("popup", e.x, e.y - 18, POPUP_FRAMES, POPUP_FRAMES, color,
                                           f"{e.error}!"))
            if e.kind == "logical":
                self.effects = [fx for fx in self.effects if fx.kind != "banner"]
                self.effects.append(Effect("banner", W / 2, BANNER_Y, BANNER_FRAMES, BANNER_FRAMES, P.BAD,
                                           BANNER_TEXT))
                self.shake = SHAKE_FRAMES
                if e.player:
                    self.flash[e.player] = (P.BAD, FLASH_FRAMES)
            elif e.kind == "corrected" and e.player:
                self.flash[e.player] = (P.GOOD, FLASH_FRAMES)

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
        return j["head"][0] - ox, j["head"][1] - oy

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
        target = max(62.0, head[1] - TAG_ABOVE_HEAD)
        y = self.tag_y[key]
        y = target if y is None else y + (target - y) * TAG_FOLLOW
        self.tag_y[key] = y
        return [min(max(head[0], TAG_LO), TAG_HI), y, head[0]]     # x, y, the head's x

    @staticmethod
    def _separate(tags: dict[str, list[float]], fight: Fight) -> None:
        """Two tags never sit closer than TAG_W across, however far apart vertically: each
        moves out to its own fighter's side, and both stay on screen (at a wall too)."""
        a, b = tags["p1"], tags["p2"]
        if abs(a[0] - b[0]) >= TAG_W:
            return
        f1, f2 = fight.fighters["p1"], fight.fighters["p2"]
        if f2.x != f1.x:
            side = 1 if f2.x > f1.x else -1     # p2 stands on this side of p1
        else:
            side = 1 if b[0] >= a[0] else -1
        mid = (a[0] + b[0]) / 2
        mid = min(max(mid, TAG_LO + TAG_W / 2), TAG_HI - TAG_W / 2)
        a[0], b[0] = mid - side * TAG_W / 2, mid + side * TAG_W / 2

    def _code_tag(self, key: str, f: Fighter, at, ox: int, oy: int) -> None:
        """The code over the head: the ket, the lights (flipped ones red) and the cycle ring."""
        code = f.code
        n = code.distance
        row = (n - 1) * LIGHT_GAP + 16             # the lights plus the ring
        cx = at[0] + ox
        cy = round(at[1]) + oy
        x0 = cx - row / 2 + 4
        flash, left = self.flash[key]
        lit = flash is not None and left % 6 >= 2
        base = P.SKY if code.basis == qec.BIT else P.GOLD
        surf = self.surface
        # a plate in the player's colour, with a tick pointing down at its own fighter
        color = PLAYER_COLORS[key]
        plate = pygame.Rect(0, 0, row + 8, 14)
        plate.center = (round(cx), cy)
        tick = min(max(round(at[2] + ox), plate.left + 4), plate.right - 4)
        pygame.draw.polygon(surf, P.INK, ((tick - 5, plate.bottom), (tick + 5, plate.bottom), (tick, plate.bottom + 6)))
        pygame.draw.polygon(surf, color, ((tick - 3, plate.bottom), (tick + 3, plate.bottom), (tick, plate.bottom + 3)))
        pygame.draw.rect(surf, P.INK, plate.inflate(2, 2), border_radius=5)
        pygame.draw.rect(surf, color, plate, border_radius=4)
        pygame.draw.rect(surf, P.NIGHT, plate.inflate(-4, -4), border_radius=3)
        for i in range(n):
            x = round(x0 + i * LIGHT_GAP)
            col = flash if lit else (P.BAD if i in code.flipped else base)
            pygame.draw.circle(surf, P.INK, (x, cy), 5)
            pygame.draw.circle(surf, col, (x, cy), 4)
            surf.fill(P.lighten(col, 0.6), (x - 2, cy - 2, 2, 2))
        ring = self.rings[min(RING_STEPS, int(code.progress * RING_STEPS))]
        blit_center(surf, ring, (x0 + n * LIGHT_GAP + 1, cy))
        blit_center(surf, outlined(code.label(), 8, P.WHITE), (cx, cy - 12))

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
