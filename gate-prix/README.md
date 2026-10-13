# GATE PRIX

A behind-the-car pseudo-3D kart racer (OutRun-style) for 1 or 2 players, for the ARQADE
cabinet (Batocera, `pygame` system). You race through THE FRIDGE, the inside of a dilution
refrigerator. Gates stand on the track as arches, and the overlay shows the **target
circuit**: drive through the arch of its next gate to build the circuit gate by gate.
Design: `../docs/superpowers/specs/2026-10-12-gate-prix-design.md`; the approved look is
`../docs/superpowers/specs/2026-10-12-gate-prix-look.py`.

**Status:** playable, with the first playtest's changes (fewer gates and a gate-free final
lap, a simpler HUD, items that explain themselves, the CIRCUIT CHECK as an event, and more
sense of speed). The race, items, CPU racers, title with an attract race, pause, results,
sound, `--input-test` and the Batocera deploy script are in; the screens get the look
file's polish next (Task 6 of the plan). Button numbers follow the ones confirmed on the
cabinet. The second playtest's rules are in (drifting, the noise storm, MEASURE, TUNNEL and
DECOHERENCE); their visuals come next (Task 5d), so until then the storm, the shots and
the clouds are not drawn.

## The race

- **6 cars, 3 laps** of about 40 s. 2 PLAYERS race in split screen (P1 on top, blue; P2
  below, red) against 4 CPU racers; 1 PLAYER gets the full screen against 5.
- **The target circuit** is 16 random gates from H, X, Y and Z (never the same gate twice
  in a row), one per **gate row**: 8 rows a lap, on **laps 1 and 2 only**. A row has 1 to
  3 arches spread across the road. The right one, the slot's gate, glows brightly under a
  bouncing ▼; the decoys are dimmer and smaller (and only what is drawn counts: a car
  goes through a decoy within 80% of the right arch's width).
- **Driving through an arch** adds its gate to your circuit, and a flash by your car says
  how it went:
  - **RIGHT GATE +BOOST:** your streak grows and you get a **light-speed boost**, +30% for
    1.5 s on the first and +10% / +0.25 s for each further one in a row, up to +70% for
    2.5 s;
  - **WRONG GATE**, or **MISSED** (the row, an empty slot): the streak resets. No other
    penalty.
- **CIRCUIT CHECK:** crossing the line into the final lap, all 16 of your slots are
  compared with the target's. Your view freezes for a second on the comparison ("14/16
  GATES CORRECT", the wrong ones marked) while your car drives on (the race keeps going for
  everyone else), then comes the **LIGHT SPEED!** warp: (right / 16)² x 100% extra speed
  for 2 s + 0.25 s per right gate. A perfect circuit is +100% for 6 s, 14/16 is +77% for
  5.5 s, 12/16 is +56% for 5 s. The CPU racers get the same check by their own circuits,
  so a better circuit's warp passes them.
  A check under +5% (3/16 or fewer) is **NO BOOST**: no warp at all.
- **The final lap** has no gates, but a **noise storm**: your own decoherence hazards, that
  only you see and hit (the CPUs get theirs). There are 4 + 2 per wrong gate of the check
  (a perfect circuit 4, 8/16 20, at most 24), spread over the lap, never within 1 s of the
  finish, and they always leave a clear line more than a car wide:
  - a **static cloud** (wide) takes your boosts and caps you at 70% for 1 s;
  - a **bit-flip mine** (small) spins you out: 40% speed, and no steering for 0.8 s.
- **Drifting:** pull the stick back *and* steer (at least 40% of the stick, from 60% of the
  top speed). The car slides, turns tighter and runs at 92% speed. After 0.7 s it is
  charged to level 1, after 1.5 s to level 2; letting go gives a **mini-turbo**, +25% for
  0.6 s or +40% for 1 s. Slowing below half speed, a bump or a hit ends it with nothing.
- **Off the road** (on the copper plate) the top speed drops to 60%. Cars bump.
- **Item boxes** (two lines a lap, every lap) always give an item: the back of the field
  gets more MEASURE, TUNNEL and SPLIT, the front more DECOHERENCE and QEC, and on the final
  lap there is no SPLIT or QEC. You hold one; its slot pulses with its name, a big A and
  what it does, and the first time you get each one a banner says "PRESS A TO USE ...":
  - **SPLIT** ("a clone takes a second gate"): for the next 2 gate rows a translucent
    clone drives mirrored across the centre line; if either of you takes the right arch,
    the slot is right. It is over with the last gate row: one still held is dropped;
  - **QEC** ("fixes your last wrong gate"): error correction, your most recent wrong or
    empty slot becomes right (for the check and the results, not the streak);
  - **MEASURE:** a homing shot at the nearest car ahead within 30,000 units (about 2.7 s).
    It flies 0.4 s and **collapses** that car: a spin-out, its streak reset, its boosts
    gone. With nobody in range it fizzles;
  - **TUNNEL:** for 3 s you pass through cars, drive off-road at full speed, and are
    immune to the storm, clouds and MEASURE;
  - **DECOHERENCE:** drops a noise cloud just behind you for 10 s. Whoever drives through
    it loses their boosts and, on laps 1-2, their NEXT GATE badge and arch marker go blank
    for 1.5 s (on the final lap it is a storm cloud's slowdown instead).
- **The HUD:** one big NEXT GATE badge with a dot under it for each of the 16 slots (✓
  green, ✗ red), the place and the lap, and the held item.
- **Speed you can feel:** the top speed is 12% up from the first build, the roadside
  stands close to the road, speed lines show at top speed, the camera shakes a little,
  and a boost widens the field of view, lights the exhaust and whooshes.
- **The result:** places and times, and each player's circuit under the target with its
  accuracy ("14/16 GATES") and its check ("CHECK 12/16"). A rematches, B goes to the title.
- **2 PLAYERS:** the race ends when both have finished, or 40 s after the first one did
  (the other is placed where they are). A finished car is driven on by the computer.

## Controls

| Action | Cabinet | P1 keyboard | P2 keyboard |
|---|---|---|---|
| Steer | stick left / right | S / F | Left / Right |
| Brake | stick pulled straight back | D | Down |
| Drift (let go for the mini-turbo) | stick pulled back and steered | D + S / F | Down + Left / Right |
| Use the item; confirm in menus | A | Q | . |
| Back (pause menu, result) | B | W | , |
| Start the race; pause (RESUME / QUIT TO TITLE) | Start | 1 | 2 |
| Select (only for the quit) | Select | 3 | 4 |
| Quit | Start + Select on one pad | 1 + 3, or Esc | 2 + 4, or Esc |

- **Title:** the stick picks 1 PLAYER (up) or 2 PLAYERS (down), A or Start begins (a
  button already held when the game starts must be let go first). Untouched for 3 s, an
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
a 2P race to the result, and a race left alone until the idle timeout. On the way it checks
that all 16 gates come before the final lap and none on it, and that the CIRCUIT CHECK's
freeze lasts about a second while the car drives on. It checks the
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
| `tools/benchmark.py` | Times the road renderer (2 views, then 1; plain, then with the warp's effects); runs headless, also on the cabinet. |
| `tools/handling.py` | How the track drives, piece by piece, for tuning the handling. |
| `tools/race_stats.py` | Races the CPUs over many seeds: gate rates, finish gaps and P1's margin, bumps, items, turbos and hits. |

## Layout (`src/gate_prix/`)

| Module | Role |
|---|---|
| `circuit.py` | Gates, the exact single-qubit simulation, targets, slots, Hamming distance, QEC. Pure. |
| `track.py` | THE FRIDGE's segments (curves, hills), gate rows, item boxes, roadside sprites, the racing line. Pure. |
| `car.py` | Car physics: auto-acceleration, steering, drifting, curves, off-road, boosts, spin-outs, bumps. Pure. |
| `race.py` | The race: cars, arches, items (shots, clouds), laps, the CIRCUIT CHECK, the storm, places, the finish. Pure. |
| `storm.py` | The final lap's noise storm: one racer's hazards, laid out from its check. Pure. |
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
