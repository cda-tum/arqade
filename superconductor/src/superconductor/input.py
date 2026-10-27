"""Translate raw pygame joystick/keyboard state into logical actions.

Devices, pad layouts and the two-player keyboard are shared by all games
(arqade_common.input). In a match A (or R) goes to the next pair, L to the
previous one, B to the other end and X undoes a step; Start confirms and
pauses, Select goes back.

The pure decision functions (stick_direction, DirectionRepeater, should_quit)
are unit tested. Reading actual device state needs pygame + hardware/SDL and
is exercised by manual/headless smoke testing only.
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

from superconductor.config import INPUT_CONFIG, REPEAT_DELAY, REPEAT_INTERVAL

BUTTON_ACTIONS = ("next", "other", "undo", "prev")
DIRECTIONS = ("up", "down", "left", "right")
PLAYERS = ("p1", "p2")


# Batocera's pygame system runs evmapy, which turns player 1's pad into
# keyboard presses as well (see ../AGENTS.md), so the cabinet loader passes
# --no-keyboard and only the joysticks are read.
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


def stick_direction(ax: float, ay: float, deadzone: float) -> str | None:
    """One of the four directions, by whichever axis is pushed further.

    The chip only has horizontal and vertical couplers, so a diagonal push
    resolves to its dominant axis instead of doing nothing.
    """
    if max(abs(ax), abs(ay)) <= deadzone:
        return None
    if abs(ax) > abs(ay):
        return "left" if ax < 0 else "right"
    return "up" if ay < 0 else "down"


class DirectionRepeater:
    """Fires once when a direction is pushed, then auto-repeats while held."""

    def __init__(self, delay: float = REPEAT_DELAY, interval: float = REPEAT_INTERVAL):
        self.delay = delay
        self.interval = interval
        self.held: str | None = None
        self.timer = 0.0

    def update(self, direction: str | None, dt: float) -> str | None:
        if direction != self.held:
            self.held = direction
            self.timer = self.delay
            return direction
        if direction is None:
            return None
        self.timer -= dt
        if self.timer <= 0:
            self.timer += self.interval
            return direction
        return None


def should_quit(*, p1_start: bool, p1_select: bool, p2_start: bool, p2_select: bool) -> bool:
    """Start + Select held together by one player. There is deliberately no
    quit key: Esc leaves fullscreen in a browser, and the PC launcher handles
    Esc itself (it ends the game process)."""
    return (p1_start and p1_select) or (p2_start and p2_select)


# The pad's printed buttons behind each action.
ACTION_BUTTONS = {
    "next": ("a", "r"),  # next station
    "other": ("b",),     # other end of the same pair
    "undo": ("x",),      # take back the last step
    "prev": ("l",),      # previous station
}


def key_codes(names: list[str]) -> list[int]:
    return [getattr(pygame, name) for name in names]


# Each player's keys, per direction and per action, from the shared layout.
KEY_CODES = {p: {**{d: key_codes([KEYBOARD_LAYOUT[p][d]]) for d in DIRECTIONS},
                 **{act: key_codes([KEYBOARD_LAYOUT[p][b] for b in bs]) for act, bs in ACTION_BUTTONS.items()}}
             for p in PLAYERS}
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
    """Keyboard + joysticks, with edge detection and stick auto-repeat.

    Per frame, per player: `move[p]` is the direction to step this frame (or
    None) and `pressed[p]` the button actions that went down this frame.
    """

    def __init__(self, pad_layout: PadLayout | None = None):
        # Which pad is whose: pads join P1 then P2 as they appear (in a
        # browser, only after their first button press).
        self.pads = PadSlots()
        self.pad_layout = pad_layout or default_pad_layout()
        # Keyboard or pad, per player, so on-screen hints name what they're holding.
        self.devices = LastDevice()
        self.repeaters = {p: DirectionRepeater() for p in PLAYERS}
        self.move: dict[str, str | None] = {p: None for p in PLAYERS}
        self.dir: dict[str, str | None] = {p: None for p in PLAYERS}
        self.prev_buttons: dict[str, set[str]] = {p: set() for p in PLAYERS}
        self.pressed: dict[str, set[str]] = {p: set() for p in PLAYERS}
        self.last_key_dir: dict[str, str | None] = {p: None for p in PLAYERS}
        self.ev_keys: set[int] = set()
        # this frame's presses: "button" (any joystick button, either pad)
        # and "key" -- what closes the HOW TO PLAY card
        self.presses: set[str] = set()
        self.last_keys: list[str] = []
        self.confirm = self.back = self.pause = False
        self.back_held = 0.0
        self.quit_combo = False
        self.pads.scan()

    @property
    def joys(self) -> dict[int, pygame.joystick.JoystickType]:
        """Every connected joystick by device index (for the input test)."""
        return {i: pygame.joystick.Joystick(i) for i in range(pygame.joystick.get_count())}

    def handle(self, e: pygame.event.Event) -> None:
        self.pads.handle_event(e)
        self.devices.handle_event(e, self.pads, keyboard=_keyboard_enabled)
        buttons = self.pad_layout.buttons
        if e.type == pygame.KEYDOWN:
            self.last_keys = (self.last_keys + [pygame.key.name(e.key)])[-8:]
            if not _keyboard_enabled:
                return
            self.presses.add("key")
            self.ev_keys.add(e.key)
            self.confirm |= e.key in START_KEYS
            self.pause |= e.key in START_KEYS
            self.back |= e.key in SELECT_KEYS
            for p in PLAYERS:
                for d in DIRECTIONS:
                    if e.key in KEY_CODES[p][d]:
                        self.last_key_dir[p] = d
        elif e.type == pygame.JOYBUTTONDOWN:
            self.presses.add("button")
            if e.button == buttons["start"]:
                self.confirm = self.pause = True
            if e.button == buttons["select"]:
                self.back = True

    def _read(self, p: str, keys):
        """(direction, actions held, Start held, Select held) from p's keys and pad.
        Direction keys and the d-pad win over the stick; of two held
        direction keys, the newer one counts."""
        pad = self.pads.pad(PLAYERS.index(p))
        try:
            state = read_player(p, keys, pad, self.pad_layout)
        except pygame.error:  # the pad went away mid-read
            state = read_player(p, keys, None, self.pad_layout)
        held = [d for d in DIRECTIONS if state[d]]
        if held:
            direction = self.last_key_dir[p] if self.last_key_dir[p] in held else held[0]
        else:
            direction = stick_direction(state.stick_x, state.stick_y, INPUT_CONFIG["axis_deadzone"])
        buttons = {act for act, bs in ACTION_BUTTONS.items() if any(state[b] for b in bs)}
        return direction, buttons, state["start"], state["select"]

    def update(self, dt: float) -> None:
        keys = _HeldOrTapped(read_keys(), self.ev_keys)
        start_select = {}
        for p in PLAYERS:
            direction, buttons, start, select = self._read(p, keys)
            start_select[p] = (start, select)
            self.dir[p] = direction
            self.move[p] = self.repeaters[p].update(direction, dt)
            self.pressed[p] = buttons - self.prev_buttons[p]
            # key presses shorter than one frame still count
            for act in BUTTON_ACTIONS:
                if any(k in self.ev_keys for k in KEY_CODES[p][act]):
                    self.pressed[p].add(act)
            self.prev_buttons[p] = buttons
        self.quit_combo = should_quit(
            p1_start=start_select["p1"][0], p1_select=start_select["p1"][1],
            p2_start=start_select["p2"][0], p2_select=start_select["p2"][1],
        )
        back_down = any(select for _start, select in start_select.values())
        self.back_held = self.back_held + dt if back_down else 0.0

    def end_frame(self) -> None:
        self.ev_keys.clear()
        self.presses.clear()
        self.confirm = self.back = self.pause = False

    def hit(self, p: str, action: str) -> bool:
        return action in self.pressed[p]

    def any_hit(self, action: str) -> bool:
        return self.hit("p1", action) or self.hit("p2", action)

    def any_move(self) -> str | None:
        return self.move["p1"] or self.move["p2"]
