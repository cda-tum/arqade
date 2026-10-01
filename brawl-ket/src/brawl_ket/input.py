"""Pads and the dev keyboard, polled once per display frame.

Per pad: the analog stick (axes 0 and 1, deadzoned; the hat only as a fallback,
which the cabinet never needs because it has none) and the A, B and X buttons
as edge-triggered presses. Start confirms, pauses and starts; Select only joins
Start for the quit combo. The pure helpers are unit tested; reading real pads
is verified on the cabinet with --input-test.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import pygame

from . import config
from .fighter import IDLE, FighterInput

PLAYERS = ("p1", "p2")

# The stick's vertical axis needs a firmer push than the horizontal one, so a
# walk never accidentally jumps or crouches.
VERTICAL_THRESHOLD = 0.5

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


def _codes(names: list[str]) -> list[int]:
    return [getattr(pygame, name) for name in names]


def keyboard_quit_held(keys) -> bool:
    return bool(keys[getattr(pygame, config.INPUT_CONFIG["system"]["keyboard_quit"])])


# --- pure helpers ----------------------------------------------------------------------


def deadzone(value: float, dz: float = config.INPUT_CONFIG["axis_deadzone"]) -> int:
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
    """Start + Select held together on the same pad."""
    return (p1_start and p1_select) or (p2_start and p2_select)


# --- one frame's worth of input ------------------------------------------------------------


@dataclass
class FrameInput:
    """What the game gets per display frame. (Task 10 moves this into match.py.)"""

    fighters: dict[str, FighterInput] = field(default_factory=lambda: {p: IDLE for p in PLAYERS})
    confirms: dict[str, bool] = field(default_factory=lambda: {p: False for p in PLAYERS})  # A or Start
    backs: dict[str, bool] = field(default_factory=lambda: {p: False for p in PLAYERS})      # B
    pauses: dict[str, bool] = field(default_factory=lambda: {p: False for p in PLAYERS})     # Start
    activity: bool = False


class Input:
    def __init__(self) -> None:
        self.joysticks: list = []
        self.keymap = {p: {act: _codes(names) for act, names in config.KEYMAP[p].items()} for p in PLAYERS}
        self._down: dict[str, set[int]] = {p: set() for p in PLAYERS}
        self._keys_prev: dict[str, set[str]] = {p: set() for p in PLAYERS}
        self.frame = FrameInput()
        self.start_select = {p: (False, False) for p in PLAYERS}
        self.select_held_time = 0.0     # seconds Select has been held on either pad
        self.keyboard_quit = False
        self.rescan()

    def rescan(self) -> None:
        self.joysticks = []
        for i in range(pygame.joystick.get_count()):
            joy = pygame.joystick.Joystick(i)
            joy.init()
            self.joysticks.append(joy)

    def handle(self, event: pygame.event.Event) -> None:
        if event.type in (pygame.JOYDEVICEADDED, pygame.JOYDEVICEREMOVED):
            self.rescan()

    def _read_pad(self, player: str) -> tuple[set[int], int, bool, bool]:
        """(buttons down, dx, up, down) for one pad."""
        cfg = config.INPUT_CONFIG[player]
        if cfg["joystick_index"] >= len(self.joysticks):
            return set(), 0, False, False
        joy = self.joysticks[cfg["joystick_index"]]
        try:
            down = {b for b in range(joy.get_numbuttons()) if joy.get_button(b)}
            ax_i, ay_i = cfg["axes"]
            dx = deadzone(joy.get_axis(ax_i)) if joy.get_numaxes() > ax_i else 0
            up, dn = vertical(joy.get_axis(ay_i)) if joy.get_numaxes() > ay_i else (False, False)
            if dx == 0 and not up and not dn and joy.get_numhats() > cfg["hat_index"]:
                hx, hy = joy.get_hat(cfg["hat_index"])
                dx, up, dn = hx, hy > 0, hy < 0
        except pygame.error:
            return set(), 0, False, False
        return down, dx, up, dn

    def update(self, dt: float) -> None:
        keys = read_keys()
        system = config.INPUT_CONFIG["system"]
        a_btn, b_btn, x_btn = system["a_button"], system["b_button"], system["x_button"]
        start = system["start_button"]
        self.keyboard_quit = keyboard_quit_held(keys)
        frame = FrameInput(activity=self.keyboard_quit)
        for p in PLAYERS:
            down, dx, up, dn = self._read_pad(p)
            held_keys = {act for act, codes in self.keymap[p].items() if any(keys[k] for k in codes)}
            if dx == 0:
                dx = ("right" in held_keys) - ("left" in held_keys)
            up = up or "up" in held_keys
            dn = dn or "down" in held_keys
            pressed = edge_presses(self._down[p], down)
            self._down[p] = down
            new_keys = edge_presses(self._keys_prev[p], held_keys)
            self._keys_prev[p] = held_keys
            a = a_btn in pressed or "a" in new_keys
            start_pressed = start in pressed or "start" in new_keys
            frame.fighters[p] = FighterInput(
                dx=dx, up=up, down=dn, a=a,
                b=b_btn in pressed or "b" in new_keys,
                x=x_btn in pressed or "x" in new_keys,
            )
            frame.confirms[p] = a or start_pressed
            frame.backs[p] = b_btn in pressed or "b" in new_keys
            frame.pauses[p] = start_pressed
            self.start_select[p] = (start in down, system["select_button"] in down)
            if down or dx or up or dn or held_keys:
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
