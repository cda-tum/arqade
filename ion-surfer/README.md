# Ion Surfer

A 1–2 player ion-trap arcade game for the IconicArcade Raspberry Pi 4 cabinet (Batocera,
`pygame` system), packaged the same way as Quantum Pong and Quantum Towers. You shape the
trap potential with the electrodes on the floor to keep your ion on screen while the
camera scrolls ever faster.

**Status:** full game (solo, 2-player versus, 2-player co-op, seeded levels, records),
a separate quantum sandbox ROM (**Ion Trap Sandbox**, 1–4 ions),
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

## Sandbox (Ion Trap Sandbox)

The sandbox is its own entry in the Batocera menu, **Ion Trap Sandbox**
(`ion_surfer_sandbox.pygame`). It runs the same package started with `--sandbox`,
so it opens straight into the sandbox, and QUIT in its pause menu exits. The arcade
game's own menu only has the three arcade modes. Locally, run it with
`uv run python -m ion_surfer.main --sandbox`.

It is a fixed screen without scrolling. Both players shape one shared potential,
like in co-op: blue's cursor starts on the left, red's on the right, matching the
joysticks. Instead of the classical ball, the ion's motion is simulated quantum
mechanically:

- **1 ion:** the full wave packet is simulated on a 400-point grid by solving the 1D
  Schrödinger equation (Crank–Nicolson). The packet is drawn on the potential, with
  the colour showing its phase (colour stripes = momentum).
- **2–4 ions (Coulomb crystal):** the game finds the crystal's equilibrium and its
  normal modes (COM, stretch, egyptian, ...). Each mode gets its own simulated wave
  packet. It feels the exact potential along that mode's direction, including trap
  anharmonicity and the Coulomb repulsion. Only the coupling between modes is left
  out. A mode where one ion dominates, for example when the ions sit in separate
  wells, is labelled `ION k`. Every ion is drawn as its position distribution.

The cockpit along the top shows this for every mode:

- **MOTIONAL STATE:** Fock populations P(n) in the mode's harmonic basis. The pink bar
  is everything above the last level.
- **PHASE SPACE:** the Gaussian blob (covariance ellipse), which shows displacement,
  squeezing and the phase it rotates through, plus its recent trail.
- **SCOPE:** displacement ⟨x⟩ and width over the last 6 s. Breathing shows up as the
  width oscillating at twice the mode frequency.
- **READOUT:** frequency, ⟨n⟩ (computed exactly from the moments), |α|, phase and
  squeezing in dB.

How to produce the effects:
- **Displacement:** a laser kick, or moving the well suddenly.
- **Squeezing and breathing:** tightening or loosening the well suddenly. A slow change
  is adiabatic and stays in the ground state.
- **Cooling:** red holds L to damp everything back to the ground state quickly. Red R
  toggles passive cooling, a slow steady drain; it is off by default.
- **COM vs stretch:** P1's kick pushes the leftmost ion right and P2's pushes the
  rightmost ion left. So one kick excites COM and stretch together, while both players
  kicking at the same moment gives an almost pure stretch.

Performance, measured on the dev machine only (not on the cabinet yet): one ion adds
about 1 ms per frame on top of the normal world drawing, and four ions about 2 ms.
Holding a voltage costs a little more, because the mode potentials are then
re-sampled every frame. If the Pi 4 struggles with four ions, lower `MAX_IONS` in
`sandbox.py`.

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
| Select electrode | Stick left/right or Y/A / ← → | Stick left/right or Y/A / D G |
| Voltage | Stick up/down or X/B / ↑ ↓ | Stick up/down or X/B / R F |
| Confirm | L or R / LCtrl, Space, Enter | L or R / A |
| Start | Start / 1 | Start / 2 |
| Sandbox: laser kick | Start / 1 | Start / 2 |
| Sandbox: L | remove ion (key Q) | cool while held (key C) |
| Sandbox: R | add ion (key E) | passive cooling on/off (key V) |

- **Select** (or Esc) opens the pause menu.
- **Quit:** hold Start and Select together on either controller, or choose QUIT in the
  main menu.
- The keyboard keys are a dev fallback only. The cabinet loader runs the game with `--no-keyboard`: Batocera also turns P1's pad into keystrokes (arrow keys, numpad, letters, Enter/Space — see `../AGENTS.md`), which would otherwise let P1's stick or buttons drive P2 or fire two actions at once.

Records (solo and co-op) are saved to `~/.ion_surfer_scores.json`. On Batocera that is
`/userdata/system/`, so a redeploy doesn't reset them.

## Deploy to the cabinet

```bash
./deploy_batocera.sh                  # defaults to root@batocera.local
./deploy_batocera.sh root@10.42.0.100 # if .local resolution isn't working
```

This works the same way as the quantum games. The package goes to
`/userdata/games/ion_surfer/`. Two small loaders go to `/userdata/roms/pygame/`:
`ion_surfer.pygame` runs the arcade game fullscreen, and `ion_surfer_sandbox.pygame`
runs the sandbox. After the first deploy of the sandbox loader, rescan the pygame
system (or restart EmulationStation) so the new entry shows up. Its name and icon come
from `../batocera/gamelist.xml` and `../batocera/icons/ion_surfer_sandbox-image.png`
(see "Game names and per-game icons" in `../AGENTS.md`).

## Tests

```bash
uv run pytest
```

The tests cover the pure input functions, `Pad`'s hold/press/auto-repeat logic, the
config (every key name exists, and start/select aren't action buttons),
`display.py`'s scaling math, and the sandbox physics:
- `quantum.py`: norm conservation, a stationary ground state, coherent-state
  oscillation, squeezed-state breathing with even-only Fock populations, kicks and
  cooling.
- `crystal.py`: the Coulomb spacing, COM at ω and stretch at √3·ω, three-ion mode
  ratios, kicks that excite only COM vs COM and stretch, and following a moving trap.

The game loop and rendering (`game.py`, `sandbox.py`) are integration glue. They are
verified by running the game.

## Tuning

`src/ion_surfer/config.py` holds the input mapping. Physics and scroll-speed constants
are in the TUNING block at the top of `src/ion_surfer/game.py`, and the sandbox
constants are in the TUNING block of `src/ion_surfer/sandbox.py`: ħ/m (sets the packet
width), potential coupling (sets the trap frequency), Coulomb strength (sets the ion
spacing), kick strength, cooling rate and `MAX_IONS`.

## Fonts

The game bundles Bungee (titles/HUD) and Rubik Medium (body text) at
`src/ion_surfer/assets/fonts/`. Both are OFL-licensed, see `OFL-Bungee.txt` and
`OFL-Rubik.txt` there. Rubik Medium is a static instance of Google Fonts' variable
`Rubik[wght].ttf`, set to weight 500. If a font is missing, the game falls back to
pygame's default font.
