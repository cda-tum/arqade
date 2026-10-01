"""Tests for the input helpers and an idle Input (no pads, no keys)."""

from __future__ import annotations

import pygame

from brawl_ket import config
from brawl_ket import input as binput
from brawl_ket.fighter import IDLE
from brawl_ket.input import Input, deadzone, edge_presses, should_quit, vertical


def test_deadzone_cuts_the_middle() -> None:
    dz = config.INPUT_CONFIG["axis_deadzone"]
    assert dz == 0.25
    assert deadzone(dz * 0.9) == 0 and deadzone(-dz * 0.9) == 0
    assert deadzone(0.3) == 1 and deadzone(-0.3) == -1
    assert deadzone(1.0) == 1 and deadzone(-1.0) == -1


def test_up_and_down_need_a_firm_push_and_up_is_negative() -> None:
    assert vertical(0.0) == (False, False)
    assert vertical(0.4) == (False, False) and vertical(-0.4) == (False, False)
    assert vertical(-0.6) == (True, False)
    assert vertical(0.6) == (False, True)


def test_edge_presses_are_only_what_just_went_down() -> None:
    assert edge_presses({1}, {1, 2}) == {2}
    assert edge_presses({1, 2}, {1}) == set()
    assert edge_presses(set(), set()) == set()


def test_quitting_needs_start_and_select_on_the_same_pad() -> None:
    assert should_quit(p1_start=True, p1_select=True, p2_start=False, p2_select=False)
    assert not should_quit(p1_start=True, p1_select=False, p2_start=False, p2_select=True)


def test_no_keyboard_reads_nothing() -> None:
    binput.set_keyboard_enabled(False)
    try:
        assert not binput.read_keys()[pygame.K_q]
    finally:
        binput.set_keyboard_enabled(True)


def test_p1_keymap_avoids_the_pad_letters() -> None:
    forbidden = {pygame.K_l, pygame.K_x, pygame.K_r, pygame.K_b, pygame.K_y, pygame.K_a}
    codes = {getattr(pygame, name) for names in config.KEYMAP["p1"].values() for name in names}
    assert codes and not codes & forbidden


def test_with_no_pads_and_no_keys_both_fighters_are_idle() -> None:
    pygame.init()
    binput.set_keyboard_enabled(False)
    try:
        inp = Input()
        inp.joysticks = []
        inp.update(1 / 60)
        fi = inp.frame_input()
        assert fi.fighters == {"p1": IDLE, "p2": IDLE}
        assert not any(fi.confirms.values()) and not any(fi.backs.values()) and not any(fi.pauses.values())
        assert not fi.activity and not inp.quit_combo() and inp.select_held_time == 0.0
    finally:
        binput.set_keyboard_enabled(True)
