"""Pads and the dev keyboard, polled once per frame into a match.FrameInput.

Per pad there are two steering inputs: the stick (with the hat as a
fallback) and the four face buttons X Y B A laid out like W A S D. Which
player each one steers is the match's business (config.CONTROLS). In menus,
printed A (or Start) confirms and printed B goes back. Any button at all
(or, without --no-keyboard, any key) dismisses the HOW TO PLAY card, and
the buttons still held then are consumed until let go (consume_held), so
the press that dismissed it never steers.

The pure helpers (stick_direction, hat_direction, latest_direction,
should_quit) are unit tested; reading real pads is verified on the cabinet
with --input-test.
"""

from __future__ import annotations

import pygame

from qurves import config
from qurves.match import FrameInput
from qurves.rules import Vec

DIRECTIONS = {"up": (0, -1), "down": (0, 1), "left": (-1, 0), "right": (1, 0)}
PADS = (0, 1)

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


def latest_direction(order: list[str], held: set[str]) -> tuple[list[str], Vec | None]:
    """Track direction buttons in the order they went down, so holding two at
    once steers by the newer one. Returns (the updated order, the direction)."""
    order = [name for name in order if name in held]
    order += [name for name in DIRECTIONS if name in held and name not in order]
    return order, DIRECTIONS[order[-1]] if order else None


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
        self._order = {pad: [] for pad in PADS}
        self._down: dict[int, set[int]] = {pad: set() for pad in PADS}
        self._consumed: dict[int, set[int]] = {pad: set() for pad in PADS}
        self._raw: dict[int, set[int]] = {pad: set() for pad in PADS}
        self._key_pressed = False
        self._keys_down: set[str] = set()
        self._stick_prev: dict[int, Vec | None] = {pad: None for pad in PADS}
        self.stick: list[Vec | None] = [None, None]
        self.pad: list[Vec | None] = [None, None]
        self.nav: Vec | None = None
        self.confirm = self.back = self.pause = self.pick = self.any_button = False
        self.start_select = {pad: (False, False) for pad in PADS}
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
        elif event.type == pygame.KEYDOWN and _keyboard_enabled:
            self._key_pressed = True

    def consume_held(self) -> None:
        """Ignore every button held right now until it is let go."""
        for pad in PADS:
            self._consumed[pad] = set(self._raw[pad])

    def _read_pad(self, pad: int) -> tuple[set[int], Vec | None]:
        cfg = config.INPUT_CONFIG["pads"][pad]
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
        return down, direction

    def update(self, dt: float) -> None:
        keys = read_keys()
        system = config.INPUT_CONFIG["system"]
        self.keyboard_quit = keyboard_quit_held(keys)
        self.activity = self.keyboard_quit
        self.confirm = self.back = self.pause = self.pick = False
        self.any_button, self._key_pressed = self._key_pressed, False
        self.nav = None
        for pad in PADS:
            raw, stick = self._read_pad(pad)
            self._raw[pad] = raw
            self._consumed[pad] &= raw
            down = raw - self._consumed[pad]
            if stick is None:
                for name, vec in DIRECTIONS.items():
                    if any(keys[k] for k in self.keymap[("stick", pad)][name]):
                        stick = vec
                        break
            buttons = config.INPUT_CONFIG["pads"][pad]["buttons"]
            held = {name for name, nums in buttons.items() if down & set(nums)}
            held |= {name for name, codes in self.keymap[("pad", pad)].items() if any(keys[k] for k in codes)}
            self._order[pad], self.pad[pad] = latest_direction(self._order[pad], held)

            pressed = down - self._down[pad]
            self._down[pad] = down
            self.confirm |= bool(pressed & {*system["confirm_buttons"], system["start_button"]})
            self.back |= bool(pressed & set(system["back_buttons"]))
            self.pause |= system["start_button"] in pressed
            self.pick |= bool(pressed & set(system["confirm_buttons"]))
            self.any_button |= bool(pressed)
            # Raw, not down: Start + Select quits even with a consumed button.
            self.start_select[pad] = (system["start_button"] in raw, system["select_button"] in raw)

            if stick is not None and stick != self._stick_prev[pad] and self.nav is None:
                self.nav = stick
            self._stick_prev[pad] = stick
            self.stick[pad] = stick
            if raw or stick is not None or held:
                self.activity = True

        keys_now = {"confirm"} if any(keys[k] for k in self.confirm_keys) else set()
        keys_now |= {"back"} if any(keys[k] for k in self.back_keys) else set()
        keys_now |= {"pause"} if any(keys[k] for k in self.pause_keys) else set()
        new_keys = keys_now - self._keys_down
        self._keys_down = keys_now
        self.confirm |= "confirm" in new_keys
        self.pick |= "confirm" in new_keys
        self.back |= "back" in new_keys
        self.pause |= "pause" in new_keys
        self.activity |= bool(keys_now)

        if any(select for _start, select in self.start_select.values()):
            self.select_held_time += dt
        else:
            self.select_held_time = 0.0

    def frame_input(self) -> FrameInput:
        return FrameInput(stick=tuple(self.stick), pad=tuple(self.pad), nav=self.nav,
                          confirm=self.confirm, back=self.back, pause=self.pause, pick=self.pick,
                          any_button=self.any_button, activity=self.activity)

    def quit_combo(self) -> bool:
        (s0, sel0), (s1, sel1) = self.start_select[0], self.start_select[1]
        return should_quit(p1_start=s0, p1_select=sel0, p2_start=s1, p2_select=sel1)
