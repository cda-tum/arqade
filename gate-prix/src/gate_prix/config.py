"""Single source of truth for resolution, race rules, colours and input.

Joystick 0 = P1 (blue, top view), joystick 1 = P2 (red, bottom view). The raw button
numbers are the ones confirmed on the cabinet (see ../../../AGENTS.md): printed A = 1,
B = 2, Select = 8, Start = 9. The stick is an analog axis, never a hat: axis 0 steers,
axis 1 brakes (pulled back, positive) and drives the menus.
"""

from __future__ import annotations

# --- Display -------------------------------------------------------------------------
INTERNAL_WIDTH = 960
INTERNAL_HEIGHT = 540  # exactly x2 onto the cabinet's 1920x1080 panel
FPS = 60
SHOW_FPS_DEFAULT = False
VIEW_1P = (960, 540)
VIEW_2P = (960, 270)  # P1 on top, P2 below

# --- The race --------------------------------------------------------------------------
CARS = 6
CPU_CARS_2P = 4
CPU_CARS_1P = 5
LAPS = 3
ROWS_PER_LAP = 8
SLOTS = LAPS * ROWS_PER_LAP  # 24: one slot of the target circuit per gate row
ARCHES_MIN = 1
ARCHES_MAX = 3
ITEM_BOXES_PER_LAP = 2
LAP_SECONDS = 45.0  # about, at top speed

# --- Boosts ----------------------------------------------------------------------------
# Streak: +20% for 1.0 s on the first right gate in a row, then +8% and +0.2 s per further
# one, up to +60% for 2.0 s.
STREAK_BOOST_FIRST = 0.20
STREAK_BOOST_STEP = 0.08
STREAK_BOOST_MAX = 0.60
STREAK_TIME_FIRST = 1.0
STREAK_TIME_STEP = 0.2
STREAK_TIME_MAX = 2.0

# CIRCUIT CHECK, at the start of the final lap, over the first CHECK_SLOTS slots:
# (CHECK_SLOTS - d) / CHECK_SLOTS * CHECK_BOOST extra speed, for
# CHECK_TIME_BASE + (CHECK_SLOTS - d) * CHECK_TIME_PER_SLOT seconds.
CHECK_SLOTS = 16
CHECK_BOOST = 0.80
CHECK_TIME_BASE = 1.0
CHECK_TIME_PER_SLOT = 0.25


def streak_boost(streak: int) -> tuple[float, float]:
    """The (extra speed fraction, seconds) of a streak of this many right gates in a row."""
    if streak <= 0:
        return 0.0, 0.0
    strength = min(STREAK_BOOST_MAX, STREAK_BOOST_FIRST + (streak - 1) * STREAK_BOOST_STEP)
    seconds = min(STREAK_TIME_MAX, STREAK_TIME_FIRST + (streak - 1) * STREAK_TIME_STEP)
    return strength, seconds


def check_boost(distance: int) -> tuple[float, float]:
    """The CIRCUIT CHECK's (extra speed fraction, seconds) for a Hamming distance."""
    right = CHECK_SLOTS - distance
    return right / CHECK_SLOTS * CHECK_BOOST, CHECK_TIME_BASE + right * CHECK_TIME_PER_SLOT


# --- Driving ---------------------------------------------------------------------------
OFFROAD_SPEED_FACTOR = 0.6  # top speed on the copper plate

# --- Flow ------------------------------------------------------------------------------
ATTRACT_DELAY = 3.0  # untouched seconds on the title before the CPU racers play
IDLE_TIMEOUT = 60.0

# --- Colours ---------------------------------------------------------------------------
PLAYER_COLORS = {"p1": (64, 136, 248), "p2": (240, 64, 72)}  # left/top blue, right/bottom red
GATE_COLORS = {  # shared with the other games
    "H": (248, 192, 40),
    "X": (232, 64, 72),
    "Z": (56, 120, 232),
    "Y": (168, 80, 216),
}

# --- Input -----------------------------------------------------------------------------
INPUT_CONFIG = {
    "p1": {"joystick_index": 0, "hat_index": 0, "axes": (0, 1)},
    "p2": {"joystick_index": 1, "hat_index": 0, "axes": (0, 1)},
    "system": {
        "a_button": 1, "back_button": 2, "start_button": 9, "select_button": 8,
        "keyboard_quit": "K_ESCAPE",
    },
    "axis_deadzone": 0.25,  # analog stick
    "step_threshold": 0.5,  # a stick push past this counts as a step in the menus
}
REPEAT_DELAY = 0.22  # auto-repeat for stick steps in menus
REPEAT_INTERVAL = 0.11

# Keyboard: a dev fallback only. The cabinet loader passes --no-keyboard, so the keystrokes
# Batocera's evmapy fakes for P1's pad never reach the game.
KEYMAP = {
    # ESDF, not WASD: P1's dev keys must avoid the pad's own letters l, x, r, b, y, a.
    "p1": {"left": ["K_s"], "right": ["K_f"], "up": ["K_e"], "down": ["K_d"], "a": ["K_q"],
           "back": ["K_w"], "start": ["K_1"]},
    "p2": {"left": ["K_LEFT"], "right": ["K_RIGHT"], "up": ["K_UP"], "down": ["K_DOWN"],
           "a": ["K_PERIOD"], "back": ["K_COMMA"], "start": ["K_2"]},
}

# --- Sound -----------------------------------------------------------------------------
MASTER_VOLUME = 0.8
MUSIC_VOLUME = 0.35
