"""PHOEBE's approved look (2026-10-09), the reference for porting her into render.py.

A prototype, not game code: it draws on Brawl-Ket's own skeleton (poses.joints) and
helpers (render.limb, _ball, _pt) with a new "toy" build. Run it from brawl-ket/:

    uv run python ../docs/superpowers/specs/2026-10-09-brawl-ket-phoebe-look.py OUT.png

`flare` (px) pushes the coat's hem out behind her; in the game it would follow her motion.
"""

import math
import sys

import pygame

from brawl_ket import palette as P
from brawl_ket import poses as PS
from brawl_ket.poses import POSES, joints
from brawl_ket.render import GREEN, PURPLE, _ball, _pt, limb, make_stage

PS.SCALE["toy"] = 2.1
PS.BUILD_BONES["toy"] = {"thigh": 18, "shin": 18, "forearm": 13, "upper_arm": 13, "neck": 8}
PS.HEAD_R["toy"] = 14
PS.LIMB_W["toy"] = 12

SKIN = (232, 176, 128)
HAIR = (88, 48, 40)
SHOE = (40, 32, 48)
TRIM = P.WHITE


def frame(j, facing):
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
    pygame.draw.polygon(surf, P.INK, pts, ink)


def shoe(surf, foot, facing):
    r = pygame.Rect(0, 0, 16, 7)
    r.midbottom = _pt((foot[0] + 4 * facing, foot[1] + 6))
    pygame.draw.rect(surf, P.INK, r.inflate(4, 4), border_radius=4)
    pygame.draw.rect(surf, SHOE, r, border_radius=3)


def draw_phoebe(surf, pose, feet, facing, base, accent, flare=0.0):
    coat = base
    lining = P.shade(base, 0.5)
    legs = P.shade(base, 0.6)
    j = joints(pose, "toy", feet, facing)
    at = frame(j, facing)
    w = PS.LIMB_W["toy"]
    hip, neck, sh = j["hip"], j["neck"], j["shoulder_f"]
    floor = max(j["foot_f"][1], j["foot_b"][1])
    leg = (PS.BASE_BONES["thigh"] + PS.BASE_BONES["shin"]) * PS.SCALE["toy"]
    # the hem: hangs (by gravity, not along the spine) to just above the ankles, never through
    # the floor; spreads with the stride and flares out behind
    hem_y = min(hip[1] + 0.86 * leg, floor - 7)
    spread = abs(j["foot_f"][0] - j["foot_b"][0])
    back_x = min(hip[0] * facing, j["knee_b"][0] * facing) * facing - facing * (20 + 0.25 * spread + flare)
    front_x = hip[0] + facing * (8 + 0.2 * spread)
    hb = (back_x, hem_y + 2)
    hm = ((back_x + front_x) / 2, hem_y + 5)
    hf = (front_x, hem_y)
    # 1. the inside of the coat, behind everything: the lining
    poly(surf, [at(sh, 0, -12), at(hip, 6, -15), hb, hm, hf, at(hip, 10, 10), at(sh, 0, 10)], lining)
    top = TRIM                                   # a white shirt under the open coat
    # 2. the back leg and arm
    limb(surf, hip, j["knee_b"], w, P.shade(legs, 0.8))
    limb(surf, j["knee_b"], j["foot_b"], w - 1, P.shade(legs, 0.8))
    shoe(surf, j["foot_b"], facing)
    dark = P.shade(coat, 0.7)
    limb(surf, j["shoulder_b"], j["elbow_b"], w + 1, dark)
    limb(surf, j["elbow_b"], j["hand_b"], w, dark)
    _ball(surf, towards(j["elbow_b"], j["hand_b"], 0.82), 7, P.shade(TRIM, 0.75))
    _ball(surf, j["hand_b"], 5, P.shade(SKIN, 0.8))
    # 3. the dark top, then the front leg: the coat goes over both
    poly(surf, [at(neck, 5, -7), at(neck, 5, 8), at(sh, 0, 12), at(hip, 6, 12), at(hip, 0, 10),
                at(hip, 0, -12), at(sh, 0, -12)], top)
    limb(surf, hip, j["knee_f"], w, legs)
    limb(surf, j["knee_f"], j["foot_f"], w - 1, legs)
    shoe(surf, j["foot_f"], facing)
    # 4. the coat, one shape: its back panel and the front panel hanging open, the front edge
    # set back so the top shows. Both outlines go down first and both fills over them, so only
    # the silhouette keeps an ink line, none where the panels overlap.
    panels = [
        [at(neck, 3, -9), at(sh, 0, -14), at(hip, 6, -17), hb, hm,
         towards(hm, hf, 0.45), at(hip, 14, 2), at(sh, 0, 6)],
        [at(neck, 2, -3), at(sh, 0, -2), at(hip, 12, 0), hf,
         towards(hf, hm, 0.75), at(hip, 4, -10), at(sh, -8, -6), at(neck, 2, -8)],
    ]
    for pts in panels:
        pygame.draw.polygon(surf, P.INK, [_pt(q) for q in pts], 4)
    for pts in panels:
        pygame.draw.polygon(surf, coat, [_pt(q) for q in pts])
    # head (as variant C): hair, ponytail, face, two lenses
    hx, hy = _pt(j["head"])
    r = PS.HEAD_R["toy"]
    swing = max(-6.0, min(10.0, pose.lean * 0.3)) + flare * 0.3
    tie = (hx - 9 * facing, hy - 9)
    limb(surf, tie, (hx - (19 + swing) * facing, hy - 3), 10, HAIR)
    limb(surf, (hx - (19 + swing) * facing, hy - 3), (hx - (21 + swing) * facing, hy + 9), 7, HAIR)
    pygame.draw.circle(surf, P.INK, (hx, hy), r + 2)
    pygame.draw.circle(surf, HAIR, (hx, hy), r)
    pygame.draw.circle(surf, SKIN, (hx + 4 * facing, hy + 3), r - 4)
    pygame.draw.circle(surf, P.lighten(HAIR, 0.45), (hx - 4 * facing, hy - 8), 3)
    # the arm runs back from the near lens's rim to the ear, under the lenses
    pygame.draw.line(surf, P.INK, (hx - 3 * facing, hy + 2), (hx - 9 * facing, hy), 2)
    for gx, rr in ((hx + 11 * facing, 4), (hx + 2 * facing, 5)):
        pygame.draw.circle(surf, P.INK, (gx, hy + 2), rr + 1)
        pygame.draw.circle(surf, P.lighten(accent, 0.6), (gx, hy + 2), rr - 1)
    surf.fill(P.WHITE, (hx + facing - 1, hy, 2, 2))
    # the front arm: sleeve, a big turned-back white cuff, hand
    limb(surf, j["shoulder_f"], j["elbow_f"], w + 1, coat)
    limb(surf, j["elbow_f"], j["hand_f"], w, coat)
    _ball(surf, towards(j["elbow_f"], j["hand_f"], 0.8), 7, TRIM)
    _ball(surf, j["hand_f"], 5, SKIN)
    return j


def main(out: str) -> None:
    pygame.init()
    stage, _ = make_stage()
    s = pygame.Surface((640, 720))
    for row, colour in enumerate((GREEN, PURPLE)):
        sub = s.subsurface((0, row * 360, 640, 360))
        sub.blit(stage, (-8, -8))
        for x, name, facing, flare, dy in ((60, "idle", 1, 0, 0), (175, "walk1", 1, 6, 0),
                                           (290, "heavy_hit", 1, 4, 0), (420, "crouch", -1, 0, 0),
                                           (530, "jump", -1, 12, -50)):
            draw_phoebe(sub, POSES[name], (x, 300 + dy), facing, colour, P.TEAL, flare)
    pygame.image.save(pygame.transform.scale(s, (1280, 1440)), out)


if __name__ == "__main__":
    main(sys.argv[1])
