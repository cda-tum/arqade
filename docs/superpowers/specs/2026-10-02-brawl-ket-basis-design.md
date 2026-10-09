# Brawl-Ket v3: the basis fighter: design

This replaces the rules of `2026-10-02-brawl-ket-shor-design.md` (v2) and, before it,
`2026-10-01-brawl-ket-design.md` (v1). Both built a fighter's health on an
error-correcting code, a repetition code and then Shor's code. Playtests found both
unintuitive: even knowing the codes, it was hard to tell what a hit would do. v3
drops error correction entirely.

- **Health is a plain bar.** A hit that lands costs health.
- **The quantum idea is one visible rule:** each fighter is in a measurement basis,
  shown by their body colour, and only an attack of the matching colour hurts them.

What stays from v2:
- **The engine:** the fixed 60 Hz simulation, puppets, match flow, sound and deploy.
- **The controls:** stick, A, B, X and Start, plus **Y** for the basis switch.
- **v2's feel work:**
  - instant crouching;
  - crouching ducks HIGH moves and jumping clears LOW ones;
  - fast heavies with no telegraph;
  - the reworked DIVE, GRAB and COLLAPSE physics;
  - knockdown that a second hit in the same frame can't undo.
- **The format and fighters:** both fighters' looks, versus only, best of 3, 60 s rounds.

## 1. Rules

### Bases and colours

Every fighter is in one of two bases at all times. The basis is shown by the
**colour of the whole body**:

| Basis | States | Colour | Hurt by |
|---|---|---|---|
| Z basis | \|0>, \|1> | green | X, which flips \|0> and \|1> |
| X basis | \|+>, \|-> | purple | Z, which flips \|+> and \|-> |

This is exact. X has \|+> and \|-> as its eigenstates, so it leaves an X-basis
fighter unchanged; Z leaves \|0> and \|1> unchanged. **An attack is drawn in the
colour of the basis it affects:** green attacks are X, purple attacks are Z. The rule
a player reads is one line: **colour must match to hurt.**

### Which colour each attack is

- **A** is always in **your own** basis colour.
- **B** is always in the **opposite** colour.
- **Specials** have their own fixed colour or twist (section 2).
- **Throws** are **Y = iXZ**. Y flips both bases, so a throw hurts whatever your
  colour. That is the exact answer to a player who keeps switching. Throws stay
  short-range and slow.

So against a rival of your colour, A hurts; against the other colour, B hurts. The
attacker always has one button that works, and the defender's switch changes which.

### Matching and wrong-colour hits

- **Matching colour:** damage, hitstun and knockback as in any fighter.
- **Wrong colour:** no damage. That part is the physics: the state is unchanged. On
  top of it comes a small pushback and a few frames of block-stun, so a wrong guess
  still costs the attacker time and position. The pushback and block-stun are a
  `GAME RULE:` and are labelled as such in the code.

### Switching basis: Y is a Hadamard

- **Y** applies H to yourself, which maps the Z basis onto the X basis and back. The
  body colour swaps at once.
- **Recovery:** the switch has **10 frames of recovery** during which you can't
  attack. You can move, crouch and be hit, and from the switch's first frame a hit is
  judged by your **new** colour.
- **No other cost:** no meter, no cooldown. Using it well is a matter of reading the
  rival.
- Switching is only possible when the fighter is free to act (idle, walking,
  crouching or in the air), not during an attack or hitstun.

### Damage

All of these are starting numbers for tuning:

| Hit | Damage |
|---|---|
| light (A) | 4 |
| heavy (B) | 8 |
| special | 10 |
| throw (Y) | 10 |
| MEASURE (a throw) | 12 |

- **Health:** ROBERT 100, BOHR 115.
- **No chip on a blocked hit.**
- **Knockdowns:** throws, sweeps and the knockdown specials knock down, as in v2.

## 2. Fighters and moves

The normals keep v2's frame data: startups, hitboxes, heights, chains and reach. Only
the damage numbers above and the colour rule change.

**The chain consequence.** In an A then B chain, A is your colour and B is the other.
Unless the rival switches mid-chain, exactly one half of the chain matches them. The
defender's colour decides which half lands.

### ROBERT: fast and lean, 100 health

- **PHOTON** (X): a projectile at head height, always **green**. A purple rival lets
  it bounce off; a green one must crouch or jump. 2.5 s cooldown, as in v2.
- **PHASE SLIDE** (down + X): a low slide, always **purple**. It slides under photons,
  as in v2.
- **HADAMARD DIVE** (air + X): v2's steep dive, in **your current colour**. When it
  hits, **you switch basis**: an H on yourself, applied at once and with no recovery.
  Your follow-up's colours flip with it, which makes the DIVE ROBERT's mix-up tool.

### BOHR: slow and broad, 115 health

- **MEASURE** (X): v2's dashing command grab, which connects from about a 125–130 px
  starting gap.
  - It is a throw, so it deals Y and hurts either colour.
  - It also **collapses the rival into BOHR's basis**: measuring projects them onto
    it. If they were already in it, nothing changes.
  - BOHR's A, which is its own colour, then matches them until they switch.
- **HADAMARD WAVE** (down + X): a short ground wave just in front of BOHR, about
  70 px.
  - It does **no damage** and **switches the rival's basis**: an H applied to them.
    Their colour flips, so the attack BOHR throws next can match.
  - It is a LOW move, so jumping clears it.
  - 3 s cooldown.
- **COLLAPSE** (air + X): v2's drifting body slam. The **slam is green** (HIGH) and
  the **landing shockwave is purple** (LOW, 60 px either side). A standing rival takes
  whichever matches their colour, so one half always hurts unless they crouch under
  the slam or jump over the shockwave.

### Shared

- **The throw:** B up close, pushing towards the rival. It is Y, hurts either colour,
  and knocks down.
- **Y** switches basis (section 1).

## 3. Readability and teaching

### On screen

- **Bodies:** each fighter's body is filled with its basis colour, green or purple,
  with darker back limbs and a highlight, as now.
- **Player identity:** a **blue ring under P1's feet and a red ring under P2's**,
  following the cabinet's left-blue, right-red convention, plus **P1/P2 tags** by the
  health bars.
- **Basis badge:** each health bar carries a badge showing the basis as `0/1` (green)
  or `+/-` (purple).
- **Attacks:** trails and the impact spark are in the attack's colour, so you can see
  before contact whether it will match. Throws show both colours.
- **Pop-ups:**
  - a matching hit shows the usual spark, damage and a pop-up: `X!` in green, `Z!` in
    purple, or `Y!` in both;
  - a wrong-colour hit shows a **ping**, a ring bouncing off in the attack's colour,
    with a short "ping" sound and the pushback;
  - a switch shows a white flash with an `H` pop-up as the body changes colour;
  - the specials' twists use the same `H` flash on whoever changes basis;
  - MEASURE shows a brief "collapse" flash on the rival in BOHR's colour.
- **No grid:** v2's grid tag and its effects are removed entirely.

### Teaching

The controls are the cabinet's biggest hurdle, so the rules are taught where a new
player actually looks:

1. **Title.** A **COLOUR MUST MATCH** card takes turns with the bot demo. An animated
   loop plays three beats, one line each:
   - *green hits green: hurts*;
   - *green hits purple: bounces*;
   - *Y switches your colour*.
2. **Select screen.** The screen lists each move with its colour, for example
   `X  PHOTON  green`, as coloured text or chips. Under each fighter is the line *A is
   your colour, B the other. Y switches.*
3. **First round.** A match's first ROUND 1 intro shows one hint line under the call:
   *MATCH THEIR COLOUR TO HURT - Y SWITCHES*.

All text is ASCII; the font has no ⟩.

## 4. Architecture and testing

The engine stays; the code underneath changes.

| Module | Change |
|---|---|
| `shor.py` → `basis.py` | Pure. `Basis` (Z_BASIS green, X_BASIS purple), `hurts(error, basis)` (X hurts Z_BASIS, Z hurts X_BASIS, Y hurts both), `hadamard(basis)`, `colour_of(error)`. Exact and fully tested. The Shor code and its reference test go. |
| `moves.py` | Every attack gets a `colour` rule: `own`, `opposite`, `green`, `purple` or `both`. Specials get a twist field: `switch_self_on_hit` (DIVE), `measure_rival` (MEASURE) or `switch_rival` (WAVE). Damage per section 1. The grid fields (`column`, cell mapping) go; `height` stays for the dodge rules. |
| `fighter.py` | A `basis` field, the Y switch (an `H` action with 10 frames of recovery), and the free-to-act rule. `take_hit` decides between damage and block from the attack's resolved error. |
| `fight.py` | Hit resolution: resolve each move's colour against its attacker's basis at the moment of the hit, then damage or block (pushback and block-stun). It applies the twists and emits `hit`, `block`, `switch`, `measure` and `throw` events. The height whiff rules and knockdown fixes from v2 stay. |
| `render.py` | Basis-coloured bodies, player rings and tags, the health-bar basis badges, coloured attack trails and sparks, the ping, the H flash, the measure flash. The grid tag goes. The select screen's move list, the title card and the ROUND 1 hint as in section 3. |
| `input.py`, `config.py` | Y on raw button 3. P1's keyboard dev key avoids `l x r b y a`. |
| `bot.py` | Reads the rival's basis to choose A or B, sometimes switches to dodge after a reaction delay, and uses throws on a rival who switches a lot. |
| `audio.py` | A "ping" for a block and a "whoosh" for a switch. |
| `match.py` | The title alternates the demo with the rules card, plus the first-round hint. |

### Testing

- **`basis.py`, exactly:**
  - X on \|0> gives \|1>, and X on \|+> gives \|+> (unchanged up to phase);
  - Z on \|+> gives \|->, and Z on \|0> gives \|0>;
  - Y flips both, and H swaps the bases;
  - `hurts` agrees with "the attack changes the state". The test checks this against
    explicit 2x2 matrices on the four basis states, not against the game's own
    tables.
- **Moves:** every attack has a colour rule and a height. A is `own` and B is
  `opposite` for both fighters, and every throw is `both`. The chain-reach test keeps
  passing.
- **Fights:**
  - a matching hit hurts, and a wrong-colour hit blocks with pushback and no damage;
  - a throw hurts both colours;
  - A then B on one rival lands exactly one half;
  - Y switches, has 10 frames of no attacking, and a hit during that time is judged by
    the new colour;
  - a DIVE hit switches the diver, MEASURE collapses the rival into BOHR's basis, and
    the WAVE switches the rival, deals no damage and is cleared by a jump;
  - COLLAPSE always has one matching half for a standing rival;
  - the v2 height and knockdown tests keep passing.
- **Bots:** fights finish in every pairing, bots land hits in both colours, and
  neither fighter wins every round.
- **Render and match:** smoke tests through the colours, rings, ping, flashes, the
  card and the hint, and the snapshot tool covers the new screens.

### Build order

Each step is its own commit, and the game stays playable throughout.

1. `basis.py` and its matrix test; move colours.
2. Switching (Y) and hit resolution (damage or block).
3. Colours, rings, badges, ping and flash on screen. This is the **playtest
   checkpoint**.
4. The specials' twists (DIVE, MEASURE, WAVE, COLLAPSE).
5. Bots, the teaching screens, audio.
6. Tuning from the playtest, docs and menu text, then deploy.

## Changes after playtests (2026-10-05)

These replace the matching parts of sections 1–3.

- **One colour rule for specials.** Fixed and mixed special colours were impossible to keep in
  mind. Every special is now in **your own colour**, like A: "A and X are your colour, B is
  the other; throws hurt both." MEASURE stays a throw (both). COLLAPSE's slam and shockwave
  are both BOHR's colour. A PHOTON keeps the colour it was fired in.
- **A move's colour is fixed when it starts**, not when it hits, so a switch mid-swing doesn't
  recolour it and the colour seen on the wind-up is always the colour that lands.
- **Y switches in any state:** walking, attacking, in hitstun, knocked down (pressed in a hit
  freeze, it applies as play resumes). A defender can switch mid-string so the rest bounces.
- **No infinites:** lights stun for 12 frames (ROBERT's jab was a true infinite), and getting up
  from a knockdown is invulnerable for 8 frames. A test mashes every normal and checks the
  defender is free again within CHAIN_MAX hits.
- **CHARGE NOISE replaces the HADAMARD WAVE** (BOHR, down + X), whose effect nobody could
  see. BOHR plants itself; for 1 s a field about 60 px all round it shocks anyone inside every
  12 frames (3 damage, 8 frames of stun, a push back), in BOHR's colour, MID. Distance or the
  other colour escapes it. Electric arcs show the field and its reach. 3 s cooldown.
- **COLLAPSE hits what it visibly lands on:** its slam box is the legs as drawn (feet to hip,
  56 px wide) instead of a 40x30 box at the feet, and the slam is MID (a falling body can't be
  ducked). The shockwave stays LOW.
- **Readability:** the whole striking arm or leg is drawn in the attack's colour from wind-up
  to the end of its active frames, with a trail while it's live; each health bar has an A and
  a B chip in the colours that player's buttons hit right now.

## Out of scope

- Superposition states (\|+> as "half green"), measurement randomness, entanglement
  between the fighters.
- A CPU mode, more fighters, a separate block button, a super meter.
