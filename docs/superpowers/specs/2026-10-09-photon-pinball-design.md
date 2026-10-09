# Photon Pinball: design

A two-player versus pinball game for the ARQADE cabinet, the 11th game. Each player keeps
balls alive on their own table. Shooting your ramp sends the ball, a photon, onto a shared
**Mach–Zehnder interferometer, "the bridge"**:

- the photon splits into two halves, one per arm;
- each arm passes one player's **phase plate**;
- where the halves meet again, interference sends the whole photon either **onto the
  rival's table**, as an extra ball they must handle, or **back onto yours**.

Hitting your **φ target** flips your plate between 0 and π. That turns an attack around, or
lets yours through.

The look reference is `2026-10-09-photon-pinball-look.py`. It renders the approved mockup:
the realistic, glossy machine with photonics art.

## Why it fits the cabinet

- **Readable cold:** everyone knows pinball. You hit the ball with A and don't let it drain.
- **The quantum part is the weapon and is exact:**
  - The bridge is a real interferometer, computed with complex amplitudes.
  - Its outcome is fully deterministic, because the phases are only ever 0 or π.
  - You see the split as two ghost halves, and you see the result as where the whole photon
    lands.
- **Short rounds and silent play:**
  - A match lasts at most 2 minutes.
  - Every event is visual: the dot-matrix display (DMD) calls each one, and the bridge shows
    the split. Sound is only a bonus in a noisy hall.

## The match

- **Format:** 2 players, versus. **1 PLAYER** plays against a CPU on the right-hand table. The
  title screen's stick picks 1 or 2 players, as in Qlimbers.
- **Balls and lives:** each player has **3 lives**.
  - A ball that drains on your table costs you a life, whoever launched it.
  - After a drain, a new ball waits on your plunger if you have lives left. Any balls you
    received may still be in play meanwhile.
- **Sending a ball doesn't cost a life:** when your ball leaves for the bridge, a fresh ball is
  served to your plunger at once.
- **How a match ends:**
  - When a player loses their last life, the other wins.
  - Otherwise it ends at **2:00**, and the higher score wins. On equal scores, fewer lives lost
    wins, and if that is equal too it's a draw.
- **After the match:**
  - The result screen shows the winner and both scores.
  - A rematches, B goes to the title.

## The tables

There are two mirrored tables: P1's (blue) on the left and P2's (red) on the right. Each has:

- **Two flippers.** Both are on **A**: the cabinet rule is stick + A, and one button for both
  flippers is common in simplified pinball.
- **The plunger lane** on the outer side.
  - **Pull the stick down and let go** to launch; the strength depends on how long it was
    held.
  - An untouched ball **auto-launches after 2 s**, so a newcomer is never stuck.
- **Three pop bumpers**, styled as ring resonators. They kick the ball away and score, and
  they flare when hit.
- **Two slingshots**, with lit plastics over rubber bands. They kick sideways.
- **Inlanes and outlanes.** The outlanes drain, so they are kind but real.
- **Top rollover lanes.** Lighting all three doubles your bumper score until you drain.
- **The ramp mouth**, at the inner top, with three arrow inserts. A fast enough ball enters
  the ramp; a slow one rolls back out.
- **The φ target**, on the outer wall, with its arrow insert. Each hit toggles your phase plate
  between 0 and π. It is lit amber at π, and the bridge's plate shows the same.
- **The apron, the side rails and the glass**, as in the mockup.

The playfield print is a photonic chip:

- a Mach–Zehnder mesh of waveguides with directional couplers;
- micro-rings;
- grating couplers and detector meanders;
- the die outline.

It's decoration only, with nothing to hit.

## The bridge: the physics, exactly

Between the tables, on a glass breadboard, sit:

- **BS1** at the top: a 50:50 beam splitter;
- the mirrors **M1** (left) and **M2** (right);
- **BS2** at the bottom;
- P1's plate **φ1** on the left upper arm, and P2's **φ2** on the right.

**Ports.** P1's ramp feeds BS1 from the upper left, and P2's from the upper right. BS2's
lower-left output drops onto P1's table, and its lower-right output onto P2's.

**The maths** (`bridge.py`, pure, tested):

- A photon's state is a pair of complex amplitudes over the two arms.
- BS = (1/√2)·[[1, i], [i, 1]].
- A plate multiplies its arm by e^{iφ}.
- The output is BS · diag(e^{iφ1}, e^{iφ2}) · BS applied to the input port's basis vector.
- The intensity at each output port is the squared modulus of its amplitude.

**The truth table this gives** (and the tests check):

| Phases | Result |
|---|---|
| φ1 = φ2 (Δ = 0) | the photon **crosses**: P1's goes to P2's table, P2's to P1's |
| φ1 ≠ φ2 (Δ = π) | it **returns** to its sender's table |

Intensities are exactly 1 and 0. Phases are only 0 or π, so the result never depends on luck.

**When the phase counts.** Each half's phase is taken **at the moment it passes its arm's
plate**. As it passes, the plate pulses in that half's colour. After that, flipping a plate
doesn't change that photon. So to bounce a rival's photon, you must flip before it reaches
your plate.

**Timing.**

| Stage | Duration |
|---|---|
| Ramp ride | 0.7 s |
| BS1 → the plates | 0.35 s |
| The plates → BS2 | 0.5 s |
| BS2 → dropped onto a table | 0.6 s |

**On the bridge:**

- Any number of photons can be on the bridge at once, each independent.
- P1's and P2's photons are different colours, so different wavelengths: distinguishable
  photons, which physically do not interfere with each other. Two-photon effects are rightly
  absent.

**Where the ball lands.** BS2's chosen output carries the whole photon down a wire ramp. It
drops onto the destination table's upper inner side with a fixed velocity, into play, as an
extra ball.

**Drawn as:**

- the halves are see-through ghost balls inside dashed rings, with the arms lit in the
  photon's colour;
- at BS2 the halves merge with a flash, and the whole photon leaves down one ramp;
- the DMD calls **SPLIT!**, then **INCOMING!** (crossed) or **BOUNCED!** (returned).

## Scoring

| Event | Points |
|---|---|
| Slingshot | 10 |
| Pop bumper | 100 (200 with the top lanes lit) |
| Top rollover lane | 250 |
| φ target | 500 |
| Ramp shot (entering the bridge) | 1,000 |
| Your photon crosses to the rival | **5,000** |
| A rival's photon you returned (your plate made Δ = π) | **2,500** |

Draining scores nothing and costs a life.

## Physics (`physics.py`, pure, tested)

- **Units and stepping:** design pixels in 960x540, with a fixed **240 Hz** step (4 substeps
  per 60 Hz frame) so a fast ball never tunnels.
- **The ball:** radius 9. Gravity along the table is about 900 px/s², and speed is capped at
  about 1,400 px/s.
- **Colliders:**
  - line segments (walls, guides, rails);
  - circles (bumpers, posts);
  - the flippers: capsules rotating about a pivot, with angular velocity applied to the
    contact point.
- **Restitution and kicks:**
  - Walls have restitution about 0.5.
  - Bumpers and slingshots add a kick along the contact normal.
- **Flippers:** they rise at about 25 rad/s and fall back under a spring.
- **Sensors:**
  - the ramp mouth: the ball enters only above a minimum speed going up;
  - the drain;
  - the plunger lane's exit;
  - the rollover lanes;
  - the φ target, a thin segment with an upward-facing hit test.
- **Balls in a table:** they collide with each other too, as simple circle–circle collisions.
- **The CPU player** (and the attract demo's two players):
  - It flips when a ball is within reach of a flipper and moving toward it.
  - It aims for the ramp by timing the flip: a late flip sends the ball inward.
  - It hits the φ target when a rival photon is about to reach its plate, with a reaction
    delay and a miss rate, so it is beatable.
  - It plunges at a random strength.

## Cabinet conventions (AGENTS.md)

- **Buttons:** A flips, Start pauses, and Start + Select quits. The stick's down axis is the
  plunger, axis 1 with deadzone 0.25.
- **Pause:** RESUME and QUIT TO TITLE. A title reached from QUIT TO TITLE waits for its
  buttons to be released.
- **Idle:** 60 s without input returns to the title.
- **Colours:** P1 blue on the left, P2 red on the right.
- **Loader:** `--fullscreen --no-keyboard`. P1's dev keys avoid `l x r b y a`, and
  `--input-test` is available.
- **Line endings:** LF.
- **New ROM:** `photon_pinball.pygame` needs a gamelist entry and an ES restart once (the
  user's go-ahead first), plus a logo module in `batocera/logos/`.
  - The logo's own look is "a real machine's backglass".
  - It must differ from every existing icon.

## Look and performance

- **Resolution:** 960x540, scaled exactly 2x to 1920x1080. This is smooth, anti-aliased art,
  **not pixel art**, deliberately unlike the GBA-style games.
- **Fonts:** DejaVu Sans Condensed Bold is bundled (its licence allows it) for labels. Press
  Start 2P renders the DMD's dots.
- **Static art is drawn once,** at start-up, into one background surface at 2x and
  smoothscaled. That covers the playfield print, chrome, plastics, apron, rails, glass and
  bridge deck.
- **Per frame:**
  - balls (pre-rendered sprites for whole and ghost photons);
  - flippers (sprites cached at their rotation angles);
  - bumper flares;
  - lit inserts (cached glow sprites);
  - the bridge's beams and plates;
  - the DMD, updated only when its text changes.
- **Budget:** the Pi 4 must hold 60 fps. A benchmark like Planck Time's (plain surfaces, no
  display) must show the worst frame comfortably under 16.7 ms, measured on the cabinet before
  deploying.

## Code layout (`photon-pinball/src/photon_pinball/`)

| Module | Role |
|---|---|
| `bridge.py` | The interferometer: amplitudes, plates, the phase lock, timing. Pure. |
| `physics.py` | Ball, colliders, flippers, sensors, the fixed step. Pure. |
| `table.py` | One table's layout (every collider and sensor, mirrored for P2), from design coordinates shared with the art. Pure. |
| `match.py` | Lives, serving, scoring, the clock, the end of a match, the CPU and attract players, title/pause/result states. Pure. |
| `art.py` | The static art (the mockup's drawing, made a module), the sprite caches. |
| `render.py` | Each frame: the background, the dynamic parts, the DMD, the screens. |
| `input.py`, `config.py`, `audio.py`, `main.py`, `input_test.py` | As in the other games. |

## Testing

- **`bridge`:**
  - the truth table above, for every combination of input port, φ1 and φ2;
  - intensities sum to 1;
  - the phase lock: a flip after a half has passed its plate doesn't change that photon;
  - two photons on the bridge are independent.
- **`physics`:**
  - a raised flipper sends a resting ball up;
  - a ball at maximum speed never passes through any wall of the table (swept tests);
  - a bumper kicks;
  - a slow ball doesn't enter the ramp and a fast one does;
  - the drain sensor;
  - two balls collide.
- **`match`:**
  - a drain costs a life and serves a ball;
  - sending doesn't cost a life;
  - the end by lives and the end by time, with the tie-breaks;
  - the scoring table above;
  - pause freezes everything;
  - the idle timeout;
  - Start + Select.
- **The CPU:** over seeds, it keeps a ball alive for at least 20 s on average, and it is not
  unbeatable.
- **Snapshots:** a tool renders the title, a match, a split on the bridge, INCOMING!,
  BOUNCED!, pause and the result, checked by eye against the mockup.
- **Benchmark:** the worst frame on the cabinet.
