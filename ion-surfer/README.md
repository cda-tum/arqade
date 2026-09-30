# Ion Surfer

A 1–2 player ion-trap arcade game for the IconicArcade Raspberry Pi 4 cabinet (Batocera,
`pygame` system), packaged the same way as Quantum Pong and Quantum Towers. You shape the
trap potential with the electrodes on the floor to keep your ion on screen while the
camera scrolls ever faster.

**Status:** full game (solo, 2-player versus, 2-player co-op, seeded levels, records),
`--input-test`, and a Batocera deploy script. Button/axis indices in `INPUT_CONFIG` use
the same placeholders as the quantum games and still need an `--input-test` run on the
real cabinet.

## Gameplay

Each player controls a cursor over the electrode strip. Left/right selects an
electrode, and up/down raises or lowers its voltage. That reshapes the potential curve
your ion rolls on. Photons give bonus points. Watch out for the hazards:

- Defects and energy caps deform the potential.
- Blocks are solid obstacles.
- Lasers push the ion up or down.
- Stray ions repel yours (Coulomb force).
- Loss holes swallow the ion.

Your score is the distance transported plus bonuses.

- **Versus:** each player has their own curve and ion.
- **Co-op:** both players shape one shared curve for one team ion.

Levels are generated from a seed. You can enter a seed in the menu to replay a level.

## Setup (dev machine)

Requires [uv](https://docs.astral.sh/uv/).

```bash
cd ion-surfer
uv sync
```

## Run

```bash
uv run python -m ion_surfer.main                    # windowed, keyboard/joystick
uv run python -m ion_surfer.main --fullscreen        # fullscreen at desktop res
uv run python -m ion_surfer.main --fps               # force the FPS overlay on
uv run python -m ion_surfer.main --window-size 1800x960
```

Press **F3** in-game to toggle the FPS overlay at runtime. The game renders at 1200×640
and is scaled and letterboxed onto the real screen.

### Input test mode

```bash
uv run python -m ion_surfer.main --input-test
```

This mode shows live joystick axes, buttons and hats. Esc quits. Update the placeholder
indices in `src/ion_surfer/config.py` (`INPUT_CONFIG`) with what you observe. All button
and axis mappings live there.

### Controls

| | P1 (blue) | P2 (red) |
|---|---|---|
| Select electrode | Stick left/right / ← → | Stick left/right / D G |
| Voltage | Stick up/down / ↑ ↓ | Stick up/down / R F |
| Confirm | Any of the 6 buttons / LCtrl, Space, Enter | Any of the 6 buttons / A |
| Start | Start / 1 | Start / 2 |

- **Select** (or Esc) opens the pause menu.
- **Quit:** hold Start and Select together on either controller, or choose QUIT in the
  main menu.

Records (solo and co-op) are saved to `~/.ion_surfer_scores.json`. On Batocera that is
`/userdata/system/`, so a redeploy doesn't reset them.

## Deploy to the cabinet

```bash
./deploy_batocera.sh                  # defaults to root@batocera.local
./deploy_batocera.sh root@10.42.0.100 # if .local resolution isn't working
```

This works the same way as the quantum games. The package goes to
`/userdata/games/ion_surfer/`, and a small loader `/userdata/roms/pygame/ion_surfer.pygame`
runs it fullscreen. After deploying, restart EmulationStation or rescan the pygame
system.

## Tests

```bash
uv run pytest
```

The tests cover the pure input functions, `Pad`'s hold/press/auto-repeat logic, the
config (every key name exists, and start/select aren't action buttons), and
`display.py`'s scaling math. Physics and rendering (`game.py`) are integration glue.
They are verified by running the game.

## Tuning

`src/ion_surfer/config.py` holds the input mapping. Physics and scroll-speed constants
are in the TUNING block at the top of `src/ion_surfer/game.py`.

## Fonts

The game bundles Bungee (titles/HUD) and Rubik Medium (body text) at
`src/ion_surfer/assets/fonts/`. Both are OFL-licensed, see `OFL-Bungee.txt` and
`OFL-Rubik.txt` there. Rubik Medium is a static instance of Google Fonts' variable
`Rubik[wght].ttf`, set to weight 500. If a font is missing, the game falls back to
pygame's default font.
