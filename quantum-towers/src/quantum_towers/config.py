"""Single source of truth for input mapping and tuning constants.

Which gate a button fires is decided by where it sits, not by its wiring:
GATE_AT_POSITION says which gate is PRINTED/shown at each of the 6 physical
button positions (row-major, matching BUTTON_LABELS' order), the same for
both players' pads. GATE_BUTTONS follows from the two. Raw button numbers
(which differ from the print order on the cabinet: the button printed "X" is
raw 0) and the keyboard layout are shared by all games and live in
arqade_common.input; re-run --input-test on new hardware.

The "push up to confirm" gesture reads the stick's vertical axis (SDL
convention: negative = up) past AXIS_DEADZONE, the value Quantum Pong
validated on this same hardware, or the d-pad or the up key.
"""

from pathlib import Path

# --- Internal render resolution (scaled + letterboxed onto the real screen) ---
INTERNAL_WIDTH = 480
INTERNAL_HEIGHT = 270

# --- Input mapping ---
# 5 gate buttons per player (button index 4 is unused), plus the joystick's
# own "up" direction, which has a real job: confirming a climb (see
# main.py's confirm-to-climb mechanic).
ACTION_NAMES = ("X", "Y", "Z", "H", "RESET")

# The IconicArcade cabinet's 6 physical buttons' PRINTED labels, row-major
# (index 0-2 top row, 3-5 bottom row) -- purely for the on-screen legend.
# Confirmed against the real cabinet (2026-09-30): bottom row is Y, B, A
# left-to-right -- NOT B, Y, A as an earlier version of this file assumed.
BUTTON_LABELS = ("L", "X", "R", "Y", "B", "A")

# Which gate is shown at each of those 6 positions (same order as
# BUTTON_LABELS) -- None means no gate is mapped to that position. This is
# about the cabinet's fixed physical layout, NOT wiring, so it's the same
# for both players regardless of how their individual pads are wired (see
# arqade_common.input for the actual raw hardware numbers). Must
# move in lockstep with BUTTON_LABELS -- these two are parallel arrays over
# the same 6 physical positions, not independently reorderable.
GATE_AT_POSITION: tuple[str | None, ...] = ("X", "Y", "Z", None, "H", "RESET")

# Which printed button (see arqade_common.input) each gate is on, from the
# two tables above: the same for both players and on the keyboard, where each
# player's half has the pad's 2x3 buttons. A confirms and B goes back in the
# menus (they are also the RESET and H gates, which only act as confirm/back
# on the title screen and in the pause menu); Start starts and pauses.
GATE_BUTTONS = {gate: label.lower() for label, gate in zip(BUTTON_LABELS, GATE_AT_POSITION) if gate}

# How far the vertical axis must move (SDL convention: negative = up) before
# it counts as "pushed up" -- same value Quantum Pong already confirmed on
# this exact cabinet's sticks.
AXIS_DEADZONE = 0.25

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

# --- Solo time trial ---
# Every solo tower has exactly this many minimum presses in total, so fastest-clear
# times are comparable. Measured once: the median of minimum_total over 2000 fully
# random towers (targets.generate_target_sequence(Random(seed), TOWER_HEIGHT), seeds
# 0..1999). Observed range 19..33, mean 25.1, median 25.
SOLO_TOTAL_PRESSES = 25
SOLO_COUNTDOWN = 3.0  # seconds of 3, 2, 1 before GO
SOLO_GO_DURATION = 0.6  # seconds GO! stays up once the clock is running
SOLO_FINISH_DURATION = 3.0  # seconds the finish banner shows the time
SOLO_TOWER_TOP = 26  # px: the solo tower starts below the big timer
NAME_REPEAT_DELAY = 0.3  # initials entry: a held stick repeats after this...
NAME_REPEAT_INTERVAL = 0.1  # ...then every this many seconds
TIMES_TABLE_DURATION = 8.0  # the table goes back to the title by itself after this
TIMES_TABLE_LOCK = 1.0  # ...and takes A, B or Start only after this
TIMES_FILE = Path.home() / ".quantum_towers_times.json"  # outside the package: a redeploy keeps it
TIMES_SLOTS = 10
