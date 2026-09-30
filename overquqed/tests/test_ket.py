import hashlib

import pygame
import pytest

from overquqed import palette
from overquqed.fonts import load_font
from overquqed.ket import ascii_ket, ket_surface, token_color


@pytest.fixture(scope="module", autouse=True)
def _pygame():
    pygame.font.init()
    yield


def _glyph_hash(ch):
    s = load_font(8).render(ch, False, (255, 255, 255))
    return hashlib.md5(pygame.image.tobytes(s, "RGBA")).hexdigest()


def test_font_has_phi_and_psi_but_no_ket_bracket():
    missing = _glyph_hash("⟩")
    assert _glyph_hash("Φ") != missing
    assert _glyph_hash("Ψ") != missing
    assert _glyph_hash("⁺") == missing  # superscript plus: drawn by ket.py


def test_ascii_form():
    assert ascii_ket(("Phi+",), "~") == "~|Phi+>"
    assert ascii_ket(("0", "+")) == "|0+>"


def test_colours_follow_the_palette_meaning():
    assert token_color(("0",)) == palette.KET_0
    assert token_color(("1",)) == palette.KET_1
    assert token_color(("+",)) == palette.KET_PLUS
    assert token_color(("-",)) == palette.KET_MINUS
    assert token_color(("Phi+",)) == palette.GOLD
    assert token_color(("?",)) == palette.NOISE


def test_scaled_ket_is_an_exact_integer_upscale():
    small = ket_surface(("Phi+",))
    big = ket_surface(("Phi+",), scale=2)
    assert big.get_size() == (small.get_width() * 2, small.get_height() * 2)
    assert small.get_bounding_rect().width > 10
