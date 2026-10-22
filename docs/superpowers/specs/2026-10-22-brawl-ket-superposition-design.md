# Brawl-Ket: SUPERposition, a super move for every fighter: design

**Status: agreed with the user on 2026-10-22**, in a brainstorm that followed their playtest
note that "the game feel is still a bit lackluster". The same session shipped the feel tuning
(every A normal 4 frames more recovery, faster walks, jumps that clear anyone) and RANDOM on
CHOOSE YOUR FIGHTER; this spec is the third and largest part.

The idea: every fighter gets one big cinematic super. Its bar has a green half and a purple
half, and fills only by fighting in **both** bases, so switching (Y) pays. The super is the one
attack that ignores the colour rule: you built it in both colours, so it hits in both.

The name is **SUPERposition**: only SUPER is in capitals (the bundled Press Start 2P has real
lower case, checked by rendering it). It is a pun that explains itself: a SUPER move that is
only yours once you have been in both bases.

Nothing in the v3 rules (`2026-10-02-brawl-ket-basis-design.md`) changes for any other move.

## 1. The bar

- **One per player,** under the health bar: a green half (Z) and a purple half (X), side by
  side, each `SUPER_HALF = 40` points.
- **What fills a half:**
  - **damage you deal** fills the half of the basis **you** are in when it lands, point for
    point;
  - **damage you take** fills the half of the basis you are in when it lands, at half the rate.
    (You are only ever hurt in your own colour, so this is always your current basis.)
  - Throws, specials and normals all count. Blocked (wrong-colour) hits, chip and the super's
    own damage fill nothing.
  - A half stops at full; the overflow is lost.
- **DOS is the exception:** he can never switch, so his halves fill by the **colour of the hit**
  instead: his A hits (green) fill green, his B hits (purple) fill purple, a PASTE fills the
  colour it was pasted in. Damage he takes is always green, so taking hits fills only his green
  half (at half the rate).
- **Full means both halves full.** The bar then shines white and gold and blinks **A+B!** under
  it, so a visitor knows what to press.
- **It carries over from round to round** (Street Fighter style) and resets to empty at the
  start of every match, rematches included.
- About one or two good exchanges per half: a round of trading normals in one colour fills one
  half and nothing of the other.

## 2. Firing it

- **A and B together,** within `SUPER_WINDOW = 3` frames of each other, while the bar is full.
  - The two colour buttons at once, for the move that is both colours at once.
  - With a full bar, a lone A or B is held back up to 3 frames, waiting for its partner, then
    comes out as normal. With a bar that isn't full, A and B behave exactly as today.
- **When:** from the ground in any state you can act in: standing, crouching, walking, and
  as soon as a block-stun ends. Not in the air, not in hitstun or knockdown, not mid-move (no
  cancels into it).
- **Firing empties both halves.**
- **ALICE & BOB:** the bar is the pair's (one bar, as their health). A decohered Bob re-forms
  at once for their super. Bob never echoes a super; it is one move for both.

## 3. The freeze and the call

Every super opens the same way, and then plays its own scene.

- **The freeze (`SUPER_FREEZE = 30` frames, 0.5 s):** the whole fight stops (both fighters,
  shots, traps, timers and the round clock).
  - The screen darkens behind the super's fighter.
  - A flash of both colours runs across the screen.
  - Their portrait (the select screen's) slides in, with the call **SUPERposition!** and under
    it the move's own name (e.g. **BLOCH SPHERE**).
- **Then the move:** the super's own frames (section 4), with everything running again.
- **Damage:** about 25 in all for every super, whatever the rival, ignoring the colour rule
  (it hurts green and purple alike). Hitstun and knockdowns as each move gives.
- **Dodging:** by position only, never by colour. Each super says how below. Superposed THE BOX
  and TUNNEL's untouchable frames still dodge, as they dodge everything.
- **A K.O. by a super** gets the longest slow motion the game has (`KO_SLOW_FRAMES` doubled).
- **Both fire on the same frame:** p1's freeze plays, then p2's, and both moves run; whoever
  lands first, lands.
- **COPY can't catch a super,** and a super's shots and fields cancel nothing and are cancelled
  by nothing.

## 4. The seven supers

Frame counts are after the freeze. All "about" numbers are starting values for the build to
check against the bots and the look.

### ROBERT: BLOCH SPHERE

- A glowing wireframe Bloch sphere forms round him (three axes, an equator ring, the state
  arrow pointing to |0>), and he rolls across the floor inside it like a wrecking ball.
- Startup 8. Rolls forward 6 px a frame for up to 50 frames, or until it reaches the rival.
- The sphere is about 70 px across, sitting on the floor: **LOW**, so a jump clears it (every
  jump peaks at 150 px or more since the feel tuning). It hits every 6 frames: 4 hits of 4.
- It ends with an H-gate uppercut (9, knockdown): the sphere's arrow flips from |0> to |1>,
  and ROBERT switches basis with it, as HADAMARD DIVE does. Recovery 24.
- **Dodge:** jump over the sphere.

### BOHR: WAVEFUNCTION COLLAPSE

- He raises both arms and a shimmering probability cloud (a dotted wave, his colours) spreads
  across the whole floor.
- Startup 24: the cloud spreads. On its last frame it **locks** on the rival's x (a white ring
  flashes there).
- 12 frames later it collapses into a pillar of light on the locked spot, dots sucked inward:
  about 60 px wide, full height, **MID**, 25 and a knockdown. Recovery 30.
- **Dodge:** move after the lock. The pillar falls where the rival was when it locked, so a
  walk, dash or jump out of the ring escapes it.

### PHOEBE: COHERENT BEAM

- She plants her feet and fires one enormous laser straight forward, to the screen's edge.
- Startup 12, active 60, recovery 30. The beam runs from the floor to 110 px up, with
  scrolling interference fringes and a lens flare at her hands.
- It hits every 12 frames: 5 hits of 5.
- **Dodge:** be above it. It covers anyone standing or crouching; a jump whose feet are higher
  than 110 px passes over it (every jump's apex is 150 px or more).

### ERWIN: NINE LIVES

- He pops into THE BOX, and the box splits into a superposition of nine holographic ERWINs
  around the rival.
- Needs the rival within about 160 px when the box splits (startup 10); otherwise the ghosts
  pounce at nothing (a whiff).
- Eight ghost pounces, every 8 frames, from alternating sides, each a low dash: **LOW**, 2
  each. The ninth is the real ERWIN, a big swipe, MID, 9 and a knockdown. Recovery 30.
- **Dodge:** partly. The pounces come in a rhythm, so jumps timed to them make some miss;
  only a rival who takes all nine takes the full 25.

### DOS: BLUE SCREEN OF DEATH

The look is the user's pick from two mockups (2026-10-22): **variant B, then a blue flash.**
The mockup script is `2026-10-22-brawl-ket-superposition-bsod-look.py`, beside this spec (run it
from `brawl-ket/` with an output path; it draws variant A on the left, B on the right).

- **The crash:** startup 8. The stage stays as it is. A blue strip runs along the floor about
  200 px either side of DOS, his reach.
  - Every rival on the ground inside it is **frozen** for 40 frames: tinted blue-white, sliced
    into rows that jitter sideways.
  - A small classic error window pops up over the frozen rival's head: a grey title bar
    **FATAL EXCEPTION**, then white on blue `ROBERT.EXE has` / `stopped responding` (their
    name), and an **OK** button.
  - The freeze is a hold, like ION TRAP's: no damage, no push.
- **The drop:** DOS leaps and comes down on the frozen rival with a giant CRT DROP, landing on
  frame 40: 25, MID, a knockdown. The moment it lands, the **whole screen flashes BSOD blue
  for one frame**, then a white CRASH! burst.
- If no one was frozen, DOS does the leap and drop in place (a whiff).
- **Dodge:** be in the air when the screen strip appears, or further than 200 px away.
- Recovery 30, his long landing.
- It is also the BLUE SCREEN idea cut from his first kit (`2026-10-21-brawl-ket-erwin-dos-design.md`).

### M-CUTIE: DILUTION FRIDGE

- She points straight up, and a shadow appears under the rival and follows them.
- Startup 6. The shadow follows for 24 frames, then **locks**.
- 12 frames later a giant gold dilution refrigerator (her dress's chandelier, many times
  bigger, as on the SUPERCONDUCTOR stage) crashes down on the shadow:
  - the fridge: about 70 px wide, full height, **MID**, 20 and a knockdown;
  - a frosty shockwave rolls out 120 px either side: **LOW**, 5.
- Recovery 30.
- **Dodge:** walk out of the shadow after it locks, and jump the shockwave.

### ALICE & BOB: ONE-TIME PAD

- Needs the rival on the ground within about 100 px of Alice when it starts (startup 6);
  otherwise they flash and nothing happens (a whiff).
- On a catch the rival is held, as a throw holds, and both kids vanish and teleport to either
  side of them. They fling the key back and forth through the rival **six** times, 3 each,
  over about 60 frames.
- It ends with a giant padlock snapping shut on the rival, **CLICK**, for 7 and a knockdown.
  Alice and Bob end on either side of the rival.
- **Dodge:** stay out of its 100 px, or be in the air when it starts.
- Quantum key distribution: the key passes between Alice and Bob, and Eve (the rival) is
  caught in the middle.

## 5. Screens, sound, HUD

- **HUD:** the bar sits right under each health bar, on the player's side: two halves with a
  thin divider, filling outward; a full bar shines and blinks A+B!.
- **HOW TO PLAY card:** one more row under the buttons, **A+B  SUPER: FULL BAR** (the longer
  line didn't fit the card's controls box), A and B already lit.
- **CHOOSE YOUR FIGHTER:** each fighter's list gets a fourth row: `A+B  <SUPER NAME>`, its chip
  reading BOTH.
- **Sound:** none while it fills; a rising chord when a half fills and a bigger one when the
  bar is full; the freeze has its own hit; each super has its own sound (synthesized, as the
  rest of the game's).
- **Performance:** every full-screen layer (the darkening, the blue strip, the beam, the cloud)
  is drawn once and cached, as the stages are. A super frame must stay inside the Pi's budget
  (`tools/benchmark.py` gains a super for every fighter).

## 6. Bots

- The one Bot (`bot.py`) fires its super when its bar is full and the rival is where that
  super lands: in reach of ONE-TIME PAD and NINE LIVES, on the ground and in the BSOD strip,
  anywhere for WAVEFUNCTION COLLAPSE and DILUTION FRIDGE, ahead and grounded for COHERENT BEAM
  and BLOCH SPHERE.
- It tries to dodge a rival's super the way each section 4 says (jump the sphere and the
  beam, move after a lock, jump at the BSOD strip, back off from ONE-TIME PAD).
- To fill both halves it already switches (Y) now and then; it switches a little more while
  one half is full and the other isn't.
- CPU VS CPU and the title demo use all of this.

## 7. Balance

- The bar stays the same: no fighter wins more than about 60% against another, bots against
  bots (`tools/balance.py`, `tests/test_balance.py`).
- A super's numbers (damage, reach, timings) are the levers. The fill rate (`SUPER_HALF`) is
  one number for everyone.

## 8. Building it

- **Looks first.** As for the fighters, each super's look is drawn as a mockup over a real
  fight frame and shown to the user before it is built in. The BSOD's look is agreed
  (section 4); the six others need a sheet each (the freeze and call, and two or three beats of
  the move).
- **Engine:** the bar is fight state per player (`Fight`), filled where damage is applied. A
  super is a `Move` with `kind="super"` in each Character's `extra` (its look, its frame data,
  its twists as new Move fields where a twist is new: a lock-on, a rolling sphere, a hold then
  a drop, a beam). The freeze is a fight-level pause, like hitstop.
- **Tests:** the fill rules (both bases, DOS by colour, taken at half rate, the cap, carry
  over and reset), the A+B window (and that A and B alone are unchanged without a full bar),
  the freeze stopping everything, each super's hit, reach and dodge, that it hurts either
  colour, COPY and TELEPORT and THE BOX against it, a K.O. by a super, the bots firing and
  dodging, the HUD and the HOW TO PLAY card. The six older fighters' digest changes on purpose.
- **Attract reels:** they show the game as it was recorded; re-recording them with supers is
  a separate job.
