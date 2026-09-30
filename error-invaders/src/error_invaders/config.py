"""Single source of truth for input mapping and tuning constants.

Joystick 0 = P1, joystick 1 = P2, same as Quantum Pong / Quantum Towers. The
fire/swap button numbers are confirmed on the cabinet; Start = 8 / Select = 9
are still placeholders -- check them with `--input-test`.
"""

from pathlib import Path

# --- Internal render resolution (4:3, letterboxed onto the real screen) ---
INTERNAL_WIDTH = 960
INTERNAL_HEIGHT = 720

# --- Input mapping ---
# Keyboard presets (pygame key names, resolved at runtime). Most arcade
# encoders emulate a keyboard; pick the layout that matches.
#  "default": P1 WASD + Y/X, P2 arrows + comma/period (same as the browser version)
#  "mame":    MAME defaults - P1 arrows + LCtrl/LAlt, P2 RFDG + A/S, 1/2 = start
KEY_PRESET = "default"
KEY_PRESETS = {
    "default": {
        "p1": {"left": ["K_a"], "right": ["K_d"], "up": ["K_w"], "down": ["K_s"],
               "fire": ["K_y", "K_z"], "swap": ["K_x"]},  # Y and Z: works on QWERTZ and QWERTY
        "p2": {"left": ["K_LEFT"], "right": ["K_RIGHT"], "up": ["K_UP"], "down": ["K_DOWN"],
               "fire": ["K_COMMA"], "swap": ["K_PERIOD"]},
    },
    "mame": {
        "p1": {"left": ["K_LEFT"], "right": ["K_RIGHT"], "up": ["K_UP"], "down": ["K_DOWN"],
               "fire": ["K_LCTRL"], "swap": ["K_LALT"]},
        "p2": {"left": ["K_d"], "right": ["K_g"], "up": ["K_r"], "down": ["K_f"],
               "fire": ["K_a"], "swap": ["K_s"]},
    },
}
KEYS_CONFIRM = ["K_RETURN", "K_KP_ENTER", "K_1", "K_2"]
KEYS_BACK = ["K_ESCAPE"]

# Joysticks. Raw button numbers confirmed on the cabinet (both pads, see
# ../AGENTS.md): printed L X R / Y B A = raw 4 0 5 / 3 2 1. The stick is an
# analog axis there; the hat is only read as a fallback for other pads.
INPUT_CONFIG = {
    "p1": {
        "joystick_index": 0,
        "hat_index": 0,
        "axes": (0, 1),  # (x axis, y axis)
        "buttons": {
            "fire": [1],  # printed A
            "swap": [2],  # printed B
        },
    },
    "p2": {
        "joystick_index": 1,
        "hat_index": 0,
        "axes": (0, 1),
        "buttons": {
            "fire": [1],  # printed A
            "swap": [2],  # printed B
        },
    },
    "system": {
        # Start confirms, Select goes back (to the menu). Quit combo: Start +
        # Select held together, on either controller.
        "start_button": 8,
        "select_button": 9,
    },
    "axis_deadzone": 0.5,
}

# --- Display / effects ---
SHOW_SCANLINES = True
GLOW = True  # additive glow effects; set False if the cabinet drops frames
MASTER_VOLUME = 0.8  # 0.0 .. 1.0
QUIT_FROM_MENU = True  # ESC / holding Select on the first menu page quits
BACK_HOLD_TO_QUIT = 2.0  # seconds

# Stored outside the package folder, so a redeploy doesn't wipe it
# (on Batocera, ~ is /userdata/system).
HISCORE_FILE = Path.home() / ".error_invaders_hiscores.json"

FPS = 60
SHOW_FPS_DEFAULT = False
