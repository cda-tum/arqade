"""The pads and the dev keyboard, read once per frame into a match.FrameInput.

Per player: the stick's axis 0 steers (deadzoned, rescaled to -1..1) and axis 1 pulled
back (positive) brakes; pushed forward it does nothing in a race. In menus the stick gives
auto-repeated steps. A, B and Start come as presses (the frame they go down), `button` is
any button at all going down (for the HOW TO PLAY card) and `held` says whether A, B, Start
or Select is down. Raw button numbers are the cabinet's
(config.INPUT_CONFIG): A = 1, B = 2, Select = 8, Start = 9. The stick is read from the
axes, never a hat (the cabinet has none).

Joysticks that can't be one of the cabinet's pads (fewer buttons than Start's number, or a
laptop's accelerometer) are skipped, so the first real pad is P1 and the second P2.

Presses are also latched from the KEYDOWN and JOYBUTTONDOWN events (`handle`), so a tap
quicker than a frame, down and up again between two polls, still counts once.

The quits are edge-triggered and armed: Start + Select on one pad (or Esc) must be seen
*not* held before it counts, so a combo already down when the game starts (a stuck
button, the keys that launched it) can't quit it at once.

The keyboard is a dev fallback, merged into each player's pad:
- P1: S / F steer, D brakes, E up, Q is A, W is B, 1 Start, 3 Select (never l x r b y a,
  which the cabinet's P1 encoder also types);
- P2: the arrows (Down brakes), "." is A, "," is B, 2 Start, 4 Select.
`--no-keyboard` (the cabinet's loader) turns it off.
"""

from __future__ import annotations

import pygame

from gate_prix import config
from gate_prix.match import PLAYERS, FrameInput, PlayerInput

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


def is_pad(joy) -> bool:
    """Whether a joystick can be one of the cabinet's pads."""
    system = config.INPUT_CONFIG["system"]
    try:
        name = joy.get_name().lower()
        buttons = joy.get_numbuttons()
    except pygame.error:
        return False
    if "accelerometer" in name or "motion sensor" in name:
        return False
    return buttons > max(system["start_button"], system["select_button"])


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
    def __init__(self) -> None:
        self.pads: list = []
        self.keymap = {p: {act: [getattr(pygame, n) for n in names]
                           for act, names in config.KEYMAP[p].items()} for p in PLAYERS}
        self.repeat_x = {p: AutoRepeat() for p in PLAYERS}
        self.repeat_y = {p: AutoRepeat() for p in PLAYERS}
        self._down: dict[str, set[int]] = {p: set() for p in PLAYERS}
        self._keys_prev: dict[str, set[str]] = {p: set() for p in PLAYERS}
        self._combo = {p: _Edge() for p in PLAYERS}
        self._escape = _Edge()
        self._key_taps: set[int] = set()  # KEYDOWNs since the last update
        self._button_taps: set[tuple[int, int]] = set()  # (instance id, button) likewise
        self._quit = False
        self.keyboard_quit = False
        self.frame = FrameInput()
        self.rescan()

    def rescan(self) -> None:
        self.pads = []
        for i in range(pygame.joystick.get_count()):
            try:
                joy = pygame.joystick.Joystick(i)
                joy.init()
            except pygame.error:
                continue
            if is_pad(joy):
                self.pads.append(joy)

    def handle(self, event) -> None:
        if event.type in (pygame.JOYDEVICEADDED, pygame.JOYDEVICEREMOVED):
            self.rescan()
        elif event.type == pygame.KEYDOWN and _keyboard_enabled:
            self._key_taps.add(event.key)
        elif event.type == pygame.JOYBUTTONDOWN:
            iid = getattr(event, "instance_id", getattr(event, "joy", None))
            self._button_taps.add((iid, event.button))

    def _taps(self, player: str) -> set[int]:
        """The buttons this player's pad reported going down since the last update."""
        index = config.INPUT_CONFIG[player]["joystick_index"]
        if index >= len(self.pads) or not self._button_taps:
            return set()
        try:
            iid = self.pads[index].get_instance_id()
        except (pygame.error, AttributeError):
            return set()
        return {b for i, b in self._button_taps if i == iid}

    def _read_pad(self, player: str) -> tuple[set[int], float, float]:
        """(buttons down, stick x, stick y), with y positive pulled back."""
        cfg = config.INPUT_CONFIG[player]
        if cfg["joystick_index"] >= len(self.pads):
            return set(), 0.0, 0.0
        joy = self.pads[cfg["joystick_index"]]
        try:
            down = {b for b in range(joy.get_numbuttons()) if joy.get_button(b)}
            ax, ay = cfg["axes"]
            x = joy.get_axis(ax) if joy.get_numaxes() > ax else 0.0
            y = joy.get_axis(ay) if joy.get_numaxes() > ay else 0.0
        except pygame.error:
            return set(), 0.0, 0.0
        return down, x, y

    def update(self, dt: float) -> None:
        keys = read_keys()
        system = config.INPUT_CONFIG["system"]
        a, b, start, select = (system["a_button"], system["back_button"],
                               system["start_button"], system["select_button"])
        esc = getattr(pygame, system["keyboard_quit"])
        escape = bool(keys[esc]) or esc in self._key_taps
        self.keyboard_quit = self._escape.update(escape)
        frame = FrameInput(activity=escape)
        quit_now = False
        for p in PLAYERS:
            down, x, y = self._read_pad(p)
            held_keys = {act for act, codes in self.keymap[p].items() if any(keys[k] for k in codes)}
            steer = deadzone(x)
            if steer == 0.0:
                steer = float(("right" in held_keys) - ("left" in held_keys))
            pull = deadzone(y)
            if pull == 0.0:
                pull = float(("down" in held_keys) - ("up" in held_keys))
            pressed = (down - self._down[p]) | self._taps(p)
            self._down[p] = down
            tapped = {act for act, codes in self.keymap[p].items()
                      if any(k in self._key_taps for k in codes)}
            new_keys = (held_keys - self._keys_prev[p]) | tapped
            self._keys_prev[p] = held_keys
            stick = (step_sign(steer), step_sign(pull))
            nav_x = self.repeat_x[p].update(dt, stick[0])
            nav_y = self.repeat_y[p].update(dt, stick[1])
            nav = (nav_x or ("right" in tapped) - ("left" in tapped),
                   nav_y or ("down" in tapped) - ("up" in tapped))
            buttons = {"a", "back", "start", "select"}
            held = bool(down & {a, b, start, select}) or bool(held_keys & buttons)
            frame.players[p] = PlayerInput(
                steer=steer,
                brake=max(0.0, pull),
                nav=nav,
                stick=stick,
                a=a in pressed or "a" in new_keys,
                b=b in pressed or "back" in new_keys,
                start=start in pressed or "start" in new_keys,
                select=select in pressed or "select" in new_keys,
                button=bool(pressed) or bool(new_keys & buttons),
                held=held,
            )
            combo = ((start in down or "start" in held_keys)
                     and (select in down or "select" in held_keys))
            if self._combo[p].update(combo):
                quit_now = True
            if down or steer or pull or held_keys or pressed or new_keys:
                frame.activity = True
        self._key_taps.clear()
        self._button_taps.clear()
        self._quit = quit_now
        self.frame = frame

    def quit_combo(self) -> bool:
        """Start + Select went down together on one pad (or one player's keys) this frame."""
        return self._quit
