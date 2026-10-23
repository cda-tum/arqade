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
- moves_cat.png, erwin_*.png: ERWIN's moves; THE BOX superposed (green, then purple after a Y),
  the collapse (0 and 3 frames on) and the swipe; a PHOTON measuring him; POUNCE and BOX DROP;
- moves_dos.png, dos_*.png: DOS's moves; FLOPPY in flight; COPY's CTRL+C frame catching a PHOTON
  and the clipboard after it; PASTE; MOUSE CABLE out and reeling in; COPY taking BOHR's
  electricity, and PASTE crackling with it; CRT DROP;
- moves_cutie.png, cutie_*.png: M-CUTIE's moves; AMPLITUDE AMPLIFICATION charging (1, 4 and 6
  steps), its wave in flight (2 and 6 steps) and DOS pasting one back; ION TRAP arming, armed and
  closed on a ROBERT; SPIN into a ROBERT;
- moves_alice.png, kids_*.png: ALICE & BOB's moves (Alice's skeleton); the pair facing a ROBERT,
  Bob's echo of a jab, KEY EXCHANGE's toss in the air and Bob's shot, TELEPORT's flash (a swap
  past a ROBERT between them), BELL DIVE twice, Bob decohered (just hit, and later his ring
  waiting) and coming back;
- screen_select_erwin_dos.png: CHOOSE YOUR FIGHTER on ERWIN (P1) and DOS (P2);
- screen_select_cutie.png: CHOOSE YOUR FIGHTER on M-CUTIE (P1, ready: the second row) and DOS (P2);
- super_bar.png, super_bar_dos_full.png: SUPERposition's bars (DOS's one green bar half full, then
  full; ROBERT a green half and a third of purple); super_call.png, the call;
- super_bsod_freeze.png, super_bsod_blue.png, super_bsod_crash.png: DOS's BLUE SCREEN OF DEATH from
  up close: the error window over the frozen rival mid-leap, the full blue screen, CRASH!;
- super_bloch.png (the 100 px sphere rolling in), super_collapse_fall.png and super_collapse_linger.png
  (the pillar mid-fall, then standing where it fell), super_beam.png, super_nine_wait.png,
  super_nine_dash.png and super_nine_claws.png (a ghost waiting on its side, one dashing in, the
  lingering claws), super_fridge_fall.png and super_fridge_linger.png, super_otp_pass.png,
  super_otp_padlock.png, super_otp_linger.png (a key pass, the padlock, still there after) and
  super_otp_whiff.png (out of reach: the kids flash);
- screen_select_random.png: CHOOSE YOUR FIGHTER on RANDOM (P1, a silhouette under the "?") and
  ROBERT (P2);
- screen_select_kids.png: CHOOSE YOUR FIGHTER on ALICE & BOB (P1, ready) and M-CUTIE (P2), and
  kids_hud.png, their shared bar with Bob's icon, greyed while he is decohered;
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
from brawl_ket.moves import ALICE_BOB, AMP_WAVES, BOHR, DOS, ERWIN, M_CUTIE, ROBERT
from brawl_ket.poses import POSE_NAMES, POSES, SCALE, joints, pose_for
from brawl_ket.render import Renderer, draw_puppet, outlined

W, H = config.INTERNAL_WIDTH, config.INTERNAL_HEIGHT
CELL_W, CELL_H, COLS = 180, 230, 6
CELL_FLOOR = 200
ACCENTS = {"lean": P.CREAM, "heavy": P.GOLD, "toy": P.TEAL, "cat": P.GOLD, "dos": P.CREAM, "cutie": P.GOLD,
           "alice": P.CREAM, "bob": P.CREAM}


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


def select_frame(out_dir: str) -> None:
    """CHOOSE YOUR FIGHTER with ERWIN and DOS picked (their traits, DOS's Y and ALWAYS GREEN), with
    M-CUTIE (P1, in the second row) against DOS, ready, and with ALICE & BOB against M-CUTIE."""
    from brawl_ket import match as M

    surface = pygame.Surface((W, H))
    for picks, ready, name in (({"p1": 3, "p2": 4}, False, "screen_select_erwin_dos.png"),
                               ({"p1": 5, "p2": 4}, True, "screen_select_cutie.png"),
                               ({"p1": 6, "p2": 5}, True, "screen_select_kids.png"),
                               ({"p1": M.RANDOM_FIGHTER, "p2": 0}, False, "screen_select_random.png")):
        r, m = Renderer(surface), M.Match(random.Random(3))
        m.state, m.picks = M.SELECT, picks
        m.ready = {"p1": ready, "p2": False}
        for _ in range(4):
            r.draw(m, [])
        save(surface, out_dir, name)


def super_frames(out_dir: str) -> None:
    """SUPERposition: the HUD bars, the call, and every super at its key beats (section 9 of the
    spec: what changed after the first playtest)."""
    from brawl_ket import basis
    from brawl_ket.fight import Fight
    from brawl_ket.fighter import FighterInput
    from brawl_ket.moves import (BLOCH_SPHERE, CHARACTERS, DILUTION_FRIDGE, NINE_LIVES, ONE_TIME_PAD,
                                 WAVE_COLLAPSE)
    from brawl_ket.render import FALL_FRAMES, LINGER_STAY
    from brawl_ket.superpos import FULL
    surface = pygame.Surface((W, H))
    ab = FighterInput(a=True, b=True)

    def fight_of(name: str, x: float, rival_x: float) -> tuple[Fight, Renderer]:
        fight = Fight({"p1": CHARACTERS[name], "p2": ROBERT}, seed=1)
        fight.fighters["p1"].x, fight.fighters["p2"].x = x, rival_x
        fight.meters["p1"].fill = {b: fight.meters["p1"].cap for b in fight.meters["p1"].fill}
        return fight, Renderer(surface)

    def play(fight, r, shots: dict) -> None:
        """Fire, then run on, saving a frame for each (name: when(n, events, fight)) at its first match."""
        r.draw_fight(fight, fight.step({"p1": ab}), {"p1": 0, "p2": 0})
        todo = dict(shots)
        for n in range(1, 400):
            events = fight.step({})
            r.draw_fight(fight, events, {"p1": 0, "p2": 0})
            for name, when in list(todo.items()):
                if when(n, events, fight):
                    save(surface, out_dir, name)
                    del todo[name]
            if not todo:
                return
        print("not reached:", sorted(todo))

    # the bars: DOS's one green bar, half full and full; ROBERT a full green half and a third of purple
    fight, r = fight_of("DOS", 250.0, 400.0)
    fight.meters["p1"].fill = {basis.Z_BASIS: FULL}       # half of his one bar
    fight.meters["p2"].fill = {basis.Z_BASIS: FULL, basis.X_BASIS: FULL // 3}
    r.draw_fight(fight, [], {"p1": 0, "p2": 0})
    save(surface, out_dir, "super_bar.png")
    fight.meters["p1"].fill = {basis.Z_BASIS: 2 * FULL}
    for _ in range(12):
        r.draw_fight(fight, [], {"p1": 0, "p2": 0})
    save(surface, out_dir, "super_bar_dos_full.png")

    def phase(move, ph, frame=None):
        return lambda n, e, f: f.fighters["p1"].move is move and f.fighters["p1"].phase == ph \
            and (frame is None or f.fighters["p1"].frame == frame)

    def after(kind, frames):
        seen = {}

        def when(n, e, f):
            if kind not in seen and any(ev.kind == kind for ev in e):
                seen[kind] = n
            return kind in seen and n - seen[kind] == frames
        return when

    # the call; the BLUE SCREEN OF DEATH from up close: the window over the frozen rival all through
    # the leap, the 30 frames of blue, and CRASH!
    fight, r = fight_of("DOS", 250.0, 310.0)
    play(fight, r, {"super_call.png": lambda n, e, f: n == 14,
                    "super_bsod_freeze.png": lambda n, e, f: f.fighters["p2"].glitch > 0 and f.fighters["p1"].y > 60,
                    "super_bsod_blue.png": after("bsod_land", 12),
                    "super_bsod_crash.png": after("bsod_land", 34)})
    # BLOCH SPHERE, 100 px, rolling in
    fight, r = fight_of("ROBERT", 150.0, 420.0)
    play(fight, r, {"super_bloch.png": phase(BLOCH_SPHERE, "active", BLOCH_SPHERE.startup + 14)})
    # WAVEFUNCTION COLLAPSE: the pillar mid-fall, then standing where it fell
    fight, r = fight_of("BOHR", 150.0, 420.0)
    play(fight, r, {"super_collapse_fall.png": phase(WAVE_COLLAPSE, "startup", WAVE_COLLAPSE.startup - FALL_FRAMES // 2),
                    "super_collapse_linger.png": after("collapse", LINGER_STAY - 6)})
    # COHERENT BEAM
    fight, r = fight_of("PHOEBE", 150.0, 420.0)
    play(fight, r, {"super_beam.png": lambda n, e, f: n == 45 + 30})
    # NINE LIVES: a ghost waiting on its side, and one dashing in
    fight, r = fight_of("ERWIN", 220.0, 330.0)
    play(fight, r, {"super_nine_wait.png": phase(NINE_LIVES, "active", NINE_LIVES.startup + 2 * 14 - 10),
                    "super_nine_dash.png": phase(NINE_LIVES, "active", NINE_LIVES.startup + 3 * 14 - 3),
                    "super_nine_claws.png": after("swipe", 20)})
    # DILUTION FRIDGE: mid-fall over its shadow, then standing where it fell
    fight, r = fight_of("M-CUTIE", 150.0, 420.0)
    play(fight, r, {"super_fridge_fall.png": phase(DILUTION_FRIDGE, "startup",
                                                   DILUTION_FRIDGE.startup - FALL_FRAMES // 2),
                    "super_fridge_linger.png": after("fridge", LINGER_STAY - 6)})
    # ONE-TIME PAD: caught from 90 px, a key pass, and the padlock, closed and lingering
    fight, r = fight_of("ALICE & BOB", 220.0, 310.0)
    play(fight, r, {"super_otp_pass.png": phase(ONE_TIME_PAD, "active", ONE_TIME_PAD.startup + 25),
                    "super_otp_padlock.png": after("padlock", 10),
                    "super_otp_linger.png": after("padlock", LINGER_STAY - 6)})
    # ... and out of reach: the kids flash and nothing plays
    fight, r = fight_of("ALICE & BOB", 150.0, 420.0)
    play(fight, r, {"super_otp_whiff.png": after("lock_miss", 1)})


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


def erwin_frames(out_dir: str) -> None:
    """ERWIN against a ROBERT: THE BOX and its collapse, a measurement, POUNCE and SCRATCH."""
    from brawl_ket.fighter import IDLE, FighterInput

    surface = pygame.Surface((W, H))
    # THE BOX: split, switched to purple, then collapsed (seed 1: into box 1) with a swipe
    fight, r = Fight({"p1": ERWIN, "p2": ROBERT}, seed=1), Renderer(surface)
    presses = {0: FighterInput(x=True), 30: FighterInput(y=True), 60: FighterInput(a=True)}
    saves = {18: "erwin_box", 40: "erwin_box_purple", 60: "erwin_collapse_0", 63: "erwin_collapse_3",
             66: "erwin_swipe"}
    for i in range(70):
        r.draw_fight(fight, fight.step({"p1": presses.get(i, IDLE), "p2": IDLE}), {"p1": 0, "p2": 0})
        if i in saves:
            save(surface, out_dir, f"{saves[i]}.png")
    # a PHOTON into box 2 measures him
    fight, r, since = Fight({"p1": ERWIN, "p2": ROBERT}), Renderer(surface), None
    for i in range(120):
        events = fight.step({"p1": FighterInput(x=i == 0), "p2": FighterInput(x=i == 12)})
        r.draw_fight(fight, events, {"p1": 0, "p2": 0})
        if since is None and any(e.kind == "box_collapse" for e in events):
            since = 0
        elif since is not None:
            since += 1
        if since == 2:
            save(surface, out_dir, "erwin_measured.png")
            break
    # POUNCE on a crouching ROBERT, mid-leap
    fight, r = Fight({"p1": ERWIN, "p2": ROBERT}), Renderer(surface)
    fight.fighters["p2"].x = fight.fighters["p1"].x + 150
    for i in range(ERWIN.moves["crouch.X"].startup + 8):
        r.draw_fight(fight, fight.step({"p1": FighterInput(down=True, x=i == 0), "p2": FighterInput(down=True)}),
                     {"p1": 0, "p2": 0})
    save(surface, out_dir, "erwin_pounce.png")
    # BOX DROP from a jump, the box falling on a ROBERT below
    fight, r = Fight({"p1": ERWIN, "p2": ROBERT}), Renderer(surface)
    fight.fighters["p2"].x = fight.fighters["p1"].x + 30
    for i in range(24):
        inp = FighterInput(up=True) if i == 0 else FighterInput(x=i == 15)
        r.draw_fight(fight, fight.step({"p1": inp, "p2": IDLE}), {"p1": 0, "p2": 0})
    save(surface, out_dir, "erwin_box_drop.png")


def dos_frames(out_dir: str) -> None:
    """DOS against a ROBERT: FLOPPY, COPY and PASTE, MOUSE CABLE and CRT DROP; and against a
    BOHR, COPY taking his electricity and PASTE crackling with it."""
    from brawl_ket.fighter import IDLE, FighterInput

    surface = pygame.Surface((W, H))

    def scene(name, presses, frames, rival_x=None, rival=IDLE, setup=None):
        fight, r = Fight({"p1": DOS, "p2": ROBERT}), Renderer(surface)
        if rival_x is not None:
            fight.fighters["p2"].x = rival_x
        if setup is not None:
            setup(fight)
        for i in range(frames):
            r.draw_fight(fight, fight.step({"p1": presses(i, fight), "p2": rival}), {"p1": 0, "p2": 0})
        save(surface, out_dir, f"{name}.png")
        return fight

    scene("dos_floppy", lambda i, f: FighterInput(x=i == 0), DOS.moves["stand.X"].startup + 30)
    # COPY against ROBERT's PHOTON: the frame up as the shot arrives, then the catch and the
    # clipboard on the HUD
    fight, r = Fight({"p1": DOS, "p2": ROBERT}), Renderer(surface)
    dos = fight.fighters["p1"]
    for i in range(90):
        near = bool(fight.shots) and abs(fight.shots[0].x - dos.x) < 80 and dos.move is None
        events = fight.step({"p1": FighterInput(y=near), "p2": FighterInput(x=i == 0)})
        r.draw_fight(fight, events, {"p1": 0, "p2": 0})
        if dos.move is not None and dos.move.catch is not None and fight.shots:
            save(surface, out_dir, "dos_copy.png")
        if any(e.kind == "copy" for e in events):
            for _ in range(4):
                r.draw_fight(fight, fight.step({}), {"p1": 0, "p2": 0})
            save(surface, out_dir, "dos_copied.png")
            break
    # PASTE: a purple PHOTON fired back
    scene("dos_paste", lambda i, f: FighterInput(y=i == 0), DOS.extra["paste"].startup + 12,
          setup=lambda f: setattr(f.fighters["p1"], "clipboard", (ROBERT.moves["stand.X"], "X")))
    mouse = DOS.moves["crouch.X"]
    scene("dos_mouse", lambda i, f: FighterInput(down=True, x=i == 0), mouse.startup + 8,
          rival_x=config.START_X["p1"] + 170)
    scene("dos_mouse_reeled", lambda i, f: FighterInput(down=True, x=i == 0), mouse.startup + 22,
          rival_x=config.START_X["p1"] + 170)
    # COPY against BOHR's CHARGE NOISE (purple), then PASTE: DOS crackling purple
    noise = BOHR.moves["crouch.X"]
    fight, r = Fight({"p1": DOS, "p2": BOHR}), Renderer(surface)
    dos, bohr = fight.fighters["p1"], fight.fighters["p2"]
    bohr.x, bohr.basis = dos.x + 60, "X"
    for i in range(noise.startup + 3):
        r.draw_fight(fight, fight.step({"p1": FighterInput(y=i == noise.startup - 3),
                                        "p2": FighterInput(down=True, x=i == 0)}), {"p1": 0, "p2": 0})
    save(surface, out_dir, "dos_copy_noise.png")
    while dos.action == "attack" or bohr.action == "attack":
        r.draw_fight(fight, fight.step({}), {"p1": 0, "p2": 0})
    for i in range(noise.startup + 6):
        r.draw_fight(fight, fight.step({"p1": FighterInput(y=i == 0)}), {"p1": 0, "p2": 0})
    save(surface, out_dir, "dos_paste_noise.png")
    scene("dos_crt_drop", lambda i, f: FighterInput(up=True) if i == 0 else FighterInput(x=i == 9), 16,
          rival_x=config.START_X["p1"] + 30)


def cutie_frames(out_dir: str) -> None:
    """M-CUTIE against a ROBERT (and a DOS): the charge, the wave, the trap and SPIN."""
    from brawl_ket.fighter import IDLE, FighterInput

    surface = pygame.Surface((W, H))

    def scene(name, presses, frames, rival_x=None, rival=lambda i: IDLE, other=ROBERT, setup=None):
        fight, r = Fight({"p1": M_CUTIE, "p2": other}), Renderer(surface)
        if rival_x is not None:
            fight.fighters["p2"].x = rival_x
        if setup is not None:
            setup(fight)
        for i in range(frames):
            r.draw_fight(fight, fight.step({"p1": presses(i), "p2": rival(i)}), {"p1": 0, "p2": 0})
        save(surface, out_dir, f"{name}.png")

    for steps in (1, 4, 6):         # charging: a press every 4 frames, saved on the last one (6 fires at once)
        last = 4 * (steps - 1)
        scene(f"cutie_charge_{steps}", lambda i, n=last: FighterInput(x=i % 4 == 0 and i <= n),
              last + (0 if steps == 6 else 1))
    for steps in (2, 6):            # the wave, well on its way
        last = 4 * (steps - 1)
        scene(f"cutie_wave_{steps}", lambda i, n=last: FighterInput(x=i % 4 == 0 and i <= n),
              last + config.CHARGE_WAIT + AMP_WAVES[0].startup + 20)
    trap = M_CUTIE.moves["crouch.X"]
    scene("cutie_trap_arming", lambda i: FighterInput(down=True, x=i == 0), trap.startup + 4)
    scene("cutie_trap_armed", lambda i: FighterInput(down=True, x=i == 0), trap.startup + config.TRAP_ARM + 4)
    scene("cutie_trap_closed", lambda i: FighterInput(down=True, x=i == 0), 80,
          rival=lambda i: FighterInput(dx=-1) if i > 30 else IDLE)
    scene("cutie_spin", lambda i: FighterInput(up=i == 0, x=i == 5), 5 + M_CUTIE.moves["air.X"].startup + 8,
          rival_x=config.START_X["p1"] + 90)
    scene("cutie_dos_paste", lambda i: IDLE, DOS.extra["paste"].startup + 14, other=DOS,
          rival=lambda i: FighterInput(y=i == 0),
          setup=lambda f: setattr(f.fighters["p2"], "clipboard", (AMP_WAVES[3], "Z")))


def kids_frames(out_dir: str) -> None:
    """ALICE & BOB (P1) against a ROBERT: the echo, KEY EXCHANGE, TELEPORT, BELL DIVE, decoherence."""
    from brawl_ket.fighter import IDLE, FighterInput

    surface = pygame.Surface((W, H))

    def scene(name, presses, frames, rival_x=430.0, setup=None, each=None):
        fight, r = Fight({"p1": ALICE_BOB, "p2": ROBERT}), Renderer(surface)
        fight.fighters["p2"].x = rival_x
        if setup is not None:
            setup(fight)
        for i in range(frames):
            if each is not None:
                each(i, fight)
            r.draw_fight(fight, fight.step({"p1": presses(i), "p2": IDLE}), {"p1": 0, "p2": 0})
        save(surface, out_dir, f"{name}.png")

    scene("kids_idle", lambda i: IDLE, 4)
    scene("kids_echo", lambda i: FighterInput(a=i == 0), 13)          # Alice recovering, Bob winding up
    scene("kids_toss", lambda i: FighterInput(x=i == 0), ALICE_BOB.moves["stand.X"].startup + 9)
    scene("kids_shot", lambda i: FighterInput(x=i == 0), ALICE_BOB.moves["stand.X"].startup + 16 + 12)
    scene("kids_teleport", lambda i: FighterInput(down=True, x=i == 0), ALICE_BOB.moves["crouch.X"].startup + 3,
          each=lambda i, f: setattr(f.fighters["p2"], "x", f.fighters["p1"].x - 20.0) if i == 2 else None)
    scene("kids_bell_dive", lambda i: FighterInput(up=True) if i == 0 else FighterInput(x=i == 14), 30)
    scene("kids_decohered", lambda i: IDLE, 6, setup=lambda f: f.echoes["p1"].decohere())
    scene("kids_gone", lambda i: IDLE, 60, setup=lambda f: f.echoes["p1"].decohere())
    scene("kids_back", lambda i: IDLE, config.DECOHERE_FRAMES + 4, setup=lambda f: f.echoes["p1"].decohere())
    fight, r = Fight({"p1": ROBERT, "p2": ALICE_BOB}), Renderer(surface)       # their bar on P2's side
    fight.echoes["p2"].decohere()
    r.draw_fight(fight, fight.step({}), {"p1": 0, "p2": 1})
    save(surface, out_dir, "kids_hud.png")


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
    save(move_sheet(ERWIN), out_dir, "moves_cat.png")
    erwin_frames(out_dir)
    save(move_sheet(DOS), out_dir, "moves_dos.png")
    dos_frames(out_dir)
    save(move_sheet(M_CUTIE), out_dir, "moves_cutie.png")
    cutie_frames(out_dir)
    save(move_sheet(ALICE_BOB), out_dir, "moves_alice.png")
    kids_frames(out_dir)
    bohr_frames(out_dir)
    scripted_frames(out_dir)
    close_frame(out_dir)
    find_frames(out_dir)
    find_frames(out_dir, (ROBERT, BOHR), "vs")
    screen_frames(out_dir)
    select_frame(out_dir)
    super_frames(out_dir)


if __name__ == "__main__":
    main(sys.argv[1:])
