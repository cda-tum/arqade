"""Render Brawl-Ket's puppets and fight frames to PNGs, to check the look
without a cabinet.

    cd brawl-ket && uv run python tools/snapshot.py OUT_DIR

Writes:
- poses_lean.png, poses_heavy.png: every pose in POSE_NAMES, labelled, facing
  right, in P1's colours;
- moves_lean.png, moves_heavy.png: every TRIO / QUINT move as a strip of frames, as pose_for
  blends it;
- code_tags.png, code_tags_quint.png: the d=3 / d=5 code tag close up (x4 on top of the x2
  save) in its states: normal, t lights flipped (danger, both beats of the pulse), the green
  flash after a correction, the red flash after a logical error;
- fight_danger.png: a bot fight at the moment a code is one hit from a logical error;
- fight_glint.png, fight_glint_sweep.png: a neutral heavy / sweep late in its 24-frame wind-up,
  with the telegraph glint on the striking hand / foot (and fight_glint_off.png, a blink-off
  frame of the heavy); quint_glint.png, quint_glint_sweep.png: QUINT's, late in its 28 frames;
- quint_collapse_*.png: QUINT's COLLAPSE next to a standing TRIO: the fall, the landing
  shockwave just after it opens, and spread out;
- quint_reencode_*.png: a crouching QUINT with two lights flipped wipes them with RE-ENCODE;
- quint_grab.png: the SYNDROME GRAB connecting;
- vs_*.png: the same bot-fight moments as fight_*.png, TRIO (P1) against QUINT (P2), and
  vs_close.png, the two walked into each other;
- screen_*.png: the match flow: the title, the attract demo, select (and with P1 ready),
  the ROUND 1 and FIGHT! calls, the pause menu, a K.O. with PERFECT, and the result;
- fight_start.png (the fighters walking in), fight_hit.png, fight_logical.png, fight_crouch.png, fight_shot.png,
  fight_knockdown.png: bot-against-bot frames at those moments (fight_boxes.png
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

from brawl_ket import config, qec
from brawl_ket import palette as P
from brawl_ket.bot import Bot
from brawl_ket.fight import Fight
from brawl_ket.fighter import Fighter
from brawl_ket.moves import QUINT, TRIO
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


def move_sheet(char=TRIO) -> pygame.Surface:
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


def _flip_t(code: qec.Code) -> None:
    for _ in range(code.t):
        code.hit(qec.X)


def tag_sheet(char=TRIO) -> pygame.Surface:
    """The code tag in each of its states, cropped around p1's and p2's heads and magnified."""
    surface = pygame.Surface((W, H))
    zoom, crop = 4, pygame.Rect(0, 0, 90 if char.distance == 3 else 110, 46)
    cases = [
        ("normal", lambda c, r, k: None),
        ("t flipped: danger (bright)", lambda c, r, k: (_flip_t(c), setattr(r, "t", 0))),
        ("t flipped: danger (dim)", lambda c, r, k: (_flip_t(c), setattr(r, "t", DANGER_BEAT // 2))),
        ("corrected: green flash", lambda c, r, k: r.flash.__setitem__(k, (P.GOOD, 21))),
        ("logical: red flash", lambda c, r, k: r.flash.__setitem__(k, (P.BAD, 21))),
    ]
    sheet = pygame.Surface((len(cases) * crop.w * zoom, 2 * (crop.h * zoom + 16)))
    sheet.fill(P.INK)
    for col, (label, setup) in enumerate(cases):
        for row, key in enumerate(("p1", "p2")):
            fight = Fight({"p1": char, "p2": char})
            fight.fighters["p1"].x, fight.fighters["p2"].x = 260, 380
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


def glint_frames(out_dir: str, char=TRIO, prefix: str = "fight") -> None:
    """A scripted heavy and a scripted sweep, frozen in the telegraph window."""
    from brawl_ket.fighter import IDLE, FighterInput

    surface = pygame.Surface((W, H))
    startup = char.moves["stand.B"].startup
    for name, pressed, crouch in (
        (f"{prefix}_glint", FighterInput(b=True), False),
        (f"{prefix}_glint_sweep", FighterInput(down=True, b=True), True),
    ):
        fight = Fight({"p1": char, "p2": TRIO})
        fight.fighters["p1"].x, fight.fighters["p2"].x = 250, 350
        if crouch:
            fight.fighters["p1"].code.switch()
        r = Renderer(surface)
        held = FighterInput(down=crouch)
        for i in range(startup - 1):
            r.draw_fight(fight, fight.step({"p1": pressed if i == 0 else held, "p2": IDLE}), {"p1": 0, "p2": 0})
            if fight.fighters["p1"].frame == startup - 3:
                save(surface, out_dir, f"{name}.png")
            if name == "fight_glint" and fight.fighters["p1"].frame == 18:
                save(surface, out_dir, "fight_glint_off.png")      # the blink's dark phase


def quint_frames(out_dir: str) -> None:
    """QUINT's specials, scripted against a TRIO: COLLAPSE, RE-ENCODE and SYNDROME GRAB."""
    from brawl_ket.fighter import IDLE, FighterInput

    surface = pygame.Surface((W, H))
    # COLLAPSE, landing 48 px from a standing TRIO
    fight = Fight({"p1": QUINT, "p2": TRIO})
    fight.fighters["p1"].x, fight.fighters["p2"].x = 300, 348
    quint, r, since = fight.fighters["p1"], Renderer(surface), None
    for i in range(80):
        inp = FighterInput(up=True) if i == 0 else \
            FighterInput(x=True) if quint.action == "jump" and quint.y > 60 else IDLE
        events = fight.step({"p1": inp, "p2": IDLE})
        r.draw_fight(fight, events, {"p1": 0, "p2": 0})
        if quint.action == "attack" and quint.phase == "active" and 30 < quint.y < 60:
            save(surface, out_dir, "quint_collapse_fall.png")
        if any(e.kind == "shockwave" for e in events):
            since = 0
        elif since is not None:
            since += 1
        if since in (1, 8):
            save(surface, out_dir, f"quint_collapse_wave{since}.png")
    # RE-ENCODE: a crouching QUINT with two lights flipped
    fight = Fight({"p1": TRIO, "p2": QUINT})
    fight.fighters["p1"].x, fight.fighters["p2"].x = 240, 380
    quint, r = fight.fighters["p2"], Renderer(surface)
    quint.code.switch()
    down = FighterInput(down=True)
    for i in range(4):
        r.draw_fight(fight, fight.step({"p2": down}), {"p1": 0, "p2": 0})
    quint.code.hit(qec.Z)
    quint.code.hit(qec.Z)
    r.draw_fight(fight, fight.step({"p2": down}), {"p1": 0, "p2": 0})
    save(surface, out_dir, "quint_reencode_0_before.png")
    since = None
    for i in range(30):
        events = fight.step({"p2": FighterInput(down=True, x=i == 0)})
        r.draw_fight(fight, events, {"p1": 0, "p2": 0})
        if any(e.kind == "reencode" for e in events):
            since = 0
        elif since is not None:
            since += 1
        if since in (1, 8):
            save(surface, out_dir, f"quint_reencode_{since}.png")
    # SYNDROME GRAB from 62 px
    fight = Fight({"p1": QUINT, "p2": TRIO})
    fight.fighters["p1"].x, fight.fighters["p2"].x = 290, 352
    r = Renderer(surface)
    for i in range(40):
        events = fight.step({"p1": FighterInput(x=i == 0)})
        r.draw_fight(fight, events, {"p1": 0, "p2": 0})
        if any(e.kind == "logical" for e in events):
            save(surface, out_dir, "quint_grab.png")
            break


def close_frame(out_dir: str) -> None:
    """TRIO and QUINT walked all the way into each other (the push box), and two QUINTs."""
    from brawl_ket.fighter import FighterInput

    surface = pygame.Surface((W, H))
    for name, chars in (("vs_close", (TRIO, QUINT)), ("quint_mirror_close", (QUINT, QUINT))):
        fight = Fight({"p1": chars[0], "p2": chars[1]})
        r = Renderer(surface)
        for _ in range(120):
            r.draw_fight(fight, fight.step({"p1": FighterInput(dx=1), "p2": FighterInput(dx=-1)}),
                         {"p1": 0, "p2": 0})
        save(surface, out_dir, f"{name}.png")


def find_frames(out_dir: str, chars=(TRIO, TRIO), prefix: str = "fight") -> None:
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
    save(move_sheet(TRIO), out_dir, "moves_lean.png")
    save(move_sheet(QUINT), out_dir, "moves_heavy.png")
    save(tag_sheet(TRIO), out_dir, "code_tags.png")
    save(tag_sheet(QUINT), out_dir, "code_tags_quint.png")
    glint_frames(out_dir)
    glint_frames(out_dir, QUINT, "quint")
    quint_frames(out_dir)
    close_frame(out_dir)
    find_frames(out_dir)
    find_frames(out_dir, (TRIO, QUINT), "vs")
    screen_frames(out_dir)


if __name__ == "__main__":
    main(sys.argv[1:])
