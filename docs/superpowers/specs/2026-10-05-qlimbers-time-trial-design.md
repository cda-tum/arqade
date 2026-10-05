# Qlimbers: single-player time trial: design

Qlimbers (`quantum-towers/`) is a two-player race: each player applies X, Y, Z, H and
RESET to their qubit to match each floor's target state, and pushes up to confirm the
climb. This adds a **single-player time trial** with a **fastest-clears table**.

## Flow

- **Title.** The stick picks **1 PLAYER** or **2 PLAYERS**, and A or Start begins. Two
  players play the existing versus mode, unchanged.
- **Solo run.**
  - **Layout:** one tower, centred on screen, playable from either pad. It uses the
    same gates, button legend and push-up-to-confirm as versus.
  - **Countdown:** 3, 2, 1, GO.
  - **Timer:** it starts at GO and is shown large at the top as `m:ss.cc`.
  - **Wrong confirms:** they stun for `STUN_DURATION` (1 s), as in versus. That costs
    time with no further penalty.
  - **No charges, attacks or charge HUD.** A minimum-press climb still shows its
    "PERFECT" feedback and has no effect on the time.
- **Finish.**
  - Reaching floor `TOWER_HEIGHT` (16) stops the clock and shows the time.
  - If it is in the top 10, the player enters 3 initials. The stick up and down
    changes the letter, left and right move, A goes on and finishes on the last letter,
    and B steps back. This is Gate Drop's entry screen.
  - Then the **FASTEST CLEARS** table: rank, initials and time, with the new entry
    blinking. It returns to the title after 8 s, or on A, B or Start after 1 s.
- **Cabinet conventions:**
  - Start pauses with RESUME and QUIT TO TITLE, and the timer freezes while paused.
  - Start + Select quits.
  - The 60 s idle timeout returns to the title, during the run, initials entry and
    table. An initials entry abandoned by the idle timeout is saved as typed so far.

## Fair towers: equal difficulty

Every solo run is a fresh random tower. Its total of minimum presses always equals one
constant, `SOLO_TOTAL_PRESSES`, so times are comparable without anyone memorising a
tower.

- The minimum for floor `f` is `minimum_steps(target[f-1], target[f])`, with
  `target[-1] = |0>`. This is the real breadth-first minimum, counting from the state
  the player is in after the previous floor.
- **The generator** (`solo.equal_difficulty_tower(rng, floors, total)`) builds a chain
  floor by floor with `targets.generate_target`. It retries until the running minimum
  total equals `total` after `floors` floors: for example, it redraws the remaining
  floors when the running total is no longer reachable.
  - It must be fast enough to run at the start of every run, well under 100 ms.
  - It must be deterministic for a given rng.
- **The constant** is the median total over many fully random 16-floor towers, so a
  balanced tower feels like a normal one. It is measured once and pinned in
  `config.py` with a comment explaining how.
- The tower is generated with `TOWER_HEIGHT + 2` targets, as versus does, so the top
  floor can still look up its next target. Only the first `TOWER_HEIGHT` targets count
  towards the total.

## Times table

- **Storage:** `times.py`, adapted from `gate-drop/src/gate_drop/hiscores.py`. It is
  sorted **fastest first**, keeps the top 10, and stores entries as `name` and
  `seconds` (a float).
- It is saved to `~/.quantum_towers_times.json`, outside the package, so a redeploy
  keeps it. A missing or broken file means an empty table.
- `qualifies(seconds)` and `add(name, seconds)` return the new rank, or -1.

## Code

- `solo.py`: pure. It holds the equal-difficulty tower generator and a pausable
  `Timer` (`update(dt)`, `seconds`, `format()`, which returns `m:ss.cc`).
- `times.py`: pure apart from file I/O, and tested with a temporary path.
- `main.py` / `screens.py`:
  - the title's player-count choice;
  - `run_solo(...)`, the solo loop, built on the existing per-player logic in
    `player.py` and drawing helpers in `visuals.py`;
  - the countdown and timer HUD;
  - the initials and table screens.

  Versus behaviour does not change.
- **Line endings:** Qlimbers' existing files are committed with CRLF. Edits keep each
  file's existing style, with no mixing inside a file. New files use LF.

## Testing

- **The generator:**
  - every tower's minimum total equals the constant, over many seeds;
  - every floor is reachable and never a no-op;
  - the same seed gives the same tower;
  - it is fast.
- **The timer:** formatting (`0:07.25`, `1:03.00`), and pausing freezes it.
- **Times:** sorted fastest first, top 10, qualifies and rank, a missing or broken file
  gives an empty table, and a save then load round-trips.
- **The solo loop:** a headless run that solves a few floors with scripted inputs,
  checks the timer advances and freezes on pause, and checks that the finish hands over
  to initials when the time qualifies. Versus tests keep passing.
