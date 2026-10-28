"""Pads and the keyboard, polled once per display frame.

Devices, pad layouts and the two-player keyboard are shared by all games (see
arqade_common.input). Per player: the analog stick (deadzoned; the d-pad and the
direction keys count too) and the A, B, X and Y buttons as edge-triggered presses.
Start confirms, pauses and starts; Select only joins Start for the quit combo. Any
button at all (L, R and Select too) going down is `any_button`, which takes the HOW
TO PLAY card away; with the keyboard on, so does any key but the stick's. The pure
helpers are unit tested; reading real pads is verified on the cabinet with
--input-test.
"""

from __future__ import annotations

import pygame
from arqade_common.input import KEYBOARD_LAYOUT, LastDevice, PadLayout, PadSlots, default_pad_layout, read_player

from . import config
from .fighter import FighterInput
from .match import FrameInput

PLAYERS = ("p1", "p2")      # pad slot 0, pad slot 1
DIRECTIONS = ("left", "right", "up", "down")
BUTTONS = ("a", "b", "x", "y", "l", "r", "start", "select")

# The stick's vertical axis needs a firmer push than the horizontal one, so a
# walk never accidentally jumps or crouches.
VERTICAL_THRESHOLD = 0.5

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


def nav_push(prev: tuple[int, int], now: tuple[int, int]) -> tuple[int, int]:
    """A menu step: each stick direction counts once, when it is pushed (no auto-repeat)."""
    return tuple(v if v and v != was else 0 for was, v in zip(prev, now))


# --- pure helpers ----------------------------------------------------------------------


def deadzone(value: float, dz: float = config.AXIS_DEADZONE) -> int:
    """-1, 0 or 1: the axis value, zero inside the deadzone."""
    if value <= -dz:
        return -1
    if value >= dz:
        return 1
    return 0


def vertical(value: float, threshold: float = VERTICAL_THRESHOLD) -> tuple[bool, bool]:
    """(up, down) from the vertical axis, where negative is up (SDL's convention)."""
    return value <= -threshold, value >= threshold


def edge_presses(prev: set, now: set) -> set:
    """What went down since the last poll."""
    return now - prev


def should_quit(*, p1_start: bool, p1_select: bool, p2_start: bool, p2_select: bool) -> bool:
    """Start + Select held together on the same pad. There is deliberately no quit
    key: Esc leaves fullscreen in a browser, and the PC launcher handles Esc itself."""
    return (p1_start and p1_select) or (p2_start and p2_select)


class Input:
    def __init__(self, pad_layout: PadLayout | None = None) -> None:
        # Which pad is whose: pads join P1 then P2 as they appear (in a browser,
        # only after their first button press).
        self.pads = PadSlots()
        self.pad_layout = pad_layout or default_pad_layout()
        # Keyboard or pad, per player, so the on-screen hints name what they hold.
        self.devices = LastDevice()
        self._down: dict[str, set[str]] = {p: set() for p in PLAYERS}
        self._stick_prev: dict[str, tuple[int, int]] = {p: (0, 0) for p in PLAYERS}
        self.frame = FrameInput()
        self.start_select = {p: (False, False) for p in PLAYERS}
        self.select_held_time = 0.0     # seconds Select has been held on either pad
        self._button_event = False      # a JOYBUTTONDOWN (or, with the keyboard on, a KEYDOWN)
        self._stick_keys = {getattr(pygame, KEYBOARD_LAYOUT[p][d]) for p in PLAYERS for d in DIRECTIONS}
        self.pads.scan()

    def handle(self, event: pygame.event.Event) -> None:
        self.pads.handle_event(event)
        self.devices.handle_event(event, self.pads, keyboard=_keyboard_enabled)
        if event.type == pygame.JOYBUTTONDOWN or (event.type == pygame.KEYDOWN and _keyboard_enabled
                                                   and event.key not in self._stick_keys):
            self._button_event = True

    def _state(self, slot: int, player: str, keys):
        """One player's keys and pad (arqade_common's PlayerState)."""
        try:
            return read_player(player, keys, self.pads.pad(slot), self.pad_layout)
        except pygame.error:            # the pad went away mid-read
            return read_player(player, keys, None, self.pad_layout)

    def update(self, dt: float) -> None:
        keys = read_keys()
        frame = FrameInput(any_button=self._button_event)
        self._button_event = False
        for slot, p in enumerate(PLAYERS):
            state = self._state(slot, p, keys)
            dx = deadzone(state.stick_x) or (state["right"] - state["left"])
            up, dn = vertical(state.stick_y)
            up, dn = up or state["up"], dn or state["down"]
            down = {b for b in BUTTONS if state[b]}
            pressed = edge_presses(self._down[p], down)
            self._down[p] = down
            a, start = "a" in pressed, "start" in pressed
            frame.fighters[p] = FighterInput(dx=dx, up=up, down=dn, a=a, b="b" in pressed, x="x" in pressed,
                                             y="y" in pressed)
            frame.confirms[p] = a or start
            frame.backs[p] = "b" in pressed
            frame.pauses[p] = start
            frame.nav[p] = nav_push(self._stick_prev[p], (dx, dn - up))
            self._stick_prev[p] = (dx, dn - up)
            if down:
                frame.held = True
            if pressed:
                frame.any_button = True
            self.start_select[p] = ("start" in down, "select" in down)
            if state.held or dx or up or dn:
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
