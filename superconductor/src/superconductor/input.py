"""Translate raw pygame joystick/keyboard state into logical actions.

The pure decision functions (stick_direction, DirectionRepeater, should_quit)
are unit tested. Reading actual device state needs pygame + hardware/SDL and
is exercised by manual/headless smoke testing only.
"""

from __future__ import annotations

import pygame

from superconductor.config import (
    INPUT_CONFIG,
    KEYS,
    KEYS_BACK,
    KEYS_CONFIRM,
    KEYS_PAUSE,
    REPEAT_DELAY,
    REPEAT_INTERVAL,
)

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
    return (p1_start and p1_select) or (p2_start and p2_select)


def key_codes(names: list[str]) -> list[int]:
    return [getattr(pygame, name) for name in names]


KEY_CODES = {p: {act: key_codes(names) for act, names in KEYS[p].items()} for p in PLAYERS}
CONFIRM_KEYS = key_codes(KEYS_CONFIRM)
BACK_KEYS = key_codes(KEYS_BACK)
PAUSE_KEYS = key_codes(KEYS_PAUSE)


class Input:
    """Keyboard + joysticks, with edge detection and stick auto-repeat.

    Per frame, per player: `move[p]` is the direction to step this frame (or
    None) and `pressed[p]` the button actions that went down this frame.
    """

    def __init__(self):
        self.joys: dict[int, pygame.joystick.JoystickType] = {}
        self.repeaters = {p: DirectionRepeater() for p in PLAYERS}
        self.move: dict[str, str | None] = {p: None for p in PLAYERS}
        self.dir: dict[str, str | None] = {p: None for p in PLAYERS}
        self.prev_buttons: dict[str, set[str]] = {p: set() for p in PLAYERS}
        self.pressed: dict[str, set[str]] = {p: set() for p in PLAYERS}
        self.last_key_dir: dict[str, str | None] = {p: None for p in PLAYERS}
        self.ev_keys: set[int] = set()
        self.last_keys: list[str] = []
        self.confirm = self.back = self.pause = False
        self.back_held = 0.0
        self.quit_combo = False
        self.refresh_joys()

    def refresh_joys(self) -> None:
        self.joys = {}
        for i in range(pygame.joystick.get_count()):
            try:
                j = pygame.joystick.Joystick(i)
                j.init()
                self.joys[i] = j
            except pygame.error:
                pass

    def handle(self, e: pygame.event.Event) -> None:
        system = INPUT_CONFIG["system"]
        if e.type == pygame.KEYDOWN:
            self.last_keys = (self.last_keys + [pygame.key.name(e.key)])[-8:]
            if not _keyboard_enabled:
                return
            self.ev_keys.add(e.key)
            self.confirm |= e.key in CONFIRM_KEYS
            self.back |= e.key in BACK_KEYS
            self.pause |= e.key in PAUSE_KEYS
            for p in PLAYERS:
                for d in DIRECTIONS:
                    if e.key in KEY_CODES[p][d]:
                        self.last_key_dir[p] = d
        elif e.type == pygame.JOYBUTTONDOWN:
            if e.button == system["start_button"]:
                self.confirm = self.pause = True
            if e.button == system["select_button"]:
                self.back = True
        elif e.type in (pygame.JOYDEVICEADDED, pygame.JOYDEVICEREMOVED):
            self.refresh_joys()

    @staticmethod
    def _button(j, idx: int) -> bool:
        return idx < j.get_numbuttons() and bool(j.get_button(idx))

    def _joy_state(self, j, cfg) -> tuple[str | None, set[str]]:
        try:
            ax_i, ay_i = cfg["axes"]
            ax = j.get_axis(ax_i) if j.get_numaxes() > ax_i else 0.0
            ay = j.get_axis(ay_i) if j.get_numaxes() > ay_i else 0.0
            if j.get_numhats() > cfg["hat_index"]:
                hx, hy = j.get_hat(cfg["hat_index"])
                if hx or hy:
                    ax, ay = float(hx), float(-hy)
            direction = stick_direction(ax, ay, INPUT_CONFIG["axis_deadzone"])
            buttons = {act for act, idxs in cfg["buttons"].items()
                       if any(self._button(j, b) for b in idxs)}
            return direction, buttons
        except pygame.error:
            return None, set()

    def _key_direction(self, p: str, keys) -> str | None:
        held = [d for d in DIRECTIONS if any(keys[k] for k in KEY_CODES[p][d])]
        if not held:
            return None
        return self.last_key_dir[p] if self.last_key_dir[p] in held else held[0]

    def update(self, dt: float) -> None:
        keys = read_keys()
        system = INPUT_CONFIG["system"]
        start_select = {}
        for p in PLAYERS:
            cfg = INPUT_CONFIG[p]
            direction = self._key_direction(p, keys)
            buttons = {act for act in BUTTON_ACTIONS if any(keys[k] for k in KEY_CODES[p][act])}
            j = self.joys.get(cfg["joystick_index"])
            start_select[p] = (False, False)
            if j is not None:
                joy_dir, joy_buttons = self._joy_state(j, cfg)
                direction = direction or joy_dir
                buttons |= joy_buttons
                start_select[p] = (self._button(j, system["start_button"]),
                                   self._button(j, system["select_button"]))
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
        back_down = any(keys[k] for k in BACK_KEYS) or any(
            self._button(j, system["select_button"]) for j in self.joys.values())
        self.back_held = self.back_held + dt if back_down else 0.0

    def end_frame(self) -> None:
        self.ev_keys.clear()
        self.confirm = self.back = self.pause = False

    def hit(self, p: str, action: str) -> bool:
        return action in self.pressed[p]

    def any_hit(self, action: str) -> bool:
        return self.hit("p1", action) or self.hit("p2", action)

    def any_move(self) -> str | None:
        return self.move["p1"] or self.move["p2"]
