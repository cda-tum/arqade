"""The approved look for Photon Pinball (2026-10-09): the mockup renderer that drew it.

A reference for the game's art, not part of it. Run with pygame 2.5.2:
    uv run --directory brawl-ket python ../docs/superpowers/specs/2026-10-09-photon-pinball-look.py OUT_DIR [FRAME]
It uses the DejaVu Sans Condensed Bold system font and Brawl-Ket's bundled Press Start 2P.
"""
import math
import os
import random
import sys

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
import pygame

pygame.init()
pygame.display.set_mode((1, 1))
BOLD = "/usr/share/fonts/truetype/dejavu/DejaVuSansCondensed-Bold.ttf"
W, H, S = 960, 540, 2
WHITE = (255, 255, 255)
P1C, P2C = (80, 170, 255), (255, 70, 80)
AMBER = (255, 190, 60)


def lerp(a, b, k):
    return (a[0] + (b[0] - a[0]) * k, a[1] + (b[1] - a[1]) * k)


def mix(c1, c2, k):
    return tuple(round(a + (b - a) * k) for a, b in zip(c1, c2))


def smooth(pts, n=10):
    pts = [pts[0], *pts, pts[-1]]
    out = []
    for i in range(1, len(pts) - 2):
        p0, p1, p2, p3 = pts[i - 1:i + 3]
        for k in range(n):
            t = k / n
            out.append(tuple(0.5 * (2 * p1[j] + (-p0[j] + p2[j]) * t + (2 * p0[j] - 5 * p1[j] + 4 * p2[j] - p3[j]) * t * t
                                    + (-p0[j] + 3 * p1[j] - 3 * p2[j] + p3[j]) * t ** 3) for j in (0, 1)))
    out.append(pts[-2])
    return out


def offset(pts, d):
    out = []
    for i, p in enumerate(pts):
        a, b = pts[max(0, i - 1)], pts[min(len(pts) - 1, i + 1)]
        dx, dy = b[0] - a[0], b[1] - a[1]
        L = math.hypot(dx, dy) or 1
        out.append((p[0] - dy / L * d, p[1] + dx / L * d))
    return out


class C:
    """A 2x canvas addressed in design units."""

    def __init__(self, w=W, h=H):
        self.s = pygame.Surface((w * S, h * S), pygame.SRCALPHA)

    @staticmethod
    def P(p):
        return (round(p[0] * S), round(p[1] * S))

    def layer(self):
        return pygame.Surface(self.s.get_size(), pygame.SRCALPHA)

    def blit(self, lay, alpha=255):
        if alpha < 255:
            lay.set_alpha(alpha)
        self.s.blit(lay, (0, 0))

    def circle(self, c, r, col, w=0, surf=None):
        pygame.draw.circle(surf or self.s, col, self.P(c), max(1, round(r * S)), round(w * S) if w else 0)

    def poly(self, pts, col, w=0, surf=None):
        pygame.draw.polygon(surf or self.s, col, [self.P(p) for p in pts], round(w * S) if w else 0)

    def lines(self, pts, col, w=1.0, surf=None):
        pygame.draw.lines(surf or self.s, col, False, [self.P(p) for p in pts], max(1, round(w * S)))

    def radial(self, c, r, inner, outer=None, surf=None, power=1.0):
        """A filled disc, inner colour (rgba) at the centre fading to outer at the rim."""
        outer = outer or (*inner[:3], 0)
        R = round(r * S)
        g = pygame.Surface((2 * R, 2 * R), pygame.SRCALPHA)
        for k in range(R, 0, -1):
            t = (k / R) ** power
            pygame.draw.circle(g, mix(inner, outer, t), (R, R), k)
        (surf or self.s).blit(g, (round(c[0] * S) - R, round(c[1] * S) - R))

    def glow(self, c, r, col, a=150, surf=None):
        self.radial(c, r, (*col, a), (*col, 0), surf, power=0.6)

    def text(self, t, size, col, center, surf=None, font=BOLD):
        img = pygame.font.Font(font, size * S).render(t, True, col)
        (surf or self.s).blit(img, img.get_rect(center=self.P(center)))

    def shadow(self, draw, off=(4, 6), blur=6, alpha=110):
        """Draw something in black on a layer, blur it (down- and up-scaling), drop it."""
        lay = self.layer()
        draw(lay)
        w, h = lay.get_size()
        small = pygame.transform.smoothscale(lay, (w // blur, h // blur))
        lay = pygame.transform.smoothscale(small, (w, h))
        lay.set_alpha(alpha)
        self.s.blit(lay, (off[0] * S, off[1] * S))

    def tube(self, pts, r, base=(150, 158, 176)):
        """A chrome tube: a dark rim, a mid body, a bright streak toward the light (top left)."""
        pts = [self.P(p) for p in pts]
        R = r * S
        for w, c in ((R * 2 + 2, (30, 30, 40)), (R * 2, mix(base, (40, 44, 60), 0.5)), (R * 1.4, base),
                     (R * 0.7, mix(base, WHITE, 0.55))):
            pygame.draw.lines(self.s, c, False, pts, max(1, round(w)))
        hl = offset([(x / S, y / S) for x, y in pts], -r * 0.35)
        pygame.draw.lines(self.s, WHITE, False, [self.P(p) for p in hl], max(1, round(R * 0.3)))

    def done(self):
        return pygame.transform.smoothscale(self.s, (W, H))


# ---------------------------------------------------------------------------------------------
TY, TW, TH = 70, 322, 462
TX = {1: 16, 2: W - 16 - TW}
FIELD = {1: ((20, 34, 92), (6, 10, 34)), 2: ((92, 20, 40), (34, 6, 14))}


def T(side, x, y):
    return (TX[side] + (x if side == 1 else TW - x), TY + y)


def cabinet_shape(side, inset=0):
    r = 118 - inset
    pts = [T(side, inset, TH - inset), T(side, inset, r + inset)]
    for k in range(25):
        a = math.pi + math.pi / 2 * k / 24
        pts.append(T(side, inset + r + r * math.cos(a), r + inset + r * math.sin(a)))
    for k in range(25):
        a = 1.5 * math.pi + math.pi / 2 * k / 24
        pts.append(T(side, TW - inset - r + r * math.cos(a), r + inset + r * math.sin(a)))
    pts.append(T(side, TW - inset, TH - inset))
    return pts


def backdrop(c):
    c.s.fill((14, 12, 22))
    # the cabinet's dark, brushed bench between and around the tables
    rnd = random.Random(1)
    for y in range(0, H * S, 3):
        k = rnd.uniform(0.85, 1.1)
        pygame.draw.line(c.s, mix((14, 12, 22), (34, 30, 48), k * 0.5), (0, y), (W * S, y), 1)
    c.glow((480, 300), 300, (60, 40, 110), 90)


def playfield(c, side):
    top, bot = FIELD[side]
    col = P1C if side == 1 else P2C
    pf = C()
    # the printed playfield: a deep gradient...
    shape = cabinet_shape(side, 9)
    xs = [p[0] for p in shape]
    x0, x1 = min(xs), max(xs)
    for y in range(TY, TY + TH):
        k = (y - TY) / TH
        pygame.draw.line(pf.s, (*mix(top, bot, k ** 0.8), 255), C.P((x0, y)), C.P((x1, y)), 2 * S)
    # ...printed with a photonic chip: the die and its alignment marks, a mesh of waveguides
    # with directional couplers (a Mach-Zehnder mesh), micro-ring resonators, grating couplers
    # bringing the light in, single-photon detectors at the outputs
    chip(pf, side, col)
    # GI: warm pools of light from the lamps under the plastics
    for p in (T(side, 70, 380), T(side, 250, 380), T(side, 160, 150)):
        pf.glow(p, 90, (255, 220, 160), 40)
    # darker toward the apron and the edges
    pf.radial(T(side, 160, 470), 170, (0, 0, 0, 150), (0, 0, 0, 0), power=0.7)
    # clip to the cabinet's shape
    mask = C()
    mask.poly(shape, (255, 255, 255, 255))
    pf.s.blit(mask.s, (0, 0), special_flags=pygame.BLEND_RGBA_MIN)
    c.s.blit(pf.s, (0, 0))


def waveguide(c, pts, col, lit=0.6):
    """A waveguide: a soft halo round a thin bright core."""
    lay = c.layer()
    c.lines(pts, (*col, round(55 * lit)), 5, lay)
    c.lines(pts, (*mix(col, WHITE, 0.5), round(230 * lit)), 1.0, lay)
    c.blit(lay)


def chip(c, side, col):
    def L(x, y):
        return T(side, x, y)
    die = [L(52, 214), L(266, 214), L(266, 330), L(52, 330)]
    c.poly(die, (*mix(col, WHITE, 0.3), 70), 1.0)
    for x, y in ((52, 214), (266, 214), (266, 330), (52, 330)):          # alignment crosses
        cx, cy = L(x, y)
        c.lines([(cx - 5, cy), (cx + 5, cy)], (*mix(col, WHITE, 0.4), 120), 0.8)
        c.lines([(cx, cy - 5), (cx, cy + 5)], (*mix(col, WHITE, 0.4), 120), 0.8)
    c.text("SiN PHOTONIC CHIP  QPU-2", 5, (*mix(col, WHITE, 0.4), 140), L(159, 322))
    # four waveguides; couplers bring neighbours close (a smooth S-bend in, a parallel run, out)
    base = (236, 258, 280, 302)
    couplers = ((108, 0), (108, 2), (160, 1), (212, 0), (212, 2))     # (x, upper waveguide of the pair)

    def y_at(i, x):
        y = base[i]
        for cx, top in couplers:
            if i not in (top, top + 1):
                continue
            d = max(0.0, abs(x - cx) - 7)                             # a parallel run 14 long...
            k = max(0.0, 1 - d / 20)
            k = k * k * (3 - 2 * k)                                     # ...between smooth S-bends
            y += (7.0 if i == top else -7.0) * k
        return y
    for i in range(4):
        pts = [L(x, y_at(i, x)) for x in range(78, 248, 2)]
        waveguide(c, pts, col, 0.75)
        # a grating coupler on the left (a little fan), a detector meander on the right
        gx, gy = L(72, base[i])
        sgn = 1 if side == 1 else -1
        for k in range(4):
            c.lines([(gx - sgn * (2 + 2 * k), gy - 2 - k), (gx - sgn * (2 + 2 * k), gy + 2 + k)], (*mix(col, WHITE, 0.4), 160), 0.7)
        dx, dy = L(250, base[i])
        mean = [(dx + sgn * (k // 2) * 2.5, dy - 3 + (6 if k % 4 in (1, 2) else 0)) for k in range(10)]
        c.lines(mean, (*mix(col, WHITE, 0.3), 170), 0.8)
    # micro-ring resonators beside the outer waveguides
    for x, i, d in ((134, 0, -1), (186, 3, 1)):
        cx, cy = L(x, base[i] + d * 10)
        lay = c.layer()
        c.circle((cx, cy), 7, (*col, 60), 4, lay)
        c.circle((cx, cy), 7, (*mix(col, WHITE, 0.5), 220), 1.0, lay)
        c.blit(lay)


def side_rails(c, side):
    """The metal side rails and the arched wall around the playfield."""
    outer, inner = cabinet_shape(side, 0), cabinet_shape(side, 9)
    lay = c.layer()
    c.poly(outer, (60, 62, 78, 255), surf=lay)
    c.poly(inner, (0, 0, 0, 0), surf=lay)
    c.s.blit(lay, (0, 0))
    c.lines(outer + [outer[0]], (200, 205, 220), 1.6)
    c.lines(cabinet_shape(side, 4), (120, 126, 150), 3.0)
    c.lines(cabinet_shape(side, 3), (220, 225, 240), 0.8)
    c.lines(inner, (20, 18, 30), 1.6)


def post(c, p):
    c.circle(p, 4.2, (240, 240, 245))
    c.circle(p, 2.4, (120, 124, 140))
    c.circle((p[0] - 0.8, p[1] - 0.8), 1.0, WHITE)


def rubber(c, pts):
    """A white rubber ring stretched round posts."""
    c.lines(pts + [pts[0]], (30, 28, 36), 4.2)
    c.lines(pts + [pts[0]], (236, 236, 240), 2.6)
    for p in pts:
        post(c, p)


def plastic(c, pts, col, art=None):
    """A translucent printed plastic, lit from below."""
    lay = c.layer()
    c.poly(pts, (*col, 150), surf=lay)
    c.blit(lay)
    c.poly(pts, mix(col, WHITE, 0.5), 1.0)
    cx = sum(p[0] for p in pts) / len(pts)
    cy = sum(p[1] for p in pts) / len(pts)
    c.glow((cx, cy), 18, mix(col, WHITE, 0.4), 90)


def insert(c, centre, col, lit, shape="arrow", ang=0, size=9):
    """A translucent playfield insert: dark when off, bright with bloom when lit."""
    a = math.radians(ang)

    def R(x, y):
        return (centre[0] + x * math.cos(a) - y * math.sin(a), centre[1] + x * math.sin(a) + y * math.cos(a))
    if shape == "arrow":
        pts = [R(0, -size), R(size * 0.9, size * 0.3), R(size * 0.35, size * 0.3), R(size * 0.35, size),
               R(-size * 0.35, size), R(-size * 0.35, size * 0.3), R(-size * 0.9, size * 0.3)]
    else:
        pts = [R(size * math.cos(t * math.pi / 8), size * math.sin(t * math.pi / 8)) for t in range(16)]
    if lit:
        c.glow(centre, size * 3, col, 140)
    c.poly(pts, (20, 16, 24), 0)
    inner = [lerp(centre, p, 0.82) for p in pts]
    c.poly(inner, mix(col, WHITE, 0.45) if lit else mix(col, (0, 0, 0), 0.6))
    c.poly([lerp(centre, p, 0.45) for p in pts], mix(col, WHITE, 0.85) if lit else mix(col, (0, 0, 0), 0.4))
    c.circle((centre[0] - size * 0.25, centre[1] - size * 0.35), size * 0.15, (255, 255, 255, 200 if lit else 90))


def bumper(c, p, col, lit):
    """A pop bumper styled as a ring resonator: a chrome rim, a dark glossy cap, and a ring of
    light in the player's colour that flares when it's hit."""
    x, y = p
    c.shadow(lambda l: c.circle((x, y), 20, (0, 0, 0, 255), surf=l), (5, 8), 6, 150)
    c.circle((x, y + 2), 20, (26, 26, 34))                     # the base
    c.radial((x, y + 1), 19, (236, 240, 250, 255), (96, 102, 124, 255), power=0.6)   # chrome rim
    c.circle((x, y), 15, (16, 14, 22))
    c.radial((x, y - 1), 14, (*mix(col, (0, 0, 0), 0.55), 255), (10, 10, 16, 255), power=1.2)   # glossy cap
    if lit:
        c.glow((x, y), 44, col, 150)
    ring = mix(col, WHITE, 0.55 if lit else 0.1)
    lay = c.layer()
    c.circle((x, y - 1), 9, (*col, 120 if lit else 60), 4, lay)
    c.circle((x, y - 1), 9, (*ring, 255), 1.6 if lit else 1.2, lay)
    c.blit(lay)
    c.circle((x, y - 1), 2.2, (*mix(col, WHITE, 0.8 if lit else 0.3), 255))
    # the gloss: one soft highlight across the cap's top
    hl = c.layer()
    pygame.draw.ellipse(hl, (255, 255, 255, 70), (round((x - 9) * S), round((y - 13) * S), 18 * S, 7 * S))
    c.blit(hl)
    c.circle((x - 13, y - 9), 1.6, (255, 255, 255, 230))


def flipper(c, pivot, tip, col):
    px, py = pivot
    tx, ty = tip
    L = math.dist(pivot, tip)
    ux, uy = (tx - px) / L, (ty - py) / L
    nx, ny = -uy, ux

    def body(r0, r1, surf, colour):
        pts = [(px + nx * r0, py + ny * r0), (tx + nx * r1, ty + ny * r1), (tx - nx * r1, ty - ny * r1), (px - nx * r0, py - ny * r0)]
        c.poly(pts, colour, surf=surf)
        c.circle(pivot, r0, colour, surf=surf)
        c.circle(tip, r1, colour, surf=surf)
    c.shadow(lambda l: body(9, 5, l, (0, 0, 0, 255)), (4, 7), 5, 150)
    body(9, 5, None, col)                                       # the rubber
    body(7, 3.4, None, (245, 245, 250))                          # the bat
    c.lines([(px + nx * 4 - 1, py + ny * 4 - 1), (tx + nx * 2, ty + ny * 2)], (255, 255, 255), 1.4)
    c.lines([(px - nx * 4, py - ny * 4), (tx - nx * 2, ty - ny * 2)], (190, 190, 205), 1.4)
    c.circle(pivot, 3.4, (60, 60, 76))
    c.circle(pivot, 2.4, (200, 204, 220))


def ball(c, p, col, k=1.0, trail=()):
    """The photon: a glass sphere glowing in its player's colour (half of one is a faint ghost)."""
    lay = c.layer()
    for i, q in enumerate(trail):
        c.circle(q, 2 + 1.6 * i, (*col, 50 + 40 * i), surf=lay)
    c.glow(p, 30, col, 170, surf=lay)
    c.radial(p, 9, (*mix(col, WHITE, 0.85), 255), (*mix(col, (0, 0, 0), 0.25), 255), surf=lay, power=1.2)
    c.circle(p, 9, (*mix(col, (0, 0, 0), 0.5), 255), 1.0, surf=lay)
    c.circle((p[0] - 3, p[1] - 3.5), 2.6, (255, 255, 255, 240), surf=lay)
    c.circle((p[0] + 3, p[1] + 4), 1.2, (255, 255, 255, 120), surf=lay)
    c.blit(lay, round(255 * (0.5 + 0.5 * k)) if k < 1 else 255)
    if k < 1:          # half a photon: a dashed ring round a see-through ball
        for i in range(10):
            a0 = 2 * math.pi * i / 10
            arc = [(p[0] + 13 * math.cos(a0 + 0.35 * j), p[1] + 13 * math.sin(a0 + 0.35 * j)) for j in range(3)]
            c.lines(arc, mix(col, WHITE, 0.5), 1.2)


def apron(c, side, col):
    """The metal apron across the bottom, printed with the game's name."""
    y0 = 446
    pts = [T(side, 40, y0 + 6), T(side, 120, y0 + 6), T(side, 140, y0), T(side, 182, y0), T(side, 202, y0 + 6),
           T(side, TW - 9, y0 + 6), T(side, TW - 9, TH - 9), T(side, 40, TH - 9)]
    c.shadow(lambda l: c.poly(pts, (0, 0, 0, 255), surf=l), (0, -4), 5, 140)
    c.poly(pts, (178, 182, 198))
    c.lines([pts[0], pts[1], pts[2], pts[3], pts[4], pts[5]], (235, 238, 248), 1.4)
    for k in range(4):
        c.lines([T(side, 46, y0 + 12 + 3 * k), T(side, TW - 14, y0 + 12 + 3 * k)], (165, 170, 188), 0.6)
    c.text("PHOTON PINBALL", 8, mix(col, (20, 20, 30), 0.35), lerp(T(side, 46, TH - 15), T(side, TW - 14, TH - 15), 0.5))


def table(c, side, phase=0, ramp_lit=False, lit=()):
    col = P1C if side == 1 else P2C
    playfield(c, side)
    # top lanes: guides, rollover inserts
    for x in (126, 162, 198, 234):
        c.tube([T(side, x, 44), T(side, x, 74)], 1.6)
    for i, x in enumerate((144, 180, 216)):
        insert(c, T(side, x, 90), AMBER, i != 1, "round", size=5)
    # plunger lane
    c.tube([T(side, 36, 446), T(side, 36, 150), T(side, 72, 76)], 2.0)
    for k in range(9):
        c.lines([T(side, 15, 390 + 4.5 * k), T(side, 29, 392 + 4.5 * k)], (190, 196, 210), 1.0)
    c.poly([T(side, 13, 430), T(side, 31, 430), T(side, 31, 444), T(side, 13, 444)], (200, 40, 40))
    c.poly([T(side, 15, 432), T(side, 22, 432), T(side, 22, 442), T(side, 15, 442)], (255, 120, 120))
    # bumpers
    for i, p in enumerate(((126, 150), (206, 136), (166, 210))):
        bumper(c, T(side, *p), col, i in lit)
    # the ramp's entrance (a chrome-lipped mouth) and its arrows
    m = T(side, 286, 172)
    c.shadow(lambda l: c.poly([(m[0] - 20, m[1] - 14), (m[0] + 20, m[1] - 14), (m[0] + 20, m[1] + 12), (m[0] - 20, m[1] + 12)], (0, 0, 0, 255), surf=l))
    c.poly([(m[0] - 19, m[1] - 13), (m[0] + 19, m[1] - 13), (m[0] + 19, m[1] + 11), (m[0] - 19, m[1] + 11)], (12, 10, 18))
    c.lines([(m[0] - 19, m[1] + 11), (m[0] - 19, m[1] - 13), (m[0] + 19, m[1] - 13), (m[0] + 19, m[1] + 11)], (210, 214, 230), 2.2)
    for k, y in enumerate((212, 240, 268)):
        insert(c, T(side, 286, y), AMBER, ramp_lit, "arrow", 0, 10)
    # the phase target on the outer wall, and its insert
    tg = [T(side, 40, 270), T(side, 54, 270), T(side, 54, 306), T(side, 40, 306)]
    c.shadow(lambda l: c.poly(tg, (0, 0, 0, 255), surf=l), (3, 5))
    c.poly(tg, AMBER if phase else (240, 240, 245))
    c.poly(tg, (40, 36, 50), 1.2)
    c.text("φ", 11, (60, 40, 20) if phase else (60, 60, 80), lerp(tg[0], tg[2], 0.5))
    insert(c, T(side, 76, 288), AMBER, bool(phase), "arrow", -90 if side == 1 else 90, 9)
    # slingshots: a lit plastic over a rubber band, and the inlane guides
    for tri in (((70, 330), (70, 380), (104, 400)), ((252, 330), (252, 380), (218, 400))):
        pts = [T(side, *p) for p in tri]
        plastic(c, pts, col)
        rubber(c, pts)
    c.tube([T(side, 54, 314), T(side, 54, 388), T(side, 112, 420)], 1.8)
    c.tube([T(side, 268, 314), T(side, 268, 388), T(side, 210, 420)], 1.8)
    flipper(c, T(side, 112, 420), T(side, 154, 436), col)
    flipper(c, T(side, 210, 420), T(side, 168, 436), col)
    apron(c, side, col)
    side_rails(c, side)
    # the glass over it all: one soft diagonal sheen
    lay = c.layer()
    a, b = T(side, 40, 10), T(side, 160, 10)
    c.poly([a, b, (b[0] + 160 * (1 if side == 1 else -1), TY + TH), (a[0] + 160 * (1 if side == 1 else -1), TY + TH)], (255, 255, 255, 14), surf=lay)
    mask = C()
    mask.poly(cabinet_shape(side, 9), (255, 255, 255, 255))
    lay.blit(mask.s, (0, 0), special_flags=pygame.BLEND_RGBA_MIN)
    c.blit(lay)


BS1, M1, M2, BS2 = (480, 150), (404, 240), (556, 240), (480, 330)


def glass_cube(c, p):
    x, y = p
    d = 16
    c.shadow(lambda l: c.poly([(x, y - d), (x + d, y), (x, y + d), (x - d, y)], (0, 0, 0, 255), surf=l), (4, 7))
    c.poly([(x, y - d), (x + d, y), (x, y + d), (x - d, y)], (150, 220, 240, 150))
    c.poly([(x, y - d), (x + d, y), (x, y)], (210, 245, 255, 120))
    c.poly([(x, y - d), (x + d, y), (x, y + d), (x - d, y)], (230, 250, 255), 1.4)
    c.lines([(x, y - d + 2), (x, y + d - 2)], (255, 255, 255), 2.0)
    c.lines([(x - 9, y - 3), (x - 3, y - 9)], (255, 255, 255, 220), 1.4)


def mirror(c, p, side):
    x, y = p[0] + side * 4, p[1]
    c.shadow(lambda l: c.poly([(x - 3, y - 20), (x + 3, y - 20), (x + 3, y + 20), (x - 3, y + 20)], (0, 0, 0, 255), surf=l), (4, 6))
    c.poly([(x - 3, y - 20), (x + 3, y - 20), (x + 3, y + 20), (x - 3, y + 20)], (70, 74, 92))
    c.poly([(x - 2, y - 19), (x + 1, y - 19), (x + 1, y + 19), (x - 2, y + 19)], (220, 228, 245))
    c.lines([(x - 1, y - 16), (x - 1, y - 2)], WHITE, 1.0)
    c.circle((x + side * 8, y), 5, (60, 62, 80))
    c.circle((x + side * 8, y), 3, (170, 176, 196))


def plate(c, p, phase, col):
    if phase:
        c.glow(p, 34, col, 160)
    c.circle(p, 11, (30, 28, 40))
    c.radial(p, 10, (*mix(col, WHITE, 0.7 if phase else 0.1), 255), (*mix(col, (0, 0, 0), 0.3 if phase else 0.6), 255), power=1.3)
    c.circle((p[0] - 3, p[1] - 4), 2.6, (255, 255, 255, 200))
    c.text("π" if phase else "0", 10, (255, 255, 255) if phase else (200, 200, 220), (p[0] + 0.5, p[1] + 1))


def bridge(c, phase1, phase2, beam=None):
    # a raised glass deck on chrome posts, over the bench
    deck = [(392, 120), (568, 120), (568, 362), (392, 362)]
    c.shadow(lambda l: c.poly(deck, (0, 0, 0, 255), surf=l), (6, 10), 8, 150)
    c.poly(deck, (24, 22, 40, 235))
    for y in range(126, 360, 10):
        for x in range(398, 566, 10):
            c.circle((x, y), 1.1, (12, 10, 22))
    c.lines(deck + [deck[0]], (170, 176, 200), 1.6)
    c.text("PHOTON BRIDGE", 10, (210, 214, 236), (480, 378))
    for a, b in ((BS1, M1), (BS1, M2), (M1, BS2), (M2, BS2)):
        c.lines([a, b], (60, 58, 84), 2.0)
        if beam:
            lay = c.layer()
            c.lines([a, b], (*beam, 70), 9, lay)
            c.lines([a, b], (*mix(beam, WHITE, 0.6), 230), 2, lay)
            c.blit(lay)
    mirror(c, M1, -1)
    mirror(c, M2, 1)
    glass_cube(c, BS1)
    glass_cube(c, BS2)
    plate(c, lerp(BS1, M1, 0.5), phase1, P1C)
    plate(c, lerp(BS1, M2, 0.5), phase2, P2C)


def ramps(c):
    x0 = TX[1]
    up = [(x0 + 286, TY + 160), (x0 + 292, TY + 96), (x0 + 312, TY + 50), (372, 66), (430, 100), (BS1[0] - 12, BS1[1] - 12)]
    down = [(BS2[0] - 12, BS2[1] + 12), (432, 376), (386, 404), (x0 + 318, TY + 350), (x0 + 294, TY + 322)]
    for path in (up, down):
        for pts in (path, [(W - x, y) for x, y in path]):
            sm = smooth(pts)
            rails = (offset(sm, -5), offset(sm, 5))
            c.shadow(lambda l: [c.lines(r, (0, 0, 0, 255), 4, l) for r in rails], (6, 12), 6, 120)
            for i in range(0, len(sm), 5):
                c.lines([rails[0][i], rails[1][i]], (120, 126, 146), 1.4)
            for r in rails:
                c.tube(r, 1.5, (170, 176, 196))


def dmd(c, scores, balls, clock, msg=None):
    """The dot-matrix display over the middle: both scores, the clock, the call."""
    box = pygame.Rect(318, 6, 324, 56)
    c.shadow(lambda l: pygame.draw.rect(l, (0, 0, 0, 255), (box.x * S, box.y * S, box.w * S, box.h * S), border_radius=6 * S), (3, 5))
    pygame.draw.rect(c.s, (50, 52, 64), (box.x * S, box.y * S, box.w * S, box.h * S), border_radius=6 * S)
    pygame.draw.rect(c.s, (150, 156, 176), (box.x * S, box.y * S, box.w * S, box.h * S), 2 * S, border_radius=6 * S)
    inner = box.inflate(-12, -12)
    pygame.draw.rect(c.s, (16, 6, 4), (inner.x * S, inner.y * S, inner.w * S, inner.h * S))
    # render the content in a tiny bitmap (one pixel per dot), then draw each lit dot
    dots = pygame.Surface((inner.w // 3, inner.h // 3))
    dots.fill((0, 0, 0))
    f = pygame.font.Font("/home/damian/03_personal/games/brawl-ket/src/brawl_ket/assets/fonts/PressStart2P-Regular.ttf", 8)
    if msg:
        img = f.render(msg, False, (255, 255, 255))
        dots.blit(img, img.get_rect(center=(dots.get_width() // 2, dots.get_height() // 2)))
    else:
        small = pygame.font.Font(BOLD, 7)
        dots.blit(small.render(f"{scores[0]:,}", False, (255, 255, 255)), (2, 1))
        r = small.render(f"{scores[1]:,}", False, (255, 255, 255))
        dots.blit(r, (dots.get_width() - r.get_width() - 2, 1))
        t = f.render(clock, False, (255, 255, 255))
        dots.blit(t, t.get_rect(center=(dots.get_width() // 2, dots.get_height() // 2)))
        for i in range(3):
            for side, x in ((0, 2 + 4 * i), (1, dots.get_width() - 5 - 4 * i)):
                if i < balls[side]:
                    pygame.draw.rect(dots, (255, 255, 255), (x, 10, 3, 3))
    for y in range(dots.get_height()):
        for x in range(dots.get_width()):
            on = dots.get_at((x, y))[0] > 100
            p = (inner.x + 1.5 + x * 3, inner.y + 1.5 + y * 3)
            pygame.draw.circle(c.s, (255, 140, 30) if on else (44, 16, 8), (round(p[0] * S), round(p[1] * S)), round(1.2 * S))
    glow = c.layer()
    c.blit(glow)


def stamp(c, p, msg, col):
    c.glow(p, 70, col, 70)
    img = pygame.font.Font(BOLD, 22 * S).render(msg, True, mix(col, WHITE, 0.5))
    edge = pygame.font.Font(BOLD, 22 * S).render(msg, True, (20, 10, 20))
    r = img.get_rect(center=C.P(p))
    for dx, dy in ((-3, 0), (3, 0), (0, -3), (0, 4), (3, 4)):
        c.s.blit(edge, r.move(dx, dy))
    c.s.blit(img, r)


def frame(phase1=0, phase2=0, ramp_lit=False, scores=(124500, 98000), balls=(3, 2), lit1=(), lit2=(), beam=None, msg=None):
    c = C()
    backdrop(c)
    table(c, 1, phase1, ramp_lit, lit1)
    table(c, 2, phase2, False, lit2)
    bridge(c, phase1, phase2, beam)
    ramps(c)
    dmd(c, scores, balls, "1:24", msg)
    return c


P2_BALL = T(2, 200, 296)
P2_TRAIL = [T(2, 206, 318 - 7 * i) for i in (2, 1, 0)]


def f_ramp():
    c = frame(ramp_lit=True, lit1=(1,))
    ball(c, T(1, 286, 196), P1C, 1, [T(1, 286, 244 - 12 * i) for i in (2, 1, 0)])
    ball(c, P2_BALL, P2C, 1, P2_TRAIL)
    c.text("A  FLIPPERS      STICK  PLUNGER", 10, (200, 204, 226), (480, 524))
    return c.done()


def f_split():
    c = frame(beam=P1C, lit2=(0,), msg="SPLIT!")
    for m in (M1, M2):
        ball(c, lerp(m, BS2, 0.45), P1C, 0.5)
    ball(c, P2_BALL, P2C, 1, P2_TRAIL)
    return c.done()


def f_cross():
    c = frame(lit2=(0, 2), scores=(149500, 98000), msg="INCOMING!")
    ball(c, T(2, 292, 330), P1C, 1, [T(2, 314 - 7 * i, 354 - 7 * i) for i in (0, 1, 2)])
    ball(c, P2_BALL, P2C, 1, P2_TRAIL)
    stamp(c, T(2, 160, 250), "INCOMING!", P1C)
    return c.done()


def f_bounce():
    c = frame(phase2=1, lit1=(0,), msg="BOUNCED!")
    ball(c, T(1, 292, 330), P1C, 1, [T(1, 314 - 7 * i, 354 - 7 * i) for i in (0, 1, 2)])
    ball(c, T(2, 66, 286), P2C, 1, [T(2, 84 + 9 * i, 296 + 7 * i) for i in (2, 1, 0)])
    stamp(c, T(1, 160, 250), "BOUNCED BACK!", P2C)
    return c.done()


if __name__ == "__main__":
    out = sys.argv[1]
    only = sys.argv[2] if len(sys.argv) > 2 else None
    frames = [("1  SHOOT THE RAMP", f_ramp), ("2  ON THE BRIDGE THE BALL SPLITS", f_split),
              ("3  EQUAL PHASES: ONTO THE RIVAL'S TABLE", f_cross), ("4  P2 HIT ITS TARGET (π): IT COMES BACK", f_bounce)]
    if only:
        frames = [frames[int(only) - 1]]
    imgs = []
    for i, (cap, fn) in enumerate(frames):
        f = fn()
        imgs.append((cap, f))
        pygame.image.save(f, os.path.join(out, f"real{only or i + 1}.png"))
    if not only:
        sheet = pygame.Surface((2 * W + 30, 2 * H + 90))
        sheet.fill((10, 8, 16))
        capf = pygame.font.Font(BOLD, 16)
        for i, (cap, f) in enumerate(imgs):
            x, y = 10 + (i % 2) * (W + 10), 34 + (i // 2) * (H + 40)
            sheet.blit(capf.render(cap, True, (236, 236, 250)), (x, y - 26))
            sheet.blit(f, (x, y))
        pygame.image.save(sheet, os.path.join(out, "real_sheet.png"))
    print("saved")
