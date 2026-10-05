# Planck Time: arqade crossover microgames: design

Planck Time (`planck-time/`) gets **nine new microgames**, one for each other game on
the cabinet. Each one is a single interaction of that game, cut down to the stick
and A. With the 12 originals, a session draws from 21 microgames.

## Rules shared by all nine

- **The contract** is the one in `microgames/base.py` and `tests/test_microgames.py`.
  The tests check, over 20 seeds at levels 0 and 3, that:
  - `bot()` always wins;
  - doing nothing always loses;
  - the same seed gives the same game;
  - drawing works throughout a game;
  - the metadata is valid: VERB upper case and ending in `!`, INPUT one of
    `stick`, `a`, `mash` or `stick+a`, CAPTION at most 64 characters and only glyphs
    the font has.
- **One module each** in `microgames/`, with one `@register`ed class and no edits
  elsewhere. Rules are pure; pygame appears only in `draw()`.
- **The screen is 240x160.** Draw with the GBA palette (`palette.py`, every channel a
  multiple of 8) and the `pixel.py` helpers. End every `draw()` with
  `result_overlay`, and put a one-line hint at the bottom, as MEASURE! does.
- **Recognisable.** Each one borrows its source game's look: its sprites, shapes and
  colours, redrawn small. Read the source game's README and its drawing code first.
  Use only elements the game really has (see the logo notes in `../AGENTS.md`):
  nothing invented.
- **Readable at first sight.** It is a 5-second game seen for the first time. There is
  one verb, an obvious goal, and fair timing at level 0. The level scales speed and
  tightness, as the originals do (`self.speed`, `self.level`).
- **Long enough to react.** At level 0, the first moment a decision is possible is at
  least 0.6 s in.
- **No player colours.** The two screens in versus show the same game. Use neutral or
  source-game colours, never P1 blue against P2 red inside one game.
- **ASCII kets** (`|0>`, `|+>`). Check any other glyph against the font notes in
  `../AGENTS.md`.

## The nine

| Verb | Source | Input | The game | Win | Fail | Caption |
|---|---|---|---|---|---|---|
| RETURN! | Quantum Pong | stick | Your white paddle is on the left. A ball comes from the right, and on its way passes a **Z gate** midfield, which bounces it as if off an invisible horizontal wall, so its vertical direction flips. Move the paddle to where the ball really arrives. The ball's path is not drawn ahead. | the ball hits the paddle | the ball passes the paddle | Z flips the ball: gates change its path |
| CLIMB! | Qlimbers | stick+a | Your qubit's state and the floor's target ket, with three gate cards from X, Y, Z, H. Exactly one card turns the state into the target in one step. The stick picks a card, A applies it, then **push up** to climb. A wrong card leaves the state wrong, and push-up on a wrong state stuns, as in Qlimbers. A gate can be re-applied to undo it. | push up with the right state | time runs out | Gates turn one state into another |
| CORRECT! | Pauli Invaders | stick+a | One error invader (X red, Z blue, Y purple, Pauli Invaders' own sprites and colours) descends. Your ship's shot colour cycles X, Z, Y on a beat. Move under it and fire with A when the colour **matches**. | a matching shot hits | a wrong shot hits, or it reaches the bottom | Only the matching Pauli corrects it |
| SURF! | Ion Surfer | stick | Your ion rolls on the trap potential, drawn as Ion Surfer's curve. The stick's up and down raise or lower the one electrode under a **loss hole**, and left and right do nothing. Keep the ion out of the hole until a photon reaches it, or until time's up. | survive to the end | the ion falls into the hole or off screen | You shape the trap that holds the ion |
| SERVE! | Overquqed | stick+a | A guest orders a state (`|1>` or `|+>`). There are two appliances, Overquqed's X oven and H toaster, and the guest's counter. Walk your qubit bowl to the right appliance and press A, then walk to the guest and press A to serve. | the right state served | a wrong state served, or time runs out | Kitchen appliances are gates |
| ROUTE! | Superconductor | stick | A small chip with two highlighted qubits. A rival route, already drawn, crosses the chip. Steer your route coupler by coupler to join the pair. Crossing onto the rival route is Superconductor's red collision X. This is not CONNECT!, which has no rival route: here the clash is the point. | the route reaches the pair | a collision, or time runs out | Two-qubit gates need a free route |
| SPLIT! | Qurves | stick | Your light cycle races toward a wall of the rival's trail with one gap. An **H gate** sits before it. Drive over the H and you split into two mirrored copies; one of them always makes it through the gap. Without the H, the gap is out of reach. | at least one copy survives to the end | every copy crashes | You lose only when every copy crashes |
| DROP! | Gate Drop | stick+a | A gate pill falls over a well of a few columns. Each column's top gate is shown. Slide the pill over the column whose top gate is its **inverse** (X on X, H on H, T on T-dagger), and A drops it fast. The pair cancels with Gate Drop's pop. | the pill lands on its inverse | it lands anywhere else | A gate next to its inverse vanishes |
| MATCH! | Brawl-Ket | a | A rival fighter, Brawl-Ket's puppet, keeps switching between green (Z basis) and purple (X basis). Your fighter's colour is fixed and shown. Strike with A while the rival's colour **matches** yours. A strike in the wrong colour is blocked with pushback. | a matching strike lands | a blocked strike, or time runs out | Colour must match to hurt |

### Notes per game

- **RETURN!:** Pong's paddle catch grace applies. The bot reads the real trajectory,
  including the Z bounce and wall bounces. On later appearances (`self.appearance`),
  the gate may be an X instead, which bounces the ball back to the right and then
  through the Z gate on its way back. The implementer picks this only if it stays
  readable in 5 s; otherwise it is Z every time.
- **CLIMB!:** the states and gates come from Qlimbers' `quantum.py` and `search.py`
  semantics, reimplemented in about 30 lines rather than imported, because the games
  are independent packages. The target is never the current state. A second stun
  still fits within the time at level 0. INPUT is `stick+a` (left and right pick, A
  applies, up confirms).
- **CORRECT!:** the colour cycle must be slow enough at level 0 that the matching
  colour lasts at least 0.5 s, and the invader descends slowly enough for at least two
  cycles.
- **SURF!:** a survive game. `timeout()` wins, as SHIELD! does. Doing nothing must
  lose, so the hole must pull the ion in on its own.
- **SERVE!:** the order and the appliances are chosen so that exactly one appliance is
  right. The empty bowl is `|0>`, X gives `|1>` and H gives `|+>`. Pressing A at the
  wrong appliance gives a wrong state, which fails only once it is served. Pressing A
  at the same appliance again undoes it (X·X = H·H = I), as in Overquqed.
- **ROUTE!:** the stick moves the route head one coupler per push (`inp.step`). The
  rival route never blocks every path.
- **SPLIT!:** steering is left and right turns, or a free 4-way stick. The implementer
  picks whichever reads clearest. The H is the only way through, so doing nothing
  crashes.
- **DROP!:** exactly one column is right. Gate Drop's gates and inverses are used
  (`H X Y Z T Td` in `gate-drop/src/gate_drop/config.py`, where H, X, Y and Z are their
  own inverses and T pairs with T-dagger), labelled and coloured as Gate Drop draws them.
  T and T-dagger appear only on later appearances (`self.appearance >= 1`).
- **MATCH!:** this is the cabinet's only `a`-only crossover. The switching is
  irregular but never faster than 0.4 s per colour at level 0.

## Testing

- The existing contract tests cover all nine automatically.
- Each module may add its own focused tests where its rules need them, e.g. CLIMB!'s
  "exactly one card is right", DROP!'s "exactly one column is right" or RETURN!'s
  trajectory with the Z bounce.
- Snapshots: `uv run python tools/snapshot.py OUT` renders each microgame at its start,
  mid-game and after the end. Every one is checked by eye for readability and
  likeness to its source game.

## Docs

- README: the microgame table gains the nine rows, and "all 12 microgames" becomes 21.
- The intro card already shows each game's INPUT, so nothing else changes.

## After the first playtest (2026-10-05)

Four crossovers were cut: SERVE! (Overquqed) and MATCH! (Brawl-Ket) were too
complex for five seconds, SPLIT! (Qurves) had too little to do with its game and
was too hard, and SURF! (Ion Surfer) left players unsure what to do. RETURN!
froze the ball on the catch (`update()` stops stepping once a result is set), so
the return is now drawn from `since_end`: a caught ball flies back at Pong's
angle, a missed one flies on. Five crossovers remain: RETURN!, CLIMB!, CORRECT!,
ROUTE! and DROP!, each in its own game's look.
