"""Single source of truth for input mapping and tuning constants.

The first pad is P1's (blue), the second P2's (red). Raw button and axis
numbers live in arqade_common.input, shared by all games.
"""

from pathlib import Path

# --- Internal render resolution (scaled + letterboxed onto the real screen) ---
INTERNAL_WIDTH = 1200
INTERNAL_HEIGHT = 640

# --- Input mapping ---
# Pads, button numbers and the keyboard layout are shared by all games: see
# arqade_common.input (and input.BUTTON_ACTIONS for what each button does).
# Start pauses (and resumes) during play, on either controller; Select is
# never a pause button: it is half of the quit combo, Start + Select held
# together by one player.
INPUT_CONFIG = {
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
