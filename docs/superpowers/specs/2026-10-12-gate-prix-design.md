# GATE PRIX: design

A kart racer for the ARQADE cabinet, the 11th game. You race inside quantum hardware, seen
from behind the car in pseudo-3D, OutRun-style. Gates stand on the track as arches. An
overlay shows the **target circuit**: drive through the arch of its next gate to stack the
circuit gate by gate. Every right gate is a light-speed boost, and the boost grows the
longer your streak runs. At the start of the final lap your circuit is checked against the
target, gate by gate. The fewer wrong gates (its Hamming distance), the bigger the boost
that carries you to the line.

The look reference is `2026-10-12-gate-prix-look.py`, the approved mockup: split screen,
the dilution fridge, semicircular arches.

## Why it fits the cabinet

- **Readable cold:** you steer through the gate the overlay shows. Racing needs no
  explanation, and the arch you want glows.
- **Stick + A:** the car accelerates by itself, the stick steers (and pulls back to brake),
  and A uses your item.
- **Fully visual:** the overlay, the glowing arch, the boost streaks and the CIRCUIT CHECK
  banner carry everything, so it plays in a noisy hall.
- **Short:** a race is 3 laps of about 45 s.
- **The domain:** the race *is* a circuit, a "racing circuit" pun made literal. The car's
  qubit is computed exactly from the gates you took, and is shown live on the car's Bloch
  orb.

## The race

- **The field:** 6 cars. 2 PLAYERS race in split screen (P1 on top, P2 below) against 4
  CPU racers. 1 PLAYER gets a full-screen view against 5 CPU racers.
- **Format:** 3 laps on a closed track.
  - The target circuit has **8 gates per lap**, so 24 in all, one **gate row** per slot.
  - The winner is whoever finishes first; places 1–6 are shown.
- **The target circuit:** a fresh random single-qubit circuit per race, drawn from H, X, Y
  and Z. It never repeats a gate twice in a row, so no slot is "free".
- **A gate row:** one place on the track for one slot of the circuit.
  - It holds **1 to 3 arches** spread anywhere across the track's width, with gaps. One arch
    is the slot's gate; the others are decoys, a different gate each.
  - Sometimes the right gate stands alone with open road beside it, so you must steer onto
    it.
  - The rows are the same for every car, in fixed places on the lap, and are rerandomised
    per race.
- **Driving through an arch** appends its gate to your circuit:
  - **The right gate** (the target's next): the streak +1 and a **light-speed boost**.
    - A streak of 1 gives +20% speed for 1.0 s.
    - Each further right gate in a row adds +8% and +0.2 s, up to +60% for 2.0 s.
  - **A wrong gate:** recorded as wrong, and the streak resets to 0. There is no other
    penalty.
  - **Missing every arch in a row:** that slot stays empty, which counts as wrong, and the
    streak resets.
- **CIRCUIT CHECK.** When you cross the line to start lap 3, your first 16 slots are
  compared with the target's first 16.
  - The **Hamming distance** is the number of slots that differ, with empty counting as
    different.
  - A banner shows "0 WRONG GATES — PERFECT CIRCUIT!" or "3 WRONG GATES", with the two
    circuits side by side and the wrong slots marked.
  - It gives a **big boost**: (16 − distance)/16 × 80% extra speed, for 1 s + (16 −
    distance) × 0.25 s. So a perfect circuit is +80% for 5 s.
  - Lap 3's gates still give streak boosts.
- **The car's qubit:** your circuit so far is simulated exactly on |0>, and the car's orb
  shows the result as a Bloch arrow and a colour. This is decoration and teaching only:
  scoring is gate by gate, as the user chose.
- **The results screen:** places, and each player's circuit against the target with its
  accuracy ("21/24 GATES") and final state. A rematches, B goes to the title.

## Items

Item boxes are spinning cubes at two places per lap. Drive through one to roll an item,
weighted by your place: further back gets better odds of the strong items. You hold one
item at a time, and **A** uses it.

| Item | Effect |
|---|---|
| **SPLIT** | For the next 2 gate rows a translucent **clone** drives mirrored across the track's centre line. If either car goes through the right arch, the slot counts as right. |
| **QEC** | **Error correction**: your most recent wrong or empty slot becomes right. This repairs the circuit for the CIRCUIT CHECK, not the streak. |

More items, for example one that clouds a rival's overlay with noise, can come later and
are not part of v1.

## Driving

- **Steering:** the car auto-accelerates to its top speed. The stick's left and right steer.
  Pulling the stick back brakes, and holding it back through a curve drifts a little.
  Pushing it forward does nothing.
- **Curves** push the car outward in proportion to speed and curvature, as OutRun does.
- **Off the road** (on the copper plate): top speed drops to 60%.
- **Cars bump:** a side contact pushes both cars apart, and a rear contact slows the car
  behind. There is no damage.
- **Hills and curves** come from the track's segment list.

## The CPU racers

- **Driving:** they follow the racing line at a skill-dependent pace.
- **Gates:** each one aims for the right arch with a skill-dependent hit rate, so the best
  CPU has about an 85% streak rate. Missed arches are mistakes.
- **Items:** they use them sensibly: QEC when they have a wrong slot, SPLIT before a row with
  a decoy.
- **Rubber-banding is mild:** a leader slightly slows and the last car slightly speeds up,
  so races stay close.

## The look

- **The world:** the first track is **THE FRIDGE**, the inside of a dilution refrigerator, as
  in the mockup.
  - The road runs across a copper stage plate under the next stage's gold plate.
  - Coax lines with SMA connectors and attenuators stand along the roadside like trees.
  - Behind them are the radiation-shield wall and the cold haze at the horizon.
  - The track runs down through the stages: hills are the drops between plates.
- **More tracks later**, each one platform, not part of v1: a photonic-chip highway and an
  ion-trap tunnel.
- **Style:** smooth, lit, high resolution, deliberately not pixel art.
  - **The arches** are semicircles with both feet on the track, a light curtain under them
    and the letter on a round badge at the crown. The gate colours are shared with the other
    games (H gold, X red, Z blue, Y purple), and the right arch glows.
  - **The cars** are low wedges with rear wings and tail lights, P1 blue and P2 red. CPU cars
    are other colours and never blue or red. Each car carries its Bloch orb.
- **The HUD**, per view:
  - The **circuit overlay** at the top left. The TARGET wire is a scrolling window of the
    next gates, the next one outlined. The YOU wire is aligned under it, with ✓ and ✗ marks.
  - The place and the lap.
  - The streak and LIGHT-SPEED BOOST.
  - The item slot.
- **Rendering:** at 960x540, scaled exactly 2x.
  - Each 2P view is 960x270. The 1P view is 960x540, with the same drawing and a different
    view rectangle.

## Performance

- **The road** uses the classic pseudo-3D technique. It projects about 120 segments per
  view, draws each as flat polygons (plate, rumble, road, centre line), and clips by
  hills.
- **Sprites** (trees, arches, cars, boxes) are pre-rendered once at about 24 sizes each, and
  the nearest size is blitted. They are never rescaled per frame.
- **Static backgrounds** (the plate overhead, the shield wall, the haze) are drawn once per
  view size, with parallax by horizontal offset only.
- **Budget:** 60 fps on the Pi 4 for 2 views. A road-rendering benchmark on plain surfaces is
  the plan's first task, measured on the cabinet as early as it is reachable. If 960x540 is
  too slow, the fallback is 640x360, which scales 3x.

## Cabinet conventions (AGENTS.md)

- **Buttons:** A uses an item and confirms in menus, B goes back. Start starts and pauses,
  with RESUME and QUIT TO TITLE. Start + Select quits.
- **The title waits for buttons to be released** when reached from QUIT TO TITLE.
- **The stick** is axis 0 for steering and axis 1 for braking and menus, with deadzone 0.25.
- **Idle:** 60 s returns to the title.
- **Colours:** P1 blue on the top or left, P2 red.
- **Loader:** `--fullscreen --no-keyboard`. P1's dev keys avoid `l x r b y a`, and
  `--input-test` is available.
- **Line endings:** LF.
- **New ROM:** it needs a gamelist entry and one ES restart (with the user's go-ahead), and
  a logo module in `batocera/logos/` with its own look, distinct from every existing icon.
- **Title:** the stick picks 1 or 2 PLAYERS, and an attract demo of CPU racers plays after
  3 s untouched.

## Code layout (`gate-prix/src/gate_prix/`)

| Module | Role |
|---|---|
| `circuit.py` | Gates, the single-qubit simulation, target generation, slots, Hamming distance, QEC. Pure. |
| `track.py` | The track's segments (curve, hill), gate rows, item boxes, the racing line, lap length. Pure. |
| `car.py` | Car physics along the track (speed, lateral position, curves, off-road, boosts, bumps). Pure. |
| `race.py` | The race: cars, laps, arch hits, items, CIRCUIT CHECK, places, the finish. Pure. |
| `bot.py` | The CPU racers. |
| `match.py` | Title, race, pause, result, idle, attract. Pure. |
| `road.py` | The pseudo-3D projection and road drawing for one view. |
| `sprites.py` | The pre-rendered, size-cached sprites. |
| `render.py` | Views, HUD, overlay, banners, screens. |
| `input.py`, `config.py`, `audio.py`, `main.py`, `input_test.py` | As in the other games. |

## Testing

- **`circuit`:**
  - the simulation is exact for H, X, Y and Z (known states, H·H = I);
  - targets never repeat a gate twice in a row;
  - Hamming distance with empty slots;
  - QEC repairs the most recent wrong slot.
- **`race`:**
  - a right arch extends the streak and boosts, by the boost table;
  - a wrong arch resets the streak;
  - a missed row leaves an empty slot;
  - SPLIT counts either car;
  - the CIRCUIT CHECK fires once, at lap 3, with the boost formula;
  - places are ordered by laps and distance;
  - the finish.
- **`car`:** auto-acceleration to top speed, braking, off-road, a curve pushing outward, a
  bump separating two cars.
- **`bot`:** over seeds, a CPU finishes every race, the best CPU's streak rate is about 85%,
  and a perfect human (a scripted bot hitting every right gate) beats the field.
- **Snapshots and a benchmark,** checked by eye against the mockup and measured on the Pi.

## Changes after the first playtest (2026-10-12)

The user played the first playable build. It "still feels a bit clunky": the speed and
boosts didn't feel like much, and there was too much to read. They didn't know how to use
items, the "next gate / incorrect gate" idea was confusing, and they didn't notice the
CIRCUIT CHECK boost.

- **No gates on the final lap.** Gate rows run on laps 1–2 only, 8 per lap, so the target
  has **16 gates**. The CIRCUIT CHECK covers all 16 as a car starts lap 3, and lap 3 is a
  gate-free sprint powered by the check boost. Item boxes stay on every lap.
- **The right arch is unmissable.** It glows brightly, with a bouncing ▼ marker above it.
  Decoys are drawn dimmer and smaller.
- **A simpler overlay.**
  - One big **NEXT GATE** badge replaces the TARGET and YOU wires.
  - Under it, a row of your gates so far as ✓ green and ✗ red dots, 16 in all.
  - Each row you pass flashes **RIGHT GATE +BOOST** (blue) or **WRONG GATE** (red) near your
    car, and a missed row flashes **MISSED**.
- **Items explain themselves.**
  - While you hold an item, the slot pulses and shows its name, a big **A**, and one line:
    "SPLIT: a clone takes a second gate" or "QEC: fixes your last wrong gate".
  - The first pickup of each item in a session shows a banner: "PRESS A TO USE SPLIT".
- **The CIRCUIT CHECK is an event.**
  - As a car crosses into lap 3, that player's view freezes for about 1 s. A panel compares
    the circuits ("14/16 GATES CORRECT", with the wrong ones marked).
  - Then comes the **LIGHT SPEED!** warp: a star-streak tunnel, the field of view widening, a
    tint at the edges of the screen, and a whoosh.
  - The check boost is strong and long enough that you visibly pass cars. The CPUs get the
    same check by their own accuracy.
  - The freeze applies only to that player's view and clock. The race keeps running for the
    others, but that player loses no distance: their car keeps moving during the freeze.
- **Speed you can feel.**
  - A higher sense of speed: roadside objects closer to the road, speed lines at top speed,
    and a slight camera shake.
  - Boosts widen the field of view and show exhaust flames, with a boost whoosh.
  - Top speed rises about 10–15% if the lap stays readable, and the boost tables are retuned
    so a streak boost is clearly felt.

## Changes after the second playtest (2026-10-13, on the cabinet)

The user played the build on the cabinet in experimental mode. The frame rate is good on
the Pi. Their feedback was:
- the split screen should be vertical;
- the finish line isn't visible;
- the game needs a minimap;
- the final lap is a bit lame;
- drifting would be cool;
- the items are boring, and more items with icons are needed.

They picked the "noise storm" final lap and the MEASURE, TUNNEL and DECOHERENCE items.

### Rules (Task 5c)

- **Drifting.**
  - **Starting and holding:** pull the stick back *and* steer, with |steer| ≥ 0.4, at ≥ 60%
    of top speed. Pulling straight back is still the brake.
  - **While drifting:** the car slides at an angle, turns tighter (the curve's outward push
    is reduced) and loses a little speed, down to 92% of what it would have.
  - **Charge:** level 1 at 0.7 s of drifting, level 2 at 1.5 s.
  - **Releasing** the drift gives a **mini-turbo** through `give_boost`: level 1 is +25% for
    0.6 s, level 2 is +40% for 1.0 s.
  - **Ending:** a drift with no charge ends with nothing. Letting go of the stick, slowing
    below 50% or a bump ends the drift; a bump ends it with no turbo.
  - **CPUs** drift in the sharpest curves by skill.
- **The noise storm (the final lap).** Lap 3 has no gates. Instead each racer meets its own
  **decoherence hazards**, visible and active only for that racer.
  - **How many:** 4 + 2 × (16 − right) hazards (a perfect circuit gets 4, 8/16 gets 20, capped
    at 24). They are spread over the lap, never within 1 s of the finish line, and always leave
    a clear line one car wide.
  - **Static clouds:** wide and soft. Driving through one removes your boosts and caps your
    speed at 70% for 1 s.
  - **Bit-flip mines:** small and sharp. One spins you out: your speed falls to 40%, you can't
    steer for 0.8 s, and your streak is irrelevant by then.
  - **The CIRCUIT CHECK warp** still happens; the storm comes on top of it.
  - **TUNNEL** makes you immune.
- **Items (5 in all).** Boxes always give an item, so no box is ever empty. Lap 3 boxes never
  give SPLIT or QEC.

  | Item | Effect |
  |---|---|
  | SPLIT | as before: a mirrored clone for the next 2 rows, where either car counts |
  | QEC | as before: your most recent wrong or empty slot becomes right |
  | **MEASURE** | a homing shot at the nearest car ahead, within 30,000 units. It **collapses** that car: a spin-out (40% speed, no steering for 0.8 s), its streak reset, its boosts cleared. If no car is in range it fizzles. TUNNEL makes a car immune. |
  | **TUNNEL** | quantum tunnelling for 3 s: you pass through cars (no bumps), drive off-road at full speed, and are immune to hazards, clouds and MEASURE |
  | **DECOHERENCE** | drops a static cloud on the road just behind you, where it stays 10 s or until a car hits it. A car that drives through it loses its boosts, and its NEXT GATE badge and right-arch marker **go blank for 1.5 s** (or, on lap 3, it takes the cloud hazard's slowdown) |

  - **Weights by place:** the back of the field gets more of MEASURE, TUNNEL and SPLIT; the
    front more of DECOHERENCE and QEC. The table is in config.
  - **CPUs:** they fire MEASURE when a car is ahead in range, use TUNNEL in traffic or before
    a hazard, drop DECOHERENCE when a car is close behind, and use SPLIT and QEC as before.
- **From Task 5b's review:**
  - a held SPLIT that runs out of rows is cued (`split_end`), and no SPLIT or QEC is rolled
    past the last row;
  - the results show the check as "CHECK 12/16" (the number right), not a Hamming distance;
  - a check below +5% boost shows **NO BOOST** instead of the full LIGHT SPEED! show.

### Screens (Task 5d)

- **Vertical split screen.** 2P is two 480x540 views side by side, P1 on the left and P2 on
  the right, with a thin divider. The HUD is laid out for the narrow view:
  - the NEXT GATE badge at the top left;
  - 16 dots in two rows of 8;
  - the place and lap at the top right;
  - the item slot under them.

  1P keeps the full 960x540 view.
- **The finish line.** A chequered band across the road at the lap line, under a **start and
  finish gantry**: two posts and a "GATE PRIX" banner with five start lights. The lights go red
  one by one in the countdown and all green at GO. As a racer crosses it, a LAP 2/3 or FINAL
  LAP banner shows.
- **The minimap.** The lap's plan view, built from the track's curves, with:
  - a dot per car in its colour (yours bigger, with a ring);
  - small ticks for the gate rows and boxes;
  - the finish line.

  In 1P it sits in the bottom-left corner; in 2P one shared map straddles the divider at the
  bottom. Pre-render the outline once, and draw only the dots per frame.
- **Drifting:** the car sprite is tilted at the drift angle, using cached rotated variants at a
  few angles. Sparks behind the rear wheels turn from white to blue (level 1) to gold
  (level 2), and the mini-turbo flash shows.
- **The noise storm:** the static clouds (crackling grey-violet) and the bit-flip mines (small
  spiked orbs marked with an X) are drawn in that racer's view only. A STORM AHEAD banner
  shows at the start of lap 3.
- **Item icons**, one for each item, used in the slot, the first-pickup banner and the box
  reveal:
  - SPLIT: two overlapping car silhouettes;
  - QEC: a shield with a check mark;
  - MEASURE: a meter needle, or an eye collapsing onto a dot;
  - TUNNEL: a ghost car passing through a wall;
  - DECOHERENCE: a static cloud.

  The item effects are drawn too: the MEASURE shot's beam, a TUNNEL car's translucency and
  shimmer, the DECOHERENCE cloud on the road, and a blanked badge.
- **AGENTS.md's new rules:**
  - **A QUIT row** on the title menu: 1 PLAYER / 2 PLAYERS / QUIT, moved with stick up and
    down and clamped (no wrap, so a held stick stays put). A on QUIT quits at once. Start never
    quits: it begins play with the highlighted mode, or 1 PLAYER if QUIT is highlighted. The
    attract bots never pick it.
  - **A HOW TO PLAY card** before every match started from the title (not on a rematch). It is
    drawn in the game's look, with:
    - the goal in 1–3 lines ("Drive through the glowing gate. Build the circuit. Fewer
      mistakes = a faster final lap.");
    - an animated demo using the game's own code: a car steering through the right arch and
      boosting;
    - the controls drawn as the L X R / Y B A cluster with A lit, plus the stick for
      steer/brake/drift and START;
    - a blinking PRESS ANY BUTTON TO START.

    Any button on either pad dismisses it, but the stick doesn't. Presses in the first 0.3 s
    are ignored, and the dismissing press does nothing in the game. Start + Select still quits,
    and the idle timeout runs. The attract race skips it, since it is not started from the
    title by a player.
- **From Task 5b's review:**
  - in 2P the first-pickup tip never covers a gate flash;
  - "FINAL LAP: NO GATES" shows only from lap 3, with "TO THE LINE" after row 16 until then.
