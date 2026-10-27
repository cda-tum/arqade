"""The idle exit, batocera/arqade_idle.py: the cabinet's loaders and the
launcher's child both install it, so it is tested here, through the launcher's
virtual pads like a game would see them."""

import pygame
import pytest

from arqade_launcher import child, runner
from arqade_launcher.settings import Settings

idle = child.load_idle()


class Clock:
    def __init__(self):
        self.now = 0.0

    def __call__(self):
        return self.now


def run(watch, clock, seconds, events=(), step=1 / 60):
    """Feed the watch `seconds` of frames; the first frame carries `events`.
    Returns whether it asked to exit."""
    frames = round(seconds / step)
    for i in range(frames):
        clock.now += step
        if watch.see(events if i == 0 else ()):
            return True
    return False


def event(kind, **attrs):
    return pygame.event.Event(kind, **attrs)


def button(down=True, pad=0, number=1):
    return event(pygame.JOYBUTTONDOWN if down else pygame.JOYBUTTONUP, instance_id=pad, button=number)


def axis(value, pad=0, number=0):
    return event(pygame.JOYAXISMOTION, instance_id=pad, axis=number, value=value)


@pytest.fixture
def watch():
    clock = Clock()
    return idle.IdleWatch(clock=clock), clock


class Pads:
    """Stands in for LivePads: what the pads themselves report as held."""

    def __init__(self):
        self.down: dict[tuple, object] = {}

    def __call__(self, key):
        return self.down.get(key)


@pytest.fixture
def live():
    clock, pads = Clock(), Pads()
    return idle.IdleWatch(clock=clock, live=pads), clock, pads


def test_exits_after_twenty_untouched_seconds(watch):
    w, clock = watch
    assert not run(w, clock, idle.TIMEOUT - 0.5)
    assert run(w, clock, 1.0)


def test_a_button_press_starts_the_count_again(watch):
    w, clock = watch
    run(w, clock, 15)
    assert not run(w, clock, 15, [button(), button(down=False)])
    assert run(w, clock, 6)


def test_a_held_button_or_stick_is_input_until_let_go(watch):
    w, clock = watch
    assert not run(w, clock, idle.HOLD_LIMIT - 5, [button()])
    assert not run(w, clock, 15, [button(down=False), axis(-1.0, number=1)])
    assert not run(w, clock, idle.HOLD_LIMIT - 5)
    run(w, clock, 15, [axis(0.0, number=1)])
    assert run(w, clock, 6)


def test_stick_jitter_is_not_input(watch):
    w, clock = watch
    for _ in range(25):
        if run(w, clock, 1, [axis(0.2), axis(-0.1)]):
            break
    else:
        pytest.fail("a drifting stick kept the game alive")


def test_an_unplugged_pad_lets_go_of_what_it_held(watch):
    w, clock = watch
    run(w, clock, 1, [button(pad=1)])
    run(w, clock, 1, [event(pygame.JOYDEVICEREMOVED, instance_id=1)])
    assert run(w, clock, idle.TIMEOUT)


def test_keys_and_mouse_buttons_are_input(watch):
    w, clock = watch
    run(w, clock, 15)
    assert not run(w, clock, 15, [event(pygame.KEYDOWN, key=pygame.K_SPACE, mod=0),
                                  event(pygame.KEYUP, key=pygame.K_SPACE, mod=0)])
    assert not run(w, clock, 15, [event(pygame.MOUSEBUTTONDOWN, button=1, pos=(0, 0))])
    # A mouse merely moving isn't: a desk gets bumped.
    assert run(w, clock, 6, [event(pygame.MOUSEMOTION, pos=(1, 1), rel=(1, 1), buttons=(0, 0, 0))])


def test_a_key_held_down_is_not_held(watch):
    # Batocera's evmapy echoes P1's stick as keys and can press one without
    # ever releasing it (stick jumping straight from one side to the other):
    # a KEYDOWN with no KEYUP must not keep the game open.
    w, clock = watch
    assert not run(w, clock, idle.TIMEOUT - 1, [event(pygame.KEYDOWN, key=pygame.K_KP6, mod=0)])
    assert run(w, clock, 2)


def test_a_release_the_game_threw_away_is_read_off_the_pad(live):
    # The JOYBUTTONUP never reaches the watch (event.clear(), a filtered
    # event.get, a pad re-opened), but the pad says the button is up.
    w, clock, pads = live
    pads.down[("button", 0, 1)] = True
    assert not run(w, clock, 30, [button()])
    del pads.down[("button", 0, 1)]
    assert not run(w, clock, idle.TIMEOUT - 1)
    assert run(w, clock, 2)


def test_a_stick_the_pad_reports_back_in_the_middle_lets_go(live):
    w, clock, pads = live
    pads.down[("axis", 1, 0)] = 1
    assert not run(w, clock, 10, [axis(1.0, pad=1)])
    pads.down.clear()
    assert run(w, clock, idle.TIMEOUT + 1)


def test_a_stick_moved_over_unseen_counts_as_moved(live):
    w, clock, pads = live
    pads.down[("axis", 0, 0)] = 1
    run(w, clock, idle.HOLD_LIMIT - 10, [axis(1.0)])
    pads.down[("axis", 0, 0)] = -1  # now left, no event seen
    assert not run(w, clock, idle.HOLD_LIMIT - 5)
    assert w.held[("axis", 0, 0)][0] == -1


def test_nothing_is_held_for_longer_than_the_hold_limit(live):
    # A jammed button, or an axis that rests at full deflection (a trigger),
    # still lets the game close.
    w, clock, pads = live
    pads.down[("button", 0, 1)] = True
    pads.down[("axis", 0, 2)] = -1
    assert not run(w, clock, idle.HOLD_LIMIT - 1, [button(), axis(-1.0, number=2)])
    assert not run(w, clock, idle.TIMEOUT - 1)
    assert run(w, clock, 3)


def test_the_hold_limit_runs_per_input(live):
    # A button stuck on one pad stops counting HOLD_LIMIT after it went
    # down, however long the other player goes on: once they leave, the game
    # closes TIMEOUT after their last press.
    w, clock, pads = live
    pads.down[("button", 1, 4)] = True
    assert not run(w, clock, idle.HOLD_LIMIT - 10, [button(pad=1, number=4)])
    assert not run(w, clock, 20, [button(), button(down=False)])
    assert not run(w, clock, idle.TIMEOUT - 1, [button(), button(down=False)])
    assert run(w, clock, 2)


def test_a_long_pause_between_frames_does_not_count(watch):
    w, clock = watch
    w.see(())
    clock.now += 60.0  # loading, nothing read meanwhile
    assert not w.see(())
    assert w.idle == idle.MAX_STEP


def test_installed_it_ends_the_game_through_event_get(monkeypatch):
    clock = Clock()
    monkeypatch.setattr(idle.time, "monotonic", clock)
    pygame.display.set_mode((64, 64))
    restore = idle.install()
    try:
        pygame.event.get()
        for _ in range(int(idle.TIMEOUT / 0.2) - 1):
            clock.now += 0.2
            pygame.event.get()
        clock.now += 0.4
        with pytest.raises(SystemExit):
            pygame.event.get()
    finally:
        restore()


def test_the_launchers_virtual_pads_count_as_input(monkeypatch):
    clock = Clock()
    monkeypatch.setattr(idle.time, "monotonic", clock)
    pygame.display.set_mode((64, 64))
    pygame.joystick.init()
    restore_pads = child.install(runner.input_config(Settings()))
    restore = idle.install()
    try:
        pygame.event.get()
        clock.now += idle.MAX_STEP
        pygame.event.post(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_d, mod=0))  # P1 stick right
        events = pygame.event.get()
        assert any(e.type == pygame.JOYAXISMOTION for e in events)
        for _ in range(int((idle.HOLD_LIMIT - 1) / idle.MAX_STEP)):
            clock.now += idle.MAX_STEP
            pygame.event.get()  # still held: the virtual pad says so too
    finally:
        restore()
        restore_pads()
        pygame.joystick.quit()


def test_live_pads_read_the_launchers_virtual_pads():
    pygame.display.set_mode((64, 64))
    pygame.joystick.init()
    restore_pads = child.install(runner.input_config(Settings()))
    try:
        pads = idle.LivePads()
        a, stick = ("button", 0, 1), ("axis", 0, 0)  # P1: A on N, stick right on D
        assert pads(a) is None and pads(stick) is None
        for key in (pygame.K_n, pygame.K_d):
            pygame.event.post(pygame.event.Event(pygame.KEYDOWN, key=key, mod=0))
        pygame.event.get()
        assert pads(a) is True and pads(stick) == 1
        assert pads(("button", 1, 1)) is None  # P2 isn't pressing anything
        assert pads(("button", 7, 1)) is None  # no such pad
        pygame.event.post(pygame.event.Event(pygame.KEYUP, key=pygame.K_n, mod=0))
        pygame.event.get()
        assert pads(a) is None
    finally:
        restore_pads()
        pygame.joystick.quit()


def test_installed_a_key_stuck_down_does_not_keep_the_game_open(monkeypatch):
    # End to end, the cabinet's bug: an evmapy key (here the keypad's 6, which
    # no virtual pad uses) goes down and never comes back up.
    clock = Clock()
    monkeypatch.setattr(idle.time, "monotonic", clock)
    pygame.display.set_mode((64, 64))
    pygame.joystick.init()
    restore_pads = child.install(runner.input_config(Settings()))
    restore = idle.install()
    try:
        pygame.event.get()
        pygame.event.post(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_KP6, mod=0))
        with pytest.raises(SystemExit):
            for _ in range(int((idle.TIMEOUT + 1) / idle.MAX_STEP)):
                clock.now += idle.MAX_STEP
                pygame.event.get()
    finally:
        restore()
        restore_pads()
        pygame.joystick.quit()
