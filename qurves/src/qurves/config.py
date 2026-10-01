"""Single source of truth for resolution, rules tuning, colours and input.

Joystick 0 = P1, joystick 1 = P2, same as the sibling games. The raw button
numbers are the ones confirmed on the cabinet (see ../../../AGENTS.md):
printed A = 1, B = 2, Select = 8, Start = 9. Axis 1 is the stick's vertical
axis (negative = up, confirmed); axis 0 being horizontal still wants an
--input-test check on the cabinet.
"""

from __future__ import annotations

# --- Display -------------------------------------------------------------------
INTERNAL_WIDTH = 960
INTERNAL_HEIGHT = 540  # exactly x2 onto the cabinet's 1920x1080 panel
HUD_HEIGHT = 36
CELL = 6
GRID_W = 160  # 160 * 6 = 960
GRID_H = 84  # 36 + 84 * 6 = 540
FPS = 60
SHOW_FPS_DEFAULT = False
GLOW = True  # glow strokes and halos; set False if the cabinet drops frames
SHOW_SCANLINES = True

# --- Round rules (see the spec, section 1) ---------------------------------------
START_CELLS = {"p1": (20, 42), "p2": (139, 42)}
START_HEADINGS = {"p1": (1, 0), "p2": (-1, 0)}
SPEED_START = 14.0  # cells per second
SPEED_STEP = 2.0
SPEED_STEP_EVERY = 10.0  # seconds
SPEED_MAX = 24.0
METER_MAX = 100.0
METER_PER_PICKUP = 50.0
SPLIT_MIN_METER = 50.0
METER_DRAIN_PER_S = 50.0 / 3.0  # one pickup buys 3 s of superposition
MAX_PICKUPS = 2
PICKUP_RESPAWN = 2.0  # seconds
PICKUP_MIN_DIST = 10  # cells from every bike head (Chebyshev distance)
PICKUP_SPAWN_ATTEMPTS = 200

# --- Match flow -------------------------------------------------------------------
ROUNDS_TO_WIN = 3
COUNTDOWN = 3.0
ROUND_RESULT_TIME = 2.0
MATCH_RESULT_LOCK = 1.0  # seconds before the result screen takes input
IDLE_TIMEOUT = 60.0
BACK_HOLD_TO_QUIT = 2.0  # hold Select this long on the title to quit

# --- Colours -----------------------------------------------------------------------
COLOR_BACKGROUND = (5, 6, 14)
COLOR_HUD = (8, 10, 22)
COLOR_GRID = (17, 21, 42)
COLOR_WALL = (110, 120, 200)
COLOR_WALL_FILL = (20, 24, 48)
COLOR_TEXT = (200, 210, 240)
COLOR_DIM = (110, 120, 160)
COLOR_FPS = (255, 211, 107)
COLOR_PICKUP = (235, 240, 255)
PLAYER_COLORS = {"p1": (40, 230, 255), "p2": (255, 140, 40)}  # cyan, orange (as Qlimbers)

# --- Input -------------------------------------------------------------------------
INPUT_CONFIG = {
    "p1": {
        "joystick_index": 0,
        "hat_index": 0,
        "axes": (0, 1),  # (horizontal, vertical)
        "buttons": {"split": [1], "back": [2]},  # printed A (also confirms menus), printed B
    },
    "p2": {
        "joystick_index": 1,
        "hat_index": 0,
        "axes": (0, 1),
        "buttons": {"split": [1], "back": [2]},
    },
    "system": {"start_button": 9, "select_button": 8, "keyboard_quit": "K_ESCAPE"},
    "axis_deadzone": 0.25,
}

# Keyboard: a dev fallback only. The cabinet loader passes --no-keyboard, so
# the keystrokes Batocera's evmapy fakes for P1's pad never reach the game.
KEYMAP = {
    "p1": {"up": ["K_w"], "left": ["K_a"], "down": ["K_s"], "right": ["K_d"],
           "split": ["K_q"], "back": ["K_e"], "start": ["K_1"]},
    "p2": {"up": ["K_i"], "left": ["K_j"], "down": ["K_k"], "right": ["K_l"],
           "split": ["K_u"], "back": ["K_o"], "start": ["K_2"]},
}
