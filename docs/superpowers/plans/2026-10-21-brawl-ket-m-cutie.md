# Brawl-Ket: M-CUTIE Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add the sixth fighter, M-CUTIE (the hardware fighter: AMPLITUDE AMPLIFICATION, ION TRAP
and SPIN), to Brawl-Ket as specified in `docs/superpowers/specs/2026-10-21-brawl-ket-m-cutie-design.md`,
drawn as the approved look (variant B, the cage) of
`docs/superpowers/specs/2026-10-21-brawl-ket-m-cutie-look.py`.

**Architecture:**
- **Rules first, pure and tested:** `moves.py` gets her character, six wave moves (one per
  charge step) and a trap's hold move, and four new `Move` / `Projectile` fields; `fighter.py`
  gets the charge (a `"charging"` action, like ERWIN's `"boxed"`), SPIN's hover with a forward
  speed and its floor recovery, and a trap's hold; `fight.py` gets traps as a new kind of object
  beside shots (`Trap`, `Fight.traps`), a wave that runs along the floor (and stays there when
  pasted) and cancels any rival shot it meets.
- **Drawing in a new module, `cutie.py`,** as `erwin.py` and `dos.py` before it: her look's own
  code (variant B only), checked pixel for pixel against the look script by importing it in the
  tests. Her head, her wave and her trap are drawn once into small cached layers (a see-through
  layer and an additive "spill" layer for the light their glows throw on bare pixels), anchored at
  the same pixel parity as where they are blitted, so the cache gives exactly the same pixels as
  drawing them. The charge's halo (the look blends a silhouette 16 times over a full-screen layer)
  becomes one cached layer, within one colour step of the look.
- **Then the screens, the sounds and the bot,** as for ERWIN and DOS. CHOOSE YOUR FIGHTER needs a
  real layout change: her portrait starts a second row, which collides with the move lists as
  the screen is drawn today (checked by rendering it), so the tiles shrink and the lists move up.

**Tech Stack:** Python 3.11, pygame 2.5.2, uv, pytest, ruff 0.15.22. All commands run from
`brawl-ket/`.

## Global Constraints

- `requires-python = ">=3.11,<3.12"`; `pygame==2.5.2` exactly. No new dependencies.
- LF line endings in every file (`file <path>` must not say CRLF).
- The simulation counts integer frames at 60 Hz; seconds appear only through `config.frames()`.
- On-screen text is ASCII capitals (Press Start 2P has no Unicode minus, no kets).
- Nothing in the v3 rules changes: colour must match to hurt; A is your colour and B the other;
  throws are Y and hurt either colour; every special is in her own colour; her Y switches her
  colour, as everyone's does.
- Her controls are everyone's: X, down + X and air X. No up + X.
- M-CUTIE: health 105; walk 1.8; jump in the middle (`jump_vy` about 11.5); normals and throws
  shared with everyone; build `"cutie"`, a little shorter than PHOEBE in the body and legs, head
  radius 15, 12 px limbs.
- AMPLITUDE AMPLIFICATION (X, her colour, 2 s cooldown after it fires): the first X starts it,
  each further X press grows the wave by one step, up to 6; she stands still while charging; it
  fires about 0.25 s after her last press, or at once on reaching 6; about 3.5 px a frame;
  steps 1 to 6 are 20 / 28 / 36 / 44 / 52 / 60 px tall and deal 7 / 8 / 10 / 11 / 13 / 15; MID;
  hit while charging, the charge is lost; the name shows in full where it fits, and as
  "AMP. AMPLIFICATION" on the select screen's move list.
- ION TRAP (down + X, her colour, 1 s cooldown): about 70 px in front of her; arms after about
  0.3 s (drawn dim until then); a rival on the ground who steps in is held for about half a
  second, with 4 damage if the colour matches (a wrong-colour trap holds without hurting); used
  up then; a jump clears it; at most two at once, a third replaces the oldest; gone at the end
  of a round, after 10 s, or when she is knocked down.
- SPIN (air X, her colour, once per jump): she stops falling and spins forward at her height,
  about 100 px, one leg out; up to three hits of 4, MID; then she drops; a miss lands into a short
  recovery.
- Interactions: DOS's COPY catches her wave and PASTE fires it at the size it was caught; her
  wave and a PHOTON, FLOPPY or LASER cancel, whatever the wave's size; a trap under a superposed
  ERWIN closes on a box (a measurement, 50/50); PHOEBE has no body while TUNNEL has her gone, so a
  trap stays armed; DOS's MOUSE CABLE: a rival pulled over a trap is caught if they end up
  standing in it; BOHR's MEASURE collapses her colour as anyone's.
- Screens: her portrait starts CHOOSE YOUR FIGHTER's second row (`ROSTER_COLS = 5`); trait
  "PATIENT AND TECHNICAL"; specials AMP. AMPLIFICATION, ION TRAP, SPIN; the charge shown on her
  and as pips above her head; sounds: a rising blip per charge step, a whoosh deeper for a bigger
  wave, a click and hum when a trap is set, a snap when it closes, a whirr for SPIN.
- Bots: `bot.py` learns her and the title demo plays her; her pairings are held to the 60% bar
  (`tests/test_balance.py`, `tools/balance.py`).
- The look: variant B with B's own face; the game reproduces it pixel for pixel.
- Cabinet conventions (`../AGENTS.md`): A = raw 1, B = 2, X = 0, Y = 3, Start = 9, Select = 8;
  P1 blue ring, P2 red ring. Brawl-Ket ran at about 3-4 ms a frame on the cabinet; her art must
  stay within the Pi's frame budget.
- **Done means, for every task:** `uv run pytest -q` passes, and
  `uvx --from 'ruff==0.15.22' ruff check src tests tools` is clean.
- **Commits:** on a feature branch (`git switch -c brawl-ket-m-cutie` before Task 1, never on
  `main`), gitmoji style (`feat: :sparkles: Brawl-Ket: ...`), staging explicit paths only, each
  message ending with `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.

## Decisions this plan takes where the spec says "about"

| Spec | Plan value | Why |
|---|---|---|
| jump in the middle, `jump_vy` about 11.5 | 11.5, gravity 0.5 | an apex of 132 px, between DOS's 91 and ERWIN's 156 (PHOEBE's height) |
| normals and throws "shared with everyone" | ROBERT's seven normal `Move`s, the same objects (as ERWIN's) | her skeleton is within a few px of ROBERT's (head 129 px up, his 135): `test_the_striking_limb_reaches_the_hitbox_on_impact` holds for all seven |
| her hurtboxes | stand `Box(-16, 0, 32, 116)`, crouch `Box(-18, 0, 36, 92)` | her drawn head's centre is 129 px up standing, 92 crouched (the crouch box reaches it, as everyone's); 4 px wider than ROBERT's, as her cage skirt is 60 px across at its hem. 36 px tipped DOS's pairing the other way (she won only 39% against him) |
| fires "about 0.25 s" after her last press | `CHARGE_WAIT = frames(0.25)` (15), `CHARGE_CAP = 6` | the wave's own move then starts: startup 3, active 1, recovery 16, so the shot leaves 18 frames after the last press |
| the wave, "about 3.5 px a frame" | `Projectile(3.5, Box(-w // 2, 0, w, h), 180, floor=True)`, `w = 2 * round((12 + 0.42 h) / 2)` (20 to 38 px), hitstun 18, knockback 3.0 | 180 frames cross the stage; the box is the drive pulse's bright middle as the look draws it; PHOTON's hitstun and knockback |
| COPY catches the wave "like any shot" | COPY's window `Box(14, 20, 40, 110)` becomes `Box(14, 16, 40, 114)` | a 1-step wave is 20 px tall and passed under the old window; 16 stays above the mouse's 16 px top, so MOUSE CABLE still can't be copied |
| PASTE "at the size it was caught" | the same move (its height and damage), on the floor, at `PASTE_SPEED` (4.0) | a pasted wave stays a floor wave; it flies at least `PASTE_SPEED`, as every paste already does |
| the wave cancels other shots "whatever its size" | a floor wave cancels a rival shot that overlaps its whole column, floor to sky | a PHOTON flies at 56-70 px, over a 20 px wave |
| ION TRAP | startup 10, active 1 (the trap appears), recovery 14; `TRAP_REACH = 70`; `TRAP_ARM = frames(0.3)` (18); `TRAP_LIFE = frames(10.0)`; `TRAP_MAX = 2` | |
| the hold, "about half a second" | `TRAP_HOLD`: `Box(-18, 0, 36, 26)` round the trap's x (between its electrodes, as drawn), LOW, 4 damage, hitstun 30, knockback 0, `hold=True` (no push, hurt or not) | LOW: a jump clears it; the colour rule decides the damage, not the hold |
| who a trap catches | a rival on the ground and free (not in hitstun or knockdown, not getting up, not tunnelling); never its owner | the MOUSE CABLE row: a rival reeled across a trap is caught once they come to rest in it, not on the way |
| SPIN, "about 100 px" | startup 4, active 24, recovery 10, `lunge=4.0` (96 px), `hit_every=8`, `Box(6, 34, 66, 34)`, hitstun 10, knockback 1.0, `hover`, `once_per_jump`, `floor_recovery` | hits on active frames 0, 8 and 16 at most: three; hitstun 10 holds the rival for the next; after the active frames she drops straight down and the recovery waits for the floor ("a miss lands into a short recovery"). A startup of 8 was tried: her bot then can't SPIN BOHR out of MEASURE |
| the charge's glow "a little more with every step" | `bright = min(1, steps / 5)` (the skirt), halo strength `steps / 4` | the look's sheet shows 4 steps with 0.8 and 1.0 |
| her hair in a jump | `JUMP_SWING = 6` while in the air, 0 on the floor | the look's jump; following her speed (as PHOEBE's coat does) gave the cached head hundreds of shapes |

The bot's numbers are in Task 4 (its constants block); every one was measured there.

More choices, flagged in the final report:
- **CHOOSE YOUR FIGHTER's layout changes.** Drawn as it is today, a second row of 56 px
  portraits sits right over both move lists (checked by rendering the screen with a sixth
  fighter). Task 3 makes the tiles 40 px (two rows fit under the lists), moves each side up 10 px
  (`SIDE_FLOOR` 178 to 168), puts the 1P / 2P tags inside the tiles' top corners, widens the list
  to 252 px (so "AMP. AMPLIFICATION", 18 letters, clears its colour chip) with lines 10 px apart,
  and moves the button hint 5 px down. `ROSTER_COLS` stays 5.
- **M-CUTIE against PHOEBE is over the bar: about 65% over 400 rounds, for the user to decide.**
  Measured in Task 4: with the health (105) and walk (1.8) the spec fixes she plays PHOEBE as
  ROBERT does (60%) with 5 more health; with none of her specials at all it is still 61.5%. No
  bot behaviour, frame number or hurtbox width moved it below 62% (health 100 would: 60%). Her
  other four pairings are 49-56%. `tests/test_balance.py` holds them, and marks this one pairing
  as a non-strict `xfail` naming it; `tools/balance.py` prints it flagged.
- **A trap never catches its owner.** In the only pairing where MOUSE CABLE meets a trap (DOS
  against M-CUTIE) the rival DOS pulls is the trap's owner, so the spec's row there reads as the
  general rule above; DOS dragging her across her own trap springs nothing (tested).
- **A trap closes on ERWIN's box either way.** If the measurement finds him in the other box, it
  closes on nothing (used up, `held` is None).
- **Her bot never jumps to SPIN at a rival standing on the ground.** At one chance in 2,000
  frames it made her win 53-67% against each of the five, at one in 1,000 56-72% (no bot answers
  a SPIN from the air), so it SPINs
  at a rival in the air (the spec's own game plan: "SPIN ... catches them in the air") and out of a
  dashing grab winding up close by.

## File Structure

| File | Responsibility after this plan |
|---|---|
| `src/brawl_ket/config.py` | + `CHARGE_CAP`, `CHARGE_WAIT`, `TRAP_REACH`, `TRAP_ARM`, `TRAP_LIFE`, `TRAP_MAX` |
| `src/brawl_ket/moves.py` | `Projectile` + `floor`; `Move` + `charge`, `trap`, `hold`, `floor_recovery`; `AMP_STEPS`, `AMP_WAVES`, `TRAP_HOLD`, `M_CUTIE`; COPY's window 4 px lower |
| `src/brawl_ket/fighter.py` | the `"charging"` action (`charge`, `charge_wait`, `_start_charge`, `_charging`), a hold's push, SPIN's hover with a lunge and its floor recovery, the trap event |
| `src/brawl_ket/fight.py` | `Trap` and `Fight.traps` (set, armed, caught, closed, gone), the floor wave's PASTE and cancel (`_cancel_box`) |
| `src/brawl_ket/poses.py` | the `"cutie"` build; poses `"charge"`, `"place"`, `"spin"`; `"charging"` shows `"charge"` |
| `src/brawl_ket/cutie.py` (new) | her look: `draw_cutie`, `draw_charging`, `draw_spin`, `draw_wave`, `draw_trap` and the look's own functions they are built from, with their cached layers |
| `src/brawl_ket/render.py` | dispatches her build, the charge and SPIN; traps on the floor, the wave, the snap; CHOOSE YOUR FIGHTER's two-row layout, her trait and `move_label` |
| `src/brawl_ket/audio.py` | 16 new sounds |
| `src/brawl_ket/bot.py` | her rules (`_cutie`, `_charging`, SPIN only in a jump made for it) |
| `src/brawl_ket/match.py` | the `ROSTER` comment |
| `tests/test_cutie.py` (new) | her rules and every interaction |
| `tests/test_render.py`, `test_moves.py`, `test_poses.py`, `test_match.py`, `test_audio.py`, `test_bot.py`, `test_balance.py` | her look against the look script, the screens, the data, the bot, the bar |
| `tools/snapshot.py`, `tools/balance.py` | her frames to check by eye; the bar's docstring |
| `README.md` | six fighters |

---

### Task 1: M-CUTIE's rules: the charge, the wave, traps and SPIN

**Files:**
- Create: `tests/test_cutie.py`
- Modify: `src/brawl_ket/config.py`, `src/brawl_ket/moves.py`, `src/brawl_ket/poses.py`,
  `src/brawl_ket/fighter.py`, `src/brawl_ket/fight.py`
- Modify (to keep the rest running): `src/brawl_ket/audio.py` (`EVENT_SOUNDS`),
  `src/brawl_ket/render.py` (`TORSO_EXTRA`, `PLATES`: a stand-in until Task 2),
  `src/brawl_ket/match.py` (a comment), `tools/snapshot.py` (`ACCENTS`)
- Modify: `tests/test_moves.py`, `tests/test_poses.py`, `tests/test_match.py`, `tests/test_balance.py`

**Interfaces:**
- Consumes: nothing new.
- Produces (later tasks rely on these exact names):
  - `config.CHARGE_CAP = 6`, `config.CHARGE_WAIT = frames(0.25)` (15), `config.TRAP_REACH = 70`,
    `config.TRAP_ARM = frames(0.3)` (18), `config.TRAP_LIFE = frames(10.0)` (600), `config.TRAP_MAX = 2`
  - `Projectile.floor: bool = False`; `Move.charge: tuple[Move, ...] = ()`, `Move.trap: Move | None = None`,
    `Move.hold: bool = False`, `Move.floor_recovery: bool = False`
  - `moves.AMP_STEPS` (six `(height, damage)`), `moves.AMP_WAVES` (six `Move`s named
    `"AMPLITUDE AMPLIFICATION"`, cues `"wave1"` to `"wave6"`), `moves.TRAP_HOLD`, `moves.M_CUTIE`
    (name `"M-CUTIE"`, build `"cutie"`, `moves["stand.X"].charge is AMP_WAVES`, `moves["crouch.X"].trap is TRAP_HOLD`,
    `moves["air.X"].name == "SPIN"`); `CHARACTERS` ends with `"M-CUTIE"`
  - poses `"charge"`, `"place"`, `"spin"`; `BUILD_BONES["cutie"]`, `SCALE["cutie"] = 2.1`,
    `HEAD_R["cutie"] = 15`, `LIMB_W["cutie"] = 12`; `pose_for` shows `"charge"` while `"charging"`
  - `Fighter.charge: int` (steps so far, 0 when not charging), `Fighter.charge_wait: int`,
    the action `"charging"`; fighter events `"charge1"` to `"charge6"` and `("trap", {"move": m})`
  - `fight.Trap(owner: str, move: Move, x: float, basis: str, age: int = 0, closed: int = 0, held: str | None = None)`
    with `.armed -> bool`, `.state -> "arming" | "armed" | "closed"`, `.box -> Rect`;
    `Fight.traps: list[Trap]` (oldest first); event `"trap_close"` (`player`: who it closed on, None for
    an empty box; `x`: the trap's x); move cues `"trap_set"`, `"spin"`; `fight._cancel_box(s: Shot) -> Rect`

- [ ] **Step 1: Write the failing tests for her rules.** Create `tests/test_cutie.py`:

```python
"""M-CUTIE (docs/superpowers/specs/2026-10-21-brawl-ket-m-cutie-design.md, sections 2, 3 and 6):
AMPLITUDE AMPLIFICATION charges a step per X press and fires a wave along the floor, taller and
harder with every step, lost if she is hit while charging; ION TRAP sets a trap on the floor that
arms, then closes on a rival who steps in and holds them; SPIN hangs at her height and spins
forward, hitting up to three times. And how they meet the others' specials."""

import random

import pytest

from brawl_ket import basis
from brawl_ket.basis import X_BASIS, Z_BASIS
from brawl_ket.config import CHARGE_CAP, CHARGE_WAIT, STAGE_RIGHT, TRAP_ARM, TRAP_LIFE, TRAP_MAX, TRAP_REACH
from brawl_ket.fight import Fight, Shot, Trap
from brawl_ket.fighter import IDLE, FighterInput
from brawl_ket.moves import AMP_STEPS, AMP_WAVES, BOHR, DOS, ERWIN, M_CUTIE, PHOEBE, ROBERT, TRAP_HOLD

X = FighterInput(x=True)
DOWN_X = FighterInput(down=True, x=True)
UP = FighterInput(up=True)
AMP, TRAP, SPIN = (M_CUTIE.moves[s] for s in ("stand.X", "crouch.X", "air.X"))
PHOTON, LASER = ROBERT.moves["stand.X"], PHOEBE.moves["air.X"]
FLOPPY, MOUSE, COPY = DOS.moves["stand.X"], DOS.moves["crouch.X"], DOS.extra["copy"]
FIRE = AMP_WAVES[0].startup     # frames from the wave move's start to the shot


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


def mash(fight, steps, gap=4):
    """M-CUTIE (p1) presses X `steps` times, `gap` frames apart, then lets go; returns the
    events up to the frame her wave leaves (or 60 frames after the last press)."""
    events = []
    for i in range((steps - 1) * gap + 1):
        events += step(fight, FighterInput(x=i % gap == 0))
    for _ in range(60):
        if fight.shots:
            break
        events += step(fight)
    return events


def heads_seed(heads: bool) -> int:
    """A fight seed whose first 50/50 comes up heads (random() < 0.5) or tails."""
    return next(s for s in range(100) if (random.Random(s).random() < 0.5) == heads)


def set_trap(fight, key="p1"):
    """M-CUTIE (`key`) sets a trap and is stepped until it is armed; returns it."""
    other = "p2" if key == "p1" else "p1"
    step(fight, **{key: DOWN_X, other: IDLE})
    for _ in range(TRAP.startup + TRAP_ARM + 2):
        step(fight, **{key: FighterInput(down=True), other: IDLE})
    (trap,) = fight.traps
    assert trap.armed
    return trap


# --- AMPLITUDE AMPLIFICATION: the charge --------------------------------------------------------


def test_x_starts_a_charge_of_one_step_and_she_stands_still():
    fight = versus(M_CUTIE, ROBERT, 300)
    me = fight.fighters["p1"]
    events = step(fight, X)
    x0 = me.x
    for _ in range(5):
        events += step(fight, FighterInput(dx=1, up=True))   # no walking, no jumping
    assert me.action == "charging" and me.charge == 1 and "charge1" in kinds(events)
    assert me.x == x0 and me.y == 0 and fight.shots == []


def test_each_press_is_a_step_and_the_sixth_fires_at_once():
    fight = versus(M_CUTIE, ROBERT, 400)
    me = fight.fighters["p1"]
    events = []
    for n in range(1, CHARGE_CAP):
        events += step(fight, X)
        events += step(fight)
        assert me.action == "charging" and me.charge == n
    events += step(fight, X)                               # the sixth: no waiting
    assert me.action == "attack" and me.move is AMP_WAVES[-1] and me.charge == 0
    assert [k for k in kinds(events) if k.startswith("charge")] == [f"charge{n}" for n in range(1, 7)]


def test_the_wave_leaves_when_15_frames_pass_without_a_press():
    fight = versus(M_CUTIE, ROBERT, 400)
    me = fight.fighters["p1"]
    step(fight, X)
    for _ in range(10):
        step(fight)
    step(fight, X)                                         # a second step resets the wait
    for _ in range(CHARGE_WAIT - 1):
        step(fight)
    assert me.action == "charging" and me.charge == 2
    step(fight)                                            # the 15th frame without one: it fires
    assert me.action == "attack" and me.move is AMP_WAVES[1]
    for _ in range(FIRE):
        step(fight)
    (shot,) = fight.shots
    assert shot.move is AMP_WAVES[1]


@pytest.mark.parametrize("steps", range(1, 7))
def test_every_step_makes_the_wave_taller_and_harder(steps):
    height, damage = AMP_STEPS[steps - 1]
    fight = versus(M_CUTIE, ROBERT, 300)
    rival = fight.fighters["p2"]
    mash(fight, steps)
    (shot,) = fight.shots
    assert shot.move.projectile.box.h == height and shot.move.damage == damage
    events = []
    for _ in range(120):
        events += step(fight)
    assert kinds(hits_on(events, "p2")) == ["hit"] and rival.health == ROBERT.health - damage


def test_the_table_grows_every_step():
    heights, damages = zip(*AMP_STEPS)
    assert heights == (20, 28, 36, 44, 52, 60) and damages == (7, 8, 10, 11, 13, 15)
    assert [w.projectile.box.h for w in AMP_WAVES] == list(heights)
    assert [w.damage for w in AMP_WAVES] == list(damages)


def test_a_hit_while_charging_loses_the_charge():
    fight = versus(M_CUTIE, ROBERT, 50)
    me = fight.fighters["p1"]
    step(fight, X)
    step(fight, X)
    events = []
    for i in range(40):
        events += step(fight, FighterInput(x=i < 6 and i % 3 == 0), FighterInput(a=i == 0))
    assert kinds(hits_on(events, "p1"))[0] == "hit" and me.charge == 0
    assert not fight.shots and me.cooldowns.get("stand.X", 0) == 0     # it never fired


def test_the_cooldown_runs_from_the_fire():
    fight = versus(M_CUTIE, ROBERT, 400)
    me = fight.fighters["p1"]
    step(fight, X)
    for _ in range(CHARGE_WAIT - 1):
        step(fight)
        assert me.cooldowns.get("stand.X", 0) == 0
    step(fight)
    assert me.cooldowns["stand.X"] == AMP.cooldown == 120


def test_the_wave_runs_along_the_floor_a_little_slower_than_a_photon():
    fight = versus(M_CUTIE, ROBERT, 400)
    me = fight.fighters["p1"]
    mash(fight, 3)
    (shot,) = fight.shots
    assert shot.y == 0 and shot.vx == 3.5 == AMP.projectile.speed < PHOTON.projectile.speed
    assert shot.facing == me.facing


def test_its_colour_is_fixed_when_it_fires():
    fight = versus(M_CUTIE, ROBERT, 400)
    me = fight.fighters["p1"]
    step(fight, X)
    step(fight, FighterInput(y=True))          # purple while charging: the wave fires purple
    for _ in range(CHARGE_WAIT + FIRE + 2):
        step(fight)
    (shot,) = fight.shots
    assert me.basis == X_BASIS and shot.basis == X_BASIS
    step(fight, FighterInput(y=True))          # a switch after it fired changes nothing
    assert shot.basis == X_BASIS


def test_a_crouch_never_ducks_it():
    fight = versus(M_CUTIE, ROBERT, 160)
    mash(fight, 1)
    events = []
    for _ in range(60):
        events += step(fight, IDLE, FighterInput(down=True))
    assert kinds(hits_on(events, "p2")) == ["hit"]


@pytest.mark.parametrize("steps,hit", [(1, False), (6, True)])
def test_a_rival_30_px_up_clears_a_small_wave_but_not_a_big_one(steps, hit):
    fight = versus(M_CUTIE, ROBERT, 300)
    rival = fight.fighters["p2"]
    rival.y, rival.action = 30.0, "jump"        # rising off the floor, 30 px up
    wave = AMP_WAVES[steps - 1]
    fight.shots.append(Shot("p1", wave, rival.x - 40, 0.0, wave.projectile.speed, 60))
    events = []
    for _ in range(5):
        events += step(fight)
    assert bool(hits_on(events, "p2")) == hit


@pytest.mark.parametrize("move,y,vy", [(PHOTON, 0.0, 0.0), (FLOPPY, 0.0, 0.0), (LASER, 60.0, -14.0)])
def test_her_smallest_wave_cancels_a_rival_shot_passing_over_it(move, y, vy):
    fight = versus(M_CUTIE, DOS, 400)
    mash(fight, 1)
    (wave,) = fight.shots
    fight.shots.append(Shot("p2", move, wave.x + 30, y, -abs(move.projectile.speed), 60, "Z", vy))
    for _ in range(10):
        step(fight)
    assert fight.shots == []


def test_dos_copies_her_wave_and_pastes_it_along_the_floor_at_its_size():
    fight = versus(M_CUTIE, DOS, 200)
    cutie, dos = fight.fighters["p1"], fight.fighters["p2"]
    mash(fight, 4)
    events = []
    for _ in range(80):
        if dos.clipboard is not None:
            break
        near = fight.shots and abs(fight.shots[0].x - dos.x) < 60
        events += step(fight, IDLE, FighterInput(y=bool(near) and dos.action != "attack"))
    assert dos.clipboard == (AMP_WAVES[3], Z_BASIS) and "copy" in kinds(events)
    for _ in range(30):
        step(fight)
    step(fight, IDLE, FighterInput(y=True))     # PASTE
    for _ in range(10):
        step(fight)
    (shot,) = fight.shots
    assert shot.owner == "p2" and shot.move is AMP_WAVES[3] and shot.y == 0 and shot.vx < 0
    assert cutie.health == M_CUTIE.health


def test_copy_catches_even_the_smallest_wave():
    assert COPY.catch.y < AMP_STEPS[0][0] and COPY.catch.y >= MOUSE.projectile.box.y + MOUSE.projectile.box.h
    fight = versus(DOS, M_CUTIE, 300)
    dos = fight.fighters["p1"]
    wave = AMP_WAVES[0]
    fight.shots.append(Shot("p2", wave, dos.x + 60, 0.0, -wave.projectile.speed, 100))
    for i in range(20):
        step(fight, FighterInput(y=i == 0))
    assert dos.clipboard == (wave, Z_BASIS)


# --- ION TRAP -----------------------------------------------------------------------------------


def test_down_x_sets_a_trap_70_px_in_front_in_her_colour():
    fight = versus(M_CUTIE, ROBERT, 300)
    me = fight.fighters["p1"]
    me.basis = X_BASIS
    events = step(fight, DOWN_X)
    for _ in range(TRAP.startup):
        events += step(fight, FighterInput(down=True))
    (trap,) = fight.traps
    assert (trap.owner, trap.x, trap.basis, trap.state) == ("p1", me.x + TRAP_REACH, X_BASIS, "arming")
    assert "trap_set" in kinds(events) and TRAP.cooldown == 60 and me.cooldowns["crouch.X"] > 0


def test_it_arms_18_frames_after_it_is_set_and_cannot_catch_before():
    fight = versus(M_CUTIE, ROBERT, 300)
    rival = fight.fighters["p2"]
    step(fight, DOWN_X)
    for _ in range(TRAP.startup - 1):
        step(fight, FighterInput(down=True))
    rival.x = fight.fighters["p1"].x + TRAP_REACH       # standing right where it lands
    step(fight, FighterInput(down=True))                # set (and arming) on this frame
    (trap,) = fight.traps
    events = []
    for _ in range(TRAP_ARM - 1):
        assert trap.state == "arming"
        events += step(fight)
    assert hits_on(events, "p2") == [] and trap.armed
    events = step(fight)
    assert kinds(hits_on(events, "p2")) == ["hit"] and trap.state == "closed"


def test_it_closes_on_a_rival_who_walks_in_and_holds_them():
    fight = versus(M_CUTIE, ROBERT, 300)
    rival = fight.fighters["p2"]
    trap = set_trap(fight)
    events = []
    for _ in range(150):
        ev = step(fight, IDLE, FighterInput(dx=-1))
        events += ev
        if "trap_close" in kinds(ev):
            break
    held_at = rival.x
    assert kinds(hits_on(events, "p2")) == ["hit"] and rival.health == ROBERT.health - TRAP_HOLD.damage
    assert rival.action == "hitstun" and rival.stun == TRAP_HOLD.hitstun == 30 and rival.vx == 0
    for _ in range(25):
        step(fight, IDLE, FighterInput(dx=-1))
    assert rival.x == held_at and trap.held == "p2" and trap.state == "closed"


def test_a_trap_of_the_other_colour_holds_but_does_not_hurt():
    fight = versus(M_CUTIE, ROBERT, 300)
    rival = fight.fighters["p2"]
    rival.basis = X_BASIS
    set_trap(fight)
    events = []
    for _ in range(150):
        events += step(fight, IDLE, FighterInput(dx=-1))
    assert kinds(hits_on(events, "p2")) == ["block"] and rival.health == ROBERT.health
    assert "trap_close" in kinds(events)


def test_a_jump_clears_it():
    fight = versus(M_CUTIE, ROBERT, 140)
    trap = set_trap(fight)
    rival = fight.fighters["p2"]
    events = []
    for i in range(40):
        events += step(fight, IDLE, FighterInput(up=i == 0, dx=-1 if i == 0 else 0))
        if rival.y == 0 and i:
            break
    assert hits_on(events, "p2") == [] and trap.armed and rival.x < trap.x   # over it


def test_a_trap_is_used_up_and_never_catches_her():
    fight = versus(M_CUTIE, ROBERT, 300)
    me, rival = fight.fighters["p1"], fight.fighters["p2"]
    trap = set_trap(fight)
    me.x = trap.x                               # her own trap: nothing
    for _ in range(5):
        step(fight)
    assert trap.armed and me.action != "hitstun"
    me.x = 220
    rival.x = trap.x
    step(fight)
    assert trap.state == "closed"
    for _ in range(TRAP_HOLD.hitstun + 5):
        step(fight)
    assert fight.traps == []


def test_a_third_trap_replaces_the_oldest():
    fight = versus(M_CUTIE, ROBERT, 400)
    me = fight.fighters["p1"]
    xs = []
    for k in range(3):
        me.x = 100.0 + 60 * k
        step(fight, DOWN_X)
        for _ in range(TRAP.cooldown + 2):
            step(fight)
        xs.append(me.x + TRAP_REACH)
    assert TRAP_MAX == 2 and [t.x for t in fight.traps] == xs[1:]


def test_traps_go_after_10_s():
    fight = versus(M_CUTIE, ROBERT, 400)
    trap = set_trap(fight)
    while trap.age < TRAP_LIFE - 1:
        step(fight)
    assert fight.traps == [trap]
    step(fight)
    assert fight.traps == []


def test_her_traps_go_when_she_is_knocked_down():
    fight = versus(M_CUTIE, ROBERT, 300)
    me, rival = fight.fighters["p1"], fight.fighters["p2"]
    set_trap(fight)
    rival.x = me.x - 46                         # behind her, clear of the trap
    for i in range(10):
        step(fight, IDLE, FighterInput(dx=1, b=True) if i == 0 else IDLE)      # a throw
    assert me.action == "knockdown" and fight.traps == []


def test_a_trap_under_a_superposed_erwin_closes_on_a_box_and_measures_him():
    for heads in (True, False):
        fight = versus(M_CUTIE, ERWIN, 200, seed=heads_seed(heads))
        erwin = fight.fighters["p2"]
        trap = set_trap(fight)
        erwin.x = 520.0                          # both boxes clear of the trap
        step(fight, IDLE, X)
        for _ in range(ERWIN.moves["stand.X"].startup):
            step(fight)
        assert erwin.boxed
        erwin.boxes = (trap.x, trap.x + 120)    # then box 1 right on it
        events = step(fight)
        assert "box_collapse" in kinds(events) and "trap_close" in kinds(events)
        assert not erwin.boxed and trap.state == "closed"
        if heads:       # he was in that box: held, and hurt (both green)
            assert erwin.x == trap.x and erwin.action == "hitstun" and trap.held == "p2"
            assert erwin.health == ERWIN.health - TRAP_HOLD.damage
        else:           # in the other one: the trap closed on nothing
            assert erwin.x == trap.x + 120 and trap.held is None and erwin.health == ERWIN.health


def test_a_tunnelling_phoebe_has_no_body_and_the_trap_stays_armed():
    fight = versus(M_CUTIE, PHOEBE, 300)
    phoebe = fight.fighters["p2"]
    trap = set_trap(fight)
    step(fight, IDLE, DOWN_X)                   # TUNNEL
    while not phoebe.intangible:
        step(fight, IDLE, FighterInput(down=True))
    phoebe.x = trap.x                           # gone, right over the trap
    for _ in range(4):
        step(fight, IDLE, FighterInput(down=True))
        phoebe.x = trap.x
    assert phoebe.intangible and trap.armed and phoebe.health == PHOEBE.health


def test_a_rival_knocked_into_a_trap_is_caught_once_they_come_to_rest():
    fight = versus(M_CUTIE, ROBERT, 300)
    rival = fight.fighters["p2"]
    trap = set_trap(fight)
    rival.x = trap.x
    rival.action, rival.stun = "hitstun", 12    # reeling across it: not yet
    events = []
    for _ in range(11):
        events += step(fight)
    assert hits_on(events, "p2") == [] and trap.armed
    for _ in range(3):
        events += step(fight)
    assert kinds(hits_on(events, "p2")) == ["hit"] and trap.held == "p2"


def test_dos_pulling_her_across_her_own_trap_never_springs_it():
    fight = versus(M_CUTIE, DOS, 160)
    me, dos = fight.fighters["p1"], fight.fighters["p2"]
    trap = set_trap(fight)
    me.x, dos.x = 180.0, 350.0                  # the trap (at 290) between them
    step(fight, IDLE, DOWN_X)                   # MOUSE CABLE
    for _ in range(60):
        step(fight, IDLE, FighterInput(down=True))
    assert me.x > trap.x and trap.armed         # dragged right across it: her own
    assert trap is fight.traps[0]


def test_measure_collapses_her_colour_as_anyones():
    fight = versus(BOHR, M_CUTIE, 80)
    bohr, cutie = fight.fighters["p1"], fight.fighters["p2"]
    bohr.basis = X_BASIS
    events = []
    for i in range(70):
        events += step(fight, FighterInput(x=i == 0))
    assert [(e.kind, e.error) for e in hits_on(events, "p2")] == [("hit", basis.Y)]
    assert cutie.basis == X_BASIS and "measure" in kinds(events)


def test_a_trap_is_its_own_object_in_the_fight():
    t = Trap("p1", TRAP_HOLD, 300.0, Z_BASIS)
    assert t.state == "arming" and not t.armed
    t.age = TRAP_ARM
    assert t.state == "armed" and t.box == (282.0, 274.0, 36, 26)


# --- SPIN ---------------------------------------------------------------------------------------


def spin_fight(gap=400):
    """M-CUTIE (p1) jumps and spins 8 frames after take-off."""
    fight = versus(M_CUTIE, ROBERT, gap)
    me = fight.fighters["p1"]
    events = step(fight, UP)
    for _ in range(7):
        events += step(fight)
    return fight, me, events + step(fight, X)


def test_spin_hangs_at_her_height_and_spins_96_px_forward():
    fight, me, _ = spin_fight()
    x0, y0 = me.x, me.y
    for _ in range(SPIN.startup + SPIN.active - 1):
        step(fight)
        assert me.y == y0                       # no falling, from the press to its last active frame
    assert me.phase == "active" and me.x - x0 == pytest.approx(SPIN.lunge * SPIN.active) == 96


def test_spin_hits_at_most_three_times():
    fight = versus(M_CUTIE, ROBERT, 60)
    rival = fight.fighters["p2"]
    events = step(fight, UP)
    for _ in range(3):
        events += step(fight)
    events += step(fight, X)
    for _ in range(60):
        events += step(fight)
    hits = kinds(hits_on(events, "p2"))
    assert hits == ["hit"] * 3 and rival.health == ROBERT.health - 3 * SPIN.damage
    assert SPIN.height == 1 and -(-SPIN.active // SPIN.hit_every) == 3


def test_spin_once_per_jump():
    fight, me, _ = spin_fight()
    for _ in range(SPIN.startup + SPIN.active + 2):
        step(fight)
    assert me.y > 0 and "air.X" in me.air_used
    events = step(fight, X)                     # again, in the same jump: nothing
    assert "attack" not in kinds(events) and me.phase == "recovery"
    while me.action != "idle":
        step(fight)
    assert "air.X" not in me.air_used           # landed: the next jump has its own


def test_a_missed_spin_drops_and_lands_into_its_recovery():
    fight, me, _ = spin_fight()
    for _ in range(SPIN.startup + SPIN.active):
        step(fight)
    x_end = me.x
    while me.y > 0:
        step(fight)
        assert me.move is SPIN and me.phase == "recovery"
    assert me.x == x_end                        # straight down
    for _ in range(SPIN.recovery - 1):
        step(fight)
        assert me.move is SPIN and me.vx == 0
    step(fight)
    assert me.move is None and me.action == "idle"


def test_the_stage_edge_stops_her_trap():
    fight = versus(M_CUTIE, ROBERT, 30)
    me = fight.fighters["p1"]
    me.x, fight.fighters["p2"].x = STAGE_RIGHT - 30.0, STAGE_RIGHT - 80.0
    step(fight, DOWN_X)
    for _ in range(TRAP.startup):
        step(fight, FighterInput(down=True))
    assert fight.traps[0].x == STAGE_RIGHT - 30.0 - TRAP_REACH
```

- [ ] **Step 2: Run them to make sure they fail**

Run: `uv run pytest tests/test_cutie.py -q`
Expected: FAIL at collection: `ImportError: cannot import name 'CHARGE_CAP' from 'brawl_ket.config'`.

- [ ] **Step 3: The config numbers.** In `src/brawl_ket/config.py`, after `PASTE_SPEED`:

In `src/brawl_ket/config.py`, replace:

```python
PASTE_SPEED = 4.0        # ... and a PASTE flies at least this fast, px per frame (a falling BOX DROP has
                         # next to no speed of its own across)
ROUNDS_TO_WIN = 2
HITSTOP = 5
```

with:

```python
PASTE_SPEED = 4.0        # ... and a PASTE flies at least this fast, px per frame (a falling BOX DROP has
                         # next to no speed of its own across)
CHARGE_CAP = 6           # AMPLITUDE AMPLIFICATION: M-CUTIE's wave grows to at most this many steps
CHARGE_WAIT = frames(0.25)  # ... and fires this long after her last X press (15 frames), or at once at the cap
TRAP_REACH = 70          # ION TRAP: she sets it this far in front of her, px
TRAP_ARM = frames(0.3)   # ... it arms this long after it is set (18 frames)
TRAP_LIFE = frames(10.0)  # ... and is gone this long after (600 frames), if nobody stepped in
TRAP_MAX = 2             # ... at most this many of hers at once: one more replaces the oldest
ROUNDS_TO_WIN = 2
HITSTOP = 5
```

- [ ] **Step 4: Her move data.** In `src/brawl_ket/moves.py` (the new fields, COPY's lower window,
her waves, her trap's hold and the character):

In `src/brawl_ket/moves.py`, replace:

```python

from collections.abc import Mapping
from dataclasses import dataclass, field
from types import MappingProxyType

```

with:

```python

from collections.abc import Mapping
from dataclasses import dataclass, field, replace
from types import MappingProxyType

```

In `src/brawl_ket/moves.py`, replace:

```python
    lifetime: int
    vy: float = 0.0                     # px per frame up (< 0: down, like PHOEBE's LASER)


```

with:

```python
    lifetime: int
    vy: float = 0.0                     # px per frame up (< 0: down, like PHOEBE's LASER)
    floor: bool = False                 # it runs along the floor (M-CUTIE's wave): a PASTE keeps it
                                        # there, and it cancels any rival shot it meets across (fight.py)


```

In `src/brawl_ket/moves.py`, replace:

```python
    catch: Box | None = None            # COPY: the window that catches a rival's shot or field (fight.py, _catch)
    paste: bool = False                 # PASTE: fires the clipboard's shot on its first active frame


```

with:

```python
    catch: Box | None = None            # COPY: the window that catches a rival's shot or field (fight.py, _catch)
    paste: bool = False                 # PASTE: fires the clipboard's shot on its first active frame
    # AMPLITUDE AMPLIFICATION: the press starts a charge ("charging", fighter.py) that every
    # further X press grows a step; it fires charge[steps - 1], one wave per step
    charge: tuple[Move, ...] = ()
    trap: Move | None = None            # ION TRAP: sets a trap (fight.py, Trap) that closes with this move
    hold: bool = False                  # a trap's hold: hitstun with no push at all, hurt or not
    floor_recovery: bool = False        # SPIN: its recovery waits for the floor (a miss lands into it)


```

In `src/brawl_ket/moves.py`, replace:

```python
class Character:
    name: str
    build: str                          # "lean" / "heavy" / "toy" / "cat" / "dos" (poses scale)
    health: int
    walk: float
```

with:

```python
class Character:
    name: str
    build: str                          # "lean" / "heavy" / "toy" / "cat" / "dos" / "cutie" (poses scale)
    health: int
    walk: float
```

In `src/brawl_ket/moves.py`, replace:

```python
    extra=MappingProxyType({
        # Y with an empty clipboard: a CTRL+C window in front of him for 0.2 s; a rival's shot
        # that meets it is caught (fight.py). A miss leaves him 0.3 s of recovery.
        "copy": Move(
            "COPY", 2, 12, 18, None, OWN, MID,
            damage=0, hitstun=1, knockback=0.0, kind="special", catch=Box(14, 20, 40, 110),
            poses=("copy", "copy", "idle"),
        ),
```

with:

```python
    extra=MappingProxyType({
        # Y with an empty clipboard: a CTRL+C window in front of him for 0.2 s; a rival's shot
        # that meets it is caught (fight.py). A miss leaves him 0.3 s of recovery. The window
        # starts 16 px up: low enough for M-CUTIE's smallest wave (20 px), above the mouse's 16.
        "copy": Move(
            "COPY", 2, 12, 18, None, OWN, MID,
            damage=0, hitstun=1, knockback=0.0, kind="special", catch=Box(14, 16, 40, 114),
            poses=("copy", "copy", "idle"),
        ),
```

In `src/brawl_ket/moves.py`, replace:

```python
)

CHARACTERS: dict[str, Character] = {"ROBERT": ROBERT, "BOHR": BOHR, "PHOEBE": PHOEBE, "ERWIN": ERWIN, "DOS": DOS}
```

with:

```python
)

# AMPLITUDE AMPLIFICATION's waves, one per step: (height px, damage). Taller with every step, from
# the floor up, so a small one can be jumped and a big one hardly; MID, so a crouch never ducks it.
AMP_STEPS = ((20, 7), (28, 8), (36, 10), (44, 11), (52, 13), (60, 15))


def _wave(step: int, height: int, damage: int) -> Move:
    """The wave fired at `step`: a microwave drive pulse along the floor, a little slower than
    PHOTON, its box as wide as the pulse's bright middle (cutie.py draws it)."""
    w = 2 * round((12 + 0.42 * height) / 2)
    return Move(
        "AMPLITUDE AMPLIFICATION", 3, 1, 16, None, OWN, MID,
        damage=damage, hitstun=18, knockback=3.0,
        kind="projectile", cooldown=config.frames(2.0), cue=f"wave{step}",
        projectile=Projectile(3.5, Box(-w // 2, 0, w, height), 180, floor=True),
        poses=("charge", "cast", "cast"),
    )


AMP_WAVES = tuple(_wave(n, h, d) for n, (h, d) in enumerate(AMP_STEPS, start=1))

# ION TRAP's hold, round the trap's x: it closes on a rival on the ground who steps between its
# electrodes (LOW: a jump clears it) and holds them for 0.5 s, with no push. The colour rule
# decides the damage, not the hold.
TRAP_HOLD = Move(
    "ION TRAP", 1, 1, 1, Box(-18, 0, 36, 26), OWN, LOW,
    damage=4, hitstun=config.frames(0.5), knockback=0.0, hold=True, kind="special",
)

M_CUTIE = Character(
    name="M-CUTIE",
    build="cutie",
    health=105,                         # in the middle
    walk=1.8,                           # a little slower than ROBERT
    jump_vy=11.5,
    gravity=0.5,                        # an apex of about 132 px: in the middle
    hurt_stand=Box(-16, 0, 32, 116),    # a little shorter than ROBERT, and wider: her cage skirt
    hurt_crouch=Box(-18, 0, 36, 92),    # is 60 px across at its hem
    moves=MappingProxyType({
        **{slot: ROBERT.moves[slot] for slot in NORMALS},   # the shared normals, as ROBERT's
        # Each X press is a step: the first starts the charge, she stands still, and the wave
        # fires CHARGE_WAIT frames after the last press or at once at CHARGE_CAP. A hit loses it.
        # The slot's own numbers are the 1-step wave's.
        "stand.X": replace(AMP_WAVES[0], charge=AMP_WAVES),
        # A trap on the floor TRAP_REACH px in front of her (fight.py, Trap): it arms after
        # TRAP_ARM frames and closes on the first rival on the ground who steps in.
        "crouch.X": Move(
            "ION TRAP", 10, 1, 14, None, OWN, LOW,
            damage=0, hitstun=1, knockback=0.0,
            kind="special", trap=TRAP_HOLD, cooldown=config.frames(1.0), cue="trap_set",
            poses=("crouch", "place", "crouch"),
        ),
        # She stops falling and spins forward at her height, the front leg out: 24 frames at
        # 4 px a frame (96 px), hitting every 8 (at most three times). Then she drops, and the
        # recovery waits for the floor.
        "air.X": Move(
            "SPIN", 4, 24, 10, Box(6, 34, 66, 34), OWN, MID,
            damage=4, hitstun=10, knockback=1.0, hit_every=8, lunge=4.0,
            kind="special", hover=True, once_per_jump=True, floor_recovery=True, cue="spin",
            poses=("jump", "spin", "jump"),
        ),
    }),
)

CHARACTERS: dict[str, Character] = {"ROBERT": ROBERT, "BOHR": BOHR, "PHOEBE": PHOEBE, "ERWIN": ERWIN, "DOS": DOS,
                                    "M-CUTIE": M_CUTIE}
```

- [ ] **Step 5: Her build and poses.** In `src/brawl_ket/poses.py` (the build's numbers are her
look script's; `tests/test_render.py` checks they stay so in Task 2):

In `src/brawl_ket/poses.py`, replace:

```python
    # DOS's COPY: both fists up in front of the case, holding up the CTRL+C frame
    "copy": Pose(4, 26, -4, -24, -12, 105, 120, 95, 115),
}
POSE_NAMES = tuple(POSES)
```

with:

```python
    # DOS's COPY: both fists up in front of the case, holding up the CTRL+C frame
    "copy": Pose(4, 26, -4, -24, -12, 105, 120, 95, 115),
    # M-CUTIE's stand.X AMPLITUDE AMPLIFICATION, charging: hands cupped together in front of her
    # chest (her approved look's CHARGE); the wave leaves with PHOTON's push ("cast")
    "charge": Pose(2, 26, -4, -24, -12, 62, 150, 52, 158),
    # M-CUTIE's crouch.X ION TRAP: crouched, the front hand reaching down to set it on the floor
    "place": Pose(28, 95, -4, 30, -86, 40, 15, 30, 155),
    # M-CUTIE's air.X SPIN: in the air, the front leg straight out, arms flung wide (the look's SPIN)
    "spin": Pose(-4, 92, 92, 24, -60, 60, 150, 30, 150),
}
POSE_NAMES = tuple(POSES)
```

In `src/brawl_ket/poses.py`, replace:

```python
    # DOS: a tall case on short legs, stubby arms; his "head" joint is the top of the case
    "dos": {"torso": 33, "shoulder": 15, "thigh": 14, "shin": 15, "upper_arm": 10, "forearm": 10, "neck": 4.5},
}
SCALE = {"lean": 2.0, "heavy": 2.3, "toy": 2.1, "cat": 2.1, "dos": 2.2}     # the mockup's proportions: about 130 px tall
HEAD_R = {"lean": 13, "heavy": 15, "toy": 14, "cat": 17, "dos": 15}
LIMB_W = {"lean": 12, "heavy": 16, "toy": 12, "cat": 13, "dos": 13}
CASE_TILT = 0.3         # DOS's case leans only this much of a pose's lean: the legs do the work
LEAN_SCALE = {"dos": CASE_TILT}
```

with:

```python
    # DOS: a tall case on short legs, stubby arms; his "head" joint is the top of the case
    "dos": {"torso": 33, "shoulder": 15, "thigh": 14, "shin": 15, "upper_arm": 10, "forearm": 10, "neck": 4.5},
    # M-CUTIE: PHOEBE's long-limbed build, a little shorter in the body and legs, thinner limbs
    "cutie": {"torso": 22, "shoulder": 19, "thigh": 17, "shin": 17, "upper_arm": 12, "forearm": 12, "neck": 7},
}
SCALE = {"lean": 2.0, "heavy": 2.3, "toy": 2.1, "cat": 2.1, "dos": 2.2, "cutie": 2.1}   # the mockup's proportions: about 130 px tall
HEAD_R = {"lean": 13, "heavy": 15, "toy": 14, "cat": 17, "dos": 15, "cutie": 15}
LIMB_W = {"lean": 12, "heavy": 16, "toy": 12, "cat": 13, "dos": 13, "cutie": 12}
CASE_TILT = 0.3         # DOS's case leans only this much of a pose's lean: the legs do the work
LEAN_SCALE = {"dos": CASE_TILT}
```

In `src/brawl_ket/poses.py`, replace:

```python
    if a == "jump":
        return POSES["jump"]
    if a == "hitstun":
        if f.stun <= EASE_FRAMES:
```

with:

```python
    if a == "jump":
        return POSES["jump"]
    if a == "charging":         # AMPLITUDE AMPLIFICATION: held, hands cupped, while it charges
        return POSES["charge"]
    if a == "hitstun":
        if f.stun <= EASE_FRAMES:
```

- [ ] **Step 6: The charge, the hold and SPIN in `src/brawl_ket/fighter.py`.** The charge is an
action of its own: the first X press starts it (no cooldown yet), each further press (read from
the buffer, so one made in a hitstop freeze counts) is a step, and when it fires the step's wave
starts as an ordinary move, which sets the cooldown and fixes its colour. A hit (`take_hit`, a
throw included) or a K.O. loses it. SPIN hovers like LASER but keeps its lunge in its active
frames, and its recovery, like a bounced dive's, waits for the floor:

In `src/brawl_ket/fighter.py`, replace:

```python
changes the fighter's basis state. Everything is counted in integer frames at 60 Hz.
THE BOX (ERWIN) is the "boxed" action: superposed in two boxes, with no body; the fight measures him.

Coordinates: x is in screen px; y is the height above the floor (>= 0), and
```

with:

```python
changes the fighter's basis state. Everything is counted in integer frames at 60 Hz.
THE BOX (ERWIN) is the "boxed" action: superposed in two boxes, with no body; the fight measures him.
AMPLITUDE AMPLIFICATION (M-CUTIE) is the "charging" action: she stands still while X presses grow
the wave, then fires it as an ordinary move.

Coordinates: x is in screen px; y is the height above the floor (>= 0), and
```

In `src/brawl_ket/fighter.py`, replace:

```python
    BUFFER_FRAMES,
    CHAIN_MAX,
    COPY_CAUGHT_RECOVERY,
    FLOOR_Y,
```

with:

```python
    BUFFER_FRAMES,
    CHAIN_MAX,
    CHARGE_CAP,
    CHARGE_WAIT,
    COPY_CAUGHT_RECOVERY,
    FLOOR_Y,
```

In `src/brawl_ket/fighter.py`, replace:

```python
        self.attack_basis = self.basis  # the basis the move in progress started in (its colour)
        self.crouching = False
        self.action = "idle"        # idle walk crouch jump attack hitstun knockdown boxed
        self.frame = 0              # frames into the action (0 on its first frame)
        self.move: Move | None = None
```

with:

```python
        self.attack_basis = self.basis  # the basis the move in progress started in (its colour)
        self.crouching = False
        self.action = "idle"        # idle walk crouch jump attack hitstun knockdown boxed charging
        self.frame = 0              # frames into the action (0 on its first frame)
        self.move: Move | None = None
```

In `src/brawl_ket/fighter.py`, replace:

```python
        self.box_t = 0                  # ... frames superposed
        self.rival_boxes: tuple[float, float] | None = None   # the rival's two boxes while it is boxed

    # --- derived state ----------------------------------------------------------------
```

with:

```python
        self.box_t = 0                  # ... frames superposed
        self.rival_boxes: tuple[float, float] | None = None   # the rival's two boxes while it is boxed
        self.charge = 0                 # AMPLITUDE AMPLIFICATION: steps charged (0: not charging)
        self.charge_wait = 0            # ... frames since the last step's press

    # --- derived state ----------------------------------------------------------------
```

In `src/brawl_ket/fighter.py`, replace:

```python
        if self.bounced:            # a diver hit in a trade stops springing up
            self.vy = min(self.vy, 0.0)
        self.move = None
        self.slot = None
```

with:

```python
        if self.bounced:            # a diver hit in a trade stops springing up
            self.vy = min(self.vy, 0.0)
        self.charge = self.charge_wait = 0      # a charge hit is lost: it never fires
        self.move = None
        self.slot = None
```

In `src/brawl_ket/fighter.py`, replace:

```python
        self.buffer = []
        self.vx = (move.knockback if hurt else max(move.knockback, BLOCK_PUSH)) * from_facing
        self.frame = 0
        if was_down:                # a knockdown is never cut short into hitstun
```

with:

```python
        self.buffer = []
        self.vx = (move.knockback if hurt else max(move.knockback, BLOCK_PUSH)) * from_facing
        if move.hold:               # a trap holds them where they stand, hurt or not
            self.vx = 0.0
        self.frame = 0
        if was_down:                # a knockdown is never cut short into hitstun
```

In `src/brawl_ket/fighter.py`, replace:

```python
        """Down for good: the round is over. Flies off `away` (+1 / -1) at least `push`
        px per frame, whatever hit it, and never gets up."""
        self.move = None
        self.slot = None
```

with:

```python
        """Down for good: the round is over. Flies off `away` (+1 / -1) at least `push`
        px per frame, whatever hit it, and never gets up."""
        self.charge = self.charge_wait = 0
        self.move = None
        self.slot = None
```

In `src/brawl_ket/fighter.py`, replace:

```python
            m = self.move
            assert m is not None
            if self.bounced and self.y > 0:
                self.frame = self.startup + m.active    # the recovery starts on the floor
            if self.frame >= self.startup + m.active + m.recovery:
```

with:

```python
            m = self.move
            assert m is not None
            if self.y > 0 and (self.bounced or (m.floor_recovery and self.frame >= self.startup + m.active)):
                self.frame = self.startup + m.active    # the recovery starts on the floor
            if self.frame >= self.startup + m.active + m.recovery:
```

In `src/brawl_ket/fighter.py`, replace:

```python
                if m.kind == "projectile":
                    events.append(("projectile", {"move": m}))
                if m.paste and self.clipboard is not None:
                    shot, shot_basis = self.clipboard
```

with:

```python
                if m.kind == "projectile":
                    events.append(("projectile", {"move": m}))
                if m.trap is not None:  # ION TRAP: the fight sets it on the floor
                    events.append(("trap", {"move": m}))
                if m.paste and self.clipboard is not None:
                    shot, shot_basis = self.clipboard
```

In `src/brawl_ket/fighter.py`, replace:

```python
        elif self.y == 0:
            self.vx = 0.0
        elif m.dive is not None and self.frame == self.startup + m.active and not self.bounced:
            self.vx = 0.0           # the dive ran out before the floor (a bounce keeps its drift)

    def _slot_for(self, btn: str, dx: int, rival_x: float) -> str:
```

with:

```python
        elif self.y == 0:
            self.vx = 0.0
        elif (m.dive is not None or m.floor_recovery) and self.frame == self.startup + m.active \
                and not self.bounced:
            self.vx = 0.0           # the dive (or SPIN) ran out before the floor: she drops (a bounce keeps its drift)

    def _slot_for(self, btn: str, dx: int, rival_x: float) -> str:
```

In `src/brawl_ket/fighter.py`, replace:

```python
        if self.boxed:
            self._boxed(inp, events)
            return
        on_ground_free = self.action in _GROUND_FREE
```

with:

```python
        if self.boxed:
            self._boxed(inp, events)
            return
        if self.action == "charging":
            self._charging(events)
            return
        on_ground_free = self.action in _GROUND_FREE
```

In `src/brawl_ket/fighter.py`, replace:

```python
            if cancel and not self.can_cancel(slot):
                continue
            if slot == "paste" and self.clipboard is not None and self.clipboard[0].projectile is None:
                self._paste_field(events)
```

with:

```python
            if cancel and not self.can_cancel(slot):
                continue
            if move.charge:             # AMPLITUDE AMPLIFICATION: the first press is its first step
                self._start_charge(events)
                return
            if slot == "paste" and self.clipboard is not None and self.clipboard[0].projectile is None:
                self._paste_field(events)
```

In `src/brawl_ket/fighter.py`, replace:

```python
        events.append(("box_split", {}))

    def _boxed(self, inp: FighterInput, events: list) -> None:
        """Superposed: any button (A, B or X; Y only switches) or a new stick direction collapses
```

with:

```python
        events.append(("box_split", {}))

    def _start_charge(self, events: list) -> None:
        """AMPLITUDE AMPLIFICATION starts: one step charged, and she stands still. The cooldown
        waits for the wave to fire."""
        self.move = None
        self.slot = None
        self.chained = False
        self.move_hit = False
        self.crouching = False
        self.buffer = []
        self.vx = 0.0
        self.action = "charging"
        self.frame = 0
        self.charge, self.charge_wait = 1, 0
        events.append(("charge1", {}))

    def _charging(self, events: list) -> None:
        """Charging: every X press (buffered, so one in a hitstop freeze counts too) grows the
        wave a step; A and B do nothing. It fires CHARGE_WAIT frames after the last press, or
        at once on reaching CHARGE_CAP, as the step's own wave move (its colour fixed now)."""
        pressed = any(p.button == "x" for p in self.buffer)
        self.buffer = []
        if pressed and self.charge < CHARGE_CAP:
            self.charge += 1
            self.charge_wait = 0
            events.append((f"charge{self.charge}", {}))
        else:
            self.charge_wait += 1
        if self.charge >= CHARGE_CAP or self.charge_wait >= CHARGE_WAIT:
            wave = self.char.moves["stand.X"].charge[self.charge - 1]
            self.charge = self.charge_wait = 0
            self._start_move("stand.X", wave, False, events)

    def _boxed(self, inp: FighterInput, events: list) -> None:
        """Superposed: any button (A, B or X; Y only switches) or a new stick direction collapses
```

In `src/brawl_ket/fighter.py`, replace:

```python
        landed = False
        if self.hovering:               # LASER: she hangs in the air while she aims and fires
            self.vx = self.vy = 0.0
        elif self.y > 0 or self.vy > 0:
            if not self._diving():
```

with:

```python
        landed = False
        if self.hovering:               # LASER: she hangs in the air while she aims and fires
            self.vy = 0.0
            if not (self.move.lunge and self.phase == "active"):
                self.vx = 0.0           # (SPIN hangs at her height, but spins forward)
        elif self.y > 0 or self.vy > 0:
            if not self._diving():
```

In `src/brawl_ket/fighter.py`, replace:

```python
        if self.action == "attack" and m is not None:
            self.vx = 0.0
            if m.dive is not None or m.leap is not None:
                # a dive or a leap that reaches the floor skips to its recovery
                self.frame = max(self.frame, self.startup + m.active)
            else:
```

with:

```python
        if self.action == "attack" and m is not None:
            self.vx = 0.0
            if m.dive is not None or m.leap is not None or m.floor_recovery:
                # a dive, a leap or a SPIN that reaches the floor skips to its recovery
                self.frame = max(self.frame, self.startup + m.active)
            else:
```

- [ ] **Step 7: Traps and the floor wave in `src/brawl_ket/fight.py`.** Traps are resolved with
the strikes, so THE BOX's measurement (`_measure`) applies to them unchanged; a trap whose strike
the measurement drops closed on the empty box:

In `src/brawl_ket/fight.py`, replace:

```python
Pure logic, no pygame. Its only randomness is THE BOX's 50/50s, drawn from the fight's own
random.Random(seed): the same inputs and the same seed always give the same round. The
fight drives two Fighters (fighter.py), spawns and moves the shots,
resolves hitboxes against hurtboxes, turns each attack's colour rule into an error
using its attacker's basis at the moment of the hit (basis.py), lets the defender's
```

with:

```python
Pure logic, no pygame. Its only randomness is THE BOX's 50/50s, drawn from the fight's own
random.Random(seed): the same inputs and the same seed always give the same round. The
fight drives two Fighters (fighter.py), spawns and moves the shots, keeps M-CUTIE's traps,
resolves hitboxes against hurtboxes, turns each attack's colour rule into an error
using its attacker's basis at the moment of the hit (basis.py), lets the defender's
```

In `src/brawl_ket/fight.py`, replace:

```python
    START_X,
    THROW_SLACK,
)
from .fighter import IDLE, STUN_DECAY, Fighter, FighterInput
```

with:

```python
    START_X,
    THROW_SLACK,
    TRAP_ARM,
    TRAP_LIFE,
    TRAP_MAX,
    TRAP_REACH,
)
from .fighter import IDLE, STUN_DECAY, Fighter, FighterInput
```

In `src/brawl_ket/fight.py`, replace:

```python

@dataclass
class _Landing:
    """A COLLAPSE-style shockwave window opened when a fighter lands."""
```

with:

```python

@dataclass
class Trap:
    """M-CUTIE's ION TRAP on the floor: arming for its first TRAP_ARM frames, then armed until a
    rival on the ground stands in it; then closed (used up), shown for the hold's length. Its
    colour is the basis she was in when she set it, for good. Gone after TRAP_LIFE frames, or
    when its owner is knocked down."""

    owner: str
    move: Move          # the hold it closes with; its hitbox is the catch box, round x
    x: float
    basis: str
    age: int = 0        # frames since it was set
    closed: int = 0     # > 0: closed, this many frames still shown
    held: str | None = None     # ... on whom (None: on an empty box)

    @property
    def armed(self) -> bool:
        return not self.closed and self.age >= TRAP_ARM

    @property
    def state(self) -> str:
        return "closed" if self.closed else "armed" if self.armed else "arming"

    @property
    def box(self) -> Rect:
        assert self.move.hitbox is not None
        return _world_box(self.x, 0.0, 1, self.move.hitbox)


@dataclass
class _Landing:
    """A COLLAPSE-style shockwave window opened when a fighter lands."""
```

In `src/brawl_ket/fight.py`, replace:

```python
    shot: Shot | None = None
    box: frozenset[int] | None = None   # THE BOX: which of the defender's boxes it touched


```

with:

```python
    shot: Shot | None = None
    box: frozenset[int] | None = None   # THE BOX: which of the defender's boxes it touched
    trap: Trap | None = None            # ION TRAP: the trap that closes


```

In `src/brawl_ket/fight.py`, replace:

```python
            f.rng = self.rng
        self.shots: list[Shot] = []
        self.frames_left = ROUND_FRAMES
        self.hitstop = 0
```

with:

```python
            f.rng = self.rng
        self.shots: list[Shot] = []
        self.traps: list[Trap] = []         # M-CUTIE's, oldest first
        self.frames_left = ROUND_FRAMES
        self.hitstop = 0
```

In `src/brawl_ket/fight.py`, replace:

```python
        self._catch(events)
        self._resolve_hits(events)
        self.frames_left -= 1
        self._check_end(events)
```

with:

```python
        self._catch(events)
        self._resolve_hits(events)
        self._step_traps()
        self.frames_left -= 1
        self._check_end(events)
```

In `src/brawl_ket/fight.py`, replace:

```python
                    speed = proj.speed
                    if data.get("paste"):   # PASTE: level, from his drive slot, in the colour it was fired in
                        y, vy, shot_basis = f.y + DRIVE_SLOT_Y - proj.box.y, 0.0, data["basis"]
                        speed = max(speed, PASTE_SPEED)     # a pasted BOX DROP flies too
                    else:
```

with:

```python
                    speed = proj.speed
                    if data.get("paste"):   # PASTE: level, from his drive slot, in the colour it was fired in
                        slot_y = f.y if proj.floor else f.y + DRIVE_SLOT_Y - proj.box.y    # a wave stays on the floor
                        y, vy, shot_basis = slot_y, 0.0, data["basis"]
                        speed = max(speed, PASTE_SPEED)     # a pasted BOX DROP flies too
                    else:
```

In `src/brawl_ket/fight.py`, replace:

```python
                    ))
                    events.append(Event("projectile", key))
                else:
                    events.append(Event(kind, key))
```

with:

```python
                    ))
                    events.append(Event("projectile", key))
                elif kind == "trap":
                    self._set_trap(key, f, data["move"])
                else:
                    events.append(Event(kind, key))
```

In `src/brawl_ket/fight.py`, replace:

```python
                left, _, w, _ = s.box
                events.append(Event("fizzle", s.owner, None, left + w / 2, FLOOR_Y))
        # shots of different owners cancel each other, with no event
        dead: set[int] = set()
        for i, s in enumerate(self.shots):
            for j in range(i + 1, len(self.shots)):
                t = self.shots[j]
                if s.owner != t.owner and _overlap(s.box, t.box) is not None:
                    dead.update((i, j))
        self.shots = [
```

with:

```python
                left, _, w, _ = s.box
                events.append(Event("fizzle", s.owner, None, left + w / 2, FLOOR_Y))
        # shots of different owners cancel each other, with no event; a wave on the floor
        # (M-CUTIE's) cancels any rival shot across its whole column, whatever its height
        dead: set[int] = set()
        for i, s in enumerate(self.shots):
            for j in range(i + 1, len(self.shots)):
                t = self.shots[j]
                if s.owner != t.owner and _overlap(_cancel_box(s), _cancel_box(t)) is not None:
                    dead.update((i, j))
        self.shots = [
```

In `src/brawl_ket/fight.py`, replace:

```python
            if i not in dead and s.life > 0 and not self._off_stage(s)
        ]

    @staticmethod
```

with:

```python
            if i not in dead and s.life > 0 and not self._off_stage(s)
        ]

    def _set_trap(self, key: str, f: Fighter, move: Move) -> None:
        """ION TRAP: a trap on the floor TRAP_REACH px in front of her, in her colour; a third
        of hers replaces the oldest."""
        assert move.trap is not None
        mine = [t for t in self.traps if t.owner == key and not t.closed]
        if len(mine) >= TRAP_MAX:
            self.traps.remove(mine[0])
        self.traps.append(Trap(key, move.trap, _clamp(f.x + f.facing * TRAP_REACH), f.attack_basis))

    def _step_traps(self) -> None:
        """Traps age; a closed one shows for its hold, then goes; all of a knocked-down owner's
        go at once, and an open one after TRAP_LIFE frames."""
        kept = []
        for t in self.traps:
            if self.fighters[t.owner].action == "knockdown":
                continue
            t.age += 1
            if t.closed:
                t.closed -= 1
                if t.closed == 0:
                    continue
            elif t.age >= TRAP_LIFE:
                continue
            kept.append(t)
        self.traps = kept

    def _close(self, trap: Trap, held: str | None, events: list[Event]) -> None:
        trap.closed, trap.held = trap.move.hitstun, held
        events.append(Event("trap_close", held, None, trap.x, FLOOR_Y))

    @staticmethod
```

In `src/brawl_ket/fight.py`, replace:

```python
                strikes.append(_Strike(None, s.owner, rival_key, s.move, s.facing, touch[0], s, box=touch[1]))

        strikes = self._measure(strikes, events)

        # Every strike was found against the state at the start of the resolution,
```

with:

```python
                strikes.append(_Strike(None, s.owner, rival_key, s.move, s.facing, touch[0], s, box=touch[1]))

        caught: set[str] = set()
        for t in self.traps:
            rival_key = _other(t.owner)
            target = self.fighters[rival_key]
            # a rival on the ground and free to move (one reeling across it is caught once they
            # come to rest in it); not one tunnelling, getting up or knocked down
            if not t.armed or rival_key in caught or target.y > 0 or target.action in _STUNNED \
                    or target.wakeup or target.intangible:
                continue
            touch = self._touch(t.box, target)
            if touch is not None:
                caught.add(rival_key)
                side = 1 if target.x >= t.x else -1
                strikes.append(_Strike(None, t.owner, rival_key, t.move, side, touch[0], box=touch[1], trap=t))

        traps = [st.trap for st in strikes if st.trap is not None]
        strikes = self._measure(strikes, events)
        for t in traps:         # a trap that measured a box and found him in the other closes empty
            if not any(st.trap is t for st in strikes):
                self._close(t, None, events)

        # Every strike was found against the state at the start of the resolution,
```

In `src/brawl_ket/fight.py`, replace:

```python
        # when it starts (a switch mid-swing doesn't recolour it), as its limb has shown; a
        # shot keeps the colour it was fired in, a shockwave its slam's.
        attack_basis = st.shot.basis if st.shot is not None else owner.attack_basis
        error = basis.error_for(m.colour, attack_basis)
        result = defender.take_hit(m, error, st.from_facing)
        if defender.char.copy_paste:        # DOS hit: his mouse's cable is cut
            self.shots = [s for s in self.shots if not (s.owner == st.defender and s.move.pull)]
```

with:

```python
        # when it starts (a switch mid-swing doesn't recolour it), as its limb has shown; a
        # shot keeps the colour it was fired in, a shockwave its slam's.
        attack_basis = st.shot.basis if st.shot is not None else st.trap.basis if st.trap is not None \
            else owner.attack_basis
        error = basis.error_for(m.colour, attack_basis)
        result = defender.take_hit(m, error, st.from_facing)
        if st.trap is not None:             # ION TRAP: it closes round them, hurt or not
            self._close(st.trap, st.defender, events)
        if defender.char.copy_paste:        # DOS hit: his mouse's cable is cut
            self.shots = [s for s in self.shots if not (s.owner == st.defender and s.move.pull)]
```

In `src/brawl_ket/fight.py`, replace:

```python


def _clamp(x: float) -> float:
    return min(max(x, STAGE_LEFT), STAGE_RIGHT)
```

with:

```python


def _cancel_box(s: Shot) -> Rect:
    """The box a shot cancels a rival's with: its own, or for a wave on the floor its whole
    column, floor to sky."""
    left, top, w, h = s.box
    if s.move.projectile is not None and s.move.projectile.floor:
        return (left, 0.0, w, float(FLOOR_Y))
    return (left, top, w, h)


def _clamp(x: float) -> float:
    return min(max(x, STAGE_LEFT), STAGE_RIGHT)
```

- [ ] **Step 8: Keep the rest of the game running with a sixth fighter.**
  - `src/brawl_ket/audio.py`, `EVENT_SOUNDS` (her events and cues, mapped to stand-ins until
    Task 3 gives them their own sounds; `test_every_moves_cue_has_a_sound` needs a sound for every
    cue, and `test_every_fight_event_is_mapped` an entry for every event):

In `src/brawl_ket/audio.py`, replace:

```python
                "floppy": "floppy", "mouse": "mouse", "crt_drop": "crt_drop", "copy": "copy",
                "paste": "paste",
                "land": None, "ko": None, "timeout": None}   # ko/timeout: the cues play those
SUPERSEDES = {"measure": "hit",     # MEASURE's zap replaces the thump of its own throw
```

with:

```python
                "floppy": "floppy", "mouse": "mouse", "crt_drop": "crt_drop", "copy": "copy",
                "paste": "paste",
                # M-CUTIE (stand-ins until her own sounds: Task 3); "trap" is the fighter's own,
                # which the fight turns into a trap on the floor
                **{f"charge{n}": None for n in range(1, 7)}, **{f"wave{n}": "photon" for n in range(1, 7)},
                "trap": None, "trap_set": "blip", "trap_close": None, "spin": "swing",
                "land": None, "ko": None, "timeout": None}   # ko/timeout: the cues play those
SUPERSEDES = {"measure": "hit",     # MEASURE's zap replaces the thump of its own throw
```

  - `src/brawl_ket/render.py` (she is drawn as the lean puppet on her own skeleton until Task 2
    replaces both lines):

In `src/brawl_ket/render.py`, replace:

```python

# how each build is drawn (the skeleton's proportions are in poses.py)
TORSO_EXTRA = {"lean": 5, "heavy": 8, "toy": 5}   # the lean torso is this much thicker than a limb
PLATES = {"lean": False, "heavy": True, "toy": False}   # armour: the heavy's wedge torso, plates, helm
# PHOEBE (the "toy" build): a scientist, not a puppet. Her neutral colours; the coat, the lining
# and her trousers are shades of her basis colour (docs/.../2026-10-09-brawl-ket-phoebe-design.md)
```

with:

```python

# how each build is drawn (the skeleton's proportions are in poses.py)
TORSO_EXTRA = {"lean": 5, "heavy": 8, "toy": 5, "cutie": 5}   # the lean torso is this much thicker than a limb
PLATES = {"lean": False, "heavy": True, "toy": False, "cutie": False}   # armour: the heavy's wedge torso, plates, helm
# PHOEBE (the "toy" build): a scientist, not a puppet. Her neutral colours; the coat, the lining
# and her trousers are shades of her basis colour (docs/.../2026-10-09-brawl-ket-phoebe-design.md)
```

  - `src/brawl_ket/match.py`:

In `src/brawl_ket/match.py`, replace:

```python

PLAYERS = ("p1", "p2")
ROSTER = tuple(CHARACTERS.values())     # the select screen's order: ROBERT, BOHR, PHOEBE, ERWIN, DOS

TITLE = "title"
```

with:

```python

PLAYERS = ("p1", "p2")
ROSTER = tuple(CHARACTERS.values())     # the select screen's order: ROBERT, BOHR, PHOEBE, ERWIN, DOS, M-CUTIE

TITLE = "title"
```

  - `tools/snapshot.py`:

In `tools/snapshot.py`, replace:

```python
CELL_W, CELL_H, COLS = 180, 230, 6
CELL_FLOOR = 200
ACCENTS = {"lean": P.CREAM, "heavy": P.GOLD, "toy": P.TEAL, "cat": P.GOLD, "dos": P.CREAM}


```

with:

```python
CELL_W, CELL_H, COLS = 180, 230, 6
CELL_FLOOR = 200
ACCENTS = {"lean": P.CREAM, "heavy": P.GOLD, "toy": P.TEAL, "cat": P.GOLD, "dos": P.CREAM, "cutie": P.GOLD}


```

- [ ] **Step 9: Run her tests**

Run: `uv run pytest tests/test_cutie.py -q`
Expected: 42 passed.

- [ ] **Step 10: Bring the cross-cutting tests up to six fighters.**

`tests/test_moves.py` (her startups, damage, health, the specials' table and twists, and her
stats and specials):

In `tests/test_moves.py`, replace:

```python
from brawl_ket.basis import BOTH, OPPOSITE, OWN, Z_BASIS
from brawl_ket.moves import HIGH, LOW, MID
from brawl_ket.moves import CHARACTERS, DOS, ERWIN, NORMALS, PHOEBE, ROBERT, SLOTS, Box


```

with:

```python
from brawl_ket.basis import BOTH, OPPOSITE, OWN, Z_BASIS
from brawl_ket.moves import HIGH, LOW, MID
from brawl_ket.moves import AMP_WAVES, CHARACTERS, DOS, ERWIN, M_CUTIE, NORMALS, PHOEBE, ROBERT, SLOTS, TRAP_HOLD, Box


```

In `tests/test_moves.py`, replace:

```python
    "ERWIN": (4, 10, 7),
    "DOS": (8, 13, 9),
}

```

with:

```python
    "ERWIN": (4, 10, 7),
    "DOS": (8, 13, 9),
    "M-CUTIE": (4, 10, 7),
}

```

In `tests/test_moves.py`, replace:

```python
# by name: the specials whose damage isn't a special's 10 (MEASURE 12; TUNNEL only moves her; LASER a
# little less; CHARGE NOISE a shock; THE BOX itself nothing, its swipe 8; BOX DROP a light box;
# MOUSE CABLE a tap: its pull is the point)
SPECIAL_DAMAGE = {"MEASURE": 12, "TUNNEL": 0, "LASER": 8, "CHARGE NOISE": 3, "THE BOX": 0, "BOX DROP": 8,
                  "FLOPPY": 9, "MOUSE CABLE": 6, "CRT DROP": 12}


```

with:

```python
# by name: the specials whose damage isn't a special's 10 (MEASURE 12; TUNNEL only moves her; LASER a
# little less; CHARGE NOISE a shock; THE BOX itself nothing, its swipe 8; BOX DROP a light box;
# MOUSE CABLE a tap: its pull is the point; AMPLITUDE AMPLIFICATION its 1-step wave (7 to 15 by
# step); ION TRAP sets a trap, which holds for 4; SPIN 4 a hit)
SPECIAL_DAMAGE = {"MEASURE": 12, "TUNNEL": 0, "LASER": 8, "CHARGE NOISE": 3, "THE BOX": 0, "BOX DROP": 8,
                  "FLOPPY": 9, "MOUSE CABLE": 6, "CRT DROP": 12, "AMPLITUDE AMPLIFICATION": 7, "ION TRAP": 0,
                  "SPIN": 4}


```

In `tests/test_moves.py`, replace:

```python
def test_health():
    assert {c.name: c.health for c in CHARACTERS.values()} == {
        "ROBERT": 100, "BOHR": 115, "PHOEBE": 95, "ERWIN": 90, "DOS": 125}


```

with:

```python
def test_health():
    assert {c.name: c.health for c in CHARACTERS.values()} == {
        "ROBERT": 100, "BOHR": 115, "PHOEBE": 95, "ERWIN": 90, "DOS": 125, "M-CUTIE": 105}


```

In `tests/test_moves.py`, replace:

```python
    for c, slot, m in all_moves():
        if m.hitbox is None:
            assert m.kind == "projectile" or m.tunnel or m.superpose, (c.name, slot)


```

with:

```python
    for c, slot, m in all_moves():
        if m.hitbox is None:
            assert m.kind == "projectile" or m.tunnel or m.superpose or m.trap is not None, (c.name, slot)


```

In `tests/test_moves.py`, replace:

```python
    ("DOS", "crouch.X"): (OWN, LOW, ("pull",)),
    ("DOS", "air.X"): (OWN, MID, ()),
}
TWISTS = ("switch_self_on_hit", "measure_rival", "hit_every", "tunnel", "hover", "superpose", "leap", "pull")


```

with:

```python
    ("DOS", "crouch.X"): (OWN, LOW, ("pull",)),
    ("DOS", "air.X"): (OWN, MID, ()),
    ("M-CUTIE", "stand.X"): (OWN, MID, ("charge",)),
    ("M-CUTIE", "crouch.X"): (OWN, LOW, ("trap",)),
    ("M-CUTIE", "air.X"): (OWN, MID, ("hit_every", "hover", "floor_recovery")),
}
TWISTS = ("switch_self_on_hit", "measure_rival", "hit_every", "tunnel", "hover", "superpose", "leap", "pull",
          "charge", "trap", "floor_recovery")


```

In `tests/test_moves.py`, replace:

```python
                     "PHOEBE": ["LIGHT PILLAR", "TUNNEL", "LASER"],
                     "ERWIN": ["THE BOX", "POUNCE", "BOX DROP"],
                     "DOS": ["FLOPPY", "MOUSE CABLE", "CRT DROP"]}


```

with:

```python
                     "PHOEBE": ["LIGHT PILLAR", "TUNNEL", "LASER"],
                     "ERWIN": ["THE BOX", "POUNCE", "BOX DROP"],
                     "DOS": ["FLOPPY", "MOUSE CABLE", "CRT DROP"],
                     "M-CUTIE": ["AMPLITUDE AMPLIFICATION", "ION TRAP", "SPIN"]}


```

In `tests/test_moves.py`, replace:

```python
    assert copy.catch is not None and copy.active == config.frames(0.2) and copy.recovery == config.frames(0.3)
    assert paste.paste and paste.startup <= 6 and paste.recovery <= 12
```

with:

```python
    assert copy.catch is not None and copy.active == config.frames(0.2) and copy.recovery == config.frames(0.3)
    assert paste.paste and paste.startup <= 6 and paste.recovery <= 12


# --- M-CUTIE ---------------------------------------------------------------------------------


def test_m_cutie_stats():
    m = CHARACTERS["M-CUTIE"]
    assert (m.build, m.health, m.walk, m.jump_vy, m.gravity) == ("cutie", 105, 1.8, 11.5, 0.5)
    assert m.walk < ROBERT.walk and m.fixed_basis is None and not m.copy_paste
    healths = sorted(c.health for c in CHARACTERS.values())
    apexes = sorted(apex(c) for c in CHARACTERS.values())
    assert healths[0] < m.health < healths[-1] and apexes[0] < apex(m) < apexes[-1]    # in the middle
    for slot in NORMALS:
        assert m.moves[slot] is ROBERT.moves[slot], slot


def test_m_cutie_specials():
    amp, trap, spin = (M_CUTIE.moves[s] for s in ("stand.X", "crouch.X", "air.X"))
    # AMPLITUDE AMPLIFICATION: six waves on the floor, each its own move; the slot is the first
    assert amp.charge == AMP_WAVES and len(AMP_WAVES) == config.CHARGE_CAP
    assert (amp.name, amp.damage, amp.projectile) == (AMP_WAVES[0].name, 7, AMP_WAVES[0].projectile)
    for w in AMP_WAVES:
        assert w.projectile.floor and w.projectile.box.y == 0 and w.projectile.speed == 3.5
        assert (w.colour, w.height, w.cooldown) == (OWN, MID, config.frames(2.0))
    # ION TRAP: no hitbox of its own; the trap's hold is LOW (a jump clears it), 4, 0.5 s, no push
    assert trap.trap is TRAP_HOLD and trap.cooldown == config.frames(1.0) and trap.hitbox is None
    assert (TRAP_HOLD.damage, TRAP_HOLD.height, TRAP_HOLD.hitstun, TRAP_HOLD.knockback) == (4, LOW, 30, 0.0)
    assert TRAP_HOLD.hold and TRAP_HOLD.colour == OWN
    # SPIN: hangs and spins forward, three hits at most, once per jump
    assert spin.hover and spin.lunge and spin.once_per_jump and spin.floor_recovery
    assert (spin.damage, spin.height) == (4, MID) and -(-spin.active // spin.hit_every) == 3
    assert 90 <= spin.lunge * spin.active <= 110     # about 100 px
```

`tests/test_poses.py` (SPIN's striker, the new action, the charge pose):

In `tests/test_poses.py`, replace:

```python
BUILDS = tuple(SCALE)
FEET = (320.0, float(FLOOR_Y))
ACTIONS = ("idle", "walk", "crouch", "jump", "attack", "hitstun", "knockdown", "boxed")
KEYS = {"hip", "neck", "head", "shoulder_f", "elbow_f", "hand_f", "shoulder_b", "elbow_b",
        "hand_b", "knee_f", "foot_f", "knee_b", "foot_b"}
```

with:

```python
BUILDS = tuple(SCALE)
FEET = (320.0, float(FLOOR_Y))
ACTIONS = ("idle", "walk", "crouch", "jump", "attack", "hitstun", "knockdown", "boxed", "charging")
KEYS = {"hip", "neck", "head", "shoulder_f", "elbow_f", "hand_f", "shoulder_b", "elbow_b",
        "hand_b", "knee_f", "foot_f", "knee_b", "foot_b"}
```

In `tests/test_poses.py`, replace:

```python
    "LIGHT PILLAR": "hand_f",
    "POUNCE": "hand_f", "CRT DROP": "foot_f",
}
REACH = 12      # px: a joint is drawn with a fist/foot about this big around it
```

with:

```python
    "LIGHT PILLAR": "hand_f",
    "POUNCE": "hand_f", "CRT DROP": "foot_f",
    "SPIN": "foot_f",
}
REACH = 12      # px: a joint is drawn with a fist/foot about this big around it
```

In `tests/test_poses.py`, replace:

```python
    for name in POSE_NAMES:                 # every other build is drawn on joints() itself
        assert drawn_joints(POSES[name], "lean", FEET, 1) == joints(POSES[name], "lean", FEET, 1)
```

with:

```python
    for name in POSE_NAMES:                 # every other build is drawn on joints() itself
        assert drawn_joints(POSES[name], "lean", FEET, 1) == joints(POSES[name], "lean", FEET, 1)


def test_m_cutie_charges_with_her_hands_cupped_in_front_of_her():
    from brawl_ket.moves import M_CUTIE
    f = Fighter(M_CUTIE, FEET[0], 1)
    f.action = "charging"
    for frame in range(20):
        f.frame = frame
        assert pose_for(f) == POSES["charge"]
    j = joints(POSES["charge"], "cutie", FEET, 1)
    assert j["hand_f"][0] > j["shoulder_f"][0] + 20 and j["hand_f"][1] < j["shoulder_f"][1]
```

`tests/test_match.py` (six in order, the demo from all six, no traps carried into a new round):

In `tests/test_match.py`, replace:

```python


def test_choose_your_fighter_cycles_through_all_five_in_order() -> None:
    from brawl_ket.match import ROSTER
    order = ["ROBERT", "BOHR", "PHOEBE", "ERWIN", "DOS"]
    assert [c.name for c in ROSTER] == order
    m = Match(random.Random(1))
```

with:

```python


def test_choose_your_fighter_cycles_through_all_six_in_order() -> None:
    from brawl_ket.match import ROSTER
    order = ["ROBERT", "BOHR", "PHOEBE", "ERWIN", "DOS", "M-CUTIE"]
    assert [c.name for c in ROSTER] == order
    m = Match(random.Random(1))
```

In `tests/test_match.py`, replace:

```python


def test_the_demo_picks_its_fighters_from_all_five() -> None:
    from brawl_ket.match import ROSTER
    m = Match(random.Random(3))
```

with:

```python


def test_the_demo_picks_its_fighters_from_all_six() -> None:
    from brawl_ket.match import ROSTER
    m = Match(random.Random(3))
```

In `tests/test_match.py`, replace:

```python
        m._start_attract()
        seen |= {f.char.name for f in m.attract.fighters.values()}
    assert len(ROSTER) == 5 and seen == {c.name for c in ROSTER}


```

with:

```python
        m._start_attract()
        seen |= {f.char.name for f in m.attract.fighters.values()}
    assert len(ROSTER) == 6 and seen == {c.name for c in ROSTER}


```

In `tests/test_match.py`, replace:

```python
    from brawl_ket.match import ROSTER, ROSTER_COLS
    assert m.picks["p1"] == (before + ROSTER_COLS if before + ROSTER_COLS < len(ROSTER) else before)
```

with:

```python
    from brawl_ket.match import ROSTER, ROSTER_COLS
    assert m.picks["p1"] == (before + ROSTER_COLS if before + ROSTER_COLS < len(ROSTER) else before)


def test_m_cutie_starts_every_round_with_no_traps() -> None:
    from brawl_ket.fight import Trap
    from brawl_ket.moves import M_CUTIE, TRAP_HOLD
    m = Match(random.Random(1))
    to_fight(m, p1=5)
    assert m.fight.fighters["p1"].char is M_CUTIE and m.fight.traps == []
    m.fight.traps.append(Trap("p1", TRAP_HOLD, 300.0, "Z"))
    ko(m, "p2")
    assert m.state == ROUND_INTRO and m.fight.traps == []
```

`tests/test_balance.py`: `PAIRS` now also has ERWIN and DOS against M-CUTIE. Both pass the bar
before her bot exists (measured: 44% and 53% for her), so nothing is marked:

In `tests/test_balance.py`, replace:

```python

def test_every_new_pairing_is_checked():
    assert len(PAIRS) == 7          # ERWIN against the other four, DOS against the first three


```

with:

```python

def test_every_new_pairing_is_checked():
    assert len(PAIRS) == 9          # ERWIN against the other five, DOS against the four besides ERWIN


```

- [ ] **Step 11: Run the whole suite and the lint**

Run: `uv run pytest -q && uvx --from 'ruff==0.15.22' ruff check src tests tools`
Expected: 1901 passed, `All checks passed!`. The bot-pairing tests (`tests/test_bot.py`) pass
for her pairings without her own bot rules (the generic bot fires her X as a 1-step wave), so no
`xfail` is needed in this task.

- [ ] **Step 12: Commit**

```bash
git add src/brawl_ket/config.py src/brawl_ket/moves.py src/brawl_ket/poses.py src/brawl_ket/fighter.py \
  src/brawl_ket/fight.py src/brawl_ket/audio.py src/brawl_ket/render.py src/brawl_ket/match.py tools/snapshot.py \
  tests/test_cutie.py tests/test_moves.py tests/test_poses.py tests/test_match.py tests/test_balance.py
git commit -m "feat: :sparkles: Brawl-Ket: M-CUTIE's rules: AMPLITUDE AMPLIFICATION, ION TRAP and SPIN

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 2: M-CUTIE drawn as her approved look, with her wave, her trap, SPIN and the charge

**Files:**
- Create: `src/brawl_ket/cutie.py`
- Modify: `src/brawl_ket/render.py`, `tools/snapshot.py`
- Modify: `tests/test_render.py`

**Interfaces:**
- Consumes (Task 1): `M_CUTIE`, `AMP_WAVES`, `Fighter.charge`, the `"charging"` action, `Trap`
  (`.state`, `.basis`, `.move`, `.x`), `Fight.traps`, `Projectile.floor`, the `"trap_close"` event,
  poses `"charge"` / `"spin"`, `HEAD_R["cutie"]`, `LIMB_W["cutie"]`.
- Produces:
  - `cutie.GOLD_PLATE`, `cutie.JUMP_SWING = 6`, `cutie.SPIN_SWING, SPIN_SPREAD, SPIN_SQUASH = 10, 1.2, 0.75`
  - `cutie.draw_cutie(surf, j: dict, lean: float, facing: int, base, strike=None, bright=0.0, swing=0.0, spread=1.0, squash=1.0) -> dict`
  - `cutie.draw_charging(surf, pose, feet, facing, base, steps: int) -> dict`;
    `cutie.charge_look(steps) -> (bright, halo strength)`; `cutie.halo(color, facing, steps) -> (Surface, (x, y))` (lru-cached)
  - `cutie.draw_spin(surf, pose, feet, facing, base, strike=None) -> dict`
  - `cutie.draw_wave(surf, x: int, floor_y: int, h: int, color, facing: int)`,
    `cutie.drive_pulse(surf, x, h, color, facing, floor_y=FLOOR_Y)` (the look's)
  - `cutie.draw_trap(surf, x: int, floor: int, color, armed: bool)`, `cutie.ion_trap(surf, x, color, armed, floor=FLOOR_Y)` (the look's)
  - `cutie.bake(size, draw) -> layers`, `cutie.blit_baked(surf, layers, topleft)`; the lru caches
    `head_layers`, `pulse_layers`, `trap_layers`, `ghost_layers`
  - `render.SELF_LIT` includes `"cutie"`; `render.STRIKER` has AMPLITUDE AMPLIFICATION, ION TRAP and
    SPIN; `render.SNAP_FRAMES`; the `"snap"` effect; `draw_puppet(..., build="cutie", flare=hair swing)`

- [ ] **Step 1: Write the failing tests.** In `tests/test_render.py`, at the end (the `look`
fixture, `same_pixels`, `BLANK`, `bot_frames` and `limb_colours` are the file's own):

In `tests/test_render.py`, replace:

```python
    seen = {tuple(surface.get_at((x, y)))[:3] for x in range(0, surface.get_width(), 2) for y in range(270, 345, 2)}
    assert PLAYER_COLORS["p1"] in seen and PLAYER_COLORS["p2"] in seen
```

with:

```python
    seen = {tuple(surface.get_at((x, y)))[:3] for x in range(0, surface.get_width(), 2) for y in range(270, 345, 2)}
    assert PLAYER_COLORS["p1"] in seen and PLAYER_COLORS["p2"] in seen


# --- M-CUTIE: her approved look (variant B), her specials, and her cached layers --------------

CUTIE_LOOK = "2026-10-21-brawl-ket-m-cutie-look.py"


@pytest.mark.parametrize("name,strike,swing,bright", [
    ("idle", None, 0, 0.0), ("crouch", None, 0, 0.0), ("jump", None, 6, 0.0), ("walk1", None, 0, 0.0),
    ("heavy_hit", ("hand_f", PURPLE), 0, 0.0), ("sweep_hit", ("foot_f", PURPLE), 0, 0.0),
    ("charge", None, 0, 0.8), ("knockdown", None, 0, 0.0),
])
@pytest.mark.parametrize("facing", [1, -1])
@pytest.mark.parametrize("base", [GREEN, PURPLE], ids=["green", "purple"])
@pytest.mark.parametrize("feet", [(120.0, 220.0), (121.0, 221.0), (120.5, 220.0)], ids=["even", "odd", "half"])
def test_m_cutie_matches_her_approved_look(look, name, strike, swing, bright, facing, base, feet):
    from brawl_ket.cutie import draw_cutie
    from brawl_ket.poses import POSES, joints
    ref = look(CUTIE_LOOK)
    pygame.init()
    a, b = pygame.Surface((240, 240)), pygame.Surface((240, 240))
    a.fill(BLANK)
    b.fill(BLANK)
    pose = POSES[name]
    ref.draw_cutie(a, pose, feet, facing, base, "B", strike, bright=bright, swing=swing)
    draw_cutie(b, joints(pose, "cutie", feet, facing), pose.lean, facing, base, strike, bright=bright, swing=swing)
    assert same_pixels(a, b)


def test_her_build_and_poses_are_the_looks(look):
    from brawl_ket import poses as PS
    ours = (PS.SCALE["cutie"], dict(PS.BUILD_BONES["cutie"]), PS.HEAD_R["cutie"], PS.LIMB_W["cutie"])
    ref = look(CUTIE_LOOK)                      # (it writes its build into the tables)
    assert ours == (PS.SCALE["cutie"], PS.BUILD_BONES["cutie"], PS.HEAD_R["cutie"], PS.LIMB_W["cutie"])
    assert PS.POSES["spin"] == ref.SPIN and PS.POSES["charge"] == ref.CHARGE


@pytest.mark.parametrize("facing", [1, -1])
@pytest.mark.parametrize("feet", [(556.0, FLOOR_Y - 70.0), (557.5, FLOOR_Y - 71.0)], ids=["whole", "half"])
def test_spin_matches_the_look(look, facing, feet):
    from brawl_ket.cutie import draw_spin
    from brawl_ket.poses import POSES, joints
    ref = look(CUTIE_LOOK)
    pygame.init()
    a, b = pygame.Surface((640, 360)), pygame.Surface((640, 360))
    a.fill(BLANK)
    b.fill(BLANK)
    ref.leg_ghosts(a, ref.SPIN, feet, facing, GREEN)        # the look's row of specials, in its order
    j = joints(ref.SPIN, "cutie", feet, facing)
    ref.spin_whirl(a, j, GREEN, "back")
    ref.draw_cutie(a, ref.SPIN, feet, facing, GREEN, "B", swing=10, spread=1.2, squash=0.75)
    ref.spin_whirl(a, j, GREEN, "front")
    draw_spin(b, POSES["spin"], feet, facing, GREEN)
    assert same_pixels(a, b)


@pytest.mark.parametrize("steps", range(1, 7))
@pytest.mark.parametrize("colour", [GREEN, PURPLE], ids=["green", "purple"])
@pytest.mark.parametrize("facing", [1, -1])
def test_her_wave_matches_the_look(look, steps, colour, facing):
    from brawl_ket.cutie import draw_wave, drive_pulse
    from brawl_ket.moves import AMP_WAVES
    ref = look(CUTIE_LOOK)
    pygame.init()
    h = AMP_WAVES[steps - 1].projectile.box.h
    for x in (172, 173):                        # both pixel parities of its middle
        a, b = pygame.Surface((640, 360)), pygame.Surface((640, 360))
        a.fill(BLANK)
        b.fill(BLANK)
        ref.drive_pulse(a, x, h, colour, facing)
        draw_wave(b, x, FLOOR_Y, h, colour, facing)
        assert same_pixels(a, b), x
    a.fill(BLANK)                               # ... and a floor line shaken a px down
    b.fill(BLANK)
    drive_pulse(a, 172, h, colour, facing, FLOOR_Y + 1)
    draw_wave(b, 172, FLOOR_Y + 1, h, colour, facing)
    assert same_pixels(a, b)


@pytest.mark.parametrize("armed", [False, True], ids=["arming", "armed"])
@pytest.mark.parametrize("colour", [GREEN, PURPLE], ids=["green", "purple"])
def test_her_trap_matches_the_look(look, armed, colour):
    from brawl_ket.cutie import draw_trap
    ref = look(CUTIE_LOOK)
    pygame.init()
    a, b = pygame.Surface((640, 360)), pygame.Surface((640, 360))
    a.fill(BLANK)
    b.fill(BLANK)
    ref.ion_trap(a, 360, colour, armed)
    draw_trap(b, 360, FLOOR_Y, colour, armed)
    assert same_pixels(a, b)


@pytest.mark.parametrize("steps", [1, 4, 6])
def test_the_charge_halo_is_the_looks_to_one_colour_step(look, steps):
    """The one approximation: one blend per pixel instead of 16. The same pixels change, and
    every one is within one step of the 15-bit grid (8) of the look's, but the head's glow
    on the background (which the look's own layer drops)."""
    from brawl_ket import palette as Pal
    from brawl_ket.cutie import charge_look, draw_charging
    from brawl_ket.poses import POSES
    ref = look(CUTIE_LOOK)
    pygame.init()
    a, b = pygame.Surface((640, 360)), pygame.Surface((640, 360))
    a.fill(BLANK)
    b.fill(BLANK)
    bright, k = charge_look(steps)
    j = ref.aura(a, lambda s: ref.draw_cutie(s, ref.CHARGE, (64, FLOOR_Y), 1, GREEN, "B", bright=bright), GREEN, k)
    ref.glow(a, j["hand_f"], 9, Pal.lighten(GREEN, 0.6), 160)
    ref.pips(a, (j["head"][0], j["head"][1] - 30), steps, GREEN)
    draw_charging(b, POSES["charge"], (64, FLOOR_Y), 1, GREEN, steps)
    pts = [(x, y) for x in range(0, 140) for y in range(120, 330)]
    changed_a = {p for p in pts if tuple(a.get_at(p))[:3] != BLANK}
    changed_b = {p for p in pts if tuple(b.get_at(p))[:3] != BLANK}
    assert changed_a == changed_b
    far = [p for p in changed_a if max(abs(u - v) for u, v in zip(a.get_at(p)[:3], b.get_at(p)[:3])) > 8]
    assert len(far) <= 16
    assert charge_look(4) == (0.8, 1.0)         # 4 steps: the look's sheet


def test_her_head_wave_and_trap_are_drawn_from_cached_layers(surface):
    from brawl_ket.cutie import head_layers, pulse_layers, trap_layers
    from brawl_ket.moves import M_CUTIE
    for cache in (head_layers, pulse_layers, trap_layers):
        cache.cache_clear()
    r = Renderer(surface)
    for fight, events in bot_frames(600, chars=(M_CUTIE, ROBERT)):
        r.draw_fight(fight, events)
    info = head_layers.cache_info()
    assert info.hits > 10 * info.misses


def cutie_frames(r, presses, frames, rival_x=600, rival=None):
    """M-CUTIE (p1) against a ROBERT at `rival_x`, `presses(i)` each frame, drawn every frame."""
    from brawl_ket.fighter import IDLE
    from brawl_ket.moves import M_CUTIE
    fight = Fight({"p1": M_CUTIE, "p2": ROBERT})
    fight.fighters["p2"].x = rival_x
    for i in range(frames):
        r.draw_fight(fight, fight.step({"p1": presses(i), "p2": rival or IDLE}))
    return fight


def test_charging_shows_a_pip_per_step_above_her_head(surface):
    from brawl_ket import palette as Pal
    from brawl_ket.fighter import FighterInput
    from brawl_ket.poses import POSES, joints
    r = Renderer(surface)
    fight = cutie_frames(r, lambda i: FighterInput(x=i in (0, 4, 8)), 10)
    me = fight.fighters["p1"]
    assert me.action == "charging" and me.charge == 3
    j = joints(POSES["charge"], "cutie", (me.x, FLOOR_Y), me.facing)
    y = round(j["head"][1] - 30)
    lit = [x for x in range(round(j["head"][0]) - 30, round(j["head"][0]) + 31)
           if tuple(surface.get_at((x, y)))[:3] == Pal.lighten(GREEN, 0.45)]
    assert len(lit) >= 3 * 5                    # three diamonds, each about 7 px across


def test_her_wave_is_drawn_on_the_floor_in_its_colour(surface):
    from brawl_ket.fighter import FighterInput
    from brawl_ket.moves import AMP_WAVES
    r = Renderer(surface)
    fight = cutie_frames(r, lambda i: FighterInput(x=i % 4 == 0 and i < 21), 21 + 16 + AMP_WAVES[0].startup + 10)
    (shot,) = fight.shots
    assert shot.move is AMP_WAVES[5]
    x = round(shot.x)
    column = {tuple(surface.get_at((x, y)))[:3] for y in range(FLOOR_Y - 50, FLOOR_Y - 2)}
    assert GREEN in column


def test_a_trap_is_dim_while_it_arms_and_lit_once_armed(surface):
    from brawl_ket import palette as Pal
    from brawl_ket.config import TRAP_ARM
    from brawl_ket.fighter import FighterInput
    from brawl_ket.moves import M_CUTIE
    trap = M_CUTIE.moves["crouch.X"]
    r = Renderer(surface)
    fight = cutie_frames(r, lambda i: FighterInput(down=True, x=i == 0), trap.startup + 2)
    (t,) = fight.traps
    ion = (round(t.x), FLOOR_Y - 17)
    assert tuple(surface.get_at(ion))[:3] == Pal.shade(GREEN, 0.5)
    for _ in range(TRAP_ARM):
        r.draw_fight(fight, fight.step({}))
    assert t.armed and tuple(surface.get_at(ion))[:3] == Pal.lighten(GREEN, 0.6)


def test_her_spin_whirls_and_its_kicking_leg_is_lit(surface):
    from brawl_ket.fighter import FighterInput
    from brawl_ket.moves import M_CUTIE
    spin = M_CUTIE.moves["air.X"]
    r = Renderer(surface)
    fight = cutie_frames(r, lambda i: FighterInput(up=i == 0, x=i == 8), 8 + spin.startup + 2)
    me = fight.fighters["p1"]
    assert me.move is spin and me.phase == "active"
    from brawl_ket.poses import joints
    j = joints(r.pose_last["p1"], "cutie", (me.x, FLOOR_Y - me.y), me.facing)
    assert GREEN in limb_colours(surface, r, me, j, "knee_f", "foot_f")     # her colour, lit


def test_a_closing_trap_snaps_a_ring_shut(surface):
    from brawl_ket.fight import Event
    r = Renderer(surface)
    fight = Fight({"p1": ROBERT, "p2": ROBERT})
    r.draw_fight(fight, [Event("trap_close", "p2", None, 300.0, FLOOR_Y)])
    assert [fx.kind for fx in r.effects] == ["snap"]
    for _ in range(20):
        r.draw_fight(fight, [])
    assert r.effects == []
```

- [ ] **Step 2: Run them to make sure they fail**

Run: `uv run pytest tests/test_render.py -q -k "cutie or her_ or spin or trap or halo or charging"`
Expected: FAIL with `ModuleNotFoundError: No module named 'brawl_ket.cutie'`.

- [ ] **Step 3: Create `src/brawl_ket/cutie.py`.** Everything in it from `GOLD_PLATE` to
`spin_whirl` is the look script's own code (variant B: `head_b` is `head`), given the joints and a
floor line; what is new is the caching (`bake`, `blit_baked`, `_parity`, the `*_layers` caches,
`draw_head`, `draw_wave`, `draw_trap`, `halo`, `ghost_layers`) and the three composites the
renderer calls (`draw_charging`, `draw_spin`, and `draw_cutie` itself, which takes the pose's
lean because the hair swing reads it):

```python
"""M-CUTIE's look: the android in a chandelier dress (variant B, the cage), and her specials.

Ported from her approved look, docs/superpowers/specs/2026-10-21-brawl-ket-m-cutie-look.py:
everything here is the look's own code (variant B only), given the joints instead of a pose and
a floor line instead of FLOOR_Y. tests/test_render.py checks her, her wave, her trap and her
SPIN against the look pixel for pixel.

The look drew everything every call. Her head, the wave and the trap are drawn once each onto
a small cached layer instead (`bake`): a see-through layer of what they paint, and a second
one of the light their additive glows throw on pixels they leave bare, which is added, not
painted. Each is anchored at the same pixel parity as where it is blitted, so Python's
round-half-to-even lands every point on the same pixel as a direct draw would: the result is
the same pixels, at two blits. The charge's halo is the one approximation: the look blended a
silhouette 16 times; here each pixel gets one blend with the alpha those 16 add up to.
"""

from __future__ import annotations

import math
from functools import lru_cache

import pygame

from . import palette as P
from .config import FLOOR_Y
from .ink import _ball, _pt, frame, limb, poly
from .ink import _towards as towards
from .poses import HEAD_R, LIMB_W, POSES, Pose, joints

# the stage's own chandelier colours (stages.py)
GOLD_PLATE = (232, 184, 72)
COAX = (176, 192, 216)
PORCELAIN = (240, 232, 232)
JOINT = (216, 208, 224)        # the pale ball joints at elbows and knees: a doll's joints
BLUSH = (240, 136, 168)
SHOE = (40, 32, 56)
GLASS = (24, 24, 56)

SPIN_SWING, SPIN_SPREAD, SPIN_SQUASH = 10, 1.2, 0.75    # SPIN: her hair blown back, the skirt flattened
JUMP_SWING = 6                  # ... and in a jump, her hair a little
HEAD_SIZE, HEAD_AT = (128, 104), (64, 40)       # a head layer, and where the head joint sits in it
PULSE_SIZE, PULSE_AT = (112, 80), (56, 72)      # a wave's layer: its middle, and the floor line
TRAP_SIZE, TRAP_AT = (56, 56), (28, 50)         # a trap's layer: its middle, and the floor line
CHARGE_SIZE, CHARGE_AT = (200, 232), (100, 216)  # the charge's halo: where her feet stand in it
HALO_SHIFTS = tuple((dx * r, dy * r) for r in (4, 2) for dx, dy in
                    ((-1, 0), (1, 0), (0, -1), (0, 1), (-1, -1), (1, -1), (-1, 1), (1, 1)))
GHOST_SIZE = (240, 200)         # SPIN's leg ghosts: drawn on a layer this big, her feet 40 px over its bottom


# --- shared helpers (the look's) -----------------------------------------------------------------


@lru_cache(maxsize=64)
def _glow_disc(r: int, color, alpha: int) -> pygame.Surface:
    g = pygame.Surface((2 * r + 2, 2 * r + 2))
    k0 = alpha / 255
    for k, a in ((1.0, 0.25), (0.7, 0.45), (0.42, 0.8)):
        pygame.draw.circle(g, tuple(round(v * a * k0) for v in color), (r + 1, r + 1), max(1, round(r * k)))
    return g


def glow(surf, c, r, color, alpha=90):
    """A soft round glow, added onto what is under it (light, not paint): three discs, the
    brightest in the middle. `alpha` (0..255) is how strong. (The look's, its disc cached.)"""
    g = _glow_disc(r, color, alpha)
    surf.blit(g, g.get_rect(center=_pt(c)), special_flags=pygame.BLEND_RGB_ADD)


def cable(surf, pts, w, color, plug=True):
    """A coax cable through pts: a capsule chain with a darker braid band every 4 px, and a
    gold SMA plug (the ferrule and its hex nut) on the last point."""
    for a, b in zip(pts, pts[1:]):
        limb(surf, a, b, w, color)
    for a, b in zip(pts, pts[1:]):
        pygame.draw.line(surf, color, _pt(a), _pt(b), w)
    band = P.shade(color, 0.72)
    for a, b in zip(pts, pts[1:]):
        dx, dy = b[0] - a[0], b[1] - a[1]
        n = math.hypot(dx, dy) or 1.0
        px, py = -dy / n, dx / n
        for k in range(1, int(n // 5) + 1):
            c = (a[0] + dx * k * 5 / n, a[1] + dy * k * 5 / n)
            pygame.draw.line(surf, band, _pt((c[0] - px * (w / 2 - 0.5), c[1] - py * (w / 2 - 0.5))),
                             _pt((c[0] + px * (w / 2 - 0.5), c[1] + py * (w / 2 - 0.5))), 1)
    if plug:
        a, b = pts[-2], pts[-1]
        dx, dy = b[0] - a[0], b[1] - a[1]
        n = math.hypot(dx, dy) or 1.0
        ux, uy = dx / n, dy / n
        nut = (b[0] + ux * 2, b[1] + uy * 2)
        tip = (b[0] + ux * 7, b[1] + uy * 7)
        limb(surf, nut, tip, 2, P.lighten(GOLD_PLATE, 0.3))
        _ball(surf, nut, 3, GOLD_PLATE)
        surf.set_at(_pt((nut[0] - 1, nut[1] - 1)), P.lighten(GOLD_PLATE, 0.6))


def ion_clip(surf, c, color, lit=True):
    """A hair clip that is a tiny ion trap: two gold electrode prongs and the glowing ion
    held between them."""
    x, y = _pt(c)
    for side in (-1, 1):
        r = pygame.Rect(0, 0, 3, 6)
        r.center = (x + side * 4, y)
        pygame.draw.rect(surf, P.INK, r.inflate(2, 2), border_radius=1)
        pygame.draw.rect(surf, GOLD_PLATE, r)
    if lit:
        glow(surf, (x, y), 7, P.lighten(color, 0.5), 110)
    pygame.draw.circle(surf, P.INK, (x, y), 3)
    pygame.draw.circle(surf, P.lighten(color, 0.55 if lit else 0.1), (x, y), 2)
    surf.set_at((x, y - 1), P.WHITE)


def shoe(surf, foot, facing, color=SHOE):
    r = pygame.Rect(0, 0, 14, 7)
    r.midbottom = _pt((foot[0] + 3 * facing, foot[1] + 6))
    pygame.draw.rect(surf, P.INK, r.inflate(4, 4), border_radius=4)
    pygame.draw.rect(surf, color, r, border_radius=3)
    surf.fill(GOLD_PLATE, (r.x + 2, r.y, r.w - 4, 1))          # a gold strap
    surf.fill(P.lighten(color, 0.3), (r.x + (r.w - 5 if facing > 0 else 2), r.y + 2, 3, 1))


# --- the cached layers ---------------------------------------------------------------------------


def bake(size, draw):
    """`draw(surface)` once onto a see-through layer and once onto black: the layer keeps
    every pixel it paints, `spill` (None if dark) the light its additive glows throw on the
    pixels it leaves bare; both cut to what they cover, with where that sits. blit_baked puts
    them down: the same pixels as drawing it there."""
    layer = pygame.Surface(size, pygame.SRCALPHA)
    draw(layer)
    spill = pygame.Surface(size)
    draw(spill)
    pygame.mask.from_surface(layer).to_surface(spill, setcolor=(0, 0, 0), unsetcolor=None)
    box = layer.get_bounding_rect()
    lit = spill.get_bounding_rect()
    return ((layer.subsurface(box).copy(), box.topleft),
            (spill.subsurface(lit).copy(), lit.topleft) if lit.w else None)


def blit_baked(surf, layers, topleft) -> None:
    (layer, (lx, ly)), spill = layers
    surf.blit(layer, (topleft[0] + lx, topleft[1] + ly))
    if spill is not None:
        light, (sx, sy) = spill
        surf.blit(light, (topleft[0] + sx, topleft[1] + sy), special_flags=pygame.BLEND_RGB_ADD)


def _parity(x: int, y: int) -> tuple[int, int]:
    return x & 1, y & 1


# --- the body (the look's) -----------------------------------------------------------------------


def limbs_back(surf, j, base, facing, w):
    dark = P.shade(base, 0.62)
    limb(surf, j["hip"], j["knee_b"], w + 1, dark)
    limb(surf, j["knee_b"], j["foot_b"], w, dark)
    _ball(surf, j["knee_b"], 3, P.shade(JOINT, 0.7))
    shoe(surf, j["foot_b"], facing, P.shade(SHOE, 0.8))
    limb(surf, j["shoulder_b"], j["elbow_b"], w - 1, dark)
    limb(surf, j["elbow_b"], j["hand_b"], w - 2, dark)
    _ball(surf, j["elbow_b"], 3, P.shade(JOINT, 0.7))
    _ball(surf, j["hand_b"], 5, P.shade(PORCELAIN, 0.72))


def leg_front(surf, j, base, facing, w, strike):
    leg = strike[1] if strike and strike[0] == "foot_f" else P.shade(base, 0.85)
    limb(surf, j["hip"], j["knee_f"], w + 1, leg)
    limb(surf, j["knee_f"], j["foot_f"], w, leg)
    _ball(surf, j["knee_f"], 3, JOINT)
    shoe(surf, j["foot_f"], facing)


def arm_front(surf, j, base, w, strike):
    arm = strike[1] if strike and strike[0] == "hand_f" else base
    limb(surf, j["shoulder_f"], j["elbow_f"], w - 1, arm)
    limb(surf, j["elbow_f"], j["hand_f"], w - 2, arm)
    _ball(surf, j["elbow_f"], 3, JOINT)
    _ball(surf, towards(j["elbow_f"], j["hand_f"], 0.8), 5, GOLD_PLATE)     # a gold cuff
    _ball(surf, j["hand_f"], 5, PORCELAIN if arm is base else P.lighten(arm, 0.55))
    # the puffed sleeve, over the shoulder joint, trimmed in gold
    sh = j["shoulder_f"]
    _ball(surf, sh, 7, arm)
    pygame.draw.circle(surf, P.lighten(arm, 0.4), _pt((sh[0] - 2, sh[1] - 3)), 2)


def bodice(surf, at, j, base):
    """The dress's top: a fitted bodice, a gold collar (the fridge's top plate) at the neck,
    an android's panel seam down the front."""
    hip, neck, sh = j["hip"], j["neck"], j["shoulder_f"]
    pts = [at(neck, 2, -7), at(sh, 2, -11), at(sh, -6, -12), at(hip, 16, -8), at(hip, 9, -10),
           at(hip, 9, 10), at(hip, 16, 8), at(sh, -6, 13), at(sh, 2, 12), at(neck, 2, 8)]
    poly(surf, pts, base)
    pygame.draw.line(surf, P.lighten(base, 0.4), _pt(at(sh, -2, 9)), _pt(at(hip, 16, 7)), 2)
    pygame.draw.line(surf, P.shade(base, 0.7), _pt(at(sh, 0, -9)), _pt(at(hip, 15, -7)), 2)
    pygame.draw.line(surf, P.shade(base, 0.78), _pt(at(sh, -4, 2)), _pt(at(hip, 14, 2)), 1)
    poly(surf, [at(neck, 4, -8), at(neck, 4, 9), at(neck, -1, 10), at(neck, -1, -9)], GOLD_PLATE)
    pygame.draw.line(surf, P.lighten(GOLD_PLATE, 0.5), _pt(at(neck, 2.5, -6)), _pt(at(neck, 2.5, 7)), 1)


def waist(j, at):
    """Where the skirt hangs from, and the x its hem centres on: the skirt hangs by gravity,
    pulled a little towards the knees so a crouch or a jump sits over the thighs."""
    wx, wy = at(j["hip"], 12, 0)
    knees = (j["knee_f"][0] + j["knee_b"][0]) / 2
    return (wx, wy), 0.3 * (knees - j["hip"][0])


def cage_hoops(j, at, spread=1.0, squash=1.0):
    (wx, wy), shift = waist(j, at)
    return [(wx + shift * u / 26, wy + u * squash, w * spread, hh)
            for u, w, hh in ((0, 26, 6), (13, 44, 9), (26, 60, 12))]


def skirt_cage_back(surf, j, at, base, bright=0.0, spread=1.0, squash=1.0):
    """The hoop skirt, behind the legs: the glow filling the bell, the far halves of the hoops."""
    hoops = cage_hoops(j, at, spread, squash)
    lit = P.lighten(base, 0.28 + 0.3 * bright)
    bell = ([(x - w / 2, y) for x, y, w, h in hoops] + [(x + w / 2, y) for x, y, w, h in reversed(hoops)])
    x, y, w, h = hoops[-1]
    under = pygame.Rect(0, 0, round(w), h)
    under.center = _pt((x, y))
    pygame.draw.polygon(surf, P.INK, [_pt(p) for p in bell], 5)
    pygame.draw.ellipse(surf, P.INK, under.inflate(4, 4))
    pygame.draw.polygon(surf, lit, [_pt(p) for p in bell])
    pygame.draw.ellipse(surf, lit, under)
    # the mixing chamber's light inside it: brighter down the middle
    x0, y0 = hoops[0][0], hoops[0][1]
    core = [(x0 - 6, y0), (x0 + 6, y0), (x + 14, y), (x - 14, y)]
    pygame.draw.polygon(surf, P.lighten(base, 0.5 + 0.3 * bright), [_pt(p) for p in core])
    for x, y, w, h in hoops:
        r = pygame.Rect(0, 0, round(w), h)
        r.center = _pt((x, y))
        pygame.draw.arc(surf, P.INK, r.inflate(2, 2), 0, math.pi, 4)
        pygame.draw.arc(surf, P.shade(GOLD_PLATE, 0.7), r, 0, math.pi, 2)


def skirt_cage_front(surf, j, at, base, facing, sway=0.0, spread=1.0, squash=1.0):
    """...and in front of the legs: the rods and coax lines between the hoops, the near halves
    of the hoops, and a coax fringe with gold plugs hanging from the hem."""
    hoops = cage_hoops(j, at, spread, squash)

    def rim(hp, k):
        x, y, w, h = hp
        return (x + k * (w / 2 - 1), y + h / 2 * math.sqrt(max(0.0, 1 - k * k)))
    for h0, h1 in zip(hoops, hoops[1:]):
        for k in (-1, -0.3, 0.4, 1):
            a, b = rim(h0, k), rim(h1, k)
            if abs(k) == 1:
                pygame.draw.line(surf, P.INK, _pt(a), _pt(b), 4)
                pygame.draw.line(surf, P.shade(GOLD_PLATE, 0.85), _pt(a), _pt(b), 2)
            else:
                m = towards(a, b, 0.5)
                m = (m[0] + 2, m[1])
                pygame.draw.lines(surf, P.INK, False, [_pt(a), _pt(m), _pt(b)], 3)
                pygame.draw.lines(surf, COAX, False, [_pt(a), _pt(m), _pt(b)], 1)
    for k in (-0.75, -0.25, 0.25, 0.75):         # the fringe: short coax tails with plugs
        x0, y0 = rim(hoops[-1], k)
        x1 = x0 - facing * sway
        pygame.draw.line(surf, P.INK, _pt((x0, y0)), _pt((x1, y0 + 7)), 4)
        pygame.draw.line(surf, COAX, _pt((x0, y0)), _pt((x1, y0 + 7)), 2)
        pygame.draw.circle(surf, P.INK, _pt((x1, y0 + 8)), 2)
        surf.set_at(_pt((x1, y0 + 8)), GOLD_PLATE)
    for x, y, w, h in hoops:
        r = pygame.Rect(0, 0, round(w), h)
        r.center = _pt((x, y))
        pygame.draw.arc(surf, P.INK, r.inflate(4, 4), math.pi, 2 * math.pi, 5)
        pygame.draw.arc(surf, GOLD_PLATE, r.inflate(1, 1), math.pi, 2 * math.pi, 3)
        surf.fill(P.lighten(GOLD_PLATE, 0.55), (r.centerx - r.w // 6, r.bottom - 1, r.w // 3, 1))


# --- the head (the look's head_b) ----------------------------------------------------------------


def led_eyes(surf, hx, hy, f, base, on_glass=False):
    for ex, ew in ((hx + 12 * f, 4), (hx + 3 * f, 5)):
        e = pygame.Rect(0, 0, ew, 8)
        e.center = (ex, hy + 3)
        if not on_glass:
            pygame.draw.rect(surf, P.INK, e.inflate(2, 0), border_radius=2)
        if on_glass:
            lit = pygame.Rect(e.x + 1, e.y + 1, ew - 1 if ew > 4 else ew - 1, 6)
            glow(surf, lit.center, 5, base, 140)
        else:
            lit = pygame.Rect(e.x + (1 if ew > 4 else 0), e.y + 3, ew - (2 if ew > 4 else 1), 4)
        surf.fill(P.lighten(base, 0.5), lit)
        surf.fill(P.lighten(base, 0.8), (lit.x, lit.bottom - 1, lit.w, 1))
        surf.fill(P.WHITE, (e.x + (1 if f > 0 else e.w - 2), e.y + 1, 1, 2))


def head(surf, j, base, facing, swing, part):
    """A shell of her colour with a dark glass face and soft LED eyes, two buns of coiled
    coax with an ion in each, a plug hanging from each bun. `part` "back" is the two hanging
    cables (drawn first), "front" the rest."""
    hx, hy = _pt(j["head"])
    r = HEAD_R["cutie"]
    f = facing
    s = swing
    buns = ((hx - 12 * f, hy - 11), (hx + 1 * f, hy - 16))
    if part == "back":
        bx, by = buns[0]
        cable(surf, [(bx - 3 * f, by + 4), (bx - (10 + s) * f, by + 13), (bx - (10 + s) * f, by + 24),
                     (bx - (6 + s) * f, by + 31)], 5, COAX)
        bx, by = buns[1]
        cable(surf, [(bx - 3 * f, by), (bx - (20 + s) * f, by + 4), (bx - (25 + s) * f, by + 14),
                     (bx - (23 + s) * f, by + 24)], 5, P.shade(COAX, 0.68))
        return
    for k, (bx, by) in enumerate(buns):          # the far bun first, under the head
        rr = 8 if k == 0 else 7
        pygame.draw.circle(surf, P.INK, (bx, by), rr + 2)
        pygame.draw.circle(surf, COAX if k == 0 else P.shade(COAX, 0.85), (bx, by), rr)
        pygame.draw.circle(surf, P.shade(COAX, 0.6), (bx, by), rr - 2, 1)       # the coil's turns
        pygame.draw.circle(surf, P.shade(COAX, 0.6), (bx, by), rr - 4, 1)
        if k == 0:
            pygame.draw.circle(surf, P.INK, (hx, hy), r + 2)
            pygame.draw.circle(surf, base, (hx, hy), r)
    pygame.draw.circle(surf, P.INK, (hx, hy), r + 2)
    pygame.draw.circle(surf, base, (hx, hy), r)
    pygame.draw.circle(surf, P.lighten(base, 0.5), (hx - 5 * f, hy - 7), 3)
    face = pygame.Rect(0, 0, 20, 16)
    face.center = (hx + 5 * f, hy + 3)
    pygame.draw.ellipse(surf, P.INK, face.inflate(4, 4))
    pygame.draw.ellipse(surf, GLASS, face)
    pygame.draw.arc(surf, P.lighten(GLASS, 0.45), face.inflate(-4, -4), 1.7, 2.7, 1)
    led_eyes(surf, hx + f, hy, f, base, on_glass=True)
    for ex, ey in ((hx + 13 * f, hy + 9), (hx + 1 * f, hy + 9)):
        glow(surf, (ex, ey), 3, BLUSH, 200)
    for bx, by in buns:
        ion_clip(surf, (bx, by), base)


@lru_cache(maxsize=1024)  # the cables follow her lean to 0.1 px: a few hundred of them, about 7 kB each
def head_layers(base, facing: int, swing: float, part: str, odd: tuple[int, int]):
    """One half of her head (its cables, or the rest), baked at a head joint of parity `odd`."""
    at = (HEAD_AT[0] + odd[0], HEAD_AT[1] + odd[1])
    return bake(HEAD_SIZE, lambda s: head(s, {"head": at}, base, facing, swing, part))


def draw_head(surf, j, base, facing, swing, part) -> None:
    """head(), from its cached layers (the front never depends on `swing`)."""
    hx, hy = _pt(j["head"])
    odd = _parity(hx, hy)
    layers = head_layers(base, facing, round(swing, 1) if part == "back" else 0.0, part, odd)
    blit_baked(surf, layers, (hx - HEAD_AT[0] - odd[0], hy - HEAD_AT[1] - odd[1]))


# --- M-CUTIE -------------------------------------------------------------------------------------


def draw_cutie(surf, j, lean, facing, base, strike=None, bright=0.0, swing=0.0, spread=1.0, squash=1.0):
    """M-CUTIE at the joints `j` (poses.joints, build "cutie") of a pose leaning `lean`, in her
    basis colour `base`. `strike` = (joint, colour) lights an attack's arm or leg; `bright`
    (0..1) is the charge's glow in the skirt; `swing` blows the hair back; `spread`/`squash`
    flare the skirt (SPIN). Returns j."""
    at = frame(j, facing)
    w = LIMB_W["cutie"]
    swing += max(-4.0, min(8.0, lean * 0.3))
    draw_head(surf, j, base, facing, swing, "back")
    limbs_back(surf, j, base, facing, w)
    skirt_cage_back(surf, j, at, base, bright, spread, squash)
    leg_front(surf, j, base, facing, w, strike)
    bodice(surf, at, j, base)
    skirt_cage_front(surf, j, at, base, facing, 2 + swing * 0.3, spread, squash)
    draw_head(surf, j, base, facing, swing, "front")
    arm_front(surf, j, base, w, strike)
    return j


# --- AMPLITUDE AMPLIFICATION ---------------------------------------------------------------------


def drive_pulse(surf, x, h, color, facing, floor_y=FLOOR_Y):
    """AMPLITUDE AMPLIFICATION's wave: a microwave drive pulse running along the floor, a
    Gaussian envelope with the carrier oscillating inside it. Taller with every step."""
    half = 12 + h * 0.42
    sig = half / 2.1
    xs = [x + k for k in range(-round(half), round(half) + 1)]
    env = [h * math.exp(-((xx - x) / sig) ** 2) for xx in xs]
    floor = floor_y - 1
    # a pool of light on the floor, and speed lines behind
    pool = pygame.Surface((round(2 * half + 16), 10))
    for k, a in ((1.0, 0.18), (0.6, 0.35)):
        rr = pygame.Rect(0, 0, round(pool.get_width() * k), round(10 * k))
        rr.center = (pool.get_width() // 2, 5)
        pygame.draw.ellipse(pool, tuple(round(v * a) for v in color), rr)
    surf.blit(pool, pool.get_rect(center=(round(x), floor + 1)), special_flags=pygame.BLEND_RGB_ADD)
    for dy, ln in ((-0.25, 16), (-0.55, 10)):
        y = floor + dy * h
        x0 = x - facing * (half * 0.9)
        pygame.draw.line(surf, P.lighten(color, 0.45), _pt((x0, y)), _pt((x0 - facing * ln, y)), 2)
    outline = [(xx, floor - e) for xx, e in zip(xs, env)] + [(xs[-1], floor), (xs[0], floor)]
    pygame.draw.polygon(surf, P.INK, [_pt(p) for p in outline], 5)
    pygame.draw.polygon(surf, P.shade(color, 0.8), [_pt(p) for p in outline])
    inner = [(xx, floor - e * 0.82) for xx, e in zip(xs, env)] + [(xs[-1], floor), (xs[0], floor)]
    pygame.draw.polygon(surf, color, [_pt(p) for p in inner])
    # the carrier: a bright line swinging between the floor and the envelope
    k = 2 * math.pi / max(7.0, half * 0.55)
    carrier = [(xx, floor - e * 0.82 * (0.5 + 0.5 * math.cos(k * (xx - x)))) for xx, e in zip(xs, env)]
    pygame.draw.lines(surf, P.lighten(color, 0.75), False, [_pt(p) for p in carrier], 2)
    top = [(xx, floor - e) for xx, e in zip(xs, env) if e > 3]
    if len(top) > 1:
        pygame.draw.lines(surf, P.lighten(color, 0.55), False, [_pt(p) for p in top], 1)


@lru_cache(maxsize=64)
def pulse_layers(h: int, color, facing: int, odd: tuple[int, int]):
    at = (PULSE_AT[0] + odd[0], PULSE_AT[1] + odd[1])
    return bake(PULSE_SIZE, lambda s: drive_pulse(s, at[0], h, color, facing, at[1]))


def draw_wave(surf, x: int, floor_y: int, h: int, color, facing: int) -> None:
    """A wave of height `h` with its middle at x, on the floor line floor_y: drive_pulse, cached."""
    odd = _parity(x, floor_y)
    blit_baked(surf, pulse_layers(h, color, facing, odd), (x - PULSE_AT[0] - odd[0], floor_y - PULSE_AT[1] - odd[1]))


def pips(surf, c, n, color):
    """The charge's steps above her head: one lit diamond per step."""
    x0 = c[0] - (n - 1) * 5
    for i in range(n):
        x, y = round(x0 + i * 10), round(c[1])
        d = [(x, y - 4), (x + 4, y), (x, y + 4), (x - 4, y)]
        pygame.draw.polygon(surf, P.INK, [(px, py) for px, py in ((x, y - 6), (x + 6, y), (x, y + 6), (x - 6, y))])
        pygame.draw.polygon(surf, P.lighten(color, 0.45), d)
        surf.set_at((x - 1, y - 1), P.WHITE)


def aura(surf, draw, color, k=1.0):
    """The look's charge glow, kept as the reference: whatever `draw` paints, ringed by a soft
    halo of her colour, blended 16 times over a full-screen layer. The game uses halo()."""
    tmp = pygame.Surface(surf.get_size(), pygame.SRCALPHA)
    j = draw(tmp)
    sil = pygame.mask.from_surface(tmp).to_surface(setcolor=(*P.lighten(color, 0.5), round(70 * k)),
                                                    unsetcolor=(0, 0, 0, 0))
    for dx, dy in HALO_SHIFTS:
        surf.blit(sil, (dx, dy))
    surf.blit(tmp, (0, 0))
    return j


def charge_look(steps: int) -> tuple[float, float]:
    """(bright, halo strength) after `steps` steps: the skirt brightest from 5 steps on, the
    halo growing with every one (the look's sheet shows 4 steps: 0.8 and 1.0)."""
    return min(1.0, steps / 5), steps / 4


@lru_cache(maxsize=48)
def halo(color, facing: int, steps: int) -> tuple[pygame.Surface, tuple[int, int]]:
    """The charge's halo round her charging silhouette (feet at CHARGE_AT), as one layer (cut
    to what it covers, and where that sits): each pixel the 16 shifted silhouettes cover gets
    the alpha their blends add up to."""
    bright, k = charge_look(steps)
    body = pygame.Surface(CHARGE_SIZE, pygame.SRCALPHA)
    pose = POSES["charge"]
    draw_cutie(body, joints(pose, "cutie", CHARGE_AT, facing), pose.lean, facing, color, bright=bright)
    sil = pygame.mask.from_surface(body)
    size = sil.get_size()
    counts = [pygame.mask.Mask(size) for _ in HALO_SHIFTS]    # counts[n]: covered more than n times
    for dx, dy in HALO_SHIFTS:
        for n in range(len(counts) - 1, 0, -1):
            counts[n].draw(counts[n - 1].overlap_mask(sil, (dx, dy)), (0, 0))
        counts[0].draw(sil, (dx, dy))
    out = pygame.Surface(CHARGE_SIZE, pygame.SRCALPHA)
    a = round(70 * k) / 255
    rgb = P.lighten(color, 0.5)
    for n, mask in enumerate(counts):
        only = mask.copy()
        if n + 1 < len(counts):
            only.erase(counts[n + 1], (0, 0))
        only.erase(sil, (0, 0))                 # under her body: she is drawn over it
        alpha = round(255 * (1 - (1 - a) ** (n + 1)))
        only.to_surface(out, setcolor=(*rgb, alpha), unsetcolor=None)
    box = out.get_bounding_rect()
    return out.subsurface(box).copy(), box.topleft


def draw_charging(surf, pose, feet, facing, base, steps) -> dict:
    """Charging: the halo, her body (in `pose`) glowing `steps` steps bright, her front hand
    alight, and a pip per step above her head (the look's row of specials). Returns the joints."""
    bright, _k = charge_look(steps)
    fx, fy = round(feet[0]), round(feet[1])
    layer, (lx, ly) = halo(base, facing, steps)
    surf.blit(layer, (fx - CHARGE_AT[0] + lx, fy - CHARGE_AT[1] + ly))
    j = draw_cutie(surf, joints(pose, "cutie", feet, facing), pose.lean, facing, base, bright=bright)
    glow(surf, j["hand_f"], 9, P.lighten(base, 0.6), 160)
    pips(surf, (j["head"][0], j["head"][1] - 30), steps, base)
    return j


# --- ION TRAP ------------------------------------------------------------------------------------


def ion_trap(surf, x, color, armed, floor=FLOOR_Y):
    """ION TRAP on the floor: two gold electrodes on a dark chip, the ion floating between.
    Dim while it arms; lit (the ion bright, the electrode tips glowing, the field round the
    ion) once armed."""
    base = pygame.Rect(0, 0, 46, 6)
    base.midbottom = (x, floor + 1)
    pygame.draw.rect(surf, P.INK, base.inflate(4, 4), border_radius=2)
    pygame.draw.rect(surf, P.shade(COAX, 0.45), base, border_radius=1)
    surf.fill(P.shade(COAX, 0.65), (base.x + 2, base.y, base.w - 4, 1))
    gold = GOLD_PLATE if armed else P.shade(GOLD_PLATE, 0.6)
    ion = (x, floor - 17)
    if armed:
        glow(surf, ion, 20, color, 200)
        for side in (-1, 1):                         # the trapping field, curving round the ion
            r = pygame.Rect(0, 0, 18, 18)
            r.center = ion
            a0 = -0.9 if side > 0 else math.pi - 0.9
            pygame.draw.arc(surf, P.lighten(color, 0.5), r, a0, a0 + 1.8, 1)
    for side in (-1, 1):
        e = pygame.Rect(0, 0, 6, 26)
        e.midbottom = (x + side * 15, base.top)
        pygame.draw.rect(surf, P.INK, e.inflate(4, 4), border_radius=3)
        pygame.draw.rect(surf, gold, e, border_radius=2)
        surf.fill(P.lighten(gold, 0.45), (e.x + 1, e.y + 2, 1, e.h - 4))
        tip = pygame.Rect(e.x, e.y, 6, 5)
        pygame.draw.rect(surf, P.lighten(color, 0.3) if armed else P.shade(color, 0.45), tip, border_radius=2)
    pygame.draw.circle(surf, P.INK, _pt(ion), 6)
    pygame.draw.circle(surf, P.lighten(color, 0.6) if armed else P.shade(color, 0.5), _pt(ion), 4)
    if armed:
        surf.set_at((ion[0] - 1, ion[1] - 1), P.WHITE)


@lru_cache(maxsize=16)
def trap_layers(color, armed: bool):
    return bake(TRAP_SIZE, lambda s: ion_trap(s, TRAP_AT[0], color, armed, TRAP_AT[1]))


def draw_trap(surf, x: int, floor: int, color, armed: bool) -> None:
    """A trap with its middle at x on the floor line `floor`: ion_trap, cached."""
    blit_baked(surf, trap_layers(color, armed), (x - TRAP_AT[0], floor - TRAP_AT[1]))


# --- SPIN ----------------------------------------------------------------------------------------


def spin_whirl(surf, j, color, part):
    """SPIN's motion: rings of light whirling round her skirt, the far half behind her
    (`part` "back"), the near half in front ("front"), with a bright head on each ring."""
    hx, hy = j["hip"]
    lit = P.lighten(color, 0.5)
    for rw, rh, dy in ((92, 18, -2), (74, 14, 14)):
        r = pygame.Rect(0, 0, rw, rh)
        r.center = (round(hx), round(hy + dy))
        if part == "back":
            pygame.draw.arc(surf, P.shade(color, 0.7), r, math.pi * 0.15, math.pi * 0.85, 2)
        else:
            pygame.draw.arc(surf, P.INK, r.inflate(2, 2), math.pi * 1.05, math.pi * 1.85, 4)
            pygame.draw.arc(surf, lit, r, math.pi * 1.05, math.pi * 1.85, 2)
            tip = (r.centerx + round(rw / 2 * math.cos(math.pi * 1.85)), r.centery - round(rh / 2 * math.sin(math.pi * 1.85)))
            pygame.draw.circle(surf, P.INK, tip, 3)
            pygame.draw.circle(surf, P.lighten(color, 0.75), tip, 2)


@lru_cache(maxsize=32)
def ghost_layers(pose: Pose, feet: tuple[float, float], facing: int, base) -> tuple[pygame.Surface, ...]:
    """The two faint copies of her front leg, each on its own layer, for her feet at `feet`
    in it (SPIN holds one pose and one height, so a spin draws these once)."""
    out = []
    for k, a in ((2, 60), (1, 110)):
        p = Pose(pose.lean, pose.thigh_f - 40 * k, pose.shin_f - 40 * k, *[getattr(pose, n) for n in
                 ("thigh_b", "shin_b", "arm_f", "fore_f", "arm_b", "fore_b")])
        j = joints(p, "cutie", feet, facing)
        s = pygame.Surface(GHOST_SIZE, pygame.SRCALPHA)
        colour = (*P.lighten(base, 0.4), a)
        limb(s, j["hip"], j["knee_f"], LIMB_W["cutie"], colour, ink=colour)
        limb(s, j["knee_f"], j["foot_f"], LIMB_W["cutie"] - 1, colour, ink=colour)
        out.append(s)
    return tuple(out)


def leg_ghosts(surf, pose, feet, facing, base):
    """Faint copies of her front leg sweeping behind it (the look's, on small cached layers
    round her feet instead of full-screen ones, shifted by an even number of px: the same pixels)."""
    ox = math.floor(feet[0]) - GHOST_SIZE[0] // 2
    oy = math.floor(feet[1]) - GHOST_SIZE[1] + 40
    ox, oy = ox - (ox & 1), oy - (oy & 1)
    for s in ghost_layers(pose, (feet[0] - ox, feet[1] - oy), facing, base):
        surf.blit(s, (ox, oy))


def draw_spin(surf, pose, feet, facing, base, strike=None) -> dict:
    """SPIN as the look draws it: the leg's ghosts and the far whirl behind her, her skirt
    flattened and widened, the near whirl in front. Returns the joints."""
    leg_ghosts(surf, pose, feet, facing, base)
    j = joints(pose, "cutie", feet, facing)
    spin_whirl(surf, j, base, "back")
    draw_cutie(surf, j, pose.lean, facing, base, strike, swing=SPIN_SWING, spread=SPIN_SPREAD, squash=SPIN_SQUASH)
    spin_whirl(surf, j, base, "front")
    return j
```

- [ ] **Step 4: Draw her in `render.py`.** Import her module, give her an accent (the portraits
and the title read `ACCENT`), drop the Task 1 stand-in, light her limbs herself (`SELF_LIT`),
draw the traps on the floor under everyone, the charge and SPIN in `_fighter`, the wave in
`_shot`, a snap when a trap closes, and the traps' boxes in the debug view:

In `src/brawl_ket/render.py`, replace:

```python
    STAGES,
)
from .dos import BEIGE, CLIP_W, clip_icon, draw_dos, draw_floppy
from .erwin import (
```

with:

```python
    STAGES,
)
from .cutie import JUMP_SWING, GOLD_PLATE, draw_charging, draw_cutie, draw_spin, draw_trap, draw_wave
from .dos import BEIGE, CLIP_W, clip_icon, draw_dos, draw_floppy
from .erwin import (
```

In `src/brawl_ket/render.py`, replace:

```python
W, H = INTERNAL_WIDTH, INTERNAL_HEIGHT
PLAYERS = ("p1", "p2")
ACCENT = {"ROBERT": P.CREAM, "BOHR": P.GOLD, "PHOEBE": P.TEAL, "ERWIN": EYE, "DOS": BEIGE}

# how each build is drawn (the skeleton's proportions are in poses.py)
TORSO_EXTRA = {"lean": 5, "heavy": 8, "toy": 5, "cutie": 5}   # the lean torso is this much thicker than a limb
PLATES = {"lean": False, "heavy": True, "toy": False, "cutie": False}   # armour: the heavy's wedge torso, plates, helm
# PHOEBE (the "toy" build): a scientist, not a puppet. Her neutral colours; the coat, the lining
# and her trousers are shades of her basis colour (docs/.../2026-10-09-brawl-ket-phoebe-design.md)
```

with:

```python
W, H = INTERNAL_WIDTH, INTERNAL_HEIGHT
PLAYERS = ("p1", "p2")
ACCENT = {"ROBERT": P.CREAM, "BOHR": P.GOLD, "PHOEBE": P.TEAL, "ERWIN": EYE, "DOS": BEIGE, "M-CUTIE": GOLD_PLATE}

# how each build is drawn (the skeleton's proportions are in poses.py)
TORSO_EXTRA = {"lean": 5, "heavy": 8, "toy": 5}   # the lean torso is this much thicker than a limb
PLATES = {"lean": False, "heavy": True, "toy": False}   # armour: the heavy's wedge torso, plates, helm
# PHOEBE (the "toy" build): a scientist, not a puppet. Her neutral colours; the coat, the lining
# and her trousers are shades of her basis colour (docs/.../2026-10-09-brawl-ket-phoebe-design.md)
```

In `src/brawl_ket/render.py`, replace:

```python
# the striking limb's joints, from the shoulder or hip out to the hand or foot that lands
STRIKE_LIMB = {"hand_f": ("shoulder_f", "elbow_f", "hand_f"), "foot_f": ("hip", "knee_f", "foot_f")}
SELF_LIT = ("cat", "dos")   # builds that draw their own lit limb: the striker adds only its trail and tip
TRAIL_LEN = 5               # a live strike's hand or foot leaves this many fading echoes
LEGEND_CHIP = 14            # the A / B colour chips under each health bar, px
```

with:

```python
# the striking limb's joints, from the shoulder or hip out to the hand or foot that lands
STRIKE_LIMB = {"hand_f": ("shoulder_f", "elbow_f", "hand_f"), "foot_f": ("hip", "knee_f", "foot_f")}
SELF_LIT = ("cat", "dos", "cutie")     # builds that draw their own lit limb: the striker adds only its trail and tip
TRAIL_LEN = 5               # a live strike's hand or foot leaves this many fading echoes
LEGEND_CHIP = 14            # the A / B colour chips under each health bar, px
```

In `src/brawl_ket/render.py`, replace:

```python
    "BOX SWIPE": "hand_f", "POUNCE": "hand_f", "BOX DROP": "hand_f",
    "MOUSE CABLE": "hand_f", "CRT DROP": "foot_f",
}

```

with:

```python
    "BOX SWIPE": "hand_f", "POUNCE": "hand_f", "BOX DROP": "hand_f",
    "MOUSE CABLE": "hand_f", "CRT DROP": "foot_f",
    "AMPLITUDE AMPLIFICATION": "hand_f", "ION TRAP": "hand_f", "SPIN": "foot_f",
}

```

In `src/brawl_ket/render.py`, replace:

```python
BOX_POP_FRAMES = 14         # THE BOX: the real cardboard box shows this long after a collapse
BOX_FADE_FRAMES = 16        # ... and the other one dissolves over this long
TRAIL_DELAY = 20            # the damage trail waits this long, then drains
TRAIL_SPEED = 0.6           # health per frame
```

with:

```python
BOX_POP_FRAMES = 14         # THE BOX: the real cardboard box shows this long after a collapse
BOX_FADE_FRAMES = 16        # ... and the other one dissolves over this long
SNAP_FRAMES = 12            # ION TRAP: a ring snapping shut on whoever it caught
TRAIL_DELAY = 20            # the damage trail waits this long, then drains
TRAIL_SPEED = 0.6           # health per frame
```

In `src/brawl_ket/render.py`, replace:

```python
                led: bool = False, eject: bool = False) -> dict:
    """One fighter, back limbs first. Returns the joints (screen px). `flare` (px) blows a
    coat's hem out behind (PHOEBE's); `strike` = (joint, colour) is the lit limb, for a build
    that draws its own (SELF_LIT); `mood`, `led` and `eject` are DOS's screen (dos.py)."""
    if build == "dos":
        j = drawn_joints(pose, build, feet, facing)
```

with:

```python
                led: bool = False, eject: bool = False) -> dict:
    """One fighter, back limbs first. Returns the joints (screen px). `flare` (px) blows a
    coat's hem out behind (PHOEBE's) or M-CUTIE's hair back; `strike` = (joint, colour) is the
    lit limb, for a build that draws its own (SELF_LIT); `mood`, `led` and `eject` are DOS's
    screen (dos.py)."""
    if build == "cutie":
        j = joints(pose, build, feet, facing)
        draw_cutie(surf, j, pose.lean, facing, body, strike, swing=flare)
        return j
    if build == "dos":
        j = drawn_joints(pose, build, feet, facing)
```

In `src/brawl_ket/render.py`, replace:

```python

        order = sorted(PLAYERS, key=lambda p: fight.fighters[p].action == "attack")
        for p in PLAYERS:
            self._shadow(p, fight.fighters[p], ox, oy)
```

with:

```python

        order = sorted(PLAYERS, key=lambda p: fight.fighters[p].action == "attack")
        for t in fight.traps:                   # on the floor, under everyone
            colour = ERROR_COLOUR[basis.error_for(t.move.colour, t.basis)]
            draw_trap(surf, round(t.x) + ox, FLOOR_Y + oy, colour, t.state != "arming")
        for p in PLAYERS:
            self._shadow(p, fight.fighters[p], ox, oy)
```

In `src/brawl_ket/render.py`, replace:

```python
            elif e.kind == "copy":
                self.effects.append(Effect("copy", e.x, e.y, COPY_FLASH_FRAMES, COPY_FLASH_FRAMES, P.WHITE))
            elif e.kind == "paste" and e.player and self._fight is not None:
                f = self._fight.fighters[e.player]
```

with:

```python
            elif e.kind == "copy":
                self.effects.append(Effect("copy", e.x, e.y, COPY_FLASH_FRAMES, COPY_FLASH_FRAMES, P.WHITE))
            elif e.kind == "trap_close":      # a ring of light snapping shut round the ion
                self.effects.append(Effect("snap", e.x, e.y - 17, SNAP_FRAMES, SNAP_FRAMES, P.WHITE))
            elif e.kind == "paste" and e.player and self._fight is not None:
                f = self._fight.fighters[e.player]
```

In `src/brawl_ket/render.py`, replace:

```python
                step = 1 + min(FADE_STEPS - 2, age * (FADE_STEPS - 1) // fx.life)
                draw_holo_box(surf, fx.x + ox, fx.y + oy, fx.facing, fx.color, 0, step)
            elif world and fx.kind == "copy":       # COPY: a selection box closing on the caught shot
                k = age / fx.life
```

with:

```python
                step = 1 + min(FADE_STEPS - 2, age * (FADE_STEPS - 1) // fx.life)
                draw_holo_box(surf, fx.x + ox, fx.y + oy, fx.facing, fx.color, 0, step)
            elif world and fx.kind == "snap":       # ION TRAP closing: a ring shrinking onto the ion
                r = round(26 * (1 - age / fx.life)) + 4
                pygame.draw.ellipse(surf, P.INK, pygame.Rect(0, 0, 2 * r + 4, r + 4).move(
                    round(fx.x) + ox - r - 2, round(fx.y) + oy - r // 2 - 2), 4)
                pygame.draw.ellipse(surf, fx.color, pygame.Rect(0, 0, 2 * r, r).move(
                    round(fx.x) + ox - r, round(fx.y) + oy - r // 2), 2)
            elif world and fx.kind == "copy":       # COPY: a selection box closing on the caught shot
                k = age / fx.life
```

In `src/brawl_ket/render.py`, replace:

```python
        feet = (f.x + ox, FLOOR_Y - f.y + oy)
        pose = self._pose(key, f)
        # a long coat blows out behind her as she moves, and trails in a jump
        flare = min(MAX_FLARE, abs(f.vx) * 2.5 + (6 if f.y > 0 else 0))
        m = f.move
        if f.action == "attack" and m is not None and m.tunnel:
```

with:

```python
        feet = (f.x + ox, FLOOR_Y - f.y + oy)
        pose = self._pose(key, f)
        # a long coat blows out behind her as she moves, and trails in a jump (M-CUTIE's hair:
        # blown back in the air, as in her look)
        flare = min(MAX_FLARE, abs(f.vx) * 2.5 + (6 if f.y > 0 else 0))
        if f.char.build == "cutie":
            flare = JUMP_SWING if f.y > 0 else 0.0
        m = f.move
        if f.action == "attack" and m is not None and m.tunnel:
```

In `src/brawl_ket/render.py`, replace:

```python
                return j["head"][0] - ox, j["head"][1] - oy
        mood, led, eject = dos_screen(f) if f.char.build == "dos" else ("calm", False, False)
        j = draw_puppet(self.surface, pose, f.char.build, feet, f.facing, body, accent, flare,
                        strike=strike_of(f), mood=mood, led=led, eject=eject)
        self._striker(key, f, j)
        if f.action == "attack" and m is not None:
```

with:

```python
                return j["head"][0] - ox, j["head"][1] - oy
        mood, led, eject = dos_screen(f) if f.char.build == "dos" else ("calm", False, False)
        if f.action == "charging":          # AMPLITUDE AMPLIFICATION: her halo and the steps so far
            j = draw_charging(self.surface, pose, feet, f.facing, body, f.charge)
        elif f.action == "attack" and m is not None and m.name == "SPIN" and f.phase == "active":
            j = draw_spin(self.surface, pose, feet, f.facing, body, strike_of(f))
        else:
            j = draw_puppet(self.surface, pose, f.char.build, feet, f.facing, body, accent, flare,
                            strike=strike_of(f), mood=mood, led=led, eject=eject)
        self._striker(key, f, j)
        if f.action == "attack" and m is not None:
```

In `src/brawl_ket/render.py`, replace:

```python
        cx, cy = left + w / 2 + ox, top + h / 2 + oy
        color = ERROR_COLOUR[basis.error_for(s.move.colour, s.basis)]
        if s.move.name == "FLOPPY":         # a spinning disk (one pasted back too)
            draw_floppy(self.surface, (cx, cy), -(self.t * 12 % 360) * s.facing, color, s.facing)
```

with:

```python
        cx, cy = left + w / 2 + ox, top + h / 2 + oy
        color = ERROR_COLOUR[basis.error_for(s.move.colour, s.basis)]
        if s.move.projectile.floor:         # M-CUTIE's wave, standing on the floor as tall as its step
            draw_wave(self.surface, round(cx), FLOOR_Y + oy, s.move.projectile.box.h, color, s.facing)
            return
        if s.move.name == "FLOPPY":         # a spinning disk (one pasted back too)
            draw_floppy(self.surface, (cx, cy), -(self.t * 12 % 360) * s.facing, color, s.facing)
```

In `src/brawl_ket/render.py`, replace:

```python
        for s in fight.shots:
            pygame.draw.rect(self.surface, P.BAD, pygame.Rect(s.box).move(ox, oy), 1)

    # --- the HUD -------------------------------------------------------------------------------
```

with:

```python
        for s in fight.shots:
            pygame.draw.rect(self.surface, P.BAD, pygame.Rect(s.box).move(ox, oy), 1)
        for t in fight.traps:
            pygame.draw.rect(self.surface, P.BAD if t.armed else P.MIST, pygame.Rect(t.box).move(ox, oy), 1)

    # --- the HUD -------------------------------------------------------------------------------
```

- [ ] **Step 5: Run the render tests**

Run: `uv run pytest tests/test_render.py -q`
Expected: 246 passed (about 20 s).

- [ ] **Step 6: Her snapshot frames.** In `tools/snapshot.py`:

In `tools/snapshot.py`, replace:

```python
  and the clipboard after it; PASTE; MOUSE CABLE out and reeling in; COPY taking BOHR's
  electricity, and PASTE crackling with it; CRT DROP;
- screen_select_erwin_dos.png: CHOOSE YOUR FIGHTER on ERWIN (P1) and DOS (P2);
- vs_*.png: the same bot-fight moments as fight_*.png, ROBERT (P1) against BOHR (P2), and
```

with:

```python
  and the clipboard after it; PASTE; MOUSE CABLE out and reeling in; COPY taking BOHR's
  electricity, and PASTE crackling with it; CRT DROP;
- moves_cutie.png, cutie_*.png: M-CUTIE's moves; AMPLITUDE AMPLIFICATION charging (1, 4 and 6
  steps), its wave in flight (2 and 6 steps) and DOS pasting one back; ION TRAP arming, armed and
  closed on a ROBERT; SPIN into a ROBERT;
- screen_select_erwin_dos.png: CHOOSE YOUR FIGHTER on ERWIN (P1) and DOS (P2);
- vs_*.png: the same bot-fight moments as fight_*.png, ROBERT (P1) against BOHR (P2), and
```

In `tools/snapshot.py`, replace:

```python
from brawl_ket.fight import Fight
from brawl_ket.fighter import Fighter
from brawl_ket.moves import BOHR, DOS, ERWIN, ROBERT
from brawl_ket.poses import POSE_NAMES, POSES, SCALE, joints, pose_for
from brawl_ket.render import Renderer, draw_puppet, outlined
```

with:

```python
from brawl_ket.fight import Fight
from brawl_ket.fighter import Fighter
from brawl_ket.moves import AMP_WAVES, BOHR, DOS, ERWIN, M_CUTIE, ROBERT
from brawl_ket.poses import POSE_NAMES, POSES, SCALE, joints, pose_for
from brawl_ket.render import Renderer, draw_puppet, outlined
```

In `tools/snapshot.py`, replace:

```python


def main(argv: list[str]) -> None:
    if len(argv) != 1:
```

with:

```python


def cutie_frames(out_dir: str) -> None:
    """M-CUTIE against a ROBERT (and a DOS): the charge, the wave, the trap and SPIN."""
    from brawl_ket.fighter import IDLE, FighterInput

    surface = pygame.Surface((W, H))

    def scene(name, presses, frames, rival_x=None, rival=lambda i: IDLE, other=ROBERT, setup=None):
        fight, r = Fight({"p1": M_CUTIE, "p2": other}), Renderer(surface)
        if rival_x is not None:
            fight.fighters["p2"].x = rival_x
        if setup is not None:
            setup(fight)
        for i in range(frames):
            r.draw_fight(fight, fight.step({"p1": presses(i), "p2": rival(i)}), {"p1": 0, "p2": 0})
        save(surface, out_dir, f"{name}.png")

    for steps in (1, 4, 6):         # charging: a press every 4 frames, saved on the last one (6 fires at once)
        last = 4 * (steps - 1)
        scene(f"cutie_charge_{steps}", lambda i, n=last: FighterInput(x=i % 4 == 0 and i <= n),
              last + (0 if steps == 6 else 1))
    for steps in (2, 6):            # the wave, well on its way
        last = 4 * (steps - 1)
        scene(f"cutie_wave_{steps}", lambda i, n=last: FighterInput(x=i % 4 == 0 and i <= n),
              last + config.CHARGE_WAIT + AMP_WAVES[0].startup + 20)
    trap = M_CUTIE.moves["crouch.X"]
    scene("cutie_trap_arming", lambda i: FighterInput(down=True, x=i == 0), trap.startup + 4)
    scene("cutie_trap_armed", lambda i: FighterInput(down=True, x=i == 0), trap.startup + config.TRAP_ARM + 4)
    scene("cutie_trap_closed", lambda i: FighterInput(down=True, x=i == 0), 80,
          rival=lambda i: FighterInput(dx=-1) if i > 30 else IDLE)
    scene("cutie_spin", lambda i: FighterInput(up=i == 0, x=i == 5), 5 + M_CUTIE.moves["air.X"].startup + 8,
          rival_x=config.START_X["p1"] + 90)
    scene("cutie_dos_paste", lambda i: IDLE, DOS.extra["paste"].startup + 14, other=DOS,
          rival=lambda i: FighterInput(y=i == 0),
          setup=lambda f: setattr(f.fighters["p2"], "clipboard", (AMP_WAVES[3], "Z")))


def main(argv: list[str]) -> None:
    if len(argv) != 1:
```

In `tools/snapshot.py`, replace:

```python
    save(move_sheet(DOS), out_dir, "moves_dos.png")
    dos_frames(out_dir)
    bohr_frames(out_dir)
    scripted_frames(out_dir)
```

with:

```python
    save(move_sheet(DOS), out_dir, "moves_dos.png")
    dos_frames(out_dir)
    save(move_sheet(M_CUTIE), out_dir, "moves_cutie.png")
    cutie_frames(out_dir)
    bohr_frames(out_dir)
    scripted_frames(out_dir)
```

Run: `uv run python tools/snapshot.py /tmp/brawl-snaps` and check by eye: `cutie_charge_4.png` (the
halo, four pips, the bright skirt), `cutie_wave_6.png` (a 60 px pulse on the floor, its pool of
light and speed lines), `cutie_trap_arming.png` / `cutie_trap_armed.png` (dim, then lit with its
field), `cutie_trap_closed.png` (ROBERT held, the snap ring), `cutie_spin.png` (the whirl rings and
leg ghosts, the lit leg on ROBERT), `cutie_dos_paste.png` (DOS's wave running back along the floor).

- [ ] **Step 7: Run the whole suite and the lint**

Run: `uv run pytest -q && uvx --from 'ruff==0.15.22' ruff check src tests tools`
Expected: 2039 passed, `All checks passed!`.

- [ ] **Step 8: Commit**

```bash
git add src/brawl_ket/cutie.py src/brawl_ket/render.py tools/snapshot.py tests/test_render.py
git commit -m "feat: :art: Brawl-Ket: M-CUTIE drawn as her approved look, with her wave, trap, SPIN and charge

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 3: Six on CHOOSE YOUR FIGHTER, her sounds and the README

**Files:**
- Modify: `src/brawl_ket/render.py` (the select layout constants, `TRAITS`, `list_top`,
  `move_label`, `_select_side`, `_portraits`, `_select`, the title's comment)
- Modify: `src/brawl_ket/audio.py` (`build_sfx`, `EVENT_SOUNDS`, `SUPERSEDES`)
- Modify: `tools/snapshot.py`, `README.md`
- Modify: `tests/test_render.py`, `tests/test_match.py`, `tests/test_audio.py`

**Interfaces:**
- Consumes: `M_CUTIE`, `ROSTER_COLS`, `grid_move`, her events and cues (`charge1`-`charge6`,
  `wave1`-`wave6`, `trap_set`, `trap_close`, `spin`).
- Produces: `render.TRAITS["M-CUTIE"] = "PATIENT AND TECHNICAL"`, `render.MOVE_LABELS`,
  `render.move_label(move) -> str`, `render.list_top(char) -> int`, `render.LIST_W = 252`,
  `render.LIST_NAME_X = 56`, `render.LIST_GAP = 10`, `render.PORTRAIT = 40`,
  `render.PORTRAIT_GAP = 6`, `render.PORTRAIT_Y = 306`, `render.SIDE_FLOOR = 168`; sounds of the same
  names as her events in `audio.build_sfx()`, each mapped to itself in `EVENT_SOUNDS`.

- [ ] **Step 1: Write the failing tests.**

`tests/test_render.py` (her trait, `MOVE_LABELS` in the ASCII check, the title's comment, and
three new tests: the labels fit, the lists clear the two rows, her portrait in the second row):

In `tests/test_render.py`, replace:

```python
def test_the_teaching_text_is_ascii_capitals():
    from brawl_ket.render import (ANY_BUTTON, BUTTON_JOBS, CARD_LINES, CLASSICAL_LINES, GOAL_LINES, HINT, LESSON_LINES,
                                  RULE_LINES, TRAITS)
    parts = (*CARD_LINES, *LESSON_LINES)
    for text in (HINT, ANY_BUTTON, *RULE_LINES, *CLASSICAL_LINES, *TRAITS.values(), *GOAL_LINES, *(job for _b, job in BUTTON_JOBS),
                 *("".join(t for t, _ in line) for line in parts)):
        assert text.isascii() and text == text.upper(), text
```

with:

```python
def test_the_teaching_text_is_ascii_capitals():
    from brawl_ket.render import (ANY_BUTTON, BUTTON_JOBS, CARD_LINES, CLASSICAL_LINES, GOAL_LINES, HINT, LESSON_LINES,
                                  MOVE_LABELS, RULE_LINES, TRAITS)
    parts = (*CARD_LINES, *LESSON_LINES)
    for text in (HINT, ANY_BUTTON, *RULE_LINES, *CLASSICAL_LINES, *TRAITS.values(), *MOVE_LABELS.values(),
                 *GOAL_LINES, *(job for _b, job in BUTTON_JOBS),
                 *("".join(t for t, _ in line) for line in parts)):
        assert text.isascii() and text == text.upper(), text
```

In `tests/test_render.py`, replace:

```python
                           "ALWAYS GREEN"]
    assert panel_lines(CHARACTERS["DOS"])[-1][1] == GREEN
    for name in ("ROBERT", "BOHR", "PHOEBE"):
        assert text[name][1:] == ["A AND X: YOUR COLOUR, B: THE OTHER", "Y SWITCHES YOUR COLOUR"], name

```

with:

```python
                           "ALWAYS GREEN"]
    assert panel_lines(CHARACTERS["DOS"])[-1][1] == GREEN
    assert text["M-CUTIE"][0] == "PATIENT AND TECHNICAL"
    for name in ("ROBERT", "BOHR", "PHOEBE", "M-CUTIE"):
        assert text[name][1:] == ["A AND X: YOUR COLOUR, B: THE OTHER", "Y SWITCHES YOUR COLOUR"], name

```

In `tests/test_render.py`, replace:

```python
    r.draw(M.Match(random.Random(1)), [])
    seen = {tuple(surface.get_at((x, y)))[:3] for x in range(440, 481, 2) for y in range(FLOOR_Y - 110, FLOOR_Y - 40, 2)}
    assert PURPLE in seen               # ERWIN on the right: DOS, last in the roster, can't be purple


```

with:

```python
    r.draw(M.Match(random.Random(1)), [])
    seen = {tuple(surface.get_at((x, y)))[:3] for x in range(440, 481, 2) for y in range(FLOOR_Y - 110, FLOOR_Y - 40, 2)}
    assert PURPLE in seen               # M-CUTIE on the right, the last fighter who can switch


```

In `tests/test_render.py`, replace:

```python
        r.draw_fight(fight, [])
    assert r.effects == []
```

with:

```python
        r.draw_fight(fight, [])
    assert r.effects == []


def test_her_specials_read_in_full_where_they_fit_and_shortened_on_the_select_screen():
    from brawl_ket.moves import M_CUTIE
    from brawl_ket.render import LIST_NAME_X, LIST_W, X_INPUTS, font, move_label
    pygame.init()
    assert [move_label(M_CUTIE.moves[s]) for s, _how in X_INPUTS] == ["AMP. AMPLIFICATION", "ION TRAP", "SPIN"]
    assert M_CUTIE.moves["stand.X"].name == "AMPLITUDE AMPLIFICATION"     # the full name, everywhere else
    chip = font(8).size("YOURS")[0] + 3
    for c in CHARACTERS.values():
        for slot, how in X_INPUTS:
            assert font(8).size(how)[0] < LIST_NAME_X, how
            assert LIST_NAME_X + font(8).size(move_label(c.moves[slot]))[0] + 4 <= LIST_W - chip, (c.name, slot)


def test_the_lists_of_specials_clear_the_two_rows_of_portraits():
    from brawl_ket import match as M
    from brawl_ket.render import LIST_GAP, LIST_W, PORTRAIT, PORTRAIT_GAP, PORTRAIT_Y, SIDE_X, list_top
    rows = -(-len(M.ROSTER) // M.ROSTER_COLS)
    assert (len(M.ROSTER), M.ROSTER_COLS, rows) == (6, 5, 2)                 # M-CUTIE starts the second row
    grid_top = PORTRAIT_Y - (rows - 1) * (PORTRAIT + PORTRAIT_GAP) - 4      # its tiles' ink and the cursors
    for c in CHARACTERS.values():
        assert list_top(c) + 2 * LIST_GAP + 8 < grid_top, c.name
    assert PORTRAIT_Y + PORTRAIT + 5 <= INTERNAL_HEIGHT - 9                 # the bottom row clears the hint
    assert INTERNAL_WIDTH / 2 + SIDE_X + LIST_W / 2 <= INTERNAL_WIDTH - 12      # and the lists the screen's edges


def test_choose_your_fighter_shows_m_cutie_in_the_second_row(surface):
    import random
    from brawl_ket import match as M
    from brawl_ket.config import PLAYER_COLORS
    from brawl_ket.render import PORTRAIT, PORTRAIT_Y
    r = Renderer(surface)
    m = M.Match(random.Random(1))
    m.state, m.picks = M.SELECT, {"p1": 5, "p2": 0}
    r.draw(m, [])
    ring = {tuple(surface.get_at((x, PORTRAIT_Y + PORTRAIT // 2)))[:3] for x in range(150, 230)}
    assert PLAYER_COLORS["p1"] in ring or P.lighten(PLAYER_COLORS["p1"], 0.6) in ring
```

`tests/test_match.py`:

In `tests/test_match.py`, replace:

```python
    ko(m, "p2")
    assert m.state == ROUND_INTRO and m.fight.traps == []
```

with:

```python
    ko(m, "p2")
    assert m.state == ROUND_INTRO and m.fight.traps == []


def test_m_cutie_is_down_a_row_from_robert_and_back_up() -> None:
    from brawl_ket.match import ROSTER, grid_move
    assert ROSTER[5].name == "M-CUTIE"
    assert grid_move(0, 0, 1) == 5 and grid_move(5, 0, -1) == 0 and grid_move(1, 0, 1) == 1
    assert grid_move(5, 1, 0) == 0 and grid_move(0, -1, 0) == 5       # and round the roster
```

`tests/test_audio.py`:

In `tests/test_audio.py`, replace:

```python
    assert audio.sounds_for([Event("projectile", "p1"), Event("floppy", "p1")]) == ["floppy"]
    assert audio.sounds_for([Event("projectile", "p1"), Event("paste", "p1")]) == ["paste"]
```

with:

```python
    assert audio.sounds_for([Event("projectile", "p1"), Event("floppy", "p1")]) == ["floppy"]
    assert audio.sounds_for([Event("projectile", "p1"), Event("paste", "p1")]) == ["paste"]


CUTIE_SOUNDS = (*(f"charge{n}" for n in range(1, 7)), *(f"wave{n}" for n in range(1, 7)), "trap_set", "trap_close",
                "spin")


def test_m_cutie_has_her_sounds() -> None:
    sfx = audio.build_sfx()
    for kind in CUTIE_SOUNDS:
        assert audio.EVENT_SOUNDS.get(kind) == kind and kind in sfx, kind
    assert audio.EVENT_SOUNDS["trap"] is None          # the fighter's own: the fight makes it a trap


def crossings(samples) -> int:
    return sum(1 for a, b in zip(samples, samples[1:]) if (a < 0) != (b < 0))


def test_each_charge_step_blips_higher_and_a_bigger_wave_whooshes_deeper() -> None:
    sfx = audio.build_sfx()
    blips = [crossings(sfx[f"charge{n}"]) for n in range(1, 7)]
    assert blips == sorted(blips) and len(set(blips)) == 6
    tones = [audio.tone(900 - 100 * n, 0.2, 0.16, "triangle", decay=7, slide=0.5) for n in range(1, 7)]
    whoosh = [crossings(t) for t in tones]              # the whoosh's tone, without its noise
    assert whoosh == sorted(whoosh, reverse=True)


def test_her_wave_replaces_the_photons_sound() -> None:
    assert audio.sounds_for([Event("projectile", "p1"), Event("wave3", "p1")]) == ["wave3"]
```

- [ ] **Step 2: Run them to make sure they fail**

Run: `uv run pytest tests/test_render.py tests/test_match.py tests/test_audio.py -q`
Expected: FAIL: `ImportError: cannot import name 'MOVE_LABELS'` (and `list_top`, `LIST_W`), her
trait missing from `panel_lines`, and the audio tests' stand-in sounds (`EVENT_SOUNDS["wave1"]` is
`"photon"`, not `"wave1"`). `test_m_cutie_is_down_a_row_from_robert_and_back_up` already passes
(`grid_move` was built for a second row).

- [ ] **Step 3: The select screen and her trait** in `src/brawl_ket/render.py`. The constants
first (the layout's numbers, her trait and the one shortened name), then `list_top` and
`move_label` after `panel_lines`, then `_select`, `_select_side` and `_portraits`:

In `src/brawl_ket/render.py`, replace:

```python
BLINK = 40                  # frames per on/off cycle of a "PRESS START" prompt

# CHOOSE YOUR FIGHTER's layout: each player's pick big on their side, the portrait strip below
SIDE_X = 176                # px from the middle to each side's fighter
SIDE_FLOOR = 178            # ... whose feet stand here
PORTRAIT = 56               # a portrait tile, px square
PORTRAIT_GAP = 8
PORTRAIT_Y = 284            # the (last) row of portraits' top
# the select screen: what each fighter is, in a line, and how its X moves are entered
TRAITS = {"ROBERT": "FAST AND LIGHT", "BOHR": "SLOW AND HEAVY", "PHOEBE": "TALL AND TRICKY",
          "ERWIN": "QUICK AND SLIPPERY", "DOS": "SLOW AND CLASSICAL"}
X_INPUTS = (("stand.X", "X"), ("crouch.X", "DOWN+X"), ("air.X", "AIR X"))
RULE_LINES = ("A AND X: YOUR COLOUR, B: THE OTHER", "Y SWITCHES YOUR COLOUR")
```

with:

```python
BLINK = 40                  # frames per on/off cycle of a "PRESS START" prompt

# CHOOSE YOUR FIGHTER's layout: each player's pick big on their side, the portrait grid below
SIDE_X = 176                # px from the middle to each side's fighter
SIDE_FLOOR = 168            # ... whose feet stand here
PORTRAIT = 40               # a portrait tile, px square: two rows of them fit under the move lists
PORTRAIT_GAP = 6
PORTRAIT_Y = 306            # the (last) row of portraits' top
LIST_W = 252                # a side's list of specials, px: the label, the name, the colour chip
LIST_NAME_X = 56            # ... where in it the names start
LIST_GAP = 10               # ... and the lines' spacing
MOVE_LABELS = {"AMPLITUDE AMPLIFICATION": "AMP. AMPLIFICATION"}    # names too long for that list
# the select screen: what each fighter is, in a line, and how its X moves are entered
TRAITS = {"ROBERT": "FAST AND LIGHT", "BOHR": "SLOW AND HEAVY", "PHOEBE": "TALL AND TRICKY",
          "ERWIN": "QUICK AND SLIPPERY", "DOS": "SLOW AND CLASSICAL", "M-CUTIE": "PATIENT AND TECHNICAL"}
X_INPUTS = (("stand.X", "X"), ("crouch.X", "DOWN+X"), ("air.X", "AIR X"))
RULE_LINES = ("A AND X: YOUR COLOUR, B: THE OTHER", "Y SWITCHES YOUR COLOUR")
```

In `src/brawl_ket/render.py`, replace:

```python
        lines[-1] = (lines[-1][0], BASIS_BODY[char.fixed_basis])
    return tuple(lines)


```

with:

```python
        lines[-1] = (lines[-1][0], BASIS_BODY[char.fixed_basis])
    return tuple(lines)


def list_top(char: Character) -> int:
    """The y of the first line of a fighter's specials on CHOOSE YOUR FIGHTER (DOS's one line
    lower, under what his Y does)."""
    return SIDE_FLOOR + 48 + (10 if char.copy_paste else 0)


def move_label(move) -> str:
    """A special's name as CHOOSE YOUR FIGHTER's list shows it: in full where it fits."""
    return MOVE_LABELS.get(move.name, move.name)


```

In `src/brawl_ket/render.py`, replace:

```python
        self._backdrop(dim=False)
        surf = self.surface
        # ROBERT green and the last fighter who can switch purple: the title shows both colours
        rival = next(c for c in reversed(M.ROSTER) if c.fixed_basis is None)
        for char, key, x, facing in ((M.ROSTER[0], "p1", 180, 1), (rival, "p2", 460, -1)):
```

with:

```python
        self._backdrop(dim=False)
        surf = self.surface
        # ROBERT green and the last fighter who can switch (M-CUTIE) purple: the title shows both colours
        rival = next(c for c in reversed(M.ROSTER) if c.fixed_basis is None)
        for char, key, x, facing in ((M.ROSTER[0], "p1", 180, 1), (rival, "p2", 460, -1)):
```

In `src/brawl_ket/render.py`, replace:

```python
        blit_center(surf, outlined("VS", 32, P.GOLD, thick=2), (W / 2, 104))
        self._portraits(match)
        blit_center(surf, outlined("STICK: CHOOSE   A: READY   B: BACK", 8, P.MIST), (W / 2, H - 10))

    def _select_side(self, key: str, side: int, char: Character, ready: bool) -> None:
```

with:

```python
        blit_center(surf, outlined("VS", 32, P.GOLD, thick=2), (W / 2, 104))
        self._portraits(match)
        blit_center(surf, outlined("STICK: CHOOSE   A: READY   B: BACK", 8, P.MIST), (W / 2, H - 5))

    def _select_side(self, key: str, side: int, char: Character, ready: bool) -> None:
```

In `src/brawl_ket/render.py`, replace:

```python
        blit_center(surf, outlined(char.name, 16, color, thick=2), (cx, floor + 18))
        blit_center(surf, outlined(TRAITS.get(char.name, ""), 8, P.MIST), (cx, floor + 34))
        top = floor + 48
        if char.copy_paste:                 # DOS: what his Y does, and his one colour, on one line
            self._parts(((CLASSICAL_LINES[1] + "  ", P.MIST), (CLASSICAL_LINES[-1], BASIS_BODY[char.fixed_basis])),
                        (cx, floor + 45))
            top += 10
        left = round(cx - 118)
        for i, (slot, how) in enumerate(X_INPUTS):
            y = top + 11 * i
            move = char.moves[slot]
            surf.blit(outlined(how, 8, P.GOLD), (left, y))
            surf.blit(outlined(move.name, 8, P.WHITE), (left + 62, y))
            self._colour_chip(move, (left + 236, y + 4))
        if ready:
            self._stamp("READY!", (cx + side * 64, floor - 120), P.GOOD)

    def _portraits(self, match: M.Match) -> None:
```

with:

```python
        blit_center(surf, outlined(char.name, 16, color, thick=2), (cx, floor + 18))
        blit_center(surf, outlined(TRAITS.get(char.name, ""), 8, P.MIST), (cx, floor + 34))
        if char.copy_paste:                 # DOS: what his Y does, and his one colour, on one line
            self._parts(((CLASSICAL_LINES[1] + "  ", P.MIST), (CLASSICAL_LINES[-1], BASIS_BODY[char.fixed_basis])),
                        (cx, floor + 45))
        top = list_top(char)
        left = round(cx - LIST_W / 2)
        for i, (slot, how) in enumerate(X_INPUTS):
            y = top + LIST_GAP * i
            move = char.moves[slot]
            surf.blit(outlined(how, 8, P.GOLD), (left, y))
            surf.blit(outlined(move_label(move), 8, P.WHITE), (left + LIST_NAME_X, y))
            self._colour_chip(move, (left + LIST_W, y + 4))
        if ready:
            self._stamp("READY!", (cx + side * 64, floor - 110), P.GOOD)

    def _portraits(self, match: M.Match) -> None:
```

In `src/brawl_ket/render.py`, replace:

```python
            pygame.draw.rect(surf, P.INK, ring.inflate(2, 2), 4, border_radius=5)
            pygame.draw.rect(surf, lit, ring, 3, border_radius=5)
            tag = outlined(key[1] + "P", 8, colour)
            surf.blit(tag, (ring.left - 2 if tag_side < 0 else ring.right - tag.get_width() + 2, ring.top - 11))

    def _stage_select(self, match: M.Match) -> None:
```

with:

```python
            pygame.draw.rect(surf, P.INK, ring.inflate(2, 2), 4, border_radius=5)
            pygame.draw.rect(surf, lit, ring, 3, border_radius=5)
            tag = outlined(key[1] + "P", 8, colour)     # in the tile's top corner: the rows sit close
            surf.blit(tag, (tile.left + 1 if tag_side < 0 else tile.right - tag.get_width() - 1, tile.top + 1))

    def _stage_select(self, match: M.Match) -> None:
```

- [ ] **Step 4: Her sounds** in `src/brawl_ket/audio.py` (the blips climb a whole tone a step;
the whoosh's tone falls 100 Hz a step; her wave replaces the photon's sound, as a FLOPPY does):

In `src/brawl_ket/audio.py`, replace:

```python
        "copy": concat(tone(c("A5"), 0.03, 0.18, "pulse"), tone(0, 0.02, 0), tone(c("A5"), 0.03, 0.18, "pulse")),
        "paste": concat(tone(c("A5"), 0.03, 0.18, "pulse"), tone(0, 0.02, 0), tone(c("E6"), 0.07, 0.2, "pulse", decay=12)),
    }

```

with:

```python
        "copy": concat(tone(c("A5"), 0.03, 0.18, "pulse"), tone(0, 0.02, 0), tone(c("A5"), 0.03, 0.18, "pulse")),
        "paste": concat(tone(c("A5"), 0.03, 0.18, "pulse"), tone(0, 0.02, 0), tone(c("E6"), 0.07, 0.2, "pulse", decay=12)),
        # M-CUTIE: a blip for each charge step, a whole tone higher each time; the wave's whoosh,
        # deeper the bigger it is; ION TRAP's click and hum, and its snap; SPIN's whirr
        **{f"charge{n}": tone(c("C5", 2 * (n - 1)), 0.05, 0.18, "pulse", decay=14) for n in range(1, 7)},
        **{f"wave{n}": mix(tone(900 - 100 * n, 0.2, 0.16, "triangle", decay=7, slide=0.5),
                           noise_wave(0.18, 0.08 + 0.02 * n, decay=12, hold=1 + n, seed=40 + n)) for n in range(1, 7)},
        "trap_set": concat(tone(c("D6"), 0.02, 0.18, "pulse"), tone(110, 0.25, 0.12, "sine", decay=4)),
        "trap_close": mix(tone(c("A6"), 0.04, 0.2, "square", decay=40, slide=0.5),
                          noise_wave(0.05, 0.25, decay=60, hold=1, seed=47)),
        "spin": mix(tone(240, 0.3, 0.14, "saw", decay=3, slide=1.6), noise_wave(0.3, 0.08, decay=4, hold=3, seed=49)),
    }

```

In `src/brawl_ket/audio.py`, replace:

```python
                "floppy": "floppy", "mouse": "mouse", "crt_drop": "crt_drop", "copy": "copy",
                "paste": "paste",
                # M-CUTIE (stand-ins until her own sounds: Task 3); "trap" is the fighter's own,
                # which the fight turns into a trap on the floor
                **{f"charge{n}": None for n in range(1, 7)}, **{f"wave{n}": "photon" for n in range(1, 7)},
                "trap": None, "trap_set": "blip", "trap_close": None, "spin": "swing",
                "land": None, "ko": None, "timeout": None}   # ko/timeout: the cues play those
SUPERSEDES = {"measure": "hit",     # MEASURE's zap replaces the thump of its own throw
              "laser": "photon",    # a LASER is a projectile too: its zap, not the photon's
              "floppy": "photon",   # ... and so are a FLOPPY
              "paste": "photon"}    # ... and a PASTE


```

with:

```python
                "floppy": "floppy", "mouse": "mouse", "crt_drop": "crt_drop", "copy": "copy",
                "paste": "paste",
                # M-CUTIE; "trap" is the fighter's own, which the fight turns into a trap on the floor
                **{f"charge{n}": f"charge{n}" for n in range(1, 7)}, **{f"wave{n}": f"wave{n}" for n in range(1, 7)},
                "trap": None, "trap_set": "trap_set", "trap_close": "trap_close", "spin": "spin",
                "land": None, "ko": None, "timeout": None}   # ko/timeout: the cues play those
SUPERSEDES = {"measure": "hit",     # MEASURE's zap replaces the thump of its own throw
              "laser": "photon",    # a LASER is a projectile too: its zap, not the photon's
              "floppy": "photon",   # ... and so are a FLOPPY
              "paste": "photon",    # ... and a PASTE
              **{f"wave{n}": "photon" for n in range(1, 7)}}    # ... and M-CUTIE's wave


```

- [ ] **Step 5: The select screen's snapshot.** In `tools/snapshot.py`:

In `tools/snapshot.py`, replace:

```python
  closed on a ROBERT; SPIN into a ROBERT;
- screen_select_erwin_dos.png: CHOOSE YOUR FIGHTER on ERWIN (P1) and DOS (P2);
- vs_*.png: the same bot-fight moments as fight_*.png, ROBERT (P1) against BOHR (P2), and
  vs_close.png, the two walked into each other;
```

with:

```python
  closed on a ROBERT; SPIN into a ROBERT;
- screen_select_erwin_dos.png: CHOOSE YOUR FIGHTER on ERWIN (P1) and DOS (P2);
- screen_select_cutie.png: CHOOSE YOUR FIGHTER on M-CUTIE (P1, ready: the second row) and DOS (P2);
- vs_*.png: the same bot-fight moments as fight_*.png, ROBERT (P1) against BOHR (P2), and
  vs_close.png, the two walked into each other;
```

In `tools/snapshot.py`, replace:

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

with:

```python

def select_frame(out_dir: str) -> None:
    """CHOOSE YOUR FIGHTER with ERWIN and DOS picked (their traits, DOS's Y and ALWAYS GREEN), and
    with M-CUTIE (P1, in the second row) against DOS, ready."""
    from brawl_ket import match as M

    surface = pygame.Surface((W, H))
    for picks, ready, name in (({"p1": 3, "p2": 4}, False, "screen_select_erwin_dos.png"),
                               ({"p1": 5, "p2": 4}, True, "screen_select_cutie.png")):
        r, m = Renderer(surface), M.Match(random.Random(3))
        m.state, m.picks = M.SELECT, picks
        m.ready = {"p1": ready, "p2": False}
        for _ in range(4):
            r.draw(m, [])
        save(surface, out_dir, name)


```

Run `uv run python tools/snapshot.py /tmp/brawl-snaps` and check `screen_select_cutie.png` by eye:
M-CUTIE alone in the second row with P1's ring; both lists of specials above the portraits, with
"AMP. AMPLIFICATION" clear of its YOURS chip; the 1P tag inside the tile's corner; READY! clear of
the P1 label.

- [ ] **Step 6: The README.** In `brawl-ket/README.md`:

In `README.md`, replace:

````markdown

**Status:**
- **The game:** five fighters (ROBERT, BOHR, PHOEBE, ERWIN and DOS), versus only, best of 3
  rounds of 60 s.
- **Screens:** chunky GBA-style puppets (and PHOEBE, a scientist in a long coat; ERWIN, Schrodinger's cat; DOS, a walking all-in-one computer) at 640x360 (x3 on the cabinet), the
  title (PLAY / QUIT) with a bot demo, a portrait-grid fighter select, stage select, a HOW TO PLAY card,
  round calls and pause.
````

with:

````markdown

**Status:**
- **The game:** six fighters (ROBERT, BOHR, PHOEBE, ERWIN, DOS and M-CUTIE), versus only, best
  of 3 rounds of 60 s.
- **Screens:** chunky GBA-style puppets (and PHOEBE, a scientist in a long coat; ERWIN, Schrodinger's cat; DOS, a walking all-in-one computer; M-CUTIE, an android in a chandelier dress) at 640x360 (x3 on the cabinet), the
  title (PLAY / QUIT) with a bot demo, a portrait-grid fighter select, stage select, a HOW TO PLAY card,
  round calls and pause.
````

In `README.md`, replace:

````markdown
  normals LOW (a jump clears them), air normals and throws MID.
- **Damage:** light 4, heavy 8, special 10, throw 10, MEASURE 12, CHARGE NOISE
  3 a shock, LASER 8, POUNCE 10, BOX DROP 8, THE BOX's swipe 8, FLOPPY 9, MOUSE CABLE 6, CRT DROP 12. Health: ROBERT 100, BOHR 115, PHOEBE 95, ERWIN 90, DOS 125. Lights stun briefly enough that mashing
  can't loop, and getting up from a knockdown is invulnerable for 8 frames.

````

with:

````markdown
  normals LOW (a jump clears them), air normals and throws MID.
- **Damage:** light 4, heavy 8, special 10, throw 10, MEASURE 12, CHARGE NOISE
  3 a shock, LASER 8, POUNCE 10, BOX DROP 8, THE BOX's swipe 8, FLOPPY 9, MOUSE CABLE 6, CRT DROP 12,
  AMPLITUDE AMPLIFICATION 7 to 15 by its steps (7, 8, 10, 11, 13, 15), ION TRAP 4, SPIN 4 a hit. Health: ROBERT 100, BOHR 115, PHOEBE 95, ERWIN 90, DOS 125, M-CUTIE 105. Lights stun briefly enough that mashing
  can't loop, and getting up from a knockdown is invulnerable for 8 frames.

````

In `README.md`, replace:

````markdown
ROUND 1 / FIGHT! -> rounds -> the result (A: rematch, B: title).

- **CHOOSE YOUR FIGHTER** is Street Fighter style: a strip of portraits along the
  bottom (five to a row; up and down move a row once there are more), one cursor
  per player (P1 blue, P2 red, both on one portrait if they pick the same fighter),
  blinking until that player presses A. Each player's pick stands big on their side,
````

with:

````markdown
ROUND 1 / FIGHT! -> rounds -> the result (A: rematch, B: title).

- **CHOOSE YOUR FIGHTER** is Street Fighter style: a grid of portraits along the
  bottom (five to a row, so M-CUTIE starts the second; up and down move a row), one cursor
  per player (P1 blue, P2 red, both on one portrait if they pick the same fighter),
  blinking until that player presses A. Each player's pick stands big on their side,
````

In `README.md`, replace:

````markdown
## The fighters

| | ROBERT | BOHR | PHOEBE | ERWIN | DOS |
|---|---|---|---|---|---|
| Build | lean and fast, high jump | heavy and slow, long reach, 115 health | tall and tricky, the longest pokes, 95 health; controls angles, not the ground | quick and slippery, the highest jump, 90 health | slow and classical, the lowest jump, 125 health; **always green** |
| X (standing) | PHOTON: a projectile; it keeps the colour it was fired in (2.5 s cooldown) | MEASURE: a dashing command throw (Y, hurts either colour) that collapses the rival into BOHR's basis | LIGHT PILLAR: a thick laser beam straight up from her raised palms: an anti-air that only ever catches someone in the air, and knocks them down (1.5 s cooldown) | THE BOX: he splits into two holographic boxes, where he stood and 120 px towards the rival. Any press or new stick direction (or 1.5 s) collapses it into a random box, with a swipe; anything that touches a box measures him, 50/50: he is in that box and it lands, or in the other and it whiffs (3 s cooldown, from the collapse) | FLOPPY: a spinning disk from his drive slot, slower than PHOTON (2.5 s cooldown) |
| Down + X | PHASE SLIDE: a low slide; it slides under photons | CHARGE NOISE: for 1 s, electric shocks all round BOHR (~60 px, every 12 frames, can't be ducked or jumped; 3 s cooldown) | TUNNEL: she dissolves and re-forms 50 px past the rival, facing them; a dotted line on the floor shows where. Untouchable only while gone, open while she re-forms (1.8 s cooldown) | POUNCE: a long low leap that knocks down; MID, so a crouch doesn't save you; a long landing (2 s cooldown) | MOUSE CABLE: he flings his mouse out along the floor on its cable (LOW, so a jump clears it, about 180 px) and reels in whoever it touches, to just in front of him, hit or bounced (3 s cooldown) |
| Air X | HADAMARD DIVE: a steep dive; when it lands, you switch basis | COLLAPSE: a drifting body slam (MID) whose landing shockwave (LOW) hits too | LASER: she hangs in the air, aims (a dotted line) and fires down and forward at 45 degrees, once per jump | BOX DROP: he lets a little box fall from the air, just in front of him (MID, his colour), once per jump | CRT DROP: a fast stomp straight down, about his case's width and then some, that knocks down; no shockwave, a long landing |
| Y | switches your colour | switches your colour | switches your colour | switches his colour, even inside THE BOX | COPY: a CTRL+C frame catches a rival's shot (a PHOTON, a LASER, a box from BOX DROP) or BOHR's crackling CHARGE NOISE into his clipboard (the icon by his chips); then PASTE fires the shot straight ahead in the colour it was fired in, or crackles with the noise himself, in its colour. Only when he is free to act |

Her weakness: she has no ground projectile and the least health, so walking straight
````

with:

````markdown
## The fighters

| | ROBERT | BOHR | PHOEBE | ERWIN | DOS | M-CUTIE |
|---|---|---|---|---|---|---|
| Build | lean and fast, high jump | heavy and slow, long reach, 115 health | tall and tricky, the longest pokes, 95 health; controls angles, not the ground | quick and slippery, the highest jump, 90 health | slow and classical, the lowest jump, 125 health; **always green** | patient and technical, in the middle on health (105) and jump, a little slower than ROBERT |
| X (standing) | PHOTON: a projectile; it keeps the colour it was fired in (2.5 s cooldown) | MEASURE: a dashing command throw (Y, hurts either colour) that collapses the rival into BOHR's basis | LIGHT PILLAR: a thick laser beam straight up from her raised palms: an anti-air that only ever catches someone in the air, and knocks them down (1.5 s cooldown) | THE BOX: he splits into two holographic boxes, where he stood and 120 px towards the rival. Any press or new stick direction (or 1.5 s) collapses it into a random box, with a swipe; anything that touches a box measures him, 50/50: he is in that box and it lands, or in the other and it whiffs (3 s cooldown, from the collapse) | FLOPPY: a spinning disk from his drive slot, slower than PHOTON (2.5 s cooldown) | AMPLITUDE AMPLIFICATION: every X press is a step, up to 6; she stands still while she charges, and the wave fires 0.25 s after her last press (at once at 6): a microwave pulse along the floor, taller and harder with every step (20 to 60 px, MID). Hit while charging, it is lost (2 s cooldown, from the fire) |
| Down + X | PHASE SLIDE: a low slide; it slides under photons | CHARGE NOISE: for 1 s, electric shocks all round BOHR (~60 px, every 12 frames, can't be ducked or jumped; 3 s cooldown) | TUNNEL: she dissolves and re-forms 50 px past the rival, facing them; a dotted line on the floor shows where. Untouchable only while gone, open while she re-forms (1.8 s cooldown) | POUNCE: a long low leap that knocks down; MID, so a crouch doesn't save you; a long landing (2 s cooldown) | MOUSE CABLE: he flings his mouse out along the floor on its cable (LOW, so a jump clears it, about 180 px) and reels in whoever it touches, to just in front of him, hit or bounced (3 s cooldown) | ION TRAP: a trap on the floor 70 px in front of her, armed after 0.3 s; a rival on the ground who steps in is held for 0.5 s (hurt only if it is their colour). A jump clears it; two at most, gone after 10 s or when she is knocked down (1 s cooldown) |
| Air X | HADAMARD DIVE: a steep dive; when it lands, you switch basis | COLLAPSE: a drifting body slam (MID) whose landing shockwave (LOW) hits too | LASER: she hangs in the air, aims (a dotted line) and fires down and forward at 45 degrees, once per jump | BOX DROP: he lets a little box fall from the air, just in front of him (MID, his colour), once per jump | CRT DROP: a fast stomp straight down, about his case's width and then some, that knocks down; no shockwave, a long landing | SPIN: she stops falling and spins forward about 100 px, one leg out, hitting up to three times (MID), once per jump; then she drops and lands into a short recovery |
| Y | switches your colour | switches your colour | switches your colour | switches his colour, even inside THE BOX | COPY: a CTRL+C frame catches a rival's shot (a PHOTON, a LASER, a box from BOX DROP, M-CUTIE's wave at its size) or BOHR's crackling CHARGE NOISE into his clipboard (the icon by his chips); then PASTE fires the shot straight ahead in the colour it was fired in, or crackles with the noise himself, in its colour. Only when he is free to act | switches her colour |

Her weakness: she has no ground projectile and the least health, so walking straight
````

In `README.md`, replace:

````markdown
ERWIN's weakness is the least health, and THE BOX is a gamble; DOS's is that his rival only ever needs green attacks against him. Design: ../docs/superpowers/specs/2026-10-21-brawl-ket-erwin-dos-design.md.

All five share the normals: A is a jab (standing, crouching, in the air), B a
heavy, a sweep (knockdown) or a jump-in, and B up close while pushing towards
the rival is a throw. A chains A, A, B.
````

with:

````markdown
ERWIN's weakness is the least health, and THE BOX is a gamble; DOS's is that his rival only ever needs green attacks against him. Design: ../docs/superpowers/specs/2026-10-21-brawl-ket-erwin-dos-design.md.

M-CUTIE traps the floor so you have to jump, then catches you in the air with SPIN or a big
wave; her weakness is that setting up takes time, so rushing her before she is ready wins.
Her wave cancels any rival shot it meets. Design:
`../docs/superpowers/specs/2026-10-21-brawl-ket-m-cutie-design.md`.

All six share the normals: A is a jab (standing, crouching, in the air), B a
heavy, a sweep (knockdown) or a jump-in, and B up close while pushing towards
the rival is a throw. A chains A, A, B.
````

In `README.md`, replace:

````markdown
|---|---|
| `basis.py` | The two bases, which errors change which, H, and each attack's error from its colour rule. Pure, exact, tested against 2x2 matrices. |
| `moves.py` | Frame data: `Move` (colour rule, height, damage, the specials' twists), `Character`, ROBERT, BOHR, PHOEBE, ERWIN and DOS. |
| `fighter.py`, `fight.py` | One fighter's state machine (basis, the Y switch); a round at a fixed 60 Hz (hits or blocks by colour, the twists, projectiles, shockwaves, the timer). THE BOX's 50/50s come from the fight's own seeded random.Random: the same seed and inputs give the same round. Pure. |
| `match.py` | Title (PLAY / QUIT), select, stage select, HOW TO PLAY, rounds, the result, pause, idle and the attract demo. Pure. |
| `tutorial.py` | The HOW TO PLAY card's scene: a real Fight played from a script, looping. Pure. |
````

with:

````markdown
|---|---|
| `basis.py` | The two bases, which errors change which, H, and each attack's error from its colour rule. Pure, exact, tested against 2x2 matrices. |
| `moves.py` | Frame data: `Move` (colour rule, height, damage, the specials' twists), `Character`, ROBERT, BOHR, PHOEBE, ERWIN, DOS and M-CUTIE (her six waves, one per step). |
| `fighter.py`, `fight.py` | One fighter's state machine (basis, the Y switch); a round at a fixed 60 Hz (hits or blocks by colour, the twists, projectiles, shockwaves, the timer). THE BOX's 50/50s come from the fight's own seeded random.Random: the same seed and inputs give the same round. M-CUTIE's charge is the fighter's "charging" state, her traps the fight's `Trap`s. Pure. |
| `match.py` | Title (PLAY / QUIT), select, stage select, HOW TO PLAY, rounds, the result, pause, idle and the attract demo. Pure. |
| `tutorial.py` | The HOW TO PLAY card's scene: a real Fight played from a script, looping. Pure. |
````

In `README.md`, replace:

````markdown
| `poses.py`, `render.py` | The skeleton and keyframe poses; the basis-coloured puppets, stage, HUD and badges, effects, the rules card and the screens (HOW TO PLAY draws its scene with a second, off-screen renderer). |
| `ink.py`, `erwin.py`, `dos.py` | The drawing primitives; ERWIN's cat and THE BOX; DOS's case, screen faces, floppy and clipboard icon (both checked pixel for pixel against their approved look scripts, and cached so the cabinet keeps its frame budget). |
| `bot.py` | The CPU for the attract demo and the tests. |
| `audio.py` | Chiptune effects, adapted from Planck Time's. No music. |
````

with:

````markdown
| `poses.py`, `render.py` | The skeleton and keyframe poses; the basis-coloured puppets, stage, HUD and badges, effects, the rules card and the screens (HOW TO PLAY draws its scene with a second, off-screen renderer). |
| `ink.py`, `erwin.py`, `dos.py` | The drawing primitives; ERWIN's cat and THE BOX; DOS's case, screen faces, floppy and clipboard icon (both checked pixel for pixel against their approved look scripts, and cached so the cabinet keeps its frame budget). |
| `cutie.py` | M-CUTIE's android, her wave, her trap, SPIN and the charge's halo (checked pixel for pixel against her approved look script; her head, wave and trap baked once into cached layers). |
| `bot.py` | The CPU for the attract demo and the tests. |
| `audio.py` | Chiptune effects, adapted from Planck Time's. No music. |
````

- [ ] **Step 7: Run the whole suite and the lint**

Run: `uv run pytest -q && uvx --from 'ruff==0.15.22' ruff check src tests tools`
Expected: 2046 passed, `All checks passed!`.

- [ ] **Step 8: Commit**

```bash
git add src/brawl_ket/render.py src/brawl_ket/audio.py tools/snapshot.py README.md \
  tests/test_render.py tests/test_match.py tests/test_audio.py
git commit -m "feat: :speaker: Brawl-Ket: six on CHOOSE YOUR FIGHTER, M-CUTIE's panel and sounds, the README

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 4: Her bot, the 60% bar, the title demo and the frame budget

**Files:**
- Modify: `src/brawl_ket/bot.py`
- Modify: `tests/test_bot.py`, `tests/test_balance.py`
- Modify: `tools/balance.py` (its docstring)

**Interfaces:**
- Consumes: `Fighter.charge`, the `"charging"` action, `Fight.traps` (`Trap.held`, `Trap.closed`,
  `Trap.owner`), `config.TRAP_MAX`, `Move.charge`, `Move.hover`, `Move.lunge`, `Move.kind`, the
  `"trap_set"`, `"spin"` and `"charge2"` events.
- Produces: `bot.TRAP_RANGE`, `TRAP_ODDS`, `CHARGE_RANGE`, `CHARGE_ODDS`, `CHARGE_STEPS`,
  `SPIN_RANGE`, `ANTI_AIR_ODDS`, `SPIN_REACH`, `SPIN_HEIGHT`, `GRAB_JUMP`, `GRAB_SPIN`;
  `Bot.charge_goal`, `Bot.spin_jump`; `Bot._cutie`, `Bot._charging`; in `tests/test_balance.py`,
  `OVER_THE_BAR` and `CASES`.

Her bot, measured against every rival over 100 and 400 rounds while this plan was written:
- **Every rate is low** because in bot fights the normals do most of the damage; her specials
  are seasoning, and each one tried at a higher rate tipped some pairing over the bar.
- **SPIN** is used only in a jump made for it (`spin_jump`): after a rival in the air at mid
  range, and at a rival winding up a dashing grab close by (MEASURE's 16-frame wind-up: she jumps
  and her SPIN knocks him out of it; from 90 px or more the grab would catch her in the air).
  Without that, BOHR's MEASURE won him 77% of their rounds; with it, she wins 49% (both over 400 rounds).
- **A trap's catch is followed up:** she walks in and hits a rival her trap holds.
- **The charge** mashes `random.randint(2, 6)` steps, one press every `PRESS_GAP` frames, then
  lets it fire.

- [ ] **Step 1: Write the failing tests.** `tests/test_bot.py`: her row in
`test_the_new_bots_use_all_their_specials` (against ERWIN, who jumps: against ROBERT, whose jumps
are fast dives that often change his colour on the way, her SPIN rarely matches), and five tests
of her rules (the module's constants are monkeypatched to isolate one rule):

In `tests/test_bot.py`, replace:

```python


@pytest.mark.parametrize("name,extra", [("ERWIN", {"box_split", "pounce", "box_drop"}),
                                        ("DOS", {"floppy", "mouse", "crt_drop", "copy", "paste"})])
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

with:

```python


# M-CUTIE SPINs at a rival in the air: against ERWIN, who jumps to drop his boxes
@pytest.mark.parametrize("name,extra,rival", [("ERWIN", {"box_split", "pounce", "box_drop"}, "ROBERT"),
                                              ("DOS", {"floppy", "mouse", "crt_drop", "copy", "paste"}, "ROBERT"),
                                              ("M-CUTIE", {"charge2", "trap_set", "spin"}, "ERWIN")])
def test_the_new_bots_use_all_their_specials(name, extra, rival):
    kinds: set[str] = set()
    for seed in range(40):
        if extra <= kinds:
            break
        fight = Fight({"p1": CHARACTERS[name], "p2": CHARACTERS[rival]}, seed=seed)
        bots = {"p1": Bot("p1", seed), "p2": Bot("p2", seed + 1000)}
        while not fight.over:
            kinds |= {e.kind for e in fight.step({k: b.input(fight) for k, b in bots.items()}) if e.player == "p1"}
    assert extra <= kinds, extra - kinds


M_CUTIE, BOHR = CHARACTERS["M-CUTIE"], CHARACTERS["BOHR"]


def far_fight(rival=ROBERT, gap=300):
    fight = Fight({"p1": M_CUTIE, "p2": rival})
    fight.fighters["p2"].x = fight.fighters["p1"].x + gap
    return fight


def test_m_cutie_mashes_a_random_2_to_6_steps_at_range(monkeypatch):
    from brawl_ket import bot as B
    monkeypatch.setattr(B, "CHARGE_ODDS", 1.0)          # only the charge, at once
    monkeypatch.setattr(B, "TRAP_ODDS", (0.0, 0.0))
    steps = set()
    for seed in range(30):
        fight = far_fight()
        me = fight.fighters["p1"]
        bot = Bot("p1", seed, skill=1.0)
        top = 0
        for _ in range(120):
            fight.step({"p1": bot.input(fight)})
            top = max(top, me.charge)
            if fight.shots:
                break
        assert fight.shots, seed                         # it fired
        steps.add(top)
    assert steps <= set(range(2, 7)) and len(steps) >= 4


def test_m_cutie_sets_traps_while_the_rival_is_far_and_never_a_third(monkeypatch):
    from brawl_ket import bot as B
    monkeypatch.setattr(B, "TRAP_ODDS", (1.0, 1.0))
    monkeypatch.setattr(B, "CHARGE_ODDS", 0.0)
    fight = far_fight(gap=320)
    bot, sets = Bot("p1", 1, skill=1.0), 0
    for _ in range(400):
        mine = sum(1 for t in fight.traps if t.owner == "p1" and not t.closed)
        events = fight.step({"p1": bot.input(fight)})
        new = sum(1 for e in events if e.kind == "trap_set")
        assert not (new and mine == 2)                   # two down: she waits
        sets += new
        fight.fighters["p2"].x = fight.fighters["p1"].x + 320     # keep the rival far
    assert sets == 2


def test_m_cutie_hits_a_rival_her_trap_holds():
    from brawl_ket.fight import Trap
    from brawl_ket.moves import TRAP_HOLD
    fight = far_fight(gap=90)
    rival = fight.fighters["p2"]
    trap = Trap("p1", TRAP_HOLD, rival.x, "Z", age=100)
    fight.traps.append(trap)
    fight.step({})                                       # it closes on him
    assert trap.held == "p2" and rival.action == "hitstun"
    bot = Bot("p1", 1, skill=1.0)
    hits = []
    for _ in range(TRAP_HOLD.hitstun + 10):
        hits += [e for e in fight.step({"p1": bot.input(fight)}) if e.kind == "hit" and e.player == "p2"]
    assert hits                                          # walked in and struck before it let go


def test_m_cutie_jumps_at_a_dashing_grab_and_spins_its_thrower_out_of_it(monkeypatch):
    from brawl_ket import bot as B
    monkeypatch.setattr(B, "GRAB_JUMP", 1.0)
    fight = far_fight(rival=BOHR, gap=70)
    me = fight.fighters["p1"]
    bot = Bot("p1", 1, skill=1.0)
    events = []
    for i in range(70):
        events += fight.step({"p1": bot.input(fight), "p2": FighterInput(x=i == 0)})   # MEASURE
    assert not [e for e in events if e.kind == "hit" and e.player == "p1" and e.error == "Y"]   # never grabbed
    assert "spin" in {e.kind for e in events if e.player == "p1"} and me.health == M_CUTIE.health


def test_m_cutie_spins_only_in_a_jump_made_for_it():
    fight = far_fight(gap=60)
    me = fight.fighters["p1"]
    fight.step({"p1": FighterInput(up=True)})
    for _ in range(3):
        fight.step({})
    bot = Bot("p1", 1, skill=1.0)
    assert not bot.input(fight).x                        # an ordinary jump: no SPIN
    bot.spin_jump, bot.air_pressed, bot.gap = True, False, 0
    assert me.y > 0 and bot.input(fight).x               # one made for it: SPIN
```

`tests/test_balance.py`: M-CUTIE joins `NEW` (12 pairings), and her pairing with PHOEBE is marked
for the user (see "More choices" above):

In `tests/test_balance.py`, replace:

```python
"""The balance bar (docs/superpowers/specs/2026-10-21-brawl-ket-erwin-dos-design.md, section 6):
bot against bot, from both sides, no fighter wins more than about 60% of the rounds against
another. Held for every pairing with ERWIN or DOS; `tools/balance.py` prints the whole table
(the older three's pairings included, which were never held to it)."""

import itertools
```

with:

```python
"""The balance bar (docs/superpowers/specs/2026-10-21-brawl-ket-erwin-dos-design.md, section 6, and
2026-10-21-brawl-ket-m-cutie-design.md, section 5): bot against bot, from both sides, no fighter
wins more than about 60% of the rounds against another. Held for every pairing with ERWIN, DOS or
M-CUTIE; `tools/balance.py` prints the whole table (the older three's pairings included, which
were never held to it)."""

import itertools
```

In `tests/test_balance.py`, replace:

```python
SEEDS = range(50)       # 100 rounds a pairing, 50 from each side
BAR = 0.62              # "about 60%", with room for 100 rounds' noise (tools/balance.py checks 0.60 over 400)
NEW = ("ERWIN", "DOS")
PAIRS = [(a, b) for a, b in itertools.combinations(CHARACTERS, 2) if a in NEW or b in NEW]

```

with:

```python
SEEDS = range(50)       # 100 rounds a pairing, 50 from each side
BAR = 0.62              # "about 60%", with room for 100 rounds' noise (tools/balance.py checks 0.60 over 400)
NEW = ("ERWIN", "DOS", "M-CUTIE")
PAIRS = [(a, b) for a, b in itertools.combinations(CHARACTERS, 2) if a in NEW or b in NEW]

```

In `tests/test_balance.py`, replace:

```python

def test_every_new_pairing_is_checked():
    assert len(PAIRS) == 9          # ERWIN against the other five, DOS against the four besides ERWIN


@pytest.mark.parametrize("pair", PAIRS, ids="-".join)
def test_no_fighter_wins_more_than_about_60_percent(pair):
    s = share(*pair)
```

with:

```python

def test_every_new_pairing_is_checked():
    assert len(PAIRS) == 12         # all 15 pairings of six but the older three's among themselves


# Over the bar, for the user to decide: with the health and walk the spec fixes, M-CUTIE plays
# PHOEBE as ROBERT does (60%) with 5 more health; about 65% over 400 rounds, whatever her bot does
# (docs/superpowers/plans/2026-10-21-brawl-ket-m-cutie.md, Task 4).
OVER_THE_BAR = {("PHOEBE", "M-CUTIE"): "M-CUTIE wins about 65% against PHOEBE: for the user to decide"}
CASES = [pytest.param(p, id="-".join(p), marks=[pytest.mark.xfail(reason=OVER_THE_BAR[p], strict=False)]
                      if p in OVER_THE_BAR else []) for p in PAIRS]


@pytest.mark.parametrize("pair", CASES)
def test_no_fighter_wins_more_than_about_60_percent(pair):
    s = share(*pair)
```

- [ ] **Step 2: Run them to make sure they fail**

Run: `uv run pytest tests/test_bot.py tests/test_balance.py -q`
Expected: 6 failed: the five new bot tests (the three that monkeypatch with `AttributeError:
<module 'brawl_ket.bot' ...> has no attribute 'CHARGE_ODDS'` / `'TRAP_ODDS'` / `'GRAB_JUMP'`, the trap
one with `assert []`, the SPIN one on its last assert) and the M-CUTIE row of
`test_the_new_bots_use_all_their_specials`; `PHOEBE-M-CUTIE` XPASSes for now (her generic bot only
fires 1-step waves), which is fine.

- [ ] **Step 3: Her bot** in `src/brawl_ket/bot.py`: the docstring, the constants (every value
measured, see above), the two new fields, the charging rule before the busy check, her rule
after DOS's, the SPIN-jump branch of `_in_air` (before CRT DROP's), the two new methods before
`_on_ground`, and the generic PHOTON rule no longer firing her X (her charge is her own rule's):

In `src/brawl_ket/bot.py`, replace:

```python
and BOHR's crackling field, PASTEs (a field only up close), FLOPPYs at range, reels in rivals
out of reach with MOUSE CABLE and CRT DROPs on one under him. DOS never switches, so he never
uses Y to dodge or feint.
"""

```

with:

```python
and BOHR's crackling field, PASTEs (a field only up close), FLOPPYs at range, reels in rivals
out of reach with MOUSE CABLE and CRT DROPs on one under him. DOS never switches, so he never
uses Y to dodge or feint. M-CUTIE sets traps while the rival is far (more often when they walk
in) and hits a rival one holds, charges a wave at range for a random 2 to 6 steps, and jumps at
a rival in the air at mid range to SPIN into them, or at one winding up a dashing grab close by.
"""

```

In `src/brawl_ket/bot.py`, replace:

```python

from . import basis
from .fight import Fight
from .fighter import FighterInput
```

with:

```python

from . import basis
from .config import TRAP_MAX
from .fight import Fight
from .fighter import FighterInput
```

In `src/brawl_ket/bot.py`, replace:

```python
MOUSE_FOLLOW = 60       # ... and strikes a rival its mouse reeled in, this many frames after the fling
DROP_RANGE = 30         # DOS stomps on a rival this close under him

_BUSY = ("hitstun", "knockdown")
```

with:

```python
MOUSE_FOLLOW = 60       # ... and strikes a rival its mouse reeled in, this many frames after the fling
DROP_RANGE = 30         # DOS stomps on a rival this close under him
TRAP_RANGE = 150        # M-CUTIE sets a trap with the rival at least this far away
TRAP_ODDS = (0.003, 0.008)  # ... a chance a frame (the second: while the rival walks in)
CHARGE_RANGE = 160      # ... and charges a wave with the rival at least this far away
CHARGE_ODDS = 0.01      # ... a chance a frame
CHARGE_STEPS = (2, 6)   # ... mashing for this many steps, picked at random each time
SPIN_RANGE = (40, 110)  # ... and jumps at a rival in the air this far away, to SPIN into them
ANTI_AIR_ODDS = 0.02    # ... a chance a frame (never at one on the ground: no bot answers that)
SPIN_REACH = (20, 100)  # ... spinning in that jump once they are this far ahead of her
SPIN_HEIGHT = (-60, 80)     # ... and her height over theirs puts her leg on their body
GRAB_JUMP = 0.8         # ... and this often jumps at a rival winding up a dashing grab (MEASURE) ...
GRAB_SPIN = 70          # ... this close, to SPIN them out of it before it dashes (from further, it would catch her)

_BUSY = ("hitstun", "knockdown")
```

In `src/brawl_ket/bot.py`, replace:

```python
        self.box_hold = 0               # THE BOX: how long this bot stays in the boxes
        self.mouse_t = -1000            # DOS: when it last flung the mouse (to follow up a pull)

    def input(self, fight: Fight) -> FighterInput:
```

with:

```python
        self.box_hold = 0               # THE BOX: how long this bot stays in the boxes
        self.mouse_t = -1000            # DOS: when it last flung the mouse (to follow up a pull)
        self.charge_goal = 0            # M-CUTIE: the steps this charge is mashed up to
        self.spin_jump = False          # ... this jump is one to SPIN in (her other jumps don't)

    def input(self, fight: Fight) -> FighterInput:
```

In `src/brawl_ket/bot.py`, replace:

```python
        if me.boxed:
            return self._in_box(me, rival)
        if me.action in _BUSY:
            self.chain.clear()
```

with:

```python
        if me.boxed:
            return self._in_box(me, rival)
        if me.action == "charging":
            return self._charging(me)
        if me.action in _BUSY:
            self.chain.clear()
```

In `src/brawl_ket/bot.py`, replace:

```python
        if me.stance == "air":
            return self._in_air(me, rival, toward, dist)
        for rule in (self._phoebe, self._erwin, self._dos):
            special = rule(fight, me, rival, toward, dist)
            if special is not None:
```

with:

```python
        if me.stance == "air":
            return self._in_air(me, rival, toward, dist)
        self.spin_jump = False
        for rule in (self._phoebe, self._erwin, self._dos, self._cutie):
            special = rule(fight, me, rival, toward, dist)
            if special is not None:
```

In `src/brawl_ket/bot.py`, replace:

```python
            self.air_pressed = True
            return self._press("x", 0)
        if air.dive is not None and air.dive[0] == 0 and ready and abs(rival.x - me.x) <= DROP_RANGE \
                and me.y > rival.y + 30:
```

with:

```python
            self.air_pressed = True
            return self._press("x", 0)
        if air.hover and air.lunge:     # SPIN: only in a jump made for it, once they are in reach
            if self.spin_jump and self.would_hurt(me, air, rival):
                if ready and SPIN_REACH[0] <= (rival.x - me.x) * me.facing <= SPIN_REACH[1] \
                        and SPIN_HEIGHT[0] <= me.y - rival.y <= SPIN_HEIGHT[1]:
                    self.air_pressed = True
                    return self._press("x", 0)
                return FighterInput(dx=toward)                  # ... and nothing else in it
            if not self.air_pressed and self.gap == 0 and dist <= AIR_RANGE:
                self.air_pressed = True
                return self._press(self.matching(me, rival), toward)   # a normal air attack
            return FighterInput(dx=toward)
        if air.dive is not None and air.dive[0] == 0 and ready and abs(rival.x - me.x) <= DROP_RANGE \
                and me.y > rival.y + 30:
```

In `src/brawl_ket/bot.py`, replace:

```python
        return None

    def _on_ground(self, me, rival, toward: int, dist: float) -> FighterInput:
        roll = self.rng.random()
```

with:

```python
        return None

    def _charging(self, me) -> FighterInput:
        """AMPLITUDE AMPLIFICATION: mash X up to this charge's goal, then let it fire."""
        if me.charge < self.charge_goal and self.gap == 0:
            return self._press("x", 0)
        return FighterInput()

    def _cutie(self, fight: Fight, me, rival, toward: int, dist: float) -> FighterInput | None:
        """M-CUTIE: up to SPIN a rival out of a dashing grab winding up close by; in to hit a rival
        her trap holds; ION TRAP while the rival is far (fewer than two down; more often when they
        walk in); AMPLITUDE AMPLIFICATION at range; and a jump at a rival in the air at mid range,
        to SPIN into them."""
        amp, spin = me.char.moves["stand.X"], me.char.moves["air.X"]
        if not amp.charge or me.action not in ("idle", "walk", "crouch") or self.gap > 0:
            return None
        m = rival.move
        if m is not None and rival.action == "attack" and rival.phase == "startup" and m.kind == "throw" \
                and m.lunge and dist <= GRAB_SPIN and rival.frame == self.react and self.rng.random() < GRAB_JUMP:
            self.down = False
            self.spin_jump = True
            return FighterInput(up=True, dx=toward)             # up, and SPIN them out of the grab
        held = rival.action == "hitstun" and any(t.held == self.rival for t in fight.traps)
        if held and not self.chain:     # a rival her trap holds: in, and hit them before it lets go
            if dist <= STRIKE_RANGE:
                button = self.matching(me, rival)
                self.down = False
                self.chain = [button, button] if button == "a" else [button]
                return self._press(self.chain.pop(0), 0)
            return FighterInput(dx=toward)
        mine = sum(1 for t in fight.traps if t.owner == self.player and not t.closed)
        walking_in = rival.action == "walk" and (rival.x - me.x) * rival.vx < 0
        if dist >= TRAP_RANGE and mine < TRAP_MAX and me.cooldowns.get("crouch.X", 0) == 0 \
                and self.rng.random() < TRAP_ODDS[walking_in]:
            self.down = True
            press = self._press("x", 0)                         # ION TRAP, from a crouch ...
            self.down = False                                   # ... and up again
            return press
        if dist >= CHARGE_RANGE and me.cooldowns.get("stand.X", 0) == 0 and self.would_hurt(me, amp, rival) \
                and self.rng.random() < CHARGE_ODDS:
            self.charge_goal = self.rng.randint(*CHARGE_STEPS)
            self.down = False
            return self._press("x", 0)                          # the first step
        if rival.y > 0 and SPIN_RANGE[0] <= dist <= SPIN_RANGE[1] and self.would_hurt(me, spin, rival) \
                and self.rng.random() < ANTI_AIR_ODDS:
            self.down = False
            self.spin_jump = True
            return FighterInput(up=True, dx=toward)             # up after them, to SPIN
        return None

    def _on_ground(self, me, rival, toward: int, dist: float) -> FighterInput:
        roll = self.rng.random()
```

In `src/brawl_ket/bot.py`, replace:

```python
        if roll < 0.01:
            return FighterInput(up=True, dx=toward)             # jump in
        if roll < 0.03 and dist > 90 and ready and special.kind == "projectile" \
                and me.cooldowns.get("stand.X", 0) == 0 and self.would_hurt(me, special, rival):
            return self._press("x", 0)                          # a PHOTON that will hurt
```

with:

```python
        if roll < 0.01:
            return FighterInput(up=True, dx=toward)             # jump in
        if roll < 0.03 and dist > 90 and ready and special.kind == "projectile" and not special.charge \
                and me.cooldowns.get("stand.X", 0) == 0 and self.would_hurt(me, special, rival):
            return self._press("x", 0)                          # a PHOTON that will hurt
```

- [ ] **Step 4: Run the bot, match and balance tests**

Run: `uv run pytest tests/test_bot.py tests/test_match.py tests/test_balance.py -q`
Expected: all pass, 1 xfailed (`PHOEBE-M-CUTIE`). `test_the_demo_picks_its_fighters_from_all_six`
(Task 1) shows the title demo plays her: the demo's bots are these.

**If a balance pairing other than PHOEBE-M-CUTIE fails,** tune in this order, rerunning
`tests/test_balance.py` after each change, and stop as soon as they pass:
1. her bot's rates and ranges (the constants above);
2. the numbers this plan chose where the spec says "about" (Decisions table): the wave move's
   recovery (16-22), SPIN's recovery (10-16), the trap's startup (8-12).

Never change a number the spec fixes (health, walk, damage, cooldowns, the step table, 0.25 s,
0.3 s, 0.5 s, 10 s, two traps, three hits), the older fighters, or `BAR`. If the bar still fails,
stop and report the `tools/balance.py` table to the user instead of loosening anything.

- [ ] **Step 5: `tools/balance.py`'s docstring:**

In `tools/balance.py`, replace:

```python
For each pair, the share of the decided rounds each fighter won, over SEEDS seeds from each
side (200 by default). The bar (docs/superpowers/specs/2026-10-21-brawl-ket-erwin-dos-design.md,
section 6): no fighter wins more than about 60% against another. tests/test_balance.py holds
every pairing with ERWIN or DOS to it; the older three's pairings are only reported here.
"""

```

with:

```python
For each pair, the share of the decided rounds each fighter won, over SEEDS seeds from each
side (200 by default). The bar (docs/superpowers/specs/2026-10-21-brawl-ket-erwin-dos-design.md,
section 6, and 2026-10-21-brawl-ket-m-cutie-design.md, section 5): no fighter wins more than about
60% against another. tests/test_balance.py holds every pairing with ERWIN, DOS or M-CUTIE to it
(but M-CUTIE against PHOEBE, left to the user); the older three's pairings are only reported here.
"""

```

Run: `uv run python tools/balance.py`
Expected: 15 lines (about 5 minutes). A prototype of this plan measured, at 200 seeds a side:

```
ROBERT v BOHR    ROBERT  34%  BOHR  66%   <- over the bar
ROBERT v PHOEBE  ROBERT  60%  PHOEBE  40%
ROBERT v ERWIN   ROBERT  40%  ERWIN  60%
ROBERT v DOS     ROBERT  55%  DOS  45%
ROBERT v M-CUTIE  ROBERT  48%  M-CUTIE  52%
  BOHR v PHOEBE  BOHR  66%  PHOEBE  34%   <- over the bar
  BOHR v ERWIN   BOHR  62%  ERWIN  38%   <- over the bar
  BOHR v DOS     BOHR  46%  DOS  54%
  BOHR v M-CUTIE  BOHR  51%  M-CUTIE  49%
PHOEBE v ERWIN   PHOEBE  54%  ERWIN  46%
PHOEBE v DOS     PHOEBE  56%  DOS  44%
PHOEBE v M-CUTIE  PHOEBE  35%  M-CUTIE  65%   <- over the bar
 ERWIN v DOS     ERWIN  49%  DOS  51%
 ERWIN v M-CUTIE  ERWIN  45%  M-CUTIE  55%
   DOS v M-CUTIE  DOS  44%  M-CUTIE  56%
```

Copy the real output into the task report. BOHR v ERWIN (62%) and the older three's pairings are
as they are on `main` (this plan changes nothing they use); PHOEBE v M-CUTIE is for the user to
decide on.

- [ ] **Step 6: The frame budget**

Run: `uv run python tools/benchmark.py`
Expected: 36 pairings plus `title + demo`. Compare within the one run (a desktop's numbers drift
by half from run to run): every pairing with M-CUTIE has a mean at most 1.3x, and a p99 at most
1.4x, the slowest pairing without her, and every mean and p99 stays under the docstring's 2 ms.
Two prototype runs of this plan measured her pairings at 0.35-0.63 ms mean and 0.58-1.01 ms p99,
the others at 0.29-0.56 ms mean and 0.37-0.87 ms p99. The `max` column shows one-off spikes of
2-3 ms, the first time a head, wave, trap or halo layer is drawn; if one shows as a hitch on the
cabinet, build her halos when the fight starts (in `Renderer.draw_fight`, beside THE BOX's
sprites: `halo(colour, facing, steps)` for both colours, facings and steps 1 to 6). If one is over, profile it
(`uv run python -m cProfile -s cumtime tools/benchmark.py | head -40`) and cache what dominates;
don't drop anything from the approved look. If the cabinet is reachable, also run the README's
on-cabinet benchmark and put its numbers in the report.

- [ ] **Step 7: Run the whole suite and the lint**

Run: `uv run pytest -q && uvx --from 'ruff==0.15.22' ruff check src tests tools`
Expected: 2054 passed, 1 xfailed, `All checks passed!`; check every touched file is LF
(`file src/brawl_ket/*.py tests/*.py tools/*.py README.md`).

- [ ] **Step 8: Commit**

```bash
git add src/brawl_ket/bot.py tests/test_bot.py tests/test_balance.py tools/balance.py
git commit -m "feat: :robot: Brawl-Ket: a bot for M-CUTIE, and her pairings on the 60% bar

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

## Self-review

**Spec coverage** (section by section, the task that implements it):
- 1, the look: the `"cutie"` build, the cage skirt (back and front halves round the legs, the
  glow brightest down the middle, the coax fringe), the buns with ion clips and plugs, the glass
  face, LED eyes and blush, the lit limb (the whole arm, sleeve included) (Task 2, pixel for pixel
  against `draw_cutie` in the look, both facings, both colours, three foot positions); the
  charge's halo, glowing hand and pips; the drive pulse; the trap dim and lit; SPIN's leg,
  flattened skirt, whirl rings and leg ghosts (Task 2, against the look's functions; the halo to
  one colour step).
- 2, the fighter: health, walk, jump, shared normals, Y (Task 1); AMPLITUDE AMPLIFICATION's charge,
  steps, cap, 0.25 s, standing still, the table, MID, the cooldown from the fire, a hit losing it,
  the short name (Tasks 1 and 3); ION TRAP's placing, arming, hold, colour rule, use, jump, two at
  most, the three ways it goes (Task 1; the round's end because every round is a new `Fight`,
  tested in `test_match.py`); SPIN's hover, forward travel, three hits, once per jump, the drop and
  the landing (Task 1).
- 3, interactions: every row has a test in `tests/test_cutie.py` (DOS copying and pasting a wave at
  its size; the wave cancelling PHOTON, FLOPPY and LASER; a trap measuring ERWIN's box, both ways;
  TUNNEL; MOUSE CABLE (the general rule, and DOS dragging her across her own trap); MEASURE).
- 4, screens, HUD and sounds: the sixth portrait in the second row, the trait, the specials'
  names (Task 3); the charge on her and the pips, the traps dim and lit (Task 2); the five kinds of
  sound, 16 in all (Task 3).
- 5, bots: her three rules, the demo, the bar (Task 4); PHOEBE's pairing over the bar is reported.
- 6, engine notes: the charging state with its step counter (`Fighter.charge`, `charge_wait`), the
  fire after 15 frames or at the cap, lost on a hit, the shot's box and damage from its step
  (`AMP_WAVES`) (Task 1); traps as a new object in `Fight` with its four states (placed is its
  first, arming frame), one owner, two each, cleared per round, a hold through the colour rule
  (Task 1); SPIN as hover + lunge + `hit_every` (Task 1).
- 7, testing: every bullet has a test in `tests/test_cutie.py`, `test_moves.py`, `test_poses.py`,
  `test_render.py`, `test_match.py`, `test_audio.py`, `test_bot.py`, `test_balance.py`; snapshots
  (Tasks 2 and 3); the benchmark (Task 4).

**Prototype run.** Every task's code and tests in this plan were applied, in order, to a scratch
copy of `brawl-ket/` while the plan was written, and the code blocks above are generated from
that copy's state after each task: after Task 1, 1901 passed; after Task 2, 2039; after Task 3,
2046; after Task 4, 2054 passed and 1 xfailed; ruff clean after each; `tools/snapshot.py` wrote all
87 frames; the benchmark and the balance table are the ones quoted. The fixes that run found are
folded in: the 32 px hurtbox, COPY's lower window, the head layers' cache size (her cables follow
her lean to 0.1 px), the hair swing tied to the air, the halo layer's height (her shoes and their
halo reach 12 px below her feet), SPIN only in a jump made for it, the grab-jump only within
70 px, and the select screen's layout.

**Type and name consistency:** `Fighter.charge` is the step count everywhere (fighter, render's
pips, bot, tests); `Move.charge` is the wave tuple (moves, fighter, bot's `not special.charge`);
`Trap` fields (`owner`, `move`, `x`, `basis`, `age`, `closed`, `held`) and `state` strings are the
same in fight, render, bot and tests; events and cues (`charge1`-`charge6`, `wave1`-`wave6`,
`trap`, `trap_set`, `trap_close`, `spin`) are spelled the same in moves, fighter, fight, render,
audio and the tests; `draw_cutie(surf, j, lean, facing, base, ...)` is called the same way by
`draw_puppet`, `draw_charging`, `draw_spin`, `halo` and the tests.
