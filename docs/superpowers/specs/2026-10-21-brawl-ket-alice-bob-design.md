# Brawl-Ket: ALICE & BOB, two fighters played as one: design

**Status: agreed with the user on 2026-10-22**, after a short design session on the 2026-10-21
proposal and two rounds of look mockups. ALICE & BOB is the seventh entry on CHOOSE YOUR
FIGHTER, after M-CUTIE (`2026-10-21-brawl-ket-m-cutie-design.md`).

The idea: two small fighters played as one, like the Ice Climbers. Bob copies Alice a beat
later, and their TELEPORT swaps them.

Alice and Bob are cryptography's two classic names, the pair every quantum protocol is
explained with: Alice sends, Bob receives, and Eve listens in.

Nothing in the v3 rules (`2026-10-02-brawl-ket-basis-design.md`) changes:
- colour must match to hurt;
- A is your colour and B the other;
- throws are Y and hurt either colour;
- every special is in their own colour.

Their controls are everyone's: X, down + X and air X.

## 1. The look

Approved on 2026-10-22: variant **A, COURIERS**, with Bob **40 px** behind Alice. The reference
is `2026-10-22-brawl-ket-alice-bob-look.py`, beside this spec (run it from `brawl-ket/`).

- **The sheet:**
  - Its rows 1 and 3 are drawn at the approved 40 px.
  - Row 2 compares 30 px with 40 px; the user chose 40.
  - The script also draws variant B (BATTERY, a pitcher and a catcher), kept for the record.
- **Porting:** porting them into the game should reproduce A.

- **Build:** both are a new, smaller build on the shared human skeleton, `"kid"`.
  - They are about 0.78 of ROBERT's height, with a big head on a short body, in the same
    chunky, ink-outlined toy language as the others.
  - Bob's back and neck are a few px longer than Alice's, so his face shows over her head.
- **A pair:** kid messengers in matching hoodies of their basis colour (hood, drawstrings,
  ribbed hem) with cream sneakers. Both are always the same colour, so the pair reads green or
  purple as one.
- **Alice, the sender:** female-coded.
  - A blonde bob with a big white bow, her clearest silhouette cue.
  - A short pleated skirt.
  - A courier satchel across her chest with a white letter in it.
- **Bob, the receiver:** male-coded.
  - Darker skin and dark hair, and a cap.
  - Big dark headphones with a little aerial on one cup.
- **An attack's limb lights up in its colour,** as on everyone, from the wind-up on (so in an
  echo, Bob's arm is already lit while he winds up).
- **Player rings:** both stand on a ring in their player's colour, Bob's thinner, so it's
  clear he belongs to that player.
- **Their specials, as drawn on the sheet:**
  - **KEY EXCHANGE:** Alice flicks the photon back underhand from her satchel side, along a
    dotted arc, into Bob's raised hand; then Bob's big photon flies forward past her, with
    speed lines.
  - **TELEPORT:** a column of light and a floor ring at each end, a dotted swap arc over the
    rival, and both bodies re-forming in TUNNEL-style scanlines.
  - **BELL DIVE:** two dives on one diagonal, Bob higher and behind.
  - **Bob decohered:** standing see-through, his outline flickering as a broken pale edge, the
    top of his head breaking into shifting scanlines and motes that drift up, his ring dimmed
    and dashed (he comes back).
- **Rejected:**
  - Variant B, BATTERY: a pitcher and a catcher in one team's kit.
  - Bob 30 px behind: the two bodies overlapped into one wide figure.
  - A decohered Bob lying faint on the floor: it didn't read.

## 2. The pair

| | |
|---|---|
| Size | both about 0.78 of ROBERT's height |
| Health | **one shared bar of 100**: a hit on either costs the bar its damage |
| Walk and jump | a little faster and lighter than ROBERT, for both |
| Normals and throws | the shared ones, for both (Bob's are his echo of Alice's) |
| Where Bob stands | **40 px behind Alice**, catching up when she walks |
| Their colour | always the same: Y switches both at once (entangled) |

- **The echo:**
  - Bob replays Alice's inputs **12 frames (0.2 s)** later.
  - He is a second body with his own hurtbox and his own hitboxes, driven by those delayed
    inputs.
  - Every attack comes twice, the second a beat late, so a rival who dodges Alice can be
    caught by Bob.
- **The player controls Alice.** Bob's facing follows hers.
- **Decoherence:**
  - A hit that knocks Bob down "decoheres" him: he fades out (section 1) and is gone for
    **3 s**.
  - Then he reappears 40 px behind Alice.
  - While he's gone, Alice fights alone. That is the rival's reward for going after Bob, but
    it never lasts the round.
- **Bob doesn't block anyone.** He has no push box against the rival, so the rival can walk
  between the two. That sets up TELEPORT and KEY EXCHANGE's interception.
- **The round** ends when the shared bar is empty, wherever Bob is.
- **Entangled colour:** anything that changes one's colour changes both. This covers Y, BOHR's
  MEASURE on either body, and a HADAMARD DIVE-style switch.

## 3. The specials

### X: KEY EXCHANGE (their colour, 2.5 s cooldown)

A nod to quantum key distribution.

1. **The toss:** Alice tosses a photon back to Bob along a short arc.
2. **The shot:** Bob "receives" it and fires it forward as **one strong shot, 12 damage**.
   - His shot is the normal projectile kind: it can be ducked or jumped as a PHOTON is,
     cancels against other shots, and DOS can COPY it.
3. **Bob doesn't echo KEY EXCHANGE:** he's the one receiving it.

- **Eve listens in:** the toss can be intercepted. A rival's attack or body that touches the
  photon in flight between them takes it out, and nothing fires. A DOS COPY catches it into
  his clipboard. That gives the rival a reason to stand between them.
- **While Bob is decohered:** Alice fires a plain small photon herself (6 damage), so X is
  never dead.

### Down + X: TELEPORT (2 s cooldown)

Quantum teleportation moves a state from Alice to Bob: here **Alice and Bob swap places**,
instantly, with a flash at both ends.

- **When the rival stands between them,** the swap crosses them up: Alice is suddenly on the
  far side, and both turn to face the rival.
- **Away from the rival,** it is a quick step back out of trouble.
- It does no damage, and Bob doesn't echo it (the swap is one move for both).
- It doesn't work while Bob is decohered.

**Changed after the first playtest (2026-10-22): ANCHOR first.** Bob copied Alice so closely
that the pair never split, and TELEPORT had nothing to swap across. Now the first down + X
**anchors** Bob: he stays where he is (a pin over his head and a second floor ring), still
echoes her attacks, but not her walks or jumps, and faces the rival. The cooldown starts only
with the second press, the swap above, after which he follows her again. Decoherence drops the
anchor.

**Also from that playtest: opposite colours.** They no longer share one colour: Bob is always
in the other basis (a singlet), so Y or MEASURE on either flips both and they stay opposite.
One attack colour then only ever hurts one of them. The user agreed to this with less damage
in mind, but over 200 rounds a side it made them no stronger (BOHR still wins about 72%
against them, PHOEBE about 37%), so their damage is unchanged.

### Air X: BELL DIVE (their colour, once per jump)

A steep diving kick: MID, 8 damage. Bob's echo lands a beat later, so the dive comes twice.

## 4. Screens and HUD

- **CHOOSE YOUR FIGHTER:**
  - one portrait showing both (Alice in front), named "ALICE & BOB", the seventh tile;
  - the trait "TWO AS ONE";
  - their specials: KEY EXCHANGE, TELEPORT and BELL DIVE.
- **The health bar:** one bar for the pair, with a small Bob icon by it that greys out while
  he is decohered.
- **Sounds:**
  - a toss blip and a catch click for KEY EXCHANGE, then a bigger shot;
  - a two-ended shimmer for TELEPORT;
  - the dive swoosh twice;
  - a fizzling static for Bob decohering, and a chime as he returns.

## 5. Bots

The bot controls Alice only. Bob follows by himself, as he does for a person.

Beyond the usual rules:
- KEY EXCHANGE at range, when the rival isn't standing between them;
- TELEPORT when the rival stands between them;
- BELL DIVE on a rival below.

Their pairings are held to the 60% bar (`tests/test_balance.py`, `tools/balance.py`), as
every fighter's since ERWIN and DOS. The bot also plays them in the title demo.

## 6. Engine notes: why this is the big job

The fight assumes one body per player throughout, and this breaks that assumption.

- **A second `Fighter` per player:** Bob, stepped from a 12-frame queue of Alice's inputs.
  Every one of these has to consider both bodies of a pair:
  - hits, shots and throws;
  - MEASURE and CHARGE NOISE;
  - ION TRAP, with its grace;
  - MOUSE CABLE's pull;
  - THE BOX's measurement;
  - COPY;
  - every fighter's bot.
- **The shared health bar,** Bob's decoherence and return, and his catch-up walk.
- **Push boxes:** the rival collides with Alice only.
- **Rendering:** two smaller fighters, a combined portrait, and the Bob icon on the HUD.
- **The bot,** and the balance bar with a two-body fighter.

A practical order: build the second body and the echo first, with the shared normals only,
and make it playable, before the three specials.

## 7. Interactions worth pinning down

| Situation | Result |
|---|---|
| BOHR's MEASURE on either body | collapses both (entangled) |
| A throw on Bob | thrown as anyone; the damage goes to the shared bar |
| CHARGE NOISE / BLUE-style fields over both | each body is hit as its own target; both hits cost the shared bar |
| ION TRAP under Bob | catches him as any grounded rival; Alice is free |
| MOUSE CABLE | pulls whichever body it hooks |
| ERWIN's THE BOX | a measurement by either body's attack, as any attack |
| DOS COPY | catches Bob's KEY EXCHANGE shot, Alice's solo photon, or the toss in flight |
| PHOEBE's TUNNEL | re-forms past Alice (the pair's x) |

## 8. Testing

- **The echo:** Bob repeats Alice's inputs exactly 12 frames later, and follows 40 px behind.
- **The pair:** one colour for both (Y switches both), and the shared health bar.
- **Decoherence:** a knockdown on Bob takes him out for 3 s and brings him back behind Alice.
- **KEY EXCHANGE:**
  - the toss and the shot;
  - an interception;
  - a COPY of the toss;
  - the solo photon while Bob is gone.
- **TELEPORT:** the swap, crossing a rival who stands between them, and no swap while Bob is
  gone.
- **BELL DIVE:** two dives, once per jump.
- **Every special in the game,** landing on either body (section 7).
- **The usual:**
  - move data and poses;
  - the select screen with seven fighters;
  - bots using all three specials;
  - rounds finishing;
  - the 60% bar;
  - the frame budget with two extra bodies on screen.
