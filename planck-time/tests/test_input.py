import pygame

from planck_time import config
from planck_time import input as pinput
from planck_time.input import AutoRepeat, Input, deadzone, should_quit, step_sign


def test_deadzone_cuts_the_middle_and_rescales_the_rest():
    dz = config.INPUT_CONFIG["axis_deadzone"]
    assert deadzone(dz * 0.9) == 0.0
    assert deadzone(1.0) == 1.0 and deadzone(-1.0) == -1.0
    assert 0 < deadzone(0.6) < 0.6


def test_a_step_needs_a_firm_push():
    assert step_sign(0.3) == 0
    assert step_sign(0.8) == 1 and step_sign(-0.8) == -1


def test_auto_repeat_fires_at_once_then_after_a_delay_then_steadily():
    r = AutoRepeat()
    assert r.update(0.016, 1) == 1
    assert r.update(config.REPEAT_DELAY - 0.05, 1) == 0
    assert r.update(0.06, 1) == 1
    assert r.update(config.REPEAT_INTERVAL - 0.03, 1) == 0
    assert r.update(0.04, 1) == 1
    assert r.update(0.016, -1) == -1  # a new direction fires at once
    assert r.update(0.5, 0) == 0


def test_quitting_needs_start_and_select_on_the_same_pad():
    assert should_quit(p1_start=True, p1_select=True, p2_start=False, p2_select=False)
    assert not should_quit(p1_start=True, p1_select=False, p2_start=False, p2_select=True)


def test_no_keyboard_reads_nothing():
    pinput.set_keyboard_enabled(False)
    try:
        assert not pinput.read_keys()[pygame.K_q]
    finally:
        pinput.set_keyboard_enabled(True)


def test_with_no_pads_and_no_keys_the_frame_is_idle():
    pygame.init()
    inp = Input()
    inp.update(1 / 60)
    fi = inp.frame_input()
    assert all(p.stick == (0.0, 0.0) and p.step == (0, 0) and not p.a for p in fi.players.values())
    assert all(d == (0, 0) for d in fi.nav.values())
    assert not fi.confirm and not fi.back and not fi.pause and not fi.activity


def test_any_key_counts_as_a_press_unless_the_keyboard_is_off():
    pygame.init()
    inp = Input()
    inp.handle(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_z))
    inp.update(1 / 60)
    assert inp.frame_input().any_press
    inp.update(1 / 60)
    assert not inp.frame_input().any_press  # a press, not a hold
    pinput.set_keyboard_enabled(False)
    try:
        inp.handle(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_z))
        inp.update(1 / 60)
        assert not inp.frame_input().any_press
    finally:
        pinput.set_keyboard_enabled(True)
