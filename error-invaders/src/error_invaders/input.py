"""Translate raw pygame joystick/keyboard state into logical actions.

The pure decision functions (axis_to_direction, pressed_edge, should_quit) are
unit tested. Reading actual device state needs pygame + hardware/SDL and is
exercised by manual/headless smoke testing only.
"""

from __future__ import annotations

import pygame

from error_invaders.config import (
    INPUT_CONFIG,
    KEY_PRESET,
    KEY_PRESETS,
    KEYS_BACK,
    KEYS_CONFIRM,
)

ACTIONS = ("left", "right", "up", "down", "fire", "swap")
PLAYERS = ("p1", "p2")


def axis_to_direction(axis_value: float, deadzone: float) -> int:
    if axis_value < -deadzone:
        return -1
    if axis_value > deadzone:
        return 1
    return 0


def pressed_edge(previous: bool, current: bool) -> bool:
    """True only on the frame a button transitions from not-held to held."""
    return current and not previous


def should_quit(*, p1_start: bool, p1_select: bool, p2_start: bool, p2_select: bool) -> bool:
    return (p1_start and p1_select) or (p2_start and p2_select)


def key_codes(names: list[str]) -> list[int]:
    return [getattr(pygame, name) for name in names]


KEYS = {p: {act: key_codes(names) for act, names in KEY_PRESETS[KEY_PRESET][p].items()} for p in PLAYERS}
CONFIRM_KEYS = key_codes(KEYS_CONFIRM)
BACK_KEYS = key_codes(KEYS_BACK)


class Input:
    """Keyboard + joysticks, with edge detection."""

    def __init__(self):
        self.joys = {}  # device index -> Joystick
        self.held = {p: set() for p in PLAYERS}
        self.prev = {p: set() for p in PLAYERS}
        self.pressed = {p: set() for p in PLAYERS}
        self.ev_keys = set()
        self.last_keys = []
        self.confirm = self.back = False
        self.back_held = 0.0
        self.quit_combo = False
        self.refresh_joys()

    def refresh_joys(self):
        self.joys = {}
        for i in range(pygame.joystick.get_count()):
            try:
                j = pygame.joystick.Joystick(i)
                j.init()
                self.joys[i] = j
            except pygame.error:
                pass

    def handle(self, e):
        system = INPUT_CONFIG["system"]
        if e.type == pygame.KEYDOWN:
            self.ev_keys.add(e.key)
            self.last_keys = (self.last_keys + [pygame.key.name(e.key)])[-8:]
            if e.key in CONFIRM_KEYS:
                self.confirm = True
            if e.key in BACK_KEYS:
                self.back = True
        elif e.type == pygame.JOYBUTTONDOWN:
            if e.button == system["start_button"]:
                self.confirm = True
            if e.button == system["select_button"]:
                self.back = True
        elif e.type in (pygame.JOYDEVICEADDED, pygame.JOYDEVICEREMOVED):
            self.refresh_joys()

    @staticmethod
    def _button(j, idx):
        return idx < j.get_numbuttons() and bool(j.get_button(idx))

    def _joy_held(self, j, cfg):
        out = set()
        deadzone = INPUT_CONFIG["axis_deadzone"]
        try:
            ax_i, ay_i = cfg["axes"]
            ax = j.get_axis(ax_i) if j.get_numaxes() > ax_i else 0
            ay = j.get_axis(ay_i) if j.get_numaxes() > ay_i else 0
            if j.get_numhats() > cfg["hat_index"]:
                hx, hy = j.get_hat(cfg["hat_index"])
                if hx:
                    ax = hx
                if hy:
                    ay = -hy
            dx, dy = axis_to_direction(ax, deadzone), axis_to_direction(ay, deadzone)
            if dx < 0: out.add("left")
            if dx > 0: out.add("right")
            if dy < 0: out.add("up")
            if dy > 0: out.add("down")
            for act, buttons in cfg["buttons"].items():
                if any(self._button(j, b) for b in buttons):
                    out.add(act)
        except pygame.error:
            pass
        return out

    def update(self, dt):
        keys = pygame.key.get_pressed()
        system = INPUT_CONFIG["system"]
        start_select = {}
        for p in PLAYERS:
            h = set()
            for act in ACTIONS:
                for k in KEYS[p][act]:
                    if keys[k] or k in self.ev_keys:
                        h.add(act)
            cfg = INPUT_CONFIG[p]
            j = self.joys.get(cfg["joystick_index"])
            start_select[p] = (False, False)
            if j is not None:
                h |= self._joy_held(j, cfg)
                start_select[p] = (self._button(j, system["start_button"]),
                                   self._button(j, system["select_button"]))
            self.pressed[p] = h - self.prev[p]
            for act in ACTIONS:
                if any(k in self.ev_keys for k in KEYS[p][act]):
                    self.pressed[p].add(act)
            self.held[p] = h
            self.prev[p] = h
        self.quit_combo = should_quit(
            p1_start=start_select["p1"][0], p1_select=start_select["p1"][1],
            p2_start=start_select["p2"][0], p2_select=start_select["p2"][1],
        )
        # hold "back" (Select/ESC) to quit from the first menu page
        back_down = any(keys[k] for k in BACK_KEYS) or any(
            self._button(j, system["select_button"]) for j in self.joys.values())
        self.back_held = self.back_held + dt if back_down else 0.0

    def end_frame(self):
        self.ev_keys.clear()
        self.confirm = self.back = False

    def down(self, p, a): return a in self.held[p]
    def hit(self, p, a): return a in self.pressed[p]
    def any_hit(self, a): return self.hit("p1", a) or self.hit("p2", a)
