# Brawl-Ket: PHOEBE, the third fighter: design

ROBERT (fast and light) and BOHR (slow and heavy) both fight on the ground. PHOEBE
controls angles instead: the air above her, the ground below her when she jumps,
and where she stands. She is a scientist in a lab coat, and the first fighter who
isn't an armoured puppet.

Her name is Greek for "bright, shining", for her lasers. Like ROBERT, it's a real
first name rather than a scientist's.

Nothing in the v3 rules changes (`2026-10-02-brawl-ket-basis-design.md`): colour
must match to hurt, A is your colour, B the other, throws are Y, Y switches.
All her specials are her own colour, like everyone's.

## 1. The look

Approved on 2026-10-09 after several rounds. The reference is
`2026-10-09-brawl-ket-phoebe-look.py`, beside this spec: porting her into
`render.py` should reproduce its image.

She is drawn in the same toy language as ROBERT and BOHR: chunky capsule limbs with
an ink outline, on the same skeleton and poses. The build is new, `"toy"`:
- scale 2.1;
- slightly longer thighs, shins and arms;
- 12 px limbs;
- head radius 14.

**Her signature is a long coat**, open at the front, in her full basis colour. It
hangs almost to her ankles, by gravity rather than along her spine, and never goes
through the floor.
- **Movement:** the hem spreads with her stride and flares out behind her. A `flare`
  amount pushes it further back; in the game it follows her motion.
- **Drawing:** the coat is one shape. Its back panel and the open front panel
  share a single outline, with no seams or highlight streaks inside it.
- **Inside the coat:** a darker lining shows behind her.

**Under the coat** is a white shirt, which shows exactly where the coat hangs open.
Her trousers are a deep shade of her basis colour, so the whole figure reads as
green or purple.

**Neutral colours:**
- big white turned-back cuffs, the lab-coat cue;
- skin-tone hands and face;
- dark brown hair in a high ponytail that swings with her lean;
- two round lenses with a teal tint. The glasses' arm runs from the near lens's rim
  to her ear, under the lenses.

**Rejected along the way**, so a later change doesn't bring them back:
- realistic, thin proportions (they looked like another game);
- a coat in the basis colour over dark, neutral trousers (most of her didn't read);
- a short coat and split coat tails (they looked like a suit);
- a belt and sash (they looked like a ninja);
- a high popped collar;
- a white lapel strip;
- highlight lines across the coat.

**An attack's limb lights up in its colour**, as on ROBERT and BOHR. On her it is
the sleeve, or the trouser leg.

## 2. The fighter

| | ROBERT | BOHR | PHOEBE |
|---|---|---|---|
| Health | 100 | 115 | **95** |
| Walk | 2.2 | 1.5 | **1.9** |
| Jump | 12.0 / 0.5 (apex ~144 px) | 10.5 / 0.55 | **11.5 / 0.5 (apex ~132 px)** |
| Normals | fast | slow, long | **slow-ish, the longest reach** |
| Select screen trait | FAST AND LIGHT | SLOW AND HEAVY | **TALL AND TRICKY** |

Her normals are ROBERT's, tuned:
- one or two frames more startup;
- 6-10 px more reach;
- her jab and heavy are long pokes, Dhalsim-style.

She is the easiest fighter to hurt (95 health) and has no ground projectile.
**The way to beat her is to walk straight in on the ground**, BOHR's game.

## 3. Her specials

### X: OPTICAL TRAP (anti-air)

Laser beams cross in a column above her and slightly in front. It is an optical
trap: tweezers made of light.

- **Hitbox:** Box(-12, 136, 56, 150). It starts above the tallest standing hurtbox
  (BOHR's, at 132), so a grounded rival walks under it: **it only ever hits someone
  in the air.** This comes from the geometry alone; no new rule. Its height is MID.
- **Frames:**
  - startup 7, during which a thin aiming beam shows where the column will be;
  - active 10;
  - recovery 18.
- **Effect:** 10 damage and a knockdown, so an anti-air brings them down.
- **Cooldown:** 1.5 s.
- **What it answers:**
  - ROBERT's HADAMARD DIVE, BOHR's COLLAPSE and every jump-in. Only if her colour
    matches, of course: that's the guess.
  - The answer to the answer: stay on the ground.

### Down + X: TUNNEL (teleport)

She tunnels through the rival, as a particle tunnels through a barrier, and
re-forms on their far side.

- **Where she lands:** 50 px past the rival's x, on the far side, kept on the
  stage. If the rival is in the corner and there is no room behind them, she
  re-forms as far as the stage allows on the near side. She always ends facing the
  rival.
- **Frames:**
  - 10 frames to vanish: she flickers into scanlines, and is still hittable for the
    first 4;
  - 12 frames gone: no hurtbox at all, so shots and hits pass through;
  - 16 frames to re-form, hittable. This is the punish window for a rival who reads it.
- **Readability:** a dotted "tunnel" line along the floor from where she was to
  where she will be, shown from the first frame of the vanish. A rival who watches
  can turn around in time.
- **Cooldown:** 2.5 s. It does no damage; it is a movement tool (escaping the
  corner, crossing up, slipping through a PHOTON).

### Air X: LASER (diagonal)

She fires a laser down and forward at 45°, hanging in the air while she aims.

- **Hover:** for the startup and active frames her fall stops. That's flashy, and
  it fixes the shot's angle. Then she falls normally.
- **Frames:** startup 8, with a dotted aiming line along the diagonal to the floor.
- **The shot:** a projectile moving 7 px/frame on each axis, drawn as a short
  bright streak with a trail.
  - It ends on the floor with a small spark.
  - MID: a crouch doesn't duck a shot from above, so you get out of the way.
  - 8 damage, hitstun 16.
- **Limit:** once per jump. A PHOTON and a LASER that meet cancel each other, as
  shots already do.

This needs one engine change: **shots get a vertical speed** (`Shot.vy`,
`Projectile.vy`). Today they only fly level.

## 4. The CPU

The attract demo and the tests rely on the bot, so it learns her three tools:
- **OPTICAL TRAP** when the rival is in the air and within about 70 px across;
- **TUNNEL** when a shot is coming and too close to jump, or now and then at mid
  range to cross up;
- **LASER** from a jump at mid range, aimed so the diagonal meets the rival.

## 5. Screens and the rest

- **Select:** the roster becomes ROBERT, BOHR, PHOEBE; the stick cycles through
  all three. P1 still starts on ROBERT and P2 on BOHR.
- **Title:** it shows ROSTER[0] and ROSTER[-1], so PHOEBE will face ROBERT there.
- **Sounds:**
  - the trap: a rising hum;
  - the tunnel: a falling-then-rising shimmer;
  - the laser: a short zap.
- **Not changed:** the logo. It shows the core conflict, two fighters.
- **README:** a third column in the fighters table.

## 6. Tests

New tests:
- the frame data;
- OPTICAL TRAP never touches a grounded standing rival of any build, and hits a
  jumping one;
- TUNNEL lands on the far side, stays on the stage (the corner case included), turns
  her round, and makes her unhittable only in the gone frames;
- the LASER's path is 45°, it hovers, it fires once per jump, and it ends on the
  floor;
- shots with vy collide and cancel correctly;
- the bot uses all three specials, and bot-vs-bot rounds with PHOEBE finish.

## 7. Risks

- **Balance.** A teleport plus a strong anti-air can make her frustrating to fight.
  The levers are the TUNNEL cooldown, its 16 re-form frames, and the trap's
  recovery. Expect a playtest round.
- **Readability for newcomers.** The aiming lines and the tunnel line are the
  answer: nothing she does should come without a visible tell.
