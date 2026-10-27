"""Controllers and keyboards, turned into the same named buttons everywhere.

Every game reads the pad's printed buttons (A, B, X, Y, L, R, Start, Select)
and its stick or d-pad, never raw button numbers. Which raw number is which
button depends on the hardware, so that lives in a PadLayout:

- ENCODER: the cabinet's arcade sticks (and the PC launcher's keyboard pads,
  which imitate them). The default on the cabinet and on a PC.
- STANDARD: the browser's "standard" gamepad mapping, which browsers apply to
  most Xbox/PlayStation/Switch pads. The default in the browser.
- XBOX: an Xbox-style pad on a PC (SDL's raw numbering). Opt-in with the
  games' --pad-layout flag.

The keyboard has one fixed layout, two players side by side, each with a
stick and the pad's 2x3 button grid (see KEYBOARD_LAYOUT).

Pads are handed to players by PadSlots as they appear, so a browser gamepad
that only shows up after its first button press still becomes P1 or P2.

On-screen hints should name what each player actually holds: LastDevice
remembers whether a player last used their keys or their pad, and label()
names a button for that device ("SPACE" on the keyboard, "START" on a pad).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping

import pygame

from arqade_common.runtime import is_browser

PLAYERS = ("p1", "p2")
DIRECTIONS = ("up", "down", "left", "right")
BUTTONS = ("a", "b", "x", "y", "l", "r", "start", "select")


@dataclass(frozen=True)
class PadLayout:
    name: str
    buttons: Mapping[str, int]  # printed button -> raw button number
    stick_axes: tuple[int, int] = (0, 1)  # (left/right, up/down); negative is left/up
    dpad_buttons: Mapping[str, int] = field(default_factory=dict)  # direction -> raw button
    dpad_hat: int | None = None  # raw hat number, for pads that report the d-pad as a hat


# Confirmed on the cabinet (AGENTS.md, "Button convention"). Note Start is 9
# and Select is 8, not the other way round. The stick is analog, no d-pad.
ENCODER = PadLayout(
    name="encoder",
    buttons={"x": 0, "a": 1, "b": 2, "y": 3, "l": 4, "r": 5, "select": 8, "start": 9},
)

# https://www.w3.org/TR/gamepad/#remapping -- A is the bottom face button.
STANDARD = PadLayout(
    name="standard",
    buttons={"a": 0, "b": 1, "x": 2, "y": 3, "l": 4, "r": 5, "select": 8, "start": 9},
    dpad_buttons={"up": 12, "down": 13, "left": 14, "right": 15},
)

XBOX = PadLayout(
    name="xbox",
    buttons={"a": 0, "b": 1, "x": 2, "y": 3, "l": 4, "r": 5, "select": 6, "start": 7},
    dpad_hat=0,
)

PAD_LAYOUTS = {layout.name: layout for layout in (ENCODER, STANDARD, XBOX)}


def default_pad_layout() -> PadLayout:
    return STANDARD if is_browser() else ENCODER


# pygame key constant names, so the table reads like the controls card.
# Only keys that sit in the same place on QWERTY and QWERTZ (no Y or Z).
KEYBOARD_LAYOUT: dict[str, dict[str, str]] = {
    "p1": {
        "up": "K_w", "left": "K_a", "down": "K_s", "right": "K_d",
        "l": "K_f", "x": "K_g", "r": "K_h",
        "y": "K_c", "b": "K_v", "a": "K_b",
        "start": "K_SPACE", "select": "K_LSHIFT",
    },
    "p2": {
        "up": "K_UP", "left": "K_LEFT", "down": "K_DOWN", "right": "K_RIGHT",
        "l": "K_u", "x": "K_i", "r": "K_o",
        "y": "K_j", "b": "K_k", "a": "K_l",
        "start": "K_RETURN", "select": "K_RSHIFT",
    },
}


@dataclass(frozen=True)
class PlayerState:
    """One player's controls in one frame, from their keys and their pad.

    `held` has every direction and button that is down. Keys and the d-pad
    count as directions; the analog stick does not -- it is in stick_x/y
    (-1..1), so each game keeps its own deadzone and feel.
    """

    held: frozenset[str] = frozenset()
    stick_x: float = 0.0
    stick_y: float = 0.0

    def __getitem__(self, name: str) -> bool:
        return name in self.held


class PadSlots:
    """Which connected pad belongs to which player.

    A pad takes the first free slot when it appears and frees it when it is
    unplugged; a third pad is ignored. On the cabinet both pads are there at
    start-up, so P1 gets pad 0 and P2 pad 1, as before. Call scan() once
    after pygame.joystick.init(), and handle_event() for every event.
    """

    def __init__(self, players: int = len(PLAYERS)) -> None:
        self._pads: list = [None] * players

    def scan(self) -> None:
        for device_index in range(pygame.joystick.get_count()):
            self._add(device_index)

    def handle_event(self, event: pygame.event.Event) -> None:
        if event.type == pygame.JOYDEVICEADDED:
            self._add(event.device_index)
        elif event.type == pygame.JOYDEVICEREMOVED:
            self._pads = [p if p is None or p.get_instance_id() != event.instance_id else None
                          for p in self._pads]

    def pad(self, slot: int):
        """The pad of player `slot` (0 = P1), or None."""
        return self._pads[slot] if slot < len(self._pads) else None

    def slot_of(self, instance_id: int) -> int | None:
        """Which player's pad this is (0 = P1), or None for an unassigned pad."""
        for slot, pad in enumerate(self._pads):
            if pad is not None and pad.get_instance_id() == instance_id:
                return slot
        return None

    def _add(self, device_index: int) -> None:
        try:
            pad = pygame.joystick.Joystick(device_index)
            if not pad.get_init():
                pad.init()
        except pygame.error:
            return  # gone again before we got to it
        instance_id = pad.get_instance_id()
        if any(p is not None and p.get_instance_id() == instance_id for p in self._pads):
            return  # scan() and JOYDEVICEADDED both report pads present at start-up
        if None in self._pads:
            self._pads[self._pads.index(None)] = pad


def read_player(player: str, keys, pad, layout: PadLayout) -> PlayerState:
    """Combine one player's keyboard keys and pad into a PlayerState.

    `keys` is pygame.key.get_pressed() (or anything indexable the same way,
    e.g. an all-released stand-in when a game ignores the keyboard); `pad`
    is a pygame Joystick or None.
    """
    held = {action for action, key in KEYBOARD_LAYOUT[player].items() if keys[getattr(pygame, key)]}
    stick_x = stick_y = 0.0

    if pad is not None:
        num_buttons = pad.get_numbuttons()
        for action, index in (*layout.buttons.items(), *layout.dpad_buttons.items()):
            if index < num_buttons and pad.get_button(index):
                held.add(action)
        if layout.dpad_hat is not None and layout.dpad_hat < pad.get_numhats():
            hat_x, hat_y = pad.get_hat(layout.dpad_hat)  # hat y is +1 for up
            held.update(name for name, on in (("left", hat_x < 0), ("right", hat_x > 0),
                                              ("up", hat_y > 0), ("down", hat_y < 0)) if on)
        axis_x, axis_y = layout.stick_axes
        num_axes = pad.get_numaxes()
        if axis_x < num_axes:
            stick_x = pad.get_axis(axis_x)
        if axis_y < num_axes:
            stick_y = pad.get_axis(axis_y)

    return PlayerState(frozenset(held), stick_x, stick_y)


# --- Which device each player is using, and what to call its buttons ---

KEYBOARD = "keyboard"
PAD = "pad"

# How far a stick must move before it counts as "using the pad", so a pad
# lying on the table with a drifting stick doesn't take over the hints.
_STICK_THRESHOLD = 0.5

# Keys whose pygame names don't read well on screen. Letters are upper-cased.
_KEY_NAMES = {
    "K_SPACE": "SPACE", "K_RETURN": "ENTER",
    "K_LSHIFT": "L-SHIFT", "K_RSHIFT": "R-SHIFT",
    "K_UP": "UP", "K_DOWN": "DOWN", "K_LEFT": "LEFT", "K_RIGHT": "RIGHT",
}

# Pads show their printed names (Xbox-style letters: browsers can't reliably
# tell an Xbox pad from a PlayStation one).
_PAD_NAMES = {"a": "A", "b": "B", "x": "X", "y": "Y", "l": "L", "r": "R",
              "start": "START", "select": "SELECT",
              "up": "UP", "down": "DOWN", "left": "LEFT", "right": "RIGHT"}


def default_device() -> str:
    """What to show before anyone has pressed anything: in the browser most
    people play on the keyboard; elsewhere (the cabinet) it's the pads."""
    return KEYBOARD if is_browser() else PAD


def label(action: str, player: str, device: str) -> str:
    """The on-screen name of a button or direction for one player's device,
    e.g. label("start", "p1", KEYBOARD) == "SPACE"."""
    if device == KEYBOARD:
        key = KEYBOARD_LAYOUT[player][action]
        return _KEY_NAMES.get(key, key.removeprefix("K_").upper())
    return _PAD_NAMES[action]


class LastDevice:
    """Remembers, per player, whether they last pressed a key or a pad button.

    Feed it every event (handle_event); the hints then follow each player as
    they switch. `latest` is the player who pressed something most recently,
    for hints that only one player reads at a time (a pause menu, say).
    """

    def __init__(self, default: str | None = None) -> None:
        start = default or default_device()
        self._devices = {player: start for player in PLAYERS}
        self.latest = PLAYERS[0]

    def __getitem__(self, player: str) -> str:
        return self._devices[player]

    def handle_event(self, event: pygame.event.Event, pads: PadSlots, *, keyboard: bool = True) -> None:
        """Note who used what. `keyboard=False` ignores key presses (the
        cabinet, where Batocera fakes key presses from P1's pad)."""
        player, device = None, None
        if event.type == pygame.KEYDOWN and keyboard:
            player, device = _player_of_key(event.key), KEYBOARD
        elif event.type in (pygame.JOYBUTTONDOWN, pygame.JOYHATMOTION, pygame.JOYAXISMOTION):
            moved = (event.type == pygame.JOYBUTTONDOWN
                     or (event.type == pygame.JOYHATMOTION and event.value != (0, 0))
                     or (event.type == pygame.JOYAXISMOTION and abs(event.value) > _STICK_THRESHOLD))
            slot = pads.slot_of(event.instance_id) if moved else None
            if slot is not None:
                player, device = PLAYERS[slot], PAD
        if player is not None:
            self._devices[player] = device
            self.latest = player

    def label(self, action: str, player: str) -> str:
        """label() for this player's current device."""
        return label(action, player, self._devices[player])

    def shared_label(self, action: str) -> str:
        """A name for a screen both players read, e.g. "SPACE / ENTER" when
        both are on the keyboard, "START" when both are on pads."""
        names = dict.fromkeys(self.label(action, player) for player in PLAYERS)
        return " / ".join(names)

    def everyone_on(self, device: str) -> bool:
        return all(d == device for d in self._devices.values())


def _player_of_key(key: int) -> str | None:
    for player, keys in KEYBOARD_LAYOUT.items():
        if any(getattr(pygame, name) == key for name in keys.values()):
            return player
    return None
