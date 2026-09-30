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
            a=["K_LCTRL", "K_SPACE", "K_RETURN"], start=["K_1"]),
    1: dict(left=["K_d"], right=["K_g"], up=["K_r"], down=["K_f"],
            a=["K_a"], start=["K_2"]),
}
SELECT_KEYS = ["K_ESCAPE"]

INPUT_CONFIG = {
    "p1": {
        "joystick_index": 0,
        "hat_index": 0,
        "axes": (0, 1),  # (x axis, y axis)
        # The game has a single action button, so every one of the six
        # cabinet buttons triggers it -- no need to know the exact layout.
        "buttons": {"a": [0, 1, 2, 3, 4, 5]},
    },
    "p2": {
        "joystick_index": 1,
        "hat_index": 0,
        "axes": (0, 1),
        "buttons": {"a": [0, 1, 2, 3, 4, 5]},
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
