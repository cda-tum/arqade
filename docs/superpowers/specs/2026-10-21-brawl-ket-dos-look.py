"""DOS's approved look (2026-10-21): the classical computer, the walking all-in-one chosen
from v1's B.

A prototype, not game code, in the manner of PHOEBE's look script: it draws on Brawl-Ket's
own skeleton (poses.joints, POSES) and render helpers (limb, _ball, _block, _boot, _pt,
make_stage), at the game's 640x360 scale. Run it from brawl-ket/:

    uv run python ../docs/superpowers/specs/2026-10-21-brawl-ket-dos-look.py OUT.png

The joke: a classical bit can't be in superposition, so DOS never switches basis. He is
always green (Z basis, 0 or 1), the green of a monochrome phosphor screen.

New in v2: about ROBERT's height (a taller case, slightly longer legs), and the case leans
only CASE_TILT of each pose's lean, so in a crouch or a jump the legs fold and the box stays
upright instead of tipping over.
"""

import math
import sys

import pygame

from brawl_ket import palette as P
from brawl_ket import poses as PS
from brawl_ket.config import FLOOR_Y, PLAYER_COLORS
from brawl_ket.fonts import load_font
from brawl_ket.poses import POSES, Pose, joints
from brawl_ket.render import GREEN, PURPLE, SHADOW, _ball, _block, _boot, _pt, draw_puppet, limb, make_stage
from dataclasses import replace

# DOS's build: a tall case (the top of it level with ROBERT's head) on legs a little longer
# than v1's, the arms still stubby
PS.SCALE["dos"] = 2.2
PS.BUILD_BONES["dos"] = {"torso": 33, "shoulder": 15, "thigh": 14, "shin": 15, "upper_arm": 10, "forearm": 10}
PS.HEAD_R["dos"] = 15
PS.LIMB_W["dos"] = 13
CASE_TILT = 0.3        # the case leans only this much of the pose's lean: the legs do the work

BEIGE = (232, 216, 168)          # the one retro trim: keycap fists
GLASS = (16, 40, 24)             # the switched-off-looking dark of a mono CRT
SCAN = (24, 56, 32)
PHOSPHOR = (136, 248, 152)       # P1 phosphor green: the face
STEEL = P.MIST
LED = (248, 200, 48)


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


def quad(at, base, up0, up1, f0, f1):
    """The four corners of a panel on the body, in the body's own frame."""
    return [at(base, up0, f0), at(base, up0, f1), at(base, up1, f1), at(base, up1, f0)]


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


def screen_face(surf, rect, facing, mood="calm"):
    """A mono CRT screen: dark glass with a bulge glare, scanlines, and a face in phosphor
    pixels looking the way the fighter faces."""
    r = pygame.Rect(rect)
    pygame.draw.rect(surf, P.INK, r.inflate(4, 4), border_radius=5)
    pygame.draw.rect(surf, GLASS, r, border_radius=4)
    # the face: two tall phosphor eyes and a flat mouth, shifted towards the rival. Angry,
    # each eye's top slopes down towards the middle (a frown in pixels)
    cx = r.centerx + round(r.w * 0.1) * facing
    cy = r.centery - 2
    for side in (-1, 1):
        eye = pygame.Rect(0, 0, 6, 9)
        eye.center = (cx + side * 6, cy)
        surf.fill(PHOSPHOR, eye)
        if mood == "angry":
            inner_x = eye.right - 2 if side < 0 else eye.left
            surf.fill(GLASS, (inner_x, eye.top, 2, 3))
            surf.fill(GLASS, (eye.left + 2, eye.top, 2, 1) if side < 0 else (eye.left + 2, eye.top, 2, 1))
    surf.fill(PHOSPHOR, (cx - 5, cy + 8, 10, 2))
    # scanlines: every other row of the glass a little lighter, and the face a little dimmer
    for y in range(r.top + 1, r.bottom - 1, 2):
        for x in range(r.left + 1, r.right - 1):
            c = surf.get_at((x, y))[:3]
            surf.set_at((x, y), P.shade(PHOSPHOR, 0.78) if c == PHOSPHOR else SCAN)
    gx = r.left + 3 if facing > 0 else r.right - 7
    surf.fill(P.lighten(GLASS, 0.55), (gx, r.top + 2, 4, 2))
    surf.fill(P.lighten(GLASS, 0.55), (gx + (0 if facing > 0 else 2), r.top + 4, 2, 2))
    # the phosphor's glow round the edge of the glass
    pygame.draw.rect(surf, P.shade(GREEN, 0.45), r, 1, border_radius=4)


def fist(surf, p, half, color):
    """A keycap fist: a square block with a dished top face."""
    _block(surf, p, half, color)


# --- the floppy ------------------------------------------------------------------------------


def floppy_sprite(color, size=18):
    """A 3.5" floppy disk, front face: the sliding metal shutter with its window at the top,
    the label at the bottom, the chamfered corner (top right) and the write-protect hole."""
    s = pygame.Surface((size + 4, size + 4), pygame.SRCALPHA)
    o = 2
    n = size
    body = [(o, o), (o + n - 4, o), (o + n, o + 4), (o + n, o + n), (o, o + n)]
    pygame.draw.polygon(s, color, body)
    pygame.draw.polygon(s, P.INK, body, 2)
    # a highlight along the top edge
    s.fill(P.lighten(color, 0.45), (o + 2, o + 2, n - 7, 1))
    # the shutter: steel, with its window onto the disk
    sh = pygame.Rect(o + 4, o, 9, 8)
    s.fill(P.INK, sh.inflate(2, 0).move(0, 0))
    s.fill(STEEL, sh.inflate(-2, -2).move(0, 0))
    s.fill(P.INK, (sh.x + 5, sh.y + 2, 2, 4))
    # the label
    lab = pygame.Rect(o + 3, o + n - 8, n - 6, 7)
    s.fill(P.INK, lab.inflate(2, 2))
    s.fill(P.WHITE, lab)
    s.fill(P.shade(P.SKY, 0.8), (lab.x + 2, lab.y + 2, lab.w - 6, 1))     # handwriting, in biro
    s.fill(P.shade(P.SKY, 0.8), (lab.x + 2, lab.y + 4, lab.w - 9, 1))
    # the write-protect hole, bottom left
    s.fill(P.INK, (o + 1, o + n - 11, 2, 2))
    return s


def draw_floppy(surf, c, angle, color, facing, spin=35):
    """A spinning floppy in flight: two pale silhouettes of its last turns behind it, a few
    speed lines, then the disk itself with a white rim so it reads against any stage."""
    img = floppy_sprite(color, 22)
    sil = pygame.mask.from_surface(img).to_surface(setcolor=(*P.lighten(color, 0.4), 255),
                                                   unsetcolor=(0, 0, 0, 0))
    for k, a in ((2, 70), (1, 130)):
        e = pygame.transform.rotate(sil, angle + k * spin * facing)
        e.set_alpha(a)
        surf.blit(e, e.get_rect(center=_pt((c[0] - facing * k * 15, c[1]))))
    for dy, ln in ((-8, 14), (0, 22), (8, 12)):
        x0 = c[0] - facing * 40
        pygame.draw.line(surf, P.lighten(color, 0.5), _pt((x0, c[1] + dy)), _pt((x0 - facing * ln, c[1] + dy)), 2)
    r = pygame.transform.rotate(img, angle)
    mask = pygame.mask.from_surface(r)
    rim = mask.to_surface(setcolor=(*P.WHITE, 255), unsetcolor=(0, 0, 0, 0))
    rect = r.get_rect(center=_pt(c))
    for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1)):
        surf.blit(rim, rect.move(dx, dy))
    surf.blit(r, rect)


# --- DOS ----------------------------------------------------------------------------------------


def draw_dos(surf, pose, feet, facing, case=GREEN, strike=None, led=False, mood="calm", eject=False):
    """`strike` = (joint, colour) lights an attack's whole arm or leg in its colour; `eject`
    shows the disk's edge leaving the drive slot."""
    pose = replace(pose, lean=pose.lean * CASE_TILT)
    j = joints(pose, "dos", feet, facing)
    at = frame(j, facing)
    w = PS.LIMB_W["dos"]
    dark = P.shade(case, 0.65)
    boot = P.shade(case, 0.42)
    hip, neck = j["hip"], j["neck"]
    f = facing
    top, bot, fb, ff = 10, -4, -27, 27          # up from the neck / from the hip; the front's edges
    # the arms come out of the case's sides, under the screen, not out of its middle
    for side, k in (("f", ff), ("b", fb + 2)):
        o = at((0.0, 0.0), 0, k)
        for name in ("shoulder", "elbow", "hand"):
            x, y = j[f"{name}_{side}"]
            j[f"{name}_{side}"] = (x + o[0], y + o[1] - (4 if side == "b" else 0))
    # 1. the back leg and arm, in shadow
    ribbed(surf, hip, j["knee_b"], w + 2, dark)
    ribbed(surf, j["knee_b"], j["foot_b"], w + 1, dark)
    _boot(surf, j["foot_b"], f, w + 2, P.shade(boot, 0.8))
    ribbed(surf, j["shoulder_b"], j["elbow_b"], w, dark)
    ribbed(surf, j["elbow_b"], j["hand_b"], w - 1, dark)
    fist(surf, j["hand_b"], w // 2 + 1, P.shade(BEIGE, 0.7))
    # 2. the front leg goes under the case
    leg = strike[1] if strike and strike[0] == "foot_f" else case
    ribbed(surf, hip, j["knee_f"], w + 2, leg)
    ribbed(surf, j["knee_f"], j["foot_f"], w + 1, leg)
    _boot(surf, j["foot_f"], f, w + 2, boot if leg is case else P.shade(leg, 0.6))
    # 3. the case, in 3/4: its side going back (behind the face), its top, its front
    d = (-10 * f, -6)                           # the side's slant: back and up

    def back(p):
        return (p[0] + d[0], p[1] + d[1])

    tl, tr = at(neck, top, fb), at(neck, top, ff)
    bl, br = at(hip, bot, fb), at(hip, bot, ff)
    poly(surf, [tl, back(tl), back(bl), bl], dark)                     # the side
    poly(surf, [tl, tr, back(tr), back(tl)], P.lighten(case, 0.3))     # the top
    for k in range(4):                                                 # a carry handle's grip
        g = towards(tl, tr, 0.32 + k * 0.1)
        pygame.draw.line(surf, P.shade(case, 0.75), _pt((g[0] + d[0] * 0.3, g[1] + d[1] * 0.3)),
                         _pt((g[0] + d[0] * 0.7, g[1] + d[1] * 0.7)), 1)
    poly(surf, [tl, tr, br, bl], case)                                 # the front
    pygame.draw.line(surf, P.lighten(case, 0.45), _pt(at(neck, top - 2, fb + 3)), _pt(at(neck, top - 2, ff - 3)), 2)
    # the screen: the face, set towards the rival
    s0 = at(neck, top - 6, fb + 6)
    s1 = at(neck, top - 42, ff - 5)
    glass = pygame.Rect(0, 0, round(abs(s1[0] - s0[0])), round(abs(s1[1] - s0[1])))
    glass.center = _pt(towards(s0, s1, 0.5))
    screen_face(surf, glass, f, mood)
    # under the screen: the floppy drive's slot (with its eject button and busy light)
    slot_y = top - 54
    poly(surf, quad(at, neck, slot_y + 3, slot_y - 3, -10, 14), P.shade(case, 0.8))
    pygame.draw.line(surf, P.INK, _pt(at(neck, slot_y, -8)), _pt(at(neck, slot_y, 7)), 2)
    poly(surf, quad(at, neck, slot_y + 1, slot_y - 2, 9, 12), BEIGE, ink=1)
    pygame.draw.circle(surf, LED if led else P.shade(LED, 0.45), _pt(at(neck, slot_y, -14)), 1)
    if eject:                                   # the disk's edge sliding out, shutter first
        sx, sy = _pt(at(neck, slot_y, 0))
        pygame.draw.rect(surf, P.INK, (sx - 7, sy - 2, 14, 4))
        surf.fill(P.lighten(GREEN, 0.3), (sx - 6, sy - 1, 12, 2))
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
    fist(surf, j["hand_f"], w // 2 + 2, BEIGE if arm is case else P.lighten(arm, 0.5))
    j["slot"] = at(neck, slot_y, 0)
    return j


# FLOPPY: braced, the front fist raised and the back one flung back, out of the drive slot's way
EJECT = Pose(-6, 30, -4, -26, -14, 150, 175, -60, -20)


# --- the sheet ---------------------------------------------------------------------------------


def robert(surf, x, facing=1, key="p1", pose="idle", body=GREEN):
    ring(surf, x, key)
    draw_puppet(surf, POSES[pose], "lean", (x, FLOOR_Y), facing, body, P.CREAM)


def row_moves(sub):
    robert(sub, 46)
    label(sub, "ROBERT", (46, 128))
    for x, posename, facing, key, dy, strike, ly, text in (
            (150, "idle", 1, "p1", 0, None, 128, "DOS"), (258, "idle", -1, "p2", 0, None, 128, "DOS"),
            (368, "heavy_hit", 1, "p1", 0, ("hand_f", PURPLE), 128, "HEAVY HIT"),
            (486, "crouch", -1, "p2", 0, None, 168, "CROUCH"), (588, "jump", -1, "p2", -58, None, 66, "JUMP")):
        ring(sub, x, key, width=60)
        draw_dos(sub, POSES[posename], (x, FLOOR_Y + dy), facing, strike=strike)
        label(sub, text, (x, ly))


def row_floppy(sub):
    """FLOPPY: DOS fires a green disk (green, so it hurts green ROBERT) straight out of his
    own drive slot, spinning."""
    robert(sub, 540, -1, "p2", "idle")
    ring(sub, 120, "p1", width=60)
    j = draw_dos(sub, EJECT, (120, FLOOR_Y), 1, led=True, mood="angry", eject=True)
    sx, sy = _pt(j["slot"])
    sx += 30
    for dy in (-3, 0, 3):
        pygame.draw.line(sub, P.lighten(GREEN, 0.5), (sx + 2, sy + dy), (sx + 18 - abs(dy) * 2, sy + dy), 1)
    draw_floppy(sub, (sx + 64, sy - 4), -25, GREEN, 1)
    label(sub, "FLOPPY", (120, 128))
    big = pygame.transform.scale(floppy_sprite(GREEN, 20), (96, 96))
    sub.blit(big, (380 - 48, 26))
    label(sub, "X4", (380 + 62, 74))


def main(out: str) -> None:
    pygame.init()
    stage, _ = make_stage("lab")
    rows = (row_moves, row_floppy)
    sheet = pygame.Surface((640, 360 * len(rows)))
    for i, draw in enumerate(rows):
        sub = sheet.subsurface((0, i * 360, 640, 360))
        sub.blit(stage, (-8, -8))
        draw(sub)
    pygame.image.save(pygame.transform.scale(sheet, (1280, 720 * len(rows))), out)


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "pc_sheet_v2.png")
