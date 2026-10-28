"""The pads and the keyboard, read once per frame into a match.FrameInput.

Devices, pad layouts and the two-player keyboard are shared by all the games
(arqade_common.input): every pad is read by its printed buttons (A, B, X, Y, L, R, Start,
Select), never raw numbers, and the keys stand in for each player's stick and buttons.

Per player: the stick's axis 0 steers (deadzoned, rescaled to -1..1) and axis 1 pulled
back (positive) brakes; pushed forward it does nothing in a race. The d-pad and the
direction keys count as a stick pushed all the way. In menus the stick gives auto-repeated
steps. A, B and Start come as presses (the frame they go down), `button` is any button at
all going down (for the HOW TO PLAY card; with the keyboard on, also any key that is not a
direction) and `held` says whether A, B, Start or Select is down. On the cabinet the stick
is an analog axis, never a hat (it has none).

Pads join P1 and then P2 as they appear (in a browser only after their first button
press). Joysticks that can't be a player's pad (fewer buttons than Start's number, or a
laptop's accelerometer) are skipped, so the first real pad is P1 and the second P2.

Presses are also latched from the KEYDOWN and JOYBUTTONDOWN events (`handle`), so a tap
quicker than a frame, down and up again between two polls, still counts once.

The quit is edge-triggered and armed: Start + Select on one pad (or one player's keys) must
be seen *not* held before it counts, so a combo already down when the game starts (a stuck
button, the keys that launched it) can't quit it at once. There is no quit key: Esc leaves
fullscreen in a browser, and the PC launcher catches Esc itself.

`--no-keyboard` (the cabinet's loader) turns the keyboard off: Batocera's evmapy types keys
for P1's pad, which would otherwise double its presses.
"""

from __future__ import annotations

import pygame
from arqade_common.input import (
    DIRECTIONS,
    KEYBOARD_LAYOUT,
    LastDevice,
    PadLayout,
    PadSlots,
    PlayerState,
    default_pad_layout,
    read_player,
)

from gate_prix import config
from gate_prix.match import PLAYERS, FrameInput, PlayerInput

_keyboard_enabled = True

MENU_BUTTONS = frozenset({"a", "b", "start", "select"})  # what PlayerInput.held is about
# Every key of the shared layout, by key code: (player, button or direction).
_KEYS = {getattr(pygame, name): (p, action)
         for p, keys in KEYBOARD_LAYOUT.items() for action, name in keys.items()}


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
    return pygame.key.get_pressed() if _keyboard_enabled else _NoKeys()


def deadzone(value: float, dz: float = config.AXIS_DEADZONE) -> float:
    """An axis value with the deadzone cut out and the rest rescaled to 0..1."""
    if abs(value) <= dz:
        return 0.0
    sign = 1.0 if value > 0 else -1.0
    return sign * min(1.0, (abs(value) - dz) / (1.0 - dz))


def step_sign(value: float, threshold: float = config.STEP_THRESHOLD) -> int:
    if value <= -threshold:
        return -1
    if value >= threshold:
        return 1
    return 0


def is_pad(joy, layout: PadLayout | None = None) -> bool:
    """Whether a joystick can be a player's pad (one with Start and Select, in `layout`)."""
    buttons = (layout or default_pad_layout()).buttons
    try:
        name = joy.get_name().lower()
        count = joy.get_numbuttons()
    except pygame.error:
        return False
    if "accelerometer" in name or "motion sensor" in name:
        return False
    return count > max(buttons["start"], buttons["select"])


class _Pads(PadSlots):
    """PadSlots that pass over joysticks that can't be a player's pad (see is_pad)."""

    def __init__(self, layout: PadLayout) -> None:
        super().__init__()
        self.layout = layout

    def _add(self, device_index: int) -> None:
        try:
            joy = pygame.joystick.Joystick(device_index)
        except pygame.error:
            return
        if is_pad(joy, self.layout):
            super()._add(device_index)


class AutoRepeat:
    """Turns a held direction (-1, 0 or 1) into presses: one at once, then one after
    REPEAT_DELAY, then one every REPEAT_INTERVAL."""

    def __init__(self, delay: float = config.REPEAT_DELAY,
                 interval: float = config.REPEAT_INTERVAL) -> None:
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


class _Edge:
    """True on the frame a condition becomes true, but only once it has been seen false."""

    def __init__(self) -> None:
        self.armed = False
        self.was = False

    def update(self, now: bool) -> bool:
        fired = now and not self.was and self.armed
        if not now:
            self.armed = True
        self.was = now
        return fired


class Input:
    def __init__(self, pad_layout: PadLayout | None = None) -> None:
        self.layout = pad_layout or default_pad_layout()
        self.pads = _Pads(self.layout)
        # Keyboard or pad, per player, so the on-screen hints name what they're holding.
        self.devices = LastDevice()
        self.repeat_x = {p: AutoRepeat() for p in PLAYERS}
        self.repeat_y = {p: AutoRepeat() for p in PLAYERS}
        self._held: dict[str, frozenset[str]] = {p: frozenset() for p in PLAYERS}
        self._raw: dict[str, set[int]] = {p: set() for p in PLAYERS}  # pad buttons down
        self._combo = {p: _Edge() for p in PLAYERS}
        self._key_taps: set[int] = set()  # KEYDOWNs since the last update
        self._button_taps: set[tuple[int, int]] = set()  # (instance id, button) likewise
        self._quit = False
        self.frame = FrameInput()
        self.pads.scan()

    def handle(self, event) -> None:
        self.pads.handle_event(event)
        self.devices.handle_event(event, self.pads, keyboard=_keyboard_enabled)
        if event.type == pygame.KEYDOWN and _keyboard_enabled:
            self._key_taps.add(event.key)
        elif event.type == pygame.JOYBUTTONDOWN:
            iid = getattr(event, "instance_id", getattr(event, "joy", None))
            self._button_taps.add((iid, event.button))

    def _raw_taps(self, slot: int) -> set[int]:
        """The raw buttons this player's pad reported going down since the last update."""
        pad = self.pads.pad(slot)
        if pad is None or not self._button_taps:
            return set()
        try:
            iid = pad.get_instance_id()
        except (pygame.error, AttributeError):
            return set()
        return {b for i, b in self._button_taps if i == iid}

    def _tapped(self, player: str, raw_taps: set[int]) -> set[str]:
        """The buttons and directions a player tapped since the last update, by name: from
        the pad's JOYBUTTONDOWNs (its d-pad too, when the layout has one) and their keys."""
        layout = self.layout
        named = {b for b, raw in layout.buttons.items() if raw in raw_taps}
        named |= {d for d, raw in layout.dpad_buttons.items() if raw in raw_taps}
        for key in self._key_taps:
            owner, action = _KEYS.get(key, (None, None))
            if owner == player:
                named.add(action)
        return named

    def _read(self, player: str, slot: int, keys) -> tuple[PlayerState, set[int]]:
        """(the player's keys and pad by name, the pad's raw buttons down)."""
        pad = self.pads.pad(slot)
        try:
            state = read_player(player, keys, pad, self.layout)
            raw = ({b for b in range(pad.get_numbuttons()) if pad.get_button(b)}
                   if pad is not None else set())
        except pygame.error:  # the pad went away mid-read
            return read_player(player, keys, None, self.layout), set()
        return state, raw

    def update(self, dt: float) -> None:
        keys = read_keys()
        dpad = set(self.layout.dpad_buttons.values())
        # any other key at all (not a stick's) goes on from the HOW TO PLAY card, as P1's
        other_key = any(key not in _KEYS for key in self._key_taps)
        frame = FrameInput(activity=other_key)
        quit_now = False
        for slot, p in enumerate(PLAYERS):
            state, raw = self._read(p, slot, keys)
            raw_taps = self._raw_taps(slot)
            tapped = self._tapped(p, raw_taps)
            held = state.held
            steer = deadzone(state.stick_x)
            if steer == 0.0:
                steer = float(("right" in held) - ("left" in held))
            pull = deadzone(state.stick_y)
            if pull == 0.0:
                pull = float(("down" in held) - ("up" in held))
            pressed = (held - self._held[p]) | tapped
            raw_pressed = ((raw - self._raw[p]) | raw_taps) - dpad
            self._held[p], self._raw[p] = held, raw
            stick = (step_sign(steer), step_sign(pull))
            nav_x = self.repeat_x[p].update(dt, stick[0])
            nav_y = self.repeat_y[p].update(dt, stick[1])
            nav = (nav_x or ("right" in tapped) - ("left" in tapped),
                   nav_y or ("down" in tapped) - ("up" in tapped))
            frame.players[p] = PlayerInput(
                steer=steer,
                brake=max(0.0, pull),
                nav=nav,
                stick=stick,
                a="a" in pressed,
                b="b" in pressed,
                start="start" in pressed,
                select="select" in pressed,
                button=(bool(raw_pressed) or bool(pressed - set(DIRECTIONS))
                        or (slot == 0 and other_key)),
                held=bool(held & MENU_BUTTONS),
            )
            if self._combo[p].update("start" in held and "select" in held):
                quit_now = True
            if held or raw or steer or pull or pressed or raw_pressed:
                frame.activity = True
        self._key_taps.clear()
        self._button_taps.clear()
        self._quit = quit_now
        self.frame = frame

    def quit_combo(self) -> bool:
        """Start + Select went down together on one pad (or one player's keys) this frame."""
        return self._quit
