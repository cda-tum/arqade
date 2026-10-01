"""Single source of truth for input mapping and tuning constants.

Joystick 0 = P1, joystick 1 = P2, same as the other games in this repo. The
face-button numbers are the ones confirmed on the cabinet (see ../AGENTS.md),
and so are Start = 9 / Select = 8 (not the other way round).
"""

from pathlib import Path

# --- Internal render resolution ---
# Native 1920x1080, the cabinet panel itself (see ../AGENTS.md: the internal
# height must divide 1080). game.py lays things out for a 1280x720 design and
# multiplies by INTERNAL_HEIGHT / 720, so any 16:9 size that divides 1080
# works here -- 960x540 is the fallback if the Pi can't keep up at 1080p.
INTERNAL_WIDTH = 1920
INTERNAL_HEIGHT = 1080

# --- Chip ---
# The chip layouts themselves live in lattice.py (LAYOUTS).
GRID_ROWS = 5  # size of the square and brick layouts
GRID_COLS = 5

# --- Gameplay tuning ---
LIVES = 3                    # decohered pairs before game over (shared in CO-OP)
HURT_SECONDS = 1.4           # how long the red "life lost" flash lasts
QUBIT_SPEED = 0.8            # edges per second a travelling qubit covers
MAX_ACTIVE_PAIRS = 6         # pairs on the chip at once (waiting + travelling)
MIN_PAIR_DISTANCE = 2        # spawned endpoints are at least this many hops apart
INITIAL_PAIRS = 2            # pairs already waiting when the game starts
# Spawn interval and coherence time both shrink linearly from START to MIN
# over RAMP_SECONDS of (board) play time.
SPAWN_INTERVAL_START = 5.0
SPAWN_INTERVAL_MIN = 2.2
COOP_SPAWN_RATE = 1.25             # CO-OP: pairs come 25% more often throughout
COHERENCE_START = 30.0
COHERENCE_MIN = 16.0
RAMP_SECONDS = 150.0
# If nothing is waiting, the next pair is pulled forward to arrive this soon.
IDLE_SPAWN_DELAY = 1.0
# Scoring: a gate is worth BASE * DETOUR_FIDELITY ** (extra hops over the
# shortest possible route), plus up to TIME_BONUS for coherence left.
GATE_BASE_POINTS = 100
DETOUR_FIDELITY = 0.9
TIME_BONUS = 50

# Crossing routes: qubits are shared, couplers are not. Each qubit extends
# NODE_RADIUS coupler lengths around its centre; two travelling qubits inside
# the same one at once crash (both gates lost).
NODE_RADIUS = 0.35
CRASH_LIFE_COST = 1

# --- Specials (appear on free parts of the chip for a while) ---
SPECIAL_FIRST = 12.0               # seconds before the first one
SPECIAL_INTERVAL = (9.0, 15.0)     # random gap between two
MAX_SPECIALS = 3                   # on the chip at once
SPECIAL_UNLOCK = {"miscal": 0.0, "speed": 25.0, "defect": 40.0, "bell": 70.0}
SPECIAL_DURATION = {"miscal": 20.0, "defect": 15.0, "speed": 25.0, "bell": 30.0}
MISCAL_SLOWDOWN = 3.0              # a miscalibrated coupler takes this many times longer
MISCAL_FIDELITY = 0.8              # ... and multiplies the gate's fidelity by this
SPEED_BOOST = 2.0                  # a speed qubit multiplies a passing qubit's speed
MAX_BOOST = 4.0
TELEPORT_TIME = 0.3                # seconds a Bell jump takes
BELL_MIN_DISTANCE = 3              # grid distance between the two Bell qubits

# Stick auto-repeat while held (seconds).
REPEAT_DELAY = 0.30
REPEAT_INTERVAL = 0.15

# --- Input mapping ---
# Dev keyboard fallback (pygame key names). P1 avoids l/x/r/b/y/a, which the
# cabinet's P1 encoder also sends as keystrokes -- see ../AGENTS.md. On the
# cabinet the loader passes --no-keyboard anyway.
KEYS = {
    "p1": {"up": ["K_e"], "down": ["K_d"], "left": ["K_s"], "right": ["K_f"],
           "next": ["K_j"], "other": ["K_k"], "undo": ["K_u"], "prev": ["K_i"]},
    "p2": {"up": ["K_UP"], "down": ["K_DOWN"], "left": ["K_LEFT"], "right": ["K_RIGHT"],
           "next": ["K_PERIOD"], "other": ["K_COMMA"], "undo": ["K_m"], "prev": ["K_n"]},
}
KEYS_CONFIRM = ["K_RETURN", "K_KP_ENTER", "K_1", "K_2"]
KEYS_BACK = ["K_ESCAPE"]
KEYS_PAUSE = ["K_p"]

# Joysticks. Raw button numbers confirmed on the cabinet (both pads):
# printed L X R / Y B A = raw 4 0 5 / 3 2 1. The stick is an analog axis
# there; the hat is only read as a fallback for other pads.
_PAD_BUTTONS = {
    "next": [1, 5],  # printed A (or R): next station
    "other": [2],    # printed B: other end of the same pair
    "undo": [0],     # printed X: take back the last step
    "prev": [4],     # printed L: previous station
}
INPUT_CONFIG = {
    "p1": {"joystick_index": 0, "hat_index": 0, "axes": (0, 1), "buttons": _PAD_BUTTONS},
    "p2": {"joystick_index": 1, "hat_index": 0, "axes": (0, 1), "buttons": _PAD_BUTTONS},
    "system": {
        # Start confirms / pauses, Select goes back to the menu. Quit combo:
        # Start + Select held together, on either controller.
        "start_button": 9,
        "select_button": 8,
    },
    "axis_deadzone": 0.5,
}

# --- Display / effects ---
SHOW_SCANLINES = True
GLOW = True  # additive glow effects; set False if the cabinet drops frames
MASTER_VOLUME = 0.8
BACK_HOLD_TO_QUIT = 2.0  # seconds holding Select/ESC on the title screen

# Outside the package folder, so a redeploy doesn't wipe it
# (on Batocera, ~ is /userdata/system).
HISCORE_FILE = Path.home() / ".superconductor_hiscores.json"

FPS = 60
SHOW_FPS_DEFAULT = False
