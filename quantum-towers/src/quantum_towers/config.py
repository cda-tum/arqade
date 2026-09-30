"""Single source of truth for input mapping and tuning constants.

Button indices are placeholders -- the IconicArcade cabinet's exact mapping
is unknown. Run `--input-test` on the real hardware and fill these in.
"""

# --- Internal render resolution (scaled + letterboxed onto the real screen) ---
INTERNAL_WIDTH = 480
INTERNAL_HEIGHT = 270

# --- Input mapping ---
# 5 gate buttons per player (button index 4 is unused), plus the joystick's
# own "up" direction, which has a real job: confirming a climb (see
# main.py's confirm-to-climb mechanic).
ACTION_NAMES = ("X", "Y", "Z", "H", "RESET")

# The IconicArcade cabinet's 6 physical buttons, in the same index order as
# each player's "buttons" mapping below -- used only to label the on-screen
# legend (index -> physical name), since a raw button *index* means nothing
# to someone looking at the actual cabinet. Confirm/adjust the ORDER against
# real hardware via --input-test; this is a naming guess, same placeholder
# status as the indices themselves. Index 4 ("Y") has no gate mapped to it.
BUTTON_LABELS = ("L", "X", "R", "B", "Y", "A")

INPUT_CONFIG = {
    "p1": {
        "joystick_index": 0,
        "hat_index": 0,  # digital d-pad/stick, read as a hat -- confirm on real hardware
        "buttons": {
            "X": 0,
            "Y": 1,
            "Z": 2,
            "H": 3,
            "RESET": 5,
        },
        "keyboard": {
            "X": "K_a",
            "Y": "K_s",
            "Z": "K_d",
            "H": "K_f",
            "RESET": "K_h",
        },
        "up_keyboard": "K_UP",
    },
    "p2": {
        "joystick_index": 1,
        "hat_index": 0,
        "buttons": {
            "X": 0,
            "Y": 1,
            "Z": 2,
            "H": 3,
            "RESET": 5,
        },
        "keyboard": {
            "X": "K_KP4",
            "Y": "K_KP5",
            "Z": "K_KP6",
            "H": "K_KP7",
            "RESET": "K_KP9",
        },
        "up_keyboard": "K_KP8",  # numpad 8 -- already spatially "up"
    },
    "system": {
        # Quit combo: Start + Select held together, on either controller.
        "start_button": 8,
        "select_button": 9,
        "keyboard_quit": "K_ESCAPE",
    },
}

# --- Tower ---
TOWER_HEIGHT = 16  # floors to win
KNOCKBACK_FLOORS = 3
CHARGES_TO_ATTACK = 3
SEARCH_MAX_DEPTH = 6  # BFS depth cap for minimum-steps search
ATTACK_BEAM_DURATION = 0.4  # seconds the attack-beam effect (and the shooter's recoil) plays for
PERFECT_FLASH_DURATION = 0.6  # seconds the "minimum steps" celebration plays for
CLIMB_ANIM_DURATION = 0.4  # seconds a floor-change (up OR down) takes to visually settle
TOWER_BAND_HEIGHT = 46  # fixed px per floor -- the tower scrolls past this unit, not a
# fraction of the viewport, since it's now taller than the viewport and only
# partially visible at once.

# --- Confirm-to-climb ---
# Matching the target no longer auto-advances a floor -- the player must
# push up to confirm it, which also means a wrong confirm can be punished,
# adding real risk instead of pure button-mashing.
STUN_DURATION = 1.0  # seconds of locked-out input after confirming on the wrong state
PUSH_UP_HINT_DELAY = 2.5  # seconds sitting on a correct, unconfirmed state before the hint shows

# --- Game flow ---
IDLE_TIMEOUT_SECONDS = 60.0
WINNER_SCREEN_DURATION = 5.0
TITLE_BLINK_PERIOD = 1.0

# --- Colors ---
# Outdoor scene, not a black void: sky above a horizon, grass below it.
COLOR_SKY_TOP = (120, 170, 235)
COLOR_SKY_BOTTOM = (190, 220, 245)
COLOR_SUN = (255, 235, 160)
COLOR_CLOUD = (250, 250, 255)
COLOR_GRASS = (86, 150, 70)
COLOR_GRASS_DARK = (70, 130, 56)

COLOR_BACKGROUND = (10, 10, 20)  # non-gameplay screens (title/winner/input-test)
COLOR_TEXT = (255, 255, 255)
COLOR_TEXT_SHADOW = (20, 20, 25)
COLOR_FPS = (255, 210, 0)

# Stone tower, not a battery: warm grey stone, gold for the lit/current
# target floor (like a beacon), cool slate for the not-yet-revealed one.
COLOR_TOWER = (128, 120, 110)
COLOR_TOWER_TRIM = (90, 84, 76)
COLOR_PLAYER_1 = (0, 190, 210)
COLOR_PLAYER_2 = (225, 100, 30)
COLOR_TARGET = (235, 175, 60)
COLOR_NEXT_TARGET = (150, 140, 165)
COLOR_UNKNOWN = (95, 90, 84)
COLOR_CHARGE_FULL = (255, 210, 0)
COLOR_CHARGE_EMPTY = (70, 66, 60)
COLOR_STUN = (220, 60, 60)
COLOR_HINT = (255, 235, 90)

# --- Debug ---
SHOW_FPS_DEFAULT = False
FPS = 60
