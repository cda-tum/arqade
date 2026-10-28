import pygame
from arqade_common.input import ENCODER, STANDARD

from qarrera import input as qinput
from qarrera.input import Input, menu_direction, should_quit, stick_held


def test_the_stick_reads_every_axis_past_the_deadzone():
    assert stick_held(0.1, -0.2, 0.5) == set()
    assert stick_held(0.0, -0.9, 0.5) == {"up"}  # SDL: negative y is up
    assert stick_held(0.9, -0.9, 0.5) == {"up", "right"}  # faster and a wire change at once
    assert stick_held(-0.8, 0.7, 0.5) == {"down", "left"}


def test_menus_step_one_way_vertical_first():
    assert menu_direction({"up", "right"}) == (0, -1)
    assert menu_direction({"left"}) == (-1, 0)
    assert menu_direction(set()) is None


def test_quitting_needs_start_and_select_on_the_same_pad():
    assert should_quit(p1_start=True, p1_select=True, p2_start=False, p2_select=False)
    assert should_quit(p1_start=False, p1_select=False, p2_start=True, p2_select=True)
    assert not should_quit(p1_start=True, p1_select=False, p2_start=False, p2_select=True)


def test_no_keyboard_reads_nothing():
    qinput.set_keyboard_enabled(False)
    try:
        keys = qinput.read_keys()
        assert not keys[pygame.K_w]
        assert not keys[pygame.K_SPACE]
    finally:
        qinput.set_keyboard_enabled(True)


def test_with_no_pads_and_no_keys_the_frame_is_idle():
    pygame.init()
    inp = Input()
    inp.update(1 / 60)
    fi = inp.frame_input()
    assert all(not v for v in fi.held.values()) and fi.nav is None
    assert not fi.confirm and not fi.back and not fi.activity


def test_any_button_comes_from_the_events_and_keys_only_with_the_keyboard_on():
    pygame.init()
    inp = Input()
    inp.handle(pygame.event.Event(pygame.JOYBUTTONDOWN, joy=1, instance_id=1, button=4))  # printed L
    inp.update(1 / 60)
    assert inp.frame_input().any_button and inp.frame_input().activity
    inp.update(1 / 60)
    assert not inp.frame_input().any_button  # once per press
    inp.handle(pygame.event.Event(pygame.JOYAXISMOTION, joy=0, instance_id=0, axis=1, value=-1.0))
    inp.update(1 / 60)
    assert not inp.frame_input().any_button  # the stick is not a button
    inp.handle(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_w))
    inp.update(1 / 60)
    assert not inp.frame_input().any_button  # nor are the keys that stand in for it
    qinput.set_keyboard_enabled(False)
    try:
        inp.handle(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_SPACE))
        inp.update(1 / 60)
        assert not inp.frame_input().any_button
    finally:
        qinput.set_keyboard_enabled(True)
    inp.handle(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_SPACE))
    inp.update(1 / 60)
    assert inp.frame_input().any_button


def test_a_browser_pads_d_pad_is_no_button_either():
    pygame.init()
    inp = Input(STANDARD)
    inp.handle(pygame.event.Event(pygame.JOYBUTTONDOWN, joy=0, instance_id=0, button=STANDARD.dpad_buttons["up"]))
    inp.update(1 / 60)
    assert not inp.frame_input().any_button


class _Keys:
    def __init__(self, held):
        self.held = held

    def __getitem__(self, key):
        return key in self.held


def test_the_shared_keyboard_drives_with_its_stick_keys_and_its_button_keys(monkeypatch):
    """Left side: W A S D are the stick, G C V B the X Y B A buttons, Space
    Start, Left Shift Select. Right side: arrows, I J K L, Enter, Right Shift."""
    pygame.init()
    inp = Input(ENCODER)
    held = {pygame.K_w, pygame.K_d, pygame.K_v, pygame.K_RIGHT, pygame.K_i}
    monkeypatch.setattr(qinput, "read_keys", lambda: _Keys(held))
    inp.update(1 / 60)
    fi = inp.frame_input()
    assert fi.held[("stick", 0)] == {"up", "right"} and fi.held[("pad", 0)] == {"down"}
    assert fi.held[("stick", 1)] == {"right"} and fi.held[("pad", 1)] == {"up"}
    assert fi.nav == (0, -1) and fi.back and fi.pad_b == (True, False)  # V is the left side's B
    held.clear()
    held.update({pygame.K_l, pygame.K_SPACE})  # the right side's A (also its "right"), the left side's Start
    inp.update(1 / 60)
    fi = inp.frame_input()
    assert fi.confirm and fi.pick and fi.pause and fi.pad_a == (False, True)
    assert fi.pressed[("pad", 1)] == {"right"}
    assert not inp.quit_combo()
    held.add(pygame.K_LSHIFT)  # Select with Start on the same side quits
    inp.update(1 / 60)
    assert inp.quit_combo()
