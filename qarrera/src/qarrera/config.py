"""Single source of truth for resolution, rules tuning, colours and input.

Joystick 0 is the left pad, joystick 1 the right one, same as the sibling
games. The raw button numbers are the ones confirmed on the cabinet (see
../../../AGENTS.md): printed X = 0, A = 1, B = 2, Y = 3, Select = 8,
Start = 9. Axis 1 is the stick's vertical axis (negative = up, confirmed);
axis 0 being horizontal still wants an --input-test check on the cabinet.

The race happens in a world measured in units: distances are units,
speeds units/s, accelerations units/s^2, heights units up. A fixed
isometric camera (camera.py, CAM_*) follows the leader; whoever falls off
the screen is put back in at the back of the pack. It is drawn in 3D with
OpenGL into a 960x540 frame, scaled x2 onto the cabinet's 1920x1080.
"""

from __future__ import annotations

from dataclasses import dataclass

# --- Display -------------------------------------------------------------------
INTERNAL_WIDTH = 960
INTERNAL_HEIGHT = 540  # exactly x2 onto the cabinet's 1920x1080 panel
FPS = 60
SHOW_FPS_DEFAULT = False

# The camera: a fixed isometric view (orthographic, from the south-west and
# above) that follows the leader. It never turns, so the screen never
# swings round with the track; the leader drives across it, and the pack
# trails behind towards an edge.
CAM_YAW = -45.0  # degrees: the world heading it looks along (north-east)
CAM_PITCH = 50.0  # degrees below the horizon
CAM_VIEW = 520.0  # world units across the screen
CAM_DISTANCE = 340.0  # where its eye sits for the fog (orthographic: no effect on size)
CAM_AHEAD = 30.0  # it centres this far ahead of the leader
CAM_FOLLOW = 0.25  # seconds: how closely it follows (smaller is tighter)
VOXEL_SIZE = 1.35  # world units per voxel of a racer's model
# A racer that stands on the wire itself (voxels.RIDERS: ROBERT, grinding it)
# leans into corners, more the harder it corners, and sways a little all the time.
RIDER_LEAN = 0.32  # radians of lean per unit of corner load (render.py)
RIDER_LEAN_MAX = 0.42  # radians
RIDER_SWAY = 0.06  # radians: the sway's size
RIDER_SWAY_RATE = 2.4  # radians per second: its pace
HUD_BAND = 46  # the strip along the top of the 960x540 frame for the HUD

# --- Track -----------------------------------------------------------------------
LANES = 4
LANE_W = 12.0  # between neighbouring wires
SPLIT_GAP = 12.0  # how far each pair of wires moves out where a track splits 2 + 2
SPLIT_RAMP = 100.0  # over this length they part, and rejoin
SPLIT_NO_SWITCH = 0.15  # no changing between wires 1 and 2 once they are this far apart
CAR_LEN = 14.0

# --- Players and controls ---------------------------------------------------------
# Up to four people (the cabinet has two sticks and two button clusters), and
# bots on the places they leave free, up to MAX_RACERS cars in all.
HUMAN_COUNTS = (1, 2, 3, 4)
HUMANS = {1: ("p1",), 2: ("p1", "p2"), 3: ("p1", "p2", "p3"), 4: ("p1", "p2", "p3", "p4")}
MAX_RACERS = 8
BOTS = tuple(f"cpu{i}" for i in range(1, MAX_RACERS))
LEVELS = ("EASY", "TOUGH", "BRUTAL")  # see ai.py
DEFAULT_HUMANS = 1
DEFAULT_BOTS = 3
DEFAULT_LEVEL = "EASY"

# Which inputs drive which player: ("stick", pad) or ("pad", pad), where
# "pad" is the four face buttons laid out like WASD (as in Qurves). Alone,
# either pad drives; with 2, each pad is a player; with 3 or 4, the left
# pad's buttons are P3 and the right pad's P4. Every control is relative to
# the car: up and down raise and lower the speed it cruises at (CRUISE_*),
# left and right change to the wire on the car's own left or right.
CONTROLS = {
    1: {"p1": (("stick", 0), ("pad", 0), ("stick", 1), ("pad", 1))},
    2: {"p1": (("stick", 0), ("pad", 0)), "p2": (("stick", 1), ("pad", 1))},
    3: {"p1": (("stick", 0),), "p2": (("stick", 1), ("pad", 1)), "p3": (("pad", 0),)},
    4: {"p1": (("stick", 0),), "p2": (("stick", 1),), "p3": (("pad", 0),), "p4": (("pad", 1),)},
}

# The grid: people in the front row, the left pad's players on the left
# wires; bots fill the rest of the front row, then the second.
GRID_LANES = {
    1: {"p1": 1},
    2: {"p1": 1, "p2": 2},
    3: {"p1": 0, "p3": 1, "p2": 2},
    4: {"p1": 0, "p3": 1, "p4": 2, "p2": 3},
}
GRID_BEHIND = 18.0  # the front row sits this far behind the start line
GRID_ROW = 24.0  # and each row behind it this much further


@dataclass(frozen=True)
class CarStats:
    """What a car can do. Each racer (racers.py) turns its 1-5 ratings into
    one of these; CAR is the middle of every rating."""

    max_speed: float
    accel: float  # at full gas
    brake: float
    coast: float  # easing down to its cruise speed from over it (off a boost pad)
    grip: float  # lateral acceleration a corner can take before the car drifts
    mass: float = 1.0  # in bumps and pushes, the heavier car gives less
    switch_rate: float = 6.0  # wires per second while changing


CAR = CarStats(max_speed=220.0, accel=110.0, brake=320.0, coast=45.0, grip=240.0)

# Cruise control: a racer holds the speed it is set to, so the stick is
# free for changing wires. The setting is a share of its top speed (the
# slipstream raises it); up raises it, down lowers it and brakes (race.py
# _cruise).
CRUISE_START = 1.0  # at the start it sets off flat out
CRUISE_RISE = 1.0  # up raises the setting by this share of top speed a second ...
CRUISE_MIN = 0.25  # ... and down lowers it no further than this: a crawl, below every corner's limit

# What each step of a racer's 1-5 ratings is worth, around CAR at 3.
STAT_SPEED = 3.0  # top speed per step
STAT_ACCEL = 0.12  # fraction of CAR's acceleration per step
STAT_GRIP = 0.07  # fraction of CAR's grip per step
STAT_MASS = 0.15  # mass per step (1.0 at 3)
STAT_HANDLING = 1.0  # wires per second per step

# --- Corners ----------------------------------------------------------------------
# A racer's load is its lateral acceleration over its grip. Above DRIFT_LOAD
# it drifts (and scrubs off a little speed); above WARN_LOAD it flashes red
# and its spin meter fills; a full meter spins it out, nearly to a stop, and
# the pack streams past.
DRIFT_LOAD = 1.0
WARN_LOAD = 1.5
SLIP_BASE = 0.6  # spin meter per second just above WARN_LOAD
SLIP_GAIN = 2.0  # plus this much per second per unit of load above it
SLIP_RECOVER = 1.5  # per second, below WARN_LOAD
DRIFT_SCRUB = 0.35  # fraction of speed lost per second per unit of load above DRIFT_LOAD
SPIN_KEEP = 0.15  # a full spin meter spins the racer out: it keeps this much speed
SPIN_TIME = 0.7  # and is stuck this long

# --- Contact ----------------------------------------------------------------------
DRAFT_RANGE = 64.0  # close behind a car on the same wire: slipstream
DRAFT_TOP = 0.15  # top speed bonus at full slipstream
DRAFT_ACCEL = 0.6  # acceleration bonus at full slipstream
DRAFT_RISE = 3.0  # how fast the slipstream builds and fades, per second
DRAFT_HOLD = 1.0  # once full, it lasts this long after you pull out, like DRS: time to pass
BUMP_REAR_SLOW = 0.05  # running into a car from behind: down to 95% of its speed
BUMP_SIDE_SLOW = 0.10  # changing wires into a car: both lose 10%
WIGGLE_TIME = 0.35

# --- Boost pads and jumps ------------------------------------------------------------
BOOST = 0.35  # a boost pad puts you this far over your top speed
JUMP_LIFT = 0.42  # a kicker launches you upwards at this fraction of your speed
GRAVITY = 520.0
JUMP_MIN_SPEED = 60.0  # slower than this, a kicker is just a bump
LAND_KEEP = 0.97  # speed kept on landing
KICKER_LEN = 18.0  # the ramp's length along the track
KICKER_HEIGHT = 5.0

# --- Gates, items, errors ----------------------------------------------------------
# Quantum gates come and go: the race keeps the track's `dynamic_gates` of
# them out at random places, each for a while, then it fades and a new one
# appears elsewhere.
GATE_KINDS = {"SWAP": 3, "CNOT": 2}  # relative odds
GATE_LIFE = (9.0, 16.0)  # seconds a gate stays, at random between these
GATE_RESPAWN = 1.5  # seconds before the next one appears
GATE_FADE = 1.5  # a gate blinks this long before it goes
GATE_SPACING = 50.0  # never this close to another gate or a boost pad or kicker
# Item gates (ERR, ZENO) are taken by the first car through them: the race
# keeps the track's `items` of them out, and one that is taken comes back
# somewhere else.
ITEM_KINDS = {"ERR": 3, "ZENO": 2}  # relative odds
ITEM_RESPAWN = 3.0  # seconds after one is taken, a new one appears
ITEM_GATE_CLEAR = 40.0  # never this close to a gate, boost pad or kicker (along the track)
ITEM_SPACING = 60.0  # nor to another item
ITEM_AHEAD_CLEAR = 90.0  # nor appearing this close in front of a car
ITEM_POP = 0.4  # seconds an item takes to appear
MAX_BODIES = 2  # a CNOT copy is one extra life at a time
COPY_TIME = 10.0  # copies last this long, then collapse onto the leading one
# A bug leaves at the speed of the car that launched it plus a little, so it
# is never slower than its car and never wildly faster: X and Z alike.
BUG_MIN_SPEED = 120.0  # launched from a slow car, it still goes at least this
BUG_EXTRA = {"X": 55.0, "Z": 45.0}
BUG_LIFE = 5.0
BUG_HIT_KEEP = {"X": 0.7, "Z": 0.5}  # fraction of speed a car keeps when hit
ERR_HOLD = 1.0  # a new bug hovers in front of its car this long: change wires to aim it
ZENO_ARM = 1.2  # a Zeno trap blinks behind its car this long, then drops
ZENO_KEEP = 0.6  # fraction of speed a car keeps when it drives into one
ZENO_GLOW = 0.5  # and it glows cyan this long
ZENO_LIFE = 30.0
ZENO_GRACE = 2.0  # its owner can't hit it this soon after dropping it

# --- Leading, resets and the match ---------------------------------------------
# The leader scores: every second in front counts, and the first to the
# target wins. A racer off the screen for OUT_DELAY is put back in at the
# back of the pack, already moving, and passes through everything for
# RESET_GHOST so it can find its feet.
OUT_DELAY = 0.4
OUT_MARGIN = 0.03  # how far past the screen's edge (as a fraction of it) counts as off
RESET_BEHIND = 30.0  # units behind the last racer still on the screen
RESET_INSET = 0.45  # and at least this far (as a fraction of the half-screen) inside its edges
RESET_SPEED = 0.95  # it comes back at this fraction of the leader's speed ...
RESET_MIN = 0.5  # ... but at least this fraction of its own top speed
RESET_GHOST = 1.5
LEAD_MARGIN = 6.0  # a challenger takes the lead once it is this far ahead
TARGET_CHOICES = (30, 60, 90)  # seconds in the lead to win
TARGET_DEFAULT = 60
FINAL_TICKS = 5  # the last seconds before someone wins tick
COUNTDOWN = 3.0
RESULT_LOCK = 1.0  # seconds before the match result takes input
IDLE_TIMEOUT = 60.0

# --- Colours -----------------------------------------------------------------------
COLOR_BACKGROUND = (7, 9, 22)
COLOR_BOARD_DOT = (20, 25, 52)
COLOR_BED = (18, 22, 46)
COLOR_EDGE = (66, 76, 130)
COLOR_KERB = (220, 60, 70)
COLOR_KERB_ALT = (230, 230, 240)
COLOR_WIRE = (92, 116, 200)
COLOR_INK = (10, 10, 24)
COLOR_TEXT = (220, 226, 245)
COLOR_DIM = (120, 128, 170)
COLOR_PANEL = (12, 14, 32)
COLOR_FPS = (255, 211, 107)
COLOR_WARN = (255, 40, 40)
COLOR_ZENO = (90, 235, 235)
# The cabinet's left side is blue and its right side red (see AGENTS.md
# "Player colours"); the left pad's second player is green, the right's purple.
PLAYER_COLORS = {
    "p1": (60, 145, 255),  # blue
    "p2": (255, 70, 85),  # red
    "p3": (60, 230, 110),  # green
    "p4": (190, 90, 255),  # purple
}
# Bots never wear a player's colour, nor a hue leaning towards one (orange
# and pink read as P2's red, cyan and teal as P1's blue): their chips and
# labels get neutral ones. The last two are greenish, and only appear with
# at most two people racing, so they never sit next to P3's green. The
# racers themselves wear their own game's colours; a person's racer rides on
# a ring in that person's colour.
BOT_COLORS = (
    (240, 220, 60),  # yellow
    (235, 235, 245),  # white
    (130, 138, 155),  # grey
    (205, 155, 100),  # tan
    (140, 95, 60),  # brown
    (170, 225, 60),  # lime
    (150, 155, 70),  # olive
)


def color_of(player: str) -> tuple[int, int, int]:
    if player in PLAYER_COLORS:
        return PLAYER_COLORS[player]
    return BOT_COLORS[(int(player[3:]) - 1) % len(BOT_COLORS)]


def label_of(player: str) -> str:
    return player.upper()


# Gate Drop's gate and error colours, so its bugs look like themselves here.
GATE_COLORS = {"H": (250, 196, 40), "X": (232, 64, 72), "Y": (170, 82, 220), "Z": (56, 124, 236)}
CNOT_COLOR = (170, 182, 204)

# --- Input -------------------------------------------------------------------------
INPUT_CONFIG = {
    "pads": (
        {"joystick_index": 0, "hat_index": 0, "axes": (0, 1),  # (horizontal, vertical)
         # printed L X R / Y B A: X, Y, B, A sit like W, A, S, D
         "buttons": {"up": [0], "left": [3], "down": [2], "right": [1]}},
        {"joystick_index": 1, "hat_index": 0, "axes": (0, 1),
         "buttons": {"up": [0], "left": [3], "down": [2], "right": [1]}},
    ),
    "system": {
        "start_button": 9, "select_button": 8,
        "confirm_buttons": [1], "back_buttons": [2],  # printed A confirms menus, B goes back
        "keyboard_quit": "K_ESCAPE",
    },
    "axis_deadzone": 0.5,
}

# Keyboard: a dev fallback only. The cabinet loader passes --no-keyboard, so
# the keystrokes Batocera's evmapy fakes for P1's pad never reach the game.
KEYMAP = {
    ("stick", 0): {"up": ["K_w"], "left": ["K_a"], "down": ["K_s"], "right": ["K_d"]},
    ("pad", 0): {"up": ["K_t"], "left": ["K_f"], "down": ["K_g"], "right": ["K_h"]},
    ("stick", 1): {"up": ["K_i"], "left": ["K_j"], "down": ["K_k"], "right": ["K_l"]},
    ("pad", 1): {"up": ["K_UP"], "left": ["K_LEFT"], "down": ["K_DOWN"], "right": ["K_RIGHT"]},
}
KEYS_CONFIRM = ["K_RETURN", "K_1", "K_2"]
KEYS_BACK = ["K_BACKSPACE"]
KEYS_PAUSE = ["K_p"]
