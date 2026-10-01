# Qurves

Light cycles in superposition for 2 or 4 players, for the ARQADE cabinet
(Batocera, `pygame` system). Split your bike into mirrored copies: you only
lose a round when every copy has crashed. Design: `../docs/superpowers/specs/2026-10-01-qurves-design.md`.

**Status:** full game (2 or 4 players, first to 3 rounds), `--input-test`,
and a Batocera deploy script. Button numbers follow the ones confirmed on the
cabinet. Axis 0 being the horizontal stick axis still needs an `--input-test`
check.

## How to play

For 2 or 4 players: push the stick left or right on the title screen to pick.

- **Steer** with the stick, or with the face buttons X, Y, B and A, which sit
  like W, A, S and D. You can't reverse into yourself.
- **H gate:** splits the copy that drove over it into two. One copy follows
  your input; the other follows it mirrored across the line it split on.
  Every H adds 3 s to your superposition bar (up to 9 s, at most 8 copies).
- **X gate:** jumps that copy to the mirror-image spot on the other side of
  the arena, and shields it for 3 s.
- **Z gate:** shields that copy for 2 s. A shielded copy (blinking white)
  drives through trails and can't be measured. Walls still stop it.
- **Your copies** are separate worlds: each passes through the others'
  trails, but not its own.
- **A copy is eliminated** in one of three ways:
  - **Crash:** it hits a wall, solid trail, or its own history.
  - **Measurement:** an opponent drives through its ghost trail. Every copy
    that came after that piece of trail never happened.
  - **Decoherence:** when the bar runs dry, one copy survives at random.
- **Eliminated copies' trails dissolve**; trail shared by all survivors
  turns solid. You only lose a round when every copy has crashed.
- Speed rises every 10 s. Last one standing takes the round; first to 3 wins.

| Action | Cabinet | Keyboard (dev only) |
|---|---|---|
| Steer, 2 players | either pad's stick, or its X Y B A buttons | P1 W A S D or T F G H, P2 I J K L or arrows |
| Steer, 4 players | left stick: P1, left buttons: P3, right stick: P2, right buttons: P4 | the same keys, one set per player |
| Confirm (menus) | A or Start | Enter, 1, 2 |
| Back (result screen) | B | Backspace |
| Pause (resume or quit to the title) | Start | P |
| Pick 2 or 4 players | stick left or right on the title | A or D, J or L |
| Quit | Start + Select, or hold Select 2 s on the title | Esc |

The keyboard is a dev fallback only. On the cabinet the loader passes
`--no-keyboard`.

## Setup (dev machine)

Requires [uv](https://docs.astral.sh/uv/).

```bash
cd qurves
uv sync
uv run python -m qurves          # windowed
uv run python -m qurves --fps    # with the FPS overlay
uv run pytest
uv run python tools/snapshot.py /tmp/qurves-snaps   # render a scripted match to PNGs
```

## Layout

| Module | Role |
|---|---|
| `rules.py` | The simulation: grid, bikes, splits, collisions, collapse. Pure, fully tested. |
| `match.py` | Title, countdown, rounds, results. Pure, tested. |
| `render.py`, `fx.py` | The neon look: a persistent trail board, ghost layers, glow sprites, particles. |
| `input.py`, `sound.py` | Pads and dev keyboard; procedural sound effects. |
| `config.py` | Every tuning number, colour and button mapping. |

If the cabinet drops frames, set `GLOW` and/or `SHOW_SCANLINES` to `False` in `config.py`.

## Deploying to the cabinet

```bash
./deploy_batocera.sh                    # or ./deploy_batocera.sh root@10.42.0.100
```

The first time, also add the `batocera/gamelist.xml` entry and the icon on the
cabinet, with EmulationStation stopped, then restart it (see `../AGENTS.md`).
Later deploys only replace the code.
