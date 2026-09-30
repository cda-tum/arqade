# Quantum Towers

A 2-player quantum-state tower-climbing game for the IconicArcade Raspberry Pi 4 cabinet
(Batocera, `pygame` system) — see
`../../docs/superpowers/specs/2026-09-29-quantum-towers-design.md` for the full design.

**Status:** quantum module + BFS minimum-step search + ket-notation rendering (all
pure/tested), and the full two-player game: side-by-side towers, each player's own
qubit/target chain, charges, and the automatic knockback attack, with smooth
procedurally-drawn visuals (anti-aliased climber figure + shaded tower blocks showing
the target state directly on them, not just text readouts). Title/winner screens, idle
timeout, `--input-test`, and simple procedurally-generated sound effects (climb, perfect,
shot — same approach as Quantum Pong's `sound.py`) are wired in. Batocera packaging isn't
built yet.

## The core loop

Each player controls a single qubit, shown as ket notation (`|0>`, `-|1>`, `i|+>`, etc. — see
"Notation" below). Every floor of the tower has a target state, and **both players climb the
exact same shared sequence of targets** (generated once per match), so neither's floors are
randomly easier or harder than the other's. Applying gates transforms your current state. Five
actions, one per button (a 6th button is unmapped): **X**, **Y**, **Z** (Pauli gates), **H**
(Hadamard), **RESET** (back to `|0>`).

**Global phase counts as part of the game state** — a deliberate departure from real quantum
mechanics, where an overall phase is unobservable and two state vectors differing only by one are
considered the *same* physical state. Under that standard convention, Y is entirely redundant here
(`Y` equals `X` then `Z` up to global phase, so any X/Z combo always substitutes for it) and Z does
nothing distinguishable to `|1>` (`Z|1> = -|1>`, identified with `|1>`). Comparing raw state
vectors exactly fixes both: X, Z, and H are all real-valued, so starting from the real `|0>`, only
**Y** can ever introduce an imaginary phase at all — without it, only half of the 16 reachable
states (those with a real overall phase) are within reach, making Y genuinely necessary rather than
a redundant alternative to X/Z. Z now really does do something to `|1>` (`-|1>`, a different
target) while still exactly fixing `|0>` (`Z|0> = |0>`, unchanged). Together X/Y/Z/H/RESET reach
exactly 16 states from `|0>` — the 4 "real" cardinal directions (`|0>`, `|1>`, `|+>`, `|->`) times
the 4 clean phases (`1`, `-1`, `i`, `-i`) — always rendered as a short, recognizable symbol, never
an arbitrary angle to guess at.

(Two gates were tried and removed on the way here: `T`, still defined in `quantum.py` but excluded
from gameplay since it's not Clifford and pushes a state to an arbitrary angle outside that clean
set; and `S`, which made all 6 Bloch-sphere *directions* reachable including `|+i>`/`|-i>` but
didn't fix Y's redundancy, since `Y = iXZ` holds regardless of which other phase gates exist —
exact state comparison turned out to be the actual fix, and doesn't need S.)

Matching the target does **not** advance you by itself — you must push the joystick **up** to
confirm the climb. Confirming while correct advances the floor (and, if that took exactly the
true minimum number of presses — found by an actual search, not a guessed "par" — awards a
charge); confirming while *not* actually on the target locks out that player's input for
`STUN_DURATION` (default 1s) as a penalty. Sitting on a correct-but-unconfirmed state for
`PUSH_UP_HINT_DELAY` seconds (default 2.5s) pops up a "PUSH UP!" hint. At `CHARGES_TO_ATTACK`
(default 3) charges, an automatic attack fires and knocks the opponent down `KNOCKBACK_FLOORS`
(default 3) floors, regenerating fresh targets for the floors they lose (their qubit state itself
is untouched, only position and targets). First to the top of the tower wins.

Each player's tower is drawn as a stack of shaded blocks (the target ket rendered directly on
the block, per the original design) with a simple anti-aliased humanoid figure climbing it —
the bottom visible block is the player's current (cleared) floor, then the current target, then
the next one revealed, then an unrevealed "?" on top.

The button legend at the bottom is shown twice — once per player, in that player's color (left =
P1, right = P2) — since each player has independent button-press state. A held button's box fills
solid and gets a bright border, so a press gives visible feedback even on a frame where the gate
itself does nothing to the target.

## Notation

The bundled pixel font is missing the Unicode ket bracket glyphs (`⟩`/`⟨` silently render as an
invisible box — confirmed by hashing rendered bitmaps against known-missing characters), so
states render with the standard ASCII substitute: `|0>`, `|1>`, `|+>`, `|->` for the 4 reachable
cardinal directions, each optionally prefixed with its global phase — `-` for phase `-1`, `i` for
phase `i`, `-i` for phase `-i` (omitted entirely for phase `1`) — e.g. `-|1>`, `i|+>`, `-i|0>`.
`|+i>`/`|-i>` are still recognized symbols in `notation.py` (for the direction itself, not a
phase) but are currently unreachable, since nothing in the gate set bridges to them (see "The core
loop"). The general `magnitude|0> + magnitude|1>@angle` fallback form (e.g. `0.71|0> +
0.71|1>@45°`) still exists for the excluded `T` gate's sake but is unreachable in normal play —
kept as a harmless defensive fallback rather than ripped out.

## Setup (dev machine)

Requires [uv](https://docs.astral.sh/uv/).

```bash
cd games/quantum-towers
uv sync
```

## Run

```bash
uv run python -m quantum_towers.main                    # windowed, keyboard/joystick
uv run python -m quantum_towers.main --fullscreen        # fullscreen at desktop res
uv run python -m quantum_towers.main --fps               # force the FPS overlay on
uv run python -m quantum_towers.main --window-size 1280x720
```

Press **F3** in-game to toggle the FPS overlay at runtime.

### Input test mode

The cabinet's exact button indices are unknown. Run this on the real hardware (or with a
controller plugged into your dev machine) and press everything to see live index values:

```bash
uv run python -m quantum_towers.main --input-test
```

Update the placeholder indices in `src/quantum_towers/config.py` (`INPUT_CONFIG`) with what you
observe. That's the single place all button mappings live.

### Keyboard fallback (dev only)

| Action | P1 | P2 |
|---|---|---|
| X / Y / Z | Q / W / E | Numpad 4 / 5 / 6 |
| H / RESET | D / F | Numpad 7 / 9 |
| Push up (confirm climb) | Up arrow | Numpad 8 |
| Quit | Esc (either player) | Esc (either player) |

On the cabinet, quit is Start+Select held together on either controller.

P1's dev keys deliberately avoid L/X/R/B/Y/A: the real cabinet's P1 encoder emits a keyboard
keystroke matching each button's own printed letter *in addition to* its joystick signal, and a
dev fallback key that collided with one of those would double-fire two actions from a single real
button press (this is exactly what caused the first real-hardware mapping bug — see
`config.py`).

## Tests

```bash
uv run pytest
```

Covers `quantum.py` (gate matrices, global-phase normalization/equality), `search.py` (the BFS
minimum-steps search, including a case where the true shortest path is shorter than however the
target was generated), `targets.py` (random-walk generation), `player.py` (floor-advance/charge
logic and knockback), `notation.py` (ket rendering, including the general fallback form), and
`sound.py` (tone-sample generation) — this is most of the game's actual complexity, and none of
it depends on pygame. The pygame game
loop and screen/visuals rendering (`main.py`, `visuals.py`) are integration glue — verified by
running it, and by a large (20k-step) scripted simulation exercising real attack/knockback
sequences and rendering across many real game states without a crash.

## Tuning

Tower height, the BFS search depth cap, charges-to-attack, knockback floors, and all colors live
in `src/quantum_towers/config.py` alongside `INPUT_CONFIG`. Target-generation walk length lives
in `src/quantum_towers/targets.py`.

## Fonts

Same bundled Press Start 2P pixel font as Quantum Pong (own copy at
`src/quantum_towers/assets/fonts/`, OFL-licensed — see `OFL.txt` there), for the same
consistency-across-hosts reason. `--input-test` uses the system font instead, same rationale as
Quantum Pong: its diagnostic text is long and variable-length.
