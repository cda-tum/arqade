# Brawl-Ket: design

A one-on-one fighting game for the ARQADE cabinet, in the style of a small
Street Fighter: health bars, light and heavy attacks, combos, specials. The
twist is quantum error correction, and it is exact. Each fighter is a logical
qubit protected by a repetition code. A hit is an error on one of its physical
qubits, and the fighting game's oldest mind game, high/low mix-ups, is the
choice between a bit-flip and a phase-flip code. The name is a pun on bra-ket
notation and tournament brackets.

- **Players:** 2, versus. There is no CPU mode; a bot plays only the attract
  demo and the tests.
- **Target:** the Batocera cabinet in `../../../AGENTS.md`: a Pi 4, 1920x1080,
  two 6-button pads, Python 3.11 and pygame 2.5.2.
- **Look:** procedural "chunky puppet" pixel art. The fighters are thick
  outlined capsule limbs on a skeleton, animated by interpolating keyframe
  poses. The stage is a GBA-style quantum lab. It renders at 640x360,
  scaled x3.

## 1. Controls

There are no motion inputs: passers-by struggle most with learning the
controls, so every move is the stick plus a single button.

| Input | Action |
|---|---|
| Stick left / right | Walk. There is no block: defence is the stance (section 2). |
| Stick up | Jump (neutral, forward or back). |
| Stick down | Crouch, which switches your code (section 2). |
| A | Light attack: fast, and chains A → A → B. |
| B | Heavy attack: slower, with knockback. |
| B up close while pushing towards the rival | Throw. |
| X | Special. Which one depends on whether you are standing, crouching or in the air. |
| Start | Pause. |
| Start + Select | Quit. |

The raw buttons are A = 1, B = 2, X = 0, Start = 9 and Select = 8, as
confirmed on the cabinet. Inputs are buffered for 6 frames, so chains are
forgiving.

## 2. Core rules: the fighter is a code

Every fighter carries a **repetition code**, drawn as a row of lights over
their head with its state as a label: `|000>` standing, `|+++>` crouching. The
font has no ⟩, so kets are written with ASCII, as in the other games.

- **Distance:** a distance-d code corrects t = (d − 1) / 2 errors per cycle.
  TRIO has d = 3 (t = 1) and QUINT has d = 5 (t = 2).
- **Correction cycle:** each fighter's code is corrected on a fixed cycle,
  shown as a ring that fills up and then ticks. TRIO's cycle is 1.0 s and
  QUINT's is 1.5 s: a bigger code takes longer to measure. At each tick the
  majority vote repairs every flipped light.
- **Stance is the code basis:**
  - Standing is the **bit-flip code** (`|000>`/`|111>`). It corrects X
    errors and cannot see Z errors.
  - Crouching is the **phase-flip code** (`|+++>`/`|--->`). It corrects Z
    errors and cannot see X errors.
  - Switching between them is a **transversal H** on every qubit, which maps
    one code exactly onto the other, and maps any X errors already on it to
    Z errors. In the game the switch takes 8 frames, and a hit during them is
    a logical error. That part is a game rule, not physics (a transversal H
    is instantaneous): it makes a switch a commitment, so you can't simply
    mirror the attacker.
- **What each attack deals:**
  - Standing attacks and jump-ins deal **X** errors.
  - Low (crouching) attacks deal **Z** errors.
  - Throws deal **Y = XZ** errors. One half of a Y always gets past either
    code, so a throw is always a logical error. That is exact, and it is the
    classic answer to a player who turtles in one stance.
- **Resolving a hit:**
  - If the hit's error is one your current code corrects, it flips one
    light and does **chip** damage.
  - If it is the second correctable error within one cycle on TRIO, or the
    third on QUINT, the next majority vote is certain to fail. The **logical
    error** lands immediately: big damage, and all the lights reset (the
    code is re-encoded).
  - If your code can't detect the error at all (the wrong stance, a hit
    mid-H, or a throw), it is a logical error at once.
- **Health and fidelity:** the health bar stands for the logical qubit's
  fidelity. A logical error takes a big chunk. Chip damage stands for
  correction not being free: every cycle that has to repair something costs
  a little fidelity.

Starting numbers, to be tuned in playtests:
- Health: 100.
- Chip: 3 for a light hit, 5 for a heavy or a special.
- Logical error: 22, plus 6 if a heavy caused it and 8 if a special did.
- Light hitstun: about 14 frames, so A → A combos.

Rounds are best of 3 and last 60 s each. On timeout, more health wins, and
equal health is a draw round.

## 3. The fighters

The normal moves have the same layout for both fighters, with different
frame data:

| | Standing (X) | Crouching (Z) | Air (X, an overhead) |
|---|---|---|---|
| A | jab | low jab | air jab |
| B | heavy, knockback | sweep, knockdown | heavy jump-in |

A standing heavy and a sweep are **telegraphed**: from neutral they start up in
20 frames (the last 12 show a blinking white star on the striking hand or foot,
and the wind-up pose is drawn far back), long enough for a defender to see them
and switch to the matching stance (an 8-frame switch). Cancelled into from a
chain (jab, jab, heavy) they keep a fast startup (8 and 9 frames), so a combo
still lands. The short 1.0 s cycle repairs isolated hits, so only a real combo
or a wrong-stance hit breaks a code.

**TRIO** is fast, with a distance-3 code (corrects 1 per 1.0 s cycle), a quick
walk and a high jump. It's lean, and wears a visor.
- **Standing X, PHOTON:** a projectile dealing an X error. Slow to start.
- **Crouching X, PHASE SLIDE:** a low slide forwards, dealing a Z error. It
  passes under photons.
- **Air X, DIVE:** a steep diving kick, dealing an X error. It beats a
  crouching rival: the mix-up tool.

**QUINT** is heavy, with a distance-5 code (corrects 2 per 1.5 s cycle) and a
slow walk. It's broad, with armour plates.
- **Standing X, SYNDROME GRAB:** a lunging command throw, dealing a Y error,
  so always a logical error. Long range, but slow and punishable on a miss.
- **Crouching X, RE-ENCODE:** wipes all your flipped lights at once (an early
  correction cycle), then goes on a 4 s cooldown. The answer to TRIO's chains.
- **Air X, COLLAPSE:** a body slam straight down. A direct hit is an X error,
  and the landing shockwave deals a Z error to anyone near the ground. Two
  error types at once make it hard to defend.

**The matchup:** TRIO only breaks QUINT's code with a 3-hit chain inside one
cycle. QUINT breaks TRIO's with 2 hits, but is slower to land them. TRIO wins
by speed and mix-ups, QUINT by a few big reads.

Both players pick freely, and mirror matches are allowed. Body colours follow
the cabinet (P1 blue, P2 red); the fighters differ by silhouette.

## 4. Flow and screens

1. **Title:** the BRAWL-KET logo. A or Start begins. After a few seconds
   untouched, two bots fight as an attract demo.
2. **Character select:** each player picks TRIO or QUINT with the stick and
   confirms with A. B goes back.
3. **Round intro:** "ROUND 1", then "FIGHT!".
4. **Round:** ends on a KO or when the clock runs out, with a short
   slow-down on the KO.
5. **Match result:** after the best of 3, A rematches and B returns to the
   title.

Cabinet conventions, from AGENTS.md:
- **Pause:** Start pauses, with RESUME and QUIT TO TITLE. The title then
  waits for the buttons to be released.
- **Quit:** Start + Select quits.
- **Idle:** 60 s without input returns to the title.
- **Buttons:** A confirms and B goes back in menus.
- **Loader:** passes `--fullscreen --no-keyboard`. P1's keyboard dev keys
  avoid the pad's letters `l x r b y a`.

## 5. Look and sound

- **Fighters:** a skeleton (hip, torso, head, two arms and two legs in two
  segments) drawn as thick capsules with an ink outline. The back limbs are a
  darker shade, with a highlight and an accent-coloured visor or plates.
  Fighters stand about 130 px tall. Each move has 2 to 4 keyframe poses,
  interpolated per frame.
- **Stage:** a quantum lab with chip racks and blinking qubit status lights
  on a tiled wall, and a chip-tile floor.
- **HUD:** health bars and names along the top, the round pips and the
  timer. Each fighter has its code lights, kept up with them, plus the
  cycle ring.
- **Juice:**
  - hit sparks, and an `X!`, `Z!` or `Y!` pop-up in the gate colour;
  - **LOGICAL ERROR!** in big letters, with a screen shake;
  - hitstop (a few frozen frames on impact);
  - the KO slow-down.
- **Sound:** synthesised chiptune: hits, the correction tick, a logical-error
  sting, and the round and KO calls as jingles, plus a fight loop.

## 6. Architecture

A new top-level `brawl-ket/` directory, in the shape of the sibling games: a
uv project, `src/brawl_ket/`, `tests/`, a `README.md`, and an executable,
LF-only `deploy_batocera.sh`.

| Module | Responsibility |
|---|---|
| `moves.py` | Pure data: every move's startup, active and recovery frames; its hitbox; error type; damage, chip, hitstun and knockback; what it cancels into; its pose keyframes. Tuning means editing this table. |
| `qec.py` | Pure: the repetition code. Its distance, basis and lights; errors landing; the cycle; the majority vote; logical errors. The physics lives here, isolated and exactly tested. |
| `fighter.py` | Pure: one fighter's state machine (idle, walk, crouch, mid-H, jump, attack phases, hitstun, knockdown) and movement. It owns a `qec.Code`. |
| `fight.py` | Pure: a round at a fixed 60 Hz. Two fighters, projectiles, hitbox-against-hurtbox checks, hit resolution, the timer, KO. Emits events. |
| `match.py` | The flow: title, character select, rounds, match result, pause, idle, attract. Pure, like Gate Drop's. |
| `poses.py` | Pure: the skeleton and keyframe interpolation, from a pose to joint positions. |
| `bot.py` | A simple bot that reads stances and does chains, for the attract demo and the tests. |
| `render.py`, `audio.py`, `input.py`, `config.py`, `display.py`, `fonts.py`, `input_test.py`, `main.py`, `game.py` | The sibling games' patterns. `game.py` steps the simulation in fixed 1/60 s ticks and renders once per frame. |

## 7. Testing

- **`qec.py`, exactly:**
  - On d = 3, one correctable error is repaired at the tick, and two within a
    cycle are a logical error. On d = 5 it takes three.
  - An error of the type the basis can't see is a logical error at once, and
    so is a Y in either basis.
  - A transversal H swaps the basis and maps X errors to Z errors.
  - The cycle resets the lights.
- **Frame data:**
  - every move has positive startup, active and recovery frames;
  - every chain link's next hit starts inside the previous hit's hitstun;
  - the throw only connects at close range;
  - specials respect their cooldowns.
- **`fight.py`:** hits resolve by stance as the rules say, hitstop and
  knockback apply, projectiles hit and expire, and KO and the timeout end the
  round. The same inputs always give the same fight.
- **`match.py`:** select, rounds, best of 3, rematch, pause, idle.
- **Bots:** a bot-against-bot match always finishes, at every pairing of
  fighters.
- **Render:** smoke tests through every screen and move, a snapshot tool
  (PNGs of every pose and screen), and a benchmark on the Pi.

## Build order

1. `qec.py`, `moves.py` (TRIO only), `fighter.py` and `fight.py`, with their
   tests.
2. `poses.py`, and the puppet renderer, checked against snapshots.
3. TRIO complete and playable in a mirror match; the first playtest.
4. QUINT.
5. Flow and screens, sound, the attract demo, deploying.
6. Tuning the feel. This is the long pole, driven by playtests.

## Out of scope for v1

- A CPU mode or an arcade ladder: a boss fighter was pitched.
- More fighters. The design leaves room for a third and a fourth: other
  codes, e.g. Shor, or the surface code, whose distance could grow.
- A super meter, and blocking.
