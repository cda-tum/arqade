"""The approved look for GATE PRIX (2026-10-12): the mockup renderer that drew it.

A reference for the game's art, not part of it. Run with pygame 2.5.2:
    uv run --directory brawl-ket python ../docs/superpowers/specs/2026-10-12-gate-prix-look.py OUT.png
It uses the DejaVu Sans Condensed Bold system font.
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
W, VH, S = 960, 270, 2          # screen width, one view's height, supersampling
WHITE = (255, 255, 255)
GATE = {"H": (248, 192, 40), "X": (232, 64, 72), "Z": (56, 120, 232), "Y": (168, 80, 216)}
P1C, P2C = (80, 170, 255), (255, 80, 90)


def mix(a, b, k):
    return tuple(round(x + (y - x) * k) for x, y in zip(a, b))


_f = {}


def font(n):
    if n not in _f:
        _f[n] = pygame.font.Font(BOLD, n * S)
    return _f[n]


class V:
    """One player's view, drawn at S x and smoothed down."""

    def __init__(self):
        self.s = pygame.Surface((W * S, VH * S), pygame.SRCALPHA)

    def P(self, p):
        return (round(p[0] * S), round(p[1] * S))

    def poly(self, pts, col, w=0):
        pygame.draw.polygon(self.s, col, [self.P(p) for p in pts], round(w * S))

    def line(self, a, b, col, w=1):
        pygame.draw.line(self.s, col, self.P(a), self.P(b), max(1, round(w * S)))

    def circle(self, c, r, col, w=0):
        pygame.draw.circle(self.s, col, self.P(c), max(1, round(r * S)), round(w * S))

    def rect(self, r, col, w=0, rad=0):
        pygame.draw.rect(self.s, col, [round(v * S) for v in r], round(w * S), border_radius=round(rad * S))

    def glow(self, c, r, col, a=140):
        R = max(2, round(r * S))
        g = pygame.Surface((2 * R, 2 * R), pygame.SRCALPHA)
        for k in range(R, 0, -2):
            pygame.draw.circle(g, (*col, min(255, round(a * (1 - k / R) ** 1.4))), (R, R), k)
        self.s.blit(g, (round(c[0] * S) - R, round(c[1] * S) - R))

    def text(self, t, n, col, center=None, topleft=None, midleft=None, shadow=True):
        img = font(n).render(t, True, col)
        r = img.get_rect()
        if center:
            r.center = self.P(center)
        elif midleft:
            r.midleft = self.P(midleft)
        else:
            r.topleft = self.P(topleft)
        if shadow:
            sh = font(n).render(t, True, (8, 8, 20))
            self.s.blit(sh, r.move(2 * S // 2, 2 * S // 2))
        self.s.blit(img, r)

    def done(self):
        return pygame.transform.smoothscale(self.s, (W, VH))


HORIZON = 112
SEG, N, ROAD_W, CAM_H, DEPTH = 200.0, 140, 1500.0, 1000.0, 0.84


def project(wx, wy, z, cam_x, cam_y):
    p = DEPTH / z
    return W / 2 + p * (wx - cam_x) * W / 2, HORIZON - p * (wy - cam_y) * VH / 2, p * ROAD_W * W / 2


def background(v, t):
    # the inside of the fridge: a cold radiation-shield wall, the next stage's gold plate overhead
    for y in range(0, HORIZON + 4):
        k = y / HORIZON
        col = mix((10, 14, 34), (96, 150, 200), k ** 2.2)
        v.line((0, y), (W, y), col, 1.2)
    # the shield wall's panels and bolts, receding
    for i in range(-12, 13):
        x = W / 2 + i * 46 + (t * 3) % 46
        v.line((x, 30), (x + i * 2.5, HORIZON), (*mix((20, 30, 60), (110, 160, 210), 0.35), ), 1)
    # hanging coax far away
    rnd = random.Random(3)
    for _ in range(26):
        x = rnd.uniform(0, W)
        y1 = rnd.uniform(60, HORIZON - 4)
        v.line((x, 0), (x, y1), mix((70, 90, 120), (150, 170, 190), rnd.random()), 1.2)
        v.circle((x, y1), 1.6, (200, 170, 90))
    # the next stage's plate overhead: a gold disc seen from below, with its standoffs
    plate = [(0, 0), (W, 0), (W, 26), (W * 0.82, 40), (W * 0.5, 46), (W * 0.18, 40), (0, 26)]
    v.poly(plate, (150, 110, 40))
    v.poly([(0, 0), (W, 0), (W, 18), (W * 0.5, 34), (0, 18)], (196, 150, 60))
    for k in range(0, 9):
        x = 40 + k * 110
        v.line((x, 30 + 8 * math.sin(k)), (x, 70), (210, 200, 180), 2)
        v.circle((x, 30 + 8 * math.sin(k)), 3, (240, 220, 160))
    v.line((0, 26), (W * 0.18, 40), (240, 210, 120), 1)
    v.line((W * 0.18, 40), (W * 0.5, 46), (240, 210, 120), 1)
    v.line((W * 0.5, 46), (W * 0.82, 40), (240, 210, 120), 1)
    v.line((W * 0.82, 40), (W, 26), (240, 210, 120), 1)
    # cold mist at the horizon
    mist = pygame.Surface((W * S, 40 * S), pygame.SRCALPHA)
    for y in range(40 * S):
        a = round(110 * (1 - abs(y - 20 * S) / (20 * S)))
        pygame.draw.line(mist, (180, 220, 255, a), (0, y), (W * S, y))
    v.s.blit(mist, (0, (HORIZON - 20) * S))


def track(n):
    """Curve and hill of segment n (relative to the camera's segment)."""
    curve = 0.0
    if 18 < n < 70:
        curve = 1.6 * math.sin((n - 18) / 52 * math.pi)
    hill = 900 * math.sin(n / 34.0)
    return curve, hill


def road(v, phase, cam_x, sprites):
    """Draw the road far to near; collect projected sprite anchors."""
    pts = []
    x, dx = 0.0, 0.0
    for n in range(N):
        curve, hill = track(n)
        z = n * SEG + SEG * (1 - phase)
        pts.append((x, hill, z, n))
        dx += curve
        x += dx
    cam_y = CAM_H + pts[0][1]
    proj = [project(px, py, z, cam_x, cam_y) + (n,) for px, py, z, n in pts]
    clip = VH
    segs = []
    for i in range(N - 1):
        segs.append((proj[i], proj[i + 1]))
    # near to far for clipping (hills hide the road behind them), drawn far to near
    visible = []
    maxy = VH
    for a, b in segs:
        if b[1] < maxy:
            visible.append((a, b))
            maxy = min(maxy, b[1])
    del clip
    for a, b in reversed(visible):
        (x1, y1, w1, n1), (x2, y2, w2, _) = a, b
        if y1 < y2:
            continue
        odd = (n1 // 2) % 2
        # the copper plate either side, machined in rings
        v.poly([(0, y2), (W, y2), (W, y1), (0, y1)], (184, 116, 64) if odd else (168, 104, 56))
        # rumble strips: gold and white
        r1, r2 = w1 * 1.12, w2 * 1.12
        v.poly([(x1 - r1, y1), (x2 - r2, y2), (x2 + r2, y2), (x1 + r1, y1)], (250, 240, 220) if odd else (220, 170, 60))
        # the road: dark anodised, a faint sheen
        v.poly([(x1 - w1, y1), (x2 - w2, y2), (x2 + w2, y2), (x1 + w1, y1)], (34, 36, 54) if odd else (40, 42, 62))
        # centre dashes: thin cyan lines like a waveguide
        if odd:
            lw1, lw2 = w1 * 0.015, w2 * 0.015
            v.poly([(x1 - lw1, y1), (x2 - lw2, y2), (x2 + lw2, y2), (x1 + lw1, y1)], (120, 220, 255))
    for (x1, y1, w1, n1), _ in visible:
        for kind, n, off in sprites:
            if n == n1:
                sprites_drawn.append((kind, x1 + off * w1, y1, w1, n1))


sprites_drawn = []


def coax_tree(v, x, y, s):
    """A semi-rigid coax line rising from the plate, with an SMA nut and an attenuator."""
    h = 260 * s
    w = max(1.0, 9 * s)
    v.rect((x - w / 2, y - h, w, h), (210, 200, 180))
    v.rect((x - w / 2, y - h, w * 0.35, h), (250, 245, 230))
    v.rect((x - w, y - h * 0.62, w * 2, h * 0.08), (220, 170, 60))
    v.rect((x - w * 1.2, y - h * 0.3, w * 2.4, h * 0.12), (196, 150, 60), rad=2 * s)
    v.rect((x - w * 1.2, y - h * 0.3, w * 2.4, h * 0.03), (255, 230, 150))
    v.circle((x, y - h), w * 0.9, (255, 220, 140))


def arch(v, x, y, s, gate, lit=False):
    """A gate: a semicircular arch standing on the track, both feet on the road, a light
    curtain under it and the gate's letter on a badge at its crown."""
    col = GATE[gate]
    r = 150 * s                      # the arch's outer radius (its feet are 2r apart)
    t = max(2.0, 24 * s)             # its thickness
    c = (x, y)                       # the circle's centre sits on the road
    box = (round((c[0] - r) * S), round((c[1] - r) * S), round(2 * r * S), round(2 * r * S))
    inner = (round((c[0] - r + t) * S), round((c[1] - r + t) * S), round(2 * (r - t) * S), round(2 * (r - t) * S))
    if lit:
        v.glow((x, y - r * 0.55), r * 1.6, col, 120)
    # its shadow on the track
    sh = pygame.Surface(v.s.get_size(), pygame.SRCALPHA)
    pygame.draw.ellipse(sh, (0, 0, 0, 110), [round(q * S) for q in (x - r * 1.05, y - r * 0.05, r * 2.1, r * 0.14)])
    v.s.blit(sh, (0, 0))
    # the light curtain under the arch: the upper half of the inner disc
    lay = pygame.Surface(v.s.get_size(), pygame.SRCALPHA)
    pygame.draw.ellipse(lay, (*col, 50 if not lit else 85), inner)
    lay.fill((0, 0, 0, 0), (0, round(y * S), lay.get_width(), lay.get_height()))
    v.s.blit(lay, (0, 0))
    # the arch: a dark rim, its colour, a bright highlight along its upper left
    arc = pygame.Surface(v.s.get_size(), pygame.SRCALPHA)
    pygame.draw.arc(arc, (*mix(col, (10, 10, 20), 0.55), 255), box, 0, math.pi, max(1, round(t * S)))
    ib = (box[0] + round(t * 0.12 * S), box[1] + round(t * 0.12 * S), box[2] - round(t * 0.24 * S), box[3] - round(t * 0.24 * S))
    pygame.draw.arc(arc, (*col, 255), ib, 0, math.pi, max(1, round(t * 0.72 * S)))
    hb = (box[0] + round(t * 0.3 * S), box[1] + round(t * 0.3 * S), box[2] - round(t * 0.6 * S), box[3] - round(t * 0.6 * S))
    pygame.draw.arc(arc, (*mix(col, WHITE, 0.6), 230), hb, math.radians(100), math.radians(165), max(1, round(t * 0.22 * S)))
    v.s.blit(arc, (0, 0))
    # its feet on the road
    for fx in (-1, 1):
        v.rect((x + fx * (r - t / 2) - t * 0.65, y - t * 0.5, t * 1.3, t * 0.6), mix(col, (20, 20, 30), 0.45), rad=2)
    # the badge at the crown
    bw = max(10, 64 * s)
    v.circle((x, y - r), bw * 0.55, (14, 16, 30))
    v.circle((x, y - r), bw * 0.48, col)
    v.text(gate, max(8, round(54 * s)), WHITE, center=(x, y - r + 1))


def car(v, x, y, s, col, boost=False, ghost=False):
    """A racer from behind: a low wedge, a rear wing, glowing tail lights."""
    w, h = 300 * s, 120 * s
    if boost:
        for k in range(3):
            v.glow((x - w * 0.22, y - h * 0.35), 40 * s * (1.4 - 0.3 * k), (140, 220, 255), 150)
            v.glow((x + w * 0.22, y - h * 0.35), 40 * s * (1.4 - 0.3 * k), (140, 220, 255), 150)
    shadow = pygame.Surface(v.s.get_size(), pygame.SRCALPHA)
    pygame.draw.ellipse(shadow, (0, 0, 0, 120), [round(c * S) for c in (x - w * 0.6, y - h * 0.12, w * 1.2, h * 0.3)])
    v.s.blit(shadow, (0, 0))
    body = [(x - w / 2, y), (x - w * 0.44, y - h * 0.55), (x - w * 0.25, y - h * 0.8), (x + w * 0.25, y - h * 0.8),
            (x + w * 0.44, y - h * 0.55), (x + w / 2, y)]
    v.poly(body, mix(col, (10, 10, 20), 0.35))
    v.poly([(x - w * 0.44, y - h * 0.55), (x - w * 0.25, y - h * 0.8), (x + w * 0.25, y - h * 0.8), (x + w * 0.44, y - h * 0.55)], col)
    v.poly([(x - w * 0.22, y - h * 0.78), (x + w * 0.22, y - h * 0.78), (x + w * 0.16, y - h * 0.95), (x - w * 0.16, y - h * 0.95)], (30, 40, 70))
    v.poly([(x - w * 0.2, y - h * 0.8), (x - w * 0.05, y - h * 0.8), (x - w * 0.1, y - h * 0.92), (x - w * 0.16, y - h * 0.92)], (140, 180, 230))
    # rear wing
    v.rect((x - w * 0.5, y - h * 1.08, w, h * 0.12), mix(col, (10, 10, 20), 0.2), rad=3 * s)
    v.rect((x - w * 0.5, y - h * 1.08, w, h * 0.04), mix(col, WHITE, 0.5), rad=3 * s)
    for sx in (-0.42, 0.38):
        v.rect((x + w * sx, y - h * 1.0, w * 0.04, h * 0.45), (40, 40, 60))
    # tail lights and wheels
    for sx in (-1, 1):
        v.rect((x + sx * w * 0.33 - w * 0.08, y - h * 0.45, w * 0.16, h * 0.12), (255, 60, 70), rad=2 * s)
        v.glow((x + sx * w * 0.33, y - h * 0.39), 24 * s, (255, 80, 90), 140)
        v.rect((x + sx * w * 0.5 - w * 0.07, y - h * 0.32, w * 0.14, h * 0.34), (18, 18, 26), rad=4 * s)
    # the qubit it carries: a small Bloch orb on the engine cover
    v.glow((x, y - h * 0.62), 26 * s, (200, 240, 255), 160)
    v.circle((x, y - h * 0.62), 12 * s, (230, 248, 255))
    v.circle((x, y - h * 0.62), 12 * s, (90, 160, 220), 1.5 * s)


def speed_lines(v, col):
    rnd = random.Random(7)
    lay = pygame.Surface(v.s.get_size(), pygame.SRCALPHA)
    cx, cy = W / 2, HORIZON
    for _ in range(48):
        a = rnd.uniform(0, 2 * math.pi)
        r0 = rnd.uniform(260, 380)
        r1 = r0 + rnd.uniform(60, 160)
        p0 = (cx + r0 * math.cos(a), cy + r0 * 0.45 * math.sin(a))
        p1 = (cx + r1 * math.cos(a), cy + r1 * 0.45 * math.sin(a))
        pygame.draw.line(lay, (*col, 120), v.P(p0), v.P(p1), 2 * S)
    v.s.blit(lay, (0, 0))


def gate_box(v, x, y, g, size, state=None, nxt=False):
    col = GATE[g]
    if nxt:
        v.glow((x + size / 2, y + size / 2), size * 1.2, col, 150)
    v.rect((x, y, size, size), (14, 16, 30), rad=4)
    v.rect((x + 1.5, y + 1.5, size - 3, size - 3), col if state != "dim" else mix(col, (14, 16, 30), 0.65), rad=3)
    v.text(g, round(size * 0.62), WHITE if state != "dim" else (170, 170, 190), center=(x + size / 2, y + size / 2 + 1), shadow=False)
    if nxt:
        v.rect((x - 2, y - 2, size + 4, size + 4), WHITE, 2, rad=5)
    if state == "ok":
        v.circle((x + size - 3, y + 3), 6, (60, 200, 110))
        v.text("✓", 9, WHITE, center=(x + size - 3, y + 3), shadow=False)
    if state == "bad":
        v.circle((x + size - 3, y + 3), 6, (230, 60, 70))
        v.text("✗", 9, WHITE, center=(x + size - 3, y + 3), shadow=False)


def hud(v, col, place, lap, streak, item, target, mine, nxt):
    # the circuit overlay: the target's wire on top, yours underneath
    panel = (12, 8, 26 + 26 * len(target), 70)
    lay = pygame.Surface(v.s.get_size(), pygame.SRCALPHA)
    pygame.draw.rect(lay, (8, 10, 24, 190), [round(c * S) for c in panel], border_radius=8 * S)
    v.s.blit(lay, (0, 0))
    v.rect(panel, mix(col, WHITE, 0.2), 1.5, rad=8)
    v.text("TARGET", 8, (190, 200, 230), midleft=(20, 20))
    v.text("YOU", 8, (190, 200, 230), midleft=(20, 52))
    x0 = 66
    v.line((x0 - 6, 22), (x0 + 26 * len(target), 22), (150, 160, 190), 1.5)
    v.line((x0 - 6, 54), (x0 + 26 * len(target), 54), (150, 160, 190), 1.5)
    for i, g in enumerate(target):
        gate_box(v, x0 + 26 * i, 12, g, 20, "dim" if i < nxt else None, i == nxt)
    for i, (g, ok) in enumerate(mine):
        gate_box(v, x0 + 26 * i, 44, g, 20, "ok" if ok else "bad")
    # place, lap, streak, item slot
    v.text(place, 26, WHITE, center=(W - 70, 30))
    v.text(lap, 11, (200, 210, 235), center=(W - 70, 58))
    if streak:
        v.text(f"STREAK x{streak}", 14, (150, 230, 255), center=(W - 200, 26))
        v.text("LIGHT-SPEED BOOST", 8, (150, 230, 255), center=(W - 200, 44))
    box = (W - 330, 10, 52, 52)
    v.rect(box, (12, 14, 30), rad=8)
    v.rect(box, mix(col, WHITE, 0.3), 2, rad=8)
    if item == "SPLIT":
        for dx in (-9, 9):
            v.circle((box[0] + 26 + dx, box[1] + 24), 10, mix(col, WHITE, 0.4), 2)
        v.text("SPLIT", 8, WHITE, center=(box[0] + 26, box[1] + 45), shadow=False)
    elif item == "QEC":
        v.text("QEC", 14, (120, 230, 160), center=(box[0] + 26, box[1] + 22), shadow=False)
        v.text("FIX GATE", 7, WHITE, center=(box[0] + 26, box[1] + 42), shadow=False)


def view(player):
    global sprites_drawn
    sprites_drawn = []
    v = V()
    t = 0.0 if player == 1 else 1.7
    background(v, t)
    # roadside coax trees, arches, a rival car, CPU racers
    sprites = []
    for n in range(6, N - 4, 5):
        sprites.append(("tree", n, -1.55 if (n // 5) % 2 else 1.55))
        if n % 10 == 1:
            sprites.append(("tree", n, -2.3))
    if player == 1:
        sprites.append(("arch:H", 18, 0.45))           # one gate, open road beside it
        sprites.append(("cpu", 30, 0.35))
        sprites.append(("cpu2", 40, -0.3))
        cam_x = 120
    else:
        for g, off in (("Z", -0.55), ("X", 0.5)):      # two gates and a gap between them
            sprites.append(("arch:" + g, 16, off))
        sprites.append(("p1car", 22, -0.2))
        cam_x = -260
    road(v, 0.35, cam_x, sprites)
    for kind, x, y, w, n in sorted(sprites_drawn, key=lambda s: -s[4]):
        s = w / (W / 2) * 0.9
        if kind == "tree":
            coax_tree(v, x, y, s)
        elif kind.startswith("arch:"):
            arch(v, x, y, s, kind[5:], lit=(kind[5:] == ("H" if player == 1 else "Z")))
        elif kind == "cpu":
            car(v, x, y, s, (120, 210, 140))
        elif kind == "cpu2":
            car(v, x, y, s, (220, 220, 230))
        elif kind == "p1car":
            car(v, x, y, s, P1C, boost=True)
    if player == 1:
        speed_lines(v, (150, 220, 255))
        car(v, W / 2 + 10, VH - 10, 0.82, P1C, boost=True)
        hud(v, P1C, "2nd", "LAP 1/3", 3, "SPLIT", list("HXZHYXHZ"),
            [("H", True), ("X", True), ("Z", True)], 3)
    else:
        car(v, W / 2 - 20, VH - 10, 0.82, P2C)
        hud(v, P2C, "4th", "LAP 1/3", 0, "QEC", list("HXZHYXHZ"),
            [("H", True), ("Z", False)], 2)
    tag = "P1" if player == 1 else "P2"
    v.text(tag, 16, P1C if player == 1 else P2C, topleft=(14, VH - 30))
    return v.done()


if __name__ == "__main__":
    out = sys.argv[1]
    screen = pygame.Surface((W, 540))
    screen.blit(view(1), (0, 0))
    screen.blit(view(2), (0, 270))
    pygame.draw.line(screen, (10, 10, 20), (0, 270), (W, 270), 4)
    pygame.draw.line(screen, (200, 205, 225), (0, 269), (W, 269), 1)
    pygame.image.save(screen, out)
    print("saved", out)
