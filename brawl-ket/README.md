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
- **The game:** two fighters (TRIO and QUINT), versus only, best of 3
  rounds of 60 s.
- **Screens:** chunky GBA-style puppets at 640x360 (x3 on the cabinet), the
  title with a bot demo, character select, round calls and pause.
- **Extras:** chiptune (a title and a fight loop), `--input-test`, a
  snapshot tool and a Batocera deploy script.

## The rules: colour must match

Every fighter is in one of two bases, shown by the colour of the whole body:

| Basis | States | Colour | Hurt by |
|---|---|---|---|
| Z basis | \|0>, \|1> | green | X (green attacks), which flips \|0> and \|1> |
| X basis | \|+>, \|-> | purple | Z (purple attacks), which flips \|+> and \|-> |

This is exact: X leaves \|+> and \|-> unchanged (up to a phase), and Z leaves
\|0> and \|1> unchanged. An attack is drawn in the colour of the basis it
changes, so the rule a player reads is: **colour must match to hurt.**

- **A** is always in **your own** colour, **B** in the **other** one. Against a
  rival of your colour A hurts; against the other colour B does. In an A then B
  chain exactly one half matches.
- **Throws** are Y = iXZ, which flips both bases: they hurt either colour.
- **A wrong-colour hit** does no damage (the state is unchanged), but the
  defender is still pushed back and held in block-stun, so the string goes on
  and its matching half can land (a game rule).
- **Y switches basis:** an H on yourself, at once. For 10 frames after it you
  can't attack (you can move, crouch and be hit, judged by your new colour).
  Only when free to act: idle, walking, crouching or in the air.
- **Heights:** standing normals are HIGH (a crouch ducks them), crouching
  normals LOW (a jump clears them), air normals and throws MID.
- **Damage:** light 4, heavy 8, special 10, throw 10, MEASURE 12. Health:
  TRIO 100, QUINT 115.

On screen: P1 has a blue ring under their feet and P2 a red one; each health
bar has a basis badge (`0/1` green, `+/-` purple); an attack's hand or foot
glows in its colour from the wind-up on, so you see before contact whether it
will match. A wrong-colour hit pings, a switch flashes white with an `H`.

## The fighters

| | TRIO | QUINT |
|---|---|---|
| Build | lean and fast, high jump | heavy and slow, long reach, 115 health |
| X (standing) | PHOTON: a projectile, always green (2.5 s cooldown) | MEASURE: a dashing command throw (Y, hurts either colour) that collapses the rival into QUINT's basis |
| Down + X | PHASE SLIDE: a low slide, always purple; it slides under photons | HADAMARD WAVE: a short ground wave (~70 px, LOW) that switches the rival's basis, no damage (3 s cooldown) |
| Air X | HADAMARD DIVE: a steep dive in your colour; when it lands, you switch basis | COLLAPSE: a drifting body slam, green (HIGH), whose landing shockwave is purple (LOW) |

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
| Switch basis (H) | Y | G | ; |
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
| `basis.py` | The two bases, which errors change which, H, and each attack's error from its colour rule. Pure, exact, tested against 2x2 matrices. |
| `moves.py` | Frame data: `Move` (colour rule, height, damage, the specials' twists), `Character`, TRIO and QUINT. |
| `fighter.py`, `fight.py` | One fighter's state machine (basis, the Y switch); a round at a fixed 60 Hz (hits or blocks by colour, the twists, projectiles, shockwaves, the timer). Pure. |
| `match.py` | Title, select, rounds, the result, pause, idle and the attract demo. Pure. |
| `poses.py`, `render.py` | The skeleton and keyframe poses; the basis-coloured puppets, stage, HUD and badges, effects, the rules card and the screens. |
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
