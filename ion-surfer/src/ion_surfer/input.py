"""Translate pygame keyboard/joystick events into logical per-player actions.

Event driven: each action is held while any of its sources (a key, a
joystick button, an axis, the hat) is down. The pure decision functions
(axis_to_direction, should_quit) and Pad's press/auto-repeat logic are unit
tested; the event plumbing needs real devices and is verified by running it.
"""

from __future__ import annotations

import pygame

from ion_surfer.config import INPUT_CONFIG, KEYMAP, PAUSE_KEYS

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

    # Every action a pad can carry, derived from the config rather than
    # written out again here. This list used to be a hand-maintained copy of
    # INPUT_CONFIG, and the moment the two disagreed -- a "confirm" action
    # added to the config but not to the list -- the first press of that
    # button raised KeyError and took the whole game down mid-play.
    ACTIONS = tuple(dict.fromkeys(
        [act for player in PLAYERS for act in INPUT_CONFIG[player]["buttons"]]
        + [act for mapping in KEYMAP.values() for act in mapping]
        + ["start", "select"]
    ))

    def __init__(self):
        self.src = {a: set() for a in self.ACTIONS}
        self.pressed = set()
        self.rep = {d: 0.0 for d in self.DIRS}
        self.consumed = set()  # (action, source) used up until released, see consume_buttons

    def consume_buttons(self):
        """Every button or key held right now stops counting until it is
        released, as if it had never been pressed. The stick is left alone
        (it can't dismiss anything, so holding it is meant), and so are
        Start and Select, so the quit combo still works with them held."""
        for act, sources in self.src.items():
            if act in ("start", "select"):
                continue
            for source in [s for s in sources if isinstance(s, tuple)]:
                sources.discard(source)
                self.consumed.add((act, source))
        self.pressed.clear()

    def held(self, act):
        # .get, not [act]: an unknown action is "not held", never a crash.
        return bool(self.src.get(act))

    def set(self, act, source, on):
        if (act, source) in self.consumed:
            if not on:
                self.consumed.discard((act, source))
            return
        was = self.held(act)
        sources = self.src.setdefault(act, set())
        if on:
            sources.add(source)
        else:
            sources.discard(source)
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
        self.pause_key = False  # keyboard-only pause key (Esc) pressed this frame
        self.any_button = False  # any joystick button (or, with the keyboard on, key) went down
        self.joys = {}  # instance id -> (joystick, pad index)
        self.keymap = {pi: {act: key_codes(names) for act, names in m.items()} for pi, m in KEYMAP.items()}
        self.pause_keys = key_codes(PAUSE_KEYS)

    def begin_frame(self):
        for p in self.pads:
            p.pressed.clear()
        self.pause_key = False
        self.any_button = False

    def consume_buttons(self):
        for p in self.pads:
            p.consume_buttons()

    def any_pressed(self, act):
        return any(act in p.pressed for p in self.pads)

    def pause_pressed(self):
        """Start on either pad (or the keyboard's Esc) pauses and resumes.
        Select never does: it is reserved for the Start + Select quit combo."""
        return self.any_pressed("start") or self.pause_key

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
            self.any_button |= on
            if on and e.key in self.pause_keys:
                self.pause_key = True
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
            # any button at all, mapped or not, on any pad: the HOW TO PLAY
            # card is dismissed with it
            self.any_button |= e.type == pygame.JOYBUTTONDOWN
            pad = self._joy_pad(e)
            if pad is None:
                return
            on = e.type == pygame.JOYBUTTONDOWN
            system = INPUT_CONFIG["system"]
            cfg = INPUT_CONFIG[PLAYERS[self.pads.index(pad)]]
            if e.button == system["select_button"]:
                pad.set("select", ("jb", e.button), on)
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
