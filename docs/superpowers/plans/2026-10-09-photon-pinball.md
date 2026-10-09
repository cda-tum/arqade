# Photon Pinball Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: use superpowers:subagent-driven-development
> (recommended) or superpowers:executing-plans to implement this plan task by task.

**Goal:** build Photon Pinball (`photon-pinball/`), a versus pinball game whose ramps feed a
shared Mach–Zehnder interferometer. The game is specified in
`docs/superpowers/specs/2026-10-09-photon-pinball-design.md`, and its look is
`docs/superpowers/specs/2026-10-09-photon-pinball-look.py`.

**Architecture:**
- Pure, tested rules: `bridge.py` (the interferometer), `physics.py` (ball, colliders,
  flippers), `table.py` (one table's layout, mirrored for P2) and `match.py` (lives, score,
  clock, states, the CPU).
- Drawing in two parts: `art.py` draws the static art once and caches the sprites, and
  `render.py` composes each frame.
- `main.py` and `input.py` follow Planck Time's and Gate Drop's patterns.

**Tech stack:** Python 3.11, pygame 2.5.2, uv, pytest. Run commands from `photon-pinball/`.

## Global constraints

- `requires-python = ">=3.11,<3.12"` and `pygame==2.5.2`. There are no other runtime
  dependencies, so no numpy.
- **Internal resolution:** 960x540, scaled exactly 2x by `pygame.SCALED` fullscreen.
- **Art:** smooth and anti-aliased (drawn at 2x, then smoothscaled), **not pixel art**.
- **Cabinet conventions** (`../AGENTS.md`):
  - raw buttons A = 1, B = 2, Start = 9, Select = 8;
  - the stick is axis 0/1, deadzone 0.25, read from the axis and never the hat;
  - Start + Select quits, and Start pauses with RESUME and QUIT TO TITLE;
  - 60 s idle returns to the title;
  - P1 is blue on the left, P2 red on the right;
  - the loader passes `--fullscreen --no-keyboard`, and P1's dev keys avoid `l x r b y a`;
  - `--input-test` is available.
- **The shared launcher's contract:**
  - `photon_pinball.main.main(argv)` accepts `--fullscreen`, `--window-size`,
    `--no-keyboard` and `--fps`;
  - input comes through `pygame.event.get()` and `pygame.joystick.Joystick(i)`.
- **Line endings:** LF.
- **Fonts:**
  - Bundle `DejaVuSansCondensed-Bold.ttf`, with its licence (the Bitstream Vera/DejaVu
    licence), and Press Start 2P with `OFL.txt`, which can be copied from `gate-drop`.
- **Physics:**
  - fixed step 1/240 s, design pixels;
  - ball radius 9, gravity about 900 px/s² down, speed cap about 1,400 px/s.
- **Bridge:**
  - phases only 0 or π;
  - BS = (1/√2)[[1, i], [i, 1]];
  - timing: ramp 0.7 s, BS1 to plates 0.35 s, plates to BS2 0.5 s, drop 0.6 s.
- **Commits:**
  - gitmoji style, ending with `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`;
  - stage explicit paths only, since another session may commit on `main`.
- **Done means:**
  - `uv run pytest -q` passes, with pristine output;
  - `uvx --from 'ruff==0.15.22' ruff check src tests tools` is clean.

---

### Task 1: the scaffold and the bridge

**Files:**
- Create `photon-pinball/`, containing:
  - `pyproject.toml`, modelled on gate-drop's (name `photon-pinball`, the same pins and dev
    group);
  - `.python-version`;
  - `.gitignore`.
- Create `src/photon_pinball/`, containing:
  - `__init__.py` and `__main__.py`;
  - `config.py`: resolution, FPS, the physics constants, the bridge timings, the scoring
    table, `INPUT_CONFIG` copied from Planck Time's shape (raw buttons, axis indices,
    deadzone, P1 keys `e s d f` + `q`, P2 arrows + `.`), and the idle timeout;
  - `bridge.py`;
  - `assets/fonts/`.
- Create `tests/test_bridge.py` and `tests/test_config.py`.

**`bridge.py` interface:**

```python
LEFT, RIGHT = 0, 1                       # input ports: P1's ramp, P2's ramp; output ports: P1's table, P2's table

def output_intensities(port: int, phi1: float, phi2: float) -> tuple[float, float]:
    """(to P1's table, to P2's table) for a photon entering BS1 from `port`. Exact complex
    amplitudes: from P1's port (left), the BS1 reflection goes to the left arm (plate phi1)
    and the transmission to the right arm (plate phi2); at BS2 the left arm's transmission
    goes to P2's table and its reflection to P1's (mirrored for the right arm and for P2's
    port). t = 1/sqrt2, r = i/sqrt2."""

@dataclass
class Photon:
    owner: str                # "p1" / "p2"
    t: float = 0.0            # seconds since it entered BS1
    phases: dict[int, float]  # the phase each half took at its plate (filled as they pass)

class Bridge:
    def __init__(self) -> None: ...      # phi = {"p1": 0.0, "p2": 0.0}; photons = []
    def flip(self, player: str) -> None  # toggles that player's plate between 0 and pi
    def launch(self, owner: str) -> None # a photon enters BS1 now
    def update(self, dt: float) -> list[tuple[str, str]]
        # advances every photon; a half passing its plate (t crosses BS_TO_PLATE) locks that
        # plate's current phase; a photon reaching BS2 (t >= BS_TO_PLATE + PLATE_TO_BS2) is
        # resolved with output_intensities (exactly 0/1, assert it) and removed; returns
        # [(owner, destination table "p1"/"p2")] for photons that resolved this step. The
        # drop ride is the caller's (match) business.
```

**Tests:**
- the full truth table, every port × phi1 × phi2 in {0, π}: Δ = 0 crosses, Δ = π returns;
- intensities sum to 1;
- intensities are exactly 0/1 within 1e-12;
- a flip before a photon reaches the plates changes its result, and a flip after the plates
  doesn't;
- two photons in flight resolve independently;
- `launch` then `update` in many small steps resolves exactly once.

**Commit:** `feat: :sparkles: Photon Pinball: the scaffold and the interferometer bridge`.

### Task 2: the physics engine

**Files:** create `src/photon_pinball/physics.py` and `tests/test_physics.py`.

**Interface (pure, no pygame):**

```python
Vec = tuple[float, float]

@dataclass
class Ball:
    pos: Vec; vel: Vec; r: float = BALL_R; id: int = 0

@dataclass
class Segment:            # a wall: a, b, restitution, kick (0 = passive; > 0 adds speed along the normal, slingshots)
@dataclass
class Circle:             # a post or bumper: c, r, restitution, kick
@dataclass
class Flipper:            # pivot, length, r0 (pivot radius), r1 (tip radius), rest angle, up angle,
                          # side (+1 left flipper, -1 right), angle, ang_vel; held: bool
    def update(self, dt) -> None          # rises at FLIPPER_UP_SPEED while held, falls back under a spring
@dataclass
class Sensor:             # a segment or rect the ball passes through; name; condition (callable on Ball) -> fires an event

class World:
    def __init__(self, segments, circles, flippers, sensors) -> None
    def add_ball(self, ball) / remove_ball(id)
    def step(self, dt: float) -> list[tuple[str, int]]
        # one fixed 1/240 s step: gravity, the speed cap, move, then collide each ball with
        # segments, circles, flippers (capsule: closest point on the pivot-tip segment,
        # radius lerped r0->r1; the contact's surface velocity = ang_vel x lever is added
        # before reflecting), other balls (equal masses); separate by penetration first; then
        # sensor events [(sensor name, ball id)], and "hit:<name>" events for bumpers and
        # targets that score.
```

The collision response is the same for every collider:
- reflect the normal component with restitution (default 0.5) and keep the tangential one;
- if the collider has a kick, set the normal speed to at least `kick`.

**Tests:**
- a resting ball on a raised, rising flipper leaves upward at > 600 px/s;
- a ball dropped on a wall settles and never passes through it;
- swept no-tunnelling: a ball fired at 1,400 px/s at a segment from 200 random angles always
  ends on the near side;
- a bumper returns the ball at ≥ its kick;
- two balls exchange velocity in a head-on collision;
- a sensor fires once per pass;
- a flipper released falls back to rest;
- energy doesn't blow up: one ball bouncing in a closed box for 60 s keeps speed ≤ the cap.

**Commit:** `feat: :sparkles: Photon Pinball: the pinball physics engine`.

### Task 3: the table layout

**Files:** create `src/photon_pinball/table.py` and `tests/test_table.py`.

- **`build_table(side: str) -> TableLayout`** returns one table's colliders, sensors, flippers
  and named points, mirrored for `"p2"`.
  - **Coordinates:** use the look reference's `T(side, x, y)` coordinates: `TX`, `TY = 70`,
    `TW = 322`, `TH = 462`.
  - **Walls:** the arched outer wall comes from `cabinet_shape(side, 9)` in the look file.
  - **Pieces placed as in the look file:**
    - the plunger lane wall;
    - the top lane guides;
    - three bumpers, as circles with a kick;
    - slingshots (the triangles' inner faces kick, the rest are passive);
    - inlane guides;
    - two flippers;
    - the φ target, a segment that scores with an event;
    - the ramp mouth, a sensor that fires only when `vel.y < -RAMP_MIN_SPEED`;
    - the drain, a sensor below the flippers;
    - the rollover lanes, sensors;
    - the plunger's launch point;
    - the drop entry point and velocity, where a ball from the bridge lands.
- **`TableLayout` also exposes, for the art:** the bumper centres, the slingshot triangles,
  the flipper pivots and tips, the target rect, the mouth rect and the insert positions. The
  physics and the drawing then share one source of truth.

**Tests (simulation with `physics.World`):**
- the outer walls are closed: 500 random launches over 30 s each never leave the table's
  polygon;
- a ball launched by the plunger at full power reaches the upper playfield;
- a well-timed flip from the left flipper can reach the ramp mouth, found by a small search
  over flip times;
- a ball left alone ends in the drain within 15 s;
- the φ target can be hit from a flipper;
- the P2 table is the exact mirror of P1's.

**Commit:** `feat: :sparkles: Photon Pinball: the table layout`.

### Task 4: the match and the CPU player

**Files:** create `src/photon_pinball/match.py`, `src/photon_pinball/bot.py`,
`tests/test_match.py` and `tests/test_bot.py`.

**`Match` (pure)** owns:
- the states: TITLE (1P/2P choice, attract demo after 3 s), PLAY, PAUSED, RESULT;
- the two worlds, one per table, and the `Bridge`;
- lives, scores, the 2:00 clock and the bridge's ride timers (the ramp up, the drop down).

**`update(dt, inputs) -> events`** runs four 1/240 s physics steps per 60 Hz frame.

**The rules come from the spec's "The match" and "Scoring" sections:**
- **Ramp:** the mouth sensor removes the ball, and after 0.7 s it is `bridge.launch(owner)`.
- **Sending:** the sender gets a fresh ball on their plunger at once, with no life lost.
- **Landing:** the bridge's resolution, after the 0.6 s drop, adds a ball at the destination
  table's drop entry. A cross scores the sender 5,000; a return scores 2,500 to the player
  whose plate made Δ = π.
- **Draining:** a drain removes the ball and costs that table's player a life. If no ball is
  left on that table and lives remain, a new ball is served.
- **Plunger:** the stick down charges it, release launches, and an untouched ball launches
  itself after 2 s.
- **Scoring:** the φ target calls `bridge.flip(player)` and scores 500. The top lanes double
  bumpers until a drain. Bumpers, slings, lanes and ramps score as the table says.
- **End:**
  - the end by lives, the end at 2:00, and the tie-breaks;
  - RESULT: A rematches and B goes to the title.
- **Conventions:**
  - Start pauses, with RESUME and QUIT TO TITLE (B or Start resumes);
  - Start + Select quits;
  - 60 s idle goes to the title;
  - the title waits for buttons to be released.

**`Bot(player, seed)`** returns per-frame inputs (flip, plunger):
- it flips when a ball within reach of a flipper is moving toward it;
- it times a late flip toward the ramp when it is calm;
- it flips its φ plate by aiming for the φ target when a rival photon is inbound, with a
  0.25 s reaction delay and a 30% miss;
- it plunges at a random strength.

**Tests:**
- every rule above;
- a scripted ramp shot: a photon crosses with equal phases and returns after the rival flips;
- pause freezes the clock, the bridge and the balls;
- idle → title;
- the bot keeps a ball alive ≥ 20 s on average over 20 seeds, and loses some matches against
  another bot.

**Commit:** `feat: :sparkles: Photon Pinball: the match rules and the CPU player`.

### Task 5: the art and rendering

**Files:**
- Create `src/photon_pinball/art.py`, `src/photon_pinball/render.py`, `tools/snapshot.py`,
  `tools/benchmark.py` and `tests/test_render.py`.

**`art.py`:** port the look reference into a module.
- **Static surface:** `build_static()` returns a 960x540 surface with everything static:
  - the backdrop, both playfields with the photonic-chip print, the rails, the apron and the
    glass;
  - the bridge deck, mirrors and glass cubes;
  - the wire ramps, and the unlit inserts, plates and bumpers.
  It is drawn at 2x and smoothscaled, **using the `TableLayout` positions**.
- **Sprite caches:**
  - the photon ball, whole and ghost, for each colour;
  - flippers at 24 angles across their swing, per side;
  - a lit bumper flare, lit inserts per shape, and a lit plate per player;
  - the DMD dot grid.

**`render.py`:** `Renderer(surface).draw(match, events)`.
- **Each frame:** the static surface, then:
  - lit inserts (lanes lit, ramp arrows when a ramp shot is "ready", φ inserts at π);
  - bumper flares that fade over 0.2 s after a hit;
  - flippers from the angle cache;
  - balls, with a 3-dot trail;
  - the balls riding ramps along their paths;
  - the bridge's ghost halves and lit arms, the plates (pulse when a half passes) and the BS2
    merge flash.
- **The DMD:** scores, clock, balls; the calls SPLIT!, INCOMING!, BOUNCED! and DRAIN!, for
  1.2 s each. It is re-rendered only when its text changes.
- **The event stamp:** INCOMING! or BOUNCED BACK! on the receiving table.
- **The screens:** the title (name, 1/2 PLAYERS, attract demo behind, a dimmed "PRESS START"),
  pause, and the result.
- **The first match's hints:**
  - "A: FLIPPERS" and "PULL STICK: PLUNGER" on each table;
  - "SHOOT THE RAMP" by the mouth;
  - "HIT φ TO FLIP YOUR PHASE" by the target;
  - each fades after 6 s.

**Tools:**
- **`tools/snapshot.py OUT`:** renders the title, a match, a split, INCOMING!, BOUNCED!, pause
  and the result. Compare these by eye with the look reference.
- **`tools/benchmark.py`:** plain surfaces with `pygame.font.init()` only, since the cabinet's
  SDL has no dummy video driver. It times 3,000 frames of a bot-vs-bot match with 3 balls and
  bridge traffic, and reports the mean, p95 and worst frame.

**Tests:**
- every screen and state draws;
- the static art is built once (a counter);
- no per-frame `smoothscale` or font render while the DMD text is unchanged (patch and count);
- snapshots run.

**Commit:** `feat: :art: Photon Pinball: the glossy table art and rendering`.

### Task 6: main, input, audio, the README and deploy script

**Files:**
- Create `src/photon_pinball/main.py`, `display.py`, `input.py`, `input_test.py`,
  `audio.py`, `README.md` and `deploy_batocera.sh` (mode 755), with tests `test_input.py`
  and `test_main.py`.

- **`display.py`:** a 960x540 SCALED window or fullscreen, `SDL_RENDER_SCALE_QUALITY=linear`,
  because this art is smooth.
- **`input.py`:**
  - per player: A held/pressed and the stick's y-axis, which drives the plunger;
  - Start/Select, and the quit combo;
  - keyboard dev fallbacks;
  - `--no-keyboard`.
- **`audio.py`:**
  - effects: flipper, bumper, sling, ramp, split, merge, incoming, drain;
  - a short title jingle;
  - synthesised as in Gate Drop's `audio.py`, and silent if the mixer fails.
- **`main.py`:** the loop. It runs fixed 60 Hz frames and `match.update`, renders, and
  supports `--fps`.
- **`deploy_batocera.sh`:** copied from gate-drop's, with the game renamed.
- **`README.md`:** what it is, the rules, the bridge's physics, the controls table, setup,
  tests, tools, layout and deploying.

**Verification:**
- run windowed for a minute, bot vs bot, using `--attract`;
- play 1P with the keyboard;
- `uv run python -m photon_pinball --input-test` works.

**Commit:** `feat: :joystick: Photon Pinball: playable, with sound and the deploy script`.

### Task 7: the logo, the menu entry and deploying (the controller)

- **The logo module:** `batocera/logos/logo_photon_pinball.py`, in its own design language, a
  real machine's backglass:
  - glossy, lit;
  - the hero is the glowing photon split into two halves on the interferometer's diamond;
  - the title in chrome-and-neon pinball lettering.
  Check it against AGENTS.md's logo rules: readable at 128 px, title readable at 256 px, no
  taglines.
- **Menu entry:** `batocera/gamelist.xml` gets `photon_pinball.pygame`, with name, description,
  image and marquee.
- **The cabinet:**
  - benchmark on the cabinet;
  - deploy;
  - the gamelist edit and **one ES restart**: ask the user first, because it's the risky step.
  This happens when the cabinet is reachable.
- **Commit:** `feat: :art: Photon Pinball: logo and menu entry`.
