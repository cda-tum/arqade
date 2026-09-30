"""Translate pygame keyboard/joystick events into logical per-player actions.

Event driven: each action is held while any of its sources (a key, a
joystick button, an axis, the hat) is down. The pure decision functions
(axis_to_direction, should_quit) and Pad's press/auto-repeat logic are unit
tested; the event plumbing needs real devices and is verified by running it.
"""

from __future__ import annotations

import pygame

from ion_surfer.config import INPUT_CONFIG, KEYMAP, SELECT_KEYS

PLAYERS = ("p1", "p2")  # pad 0, pad 1


# Batocera's pygame system runs evmapy, which turns player 1's pad into
# keyboard presses (d-pad -> arrow keys, a/b/x/y -> A/B/X/Y, start -> Enter,
# select -> Space, ...). Those fake keys collide with the dev keyboard layout
# (P1's stick moving P2, one button firing two actions), so the cabinet
# loader passes --no-keyboard and only the joysticks are read.
_keyboard_enabled = True


def set_keyboard_enabled(enabled: bool) -> None:
    global _keyboard_enabled
    _keyboard_enabled = enabled


def keyboard_enabled() -> bool:
    return _keyboard_enabled


class _NoKeys:
    """Stands in for pygame.key.get_pressed() while the keyboard is off."""

    def __getitem__(self, key: int) -> bool:
        return False


def read_keys():
    """pygame.key.get_pressed(), or an all-released stand-in with --no-keyboard."""
    return pygame.key.get_pressed() if _keyboard_enabled else _NoKeys()


def axis_to_direction(axis_value: float, deadzone: float) -> int:
    if axis_value < -deadzone:
        return -1
    if axis_value > deadzone:
        return 1
    return 0


def should_quit(*, p1_start: bool, p1_select: bool, p2_start: bool, p2_select: bool) -> bool:
    return (p1_start and p1_select) or (p2_start and p2_select)


def key_codes(names: list[str]) -> list[int]:
    return [getattr(pygame, name) for name in names]


def keyboard_quit_held(keys: pygame.key.ScancodeWrapper) -> bool:
    key_name = INPUT_CONFIG["system"]["keyboard_quit"]
    return bool(keys[getattr(pygame, key_name)])


class Pad:
    DIRS = ("left", "right", "up", "down")

    def __init__(self):
        self.src = {a: set() for a in ("left", "right", "up", "down", "a", "start", "select", "remove_ion", "add_ion", "cool", "passive_cool")}
        self.pressed = set()
        self.rep = {d: 0.0 for d in self.DIRS}

    def held(self, act):
        return bool(self.src[act])

    def set(self, act, source, on):
        was = self.held(act)
        if on:
            self.src[act].add(source)
        else:
            self.src[act].discard(source)
        if on and not was:
            self.pressed.add(act)
            if act in self.rep:
                self.rep[act] = 0.28

    def update(self, dt):
        for d in self.DIRS:
            if self.held(d):
                self.rep[d] -= dt
                if self.rep[d] <= 0:
                    self.pressed.add(d)
                    self.rep[d] = 0.09


class Controls:
    def __init__(self):
        self.pads = [Pad(), Pad()]
        self.select = False
        self.joys = {}  # instance id -> (joystick, pad index)
        self.keymap = {pi: {act: key_codes(names) for act, names in m.items()} for pi, m in KEYMAP.items()}
        self.select_keys = key_codes(SELECT_KEYS)

    def begin_frame(self):
        for p in self.pads:
            p.pressed.clear()
        self.select = False

    def any_pressed(self, act):
        return any(act in p.pressed for p in self.pads)

    def quit_combo(self):
        a, b = self.pads
        return should_quit(
            p1_start=a.held("start"), p1_select=a.held("select"),
            p2_start=b.held("start"), p2_select=b.held("select"),
        )

    def _joy_pad(self, e):
        entry = self.joys.get(e.instance_id)
        return None if entry is None else self.pads[entry[1]]

    def handle(self, e):
        if e.type in (pygame.KEYDOWN, pygame.KEYUP):
            if not _keyboard_enabled:
                return
            on = e.type == pygame.KEYDOWN
            if on and e.key in self.select_keys:
                self.select = True
            for pi, m in self.keymap.items():
                for act, keys in m.items():
                    if e.key in keys:
                        self.pads[pi].set(act, ("k", e.key), on)
        elif e.type == pygame.JOYDEVICEADDED:
            for pi, pk in enumerate(PLAYERS):
                if INPUT_CONFIG[pk]["joystick_index"] == e.device_index:
                    j = pygame.joystick.Joystick(e.device_index)
                    self.joys[j.get_instance_id()] = (j, pi)
        elif e.type == pygame.JOYDEVICEREMOVED:
            self.joys.pop(e.instance_id, None)
        elif e.type in (pygame.JOYBUTTONDOWN, pygame.JOYBUTTONUP):
            pad = self._joy_pad(e)
            if pad is None:
                return
            on = e.type == pygame.JOYBUTTONDOWN
            system = INPUT_CONFIG["system"]
            cfg = INPUT_CONFIG[PLAYERS[self.pads.index(pad)]]
            if e.button == system["select_button"]:
                pad.set("select", ("jb", e.button), on)
                if on:
                    self.select = True
            elif e.button == system["start_button"]:
                pad.set("start", ("jb", e.button), on)
            else:
                for act, buttons in cfg["buttons"].items():
                    if e.button in buttons:
                        pad.set(act, ("jb", e.button), on)
        elif e.type == pygame.JOYAXISMOTION:
            pad = self._joy_pad(e)
            if pad is None:
                return
            ax_x, ax_y = INPUT_CONFIG[PLAYERS[self.pads.index(pad)]]["axes"]
            d = axis_to_direction(e.value, INPUT_CONFIG["axis_deadzone"])
            if e.axis == ax_x:
                pad.set("left", "jax", d < 0)
                pad.set("right", "jax", d > 0)
            elif e.axis == ax_y:
                pad.set("up", "jay", d < 0)
                pad.set("down", "jay", d > 0)
        elif e.type == pygame.JOYHATMOTION:
            pad = self._joy_pad(e)
            if pad is None or e.hat != INPUT_CONFIG[PLAYERS[self.pads.index(pad)]]["hat_index"]:
                return
            hx, hy = e.value
            pad.set("left", "hat", hx < 0)
            pad.set("right", "hat", hx > 0)
            pad.set("up", "hat", hy > 0)
            pad.set("down", "hat", hy < 0)

    def update(self, dt):
        for p in self.pads:
            p.update(dt)
