"""Single source of truth for resolution, rules tuning, colours and input.

Joystick 0 = P1 (left, blue), joystick 1 = P2 (right, red). The raw button
numbers are the ones confirmed on the cabinet (see ../../../AGENTS.md):
printed A = 1, B = 2, Select = 8, Start = 9. In game A and B rotate the
pill; in menus A (or Start) confirms and B goes back.
"""

from __future__ import annotations

# --- Display -------------------------------------------------------------------
INTERNAL_WIDTH = 480
INTERNAL_HEIGHT = 270  # exactly x4 onto the cabinet's 1920x1080 panel
FPS = 60
SHOW_FPS_DEFAULT = False

# --- The board -------------------------------------------------------------------
COLS = 6  # qubit wires
ROWS = 14
CELL = 16
BOARD_ORIGIN = {"p1": (40, 34), "p2": (344, 34)}  # top-left of each well, in px

GATE_KINDS = ("H", "X", "Y", "Z")
PAULIS = ("X", "Y", "Z")
CNOT_SHARE = 0.15  # share of pills that are a CNOT
SPAWN_X = 2  # pills spawn lying flat over wires 2 and 3

FALL_START = 0.8  # seconds per row
FALL_SPEEDUP = 0.9  # times this...
FALL_SPEEDUP_EVERY = 30.0  # ...every this many seconds of a round
FALL_MIN = 0.25
SOFT_DROP_INTERVAL = 0.05
SETTLE_STEP = 0.06  # seconds per row while things settle
CLEAR_TIME = 0.35  # how long matched gates flash before they vanish

MAX_ATTACK = 4  # noise gates a chain can send, before the big-pass bonus
BIG_PASS = 3  # matches in one pass that earn one extra noise gate
DANGER_ROWS = 4  # a stack this close to the top makes the frame blink

# --- Errors and rounds -------------------------------------------------------------
ERROR_ROWS = 8  # errors sit in the bottom 8 rows
ERRORS_FIRST = 4
ERRORS_STEP = 2
ERRORS_MAX = 12
ROUNDS_TO_WIN = 2
COUNTDOWN = 3.0
ROUND_RESULT_TIME = 2.5
MATCH_RESULT_LOCK = 1.0  # seconds before the result screen takes input
IDLE_TIMEOUT = 60.0
BACK_HOLD_TO_QUIT = 2.0  # hold Select this long on the title to quit

# --- Colours -----------------------------------------------------------------------
COLOR_INK = (24, 18, 40)
COLOR_WELL = (18, 22, 46)
COLOR_WIRE = (44, 54, 96)
COLOR_TEXT = (240, 240, 255)
COLOR_FPS = (255, 211, 107)
GATE_COLORS = {"H": (250, 196, 40), "X": (232, 64, 72), "Y": (170, 82, 220), "Z": (56, 124, 236)}
CNOT_COLOR = (170, 182, 204)
PLAYER_COLORS = {"p1": (64, 136, 248), "p2": (236, 64, 72)}  # left blue, right red
BACKGROUNDS = (  # two-tone tile patterns, one per round
    ((40, 44, 120), (54, 60, 152)),
    ((92, 40, 110), (116, 54, 140)),
    ((22, 92, 96), (30, 116, 120)),
    ((110, 62, 30), (138, 82, 42)),
)

# --- Input -------------------------------------------------------------------------
INPUT_CONFIG = {
    "p1": {"joystick_index": 0, "hat_index": 0, "axes": (0, 1)},
    "p2": {"joystick_index": 1, "hat_index": 0, "axes": (0, 1)},
    "buttons": {"cw": [1], "ccw": [2]},  # printed A and B
    "system": {
        "start_button": 9, "select_button": 8,
        "confirm_buttons": [1], "back_buttons": [2],
        "keyboard_quit": "K_ESCAPE",
    },
    "axis_deadzone": 0.5,
}
REPEAT_DELAY = 0.18  # stick auto-repeat for moving the pill
REPEAT_INTERVAL = 0.06

# Keyboard: a dev fallback only. The cabinet loader passes --no-keyboard, so
# the keystrokes Batocera's evmapy fakes for P1's pad never reach the game.
KEYMAP = {
    "p1": {"left": ["K_a"], "right": ["K_d"], "down": ["K_s"], "cw": ["K_q"], "ccw": ["K_e"]},
    "p2": {"left": ["K_LEFT"], "right": ["K_RIGHT"], "down": ["K_DOWN"], "cw": ["K_PERIOD"], "ccw": ["K_COMMA"]},
}
KEYS_CONFIRM = ["K_RETURN", "K_1", "K_2"]
KEYS_BACK = ["K_BACKSPACE"]

# --- Sound -------------------------------------------------------------------------
MASTER_VOLUME = 0.8
MUSIC_VOLUME = 0.35
