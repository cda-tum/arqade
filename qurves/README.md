# Qurves

Two-player light cycles in superposition, for the ARQADE cabinet (Batocera,
`pygame` system). Split your bike into two mirrored copies: you only lose a
round when every copy has crashed. Design: `../docs/superpowers/specs/2026-10-01-qurves-design.md`.

**Status:** full game (2-player versus, first to 3 rounds), `--input-test`,
and a Batocera deploy script. Button numbers follow the ones confirmed on the
cabinet. Axis 0 being the horizontal stick axis still needs an `--input-test`
check.

## How to play

- Steer with the stick. You can't reverse into yourself.
- Drive over **H** gates to charge your `|ψ>` meter. Each one adds half.
- With at least half a meter, press **A** to **split**. Your bike forks into
  two copies, one each side. One copy follows the stick, and the other
  follows it mirrored across the line you split on. The meter drains while
  you're split. A full meter lasts 6 s.
- Your two copies are separate worlds and pass through each other.
- A superposition ends in one of three ways:
  - **Crash:** a copy that hits something is gone, and its trail dissolves.
    You become the other copy.
  - **Measurement:** if your opponent drives through one of your ghost trails,
    you collapse onto the copy whose trail was *not* touched.
  - **Decoherence:** when the meter runs dry, you become one copy at random.
- A branch that is eliminated never happened, so its trail dissolves. The
  surviving branch's trail becomes solid.
- Speed rises every 10 s. First to 3 rounds wins.

| Action | Cabinet | P1 keyboard | P2 keyboard |
|---|---|---|---|
| Steer | stick | W A S D | I J K L |
| Split / confirm | A | Q | U |
| Start | Start | 1 | 2 |
| Back (result screen) | B | E | O |
| Quit | Start + Select, or hold Select 2 s on the title | Esc | Esc |

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
