# Brawl-Ket: ERWIN and DOS Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add the fourth and fifth fighters, ERWIN (Schrodinger's cat, THE BOX) and DOS (a
classical computer, always green, COPY / PASTE), to Brawl-Ket as specified in
`docs/superpowers/specs/2026-10-21-brawl-ket-erwin-dos-design.md`, drawn as the approved
looks `docs/superpowers/specs/2026-10-21-brawl-ket-erwin-look.py` and
`docs/superpowers/specs/2026-10-21-brawl-ket-dos-look.py`.

**Architecture:**
- **Rules first, pure and tested:** `moves.py` gets the two characters and a few new `Move` /
  `Character` fields; `fighter.py` gets THE BOX's superposed state, POUNCE's leap and DOS's
  COPY / PASTE; `fight.py` gets a seeded `random.Random` (the spec's one change to its
  purity), the box measurement, the COPY catch and PASTE's level shot.
- **Drawing in two new modules,** because `render.py` is already 1,417 lines: `erwin.py`
  (the cat and THE BOX) and `dos.py` (the case, the screen faces, the floppy, the clipboard
  icon). The shared drawing primitives move from `render.py` to a small `ink.py` so the new
  modules can use them without a circular import; `render.py` re-exports them, so the look
  scripts and tests that import `render._pt`, `render.limb`, ... keep working.
- **Each fighter's art is checked pixel for pixel against its approved look script,** whose
  `draw_erwin` / `draw_dos` / `floppy_sprite` the tests import and run side by side with the
  game's.
- **Expensive art is drawn once and cached** (the holographic boxes, the screen faces, the
  turning disk), because the look scripts' per-pixel loops would blow the Pi's frame budget.

**Tech Stack:** Python 3.11, pygame 2.5.2, uv, pytest, ruff 0.15.22. All commands run from
`brawl-ket/`.

## Global Constraints

- `requires-python = ">=3.11,<3.12"`; `pygame==2.5.2` exactly. No new dependencies.
- LF line endings in every file (`file <path>` must not say CRLF).
- The simulation counts integer frames at 60 Hz; seconds appear only through `config.frames()`.
- On-screen text is ASCII capitals (Press Start 2P has no Unicode minus, no kets).
- Nothing else in the v3 rules changes: colour must match to hurt; A is your colour and B the
  other; throws are Y and hurt either colour; every special is in your own colour. The only
  exception is DOS's Y and his fixed basis.
- ERWIN: health 90 (the lowest), walk 2.3, the highest jump (`jump_vy` about 12.5); normals,
  throws and Y shared with everyone.
- THE BOX (X, her colour, 3 s cooldown): box 1 where she stood, box 2 120 px towards the
  rival, clamped to the stage; no body while superposed; she collapses herself with any new
  stick direction or button press after the move's startup, or after 1.5 s at the latest,
  into a random box, 50/50, popping out with a quick swipe (MID, 8 damage, her colour, short
  range); anything that would hit her and touches either box is a 50/50 measurement; the
  cooldown runs from the collapse; Y still works while superposed.
- POUNCE (Down + X, her colour, 2 s cooldown): a long low leap, MID, 10 damage, knockdown,
  about 20 frames of landing recovery.
- SCRATCH (Air X, her colour, once per jump): hangs in the air, three claws, `hit_every`,
  4 damage each, MID, then falls on.
- DOS: health 125 (the most), walk 1.6, the lowest jump (`jump_vy` about 10.0), always Z
  (green): Y never switches, MEASURE hurts but doesn't collapse him, badge always `0/1`.
- COPY / PASTE (Y): a COPY catch window of about 0.2 s; a missed COPY about 0.3 s of
  recovery; a caught shot goes into a one-item clipboard; PASTE fires it straight ahead at its
  own speed in the absolute basis it was fired in; both only when he is free to act (not in
  hitstun or knocked down); the clipboard is emptied at the start of each round.
- FLOPPY (X, his colour, 2.5 s cooldown): 9 damage, about 3 px a frame (PHOTON flies at 4).
- BLUE SCREEN (Down + X, his colour, 3 s cooldown): about 50 px around him, MID, 6 damage,
  a long stun of about 0.6 s, pushes the rival away.
- CRT DROP (Air X, his colour, once per jump): straight down, MID, 12 damage, knockdown, no
  shockwave, about 20 frames of landing recovery.
- Randomness: a `Fight` takes a `seed` (default 0) and owns a `random.Random(seed)`; `Match`
  passes a seed from its own rng; the tests fix it.
- CHOOSE YOUR FIGHTER order: ROBERT, BOHR, PHOEBE, ERWIN, DOS.
- Balance: bot against bot, no fighter wins more than about 60% against another.
- Cabinet conventions (`../AGENTS.md`): A = raw 1, B = 2, X = 0, Y = 3, Start = 9,
  Select = 8; P1 blue ring, P2 red ring. Brawl-Ket ran at about 3-4 ms a frame on the
  cabinet; the new art must stay within the Pi's frame budget.
- **Done means, for every task:** `uv run pytest -q` passes, and
  `uvx --from 'ruff==0.15.22' ruff check src tests tools` is clean.
- **Commits:** on a feature branch (`git switch -c brawl-ket-erwin-dos` before Task 1, never
  on `main`), gitmoji style (`feat: :sparkles: Brawl-Ket: ...`), staging explicit paths only,
  each message ending with `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.

## Decisions this plan takes where the spec says "about"

| Spec | Plan value | Why |
|---|---|---|
| ERWIN `jump_vy` about 12.5 | 12.5, gravity 0.5 | apex 156 px, above ROBERT's 144 |
| DOS `jump_vy` about 10.0 | 10.0, gravity 0.55 | apex 91 px, below BOHR's 100 |
| ERWIN's normals "shared, as on the others" | ROBERT's seven normal `Move`s, the same objects | she is ROBERT's height; the cat skeleton puts her fists and feet within 10 px of ROBERT's boxes (checked by `test_the_striking_limb_reaches_the_hitbox_on_impact`) |
| DOS's normals | BOHR's frame numbers, except his jabs start in 8 frames (BOHR 6): startups 8 / 13 / 9; new boxes fitted to his arms | he is the slow one; with BOHR's 6-frame jabs, a prototype of this plan had DOS winning 85% of bot rounds against ROBERT (health 125 does a lot), with 8 they are even. His fists come out of the case's sides, lower and further forward than BOHR's |
| ERWIN's hurtboxes | ROBERT's: stand `Box(-14, 0, 28, 120)`, crouch `Box(-16, 0, 32, 100)` | same height; the crouch box reaches her drawn head (98 px) |
| DOS's hurtboxes | stand `Box(-24, 0, 48, 140)`, crouch `Box(-26, 0, 52, 112)` | the case is 54 px wide and its top 144 px up (crouched: 113); 140 stays under LIGHT PILLAR's 150 |
| THE BOX frames | startup 8 (ducking in, hittable), active 1, recovery 4; then the `"boxed"` state | the split happens on its first active frame, so the recovery never plays; 4 (not 1) keeps it clear of the last-frames blend `test_recovery_eases_out_of_the_strike` checks |
| a box's hurtbox | `BOX_HURT = Box(-36, 0, 72, 86)` around each box's x | the drawn box (70 wide, 48 tall) plus her ears over its rim (86 px); every standing normal, PHOTON and FLOPPY touch it |
| the swipe | `BOX SWIPE`: startup 3, active 4, recovery 14, `Box(14, 50, 46, 36)`, hitstun 16, knockback 2.5 | short range: 60 px ahead, about a jab's |
| POUNCE | startup 8, active 30, recovery 20, leap `(6.0, 7.0)`, `Box(10, 10, 70, 44)`, hitstun 20, knockback 4.0 | a 28-frame arc, 168 px long and 49 px high; the active frames outlast the arc, so it always lands into its 20 recovery frames |
| SCRATCH | startup 4, active 24, recovery 8, `hit_every=8`, `Box(12, 40, 46, 36)`, hitstun 10, knockback 1.0 | hits on active frames 0, 8 and 16 only: exactly three; hitstun 10 holds the rival for the next claw |
| COPY | startup 2, active 12 (0.2 s), recovery 18 (0.3 s), catch window `Box(14, 20, 40, 110)`; a catch cuts the recovery to `COPY_CAUGHT_RECOVERY = 6` | "about 0.2 s" and "about 0.3 s"; a catch is rewarded |
| PASTE | startup 6, active 1, recovery 12 | "short startup and recovery" |
| FLOPPY | startup 14, active 1, recovery 22, `Projectile(3.0, Box(0, 80, 18, 18), 240)`, HIGH, hitstun 18, knockback 3.0 | PHOTON's shape; 240 frames cross the whole stage; HIGH like PHOTON, so a crouch ducks it |
| the drive slot | `DRIVE_SLOT_Y = 80`: FLOPPY's box and every pasted shot's box start 80 px above his feet | the drawn slot is at about 90 px; 80 keeps a shot low enough to touch a box (86) |
| BLUE SCREEN | startup 10, active 6, recovery 24, `Box(-74, 0, 148, 110)`, hitstun 36 (0.6 s), knockback 5.0, `push_out` | "about 50 px around him": 50 px past each side of his 48 px case; 110 tall, so someone high in a jump clears it |
| CRT DROP | startup 4, active 60, recovery 20, `dive=(0.0, 14.0)`, `Box(-24, 0, 48, 40)`, hitstun 20, knockback 3.0 | straight down and faster than COLLAPSE (9) or the DIVE (13) |

Three more choices, flagged in the final report:
- **PHOEBE's TUNNEL past DOS:** her re-form point is `max(TUNNEL_PAST, body_width)` past the
  rival. DOS's case makes the push box between them 54 px, more than `TUNNEL_PAST` (50), so
  without this she could never tunnel past him. Nothing changes for the other pairings
  (their push boxes are 44-52 px).
- **The title's two fighters:** ROBERT and the last fighter who can switch (ERWIN, purple),
  not `ROSTER[-1]` (DOS, who can't be purple), so the title still shows both colours.
- **The real box after a collapse has no head over its rim.** The look's collapse row shows the
  cardboard box with her ears and eyes peeking out, because no cat stood there; in the game
  her body is drawn at that box from the collapse on (popping out with the swipe, or standing
  free), so a peeking head would be a second one. The holographic boxes keep theirs.

## File Structure

| File | Responsibility after this plan |
|---|---|
| `src/brawl_ket/config.py` | + `BOX_SPLIT`, `BOX_FRAMES`, `DRIVE_SLOT_Y`, `COPY_CAUGHT_RECOVERY` |
| `src/brawl_ket/moves.py` | `Move` + `superpose`, `pop_out`, `leap`, `push_out`, `catch`, `paste`; `Character` + `fixed_basis`, `copy_paste`, `extra`; `BOX_HURT`, `NORMALS`, `BOX_SWIPE`, `ERWIN`, `DOS` |
| `src/brawl_ket/fighter.py` | THE BOX (`boxed`, `boxes`, `box_rects`, `collapse`), POUNCE's leap, DOS's fixed basis, COPY / PASTE (`clipboard`, `caught`) |
| `src/brawl_ket/fight.py` | `Fight(chars, seed=0)` with `self.rng`; the box measurement (`_touch`, `_measure`); `_catch_shots`; PASTE's level shot; `push_out` |
| `src/brawl_ket/poses.py` | the `"cat"` and `"dos"` builds, their new poses, `CASE_TILT`, `ARM_SOCKETS`, `drawn_joints()` |
| `src/brawl_ket/match.py` | seeds every round's and demo's `Fight` from `self.rng` |
| `src/brawl_ket/ink.py` (new) | the drawing primitives moved out of `render.py`: `_pt`, `limb`, `_ball`, `_block`, `_boot`, `_poly`, `_towards` |
| `src/brawl_ket/erwin.py` (new) | ERWIN's look: `draw_erwin`, the holographic and cardboard boxes, the collapse flash |
| `src/brawl_ket/dos.py` (new) | DOS's look: `draw_dos`, the cached screen faces, `floppy_sprite`, `draw_floppy`, `clip_icon` |
| `src/brawl_ket/render.py` | dispatches the new builds; THE BOX, COPY frame, BLUE SCREEN ring, CRT DROP, the floppy shot, the HUD clipboard; select panels and title |
| `src/brawl_ket/bot.py` | ERWIN's and DOS's rules |
| `src/brawl_ket/audio.py` | nine new cues |
| `tests/test_erwin.py`, `tests/test_dos.py`, `tests/test_balance.py` (new) | the two fighters' rules; the balance bar |
| `tools/snapshot.py`, `tools/balance.py` (new), `tools/benchmark.py` | frames to check by eye; the win-rate table; the frame cost |
| `README.md` | five fighters |

Measured before this plan (bot against bot, 200 seeds each side, at commit `3d4062f`): BOHR
wins 66% against ROBERT and 66% against PHOEBE; ROBERT wins 60% against PHOEBE. **The existing
three are not held to the 60% bar today** (no test checks it). Task 6 therefore enforces the
bar for every pairing with ERWIN or DOS, and prints the whole table, existing pairings
included, for the user to decide on.

---

### Task 1: A seeded fight, and ERWIN's rules

**Files:**
- Modify: `src/brawl_ket/config.py` (after `TUNNEL_EXPOSED`, line 34)
- Modify: `src/brawl_ket/moves.py` (`Move`, after `PHOEBE`, `CHARACTERS`)
- Modify: `src/brawl_ket/poses.py` (`POSES`, `BUILD_BONES`, `SCALE`, `HEAD_R`, `LIMB_W`)
- Modify: `src/brawl_ket/fighter.py`
- Modify: `src/brawl_ket/fight.py`
- Modify: `src/brawl_ket/match.py:298-306` (`_start_attract`), `:352-358` (`_start_round`)
- Modify: `src/brawl_ket/render.py:52-53` (`TORSO_EXTRA`, `PLATES`: a stand-in until Task 2)
- Modify: `src/brawl_ket/audio.py:149-152` (`EVENT_SOUNDS`)
- Modify: `tools/snapshot.py:53` (`ACCENTS`)
- Create: `tests/test_erwin.py`
- Modify: `tests/test_moves.py`, `tests/test_poses.py`, `tests/test_match.py`, `tests/test_bot.py`

**Interfaces:**
- Consumes: nothing new.
- Produces (later tasks rely on these exact names):
  - `config.BOX_SPLIT = 120`, `config.BOX_FRAMES = frames(1.5)` (90)
  - `Move.superpose: bool = False`, `Move.pop_out: Move | None = None`, `Move.leap: tuple[float, float] | None = None`
  - `moves.BOX_HURT = Box(-36, 0, 72, 86)`, `moves.NORMALS` (the seven normal slots), `moves.BOX_SWIPE`, `moves.ERWIN` (build `"cat"`); `CHARACTERS` order ROBERT, BOHR, PHOEBE, ERWIN
  - poses `"box_duck"`, `"swipe"`, `"pounce"`, `"scratch"`; `SCALE["cat"] = 2.1`, `HEAD_R["cat"] = 17`, `LIMB_W["cat"] = 13`
  - `Fight(chars: dict[str, Character], seed: int = 0)` with `Fight.seed: int`, `Fight.rng: random.Random`; every `Fighter.rng is fight.rng`
  - `Fighter.boxed -> bool` (property: `action == "boxed"`), `Fighter.boxes: tuple[float, float]`, `Fighter.box_real: int`, `Fighter.box_t: int`, `Fighter.stick: tuple[int, bool, bool]`, `Fighter.box_rects() -> list[tuple[float, float, int, int]]`, `Fighter.collapse(k: int, swipe: bool, events: list) -> None`
  - fight events `"box_split"` (from the fighter), `"box_collapse"` (from the fighter when she collapses herself, from the fight when measured; `Event.x` is where she is); move cues `"pounce"`, `"scratch"`
  - `fight._Strike.box: int | None`; `Fight._touch(rect, target) -> tuple[tuple[float, float], int | None] | None`; `Fight._measure(strikes, events) -> list[_Strike]`

- [ ] **Step 1: Write the failing tests for ERWIN's rules** in `tests/test_erwin.py`:

```python
"""ERWIN (docs/superpowers/specs/2026-10-21-brawl-ket-erwin-dos-design.md, section 2): THE BOX
splits her into two boxes and any attack that touches one measures her, 50/50; she collapses
herself with a press, a new stick direction or after 1.5 s, popping out with a swipe; POUNCE
leaps and knocks down; SCRATCH hangs in the air and claws three times. And the fight's seeded
random source, which the 50/50s come from."""

import random

import pytest

from brawl_ket import basis
from brawl_ket.basis import X_BASIS
from brawl_ket.config import BOX_FRAMES, BOX_SPLIT, STAGE_RIGHT, TUNNEL_PAST
from brawl_ket.fight import Fight, Shot
from brawl_ket.fighter import IDLE, FighterInput
from brawl_ket.moves import BOHR, ERWIN, PHOEBE, ROBERT

X = FighterInput(x=True)
A = FighterInput(a=True)
DOWN_X = FighterInput(down=True, x=True)
UP = FighterInput(up=True)
BOX, POUNCE, SCRATCH = (ERWIN.moves[s] for s in ("stand.X", "crouch.X", "air.X"))
SWIPE = BOX.pop_out
PHOTON = ROBERT.moves["stand.X"]


def heads_seed(heads: bool) -> int:
    """A fight seed whose first 50/50 comes up heads (random() < 0.5) or tails. Heads: a
    measured box is the one she is in; her own collapse picks box 1 (where she stood)."""
    return next(s for s in range(100) if (random.Random(s).random() < 0.5) == heads)


def versus(c1, c2, gap, seed=0):
    fight = Fight({"p1": c1, "p2": c2}, seed=seed)
    fight.fighters["p2"].x = fight.fighters["p1"].x + gap
    return fight


def step(fight, p1=IDLE, p2=IDLE):
    return fight.step({"p1": p1, "p2": p2})


def kinds(events):
    return [e.kind for e in events]


def hits_on(events, player):
    return [e for e in events if e.kind in ("hit", "block") and e.player == player]


def boxed(gap=300, seed=0, rival=ROBERT):
    """ERWIN (p1) presses X `gap` px from the rival and is stepped until she splits."""
    fight = versus(ERWIN, rival, gap, seed)
    me = fight.fighters["p1"]
    events = step(fight, X)
    for _ in range(20):
        if me.boxed:
            break
        events += step(fight)
    assert me.boxed
    return fight, me, events


# --- the seeded fight -------------------------------------------------------------------------


def test_a_fight_takes_a_seed_and_owns_its_random_source():
    a = Fight({"p1": ERWIN, "p2": ROBERT}, seed=7)
    b = Fight({"p1": ERWIN, "p2": ROBERT}, seed=7)
    assert a.seed == 7 and [a.rng.random() for _ in range(3)] == [b.rng.random() for _ in range(3)]
    assert Fight({"p1": ROBERT, "p2": ROBERT}).seed == 0
    assert all(f.rng is a.rng for f in a.fighters.values())


def test_the_same_seed_gives_the_same_collapse_and_seeds_differ():
    def where(seed):
        fight, me, _ = boxed(seed=seed)
        step(fight, A)
        return me.box_real

    assert where(3) == where(3)
    assert {where(s) for s in range(10)} == {0, 1}


# --- THE BOX: the split -----------------------------------------------------------------------


def test_the_box_splits_where_she_stood_and_120_px_towards_the_rival():
    fight, me, events = boxed(gap=200)
    x0 = me.boxes[0]
    assert me.boxes == (x0, x0 + BOX_SPLIT) and me.x == x0
    assert "box_split" in kinds(events)
    assert me.cooldowns.get("stand.X", 0) == 0          # the cooldown waits for the collapse


def test_box_2_can_land_behind_a_close_rival_and_stays_on_the_stage():
    fight, me, _ = boxed(gap=60)
    assert me.boxes[1] > fight.fighters["p2"].x         # behind the rival
    fight = versus(ERWIN, ROBERT, 50)
    me, rival = fight.fighters["p1"], fight.fighters["p2"]
    me.x, rival.x = STAGE_RIGHT - 60.0, STAGE_RIGHT - 10.0
    step(fight, X)
    for _ in range(BOX.startup):
        step(fight)
    assert me.boxed and me.boxes == (STAGE_RIGHT - 60.0, STAGE_RIGHT)


def test_while_superposed_she_has_no_body_and_the_rival_walks_through_a_box():
    fight, me, _ = boxed(gap=200)
    rival = fight.fighters["p2"]
    for _ in range(40):
        step(fight, IDLE, FighterInput(dx=-1))
    assert me.boxed and rival.x < me.boxes[1]           # walked straight through box 2


# --- THE BOX: measured by the rival -----------------------------------------------------------


@pytest.mark.parametrize("k", [0, 1])
@pytest.mark.parametrize("heads", [True, False])
def test_a_strike_on_a_box_measures_her(k, heads):
    fight, me, _ = boxed(seed=heads_seed(heads))
    rival = fight.fighters["p2"]
    rival.x = me.boxes[k] + 40              # beside box k, jabbing it
    events = []
    for i in range(12):
        events += step(fight, IDLE, FighterInput(a=i == 0))
    where = k if heads else 1 - k
    (collapse,) = [e for e in events if e.kind == "box_collapse"]    # once, where she turned out to be
    assert not me.boxed and me.box_real == where and collapse.x == me.boxes[where]
    if heads:       # she is in that box: the jab resolves against her as normal
        assert kinds(hits_on(events, "p1")) == ["hit"] and me.health == ERWIN.health - 4
    else:           # she is in the other one: it finds nothing
        assert hits_on(events, "p1") == [] and me.health == ERWIN.health


def test_measured_into_the_other_box_she_is_free_at_once():
    fight, me, _ = boxed(seed=heads_seed(False))
    rival = fight.fighters["p2"]
    rival.x = me.boxes[0] + 40
    for i in range(12):
        events = step(fight, IDLE, FighterInput(a=i == 0))
        if "box_collapse" in kinds(events):
            break
    assert me.action == "idle" and me.move is None      # no swipe: she just appears


def test_a_wrong_colour_strike_on_the_box_she_is_in_bounces():
    fight, me, _ = boxed(seed=heads_seed(True))
    rival = fight.fighters["p2"]
    rival.basis = X_BASIS                   # a purple jab: green ERWIN isn't hurt by it
    rival.x = me.boxes[0] + 40
    events = []
    for i in range(12):
        events += step(fight, IDLE, FighterInput(a=i == 0))
    assert kinds(hits_on(events, "p1")) == ["block"] and me.health == ERWIN.health


@pytest.mark.parametrize("heads", [True, False])
def test_a_shot_into_a_box_measures_her_and_flies_on_if_she_is_not_there(heads):
    fight, me, _ = boxed(seed=heads_seed(heads))
    shot = Shot("p2", PHOTON, me.boxes[0] + 40, 0.0, -PHOTON.projectile.speed, 200)
    fight.shots.append(shot)
    events = step(fight)
    assert not me.boxed
    if heads:
        assert me.x == me.boxes[0] and kinds(hits_on(events, "p1")) == ["hit"] and shot not in fight.shots
    else:
        assert me.x == me.boxes[1] and hits_on(events, "p1") == [] and shot in fight.shots


@pytest.mark.parametrize("heads", [True, False])
def test_a_throw_in_reach_of_a_box_measures_her(heads):
    fight, me, _ = boxed(seed=heads_seed(heads))
    rival = fight.fighters["p2"]
    rival.x = me.boxes[0] + 46              # in throw range of box 1 (her x)
    events = []
    for i in range(10):
        events += step(fight, IDLE, FighterInput(dx=-1, b=True) if i == 0 else IDLE)
    got = [(e.kind, e.error) for e in hits_on(events, "p1")]
    if heads:
        assert got == [("hit", basis.Y)] and me.action == "knockdown"
    else:
        assert got == [] and me.x == me.boxes[1]


def test_charge_noise_measures_with_its_first_shock_and_later_shocks_hit_her_body():
    fight, me, _ = boxed(seed=heads_seed(False), rival=BOHR)
    bohr = fight.fighters["p2"]
    bohr.x = me.boxes[0] + 50               # its field covers box 1 and the edge of box 2
    noise = BOHR.moves["crouch.X"]
    events, measured = [], False
    for i in range(noise.startup + 30):
        ev = step(fight, IDLE, FighterInput(down=True, x=i == 0))
        if not measured and "box_collapse" in kinds(ev):
            measured = True
            assert hits_on(ev, "p1") == []  # tails: the first shock found nothing
        events += ev
    assert measured and me.box_real == 1                # (the later shocks push her on)
    later = hits_on(events, "p1")
    assert later and later[0].kind == "hit"             # a later shock hits her body


def test_tunnel_past_a_superposed_erwin_goes_past_box_1():
    fight = versus(ERWIN, PHOEBE, 200)
    erwin, phoebe = fight.fighters["p1"], fight.fighters["p2"]
    step(fight, X)
    for _ in range(BOX.startup):
        step(fight)
    assert erwin.boxed
    step(fight, IDLE, DOWN_X)
    for _ in range(25):
        step(fight, IDLE, FighterInput(down=True))
    assert phoebe.x == erwin.boxes[0] - TUNNEL_PAST


# --- THE BOX: collapsed by herself ------------------------------------------------------------


@pytest.mark.parametrize("heads", [True, False])
def test_she_collapses_herself_with_a_press_and_pops_out_with_a_swipe(heads):
    fight, me, _ = boxed(seed=heads_seed(heads))
    events = step(fight, A)
    assert not me.boxed and me.x == me.boxes[0 if heads else 1]
    assert me.move is SWIPE and "box_collapse" in kinds(events)
    assert me.cooldowns["stand.X"] == BOX.cooldown      # the cooldown runs from the collapse


def test_a_new_stick_direction_collapses_her_but_one_held_from_before_does_not():
    fight = versus(ERWIN, ROBERT, 300)
    me = fight.fighters["p1"]
    hold = FighterInput(dx=-1)
    step(fight, FighterInput(dx=-1, x=True))
    for _ in range(BOX.startup + 5):
        step(fight, hold)
    assert me.boxed
    step(fight, UP)
    assert not me.boxed and me.move is SWIPE


def test_she_pops_out_by_herself_after_1_5_s():
    fight, me, _ = boxed()
    for _ in range(BOX_FRAMES - 1):
        step(fight)
    assert me.boxed
    events = step(fight)
    assert not me.boxed and me.move is SWIPE and "box_collapse" in kinds(events)


def test_the_swipe_hits_a_rival_beside_her_box_for_8():
    fight, me, _ = boxed(seed=heads_seed(True))         # heads: she pops out of box 1
    rival = fight.fighters["p2"]
    rival.x = me.boxes[0] + 50
    events = step(fight, A)
    for _ in range(SWIPE.startup + SWIPE.active):
        events += step(fight)
    assert kinds(hits_on(events, "p2")) == ["hit"] and rival.health == ROBERT.health - SWIPE.damage == 92


def test_the_cooldown_runs_from_the_collapse():
    fight, me, _ = boxed()
    for _ in range(40):
        step(fight)                         # time in the boxes doesn't count
    step(fight, A)
    events = []
    for i in range(BOX.cooldown - 1):
        events += step(fight, X if i % 5 == 0 else IDLE)
    assert "box_split" not in kinds(events)
    for i in range(BOX.startup + 6):
        step(fight, X if i == 0 else IDLE)
    assert me.boxed


def test_y_switches_her_basis_while_superposed_and_does_not_collapse_her():
    fight, me, _ = boxed()
    events = step(fight, FighterInput(y=True))
    assert me.boxed and me.basis == X_BASIS and "switch" in kinds(events)


# --- POUNCE and SCRATCH ------------------------------------------------------------------------


def test_pounce_leaps_low_and_knocks_down_a_crouching_rival():
    fight = versus(ERWIN, ROBERT, 120)
    me, rival = fight.fighters["p1"], fight.fighters["p2"]
    events, top = [], 0.0
    for i in range(60):
        events += step(fight, DOWN_X if i == 0 else FighterInput(down=True), FighterInput(down=True))
        top = max(top, me.y)
    assert 30 < top < 60                                # a long, low arc
    assert kinds(hits_on(events, "p2")) == ["hit"] and rival.action == "knockdown"
    assert "pounce" in kinds(events)


def test_a_missed_pounce_lands_into_a_long_recovery():
    fight = versus(ERWIN, ROBERT, 400)
    me = fight.fighters["p1"]
    step(fight, DOWN_X)
    airborne = False
    for _ in range(80):
        step(fight)
        airborne |= me.y > 0
        if airborne and me.y == 0:
            break
    assert me.action == "attack" and me.phase == "recovery"
    stuck = 0
    while me.action == "attack":
        step(fight)
        stuck += 1
    assert POUNCE.recovery - 1 <= stuck <= POUNCE.recovery


def test_scratch_hangs_in_the_air_and_claws_three_times():
    fight = versus(ERWIN, ROBERT, 44)
    me, rival = fight.fighters["p1"], fight.fighters["p2"]
    events = step(fight, UP) + step(fight, X)
    height = me.y
    for _ in range(60):
        events += step(fight)
        if me.hovering:
            assert me.y == height and me.vx == 0
    assert kinds(hits_on(events, "p2")) == ["hit"] * 3
    assert rival.health == ROBERT.health - 3 * SCRATCH.damage and me.y == 0


def test_scratch_is_once_per_jump():
    fight = versus(ERWIN, ROBERT, 300)
    me = fight.fighters["p1"]
    events = step(fight, UP) + step(fight, X)
    while me.y > 0:
        events += step(fight, X)            # mashing X in the air: no second scratch
    assert kinds(events).count("scratch") == 1
```

- [ ] **Step 2: Run them to make sure they fail**

Run: `uv run pytest tests/test_erwin.py -q`
Expected: collection error, `ImportError: cannot import name 'BOX_FRAMES' from 'brawl_ket.config'`.

- [ ] **Step 3: Add the config numbers.** In `src/brawl_ket/config.py`, after the
`TUNNEL_EXPOSED` line:

```python
BOX_SPLIT = 120          # THE BOX: ERWIN's second box stands this far towards the rival (on the stage)
BOX_FRAMES = frames(1.5)  # ... and she collapses herself after this long in the boxes at the latest
```

- [ ] **Step 4: Add the move data.** In `src/brawl_ket/moves.py`, add three fields at the
end of `Move` (after `cue`):

```python
    superpose: bool = False             # THE BOX: she splits into two boxes (fighter.py) until a collapse
    pop_out: Move | None = None         # ... and the swipe she pops out with when she collapses herself
    leap: tuple[float, float] | None = None   # (vx, vy) on the first active frame: an arc (POUNCE)
```

After `PHOEBE`, before `CHARACTERS`:

```python
NORMALS = ("stand.A", "stand.B", "crouch.A", "crouch.B", "air.A", "air.B", "throw")

# THE BOX's two boxes, each around its own x: the drawn box (70 px wide, 48 tall) and her ears
# over its rim. Every standing normal, PHOTON and FLOPPY touch it.
BOX_HURT = Box(-36, 0, 72, 86)

# The quick swipe ERWIN pops out of THE BOX with when she collapses it herself: MID, her colour,
# a short reach (60 px ahead, about a jab's).
BOX_SWIPE = Move(
    "BOX SWIPE", 3, 4, 14, Box(14, 50, 46, 36), OWN, MID,
    damage=8, hitstun=16, knockback=2.5, kind="special",
    poses=("crouch", "swipe", "jab_wind"),
)

ERWIN = Character(
    name="ERWIN",
    build="cat",
    health=90,                          # the least: quick and slippery, and THE BOX is a gamble
    walk=2.3,
    jump_vy=12.5,
    gravity=0.5,                        # an apex of about 156 px: the highest
    hurt_stand=Box(-14, 0, 28, 120),    # ROBERT's height
    hurt_crouch=Box(-16, 0, 32, 100),
    moves=MappingProxyType({
        **{slot: ROBERT.moves[slot] for slot in NORMALS},   # the shared normals, as ROBERT's
        # One cat, two places: she ducks into a box (startup, hittable), and on the first active
        # frame it splits into two (fighter.py, _split). Collapsed by her (a press, a new stick
        # direction, or BOX_FRAMES) she pops out with BOX_SWIPE; by the rival, it's a measurement
        # (fight.py, _measure). The cooldown runs from the collapse.
        "stand.X": Move(
            "THE BOX", 8, 1, 4, None, OWN, MID,
            damage=0, hitstun=1, knockback=0.0,
            kind="special", superpose=True, pop_out=BOX_SWIPE, cooldown=config.frames(3.0),
            poses=("box_duck", "box_duck", "box_duck"),
        ),
        # A long, low leap along an arc, which hits on the way. MID: a crouch doesn't save the
        # rival. The active frames outlast the 28-frame arc, so it always lands into its recovery.
        "crouch.X": Move(
            "POUNCE", 8, 30, 20, Box(10, 10, 70, 44), OWN, MID,
            damage=10, hitstun=20, knockback=4.0, knockdown=True,
            kind="special", leap=(6.0, 7.0), cooldown=config.frames(2.0), cue="pounce",
            poses=("crouch", "pounce", "crouch"),
        ),
        # She hangs in the air (like LASER) and claws three times: on active frames 0, 8 and 16.
        "air.X": Move(
            "SCRATCH", 4, 24, 8, Box(12, 40, 46, 36), OWN, MID,
            damage=4, hitstun=10, knockback=1.0, hit_every=8,
            kind="special", hover=True, once_per_jump=True, cue="scratch",
            poses=("jump", "scratch", "jump"),
        ),
    }),
)
```

and `CHARACTERS`:

```python
CHARACTERS: dict[str, Character] = {"ROBERT": ROBERT, "BOHR": BOHR, "PHOEBE": PHOEBE, "ERWIN": ERWIN}
```

Also change the `Character.build` comment to `# "lean" / "heavy" / "toy" / "cat" (poses scale)`.

- [ ] **Step 5: Add the cat build and her poses.** In `src/brawl_ket/poses.py`, append to `POSES`:

```python
    # ERWIN's stand.X THE BOX: ducking down into the box, paws tucked in
    "box_duck": Pose(24, 95, -4, 30, -86, 60, 170, 40, 160),
    # ... and the swipe she pops out of it with: a paw raking low and forward
    "swipe": Pose(18, 70, 10, -20, -50, 80, 75, 30, 150),
    # ERWIN's crouch.X POUNCE: stretched out along the leap, paws first, hind legs trailing
    "pounce": Pose(40, 140, 90, -70, -110, 100, 95, 85, 95),
    # ERWIN's air.X SCRATCH: hanging in the air, a paw raking forward
    "scratch": Pose(14, 100, 15, 40, -50, 60, 70, 30, 150),
```

and the build (the look script's numbers):

```python
BUILD_BONES = {
    "heavy": {"neck": 6},                   # the heavy's helmet sits down between its shoulders
    "toy": {"thigh": 18, "shin": 18, "forearm": 13, "upper_arm": 13, "neck": 8},   # PHOEBE: long limbs
    # ERWIN: ROBERT's height, a big head on a short neck; the long shin holds two cat-leg
    # segments (the lower leg and the long foot, up to the hock: erwin.py draws the hock)
    "cat": {"torso": 24, "neck": 7, "thigh": 15, "shin": 18, "upper_arm": 12, "forearm": 12},
}
SCALE = {"lean": 2.0, "heavy": 2.3, "toy": 2.1, "cat": 2.1}     # the mockup's proportions: about 130 px tall
HEAD_R = {"lean": 13, "heavy": 15, "toy": 14, "cat": 17}
LIMB_W = {"lean": 12, "heavy": 16, "toy": 12, "cat": 13}
```

- [ ] **Step 6: THE BOX, the leap and the shared random source in `src/brawl_ket/fighter.py`.**

Imports: add `import random` (after `from dataclasses import dataclass`), add `BOX_FRAMES`
and `BOX_SPLIT` to the `.config` import list, and `BOX_HURT` to the `.moves` import
(`from .moves import BOX_HURT, Box, Character, Move`). In the module docstring add a line:
`THE BOX (ERWIN) is the "boxed" action: superposed in two boxes, with no body; the fight measures her.`

At the end of `Fighter.__init__`:

```python
        self.rng = random.Random(0)     # the fight gives every fighter its own seeded source
        self.stick = (0, False, False)  # last frame's stick (dx, up, down): THE BOX waits for a new one
        self.boxes: tuple[float, float] = (self.x, self.x)  # THE BOX: where she stood, the far box
        self.box_real = 0               # ... the box a collapse found her in (0 or 1)
        self.box_t = 0                  # ... frames superposed
```

and change the `self.action` comment to `# idle walk crouch jump attack hitstun knockdown boxed`.

Derived state, after `hovering`:

```python
    @property
    def boxed(self) -> bool:
        """THE BOX: superposed in two boxes, with no body (the fight measures her)."""
        return self.action == "boxed"

    def box_rects(self) -> list[tuple[float, float, int, int]]:
        """THE BOX: each box as a hurtbox (left, top, w, h) in screen px, box 1 first."""
        b = BOX_HURT
        return [(x + b.x, FLOOR_Y - (b.y + b.h), b.w, b.h) for x in self.boxes]
```

In `hurtbox`, first line of the body:

```python
        if self.boxed:              # for whoever asks for one box: box 1, where she stood
            return self.box_rects()[0]
```

In `step`, just before the `self.buffer = [ ... ]` ageing line:

```python
        self.stick = (inp.dx, inp.up, inp.down)
```

After `knock_out`:

```python
    def collapse(self, k: int, swipe: bool, events: list) -> None:
        """THE BOX collapses: she turns out to be in box k (0: where she stood, 1: the far one)
        and is free at once, facing the rival. `swipe`: she collapsed it herself and pops out
        with the move's swipe. The cooldown runs from now."""
        box = self.char.moves["stand.X"]
        self.box_real = k
        self.x = float(self.boxes[k])
        self.box_t = 0
        self.cooldowns["stand.X"] = box.cooldown
        if self.rival_x != self.x:
            self.facing = 1 if self.rival_x > self.x else -1
        self.action = "idle"
        self.frame = 0
        events.append(("box_collapse", {}))
        if swipe:
            assert box.pop_out is not None
            self._start_move("stand.X", box.pop_out, False, events)
```

In `_advance`, a branch after the `elif self.action == "attack":` block:

```python
        elif self.action == "boxed":
            self.box_t += 1
```

In `_move_effects`, at the top of the `if self.frame == self.startup:` block:

```python
                if m.superpose:         # THE BOX: one cat, two boxes
                    self._split(events)
                    return
                if m.leap is not None:  # POUNCE: off along an arc; gravity does the rest
                    self.vx, self.vy = m.leap[0] * self.facing, m.leap[1]
```

At the top of `_act`:

```python
        if self.boxed:
            self._boxed(inp, events)
            return
```

In `_start_move`, the cooldown line becomes:

```python
        if move.cooldown > 0 and not move.superpose:     # THE BOX's runs from its collapse
            self.cooldowns[slot] = move.cooldown
```

In `_land`, the dive branch becomes:

```python
            if m.dive is not None or m.leap is not None:
                # a dive or a leap that reaches the floor skips to its recovery
                self.frame = max(self.frame, self.startup + m.active)
```

New internals (after `_tunnel_target`):

```python
    def _split(self, events: list) -> None:
        """THE BOX splits: box 1 where she stands, box 2 BOX_SPLIT px towards the rival (kept on
        the stage, so it can land behind a rival who is close). She has no body until it collapses."""
        side = 1 if self.rival_x > self.x else -1 if self.rival_x < self.x else self.facing
        far = min(max(self.x + side * BOX_SPLIT, STAGE_LEFT), STAGE_RIGHT)
        self.boxes = (self.x, far)
        self.move = None
        self.slot = None
        self.chained = False
        self.move_hit = False
        self.crouching = False
        self.buffer = []            # a press from the ducking-in mustn't collapse it at once
        self.vx = 0.0
        self.action = "boxed"
        self.frame = 0
        self.box_t = 0
        events.append(("box_split", {}))

    def _boxed(self, inp: FighterInput, events: list) -> None:
        """Superposed: any button (A, B or X; Y only switches) or a new stick direction collapses
        it, or BOX_FRAMES at the latest. She lands in a random box, 50/50, with a swipe."""
        stick = (inp.dx, inp.up, inp.down)
        fresh = stick != self.stick and stick != (0, False, False)
        if fresh or self.buffer or self.box_t >= BOX_FRAMES:
            self.collapse(0 if self.rng.random() < 0.5 else 1, True, events)
```

- [ ] **Step 7: The seed and the measurement in `src/brawl_ket/fight.py`.**

Module docstring, first paragraph becomes:

```python
"""One round between two fighters: hits, projectiles, hitstop, the clock.

Pure logic, no pygame. Its only randomness is THE BOX's 50/50s, drawn from the fight's own
random.Random(seed): the same inputs and the same seed always give the same round. The
fight drives two Fighters (fighter.py), spawns and moves the shots,
```

(the rest of the docstring unchanged). Add `import random` after `from __future__ import annotations`.

`_Strike` gets a last field:

```python
    box: int | None = None      # THE BOX: which of the defender's boxes it touched
```

`Fight.__init__` becomes:

```python
    def __init__(self, chars: dict[str, Character], seed: int = 0) -> None:
        self.seed = seed
        self.rng = random.Random(seed)      # THE BOX's 50/50s
        self.fighters: dict[str, Fighter] = {
            "p1": Fighter(chars["p1"], START_X["p1"], 1),
            "p2": Fighter(chars["p2"], START_X["p2"], -1),
        }
        self.body_width = body_width(chars["p1"], chars["p2"])
        for f in self.fighters.values():   # a throw reaches a little past the push box
            f.throw_range = self.body_width + THROW_SLACK
            f.body_width = self.body_width
            f.rng = self.rng
        # ... the rest unchanged
```

`_push_apart`'s guard becomes:

```python
        if a.y > 0 or b.y > 0 or a.intangible or b.intangible or a.boxed or b.boxed \
                or abs(b.x - a.x) >= width:
            return
```

In `_resolve_hits`, the shot loop's overlap becomes:

```python
            touch = self._touch(s.box, target)
            if touch is not None:
                strikes.append(_Strike(None, s.owner, rival_key, s.move, s.facing, touch[0], s, box=touch[1]))
```

and right after the collection loops, before `# Every strike was found against the state ...`:

```python
        strikes = self._measure(strikes, events)
```

In `_move_strike`, the last three lines become:

```python
        touch = self._touch(f.world_box(m.hitbox), rival)
        if touch is not None:
            strikes.append(_Strike(key, key, rival_key, m, f.facing, touch[0], box=touch[1]))
```

In `_landing_strike`, the overlap block becomes:

```python
            touch = self._touch(f.world_box(move.landing), rival)
            if touch is not None:
                win.hit = True
                strikes.append(_Strike(
                    None, key, rival_key, replace(move, colour=move.landing_colour, height=move.landing_height),
                    f.facing, touch[0], box=touch[1],
                ))
```

New methods (after `_resolve_hits`):

```python
    @staticmethod
    def _touch(rect: Rect, target: Fighter) -> tuple[tuple[float, float], int | None] | None:
        """Where an attack's rect meets the target: its body, or (THE BOX) the first box it
        touches and which one."""
        if target.boxed:
            for k, box in enumerate(target.box_rects()):
                where = _overlap(rect, box)
                if where is not None:
                    return where, k
            return None
        where = _overlap(rect, target.hurtbox)
        return None if where is None else (where, None)

    def _measure(self, strikes: list[_Strike], events: list[Event]) -> list[_Strike]:
        """THE BOX: the first strike that touches a box (a hit, a shot, a throw, a field, a
        shockwave) measures her, 50/50. She is in that box (the strikes on it land on her as
        normal, the colour rule included) or in the other one (they find nothing: a shot flies
        on). Either way she is free at once, with no swipe. A repeating move's shock that found
        nothing is still spent (CHARGE NOISE: later shocks hit her body)."""
        kept: list[_Strike] = []
        real: dict[str, int] = {}
        for st in strikes:
            if st.box is None:
                kept.append(st)
                continue
            d = self.fighters[st.defender]
            if st.defender not in real:
                k = st.box if self.rng.random() < 0.5 else 1 - st.box
                real[st.defender] = k
                d.collapse(k, False, [])
                events.append(Event("box_collapse", st.defender, None, d.x, FLOOR_Y))
            if st.box == real[st.defender]:
                kept.append(st)
            elif st.attacker is not None and st.move.hit_every:
                a = self.fighters[st.attacker]
                a.move_hit, a.hit_frame = True, a.frame
        return kept
```

- [ ] **Step 8: Seed every fight from the match.** In `src/brawl_ket/match.py`,
`_start_attract` becomes (the rng draws stay in the same order):

```python
    def _start_attract(self) -> None:
        self.title_index = 0    # whoever stops the demo finds PLAY, never QUIT, under A
        chars = {p: self.rng.choice(ROSTER) for p in PLAYERS}
        self.stage = self.rng.choice(config.STAGES)
        self._title_phase = 0
        seed = self.rng.randrange(1 << 30)
        self.attract = Fight(chars, seed)       # the demo fight and its bots, seeded from the match
        self.bots = {p: Bot(p, seed + i) for i, p in enumerate(PLAYERS)}
        self._attract_over = 0
```

and in `_start_round`:

```python
        self.fight = Fight({p: ROSTER[self.picks[p]] for p in PLAYERS}, self.rng.randrange(1 << 30))
```

Change the `ROSTER` comment to `# the select screen's order: ROBERT, BOHR, PHOEBE, ERWIN, DOS`.

- [ ] **Step 9: Keep the rest of the game running with a fourth fighter.**
  - `src/brawl_ket/render.py`: `TORSO_EXTRA` and `PLATES` get `"cat": 5` and `"cat": False`
    (ERWIN is drawn as the lean puppet on her own skeleton until Task 2 replaces both lines).
  - `src/brawl_ket/audio.py`: add `"box_split": None, "box_collapse": None,` to `EVENT_SOUNDS`
    (Task 5 gives them sounds).
  - `tools/snapshot.py`: `ACCENTS = {"lean": P.CREAM, "heavy": P.GOLD, "toy": P.TEAL, "cat": P.GOLD}`.

- [ ] **Step 10: Run ERWIN's tests**

Run: `uv run pytest tests/test_erwin.py -q`
Expected: all pass.

- [ ] **Step 11: Bring the cross-cutting tests up to five-fighter shape (ERWIN now).**

`tests/test_moves.py`:
- the import becomes `from brawl_ket.moves import CHARACTERS, ERWIN, NORMALS, PHOEBE, ROBERT, SLOTS, Box`
  (`BOHR` is no longer used once `test_health` reads the table)
- `STARTUPS` gets `"ERWIN": (4, 10, 7),`
- replace `test_the_damage` with:

```python
# by name: the specials whose damage isn't a special's 10 (MEASURE 12; TUNNEL only moves her; LASER a
# little less; CHARGE NOISE a shock; THE BOX itself nothing, its swipe 8; SCRATCH a claw)
SPECIAL_DAMAGE = {"MEASURE": 12, "TUNNEL": 0, "LASER": 8, "CHARGE NOISE": 3, "THE BOX": 0, "SCRATCH": 4}


def test_the_damage():
    for c, slot, m in all_moves():
        if m.name in SPECIAL_DAMAGE:
            assert m.damage == SPECIAL_DAMAGE[m.name], (c.name, slot)
        else:
            key = "throw" if slot == "throw" else slot.split(".")[1]
            assert m.damage == DAMAGE[key], (c.name, slot)
```

- `test_health` becomes:

```python
def test_health():
    assert {c.name: c.health for c in CHARACTERS.values()} == {
        "ROBERT": 100, "BOHR": 115, "PHOEBE": 95, "ERWIN": 90}
```

- `test_only_a_projectile_has_no_hitbox`: `assert m.kind == "projectile" or m.tunnel or m.superpose, (c.name, slot)`
- replace `SPECIALS`, `TWISTS` and the twist assertion in `test_the_specials_colours_and_twists`:

```python
SPECIALS = {   # (character, slot): (colour rule, height, twists): every special is your colour
    ("ROBERT", "stand.X"): (OWN, HIGH, ()),
    ("ROBERT", "crouch.X"): (OWN, LOW, ()),
    ("ROBERT", "air.X"): (OWN, MID, ("switch_self_on_hit",)),
    ("BOHR", "stand.X"): (BOTH, MID, ("measure_rival",)),     # a throw: both, like every throw
    ("BOHR", "crouch.X"): (OWN, MID, ("hit_every",)),
    ("BOHR", "air.X"): (OWN, MID, ()),
    ("PHOEBE", "stand.X"): (OWN, MID, ()),
    ("PHOEBE", "crouch.X"): (OWN, MID, ("tunnel",)),
    ("PHOEBE", "air.X"): (OWN, MID, ("hover",)),
    ("ERWIN", "stand.X"): (OWN, MID, ("superpose",)),
    ("ERWIN", "crouch.X"): (OWN, MID, ("leap",)),
    ("ERWIN", "air.X"): (OWN, MID, ("hit_every", "hover")),
}
TWISTS = ("switch_self_on_hit", "measure_rival", "hit_every", "tunnel", "hover", "superpose", "leap")


def test_the_specials_colours_and_twists():
    for (name, slot), (colour, height, twists) in SPECIALS.items():
        m = CHARACTERS[name].moves[slot]
        assert (m.colour, m.height) == (colour, height), (name, slot)
        assert tuple(t for t in TWISTS if getattr(m, t)) == twists, (name, slot)
    names = {n: [CHARACTERS[n].moves[s].name for s in ("stand.X", "crouch.X", "air.X")] for n in CHARACTERS}
    assert names == {"ROBERT": ["PHOTON", "PHASE SLIDE", "HADAMARD DIVE"],
                     "BOHR": ["MEASURE", "CHARGE NOISE", "COLLAPSE"],
                     "PHOEBE": ["LIGHT PILLAR", "TUNNEL", "LASER"],
                     "ERWIN": ["THE BOX", "POUNCE", "SCRATCH"]}
```

- new tests at the end:

```python
# --- ERWIN -----------------------------------------------------------------------------------


def test_erwin_stats():
    e = CHARACTERS["ERWIN"]
    assert (e.build, e.health, e.walk, e.jump_vy, e.gravity) == ("cat", 90, 2.3, 12.5, 0.5)
    others = [c for c in CHARACTERS.values() if c is not e]
    assert apex(e) > max(apex(c) for c in others) and e.health < min(c.health for c in others)
    for slot in NORMALS:
        assert e.moves[slot] is ROBERT.moves[slot], slot


def test_erwin_specials():
    box, pounce, scratch = (ERWIN.moves[s] for s in ("stand.X", "crouch.X", "air.X"))
    assert box.superpose and box.hitbox is None and box.cooldown == config.frames(3.0)
    swipe = box.pop_out
    assert (swipe.damage, swipe.height, swipe.colour, swipe.kind) == (8, MID, OWN, "special")
    assert swipe.hitbox.x + swipe.hitbox.w <= 64                 # short range
    assert pounce.leap is not None and (pounce.damage, pounce.height, pounce.knockdown) == (10, MID, True)
    assert pounce.cooldown == config.frames(2.0) and 18 <= pounce.recovery <= 22
    assert pounce.active > 2 * pounce.leap[1] / ERWIN.gravity    # it always lands in its active frames
    assert scratch.hover and scratch.once_per_jump and (scratch.damage, scratch.height) == (4, MID)
    assert -(-scratch.active // scratch.hit_every) == 3          # three claws
```

`tests/test_poses.py`:
- the test file's `STRIKER` dict gets `"POUNCE": "hand_f", "SCRATCH": "hand_f",`
- `ACTIONS` gets `"boxed"` at the end
- a new test after `test_photon_leaves_from_the_hand`:

```python
def test_the_box_swipe_reaches_its_hitbox():
    from brawl_ket.moves import ERWIN
    swipe = ERWIN.moves["stand.X"].pop_out
    f = Fighter(ERWIN, FEET[0], 1)
    f.action, f.move, f.slot, f.frame = "attack", swipe, "stand.X", swipe.startup
    j = joints(pose_for(f), ERWIN.build, FEET, 1)
    assert distance_to_box(j["hand_f"], screen_box(swipe)) <= REACH
```

`tests/test_match.py`, after `test_the_demo_starts_a_new_fight_when_one_ends`:

```python
def test_each_round_gets_its_seed_from_the_matchs_rng() -> None:
    seeds = []
    for _ in range(2):
        m = Match(random.Random(4))
        to_fight(m)
        seeds.append(m.fight.seed)
    assert seeds[0] == seeds[1]
    m = Match(random.Random(4))
    to_fight(m)
    first = m.fight.seed
    ko(m, "p2")                             # round 2: a fresh fight, a fresh seed
    assert m.state == ROUND_INTRO and m.fight.seed != first


def test_the_demo_fight_is_seeded_from_the_matchs_rng() -> None:
    a, b = Match(random.Random(9)), Match(random.Random(9))
    for m in (a, b):
        run(m, config.ATTRACT_DELAY + 1)
    assert a.attract is not None and a.attract.seed == b.attract.seed
```

`tests/test_bot.py`, `play` seeds its fight (so THE BOX's 50/50s vary from seed to seed):

```python
    fight = Fight({"p1": CHARACTERS[pairing[0]], "p2": CHARACTERS[pairing[1]]}, seed=seed)
```

- [ ] **Step 12: Run the whole suite and the lint**

Run: `uv run pytest -q && uvx --from 'ruff==0.15.22' ruff check src tests tools`
Expected: all pass, `All checks passed!`.
`test_neither_side_is_favoured` is expected to fail for `(ROBERT, ERWIN)` (measured on a
prototype of this task: her bot doesn't use her specials until Task 6, and she is ROBERT with
less health). Give that one test its own parameter list, the same pairings with only the
failing one(s) wrapped as `pytest.param(pair, marks=pytest.mark.xfail(reason="ERWIN's bot: Task 6", strict=False))`
(the shared `PAIRINGS` stays as it is); Task 6 removes the list. Change nothing else to make it pass.

- [ ] **Step 13: Commit**

```bash
git add src/brawl_ket/config.py src/brawl_ket/moves.py src/brawl_ket/poses.py src/brawl_ket/fighter.py \
  src/brawl_ket/fight.py src/brawl_ket/match.py src/brawl_ket/render.py src/brawl_ket/audio.py \
  tools/snapshot.py tests/test_erwin.py tests/test_moves.py tests/test_poses.py tests/test_match.py tests/test_bot.py
git commit -m "feat: :game_die: Brawl-Ket: a seeded fight, and ERWIN's rules (THE BOX, POUNCE, SCRATCH)

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---
### Task 2: ERWIN drawn as the approved cat, with THE BOX

**Files:**
- Create: `src/brawl_ket/ink.py` (the primitives moved out of `render.py`)
- Create: `src/brawl_ket/erwin.py`
- Modify: `src/brawl_ket/render.py`
- Modify: `tools/snapshot.py`
- Modify: `tests/test_render.py`

**Interfaces:**
- Consumes (Task 1): `ERWIN`, `BOX_SWIPE`, `Fighter.boxed`, `Fighter.boxes`, `Fighter.box_real`,
  `Fighter.collapse`, events `"box_split"` / `"box_collapse"`, poses and `SCALE["cat"]`,
  `HEAD_R["cat"]`, `LIMB_W["cat"]`.
- Produces:
  - `ink._pt(p) -> tuple[int, int]`, `ink.limb(surf, a, b, w, color, ink=P.INK)`, `ink._ball(surf, p, r, color)`, `ink._block(surf, p, half, color, radius=3)`, `ink._boot(surf, foot, facing, w, color)`, `ink._poly(surf, pts, color, ink=2)`, `ink._towards(a, b, k)` (all still importable from `render`); `ink.frame(j, facing) -> at(base, up, front)`, `ink.poly(surf, pts, color, ink=2)` (the look scripts' helpers)
  - `erwin.EYE`, `erwin.CARD`, `erwin.BOX_W`, `erwin.BOX_H`, `erwin.HOLO_PHASES`, `erwin.FADE_STEPS`
  - `erwin.draw_erwin(surf, j: dict, facing: int, fur: tuple, strike: tuple[str, tuple] | None = None) -> dict`
  - `erwin.cat_leg_points(j, side, facing) -> tuple[point, point]` (knee, hock)
  - `erwin.holo_sprite(fur, facing, phase, fade_step=0) -> tuple[Surface, Surface]` (lru-cached), `erwin.draw_holo_box(surf, x, floor, facing, fur, phase, fade_step=0)`, `erwin.draw_superposed(surf, boxes, floor, facing, fur, t)`, `erwin.draw_collapse(surf, x, floor, facing, fur, age)`
  - `render.draw_puppet(surf, pose, build, feet, facing, body, accent, flare=0.0, strike=None, mood="calm", led=False, eject=False) -> dict` (`mood`, `led`, `eject` are DOS's, used from Task 4)
  - `render.strike_of(f: Fighter) -> tuple[str, tuple] | None`; `render.SELF_LIT: tuple[str, ...]`; `Effect.facing: int = 1`

- [ ] **Step 1: Write the failing tests.** In `tests/test_render.py`, add at the top
`import importlib.util` and `from pathlib import Path`, and append:

```python
# --- the approved looks: the game draws each new fighter exactly as its look script does ---------

LOOKS = Path(__file__).resolve().parents[2] / "docs" / "superpowers" / "specs"


@pytest.fixture
def look(monkeypatch):
    """Load an approved look script. It writes its build into the skeleton's tables when it is
    imported, so for the test those tables are copies."""
    from brawl_ket import poses as PS

    def load(name: str):
        path = LOOKS / name
        if not path.exists():
            pytest.skip(f"{name} is not in this checkout")
        for table in ("SCALE", "HEAD_R", "LIMB_W"):
            monkeypatch.setattr(PS, table, dict(getattr(PS, table)))
        monkeypatch.setattr(PS, "BUILD_BONES", {k: dict(v) for k, v in PS.BUILD_BONES.items()})
        spec = importlib.util.spec_from_file_location(path.stem.replace("-", "_"), path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    return load


def same_pixels(a: pygame.Surface, b: pygame.Surface, mode: str = "RGB") -> bool:
    return pygame.image.tostring(a, mode) == pygame.image.tostring(b, mode)


@pytest.mark.parametrize("name,strike", [("idle", None), ("crouch", None), ("jump", None),
                                         ("heavy_hit", ("hand_f", PURPLE)), ("sweep_hit", ("foot_f", PURPLE))])
@pytest.mark.parametrize("facing", [1, -1])
@pytest.mark.parametrize("fur", [GREEN, PURPLE], ids=["green", "purple"])
def test_erwin_matches_her_approved_look(look, name, strike, facing, fur):
    from brawl_ket.erwin import draw_erwin
    from brawl_ket.poses import POSES, joints
    ref = look("2026-10-21-brawl-ket-erwin-look.py")
    pygame.init()
    a, b = pygame.Surface((240, 240)), pygame.Surface((240, 240))
    a.fill(BLANK)
    b.fill(BLANK)
    feet = (120.0, 220.0)
    ref.draw_erwin(a, POSES[name], feet, facing, fur, strike)
    draw_erwin(b, joints(POSES[name], "cat", feet, facing), facing, fur, strike)
    assert same_pixels(a, b)


def test_the_holographic_boxes_are_her_colour():
    from brawl_ket.erwin import CARD, holo_sprite
    pygame.init()
    for fur in (GREEN, PURPLE):
        out, _pool = holo_sprite(fur, 1, 0)
        seen = {tuple(out.get_at((x, y)))[:3] for x in range(0, out.get_width(), 2)
                for y in range(0, out.get_height(), 2)}
        assert fur in seen and CARD not in seen


def boxed_fight(r, frames=40):
    """ERWIN (p1) in THE BOX `frames` frames after the split, drawn every frame."""
    from brawl_ket.fighter import FighterInput
    from brawl_ket.moves import ERWIN
    fight = Fight({"p1": ERWIN, "p2": ROBERT}, seed=1)
    fight.fighters["p2"].x = 600
    r.draw_fight(fight, fight.step({"p1": FighterInput(x=True)}))
    for _ in range(ERWIN.moves["stand.X"].startup + frames):
        r.draw_fight(fight, fight.step({}))
    assert fight.fighters["p1"].boxed
    return fight


def test_superposed_erwin_is_two_boxes_drawn_from_cached_sprites(surface):
    from brawl_ket.erwin import HOLO_PHASES, holo_sprite
    from brawl_ket.stages import MARGIN
    holo_sprite.cache_clear()
    r = Renderer(surface)
    fight = boxed_fight(r)
    info = holo_sprite.cache_info()
    assert info.currsize <= HOLO_PHASES and info.hits > info.misses
    for x in fight.fighters["p1"].boxes:
        changed = [(i, j) for i in range(round(x) - 30, round(x) + 31, 3) for j in range(FLOOR_Y - 50, FLOOR_Y - 4, 3)
                   if surface.get_at((i, j)) != r.stage.get_at((i + MARGIN, j + MARGIN))]
        assert len(changed) > 40, x


def test_a_collapse_shows_one_real_cardboard_box_then_clears(surface):
    from brawl_ket.erwin import CARD
    from brawl_ket.fighter import FighterInput
    r = Renderer(surface)
    fight = boxed_fight(r)
    r.draw_fight(fight, fight.step({"p1": FighterInput(a=True)}))
    erwin = fight.fighters["p1"]
    assert not erwin.boxed and {"box_pop", "box_fade"} <= {fx.kind for fx in r.effects}
    real = round(erwin.boxes[erwin.box_real])
    seen = {tuple(surface.get_at((i, j)))[:3] for i in range(real - 34, real + 35, 2) for j in range(FLOOR_Y - 46, FLOOR_Y, 2)}
    assert CARD in seen
    for _ in range(60):
        r.draw_fight(fight, fight.step({}))
    assert not [fx for fx in r.effects if fx.kind in ("box_pop", "box_fade")]


def test_erwins_kicking_leg_is_lit_in_the_attacks_colour(surface):
    from brawl_ket.erwin import cat_leg_points
    from brawl_ket.fighter import FighterInput
    from brawl_ket.moves import ERWIN
    from brawl_ket.poses import joints
    r = Renderer(surface)
    fight = Fight({"p1": ERWIN, "p2": ROBERT})
    fight.fighters["p2"].x = 600
    for i in range(3):
        r.draw_fight(fight, fight.step({"p1": FighterInput(down=True, b=i == 0)}))
    f = fight.fighters["p1"]
    assert f.action == "attack" and f.phase == "startup"
    j = joints(r.pose_last["p1"], "cat", (f.x, FLOOR_Y - f.y), f.facing)
    knee, hock = cat_leg_points(j, "f", f.facing)
    assert PURPLE in limb_colours(surface, r, f, {"knee": knee, "hock": hock}, "knee", "hock")
```

- [ ] **Step 2: Run them to make sure they fail**

Run: `uv run pytest tests/test_render.py -q -k "erwin or holographic or superposed or collapse"`
Expected: FAIL with `ModuleNotFoundError: No module named 'brawl_ket.erwin'`.

- [ ] **Step 3: Move the primitives to `src/brawl_ket/ink.py`.** Create it with this
docstring and imports, then **cut** `_pt`, `limb`, `_ball`, `_block`, `_boot`, `_towards`
and `_poly` out of `render.py` and paste them below, unchanged:

```python
"""The drawing primitives every fighter is built from: chunky capsules, balls and blocks with
a 2 px ink outline, and a body's own frame. Shared by render.py, erwin.py and dos.py
(render.py re-exports the ones it had)."""

from __future__ import annotations

import math

import pygame

from . import palette as P
```

and after them add the two helpers the look scripts share (`frame`, and their `poly`, which,
unlike `_poly`, can skip the outline):

```python
def frame(j, facing):
    """at(base, up, front): a point `up` px along the spine and `front` px towards the face."""
    hip, neck = j["hip"], j["neck"]
    tx, ty = neck[0] - hip[0], neck[1] - hip[1]
    n = math.hypot(tx, ty) or 1.0
    ux, uy = tx / n, ty / n
    fx, fy = -uy * facing, ux * facing

    def at(base, up, front):
        return (base[0] + ux * up + fx * front, base[1] + uy * up + fy * front)
    return at


def poly(surf, pts, color, ink=2):
    """A filled polygon, with an `ink` px outline (0: none)."""
    pts = [_pt(p) for p in pts]
    pygame.draw.polygon(surf, color, pts)
    if ink:
        pygame.draw.polygon(surf, P.INK, pts, ink)
```

In `render.py`, after the `.fonts` import:

```python
from .ink import _ball, _block, _boot, _poly, _pt, _towards, limb
```

- [ ] **Step 4: Create `src/brawl_ket/erwin.py`.** The fighter's functions are the look
script's, verbatim except that `draw_erwin` takes the joints and the module's
`LIMB_W` / `HEAD_R`; the boxes draw onto small cached sprites:

```python
"""ERWIN's look: Schrodinger's cat on the shared skeleton, and THE BOX.

Ported from her approved look, docs/superpowers/specs/2026-10-21-brawl-ket-erwin-look.py:
draw_erwin and everything it calls are the look's own code, given the joints instead of a
pose (tests/test_render.py checks her against the look pixel for pixel). The holographic
and cardboard boxes are the look's too, but each is drawn once per colour, facing and
shimmer phase onto a small sprite (the look drew a full-screen layer every call), then only
blitted: the superposition costs four blits a frame.
"""

from __future__ import annotations

import math
from functools import lru_cache

import pygame

from . import palette as P
from .ink import _ball, _pt, frame, limb, poly
from .ink import _towards as towards
from .poses import HEAD_R, LIMB_W

NOSE = (240, 136, 168)
EYE = (248, 208, 64)            # amber: the one warm accent, as BOHR's gold
CARD = (200, 144, 88)
CARD_DARK = (152, 104, 64)
CARD_DEEP = (104, 64, 40)
CARD_LIGHT = (224, 176, 120)
TAPE = (232, 208, 160)

BOX_W, BOX_H = 70, 52           # a box as drawn
KEY = (255, 0, 255)             # the see-through colour of the box sprites
OFF = (1, 2, 3)                 # ... and of the dither stencil
SPRITE_W, SPRITE_H = 140, 130   # a box sprite, with its box centred at SPRITE_X on its floor line
SPRITE_X, SPRITE_FLOOR = 60, 120
HOLO_PHASES = 4                 # the shimmer's slipped rows: this many variants, cycled
FADE_STEPS = 4                  # a box dissolving: this many dither steps
FLASH_FRAMES = 6                # the collapse's white rim and rays


# --- shared helpers (the look's) -----------------------------------------------------------


def blob(surf, pts, color):
    """A filled shape with a 2 px ink outline all round, its corners rounded off."""
    pts = [_pt(p) for p in pts]
    pygame.draw.polygon(surf, P.INK, pts, 5)
    for p in pts:
        pygame.draw.circle(surf, P.INK, p, 2)
    pygame.draw.polygon(surf, color, pts)


def chain(surf, pts, widths, colors):
    """A bendy tube through pts (a tail): all its ink first, then all its fill, so there is
    one outline round the whole tube and no seams between its segments."""
    pts = [_pt(p) for p in pts]
    for k in (0, 1):
        for i in range(len(pts) - 1):
            w = widths[i] + (4 if k == 0 else 0)
            c = P.INK if k == 0 else colors[i]
            pygame.draw.line(surf, c, pts[i], pts[i + 1], w)
            pygame.draw.circle(surf, c, pts[i], w // 2)
            pygame.draw.circle(surf, c, pts[i + 1], w // 2)


def curve(p0, p1, p2, p3, n):
    """n+1 points along a cubic Bezier."""
    out = []
    for i in range(n + 1):
        t = i / n
        a, b, c, d = (1 - t) ** 3, 3 * t * (1 - t) ** 2, 3 * t * t * (1 - t), t ** 3
        out.append((a * p0[0] + b * p1[0] + c * p2[0] + d * p3[0], a * p0[1] + b * p1[1] + c * p2[1] + d * p3[1]))
    return out


# --- cat parts (the look's) -----------------------------------------------------------------


def paw(surf, p, r, color):
    """A round mitten paw with two toe creases."""
    _ball(surf, p, r, color)
    x, y = _pt(p)
    for dx in (-2, 2):
        pygame.draw.line(surf, P.shade(color, 0.6), (x + dx, y + 1), (x + dx, y + r - 1), 1)


def cat_head(surf, c, r, facing, fur, light, peek=False):
    """The head: wide cheeks with a tuft behind, two tall ears, a pale muzzle with a pink
    nose, big amber eyes with slit pupils, and whiskers. `peek` stops after the eyes (all
    that shows over the box's rim)."""
    hx, hy = _pt(c)
    f = facing

    def X(dx):
        return hx + dx * f

    dark = P.shade(fur, 0.72)
    inner = P.lighten(fur, 0.3)
    for base_a, base_b, tip, col, ins in (
            ((X(-r - 1), hy - r + 9), (X(-3), hy - r + 1), (X(-r + 1), hy - r - 13), dark, P.shade(inner, 0.75)),
            ((X(-5), hy - r + 1), (X(r - 1), hy - r + 7), (X(4), hy - r - 15), fur, inner)):
        pts = [_pt(base_a), _pt(tip), _pt(base_b)]
        pygame.draw.polygon(surf, P.INK, pts, 0)
        pygame.draw.lines(surf, P.INK, True, pts, 5)
        pygame.draw.polygon(surf, col, pts)
        mid = towards(base_a, base_b, 0.5)
        poly(surf, [towards(base_a, mid, 0.45), towards(tip, mid, 0.28), towards(base_b, mid, 0.45)], ins, ink=0)
    head = pygame.Rect(0, 0, 2 * r + 8, 2 * r - 2)
    head.center = (hx, hy)
    for tip, y0, y1 in (((X(-r - 9), hy + 3), hy - 3, hy + 6), ((X(-r - 6), hy + 11), hy + 4, hy + 12)):
        pts = [_pt((X(-r + 3), y0)), _pt(tip), _pt((X(-r + 5), y1))]
        pygame.draw.polygon(surf, P.INK, pts)
        pygame.draw.lines(surf, P.INK, True, pts, 5)
        pygame.draw.polygon(surf, fur, pts)
    pygame.draw.ellipse(surf, P.INK, head.inflate(4, 4))
    pygame.draw.ellipse(surf, fur, head)
    surf.fill(P.lighten(fur, 0.5), (X(-8) - (2 if f < 0 else 0), hy - r + 5, 3, 3))
    muz = pygame.Rect(0, 0, 22, 14)
    muz.center = (X(9), hy + 7)
    pygame.draw.ellipse(surf, light, muz)
    for ex, ew in ((X(0), 10), (X(13), 8)):
        eye = pygame.Rect(0, 0, ew, 12)
        eye.center = (ex, hy - 2)
        pygame.draw.ellipse(surf, P.INK, eye.inflate(4, 4))
        pygame.draw.ellipse(surf, EYE, eye)
        surf.fill(P.INK, (ex - 1 + (1 if f > 0 else 0), hy - 6, 2, 9))
        surf.fill(P.WHITE, (ex - 3 * f - (1 if f < 0 else 0), hy - 6, 2, 2))
    if peek:
        return
    nx, ny = X(16), hy + 4
    pygame.draw.polygon(surf, P.INK, [(nx - 5 * f, ny - 2), (nx + 2 * f, ny - 2), (nx - f, ny + 3)])
    pygame.draw.polygon(surf, NOSE, [(nx - 4 * f, ny - 1), (nx + 1 * f, ny - 1), (nx - f, ny + 1)])
    pygame.draw.line(surf, P.INK, (nx - f, ny + 3), (nx - f, ny + 5), 1)
    pygame.draw.lines(surf, P.INK, False, [(nx - 6 * f, ny + 6), (nx - 3 * f, ny + 7), (nx - f, ny + 5),
                                            (nx + 1 * f, ny + 7)], 1)
    for y0, dy in ((ny + 2, -3), (ny + 5, 1)):
        pygame.draw.line(surf, P.WHITE, (nx - 2 * f, y0), (nx + 11 * f, y0 + dy), 1)


def tail(surf, base, facing, fur, swish=0.0, scale=1.0, width=10):
    """A tail curling up from the hip: thick at the root, a paler tip curling forward."""
    s = scale
    bx, by = base
    pts = curve((bx, by), (bx - 26 * s * facing, by + 4 * s), (bx - (44 + swish) * s * facing, by - 26 * s),
                (bx - (30 + swish) * s * facing, by - 58 * s), 14)
    tip_curl = (pts[-1][0] + 8 * s * facing, pts[-1][1] - 5 * s)
    pts.append(tip_curl)
    n = len(pts) - 1
    widths = [max(6, round(width - i * 0.3)) for i in range(n)]
    colors = [fur] * (n - 3) + [P.lighten(fur, 0.45)] * 3
    chain(surf, pts, widths, colors)


def cat_leg_points(j, side, facing):
    """The cat leg over the skeleton's hip, knee and foot: the knee nudged forward, a hock
    added halfway down the knee-foot line and pushed well off it towards the back, so the leg
    reads thigh forward, long lower leg back to a high heel, the long foot down to the toes."""
    k, ft = j[f"knee_{side}"], j[f"foot_{side}"]
    dx, dy = ft[0] - k[0], ft[1] - k[1]
    n = math.hypot(dx, dy) or 1.0
    bx, by = -dy / n * facing, dx / n * facing
    knee = (k[0] - bx * n * 0.14, k[1] - by * n * 0.14)
    hk = (k[0] + dx * 0.52 + bx * n * 0.42, k[1] + dy * 0.52 + by * n * 0.42)
    return knee, hk


def toes(surf, p, facing, color):
    """Standing on the toe pads: a small round paw, toes forward, two creases."""
    r = pygame.Rect(0, 0, 15, 9)
    r.midbottom = _pt((p[0] + 3 * facing, p[1] + 5))
    pygame.draw.ellipse(surf, P.INK, r.inflate(4, 4))
    pygame.draw.ellipse(surf, color, r)
    tx = r.right - 4 if facing > 0 else r.left + 4
    for dx in (0, -4 * facing):
        pygame.draw.line(surf, P.shade(color, 0.6), (tx + dx, r.top + 3), (tx + dx, r.bottom - 2), 1)


def cat_leg(surf, j, side, facing, color, paw_color, w):
    """Haunch and thigh forward to the knee, the lower leg back to the hock, the long foot
    down to the toes. All its ink first, then its fill: one outline, no seams."""
    hip, foot_p = j["hip"], j[f"foot_{side}"]
    knee, hk = cat_leg_points(j, side, facing)
    toe = (foot_p[0], foot_p[1] - 2)
    segs = ((hip, knee, w + 6), (knee, hk, w - 1), (hk, toe, w - 5))
    for c, pad in ((P.INK, 4), (color, 0)):
        for a, b, ww in segs:
            a, b = _pt(a), _pt(b)
            pygame.draw.line(surf, c, a, b, ww + pad)
            pygame.draw.circle(surf, c, a, (ww + pad) // 2)
            pygame.draw.circle(surf, c, b, (ww + pad) // 2)
    toes(surf, foot_p, facing, paw_color)


def draw_erwin(surf, j, facing, fur, strike=None):
    """ERWIN at the joints `j` (poses.joints, build "cat"), in her basis colour `fur`.
    `strike` = (joint, colour) lights an attack's whole arm ("hand_f") or leg ("foot_f") in its
    colour, as on every fighter. Returns j."""
    light = P.lighten(fur, 0.55)                # belly, muzzle, paws: a pale shade of her fur
    dark = P.shade(fur, 0.68)
    at = frame(j, facing)
    w = LIMB_W["cat"]
    hip, neck, sh = j["hip"], j["neck"], j["shoulder_f"]
    # 1. the tail, behind everything
    tail(surf, at(hip, 6, -10), facing, fur)
    # 2. the back leg and arm, in shadow
    cat_leg(surf, j, "b", facing, P.shade(dark, 0.9), P.shade(light, 0.8), w)
    limb(surf, j["shoulder_b"], j["elbow_b"], w - 1, dark)
    limb(surf, j["elbow_b"], j["hand_b"], w - 2, dark)
    paw(surf, j["hand_b"], 6, P.shade(light, 0.8))
    # 3. the body: a soft pear, narrow at the shoulders, round at the belly
    rows = ((neck, 2, 8), (sh, 0, 11), (hip, 16, 15), (hip, 6, 15), (hip, -4, 12), (hip, -9, 5))
    front = [at(b, up, half) for b, up, half in rows]
    back = [at(b, up, -half) for b, up, half in reversed(rows)]
    blob(surf, front + back, fur)
    bib = [at(neck, 0, 2), at(sh, -2, 9), at(hip, 14, 13), at(hip, 2, 12), at(hip, -5, 6),
           at(hip, 2, 1), at(sh, -6, 1)]
    poly(surf, bib, light, ink=0)
    pygame.draw.circle(surf, P.lighten(fur, 0.35), _pt(at(sh, -1, -6)), 2)
    # 4. the front leg (lit when it kicks)
    lit = strike[1] if strike and strike[0] == "foot_f" else None
    cat_leg(surf, j, "f", facing, lit or fur, P.lighten(lit, 0.5) if lit else light, w)
    hx, hy = _pt(towards(hip, j["knee_f"], 0.25))
    pygame.draw.arc(surf, P.shade(lit or fur, 0.78), (hx - 9, hy - 9, 18, 18),
                    math.radians(60 if facing > 0 else 0), math.radians(180 if facing > 0 else 120), 2)
    # 5. the head
    cat_head(surf, j["head"], HEAD_R["cat"], facing, fur, light)
    # 6. the front arm, in front of everything
    arm = strike[1] if strike and strike[0] == "hand_f" else fur
    limb(surf, j["shoulder_f"], j["elbow_f"], w - 1, arm)
    limb(surf, j["elbow_f"], j["hand_f"], w - 2, arm)
    paw(surf, j["hand_f"], 7, light if arm is fur else P.lighten(arm, 0.5))
    return j


# --- THE BOX ---------------------------------------------------------------------------------


def box(surf, x, w, h, facing, fur, floor, peek=True, head_r=16):
    """A cardboard box on the floor, its flaps open; her ears and eyes peek over the rim.
    Drawn in 3/4: the front face, the side face going back, the open top (the look's)."""
    d = 10
    f = facing
    left, top = round(x - w / 2), floor - h + 4
    front = pygame.Rect(left, top, w, h)
    bl, br = (left + d, top - d), (left + w + d, top - d)
    poly(surf, [bl, (bl[0] + 4, bl[1] - 22), (br[0] - 4, br[1] - 22), br], CARD_DARK)
    poly(surf, [(left, top), bl, br, (left + w, top)], CARD_DEEP)
    if peek:
        hx = x + d / 2 + 2 * f
        layer = surf.subsurface(pygame.Rect(0, 0, surf.get_width(), top + 1))
        cat_head(layer, (hx, top - 7), head_r, facing, fur, P.lighten(fur, 0.55), peek=True)
    poly(surf, [(left + w, top), (left + w + d, top - d), (left + w + d, top - d + h), (left + w, top + h)], CARD_DARK)
    poly(surf, [(left + w, top), (left + w + d, top - d), (left + w + d + 17, top - d + 3), (left + w + 17, top + 3)],
         CARD_LIGHT)
    poly(surf, [front.topleft, front.topright, front.bottomright, front.bottomleft], CARD)
    surf.fill(CARD_LIGHT, (left + 3, top + 3, w - 6, 2))
    tx = left + w // 2
    surf.fill(TAPE, (tx - 4, top + 2, 8, 16))
    surf.fill(P.shade(TAPE, 0.85), (tx - 4, top + 16, 8, 2))
    poly(surf, [(left, top), (left - 14, top - 14), (left - 4, top - 18), (left + d, top - d)], CARD_LIGHT)
    poly(surf, [(left + 2, top), (left + w - 2, top), (left + w - 6, top + 12), (left + 6, top + 12)], CARD_LIGHT)
    surf.fill(TAPE, (tx - 4, top + 2, 8, 9))
    pygame.draw.line(surf, P.INK, (left + 6, top + 12), (left + w - 6, top + 12), 2)
    for ax in (left + 10, left + w - 18):
        ay = top + h - 14
        pygame.draw.polygon(surf, CARD_DEEP, [(ax + 4, ay - 5), (ax, ay), (ax + 8, ay)])
        surf.fill(CARD_DEEP, (ax + 3, ay, 2, 6))
    return front


def _layer() -> pygame.Surface:
    s = pygame.Surface((SPRITE_W, SPRITE_H))
    s.fill(KEY)
    s.set_colorkey(KEY)
    return s


def _anchor(facing: int) -> int:
    """Where a box's centre is across its sprite (the sprite is mirrored for facing left)."""
    return SPRITE_X if facing > 0 else SPRITE_W - 1 - SPRITE_X


def _flat_box(fur, facing: int, peek: bool = True) -> pygame.Surface:
    """The cardboard box (with her ears and eyes over the rim if `peek`), on its own sprite."""
    layer = _layer()
    box(layer, SPRITE_X, BOX_W, BOX_H, 1, fur, SPRITE_FLOOR, peek)
    if facing < 0:
        layer = pygame.transform.flip(layer, True, False)
    return layer


@lru_cache(maxsize=FADE_STEPS)
def _dither(fade_step: int) -> pygame.Surface:
    """An ordered dither, fade_step / FADE_STEPS of its pixels KEY (the rest see-through):
    blitted over a box sprite, it eats that much of it. The pattern repeats every 10 px."""
    tile = pygame.Surface((10, 10))
    tile.fill(OFF)
    tile.set_colorkey(OFF)
    for y in range(10):
        for x in range(10):
            if ((x * 7 + y * 13) % 10) / 10 < fade_step / FADE_STEPS:
                tile.set_at((x, y), KEY)
    s = pygame.Surface((SPRITE_W, SPRITE_H))
    s.fill(OFF)
    s.set_colorkey(OFF)
    for y in range(0, SPRITE_H, 10):
        for x in range(0, SPRITE_W, 10):
            s.blit(tile, (x, y))
    return s


@lru_cache(maxsize=64)
def holo_sprite(fur, facing: int, phase: int, fade_step: int = 0) -> tuple[pygame.Surface, pygame.Surface]:
    """A holographic box (the look's holo_box): the box recoloured into her basis colour with
    glowing edges, see-through, with scanline gaps and a few rows slipped sideways by `phase`;
    `fade_step` / FADE_STEPS of it dissolved. Returns (the box, the pale pool it stands in),
    both SPRITE_W x SPRITE_H, to blit at (x - _anchor(facing), floor - SPRITE_FLOOR)."""
    fade = fade_step / FADE_STEPS
    layer = _flat_box(fur, facing)
    glow = P.lighten(fur, 0.75)
    pa = pygame.PixelArray(layer)
    for src, dst in ((P.INK, glow), (CARD, fur), (CARD_LIGHT, P.lighten(fur, 0.3)), (CARD_DARK, P.shade(fur, 0.7)),
                     (CARD_DEEP, P.shade(fur, 0.4)), (TAPE, P.lighten(fur, 0.45)),
                     (P.shade(TAPE, 0.85), P.lighten(fur, 0.25)), (EYE, P.WHITE)):
        pa.replace(src, dst)
    del pa
    gaps = (fur, P.lighten(fur, 0.3), P.shade(fur, 0.7), P.shade(fur, 0.4), P.lighten(fur, 0.45),
            P.lighten(fur, 0.25), P.lighten(fur, 0.55))
    out = _layer()
    seed = phase * 3
    for y in range(SPRITE_H):
        if y % 3 == 0:                                 # a scanline gap: only the glowing edges
            row = layer.subsurface((0, y, SPRITE_W, 1)).copy()
            pa = pygame.PixelArray(row)
            for c in gaps:
                pa.replace(c, KEY)
            del pa
            row.set_colorkey(KEY)
            out.blit(row, (0, y))
            continue
        slip = 2 if (y // 2 + seed) % 9 == 0 else (-1 if (y + seed) % 13 == 0 else 0)
        out.blit(layer, (slip, y), (0, y, SPRITE_W, 1))
    if fade_step:
        out.blit(_dither(fade_step), (0, 0))
    pool = _layer()
    base = pygame.Rect(0, 0, BOX_W + 26, 12)
    base.center = (_anchor(facing) + 4 * facing, SPRITE_FLOOR + 2)
    pygame.draw.ellipse(pool, P.lighten(fur, 0.3), base, 2)
    pool.set_alpha(round(140 * (1 - fade)))
    out.set_alpha(round(215 * (1 - 0.5 * fade)))
    return out, pool


def draw_holo_box(surf, x, floor, facing, fur, phase, fade_step=0):
    """One holographic box standing on `floor` at x."""
    out, pool = holo_sprite(fur, facing, 0 if fade_step else phase % HOLO_PHASES, fade_step)
    pos = (round(x) - _anchor(facing), round(floor) - SPRITE_FLOOR)
    surf.blit(pool, pos)
    surf.blit(out, pos)


@lru_cache(maxsize=16)
def card_sprite(fur, facing: int) -> tuple[pygame.Surface, pygame.Surface]:
    """The real cardboard box she turned out to be in, and its white silhouette (the rim). No
    ears over its rim: in the game her real body is there, popping out of it."""
    card = _flat_box(fur, facing, peek=False)
    rim = pygame.mask.from_surface(card).to_surface(setcolor=(*P.WHITE, 255), unsetcolor=(0, 0, 0, 0))
    return card, rim


def dotted_arc(surf, a, b, peak, color):
    """A dashed arc from a to b, its top `peak` px above them: one cat, two places."""
    n = 28
    pts = []
    for i in range(n + 1):
        t = i / n
        pts.append((a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t - 4 * peak * t * (1 - t)))
    for i in range(0, n, 2):
        pygame.draw.line(surf, P.INK, _pt(pts[i]), _pt(pts[i + 1]), 5)
    for i in range(0, n, 2):
        pygame.draw.line(surf, color, _pt(pts[i]), _pt(pts[i + 1]), 2)


def star(surf, c, r, color):
    """A four-pointed glint: a thin cross that tapers to points."""
    x, y = _pt(c)
    for k in range(r):
        half = max(0, (r - k) // 3)
        surf.fill(color, (x - half, y - k, 2 * half + 1, 1))
        surf.fill(color, (x - half, y + k, 2 * half + 1, 1))
        surf.fill(color, (x - k, y - half, 1, 2 * half + 1))
        surf.fill(color, (x + k, y - half, 1, 2 * half + 1))


def draw_superposed(surf, boxes, floor, facing, fur, t):
    """THE BOX superposed: the two holographic boxes, each shimmering on its own beat, and the
    dashed arc between them."""
    a, b = boxes
    y = floor - BOX_H - 34
    dotted_arc(surf, (a + 5, y), (b + 5, y), 24 + abs(b - a) * 0.12, P.lighten(fur, 0.45))
    for i, x in enumerate(boxes):
        draw_holo_box(surf, x, floor, facing, fur, t // 3 + 2 * i)


def draw_collapse(surf, x, floor, facing, fur, age):
    """The collapse, `age` frames on: the box she is in is real cardboard, for its first
    FLASH_FRAMES in a white rim with rays bursting off it and two glints (the look's
    collapse_flash)."""
    card, rim = card_sprite(fur, facing)
    pos = (round(x) - _anchor(facing), round(floor) - SPRITE_FLOOR)
    if age < FLASH_FRAMES:
        for dx, dy in ((-2, 0), (2, 0), (0, -2), (0, 2), (-1, -1), (1, 1), (-1, 1), (1, -1)):
            surf.blit(rim, (pos[0] + dx, pos[1] + dy))
        cx, cy = x + 5 * facing, floor - BOX_H / 2 - 8
        for k in range(9):
            a = math.radians(-180 + k * 22.5)               # only upwards and sideways
            r0, r1 = 54, 74 + (k % 2) * 12
            p0 = (cx + math.cos(a) * r0, cy + math.sin(a) * r0 * 0.85)
            p1 = (cx + math.cos(a) * r1, cy + math.sin(a) * r1 * 0.85)
            pygame.draw.line(surf, P.INK, _pt(p0), _pt(p1), 6)
            pygame.draw.line(surf, P.WHITE if k % 2 else P.lighten(fur, 0.5), _pt(p0), _pt(p1), 3)
        star(surf, (x - (BOX_W / 2 + 4) * facing, floor - BOX_H - 10), 9, P.WHITE)
        star(surf, (x + (BOX_W / 2 + 16) * facing, floor - BOX_H - 22), 6, P.lighten(fur, 0.6))
    surf.blit(card, pos)
```

- [ ] **Step 5: Draw her in `render.py`.**
  - Imports: `from .erwin import EYE, FADE_STEPS, draw_collapse, draw_erwin, draw_holo_box, draw_superposed`.
  - `ACCENT` gets `"ERWIN": EYE`; remove the Task 1 stand-ins `"cat": 5` / `"cat": False` from `TORSO_EXTRA` / `PLATES`.
  - After `STRIKE_LIMB`: `SELF_LIT = ("cat",)   # builds that draw their own lit limb: the striker adds only its trail and tip`
  - `STRIKER` gets `"BOX SWIPE": "hand_f", "POUNCE": "hand_f", "SCRATCH": "hand_f",`
  - Effect lengths: `BOX_POP_FRAMES = 14   # THE BOX: the real cardboard box shows this long after a collapse` and `BOX_FADE_FRAMES = 16  # ... and the other one dissolves over this long`
  - `Effect` gets a last field `facing: int = 1`.
  - New module-level function after `tunnel_visibility`:

```python
def strike_of(f: Fighter) -> tuple[str, tuple] | None:
    """The joint an attack lands with and the colour its whole limb is lit in, from its
    wind-up to the end of its active frames (a throw, both colours, is lit green), or None."""
    m = f.move
    if f.action != "attack" or m is None or f.phase not in ("startup", "active"):
        return None
    joint = STRIKER.get(m.name)
    if joint is None:
        return None
    error = basis.error_for(m.colour, f.attack_basis)
    return joint, GREEN if error == basis.Y else ERROR_COLOUR[error]
```

  - `draw_puppet`'s signature and first lines become:

```python
def draw_puppet(surf: pygame.Surface, pose, build: str, feet, facing: int, body, accent,
                flare: float = 0.0, strike: tuple[str, tuple] | None = None, mood: str = "calm",
                led: bool = False, eject: bool = False) -> dict:
    """One fighter, back limbs first. Returns the joints (screen px). `flare` (px) blows a
    coat's hem out behind (PHOEBE's); `strike` = (joint, colour) is the lit limb, for a build
    that draws its own (SELF_LIT); `mood`, `led` and `eject` are DOS's screen (dos.py)."""
    j = joints(pose, build, feet, facing)
    if build == "cat":
        draw_erwin(surf, j, facing, body, strike)
        return j
```

  - In `_fighter`, right after the body-flash `if/elif`:

```python
        if f.boxed:                 # THE BOX: two holographic boxes, no body
            self.trails[key].clear()
            draw_superposed(self.surface, (f.boxes[0] + ox, f.boxes[1] + ox), FLOOR_Y + oy, f.facing, body, self.t)
            return f.boxes[0], FLOOR_Y - 60.0
```

    and the main `draw_puppet` call and the lines after it become:

```python
        j = draw_puppet(self.surface, pose, f.char.build, feet, f.facing, body, accent, flare, strike=strike_of(f))
        self._striker(key, f, j)
        if f.action == "attack" and m is not None and m.name == "SCRATCH" and f.phase == "active":
            self._claws(f, j)
```

  - `_striker` becomes:

```python
    def _striker(self, key: str, f: Fighter, j: dict) -> None:
        """The whole arm or leg an attack lands with is drawn in the attack's colour, from its
        wind-up to the end of its active frames, so a player sees before contact whether it
        will match; while it is live, its hand or foot leaves a fading trail. A throw (both
        colours) is green outlined in purple. CHARGE NOISE crackles instead. A SELF_LIT build
        drew its lit limb itself (ERWIN's cat leg): only the trail and the tip are added."""
        m = f.move
        trail = self.trails[key]
        if f.action != "attack" or m is None or f.phase not in ("startup", "active"):
            trail.clear()
            return
        if m.name == "CHARGE NOISE":
            trail.clear()
            self._charge_noise(f, m, j)
            return
        lit = strike_of(f)
        if lit is None:
            trail.clear()
            return
        joint, fill = lit
        edge = PURPLE if basis.error_for(m.colour, f.attack_basis) == basis.Y else P.INK
        surf = self.surface
        w = LIMB_W[f.char.build]
        if f.phase == "active":         # the trail, oldest first, under the limb
            trail.append((_pt(j[joint]), fill))
            del trail[:-TRAIL_LEN]
            for n, (p, c) in enumerate(trail[:-1]):
                r = 3 + n * 2
                pygame.draw.circle(surf, P.INK, p, r + 1)
                pygame.draw.circle(surf, P.lighten(c, 0.5), p, r)
        else:
            trail.clear()
        if f.char.build not in SELF_LIT:
            a, b, c = (j[name] for name in STRIKE_LIMB[joint])
            limb(surf, a, b, w, fill, ink=edge)
            limb(surf, b, c, w - 1, fill, ink=edge)
        tip = _pt(j[joint])
        r = w // 2 + (4 if f.phase == "active" else 2)
        pygame.draw.circle(surf, edge, tip, r + 2)
        pygame.draw.circle(surf, fill, tip, r)
        pygame.draw.circle(surf, P.lighten(fill, 0.5), (tip[0] - 2, tip[1] - 2), max(2, r // 3))
```

  - After `_laser_aim`:

```python
    def _claws(self, f: Fighter, j: dict) -> None:
        """SCRATCH: three white claw marks in front of her paw on the first frames of each swipe."""
        if (f.frame - f.startup) % f.move.hit_every >= 3:
            return
        hx, hy = j["hand_f"]
        for k in (-6, 0, 6):
            a = (hx + f.facing * 6, hy + k - 6)
            b = (hx + f.facing * 16, hy + k + 6)
            pygame.draw.line(self.surface, P.INK, _pt(a), _pt(b), 4)
            pygame.draw.line(self.surface, P.WHITE, _pt(a), _pt(b), 2)
```

  - `_shadow`, first line: `if f.boxed: return       # the boxes stand in pools of their own light`
  - `_start_effects`, a new branch:

```python
            elif e.kind == "box_collapse" and e.player and self._fight is not None:
                f = self._fight.fighters[e.player]
                fur = BASIS_BODY[f.basis]
                real, other = f.boxes[f.box_real], f.boxes[1 - f.box_real]
                self.effects.append(Effect("box_pop", real, FLOOR_Y, BOX_POP_FRAMES, BOX_POP_FRAMES, fur,
                                           facing=f.facing))
                self.effects.append(Effect("box_fade", other, FLOOR_Y, BOX_FADE_FRAMES, BOX_FADE_FRAMES, fur,
                                           facing=f.facing))
```

  - `_draw_effects`, two new branches:

```python
            elif world and fx.kind == "box_pop":     # the box she is in, real cardboard
                draw_collapse(surf, fx.x + ox, fx.y + oy, fx.facing, fx.color, age)
            elif world and fx.kind == "box_fade":    # the other one dissolving in a dither
                step = 1 + min(FADE_STEPS - 2, age * (FADE_STEPS - 1) // fx.life)
                draw_holo_box(surf, fx.x + ox, fx.y + oy, fx.facing, fx.color, 0, step)
```

  - `_boxes` (the debug overlay): for a boxed fighter draw both `f.box_rects()` instead of `f.hurtbox`.

- [ ] **Step 6: Run the new tests and the whole render file**

Run: `uv run pytest tests/test_render.py -q`
Expected: all pass. If `test_erwin_matches_her_approved_look` fails, diff the two surfaces
(`pygame.image.save` both to the scratch dir) and fix the port, never the test: the look is
the approved reference.

- [ ] **Step 7: ERWIN's snapshot frames.** In `tools/snapshot.py`, import `ERWIN`
(`from brawl_ket.moves import BOHR, ERWIN, ROBERT`), add to the docstring
`- moves_cat.png, erwin_*.png: ERWIN's moves; THE BOX superposed (green, then purple after a Y),
the collapse (0 and 3 frames on) and the swipe; a PHOTON measuring her; POUNCE and SCRATCH;`
and add:

```python
def erwin_frames(out_dir: str) -> None:
    """ERWIN against a ROBERT: THE BOX and its collapse, a measurement, POUNCE and SCRATCH."""
    from brawl_ket.fighter import IDLE, FighterInput

    surface = pygame.Surface((W, H))
    # THE BOX: split, switched to purple, then collapsed (seed 1: into box 1) with a swipe
    fight, r = Fight({"p1": ERWIN, "p2": ROBERT}, seed=1), Renderer(surface)
    presses = {0: FighterInput(x=True), 30: FighterInput(y=True), 60: FighterInput(a=True)}
    saves = {18: "erwin_box", 40: "erwin_box_purple", 60: "erwin_collapse_0", 63: "erwin_collapse_3",
             66: "erwin_swipe"}
    for i in range(70):
        r.draw_fight(fight, fight.step({"p1": presses.get(i, IDLE), "p2": IDLE}), {"p1": 0, "p2": 0})
        if i in saves:
            save(surface, out_dir, f"{saves[i]}.png")
    # a PHOTON into box 2 measures her
    fight, r, since = Fight({"p1": ERWIN, "p2": ROBERT}), Renderer(surface), None
    for i in range(120):
        events = fight.step({"p1": FighterInput(x=i == 0), "p2": FighterInput(x=i == 12)})
        r.draw_fight(fight, events, {"p1": 0, "p2": 0})
        if since is None and any(e.kind == "box_collapse" for e in events):
            since = 0
        elif since is not None:
            since += 1
        if since == 2:
            save(surface, out_dir, "erwin_measured.png")
            break
    # POUNCE on a crouching ROBERT, mid-leap
    fight, r = Fight({"p1": ERWIN, "p2": ROBERT}), Renderer(surface)
    fight.fighters["p2"].x = fight.fighters["p1"].x + 150
    for i in range(ERWIN.moves["crouch.X"].startup + 8):
        r.draw_fight(fight, fight.step({"p1": FighterInput(down=True, x=i == 0), "p2": FighterInput(down=True)}),
                     {"p1": 0, "p2": 0})
    save(surface, out_dir, "erwin_pounce.png")
    # SCRATCH from a short hop, on its first claw
    fight, r = Fight({"p1": ERWIN, "p2": ROBERT}), Renderer(surface)
    fight.fighters["p2"].x = fight.fighters["p1"].x + 44
    erwin = fight.fighters["p1"]
    for i in range(12):
        inp = FighterInput(up=True) if i == 0 else FighterInput(x=i == 1)
        r.draw_fight(fight, fight.step({"p1": inp, "p2": IDLE}), {"p1": 0, "p2": 0})
        if erwin.phase == "active":
            save(surface, out_dir, "erwin_scratch.png")
            break
```

and in `main`, after `save(move_sheet(BOHR), ...)`:

```python
    save(move_sheet(ERWIN), out_dir, "moves_cat.png")
    erwin_frames(out_dir)
```

Run: `uv run python tools/snapshot.py /tmp/brawl-snaps` (or the scratch dir).
Expected: the new PNGs are written. **Check them by eye** against the ERWIN look sheet
(`uv run python ../docs/superpowers/specs/2026-10-21-brawl-ket-erwin-look.py /tmp/erwin-look.png`):
the same cat, the two shimmering boxes with the dashed arc, the cardboard box in its white
flash, the dissolving box. Both look scripts must still run unchanged after the `ink.py`
move (they import `_ball`, `_block`, `_boot`, `_pt`, `limb` from `render`).

- [ ] **Step 8: Run the whole suite and the lint**

Run: `uv run pytest -q && uvx --from 'ruff==0.15.22' ruff check src tests tools`
Expected: all pass, `All checks passed!`.

- [ ] **Step 9: Commit**

```bash
git add src/brawl_ket/ink.py src/brawl_ket/erwin.py src/brawl_ket/render.py tools/snapshot.py tests/test_render.py
git commit -m "feat: :art: Brawl-Ket: ERWIN drawn as the approved cat, and THE BOX's holographic boxes

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---
### Task 3: DOS's rules

**Files:**
- Modify: `src/brawl_ket/config.py` (after `BOX_FRAMES`)
- Modify: `src/brawl_ket/moves.py` (`Move`, `Character`, after `ERWIN`, `CHARACTERS`)
- Modify: `src/brawl_ket/poses.py` (`POSES`, the `"dos"` build, `drawn_joints`)
- Modify: `src/brawl_ket/fighter.py`
- Modify: `src/brawl_ket/fight.py`
- Modify: `src/brawl_ket/render.py` (`TORSO_EXTRA`, `PLATES`: a stand-in until Task 4)
- Modify: `src/brawl_ket/audio.py` (`EVENT_SOUNDS`)
- Modify: `tools/snapshot.py` (`ACCENTS`)
- Create: `tests/test_dos.py`
- Modify: `tests/test_moves.py`, `tests/test_poses.py`, `tests/test_match.py`, `tests/test_bot.py`

**Interfaces:**
- Consumes (Task 1): `Fight(chars, seed)`, `Fighter.boxed`, `_Strike`, `Fight._touch`, `_measure`, `NORMALS`.
- Produces:
  - `config.DRIVE_SLOT_Y = 80`, `config.COPY_CAUGHT_RECOVERY = 6`
  - `Move.push_out: bool = False`, `Move.catch: Box | None = None`, `Move.paste: bool = False`
  - `Character.fixed_basis: str | None = None`, `Character.copy_paste: bool = False`, `Character.extra: Mapping[str, Move]` (default empty; DOS's keys `"copy"`, `"paste"`)
  - `moves.DOS` (build `"dos"`); `CHARACTERS` order ROBERT, BOHR, PHOEBE, ERWIN, DOS
  - poses `"eject"`, `"crash"`, `"stomp"`, `"copy"`; `SCALE["dos"] = 2.2`, `HEAD_R["dos"] = 15`, `LIMB_W["dos"] = 13`; `poses.CASE_TILT = 0.3`, `poses.LEAN_SCALE`, `poses.ARM_SOCKETS`; `poses.drawn_joints(pose, build, feet, facing) -> dict`
  - `Fighter.clipboard: tuple[Move, str] | None` (the caught shot's move and its absolute basis), `Fighter.caught(move: Move, shot_basis: str) -> None`, `Fighter.measured_into(b: str) -> bool`
  - fight event `"copy"` (`Event.x, y` where it was caught); move cues `"floppy"`, `"blue_screen"`, `"crt_drop"`, `"paste"`; the local `("projectile", {"move", "basis", "paste": True})` event for PASTE

- [ ] **Step 1: Write the failing tests** in `tests/test_dos.py`:

```python
"""DOS (docs/superpowers/specs/2026-10-21-brawl-ket-erwin-dos-design.md, sections 3 and 4): a
classical bit, always green, so Y never switches him and MEASURE never collapses him; his Y
is COPY (catch a rival's shot) and then PASTE (fire it back, straight ahead, in the colour it
was fired in); FLOPPY, BLUE SCREEN and CRT DROP."""

from brawl_ket import basis
from brawl_ket.basis import X_BASIS, Z_BASIS
from brawl_ket.config import COPY_CAUGHT_RECOVERY, DRIVE_SLOT_Y
from brawl_ket.fight import Fight, Shot, body_width
from brawl_ket.fighter import IDLE, FighterInput
from brawl_ket.moves import BOHR, DOS, ERWIN, PHOEBE, ROBERT

Y = FighterInput(y=True)
COPY, PASTE = DOS.extra["copy"], DOS.extra["paste"]
FLOPPY, BLUE, DROP = (DOS.moves[s] for s in ("stand.X", "crouch.X", "air.X"))
PHOTON, LASER = ROBERT.moves["stand.X"], PHOEBE.moves["air.X"]
TUNNEL = PHOEBE.moves["crouch.X"]
TUNNEL_STEPS = TUNNEL.startup + TUNNEL.active + TUNNEL.recovery


def versus(c1, c2, gap, seed=0):
    fight = Fight({"p1": c1, "p2": c2}, seed=seed)
    fight.fighters["p2"].x = fight.fighters["p1"].x + gap
    return fight


def step(fight, p1=IDLE, p2=IDLE):
    return fight.step({"p1": p1, "p2": p2})


def kinds(events):
    return [e.kind for e in events]


def hits_on(events, player):
    return [e for e in events if e.kind in ("hit", "block") and e.player == player]


# --- always green -------------------------------------------------------------------------------


def test_y_never_switches_dos():
    fight = versus(DOS, ROBERT, 300)
    dos = fight.fighters["p1"]
    events = []
    for i in range(60):
        events += step(fight, FighterInput(y=i % 10 == 0))
    assert dos.basis == Z_BASIS and "switch" not in kinds(events)
    dos.switch()                        # any colour-changing move does nothing to him either
    assert dos.basis == Z_BASIS


def test_measure_hurts_dos_but_never_collapses_him():
    fight = versus(BOHR, DOS, 80)
    bohr, dos = fight.fighters["p1"], fight.fighters["p2"]
    bohr.basis = X_BASIS                # BOHR purple: MEASURE would collapse anyone else into purple
    events = []
    for i in range(70):
        events += step(fight, FighterInput(x=i == 0))
    assert [(e.kind, e.error) for e in hits_on(events, "p2")] == [("hit", basis.Y)]
    assert dos.health == DOS.health - 12 and dos.basis == Z_BASIS and "measure" not in kinds(events)


# --- COPY ---------------------------------------------------------------------------------------


def test_copy_catches_a_photon_and_the_shot_is_gone():
    fight = versus(DOS, ROBERT, 300)
    dos = fight.fighters["p1"]
    shot = Shot("p2", PHOTON, dos.x + 70, 0.0, -PHOTON.projectile.speed, 200, X_BASIS)
    fight.shots.append(shot)
    events = []
    for i in range(10):
        events += step(fight, Y if i == 0 else IDLE)
    assert shot not in fight.shots and dos.clipboard == (PHOTON, X_BASIS)
    assert "copy" in kinds(events) and dos.health == DOS.health


def test_copy_catches_a_laser_falling_on_him():
    fight = versus(DOS, PHOEBE, 300)
    dos = fight.fighters["p1"]
    speed = LASER.projectile.speed
    fight.shots.append(Shot("p2", LASER, dos.x + 94, 74.0, -speed, 30, Z_BASIS, -speed))
    for i in range(6):
        step(fight, Y if i == 0 else IDLE)
    assert not fight.shots and dos.clipboard == (LASER, Z_BASIS) and dos.health == DOS.health


def test_dos_copies_a_floppy_and_keeps_its_green():
    fight = versus(DOS, DOS, 300)
    me = fight.fighters["p1"]
    fight.shots.append(Shot("p2", FLOPPY, me.x + 64, 0.0, -FLOPPY.projectile.speed, 240, Z_BASIS))
    for i in range(12):
        step(fight, Y if i == 0 else IDLE)
    assert me.clipboard == (FLOPPY, Z_BASIS)


def test_a_copy_that_catches_nothing_leaves_him_open():
    fight = versus(DOS, ROBERT, 300)
    dos = fight.fighters["p1"]
    step(fight, Y)
    frames = 1
    while dos.action == "attack":
        step(fight)
        frames += 1
    assert frames >= COPY.startup + COPY.active + COPY.recovery
    assert COPY.active == 12 and COPY.recovery == 18          # 0.2 s to catch, 0.3 s to recover


def test_a_catch_cuts_his_recovery_short():
    fight = versus(DOS, ROBERT, 300)
    dos = fight.fighters["p1"]
    fight.shots.append(Shot("p2", PHOTON, dos.x + 70, 0.0, -PHOTON.projectile.speed, 200))
    after = None
    for i in range(40):
        events = step(fight, Y if i == 0 else IDLE)
        if after is None and "copy" in kinds(events):
            after = 0
        elif after is not None:
            after += 1
        if after is not None and dos.action != "attack":
            break
    assert after is not None and after <= COPY_CAUGHT_RECOVERY


def test_copy_cannot_start_in_hitstun_or_knocked_down():
    fight = versus(DOS, ROBERT, 300)
    dos = fight.fighters["p1"]
    dos.take_hit(ROBERT.moves["stand.B"], basis.X, -1)
    assert dos.action == "hitstun"
    step(fight, Y)
    assert dos.move is None and dos.action == "hitstun"
    dos.take_hit(ROBERT.moves["crouch.B"], basis.X, -1)
    assert dos.action == "knockdown"
    step(fight, Y)
    assert dos.move is None


# --- PASTE --------------------------------------------------------------------------------------


def test_paste_fires_the_shot_straight_ahead_in_its_own_colour_and_empties_the_clipboard():
    fight = versus(DOS, ROBERT, 300)
    dos = fight.fighters["p1"]
    dos.clipboard = (LASER, X_BASIS)            # a purple LASER, caught from above
    events = []
    for i in range(PASTE.startup + 2):
        events += step(fight, Y if i == 0 else IDLE)
    (shot,) = fight.shots
    assert shot.owner == "p1" and shot.move is LASER and shot.basis == X_BASIS
    assert shot.vx == LASER.projectile.speed and shot.vy == 0.0           # level now
    assert shot.y + LASER.projectile.box.y == DRIVE_SLOT_Y and dos.clipboard is None
    assert "paste" in kinds(events)


def test_a_pasted_shot_keeps_the_colour_it_was_fired_in():
    for rival_basis, want in ((X_BASIS, "hit"), (Z_BASIS, "block")):
        fight = versus(DOS, ROBERT, 200)
        dos, rival = fight.fighters["p1"], fight.fighters["p2"]
        rival.basis = rival_basis
        dos.clipboard = (PHOTON, X_BASIS)       # purple: it hurts a purple ROBERT, not a green one
        events = []
        for i in range(80):
            events += step(fight, Y if i == 0 else IDLE)
        assert kinds(hits_on(events, "p2")) == [want], rival_basis


def test_a_pasted_shot_into_a_box_measures_erwin():
    fight = Fight({"p1": DOS, "p2": ERWIN})
    dos, erwin = fight.fighters["p1"], fight.fighters["p2"]
    step(fight, IDLE, FighterInput(x=True))
    for _ in range(ERWIN.moves["stand.X"].startup):
        step(fight)
    assert erwin.boxed
    dos.clipboard = (PHOTON, Z_BASIS)
    events = []
    for i in range(60):
        events += step(fight, Y if i == 0 else IDLE)
        if not erwin.boxed:
            break
    assert kinds(events).count("box_collapse") == 1


# --- FLOPPY, BLUE SCREEN, CRT DROP ---------------------------------------------------------------


def test_floppy_leaves_his_drive_slot_at_3_px_a_frame():
    fight = versus(DOS, ROBERT, 300)
    for i in range(FLOPPY.startup + 1):
        step(fight, FighterInput(x=i == 0))
    (shot,) = fight.shots
    x = shot.x
    step(fight)
    assert shot.x - x == 3.0 and shot.y + FLOPPY.projectile.box.y == DRIVE_SLOT_Y and shot.basis == Z_BASIS


def test_blue_screen_cannot_be_ducked():
    fight = versus(DOS, ROBERT, 60)
    events = []
    for i in range(BLUE.startup + 2):
        events += step(fight, FighterInput(down=True, x=i == 0), FighterInput(down=True))
    assert kinds(hits_on(events, "p2")) == ["hit"]


def test_blue_screen_pushes_a_rival_behind_him_away_too():
    fight = versus(DOS, ROBERT, 100)
    dos, rival = fight.fighters["p1"], fight.fighters["p2"]
    events = step(fight, FighterInput(down=True, x=True))
    rival.x = dos.x - 60                    # crossed behind him during the wind-up
    for _ in range(BLUE.startup + 2):
        events += step(fight)
    assert kinds(hits_on(events, "p2")) == ["hit"] and rival.vx < 0


def test_blue_screen_misses_a_rival_high_in_a_jump():
    fight = versus(DOS, ROBERT, 60)
    rival = fight.fighters["p2"]
    rival.y, rival.vy, rival.action = 130.0, 6.0, "jump"
    events = []
    for i in range(BLUE.startup + BLUE.active):
        events += step(fight, FighterInput(down=True, x=i == 0))
    assert hits_on(events, "p2") == []


def test_crt_drop_stomps_straight_down_and_knocks_down():
    fight = versus(DOS, ROBERT, 200)
    dos, rival = fight.fighters["p1"], fight.fighters["p2"]
    events = step(fight, FighterInput(up=True))
    for _ in range(8):
        events += step(fight)
    rival.x = dos.x + 20                    # walked in under him
    events += step(fight, FighterInput(x=True))
    x0 = dos.x
    for _ in range(40):
        events += step(fight)
        if dos.action == "attack" and dos.phase == "active" and not dos.bounced:
            assert dos.x == x0
    assert kinds(hits_on(events, "p2")) == ["hit"] and rival.action == "knockdown"
    assert "shockwave" not in kinds(events) and "crt_drop" in kinds(events)


def test_a_missed_crt_drop_lands_into_its_recovery():
    fight = versus(DOS, ROBERT, 300)
    dos = fight.fighters["p1"]
    step(fight, FighterInput(up=True))
    for _ in range(8):
        step(fight)
    step(fight, FighterInput(x=True))
    while dos.y > 0:
        step(fight)
    stuck = 0
    while dos.action == "attack":
        step(fight)
        stuck += 1
    assert DROP.recovery - 1 <= stuck <= DROP.recovery


def test_tunnel_past_dos_re_forms_clear_of_his_case():
    fight = versus(PHOEBE, DOS, 100)
    phoebe, dos = fight.fighters["p1"], fight.fighters["p2"]
    step(fight, FighterInput(down=True, x=True))
    for _ in range(TUNNEL_STEPS):
        step(fight, FighterInput(down=True))
    assert phoebe.x - dos.x == body_width(PHOEBE, DOS) == 54
```

- [ ] **Step 2: Run them to make sure they fail**

Run: `uv run pytest tests/test_dos.py -q`
Expected: collection error, `ImportError: cannot import name 'COPY_CAUGHT_RECOVERY'`.

- [ ] **Step 3: Config.** In `src/brawl_ket/config.py`, after `BOX_FRAMES`:

```python
DRIVE_SLOT_Y = 80        # DOS: FLOPPY and a PASTE leave his drive slot this high above his feet, px
COPY_CAUGHT_RECOVERY = 6  # ... and a COPY that catches a shot recovers in this many frames (a miss: all 18)
```

- [ ] **Step 4: Move and character data.** In `src/brawl_ket/moves.py`:

`from dataclasses import dataclass, field`; `from .basis import BOTH, OPPOSITE, OWN, Z_BASIS`;
`from .config import DRIVE_SLOT_Y` (beside `from . import config`).

Three more `Move` fields, after `leap`:

```python
    push_out: bool = False              # the hit pushes the rival away from the attacker, either side (BLUE SCREEN)
    catch: Box | None = None            # COPY: the window that catches a rival's shot (fight.py, _catch_shots)
    paste: bool = False                 # PASTE: fires the clipboard's shot on its first active frame
```

Three more `Character` fields, after `moves`:

```python
    fixed_basis: str | None = None      # DOS: always this basis; Y and MEASURE never change it
    copy_paste: bool = False            # DOS: Y is COPY / PASTE (`extra`), not a switch
    extra: Mapping[str, Move] = field(default_factory=lambda: MappingProxyType({}))   # moves outside SLOTS
```

After `ERWIN`:

```python
DOS = Character(
    name="DOS",
    build="dos",
    health=125,                         # the most: big and slow
    walk=1.6,
    jump_vy=10.0,
    gravity=0.55,                       # an apex of about 91 px: the lowest
    hurt_stand=Box(-24, 0, 48, 140),    # the case: 54 px wide, its top 144 px up
    hurt_crouch=Box(-26, 0, 52, 112),
    fixed_basis=Z_BASIS,                # a classical bit: always green
    copy_paste=True,
    moves=MappingProxyType({
        # BOHR's frame numbers, but slower jabs (8, not 6: with 125 health, 6 made him too strong);
        # the boxes fit his fists, which come out of the case's sides
        "stand.A": Move(
            "jab", 8, 3, 10, Box(20, 58, 50, 16), OWN, HIGH,
            damage=4, hitstun=17, knockback=1.0, lunge=1.5,
            cancels=("stand.A", "stand.B"),
            poses=("jab_wind", "jab_hit", "jab_wind"),
        ),
        "stand.B": Move(
            "heavy", 13, 5, 20, Box(20, 60, 54, 22), OPPOSITE, HIGH,
            damage=8, hitstun=22, knockback=6.0, chain_startup=9, lunge=3.0,
            poses=("heavy_wind", "heavy_hit", "heavy_recover"),
        ),
        "crouch.A": Move(
            "low jab", 8, 3, 11, Box(18, 20, 48, 14), OWN, LOW,
            damage=4, hitstun=16, knockback=1.0, lunge=1.5,
            cancels=("crouch.A", "crouch.B"),
            poses=("low_wind", "low_hit", "low_wind"),
        ),
        "crouch.B": Move(
            "sweep", 13, 4, 22, Box(14, 6, 62, 14), OPPOSITE, LOW,
            damage=8, hitstun=24, knockback=2.5, knockdown=True, chain_startup=9, lunge=3.0,
            poses=("sweep_wind", "sweep_hit", "crouch"),
        ),
        "air.A": Move(
            "air jab", 5, 6, 5, Box(16, 34, 44, 20), OWN, MID,
            damage=4, hitstun=15, knockback=1.5,
            poses=("jump", "air_jab", "jump"),
        ),
        "air.B": Move(
            "jump-in", 8, 6, 8, Box(10, 16, 40, 26), OPPOSITE, MID,
            damage=8, hitstun=20, knockback=3.0,
            poses=("jump", "air_kick", "jump"),
        ),
        "throw": Move(
            "throw", 6, 2, 24, Box(0, 40, 56, 70), BOTH, MID,     # 56: it must reach past his broad push box
            damage=10, hitstun=30, knockback=6.0, knockdown=True,
            kind="throw",
            poses=("throw_reach", "throw_hold", "idle"),
        ),
        # A spinning 3.5" disk out of his drive slot: slower than PHOTON, HIGH like it.
        "stand.X": Move(
            "FLOPPY", 14, 1, 22, None, OWN, HIGH,
            damage=9, hitstun=18, knockback=3.0,
            kind="projectile", cooldown=config.frames(2.5), cue="floppy",
            projectile=Projectile(3.0, Box(0, DRIVE_SLOT_Y, 18, 18), 240),
            poses=("cast_wind", "eject", "eject"),
        ),
        # His screen crashes blue and a shockwave rings out 50 px past his case on either side:
        # MID (no ducking it), 110 px tall (high in a jump clears it), a long stun, and the rival
        # pushed away whichever side they are on. His "get off me" move.
        "crouch.X": Move(
            "BLUE SCREEN", 10, 6, 24, Box(-74, 0, 148, 110), OWN, MID,
            damage=6, hitstun=config.frames(0.6), knockback=5.0, push_out=True,
            kind="special", cooldown=config.frames(3.0), cue="blue_screen",
            poses=("crouch", "crash", "crouch"),
        ),
        # A fast stomp straight down; no shockwave. A miss lands into its long recovery.
        "air.X": Move(
            "CRT DROP", 4, 60, 20, Box(-24, 0, 48, 40), OWN, MID,
            damage=12, hitstun=20, knockback=3.0, knockdown=True,
            kind="special", dive=(0.0, 14.0), cue="crt_drop",
            poses=("jump", "stomp", "crouch"),
        ),
    }),
    extra=MappingProxyType({
        # Y with an empty clipboard: a CTRL+C window in front of him for 0.2 s; a rival's shot
        # that meets it is caught (fight.py). A miss leaves him 0.3 s of recovery.
        "copy": Move(
            "COPY", 2, 12, 18, None, OWN, MID,
            damage=0, hitstun=1, knockback=0.0, kind="special", catch=Box(14, 20, 40, 110),
            poses=("copy", "copy", "idle"),
        ),
        # Y with a shot in the clipboard: fired straight ahead from his drive slot, at its own
        # speed, in the colour it was fired in.
        "paste": Move(
            "PASTE", 6, 1, 12, None, OWN, HIGH,
            damage=0, hitstun=1, knockback=0.0, kind="special", paste=True, cue="paste",
            poses=("cast_wind", "eject", "eject"),
        ),
    }),
)

CHARACTERS: dict[str, Character] = {"ROBERT": ROBERT, "BOHR": BOHR, "PHOEBE": PHOEBE, "ERWIN": ERWIN, "DOS": DOS}
```

(`config.frames(0.6)` is 36.) The `Character.build` comment becomes `# "lean" / "heavy" / "toy" / "cat" / "dos" (poses scale)`.

- [ ] **Step 5: His build, poses and `drawn_joints`.** In `src/brawl_ket/poses.py`:
`from dataclasses import dataclass, fields, replace`. Append to `POSES`:

```python
    # DOS's stand.X FLOPPY (and PASTE): braced, the front fist raised and the back one flung
    # back, out of the drive slot's way (the look's EJECT)
    "eject": Pose(-6, 30, -4, -26, -14, 150, 175, -60, -20),
    # DOS's crouch.X BLUE SCREEN: the crash, arms flung straight out
    "crash": Pose(-4, 32, -6, -32, -10, 95, 105, -95, -105),
    # DOS's air.X CRT DROP: feet together straight down, arms up
    "stomp": Pose(0, 8, 0, -8, 0, 130, 160, -130, -160),
    # DOS's COPY: both fists up in front of the case, holding up the CTRL+C frame
    "copy": Pose(4, 26, -4, -24, -12, 105, 120, 95, 115),
```

The build (the look's numbers, plus a short neck so his "head" joint is the top of his case:
nothing is drawn at it):

```python
    # DOS: a tall case on short legs, stubby arms; his "head" joint is the top of the case
    "dos": {"torso": 33, "shoulder": 15, "thigh": 14, "shin": 15, "upper_arm": 10, "forearm": 10, "neck": 4.5},
```

`SCALE` gets `"dos": 2.2`, `HEAD_R` `"dos": 15`, `LIMB_W` `"dos": 13`. After `LIMB_W`:

```python
CASE_TILT = 0.3         # DOS's case leans only this much of a pose's lean: the legs do the work
LEAN_SCALE = {"dos": CASE_TILT}
# DOS's arms come out of the case's sides, under the screen: each arm's joints move `front` px
# across the body (towards the face) and `down` px down the screen (the look's numbers)
ARM_SOCKETS = {"dos": {"f": (27.0, 0.0), "b": (-25.0, -4.0)}}
```

and after `joints`:

```python
def drawn_joints(pose: Pose, build: str, feet: tuple[float, float], facing: int) -> dict[str, tuple[float, float]]:
    """joints() as the build is drawn, and as its hit- and hurtboxes are fitted. DOS: the case
    leans only CASE_TILT of the pose's lean and his arms come out of the case's sides
    (ARM_SOCKETS). Every other build: joints() itself."""
    if build in LEAN_SCALE:
        pose = replace(pose, lean=pose.lean * LEAN_SCALE[build])
    j = joints(pose, build, feet, facing)
    sockets = ARM_SOCKETS.get(build)
    if sockets:
        hip, neck = j["hip"], j["neck"]
        tx, ty = neck[0] - hip[0], neck[1] - hip[1]
        n = math.hypot(tx, ty) or 1.0
        ux, uy = tx / n, ty / n
        fx, fy = -uy * facing, ux * facing
        for side, (front, down) in sockets.items():
            for name in ("shoulder", "elbow", "hand"):
                x, y = j[f"{name}_{side}"]
                j[f"{name}_{side}"] = (x + fx * front, y + fy * front + down)
    return j
```

- [ ] **Step 6: Fixed basis and COPY / PASTE in `src/brawl_ket/fighter.py`.**
Import `COPY_CAUGHT_RECOVERY` from `.config`. In `__init__`:

```python
        self.basis = char.fixed_basis or basis.Z_BASIS      # green: |0>, |1> (DOS: for good)
        ...
        self.clipboard: tuple[Move, str] | None = None      # DOS: the shot COPY caught, and its basis
```

In `step`, the switch condition becomes:

```python
        if not self.char.copy_paste and (inp.y or self.switch_pending):
```

`buffer_presses`:

```python
        buttons = ("a", "b", "x", "y") if self.char.copy_paste else ("a", "b", "x")   # DOS: Y is a move
        for btn in buttons:
            if getattr(inp, btn):
                self.buffer.append(Press(btn, 0))
```

`hold_switch`: `if inp.y and not self.char.copy_paste:`

`switch`:

```python
    def switch(self) -> None:
        """An H on yourself: the basis (and so the body's colour) swaps at once. A fixed basis
        (DOS: a classical bit can't be in superposition) never changes."""
        if self.char.fixed_basis is not None:
            return
        self.basis = basis.hadamard(self.basis)

    def measured_into(self, b: str) -> bool:
        """MEASURE projects this fighter onto basis b; True if that changed it. A fixed basis
        never changes."""
        if self.char.fixed_basis is not None or self.basis == b:
            return False
        self.basis = b
        return True

    def caught(self, move: Move, shot_basis: str) -> None:
        """COPY caught a shot: it goes into the clipboard (with the basis it was fired in), and
        the recovery is cut to COPY_CAUGHT_RECOVERY frames."""
        m = self.move
        assert m is not None
        self.clipboard = (move, shot_basis)
        self.frame = max(self.frame, self.startup + m.active + m.recovery - COPY_CAUGHT_RECOVERY)
```

`_move_effects`, inside `if self.frame == self.startup:` after the projectile line:

```python
                if m.paste and self.clipboard is not None:
                    shot, shot_basis = self.clipboard
                    self.clipboard = None
                    events.append(("projectile", {"move": shot, "basis": shot_basis, "paste": True}))
```

`_try_buffer`'s loop head becomes:

```python
        for entry in reversed(self.buffer):
            if entry.button == "y":     # DOS: COPY, or PASTE with a shot in the clipboard; free, on the ground
                if not free or self.y > 0:
                    continue
                slot = "paste" if self.clipboard is not None else "copy"
                move = self.char.extra.get(slot)
            else:
                slot = self._slot_for(entry.button, dx, rival_x)
                move = self.char.moves.get(slot)
            if move is None or self.cooldowns.get(slot, 0) > 0 or slot in self.air_used:
                continue
```

`_start_move`, after the `if move.tunnel:` block:

```python
        if move.catch is not None or move.paste:
            self.crouching = False      # COPY and PASTE stand him up
```

`_tunnel_target` uses the push box when it is wider than `TUNNEL_PAST` (DOS):

```python
    def _tunnel_target(self) -> float:
        """TUNNEL_PAST px past the rival (or the push box, if that is wider: DOS's case), on
        their far side; if the stage has no room there (the rival in a corner), as far in front
        of them, on her own side."""
        past = max(TUNNEL_PAST, self.body_width)
        side = 1 if self.rival_x > self.x else -1 if self.rival_x < self.x else self.facing
        far = min(max(self.rival_x + side * past, STAGE_LEFT), STAGE_RIGHT)
        if (far - self.rival_x) * side >= self.body_width:
            return far
        return min(max(self.rival_x - side * past, STAGE_LEFT), STAGE_RIGHT)
```

- [ ] **Step 7: The catch, PASTE's shot, `push_out` and MEASURE in `src/brawl_ket/fight.py`.**
Import `DRIVE_SLOT_Y` from `.config`. In `step`, after `self._move_shots(events)`:

```python
        self._catch_shots(events)
```

In `_step_fighters`, the projectile branch becomes:

```python
                if kind == "projectile":
                    move = data["move"]
                    proj = move.projectile
                    assert proj is not None
                    if data.get("paste"):   # PASTE: level, from his drive slot, in the colour it was fired in
                        y, vy, shot_basis = f.y + DRIVE_SLOT_Y - proj.box.y, 0.0, data["basis"]
                    else:
                        y, vy, shot_basis = f.y, proj.vy, f.attack_basis
                    self.shots.append(Shot(
                        key, move, f.x + f.facing * SHOT_SPAWN_OFFSET, y,
                        proj.speed * f.facing, proj.lifetime, shot_basis, vy,
                    ))
                    events.append(Event("projectile", key))
```

New method after `_off_stage`:

```python
    def _catch_shots(self, events: list[Event]) -> None:
        """COPY: a rival's shot that meets the catch window while it is open is caught, before
        it can hit him: gone from the stage and into his clipboard."""
        for key, f in self.fighters.items():
            m = f.move
            if f.action != "attack" or m is None or m.catch is None or f.phase != "active":
                continue
            window = f.world_box(m.catch)
            for s in self.shots:
                where = _overlap(s.box, window) if s.owner != key else None
                if where is not None:
                    self.shots.remove(s)
                    f.caught(s.move, s.basis)
                    events.append(Event("copy", key, None, *where))
                    break
```

In `_move_strike`, the strike becomes:

```python
        touch = self._touch(f.world_box(m.hitbox), rival)
        if touch is not None:
            where, box = touch
            facing = f.facing
            if m.push_out:      # BLUE SCREEN: away from him, whichever side the rival is on
                facing = 1 if where[0] >= f.x else -1
            strikes.append(_Strike(key, key, rival_key, m, facing, where, box=box))
```

In `_apply_strike`, the MEASURE block becomes:

```python
        if m.measure_rival and defender.measured_into(owner.basis):
            # MEASURE projects the rival onto BOHR's basis (never DOS: a classical bit)
            events.append(Event("measure", st.defender, None, x, y))
```

- [ ] **Step 8: Keep the rest running with a fifth fighter.**
  - `render.py`: `TORSO_EXTRA` gets `"dos": 8`, `PLATES` `"dos": True` (BOHR's armour on his skeleton until Task 4).
  - `audio.py`: `EVENT_SOUNDS` gets `"copy": None,`.
  - `tools/snapshot.py`: `ACCENTS` gets `"dos": P.CREAM`.

- [ ] **Step 9: Run DOS's tests**

Run: `uv run pytest tests/test_dos.py -q`
Expected: all pass.

- [ ] **Step 10: The cross-cutting tests, with DOS.**

`tests/test_moves.py`:
- import `DOS`; `from brawl_ket.basis import BOTH, OPPOSITE, OWN, Z_BASIS`
- `STARTUPS` gets `"DOS": (8, 13, 9),`
- `SPECIAL_DAMAGE` gets `"FLOPPY": 9, "BLUE SCREEN": 6, "CRT DROP": 12`
- `test_health`'s dict gets `"DOS": 125`
- `SPECIALS` gets

```python
    ("DOS", "stand.X"): (OWN, HIGH, ()),
    ("DOS", "crouch.X"): (OWN, MID, ("push_out",)),
    ("DOS", "air.X"): (OWN, MID, ()),
```

  `TWISTS` gets `"push_out"` at the end, and the names dict `"DOS": ["FLOPPY", "BLUE SCREEN", "CRT DROP"]`.
- `test_the_crouch_hurtbox_covers_the_drawn_crouch` uses `drawn_joints` instead of `joints`
  (`from brawl_ket.poses import POSES, drawn_joints`).
- new tests at the end:

```python
# --- DOS -------------------------------------------------------------------------------------


def test_dos_stats():
    d = CHARACTERS["DOS"]
    assert (d.build, d.health, d.walk, d.jump_vy, d.gravity) == ("dos", 125, 1.6, 10.0, 0.55)
    others = [c for c in CHARACTERS.values() if c is not d]
    assert apex(d) < min(apex(c) for c in others) and d.health > max(c.health for c in others)
    assert d.fixed_basis == Z_BASIS and d.copy_paste and set(d.extra) == {"copy", "paste"}
    assert all(not c.copy_paste and c.fixed_basis is None for c in others)


def test_dos_specials():
    floppy, screen, drop = (DOS.moves[s] for s in ("stand.X", "crouch.X", "air.X"))
    assert (floppy.damage, floppy.kind, floppy.cooldown) == (9, "projectile", config.frames(2.5))
    assert floppy.projectile.speed == 3.0 < ROBERT.moves["stand.X"].projectile.speed
    assert (screen.damage, screen.height, screen.hitstun, screen.cooldown) == (6, MID, config.frames(0.6),
                                                                              config.frames(3.0))
    half = DOS.hurt_stand.w / 2
    assert screen.push_out and screen.hitbox.x == -(half + 50) and screen.hitbox.x + screen.hitbox.w == half + 50
    assert (drop.damage, drop.height, drop.knockdown, drop.dive[0]) == (12, MID, True, 0.0)
    assert drop.landing is None and 18 <= drop.recovery <= 22


def test_copy_and_paste_numbers():
    copy, paste = DOS.extra["copy"], DOS.extra["paste"]
    assert copy.catch is not None and copy.active == config.frames(0.2) and copy.recovery == config.frames(0.3)
    assert paste.paste and paste.startup <= 6 and paste.recovery <= 12
```

`tests/test_poses.py`:
- import `drawn_joints` (and `POSE_NAMES` is already imported); the test-local `STRIKER`
  gets `"BLUE SCREEN": "hand_f", "CRT DROP": "foot_f",`
- `test_the_striking_limb_reaches_the_hitbox_on_impact` uses
  `j = drawn_joints(pose_for(f), c.build, FEET, 1)`
- new test:

```python
def test_dos_leans_only_a_little_and_his_arms_come_out_of_the_case():
    from brawl_ket.poses import CASE_TILT
    pose = POSES["crouch"]
    j = drawn_joints(pose, "dos", FEET, 1)
    tilt = math.degrees(math.atan2(j["neck"][0] - j["hip"][0], j["hip"][1] - j["neck"][1]))
    assert tilt == pytest.approx(pose.lean * CASE_TILT)
    idle, plain = drawn_joints(POSES["idle"], "dos", FEET, 1), joints(POSES["idle"], "dos", FEET, 1)
    assert idle["foot_f"] == plain["foot_f"] and idle["hand_f"][0] > plain["hand_f"][0] + 20
    for name in POSE_NAMES:                 # every other build is drawn on joints() itself
        assert drawn_joints(POSES[name], "lean", FEET, 1) == joints(POSES[name], "lean", FEET, 1)
```

`tests/test_match.py` (uses its helpers `to_fight` and `ko`):

```python
def test_dos_starts_every_round_with_an_empty_clipboard() -> None:
    from brawl_ket.moves import DOS
    m = Match(random.Random(1))
    to_fight(m, p1=4)
    dos = m.fight.fighters["p1"]
    assert dos.char is DOS and dos.clipboard is None
    dos.clipboard = (ROBERT.moves["stand.X"], "Z")
    ko(m, "p2")
    assert m.state == ROUND_INTRO and m.fight.fighters["p1"].clipboard is None
```

`tests/test_bot.py`, `test_bots_land_hits_in_both_colours`: two DOS can only ever hurt each
other green, so its assertion becomes:

```python
    fixed = all(CHARACTERS[name].fixed_basis for name in pairing)
    assert ({"X"} if fixed else {"X", "Z"}) <= errors, (pairing, errors)       # both colours land (DOS: green)
```

- [ ] **Step 11: Run the whole suite and the lint**

Run: `uv run pytest -q && uvx --from 'ruff==0.15.22' ruff check src tests tools`
Expected: all pass, `All checks passed!`. The same `test_neither_side_is_favoured` fallback
as in Task 1 Step 12 applies to a pairing with DOS (`reason="DOS's bot: Task 6"`).

- [ ] **Step 12: Commit**

```bash
git add src/brawl_ket/config.py src/brawl_ket/moves.py src/brawl_ket/poses.py src/brawl_ket/fighter.py \
  src/brawl_ket/fight.py src/brawl_ket/render.py src/brawl_ket/audio.py tools/snapshot.py \
  tests/test_dos.py tests/test_moves.py tests/test_poses.py tests/test_match.py tests/test_bot.py
git commit -m "feat: :floppy_disk: Brawl-Ket: DOS's rules (always green, COPY / PASTE, FLOPPY, BLUE SCREEN, CRT DROP)

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---
### Task 4: DOS drawn as the approved all-in-one, with his disk, his specials and his clipboard

**Files:**
- Create: `src/brawl_ket/dos.py`
- Modify: `src/brawl_ket/render.py`
- Modify: `tools/snapshot.py`
- Modify: `tests/test_render.py`

**Interfaces:**
- Consumes (Tasks 1-3): `ink.frame`, `ink.poly`, `ink._towards`, `ink._ball`, `ink._block`,
  `ink._boot`, `ink._pt`, `ink.limb`; `poses.drawn_joints`, `LIMB_W["dos"]`; `DOS`,
  `Move.catch`, `Move.paste`, `Fighter.clipboard`, `config.DRIVE_SLOT_Y`; the `look` fixture,
  `same_pixels`, `BLANK`, `bot_frames`, `body_pixels` in `tests/test_render.py`;
  `render.draw_puppet(..., strike, mood, led, eject)`, `render.SELF_LIT`, `render.strike_of`.
- Produces:
  - `dos.BEIGE`, `dos.GLASS`, `dos.SCAN`, `dos.PHOSPHOR`, `dos.STEEL`, `dos.BSOD`, `dos.ANGLE_STEP`, `dos.CLIP_W`, `dos.CLIP_H`
  - `dos.draw_dos(surf, j: dict, facing: int, case: tuple, strike=None, led=False, mood="calm", eject=False) -> dict` (adds `j["slot"]`)
  - `dos.screen_sprite(w, h, facing, mood, glow) -> Surface` (lru-cached), `dos.floppy_sprite(color, size=18) -> Surface` (lru-cached; never draw on it), `dos._turned(color, angle)` (lru-cached), `dos.draw_floppy(surf, c, angle, color, facing)`, `dos.clip_icon(kind: str | None, color) -> Surface`
  - `render.dos_screen(f) -> tuple[str, bool, bool]` (mood, busy light, disk in the slot); `Renderer.clip_rects: dict[str, pygame.Rect]`

- [ ] **Step 1: Write the failing tests** at the end of `tests/test_render.py`:

```python
@pytest.mark.parametrize("name,strike,led,mood,eject", [
    ("idle", None, False, "calm", False),
    ("heavy_hit", ("hand_f", PURPLE), False, "calm", False),
    ("sweep_hit", ("foot_f", PURPLE), True, "angry", False),
    ("crouch", None, False, "calm", False),
    ("jump", None, False, "calm", False),
    ("eject", None, True, "angry", True),
])
@pytest.mark.parametrize("facing", [1, -1])
def test_dos_matches_his_approved_look(look, name, strike, led, mood, eject, facing):
    from brawl_ket.dos import draw_dos
    from brawl_ket.poses import POSES, drawn_joints
    ref = look("2026-10-21-brawl-ket-dos-look.py")
    pygame.init()
    a, b = pygame.Surface((240, 240)), pygame.Surface((240, 240))
    a.fill(BLANK)
    b.fill(BLANK)
    feet = (120.0, 220.0)
    ref.draw_dos(a, POSES[name], feet, facing, GREEN, strike, led, mood, eject)
    draw_dos(b, drawn_joints(POSES[name], "dos", feet, facing), facing, GREEN, strike, led, mood, eject)
    assert same_pixels(a, b)


def test_the_floppy_matches_the_approved_look(look):
    from brawl_ket.dos import floppy_sprite
    ref = look("2026-10-21-brawl-ket-dos-look.py")
    pygame.init()
    for colour in (GREEN, PURPLE):
        for size in (18, 22):
            assert same_pixels(ref.floppy_sprite(colour, size), floppy_sprite(colour, size), "RGBA")


def test_dos_is_always_drawn_green(surface):
    from brawl_ket.moves import DOS
    r = Renderer(surface)
    fight = Fight({"p1": ROBERT, "p2": DOS})
    r.draw_fight(fight, [])
    seen = body_pixels(surface, r, fight, "p2")
    assert GREEN in seen and PURPLE not in seen


def dos_frames(r, presses, frames, rival_x=600):
    """DOS (p1) against a far ROBERT, pressing `presses` on the first frame, drawn every frame."""
    from brawl_ket.fighter import FighterInput
    from brawl_ket.moves import DOS
    fight = Fight({"p1": DOS, "p2": ROBERT})
    fight.fighters["p2"].x = rival_x
    for i in range(frames):
        r.draw_fight(fight, fight.step({"p1": FighterInput(**presses) if i == 0 else FighterInput(
            down=presses.get("down", False))}))
    return fight


def test_blue_screen_turns_his_face_blue_and_rings_out_green(surface):
    from brawl_ket.dos import BSOD
    from brawl_ket.moves import DOS
    r = Renderer(surface)
    fight = dos_frames(r, {"down": True, "x": True}, DOS.moves["crouch.X"].startup + 2)
    dos = fight.fighters["p1"]
    assert dos.phase == "active"
    x = round(dos.x)
    face = {tuple(surface.get_at((i, j)))[:3] for i in range(x - 30, x + 31, 2) for j in range(FLOOR_Y - 150, FLOOR_Y - 60)}
    assert BSOD in face
    ring = {tuple(surface.get_at((i, FLOOR_Y - 55)))[:3] for i in range(x + 30, x + 80)}
    assert ring & {GREEN, P.lighten(GREEN, 0.35), P.WHITE}


def test_copy_holds_up_a_ctrl_c_frame(surface):
    from brawl_ket.moves import DOS
    copy = DOS.extra["copy"]
    r = Renderer(surface)
    fight = dos_frames(r, {"y": True}, copy.startup + 2)
    dos = fight.fighters["p1"]
    assert dos.move is copy and dos.phase == "active"
    left, top, w, _h = dos.world_box(copy.catch)
    assert P.WHITE in {tuple(surface.get_at((i, round(top))))[:3] for i in range(round(left), round(left + w))}


def test_a_floppy_in_flight_is_drawn_from_cached_turns(surface):
    from brawl_ket.dos import ANGLE_STEP, _turned
    from brawl_ket.moves import DOS
    _turned.cache_clear()
    r = Renderer(surface)
    fight = dos_frames(r, {"x": True}, DOS.moves["stand.X"].startup + 60)
    (shot,) = fight.shots
    assert _turned.cache_info().currsize <= 360 // ANGLE_STEP
    left, top, w, h = shot.box
    cx, cy = round(left + w / 2), round(top + h / 2)
    assert GREEN in {tuple(surface.get_at((i, j)))[:3] for i in range(cx - 12, cx + 13) for j in range(cy - 12, cy + 13)}


def test_the_hud_shows_doss_clipboard(surface):
    from brawl_ket.basis import X_BASIS
    from brawl_ket.moves import DOS
    r = Renderer(surface)
    fight = Fight({"p1": DOS, "p2": ROBERT})
    r.draw_fight(fight, [])
    assert set(r.clip_rects) == {"p1"}                      # only DOS has one

    def icon():
        rect = r.clip_rects["p1"]
        return {tuple(surface.get_at((i, j)))[:3] for i in range(rect.left, rect.right) for j in range(rect.top, rect.bottom)}

    assert not icon() & {GREEN, PURPLE}                     # empty
    fight.fighters["p1"].clipboard = (ROBERT.moves["stand.X"], X_BASIS)
    r.draw_fight(fight, [])
    assert PURPLE in icon()                                 # a purple PHOTON in it


def test_doss_screen_faces_are_drawn_once_and_blitted(surface):
    from brawl_ket.dos import screen_sprite
    from brawl_ket.moves import DOS
    screen_sprite.cache_clear()
    r = Renderer(surface)
    for fight, events in bot_frames(600, chars=(DOS, ROBERT)):
        r.draw_fight(fight, events)
    info = screen_sprite.cache_info()
    assert info.hits > 2 * info.misses
```

- [ ] **Step 2: Run them to make sure they fail**

Run: `uv run pytest tests/test_render.py -q -k "dos or floppy or blue_screen or copy or clipboard"`
Expected: FAIL with `ModuleNotFoundError: No module named 'brawl_ket.dos'`.

- [ ] **Step 3: Create `src/brawl_ket/dos.py`.** `draw_dos` is the look's, given the joints
from `poses.drawn_joints` (which applies the case's tilt and the arm sockets the look applied
itself), with `case` in place of the look's `GREEN`. The screen face and the disk are the
look's, drawn once per size, mood and angle:

```python
"""DOS's look: a walking all-in-one computer in 3/4 view, his screen his face, and his floppy.

Ported from his approved look, docs/superpowers/specs/2026-10-21-brawl-ket-dos-look.py:
draw_dos is the look's, given poses.drawn_joints (the case leans only CASE_TILT of a pose's
lean and his arms come out of its sides); tests/test_render.py checks him and the disk
against the look pixel for pixel. The screen faces (the look scanned every pixel of the
glass every call) and the disk's turns are drawn once each, then only blitted, so the
cabinet's frame budget holds.
"""

from __future__ import annotations

import math
from functools import lru_cache

import pygame

from . import palette as P
from .ink import _ball, _block, _boot, _pt, frame, limb, poly
from .ink import _towards as towards
from .poses import LIMB_W

BEIGE = (232, 216, 168)          # the one retro trim: keycap fists
GLASS = (16, 40, 24)             # the switched-off-looking dark of a mono CRT
SCAN = (24, 56, 32)
PHOSPHOR = (136, 248, 152)       # the phosphor green of his face
STEEL = P.MIST
LED = (248, 200, 48)
BSOD = (32, 72, 200)             # BLUE SCREEN: the crash
BSOD_SCAN = (24, 56, 168)
KEY = (255, 0, 255)
ANGLE_STEP = 15                  # the disk turns in steps of this many degrees, each drawn once
SPIN = 30                        # ... and its two pale silhouettes trail this far behind
CLIP_W, CLIP_H = 18, 14          # his clipboard on the HUD


def quad(at, base, up0, up1, f0, f1):
    """The four corners of a panel on the body, in the body's own frame."""
    return [at(base, up0, f0), at(base, up0, f1), at(base, up1, f1), at(base, up1, f0)]


def ribbed(surf, a, b, w, color):
    """A limb as a ribbed cable conduit: the game's capsule, with a darker band every 5 px."""
    limb(surf, a, b, w, color)
    dx, dy = b[0] - a[0], b[1] - a[1]
    n = math.hypot(dx, dy) or 1.0
    px, py = -dy / n, dx / n
    band = P.shade(color, 0.72)
    half = w / 2 - 1
    for k in range(1, int(n // 5)):
        c = (a[0] + dx * k * 5 / n, a[1] + dy * k * 5 / n)
        pygame.draw.line(surf, band, _pt((c[0] - px * half, c[1] - py * half)),
                         _pt((c[0] + px * half, c[1] + py * half)), 1)


@lru_cache(maxsize=512)    # about 50 sizes (the case tilts), 3 moods, 2 facings
def screen_sprite(w: int, h: int, facing: int, mood: str, glow) -> pygame.Surface:
    """His screen, w x h (plus its 2 px ink frame): dark glass with scanlines and a glare, and a
    face in phosphor pixels looking the way he faces, the look's screen_face. Angry, each
    eye's top slopes down towards the middle; "blue" (BLUE SCREEN), the glass crashes blue and
    the face is a white frown."""
    s = pygame.Surface((w + 4, h + 4))
    s.fill(KEY)
    s.set_colorkey(KEY)
    r = pygame.Rect(2, 2, w, h)
    blue = mood == "blue"
    bg, scan, lit = (BSOD, BSOD_SCAN, P.WHITE) if blue else (GLASS, SCAN, PHOSPHOR)
    pygame.draw.rect(s, P.INK, r.inflate(4, 4), border_radius=5)
    pygame.draw.rect(s, bg, r, border_radius=4)
    cx = r.centerx + round(r.w * 0.1) * facing
    cy = r.centery - 2
    if blue:
        for side in (-1, 1):
            s.fill(lit, (cx + side * 6 - 2, cy - 2, 4, 4))
        s.fill(lit, (cx - 5, cy + 8, 10, 2))
        s.fill(lit, (cx - 7, cy + 10, 2, 2))
        s.fill(lit, (cx + 5, cy + 10, 2, 2))
    else:
        for side in (-1, 1):
            eye = pygame.Rect(0, 0, 6, 9)
            eye.center = (cx + side * 6, cy)
            s.fill(lit, eye)
            if mood == "angry":
                inner_x = eye.right - 2 if side < 0 else eye.left
                s.fill(GLASS, (inner_x, eye.top, 2, 3))
                s.fill(GLASS, (eye.left + 2, eye.top, 2, 1))
        s.fill(lit, (cx - 5, cy + 8, 10, 2))
    # the look's scanlines, a row at a time: every other row of the glass turns `scan`, and the
    # face's pixels on it a dimmer shade (the look set every pixel by hand; same pixels, faster)
    dim = P.shade(lit, 0.78)
    for y in range(r.top + 1, r.bottom - 1, 2):
        row = s.subsurface((r.left + 1, y, r.w - 2, 1))
        face = pygame.mask.from_threshold(row, lit, (1, 1, 1, 255))
        row.fill(scan)
        face.to_surface(row, setcolor=dim, unsetcolor=None)
    gx = r.left + 3 if facing > 0 else r.right - 7
    s.fill(P.lighten(bg, 0.55), (gx, r.top + 2, 4, 2))
    s.fill(P.lighten(bg, 0.55), (gx + (0 if facing > 0 else 2), r.top + 4, 2, 2))
    pygame.draw.rect(s, glow, r, 1, border_radius=4)
    return s


def screen_face(surf, rect, facing, mood, glow):
    r = pygame.Rect(rect)
    surf.blit(screen_sprite(r.w, r.h, facing, mood, glow), (r.x - 2, r.y - 2))


@lru_cache(maxsize=16)
def floppy_sprite(color, size=18):
    """A 3.5" floppy disk, front face (the look's): the sliding steel shutter with its window
    at the top, the label with two lines of biro, the chamfered corner and the write-protect
    hole. Cached: never draw on it."""
    s = pygame.Surface((size + 4, size + 4), pygame.SRCALPHA)
    o = 2
    n = size
    body = [(o, o), (o + n - 4, o), (o + n, o + 4), (o + n, o + n), (o, o + n)]
    pygame.draw.polygon(s, color, body)
    pygame.draw.polygon(s, P.INK, body, 2)
    s.fill(P.lighten(color, 0.45), (o + 2, o + 2, n - 7, 1))
    sh = pygame.Rect(o + 4, o, 9, 8)
    s.fill(P.INK, sh.inflate(2, 0).move(0, 0))
    s.fill(STEEL, sh.inflate(-2, -2).move(0, 0))
    s.fill(P.INK, (sh.x + 5, sh.y + 2, 2, 4))
    lab = pygame.Rect(o + 3, o + n - 8, n - 6, 7)
    s.fill(P.INK, lab.inflate(2, 2))
    s.fill(P.WHITE, lab)
    s.fill(P.shade(P.SKY, 0.8), (lab.x + 2, lab.y + 2, lab.w - 6, 1))
    s.fill(P.shade(P.SKY, 0.8), (lab.x + 2, lab.y + 4, lab.w - 9, 1))
    s.fill(P.INK, (o + 1, o + n - 11, 2, 2))
    return s


@lru_cache(maxsize=128)
def _turned(color, angle: int) -> tuple[pygame.Surface, pygame.Surface, pygame.Surface]:
    """The flying disk turned by `angle` degrees: (the disk, its white rim, a pale silhouette)."""
    img = floppy_sprite(color, 22)
    disk = pygame.transform.rotate(img, angle)
    rim = pygame.mask.from_surface(disk).to_surface(setcolor=(*P.WHITE, 255), unsetcolor=(0, 0, 0, 0))
    sil = pygame.mask.from_surface(img).to_surface(setcolor=(*P.lighten(color, 0.4), 255), unsetcolor=(0, 0, 0, 0))
    return disk, rim, pygame.transform.rotate(sil, angle)


def draw_floppy(surf, c, angle, color, facing):
    """A spinning floppy in flight (the look's draw_floppy): two pale silhouettes of its last
    turns behind it, a few speed lines, then the disk itself with a white rim, so it reads
    against any stage. `angle` is rounded to ANGLE_STEP."""
    a = round(angle / ANGLE_STEP) * ANGLE_STEP % 360
    for k, alpha in ((2, 70), (1, 130)):
        e = _turned(color, (a + k * SPIN * facing) % 360)[2]
        e.set_alpha(alpha)
        surf.blit(e, e.get_rect(center=_pt((c[0] - facing * k * 15, c[1]))))
    for dy, ln in ((-8, 14), (0, 22), (8, 12)):
        x0 = c[0] - facing * 40
        pygame.draw.line(surf, P.lighten(color, 0.5), _pt((x0, c[1] + dy)), _pt((x0 - facing * ln, c[1] + dy)), 2)
    disk, rim, _sil = _turned(color, a)
    rect = disk.get_rect(center=_pt(c))
    for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1)):
        surf.blit(rim, rect.move(dx, dy))
    surf.blit(disk, rect)


@lru_cache(maxsize=32)
def clip_icon(kind: str | None, color) -> pygame.Surface:
    """His clipboard on the HUD: a little dark screen, empty, or showing the caught shot's tiny
    sprite (a disk, a laser streak or a photon) in the colour it was fired in."""
    s = pygame.Surface((CLIP_W, CLIP_H))
    s.fill(KEY)
    s.set_colorkey(KEY)
    box = s.get_rect()
    pygame.draw.rect(s, P.INK, box, border_radius=3)
    inner = box.inflate(-4, -4)
    pygame.draw.rect(s, GLASS, inner, border_radius=2)
    if kind is None:
        pygame.draw.rect(s, SCAN, inner, 1, border_radius=2)
        return s
    cx, cy = inner.center
    if kind == "FLOPPY":
        disk = pygame.Rect(0, 0, 8, 8)
        disk.center = (cx, cy)
        s.fill(color, disk)
        s.fill(STEEL, (disk.x + 2, disk.y, 4, 3))
        s.fill(P.WHITE, (disk.x + 1, disk.bottom - 3, 6, 2))
    elif kind == "LASER":
        pygame.draw.line(s, color, (inner.left + 2, cy), (inner.right - 3, cy), 3)
        s.fill(P.WHITE, (inner.right - 4, cy - 1, 2, 2))
    else:
        pygame.draw.circle(s, color, (cx, cy), 4)
        s.fill(P.lighten(color, 0.6), (cx - 1, cy - 2, 2, 2))
    return s


def draw_dos(surf, j, facing, case, strike=None, led=False, mood="calm", eject=False):
    """DOS at the joints `j` (poses.drawn_joints, build "dos"), his case in `case` (always his
    green). `strike` = (joint, colour) lights an attack's whole arm or leg; `mood` is his
    screen ("calm", "angry", "blue"), `led` his drive's busy light, `eject` a disk's edge in
    the slot. Adds j["slot"] (the drive slot's middle) and returns j."""
    at = frame(j, facing)
    w = LIMB_W["dos"]
    dark = P.shade(case, 0.65)
    boot = P.shade(case, 0.42)
    hip, neck = j["hip"], j["neck"]
    f = facing
    top, bot, fb, ff = 10, -4, -27, 27          # up from the neck / from the hip; the front's edges
    # 1. the back leg and arm, in shadow
    ribbed(surf, hip, j["knee_b"], w + 2, dark)
    ribbed(surf, j["knee_b"], j["foot_b"], w + 1, dark)
    _boot(surf, j["foot_b"], f, w + 2, P.shade(boot, 0.8))
    ribbed(surf, j["shoulder_b"], j["elbow_b"], w, dark)
    ribbed(surf, j["elbow_b"], j["hand_b"], w - 1, dark)
    _block(surf, j["hand_b"], w // 2 + 1, P.shade(BEIGE, 0.7))
    # 2. the front leg goes under the case
    leg = strike[1] if strike and strike[0] == "foot_f" else case
    ribbed(surf, hip, j["knee_f"], w + 2, leg)
    ribbed(surf, j["knee_f"], j["foot_f"], w + 1, leg)
    _boot(surf, j["foot_f"], f, w + 2, boot if leg is case else P.shade(leg, 0.6))
    # 3. the case, in 3/4: its side going back (behind the face), its top, its front
    d = (-10 * f, -6)

    def back(p):
        return (p[0] + d[0], p[1] + d[1])

    tl, tr = at(neck, top, fb), at(neck, top, ff)
    bl, br = at(hip, bot, fb), at(hip, bot, ff)
    poly(surf, [tl, back(tl), back(bl), bl], dark)
    poly(surf, [tl, tr, back(tr), back(tl)], P.lighten(case, 0.3))
    for k in range(4):                                                 # a carry handle's grip
        g = towards(tl, tr, 0.32 + k * 0.1)
        pygame.draw.line(surf, P.shade(case, 0.75), _pt((g[0] + d[0] * 0.3, g[1] + d[1] * 0.3)),
                         _pt((g[0] + d[0] * 0.7, g[1] + d[1] * 0.7)), 1)
    poly(surf, [tl, tr, br, bl], case)
    pygame.draw.line(surf, P.lighten(case, 0.45), _pt(at(neck, top - 2, fb + 3)), _pt(at(neck, top - 2, ff - 3)), 2)
    # the screen: the face, set towards the rival
    s0 = at(neck, top - 6, fb + 6)
    s1 = at(neck, top - 42, ff - 5)
    glass = pygame.Rect(0, 0, round(abs(s1[0] - s0[0])), round(abs(s1[1] - s0[1])))
    glass.center = _pt(towards(s0, s1, 0.5))
    screen_face(surf, glass, f, mood, P.shade(case, 0.45))
    # under the screen: the floppy drive's slot, its eject button and busy light
    slot_y = top - 54
    poly(surf, quad(at, neck, slot_y + 3, slot_y - 3, -10, 14), P.shade(case, 0.8))
    pygame.draw.line(surf, P.INK, _pt(at(neck, slot_y, -8)), _pt(at(neck, slot_y, 7)), 2)
    poly(surf, quad(at, neck, slot_y + 1, slot_y - 2, 9, 12), BEIGE, ink=1)
    pygame.draw.circle(surf, LED if led else P.shade(LED, 0.45), _pt(at(neck, slot_y, -14)), 1)
    if eject:                                   # the disk's edge sliding out, shutter first
        sx, sy = _pt(at(neck, slot_y, 0))
        pygame.draw.rect(surf, P.INK, (sx - 7, sy - 2, 14, 4))
        surf.fill(P.lighten(case, 0.3), (sx - 6, sy - 1, 12, 2))
    # the chin: vent slots, and the power switch with its light
    for k in range(3):
        pygame.draw.line(surf, P.shade(case, 0.6), _pt(at(hip, bot + 6 + k * 4, fb + 5)),
                         _pt(at(hip, bot + 6 + k * 4, fb + 19)), 2)
    pygame.draw.circle(surf, P.INK, _pt(at(hip, bot + 10, ff - 8)), 3)
    pygame.draw.circle(surf, PHOSPHOR, _pt(at(hip, bot + 10, ff - 8)), 1)
    # 4. the front arm, out of the case's side
    arm = strike[1] if strike and strike[0] == "hand_f" else case
    ribbed(surf, j["shoulder_f"], j["elbow_f"], w, arm)
    _ball(surf, j["shoulder_f"], w // 2 + 1, P.shade(arm, 0.8))
    ribbed(surf, j["elbow_f"], j["hand_f"], w - 1, arm)
    _block(surf, j["hand_f"], w // 2 + 2, BEIGE if arm is case else P.lighten(arm, 0.5))
    j["slot"] = at(neck, slot_y, 0)
    return j
```

(The look's second angry `fill` had the same rectangle on both sides of its `if`; it is
written once here, with the same pixels.)

- [ ] **Step 4: Draw him in `render.py`.**
  - Imports: `from .dos import BEIGE, CLIP_W, clip_icon, draw_dos, draw_floppy`;
    `drawn_joints` in the `.poses` import; `DRIVE_SLOT_Y` in the `.config` import.
  - `ACCENT` gets `"DOS": BEIGE`; remove Task 3's `"dos": 8` / `"dos": True` stand-ins; `SELF_LIT = ("cat", "dos")`.
  - `STRIKER` gets `"CRT DROP": "foot_f",` (BLUE SCREEN rings instead; FLOPPY, COPY and PASTE light nothing).
  - Effect lengths: `COPY_FLASH_FRAMES = 10   # COPY: a white selection box closing on the shot it caught` and `TAG_FRAMES = 30          # a small rising label (PASTE's CTRL+V)`.
  - `draw_puppet`, before `j = joints(...)`:

```python
    if build == "dos":
        j = drawn_joints(pose, build, feet, facing)
        draw_dos(surf, j, facing, body, strike, led, mood, eject)
        return j
```

  - After `strike_of`:

```python
def dos_screen(f: Fighter) -> tuple[str, bool, bool]:
    """DOS's screen this frame: (mood, his drive's busy light, a disk's edge in the slot).
    Calm, angry while he attacks or reels, blue through BLUE SCREEN; the disk shows as FLOPPY
    or PASTE fires."""
    m = f.move
    if f.action in ("hitstun", "knockdown"):
        return "angry", False, False
    if f.action != "attack" or m is None:
        return "calm", False, False
    if m.name == "BLUE SCREEN":
        return "blue", True, False
    fires = m.kind == "projectile" or m.paste
    return "angry", True, fires and f.startup - 2 <= f.frame < f.startup + m.active + 4
```

  - In `_fighter`, the main `draw_puppet` call becomes:

```python
        mood, led, eject = dos_screen(f) if f.char.build == "dos" else ("calm", False, False)
        j = draw_puppet(self.surface, pose, f.char.build, feet, f.facing, body, accent, flare,
                        strike=strike_of(f), mood=mood, led=led, eject=eject)
```

    and after the `_claws` lines:

```python
        if f.action == "attack" and m is not None:
            if m.catch is not None:
                self._copy_window(f, m, ox, oy)
            elif m.name == "BLUE SCREEN":
                self._blue_screen(f, m, ox, oy)
            elif m.name == "CRT DROP":
                self._crt_drop(f, ox, oy)
```

  - New methods after `_claws`:

```python
    def _copy_window(self, f: Fighter, m, ox: int, oy: int) -> None:
        """COPY: a dashed CTRL+C frame round the catch window in front of him, pale while he
        raises it and bright white while it can catch."""
        if f.phase not in ("startup", "active"):
            return
        surf = self.surface
        rect = pygame.Rect(f.world_box(m.catch)).move(ox, oy)
        colour = P.WHITE if f.phase == "active" else P.MIST
        for x in range(rect.left, rect.right - 2, 7):
            for y in (rect.top, rect.bottom - 2):
                surf.fill(P.INK, (x - 1, y - 1, 6, 4))
                surf.fill(colour, (x, y, 4, 2))
        for y in range(rect.top, rect.bottom - 2, 7):
            for x in (rect.left, rect.right - 2):
                surf.fill(P.INK, (x - 1, y - 1, 4, 6))
                surf.fill(colour, (x, y, 2, 4))
        blit_center(surf, outlined("CTRL+C", 8, colour), (rect.centerx, rect.top - 9))

    def _blue_screen(self, f: Fighter, m, ox: int, oy: int) -> None:
        """BLUE SCREEN: the crash rings out from his case to the edge of its reach, in the move's
        colour (his green: the colour rule stays readable), white on its first frame."""
        if f.phase != "active":
            return
        surf = self.surface
        colour = ERROR_COLOUR[basis.error_for(m.colour, f.attack_basis)]
        age = f.frame - f.startup
        k = (age + 1) / m.active
        reach, tall = m.hitbox.w / 2, m.hitbox.h
        cx, cy = round(f.x) + ox, round(FLOOR_Y - f.y - tall / 2) + oy
        for lag, width in ((0.0, 3), (0.35, 2)):
            kk = max(0.0, k - lag) / (1 - lag)
            if kk <= 0:
                continue
            rx = round(24 + (reach - 24) * kk)
            rect = pygame.Rect(0, 0, 2 * rx, round(tall * (0.4 + 0.6 * kk)))
            rect.center = (cx, cy)
            ring = P.WHITE if age == 0 else P.lighten(colour, 0.35) if lag == 0 else colour
            pygame.draw.ellipse(surf, P.INK, rect.inflate(4, 4), width + 2)
            pygame.draw.ellipse(surf, ring, rect, width)

    def _crt_drop(self, f: Fighter, ox: int, oy: int) -> None:
        """CRT DROP: speed lines streaming up off the case as it stomps straight down."""
        if f.phase != "active" or f.y <= 0:
            return
        top = round(FLOOR_Y - f.y - 150) + oy
        for dx, ln in ((-18, 22), (0, 30), (18, 22)):
            x = round(f.x) + dx + ox
            pygame.draw.line(self.surface, P.INK, (x, top - ln), (x, top), 4)
            pygame.draw.line(self.surface, P.WHITE, (x, top - ln), (x, top), 2)
```

  - `_shot`: draw the disk, and draw any shot whose move is a LASER as a beam even when it
    flies level (a pasted one):

```python
    def _shot(self, s, ox: int, oy: int) -> None:
        left, top, w, h = s.box
        cx, cy = left + w / 2 + ox, top + h / 2 + oy
        color = ERROR_COLOUR[basis.error_for(s.move.colour, s.basis)]
        if s.move.name == "FLOPPY":         # a spinning disk (one pasted back too)
            draw_floppy(self.surface, (cx, cy), -(self.t * 12 % 360) * s.facing, color, s.facing)
            return
        if s.move.projectile.vy:            # a LASER: a beam from where it left her hand to its head
            # ... the existing beam code, unchanged
```

  - `_reset` gets `self.clip_rects: dict[str, pygame.Rect] = {}`; in `_hud`, after
    `self._legend(key, f, lx, y)`:

```python
            if f.char.copy_paste:           # DOS's clipboard, beside his A / B chips
                self._clipboard(key, f, lx + LEGEND_W + 4 if side < 0 else lx - CLIP_W - 4, y - 3)
```

    and the method, after `_legend`:

```python
    def _clipboard(self, key: str, f: Fighter, x: int, y: int) -> None:
        """DOS's clipboard: empty, or the caught shot's tiny sprite in the colour it was fired in."""
        kind = colour = None
        if f.clipboard is not None:
            move, shot_basis = f.clipboard
            kind, colour = move.name, ERROR_COLOUR[basis.error_for(move.colour, shot_basis)]
        icon = clip_icon(kind, colour)
        self.surface.blit(icon, (x, y))
        self.clip_rects[key] = pygame.Rect(x, y, *icon.get_size())
```

  - `_start_effects`, two new branches:

```python
            elif e.kind == "copy":
                self.effects.append(Effect("copy", e.x, e.y, COPY_FLASH_FRAMES, COPY_FLASH_FRAMES, P.WHITE))
            elif e.kind == "paste" and e.player and self._fight is not None:
                f = self._fight.fighters[e.player]
                self.effects.append(Effect("tag", f.x + f.facing * 36, FLOOR_Y - f.y - DRIVE_SLOT_Y - 16,
                                           TAG_FRAMES, TAG_FRAMES, P.WHITE, "CTRL+V"))
```

  - `_draw_effects`, two new branches:

```python
            elif world and fx.kind == "copy":       # COPY: a selection box closing on the caught shot
                k = age / fx.life
                half = round(18 * (1 - k)) + 4
                rect = pygame.Rect(0, 0, 2 * half, 2 * half)
                rect.center = _pt((fx.x + ox, fx.y + oy))
                pygame.draw.rect(surf, P.INK, rect.inflate(2, 2), 3)
                pygame.draw.rect(surf, fx.color, rect, 1)
            elif world and fx.kind == "tag":        # a small label, rising (PASTE's CTRL+V)
                if fx.left < 8 and fx.left % 4 < 2:
                    continue
                blit_center(surf, outlined(fx.text, 8, fx.color), (fx.x + ox, fx.y + oy - min(age, 10)))
```

- [ ] **Step 5: Run the render tests**

Run: `uv run pytest tests/test_render.py -q`
Expected: all pass. As in Task 2, a look mismatch is fixed in `dos.py`, never in the test.

- [ ] **Step 6: DOS's snapshot frames.** In `tools/snapshot.py`, import `DOS`
(`from brawl_ket.moves import BOHR, DOS, ERWIN, ROBERT`),
add to the docstring `- moves_dos.png, dos_*.png: DOS's moves; FLOPPY in flight; COPY's
CTRL+C frame catching a PHOTON and the clipboard after it; PASTE; BLUE SCREEN; CRT DROP;` and:

```python
def dos_frames(out_dir: str) -> None:
    """DOS against a ROBERT: FLOPPY, COPY and PASTE, BLUE SCREEN and CRT DROP."""
    from brawl_ket.fighter import IDLE, FighterInput

    surface = pygame.Surface((W, H))

    def scene(name, presses, frames, rival_x=None, rival=IDLE, setup=None):
        fight, r = Fight({"p1": DOS, "p2": ROBERT}), Renderer(surface)
        if rival_x is not None:
            fight.fighters["p2"].x = rival_x
        if setup is not None:
            setup(fight)
        for i in range(frames):
            r.draw_fight(fight, fight.step({"p1": presses(i, fight), "p2": rival}), {"p1": 0, "p2": 0})
        save(surface, out_dir, f"{name}.png")
        return fight

    scene("dos_floppy", lambda i, f: FighterInput(x=i == 0), DOS.moves["stand.X"].startup + 30)
    # COPY against ROBERT's PHOTON: the frame up as the shot arrives, then the catch and the
    # clipboard on the HUD
    fight, r = Fight({"p1": DOS, "p2": ROBERT}), Renderer(surface)
    dos = fight.fighters["p1"]
    for i in range(90):
        near = bool(fight.shots) and abs(fight.shots[0].x - dos.x) < 80 and dos.move is None
        events = fight.step({"p1": FighterInput(y=near), "p2": FighterInput(x=i == 0)})
        r.draw_fight(fight, events, {"p1": 0, "p2": 0})
        if dos.move is not None and dos.move.catch is not None and fight.shots:
            save(surface, out_dir, "dos_copy.png")
        if any(e.kind == "copy" for e in events):
            for _ in range(4):
                r.draw_fight(fight, fight.step({}), {"p1": 0, "p2": 0})
            save(surface, out_dir, "dos_copied.png")
            break
    # PASTE: a purple PHOTON fired back
    scene("dos_paste", lambda i, f: FighterInput(y=i == 0), DOS.extra["paste"].startup + 12,
          setup=lambda f: setattr(f.fighters["p1"], "clipboard", (ROBERT.moves["stand.X"], "X")))
    scene("dos_blue_screen", lambda i, f: FighterInput(down=True, x=i == 0), DOS.moves["crouch.X"].startup + 2,
          rival_x=config.START_X["p1"] + 64)
    scene("dos_crt_drop", lambda i, f: FighterInput(up=True) if i == 0 else FighterInput(x=i == 9), 16,
          rival_x=config.START_X["p1"] + 30)
```

and in `main`, after `erwin_frames(out_dir)`:

```python
    save(move_sheet(DOS), out_dir, "moves_dos.png")
    dos_frames(out_dir)
```

(`dos_copy.png` is written over on each frame of the COPY before the catch; the last one,
the frame up and the shot about to meet it, is the one to look at.)

Run: `uv run python tools/snapshot.py /tmp/brawl-snaps`
Expected: the new PNGs. **Check them by eye** against
`uv run python ../docs/superpowers/specs/2026-10-21-brawl-ket-dos-look.py /tmp/dos-look.png`:
the same green case on ribbed legs, the floppy with its white rim and silhouettes; the blue
crash face and the green ring; the CTRL+C frame; the clipboard icon beside P1's chips.

- [ ] **Step 7: Run the whole suite and the lint**

Run: `uv run pytest -q && uvx --from 'ruff==0.15.22' ruff check src tests tools`
Expected: all pass, `All checks passed!`.

- [ ] **Step 8: Commit**

```bash
git add src/brawl_ket/dos.py src/brawl_ket/render.py tools/snapshot.py tests/test_render.py
git commit -m "feat: :art: Brawl-Ket: DOS drawn as the approved all-in-one, his floppy, BLUE SCREEN, COPY and his clipboard

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---
### Task 5: Five on CHOOSE YOUR FIGHTER, the title, the sounds and the README

**Files:**
- Modify: `src/brawl_ket/render.py` (`TRAITS`, `RULE_LINES`, `_select_panel`, `_title`)
- Modify: `src/brawl_ket/audio.py` (`build_sfx`, `EVENT_SOUNDS`, `SUPERSEDES`)
- Modify: `tools/snapshot.py`
- Modify: `README.md`
- Modify: `tests/test_render.py`, `tests/test_match.py`, `tests/test_audio.py`

**Interfaces:**
- Consumes: `Character.copy_paste`, `Character.fixed_basis`, `Character.extra`; every event and
  cue name from Tasks 1 and 3 (`box_split`, `box_collapse`, `pounce`, `scratch`, `floppy`,
  `blue_screen`, `crt_drop`, `copy`, `paste`).
- Produces: `render.TRAITS` (five entries), `render.CLASSICAL_LINES`,
  `render.panel_lines(char) -> tuple[tuple[str, tuple], ...]`; nine sounds of the same names in
  `audio.build_sfx()`, each mapped in `EVENT_SOUNDS`.

- [ ] **Step 1: Write the failing tests.**

`tests/test_render.py`:

```python
def test_the_select_panels_say_what_each_fighter_is():
    from brawl_ket.moves import CHARACTERS
    from brawl_ket.render import panel_lines
    text = {name: [line for line, _c in panel_lines(c)] for name, c in CHARACTERS.items()}
    assert text["ERWIN"][0] == "QUICK AND SLIPPERY" and "Y SWITCHES YOUR COLOUR" in text["ERWIN"]
    assert text["DOS"] == ["SLOW AND CLASSICAL", "A AND X: YOUR COLOUR, B: THE OTHER", "Y: COPY, THEN PASTE",
                           "ALWAYS GREEN"]
    assert panel_lines(CHARACTERS["DOS"])[-1][1] == GREEN
    for name in ("ROBERT", "BOHR", "PHOEBE"):
        assert text[name][1:] == ["A AND X: YOUR COLOUR, B: THE OTHER", "Y SWITCHES YOUR COLOUR"], name


def test_choose_your_fighter_draws_every_fighter(surface):
    import random

    from brawl_ket import match as M
    r = Renderer(surface)
    m = M.Match(random.Random(1))
    m.state = M.SELECT
    for i in range(len(M.ROSTER)):
        m.picks = {"p1": i, "p2": (i + 1) % len(M.ROSTER)}
        r.draw(m, [])


def test_the_title_still_shows_both_colours(surface):
    import random

    from brawl_ket import match as M
    r = Renderer(surface)
    r.draw(M.Match(random.Random(1)), [])
    seen = {tuple(surface.get_at((x, y)))[:3] for x in range(440, 481, 2) for y in range(FLOOR_Y - 110, FLOOR_Y - 40, 2)}
    assert PURPLE in seen               # ERWIN on the right: DOS, last in the roster, can't be purple
```

and in `test_the_teaching_text_is_ascii_capitals`, import `CLASSICAL_LINES` and `TRAITS` and
add `*CLASSICAL_LINES, *TRAITS.values()` to the texts it checks.

`tests/test_match.py`:

```python
def test_choose_your_fighter_cycles_through_all_five_in_order() -> None:
    from brawl_ket.match import ROSTER
    order = ["ROBERT", "BOHR", "PHOEBE", "ERWIN", "DOS"]
    assert [c.name for c in ROSTER] == order
    m = Match(random.Random(1))
    m.update(press("confirm"))
    seen = []
    for _ in range(len(ROSTER)):
        seen.append(ROSTER[m.picks["p1"]].name)
        m.update(press("right", "p1"))
    assert seen == order and m.picks["p1"] == 0         # and round again
```

`tests/test_audio.py`
(add `from brawl_ket.moves import CHARACTERS` to the imports at the top of the file)

```python
NEW_SOUNDS = ("box_split", "box_collapse", "pounce", "scratch", "floppy", "blue_screen", "crt_drop", "copy", "paste")


def test_erwin_and_dos_have_their_sounds() -> None:
    sfx = audio.build_sfx()
    for kind in NEW_SOUNDS:
        assert audio.EVENT_SOUNDS.get(kind) in sfx, kind


def test_every_moves_cue_has_a_sound() -> None:
    moves = [m for c in CHARACTERS.values() for m in (*c.moves.values(), *c.extra.values())]
    assert {m.cue for m in moves if m.cue} <= {k for k, s in audio.EVENT_SOUNDS.items() if s}


def test_a_floppy_and_a_paste_replace_the_photons_sound() -> None:
    assert audio.sounds_for([Event("projectile", "p1"), Event("floppy", "p1")]) == ["floppy"]
    assert audio.sounds_for([Event("projectile", "p1"), Event("paste", "p1")]) == ["paste"]
```

- [ ] **Step 2: Run them to make sure they fail**

Run: `uv run pytest tests/test_render.py tests/test_match.py tests/test_audio.py -q`
Expected: FAIL: `ImportError: cannot import name 'panel_lines'` and the audio tests'
`None in sfx` assertions.

- [ ] **Step 3: The select panels and the title** in `src/brawl_ket/render.py`:

```python
TRAITS = {"ROBERT": "FAST AND LIGHT", "BOHR": "SLOW AND HEAVY", "PHOEBE": "TALL AND TRICKY",
          "ERWIN": "QUICK AND SLIPPERY", "DOS": "SLOW AND CLASSICAL"}
X_INPUTS = (("stand.X", "X"), ("crouch.X", "DOWN+X"), ("air.X", "AIR X"))
RULE_LINES = ("A AND X: YOUR COLOUR, B: THE OTHER", "Y SWITCHES YOUR COLOUR")
# DOS can't switch: his Y copies a shot and then pastes it, and he is always green
CLASSICAL_LINES = ("A AND X: YOUR COLOUR, B: THE OTHER", "Y: COPY, THEN PASTE", "ALWAYS GREEN")
```

After `legend_colours`:

```python
def panel_lines(char: Character) -> tuple[tuple[str, tuple], ...]:
    """CHOOSE YOUR FIGHTER's lines under a fighter's name, each (text, colour): what it is, then
    its colour rules. DOS's say what his Y does instead, and the last one is in his one colour."""
    rules = CLASSICAL_LINES if char.copy_paste else RULE_LINES
    lines = [(TRAITS.get(char.name, ""), P.MIST), *((line, P.MIST) for line in rules)]
    if char.fixed_basis is not None:
        lines[-1] = (lines[-1][0], BASIS_BODY[char.fixed_basis])
    return tuple(lines)
```

In `_select_panel`, the "what it is" loop becomes:

```python
        lines = panel_lines(char)
        gap = 11 if len(lines) <= 3 else 10         # DOS's four lines still clear his moves
        for i, (line, colour) in enumerate(lines):
            blit_center(surf, outlined(line, 8, colour), (cx, floor + 36 + gap * i))
```

In `_title`, the fighters' loop head becomes:

```python
        # ROBERT green and the last fighter who can switch purple: the title shows both colours
        rival = next(c for c in reversed(M.ROSTER) if c.fixed_basis is None)
        for char, key, x, facing in ((M.ROSTER[0], "p1", 180, 1), (rival, "p2", 460, -1)):
```

- [ ] **Step 4: The sounds** in `src/brawl_ket/audio.py`, at the end of the dict in `build_sfx`:

```python
        # ERWIN: THE BOX splitting (a wobble, up and down at once), the collapse (a pop and a
        # bright blip), POUNCE (a springy leap), SCRATCH (three quick scratches)
        "box_split": mix(tone(c("E5"), 0.18, 0.13, "triangle", decay=5, slide=1.5),
                         tone(c("E5", 7), 0.18, 0.1, "triangle", decay=5, slide=0.67)),
        "box_collapse": concat(noise_wave(0.03, 0.2, decay=40, hold=2, seed=13),
                               tone(c("B5"), 0.08, 0.2, "pulse", decay=14)),
        "pounce": tone(300, 0.14, 0.18, "square", decay=10, slide=2.4),
        "scratch": concat(*(noise_wave(0.025, 0.16, decay=60, hold=1, seed=s) for s in (21, 22, 23))),
        # DOS: FLOPPY (a drive's whirr and click), BLUE SCREEN (a crashing low buzz), CRT DROP (a
        # heavy thud), COPY (two key clicks), PASTE (a click, then a blip)
        "floppy": concat(tone(180, 0.08, 0.16, "saw", decay=6, slide=1.4), noise_wave(0.03, 0.18, decay=50, hold=4, seed=31)),
        "blue_screen": mix(tone(110, 0.35, 0.22, "square", decay=4, slide=0.7),
                           noise_wave(0.3, 0.14, decay=6, hold=8, seed=33)),
        "crt_drop": mix(tone(90, 0.2, 0.35, "sine", decay=10, slide=0.5), noise_wave(0.15, 0.25, decay=18, hold=5, seed=35)),
        "copy": concat(tone(c("A5"), 0.03, 0.18, "pulse"), tone(0, 0.02, 0), tone(c("A5"), 0.03, 0.18, "pulse")),
        "paste": concat(tone(c("A5"), 0.03, 0.18, "pulse"), tone(0, 0.02, 0), tone(c("E6"), 0.07, 0.2, "pulse", decay=12)),
```

`EVENT_SOUNDS`: replace the Task 1 / Task 3 `None`s and add the cues:

```python
EVENT_SOUNDS = {"attack": "swing", "hit": "hit", "block": "ping", "switch": "whoosh", "measure": "measure",
                "projectile": "photon", "shockwave": "shockwave",
                "pillar": "pillar", "tunnel": "tunnel", "laser": "laser", "fizzle": "sizzle",
                "box_split": "box_split", "box_collapse": "box_collapse", "pounce": "pounce", "scratch": "scratch",
                "floppy": "floppy", "blue_screen": "blue_screen", "crt_drop": "crt_drop", "copy": "copy",
                "paste": "paste",
                "land": None, "ko": None, "timeout": None}   # ko/timeout: the cues play those
SUPERSEDES = {"measure": "hit",     # MEASURE's zap replaces the thump of its own throw
              "laser": "photon",    # a LASER is a projectile too: its zap, not the photon's
              "floppy": "photon",   # ... and so are a FLOPPY
              "paste": "photon"}    # ... and a PASTE
```

- [ ] **Step 5: The select screen's snapshot.** In `tools/snapshot.py`, add to the
docstring `- screen_select_erwin_dos.png: CHOOSE YOUR FIGHTER on ERWIN (P1) and DOS (P2);` and:

```python
def select_frame(out_dir: str) -> None:
    """CHOOSE YOUR FIGHTER with ERWIN and DOS picked: their traits, DOS's Y and ALWAYS GREEN."""
    from brawl_ket import match as M

    surface = pygame.Surface((W, H))
    r, m = Renderer(surface), M.Match(random.Random(3))
    m.state = M.SELECT
    m.picks = {"p1": 3, "p2": 4}
    for _ in range(4):
        r.draw(m, [])
    save(surface, out_dir, "screen_select_erwin_dos.png")
```

called from `main` after `screen_frames(out_dir)`. Run `uv run python tools/snapshot.py /tmp/brawl-snaps`
and check by eye that DOS's four lines clear his three moves.

- [ ] **Step 6: The README.** In `brawl-ket/README.md`:
  - **Status**, first bullet: `five fighters (ROBERT, BOHR, PHOEBE, ERWIN and DOS), versus only, best of 3 rounds of 60 s.`
  - **Screens** bullet: `chunky GBA-style puppets (and PHOEBE, a scientist in a long coat; ERWIN, Schrodinger's cat; DOS, a walking all-in-one computer) at 640x360 ...`
  - **The rules**, after the "Y switches basis" bullet:
    `- **DOS is the exception.** A classical bit can't be in superposition, so he is always green: his Y doesn't switch, and MEASURE hurts him without collapsing him. His Y is COPY, then PASTE (below).`
  - **Damage** line: append `, POUNCE 10, SCRATCH 4 a claw, THE BOX's swipe 8, FLOPPY 9, BLUE SCREEN 6, CRT DROP 12` and the health list becomes `ROBERT 100, BOHR 115, PHOEBE 95, ERWIN 90, DOS 125`.
  - **The fighters** table gets two columns:

| | ERWIN | DOS |
|---|---|---|
| Build | quick and slippery, the highest jump, 90 health | slow and classical, the lowest jump, 125 health; **always green** |
| X (standing) | THE BOX: she splits into two holographic boxes, where she stood and 120 px towards the rival. Any press or new stick direction (or 1.5 s) collapses it into a random box, with a swipe; anything that touches a box measures her, 50/50: she is in that box and it lands, or in the other and it whiffs (3 s cooldown, from the collapse) | FLOPPY: a spinning disk from his drive slot, slower than PHOTON (2.5 s cooldown) |
| Down + X | POUNCE: a long low leap that knocks down; MID, so a crouch doesn't save you; a long landing (2 s cooldown) | BLUE SCREEN: his screen crashes blue and a shockwave rings out 50 px past his case, MID, a long stun, pushing you away (3 s cooldown) |
| Air X | SCRATCH: she hangs in the air and claws three times, once per jump | CRT DROP: a fast stomp straight down that knocks down; no shockwave, a long landing |
| Y | switches her colour, even inside THE BOX | COPY: a CTRL+C frame catches a rival's shot into his clipboard (the icon by his chips); then PASTE fires it straight ahead in the colour it was fired in. Only when he is free to act |

    Merge them into the existing table as its fourth and fifth columns (with a `Y` row reading
    `switches your colour` for ROBERT, BOHR and PHOEBE). After PHOEBE's paragraph add:
    `ERWIN's weakness is the least health, and THE BOX is a gamble; DOS's is that his rival only ever needs green attacks against him. Design: ../docs/superpowers/specs/2026-10-21-brawl-ket-erwin-dos-design.md.`
    and `All three share the normals` becomes `All five share the normals`.
  - **Layout** table: `moves.py`'s row says `ROBERT, BOHR, PHOEBE, ERWIN and DOS`; add rows
    `| ink.py, erwin.py, dos.py | The drawing primitives; ERWIN's cat and THE BOX; DOS's case, screen faces, floppy and clipboard icon (both checked pixel for pixel against their approved look scripts, and cached so the cabinet keeps its frame budget). |`;
    `fighter.py, fight.py`'s row adds `THE BOX's 50/50s come from the fight's own seeded random.Random: the same seed and inputs give the same round.`

- [ ] **Step 7: Run the whole suite and the lint**

Run: `uv run pytest -q && uvx --from 'ruff==0.15.22' ruff check src tests tools`
Expected: all pass, `All checks passed!`.

- [ ] **Step 8: Commit**

```bash
git add src/brawl_ket/render.py src/brawl_ket/audio.py tools/snapshot.py README.md \
  tests/test_render.py tests/test_match.py tests/test_audio.py
git commit -m "feat: :speaker: Brawl-Ket: five on CHOOSE YOUR FIGHTER, DOS's panel, ERWIN's and DOS's sounds, the README

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 6: Bots for ERWIN and DOS, the balance bar, the demo and the benchmark

**Files:**
- Modify: `src/brawl_ket/bot.py`
- Create: `tests/test_balance.py`, `tools/balance.py`
- Modify: `tests/test_bot.py` (remove any Task 1 / Task 3 `xfail` marks), `tests/test_match.py`
- Modify: `README.md` (Setup)

**Interfaces:**
- Consumes: `Fighter.boxed`, `Fighter.boxes`, `Fighter.box_t`, `Fighter.clipboard`,
  `Character.fixed_basis`, `Character.copy_paste`, `Move.superpose`, `Move.leap`, `Move.dive`,
  `Move.hover`, `Move.hit_every`, `Move.projectile`.
- Produces: `bot.BOX_DANGER`, `BOX_POP`, `POUNCE_RANGE`, `COPY_REACH`, `SCREEN_RANGE`,
  `DROP_RANGE`; `Bot._in_box`, `Bot._erwin`, `Bot._dos`; `Bot._press("y", dx)`;
  `tools/balance.py` `share(a: str, b: str, seeds) -> float`.

- [ ] **Step 1: Write the failing tests.** In `tests/test_bot.py`, the imports at the top
become `from brawl_ket.fight import Fight, Shot` and `from brawl_ket.fighter import FighterInput`
(added); then append:

```python
ERWIN, DOS, ROBERT = CHARACTERS["ERWIN"], CHARACTERS["DOS"], CHARACTERS["ROBERT"]
PHOTON = ROBERT.moves["stand.X"]


def test_erwin_boxes_against_a_shot_that_would_hurt():
    fight = Fight({"p1": ERWIN, "p2": ROBERT})
    me = fight.fighters["p1"]
    fight.shots.append(Shot("p2", PHOTON, me.x + 50, 0.0, -PHOTON.projectile.speed, 200))
    bot = Bot("p1", seed=1, skill=1.0)
    pressed = [inp for inp in (bot.input(fight) for _ in range(30)) if inp.x]
    assert pressed and not pressed[0].down              # X standing: THE BOX


def test_erwin_waits_in_the_box_then_pops_out_near_the_rival():
    fight = Fight({"p1": ERWIN, "p2": ROBERT})
    me, rival = fight.fighters["p1"], fight.fighters["p2"]
    fight.step({"p1": FighterInput(x=True)})
    while not me.boxed:
        fight.step({})
    bot = Bot("p1", seed=1, skill=1.0)
    assert not bot.input(fight).a                       # far from both boxes: she waits
    rival.x = me.boxes[1] + 30
    bot.gap = 0
    assert bot.input(fight).a                           # the rival came close: out with a swipe


def test_dos_copies_an_incoming_shot_and_pastes_at_once():
    fight = Fight({"p1": DOS, "p2": ROBERT})
    dos = fight.fighters["p1"]
    fight.shots.append(Shot("p2", PHOTON, dos.x + 80, 0.0, -PHOTON.projectile.speed, 200))
    bot = Bot("p1", seed=1, skill=1.0)
    assert any(bot.input(fight).y for _ in range(20))
    fight.shots.clear()
    dos.clipboard = (PHOTON, "X")
    bot.gap = 0
    assert bot.input(fight).y


def test_dos_never_uses_y_to_dodge_or_feint():
    for seed in range(5):
        fight = Fight({"p1": DOS, "p2": ROBERT}, seed=seed)
        bots = {"p1": Bot("p1", seed), "p2": Bot("p2", seed + 1000)}
        while not fight.over:
            ins = {k: b.input(fight) for k, b in bots.items()}
            if ins["p1"].y:     # every Y of his is a COPY at a shot or a PASTE
                assert fight.fighters["p1"].clipboard is not None or any(s.owner == "p2" for s in fight.shots)
            fight.step(ins)


@pytest.mark.parametrize("name,extra", [("ERWIN", {"box_split", "pounce", "scratch"}),
                                        ("DOS", {"floppy", "blue_screen", "crt_drop", "copy", "paste"})])
def test_the_new_bots_use_all_their_specials(name, extra):
    kinds: set[str] = set()
    for seed in range(40):
        if extra <= kinds:
            break
        fight = Fight({"p1": CHARACTERS[name], "p2": ROBERT}, seed=seed)
        bots = {"p1": Bot("p1", seed), "p2": Bot("p2", seed + 1000)}
        while not fight.over:
            kinds |= {e.kind for e in fight.step({k: b.input(fight) for k, b in bots.items()}) if e.player == "p1"}
    assert extra <= kinds, extra - kinds
```

`tests/test_match.py`:

```python
def test_the_demo_picks_its_fighters_from_all_five() -> None:
    from brawl_ket.match import ROSTER
    m = Match(random.Random(3))
    seen = set()
    for _ in range(40):
        m._start_attract()
        seen |= {f.char.name for f in m.attract.fighters.values()}
    assert len(ROSTER) == 5 and seen == {c.name for c in ROSTER}
```

`tests/test_balance.py`:

```python
"""The balance bar (docs/superpowers/specs/2026-10-21-brawl-ket-erwin-dos-design.md, section 6):
bot against bot, from both sides, no fighter wins more than about 60% of the rounds against
another. Held for every pairing with ERWIN or DOS; `tools/balance.py` prints the whole table
(the older three's pairings included, which were never held to it)."""

import itertools

import pytest

from brawl_ket.bot import Bot
from brawl_ket.config import ROUND_FRAMES
from brawl_ket.fight import Fight
from brawl_ket.moves import CHARACTERS

SEEDS = range(50)       # 100 rounds a pairing, 50 from each side
BAR = 0.62              # "about 60%", with room for 100 rounds' noise (tools/balance.py checks 0.60 over 400)
NEW = ("ERWIN", "DOS")
PAIRS = [(a, b) for a, b in itertools.combinations(CHARACTERS, 2) if a in NEW or b in NEW]


def winner(seed: int, p1: str, p2: str) -> str | None:
    fight = Fight({"p1": CHARACTERS[p1], "p2": CHARACTERS[p2]}, seed=seed)
    bots = {"p1": Bot("p1", seed), "p2": Bot("p2", seed + 1000)}
    for _ in range(2 * ROUND_FRAMES):
        if fight.over:
            break
        fight.step({k: b.input(fight) for k, b in bots.items()})
    return fight.winner


def share(a: str, b: str) -> float:
    """a's share of the decided rounds against b, playing each seed from both sides."""
    won = lost = 0
    for seed in SEEDS:
        for p1, p2 in ((a, b), (b, a)):
            w = winner(seed, p1, p2)
            if w is None:
                continue
            if (w == "p1") == (p1 == a):
                won += 1
            else:
                lost += 1
    return won / max(1, won + lost)


def test_every_new_pairing_is_checked():
    assert len(PAIRS) == 7          # ERWIN against the other four, DOS against the first three


@pytest.mark.parametrize("pair", PAIRS, ids="-".join)
def test_no_fighter_wins_more_than_about_60_percent(pair):
    s = share(*pair)
    assert 1 - BAR <= s <= BAR, (pair, round(s, 2))
```

- [ ] **Step 2: Run them to make sure they fail**

Run: `uv run pytest tests/test_bot.py tests/test_balance.py tests/test_match.py -q`
Expected: the new bot tests FAIL (ERWIN never boxes, DOS never copies; `_press("y")` is not a
press); the balance test may pass or fail for some pairings: record its numbers.

- [ ] **Step 3: The bots** in `src/brawl_ket/bot.py`. Module docstring, append:
`ERWIN boxes against a shot or a heavy that would hurt her and pops out when the rival comes
near a box, pounces on crouchers and scratches jumpers; DOS COPYs incoming shots, PASTEs at
once, FLOPPYs at range, BLUE SCREENs a rival who is close and CRT DROPs on one under him. DOS
never switches, so he never uses Y to dodge or feint.`

Constants, after `SWITCHER`:

```python
BOX_DANGER = 60         # ERWIN boxes against a shot or a heavy this close (90 made her win 65% against DOS)
BOX_POP = 50            # ... and pops out once the rival is this close to either box
POUNCE_RANGE = (60, 170)    # ERWIN pounces on a crouching rival this far away
COPY_REACH = (30, 110)  # a rival's shot this far from DOS, coming, is worth a COPY
SCREEN_RANGE = 80       # DOS's BLUE SCREEN reaches a rival this close (50 px past his case)
DROP_RANGE = 30         # DOS stomps on a rival this close under him
```

`__init__` gets `self.box_hold = 0               # THE BOX: how long this bot stays in the boxes`.

`input` becomes:

```python
    def input(self, fight: Fight) -> FighterInput:
        me, rival = fight.fighters[self.player], fight.fighters[self.rival]
        self.t += 1
        self.gap = max(0, self.gap - 1)
        self.rival_crouched = self.rival_crouched + 1 if rival.stance == "crouch" else 0
        self._watch(rival.stance)
        self._count_switches(rival)

        if self._wants_dodge(me, rival):     # a switch works in any state, hitstun included
            self.gap = PRESS_GAP
            return FighterInput(down=self.down, y=True)
        if me.boxed:
            return self._in_box(me, rival)
        if me.action in _BUSY:
            self.chain.clear()
            return FighterInput(down=self.down)
        toward = 1 if rival.x > me.x else -1
        dist = abs(rival.x - me.x)
        m = rival.move
        if m is not None and m.hit_every and rival.action == "attack" and dist <= FIELD_RANGE + 20 \
                and self.would_hurt(rival, m, me) and me.action in ("idle", "walk", "crouch"):
            self.down = False
            return FighterInput(dx=-toward)                     # back out of a field that hurts
        if me.stance == "air":
            return self._in_air(me, rival, toward, dist)
        for rule in (self._phoebe, self._erwin, self._dos):
            special = rule(fight, me, rival, toward, dist)
            if special is not None:
                return special
        self.air_pressed = False
        if me.action == "attack":
            return self._continue_chain(me, toward)
        if self.chain and not me.buffer:
            self.chain.clear()      # the string ended (or whiffed): start afresh
        return self._on_ground(me, rival, toward, dist)
```

`_wants_dodge`, first lines of its body:

```python
        if me.char.fixed_basis is not None:     # DOS can't switch: his Y is COPY / PASTE
            return False
```

In `_on_ground`, the feint's condition becomes `if roll < 0.04 and ready and me.char.fixed_basis is None:`.

`_in_air` becomes:

```python
    def _in_air(self, me, rival, toward: int, dist: float) -> FighterInput:
        air = me.char.moves["air.X"]
        ready = not self.air_pressed and self.gap == 0 and "air.X" not in me.air_used
        if air.hover and air.projectile is not None and ready and abs(dist - (me.y + 50)) < 45 \
                and self.would_hurt(me, air, rival):
            # LASER: the shot leaves 50 px ahead at hand height (59 px) and falls one px per px, so
            # it meets a standing body about y + 50 px ahead, give or take its height: fire
            self.air_pressed = True
            return self._press("x", toward)
        if air.hover and air.hit_every and ready and dist <= 60 and abs(me.y - rival.y) <= 50 \
                and self.would_hurt(me, air, rival):
            self.air_pressed = True
            return self._press("x", toward)                     # SCRATCH a rival beside her
        if air.dive is not None and air.dive[0] == 0 and ready and abs(rival.x - me.x) <= DROP_RANGE \
                and me.y > rival.y + 30:
            self.air_pressed = True
            return self._press("x", 0)                          # CRT DROP on a rival under him
        if not self.air_pressed and self.gap == 0 and dist <= AIR_RANGE:
            self.air_pressed = True
            button = "x" if self.rng.random() < 0.3 else self.matching(me, rival)
            return self._press(button, toward)
        return FighterInput(dx=toward)
```

New rules, after `_phoebe`:

```python
    def _in_box(self, me, rival) -> FighterInput:
        """THE BOX: pop out (A, with the swipe) once the rival comes near either box, or after a
        while of its own choosing."""
        if me.box_t == 0:
            self.box_hold = self.rng.randrange(20, 70)
        near = min(abs(rival.x - x) for x in me.boxes) <= BOX_POP
        if self.gap == 0 and (near or me.box_t >= self.box_hold):
            return self._press("a", 0)
        return FighterInput()

    def _erwin(self, fight: Fight, me, rival, toward: int, dist: float) -> FighterInput | None:
        """ERWIN on the ground: THE BOX against a shot or a heavy that would hurt her, POUNCE on a
        crouching rival, and a jump to SCRATCH a rival in the air."""
        box, pounce = me.char.moves["stand.X"], me.char.moves["crouch.X"]
        if not box.superpose or me.action not in ("idle", "walk", "crouch") or self.gap > 0:
            return None
        if me.cooldowns.get("stand.X", 0) == 0:
            shot = any(s.owner == self.rival and (s.x - me.x) * s.vx < 0 and abs(s.x - me.x) <= BOX_DANGER
                       and self.would_hurt_shot(s, me) for s in fight.shots)
            m = rival.move
            heavy = rival.action == "attack" and m is not None and rival.phase == "startup" and m.damage >= 8 \
                and m.kind != "throw" and dist <= BOX_DANGER and self.would_hurt(rival, m, me)
            if (shot and self.rng.random() < self.skill * 0.5) or (heavy and self.rng.random() < self.skill * 0.3):
                self.down = False
                return self._press("x", 0)
        if rival.stance == "crouch" and POUNCE_RANGE[0] <= dist <= POUNCE_RANGE[1] \
                and me.cooldowns.get("crouch.X", 0) == 0 and self.would_hurt(me, pounce, rival) \
                and self.rng.random() < 0.05:
            self.down = True
            press = self._press("x", 0)                         # POUNCE, from a crouch ...
            self.down = False                                   # ... and up again: no sitting there
            return press
        if rival.y > 30 and dist <= 110 and self.rng.random() < 0.04:
            self.down = False
            return FighterInput(up=True, dx=toward)             # up after a jumper, to scratch
        return None

    def _dos(self, fight: Fight, me, rival, toward: int, dist: float) -> FighterInput | None:
        """DOS: PASTE at once, COPY a rival's shot that is about to arrive, BLUE SCREEN a rival
        who is close, and now and then a hop to CRT DROP on them."""
        if not me.char.copy_paste or me.action not in ("idle", "walk", "crouch") or self.gap > 0:
            return None
        if me.clipboard is not None:
            self.down = False
            return self._press("y", 0)                          # PASTE
        coming = any(s.owner == self.rival and (s.x - me.x) * s.vx < 0
                     and COPY_REACH[0] <= abs(s.x - me.x) <= COPY_REACH[1] for s in fight.shots)
        if coming and self.rng.random() < self.skill * 0.6:
            self.down = False
            return self._press("y", 0)                          # COPY
        screen = me.char.moves["crouch.X"]
        if dist <= SCREEN_RANGE and me.cooldowns.get("crouch.X", 0) == 0 and self.would_hurt(me, screen, rival) \
                and self.rng.random() < 0.05:
            self.down = True
            press = self._press("x", 0)                         # BLUE SCREEN, from a crouch ...
            self.down = False                                   # ... and up again (a crouching DOS invites POUNCE)
            return press
        if dist <= 60 and rival.y == 0 and self.rng.random() < 0.01:
            self.down = False
            return FighterInput(up=True, dx=toward)             # a hop, to come down on them
        return None
```

`_press` handles Y too:

```python
    def _press(self, button: str, dx: int) -> FighterInput:
        self.gap = PRESS_GAP
        return FighterInput(dx=dx, down=self.down, a=button == "a", b=button == "b",
                            x=button == "x", y=button == "y")
```

- [ ] **Step 4: Run the bot, match and balance tests**

Run: `uv run pytest tests/test_bot.py tests/test_match.py tests/test_balance.py -q`
Expected: all pass (they did on a prototype of this plan, with exactly these numbers). Remove any `xfail` mark added in Task 1 or Task 3 Step 12 / Step 11 and
rerun; `test_neither_side_is_favoured` must pass for every pairing.

**If a balance pairing fails,** tune in this order, rerunning `tests/test_balance.py` after
each change, and stop as soon as all seven pass:
1. the new bots' probabilities and ranges (`_erwin`, `_dos`, `_in_box`, the constants above);
2. the numbers this plan chose where the spec says "about" (Decisions table): POUNCE's
   recovery (18-22), COPY's window (10-14) and missed recovery (16-20), BLUE SCREEN's stun
   (30-40) and reach (44-56 px past his case), CRT DROP's recovery (18-22), FLOPPY's speed
   (2.5-3.5), the jumps (`jump_vy` 12.0-13.0 and 9.5-10.5).

Never change a number the spec fixes (health, walk, damage, cooldowns, BOX_SPLIT, 1.5 s, the
50/50s), the older three fighters, or `BAR`. If the bar still fails, stop and report the
`tools/balance.py` table to the user instead of loosening anything.

- [ ] **Step 5: `tools/balance.py`:**

```python
"""Bot-against-bot win rates for every pairing of fighters, from both sides.

    cd brawl-ket && uv run python tools/balance.py [SEEDS]

For each pair, the share of the decided rounds each fighter won, over SEEDS seeds from each
side (200 by default). The bar (docs/superpowers/specs/2026-10-21-brawl-ket-erwin-dos-design.md,
section 6): no fighter wins more than about 60% against another. tests/test_balance.py holds
every pairing with ERWIN or DOS to it; the older three's pairings are only reported here.
"""

from __future__ import annotations

import itertools
import sys

from brawl_ket.bot import Bot
from brawl_ket.config import ROUND_FRAMES
from brawl_ket.fight import Fight
from brawl_ket.moves import CHARACTERS

BAR = 0.60


def winner(seed: int, p1: str, p2: str) -> str | None:
    fight = Fight({"p1": CHARACTERS[p1], "p2": CHARACTERS[p2]}, seed=seed)
    bots = {"p1": Bot("p1", seed), "p2": Bot("p2", seed + 1000)}
    for _ in range(2 * ROUND_FRAMES):
        if fight.over:
            break
        fight.step({k: b.input(fight) for k, b in bots.items()})
    return fight.winner


def share(a: str, b: str, seeds) -> float:
    """a's share of the decided rounds against b, playing each seed from both sides."""
    won = lost = 0
    for seed in seeds:
        for p1, p2 in ((a, b), (b, a)):
            w = winner(seed, p1, p2)
            if w is None:
                continue
            if (w == "p1") == (p1 == a):
                won += 1
            else:
                lost += 1
    return won / max(1, won + lost)


def main(argv: list[str]) -> None:
    n = int(argv[0]) if argv else 200
    for a, b in itertools.combinations(CHARACTERS, 2):
        s = share(a, b, range(n))
        flag = "" if 1 - BAR <= s <= BAR else "   <- over the bar"
        print(f"{a:>6} v {b:<6}  {a} {s:4.0%}  {b} {1 - s:4.0%}{flag}")


if __name__ == "__main__":
    main(sys.argv[1:])
```

Run: `uv run python tools/balance.py`
Expected: ten lines; every pairing with ERWIN or DOS within 40-60%. A prototype of this plan
measured, at 200 seeds a side:

```
ROBERT v BOHR    ROBERT  34%  BOHR  66%   <- over the bar
ROBERT v PHOEBE  ROBERT  60%  PHOEBE  40%
ROBERT v ERWIN   ROBERT  56%  ERWIN  44%
ROBERT v DOS     ROBERT  49%  DOS  51%
  BOHR v PHOEBE  BOHR  66%  PHOEBE  34%   <- over the bar
  BOHR v ERWIN   BOHR  58%  ERWIN  42%
  BOHR v DOS     BOHR  54%  DOS  46%
PHOEBE v ERWIN   PHOEBE  44%  ERWIN  56%
PHOEBE v DOS     PHOEBE  46%  DOS  54%
 ERWIN v DOS     ERWIN  51%  DOS  49%
```

Copy the real output into the task report: the two older pairings over the bar (unchanged by
this plan) are for the user to decide on.

- [ ] **Step 6: The frame budget**

Run: `uv run python tools/benchmark.py`
Expected: 25 pairings plus `title + demo`. Every pairing with ERWIN or DOS has a mean of at
most 0.65 ms and a p99 of at most 1.0 ms on the dev machine (the older pairings ran at
0.22-0.32 ms mean, 0.38 ms p99, which was 3-4 ms on the cabinet: about 12x). A prototype of
this plan measured 0.36-0.49 ms mean and 0.59-0.81 ms p99 for them. If one is over, profile it
(`uv run python -m cProfile -s cumtime tools/benchmark.py | head -40`) and cache the drawing
that dominates; don't drop anything from the approved look. If the cabinet is reachable, also
run the README's on-cabinet benchmark and put its numbers in the report.

The `max` column will show a one-off spike (about 6 ms on the dev machine) the first time a
box sprite or a screen face is built. If that shows as a hitch on the cabinet when ERWIN first
boxes, build her boxes when the fight starts instead: in `Renderer.draw_fight`, inside
`if fight is not self._fight:`, add

```python
            for f in fight.fighters.values():   # THE BOX's sprites now, not mid-round
                if f.char.build == "cat":
                    for fur in BASIS_BODY.values():
                        for facing in (1, -1):
                            for phase in range(HOLO_PHASES):
                                holo_sprite(fur, facing, phase)
```

(importing `HOLO_PHASES` and `holo_sprite` from `.erwin`).

- [ ] **Step 7: README Setup.** After the `tools/benchmark.py` line:

```bash
uv run python tools/balance.py                      # bot-against-bot win rates for every pairing
```

- [ ] **Step 8: Run the whole suite and the lint**

Run: `uv run pytest -q && uvx --from 'ruff==0.15.22' ruff check src tests tools`
Expected: all pass, `All checks passed!`; check every touched file is LF (`file src/brawl_ket/*.py tests/*.py tools/*.py README.md`).

- [ ] **Step 9: Commit**

```bash
git add src/brawl_ket/bot.py tests/test_bot.py tests/test_match.py tests/test_balance.py tools/balance.py README.md
git commit -m "feat: :robot: Brawl-Ket: bots for ERWIN and DOS, and the 60% balance bar

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

## Self-review

**Spec coverage** (section by section, the task that implements it):
- 1, the looks: ERWIN's build, cat legs, fur, accents, lit limb, the superposed boxes and the
  collapse (Task 2, pixel-checked against the look); DOS's case, 3/4 view, face and angry face,
  ribbed arms from the sides, `CASE_TILT`, always green, FLOPPY's disk, BLUE SCREEN's blue face
  and green ring (Task 4, pixel-checked). The look scripts keep running (Task 2 Step 7).
- 2, ERWIN: health, walk, jump, shared normals (Task 1); THE BOX's split, clamp, no body,
  self-collapse by press / new direction / 1.5 s with the swipe, the measurement by strikes,
  shots, throws and fields, the colour rule, "free at once", the cooldown from the collapse,
  Y while superposed (Task 1); POUNCE and SCRATCH (Task 1); the seeded `Fight` and `Match`'s
  seeds (Task 1).
- 3, DOS: stats and always Z, MEASURE, the badge (automatic: his basis never changes) (Task 3);
  COPY / PASTE, the clipboard, "only when free", cleared per round (Task 3); FLOPPY, BLUE
  SCREEN, CRT DROP (Task 3).
- 4, interactions: shots into a box (Task 1, and a PASTE, Task 3); throws and MEASURE on a box
  (Task 1: MEASURE goes through the same strike path, and `measured_into` collapses her basis);
  CHARGE NOISE (Task 1); TUNNEL past a boxed ERWIN (Task 1); COPY against FLOPPY (Task 3);
  HADAMARD DIVE against DOS (unchanged code: the dive switches its owner; DOS's `switch()` is a
  no-op, Task 3).
- 5, screens and HUD: roster order and the two panels (Task 5), the clipboard icon (Task 4),
  HOW TO PLAY unchanged, the nine sounds (Task 5).
- 6, bots: both fighters' rules, the demo picking from five, the 60% bar (Task 6).
- 7, testing: every bullet has a test in `tests/test_erwin.py`, `tests/test_dos.py`,
  `tests/test_render.py`, `tests/test_match.py`, `tests/test_bot.py`, `tests/test_balance.py`;
  snapshots (Tasks 2, 4, 5); the benchmark (Task 6).

**Prototype run.** Every task's code and tests in this plan were applied, in order, to a
scratch copy of `brawl-ket/` while the plan was written: after Task 6 the whole suite passed
(1,526 tests, ruff clean), `tools/snapshot.py` wrote every frame, and the numbers above (DOS's
8-frame jabs, `BOX_DANGER = 60`, `POUNCE_RANGE`, the bots standing up after BLUE SCREEN and
POUNCE, the 50 px shot in the boxing test, THE BOX's 4 recovery frames) are the fixes that run
found. The only failure on the way is the expected `test_neither_side_is_favoured[(ROBERT, ERWIN)]`
between Task 1 and Task 6.

**Type and name consistency:** `Fighter.collapse(k, swipe, events)` (Task 1) is called the same
way by `Fight._measure`; `_Strike.box` is set by `_touch` in all three collection paths;
`draw_puppet`'s `strike`, `mood`, `led`, `eject` (Task 2) are what Task 4's DOS branch passes
to `draw_dos(surf, j, facing, case, strike, led, mood, eject)`; `Fighter.clipboard` is
`(Move, basis str)` everywhere (fight, render, bot, tests); events and cues (`box_split`,
`box_collapse`, `copy`, `pounce`, `scratch`, `floppy`, `blue_screen`, `crt_drop`, `paste`) are
spelled the same in moves, fighter, fight, render, audio and the tests.
