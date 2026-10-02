"""Single source of truth for resolution, timings, colours and input.

Joystick 0 = P1 (left, blue), joystick 1 = P2 (right, red). The raw button
numbers are the ones confirmed on the cabinet (see ../../../AGENTS.md):
printed A = 1, B = 2, X = 0, Start = 9, Select = 8.
"""

from __future__ import annotations

# --- Display -------------------------------------------------------------------
INTERNAL_WIDTH = 640
INTERNAL_HEIGHT = 360
FPS = 60
SHOW_FPS_DEFAULT = False


def frames(seconds: float) -> int:
    """Convert seconds to frame count at FPS."""
    return round(seconds * FPS)


# --- Stage and movement -------------------------------------------------------
FLOOR_Y = 300            # the floor line, in screen px
STAGE_LEFT, STAGE_RIGHT = 24, 616   # fighters' x is clamped to this
START_X = {"p1": 220, "p2": 420}


# --- Round timing and rules ---------------------------------------------------
ROUND_FRAMES = frames(60.0)
ROUNDS_TO_WIN = 2
LOGICAL_DAMAGE = 25         # plus Move.bonus (5 for heavies and specials)
HITSTOP = 5
HITSTOP_LOGICAL = 12
BUFFER_FRAMES = 6
CHAIN_MAX = 3
BODY_MARGIN = 8          # the push box reaches this far past each fighter's standing hurtbox, px
                         # (fight.body_width: 44 between two TRIOs, 52 between two QUINTs)
THROW_SLACK = 6          # a throw reaches this far past the push box (px between the fighters' x)
THROW_RANGE = 50         # two TRIOs' push box plus THROW_SLACK: a lone Fighter's throw range


# --- Screen transitions and input timing -------------------------------------
ROUND_INTRO_FRAMES = frames(2.0)
ROUND_END_FRAMES = frames(2.5)
MATCH_RESULT_LOCK = frames(1.0)
KO_SLOW_FRAMES = frames(1.2)    # after a K.O. the round end plays in slow motion this long,
KO_SLOW_RATE = 3                # stepping the fight once every this many frames
ATTRACT_DELAY = frames(4.0)
IDLE_TIMEOUT = frames(60.0)
BACK_HOLD_TO_QUIT = frames(2.0)


# --- Colours (players) -------------------------------------------------------
PLAYER_COLORS = {"p1": (64, 136, 248), "p2": (240, 64, 72)}  # left blue, right red
COLOR_FPS = (248, 208, 104)


# --- Input -------------------------------------------------------------------------
INPUT_CONFIG = {
    "p1": {"joystick_index": 0, "hat_index": 0, "axes": (0, 1)},
    "p2": {"joystick_index": 1, "hat_index": 0, "axes": (0, 1)},
    "system": {
        "a_button": 1, "b_button": 2, "x_button": 0, "start_button": 9,
        "select_button": 8, "keyboard_quit": "K_ESCAPE",
    },
    "axis_deadzone": 0.25,
}


# Keyboard: a dev fallback only. The cabinet loader passes --no-keyboard, so
# the keystrokes Batocera's evmapy fakes for P1's pad never reach the game.
KEYMAP = {
    # P1's dev keys must avoid the pad's own letters l, x, r, b, y, a.
    "p1": {"left": ["K_s"], "right": ["K_f"], "up": ["K_e"], "down": ["K_d"],
           "a": ["K_q"], "b": ["K_w"], "x": ["K_t"], "start": ["K_1"]},
    "p2": {"left": ["K_LEFT"], "right": ["K_RIGHT"], "up": ["K_UP"], "down": ["K_DOWN"],
           "a": ["K_PERIOD"], "b": ["K_COMMA"], "x": ["K_SLASH"], "start": ["K_2"]},
}


# --- Sound -------------------------------------------------------------------------
MASTER_VOLUME = 0.8
MUSIC_VOLUME = 0.35
