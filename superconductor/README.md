# Superconductor

Route two-qubit gates across a superconducting chip before they decohere. A 1–2 player
pygame game for the IconicArcade Raspberry Pi 4 cabinet (Batocera, `pygame` system),
packaged the same way as the other games in this repo.

**Status:** playable prototype. It has 1 player, co-op and versus modes, square and brick
chips, crossing routes with collisions, four chip specials, a coherence timer, scoring,
high scores, an input-test mode and a Batocera deploy script. There is no circuit mode
yet.

## Gameplay

Pairs of qubits light up on a 5×5 chip in the same color: each pair is a two-qubit gate
waiting to happen. Draw a route between them, one coupler at a time. When the route
reaches the partner, a qubit travels along it (a few seconds), and the gate fires on
arrival.

- **Couplers are exclusive, qubits are shared.** The couplers on a committed route are
  reserved, so no other route can use them. Each coupler is released as soon as the
  travelling qubit has passed it, so routes open up again from behind. Routes *may*
  cross at a qubit, but every qubit has a finite size: if two travelling qubits are
  inside the same one at the same time, they crash, both gates are lost, and you lose a
  life. While you draw, a blinking red X marks where your route would crash if it went
  off right now.
- **Coherence timer.** The ring around a waiting pair is its coherence. At zero the pair
  decoheres and costs one of 3 lives. The game starts with two pairs waiting. After that,
  pairs arrive faster and decohere sooner as the game goes on.
- **Score** = 100 × fidelity + up to 50 for coherence left. Each hop beyond the shortest
  possible route multiplies the fidelity by 0.9.
- You never roam the chip freely: your cursor always starts on an endpoint ("station") of
  a waiting pair, marked by a wobbling rounded square in your color. You cycle between
  stations with a button. When you finish a route, the cursor jumps to the oldest pair
  still waiting.

**Specials** turn up on free parts of the chip for a while. They never land on a route
that is drawn or in progress, and never share a qubit with a station:

| Special | Looks like | Effect | Lasts |
|---|---|---|---|
| Miscalibrated coupler | orange wobbly coupler | 3× slower, and the gate's fidelity × 0.8 | 20 s, then "recalibrated" |
| Defect coupler | broken red coupler with an X | can't be used at all | 15 s, then "restored" |
| Speed qubit | gold chevrons | every qubit passing over it travels 2× faster (stacks up to 4×) | 25 s |
| Bell pair | two ringed qubits linked by a bowed dashed line | a route entering one end continues from the other end, once | 30 s, or until used |

They unlock over time: miscalibrations from the start, speed qubits after 25 s, defects
after 40 s and Bell pairs after 70 s. The values are in `config.py`.

**Chips:** *Square* couples every grid neighbour (4 couplers per qubit, as on Google's
chips). *Brick* keeps every other vertical coupler, staggered like a brick wall, which is
hexagonal connectivity (3 per qubit, the graph behind IBM's heavy-hex) without any
diagonal lines.

**Modes:**
- **1 Player:** one chip.
- **Co-op:** both players route on the same chip, with shared score and lives. A pair one
  player has selected can't be taken by the other. If one player commits a route through
  the other's half-drawn route, the half-drawn one is cut back.
- **Versus:** two chips side by side, fed the identical sequence of pairs (same seed).
  Each player has their own lives. Once both chips have decohered, the higher score wins.

## Setup and run (dev machine)

Requires [uv](https://docs.astral.sh/uv/).

```bash
cd superconductor
uv sync
uv run python -m superconductor.main                # windowed, keyboard/joystick
uv run python -m superconductor.main --fullscreen
uv run python -m superconductor.main --input-test   # live joystick/keyboard state
uv run pytest
```

The game renders at 1280×720 (16:9, so versus fits two chips). **F3** toggles the FPS
overlay, and **F1** on the title screen opens the input test.

### Controls

| | Cabinet pad | P1 keyboard | P2 keyboard |
|---|---|---|---|
| Draw route / step back | Stick | E S D F | Arrow keys |
| Next station | A or R | J | `.` |
| Previous station | L | I | N |
| Other end of this pair | B | K | `,` |
| Undo one step | X | U | M |

- Moving back the way you came also undoes one step. A Bell jump has no "way back" on the
  stick, so undo it with X. Reaching the partner commits the route automatically.
- On the title screen, use the stick to pick mode and chip, and A or Start to play.
- In-game, Start (or P) pauses. Select (or Esc) pauses too, and from the pause menu it
  goes back to the title.
- **Quit:** hold Start and Select together on either pad, or hold Select (or press Esc) for
  2 s on the title screen.
- Start is raw 9 and Select raw 8, confirmed on the cabinet. B resumes from the pause menu
  and leaves the game-over screen, per the cabinet's button convention (`../AGENTS.md`).
- The keyboard is a dev fallback only. P1's keys avoid `l x r b y a`, which the cabinet's P1
  encoder types too (see `../AGENTS.md`). On the cabinet the loader passes `--no-keyboard`.

High scores (per mode and chip, not for versus) are saved to
`~/.superconductor_hiscores.json`, which is `/userdata/system/` on Batocera.

## Code layout

| File | What |
|---|---|
| `lattice.py` | The chip graph: square and brick couplers, neighbours, distances |
| `rules.py` | All game rules (spawning, drawing, committing, travel, collisions, specials, scoring), pure Python and unit tested |
| `input.py` | Pad and keyboard to actions, with stick auto-repeat |
| `game.py` | Menus, drawing, sound and the main loop |
| `config.py` | Input mapping and every tuning constant (speed, timers, ramp, scoring) |

## Deploy to the cabinet

```bash
./deploy_batocera.sh                  # defaults to root@batocera.local
./deploy_batocera.sh root@10.42.0.100 # if .local resolution isn't working
```

This is a new ROM, so EmulationStation needs one rescan or restart before it appears.
For the menu name and icon, merge the `superconductor` entry from
`../batocera/gamelist.xml` into the cabinet's gamelist, and copy
`../batocera/icons/superconductor-image.png` to `/userdata/roms/pygame/images/` (see
`../AGENTS.md`).

## Ideas parked for later

- Circuit mode: a circuit window with a dependency graph instead of random pairs (gates
  that don't depend on each other can run in any order).
- More specials: meeting in the middle (both ends travel), three-qubit chains (GHZ), chip
  regions going offline for calibration.
- In versus, specials can land in different places on the two chips, because where one
  fits depends on each chip's state. Only the pairs are guaranteed identical.
- Bigger chips and real topologies (heavy-hex with coupler qubits).
