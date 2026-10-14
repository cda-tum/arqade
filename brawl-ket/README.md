# Brawl-Ket

A one-on-one fighting game for the ARQADE cabinet (Batocera, `pygame`
system), in the style of a small Street Fighter: health bars, light and heavy
attacks, chains and specials. The quantum idea is one visible rule: each
fighter is in a measurement basis, shown by their body colour, and only an
attack of the matching colour hurts them. The name is a pun on bra-ket
notation and tournament brackets. Design:
`../docs/superpowers/specs/2026-10-02-brawl-ket-basis-design.md` (v3; it
replaces the repetition-code v1 and the Shor-code v2, which playtests found
too hard to read).

**Status:**
- **The game:** three fighters (ROBERT, BOHR and PHOEBE), versus only, best of 3
  rounds of 60 s.
- **Screens:** chunky GBA-style puppets (and PHOEBE, a scientist in a long coat) at 640x360 (x3 on the cabinet), the
  title (PLAY / QUIT) with a bot demo, character select, stage select, a HOW TO PLAY card,
  round calls and pause.
- **Stages:** five backdrops, picked on CHOOSE YOUR STAGE (RANDOM by default, which rolls one
  for each match; the title demo always rolls), kept for all its rounds. Visual only:
  - SERVER RACK: the lab with its qubit racks;
  - SUPERCONDUCTOR: a cryostat room with a superconducting quantum computer's gold
    "chandelier";
  - OPTICAL LAB: a white laser lab;
  - QUANTUM SPACE: the open-plan TUM Quantum Space office, with the MQT logo on its glass wall;
  - QUANTUM WEEK: Toronto at dusk, with the CN Tower and the Metro Toronto Convention Centre,
    home of IEEE Quantum Week 2026.
- **Extras:** chiptune sound effects (no music: on the cabinet only
  Overquqed has music), `--input-test`, a snapshot tool and a Batocera
  deploy script.

## The rules: colour must match

Every fighter is in one of two bases, shown by the colour of the whole body:

| Basis | States | Colour | Hurt by |
|---|---|---|---|
| Z basis | \|0>, \|1> | green | X (green attacks), which flips \|0> and \|1> |
| X basis | \|+>, \|-> | purple | Z (purple attacks), which flips \|+> and \|-> |

This is exact: X leaves \|+> and \|-> unchanged (up to a phase), and Z leaves
\|0> and \|1> unchanged. An attack is drawn in the colour of the basis it
changes, so the rule a player reads is: **colour must match to hurt.**

- **A and every special (X)** are in **your own** colour, **B** in the **other**
  one; a move's colour is fixed when it starts. Against a rival of your colour A
  and X hurt; against the other colour B does. In an A then B chain exactly one
  half matches.
- **Throws** are Y = iXZ, which flips both bases: they hurt either colour.
- **A wrong-colour hit** does no damage (the state is unchanged), but the
  defender is still pushed back and held in block-stun, so the string goes on
  and its matching half can land (a game rule).
- **Y switches basis:** an H on yourself, at once, in any state, even mid-attack,
  in hitstun or knocked down. For 10 frames after it you can't start an attack.
  Switching mid-string makes the rest of the string bounce.
- **Heights:** standing normals are HIGH (a crouch ducks them), crouching
  normals LOW (a jump clears them), air normals and throws MID.
- **Damage:** light 4, heavy 8, special 10, throw 10, MEASURE 12, CHARGE NOISE
  3 a shock, LASER 8. Health: ROBERT 100, BOHR 115, PHOEBE 95. Lights stun briefly enough that mashing
  can't loop, and getting up from a knockdown is invulnerable for 8 frames.

On screen: P1 has a blue ring under their feet and P2 a red one; each health
bar has a basis badge (`0/1` green, `+/-` purple) and A / B chips in the colours
that player's buttons hit right now; an attack's whole arm or leg is drawn in its
colour from the wind-up on, so you see before contact whether it will match. A wrong-colour hit pings, a switch flashes white with an `H`.

## The flow

Title (PLAY / QUIT) -> character select -> CHOOSE YOUR STAGE -> **HOW TO PLAY** ->
ROUND 1 / FIGHT! -> rounds -> the result (A: rematch, B: title).

- **The title** is a menu: the stick picks PLAY or QUIT, A takes it. QUIT ends
  the game at once, back to EmulationStation (or the launcher), the same way out
  as Start + Select. **Start always plays**, whichever row is picked, and B does
  nothing. Left alone, the title runs a bot demo and a COLOUR MUST MATCH card;
  the demo puts the cursor back on PLAY, so whoever stops it with A never quits.
- **HOW TO PLAY** shows before every match started from CHOOSE YOUR STAGE, in the
  room that match is fought in (RANDOM is rolled as the stage is picked). A rematch
  goes straight to ROUND 1 as before, with no stage screen and no card. The card
  shows the goal in two lines, the controls (the stick and the 2x3 buttons as
  printed on the cabinet, `L X R` over `Y B A`, with A, B, X and Y lit) and a
  looping 4.7 s scene, a real fight played from a script (`tutorial.py`): a green
  jab from ROBERT hurts green BOHR, BOHR switches (Y) to purple, the same jab
  bounces, B hurts. Any button on either pad (L, R and Select too, but not the
  stick) goes on, once the card has been up 0.3 s. It plays the confirm sound,
  and because presses are edges it does nothing in the round. Start + Select still
  quits, and the 60 s idle timeout still returns to the title.

## The fighters

| | ROBERT | BOHR | PHOEBE |
|---|---|---|---|
| Build | lean and fast, high jump | heavy and slow, long reach, 115 health | tall and tricky, the longest pokes, 95 health; controls angles, not the ground |
| X (standing) | PHOTON: a projectile; it keeps the colour it was fired in (2.5 s cooldown) | MEASURE: a dashing command throw (Y, hurts either colour) that collapses the rival into BOHR's basis | LIGHT PILLAR: a thick laser beam straight up from her raised palms: an anti-air that only ever catches someone in the air, and knocks them down (1.5 s cooldown) |
| Down + X | PHASE SLIDE: a low slide; it slides under photons | CHARGE NOISE: for 1 s, electric shocks all round BOHR (~60 px, every 12 frames, can't be ducked or jumped; 3 s cooldown) | TUNNEL: she dissolves and re-forms 50 px past the rival, facing them; a dotted line on the floor shows where. Untouchable only while gone, open while she re-forms (1.8 s cooldown) |
| Air X | HADAMARD DIVE: a steep dive; when it lands, you switch basis | COLLAPSE: a drifting body slam (MID) whose landing shockwave (LOW) hits too | LASER: she hangs in the air, aims (a dotted line) and fires down and forward at 45 degrees, once per jump |

Her weakness: she has no ground projectile and the least health, so walking straight
in on the ground (BOHR's game) is how you beat her. Design:
`../docs/superpowers/specs/2026-10-09-brawl-ket-phoebe-design.md`.

All three share the normals: A is a jab (standing, crouching, in the air), B a
heavy, a sweep (knockdown) or a jump-in, and B up close while pushing towards
the rival is a throw. A chains A, A, B.

## Controls

| Action | Cabinet | P1 keyboard | P2 keyboard |
|---|---|---|---|
| Walk / jump / crouch | stick | E S D F | arrows |
| Light (and confirm in menus) | A | Q | . |
| Heavy (and back in menus) | B | W | , |
| Special | X | T | / |
| Switch basis (H) | Y | G | ; |
| Start / pause (resume or quit to the title) | Start | 1 | 2 |
| Quit | QUIT on the title, Start + Select, or hold Select 2 s on the title | Esc | Esc |

P1's dev keys avoid the pad's own letters (l, x, r, b, y, a; see
`../AGENTS.md`). The keyboard is a dev fallback only: on the cabinet the
loader passes `--no-keyboard`.

## Setup (dev machine)

Requires [uv](https://docs.astral.sh/uv/).

```bash
cd brawl-ket
uv sync
uv run python -m brawl_ket          # windowed
uv run python -m brawl_ket --fps    # with the FPS overlay
uv run pytest
uv run python tools/snapshot.py /tmp/brawl-snaps   # poses, moves, fights and screens to PNGs
uv run python tools/benchmark.py                    # frame cost (on the cabinet: see below)
```

## Layout

| Module | Role |
|---|---|
| `basis.py` | The two bases, which errors change which, H, and each attack's error from its colour rule. Pure, exact, tested against 2x2 matrices. |
| `moves.py` | Frame data: `Move` (colour rule, height, damage, the specials' twists), `Character`, ROBERT, BOHR and PHOEBE. |
| `fighter.py`, `fight.py` | One fighter's state machine (basis, the Y switch); a round at a fixed 60 Hz (hits or blocks by colour, the twists, projectiles, shockwaves, the timer). Pure. |
| `match.py` | Title (PLAY / QUIT), select, stage select, HOW TO PLAY, rounds, the result, pause, idle and the attract demo. Pure. |
| `tutorial.py` | The HOW TO PLAY card's scene: a real Fight played from a script, looping. Pure. |
| `stages.py` | The backdrops, each drawn once (with its blinking lights); no green or purple in a large area, so the fighters stay readable. |
| `poses.py`, `render.py` | The skeleton and keyframe poses; the basis-coloured puppets, stage, HUD and badges, effects, the rules card and the screens (HOW TO PLAY draws its scene with a second, off-screen renderer). |
| `bot.py` | The CPU for the attract demo and the tests. |
| `audio.py` | Chiptune effects, adapted from Planck Time's. No music. |
| `input.py`, `config.py` | Pads and the dev keyboard; every tuning number and button. |

## Deploying to the cabinet

```bash
./deploy_batocera.sh                    # or ./deploy_batocera.sh root@10.42.0.100
```

The first time, you also need to add the `batocera/gamelist.xml` entry and
copy `batocera/logos/brawl_ket-logo.png` and `-marquee.png` to the cabinet,
with EmulationStation stopped, and then restart it (see `../AGENTS.md`).
Later deploys only replace the code.

To time a frame on the Pi itself, copy `tools/benchmark.py` over and run it
against the deployed package:

```bash
scp tools/benchmark.py root@batocera.local:/tmp/
ssh root@batocera.local "python3 /tmp/benchmark.py /userdata/games/brawl_ket"
```
