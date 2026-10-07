"""Render a styled logo for every game: key art plus the game's title.

    python generate_logos.py               # all games
    python generate_logos.py qurves ...    # just these (by ROM name)

Run it with any of the games' venvs (they all pin the same pygame), e.g.
`../../quantum-pong/.venv/bin/python generate_logos.py`. For each game it
writes, next to this file:

  <rom>-logo.png     1024x1024 key art with the title, for the ES game list
  <rom>-marquee.png  the title alone on transparency (a wide "wheel" logo)
  contact-sheet.png  all logos side by side, for a quick look

Each game lives in its own logo_<rom>.py with `ROM`, `art(size)` and
`marquee()`. Those modules import the game's own package (its src/ goes on
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
]
SIZE = 1024


def contact_sheet(images: list[pygame.Surface], cell: int = 384) -> pygame.Surface:
    cols = 4
    rows = (len(images) + cols - 1) // cols
    sheet = pygame.Surface((cols * cell, rows * cell))
    sheet.fill((12, 12, 18))
    for i, img in enumerate(images):
        sheet.blit(pygame.transform.smoothscale(img, (cell, cell)), ((i % cols) * cell, (i // cols) * cell))
    return sheet


def main(argv: list[str]) -> None:
    pygame.init()
    pygame.display.set_mode((1, 1))
    roms = argv or ROMS
    arts = []
    for rom in roms:
        mod = importlib.import_module(f"logo_{rom}")
        art = mod.art(SIZE)
        assert art.get_size() == (SIZE, SIZE), f"{rom}: art() must return {SIZE}x{SIZE}"
        pygame.image.save(art, HERE / f"{rom}-logo.png")
        pygame.image.save(mod.marquee(), HERE / f"{rom}-marquee.png")
        arts.append(art)
        print(f"wrote {rom}-logo.png, {rom}-marquee.png")
    if not argv:
        pygame.image.save(contact_sheet(arts), HERE / "contact-sheet.png")
        print("wrote contact-sheet.png")


if __name__ == "__main__":
    sys.path.insert(0, str(HERE))
    main(sys.argv[1:])
