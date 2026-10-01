"""Render Brawl-Ket's puppets and fight frames to PNGs, to check the look
without a cabinet.

    cd brawl-ket && uv run python tools/snapshot.py OUT_DIR

Writes:
- poses_lean.png, poses_heavy.png: every pose in POSE_NAMES, labelled, facing
  right, in P1's colours;
- moves_lean.png: every TRIO move as a strip of frames, as pose_for blends it;
- code_tags.png: the code tag close up (x4 on top of the x2 save) in its states: normal, one
  light flipped (danger, both beats of the pulse), the green flash after a correction, the
  red flash after a logical error;
- fight_danger.png: a bot fight at the moment a code is one hit from a logical error;
- fight_start.png (the fighters walking in), fight_hit.png, fight_logical.png, fight_crouch.png, fight_shot.png,
  fight_knockdown.png: bot-against-bot frames at those moments (fight_boxes.png
  is the hit frame again with the hurt- and hitboxes drawn).

Everything is saved at x2 so the pixels are easy to see.
"""

from __future__ import annotations

import os
import sys

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")

import pygame

from brawl_ket import config, qec
from brawl_ket import palette as P
from brawl_ket.bot import Bot
from brawl_ket.fight import Fight
from brawl_ket.fighter import Fighter
from brawl_ket.moves import TRIO
from brawl_ket.poses import POSE_NAMES, POSES, SCALE, joints, pose_for
from brawl_ket.render import DANGER_BEAT, Renderer, draw_puppet, outlined, tag_state

W, H = config.INTERNAL_WIDTH, config.INTERNAL_HEIGHT
CELL_W, CELL_H, COLS = 180, 230, 6
CELL_FLOOR = 200
ACCENTS = {"lean": P.CREAM, "heavy": P.GOLD}


def save(surf: pygame.Surface, out_dir: str, name: str) -> None:
    path = os.path.join(out_dir, name)
    pygame.image.save(pygame.transform.scale_by(surf, 2), path)
    print(path)


def cell_floor(sheet: pygame.Surface, x: int, y: int) -> None:
    sheet.fill(P.NIGHT, (x + 1, y + 1, CELL_W - 2, CELL_H - 2))
    sheet.fill(P.SLATE, (x + 1, y + CELL_FLOOR, CELL_W - 2, 2))


def pose_sheet(build: str) -> pygame.Surface:
    rows = -(-len(POSE_NAMES) // COLS)
    sheet = pygame.Surface((COLS * CELL_W, rows * CELL_H))
    sheet.fill(P.INK)
    for i, name in enumerate(POSE_NAMES):
        x, y = (i % COLS) * CELL_W, (i // COLS) * CELL_H
        cell_floor(sheet, x, y)
        xs = [jx for jx, _ in joints(POSES[name], build, (0.0, 0.0), 1).values()]
        feet = (x + CELL_W / 2 - (min(xs) + max(xs)) / 2, y + CELL_FLOOR)   # centred in the cell
        draw_puppet(sheet, POSES[name], build, feet, 1, config.PLAYER_COLORS["p1"], ACCENTS[build])
        sheet.blit(outlined(name, 8, P.WHITE), (x + 6, y + 6))
    return sheet


def move_sheet() -> pygame.Surface:
    """Each TRIO move, one row: every few frames of it, as the game blends them."""
    strip = 9
    sheet = pygame.Surface((strip * 130, len(TRIO.moves) * 170))
    sheet.fill(P.INK)
    for row, (slot, move) in enumerate(TRIO.moves.items()):
        total = move.startup + move.active + move.recovery
        f = Fighter(TRIO, 0, 1)
        f.action, f.move, f.slot = "attack", move, slot
        y = row * 170
        for k in range(strip):
            f.frame = round(k * (total - 1) / (strip - 1))
            x = k * 130
            sheet.fill(P.NIGHT, (x + 1, y + 1, 128, 168))
            sheet.fill(P.SLATE, (x + 1, y + 150, 128, 2))
            draw_puppet(sheet, pose_for(f), "lean", (x + 62, y + 150), 1, config.PLAYER_COLORS["p1"], P.CREAM)
            sheet.blit(outlined(f"{f.phase[0].upper()}{f.frame}", 8, P.MIST), (x + 4, y + 156))
        sheet.blit(outlined(f"{slot} {move.name}", 8, P.WHITE), (6, y + 6))
    return sheet


def tag_sheet() -> pygame.Surface:
    """The code tag in each of its states, cropped around p1's and p2's heads and magnified."""
    surface = pygame.Surface((W, H))
    zoom, crop = 4, pygame.Rect(0, 0, 90, 46)
    cases = [
        ("normal", lambda c, r, k: None),
        ("1 flipped: danger (bright)", lambda c, r, k: (c.hit(qec.X), setattr(r, "t", 0))),
        ("1 flipped: danger (dim)", lambda c, r, k: (c.hit(qec.X), setattr(r, "t", DANGER_BEAT // 2))),
        ("corrected: green flash", lambda c, r, k: r.flash.__setitem__(k, (P.GOOD, 21))),
        ("logical: red flash", lambda c, r, k: r.flash.__setitem__(k, (P.BAD, 21))),
    ]
    sheet = pygame.Surface((len(cases) * crop.w * zoom, 2 * (crop.h * zoom + 16)))
    sheet.fill(P.INK)
    for col, (label, setup) in enumerate(cases):
        for row, key in enumerate(("p1", "p2")):
            fight = Fight({"p1": TRIO, "p2": TRIO})
            fight.fighters["p1"].x, fight.fighters["p2"].x = 280, 360
            r = Renderer(surface)
            r.draw_fight(fight, [])
            setup(fight.fighters[key].code, r, key)
            r.draw_fight(fight, [])
            f = fight.fighters[key]
            crop.center = (round(f.x), round(r.tag_y[key]) - 6)
            shot = pygame.transform.scale_by(surface.subsurface(crop.clip(surface.get_rect())), zoom)
            x, y = col * crop.w * zoom, row * (crop.h * zoom + 16)
            sheet.blit(shot, (x, y + 16))
            sheet.blit(outlined(f"{key} {label}", 8, P.WHITE), (x + 4, y + 2))
    return sheet


def find_frames(out_dir: str) -> None:
    """Play bot fights until each wanted moment has been seen, saving the frame."""
    surface = pygame.Surface((W, H))
    wanted = {
        "hit": lambda f, ev, ago: ago.get("hit") == 2,
        "logical": lambda f, ev, ago: ago.get("logical") == 8,
        "crouch": lambda f, ev, ago: sorted(x.action for x in f.fighters.values()) in (["crouch", "idle"], ["crouch", "walk"])
        and all(ago.get(k, 99) > 80 for k in ("hit", "logical")),
        "danger": lambda f, ev, ago: any(tag_state(x.code) == "danger" for x in f.fighters.values())
        and ago.get("hit") == 6,
        "shot": lambda f, ev, ago: bool(f.shots) and abs(f.shots[0].x - f.fighters["p2"].x) > 120,
        "knockdown": lambda f, ev, ago: any(x.action == "knockdown" and x.frame == 14 for x in f.fighters.values()),
    }
    for seed in range(300):
        if not wanted:
            break
        fight = Fight({"p1": TRIO, "p2": TRIO})
        bots = {"p1": Bot("p1", seed), "p2": Bot("p2", seed + 1000)}
        r = Renderer(surface)
        ago: dict[str, int] = {}        # frames since the last event of each kind
        while not fight.over and wanted:
            events = fight.step({k: b.input(fight) for k, b in bots.items()})
            ago = {k: v + 1 for k, v in ago.items() if v < 90}
            for e in events:
                ago[e.kind] = 0
            r.draw_fight(fight, events, {"p1": 1, "p2": 0})
            if seed == 0 and fight.frames_left == config.ROUND_FRAMES - 24:
                save(surface, out_dir, "fight_start.png")
            for name in list(wanted):
                if fight.frames_left < config.ROUND_FRAMES - 60 and wanted[name](fight, events, ago):
                    save(surface, out_dir, f"fight_{name}.png")
                    if name == "hit":
                        r.show_boxes = True
                        r.draw_fight(fight, [])
                        r.show_boxes = False
                        save(surface, out_dir, "fight_boxes.png")
                    del wanted[name]
    for name in wanted:
        print(f"never saw: {name}")


def main(argv: list[str]) -> None:
    if len(argv) != 1:
        sys.exit(__doc__)
    out_dir = argv[0]
    os.makedirs(out_dir, exist_ok=True)
    pygame.init()
    for build in SCALE:
        save(pose_sheet(build), out_dir, f"poses_{build}.png")
    save(move_sheet(), out_dir, "moves_lean.png")
    save(tag_sheet(), out_dir, "code_tags.png")
    find_frames(out_dir)


if __name__ == "__main__":
    main(sys.argv[1:])
