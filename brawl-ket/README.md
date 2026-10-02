# Brawl-Ket

A one-on-one fighting game for the ARQADE cabinet (Batocera, `pygame`
system), in the style of a small Street Fighter: health bars, light and heavy
attacks, chains and specials. The twist is quantum error correction, and it
is exact: each fighter is a logical qubit protected by a repetition code, and
the oldest mind game in fighting games, high or low, is the choice between a
bit-flip and a phase-flip code. The name is a pun on bra-ket notation and
tournament brackets. Design:
`../docs/superpowers/specs/2026-10-01-brawl-ket-design.md`.

**Status:**
- **The game:** two fighters (TRIO and QUINT), versus only, best of 3
  rounds of 60 s.
- **Screens:** chunky GBA-style puppets at 640x360 (x3 on the cabinet), the
  title with a bot demo, character select, round calls and pause.
- **Extras:** chiptune (a title and a fight loop), `--input-test`, a
  snapshot tool and a Batocera deploy script.

## The rules: a fighter is a code

The lights over each fighter's head are its code, with the code's state
beside them (`|000>` standing, `|+++>` crouching).

- **Stance is the code basis.** Standing is the bit-flip code: it corrects X
  errors and can't see Z. Crouching is the phase-flip code: it corrects Z and
  can't see X. Switching between them is a transversal H, which takes 8 frames
  (a game rule; a hit during it is a logical error).
- **Attacks deal errors.** Standing attacks and jump-ins deal X, low attacks
  Z, throws Y = XZ (half of a Y always gets past either code, so a throw is
  always a logical error).
- **A hit the code can correct** flips one light and does a little chip
  damage. The ring beside the lights is the correction cycle: when it ticks,
  the majority vote repairs every flipped light.
- **A logical error** costs a big chunk of health and resets the lights. It
  happens when a hit comes from the wrong stance, or when one more hit
  within a cycle would outvote the code: the second on TRIO (d = 3, t = 1),
  the third on QUINT (d = 5, t = 2). With t lights down, the tag shows the
  danger state (the other lights pulse, a "!" by the ket).

## The fighters

| | TRIO | QUINT |
|---|---|---|
| Code | `|000>`, d = 3, corrects 1 per 1.0 s | `|00000>`, d = 5, corrects 2 per 1.5 s |
| Build | lean and fast, high jump | heavy and slow, long reach |
| X (standing) | PHOTON: a projectile, an X error (2.5 s cooldown) | SYNDROME GRAB: a lunging command throw, a Y error |
| Down + X | PHASE SLIDE: a low slide, a Z error, under photons | RE-ENCODE: wipes every flipped light (4 s cooldown) |
| Air X | DIVE: a steep kick, an X error | COLLAPSE: a body slam (X), whose landing shockwave deals Z |

Both share the normals: A is a jab (standing, crouching, in the air), B a
heavy, a sweep (knockdown) or a jump-in, and B up close while pushing towards
the rival is a throw. A chains A, A, B.

## Controls

| Action | Cabinet | P1 keyboard | P2 keyboard |
|---|---|---|---|
| Walk / jump / crouch | stick | E S D F | arrows |
| Light (and confirm in menus) | A | Q | . |
| Heavy (and back in menus) | B | W | , |
| Special | X | T | / |
| Start / pause (resume or quit to the title) | Start | 1 | 2 |
| Quit | Start + Select, or hold Select 2 s on the title | Esc | Esc |

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
| `qec.py` | The repetition code: stance, flipped lights, the cycle, logical errors. Pure, exact. |
| `moves.py` | Frame data: `Move`, `Character`, TRIO and QUINT. |
| `fighter.py`, `fight.py` | One fighter's state machine; a round at a fixed 60 Hz (hits, projectiles, shockwaves, the timer). Pure. |
| `match.py` | Title, select, rounds, the result, pause, idle and the attract demo. Pure. |
| `poses.py`, `render.py` | The skeleton and keyframe poses; the puppets, stage, HUD, effects and screens. |
| `bot.py` | The CPU for the attract demo and the tests. |
| `audio.py` | Chiptune effects and music, adapted from Planck Time's. |
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
