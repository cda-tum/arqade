"""Wave-packet simulation for the SANDBOX mode.

Solves the 1D Schrödinger equation

    i dpsi/dt = -(D/2) d^2psi/dx^2 + V(x) psi        (D = hbar/m, V in rad/s)

on a fixed grid with Dirichlet walls, using Crank-Nicolson (unitary and
unconditionally stable, so a few large steps per frame are fine). Pure Python
on purpose: Batocera doesn't ship numpy. Everything the cockpit shows is
derived here, relative to the harmonic approximation of the trap around the
packet: Fock populations (motional excitations), phase-space moments
(displacement, squeezing, phase) and the energy.

No pygame in this module, so all of it is unit tested.
"""

from __future__ import annotations

import cmath
import math
from dataclasses import dataclass


@dataclass
class Trap:
    """Harmonic approximation of the potential around a local minimum."""

    x0: float  # position of the minimum (px)
    omega: float  # trap frequency (rad/s)
    sigma0: float  # ground-state width sqrt(D / (2 omega)) (px)
    v0: float  # potential at the minimum (rad/s)


@dataclass
class Moments:
    norm: float
    mean_x: float
    var_x: float
    mean_k: float  # <p>/hbar (1/px)
    var_k: float
    cov_xk: float  # symmetrized <(x k + k x)/2> - <x><k>
    energy: float  # <H> (rad/s)


@dataclass
class PhaseSpace:
    """Moments in oscillator units of a Trap: vacuum has var_q = var_p = 1."""

    q: float
    p: float
    var_q: float
    var_p: float
    cov: float

    @property
    def alpha(self) -> complex:
        """Coherent amplitude: x = sigma0 (a + a^dagger)."""
        return complex(self.q, self.p) / 2

    def ellipse(self) -> tuple[float, float, float]:
        """(major sd, minor sd, angle of the major axis in rad)."""
        tr = self.var_q + self.var_p
        det = self.var_q * self.var_p - self.cov * self.cov
        disc = math.sqrt(max(0.0, tr * tr / 4 - det))
        big, small = tr / 2 + disc, max(1e-9, tr / 2 - disc)
        angle = 0.5 * math.atan2(2 * self.cov, self.var_q - self.var_p)
        return math.sqrt(big), math.sqrt(small), angle

    def squeezing_db(self) -> float:
        """How far the narrowest quadrature is below vacuum noise (0 dB = none)."""
        _, small, _ = self.ellipse()
        return -10 * math.log10(small * small)


class WavePacket:
    def __init__(self, n: int, width: float, hbar_m: float, x_start: float = 0.0):
        self.n = n
        self.dx = width / (n + 1)
        self.x_start = x_start
        self.xs = [x_start + (i + 1) * self.dx for i in range(n)]  # walls at the ends
        self.d = hbar_m
        self.v = [0.0] * n
        self.psi = [0j] * n
        self._coeffs: dict[complex, tuple] = {}

    # ---------- setup ----------
    def set_potential(self, v: list[float]) -> None:
        self.v = list(v)
        self._coeffs.clear()

    def set_gaussian(self, x0: float, sigma: float, k0: float = 0.0) -> None:
        self.psi = [
            cmath.exp(complex(-((x - x0) ** 2) / (4 * sigma * sigma), k0 * (x - x0)))
            for x in self.xs
        ]
        self.normalize()

    def normalize(self) -> None:
        norm = math.sqrt(sum(abs(z) ** 2 for z in self.psi) * self.dx)
        if norm > 0:
            inv = 1 / norm
            self.psi = [z * inv for z in self.psi]

    def shift_cells(self, cells: int) -> None:
        """Move the grid window by whole cells (content stays put in x), so a
        packet that drifts far can be followed without interpolation."""
        if cells == 0:
            return
        n = self.n
        psi = self.psi
        if cells > 0:
            self.psi = psi[cells:] + [0j] * min(n, cells)
        else:
            self.psi = [0j] * min(n, -cells) + psi[:cells]
        self.psi = self.psi[:n]
        self.x_start += cells * self.dx
        self.xs = [self.x_start + (i + 1) * self.dx for i in range(n)]
        self._coeffs.clear()

    def kick(self, k0: float) -> None:
        """Momentum kick (what a short laser push does): psi *= exp(i k0 x)."""
        self.psi = [z * cmath.exp(1j * k0 * x) for z, x in zip(self.psi, self.xs)]

    # ---------- time evolution ----------
    def _prepare(self, dt: complex) -> tuple:
        # A psi' = B psi with A = 1 + i dt/2 H, B = 1 - i dt/2 H and the
        # 3-point Laplacian. Thomas-algorithm coefficients only depend on
        # V and dt, so they're cached until the potential changes.
        t = self.d / (self.dx * self.dx)
        h = 0.5j * dt
        off_a = -h * t / 2
        off_b = h * t / 2
        diag_b = [1 - h * (t + v) for v in self.v]
        cp, inv = [], []
        prev = 0j
        for v in self.v:
            m = 1 + h * (t + v) - off_a * prev
            im = 1 / m
            prev = off_a * im
            cp.append(prev)
            inv.append(im)
        return off_a, off_b, diag_b, cp, inv

    def step(self, dt: complex) -> None:
        """One Crank-Nicolson step. A complex dt = h (1 - i gamma) also damps
        the higher energies (used for cooling); renormalize afterwards then."""
        coeffs = self._coeffs.get(dt)
        if coeffs is None:
            coeffs = self._coeffs[dt] = self._prepare(dt)
        off_a, off_b, diag_b, cp, inv = coeffs
        psi = self.psi
        n = self.n
        # right-hand side + forward sweep in one pass
        dp = [0j] * n
        prev_psi, prev_dp = 0j, 0j
        for i in range(n):
            nxt = psi[i + 1] if i + 1 < n else 0j
            rhs = diag_b[i] * psi[i] + off_b * (prev_psi + nxt)
            prev_dp = (rhs - off_a * prev_dp) * inv[i]
            dp[i] = prev_dp
            prev_psi = psi[i]
        # back substitution
        out = dp
        for i in range(n - 2, -1, -1):
            out[i] = dp[i] - cp[i] * out[i + 1]
        self.psi = out

    # ---------- observables ----------
    def density(self) -> list[float]:
        return [z.real * z.real + z.imag * z.imag for z in self.psi]

    def moments(self) -> Moments:
        psi, xs, dx, n = self.psi, self.xs, self.dx, self.n
        s0 = sx = sxx = sk = skk = sxk = sv = 0.0
        inv2dx = 1 / (2 * dx)
        for i in range(n):
            z = psi[i]
            rho = z.real * z.real + z.imag * z.imag
            x = xs[i]
            dz = ((psi[i + 1] if i + 1 < n else 0j) - (psi[i - 1] if i > 0 else 0j)) * inv2dx
            cur = z.real * dz.imag - z.imag * dz.real  # Im(conj(z) dz) = local rho*k
            s0 += rho
            sx += rho * x
            sxx += rho * x * x
            sk += cur
            skk += dz.real * dz.real + dz.imag * dz.imag
            sxk += x * cur
            sv += rho * self.v[i]
        s0 = max(s0, 1e-12)
        mx, mk = sx / s0, sk / s0
        return Moments(
            norm=s0 * dx,
            mean_x=mx,
            var_x=max(0.0, sxx / s0 - mx * mx),
            mean_k=mk,
            var_k=max(0.0, skk / s0 - mk * mk),
            cov_xk=sxk / s0 - mx * mk,
            energy=0.5 * self.d * skk / s0 + sv / s0,
        )

    def fit_trap(self, near_x: float, span: float = 12.0) -> Trap | None:
        """Harmonic approximation around the local minimum reached by walking
        downhill from near_x. None if the potential isn't curved upwards."""
        v, dx, n = self.v, self.dx, self.n
        i = min(n - 1, max(0, round((near_x - self.x_start) / dx) - 1))
        while True:
            left = v[i - 1] if i > 0 else math.inf
            right = v[i + 1] if i + 1 < n else math.inf
            if left < v[i] and left <= right:
                i -= 1
            elif right < v[i]:
                i += 1
            else:
                break
        k = max(1, min(round(span / dx), i, n - 1 - i))
        if k < 1 or i - k < 0 or i + k >= n:
            return None
        a, b, c = v[i - k], v[i], v[i + k]
        curv = (a - 2 * b + c) / (k * dx) ** 2
        if curv <= 1e-9:
            return None
        # parabola vertex for a sub-grid minimum position
        shift = 0.5 * (a - c) / (a - 2 * b + c) * k * dx
        omega = math.sqrt(self.d * curv)
        return Trap(
            x0=self.xs[i] + shift,
            omega=omega,
            sigma0=math.sqrt(self.d / (2 * omega)),
            v0=b - 0.125 * (a - c) ** 2 / (a - 2 * b + c) if a - 2 * b + c else b,
        )

    def phase_space(self, m: Moments, trap: Trap) -> PhaseSpace:
        s0 = trap.sigma0
        # q = (x - x0)/sigma0, p = k * 2 sigma0  ->  vacuum: var_q = var_p = 1
        return PhaseSpace(
            q=(m.mean_x - trap.x0) / s0,
            p=m.mean_k * 2 * s0,
            var_q=m.var_x / (s0 * s0),
            var_p=m.var_k * 4 * s0 * s0,
            cov=2 * m.cov_xk,
        )

    def fock_populations(self, trap: Trap, n_max: int) -> list[float]:
        """|<n|psi>|^2 for n = 0..n_max-1 in the trap's harmonic basis."""
        length = math.sqrt(2) * trap.sigma0  # sqrt(hbar / (m omega))
        reach = math.sqrt(2 * n_max + 1) + 5  # Hermite functions die off past this
        norm0 = 1 / (math.pi ** 0.25 * math.sqrt(length))
        amps = [0j] * n_max
        dx = self.dx
        sq = [math.sqrt(k) for k in range(n_max + 1)]
        for x, z in zip(self.xs, self.psi):
            xi = (x - trap.x0) / length
            if abs(xi) > reach:
                continue
            prev, cur = 0.0, norm0 * math.exp(-0.5 * xi * xi)
            for k in range(n_max):
                amps[k] += cur * z
                prev, cur = cur, (math.sqrt(2) * xi * cur - sq[k] * prev) / sq[k + 1]
        return [(a.real * a.real + a.imag * a.imag) * dx * dx for a in amps]
