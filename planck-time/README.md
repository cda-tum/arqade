# Planck Time

A quantum microgame party in the style of WarioWare, for 1 or 2 players, for
the ARQADE cabinet (Batocera, `pygame` system). Twelve tiny games come one
after another, each about five seconds long and faster and faster. The name:
the Planck time is the shortest meaningful unit of time in physics.
Design: `../docs/superpowers/specs/2026-10-01-planck-time-design.md`.

**The design rule:** playtests showed that learning the controls is the
biggest hurdle, so every microgame uses **only the stick and A**, shows
**one verb**, is **playable by eye** without any physics knowledge, and
explains its concept in a one-line caption *afterwards*.

**Status:**
- **The game:** all 12 microgames, single player (endless, 4 lives, top-10
  initials) and versus (both players on the same microgame, side by side).
- **Screens:** GBA-style pixel art at 640x360 (x3 on the cabinet), the title
  with an attract demo, and pause.
- **Extras:** chiptune whose tempo follows the level, `--input-test`, and a
  Batocera deploy script.

## How to play

- **Title:** the stick picks 1 or 2 players, and A or Start begins. Left
  alone for 3 s, the title shows bots playing.
- **Every microgame has three beats:**
  1. **Intro** (1.5 s): the verb, and an icon of the one input it uses. The
     first time a microgame comes up, the icon is animated.
  2. **Play:** the fuse below the screen burns down. Win early and the win
     animation plays out the rest. A failure ends it at once.
  3. **Result:** NICE! or OOPS!, plus the concept caption.
- **Speed:** every 4 microgames the level goes up (SPEED UP!).
  - The play time is `max(2.5, 5 x 0.9^level)` s.
  - Objects move `1 + 0.15 x level` times as fast.
  - Each microgame also gets a little harder.
- **Single player:** 4 lives, and the score is the number of microgames
  cleared. Either pad plays.
- **Versus:** both players get the same microgame from the same seed, at the
  same moment. A success scores 1, and if both succeed, whoever finished
  first scores 1 more. A failure costs a life. The last player with lives
  left wins. If both go out together, the higher score wins, and equal
  scores are a draw. On the result screen, A rematches and B goes to the
  title.

| # | Verb | Input | What you do |
|---|---|---|---|
| 1 | ALIGN! | stick | Point the Bloch-sphere arrow at the star |
| 2 | CANCEL! | A | Press as the slot gate's twin passes over it |
| 3 | FIX! | stick + A | Pick the Pauli card that matches the error |
| 4 | MEASURE! | A | Press while the needle is in the top zone |
| 5 | SHIELD! | stick | Dodge the noise until time's up |
| 6 | VOTE! | stick + A | Pick the bit that disagrees with the others |
| 7 | SHORTER! | stick + A | Pick the circuit with fewer gates |
| 8 | CONNECT! | stick | Walk your qubit along couplers to its partner |
| 9 | PAIR! | stick + A | Pick one of the two particles moving in sync |
| 10 | REFRESH! | mash A | Keep the glow bar above the line |
| 11 | STEER! | stick | Turn the mirror to keep the beam on the detector |
| 12 | SORT! | stick | Slide each falling `|0>` / `|1>` into its bin |

| Action | Cabinet | P1 keyboard | P2 keyboard |
|---|---|---|---|
| Stick | stick | E S D F | arrows |
| A (and confirm in menus) | A | Q | . |
| Back (menus) | B | W | , |
| Start / pause (resume or quit to the title) | Start | 1 | 2 |
| Quit | Start + Select, or hold Select 2 s on the title | Esc | Esc |

P1's dev keys avoid the pad's own letters (l, x, r, b, y, a; see
`../AGENTS.md`). The keyboard is a dev fallback only: on the cabinet the
loader passes `--no-keyboard`. High scores are kept in
`~/.planck_time_scores.json`, outside the package, so a redeploy keeps them.

## Setup (dev machine)

Requires [uv](https://docs.astral.sh/uv/).

```bash
cd planck-time
uv sync
uv run python -m planck_time          # windowed
uv run python -m planck_time --fps    # with the FPS overlay
uv run pytest
uv run python tools/snapshot.py /tmp/planck-snaps   # every screen and microgame to PNGs
```

## Layout

| Module | Role |
|---|---|
| `microgames/` | One module per microgame, plus `base.py`, the contract. Rules are pure; `draw()` is the only pygame part. |
| `session.py` | Title, the beats, speed levels, lives, scores, versus, pause, idle, the attract demo. Pure, tested. |
| `palette.py`, `pixel.py` | The 15-bit GBA palette, and pixel-art helpers (outlined text, orbs, cards, the win/fail overlay). |
| `render.py` | The 640x360 frame: handheld bezels, HUD, fuse, cards, and every screen. |
| `audio.py` | Chiptune effects and music, adapted from Gate Drop's. |
| `input.py`, `config.py`, `hiscores.py` | Pads and the dev keyboard; every tuning number and button; the top-10 table. |

### Adding a microgame

Drop a module into `microgames/` with one `@register`ed `Microgame` subclass.
It's discovered automatically, and `tests/test_microgames.py` checks it
against the contract over 20 seeds at levels 0 and 3:

- its `bot()` always wins;
- doing nothing always loses;
- it's deterministic for a given seed;
- it draws in every state;
- its verb and caption use only glyphs the font has.

`align.py` and `cancel.py` are the reference implementations.

## Deploying to the cabinet

```bash
./deploy_batocera.sh                    # or ./deploy_batocera.sh root@10.42.0.100
```

The first time, you also need to add the `batocera/gamelist.xml` entry and
copy `batocera/icons/planck_time-image.png` to the cabinet, with
EmulationStation stopped, and then restart it (see `../AGENTS.md`). Later
deploys only replace the code.
