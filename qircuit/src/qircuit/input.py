"""Pads and the dev keyboard, polled once per frame into a match.FrameInput.

Per pad there are two input sources: the stick (with the hat as a fallback)
and the four face buttons X Y B A laid out like W A S D. Each source reports
which of up/down/left/right are held, and which were newly pressed; which
player a source drives is the match's business (config.CONTROLS). In menus,
printed A (or Start) confirms and printed B goes back. Any button at all
(from the events, either pad) dismisses the HOW TO PLAY card.

The pure helpers (stick_held, hat_held, menu_direction, should_quit) are
unit tested; reading real pads is verified on the cabinet with --input-test.
"""

from __future__ import annotations

import pygame

from qircuit import config
from qircuit.match import FrameInput

DIRECTIONS = {"up": (0, -1), "down": (0, 1), "left": (-1, 0), "right": (1, 0)}
PADS = (0, 1)
SOURCES = tuple((kind, pad) for pad in PADS for kind in ("stick", "pad"))

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


def stick_held(ax: float, ay: float, deadzone: float) -> set[str]:
    """Every direction the stick is pushed past the deadzone: up-right is
    faster and a wire change at once."""
    held = set()
    if ay < -deadzone:
        held.add("up")
    elif ay > deadzone:
        held.add("down")
    if ax < -deadzone:
        held.add("left")
    elif ax > deadzone:
        held.add("right")
    return held


def hat_held(hat: tuple[int, int]) -> set[str]:
    """A hat switch's directions (a hat's positive y is up)."""
    hx, hy = hat
    held = set()
    if hy > 0:
        held.add("up")
    elif hy < 0:
        held.add("down")
    if hx < 0:
        held.add("left")
    elif hx > 0:
        held.add("right")
    return held


def menu_direction(pressed: set[str]) -> tuple[int, int] | None:
    """One menu step from newly pressed directions; vertical wins a diagonal."""
    for name in ("up", "down", "left", "right"):
        if name in pressed:
            return DIRECTIONS[name]
    return None


def should_quit(*, p1_start: bool, p1_select: bool, p2_start: bool, p2_select: bool) -> bool:
    """Start + Select held together on the same pad."""
    return (p1_start and p1_select) or (p2_start and p2_select)


class Input:
    def __init__(self) -> None:
        self.joysticks: list = []
        self.keymap = {src: {name: _codes(keys) for name, keys in m.items()} for src, m in config.KEYMAP.items()}
        self.confirm_keys = _codes(config.KEYS_CONFIRM)
        self.back_keys = _codes(config.KEYS_BACK)
        self.pause_keys = _codes(config.KEYS_PAUSE)
        self._down: dict[int, set[int]] = {pad: set() for pad in PADS}
        self._held_prev: dict = {src: set() for src in SOURCES}
        self._keys_down: set[str] = set()
        self.held: dict = {src: set() for src in SOURCES}
        self.pressed: dict = {src: set() for src in SOURCES}
        self.nav: tuple[int, int] | None = None
        self.confirm = self.back = self.pause = self.pick = False
        self.pad_a = [False, False]
        self.pad_b = [False, False]
        self.start_select = {pad: (False, False) for pad in PADS}
        self.keyboard_quit = False
        self.activity = False
        self.any_button = False
        self._hit = False  # a button or key went down since the last update
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
        elif event.type == pygame.JOYBUTTONDOWN or (event.type == pygame.KEYDOWN and _keyboard_enabled):
            self._hit = True  # from the events, so even a tap shorter than a frame counts

    def _read_pad(self, pad: int) -> tuple[set[int], set[str]]:
        cfg = config.INPUT_CONFIG["pads"][pad]
        if cfg["joystick_index"] >= len(self.joysticks):
            return set(), set()
        joy = self.joysticks[cfg["joystick_index"]]
        try:
            down = {b for b in range(joy.get_numbuttons()) if joy.get_button(b)}
            ax_i, ay_i = cfg["axes"]
            ax = joy.get_axis(ax_i) if joy.get_numaxes() > ax_i else 0.0
            ay = joy.get_axis(ay_i) if joy.get_numaxes() > ay_i else 0.0
            stick = stick_held(ax, ay, config.INPUT_CONFIG["axis_deadzone"])
            if not stick and joy.get_numhats() > cfg["hat_index"]:
                stick = hat_held(joy.get_hat(cfg["hat_index"]))
        except pygame.error:
            return set(), set()
        return down, stick

    def update(self, dt: float) -> None:
        keys = read_keys()
        system = config.INPUT_CONFIG["system"]
        self.keyboard_quit = bool(keys[getattr(pygame, system["keyboard_quit"])])
        self.activity = self.keyboard_quit
        self.confirm = self.back = self.pause = self.pick = False
        self.pad_a = [False, False]
        self.pad_b = [False, False]
        self.nav = None
        for pad in PADS:
            down, stick = self._read_pad(pad)
            stick |= {name for name, codes in self.keymap[("stick", pad)].items() if any(keys[k] for k in codes)}
            buttons = config.INPUT_CONFIG["pads"][pad]["buttons"]
            face = {name for name, raw in buttons.items() if down & set(raw)}
            face |= {name for name, codes in self.keymap[("pad", pad)].items() if any(keys[k] for k in codes)}
            for src, held in ((("stick", pad), stick), (("pad", pad), face)):
                self.pressed[src] = held - self._held_prev[src]
                self.held[src] = held
                self._held_prev[src] = held
            if self.nav is None:
                self.nav = menu_direction(self.pressed[("stick", pad)])

            pressed = down - self._down[pad]
            self._down[pad] = down
            self.confirm |= bool(pressed & {*system["confirm_buttons"], system["start_button"]})
            self.back |= bool(pressed & set(system["back_buttons"]))
            self.pause |= system["start_button"] in pressed
            self.pick |= bool(pressed & set(system["confirm_buttons"]))
            self.pad_a[pad] = bool(pressed & set(system["confirm_buttons"]))
            self.pad_b[pad] = bool(pressed & set(system["back_buttons"]))
            self.start_select[pad] = (system["start_button"] in down, system["select_button"] in down)
            if down or stick or face:
                self.activity = True

        keys_now = {"confirm"} if any(keys[k] for k in self.confirm_keys) else set()
        keys_now |= {"back"} if any(keys[k] for k in self.back_keys) else set()
        keys_now |= {"pause"} if any(keys[k] for k in self.pause_keys) else set()
        new_keys = keys_now - self._keys_down
        self._keys_down = keys_now
        self.confirm |= "confirm" in new_keys
        self.pick |= "confirm" in new_keys
        self.pad_a[0] |= "confirm" in new_keys  # Enter locks P1's racer in
        self.pad_b[0] |= "back" in new_keys
        self.back |= "back" in new_keys
        self.pause |= "pause" in new_keys
        self.activity |= bool(keys_now)
        self.any_button, self._hit = self._hit, False
        self.activity |= self.any_button

    def frame_input(self) -> FrameInput:
        return FrameInput(held={k: frozenset(v) for k, v in self.held.items()},
                          pressed={k: frozenset(v) for k, v in self.pressed.items()},
                          nav=self.nav, confirm=self.confirm, back=self.back, pause=self.pause,
                          pick=self.pick, activity=self.activity,
                          pad_a=tuple(self.pad_a), pad_b=tuple(self.pad_b), any_button=self.any_button)

    def quit_combo(self) -> bool:
        (s0, sel0), (s1, sel1) = self.start_select[0], self.start_select[1]
        return should_quit(p1_start=s0, p1_select=sel0, p2_start=s1, p2_select=sel1)
