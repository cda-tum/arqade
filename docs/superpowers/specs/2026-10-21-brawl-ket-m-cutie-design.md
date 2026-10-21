# Brawl-Ket: M-CUTIE, the sixth fighter: design

M-CUTIE is the hardware fighter from the 2026-10-21 brainstorm (`2026-10-21-brawl-ket-erwin-dos-design.md`
lists her among the later fighters). Her three specials are three ways quantum computers are
built: a superconducting chip's microwave drive, an ion trap and a spin qubit.

- **Her name** sounds like "MQT", the Munich Quantum Toolkit: the group's own toolkit as a
  fighter. She is female-coded.
- **Names the user turned down:** CHIP, MONA, IONA and HARDY (puns on hardware words).

Nothing in the v3 rules (`2026-10-02-brawl-ket-basis-design.md`) changes:
- colour must match to hurt;
- A is your colour and B the other;
- throws are Y and hurt either colour;
- every special is in her own colour;
- her Y switches her colour, as everyone's does.

Her controls are everyone's: X, down + X and air X. Up + X was considered for SPIN and dropped,
because one fighter with a fourth special input would undo the shared controls (playtests found
learning the controls is the biggest hurdle).

## 1. The look

Approved on 2026-10-21: variant **B, the cage**, with B's own face. The reference is
`2026-10-21-brawl-ket-m-cutie-look.py`, beside this spec (run it from `brawl-ket/`). Its sheet
also draws variant A, kept for the record. Porting her into `render.py` should reproduce B.

- **Build:** a cute android on the shared human skeleton, in a new `"cutie"` build. She is a
  little shorter than PHOEBE in the body and legs, with head radius 15 and 12 px limbs.
- **Body:** her basis colour, so she reads green or purple at a glance, with pale ball joints
  at the elbows and knees (doll joints). She has puffed sleeves, gold wrist cuffs and dark
  shoes with a gold strap.
- **The chandelier skirt is an open hoop cage:**
  - three gold hoops, drawn as ellipses, on gold rods at the sides, with coax lines between
    them and a short coax fringe with gold tips at the hem;
  - her colour fills the cage, brightest down the middle like the fridge's chamber light;
  - her legs are drawn between the back and front halves of the hoops, so crouch, jump and
    kicks show through it;
  - it hangs straight down from the waist, shifting a little towards the knees, so it never
    tips with the body.
- **Head:**
  - coiled-coax buns, each with an ion-trap clip (two gold prongs and a glowing ion, which
    reads as a bow) and a gold plug hanging from it, as twin tails;
  - a shell head with a dark glass face, soft glowing LED eyes and blush lights.
- **An attack's limb lights up in its colour,** as on everyone. The heavy hit lights the
  whole front arm, sleeve included.
- **Her specials, as drawn on the sheet:**
  - **AMPLITUDE AMPLIFICATION:** while charging, a halo of her colour round her outline,
    glowing hands, and one lit diamond pip per step above her head. The wave is a microwave
    drive pulse (a Gaussian envelope with the carrier swinging inside), standing on the floor
    with a pool of light and speed lines, as tall as its step.
  - **ION TRAP:** a dark chip base, two gold electrodes and the ion between them. Arming is
    dim (shaded electrodes, a dark ion); armed lights the ion, the electrode tips and the
    field arcs round it.
  - **SPIN:** the front leg straight out, the skirt flattened and widened, whirl rings behind
    and in front of her, and faint copies of the leg sweeping behind.
- **Rejected:**
  - Variant A, a skirt of three solid gold plates: at game scale it read as a lampshade.
  - An engineer girl in a lab: too close to PHOEBE, a second human scientist.
  - A qubit-chip mascot: too far from the human skeleton, as ERWIN's first legs were.

## 2. The fighter

| | |
|---|---|
| Health | 105, in the middle |
| Walk | 1.8, a little slower than ROBERT |
| Jump | in the middle (`jump_vy` about 11.5) |
| Normals and throws | shared with everyone |
| Y | switches her colour |
| Her role | the set-up fighter: she traps the floor, charges a wave and spins across the air |
| Her weakness | setting up takes time: she stands still while she charges, and her traps take a moment to arm. A rival who rushes her before she is ready wins. |

Her game plan in one line: trap the floor so the rival has to jump, then SPIN or a big wave
catches them in the air.

### X: AMPLITUDE AMPLIFICATION (her colour, 2 s cooldown after it fires)

Grover's algorithm amplifies an amplitude step by step; here every press is a step.

- **The charge:** the first X starts it, and each further X press grows the wave by one step,
  up to 6. She stands still while charging, glowing a little more with every step.
- **It fires** about 0.25 s after her last press, or at once on reaching 6 steps. The wave
  travels straight ahead, a little slower than ROBERT's PHOTON (about 3.5 px a frame against
  4).
- **Bigger is taller and harder:**

  | Steps | 1 | 2 | 3 | 4 | 5 | 6 |
  |---|---|---|---|---|---|---|
  | Height (px) | 20 | 28 | 36 | 44 | 52 | 60 |
  | Damage | 7 | 8 | 10 | 11 | 13 | 15 |

  The wave runs along the floor and grows upward from it, so a small one can be jumped and a
  big one hardly. Its height is MID: a crouch never ducks it.
- **Hit while charging, the charge is lost** (it never fires). That's the risk for the reward.
- **On screen:** the name shows in full where it fits; where it doesn't (the select screen's
  move list holds about 21 letters), it reads "AMP. AMPLIFICATION".
- **Simpler than Grover on purpose:** the real amplitude peaks and then falls if you over-iterate.
  A "sweet spot" version was offered and the user chose "keeps growing", as easiest to
  understand.

### Down + X: ION TRAP (her colour, 1 s cooldown)

- **She sets a small trap on the floor,** about 70 px in front of her: two electrodes with a
  glowing ion between them, in her colour.
- **It arms after about 0.3 s,** so it can't be used as a point-blank attack. Unarmed, it is
  drawn dim.
- **When a rival on the ground steps into it,** it closes round them and holds them in place
  for about half a second, with 4 damage if the colour matches.
  - A wrong-colour trap still holds them, but doesn't hurt: as with DOS's MOUSE CABLE, the
    colour decides the damage, not the effect.
  - The trap is then used up.
- **A jump clears it.** The trap only catches someone on the ground.
- **At most two at once:** a third replaces the oldest. Traps vanish at the end of a round,
  after 10 s, or when she is knocked down.

### Air X: SPIN (her colour, once per jump)

Like Ryu's hurricane kick, and named for spin qubits.

- **She stops falling and spins forward at her current height,** about 100 px, one leg out and
  the chandelier skirt whirling.
- **It hits up to three times,** 4 damage each, MID (her body in the air: no ducking it).
- **Then she drops normally.** A miss lands into a short recovery.

## 3. Interactions worth pinning down

| Situation | Result |
|---|---|
| DOS COPY against her wave | caught like any shot; PASTE fires it back at the size it was caught |
| Her wave meets a PHOTON, FLOPPY or LASER | they cancel, as shots of different owners do, whatever the wave's size |
| A trap under a superposed ERWIN | it closes on a box: a measurement, 50/50, as any attack touching a box |
| PHOEBE's TUNNEL across a trap | while PHOEBE is gone she has no body, so the trap stays armed |
| DOS's MOUSE CABLE pulls a rival over a trap | the trap catches them if they end up standing in it |
| BOHR's MEASURE on her | it collapses her colour, as on anyone |

## 4. Screens, HUD and sounds

- **CHOOSE YOUR FIGHTER:** the sixth portrait starts the grid's second row (`ROSTER_COLS = 5`).
  Her trait reads "PATIENT AND TECHNICAL"; her specials list AMP. AMPLIFICATION, ION TRAP and
  SPIN.
- **The charge:** shown on her (the glow growing step by step), and as a small number of pips
  above her head while she charges, so both players can see the size coming.
- **Traps:** drawn on the floor in her colour, dim while arming, lit once armed.
- **Sounds:**
  - a rising blip for each charge step (pitch goes up a step each time);
  - a whoosh when the wave fires, deeper the bigger it is;
  - a click and a hum when a trap is set, and a snap when it closes;
  - a whirr for SPIN.

## 5. Bots

`bot.py` learns her, and the bot also plays her in the title demo:
- **AMPLITUDE AMPLIFICATION:** at range, mash for a random 2 to 6 steps, then let go.
- **ION TRAP:** set one when the rival is far and fewer than two are down, more often when the
  rival likes to walk in.
- **SPIN:** jump towards a rival at mid range and spin into them.
- **Balance:** her pairings are held to the 60% bar (`tests/test_balance.py`, `tools/balance.py`),
  as ERWIN's and DOS's are.

## 6. Engine notes

Three things the engine doesn't do yet:
- **A charged move:** a "charging" state with a step counter that grows on each X edge, fires
  after 15 frames without one or at the cap, and is lost on a hit. The fired shot's box and
  damage come from its step.
- **Traps:** a new kind of object in `Fight`, beside shots: placed, arming, armed, closed. One
  owner, at most two each, cleared per round. A closed trap applies a hold (hitstun with no
  knockback, the rival kept in place) through the normal colour rule.
- **SPIN:** a hover (as LASER) with a forward speed (as a lunge) and repeating hits (as CHARGE
  NOISE's `hit_every`); mostly a combination of existing move fields.

## 7. Testing

- **The charge:** steps grow on presses, cap at 6, fire after the pause or at the cap; the
  height and damage table; a hit while charging loses it.
- **The wave:** its speed, its colour fixed when it fires, cancelling other shots, DOS copying
  it and pasting it at its size.
- **The trap:** arming time, catching a grounded rival and holding them, damage only on the
  matching colour, a jump clearing it, the two-trap limit replacing the oldest, clearing at a
  new round and after 10 s, a box measurement on ERWIN.
- **SPIN:** hover and forward travel, up to three hits, once per jump.
- **The usual:** the move data, every slot present, poses, the select screen with six fighters,
  bots using all three specials, rounds finishing, the 60% bar, and the frame budget.
