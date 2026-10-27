"""Translate raw pygame joystick/keyboard state into logical actions.

Devices, pad layouts and the two-player keyboard are shared by all games
(arqade_common.input). Each gate sits on one of the pad's printed buttons
(GATE_BUTTONS); A confirms and B goes back in the menus.

The pure decision functions (pressed_edge, should_quit) are unit tested.
Reading actual device state needs pygame + hardware/SDL and is exercised by
manual/headless smoke testing only.
"""

from __future__ import annotations

from dataclasses import dataclass

import pygame
from arqade_common.input import (
    KEYBOARD,
    PLAYERS,
    LastDevice,
    PadLayout,
    PadSlots,
    default_pad_layout,
    read_player,
)

from quantum_towers.config import ACTION_NAMES, AXIS_DEADZONE, GATE_BUTTONS


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


def pressed_edge(previous: bool, current: bool) -> bool:
    """True only on the frame a button transitions from not-held to held."""
    return current and not previous


def axis_indicates_up(axis_value: float, deadzone: float) -> bool:
    """True when the vertical axis is pushed far enough toward "up" -- negative,
    matching SDL's convention (same sign Quantum Pong already confirmed on this
    exact cabinet's sticks)."""
    return axis_value < -deadzone


def axis_indicates_down(axis_value: float, deadzone: float) -> bool:
    """The mirror of axis_indicates_up (positive = down); only the pause menu
    reads it, to move its selection."""
    return axis_value > deadzone


def should_quit(*, p1_start: bool, p1_select: bool, p2_start: bool, p2_select: bool) -> bool:
    """Start + Select held together by one player. There is deliberately no
    quit key: Esc leaves fullscreen in a browser, and the PC launcher handles
    Esc itself (it ends the game process)."""
    return (p1_start and p1_select) or (p2_start and p2_select)


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


@dataclass
class PlayerRawInput:
    button_held: dict[str, bool]
    up_held: bool
    start_held: bool
    select_held: bool
    confirm_held: bool
    down_held: bool = False  # pause menu and title choice only
    back_held: bool = False  # B; pause menu and initials entry only
    left_held: bool = False  # initials entry only
    right_held: bool = False


def read_player_raw_input(player_key: str, keys: pygame.key.ScancodeWrapper) -> PlayerRawInput:
    """Poll this player's keys + pad for one frame."""
    pad = _pads.pad(PLAYERS.index(player_key))
    try:
        state = read_player(player_key, keys, pad, _pad_layout)
    except pygame.error:  # the pad went away mid-read
        state = read_player(player_key, keys, None, _pad_layout)
    return PlayerRawInput(
        button_held={name: state[GATE_BUTTONS[name]] for name in ACTION_NAMES},
        up_held=state["up"] or axis_indicates_up(state.stick_y, AXIS_DEADZONE),
        start_held=state["start"],
        select_held=state["select"],
        confirm_held=state["a"],
        down_held=state["down"] or axis_indicates_down(state.stick_y, AXIS_DEADZONE),
        back_held=state["b"],
        # Same sign convention as the vertical axis: negative = left.
        left_held=state["left"] or state.stick_x < -AXIS_DEADZONE,
        right_held=state["right"] or state.stick_x > AXIS_DEADZONE,
    )


def button_name(control: str, player: str | None = None) -> str:
    """A control's on-screen name for one player's keys or pad, or for both
    players' when player is None (e.g. "SPACE / ENTER"). "up" is the stick
    pushed up: "STICK UP" on a pad, the up key on the keyboard."""
    if player is None:
        return " / ".join(dict.fromkeys(button_name(control, p) for p in PLAYERS))
    if control == "up" and _last_device[player] != KEYBOARD:
        return "STICK UP"
    if control == "stick" and _last_device[player] == KEYBOARD:
        return "WASD" if player == "p1" else "ARROWS"
    if control == "stick":
        return "STICK"
    return _last_device.label(control, player)


def cluster_keys(player: str) -> str:
    """A player's six button keys as they sit, e.g. "F G H / C V B"."""
    rows = (("l", "x", "r"), ("y", "b", "a"))
    return " / ".join(" ".join(_last_device.label(b, player) for b in row) for row in rows)
