"""Single source of truth for resolution, rules tuning, colours and input.

The first pad is the left one, the second the right one, same as the
sibling games. Raw button and axis numbers live in arqade_common.input,
shared by all games; run --input-test on new hardware to see what it reports.
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
TUTORIAL_GUARD = 0.3  # seconds the HOW TO PLAY card ignores buttons (the press that opened it)
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
# Pads, button numbers and the keyboard layout are shared by all games: see
# arqade_common.input (and input.FACE_DIRECTIONS for the buttons that steer).
# The cabinet loader passes --no-keyboard, so the keystrokes Batocera's evmapy
# fakes for P1's pad never reach the game.
INPUT_CONFIG = {
    "axis_deadzone": 0.25,
}
