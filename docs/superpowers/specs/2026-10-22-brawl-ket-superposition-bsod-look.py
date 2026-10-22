"""BLUE SCREEN OF DEATH look mockups: two variants, two beats each (run from brawl-ket/)."""
import sys
import pygame
pygame.init()
from brawl_ket import palette as P
from brawl_ket.fight import Fight
from brawl_ket.fighter import FighterInput
from brawl_ket.fonts import load_font
from brawl_ket.moves import CHARACTERS
from brawl_ket.render import Renderer, outlined, blit_center
from brawl_ket.config import FLOOR_Y

W, H = 640, 360
BSOD = (0, 0, 168)
KEY = (255, 0, 255)
f8 = load_font(8)


def fight_frame(dos_x, dos_y, rival_x, drop=False):
    fight = Fight({"p1": CHARACTERS["DOS"], "p2": CHARACTERS["ROBERT"]}, seed=1)
    for _ in range(3):
        fight.step({})
    d, r = fight.fighters["p1"], fight.fighters["p2"]
    d.x, r.x = dos_x, rival_x
    if drop:
        d.y = dos_y
        d.action = "jump"
    return fight


def layers(fight):
    """(the normal frame, the fighters and HUD alone on a transparent layer)"""
    surf = pygame.Surface((W, H))
    rr = Renderer(surf)
    rr.use_stage("lab")
    rr.draw_fight(fight, [], {"p1": 0, "p2": 0})
    normal = surf.copy()
    rr.stage = pygame.Surface(rr.stage.get_size())
    rr.stage.fill(KEY)
    rr.lights = []
    rr.draw_fight(fight, [], {"p1": 0, "p2": 0})
    top = surf.copy()
    top.set_colorkey(KEY)
    alpha = pygame.Surface((W, H), pygame.SRCALPHA)
    alpha.blit(top, (0, 0))
    return normal, alpha


def glitch(surf, rect, t):
    """The frozen rival: tinted blue-white, sliced into rows nudged sideways."""
    sub = surf.subsurface(rect).copy()
    sub.fill((120, 150, 255, 255), special_flags=pygame.BLEND_RGBA_MULT)
    out = pygame.Surface(sub.get_size(), pygame.SRCALPHA)
    for y in range(0, sub.get_height(), 6):
        dx = ((y * 7 + t) % 11) - 5 if (y // 6) % 3 == 0 else 0
        out.blit(sub, (dx, y), (0, y, sub.get_width(), 6))
    return out


TEXT = ["A fatal exception 0E has occurred at",
        "0028:C0011E36 in VXD QUBIT(01).",
        "The current opponent will be terminated.",
        "",
        "*  Press any key to terminate the",
        "   current opponent.",
        "*  Press CTRL+ALT+DEL to lose the round."]


def variant_a(beat):
    fight = fight_frame(200, 0, 360) if beat == 0 else fight_frame(360, 120, 360, drop=True)
    normal, top = layers(fight)
    surf = pygame.Surface((W, H))
    surf.fill(BSOD)
    if beat == 0:
        tag = pygame.Surface((50, 10)); tag.fill(P.MIST)
        surf.blit(tag, (W // 2 - 25, 52))
        blit_center(surf, f8.render("DOS", False, BSOD), (W // 2, 57))
        for i, line in enumerate(TEXT):
            surf.blit(f8.render(line, False, P.WHITE), (150, 70 + 10 * i))
    surf.fill(P.WHITE, (0, FLOOR_Y + 4, W, 1))      # the floor, as a line
    surf.blit(top, (0, 0))
    if beat == 0:
        rect = pygame.Rect(326, FLOOR_Y - 130, 68, 134)
        g = glitch(top, rect, 3)
        surf.fill(BSOD, rect)
        surf.blit(g, rect)
    else:
        impact(surf)
    return surf


def impact(surf):
    """The CRT DROP landing: a white burst on the rival and speed lines above DOS."""
    for dx in (-14, 0, 14):
        pygame.draw.line(surf, P.WHITE, (360 + dx, 20), (360 + dx, 90), 2)
    blit_center(surf, outlined("CRASH!", 16, P.WHITE, thick=2), (430, FLOOR_Y - 150))


def variant_b(beat):
    fight = fight_frame(200, 0, 360) if beat == 0 else fight_frame(360, 120, 360, drop=True)
    normal, top = layers(fight)
    surf = normal.copy()
    if beat == 0:
        # a blue sweep across the floor: the 200 px DOS freezes
        band = pygame.Surface((400, 18), pygame.SRCALPHA)
        band.fill((*BSOD, 140))
        surf.blit(band, (200 - 200, FLOOR_Y - 9))
        rect = pygame.Rect(326, FLOOR_Y - 130, 68, 134)
        g = glitch(top, rect, 3)
        surf.blit(normal, rect, rect)
        surf.blit(g, rect)
        # the error window over the rival's head
        win = pygame.Rect(0, 0, 170, 62)
        win.midbottom = (360, FLOOR_Y - 140)
        pygame.draw.rect(surf, P.INK, win.inflate(4, 4))
        surf.fill(BSOD, win)
        surf.fill(P.MIST, (win.x, win.y, win.w, 11))
        blit_center(surf, f8.render("FATAL EXCEPTION", False, BSOD), (win.centerx, win.y + 6))
        surf.blit(f8.render("ROBERT.EXE has", False, P.WHITE), (win.x + 8, win.y + 18))
        surf.blit(f8.render("stopped responding", False, P.WHITE), (win.x + 8, win.y + 30))
        ok = pygame.Rect(0, 0, 32, 12); ok.midbottom = (win.centerx, win.bottom - 4)
        surf.fill(P.MIST, ok)
        blit_center(surf, f8.render("OK", False, BSOD), ok.center)
    else:
        impact(surf)
    return surf


def call(surf, text, sub):
    blit_center(surf, outlined(text, 16, P.GOLD, thick=2), (W / 2, 300))
    blit_center(surf, outlined(sub, 8, P.WHITE), (W / 2, 322))


sheet = pygame.Surface((W * 2 + 8, H * 2 + 8))
sheet.fill(P.INK)
for col, v in enumerate((variant_a, variant_b)):
    for row in range(2):
        s = v(row)
        if row == 0:
            call(s, "BLUE SCREEN OF DEATH", "variant " + "AB"[col] + ": the freeze")
        else:
            call(s, "CRT DROP", "the hit")
        sheet.blit(s, (col * (W + 8), row * (H + 8)))
pygame.image.save(pygame.transform.scale_by(sheet, 1.5), sys.argv[1])
