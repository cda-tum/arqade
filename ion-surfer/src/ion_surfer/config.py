"""Single source of truth for input mapping and tuning constants.

Button/axis indices follow the same cabinet layout as Quantum Pong / Quantum
Towers (joystick 0 = P1, joystick 1 = P2, Start = 8, Select = 9). They are
still placeholders -- run `--input-test` on the real hardware and fill them in.
"""

from pathlib import Path

# --- Internal render resolution (scaled + letterboxed onto the real screen) ---
INTERNAL_WIDTH = 1200
INTERNAL_HEIGHT = 640

# --- Input mapping ---
# Keyboard (pygame key names, resolved at runtime). Defaults follow the common
# MAME / I-PAC keyboard-encoder layout. Pad 0 = P1 (blue), pad 1 = P2 (red).
KEYMAP = {
    0: dict(left=["K_LEFT"], right=["K_RIGHT"], up=["K_UP"], down=["K_DOWN"],
            a=["K_LCTRL", "K_SPACE", "K_RETURN"], start=["K_1"],
            remove_ion=["K_q"], add_ion=["K_e"]),
    1: dict(left=["K_d"], right=["K_g"], up=["K_r"], down=["K_f"],
            a=["K_a"], start=["K_2"],
            cool=["K_c"], passive_cool=["K_v"]),
}
SELECT_KEYS = ["K_ESCAPE"]

INPUT_CONFIG = {
    "p1": {
        "joystick_index": 0,
        "hat_index": 0,
        "axes": (0, 1),  # (x axis, y axis)
        # RAW button numbers (confirmed on the cabinet, see AGENTS.md):
        # printed L X R / Y B A = raw 4 0 5 / 3 2 1. The four face buttons
        # double as a d-pad (Y left, A right, X up, B down); L and R confirm.
        # In the SANDBOX, blue's L/R remove/add an ion, red's L cools while
        # held and R toggles passive cooling.
        "buttons": {"left": [3], "right": [1], "up": [0], "down": [2], "a": [4, 5],
                    "remove_ion": [4], "add_ion": [5]},
    },
    "p2": {
        "joystick_index": 1,
        "hat_index": 0,
        "axes": (0, 1),
        "buttons": {"left": [3], "right": [1], "up": [0], "down": [2], "a": [4, 5],
                    "cool": [4], "passive_cool": [5]},
    },
    "system": {
        # Select opens the pause menu. Quit combo: Start + Select held
        # together, on either controller.
        "start_button": 8,
        "select_button": 9,
        "keyboard_quit": "K_ESCAPE",  # only used to leave --input-test
    },
    "axis_deadzone": 0.5,
}

# Stored outside the package folder, so a redeploy doesn't wipe it
# (on Batocera, ~ is /userdata/system).
SCORE_FILE = Path.home() / ".ion_surfer_scores.json"

# --- Colors used outside the game's own palette (FPS overlay, --input-test) ---
COLOR_BACKGROUND = (6, 10, 24)
COLOR_TEXT = (195, 203, 232)
COLOR_FPS = (255, 211, 107)

# --- Debug ---
SHOW_FPS_DEFAULT = False
FPS = 60
