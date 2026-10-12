"""Single source of truth for resolution, race rules, colours and input.

Joystick 0 = P1 (blue, top view), joystick 1 = P2 (red, bottom view). The raw button
numbers are the ones confirmed on the cabinet (see ../../../AGENTS.md): printed A = 1,
B = 2, Select = 8, Start = 9. The stick is an analog axis, never a hat: axis 0 steers,
axis 1 brakes (pulled back, positive) and drives the menus.
"""

from __future__ import annotations

# --- Display -------------------------------------------------------------------------
INTERNAL_WIDTH = 960
INTERNAL_HEIGHT = 540  # exactly x2 onto the cabinet's 1920x1080 panel
FPS = 60
SHOW_FPS_DEFAULT = False
VIEW_1P = (960, 540)
VIEW_2P = (960, 270)  # P1 on top, P2 below

# --- The race --------------------------------------------------------------------------
CARS = 6
CPU_CARS_2P = 4
CPU_CARS_1P = 5
LAPS = 3
ROWS_PER_LAP = 8
SLOTS = LAPS * ROWS_PER_LAP  # 24: one slot of the target circuit per gate row
ARCHES_MIN = 1
ARCHES_MAX = 3
ITEM_BOXES_PER_LAP = 2
LAP_SECONDS = 45.0  # about, at top speed

# --- Boosts ----------------------------------------------------------------------------
# Streak: +20% for 1.0 s on the first right gate in a row, then +8% and +0.2 s per further
# one, up to +60% for 2.0 s.
STREAK_BOOST_FIRST = 0.20
STREAK_BOOST_STEP = 0.08
STREAK_BOOST_MAX = 0.60
STREAK_TIME_FIRST = 1.0
STREAK_TIME_STEP = 0.2
STREAK_TIME_MAX = 2.0

# CIRCUIT CHECK, at the start of the final lap, over the first CHECK_SLOTS slots:
# (CHECK_SLOTS - d) / CHECK_SLOTS * CHECK_BOOST extra speed, for
# CHECK_TIME_BASE + (CHECK_SLOTS - d) * CHECK_TIME_PER_SLOT seconds.
CHECK_SLOTS = 16
CHECK_BOOST = 0.80
CHECK_TIME_BASE = 1.0
CHECK_TIME_PER_SLOT = 0.25


def streak_boost(streak: int) -> tuple[float, float]:
    """The (extra speed fraction, seconds) of a streak of this many right gates in a row."""
    if streak <= 0:
        return 0.0, 0.0
    strength = min(STREAK_BOOST_MAX, STREAK_BOOST_FIRST + (streak - 1) * STREAK_BOOST_STEP)
    seconds = min(STREAK_TIME_MAX, STREAK_TIME_FIRST + (streak - 1) * STREAK_TIME_STEP)
    return strength, seconds


def check_boost(distance: int) -> tuple[float, float]:
    """The CIRCUIT CHECK's (extra speed fraction, seconds) for a Hamming distance.

    The distance is clamped to [0, CHECK_SLOTS], so the boost is never negative.
    """
    right = CHECK_SLOTS - max(0, min(CHECK_SLOTS, distance))
    return right / CHECK_SLOTS * CHECK_BOOST, CHECK_TIME_BASE + right * CHECK_TIME_PER_SLOT


# --- Driving ---------------------------------------------------------------------------
OFFROAD_SPEED_FACTOR = 0.6  # top speed on the copper plate
TOP_SPEED = 10_000.0  # world units per second: 50 segments, so a lap of THE FRIDGE is ~45 s
# Speed changes, in world units per second per second.
ACCEL = 5_000.0  # auto-acceleration: standing to top speed in 2 s
BOOST_ACCEL = 20_000.0  # up to a boost's speed: +80% in 0.4 s
COAST_DECEL = 5_000.0  # back down to top speed when a boost ends
OFFROAD_DECEL = 12_000.0  # down to the off-road cap: top speed to 60% in 1/3 s
BRAKE = 6_000.0  # with the stick fully back
BRAKE_FLOOR = 0.4  # braking never slows the car below 40% of top speed
# Lateral rates, in road half-widths per second, at top speed. Steering scales with speed
# and the curves' outward push with speed squared, as OutRun does.
STEER_RATE = 2.0  # full stick: across the whole road in a second
CURVE_PUSH = 0.46  # outward push per unit of curve: the coax corner (4.4) just beats full stick
DRIFT = 0.3  # a brake held through a curve takes up to 30% off the push
X_LIMIT = 2.2  # the car never strays further than this from the centre line
# Bumps. CAR_WIDTH (below) is a car's whole width in road half-widths.
CAR_LENGTH = 400.0  # world units, two segments
BUMP_KNOCK = 1.2  # a side bump knocks both cars apart at this many half-widths a second
BUMP_KNOCK_DECAY = 8.0  # per second: the knock is mostly gone in a quarter of a second
BUMP_SLOW = 0.85  # a rear bump leaves the car behind at 85% of the front car's speed
BUMP_NUDGE = 0.6  # and nudges it sideways (half-widths a second), so it slides by
BUMP_COOLDOWN = 0.3  # seconds before the same two cars can bump (and cue it) again
# The starting grid: two lanes, the rows of cars a little apart behind the line.
GRID_LANES = (-0.4, 0.4)
GRID_FIRST = 300.0  # the front row's distance behind the line
GRID_GAP = 1000.0  # between the rows; a CPU in the right lane is half of it further back

# Pace: a speed multiplier on top of everything else, from the controls. Humans always drive
# at 1.0; the CPU racers use it for their skill and the rubber-banding.
PACE_LIMITS = (0.9, 1.1)

# --- Items -----------------------------------------------------------------------------------
ITEMS = ("SPLIT", "QEC")
BOX_REACH = 0.2  # a car whose centre is within this of a box's offset drives through it
BOX_RESPAWN = 3.0  # seconds before a taken box is back (the same box on every lap)
SPLIT_ROWS = 2  # the clone lasts for this many gate rows
# The odds of a box by place (1st to 6th), as weights of (SPLIT, QEC, nothing). The back gets
# more of both items and the front more empty boxes; last place always gets something.
ITEM_ODDS = (
    (20, 30, 50),
    (30, 30, 40),
    (35, 35, 30),
    (45, 35, 20),
    (55, 35, 10),
    (60, 40, 0),
)

# --- The CPU racers --------------------------------------------------------------------------
BOT_SKILL_BEST = 0.85  # the CPU skills spread evenly from the best down to the worst
BOT_SKILL_WORST = 0.60
BOT_LOOK = 600.0  # how far ahead on the racing line a bot steers for (world units)
BOT_ROW_LEAD = 1.5  # seconds before a gate row a bot lines up for its arch
BOT_OFFSET_MAX = 0.3  # each bot keeps its own offset from the racing line, up to this
BOT_GOAL_MAX = 0.9  # and never aims further out than this (the road is -1 to 1)
BOT_GAP_CLEAR = 0.08  # aiming for a gap, it keeps this far outside every arch
BOT_DECOY = 0.6  # a bot that misses aims for a decoy this often (when there is one)
BOT_AVOID_TIME = 0.8  # a car it would reach within this many seconds, in its path, is passed
BOT_YIELD_TIME = 0.5  # and it makes way for a faster car that would hit it within this
BOT_AVOID_CLEAR = 0.38  # passing, it aims this far beside the car (CAR_WIDTH and a margin)
BOT_BRAKE_SKILL = 0.7  # bots below this skill brake into sharp curves; the rest never brake
BOT_BRAKE = 0.5  # how hard
BOT_BRAKE_LOOK = 800.0  # how far ahead they look for the curve
BOT_SPLIT_LEAD = 0.6  # seconds before a row with decoys a bot uses its SPLIT
BOT_PACE_WORST = 0.99  # the pace of the worst skill; the best drives at 1.0
BOT_RUBBER_FIRST = 0.97  # rubber-banding: the pace multiplier in 1st place ...
BOT_RUBBER_LAST = 1.03  # ... and in last, in a straight line between

# --- The world and the camera (the look file's numbers) ---------------------------------
# Lateral positions (car x, arch offsets, roadside sprites) are in road half-widths: -1 to 1
# is the road. z is distance along the track in world units.
SEG = 200.0  # world units per road segment
ROAD_HALF_WIDTH = 1500.0  # world units
RUMBLE = 1.12  # the rumble strip's outer edge, in road half-widths
CAMERA_HEIGHT = 1000.0
CAMERA_DEPTH = 0.84  # 1 / tan(half the field of view)
CAR_AHEAD = 760.0  # camera to its own car: the car's wheels then sit 10 px above the bottom
DRAW_SEGMENTS = 120  # how far ahead the road is projected (2.4 s at top speed)
HORIZON = 112 / 270  # the horizon's height, as a fraction of a view's height
PARALLAX_TILES = 3  # how many background widths scroll past in one full turn (a lap)

# --- Gate rows -----------------------------------------------------------------------------
ARCH_HALF_WIDTH = 0.22  # an arch's outer radius: a car within it of the offset goes through
ARCH_OFFSET_MAX = 0.8  # arch centres lie in [-0.8, 0.8]
ARCH_MIN_GAP = 0.04  # the least space between two arches of a row
SHARP_CURVE = 3.0  # |curve| above this is a sharp curve: no gate row there

# --- Sprites -------------------------------------------------------------------------------
# Every sprite is drawn once at start-up, at SPRITE_SIZES sizes spaced evenly in log between
# these scales (pixels per road half-width at the sprite's distance), and the nearest is
# blitted. Nearer than the largest size (just behind the camera's own car) is not drawn.
SPRITE_SIZES = 24
SPRITE_SCALE_MIN = 20.0
SPRITE_SCALE_MAX = 1000.0
CAR_WIDTH = 0.32  # in road half-widths, as the look's own car beside its road

# --- Flow ------------------------------------------------------------------------------
ATTRACT_DELAY = 3.0  # untouched seconds on the title before the CPU racers play
ATTRACT_SKILL = 0.725  # the bots driving P1's and P2's cars in the attract race
IDLE_TIMEOUT = 60.0  # untouched seconds anywhere but the title: back to the title, 1 PLAYER
COUNTDOWN = 3.0  # 3, 2, 1 a second each, then GO
GO_TIME = 0.8  # GO! stays up this long into the race
AUTOPILOT_SKILL = 0.725  # a player's car after the line is driven on by a bot
FINISH_GRACE = 40.0  # 2P: once one player has finished, the other has this long to
FINISH_DELAY = 3.0  # the finish banner, before the result screen
RESULT_LOCK = 1.0  # the result screen ignores the buttons this long (a mashed A)
CHECK_BANNER = 4.0  # the CIRCUIT CHECK banner's seconds
LAP_BANNER = 1.6
PAUSE_ITEMS = ("RESUME", "QUIT TO TITLE")

# --- Colours ---------------------------------------------------------------------------
# The one source of the players' colours (the look's): P1 blue on top, P2 red below.
PLAYER_COLORS = {"p1": (80, 170, 255), "p2": (255, 80, 90)}
# The CPU racers, best first: never a player's hue (P1's blue, cyan and teal; P2's red,
# orange and pink) and clear of the gates' (H gold, X red, Z blue, Y purple). Only greens are
# left as hues, so two greens far apart, and three greys apart in brightness.
CPU_COLORS = {
    "green": (30, 180, 90),  # emerald
    "white": (236, 238, 246),
    "lime": (150, 220, 40),
    "steel": (120, 124, 138),
    "black": (60, 60, 72),  # only in 1P races (the fifth CPU); lighter than the road
}
CAR_COLORS = {**PLAYER_COLORS, **CPU_COLORS}
GATE_COLORS = {  # shared with the other games
    "H": (248, 192, 40),
    "X": (232, 64, 72),
    "Z": (56, 120, 232),
    "Y": (168, 80, 216),
}

# --- Input -----------------------------------------------------------------------------
INPUT_CONFIG = {
    "p1": {"joystick_index": 0, "hat_index": 0, "axes": (0, 1)},
    "p2": {"joystick_index": 1, "hat_index": 0, "axes": (0, 1)},
    "system": {
        "a_button": 1, "back_button": 2, "start_button": 9, "select_button": 8,
        "keyboard_quit": "K_ESCAPE",
    },
    "axis_deadzone": 0.25,  # analog stick
    "step_threshold": 0.5,  # a stick push past this counts as a step in the menus
}
REPEAT_DELAY = 0.22  # auto-repeat for stick steps in menus
REPEAT_INTERVAL = 0.11

# Keyboard: a dev fallback only. The cabinet loader passes --no-keyboard, so the keystrokes
# Batocera's evmapy fakes for P1's pad never reach the game.
KEYMAP = {
    # ESDF, not WASD: P1's dev keys must avoid the pad's own letters l, x, r, b, y, a.
    "p1": {"left": ["K_s"], "right": ["K_f"], "up": ["K_e"], "down": ["K_d"], "a": ["K_q"],
           "back": ["K_w"], "start": ["K_1"], "select": ["K_3"]},
    "p2": {"left": ["K_LEFT"], "right": ["K_RIGHT"], "up": ["K_UP"], "down": ["K_DOWN"],
           "a": ["K_PERIOD"], "back": ["K_COMMA"], "start": ["K_2"], "select": ["K_4"]},
}

# --- Sound -----------------------------------------------------------------------------
MASTER_VOLUME = 0.8
MUSIC_VOLUME = 0.35
