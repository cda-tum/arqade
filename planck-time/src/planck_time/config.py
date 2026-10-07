"""Single source of truth for resolution, timings, colours and input.

Joystick 0 = P1 (left, blue), joystick 1 = P2 (right, red). The raw button
numbers are the ones confirmed on the cabinet (see ../../../AGENTS.md):
printed A = 1, B = 2, Select = 8, Start = 9. Every microgame uses only the
stick and A; B, Start and Select are for menus, pausing and quitting.
"""

from __future__ import annotations

from pathlib import Path

# --- Display -------------------------------------------------------------------
INTERNAL_WIDTH = 640
INTERNAL_HEIGHT = 360  # exactly x3 onto the cabinet's 1920x1080 panel
FPS = 60
SHOW_FPS_DEFAULT = False
SCREEN_W, SCREEN_H = 240, 160  # one GBA screen, per player
SCREEN_CENTERS = {"p1": (160, 196), "p2": (480, 196)}  # each player's screen, in the 640x360 frame
SOLO_CENTER = (320, 196)

# --- The beats of a microgame ------------------------------------------------------
INTRO_TIME = 1.5
RESULT_TIME = 1.2
SPEED_UP_TIME = 1.2
PLAY_TIME = 5.0  # at level 0...
PLAY_TIME_FACTOR = 0.9  # ...times this per level...
PLAY_TIME_MIN = 2.5  # ...down to this
GAMES_PER_LEVEL = 4
BOSS_EVERY = 12  # a boss after every this many wins
BOSS_CARD_TIME = 2.0  # the BOSS! warning before it
BOSS_LINGER = 1.2  # a boss ends this long after everyone is done, not at the timer
SPEED_PER_LEVEL = 0.15  # objects move this much faster per level

# --- Lives, scores, the rest of the flow ------------------------------------------
LIVES = 4
GAME_OVER_TIME = 2.5
HISCORES_TIME = 8.0
MATCH_RESULT_LOCK = 1.0  # seconds before a result screen takes input
ATTRACT_DELAY = 3.0  # untouched seconds on the title before the bots play
IDLE_TIMEOUT = 60.0
BACK_HOLD_TO_QUIT = 2.0  # hold Select this long on the title to quit
HISCORE_SLOTS = 10
# Outside the package folder, so a redeploy doesn't wipe it.
SCORE_FILE = Path.home() / ".planck_time_scores.json"

# --- Colours (players; the rest lives in palette.py) ---------------------------------
PLAYER_COLORS = {"p1": (64, 136, 248), "p2": (240, 64, 72)}  # left blue, right red
COLOR_FPS = (248, 208, 104)

# --- Input -------------------------------------------------------------------------
INPUT_CONFIG = {
    "p1": {"joystick_index": 0, "hat_index": 0, "axes": (0, 1)},
    "p2": {"joystick_index": 1, "hat_index": 0, "axes": (0, 1)},
    "system": {
        "a_button": 1, "back_button": 2, "start_button": 9, "select_button": 8,
        "keyboard_quit": "K_ESCAPE",
    },
    "axis_deadzone": 0.25,  # analog stick
    "step_threshold": 0.5,  # a stick push past this counts as a step
}
REPEAT_DELAY = 0.22  # auto-repeat for stick steps (cursors, grids, menus)
REPEAT_INTERVAL = 0.11

# Keyboard: a dev fallback only. The cabinet loader passes --no-keyboard, so
# the keystrokes Batocera's evmapy fakes for P1's pad never reach the game.
KEYMAP = {
    # ESDF, not WASD: P1's dev keys must avoid the pad's own letters l, x, r, b, y, a.
    "p1": {"left": ["K_s"], "right": ["K_f"], "up": ["K_e"], "down": ["K_d"], "a": ["K_q"],
           "back": ["K_w"], "start": ["K_1"]},
    "p2": {"left": ["K_LEFT"], "right": ["K_RIGHT"], "up": ["K_UP"], "down": ["K_DOWN"], "a": ["K_PERIOD"],
           "back": ["K_COMMA"], "start": ["K_2"]},
}

# --- Sound -------------------------------------------------------------------------
MASTER_VOLUME = 0.8
MUSIC_VOLUME = 0.35
