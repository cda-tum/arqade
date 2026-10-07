# Qlimbers Time Trial Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: use superpowers:subagent-driven-development
> (recommended) or superpowers:executing-plans to implement this plan task by task.

**Goal:** add a single-player time trial with a fastest-clears table to Qlimbers
(`quantum-towers/`), as specified in
`docs/superpowers/specs/2026-10-05-qlimbers-time-trial-design.md`.

**Architecture:**
- Two pure modules: `solo.py` (the equal-difficulty tower and a pausable timer) and
  `times.py` (the top-10 fastest clears).
- `main.py` gains a title-screen player-count choice and a `run_solo` loop, built on
  the existing per-player logic.
- `screens.py` gains the countdown and timer HUD, the initials screen and the table.

**Tech stack:** Python 3.11, pygame 2.5.2, uv, pytest. Run commands from
`quantum-towers/`.

## Global constraints

- `pygame==2.5.2`, Python `>=3.11,<3.12`. No new dependencies.
- **Line endings:** existing files are CRLF, so keep each file's style and never mix
  within a file. New files are LF. Check with `git ls-files --eol quantum-towers`.
- **Cabinet conventions** (`../AGENTS.md`):
  - A confirms, B goes back, and Start starts and pauses.
  - Start + Select quits.
  - 60 s idle returns to the title.
  - A title reached from QUIT TO TITLE waits for its buttons to be released.
- **Raw buttons:** A = 1, B = 2, Start = 9, Select = 8. The stick is axis 0/1.
- **ASCII kets** (`|0>`).
- **Versus mode is unchanged:** its tests keep passing.
- **Commits:** gitmoji style, ending with
  `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`. Stage only
  `quantum-towers/` paths.

### Task 1: `solo.py` and `times.py` (pure, tested)

**Files:**
- Create `src/quantum_towers/solo.py`, `src/quantum_towers/times.py`,
  `tests/test_solo.py` and `tests/test_times.py`.
- Modify `config.py` to add `SOLO_TOTAL_PRESSES`, `SOLO_COUNTDOWN = 3.0`,
  `TIMES_FILE = Path.home() / ".quantum_towers_times.json"` and `TIMES_SLOTS = 10`.

**Interfaces (produced):**
- `solo.minimum_total(targets: list[State]) -> int` is the sum over floors of
  `search.minimum_steps(prev, t)`, starting from `quantum.zero_state()`.
- `solo.equal_difficulty_tower(rng, floors: int, total: int, extra: int = 2) -> list[State]`
  returns `floors + extra` targets whose first `floors` have
  `minimum_total == total`. It is deterministic per rng.
- `class Timer` has `update(dt)` (it ignores dt while `paused`), a `paused: bool`
  attribute, a `seconds` property and `format() -> str` (`m:ss.cc`).
- `times.Entry(name: str, seconds: float)` and `times.Times(path: Path | None)`.
  `Times` has `entries` (fastest first, at most 10), `qualifies(seconds)`,
  `add(name, seconds) -> rank or -1` (which saves when `path` is set) and
  `format_time(seconds)`, the same format as `Timer`.

**Steps:**
1. Measure the constant. Generate 2000 fully random towers with
   `targets.generate_target_sequence(rng, 16)` and take the median `minimum_total`.
   Pin it as `SOLO_TOTAL_PRESSES`, with a comment giving the method and the observed
   range.
2. Write the tests first:
   - over 200 seeds, `minimum_total(tower[:16]) == SOLO_TOTAL_PRESSES`;
   - every target differs from its predecessor;
   - the same seed gives the same tower;
   - 50 generations take under 2 s in total;
   - the timer formats `0:07.25` and `1:03.00`, and freezes when paused;
   - times sort fastest first and keep the top 10;
   - `qualifies` works, and `add` returns the rank;
   - a missing or broken file gives an empty table;
   - a save then load round-trips (use `tmp_path`).
3. Implement. A suggested generator: build floor by floor. After each floor, check
   that the remaining total is achievable, i.e. between `remaining_floors * 1` and
   `remaining_floors * 6`. If it isn't, or the last floor misses, restart that attempt.
   Cache `minimum_steps` per state pair; there are only 16 reachable states.
4. Run `uv run pytest -q`, then commit:
   `feat: :stopwatch: Qlimbers: equal-difficulty solo towers, timer and fastest-clears table`.

### Task 2: the title choice, the solo loop and the screens

**Files:**
- Modify `src/quantum_towers/main.py`, `src/quantum_towers/screens.py` and, if needed,
  `visuals.py`.
- Create `tests/test_solo_flow.py`.

**Behaviour:** follow the spec's "Flow" section exactly.
- `run_title_screen` returns `"1p"`, `"2p"` or `"quit"`. The stick moves between
  1 PLAYER and 2 PLAYERS, and A or Start confirms. Keep the release-before-arming
  logic.
- `run_solo(surface, window, sounds, show_fps, times) -> str` returns `"done"`,
  `"quit"`, `"idle"` or `"title"`:
  - one centred tower from `equal_difficulty_tower`;
  - input from both pads merged, with either pad able to play;
  - the countdown, then the timer;
  - pause through the existing `pause.py` menu, with the timer paused;
  - the stun on a wrong confirm, as versus;
  - no charges or attacks;
  - on reaching the top, the finish banner with the time, then hand over.
- `run_initials(...)` and `run_times_table(...)` follow Gate Drop's `NameEntry` logic
  (`gate-drop/src/gate_drop/match.py`) and its table layout (`render.py`
  `_hiscores`), restyled to Qlimbers' palette and fonts.
- `main()`: on `"1p"`, run solo. If it finished and the time qualifies, run initials,
  then the table; if it finished without qualifying, just the table. Then back to the
  title. `"2p"` runs the existing versus flow, unchanged.

**Tests** (headless, `SDL_VIDEODRIVER=dummy`; see the existing tests for how screens
are driven):
- the title choice;
- a scripted solo run that solves floors with the BFS's own action sequence, posting
  events or stubbing input. Assert the timer advances, freezes while paused, and that
  the finish reports the time;
- the initials entry logic;
- times-table drawing as a smoke test.

**Steps:** write the tests, implement, run `uv run pytest -q`, run the game windowed
and take a snapshot of each new screen to check it by eye, then commit:
`feat: :stopwatch: Qlimbers: single-player time trial with fastest clears`.

### Task 3: README and deploy

- README: a "Single player: time trial" section covering the flow, fair towers and
  where times are kept.
- Deploy with `./deploy_batocera.sh` when the cabinet is idle (no game running). No
  gamelist change is needed, because the ROM is already registered. Commit the
  README:
  `docs: :memo: Qlimbers: the time trial`.
