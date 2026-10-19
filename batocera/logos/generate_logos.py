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

Each game lives in its own logo_<rom>.py with `ROM`, `art(size)`,
`wide(width, height)` and `marquee()`. The wide tile is the same identity as
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
]
SIZE = 1024
WIDE = (1024, 512)


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


def main(argv: list[str]) -> None:
    pygame.init()
    pygame.display.set_mode((1, 1))
    wide_only = "--wide" in argv
    roms = [a for a in argv if not a.startswith("--")] or ROMS
    arts, wides = [], []
    for rom in roms:
        mod = importlib.import_module(f"logo_{rom}")
        if not wide_only:
            art = mod.art(SIZE)
            assert art.get_size() == (SIZE, SIZE), f"{rom}: art() must return {SIZE}x{SIZE}"
            pygame.image.save(art, HERE / f"{rom}-logo.png")
            pygame.image.save(mod.marquee(), HERE / f"{rom}-marquee.png")
            arts.append(art)
            print(f"wrote {rom}-logo.png, {rom}-marquee.png")
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
    if roms == ROMS:
        tiles = [pygame.image.load(str(HERE / f"{rom}-wide.png")) for rom in ROMS
                 if (HERE / f"{rom}-wide.png").is_file()]
        pygame.image.save(wide_sheet(tiles), HERE / "wide-sheet.png")
        print("wrote wide-sheet.png")


if __name__ == "__main__":
    sys.path.insert(0, str(HERE))
    main(sys.argv[1:])
