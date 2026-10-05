"""Several ions in the trap: a Coulomb crystal, simulated mode by mode.

The full N-ion wave function is out of reach in pure Python on a Pi (already
2 ions on a grid are 10^5 points), so this does what ion-trap physics does
anyway: find the classical equilibrium of the crystal, diagonalize the
Hessian into normal modes (COM, stretch, ...), and give every mode its own
1D wave packet (quantum.WavePacket). Each mode feels the exact potential
along its own direction through the N-dimensional landscape (trap
anharmonicity and Coulomb walls included), only mode-mode coupling is left
out. Each ion's position distribution then follows from the modes:
x_i = x_i,eq + sum_m b_im (Q_m - Q_m,eq).

No pygame in here, so it is unit tested.
"""

from __future__ import annotations

import math

from ion_surfer.quantum import WavePacket

MIN_DIST = 6.0  # px: ions never get closer than this along a mode cut
MODE_GRID = 256
MODE_WINDOW = 800.0  # px of mode coordinate covered by each mode's grid
CUT_STRIDE = 4  # mode potentials are sampled every 4th grid point (10 px)


class Sampled:
    """Single-ion potential V(x) (rad/s) as a table, linearly interpolated."""

    def __init__(self, xs: list[float], vs: list[float]):
        self.x0 = xs[0]
        self.dx = xs[1] - xs[0]
        self.vs = vs
        self.last = len(vs) - 1

    def __call__(self, x: float) -> float:
        f = (x - self.x0) / self.dx
        if f <= 0:
            return self.vs[0] - f * 50.0  # steep walls outside the table
        if f >= self.last:
            return self.vs[-1] + (f - self.last) * 50.0
        i = int(f)
        t = f - i
        return self.vs[i] * (1 - t) + self.vs[i + 1] * t

    def d1(self, x: float, h: float = 3.0) -> float:
        return (self(x + h) - self(x - h)) / (2 * h)

    def d2(self, x: float, h: float = 12.0) -> float:
        return (self(x + h) - 2 * self(x) + self(x - h)) / (h * h)


def energy(pot: Sampled, xs: list[float], coulomb: float) -> float:
    e = sum(pot(x) for x in xs)
    for i in range(len(xs)):
        for j in range(i + 1, len(xs)):
            e += coulomb / max(MIN_DIST, abs(xs[j] - xs[i]))
    return e


def chain_energy(pot: Sampled, xs: list[float], coulomb: float) -> float:
    """energy() for ions in their order along the chain, which they can't
    leave in 1D: past MIN_DIST the Coulomb wall keeps rising (on the slope
    it had there) rather than levelling off and letting an ion through."""
    e = sum(pot(x) for x in xs)
    for i in range(len(xs)):
        for j in range(i + 1, len(xs)):
            d = xs[j] - xs[i]
            e += coulomb / d if d >= MIN_DIST else coulomb / MIN_DIST * (2 - d / MIN_DIST)
    return e


def gradient_hessian(pot: Sampled, xs: list[float], coulomb: float):
    n = len(xs)
    g = [pot.d1(x) for x in xs]
    h = [[0.0] * n for _ in range(n)]
    for i in range(n):
        h[i][i] = pot.d2(xs[i])
    for i in range(n):
        for j in range(i + 1, n):
            d = xs[j] - xs[i]
            r = max(MIN_DIST, abs(d))
            s = 1 if d > 0 else -1
            f = coulomb / (r * r)  # repulsion pushes i left, j right
            g[i] += f * s
            g[j] -= f * s
            k = 2 * coulomb / (r ** 3)
            h[i][i] += k
            h[j][j] += k
            h[i][j] -= k
            h[j][i] -= k
    return g, h


def solve(a: list[list[float]], b: list[float]) -> list[float]:
    """Gaussian elimination with partial pivoting (tiny systems only)."""
    n = len(b)
    m = [row[:] + [b[i]] for i, row in enumerate(a)]
    for c in range(n):
        p = max(range(c, n), key=lambda r: abs(m[r][c]))
        m[c], m[p] = m[p], m[c]
        if abs(m[c][c]) < 1e-12:
            raise ZeroDivisionError
        for r in range(c + 1, n):
            f = m[r][c] / m[c][c]
            for k in range(c, n + 1):
                m[r][k] -= f * m[c][k]
    out = [0.0] * n
    for r in range(n - 1, -1, -1):
        out[r] = (m[r][n] - sum(m[r][k] * out[k] for k in range(r + 1, n))) / m[r][r]
    return out


def equilibrium(pot: Sampled, guess: list[float], coulomb: float, lo: float, hi: float,
                iters: int = 40) -> list[float]:
    """Damped Newton on the crystal energy; falls back to gradient steps
    where the Hessian isn't positive (e.g. an ion sitting on a hill)."""
    xs = sorted(guess)
    for _ in range(iters):
        g, h = gradient_hessian(pot, xs, coulomb)
        try:
            step = solve(h, g)
            if sum(si * gi for si, gi in zip(step, g)) <= 0:
                raise ZeroDivisionError  # not a descent direction
        except ZeroDivisionError:
            step = [gi * 200.0 for gi in g]
        biggest = max(abs(s) for s in step)
        if biggest > 25:
            step = [s * 25 / biggest for s in step]
        e0 = energy(pot, xs, coulomb)
        t = 1.0
        while t > 1e-3:
            trial = [min(hi, max(lo, x - t * s)) for x, s in zip(xs, step)]
            if energy(pot, trial, coulomb) <= e0:
                break
            t *= 0.5
        xs = sorted(trial)
        if biggest * t < 1e-3:
            break
    return xs


def jacobi_eigen(a: list[list[float]], sweeps: int = 30):
    """Eigenvalues and (column) eigenvectors of a small symmetric matrix,
    sorted by eigenvalue."""
    n = len(a)
    m = [row[:] for row in a]
    v = [[float(i == j) for j in range(n)] for i in range(n)]
    for _ in range(sweeps):
        off = sum(m[i][j] ** 2 for i in range(n) for j in range(n) if i != j)
        if off < 1e-18:
            break
        for p in range(n):
            for q in range(p + 1, n):
                if abs(m[p][q]) < 1e-15:
                    continue
                theta = (m[q][q] - m[p][p]) / (2 * m[p][q])
                t = (1 if theta >= 0 else -1) / (abs(theta) + math.sqrt(theta * theta + 1))
                c = 1 / math.sqrt(t * t + 1)
                s = t * c
                for k in range(n):
                    mkp, mkq = m[k][p], m[k][q]
                    m[k][p], m[k][q] = c * mkp - s * mkq, s * mkp + c * mkq
                for k in range(n):
                    mpk, mqk = m[p][k], m[q][k]
                    m[p][k], m[q][k] = c * mpk - s * mqk, s * mpk + c * mqk
                for k in range(n):
                    vkp, vkq = v[k][p], v[k][q]
                    v[k][p], v[k][q] = c * vkp - s * vkq, s * vkp + c * vkq
    order = sorted(range(n), key=lambda i: m[i][i])
    return [m[i][i] for i in order], [[v[k][i] for k in range(n)] for i in order]


def mode_name(index: int, vec: list[float]) -> str:
    """COM / STRETCH / ... for collective modes, ION k when one ion dominates."""
    big = max(range(len(vec)), key=lambda i: abs(vec[i]))
    if abs(vec[big]) > 0.95:
        return f"ION {big + 1}"
    if all(c > 0.05 for c in vec) or all(c < -0.05 for c in vec):
        return "COM"
    names = ["COM", "STRETCH", "EGYPTIAN", "MODE 4"]
    return names[index] if index < len(names) else f"MODE {index + 1}"


class Crystal:
    """N >= 2 ions: equilibrium + normal modes + one WavePacket per mode."""

    def __init__(self, pot: Sampled, positions: list[float], hbar_m: float, coulomb: float,
                 lo: float, hi: float):
        self.d, self.c, self.lo, self.hi = hbar_m, coulomb, lo, hi
        self.pot = pot
        self.x_eq = equilibrium(pot, positions, coulomb, lo, hi)
        self._modes_from_hessian(None)
        self.packets = []
        for m in range(self.n):
            q0 = self.q_eq[m]
            wp = WavePacket(MODE_GRID, MODE_WINDOW, hbar_m, x_start=q0 - MODE_WINDOW / 2)
            self.packets.append(wp)
        self._set_cuts()
        self.cool_to_ground()

    @property
    def n(self) -> int:
        return len(self.x_eq)

    def _modes_from_hessian(self, previous):
        _, h = gradient_hessian(self.pot, self.x_eq, self.c)
        lams, vecs = jacobi_eigen(h)
        if previous is not None:
            # keep each mode's identity and sign continuous between frames
            matched = []
            free = list(range(len(vecs)))
            for old in previous:
                best = max(free, key=lambda k: abs(sum(a * b for a, b in zip(old, vecs[k]))))
                free.remove(best)
                v = vecs[best]
                if sum(a * b for a, b in zip(old, v)) < 0:
                    v = [-c for c in v]
                matched.append((lams[best], v))
            lams = [m[0] for m in matched]
            vecs = [m[1] for m in matched]
        self.lams, self.vecs = lams, vecs
        self.q_eq = [sum(b * x for b, x in zip(v, self.x_eq)) for v in vecs]
        self.stable = all(lam > 1e-7 for lam in lams)

    def _cut(self, m: int, q: float) -> float:
        v = self.vecs[m]
        dq = q - self.q_eq[m]
        return chain_energy(self.pot, [x + b * dq for x, b in zip(self.x_eq, v)], self.c)

    def _set_cuts(self):
        for m, wp in enumerate(self.packets):
            # follow a drifting equilibrium with the grid window; a jump
            # bigger than that (modes swapped or the crystal rearranged)
            # can't be tracked, so that mode restarts in its ground state
            off = self.q_eq[m] - (wp.x_start + MODE_WINDOW / 2)
            lost = abs(off) > MODE_WINDOW / 3
            if lost:
                wp = self.packets[m] = WavePacket(MODE_GRID, MODE_WINDOW, self.d,
                                                  x_start=self.q_eq[m] - MODE_WINDOW / 2)
            elif abs(off) > MODE_WINDOW / 8:
                wp.shift_cells(round(off / wp.dx))
                wp.normalize()  # anything pushed off the window edge is gone
            # the cut is smooth: evaluate it every CUT_STRIDE-th grid point and
            # fill in with cubic interpolation (exact for the harmonic part)
            e0 = self._cut(m, self.q_eq[m])
            xs = wp.xs
            nodes = [self._cut(m, xs[0] + (j - 1) * CUT_STRIDE * wp.dx) - e0
                     for j in range(len(xs) // CUT_STRIDE + 4)]
            out = []
            for i in range(len(xs)):
                j, t = divmod(i, CUT_STRIDE)
                t /= CUT_STRIDE
                p0, p1, p2, p3 = nodes[j:j + 4]
                # 4-point Lagrange through nodes at t = -1, 0, 1, 2
                out.append(-t * (t - 1) * (t - 2) / 6 * p0 + (t + 1) * (t - 1) * (t - 2) / 2 * p1
                           - (t + 1) * t * (t - 2) / 2 * p2 + (t + 1) * t * (t - 1) / 6 * p3)
            wp.set_potential(out)
            if lost:
                self._ground(m)

    def ion_means(self, means: list[float] | None = None) -> list[float]:
        """Every ion's mean position, from the modes' packets (or their
        given mean coordinates)."""
        if means is None:
            means = [wp.mean_x() for wp in self.packets]
        dq = [q - qe for q, qe in zip(means, self.q_eq)]
        return [x + sum(v[i] * d for v, d in zip(self.vecs, dq)) for i, x in enumerate(self.x_eq)]

    def update_potential(self, pot: Sampled) -> None:
        # Changing the potential moves the equilibrium and turns the modes,
        # but not the ions. So the new equilibrium is searched from where
        # the ions are, and every packet is moved to where they are in the
        # new mode coordinates. Without that, a mode's coordinate b.x, which
        # is measured from the screen's edge, shifted by hundreds of px
        # whenever b turned slightly, and the packets were left there.
        means = [wp.mean_x() for wp in self.packets]
        ions = self.ion_means(means)
        self.pot = pot
        self.x_eq = equilibrium(pot, ions, self.c, self.lo, self.hi, iters=12)
        self._modes_from_hessian(self.vecs)
        gone = []
        for m, (v, wp) in enumerate(zip(self.vecs, self.packets)):
            if wp.translate(sum(b * x for b, x in zip(v, ions)) - means[m]) < 0.5:
                gone.append(m)
        self._set_cuts()
        for m in gone:
            self._ground(m)

    def cool_to_ground(self) -> None:
        for m in range(self.n):
            self._ground(m)

    def _ground(self, m: int) -> None:
        wp = self.packets[m]
        trap = wp.fit_trap(self.q_eq[m])
        wp.set_gaussian(self.q_eq[m], trap.sigma0 if trap else 20.0)

    def step(self, dt: complex, damp: bool = False) -> None:
        for wp in self.packets:
            wp.step(dt)
            if damp:
                wp.normalize()

    def kick_ion(self, ion: int, k0: float) -> None:
        """Addressed laser kick on one ion = a kick of b_im * k0 on every mode."""
        for m, wp in enumerate(self.packets):
            wp.kick(self.vecs[m][ion] * k0)

    def ion_gaussians(self, moments) -> list[tuple[float, float]]:
        """(mean, sd) of every ion's position, from the per-mode moments."""
        out = []
        for i in range(self.n):
            mean = self.x_eq[i]
            var = 0.0
            for m, mo in enumerate(moments):
                b = self.vecs[m][i]
                mean += b * (mo.mean_x - self.q_eq[m])
                var += b * b * mo.var_x
            out.append((mean, math.sqrt(max(var, 1e-6))))
        return out
