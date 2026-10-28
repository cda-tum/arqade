"""Single source of truth for resolution, race rules, colours and input.

Joystick 0 = P1 (blue, left view), joystick 1 = P2 (red, right view). The raw button
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
VIEW_2P = (480, 540)  # side by side: P1 on the left, P2 on the right, a thin divider between
# A 2P view projects the road as if it were VIEW_2P_SPREAD * 2 wide and shows its middle 480:
# at half the width the cars and the road would be squeezed to half their size.
VIEW_2P_SPREAD = 320

# --- The race --------------------------------------------------------------------------
CARS = 6  # the most cars in a race: people (1 or 2) and bots together
MAX_PLAYERS = 2
LEVELS = ("EASY", "TOUGH", "BRUTAL")  # the bots' level, one for all of them (ai.SKILLS)
DEFAULT_LEVEL = "EASY"  # the title's, as a visitor finds it: one they can beat
LAPS = 3
ROWS_PER_LAP = 8
GATE_LAPS = 2  # gate rows stand on laps 1 and 2 only: the final lap is a gate-free sprint
SLOTS = GATE_LAPS * ROWS_PER_LAP  # 16: one slot of the target circuit per gate row
ARCHES_MIN = 1
ARCHES_MAX = 3
ITEM_BOXES_PER_LAP = 2
LAP_SECONDS = 40.0  # about, at top speed

# --- Boosts ----------------------------------------------------------------------------
# Streak: +30% for 1.5 s on the first right gate in a row, then +10% and +0.25 s per further
# one, up to +70% for 2.5 s (the fifth in a row).
STREAK_BOOST_FIRST = 0.30
STREAK_BOOST_STEP = 0.10
STREAK_BOOST_MAX = 0.70
STREAK_TIME_FIRST = 1.5
STREAK_TIME_STEP = 0.25
STREAK_TIME_MAX = 2.5

# CIRCUIT CHECK, as a car crosses into the final lap, over all CHECK_SLOTS slots, with d
# of them wrong: ((CHECK_SLOTS - d) / CHECK_SLOTS) ** 2 * CHECK_BOOST extra speed, for
# CHECK_TIME_BASE + (CHECK_SLOTS - d) * CHECK_TIME_PER_SLOT seconds: the LIGHT SPEED! warp.
# A perfect circuit is +100% for 6 s, 14/16 +77% for 5.5 s, 12/16 +56% for 5 s, 8/16 +25%
# for 4 s. Squared, so that accuracy pays: the bots get the same check by their own
# circuits, and a better circuit's warp passes a bot up to ~2 s ahead.
CHECK_SLOTS = SLOTS
CHECK_BOOST = 1.00
CHECK_TIME_BASE = 2.0
CHECK_TIME_PER_SLOT = 0.25
# The check's boost starts this long after the crossing: meanwhile that player's view is
# frozen on the comparison panel, and the car drives straight on at its speed.
CHECK_FREEZE = 1.0
# A check whose boost is under this (3/16 right or fewer: +3.5% at most) is NO BOOST: no warp,
# no LIGHT SPEED! show, and the boost is not given (it would be too small to feel).
CHECK_SHOW_MIN = 0.05


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
    return (right / CHECK_SLOTS) ** 2 * CHECK_BOOST, CHECK_TIME_BASE + right * CHECK_TIME_PER_SLOT


# --- Driving ---------------------------------------------------------------------------
OFFROAD_SPEED_FACTOR = 0.6  # top speed on the copper plate
TOP_SPEED = 11_200.0  # world units per second: 56 segments, so a lap of THE FRIDGE is ~40 s
# Speed changes, in world units per second per second, in proportion to the top speed.
ACCEL = TOP_SPEED / 2  # auto-acceleration: standing to top speed in 2 s
BOOST_ACCEL = TOP_SPEED * 2  # up to a boost's speed: +80% in 0.4 s
COAST_DECEL = TOP_SPEED / 2  # back down to top speed when a boost ends
OFFROAD_DECEL = TOP_SPEED * 1.2  # down to the off-road cap: top speed to 60% in 1/3 s
BRAKE = TOP_SPEED * 0.6  # with the stick fully back
BRAKE_FLOOR = 0.4  # braking never slows the car below 40% of top speed
# Lateral rates, in road half-widths per second, at top speed. Steering scales with speed
# and the curves' outward push with speed squared, as OutRun does.
STEER_RATE = 2.0  # full stick: across the whole road in a second
CURVE_PUSH = 0.46  # outward push per unit of curve: the coax corner (4.4) just beats full stick
BRAKE_PUSH = 0.3  # a brake held through a curve takes up to 30% off the push
# Drifting: the stick pulled back *and* steered (pulled straight back is the brake). It starts
# and holds with |steer| >= DRIFT_STEER and any pull past the stick's deadzone (the brake's
# own: brake > DRIFT_PULL), from DRIFT_MIN_SPEED of the top speed. A drifting car runs at
# DRIFT_SPEED of the speed it would have and the curve pushes it out with DRIFT_PUSH of the
# push, so it turns tighter. DRIFT_LEVELS seconds of drifting into a bend charge levels 1
# and 2; letting
# go gives that level's mini-turbo (DRIFT_TURBOS, through give_boost). An uncharged drift
# ends with nothing, and so does one ended by slowing below DRIFT_END_SPEED, a bump or a hit.
DRIFT_STEER = 0.4
DRIFT_PULL = 0.0
DRIFT_MIN_SPEED = 0.6
DRIFT_END_SPEED = 0.5
DRIFT_SPEED = 0.92
DRIFT_PUSH = 0.5
DRIFT_LEVELS = (0.7, 1.5)
# The charge only grows while the road bends the drift's way by more than this (|curve|):
# on a straight, or drifting against the bend, a drift slides but its charge holds, so
# weaving on a straight earns nothing (THE FRIDGE's sweepers bend 2.0-2.4, the s-bend 3.2,
# the coax corner 4.4).
DRIFT_CHARGE_CURVE = 1.0
DRIFT_TURBOS = ((0.25, 0.6), (0.40, 1.0))  # (strength, seconds) of levels 1 and 2
DRIFT_ANGLE = 0.35  # radians: the slide's angle in a drift (the renderer's tilt)
DRIFT_ANGLE_RATE = 2.5  # radians a second toward it, and back to straight after
TURBO_FLASH = 0.3  # seconds of the mini-turbo's flash (the renderer's)
# Hits. A spin-out (a bit-flip mine, a MEASURE) leaves SPIN_SPEED of the car's speed (of
# the top speed at most: a boost's share is lost) and the stick does nothing for SPIN_TIME; a static cloud caps the speed at CLOUD_CAP of the top
# speed for CLOUD_TIME (and takes the boosts).
SPIN_SPEED = 0.4
SPIN_TIME = 0.8
CLOUD_CAP = 0.7
CLOUD_TIME = 1.0
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
GRID_GAP = 1000.0  # between the rows; a car in the right lane is half of it further back

# Pace: a speed multiplier on top of everything else, from the controls. Humans always drive
# at 1.0; the bots use it for their level and the rubber-banding (ai.Skill).
PACE_LIMITS = (0.9, 1.1)

# --- Items -----------------------------------------------------------------------------------
ITEMS = ("SPLIT", "QEC", "MEASURE", "TUNNEL", "DECOHERENCE")
GATE_ITEMS = ("SPLIT", "QEC")  # about gates: never from a box once a car's rows are over
BOX_REACH = 0.2  # a car whose centre is within this of a box's offset drives through it
BOX_RESPAWN = 3.0  # seconds before a taken box is back (the same box on every lap)
SPLIT_ROWS = 2  # the clone lasts for this many gate rows
# The odds of a box by place (1st to 6th), as weights of ITEMS. A box always gives one. The
# back gets more MEASURE, TUNNEL and SPLIT, the front more DECOHERENCE and QEC; the leader
# gets no MEASURE (there is nobody ahead to measure). Past a car's last row SPLIT and QEC are
# left out and the rest share the odds.
#            SPLIT QEC MEASURE TUNNEL DECOHERENCE
ITEM_ODDS = (
    (10, 35, 0, 10, 45),
    (15, 30, 15, 15, 25),
    (20, 25, 20, 17, 18),
    (25, 20, 22, 20, 13),
    (28, 15, 25, 24, 8),
    (30, 10, 28, 27, 5),
)
MEASURE_RANGE = 30_000.0  # a MEASURE homes on the nearest car ahead within this (world units)
MEASURE_FLIGHT = 0.4  # seconds the shot flies before it hits (and collapses) that car
TUNNEL_TIME = 3.0  # through cars, off-road at full speed, immune to hazards, clouds, MEASURE
DECO_TIME = 10.0  # a DECOHERENCE cloud stays this long, or until a car drives through it
DECO_BEHIND = 600.0  # dropped this far behind the car (world units): just behind its tail
DECO_SIZE = 0.3  # its radius, in road half-widths (a storm cloud's size)
BLIND_TIME = 1.5  # laps 1-2: driving through one blanks the NEXT GATE badge and marker

# --- The noise storm (the final lap) -----------------------------------------------------------
# Each racer meets its own decoherence hazards on the final lap, set by its CIRCUIT CHECK:
# STORM_BASE + STORM_PER_WRONG per wrong gate, at most STORM_MAX. They are spread from
# STORM_START seconds (at top speed) after the line, past the check's freeze, to STORM_END
# seconds before the finish, and always leave a clear line STORM_GAP wide (more than a car)
# that half stick can follow.
STORM_BASE = 4
STORM_PER_WRONG = 2
STORM_MAX = 24
STORM_START = 3.0
STORM_END = 1.0
STORM_GAP = 0.52  # CAR_WIDTH (0.32) and 0.1 to spare either side
STORM_LANE_MAX = 0.6  # the clear line's centre stays within this of the centre line
STORM_LANE_STEER = 0.5  # and never needs more than this much stick to follow
STORM_PAIRS_FROM = 8  # past this many hazards, some come in pairs, one either side of the line
STORM_MINES = 0.4  # the share of bit-flip mines; the rest are static clouds
HAZARD_SIZE = {"cloud": 0.28, "mine": 0.1}  # their radii (road half-widths): wide, and small
HAZARD_X_MAX = 0.9  # a hazard's centre stays on the road, within this

# --- The bots (ai.py; each level's own numbers are its Skill there) -----------------------------
BOT_LOOK = 600.0  # how far ahead on the racing line a bot steers for (world units)
BOT_ROW_LEAD = 1.5  # seconds before a gate row a bot lines up for its arch
BOT_OFFSET_MAX = 0.3  # each bot keeps its own offset from the racing line, up to this
BOT_GOAL_MAX = 0.9  # and never aims further out than this (the road is -1 to 1)
BOT_WEAVE_RATE = 0.9  # radians a second: a weaving bot's slow sway either side of its line
BOT_GAP_CLEAR = 0.08  # aiming for a gap, it keeps this far outside every arch
BOT_DECOY = 0.6  # a bot that misses aims for a decoy this often (when there is one)
BOT_AVOID_TIME = 0.8  # a car it would reach within this many seconds, in its path, is passed
BOT_YIELD_TIME = 0.5  # and it makes way for a faster car that would hit it within this
BOT_AVOID_CLEAR = 0.38  # passing, it aims this far beside the car (CAR_WIDTH and a margin)
BOT_BRAKE_LOOK = 3000.0  # how far ahead a braking bot looks for a sharp curve, braking before it
BOT_SPLIT_LEAD = 0.6  # seconds before a row with decoys a bot uses its SPLIT
BOT_DRIFT_CURVE = 2.5  # a bot drifts (by its level) through curves sharper than this
BOT_HAZARD_LOOK = 1.2  # seconds ahead a bot looks for hazards and clouds to steer round
BOT_HAZARD_LOOK_INFORMED = 1.5  # and a BRUTAL one
BOT_HAZARD_CLEAR = 0.06  # steering round one, it keeps this far outside its reach
BOT_HAZARD_WAVE = 1600.0  # and round any others within this of it (a staggered pair's half)
BOT_TUNNEL_LOOK = 0.5  # a hazard or cloud still in its path this close: TUNNEL
BOT_TRAFFIC = 2 * 400.0  # TUNNEL in traffic: a car this close ahead or alongside (CAR_LENGTH)
BOT_DECO_BEHIND = 8000.0  # DECOHERENCE when a car is this close behind it, in line
BOT_DECO_LINE = 0.6  # in line: within this sideways
BOT_BLIND_SKILL = 0.5  # a bot picking its arch while blind does it at this times its aim
BOT_FUMBLE = 0.8  # seconds after the pickup a bot that fumbles an item uses it, wherever

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
# A bump or a MEASURE hit between two bots sounds for a person who can see it: the bot is
# within the person's draw distance ahead, or a few car lengths behind (match.Match._seen).
HEAR_AHEAD = DRAW_SEGMENTS * SEG
HEAR_BEHIND = 3 * CAR_LENGTH

# --- Gate rows -----------------------------------------------------------------------------
ARCH_HALF_WIDTH = 0.22  # an arch's outer radius: a car within it of the offset goes through
# Decoys are drawn smaller (and dimmer), and only what is drawn counts: a car within
# DECOY_HALF_WIDTH of a decoy's centre goes through it. Rows are still spaced for full arches.
DECOY_HALF_WIDTH = 0.8 * ARCH_HALF_WIDTH
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
ATTRACT_DELAY = 3.0  # untouched seconds on the title before the attract race plays
# untouched seconds on the title before its rows go back to the defaults: long enough to read
# the title (the attract race starting does not touch them), short of a new visitor arriving
ATTRACT_RESET = 30.0
ATTRACT_LEVEL = "TOUGH"  # the attract race behind the title: bots only
ATTRACT_BOTS = 5  # its cars (the bots' five colours); the two split views follow two of them
IDLE_TIMEOUT = 60.0  # untouched seconds anywhere but the title: back to the title, its rows reset
COUNTDOWN = 3.0  # 3, 2, 1 a second each, then GO
GO_TIME = 0.8  # GO! stays up this long into the race
AUTOPILOT_LEVEL = "TOUGH"  # a player's car after the line is driven on by the AI
FINISH_GRACE = 40.0  # 2P: once one player has finished, the other has this long to
FINISH_DELAY = 3.0  # the finish banner, before the result screen
RESULT_LOCK = 1.0  # the result screen ignores the buttons this long (a mashed A)
LAP_BANNER = 1.6
FLASH_TIME = 0.8  # RIGHT GATE +BOOST / WRONG GATE / MISSED, near the car
TIP_TIME = 2.5  # PRESS A TO USE SPLIT: on the first pickup of each item, per player

# --- The feel of speed (the renderer's only: nothing here changes the race) ------------
# The field of view widens with speed above the top speed: the projection constant is
# divided by 1 + FOV_BOOST * (speed / TOP_SPEED - 1), and the camera moves in towards its
# car by the same factor (a dolly zoom), so the car stays put while the world stretches.
FOV_BOOST = 0.35
FOV_WARP = 0.15  # and by this much more at the start of the LIGHT SPEED! warp, fading out
FOV_MAX = 1.45
SPEED_LINES_AT = 0.97  # speed lines from this fraction of the top speed
SHAKE = 7.0  # the camera's height jitter (world units) at top speed ...
SHAKE_BOOST = 14.0  # ... and at +100%
LIGHT_SPEED_TEXT = 1.3  # seconds the LIGHT SPEED! title stays up
PAUSE_ITEMS = ("RESUME", "QUIT TO TITLE")
TITLE_ITEMS = ("PLAYERS", "BOTS", "LEVEL", "QUIT")  # the title's rows; QUIT exits the game
HOWTO_GUARD = 0.3  # the HOW TO PLAY card ignores the buttons this long (the A that chose)
REVEAL_TIME = 0.9  # a box's item pops up over the car this long
FULL_TIME = 1.0  # ITEM FULL flashes in the slot this long, on a box hit with an item held
FINAL_BANNER = 2.4  # FINAL LAP / STORM AHEAD stays up this long after the check's freeze
GANTRY_LIGHTS = 5  # the start lights: red one by one in the countdown, all green at GO

# --- Colours ---------------------------------------------------------------------------
# The one source of the players' colours (the look's): P1 blue on the left, P2 red on the right.
PLAYER_COLORS = {"p1": (80, 170, 255), "p2": (255, 80, 90)}
# The bots' colours, CPU1 first (a race with fewer bots uses the first ones): neutral only,
# never a player's hue nor one leaning towards it (P1-P4 are blue, red, green and purple;
# cyan, teal, orange and pink lean), so greys and pale warm tones, apart in brightness, and
# the pale yellow far paler than the H gate's gold. The graphite only comes with a fifth bot.
CPU_COLORS = {
    "white": (236, 238, 246),
    "tan": (176, 148, 106),
    "silver": (150, 154, 166),
    "cream": (238, 228, 150),
    "graphite": (72, 72, 76),  # lighter than the road, and no blue in it
}
CPU_IDS = tuple(f"cpu{i + 1}" for i in range(CARS - 1))  # their car ids; labels CPU1, CPU2 ...
CAR_COLORS = {**PLAYER_COLORS, **CPU_COLORS}
GATE_COLORS = {  # shared with the other games
    "H": (248, 192, 40),
    "X": (232, 64, 72),
    "Z": (56, 120, 232),
    "Y": (168, 80, 216),
}

# --- Input -----------------------------------------------------------------------------
# Raw button numbers and the keyboard layout live in arqade_common.input (P1 is the first
# pad, P2 the second; axis 0 steers and axis 1 pulled back brakes). The cabinet loader
# passes --no-keyboard, so the keystrokes Batocera's evmapy fakes for P1's pad never reach
# the game.
AXIS_DEADZONE = 0.25  # analog stick
STEP_THRESHOLD = 0.5  # a stick push past this counts as a step in the menus
REPEAT_DELAY = 0.22  # auto-repeat for stick steps in menus
REPEAT_INTERVAL = 0.11

# --- Sound -----------------------------------------------------------------------------
MASTER_VOLUME = 0.8
MUSIC_VOLUME = 0.35
