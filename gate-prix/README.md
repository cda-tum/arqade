# GATE PRIX

A behind-the-car pseudo-3D kart racer (OutRun-style) for 1 or 2 players, for the ARQADE
cabinet (Batocera, `pygame` system). You race through THE FRIDGE, the inside of a dilution
refrigerator. Gates stand on the track as arches, and the overlay shows the **target
circuit**: drive through the arch of its next gate to build the circuit gate by gate.
Design: `../docs/superpowers/specs/2026-10-12-gate-prix-design.md`; the approved look is
`../docs/superpowers/specs/2026-10-12-gate-prix-look.py`.

**Status:** playable, with the first playtest's changes (fewer gates and a gate-free final
lap, a simpler HUD, items that explain themselves, the CIRCUIT CHECK as an event, and more
sense of speed). The race, items, the AI's bots at three levels, the title (PLAYERS, BOTS,
LEVEL) with an attract race, pause, results,
sound, `--input-test` and the Batocera deploy script are in. Button numbers follow the
ones confirmed on the cabinet. The second playtest's changes are in: drifting, the noise
storm, MEASURE, TUNNEL and DECOHERENCE (the rules), and the screens: the vertical split,
the finish line and its gantry, the minimap, item icons, the drift and item effects, the
QUIT row and the HOW TO PLAY card. So is the look file's polish: every car's Bloch orb,
the results' circuits and Bloch spheres, the title's wordmark and ITEM FULL.

## The race

- **Up to 6 cars, 3 laps** of about 40 s. 2 players race in a vertical split screen (P1
  on the left, blue; P2 on the right, red); 1 player gets the full screen. The **bots**
  fill the rest of the field by default (5 against one player, 4 against two), or as many
  as the title's BOTS row says: none at all is a time trial alone, or a duel for two.
- **The bots** are one AI (`ai.py`) at the title's **LEVEL**, the same for all of them:
  - **EASY** (the default), for a first-time visitor: it goes for the right arch only about 45% of the
    time, drives at 94% of the top speed, brakes into the sharp curves instead of drifting,
    misses half the hazards, fumbles half its items (using them at once, wherever it is),
    reacts late (it looks at the traffic every fifth of a second) and wanders off its line;
  - **TOUGH** makes a decent player work: about 4 rows in 5 right, drifts
    most sharp curves, sees nearly every hazard, plays every item at its moment, and is
    rubber-banded a little (3% slower in front, 3% quicker at the back);
  - **BRUTAL** is as near perfect as the game allows: every right arch, every curve
    drifted, every hazard seen, every item played at its moment, and it knows the rivals'
    items too (it never MEASUREs a car that holds a TUNNEL). It never eases off in front.

  Inside a level each bot differs a little (its aim and pace, and its own line), so a field
  never moves in lockstep. The bots are labelled CPU1 to CPU5 and wear neutral colours
  (white, tan, silver, cream, graphite), never a player's; your own car has a white
  outline. Alone on the track over 20 seeds a race takes BRUTAL about 87 s, TOUGH 107 s and
  EASY 127 s (`tools/race_stats.py --ladder`). Scripted players in a 5-bot race: one with
  60% right gates, no drifting and no items beats EASY 20 races out of 20 (at 50% 19, at
  40% 13), and loses to TOUGH every time; a perfect-gate player (no drifting, no items)
  beats TOUGH 19 times in 20 by about 8 s, and loses to BRUTAL every time by about a
  second.
- **The start and finish line** is a chequered band across the road under a gantry with
  a "GATE PRIX" banner and five start lights: red one by one in the 3-2-1 countdown, all
  green at GO. Crossing it shows LAP 2/3, and FINAL LAP with STORM AHEAD. The gantry is
  the one thing on the road drawn at its exact size every frame (`gantry.py`): as a
  nearest-size sprite it jumped between sizes 18% apart as the grid pulled away under it,
  and flickered.
- **The target circuit** is 16 random gates from H, X, Y and Z (never the same gate twice
  in a row), one per **gate row**: 8 rows a lap, on **laps 1 and 2 only**. A row has 1 to
  3 arches spread across the road. The right one, the slot's gate, glows brightly under a
  bouncing ▼; the decoys are dimmer and smaller (and only what is drawn counts: a car
  goes through a decoy within 80% of the right arch's width).
- **The car's qubit:** your circuit so far is simulated exactly on |0>, and the orb on
  your engine cover shows the state: its arrow points along the Bloch vector and its colour
  names the state (|0⟩ ice white, pointing up; |1⟩ gold, down; |+⟩ green, towards you;
  |−⟩ pink, away). H, X, Y and Z from |0> only ever reach these four. Every car carries
  one. It is decoration and teaching only: scoring is gate by gate.
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
  5.5 s, 12/16 is +56% for 5 s. The bots get the same check by their own circuits,
  so a better circuit's warp passes them.
  A check under +5% (3/16 or fewer) is **NO BOOST**: no warp at all.
- **The final lap** has no gates, but a **noise storm**: your own decoherence hazards, that
  only you see (drawn in your view only) and hit (the bots get theirs). There are 4 + 2 per wrong gate of the check
  (a perfect circuit 4, 8/16 20, at most 24), spread over the lap, never within 1 s of the
  finish, and they always leave a clear line more than a car wide:
  - a **static cloud** (wide, crackling grey-violet) takes your boosts and caps you at 70%
    for 1 s;
  - a **bit-flip mine** (a small spiked orb marked X) spins you out: 40% speed, and no
    steering for 0.8 s.
- **Drifting:** pull the stick back *and* steer (at least 40% of the stick, from 60% of the
  top speed). The car slides, turns tighter and runs at 92% speed. After 0.7 s it is
  charged to level 1, after 1.5 s to level 2 (the charge only grows in a bend); letting go
  gives a **mini-turbo**, +25% for 0.6 s or +40% for 1 s. Slowing below half speed, a bump
  or a hit ends it with nothing. A drifting car tilts, with sparks at its rear wheels:
  white, then blue at level 1 and gold at level 2, and the mini-turbo flashes as it fires.
- **Off the road** (on the copper plate) the top speed drops to 60%. Cars bump.
- **Item boxes** (two lines a lap, every lap) always give an item: the back of the field
  gets more MEASURE, TUNNEL and SPLIT, the front more DECOHERENCE and QEC, and on the final
  lap there is no SPLIT or QEC. A box's item pops up over your car as you take it. You hold
  one; its slot pulses with its icon, its name and A (in 1P also what it does), and the
  first time you get each one a banner says "PRESS A TO USE ...". A box driven through
  with an item already held breaks and gives nothing: the slot's edge flashes red and says
  ITEM FULL for a second. The icons:
  - **SPLIT** (two overlapping cars, "a clone takes a second gate"): for the next 2 gate rows a translucent
    clone drives mirrored across the centre line; if either of you takes the right arch,
    the slot is right. It is over with the last gate row: one still held is dropped;
  - **QEC** (a shield with a check mark, "fixes your last wrong gate"): error correction, your most recent wrong or
    empty slot becomes right (for the check and the results, not the streak);
  - **MEASURE** (a meter, its needle swung over): a homing shot at the nearest car ahead
    within 30,000 units (about 2.7 s). A gold orb flies 0.4 s on a beam from your car and
    **collapses** that car: a spin-out, its streak reset, its boosts
    gone. With nobody in range it fizzles;
  - **TUNNEL** (a see-through car passing through a wall): for 3 s, see-through and
    shimmering, you pass through cars, drive off-road at full speed, and are
    immune to the storm, clouds and MEASURE;
  - **DECOHERENCE** (a static cloud): drops a violet noise cloud on the road just behind
    you for 10 s. Whoever drives through it loses their boosts and, on laps 1-2, their
    NEXT GATE badge turns to static (NO SIGNAL) and the arch marker goes for 1.5 s (on the
    final lap it is a storm cloud's slowdown instead). The shooter of a MEASURE that lands
    and the dropper of a cloud that is hit get a sound of their own.
- **The HUD:** top left one big NEXT GATE badge with a dot for each of the 16 slots (✓
  green, ✗ red; in 2P two rows of 8, a lap each); past the last row "TO THE LINE", and on
  the final lap "FINAL LAP: NO GATES". Top right the place and the lap, and the held item
  under them (beside them in 1P).
- **The minimap:** the lap from above with a dot per car (yours bigger, ringed), each
  named beside it (P1, P2, CPU1 ...; in a bunch the people's names come first), small
  ticks for the gate rows (gold) and boxes (blue) and the finish line. 1P: bottom left;
  2P: one map for both, straddling the divider at the bottom.
- **Speed you can feel:** the top speed is 12% up from the first build, the roadside
  stands close to the road, speed lines show at top speed, the camera shakes a little,
  and a boost widens the field of view, lights the exhaust and whooshes.
- **The result:** places (the bots as CPU1 ...) and times, and a panel per player: the
  accuracy ("14/16 GATES") and the check ("CHECK 12/16"); the whole circuit under the
  target's, the wrong slots outlined in red and a ✓ or ✗ under each slot in a row of its
  own; and the final state on a small Bloch sphere beside the target's, with = or ≠
  between them. A rematches, B goes to the title.
- **2 players:** the race ends when both have finished, or 40 s after the first one did
  (the other is placed where they are). A finished car is driven on by the AI.
- **Sounds:** what happens to a bot sounds as it does for a person: a bump or a MEASURE
  hit, yours or between two bots you can see (the bot within your view ahead, or a few car
  lengths behind you). What a bot does to you (a bump, a MEASURE, its cloud you drive
  through) sounds as from a person, and your MEASURE hitting a bot zaps it as well as
  ringing for you. A bot's own drifts, boosts, streaks, boxes, items and checks stay
  silent, so a full field never turns into noise.

## Controls

| Action | Cabinet | P1 keyboard | P2 keyboard |
|---|---|---|---|
| Steer | stick left / right | S / F | Left / Right |
| Brake | stick pulled straight back | D | Down |
| Drift (let go for the mini-turbo) | stick pulled back and steered | D + S / F | Down + Left / Right |
| Use the item; confirm in menus | A | Q | . |
| Title: choose a row / change its value | stick up, down / left, right | E, D / S, F | arrows |
| Back (pause menu, result) | B | W | , |
| Start the race; pause (RESUME / QUIT TO TITLE) | Start | 1 | 2 |
| Select (only for the quit) | Select | 3 | 4 |
| Quit | Start + Select on one pad | 1 + 3, or Esc | 2 + 4, or Esc |

- **Title:** four rows, **PLAYERS** (1 or 2), **BOTS** (0 up to 6 minus the players; 5 by
  default), **LEVEL** (EASY, TOUGH or BRUTAL; EASY by default, dimmed when there are no bots) and **QUIT**. The stick
  moves up and down one row per push, and left and right change the highlighted row's
  value one step per push, both stopping at the ends (no wrap); a diagonal moves the row
  and never a value. Going to 2 players keeps a full field full (4 bots), and back to 1
  fills it again. A line under the rows says what you picked ("A TIME TRIAL: JUST YOU").
  A or Start begins the race as set; A on **QUIT** quits the game at once, and Start never
  quits. B does nothing. A button already held when the game starts must be let go first.
  The title is the GATE PRIX wordmark of the logo (italic race lettering over the
  chequer). Untouched for 3 s, an attract race of 5 bots at TOUGH plays behind it, its two
  split views following two of them, and whoever stops it never finds QUIT highlighted
  (PLAYERS is). The rows stay as set while a visitor reads; only after 30 s untouched do
  they go back to 1 player, 5 bots, EASY for the next one.
- **HOW TO PLAY:** every match begun from the title (not a rematch) opens on a card: the
  goal, a demo of a car steering through the glowing arch and boosting (the real race and
  the AI at BRUTAL), and the controls (the stick: steer, brake, STICK BACK + STEER: DRIFT; the
  L X R / Y B A buttons with A lit; START). Any button on either pad goes on, after its
  first 0.3 s; the stick doesn't. Start + Select still quits and the idle timeout runs.
- **Pause:** Start, on either pad. The stick moves, A picks, B or Start resumes.
- **Idle:** 60 s untouched anywhere (paused too) returns to the title, its rows reset (1
  player, 5 bots, EASY).
- With 1 player either pad drives. The accelerator is automatic.
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
as the machine draws: the title and the attract race, BOTS stepped down and up, the menu
held down onto QUIT and back, Start on QUIT (1 player, 5 EASY bots) and its HOW TO PLAY
card (a press in its first 0.3 s ignored), a 1P race steered by the AI with the stick
mashed on top (pause and resume, the result, a rematch, QUIT TO TITLE with A held), 2
players with 2 BRUTAL bots: the card and the race to the result, a race left alone until
the idle timeout (the rows reset), and finally A on QUIT, which must quit the game. On the way it checks
that all 16 gates come before the final lap and none on it, and that the CIRCUIT CHECK's
freeze lasts about a second while the car drives on. It checks the
match at every step and exits 0 if all held (it stops early, still 0, after SECONDS of game
time). `--shots DIR` saves a screenshot of every screen on the way; `--seed N` fixes the
races.

## Tests

```bash
uv run pytest -q                                            # about 50 s
uvx --from 'ruff==0.15.22' ruff check src tests tools
```

The tests cover the circuit, the track and its gate rows, the car's handling, the race
rules, items, the AI (its levels and the ladder alone on the track, and who beats which
level over many seeds), the road projection and sprite cache, the
match flow (title, attract, countdown, pause, idle, finish, result), the qubit's states
and pictures, the gantry drawn at its exact size through the start, the input (axes,
presses, the armed Start + Select quit, keyboard fallbacks, `--no-keyboard`), the QUIT row
and the HOW TO PLAY card, the demo, the minimap, the renderer drawing every effect from its
caches only, the sound table, and a short scripted session of the real loop.

## Tools

| Tool | Does |
|---|---|
| `tools/snapshot.py OUT` | Every screen to PNGs, through the real match and renderer: the title (and over the attract race), HOW TO PLAY, the countdown's lights, GO, the 1P race, a drift, each item held and used, ITEM FULL, pause, the CHECK and the warp, the storm, the results, and a 2P race, check and results. |
| `tools/road_demo.py` | Drive the camera round the track (`--screenshot` for one frame). |
| `tools/drive_demo.py` | A real race with debug text; `--auto` drives P1 perfectly. |
| `tools/benchmark.py` | Times the road renderer (2 views of 480x540, then 1, 6 cars in each; plain, then with the warp's and the drift, orb, storm, gantry and minimap effects; every run made twice, the first discarded); runs headless, also on the cabinet. |
| `tools/handling.py` | How the track drives, piece by piece, for tuning the handling. |
| `tools/race_stats.py` | Races the bots (`--level`, `--bots`) against a scripted P1 (`--player perfect`, `mediocre` with `--right`, `ai`, `park`) over many seeds: gate rates, finish gaps and P1's margin, bumps, items, turbos and hits. `--ladder` times each level alone on the track. |

## Layout (`src/gate_prix/`)

| Module | Role |
|---|---|
| `circuit.py` | Gates, the exact single-qubit simulation, targets, slots, Hamming distance, QEC. Pure. |
| `track.py` | THE FRIDGE's segments (curves, hills), gate rows, item boxes, roadside sprites, the racing line. Pure. |
| `car.py` | Car physics: auto-acceleration, steering, drifting, curves, off-road, boosts, spin-outs, bumps. Pure. |
| `race.py` | The race: cars, arches, items (shots, clouds), laps, the CIRCUIT CHECK, the storm, places, the finish. Pure. |
| `storm.py` | The final lap's noise storm: one racer's hazards, laid out from its check. Pure. |
| `ai.py` | The one AI: `Skill`, `SKILLS` (EASY / TOUGH / BRUTAL) and the `Driver` for the bots, the attract race, a finished player's autopilot and the HOW TO PLAY demo. Pure. |
| `match.py` | Title (and QUIT), the HOW TO PLAY card, attract, countdown, race, pause, result, idle. Pure. |
| `road.py` | The pseudo-3D projection and road drawing (and the chequered lap line) for one view. |
| `sprites.py` | Every sprite pre-rendered at 24 sizes at start-up (cars tilted and see-through too, sparks, the storm, shots); the backgrounds per view size. |
| `gantry.py` | The start and finish gantry, drawn from its parts at its exact size (its lettering, shadows and lights pre-rendered). |
| `icons.py` | The five item icons, drawn once per size. |
| `bloch.py` | The four states the gates reach from \|0⟩: their colours, the cars' orbs' arrows, the results' Bloch spheres. |
| `wordmark.py` | The title's GATE PRIX lettering, drawn once at start-up. |
| `minimap.py` | The lap from above, drawn once; a dot and a name per car per frame. |
| `tutorial.py` | The HOW TO PLAY card and its demo (a real race, the AI on P1's car). |
| `render.py` | The views, the HUD, the banners and the screens. |
| `audio.py` | Synthesised effects and the engine hum (pitch follows speed); silent without a mixer. |
| `input.py`, `display.py` | Pads and dev keys; the 960x540 surface scaled onto the screen. |
| `game.py`, `main.py` | The fixed 60 Hz loop; the command line. `selftest.py`: the scripted session. |
| `input_test.py`, `config.py` | The input diagnostic; every number, colour and button. |

Rendering is 960x540 (each 2P view 480x540, projecting the road as if 640 wide so the cars
keep their size), scaled exactly 2x by `pygame.SCALED` on the
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
