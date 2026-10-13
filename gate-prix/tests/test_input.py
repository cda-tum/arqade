"""Reading the pads and the dev keys into a FrameInput, and the Start + Select quit."""

import pygame
import pytest

from gate_prix import config, input as gp_input
from gate_prix.input import AutoRepeat, Input, deadzone, is_pad, step_sign

DT = 1 / 60
SYSTEM = config.INPUT_CONFIG["system"]
A, B, START, SELECT = (SYSTEM[k] for k in ("a_button", "back_button", "start_button",
                                           "select_button"))


class FakePad:
    count = 0

    def __init__(self, name="Cabinet encoder", buttons=12, axes=2):
        self.name, self.buttons, self.axes = name, buttons, axes
        FakePad.count += 1
        self.iid = 100 + FakePad.count
        self.down: set[int] = set()
        self.axis = [0.0] * axes

    def init(self):
        pass

    def get_name(self):
        return self.name

    def get_instance_id(self):
        return self.iid

    def get_numbuttons(self):
        return self.buttons

    def get_numaxes(self):
        return self.axes

    def get_numhats(self):
        return 0

    def get_button(self, i):
        if i >= self.buttons:
            raise pygame.error("Invalid joystick button")
        return i in self.down

    def get_axis(self, i):
        return self.axis[i]


class Keys:
    def __init__(self):
        self.held: set[int] = set()

    def __getitem__(self, key):
        return key in self.held


@pytest.fixture
def rig(monkeypatch):
    pads: list[FakePad] = []
    keys = Keys()
    monkeypatch.setattr(pygame.joystick, "get_count", lambda: len(pads))
    monkeypatch.setattr(pygame.joystick, "Joystick", lambda i: pads[i])
    monkeypatch.setattr(pygame.key, "get_pressed", lambda: keys)
    gp_input.set_keyboard_enabled(True)
    yield pads, keys
    gp_input.set_keyboard_enabled(True)


def step(inp: Input, n=1):
    for _ in range(n):
        inp.update(DT)
    return inp.frame


# --- The helpers -----------------------------------------------------------------------------


def test_the_deadzone_cuts_and_rescales():
    dz = config.INPUT_CONFIG["axis_deadzone"]
    assert deadzone(dz * 0.9) == 0.0 and deadzone(-dz) == 0.0
    assert deadzone(1.0) == 1.0 and deadzone(-1.0) == -1.0
    assert 0 < deadzone(0.5) < 0.5


def test_a_step_needs_a_push_past_half_way():
    assert step_sign(0.4) == 0 and step_sign(0.6) == 1 and step_sign(-0.7) == -1


def test_auto_repeat_steps_once_then_repeats():
    r = AutoRepeat(delay=0.2, interval=0.1)
    assert r.update(DT, 1) == 1
    steps = [r.update(DT, 1) for _ in range(30)]
    assert steps[:10] == [0] * 10 and sum(steps) >= 3
    assert r.update(DT, 0) == 0 and r.update(DT, -1) == -1


def test_only_real_pads_count():
    assert is_pad(FakePad())
    assert not is_pad(FakePad(buttons=4))  # no Start: not one of the cabinet's pads
    assert not is_pad(FakePad(name="ST LIS3LV02DL Accelerometer"))  # a laptop's sensor


# --- The pads --------------------------------------------------------------------------------


def test_the_stick_steers_and_pulled_back_brakes(rig):
    pads, _ = rig
    pads.append(FakePad())
    inp = Input()
    pads[0].axis = [-0.9, 0.95]
    p1 = step(inp).players["p1"]
    assert p1.steer < -0.8 and p1.brake > 0.9
    pads[0].axis = [0.1, -1.0]  # pushed forward: no brake, but a menu step up
    p1 = step(inp).players["p1"]
    assert p1.steer == 0.0 and p1.brake == 0.0 and p1.nav == (0, -1)


def test_buttons_are_pressed_once_then_held(rig):
    pads, _ = rig
    pads += [FakePad(), FakePad()]
    inp = Input()
    pads[1].down = {A}
    f = step(inp)
    assert f.players["p2"].a and f.players["p2"].held and not f.players["p1"].a
    assert f.activity
    f = step(inp)
    assert not f.players["p2"].a and f.players["p2"].held
    pads[1].down = {B, START}
    f = step(inp)
    assert f.players["p2"].b and f.players["p2"].start and not f.players["p2"].select
    pads[1].down = {B, START, SELECT}
    assert step(inp).players["p2"].select


def test_a_tap_quicker_than_a_frame_still_counts(rig):
    """Polled alone, a button down and up again between two frames would be lost."""
    pads, _ = rig
    pads += [FakePad(), FakePad()]
    inp = Input()
    step(inp)
    inp.handle(pygame.event.Event(pygame.JOYBUTTONDOWN, instance_id=pads[1].iid, button=START))
    f = step(inp)
    assert f.players["p2"].start and not f.players["p1"].start and f.activity
    assert not step(inp).players["p2"].start  # once
    inp.handle(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_q))
    f = step(inp)
    assert f.players["p1"].a and not step(inp).players["p1"].a


def test_a_direction_key_tapped_quicker_than_a_frame_still_steps_the_menu(rig):
    inp = Input()
    step(inp)
    inp.handle(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_RIGHT))
    assert step(inp).players["p2"].nav == (1, 0)
    inp.handle(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_e))
    assert step(inp).players["p1"].nav == (0, -1)
    assert step(inp).players["p1"].nav == (0, 0)


def test_a_tap_seen_both_as_an_event_and_held_is_one_press(rig):
    pads, _ = rig
    pads.append(FakePad())
    inp = Input()
    step(inp)
    inp.handle(pygame.event.Event(pygame.JOYBUTTONDOWN, instance_id=pads[0].iid, button=A))
    pads[0].down = {A}
    assert step(inp).players["p1"].a
    assert not step(inp).players["p1"].a


def test_the_second_real_pad_is_p2_whatever_comes_before_it(rig):
    pads, _ = rig
    pads += [FakePad(name="Accelerometer"), FakePad(), FakePad()]
    inp = Input()
    pads[2].down = {A}
    assert step(inp).players["p2"].a


def test_start_and_select_on_one_pad_quit(rig):
    pads, _ = rig
    pads += [FakePad(), FakePad()]
    inp = Input()
    step(inp)
    pads[1].down = {START}
    step(inp)
    assert not inp.quit_combo()
    pads[1].down = {START, SELECT}
    step(inp)
    assert inp.quit_combo()


def test_start_and_select_on_two_pads_do_not_quit(rig):
    pads, _ = rig
    pads += [FakePad(), FakePad()]
    inp = Input()
    step(inp)
    pads[0].down, pads[1].down = {START}, {SELECT}
    step(inp)
    assert not inp.quit_combo()


def test_a_combo_already_held_at_start_up_does_not_quit_until_pressed_again(rig):
    pads, _ = rig
    pads.append(FakePad())
    pads[0].down = {START, SELECT}  # stuck, or held while the game launched
    inp = Input()
    for _ in range(120):
        step(inp)
        assert not inp.quit_combo()
    pads[0].down = set()
    step(inp)
    pads[0].down = {START, SELECT}
    step(inp)
    assert inp.quit_combo()


def test_no_pads_and_no_keys_is_quiet_for_ever(rig):
    inp = Input()
    for _ in range(600):
        f = step(inp)
        assert not f.activity and not inp.quit_combo() and not inp.keyboard_quit
        assert all(p == gp_input.PlayerInput() for p in f.players.values())


def test_a_pad_that_errors_reads_as_untouched(rig):
    pads, _ = rig
    pads.append(FakePad())
    inp = Input()

    def broken(i):
        raise pygame.error("unplugged")

    pads[0].get_button = broken
    f = step(inp)
    assert not f.activity and not inp.quit_combo()


# --- The keyboard ----------------------------------------------------------------------------


def test_p1_keys_steer_brake_and_use_items(rig):
    _, keys = rig
    inp = Input()
    keys.held = {pygame.K_s, pygame.K_d}
    p1 = step(inp).players["p1"]
    assert p1.steer == -1.0 and p1.brake == 1.0
    keys.held = {pygame.K_f, pygame.K_q}
    p1 = step(inp).players["p1"]
    assert p1.steer == 1.0 and p1.a
    assert not step(inp).players["p1"].a  # held, not pressed again


def test_p2_keys_are_the_arrows_and_full_stop(rig):
    _, keys = rig
    inp = Input()
    keys.held = {pygame.K_LEFT, pygame.K_DOWN, pygame.K_PERIOD}
    p2 = step(inp).players["p2"]
    assert p2.steer == -1.0 and p2.brake == 1.0 and p2.a
    assert step(inp).players["p1"] == gp_input.PlayerInput()


def test_the_keys_for_b_start_and_the_quit(rig):
    _, keys = rig
    inp = Input()
    keys.held = {pygame.K_w}
    assert step(inp).players["p1"].b
    keys.held = {pygame.K_2}
    assert step(inp).players["p2"].start
    keys.held = {pygame.K_1, pygame.K_3}
    step(inp)
    assert inp.quit_combo()
    keys.held = {pygame.K_ESCAPE}
    step(inp)
    assert inp.keyboard_quit


def test_a_pad_and_its_keys_merge(rig):
    pads, keys = rig
    pads.append(FakePad())
    inp = Input()
    keys.held = {pygame.K_f}
    pads[0].down = {A}
    p1 = step(inp).players["p1"]
    assert p1.steer == 1.0 and p1.a


def test_no_keyboard_ignores_every_key(rig):
    _, keys = rig
    gp_input.set_keyboard_enabled(False)
    inp = Input()
    keys.held = {pygame.K_s, pygame.K_q, pygame.K_1, pygame.K_3, pygame.K_ESCAPE}
    inp.handle(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_q))
    f = step(inp)
    assert not f.activity and not inp.quit_combo() and not inp.keyboard_quit


def test_p1_keys_avoid_the_letters_the_pad_types():
    for names in config.KEYMAP["p1"].values():
        for name in names:
            assert name not in {"K_l", "K_x", "K_r", "K_b", "K_y", "K_a"}


def test_stick_is_the_held_direction_without_repeats(rig):
    pads, _ = rig
    pads.append(FakePad())
    inp = Input()
    pads[0].axis = [0.9, -0.9]  # held up-right
    sticks = [step(inp).players["p1"].stick for _ in range(30)]
    assert set(sticks) == {(1, -1)}
    pads[0].axis = [0.3, 0.0]  # past the deadzone, not half way: no direction
    assert step(inp).players["p1"].stick == (0, 0)


def test_any_button_is_a_press_for_the_how_to_play_card(rig):
    """X, Y, L and R (raw 0, 3, 4, 5) do nothing else, but they count as a press."""
    pads, _ = rig
    pads += [FakePad(), FakePad()]
    inp = Input()
    for raw in (0, 3, 4, 5, A, START):
        pads[0].down = {raw}
        f = step(inp)
        assert f.players["p1"].button and not f.players["p2"].button, raw
        f = step(inp)
        assert not f.players["p1"].button, raw  # held, not pressed again
        pads[0].down = set()
        step(inp)
    pads[1].down = set()
    f = step(inp)
    assert not f.players["p1"].button and not f.players["p2"].button
