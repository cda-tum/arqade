import os

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import pygame
import pytest

from arqade_common import input as inp


class FakeKeys:
    def __init__(self, *names):
        self.down = {getattr(pygame, n) for n in names}

    def __getitem__(self, key):
        return key in self.down


class FakePad:
    def __init__(self, instance_id=0, buttons=(), axes=(0.0, 0.0), hat=None, num_buttons=16):
        self.instance_id, self.buttons, self.axes, self.hat = instance_id, set(buttons), axes, hat
        self.num_buttons = num_buttons

    def get_init(self): return True
    def init(self): pass
    def get_instance_id(self): return self.instance_id
    def get_numbuttons(self): return self.num_buttons
    def get_button(self, i): return i in self.buttons
    def get_numaxes(self): return len(self.axes)
    def get_axis(self, i): return self.axes[i]
    def get_numhats(self): return 0 if self.hat is None else 1
    def get_hat(self, i): return self.hat


def test_encoder_layout_matches_the_cabinet_convention():
    # AGENTS.md: A = 1, B = 2, Start = 9, Select = 8.
    assert inp.ENCODER.buttons["a"] == 1
    assert inp.ENCODER.buttons["b"] == 2
    assert inp.ENCODER.buttons["start"] == 9
    assert inp.ENCODER.buttons["select"] == 8


def test_every_layout_and_keyboard_names_every_button():
    for layout in inp.PAD_LAYOUTS.values():
        assert set(layout.buttons) == set(inp.BUTTONS), layout.name
    for player in inp.PLAYERS:
        assert set(inp.KEYBOARD_LAYOUT[player]) == set(inp.BUTTONS) | set(inp.DIRECTIONS)
        for key in inp.KEYBOARD_LAYOUT[player].values():
            assert hasattr(pygame, key)


def test_the_two_keyboard_players_share_no_key():
    p1, p2 = (set(inp.KEYBOARD_LAYOUT[p].values()) for p in inp.PLAYERS)
    assert not p1 & p2


def test_keyboard_only():
    state = inp.read_player("p1", FakeKeys("K_w", "K_b", "K_SPACE"), None, inp.ENCODER)
    assert state.held == {"up", "a", "start"}
    assert (state.stick_x, state.stick_y) == (0.0, 0.0)


def test_pad_buttons_follow_the_layout():
    pad = FakePad(buttons={0, 9})
    assert inp.read_player("p2", FakeKeys(), pad, inp.STANDARD).held == {"a", "start"}
    assert inp.read_player("p2", FakeKeys(), pad, inp.ENCODER).held == {"x", "start"}


def test_standard_dpad_buttons_and_xbox_hat_are_directions():
    assert inp.read_player("p1", FakeKeys(), FakePad(buttons={12, 15}), inp.STANDARD).held == {"up", "right"}
    assert inp.read_player("p1", FakeKeys(), FakePad(hat=(-1, -1)), inp.XBOX).held == {"left", "down"}


def test_stick_is_analog_and_not_a_direction():
    state = inp.read_player("p1", FakeKeys(), FakePad(axes=(0.5, -0.9)), inp.ENCODER)
    assert state.held == frozenset()
    assert (state.stick_x, state.stick_y) == (0.5, -0.9)


def test_buttons_the_pad_does_not_have_are_skipped():
    state = inp.read_player("p1", FakeKeys(), FakePad(buttons={1, 9}, num_buttons=4, axes=()), inp.ENCODER)
    assert state.held == {"a"}


class TestPadSlots:
    @pytest.fixture
    def devices(self, monkeypatch):
        """Connected devices by index, as pygame.joystick would report them."""
        connected: list[FakePad] = []
        monkeypatch.setattr(pygame.joystick, "get_count", lambda: len(connected))
        monkeypatch.setattr(pygame.joystick, "Joystick", lambda i: connected[i])
        return connected

    def added(self, index):
        return pygame.event.Event(pygame.JOYDEVICEADDED, device_index=index)

    def removed(self, instance_id):
        return pygame.event.Event(pygame.JOYDEVICEREMOVED, instance_id=instance_id)

    def test_scan_assigns_pads_in_device_order(self, devices):
        devices += [FakePad(10), FakePad(11), FakePad(12)]
        slots = inp.PadSlots()
        slots.scan()
        assert [slots.pad(0).instance_id, slots.pad(1).instance_id] == [10, 11]

    def test_added_event_for_a_scanned_pad_is_not_counted_twice(self, devices):
        devices += [FakePad(10)]
        slots = inp.PadSlots()
        slots.scan()
        slots.handle_event(self.added(0))
        assert slots.pad(0).instance_id == 10 and slots.pad(1) is None

    def test_late_pad_gets_the_first_free_slot(self, devices):
        slots = inp.PadSlots()
        slots.scan()
        assert slots.pad(0) is None
        devices += [FakePad(20)]
        slots.handle_event(self.added(0))
        assert slots.pad(0).instance_id == 20

    def test_unplugging_frees_the_slot_for_the_next_pad(self, devices):
        devices += [FakePad(10), FakePad(11)]
        slots = inp.PadSlots()
        slots.scan()
        slots.handle_event(self.removed(10))
        assert slots.pad(0) is None and slots.pad(1).instance_id == 11
        devices += [FakePad(12)]
        slots.handle_event(self.added(2))
        assert slots.pad(0).instance_id == 12


class TestLabelsAndLastDevice:
    def key(self, name):
        return pygame.event.Event(pygame.KEYDOWN, key=getattr(pygame, name))

    def button(self, instance_id, index=0):
        return pygame.event.Event(pygame.JOYBUTTONDOWN, instance_id=instance_id, button=index)

    def axis(self, instance_id, value):
        return pygame.event.Event(pygame.JOYAXISMOTION, instance_id=instance_id, axis=1, value=value)

    @pytest.fixture
    def pads(self, monkeypatch):
        connected = [FakePad(10), FakePad(11)]
        monkeypatch.setattr(pygame.joystick, "get_count", lambda: len(connected))
        monkeypatch.setattr(pygame.joystick, "Joystick", lambda i: connected[i])
        slots = inp.PadSlots()
        slots.scan()
        return slots

    def test_labels_name_the_key_or_the_printed_button(self):
        assert inp.label("start", "p1", inp.KEYBOARD) == "SPACE"
        assert inp.label("a", "p1", inp.KEYBOARD) == "B"  # the pad's A sits on the B key
        assert inp.label("select", "p2", inp.KEYBOARD) == "R-SHIFT"
        assert inp.label("up", "p2", inp.KEYBOARD) == "UP"
        assert inp.label("start", "p1", inp.PAD) == "START"
        assert inp.label("a", "p2", inp.PAD) == "A"

    def test_every_player_switches_on_their_own(self, pads):
        last = inp.LastDevice(default=inp.PAD)
        last.handle_event(self.key("K_SPACE"), pads)  # P1's key
        assert (last["p1"], last["p2"], last.latest) == (inp.KEYBOARD, inp.PAD, "p1")
        last.handle_event(self.button(11), pads)  # P2's pad
        assert (last["p1"], last["p2"], last.latest) == (inp.KEYBOARD, inp.PAD, "p2")
        last.handle_event(self.button(10), pads)  # P1 picks up their pad
        assert last["p1"] == inp.PAD

    def test_shared_labels_merge_both_players(self, pads):
        last = inp.LastDevice(default=inp.KEYBOARD)
        assert last.shared_label("start") == "SPACE / ENTER"
        last.handle_event(self.button(11), pads)
        assert last.shared_label("start") == "SPACE / START"
        last.handle_event(self.button(10), pads)
        assert last.shared_label("start") == "START"
        assert last.everyone_on(inp.PAD)

    def test_small_stick_drift_and_unassigned_pads_change_nothing(self, pads):
        last = inp.LastDevice(default=inp.KEYBOARD)
        last.handle_event(self.axis(10, 0.2), pads)
        last.handle_event(self.button(99), pads)
        assert last.everyone_on(inp.KEYBOARD)
        last.handle_event(self.axis(10, -0.9), pads)
        assert last["p1"] == inp.PAD

    def test_ignored_keyboard_and_unknown_keys_change_nothing(self, pads):
        last = inp.LastDevice(default=inp.PAD)
        last.handle_event(self.key("K_SPACE"), pads, keyboard=False)
        last.handle_event(self.key("K_F3"), pads)
        assert last.everyone_on(inp.PAD)
