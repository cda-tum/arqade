# Quantum Pong

A 2-player Pong variant for the IconicArcade Raspberry Pi 4 cabinet (Batocera,
`pygame` system). Gates named after quantum operations (H / X / Z / SWAP) act
as deterministic power-ups: no probability, no measurement — see
`../../docs/superpowers/specs/2026-09-28-quantum-pong-design.md` for the
original design spec and its revision note on the mechanics change.

**Status:** classic 2-player Pong with joystick/keyboard input and an
input-test mode, multi-ball gate mechanics (H/X/Z/SWAP, capped at 4 balls on
screen, each gate announced before it appears, spawning faster as a match goes
on), a title/attract screen with a legend and a PLAY / QUIT menu, a HOW TO
PLAY card before every match, a winner screen, a pause menu (Start), a 60s
idle timeout back to the title, simple procedurally-generated beep sounds, and
a Batocera packaging script. Button/axis indices in `INPUT_CONFIG` are still
placeholders pending an `--input-test` run on the real cabinet.

## Gate mechanics

Gates spawn randomly in the middle of the field (away from the paddles) and
never overlap: each keeps at least `GATE_MIN_GAP` px of clear space to every
other gate. Placement uses best-candidate sampling — `GATE_SPAWN_CANDIDATES`
random valid spots are tried and the one farthest from the existing gates
wins — so gates stay random but spread out, as if lightly repelling each
other. Spawn kind is weighted via `GATE_WEIGHTS` in config — H spawns twice as
often as X/Z/SWAP by default. At most a few gates on screen at once; they
never vanish on their own. Touching one with any ball applies it and consumes
the gate.

**Announced first.** Every gate shows up `GATE_WARNING_SECONDS` (1.5 s) before
it appears, as a white dashed outline (marching round) with its letter, at
exactly the spot and of exactly the kind it will be, with a soft tick. Balls
pass straight through an announced gate; then it turns solid and works as
normal. No ball is ever hit by a gate that pops in out of nowhere.

**The field fills up over a match.** The gap between spawns shrinks from
`GATE_SPAWN_INTERVAL` (2.5 s) to `GATE_SPAWN_INTERVAL_MIN` (1.25 s) over
`GATE_SPAWN_RAMP_SECONDS` (90 s) of play, and the cap on gates on the field
(announced ones count) grows by one every `GATE_CAP_STEP_SECONDS` (45 s), from
`MAX_GATES_ON_SCREEN` (3) up to `MAX_GATES_ON_SCREEN_LATE` (5). Time paused
doesn't count. Since gates only go when a ball uses them, the cap is what
really sets the pace; a long, close match ends noticeably busier than it
started.

What each gate does:

- **H** — splits the ball into two: one keeps going the way it was, the other
  reverses horizontal direction and heads to the other paddle. No-op past the
  4-ball cap (the gate stays, in case the ball count drops again).
- **X** — bounces the ball as if off an invisible vertical wall (reverses
  horizontal direction).
- **Z** — bounces the ball as if off an invisible horizontal wall (reverses
  vertical direction).
- **SWAP** — teleports the ball to the mirrored spot across the field and
  reverses horizontal momentum, so it keeps moving deeper into that side.

Every ball on screen is independent: each one is checked against the paddles
and can be caught or score on its own. Paddles have a small catch-range
forgiveness (`PADDLE_CATCH_GRACE` in config) so a paddle moved into place at
the last instant still counts, rather than needing pixel-perfect timing.

## Setup (dev machine)

Requires [uv](https://docs.astral.sh/uv/).

```bash
cd games/quantum-pong
uv sync
```

## Run

```bash
uv run python -m quantum_pong.main                    # windowed, keyboard/joystick
uv run python -m quantum_pong.main --fullscreen        # fullscreen at desktop res
uv run python -m quantum_pong.main --fps               # force the FPS overlay on
uv run python -m quantum_pong.main --window-size 1280x720
```

Press **F3** in-game to toggle the FPS overlay at runtime.

### Input test mode

The cabinet's exact joystick/button indices are unknown. Run this on the real
hardware (or with a controller plugged into your dev machine) and press
everything to see live index/axis values:

```bash
uv run python -m quantum_pong.main --input-test
```

Update the placeholder indices in `src/quantum_pong/config.py` (`INPUT_CONFIG`)
with what you observe. That's the single place all button/axis mappings live.

### Title, HOW TO PLAY, match

The title shows the gate legend and a two-row menu, **PLAY** / **QUIT**. The
stick moves the selection and A picks it: QUIT ends the game and hands the
cabinet back to its game list (EmulationStation, or the launcher's menu on a
PC), the same clean exit as Start+Select. **Start always starts a match**,
whichever row is selected; B does nothing on the title.

Every match started from the title opens with a **HOW TO PLAY** card
(`tutorial.py`): the goal in three lines, a looping demo played by the game's
own rules and sprites (a gate is announced, appears, and a served ball runs
into it: H, X, Z and SWAP in turn, captioned), and the controls (stick: move
your paddle, START: pause). Any button on either pad dismisses it, except in
its first 0.3 s, so the press that left the title can't skip it unseen; the
stick doesn't. Start+Select still quits from it, and after 60 s untouched it
goes back to the title. The press that dismisses it can't pause the match:
the match seeds its button edges with whatever is held when it begins.

### Keyboard fallback (dev only)

| Action | P1 | P2 |
|---|---|---|
| Move | W / S | Up / Down |
| Pause / resume | P (either player) | P (either player) |
| Pick a menu item (A) | Enter | Enter |
| Start from the title (Start) | Space or P | Space or P |
| Dismiss HOW TO PLAY | any key | any key |
| Quit | Esc (either player) | Esc (either player) |

On the cabinet, quit is Start+Select held together on either controller, or
QUIT on the title. Start or A (Enter/Space on keyboard) also leaves the winner
screen.

### Pausing

Start on either pad pauses a match (the cabinet-wide convention, see
"Pausing" in `../AGENTS.md`). Everything freezes — balls, paddles, gate
spawns, the flashes — and a menu opens over the field: the stick moves
between **RESUME** and **QUIT TO TITLE**, A picks, and Start or B resumes.
QUIT TO TITLE ends the match and goes back to this game's own title screen;
Start+Select still quits the game at once, paused or not. The 60s idle
timeout keeps counting while paused (using the menu resets it), so a match
left paused on an unattended cabinet still drops back to the title.

The cabinet loader runs the game with `--no-keyboard`: Batocera also turns P1's pad into
keystrokes (arrow keys, numpad, letters, Enter/Space — see `../AGENTS.md`), which would
otherwise let P1's stick or buttons drive P2 or fire two actions at once.

## Tests

```bash
uv run pytest
```

Covers `gates.py` (spawning, the announcement before each gate appears, the
spawn-rate and cap ramp, deterministic H-X-Z-SWAP effects, ball-cap
enforcement), the paddle-line/catch-or-score logic and classic physics in
`pong.py`, the pure input-decision functions in `input.py`, the pure
tone-generation math in `sound.py`, the idle-blink timing in `screens.py`, the
pause menu's state machine in `pause.py`, the title menu's in `title.py`
(Start always starts, A on QUIT quits, B doesn't), the HOW TO PLAY card's
dismissal rules and demo scenes in `tutorial.py`, the screen flow in `main()`
(title -> HOW TO PLAY -> match -> winner -> title, with the screens stubbed),
and `display.py`'s scaling math. The pygame game loop itself, screen
rendering, and `input_test.py` are integration glue — verified by running it,
not unit tested.

## Sounds

All generated at startup as sine beeps (`sound.py`), silent if there is no
mixer: paddle bounce, score, a gate used, a gate announced (a soft tick), the
match won, and menu move / confirm (title menu, pause menu, leaving HOW TO
PLAY).

## Tuning

All tuning constants (paddle/ball speed, sizes, colors, winning score, gate
timing, the ball cap) live in `src/quantum_pong/config.py` alongside
`INPUT_CONFIG`.

## Performance

Fullscreen mode (`--fullscreen`, what the cabinet actually runs) uses
pygame's `SCALED` display mode: pygame/SDL does the internal-resolution
upscale itself, hardware-accelerated where the platform supports it, instead
of a manual `pygame.transform.scale()` blit every frame (a real, sizeable CPU
cost on a Pi 4 upscaling ~130K to ~2M+ pixels in software). Windowed dev mode
keeps the old manual-scale path since it needs a specific initial window
size that `SCALED` has no API for in pygame 2.5.2 — not worth it locally
where performance isn't the concern anyway. Gate labels (4 possible strings)
and the score text are pre-rendered/cached rather than re-rasterized every
frame.

## Fonts

All in-game text (title, legend, score, winner screen, pause menu, gate
labels) uses the bundled pixel font
`src/quantum_pong/assets/fonts/PressStart2P-Regular.ttf`
("Press Start 2P" by The Press Start 2P Project Authors, SIL Open Font
License 1.1 — see `OFL.txt` in that folder) rather than the OS's default
font, so text renders consistently instead of depending on whatever's
installed on the host. `--input-test` is the one screen that still uses the
system font, since its diagnostic text is long and variable-length (joystick
names, key lists) and needs a denser font to avoid overflowing.
