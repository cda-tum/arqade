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
        # Confirm button: printed A (raw 1), back: printed B (raw 2). The
        # cabinet-wide convention is A = confirm, B = back, Start = start the
        # game -- see "Button convention" in ../AGENTS.md. Back is only used
        # by the pause menu (Start pauses; Start or B resumes).
        "confirm_button": 1,
        "back_button": 2,
        # Raw 9 is the button printed START and raw 8 is SELECT -- the
        # reverse of what these were set to originally. EmulationStation's own
        # es_input.cfg for this pad agrees (select id=8, start id=9), and the
        # symptom was unmistakable: SELECT confirmed menus, because the game
        # read raw 8 as "start". The quit combo is unaffected either way,
        # which is why it went unnoticed for so long.
        "start_button": 9,
        "select_button": 8,
        "keyboard_quit": "K_ESCAPE",
        # Dev-only pause menu keys. P pauses/resumes (Start), Enter picks
        # (A); W/S and Up/Down move the selection. Not one of P1's evmapy
        # letters (l x r b y a) -- see ../AGENTS.md.
        "keyboard_pause": "K_p",
        "keyboard_confirm": "K_RETURN",
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
# Spawning speeds up over a match, gently: the gap between spawn attempts
# shrinks linearly from GATE_SPAWN_INTERVAL to GATE_SPAWN_INTERVAL_MIN over
# GATE_SPAWN_RAMP_SECONDS of play (pauses don't count), and the on-screen cap
# grows by one every GATE_CAP_STEP_SECONDS, from MAX_GATES_ON_SCREEN up to
# MAX_GATES_ON_SCREEN_LATE. Gates never vanish on their own, so the cap is
# what really sets how crowded the field gets.
GATE_SPAWN_INTERVAL = 2.5  # seconds between spawn attempts, at kick-off
GATE_SPAWN_INTERVAL_MIN = 1.25  # ... and once the ramp is over
GATE_SPAWN_RAMP_SECONDS = 90.0
MAX_GATES_ON_SCREEN = 3  # at kick-off
MAX_GATES_ON_SCREEN_LATE = 5
GATE_CAP_STEP_SECONDS = 45.0
# A gate is announced this long before it appears: a dashed outline with its
# letter, at exactly the spot it will land, so a ball is never hit by a gate
# that pops in out of nowhere. An announced gate does nothing to balls yet.
GATE_WARNING_SECONDS = 1.5
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
COLOR_FPS = (255, 210, 0)  # also the highlight colour (title prompt, pause menu)
COLOR_HINT = (140, 140, 160)  # pause menu's control hint

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
# HOW TO PLAY card before each match from the title: button presses in its
# first TUTORIAL_IGNORE_SECONDS don't dismiss it (the A/Start that left the
# title, or its bounce), and its demo shows each gate for this long.
TUTORIAL_IGNORE_SECONDS = 0.3
TUTORIAL_SCENE_SECONDS = 4.0

# --- Debug ---
SHOW_FPS_DEFAULT = False
FPS = 60
