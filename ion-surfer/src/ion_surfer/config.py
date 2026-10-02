"""Single source of truth for input mapping and tuning constants.

Button/axis indices follow the same cabinet layout as Quantum Pong / Quantum
Towers (joystick 0 = P1, joystick 1 = P2, Start = raw 9, Select = raw 8),
confirmed on the cabinet -- see the comments below and ../AGENTS.md.
"""

from pathlib import Path

# --- Internal render resolution (scaled + letterboxed onto the real screen) ---
INTERNAL_WIDTH = 1200
INTERNAL_HEIGHT = 640

# --- Input mapping ---
# Keyboard (pygame key names, resolved at runtime). Defaults follow the common
# MAME / I-PAC keyboard-encoder layout. Pad 0 = P1 (blue), pad 1 = P2 (red).
# Start is 1/2 and Select is the coin key 5/6, as on an I-PAC, so the keyboard
# also has Start + Select (1+5, 2+6) as the quit combo.
KEYMAP = {
    0: dict(left=["K_LEFT"], right=["K_RIGHT"], up=["K_UP"], down=["K_DOWN"],
            confirm=["K_LCTRL", "K_SPACE", "K_RETURN"], back=["K_BACKSPACE"],
            start=["K_1"], select=["K_5"],
            remove_ion=["K_q"], add_ion=["K_e"]),
    1: dict(left=["K_d"], right=["K_g"], up=["K_r"], down=["K_f"],
            confirm=["K_a"], back=["K_s"], start=["K_2"], select=["K_6"],
            cool=["K_c"], passive_cool=["K_v"]),
}
# Extra keyboard-only pause/resume key, besides Start (1/2).
PAUSE_KEYS = ["K_ESCAPE"]

INPUT_CONFIG = {
    "p1": {
        "joystick_index": 0,
        "hat_index": 0,
        "axes": (0, 1),  # (x axis, y axis)
        # RAW button numbers (confirmed on the cabinet, see AGENTS.md):
        # printed L X R / Y B A = raw 4 0 5 / 3 2 1. The four face buttons
        # double as a d-pad in-game (Y left, A right, X up, B down).
        # A and B additionally carry the cabinet-wide menu convention --
        # A confirms, B goes back (see "Button convention" in ../AGENTS.md).
        # One button can drive several actions; the menu code checks
        # confirm/back first and returns, so B never also scrolls down.
        # In the SANDBOX, blue's L/R remove/add an ion, red's L cools while
        # held and R toggles passive cooling.
        "buttons": {"left": [3], "right": [1], "up": [0], "down": [2],
                    "confirm": [1], "back": [2],
                    "remove_ion": [4], "add_ion": [5]},
    },
    "p2": {
        "joystick_index": 1,
        "hat_index": 0,
        "axes": (0, 1),
        "buttons": {"left": [3], "right": [1], "up": [0], "down": [2],
                    "confirm": [1], "back": [2],
                    "cool": [4], "passive_cool": [5]},
    },
    "system": {
        # Start pauses (and resumes) during play, on either controller --
        # the cabinet's pause convention (see "Pausing" in ../AGENTS.md).
        # Select is never a pause button: it is half of the quit combo,
        # Start + Select held together on either controller. In the SANDBOX
        # alone it also fires that pad's laser kick.
        # Raw 9 is the button printed START and raw 8 is SELECT -- the
        # reverse of what these were set to originally. EmulationStation's own
        # es_input.cfg for this pad agrees (select id=8, start id=9), and the
        # symptom was unmistakable: SELECT confirmed menus, because the game
        # read raw 8 as "start". The quit combo is unaffected either way,
        # which is why it went unnoticed for so long.
        "start_button": 9,
        "select_button": 8,
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
