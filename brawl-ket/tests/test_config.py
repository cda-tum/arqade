"""Tests for the config module."""

from __future__ import annotations

from brawl_ket import config


def test_frames_conversion() -> None:
    """Test frames() conversion from seconds."""
    assert config.frames(1.0) == 60
    assert config.frames(0.5) == 30


def test_button_mappings() -> None:
    """Test that button mappings are correct."""
    assert config.INPUT_CONFIG["system"]["a_button"] == 1
    assert config.INPUT_CONFIG["system"]["b_button"] == 2
    assert config.INPUT_CONFIG["system"]["x_button"] == 0
    assert config.INPUT_CONFIG["system"]["start_button"] == 9
    assert config.INPUT_CONFIG["system"]["select_button"] == 8


def test_p1_keymap_avoids_pad_letters() -> None:
    """Test that P1's keymap avoids the pad's own button letters."""
    p1_keys = []
    for keys in config.KEYMAP["p1"].values():
        for key in keys:
            # Extract the letter from keys like "K_a" -> "a"
            if key.startswith("K_"):
                letter = key[2:].lower()
                p1_keys.append(letter)

    # Pad letters that P1's encoder emits: l, x, r, b, y, a
    pad_letters = {"l", "x", "r", "b", "y", "a"}
    for letter in p1_keys:
        assert letter not in pad_letters, f"P1 keymap uses '{letter}' which is emitted by the pad"


def test_display_scaling() -> None:
    """Test that display dimensions scale evenly onto the cabinet."""
    cabinet_w, cabinet_h = 1920, 1080
    assert cabinet_h % config.INTERNAL_HEIGHT == 0
    assert cabinet_w % config.INTERNAL_WIDTH == 0


def test_stage_bounds() -> None:
    """Test that start positions are within stage bounds."""
    assert config.STAGE_LEFT < config.START_X["p1"]
    assert config.START_X["p1"] < config.START_X["p2"]
    assert config.START_X["p2"] < config.STAGE_RIGHT
