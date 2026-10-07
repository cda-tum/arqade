# Planck Time Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build Planck Time, a WarioWare-style quantum microgame party for 1-2
players with GBA pixel art, and ship it to the ARQADE cabinet.

**Architecture:** A uv project `planck-time/` in the sibling games' shape.
- **The contract** in `microgames/base.py`: every microgame is a pure class
  that steps on `PlayerInput`, ends in success or failure, has a perfect bot,
  and draws itself to a 240x160 surface.
- **One generic test harness** checks every registered microgame the same
  way.
- **`session.py`** (pure) runs the beats, speed, lives, scores and versus.
- **`render.py`** frames two GBA bezels on a 640x360 canvas, scaled x3.

**Tech Stack:** Python 3.11, pygame 2.5.2, pytest, uv.

**Spec:** `docs/superpowers/specs/2026-10-01-planck-time-design.md`. The
microgame rules table in its section 2 is normative.

## Global Constraints

- `requires-python = ">=3.11,<3.12"` and `pygame==2.5.2` exactly. LF line
  endings everywhere, and `deploy_batocera.sh` committed executable.
- Raw buttons: A = 1, B = 2, Select = 8, Start = 9. The stick is analog,
  axis 0 horizontal and axis 1 vertical (negative = up), with the hat as a
  fallback.
- Every microgame uses only the stick and A.
- Internal resolution 640x360 (x3), each microgame screen 240x160,
  `SDL_RENDER_SCALE_QUALITY=nearest`. P1 (left) is blue and P2 (right) red.
- Microgames and `session.py` contain no pygame outside `draw()`. All
  randomness comes from the seed.
- AGENTS.md conventions: Start pauses (RESUME / QUIT TO TITLE), Start +
  Select quits, 60 s idle timeout, A confirms and B goes back, the loader
  passes `--fullscreen --no-keyboard`.
- Commits: gitmoji conventional style, ending with
  `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.

## The microgame contract (Task 2 creates it; every microgame task relies on it)

```python
# planck_time/microgames/base.py
@dataclass(frozen=True)
class PlayerInput:
    stick: tuple[float, float] = (0.0, 0.0)  # analog, deadzoned, -1..1, y positive = down
    step: tuple[int, int] = (0, 0)           # a stick push this frame, auto-repeated (cursor and grid moves)
    a: bool = False                          # A pressed this frame
    a_held: bool = False

class Microgame:
    VERB: str          # "ALIGN!"
    INPUT: str         # "stick" | "a" | "mash" | "stick+a"
    CAPTION: str
    def __init__(self, seed: int, level: int, duration: float): ...
        # self.rng = random.Random(seed); self.level; self.duration
        # self.speed = 1 + 0.15 * level; self.t = 0.0; self.result = None; self.won_at = None
    def update(self, dt: float, inp: PlayerInput) -> None  # calls step() while unresolved; always advances t
    def step(self, dt: float, inp: PlayerInput) -> None    # the rules (override)
    def win(self) / fail(self)                             # resolve: result True / False, won_at = t
    def timeout(self) -> None                              # the time is up: default fail(); SHIELD/REFRESH win
    def bot(self) -> PlayerInput                           # perfect play from the current state (override)
    def draw(self, surf: pygame.Surface) -> None           # onto a 240x160 surface (override)

REGISTRY: list[type[Microgame]]   # filled by the @register decorator; microgames/__init__.py imports all modules
```

**The generic harness** is `tests/test_microgames.py`, parametrised over
`REGISTRY` and levels `(0, 3)`. `simulate()` runs at dt = 1/60 for
`duration` seconds, stops early on a failure, and calls `timeout()` at the
end.
- **The bot wins** for seeds 0 to 19.
- **Doing nothing loses** for seeds 0 to 19.
- **Same seed, same result:** two instances with the same seed, fed the same
  random input sequence, end with the same result and `won_at`.
- **Drawing never raises:** `draw()` runs at several moments of a bot game,
  and after the result, on a 240x160 surface.
- **Metadata is valid:** `VERB` ends with "!", `INPUT` is in the allowed
  set, `CAPTION` is no longer than 64 characters, and the font can render
  every character in all three.

---

### Task 1: Scaffold
Copy the sibling patterns into `planck-time/`:
- packaging and `.gitignore`;
- `config.py` (640x360, input config, colours, timings from the spec);
- `display.py`, `fonts.py` and the font assets;
- `hiscores.py`, from Gate Drop with the score file path changed.

Tests `test_config.py` (buttons, resolution x3, player colours) and
`test_display.py`. Commit.

### Task 2: The contract, the palette, the pixel helpers, the harness
- `microgames/base.py` as above.
- `palette.py`: the GBA palette. Every channel is a multiple of 8, and there
  are named colours for the UI, the players, and the X Y Z H gate colours
  shared with Gate Drop.
- `pixel.py`: `outlined(font, text, color)`, `dither(surf, rect, c1, c2)`,
  `orb(surf, center, r, color)` (a shaded sphere with an outline),
  `gate_card(surf, rect, letter, color)`, and `bounce_text`.
- `tests/test_microgames.py`: the harness. Commit.

### Task 3: Reference microgames ALIGN! and CANCEL!
Implement both exactly as in the spec table. They become the style template
for the other ten: a GBA-style background (an 8x8 tile pattern), a chunky
outline on everything, and win/fail animations (a confetti burst or a crack
and shake), drawn from `self.result` and `self.t`. The harness must pass.
Commit.

### Tasks 4-6: The other ten microgames (in parallel)
- **Agent A:** FIX!, MEASURE!, SHIELD!, VOTE!
- **Agent B:** SHORTER!, CONNECT!, PAIR!
- **Agent C:** REFRESH!, STEER!, SORT!

Each module follows the spec table and the ALIGN!/CANCEL! template, and
passes the harness. Each also adds its own rule tests for its trickiest rule
(e.g. CONNECT!'s broken couplers, SORT!'s wrong-bin failure). Agents touch
only their own microgame modules and their tests. Commit per agent after
review.

### Task 7: The session (`session.py`)
Pure state machine:
- **States:** TITLE (with the bot-driven attract demo), INTRO 1.5 s, PLAY,
  RESULT 1.2 s, SPEED_UP 1.2 s, GAME_OVER, NAME_ENTRY, HISCORES and
  MATCH_RESULT, plus a `paused` overlay during INTRO, PLAY, RESULT and
  SPEED_UP.
- **`FrameInput`:** a `PlayerInput` per player, menu nav, and per-player
  confirm, back and pause.

Tests:
- **Beats:** their timing; PLAY ends early once every player has failed;
  `timeout()` is called at the end.
- **Order:** the no-repeat deck.
- **Speed:** the ramp every 4 microgames, and the duration formula.
- **Single player:** lives; game over leading to initials when the score
  qualifies, and to the table otherwise.
- **Versus:** +1 for a success, +1 more for finishing first; last player
  standing; a draw on equal scores; same-seed instances for both players;
  the rematch.
- **First appearance:** the flag that drives the intro demo.
- **Pause:** it freezes play, and offers RESUME and QUIT TO TITLE.
- **Idle:** the timeout returns to the title.

Commit.

### Task 8: Rendering, input, sound, game loop
- `render.py`:
  - **Bezels:** two GBA bezels in the player colours, with a D-pad and A/B
    wings and a power LED.
  - **Microgame screens:** blitted in from each instance's surface.
  - **HUD:** hearts, the score and the timer bar.
  - **Cards:** the intro (verb, input icon, first-time demo animation), the
    result (NICE!/OOPS! and the caption), and SPEED UP!.
  - **Screens:** the title with its logo and the attract demo; initials,
    high scores, the match result, and the pause menu.
- `input.py`: from Gate Drop, adapted to the analog stick plus step presses
  and the `PlayerInput` contract.
- `audio.py`: from Gate Drop, with jingles per beat and the tempo following
  the level.
- `game.py`, `main.py`, `input_test.py`.
- **Snapshot tool** `tools/snapshot.py`, which renders every microgame and
  every screen to PNGs.
- **Tests:** render smoke tests through every screen and microgame, and a
  headless smoke run of `main([])`.

Commit.

### Task 9: Packaging and shipping
- `deploy_batocera.sh`, the README, a `planck_time()` icon in
  `generate_icons.py`, the `gamelist.xml` entry ("Planck Time"), and the game
  added to AGENTS.md's list.
- **Cabinet:** check that it's idle, deploy, then register the menu entry
  with ES stopped and restart ES. Verify "Games: 9", and run the renderer
  benchmark on the Pi. Commit and push.
