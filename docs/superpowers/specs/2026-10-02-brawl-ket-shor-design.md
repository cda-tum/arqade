# Brawl-Ket v2: the Shor code: design

This replaces the rules of `2026-10-01-brawl-ket-design.md`, which built each
fighter on a repetition code. The first cabinet playtest (2026-10-02) found:

- **It doesn't feel quantum.** A bit-flip repetition code is classical error
  correction. The players never did anything that a classical code couldn't
  explain, and the stance switch was a game rule dressed up as a basis change.
- **Lights beat heavies.** Two jabs broke a TRIO, and heavies had a 24-frame
  telegraph (for the defender's stance switch), so mashing A was always best.
- **QUINT's specials whiffed:** SYNDROME GRAB reached only ~75 px, as far as a
  jab, and COLLAPSE only hit straight down.
- **TRIO's DIVE took too long to land:** up to 40 frames.
- **Chains whiffed at close range.** That was a bug, fixed separately in
  `01689a1`: jabs pushed the rival out of the heavy's reach.

What stays: the engine (fixed 60 Hz simulation, puppets, match flow,
sound, deploy), the controls (stick, A, B, X, Start), both fighters'
looks, versus only, best of 3, 60 s rounds.

## 1. Rules: every fighter is a Shor code

Each fighter's health stands for one logical qubit protected by **Shor's
[[9,1,3]] code**: three blocks of three qubits. Inside a block, a bit-flip
code guards against X errors; across the blocks, a phase-flip code guards
against Z errors. Unlike a repetition code it corrects *any* single-qubit
error, X, Y or Z, which no classical code can.

The game draws it as a **3×3 grid**:

- **Rows are hit heights:** HIGH, MID, LOW. They are the code's three blocks.
- **Columns are A, B and THROW:** the three qubits in a block.

### What deals what

| Move | Error | Lands on |
|---|---|---|
| A or B normal | X | one cell: (the move's height, its button's column) |
| Special (the X button, labelled SPECIAL on screen) | Z | the whole row at the move's height |
| Throw | Y = X + Z | the THROW cell at MID, plus the MID row |
| RE-ENCODE | none | it corrects instead (section 2) |

A Z on any qubit of a block acts the same way on the code, so a Z is drawn
as the whole row; the game applies it to the row's first qubit.

### When a hit lands

Counted within one correction cycle:

- **An X on a lit cell cancels it:** the cell goes dark (X·X = I).
- **A Z on a flipped row cancels it:** the row goes dark. Two Z errors in one
  block are a stabiliser of the code: degeneracy, a purely quantum property.
- **Two different X cells in one row** are uncorrectable: the block's
  majority vote completes them to XXX, a logical operator.
- **Z on two different rows** is uncorrectable: the vote across the blocks
  completes them to a logical operator.
- **An uncorrectable state is a logical error, and it lands at once:** big
  damage, a knockdown, and the grid resets, since the qubit is re-encoded.
- **Anything else** is correctable: chip damage, and the light stays on until
  the next correction cycle.

X and Z errors are decoded independently (the Shor code is a CSS code), so
an X and a Z in the same row don't interact.

Verified against the code's stabilisers and its standard decoder:

| Errors in one cycle | Verdict |
|---|---|
| X on one cell, twice | corrected (cancels) |
| X on A then B, same row | logical |
| X on A then B, different rows | corrected |
| Z on one row, twice | corrected (cancels) |
| Z on two rows | logical |
| a throw alone (Y at MID/THROW) | corrected |
| a throw + any X at MID | logical |
| a throw + an X at HIGH | corrected |
| an X and a Z in one row | corrected |

### The correction cycle

Each fighter's code runs a correction cycle on a fixed beat, shown as a ring
that fills beside the grid. At each tick the standard Shor decoder runs (a
majority vote inside each row, then across the rows) and every correctable
error is cleared. Players never decode by hand.

### Physics, and what is a game rule

Exact: the error algebra, cancellation, degeneracy, which patterns are
logical, and the decoder. Game rules, labelled as such in code comments:

- each hit is exactly one error, on the qubit its move and button choose;
- correction happens on a fixed beat, and errors in a cycle are only
  counted against each other;
- an uncorrectable pattern counts as a logical error at once (the decoder is
  certain to fail at the next tick), and the qubit is then re-encoded.

### Defence is the body

No block and no basis switch. What protects a lit row is moving that part of
the body out of the way:

| Height | Moves | Avoided by |
|---|---|---|
| HIGH | standing A and B, PHOTON, COLLAPSE's slam | crouching: they whiff over you |
| MID | air A and B (jump-ins), throws, DIVE, SYNDROME GRAB | nothing: you must hit first or stay out of reach |
| LOW | crouching A and B, PHASE SLIDE, COLLAPSE's shockwave | jumping |

These whiff rules come on top of the hitbox overlap: a HIGH move never hits a
crouching fighter, and a LOW move never hits an airborne one.

## 2. Fighters and moves

Every height has an A and a B, so **A then B at one height breaks a code**, at
any height. A chain that changes height (crouching A, then standing B) spreads
its errors over two rows and is corrected. The defender sees their lit row
and knows which height to protect: that is the core read.

Both fighters use the same code and rules. They differ in speed, reach,
health, cycle length and specials. The names TRIO and QUINT stay as names.

### TRIO: fast and lean, 1.0 s cycle, 100 health

Its specials cover all three rows, so two different specials in one cycle are
a logical error.

- **PHOTON** (X): a projectile at head height, Z on HIGH. Crouching ducks it.
  2.5 s cooldown.
- **PHASE SLIDE** (down + X): Z on LOW. It slides under photons, as now.
- **DIVE** (air + X): Z on MID. Steep and fast: it reaches the floor in
  about 12 frames from the top of a jump, bounces back off a hit, and
  recovers quickly on landing.

### QUINT: slow and broad, 1.5 s cycle, 115 health, longer normals

- **SYNDROME GRAB** (X): a dashing command grab that reaches about 130 px,
  Z on MID. A throw, so it can't be ducked or jumped. Slow to start, with a
  long recovery on a whiff.
- **RE-ENCODE** (down + X): no error. It runs an extra correction round at
  once (real QEC also schedules extra rounds of checks), clearing every
  correctable error. 4 s cooldown.
- **COLLAPSE** (air + X): a body slam that drifts towards the rival. A direct
  hit is Z on HIGH; the landing shockwave is Z on LOW. A rival caught by both
  has two rows flipped: one slam is a logical error. A long landing recovery
  punishes a whiff.

### Shared

The throw (B up close, pushing towards the rival) is Y = X + Z at MID for
both. One throw alone is corrected; a throw on top of a MID error breaks
the code.

## 3. Feel: starting numbers

All in `moves.py` and `config.py`, tuned after the next playtest.

**Heavies are fast.** The telegraph (24 or 28 frames, with a glint) existed
for the defender's basis switch; it goes.

| Startup (frames) | TRIO | QUINT |
|---|---|---|
| A | 4 | 6 |
| B (heavy, sweep) on its own | 10 | 13 |
| B cancelled from a hit A | 7 | 9 |

**Crouching is instant.** The 8-frame switch window and its "a hit
mid-switch is a logical error" rule go.

**Damage:**
- every error that lands: 2 chip (no refund when it cancels);
- a logical error: 25, plus 5 if a heavy or a special caused it, and a
  knockdown, so a break resets the fight to neutral;
- health: TRIO 100, QUINT 115;
- cycles: TRIO 1.0 s, QUINT 1.5 s. QUINT's errors stay longer: its weakness.

**Specials:**

| Move | Numbers |
|---|---|
| PHOTON | startup 14, 2.5 s cooldown (as now) |
| PHASE SLIDE | as now |
| DIVE | startup 3, falls at 10 px/frame with a slight forward drift (~12 frames to the floor from the apex), bounces back on a hit, 8 frames of landing recovery |
| SYNDROME GRAB | startup 16, then a dash of up to 30 frames at ~6 px/frame (reach ~130 px), 30 frames of recovery on a whiff |
| RE-ENCODE | startup 6, 4 s cooldown |
| COLLAPSE | drifts 2 px/frame towards the rival while falling, shockwave reaches 45 px either side, 20 frames of landing recovery |

**Bots** read the rival's grid: A then B at the height of a lit row, and
specials on two different rows. They play the attract demo and the tests,
and keep the balance numbers honest.

## 4. Readability and teaching

### The grid tag

The grid replaces the lights above each fighter's head and follows its
fighter, with the cycle ring beside it. HIGH is the top row, so it reads like
a tiny copy of the body. Cells are 6 px with 3 px gaps (about 27×27 px). The
ket label goes.

| State | Look |
|---|---|
| X on a cell | the cell lit in the X gate's red |
| a row flipped by Z | the row's backing glows in the Z gate's blue |
| Y (a throw) | both: the red THROW cell on a blue MID row |
| danger: a row holding one X | its other two cells pulse orange |
| danger: a row flipped | the other two rows pulse orange |
| cancel | the light goes out with a white pop and an `I` pop-up |
| logical error | LOGICAL ERROR!, the shake, the grid flashes red and clears |
| correction tick | lit cells flash green and clear |

The hit pop-ups (`X!`, `Z!`, `Y!`) stay.

### Teaching

The controls are the cabinet's biggest hurdle, so the rules are taught where
a new player actually looks:

1. **HOW THE CODE WORKS:** a card that takes turns with the bot demo on the
   title. An animated grid plays three rules in a loop, one line each:
   *same hit twice: cancels*, *A then B at one height: BREAK*, *specials at
   two heights: BREAK*.
2. **The select screen** lists each move with its height and error
   (`X  PHOTON  Z HIGH`) and a line under the fighter: *Mix A and B at one
   height to break the code.*
3. **A match's first ROUND 1 intro** shows one hint line under the call:
   *A then B at one height breaks the code.*

No separate tutorial mode.

## 5. Architecture and testing

The engine stays; the code underneath changes.

| Module | Change |
|---|---|
| `qec.py` → `shor.py` | Pure. `ShorCode` holds the lit X cells and flipped rows; `apply_x(row, col)`, `apply_z(row)`, `apply_y(row, col)` return `cancel`, `flipped` or `logical`; `tick()`, `progress`, `reset()`, and danger queries for the HUD and the bots. The repetition code goes. |
| `moves.py` | Every attacking move gets a `height`; the error per section 1; the column from the slot. Section 3's numbers; the telegraph fields go. |
| `fighter.py` | No basis switch or switch window; crouching is instant. Hits go to the `ShorCode`; a logical error knocks down. |
| `fight.py` | The height whiff rules; events carry the cell or row and the outcome, plus a `cancel` event; COLLAPSE's slam and shockwave, the new DIVE and GRAB. |
| `render.py` | The grid tag and its effects; the glint goes; the select screen's move list, the HOW THE CODE WORKS card, the ROUND 1 hint. |
| `match.py` | The title alternates the demo with the card; the hint on a match's first round. |
| `bot.py` | Reads the grid, as in section 3. |
| `audio.py` | A sound for a cancel. |

### Testing

- **`shor.py` against an independent reference.** The test builds the Shor
  code in the Pauli (stabiliser) formalism (8 stabilisers, the standard
  decoder) and, for every sequence of up to 3 hits (any X cell, Z row or Y),
  checks the game's verdict: the residual after decoding is the identity or a
  stabiliser (corrected), or a logical operator (logical). It also checks the
  table in section 1.
- **Moves:** every attacking move has a height and the error from section 1;
  every height has an A and a B; the chain test (A, B and A, A, B connect from
  every spacing a jab does) keeps passing.
- **Fights:** A, A at one height cancels; A, B at one height is logical; at
  two heights, corrected. Two specials on two rows are logical; the same one
  twice cancels. A lone throw is corrected; a throw on a MID error is
  logical. A COLLAPSE hitting with slam and shockwave is logical. HIGH whiffs
  on a crouching rival, LOW on an airborne one. The GRAB reaches ~130 px; the
  DIVE lands within ~12 frames of the apex.
- **Bots:** fights finish in every pairing, and bots break codes.
- **Render and match:** smoke tests through the grid states, the card and the
  hint; the snapshot tool covers the new screens.

### Build order

Each step is its own commit, and the game stays playable throughout.

1. `shor.py` and its reference test.
2. Rules: moves, fighter, fight.
3. The grid HUD and effects. **Playtest checkpoint:** the core is playable.
4. Bots, teaching screens, audio.
5. Tuning from the playtest, then deploy.

## Out of scope

- A bigger or asymmetric code for QUINT (a 5×3 Shor code, or 5×5): both
  fighters use the 3×3 code.
- Player-driven decoding: the cycle corrects automatically.
- A CPU mode, more fighters, blocking, a super meter.
