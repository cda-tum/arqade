"""Translate raw pygame joystick/keyboard state into logical actions.

Devices, pad layouts and the two-player keyboard are shared by all games
(arqade_common.input). In play A fires and B switches color; in the menus
A picks, B or Select goes back and Start goes on (and pauses).

The pure decision functions (axis_to_direction, pressed_edge, should_quit) are
unit tested. Reading actual device state needs pygame + hardware/SDL and is
exercised by manual/headless smoke testing only.
"""

from __future__ import annotations

import pygame

from arqade_common.input import (
    KEYBOARD_LAYOUT,
    LastDevice,
    PadLayout,
    PadSlots,
    default_pad_layout,
    read_player,
)

from error_invaders.config import INPUT_CONFIG

ACTIONS = ("left", "right", "up", "down", "fire", "swap")
PLAYERS = ("p1", "p2")


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


def pressed_edge(previous: bool, current: bool) -> bool:
    """True only on the frame a button transitions from not-held to held."""
    return current and not previous


def should_quit(*, p1_start: bool, p1_select: bool, p2_start: bool, p2_select: bool) -> bool:
    """Start + Select held together by one player. There is deliberately no
    quit key: Esc leaves fullscreen in a browser, and the PC launcher handles
    Esc itself (it ends the game process)."""
    return (p1_start and p1_select) or (p2_start and p2_select)


# Which of a player's buttons each action is (directions are themselves).
ACTION_BUTTONS = {"left": "left", "right": "right", "up": "up", "down": "down", "fire": "a", "swap": "b"}


def key_codes(names: list[str]) -> list[int]:
    return [getattr(pygame, name) for name in names]


KEYS = {p: {act: key_codes([KEYBOARD_LAYOUT[p][b]]) for act, b in ACTION_BUTTONS.items()} for p in PLAYERS}
START_KEYS = key_codes([KEYBOARD_LAYOUT[p]["start"] for p in PLAYERS])
SELECT_KEYS = key_codes([KEYBOARD_LAYOUT[p]["select"] for p in PLAYERS])


class _HeldOrTapped:
    """Keys held now, or pressed since the last frame: a tap shorter than a
    frame still counts."""

    def __init__(self, keys, ev_keys):
        self.keys, self.ev_keys = keys, ev_keys

    def __getitem__(self, key: int) -> bool:
        return bool(self.keys[key]) or key in self.ev_keys


class Input:
    """Keyboard + joysticks, with edge detection."""

    def __init__(self, pad_layout: PadLayout | None = None):
        # Which pad is whose: pads join P1 then P2 as they appear (in a
        # browser, only after their first button press).
        self.pads = PadSlots()
        self.pad_layout = pad_layout or default_pad_layout()
        # Keyboard or pad, per player, so on-screen hints name what they're holding.
        self.devices = LastDevice()
        self.held = {p: set() for p in PLAYERS}
        self.prev = {p: set() for p in PLAYERS}
        self.pressed = {p: set() for p in PLAYERS}
        self.raw = {p: set() for p in PLAYERS}
        self.blocked = {p: set() for p in PLAYERS}  # see swallow()
        self.ev_keys = set()
        self.last_keys = []
        self.confirm = self.back = self.pause = False
        self.any_button = False  # any new button press this frame, any pad
        self.back_held = 0.0
        self.quit_combo = False
        self.pads.scan()

    @property
    def joys(self):
        """Every connected joystick by device index (for the input test)."""
        return {i: pygame.joystick.Joystick(i) for i in range(pygame.joystick.get_count())}

    def handle(self, e):
        self.pads.handle_event(e)
        self.devices.handle_event(e, self.pads, keyboard=_keyboard_enabled)
        buttons = self.pad_layout.buttons
        if e.type == pygame.KEYDOWN:
            self.last_keys = (self.last_keys + [pygame.key.name(e.key)])[-8:]
            if not _keyboard_enabled:
                return
            self.ev_keys.add(e.key)
            self.any_button = True
            if e.key in START_KEYS:
                self.confirm = self.pause = True
            if e.key in SELECT_KEYS:
                self.back = True
        elif e.type == pygame.JOYBUTTONDOWN:
            self.any_button = True
            if e.button == buttons["start"]:
                self.confirm = self.pause = True
            if e.button == buttons["select"]:
                self.back = True

    def _read(self, p, keys):
        """(actions held, Start held, Select held) from p's keys and pad."""
        pad = self.pads.pad(PLAYERS.index(p))
        try:
            state = read_player(p, keys, pad, self.pad_layout)
        except pygame.error:  # the pad went away mid-read
            state = read_player(p, keys, None, self.pad_layout)
        out = {act for act, b in ACTION_BUTTONS.items() if state[b]}
        deadzone = INPUT_CONFIG["axis_deadzone"]
        dx, dy = axis_to_direction(state.stick_x, deadzone), axis_to_direction(state.stick_y, deadzone)
        if dx < 0: out.add("left")
        if dx > 0: out.add("right")
        if dy < 0: out.add("up")
        if dy > 0: out.add("down")
        return out, state["start"], state["select"]

    def update(self, dt):
        keys = _HeldOrTapped(read_keys(), self.ev_keys)
        start_select = {}
        for p in PLAYERS:
            h, start, select = self._read(p, keys)
            start_select[p] = (start, select)
            self.raw[p] = h
            self.blocked[p] &= h  # let go: counts again on the next press
            h = h - self.blocked[p]
            self.pressed[p] = h - self.prev[p]
            for act in ACTIONS:
                if act not in self.blocked[p] and any(k in self.ev_keys for k in KEYS[p][act]):
                    self.pressed[p].add(act)
            self.held[p] = h
            self.prev[p] = h
        self.quit_combo = should_quit(
            p1_start=start_select["p1"][0], p1_select=start_select["p1"][1],
            p2_start=start_select["p2"][0], p2_select=start_select["p2"][1],
        )
        # hold "back" (Select) to quit from the first menu page
        back_down = any(select for _start, select in start_select.values())
        self.back_held = self.back_held + dt if back_down else 0.0

    def swallow(self):
        """Treat the fire/swap buttons held right now as already used: they
        do nothing until they are let go. For the press that leaves the
        HOW TO PLAY card, so it doesn't fire or switch color as well."""
        for p in PLAYERS:
            self.blocked[p] = self.raw[p] & {"fire", "swap"}
            self.held[p] -= self.blocked[p]
            self.pressed[p] -= self.blocked[p]

    def end_frame(self):
        self.ev_keys.clear()
        self.confirm = self.back = self.pause = self.any_button = False

    def down(self, p, a): return a in self.held[p]
    def hit(self, p, a): return a in self.pressed[p]
    def any_hit(self, a): return self.hit("p1", a) or self.hit("p2", a)
