"""Translate raw pygame joystick/keyboard state into logical per-player actions.

Polled once per frame: each action is held while any of its sources (a key,
a joystick button, the analog stick, the hat) is down; `pressed` is the
rising edge. The pure decision helpers (axis_to_direction, joystick_actions,
should_quit, Repeater) are unit tested; reading real devices needs hardware
and is verified with `--input-test`.
"""

from __future__ import annotations

import pygame

from overquqed.config import (
    INPUT_CONFIG,
    KEYBOARD_QUIT,
    KEYMAP,
    REPEAT_DELAY,
    REPEAT_INTERVAL,
)

PLAYERS = ("p1", "p2")  # pad 0, pad 1
DIRECTIONS = ("left", "right", "up", "down")
ACTIONS = DIRECTIONS + ("pick", "use", "swap", "start", "select")


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
    """Start + Select held together on the *same* pad."""
    return (p1_start and p1_select) or (p2_start and p2_select)


def key_codes(names: list[str]) -> list[int]:
    return [getattr(pygame, name) for name in names]


def keyboard_quit_held(keys) -> bool:
    return bool(keys[getattr(pygame, KEYBOARD_QUIT)])


def joystick_actions(
    player: str,
    buttons_down: set[int],
    axes: tuple[float, float],
    hat: tuple[int, int],
) -> set[str]:
    """Logical actions held on one pad, from its raw state.

    The analog stick is the primary direction source (this cabinet has no
    hat: get_numhats() == 0); a non-centred hat, if present, wins.
    """
    cfg = INPUT_CONFIG[player]
    system = INPUT_CONFIG["system"]
    deadzone = INPUT_CONFIG["axis_deadzone"]
    held: set[str] = set()
    for act, buttons in cfg["buttons"].items():
        if buttons_down & set(buttons):
            held.add(act)
    if system["start_button"] in buttons_down:
        held.add("start")
    if system["select_button"] in buttons_down:
        held.add("select")

    dx = axis_to_direction(axes[0], deadzone)
    dy = axis_to_direction(axes[1], deadzone)
    if hat != (0, 0):
        dx, dy = hat[0], -hat[1]  # hat y is positive-up
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

    def __init__(self) -> None:
        self.joysticks: list[pygame.joystick.JoystickType] = []
        self.keymap = {p: {act: key_codes(names) for act, names in m.items()} for p, m in KEYMAP.items()}
        self.held = {p: set() for p in PLAYERS}
        self.pressed = {p: set() for p in PLAYERS}
        self.nav = {p: set() for p in PLAYERS}  # directions incl. auto-repeat
        self._repeat = {p: {d: Repeater() for d in DIRECTIONS} for p in PLAYERS}
        self.select_held_time = 0.0
        self.keyboard_quit = False
        self.activity = False  # any input at all this frame (for the idle timer)
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

    def _pad_state(self, player: str) -> set[str]:
        index = INPUT_CONFIG[player]["joystick_index"]
        if index >= len(self.joysticks):
            return set()
        joy = self.joysticks[index]
        cfg = INPUT_CONFIG[player]
        buttons = {b for b in range(joy.get_numbuttons()) if joy.get_button(b)}
        ax_x, ax_y = cfg["axes"]
        axes = (
            joy.get_axis(ax_x) if joy.get_numaxes() > ax_x else 0.0,
            joy.get_axis(ax_y) if joy.get_numaxes() > ax_y else 0.0,
        )
        hat = joy.get_hat(cfg["hat_index"]) if joy.get_numhats() > cfg["hat_index"] else (0, 0)
        return joystick_actions(player, buttons, axes, hat)

    def update(self, dt: float) -> None:
        keys = read_keys()
        self.keyboard_quit = keyboard_quit_held(keys)
        self.activity = self.keyboard_quit
        for p in PLAYERS:
            held = self._pad_state(p)
            for act, codes in self.keymap[p].items():
                if any(keys[c] for c in codes):
                    held.add(act)
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
