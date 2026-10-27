"""Pads and the keyboard, polled once per frame into a match.FrameInput.

Devices, pad layouts and the two-player keyboard are shared by all games
(arqade_common.input); each player's half of the keyboard counts as their
pad. Per pad there are two steering inputs: the stick (or the d-pad, or the
direction keys) and the four face buttons X Y B A laid out like W A S D. Which
player each one steers is the match's business (config.CONTROLS). In menus,
printed A (or Start) confirms and printed B goes back. Any button at all
(or, without --no-keyboard, any key) dismisses the HOW TO PLAY card, and
the buttons still held then are consumed until let go (consume_held), so
the press that dismissed it never steers.

The pure helpers (stick_direction, latest_direction,
should_quit) are unit tested; reading real pads is verified on the cabinet
with --input-test.
"""

from __future__ import annotations

import pygame
from arqade_common.input import PLAYERS, LastDevice, PadLayout, PadSlots, default_pad_layout, read_player

from qurves import config
from qurves.match import FrameInput
from qurves.rules import Vec

DIRECTIONS = {"up": (0, -1), "down": (0, 1), "left": (-1, 0), "right": (1, 0)}
PADS = (0, 1)
# Printed L X R / Y B A: X, Y, B, A sit like W, A, S, D.
FACE_DIRECTIONS = {"x": "up", "y": "left", "b": "down", "a": "right"}

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


def stick_direction(ax: float, ay: float, deadzone: float) -> Vec | None:
    """The stick's dominant axis past the deadzone, as a grid direction."""
    if abs(ax) <= deadzone and abs(ay) <= deadzone:
        return None
    if abs(ax) > abs(ay):
        return (1 if ax > 0 else -1, 0)
    return (0, 1 if ay > 0 else -1)


def latest_direction(order: list[str], held: set[str]) -> tuple[list[str], Vec | None]:
    """Track direction buttons in the order they went down, so holding two at
    once steers by the newer one. Returns (the updated order, the direction)."""
    order = [name for name in order if name in held]
    order += [name for name in DIRECTIONS if name in held and name not in order]
    return order, DIRECTIONS[order[-1]] if order else None


def should_quit(*, p1_start: bool, p1_select: bool, p2_start: bool, p2_select: bool) -> bool:
    """Start + Select held together on the same pad. There is deliberately no
    quit key: Esc leaves fullscreen in a browser, and the PC launcher handles
    Esc itself (it ends the game process)."""
    return (p1_start and p1_select) or (p2_start and p2_select)


class Input:
    def __init__(self, pad_layout: PadLayout | None = None) -> None:
        # Which pad is whose: pads join P1's side then P2's as they appear
        # (in a browser, only after their first button press).
        self.pads = PadSlots()
        self.pad_layout = pad_layout or default_pad_layout()
        # Keyboard or pad, per side, so on-screen hints name what they're holding.
        self.devices = LastDevice()
        self._order = {pad: [] for pad in PADS}
        self._down: dict[int, set[str]] = {pad: set() for pad in PADS}
        self._consumed: dict[int, set[str]] = {pad: set() for pad in PADS}
        self._raw: dict[int, set[str]] = {pad: set() for pad in PADS}
        self._key_pressed = False
        self._stick_prev: dict[int, Vec | None] = {pad: None for pad in PADS}
        self.stick: list[Vec | None] = [None, None]
        self.pad: list[Vec | None] = [None, None]
        self.nav: Vec | None = None
        self.confirm = self.back = self.pause = self.pick = self.any_button = False
        self.start_select = {pad: (False, False) for pad in PADS}
        self.select_held_time = 0.0
        self.activity = False
        self.pads.scan()

    def handle(self, event: pygame.event.Event) -> None:
        self.pads.handle_event(event)
        self.devices.handle_event(event, self.pads, keyboard=_keyboard_enabled)
        if event.type == pygame.KEYDOWN and _keyboard_enabled:
            self._key_pressed = True

    def consume_held(self) -> None:
        """Ignore every button held right now until it is let go."""
        for pad in PADS:
            self._consumed[pad] = set(self._raw[pad])

    def _read(self, pad: int, keys):
        """(buttons and directions held, the stick as a grid direction or None)."""
        player = PLAYERS[pad]
        try:
            state = read_player(player, keys, self.pads.pad(pad), self.pad_layout)
        except pygame.error:  # the pad went away mid-read
            state = read_player(player, keys, None, self.pad_layout)
        stick = stick_direction(state.stick_x, state.stick_y, config.INPUT_CONFIG["axis_deadzone"])
        if stick is None:  # the d-pad or the direction keys
            stick = next((vec for name, vec in DIRECTIONS.items() if state[name]), None)
        return set(state.held), stick

    def update(self, dt: float) -> None:
        keys = read_keys()
        self.activity = False
        self.confirm = self.back = self.pause = self.pick = False
        self.any_button, self._key_pressed = self._key_pressed, False
        self.nav = None
        for pad in PADS:
            raw, stick = self._read(pad, keys)
            self._raw[pad] = raw
            self._consumed[pad] &= raw
            down = raw - self._consumed[pad] - set(DIRECTIONS)
            held = {FACE_DIRECTIONS[name] for name in down if name in FACE_DIRECTIONS}
            self._order[pad], self.pad[pad] = latest_direction(self._order[pad], held)

            pressed = down - self._down[pad]
            self._down[pad] = down
            self.confirm |= bool(pressed & {"a", "start"})
            self.back |= "b" in pressed
            self.pause |= "start" in pressed
            self.pick |= "a" in pressed
            self.any_button |= bool(pressed)
            # Raw, not down: Start + Select quits even with a consumed button.
            self.start_select[pad] = ("start" in raw, "select" in raw)

            if stick is not None and stick != self._stick_prev[pad] and self.nav is None:
                self.nav = stick
            self._stick_prev[pad] = stick
            self.stick[pad] = stick
            if raw or stick is not None:
                self.activity = True

        if any(select for _start, select in self.start_select.values()):
            self.select_held_time += dt
        else:
            self.select_held_time = 0.0

    def frame_input(self) -> FrameInput:
        return FrameInput(stick=tuple(self.stick), pad=tuple(self.pad), nav=self.nav,
                          confirm=self.confirm, back=self.back, pause=self.pause, pick=self.pick,
                          any_button=self.any_button, activity=self.activity)

    def quit_combo(self) -> bool:
        (s0, sel0), (s1, sel1) = self.start_select[0], self.start_select[1]
        return should_quit(p1_start=s0, p1_select=sel0, p2_start=s1, p2_select=sel1)
