"""
ION SURFER  -  arcade edition (pygame 2.5)

Shape the trap potential with the electrodes on the floor and keep your ion on screen.

Game state, physics and drawing. CLI / entry point: main.py; input mapping:
config.py / input.py.
"""
import asyncio
import json
import math
import random
from pathlib import Path

import pygame
from arqade_common import runtime, web
from arqade_common.input import KEYBOARD

from ion_surfer import sound
from ion_surfer.config import FPS, INTERNAL_HEIGHT, INTERNAL_WIDTH, SCORE_FILE
from ion_surfer.display import make_display, present
from ion_surfer.input import Controls, keyboard_enabled
from ion_surfer.sandbox import SANDBOX_RATE, Sandbox, start_voltages
from ion_surfer.sound import Sounds

# ============================== TUNING ==============================
W, H = INTERNAL_WIDTH, INTERNAL_HEIGHT   # logical resolution (scaled to the display)

GROUND = H - 78
EW = 100                         # electrode pitch
G = 1300                         # pseudo gravity
R = 11                           # ion radius
VMIN, VMAX = 24, GROUND - 60
RATE = 480                       # voltage change per second while holding up/down
STEP = 1 / 240                   # physics step
CAM_BASE = 28                    # start scroll speed (px/s)
CAM_ACCEL = 0.35                 # added scroll speed per second, no upper limit
LASER_UP, LASER_DOWN = 3400, 2600
COULOMB = 5.5e6
BEAM_W0, BEAM_ZR = EW * 0.17, 119
HOLE_PULL, HOLE_CAPTURE, HOLE_RANGE = 1.6e6, 20, 150
BEAM_HEAR, STRAY_HEAR = 280, 360   # px from an ion at which a beam / stray starts to get louder

FONT_DIR = Path(__file__).parent / "assets" / "fonts"
# ======================================================================

BLUE, RED, COOP = (78, 168, 255), (255, 84, 112), (199, 155, 255)
GOLD = (255, 211, 107)
STRAY_C = (255, 143, 214)
TEXT_DIM = (142, 153, 194)
SEED_CHARS = [" "] + list("ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789")
SEED_LEN = 8


def clamp(v, a, b):
    return a if v < a else b if v > b else v


def sy(y):
    return GROUND - y


def beam_half(y):
    return BEAM_W0 * math.sqrt(1 + ((y - GROUND / 2) / BEAM_ZR) ** 2)


def hsh(n):
    v = math.sin(n * 12.9898) * 43758.5453
    return v - math.floor(v)


def scale_col(c, a):
    return (int(c[0] * a), int(c[1] * a), int(c[2] * a))


def random_seed():
    chars = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
    return "".join(random.choice(chars) for _ in range(6))


# ------------------------------ entities ------------------------------
class Ent:
    def __init__(self, **kw):
        self.got = False
        self.dead = False
        self.inv = 0
        self.__dict__.update(kw)


class Curve:
    def __init__(self, color):
        self.color = color
        self.v = []
        self.changes = []


class Ion:
    def __init__(self, curve, color, name, x):
        self.curve, self.color, self.name = curve, color, name
        self.x, self.y, self.vx, self.vy = x, 0.0, 0.0, 0.0
        self.max_x = self.start_x = x
        self.bonus = 0
        self.lives = 3
        self.alive = True
        self.inv = 0.0
        self.trail = []


class Cursor:
    def __init__(self, curve, color, pads, sel):
        self.curve, self.color, self.pads, self.sel = curve, color, pads, sel


# ------------------------------ graphics helpers ------------------------------
def load_font(fname, size, fallback_scale=1.3):
    path = FONT_DIR / fname
    if path.exists():
        try:
            return pygame.font.Font(str(path), size)
        except Exception:
            pass
    return pygame.font.Font(None, int(size * fallback_scale))


def make_glow(color, radius, power=2.0):
    s = pygame.Surface((radius * 2, radius * 2))
    s.fill((0, 0, 0))
    for r in range(radius, 0, -1):
        a = (1 - r / radius) ** power
        pygame.draw.circle(s, scale_col(color, a), (radius, radius), r)
    return s


def make_vgrad(w, h, top, bot):
    s = pygame.Surface((w, h))
    for y in range(h):
        f = y / max(1, h - 1)
        s.fill(tuple(int(top[i] + (bot[i] - top[i]) * f) for i in range(3)), (0, y, w, 1))
    return s


def make_hatch(color):
    s = pygame.Surface((W + 24, H), pygame.SRCALPHA)
    for k in range(-H, W + 24, 12):
        pygame.draw.line(s, color, (k, H), (k + H, 0), 2)
    return s


def make_hole_sprite(radius):
    s = pygame.Surface((radius * 2, radius * 2), pygame.SRCALPHA)
    for r in range(radius, 0, -1):
        f = r / radius
        if f < 0.25:
            c = (4, 2, 10, 255)
        elif f < 0.45:
            k = (f - 0.25) / 0.2
            c = (int(10 + 110 * k), int(4 + 56 * k), int(20 + 180 * k), int(250 - 160 * k))
        else:
            k = (f - 0.45) / 0.55
            c = (int(120 - 60 * k), int(60 - 40 * k), int(200 - 80 * k), int(90 * (1 - k)))
        pygame.draw.circle(s, c, (radius, radius), r)
    return s


def text(surf, s, font, color, pos, anchor="center", alpha=None):
    img = font.render(s, True, color)
    if alpha is not None:
        img.set_alpha(int(clamp(alpha, 0, 1) * 255))
    r = img.get_rect(**{anchor: pos})
    surf.blit(img, r)
    return r


# ------------------------------ game ------------------------------
SANDBOX = 4  # mode number of the sandbox, picked from the main menu


KEYBOARD_STICKS = {"p1": "WASD", "p2": "ARROWS"}  # the keys that stand in for each player's stick
# Same as the folder name in the web build and the "id" in game.json.
GAME_ID = "ion-surfer"


class Game:
    def __init__(self, screen, sandbox_only=False, sounds=None, pad_layout=None):
        self.screen = screen
        self.sandbox_only = sandbox_only
        self.running = True
        self.controls = Controls(pad_layout)
        self.sounds = sounds or Sounds()  # silent unless run() built real ones
        self.tutorial = None
        self.f_title = load_font("Bungee-Regular.ttf", 54)
        self.f_big = load_font("Bungee-Regular.ttf", 22)
        self.f_hud = load_font("Bungee-Regular.ttf", 20)
        self.f_item = load_font("Rubik-Medium.ttf", 24)
        self.f_small = load_font("Rubik-Medium.ttf", 15)
        self.f_tiny = load_font("Rubik-Medium.ttf", 12)
        self.f_plus = load_font("Rubik-Medium.ttf", 12)

        self.bg = make_vgrad(W, H, (6, 10, 24), (16, 26, 58))
        self.fx = pygame.Surface((W, H), pygame.SRCALPHA)
        self.layer = pygame.Surface((W, H), pygame.SRCALPHA)
        self.hatch_cap = make_hatch((255, 90, 130, 80))
        self.hatch_block = make_hatch((140, 160, 230, 45))
        self.glows = {}
        self.hole_sprite = make_hole_sprite(int(HOLE_RANGE * 0.6))
        self.plate_gold = make_vgrad(EW - 16, 28, (242, 207, 115), (138, 100, 32))
        self.plate_lit = make_vgrad(EW - 16, 28, (230, 214, 255), (138, 92, 240))
        self.warn = pygame.Surface((60, GROUND), pygame.SRCALPHA)
        for x in range(60):
            pygame.draw.line(self.warn, (255, 60, 90, int(70 * (1 - x / 60))), (x, 0), (x, GROUND))
        self.dim = pygame.Surface((W, H), pygame.SRCALPHA)
        self.dim.fill((4, 7, 18, 190))

        self.best = {}
        try:
            with open(SCORE_FILE) as fh:
                self.best = json.load(fh)
        except Exception:
            self.best = {}

        self.seed_chars = [" "] * SEED_LEN
        self.seed_edit = False
        self.seed_slot = 0
        self.menu_sel = 0
        self.mode = 1
        self.current_seed = ""
        self.sandbox = None
        self.new_world(random_seed())
        self.state = "menu"
        if sandbox_only:
            self.start(SANDBOX)

    # ---------- world setup ----------
    def glow(self, color, radius):
        key = (color, radius)
        if key not in self.glows:
            self.glows[key] = make_glow(color, radius)
        return self.glows[key]

    def new_world(self, seed):
        self.current_seed = seed
        self.lrng = random.Random(seed)
        self.seed_a = self.lrng.random() * 10
        self.seed_b = self.lrng.random() * 10
        self.t = 0.0
        self.cam_x = 0.0
        self.cam_speed = CAM_BASE
        self.next_spawn = 1500.0
        self.ents, self.parts, self.texts = [], [], []
        self.caps, self.defects = [], []
        self.acc = 0.0
        c = Curve(BLUE)
        self.curves = [c]
        self.ions = [Ion(c, BLUE, "Blue", 450)]
        self.cursors = []
        self.ions[0].y = self.potential(c, 450) + R + 20

    def start(self, mode, seed=None):
        self.mode = mode
        self.new_world(seed or random_seed())
        if mode == 1:
            c = Curve(BLUE)
            self.curves = [c]
            self.ions = [Ion(c, BLUE, "Blue", 450)]
            self.cursors = [Cursor(c, BLUE, [0, 1], 4)]
        elif mode == 2:
            cr, cb = Curve(RED), Curve(BLUE)
            self.curves = [cr, cb]
            self.ions = [Ion(cr, RED, "Red", 420), Ion(cb, BLUE, "Blue", 480)]
            self.cursors = [Cursor(cr, RED, [1], 3), Cursor(cb, BLUE, [0], 5)]
        elif mode == 3:
            c = Curve(COOP)
            self.curves = [c]
            self.ions = [Ion(c, COOP, "Team", 450)]
            self.cursors = [Cursor(c, RED, [1], 3), Cursor(c, BLUE, [0], 6)]
        else:
            # SANDBOX: fixed screen, one shared curve, a quantum wave packet
            # instead of the classical ion.
            c = Curve(COOP)
            c.v = start_voltages(W // EW + 3, VMIN, VMAX)
            self.curves = [c]
            self.ions = []
            self.cursors = [Cursor(c, BLUE, [0], 4), Cursor(c, RED, [1], 7)]
            self.sandbox = Sandbox(lambda x: self.potential(c, x), W, H, GROUND,
                                   (self.f_big, self.f_small, self.f_tiny))
        for ion in self.ions:
            ion.y = self.potential(ion.curve, ion.x) + R + 20
        self.state = "play"

    # ---------- potential ----------
    def default_v(self, i):
        if i < 9:
            return clamp(55 + 16 * (i - 4) ** 2, VMIN, VMAX)
        amp = min(150, 55 + (i - 9) * 1.2)
        n = 0.6 * math.sin(i * 1.73 + self.seed_a) + 0.4 * math.sin(i * 0.61 + self.seed_b)
        return clamp(170 + amp * n, VMIN, VMAX)

    def ensure(self, c, i):
        while len(c.v) <= i:
            c.v.append(self.default_v(len(c.v)))

    def node(self, c, i, rev):
        if i < 0:
            i = 0
        if len(c.v) <= i:
            self.ensure(c, i)
        v = c.v[i]
        if rev:
            for ci, dv in c.changes:
                if ci == i:
                    v -= dv
        return v

    def potential(self, c, x, rev=False):
        tt = x / EW - 0.5
        i = math.floor(tt)
        f = tt - i
        p0 = self.node(c, i - 1, rev)
        p1 = self.node(c, i, rev)
        p2 = self.node(c, i + 1, rev)
        p3 = self.node(c, i + 2, rev)
        h = 0.5 * (2 * p1 + (-p0 + p2) * f + (2 * p0 - 5 * p1 + 4 * p2 - p3) * f * f
                   + (-p0 + 3 * p1 - 3 * p2 + p3) * f * f * f)
        for e in self.caps:
            if e.x - 40 < x < e.x + e.w + 40:
                edge = min(x - e.x, e.x + e.w - x)
                win = clamp((edge + 40) / 40, 0, 1)
                h = min(h, e.h + (1 - win * win * (3 - 2 * win)) * 700)
        for e in self.defects:
            if abs(x - e.x) < 3 * e.w:
                q = (x - e.x) / e.w
                h = max(h, e.a * math.exp(-q * q))
        return clamp(h, VMIN, VMAX)

    def surf(self, cs, x, rev=False):
        if len(cs) == 1:
            return self.potential(cs[0], x, rev)
        return sum(self.potential(c, x, rev) for c in cs) / len(cs)

    # ---------- level generation (seeded) ----------
    def spawn_at(self, x):
        L = self.lrng
        u = L.uniform
        k = min(1.0, (x - 1500) / 12000)
        r = L.random()
        E = self.ents
        if r < 0.20:
            E.append(Ent(type="defect", x=x, a=u(90, 150 + 110 * k), w=u(30, 55)))
        elif r < 0.31:
            E.append(Ent(type="cap", x=x, w=u(180, 340), h=u(80, 140)))
        elif r < 0.44:
            E.append(Ent(type="block", x=x, w=u(40, 70), y0=0, y1=u(100, 150 + 90 * k)))
        elif r < 0.55:
            E.append(Ent(type="block", x=x, w=u(80, 160), y0=u(160, 240), y1=GROUND + 40))
        elif r < 0.66:
            n = 3 + int(L.random() * 3)
            base = u(80, 280)
            for i in range(n):
                E.append(Ent(type="photon", x=x + i * 46,
                             y=base + math.sin(i / (n - 1) * math.pi) * 70, ph=L.random() * 6))
        elif r < 0.78:
            E.append(Ent(type="laser", x=(round(x / EW - 0.5) + 0.5) * EW, dir=1))
        elif r < 0.84:
            E.append(Ent(type="laser", x=(round(x / EW - 0.5) + 0.5) * EW, dir=-1))
        elif r < 0.92:
            E.append(Ent(type="stray", x=x + 300, y=0.0, vx=0.0, vy=0.0, active=False, color=STRAY_C))
            return 900
        else:
            E.append(Ent(type="hole", x=x + 300, y=u(80, 260), ph=L.random() * 6))
            return 900
        return u(380, 700) * (1 - 0.3 * k)

    # ---------- physics ----------
    @staticmethod
    def coulomb(b, ox, oy, acc):
        dx, dy = b.x - ox, b.y - oy
        d = max(16.0, math.hypot(dx, dy))
        if d < 450:
            a = COULOMB / (d * d)
            acc[0] += a * dx / d
            acc[1] += a * dy / d

    def env_forces(self, b, is_stray):
        acc = [0.0, -G]
        for e in self.ents:
            if e is b:
                continue
            if e.type == "laser":
                if abs(b.x - e.x) < beam_half(b.y):
                    acc[1] += LASER_UP if e.dir > 0 else -LASER_DOWN
                    if random.random() < 0.12:
                        self.parts.append([b.x + random.uniform(-6, 6), b.y, random.uniform(-20, 20),
                                           e.dir * random.uniform(80, 200), 0.35, (216, 200, 255)])
            elif e.type == "stray" and e.active:
                self.coulomb(b, e.x, e.y, acc)
            elif e.type == "hole":
                dx, dy = e.x - b.x, e.y - b.y
                d = math.hypot(dx, dy)
                if d < HOLE_CAPTURE:
                    return None
                if d < HOLE_RANGE:
                    a = min(5000, HOLE_PULL / (d * d))
                    acc[0] += a * dx / d
                    acc[1] += a * dy / d
        if is_stray:
            for ion in self.ions:
                if ion.alive:
                    self.coulomb(b, ion.x, ion.y, acc)
        return acc

    def integrate(self, b, cs, acc, dt):
        b.vx += acc[0] * dt
        b.vy += acc[1] * dt
        damp = 1 - 0.08 * dt
        b.vx *= damp
        b.vy *= damp
        b.x += b.vx * dt
        b.y += b.vy * dt

        h = self.surf(cs, b.x)
        m = (self.surf(cs, b.x + 3) - self.surf(cs, b.x - 3)) / 6
        nl = math.hypot(1, m)
        nx, ny = -m / nl, 1 / nl
        d = (b.y - h) / nl
        if d < R:
            b.x += (R - d) * nx
            b.y += (R - d) * ny
            vs = 0.0
            if any(c.changes for c in cs):
                vs = (h - self.surf(cs, b.x, True)) / dt
            rx, ry = b.vx, b.vy - vs
            vn = rx * nx + ry * ny
            if vn < 0:
                e = 0.5 if vn < -140 else 0.0
                rx -= (1 + e) * vn * nx
                ry -= (1 + e) * vn * ny
                b.vx, b.vy = rx, ry + vs
                if vn < -320:
                    self.burst(b.x, b.y - R, b.color, 6)
                if isinstance(b, Ion):
                    # how hard it hit: its speed into the wave, relative to
                    # the wave (a curve pushed up under it counts too)
                    self.sounds.impact(-vn)

        if not b.inv > 0:
            for k in self.ents:
                if k.type != "block":
                    continue
                cx = clamp(b.x, k.x, k.x + k.w)
                cy = clamp(b.y, k.y0, k.y1)
                dx, dy = b.x - cx, b.y - cy
                dd = math.hypot(dx, dy)
                if dd < R:
                    if dd < 1e-6:
                        bx, by = -1.0, 0.0
                        b.x = k.x - R
                    else:
                        bx, by = dx / dd, dy / dd
                        b.x, b.y = cx + bx * R, cy + by * R
                    vn = b.vx * bx + b.vy * by
                    if vn < 0:
                        b.vx -= 1.4 * vn * bx
                        b.vy -= 1.4 * vn * by

        if b.x > self.cam_x + W - R:
            b.x = self.cam_x + W - R
            b.vx = -abs(b.vx) * 0.5
        if b.y > GROUND - R:
            b.y = GROUND - R
            b.vy = -abs(b.vy) * 0.5

    def ion_physics(self, ion, dt):
        acc = self.env_forces(ion, False)
        if acc is None:
            self.lose(ion, "ION LOSS")
            return
        self.integrate(ion, [ion.curve], acc, dt)
        for e in self.ents:
            if e.type == "photon" and not e.got and math.hypot(ion.x - e.x, ion.y - e.y) < R + 14:
                e.got = True
                ion.bonus += 50
                self.sounds.play("photon")
                self.burst(e.x, e.y, (255, 243, 168), 10)
                self.texts.append([e.x, e.y + 20, "+50", 0.8, (255, 243, 168)])
        ion.max_x = max(ion.max_x, ion.x)
        if ion.x < self.cam_x - 2 * R:
            self.lose(ion, "ION LOST")

    def stray_physics(self, e, dt):
        if not e.active:
            if e.x > self.cam_x + W + 40:
                return
            e.active = True
            e.x = min(e.x, self.cam_x + W - R)
            e.y = self.surf(self.curves, e.x) + R + 40
        acc = self.env_forces(e, True)
        if acc is None:
            self.burst(e.x, e.y, e.color, 18)
            e.dead = True
            return
        self.integrate(e, self.curves, acc, dt)
        if e.x < self.cam_x - 3 * R:
            e.dead = True

    def lose(self, ion, msg):
        ion.lives -= 1
        self.sounds.play("lost")
        self.burst(ion.x, ion.y, ion.color, 24)
        self.texts.append([clamp(ion.x, self.cam_x + 160, self.cam_x + W - 160),
                           clamp(ion.y, 60, GROUND - 60), msg, 1.6, ion.color])
        if ion.lives <= 0:
            ion.alive = False
            return
        bx, bh = self.cam_x + 600, 1e9
        x = self.cam_x + 420
        while x < self.cam_x + 900:
            h = self.potential(ion.curve, x)
            if h < bh:
                bh, bx = h, x
            x += 10
        ion.x, ion.y, ion.vx, ion.vy = bx, bh + R + 60, 0.0, 0.0
        ion.inv = 2.0
        ion.trail = []

    def burst(self, x, y, color, n):
        for _ in range(n):
            a = random.random() * math.tau
            s = random.uniform(60, 240)
            self.parts.append([x, y, math.cos(a) * s, math.sin(a) * s, random.uniform(0.4, 0.9), color])

    def step(self, dt):
        self.t += dt
        self.cam_speed = CAM_BASE + self.t * CAM_ACCEL          # unlimited speed-up
        lead = max((i.x - self.cam_x for i in self.ions if i.alive), default=0)
        self.cam_x += (self.cam_speed + max(0, lead - 0.65 * W) * 1.2) * dt

        while self.next_spawn < self.cam_x + W + 300:
            self.next_spawn += self.spawn_at(self.next_spawn)
        cx = self.cam_x
        self.ents = [e for e in self.ents
                     if e.x + getattr(e, "w", 0) * 3 > cx - 200 and not e.got and not e.dead]
        self.caps = [e for e in self.ents if e.type == "cap"]
        self.defects = [e for e in self.ents if e.type == "defect"]

        first = math.ceil(cx / EW - 0.5)
        last = math.floor((cx + W) / EW - 0.5)
        for c in self.curves:
            c.changes.clear()
            self.ensure(c, last + 3)
        self.drive_electrodes(dt, first, last, RATE)
        for ion in self.ions:
            if ion.alive:
                self.ion_physics(ion, dt)
                if ion.inv > 0:
                    ion.inv -= dt
        for e in self.ents:
            if e.type == "stray":
                self.stray_physics(e, dt)

        for q in self.parts:
            q[0] += q[2] * dt
            q[1] += q[3] * dt
            q[3] -= 500 * dt
            q[4] -= dt
        self.parts = [q for q in self.parts if q[4] > 0]
        for tx in self.texts:
            tx[3] -= dt
            tx[1] += 30 * dt
        self.texts = [tx for tx in self.texts if tx[3] > 0]

        if all(not i.alive for i in self.ions):
            self.game_over()

    def drive_electrodes(self, dt, first, last, rate):
        """Cursor voltage changes from held up/down. Returns True if any changed."""
        pads = self.controls.pads
        changed = False
        for cu in self.cursors:
            cu.sel = clamp(cu.sel, first, last)
            c = cu.curve
            old = c.v[cu.sel]
            nv = old
            if any(pads[p].held("up") for p in cu.pads):
                nv = min(VMAX, nv + rate * dt)
            if any(pads[p].held("down") for p in cu.pads):
                nv = max(VMIN, nv - rate * dt)
            if nv != old:
                c.v[cu.sel] = nv
                c.changes.append((cu.sel, nv - old))
                changed = True
        return changed

    def sandbox_frame(self):
        """Electrodes move once per frame (re-sampling the potential is the
        expensive part), then the packet takes the frame's physics steps."""
        steps = int(self.acc / STEP)
        self.acc -= steps * STEP
        if steps == 0:
            return
        for c in self.curves:
            c.changes.clear()
        changed = self.drive_electrodes(steps * STEP, 0, W // EW - 1, SANDBOX_RATE)
        cooling = self.controls.pads[1].held("cool")
        for k in range(steps):
            self.sandbox.step(STEP, changed and k == 0, cooling)
        self.t += steps * STEP

    def score(self, ion):
        return int((ion.max_x - ion.start_x) / 10 + ion.bonus)

    def game_over(self):
        self.state = "over"
        self.menu_sel = 0
        self.record = False
        if self.mode == 2:
            a, b = (self.score(i) for i in self.ions)
            self.sounds.play("over" if a == b else "win")
        else:
            key = "solo" if self.mode == 1 else "coop"
            sc = self.score(self.ions[0])
            if sc > self.best.get(key, 0):
                self.best[key] = sc
                self.record = True
                try:
                    with open(SCORE_FILE, "w") as fh:
                        json.dump(self.best, fh)
                except Exception:
                    pass
            self.sounds.play("win" if self.record else "over")

    # ---------- per-frame update / menus ----------
    def seed_string(self):
        return "".join(self.seed_chars).replace(" ", "")

    def text_input_active(self):
        return self.state == "menu" and self.seed_edit

    def type_key(self, e):
        if e.key == pygame.K_BACKSPACE:
            if self.seed_chars[self.seed_slot] == " " and self.seed_slot > 0:
                self.seed_slot -= 1
            self.seed_chars[self.seed_slot] = " "
        else:
            ch = e.unicode.upper()
            if ch in SEED_CHARS and ch != " ":
                self.seed_chars[self.seed_slot] = ch
                self.seed_slot = min(SEED_LEN - 1, self.seed_slot + 1)

    def confirm(self):
        # A, or Start -- the cabinet convention. L/R used to confirm too, which
        # read as arbitrary next to every other game.
        return self.controls.any_pressed("confirm") or self.controls.any_pressed("start")

    def back(self):
        return self.controls.any_pressed("back")

    def nav(self, n):
        old = self.menu_sel
        if self.controls.any_pressed("up"):
            self.menu_sel = (self.menu_sel - 1) % n
        if self.controls.any_pressed("down"):
            self.menu_sel = (self.menu_sel + 1) % n
        if self.menu_sel != old:
            self.sounds.play("move")

    MAIN_ITEMS = ["1 PLAYER", "2 PLAYERS: VERSUS", "2 PLAYERS: CO-OP", "SANDBOX", "SEED", "QUIT"]
    # The first three items start modes 1..3. These two are named because both
    # the menu logic and the drawing code index into MAIN_ITEMS by row, and a
    # bare 3 silently becomes the wrong row the moment an item is inserted.
    SANDBOX_ITEM = 3
    SEED_ITEM = 4

    # Cabinet pause convention: at least RESUME and QUIT TO TITLE. The title
    # here is the main menu. With --sandbox there is no menu to go back to,
    # so the last item quits the program instead.
    @property
    def PAUSE_ITEMS(self):
        return ["RESUME", "RESTART", "QUIT" if self.sandbox_only else "QUIT TO TITLE"]
    OVER_ITEMS = ["SAME SEED", "NEW SEED", "MAIN MENU"]

    def open_tutorial(self, mode, seed=None):
        """A match picked in the main menu starts behind the HOW TO PLAY
        card. RESTART and the game-over screen's rematches skip it: the
        same people just played."""
        from ion_surfer.tutorial import Tutorial  # it builds on this module

        self.start(mode, seed)
        self.tutorial = Tutorial(mode, self)
        self.state = "tutorial"

    def update(self, dt):
        self.update_state(dt)
        self.sounds.ambient(self.ambient_sources(), dt)

    def ambient_sources(self):
        """What hums and pings in the background: every laser beam and active
        stray ion in a running match, as (kind, key, screen x, nearness to the
        closest ion). Nothing in menus, while paused or in the sandbox, so
        the ambience fades out there."""
        if self.state != "play" or self.mode == SANDBOX:
            return []
        ions = [i for i in self.ions if i.alive]
        out = []
        for e in self.ents:
            if e.type == "laser":
                d = min((abs(i.x - e.x) for i in ions), default=math.inf)
                kind = "beam_up" if e.dir > 0 else "beam_down"
                out.append((kind, id(e), e.x - self.cam_x, sound.nearness(d, BEAM_HEAR)))
            elif e.type == "stray" and e.active:
                d = min((math.hypot(i.x - e.x, i.y - e.y) for i in ions), default=math.inf)
                out.append(("stray", id(e), e.x - self.cam_x, sound.nearness(d, STRAY_HEAR)))
        return out

    def update_state(self, dt):
        c = self.controls
        if self.state == "play":
            if c.pause_pressed():
                self.state = "pause"
                self.menu_sel = 0
                self.sounds.play("pause")
                return
            for cu in self.cursors:
                for p in cu.pads:
                    if "left" in c.pads[p].pressed:
                        cu.sel -= 1
                        self.sounds.play("electrode")
                    if "right" in c.pads[p].pressed:
                        cu.sel += 1
                        self.sounds.play("electrode")
            self.acc += dt
            if self.mode == SANDBOX:
                # blue: L/R remove/add an ion; red: L cools while held, R
                # toggles passive cooling; SELECT on either pad: laser kick
                # (Start pauses, as in every other mode)
                sb = self.sandbox
                blue, red = c.pads
                if "add_ion" in blue.pressed:
                    if sb.add_ion():
                        self.sounds.play("ion_add")
                elif "remove_ion" in blue.pressed:
                    if sb.remove_ion():
                        self.sounds.play("ion_remove")
                if "passive_cool" in red.pressed:
                    sb.passive_cooling = not sb.passive_cooling
                    self.sounds.play("toggle_on" if sb.passive_cooling else "toggle_off")
                if "cool" in red.pressed:
                    self.sounds.play("cool")
                for pi, p in enumerate(c.pads):
                    if "select" in p.pressed:
                        sb.kick(pi)
                        self.sounds.play("kick")
                self.sandbox_frame()
                was = sb.anharmonic
                sb.measure()
                if sb.anharmonic and not was:
                    self.sounds.play("warn")
                return
            while self.acc >= STEP and self.state == "play":
                self.step(STEP)
                self.acc -= STEP
            for ion in self.ions:
                if ion.alive:
                    ion.trail.append((ion.x, ion.y))
                    if len(ion.trail) > 16:
                        ion.trail.pop(0)

        elif self.state == "tutorial":
            # Any button dismisses the card, once it has been up long enough
            # to be seen. The stick doesn't. Buttons still held are used up,
            # so that press doesn't also move a cursor in the match.
            self.tutorial.update(dt)
            if c.any_button and self.tutorial.can_dismiss():
                c.consume_buttons()
                self.tutorial = None
                self.state = "play"
                self.acc = 0.0
                self.sounds.play("start")

        elif self.state == "pause":
            self.acc = 0
            # Start or B resumes; only A picks an item (so not confirm(),
            # which would let Start pick one too).
            if c.pause_pressed() or self.back():
                self.state = "play"
                self.sounds.play("pause")
                return
            self.nav(len(self.PAUSE_ITEMS))
            if c.any_pressed("confirm"):
                if self.menu_sel == 0:
                    self.state = "play"
                    self.sounds.play("pause")
                elif self.menu_sel == 1:
                    self.start(self.mode, self.current_seed)
                    self.sounds.play("start")
                elif self.sandbox_only:
                    self.running = False
                else:
                    self.to_menu()
                    self.sounds.play("back")

        elif self.state == "over":
            if self.back():
                self.to_menu()
                self.sounds.play("back")
                return
            self.nav(3)
            if self.confirm():
                if self.menu_sel == 0:
                    self.start(self.mode, self.current_seed)
                    self.sounds.play("start")
                elif self.menu_sel == 1:
                    self.start(self.mode)
                    self.sounds.play("start")
                else:
                    self.to_menu()
                    self.sounds.play("back")

        elif self.state == "menu":
            self.t += dt
            if self.seed_edit:
                if self.confirm() or self.back():
                    self.seed_edit = False
                    self.sounds.play("confirm")
                    return
                sl = self.seed_slot
                idx = SEED_CHARS.index(self.seed_chars[sl])
                if c.any_pressed("up"):
                    self.seed_chars[sl] = SEED_CHARS[(idx + 1) % len(SEED_CHARS)]
                if c.any_pressed("down"):
                    self.seed_chars[sl] = SEED_CHARS[(idx - 1) % len(SEED_CHARS)]
                if c.any_pressed("left"):
                    self.seed_slot = max(0, sl - 1)
                if c.any_pressed("right"):
                    self.seed_slot = min(SEED_LEN - 1, sl + 1)
                if any(c.any_pressed(d) for d in ("up", "down", "left", "right")):
                    self.sounds.play("move")
                return
            if self.back():
                return
            self.nav(len(self.MAIN_ITEMS))
            seed = self.seed_string() or None
            if c.any_pressed("start"):
                # Start always starts a match, whatever row is picked: that
                # row's mode, or 1 PLAYER from SEED or QUIT. It never quits.
                mode = (self.menu_sel + 1 if self.menu_sel < self.SANDBOX_ITEM
                        else SANDBOX if self.menu_sel == self.SANDBOX_ITEM else 1)
                self.sounds.play("confirm")
                self.open_tutorial(mode, None if mode == SANDBOX else seed)
            elif c.any_pressed("confirm"):
                if self.menu_sel in (0, 1, 2):
                    self.sounds.play("confirm")
                    self.open_tutorial(self.menu_sel + 1, seed)
                elif self.menu_sel == self.SANDBOX_ITEM:
                    self.sounds.play("confirm")
                    self.open_tutorial(SANDBOX)
                elif self.menu_sel == self.SEED_ITEM:
                    self.seed_edit = True
                    self.seed_slot = 0
                    self.sounds.play("confirm")
                else:
                    # QUIT: back to the cabinet's game list, the same clean
                    # exit as Start + Select
                    self.running = False

    def to_menu(self):
        self.state = "menu"
        self.menu_sel = 0
        self.sandbox = None
        self.tutorial = None
        self.new_world(random_seed())

    # ---------- drawing ----------
    def draw_laser(self, e, X):
        s = self.screen
        x = X(e.x)
        pulse = 0.8 + 0.2 * math.sin(self.t * 9 + e.x)
        left = [(x - beam_half(y), sy(y)) for y in range(0, GROUND + 1, 16)]
        right = [(x + beam_half(y), sy(y)) for y in range(GROUND, -1, -16)]
        pygame.draw.polygon(self.fx, (170, 125, 255, int(40 * pulse)), left + right)
        inner_l = [(x - beam_half(y) * 0.45, sy(y)) for y in range(0, GROUND + 1, 16)]
        inner_r = [(x + beam_half(y) * 0.45, sy(y)) for y in range(GROUND, -1, -16)]
        self.layer_laser.append(inner_l + inner_r)
        return pulse

    def draw_laser_streaks(self, e, X):
        s = self.screen
        x = X(e.x)
        pulse = 0.8 + 0.2 * math.sin(self.t * 9 + e.x)
        for k in range(24):
            sp = 360 + hsh(k * 3.1 + e.x) * 260
            raw = self.t * sp + hsh(k * 7.7 + e.x) * GROUND * 3
            cyc = math.floor(raw / GROUND)
            prog = raw - cyc * GROUND
            y = prog if e.dir > 0 else GROUND - prog
            u = hsh(k * 31.7 + cyc * 7.3 + e.x) * 2 - 1
            ln = 14 + 30 * hsh(k * 1.3 + cyc * 3.9)
            y2 = clamp(y - e.dir * ln, 0, GROUND)
            col = scale_col((235, 222, 255), (0.3 + 0.55 * hsh(k * 5.1 + cyc)) * pulse)
            pygame.draw.line(s, col, (x + u * beam_half(y) * 0.85, sy(y)),
                             (x + u * beam_half(y2) * 0.85, sy(y2)), 2)

    def blit_hatch(self, hatch, rect):
        r = pygame.Rect(rect).clip(pygame.Rect(0, 0, W, H))
        if r.w <= 0 or r.h <= 0:
            return
        off = int(self.cam_x) % 12
        self.screen.blit(hatch, r.topleft, pygame.Rect(r.x + off, r.y, r.w, r.h))

    def draw_world(self):
        s = self.screen
        cam = self.cam_x
        X = lambda x: x - cam
        s.blit(self.bg, (0, 0))

        grid = (20, 30, 60)
        off = cam % 60
        x = -off
        while x < W:
            pygame.draw.line(s, grid, (x, 0), (x, GROUND))
            x += 60
        y = GROUND
        while y > 0:
            pygame.draw.line(s, grid, (0, y), (W, y))
            y -= 60

        # translucent world layer: caps, defects, laser envelopes
        self.fx.fill((0, 0, 0, 0))
        self.layer_laser = []
        labels = []
        for e in self.ents:
            if e.type == "laser":
                self.draw_laser(e, X)
            elif e.type == "cap":
                pygame.draw.rect(self.fx, (255, 70, 120, 28), (X(e.x), 0, e.w, sy(e.h)))
            elif e.type == "defect":
                pts = [(X(e.x - 3 * e.w), GROUND)]
                xx = e.x - 3 * e.w
                while xx <= e.x + 3 * e.w:
                    q = (xx - e.x) / e.w
                    pts.append((X(xx), sy(e.a * math.exp(-q * q))))
                    xx += 6
                pts.append((X(e.x + 3 * e.w), GROUND))
                pygame.draw.polygon(self.fx, (255, 193, 77, 38), pts)
                labels.append((e, pts))
        s.blit(self.fx, (0, 0))
        if self.layer_laser:
            self.fx.fill((0, 0, 0, 0))
            for poly in self.layer_laser:
                pygame.draw.polygon(self.fx, (200, 165, 255, 45), poly)
            s.blit(self.fx, (0, 0))
        for e in self.ents:
            if e.type == "laser":
                self.draw_laser_streaks(e, X)
            elif e.type == "cap":
                self.blit_hatch(self.hatch_cap, (X(e.x), 0, e.w, sy(e.h)))
                xx = X(e.x)
                while xx < X(e.x) + e.w:
                    pygame.draw.line(s, (255, 90, 138), (xx, sy(e.h)), (min(xx + 8, X(e.x) + e.w), sy(e.h)), 2)
                    xx += 14
                text(s, "ENERGY CAP", self.f_small, (255, 143, 176), (X(e.x) + e.w / 2, sy(e.h) - 14))
        for e, pts in labels:
            pygame.draw.lines(s, (220, 170, 70), False, pts[1:-1], 2)
            text(s, "DEFECT", self.f_small, (255, 193, 77), (X(e.x), sy(e.a) - 16))

        # potential curves
        first_i = max(0, math.floor(cam / EW - 0.5) - 1)
        last_i = math.ceil((cam + W) / EW)
        for c in self.curves:
            pts = [(sx, sy(self.potential(c, cam + sx))) for sx in range(0, W + 1, 6)]
            self.layer.fill((0, 0, 0, 0))
            a = 55 if len(self.curves) == 1 else 34
            pygame.draw.polygon(self.layer, (*c.color, a), pts + [(W, GROUND), (0, GROUND)])
            pygame.draw.lines(self.layer, (*c.color, 70), False, pts, 10)
            s.blit(self.layer, (0, 0))
            pygame.draw.lines(s, c.color, False, pts, 3)
            for i in range(first_i, last_i + 1):
                self.ensure(c, i)
                sel = any(cu.curve is c and cu.sel == i for cu in self.cursors)
                pygame.draw.circle(s, (255, 255, 255) if sel else scale_col(c.color, 0.6),
                                   (X((i + 0.5) * EW), sy(c.v[i])), 5 if sel else 3)
        for cu in self.cursors:
            self.ensure(cu.curve, cu.sel)
            sx = X((cu.sel + 0.5) * EW)
            y0, y1 = GROUND + 6, sy(cu.curve.v[cu.sel])
            col = scale_col(cu.color, 0.75)
            yy = y0
            while yy > y1:
                pygame.draw.line(s, col, (sx, yy), (sx, max(y1, yy - 4)), 2)
                yy -= 10

        # blocks
        for b in self.ents:
            if b.type != "block":
                continue
            top, bot = sy(min(b.y1, GROUND + 40)), sy(b.y0)
            rect = pygame.Rect(X(b.x), top, b.w, bot - top)
            pygame.draw.rect(s, (24, 33, 63), rect)
            self.blit_hatch(self.hatch_block, rect)
            pygame.draw.rect(s, (143, 162, 230), rect, 2)

        # strays, holes, photons
        for e in self.ents:
            if e.type == "stray" and e.active:
                x, y = X(e.x), sy(e.y)
                for k in range(1, 4):
                    rr = 30 * k + (self.t * 20) % 30
                    rect = pygame.Rect(x - rr, y - rr, rr * 2, rr * 2)
                    for a in range(0, 360, 24):
                        ar = math.radians(a)
                        pygame.draw.arc(s, (96, 52, 88), rect, ar, ar + 0.14, 2)
                gl = self.glow(STRAY_C, 26)
                s.blit(gl, (x - 26, y - 26), special_flags=pygame.BLEND_ADD)
                pygame.draw.circle(s, (255, 205, 235), (x, y), R - 2)
                text(s, "+", self.f_plus, (255, 255, 255), (x, y))
                text(s, "STRAY ION", self.f_small, (255, 179, 228), (x, y - 36))
            elif e.type == "hole":
                x, y = X(e.x), sy(e.y)
                hs = self.hole_sprite
                s.blit(hs, (x - hs.get_width() / 2, y - hs.get_height() / 2))
                for k in range(4):
                    a0 = self.t * (1.5 + k * 0.4) + k * 1.7 + e.ph
                    rr = 26 + k * 12
                    pygame.draw.arc(s, scale_col((200, 160, 255), 0.9 - k * 0.18),
                                    (x - rr, y - rr, rr * 2, rr * 2), a0, a0 + math.pi * 0.9, 2)
                pygame.draw.circle(s, (0, 0, 0), (x, y), HOLE_CAPTURE)
                pygame.draw.circle(s, (210, 180, 255), (x, y), HOLE_CAPTURE, 2)
                text(s, "LOSS", self.f_small, (205, 178, 255), (x, y - 64))
            elif e.type == "photon":
                x, y = X(e.x), sy(e.y + math.sin(self.t * 4 + e.ph) * 5)
                gl = self.glow((255, 215, 110), 18)
                s.blit(gl, (x - 18, y - 18), special_flags=pygame.BLEND_ADD)
                pygame.draw.circle(s, (255, 250, 210), (x, y), 4)

        # ions
        for ion in self.ions:
            if not ion.alive:
                continue
            n = len(ion.trail)
            for i, (tx, ty) in enumerate(ion.trail):
                a = i / max(1, n)
                pygame.draw.circle(s, scale_col(ion.color, a * 0.45), (X(tx), sy(ty)), max(1, int(R * a)))
            if ion.inv > 0 and int(ion.inv * 10) % 2:
                continue
            x, y = X(ion.x), sy(ion.y)
            gl = self.glow(ion.color, 30)
            s.blit(gl, (x - 30, y - 30), special_flags=pygame.BLEND_ADD)
            pygame.draw.circle(s, ion.color, (x, y), R)
            pygame.draw.circle(s, (255, 255, 255), (x - 3, y - 3), 4)
            text(s, "+", self.f_plus, (255, 255, 255), (x + 1, y + 1))

        for q in self.parts:
            sz = max(1, int(4 * clamp(q[4] * 1.5, 0, 1)))
            pygame.draw.rect(s, q[5], (X(q[0]) - sz / 2, sy(q[1]) - sz / 2, sz, sz))
        for tx in self.texts:
            text(s, tx[2], self.f_big, tx[4], (X(tx[0]), sy(tx[1])), alpha=tx[3])

        if self.mode != SANDBOX or self.state == "menu":
            s.blit(self.warn, (0, 0))

        # electrode strip
        pygame.draw.rect(s, (8, 13, 29), (0, GROUND, W, H - GROUND))
        pygame.draw.rect(s, (42, 55, 100), (0, GROUND, W, 2))
        lit_x = {e.x for e in self.ents if e.type == "laser"}
        for i in range(first_i, last_i + 1):
            x = X(i * EW) + 8
            w = EW - 16
            y = GROUND + 16
            lit = any(abs(lx - (i + 0.5) * EW) < 1 for lx in lit_x)
            s.blit(self.plate_lit if lit else self.plate_gold, (x, y))
            for j, c in enumerate(self.curves):
                self.ensure(c, i)
                lv = (c.v[i] - VMIN) / (VMAX - VMIN)
                pygame.draw.rect(s, (26, 36, 70), (x, y + 34 + j * 9, w, 6))
                pygame.draw.rect(s, c.color, (x, y + 34 + j * 9, w * lv, 6))
        for j, cu in enumerate(self.cursors):
            x = X(cu.sel * EW) + 8
            w = EW - 16
            y = GROUND + 16
            o = j * 3
            pygame.draw.rect(s, cu.color, (x - 3 - o, y - 3 - o, w + 6 + 2 * o, 34 + 2 * o), 3)
            cx = x + w / 2 + ((10 if j else -10) if len(self.cursors) == 2 else 0)
            pygame.draw.polygon(s, cu.color, [(cx, GROUND + 4), (cx - 6, GROUND + 11), (cx + 6, GROUND + 11)])

    def draw_hud(self):
        s = self.screen
        for j, ion in enumerate(self.ions):
            x = 20 if j == 0 else W - 220
            text(s, str(self.score(ion)) if ion.alive else "OUT", self.f_hud, ion.color, (x, 22), "topleft")
            for k in range(3):
                col = ion.color if k < ion.lives else (40, 46, 66)
                pygame.draw.circle(s, col, (x + 8 + k * 20, 60), 6)
            if self.mode == 3:
                text(s, "CO-OP", self.f_small, (185, 166, 230), (x + 72, 60), "midleft")
        text(s, f"{int(self.cam_x / 100)} µm transported", self.f_small, TEXT_DIM, (W / 2, 26))
        text(s, f"SEED {self.current_seed}", self.f_tiny, (110, 120, 160), (W / 2, 46))

    def draw_items(self, items, y0, labels=None, spacing=42):
        s = self.screen
        for i, it in enumerate(items):
            lab = labels[i] if labels else it
            sel = i == self.menu_sel
            col = GOLD if sel else (195, 203, 232)
            r = text(s, lab, self.f_item, col, (W / 2, y0 + i * spacing))
            if sel:
                pygame.draw.polygon(s, GOLD, [(r.left - 26, r.centery - 8), (r.left - 26, r.centery + 8),
                                              (r.left - 12, r.centery)])

    def draw_menu(self):
        s = self.screen
        s.blit(self.dim, (0, 0))
        t = text(s, "ION SURFER", self.f_title, GOLD, (W / 2, 110))
        text(s, "Shape the trap potential. Keep your ion in the picture.", self.f_small, (195, 203, 232),
             (W / 2, t.bottom + 18))
        seed = self.seed_string()
        labels = list(self.MAIN_ITEMS)
        labels[self.SEED_ITEM] = f"SEED: {seed if seed else 'RANDOM'}"
        if self.seed_edit:
            labels[self.SEED_ITEM] = "SEED:"
        self.draw_items(self.MAIN_ITEMS, 236, labels)
        if self.seed_edit:
            y = 236 + self.SEED_ITEM * 42
            base = W / 2 + 40
            for i, ch in enumerate(self.seed_chars):
                x = base + i * 26
                col = GOLD if i == self.seed_slot else (230, 235, 255)
                text(s, ch if ch != " " else "_", self.f_item, col, (x, y))
                if i == self.seed_slot:
                    pygame.draw.rect(s, GOLD, (x - 10, y + 16, 20, 3))
            if self.controls.devices.everyone_on(KEYBOARD):  # letter keys type, so Start finishes
                done = f"type   LEFT/RIGHT move   {self.name('start')} done"
            else:
                done = f"UP/DOWN change   LEFT/RIGHT move   {self.name('a')} or {self.name('b')} done"
            text(s, f"{done}   (empty = random)", self.f_tiny,
                 TEXT_DIM, (W / 2, 236 + len(self.MAIN_ITEMS) * 42))
        lines = [
            f"BLUE (P1): {self.name('stick', 'p1').lower()} = select electrode / voltage",
            f"RED (P2): {self.name('stick', 'p2').lower()} = select electrode / voltage",
            f"Co-op: one shared waveform, one ion.   {self.name('a')}: confirm   {self.name('b')}: back   "
            f"{self.name('start')}: pause",
        ]
        for i, ln in enumerate(lines):
            text(s, ln, self.f_small, TEXT_DIM, (W / 2, 486 + i * 22))
        rec = f"Records  Solo {self.best.get('solo', 0)}   Co-op {self.best.get('coop', 0)}"
        text(s, rec, self.f_tiny, (110, 120, 160), (W / 2, 560))

    def draw_pause(self):
        s = self.screen
        s.blit(self.dim, (0, 0))
        text(s, "PAUSED", self.f_title, GOLD, (W / 2, 190))
        self.draw_items(self.PAUSE_ITEMS, 290)
        p = self.controls.devices.latest  # one player works the menu
        text(s, f"{self.name('a', p)}: choose   {self.name('start', p)} or {self.name('b', p)}: resume",
             self.f_small, TEXT_DIM, (W / 2, 420))
        if self.mode != SANDBOX:
            text(s, f"SEED {self.current_seed}", self.f_small, TEXT_DIM, (W / 2, 450))

    def draw_over(self):
        s = self.screen
        s.blit(self.dim, (0, 0))
        text(s, "TRAP EMPTY", self.f_title, GOLD, (W / 2, 150))
        if self.mode == 2:
            a, b = (self.score(i) for i in self.ions)
            win = "IT'S A DRAW" if a == b else ("RED WINS" if a > b else "BLUE WINS")
            text(s, win, self.f_item, (255, 255, 255), (W / 2, 220))
            text(s, f"Red {a}   Blue {b}", self.f_small, (195, 203, 232), (W / 2, 252))
        else:
            key = "solo" if self.mode == 1 else "coop"
            sc = self.score(self.ions[0])
            lab = "TEAM SCORE" if self.mode == 3 else "SCORE"
            text(s, f"{lab} {sc}" + ("   NEW RECORD" if self.record else ""), self.f_item,
                 (255, 255, 255), (W / 2, 220))
            text(s, f"Record {self.best.get(key, 0)}", self.f_small, (195, 203, 232), (W / 2, 252))
        text(s, f"SEED {self.current_seed}", self.f_item, (230, 235, 255), (W / 2, 296))
        self.draw_items(self.OVER_ITEMS, 370)

    # ---------- button names ----------
    def name(self, control, player=None):
        """A control's on-screen name for one player's keys or pad, or for
        both players' when player is None (e.g. "SPACE / ENTER"). "stick" is
        the stick or the direction keys."""
        if player is None:
            return " / ".join(dict.fromkeys(self.name(control, p) for p in ("p1", "p2")))
        if control == "stick":
            return KEYBOARD_STICKS[player] if self.controls.devices[player] == KEYBOARD else "STICK"
        return self.controls.devices.label(control, player)

    def sandbox_hint(self):
        """The SANDBOX's controls line, for the players' devices."""
        n = self.name
        return (f"{n('stick')} electrode / voltage    {n('select')} laser kick    "
                f"BLUE  {n('l', 'p1')} remove / {n('r', 'p1')} add ion    "
                f"RED  {n('l', 'p2')} hold: cool / {n('r', 'p2')} passive cooling    {n('start')} pause")

    def draw(self):
        if self.state == "tutorial":
            self.tutorial.draw(self.screen)  # a full-screen card of its own
            return
        self.draw_world()
        if self.state != "menu" and self.mode == SANDBOX:
            self.sandbox.draw(self.screen, sy, self.sandbox_hint())
        elif self.state != "menu":
            self.draw_hud()
        if self.state == "menu":
            self.draw_menu()
        elif self.state == "pause":
            self.draw_pause()
        elif self.state == "over":
            self.draw_over()


async def _leave(game, surface, window):
    """A player asked to quit: True ends the program. In the browser there is
    nothing to hand back to, so instead the game tells the page (which may
    take the player back to its game list) and returns to its menu -- once
    the quit buttons are let go, or the menu would quit again at once."""
    if not runtime.is_browser():
        return True
    web.post_event(web.QUIT, GAME_ID)
    while game.controls.quit_combo():
        game.controls.begin_frame()
        for e in pygame.event.get():
            game.controls.handle(e)
        present(surface, window)
        pygame.display.flip()
        await asyncio.sleep(0)
    game.running = True
    game.to_menu()
    return False


async def run(*, fullscreen=False, window_size="1200x640", show_fps=False, sandbox_only=False, pad_layout=None):
    sound.pre_init()
    pygame.init()
    pygame.joystick.init()
    surface, window = make_display(fullscreen, window_size)
    pygame.display.set_caption("Ion Trap Sandbox" if sandbox_only else "Ion Surfer")
    pygame.mouse.set_visible(not fullscreen)
    clock = pygame.time.Clock()
    game = Game(surface, sandbox_only=sandbox_only, sounds=sound.load_sounds(W), pad_layout=pad_layout)
    fps_font = load_font("Rubik-Medium.ttf", 15)
    playing = False  # a match is on (for the page's game-start / game-end events)
    while True:
        dt = min(0.1, clock.tick(FPS) / 1000)
        game.controls.begin_frame()
        for e in pygame.event.get():
            if e.type == pygame.QUIT:
                game.running = False
            elif e.type == pygame.KEYDOWN and e.key == pygame.K_F3:
                show_fps = not show_fps
                continue
            elif (keyboard_enabled() and game.text_input_active() and e.type == pygame.KEYDOWN
                  and (e.key == pygame.K_BACKSPACE or (e.unicode and e.unicode.isalnum()))):
                game.type_key(e)
                continue
            game.controls.handle(e)
        if game.controls.quit_combo():
            game.running = False
        if game.running:
            game.controls.update(dt)
            game.update(dt)
        now_playing = game.state in ("play", "pause") and game.running
        if now_playing != playing:
            playing = now_playing
            web.post_event(web.GAME_START if playing else web.GAME_END, GAME_ID)
        if not game.running:  # QUIT, Start + Select, or the window closed
            if await _leave(game, surface, window):
                break
            continue
        game.draw()
        if show_fps:
            text(surface, f"{clock.get_fps():.0f} fps", fps_font, (255, 211, 107), (8, H - 8), "bottomleft")
        present(surface, window)
        pygame.display.flip()
        await asyncio.sleep(0)  # hand the frame to the browser (pygbag); no-op elsewhere
