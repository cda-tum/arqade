import math

import pytest

from ion_surfer.quantum import WavePacket

D = 3800.0  # hbar/m in px^2/s, same order as the game
OMEGA = 4.0
X0 = 600.0


def harmonic_packet(n=400):
    wp = WavePacket(n, 1200, D)
    k = OMEGA * OMEGA / D  # V = 1/2 m w^2 x^2 / hbar = (w^2 / D) x^2 / 2
    wp.set_potential([0.5 * k * (x - X0) ** 2 for x in wp.xs])
    return wp


def evolve(wp, seconds, dt=1 / 480):
    for _ in range(round(seconds / dt)):
        wp.step(dt)


def test_fit_trap_recovers_frequency_and_ground_width():
    wp = harmonic_packet()
    trap = wp.fit_trap(700)
    assert trap.x0 == pytest.approx(X0, abs=0.5)
    assert trap.omega == pytest.approx(OMEGA, rel=1e-3)
    assert trap.sigma0 == pytest.approx(math.sqrt(D / (2 * OMEGA)), rel=1e-3)


def test_fit_trap_returns_none_without_a_minimum_curving_up():
    wp = WavePacket(100, 1200, D)
    wp.set_potential([-0.001 * (x - 600) ** 2 for x in wp.xs])
    assert wp.fit_trap(600) is None


def test_ground_state_is_stationary_vacuum():
    wp = harmonic_packet()
    trap = wp.fit_trap(X0)
    wp.set_gaussian(X0, trap.sigma0)
    evolve(wp, 1.0)
    m = wp.moments()
    assert m.norm == pytest.approx(1.0, abs=1e-6)  # Crank-Nicolson is unitary
    ps = wp.phase_space(m, trap)
    assert ps.var_q == pytest.approx(1.0, abs=0.03)
    assert ps.var_p == pytest.approx(1.0, abs=0.03)
    assert abs(ps.squeezing_db()) < 0.2
    pops = wp.fock_populations(trap, 12)
    assert pops[0] == pytest.approx(1.0, abs=0.01)
    assert m.energy == pytest.approx(OMEGA / 2, rel=0.02)


def test_displaced_packet_oscillates_like_a_coherent_state():
    wp = harmonic_packet()
    trap = wp.fit_trap(X0)
    wp.set_gaussian(X0 + 3 * trap.sigma0, trap.sigma0)  # q = 3 -> alpha = 1.5
    ps = wp.phase_space(wp.moments(), trap)
    assert ps.alpha == pytest.approx(1.5, abs=0.01)
    pops = wp.fock_populations(trap, 16)
    mean_n = sum(k * p for k, p in enumerate(pops))
    assert mean_n == pytest.approx(abs(ps.alpha) ** 2, abs=0.05)  # Poisson mean |alpha|^2
    evolve(wp, math.pi / OMEGA)  # half a period: mirrored across the trap
    m = wp.moments()
    assert m.mean_x == pytest.approx(X0 - 3 * trap.sigma0, abs=0.1 * trap.sigma0)
    # a quarter period later it all sits in momentum
    evolve(wp, math.pi / (2 * OMEGA))
    ps = wp.phase_space(wp.moments(), trap)
    assert abs(ps.q) < 0.2
    assert abs(ps.p) == pytest.approx(3.0, abs=0.2)


def test_narrow_packet_is_squeezed_and_breathes():
    wp = harmonic_packet()
    trap = wp.fit_trap(X0)
    wp.set_gaussian(X0, trap.sigma0 / 2)  # var_q = 1/4 -> 6 dB
    ps = wp.phase_space(wp.moments(), trap)
    assert ps.squeezing_db() == pytest.approx(6.02, abs=0.2)
    pops = wp.fock_populations(trap, 16)
    assert sum(pops[1::2]) < 1e-6  # squeezed vacuum: even phonon numbers only
    assert pops[2] > 0.1
    # breathing: a quarter period later the narrow axis has moved to momentum
    evolve(wp, math.pi / (2 * OMEGA))
    ps = wp.phase_space(wp.moments(), trap)
    assert ps.var_q == pytest.approx(4.0, rel=0.1)
    assert ps.var_p == pytest.approx(0.25, rel=0.1)


def test_kick_adds_momentum():
    wp = harmonic_packet()
    trap = wp.fit_trap(X0)
    wp.set_gaussian(X0, trap.sigma0)
    wp.kick(1 / trap.sigma0)
    ps = wp.phase_space(wp.moments(), trap)
    assert ps.p == pytest.approx(2.0, abs=0.02)


def test_damped_steps_cool_towards_the_ground_state():
    wp = harmonic_packet()
    trap = wp.fit_trap(X0)
    wp.set_gaussian(X0 + 3 * trap.sigma0, trap.sigma0 / 2)
    for _ in range(600):
        wp.step((1 / 240) * (1 - 0.5j))
        wp.normalize()
    assert wp.fock_populations(trap, 12)[0] > 0.99


def test_shift_cells_keeps_the_packet_in_place():
    wp = harmonic_packet()
    trap = wp.fit_trap(X0)
    wp.set_gaussian(X0 + 40, trap.sigma0)
    before = wp.moments()
    wp.shift_cells(25)
    after = wp.moments()
    assert after.mean_x == pytest.approx(before.mean_x, abs=1e-6)
    assert after.norm == pytest.approx(1.0, abs=1e-6)
    wp.shift_cells(-40)
    assert wp.moments().mean_x == pytest.approx(before.mean_x, abs=1e-6)


def test_mean_phonon_number_from_moments_matches_fock_sum():
    wp = harmonic_packet()
    trap = wp.fit_trap(X0)
    wp.set_gaussian(X0 + 2 * trap.sigma0, trap.sigma0 * 0.7, k0=0.5 / trap.sigma0)
    ps = wp.phase_space(wp.moments(), trap)
    from_moments = (ps.var_q + ps.q ** 2 + ps.var_p + ps.p ** 2 - 2) / 4
    pops = wp.fock_populations(trap, 30)
    assert from_moments == pytest.approx(sum(k * p for k, p in enumerate(pops)), abs=0.02)
