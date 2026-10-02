import pygame
import pytest

from arqade_launcher import child, runner
from arqade_launcher.settings import Settings


@pytest.fixture
def shim():
    pygame.display.set_mode((64, 64))
    pygame.joystick.init()
    pygame.event.clear()
    restore = child.install(runner.input_config(Settings()))
    yield
    restore()
    pygame.joystick.quit()


def press(key, down=True):
    pygame.event.post(pygame.event.Event(pygame.KEYDOWN if down else pygame.KEYUP, key=key, mod=0))


def joy_events(events):
    return [e for e in events if pygame.JOYAXISMOTION <= e.type <= pygame.JOYDEVICEREMOVED]


def test_two_pads_are_announced_once(shim):
    added = [e for e in pygame.event.get() if e.type == pygame.JOYDEVICEADDED]
    assert [e.device_index for e in added] == [0, 1]
    assert pygame.joystick.get_count() == 2
    assert not [e for e in pygame.event.get() if e.type == pygame.JOYDEVICEADDED]


def test_buttons_report_the_cabinets_raw_numbers(shim):
    pygame.event.get()
    pad1, pad2 = pygame.joystick.Joystick(0), pygame.joystick.Joystick(1)
    press(pygame.K_n)  # P1 A -> raw 1
    press(pygame.K_RETURN)  # P2 Start -> raw 9
    events = joy_events(pygame.event.get())
    assert [(e.type, e.instance_id, e.button) for e in events] == [
        (pygame.JOYBUTTONDOWN, 0, 1), (pygame.JOYBUTTONDOWN, 1, 9)]
    assert pad1.get_button(1) and not pad1.get_button(9)
    assert pad2.get_button(9) and not pad2.get_button(1)
    press(pygame.K_n, down=False)
    events = joy_events(pygame.event.get())
    assert [(e.type, e.button) for e in events] == [(pygame.JOYBUTTONUP, 1)]
    assert not pad1.get_button(1)


def test_held_key_repeats_dont_press_the_button_again(shim):
    pygame.event.get()
    press(pygame.K_n)
    press(pygame.K_n)
    assert len(joy_events(pygame.event.get())) == 1


def test_stick_is_an_analog_axis_like_the_cabinets(shim):
    pygame.event.get()
    pad = pygame.joystick.Joystick(0)
    assert pad.get_numhats() == 0
    press(pygame.K_w)
    (event,) = joy_events(pygame.event.get())
    assert (event.type, event.axis, event.value) == (pygame.JOYAXISMOTION, 1, -1.0)
    assert pad.get_axis(1) == -1.0 and pad.get_axis(0) == 0.0
    press(pygame.K_s)  # up and down together: centred
    (event,) = joy_events(pygame.event.get())
    assert event.value == 0.0 and pad.get_axis(1) == 0.0
    press(pygame.K_w, down=False)
    (event,) = joy_events(pygame.event.get())
    assert event.value == 1.0 and pad.get_axis(1) == 1.0


def test_key_events_still_reach_the_game(shim):
    press(pygame.K_n)
    assert any(e.type == pygame.KEYDOWN and e.key == pygame.K_n for e in pygame.event.get())


def test_real_joystick_events_are_hidden(shim):
    pygame.event.get()
    pygame.event.post(pygame.event.Event(pygame.JOYBUTTONDOWN, joy=0, instance_id=0, button=1))
    assert not joy_events(pygame.event.get())


def test_exit_key_ends_the_game(shim):
    press(pygame.K_ESCAPE)
    with pytest.raises(SystemExit):
        pygame.event.get()


def test_without_pads_only_the_exit_key_is_handled():
    pygame.display.set_mode((64, 64))
    real_count = pygame.joystick.get_count
    restore = child.install(runner.input_config(Settings(pads=False)))
    try:
        assert pygame.joystick.get_count is real_count
        press(pygame.K_n)
        assert not joy_events(pygame.event.get())
        press(pygame.K_ESCAPE)
        with pytest.raises(SystemExit):
            pygame.event.get()
    finally:
        restore()
