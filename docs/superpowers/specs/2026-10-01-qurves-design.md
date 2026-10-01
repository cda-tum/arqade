# Qurves: design

A two-player versus light-cycle game (Tron) for the ARQADE cabinet, where your
bike can split into a superposition of two mirrored copies. You only lose a
round when *every* copy of you has crashed.

- **Players:** exactly 2, versus. No solo mode and no bot in v1.
- **Target:** the Batocera cabinet described in `../../../AGENTS.md` (Pi 4,
  1920x1080, two 6-button pads, Python 3.11, pygame 2.5.2).
- **Look:** neon vector, all procedural (no image assets beyond the bundled
  Press Start 2P font).

## 1. Rules

### Controls

| Action | Cabinet | P1 keyboard (dev) | P2 keyboard (dev) |
|---|---|---|---|
| Steer | stick (absolute: push up = head up) | I J K L | numpad 8 4 5 6 |
| Split | A (raw 1) | U | numpad 0 |
| Start / confirm | Start (raw 9), or A | Enter | numpad Enter |
| Back | B (raw 2) | O | numpad . |
| Quit | Start + Select (raw 9 + 8) on one pad | Esc | Esc |

- Direction comes from the stick's dominant axis past a 0.25 deadzone. Axis 1
  is vertical (negative = up, confirmed on the cabinet). Axis 0 is assumed
  horizontal and must be confirmed with `--input-test`. The hat is read only
  as a fallback.
- P1's keyboard keys avoid `l x r b y a` and the arrow keys, which the
  cabinet's P1 encoder also types (AGENTS.md). On the cabinet the loader
  passes `--no-keyboard`, so this only matters for dev runs.
- Reversing straight into your own heading is ignored.
- Steering input is sampled per tick: the most recent non-neutral direction
  since the last tick wins, so a quick tap between ticks is not lost.
- There is no pause. It is a short arcade versus game.

### Arena and round

- The arena is a grid of **160 x 84 cells**, ringed by walls.
- P1 starts at cell (20, 42) heading right, P2 at (139, 42) heading left,
  after a 3-2-1 countdown.
- Bikes move one cell per tick. Speed starts at **14 cells/s** and rises by
  **2 cells/s every 10 s**, capped at **24 cells/s**. The ramp starts over
  with every round.
- A player loses the round when every copy of their bike has crashed.
- If both players lose on the same tick, the round is a **draw** and is
  replayed. No one scores.
- **First to 3 round wins** takes the match.

### H pickups and the meter

- Each player has a meter from 0 to 100. It starts at 0 each round and never
  recharges on its own.
- Up to **2 H tokens** are on the field at once. Each spawns on a random empty
  cell at least 10 cells from every bike head, and respawns 2 s after it is
  taken. If no cell qualifies, the spawn waits and is retried each tick.
- Driving over a token adds **50** to your meter, capped at 100. A token
  picked up by a copy is credited immediately, even if that copy is later
  eliminated.

### Splitting

- Press A to split when your meter is **at least 50** and you are not
  already split. You never have more than 2 copies.
- **The fork:** at the moment of the split, your bike at cell `p` with
  heading `h` becomes two copies at `p`. Copy 0 turns left relative to `h`
  and copy 1 turns right. The **split axis** is the line through `p` along
  `h`.
- **Mirrored steering:** after that, copy 0 follows the stick directly. Copy 1
  follows the stick reflected across the split axis: the component along `h`
  is unchanged, and the perpendicular component is negated. Each copy still
  ignores a reversal of its own heading.
- While split, the meter drains at **50 per 3 s** in real time, so one token
  buys 3 s of superposition and a full meter buys 6 s.
- Both copies leave **ghost trails**, tagged with the player and branch
  (0 or 1).

### What each bike collides with

The core idea: **a branch only sees real trail and its own branch.** Each bike
classifies the cell it is about to enter:

| Cell contains | Effect on the entering bike |
|---|---|
| Wall | crash |
| Solid trail (anyone's) | crash |
| Its own branch's ghost trail | crash |
| The *other* branch of its own player | nothing, passes through |
| An opponent's ghost trail | **measurement** of the opponent (see below), passes through |

- A bike's **head counts as trail of its kind**: real for a solid bike, ghost
  of its branch for a copy. This settles head-on and swap-through cases with
  the same table. Two copies of the same player never collide with each other.
- Two bikes of different players that enter the same cell, or swap cells, on
  the same tick each apply the table to the other's head.

### How a superposition ends

One principle covers all three cases: **an eliminated branch never happened,
so its ghost trail dissolves** (its cells become empty), and the surviving
branch's ghost trail becomes solid.

- **Crash:** the copy that crashed is removed, and its trail dissolves. The
  player is now a single solid bike. If both copies crash on the same tick,
  the player loses the round.
- **Measurement:** when any opponent bike, including an opponent's copy,
  enters your branch `b`'s ghost trail, you collapse at once onto branch
  `1 - b`. If both your branches are touched on the same tick, collapse at
  random, 50/50.
- **Decoherence:** when your meter reaches 0, you collapse at random, 50/50.

### Tick order

Each tick runs these steps in order. Steps 2 and 3 are computed for every bike
before any of them is applied, so all bikes effectively move at once.

1. Apply steering, including the mirroring for split players.
2. Compute each bike's target cell.
3. Classify every target against the grid before this tick, with heads
   counted as trail.
4. Apply crashes, dissolving the trails of eliminated branches.
5. Apply measurements, to players who are still split.
6. Write each surviving bike's new cell: solid for a single bike, ghost for a
   copy.
7. Collect pickups.
8. Drain the meters, and apply decoherence when a meter reaches 0.
9. Check whether the round is over: a win, or a draw.

Meter drain is real time, so step 8 takes `dt`. Everything else is per tick.

## 2. Architecture

The game lives in a new top-level `qurves/` directory, the same shape as the
other games: a uv project, `src/qurves/`, `tests/`, `README.md` and
`deploy_batocera.sh`.

| Module | Responsibility |
|---|---|
| `rules.py` | Pure simulation, no pygame. `Arena` (the cell grid), `Bike`, `Player`, `RoundState` and `step(state, inputs, rng) -> list[Event]`. |
| `match.py` | Pure state machine: title, countdown, round, round result, match result. Owns the score, the speed ramp and the idle timeout. |
| `render.py` | Draws the layers listed in section 3 from the state, and reacts to events. |
| `fx.py` | Particles, flashes and screen shake. |
| `sound.py` | Procedural sound effects, keyed by event. |
| `input.py` | Pads plus the dev keyboard turned into per-player actions, including the quit combo and `--no-keyboard`. |
| `config.py` | All tuning numbers, colours, `INPUT_CONFIG`, and the `GLOW` / `SHOW_SCANLINES` flags. |
| `display.py`, `fonts.py`, `input_test.py`, `main.py` | Copied from the sibling games' patterns. |

- **Grid cells** hold `EMPTY`, `WALL`, or a trail value of
  `(player, branch)`, where `branch` is `None` for solid trail and `0`/`1`
  for a ghost trail.
- Each branch keeps the list of cells it wrote, so dissolving or solidifying
  it touches only those cells, never a whole-grid scan.
- `step()` returns events: `Split`, `Crash`, `Collapse(player, reason)` with
  reason crash, measurement or decoherence, `Measured`, `Pickup`, `RoundOver`.
  `render.py`, `fx.py` and `sound.py` consume them. `rules.py` never imports
  pygame.
- The RNG is injected, so decoherence and pickup spawns are deterministic in
  tests.
- **Ticks vs frames:** the simulation runs at the tick rate set by the
  current speed. Rendering runs at 60 fps and interpolates each head between
  its previous and current cell, so movement looks continuous.

### Screens and buttons (cabinet convention)

- **Title:** Start or A begins a match. Select held for 2 s, or Start +
  Select, quits.
- **Countdown, round, round result:** no menu input. The round result shows
  for 2 s, then the next countdown starts.
- **Match result:** A or Start starts a rematch. B goes back to the title.
- **Idle:** 60 s without input on any screen returns to the title.

## 3. Visuals, sound and performance

- **Resolution:** an internal 960x540 surface, shown with SDL `SCALED`
  fullscreen at exactly x2. The grid uses 6 px cells, with a 36 px HUD strip
  on top (160 x 6 = 960, 36 + 84 x 6 = 540).
- **Layers, from the bottom up:**
  1. **Background:** pre-baked once. A dark floor, a faint grid, a vignette.
  2. **Solid trails:** a persistent surface. Each tick only the new cell is
     painted: a wide, dim glow stroke under a thin bright core, with rounded
     joins at corners.
  3. **Ghost trails:** one surface per player, drawn dashed (every other
     cell) and flickering through a per-frame alpha. A surviving branch is
     repainted onto the solid layer. An eliminated branch's layer is cleared
     and the dissolve effect runs.
  4. **Bike heads:** small pre-rendered glow sprites, blended additively.
  5. **Effects:** sparks for crashes and collapses, sparks sampled along a
     dissolving trail, a white flash with a ring at a measurement, and a
     light screen shake on crashes.
  6. **Scanlines:** a pre-baked CRT overlay, blitted last.
- **Budget:** about four full-screen blits per frame, plus small sprites.
  `GLOW` and `SHOW_SCANLINES` can be turned off in `config.py` if the cabinet
  drops frames. Check with `--fps` on the cabinet.
- **Colours:** P1 cyan, P2 orange (matching Qlimbers). Ghost copies use the
  same hue at lower intensity. H tokens are pulsing white.
- **HUD:** each player's meter, labeled `|ψ>`, on their own side, and the
  round pips in the middle. Check that the font has `ψ` (AGENTS.md lists it
  as present) and spell kets with ASCII `|` and `>`.
- **Title:** a neon QURVES logo, two short animated trails, a one-line rule
  summary and PRESS A OR START.
- **Sound:** short procedural effects only, no engine hum. Countdown beeps, a
  pickup blip, a rising chirp on a split, a falling sweep on a collapse, a
  zap on a measurement, a noise burst on a crash.

## 4. Packaging and cabinet integration

- `deploy_batocera.sh` follows the sibling scripts: code to
  `/userdata/games/qurves/qurves/`, and a loader at
  `/userdata/roms/pygame/qurves.pygame` calling
  `main(["--fullscreen", "--no-keyboard"])`. It is committed executable with
  LF line endings.
- A `batocera/gamelist.xml` entry (name **Qurves**) and a `qurves()` icon
  function in `batocera/icons/generate_icons.py`, producing
  `qurves-image.png`.
- The first time it goes on the cabinet, add the gamelist entry with ES
  stopped, then restart ES, as done for Overquqed and Superconductor.
- `--input-test` mode, to confirm axis 0 and the button numbers on the pads.

## 5. Testing

pytest, with most of the weight on `rules.py`:

- The fork directions, and mirror reflection for each heading.
- The no-reverse rule for a single bike and for each copy.
- Every row of the collision table, including heads counted as trail,
  head-on, swap-through, and same-player copies passing through each other.
- All three collapse paths: the right cells dissolve, the right ones become
  solid, and the player ends up with a single bike.
- Measurement on both branches in one tick falls back to the random collapse.
- Both copies crashing on one tick loses the round. Both players losing on
  one tick is a draw.
- The meter: the 50 threshold, the cap at 100, drain over time, and pickup
  crediting.
- The tick-order cases where a crash and a measurement happen on the same
  tick.

`match.py`: the transitions, first to 3, draws replaying the round, rematch
versus back to title, and the idle timeout. Plus config sanity and input
mapping tests, as in the sibling games. The look is checked by rendering
frames to PNG during development and on the cabinet with `--fps`.

## Out of scope for v1

- Solo play against a bot, and more than 2 players.
- Nested splits (more than 2 copies per player).
- A pause menu.
- High scores. The game is a pure head-to-head match.

The next game after this one is **Gate Drop**, the versus puzzle where
cancelling gates clears them. It gets its own spec.
