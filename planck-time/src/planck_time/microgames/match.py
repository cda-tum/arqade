"""MATCH!: a Brawl-Ket crossover. Two of Brawl-Ket's puppet fighters face
off in its lab: you are TRIO, the lean one, and your rival is QUINT, the
armoured one. A body's colour is its measurement basis: green is the Z basis
(|0>, |1>) and purple the X basis (|+>, |->), as on the health bars' badges.
Your colour is fixed. The rival keeps switching basis, each switch an H
with Brawl-Ket's white flash. Press A to jab: A is always in your own
colour, and an attack only hurts a rival of the matching colour. A jab while
the colours match lands and wins; a jab in the wrong colour is blocked
with pushback and fails, and so does never striking.

The strike is judged the moment A is pressed. The rival starts in the other
colour; at level 0 it keeps it for at least 0.7 s, and after that each colour
lasts an irregular 0.45 to 1.1 s, so there are always two or more chances.
Higher levels switch faster.
"""

from __future__ import annotations

import math

import pygame

from planck_time import palette as P
from planck_time.microgames.base import IDLE, H, W, Microgame, PlayerInput, register
from planck_time.pixel import blit_center, outlined, result_overlay

GREEN = (72, 200, 96)  # Brawl-Ket's Z basis (and its X attacks)...
PURPLE = (160, 88, 232)  # ...and its X basis (and its Z attacks)
BODY = {"Z": GREEN, "X": PURPLE}
BADGE = {"Z": "0/1", "X": "+/-"}  # the basis's states, as on Brawl-Ket's health bars
ERROR = {"Z": "X!", "X": "Z!"}  # what a matching jab deals: green attacks are X, purple Z
OTHER = {"Z": "X", "X": "Z"}
FIRST = (0.7, 1.0)  # seconds before the rival's first switch, at level 0
HOLD = (0.45, 1.1)  # how long each colour lasts after that, at level 0
REACT = 0.15  # the bot waits this long into a matching colour

FLOOR = 132
YOU_X, RIVAL_X = 98, 142  # the fighters' feet, a step and a jab apart
LUNGE = 8  # px the jab steps in
WIND, STRIKE = 0.05, 0.3  # the jab's wind-up and how long its fist stays out
FLASH = 0.06  # the white flash of a switch
KNOCK, PUSH = 16, 6  # px a landed jab knocks the rival back, and a block pushes both

# Brawl-Ket's lab, on the GBA grid
WALL, WALL_TILE = (40, 32, 80), (48, 40, 96)
RACK, RACK_SLOT = (56, 48, 112), (88, 80, 152)
FLOOR_TOP, FLOOR_TILE, FLOOR_SHINE = (72, 64, 128), (56, 48, 104), (96, 88, 160)
SHADOW = (32, 24, 64)

# --- Brawl-Ket's puppet, at GBA size ----------------------------------------------------------
# A pose is joint angles in degrees from straight down, positive towards the facing:
# lean, front thigh and shin, back thigh and shin, front arm and forearm, back arm and forearm.
POSES = {
    "idle": (4, 24, -4, -22, -12, 40, 160, 20, 150),
    "crouch": (16, 95, -4, 30, -86, 50, 165, 30, 155),
    "jab_wind": (0, 26, -4, -24, -12, 30, 130, 24, 150),
    "jab_hit": (12, 32, 0, -28, -14, 56, 56, 30, 150),
    "hitstun": (-28, 14, -8, -26, -14, -30, -70, -60, -100),
}
BONES = {"torso": 26, "neck": 9, "shoulder": 22, "upper_arm": 13, "forearm": 13, "thigh": 17, "shin": 17}
BUILDS = {  # scale, head radius, limb width, the neck (the heavy's helm sits low)
    "lean": (0.88, 6, 5, 9),
    "heavy": (1.0, 7, 7, 6),
}


def lerp(a, b, k: float):
    return tuple(x + (y - x) * k for x, y in zip(a, b))


def joints(pose, build: str, feet, facing: int) -> dict:
    """Screen positions of every joint, the lowest foot on the floor."""
    s, _, _, neck = BUILDS[build]
    bone = {**{k: v * s for k, v in BONES.items()}, "neck": neck * s}
    lean, thigh_f, shin_f, thigh_b, shin_b, arm_f, fore_f, arm_b, fore_b = pose

    def at(p, angle, length):
        a = math.radians(angle)
        return (p[0] + facing * math.sin(a) * length, p[1] + math.cos(a) * length)

    up = 180 - lean
    pts = {"hip": (0.0, 0.0)}
    pts["neck"] = at(pts["hip"], up, bone["torso"])
    pts["head"] = at(pts["neck"], up, bone["neck"])
    sh = pts["shoulder"] = at(pts["hip"], up, bone["shoulder"])
    for side, arm, fore, thigh, shin in (("f", arm_f, fore_f, thigh_f, shin_f), ("b", arm_b, fore_b, thigh_b, shin_b)):
        pts[f"elbow_{side}"] = at(sh, arm, bone["upper_arm"])
        pts[f"hand_{side}"] = at(pts[f"elbow_{side}"], fore, bone["forearm"])
        pts[f"knee_{side}"] = at(pts["hip"], thigh, bone["thigh"])
        pts[f"foot_{side}"] = at(pts[f"knee_{side}"], shin, bone["shin"])
    dy = feet[1] - max(pts["foot_f"][1], pts["foot_b"][1])
    return {k: (x + feet[0], y + dy) for k, (x, y) in pts.items()}


def _pt(p) -> tuple[int, int]:
    return round(p[0]), round(p[1])


def limb(surf, a, b, w: int, color) -> None:
    """A capsule from a to b with an ink outline."""
    a, b = _pt(a), _pt(b)
    for c, ww in ((P.INK, w + 2), (color, w)):
        pygame.draw.line(surf, c, a, b, ww)
        pygame.draw.circle(surf, c, a, ww // 2)
        pygame.draw.circle(surf, c, b, ww // 2)


def ball(surf, p, r: int, color) -> None:
    pygame.draw.circle(surf, P.INK, _pt(p), r + 1)
    pygame.draw.circle(surf, color, _pt(p), r)


def block(surf, p, half: int, color) -> None:
    rect = pygame.Rect(0, 0, 2 * half, 2 * half)
    rect.center = _pt(p)
    pygame.draw.rect(surf, P.INK, rect.inflate(2, 2), border_radius=2)
    pygame.draw.rect(surf, color, rect, border_radius=1)


def puppet(surf, pose, build: str, feet, facing: int, body, accent) -> dict:
    """TRIO (lean) or QUINT (heavy, armoured), back limbs first, as Brawl-Ket draws them."""
    j = joints(pose, build, feet, facing)
    _, r, w, _ = BUILDS[build]
    dark = P.shade(body, 0.65)
    heavy = build == "heavy"
    limb(surf, j["hip"], j["knee_b"], w + 1, dark)
    limb(surf, j["knee_b"], j["foot_b"], w, dark)
    limb(surf, j["shoulder"], j["elbow_b"], w - 1, dark)
    limb(surf, j["elbow_b"], j["hand_b"], w - 2, dark)
    (block if heavy else ball)(surf, j["hand_b"], w // 2 + 1, P.shade(accent, 0.7))
    hip, neck, sh = j["hip"], j["neck"], j["shoulder"]
    tx, ty = neck[0] - hip[0], neck[1] - hip[1]
    n = math.hypot(tx, ty) or 1.0
    ux, uy = tx / n, ty / n  # up the spine...
    fx, fy = -uy * facing, ux * facing  # ...and towards the front
    if heavy:  # a wedge torso, broad at the shoulders, with a belt
        def at(base, up, front):
            return (base[0] + ux * up + fx * front, base[1] + uy * up + fy * front)
        rows = ((neck, 2, 5), (sh, 0, 9), (hip, 4, 6), (hip, -3, 6))
        wedge = [at(b, u, h) for b, u, h in rows] + [at(b, u, -h) for b, u, h in reversed(rows)]
        pygame.draw.polygon(surf, P.INK, wedge, 3)
        pygame.draw.polygon(surf, body, wedge)
        pygame.draw.line(surf, P.lighten(body, 0.5), _pt(at(sh, -1, 6)), _pt(at(sh, -7, 5)), 1)
        pygame.draw.line(surf, P.INK, _pt(at(hip, 1, -6)), _pt(at(hip, 1, 6)), 2)
    else:  # a capsule, with a highlight stripe down its front
        limb(surf, hip, neck, w + 2, body)
        pygame.draw.line(surf, P.lighten(body, 0.4), _pt((hip[0] + fx * 1.5 + tx * 0.2, hip[1] + fy * 1.5 + ty * 0.2)),
                         _pt((neck[0] + fx * 1.5 - tx * 0.2, neck[1] + fy * 1.5 - ty * 0.2)), 1)
    limb(surf, j["hip"], j["knee_f"], w + 1, body)
    limb(surf, j["knee_f"], j["foot_f"], w, body)
    if heavy:  # boots, a shoulder plate
        for foot, c in ((j["foot_b"], P.shade(body, 0.4)), (j["foot_f"], P.shade(body, 0.45))):
            boot = pygame.Rect(0, 0, w + 4, w - 2)
            boot.midbottom = _pt((foot[0] + 1 * facing, foot[1] + w // 2 + 1))
            pygame.draw.rect(surf, P.INK, boot.inflate(2, 2), border_radius=2)
            pygame.draw.rect(surf, c, boot, border_radius=1)
    hx, hy = _pt(j["head"])
    if heavy:  # a flat-topped helm with a slit visor
        helm = pygame.Rect(0, 0, 2 * r + 2, 2 * r)
        helm.center = (hx, hy)
        pygame.draw.rect(surf, P.INK, helm.inflate(2, 2), border_radius=4)
        pygame.draw.rect(surf, body, helm, border_radius=3)
        slit = pygame.Rect(0, 0, r + 3, 2)
        slit.midleft = (hx - 2, hy - 1) if facing > 0 else (hx - r - 1, hy - 1)
        surf.fill(P.INK, slit.inflate(2, 2))
        surf.fill(accent, slit)
    else:  # a round helmet with a visor on the facing side
        pygame.draw.circle(surf, P.INK, (hx, hy), r + 1)
        pygame.draw.circle(surf, body, (hx, hy), r)
        visor = pygame.Rect(0, 0, r, 3)
        visor.midleft = (hx - 1, hy) if facing > 0 else (hx - r + 1, hy)
        surf.fill(accent, visor)
        surf.fill(P.lighten(body, 0.5), (hx - 2 * facing - 1, hy - 3, 2, 2))
    limb(surf, j["shoulder"], j["elbow_f"], w - 1, body)
    if heavy:
        ball(surf, j["shoulder"], w // 2 + 2, P.shade(accent, 0.85))
    limb(surf, j["elbow_f"], j["hand_f"], w - 2, body)
    (block if heavy else ball)(surf, j["hand_f"], w // 2 + 1, accent)
    return j


@register
class Match(Microgame):
    VERB = "MATCH!"
    INPUT = "a"
    CAPTION = "Colour must match to hurt"

    def __init__(self, seed: int, level: int, duration: float) -> None:
        super().__init__(seed, level, duration)
        self.mine = self.rng.choice(("Z", "X"))
        # the rival switches basis at these times, starting in the other colour
        self.switches = []
        t = self.rng.uniform(*FIRST) / self.speed
        while t < duration:
            self.switches.append(t)
            t += self.rng.uniform(*HOLD) / self.speed
        self.struck_at: float | None = None

    def basis_at(self, t: float) -> str:
        flips = sum(1 for s in self.switches if s <= t)
        return OTHER[self.mine] if flips % 2 == 0 else self.mine

    @property
    def rival(self) -> str:
        return self.basis_at(self.ended_at if self.ended_at is not None else self.t)

    def last_switch(self, t: float) -> float:
        return max((s for s in self.switches if s <= t), default=0.0)

    # --- the rules ----------------------------------------------------------------------

    def step(self, dt: float, inp: PlayerInput) -> None:
        if inp.a:
            self.struck_at = self.t
            if self.basis_at(self.t) == self.mine:
                self.win()
            else:
                self.fail()

    def bot(self) -> PlayerInput:
        go = self.basis_at(self.t) == self.mine and self.t - self.last_switch(self.t) >= REACT
        return PlayerInput(a=go, a_held=go) if go else IDLE

    # --- drawing ----------------------------------------------------------------------

    def stage(self, surf: pygame.Surface) -> None:
        """Brawl-Ket's lab: a tiled wall, racks of qubit chips with blinking lights, a tiled floor."""
        surf.fill(WALL)
        for y in range(0, FLOOR, 8):
            for x in range(-(y // 8 % 2) * 8, W, 16):
                surf.fill(WALL_TILE, (x, y, 15, 7))
        for i, x in enumerate((14, 196)):
            rack = pygame.Rect(x, 44, 30, 80)
            pygame.draw.rect(surf, P.INK, rack.inflate(2, 2), border_radius=3)
            pygame.draw.rect(surf, RACK, rack, border_radius=2)
            for k in range(5):
                slot = pygame.Rect(rack.x + 4, rack.y + 6 + k * 15, 22, 4)
                surf.fill(P.INK, slot.inflate(2, 2))
                surf.fill(P.GOLD if (i + k) % 3 == 0 else RACK_SLOT, slot)
                for q in range(3):
                    on = (int(self.t * 4) + i * 7 + k * 3 + q * 5) % 9 < 6
                    color = (P.GOOD, P.SKY, P.GOLD)[(i + k + q) % 3]
                    surf.fill(color if on else P.shade(color, 0.45), (slot.x + 2 + q * 5, slot.bottom + 3, 3, 2))
            pygame.draw.line(surf, P.INK, (rack.centerx, rack.bottom), (rack.centerx, FLOOR), 2)
        surf.fill(P.INK, (0, FLOOR - 2, W, H - FLOOR + 2))
        for x in range(-8, W, 16):
            surf.fill(FLOOR_TOP, (x + 1, FLOOR - 1, 14, 7))
            surf.fill(FLOOR_SHINE, (x + 2, FLOOR, 12, 1))
            surf.fill(FLOOR_TILE, (x + 1, FLOOR + 7, 14, H - FLOOR - 7))

    def hud(self, surf: pygame.Surface) -> None:
        """Brawl-Ket's health bars, each with its basis badge, and the A chip in your colour."""
        rival_hurt = self.result is True
        for side, name, basis, full in ((-1, "TRIO", self.mine, True), (1, "QUINT", self.rival, not rival_hurt)):
            bar = pygame.Rect(0, 8, 76, 6)
            if side < 0:
                bar.left = 8
            else:
                bar.right = W - 8
            pygame.draw.rect(surf, P.INK, bar.inflate(2, 2), border_radius=2)
            width = bar.w if full else round(bar.w * 0.86)
            fill = pygame.Rect(bar.x, bar.y, width, bar.h)
            if side > 0:
                fill.right = bar.right
            surf.fill(P.GOLD, fill)
            surf.fill(P.lighten(P.GOLD, 0.5), (fill.x + 1, fill.y + 1, fill.w - 2, 1))
            label = outlined(BADGE[basis], 8, P.WHITE)
            badge = pygame.Rect(0, 0, label.get_width() + 4, 12)
            badge.centery = bar.centery
            if side < 0:
                badge.left = bar.right + 4
            else:
                badge.right = bar.left - 4
            pygame.draw.rect(surf, P.INK, badge.inflate(2, 2), border_radius=3)
            pygame.draw.rect(surf, BODY[basis], badge, border_radius=2)
            blit_center(surf, label, badge.center)
            tag = outlined(name, 8, P.MIST)
            surf.blit(tag, (bar.left if side < 0 else bar.right - tag.get_width(), bar.bottom + 4))
        # A hits in your own colour
        chip = pygame.Rect(46, 18, 12, 11)
        pygame.draw.rect(surf, P.INK, chip.inflate(2, 2), border_radius=2)
        pygame.draw.rect(surf, BODY[self.mine], chip, border_radius=2)
        blit_center(surf, outlined("A", 8, P.WHITE), (chip.centerx + 1, chip.centery + 1))

    def draw(self, surf: pygame.Surface) -> None:
        self.stage(surf)
        self.hud(surf)
        k = 0.0 if self.struck_at is None else self.t - self.struck_at
        # where everyone stands: the jab steps in; a landed one knocks the rival back, a block
        # pushes both apart
        slide = min(1.0, k / 0.15)
        you_x = YOU_X + LUNGE * min(1.0, k / WIND) - (PUSH * slide if self.result is False else 0)
        rival_x = RIVAL_X + (KNOCK if self.result else PUSH) * slide
        for x in (you_x, rival_x):
            shadow = pygame.Rect(0, 0, 30, 6)
            shadow.center = (round(x), FLOOR + 1)
            pygame.draw.ellipse(surf, SHADOW, shadow)

        breath = 0.5 - 0.5 * math.cos(self.t * 5)
        idle = lerp(POSES["idle"], POSES["crouch"], 0.05 * breath)
        rival_pose = idle
        if self.result is True:
            rival_pose = POSES["hitstun"]
        elif self.struck_at is not None:  # blocked: rocked back a little
            rival_pose = lerp(idle, POSES["hitstun"], 0.35)
        # a switch is an H: a white flash, and an H rising over the rival
        since = self.t - self.last_switch(self.t)
        switched = self.result is None and bool(self.switches) and self.switches[0] <= self.t
        rival_body = P.WHITE if switched and since < FLASH else BODY[self.rival]
        puppet(surf, rival_pose, "heavy", (rival_x, FLOOR), -1, rival_body, P.GOLD)
        if switched and since < 0.4:
            blit_center(surf, outlined("H", 16, P.WHITE), (rival_x, 46 - 20 * since))

        if self.struck_at is None:
            pose = idle
        elif k < WIND:
            pose = lerp(idle, POSES["jab_wind"], k / WIND)
        elif k < WIND + STRIKE:
            pose = POSES["jab_hit"]
        else:
            pose = lerp(POSES["jab_hit"], idle, min(1.0, (k - WIND - STRIKE) / 0.15))
        mine = BODY[self.mine]
        j = puppet(surf, pose, "lean", (you_x, FLOOR), 1, mine, P.CREAM)
        fist = _pt(j["hand_f"])
        if self.struck_at is not None and WIND <= k < WIND + STRIKE:  # the fist glows in the jab's colour
            pygame.draw.circle(surf, P.INK, fist, 5)
            pygame.draw.circle(surf, P.lighten(mine, 0.5), fist, 4)
        if self.result is True and k < 0.5:  # a spark, and the error it dealt
            cx, cy = fist[0] + 5, fist[1]
            age = k / 0.5
            for i in range(8):
                a = i * math.pi / 4 + 0.2
                out = (6 + 6 * age) * (1.0 if i % 2 == 0 else 0.6)
                pygame.draw.line(surf, P.WHITE, (cx + math.cos(a) * 2, cy + math.sin(a) * 2),
                                 (cx + math.cos(a) * out, cy + math.sin(a) * out), 2)
        if self.result is True:
            blit_center(surf, outlined(ERROR[self.mine], 16, mine), (rival_x, 50 - min(k, 0.4) * 20))
        blocked = self.result is False and self.struck_at is not None
        if blocked and k < 0.4:  # it bounces off: a ring springing out
            r = round(3 + 9 * (1 - (1 - k / 0.4) ** 2))
            pygame.draw.circle(surf, P.INK, (fist[0] + 4, fist[1]), r + 1, 3)
            pygame.draw.circle(surf, P.WHITE if k < 0.05 else mine, (fist[0] + 4, fist[1]), r, 2)
        if blocked:
            blit_center(surf, outlined("BLOCKED", 8, P.WHITE), (rival_x, 52))
        blit_center(surf, outlined("A WHEN THE COLOURS MATCH", 8, P.WHITE), (W // 2, H - 9))
        result_overlay(surf, self.result, self.since_end, seed=19)
