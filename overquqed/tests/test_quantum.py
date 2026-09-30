import math
from itertools import product

import pytest

from overquqed.quantum import (
    GATE_ROTATIONS,
    GATES,
    NAMED_STATES,
    Noise,
    QState,
    amplitude_damp,
    cnot_merge,
    conjugate_1q,
    dephase,
    depolarize,
    merge,
    rotate,
    trace,
)

PLUS = NAMED_STATES["+"]
MINUS = NAMED_STATES["-"]


def fresh_after(*gates):
    s = QState.fresh()
    for g in gates:
        s.apply(g)
    return s


def close(a, b, tol=1e-9):
    return abs(a - b) < tol


def mat_close(a, b, tol=1e-9):
    return all(abs(x - y) < tol for ra, rb in zip(a, b) for x, y in zip(ra, rb))


def matmul(a, b):
    return [[sum(a[i][k] * b[k][j] for k in range(2)) for j in range(2)] for i in range(2)]


def equal_up_to_phase(a, b):
    # a = e^{i phi} b for 2x2 matrices
    for i, j in product(range(2), range(2)):
        if abs(b[i][j]) > 1e-9:
            phase = a[i][j] / b[i][j]
            break
    return abs(abs(phase) - 1) < 1e-9 and all(
        abs(a[i][j] - phase * b[i][j]) < 1e-9 for i, j in product(range(2), range(2))
    )


# --- gate identities ---------------------------------------------------------


def test_hadamard_squared_is_identity():
    h = GATES["H"]
    assert equal_up_to_phase(matmul(h, h), GATES["I"])


def test_hxh_is_z_and_hzh_is_x():
    h, x, z = GATES["H"], GATES["X"], GATES["Z"]
    assert equal_up_to_phase(matmul(matmul(h, x), h), z)
    assert equal_up_to_phase(matmul(matmul(h, z), h), x)


def test_s_squared_is_z_and_t_squared_is_s():
    s, t = GATES["S"], GATES["T"]
    assert equal_up_to_phase(matmul(s, s), GATES["Z"])
    assert equal_up_to_phase(matmul(t, t), s)


# --- single qubit recipes ----------------------------------------------------


def test_fresh_bowl_is_zero_pointing_north():
    s = QState.fresh()
    assert close(s.fidelity(NAMED_STATES["0"]), 1)
    assert s.bloch(0) == pytest.approx((0, 0, 1))


def test_x_flips_to_one():
    s = fresh_after("X")
    assert close(s.fidelity(NAMED_STATES["1"]), 1)
    assert s.bloch(0) == pytest.approx((0, 0, -1))


def test_h_makes_plus_on_the_equator():
    s = fresh_after("H")
    assert close(s.fidelity(PLUS), 1)
    assert s.bloch(0) == pytest.approx((1, 0, 0), abs=1e-9)


def test_blending_twice_unblends():
    assert close(fresh_after("H", "H").fidelity(NAMED_STATES["0"]), 1)


def test_gate_order_matters_x_then_h_is_minus_but_h_then_x_is_plus():
    assert close(fresh_after("X", "H").fidelity(MINUS), 1)
    # X on |+> does nothing visible: |+> is an X eigenstate.
    assert close(fresh_after("H", "X").fidelity(PLUS), 1)
    assert close(fresh_after("H", "X").fidelity(MINUS), 0)


def test_h_then_z_is_minus_and_z_on_zero_is_only_a_global_phase():
    assert close(fresh_after("H", "Z").fidelity(MINUS), 1)
    assert close(fresh_after("Z").fidelity(NAMED_STATES["0"]), 1)


def test_bloch_arrow_matches_gate_rotation_axes():
    for gate, start in (("X", (0, 0, 1)), ("H", (0, 0, 1)), ("Z", (1, 0, 0)), ("H", (1, 0, 0))):
        s = QState.fresh()
        if start == (1, 0, 0):
            s.apply("H")
        s.apply(gate)
        axis, angle = GATE_ROTATIONS[gate]
        assert rotate(start, axis, angle) == pytest.approx(s.bloch(0), abs=1e-9)


# --- entanglement ---------------------------------------------------------------


def test_h_then_cnot_makes_phi_plus_and_the_bowls_lose_their_arrows():
    bell = cnot_merge(fresh_after("H"), QState.fresh())
    assert close(bell.fidelity(NAMED_STATES["Phi+"]), 1)
    for q in (0, 1):
        assert bell.bloch(q) == pytest.approx((0, 0, 0), abs=1e-9)
    assert close(bell.entanglement(), 1)
    assert bell.label() == (("Phi+",), "")


def test_cnot_with_a_basis_state_control_creates_no_entanglement():
    for control in (QState.fresh(), fresh_after("X")):
        tray = cnot_merge(control, fresh_after("H"))
        assert close(tray.entanglement(), 0)
        assert close(tray.fidelity(NAMED_STATES["Phi+"]), 0.25)


def test_wrong_cnot_orientation_fails_the_bell_order():
    # Superposition in the *target* slot, |0> as control: product state |0+>.
    tray = cnot_merge(QState.fresh(), fresh_after("H"))
    assert tray.fidelity(NAMED_STATES["Phi+"]) < 0.8
    assert tray.label() == (("0", "+"), "")


def test_bell_variants_from_phi_plus():
    def bell():
        return cnot_merge(fresh_after("H"), QState.fresh())

    phi_minus = bell()
    phi_minus.apply("Z")
    assert close(phi_minus.fidelity(NAMED_STATES["Phi-"]), 1)
    psi_plus = bell()
    psi_plus.apply("X")
    assert close(psi_plus.fidelity(NAMED_STATES["Psi+"]), 1)
    psi_minus = bell()
    psi_minus.apply("X")
    psi_minus.apply("Z")
    assert close(psi_minus.fidelity(NAMED_STATES["Psi-"]), 1)
    # X on the target before the CNOT also gives Psi+.
    alt = cnot_merge(fresh_after("H"), fresh_after("X"))
    assert close(alt.fidelity(NAMED_STATES["Psi+"]), 1)


def test_bell_tray_as_control_with_fresh_target_makes_ghz():
    bell = cnot_merge(fresh_after("H"), QState.fresh())
    ghz = cnot_merge(bell, QState.fresh())
    assert ghz.n == 3
    assert close(ghz.fidelity(NAMED_STATES["GHZ"]), 1)
    assert ghz.label() == (("GHZ",), "")
    assert ghz.ops == [("H", 0), ("CNOT", 0, 1), ("CNOT", 0, 2)]


def test_trays_never_exceed_three_qubits():
    bell = cnot_merge(fresh_after("H"), QState.fresh())
    with pytest.raises(ValueError):
        merge(bell, bell)


# --- fidelity -------------------------------------------------------------------


def test_fidelity_ignores_global_phase():
    s = QState.fresh()
    s.apply("X")
    s.apply("Z")  # -|1>
    assert close(s.fidelity(NAMED_STATES["1"]), 1)
    assert close(s.fidelity([0j, -1 + 0j]), 1)


def test_fidelity_is_maximised_over_qubit_permutations():
    # |0>|1> vs target |1>|0>
    tray = merge(QState.fresh(), fresh_after("X"))
    target = [0j, 0j, 1 + 0j, 0j]
    assert close(tray.fidelity(target, permute=False), 0)
    assert close(tray.fidelity(target), 1)


def test_fidelity_for_wrong_qubit_count_is_zero():
    assert QState.fresh().fidelity(NAMED_STATES["Phi+"]) == 0


# --- noise ----------------------------------------------------------------------


def is_valid_density_matrix(m):
    d = len(m)
    if not close(trace(m).real, 1, 1e-9):
        return False
    for i in range(d):
        for j in range(d):
            if abs(m[i][j] - m[j][i].conjugate()) > 1e-9:
                return False
    # positivity: 2x2 principal minors and diagonal (sufficient check for tests)
    return all(m[i][i].real > -1e-12 for i in range(d)) and all(
        m[i][i].real * m[j][j].real - abs(m[i][j]) ** 2 > -1e-9 for i in range(d) for j in range(d)
    )


@pytest.mark.parametrize("channel", ["damp", "dephase", "depol"])
def test_noise_channels_preserve_trace_hermiticity_and_positivity(channel):
    ghz = cnot_merge(cnot_merge(fresh_after("H"), QState.fresh()), QState.fresh())
    m = ghz.rho
    for q in range(3):
        if channel == "damp":
            m = amplitude_damp(m, q, 3, 0.3)
        elif channel == "dephase":
            m = dephase(m, q, 3, 0.4)
        else:
            m = depolarize(m, q, 3, 0.2)
        assert is_valid_density_matrix(m)


def test_plus_dephases_as_one_plus_exp_over_two():
    noise = Noise(t1=100, t2=45)
    s = fresh_after("H")
    s.advance(20.0, noise)
    assert s.ideal_fidelity() == pytest.approx((1 + math.exp(-20 / 45)) / 2, abs=1e-9)


def test_one_relaxes_as_exp_minus_t_over_t1():
    noise = Noise(t1=100, t2=45)
    s = fresh_after("X")
    s.advance(22.0, noise)
    assert s.ideal_fidelity() == pytest.approx(math.exp(-22 / 100), abs=1e-9)
    # ...and the arrow is dragged towards the north pole
    assert s.bloch(0)[2] > -1


def test_zero_never_decays():
    s = QState.fresh()
    s.advance(500.0, Noise(t1=100, t2=45))
    assert close(s.ideal_fidelity(), 1)


def test_lazy_noise_is_split_invariant():
    noise = Noise(t1=100, t2=45)
    a, b = fresh_after("H"), fresh_after("H")
    a.advance(30.0, noise)
    for k in range(1, 31):
        b.advance(float(k), noise)
    assert mat_close(a.rho, b.rho)


def test_noiseless_levels_do_nothing():
    s = fresh_after("H")
    s.advance(1000.0, Noise())
    assert close(s.ideal_fidelity(), 1)


def test_t2_above_twice_t1_is_rejected():
    with pytest.raises(ValueError):
        Noise(t1=10, t2=30)


def test_labels_go_approximate_then_unknown_as_noise_grows():
    noise = Noise(t1=100, t2=45)
    s = fresh_after("H")
    assert s.label() == (("+",), "")
    s.advance(5.0, noise)
    assert s.label() == (("+",), "")
    s.advance(15.0, noise)
    assert s.label() == (("+",), "~")
    s.advance(60.0, noise)
    assert s.label()[0] == ("?",)


def test_scramble_makes_a_maximally_mixed_state():
    bell = cnot_merge(fresh_after("H"), QState.fresh())
    bell.scramble()
    assert close(bell.ideal_fidelity(), 0.25)
    assert is_valid_density_matrix(bell.rho)


def test_depolarizing_gate_error_lowers_fidelity():
    s = QState.fresh()
    s.apply("H", depolarizing=0.1)
    assert 0.9 < s.ideal_fidelity() < 1


def test_conjugate_is_unitary_evolution():
    rho = fresh_after("H").rho
    back = conjugate_1q(rho, GATES["H"], 0, 1)
    assert mat_close(back, [[1, 0], [0, 0]])
