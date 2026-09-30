"""Translate raw pygame joystick/keyboard state into logical actions.

The pure decision functions (pressed_edge, should_quit) are unit tested.
Reading actual device state needs pygame + hardware/SDL and is exercised by
manual/headless smoke testing only.
"""

from __future__ import annotations

from dataclasses import dataclass

import pygame

from quantum_towers.config import ACTION_NAMES, INPUT_CONFIG


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
    button_held: dict[str, bool]
    up_held: bool
    start_held: bool
    select_held: bool


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
    button_held = {name: bool(keys[getattr(pygame, kb[name])]) for name in ACTION_NAMES}
    up_held = bool(keys[getattr(pygame, cfg["up_keyboard"])])

    start_held = False
    select_held = False

    joystick = get_joystick(cfg["joystick_index"])
    if joystick is not None:
        num_buttons = joystick.get_numbuttons()
        for name in ACTION_NAMES:
            idx = cfg["buttons"][name]
            if idx < num_buttons:
                button_held[name] = button_held[name] or bool(joystick.get_button(idx))

        num_hats = joystick.get_numhats()
        hat_index = cfg["hat_index"]
        if hat_index < num_hats:
            _hat_x, hat_y = joystick.get_hat(hat_index)
            up_held = up_held or hat_y > 0

        system = INPUT_CONFIG["system"]
        if system["start_button"] < num_buttons:
            start_held = bool(joystick.get_button(system["start_button"]))
        if system["select_button"] < num_buttons:
            select_held = bool(joystick.get_button(system["select_button"]))

    return PlayerRawInput(
        button_held=button_held, up_held=up_held, start_held=start_held, select_held=select_held
    )


def keyboard_quit_held(keys: pygame.key.ScancodeWrapper) -> bool:
    key_name = INPUT_CONFIG["system"]["keyboard_quit"]
    return bool(keys[getattr(pygame, key_name)])
