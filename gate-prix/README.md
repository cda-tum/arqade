# GATE PRIX

A behind-the-car pseudo-3D kart racer (OutRun-style) for 1 or 2 players, for the ARQADE
cabinet (Batocera, `pygame` system). You race through THE FRIDGE, the inside of a dilution
refrigerator. Gates stand on the track as arches, and the overlay shows the **target
circuit**: drive through the arch of its next gate to build the circuit gate by gate.
Design: `../docs/superpowers/specs/2026-10-12-gate-prix-design.md`; the approved look is
`../docs/superpowers/specs/2026-10-12-gate-prix-look.py`.

**Status:** playable. The race, items, CPU racers, title with an attract race, pause,
results, sound, `--input-test` and the Batocera deploy script are in; the HUD and screens
are basic and get the look file's polish next (Task 6 of the plan). Button numbers follow
the ones confirmed on the cabinet.

## The race

- **6 cars, 3 laps** of about 45 s. 2 PLAYERS race in split screen (P1 on top, blue; P2
  below, red) against 4 CPU racers; 1 PLAYER gets the full screen against 5.
- **The target circuit** is 24 random gates from H, X, Y and Z (never the same gate twice
  in a row), one per **gate row**: 8 rows a lap. A row has 1 to 3 arches spread across the
  road; one is the slot's gate (it glows), the others are decoys.
- **Driving through an arch** adds its gate to your circuit:
  - **the right gate:** your streak grows and you get a **light-speed boost**, +20% for
    1 s on the first and +8% / +0.2 s for each further one in a row, up to +60% for 2 s;
  - **a wrong gate** or **missing the row** (an empty slot): the streak resets. No other
    penalty.
- **CIRCUIT CHECK:** crossing the line into the final lap, your first 16 slots are
  compared with the target's. Each wrong or empty one counts; the fewer, the bigger the
  boost: (16 - wrong) / 16 x 80% for 1 s + (16 - wrong) x 0.25 s. A perfect circuit is
  +80% for 5 s.
- **Off the road** (on the copper plate) the top speed drops to 60%. Cars bump.
- **Item boxes** (two lines a lap) give an item, better odds further back. You hold one:
  - **SPLIT:** for the next 2 gate rows a translucent clone drives mirrored across the
    centre line; if either of you takes the right arch, the slot is right;
  - **QEC:** error correction, your most recent wrong or empty slot becomes right (for the
    check and the results, not the streak).
- **The result:** places and times, and each player's circuit under the target with its
  accuracy ("21/24 GATES"). A rematches, B goes to the title.
- **2 PLAYERS:** the race ends when both have finished, or 40 s after the first one did
  (the other is placed where they are). A finished car is driven on by the computer.

## Controls

| Action | Cabinet | P1 keyboard | P2 keyboard |
|---|---|---|---|
| Steer | stick left / right | S / F | Left / Right |
| Brake (held through a curve: a little drift) | stick pulled back | D | Down |
| Use the item; confirm in menus | A | Q | . |
| Back (pause menu, result) | B | W | , |
| Start the race; pause (RESUME / QUIT TO TITLE) | Start | 1 | 2 |
| Select (only for the quit) | Select | 3 | 4 |
| Quit | Start + Select on one pad | 1 + 3, or Esc | 2 + 4, or Esc |

- **Title:** the stick picks 1 or 2 PLAYERS, A or Start begins. Untouched for 3 s, an
  attract race of 6 CPU-driven cars plays behind it.
- **Pause:** Start, on either pad. The stick moves, A picks, B or Start resumes.
- **Idle:** 60 s untouched anywhere (paused too) returns to the title, at 1 PLAYER.
- With 1 PLAYER either pad drives. The accelerator is automatic.
- The keyboard is a dev fallback only: P1's keys avoid `l x r b y a`, which the cabinet's
  P1 encoder also types, and the cabinet's loader passes `--no-keyboard`. The stick is read
  as an analog axis (axis 0 steers, axis 1 brakes), never a hat.

## Setup (dev machine)

Requires [uv](https://docs.astral.sh/uv/). Python 3.11 and pygame 2.5.2 exactly, as on
the cabinet.

```bash
cd gate-prix
uv sync
uv run python -m gate_prix                       # windowed, 1440x810
uv run python -m gate_prix --window-size 960x540 --fps
uv run python -m gate_prix --fullscreen          # scaled exactly 2x on a 1920x1080 screen
uv run python -m gate_prix --input-test          # live pad and keyboard state
uv run python -m gate_prix --selftest 600 --shots /tmp/gate-prix-shots
```

From the repo root, `./arqade.sh` runs it from the ARQADE launcher's menu too.

`--selftest SECONDS` plays a scripted session through the real loop and renderer, as fast
as the machine draws: the title and the attract race, a 1P race steered by a bot with the
stick mashed on top (pause and resume, the result, a rematch, QUIT TO TITLE with A held),
a 2P race to the result, and a race left alone until the idle timeout. It checks the
match at every step and exits 0 if all held (it stops early, still 0, after SECONDS of game
time). `--shots DIR` saves a screenshot of every screen on the way; `--seed N` fixes the
races.

## Tests

```bash
uv run pytest -q                                            # about 20 s
uvx --from 'ruff==0.15.22' ruff check src tests tools
```

The tests cover the circuit, the track and its gate rows, the car's handling, the race
rules, items, the CPU racers (over many seeds), the road projection and sprite cache, the
match flow (title, attract, countdown, pause, idle, finish, result), the input (axes,
presses, the armed Start + Select quit, keyboard fallbacks, `--no-keyboard`), the sound
table, and a short scripted session of the real loop.

## Tools

| Tool | Does |
|---|---|
| `tools/road_demo.py` | Drive the camera round the track (`--screenshot` for one frame). |
| `tools/drive_demo.py` | A real race with debug text; `--auto` drives P1 perfectly. |
| `tools/benchmark.py` | Times the road renderer (2 views, then 1); runs headless, also on the cabinet. |
| `tools/handling.py` | How the track drives, piece by piece, for tuning the handling. |
| `tools/race_stats.py` | Races the CPUs over many seeds: gate rates, finish gaps, bumps. |

## Layout (`src/gate_prix/`)

| Module | Role |
|---|---|
| `circuit.py` | Gates, the exact single-qubit simulation, targets, slots, Hamming distance, QEC. Pure. |
| `track.py` | THE FRIDGE's segments (curves, hills), gate rows, item boxes, roadside sprites, the racing line. Pure. |
| `car.py` | Car physics: auto-acceleration, steering, curves, off-road, boosts, bumps. Pure. |
| `race.py` | The race: cars, arches, items, laps, the CIRCUIT CHECK, places, the finish. Pure. |
| `bot.py` | The CPU racers (and the attract race's drivers, and a finished player's autopilot). Pure. |
| `match.py` | Title, attract, countdown, race, pause, result, idle. Pure. |
| `road.py` | The pseudo-3D projection and road drawing for one view. |
| `sprites.py` | Every sprite pre-rendered at 24 sizes at start-up; the backgrounds per view size. |
| `render.py` | The views, the HUD, the banners and the screens. |
| `audio.py` | Synthesised effects and the engine hum (pitch follows speed); silent without a mixer. |
| `input.py`, `display.py` | Pads and dev keys; the 960x540 surface scaled onto the screen. |
| `game.py`, `main.py` | The fixed 60 Hz loop; the command line. `selftest.py`: the scripted session. |
| `input_test.py`, `config.py` | The input diagnostic; every number, colour and button. |

Rendering is 960x540 (each 2P view 960x270), scaled exactly 2x by `pygame.SCALED` on the
cabinet's 1920x1080 panel. Smooth, anti-aliased art, not pixel art: nothing is rescaled
per frame, only blitted from the start-up caches.

## Deploying to the cabinet

```bash
./deploy_batocera.sh                    # or ./deploy_batocera.sh root@10.42.0.100
```

It copies the package to `/userdata/games/gate_prix/` and writes the loader
`/userdata/roms/pygame/gate_prix.pygame`, which calls `main(["--fullscreen",
"--no-keyboard"])`. The first time, the game also needs its `batocera/gamelist.xml` entry
and one EmulationStation restart (with the go-ahead, see `../AGENTS.md`). Later deploys
only replace the code. For `--input-test` on the cabinet, point the loader at
`main(["--input-test", "--fullscreen"])` for a while, as AGENTS.md describes.
