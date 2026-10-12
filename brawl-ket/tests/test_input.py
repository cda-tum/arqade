"""Tests for the input helpers and an idle Input (no pads, no keys)."""

from __future__ import annotations

import pygame

from brawl_ket import config
from brawl_ket import input as binput
from brawl_ket.fighter import IDLE
from brawl_ket.input import Input, deadzone, edge_presses, nav_push, should_quit, vertical


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


def test_a_menu_step_is_a_fresh_push_only() -> None:
    assert nav_push((0, 0), (1, 0)) == (1, 0)
    assert nav_push((1, 0), (1, 0)) == (0, 0)           # held: no repeat
    assert nav_push((1, 0), (-1, 0)) == (-1, 0)         # flicked across
    assert nav_push((1, 0), (1, 1)) == (0, 1)           # only the new direction


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
        assert not fi.activity and not fi.held and fi.nav == {"p1": (0, 0), "p2": (0, 0)}
        assert not inp.quit_combo() and inp.select_held_time == 0.0
    finally:
        binput.set_keyboard_enabled(True)


class FakePad:
    """A cabinet pad: 12 buttons and two axes, no hat."""

    def __init__(self) -> None:
        self.down: set[int] = set()
        self.axes = [0.0, 0.0]

    def get_numbuttons(self) -> int:
        return 12

    def get_button(self, b: int) -> bool:
        return b in self.down

    def get_numaxes(self) -> int:
        return 2

    def get_axis(self, i: int) -> float:
        return self.axes[i]

    def get_numhats(self) -> int:
        return 0


def test_any_button_is_any_raw_button_going_down_but_never_the_stick() -> None:
    pygame.init()
    binput.set_keyboard_enabled(False)
    try:
        inp = Input()
        pad = FakePad()
        inp.joysticks = [pad]
        pad.axes = [1.0, -1.0]
        inp.update(1 / 60)
        assert not inp.frame_input().any_button
        pad.down = {config.INPUT_CONFIG["system"]["select_button"]}    # not A, not Start
        inp.update(1 / 60)
        assert inp.frame_input().any_button
        inp.update(1 / 60)                  # held: not again
        assert not inp.frame_input().any_button
        pad.down = {4}                      # L
        inp.update(1 / 60)
        assert inp.frame_input().any_button
    finally:
        binput.set_keyboard_enabled(True)


def test_any_button_from_events_and_keys_only_with_the_keyboard_on() -> None:
    pygame.init()
    inp = Input()
    inp.joysticks = []
    inp.handle(pygame.event.Event(pygame.JOYBUTTONDOWN, joy=0, instance_id=0, button=5))
    inp.update(1 / 60)
    assert inp.frame_input().any_button
    inp.handle(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_SPACE))
    inp.update(1 / 60)
    assert inp.frame_input().any_button
    inp.handle(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_LEFT))      # P2's stick
    inp.update(1 / 60)
    assert not inp.frame_input().any_button
    binput.set_keyboard_enabled(False)
    try:
        inp.handle(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_SPACE))
        inp.update(1 / 60)
        assert not inp.frame_input().any_button
    finally:
        binput.set_keyboard_enabled(True)
