# Error Invaders

Retro meets quantum error correction: a 1–2 player Space Invaders variant for the
IconicArcade Raspberry Pi 4 cabinet (Batocera, `pygame` system). A pygame port of the
browser version, packaged the same way as Quantum Pong and Quantum Towers.

**Status:** full game (1 or 2 players, EASY/HARD mode, power-ups, lattice surgery,
high scores), in-game input-test mode, and a Batocera deploy script. Button/axis
indices in `INPUT_CONFIG` use the same placeholders as the quantum games and still need
an `--input-test` run on the real cabinet.

## Gameplay

Each invader is an X, Z or Y error. Only a shot of the matching color corrects it. A Y
error equals X·Z, so you can hit it with red and then blue, or with purple directly. In
**HARD** mode a wrong color multiplies the error instead (Pauli algebra: any two colors
make the third). P1 flies the 3-color *color code* triangle, and P2 the faster-firing
2-color *surface patch*. Shoot the Cosmic Ray (wave packet at the top) to drop power-ups:
transversal gate (spread shot), magic state (bomb), noise bias (errors correlate into
chains you can pop in one hit) and, in 2-player mode, lattice surgery (both players
merge into one ship: P1 steers, P2 aims).

## Setup (dev machine)

Requires [uv](https://docs.astral.sh/uv/).

```bash
cd error-invaders
uv sync
```

## Run

```bash
uv run python -m error_invaders.main                    # windowed, keyboard/joystick
uv run python -m error_invaders.main --fullscreen        # fullscreen at desktop res
uv run python -m error_invaders.main --fps               # force the FPS overlay on
uv run python -m error_invaders.main --window-size 1280x960
```

Press **F3** in-game to toggle the FPS overlay at runtime. The game renders at 960×720
(4:3). On a 16:9 screen it is scaled up with black bars at the sides.

### Input test mode

```bash
uv run python -m error_invaders.main --input-test
```

This mode shows live joystick axes, hats and buttons, and the actions each player
currently triggers. You can also open it from the title screen with **F1**. Esc (or
holding Select for 2 s) goes back to the title. Update the placeholder indices in
`src/error_invaders/config.py` (`INPUT_CONFIG`) with what you observe. All button and
axis mappings live there.

### Controls

| | P1 | P2 |
|---|---|---|
| Move | Stick / WASD | Stick / arrow keys |
| Fire / confirm | Button 0 / Y (or Z) | Button 0 / `,` |
| Switch color / back | Button 1, 2 / X | Button 1, 2 / `.` |

- **Start** (or Enter) confirms in menus. **Select** (or Esc) goes back to the menu during
  play.
- **Quit:** hold Start and Select together on either controller. You can also hold Select
  (or press Esc) for 2 s on the first menu page.
- For a keyboard-emulating encoder with MAME defaults, set `KEY_PRESET = "mame"` in
  `config.py`. P1 is then arrows + LCtrl/LAlt, and P2 is R/F/D/G + A/S.

High scores (one per mode) are saved to `~/.error_invaders_hiscores.json`. On Batocera
that is `/userdata/system/`, so a redeploy doesn't reset them.

## Deploy to the cabinet

```bash
./deploy_batocera.sh                  # defaults to root@batocera.local
./deploy_batocera.sh root@10.42.0.100 # if .local resolution isn't working
```

This works the same way as the quantum games. The package goes to
`/userdata/games/error_invaders/`, and a small loader
`/userdata/roms/pygame/error_invaders.pygame` runs it fullscreen. After deploying,
restart EmulationStation or rescan the pygame system. If you copied the old
`error_invaders_pygame/` folder into `/userdata/roms/pygame/` before, delete it there so
the game doesn't show up twice.

## Tests

```bash
uv run pytest
```

The tests cover the pure input-decision functions, the config (every key name exists
and fire/swap/start/select don't collide), the Pauli table used in HARD mode, and
`display.py`'s scaling math. The game loop and rendering (`game.py`) are integration
glue. They are verified by running the game.

## Tuning

`src/error_invaders/config.py` holds the input mapping, the effect toggles and the
volume. Set `GLOW = False` (additive glow) and/or `SHOW_SCANLINES = False` (CRT overlay)
if the cabinet drops frames. Gameplay constants (formation size, zones, colors) are at
the top of `src/error_invaders/game.py`.

## Fonts

The game bundles the Press Start 2P pixel font, the same one the quantum games use, at
`src/error_invaders/assets/fonts/`. It is OFL-licensed, see `OFL.txt` there.
