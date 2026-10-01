# Pauli Invaders

Retro meets quantum error correction: a 1–2 player Space Invaders variant for the
IconicArcade Raspberry Pi 4 cabinet (Batocera, `pygame` system). A pygame port of the
browser version, packaged the same way as Quantum Pong and Quantum Towers.

**Status:** full game (1 or 2 players, EASY/HARD/BOSS RUSH mode, boss fights,
power-ups, lattice surgery, high scores), in-game input-test mode, and a Batocera deploy script. Fire/swap use the
button numbers confirmed on the cabinet. Start/Select (8/9) are still unconfirmed.

The game used to be called *Error Invaders*. Only the displayed name changed: the
folder, the Python package `error_invaders`, the ROM file `error_invaders.pygame`
and the high-score file still use the old name, so deploys and saved scores keep
working.

## Gameplay

Each invader is an X, Z or Y error. Only a shot of the matching color corrects it. A Y
error equals X·Z, so you can hit it with red and then blue, or with purple directly. In
**HARD** mode a wrong color multiplies the error instead (Pauli algebra: any two colors
make the third). P1 flies the 3-color *color code* triangle, and P2 the faster-firing
2-color *surface patch*. Shoot the Cosmic Ray (wave packet at the top) to drop power-ups:
transversal gate (spread shot), magic state (bomb), noise bias (errors correlate into
chains you can pop in one hit) and, in 2-player mode, lattice surgery (both players
merge into one ship: P1 steers, P2 aims).

### Bosses

Every third wave is a boss fight instead of a formation. **BOSS RUSH** (the third mode
in the menu, with EASY color rules) skips the formations and runs the bosses back to
back, so they are quick to try out. They come in this order, and after the fifth one
the cycle repeats, each boss tougher than before:

| Boss | Idea | How to beat it |
|---|---|---|
| LOGICAL ERROR | An error chain that crawls down like Centipede. Some segments fire. | Shoot segments in their color, which splits the chain. If a head reaches the threshold, you lose a life. |
| WAVE PACKET | Spread out (wide), it can't be hit and drops bullets from all along its width. | Wait for "MEASURED!". Collapsed, it can be hit in its color, but it darts around (sharp in x, wild in p). A bomb collapses it right away. |
| SYNDROME | A check lattice. The errors are hidden, only the checks around them light up. | Shoot the qubit (dot) between two lit checks, in their color. A single lit check on the left or right edge means the boundary qubit. A faint hint appears after a while. |
| CLIFFORD CORE | Immune to every Pauli shot (its shield blinks). Fires neutral bullet-hell patterns, plus now and then a colored curtain. | A colored shot that meets a ship of the same color is absorbed. Five absorbed shots charge a magic-state bomb (pips above the ship), and only that hurts the core. |
| BELL PAIR | Two entangled halves that fire mirrored shots and spawn mirrored minion pairs. | A hit half heals unless the other one is hit within the window (0.5 s with two players, 1.2 s alone). |

Most bosses also spawn minions: single errors that waver down and shoot, and burst
into a spread when they reach the threshold. During boss fights there is no Cosmic
Ray. Instead minions occasionally drop capsules, and every boss drops two when it is
beaten. The code lives in `src/error_invaders/bosses.py`.

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
| Fire / confirm | A / Y (or Z) | A / `,` |
| Switch color / back | B / X | B / `.` |

- **Start** (or Enter) confirms in menus. **Select** (or Esc) goes back a menu page.
- **Pause:** press **Start** (or P / Esc) during play, on either controller. Everything
  freezes. In the pause menu the stick picks RESUME or QUIT TO TITLE, A (fire) chooses,
  and Start or B resumes. Quitting to the title doesn't record a score.
- **Quit:** hold Start and Select together on either controller. You can also hold Select
  (or press Esc) for 2 s on the first menu page.
- The keyboard keys are a dev fallback only. On the cabinet the loader passes
  `--no-keyboard`, because Batocera turns P1's pad into keystrokes as well (see
  `../AGENTS.md`), which made P1 move P2 and one button fire two actions.
- For a keyboard-emulating encoder with MAME defaults, set `KEY_PRESET = "mame"` in
  `config.py`. P1 is then arrows + LCtrl/LAlt, and P2 is R/F/D/G + A/S.

High scores (one per mode, BOSS RUSH included) are saved to `~/.error_invaders_hiscores.json`. On Batocera
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
and fire/swap/start/select don't collide), the Pauli table used in HARD mode,
`display.py`'s scaling math, and the bosses' pure logic: which wave gets which boss,
the shared color rules, that every Syndrome error is uniquely decodable, and that
splitting the Centipede chain leaves every segment where it was. The game loop and rendering (`game.py`) are integration
glue. They are verified by running the game.

## Tuning

`src/error_invaders/config.py` holds the input mapping, the effect toggles and the
volume. Set `GLOW = False` (additive glow) and/or `SHOW_SCANLINES = False` (CRT overlay)
if the cabinet drops frames. Gameplay constants (formation size, zones, colors) are at
the top of `src/error_invaders/game.py`.

## Fonts

The game bundles the Press Start 2P pixel font, the same one the quantum games use, at
`src/error_invaders/assets/fonts/`. It is OFL-licensed, see `OFL.txt` there.
