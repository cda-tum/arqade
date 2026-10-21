"""Render Brawl-Ket's puppets and fight frames to PNGs, to check the look
without a cabinet.

    cd brawl-ket && uv run python tools/snapshot.py OUT_DIR

Writes:
- poses_lean.png, poses_heavy.png: every pose in POSE_NAMES, labelled, facing
  right, in P1's colours;
- moves_lean.png, moves_heavy.png: every ROBERT / BOHR move as a strip of frames, as pose_for
  blends it;
- fight_block.png: p1 jabs a purple p2 at 50 px, 2 frames on (the green jab bounces: the ping);
- fight_throw.png: p1 throws p2, 2 frames on (Y!: green and purple);
- fight_switch.png: p1 presses Y (an H), 2 frames on (the white flash, the H pop-up, the badge);
- fight_strike.png: p1's heavy late in its wind-up (the fist glows in its colour);
- bohr_collapse_*.png: BOHR's COLLAPSE next to a standing purple ROBERT: the fall (the green
  slam bounces), the landing shockwave just after it opens (green too: it bounces), and spread out;
- bohr_noise_*.png: BOHR's CHARGE NOISE on a ROBERT: the wind-up sparks, and the field crackling;
- bohr_measure.png: MEASURE connecting on a purple ROBERT, 3 frames on (the collapse into green);
- vs_*.png: the same bot-fight moments as fight_*.png, ROBERT (P1) against BOHR (P2), and
  vs_close.png, the two walked into each other;
- screen_*.png: the match flow: the title (and with QUIT picked), the attract demo, select (and
  with P1 ready), the stage select (on RANDOM, and on QUANTUM WEEK), HOW TO PLAY,
  the ROUND 1 and FIGHT! calls, the pause menu, a K.O. with PERFECT, and the result;
- fight_start.png (the fighters walking in), fight_hit.png, fight_bot_block.png, fight_bot_switch.png,
  fight_crouch.png, fight_shot.png, fight_knockdown.png: bot-against-bot frames at those moments (fight_boxes.png
  is the hit frame again with the hurt- and hitboxes drawn).

Everything is saved at x2 so the pixels are easy to see.
"""

from __future__ import annotations

import os
import random
import sys

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")

import pygame

from brawl_ket import config
from brawl_ket.basis import X_BASIS
from brawl_ket import palette as P
from brawl_ket.bot import Bot
from brawl_ket.fight import Fight
from brawl_ket.fighter import Fighter
from brawl_ket.moves import BOHR, ROBERT
from brawl_ket.poses import POSE_NAMES, POSES, SCALE, joints, pose_for
from brawl_ket.render import Renderer, draw_puppet, outlined

W, H = config.INTERNAL_WIDTH, config.INTERNAL_HEIGHT
CELL_W, CELL_H, COLS = 180, 230, 6
CELL_FLOOR = 200
ACCENTS = {"lean": P.CREAM, "heavy": P.GOLD, "toy": P.TEAL, "cat": P.GOLD}


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


def move_sheet(char=ROBERT) -> pygame.Surface:
    """Each of a character's moves, one row: every few frames of it, as the game blends them."""
    strip = 9
    sheet = pygame.Surface((strip * 130, len(char.moves) * 220))
    sheet.fill(P.INK)
    for row, (slot, move) in enumerate(char.moves.items()):
        total = move.startup + move.active + move.recovery
        f = Fighter(char, 0, 1)
        f.action, f.move, f.slot = "attack", move, slot
        y = row * 220
        for k in range(strip):
            f.frame = round(k * (total - 1) / (strip - 1))
            x = k * 130
            sheet.fill(P.NIGHT, (x + 1, y + 1, 128, 218))
            sheet.fill(P.SLATE, (x + 1, y + 200, 128, 2))
            draw_puppet(sheet, pose_for(f), char.build, (x + 62, y + 200), 1, config.PLAYER_COLORS["p1"],
                        ACCENTS[char.build])
            sheet.blit(outlined(f"{f.phase[0].upper()}{f.frame}", 8, P.MIST), (x + 4, y + 206))
        sheet.blit(outlined(f"{slot} {move.name}", 8, P.WHITE), (6, y + 6))
    return sheet


def bohr_frames(out_dir: str) -> None:
    """BOHR's specials, scripted against a ROBERT: COLLAPSE, CHARGE NOISE and MEASURE."""
    from brawl_ket.fighter import IDLE, FighterInput

    surface = pygame.Surface((W, H))
    # COLLAPSE, landing 48 px from a standing purple ROBERT: the slam bounces, the shockwave hurts
    fight = Fight({"p1": BOHR, "p2": ROBERT})
    fight.fighters["p1"].x, fight.fighters["p2"].x = 300, 348
    fight.fighters["p2"].basis = X_BASIS
    bohr, r, since = fight.fighters["p1"], Renderer(surface), None
    for i in range(80):
        inp = FighterInput(up=True) if i == 0 else \
            FighterInput(x=True) if bohr.action == "jump" and bohr.y > 60 else IDLE
        events = fight.step({"p1": inp, "p2": IDLE})
        r.draw_fight(fight, events, {"p1": 0, "p2": 0})
        if bohr.action == "attack" and bohr.phase == "active" and 30 < bohr.y < 60:
            save(surface, out_dir, "bohr_collapse_fall.png")
        if any(e.kind == "shockwave" for e in events):
            since = 0
        elif since is not None:
            since += 1
        if since in (1, 8):
            save(surface, out_dir, f"bohr_collapse_wave{since}.png")
    # CHARGE NOISE on a ROBERT 60 px away: the wind-up, and the field mid-shock
    fight = Fight({"p1": BOHR, "p2": ROBERT})
    fight.fighters["p1"].x, fight.fighters["p2"].x = 290, 350
    r = Renderer(surface)
    bohr = fight.fighters["p1"]
    for i in range(40):
        events = fight.step({"p1": FighterInput(down=True, x=i == 0)})
        r.draw_fight(fight, events, {"p1": 0, "p2": 0})
        if bohr.phase == "startup" and bohr.frame == 5:
            save(surface, out_dir, "bohr_noise_0.png")
        if bohr.phase == "active" and bohr.frame - bohr.startup == 14:
            save(surface, out_dir, "bohr_noise_1.png")
    # MEASURE from 62 px onto a purple ROBERT
    fight = Fight({"p1": BOHR, "p2": ROBERT})
    fight.fighters["p1"].x, fight.fighters["p2"].x = 290, 352
    fight.fighters["p2"].basis = X_BASIS
    r, since = Renderer(surface), None
    for i in range(40):
        events = fight.step({"p1": FighterInput(x=i == 0)})
        r.draw_fight(fight, events, {"p1": 0, "p2": 0})
        if any(e.kind == "measure" for e in events):
            since = 0
        elif since is not None:
            since += 1
        if since == 3:
            save(surface, out_dir, "bohr_measure.png")
            break


def scripted_frames(out_dir: str) -> None:
    """Moments of the colour rule, scripted at 50 px, each saved 2 frames after its event: a
    green jab bouncing off a purple rival, a throw (Y), a switch (Y on the pad), and a heavy
    late in its wind-up."""
    from brawl_ket.fighter import IDLE, FighterInput

    surface = pygame.Surface((W, H))

    def purple(fight: Fight) -> None:
        fight.fighters["p2"].basis = X_BASIS

    scripts = (
        ("fight_block", "block", lambda i: FighterInput(a=i == 0), purple),
        ("fight_throw", "hit", lambda i: FighterInput(dx=1, b=i == 0), None),
        ("fight_switch", "switch", lambda i: FighterInput(y=i == 0), None),
    )
    for name, kind, p1_input, setup in scripts:
        fight = Fight({"p1": ROBERT, "p2": ROBERT})
        fight.fighters["p1"].x, fight.fighters["p2"].x = 295, 345
        if setup is not None:
            setup(fight)
        r = Renderer(surface)
        since = None
        for i in range(90):
            events = fight.step({"p1": p1_input(i), "p2": IDLE})
            r.draw_fight(fight, events, {"p1": 0, "p2": 0})
            if since is None and any(e.kind == kind for e in events):
                since = 0
            elif since is not None:
                since += 1
            if since == 2:
                save(surface, out_dir, f"{name}.png")
                break
        else:
            print(f"never saw: {name}")
    fight = Fight({"p1": ROBERT, "p2": ROBERT})
    fight.fighters["p1"].x, fight.fighters["p2"].x = 280, 360
    r = Renderer(surface)
    for i in range(ROBERT.moves["stand.B"].startup - 1):
        r.draw_fight(fight, fight.step({"p1": FighterInput(b=i == 0), "p2": IDLE}), {"p1": 0, "p2": 0})
    save(surface, out_dir, "fight_strike.png")


def close_frame(out_dir: str) -> None:
    """ROBERT and BOHR walked all the way into each other (the push box), and two BOHRs."""
    from brawl_ket.fighter import FighterInput

    surface = pygame.Surface((W, H))
    for name, chars in (("vs_close", (ROBERT, BOHR)), ("bohr_mirror_close", (BOHR, BOHR))):
        fight = Fight({"p1": chars[0], "p2": chars[1]})
        r = Renderer(surface)
        for _ in range(120):
            r.draw_fight(fight, fight.step({"p1": FighterInput(dx=1), "p2": FighterInput(dx=-1)}),
                         {"p1": 0, "p2": 0})
        save(surface, out_dir, f"{name}.png")


def find_frames(out_dir: str, chars=(ROBERT, ROBERT), prefix: str = "fight") -> None:
    """Play bot fights until each wanted moment has been seen, saving the frame."""
    surface = pygame.Surface((W, H))
    wanted = {
        "hit": lambda f, ev, ago: ago.get("hit") == 2,
        "bot_block": lambda f, ev, ago: ago.get("block") == 3,
        "bot_switch": lambda f, ev, ago: ago.get("switch") == 2,
        "crouch": lambda f, ev, ago: sorted(x.action for x in f.fighters.values()) in (["crouch", "idle"], ["crouch", "walk"])
        and all(ago.get(k, 99) > 80 for k in ("hit", "block")),
        "shot": lambda f, ev, ago: bool(f.shots) and abs(f.shots[0].x - f.fighters["p2"].x) > 120,
        "knockdown": lambda f, ev, ago: any(x.action == "knockdown" and x.frame == 14 for x in f.fighters.values()),
    }
    for seed in range(300):
        if not wanted:
            break
        fight = Fight({"p1": chars[0], "p2": chars[1]})
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
                save(surface, out_dir, f"{prefix}_start.png")
            for name in list(wanted):
                if fight.frames_left < config.ROUND_FRAMES - 60 and wanted[name](fight, events, ago):
                    save(surface, out_dir, f"{prefix}_{name}.png")
                    if name == "hit":
                        r.show_boxes = True
                        r.draw_fight(fight, [])
                        r.show_boxes = False
                        save(surface, out_dir, f"{prefix}_boxes.png")
                    del wanted[name]
    for name in wanted:
        print(f"never saw: {prefix} {name}")


def screen_frames(out_dir: str) -> None:
    """Every screen of the match flow, driven through a real Match."""
    from brawl_ket import match as M

    surface = pygame.Surface((640, 360))
    r = Renderer(surface)
    m = M.Match(random.Random(3))

    def step(n: int = 1, inp: M.FrameInput | None = None) -> None:
        for _ in range(n):
            r.draw(m, m.update(inp or M.FrameInput()))

    def press(**kw) -> M.FrameInput:
        inp = M.FrameInput(activity=True)
        for name, (player, value) in kw.items():
            getattr(inp, name)[player] = value
        return inp

    step(4)
    save(surface, out_dir, "screen_title.png")
    step(1, press(nav=("p1", (0, 1))))
    save(surface, out_dir, "screen_title_quit.png")
    step(1, press(nav=("p1", (0, -1))))
    step(config.ATTRACT_DELAY + 200)
    save(surface, out_dir, "screen_attract.png")
    step(1, press(confirms=("p1", True)))      # stops the demo
    step(1, press(confirms=("p1", True)))
    step(4)
    save(surface, out_dir, "screen_select.png")
    step(1, press(confirms=("p1", True)))
    step(4)
    save(surface, out_dir, "screen_select_ready.png")
    step(1, press(confirms=("p2", True)))
    step(config.FPS + 4)
    save(surface, out_dir, "screen_stage_select.png")
    while M.STAGE_OPTIONS[m.stage_pick] != "toronto":
        step(1, press(nav=("p1", (1, 0))))
    step(4)
    save(surface, out_dir, "screen_stage_select_toronto.png")
    step(1, press(confirms=("p1", True)))
    step(30)
    save(surface, out_dir, "screen_how_to_play.png")
    step(1, M.FrameInput(activity=True, any_button=True))
    step(8)
    save(surface, out_dir, "screen_round.png")
    step(M.FIGHT_CALL)
    save(surface, out_dir, "screen_fight_call.png")
    step(config.ROUND_INTRO_FRAMES)
    step(1, press(pauses=("p1", True), confirms=("p1", True)))
    step(1, press(nav=("p1", (0, 1))))
    step(2)
    save(surface, out_dir, "screen_pause.png")
    step(1, press(pauses=("p1", True), confirms=("p1", True)))
    m.fight.fighters["p2"].health = 0
    step(config.FPS + 10)
    save(surface, out_dir, "screen_ko_perfect.png")
    step(config.ROUND_END_FRAMES + config.ROUND_INTRO_FRAMES)
    m.fight.fighters["p2"].health = 0
    step(config.ROUND_END_FRAMES + config.MATCH_RESULT_LOCK + 2)
    save(surface, out_dir, "screen_result.png")


def main(argv: list[str]) -> None:
    if len(argv) != 1:
        sys.exit(__doc__)
    out_dir = argv[0]
    os.makedirs(out_dir, exist_ok=True)
    pygame.init()
    for build in SCALE:
        save(pose_sheet(build), out_dir, f"poses_{build}.png")
    save(move_sheet(ROBERT), out_dir, "moves_lean.png")
    save(move_sheet(BOHR), out_dir, "moves_heavy.png")
    bohr_frames(out_dir)
    scripted_frames(out_dir)
    close_frame(out_dir)
    find_frames(out_dir)
    find_frames(out_dir, (ROBERT, BOHR), "vs")
    screen_frames(out_dir)


if __name__ == "__main__":
    main(sys.argv[1:])
