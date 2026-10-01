"""Pads and the dev keyboard turned into per-player actions, polled once per frame.

The pure helpers (stick_direction, hat_direction, should_quit) are unit
tested; reading real pads is verified on the cabinet with --input-test.
Actions per player: "split" (printed A, which also confirms menus), "back"
(printed B), "start" and "select".
"""

from __future__ import annotations

import pygame

from qurves import config
from qurves.match import FrameInput
from qurves.rules import PLAYERS, Vec

DIRECTIONS = {"up": (0, -1), "down": (0, 1), "left": (-1, 0), "right": (1, 0)}
ACTIONS = ("split", "back", "start", "select")

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


def keyboard_quit_held(keys) -> bool:
    return bool(keys[getattr(pygame, config.INPUT_CONFIG["system"]["keyboard_quit"])])


def stick_direction(ax: float, ay: float, deadzone: float) -> Vec | None:
    """The stick's dominant axis past the deadzone, as a grid direction."""
    if abs(ax) <= deadzone and abs(ay) <= deadzone:
        return None
    if abs(ax) > abs(ay):
        return (1 if ax > 0 else -1, 0)
    return (0, 1 if ay > 0 else -1)


def hat_direction(hat: tuple[int, int]) -> Vec | None:
    """A hat switch as a grid direction (a hat's positive y is up)."""
    hx, hy = hat
    if hx:
        return (hx, 0)
    if hy:
        return (0, -hy)
    return None


def should_quit(*, p1_start: bool, p1_select: bool, p2_start: bool, p2_select: bool) -> bool:
    """Start + Select held together on the same pad."""
    return (p1_start and p1_select) or (p2_start and p2_select)


class Input:
    def __init__(self) -> None:
        self.joysticks: list = []
        self.keymap = {
            p: {act: [getattr(pygame, name) for name in names] for act, names in config.KEYMAP[p].items()}
            for p in PLAYERS
        }
        self.held: dict[str, set[str]] = {p: set() for p in PLAYERS}
        self.pressed: dict[str, set[str]] = {p: set() for p in PLAYERS}
        self.direction: dict[str, Vec | None] = {p: None for p in PLAYERS}
        self.select_held_time = 0.0
        self.keyboard_quit = False
        self.activity = False
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

    def _pad(self, player: str) -> tuple[set[str], Vec | None]:
        cfg = config.INPUT_CONFIG[player]
        if cfg["joystick_index"] >= len(self.joysticks):
            return set(), None
        joy = self.joysticks[cfg["joystick_index"]]
        try:
            down = {b for b in range(joy.get_numbuttons()) if joy.get_button(b)}
            ax_i, ay_i = cfg["axes"]
            ax = joy.get_axis(ax_i) if joy.get_numaxes() > ax_i else 0.0
            ay = joy.get_axis(ay_i) if joy.get_numaxes() > ay_i else 0.0
            direction = stick_direction(ax, ay, config.INPUT_CONFIG["axis_deadzone"])
            if direction is None and joy.get_numhats() > cfg["hat_index"]:
                direction = hat_direction(joy.get_hat(cfg["hat_index"]))
        except pygame.error:
            return set(), None
        held = {act for act, buttons in cfg["buttons"].items() if down & set(buttons)}
        system = config.INPUT_CONFIG["system"]
        if system["start_button"] in down:
            held.add("start")
        if system["select_button"] in down:
            held.add("select")
        return held, direction

    def update(self, dt: float) -> None:
        keys = read_keys()
        self.keyboard_quit = keyboard_quit_held(keys)
        self.activity = False
        for p in PLAYERS:
            held, direction = self._pad(p)
            keymap = self.keymap[p]
            for act in ACTIONS:
                if any(keys[k] for k in keymap.get(act, [])):
                    held.add(act)
            if direction is None:
                for name, vec in DIRECTIONS.items():
                    if any(keys[k] for k in keymap[name]):
                        direction = vec
                        break
            self.pressed[p] = held - self.held[p]
            self.held[p] = held
            self.direction[p] = direction
            if held or direction is not None:
                self.activity = True
        if any("select" in self.held[p] for p in PLAYERS):
            self.select_held_time += dt
        else:
            self.select_held_time = 0.0

    def frame_input(self) -> FrameInput:
        return FrameInput(
            direction=dict(self.direction),
            split={p: "split" in self.pressed[p] for p in PLAYERS},
            confirm=any(self.pressed[p] & {"split", "start"} for p in PLAYERS),
            back=any("back" in self.pressed[p] for p in PLAYERS),
            activity=self.activity,
        )

    def quit_combo(self) -> bool:
        a, b = self.held["p1"], self.held["p2"]
        return should_quit(
            p1_start="start" in a, p1_select="select" in a,
            p2_start="start" in b, p2_select="select" in b,
        )
