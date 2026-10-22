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
- **The game:** seven fighters (ROBERT, BOHR, PHOEBE, ERWIN, DOS, M-CUTIE and ALICE & BOB, two
  played as one), versus only, best of 3 rounds of 60 s.
- **Screens:** chunky GBA-style puppets (and PHOEBE, a scientist in a long coat; ERWIN, Schrodinger's cat; DOS, a walking all-in-one computer; M-CUTIE, an android in a chandelier dress; ALICE & BOB, two kid couriers in matching hoodies) at 640x360 (x3 on the cabinet), the
  title (PLAY / QUIT) with a bot demo, a portrait-grid fighter select, stage select, a HOW TO PLAY card,
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
- **DOS is the exception.** A classical bit can't be in superposition, so he is always green: his Y doesn't switch, and MEASURE hurts him without collapsing him. His Y is COPY, then PASTE (below).
- **Heights:** standing normals are HIGH (a crouch ducks them), crouching
  normals LOW (a jump clears them), air normals and throws MID.
- **Damage:** light 4, heavy 8, special 10, throw 10, MEASURE 12, CHARGE NOISE
  3 a shock, LASER 8, POUNCE 10, BOX DROP 8, THE BOX's swipe 8, FLOPPY 9, MOUSE CABLE 6, CRT DROP 12,
  AMPLITUDE AMPLIFICATION 7 to 15 by its steps (7, 8, 10, 11, 13, 15), ION TRAP 4, SPIN 4 a hit, KEY EXCHANGE 12 (6 alone), BELL DIVE 8. Health: ROBERT 100, BOHR 115, PHOEBE 95, ERWIN 90, DOS 125, M-CUTIE 105, ALICE & BOB 100 between them. Lights stun briefly enough that mashing
  can't loop, and getting up from a knockdown is invulnerable for 8 frames.

On screen: P1 has a blue ring under their feet and P2 a red one (Bob a thinner one); each health
bar has a basis badge (`0/1` green, `+/-` purple) and A / B chips in the colours
that player's buttons hit right now; an attack's whole arm or leg is drawn in its
colour from the wind-up on, so you see before contact whether it will match. A wrong-colour hit pings, a switch flashes white with an `H`.

## The flow

Title (PLAY / QUIT) -> CHOOSE YOUR FIGHTER -> CHOOSE YOUR STAGE -> **HOW TO PLAY** ->
ROUND 1 / FIGHT! -> rounds -> the result (A: rematch, B: title).

- **CHOOSE YOUR FIGHTER** is Street Fighter style: a grid of portraits along the
  bottom (five to a row, so M-CUTIE and ALICE & BOB make the second; up and down move a row), one cursor
  per player (P1 blue, P2 red, both on one portrait if they pick the same fighter),
  blinking until that player presses A. Each player's pick stands big on their side,
  facing the middle, with what it is and its three specials. B un-readies, or goes
  back to the title.

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

| | ROBERT | BOHR | PHOEBE | ERWIN | DOS | M-CUTIE |
|---|---|---|---|---|---|---|
| Build | lean and fast, high jump | heavy and slow, long reach, 115 health | tall and tricky, the longest pokes, 95 health; controls angles, not the ground | quick and slippery, the highest jump, 90 health | slow and classical, the lowest jump, 125 health; **always green** | patient and technical, in the middle on health (105) and jump, a little slower than ROBERT |
| X (standing) | PHOTON: a projectile; it keeps the colour it was fired in (2.5 s cooldown) | MEASURE: a dashing command throw (Y, hurts either colour) that collapses the rival into BOHR's basis | LIGHT PILLAR: a thick laser beam straight up from her raised palms: an anti-air that only ever catches someone in the air, and knocks them down (1.5 s cooldown) | THE BOX: he splits into two holographic boxes, where he stood and 120 px towards the rival. Any press or new stick direction (or 1.5 s) collapses it into a random box, with a swipe; anything that touches a box measures him, 50/50: he is in that box and it lands, or in the other and it whiffs (3 s cooldown, from the collapse) | FLOPPY: a spinning disk from his drive slot, slower than PHOTON (2.5 s cooldown) | AMPLITUDE AMPLIFICATION: every X press is a step, up to 6; she stands still while she charges, and the wave fires 0.25 s after her last press (at once at 6): a microwave pulse along the floor, taller and harder with every step (20 to 60 px, MID). Hit while charging, it is lost (2 s cooldown, from the fire) |
| Down + X | PHASE SLIDE: a low slide; it slides under photons | CHARGE NOISE: for 1 s, electric shocks all round BOHR (~60 px, every 12 frames, can't be ducked or jumped; 3 s cooldown) | TUNNEL: she dissolves and re-forms 50 px past the rival, facing them; a dotted line on the floor shows where. Untouchable only while gone, open while she re-forms (1.8 s cooldown) | POUNCE: a long low leap that knocks down; MID, so a crouch doesn't save you; a long landing (2 s cooldown) | MOUSE CABLE: he flings his mouse out along the floor on its cable (LOW, so a jump clears it, about 180 px) and reels in whoever it touches, to just in front of him, hit or bounced (3 s cooldown) | ION TRAP: a trap on the floor 70 px in front of her, armed after 0.3 s; a rival on the ground who steps in is held for 0.5 s (hurt only if it is their colour), and can't be caught again for 0.3 s after. A jump clears it; two at most, gone after 10 s or when she is knocked down (1 s cooldown) |
| Air X | HADAMARD DIVE: a steep dive; when it lands, you switch basis | COLLAPSE: a drifting body slam (MID) whose landing shockwave (LOW) hits too | LASER: she hangs in the air, aims (a dotted line) and fires down and forward at 45 degrees, once per jump | BOX DROP: he lets a little box fall from the air, just in front of him (MID, his colour), once per jump | CRT DROP: a fast stomp straight down, about his case's width and then some, that knocks down; no shockwave, a long landing | SPIN: she stops falling and spins forward about 100 px, one leg out, hitting up to three times (MID), once per jump; then she drops and lands into a short recovery |
| Y | switches your colour | switches your colour | switches your colour | switches his colour, even inside THE BOX | COPY: a CTRL+C frame catches a rival's shot (a PHOTON, a LASER, a box from BOX DROP, M-CUTIE's wave at its size) or BOHR's crackling CHARGE NOISE into his clipboard (the icon by his chips); then PASTE fires the shot straight ahead in the colour it was fired in, or crackles with the noise himself, in its colour. Only when he is free to act | switches her colour |

Her weakness: she has no ground projectile and the least health, so walking straight
in on the ground (BOHR's game) is how you beat her. Design:
`../docs/superpowers/specs/2026-10-09-brawl-ket-phoebe-design.md`.

ERWIN's weakness is the least health, and THE BOX is a gamble; DOS's is that his rival only ever needs green attacks against him. Design: ../docs/superpowers/specs/2026-10-21-brawl-ket-erwin-dos-design.md.

**ALICE & BOB** are two small fighters played as one, like the Ice Climbers: the player controls
Alice, and Bob, 40 px behind her, does what she did 0.2 s later (every attack comes twice). They
share one health bar of 100 and are always in opposite colours, a singlet: Alice green, Bob
purple, or the other way round (Y, MEASURE, anything that changes one flips both), so one attack
colour never hurts them both. They are a little faster and lighter than ROBERT. Bob has no push box: the rival can walk between
them. A knockdown on Bob decoheres him: he fades, and is gone for 3 s while Alice fights alone.

| | ALICE & BOB |
|---|---|
| X | KEY EXCHANGE: Alice tosses a photon back to Bob along a short arc, and he fires it forward as one strong shot (12, ducked or jumped as a PHOTON; 2.5 s cooldown). A rival's body, attack or shot touching the toss in flight takes it out, and DOS's COPY catches it. While Bob is gone, Alice fires a small photon herself (6) |
| Down + X | ANCHOR, then TELEPORT: the first press plants Bob (a pin over his head): he stops following but still echoes her attacks, facing the rival, so they can split up. The second swaps them at once, a flash at both ends, and he follows again: with the rival between them it crosses them up, otherwise it is a quick step back (2 s cooldown, from the swap; not while Bob is gone, and a decohered Bob comes back unplanted) |
| Air X | BELL DIVE: a steep diving kick (MID, 8), once per jump; Bob's echo dives a beat later |
| Y | switches the pair's colour |

Design: `../docs/superpowers/specs/2026-10-21-brawl-ket-alice-bob-design.md`.

M-CUTIE traps the floor so you have to jump, then catches you in the air with SPIN or a big
wave; her weakness is that setting up takes time, so rushing her before she is ready wins.
Her wave cancels any rival shot it meets. Design:
`../docs/superpowers/specs/2026-10-21-brawl-ket-m-cutie-design.md`.

All seven share the normals (ALICE & BOB's fitted to their size): A is a jab (standing, crouching, in the air), B a
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
uv run python tools/balance.py                      # bot-against-bot win rates for every pairing
```

## Layout

| Module | Role |
|---|---|
| `basis.py` | The two bases, which errors change which, H, and each attack's error from its colour rule. Pure, exact, tested against 2x2 matrices. |
| `moves.py` | Frame data: `Move` (colour rule, height, damage, the specials' twists), `Character`, ROBERT, BOHR, PHOEBE, ERWIN, DOS, M-CUTIE (her six waves, one per step) and ALICE & BOB (with BOB, the second body). |
| `fighter.py`, `fight.py` | One fighter's state machine (basis, the Y switch); a round at a fixed 60 Hz (hits or blocks by colour, the twists, projectiles, shockwaves, the timer). THE BOX's 50/50s come from the fight's own seeded random.Random: the same seed and inputs give the same round. M-CUTIE's charge is the fighter's "charging" state, her traps the fight's `Trap`s. ALICE & BOB's Bob is a second body (`Fight.echoes`, `Fight.bodies`); KEY EXCHANGE's photon in flight is a `Toss`. Pure. |
| `echo.py` | Bob, ALICE & BOB's second body: a Fighter that replays Alice's inputs 12 frames later and shares her health and basis; his walk back behind her, decoherence and return. Pure. |
| `match.py` | Title (PLAY / QUIT), select, stage select, HOW TO PLAY, rounds, the result, pause, idle and the attract demo. Pure. |
| `tutorial.py` | The HOW TO PLAY card's scene: a real Fight played from a script, looping. Pure. |
| `stages.py` | The backdrops, each drawn once (with its blinking lights); no green or purple in a large area, so the fighters stay readable. |
| `poses.py`, `render.py` | The skeleton and keyframe poses; the basis-coloured puppets, stage, HUD and badges, effects, the rules card and the screens (HOW TO PLAY draws its scene with a second, off-screen renderer). |
| `ink.py`, `erwin.py`, `dos.py` | The drawing primitives; ERWIN's cat and THE BOX; DOS's case, screen faces, floppy and clipboard icon (both checked pixel for pixel against their approved look scripts, and cached so the cabinet keeps its frame budget). |
| `cutie.py` | M-CUTIE's android, her wave, her trap, SPIN and the charge's halo (checked pixel for pixel against her approved look script; her head, wave and trap baked once into cached layers). |
| `kids.py` | ALICE & BOB's couriers, KEY EXCHANGE's toss and big photon, TELEPORT's flash, BELL DIVE's streaks, a decohered Bob and his HUD icon (checked pixel for pixel against their approved look script). |
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
