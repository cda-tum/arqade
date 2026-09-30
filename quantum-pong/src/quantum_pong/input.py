"""Translate raw pygame joystick/keyboard state into logical game actions.

The pure decision functions (axis_to_direction, resolve_paddle_direction,
pressed_edge, should_quit) are unit tested. Reading actual device state needs
pygame + hardware/SDL and is exercised by manual/headless smoke testing only.
"""

from __future__ import annotations

from dataclasses import dataclass

import pygame

from quantum_pong.config import INPUT_CONFIG


def axis_to_direction(axis_value: float, deadzone: float) -> int:
    if axis_value < -deadzone:
        return -1
    if axis_value > deadzone:
        return 1
    return 0


def resolve_paddle_direction(
    *, up_held: bool, down_held: bool, axis_value: float, deadzone: float
) -> int:
    """Combine digital (keyboard) and analog (joystick axis) input into -1/0/1.
    Digital input wins when both are active, so dev keyboard testing is predictable.
    """
    digital = (1 if down_held else 0) - (1 if up_held else 0)
    if digital != 0:
        return digital
    return axis_to_direction(axis_value, deadzone)


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


def should_quit(
    *, p1_start: bool, p1_select: bool, p2_start: bool, p2_select: bool, keyboard_quit: bool
) -> bool:
    combo = (p1_start and p1_select) or (p2_start and p2_select)
    return keyboard_quit or combo


@dataclass
class PlayerRawInput:
    up_held: bool
    down_held: bool
    axis_value: float
    start_held: bool
    select_held: bool
    confirm_held: bool


def get_joystick(index: int) -> pygame.joystick.JoystickType | None:
    if index >= pygame.joystick.get_count():
        return None
    joy = pygame.joystick.Joystick(index)
    if not joy.get_init():
        joy.init()
    return joy


def read_player_raw_input(player_key: str, keys: pygame.key.ScancodeWrapper) -> PlayerRawInput:
    """Poll keyboard + this player's configured joystick for one frame."""
    cfg = INPUT_CONFIG[player_key]
    kb = cfg["keyboard"]
    up_held = bool(keys[getattr(pygame, kb["up"])])
    down_held = bool(keys[getattr(pygame, kb["down"])])

    axis_value = 0.0
    start_held = False
    select_held = False
    confirm_held = False

    joystick = get_joystick(cfg["joystick_index"])
    if joystick is not None:
        if joystick.get_numaxes() > cfg["vertical_axis"]:
            axis_value = joystick.get_axis(cfg["vertical_axis"])

        num_buttons = joystick.get_numbuttons()
        system = INPUT_CONFIG["system"]
        if system["start_button"] < num_buttons:
            start_held = bool(joystick.get_button(system["start_button"]))
        if system["select_button"] < num_buttons:
            select_held = bool(joystick.get_button(system["select_button"]))
        if system["confirm_button"] < num_buttons:
            confirm_held = bool(joystick.get_button(system["confirm_button"]))

    return PlayerRawInput(
        up_held=up_held,
        down_held=down_held,
        axis_value=axis_value,
        start_held=start_held,
        select_held=select_held,
        confirm_held=confirm_held,
    )


def keyboard_quit_held(keys: pygame.key.ScancodeWrapper) -> bool:
    key_name = INPUT_CONFIG["system"]["keyboard_quit"]
    return bool(keys[getattr(pygame, key_name)])
