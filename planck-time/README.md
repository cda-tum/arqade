# Planck Time

A quantum microgame party in the style of WarioWare, for 1 or 2 players, for
the ARQADE cabinet (Batocera, `pygame` system). Nineteen tiny games come
one after another, each about five seconds long and faster and faster. The name:
the Planck time is the shortest meaningful unit of time in physics.
Design: `../docs/superpowers/specs/2026-10-01-planck-time-design.md`, with the
arqade crossovers in `2026-10-05-planck-time-crossovers-design.md` and the two
error-correcting-code microgames in `2026-10-05-planck-time-code-microgames-design.md`.

**The design rule:** playtests showed that learning the controls is the
biggest hurdle, so every microgame uses **only the stick and A**, shows
**one verb**, is **playable by eye** without any physics knowledge, and
explains its concept in a one-line caption *afterwards*.

**Status:**
- **The game:** all 19 microgames (the 12 originals, 5 crossovers from the
  other arqade games, and TILE! and MERGE! on error-correcting codes), single
  player (endless, 4 lives, top-10 initials) and versus (both players on the
  same microgame, side by side).
- **Screens:** GBA-style pixel art at 640x360 (x3 on the cabinet), the title
  with an attract demo, and pause.
- **Extras:** chiptune whose tempo follows the level, `--input-test`, and a
  Batocera deploy script.

## How to play

- **Title:** the stick moves between 1 PLAYER, 2 PLAYERS and QUIT (it
  doesn't wrap, so QUIT is never one push from the top). A picks the row:
  QUIT goes straight back to the cabinet's menu. Start always starts, with
  the player count last picked, even on QUIT. Left alone for 3 s, the title
  shows bots playing (and its selection goes back to the player count).
- **HOW TO PLAY:** a run started from the title opens on a card
  (`tutorial.py`): the goal, the controls on a drawing of the cabinet's pad
  (the stick, L X R over Y B A, Start; the stick, A and Start lit), and a
  handheld playing VOTE! and MEASURE! with their own bots through the real
  beats. Any button dismisses it, after its first 0.3 s; the stick doesn't.
  A rematch skips it. Start doesn't pause in the first 0.5 s after it, so
  mashing through the card can't pause the first intro.
- **Every microgame has three beats:**
  1. **Intro** (1.5 s): the verb, and an icon of the one input it uses. The
     first time a microgame comes up, the icon is animated.
  2. **Play:** the fuse below the screen burns down. A failure ends it at
     once, and a win 0.4 s later (`WIN_LINGER`), with the fuse left over
     frozen on the result. In versus it ends once both outcomes are decided.
     SHIELD! and REFRESH! (and the boss) are won by surviving, so only the
     fuse can end those with a win.
  3. **Result:** NICE! or OOPS!, plus the concept caption.
- **Sound:** chiptune jingles for every beat, a tick for each cursor step
  and a click for each A press that doesn't end the microgame.
- **Speed:** every 4 microgames the level goes up (SPEED UP!).
  - The play time is `max(2.5, 5 x 0.9^level)` s.
  - Objects move `1 + 0.15 x level` times as fast.
  - Each microgame also gets a little harder.
- **Single player:** 4 lives, and the score is the number of microgames
  cleared. Either pad plays.
- **Versus:** both players get the same microgame from the same seed, at the
  same moment. A success scores 1, and if both succeed, whoever finished
  first scores 1 more. A failure costs a life. The last player with lives
  left wins. If both go out together, the higher score wins, and equal
  scores are a draw. On the result screen, A rematches and B goes to the
  title.

| # | Verb | Input | What you do |
|---|---|---|---|
| 1 | ALIGN! | stick | Point the Bloch-sphere arrow at the star |
| 2 | CANCEL! | A | Press as the slot gate's twin passes over it |
| 3 | FIX! | stick + A | Pick the Pauli card that matches the error |
| 4 | MEASURE! | A | Press while the needle is in the top zone |
| 5 | SHIELD! | stick | Dodge the noise until time's up |
| 6 | VOTE! | stick + A | Pick the bit that disagrees with the others |
| 7 | SHORTER! | stick + A | Pick the circuit that is shorter once identical neighbours cancel (it gets harder each time it comes up) |
| 8 | CONNECT! | stick | Walk your qubit along couplers to its partner |
| 9 | PAIR! | stick + A | Pick one of the two particles swaying in sync |
| 10 | REFRESH! | mash A | Keep the glow bar above the line |
| 11 | STEER! | stick | Turn the mirror to keep the beam on the detector |
| 12 | SORT! | stick | Slide each falling `|0>` / `|1>` into its bin |

**The arqade crossovers:** a microgame for five of the other games on the cabinet,
each a single interaction of that game cut down to the stick and A, in its own look.
Overquqed, Brawl-Ket, Qurves and Ion Surfer had one too (SERVE!, MATCH!, SPLIT! and
SURF!), cut after a playtest: too complex or too hard to read in five seconds.

| # | Verb | From | Input | What you do |
|---|---|---|---|---|
| 13 | RETURN! | Quantum Pong | stick | Catch the ball where it really arrives: a Z gate in midfield flips its vertical direction |
| 14 | CLIMB! | Qlimbers | stick + A | Apply the one gate card that turns your state into the floor's target, then push up to climb |
| 15 | CORRECT! | Pauli Invaders | stick + A | Fire at the descending error invader while your shot's colour matches it |
| 16 | ROUTE! | Superconductor | stick | Route your coupler path to the qubit pair without crossing the rival route |
| 17 | DROP! | Gate Drop | stick + A | Drop the gate pill on the wire whose top gate is its inverse |

**The codes:** two microgames about what error-correcting codes look like and
how they compute, rather than decoding.

| # | Verb | Code | Input | What you do |
|---|---|---|---|---|
| 18 | TILE! | colour code | stick + A | Paint the blank honeycomb tile the one colour its neighbours lack (every corner touches all three colours) |
| 19 | MERGE! | surface code | stick + A | Turn your patch so its facing edge matches the other patch's, then push in to merge: XX along X edges, ZZ along Z edges (lattice surgery) |

**Bosses:** after every 12 wins comes a BOSS! (worth 3 points, a life if
lost). **SYNDROME!**: keep a logical qubit alive on a chip of 5 data qubits
(a distance-5 repetition code) until the time runs out. X errors land
unseen, with only a crackle over the chip; the 4 parity checks between the
qubits show where. A lit pair points at the qubit between them, and a lone
lit check at an end points at the end qubit. Step the cursor and press A to
apply an X: on the right qubit its checks go dark, on a wrong one it is a
new error. Three flipped qubits outvote the other two: a logical error. The
fight runs in thirds: one error at a time, then faster with some two at once,
then end qubits and adjacent pairs (whose shared check cancels, so the lit
checks are two links apart and both qubits in between need an X).
The noise has a face: DECOHERENCE, a blob of static above the chip that
winds up and spits every error, though its bolt always splashes the whole
chip, so only the checks say where it hit. It flinches at a fix, grins at a
wrong press, laughs at a logical error and dissolves when the qubit
survives. Its portrait and name are on the BOSS! card, and the boss has its
own track.

| Action | Cabinet | P1 keyboard | P2 keyboard |
|---|---|---|---|
| Stick | stick | E S D F | arrows |
| A (and confirm in menus) | A | Q | . |
| Back (menus) | B | W | , |
| Start / pause (resume or quit to the title) | Start | 1 | 2 |
| Quit | QUIT on the title, Start + Select, or hold Select 2 s on the title | Esc | Esc |

P1's dev keys avoid the pad's own letters (l, x, r, b, y, a; see
`../AGENTS.md`). The keyboard is a dev fallback only: on the cabinet the
loader passes `--no-keyboard`. High scores are kept in
`~/.planck_time_scores.json`, outside the package, so a redeploy keeps them.

## Setup (dev machine)

Requires [uv](https://docs.astral.sh/uv/).

```bash
cd planck-time
uv sync
uv run python -m planck_time          # windowed
uv run python -m planck_time --fps    # with the FPS overlay
uv run pytest
uv run python tools/snapshot.py /tmp/planck-snaps   # every screen and microgame to PNGs
```

## Layout

| Module | Role |
|---|---|
| `microgames/` | One module per microgame or boss, plus `base.py`, the contract. Rules are pure; `draw()` is the only pygame part. |
| `session.py` | Title, the HOW TO PLAY card, the beats, speed levels, lives, scores, versus, pause, idle, the attract demo. Pure, tested. |
| `palette.py`, `pixel.py` | The 15-bit GBA palette, and pixel-art helpers (outlined text, orbs, cards, the win/fail overlay). |
| `tutorial.py` | The HOW TO PLAY card's words and its demo (real microgames, played by their bots). |
| `render.py` | The 640x360 frame: handheld bezels, HUD, fuse, cards, and every screen. |
| `decoherence.py` | DECOHERENCE, SYNDROME!'s monster: its pre-rendered static body, face, moods, bolt and dissolve. |
| `audio.py` | Chiptune effects and music, adapted from Gate Drop's. |
| `input.py`, `config.py`, `hiscores.py` | Pads and the dev keyboard; every tuning number and button; the top-10 table. |

### Adding a microgame

Drop a module into `microgames/` with one `@register`ed `Microgame` subclass
(or a `@register_boss`ed `Boss` subclass).
It's discovered automatically, and `tests/test_microgames.py` checks it
against the contract over 20 seeds at levels 0 and 3:

- its `bot()` always wins;
- doing nothing always loses;
- it's deterministic for a given seed;
- it draws in every state;
- its verb and caption use only glyphs the font has.

`align.py` and `cancel.py` are the reference implementations.

## Deploying to the cabinet

```bash
./deploy_batocera.sh                    # or ./deploy_batocera.sh root@10.42.0.100
```

The first time, you also need to add the `batocera/gamelist.xml` entry and
copy `batocera/icons/planck_time-image.png` to the cabinet, with
EmulationStation stopped, and then restart it (see `../AGENTS.md`). Later
deploys only replace the code.
