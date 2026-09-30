"""Exact 1-3 qubit simulation: density matrices, gates, T1/T2 noise, fidelity.

Pure Python (no numpy, no pygame) so it runs anywhere and is unit tested
headless. At most 8x8 complex matrices, and noise is applied lazily (only
when an item is touched or its bars refresh), so the cost is negligible.

Conventions: qubit 0 is the most significant bit of a basis index and is the
leftmost bowl on a tray. Bloch vector r = (<X>, <Y>, <Z>), so |0> is +z
(north pole) and |+> is +x.
"""

from __future__ import annotations

import cmath
import math
from dataclasses import dataclass, field
from itertools import permutations, product

S2 = 1 / math.sqrt(2)

Matrix = list[list[complex]]
Vector = list[complex]

GATES: dict[str, tuple[tuple[complex, complex], tuple[complex, complex]]] = {
    "I": ((1, 0), (0, 1)),
    "X": ((0, 1), (1, 0)),
    "Y": ((0, -1j), (1j, 0)),
    "Z": ((1, 0), (0, -1)),
    "H": ((S2, S2), (S2, -S2)),
    "S": ((1, 0), (0, 1j)),
    "T": ((1, 0), (0, cmath.exp(1j * math.pi / 4))),
}

# Rotation axis and angle of each single-qubit gate on the Bloch sphere (up to
# global phase), used to animate the arrow swinging the way the gate really
# rotates it: X = pi about x, Z = pi about z, H = pi about (x+z)/sqrt2.
GATE_ROTATIONS: dict[str, tuple[tuple[float, float, float], float]] = {
    "X": ((1.0, 0.0, 0.0), math.pi),
    "Y": ((0.0, 1.0, 0.0), math.pi),
    "Z": ((0.0, 0.0, 1.0), math.pi),
    "H": ((S2, 0.0, S2), math.pi),
    "S": ((0.0, 0.0, 1.0), math.pi / 2),
    "T": ((0.0, 0.0, 1.0), math.pi / 4),
}

MAX_QUBITS = 3


def _bit(index: int, q: int, n: int) -> int:
    return (index >> (n - 1 - q)) & 1


# --- low-level linear algebra ---------------------------------------------


def zeros(d: int) -> Matrix:
    return [[0j] * d for _ in range(d)]


def outer(psi: Vector) -> Matrix:
    return [[a * b.conjugate() for b in psi] for a in psi]


def kron_vec(a: Vector, b: Vector) -> Vector:
    return [x * y for x in a for y in b]


def kron_mat(a: Matrix, b: Matrix) -> Matrix:
    da, db = len(a), len(b)
    return [
        [a[i // db][j // db] * b[i % db][j % db] for j in range(da * db)]
        for i in range(da * db)
    ]


def trace(m: Matrix) -> complex:
    return sum(m[i][i] for i in range(len(m)))


def _left_1q(m: Matrix, u, q: int, n: int) -> Matrix:
    """(U acting on qubit q) @ m."""
    d = len(m)
    out = [row[:] for row in m]
    step = 1 << (n - 1 - q)
    for i0 in range(d):
        if i0 & step:
            continue
        i1 = i0 | step
        r0, r1 = m[i0], m[i1]
        o0, o1 = out[i0], out[i1]
        for j in range(d):
            a, b = r0[j], r1[j]
            o0[j] = u[0][0] * a + u[0][1] * b
            o1[j] = u[1][0] * a + u[1][1] * b
    return out


def _right_1q_dag(m: Matrix, u, q: int, n: int) -> Matrix:
    """m @ (U acting on qubit q)^dagger."""
    d = len(m)
    out = [row[:] for row in m]
    step = 1 << (n - 1 - q)
    c00, c01 = complex(u[0][0]).conjugate(), complex(u[0][1]).conjugate()
    c10, c11 = complex(u[1][0]).conjugate(), complex(u[1][1]).conjugate()
    for i in range(d):
        row, orow = m[i], out[i]
        for j0 in range(d):
            if j0 & step:
                continue
            j1 = j0 | step
            a, b = row[j0], row[j1]
            orow[j0] = a * c00 + b * c01
            orow[j1] = a * c10 + b * c11
    return out


def conjugate_1q(m: Matrix, u, q: int, n: int) -> Matrix:
    """U_q m U_q^dagger."""
    return _right_1q_dag(_left_1q(m, u, q, n), u, q, n)


def apply_1q_vec(psi: Vector, u, q: int, n: int) -> Vector:
    out = psi[:]
    step = 1 << (n - 1 - q)
    for i0 in range(len(psi)):
        if i0 & step:
            continue
        i1 = i0 | step
        a, b = psi[i0], psi[i1]
        out[i0] = u[0][0] * a + u[0][1] * b
        out[i1] = u[1][0] * a + u[1][1] * b
    return out


def _cnot_perm(c: int, t: int, n: int) -> list[int]:
    perm = []
    for i in range(1 << n):
        perm.append(i ^ (1 << (n - 1 - t)) if _bit(i, c, n) else i)
    return perm


def _qubit_perm_index(order: tuple[int, ...], n: int) -> list[int]:
    """Basis index map for reordering qubits: new qubit k = old qubit order[k]."""
    out = []
    for i in range(1 << n):
        j = 0
        for k, old in enumerate(order):
            if _bit(i, k, n):
                j |= 1 << (n - 1 - old)
        out.append(j)
    return out


def permute_vec(psi: Vector, order: tuple[int, ...]) -> Vector:
    n = len(order)
    idx = _qubit_perm_index(order, n)
    return [psi[idx[i]] for i in range(len(psi))]


def permute_mat(m: Matrix, order: tuple[int, ...]) -> Matrix:
    n = len(order)
    idx = _qubit_perm_index(order, n)
    return [[m[idx[i]][idx[j]] for j in range(len(m))] for i in range(len(m))]


def expectation(psi: Vector, m: Matrix) -> float:
    """<psi| m |psi> (real part; m is Hermitian)."""
    total = 0j
    for i, a in enumerate(psi):
        if a == 0:
            continue
        row = m[i]
        acc = 0j
        for j, b in enumerate(psi):
            if b != 0:
                acc += row[j] * b
        total += a.conjugate() * acc
    return total.real


def overlap2(a: Vector, b: Vector) -> float:
    """|<a|b>|^2."""
    return abs(sum(x.conjugate() * y for x, y in zip(a, b))) ** 2


def reduced_1q(m: Matrix, q: int, n: int) -> tuple[tuple[complex, complex], tuple[complex, complex]]:
    """Partial trace down to qubit q."""
    r = [[0j, 0j], [0j, 0j]]
    step = 1 << (n - 1 - q)
    for i in range(len(m)):
        if i & step:
            continue
        i1 = i | step
        r[0][0] += m[i][i]
        r[1][1] += m[i1][i1]
        r[0][1] += m[i][i1]
        r[1][0] += m[i1][i]
    return (r[0][0], r[0][1]), (r[1][0], r[1][1])


def bloch_of(r) -> tuple[float, float, float]:
    """Bloch vector of a 2x2 density matrix: rho = (I + xX + yY + zZ)/2."""
    x = 2 * r[0][1].real
    y = -2 * r[0][1].imag
    z = (r[0][0] - r[1][1]).real
    return x, y, z


# --- noise ------------------------------------------------------------------


@dataclass(frozen=True)
class Noise:
    """Per-level coherence. T1 = relaxation to |0>, T2 = total coherence
    time (T2 <= 2*T1). math.inf switches a process off."""

    t1: float = math.inf
    t2: float = math.inf
    depolarizing: float = 0.0  # error probability per gate

    def __post_init__(self) -> None:
        if self.t2 > 2 * self.t1:
            raise ValueError("T2 must be <= 2*T1")

    @property
    def dephasing_rate(self) -> float:
        """1/T_phi = 1/T2 - 1/(2*T1)."""
        rate = (0.0 if math.isinf(self.t2) else 1 / self.t2) - (
            0.0 if math.isinf(self.t1) else 1 / (2 * self.t1)
        )
        return max(0.0, rate)

    @property
    def is_noiseless(self) -> bool:
        return math.isinf(self.t1) and self.dephasing_rate == 0.0


NOISELESS = Noise()


def amplitude_damp(m: Matrix, q: int, n: int, gamma: float) -> Matrix:
    if gamma <= 0:
        return m
    k0 = ((1, 0), (0, math.sqrt(1 - gamma)))
    k1 = ((0, math.sqrt(gamma)), (0, 0))
    a = conjugate_1q(m, k0, q, n)
    b = conjugate_1q(m, k1, q, n)
    return [[x + y for x, y in zip(ra, rb)] for ra, rb in zip(a, b)]


def dephase(m: Matrix, q: int, n: int, factor: float) -> Matrix:
    """Multiply every coherence between |..0..> and |..1..> on qubit q by factor."""
    if factor >= 1:
        return m
    step = 1 << (n - 1 - q)
    return [
        [v * factor if (i ^ j) & step else v for j, v in enumerate(row)]
        for i, row in enumerate(m)
    ]


def depolarize(m: Matrix, q: int, n: int, p: float) -> Matrix:
    """rho -> (1 - 3p/4) rho + p/4 (X rho X + Y rho Y + Z rho Z)."""
    if p <= 0:
        return m
    out = [[v * (1 - 0.75 * p) for v in row] for row in m]
    for g in ("X", "Y", "Z"):
        c = conjugate_1q(m, GATES[g], q, n)
        for i in range(len(m)):
            for j in range(len(m)):
                out[i][j] += 0.25 * p * c[i][j]
    return out


# --- named states -------------------------------------------------------------

ONE_QUBIT_STATES: dict[str, Vector] = {
    "0": [1 + 0j, 0j],
    "1": [0j, 1 + 0j],
    "+": [S2 + 0j, S2 + 0j],
    "-": [S2 + 0j, -S2 + 0j],
}

NAMED_STATES: dict[str, Vector] = {
    **ONE_QUBIT_STATES,
    "Phi+": [S2 + 0j, 0j, 0j, S2 + 0j],
    "Phi-": [S2 + 0j, 0j, 0j, -S2 + 0j],
    "Psi+": [0j, S2 + 0j, S2 + 0j, 0j],
    "Psi-": [0j, S2 + 0j, -S2 + 0j, 0j],
    "GHZ": [S2 + 0j] + [0j] * 6 + [S2 + 0j],
}


def n_qubits_of(vec: Vector) -> int:
    return len(vec).bit_length() - 1


def _build_label_candidates() -> dict[int, list[tuple[tuple[str, ...], Vector]]]:
    """Every state a label can name, as (tokens, vector): products of the four
    single-qubit states, Bell pairs (optionally with a separate bowl beside
    them) and GHZ. `tokens` concatenate into one ket, e.g. ("Phi+", "0")."""
    cands: dict[int, list[tuple[tuple[str, ...], Vector]]] = {1: [], 2: [], 3: []}
    singles = list(ONE_QUBIT_STATES.items())
    for n in (1, 2, 3):
        for combo in product(singles, repeat=n):
            vec = [1 + 0j]
            for _, v in combo:
                vec = kron_vec(vec, v)
            cands[n].append((tuple(name for name, _ in combo), vec))
    bells = [(k, NAMED_STATES[k]) for k in ("Phi+", "Phi-", "Psi+", "Psi-")]
    for name, vec in bells:
        cands[2].append(((name,), vec))
        for sname, svec in singles:
            cands[3].append(((name, sname), kron_vec(vec, svec)))
            cands[3].append(((sname, name), kron_vec(svec, vec)))
    ghz_minus = [S2 + 0j] + [0j] * 6 + [-S2 + 0j]
    cands[3].append((("GHZ",), NAMED_STATES["GHZ"]))
    cands[3].append((("GHZ-",), ghz_minus))
    return cands


LABEL_CANDIDATES = _build_label_candidates()


def closest_named(psi: Vector) -> tuple[tuple[str, ...], float]:
    """Best-matching named state for a pure state vector (exact order; the
    label is drawn left to right over the bowls)."""
    best: tuple[tuple[str, ...], float] = (("?",), 0.0)
    for tokens, vec in LABEL_CANDIDATES[n_qubits_of(psi)]:
        f = overlap2(vec, psi)
        if f > best[1] + 1e-9:
            best = (tokens, f)
    return best


# --- the qubit item's state -----------------------------------------------------

LABEL_EXACT = 0.97  # at or above: plain ket, e.g. |+>
LABEL_APPROX = 0.80  # at or above: "~|+>"; below: "?"


@dataclass
class QState:
    """The state of one item (a bowl or a linked tray of 2-3 bowls).

    Holds the actual (noisy) density matrix, the ideal noise-free pure state
    it would have without errors, the circuit it went through (for the
    receipt) and the time noise was last applied (for lazy decoherence)."""

    n: int
    rho: Matrix
    ideal: Vector
    ops: list[tuple] = field(default_factory=list)
    t: float = 0.0

    @classmethod
    def fresh(cls, t: float = 0.0) -> "QState":
        return cls(1, [[1 + 0j, 0j], [0j, 0j]], [1 + 0j, 0j], [], t)

    def copy(self) -> "QState":
        return QState(self.n, [r[:] for r in self.rho], self.ideal[:], list(self.ops), self.t)

    # --- time evolution ---
    def advance(self, now: float, noise: Noise) -> None:
        """Apply T1/T2 decoherence for the time since the last update."""
        dt = now - self.t
        self.t = now
        if dt <= 0 or noise.is_noiseless:
            return
        gamma = 0.0 if math.isinf(noise.t1) else 1 - math.exp(-dt / noise.t1)
        phase = math.exp(-dt * noise.dephasing_rate)
        rho = self.rho
        for q in range(self.n):
            rho = amplitude_damp(rho, q, self.n, gamma)
            rho = dephase(rho, q, self.n, phase)
        self.rho = rho

    # --- gates ---
    def apply(self, gate: str, q: int = 0, depolarizing: float = 0.0) -> None:
        u = GATES[gate]
        self.rho = conjugate_1q(self.rho, u, q, self.n)
        self.ideal = apply_1q_vec(self.ideal, u, q, self.n)
        self.rho = depolarize(self.rho, q, self.n, depolarizing)
        self.ops.append((gate, q))

    def cnot(self, c: int, t: int, depolarizing: float = 0.0) -> None:
        perm = _cnot_perm(c, t, self.n)
        self.rho = [[self.rho[perm[i]][perm[j]] for j in range(len(perm))] for i in range(len(perm))]
        self.ideal = [self.ideal[perm[i]] for i in range(len(perm))]
        for q in (c, t):
            self.rho = depolarize(self.rho, q, self.n, depolarizing)
        self.ops.append(("CNOT", c, t))

    def scramble(self) -> None:
        """Maximally mixed (a cosmic-ray hit). The ideal state is unchanged,
        so fidelity collapses to 1/2^n."""
        d = 1 << self.n
        self.rho = [[(1 / d if i == j else 0) + 0j for j in range(d)] for i in range(d)]

    # --- queries ---
    def fidelity(self, target: Vector, permute: bool = True) -> float:
        """<target| rho |target>, maximised over qubit orderings (a tray can be
        served in any order: all v1 targets are symmetric anyway)."""
        if len(target) != len(self.rho):
            return 0.0
        orders = permutations(range(self.n)) if permute else [tuple(range(self.n))]
        return max(expectation(permute_vec(target, o), self.rho) for o in orders)

    def ideal_fidelity(self) -> float:
        """How close the noisy state still is to what it should be."""
        return expectation(self.ideal, self.rho)

    def bloch(self, q: int) -> tuple[float, float, float]:
        return bloch_of(reduced_1q(self.rho, q, self.n))

    def ideal_bloch(self, q: int) -> tuple[float, float, float]:
        return bloch_of(reduced_1q(outer(self.ideal), q, self.n))

    def entanglement(self) -> float:
        """0 for a product ideal state, 1 when every bowl's own arrow is gone
        (maximally entangled): 1 - mean reduced Bloch length of the ideal."""
        if self.n == 1:
            return 0.0
        lengths = [math.sqrt(sum(c * c for c in self.ideal_bloch(q))) for q in range(self.n)]
        return max(0.0, 1.0 - sum(lengths) / self.n)

    def label(self) -> tuple[tuple[str, ...], str]:
        """(ket tokens, prefix) for the floating label: prefix "" = exact,
        "~" = close, and tokens ("?",) when nothing named is close.

        Candidates are the name of the ideal state plus the all-|0> state (T1
        drags every bowl there), so this stays cheap enough for a 10 Hz
        refresh while still following the physics."""
        tokens, f_ideal_named = closest_named(self.ideal)
        best_tokens, best_f = tokens, 0.0
        if f_ideal_named > 0.99:
            best_f = self.fidelity(LOOKUP[tokens], permute=False)
        ground_tokens = ("0",) * self.n
        if ground_tokens != best_tokens:
            f0 = self.rho[0][0].real
            if f0 > best_f:
                best_tokens, best_f = ground_tokens, f0
        if best_f >= LABEL_EXACT:
            return best_tokens, ""
        if best_f >= LABEL_APPROX:
            return best_tokens, "~"
        return ("?",), ""


LOOKUP: dict[tuple[str, ...], Vector] = {
    tokens: vec for cands in LABEL_CANDIDATES.values() for tokens, vec in cands
}


def merge(a: QState, b: QState) -> QState:
    """Tensor product a (x) b: a's bowls first. Both must be up to date in time."""
    if a.n + b.n > MAX_QUBITS:
        raise ValueError("a tray holds at most 3 qubits")
    ops = list(a.ops) + [
        (op[0], *(q + a.n for q in op[1:])) for op in b.ops
    ]
    return QState(
        a.n + b.n, kron_mat(a.rho, b.rho), kron_vec(a.ideal, b.ideal), ops, max(a.t, b.t)
    )


def cnot_merge(control: QState, target: QState, depolarizing: float = 0.0) -> QState:
    """The CNOT Waffle Iron: control tray's first bowl controls target tray's
    first bowl. The result is one linked tray, control's bowls first."""
    merged = merge(control, target)
    merged.cnot(0, control.n, depolarizing)
    return merged


def rotate(v: tuple[float, float, float], axis: tuple[float, float, float], angle: float):
    """Rodrigues rotation of vector v about a unit axis (for gate animations)."""
    x, y, z = v
    ax, ay, az = axis
    c, s = math.cos(angle), math.sin(angle)
    dot = x * ax + y * ay + z * az
    cx, cy, cz = ay * z - az * y, az * x - ax * z, ax * y - ay * x
    return (
        x * c + cx * s + ax * dot * (1 - c),
        y * c + cy * s + ay * dot * (1 - c),
        z * c + cz * s + az * dot * (1 - c),
    )
