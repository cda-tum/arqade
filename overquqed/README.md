# Overquqed

A cooperative 2-player quantum kitchen for the Arqade cabinet. You and a
friend run the **ancilla kitchen of a fault-tolerant quantum computer**.
Guests (personified error-correction codes and protocols) order quantum
states. You pull fresh qubits from the Dilution Fridge, run them through
kitchen appliances that are really quantum gates, and serve them before
they decohere.

Everything is original: the pixel art is defined in code, the music and
sound are synthesised at start-up, and the name and look are not taken from
any commercial game.

## Status

v1 is complete:

- a tutorial and three levels
- 2-player co-op, plus a 1-player mode where you swap between the chefs
- attract mode
- hiscores with team initials
- tested headless

It has not been played on the cabinet yet. See [On the cabinet](#on-the-cabinet)
for what still needs checking there.

## The quantum part

The physics is exact, not decoration:

- **Bloch Bowls.** Every qubit is a glass sphere with its Bloch vector drawn as
  an arrow. |0> points up and |1> points down. |+> points toward you on the
  equator (down-left on screen) and |-> points away from you.
- **Gates are real.** Each appliance is a real gate:
  - Pauli-X Flipper = X
  - Hadamard Blender = H
  - Phase Stirrer = Z
  - CNOT Waffle Iron = CNOT

  The arrow swings around the gate's actual rotation axis (X = π about x,
  H = π about (x+z)/√2), so gate order matters. X then H gives |->, but H then
  X gives |+>. Blending twice un-blends (H² = I).
- **Entanglement.** Bowls joined by the Waffle Iron become a linked tray with a
  gold thread. In a Bell pair each bowl's own arrow shrinks to nothing, because
  the information is in the link. Putting |+> in the control slot and |0> in
  the target makes |Φ⁺⟩. Getting the orientation wrong gives a plain product
  state. A Bell tray as control plus a fresh |0> as target makes a 3-qubit GHZ.
- **States are simulated exactly.** Items are 1–3 qubit density matrices
  (`quantum.py`, pure Python, no numpy).
- **Noise is real T1/T2.** Each level applies amplitude damping plus pure
  dephasing, lazily, whenever an item is touched and on a 10 Hz refresh.
  Arrows shrink or droop toward |0>, bowls frost over, and the fidelity bar
  drops.
- **Serving.** The pass compares the exact fidelity F = ⟨ψ|ρ|ψ⟩ (maximised
  over qubit orderings) against every open order and picks the best match.
  Below **F = 0.8** the guest refuses, a nod to the fault-tolerance threshold.
  A receipt prints the circuit the dish actually went through.

## Levels

| Level | Idea | Physics |
|---|---|---|
| Training Day | Chef Ket teaches \|0>, \|1>, \|+> and the 0.8 threshold in under a minute | no noise |
| Superconducting Snack Bar | open kitchen, single-qubit orders, learn gate order | T1 100 s, T2 45 s |
| Ion Trap Trattoria | two trap zones joined only by conveyor belts; only 4 qubits in the fridge (served bowls come back dirty; recycle them in the Reset Sink); Bell pairs need both chefs | T1 200 s, T2 120 s, gates ×2 slower |
| Cosmic Cafe | every dish up to GHZ, a two-chef Waffle Iron, cosmic-ray bursts that scramble a 3×3 area and jam its stations | T1 240 s, T2 160 s |

Maps and every tunable (spawn rates, patience, stars, noise) are in
`levels.py`.

## Setup and running

```bash
uv sync
uv run python -m overquqed                 # windowed, 960x720 (an exact 2x)
uv run python -m overquqed --fullscreen
uv run python -m overquqed --window-size 1440x1080 --fps
```

`python -m overquqed.main` works too, like the sibling games. F3 toggles
the FPS overlay. The internal resolution is 480×360, which scales by exactly
3 onto the cabinet's 1920×1080 panel, so pixels stay crisp.

### Input test

```bash
uv run python -m overquqed --input-test
```

This mode shows every joystick's axes, buttons and hats, which logical
actions each pad resolves to, and the keys held down. You can also open it
with F1 on the title screen. Leave with Esc, or hold Select for 2 s.

## Controls

| Action | Cabinet (either pad) | P1 keyboard | P2 keyboard |
|---|---|---|---|
| Move | stick | arrow keys | I J K L |
| Pick up / put down / serve | A (raw 1) | A | O |
| Use station (tap or hold) | B (raw 2) | B | P |
| Swap chef (1-player) | Y (raw 3) | Y | U |
| Start / pause | Start | Enter | 2 |
| Back (menus) | B, or Select | B, or Space | P, or Backspace |

- **Using stations.** Tap B on the Flipper and the Stirrer. Hold B on the
  Blender, the Waffle Iron and the Sink; a ring shows progress, and letting go
  pauses it.
- **Menus.** A or Start confirms, B goes back: the cabinet's shared button
  convention (see `../AGENTS.md`). Select also goes back.
- **Title.** Two rows, PLAY and QUIT; the stick picks one and A takes it.
  Start always plays, whichever row is selected. QUIT exits back to the
  cabinet's game list (or the launcher's menu) at once, and B does nothing
  there. When the attract demo starts, the selection goes back to PLAY.
- **HOW TO PLAY.** Every kitchen picked from the level select (Training Day
  too) opens with a card: the goal in three lines, a tiny kitchen where the
  game's own bot cooks a |+> and a |1> on the real rules, with a caption for
  P1's chef, and the pad's buttons. Any button on either pad starts the
  round once the card has been up 0.3 s; the stick doesn't. A button held
  through it counts as released until it really is, so it never works a
  station or pauses. RESTART from the pause menu skips the card.
- **Quitting.** QUIT on the title, or Start + Select on one pad from
  anywhere. Holding Select for 2 s on the title screen also quits. Esc quits
  from the title when the keyboard is enabled.
- **Keyboard on the cabinet.** The cabinet loader passes `--no-keyboard`
  because Batocera's evmapy turns P1's pad into key presses (see
  `../AGENTS.md`). P1's dev keys are deliberately the keys evmapy sends for the
  same buttons, and P2's avoid all of them. `tests/test_config.py` enforces
  both rules.
- **Idle.** Any screen left alone for 60 s falls back to the title. After 12 s
  on the title, bots start cooking a demo round.
- **Hiscores.** They live in `~/.overquqed_hiscores.json`, which is
  `/userdata/system` on Batocera, so redeploys keep them.

## On the cabinet

```bash
./deploy_batocera.sh                     # or ./deploy_batocera.sh root@<cabinet-ip>
```

The code goes to `/userdata/games/overquqed/overquqed/` and the loader to
`/userdata/roms/pygame/overquqed.pygame`. It runs with
`main(["--fullscreen", "--no-keyboard"])`, the same shape as the other games.

The first time you deploy:

1. **Icon.** Copy `../batocera/icons/overquqed-image.png` to
   `/userdata/roms/pygame/images/`.
2. **Menu entry.** Merge the Overquqed `<game>` entry from
   `../batocera/gamelist.xml` into the cabinet's
   `/userdata/roms/pygame/gamelist.xml` by hand. Don't overwrite the file;
   it holds the play statistics.
3. **Rescan.** Rescan or restart EmulationStation once so the new ROM appears.

Still to verify on the hardware:

- frame rate with `--fps`
- sound level

## Tests

```bash
uv run pytest
```

| Area | What's covered |
|---|---|
| Quantum core | gate identities, every recipe and wrong-order case, CNOT orientation, entanglement, global phase, permutation-maximised fidelity, trace/positivity of every noise channel, analytic T1/T2 decay curves |
| Rules | chef movement and collision, every station, belts, the limited fridge and dirty bowls, the two-chef press (and its half-speed solo mode), cosmic rays, orders, scoring, hiscores |
| Playthroughs (`test_bot.py`) | bots play whole rounds of every level on the real rules. They must make every dish, including all Bell states and GHZ, and reach 3 stars. The bot also completes the tutorial script. |
| Smoke (`test_smoke.py`) | drives every scene headless with scripted input: menus, the title's PLAY / QUIT, the HOW TO PLAY card (its 0.3 s guard, stick vs buttons, held buttons, RESTART skipping it, its demo kitchen), pause, results, quit combo, idle reset, attract mode |

## Dev tools

- `uv run python tools/snapshot.py OUT_DIR` renders every screen to PNGs at
  3× headless, for reviewing the art.
- `uv run python tools/bench.py [snackbar|trattoria|cosmic]` measures the frame
  cost of a bot-played round. It's about 0.1 ms per frame on a laptop, far
  inside the Pi's 16.7 ms.

## Layout

| Module | Role |
|---|---|
| `quantum.py`, `recipes.py` | exact simulation and target states (pure Python) |
| `world.py`, `stations.py`, `guests.py`, `scoring.py`, `levels.py` | game rules (no pygame) |
| `bot.py` | planner used by attract mode and tests |
| `render.py`, `hud.py`, `dining.py`, `sprites.py`, `ket.py`, `circuit.py` | drawing |
| `game.py`, `scenes.py`, `round_scene.py`, `howto.py`, `tutorial.py`, `attract.py` | flow |
| `input.py`, `display.py`, `audio.py`, `hiscores.py` | platform |

## Fonts

Press Start 2P (SIL Open Font License, `assets/fonts/OFL.txt`), the same font
as the sibling games.

- It has Φ and Ψ, checked by rendering and hashing the glyphs.
- It has no ⟩ bracket and no superscripts, so `ket.py` draws those as pixel
  masks. That's how labels can show proper `|Φ⁺⟩` kets.
