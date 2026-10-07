# Trailer V3: collected feedback

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
