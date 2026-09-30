import math

import pytest

from quantum_towers.quantum import (
    State,
    apply_h,
    apply_reset,
    apply_t,
    apply_x,
    apply_y,
    apply_z,
    normalize_global_phase,
    states_equal,
    states_equal_up_to_global_phase,
    zero_state,
)

INV_SQRT2 = 1 / math.sqrt(2)


def test_zero_state_is_basis_zero():
    state = zero_state()
    assert state.a0 == 1 + 0j
    assert state.a1 == 0 + 0j


def test_apply_x_swaps_amplitudes():
    state = apply_x(State(1 + 0j, 0 + 0j))
    assert state == State(0 + 0j, 1 + 0j)


def test_apply_y_on_zero_gives_i_times_one():
    state = apply_y(zero_state())
    assert state.a0 == pytest.approx(0 + 0j)
    assert state.a1 == pytest.approx(0 + 1j)


def test_apply_y_on_one_gives_minus_i_times_zero():
    state = apply_y(State(0 + 0j, 1 + 0j))
    assert state.a0 == pytest.approx(0 - 1j)
    assert state.a1 == pytest.approx(0 + 0j)


def test_apply_z_flips_sign_of_a1_only():
    state = apply_z(State(INV_SQRT2 + 0j, INV_SQRT2 + 0j))
    assert state.a0 == pytest.approx(INV_SQRT2)
    assert state.a1 == pytest.approx(-INV_SQRT2)


def test_apply_h_on_zero_gives_plus_state():
    state = apply_h(zero_state())
    assert state.a0 == pytest.approx(INV_SQRT2)
    assert state.a1 == pytest.approx(INV_SQRT2)


def test_apply_h_is_self_inverse():
    state = apply_h(apply_h(zero_state()))
    assert state.a0 == pytest.approx(1 + 0j)
    assert state.a1 == pytest.approx(0 + 0j)


def test_apply_t_leaves_basis_zero_unchanged():
    state = apply_t(zero_state())
    assert state.a0 == pytest.approx(1 + 0j)
    assert state.a1 == pytest.approx(0 + 0j)


def test_apply_t_rotates_one_amplitude_by_45_degrees():
    state = apply_t(State(0 + 0j, 1 + 0j))
    assert state.a1 == pytest.approx(INV_SQRT2 + INV_SQRT2 * 1j)


def test_apply_t_four_times_equals_z():
    state = zero_state()
    for _ in range(4):
        state = apply_t(state)
    z_state = apply_z(zero_state())
    assert states_equal_up_to_global_phase(state, z_state)


def test_apply_reset_always_returns_zero_state_regardless_of_input():
    state = apply_reset(State(INV_SQRT2 + 0j, -INV_SQRT2 + 0j))
    assert state == zero_state()


def test_normalize_global_phase_flips_negative_a0():
    state = normalize_global_phase(State(-1 + 0j, 0 + 0j))
    assert state.a0 == pytest.approx(1 + 0j)
    assert state.a1 == pytest.approx(0 + 0j)


def test_normalize_global_phase_uses_a1_when_a0_is_zero():
    state = normalize_global_phase(State(0 + 0j, -1 + 0j))
    assert state.a0 == pytest.approx(0 + 0j)
    assert state.a1 == pytest.approx(1 + 0j)


def test_states_equal_up_to_global_phase_true_for_same_state_different_phase():
    a = State(1 + 0j, 0 + 0j)
    b = State(-1 + 0j, 0 + 0j)  # global phase of pi
    assert states_equal_up_to_global_phase(a, b) is True


def test_states_equal_up_to_global_phase_false_for_different_states():
    assert states_equal_up_to_global_phase(zero_state(), State(0 + 0j, 1 + 0j)) is False


def test_states_equal_up_to_global_phase_respects_tolerance():
    # a0 is identical (so phase normalization is a no-op on it); the tiny
    # difference lives in a1, which normalization does NOT cancel out.
    a = State(1 + 0j, 0.5 + 0j)
    b = State(1 + 0j, 0.5 + 1e-8j)
    assert states_equal_up_to_global_phase(a, b, tol=1e-6) is True
    assert states_equal_up_to_global_phase(a, b, tol=1e-12) is False


def test_states_equal_treats_a_global_phase_difference_as_a_different_state():
    # This is the whole point of `states_equal` vs the up-to-phase version:
    # gameplay now cares about the actual sign/phase, not just the physical
    # Bloch-sphere point.
    a = State(1 + 0j, 0 + 0j)
    b = State(-1 + 0j, 0 + 0j)  # global phase of pi -- same physical state, different game state
    assert states_equal(a, b) is False


def test_states_equal_true_for_identical_states():
    a = State(INV_SQRT2 + 0j, -INV_SQRT2 + 0j)
    b = State(INV_SQRT2 + 0j, -INV_SQRT2 + 0j)
    assert states_equal(a, b) is True


def test_states_equal_respects_tolerance():
    a = State(1 + 0j, 0.5 + 0j)
    b = State(1 + 0j, 0.5 + 1e-8j)
    assert states_equal(a, b, tol=1e-6) is True
    assert states_equal(a, b, tol=1e-12) is False


def test_apply_z_exactly_fixes_zero_but_changes_one():
    # This is the concrete motivation for the whole change: under exact
    # equality, Z now genuinely does something to |1> (flips it to -|1>,
    # a different game state) while still leaving |0> completely untouched.
    assert states_equal(apply_z(zero_state()), zero_state())
    assert not states_equal(apply_z(State(0 + 0j, 1 + 0j)), State(0 + 0j, 1 + 0j))


def test_apply_y_on_zero_is_not_states_equal_to_apply_x_on_zero():
    # Y(|0>) = i|1> and X(|0>) = |1> used to be the "same" target (identical
    # up to global phase) -- now they're genuinely different, which is what
    # makes Y non-redundant with X and Z.
    assert not states_equal(apply_y(zero_state()), apply_x(zero_state()))
