"""Single source of truth for resolution, timings, colours and input.

Joystick 0 = P1 (left, blue), joystick 1 = P2 (right, red). The raw button
numbers are the ones confirmed on the cabinet (see ../../../AGENTS.md):
printed A = 1, B = 2, X = 0, Y = 3, Start = 9, Select = 8.
"""

from __future__ import annotations

# --- Display -------------------------------------------------------------------
INTERNAL_WIDTH = 640
INTERNAL_HEIGHT = 360
FPS = 60
SHOW_FPS_DEFAULT = False


def frames(seconds: float) -> int:
    """Convert seconds to frame count at FPS."""
    return round(seconds * FPS)


# --- Stage and movement -------------------------------------------------------
FLOOR_Y = 300            # the floor line, in screen px
STAGE_LEFT, STAGE_RIGHT = 24, 616   # fighters' x is clamped to this
START_X = {"p1": 220, "p2": 420}


# --- Round timing and rules ---------------------------------------------------
ROUND_FRAMES = frames(60.0)
STAGES = ("lab", "cryo", "optics", "office", "toronto")   # the backdrops a match is fought in (stages.py)
STAGE_NAMES = {"lab": "SERVER RACK", "cryo": "SUPERCONDUCTOR", "optics": "OPTICAL LAB",
               "office": "QUANTUM SPACE", "toronto": "QUANTUM WEEK"}   # as CHOOSE YOUR STAGE shows them
TUNNEL_PAST = 50         # TUNNEL: PHOEBE re-forms this far past the rival's x
TUNNEL_EXPOSED = 4       # ... and can still be hit for this many frames of her dissolve
BOX_SPLIT = 120          # THE BOX: ERWIN's second box stands this far towards the rival (on the stage)
BOX_FRAMES = frames(1.5)  # ... and he collapses himself after this long in the boxes at the latest
DRIVE_SLOT_Y = 80        # DOS: FLOPPY and a PASTE leave his drive slot this high above his feet, px
COPY_CAUGHT_RECOVERY = 6  # ... and a COPY that catches a shot recovers in this many frames (a miss: all 18)
PASTE_SPEED = 4.0        # ... and a PASTE flies at least this fast, px per frame (a falling BOX DROP has
                         # next to no speed of its own across)
CHARGE_CAP = 6           # AMPLITUDE AMPLIFICATION: M-CUTIE's wave grows to at most this many steps
CHARGE_WAIT = frames(0.25)  # ... and fires this long after her last X press (15 frames), or at once at the cap
TRAP_REACH = 70          # ION TRAP: she sets it this far in front of her, px
TRAP_ARM = frames(0.3)   # ... it arms this long after it is set (18 frames)
TRAP_LIFE = frames(10.0)  # ... and is gone this long after (600 frames), if nobody stepped in
TRAP_GRACE = frames(0.3)  # a rival released from a trap's hold can't be caught by any trap for this long (18 frames)
TRAP_MAX = 2             # ... at most this many of hers at once: one more replaces the oldest
ECHO_DELAY = frames(0.2)  # ALICE & BOB: Bob replays Alice's inputs this many frames later (12)
ECHO_GAP = 40            # ... standing this far behind her, px
ECHO_SLACK = 4           # ... and walks back to that spot by himself once he is this far off it, px
DECOHERE_FRAMES = frames(3.0)   # a knockdown on Bob decoheres him: gone this long (180 frames) ...
DECOHERE_FADE = frames(0.5)     # ... of which he fades out for the first 30 ...
REFORM_FRAMES = 12       # ... and he re-forms over this many frames as he comes back (drawn only)
TOSS_FRAMES = 16         # KEY EXCHANGE: the photon is this long in the air from Alice's hand to Bob's
TOSS_ARC = 40            # ... along an arc this many px over the straight line
TOSS_FROM = (-36, 78)    # ... from her back hand (px behind her x, px up) ...
TOSS_TO = (8, 120)       # ... to his raised hand (px in front of his x, px up)
TOSS_SIZE = 14           # ... a photon this many px across
ROUNDS_TO_WIN = 2
HITSTOP = 5
HITSTOP_KNOCKDOWN = 10   # a hit that knocks down freezes the fight a little longer
SWITCH_RECOVERY = 10     # after Y (an H on yourself): frames you can't attack (you can move)
# GAME RULE: a wrong-colour hit changes nothing (that is the physics: no damage), but the
# defender is still pushed back (at least BLOCK_PUSH px/frame) and held in block-stun for the
# move's hitstun, so the attacker's string goes on and its matching half can land.
BLOCK_PUSH = 2.0
BLOCK_HITSTOP = 3
BUFFER_FRAMES = 6
CHAIN_MAX = 3
BODY_MARGIN = 8          # the push box reaches this far past each fighter's standing hurtbox, px
                         # (fight.body_width: 44 between two ROBERTs, 52 between two BOHRs)
THROW_SLACK = 6          # a throw reaches this far past the push box (px between the fighters' x)
THROW_RANGE = 50         # two ROBERTs' push box plus THROW_SLACK: a lone Fighter's throw range
# SUPERposition (superpos.py; docs/superpowers/specs/2026-10-22-brawl-ket-superposition-design.md):
# a bar of two halves, green and purple, each SUPER_HALF points of damage dealt in that basis
# (damage taken counts half); full, A and B pressed within SUPER_WINDOW frames fire the super,
# and the fight freezes SUPER_FREEZE frames for its call
SUPER_HALF = 40
SUPER_WINDOW = 3
SUPER_FREEZE = frames(0.5)
# DOS's BLUE SCREEN OF DEATH: every rival on the ground within CRASH_REACH px is frozen for
# CRASH_HOLD frames, and DOS comes down on them in a leap CRASH_LEAP frames long
CRASH_REACH = 200
CRASH_HOLD = 50
CRASH_LEAP = 40


# --- Screen transitions and input timing -------------------------------------
ROUND_INTRO_FRAMES = frames(2.0)
ROUND_END_FRAMES = frames(2.5)
MATCH_RESULT_LOCK = frames(1.0)
KO_SLOW_FRAMES = frames(1.2)    # after a K.O. the round end plays in slow motion this long,
KO_SLOW_RATE = 3                # stepping the fight once every this many frames
ATTRACT_DELAY = frames(4.0)
DEMO_FRAMES = frames(20.0)      # the title's bot demo runs this long, then the rules card
CARD_FRAMES = frames(9.0)       # the COLOUR MUST MATCH card: three beats of 3 s
TUTORIAL_LOCK = frames(0.3)     # the HOW TO PLAY card ignores buttons this long
IDLE_TIMEOUT = frames(60.0)
BACK_HOLD_TO_QUIT = frames(2.0)


# --- Colours (players) -------------------------------------------------------
PLAYER_COLORS = {"p1": (64, 136, 248), "p2": (240, 64, 72)}  # left blue, right red
COLOR_FPS = (248, 208, 104)


# --- Input -------------------------------------------------------------------------
INPUT_CONFIG = {
    "p1": {"joystick_index": 0, "hat_index": 0, "axes": (0, 1)},
    "p2": {"joystick_index": 1, "hat_index": 0, "axes": (0, 1)},
    "system": {
        "a_button": 1, "b_button": 2, "x_button": 0, "y_button": 3, "start_button": 9,
        "select_button": 8, "keyboard_quit": "K_ESCAPE",
    },
    "axis_deadzone": 0.25,
}


# Keyboard: a dev fallback only. The cabinet loader passes --no-keyboard, so
# the keystrokes Batocera's evmapy fakes for P1's pad never reach the game.
KEYMAP = {
    # P1's dev keys must avoid the pad's own letters l, x, r, b, y, a.
    "p1": {"left": ["K_s"], "right": ["K_f"], "up": ["K_e"], "down": ["K_d"],
           "a": ["K_q"], "b": ["K_w"], "x": ["K_t"], "y": ["K_g"], "start": ["K_1"]},
    "p2": {"left": ["K_LEFT"], "right": ["K_RIGHT"], "up": ["K_UP"], "down": ["K_DOWN"],
           "a": ["K_PERIOD"], "b": ["K_COMMA"], "x": ["K_SLASH"], "y": ["K_SEMICOLON"], "start": ["K_2"]},
}


# --- Sound -------------------------------------------------------------------------
MASTER_VOLUME = 0.8
