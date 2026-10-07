# Planck Time Crossovers Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: use superpowers:subagent-driven-development
> (recommended) or superpowers:executing-plans to implement this plan task by task.

**Goal:** nine new Planck Time microgames, one per other arqade game, as specified in
`docs/superpowers/specs/2026-10-05-planck-time-crossovers-design.md`.

**Architecture:**
- One module per microgame in `planck-time/src/planck_time/microgames/`, each with one
  `@register`ed `Microgame` subclass.
- They are discovered automatically and checked by `tests/test_microgames.py`. No other
  file changes, except an optional focused test file per microgame and, in Task 4, the
  README.

**Tech stack:** Python 3.11, pygame 2.5.2, uv, pytest. Run commands from
`planck-time/`.

## Global constraints

- `pygame==2.5.2`, Python `>=3.11,<3.12`. No new dependencies.
- **No imports from the other games' packages.** Each game is an independent package,
  so reimplement the few lines of rules you need.
- **The GBA palette** (`palette.py`, every channel a multiple of 8) and the `pixel.py`
  helpers. The screen is 240x160.
- **ASCII kets.** Every glyph in VERB and CAPTION must be in Press Start 2P (the
  metadata test checks this).
- **LF line endings.**
- **The bar to pass:** `uv run pytest -q` is green. Lint is
  `uvx --from 'ruff==0.15.22' ruff check src tests tools`.
- **Commits:** gitmoji style, ending with
  `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`. Stage explicit paths
  only.

## Each microgame task follows the same steps

1. Read the spec's shared rules and the task's three rows and notes.
2. Read `microgames/base.py`, two existing microgames as models (`measure.py` for `a`,
   `sort.py` or `fix.py` for stick and stick+a), `pixel.py` and `palette.py`.
3. For each microgame:
   - read its source game's README and its sprite and drawing code;
   - write any focused rule tests (e.g. "exactly one answer is right");
   - implement the module;
   - run `uv run pytest -q tests/test_microgames.py -k <ClassName>`.
4. Run `uv run python tools/snapshot.py OUT` and look at every new sheet:
   - is it readable at first sight?
   - is the hint line on screen?
   - is it recognisably the source game?

   Fix what isn't.
5. Run the full suite and the lint, then commit:
   `feat: :joystick: Planck Time: <VERB>, <VERB> and <VERB> (arqade crossovers)`.

### Task 1: RETURN! (Quantum Pong), SPLIT! (Qurves), SURF! (Ion Surfer)

**Files:** create `microgames/ret.py` (`return` is a keyword), `microgames/split.py`
and `microgames/surf.py`, plus optional `tests/test_crossovers_1.py`.

### Task 2: CLIMB! (Qlimbers), SERVE! (Overquqed), DROP! (Gate Drop)

**Files:** create `microgames/climb.py`, `microgames/serve.py` and
`microgames/drop.py`, plus optional `tests/test_crossovers_2.py`.

### Task 3: CORRECT! (Pauli Invaders), ROUTE! (Superconductor), MATCH! (Brawl-Ket)

**Files:** create `microgames/correct.py`, `microgames/route.py` and
`microgames/match.py`, plus optional `tests/test_crossovers_3.py`.

Pauli Invaders lives in `error-invaders/`, and Qlimbers in `quantum-towers/`.

### Task 5: TILE! (colour code) and MERGE! (lattice surgery)

Spec: `docs/superpowers/specs/2026-10-05-planck-time-code-microgames-design.md`. The same
steps as the crossovers apply, and these two are not crossovers.

**Files:** create `microgames/tile.py` and `microgames/merge.py`, plus
`tests/test_code_microgames.py`, which checks:

- TILE!'s colourings are valid and every blank has a unique answer;
- MERGE! has exactly one winning configuration.

The commit is
`feat: :joystick: Planck Time: TILE! and MERGE! (colour code, lattice surgery)`.

### Task 4: integration, README and deploy (the controller)

- Merge the three tasks' commits onto the branch, then run the full suite.
- README:
  - the microgame table gains the eleven rows (the nine crossovers, TILE! and MERGE!);
  - "all 12 microgames" becomes "all 23".
- Run a snapshot pass over all 21.
- Check performance: time `step` plus `draw` for each new microgame on a plain
  surface. The Pi budget is 16.7 ms per frame for two screens.
- Deploy with `planck-time/deploy_batocera.sh` when the cabinet is idle.
- Commit the README: `docs: :memo: Planck Time: the arqade crossovers`.
