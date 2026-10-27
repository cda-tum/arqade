"""Pads and the keyboard, polled once per frame into a match.FrameInput.

Devices, pad layouts and the keyboard layout are shared by all games (see
arqade_common.input). Per player: the stick moves the pill left and right
(auto-repeated) and soft-drops it when pushed down; A rotates clockwise and B
anti-clockwise. In menus the stick navigates (auto-repeated, per player), A
(or Start) confirms and B goes back, each per player, so both can set up at
once. The pure helpers are unit tested; reading real pads is verified on the
cabinet with --input-test.
"""

from __future__ import annotations

import pygame
from arqade_common.input import (
    PLAYERS as _PAD_PLAYERS,
    LastDevice,
    PadLayout,
    PadSlots,
    default_pad_layout,
    read_player,
)

from gate_drop import config
from gate_drop.board import PlayerInput
from gate_drop.match import PLAYERS, FrameInput

# Batocera's evmapy turns P1's pad into keystrokes too (see ../../../AGENTS.md),
# so the cabinet loader passes --no-keyboard and only the pads are read.
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
    return pygame.key.get_pressed() if _keyboard_enabled else _NoKeys()


# Which pad is whose, and how to read its buttons. main() calls
# set_pad_layout() and start_devices() once at start-up.
_pads = PadSlots()
_pad_layout = default_pad_layout()
# Keyboard or pad, per player, so on-screen hints name what they're holding.
_last_device = LastDevice()


def set_pad_layout(layout: PadLayout) -> None:
    global _pad_layout
    _pad_layout = layout


def start_devices() -> None:
    """Pick up the pads already connected (call after pygame.joystick.init())."""
    _pads.scan()


def get_events() -> list[pygame.event.Event]:
    """pygame.event.get(), noting pads that connect or disconnect on the way.
    Every event loop in the game uses this instead of pygame.event.get():
    in a browser, a gamepad only appears after its first button press."""
    events = pygame.event.get()
    for event in events:
        _pads.handle_event(event)
        _last_device.handle_event(event, _pads, keyboard=_keyboard_enabled)
    return events


def last_device() -> LastDevice:
    """Who last used their keys or their pad, for the screens' button hints."""
    return _last_device


def axis_sign(value: float, deadzone: float) -> int:
    if value < -deadzone:
        return -1
    if value > deadzone:
        return 1
    return 0


def should_quit(*, p1_start: bool, p1_select: bool, p2_start: bool, p2_select: bool) -> bool:
    """Start + Select held together on the same pad."""
    return (p1_start and p1_select) or (p2_start and p2_select)


class AutoRepeat:
    """Turns a held direction (-1, 0 or 1) into presses: one at once, then
    one after REPEAT_DELAY, then one every REPEAT_INTERVAL."""

    def __init__(self, delay: float = config.REPEAT_DELAY, interval: float = config.REPEAT_INTERVAL) -> None:
        self.delay, self.interval = delay, interval
        self.held = 0
        self.timer = 0.0

    def update(self, dt: float, value: int) -> int:
        if value == 0:
            self.held = 0
            return 0
        if value != self.held:
            self.held = value
            self.timer = self.delay
            return value
        self.timer -= dt
        if self.timer <= 0:
            self.timer += self.interval
            return value
        return 0


_BUTTONS = ("a", "b", "x", "y", "l", "r", "start", "select")


class Input:
    def __init__(self) -> None:
        self.repeat_x = {p: AutoRepeat() for p in PLAYERS}
        self.repeat_y = {p: AutoRepeat() for p in PLAYERS}
        self._down: dict[str, set[str]] = {p: set() for p in PLAYERS}
        self.pads = _pads
        self.frame = FrameInput()
        self.start_select = {p: (False, False) for p in PLAYERS}
        self.select_held_time = 0.0
        self._key_pressed = False  # a KEYDOWN since the last update

    def handle(self, event: pygame.event.Event) -> None:
        if event.type == pygame.KEYDOWN and _keyboard_enabled:
            self._key_pressed = True

    def update(self, dt: float) -> None:
        keys = read_keys()
        frame = FrameInput(any_button=self._key_pressed)
        self._key_pressed = False
        deadzone = config.AXIS_DEADZONE
        for slot, p in enumerate(_PAD_PLAYERS):
            state = read_player(p, keys, self.pads.pad(slot), _pad_layout)
            dx = axis_sign(state.stick_x, deadzone) or (state["right"] - state["left"])
            dy = axis_sign(state.stick_y, deadzone) or (state["down"] - state["up"])
            down = {b for b in _BUTTONS if state[b]}
            pressed = down - self._down[p]
            self._down[p] = down
            move = self.repeat_x[p].update(dt, dx)
            frame.players[p] = PlayerInput(move, "a" in pressed, "b" in pressed, dy > 0)
            frame.nav[p] = (move, self.repeat_y[p].update(dt, dy))
            frame.confirms[p] = bool(pressed & {"a", "start"})
            frame.backs[p] = "b" in pressed
            frame.pauses[p] = "start" in pressed
            frame.any_button |= bool(pressed)
            self.start_select[p] = ("start" in down, "select" in down)
            if state.held or dx or dy:
                frame.activity = True
        self.frame = frame
        if any(select for _start, select in self.start_select.values()):
            self.select_held_time += dt
        else:
            self.select_held_time = 0.0

    def frame_input(self) -> FrameInput:
        return self.frame

    def quit_combo(self) -> bool:
        (s1, sel1), (s2, sel2) = self.start_select["p1"], self.start_select["p2"]
        return should_quit(p1_start=s1, p1_select=sel1, p2_start=s2, p2_select=sel2)
