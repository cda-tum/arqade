"""Tests for the config module."""

from __future__ import annotations

from brawl_ket import config


def test_frames_conversion() -> None:
    """Test frames() conversion from seconds."""
    assert config.frames(1.0) == 60
    assert config.frames(0.5) == 30


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
