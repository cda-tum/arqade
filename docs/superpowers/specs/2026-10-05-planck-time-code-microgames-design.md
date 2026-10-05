# Planck Time: two error-correcting-code microgames (not decoding): design

Planck Time already has a lot of decoding: VOTE!, FIX! and the SYNDROME! boss. These two
microgames use the colour code and the surface code for something else: what the code
*looks like*, and how logical operations are done with it. They follow every rule in
"Rules shared by all nine" of `2026-10-05-planck-time-crossovers-design.md`:

- the contract tests and one module each;
- 240x160 and the GBA palette;
- readable at first sight, with the first decision at least 0.6 s in at level 0;
- a hint line at the bottom;
- ASCII text, with each glyph checked against the font.

## TILE! (colour code), stick+a

- **The picture:** a patch of the 2D colour code, a honeycomb of hexagonal tiles, each
  red, green or blue, with a dot at every corner for the data qubits. It is a real
  3-colouring: neighbouring tiles always differ, so around any tile the six neighbours
  alternate between the other two colours. One tile is **blank** and pulses.
- **The play:** three colour swatches at the bottom. The stick, left and right, picks a
  swatch, and A paints the blank tile. Each swatch also carries a small shape (for
  example a triangle, a circle and a square) so the colours can be told apart without
  colour vision; the same shape is drawn on the tiles.
- **Win:** the missing third colour. The tile fills in, and the corners round it light up
  to show that each touches one tile of every colour.
- **Fail:** any other colour. The clashing neighbours flash with the red X. A timeout
  also fails, and so does idle.
- **Later appearances** (`self.appearance`):
  - first, one interior blank;
  - then two blanks, which are never adjacent, so each is still determined by its
    neighbours, painted in either order;
  - then blanks near the patch's edge with only 3 or 4 neighbours, which still have at
    least two different colours around them. The answer must always be unique: test
    this.
- **Caption:** "Each corner touches one tile of every colour" (43 characters).

## MERGE! (lattice surgery on the surface code), stick+a

- **The picture:** two surface-code patches, drawn as in Litinski's *A Game of Surface
  Codes*, the best-known pictorial convention. Each is a small square (a distance-3
  rotated surface code) checkerboarded with X plaquettes and Z plaquettes. Every edge is
  an **X edge** (dashed) or a **Z edge** (solid); opposite edges match and adjacent edges
  differ. The edges are also coloured, X in `P.GATE["X"]` (red) and Z in `P.GATE["Z"]`
  (blue), and carry a small letter, so dashed against solid, colour and letter all say
  the same thing.
  - The left patch is fixed.
  - The right patch is yours, floating to the right.
- **The play:** A rotates your patch by 90 degrees, with a short spin animation. That
  swaps which edge type faces left. Pushing the stick **left** slides it in to merge.
- **Win:** the edges facing each other are the same type. The patches join, the gap fills
  with new plaquettes, and a merged patch glows. A label shows the joint measurement:
  `XX` when merged along X edges, `ZZ` along Z edges.
- **Fail:** pushing in while the facing edges differ. The patches bounce apart with the
  red X. A timeout also fails, and so does idle.
- **Later appearances:**
  - first, one fixed patch on the left, and your patch starts mismatched about half the
    time;
  - from the second appearance on, two fixed patches on the left, upper and lower, with
    *different* edge types facing you, and an order at the top: `MEASURE XX` or
    `MEASURE ZZ`. The stick, up and down, picks the lane. Rotate to the right edge type,
    pick the lane whose patch has that type facing, and push left.
  - Exactly one combination wins. Test this.
- **Caption:** "Code patches merge along matching edges" (39 characters).
- **Faithfulness:** in Litinski's convention, an edge's type is the logical operator that
  runs along it. Merging two patches along their X edges measures the joint operator XX,
  and along their Z edges ZZ. That is how logical two-qubit operations are built in
  lattice surgery. The labels say only this, and the module's docstring names the
  convention.

## Testing

- The contract tests cover both.
- TILE!: the colouring is a valid 3-colouring, and every blank has a unique answer,
  over many seeds and appearances.
- MERGE!: exactly one winning configuration, the bot wins and idle loses, at
  appearances 0 and 2.
- Snapshots of each, checked by eye.
