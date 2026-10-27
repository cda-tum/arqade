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
# Pads, button numbers and the keyboard layout are shared by all games: see
# arqade_common.input (and input.ACTION_BUTTONS: A picks, B uses a station, Y
# swaps chef). The cabinet loader passes --no-keyboard, so the keystrokes
# Batocera's evmapy fakes for P1's pad never reach the game.
AXIS_DEADZONE = 0.5

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
