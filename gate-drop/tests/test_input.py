import pygame

from gate_drop import config
from gate_drop import input as ginput
from gate_drop.input import AutoRepeat, Input, axis_sign, should_quit


def test_axis_sign_has_a_deadzone():
    assert axis_sign(0.3, 0.5) == 0
    assert axis_sign(-0.9, 0.5) == -1
    assert axis_sign(0.9, 0.5) == 1


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
    ginput.set_keyboard_enabled(False)
    try:
        assert not ginput.read_keys()[pygame.K_a]
    finally:
        ginput.set_keyboard_enabled(True)


def test_with_no_pads_and_no_keys_the_frame_is_idle():
    pygame.init()
    inp = Input()
    inp.update(1 / 60)
    fi = inp.frame_input()
    assert all(p.move == 0 and not p.cw and not p.soft for p in fi.players.values())
    assert not fi.confirm and not fi.back and not fi.activity
