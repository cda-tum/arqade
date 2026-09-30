"""Single source of truth for input mapping and tuning constants.

Button/axis indices are placeholders — the IconicArcade cabinet's exact mapping
is unknown. Run `--input-test` on the real hardware and fill these in.
"""

# --- Internal render resolution (scaled + letterboxed onto the real window) ---
INTERNAL_WIDTH = 480
INTERNAL_HEIGHT = 270

# --- Input mapping ---
# Joystick axis 1 (vertical) is standard for most USB arcade encoders; axis
# index and sign may need flipping once tested on real hardware.
INPUT_CONFIG = {
    "p1": {
        "joystick_index": 0,
        "vertical_axis": 1,
        "keyboard": {
            "up": "K_w",
            "down": "K_s",
        },
    },
    "p2": {
        "joystick_index": 1,
        "vertical_axis": 1,
        "keyboard": {
            "up": "K_UP",
            "down": "K_DOWN",
        },
    },
    "system": {
        # Quit combo: Start + Select held together, on either controller.
        # Confirm button: printed A (raw 1). The cabinet-wide convention is
        # A = confirm, B = back, Start = start the game -- see "Button
        # convention" in ../AGENTS.md. This game has no menu to go back in,
        # so it binds confirm only.
        "confirm_button": 1,
        # Raw 9 is the button printed START and raw 8 is SELECT -- the
        # reverse of what these were set to originally. EmulationStation's own
        # es_input.cfg for this pad agrees (select id=8, start id=9), and the
        # symptom was unmistakable: SELECT confirmed menus, because the game
        # read raw 8 as "start". The quit combo is unaffected either way,
        # which is why it went unnoticed for so long.
        "start_button": 9,
        "select_button": 8,
        "keyboard_quit": "K_ESCAPE",
    },
    "axis_deadzone": 0.25,
}

# --- Tuning constants ---
PADDLE_WIDTH = 8
PADDLE_HEIGHT = 40
PADDLE_MARGIN = 16  # distance from paddle to nearest screen edge
PADDLE_SPEED = 180.0  # px/sec, internal-resolution space

BALL_RADIUS = 4
BALL_START_SPEED = 140.0  # px/sec
BALL_SPEED_INCREMENT = 12.0  # added to speed on each paddle return
BALL_MAX_SPEED = 320.0
BALL_MAX_BOUNCE_ANGLE_DEG = 60.0  # max deflection angle off a paddle edge hit
PADDLE_CATCH_GRACE = 8.0  # px of forgiveness on catch range past each paddle edge

WINNING_SCORE = 7

# --- Gates (H / X / Z / SWAP pickups) ---
# No probability: each gate is a fixed, deterministic transform on whichever
# ball touches it. H is the only one that changes the ball count -- it splits
# one ball into two (one keeps going, one reverses horizontal direction), and
# is a no-op past MAX_BALLS_ON_SCREEN (the gate stays, in case the count
# drops again later). X/Z bounce the ball as if off a vertical/horizontal
# wall. SWAP teleports it to the mirrored spot across the field.
GATE_RADIUS = 24  # sized to comfortably fit the 4-letter "SWAP" label
GATE_SPAWN_INTERVAL = 2.5  # seconds between spawn attempts
MAX_GATES_ON_SCREEN = 3
MAX_BALLS_ON_SCREEN = 4
# Keep spawns out of a margin near each paddle.
GATE_SPAWN_MARGIN_X = 120
GATE_SPAWN_MARGIN_Y = 20
# Gates never overlap: a new gate's square keeps at least GATE_MIN_GAP px of
# clear space to every existing gate's square (if no such spot exists, that
# spawn attempt is skipped). Gates stay on screen until a ball touches them.
GATE_MIN_GAP = 16
# Spread: each spawn samples this many random valid spots and keeps the one
# farthest from the existing gates -- random, but with a soft repulsion. Higher
# = more evenly spread (and more predictable); 1 = plain uniform random.
GATE_SPAWN_CANDIDATES = 8
# Relative spawn chance per kind -- H spawns twice as often as the others.
GATE_WEIGHTS = {"H": 2, "X": 1, "Z": 1, "SWAP": 1}

# --- Colors ---
COLOR_BACKGROUND = (10, 10, 20)
COLOR_MIDLINE = (60, 60, 80)
COLOR_PADDLE = (230, 230, 230)
COLOR_BALL = (230, 230, 230)
COLOR_TEXT = (230, 230, 230)
COLOR_FPS = (255, 210, 0)

GATE_COLORS = {
    "H": (120, 200, 255),
    "X": (255, 170, 60),
    "Z": (200, 110, 255),
    "SWAP": (120, 255, 160),
}

# --- Paddle-catch / score flash ---
FLASH_DURATION = 0.25  # seconds
FLASH_MAX_GROWTH = 14  # px added to the ring radius over the flash's lifetime
COLOR_FLASH = (255, 255, 255)

# --- Game flow ---
IDLE_TIMEOUT_SECONDS = 60.0  # no input during a match -> back to the title screen
WINNER_SCREEN_DURATION = 5.0  # auto-return to title after this long, sooner on input
TITLE_BLINK_PERIOD = 1.0  # seconds per "PRESS START" blink cycle

# --- Debug ---
SHOW_FPS_DEFAULT = False
FPS = 60
