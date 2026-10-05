"""Wave-packet simulation for the SANDBOX mode.

Solves the 1D Schrödinger equation

    i dpsi/dt = -(D/2) d^2psi/dx^2 + V(x) psi        (D = hbar/m, V in rad/s)

on a fixed grid with Dirichlet walls. Time steps use the (2,2) Padé
approximant of exp(-i H dt), Crank-Nicolson's 4th-order sibling: unitary and
unconditionally stable, so a few large steps per frame are fine. Space uses
the 4th-order Numerov form of the Laplacian, which costs no more than the
plain 3-point one. Energies are measured from a reference that follows the
packet (set_reference), because the steps only get the phases right where
(E - E_ref) dt is small: with plain Crank-Nicolson and energies measured from
the screen's lowest point, a packet in a raised well oscillated several times
too slowly. Pure Python
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

# exp(-z) ~ (1 - z/a1)(1 - z/a2) / ((1 + z/a1)(1 + z/a2)), z = i H dt: the
# (2,2) Padé approximant, error z^5/720 against Crank-Nicolson's z^3/12.
# Paired as (1 - z/a1)/(1 + z/a2) and (1 - z/a2)/(1 + z/a1), each factor is
# unitary on its own (a2 = conj(a1)), so a step is two Crank-Nicolson-like
# tridiagonal solves.
PADE = (3 + math.sqrt(3) * 1j, 3 - math.sqrt(3) * 1j)


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

    def area(self) -> float:
        """Uncertainty area in units of the vacuum's. Exactly 1 for every pure
        Gaussian state (coherent, squeezed), and the state here is always
        pure, so anything above 1 is shape the ellipse can't show: what an
        anharmonic potential does to a packet."""
        return math.sqrt(max(0.0, self.var_q * self.var_p - self.cov * self.cov))

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
        self.e_ref = 0.0  # energy the time steps are measured from (rad/s)
        self._carry = 0.0  # translate()'s remainder below a whole cell (px)
        self._coeffs: dict[complex, tuple] = {}

    # ---------- setup ----------
    def set_potential(self, v: list[float]) -> None:
        self.v = list(v)
        self._coeffs.clear()

    def set_reference(self, energy: float, tol: float = 5.0) -> None:
        """Measure energies from `energy` (best: the packet's own <H>). Only
        a global phase for the exact evolution, but the time steps are only
        phase-accurate for (E - E_ref) dt << 1 (see PADE). The coefficients
        are rebuilt only once it has moved by more than tol."""
        if abs(energy - self.e_ref) > tol:
            self.e_ref = energy
            self._coeffs.clear()

    def set_gaussian(self, x0: float, sigma: float, k0: float = 0.0) -> None:
        self.psi = [
            cmath.exp(complex(-((x - x0) ** 2) / (4 * sigma * sigma), k0 * (x - x0)))
            for x in self.xs
        ]
        self._carry = 0.0
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

    def translate(self, dist: float) -> float:
        """Move the packet itself by dist px (the grid stays). Whole cells
        only, so nothing is smeared; the remainder carries over to the next
        call. Returns the share of the packet still on the grid."""
        self._carry += dist
        cells = round(self._carry / self.dx)
        if cells == 0:
            return 1.0
        self._carry -= cells * self.dx
        n = self.n
        if abs(cells) >= n:
            self.psi = [0j] * n
        elif cells > 0:
            self.psi = [0j] * cells + self.psi[:-cells]
        else:
            self.psi = self.psi[-cells:] + [0j] * -cells
        kept = sum(abs(z) ** 2 for z in self.psi) * self.dx
        self.normalize()
        return kept

    def kick(self, k0: float) -> None:
        """Momentum kick (what a short laser push does): psi *= exp(i k0 x)."""
        self.psi = [z * cmath.exp(1j * k0 * x) for z, x in zip(self.psi, self.xs)]

    # ---------- time evolution ----------
    def _prepare(self, ca: complex, cb: complex) -> tuple:
        # A psi' = B psi with A = 1 + ca H, B = 1 - cb H, where the kinetic
        # term K = -(D/2) M^-1 L is Numerov's: L the 3-point Laplacian,
        # M = (1, 10, 1)/12. M and L commute, so H stays Hermitian, and
        # multiplying by M keeps both sides tridiagonal: M A = M + ca (-(D/2) L
        # + M V), whose off-diagonal entries carry the potential of their
        # column. 4th order in dx, where the 3-point Laplacian alone left a
        # fast packet ~5 % too slow. Thomas-algorithm coefficients only depend
        # on V and dt, so they're cached until the potential (or the energy
        # reference) changes.
        t = self.d / (self.dx * self.dx)
        us = [v - self.e_ref for v in self.v]
        off_a = [1 / 12 + ca * (u / 12 - t / 2) for u in us]
        off_b = [1 / 12 - cb * (u / 12 - t / 2) for u in us]
        diag_b = [5 / 6 - cb * (t + 5 / 6 * u) for u in us]
        sub = [0j] + off_a[:-1]
        cp, inv = [], []
        prev = 0j
        for i, u in enumerate(us):
            im = 1 / (5 / 6 + ca * (t + 5 / 6 * u) - sub[i] * prev)
            prev = (off_a[i + 1] if i + 1 < len(us) else 0j) * im
            cp.append(prev)
            inv.append(im)
        return sub, off_b, diag_b, cp, inv

    def step(self, dt: complex) -> None:
        """One time step (see PADE). A complex dt = h (1 - i gamma) also damps
        the higher energies (used for cooling); renormalize afterwards then."""
        stages = self._coeffs.get(dt)
        if stages is None:
            z = 1j * dt
            a1, a2 = PADE
            stages = self._coeffs[dt] = (self._prepare(z / a2, z / a1),
                                         self._prepare(z / a1, z / a2))
        for coeffs in stages:
            self._solve(coeffs)

    def _solve(self, coeffs: tuple) -> None:
        sub, off_b, diag_b, cp, inv = coeffs
        psi = self.psi
        # B psi: off-diagonal terms by column, with a trailing zero that also
        # serves as w[-1] for the first row
        w = [b * z for b, z in zip(off_b, psi)]
        w.append(0j)
        rhs = [d * z + w[i - 1] + w[i + 1] for i, (d, z) in enumerate(zip(diag_b, psi))]
        # forward sweep, then back substitution
        out = []
        prev = 0j
        for r, s, im in zip(rhs, sub, inv):
            prev = (r - s * prev) * im
            out.append(prev)
        for i in range(self.n - 2, -1, -1):
            out[i] -= cp[i] * out[i + 1]
        self.psi = out

    # ---------- observables ----------
    def mean_x(self) -> float:
        s0 = sx = 0.0
        for z, x in zip(self.psi, self.xs):
            rho = z.real * z.real + z.imag * z.imag
            s0 += rho
            sx += rho * x
        return sx / s0 if s0 > 0 else self.x_start + (self.n + 1) * self.dx / 2

    def density(self) -> list[float]:
        return [z.real * z.real + z.imag * z.imag for z in self.psi]

    def moments(self) -> Moments:
        psi, xs, dx = self.psi, self.xs, self.dx
        # A finite difference sees sin(k dx)/dx instead of k, which made a
        # fast packet look squeezed. So take the derivatives of psi with its
        # mean phase gradient k1 divided out, where they are accurate, and
        # add k1 back afterwards.
        acc = sum(a.conjugate() * b for a, b in zip(psi, psi[1:]))
        k1 = cmath.phase(acc) / dx if acc else 0.0
        turn = cmath.exp(-1j * k1 * dx)
        z = cmath.exp(-1j * k1 * xs[0])
        phi = [0j]  # zero-padded at both ends: the walls
        for a in psi:
            phi.append(a * z)
            z *= turn
        phi.append(0j)
        s0 = sx = sxx = sk = skk = sxk = sv = 0.0
        inv2dx = 1 / (2 * dx)
        for i, (x, v) in enumerate(zip(xs, self.v)):
            z = phi[i + 1]
            rho = z.real * z.real + z.imag * z.imag
            dz = (phi[i + 2] - phi[i]) * inv2dx
            cur = z.real * dz.imag - z.imag * dz.real  # Im(conj(z) dz) = local rho*k
            s0 += rho
            sx += rho * x
            sxx += rho * x * x
            sk += cur
            skk += dz.real * dz.real + dz.imag * dz.imag
            sxk += x * cur
            sv += rho * v
        s0 = max(s0, 1e-12)
        mx, mk = sx / s0, sk / s0
        return Moments(
            norm=s0 * dx,
            mean_x=mx,
            var_x=max(0.0, sxx / s0 - mx * mx),
            mean_k=k1 + mk,
            var_k=max(0.0, skk / s0 - mk * mk),
            cov_xk=sxk / s0 - mx * mk,
            energy=0.5 * self.d * (skk / s0 + 2 * k1 * mk + k1 * k1) + sv / s0,
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
