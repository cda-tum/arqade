# Brawl-Ket: ALICE & BOB, two fighters played as one: design proposal

**Status: a proposal, not yet agreed.** The user liked the idea in the 2026-10-21 brainstorm
(two small fighters played as one, like the Ice Climbers, with Bob copying Alice a beat
later and a TELEPORT special) and asked for the spec to be written down without a design
session. Everything below is a concrete proposal to react to. The decisions that are the
user's to make are collected in section 8, Open questions. They come after M-CUTIE
(`2026-10-21-brawl-ket-m-cutie-design.md`), as the bigger job.

Alice and Bob are cryptography's two classic names, the pair every quantum protocol is
explained with: Alice sends, Bob receives, and Eve listens in.

Nothing in the v3 rules (`2026-10-02-brawl-ket-basis-design.md`) changes:
- colour must match to hurt;
- A is your colour and B the other;
- throws are Y and hurt either colour;
- every special is in their own colour.

## 1. The idea

- **One player, two bodies.** The player controls ALICE. BOB follows a little behind her and
  does whatever she did, a beat later: the same moves, the same jumps, the same specials.
- **An entangled pair.** They are always the same colour: Y switches both at once, like
  measuring one half of an entangled pair fixes the other. So the colour rule reads the same
  for both, and the rival only ever has one colour to match.
- **Why it's fun:** every attack comes twice, the second one a beat late, so a rival who dodges
  Alice can be caught by Bob. In return the pair is two targets, and each is small and light.

## 2. The bodies

| | |
|---|---|
| Size | both smaller than the others, about 0.8 of ROBERT's height |
| Health | one shared bar of 100: a hit on either costs the bar its damage |
| Walk and jump | a little faster and lighter than ROBERT, for both |
| Normals and throws | the shared ones, for both (Bob's are his echo of Alice's) |
| Where Bob stands | about 30 px behind Alice, catching up when she walks |

- **The echo:** Bob replays Alice's inputs 12 frames (0.2 s) later. He is a second body with
  his own hurtbox and his own hitboxes, driven by those delayed inputs.
- **Knocking Bob out:** a hit that knocks Bob down "decoheres" him. He fades out for 3 s, then
  reappears behind Alice. While he's gone, Alice fights alone: the pair is weaker, and that
  is the rival's reward for going after Bob.
- **Bob doesn't block anyone:** he has no push box against the rival, so the rival can walk
  between the two. That sets up TELEPORT.
- **The round:** it ends when the shared bar is empty, wherever Bob is.

## 3. The specials

### X: PHOTON PAIR (their colour, 2.5 s cooldown)

Alice fires a small photon; Bob fires his a beat later (the echo). Two shots in a row, which
covers a rival who jumps the first one. Each does 6 damage: two together roughly match one
PHOTON.

### Down + X: TELEPORT (2 s cooldown)

Quantum teleportation moves a state from Alice to Bob: here **Alice and Bob swap places**,
instantly, with a flash at both ends.
- **When the rival stands between them,** the swap crosses them up: Alice is suddenly on the
  far side.
- **Away from the rival,** it is a quick step back out of trouble.
- It does no damage, and Bob doesn't echo it (the swap is one move for both).

### Air X: BELL DIVE (their colour, once per jump)

A steep diving kick. Bob's echo lands a beat later, so the dive comes twice. Each does 8
damage, MID.

## 4. Screens and HUD

- **CHOOSE YOUR FIGHTER:** one portrait showing both (Alice in front), named "ALICE & BOB",
  with the trait "TWO AS ONE".
- **The health bar:** one bar for the pair, with a small Bob icon by it that greys out while
  he is decohered.
- **Player rings:** both stand on a ring in their player's colour, Bob's thinner, so it's clear
  he belongs to that player.

## 5. Bots

The bot controls Alice only; Bob follows by himself, as he does for a person. Beyond the
usual rules:
- PHOTON PAIR at range;
- TELEPORT when the rival stands between them;
- BELL DIVE on a rival below.

Their pairings are held to the 60% bar, as every fighter's since ERWIN and DOS.

## 6. Engine notes: why this is the big job

The fight assumes one body per player throughout, and this breaks that assumption:
- **A second `Fighter` per player:** Bob, stepped from a 12-frame queue of Alice's inputs.
  Hits, shots, throws, MEASURE, CHARGE NOISE, ION TRAP, MOUSE CABLE's pull and THE BOX's
  measurement all have to consider both bodies of a pair.
- **The shared health bar,** Bob's decoherence and return, and his catch-up walk.
- **Push boxes:** the rival collides with Alice only.
- **Rendering:** two smaller fighters, a combined portrait, and the Bob icon on the HUD.
- **The bot,** and the balance bar with a two-body fighter.
- **Every existing special's interaction with a pair** needs a decision and a test (for
  example: does BOHR's MEASURE collapse both? It should, since they're entangled).

A practical order: build the second body and the echo first, with the shared normals only,
and play it, before the three specials.

## 7. Testing

- **The echo:** Bob repeats Alice's inputs exactly 12 frames later, and follows 30 px behind.
- **The pair:** one colour for both (Y switches both), and the shared health bar.
- **Decoherence:** a knockdown on Bob takes him out for 3 s and brings him back behind Alice.
- **TELEPORT:** the swap, and crossing a rival who stands between them.
- **Their specials:** PHOTON PAIR's two shots and BELL DIVE's two dives.
- **Against every special in the game:** each one landing on either body.
- **The usual:** bots, rounds finishing, the 60% bar, the frame budget.

## 8. Open questions (the user's to decide)

1. **One shared bar, or does Bob have his own?** Proposed: one shared bar, with Bob decohering
   for 3 s after a knockdown. The alternative is the Ice Climbers' way: Bob can be lost for
   the rest of the round.
2. **How late is the echo?** Proposed: 0.2 s, enough to see two attacks, short enough to stay
   one fighter.
3. **TELEPORT as a swap?** Proposed: Alice and Bob swap places. The alternative is that Alice
   jumps to Bob, and Bob stays.
4. **Their X and air X:** PHOTON PAIR and BELL DIVE are placeholders that make the echo show
   off. Any move ideas of your own for the pair?
5. **Their look:** two small, cute characters in the basis colour, told apart by something
   simple (her hair bow, his cap). To be settled with prototypes, as for every fighter.
