# Gate Drop

A quantum-circuit puzzle in the style of Dr. Mario, for 1 or 2 players, for
the ARQADE cabinet (Batocera, `pygame` system). Each board is a small circuit
with Pauli errors sitting on its wires. Gate pills fall onto the wires, and a
gate next to its inverse vanishes. **Clear every error on your board.**
Design: `../docs/superpowers/specs/2026-10-01-gate-drop-design.md`.

**Status:** full game, with versus (first to 2 rounds) and Dr. Mario-style
single player (levels, score, top-10 initials). Each player sets their own
level and speed. Chiptune sound and music, `--input-test`, and a Batocera
deploy script. Button numbers follow the ones confirmed on the cabinet.

## How to play

- **Title:** the stick picks 1 or 2 players.
- **Setup:** each player picks a **level** (1-10; level n has 2n + 2 errors)
  and a **speed** (LOW, MED, HI), then presses A. With 2 players this is a
  handicap: each sets their own, and the round starts when both are ready.
- **Pills:**
  - A gate pill carries two single-qubit gates (H, X, Y, Z, and the rare T
    and T-dagger, 1 half in 26 each). Once it lands, the halves are independent gates.
  - A CNOT pill (steel, control `●`, target `⊕`) always lies across two
    neighbouring wires and stays rigid. If one side lands first, it leaves a
    gap under the other, and an idle wire is just the identity.
- **Cancelling:** only along a wire (a column).
  - A gate next to its inverse vanishes: `XX`, `YY`, `ZZ`, `HH`, and T with
    T-dagger. `T T` doesn't cancel, because it is an S gate, not the
    identity.
  - Gaps are skipped, nothing cancels across a CNOT half, and two CNOTs
    stacked the same way round cancel.
  - **Sandwiches:** `H X H` becomes `Z`, and `H Z H` becomes `X`.
  - **CNOT propagation:** an X dropped on a CNOT's control (or a Z on its
    target), with that same Pauli right under each half, clears all three,
    and the CNOT stays. It's exact: an X after the control equals an X on
    both wires before the CNOT (CNOT · X⊗I · CNOT = X⊗X), so the X's cancel
    pairwise. This is the only way to clear errors on two wires at once.
- **Versus:**
  - A 2-step chain, or one pass with 3 or more matches, drops **2 T gates**
    on your rival. A 3-step chain drops 3, and the maximum is 4.
  - T gates only clear with a T-dagger, so they don't just cancel away.
  - Clear all your errors first, or make your rival overflow, to take the
    round. First to 2 rounds wins.
- **Single player:**
  - Clear the board to go up a level.
  - Each error scores `100 x speed (1, 2 or 3) x 2^(chain step - 1)`, with
    the multiplier capped at 8. A level clear adds `500 x level x speed`.
  - Overflowing ends the game, and a top-10 score gets your initials.

| Action | Cabinet | P1 keyboard | P2 keyboard |
|---|---|---|---|
| Move / menus | stick | W A S D | arrows |
| Soft drop | stick down | S | down arrow |
| Rotate clockwise / anti-clockwise | A / B | Q / E | . / , |
| Confirm, ready (menus) | A or Start | 1, Enter | 2, keypad Enter |
| Back, un-ready (menus) | B | Backspace | Delete |
| Pause (resume or quit to the title) | Start | P | End |
| Quit | Start + Select, or hold Select 2 s on the title | Esc | Esc |

In single player, either pad plays. The keyboard is a dev fallback only; on
the cabinet the loader passes `--no-keyboard`. High scores are kept in
`~/.gate_drop_scores.json`, outside the package, so a redeploy keeps them.

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
| `levels.py`, `hiscores.py` | Seeded error layouts (same level, same layout); the top-10 table. Pure, tested. |
| `match.py` | Title, setup, countdown, rounds, levels, results, initials, the attack exchange. Pure, tested. |
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
