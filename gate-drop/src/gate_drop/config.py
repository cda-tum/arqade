"""Single source of truth for resolution, rules tuning, colours and input.

Joystick 0 = P1 (left, blue), joystick 1 = P2 (right, red). The raw button
numbers are the ones confirmed on the cabinet (see ../../../AGENTS.md):
printed A = 1, B = 2, Select = 8, Start = 9. In game A and B rotate the
pill; in menus A (or Start) confirms and B goes back.
"""

from __future__ import annotations

from pathlib import Path

# --- Display -------------------------------------------------------------------
INTERNAL_WIDTH = 480
INTERNAL_HEIGHT = 270  # exactly x4 onto the cabinet's 1920x1080 panel
FPS = 60
SHOW_FPS_DEFAULT = False

# --- The board -------------------------------------------------------------------
COLS = 6  # qubit wires
ROWS = 14
CELL = 16
BOARD_ORIGIN = {"p1": (40, 30), "p2": (344, 30)}  # top-left of each well, in px
SOLO_ORIGIN = (192, 30)  # the single-player board, centred
LABEL_PLATE = 8  # extra frame height under each well, for the |q_n> wire labels

GATE_KINDS = ("H", "X", "Y", "Z", "T", "Td")  # "Td" is T-dagger
GATE_WEIGHTS = {"H": 6, "X": 6, "Y": 6, "Z": 6, "T": 1, "Td": 1}  # T and T-dagger: 1 half in 26 each
# A gate cancels with its inverse. X, Y, Z and H are their own; T and T-dagger
# undo each other, while T T = S is not the identity, so two Ts don't cancel.
INVERSE = {"H": "H", "X": "X", "Y": "Y", "Z": "Z", "T": "Td", "Td": "T"}
PAULIS = ("X", "Y", "Z")  # the kinds an error can be
NOISE_KIND = "T"  # what attacks drop on the opponent: it only clears with a T-dagger
CNOT_SHARE = 0.15  # share of pills that are a CNOT
SPAWN_X = 2  # pills spawn lying flat over wires 2 and 3

SPEEDS = ("LOW", "MED", "HI")
SPEED_FALL = {"LOW": (0.9, 0.3), "MED": (0.65, 0.22), "HI": (0.42, 0.15)}  # (start, floor), s per row
FALL_SPEEDUP = 0.9  # times this...
FALL_SPEEDUP_EVERY = 30.0  # ...every this many seconds of a round
SOFT_DROP_INTERVAL = 0.05
SETTLE_STEP = 0.06  # seconds per row while things settle
CLEAR_TIME = 0.35  # how long matched gates flash before they vanish

MAX_ATTACK = 4  # an attack sends at most this many T gates
MIN_ATTACK = 2  # and at least this many: a 2-step chain sends 2, a 3-step chain 3
BIG_PASS = 3  # this many matches in one pass attack too (one more if part of a chain)
DANGER_ROWS = 4  # a stack this close to the top makes the frame blink

# --- Errors, levels and rounds -------------------------------------------------------
ERROR_ROWS = 8  # errors sit in the bottom 8 rows
LEVEL_MIN, LEVEL_MAX = 1, 10  # level n has 2n + 2 errors
DEFAULT_LEVEL = 1
DEFAULT_SPEED = "MED"
ROUNDS_TO_WIN = 2
COUNTDOWN = 3.0
TUTORIAL_LOCK = 0.3  # the HOW TO PLAY card ignores presses this long, so the A that readied up can't skip it
ROUND_RESULT_TIME = 2.5
MATCH_RESULT_LOCK = 1.0  # seconds before the result screen takes input
LEVEL_CLEAR_TIME = 2.5  # single player
GAME_OVER_TIME = 2.5
HISCORES_TIME = 8.0
IDLE_TIMEOUT = 60.0
BACK_HOLD_TO_QUIT = 2.0  # hold Select this long on the title to quit

# --- Colours -----------------------------------------------------------------------
COLOR_INK = (24, 18, 40)
COLOR_WELL = (18, 22, 46)
COLOR_WIRE = (44, 54, 96)
COLOR_TEXT = (240, 240, 255)
COLOR_FPS = (255, 211, 107)
GATE_COLORS = {
    "H": (250, 196, 40), "X": (232, 64, 72), "Y": (170, 82, 220), "Z": (56, 124, 236),
    "T": (52, 190, 108), "Td": (240, 132, 40),
}
CNOT_COLOR = (170, 182, 204)
PLAYER_COLORS = {"p1": (64, 136, 248), "p2": (236, 64, 72)}  # left blue, right red
BACKGROUNDS = (  # two-tone tile patterns, one per round
    ((40, 44, 120), (54, 60, 152)),
    ((92, 40, 110), (116, 54, 140)),
    ((22, 92, 96), (30, 116, 120)),
    ((110, 62, 30), (138, 82, 42)),
)

# --- Input -------------------------------------------------------------------------
# Raw button numbers and the keyboard layout live in arqade_common.input
# (printed A rotates clockwise and B anti-clockwise in game; in menus A or
# Start confirms and B goes back). The cabinet loader passes --no-keyboard, so
# the keystrokes Batocera's evmapy fakes for P1's pad never reach the game.
AXIS_DEADZONE = 0.5
REPEAT_DELAY = 0.18  # stick auto-repeat for moving the pill
REPEAT_INTERVAL = 0.06

# --- Single-player scoring ----------------------------------------------------------
SPEED_SCORE = {"LOW": 1, "MED": 2, "HI": 3}
ERROR_POINTS = 100  # x speed x 2^(chain step - 1)
CHAIN_MULT_CAP = 8
LEVEL_CLEAR_BONUS = 500  # x level x speed
HISCORE_SLOTS = 10
# Outside the package folder, so a redeploy doesn't wipe it.
SCORE_FILE = Path.home() / ".gate_drop_scores.json"

# --- Sound -------------------------------------------------------------------------
MASTER_VOLUME = 0.8
