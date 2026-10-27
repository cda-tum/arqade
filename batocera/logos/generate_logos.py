"""Render a styled logo for every game: key art plus the game's title.

    python generate_logos.py               # all games
    python generate_logos.py qurves ...    # just these (by ROM name)
    python generate_logos.py --wide ...    # only the wide tiles (and their sheet)

Run it with any of the games' venvs (they all pin the same pygame), e.g.
`../../quantum-pong/.venv/bin/python generate_logos.py`. For each game it
writes, next to this file:

  <rom>-logo.png     1024x1024 key art with the title (the PC launcher's tiles)
  <rom>-wide.png     1024x512, the same art laid out for the cabinet's game
                     list: its tiles are about 2:1, and ES scales an image to
                     *cover* a tile, so a square logo loses its top and bottom
  <rom>-marquee.png  the title alone on transparency (a wide "wheel" logo)
  contact-sheet.png  all logos side by side, for a quick look
  wide-sheet.png     all wide tiles side by side
  extended/<rom>-logo.png
                     the square logo with PAD px more of its own background on
                     every side (1792x1792), for round 50 mm pin badges: the
                     whole image is the 50 mm punch circle's square, and only
                     the middle 38 mm show on the badge's face (the rest wraps
                     round its edge), so every title has to sit inside that
  extended/circle-sheet.png
                     those, cropped to the punch circle, a ring marking the face

Each game lives in its own logo_<rom>.py with `ROM`, `art(size, pad=0)`,
`wide(width, height)` and `marquee()`. With `pad`, art() draws the same logo,
everything where it was, on a canvas `pad` px bigger on every side, its
background running on out to the new edges (a flat colour, a starfield, the
floor, the sky...): not stretched or mirrored, drawn. The wide tile is the same identity as
the square logo, rearranged: not a crop of it. ES crops the tile a little
anyway (it is not exactly 2:1) and rounds its corners, so keep the title and
hero inside the middle 90 % of the width. Those modules import the game's own package (its src/ goes on
sys.path), so the logos are built from the same sprites and colours the game
draws -- a sprite tweak in a game shows up here on the next run. Shared
lettering and lighting effects are in kit.py.
"""

from __future__ import annotations

import importlib
import sys
from pathlib import Path

import kit  # noqa: F401  (sets the dummy SDL drivers before pygame starts)
import pygame

HERE = Path(__file__).resolve().parent
EXTENDED = HERE / "extended"
ROMS = [
    "quantum_pong",
    "quantum_towers",
    "error_invaders",
    "ion_surfer",
    "superconductor",
    "overquqed",
    "qurves",
    "gate_drop",
    "planck_time",
    "brawl_ket",
    "qarrera",
    "gate_prix",
]
SIZE = 1024
WIDE = (1024, 512)
# The badge face (38 mm of the 50 mm punch) must hold every title. The farthest
# title corners from the centre (Brawl-Ket's band, Gate Prix's banner) are ~645 px
# out on the 1024 square, and the face's radius is 0.76 * (1024 / 2 + PAD) = 681 px.
# 384 is also a whole number of Overquqed's floor tiles and Planck Time's checker
# squares (so they line up as before) and of Pauli Invaders' grid.
PAD = 384
FACE = 38 / 50  # the badge's face, of its punch diameter


def contact_sheet(images: list[pygame.Surface], cell: int = 384) -> pygame.Surface:
    cols = 4
    rows = (len(images) + cols - 1) // cols
    sheet = pygame.Surface((cols * cell, rows * cell))
    sheet.fill((12, 12, 18))
    for i, img in enumerate(images):
        sheet.blit(pygame.transform.smoothscale(img, (cell, cell)), ((i % cols) * cell, (i // cols) * cell))
    return sheet


def wide_sheet(images: list[pygame.Surface], cell: tuple[int, int] = (512, 256)) -> pygame.Surface:
    cols = 3
    rows = (len(images) + cols - 1) // cols
    sheet = pygame.Surface((cols * cell[0], rows * cell[1]))
    sheet.fill((12, 12, 18))
    for i, img in enumerate(images):
        sheet.blit(pygame.transform.smoothscale(img, cell), ((i % cols) * cell[0], (i // cols) * cell[1]))
    return sheet


def circle_sheet(images: list[pygame.Surface], cell: int = 320) -> pygame.Surface:
    """The extended logos cropped to the punch circle, side by side, a thin ring
    marking the badge's face."""
    cols = 4
    rows = (len(images) + cols - 1) // cols
    sheet = pygame.Surface((cols * cell, rows * cell))
    sheet.fill((40, 40, 46))
    mask = pygame.Surface((cell, cell), pygame.SRCALPHA)
    pygame.draw.circle(mask, (255, 255, 255, 255), (cell / 2, cell / 2), cell / 2 - 4)
    for i, img in enumerate(images):
        disc = pygame.transform.smoothscale(img, (cell, cell)).convert_alpha()
        disc.blit(mask, (0, 0), special_flags=pygame.BLEND_RGBA_MIN)
        pygame.draw.circle(disc, (255, 255, 255), (cell / 2, cell / 2), (cell / 2 - 4) * FACE, 1)
        sheet.blit(disc, ((i % cols) * cell, (i // cols) * cell))
    return sheet


def main(argv: list[str]) -> None:
    pygame.init()
    pygame.display.set_mode((1, 1))
    wide_only = "--wide" in argv
    roms = [a for a in argv if not a.startswith("--")] or ROMS
    arts, wides, extended = [], [], []
    EXTENDED.mkdir(exist_ok=True)
    for rom in roms:
        mod = importlib.import_module(f"logo_{rom}")
        if not wide_only:
            art = mod.art(SIZE)
            assert art.get_size() == (SIZE, SIZE), f"{rom}: art() must return {SIZE}x{SIZE}"
            pygame.image.save(art, HERE / f"{rom}-logo.png")
            pygame.image.save(mod.marquee(), HERE / f"{rom}-marquee.png")
            arts.append(art)
            print(f"wrote {rom}-logo.png, {rom}-marquee.png")
            ext = mod.art(SIZE, PAD)
            assert ext.get_size() == (SIZE + 2 * PAD,) * 2, f"{rom}: art(size, pad) must return {SIZE + 2 * PAD} square"
            pygame.image.save(ext, EXTENDED / f"{rom}-logo.png")
            extended.append(ext)
            print(f"wrote extended/{rom}-logo.png")
        if hasattr(mod, "wide"):
            tile = mod.wide(*WIDE)
            assert tile.get_size() == WIDE, f"{rom}: wide() must return {WIDE[0]}x{WIDE[1]}"
            pygame.image.save(tile, HERE / f"{rom}-wide.png")
            wides.append(tile)
            print(f"wrote {rom}-wide.png")
        else:
            print(f"NOTE: logo_{rom}.py has no wide() yet")
    if roms == ROMS and not wide_only:
        pygame.image.save(contact_sheet(arts), HERE / "contact-sheet.png")
        print("wrote contact-sheet.png")
        pygame.image.save(circle_sheet(extended), EXTENDED / "circle-sheet.png")
        print("wrote extended/circle-sheet.png")
    if roms == ROMS:
        tiles = [pygame.image.load(str(HERE / f"{rom}-wide.png")) for rom in ROMS
                 if (HERE / f"{rom}-wide.png").is_file()]
        pygame.image.save(wide_sheet(tiles), HERE / "wide-sheet.png")
        print("wrote wide-sheet.png")


if __name__ == "__main__":
    sys.path.insert(0, str(HERE))
    main(sys.argv[1:])
