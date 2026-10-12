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
