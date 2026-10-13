# Trailer V3: collected feedback

**Status (2026-10-07): V3 is built** (`build_trailer.py`, 40.6 s): the intro with
WELCOME TO THE and the pixelating logo, the new card texts with two games each
(Planck Time's ALIGN! and PAIR! among them), no speed-up section, a 4x3 mosaic of
all ten games, Nihilore's "Motion Blur" cut at 48.45 s with a filter fade-in,
reverse cymbal, crash and reverb tail. The notes below are what led there.

**V4 (2026-10-07), rearranged only, no new captures:**
- **Opening:** a 2x2 box of four classic-looking games (Pong, Pauli Invaders, Gate Drop, Ion Surfer), one more
  on every beat, replaces the opening Brawl-Ket fight, which felt random.
- **FIGHT QUANTUM ERRORS:** back instead of CORRECT, as it fits the shots after it better.
- **ALL WITHIN THE:** a new card before the mosaic, answering WELCOME TO THE.
- **Timing:** 42.6 s; the music now starts 2 s earlier (11.06 s into the track) so it still ends on the mosaic's cut.

**Short edition (2026-10-08, `--short`, 22.2 s):** the same opening box, then six
games without cards (cards at that pace were too much to read), 2.5 beats each
(two felt rushed), a quick mosaic and the end card. The same day, red and green
specks on the end card's logo turned out to be a rounding bug in the tube
(`build_reel.Tube`): a bilinear weight of -1 wrapped round in uint16. Fixed;
it was in every render, the reels included, but only showed on still pictures.

V2 (`build_trailer.py` as of 2026-10-07, 39.7 s) went down well. These notes
were collected for a V3; more feedback from colleagues is still coming. Don't
build V3 until it's asked for.

## Decided

- **The cards become:**
  - USE SUPERPOSITION (instead of "FIND YOURSELF IN SUPERPOSITION": too much)
  - BECOME ENTANGLED
  - APPLY QUANTUM GATES
  - CORRECT QUANTUM ERRORS (picked over "FIGHT QUANTUM ERRORS")
  - AND MUCH MORE (instead of "AND MANY MORE")
- **The rest stays:** the length (~40 s), the beat-synced cuts, the montage,
  the cuts that get faster, the 3x3 grid with the zoom into the logo, the end
  card with the TUM and MQT logos, the tube look, and powering the tube on and
  off.

## Ideas, not settled yet

- **A new opening.** Start on the Munich Quantum Arqade logo, standing still
  rather than turning, introduced by something like "WELCOME TO THE …". Then
  the logo pixelates away, and the trailer goes straight into something
  dynamic. Which shot opens isn't decided. Strong candidates from the
  highlights:
  - Pong with four balls (16.9 s)
  - every Qurves bike splitting at once (9.7 s)
  - the LOGICAL ERROR boss being shot apart (29.0 s)
- **More than one game per card, reusing games where needed.** A card with a
  single game behind it feels thin, especially "correct quantum errors" with
  only Pauli Invaders:
  - Superposition: Qurves. A second game is open; Pong's H gate splitting the
    ball would fit.
  - Entangled: Overquqed (Bell pairs). Undecided; games may move between cards.
  - Quantum gates: Qlimbers and Superconductor.
  - Quantum errors: Pauli Invaders and Gate Drop.
  - This should work better once there are one or two more games.
- **Music.** The owner remembers one of the Nihilore tracks from Batocera's
  menu music as cooler than Bolt Action's "Some Potential". Which one is
  still to be found. Nihilore is CC BY 4.0, so it could also be used
  publicly with credit.
  - Batocera ships five Nihilore tracks: Endless Blue, Motion Blur, Our Ships
    Line The Ocean Floor, Sparkwood & 21, The Bright Lights of Summer.
  - Measured so far:
    - Endless Blue: ~119.5 BPM, a long build, then a big loud section from
      ~146 s.
    - Motion Blur: ~86.5 BPM, possibly double that.
  - A new track needs `MUSIC`, `BPM`, `DROP_AT` and `DROP_BEAT` in
    `build_trailer.py`. Measure the BPM and the drop as was done for "Some
    Potential": onset strength, then beats lined up over the loud part.

## Colleague feedback (2026-10-07)

> As the cuts at the end get faster they soon repeat, and it feels as if
> there were only 4 or 5 games. Some games had no clips at all(?). Maybe the
> remaining videos could go in too?

Both points hold up against V2's `TIMELINE`:

- **Repeats in the fast section.** All 8 games in this repo are in V2, 3–4
  shots each. But the fast section is 4 cuts of one beat and 8 of half a beat,
  and Qlimbers, Pauli Invaders, Gate Drop and Qurves come twice within those
  12 cuts. Half a beat is 0.23 s, too short to tell games apart, so the
  section reads as a few games on a loop.
  - Fix: no game twice in the fast section (every game exactly once per
    pass).
  - Order it so neighbours look different: light Qlimbers and Overquqed
    between dark games, the 4:3 games apart.
  - Consider a minimum of one beat (0.45 s) per cut.
- **Games with no footage at all.**
  - The cabinet's menu also has **Planck Time** and **Brawl-Ket**, which are
    not in this repo. They need their code here (or alongside) and a bot in
    `bots/`, like the other games.
  - **Qlinko** is in `qlinko/` here but gitignored and not on the cabinet.
  - Sibling folders such as `froqqer`, `paq-man` and `quitar-hero` look like
    more games. If they are meant for the cabinet, they could get bots too.
  - Which games count is for the owner to decide.
- **Keeping ~40 s with more games:** two beats each in the montage would grow
  with every game, about 1 s per game. Options: 1.5 beats each, fewer games
  behind the concept cards, or the fast section as the only place every game
  appears.

### Second colleague (2026-10-07)

> Maybe just drop the part where the previews get faster and faster, and go
> straight from "and many more" to the mosaic.

This also solves the repeats above, which all sit in that section. In V2 the
section is 8 beats (3.6 s). Dropping it makes the trailer ~36 s, or the time
goes to the extra games after AND MUCH MORE (Planck Time, Brawl-Ket). Then
every game is on screen long enough to recognise before the mosaic shows all
of them together. The mosaic would need a 4x3 or similar layout if it should
hold more than 8 games around the logo.

Planck Time (`planck-time/`) and Brawl-Ket (`brawl-ket/`) arrived with the
pull of 2026-10-07. Once merged, they can get bots and captures like the
others.

### Planck Time for the thin cards (owner, 2026-10-07)

Planck Time's microgames could fill out the superposition and entanglement
cards. From its README, these fit:

- **Superposition:**
  - ALIGN!: point the Bloch-sphere arrow at the star.
  - MEASURE!: press while the needle is in the top zone.
  - SORT!: slide falling `|0>` / `|1>` into their bins.
- **Entanglement:**
  - PAIR!: pick one of the two particles swaying in sync.
  - MERGE!: lattice surgery, two surface-code patches merged XX or ZZ.
  - CONNECT!: walk your qubit along couplers to its partner.
- **Also usable:**
  - Gates: CANCEL!, SHORTER!
  - Errors: FIX!, VOTE! and the SYNDROME! boss, a fine "correct quantum
    errors" shot.

Planck Time plays one microgame of about five seconds after another, so a
capture won't contain a chosen microgame on cue. Two ways to get them:

- Its title already runs bots in an attract demo. The capture bot could reuse
  them, the way Overquqed's bot drives the game's own kitchen AI.
- Or set the seed or the microgame order so the ones wanted come up.

Either way, the bot should note in its `HIGHLIGHTS` which microgame each
window shows. The cards can then pick by microgame.

### All of Batocera's menu music, to listen to

All 12 tracks are in `trailer_assets/music_candidates/` (gitignored, ~60 MB;
licences beside them). BPM is measured from onsets, so double or half values
are possible. "Loud from" is where a trailer-worthy drop or full section
starts, if one was measured.

| Track | Length | BPM | Loud from | Licence |
|---|---|---|---|---|
| Bolt Action – Better Believe (Instrumental Mix) | 4:04 | ~95 | | non-commercial + credit |
| Bolt Action – Give Me | 1:42 | ~113 | 0:18 and 1:08 | non-commercial + credit |
| Bolt Action – Human Music (Instrumental Mix) | 3:01 | ~109 | | non-commercial + credit |
| Bolt Action – Retro Playground | 1:48 | ~93 (or 186) | 0:24, moderate | non-commercial + credit |
| Bolt Action – Some Potential (V2's) | 4:55 | 132.0 | 0:58 drop | non-commercial + credit |
| Bolt Action – Who You Are | 3:31 | ~120 | | non-commercial + credit |
| Bolt Action – vapormall | 3:36 | ~80 (or 160) | ~1:00 | non-commercial + credit |
| Nihilore – Endless Blue | 4:44 | ~120 | 2:26 | CC BY 4.0 |
| Nihilore – Motion Blur | 3:57 | ~87 (or 173) | even throughout | CC BY 4.0 |
| Nihilore – Our Ships Line The Ocean Floor | 6:07 | ~133 | | CC BY 4.0 |
| Nihilore – Sparkwood & 21 | 6:37 | ~143 | | CC BY 4.0 |
| Nihilore – The Bright Lights of Summer | 5:20 | ~120 | | CC BY 4.0 |

The owner found the Nihilore tracks less punchy than remembered (2026-10-07)
and is listening to the Bolt Action ones too.

## How the new parts could be built

- **The still logo:** the spin's frame 0, i.e. `art/mqt_splash.png`, or the
  flat logo from `logos/Arqade_logo.svg`, with "WELCOME TO THE" in the cards'
  small blue lead-in style above it.
- **Pixelating away:** shrink each frame by a growing factor, scale it back up
  nearest-neighbour, and cut to the first shot at the coarsest step. That
  also fits the pixel-art games.
- **Several games behind a card:** consecutive `shot` entries after the card
  in `TIMELINE`, about 2.5 beats each. Keep the total in beats about the same,
  so the drop still lands where it should.
