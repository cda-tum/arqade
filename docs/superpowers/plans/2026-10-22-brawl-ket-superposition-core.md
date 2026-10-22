# Brawl-Ket SUPERposition, part 1 (the core and DOS's BLUE SCREEN OF DEATH) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give every fighter the SUPERposition bar (green and purple halves, filled by fighting
in both bases), fire a super with A+B, freeze the fight for the call, and build the first super
end to end: DOS's BLUE SCREEN OF DEATH.

**Architecture:** The bar is a small pure class (`superpos.py`, `Meter`), owned per player by
the `Match` for a whole match and handed to every round's `Fight`, which fills it where damage
is applied (`_apply_strike`). A super is an ordinary `Move` with `kind="super"` and colour
`BOTH` (so the existing colour rule already lets it hurt either basis, as a throw does) in the
Character's `extra["super"]`. The Fighter starts it from its press buffer when both A and B
are in it and the fight says the bar is full (`Fighter.super_ready`); the fight then empties
the bar and freezes everything for `SUPER_FREEZE` frames, like hitstop. DOS's super adds two
Move twists: `crash` (a hold on every rival body in reach) and `seek` (a leap that lands on the
rival). The renderer draws the bar, the freeze's call and the BSOD look (variant B of
`docs/superpowers/specs/2026-10-22-brawl-ket-superposition-bsod-look.py`).

**Tech Stack:** Python 3.11, pygame 2.5.2, pytest, ruff 0.15.22, uv.

**Spec:** `docs/superpowers/specs/2026-10-22-brawl-ket-superposition-design.md`. The six other
supers (sections 4.1-4.4, 4.6, 4.7) are part 2, planned once their looks are approved.

## Global Constraints

- Work in the worktree `/home/damian/03_personal/games/.claude/worktrees/brawl-ket-alice-bob/`,
  branch `brawl-ket-alice-bob`. Run every command from its `brawl-ket/` directory.
- Python 3.11, pygame 2.5.2 exactly; no new dependencies. LF line endings.
- The name is written **SUPERposition** (only SUPER in capitals); the bar's label is **SUPER**.
- `SUPER_HALF = 40` points per half; damage taken fills at half the rate.
- `SUPER_WINDOW = 3` frames for A+B; `SUPER_FREEZE = 30` frames (0.5 s).
- A super hurts either basis (colour `BOTH`), about 25 damage; its own damage fills no bar.
- The bar carries over from round to round and resets at the start of every match (rematches too).
- Firing: from the ground only, in a free state (idle, walk, crouch); never in the air, stunned or mid-move.
- Bob never echoes a super's A and B.
- Commits: gitmoji style, explicit paths, ending with `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.
- Checks (each task's last step runs the ones it touches; Task 6 runs all):
  - `uv run pytest -q`
  - `uvx --from 'ruff==0.15.22' ruff check src tests tools`
  - `SDL_VIDEODRIVER=dummy uv run python tools/snapshot.py <out dir>`
  - `uv run python tools/balance.py 100`
  - `SDL_VIDEODRIVER=dummy uv run python tools/benchmark.py`

## File Structure

- Create `src/brawl_ket/superpos.py`: `Meter`, the bar's state and fill rules. Pure.
- Modify `src/brawl_ket/config.py`: the SUPERposition and BSOD constants.
- Modify `src/brawl_ket/fight.py`: meters, filling, firing, the freeze, the crash, `super_ko`.
- Modify `src/brawl_ket/fighter.py`: `super_ready`, A+B in `_try_buffer`, `seek`, `crash`, `glitch`.
- Modify `src/brawl_ket/echo.py`: `forget_presses()`.
- Modify `src/brawl_ket/moves.py`: `Move.crash`, `Move.seek`, `BSOD_HOLD`, `BLUE_SCREEN`, DOS's `extra["super"]`.
- Modify `src/brawl_ket/match.py`: one Meter per player per match; a super K.O.'s longer slow motion.
- Modify `src/brawl_ket/render.py`: the HUD bar, the freeze's call, the select screen's fourth row, HOW TO PLAY's A+B row, the BSOD's strip, glitch, window and flash.
- Modify `src/brawl_ket/dos.py`: `draw_error_window`, `glitch_layer` (the BSOD look's pieces).
- Modify `src/brawl_ket/audio.py`: the super's sounds (each with the task that adds its event).
- Modify `src/brawl_ket/bot.py`: fire a super that will land; dodge the BSOD; switch a little more with one half full.
- Modify `tools/snapshot.py`, `tools/benchmark.py`, `README.md`, the spec.
- Create `tests/test_superpos.py`; modify `tests/test_match.py`, `tests/test_render.py`, `tests/test_bot.py`.

---

### Task 1: The bar and how it fills

**Files:**
- Create: `src/brawl_ket/superpos.py`
- Modify: `src/brawl_ket/config.py` (after `THROW_RANGE`)
- Modify: `src/brawl_ket/fight.py` (`Fight.__init__`, `_apply_strike`, a new `_fill`)
- Modify: `src/brawl_ket/match.py` (`__init__`, `_start_match`, `_start_round`)
- Modify: `src/brawl_ket/audio.py` (the half's and the full bar's sounds)
- Test: `tests/test_superpos.py`, `tests/test_match.py`, `tests/test_audio.py`

**Interfaces:**
- Produces: `superpos.FULL: int` (half points in a full half, 80); `superpos.Meter` with
  `fill: dict[str, int]` (keys `basis.Z_BASIS`, `basis.X_BASIS`, in half points),
  `dealt(b: str, damage: int) -> list[str]`, `taken(b: str, damage: int) -> list[str]`
  (each returns the kinds that just happened: `"half"`, then `"full"`), `full: bool`,
  `share(b: str) -> float` (0..1), `empty() -> None`.
- Produces: `Fight(chars, seed=0, meters: dict[str, Meter] | None = None)`, `Fight.meters`.
- Produces: Events `super_half` and `super_full` (player = whose bar).
- Produces: `Match.meters: dict[str, Meter]`, passed to every round's Fight.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_superpos.py`:

```python
"""Tests for SUPERposition (superpos.py, and the fight's and the fighter's part in it)."""

from __future__ import annotations

from dataclasses import replace

from brawl_ket import basis
from brawl_ket.fight import Fight
from brawl_ket.fighter import FighterInput
from brawl_ket.moves import CHARACTERS, ROBERT
from brawl_ket.superpos import FULL, Meter

Z, X = basis.Z_BASIS, basis.X_BASIS
A = FighterInput(a=True)
B = FighterInput(b=True)
DOS = CHARACTERS["DOS"]


def fight_of(a=ROBERT, b=ROBERT, gap: float = 50.0) -> Fight:
    fight = Fight({"p1": a, "p2": b}, seed=1)
    fight.fighters["p1"].x = 300.0
    fight.fighters["p2"].x = 300.0 + gap
    return fight


def until(fight: Fight, kind: str, first: dict | None = None, frames: int = 60) -> list:
    """Step once with `first`, then idle until an event of `kind` (or `frames` run out)."""
    events = fight.step(first or {})
    for _ in range(frames):
        if any(e.kind == kind for e in events):
            break
        events += fight.step({})
    return events


# --- the bar ---------------------------------------------------------------------------------


def test_a_half_takes_40_points_dealt_or_80_taken():
    assert FULL == 80
    m = Meter()
    assert m.fill == {Z: 0, X: 0} and not m.full
    assert m.dealt(Z, 39) == [] and m.share(Z) == 78 / 80
    assert m.dealt(Z, 1) == ["half"] and m.share(Z) == 1.0 and not m.full
    m.empty()
    assert m.taken(X, 40) == [] and m.share(X) == 0.5


def test_the_bar_is_full_only_with_both_halves_and_says_so_once():
    m = Meter()
    assert m.dealt(Z, 50) == ["half"]           # the overflow is lost
    assert m.fill[Z] == FULL
    assert m.dealt(Z, 10) == []                 # already full: nothing new
    assert m.dealt(X, 40) == ["half", "full"]
    assert m.full
    m.empty()
    assert m.fill == {Z: 0, X: 0} and not m.full


# --- filling in a fight ----------------------------------------------------------------------


def test_a_hit_fills_the_attackers_half_of_its_basis_and_the_hit_ones_at_half_rate():
    fight = fight_of()
    until(fight, "hit", {"p1": A})                  # green ROBERT jabs green ROBERT: 4
    assert fight.meters["p1"].fill == {Z: 8, X: 0}
    assert fight.meters["p2"].fill == {Z: 4, X: 0}


def test_the_half_is_the_attackers_basis_not_the_colour_of_the_hit():
    fight = fight_of()
    fight.fighters["p1"].basis = X                  # purple ROBERT's B is green: it hurts green p2
    until(fight, "hit", {"p1": B})
    assert fight.fighters["p2"].health == ROBERT.health - 8
    assert fight.meters["p1"].fill == {Z: 0, X: 16}
    assert fight.meters["p2"].fill == {Z: 8, X: 0}


def test_dos_fills_the_half_of_the_hits_colour():
    fight = fight_of(DOS, ROBERT, gap=60.0)
    fight.fighters["p2"].basis = X                  # DOS's B is purple: it hurts purple ROBERT
    until(fight, "hit", {"p1": B})
    dealt = ROBERT.health - fight.fighters["p2"].health
    assert dealt > 0
    assert fight.meters["p1"].fill == {Z: 0, X: 2 * dealt}


def test_a_blocked_hit_fills_nothing():
    fight = fight_of()
    fight.fighters["p2"].basis = X                  # a green jab bounces off purple
    events = until(fight, "block", {"p1": A})
    assert any(e.kind == "block" for e in events)
    assert fight.meters["p1"].fill == {Z: 0, X: 0} and fight.meters["p2"].fill == {Z: 0, X: 0}


def test_filling_a_half_and_the_bar_are_events():
    fight = fight_of()
    fight.meters["p1"].fill = {Z: FULL - 2, X: FULL}
    events = until(fight, "hit", {"p1": A})
    kinds = [(e.kind, e.player) for e in events if e.kind.startswith("super_")]
    assert kinds == [("super_half", "p1"), ("super_full", "p1")]
    assert fight.meters["p1"].full


def test_a_fight_can_be_handed_its_meters():
    meters = {"p1": Meter(), "p2": Meter()}
    meters["p1"].fill[Z] = 12
    fight = Fight({"p1": ROBERT, "p2": ROBERT}, seed=1, meters=meters)
    assert fight.meters is meters and fight.meters["p1"].fill[Z] == 12
```

In `tests/test_match.py`, add at the end:

```python


# --- SUPERposition: one bar per player for a whole match ----------------------------------------


def test_the_bars_carry_over_from_round_to_round_and_reset_for_a_new_match() -> None:
    from brawl_ket.basis import Z_BASIS
    m = Match(random.Random(1))
    to_fight(m)
    m.fight.meters["p1"].fill[Z_BASIS] = 30
    ko(m, "p2")
    run(m, config.ROUND_INTRO_FRAMES)
    assert m.state == FIGHT and m.round_no == 2
    assert m.fight.meters is m.meters and m.meters["p1"].fill[Z_BASIS] == 30
    ko(m, "p2")                                 # 2-0: the match is won
    assert m.state == MATCH_RESULT
    run(m, config.MATCH_RESULT_LOCK)
    m.update(press("confirm"))                  # a rematch is a new match
    assert m.meters["p1"].fill[Z_BASIS] == 0 and m.fight.meters is m.meters
```

- [ ] **Step 2: Run them to see them fail**

Run: `uv run pytest -q tests/test_superpos.py tests/test_match.py -k "half or fill or bar or meters or carry"`
Expected: FAIL / ERROR with `ModuleNotFoundError: No module named 'brawl_ket.superpos'`.

- [ ] **Step 3: The constants**

In `src/brawl_ket/config.py`, after the `THROW_RANGE = 50 ...` line, add:

```python
# SUPERposition (superpos.py; docs/superpowers/specs/2026-10-22-brawl-ket-superposition-design.md):
# a bar of two halves, green and purple, each SUPER_HALF points of damage dealt in that basis
# (damage taken counts half); full, A and B pressed within SUPER_WINDOW frames fire the super,
# and the fight freezes SUPER_FREEZE frames for its call
SUPER_HALF = 40
SUPER_WINDOW = 3
SUPER_FREEZE = frames(0.5)
```

- [ ] **Step 4: The bar**

Create `src/brawl_ket/superpos.py`:

```python
"""SUPERposition's bar: one per player, a green half (Z) and a purple half (X); full when both are.

Pure logic, no pygame. The fight fills it where damage is applied (fight.py, _fill): damage
dealt fills the half of the basis the attacker is in when it lands, damage taken the half of the
basis the one hit is in, at half the rate. DOS can't switch, so his dealt damage fills the half
of the hit's colour instead (the basis of the one it hurt). A super's own damage fills nothing.
The match keeps one per player for a whole match, so it carries over from round to round
(docs/superpowers/specs/2026-10-22-brawl-ket-superposition-design.md).
"""

from __future__ import annotations

from dataclasses import dataclass, field

from . import basis
from .config import SUPER_HALF

FULL = 2 * SUPER_HALF   # a half, in half points: damage taken fills at half the rate


@dataclass
class Meter:
    fill: dict[str, int] = field(default_factory=lambda: {basis.Z_BASIS: 0, basis.X_BASIS: 0})

    def dealt(self, b: str, damage: int) -> list[str]:
        """Damage dealt in basis b: its half fills point for point."""
        return self._add(b, 2 * damage)

    def taken(self, b: str, damage: int) -> list[str]:
        """Damage taken in basis b: its half fills at half the rate."""
        return self._add(b, damage)

    def _add(self, b: str, half_points: int) -> list[str]:
        """Fill b's half (the overflow is lost). Returns what just happened: "half" if that
        filled it, and then "full" if the whole bar is now full."""
        before = self.fill[b]
        self.fill[b] = min(FULL, before + half_points)
        if before >= FULL or self.fill[b] < FULL:
            return []
        return ["half", "full"] if self.full else ["half"]

    @property
    def full(self) -> bool:
        return all(v >= FULL for v in self.fill.values())

    def share(self, b: str) -> float:
        """How full b's half is, 0 to 1."""
        return self.fill[b] / FULL

    def empty(self) -> None:
        for b in self.fill:
            self.fill[b] = 0
```

- [ ] **Step 5: The fight fills it**

In `src/brawl_ket/fight.py`:

Add the import after `from .moves import HIGH, LOW, Box, Character, Move`:

```python
from .superpos import Meter
```

Change the `Fight.__init__` signature and add the meters after `self.rng = random.Random(seed)      # THE BOX's 50/50s`:

```python
    def __init__(self, chars: dict[str, Character], seed: int = 0,
                 meters: dict[str, Meter] | None = None) -> None:
        self.seed = seed
        self.rng = random.Random(seed)      # THE BOX's 50/50s
        # SUPERposition's bars (superpos.py): the match's, so they carry over between rounds
        self.meters = meters if meters is not None else {"p1": Meter(), "p2": Meter()}
```

In `_apply_strike`, capture the health before the hit. Replace:

```python
        error = basis.error_for(m.colour, attack_basis)
        result = defender.take_hit(m, error, st.from_facing)
```

with:

```python
        error = basis.error_for(m.colour, attack_basis)
        before = defender.health
        result = defender.take_hit(m, error, st.from_facing)
```

and replace:

```python
        events.append(Event("hit", st.defender, error, x, y))
        knocked = defender.action == "knockdown"
```

with:

```python
        events.append(Event("hit", st.defender, error, x, y))
        if before > defender.health and m.kind != "super":
            self._fill(st.owner, owner, st.defender, defender, before - defender.health, events)
        knocked = defender.action == "knockdown"
```

Add the method after `_apply_strike`:

```python
    def _fill(self, key: str, owner: Fighter, defender_key: str, defender: Fighter, damage: int,
              events: list[Event]) -> None:
        """SUPERposition's bars (superpos.py): the attacker's half of the basis it is in (DOS: the
        hit's colour, the basis of the one it hurt), and the one hit's own half at half the rate."""
        half = defender.basis if owner.char.fixed_basis is not None else owner.basis
        for kind in self.meters[key].dealt(half, damage):
            events.append(Event(f"super_{kind}", key))
        for kind in self.meters[defender_key].taken(defender.basis, damage):
            events.append(Event(f"super_{kind}", defender_key))
```

- [ ] **Step 6: The match keeps them**

In `src/brawl_ket/match.py`, add the import after `from .moves import CHARACTERS`:

```python
from .superpos import Meter
```

In `Match.__init__`, after `self.wins = {p: 0 for p in PLAYERS}`:

```python
        self.meters = {p: Meter() for p in PLAYERS}     # SUPERposition's bars: a whole match's
```

In `_start_match`, after `self.wins = {p: 0 for p in PLAYERS}`:

```python
        self.meters = {p: Meter() for p in PLAYERS}
```

In `_start_round`, replace:

```python
        self.fight = Fight({p: self.fighter(p) for p in PLAYERS}, seed)
```

with:

```python
        self.fight = Fight({p: self.fighter(p) for p in PLAYERS}, seed, self.meters)
```

- [ ] **Step 7: The sounds of a half and of the bar filling**

In `src/brawl_ket/audio.py`, in `build_sfx()`'s dict after the ALICE & BOB block (`"recohere": ...`), add:

```python
        # SUPERposition: a half filling (a rising pair) and the whole bar (a rising chord)
        "super_half": concat(tone(c("E5"), 0.05, 0.14, "triangle", decay=10), tone(c("A5"), 0.08, 0.14, "triangle", decay=8)),
        "super_full": concat(tone(c("C5"), 0.05, 0.16, "triangle", decay=8), tone(c("E5"), 0.05, 0.16, "triangle", decay=8),
                             tone(c("G5"), 0.05, 0.16, "triangle", decay=8), tone(c("C6"), 0.2, 0.18, "triangle", decay=4)),
```

and in `EVENT_SOUNDS`, after `"bell_dive": "bell_dive",`, add:

```python
                "super_half": "super_half", "super_full": "super_full",
```

Add to `tests/test_audio.py`:

```python


def test_the_super_has_its_sounds() -> None:
    sfx = audio.build_sfx()
    for kind in ("super_half", "super_full"):
        assert audio.EVENT_SOUNDS.get(kind) in sfx, kind
```

- [ ] **Step 8: Run the tests**

Run: `uv run pytest -q tests/test_superpos.py tests/test_match.py tests/test_fight.py tests/test_audio.py`
Expected: PASS.

Run: `uv run python /tmp/claude-1000/-home-damian-03-personal-games/f36daf68-213a-40bf-b401-f1c20781411e/scratchpad/brawl-digest.py`
(if the scratchpad is gone: any bot-vs-bot digest taken before this task)
Expected: `0f53aa97f6c572ea22353215416da852ab2aa30a33b2900ac3cba9c434e8cec4`, unchanged: the bar is only state.

- [ ] **Step 9: Commit**

```bash
git add src/brawl_ket/superpos.py src/brawl_ket/config.py src/brawl_ket/fight.py src/brawl_ket/match.py src/brawl_ket/audio.py tests/test_superpos.py tests/test_match.py tests/test_audio.py
git commit -m "feat: :sparkles: Brawl-Ket: SUPERposition's bar, filled by fighting in both bases

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 2: Firing a super: A+B, the freeze, and what it hits

**Files:**
- Modify: `src/brawl_ket/fighter.py` (`__init__`, `_try_buffer`)
- Modify: `src/brawl_ket/echo.py` (`forget_presses`)
- Modify: `src/brawl_ket/fight.py` (`__init__`, `step`, `_step_fighters`, `_fighter_events`, a new `_fire`, `_apply_strike`)
- Modify: `src/brawl_ket/match.py` (`_on_round_end`)
- Modify: `src/brawl_ket/moves.py` (the `kind` comment)
- Modify: `src/brawl_ket/audio.py` (the call's sound)
- Test: `tests/test_superpos.py`, `tests/test_match.py`, `tests/test_audio.py`

**Interfaces:**
- Consumes: `Meter.full`, `Meter.empty()`, `Fight.meters` (Task 1).
- Produces: `Fighter.super_ready: bool` (set by the fight every frame); the local event
  `("super", {})` and slot `"super"`; `Fight.freeze: int` (frames of the call left),
  `Fight.supers: list[str]` (whose call plays, first first), `Fight.super_ko: bool`;
  the Event `super` (player = who fired); `Echo.forget_presses() -> None`.
- Produces: a super is `char.extra["super"]`, a `Move` with `kind="super"` and colour `BOTH`.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_superpos.py`:

```python


# --- firing ------------------------------------------------------------------------------------

from types import MappingProxyType  # noqa: E402

from brawl_ket.basis import BOTH  # noqa: E402
from brawl_ket.config import SUPER_FREEZE  # noqa: E402
from brawl_ket.moves import ALICE_BOB, MID, Box, Move  # noqa: E402

AB = FighterInput(a=True, b=True)
# a plain test super: a big strike in front, both colours
TEST_SUPER = Move("TEST SUPER", 4, 4, 10, Box(14, 40, 60, 60), BOTH, MID,
                  damage=25, hitstun=30, knockback=3.0, knockdown=True, kind="super")
SUPER_ROBERT = replace(ROBERT, extra=MappingProxyType({"super": TEST_SUPER}))


def full(fight: Fight, key: str = "p1") -> None:
    fight.meters[key].fill = {Z: FULL, X: FULL}


def kinds(events: list) -> list[str]:
    return [e.kind for e in events]


def test_a_and_b_together_with_a_full_bar_fire_it_and_empty_the_bar():
    fight = fight_of(SUPER_ROBERT)
    full(fight)
    events = fight.step({"p1": AB})
    assert "super" in kinds(events) and fight.fighters["p1"].slot == "super"
    assert not fight.meters["p1"].full and fight.meters["p1"].fill == {Z: 0, X: 0}
    assert fight.freeze == SUPER_FREEZE and fight.supers == ["p1"]


def test_the_freeze_stops_everything_for_its_call():
    fight = fight_of(SUPER_ROBERT)
    full(fight)
    fight.fighters["p2"].vx = 2.0
    fight.step({"p1": AB})
    clock, frame, x = fight.frames_left, fight.fighters["p1"].frame, fight.fighters["p2"].x
    for _ in range(SUPER_FREEZE - 1):
        assert fight.step({"p2": FighterInput(dx=1)}) == []
    assert (fight.frames_left, fight.fighters["p1"].frame, fight.fighters["p2"].x) == (clock, frame, x)
    fight.step({})                                  # the last frame of the call
    assert fight.freeze == 0 and fight.supers == []
    fight.step({})
    assert fight.fighters["p1"].frame == frame + 1  # and on it goes


def test_a_then_b_two_frames_later_still_fires_but_three_is_a_jab():
    fight = fight_of(SUPER_ROBERT)
    full(fight)
    fight.step({"p1": A})
    fight.step({})
    assert "super" in kinds(fight.step({"p1": B}))
    fight = fight_of(SUPER_ROBERT)
    full(fight)
    fight.step({"p1": A})
    fight.step({})
    events = fight.step({})                         # a lone A waited 2 frames: now it's a jab
    assert fight.fighters["p1"].slot == "stand.A" and "super" not in kinds(events)


def test_without_a_full_bar_a_and_b_are_as_ever():
    fight = fight_of(SUPER_ROBERT)
    fight.step({"p1": A})
    assert fight.fighters["p1"].slot == "stand.A"   # at once, no waiting
    fight = fight_of(SUPER_ROBERT)
    events = fight.step({"p1": AB})
    assert "super" not in kinds(events) and fight.fighters["p1"].slot != "super"


def test_a_fighter_with_no_super_never_waits():
    fight = fight_of()
    full(fight)
    fight.step({"p1": A})
    assert fight.fighters["p1"].slot == "stand.A"


def test_not_from_the_air():
    fight = fight_of(SUPER_ROBERT)
    full(fight)
    fight.step({"p1": FighterInput(up=True)})
    events = fight.step({"p1": AB})
    assert "super" not in kinds(events) and fight.meters["p1"].full


def test_it_hurts_either_colour_and_fills_no_bar():
    for rival_basis in (Z, X):
        fight = fight_of(SUPER_ROBERT)
        full(fight)
        fight.fighters["p2"].basis = rival_basis
        until(fight, "hit", {"p1": AB}, frames=SUPER_FREEZE + 20)
        assert fight.fighters["p2"].health == ROBERT.health - 25
        assert fight.meters["p1"].fill == {Z: 0, X: 0} and fight.meters["p2"].fill == {Z: 0, X: 0}


def test_a_ko_by_a_super_is_marked():
    fight = fight_of(SUPER_ROBERT)
    full(fight)
    fight.fighters["p2"].health = 20
    until(fight, "ko", {"p1": AB}, frames=SUPER_FREEZE + 20)
    assert fight.over and fight.super_ko


def test_both_on_the_same_frame_freeze_one_after_the_other():
    fight = fight_of(SUPER_ROBERT, SUPER_ROBERT, gap=200.0)
    full(fight, "p1")
    full(fight, "p2")
    fight.step({"p1": AB, "p2": AB})
    assert fight.supers == ["p1", "p2"]
    for _ in range(SUPER_FREEZE):
        fight.step({})
    assert fight.supers == ["p2"] and fight.freeze == SUPER_FREEZE
    for _ in range(SUPER_FREEZE):
        fight.step({})
    assert fight.supers == [] and fight.freeze == 0


def test_bob_never_echoes_a_supers_a_and_b():
    pair = replace(ALICE_BOB, extra=MappingProxyType({**ALICE_BOB.extra, "super": TEST_SUPER}))
    fight = fight_of(pair, ROBERT, gap=300.0)
    full(fight)
    fight.step({"p1": A})
    fight.step({"p1": B})                           # A, then B a frame later
    assert fight.fighters["p1"].slot == "super"
    bob = fight.echoes["p1"]
    for _ in range(SUPER_FREEZE + 30):
        fight.step({})
        assert bob.action != "attack"
```

In `tests/test_match.py`, append:

```python


def test_a_ko_by_a_super_plays_out_twice_as_long_in_slow_motion() -> None:
    m = Match(random.Random(1))
    to_fight(m)
    m.fight.fighters["p2"].health = 0
    m.fight.super_ko = True
    m.update(idle())
    assert m.state == ROUND_END and m.ko
    slow = steps_of(m, 2 * config.KO_SLOW_FRAMES)
    assert slow == 2 * config.KO_SLOW_FRAMES // config.KO_SLOW_RATE
```

- [ ] **Step 2: Run them to see them fail**

Run: `uv run pytest -q tests/test_superpos.py tests/test_match.py -k "fire or freeze or frames_later or as_ever or never_waits or air or either_colour or super or bob"`
Expected: FAIL (`AttributeError: 'Fight' object has no attribute 'freeze'`, and the like).

- [ ] **Step 3: The fighter fires it**

In `src/brawl_ket/fighter.py`, extend the config import with `SUPER_WINDOW` (alphabetical, after `STAGE_RIGHT`):

```python
    STAGE_RIGHT,
    SUPER_WINDOW,
    SWITCH_RECOVERY,
```

In `Fighter.__init__`, after `self.paired = False ...`:

```python
        self.super_ready = False        # SUPERposition: the bar is full (the fight sets it every frame)
```

At the top of `_try_buffer`, before `for entry in reversed(self.buffer):`, add:

```python
        if self.super_ready and self.action in _GROUND_FREE and self._try_super(events):
            return
```

and add the method after `_try_buffer`:

```python
    def _try_super(self, events: list) -> bool:
        """SUPERposition: with the bar full, A and B pressed within SUPER_WINDOW frames of each
        other fire the super. A lone A or B waits up to SUPER_WINDOW - 1 frames for its partner
        (True: nothing else may start meanwhile), then comes out as ever."""
        move = self.char.extra.get("super")
        if move is None:
            return False
        ages = {p.button: p.age for p in self.buffer if p.button in ("a", "b")}
        if len(ages) == 2 and abs(ages["a"] - ages["b"]) < SUPER_WINDOW:
            self._start_move("super", move, False, events)
            events.append(("super", {}))
            return True
        return bool(ages) and max(ages.values()) < SUPER_WINDOW - 1
```

- [ ] **Step 4: Bob forgets the presses**

In `src/brawl_ket/echo.py`, after `replay`:

```python
    def forget_presses(self) -> None:
        """Alice fired her super: the A and B that fired it must not come out of Bob as normals
        (a super is one move for both)."""
        self.queue = deque(replace(q, a=False, b=False) for q in self.queue)
```

- [ ] **Step 5: The fight freezes for it**

In `src/brawl_ket/fight.py`:

Extend the config import with `SUPER_FREEZE` (after `STAGE_RIGHT,`):

```python
    STAGE_RIGHT,
    START_X,
    SUPER_FREEZE,
```

(keep `START_X` where it is; the list stays alphabetical).

In `Fight.__init__`, after `self.hitstop = 0`:

```python
        self.freeze = 0                     # SUPERposition: frames of the call left (nothing moves)
        self.supers: list[str] = []         # ... whose call it is, and who fired on the same frame after them
        self.super_ko = False               # the round ended on a super
        self._fired: set[str] = set()       # who fired this frame (Bob forgets those presses)
```

In `step`, after the `if self.over:` block and before `if self.hitstop > 0:`, add:

```python
        if self.freeze > 0:                 # a super's call: nothing moves, the clock included
            self.freeze -= 1
            if self.freeze == 0:
                self.supers.pop(0)
                if self.supers:             # another super fired on the same frame: its call
                    self.freeze = SUPER_FREEZE
            return []
```

In `_step_fighters`, replace:

```python
        for key, echo in self.echoes.items():
            self.fighters[key].paired = echo.here     # her X and TELEPORT need Bob
        for key, f in self.fighters.items():
            f.rival_boxes = self._reach(_other(key))
            self._fighter_events(key, f, f.step(inputs.get(key, IDLE), start_x[_other(key)]), events)
        for key, echo in self.echoes.items():     # Bob after Alice: he faces as she now does
            late = echo.replay(inputs.get(key, IDLE))
```

with:

```python
        for key, echo in self.echoes.items():
            self.fighters[key].paired = echo.here     # her X and TELEPORT need Bob
        self._fired = set()
        for key, f in self.fighters.items():
            f.rival_boxes = self._reach(_other(key))
            f.super_ready = self.meters[key].full
            self._fighter_events(key, f, f.step(inputs.get(key, IDLE), start_x[_other(key)]), events)
        for key, echo in self.echoes.items():     # Bob after Alice: he faces as she now does
            late = echo.replay(inputs.get(key, IDLE))
            if key in self._fired:
                echo.forget_presses()
```

In `_fighter_events`, add a branch before `elif kind == "swap":`:

```python
            elif kind == "super":
                self._fire(key, events)
```

Add the method after `_fighter_events`:

```python
    def _fire(self, key: str, events: list[Event]) -> None:
        """SUPERposition: the bar empties and the fight freezes SUPER_FREEZE frames for the call
        (a second super fired on the same frame plays its call after this one)."""
        self.meters[key].empty()
        self.supers.append(key)
        self.freeze = SUPER_FREEZE
        self._fired.add(key)
        events.append(Event("super", key))
```

In `_apply_strike`, after the line `knocked = defender.action == "knockdown"`, add:

```python
        if m.kind == "super" and defender.health <= 0:
            self.super_ko = True
```

- [ ] **Step 6: The match's longer slow motion**

In `src/brawl_ket/match.py`, `_on_round_end`, replace:

```python
        slow = self.ko and self.t <= config.KO_SLOW_FRAMES
```

with:

```python
        # a K.O. by a super plays out twice as long
        slow = self.ko and self.t <= config.KO_SLOW_FRAMES * (2 if self.fight.super_ko else 1)
```

- [ ] **Step 7: Document the kind**

In `src/brawl_ket/moves.py`, replace the `kind` field's comment:

```python
    kind: str = "normal"                # normal / throw / projectile / special
```

with:

```python
    kind: str = "normal"                # normal / throw / projectile / special / super (SUPERposition:
                                        # a Character's extra["super"], colour BOTH, fired with A+B)
```

- [ ] **Step 8: The call's sound**

`tests/test_audio.py::test_every_fight_event_is_mapped` requires every event to have a sound (or
None). In `src/brawl_ket/audio.py`, `build_sfx()`, after `"super_full": ...`, add:

```python
        # the call's hit: a low boom and a high shimmer
        "super": mix(tone(70, 0.6, 0.3, "square", decay=4, slide=0.6),
                     tone(1200, 0.5, 0.08, "triangle", decay=5, slide=1.5)),
```

and in `EVENT_SOUNDS`, after `"super_half": "super_half", "super_full": "super_full",` add `"super": "super",`.
In `tests/test_audio.py`'s `test_the_super_has_its_sounds`, add `"super"` to the tuple.

- [ ] **Step 9: Run the tests**

Run: `uv run pytest -q tests/test_superpos.py tests/test_match.py tests/test_fighter.py tests/test_fight.py tests/test_alice_bob.py tests/test_audio.py`
Expected: PASS.

Run the digest (Task 1, Step 7). Expected: unchanged `0f53aa97...` (no fighter has a super yet).

- [ ] **Step 10: Commit**

```bash
git add src/brawl_ket/fighter.py src/brawl_ket/echo.py src/brawl_ket/fight.py src/brawl_ket/match.py src/brawl_ket/moves.py src/brawl_ket/audio.py tests/test_superpos.py tests/test_match.py tests/test_audio.py
git commit -m "feat: :sparkles: Brawl-Ket: fire SUPERposition with A+B: the freeze, both colours, a longer K.O.

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 3: DOS's BLUE SCREEN OF DEATH, the engine

**Files:**
- Modify: `src/brawl_ket/config.py` (after `SUPER_FREEZE`)
- Modify: `src/brawl_ket/moves.py` (`Move.crash`, `Move.seek`, `BSOD_HOLD`, `BLUE_SCREEN`, DOS's `extra`)
- Modify: `src/brawl_ket/fighter.py` (`glitch`, `step`, `take_hit`, `_move_effects`)
- Modify: `src/brawl_ket/fight.py` (`_fighter_events`, a new `_crash`)
- Modify: `src/brawl_ket/audio.py` (its two sounds)
- Test: `tests/test_superpos.py`, `tests/test_audio.py`

**Interfaces:**
- Consumes: firing (Task 2).
- Produces: `CRASH_REACH = 200`, `CRASH_HOLD = 50`, `CRASH_LEAP = 40`;
  `Move.crash: Move | None`, `Move.seek: int`; `moves.BSOD_HOLD`, `moves.BLUE_SCREEN`;
  `DOS.extra["super"] is BLUE_SCREEN`; `Fighter.glitch: int` (frames left of the frozen look);
  Events `crash` (player = the one frozen, or None when nobody was; x, y: where its window
  goes) and `bsod_land` (player = DOS's; x: where he landed).

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_superpos.py`:

```python


# --- DOS: BLUE SCREEN OF DEATH -------------------------------------------------------------------

from brawl_ket.config import CRASH_HOLD, CRASH_LEAP, CRASH_REACH  # noqa: E402
from brawl_ket.moves import BLUE_SCREEN, BSOD_HOLD, ERWIN  # noqa: E402

STARTUP = BLUE_SCREEN.startup


def bsod(rival=ROBERT, gap: float = 150.0) -> Fight:
    """DOS with a full bar fires; the call is skipped and the startup run."""
    fight = fight_of(DOS, rival, gap)
    full(fight)
    fight.step({"p1": AB})
    for _ in range(SUPER_FREEZE):
        fight.step({})
    return fight


def run(fight: Fight, frames: int, inp: dict | None = None) -> list:
    events = []
    for _ in range(frames):
        events += fight.step(inp or {})
    return events


def test_dos_has_it_and_it_is_both_colours():
    assert DOS.extra["super"] is BLUE_SCREEN
    assert BLUE_SCREEN.kind == "super" and BLUE_SCREEN.colour == BOTH and BLUE_SCREEN.name == "BLUE SCREEN OF DEATH"
    assert BLUE_SCREEN.crash is BSOD_HOLD and BSOD_HOLD.hold and BSOD_HOLD.damage == 0
    assert BLUE_SCREEN.seek == CRASH_LEAP and BSOD_HOLD.hitstun == CRASH_HOLD


def test_it_freezes_a_rival_on_the_ground_in_reach():
    fight = bsod(gap=150.0)
    events = run(fight, STARTUP)
    rival = fight.fighters["p2"]
    crash = [e for e in events if e.kind == "crash"]
    assert crash and crash[0].player == "p2"
    assert rival.action == "hitstun" and rival.glitch > 0 and rival.vx == 0.0
    assert rival.health == ROBERT.health                # the freeze itself does no damage


def test_then_he_comes_down_on_them_for_25_whatever_their_colour():
    for colour in (Z, X):
        fight = bsod(gap=150.0)
        fight.fighters["p2"].basis = colour
        events = run(fight, STARTUP + CRASH_LEAP + 20)     # (the hit's hitstop holds the landing back)
        rival = fight.fighters["p2"]
        assert rival.health == ROBERT.health - 25 and rival.action == "knockdown"
        assert rival.glitch == 0
        assert any(e.kind == "bsod_land" for e in events)


def test_he_lands_about_crash_leap_frames_after_the_crash():
    fight = bsod(gap=CRASH_REACH + 20)                  # nobody frozen, so no hit and no hitstop
    dos = fight.fighters["p1"]
    run(fight, STARTUP)
    landed = None
    for n in range(1, CRASH_LEAP + 10):
        if any(e.kind == "bsod_land" for e in fight.step({})):
            landed = n
            break
    assert landed is not None and CRASH_LEAP - 3 <= landed <= CRASH_LEAP + 1
    assert dos.phase == "recovery"


def test_a_rival_in_the_air_is_not_frozen_and_he_drops_where_he_stands():
    fight = fight_of(DOS, ROBERT, 150.0)
    full(fight)
    fight.step({"p1": AB})
    for _ in range(SUPER_FREEZE):
        fight.step({})
    fight.step({"p2": FighterInput(up=True)})           # up in its startup
    events = run(fight, STARTUP - 1)
    assert [e.player for e in events if e.kind == "crash"] == [None]
    x = fight.fighters["p1"].x
    run(fight, CRASH_LEAP + 4)
    assert fight.fighters["p1"].x == x


def test_a_rival_out_of_reach_is_not_frozen():
    fight = bsod(gap=CRASH_REACH + 20)
    events = run(fight, STARTUP + CRASH_LEAP + 4)
    assert [e.player for e in events if e.kind == "crash"] == [None]
    assert fight.fighters["p2"].health == ROBERT.health


def test_the_box_dodges_it():
    fight = fight_of(DOS, ERWIN, 150.0)
    fight.fighters["p2"].action = "boxed"
    fight.fighters["p2"].boxes = (450.0, 450.0)
    full(fight)
    fight.step({"p1": AB})
    for _ in range(SUPER_FREEZE):
        fight.step({})
    events = run(fight, STARTUP)
    assert [e.player for e in events if e.kind == "crash"] == [None]


def test_both_of_alice_and_bob_in_reach_are_frozen():
    fight = bsod(ALICE_BOB, gap=120.0)
    events = run(fight, STARTUP)
    assert [e.player for e in events if e.kind == "crash"] == ["p2", "p2"]
    assert fight.echoes["p2"].glitch > 0 and fight.fighters["p2"].glitch > 0


def test_the_glitch_runs_down_a_frame_at_a_time_and_a_hit_ends_it():
    fight = fight_of()
    rival = fight.fighters["p2"]
    rival.glitch = 3
    run(fight, 3)
    assert rival.glitch == 0
    rival.glitch = 30
    until(fight, "hit", {"p1": A})
    assert rival.glitch == 0
```

- [ ] **Step 2: Run them to see them fail**

Run: `uv run pytest -q tests/test_superpos.py -k "dos or freezes or comes_down or lands or air or reach or box or alice or glitch"`
Expected: FAIL with `ImportError: cannot import name 'CRASH_HOLD'`.

- [ ] **Step 3: The constants**

In `src/brawl_ket/config.py`, after `SUPER_FREEZE = frames(0.5)`:

```python
# DOS's BLUE SCREEN OF DEATH: every rival on the ground within CRASH_REACH px is frozen for
# CRASH_HOLD frames, and DOS comes down on them in a leap CRASH_LEAP frames long
CRASH_REACH = 200
CRASH_HOLD = 50
CRASH_LEAP = 40
```

- [ ] **Step 4: The moves**

In `src/brawl_ket/moves.py`:

Extend the config import:

```python
from .config import CRASH_HOLD, CRASH_LEAP, DRIVE_SLOT_Y
```

In `Move`, after `swap: bool = False ...`, add:

```python
    # SUPERposition's twists (fight.py, fighter.py):
    crash: Move | None = None           # BLUE SCREEN OF DEATH: on its first active frame every rival body
                                        # on the ground within CRASH_REACH is held by this move
    seek: int = 0                       # > 0: on its first active frame a leap that comes down on the
                                        # rival this many frames later
```

Before `DOS = Character(` add:

```python
# DOS's super, BLUE SCREEN OF DEATH (SUPERposition, docs/superpowers/specs/2026-10-22-brawl-ket-superposition-
# design.md, 4): every rival on the ground within CRASH_REACH is frozen (a hold, no damage) while an
# error window pops up over them; then he leaps and comes down on them with a giant CRT DROP: MID, 25,
# a knockdown, in either colour. Nobody frozen, he comes down where he stands.
BSOD_HOLD = Move(
    "BLUE SCREEN", 0, 1, 1, None, BOTH, MID,
    damage=0, hitstun=CRASH_HOLD, knockback=0.0, hold=True,
)
BLUE_SCREEN = Move(
    "BLUE SCREEN OF DEATH", 8, CRASH_LEAP + 4, 30, Box(-44, -10, 88, 40), BOTH, MID,
    damage=25, hitstun=30, knockback=3.0, knockdown=True,
    kind="super", crash=BSOD_HOLD, seek=CRASH_LEAP, floor_recovery=True,
    poses=("crouch", "stomp", "crouch"),
)
```

In DOS's `extra=MappingProxyType({`, after the `"paste": Move(...)` entry and before `}),`, add:

```python
        "super": BLUE_SCREEN,
```

(`MID` is defined in moves.py with `HIGH` and `LOW`; check it is above this point.)

- [ ] **Step 5: The fighter's part**

In `src/brawl_ket/fighter.py`, `Fighter.__init__`, after `self.super_ready = False ...`:

```python
        self.glitch = 0                 # BLUE SCREEN OF DEATH: frames left of the frozen, glitching look
```

In `step`, after:

```python
        if self.wakeup > 0:
            self.wakeup -= 1
```

add:

```python
        if self.glitch > 0:
            self.glitch -= 1
```

In `take_hit`, after `hurt = basis.hurts(error, self.basis)`:

```python
        self.glitch = 0                 # (a BSOD freeze ends with the next hit; the fight sets it after its hold)
```

In `_move_effects`, after:

```python
                if m.leap is not None:  # POUNCE: off along an arc; gravity does the rest
                    self.vx, self.vy = m.leap[0] * self.facing, m.leap[1]
```

add:

```python
                if m.seek:              # BLUE SCREEN OF DEATH: up, to come down on the rival m.seek frames later
                    self.vx = (self.rival_x - self.x) / m.seek
                    self.vy = self.char.gravity * m.seek / 2
                if m.crash is not None:     # ... and the fight freezes whoever it reaches
                    events.append(("crash", {"move": m.crash}))
```

- [ ] **Step 6: The fight's part**

In `src/brawl_ket/fight.py`:

Extend the config import with `CRASH_REACH` (first in the list: `BLOCK_HITSTOP, BODY_MARGIN, CRASH_REACH, DRIVE_SLOT_Y, ...`).

In `_fighter_events`, add a branch before `elif kind == "swap":`:

```python
            elif kind == "crash":
                self._crash(key, f, data["move"], events)
```

and in its final `else:` branch, after the `if kind == "land" and data["dive"] ...` block, add:

```python
                if kind == "land" and f.action == "attack" and f.move is not None and f.move.crash is not None:
                    events.append(Event("bsod_land", key, None, f.x, FLOOR_Y))
```

Add the method after `_fire`:

```python
    def _crash(self, key: str, f: Fighter, hold: Move, events: list[Event]) -> None:
        """BLUE SCREEN OF DEATH: every rival body on the ground within CRASH_REACH is frozen (the
        hold: no damage, no push) and glitches; one in the air, beyond it, down, getting up or
        out of reach (TUNNEL, THE BOX) is not. With nobody frozen, DOS comes down where he stands."""
        frozen = False
        for body in self.bodies(_other(key)):
            if body.y > 0 or abs(body.x - f.x) > CRASH_REACH or body.action == "knockdown" \
                    or body.wakeup or body.intangible or body.boxed:
                continue
            body.take_hit(hold, basis.Y, f.facing)
            body.glitch = hold.hitstun
            frozen = True
            events.append(Event("crash", _other(key), None, body.x, FLOOR_Y - 140))
        if not frozen:
            f.vx = 0.0
            events.append(Event("crash", None, None, f.x, FLOOR_Y))
```

- [ ] **Step 7: Its sounds**

In `src/brawl_ket/audio.py`, `build_sfx()`, after `"super": ...`, add:

```python
        # BLUE SCREEN OF DEATH: the error chord as it freezes, and the crash as he lands
        "crash": concat(tone(c("A4"), 0.12, 0.18, "square", decay=6), tone(c("E4"), 0.25, 0.18, "square", decay=5)),
        "bsod_land": mix(noise_wave(0.5, 0.3, decay=6, hold=2, seed=59), tone(60, 0.5, 0.3, "square", decay=6, slide=0.5)),
```

and in `EVENT_SOUNDS`, after `"super": "super",` add `"crash": "crash", "bsod_land": "bsod_land",`.
In `tests/test_audio.py`'s `test_the_super_has_its_sounds`, add `"crash", "bsod_land"` to the tuple.

- [ ] **Step 8: Run the tests**

Run: `uv run pytest -q tests/test_superpos.py tests/test_fighter.py tests/test_fight.py tests/test_moves.py tests/test_audio.py`
Expected: PASS. (If a test pins DOS's `extra` keys, add `"super"` to its expected set.)

- [ ] **Step 9: Commit**

```bash
git add src/brawl_ket/config.py src/brawl_ket/moves.py src/brawl_ket/fighter.py src/brawl_ket/fight.py src/brawl_ket/audio.py tests/test_superpos.py tests/test_moves.py tests/test_audio.py
git commit -m "feat: :sparkles: Brawl-Ket: DOS's BLUE SCREEN OF DEATH: the freeze and the drop

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 4: The bar on screen, the call, and the menus

**Files:**
- Modify: `src/brawl_ket/render.py` (constants, `draw_fight`, `_hud`, new `_super_bar` and `_super_call`, `_select_side`, `list_top`, `_controls`, `BUTTON_JOBS`, `X_INPUTS`)
- Modify: `docs/superpowers/specs/2026-10-22-brawl-ket-superposition-design.md` (section 5's HOW TO PLAY line)
- Test: `tests/test_render.py`

**Interfaces:**
- Consumes: `Fight.meters`, `Meter.share`, `Meter.full`, `Fight.freeze`, `Fight.supers` (Tasks 1-2); `portrait(name)` (render.py).
- Produces: `render.SUPER_BAR = (x_inset 20, y 46, half width 56, height 5)` as constants
  `SUPER_BAR_Y`, `SUPER_HALF_W`, `SUPER_BAR_H`, `SUPER_LABEL`; `Renderer._super_bar(key, f, meter, rect, side)`;
  `Renderer._super_call(fight)`; `SUPER_CALL = "SUPERposition!"`.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_render.py`:

```python


# --- SUPERposition ----------------------------------------------------------------------------------


def test_the_super_bar_shows_each_half_in_its_colour(surface):
    from brawl_ket.fight import Fight
    from brawl_ket.render import SUPER_BAR_H, SUPER_BAR_Y, SUPER_HALF_W
    from brawl_ket.superpos import FULL
    fight = Fight({"p1": ROBERT, "p2": ROBERT})
    fight.meters["p1"].fill = {basis.Z_BASIS: FULL, basis.X_BASIS: FULL // 2}
    r = Renderer(surface)
    r.draw_fight(fight, [], {"p1": 0, "p2": 0})
    y = SUPER_BAR_Y + SUPER_BAR_H // 2
    row = [tuple(surface.get_at((x, y)))[:3] for x in range(0, INTERNAL_WIDTH // 2)]
    assert row.count(GREEN) >= SUPER_HALF_W - 4          # the green half, full
    assert SUPER_HALF_W // 2 - 4 <= row.count(PURPLE) <= SUPER_HALF_W // 2 + 4    # half the purple


def test_a_full_bar_says_a_plus_b_for_a_fighter_with_a_super(surface):
    from brawl_ket.fight import Fight
    from brawl_ket.moves import CHARACTERS
    from brawl_ket.superpos import FULL
    r = Renderer(surface)
    seen = {}
    for name in ("DOS", "ROBERT"):
        fight = Fight({"p1": CHARACTERS[name], "p2": ROBERT})
        fight.meters["p1"].fill = {basis.Z_BASIS: FULL, basis.X_BASIS: FULL}
        frames = []
        for _ in range(24):                             # it blinks: look over a whole cycle
            r.draw_fight(fight, [], {"p1": 0, "p2": 0})
            frames.append(surface.subsurface((0, 40, 300, 18)).copy())
        seen[name] = len({pygame.image.tostring(s, "RGB") for s in frames})
    assert seen["DOS"] > seen["ROBERT"]                  # (ROBERT has no super yet: no A+B!)


def test_the_freeze_shows_the_call(surface):
    from brawl_ket.fight import Fight
    from brawl_ket.fighter import FighterInput
    from brawl_ket.moves import CHARACTERS
    from brawl_ket.superpos import FULL
    fight = Fight({"p1": CHARACTERS["DOS"], "p2": ROBERT})
    fight.meters["p1"].fill = {basis.Z_BASIS: FULL, basis.X_BASIS: FULL}
    r = Renderer(surface)
    r.draw_fight(fight, fight.step({"p1": FighterInput(a=True, b=True)}), {"p1": 0, "p2": 0})
    for _ in range(12):
        r.draw_fight(fight, fight.step({}), {"p1": 0, "p2": 0})
    from brawl_ket.render import CALL_Y
    assert fight.freeze > 0
    band = {tuple(surface.get_at((x, y)))[:3] for x in range(100, 540) for y in range(CALL_Y - 16, CALL_Y - 4)}
    assert P.GOLD in band                                # "SUPERposition!" in gold across the middle


def test_choose_your_fighter_lists_the_super_as_a_fourth_row(surface):
    import random
    from brawl_ket import match as M
    from brawl_ket.render import LIST_GAP, list_top
    from brawl_ket.moves import CHARACTERS
    r = Renderer(surface)
    m = M.Match(random.Random(1))
    m.state, m.picks = M.SELECT, {"p1": M.ROSTER.index(CHARACTERS["DOS"]), "p2": 0}
    r.draw(m, [])
    y = list_top(CHARACTERS["DOS"]) + 3 * LIST_GAP + 4
    row = {tuple(surface.get_at((x, y)))[:3] for x in range(20, 300)}
    assert P.GOLD in row                                 # "A+B" in gold, on the fourth line


def test_how_to_play_lists_a_plus_b():
    from brawl_ket.render import BUTTON_JOBS
    assert ("A+B", "SUPER: FULL BAR") in BUTTON_JOBS
```

Update the existing test `test_the_lists_of_specials_clear_the_two_rows_of_portraits`: replace

```python
        assert list_top(c) + 2 * LIST_GAP + 8 < grid_top, c.name
```

with

```python
        assert list_top(c) + 3 * LIST_GAP + 8 < grid_top, c.name      # four rows: the super's too
```

(`INTERNAL_WIDTH`, `INTERNAL_HEIGHT`, `FLOOR_Y`, `GREEN`, `PURPLE`, `P`, `basis`, `ROBERT`,
`Renderer` and `pygame` are imported at the top of `tests/test_render.py` already.)

- [ ] **Step 2: Run them to see them fail**

Run: `uv run pytest -q tests/test_render.py -k "super or fourth or a_plus_b or lists_of_specials"`
Expected: FAIL with `ImportError: cannot import name 'SUPER_BAR_H'`.

- [ ] **Step 3: Constants and the menus' rows**

In `src/brawl_ket/render.py`, after `BAR_W, BAR_H, BAR_Y = 236, 12, 14 ...` add:

```python
# SUPERposition's bar, under the name line: SUPER, then a green half and a purple half
SUPER_BAR_Y = 46
SUPER_HALF_W = 56
SUPER_BAR_H = 5
SUPER_LABEL = "SUPER"
SUPER_CALL = "SUPERposition!"       # only SUPER in capitals (the font has real lower case)
```

Replace `LIST_GAP = 10               # ... and the lines' spacing` with:

```python
LIST_GAP = 9                # ... and the lines' spacing (four lines: the super's too)
```

Replace `X_INPUTS = (("stand.X", "X"), ("crouch.X", "DOWN+X"), ("air.X", "AIR X"))` with:

```python
X_INPUTS = (("stand.X", "X"), ("crouch.X", "DOWN+X"), ("air.X", "AIR X"), ("super", "A+B"))
```

Replace `BUTTON_JOBS` with:

```python
BUTTON_JOBS = (("A", "HIT, YOUR COLOUR"), ("B", "HIT, OTHER COLOUR"), ("X", "SPECIAL MOVE"),
               ("Y", "SWITCH COLOUR"), ("A+B", "SUPER: FULL BAR"))
```

Replace `list_top`'s body:

```python
    return SIDE_FLOOR + 48 + (10 if char.copy_paste else 0)
```

with:

```python
    return SIDE_FLOOR + 46 + (6 if char.copy_paste else 0)
```

In `_select_side`, replace:

```python
        for i, (slot, how) in enumerate(X_INPUTS):
            y = top + LIST_GAP * i
            move = char.moves[slot]
```

with:

```python
        for i, (slot, how) in enumerate(X_INPUTS):
            y = top + LIST_GAP * i
            move = char.extra.get(slot) if slot == "super" else char.moves[slot]
            if move is None:                # no super yet
                continue
```

In `_controls`, replace:

```python
        for i, (label, job) in enumerate(BUTTON_JOBS):
            y = top - 8 + 14 * i
            surf.blit(outlined(label, 8, P.GOLD), (box.x + 90, y))
            surf.blit(outlined(job, 8, P.WHITE), (box.x + 108, y))
```

with:

```python
        for i, (label, job) in enumerate(BUTTON_JOBS):
            y = top - 8 + 14 * i
            tag = outlined(label, 8, P.GOLD)
            surf.blit(tag, (box.x + 90, y))
            surf.blit(outlined(job, 8, P.WHITE), (box.x + max(108, 96 + tag.get_width()), y))
```

and replace `used = {b for b, _ in BUTTON_JOBS}` with:

```python
        used = {b for b, _ in BUTTON_JOBS if len(b) == 1}
```

- [ ] **Step 4: The bar in the HUD**

In `_hud`, after the line `self._legend(key, f, lx, y)`, add:

```python
            self._super_bar(key, f, fight.meters[key], rect, side)
```

Add the method after `_legend`:

```python
    def _super_bar(self, key: str, f: Fighter, meter, rect: pygame.Rect, side: int) -> None:
        """SUPERposition's bar under the name line: SUPER, a green half and a purple half filling
        away from the clock; full, both shine white and gold in turn, and A+B! blinks beside them
        (for a fighter who has a super)."""
        surf = self.surface
        label = outlined(SUPER_LABEL, 8, P.MIST)
        width = 2 * SUPER_HALF_W + 2
        if side < 0:
            lx = rect.left + 2
            x0 = lx + label.get_width() + 6
        else:
            lx = rect.right - 2 - label.get_width()
            x0 = lx - 6 - width
        surf.blit(label, (lx, SUPER_BAR_Y - 2))
        frame = pygame.Rect(x0, SUPER_BAR_Y, width, SUPER_BAR_H)
        pygame.draw.rect(surf, P.INK, frame.inflate(4, 4), border_radius=2)
        pygame.draw.rect(surf, P.NIGHT, frame)
        shine = meter.full and (self.t // 6) % 2
        for i, b in enumerate((basis.Z_BASIS, basis.X_BASIS)):
            half = pygame.Rect(x0 + i * (SUPER_HALF_W + 2), SUPER_BAR_Y, SUPER_HALF_W, SUPER_BAR_H)
            fill = round(SUPER_HALF_W * meter.share(b))
            if fill <= 0:
                continue
            part = pygame.Rect(half.x, half.y, fill, SUPER_BAR_H)
            if side > 0:
                part.right = half.right
            colour = (P.WHITE if i == 0 else P.GOLD) if shine else BASIS_BODY[b]
            surf.fill(colour, part)
            surf.fill(P.lighten(colour, 0.5), (part.x, part.y, part.w, 1))
        if meter.full and "super" in f.char.extra and (self.t // 12) % 2 == 0:
            tag = outlined("A+B!", 8, P.GOLD)
            tx = frame.right + 8 if side < 0 else frame.left - 8 - tag.get_width()
            surf.blit(tag, (tx, SUPER_BAR_Y - 2))
```

- [ ] **Step 5: The call**

In `draw_fight`, after `self._hud(fight, wins)`, add:

```python
        if fight.freeze > 0 and fight.supers:
            self._super_call(fight)
```

Add the method after `_super_bar`:

```python
    def _super_call(self, fight: Fight) -> None:
        """A super's freeze: the screen darkens, a sweep of both colours crosses it, the fighter's
        portrait slides in from their side, and the call: SUPERposition! and the move's name."""
        surf = self.surface
        key = fight.supers[0]
        f = fight.fighters[key]
        age = SUPER_FREEZE - fight.freeze           # frames into the call
        surf.blit(self.dim, (0, 0))
        if age < 10:                                # the sweep: green, then purple, across the screen
            x = round(W * age / 10) if key == "p1" else round(W - W * age / 10)
            for dx, colour in ((0, GREEN), (-24 if key == "p1" else 24, PURPLE)):
                pygame.draw.rect(surf, colour, (x + dx - 10, 0, 20, H))
        self._band(CALL_Y - 40, CALL_Y + 40)
        side = -1 if key == "p1" else 1
        face = pygame.transform.scale_by(portrait(f.char.name), 2)
        slide = min(1.0, age / 8)
        fx = round(W / 2 + side * (W / 2 + 40 - slide * 220)) - face.get_width() // 2
        surf.blit(face, (fx, CALL_Y - face.get_height() // 2))
        move = f.char.extra["super"]
        blit_center(surf, outlined(SUPER_CALL, 16, P.GOLD, thick=2), (W / 2, CALL_Y - 10))
        blit_center(surf, outlined(move.name, 8, P.WHITE), (W / 2, CALL_Y + 14))
```

Add `SUPER_FREEZE` to render.py's config import (keep it alphabetical). `portrait` is defined in
render.py; `GREEN`, `PURPLE`, `W`, `H`, `CALL_Y` too.

- [ ] **Step 6: The spec's HOW TO PLAY line**

In `docs/superpowers/specs/2026-10-22-brawl-ket-superposition-design.md`, section 5, replace:

```markdown
- **HOW TO PLAY card:** one more line, **FILL BOTH COLOURS, THEN A+B: SUPER**, and the button
  drawing lights A and B together.
```

with:

```markdown
- **HOW TO PLAY card:** one more row under the buttons, **A+B  SUPER: FULL BAR** (the longer
  line didn't fit the card's controls box), A and B already lit.
```

- [ ] **Step 7: Run the tests, and look**

Run: `uv run pytest -q tests/test_render.py`
Expected: PASS.

Run: `SDL_VIDEODRIVER=dummy uv run python tools/snapshot.py /tmp/brawl-snaps` and open
`/tmp/brawl-snaps/screen_select_erwin_dos.png` (DOS's four rows clear the portraits) and
`/tmp/brawl-snaps/screen_how_to_play.png` (the A+B row sits above the START pill).

- [ ] **Step 8: Commit**

```bash
git add src/brawl_ket/render.py tests/test_render.py docs/superpowers/specs/2026-10-22-brawl-ket-superposition-design.md
git commit -m "feat: :lipstick: Brawl-Ket: SUPERposition's bar, its call, and A+B on the menus

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 5: The BLUE SCREEN OF DEATH's look

The agreed look is variant B of `docs/superpowers/specs/2026-10-22-brawl-ket-superposition-bsod-look.py`
plus a one-frame blue flash when DOS lands: the stage stays; a blue strip along the floor
shows his reach; the frozen rival is tinted blue-white and sliced into jittering rows; a small
error window (grey title bar `FATAL EXCEPTION`, white on blue `<NAME>.EXE has` /
`stopped responding`, an `OK` button) pops up over their head.

**Files:**
- Modify: `src/brawl_ket/dos.py` (`BSOD_BLUE`, `draw_error_window`, `glitch_layer`)
- Modify: `src/brawl_ket/render.py` (`_reset`, `_start_effects`, `draw_fight`, `_fighter` wrapper for glitch)
- Modify: `tools/snapshot.py` (a `super_frames`)
- Test: `tests/test_render.py`

**Interfaces:**
- Consumes: Events `crash`, `bsod_land`; `Fighter.glitch`; `CRASH_REACH`, `CRASH_HOLD` (Task 3).
- Produces: `dos.BSOD_BLUE = (0, 0, 168)`; `dos.draw_error_window(surf, midbottom, name) -> pygame.Rect`;
  `dos.glitch_layer(layer, rect, t) -> pygame.Surface`; `Renderer.crashes: dict[str, tuple[float, int]]`
  (whose strip: DOS's x, frames since); `Renderer.bsod_flash: int`; `exe_name(f) -> str` in render.py.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_render.py`:

```python


def test_the_error_window_is_the_looks(surface):
    from brawl_ket.dos import BSOD_BLUE, draw_error_window
    surface.fill((0, 0, 0))
    win = draw_error_window(surface, (320, 200), "ROBERT")
    assert win.midbottom == (320, 200) and win.w >= 160
    assert tuple(surface.get_at((win.x + 2, win.y + 2)))[:3] == P.MIST            # the title bar
    assert tuple(surface.get_at((win.x + 3, win.centery)))[:3] == BSOD_BLUE         # the blue body
    body = {tuple(surface.get_at((x, y)))[:3] for x in range(win.x, win.right) for y in range(win.y + 14, win.y + 40)}
    assert P.WHITE in body                                                          # its white text


def test_a_frozen_rival_glitches_under_its_window_and_the_landing_flashes_blue(surface):
    from brawl_ket.config import SUPER_FREEZE
    from brawl_ket.dos import BSOD_BLUE
    from brawl_ket.fight import Fight
    from brawl_ket.fighter import FighterInput
    from brawl_ket.moves import BLUE_SCREEN, CHARACTERS
    from brawl_ket.superpos import FULL
    fight = Fight({"p1": CHARACTERS["DOS"], "p2": ROBERT}, seed=1)
    fight.fighters["p1"].x, fight.fighters["p2"].x = 250.0, 400.0
    fight.meters["p1"].fill = {basis.Z_BASIS: FULL, basis.X_BASIS: FULL}
    r = Renderer(surface)
    r.draw_fight(fight, fight.step({"p1": FighterInput(a=True, b=True)}))
    for _ in range(SUPER_FREEZE + BLUE_SCREEN.startup + 4):
        r.draw_fight(fight, fight.step({}))
    assert fight.fighters["p2"].glitch > 0 and "p1" in r.crashes
    above = {tuple(surface.get_at((400 + dx, FLOOR_Y - 180 + dy)))[:3] for dx in range(-60, 60, 3) for dy in range(0, 60, 3)}
    assert BSOD_BLUE in above                                   # the window over their head
    flashed = False
    for _ in range(60):
        events = fight.step({})
        r.draw_fight(fight, events)
        if any(e.kind == "bsod_land" for e in events):
            corner = tuple(surface.get_at((INTERNAL_WIDTH - 5, INTERNAL_HEIGHT - 5)))[:3]
            flashed = corner == BSOD_BLUE
            break
    assert flashed                                              # the whole screen, for that frame
```

- [ ] **Step 2: Run them to see them fail**

Run: `uv run pytest -q tests/test_render.py -k "error_window or glitches"`
Expected: FAIL with `ImportError: cannot import name 'BSOD_BLUE'`.

- [ ] **Step 3: The look's pieces**

Append to `src/brawl_ket/dos.py`:

```python


# --- BLUE SCREEN OF DEATH (SUPERposition; its look: docs/superpowers/specs/2026-10-22-brawl-ket-superposition-
# bsod-look.py, variant B) -------------------------------------------------------------------------------------

BSOD_BLUE = (0, 0, 168)
WINDOW_W, WINDOW_H = 170, 62


def draw_error_window(surf, midbottom, name: str):
    """The classic error box over a frozen rival: a grey title bar FATAL EXCEPTION, then white on
    blue "<NAME>.EXE has / stopped responding", and an OK button. Returns its rect."""
    from .fonts import load_font
    f8 = load_font(8)
    win = pygame.Rect(0, 0, WINDOW_W, WINDOW_H)
    win.midbottom = (round(midbottom[0]), round(midbottom[1]))
    pygame.draw.rect(surf, P.INK, win.inflate(4, 4))
    surf.fill(BSOD_BLUE, win)
    surf.fill(P.MIST, (win.x, win.y, win.w, 11))
    title = f8.render("FATAL EXCEPTION", False, BSOD_BLUE)
    surf.blit(title, title.get_rect(center=(win.centerx, win.y + 6)))
    surf.blit(f8.render(f"{name}.EXE has", False, P.WHITE), (win.x + 8, win.y + 18))
    surf.blit(f8.render("stopped responding", False, P.WHITE), (win.x + 8, win.y + 30))
    ok = pygame.Rect(0, 0, 32, 12)
    ok.midbottom = (win.centerx, win.bottom - 4)
    surf.fill(P.MIST, ok)
    label = f8.render("OK", False, BSOD_BLUE)
    surf.blit(label, label.get_rect(center=ok.center))
    return win


def glitch_layer(layer, rect, t: int):
    """A frozen body, cut from its own layer (`rect`): tinted blue-white and sliced into rows of 6 px,
    every third nudged sideways a few px, the nudges shifting with `t`."""
    sub = layer.subsurface(rect).copy()
    sub.fill((120, 150, 255, 255), special_flags=pygame.BLEND_RGBA_MULT)
    out = pygame.Surface(sub.get_size(), pygame.SRCALPHA)
    for y in range(0, sub.get_height(), 6):
        dx = ((y * 7 + t) % 11) - 5 if (y // 6) % 3 == 0 else 0
        out.blit(sub, (dx, y), (0, y, sub.get_width(), 6))
    return out
```

- [ ] **Step 4: The renderer draws them**

In `src/brawl_ket/render.py`:

Replace the dos import line `from .dos import BEIGE, CLIP_W, clip_icon, draw_dos, draw_floppy` with:

```python
from .dos import BEIGE, BSOD_BLUE, CLIP_W, clip_icon, draw_dos, draw_error_window, draw_floppy, glitch_layer
```

and add `CRASH_HOLD`, `CRASH_REACH` to the `from .config import (...)` list (alphabetical).

Add a module-level helper after `move_label`:

```python
def exe_name(f) -> str:
    """The name the BLUE SCREEN's error window gives a frozen body: ALICE or BOB for the pair."""
    if f.char.pair is not None:
        return "ALICE"
    return "BOB" if f.char.name == "BOB" else f.char.name
```

In `_reset`, add:

```python
        self.crashes: dict[str, tuple[float, int]] = {}     # BLUE SCREEN OF DEATH: whose strip (DOS's x, age)
        self.bsod_flash = 0                                 # ... and the landing's blue frame
        self._glitch = pygame.Surface((W, H), pygame.SRCALPHA)
```

(`_reset` runs from `__init__` and again for every new fight.)

In `_start_effects`, in its `for e in events:` loop, add the branches:

```python
            elif e.kind == "crash" and self._fight is not None:
                dos = next((k for k, f in self._fight.fighters.items()
                            if f.move is not None and f.move.crash is not None), None)
                if dos is not None and dos not in self.crashes:
                    self.crashes[dos] = (self._fight.fighters[dos].x, 0)
            elif e.kind == "bsod_land":
                self.bsod_flash = 1
                self.effects.append(Effect("popup", e.x + 50, FLOOR_Y - 150, POPUP_FRAMES, POPUP_FRAMES,
                                           P.WHITE, "CRASH!"))
```

In `draw_fight`, right after `self._blink(ox, oy)`, add the strip:

```python
        for key, (x, age) in list(self.crashes.items()):   # BLUE SCREEN OF DEATH: DOS's reach, on the floor
            if age >= CRASH_HOLD:
                del self.crashes[key]
                continue
            self.crashes[key] = (x, age + 1)
            strip = pygame.Surface((2 * CRASH_REACH, 18), pygame.SRCALPHA)
            strip.fill((*BSOD_BLUE, 140))
            surf.blit(strip, (round(x) - CRASH_REACH + ox, FLOOR_Y - 9 + oy))
```

Replace the fighters' loop:

```python
        for p in order:
            if p in fight.echoes:               # Bob first: he stands behind her
                self._echo(p, fight.echoes[p], ox, oy)
            heads[p] = self._fighter(p, fight.fighters[p], ox, oy)
```

with:

```python
        for p in order:
            if p in fight.echoes:               # Bob first: he stands behind her
                self._frozen_or(fight.echoes[p], lambda: self._echo(p, fight.echoes[p], ox, oy))
            heads[p] = self._frozen_or(fight.fighters[p], lambda: self._fighter(p, fight.fighters[p], ox, oy))
```

then, right after that loop, draw the frozen bodies' error windows over everyone (in `draw_fight`,
before `for t in fight.tosses:`):

```python
        for x, y, name in self._windows:        # BLUE SCREEN OF DEATH: the error windows, over the bodies
            draw_error_window(surf, (x + ox, y + oy), name)
        self._windows = []
```

and add `self._windows: list[tuple[float, float, str]] = []` to `_reset` with the three above.

At the end of `draw_fight`, after `self._advance()`, add:

```python
        if self.bsod_flash:                     # the BLUE SCREEN's drop lands: one frame all blue
            surf.fill(BSOD_BLUE)
            self.bsod_flash = 0
```

Add the method after `_echo`:

```python
    def _frozen_or(self, f, draw):
        """Draw a body with `draw`; one frozen by the BLUE SCREEN OF DEATH is drawn to a layer of
        its own, glitched (dos.glitch_layer), and its error window pops up over its head."""
        if f.glitch <= 0:
            return draw()
        real, self.surface = self.surface, self._glitch
        self._glitch.fill((0, 0, 0, 0))
        try:
            out = draw()
        finally:
            self.surface = real
        rect = pygame.Rect(0, 0, 170, 180)            # round the body and its reach, with room for the shake
        rect.midbottom = (round(f.x), FLOOR_Y - round(f.y) + 8)
        rect = rect.clip(self._glitch.get_rect())
        self.surface.blit(glitch_layer(self._glitch, rect, self.t), rect)
        self._windows.append((f.x, FLOOR_Y - f.y - 140, exe_name(f)))    # over everyone: drawn after the bodies
        return out
```

- [ ] **Step 5: A snapshot**

In `tools/snapshot.py`, add after `select_frame`:

```python
def super_frames(out_dir: str) -> None:
    """SUPERposition: the HUD bar half full and full, the call, and DOS's BLUE SCREEN OF DEATH
    (the freeze, and the frame his drop lands)."""
    from brawl_ket import basis
    from brawl_ket.config import SUPER_FREEZE
    from brawl_ket.fight import Fight
    from brawl_ket.fighter import FighterInput
    from brawl_ket.moves import BLUE_SCREEN
    from brawl_ket.superpos import FULL
    surface = pygame.Surface((W, H))
    r = Renderer(surface)
    fight = Fight({"p1": DOS, "p2": ROBERT}, seed=1)
    fight.fighters["p1"].x, fight.fighters["p2"].x = 250.0, 400.0
    fight.meters["p2"].fill = {basis.Z_BASIS: FULL, basis.X_BASIS: FULL // 3}
    fight.meters["p1"].fill = {basis.Z_BASIS: FULL, basis.X_BASIS: FULL}
    r.draw_fight(fight, [], {"p1": 0, "p2": 0})
    save(surface, out_dir, "super_bar.png")
    r.draw_fight(fight, fight.step({"p1": FighterInput(a=True, b=True)}), {"p1": 0, "p2": 0})
    for _ in range(12):
        r.draw_fight(fight, fight.step({}), {"p1": 0, "p2": 0})
    save(surface, out_dir, "super_call.png")
    for _ in range(SUPER_FREEZE - 12 + BLUE_SCREEN.startup + 6):
        r.draw_fight(fight, fight.step({}), {"p1": 0, "p2": 0})
    save(surface, out_dir, "super_bsod_freeze.png")
    for _ in range(60):
        events = fight.step({})
        r.draw_fight(fight, events, {"p1": 0, "p2": 0})
        if any(e.kind == "bsod_land" for e in events):
            save(surface, out_dir, "super_bsod_flash.png")
            r.draw_fight(fight, fight.step({}), {"p1": 0, "p2": 0})
            save(surface, out_dir, "super_bsod_crash.png")
            break
```

Call it in `main` after `select_frame(out_dir)`: `super_frames(out_dir)`. Add its five files to
the docstring's list: `- super_bar.png, super_call.png, super_bsod_freeze.png, super_bsod_flash.png,
super_bsod_crash.png: SUPERposition's bar (DOS full, ROBERT a third of purple), the call, and
DOS's BLUE SCREEN OF DEATH;`. (`DOS`, `ROBERT`, `W`, `H`, `Renderer` are imported at the top of
`tools/snapshot.py` already; check.)

- [ ] **Step 6: Run the tests, and look**

Run: `uv run pytest -q tests/test_render.py`
Expected: PASS.

Run: `SDL_VIDEODRIVER=dummy uv run python tools/snapshot.py /tmp/brawl-snaps` and open
`super_bar.png`, `super_call.png`, `super_bsod_freeze.png`, `super_bsod_flash.png`,
`super_bsod_crash.png`. Compare `super_bsod_freeze.png` with the look script's variant B
(`uv run python ../docs/superpowers/specs/2026-10-22-brawl-ket-superposition-bsod-look.py /tmp/bsod-look.png`):
the strip, the glitching rival and the window must read the same.

- [ ] **Step 7: Commit**

```bash
git add src/brawl_ket/dos.py src/brawl_ket/render.py tools/snapshot.py tests/test_render.py
git commit -m "feat: :lipstick: Brawl-Ket: the BLUE SCREEN OF DEATH's look: the strip, the glitch, the window, the flash

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 6: The CPU, the benchmark, balance, the README

**Files:**
- Modify: `src/brawl_ket/bot.py` (constants, `input`, new `_super` and `_dodge_super`, the feint)
- Modify: `tools/benchmark.py` (a BSOD run)
- Modify: `tests/test_balance.py` (only if a pairing moves past the bar), `README.md`
- Test: `tests/test_bot.py`

**Interfaces:**
- Consumes: `Fight.meters`, `Meter.full`, `Meter.share`; `BLUE_SCREEN`, `CRASH_REACH`.
- Produces: `bot.SUPER_DODGE_ODDS = 0.1`, `bot.LOPSIDED_FEINT = 0.06`; `Bot._super(fight, me, rival, dist) -> bool`;
  `Bot._dodge_super(me, rival, dist) -> bool`.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_bot.py`:

```python


# --- SUPERposition ----------------------------------------------------------------------------------


def test_dos_fires_his_blue_screen_with_a_full_bar_and_a_rival_on_the_ground_in_reach():
    from brawl_ket import basis
    from brawl_ket.moves import CHARACTERS
    from brawl_ket.superpos import FULL
    fight = Fight({"p1": CHARACTERS["DOS"], "p2": ROBERT}, seed=1)
    fight.fighters["p1"].x, fight.fighters["p2"].x = 300.0, 450.0
    fight.meters["p1"].fill = {basis.Z_BASIS: FULL, basis.X_BASIS: FULL}
    bot = Bot("p1", 1)
    inp = bot.input(fight)
    assert inp.a and inp.b


def test_not_with_the_rival_out_of_reach_or_in_the_air():
    from brawl_ket import basis
    from brawl_ket.config import CRASH_REACH
    from brawl_ket.moves import CHARACTERS
    from brawl_ket.superpos import FULL
    for gap, y in ((CRASH_REACH + 30, 0.0), (100.0, 60.0)):
        fight = Fight({"p1": CHARACTERS["DOS"], "p2": ROBERT}, seed=1)
        fight.fighters["p1"].x, fight.fighters["p2"].x = 300.0, 300.0 + gap
        fight.fighters["p2"].y = y
        fight.meters["p1"].fill = {basis.Z_BASIS: FULL, basis.X_BASIS: FULL}
        inp = Bot("p1", 1).input(fight)
        assert not (inp.a and inp.b)


def test_a_bot_jumps_away_from_a_blue_screen_winding_up_in_reach(monkeypatch):
    import brawl_ket.bot as bot_module
    from brawl_ket.moves import BLUE_SCREEN, CHARACTERS
    monkeypatch.setattr(bot_module, "SUPER_DODGE_ODDS", 1.0)
    fight = Fight({"p1": ROBERT, "p2": CHARACTERS["DOS"]}, seed=1)
    fight.fighters["p1"].x, fight.fighters["p2"].x = 300.0, 420.0
    dos = fight.fighters["p2"]
    dos.action, dos.move, dos.slot, dos.frame = "attack", BLUE_SCREEN, "super", 1
    inp = Bot("p1", 1).input(fight)
    assert inp.up and inp.dx == -1
```

- [ ] **Step 2: Run them to see them fail**

Run: `uv run pytest -q tests/test_bot.py -k "blue_screen or reach"`
Expected: FAIL (`assert inp.a and inp.b`).

- [ ] **Step 3: The CPU**

In `src/brawl_ket/bot.py`:

Extend the imports: `from .config import CRASH_REACH, TRAP_MAX`.

After `KIDS_STRIKE_ODDS = 0.017`, add:

```python
# SUPERposition: it fires a super as soon as its bar is full and the super would land; it jumps
# away from a BLUE SCREEN OF DEATH winding up in reach, a chance a frame of its startup; and it
# feints (switches at range) a little more often while one half is full and the other isn't
SUPER_DODGE_ODDS = 0.1
LOPSIDED_FEINT = 0.06
```

In `input`, after:

```python
        if me.action in _BUSY:
            self.chain.clear()
            return FighterInput(down=self.down)
        toward = 1 if rival.x > me.x else -1
        dist = abs(rival.x - me.x)
```

add:

```python
        if self._super(fight, me, rival, dist):
            self.gap = PRESS_GAP
            return FighterInput(a=True, b=True)
        if self._dodge_super(me, rival, dist):
            return FighterInput(up=True, dx=-toward)
```

Add the methods after `would_hurt_shot`:

```python
    def _super(self, fight: Fight, me, rival, dist: float) -> bool:
        """Fire the super: the bar full, free on the ground, and the rival where it lands."""
        move = me.char.extra.get("super")
        if move is None or not fight.meters[self.player].full or self.gap \
                or me.action not in ("idle", "walk", "crouch"):
            return False
        if move.crash is not None:      # BLUE SCREEN OF DEATH: a rival on the ground in reach
            return rival.y == 0 and dist <= CRASH_REACH - 20 and not rival.boxed and not rival.intangible
        return False

    def _dodge_super(self, me, rival, dist: float) -> bool:
        """Jump away from a BLUE SCREEN OF DEATH winding up in reach (in the air, it can't freeze you)."""
        m = rival.move
        return (rival.action == "attack" and m is not None and m.crash is not None and rival.phase == "startup"
                and dist <= CRASH_REACH + 10 and me.action in ("idle", "walk", "crouch")
                and self.rng.random() < SUPER_DODGE_ODDS)
```

`_on_ground` needs the fight for the bar. Change its signature:

```python
    def _on_ground(self, me, rival, toward: int, dist: float) -> FighterInput:
```

to:

```python
    def _on_ground(self, fight: Fight, me, rival, toward: int, dist: float) -> FighterInput:
```

and its call at the end of `input`, `return self._on_ground(me, rival, toward, dist)`, to:

```python
        return self._on_ground(fight, me, rival, toward, dist)
```

(search `tests/` for other calls of `_on_ground` and pass the fight there too). Then in it, replace:

```python
        if roll < 0.04 and ready and me.char.fixed_basis is None:
```

with:

```python
        meter = fight.meters[self.player]
        lopsided = max(meter.share(b) for b in meter.fill) >= 1.0 > min(meter.share(b) for b in meter.fill)
        if roll < (LOPSIDED_FEINT if lopsided else 0.04) and ready and me.char.fixed_basis is None:
```

- [ ] **Step 4: The benchmark**

In `tools/benchmark.py`, before `m, times = M.Match(), []`, add:

```python
    # SUPERposition: DOS's BLUE SCREEN OF DEATH over and over (his bar refilled every frame)
    from brawl_ket.basis import X_BASIS, Z_BASIS
    from brawl_ket.superpos import FULL
    fight, times = None, []
    for i in range(FRAMES):
        if fight is None or fight.over:
            fight = Fight({"p1": CHARACTERS["DOS"], "p2": CHARACTERS["ROBERT"]})
            bots = {p: Bot(p, i + k) for k, p in enumerate(PLAYERS)}
        fight.meters["p1"].fill = {Z_BASIS: FULL, X_BASIS: FULL}
        t = time.perf_counter()
        events = fight.step({p: b.input(fight) for p, b in bots.items()})
        renderer.draw_fight(fight, events, {"p1": 0, "p2": 0})
        times.append(time.perf_counter() - t)
    report("DOS supers", times[60:])
```

- [ ] **Step 5: Run the tests**

Run: `uv run pytest -q tests/test_bot.py`
Expected: PASS.

- [ ] **Step 6: The whole check, balance and the README**

Run, in order:

```bash
uv run pytest -q
uvx --from 'ruff==0.15.22' ruff check src tests tools
SDL_VIDEODRIVER=dummy uv run python tools/snapshot.py /tmp/brawl-snaps
SDL_VIDEODRIVER=dummy uv run python tools/benchmark.py
uv run python tools/balance.py 100
```

Expected: all tests pass (the balance test's xfails aside); ruff clean; the snapshot exits 0; the
benchmark's `DOS supers` line under 2 ms mean; balance printed.

Balance: compare every DOS pairing with the table before this plan (the 2026-10-22 feel tuning's
100-round run: ROBERT v DOS 63/37, BOHR v DOS 61/39, PHOEBE v DOS 60/40, ERWIN v DOS 55/45,
DOS v M-CUTIE 38/62, DOS v ALICE & BOB 54/46). If a DOS pairing in `tests/test_balance.py`'s
`PAIRS` now fails, record it in `OVER_THE_BAR` with its measured share and the reason (only DOS
has a super so far: the others get theirs in part 2), in the existing comment style. Do not tune
numbers to pass it.

README: in `brawl-ket/README.md`, after the **Feel tuning** paragraph, add:

```markdown
**SUPERposition (2026-10-22):** every fighter has a bar under their name, a green half and a
purple half. Damage you deal fills the half of the colour you are in (damage you take, half as
fast), so only fighting in both colours fills it; DOS, who can't switch, fills by the colour of
his hits. Full, it shines and says A+B!: A and B together fire your super, which freezes the
fight for its call (SUPERposition!) and hurts in either colour. The bar carries over between
rounds. So far DOS has his, BLUE SCREEN OF DEATH: everyone on the ground near him freezes under
an error window, and he comes down on them (25). Design:
`../docs/superpowers/specs/2026-10-22-brawl-ket-superposition-design.md`.
```

and add a row to the module table (after `basis.py`'s):

```markdown
| `superpos.py` | SUPERposition's bar: two halves, how damage fills them, full and empty. Pure. |
```

- [ ] **Step 7: Commit**

```bash
git add src/brawl_ket/bot.py tools/benchmark.py tests/test_bot.py tests/test_balance.py README.md
git commit -m "feat: :robot: Brawl-Ket: the CPU fires and dodges the BLUE SCREEN; SUPERposition in the README

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

## Done means

- `uv run pytest -q` passes (the balance test's xfails aside), ruff is clean, the snapshot tool
  exits 0 and writes the five `super_*.png` files, the benchmark's every line is under 2 ms mean.
- In a round: hits fill the halves as the spec says; a full bar shows A+B!; A+B fires DOS's
  BLUE SCREEN OF DEATH with the freeze and the call; a rival on the ground in reach freezes
  under its error window and takes 25 when he lands, with one blue frame; a jump dodges it.
- Then: deploy to the cabinet (`./deploy_batocera.sh root@10.42.0.100`, md5-verified) for the
  user to try the bar and DOS's super, and start part 2 with the six look sheets.
