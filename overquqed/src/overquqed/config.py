"""Single source of truth for resolution, input mapping and tuning constants.

Joystick 0 = P1, joystick 1 = P2, same as the sibling games. A/B/Y raw
numbers are confirmed on the cabinet (see ../../../AGENTS.md), and so are
Start = 9 / Select = 8 (not the other way round). Every menu also accepts A
as "confirm", per the cabinet's button convention.
"""

from pathlib import Path

# --- Internal render resolution (4:3, letterboxed onto the real screen) ---
# 480x360 scales by exactly 3 onto the cabinet's 1920x1080 panel (1440x1080
# plus pillarbox bars), so every art pixel stays a crisp 3x3 block. 24 px
# tiles give a 20x15 grid: HUD rows 0-2, kitchen rows 3-10, dining room 11-14.
INTERNAL_WIDTH = 480
INTERNAL_HEIGHT = 360
TILE = 24
GRID_W = INTERNAL_WIDTH // TILE  # 20
GRID_H = INTERNAL_HEIGHT // TILE  # 15
HUD_HEIGHT = 3 * TILE  # ticket strip
KITCHEN_Y = HUD_HEIGHT  # top edge of map row 0

# --- Input mapping ---
# Raw button numbers confirmed on the cabinet (both pads, see AGENTS.md):
# printed L X R / Y B A = raw 4 0 5 / 3 2 1. The stick is an analog axis; the
# hat is only read as a fallback for other pads.
INPUT_CONFIG = {
    "p1": {
        "joystick_index": 0,
        "hat_index": 0,
        "axes": (0, 1),  # (x axis, y axis), SDL convention: negative = left/up
        "buttons": {
            "pick": [1],  # printed A: pick up / put down / take / serve
            "use": [2],  # printed B: work the station in front of you
            "swap": [3],  # printed Y: swap chef (1-player mode)
        },
    },
    "p2": {
        "joystick_index": 1,
        "hat_index": 0,
        "axes": (0, 1),
        "buttons": {
            "pick": [1],
            "use": [2],
            "swap": [3],
        },
    },
    "system": {
        # Start confirms / pauses, Select goes back. Quit: Start + Select held
        # together on the same pad. Confirmed on the cabinet (see AGENTS.md).
        "start_button": 9,
        "select_button": 8,
    },
    "axis_deadzone": 0.5,
}

# Keyboard fallback for local dev (ignored on the cabinet via --no-keyboard).
# P1 deliberately uses exactly the keys Batocera's evmapy emits for P1's pad
# for the *same* actions (arrows, a, b, y, Enter, Space), so a double-fire
# would only ever repeat the same action. P2 avoids every key evmapy emits
# for a control this game reads. tests/test_config.py enforces both.
KEYMAP = {
    "p1": {
        "left": ["K_LEFT"], "right": ["K_RIGHT"], "up": ["K_UP"], "down": ["K_DOWN"],
        "pick": ["K_a"], "use": ["K_b"], "swap": ["K_y"],
        "start": ["K_RETURN"], "select": ["K_SPACE"],
    },
    "p2": {
        "left": ["K_j"], "right": ["K_l"], "up": ["K_i"], "down": ["K_k"],
        "pick": ["K_o"], "use": ["K_p"], "swap": ["K_u"],
        "start": ["K_2"], "select": ["K_BACKSPACE"],
    },
}
KEYBOARD_QUIT = "K_ESCAPE"

# What evmapy (batocera-pygame/evmapy.keys) turns P1's pad into. Used by the
# config tests only. "l" is P1's printed L, a button this game never reads.
EVMAPY_P1_KEYS = {
    "a": "K_a", "b": "K_b", "x": "K_x", "y": "K_y", "l": "K_l", "r": "K_r",
    "l2": "K_m", "r2": "K_s", "l3": "K_n", "r3": "K_t", "hotkey": "K_h",
    "start": "K_RETURN", "select": "K_SPACE",
    "up": "K_UP", "down": "K_DOWN", "left": "K_LEFT", "right": "K_RIGHT",
    "stick_up": "K_KP8", "stick_down": "K_KP2", "stick_left": "K_KP4", "stick_right": "K_KP6",
}
EVMAPY_UNUSED_BUTTONS = {"l"}  # P1 buttons whose keystroke nothing here reads

# Menu auto-repeat for held stick directions.
REPEAT_DELAY = 0.30
REPEAT_INTERVAL = 0.10

# --- Session / arcade behaviour ---
BACK_HOLD_TO_QUIT = 2.0  # hold Select this long on the title screen to quit
IDLE_TIMEOUT = 60.0  # seconds without input on any screen -> back to title
ATTRACT_DELAY = 12.0  # seconds idle on the title before the demo loop starts

# Stored outside the package folder, so a redeploy doesn't wipe it
# (on Batocera, ~ is /userdata/system).
HISCORE_FILE = Path.home() / ".overquqed_hiscores.json"

MASTER_VOLUME = 0.7
MUSIC_VOLUME = 0.35

FPS = 60
SHOW_FPS_DEFAULT = False
