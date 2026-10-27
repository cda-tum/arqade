"""Single source of truth for input mapping and tuning constants.

The first pad is P1's, the second P2's, same as the sibling games. Raw button
and axis numbers live in arqade_common.input, shared by all games; check new
hardware with `--input-test`.
"""

from pathlib import Path

# --- Internal render resolution (4:3, letterboxed onto the real screen) ---
INTERNAL_WIDTH = 960
INTERNAL_HEIGHT = 720

# --- Input mapping ---
# Pads, button numbers and the keyboard layout are shared by all games: see
# arqade_common.input (and input.ACTION_BUTTONS: A fires, B switches color).
INPUT_CONFIG = {
    "axis_deadzone": 0.5,
}

# --- Display / effects ---
SHOW_SCANLINES = True
GLOW = True  # additive glow effects; set False if the cabinet drops frames
MASTER_VOLUME = 0.8  # 0.0 .. 1.0
QUIT_FROM_MENU = True  # holding Select on the first menu page quits
BACK_HOLD_TO_QUIT = 2.0  # seconds

# Stored outside the package folder, so a redeploy doesn't wipe it
# (on Batocera, ~ is /userdata/system).
HISCORE_FILE = Path.home() / ".error_invaders_hiscores.json"

FPS = 60
SHOW_FPS_DEFAULT = False
