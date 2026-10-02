# Planck Time: design

A microgame party for the ARQADE cabinet, in the style of WarioWare: 5-second
quantum microgames, one after another, faster and faster. The name: the
Planck time is the shortest meaningful unit of time in physics.

- **Players:** 1 (endless, high scores), or 2 side by side on the same
  microgame (versus).
- **Target:** the Batocera cabinet described in `../../../AGENTS.md` (Pi 4,
  1920x1080, two 6-button pads, Python 3.11, pygame 2.5.2).
- **Look:** Game Boy Advance pixel art, all procedural. Each player gets a
  true GBA-sized 240x160 screen inside a handheld-style bezel.
- **The design rule above all others:** colleagues' playtests showed that
  learning the controls is the biggest hurdle. Every microgame uses **only
  the stick and the A button**, shows **one verb**, is **playable by eye
  without any physics knowledge**, and explains its concept in a caption
  *afterwards*.

## 1. Flow

### Title

- A big PLANCK TIME logo, and the stick picks **1 PLAYER** or **2 PLAYERS**.
  A or Start begins.
- After 3 s untouched, an **attract mode** starts: bots play random
  microgames on both screens, until any input.

### The three beats of every microgame

1. **Intro, 1.5 s:** the verb in huge bouncing letters ("ALIGN!") and a big
   icon of the one input it uses: the stick, A, or "mash A". The first time a
   microgame comes up in a session, the icon is a little looping demo of the
   motion (the stick wiggling the right way, A being tapped). This is where
   the teaching happens.
2. **Play, 5 s, shrinking with speed:** a timer bar runs down. A microgame
   can be won early; it then shows its win animation until the bar runs out.
   A failure ends it at once.
3. **Result, 1.2 s:** "NICE!" or "OOPS!", plus the microgame's one-line
   concept caption.

### Speed

Every 4 microgames played, the level goes up by one:

- play time `max(2.5, 5.0 x 0.9^level)` seconds;
- object speeds `x (1 + 0.15 x level)`.

The music tempo follows. Each microgame also gets a little harder with the
level, as listed in its row below.

### Single player

- 4 lives. A failure costs one, and the game ends at 0.
- The **score** is the number of microgames cleared. A top-10 table with 3
  initials, reusing Gate Drop's `hiscores.py` and initials screen, is kept at
  `~/.planck_time_scores.json`.
- Either pad plays.

### Versus

- Both screens play **the same microgame, from the same seed, at the same
  moment**.
- A success scores 1. If both succeed, whoever finished **first** scores 1
  more. A failure costs a life (4 each).
- The last player with lives left wins. If both lose their last life on the
  same microgame, the higher score wins, and an equal score is a draw.
- The result screen offers A for a rematch and B for the title.

### Cabinet conventions (AGENTS.md)

- Start pauses (RESUME / QUIT TO TITLE). Start + Select quits.
- A 60 s idle timeout returns to the title.
- A confirms and B goes back in menus. P1 is blue on the left, P2 red on the
  right.
- The loader passes `--fullscreen --no-keyboard`.

## 2. The microgames

Each microgame is one class. It declares a `VERB`, an `INPUT` (`"stick"`,
`"a"`, `"mash"` or `"stick+a"`) and a `CAPTION`. It implements
`update(dt, inp)` and `draw(surface)` onto its own 240x160 surface, and ends
in success or failure. It also has a **bot**, a function from its state to an
input, which plays it perfectly. The bot serves three purposes: tests, the
attract mode, and the intro demos. All randomness comes from the seed it is
given.

| # | Verb | Input | Rules | Harder with level | Caption |
|---|---|---|---|---|---|
| 1 | **ALIGN!** | stick | A Bloch sphere (a circle, its equator ellipse and an arrow). The arrow swings round the circle facing the player and turns towards wherever the stick points. Win by holding it within 15° of the glowing target for 0.3 s. | The target starts farther away. | "You prepared a qubit state" |
| 2 | **CANCEL!** | A | A wire with a fixed gate in a slot at its centre. Gates scroll along it (X, Y, Z, H). Press A while the slot gate's twin is over the slot: both vanish and you win. A press at any other time fails. | Faster scrolling, more look-alikes. | "A gate followed by its inverse cancels out. Compilers do this!" |
| 3 | **FIX!** | stick + A | A qubit orb carries an error bug, X, Y or Z, in its gate colour. Three gate cards sit below it. The stick picks a card and A applies it. The matching card wins; any other fails. | The cards shuffle once mid-game. | "Undo an error by applying the same Pauli" |
| 4 | **MEASURE!** | A | An orb's needle swings between \|0⟩ (down) and \|1⟩ (up). Press A while it's in the top zone. A press elsewhere fails. | Faster swing, smaller zone. | "Measuring collapses a qubit to 0 or 1" |
| 5 | **SHIELD!** | stick | Steer a fragile qubit around the screen. Noise particles bounce about, and one always heads for where the qubit starts, so standing still loses. Win if nothing touches it until time's up. | More and faster particles. | "Noise destroys quantum states (decoherence)" |
| 6 | **VOTE!** | stick + A | A row of copies of a bit, one of them flipped. The stick moves a cursor and A picks. Picking the odd one out wins (it flips back and glows); anything else fails. | 5 copies instead of 3, and they jiggle. | "A majority vote corrects a bit flip" |
| 7 | **SHORTER!** | stick + A | Two small circuits, not necessarily equivalent. The stick picks a side and A chooses the one with fewer gates **after optimising**: identical neighbouring self-inverse gates cancel, repeatedly (X H H X vanishes). After the pick, the cancellations play out with "before->after" counts. | Taught over the session: the 1st time one is plainly shorter and the other's one pair still leaves it longer; the 2nd time the one with more gates as written compiles shorter; from then on the written counts say nothing either way. | "Compilers cancel gates to make circuits shorter" |
| 8 | **CONNECT!** | stick | A chip grid of qubits joined by couplers. The stick steps your qubit along couplers. Win once it is next to its partner (joined by one coupler). | A bigger grid, a farther partner, some broken couplers. | "Two-qubit gates need neighbours. Compilers move qubits with SWAPs" |
| 9 | **PAIR!** | stick + A | Particles sway in smooth loops with fading trails, and two of them sway in perfect sync; every other one is at a clearly different tempo or a quarter turn out of step. The stick jumps a cursor between particles and A picks. Picking one of the pair wins. (Random jiggling proved impossible to read in playtesting.) | 4, then 6, then 8 particles. | "Entangled qubits behave as one" |
| 10 | **REFRESH!** | mash A | A qubit's glow bar drains steadily, and every A press tops it up. Keep it above the line until time's up. | Faster drain. | "Error correction has to run again and again" |
| 11 | **STEER!** | stick | A photon beam from the left hits a mirror the stick rotates. Win by keeping the reflected beam on the detector for 0.4 s. | The detector drifts. | "Mirrors steer photons, which can carry qubits" |
| 12 | **SORT!** | stick | \|0⟩ and \|1⟩ tokens fall one at a time; the stick slides each into its bin (\|0⟩ left, \|1⟩ right). Win when all of them are sorted; a wrong bin fails. | More tokens, falling faster. | "Every measurement gives 0 or 1" |

A run never repeats a microgame until all 12 have come up, and none comes up
twice in a row.

### Bosses

After every **12 wins** (in versus: microgames that anyone won) comes a
**boss**:

- **The warning:** a BOSS! card with hazard stripes and a siren.
- **The fight:** one long game in phases, built from verbs players already
  know. It still uses only the stick and A.
- **Length:** a boss lasts 18 s at level 0, shrinking with the object speed.
  It ends 1.2 s after every player is done, not at the timer.
- **Scoring:** a win is worth **3 points**, plus the first-finish bonus. A
  loss costs a life, like any microgame.
- **Rotation:** bosses come round in order. v1 has one.

**SYNDROME!**: keep a logical qubit alive until the time runs out. (It
replaced TELEPORT!, which playtested as too hard and too far from quantum
computing.)

- **The chip:** 5 data qubits in a row, a distance-5 repetition code. On
  each link between neighbours is a parity check, a ZZ stabilizer measured by
  an ancilla: 4 checks, each reading 0 (dim) or 1 (lit red, glowing). The
  qubits are orbs that always read `|0>`.
- **Noise:** from time to time an X error lands on a data qubit. The qubit
  looks unchanged; only the checks on both sides of it flip. A middle error
  lights the two checks either side, an end one the single check next to it.
  The noise shows as a crackle over the whole chip, with no position.
- **Fixing:** the stick steps a gold bracket along the qubits and A applies
  an X. On a flipped qubit its checks go dark (a green pulse); on any other
  it is a new error, and the checks change accordingly.
- **Losing:** 3 flipped qubits outvote the other 2, so the majority reads the
  wrong value: a logical error. The chip flashes red, every qubit turns over
  to `|1>`, and the checks go dark, because that is a codeword again. Three
  danger pips, top right, are the only place the hidden error count shows.
- **Winning:** survive to the end (`timeout()` wins). Errors keep coming, so
  doing nothing reaches 3 flips by about 40% of the time.
- **The three phases** (thirds of the fight; all times shrink with speed):
  1. One error at a time, on the middle three qubits. The next lands 2.0 s
     after the chip is clean, or 3.0 s after the last error if it is left.
  2. Faster (1.3 s). The phase's second error comes with a second one: a lit
     pair plus a lone check at an end.
  3. The cases that need reading, with room to think (2.2 s): first an end
     qubit, then an adjacent pair (the shared check cancels, so the lit
     checks are two links apart and the fix is both qubits in between).
- **Only readable patterns land.** With 5 qubits, two errors one apart in the
  middle (qubits 1 and 3) light all 4 checks, and an X on the qubit between
  them would be a third error. That pattern, and the others with a lit run of
  3 or a lone check away from the edges, never land; a player's own wrong
  press can still make them.
- **The bot** knows the flipped set; it looks for 0.2 s, then steps once
  every 0.12 s to the nearest flipped qubit and presses A.
- **Hint:** "A BETWEEN THE RED CHECKS".
- **Caption:** "Parity checks find errors without measuring the qubits".

## 3. Architecture

A new top-level `planck-time/` directory, in the same shape as the sibling
games: a uv project, `src/planck_time/`, `tests/`, `README.md` and an
executable, LF-only `deploy_batocera.sh`.

| Module | Responsibility |
|---|---|
| `microgames/` | One module per microgame (class, bot), plus `base.py` (the `Microgame` base class, the `PlayerInput` it reads, and the registry). Rules are pure; `draw()` is the only pygame part. |
| `session.py` | Pure. The order of microgames, the beats and their timing, speed levels, lives, scores, the versus rules, pause, idle. The equivalent of Gate Drop's `match.py`. |
| `hiscores.py` | Copied from Gate Drop. |
| `palette.py`, `pixel.py` | The GBA-style palette, and pixel-art helpers: outlines, dithering, 8x8 tile drawing, bouncy text. |
| `render.py` | The 640x360 frame: two GBA bezels with their 240x160 screens, lives and scores, the intro and result cards, the title, the initials and high-score screens, the pause menu. |
| `input.py` | Per pad: the analog stick (with deadzone), auto-repeated stick steps for menus and grid moves, A pressed and held, Start / B / Select. |
| `audio.py` | Chiptune adapted from Gate Drop: jingles for intro, win, fail and level-up, and a music loop whose tempo follows the level. |
| `config.py`, `display.py`, `fonts.py`, `input_test.py`, `main.py`, `game.py` | The sibling games' patterns. |

**Rendering:** each microgame draws into its own 240x160 surface, which
`render.py` blits into a bezel. Both players' instances are separate objects
created from the same seed.

## 4. Look and sound

- **Resolution:** 640x360, integer-scaled x3 to 1080p, with
  `SDL_RENDER_SCALE_QUALITY=nearest`. 480x270 was the first idea, but two
  240x160 screens fill it exactly, which leaves no room for bezels. At
  640x360 each GBA pixel is a crisp 3x3 block on the cabinet. Each screen sits
  in a 300 px GBA-shaped bezel (side wings with a little D-pad and A/B
  buttons), centred at x = 160 and x = 480, with lives and score above.
- **Palette:** a fixed, bright GBA-like palette of about 32 colours, with
  every channel a multiple of 8, as on the GBA's 15-bit display. Chunky
  dark outlines, 2-colour dithering for shading, 8x8 tile backgrounds.
- **Bezels:** each player's screen sits in a rounded, GBA-shaped bezel in the
  player's colour (P1 blue, P2 red), with a little power LED that blinks on a
  success.
- **Juice:** squash-and-stretch on the verb text, screen shake on a failure,
  confetti on a success, and the speed-up card ("SPEED UP!") between levels.
- **Text:** the bundled Press Start 2P, which is 8 px like real GBA fonts.
  Its known missing glyphs (`⟩`, the Unicode minus) are drawn in pixels where
  needed, as in Gate Drop's ket labels.

## 5. Testing

- **Every microgame**, over seeds 0 to 19 at levels 0 and 3:
  - its bot wins;
  - doing nothing loses, in every microgame (SHIELD aims a particle at the
    qubit's starting point for exactly this reason);
  - pressing A at random (for the A games) loses at least sometimes;
  - two instances from the same seed stay identical under the same inputs.
- **The session:** beat timing; the speed ramp; lives; single-player game
  over and the high-score handoff; the versus scoring with its first-finish
  bonus; last player standing and draws; same-seed instances for both
  players; the no-repeat order; pause; idle.
- **Rendering:** smoke tests through every screen and every microgame, plus a
  snapshot tool that renders PNGs for checking by eye.

## Out of scope for v1

- More than 12 microgames: new ones drop into `microgames/` and the registry.
- More bosses (DECOHERENCE DEMON and GROVER'S VAULT were pitched).
- Co-op with shared lives.
