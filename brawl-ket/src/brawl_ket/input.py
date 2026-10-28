"""Pads and the keyboard, polled once per display frame.

Devices, pad layouts and the two-player keyboard are shared by all games (see
arqade_common.input). Per player: the analog stick (deadzoned; the d-pad and
the direction keys count too) and the A, B, X and Y buttons as edge-triggered
presses. Start confirms, pauses and starts; Select only joins Start for the
quit combo. Any button at all (L, R and Select too) going down is
`any_button`, which takes the HOW TO PLAY card away; with the keyboard on, so
does any key but the stick's. The pure helpers are unit tested; reading real
pads is verified on the cabinet with --input-test.
"""

from __future__ import annotations

import pygame
from arqade_common.input import (
    BUTTONS,
    DIRECTIONS,
    KEYBOARD,
    KEYBOARD_LAYOUT,
    LastDevice,
    PadLayout,
    PadSlots,
    default_pad_layout,
    read_player,
)

from . import config
from .fighter import FighterInput
from .match import FrameInput

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


# Which pad is whose, and how to read its buttons. main() calls
# set_pad_layout() and the game loop start_devices() once at start-up.
_pads = PadSlots()
_pad_layout = default_pad_layout()
# Keyboard or pad, per player, so on-screen hints name what they're holding.
_last_device = LastDevice()


def set_pad_layout(layout: PadLayout) -> None:
    global _pad_layout
    _pad_layout = layout


def pad_layout() -> PadLayout:
    return _pad_layout


def start_devices() -> None:
    """Pick up the pads already connected (call after pygame.joystick.init())."""
    _pads.scan()


def get_events() -> list[pygame.event.Event]:
    """pygame.event.get(), noting pads that connect or disconnect on the way.
    Every event loop in the game uses this instead of pygame.event.get():
    in a browser, a gamepad only appears after its first button press."""
    events = pygame.event.get()
    for event in events:
        _pads.handle_event(event)
        _last_device.handle_event(event, _pads, keyboard=_keyboard_enabled)
    return events


def last_device() -> LastDevice:
    """Who last used their keys or their pad, for the screens' button hints."""
    return _last_device


def nav_push(prev: tuple[int, int], now: tuple[int, int]) -> tuple[int, int]:
    """A menu step: each stick direction counts once, when it is pushed (no auto-repeat)."""
    return tuple(v if v and v != was else 0 for was, v in zip(prev, now))


# --- pure helpers ----------------------------------------------------------------------


def deadzone(value: float, dz: float = config.AXIS_DEADZONE) -> int:
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
    """Start + Select held together by one player. There is deliberately no
    quit key: Esc leaves fullscreen in a browser, and the PC launcher handles
    Esc itself (it ends the game process)."""
    return (p1_start and p1_select) or (p2_start and p2_select)


class Input:
    def __init__(self) -> None:
        self._buttons_prev: dict[str, frozenset[str]] = {p: frozenset() for p in PLAYERS}
        self._stick_prev: dict[str, tuple[int, int]] = {p: (0, 0) for p in PLAYERS}
        self.frame = FrameInput()
        self.start_select = {p: (False, False) for p in PLAYERS}
        self.select_held_time = 0.0     # seconds Select has been held on either side
        self._button_event = False      # a JOYBUTTONDOWN (or, with the keyboard on, a KEYDOWN)
        self._stick_keys = {getattr(pygame, KEYBOARD_LAYOUT[p][d]) for p in PLAYERS for d in DIRECTIONS}

    def handle(self, event: pygame.event.Event) -> None:
        if event.type == pygame.JOYBUTTONDOWN or (event.type == pygame.KEYDOWN and _keyboard_enabled
                                                   and event.key not in self._stick_keys):
            self._button_event = True

    def _read(self, player: str, keys) -> tuple[frozenset[str], int, bool, bool]:
        """(buttons held, dx, up, down) for one player, from their pad and keys."""
        pad = _pads.pad(PLAYERS.index(player))
        try:
            state = read_player(player, keys, pad, _pad_layout)
        except pygame.error:            # the pad went away mid-read
            state = read_player(player, keys, None, _pad_layout)
        dx = deadzone(state.stick_x)
        up, dn = vertical(state.stick_y)
        if dx == 0:                     # the d-pad or the direction keys
            dx = state["right"] - state["left"]
        up = up or state["up"]
        dn = dn or state["down"]
        return frozenset(b for b in BUTTONS if state[b]), dx, up, dn

    def update(self, dt: float) -> None:
        keys = read_keys()
        frame = FrameInput(any_button=self._button_event)
        self._button_event = False
        for p in PLAYERS:
            held, dx, up, dn = self._read(p, keys)
            pressed = edge_presses(self._buttons_prev[p], held)
            self._buttons_prev[p] = held
            a = "a" in pressed
            start_pressed = "start" in pressed
            frame.fighters[p] = FighterInput(dx=dx, up=up, down=dn, a=a, b="b" in pressed,
                                             x="x" in pressed, y="y" in pressed)
            frame.confirms[p] = a or start_pressed
            frame.backs[p] = "b" in pressed
            frame.pauses[p] = start_pressed
            frame.nav[p] = nav_push(self._stick_prev[p], (dx, dn - up))
            self._stick_prev[p] = (dx, dn - up)
            if held:
                frame.held = True
            if pressed:
                frame.any_button = True
            self.start_select[p] = ("start" in held, "select" in held)
            if held or dx or up or dn:
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


# --- button names, for on-screen hints ----------------------------------------------------


FACE_BUTTONS = ("a", "b", "x", "y", "l", "r")     # printed letters, unlike START or the stick


def mixed_devices(devices: LastDevice | None = None) -> bool:
    """One player on the keys, the other on a pad."""
    devices = devices or _last_device
    return len({devices[p] for p in PLAYERS}) > 1


def button_name(control: str, player: str | None = None, devices: LastDevice | None = None) -> str:
    """A control's on-screen name ("a", "start", "stick", ...) for one player's keys or pad,
    or for both players' when player is None (e.g. "SPACE / ENTER"; one name when both are
    on pads). "stick" is the stick or the direction keys."""
    devices = devices or _last_device
    if player is None:
        names = [button_name(control, p, devices) for p in PLAYERS]
        if control in FACE_BUTTONS and mixed_devices(devices):
            # one on keys, one on a pad: "B / A" would read as one button standing for
            # another, so say whose is whose ("P1 B / P2 A")
            return " / ".join(f"{p.upper()} {n}" for p, n in zip(PLAYERS, names))
        return " / ".join(dict.fromkeys(names))
    if control == "stick":
        if devices[player] == KEYBOARD:
            return "WASD" if player == "p1" else "ARROWS"
        return "STICK"
    return devices.label(control, player)
