# Gate Drop: design

A two-player versus puzzle game for the ARQADE cabinet, styled after Dr.
Mario. Each player's board is a small quantum circuit with a few Pauli errors
already sitting on its wires. Gate pills fall onto the wires, and gates that
cancel each other vanish. **The first player to clear every error on their
board wins the round.**

- **Players:** 2, versus, or 1, Dr. Mario style (see Revision 2).
- **Target:** the Batocera cabinet described in `../../../AGENTS.md` (Pi 4,
  1920x1080, two 6-button pads, Python 3.11, pygame 2.5.2).
- **Look:** chunky, colourful SNES-era pixel art, all procedural. No neon.
- **Name:** "Gate Drop" is a working title. The menu name lives only in
  `gamelist.xml`, so renaming it later costs nothing.

## Revision 2: menus and single player

Requested after the first look. Where this disagrees with the sections below,
this revision wins.

- **Title:** the stick picks **1 PLAYER** or **2 PLAYERS**, and A or Start
  goes on to the setup screen.
- **Setup screen:** every player picks a **LEVEL** from 1 to 10 and a
  **SPEED** of LOW, MED or HI.
  - The stick moves between the two rows and changes the values. A is
    ready, B un-readies, and B while not ready goes back to the title.
  - With two players each sets their own, as a handicap, side by side. The
    countdown starts once everyone is ready.
  - The choices are remembered for the next game.
- **Level n** has `2n + 2` errors, from 4 up to 22, still in the bottom 8
  rows. Players on the same level get the same layout. In versus the level
  stays fixed for the whole match, instead of growing every round.
- **Speed** sets the starting fall interval and its floor: LOW 0.9 s to
  0.3 s, MED 0.65 s to 0.22 s, HI 0.42 s to 0.15 s. It speeds up 10% every
  30 s, as before.
- **Single player, Dr. Mario style:**
  - **Controls:** one centred board, and either pad plays it.
  - **Levels:** clearing every error is a level clear. The next level
    starts with more errors, and after level 10 it repeats level 10 with
    fresh layouts.
  - **Scoring:** each error cleared scores `100 x speed (LOW 1, MED 2, HI 3)
    x 2^(chain step - 1)`, with the chain multiplier capped at 8. A level
    clear adds `500 x level x speed`.
  - **Game over:** topping out ends the game. A score that makes the top 10
    is entered with 3 initials: the stick changes the letter and moves
    between them, and A confirms. The table is then shown.
  - **High scores:** they are kept outside the package folder
    (`~/.gate_drop_scores.json`), so a redeploy doesn't wipe them. Idling on
    the initials screen saves what has been entered so far.

## 1. Rules

### The board

- Each board has **6 wires** (columns) and **14 rows**. A column is one
  qubit wire, and the gates stacked on it are that qubit's circuit.
- Every cell holds nothing, a **gate**, an **error**, or one half of a **CNOT**.
- **Gate colours:** X red, Z blue, Y purple (as in Error Invaders), H yellow.
  CNOTs are steel grey, with the control `●` on one half and the target `⊕`
  on the other.

### Pills

Every piece is a 2x1 pill, in one of two kinds:

- **Gate pill:** two single-qubit gates, each drawn from H, X, Y and Z with
  equal weight. It falls as one piece and rotates through four
  orientations, as in Dr. Mario. After it locks, the two halves are
  independent gates: a half whose support is cleared away falls on its own.
- **CNOT pill:** one CNOT, always lying across two neighbouring wires,
  because a 2-qubit gate acts on both at the same time step. Rotating it
  swaps which side has the control and which the target. It is **rigid**: it
  lands as soon as either half touches something, both halves always stay at
  the same height, and when its support goes it falls as one piece. A gap
  left under the higher side is just an idle stretch of wire.
- **Rotating:** as in Dr. Mario, a gate pill pivots on its lower-left half.
  If the rotated pill would overlap something or a wall, it tries one cell to
  the left (a wall kick), and otherwise doesn't rotate.
- **Mix:** 15% of pills are CNOTs. Every pill spawns lying flat over the two
  middle wires, and the next pill is shown in a preview.

### Controls (in game)

| Action | Cabinet |
|---|---|
| Move left / right | stick left / right (auto-repeat) |
| Soft drop | stick down |
| Rotate clockwise / counter-clockwise | A / B |
| Quit | Start + Select on one pad |

There is no pause, as in the other versus games. Menus follow the cabinet's
button convention: Start or A starts and confirms, B goes back.

### Gravity

- The falling pill drops one row every **0.8 s**, speeding up by 10% every
  30 s of a round, to a floor of **0.25 s**. Soft drop moves it one row
  every 0.05 s.
- A pill locks on the gravity tick where it can't move down.
- After a lock, and after every clear, everything unsupported falls:
  loose gates and CNOT pills fall, and errors never do (they are anchored,
  like Dr. Mario's viruses). This settling is animated a row at a time.

### What cancels

Cancellation happens **only along a wire**, never across wires: gates on
different qubits don't cancel. Each wire is read as its sequence of items
from bottom to top. **Gaps are skipped**, because an empty cell is the
identity, so `X`, gap, `X` still cancels. A CNOT half is an item too, and
because there is no commuting, nothing cancels across it.

| Pattern on a wire | Result |
|---|---|
| Two identical gates in a row: `X X`, `Y Y`, `Z Z`, `H H` | both vanish |
| A gate in a row with an identical **error** | both vanish: the error is cleared |
| `H X H` | becomes a single `Z` |
| `H Z H` | becomes a single `X` |
| Two CNOT pills stacked directly on the same two wires, in the same orientation | both vanish |

- **Sandwiches:** the rewritten gate stays where the middle gate was, and
  the two `H`s vanish. If the middle was an error, it stays an error of the
  new type. `H Y H` is `Y` up to a phase, so it changes nothing.
- **Scan order:** each wire is scanned from the bottom. At each position
  the scan tries a sandwich, then a pair. Matches don't overlap, and
  everything found in one pass vanishes at once.
- **Chains:** each pass is one chain step. Things settle, and the next pass
  runs. A chain ends when a pass finds nothing.

### Errors and winning

- **Errors** are anchored Pauli gates (X, Y or Z), drawn as little grumpy
  pixel bugs in their gate's colour. They sit in the bottom 8 rows, and two
  identical errors are never directly stacked on one wire.
- **Both boards get the same error layout** each round, so neither player
  is luckier, as with Qlimbers' shared targets.
- **Error count:** round 1 has 4 errors per board, and every later round
  adds 2, up to 12.
- **Winning a round:**
  - The first player whose board has **no errors left** takes the round.
  - A player who can't spawn their next pill, because the spawn cells are
    blocked, has **topped out**, and their opponent takes the round.
  - If both happen on the same frame, the round is a draw and is replayed.
- **First to 2 rounds** wins the match.

### Attacks

- A resolve sequence of `c` chain steps sends `c - 1` noise gates to the
  opponent, capped at 4. A single pass that clears 3 or more matches at
  once sends 1 more.
- Noise gates are random Paulis (X, Y or Z), as ordinary gates, not errors.
  They can even help the receiver, by cancelling something.
- Incoming noise waits in a queue shown beside the board. It drops onto
  random, distinct wires from the top, right after the receiver's current
  pill locks, as Dr. Mario's garbage does.

## 2. Architecture

A new top-level `gate-drop/` directory, the same shape as the sibling games:
a uv project, `src/gate_drop/`, `tests/`, `README.md` and an executable,
LF-only `deploy_batocera.sh`. The loader calls
`main(["--fullscreen", "--no-keyboard"])`.

| Module | Responsibility |
|---|---|
| `board.py` | Pure, no pygame. The grid, pills, movement and rotation, locking, settling, the cancellation scan, chains, noise. Fully unit tested. |
| `levels.py` | Pure. Error layouts from a seeded RNG, which both boards share. |
| `match.py` | Pure. Title, countdown, round, round result, match result; the attack exchange between boards; win and top-out checks; the idle timeout. |
| `input.py` | Pads and the dev keyboard turned into per-player actions, with stick auto-repeat. Start = raw 9, Select = raw 8, A = 1, B = 2. |
| `sprites.py` | Procedural pixel sprites: pill halves, CNOT halves, error bugs (2-frame wiggle), frame tiles, sparkles. Drawn from small pixel maps and palette rules, cached. |
| `render.py` | Boards, the background, the HUD (next pill, errors left, noise queue, round pips), animations, banners, the title. |
| `audio.py` | Chiptune sound effects and a looping music track, adapted from Overquqed's `audio.py`, credited. It speeds up when a board is nearly full. |
| `config.py`, `display.py`, `fonts.py`, `input_test.py`, `main.py`, `game.py` | The sibling games' patterns. |

- **Animation:** the simulation is step-based. Gravity ticks, settle steps
  and clear passes come out as events, and `render.py` animates them:
  landing squish, clear flash, then pop. The board logic pauses for each
  animation's fixed duration, so what you see is always the real state.

## 3. Look and sound

- **Resolution:** 480x270, integer-scaled x4 to 1080p, with
  `SDL_RENDER_SCALE_QUALITY=nearest` (as in AGENTS.md and Overquqed).
  Cells are 16 px, so a board is 96x224 px inside a chunky pixel frame.
- **Layout:** P1's board is on the left and framed in **blue**, P2's on the
  right and framed in **red** (AGENTS.md "Player colours"). Between them
  are each player's next pill, the count of errors left, the incoming
  noise queue, and round pips.
- **Sprites:**
  - **Pill halves:** a dark outline, a bright fill, a highlight top-left,
    a shade bottom-right, and the gate letter in the bundled 8 px font.
  - **Loose halves:** a gate whose partner is gone becomes a rounded half-pill.
  - **Error bugs:** a body in the gate's colour with angry eyes, little
    legs and the letter. They wiggle on a 2-frame loop.
- **Background:** a slowly scrolling, two-tone tiled pattern (diamonds or
  checks) per round, in a bright SNES palette.
- **Juice:**
  - pills squish slightly when they land;
  - cleared cells flash white, then burst into pixel stars;
  - chain steps pop up "2 CHAIN!", "3 CHAIN!" with a bounce;
  - incoming noise shakes the receiving board;
  - a board turns its frame red and blinks when its stack nears the top.
- **Title:** a big pixel "GATE DROP" logo with a drop shadow, pills raining
  behind it, a one-line rule summary, and PRESS A OR START.
- **Audio:** chiptune square and noise blips for move, rotate, land, clear
  (rising with chain length), noise sent and received, an error cleared, a
  round won and a top-out, plus one looping game track.

## 4. Testing

pytest, with the weight on `board.py`, `levels.py` and `match.py`:

- **Pill movement:** moving, walls, rotating in all four orientations
  (with a one-cell wall kick when a rotation would collide), CNOTs only
  swapping sides, and locking.
- **Settling:** loose halves fall, CNOTs fall rigidly, bridges keep their
  gap, and errors never move.
- **Every cancellation rule,** including gaps being skipped, a CNOT half
  blocking, errors being cleared, sandwiches turning an error into another
  error, scan order and non-overlap.
- **Chains:** counting steps, and the attack sizes they produce.
- **Noise:** it drops after the current pill locks, onto distinct wires.
- **Levels:** errors stay in the bottom 8 rows, no identical errors are
  stacked, the same seed gives the same layout, and the count follows the
  round.
- **The match:** winning by clearing all errors, by a top-out, a draw on
  the same frame, first to 2, rematch and back to title, and the idle
  timeout.
- **Rendering:** smoke tests that walk through every screen headless, plus
  a snapshot tool that renders PNGs for checking the look.

## Out of scope for v1

- Commuting rules: gates sliding through CNOTs, three CNOTs making a SWAP.
- Any gate beyond H, X, Y, Z and CNOT.
- A pause menu and high scores.
