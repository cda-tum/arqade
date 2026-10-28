"""Tests for the input helpers and an idle Input (no pads, no keys)."""

from __future__ import annotations

import pygame
from arqade_common.input import KEYBOARD, PAD, STANDARD

from brawl_ket import config
from brawl_ket import input as binput
from brawl_ket.fighter import IDLE
from brawl_ket.input import Input, deadzone, edge_presses, nav_push, should_quit, vertical


def test_deadzone_cuts_the_middle() -> None:
    dz = config.AXIS_DEADZONE
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
        assert not binput.read_keys()[pygame.K_b]
    finally:
        binput.set_keyboard_enabled(True)


def test_with_no_pads_and_no_keys_both_fighters_are_idle() -> None:
    pygame.init()
    binput.set_keyboard_enabled(False)
    try:
        inp = Input()
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


class _Keys:
    """pygame.key.get_pressed() with these keys down."""

    def __init__(self, held) -> None:
        self.held = held

    def __getitem__(self, key: int) -> bool:
        return key in self.held


def test_any_button_is_any_pad_button_going_down_but_never_the_stick(monkeypatch) -> None:
    pygame.init()
    binput.set_keyboard_enabled(False)
    try:
        inp = Input()
        pad = FakePad()
        monkeypatch.setattr(inp.pads, "pad", lambda slot: pad if slot == 0 else None)
        pad.axes = [1.0, -1.0]
        inp.update(1 / 60)
        assert not inp.frame_input().any_button
        pad.down = {8}                      # Select: not A, not Start
        inp.update(1 / 60)
        assert inp.frame_input().any_button
        inp.update(1 / 60)                  # held: not again
        assert not inp.frame_input().any_button
        pad.down = {4}                      # L
        inp.update(1 / 60)
        assert inp.frame_input().any_button
    finally:
        binput.set_keyboard_enabled(True)


def test_the_cabinet_pads_buttons_are_the_fights(monkeypatch) -> None:
    """Raw 1, 2, 0 and 3 are the printed A, B, X and Y (AGENTS.md); Start (raw 9) pauses and
    confirms, Start + Select (raw 8) on one pad quits."""
    pygame.init()
    binput.set_keyboard_enabled(False)
    try:
        inp = Input()
        pads = [FakePad(), FakePad()]
        monkeypatch.setattr(inp.pads, "pad", lambda slot: pads[slot])
        pads[0].down, pads[1].down = {1, 0}, {2, 3}
        inp.update(1 / 60)
        fi = inp.frame_input()
        assert fi.fighters["p1"].a and fi.fighters["p1"].x and not fi.fighters["p1"].b
        assert fi.fighters["p2"].b and fi.fighters["p2"].y and not fi.fighters["p2"].a
        assert fi.confirms == {"p1": True, "p2": False} and fi.backs == {"p1": False, "p2": True}
        pads[0].down, pads[1].down = {9}, set()
        inp.update(1 / 60)
        assert inp.frame_input().pauses["p1"] and inp.frame_input().confirms["p1"]
        pads[0].down = {9, 8}
        inp.update(1 / 60)
        assert inp.quit_combo()
    finally:
        binput.set_keyboard_enabled(True)


def test_the_shared_keyboard_layout_fights_and_pauses(monkeypatch) -> None:
    """P1's B key is their A button (a light), V their B, G their X, C their Y, Space their
    Start, W A S D their stick; P2's L, K, I, J, Enter and the arrows."""
    pygame.init()
    inp = Input()
    held = {pygame.K_b, pygame.K_g, pygame.K_d, pygame.K_k, pygame.K_j, pygame.K_UP}
    monkeypatch.setattr(binput, "read_keys", lambda: _Keys(held))
    inp.update(1 / 60)
    fi = inp.frame_input()
    assert fi.fighters["p1"].a and fi.fighters["p1"].x and fi.fighters["p1"].dx == 1
    assert fi.fighters["p2"].b and fi.fighters["p2"].y and fi.fighters["p2"].up
    held.clear()
    held.update({pygame.K_SPACE, pygame.K_v, pygame.K_RETURN, pygame.K_s})
    inp.update(1 / 60)
    fi = inp.frame_input()
    assert fi.pauses == {"p1": True, "p2": True} and fi.fighters["p1"].b and fi.fighters["p1"].down
    held.add(pygame.K_LSHIFT)
    inp.update(1 / 60)
    assert inp.quit_combo()             # Space + L-Shift: P1's Start + Select


def test_a_browser_gamepads_d_pad_walks_and_its_bottom_button_is_a(monkeypatch) -> None:
    pygame.init()
    binput.set_keyboard_enabled(False)
    try:
        inp = Input(STANDARD)
        pad = FakePad()
        pad.get_numbuttons = lambda: 17
        monkeypatch.setattr(inp.pads, "pad", lambda slot: pad if slot == 0 else None)
        pad.down = {0, 15}                  # A, d-pad right
        inp.update(1 / 60)
        fi = inp.frame_input()
        assert fi.fighters["p1"].a and fi.fighters["p1"].dx == 1 and fi.activity
    finally:
        binput.set_keyboard_enabled(True)


def test_the_hints_follow_whoever_last_used_keys_or_a_pad() -> None:
    pygame.init()
    inp = Input()
    assert inp.devices["p1"] == PAD                 # off the browser: the pads, as on the cabinet
    inp.handle(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_v))
    assert inp.devices["p1"] == KEYBOARD and inp.devices.latest == "p1"
    inp.handle(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_l))
    assert inp.devices["p2"] == KEYBOARD and inp.devices.latest == "p2"


def test_any_button_from_events_and_keys_only_with_the_keyboard_on() -> None:
    pygame.init()
    inp = Input()
    inp.handle(pygame.event.Event(pygame.JOYBUTTONDOWN, joy=0, instance_id=0, button=5))
    inp.update(1 / 60)
    assert inp.frame_input().any_button
    inp.handle(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_SPACE))
    inp.update(1 / 60)
    assert inp.frame_input().any_button
    inp.handle(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_LEFT))      # P2's stick
    inp.update(1 / 60)
    assert not inp.frame_input().any_button
    inp.handle(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_w))         # P1's stick
    inp.update(1 / 60)
    assert not inp.frame_input().any_button
    binput.set_keyboard_enabled(False)
    try:
        inp.handle(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_SPACE))
        inp.update(1 / 60)
        assert not inp.frame_input().any_button
    finally:
        binput.set_keyboard_enabled(True)
