# Gate Drop

A two-player versus puzzle in the style of Dr. Mario, for the ARQADE cabinet
(Batocera, `pygame` system). Each board is a small quantum circuit with Pauli
errors sitting on its wires. Gate pills fall onto the wires and gates that
cancel vanish. **The first player to clear every error on their board wins the
round.** Design: `../docs/superpowers/specs/2026-10-01-gate-drop-design.md`.

**Status:** full game (2-player versus, first to 2 rounds), chiptune sound
and music, `--input-test`, and a Batocera deploy script. Button numbers follow
the ones confirmed on the cabinet.

## How to play

- **Pills:**
  - Each pill is two halves. A gate pill carries two single-qubit gates (H,
    X, Y or Z); once it lands, the halves are independent gates.
  - A CNOT pill (steel, with the control `●` and the target `⊕`) always lies
    across two neighbouring wires and stays rigid. If one side lands first,
    it leaves a gap under the other, and an idle wire is just the identity.
- **Cancelling:** only along a wire (a column), never across wires.
  - Two identical gates in a row cancel: `XX`, `YY`, `ZZ`, `HH`. So does a
    gate in a row with the identical error.
  - Gaps are skipped, so `X`, gap, `X` cancels too.
  - Nothing cancels across a CNOT half, and two CNOTs stacked the same way
    round on the same two wires cancel.
  - **Sandwiches:** `H X H` becomes `Z`, and `H Z H` becomes `X`.
- **Chains:** after a clear, everything settles and may cancel again. A
  chain of n steps sends n - 1 random Pauli gates (up to 4) to your rival, and
  clearing 3 matches at once sends one more. They drop onto your rival's
  board after their pill lands.
- **Winning:** clear every error bug first, or make your rival overflow
  (their next pill can't spawn). First to 2 rounds wins; each round has 2
  more errors than the last.

| Action | Cabinet | P1 keyboard | P2 keyboard |
|---|---|---|---|
| Move | stick left / right | A / D | arrows |
| Soft drop | stick down | S | down arrow |
| Rotate clockwise / anti-clockwise | A / B | Q / E | . / , |
| Confirm (menus) | A or Start | Enter, 1 | Enter, 2 |
| Back (result screen) | B | Backspace | Backspace |
| Quit | Start + Select, or hold Select 2 s on the title | Esc | Esc |

The keyboard is a dev fallback only. On the cabinet the loader passes
`--no-keyboard`.

## Setup (dev machine)

Requires [uv](https://docs.astral.sh/uv/).

```bash
cd gate-drop
uv sync
uv run python -m gate_drop          # windowed
uv run python -m gate_drop --fps    # with the FPS overlay
uv run pytest
uv run python tools/snapshot.py /tmp/gate-drop-snaps   # render a scripted match to PNGs
```

## Layout

| Module | Role |
|---|---|
| `board.py` | One board: pills, rotation, settling, the cancellation scan, chains, noise. Pure, fully tested. |
| `levels.py` | Seeded error layouts, shared by both boards. Pure, tested. |
| `match.py` | Title, countdown, rounds, results, the attack exchange. Pure, tested. |
| `sprites.py`, `render.py` | Procedural SNES-style pixel art at 480x270 (x4 on the cabinet). |
| `audio.py` | Chiptune effects and music, adapted from Overquqed's `audio.py`. |
| `input.py`, `config.py` | Pads and dev keyboard; every tuning number, colour and button. |

## Deploying to the cabinet

```bash
./deploy_batocera.sh                    # or ./deploy_batocera.sh root@10.42.0.100
```

The first time, also add the `batocera/gamelist.xml` entry and the icon on the
cabinet, with EmulationStation stopped, then restart it (see `../AGENTS.md`).
Later deploys only replace the code.
