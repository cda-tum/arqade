import pygame

from qircuit import input as qinput
from qircuit.input import Input, hat_held, menu_direction, should_quit, stick_held


def test_the_stick_reads_every_axis_past_the_deadzone():
    assert stick_held(0.1, -0.2, 0.5) == set()
    assert stick_held(0.0, -0.9, 0.5) == {"up"}  # SDL: negative y is up
    assert stick_held(0.9, -0.9, 0.5) == {"up", "right"}  # faster and a wire change at once
    assert stick_held(-0.8, 0.7, 0.5) == {"down", "left"}


def test_the_hat_reads_positive_y_as_up():
    assert hat_held((0, 1)) == {"up"}
    assert hat_held((-1, -1)) == {"left", "down"}
    assert hat_held((0, 0)) == set()


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
        assert not keys[pygame.K_ESCAPE]
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
