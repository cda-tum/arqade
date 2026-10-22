# Brawl-Ket SUPERposition, part 2 (the six other supers) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give ROBERT, BOHR, PHOEBE, ERWIN, M-CUTIE and ALICE & BOB their supers (BLOCH SPHERE,
WAVEFUNCTION COLLAPSE, COHERENT BEAM, NINE LIVES, DILUTION FRIDGE, ONE-TIME PAD), drawn as the
approved look sheets show, fought by the CPU.

**Architecture:** Part 1 (`2026-10-22-brawl-ket-superposition-core.md`) built the bar, A+B,
the freeze and DOS's BLUE SCREEN OF DEATH. Part 2 adds six generic Move twists and builds the
six supers from them:
- **`lock`:** frames before the active ones when the fight fixes the target, the rival's x then,
  into `Fighter.target_x`. With **`lock_range`** and **`lock_ground`** it can miss: `target_x` is None.
- **`lock_hold`:** a hold put on the rival when the lock catches them.
- **`flank`:** the pair re-forms that far either side of the target.
- **`remote`:** the hitbox sits at `target_x`, not round the fighter.
- **`hits`:** the most times a repeating move (`hit_every`) may hit.
- **`follow`:** a move that starts the moment this one's active frames end, or its `hits` are spent.
- **`warp`:** a follow-up starts this far in front of the target.

The art lives in a new `superart.py`, ported from the look script. The renderer calls it
from `draw_fight` (the overlays) and `_fighter` (ROBERT's sphere and ERWIN's box instead of
their puppets).

**Tech Stack:** Python 3.11, pygame 2.5.2, pytest, ruff 0.15.22, uv.

**Spec:** `docs/superpowers/specs/2026-10-22-brawl-ket-superposition-design.md` section 4; looks:
`docs/superpowers/specs/2026-10-22-brawl-ket-superposition-looks.py` (approved by the user, 2026-10-22).

## Global Constraints

- Worktree `/home/damian/03_personal/games/.claude/worktrees/brawl-ket-alice-bob/`, branch
  `brawl-ket-alice-bob`; run every command from its `brawl-ket/` directory.
- Python 3.11, pygame 2.5.2 exactly; no new dependencies; LF line endings.
- Every super: `kind="super"`, colour `BOTH`, about 25 damage in all, its own damage fills no bar.
- Dodges are by position only, as spec section 4 gives each.
- The six older supers' numbers are the spec's (section 4); the bot's are levers, not the moves'.
- Commits: gitmoji style, explicit paths, ending with `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.
- Checks: `uv run pytest -q`; `uvx --from 'ruff==0.15.22' ruff check src tests tools`;
  `SDL_VIDEODRIVER=dummy uv run python tools/snapshot.py <dir>`; `uv run python tools/balance.py 100`;
  `SDL_VIDEODRIVER=dummy uv run python tools/benchmark.py`.

## File Structure

- Modify `src/brawl_ket/moves.py`: the seven Move fields; the six supers, their follow-ups and hold; each Character's `extra["super"]`.
- Modify `src/brawl_ket/fighter.py`: `target_x`, `hit_count`, the lock event, follow-ups, warp.
- Modify `src/brawl_ket/fight.py`: `_lock`, remote hitboxes, the hit cap, counting hits, a decohered Bob back for the super.
- Modify `src/brawl_ket/echo.py`: `recohere()`.
- Create `src/brawl_ket/superart.py`: the supers' drawing (from the look script).
- Modify `src/brawl_ket/render.py`: `_super_art`, `_super_body`, `MOVE_LABELS`.
- Modify `src/brawl_ket/audio.py`: the supers' sounds.
- Modify `src/brawl_ket/bot.py`: fire and dodge every super.
- Modify `tools/snapshot.py`, `tools/benchmark.py`, `README.md`, `tests/test_balance.py`.
- Tests: `tests/test_superpos.py`, `tests/test_render.py`, `tests/test_bot.py`.

---

### Task 1: The supers' twists in the engine

**Files:**
- Modify: `src/brawl_ket/moves.py` (`Move`)
- Modify: `src/brawl_ket/fighter.py` (`__init__`, `_advance`, `_move_effects`, `_start_move`, a new `_follow`)
- Modify: `src/brawl_ket/fight.py` (`_fighter_events`, a new `_lock`, `_fire`, `_resolve_hits`, `_move_strike`)
- Modify: `src/brawl_ket/echo.py` (`recohere`)
- Test: `tests/test_superpos.py`

**Interfaces:**
- Produces: `Move.lock: int = -1`, `Move.lock_range: int = 0`, `Move.lock_ground: bool = False`,
  `Move.lock_hold: Move | None = None`, `Move.flank: int = 0`, `Move.remote: bool = False`,
  `Move.hits: int = 0`, `Move.follow: Move | None = None`, `Move.warp: int = 0`.
- Produces: `Fighter.target_x: float | None`, `Fighter.hit_count: int`; the local event `("lock", {"move": m})`.
- Produces: Events `lock` (player = who locked, x = target) and `lock_miss` (player = who missed).
- Produces: `Echo.recohere() -> None`.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_superpos.py`:

```python


# --- part 2: the twists (lock, remote, hits, follow, warp, flank) ----------------------------------

from brawl_ket.moves import LOW  # noqa: E402


def with_super(char, move):
    return replace(char, extra=MappingProxyType({**char.extra, "super": move}))


def fire(fight: Fight, key: str = "p1") -> None:
    """Fill the bar, fire, and sit out the call."""
    full(fight, key)
    fight.step({key: AB})
    for _ in range(SUPER_FREEZE):
        fight.step({})


# a remote strike that locks 4 frames before it lands
REMOTE = Move("REMOTE", 10, 4, 10, Box(-30, 0, 60, 300), BOTH, MID, damage=25, hitstun=30, knockback=0.0,
              knockdown=True, kind="super", lock=4, remote=True)


def test_a_lock_fixes_the_target_where_the_rival_stood_then():
    fight = fight_of(with_super(ROBERT, REMOTE), ROBERT, gap=200.0)
    fire(fight)
    events = run(fight, REMOTE.startup - REMOTE.lock)
    assert fight.fighters["p1"].target_x == 500.0
    assert [(e.kind, e.player, e.x) for e in events if e.kind == "lock"] == [("lock", "p1", 500.0)]


def test_a_remote_hitbox_lands_on_the_target_not_round_the_fighter():
    fight = fight_of(with_super(ROBERT, REMOTE), ROBERT, gap=200.0)
    fire(fight)
    run(fight, REMOTE.startup + 2)
    assert fight.fighters["p2"].health == ROBERT.health - 25


def test_who_moves_away_after_the_lock_is_missed():
    fight = fight_of(with_super(ROBERT, REMOTE), ROBERT, gap=200.0)
    fire(fight)
    run(fight, REMOTE.startup - REMOTE.lock)
    fight.fighters["p2"].x = 600.0
    run(fight, REMOTE.lock + 4)
    assert fight.fighters["p2"].health == ROBERT.health


def test_a_lock_with_a_range_misses_one_too_far_or_in_the_air():
    near = replace(REMOTE, lock=0, lock_range=100, lock_ground=True)
    fight = fight_of(with_super(ROBERT, near), ROBERT, gap=150.0)
    fire(fight)
    events = run(fight, near.startup + 4)
    assert fight.fighters["p1"].target_x is None and "lock_miss" in kinds(events)
    assert fight.fighters["p2"].health == ROBERT.health
    fight = fight_of(with_super(ROBERT, near), ROBERT, gap=80.0)
    fire(fight)
    fight.step({"p2": FighterInput(up=True)})
    run(fight, near.startup + 4)
    assert fight.fighters["p2"].health == ROBERT.health


def test_hits_caps_a_repeating_move():
    ROLL = Move("ROLL", 2, 60, 1, Box(-40, 0, 120, 120), BOTH, MID, damage=4, hitstun=16, knockback=0.0,
                kind="super", hit_every=6, hits=3)
    fight = fight_of(with_super(ROBERT, ROLL), ROBERT, gap=60.0)
    fire(fight)
    run(fight, 80)
    assert fight.fighters["p2"].health == ROBERT.health - 12
    assert fight.fighters["p1"].hit_count == 3 or fight.fighters["p1"].move is None


def test_a_follow_up_starts_when_the_hits_are_spent_and_keeps_the_target():
    after = Move("AFTER", 2, 4, 10, Box(-30, 0, 60, 300), BOTH, MID, damage=9, hitstun=30, knockback=0.0,
                 knockdown=True, kind="super", remote=True)
    first = replace(REMOTE, damage=4, hitstun=16, knockdown=False, active=40, hit_every=6, hits=4, follow=after)
    fight = fight_of(with_super(ROBERT, first), ROBERT, gap=200.0)
    fire(fight)
    run(fight, first.startup + 40 + 6 * 10)        # (every hit's hitstop holds the frames back)
    assert fight.fighters["p2"].health == ROBERT.health - 4 * 4 - 9
    assert fight.fighters["p1"].move in (after, None)


def test_a_warp_starts_the_follow_up_in_front_of_the_target():
    after = Move("WARPED", 2, 4, 10, Box(10, 20, 60, 90), BOTH, MID, damage=9, hitstun=30, knockback=0.0,
                 knockdown=True, kind="super", warp=40)
    first = replace(REMOTE, remote=False, follow=after)     # (it hits nothing: no hitstop)
    fight = fight_of(with_super(ROBERT, first), ROBERT, gap=200.0)
    fire(fight)
    run(fight, first.startup + first.active)
    assert abs(fight.fighters["p1"].x - 460.0) <= 3 and fight.fighters["p1"].move is after   # (the push box nudges)


def test_a_lock_hold_holds_the_rival_and_a_flank_puts_the_pair_either_side():
    hold = Move("HELD", 0, 1, 1, None, BOTH, MID, damage=0, hitstun=70, knockback=0.0, hold=True)
    pad = replace(REMOTE, lock=0, lock_range=100, lock_ground=True, lock_hold=hold, flank=50, remote=False)
    fight = fight_of(with_super(ALICE_BOB, pad), ROBERT, gap=90.0)
    fire(fight)
    run(fight, pad.startup)
    rival, alice, bob = fight.fighters["p2"], fight.fighters["p1"], fight.echoes["p1"]
    assert rival.action == "hitstun" and rival.stun > 60
    assert (alice.x, bob.x) == (390.0 - 50, 390.0 + 50) and bob.anchored


def test_a_decohered_bob_comes_back_for_their_super():
    fight = fight_of(with_super(ALICE_BOB, REMOTE), ROBERT, gap=200.0)
    fight.echoes["p1"].decohere()
    full(fight)
    events = fight.step({"p1": AB})
    assert fight.echoes["p1"].here and "recohere" in kinds(events)
```

- [ ] **Step 2: Run them to see them fail**

Run: `uv run pytest -q tests/test_superpos.py -k "lock or remote or moves_away or caps or follow or warp or flank or decohered"`
Expected: FAIL with `TypeError: Move.__init__() got an unexpected keyword argument 'lock'`.

- [ ] **Step 3: The Move fields**

In `src/brawl_ket/moves.py`, in `Move`, after the `seek: int = 0 ...` field and its comment line, add:

```python
    lock: int = -1                      # >= 0: this many frames before the active ones the fight fixes the
                                        # target, the rival's x then (Fighter.target_x) ...
    lock_range: int = 0                 # ... missing a rival further than this (0: any distance) ...
    lock_ground: bool = False           # ... or one in the air (target_x None: a whiff)
    lock_hold: Move | None = None       # a hold the lock puts on the rival it catches (ONE-TIME PAD)
    flank: int = 0                      # ... and the pair re-forms this far either side of them
    remote: bool = False                # the hitbox sits at target_x, not round the fighter
    hits: int = 0                       # > 0: a repeating move (hit_every) hits at most this many times
    follow: Move | None = None          # a move that starts as this one's active frames end (or its
                                        # hits are spent), keeping the target
    warp: int = 0                       # > 0: a follow-up starts this far in front of the target
```

- [ ] **Step 4: The fighter's part**

In `src/brawl_ket/fighter.py`, `Fighter.__init__`, after `self.glitch = 0 ...`:

```python
        self.target_x: float | None = None  # a super's lock: where the rival stood (None: none, or a miss)
        self.hit_count = 0                  # times the move in progress has hit (the fight counts)
```

In `_advance`, replace:

```python
            if self.frame >= self.startup + m.active + m.recovery:
                self._end_move()
            else:
                self._move_effects(m, events)
```

with:

```python
            spent = m.hits and self.hit_count >= m.hits and self.phase == "active"
            if m.follow is not None and (self.frame >= self.startup + m.active or spent):
                self._follow(m.follow, events)
            elif self.frame >= self.startup + m.active + m.recovery:
                self._end_move()
            else:
                self._move_effects(m, events)
```

At the top of `_move_effects`, before `if self.phase == "active":`, add:

```python
        if m.lock >= 0 and self.frame == self.startup - m.lock:     # a super locks on: the fight decides
            events.append(("lock", {"move": m}))
```

In `_start_move`, after `self.move_hit = False`:

```python
        self.hit_count = 0
        self.target_x = None
```

Add the method after `_start_move`:

```python
    def _follow(self, move: Move, events: list) -> None:
        """A super's next part: it starts at once, keeping the target (a warp puts the fighter
        `warp` px in front of it, facing it)."""
        target = self.target_x
        self._start_move(self.slot or "super", move, False, events)
        self.target_x = target
        if move.warp and target is not None:
            self.x = min(max(target - self.facing * move.warp, STAGE_LEFT), STAGE_RIGHT)
        self._move_effects(move, events)
```

- [ ] **Step 5: The fight's part**

In `src/brawl_ket/fight.py`:

In `_fighter_events`, add before `elif kind == "swap":`:

```python
            elif kind == "lock":
                self._lock(key, f, data["move"], events)
```

Add the method after `_crash`:

```python
    def _lock(self, key: str, f: Fighter, m: Move, events: list[Event]) -> None:
        """A super locks on: its target is where the rival stands now, unless the rival is out of
        reach of it (lock_range), in the air (lock_ground), down, getting up, tunnelling or in THE
        BOX: then it misses (target None). A catch may hold the rival (lock_hold) and put the pair
        either side of them (flank)."""
        rival_key = _other(key)
        rival = self.fighters[rival_key]
        missed = rival.action == "knockdown" or rival.wakeup or rival.intangible or rival.boxed \
            or (m.lock_range and abs(rival.x - f.x) > m.lock_range) or (m.lock_ground and rival.y > 0)
        if missed:
            f.target_x = None
            events.append(Event("lock_miss", key, None, f.x, FLOOR_Y))
            return
        f.target_x = rival.x
        events.append(Event("lock", key, None, rival.x, FLOOR_Y))
        if m.lock_hold is not None:
            for body in self.bodies(rival_key):
                body.take_hit(m.lock_hold, basis.Y, f.facing)
        echo = self.echoes.get(key)
        if m.flank and echo is not None:
            side = 1 if rival.x >= f.x else -1
            f.x = _clamp(rival.x - side * m.flank)
            echo.x, echo.y = _clamp(rival.x + side * m.flank), 0.0
            f.facing, echo.facing = side, -side
            echo.anchored = True
            events.append(Event("teleport", key, None, f.x, FLOOR_Y))
```

In `_fire`, after `self.meters[key].empty()`, add:

```python
        echo = self.echoes.get(key)
        if echo is not None and not echo.here:      # their super brings a decohered Bob back at once
            echo.recohere()
            events.append(Event("recohere", key, None, echo.x, FLOOR_Y))
```

In `_resolve_hits`, replace:

```python
            if st.body is not None:
                f = st.body
                f.move_hit = True
                f.hit_frame = f.frame       # a repeating move (CHARGE NOISE) counts from here
```

with:

```python
            if st.body is not None:
                f = st.body
                f.move_hit = True
                f.hit_frame = f.frame       # a repeating move (CHARGE NOISE) counts from here
                f.hit_count += 1
```

In `_move_strike`, replace:

```python
        # a move hits once, except one that repeats (hit_every frames after its last hit)
        if f.move_hit and not (m.hit_every and f.frame - f.hit_frame >= m.hit_every):
            return
```

with:

```python
        # a move hits once, except one that repeats (hit_every frames after its last hit, at most
        # `hits` times)
        if f.move_hit and not (m.hit_every and f.frame - f.hit_frame >= m.hit_every):
            return
        if m.hits and f.hit_count >= m.hits:
            return
        if m.remote and f.target_x is None:         # a super's lock that missed: nothing to hit
            return
```

and replace, a few lines below:

```python
            touch = self._touch(f.world_box(m.hitbox), rival)
```

with:

```python
            box = _world_box(f.target_x, 0.0, f.facing, m.hitbox) if m.remote else f.world_box(m.hitbox)
            touch = self._touch(box, rival)
```

- [ ] **Step 6: Bob comes back**

In `src/brawl_ket/echo.py`, after `forget_presses`:

```python
    def recohere(self) -> None:
        """Back at once (their super): as if his time away had run out."""
        if not self.here:
            self._come_back()
```

- [ ] **Step 7: Run the tests**

Run: `uv run pytest -q tests/test_superpos.py tests/test_fighter.py tests/test_fight.py tests/test_alice_bob.py tests/test_audio.py`
Expected: PASS. (`test_every_fight_event_is_mapped` needs the new events in `EVENT_SOUNDS`: add
`"lock": None, "lock_miss": None,` after `"crash": "crash", "bsod_land": "bsod_land",` in
`src/brawl_ket/audio.py`; Task 2 gives `lock` its sound.)

Run the digest (part 1's Task 1, Step 7): unchanged from part 1's end (no fighter uses these yet).

- [ ] **Step 8: Commit**

```bash
git add src/brawl_ket/moves.py src/brawl_ket/fighter.py src/brawl_ket/fight.py src/brawl_ket/echo.py src/brawl_ket/audio.py tests/test_superpos.py
git commit -m "feat: :sparkles: Brawl-Ket: the supers' twists: lock-on, remote hits, a hit cap, follow-ups, warp, flank

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 2: The six supers

**Files:**
- Modify: `src/brawl_ket/moves.py` (the moves; each Character's `extra`)
- Modify: `src/brawl_ket/audio.py` (their sounds)
- Modify: `src/brawl_ket/render.py` (`MOVE_LABELS`)
- Test: `tests/test_superpos.py`, `tests/test_render.py`

**Interfaces:**
- Consumes: Task 1's twists.
- Produces: `moves.BLOCH_SPHERE`, `H_UPPERCUT`, `WAVE_COLLAPSE`, `COHERENT_BEAM`, `NINE_LIVES`,
  `NINE_SWIPE`, `DILUTION_FRIDGE`, `FROST_WAVE`, `ONE_TIME_PAD`, `OTP_HOLD`, `PADLOCK`;
  every Character but BOB has `extra["super"]`.

The numbers are the spec's section 4:

| Super | Who | Frames | Hits |
|---|---|---|---|
| BLOCH SPHERE | ROBERT | startup 8, rolls 6 px/frame up to 50 | LOW, 4 hits of 4 every 6, then H-GATE UPPERCUT (MID, 9, knockdown, he switches) |
| WAVEFUNCTION COLLAPSE | BOHR | startup 36, locks at 24 | a pillar on the locked spot: MID, 25, knockdown |
| COHERENT BEAM | PHOEBE | startup 12, active 60 | floor to 110 px, to the screen's edge: MID, 5 hits of 5 every 12 |
| NINE LIVES | ERWIN | startup 10, locks then (160 px) | 8 ghost pounces LOW 2 every 8, then NINE SWIPE (warps in, MID 9, knockdown) |
| DILUTION FRIDGE | M-CUTIE | startup 42, locks at 30 | the fridge: MID 20 knockdown; then FROST WAVE: LOW 5, 150 px either side |
| ONE-TIME PAD | ALICE & BOB | startup 6, locks then (100 px, on the ground) | holds the rival, flank 50; 6 passes MID 3 every 10, then PADLOCK MID 7 knockdown |

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_superpos.py`:

```python


# --- part 2: the six supers --------------------------------------------------------------------------

from brawl_ket.config import FLOOR_Y  # noqa: E402
from brawl_ket.moves import (  # noqa: E402
    BLOCH_SPHERE,
    COHERENT_BEAM,
    DILUTION_FRIDGE,
    H_UPPERCUT,
    NINE_LIVES,
    NINE_SWIPE,
    ONE_TIME_PAD,
    WAVE_COLLAPSE,
)

ALL_SUPERS = {"ROBERT": "BLOCH SPHERE", "BOHR": "WAVEFUNCTION COLLAPSE", "PHOEBE": "COHERENT BEAM",
              "ERWIN": "NINE LIVES", "DOS": "BLUE SCREEN OF DEATH", "M-CUTIE": "DILUTION FRIDGE",
              "ALICE & BOB": "ONE-TIME PAD"}


def test_everyone_has_their_super_and_it_is_both_colours():
    for name, sup in ALL_SUPERS.items():
        m = CHARACTERS[name].extra["super"]
        assert m.name == sup and m.kind == "super" and m.colour == BOTH, name
        part = m
        while part is not None:                     # its follow-ups too
            assert part.kind == "super" and part.colour == BOTH, part.name
            part = part.follow


def total(m) -> int:
    n = 0
    while m is not None:
        n += m.damage * (m.hits or 1)
        m = m.follow
    return n


def test_each_is_about_25_in_all():
    for name in ALL_SUPERS:
        m = CHARACTERS[name].extra["super"]
        if m.name == "DILUTION FRIDGE":
            assert total(m) == 25                   # the fridge and the frost don't both land on one rival
        else:
            assert total(m) == 25, name


def landed(name: str, rival=ROBERT, gap=60.0, frames=200, setup=None) -> Fight:
    fight = fight_of(CHARACTERS[name], rival, gap)
    if setup:
        setup(fight)
    fire(fight)
    run(fight, frames)
    return fight


def test_bloch_sphere_rolls_in_for_4_hits_then_the_uppercut_and_he_switches():
    fight = landed("ROBERT", gap=200.0)
    assert fight.fighters["p2"].health == ROBERT.health - 25
    assert fight.fighters["p1"].basis == X


def test_bloch_sphere_rolls_six_px_a_frame_and_a_jump_clears_it():
    fight = fight_of(CHARACTERS["ROBERT"], ROBERT, 300.0)
    fire(fight)
    x = fight.fighters["p1"].x
    run(fight, BLOCH_SPHERE.startup + 5)               # its first active frame is the startup's last
    assert fight.fighters["p1"].x == x + 6 * 6
    fight = fight_of(CHARACTERS["ROBERT"], ROBERT, 150.0)
    fire(fight)
    run(fight, BLOCH_SPHERE.startup + 8)
    fight.step({"p2": FighterInput(up=True)})
    run(fight, 14)
    assert fight.fighters["p2"].health >= ROBERT.health - H_UPPERCUT.damage    # the roll passed under


def test_wavefunction_collapse_falls_where_they_stood_at_the_lock():
    fight = landed("BOHR", gap=300.0)
    assert fight.fighters["p2"].health == ROBERT.health - 25
    fight = fight_of(CHARACTERS["BOHR"], ROBERT, 300.0)
    fire(fight)
    run(fight, WAVE_COLLAPSE.startup - WAVE_COLLAPSE.lock + 1)
    fight.fighters["p2"].x -= 120                   # walked off the ring (towards him: the stage ends behind)
    run(fight, 40)
    assert fight.fighters["p2"].health == ROBERT.health


def test_coherent_beam_hits_five_times_crouching_or_not_and_its_top_is_110_px():
    fight = landed("PHOEBE", gap=300.0, setup=lambda f: setattr(f.fighters["p2"], "crouching", True))
    assert fight.fighters["p2"].health == ROBERT.health - 25
    phoebe = fight.fighters["p1"]
    _, top, _, h = phoebe.world_box(COHERENT_BEAM.hitbox)
    assert top + h == FLOOR_Y and h == 110


def test_nine_lives_eight_pounces_then_the_swipe_from_right_in_front():
    fight = landed("ERWIN", gap=120.0)
    assert fight.fighters["p2"].health == ROBERT.health - 25
    fight = fight_of(CHARACTERS["ERWIN"], ROBERT, 120.0)
    fire(fight)
    for _ in range(200):                            # (the pounces' hitstop holds the frames back)
        if fight.fighters["p1"].move is NINE_SWIPE:
            break
        fight.step({})
    assert fight.fighters["p1"].move is NINE_SWIPE
    assert abs(fight.fighters["p1"].x - (420.0 - NINE_SWIPE.warp)) <= 4     # (the push box nudges)


def test_nine_lives_misses_a_rival_out_of_its_reach():
    fight = landed("ERWIN", gap=NINE_LIVES.lock_range + 30.0)
    assert fight.fighters["p2"].health == ROBERT.health


def test_dilution_fridge_crushes_who_stays_and_frosts_who_got_out_but_not_who_jumps():
    fight = landed("M-CUTIE", gap=300.0)
    assert fight.fighters["p2"].health == ROBERT.health - 20
    fight = fight_of(CHARACTERS["M-CUTIE"], ROBERT, 300.0)
    fire(fight)
    run(fight, DILUTION_FRIDGE.startup - DILUTION_FRIDGE.lock + 1)
    fight.fighters["p2"].x -= 90                    # out of the shadow, into the frost
    run(fight, 60)
    assert fight.fighters["p2"].health == ROBERT.health - 5


def test_one_time_pad_holds_the_rival_between_them_for_25():
    fight = landed("ALICE & BOB", gap=80.0)
    rival, alice, bob = fight.fighters["p2"], fight.fighters["p1"], fight.echoes["p1"]
    assert rival.health == ROBERT.health - 25
    assert alice.x < rival.x < bob.x or bob.x < rival.x < alice.x


def test_one_time_pad_misses_out_of_reach_or_in_the_air():
    fight = landed("ALICE & BOB", gap=ONE_TIME_PAD.lock_range + 30.0)
    assert fight.fighters["p2"].health == ROBERT.health
```

In `tests/test_superpos.py`, change the part 1 test `test_a_fighter_with_no_super_never_waits`
(ROBERT has a super now): replace `fight = fight_of()` in it with
`fight = fight_of(replace(ROBERT, extra=MappingProxyType({})))`.

In `tests/test_render.py`'s `test_a_full_bar_says_a_plus_b_for_a_fighter_with_a_super`, replace
`fight = Fight({"p1": CHARACTERS[name], "p2": ROBERT})` with:

```python
        from types import MappingProxyType
        from dataclasses import replace as _replace
        char = CHARACTERS[name] if name == "DOS" else _replace(ROBERT, extra=MappingProxyType({}))
        fight = Fight({"p1": char, "p2": ROBERT})
```

(and update its comment: `# (a fighter with no super: no A+B!)`).

- [ ] **Step 2: Run them to see them fail**

Run: `uv run pytest -q tests/test_superpos.py -k "everyone or about_25 or bloch or wavefunction or coherent or nine or fridge or one_time"`
Expected: FAIL with `ImportError: cannot import name 'BLOCH_SPHERE'`.

- [ ] **Step 3: The moves**

In `src/brawl_ket/moves.py`, before the `CHARACTERS: dict[str, Character] = {...}` line, add:

```python
# --- SUPERposition: the six other supers (docs/superpowers/specs/2026-10-22-brawl-ket-superposition-design.md,
# 4; their look: 2026-10-22-brawl-ket-superposition-looks.py). All BOTH: they hurt either colour.

# ROBERT: BLOCH SPHERE. A Bloch sphere forms round him and he rolls in inside it, LOW (a jump
# clears it), 4 hits of 4; then an H-gate uppercut (9) flips its arrow to |1>, and him with it.
H_UPPERCUT = Move(
    "H-GATE UPPERCUT", 4, 6, 24, Box(6, 50, 36, 80), BOTH, MID,
    damage=9, hitstun=30, knockback=3.0, knockdown=True, kind="super", switch_self_on_hit=True,
    cue="h_gate", poses=("crouch", "slam", "slam"),
)
BLOCH_SPHERE = Move(
    "BLOCH SPHERE", 8, 50, 1, Box(-33, 0, 66, 66), BOTH, LOW,
    damage=4, hitstun=16, knockback=1.0, kind="super", hit_every=6, hits=4, lunge=6.0,
    hurt_active=Box(-30, 0, 60, 60), follow=H_UPPERCUT, cue="bloch",
    poses=("brace", "crouch", "crouch"),
)
# BOHR: WAVEFUNCTION COLLAPSE. A probability cloud spreads over the floor; 12 frames before it
# falls it locks on the rival's x, and a pillar of light falls there: 25, a knockdown.
WAVE_COLLAPSE = Move(
    "WAVEFUNCTION COLLAPSE", 36, 6, 30, Box(-30, 0, 60, 320), BOTH, MID,
    damage=25, hitstun=30, knockback=0.0, knockdown=True, kind="super", lock=12, remote=True,
    cue="collapse", poses=("stomp", "slam", "slam"),
)
# PHOEBE: COHERENT BEAM. A laser straight forward to the screen's edge, floor to 110 px up:
# 5 hits of 5. Only a jump above it passes over.
COHERENT_BEAM = Move(
    "COHERENT BEAM", 12, 60, 30, Box(20, 0, 660, 110), BOTH, MID,
    damage=5, hitstun=16, knockback=1.0, kind="super", hit_every=12, hits=5,
    cue="beam", poses=("throw_reach", "throw_reach", "throw_reach"),
)
# ERWIN: NINE LIVES. Into THE BOX, which splits into nine ERWINs round a rival within 160 px:
# eight ghost pounces, LOW, 2 each; then the real one warps in and swipes (9, a knockdown).
NINE_SWIPE = Move(
    "NINE LIVES", 2, 6, 30, Box(10, 20, 60, 90), BOTH, MID,
    damage=9, hitstun=30, knockback=3.0, knockdown=True, kind="super", warp=40,
    cue="swipe", poses=("swipe", "swipe", "idle"),
)
NINE_LIVES = Move(
    "NINE LIVES", 10, 64, 1, Box(-40, 0, 80, 40), BOTH, LOW,
    damage=2, hitstun=14, knockback=0.0, kind="super", hit_every=8, hits=8,
    lock=0, lock_range=160, remote=True, follow=NINE_SWIPE, cue="ghosts",
    poses=("box_duck", "box_duck", "box_duck"),
)
# M-CUTIE: DILUTION FRIDGE. A shadow follows the rival and locks 12 frames before a giant gold
# dilution refrigerator lands there (20, a knockdown); then a frosty shockwave, LOW, 150 px
# either side (5) for whoever got out of the shadow.
FROST_WAVE = Move(
    "DILUTION FRIDGE", 1, 6, 30, Box(-150, 0, 300, 30), BOTH, LOW,
    damage=5, hitstun=14, knockback=3.0, kind="super", remote=True,
    poses=("idle", "idle", "idle"),
)
DILUTION_FRIDGE = Move(
    "DILUTION FRIDGE", 42, 4, 1, Box(-35, 0, 70, 320), BOTH, MID,
    damage=20, hitstun=30, knockback=3.0, knockdown=True, kind="super", lock=12, remote=True,
    follow=FROST_WAVE, cue="fridge", poses=("slam", "slam", "slam"),
)
# ALICE & BOB: ONE-TIME PAD. A rival on the ground within 100 px of Alice is held, and the two
# re-form either side of them; the key passes through them six times (3 each), then a padlock
# snaps shut (7, a knockdown).
OTP_HOLD = Move(
    "ONE-TIME PAD", 0, 1, 1, None, BOTH, MID,
    damage=0, hitstun=75, knockback=0.0, hold=True,
)
PADLOCK = Move(
    "ONE-TIME PAD", 2, 4, 30, Box(-30, 0, 60, 140), BOTH, MID,
    damage=7, hitstun=30, knockback=3.0, knockdown=True, kind="super", remote=True,
    cue="padlock", poses=("fire", "fire", "idle"),
)
ONE_TIME_PAD = Move(
    "ONE-TIME PAD", 6, 60, 1, Box(-20, 20, 40, 100), BOTH, MID,
    damage=3, hitstun=14, knockback=0.0, kind="super", hit_every=10, hits=6,
    lock=0, lock_range=100, lock_ground=True, lock_hold=OTP_HOLD, flank=50, remote=True,
    follow=PADLOCK, cue="key_pass", poses=("catch", "fire", "fire"),
)


def _with_super(char: Character, move: Move) -> Character:
    return replace(char, extra=MappingProxyType({**char.extra, "super": move}))


ROBERT = _with_super(ROBERT, BLOCH_SPHERE)
BOHR = _with_super(BOHR, WAVE_COLLAPSE)
PHOEBE = _with_super(PHOEBE, COHERENT_BEAM)
ERWIN = _with_super(ERWIN, NINE_LIVES)
M_CUTIE = _with_super(M_CUTIE, DILUTION_FRIDGE)
ALICE_BOB = _with_super(ALICE_BOB, ONE_TIME_PAD)
```

- [ ] **Step 4: Their sounds**

In `src/brawl_ket/audio.py`, `build_sfx()`, after `"bsod_land": ...`, add:

```python
        # the six other supers: the lock's ping; BLOCH SPHERE's rumble and the H-gate's chime;
        # the collapse's fall; the beam's hum; the ghosts' hiss and the swipe; the fridge's crash;
        # the key's pass and the padlock's click
        "lock": tone(c("E6"), 0.08, 0.16, "triangle", decay=8),
        "bloch": mix(tone(90, 0.5, 0.22, "saw", decay=3, slide=1.4), noise_wave(0.5, 0.08, decay=3, hold=4, seed=61)),
        "h_gate": concat(tone(c("C6"), 0.05, 0.18, "square", decay=10), tone(c("G6"), 0.12, 0.18, "square", decay=8)),
        "collapse": mix(tone(1400, 0.4, 0.14, "triangle", decay=4, slide=0.2), noise_wave(0.4, 0.14, decay=5, hold=2, seed=63)),
        "beam": mix(tone(220, 1.0, 0.16, "saw", decay=1.5), tone(660, 1.0, 0.06, "sine", decay=1.5)),
        "ghosts": noise_wave(0.6, 0.12, decay=3, hold=6, seed=65),
        "swipe": mix(noise_wave(0.15, 0.25, decay=14, hold=1, seed=67), tone(900, 0.12, 0.12, "saw", decay=12, slide=0.4)),
        "fridge": mix(noise_wave(0.6, 0.3, decay=5, hold=2, seed=69), tone(55, 0.6, 0.3, "square", decay=5, slide=0.6)),
        "key_pass": tone(c("A5"), 0.06, 0.14, "pulse", decay=12),
        "padlock": concat(tone(c("G5"), 0.03, 0.2, "square", decay=30), tone(c("C5"), 0.06, 0.2, "square", decay=20)),
```

and in `EVENT_SOUNDS`, replace `"lock": None` (from Task 1) with `"lock": "lock"`, and add after
`"crash": "crash", "bsod_land": "bsod_land",`:

```python
                "bloch": "bloch", "h_gate": "h_gate", "collapse": "collapse", "beam": "beam",
                "ghosts": "ghosts", "swipe": "swipe", "fridge": "fridge", "key_pass": "key_pass",
                "padlock": "padlock",
```

(`tests/test_audio.py::test_every_moves_cue_has_a_sound` checks every cue has one.)

- [ ] **Step 5: Their names on the select screen**

In `src/brawl_ket/render.py`, extend `MOVE_LABELS` with:

```python
               "WAVEFUNCTION COLLAPSE": "WAVEFUNC. COLLAPSE",
```

- [ ] **Step 6: Run the tests**

Run: `uv run pytest -q tests/test_superpos.py tests/test_audio.py tests/test_render.py tests/test_moves.py`
Expected: PASS. If a test pins a fighter's `extra` keys (as `test_dos_stats` did), add `"super"`
to it. If a super test misses by its timing (a hitstop holding the follow-up back), lengthen
that test's `frames`, not the move.

- [ ] **Step 7: Commit**

```bash
git add src/brawl_ket/moves.py src/brawl_ket/audio.py src/brawl_ket/render.py tests/test_superpos.py tests/test_render.py tests/test_moves.py
git commit -m "feat: :sparkles: Brawl-Ket: the six other supers: BLOCH SPHERE, WAVEFUNCTION COLLAPSE, COHERENT BEAM, NINE LIVES, DILUTION FRIDGE, ONE-TIME PAD

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 3: Drawing them

The approved look is the look script; this task ports its pieces into the game, moving with
the super's frames.

**Files:**
- Create: `src/brawl_ket/superart.py`
- Modify: `src/brawl_ket/render.py` (`draw_fight`, `_fighter`, new `_super_art` and `_super_body`)
- Modify: `tools/snapshot.py` (`super_frames`)
- Test: `tests/test_render.py`

**Interfaces:**
- Consumes: the moves (Task 2); `Fighter.target_x`, `Fighter.hit_count`.
- Produces: `superart.bloch(surf, c, r, colour, up=True, spin=0.4, fill=40)`, `h_gate(surf, c, size=28)`,
  `cloud(surf, centre, sigma, colour, t=0.0, amp=26)`, `lock_ring(surf, x, colour=P.WHITE)`,
  `pillar(surf, x, colour, top=40, k=1.0)`, `flare(surf, c, r, colour)`,
  `beam(surf, x0, facing, colour, t=0, height=110, k=1.0)`, `fridge(surf, cx, bottom, s=1.2, falling=False)`,
  `shadow_mark(surf, x, w=110, locked=False, colour=...)`, `frost_wave(surf, x, reach=150)`,
  `padlock(surf, c, closed=True)`, `counter(surf, c, text)`, `star(surf, c, r, colour)`,
  `curled(colour, facing) -> pygame.Surface` (ROBERT tucked, half size).

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_render.py`:

```python


@pytest.mark.parametrize("name", ["ROBERT", "BOHR", "PHOEBE", "ERWIN", "M-CUTIE", "ALICE & BOB"])
@pytest.mark.parametrize("side", ["p1", "p2"])
def test_every_super_draws_from_its_call_to_its_end(surface, name, side):
    from brawl_ket.fighter import FighterInput
    from brawl_ket.superpos import FULL
    chars = {"p1": CHARACTERS[name], "p2": ROBERT} if side == "p1" else {"p1": ROBERT, "p2": CHARACTERS[name]}
    fight = Fight(chars, seed=1)
    fight.fighters["p1"].x, fight.fighters["p2"].x = 260.0, 340.0
    fight.meters[side].fill = {basis.Z_BASIS: FULL, basis.X_BASIS: FULL}
    r = Renderer(surface)
    r.draw_fight(fight, fight.step({side: FighterInput(a=True, b=True)}))
    seen = set()
    for _ in range(220):
        r.draw_fight(fight, fight.step({}))
        seen.add(pygame.image.tostring(surface, "RGB")[::997])
    assert len(seen) > 30                                   # it moves


def test_the_beam_is_white_hot_in_the_middle(surface):
    from brawl_ket.config import SUPER_FREEZE
    from brawl_ket.fighter import FighterInput
    from brawl_ket.moves import COHERENT_BEAM
    from brawl_ket.superpos import FULL
    fight = Fight({"p1": CHARACTERS["PHOEBE"], "p2": ROBERT}, seed=1)
    fight.fighters["p1"].x, fight.fighters["p2"].x = 150.0, 560.0
    fight.meters["p1"].fill = {basis.Z_BASIS: FULL, basis.X_BASIS: FULL}
    r = Renderer(surface)
    r.draw_fight(fight, fight.step({"p1": FighterInput(a=True, b=True)}))
    for _ in range(SUPER_FREEZE + COHERENT_BEAM.startup + 10):
        r.draw_fight(fight, fight.step({}))
    assert tuple(surface.get_at((400, FLOOR_Y - 55)))[:3] == P.WHITE


def test_the_fridge_lands_gold_on_the_locked_spot(surface):
    from brawl_ket.config import SUPER_FREEZE
    from brawl_ket.fighter import FighterInput
    from brawl_ket.moves import DILUTION_FRIDGE
    from brawl_ket.superart import GOLD_PLATE
    from brawl_ket.superpos import FULL
    fight = Fight({"p1": CHARACTERS["M-CUTIE"], "p2": ROBERT}, seed=1)
    fight.fighters["p1"].x, fight.fighters["p2"].x = 150.0, 450.0
    fight.meters["p1"].fill = {basis.Z_BASIS: FULL, basis.X_BASIS: FULL}
    r = Renderer(surface)
    r.draw_fight(fight, fight.step({"p1": FighterInput(a=True, b=True)}))
    for _ in range(SUPER_FREEZE + DILUTION_FRIDGE.startup + 2):
        r.draw_fight(fight, fight.step({}))
    area = {tuple(surface.get_at((x, y)))[:3] for x in range(380, 520, 2) for y in range(FLOOR_Y - 200, FLOOR_Y, 2)}
    assert GOLD_PLATE in area
```

- [ ] **Step 2: Run them to see them fail**

Run: `uv run pytest -q tests/test_render.py -k "every_super or white_hot or fridge_lands"`
Expected: FAIL (`ModuleNotFoundError: No module named 'brawl_ket.superart'`, and the beam test's pixel).

- [ ] **Step 3: The art**

Create `src/brawl_ket/superart.py`:

```python
"""SUPERposition: the supers' drawing (their approved look:
docs/superpowers/specs/2026-10-22-brawl-ket-superposition-looks.py, which drew these first).

Each function draws one piece at a size and phase the renderer works out from the super's
frames (render.py, _super_art and _super_body). DOS's BLUE SCREEN OF DEATH has its own in dos.py.
"""

from __future__ import annotations

import math
from functools import lru_cache

import pygame

from . import palette as P
from .config import FLOOR_Y, INTERNAL_WIDTH as W
from .fonts import load_font
from .kids import glow
from .poses import POSES

FROST = (168, 224, 248)
GOLD_PLATE = (232, 184, 72)
COAX = (176, 200, 216)


def _outlined(text: str, size: int, colour, outline=P.INK):
    font = load_font(size)
    img = font.render(text, False, colour)
    out = pygame.Surface((img.get_width() + 2, img.get_height() + 2), pygame.SRCALPHA)
    edge = font.render(text, False, outline)
    for dx, dy in ((0, 1), (2, 1), (1, 0), (1, 2)):
        out.blit(edge, (dx, dy))
    out.blit(img, (1, 1))
    return out


def _centred(surf, img, c) -> None:
    surf.blit(img, img.get_rect(center=(round(c[0]), round(c[1]))))


def star(surf, c, r, colour) -> None:
    cx, cy = c
    for width, col in ((5, P.INK), (2, colour)):
        for a in range(4):
            ang = a * math.pi / 4
            dx, dy = math.cos(ang) * r, math.sin(ang) * r
            pygame.draw.line(surf, col, (cx - dx, cy - dy), (cx + dx, cy + dy), width)
    pygame.draw.circle(surf, P.WHITE, (round(cx), round(cy)), 3)


def counter(surf, c, text) -> None:
    _centred(surf, _outlined(text, 16, P.GOLD), c)


# --- ROBERT: BLOCH SPHERE ----------------------------------------------------------------------------


def bloch(surf, c, r, colour, up=True, spin=0.4, fill=40) -> None:
    """A Bloch sphere: a glowing wireframe ball (rim, equator, a meridian turned `spin`), its z
    axis with |0> on top and |1> below (when big enough to read), and the state arrow."""
    cx, cy = round(c[0]), round(c[1])
    glow(surf, (cx, cy), r + 10, colour, 70)
    disc = pygame.Surface((2 * r + 2, 2 * r + 2), pygame.SRCALPHA)
    pygame.draw.circle(disc, (*P.lighten(colour, 0.3), fill), (r + 1, r + 1), r)
    surf.blit(disc, (cx - r - 1, cy - r - 1))
    light = P.lighten(colour, 0.55)
    eq = pygame.Rect(0, 0, 2 * r, max(6, r // 2))
    eq.center = (cx, cy)
    mer = pygame.Rect(0, 0, max(4, round(2 * r * abs(math.cos(spin)))), 2 * r)
    mer.center = (cx, cy)
    for rect in (eq, mer):
        pygame.draw.ellipse(surf, P.INK, rect.inflate(2, 2), 3)
        pygame.draw.ellipse(surf, light, rect, 1)
    pygame.draw.circle(surf, P.INK, (cx, cy), r + 1, 4)
    pygame.draw.circle(surf, light, (cx, cy), r, 2)
    for y in range(cy - r, cy + r, 6):
        pygame.draw.line(surf, P.MIST, (cx, y), (cx, min(y + 3, cy + r)), 1)
    if r >= 50:
        _centred(surf, _outlined("|0>", 8, P.WHITE if up else P.MIST), (cx, cy - r - 9))
        _centred(surf, _outlined("|1>", 8, P.MIST if up else P.WHITE), (cx, cy + r + 9))
    tip = (cx, cy - round(0.85 * r) if up else cy + round(0.85 * r))
    pygame.draw.line(surf, P.INK, (cx, cy), tip, 5)
    pygame.draw.line(surf, P.WHITE, (cx, cy), tip, 2)
    d = -1 if up else 1
    pygame.draw.polygon(surf, P.INK, [(tip[0] - 6, tip[1] - d * 7), (tip[0] + 6, tip[1] - d * 7), (tip[0], tip[1] + d * 3)])
    pygame.draw.polygon(surf, P.WHITE, [(tip[0] - 4, tip[1] - d * 6), (tip[0] + 4, tip[1] - d * 6), (tip[0], tip[1] + d)])
    pygame.draw.circle(surf, P.INK, (cx, cy), 4)
    pygame.draw.circle(surf, colour, (cx, cy), 2)


@lru_cache(maxsize=8)
def curled(colour, facing: int) -> pygame.Surface:
    """ROBERT tucked into a ball, half size, for the inside of the rolling sphere."""
    from .render import draw_puppet
    layer = pygame.Surface((160, 160), pygame.SRCALPHA)
    draw_puppet(layer, POSES["crouch"], "lean", (80, 150), facing, colour, P.CREAM, 0.0)
    return pygame.transform.scale_by(layer, 0.5)


def h_gate(surf, c, size=28) -> None:
    box = pygame.Rect(0, 0, size, size)
    box.center = (round(c[0]), round(c[1]))
    glow(surf, box.center, size, P.GOLD, 110)
    pygame.draw.rect(surf, P.INK, box.inflate(4, 4), border_radius=4)
    pygame.draw.rect(surf, P.GOLD, box, border_radius=3)
    _centred(surf, _outlined("H", 16, P.INK, outline=P.GOLD), box.center)


# --- BOHR: WAVEFUNCTION COLLAPSE ----------------------------------------------------------------------


def cloud(surf, centre, sigma, colour, t=0.0, amp=26) -> None:
    """A probability cloud on the floor: a dotted wave under a Gaussian envelope, and faint bars
    of |psi|^2 under it, motes rising."""
    bars = pygame.Surface((W, 90), pygame.SRCALPHA)
    for x in range(0, W, 6):
        env = math.exp(-((x - centre) / sigma) ** 2)
        h = round(70 * env * env)
        if h > 1:
            bars.fill((*P.lighten(colour, 0.2), 70), (x, 90 - h, 4, h))
    surf.blit(bars, (0, FLOOR_Y - 88))
    light = P.lighten(colour, 0.5)
    for x in range(0, W, 3):
        env = math.exp(-((x - centre) / sigma) ** 2)
        if env > 0.04:
            y = round(FLOOR_Y - 30 - env * amp * math.sin(x / 9 + t))
            surf.fill(P.INK, (x - 1, y - 1, 4, 4))
            surf.fill(light if (x // 3) % 2 else P.WHITE, (x, y, 2, 2))
    for k in range(14):
        x = centre + sigma * math.sin(k * 2.4) * 0.9
        y = FLOOR_Y - 40 - (k * 23 + round(t * 6)) % 90
        surf.fill(light, (round(x), y, 2, 2))


def lock_ring(surf, x, colour=P.WHITE) -> None:
    x = round(x)
    rect = pygame.Rect(0, 0, 76, 14)
    rect.center = (x, FLOOR_Y + 2)
    pygame.draw.ellipse(surf, P.INK, rect.inflate(4, 4), 4)
    pygame.draw.ellipse(surf, colour, rect, 2)
    for sx in (-1, 1):
        for sy in (-1, 1):
            cx, cy = x + sx * 46, FLOOR_Y - 60 + sy * 64
            pygame.draw.lines(surf, colour, False, [(cx, cy - sy * 12), (cx, cy), (cx - sx * 12, cy)], 2)


def pillar(surf, x, colour, top=40, k=1.0) -> None:
    """The collapse: a pillar of light on the locked spot (`k`: how much of it is left), dots
    sucked inward, a ring on the floor."""
    x = round(x)
    glow(surf, (x, FLOOR_Y - 40), 70, colour, round(90 * k))
    for w, a, c in ((70, 110, colour), (46, 170, P.lighten(colour, 0.4)), (18, 240, P.WHITE)):
        w = max(2, round(w * k))
        col = pygame.Surface((w, FLOOR_Y - top), pygame.SRCALPHA)
        col.fill((*c, a))
        surf.blit(col, (x - w // 2, top))
    for sx in (-1, 1):
        edge = x + sx * round(35 * k)
        pygame.draw.line(surf, P.INK, (edge, top), (edge, FLOOR_Y), 2)
    for n in range(10):
        ang = n * math.tau / 10
        a = (x + math.cos(ang) * 110 * k, FLOOR_Y - 90 + math.sin(ang) * 66 * k)
        b = (x + math.cos(ang) * 44 * k, FLOOR_Y - 90 + math.sin(ang) * 26 * k)
        pygame.draw.line(surf, P.lighten(colour, 0.5), a, b, 1)
        pygame.draw.circle(surf, P.WHITE, (round(a[0]), round(a[1])), 2)
    rect = pygame.Rect(0, 0, 96, 16)
    rect.center = (x, FLOOR_Y + 2)
    pygame.draw.ellipse(surf, P.WHITE, rect, 3)


# --- PHOEBE: COHERENT BEAM ----------------------------------------------------------------------------


def flare(surf, c, r, colour) -> None:
    glow(surf, c, r, colour, 150)
    glow(surf, c, max(2, r // 2), P.WHITE, 200)
    cx, cy = c
    for ang, ln in ((0, r * 2), (math.pi / 2, r), (math.pi / 4, r * 0.7), (-math.pi / 4, r * 0.7)):
        dx, dy = math.cos(ang) * ln, math.sin(ang) * ln
        pygame.draw.line(surf, P.WHITE, (cx - dx, cy - dy), (cx + dx, cy + dy), 1)


def beam(surf, x0, facing, colour, t=0, height=110, k=1.0) -> None:
    """COHERENT BEAM from x0 to the screen's edge the way she faces, floor to `height` px up (`k`
    of it while it narrows): colour edges, a lighter body, a white core, interference fringes."""
    x0 = round(x0)
    left, w = (x0, W - x0) if facing > 0 else (0, x0)
    if w <= 0:
        return
    full = max(2, round(height * k))
    for inset, a, c in ((0, 150, colour), (10, 190, P.lighten(colour, 0.35)), (34, 240, P.WHITE)):
        h = round((height - 2 * inset) * k)
        if h <= 0:
            continue
        band = pygame.Surface((w, h), pygame.SRCALPHA)
        band.fill((*c, a))
        surf.blit(band, (left, FLOOR_Y - full + round(inset * k)))
    fringe = pygame.Surface((w, full), pygame.SRCALPHA)
    for x in range(-14, w, 14):
        fringe.fill((*P.INK, 40), (x + (t * facing) % 14, 0, 6, full))
    surf.blit(fringe, (left, FLOOR_Y - full))
    pygame.draw.line(surf, P.INK, (left, FLOOR_Y - full - 1), (left + w, FLOOR_Y - full - 1), 2)


# --- M-CUTIE: DILUTION FRIDGE -------------------------------------------------------------------------


def fridge(surf, cx, bottom, s=1.2, falling=False) -> None:
    """The dilution refrigerator (the cryo stage's chandelier made a weapon, bigger and glowing
    with frost so it never reads as the stage's own), its mixing chamber's bottom at `bottom`."""
    cx, bottom = round(cx), round(bottom)
    glow(surf, (cx, bottom - round(90 * s)), round(150 * s), FROST, 70)
    if falling:
        for dx in range(-round(100 * s), round(100 * s) + 1, round(28 * s)):
            top = bottom - round(260 * s)
            pygame.draw.line(surf, P.INK, (cx + dx, top - 60), (cx + dx, top), 4)
            pygame.draw.line(surf, P.WHITE, (cx + dx, top - 60), (cx + dx, top), 2)
    plates = [(bottom + round(dy * s) - 30, round(w * s)) for dy, w in
              ((-150, 200), (-115, 164), (-82, 132), (-52, 104), (-26, 80))]
    for (y0, w0), (y1, w1) in zip(plates, plates[1:]):
        for side in (-1, 1):
            a, b = (cx + side * (w0 // 2 - 10), y0), (cx + side * (w1 // 2 - 8), y1)
            pygame.draw.line(surf, P.INK, a, b, 5)
            pygame.draw.line(surf, P.shade(GOLD_PLATE, 0.85), a, b, 3)
        for k in range(-3, 4):
            a, b = (cx + k * (w0 // 8), y0 + 4), (cx + k * (w1 // 8), y1)
            pygame.draw.line(surf, P.INK, a, b, 3)
            pygame.draw.line(surf, COAX, a, b, 1)
    pygame.draw.line(surf, P.INK, (cx, plates[0][0]), (cx, -10), 7)
    pygame.draw.line(surf, P.MIST, (cx, plates[0][0]), (cx, -10), 3)
    for y, w in plates:
        plate = pygame.Rect(cx - w // 2, y, w, 10)
        pygame.draw.rect(surf, P.INK, plate.inflate(4, 4), border_radius=4)
        pygame.draw.rect(surf, GOLD_PLATE, plate, border_radius=3)
        surf.fill(P.lighten(GOLD_PLATE, 0.5), (plate.x + 4, plate.y + 1, plate.w - 8, 2))
    chamber = pygame.Rect(cx - round(18 * s), bottom - round(26 * s), round(36 * s), round(26 * s))
    pygame.draw.rect(surf, P.INK, chamber.inflate(4, 4), border_radius=4)
    pygame.draw.rect(surf, P.shade(GOLD_PLATE, 0.9), chamber, border_radius=3)
    for k in range(8):
        surf.fill(FROST, (cx - 90 + (k * 37) % 180, plates[k % 5][0] + 12, 3, 2))


def shadow_mark(surf, x, w=110, locked=False, colour=(160, 88, 232)) -> None:
    """The fridge's shadow: a dark disc, ringed dashed in her colour while it follows, solid
    white once it locks."""
    rect = pygame.Rect(0, 0, w, 18)
    rect.center = (round(x), FLOOR_Y + 2)
    sh = pygame.Surface(rect.size, pygame.SRCALPHA)
    pygame.draw.ellipse(sh, (*P.INK, 190), sh.get_rect())
    surf.blit(sh, rect)
    ring = rect.inflate(8, 6)
    if locked:
        pygame.draw.ellipse(surf, P.INK, ring.inflate(4, 4), 4)
        pygame.draw.ellipse(surf, P.WHITE, ring, 2)
        return
    for k in range(16):
        a0 = k * math.tau / 16
        pygame.draw.arc(surf, P.lighten(colour, 0.3), ring, a0, a0 + math.tau / 32, 3)


def frost_wave(surf, x, reach=150, k=1.0) -> None:
    """The frosty shockwave either side of the fridge: ice spikes along the floor (`k`: how far
    out it has rolled) and snow."""
    x = round(x)
    for side in (-1, 1):
        for n in range(9):
            sx = x + side * (30 + n * reach / 9 * k)
            h = 26 - n * 2
            pygame.draw.polygon(surf, P.INK, [(sx - 5, FLOOR_Y), (sx, FLOOR_Y - h), (sx + 5, FLOOR_Y)])
            pygame.draw.polygon(surf, FROST, [(sx - 3, FLOOR_Y - 1), (sx, FLOOR_Y - h + 3), (sx + 3, FLOOR_Y - 1)])
    for n in range(18):
        surf.fill(P.WHITE, (x - reach + (n * 53) % (2 * reach), FLOOR_Y - 20 - (n * 29) % 90, 2, 2))


# --- ALICE & BOB: ONE-TIME PAD ------------------------------------------------------------------------


def padlock(surf, c, closed=True) -> None:
    cx, cy = round(c[0]), round(c[1])
    shackle = pygame.Rect(0, 0, 44, 52)
    shackle.midbottom = (cx, cy - 4 if closed else cy - 24)
    pygame.draw.arc(surf, P.INK, shackle.inflate(8, 8), 0, math.pi, 12)
    pygame.draw.arc(surf, P.MIST, shackle, 0, math.pi, 6)
    for sx in (shackle.left + 3, shackle.right - 3):
        pygame.draw.line(surf, P.INK, (sx, shackle.centery), (sx, cy + 4), 10)
        pygame.draw.line(surf, P.MIST, (sx, shackle.centery), (sx, cy + 4), 5)
    body = pygame.Rect(0, 0, 70, 54)
    body.midtop = (cx, cy)
    glow(surf, body.center, 50, P.GOLD, 120)
    pygame.draw.rect(surf, P.INK, body.inflate(6, 6), border_radius=8)
    pygame.draw.rect(surf, P.GOLD, body, border_radius=6)
    surf.fill(P.lighten(P.GOLD, 0.5), (body.x + 6, body.y + 4, body.w - 12, 3))
    pygame.draw.circle(surf, P.INK, (cx, body.y + 22), 7)
    pygame.draw.rect(surf, P.INK, (cx - 3, body.y + 24, 6, 16))
```

(Check `draw_puppet`'s signature in render.py before using it in `curled`: it is
`draw_puppet(surf, pose, build, feet, facing, body, accent, flare, ...)`; pass what it needs.)

- [ ] **Step 4: The renderer calls it**

In `src/brawl_ket/render.py`:

Add the import after the `from .kids import (...)` block:

```python
from . import superart as SA
```

In `draw_fight`, after `for s in fight.shots: self._shot(s, ox, oy)` (the shots' loop), add:

```python
        self._super_art(fight, ox, oy)
```

At the top of `_fighter`, after the `if f.boxed:` block (its `return`), add:

```python
        if f.action == "attack" and f.move is not None and f.move.kind == "super":
            drawn = self._super_body(f, body, ox, oy)
            if drawn is not None:
                return drawn
```

Add the two methods after `_frozen_or`:

```python
    def _super_body(self, f: Fighter, body, ox: int, oy: int):
        """A super that replaces the fighter's own drawing: ROBERT rolling inside his Bloch
        sphere, ERWIN in his box while his ghosts pounce. None: draw them as ever."""
        m = f.move
        if m.name == "BLOCH SPHERE" and f.phase == "active":
            c = (f.x + ox, FLOOR_Y - 36 + oy)
            curl = SA.curled(body, f.facing)
            self.surface.blit(curl, curl.get_rect(center=(round(c[0]), round(c[1]) + 4)))
            SA.bloch(self.surface, c, 36, body, up=True, spin=(f.frame - f.startup) * 0.35, fill=70)
            return f.x, FLOOR_Y - 72.0
        if m.name == "NINE LIVES" and m.hits and f.phase in ("startup", "active"):
            erwin_box(self.surface, round(f.x) + ox, 70, 48, f.facing, body, FLOOR_Y + oy)
            return f.x, FLOOR_Y - 60.0
        return None

    def _super_art(self, fight: Fight, ox: int, oy: int) -> None:
        """Each super's art over the fight, by its frames: the sphere forming and the H gate; the
        cloud, the lock and the pillar; the flare and the beam; the ghosts and the claws; the
        shadow, the falling fridge and the frost; the key's passes and the padlock."""
        surf = self.surface
        for key, f in fight.fighters.items():
            m = f.move
            if f.action != "attack" or m is None or m.kind != "super":
                continue
            colour = BASIS_BODY[f.basis]
            into = f.frame - f.startup                  # frames into the active ones (< 0: startup)
            target = None if f.target_x is None else f.target_x + ox
            rival = fight.fighters["p2" if key == "p1" else "p1"]
            if m.name == "BLOCH SPHERE" and f.phase == "startup":
                k = (f.frame + 1) / f.startup
                SA.bloch(surf, (f.x + ox, FLOOR_Y - 66 + oy), round(20 + 52 * k), colour, spin=0.9, fill=34)
            elif m.name == "H-GATE UPPERCUT" and f.frame < 18:
                SA.h_gate(surf, (f.x + ox + f.facing * 12, FLOOR_Y - f.y - 190 + oy))
                SA.bloch(surf, (f.x + ox - f.facing * 80, FLOOR_Y - 190 + oy), 52, colour, up=False, spin=1.2, fill=30)
            elif m.name == "WAVEFUNCTION COLLAPSE":
                if f.phase == "startup" and target is None:
                    SA.cloud(surf, f.x + ox + f.facing * 160, 260, colour, t=self.t / 4, amp=22)
                elif f.phase == "startup":
                    left = (f.startup - f.frame) / m.lock
                    SA.cloud(surf, target, 40 + 160 * left, colour, t=self.t / 4, amp=34)
                    SA.lock_ring(surf, target)
                elif target is not None and into < m.active + 14:
                    SA.pillar(surf, target, colour, k=max(0.2, 1 - max(0, into - m.active) / 14))
            elif m.name == "COHERENT BEAM":
                hands = (f.x + ox + f.facing * 50, FLOOR_Y - 92 + oy)
                if f.phase == "startup":
                    SA.flare(surf, hands, round(8 + 22 * (f.frame + 1) / f.startup), colour)
                elif f.phase == "active":
                    fade = min(1.0, (m.active - into) / 10)
                    SA.beam(surf, hands[0], f.facing, colour, t=self.t, k=max(0.25, fade))
                    SA.flare(surf, hands, 34, colour)
            elif m.name == "NINE LIVES" and m.hits:
                if f.phase == "active" and target is not None:
                    side = 1 if (into // m.hit_every) % 2 else -1
                    gx = target + side * (70 - (into % m.hit_every) * 6)
                    self._ghost(gx, -side, colour)
                    SA.counter(surf, (target, FLOOR_Y - 180 + oy), f"{min(f.hit_count + 1, 8)}/9")
            elif m.name == "NINE LIVES":
                if f.frame < 14 and target is not None:
                    for n in range(3):
                        a = (target - 4 + 14 * n, FLOOR_Y - 150 + oy)
                        b = (target + 40 + 14 * n, FLOOR_Y - 40 + oy)
                        pygame.draw.line(surf, P.INK, a, b, 6)
                        pygame.draw.line(surf, P.WHITE, a, b, 3)
                    SA.counter(surf, (target, FLOOR_Y - 190 + oy), "9/9")
            elif m.name == "DILUTION FRIDGE" and m.follow is not None:
                if f.phase == "startup" and target is None:
                    SA.shadow_mark(surf, rival.x + ox, colour=colour)
                elif f.phase == "startup":
                    SA.shadow_mark(surf, target, w=130, locked=True)
                    k = 1 - (f.startup - f.frame) / m.lock
                    SA.fridge(surf, target, -40 + (FLOOR_Y + 46) * k + oy, falling=True)
                elif target is not None:
                    SA.fridge(surf, target, FLOOR_Y + 6 + oy)
            elif m.name == "DILUTION FRIDGE" and target is not None:
                SA.fridge(surf, target, FLOOR_Y + 6 + oy)
                SA.frost_wave(surf, target, k=min(1.0, (f.frame + 1) / 6))
            elif m.name == "ONE-TIME PAD" and m.hits and f.phase == "active" and target is not None:
                bob = fight.echoes[key]
                a, b = (f.x, bob.x) if (into // m.hit_every) % 2 == 0 else (bob.x, f.x)
                k = (into % m.hit_every) / m.hit_every
                kx = a + (b - a) * k + ox
                for x in range(round(min(a, b)) + ox + 20, round(max(a, b)) + ox - 20, 8):
                    surf.fill(P.INK, (x - 1, FLOOR_Y - 77 + oy, 5, 4))
                    surf.fill(P.GOLD, (x, FLOOR_Y - 76 + oy, 3, 2))
                key_img = key_sprite(colour, True, 1 if b > a else -1)
                surf.blit(key_img, key_img.get_rect(center=(round(kx), FLOOR_Y - 76 + oy)))
                SA.counter(surf, (target, FLOOR_Y - 180 + oy), f"{min(f.hit_count + 1, 6)}/6")
            elif m.name == "ONE-TIME PAD" and target is not None:
                SA.padlock(surf, (target, FLOOR_Y - 120 + oy), closed=f.frame >= 3)
                if f.frame < 16:
                    blit_center(surf, outlined("CLICK!", 16, P.WHITE, thick=2), (target + 70, FLOOR_Y - 190 + oy))

    def _ghost(self, x: float, facing: int, colour) -> None:
        """One of NINE LIVES' ghost ERWINs, pouncing: see-through and pale."""
        layer = self._ghost_layer
        layer.fill((0, 0, 0, 0))
        draw_puppet(layer, POSES["pounce"], "cat", (160, 300), facing, P.lighten(colour, 0.45),
                    ACCENT.get("ERWIN", P.CREAM), 0.0)
        layer.set_alpha(150)
        self.surface.blit(layer, (round(x) - 160, FLOOR_Y - 300))
```

In `_reset`, add `self._ghost_layer = pygame.Surface((320, 320), pygame.SRCALPHA)`.
Import `box as erwin_box` from `.erwin` (extend its import list) and `key_sprite` from `.kids`
(it is already imported there with `tossed_key`; add it if missing).

- [ ] **Step 5: Snapshots**

In `tools/snapshot.py`, at the end of `super_frames`, add:

```python
    # the six others, each in the middle of its move
    for name, fname, frames in (("ROBERT", "bloch", 12), ("BOHR", "collapse", 34), ("PHOEBE", "beam", 30),
                                ("ERWIN", "nine", 30), ("M-CUTIE", "fridge", 38), ("ALICE & BOB", "otp", 30)):
        fight = Fight({"p1": CHARACTERS[name], "p2": ROBERT}, seed=1)
        fight.fighters["p1"].x, fight.fighters["p2"].x = 220.0, 300.0
        fight.meters["p1"].fill = {basis.Z_BASIS: FULL, basis.X_BASIS: FULL}
        r = Renderer(surface)
        r.draw_fight(fight, fight.step({"p1": FighterInput(a=True, b=True)}), {"p1": 0, "p2": 0})
        for _ in range(SUPER_FREEZE + frames):
            r.draw_fight(fight, fight.step({}), {"p1": 0, "p2": 0})
        save(surface, out_dir, f"super_{fname}.png")
```

(import `CHARACTERS` from `brawl_ket.moves` inside the function) and list the six files in the
module docstring after the BSOD ones: `super_bloch.png, super_collapse.png, super_beam.png,
super_nine.png, super_fridge.png, super_otp.png: each of the six others mid-move;`.

- [ ] **Step 6: Run the tests, and look**

Run: `uv run pytest -q tests/test_render.py`
Expected: PASS.

Run the snapshot tool and open the six new `super_*.png` beside the look sheets
(`uv run python ../docs/superpowers/specs/2026-10-22-brawl-ket-superposition-looks.py /tmp/looks`):
each must read as its sheet does. Fix what doesn't (positions, sizes) in render.py/superart.py.

- [ ] **Step 7: Commit**

```bash
git add src/brawl_ket/superart.py src/brawl_ket/render.py tools/snapshot.py tests/test_render.py
git commit -m "feat: :lipstick: Brawl-Ket: the six supers drawn, as their approved look sheets

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 4: The CPU, balance, the benchmark, the README

**Files:**
- Modify: `src/brawl_ket/bot.py` (`SUPER_REACH`, `_super`, `_dodge_super`, `input`)
- Modify: `tools/benchmark.py` (every super)
- Modify: `tests/test_bot.py`, `tests/test_balance.py`, `README.md`

**Interfaces:**
- Consumes: the supers (Task 2), `Fighter.target_x`.
- Produces: `bot.SUPER_REACH: dict[str, int]`; `Bot._dodge_super(me, rival, toward, dist) -> FighterInput | None`.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_bot.py`:

```python


@pytest.mark.parametrize("name,gap", [("ROBERT", 150.0), ("BOHR", 400.0), ("PHOEBE", 300.0),
                                      ("ERWIN", 120.0), ("M-CUTIE", 400.0), ("ALICE & BOB", 80.0)])
def test_every_bot_fires_its_super_when_it_will_land(name, gap):
    from brawl_ket import basis
    from brawl_ket.moves import CHARACTERS
    from brawl_ket.superpos import FULL
    fight = Fight({"p1": CHARACTERS[name], "p2": ROBERT}, seed=1)
    fight.fighters["p1"].x, fight.fighters["p2"].x = 150.0, 150.0 + gap
    fight.meters["p1"].fill = {basis.Z_BASIS: FULL, basis.X_BASIS: FULL}
    inp = Bot("p1", 1).input(fight)
    assert inp.a and inp.b


def test_a_bot_walks_off_a_locked_ring(monkeypatch):
    import brawl_ket.bot as bot_module
    from brawl_ket.moves import CHARACTERS, WAVE_COLLAPSE
    monkeypatch.setattr(bot_module, "SUPER_DODGE_ODDS", 1.0)
    fight = Fight({"p1": ROBERT, "p2": CHARACTERS["BOHR"]}, seed=1)
    fight.fighters["p1"].x, fight.fighters["p2"].x = 300.0, 500.0
    bohr = fight.fighters["p2"]
    bohr.action, bohr.move, bohr.slot, bohr.frame = "attack", WAVE_COLLAPSE, "super", 30
    bohr.target_x = 300.0
    inp = Bot("p1", 1).input(fight)
    assert inp.dx != 0 and not inp.up
```

(`pytest` and `ROBERT`, `Fight`, `Bot` are imported at the top of `tests/test_bot.py`; check.)

- [ ] **Step 2: Run them to see them fail**

Run: `uv run pytest -q tests/test_bot.py -k "fires_its_super or locked_ring"`
Expected: FAIL.

- [ ] **Step 3: The CPU**

In `src/brawl_ket/bot.py`, after `LOPSIDED_FEINT = 0.06`, add:

```python
# ... and where each super lands: the rival on the ground within this many px
SUPER_REACH = {"BLUE SCREEN OF DEATH": CRASH_REACH - 20, "BLOCH SPHERE": 260, "WAVEFUNCTION COLLAPSE": 2000,
               "COHERENT BEAM": 520, "NINE LIVES": 150, "DILUTION FRIDGE": 2000, "ONE-TIME PAD": 90}
```

Replace `_super`'s body after the first `if ... return False` guard:

```python
        if move.crash is not None:      # BLUE SCREEN OF DEATH: a rival on the ground in reach
            return rival.y == 0 and dist <= CRASH_REACH - 20 and not rival.boxed and not rival.intangible
        return False
```

with:

```python
        return rival.y == 0 and dist <= SUPER_REACH.get(move.name, 0) and not rival.boxed \
            and not rival.intangible and rival.action != "knockdown"
```

Replace `_dodge_super` with:

```python
    def _dodge_super(self, me, rival, toward: int, dist: float) -> FighterInput | None:
        """Get out of a rival's super, the way each one is dodged (a chance a frame): jump away from
        a BLUE SCREEN winding up, jump the BLOCH SPHERE rolling in and the COHERENT BEAM as it
        fires, walk off a WAVEFUNCTION COLLAPSE's or DILUTION FRIDGE's locked ring, back off from
        NINE LIVES and ONE-TIME PAD winding up."""
        m = rival.move
        if rival.action != "attack" or m is None or m.kind != "super" or me.action not in ("idle", "walk", "crouch") \
                or self.rng.random() >= SUPER_DODGE_ODDS:
            return None
        if m.crash is not None and rival.phase == "startup" and dist <= CRASH_REACH + 10:
            return FighterInput(up=True, dx=-toward)
        if m.name == "BLOCH SPHERE" and rival.phase == "active" and dist <= 120:
            return FighterInput(up=True)
        if m.name == "COHERENT BEAM" and rival.phase == "startup" and rival.frame >= rival.startup - 3:
            return FighterInput(up=True)
        if m.remote and m.lock > 0 and rival.target_x is not None and rival.phase == "startup" \
                and abs(me.x - rival.target_x) < 70:
            return FighterInput(dx=1 if me.x >= rival.target_x else -1)
        if m.lock_range and rival.phase == "startup" and dist <= m.lock_range + 20:
            return FighterInput(dx=-toward)
        return None
```

and in `input`, replace:

```python
        if self._dodge_super(me, rival, dist):
            return FighterInput(up=True, dx=-toward)
```

with:

```python
        dodge = self._dodge_super(me, rival, toward, dist)
        if dodge is not None:
            return dodge
```

- [ ] **Step 4: The benchmark**

In `tools/benchmark.py`, replace the `# SUPERposition: DOS's BLUE SCREEN OF DEATH over and over`
block with one that does that for every fighter (each against ROBERT, bars refilled every frame):

```python
    # SUPERposition: every fighter's super over and over (their bar refilled every frame)
    from brawl_ket.basis import X_BASIS, Z_BASIS
    from brawl_ket.superpos import FULL
    for c in chars:
        fight, times = None, []
        for i in range(FRAMES // 3):
            if fight is None or fight.over:
                fight = Fight({"p1": c, "p2": CHARACTERS["ROBERT"]})
                bots = {p: Bot(p, i + k) for k, p in enumerate(PLAYERS)}
            fight.meters["p1"].fill = {Z_BASIS: FULL, X_BASIS: FULL}
            t = time.perf_counter()
            events = fight.step({p: b.input(fight) for p, b in bots.items()})
            renderer.draw_fight(fight, events, {"p1": 0, "p2": 0})
            times.append(time.perf_counter() - t)
        report(f"{c.name} supers", times[60:])
```

- [ ] **Step 5: The whole check, balance and the README**

Run all the Global Constraints' checks. Every benchmark line under 2 ms mean.

Balance: compare with part 1's 100-round table (in its Task 6 report). Record every pairing
`tests/test_balance.py` now fails in `OVER_THE_BAR`, with its measured share, as "SUPERposition,
all seven supers, over 200 rounds", and remove entries that now pass the bar by a margin (an
xpass at 200 rounds too). Do not tune the supers to pass it.

README: in `brawl-ket/README.md`'s SUPERposition paragraph, replace `So far DOS has his, BLUE SCREEN
OF DEATH: everyone on the ground near him freezes under an error window, and he comes down on them (25).`
with:

```markdown
Each fighter's super, and how to get out of it:

| Fighter | Super | Dodge |
|---|---|---|
| ROBERT | BLOCH SPHERE: rolls in inside a Bloch sphere (4 hits), then an H-gate uppercut flips him to the other colour | jump the sphere |
| BOHR | WAVEFUNCTION COLLAPSE: a probability cloud locks onto you, and a pillar of light falls there | move after the lock |
| PHOEBE | COHERENT BEAM: a laser to the screen's edge, floor to 110 px (5 hits) | be above it |
| ERWIN | NINE LIVES: nine ERWINs pounce from both sides (8 ghosts, low), the ninth real | partly: jump in time |
| DOS | BLUE SCREEN OF DEATH: everyone on the ground near him freezes under an error window; he comes down on them | be in the air, or far |
| M-CUTIE | DILUTION FRIDGE: a shadow locks onto you; a giant gold dilution fridge falls there, then frost either side | leave the shadow, jump the frost |
| ALICE & BOB | ONE-TIME PAD: they re-form either side of you, pass the key through you six times, and a padlock snaps shut | stay out of reach, or jump |
```

- [ ] **Step 6: Commit**

```bash
git add src/brawl_ket/bot.py tools/benchmark.py tests/test_bot.py tests/test_balance.py README.md
git commit -m "feat: :robot: Brawl-Ket: the CPU fires and dodges every super; balance and the README

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

## Done means

- All checks pass (the balance test's xfails aside); every benchmark line under 2 ms mean.
- In a round, every fighter's A+B with a full bar fires their super, drawn as its look sheet,
  doing 25 in all to a rival who doesn't dodge and nothing to one who dodges it the spec's way.
- Then deploy (`./deploy_batocera.sh root@10.42.0.100`, md5-verified) for the user's playtest.
