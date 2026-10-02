"""Single source of truth for input mapping and tuning constants.

Two genuinely independent mappings are involved in "which gate does this
physical button fire, and what does the on-screen legend call it" -- an
earlier version of this file conflated them (using one number for both),
which is exactly what caused the first real-hardware mapping bug:

  - GATE_AT_POSITION: which gate is PRINTED/shown at each of the 6 physical
    button positions (row-major, matching BUTTON_LABELS' order). This is
    about the cabinet's fixed layout, not its wiring, and is the same for
    both players' pads.
  - INPUT_CONFIG[player]["buttons"]: which RAW hardware button number
    (as `joystick.get_button(n)` sees it) each GATE is wired to. This is
    hardware/wiring-specific and can differ from the position order
    entirely -- confirmed via --input-test (2026-09-30) that on the real
    IconicArcade cabinet it does NOT follow print order at all (e.g. the
    button printed "X" is raw button 0, but the gate shown at that position,
    Y, is wired to a different raw number than you'd guess from the label).

If the cabinet's wiring ever changes (or this runs on different hardware),
re-run --input-test and update the `buttons` dicts below; GATE_AT_POSITION
and BUTTON_LABELS (the legend's fixed layout) should stay as-is since that
layout was separately confirmed correct.

P1's encoder also emits a keyboard keystroke matching each button's own
printed letter (l/x/r/b/y/a) *in addition to* the joystick signal -- so P1's
dev keyboard fallback below is deliberately chosen to avoid all six of those
letters; a fallback key that collided would double-fire two actions from one
real button press on the cabinet (this is exactly what caused the "one
button does two things" symptom in the first bug report: physical "A" sent
both raw button 1 *and* the keystroke "a", and "a" was gate X's old fallback
key). P2's encoder does not emit keystrokes, so no such collision risk there.

The "push up to confirm" gesture reads the stick as an ANALOG AXIS
(`vertical_axis`, SDL convention: negative = up), not a hat switch -- this
cabinet's sticks don't send hat events at all. Confirmed by reusing the
exact axis index and deadzone Quantum Pong already validated on this same
hardware for paddle movement (`vertical_axis: 1`, `AXIS_DEADZONE = 0.25`);
`hat_index` is kept as a harmless secondary check in case a future stick on
this cabinet does have one, but the axis is what actually works today.
"""

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
# INPUT_CONFIG's "buttons" dicts for the actual raw hardware numbers). Must
# move in lockstep with BUTTON_LABELS -- these two are parallel arrays over
# the same 6 physical positions, not independently reorderable.
GATE_AT_POSITION: tuple[str | None, ...] = ("X", "Y", "Z", None, "H", "RESET")

INPUT_CONFIG = {
    "p1": {
        "joystick_index": 0,
        "hat_index": 0,  # digital d-pad, if the stick has one -- most don't on this cabinet
        "vertical_axis": 1,  # confirmed on this cabinet via Quantum Pong's paddle input
        "buttons": {
            "X": 4,
            "Y": 0,
            "Z": 5,
            "H": 2,
            "RESET": 1,
        },
        "keyboard": {
            "X": "K_q",
            "Y": "K_w",
            "Z": "K_e",
            "H": "K_d",
            "RESET": "K_f",
        },
        "up_keyboard": "K_UP",
        "down_keyboard": "K_DOWN",  # pause menu only
    },
    "p2": {
        "joystick_index": 1,
        "hat_index": 0,
        "vertical_axis": 1,
        "buttons": {
            "X": 4,
            "Y": 0,
            "Z": 5,
            "H": 2,
            "RESET": 1,
        },
        "keyboard": {
            "X": "K_KP4",
            "Y": "K_KP5",
            "Z": "K_KP6",
            "H": "K_KP7",
            "RESET": "K_KP9",
        },
        "up_keyboard": "K_KP8",  # numpad 8 -- already spatially "up"
        "down_keyboard": "K_KP2",  # pause menu only
    },
    "system": {
        # Quit combo: Start + Select held together, on either controller.
        # Confirm button: printed A (raw 1), back: printed B (raw 2). The
        # cabinet-wide convention is A = confirm, B = back, Start = start the
        # game and pause it -- see "Button convention" and "Pausing" in
        # ../AGENTS.md. Raw 1 and 2 are also the RESET and H gates; they only
        # act as confirm/back on the title screen and in the pause menu.
        "confirm_button": 1,
        "back_button": 2,
        # Raw 9 is the button printed START and raw 8 is SELECT -- the
        # reverse of what these were set to originally. EmulationStation's own
        # es_input.cfg for this pad agrees (select id=8, start id=9), and the
        # symptom was unmistakable: SELECT confirmed menus, because the game
        # read raw 8 as "start". The quit combo is unaffected either way,
        # which is why it went unnoticed for so long.
        "start_button": 9,
        "select_button": 8,
        "keyboard_quit": "K_ESCAPE",
        # Dev keyboard for the pause menu: P pauses/resumes (P is not one of
        # the l/x/r/b/y/a letters P1's encoder types), Enter picks, Backspace
        # resumes, and each player's up/down keys move the selection.
        "keyboard_pause": "K_p",
        "keyboard_menu_confirm": "K_RETURN",
        "keyboard_menu_back": "K_BACKSPACE",
    },
}

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
