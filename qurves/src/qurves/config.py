"""Single source of truth for resolution, rules tuning, colours and input.

Joystick 0 is the left pad, joystick 1 the right one, same as the sibling
games. The raw button numbers are the ones confirmed on the cabinet (see
../../../AGENTS.md): printed X = 0, A = 1, B = 2, Y = 3, Select = 8,
Start = 9. Axis 1 is the stick's vertical axis (negative = up, confirmed);
axis 0 being horizontal still wants an --input-test check on the cabinet.
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

# --- Players and controls ---------------------------------------------------------
MODES = (2, 4)
PLAYERS_BY_MODE = {2: ("p1", "p2"), 4: ("p1", "p2", "p3", "p4")}

# (cell, heading) per player. In 4-player mode the left pad's two players
# (p1 on the stick, p3 on the buttons) start on the left, the right pad's on
# the right.
START = {
    2: {"p1": ((20, 42), (1, 0)), "p2": ((139, 42), (-1, 0))},
    4: {"p1": ((20, 21), (1, 0)), "p3": ((20, 62), (1, 0)),
        "p2": ((139, 62), (-1, 0)), "p4": ((139, 21), (-1, 0))},
}

# Which inputs steer which player: ("stick", pad) or ("pad", pad), where
# "pad" is the four face buttons laid out like WASD. With 2 players either
# works; with 4, each pad's stick and buttons are separate players.
CONTROLS = {
    2: {"p1": (("stick", 0), ("pad", 0)), "p2": (("stick", 1), ("pad", 1))},
    4: {"p1": (("stick", 0),), "p2": (("stick", 1),), "p3": (("pad", 0),), "p4": (("pad", 1),)},
}

# --- Round rules (see the spec, section 1) ---------------------------------------
SPEED_START = 14.0  # cells per second
SPEED_STEP = 2.0
SPEED_STEP_EVERY = 10.0  # seconds
SPEED_MAX = 24.0

GATE_WEIGHTS = {"H": 2, "X": 1, "Z": 1}
MAX_GATES = {2: 3, 4: 4}
GATE_REACH = 2  # a bike within 2 cells of a gate's centre takes it: a 5x5 area
GATE_MIN_DIST = 10  # spawn at least this far (Chebyshev) from every bike head
GATE_GAP = 8  # and from every other gate
GATE_RESPAWN = 2.0  # seconds
GATE_SPAWN_ATTEMPTS = 200

H_TIME = 3.0  # seconds of superposition each H gate adds
SUPERPOSITION_MAX = 9.0
MAX_COPIES = 8
SHIELD_Z = 2.0  # seconds of invulnerability from a Z gate
SHIELD_X = 3.0  # and after an X gate's jump

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
# The cabinet's left side is blue and its right side red (see AGENTS.md
# "Player colours"); the left pad's second player is green, the right's purple.
PLAYER_COLORS = {
    "p1": (60, 145, 255),  # blue
    "p2": (255, 70, 85),  # red
    "p3": (60, 230, 110),  # green
    "p4": (190, 90, 255),  # purple
}
GATE_COLORS = {"H": (235, 240, 255), "X": (255, 205, 60), "Z": (70, 235, 235)}

# --- Input -------------------------------------------------------------------------
INPUT_CONFIG = {
    "pads": (
        {"joystick_index": 0, "hat_index": 0, "axes": (0, 1),  # (horizontal, vertical)
         # printed L X R / Y B A: X, Y, B, A sit like W, A, S, D
         "buttons": {"up": [0], "left": [3], "down": [2], "right": [1]}},
        {"joystick_index": 1, "hat_index": 0, "axes": (0, 1),
         "buttons": {"up": [0], "left": [3], "down": [2], "right": [1]}},
    ),
    "system": {
        "start_button": 9, "select_button": 8,
        "confirm_buttons": [1], "back_buttons": [2],  # printed A confirms menus, B goes back
        "keyboard_quit": "K_ESCAPE",
    },
    "axis_deadzone": 0.25,
}

# Keyboard: a dev fallback only. The cabinet loader passes --no-keyboard, so
# the keystrokes Batocera's evmapy fakes for P1's pad never reach the game.
KEYMAP = {
    ("stick", 0): {"up": ["K_w"], "left": ["K_a"], "down": ["K_s"], "right": ["K_d"]},
    ("pad", 0): {"up": ["K_t"], "left": ["K_f"], "down": ["K_g"], "right": ["K_h"]},
    ("stick", 1): {"up": ["K_i"], "left": ["K_j"], "down": ["K_k"], "right": ["K_l"]},
    ("pad", 1): {"up": ["K_UP"], "left": ["K_LEFT"], "down": ["K_DOWN"], "right": ["K_RIGHT"]},
}
KEYS_CONFIRM = ["K_RETURN", "K_1", "K_2"]
KEYS_BACK = ["K_BACKSPACE"]
