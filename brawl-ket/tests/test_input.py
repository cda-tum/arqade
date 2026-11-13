"""Tests for the input helpers and an idle Input (no pads, no keys)."""

from __future__ import annotations

import pygame

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
        assert not binput.read_keys()[pygame.K_q]
    finally:
        binput.set_keyboard_enabled(True)


class Keys:
    """Stands in for pygame.key.get_pressed(): these keys are down."""

    def __init__(self, *held: int) -> None:
        self.held = held

    def __getitem__(self, key: int) -> bool:
        return key in self.held


def test_the_shared_keyboard_fights(monkeypatch) -> None:
    """P1: W A S D, B = A, V = B, G = X, C = Y, Space = Start. P2: arrows, L K I J, Enter."""
    pygame.init()
    inp = Input()
    monkeypatch.setattr(binput, "read_keys", lambda: Keys(pygame.K_d, pygame.K_w, pygame.K_b, pygame.K_g,
                                                         pygame.K_LEFT, pygame.K_DOWN, pygame.K_k, pygame.K_j,
                                                         pygame.K_RETURN))
    inp.update(1 / 60)
    fi = inp.frame_input()
    p1, p2 = fi.fighters["p1"], fi.fighters["p2"]
    assert (p1.dx, p1.up, p1.down, p1.a, p1.b, p1.x, p1.y) == (1, True, False, True, False, True, False)
    assert (p2.dx, p2.up, p2.down, p2.a, p2.b, p2.x, p2.y) == (-1, False, True, False, True, False, True)
    assert fi.confirms == {"p1": True, "p2": True} and fi.pauses == {"p1": False, "p2": True}
    assert fi.backs == {"p1": False, "p2": True}


def test_start_and_select_quit_from_the_keyboard_too_but_there_is_no_quit_key(monkeypatch) -> None:
    pygame.init()
    inp = Input()
    monkeypatch.setattr(binput, "read_keys", lambda: Keys(pygame.K_ESCAPE))
    inp.update(1 / 60)
    assert not inp.quit_combo()
    monkeypatch.setattr(binput, "read_keys", lambda: Keys(pygame.K_SPACE, pygame.K_LSHIFT))
    inp.update(1 / 60)
    assert inp.quit_combo() and inp.select_held_time > 0


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


class FakeSlots:
    """PadSlots with these pads in it, P1's first."""

    def __init__(self, *pads) -> None:
        self.pads = pads

    def pad(self, slot: int):
        return self.pads[slot] if slot < len(self.pads) else None


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


def test_any_button_is_any_raw_button_going_down_but_never_the_stick(monkeypatch) -> None:
    from arqade_common.input import ENCODER
    pygame.init()
    binput.set_keyboard_enabled(False)
    try:
        inp = Input()
        pad = FakePad()
        monkeypatch.setattr(binput, "_pads", FakeSlots(pad))
        pad.axes = [1.0, -1.0]
        inp.update(1 / 60)
        assert not inp.frame_input().any_button
        pad.down = {ENCODER.buttons["select"]}    # not A, not Start
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


def _devices(d1: str, d2: str):
    from arqade_common.input import LastDevice
    devices = LastDevice(d1)
    devices._devices["p2"] = d2
    return devices


def test_hints_name_each_players_keys_or_buttons() -> None:
    from arqade_common.input import KEYBOARD, PAD
    pads, keys = _devices(PAD, PAD), _devices(KEYBOARD, KEYBOARD)
    assert binput.button_name("a", None, pads) == "A" and binput.button_name("start", None, pads) == "START"
    assert binput.button_name("a", None, keys) == "B / L" and binput.button_name("b", "p1", keys) == "V"
    assert not binput.mixed_devices(pads) and not binput.mixed_devices(keys)


def test_one_on_keys_one_on_a_pad_says_whose_letter_is_whose() -> None:
    # "B / A" would read as the B key standing for the pad's A button
    from arqade_common.input import KEYBOARD, PAD
    mixed = _devices(KEYBOARD, PAD)
    assert binput.mixed_devices(mixed)
    assert binput.button_name("a", None, mixed) == "P1 B / P2 A"
    assert binput.button_name("start", None, mixed) == "SPACE / START"     # nothing to mix up
    assert binput.button_name("stick", None, mixed) == "WASD / STICK"
