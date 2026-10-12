# Superconductor

Route two-qubit gates across a superconducting chip before they decohere. A 1–2 player
pygame game for the IconicArcade Raspberry Pi 4 cabinet (Batocera, `pygame` system),
packaged the same way as the other games in this repo.

**Status:** playable prototype. It has 1 player, co-op and versus modes, four chip
layouts, crossing routes with collisions, four chip specials, a coherence timer, scoring,
high scores, an input-test mode and a Batocera deploy script. There is no circuit mode
yet.

## Gameplay

Pairs of qubits light up on the chip in the same color: each pair is a two-qubit gate
waiting to happen. Draw a route between them, one coupler at a time. When the route
reaches the partner, a qubit travels along it (a few seconds), and the gate fires on
arrival.

- **Nothing is reserved.** A route can go anywhere except over a defect coupler (or
  across itself): through other stations, across other routes, even along the same
  couplers another qubit is travelling. What stops you is crashing. Every qubit has a
  finite size: two qubits inside the same one at the same time crash, and so do two
  qubits that meet on a coupler, head-on or one catching up with the other. Following
  another qubit down a coupler is fine. In a crash both gates are lost, and you lose a
  life.
- **A waiting pair is in superposition.** Until it is routed, its qubit is in *both*
  stations at once, and you can see it: a light disc in each station, swelling in one as
  it shrinks in the other. Run into either station and you crash. Routing the pair
  collapses the qubit onto the start: from then on it is the qubit travelling along the
  route, and both stations are empty (drawn dimmed) and safe to run through, the start
  once the qubit has left it. So running through a waiting station is fine if you route
  that pair, from either end, before you get there. The game doesn't stop you.
- **Lookahead.** While you draw, a big blinking red X marks where your route would crash
  if it went off right now, on a qubit or part way along a coupler. A small one on a
  station means a committed route is heading into it, so route that pair before the qubit
  gets there. Both use exactly the rules the crash itself uses. A crash between two
  committed routes gets no warning: nothing can change it any more.
- **Losing a life** flashes the whole chip red, the lost life icon swells and blinks, and
  "LIFE LOST" appears above the chip.
- **Coherence timer.** The ring around a waiting pair is its coherence. At zero the pair
  decoheres and costs one of 3 lives. The game starts with two pairs waiting. Over the
  first 2.5 minutes, pairs arrive faster and decohere sooner. A quick player gets there
  sooner: every second the chip sits with nothing to route speeds the schedule up a
  little more (`PACE_GAIN`, up to 1.4×), and it never slows down again.
- **Score** = 100 × fidelity + up to 50 for coherence left. Each hop beyond the shortest
  possible route multiplies the fidelity by 0.9.
- You never roam the chip freely: your cursor always starts on an endpoint ("station") of
  a waiting pair, marked by a wobbling rounded square in your color. You cycle between
  stations with a button. When you finish a route, the cursor jumps to the oldest pair
  still waiting.

**Specials** turn up on free parts of the chip for a while. They never land on a route
that is drawn or in progress, and never share a qubit with a station:

| Special | Looks like | Effect | Lasts |
|---|---|---|---|
| Miscalibrated coupler | orange wobbly coupler | 3× slower, and the gate's fidelity × 0.8 | 20 s, then "recalibrated" |
| Defect coupler | broken red coupler with an X | can't be used at all | 15 s, then "restored" |
| Speed qubit | gold chevrons | every qubit passing over it travels 2× faster (stacks up to 4×) | 25 s |
| Bell pair | two ringed qubits linked by a bowed dashed line | a route entering one end continues from the other end, once. While a route has claimed it, both ends are plain qubits to every other route | 30 s, or until used |

They unlock over time: miscalibrations from the start, speed qubits after 25 s, defects
after 40 s and Bell pairs after 70 s. The values are in `config.py`.

**Chips:**

| Chip | Layout |
|---|---|
| Square | 5×5, every grid neighbour coupled (4 per qubit, as on Google's chips) |
| Brick | 5×5, every other vertical coupler, staggered like a brick wall. That is hexagonal connectivity (3 per qubit, the graph behind IBM's heavy-hex), without diagonal lines |
| Bottleneck | two 4-wide, 3-high halves, joined only through the middle two columns |
| Distributed | four 3×3 modules in a 2×2 grid. Neighbouring modules share a single link between the middle qubits of their facing sides |

The links between blocks and modules are drawn as hollow lines. Every coupler on every
chip joins grid neighbours, so the stick always works in four directions.

**Modes:**
- **1 Player:** one chip.
- **Co-op:** both players route on the same chip, with shared score and lives. Pairs come
  25% more often than solo (`COOP_SPAWN_RATE`). A pair one player has selected can't be
  taken by the other. When a new pair appears and both players are free, it goes to
  whoever did *not* route last, so it doesn't always land on P1. Routes don't block
  each other here either: if one player commits a route through the other's half-drawn
  one, the red X shows the second player where they would now crash.
- **Versus:** two chips side by side, fed the identical sequence of pairs (same seed).
  Each player has their own lives. Once both chips have decohered, the higher score wins.

**Title screen legend:** while MODE or QUIT is picked, the right half of the title plays
a legend, one thing on the chip at a time: PAIR, COHERENCE, RED X, MISCALIBRATED, DEFECT,
SPEED QUBIT and BELL PAIR. Each is a few seconds on a small 3x4 chip, played by the real
rules (a `Board` with a scripted spawn list and scripted stick pushes, in `tutorial.py`)
and drawn by the game's own `draw_board()`, with a name and two short lines under it. The
scenes make no sound. While CHIP is picked it shows the chosen chip playing itself instead.
The HOW TO PLAY card reuses the PAIR and RED X scenes.

## Setup and run (dev machine)

Requires [uv](https://docs.astral.sh/uv/).

```bash
cd superconductor
uv sync
uv run python -m superconductor.main                # windowed, keyboard/joystick
uv run python -m superconductor.main --fullscreen
uv run python -m superconductor.main --input-test   # live joystick/keyboard state
uv run pytest
```

The game renders natively at 1920×1080, the cabinet panel's own resolution, so SDL never
rescales it (see `../AGENTS.md`). Layout values in `game.py` are written for a 1280×720
design and multiplied by `U = height / 720`. If the Pi can't keep up, set
`INTERNAL_WIDTH/HEIGHT` in `config.py` to 960×540: that height also divides 1080. On a dev
PC a frame takes about 1.6 ms. **F3** toggles the FPS overlay, and **F1** on the title
screen opens the input test.

### Controls

| | Cabinet pad | P1 keyboard | P2 keyboard |
|---|---|---|---|
| Draw route / step back | Stick | E S D F | Arrow keys |
| Next station | A or R | J | `.` |
| Previous station | L | I | N |
| Other end of this pair | B | K | `,` |
| Undo one step | X | U | M |

- Moving back the way you came also undoes one step. A Bell jump has no "way back" on the
  stick, so undo it with X. Reaching the partner commits the route automatically.
- On the title screen, the stick picks a row (MODE, CHIP, QUIT) and changes it. Start
  always plays, whatever row is picked; A plays too, except on **QUIT**, where it leaves
  the game at once (back to EmulationStation, or the launcher's menu). B does nothing
  there.
- Every match from the title opens on a **HOW TO PLAY** card: the goal in three lines, a
  scripted scene played by the game's own rules, and the cabinet's 2x3 button cluster with
  the used buttons lit. Any button closes it (presses in the first 0.3 s are ignored, so
  the Start that picked the match can't skip it); that press does nothing in the match.
- In-game, Start (or P) pauses. Select (or Esc) pauses too, and from the pause menu it
  goes back to the title.
- **Quit:** QUIT on the title, or hold Start and Select together on either pad, or hold
  Select (or press Esc) for 2 s on the title screen.
- Start is raw 9 and Select raw 8, confirmed on the cabinet. B resumes from the pause menu
  and leaves the game-over screen, per the cabinet's button convention (`../AGENTS.md`).
- The keyboard is a dev fallback only. P1's keys avoid `l x r b y a`, which the cabinet's P1
  encoder types too (see `../AGENTS.md`). On the cabinet the loader passes `--no-keyboard`.

High scores (per mode and chip, not for versus) are saved to
`~/.superconductor_hiscores.json`, which is `/userdata/system/` on Batocera.

## Code layout

| File | What |
|---|---|
| `lattice.py` | The chip layouts: couplers, drawing positions, neighbours, distances |
| `rules.py` | All game rules (spawning, drawing, committing, travel, collisions, specials, scoring), pure Python and unit tested |
| `input.py` | Pad and keyboard to actions, with stick auto-repeat |
| `tutorial.py` | The scripted scenes (title legend, HOW TO PLAY) and when a press closes the card |
| `game.py` | Menus, drawing, sound and the main loop |
| `config.py` | Input mapping and every tuning constant (speed, timers, ramp, scoring) |

## Deploy to the cabinet

```bash
./deploy_batocera.sh                  # defaults to root@batocera.local
./deploy_batocera.sh root@10.42.0.100 # if .local resolution isn't working
```

This is a new ROM, so EmulationStation needs one rescan or restart before it appears.
For the menu name and icon, merge the `superconductor` entry from
`../batocera/gamelist.xml` into the cabinet's gamelist, and copy
`../batocera/icons/superconductor-image.png` to `/userdata/roms/pygame/images/` (see
`../AGENTS.md`).

## Ideas parked for later

- Circuit mode: a circuit window with a dependency graph instead of random pairs (gates
  that don't depend on each other can run in any order).
- More specials: meeting in the middle (both ends travel), three-qubit chains (GHZ), chip
  regions going offline for calibration.
- In versus, specials can land in different places on the two chips, because where one
  fits depends on each chip's state. Only the pairs are guaranteed identical.
- Bigger chips and real topologies (heavy-hex with coupler qubits).
