"""Pads and the dev keyboard, polled once per frame into a match.FrameInput.

Per player: the stick moves the pill left and right (auto-repeated) and
soft-drops it when pushed down; A rotates clockwise and B anti-clockwise.
In menus the stick navigates (auto-repeated, per player), A (or Start)
confirms and B goes back, each per player, so both can set up at once. The pure helpers are unit
tested; reading real pads is verified on the cabinet with --input-test.
"""

from __future__ import annotations

import pygame

from gate_drop import config
from gate_drop.board import PlayerInput
from gate_drop.match import PLAYERS, FrameInput

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


def axis_sign(value: float, deadzone: float) -> int:
    if value < -deadzone:
        return -1
    if value > deadzone:
        return 1
    return 0


def should_quit(*, p1_start: bool, p1_select: bool, p2_start: bool, p2_select: bool) -> bool:
    """Start + Select held together on the same pad."""
    return (p1_start and p1_select) or (p2_start and p2_select)


class AutoRepeat:
    """Turns a held direction (-1, 0 or 1) into presses: one at once, then
    one after REPEAT_DELAY, then one every REPEAT_INTERVAL."""

    def __init__(self, delay: float = config.REPEAT_DELAY, interval: float = config.REPEAT_INTERVAL) -> None:
        self.delay, self.interval = delay, interval
        self.held = 0
        self.timer = 0.0

    def update(self, dt: float, value: int) -> int:
        if value == 0:
            self.held = 0
            return 0
        if value != self.held:
            self.held = value
            self.timer = self.delay
            return value
        self.timer -= dt
        if self.timer <= 0:
            self.timer += self.interval
            return value
        return 0


class Input:
    def __init__(self) -> None:
        self.joysticks: list = []
        self.keymap = {p: {act: _codes(names) for act, names in config.KEYMAP[p].items()} for p in PLAYERS}
        self.repeat_x = {p: AutoRepeat() for p in PLAYERS}
        self.repeat_y = {p: AutoRepeat() for p in PLAYERS}
        self._down: dict[str, set[int]] = {p: set() for p in PLAYERS}
        self._keys_prev: dict[str, set[str]] = {p: set() for p in PLAYERS}
        self.frame = FrameInput()
        self.start_select = {p: (False, False) for p in PLAYERS}
        self.select_held_time = 0.0
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

    def _read_pad(self, player: str) -> tuple[set[int], int, int]:
        """(buttons down, stick x, stick y) with y positive = down."""
        cfg = config.INPUT_CONFIG[player]
        if cfg["joystick_index"] >= len(self.joysticks):
            return set(), 0, 0
        joy = self.joysticks[cfg["joystick_index"]]
        try:
            down = {b for b in range(joy.get_numbuttons()) if joy.get_button(b)}
            ax_i, ay_i = cfg["axes"]
            dz = config.INPUT_CONFIG["axis_deadzone"]
            dx = axis_sign(joy.get_axis(ax_i), dz) if joy.get_numaxes() > ax_i else 0
            dy = axis_sign(joy.get_axis(ay_i), dz) if joy.get_numaxes() > ay_i else 0
            if dx == 0 and dy == 0 and joy.get_numhats() > cfg["hat_index"]:
                hx, hy = joy.get_hat(cfg["hat_index"])
                dx, dy = hx, -hy
        except pygame.error:
            return set(), 0, 0
        return down, dx, dy

    def update(self, dt: float) -> None:
        keys = read_keys()
        system = config.INPUT_CONFIG["system"]
        buttons = config.INPUT_CONFIG["buttons"]
        self.keyboard_quit = keyboard_quit_held(keys)
        frame = FrameInput(activity=self.keyboard_quit)
        for p in PLAYERS:
            down, dx, dy = self._read_pad(p)
            held_keys = {act for act, codes in self.keymap[p].items() if any(keys[k] for k in codes)}
            if dx == 0:
                dx = ("right" in held_keys) - ("left" in held_keys)
            if dy == 0:
                dy = ("down" in held_keys) - ("up" in held_keys)
            pressed = down - self._down[p]
            self._down[p] = down
            new_keys = held_keys - self._keys_prev[p]
            self._keys_prev[p] = held_keys
            move = self.repeat_x[p].update(dt, dx)
            cw = bool(pressed & set(buttons["cw"])) or "cw" in new_keys
            ccw = bool(pressed & set(buttons["ccw"])) or "ccw" in new_keys
            frame.players[p] = PlayerInput(move, cw, ccw, dy > 0)
            frame.nav[p] = (move, self.repeat_y[p].update(dt, dy))
            frame.confirms[p] = bool(pressed & {*system["confirm_buttons"], system["start_button"]}) \
                or "confirm" in new_keys
            frame.backs[p] = bool(pressed & set(system["back_buttons"])) or "back" in new_keys
            frame.pauses[p] = system["start_button"] in pressed or "pause" in new_keys
            self.start_select[p] = (system["start_button"] in down, system["select_button"] in down)
            if down or dx or dy or held_keys:
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
