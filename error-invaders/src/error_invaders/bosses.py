"""
Boss fights: every third wave, and every wave in BOSS RUSH.

Five bosses, each built on one idea from quantum error correction:

  LOGICAL ERROR  an error chain that crawls down the code like Centipede and
                 splits where it is hit; reaching the qubits costs a life
  WAVE PACKET    only hittable while it is collapsed (narrow in x -- and then
                 its momentum is wild); a bomb measures it on the spot
  SYNDROME       the errors are hidden, only the checks around them light up:
                 shoot the qubit between two lit checks (you are the decoder)
  CLIFFORD CORE  immune to Pauli shots (they are Clifford). Absorb shots of
                 your own color to charge a magic-state bomb, which hurts it
  BELL PAIR      two entangled halves that heal each other unless both are
                 hit within a short window

All of them shoot, and most also spawn minions: single errors that waver down
and shoot. This module drives game.py's state (game.g) and uses its helpers at
call time; game.py imports it, so nothing here touches game at import time.
"""
import math, random

import pygame

from error_invaders import game as G
from error_invaders.config import INTERNAL_HEIGHT as H, INTERNAL_WIDTH as W

ORDER = ["centipede", "packet", "syndrome", "clifford", "bell"]
INFO = {  # name, two lines for the intro card
    "centipede": ("LOGICAL ERROR", "An error chain crawling across the code.",
                  "Break it up before it reaches the qubits!"),
    "packet":    ("WAVE PACKET", "Spread out, it is nowhere in particular.",
                  "Shoot it while it is collapsed!"),
    "syndrome":  ("SYNDROME", "The errors are hidden. Only the checks light up.",
                  "Shoot the qubit between two lit checks!"),
    "clifford":  ("CLIFFORD CORE", "Pauli shots are Clifford: it is immune.",
                  "Absorb shots of YOUR color for a magic state!"),
    "bell":      ("BELL PAIR |Φ+>", "Two entangled halves heal each other.",
                  "Hit both halves at the same time!"),
}
INTRO = 3.0          # seconds of intro card; the boss can't hurt or be hurt meanwhile
MAX_MINIONS = 8
MAGIC_NEEDED = 5     # absorbed shots per magic-state bomb (Clifford Core)
TOP = 70             # upper edge of the boss area (below the HUD)

rand = random.uniform
pick = random.choice
def clamp(v, a, b): return max(a, min(b, v))


def boss_for_wave(wave, mode):
    """(kind, tier) of the boss fought in this wave, or None for a normal wave.

    Normal modes: waves 3, 6, 9, ... cycle through ORDER. BOSS RUSH: every wave.
    `tier` counts completed laps through ORDER and makes each boss harder.
    """
    if mode == "rush": i = wave - 1
    elif wave % 3 == 0: i = wave // 3 - 1
    else: return None
    return ORDER[i % len(ORDER)], i // len(ORDER)


# =====================================================================
# Shared helpers
# =====================================================================
def targets():
    g = G.g
    return [g.merged] if g.merged else [p for p in g.players if p.alive]

def aim(x, y):
    """Angle from (x, y) toward a random live player (straight down if none)."""
    t = targets()
    if not t: return math.pi / 2
    t = pick(t)
    return math.atan2(t.y - y, t.x - x)

def shoot(x, y, ang, sp, kind="orb", col=None):
    G.g.eb.append(G.Obj(x=x, y=y, vx=math.cos(ang) * sp, vy=math.sin(ang) * sp, kind=kind, col=col))

def fan(x, y, ang, n, spread, sp, kind="orb"):
    for i in range(n):
        shoot(x, y, ang + (i - (n - 1) / 2) * spread, sp, kind)

def ring(x, y, n, sp, off=0.0, r0=0.0):
    for i in range(n):
        a = off + i * 2 * math.pi / n
        shoot(x + math.cos(a) * r0, y + math.sin(a) * r0, a, sp)

def color_hit(obj, b, x, y):
    """Apply a colored shot to a colored target with the game's Pauli rules.

    True if the shot corrected it; otherwise the target may have changed color
    (Y hit by X/Z, or any wrong color in HARD) or the shot was blocked.
    """
    res, new = G.pauli_hit(obj.col, b.col, G.g.mode == "hard")
    if res == "kill":
        G.play("kill"); return True
    if res == "convert":
        obj.col = new; obj.flash = 0.2; G.g.score += 10
        G.burst(x, y, G.COL[new], 8, 120); G.play("convert")
    else:
        obj.flash = 0.12; G.burst(x, y, (136, 136, 136), 5, 80); G.play("block")
    return False

def bomb_blast(x, y, r=125):
    """The magic-state explosion: kills minions near it and clears bullets."""
    g = G.g
    G.burst(x, y, G.SPECIAL["bomb"], 60, 380); G.play("boom_l"); g.shake = 0.5
    g.parts.append(G.Obj(ring=True, x=x, y=y, r=10, life=0.4, col=G.SPECIAL["bomb"]))
    for m in g.minions:
        if math.hypot(m.x - x, m.y - y) < r: kill_minion(m)
    g.eb = [q for q in g.eb if math.hypot(q.x - x, q.y - y) > 200]

def leak(reason):
    """An error got through: costs a life, or the game when none are left."""
    g = G.g
    g.shake = 0.8; G.play("boom_l")
    G.pop(W / 2, G.DEATH_LINE - 40, "LOGICAL ERROR!", G.COL["X"], 18, 1.6)
    if g.lives > 0: g.lives -= 1
    elif not g.overDelay: g.overDelay = 1.2; g.reason = reason

def damage(boss, n, x, y):
    boss.hp = max(0, boss.hp - n); boss.flash = 0.12
    G.g.score += 30 * n
    G.burst(x, y, G.WHITE, 10, 200); G.play("boss_hit")


# =====================================================================
# Minions: single errors that waver down and shoot
# =====================================================================
def spawn_minion(x, y, col=None):
    g = G.g
    if len(g.minions) >= MAX_MINIONS: return None
    m = G.Obj(x0=x, x=x, y=y, col=col or pick(["X", "Z", "X", "Z", "Y"]), t=rand(0, 6),
              amp=rand(25, 55), vy=rand(24, 34), shootT=rand(1.5, 3.5), flash=0.0, dead=False)
    g.minions.append(m)
    return m

def kill_minion(m):
    m.dead = True
    G.g.score += 20
    G.burst(m.x, m.y, G.COL.get(m.col, G.WHITE), 14)
    if random.random() < 0.08: G.g.caps.append(G.make_cap(m.x, m.y))

def update_minions(dt, quiet):
    g = G.g
    for m in g.minions:
        m.t += dt; m.y += m.vy * dt; m.flash = max(0.0, m.flash - dt)
        m.x = clamp(m.x0 + math.sin(m.t * 1.4) * m.amp, 20, W - 20)
        m.shootT -= dt
        if m.shootT <= 0 and not quiet:
            m.shootT = rand(2.2, 4.0)
            ang = aim(m.x, m.y) if random.random() < 0.5 else math.pi / 2
            shoot(m.x, m.y + G.EH / 2, ang, 200, None)
        if m.y > G.DEATH_LINE - 12:
            # it decoheres at the threshold and sprays a last spread
            m.dead = True; G.burst(m.x, m.y, G.COL[m.col], 10)
            if not quiet: fan(m.x, m.y, math.pi / 2, 3, 0.4, 210, None)
    g.minions = [m for m in g.minions if not m.dead]

def minion_hit(b):
    for m in G.g.minions:
        if m.dead: continue
        if b.kind == "bomb" and math.hypot(b.x - m.x, b.y - m.y) < 34:
            bomb_blast(b.x, b.y); return True
        if abs(b.x - m.x) < G.EW / 2 + 2 and abs(b.y - m.y) < G.EH / 2 + 4:
            if color_hit(m, b, m.x, m.y): kill_minion(m)
            return True
    return False

def draw_minions(S):
    for m in G.g.minions:
        G.draw_enemy(S, m.x, m.y, m.col, int(m.t * 2) % 2, m.flash)


# =====================================================================
# Base class
# =====================================================================
class Boss:
    kind = ""
    def __init__(self, tier, two):
        self.tier, self.two = tier, two
        self.t = 0.0; self.intro = INTRO; self.flash = 0.0
        self.hp = self.maxhp = 1
        self.x, self.y = W / 2, 200     # where the victory explosion goes
    @property
    def defeated(self): return self.hp <= 0
    def rate(self, base):
        """An attack interval, shorter per tier and with two players."""
        return base * 0.85 ** self.tier * (0.8 if self.two else 1.0)
    def enter(self, dt): pass
    def update(self, dt): pass
    def hit(self, b): return False   # True if it consumed the bullet
    def draw(self, S): pass


# =====================================================================
# LOGICAL ERROR: Centipede-style chain of errors
# =====================================================================
STEP = 3                 # px between recorded path points
SEG_GAP = 30             # px between segments along the path
K = SEG_GAP // STEP      # path points per segment
SEG_R = 14
ROW_H = 39               # a multiple of STEP, so rows stay aligned
C_TOP = TOP + 40
MARGIN = 30

def heading(path, fallback):
    """Horizontal direction the head of `path` (newest point first) last moved."""
    for i in range(1, len(path)):
        dx = path[i - 1][0] - path[i][0]
        if dx: return 1 if dx > 0 else -1
    return fallback

def split_chain(ch, i):
    """Remove segment i from chain `ch`; returns the chains left over (0-2).

    Every surviving segment keeps exactly its position: the front part keeps
    the path, the back part's path starts where its new head already is.
    """
    out = []
    if i > 0:
        out.append(G.Obj(segs=ch.segs[:i], path=ch.path[:(i - 1) * K + 1], dir=ch.dir, down=ch.down))
    if i + 1 < len(ch.segs):
        path = ch.path[(i + 1) * K:]
        d = heading(path, ch.dir)
        y = path[0][1]
        r = (y - C_TOP) / ROW_H
        down = 0.0
        if r - math.floor(r) > 0.01:          # mid-descent: finish it, then turn
            down = (math.floor(r) + 1) * ROW_H + C_TOP - y
        out.append(G.Obj(segs=ch.segs[i + 1:], path=path, dir=d, down=down))
    return out

class Centipede(Boss):
    kind = "centipede"
    def __init__(self, tier, two):
        super().__init__(tier, two)
        n = 14 + 3 * tier + (2 if two else 0)
        y_share = 0.2 + 0.05 * tier
        segs = [G.Obj(col="Y" if random.random() < y_share else pick(["X", "Z"]), flash=0.0,
                      turret=(k % 4 == 1), tele=0.0) for k in range(n)]
        self.chains = [self._fresh(segs)]
        self.hp = self.maxhp = n
        self.fireT = 2.0

    def _fresh(self, segs):
        """A chain entering at the top, from a random side."""
        left = random.random() < 0.5
        x0 = MARGIN if left else W - MARGIN; d = 1 if left else -1
        path = [(x0 - d * k * STEP, C_TOP) for k in range(len(segs) * K + 1)]
        return G.Obj(segs=segs, path=path, dir=d, down=0.0)

    def segs_at(self):
        for ch in self.chains:
            for i, s in enumerate(ch.segs):
                yield ch, i, s, ch.path[min(i * K, len(ch.path) - 1)]

    def speed(self):
        left = self.hp / self.maxhp
        return 120 + 15 * self.tier + 100 * (1 - left)

    def move(self, dt):
        for ch in self.chains:
            ch.carry = ch.get("carry", 0.0) + self.speed() * dt
            while ch.carry >= STEP:
                ch.carry -= STEP
                x, y = ch.path[0]
                if ch.down <= 0 and not MARGIN <= x + ch.dir * STEP <= W - MARGIN:
                    ch.down = ROW_H     # at a wall: one row down, then turn around
                if ch.down > 0:
                    y += STEP; ch.down -= STEP
                    if ch.down <= 0: ch.down = 0.0; ch.dir *= -1
                else:
                    x += ch.dir * STEP
                ch.path.insert(0, (x, y))
            del ch.path[(len(ch.segs) - 1) * K + 1:]

    def enter(self, dt): self.move(dt)

    def update(self, dt):
        self.move(dt)
        for ch in self.chains:
            if ch.path[0][1] + SEG_R > G.DEATH_LINE:
                leak("The error chain reached the qubits")
                fresh = self._fresh(ch.segs); ch.path, ch.dir, ch.down = fresh.path, fresh.dir, 0.0
        # turrets: a segment flashes, then fires
        self.fireT -= dt
        if self.fireT <= 0:
            self.fireT = self.rate(1.15) * rand(0.7, 1.3)
            onscreen = [s for _, _, s, (x, y) in self.segs_at() if 0 < x < W]
            guns = [s for s in onscreen if s.turret] or onscreen
            if guns: pick(guns).tele = 0.4
        for ch, i, s, (x, y) in self.segs_at():
            s.flash = max(0.0, s.flash - dt)
            if s.tele > 0:
                s.tele -= dt
                if s.tele <= 0:
                    sp = 200 + 20 * self.tier
                    if random.random() < 0.6: shoot(x, y + SEG_R, aim(x, y), sp, None)
                    else: fan(x, y + SEG_R, math.pi / 2, 3, 0.35, sp, None)
        hx, hy = self.chains[0].path[0] if self.chains else (W / 2, 200)
        self.x, self.y = hx, hy

    def hit(self, b):
        r = 60 if b.kind == "bomb" else SEG_R + 4
        found = None
        for ch, i, s, (x, y) in self.segs_at():
            if 0 < x < W and math.hypot(b.x - x, b.y - y) < r: found = (ch, i, s, x, y); break
        if not found: return False
        if b.kind == "bomb":
            bomb_blast(b.x, b.y)
            while True:     # the blast takes every segment in range
                near = [(ch, i) for ch, i, s, (x, y) in self.segs_at() if math.hypot(b.x - x, b.y - y) < 90]
                if not near: break
                self.remove(*near[0])
            return True
        ch, i, s, x, y = found
        if color_hit(s, b, x, y): self.remove(ch, i)
        return True

    def remove(self, ch, i):
        x, y = ch.path[min(i * K, len(ch.path) - 1)]
        G.burst(x, y, G.COL[ch.segs[i].col], 14)
        k = self.chains.index(ch)
        self.chains[k:k + 1] = split_chain(ch, i)
        self.hp -= 1; G.g.score += 40
        if random.random() < 0.06: G.g.caps.append(G.make_cap(x, y))

    def draw(self, S):
        for ch in self.chains:
            pts = [ch.path[min(i * K, len(ch.path) - 1)] for i in range(len(ch.segs))]
            if len(pts) > 1: pygame.draw.lines(S, G.fade(G.SPECIAL["bias"], 0.5), False, pts, 3)
        for ch in self.chains:
            for i in range(len(ch.segs) - 1, -1, -1):
                s = ch.segs[i]; x, y = ch.path[min(i * K, len(ch.path) - 1)]
                if not -SEG_R < x < W + SEG_R: continue
                c = G.WHITE if s.flash > 0 else G.COL[s.col]
                r = SEG_R + 2 if i == 0 else SEG_R
                pygame.draw.circle(S, c, (int(x), int(y)), r)
                if i == 0:
                    pygame.draw.circle(S, G.WHITE, (int(x), int(y)), r + 2, 2)
                    for ex in (-5, 5): S.fill(G.WHITE, (int(x + ex - 2), int(y - r + 3), 4, 4))
                if s.turret: S.fill(G.BG, (int(x - 2), int(y + r - 6), 4, 4))
                if s.tele > 0:
                    G.glow(S, x, y, 26, G.WHITE, 0.5)
                    pygame.draw.circle(S, G.WHITE, (int(x), int(y)), int(r + 4 + s.tele * 20), 2)
                G.text(S, s.col, 10, G.BG, x + 1, y + 1)


# =====================================================================
# WAVE PACKET: hittable only while collapsed
# =====================================================================
WIDE_SIGMA, NARROW_SIGMA = 105.0, 16.0

class Packet(Boss):
    kind = "packet"
    def __init__(self, tier, two):
        super().__init__(tier, two)
        self.hp = self.maxhp = 30 + 8 * tier + (6 if two else 0)
        self.x, self.y = W / 2, -60
        self.vx = self.vy = 0.0
        self.sigma = WIDE_SIGMA
        self.phase, self.phaseT = "wide", 4.0
        self.col = "X"
        self.rainT = self.minT = self.kickT = self.shotT = 1.0
        self.goal = (W / 2, 200)
        self.told = False      # "NOT LOCALIZED" hint shown this wide phase

    @property
    def hittable(self): return self.phase == "narrow"

    def enter(self, dt):
        self.y += (200 - self.y) * min(1.0, dt * 2)

    def set_phase(self, ph):
        self.phase = ph
        if ph == "collapse":
            self.phaseT = 0.6; G.play("telegraph")
            self.col = pick(["X", "Z", "Y"] if self.tier and not self.two else ["X", "Z"])
            G.pop(self.x, self.y - 70, "MEASURED!", G.WHITE, 12, 0.9)
        elif ph == "narrow":
            self.phaseT = 3.2; self.kickT = 0.0; self.shotT = 1.0
        elif ph == "spread": self.phaseT = 0.8; self.vx = self.vy = 0.0
        else: self.phaseT = max(2.2, 4.2 - 0.4 * self.tier); self.told = False

    def update(self, dt):
        self.phaseT -= dt
        if self.phaseT <= 0:
            self.set_phase({"wide": "collapse", "collapse": "narrow", "narrow": "spread", "spread": "wide"}[self.phase])
        target = {"wide": WIDE_SIGMA, "spread": WIDE_SIGMA}.get(self.phase, NARROW_SIGMA)
        self.sigma += (target - self.sigma) * min(1.0, dt * (8 if self.phase == "collapse" else 3))

        if self.phase == "narrow":
            # sharp in x, so wild in p: random momentum kicks
            self.kickT -= dt
            if self.kickT <= 0:
                self.kickT = rand(0.35, 0.6); a = rand(0, 2 * math.pi); s = rand(230, 360 + 30 * self.tier)
                self.vx, self.vy = math.cos(a) * s, math.sin(a) * s * 0.6
            self.x += self.vx * dt; self.y += self.vy * dt
            if not 60 < self.x < W - 60: self.vx = -self.vx; self.x = clamp(self.x, 60, W - 60)
            if not TOP + 50 < self.y < 380: self.vy = -self.vy; self.y = clamp(self.y, TOP + 50, 380)
            self.shotT -= dt
            if self.shotT <= 0:
                self.shotT = self.rate(1.3); fan(self.x, self.y, aim(self.x, self.y), 3, 0.25, 210)
        elif self.phase == "wide":
            # drifts, and rains bullets from anywhere under its envelope
            if math.hypot(self.goal[0] - self.x, self.goal[1] - self.y) < 20:
                self.goal = (rand(180, W - 180), rand(TOP + 80, 280))
            self.x += (self.goal[0] - self.x) * min(1.0, dt * 0.8)
            self.y += (self.goal[1] - self.y) * min(1.0, dt * 0.8)
            self.rainT -= dt
            if self.rainT <= 0:
                self.rainT = self.rate(0.16)
                bx = clamp(random.gauss(self.x, self.sigma), 10, W - 10)
                shoot(bx, self.y + rand(-15, 15), math.pi / 2 + rand(-0.2, 0.2), rand(140, 190))
            self.minT -= dt
            if self.minT <= 0:
                self.minT = self.rate(3.5)
                spawn_minion(clamp(random.gauss(self.x, self.sigma), 40, W - 40), self.y + 20)

    def inside(self, b, wide):
        return abs(b.x - self.x) < (2 * self.sigma if wide else max(1.6 * self.sigma, 24)) and abs(b.y - self.y) < 45

    def hit(self, b):
        if not self.hittable:
            if self.inside(b, True):
                if b.kind == "bomb" and self.phase == "wide":
                    bomb_blast(b.x, b.y); self.set_phase("collapse"); return True
                if not self.told:
                    self.told = True
                    G.pop(self.x, self.y + 60, "NOT LOCALIZED - WAIT!", (170, 170, 170), 10, 1.2)
            return False    # passes straight through
        if not self.inside(b, False): return False
        if b.kind == "bomb":
            bomb_blast(b.x, b.y); damage(self, 5, self.x, self.y); return True
        if color_hit(self, b, self.x, self.y): damage(self, 1, b.x, b.y)
        return True

    def draw(self, S):
        t = G.now()
        narrow = self.phase in ("narrow", "collapse")
        col = G.COL[self.col] if narrow else G.YELLOW
        if self.flash > 0: col = G.WHITE
        s = self.sigma
        A = 60 * math.sqrt(NARROW_SIGMA / s)    # |psi| ~ 1/sqrt(sigma): a narrow packet is taller
        if narrow: G.glow(S, self.x, self.y, 70, col, 0.5)
        span = int(min(3 * s + 10, W))
        env = lambda dx: math.exp(-(dx * dx) / (2 * s * s))
        xs = range(-span, span + 1, 3)
        up = [(self.x + dx, self.y - A * env(dx)) for dx in xs]
        dn = [(self.x + dx, self.y + A * env(dx)) for dx in reversed(xs)]
        pygame.draw.lines(S, G.fade(col, 0.35), True, up + dn, 1)
        k = 0.3 if not narrow else 0.5
        pts = [(self.x + dx, self.y - A * env(dx) * math.cos(dx * k - t * 14)) for dx in xs]
        pygame.draw.lines(S, col, False, pts, 3)
        if narrow: G.text(S, self.col, 14, G.BG if self.flash <= 0 else G.WHITE, self.x + 1, self.y + 1)


# =====================================================================
# SYNDROME: a lattice of checks, the errors hidden on the qubits
# =====================================================================
PC, PR, CELL = 8, 3, 84
LX0, LY0 = (W - PC * CELL) / 2, TOP + 50
LY1 = LY0 + PR * CELL

def lattice_qubits():
    """Every qubit of the lattice as (x, y, frozenset of the checks it flips).

    A qubit between two checks flips both; one on the left or right boundary
    only flips its single neighbour. No two qubits share a syndrome, so a
    single error is always uniquely decodable.
    """
    cx = lambda c: LX0 + (c + 0.5) * CELL
    cy = lambda r: LY0 + (r + 0.5) * CELL
    qs = []
    for r in range(PR):
        qs.append((LX0, cy(r), frozenset({(0, r)})))
        qs.append((LX0 + PC * CELL, cy(r), frozenset({(PC - 1, r)})))
        for c in range(PC - 1):
            qs.append((LX0 + (c + 1) * CELL, cy(r), frozenset({(c, r), (c + 1, r)})))
    for r in range(PR - 1):
        for c in range(PC):
            qs.append((cx(c), LY0 + (r + 1) * CELL, frozenset({(c, r), (c, r + 1)})))
    return qs

def near_checks(checks):
    """The checks themselves plus their 4-neighbours."""
    out = set()
    for c, r in checks:
        out |= {(c, r), (c + 1, r), (c - 1, r), (c, r + 1), (c, r - 1)}
    return out

class Syndrome(Boss):
    kind = "syndrome"
    def __init__(self, tier, two):
        super().__init__(tier, two)
        self.qubits = lattice_qubits()
        self.hp = self.maxhp = 10 + 3 * tier + (2 if two else 0)
        self.errors = []
        self.minT = 3.0; self.noiseT = 1.0; self.roundT = 0.0
        self.x, self.y = W / 2, (LY0 + LY1) / 2
        self.drop = -260.0   # lattice slides in from the top during the intro

    def enter(self, dt): self.drop = min(0.0, self.drop + 160 * dt)

    def lit(self):
        out = {}
        for e in self.errors:
            for ch in e.q[2]: out[ch] = e
        return out

    def add_error(self):
        busy = near_checks(self.lit().keys())
        free = [q for q in self.qubits if not (q[2] & busy)]
        if not free: return
        y_share = 0.15 + 0.05 * self.tier
        self.errors.append(G.Obj(q=pick(free), col="Y" if random.random() < y_share else pick(["X", "Z"]),
                                 t=0.0, life=max(5.0, 8.5 - self.tier), flash=0.0))

    def update(self, dt):
        self.drop = 0.0
        done = self.maxhp - self.hp
        want = min(3, 1 + done // 4 + self.tier, self.hp)
        while len(self.errors) < want:
            n = len(self.errors); self.add_error()
            if len(self.errors) == n: break
        for e in self.errors:
            e.t += dt; e.flash = max(0.0, e.flash - dt)
            if e.t > e.life:
                # uncorrected: the lit checks fire, and the error moves elsewhere
                e.dead = True
                G.pop(e.q[0], e.q[1] - 30, "TOO SLOW!", (200, 200, 200), 10, 1.0)
                for c, r in e.q[2]:
                    fan(LX0 + (c + 0.5) * CELL, LY0 + (r + 0.5) * CELL, math.pi / 2, 5, 0.3, 190)
        self.errors = [e for e in self.errors if not e.get("dead")]
        # measurement rounds: a few quiet checks misfire as noise
        self.roundT -= dt
        if self.roundT <= 0: self.roundT = 1.2
        self.noiseT -= dt
        if self.noiseT <= 0:
            self.noiseT = self.rate(0.9)
            lit = self.lit()
            quiet = [(c, r) for c in range(PC) for r in range(PR) if (c, r) not in lit]
            if quiet:
                c, r = pick(quiet); x, y = LX0 + (c + 0.5) * CELL, LY0 + (r + 0.5) * CELL
                shoot(x, y, aim(x, y) if random.random() < 0.4 else math.pi / 2, 190)
        self.minT -= dt
        if self.minT <= 0:
            self.minT = self.rate(3.4)
            spawn_minion(LX0 + (random.randrange(PC) + 0.5) * CELL, LY1 + 10)

    def hit(self, b):
        if b.kind == "bomb":
            if b.y > LY1: return False
            bomb_blast(b.x, b.y)
            for e in self.errors:
                if math.hypot(e.q[0] - b.x, e.q[1] - b.y) < 140: e.dead = True; damage(self, 1, e.q[0], e.q[1])
            self.errors = [e for e in self.errors if not e.get("dead")]
            return True
        for e in self.errors:
            x, y = e.q[0], e.q[1]
            if abs(b.x - x) < 14 and abs(b.y - y) < 16:
                if color_hit(e, b, x, y):
                    e.dead = True; damage(self, 1, x, y)
                    G.pop(x, y - 24, "CORRECTED", G.SPECIAL["bias"], 10, 0.9)
                    self.errors = [o for o in self.errors if not o.get("dead")]
                return True
        return False    # a guess at a healthy qubit just passes through

    def draw(self, S):
        t = G.now(); oy = self.drop
        lit = self.lit()
        pulse = 0.55 + 0.3 * math.sin(t * 8)
        rnd = self.roundT > 1.05     # brief brightening at each measurement round
        for c in range(PC):
            for r in range(PR):
                x, y = LX0 + c * CELL, LY0 + r * CELL + oy
                e = lit.get((c, r))
                if e:
                    col = G.COL[e.col]
                    S.fill(G.fade(col, 0.25 + 0.2 * pulse), (x + 3, y + 3, CELL - 6, CELL - 6))
                    G.glow(S, x + CELL / 2, y + CELL / 2, 50, col, 0.3)
                    pygame.draw.rect(S, col, (x + 3, y + 3, CELL - 6, CELL - 6), 3)
                    G.text(S, "!", 14, G.WHITE, x + CELL / 2, y + CELL / 2)
                else:
                    pygame.draw.rect(S, G.fade(G.SPECIAL["bias"], 0.4 if rnd else 0.22), (x + 3, y + 3, CELL - 6, CELL - 6), 2)
        for side in (LX0, LX0 + PC * CELL):   # boundaries
            G.dashed_line(S, G.fade(G.WHITE, 0.45), (side, LY0 + oy), (side, LY1 + oy), 6, 6, 2)
        errs = {e.q: e for e in self.errors}
        for q in self.qubits:
            x, y = q[0], q[1] + oy
            e = errs.get(q)
            hint = e and e.t > e.life * 0.5
            c = G.WHITE if (e and e.flash > 0) else (190, 190, 205)
            S.fill(c, (int(x - 3), int(y - 3), 6, 6))
            if hint:
                rr = 8 + 4 * math.sin(t * 10)
                pygame.draw.circle(S, G.fade(G.COL[e.col], 0.7), (int(x), int(y)), int(rr), 1)
        G.text(S, "lit check = syndrome  ·  shoot the qubit between", 8, (110, 120, 120), W / 2, LY1 + 14 + oy)


# =====================================================================
# CLIFFORD CORE: only a magic state hurts it
# =====================================================================
CORE_R, SHIELD_R = 40, 62
PATTERNS = ["spiral", "color", "rings", "color", "fans", "color"]

class Clifford(Boss):
    kind = "clifford"
    def __init__(self, tier, two):
        super().__init__(tier, two)
        self.hp = self.maxhp = 3 + tier + (1 if two else 0)
        self.x, self.y, self.cx = W / 2, -80, W / 2
        self.pi = -1; self.pat = None; self.patT = 0.0
        self.emitT = 0.0; self.spin = 0.0
        self.col = None; self.tele = 0.0
        self.shieldF = 0.0; self.broken = 0.0; self.immuneT = 0.0
        self.next_pattern()

    @property
    def heat(self): return 1 + 0.15 * (self.maxhp - self.hp) + 0.1 * self.tier

    def enter(self, dt): self.y += (190 - self.y) * min(1.0, dt * 2)

    def next_pattern(self):
        self.pi = (self.pi + 1) % len(PATTERNS)
        self.pat = PATTERNS[self.pi]; self.emitT = 0.4
        if self.pat == "color":
            self.col = pick(["X", "Z", "Y"] if not self.two else ["X", "Z", "X", "Z", "Y"])
            self.tele = 0.9; self.patT = 2.6; self.shots = 0
            G.play("telegraph")
            G.pop(self.x, self.y + 90, "ABSORB %s!" % self.col, G.COL[self.col], 12, 1.4)
        else:
            self.col = None; self.patT = 3.8

    def update(self, dt):
        self.enter(dt)
        self.x = self.cx + math.sin(self.t * 0.5) * 200
        self.shieldF = max(0.0, self.shieldF - dt); self.broken = max(0.0, self.broken - dt)
        self.immuneT = max(0.0, self.immuneT - dt)
        if self.broken > 0: return     # stunned by the last bomb
        self.patT -= dt
        if self.patT <= 0: self.next_pattern(); return
        h = self.heat
        self.emitT -= dt
        if self.pat == "color":
            if self.tele > 0: self.tele -= dt; return
            # wide colored curtains, hard to dodge: switch to that color and catch them
            if self.emitT <= 0 and self.shots < 5:
                self.emitT = 0.38; self.shots += 1
                base = math.pi / 2 + (0.07 if self.shots % 2 else -0.07)
                for i in range(9):
                    shoot(self.x, self.y + CORE_R, base + (i - 4) * 0.14, 165, "orb", self.col)
            return
        if self.emitT > 0: return
        if self.pat == "spiral":
            self.emitT = 0.11 / h; self.spin += 0.32
            arms = 2 + (self.maxhp - self.hp) // 2
            ring(self.x, self.y, arms, 150 * min(h, 1.4), self.spin, SHIELD_R)
        elif self.pat == "rings":
            self.emitT = 0.95 / h; ring(self.x, self.y, int(14 + 4 * self.tier), 140 * min(h, 1.4), self.spin, SHIELD_R)
            self.spin += 0.2
        elif self.pat == "fans":
            self.emitT = 0.7 / h; fan(self.x, self.y + CORE_R, aim(self.x, self.y), 5, 0.18, 200)

    def hit(self, b):
        if math.hypot(b.x - self.x, b.y - self.y) > SHIELD_R + 6: return False
        if b.kind == "bomb":
            bomb_blast(b.x, b.y); damage(self, 1, self.x, self.y)
            G.g.eb = [q for q in G.g.eb if math.hypot(q.x - self.x, q.y - self.y) > 280]
            self.broken = 1.2
            G.pop(self.x, self.y - 90, "NON-CLIFFORD HIT!", G.SPECIAL["bomb"], 14, 1.5)
            return True
        self.shieldF = 0.15
        G.burst(b.x, b.y, (200, 220, 255), 4, 90); G.play("shield")
        if not self.immuneT:
            self.immuneT = 2.0
            G.pop(self.x, self.y - 85, "IMMUNE TO PAULIS", (190, 200, 220), 10, 1.0)
        return True

    def draw(self, S):
        t = G.now(); x, y = self.x, self.y
        core = G.COL[self.col] if self.col else (200, 205, 220)
        if self.tele > 0 and int(t * 12) % 2: core = G.WHITE
        if self.flash > 0 or self.broken > 1.0: core = G.WHITE
        G.glow(S, x, y, 90, core, 0.35)
        # shield: hexagon that blinks, brighter when a shot bounces off it
        if self.broken <= 0:
            blink = 0.45 + 0.25 * math.sin(t * 9)
            a = 1.0 if self.shieldF > 0 else blink
            hexa = [(x + SHIELD_R * math.cos(t * 0.6 + k * math.pi / 3), y + SHIELD_R * math.sin(t * 0.6 + k * math.pi / 3))
                    for k in range(6)]
            pygame.draw.polygon(S, G.fade((170, 200, 255), a), hexa, 3)
        else:
            for k in range(6):
                a = t * 3 + k
                pygame.draw.line(S, G.fade((170, 200, 255), 0.4), (x + 50 * math.cos(a), y + 50 * math.sin(a)),
                                 (x + 70 * math.cos(a), y + 70 * math.sin(a)), 2)
        pygame.draw.circle(S, core, (int(x), int(y)), CORE_R)
        pygame.draw.circle(S, G.BG, (int(x), int(y)), CORE_R - 8, 2)
        for k in range(4):
            a = -t * 2 + k * math.pi / 2
            pygame.draw.line(S, G.BG, (x, y), (x + (CORE_R - 10) * math.cos(a), y + (CORE_R - 10) * math.sin(a)), 3)
        G.text(S, "C", 16, G.BG, x + 1, y + 1)


# =====================================================================
# BELL PAIR: two entangled halves, hit both at once
# =====================================================================
class Bell(Boss):
    kind = "bell"
    def __init__(self, tier, two):
        super().__init__(tier, two)
        self.hp = self.maxhp = 12 + 4 * tier + (3 if two else 0)
        self.window = 0.5 if two else 1.2
        self.col = pick(["X", "Z"])
        self.halves = [G.Obj(x=0.0, y=0.0, mark=0.0, flash=0.0, col=self.col) for _ in range(2)]
        self.theta = 0.0; self.cy = -80.0
        self.fireT = 1.5; self.ringT = 3.0; self.minT = 4.0
        self.tether = 0.0
        self.place()

    def place(self):
        t = self.t
        self.x = W / 2 + math.sin(t * 0.4) * 140
        self.y = self.cy + math.sin(t * 0.7) * 35
        d = 60 + 160 * (0.5 + 0.5 * math.sin(t * 0.55))
        for k, h in enumerate(self.halves):
            s = 1 if k == 0 else -1
            h.x = self.x + s * d * math.cos(self.theta)
            h.y = self.y + s * d * math.sin(self.theta) * 0.45

    def enter(self, dt):
        self.cy += (210 - self.cy) * min(1.0, dt * 2); self.t += dt; self.place()

    def update(self, dt):
        self.theta += (0.6 + 0.1 * self.tier) * dt
        self.cy += (210 - self.cy) * min(1.0, dt * 2)
        self.place()
        self.tether = max(0.0, self.tether - dt)
        for h in self.halves:
            h.flash = max(0.0, h.flash - dt)
            if h.mark > 0:
                h.mark -= dt
                if h.mark <= 0:
                    G.pop(h.x, h.y - 40, "HEALED", G.SPECIAL["bias"], 10, 0.9)
                    G.burst(h.x, h.y, G.SPECIAL["bias"], 10, 120)
        # correlated noise: whatever one half fires, the other fires mirrored
        self.fireT -= dt
        if self.fireT <= 0:
            self.fireT = self.rate(1.0)
            a, b = self.halves
            ang = aim(a.x, a.y)
            fan(a.x, a.y, ang, 2, 0.2, 200)
            fan(b.x, b.y, math.atan2(math.sin(ang), -math.cos(ang)), 2, 0.2, 200)
        self.ringT -= dt
        if self.ringT <= 0:
            self.ringT = self.rate(3.2)
            for h in self.halves: ring(h.x, h.y, 10, 130, self.theta)
        self.minT -= dt
        if self.minT <= 0:
            self.minT = self.rate(4.5)
            col = pick(["X", "Z"])      # a correlated pair, wavering in mirror image
            a, b = (spawn_minion(clamp(h.x, 40, W - 40), h.y + 30, col) for h in self.halves)
            if a and b: b.t, b.amp = a.t, -a.amp

    def hit(self, b):
        for k, h in enumerate(self.halves):
            if math.hypot(b.x - h.x, b.y - h.y) > 28: continue
            if b.kind == "bomb":
                bomb_blast(b.x, b.y); damage(self, 3, h.x, h.y); return True
            if b.col != "all" and b.col != self.col:
                h.flash = 0.12; G.burst(b.x, b.y, (136, 136, 136), 5, 80); G.play("block")
                return True
            other = self.halves[1 - k]
            if other.mark > 0:
                other.mark = h.mark = 0.0; self.tether = 0.4
                damage(self, 1, h.x, h.y); G.burst(other.x, other.y, G.WHITE, 10, 200)
                G.pop(self.x, self.y - 50, "ENTANGLED HIT!", G.WHITE, 12, 0.9)
                if random.random() < 0.5:         # measured again: the basis may flip
                    self.col = "Z" if self.col == "X" else "X"
                    for o in self.halves: o.col = self.col
            else:
                h.mark = self.window; h.flash = 0.1; G.play("kill")
            return True
        return False

    def draw(self, S):
        t = G.now()
        a, b = self.halves
        tc = G.WHITE if self.tether > 0 else G.hue(t * 120, 50, 100)
        G.dashed_line(S, tc, (a.x, a.y), (b.x, b.y), 6, 6, 3 if self.tether > 0 else 2)
        G.text(S, "|Φ+>", 10, (200, 200, 220), self.x, self.y - 4)
        for h in self.halves:
            col = G.WHITE if (h.flash > 0 or self.flash > 0) else G.COL[self.col]
            G.glow(S, h.x, h.y, 50, G.COL[self.col], 0.35)
            pygame.draw.circle(S, col, (int(h.x), int(h.y)), 24)
            G.text(S, self.col, 14, G.BG, h.x + 1, h.y + 1)
            if h.mark > 0:
                k = h.mark / self.window
                rr = pygame.Rect(0, 0, 66, 66); rr.center = (int(h.x), int(h.y))
                pygame.draw.arc(S, G.WHITE, rr, math.pi / 2, math.pi / 2 + 2 * math.pi * k, 4)


KINDS = {"centipede": Centipede, "packet": Packet, "syndrome": Syndrome, "clifford": Clifford, "bell": Bell}

def make_boss(kind, tier, two):
    return KINDS[kind](tier, two)


# =====================================================================
# Hooks called from game.py
# =====================================================================
def update(dt):
    g = G.g; b = g.boss
    quiet = b.intro > 0 or bool(g.overDelay)
    update_minions(dt, quiet)
    if b.intro > 0:
        b.intro -= dt; b.enter(dt); return
    b.t += dt; b.flash = max(0.0, b.flash - dt)
    if not g.overDelay: b.update(dt)
    if b.defeated and not g.overDelay: victory()

def victory():
    g = G.g; b = g.boss
    for k in range(3): G.burst(b.x + rand(-60, 60), b.y + rand(-40, 40), G.WHITE, 40, 360)
    G.burst(b.x, b.y, G.SPECIAL["bomb"], 60, 420)
    G.play("boom_l"); g.shake = 0.8
    for m in g.minions: G.burst(m.x, m.y, G.COL[m.col], 10)
    g.minions = []; g.eb = []
    bonus = 2000 * (1 + b.tier); g.score += bonus
    G.pop(W / 2, 300, "%s CORRECTED!" % INFO[b.kind][0].split(" |")[0], G.SPECIAL["bias"], 16, 2.6)
    G.pop(W / 2, 335, "+%d" % bonus, G.WHITE, 12, 2.6)
    G.arp(["n523", "n659", "n784", "n1047", "n1319"], 0.09)
    for dx in (-60, 60): g.caps.append(G.make_cap(clamp(b.x + dx, 40, W - 40), clamp(b.y, 80, 400)))
    g.boss = None; g.waveT = 3.0

def bullet_hit(b):
    """Player bullet vs minions and boss. True if the bullet is used up."""
    g = G.g
    if minion_hit(b): return True
    return g.boss is not None and g.boss.intro <= 0 and g.boss.hit(b)

def absorb(p, b):
    """A colored boss shot meeting a ship of the same color: charge, don't die."""
    g = G.g
    G.g.parts.append(G.Obj(ring=True, x=p.x, y=p.y, r=8, life=0.25, col=G.COL[b.col]))
    G.burst(b.x, b.y, G.COL[b.col], 6, 60)
    G.play("absorb")
    ships = [q for q in g.players if not q.out] if p is g.merged else [p]
    for q in ships:
        q.absorbT = 0.25
        if q.bombT > 0: continue
        q.magic += 1
        if q.magic >= MAGIC_NEEDED:
            q.magic = 0; q.bombT = G.BOMB_CHARGE
            G.pop(q.x, q.y - 60, "MAGIC STATE!", G.SPECIAL["bomb"], 12, 1.4)
    G.pop(p.x + rand(-10, 10), p.y - 34, "+MAGIC", G.SPECIAL["bomb"], 8, 0.5)

def draw(S):
    g = G.g
    if g.boss: g.boss.draw(S)
    draw_minions(S)

def draw_overlay(S):
    """Boss health bar and, during the intro, the boss's name card."""
    b = G.g.boss
    if not b: return
    name, l1, l2 = INFO[b.kind]
    if b.intro > 0:
        a = clamp(min(b.intro, INTRO - b.intro) * 2.5, 0, 1)
        shade = pygame.Surface((W, 150), pygame.SRCALPHA); shade.fill((0, 0, 0, int(170 * a)))
        S.blit(shade, (0, 395))
        G.text(S, "- BOSS -", 12, G.fade(G.COL["X"], a), W / 2, 418)
        G.text(S, name, 26, G.fade(G.WHITE, a), W / 2, 452)
        G.text(S, l1, 10, G.fade((190, 190, 200), a), W / 2, 490)
        G.text(S, l2, 10, G.fade(G.YELLOW, a), W / 2, 512)
        return
    bw = 360; x0 = (W - bw) / 2
    G.text(S, name, 8, (200, 200, 210), W / 2, 52)
    S.fill((40, 40, 52), (x0, 60, bw, 6))
    S.fill(G.COL["X"] if b.flash <= 0 else G.WHITE, (x0, 60, int(bw * b.hp / b.maxhp), 6))
