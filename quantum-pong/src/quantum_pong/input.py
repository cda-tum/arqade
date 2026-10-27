"""Translate raw pygame joystick/keyboard state into logical game actions.

Devices, button layouts and the keyboard layout are shared by all games and
live in arqade_common.input; this module turns them into what Pong needs
(a paddle direction, start/select/confirm/back).

The pure decision functions (axis_to_direction, resolve_paddle_direction,
pressed_edge, should_quit) are unit tested. Reading actual device state needs
pygame + hardware/SDL and is exercised by manual/headless smoke testing only.
"""

from __future__ import annotations

from dataclasses import dataclass

import pygame
from arqade_common.input import (
    PLAYERS,
    LastDevice,
    PadLayout,
    PadSlots,
    default_pad_layout,
    read_player,
)


def axis_to_direction(axis_value: float, deadzone: float) -> int:
    if axis_value < -deadzone:
        return -1
    if axis_value > deadzone:
        return 1
    return 0


def resolve_paddle_direction(
    *, up_held: bool, down_held: bool, axis_value: float, deadzone: float
) -> int:
    """Combine digital (keyboard, d-pad) and analog (joystick axis) input into -1/0/1.
    Digital input wins when both are active, so dev keyboard testing is predictable.
    """
    digital = (1 if down_held else 0) - (1 if up_held else 0)
    if digital != 0:
        return digital
    return axis_to_direction(axis_value, deadzone)


# Batocera's pygame system runs evmapy, which turns player 1's pad into
# keyboard presses (d-pad -> arrow keys, a/b/x/y -> A/B/X/Y, start -> Enter,
# select -> Space, ...). Those fake keys collide with the keyboard layout
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


def pressed_edge(previous: bool, current: bool) -> bool:
    """True only on the frame a button transitions from not-held to held."""
    return current and not previous


def should_quit(*, p1_start: bool, p1_select: bool, p2_start: bool, p2_select: bool) -> bool:
    """Start + Select held together by one player. There is deliberately no
    quit key: Esc leaves fullscreen in a browser, and the PC launcher handles
    Esc itself (it ends the game process)."""
    return (p1_start and p1_select) or (p2_start and p2_select)


@dataclass
class PlayerRawInput:
    up_held: bool
    down_held: bool
    axis_value: float
    start_held: bool
    select_held: bool
    confirm_held: bool
    back_held: bool


def read_player_raw_input(player_key: str, keys: pygame.key.ScancodeWrapper) -> PlayerRawInput:
    """Poll this player's keys + pad for one frame. A confirms and B goes back,
    the cabinet-wide convention ("Button convention" in ../AGENTS.md)."""
    state = read_player(player_key, keys, _pads.pad(PLAYERS.index(player_key)), _pad_layout)
    return PlayerRawInput(
        up_held=state["up"],
        down_held=state["down"],
        axis_value=state.stick_y,
        start_held=state["start"],
        select_held=state["select"],
        confirm_held=state["a"],
        back_held=state["b"],
    )

