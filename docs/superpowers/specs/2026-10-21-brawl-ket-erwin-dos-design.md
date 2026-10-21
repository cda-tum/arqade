# Brawl-Ket: ERWIN and DOS, the fourth and fifth fighters: design

Two new fighters join ROBERT, BOHR and PHOEBE, chosen from a long list of ideas with the
user on 2026-10-21:

- **ERWIN**, Schrödinger's cat: quick and slippery. His signature is THE BOX, a real
  superposition of two places that a measurement collapses at random.
- **DOS**, a classical computer: slow and classical. He is the one fighter who breaks the
  colour rule on purpose. A classical bit can't be in superposition, so he is always green.
  His Y copies a rival's projectile instead of switching basis.

The cat is named after Schrödinger (the cat named after its owner). DOS is named after the
old operating system, which matches his green phosphor screen and floppy disks.

Nothing else in the v3 rules (`2026-10-02-brawl-ket-basis-design.md`) changes:
- colour must match to hurt;
- A is your colour and B the other;
- throws are Y and hurt either colour;
- every special is in your own colour.

The only exception is DOS's Y and his fixed basis, in section 3.

Later fighters from the same list, not part of this spec: a noise ghost (it forces the
rival's colour and locks it), a hardware-modality fighter (ion trap, spin jump, a
Grover-style microwave pulse), ALICE & BOB and a QEC knight.

## 1. The looks

Both were approved on 2026-10-21, from two rounds of mockups. The references are the
scripts beside this spec. Run them from `brawl-ket/`; porting each fighter into
`render.py` should reproduce its sheet.

- `2026-10-21-brawl-ket-erwin-look.py`
- `2026-10-21-brawl-ket-dos-look.py`

### ERWIN

- **Build:** an upright cat in the same toy language as the others: chunky, ink-outlined
  and flat-shaded. He is about ROBERT's height, which is bigger than a real cat, as the
  user asked.
  - He is on the shared skeleton and poses, with a new `"cat"` build.
  - **Cat legs:** the hip, knee and foot joints come from `poses.joints` as for everyone,
    and a hock is added between the knee and the foot, pushed back off that line. So each
    leg reads thigh forward, long lower leg back, heel high, standing on the toe pads.
    Every shared pose still works, and the crouch reads as a sitting cat.
- **Fur:** his basis colour, so the whole figure reads green or purple. The belly, muzzle
  and inner ears are a paler shade of it.
- **Accents:** big amber slit-pupil eyes (his one warm accent, like BOHR's gold), a pink
  nose, an ink "w" mouth and white whiskers. His hands and feet are round paws. His tail
  is a question mark with a pale tip, coming off the hip.
- **The lit limb:** an attack's arm or leg lights up in its colour, as on everyone.
- **THE BOX:**
  - **Superposed:** two holographic cardboard boxes in his basis colour, each with his ears
    and eyes over the rim. They are see-through, with scanline gaps and a slight sideways
    shimmer, and each stands in a pale pool of light. A dashed arc joins them: one cat, two
    places.
  - **Collapse:** the chosen box turns into real cardboard (neutral brown, a tape strip,
    "this side up" arrows) in a white flash with rays. The other one dissolves in a dither.
- **Rejected along the way:**
  - a four-legged, panther-sized cat: every move would need new animation, and it was too
    wide for the stage;
  - straight human legs: they looked like a cat-person;
  - one real box with two ghost cats as its possible spots: the user preferred two
    holographic boxes.

### DOS

- **Build:** a walking all-in-one computer, Mac-like, seen in 3/4 view: a front, a side, a
  top and a carry grip on top. The top of the case is level with ROBERT's head.
- **Face and case:** the screen is his face, in green phosphor pixels on dark glass with
  scanlines and a glare, with an angry variant for attacks. A floppy slot and vents sit
  below the screen.
- **Limbs:** stubby ribbed puppet arms come out of the case's sides, below the screen, so
  his fists never cover it. His fists are beige keycap blocks and his boots dark green.
- **Movement:** the case leans only a fraction (`CASE_TILT`) of each pose's lean, so in a
  crouch or a jump the legs do the work and the box stays upright.
- **Colour:** the whole case is green, a phosphor green that reads as clearly as ROBERT's.
  It never turns purple. His lit limbs show only on his purple (B) moves; his green moves
  light up green on a green body, which is fine.
- **FLOPPY:** a 3.5" disk like the classic save icon: a steel shutter with its window, a
  white label with two blue biro lines, a chamfered corner and a write-protect hole. It is
  in the move's colour with a white rim, spin silhouettes and speed lines, and it comes out
  of his drive slot.
- **MOUSE CABLE:** the mouse, in his colour, slides along the floor on a cable back to his front.
- **Rejected:** a CRT head on BOHR's heavy puppet body. It read as a generic fighter; the
  all-in-one is the better joke.

## 2. ERWIN, quick and slippery

| | |
|---|---|
| Health | 90, the lowest |
| Walk | 2.3 (ROBERT 2.2) |
| Jump | the highest (`jump_vy` about 12.5) |
| Normals, throws, Y | shared with everyone, as on ROBERT, BOHR and PHOEBE |
| His weakness | the least health, and THE BOX is a gamble |

### X: THE BOX (his colour, 3 s cooldown)

1. **Superposition.** He ducks into a box, and it splits into two holographic boxes:
   - **Box 1** stands where he stood.
   - **Box 2** stands 120 px towards the rival, clamped to the stage. So it can land
     behind a rival who is close.

   While superposed he has no body: only the two boxes can be touched.

2. **He collapses himself** with any new stick direction or button press after the
   move's startup, or after 1.5 s at the latest.
   - He lands in a **random box, 50/50**.
   - He pops out of it with a quick swipe: MID, 8 damage, his colour, short range.

3. **The rival collapses his** whenever anything that would hit his touches either box:
   a strike's hitbox, a projectile, a throw's reach or CHARGE NOISE's field. That is a
   measurement, and it is 50/50:
   - **He is in that box:** he is there, and the attack resolves against him as normal.
     The colour rule still applies, so a wrong-colour attack bounces off him as usual.
   - **He is in the other box:** the attack finds nothing (it whiffs, and a projectile
     flies on). He appears in the other box, free to act at once, with no swipe.

4. **Afterwards:**
   - The cooldown runs from the collapse.
   - Y still works while he is superposed, as in any state: the boxes change colour with
     his basis.
   - The rival and the clock carry on as normal.

**Randomness.** `fight.py` has been pure and deterministic. The box needs a seeded random
source: a `Fight` takes a `seed` (default 0) and owns a `random.Random(seed)`. The same
inputs and the same seed always give the same round. `Match` passes a seed from its own
rng, and the tests fix it.

### Down + X: POUNCE (his colour, 2 s cooldown)

- A long, low leap forward along an arc, which hits on the way: MID (a crouch doesn't
  save the rival), 10 damage and a knockdown.
- A long landing recovery (about 20 frames) makes it punishable when blocked or missed.

### Air X: BOX DROP (his colour, once per jump)

- He lets a little cardboard box fall from the air, just in front of him. It's a projectile:
  it falls straight down (drifting half a pixel a frame forward) and ends on the floor. MID,
  8 damage.
- Being a shot, DOS can COPY it; his PASTE then sends it flying level.

## 3. DOS, slow and classical

| | |
|---|---|
| Health | 125, the most |
| Walk | 1.6 |
| Jump | the lowest (`jump_vy` about 10.0) |
| Basis | **always Z (green)** |
| Normals and throws | shared with everyone (A his own colour, so always green; B purple; throws hurt either colour) |
| Y | COPY / PASTE, not a switch |
| His weakness | a rival only ever needs green attacks against him |

### Always green

A classical bit can't be in superposition, so his basis never changes:
- His Y doesn't switch.
- BOHR's MEASURE still grabs and hurts him, but doesn't collapse him into BOHR's basis.
- Any later colour-changing move does nothing to him either.

His badge always shows `0/1`, and his A/B chips are always green and purple.

### Y: COPY / PASTE

- **COPY** (when his clipboard is empty):
  - Y opens a catch window of about 0.2 s, drawn as a `CTRL+C` frame in front of him.
  - A rival projectile whose box meets the window is caught: it disappears and goes into
    his **clipboard**. That covers PHOTON, LASER, FLOPPY and any later projectile, but not
    beams or strikes.
  - It also catches BOHR's crackling CHARGE NOISE: the field stops, and the clipboard holds it.
  - A COPY that catches nothing leaves him in about 0.3 s of recovery, so he can't hold it
    up.
- **PASTE** (when his clipboard holds something):
  - Y fires the stored projectile from his drive slot, **straight ahead** at its own speed, or
    at 4 px a frame if that is faster (a falling box has next to no speed across).
  - A stored CHARGE NOISE is not fired: he crackles with it himself, for its full second, in
    the colour it was copied in.
    A LASER caught from above flies horizontally.
  - It keeps **the colour it was fired in**: a purple PHOTON comes back purple. The stored
    colour is the shot's absolute basis, not "own" or "other".
  - Short startup and recovery, and the clipboard is empty again.
- **When it works:** COPY and PASTE start only when he is free to act. He can't use them in
  hitstun or knocked down, unlike everyone else's Y, which works in any state.
- **The clipboard:** one item, emptied at the start of each round.

### X: FLOPPY (his colour, 2.5 s cooldown)

- A spinning floppy disk from his drive slot: 9 damage, and slower than PHOTON (about
  3 px a frame; PHOTON flies at 4).

### Down + X: MOUSE CABLE (his colour, 3 s cooldown)

- He flings his mouse out along the floor on its cable: a LOW projectile (a jump clears it),
  reaching about 180 px. Whoever it touches is reeled in to just in front of him, whether it
  hurt them or bounced off; the colour rule still decides the damage (6) and the stun.
- He stays planted while the mouse is out, and being hit cuts the cable.
- A pull from far away leaves the rival stunned long enough for his jab to combo; at point
  blank it leaves him only a little ahead.

### Air X: CRT DROP (his colour, once per jump)

- A fast, straight-down stomp: MID, 12 damage and a knockdown.
- Unlike BOHR's drifting COLLAPSE, it has no shockwave. Its landing recovery (about 20
  frames) makes it punishable when it misses.

## 4. Interactions worth pinning down

| Situation | Result |
|---|---|
| PHOTON / LASER / FLOPPY into a box | a measurement: 50/50 hit or fly on |
| A throw or MEASURE in reach of a box | a measurement; if he is there, he is thrown (MEASURE also collapses his basis) |
| CHARGE NOISE over a box | its first shock measures; later shocks hit him as a body |
| PHOEBE's TUNNEL past a superposed ERWIN | TUNNEL places PHOEBE past the rival's x; for a superposed ERWIN that x is box 1's |
| DOS COPY against FLOPPY | caught, and pasted back as a green floppy |
| DOS COPY against BOX DROP | caught, and pasted back flying level |
| DOS COPY against CHARGE NOISE | BOHR's field stops; PASTE makes DOS crackle in its colour |
| DOS against HADAMARD DIVE | the dive switches ROBERT, the attacker, as before; DOS is unaffected |
| DOS paste into a box | a measurement, like any projectile |

## 5. Screens and HUD

- **CHOOSE YOUR FIGHTER:** the order is ROBERT, BOHR, PHOEBE, ERWIN, DOS, paged with
  `< >` as now.
  - ERWIN: "QUICK AND SLIPPERY", with his specials THE BOX, POUNCE and BOX DROP, each marked
    YOURS.
  - DOS: "SLOW AND CLASSICAL". The line "Y SWITCHES YOUR COLOUR" reads "Y: COPY, THEN
    PASTE" and "ALWAYS GREEN" for him. His specials are FLOPPY, MOUSE CABLE and CRT DROP.
- **HUD:** DOS's clipboard is a small icon next to his A/B chips. It is empty, or shows the
  stored projectile's tiny sprite in its colour. ERWIN needs nothing extra.
- **HOW TO PLAY:** unchanged. It teaches the colour rule with ROBERT and BOHR, which still
  holds. DOS's exception is on his select panel.
- **Sounds:** new cues from the existing chiptune palette for the box splitting, the
  collapse, POUNCE, BOX DROP, FLOPPY, MOUSE CABLE, CRT DROP, COPY and PASTE.

## 6. Bots

`bot.py` learns both fighters, and these bots also play the title demo, whose fighters are
picked at random.

- **ERWIN:** he boxes when a projectile or a heavy is coming, pounces at crouchers, and
  jumps at rivals to drop a box on them.
- **DOS:** he COPYs incoming projectiles and BOHR's field, PASTEs (a field only up close),
  FLOPPYs at range, reels in rivals with MOUSE CABLE and follows the pull with a strike, and
  CRT DROPs on rivals below him.

**Balance check:** bot against bot over many seeds, for every pair of the five fighters.
No fighter may win more than about 60% against another, the bar the existing three are held
to.

## 7. Testing

- **THE BOX:**
  - the split positions, including the clamp at a wall;
  - with seeds that pick each box: a strike, a projectile and a throw against the box he
    is in (he is hit or thrown) and against the other one (a whiff, he appears free);
  - the colour rule against a box (a wrong colour bounces);
  - his own collapse (an input, or the 1.5 s timeout) with the swipe;
  - the cooldown from the collapse;
  - Y while superposed;
  - the same seed giving the same round.
- **DOS:**
  - Y never switches him;
  - MEASURE hurts him without collapsing him;
  - COPY catches a PHOTON (and a LASER), and the shot is gone;
  - PASTE fires it straight ahead in its original colour and empties the clipboard;
  - a missed COPY's recovery;
  - COPY not usable in hitstun;
  - the clipboard cleared at a new round;
  - FLOPPY, MOUSE CABLE and CRT DROP as move data (damage, height, knockdown, cooldown).
- **Select screen and HUD:** all five fighters can be picked, and DOS's panel text and
  clipboard icon appear.
- **Bots:** every pair over seeds; the 60% bar.
- **Snapshots:** both fighters' poses and moves, the box superposed and collapsing, COPY,
  PASTE, FLOPPY, MOUSE CABLE, COPY and PASTE of CHARGE NOISE, and the select panels. Checked by eye against the look
  scripts.
- **Benchmark:** the holographic boxes and the disk stay within the Pi's frame budget
  (Brawl-Ket ran at about 3-4 ms a frame on the cabinet).

## 8. After the first playtest (2026-10-21)

- **ERWIN is a he.**
- **SCRATCH is gone; BOX DROP replaces it.** SCRATCH clawed only a small box in front of
  him while he hung in the air, and in play it hardly ever connected.
- **BLUE SCREEN is gone; MOUSE CABLE replaces it.** Players couldn't tell what BLUE SCREEN
  was for. The mouse also fixes his real problem as the slowest fighter: getting close.
- **CRT DROP's box** grew from 48 x 40 px to 88 x 64: it missed rivals right beside him.
- **COPY** also catches ERWIN's box and BOHR's CHARGE NOISE, since projectiles alone came
  up too rarely. ROBERT's PHOTON and PHOEBE's LASER stay as they were.
- The bots learnt the new moves (DOS follows a pull with a strike); every pairing with ERWIN
  or DOS stays within the 60% bar.

