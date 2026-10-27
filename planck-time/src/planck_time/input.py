"""Pads and the keyboard, polled once per frame into a session.FrameInput.

Per player, in a microgame: the analog stick (deadzoned, -1..1), stick
steps (a push past half way, auto-repeated, for cursors and grids), and A
pressed and held. In menus the same steps navigate, A (or Start) confirms
and B goes back. Start pauses. Any button at all (or, for dev, any key)
counts as a press, for the HOW TO PLAY card. Devices, button layouts and
the two-player keyboard are shared by all games (arqade_common.input). The pure helpers are unit tested; reading
real pads is verified on the cabinet with --input-test.
"""

from __future__ import annotations

import pygame
from arqade_common.input import LastDevice, PadLayout, PadSlots, default_pad_layout, read_player

from planck_time import config
from planck_time.microgames import PlayerInput
from planck_time.session import PLAYERS, FrameInput

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


def deadzone(value: float, dz: float = config.INPUT_CONFIG["axis_deadzone"]) -> float:
    """An axis value with the deadzone cut out and the rest rescaled to 0..1."""
    if abs(value) <= dz:
        return 0.0
    sign = 1.0 if value > 0 else -1.0
    return sign * min(1.0, (abs(value) - dz) / (1.0 - dz))


def step_sign(value: float, threshold: float = config.INPUT_CONFIG["step_threshold"]) -> int:
    if value <= -threshold:
        return -1
    if value >= threshold:
        return 1
    return 0


def should_quit(*, p1_start: bool, p1_select: bool, p2_start: bool, p2_select: bool) -> bool:
    """Start + Select held together by one player. There is deliberately no
    quit key: Esc leaves fullscreen in a browser, and the PC launcher handles
    Esc itself (it ends the game process)."""
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
    def __init__(self, pad_layout: PadLayout | None = None) -> None:
        # Which pad is whose: pads join P1 then P2 as they appear (in a
        # browser, only after their first button press).
        self.pads = PadSlots()
        self.pad_layout = pad_layout or default_pad_layout()
        # Keyboard or pad, per player, so on-screen hints name what they're holding.
        self.devices = LastDevice()
        self.repeat_x = {p: AutoRepeat() for p in PLAYERS}
        self.repeat_y = {p: AutoRepeat() for p in PLAYERS}
        self._held_prev: dict[str, frozenset[str]] = {p: frozenset() for p in PLAYERS}
        self.frame = FrameInput()
        self.start_select = {p: (False, False) for p in PLAYERS}
        self.select_held_time = 0.0
        self._key_pressed = False  # any key went down since the last update
        self.pads.scan()

    def handle(self, event: pygame.event.Event) -> None:
        self.pads.handle_event(event)
        self.devices.handle_event(event, self.pads, keyboard=_keyboard_enabled)
        if event.type == pygame.KEYDOWN and _keyboard_enabled:
            self._key_pressed = True

    def _read(self, player: str):
        """(buttons and directions held, stick x, stick y), the stick deadzoned
        with y positive = down. Keys and the d-pad stand in for a centred stick."""
        pad = self.pads.pad(PLAYERS.index(player))
        try:
            state = read_player(player, read_keys(), pad, self.pad_layout)
        except pygame.error:  # the pad went away mid-read
            state = read_player(player, read_keys(), None, self.pad_layout)
        x, y = deadzone(state.stick_x), deadzone(state.stick_y)
        if x == 0:
            x = float(state["right"]) - float(state["left"])
        if y == 0:
            y = float(state["down"]) - float(state["up"])
        return state.held, x, y

    def update(self, dt: float) -> None:
        frame = FrameInput()
        for p in PLAYERS:
            held, x, y = self._read(p)
            pressed = held - self._held_prev[p]
            self._held_prev[p] = held
            step = (self.repeat_x[p].update(dt, step_sign(x)), self.repeat_y[p].update(dt, step_sign(y)))
            a = "a" in pressed
            frame.players[p] = PlayerInput((x, y), step, a, "a" in held)
            frame.nav[p] = step
            frame.confirms[p] = a or "start" in pressed
            frame.backs[p] = "b" in pressed
            frame.pauses[p] = "start" in pressed
            frame.presses[p] = bool(pressed)
            self.start_select[p] = ("start" in held, "select" in held)
            if held or x or y:
                frame.activity = True
        if self._key_pressed:  # any key at all, not just the mapped ones (the HOW TO PLAY card)
            frame.presses["p1"] = frame.activity = True
            self._key_pressed = False
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
