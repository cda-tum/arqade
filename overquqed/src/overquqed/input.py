"""Translate raw pygame joystick/keyboard state into logical per-player actions.

Polled once per frame: each action is held while any of its sources (a key,
a joystick button, the analog stick, the d-pad) is down; `pressed` is the
rising edge. Devices, pad layouts and the two-player keyboard are shared by
all games (arqade_common.input). The pure decision helpers
(axis_to_direction, actions_from_state, should_quit, Repeater) are unit
tested; reading real devices needs hardware and is verified with
`--input-test`.
"""

from __future__ import annotations

import pygame
from arqade_common.input import (
    KEYBOARD,
    LastDevice,
    PadLayout,
    PadSlots,
    PlayerState,
    default_pad_layout,
    read_player,
)

from overquqed.config import AXIS_DEADZONE, REPEAT_DELAY, REPEAT_INTERVAL

PLAYERS = ("p1", "p2")  # pad 0, pad 1
DIRECTIONS = ("left", "right", "up", "down")
ACTIONS = DIRECTIONS + ("pick", "use", "swap", "start", "select")
# The printed button behind each action.
ACTION_BUTTONS = {
    "pick": "a",  # pick up / put down / take / serve
    "use": "b",  # work the station in front of you
    "swap": "y",  # swap chef (1-player mode)
    "start": "start",  # confirms / pauses
    "select": "select",  # goes back; Start + Select on one pad quits
}


# Batocera's pygame system runs evmapy, which turns player 1's pad into
# keyboard presses (d-pad -> arrow keys, a/b/x/y -> A/B/X/Y, start -> Enter,
# select -> Space, ...). Those fake keys collide with a dev keyboard layout,
# so the cabinet loader passes --no-keyboard and only the joysticks are read.
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
    """Start + Select held together on the *same* pad. There is deliberately
    no quit key: Esc leaves fullscreen in a browser, and the PC launcher
    handles Esc itself (it ends the game process)."""
    return (p1_start and p1_select) or (p2_start and p2_select)


def actions_from_state(state: PlayerState) -> set[str]:
    """Logical actions held by one player, from their keys and pad.

    The analog stick is the primary direction source on the cabinet (it has
    no hat); the d-pad and the direction keys count too.
    """
    held = {act for act, button in ACTION_BUTTONS.items() if state[button]}
    held.update(d for d in DIRECTIONS if state[d])
    dx = axis_to_direction(state.stick_x, AXIS_DEADZONE)
    dy = axis_to_direction(state.stick_y, AXIS_DEADZONE)
    if dx < 0:
        held.add("left")
    elif dx > 0:
        held.add("right")
    if dy < 0:
        held.add("up")
    elif dy > 0:
        held.add("down")
    return held


class Repeater:
    """Menu-style auto-repeat for a held direction: fires on press, then after
    REPEAT_DELAY, then every REPEAT_INTERVAL while still held."""

    def __init__(self) -> None:
        self.timer = 0.0

    def update(self, dt: float, held: bool, pressed: bool) -> bool:
        if not held:
            self.timer = 0.0
            return False
        if pressed:
            self.timer = REPEAT_DELAY
            return True
        self.timer -= dt
        if self.timer <= 0:
            self.timer += REPEAT_INTERVAL
            return True
        return False


class Input:
    """All input for one frame. Call `handle(event)` for every event, then
    `update(dt)` once per frame before querying."""

    def __init__(self, pad_layout: PadLayout | None = None) -> None:
        # Which pad is whose: pads join P1 then P2 as they appear (in a
        # browser, only after their first button press).
        self.pads = PadSlots()
        self.pad_layout = pad_layout or default_pad_layout()
        # Keyboard or pad, per player, so on-screen hints name what they're holding.
        self.devices = LastDevice()
        self.held = {p: set() for p in PLAYERS}
        self.pressed = {p: set() for p in PLAYERS}
        self.nav = {p: set() for p in PLAYERS}  # directions incl. auto-repeat
        self._repeat = {p: {d: Repeater() for d in DIRECTIONS} for p in PLAYERS}
        self.select_held_time = 0.0
        self.activity = False  # any input at all this frame (for the idle timer)
        # Any joystick button (or, without --no-keyboard, any key) that went
        # down this frame, mapped or not: what dismisses the HOW TO PLAY card.
        self.any_button = False
        self._button_down = False
        self.pads.scan()

    @property
    def joysticks(self) -> list[pygame.joystick.JoystickType]:
        """Every connected joystick (for the input test)."""
        return [pygame.joystick.Joystick(i) for i in range(pygame.joystick.get_count())]

    def handle(self, event: pygame.event.Event) -> None:
        self.pads.handle_event(event)
        self.devices.handle_event(event, self.pads, keyboard=_keyboard_enabled)
        if event.type == pygame.JOYBUTTONDOWN or (event.type == pygame.KEYDOWN and _keyboard_enabled):
            self._button_down = True

    def _held(self, player: str, keys) -> set[str]:
        pad = self.pads.pad(PLAYERS.index(player))
        try:
            return actions_from_state(read_player(player, keys, pad, self.pad_layout))
        except pygame.error:  # the pad went away mid-read
            return actions_from_state(read_player(player, keys, None, self.pad_layout))

    def update(self, dt: float) -> None:
        keys = read_keys()
        self.activity = self._button_down
        self.any_button, self._button_down = self._button_down, False
        for p in PLAYERS:
            held = self._held(p, keys)
            self.pressed[p] = held - self.held[p]
            self.held[p] = held
            self.nav[p] = {
                d for d in DIRECTIONS
                if self._repeat[p][d].update(dt, d in held, d in self.pressed[p])
            }
            if held:
                self.activity = True
        if any("select" in self.held[p] for p in PLAYERS):
            self.select_held_time += dt
        else:
            self.select_held_time = 0.0

    # --- queries ---
    def is_held(self, player: str, act: str) -> bool:
        return act in self.held[player]

    def was_pressed(self, player: str, act: str) -> bool:
        return act in self.pressed[player]

    def any_pressed(self, act: str) -> bool:
        return any(act in self.pressed[p] for p in PLAYERS)

    def any_nav(self, direction: str) -> bool:
        return any(direction in self.nav[p] for p in PLAYERS)

    def move(self, player: str) -> tuple[int, int]:
        held = self.held[player]
        dx = ("right" in held) - ("left" in held)
        dy = ("down" in held) - ("up" in held)
        return dx, dy

    def confirm(self) -> bool:
        """A or Start, per the cabinet's button convention (AGENTS.md)."""
        return self.any_pressed("start") or self.any_pressed("pick")

    def back(self) -> bool:
        """B (the "use" button), per the cabinet's button convention; Select
        still works too. Only called from menus, never mid-round, where B
        works the station in front of you."""
        return self.any_pressed("use") or self.any_pressed("select")

    def quit_combo(self) -> bool:
        a, b = self.held["p1"], self.held["p2"]
        return should_quit(
            p1_start="start" in a, p1_select="select" in a,
            p2_start="start" in b, p2_select="select" in b,
        )

    # --- button names, for on-screen hints ---
    def name(self, control: str, player: str | None = None) -> str:
        """A control's on-screen name for one player's keys or pad, or for
        both players' when player is None (e.g. "SPACE / ENTER"). "stick" is
        the stick or the direction keys."""
        if player is None:
            return " / ".join(dict.fromkeys(self.name(control, p) for p in PLAYERS))
        if control == "stick":
            if self.devices[player] == KEYBOARD:
                return "WASD" if player == "p1" else "ARROWS"
            return "STICK"
        return self.devices.label(control, player)
