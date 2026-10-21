"""DOS's look: a walking all-in-one computer in 3/4 view, his screen his face, and his floppy.

Ported from his approved look, docs/superpowers/specs/2026-10-21-brawl-ket-dos-look.py:
draw_dos is the look's, given poses.drawn_joints (the case leans only CASE_TILT of a pose's
lean and his arms come out of its sides); tests/test_render.py checks him and the disk
against the look pixel for pixel. The screen faces (the look scanned every pixel of the
glass every call) and the disk's turns are drawn once each, then only blitted, so the
cabinet's frame budget holds.
"""

from __future__ import annotations

import math
from functools import lru_cache

import pygame

from . import palette as P
from .ink import _ball, _block, _boot, _pt, frame, limb, poly
from .ink import _towards as towards
from .poses import LIMB_W

BEIGE = (232, 216, 168)          # the one retro trim: keycap fists
GLASS = (16, 40, 24)             # the switched-off-looking dark of a mono CRT
SCAN = (24, 56, 32)
PHOSPHOR = (136, 248, 152)       # the phosphor green of his face
STEEL = P.MIST
LED = (248, 200, 48)
BSOD = (32, 72, 200)             # BLUE SCREEN: the crash
BSOD_SCAN = (24, 56, 168)
KEY = (255, 0, 255)
ANGLE_STEP = 15                  # the disk turns in steps of this many degrees, each drawn once
SPIN = 30                        # ... and its two pale silhouettes trail this far behind
CLIP_W, CLIP_H = 18, 14          # his clipboard on the HUD


def quad(at, base, up0, up1, f0, f1):
    """The four corners of a panel on the body, in the body's own frame."""
    return [at(base, up0, f0), at(base, up0, f1), at(base, up1, f1), at(base, up1, f0)]


def ribbed(surf, a, b, w, color):
    """A limb as a ribbed cable conduit: the game's capsule, with a darker band every 5 px."""
    limb(surf, a, b, w, color)
    dx, dy = b[0] - a[0], b[1] - a[1]
    n = math.hypot(dx, dy) or 1.0
    px, py = -dy / n, dx / n
    band = P.shade(color, 0.72)
    half = w / 2 - 1
    for k in range(1, int(n // 5)):
        c = (a[0] + dx * k * 5 / n, a[1] + dy * k * 5 / n)
        pygame.draw.line(surf, band, _pt((c[0] - px * half, c[1] - py * half)),
                         _pt((c[0] + px * half, c[1] + py * half)), 1)


@lru_cache(maxsize=512)    # about 50 sizes (the case tilts), 3 moods, 2 facings
def screen_sprite(w: int, h: int, facing: int, mood: str, glow) -> pygame.Surface:
    """His screen, w x h (plus its 2 px ink frame): dark glass with scanlines and a glare, and a
    face in phosphor pixels looking the way he faces, the look's screen_face. Angry, each
    eye's top slopes down towards the middle; "blue" (BLUE SCREEN), the glass crashes blue and
    the face is a white frown."""
    s = pygame.Surface((w + 4, h + 4))
    s.fill(KEY)
    s.set_colorkey(KEY)
    r = pygame.Rect(2, 2, w, h)
    blue = mood == "blue"
    bg, scan, lit = (BSOD, BSOD_SCAN, P.WHITE) if blue else (GLASS, SCAN, PHOSPHOR)
    pygame.draw.rect(s, P.INK, r.inflate(4, 4), border_radius=5)
    pygame.draw.rect(s, bg, r, border_radius=4)
    cx = r.centerx + round(r.w * 0.1) * facing
    cy = r.centery - 2
    if blue:
        for side in (-1, 1):
            s.fill(lit, (cx + side * 6 - 2, cy - 2, 4, 4))
        s.fill(lit, (cx - 5, cy + 8, 10, 2))
        s.fill(lit, (cx - 7, cy + 10, 2, 2))
        s.fill(lit, (cx + 5, cy + 10, 2, 2))
    else:
        for side in (-1, 1):
            eye = pygame.Rect(0, 0, 6, 9)
            eye.center = (cx + side * 6, cy)
            s.fill(lit, eye)
            if mood == "angry":
                inner_x = eye.right - 2 if side < 0 else eye.left
                s.fill(GLASS, (inner_x, eye.top, 2, 3))
                s.fill(GLASS, (eye.left + 2, eye.top, 2, 1))
        s.fill(lit, (cx - 5, cy + 8, 10, 2))
    # the look's scanlines, a row at a time: every other row of the glass turns `scan`, and the
    # face's pixels on it a dimmer shade (the look set every pixel by hand; same pixels, faster)
    dim = P.shade(lit, 0.78)
    for y in range(r.top + 1, r.bottom - 1, 2):
        row = s.subsurface((r.left + 1, y, r.w - 2, 1))
        face = pygame.mask.from_threshold(row, lit, (1, 1, 1, 255))
        row.fill(scan)
        face.to_surface(row, setcolor=dim, unsetcolor=None)
    gx = r.left + 3 if facing > 0 else r.right - 7
    s.fill(P.lighten(bg, 0.55), (gx, r.top + 2, 4, 2))
    s.fill(P.lighten(bg, 0.55), (gx + (0 if facing > 0 else 2), r.top + 4, 2, 2))
    pygame.draw.rect(s, glow, r, 1, border_radius=4)
    return s


def screen_face(surf, rect, facing, mood, glow):
    r = pygame.Rect(rect)
    surf.blit(screen_sprite(r.w, r.h, facing, mood, glow), (r.x - 2, r.y - 2))


@lru_cache(maxsize=16)
def floppy_sprite(color, size=18):
    """A 3.5" floppy disk, front face (the look's): the sliding steel shutter with its window
    at the top, the label with two lines of biro, the chamfered corner and the write-protect
    hole. Cached: never draw on it."""
    s = pygame.Surface((size + 4, size + 4), pygame.SRCALPHA)
    o = 2
    n = size
    body = [(o, o), (o + n - 4, o), (o + n, o + 4), (o + n, o + n), (o, o + n)]
    pygame.draw.polygon(s, color, body)
    pygame.draw.polygon(s, P.INK, body, 2)
    s.fill(P.lighten(color, 0.45), (o + 2, o + 2, n - 7, 1))
    sh = pygame.Rect(o + 4, o, 9, 8)
    s.fill(P.INK, sh.inflate(2, 0).move(0, 0))
    s.fill(STEEL, sh.inflate(-2, -2).move(0, 0))
    s.fill(P.INK, (sh.x + 5, sh.y + 2, 2, 4))
    lab = pygame.Rect(o + 3, o + n - 8, n - 6, 7)
    s.fill(P.INK, lab.inflate(2, 2))
    s.fill(P.WHITE, lab)
    s.fill(P.shade(P.SKY, 0.8), (lab.x + 2, lab.y + 2, lab.w - 6, 1))
    s.fill(P.shade(P.SKY, 0.8), (lab.x + 2, lab.y + 4, lab.w - 9, 1))
    s.fill(P.INK, (o + 1, o + n - 11, 2, 2))
    return s


@lru_cache(maxsize=128)
def _turned(color, angle: int) -> tuple[pygame.Surface, pygame.Surface, pygame.Surface]:
    """The flying disk turned by `angle` degrees: (the disk, its white rim, a pale silhouette)."""
    img = floppy_sprite(color, 22)
    disk = pygame.transform.rotate(img, angle)
    rim = pygame.mask.from_surface(disk).to_surface(setcolor=(*P.WHITE, 255), unsetcolor=(0, 0, 0, 0))
    sil = pygame.mask.from_surface(img).to_surface(setcolor=(*P.lighten(color, 0.4), 255), unsetcolor=(0, 0, 0, 0))
    return disk, rim, pygame.transform.rotate(sil, angle)


def draw_floppy(surf, c, angle, color, facing):
    """A spinning floppy in flight (the look's draw_floppy): two pale silhouettes of its last
    turns behind it, a few speed lines, then the disk itself with a white rim, so it reads
    against any stage. `angle` is rounded to ANGLE_STEP."""
    a = round(angle / ANGLE_STEP) * ANGLE_STEP % 360
    for k, alpha in ((2, 70), (1, 130)):
        e = _turned(color, (a + k * SPIN * facing) % 360)[2]
        e.set_alpha(alpha)
        surf.blit(e, e.get_rect(center=_pt((c[0] - facing * k * 15, c[1]))))
    for dy, ln in ((-8, 14), (0, 22), (8, 12)):
        x0 = c[0] - facing * 40
        pygame.draw.line(surf, P.lighten(color, 0.5), _pt((x0, c[1] + dy)), _pt((x0 - facing * ln, c[1] + dy)), 2)
    disk, rim, _sil = _turned(color, a)
    rect = disk.get_rect(center=_pt(c))
    for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1)):
        surf.blit(rim, rect.move(dx, dy))
    surf.blit(disk, rect)


@lru_cache(maxsize=32)
def clip_icon(kind: str | None, color) -> pygame.Surface:
    """His clipboard on the HUD: a little dark screen, empty, or showing the caught shot's tiny
    sprite (a disk, a laser streak, a box, a bolt of electricity or a photon) in the colour it
    was fired in."""
    s = pygame.Surface((CLIP_W, CLIP_H))
    s.fill(KEY)
    s.set_colorkey(KEY)
    box = s.get_rect()
    pygame.draw.rect(s, P.INK, box, border_radius=3)
    inner = box.inflate(-4, -4)
    pygame.draw.rect(s, GLASS, inner, border_radius=2)
    if kind is None:
        pygame.draw.rect(s, SCAN, inner, 1, border_radius=2)
        return s
    cx, cy = inner.center
    if kind == "FLOPPY":
        disk = pygame.Rect(0, 0, 8, 8)
        disk.center = (cx, cy)
        s.fill(color, disk)
        s.fill(STEEL, (disk.x + 2, disk.y, 4, 3))
        s.fill(P.WHITE, (disk.x + 1, disk.bottom - 3, 6, 2))
    elif kind == "LASER":
        pygame.draw.line(s, color, (inner.left + 2, cy), (inner.right - 3, cy), 3)
        s.fill(P.WHITE, (inner.right - 4, cy - 1, 2, 2))
    elif kind == "BOX DROP":                    # ERWIN's little box
        s.fill(color, (cx - 4, cy - 2, 8, 6))
        s.fill(P.lighten(color, 0.45), (cx - 1, cy - 2, 2, 5))
        s.fill(P.shade(color, 0.7), (cx - 5, cy - 4, 4, 2))
        s.fill(P.shade(color, 0.7), (cx + 1, cy - 4, 4, 2))
    elif kind == "CHARGE NOISE":                # BOHR's electricity: a bolt
        pygame.draw.lines(s, color, False, [(cx + 2, cy - 5), (cx - 2, cy), (cx + 2, cy), (cx - 2, cy + 5)], 2)
    else:
        pygame.draw.circle(s, color, (cx, cy), 4)
        s.fill(P.lighten(color, 0.6), (cx - 1, cy - 2, 2, 2))
    return s


def draw_dos(surf, j, facing, case, strike=None, led=False, mood="calm", eject=False):
    """DOS at the joints `j` (poses.drawn_joints, build "dos"), his case in `case` (always his
    green). `strike` = (joint, colour) lights an attack's whole arm or leg; `mood` is his
    screen ("calm", "angry", "blue"), `led` his drive's busy light, `eject` a disk's edge in
    the slot. Adds j["slot"] (the drive slot's middle) and returns j."""
    at = frame(j, facing)
    w = LIMB_W["dos"]
    dark = P.shade(case, 0.65)
    boot = P.shade(case, 0.42)
    hip, neck = j["hip"], j["neck"]
    f = facing
    top, bot, fb, ff = 10, -4, -27, 27          # up from the neck / from the hip; the front's edges
    # 1. the back leg and arm, in shadow
    ribbed(surf, hip, j["knee_b"], w + 2, dark)
    ribbed(surf, j["knee_b"], j["foot_b"], w + 1, dark)
    _boot(surf, j["foot_b"], f, w + 2, P.shade(boot, 0.8))
    ribbed(surf, j["shoulder_b"], j["elbow_b"], w, dark)
    ribbed(surf, j["elbow_b"], j["hand_b"], w - 1, dark)
    _block(surf, j["hand_b"], w // 2 + 1, P.shade(BEIGE, 0.7))
    # 2. the front leg goes under the case
    leg = strike[1] if strike and strike[0] == "foot_f" else case
    ribbed(surf, hip, j["knee_f"], w + 2, leg)
    ribbed(surf, j["knee_f"], j["foot_f"], w + 1, leg)
    _boot(surf, j["foot_f"], f, w + 2, boot if leg is case else P.shade(leg, 0.6))
    # 3. the case, in 3/4: its side going back (behind the face), its top, its front
    d = (-10 * f, -6)

    def back(p):
        return (p[0] + d[0], p[1] + d[1])

    tl, tr = at(neck, top, fb), at(neck, top, ff)
    bl, br = at(hip, bot, fb), at(hip, bot, ff)
    poly(surf, [tl, back(tl), back(bl), bl], dark)
    poly(surf, [tl, tr, back(tr), back(tl)], P.lighten(case, 0.3))
    for k in range(4):                                                 # a carry handle's grip
        g = towards(tl, tr, 0.32 + k * 0.1)
        pygame.draw.line(surf, P.shade(case, 0.75), _pt((g[0] + d[0] * 0.3, g[1] + d[1] * 0.3)),
                         _pt((g[0] + d[0] * 0.7, g[1] + d[1] * 0.7)), 1)
    poly(surf, [tl, tr, br, bl], case)
    pygame.draw.line(surf, P.lighten(case, 0.45), _pt(at(neck, top - 2, fb + 3)), _pt(at(neck, top - 2, ff - 3)), 2)
    # the screen: the face, set towards the rival
    s0 = at(neck, top - 6, fb + 6)
    s1 = at(neck, top - 42, ff - 5)
    glass = pygame.Rect(0, 0, round(abs(s1[0] - s0[0])), round(abs(s1[1] - s0[1])))
    glass.center = _pt(towards(s0, s1, 0.5))
    screen_face(surf, glass, f, mood, P.shade(case, 0.45))
    # under the screen: the floppy drive's slot, its eject button and busy light
    slot_y = top - 54
    poly(surf, quad(at, neck, slot_y + 3, slot_y - 3, -10, 14), P.shade(case, 0.8))
    pygame.draw.line(surf, P.INK, _pt(at(neck, slot_y, -8)), _pt(at(neck, slot_y, 7)), 2)
    poly(surf, quad(at, neck, slot_y + 1, slot_y - 2, 9, 12), BEIGE, ink=1)
    pygame.draw.circle(surf, LED if led else P.shade(LED, 0.45), _pt(at(neck, slot_y, -14)), 1)
    if eject:                                   # the disk's edge sliding out, shutter first
        sx, sy = _pt(at(neck, slot_y, 0))
        pygame.draw.rect(surf, P.INK, (sx - 7, sy - 2, 14, 4))
        surf.fill(P.lighten(case, 0.3), (sx - 6, sy - 1, 12, 2))
    # the chin: vent slots, and the power switch with its light
    for k in range(3):
        pygame.draw.line(surf, P.shade(case, 0.6), _pt(at(hip, bot + 6 + k * 4, fb + 5)),
                         _pt(at(hip, bot + 6 + k * 4, fb + 19)), 2)
    pygame.draw.circle(surf, P.INK, _pt(at(hip, bot + 10, ff - 8)), 3)
    pygame.draw.circle(surf, PHOSPHOR, _pt(at(hip, bot + 10, ff - 8)), 1)
    # 4. the front arm, out of the case's side
    arm = strike[1] if strike and strike[0] == "hand_f" else case
    ribbed(surf, j["shoulder_f"], j["elbow_f"], w, arm)
    _ball(surf, j["shoulder_f"], w // 2 + 1, P.shade(arm, 0.8))
    ribbed(surf, j["elbow_f"], j["hand_f"], w - 1, arm)
    _block(surf, j["hand_f"], w // 2 + 2, BEIGE if arm is case else P.lighten(arm, 0.5))
    j["slot"] = at(neck, slot_y, 0)
    return j
