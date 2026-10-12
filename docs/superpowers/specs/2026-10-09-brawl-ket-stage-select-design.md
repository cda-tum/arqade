# Brawl-Ket: stage select and the QUANTUM WEEK stage: design

Two additions to Brawl-Ket (`brawl-ket/`), both approved by the user on 2026-10-09.

## 1. CHOOSE YOUR STAGE

- **When it appears:** a new match state, `STAGE_SELECT`, comes after CHOOSE YOUR
  FIGHTER, once both players are READY.
- **What it shows:** a big preview of the real backdrop (the stage surface, scaled down)
  with the stage's name between arrows. The order is:
  - RANDOM
  - LAB
  - CRYO
  - OPTICS
  - QUANTUMSPACE (the office)
  - QUANTUM WEEK (Toronto)
- **RANDOM's preview:** a big "?" over the stages, which cycle behind it about once a
  second.
- **Input:**
  - Either pad's stick (left/right) flips through the list.
  - A or Start begins the match on that stage.
  - B goes back to CHOOSE YOUR FIGHTER, with both players still READY, so one A there
    returns. There, a player's B un-readies them as it does today.
- **Hint line:** `STICK: CHOOSE   A: FIGHT!   B: BACK`.
- **Memory:**
  - The cursor starts on RANDOM.
  - Within a session it remembers the last pick. Coming back through the fighter
    screen, it is still where it was.
  - A rematch (A on the result screen) keeps the choice; RANDOM re-rolls.
  - Going back to the title resets it to RANDOM.
- **Unchanged:** the attract demo still picks at random. The idle timeout, Start +
  Select, and every state other than the new one behave as before.
- **Code:**
  - `Match` gains `stage_pick` (an index, 0 = RANDOM) and the state's handler.
  - `_start_match` uses the pick, or `rng.choice(config.STAGES)` for RANDOM.
  - `render.py` draws the screen. The previews are scaled once and cached, never every
    frame.
  - Each stage gets a display name: `config.STAGE_NAMES`.

## 2. QUANTUM WEEK: Toronto at dusk

IEEE Quantum Week 2026 (QCE26) is at the Metro Toronto Convention Centre, at the foot of
the CN Tower. The stage is a new `toronto` entry in `config.STAGES` and `_toronto` in
`stages.py`. It is drawn once, like the others. From back to front:

- **Sky:** a dusk gradient in dithered bands, orange at the horizon through pink and
  purple to deep blue at the top.
- **Skyline:**
  - the financial district's towers in dark silhouette, of varied heights and widths,
    some with scattered lit windows;
  - the Rogers Centre's low white dome, beside the tower's base.
- **CN Tower:** right of centre, so the timer doesn't cover it.
  - The slim, tapering concrete shaft, with its three-legged base flare.
  - The main pod: a wide disc with a lit window band.
  - The small SkyPod higher up, then the antenna, which may run up behind the HUD.
- **Metro Toronto Convention Centre:** a long, low glass front reflecting the sunset (a
  mullion grid, its panes catching the sky's colours).
  - Across it, a purple sign, **QUANTUM WEEK**, white on purple and lit.
  - Narrow vertical purple banners by the entrance say **QCE**.
  - The sign carries the conference's name only. It is not a copy of the official logo.
- **Foreground:** the paved plaza in front of the centre, warmly lit, with a couple of
  street lamps. It is the floor the fighters stand on. It stays mid-toned, so green and
  purple fighters read clearly against everything behind them.

## Testing

- Match logic:
  - the state order fighter select → stage select → round intro;
  - B goes back;
  - a fixed pick is used;
  - RANDOM picks from STAGES;
  - a rematch keeps the pick;
  - the title resets it.
- The existing stage tests cover the new stage automatically, because they are
  parametrised over `config.STAGES`.
- Snapshots of the new screen and stage, checked by eye.
