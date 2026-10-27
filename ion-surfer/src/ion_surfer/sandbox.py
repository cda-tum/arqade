"""SANDBOX mode: real quantum motion in the electrode trap, no scrolling.

Both players shape one shared potential (like co-op). Instead of the
classical ion, the motion is simulated quantum mechanically:

- 1 ion: its full wave packet on a grid (quantum.WavePacket), drawn with its
  phase as colour.
- 2-4 ions: a Coulomb crystal (crystal.Crystal): one wave packet per normal
  mode (COM, stretch, ...), each ion drawn as its position distribution.

A cockpit along the top shows what the motion is doing, per mode:

- MOTIONAL STATE: Fock populations |<n|psi>|^2 in the mode's harmonic basis
- PHASE SPACE: the Gaussian blob (covariance ellipse) -- displaced, squeezed,
  and the phase it rotates through
- SCOPE: displacement and width over time -- breathing shows up as the width
  oscillating at twice the mode frequency
- READOUT: frequency, <n>, |alpha|, phase, squeezing

All of that is relative to the harmonic approximation of the well. When the
packet stops being Gaussian for a while (what an anharmonic potential does
to it), the phase-space panel gets a red edge and says ANHARMONIC.

Rendering and input glue only; the physics lives in quantum.py / crystal.py.
"""

from __future__ import annotations

import cmath
import math
from collections import deque
from dataclasses import dataclass

import pygame

from ion_surfer.crystal import Crystal, Sampled, mode_name
from ion_surfer.quantum import Moments, PhaseSpace, Trap, WavePacket

# ============================== TUNING ==============================
Q_N = 400                 # grid points across the screen (3 px each), single ion
Q_HBAR_M = 3800.0         # hbar/m in px^2/s: sets the ground-state width (~22 px)
Q_COUPLING = 2.9          # potential in rad/s per px of curve height (sets the trap frequency)
Q_COULOMB = 2000.0        # ion-ion repulsion in rad/s * px (~100 px spacing in the start trap)
MAX_IONS = 4
Q_DT = 1 / 120            # s per time step of the single ion's packet (4th order, see quantum.PADE)
CRYSTAL_DT = 1 / 60       # ... and of each crystal mode's (several packets per frame)
KICK = 1.5                # laser kick, in units of 1/sigma0 (moves alpha by 1.5 i)
COOL_DAMPING = 0.6        # imaginary part of the time step while red holds L (strong cooling)
PASSIVE_DAMPING = 0.04    # ... and with passive cooling toggled on (red R): a slow, steady drain
SANDBOX_RATE = 300        # electrode voltage change per second (a bit slower than the game)
FOCK_LEVELS = 16
ANHARMONIC_AREA = 1.3     # uncertainty area (vacuum = 1) past which the ellipse leaves too much out
ANHARMONIC_HOLD = 1.0     # s the area must stay past it (or back under it) before the warning flips
SCOPE_SECONDS = 6.0
DENSITY_SCALE = 4200      # px of packet height per unit probability density
DENSITY_MAX = 230


# Shape of the trap at the start: a gentle bowl centred on the screen.
def start_voltages(n_nodes, vmin, vmax):
    return [min(vmax, max(vmin, 60 + 7 * (i - 5.5) ** 2)) for i in range(n_nodes)]


PANEL_TOP, PANEL_H = 10, 186
PANEL_BG = (10, 16, 36, 215)
PANEL_EDGE = (70, 90, 150)
TITLE_C = (150, 165, 215)
TEXT_C = (215, 222, 245)
DIM_C = (110, 120, 160)
GOLD = (255, 211, 107)
CYAN = (110, 220, 255)
PINK = (255, 120, 190)
GREEN = (120, 255, 160)
WARN_C = (226, 92, 108)
WARN_EDGE = (176, 72, 92)  # muted, like PANEL_EDGE
PURPLE = (199, 155, 255)
MODE_COLORS = (GOLD, CYAN, PINK, GREEN)
ION_COLORS = ((78, 168, 255), (255, 84, 112), (120, 255, 160), (255, 211, 107))


@dataclass
class ModeView:
    """Everything the cockpit shows about one mode (or the single ion)."""

    name: str
    color: tuple[int, int, int]
    trap: Trap | None
    moments: Moments
    ps: PhaseSpace | None
    pops: list[float]
    stray: bool = False  # a crystal mode's packet sits in another well than the equilibrium

    @property
    def mean_n(self) -> float:
        """<a^dagger a> from the moments: exact, even beyond the plotted Fock levels."""
        if self.ps is None:
            return 0.0
        ps = self.ps
        return max(0.0, (ps.var_q + ps.q * ps.q + ps.var_p + ps.p * ps.p - 2) / 4)

    @property
    def short(self) -> str:
        return {"STRETCH": "STR", "EGYPTIAN": "EGY"}.get(self.name, self.name.replace("MODE ", "M").replace("ION ", "I"))


def _text(surf, s, font, color, pos, anchor="center"):
    img = font.render(s, True, color)
    r = img.get_rect(**{anchor: pos})
    surf.blit(img, r)
    return r


def _phase_palette(n=48):
    out = []
    for k in range(n):
        c = pygame.Color(0)
        c.hsva = (k * 360 / n, 55, 100, 100)
        out.append((c.r, c.g, c.b))
    return out


def _dim(c, f):
    return (int(c[0] * f), int(c[1] * f), int(c[2] * f))


def _mix(a, b, f):
    return tuple(round(x + (y - x) * f) for x, y in zip(a, b))


class Sandbox:
    """Owns the quantum state and draws the cockpit. `potential(x)` samples
    the shared curve in px of height."""

    def __init__(self, potential, width, height, ground, fonts):
        self.potential = potential
        self.w, self.h, self.ground = width, height, ground
        self.f_title, self.f_small, self.f_tiny = fonts
        self.wp = WavePacket(Q_N, width, Q_HBAR_M)
        self.crystal = None
        self.palette = _phase_palette()
        self.panels = {
            "fock": pygame.Rect(12, PANEL_TOP, 372, PANEL_H),
            "phase": pygame.Rect(396, PANEL_TOP, 240, PANEL_H),
            "scope": pygame.Rect(648, PANEL_TOP, 348, PANEL_H),
            "readout": pygame.Rect(1008, PANEL_TOP, 180, PANEL_H),
        }
        self.bg = self._make_cockpit_bg()
        ph = self.panels["phase"]
        self.blob = pygame.Surface((ph.w - 16, ph.h - 34), pygame.SRCALPHA)
        self.t = 0.0
        self.frame = 0
        self.unit = 10.0
        self._acc = 0.0
        self.cooling = False
        self.passive_cooling = False  # toggled by red R, off by default
        self.anharmonic = False  # the phase-space warning, see measure()
        self._flip_at = None
        self.warn_fade = 0.0
        self.views: list[ModeView] = []
        self.trails: list[deque] = []
        self.scope: deque = deque(maxlen=int(SCOPE_SECONDS * 60))
        self.sync_potential()
        self.cool_to_ground()

    @property
    def n_ions(self) -> int:
        return self.crystal.n if self.crystal else 1

    # ---------- physics glue ----------
    def sync_potential(self):
        xs = self.wp.xs
        hs = [self.potential(x) for x in xs]
        base = min(hs)  # a constant offset only adds a global phase
        vs = [Q_COUPLING * (h - base) for h in hs]
        self.height_base = base
        self.table = Sampled(xs, vs)
        self.wp.set_potential(vs)
        if self.crystal:
            self.crystal.update_potential(self.table)

    def _reset_history(self):
        self.trails = []
        self.scope.clear()
        self.anharmonic, self._flip_at, self.warn_fade = False, None, 0.0

    def cool_to_ground(self):
        if self.crystal:
            self.crystal.cool_to_ground()
        else:
            trap = self.wp.fit_trap(self.w / 2) or self.wp.fit_trap(self.w / 2, span=30)
            if trap:
                self.wp.set_gaussian(trap.x0, trap.sigma0)
            else:
                self.wp.set_gaussian(self.w / 2, 22)
        self._reset_history()
        self.measure(force_fock=True)

    def ion_positions(self) -> list[float]:
        if self.crystal:
            return [m for m, _ in self.crystal.ion_gaussians([v.moments for v in self.views])]
        return [self.wp.moments().mean_x]

    def add_ion(self) -> bool:
        if self.n_ions >= MAX_IONS:
            return False
        xs = sorted(self.ion_positions())
        new = xs[-1] + 90 if xs[-1] + 90 < self.w - 60 else xs[0] - 90
        self.crystal = Crystal(self.table, xs + [new], Q_HBAR_M, Q_COULOMB, 30, self.w - 30)
        self._reset_history()
        self.measure(force_fock=True)
        return True

    def remove_ion(self) -> bool:
        if not self.crystal:
            return False
        xs = self.crystal.x_eq[:-1]
        if len(xs) >= 2:
            self.crystal = Crystal(self.table, xs, Q_HBAR_M, Q_COULOMB, 30, self.w - 30)
        else:
            self.crystal = None
            trap = self.wp.fit_trap(xs[0])
            self.wp.set_gaussian(trap.x0 if trap else xs[0], trap.sigma0 if trap else 22)
        self._reset_history()
        self.measure(force_fock=True)
        return True

    def kick(self, player):
        """P1's laser pushes the leftmost ion right, P2's the rightmost left."""
        direction = 1 if player == 0 else -1
        v0 = self.views[0] if self.views else None
        s0 = v0.trap.sigma0 if v0 and v0.trap else 22
        k0 = direction * KICK / s0
        if self.crystal:
            self.crystal.kick_ion(0 if player == 0 else self.crystal.n - 1, k0)
        else:
            self.wp.kick(k0)

    def step(self, dt, potential_changed, cooling):
        self.t += dt
        self.cooling = cooling
        if potential_changed:
            self.sync_potential()
        gamma = COOL_DAMPING if cooling else (PASSIVE_DAMPING if self.passive_cooling else 0.0)
        damp = gamma > 0
        # fixed steps, coarser than the game's: the coefficient cache only
        # hits for a constant dt, and the crystal has several packets to move
        h = CRYSTAL_DT if self.crystal else Q_DT
        self._acc += dt
        while self._acc >= h - 1e-9:
            self._acc -= h
            q = complex(h, -gamma * h) if damp else h
            if self.crystal:
                self.crystal.step(q, damp=damp)
            else:
                self.wp.step(q)
                if damp:
                    self.wp.normalize()

    def _view(self, name, color, wp, force_fock, old, q_eq=None):
        """A crystal mode (q_eq given) is measured against the crystal's
        equilibrium, the single ion against the well it is in."""
        m = wp.moments()
        wp.set_reference(m.energy)  # keeps the time steps' phases accurate
        trap = wp.fit_trap(m.mean_x if q_eq is None else q_eq)
        if trap is None:
            return ModeView(name, color, None, m, None, [0.0] * FOCK_LEVELS)
        stray = False
        if q_eq is not None:
            own = wp.fit_trap(m.mean_x)
            stray = own is None or abs(own.x0 - trap.x0) > trap.sigma0
        ps = wp.phase_space(m, trap)
        every = 2 if not self.crystal else 3  # Fock projections are the costly part
        if force_fock or old is None or old.trap is None or self.frame % every == 0:
            pops = wp.fock_populations(trap, FOCK_LEVELS)
        else:
            pops = old.pops
        return ModeView(name, color, trap, m, ps, pops, stray)

    def measure(self, force_fock=False):
        """Once per frame: moments, harmonic fit, phase space; Fock every other frame."""
        self.frame += 1
        old = self.views
        if self.crystal:
            cr = self.crystal
            self.views = [
                self._view(mode_name(k, cr.vecs[k]), MODE_COLORS[k % 4], wp,
                           force_fock, old[k] if k < len(old) else None, cr.q_eq[k])
                for k, wp in enumerate(cr.packets)
            ]
        else:
            self.views = [self._view("MOTION", GOLD, self.wp, force_fock, old[0] if old else None)]
        while len(self.trails) < len(self.views):
            self.trails.append(deque(maxlen=70))
        sample = []
        for k, v in enumerate(self.views):
            if v.trap is None:
                sample.append(None)
                continue
            self.trails[k].append((v.ps.q, v.ps.p))
            sample.append(((v.moments.mean_x - v.trap.x0) / v.trap.sigma0,
                           math.sqrt(v.moments.var_x) / v.trap.sigma0))
        self.scope.append(sample)
        # The cockpit pictures every mode as a Gaussian in a parabola. A
        # harmonic well keeps a Gaussian packet Gaussian, an anharmonic one
        # bends it, and that shows as a growing uncertainty area. A crystal
        # mode whose packet has settled in another well along its direction
        # is outside the picture too, Gaussian or not. An oscillating packet
        # only reaches the anharmonic part of the well now and then, so the
        # warning waits for this to last (or to be over) for a while.
        over = any(v.ps is not None and (v.ps.area() > ANHARMONIC_AREA or v.stray)
                   for v in self.views)
        if over == self.anharmonic:
            self._flip_at = None
        elif self._flip_at is None:
            self._flip_at = self.t
        elif self.t - self._flip_at >= ANHARMONIC_HOLD:
            self.anharmonic, self._flip_at = over, None
        fade = 0.1 if self.anharmonic else -0.1
        self.warn_fade = min(1.0, max(0.0, self.warn_fade + fade))

    # ---------- drawing ----------
    def _make_cockpit_bg(self):
        s = pygame.Surface((self.w, PANEL_TOP + PANEL_H + 4), pygame.SRCALPHA)
        titles = {"fock": "MOTIONAL STATE  P(n)", "phase": "PHASE SPACE",
                  "scope": "SCOPE  displacement / width", "readout": "READOUT"}
        for key, r in self.panels.items():
            pygame.draw.rect(s, PANEL_BG, r, border_radius=8)
            pygame.draw.rect(s, PANEL_EDGE, r, 2, border_radius=8)
            _text(s, titles[key], self.f_tiny, TITLE_C, (r.x + 10, r.y + 6), "topleft")
        return s

    def draw(self, surf, sy, hint=None):
        """`hint` is the controls line under the panels, named for the
        players' devices (the game builds it); by default the pads' names."""
        if self.crystal:
            self.draw_ions(surf, sy)
        else:
            self.draw_packet(surf, sy)
        surf.blit(self.bg, (0, 0))
        self.draw_fock(surf)
        self.draw_phase_space(surf)
        self.draw_scope(surf)
        self.draw_readout(surf)
        _text(surf, hint or ("STICK electrode / voltage    SELECT laser kick    BLUE  L remove / R add ion    "
                             "RED  L hold: cool / R passive cooling    START pause"),
              self.f_tiny, DIM_C, (self.w / 2, PANEL_TOP + PANEL_H + 14))

    def _surface_y(self, sy, x):
        return sy(self.table(x) / Q_COUPLING + self.height_base)

    def draw_packet(self, surf, sy):
        wp = self.wp
        psi = wp.psi
        rho = wp.density()
        peak = max(range(len(rho)), key=rho.__getitem__)
        ref = cmath.phase(psi[peak])
        pal, npal = self.palette, len(self.palette)
        base = self.height_base
        top = []
        for i, x in enumerate(wp.xs):
            hgt = min(DENSITY_MAX, rho[i] * DENSITY_SCALE)
            y0 = sy(wp.v[i] / Q_COUPLING + base)
            if hgt >= 0.6:
                ph = (cmath.phase(psi[i]) - ref) / (2 * math.pi)
                col = pal[int(ph * npal) % npal]
                pygame.draw.line(surf, col, (x, y0 - 2), (x, y0 - 2 - hgt), 3)
            top.append((x, y0 - 2 - hgt))
        pygame.draw.lines(surf, (250, 250, 255), False, top, 2)
        v = self.views[0]
        if v.trap:
            self._marker(surf, sy, v.trap.x0, v.moments.mean_x)

    def _marker(self, surf, sy, x0, mean_x, color=GOLD):
        y = self._surface_y(sy, x0)
        for yy in range(int(y) - 6, int(y) - 60, -8):
            pygame.draw.line(surf, DIM_C, (x0, yy), (x0, yy - 4), 1)
        y = self._surface_y(sy, mean_x)
        pygame.draw.polygon(surf, color, [(mean_x, y + 4), (mean_x - 5, y + 12), (mean_x + 5, y + 12)])

    def draw_ions(self, surf, sy):
        cr = self.crystal
        gauss = cr.ion_gaussians([v.moments for v in self.views])
        for i, (mean, sd) in enumerate(gauss):
            col = ION_COLORS[i % len(ION_COLORS)]
            top = []
            x = mean - 4 * sd
            while x <= mean + 4 * sd:
                rho = math.exp(-0.5 * ((x - mean) / sd) ** 2) / (math.sqrt(math.tau) * sd)
                hgt = min(DENSITY_MAX, rho * DENSITY_SCALE)
                y0 = self._surface_y(sy, x) - 2
                if hgt >= 0.6:
                    pygame.draw.line(surf, col, (x, y0), (x, y0 - hgt), 3)
                top.append((x, y0 - hgt))
                x += 3
            if len(top) > 1:
                pygame.draw.lines(surf, (250, 250, 255), False, top, 2)
            y = self._surface_y(sy, mean)
            pygame.draw.polygon(surf, col, [(mean, y + 4), (mean - 5, y + 12), (mean + 5, y + 12)])
        for x in cr.x_eq:
            y = self._surface_y(sy, x)
            for yy in range(int(y) - 6, int(y) - 50, -8):
                pygame.draw.line(surf, DIM_C, (x, yy), (x, yy - 4), 1)

    def draw_fock(self, surf):
        r = self.panels["fock"]
        views = self.views
        cols = len(views)
        levels = FOCK_LEVELS if cols == 1 else (12 if cols == 2 else 8)
        y_base, bh = r.bottom - 26, r.h - 64 - (14 if cols > 1 else 0)
        col_w = (r.w - 28) / cols
        for c, v in enumerate(views):
            x_left = r.x + 14 + c * col_w
            pops = v.pops[:levels] if v.trap else [0.0] * levels
            rest = max(0.0, 1.0 - sum(pops)) if v.trap else 0.0
            bars = pops + [rest]
            n = len(bars)
            bw = (col_w - (10 if cols > 1 else 0)) / n
            right = x_left + bw * n
            pygame.draw.line(surf, PANEL_EDGE, (x_left, y_base), (right, y_base), 1)
            for k in (0.25, 0.5, 0.75, 1.0):
                y = y_base - bh * k
                pygame.draw.line(surf, (30, 40, 72), (x_left, y), (right, y), 1)
            big = max(range(n), key=bars.__getitem__)
            full = max(0.2, bars[big])  # auto-range, never zooming in past 20 %
            main = GOLD if cols == 1 else v.color
            for k, p in enumerate(bars):
                x = x_left + k * bw + 1
                hgt = max(1, round(bh * min(1.0, p / full)))
                last = k == n - 1
                col = PINK if last else (main if k == big else (PURPLE if cols == 1 else _dim(v.color, 0.6)))
                pygame.draw.rect(surf, col, (x, y_base - hgt, max(1, bw - 2), hgt))
                step = 2 if cols <= 2 else 4
                if k % step == 0 or (last and cols == 1):
                    _text(surf, f"{levels}+" if last else str(k), self.f_tiny, DIM_C,
                          (x + (bw - 2) / 2, y_base + 10))
            if not v.trap:
                _text(surf, "NO TRAP", self.f_small, PINK, (x_left + col_w / 2, y_base - bh / 2))
                continue
            if cols == 1:
                _text(surf, f"<n> = {v.mean_n:.2f}", self.f_small, TEXT_C, (r.right - 12, r.y + 5), "topright")
                _text(surf, f"{full * 100:.0f}%", self.f_tiny, DIM_C, (x_left, y_base - bh - 2), "bottomleft")
            else:
                _text(surf, f"{v.name if cols <= 2 else v.short} {v.mean_n:.1f}", self.f_tiny, v.color,
                      (x_left, y_base - bh - 4), "bottomleft")

    def draw_phase_space(self, surf):
        r = self.panels["phase"]
        b = self.blob
        b.fill((0, 0, 0, 0))
        bw, bh = b.get_size()
        cx, cy = bw / 2, bh / 2
        live = [v for v in self.views if v.ps is not None]
        # px per vacuum standard deviation: zoom out smoothly for big states
        if live:
            reach = max(max(abs(v.ps.q), abs(v.ps.p)) + 2 * v.ps.ellipse()[0] for v in live)
            want = max(2.5, min(10.0, (min(bw, bh) / 2 - 6) / max(reach, 1e-6)))
            self.unit += (want - self.unit) * 0.15
        unit = self.unit
        pygame.draw.line(b, (40, 52, 90, 255), (0, cy), (bw, cy), 1)
        pygame.draw.line(b, (40, 52, 90, 255), (cx, 0), (cx, bh), 1)
        pygame.draw.circle(b, (90, 105, 160, 255), (cx, cy), unit, 1)  # vacuum reference
        single = len(self.views) == 1
        to_px = lambda q, p: (cx + q * unit, cy - p * unit)
        for k, v in enumerate(self.views):
            if v.ps is None:
                continue
            ps = v.ps
            blob_c = CYAN if single else v.color
            pts = list(self.trails[k]) if k < len(self.trails) else []
            for i in range(1, len(pts)):
                a = int(200 * i / len(pts))
                pygame.draw.line(b, (*(GOLD if single else v.color), a), to_px(*pts[i - 1]), to_px(*pts[i]), 1)
            major, minor, ang = ps.ellipse()
            ca, sa = math.cos(ang), math.sin(ang)
            for level, alpha in ((2.2, 40), (1.6, 70), (1.0, 120), (0.5, 190)):
                poly = []
                for j in range(36):
                    t = j * math.tau / 36
                    u, w = major * level * math.cos(t), minor * level * math.sin(t)
                    poly.append(to_px(ps.q + u * ca - w * sa, ps.p + u * sa + w * ca))
                pygame.draw.polygon(b, (*blob_c, alpha if single else alpha * 3 // 4), poly)
            end = to_px(ps.q, ps.p)
            pygame.draw.line(b, (*(GOLD if single else v.color), 220), (cx, cy), end, 2)
            pygame.draw.circle(b, (255, 255, 255, 255), end, 3)
        surf.blit(b, (r.x + 8, r.y + 26))
        _text(surf, "x", self.f_tiny, DIM_C, (r.right - 12, r.y + 26 + cy - 8))
        _text(surf, "p", self.f_tiny, DIM_C, (r.x + 8 + cx + 8, r.y + 30))
        if not single:
            x = r.x + 10
            for v in self.views:
                x = _text(surf, v.name, self.f_tiny, v.color, (x, r.bottom - 8), "bottomleft").right + 8
        if self.warn_fade > 0:
            pygame.draw.rect(surf, _mix(PANEL_EDGE, WARN_EDGE, self.warn_fade), r, 2, border_radius=8)
            img = self.f_tiny.render("ANHARMONIC", True, WARN_C)
            img.set_alpha(round(255 * self.warn_fade))
            surf.blit(img, img.get_rect(topright=(r.right - 10, r.y + 6)))

    def draw_scope(self, surf):
        r = self.panels["scope"]
        plot = pygame.Rect(r.x + 12, r.y + 28, r.w - 24, r.h - 40)
        mid = plot.centery
        pygame.draw.line(surf, (30, 40, 72), (plot.x, mid), (plot.right, mid), 1)
        samples = list(self.scope)
        n = self.scope.maxlen
        disp_scale = plot.h / 2 / 6.0  # +-6 sigma0
        width_scale = plot.h / 2.5  # width 0..2.5 sigma0, drawn upward from the bottom
        y_one = plot.bottom - width_scale  # width of the vacuum = 1
        for xx in range(plot.x, plot.right, 8):
            pygame.draw.line(surf, (45, 58, 100), (xx, y_one), (xx + 3, y_one), 1)
        single = len(self.views) == 1
        start = n - len(samples)
        for k, v in enumerate(self.views):
            d_col = GOLD if single else v.color
            w_col = CYAN if single else _dim(v.color, 0.55)
            seg_d, seg_w = [], []

            def flush():
                if len(seg_d) > 1:
                    pygame.draw.lines(surf, d_col, False, seg_d, 2)
                if len(seg_w) > 1:
                    pygame.draw.lines(surf, w_col, False, seg_w, 2 if single else 1)
                seg_d.clear()
                seg_w.clear()

            for i, smp in enumerate(samples):
                val = smp[k] if k < len(smp) else None
                if val is None:
                    flush()
                    continue
                x = plot.x + (start + i) * plot.w / n
                d, wdt = val
                seg_d.append((x, max(plot.y, min(plot.bottom, mid - d * disp_scale))))
                seg_w.append((x, max(plot.y, min(plot.bottom, plot.bottom - wdt * width_scale))))
            flush()
        if single:
            _text(surf, "<x>", self.f_tiny, GOLD, (r.right - 70, r.y + 6), "topleft")
            _text(surf, "width", self.f_tiny, CYAN, (r.right - 40, r.y + 6), "topleft")
        else:
            _text(surf, "bold <x>  thin width", self.f_tiny, DIM_C, (r.right - 12, r.y + 6), "topright")

    def draw_readout(self, surf):
        r = self.panels["readout"]
        y = r.y + 30
        if len(self.views) == 1:
            v = self.views[0]
            if v.trap and v.ps:
                alpha = v.ps.alpha
                e_q = (v.moments.energy - v.trap.v0) / v.trap.omega
                rows = [
                    ("TRAP", f"{v.trap.omega / math.tau:.2f} Hz"),
                    ("<n>", f"{v.mean_n:.2f}"),
                    ("|alpha|", f"{abs(alpha):.2f}"),
                    ("PHASE", f"{math.degrees(cmath.phase(alpha)) % 360:.0f} deg" if abs(alpha) > 0.05 else "--"),
                    ("SQUEEZE", f"{max(0.0, v.ps.squeezing_db()):.1f} dB"),
                    ("E / hw", f"{e_q:.2f}"),
                ]
            else:
                rows = [("TRAP", "none")]
            for label, val in rows:
                _text(surf, label, self.f_tiny, DIM_C, (r.x + 12, y), "topleft")
                _text(surf, val, self.f_small, TEXT_C, (r.right - 12, y - 2), "topright")
                y += 24
        else:
            _text(surf, f"{self.n_ions} IONS", self.f_small, TEXT_C, (r.right - 12, r.y + 4), "topright")
            for v in self.views:
                _text(surf, v.name, self.f_tiny, v.color, (r.x + 12, y), "topleft")
                if v.trap and v.ps:
                    _text(surf, f"{v.trap.omega / math.tau:.2f} Hz", self.f_tiny, TEXT_C,
                          (r.right - 12, y), "topright")
                    y += 16
                    sq = max(0.0, v.ps.squeezing_db())
                    _text(surf, f"n {v.mean_n:.2f}  |a| {abs(v.ps.alpha):.1f}  sq {sq:.1f}dB",
                          self.f_tiny, DIM_C, (r.x + 12, y), "topleft")
                else:
                    _text(surf, "unstable", self.f_tiny, PINK, (r.right - 12, y), "topright")
                    y += 16
                y += 20
        if self.cooling:
            _text(surf, "LASER COOLING", self.f_small, CYAN, (self.w / 2, PANEL_TOP + PANEL_H + 36))
        elif self.passive_cooling:
            _text(surf, "PASSIVE COOLING ON", self.f_small, _dim(CYAN, 0.75),
                  (self.w / 2, PANEL_TOP + PANEL_H + 36))
