import math

import pytest

from ion_surfer.crystal import Crystal, Sampled, jacobi_eigen, mode_name

D = 3800.0
OMEGA = 4.0
K = OMEGA * OMEGA / D  # V = K x^2 / 2 per ion, in rad/s
C = 2000.0
X0 = 600.0


def harmonic():
    xs = [i * 1.0 for i in range(0, 1201)]
    return Sampled(xs, [0.5 * K * (x - X0) ** 2 for x in xs])


def crystal(positions):
    return Crystal(harmonic(), positions, D, C, 10, 1190)


def test_jacobi_diagonalizes_a_symmetric_matrix():
    lams, vecs = jacobi_eigen([[2.0, -1.0], [-1.0, 2.0]])
    assert lams == pytest.approx([1.0, 3.0])
    assert abs(vecs[0][0]) == pytest.approx(1 / math.sqrt(2))


def test_two_ions_sit_symmetric_at_the_coulomb_spacing():
    cr = crystal([550, 700])
    d = (2 * C / K) ** (1 / 3)
    assert cr.x_eq[1] - cr.x_eq[0] == pytest.approx(d, rel=0.01)
    assert (cr.x_eq[0] + cr.x_eq[1]) / 2 == pytest.approx(X0, abs=0.5)


def test_two_ion_modes_are_com_and_stretch_at_sqrt3():
    cr = crystal([550, 700])
    omegas = [math.sqrt(D * lam) for lam in cr.lams]
    assert omegas[0] == pytest.approx(OMEGA, rel=0.01)
    assert omegas[1] == pytest.approx(math.sqrt(3) * OMEGA, rel=0.01)
    assert mode_name(0, cr.vecs[0]) == "COM"
    assert mode_name(1, cr.vecs[1]) == "STRETCH"
    # the per-mode wave packets see the same frequencies
    for m, wp in enumerate(cr.packets):
        assert wp.fit_trap(cr.q_eq[m]).omega == pytest.approx(omegas[m], rel=0.03)


def test_three_ion_mode_frequencies():
    cr = crystal([500, 600, 700])
    ratios = [math.sqrt(D * lam) / OMEGA for lam in cr.lams]
    assert ratios == pytest.approx([1.0, math.sqrt(3), math.sqrt(29 / 5)], rel=0.02)


def test_kicking_every_ion_equally_only_excites_com():
    cr = crystal([550, 700])
    for i in range(cr.n):
        cr.kick_ion(i, 0.05)
    moms = [wp.moments() for wp in cr.packets]
    assert abs(moms[0].mean_k) > 0.05  # COM got it all ...
    assert abs(moms[1].mean_k) < 1e-6  # ... stretch nothing


def test_kicking_one_ion_excites_both_modes():
    cr = crystal([550, 700])
    cr.kick_ion(0, 0.05)
    moms = [wp.moments() for wp in cr.packets]
    assert abs(moms[0].mean_k) == pytest.approx(0.05 / math.sqrt(2), rel=0.01)
    assert abs(moms[1].mean_k) == pytest.approx(0.05 / math.sqrt(2), rel=0.01)


def test_ion_positions_follow_the_modes():
    cr = crystal([550, 700])
    gs = cr.ion_gaussians([wp.moments() for wp in cr.packets])
    for (mean, sd), x in zip(gs, cr.x_eq):
        assert mean == pytest.approx(x, abs=0.5)
    # ground-state width of each ion: (sigma_com^2 + sigma_str^2) / 2
    s_com, s_str = (math.sqrt(D / (2 * w)) for w in (OMEGA, math.sqrt(3) * OMEGA))
    assert gs[0][1] == pytest.approx(math.sqrt((s_com ** 2 + s_str ** 2) / 2), rel=0.03)


def test_moving_the_trap_moves_the_crystal_and_its_grids():
    cr = crystal([550, 700])
    xs = [i * 1.0 for i in range(0, 1201)]
    shifted = Sampled(xs, [0.5 * K * (x - 900) ** 2 for x in xs])
    for _ in range(10):
        cr.update_potential(shifted)
    assert sum(cr.x_eq) / 2 == pytest.approx(900, abs=1)
    for m, wp in enumerate(cr.packets):
        assert wp.x_start < cr.q_eq[m] < wp.x_start + 800


def test_changing_the_potential_leaves_the_ions_where_they_are():
    # A mode's coordinate b.x is measured from the screen's edge, so when
    # the modes turn, every packet has to move with them; that used to put
    # the packets hundreds of px from the equilibrium.
    cr = crystal([500, 600, 700])
    xs = [i * 1.0 for i in range(0, 1201)]
    before = cr.ion_means()
    turned = 0.0
    for step in range(1, 21):  # a bump rising between the 2nd and 3rd ion
        a = 3.0 * step
        bumped = Sampled(xs, [0.5 * K * (x - X0) ** 2 + a * math.exp(-(((x - 650) / 30) ** 2))
                              for x in xs])
        old = [v[:] for v in cr.vecs]
        cr.update_potential(bumped)
        turned = max(turned, max(1 - abs(sum(p * q for p, q in zip(o, n))) for o, n in zip(old, cr.vecs)))
        for x0, x1 in zip(before, cr.ion_means()):
            assert x1 == pytest.approx(x0, abs=2.0)  # half a cell of rounding at most
    assert turned > 1e-4  # the modes really did turn


def test_ions_cannot_pass_each_other_along_a_mode():
    cr = crystal([550, 700])
    stretch = 1
    gap = cr.x_eq[1] - cr.x_eq[0]
    q0 = cr.q_eq[stretch]
    sign = 1 if cr.vecs[stretch][1] > 0 else -1  # +q pulls the ions apart
    # squeeze the pair together, through contact and beyond
    qs = [q0 - sign * gap / math.sqrt(2) * f for f in (0.5, 0.8, 0.95, 1.0, 1.2, 1.5, 2.0)]
    cut = [cr._cut(stretch, q) for q in qs]
    assert all(b > a for a, b in zip(cut, cut[1:]))
