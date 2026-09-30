import math

import pytest

from quantum_towers.notation import render_state
from quantum_towers.quantum import State, apply_h, apply_t, apply_x, apply_y, apply_z, zero_state

INV_SQRT2 = 1 / math.sqrt(2)


def test_render_zero_state():
    assert render_state(zero_state()) == "|0>"


def test_render_one_state():
    assert render_state(State(0 + 0j, 1 + 0j)) == "|1>"


def test_render_plus_state():
    assert render_state(apply_h(zero_state())) == "|+>"


def test_render_minus_state():
    assert render_state(apply_z(apply_h(zero_state()))) == "|->"


def test_render_plus_i_state():
    assert render_state(State(INV_SQRT2 + 0j, INV_SQRT2 * 1j)) == "|+i>"


def test_render_minus_i_state():
    assert render_state(State(INV_SQRT2 + 0j, -INV_SQRT2 * 1j)) == "|-i>"


def test_render_shows_a_minus_sign_for_negative_global_phase():
    # -|0> is the same *physical* state as |0>, but global phase counts as
    # part of the game state now, so it renders distinctly.
    assert render_state(State(-1 + 0j, 0 + 0j)) == "-|0>"


def test_render_z_on_one_shows_the_minus_sign():
    # The concrete example from the design discussion: Z now genuinely does
    # something visible to |1> (-> -|1>) while leaving |0> untouched.
    assert render_state(apply_z(zero_state())) == "|0>"
    assert render_state(apply_z(State(0 + 0j, 1 + 0j))) == "-|1>"


def test_render_shows_an_i_prefix_for_imaginary_global_phase():
    # Y(|0>) = i|1> -- distinct from X(|0>) = |1> now that phase counts.
    assert render_state(apply_y(zero_state())) == "i|1>"


def test_render_shows_a_minus_i_prefix_for_negative_imaginary_global_phase():
    assert render_state(apply_y(State(0 + 0j, 1 + 0j))) == "-i|0>"


def test_render_t_rotated_state_shows_exact_fraction_not_a_decimal():
    state = apply_t(apply_h(zero_state()))  # 45 degree relative phase
    assert render_state(state) == "1/√2|0> + 1/√2|1>@45°"


def test_render_falls_back_to_decimal_only_for_genuinely_non_special_magnitudes():
    # H applied to a T-rotated equator state lands outside the 10 "nice"
    # forms (magnitude split isn't 1 or 1/sqrt2) -- must still render
    # something sane rather than crashing or matching the wrong symbol,
    # and only THIS case should fall back to a decimal.
    state = apply_h(apply_t(apply_h(zero_state())))
    text = render_state(state)
    assert text.startswith("0.")
    assert "|0>" in text and "|1>" in text
