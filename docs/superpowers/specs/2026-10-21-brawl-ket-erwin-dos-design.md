# Brawl-Ket: ERWIN and DOS, the fourth and fifth fighters: design

Two new fighters join ROBERT, BOHR and PHOEBE, chosen from a long list of ideas with the
user on 2026-10-21:

- **ERWIN**, Schrödinger's cat: quick and slippery. Her signature is THE BOX, a real
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
  and flat-shaded. She is about ROBERT's height, which is bigger than a real cat, as the
  user asked.
  - She is on the shared skeleton and poses, with a new `"cat"` build.
  - **Cat legs:** the hip, knee and foot joints come from `poses.joints` as for everyone,
    and a hock is added between the knee and the foot, pushed back off that line. So each
    leg reads thigh forward, long lower leg back, heel high, standing on the toe pads.
    Every shared pose still works, and the crouch reads as a sitting cat.
- **Fur:** her basis colour, so the whole figure reads green or purple. The belly, muzzle
  and inner ears are a paler shade of it.
- **Accents:** big amber slit-pupil eyes (her one warm accent, like BOHR's gold), a pink
  nose, an ink "w" mouth and white whiskers. Her hands and feet are round paws. Her tail
  is a question mark with a pale tip, coming off the hip.
- **The lit limb:** an attack's arm or leg lights up in its colour, as on everyone.
- **THE BOX:**
  - **Superposed:** two holographic cardboard boxes in her basis colour, each with her ears
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
- **BLUE SCREEN:** his screen face turns blue (a crash). The shockwave ring is drawn in his
  green, the move's colour, so the colour rule stays readable.
- **Rejected:** a CRT head on BOHR's heavy puppet body. It read as a generic fighter; the
  all-in-one is the better joke.

## 2. ERWIN, quick and slippery

| | |
|---|---|
| Health | 90, the lowest |
| Walk | 2.3 (ROBERT 2.2) |
| Jump | the highest (`jump_vy` about 12.5) |
| Normals, throws, Y | shared with everyone, as on ROBERT, BOHR and PHOEBE |
| Her weakness | the least health, and THE BOX is a gamble |

### X: THE BOX (her colour, 3 s cooldown)

1. **Superposition.** She ducks into a box, and it splits into two holographic boxes:
   - **Box 1** stands where she stood.
   - **Box 2** stands 120 px towards the rival, clamped to the stage. So it can land
     behind a rival who is close.

   While superposed she has no body: only the two boxes can be touched.

2. **She collapses herself** with any new stick direction or button press after the
   move's startup, or after 1.5 s at the latest.
   - She lands in a **random box, 50/50**.
   - She pops out of it with a quick swipe: MID, 8 damage, her colour, short range.

3. **The rival collapses her** whenever anything that would hit her touches either box:
   a strike's hitbox, a projectile, a throw's reach or CHARGE NOISE's field. That is a
   measurement, and it is 50/50:
   - **She is in that box:** she is there, and the attack resolves against her as normal.
     The colour rule still applies, so a wrong-colour attack bounces off her as usual.
   - **She is in the other box:** the attack finds nothing (it whiffs, and a projectile
     flies on). She appears in the other box, free to act at once, with no swipe.

4. **Afterwards:**
   - The cooldown runs from the collapse.
   - Y still works while she is superposed, as in any state: the boxes change colour with
     her basis.
   - The rival and the clock carry on as normal.

**Randomness.** `fight.py` has been pure and deterministic. The box needs a seeded random
source: a `Fight` takes a `seed` (default 0) and owns a `random.Random(seed)`. The same
inputs and the same seed always give the same round. `Match` passes a seed from its own
rng, and the tests fix it.

### Down + X: POUNCE (her colour, 2 s cooldown)

- A long, low leap forward along an arc, which hits on the way: MID (a crouch doesn't
  save the rival), 10 damage and a knockdown.
- A long landing recovery (about 20 frames) makes it punishable when blocked or missed.

### Air X: SCRATCH (her colour, once per jump)

- She hangs in the air (like PHOEBE's LASER `hover`) and claws three times in front of her:
  `hit_every`, 4 damage each, MID.
- Then she falls on.

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
    beams, strikes or fields.
  - A COPY that catches nothing leaves him in about 0.3 s of recovery, so he can't hold it
    up.
- **PASTE** (when his clipboard holds something):
  - Y fires the stored projectile from his drive slot, **straight ahead** at its own speed.
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

### Down + X: BLUE SCREEN (his colour, 3 s cooldown)

- His face turns blue, and a crash shockwave rings out about 50 px around him.
- It is MID, so it can't be ducked; someone high in a jump is out of its reach. It deals 6
  damage and a long stun, about 0.6 s, and pushes the rival away.
- It is his "get off me" move, since he is big and slow.

### Air X: CRT DROP (his colour, once per jump)

- A fast, straight-down stomp: MID, 12 damage and a knockdown.
- Unlike BOHR's drifting COLLAPSE, it has no shockwave. Its landing recovery (about 20
  frames) makes it punishable when it misses.

## 4. Interactions worth pinning down

| Situation | Result |
|---|---|
| PHOTON / LASER / FLOPPY into a box | a measurement: 50/50 hit or fly on |
| A throw or MEASURE in reach of a box | a measurement; if she is there, she is thrown (MEASURE also collapses her basis) |
| CHARGE NOISE over a box | its first shock measures; later shocks hit her as a body |
| PHOEBE's TUNNEL past a superposed ERWIN | TUNNEL places PHOEBE past the rival's x; for a superposed ERWIN that x is box 1's |
| DOS COPY against FLOPPY | caught, and pasted back as a green floppy |
| DOS against HADAMARD DIVE | the dive switches ROBERT, the attacker, as before; DOS is unaffected |
| DOS paste into a box | a measurement, like any projectile |

## 5. Screens and HUD

- **CHOOSE YOUR FIGHTER:** the order is ROBERT, BOHR, PHOEBE, ERWIN, DOS, paged with
  `< >` as now.
  - ERWIN: "QUICK AND SLIPPERY", with her specials THE BOX, POUNCE and SCRATCH, each marked
    YOURS.
  - DOS: "SLOW AND CLASSICAL". The line "Y SWITCHES YOUR COLOUR" reads "Y: COPY, THEN
    PASTE" and "ALWAYS GREEN" for him. His specials are FLOPPY, BLUE SCREEN and CRT DROP.
- **HUD:** DOS's clipboard is a small icon next to his A/B chips. It is empty, or shows the
  stored projectile's tiny sprite in its colour. ERWIN needs nothing extra.
- **HOW TO PLAY:** unchanged. It teaches the colour rule with ROBERT and BOHR, which still
  holds. DOS's exception is on his select panel.
- **Sounds:** new cues from the existing chiptune palette for the box splitting, the
  collapse, POUNCE, SCRATCH, FLOPPY, BLUE SCREEN, CRT DROP, COPY and PASTE.

## 6. Bots

`bot.py` learns both fighters, and these bots also play the title demo, whose fighters are
picked at random.

- **ERWIN:** she boxes when a projectile or a heavy is coming, pounces at crouchers, and
  scratches against jumpers.
- **DOS:** he COPYs incoming projectiles, PASTEs at once, FLOPPYs at range, BLUE SCREENs
  when the rival is close, and CRT DROPs on rivals below him.

**Balance check:** bot against bot over many seeds, for every pair of the five fighters.
No fighter may win more than about 60% against another, the bar the existing three are held
to.

## 7. Testing

- **THE BOX:**
  - the split positions, including the clamp at a wall;
  - with seeds that pick each box: a strike, a projectile and a throw against the box she
    is in (she is hit or thrown) and against the other one (a whiff, she appears free);
  - the colour rule against a box (a wrong colour bounces);
  - her own collapse (an input, or the 1.5 s timeout) with the swipe;
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
  - FLOPPY, BLUE SCREEN and CRT DROP as move data (damage, height, knockdown, cooldown).
- **Select screen and HUD:** all five fighters can be picked, and DOS's panel text and
  clipboard icon appear.
- **Bots:** every pair over seeds; the 60% bar.
- **Snapshots:** both fighters' poses and moves, the box superposed and collapsing, COPY,
  PASTE, FLOPPY, BLUE SCREEN, and the select panels. Checked by eye against the look
  scripts.
- **Benchmark:** the holographic boxes and the disk stay within the Pi's frame budget
  (Brawl-Ket ran at about 3-4 ms a frame on the cabinet).
