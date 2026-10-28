"""Pads and the keyboard, polled once per frame into a match.FrameInput.

Devices, pad layouts and the two-player keyboard are shared by all games
(arqade_common.input); each player's half of the keyboard counts as their
pad. Per pad there are two input sources: the stick (or the d-pad, or the
direction keys) and the four face buttons X Y B A laid out like W A S D.
Each source reports which of up/down/left/right are held, and which were
newly pressed; which player a source drives is the match's business
(config.CONTROLS). In menus, printed A (or Start) confirms and printed B
goes back. Any button at all (from the events, either pad, or without
--no-keyboard any key but the direction keys) dismisses the HOW TO PLAY
card; the stick does not.

The pure helpers (stick_held, menu_direction, should_quit) are unit tested;
reading real pads is verified on the cabinet with --input-test.
"""

from __future__ import annotations

import pygame
from arqade_common.input import (KEYBOARD_LAYOUT, PLAYERS, LastDevice, PadLayout, PadSlots, default_pad_layout,
                                 read_player)

from qarrera import config
from qarrera.match import FrameInput

DIRECTIONS = {"up": (0, -1), "down": (0, 1), "left": (-1, 0), "right": (1, 0)}
PADS = (0, 1)
SOURCES = tuple((kind, pad) for pad in PADS for kind in ("stick", "pad"))
# Printed L X R / Y B A: X, Y, B, A sit like W, A, S, D.
FACE_DIRECTIONS = {"x": "up", "y": "left", "b": "down", "a": "right"}
_DIRECTION_NAMES = frozenset(DIRECTIONS)
# The keys that stand in for a stick: like the stick, they don't dismiss HOW TO PLAY.
_DIRECTION_KEYS = {getattr(pygame, keys[d]) for keys in KEYBOARD_LAYOUT.values() for d in DIRECTIONS}

# Batocera's evmapy turns P1's pad into keystrokes too (see ../../../AGENTS.md),
# so the cabinet loader passes --no-keyboard and only the pads are read.
_keyboard_enabled = True


def set_keyboard_enabled(enabled: bool) -> None:
    global _keyboard_enabled
    _keyboard_enabled = enabled


class _NoKeys:
    """Stands in for pygame.key.get_pressed() while the keyboard is off."""

    def __getitem__(self, key: int) -> bool:
        return False


def read_keys():
    return pygame.key.get_pressed() if _keyboard_enabled else _NoKeys()


def stick_held(ax: float, ay: float, deadzone: float) -> set[str]:
    """Every direction the stick is pushed past the deadzone: up-right is
    faster and a wire change at once."""
    held = set()
    if ay < -deadzone:
        held.add("up")
    elif ay > deadzone:
        held.add("down")
    if ax < -deadzone:
        held.add("left")
    elif ax > deadzone:
        held.add("right")
    return held


def menu_direction(pressed: set[str]) -> tuple[int, int] | None:
    """One menu step from newly pressed directions; vertical wins a diagonal."""
    for name in ("up", "down", "left", "right"):
        if name in pressed:
            return DIRECTIONS[name]
    return None


def should_quit(*, p1_start: bool, p1_select: bool, p2_start: bool, p2_select: bool) -> bool:
    """Start + Select held together on the same pad. There is deliberately no
    quit key: Esc leaves fullscreen in a browser, and the PC launcher handles
    Esc itself (it ends the game process)."""
    return (p1_start and p1_select) or (p2_start and p2_select)


class Input:
    def __init__(self, pad_layout: PadLayout | None = None) -> None:
        # Which pad is whose: pads join the left side then the right as they
        # appear (in a browser, only after their first button press).
        self.pads = PadSlots()
        self.pad_layout = pad_layout or default_pad_layout()
        # Keyboard or pad, per side, so on-screen hints name what each side holds.
        self.devices = LastDevice()
        self._dpad_buttons = set(self.pad_layout.dpad_buttons.values())
        self._down: dict[int, set[str]] = {pad: set() for pad in PADS}
        self._held_prev: dict = {src: set() for src in SOURCES}
        self.held: dict = {src: set() for src in SOURCES}
        self.pressed: dict = {src: set() for src in SOURCES}
        self.nav: tuple[int, int] | None = None
        self.confirm = self.back = self.pause = self.pick = False
        self.pad_a = [False, False]
        self.pad_b = [False, False]
        self.start_select = {pad: (False, False) for pad in PADS}
        self.activity = False
        self.any_button = False
        self._hit = False  # a button or key went down since the last update
        self.pads.scan()

    def handle(self, event: pygame.event.Event) -> None:
        self.pads.handle_event(event)
        self.devices.handle_event(event, self.pads, keyboard=_keyboard_enabled)
        # From the events, so even a tap shorter than a frame counts.
        if event.type == pygame.JOYBUTTONDOWN and event.button not in self._dpad_buttons:
            self._hit = True
        elif event.type == pygame.KEYDOWN and _keyboard_enabled and event.key not in _DIRECTION_KEYS:
            self._hit = True

    def _read(self, pad: int, keys) -> tuple[set[str], set[str]]:
        """(the buttons held, the directions the stick, d-pad or direction keys hold)."""
        player = PLAYERS[pad]
        try:
            state = read_player(player, keys, self.pads.pad(pad), self.pad_layout)
        except pygame.error:  # the pad went away mid-read
            state = read_player(player, keys, None, self.pad_layout)
        stick = stick_held(state.stick_x, state.stick_y, config.INPUT_CONFIG["axis_deadzone"])
        stick |= state.held & _DIRECTION_NAMES
        return set(state.held - _DIRECTION_NAMES), stick

    def update(self, dt: float) -> None:
        keys = read_keys()
        self.activity = False
        self.confirm = self.back = self.pause = self.pick = False
        self.pad_a = [False, False]
        self.pad_b = [False, False]
        self.nav = None
        for pad in PADS:
            buttons, stick = self._read(pad, keys)
            face = {FACE_DIRECTIONS[name] for name in buttons if name in FACE_DIRECTIONS}
            for src, held in ((("stick", pad), stick), (("pad", pad), face)):
                self.pressed[src] = held - self._held_prev[src]
                self.held[src] = held
                self._held_prev[src] = held
            if self.nav is None:
                self.nav = menu_direction(self.pressed[("stick", pad)])

            pressed = buttons - self._down[pad]
            self._down[pad] = buttons
            self.confirm |= bool(pressed & {"a", "start"})
            self.back |= "b" in pressed
            self.pause |= "start" in pressed
            self.pick |= "a" in pressed
            self.pad_a[pad] = "a" in pressed
            self.pad_b[pad] = "b" in pressed
            self.start_select[pad] = ("start" in buttons, "select" in buttons)
            if buttons or stick:
                self.activity = True
        self.any_button, self._hit = self._hit, False
        self.activity |= self.any_button

    def frame_input(self) -> FrameInput:
        return FrameInput(held={k: frozenset(v) for k, v in self.held.items()},
                          pressed={k: frozenset(v) for k, v in self.pressed.items()},
                          nav=self.nav, confirm=self.confirm, back=self.back, pause=self.pause,
                          pick=self.pick, activity=self.activity,
                          pad_a=tuple(self.pad_a), pad_b=tuple(self.pad_b), any_button=self.any_button)

    def quit_combo(self) -> bool:
        (s0, sel0), (s1, sel1) = self.start_select[0], self.start_select[1]
        return should_quit(p1_start=s0, p1_select=sel0, p2_start=s1, p2_select=sel1)
