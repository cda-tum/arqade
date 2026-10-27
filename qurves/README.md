# Qurves

Light cycles in superposition for 2 or 4 players, for the ARQADE cabinet
(Batocera, `pygame` system). Split your bike into mirrored copies: you only
lose a round when every copy has crashed. Design: `../docs/superpowers/specs/2026-10-01-qurves-design.md`.

**Status:** full game (2 or 4 players, first to 3 rounds), `--input-test`,
and a Batocera deploy script. Button numbers follow the ones confirmed on the
cabinet. Axis 0 being the horizontal stick axis still needs an `--input-test`
check.

## How to play

The title is a short menu: the player count (push the stick left or right
to pick 2 or 4) and QUIT, which goes straight back to the cabinet's game list.
Start always starts a match, whichever row is picked.

Every match started from the title opens on a HOW TO PLAY card: the goal in
three lines, a looping demo (the real rules on a small arena: P1 takes an H,
splits, loses one copy to P2's trail and still wins) and the two pads as
drawn, with who steers with what in the chosen player count. Any button
dismisses it after a 0.3 s guard (the stick doesn't), and the press that
dismissed it doesn't steer. A rematch from the result screen skips it.

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

| Action | Pad | Keyboard |
|---|---|---|
| Steer, 2 players | either pad's stick or d-pad, or its X Y B A buttons | P1 W A S D or G C V B, P2 arrows or I J K L |
| Steer, 4 players | left stick: P1, left buttons: P3, right stick: P2, right buttons: P4 | P1 W A S D, P3 G C V B, P2 arrows, P4 I J K L |
| Title menu | stick up or down picks a row, A picks it, Start always starts | W S or arrows, B or L, Space or Enter |
| Pick 2 or 4 players | stick left or right on the PLAYERS row | A D or left right |
| Dismiss HOW TO PLAY | any button | any key |
| Back (result screen) | B | V or K |
| Rematch (result screen) | A or Start | B, L, Space or Enter |
| Pause (resume or quit to the title) | Start | Space or Enter |
| Quit | QUIT on the title, Start + Select, or hold Select 2 s on the title | Space + L-Shift or Enter + R-Shift |

The keys are the layout shared by all the games (`../common`): each side of
the keyboard is a pad, with the pad's 2x3 buttons on F G H / C V B and
U I O / J K L. On-screen hints name the keys or the pad buttons, whichever
each side last used. There is no quit key (Esc leaves fullscreen in a
browser). On the cabinet the loader passes `--no-keyboard`.

## Sound

Light-cycle synth effects, built at start-up in `sound.py` with no asset
files and no numpy. It's a small subtractive synth in pure Python:
band-limited sawtooth or raw pulse oscillators in detuned unison, a square
sub, noise, a resonant low-pass filter whose cutoff sweeps, a bit crusher,
and tanh saturation on the output. Everything is synthesized at 22050 Hz and
resampled to the mixer's rate. That takes about 0.1 s on a desktop.

| Sound | Plays on | Design |
|---|---|---|
| `beep` | countdown 3-2-1, pause | plucked E stab, 3-saw unison plus a sub, the resonant filter chirping shut |
| `go` | GO | B power-chord stab whose filter blooms open, over a resonant bass hum |
| `blip` | menu moves | tiny 25 % pulse tick |
| `confirm` | start, HOW TO PLAY dismissed | two-note octave stab |
| `pickup` | any gate | bright four-note arpeggio zap up to E7 |
| `split` | H | forking arpeggios: one climbs while its mirror falls |
| `teleport` | X | pulse laser rising through a resonant filter, with one echo |
| `shield` | Z | A power chord charging up through a high-resonance sweep |
| `collapse` | measurement, decoherence | wide, beating unison sliding down, lightly crushed |
| `measure` | measuring a rival | glitchy, sample-held pulse zap downwards |
| `crash` | a copy crashes (derez) | noise-and-thump impact, then a saw diving to 30 Hz while the crusher eats it (8 to 4 bits, 1/8 rate), plus scattering pulse shards |
| `round`, `match` | round won or draw, match won | climbing E-minor arpeggios over a resonant hum (the match one is longer) |

Each effect's level in `EFFECTS` is calibrated so that its A-weighted loudness
(RMS of the loudest 50 ms) matches the sine beep it replaced, so the balance
between sounds didn't change. Nothing peaks above `PEAK` (55 % of full scale).

There is deliberately no engine hum. A loop under every round would drone
on a public cabinet. pygame can't bend a playing sound's pitch either, so a
hum that follows the bike would mean several pre-rendered loops cross-faded
per bike. The resonant hum lives in the GO, round and match stabs instead.

Without a mixer, every sound is a silent no-op. The attract capture
(`batocera/attract/capture.py`) logs these effects like any others.

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

In the browser (pygbag's test server on http://localhost:8000), from the
repo root:

```bash
uv run --project tools tools/build_web.py --serve qurves
```

In the browser, quitting (Start + Select, or QUIT on the title) goes back to
the title and tells the page around the game (`arqade:quit`). Pads use the
cabinet's button numbers by default; `--pad-layout xbox` reads an Xbox-style
pad on a PC instead, and browser gamepads use the browser's standard layout.

## Layout

| Module | Role |
|---|---|
| `rules.py` | The simulation: grid, bikes, splits, collisions, collapse. Pure, fully tested. |
| `match.py` | Title menu, HOW TO PLAY, countdown, rounds, results. Pure, tested. |
| `tutorial.py` | The HOW TO PLAY card: its scripted demo (pure, tested) and drawing. |
| `render.py`, `fx.py` | The neon look: a persistent trail board, ghost layers, glow sprites, particles. |
| `input.py`, `sound.py` | Pads and dev keyboard; the synthesized sound effects (see Sound). |
| `config.py` | Every tuning number, colour and button mapping. |

If the cabinet drops frames, set `GLOW` and/or `SHOW_SCANLINES` to `False` in `config.py`.

## Deploying to the cabinet

```bash
./deploy_batocera.sh                    # or ./deploy_batocera.sh root@10.42.0.100
```

The first time, also add the `batocera/gamelist.xml` entry and the icon on the
cabinet, with EmulationStation stopped, then restart it (see `../AGENTS.md`).
Later deploys only replace the code.
