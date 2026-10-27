# Gate Drop

A quantum-circuit puzzle in the style of Dr. Mario, for 1 or 2 players, for
the ARQADE cabinet (Batocera, `pygame` system). Each board is a small circuit
with Pauli errors sitting on its wires. Gate pills fall onto the wires, and a
gate next to its inverse vanishes. **Clear every error on your board.**
Design: `../docs/superpowers/specs/2026-10-01-gate-drop-design.md`.

**Status:** full game, with versus (first to 2 rounds) and Dr. Mario-style
single player (levels, score, top-10 initials). Each player sets their own
level and speed. Chiptune sound effects (no music: on the cabinet only
Overquqed has music), `--input-test`, and a Batocera deploy script. Button numbers follow the ones confirmed on the cabinet.

## How to play

- **Title:** a menu of 1 PLAYER, 2 PLAYERS and QUIT. The stick moves the
  cursor, A picks the row, and A on QUIT leaves the game, back to the
  cabinet's game list. Start always plays, whatever row is lit (with the
  mode last picked).
- **Setup:** each player picks a **level** (1-10; level n has 2n + 2 errors)
  and a **speed** (LOW, MED, HI), then presses A. With 2 players this is a
  handicap: each sets their own, and the round starts when both are ready.
- **How to play:** before every match started from the setup screen, a card
  shows the goal, a looping demo on a small 4-wire board (a pill slides
  over, turns twice, drops onto an X and a Z bug, and both pairs cancel; it
  runs on the real board rules) and the controls on a drawing of the
  cabinet's buttons, each lit while the demo uses it. Any button starts the
  match, but only after 0.3 s, so the A that readied up can't skip it; the
  stick doesn't. A rematch or the next round skips the card.
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

| Action | Pad | P1 keyboard | P2 keyboard |
|---|---|---|---|
| Move / menus | stick or d-pad | W A S D | arrows |
| Soft drop | stick down | S | down arrow |
| Rotate clockwise / anti-clockwise | A / B | B / V | L / K |
| Confirm, ready (menus) | A or Start | B or Space | L or Enter |
| Back, un-ready (menus) | B | V | K |
| Skip HOW TO PLAY | any button | any key | any key |
| Pause (resume or quit to the title) | Start | Space | Enter |
| Quit | QUIT on the title, Start + Select, or hold Select 2 s on the title | Space + L-Shift | Enter + R-Shift |

In single player, either pad plays. The keys are the layout shared by all
the games (`../common`); on-screen hints name the keys or the pad buttons,
whichever each player last used. There is no quit key (Esc leaves
fullscreen in a browser). On the cabinet the loader passes `--no-keyboard`. High scores are kept in
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

In the browser (pygbag's test server on http://localhost:8000), from the
repo root:

```bash
uv run --project tools tools/build_web.py --serve gate-drop
```

In the browser, quitting (Start + Select, or QUIT on the title) goes back to
the title and tells the page around the game (`arqade:quit`). Pads use the
cabinet's button numbers by default; `--pad-layout xbox` reads an Xbox-style
pad on a PC instead, and browser gamepads use the browser's standard layout.

## Layout

| Module | Role |
|---|---|
| `board.py` | One board: pills, rotation, settling, the cancellation scan, chains, noise. Pure, fully tested. |
| `levels.py`, `hiscores.py` | Seeded error layouts (same level, same layout); the top-10 table. Pure, tested. |
| `match.py` | Title, setup, how to play, countdown, rounds, levels, results, initials, the attack exchange. Pure, tested. |
| `tutorial.py` | The HOW TO PLAY card's words and its scripted demo round. Pure, tested. |
| `sprites.py`, `render.py` | Procedural SNES-style pixel art at 480x270 (x4 on the cabinet). |
| `audio.py` | Chiptune effects (menu move, confirm and back too), adapted from Overquqed's `audio.py`. No music. |
| `input.py`, `config.py` | Pads and the keyboard; every tuning number, colour and button. |

## Deploying to the cabinet

```bash
./deploy_batocera.sh                    # or ./deploy_batocera.sh root@10.42.0.100
```

The first time, also add the `batocera/gamelist.xml` entry and the icon on the
cabinet, with EmulationStation stopped, then restart it (see `../AGENTS.md`).
Later deploys only replace the code.
