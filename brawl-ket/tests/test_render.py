"""Smoke tests: bot-against-bot fights render without errors."""

import importlib.util
from pathlib import Path

import pygame
import pytest

from brawl_ket import palette as P
from brawl_ket import basis
from brawl_ket.basis import X_BASIS, Z_BASIS
from brawl_ket.bot import Bot
from brawl_ket.config import FLOOR_Y, INTERNAL_HEIGHT, INTERNAL_WIDTH
from brawl_ket.fight import Event, Fight
from brawl_ket.moves import CHARACTERS, BOHR, ROBERT
from brawl_ket.render import BASIS_BODY, ERROR_COLOUR, GREEN, PURPLE, Renderer

PAIRINGS = [(a, b) for a in CHARACTERS.values() for b in CHARACTERS.values()]


@pytest.fixture
def surface():
    pygame.init()
    return pygame.Surface((INTERNAL_WIDTH, INTERNAL_HEIGHT))


def bot_frames(n, seed=1, chars=(ROBERT, ROBERT)):
    """n frames of bot-against-bot fights, starting a new round when one ends."""
    fight, bots = None, {}
    for i in range(n):
        if fight is None or fight.over:
            fight = Fight({"p1": chars[0], "p2": chars[1]})
            bots = {"p1": Bot("p1", seed + i), "p2": Bot("p2", seed + i + 1000)}
        yield fight, fight.step({k: b.input(fight) for k, b in bots.items()})


@pytest.mark.parametrize("chars", PAIRINGS, ids=lambda cs: "-".join(c.name for c in cs))
def test_900_bot_frames_draw(surface, chars):
    r = Renderer(surface)
    kinds = set()
    for fight, events in bot_frames(900, chars=chars):
        r.draw_fight(fight, events)
        kinds |= {e.kind for e in events}
    assert "hit" in kinds                   # the effects were exercised (blocks: their own test)


def test_the_shockwave_effect_draws_and_expires(surface):
    r = Renderer(surface)
    fight = Fight({"p1": BOHR, "p2": ROBERT})
    r.draw_fight(fight, [])
    r.draw_fight(fight, [Event("shockwave", "p1", "Z", fight.fighters["p1"].x, FLOOR_Y)])
    assert {fx.kind for fx in r.effects} == {"wave"}
    # the wave is drawn along the floor, around where the slam landed, then in Z's purple
    x = round(fight.fighters["p1"].x)
    row = {tuple(surface.get_at((i, FLOOR_Y - 2)))[:3] for i in range(x - 50, x + 50)}
    assert P.WHITE in row                           # the white flash of the impact
    for _ in range(8):                              # and it spreads out to the shockwave's reach
        r.draw_fight(fight, [])
    far = {tuple(surface.get_at((i, j)))[:3] for i in range(x - 56, x - 30) for j in range(FLOOR_Y - 12, FLOOR_Y + 8)}
    assert far & {PURPLE, P.lighten(PURPLE, 0.35)}
    for _ in range(120):
        r.draw_fight(fight, [])
    assert not r.effects


def test_round_pips_draw(surface):
    r = Renderer(surface)
    fight = Fight({"p1": ROBERT, "p2": ROBERT})
    for wins in ({"p1": 0, "p2": 0}, {"p1": 1, "p2": 0}, {"p1": 1, "p2": 1}):
        r.draw_fight(fight, [], wins)


def test_effects_expire(surface):
    r = Renderer(surface)
    fight = Fight({"p1": ROBERT, "p2": ROBERT})
    r.draw_fight(fight, [Event("hit", "p2", "X", 330, 220), Event("block", "p1", "Z", 300, 250)])
    assert r.effects
    for _ in range(240):
        r.draw_fight(fight, [])
    assert not r.effects
    assert r.shake == 0


def test_the_floor_is_drawn_where_the_fighters_stand(surface):
    r = Renderer(surface)
    r.draw_fight(Fight({"p1": ROBERT, "p2": ROBERT}), [])
    # away from the fighters, just below FLOOR_Y is floor and just above it is wall
    xs = range(0, 150, 3)
    floor = {tuple(surface.get_at((x, FLOOR_Y + 3)))[:3] for x in xs} - {P.INK}
    wall = {tuple(surface.get_at((x, FLOOR_Y - 12)))[:3] for x in xs} - {P.INK}
    assert floor and wall and not floor & wall


BLANK = (1, 2, 3)


def test_a_cancel_blends_out_of_the_pose_drawn(surface):
    from brawl_ket.poses import EASE_FRAMES, POSES, lerp

    r = Renderer(surface)
    f = Fight({"p1": ROBERT, "p2": ROBERT}).fighters["p1"]
    jab, heavy = ROBERT.moves["stand.A"], ROBERT.moves["stand.B"]
    f.action, f.move, f.slot, f.frame = "attack", jab, "stand.A", jab.startup
    assert r._pose("p1", f) == POSES["jab_hit"]
    f.move, f.slot, f.frame = heavy, "stand.B", 0          # cancelled into the heavy
    assert r._pose("p1", f) == lerp(POSES["jab_hit"], POSES["heavy_wind"], 1 / EASE_FRAMES)
    f.move, f.slot, f.frame = jab, "stand.A", jab.startup   # and a jab into a jab: frame went back
    r._pose("p1", f)
    f.frame = 0
    assert r._pose("p1", f) == lerp(POSES["jab_hit"], POSES["jab_wind"], 1 / EASE_FRAMES)


def test_bohr_is_drawn_broader_than_robert(surface):
    # the same pose (arms up, out of the way): across the chest, BOHR is far broader
    from brawl_ket.poses import POSES, joints
    from brawl_ket.render import draw_puppet

    widths = {}
    for c in (ROBERT, BOHR):
        surface.fill(BLANK)
        pose = POSES["slam"]
        draw_puppet(surface, pose, c.build, (320, FLOOR_Y), 1, (64, 136, 248), P.GOLD)
        j = joints(pose, c.build, (320, FLOOR_Y), 1)
        chest = round(j["hip"][1] + 0.6 * (j["shoulder_f"][1] - j["hip"][1]))
        xs = [x for x in range(INTERNAL_WIDTH) if tuple(surface.get_at((x, chest)))[:3] != BLANK]
        widths[c.name] = max(xs) - min(xs) + 1
    assert widths["BOHR"] >= widths["ROBERT"] * 1.6, widths


def test_every_match_screen_draws(surface):
    """Drive a real Match through every state (and the pause menu), drawing each frame."""
    import random

    from brawl_ket import config
    from brawl_ket import match as M

    r = Renderer(surface)
    m = M.Match(random.Random(2))
    seen = set()

    def step(n=1, **presses):
        for _ in range(n):
            inp = M.FrameInput(activity=bool(presses))
            for name, (player, value) in presses.items():
                if player is None:
                    setattr(inp, name, value)
                else:
                    getattr(inp, name)[player] = value
            r.draw(m, m.update(inp))
            seen.add((m.state, m.paused, m.attract is not None))

    step(config.ATTRACT_DELAY + 120)                # the title, then its demo
    step(confirms=("p1", True))
    step(confirms=("p1", True))                     # select
    step(confirms=("p1", True))
    step(nav=("p2", (1, 0)))
    step(confirms=("p2", True))
    step(nav=("p1", (1, 0)))                        # stage select: LAB
    step(M.STAGE_LOCK)
    step(confirms=("p1", True))
    step(config.TUTORIAL_LOCK + 30)                 # HOW TO PLAY
    step(any_button=(None, True))
    step(config.ROUND_INTRO_FRAMES // 2)
    step(pauses=("p1", True), confirms=("p1", True))
    step(3)
    step(pauses=("p1", True), confirms=("p1", True))
    step(config.ROUND_INTRO_FRAMES)                 # the fight
    for _ in range(2):
        m.fight.fighters["p2"].health = 0
        step(config.ROUND_END_FRAMES + config.ROUND_INTRO_FRAMES)
    step(config.MATCH_RESULT_LOCK + 2)
    states = {s for s, _, _ in seen}
    assert states == {M.TITLE, M.SELECT, M.STAGE_SELECT, M.TUTORIAL, M.ROUND_INTRO, M.FIGHT, M.ROUND_END,
                      M.MATCH_RESULT}
    assert (M.TITLE, False, True) in seen and (M.ROUND_INTRO, True, False) in seen


def test_a_new_popup_replaces_an_older_one_beside_it(surface):
    # jab, heavy: the heavy's Z! must not be drawn over the jab's X!, still rising
    r = Renderer(surface)
    fight = Fight({"p1": ROBERT, "p2": ROBERT})
    r.draw_fight(fight, [Event("hit", "p2", basis.X, 400, 200)])
    for _ in range(10):
        r.draw_fight(fight, [])
    r.draw_fight(fight, [Event("hit", "p2", basis.Z, 404, 202), Event("hit", "p1", basis.X, 100, 200)])
    assert {fx.x: fx.text for fx in r.effects if fx.kind == "popup"} == {404: "Z!", 100: "X!"}


def test_popups_started_in_the_same_frame_all_survive(surface):
    # only pop-ups from earlier frames are replaced, never one this frame's events just started
    r = Renderer(surface)
    fight = Fight({"p1": ROBERT, "p2": ROBERT})
    r.draw_fight(fight, [Event("hit", "p2", basis.X, 400, 200), Event("hit", "p1", basis.X, 410, 200)])
    assert sorted(fx.x for fx in r.effects if fx.kind == "popup") == [400, 410]


def body_pixels(surface, r, fight, key):
    """The colours drawn in a small box round the fighter's torso."""
    f = fight.fighters[key]
    x = round(f.x)
    return {tuple(surface.get_at((i, j)))[:3] for i in range(x - 4, x + 5) for j in range(FLOOR_Y - 90, FLOOR_Y - 60)}


def test_a_body_is_drawn_in_its_basis_colour(surface):
    r = Renderer(surface)
    fight = Fight({"p1": ROBERT, "p2": BOHR})
    fight.fighters["p2"].basis = X_BASIS
    r.draw_fight(fight, [])
    assert GREEN in body_pixels(surface, r, fight, "p1") and PURPLE not in body_pixels(surface, r, fight, "p1")
    assert PURPLE in body_pixels(surface, r, fight, "p2") and GREEN not in body_pixels(surface, r, fight, "p2")
    assert BASIS_BODY == {Z_BASIS: GREEN, X_BASIS: PURPLE}
    assert ERROR_COLOUR[basis.X] == GREEN and ERROR_COLOUR[basis.Z] == PURPLE


def test_a_block_pings_in_the_attacks_colour(surface):
    r = Renderer(surface)
    fight = Fight({"p1": ROBERT, "p2": ROBERT})
    r.draw_fight(fight, [Event("block", "p2", basis.Z, 400, 200)])
    (ping,) = [fx for fx in r.effects if fx.kind == "ping"]
    assert ping.color == PURPLE and not [fx for fx in r.effects if fx.kind == "popup"]
    for _ in range(30):
        r.draw_fight(fight, [])
    assert not r.effects


def test_the_rings_under_the_feet_are_the_players_colours(surface):
    from brawl_ket.config import PLAYER_COLORS
    r = Renderer(surface)
    fight = Fight({"p1": ROBERT, "p2": ROBERT})
    r.draw_fight(fight, [])
    for key in ("p1", "p2"):
        x = round(fight.fighters[key].x)
        ring = {tuple(surface.get_at((i, j)))[:3] for i in range(x - 34, x + 35) for j in range(FLOOR_Y - 6, FLOOR_Y + 10)}
        assert PLAYER_COLORS[key] in ring, key


def test_the_badges_show_each_basis(surface):
    r = Renderer(surface)
    fight = Fight({"p1": ROBERT, "p2": ROBERT})
    fight.fighters["p2"].basis = X_BASIS
    r.draw_fight(fight, [])
    from brawl_ket.render import BAR_H, BAR_W, BAR_Y
    y = BAR_Y + BAR_H // 2
    left = {tuple(surface.get_at((x, y)))[:3] for x in range(20 + BAR_W + 4, 20 + BAR_W + 36)}
    right = {tuple(surface.get_at((x, y)))[:3] for x in range(INTERNAL_WIDTH - 20 - BAR_W - 36, INTERNAL_WIDTH - 20 - BAR_W - 4)}
    assert GREEN in left and PURPLE not in left
    assert PURPLE in right and GREEN not in right


def test_a_switch_flashes_the_body_white_with_an_h(surface):
    r = Renderer(surface)
    fight = Fight({"p1": ROBERT, "p2": ROBERT})
    r.draw_fight(fight, [])
    r.draw_fight(fight, [Event("switch", "p1")])
    assert [fx.text for fx in r.effects if fx.kind == "popup"] == ["H"]
    assert r.body_flash["p1"][0] == P.WHITE
    for _ in range(40):
        r.draw_fight(fight, [])
    assert r.body_flash["p1"] == (None, 0)


def limb_colours(surface, r, f, joints_, a, b, n=9):
    """The colours along the middle third of the segment between two joints (clear of the
    ink rings of the joints and the fist or foot at its end)."""
    pa, pb = joints_[a], joints_[b]
    pts = [(pa[0] + (pb[0] - pa[0]) * k / n, pa[1] + (pb[1] - pa[1]) * k / n) for k in range(3, n - 3)]
    return {tuple(surface.get_at((round(x), round(y))))[:3] for x, y in pts}


def test_the_whole_striking_limb_is_drawn_in_the_attacks_colour(surface):
    from brawl_ket.fighter import FighterInput
    from brawl_ket.poses import joints
    # a green fighter: A green (its own colour), B purple (the other), and a crouching B
    # (the sweep) strikes with the leg
    for button, down, colour, a, b in (("a", False, GREEN, "elbow_f", "hand_f"),
                                       ("b", False, PURPLE, "elbow_f", "hand_f"),
                                       ("b", True, PURPLE, "knee_f", "foot_f")):
        r = Renderer(surface)
        fight = Fight({"p1": ROBERT, "p2": ROBERT})
        fight.fighters["p2"].x = 600
        for i in range(3):
            r.draw_fight(fight, fight.step({"p1": FighterInput(down=down, **{button: i == 0})}))
        f = fight.fighters["p1"]
        assert f.action == "attack" and f.phase == "startup", button
        j = joints(r.pose_last["p1"], ROBERT.build, (f.x, FLOOR_Y - f.y), f.facing)
        seen = limb_colours(surface, r, f, j, a, b)
        assert seen == {colour} or seen <= {colour, P.lighten(colour, 0.5)}, (button, down, seen)


def test_each_hud_shows_its_players_a_and_b_colours(surface):
    from brawl_ket.render import legend_colours
    fight = Fight({"p1": ROBERT, "p2": ROBERT})
    fight.fighters["p2"].basis = X_BASIS
    assert legend_colours(fight.fighters["p1"]) == {"A": GREEN, "B": PURPLE}
    assert legend_colours(fight.fighters["p2"]) == {"A": PURPLE, "B": GREEN}
    r = Renderer(surface)
    r.draw_fight(fight, [])
    assert r.legend_rects["p1"]["A"].collidepoint(r.legend_rects["p1"]["A"].center)
    for key, want in (("p1", {"A": GREEN, "B": PURPLE}), ("p2", {"A": PURPLE, "B": GREEN})):
        for button, colour in want.items():
            rect = r.legend_rects[key][button]
            inside = {tuple(surface.get_at((x, y)))[:3] for x in range(rect.left, rect.right)
                      for y in range(rect.top, rect.bottom)}
            assert colour in inside, (key, button)


def test_a_live_strike_leaves_a_trail(surface):
    from brawl_ket.fighter import FighterInput
    r = Renderer(surface)
    fight = Fight({"p1": ROBERT, "p2": ROBERT})
    fight.fighters["p2"].x = 600
    for i in range(ROBERT.moves["stand.B"].startup + 3):
        r.draw_fight(fight, fight.step({"p1": FighterInput(b=i == 0)}))
    assert fight.fighters["p1"].phase == "active"
    assert len(r.trails["p1"]) >= 2
def test_the_teaching_text_is_ascii_capitals():
    from brawl_ket.render import (ANY_BUTTON, BUTTON_JOBS, CARD_LINES, CLASSICAL_LINES, GOAL_LINES, HINT, LESSON_LINES,
                                  MOVE_LABELS, RULE_LINES, TRAITS)
    parts = (*CARD_LINES, *LESSON_LINES)
    for text in (HINT, ANY_BUTTON, *RULE_LINES, *CLASSICAL_LINES, *TRAITS.values(), *MOVE_LABELS.values(),
                 *GOAL_LINES, *(job for _b, job in BUTTON_JOBS),
                 *("".join(t for t, _ in line) for line in parts)):
        assert text.isascii() and text == text.upper(), text


def test_the_how_to_play_card_fits_the_screen():
    """Every line of it in the 8 px font, inside the 640 px screen and its own boxes."""
    from brawl_ket.render import GOAL_LINES, LESSON_LINES, LESSON_VIEW, font
    pygame.init()
    for line in GOAL_LINES:
        assert font(8).size(line)[0] <= INTERNAL_WIDTH - 32, line
    for parts in LESSON_LINES:
        text = "".join(t for t, _ in parts)
        assert font(8).size(text)[0] <= LESSON_VIEW.w - 16, text


def test_the_how_to_play_card_draws_its_scene_and_title_draws_quit(surface):
    import random

    from brawl_ket import config
    from brawl_ket import match as M
    r = Renderer(surface)
    m = M.Match(random.Random(1))
    inp = M.FrameInput(activity=True)
    inp.nav["p1"] = (0, -1)                 # up: round to the last row
    r.draw(m, m.update(inp))
    assert M.TITLE_ITEMS[m.title_index] == "QUIT"
    for kind in ("p1", "p1", "p2", "p1"):
        if m.state == M.STAGE_SELECT:
            for _ in range(M.STAGE_LOCK):
                m.update(M.FrameInput())
            m.stage_pick = M.STAGE_OPTIONS.index("cryo")
        inp = M.FrameInput(activity=True)
        inp.confirms[kind] = True
        if m.state == M.TITLE:
            inp.pauses[kind] = True         # Start: QUIT is selected, Start still plays
        r.draw(m, m.update(inp))
    assert m.state == M.TUTORIAL
    before = surface.copy()
    for _ in range(config.TUTORIAL_LOCK + 40):
        r.draw(m, m.update(M.FrameInput()))
    assert m.state == M.TUTORIAL and r._lesson is not None
    assert r._lesson.stage_name == "cryo"                       # the scene is in the match's room
    assert pygame.image.tostring(before, "RGB") != pygame.image.tostring(surface, "RGB")   # it moves


def test_the_rules_card_plays_its_three_beats(surface):
    import random

    from brawl_ket import config
    from brawl_ket import match as M
    r = Renderer(surface)
    m = M.Match(random.Random(1))
    seen = set()
    for _ in range(config.ATTRACT_DELAY + config.DEMO_FRAMES + config.CARD_FRAMES + 5):
        r.draw(m, m.update(M.FrameInput()))
        if m.card:
            seen.add(min(2, m._title_phase // (config.CARD_FRAMES // 3)))
    assert seen == {0, 1, 2} and not m.card


def test_the_first_round_intro_draws_its_hint(surface):
    import random

    from brawl_ket import config
    from brawl_ket import match as M
    r = Renderer(surface)
    m = M.Match(random.Random(1))
    for kind in ("p1", "p1", "p2", "p1"):
        if m.state == M.STAGE_SELECT:
            for _ in range(M.STAGE_LOCK):
                m.update(M.FrameInput())
        inp = M.FrameInput(activity=True)
        inp.confirms[kind] = True
        m.update(inp)
    for _ in range(config.TUTORIAL_LOCK):
        m.update(M.FrameInput())
    m.update(M.FrameInput(activity=True, any_button=True))
    assert m.state == M.ROUND_INTRO and m.hint
    r.draw(m, [])


def test_the_stage_select_scales_each_preview_once(surface, monkeypatch):
    import random

    from brawl_ket import config
    from brawl_ket import match as M
    from brawl_ket import render

    r = Renderer(surface)
    m = M.Match(random.Random(1))
    m.state = M.STAGE_SELECT
    calls = []
    real = render.pygame.transform.smoothscale
    monkeypatch.setattr(render.pygame.transform, "smoothscale", lambda *a: calls.append(1) or real(*a))
    for pick in range(len(M.STAGE_OPTIONS)):
        m.stage_pick = pick
        for _ in range(config.FPS * len(config.STAGES) + 5):    # RANDOM cycles through them all
            m.t += 1
            r.draw(m, [])
    assert len(calls) == len(config.STAGES)


# --- the approved looks: the game draws each new fighter exactly as its look script does ---------

LOOKS = Path(__file__).resolve().parents[2] / "docs" / "superpowers" / "specs"


@pytest.fixture
def look(monkeypatch):
    """Load an approved look script. It writes its build into the skeleton's tables when it is
    imported, so for the test those tables are copies."""
    from brawl_ket import poses as PS

    def load(name: str):
        path = LOOKS / name
        if not path.exists():
            pytest.skip(f"{name} is not in this checkout")
        for table in ("SCALE", "HEAD_R", "LIMB_W"):
            monkeypatch.setattr(PS, table, dict(getattr(PS, table)))
        monkeypatch.setattr(PS, "BUILD_BONES", {k: dict(v) for k, v in PS.BUILD_BONES.items()})
        spec = importlib.util.spec_from_file_location(path.stem.replace("-", "_"), path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    return load


def same_pixels(a: pygame.Surface, b: pygame.Surface, mode: str = "RGB") -> bool:
    return pygame.image.tostring(a, mode) == pygame.image.tostring(b, mode)


@pytest.mark.parametrize("name,strike", [("idle", None), ("crouch", None), ("jump", None),
                                         ("heavy_hit", ("hand_f", PURPLE)), ("sweep_hit", ("foot_f", PURPLE))])
@pytest.mark.parametrize("facing", [1, -1])
@pytest.mark.parametrize("fur", [GREEN, PURPLE], ids=["green", "purple"])
def test_erwin_matches_her_approved_look(look, name, strike, facing, fur):
    from brawl_ket.erwin import draw_erwin
    from brawl_ket.poses import POSES, joints
    ref = look("2026-10-21-brawl-ket-erwin-look.py")
    pygame.init()
    a, b = pygame.Surface((240, 240)), pygame.Surface((240, 240))
    a.fill(BLANK)
    b.fill(BLANK)
    feet = (120.0, 220.0)
    ref.draw_erwin(a, POSES[name], feet, facing, fur, strike)
    draw_erwin(b, joints(POSES[name], "cat", feet, facing), facing, fur, strike)
    assert same_pixels(a, b)


def test_the_holographic_boxes_are_her_colour():
    from brawl_ket.erwin import CARD, holo_sprite
    pygame.init()
    for fur in (GREEN, PURPLE):
        out, _pool = holo_sprite(fur, 1, 0)
        seen = {tuple(out.get_at((x, y)))[:3] for x in range(0, out.get_width(), 2)
                for y in range(0, out.get_height(), 2)}
        assert fur in seen and CARD not in seen


def boxed_fight(r, frames=40):
    """ERWIN (p1) in THE BOX `frames` frames after the split, drawn every frame."""
    from brawl_ket.fighter import FighterInput
    from brawl_ket.moves import ERWIN
    fight = Fight({"p1": ERWIN, "p2": ROBERT}, seed=1)
    fight.fighters["p2"].x = 600
    r.draw_fight(fight, fight.step({"p1": FighterInput(x=True)}))
    for _ in range(ERWIN.moves["stand.X"].startup + frames):
        r.draw_fight(fight, fight.step({}))
    assert fight.fighters["p1"].boxed
    return fight


def test_m_cutie_s_charge_halos_are_built_as_the_fight_starts(surface):
    from brawl_ket.config import CHARGE_CAP
    from brawl_ket.cutie import halo
    from brawl_ket.fighter import FighterInput
    halo.cache_clear()
    r = Renderer(surface)
    fight = Fight({"p1": CHARACTERS["M-CUTIE"], "p2": CHARACTERS["M-CUTIE"]}, seed=1)
    fight.fighters["p2"].x = 600
    r.draw_fight(fight, fight.step({}))
    # every halo, both colours, both facings, every step: all of them fit the cache, so a
    # charge mid-round builds nothing new (a hitch on the cabinet otherwise)
    info = halo.cache_info()
    assert info.currsize == info.misses == 2 * 2 * CHARGE_CAP <= info.maxsize
    for i in range(40):
        r.draw_fight(fight, fight.step({"p1": FighterInput(x=i % 4 == 0)}))
    assert fight.fighters["p1"].charge or fight.shots
    assert halo.cache_info().misses == info.misses


def test_superposed_erwin_is_two_boxes_drawn_from_cached_sprites(surface):
    from brawl_ket.erwin import FADE_STEPS, HOLO_PHASES, holo_sprite
    from brawl_ket.stages import MARGIN
    holo_sprite.cache_clear()
    r = Renderer(surface)
    fight = boxed_fight(r)
    # every box sprite is built as the fight starts (a hitch on the cabinet otherwise, the first
    # time he boxes), all of them fit the cache, and drawing his boxed builds nothing new
    info = holo_sprite.cache_info()
    assert info.currsize == info.misses <= min(info.maxsize, 2 * 2 * (HOLO_PHASES + FADE_STEPS))
    for _ in range(20):
        r.draw_fight(fight, fight.step({}))
    assert holo_sprite.cache_info().misses == info.misses and fight.fighters["p1"].boxed
    for x in fight.fighters["p1"].boxes:
        changed = [(i, j) for i in range(round(x) - 30, round(x) + 31, 3) for j in range(FLOOR_Y - 50, FLOOR_Y - 4, 3)
                   if surface.get_at((i, j)) != r.stage.get_at((i + MARGIN, j + MARGIN))]
        assert len(changed) > 40, x


def test_a_collapse_shows_one_real_cardboard_box_then_clears(surface):
    from brawl_ket.erwin import CARD
    from brawl_ket.fighter import FighterInput
    r = Renderer(surface)
    fight = boxed_fight(r)
    r.draw_fight(fight, fight.step({"p1": FighterInput(a=True)}))
    erwin = fight.fighters["p1"]
    assert not erwin.boxed and {"box_pop", "box_fade"} <= {fx.kind for fx in r.effects}
    real = round(erwin.boxes[erwin.box_real])
    seen = {tuple(surface.get_at((i, j)))[:3] for i in range(real - 34, real + 35, 2) for j in range(FLOOR_Y - 46, FLOOR_Y, 2)}
    assert CARD in seen
    for _ in range(60):
        r.draw_fight(fight, fight.step({}))
    assert not [fx for fx in r.effects if fx.kind in ("box_pop", "box_fade")]


def test_erwins_kicking_leg_is_lit_in_the_attacks_colour(surface):
    from brawl_ket.erwin import cat_leg_points
    from brawl_ket.fighter import FighterInput
    from brawl_ket.moves import ERWIN
    from brawl_ket.poses import joints
    r = Renderer(surface)
    fight = Fight({"p1": ERWIN, "p2": ROBERT})
    fight.fighters["p2"].x = 600
    for i in range(3):
        r.draw_fight(fight, fight.step({"p1": FighterInput(down=True, b=i == 0)}))
    f = fight.fighters["p1"]
    assert f.action == "attack" and f.phase == "startup"
    j = joints(r.pose_last["p1"], "cat", (f.x, FLOOR_Y - f.y), f.facing)
    knee, hock = cat_leg_points(j, "f", f.facing)
    assert PURPLE in limb_colours(surface, r, f, {"knee": knee, "hock": hock}, "knee", "hock")


@pytest.mark.parametrize("name,strike,led,mood,eject", [
    ("idle", None, False, "calm", False),
    ("heavy_hit", ("hand_f", PURPLE), False, "calm", False),
    ("sweep_hit", ("foot_f", PURPLE), True, "angry", False),
    ("crouch", None, False, "calm", False),
    ("jump", None, False, "calm", False),
    ("eject", None, True, "angry", True),
])
@pytest.mark.parametrize("facing", [1, -1])
def test_dos_matches_his_approved_look(look, name, strike, led, mood, eject, facing):
    from brawl_ket.dos import draw_dos
    from brawl_ket.poses import POSES, drawn_joints
    ref = look("2026-10-21-brawl-ket-dos-look.py")
    pygame.init()
    a, b = pygame.Surface((240, 240)), pygame.Surface((240, 240))
    a.fill(BLANK)
    b.fill(BLANK)
    feet = (120.0, 220.0)
    ref.draw_dos(a, POSES[name], feet, facing, GREEN, strike, led, mood, eject)
    draw_dos(b, drawn_joints(POSES[name], "dos", feet, facing), facing, GREEN, strike, led, mood, eject)
    assert same_pixels(a, b)


def test_the_floppy_matches_the_approved_look(look):
    from brawl_ket.dos import floppy_sprite
    ref = look("2026-10-21-brawl-ket-dos-look.py")
    pygame.init()
    for colour in (GREEN, PURPLE):
        for size in (18, 22):
            assert same_pixels(ref.floppy_sprite(colour, size), floppy_sprite(colour, size), "RGBA")


def test_dos_is_always_drawn_green(surface):
    from brawl_ket.moves import DOS
    r = Renderer(surface)
    fight = Fight({"p1": ROBERT, "p2": DOS})
    r.draw_fight(fight, [])
    seen = body_pixels(surface, r, fight, "p2")
    assert GREEN in seen and PURPLE not in seen


def dos_frames(r, presses, frames, rival_x=600):
    """DOS (p1) against a far ROBERT, pressing `presses` on the first frame, drawn every frame."""
    from brawl_ket.fighter import FighterInput
    from brawl_ket.moves import DOS
    fight = Fight({"p1": DOS, "p2": ROBERT})
    fight.fighters["p2"].x = rival_x
    for i in range(frames):
        r.draw_fight(fight, fight.step({"p1": FighterInput(**presses) if i == 0 else FighterInput(
            down=presses.get("down", False))}))
    return fight


def test_mouse_cable_draws_the_mouse_on_its_cable_back_to_him(surface):
    from brawl_ket.moves import DOS
    mouse = DOS.moves["crouch.X"]
    r = Renderer(surface)
    fight = dos_frames(r, {"down": True, "x": True}, mouse.startup + 6)
    dos = fight.fighters["p1"]
    (shot,) = [s for s in fight.shots if s.move is mouse]
    left, top, w, h = shot.box
    body = {tuple(surface.get_at((round(left + w / 2) + dx, round(top + h / 2))))[:3] for dx in (-3, 0, 3)}
    assert GREEN in body or P.lighten(GREEN, 0.6) in body                   # the mouse, his colour
    cable_x = round((dos.x + 30 + left) / 2)                                 # halfway out along the cable
    cable = {tuple(surface.get_at((cable_x, j)))[:3] for j in range(FLOOR_Y - 50, FLOOR_Y)}
    assert P.shade(GREEN, 0.7) in cable


def test_a_falling_box_drop_is_a_little_box_in_his_colour(surface):
    from brawl_ket.fight import Shot
    from brawl_ket.moves import ERWIN
    r = Renderer(surface)
    fight = Fight({"p1": ERWIN, "p2": ROBERT}, seed=1)
    fight.shots.append(Shot("p1", ERWIN.moves["air.X"], 300, 80.0, 0.5, 90, "Z", -7.0))
    r.draw_fight(fight, [])
    left, top, w, h = fight.shots[0].box
    seen = {tuple(surface.get_at((i, j)))[:3] for i in range(round(left), round(left + w)) for j in range(round(top), round(top + h))}
    assert GREEN in seen and P.lighten(GREEN, 0.45) in seen                 # the box and its tape


def test_copy_holds_up_a_ctrl_c_frame(surface):
    from brawl_ket.moves import DOS
    copy = DOS.extra["copy"]
    r = Renderer(surface)
    fight = dos_frames(r, {"y": True}, copy.startup + 2)
    dos = fight.fighters["p1"]
    assert dos.move is copy and dos.phase == "active"
    left, top, w, _h = dos.world_box(copy.catch)
    assert P.WHITE in {tuple(surface.get_at((i, round(top))))[:3] for i in range(round(left), round(left + w))}


def test_a_floppy_in_flight_is_drawn_from_cached_turns(surface):
    from brawl_ket.dos import ANGLE_STEP, _turned
    from brawl_ket.moves import DOS
    _turned.cache_clear()
    r = Renderer(surface)
    fight = dos_frames(r, {"x": True}, DOS.moves["stand.X"].startup + 60)
    (shot,) = fight.shots
    assert _turned.cache_info().currsize <= 360 // ANGLE_STEP
    left, top, w, h = shot.box
    cx, cy = round(left + w / 2), round(top + h / 2)
    assert GREEN in {tuple(surface.get_at((i, j)))[:3] for i in range(cx - 12, cx + 13) for j in range(cy - 12, cy + 13)}


def test_the_hud_shows_doss_clipboard(surface):
    from brawl_ket.basis import X_BASIS
    from brawl_ket.moves import DOS
    r = Renderer(surface)
    fight = Fight({"p1": DOS, "p2": ROBERT})
    r.draw_fight(fight, [])
    assert set(r.clip_rects) == {"p1"}                      # only DOS has one

    def icon():
        rect = r.clip_rects["p1"]
        return {tuple(surface.get_at((i, j)))[:3] for i in range(rect.left, rect.right) for j in range(rect.top, rect.bottom)}

    assert not icon() & {GREEN, PURPLE}                     # empty
    fight.fighters["p1"].clipboard = (ROBERT.moves["stand.X"], X_BASIS)
    r.draw_fight(fight, [])
    assert PURPLE in icon()                                 # a purple PHOTON in it


def test_doss_screen_faces_are_drawn_once_and_blitted(surface):
    from brawl_ket.dos import screen_sprite
    from brawl_ket.moves import DOS
    screen_sprite.cache_clear()
    r = Renderer(surface)
    for fight, events in bot_frames(600, chars=(DOS, ROBERT)):
        r.draw_fight(fight, events)
    info = screen_sprite.cache_info()
    assert info.hits > 2 * info.misses


def test_the_select_panels_say_what_each_fighter_is():
    from brawl_ket.moves import CHARACTERS
    from brawl_ket.render import panel_lines
    text = {name: [line for line, _c in panel_lines(c)] for name, c in CHARACTERS.items()}
    assert text["ERWIN"][0] == "QUICK AND SLIPPERY" and "Y SWITCHES YOUR COLOUR" in text["ERWIN"]
    assert text["DOS"] == ["SLOW AND CLASSICAL", "A AND X: YOUR COLOUR, B: THE OTHER", "Y: COPY, THEN PASTE",
                           "ALWAYS GREEN"]
    assert panel_lines(CHARACTERS["DOS"])[-1][1] == GREEN
    assert text["M-CUTIE"][0] == "PATIENT AND TECHNICAL"
    assert text["ALICE & BOB"][0] == "TWO AS ONE"
    for name in ("ROBERT", "BOHR", "PHOEBE", "M-CUTIE", "ALICE & BOB"):
        assert text[name][1:] == ["A AND X: YOUR COLOUR, B: THE OTHER", "Y SWITCHES YOUR COLOUR"], name


def test_choose_your_fighter_draws_every_fighter(surface):
    import random

    from brawl_ket import match as M
    r = Renderer(surface)
    m = M.Match(random.Random(1))
    m.state = M.SELECT
    for i in range(len(M.ROSTER)):
        m.picks = {"p1": i, "p2": (i + 1) % len(M.ROSTER)}
        r.draw(m, [])


def test_the_title_still_shows_both_colours(surface):
    import random

    from brawl_ket import match as M
    r = Renderer(surface)
    r.draw(M.Match(random.Random(1)), [])
    seen = {tuple(surface.get_at((x, y)))[:3] for x in range(440, 481, 2) for y in range(FLOOR_Y - 110, FLOOR_Y - 40, 2)}
    assert PURPLE in seen               # ALICE & BOB on the right, the last fighter who can switch


def test_every_fighter_has_a_portrait_framed_on_its_head():
    from brawl_ket.render import PORTRAIT, portrait
    for name in CHARACTERS:
        img = portrait(name)
        assert img.get_size() == (PORTRAIT, PORTRAIT)
        rows = [y for y in range(PORTRAIT) if any(img.get_at((x, y))[3] for x in range(PORTRAIT))]
        assert rows and rows[0] <= 6 and rows[-1] == PORTRAIT - 1, name   # the head at the top, the body to the bottom


def test_choose_your_fighter_frames_both_picks_in_the_players_colours(surface):
    import random
    from brawl_ket import match as M
    from brawl_ket.config import PLAYER_COLORS
    r = Renderer(surface)
    m = M.Match(random.Random(1))
    m.state, m.picks, m.ready = M.SELECT, {"p1": 3, "p2": 4}, {"p1": True, "p2": True}
    r.draw(m, [])
    seen = {tuple(surface.get_at((x, y)))[:3] for x in range(0, surface.get_width(), 2) for y in range(270, 345, 2)}
    assert PLAYER_COLORS["p1"] in seen and PLAYER_COLORS["p2"] in seen


# --- M-CUTIE: her approved look (variant B), her specials, and her cached layers --------------

CUTIE_LOOK = "2026-10-21-brawl-ket-m-cutie-look.py"


@pytest.mark.parametrize("name,strike,swing,bright", [
    ("idle", None, 0, 0.0), ("crouch", None, 0, 0.0), ("jump", None, 6, 0.0), ("walk1", None, 0, 0.0),
    ("heavy_hit", ("hand_f", PURPLE), 0, 0.0), ("sweep_hit", ("foot_f", PURPLE), 0, 0.0),
    ("charge", None, 0, 0.8), ("knockdown", None, 0, 0.0),
])
@pytest.mark.parametrize("facing", [1, -1])
@pytest.mark.parametrize("base", [GREEN, PURPLE], ids=["green", "purple"])
@pytest.mark.parametrize("feet", [(120.0, 220.0), (121.0, 221.0), (120.5, 220.0)], ids=["even", "odd", "half"])
def test_m_cutie_matches_her_approved_look(look, name, strike, swing, bright, facing, base, feet):
    from brawl_ket.cutie import draw_cutie
    from brawl_ket.poses import POSES, joints
    ref = look(CUTIE_LOOK)
    pygame.init()
    a, b = pygame.Surface((240, 240)), pygame.Surface((240, 240))
    a.fill(BLANK)
    b.fill(BLANK)
    pose = POSES[name]
    ref.draw_cutie(a, pose, feet, facing, base, "B", strike, bright=bright, swing=swing)
    draw_cutie(b, joints(pose, "cutie", feet, facing), pose.lean, facing, base, strike, bright=bright, swing=swing)
    assert same_pixels(a, b)


def test_her_build_and_poses_are_the_looks(look):
    from brawl_ket import poses as PS
    ours = (PS.SCALE["cutie"], dict(PS.BUILD_BONES["cutie"]), PS.HEAD_R["cutie"], PS.LIMB_W["cutie"])
    ref = look(CUTIE_LOOK)                      # (it writes its build into the tables)
    assert ours == (PS.SCALE["cutie"], PS.BUILD_BONES["cutie"], PS.HEAD_R["cutie"], PS.LIMB_W["cutie"])
    assert PS.POSES["spin"] == ref.SPIN and PS.POSES["charge"] == ref.CHARGE


@pytest.mark.parametrize("facing", [1, -1])
@pytest.mark.parametrize("feet", [(556.0, FLOOR_Y - 70.0), (557.5, FLOOR_Y - 71.0)], ids=["whole", "half"])
def test_spin_matches_the_look(look, facing, feet):
    from brawl_ket.cutie import draw_spin
    from brawl_ket.poses import POSES, joints
    ref = look(CUTIE_LOOK)
    pygame.init()
    a, b = pygame.Surface((640, 360)), pygame.Surface((640, 360))
    a.fill(BLANK)
    b.fill(BLANK)
    ref.leg_ghosts(a, ref.SPIN, feet, facing, GREEN)        # the look's row of specials, in its order
    j = joints(ref.SPIN, "cutie", feet, facing)
    ref.spin_whirl(a, j, GREEN, "back")
    ref.draw_cutie(a, ref.SPIN, feet, facing, GREEN, "B", swing=10, spread=1.2, squash=0.75)
    ref.spin_whirl(a, j, GREEN, "front")
    draw_spin(b, POSES["spin"], feet, facing, GREEN)
    assert same_pixels(a, b)


def _skirt_bottom(pose_name: str, feet, facing: int, floor) -> int:
    """The lowest row M-CUTIE's skirt (both halves of the cage, and its fringe) paints."""
    from brawl_ket.cutie import skirt_cage_back, skirt_cage_front
    from brawl_ket.ink import frame
    from brawl_ket.poses import POSES, joints
    j = joints(POSES[pose_name], "cutie", feet, facing)
    at = frame(j, facing)
    s = pygame.Surface((INTERNAL_WIDTH, INTERNAL_HEIGHT), pygame.SRCALPHA)
    skirt_cage_back(s, j, at, GREEN, floor=floor)
    skirt_cage_front(s, j, at, GREEN, facing, 2, floor=floor)
    return s.get_bounding_rect().bottom - 1


def test_her_skirt_sinks_into_the_floor_without_a_floor_line():
    """The look hangs the cage straight down from the hip: lying down it went through the floor."""
    pygame.init()
    for name in ("knockdown", "slide", "pounce"):
        assert _skirt_bottom(name, (300.0, FLOOR_Y), 1, None) > FLOOR_Y + 20


@pytest.mark.parametrize("facing", [1, -1])
@pytest.mark.parametrize("feet_x", [300.0, 300.5, 301.0])
def test_her_skirt_never_sinks_into_the_floor(facing, feet_x):
    """Given the floor line, the hem's bottom stays on or above it in every pose (the knockdown,
    the slide and the pounce lie lowest)."""
    from brawl_ket.poses import POSES
    pygame.init()
    for name in POSES:
        assert _skirt_bottom(name, (feet_x, FLOOR_Y), facing, FLOOR_Y) <= FLOOR_Y, name


@pytest.mark.parametrize("name", ["idle", "crouch", "jump", "walk1", "heavy_hit", "sweep_hit", "charge"])
@pytest.mark.parametrize("facing", [1, -1])
def test_the_floor_line_leaves_the_looks_poses_alone(look, name, facing):
    """Standing, crouching or jumping her skirt never reaches the floor: with the floor line at
    her feet she is still the look, pixel for pixel."""
    from brawl_ket.cutie import draw_cutie
    from brawl_ket.poses import POSES, joints
    ref = look(CUTIE_LOOK)
    pygame.init()
    feet = (120.5, 220.0)
    a, b = pygame.Surface((240, 240)), pygame.Surface((240, 240))
    a.fill(BLANK)
    b.fill(BLANK)
    pose = POSES[name]
    ref.draw_cutie(a, pose, feet, facing, GREEN, "B")
    draw_cutie(b, joints(pose, "cutie", feet, facing), pose.lean, facing, GREEN, floor=feet[1])
    assert same_pixels(a, b)


def test_a_knocked_out_m_cutie_lies_on_the_floor(monkeypatch):
    """The KO pose stays on screen through ROUND_END: her skirt is drawn on the stage's floor."""
    from brawl_ket.moves import M_CUTIE
    pygame.init()
    surface = pygame.Surface((INTERNAL_WIDTH, INTERNAL_HEIGHT))
    renderer = Renderer(surface)
    fight = Fight({"p1": ROBERT, "p2": M_CUTIE})
    cutie = fight.fighters["p2"]
    cutie.knock_out(1, 0)
    for _ in range(40):
        fight.step({})
    assert cutie.action == "knockdown" and cutie.y == 0
    import brawl_ket.render as R
    drawn, real = [], R.draw_cutie

    def spy(*args, **kwargs):
        drawn.append(kwargs.get("floor"))
        return real(*args, **kwargs)
    monkeypatch.setattr(R, "draw_cutie", spy)
    renderer.draw_fight(fight, [])
    assert drawn and all(f is not None and abs(f - FLOOR_Y) <= 8 for f in drawn)


@pytest.mark.parametrize("steps", range(1, 7))
@pytest.mark.parametrize("colour", [GREEN, PURPLE], ids=["green", "purple"])
@pytest.mark.parametrize("facing", [1, -1])
def test_her_wave_matches_the_look(look, steps, colour, facing):
    from brawl_ket.cutie import draw_wave, drive_pulse
    from brawl_ket.moves import AMP_WAVES
    ref = look(CUTIE_LOOK)
    pygame.init()
    h = AMP_WAVES[steps - 1].projectile.box.h
    for x in (172, 173):                        # both pixel parities of its middle
        a, b = pygame.Surface((640, 360)), pygame.Surface((640, 360))
        a.fill(BLANK)
        b.fill(BLANK)
        ref.drive_pulse(a, x, h, colour, facing)
        draw_wave(b, x, FLOOR_Y, h, colour, facing)
        assert same_pixels(a, b), x
    a.fill(BLANK)                               # ... and a floor line shaken a px down
    b.fill(BLANK)
    drive_pulse(a, 172, h, colour, facing, FLOOR_Y + 1)
    draw_wave(b, 172, FLOOR_Y + 1, h, colour, facing)
    assert same_pixels(a, b)


@pytest.mark.parametrize("armed", [False, True], ids=["arming", "armed"])
@pytest.mark.parametrize("colour", [GREEN, PURPLE], ids=["green", "purple"])
def test_her_trap_matches_the_look(look, armed, colour):
    from brawl_ket.cutie import draw_trap
    ref = look(CUTIE_LOOK)
    pygame.init()
    a, b = pygame.Surface((640, 360)), pygame.Surface((640, 360))
    a.fill(BLANK)
    b.fill(BLANK)
    ref.ion_trap(a, 360, colour, armed)
    draw_trap(b, 360, FLOOR_Y, colour, armed)
    assert same_pixels(a, b)


@pytest.mark.parametrize("steps", [1, 4, 6])
def test_the_charge_halo_is_the_looks_to_one_colour_step(look, steps):
    """The one approximation: one blend per pixel instead of 16. The same pixels change, and
    every one is within one step of the 15-bit grid (8) of the look's, but the head's glow
    on the background (which the look's own layer drops)."""
    from brawl_ket import palette as Pal
    from brawl_ket.cutie import charge_look, draw_charging
    from brawl_ket.poses import POSES
    ref = look(CUTIE_LOOK)
    pygame.init()
    a, b = pygame.Surface((640, 360)), pygame.Surface((640, 360))
    a.fill(BLANK)
    b.fill(BLANK)
    bright, k = charge_look(steps)
    j = ref.aura(a, lambda s: ref.draw_cutie(s, ref.CHARGE, (64, FLOOR_Y), 1, GREEN, "B", bright=bright), GREEN, k)
    ref.glow(a, j["hand_f"], 9, Pal.lighten(GREEN, 0.6), 160)
    ref.pips(a, (j["head"][0], j["head"][1] - 30), steps, GREEN)
    draw_charging(b, POSES["charge"], (64, FLOOR_Y), 1, GREEN, steps)
    pts = [(x, y) for x in range(0, 140) for y in range(120, 330)]
    changed_a = {p for p in pts if tuple(a.get_at(p))[:3] != BLANK}
    changed_b = {p for p in pts if tuple(b.get_at(p))[:3] != BLANK}
    assert changed_a == changed_b
    far = [p for p in changed_a if max(abs(u - v) for u, v in zip(a.get_at(p)[:3], b.get_at(p)[:3])) > 8]
    assert len(far) <= 16
    assert charge_look(4) == (0.8, 1.0)         # 4 steps: the look's sheet


def test_her_head_wave_and_trap_are_drawn_from_cached_layers(surface):
    from brawl_ket.cutie import head_layers, pulse_layers, trap_layers
    from brawl_ket.moves import M_CUTIE
    for cache in (head_layers, pulse_layers, trap_layers):
        cache.cache_clear()
    r = Renderer(surface)
    for fight, events in bot_frames(600, chars=(M_CUTIE, ROBERT)):
        r.draw_fight(fight, events)
    info = head_layers.cache_info()
    assert info.hits > 10 * info.misses


def cutie_frames(r, presses, frames, rival_x=600, rival=None):
    """M-CUTIE (p1) against a ROBERT at `rival_x`, `presses(i)` each frame, drawn every frame."""
    from brawl_ket.fighter import IDLE
    from brawl_ket.moves import M_CUTIE
    fight = Fight({"p1": M_CUTIE, "p2": ROBERT})
    fight.fighters["p2"].x = rival_x
    for i in range(frames):
        r.draw_fight(fight, fight.step({"p1": presses(i), "p2": rival or IDLE}))
    return fight


def test_charging_shows_a_pip_per_step_above_her_head(surface):
    from brawl_ket import palette as Pal
    from brawl_ket.fighter import FighterInput
    from brawl_ket.poses import POSES, joints
    r = Renderer(surface)
    fight = cutie_frames(r, lambda i: FighterInput(x=i in (0, 4, 8)), 10)
    me = fight.fighters["p1"]
    assert me.action == "charging" and me.charge == 3
    j = joints(POSES["charge"], "cutie", (me.x, FLOOR_Y), me.facing)
    y = round(j["head"][1] - 30)
    lit = [x for x in range(round(j["head"][0]) - 30, round(j["head"][0]) + 31)
           if tuple(surface.get_at((x, y)))[:3] == Pal.lighten(GREEN, 0.45)]
    assert len(lit) >= 3 * 5                    # three diamonds, each about 7 px across


def test_her_wave_is_drawn_on_the_floor_in_its_colour(surface):
    from brawl_ket.fighter import FighterInput
    from brawl_ket.moves import AMP_WAVES
    r = Renderer(surface)
    fight = cutie_frames(r, lambda i: FighterInput(x=i % 4 == 0 and i < 21), 21 + 16 + AMP_WAVES[0].startup + 10)
    (shot,) = fight.shots
    assert shot.move is AMP_WAVES[5]
    x = round(shot.x)
    column = {tuple(surface.get_at((x, y)))[:3] for y in range(FLOOR_Y - 50, FLOOR_Y - 2)}
    assert GREEN in column


def test_a_trap_is_dim_while_it_arms_and_lit_once_armed(surface):
    from brawl_ket import palette as Pal
    from brawl_ket.config import TRAP_ARM
    from brawl_ket.fighter import FighterInput
    from brawl_ket.moves import M_CUTIE
    trap = M_CUTIE.moves["crouch.X"]
    r = Renderer(surface)
    fight = cutie_frames(r, lambda i: FighterInput(down=True, x=i == 0), trap.startup + 2)
    (t,) = fight.traps
    ion = (round(t.x), FLOOR_Y - 17)
    assert tuple(surface.get_at(ion))[:3] == Pal.shade(GREEN, 0.5)
    for _ in range(TRAP_ARM):
        r.draw_fight(fight, fight.step({}))
    assert t.armed and tuple(surface.get_at(ion))[:3] == Pal.lighten(GREEN, 0.6)


def test_her_spin_whirls_and_its_kicking_leg_is_lit(surface):
    from brawl_ket.fighter import FighterInput
    from brawl_ket.moves import M_CUTIE
    spin = M_CUTIE.moves["air.X"]
    r = Renderer(surface)
    fight = cutie_frames(r, lambda i: FighterInput(up=i == 0, x=i == 8), 8 + spin.startup + 2)
    me = fight.fighters["p1"]
    assert me.move is spin and me.phase == "active"
    from brawl_ket.poses import joints
    j = joints(r.pose_last["p1"], "cutie", (me.x, FLOOR_Y - me.y), me.facing)
    assert GREEN in limb_colours(surface, r, me, j, "knee_f", "foot_f")     # her colour, lit


def test_a_closing_trap_snaps_a_ring_shut(surface):
    from brawl_ket.fight import Event
    r = Renderer(surface)
    fight = Fight({"p1": ROBERT, "p2": ROBERT})
    r.draw_fight(fight, [Event("trap_close", "p2", None, 300.0, FLOOR_Y)])
    assert [fx.kind for fx in r.effects] == ["snap"]
    for _ in range(20):
        r.draw_fight(fight, [])
    assert r.effects == []


def test_her_specials_read_in_full_where_they_fit_and_shortened_on_the_select_screen():
    from brawl_ket.moves import M_CUTIE
    from brawl_ket.render import LIST_NAME_X, LIST_W, X_INPUTS, font, move_label
    pygame.init()
    assert [move_label(M_CUTIE.moves[s]) for s, _how in X_INPUTS[:3]] == ["AMP. AMPLIFICATION", "ION TRAP", "SPIN"]
    assert M_CUTIE.moves["stand.X"].name == "AMPLITUDE AMPLIFICATION"     # the full name, everywhere else
    chip = font(8).size("YOURS")[0] + 3
    for c in CHARACTERS.values():
        for slot, how in X_INPUTS:
            move = c.extra.get(slot) if slot == "super" else c.moves[slot]
            if move is None:                # no super yet
                continue
            assert font(8).size(how)[0] < LIST_NAME_X, how
            assert LIST_NAME_X + font(8).size(move_label(move))[0] + 4 <= LIST_W - chip, (c.name, slot)


def test_the_lists_of_specials_clear_the_two_rows_of_portraits():
    from brawl_ket import match as M
    from brawl_ket.render import LIST_GAP, LIST_W, PORTRAIT, PORTRAIT_GAP, PORTRAIT_Y, SIDE_X, list_top
    rows = -(-M.GRID // M.ROSTER_COLS)
    assert (M.GRID, M.ROSTER_COLS, rows) == (8, 4, 2)                       # DOS starts the second row
    grid_top = PORTRAIT_Y - (rows - 1) * (PORTRAIT + PORTRAIT_GAP) - 4      # its tiles' ink and the cursors
    for c in CHARACTERS.values():
        assert list_top(c) + 3 * LIST_GAP + 8 < grid_top, c.name      # four rows: the super's too
    assert PORTRAIT_Y + PORTRAIT + 5 <= INTERNAL_HEIGHT - 9                 # the bottom row clears the hint
    assert INTERNAL_WIDTH / 2 + SIDE_X + LIST_W / 2 <= INTERNAL_WIDTH - 12      # and the lists the screen's edges


def test_choose_your_fighter_shows_m_cutie_in_the_second_row(surface):
    import random
    from brawl_ket import match as M
    from brawl_ket.config import PLAYER_COLORS
    from brawl_ket.render import PORTRAIT, PORTRAIT_Y
    r = Renderer(surface)
    m = M.Match(random.Random(1))
    m.state, m.picks = M.SELECT, {"p1": 5, "p2": 0}
    r.draw(m, [])
    ring = {tuple(surface.get_at((x, PORTRAIT_Y + PORTRAIT // 2)))[:3] for x in range(200, 440)}
    assert PLAYER_COLORS["p1"] in ring or P.lighten(PLAYER_COLORS["p1"], 0.6) in ring


# --- ALICE & BOB: their approved look (variant A, COURIERS), their specials, a decohered Bob ---------

KIDS_LOOK = "2026-10-22-brawl-ket-alice-bob-look.py"


@pytest.mark.parametrize("name,strike", [
    ("idle", None), ("crouch", None), ("jump", None), ("walk1", None), ("knockdown", None),
    ("heavy_wind", ("hand_f", PURPLE, False)), ("heavy_hit", ("hand_f", PURPLE, True)),
    ("sweep_hit", ("foot_f", PURPLE, True)), ("dive", ("foot_f", GREEN, True)),
    ("toss", None), ("catch", None), ("fire", ("hand_f", GREEN, True)),
])
@pytest.mark.parametrize("who", ["alice", "bob"])
@pytest.mark.parametrize("facing", [1, -1])
@pytest.mark.parametrize("base", [GREEN, PURPLE], ids=["green", "purple"])
@pytest.mark.parametrize("feet", [(120.0, 220.0), (121.0, 221.0), (120.5, 220.0)], ids=["even", "odd", "half"])
def test_alice_and_bob_match_their_approved_look(look, name, strike, who, facing, base, feet):
    from brawl_ket.kids import draw_kid
    from brawl_ket.poses import POSES, joints
    ref = look(KIDS_LOOK)
    pygame.init()
    a, b = pygame.Surface((240, 240)), pygame.Surface((240, 240))
    a.fill(BLANK)
    b.fill(BLANK)
    pose = POSES[name]
    ref.draw_kid(a, pose, feet, facing, base, who, "A", strike)
    draw_kid(b, joints(pose, who, feet, facing), facing, base, who, strike)
    assert same_pixels(a, b)


def test_their_builds_and_poses_are_the_looks(look):
    from brawl_ket import poses as PS
    ours = {b: (PS.SCALE[b], dict(PS.BUILD_BONES[b]), PS.HEAD_R[b], PS.LIMB_W[b]) for b in ("alice", "bob")}
    ref = look(KIDS_LOOK)                       # (it writes its builds into the tables)
    assert ours == {b: (PS.SCALE[b], PS.BUILD_BONES[b], PS.HEAD_R[b], PS.LIMB_W[b]) for b in ("alice", "bob")}
    assert PS.HEAD_R["kid"] == PS.HEAD_R["alice"] and PS.LIMB_W["kid"] == PS.LIMB_W["alice"]
    assert (PS.POSES["toss"], PS.POSES["catch"], PS.POSES["fire"]) == (ref.TOSS_A, ref.CATCH, ref.FIRE)
    assert ref.GAP == 40


def test_the_pair_drawn_together_is_the_looks_pair(look):
    from brawl_ket.kids import draw_pair
    from brawl_ket.poses import POSES
    ref = look(KIDS_LOOK)
    pygame.init()
    for facing in (1, -1):
        a, b = pygame.Surface((320, 240)), pygame.Surface((320, 240))
        a.fill(BLANK)
        b.fill(BLANK)
        ref.pair(a, 160, facing, GREEN, "A", "p1", rings=False)       # (on the look's FLOOR_Y)
        draw_pair(b, POSES["idle"], (160, FLOOR_Y), facing, GREEN)
        assert same_pixels(a, b)


@pytest.mark.parametrize("big", [False, True])
@pytest.mark.parametrize("facing", [1, -1])
def test_the_photons_are_the_looks(look, big, facing):
    from brawl_ket.kids import photon
    ref = look(KIDS_LOOK)
    pygame.init()
    a, b = pygame.Surface((200, 120)), pygame.Surface((200, 120))
    a.fill(BLANK)
    b.fill(BLANK)
    ref.photon(a, (100.5, 60.0), GREEN, facing, big)
    photon(b, (100.5, 60.0), GREEN, facing, big)
    assert same_pixels(a, b)


def test_key_exchange_teleport_and_bell_dive_art_is_the_looks(look):
    from brawl_ket.kids import dive_streaks, flash, lob, swap_arc
    from brawl_ket.poses import POSES, joints
    ref = look(KIDS_LOOK)
    pygame.init()
    for draw_ref, draw_ours in (
        (lambda s: ref.lob(s, (90, 222), (50, 180), GREEN, k_at=0.55, height=40),
         lambda s: lob(s, (90, 222), (50, 180), GREEN, k_at=0.55, height=40)),
        (lambda s: ref.flash(s, 276, PURPLE), lambda s: flash(s, 276, PURPLE)),
        (lambda s: ref.swap_arc(s, 276, 400, FLOOR_Y - 150, GREEN), lambda s: swap_arc(s, 276, 400, FLOOR_Y - 150, GREEN)),
        (lambda s: ref.streaks(s, (450, FLOOR_Y - 164), joints(POSES["dive"], "bob", (484, FLOOR_Y - 108), 1)["hip"],
                               GREEN),
         lambda s: dive_streaks(s, joints(POSES["dive"], "bob", (484, FLOOR_Y - 108), 1), (484, FLOOR_Y - 108), 1,
                                GREEN)),
    ):
        a, b = pygame.Surface((640, 360)), pygame.Surface((640, 360))
        a.fill(BLANK)
        b.fill(BLANK)
        draw_ref(a)
        draw_ours(b)
        assert same_pixels(a, b)


@pytest.mark.parametrize("t", [0, 1, 5])
@pytest.mark.parametrize("facing", [1, -1])
@pytest.mark.parametrize("feet", [(588.0, float(FLOOR_Y)), (300.5, float(FLOOR_Y + 1))], ids=["look", "odd"])
def test_a_decohered_bob_is_the_looks(look, t, facing, feet):
    from brawl_ket.kids import draw_decohered
    ref = look(KIDS_LOOK)
    pygame.init()
    a, b = pygame.Surface((640, 360)), pygame.Surface((640, 360))
    a.fill(BLANK)
    b.fill(BLANK)
    ref.decohered(a, feet, facing, GREEN, "A", t)
    draw_decohered(b, feet, facing, GREEN, t)
    assert same_pixels(a, b)


def pair_frames(surface, steps, rival=ROBERT, setup=None, rival_x=500.0):
    """Draw a fight of ALICE & BOB (p1) against `rival`, `steps` = [p1 inputs]; returns (r, fight)."""
    from brawl_ket.fighter import IDLE
    from brawl_ket.moves import ALICE_BOB
    r = Renderer(surface)
    fight = Fight({"p1": ALICE_BOB, "p2": rival})
    fight.fighters["p2"].x = rival_x
    if setup is not None:
        setup(fight)
    for inp in steps:
        r.draw_fight(fight, fight.step({"p1": inp or IDLE}))
    return r, fight


def test_bob_is_drawn_behind_alice_on_the_thinner_ring(surface):
    from brawl_ket.config import PLAYER_COLORS
    r, fight = pair_frames(surface, [None] * 3)
    alice, bob = fight.fighters["p1"], fight.echoes["p1"]
    ring_rows = range(FLOOR_Y - 4, FLOOR_Y + 9)

    def ring_px(x):
        return sum(1 for i in range(round(x) - 28, round(x) + 29) for j in ring_rows
                   if tuple(surface.get_at((i, j)))[:3] == PLAYER_COLORS["p1"])
    assert 0 < ring_px(bob.x - 30) < ring_px(alice.x + 30)       # (their outer halves: the rings overlap)
    # Alice is drawn over Bob: where they overlap (her back, his front), her satchel strap and
    # hoodie show, not his arm: her body's pixels win at her hip
    from brawl_ket.kids import draw_kid
    from brawl_ket.poses import joints
    alone = pygame.Surface(surface.get_size())
    alone.blit(surface, (0, 0))
    j = joints(r.pose_last["p1"], "alice", (alice.x, FLOOR_Y), 1)
    draw_kid(alone, j, 1, GREEN, "alice")
    hip = (round(j["hip"][0]), round(j["hip"][1]) - 10)
    assert surface.get_at(hip) == alone.get_at(hip)


def test_a_decohering_bob_fades_and_his_ring_waits_dimmed_behind_her(surface):
    from brawl_ket.config import DECOHERE_FADE, PLAYER_COLORS
    from brawl_ket.stages import MARGIN

    def setup(f):
        f.fighters["p1"].x = 320.0                          # Alice well clear of where Bob decoheres
        f.echoes["p1"].decohere()
    r, fight = pair_frames(surface, [None] * 2, setup=setup)
    bob = fight.echoes["p1"]
    x = round(bob.x)

    def changed():                                          # (the racks' blinking lights aside)
        return sum(1 for i in range(x - 20, x + 21, 2) for j in range(FLOOR_Y - 110, FLOOR_Y - 10, 2)
                   if surface.get_at((i, j)) != r.stage.get_at((i + MARGIN, j + MARGIN))
                   and not any(rect.collidepoint(i, j) for rect, _c in r.lights))
    assert changed() > 100                                  # standing there, see-through
    for _ in range(DECOHERE_FADE + 2):
        r.draw_fight(fight, fight.step({}))
    assert changed() == 0                                   # gone
    dim = P.shade(PLAYER_COLORS["p1"], 0.5)
    assert any(tuple(surface.get_at((i, j)))[:3] == dim for i in range(round(bob.spot) - 26, round(bob.spot) + 27)
               for j in range(FLOOR_Y - 4, FLOOR_Y + 9))


def test_the_toss_and_bobs_shot_are_keys(surface, monkeypatch):
    """KEY EXCHANGE is a key (after the first playtest): a small one tumbling along the toss's arc,
    then Bob's shot, a big one, blade first."""
    import brawl_ket.render as R
    from brawl_ket.fighter import FighterInput
    from brawl_ket.kids import key_sprite
    from brawl_ket.render import ERROR_COLOUR
    tossed, shot_keys = [], []
    real_toss, real_shot = R.tossed_key, R.key_shot
    monkeypatch.setattr(R, "tossed_key", lambda surf, c, *a: (tossed.append(c), real_toss(surf, c, *a)))
    monkeypatch.setattr(R, "key_shot", lambda surf, c, *a: (shot_keys.append(c), real_shot(surf, c, *a)))
    r, fight = pair_frames(surface, [FighterInput(x=True)] + [None] * 16)
    assert fight.tosses and tossed
    t = fight.tosses[0]
    centre = (round(t.x), round(FLOOR_Y - t.y))
    near = {tuple(surface.get_at((centre[0] + dx, centre[1] + dy)))[:3] for dx in range(-3, 4) for dy in range(-3, 4)}
    assert ERROR_COLOUR[basis.X] in near
    for _ in range(14):
        r.draw_fight(fight, fight.step({}))
    (shot,) = fight.shots
    left, top, w, h = shot.box
    assert shot_keys and shot_keys[-1] == (left + w / 2, top + h / 2)
    key = key_sprite(GREEN, True, shot.facing)
    assert key.get_width() > key.get_height()               # lying flat, blade first


def test_a_key_turns_a_quarter_at_a_time_and_flips_with_its_facing():
    from brawl_ket.kids import key_sprite
    flat = key_sprite(GREEN, False)
    assert key_sprite(GREEN, False, 1, 1).get_size() == flat.get_size()[::-1]
    assert key_sprite(GREEN, False, 1, 4).get_size() == flat.get_size()
    left = key_sprite(GREEN, True, -1)
    right = key_sprite(GREEN, True, 1)
    assert pygame.image.tostring(pygame.transform.flip(right, True, False), "RGBA") == \
        pygame.image.tostring(left, "RGBA")


def test_teleport_flashes_at_both_ends_and_both_re_form(surface):
    from brawl_ket.fighter import FighterInput
    from brawl_ket.render import TELEPORT_FRAMES
    # TELEPORT swaps an anchored Bob (the first down + X anchors him)
    r, fight = pair_frames(surface, [FighterInput(down=True, x=True)] + [None] * 7,
                           setup=lambda f: setattr(f.echoes["p1"], "anchored", True))
    assert "p1" in r.teleported
    for _ in range(TELEPORT_FRAMES):
        r.draw_fight(fight, fight.step({}))
    assert "p1" not in r.teleported


def test_every_pair_frame_draws(surface):
    """Bot-free smoke: every special of theirs, a decoherence and a return, on both sides."""
    from brawl_ket.config import DECOHERE_FRAMES
    from brawl_ket.fighter import FighterInput
    from brawl_ket.moves import ALICE_BOB
    for side in ("p1", "p2"):
        other = "p2" if side == "p1" else "p1"
        r = Renderer(surface)
        fight = Fight({side: ALICE_BOB, other: ROBERT})
        presses = {0: FighterInput(x=True), 60: FighterInput(down=True, x=True), 90: FighterInput(up=True),
                   100: FighterInput(x=True), 130: FighterInput(y=True)}
        for i in range(160 + DECOHERE_FRAMES):
            if i == 140:
                fight.echoes[side].decohere()
            r.draw_fight(fight, fight.step({side: presses.get(i, FighterInput())}))
        assert fight.echoes[side].here


def test_their_portrait_shows_both_alice_in_front():
    from brawl_ket.kids import BLONDE, SKIN_A, SKIN_B
    from brawl_ket.render import portrait
    img = portrait("ALICE & BOB")
    seen = {tuple(img.get_at((x, y)))[:3] for x in range(img.get_width()) for y in range(img.get_height())
            if img.get_at((x, y))[3]}
    assert {BLONDE, SKIN_A, SKIN_B} <= seen


def test_the_shared_bar_has_a_bob_icon_that_greys_while_he_is_gone(surface):
    from brawl_ket.kids import BOB_ICON, PHONES, bob_icon
    from brawl_ket.moves import ALICE_BOB
    r = Renderer(surface)
    fight = Fight({"p1": ALICE_BOB, "p2": ROBERT})
    r.draw_fight(fight, fight.step({}))
    here = bob_icon(GREEN, False)
    assert here.get_size() == (BOB_ICON, BOB_ICON)
    assert any(tuple(here.get_at((x, y)))[:3] == PHONES for x in range(BOB_ICON) for y in range(BOB_ICON))
    hud = {tuple(surface.get_at((x, y)))[:3] for x in range(0, 320) for y in range(20, 50)}
    assert PHONES in hud
    fight.echoes["p1"].decohere()
    r.draw_fight(fight, fight.step({}))
    gone = bob_icon(GREEN, True)
    assert all(abs(c[0] - c[1]) <= 8 and abs(c[1] - c[2]) <= 8 for c in
               (tuple(gone.get_at((x, y))) for x in range(BOB_ICON) for y in range(BOB_ICON)) if c[3])
    hud = {tuple(surface.get_at((x, y)))[:3] for x in range(0, 320) for y in range(20, 50)}
    assert PHONES not in hud


def test_an_anchored_bob_wears_a_pin_in_his_players_colour(surface):
    from brawl_ket.config import FLOOR_Y as FLOOR, PLAYER_COLORS
    from brawl_ket.fighter import FighterInput
    from brawl_ket.render import ANCHOR_PIN_Y
    r, fight = pair_frames(surface, [FighterInput(down=True, x=True)] + [None] * 10)
    bob = fight.echoes["p1"]
    assert bob.anchored
    x, y = round(bob.x), FLOOR - ANCHOR_PIN_Y
    seen = {tuple(surface.get_at((i, j)))[:3] for i in range(x - 8, x + 9) for j in range(y - 16, y + 6)}
    assert PLAYER_COLORS["p1"] in seen


def test_spin_turns_her_round_and_back(surface):
    """M-CUTIE's SPIN is a hurricane kick: drawn facing forward, then the other way, then forward."""
    from brawl_ket.fighter import FighterInput
    from brawl_ket.moves import CHARACTERS
    from brawl_ket.render import SPIN_TURN
    import brawl_ket.render as R
    cutie = CHARACTERS["M-CUTIE"]
    r = Renderer(surface)
    fight = Fight({"p1": cutie, "p2": ROBERT})
    fight.fighters["p2"].x = 600.0
    drawn = []
    real_spin, real_puppet = R.draw_spin, R.draw_puppet
    R.draw_spin = lambda surf, pose, feet, facing, *a, **k: (drawn.append(facing), real_spin(surf, pose, feet, facing, *a, **k))[1]
    try:
        r.draw_fight(fight, fight.step({"p1": FighterInput(up=True)}))
        for i in range(12):
            r.draw_fight(fight, fight.step({"p1": FighterInput(x=i == 8)}))
        me = fight.fighters["p1"]
        for _ in range(4 * SPIN_TURN):
            if me.phase != "active":
                r.draw_fight(fight, fight.step({}))
                continue
            r.draw_fight(fight, fight.step({}))
    finally:
        R.draw_spin, R.draw_puppet = real_spin, real_puppet
    assert 1 in drawn and -1 in drawn               # out in front, then out behind


def test_cpu_vs_cpu_names_both_sides_cpu(surface):
    """CPU VS CPU: the fighter screen says whose fighter is being picked, and the HUD and the
    result say CPU1 and CPU2 where a match between people says P1 and P2."""
    import random

    from brawl_ket import config
    from brawl_ket import match as M
    from brawl_ket.render import tags_of
    r = Renderer(surface)
    m = M.Match(random.Random(1))
    assert tags_of(m) == {"p1": "P1", "p2": "P2"}
    title = M.FrameInput(activity=True)
    title.nav["p1"] = (0, 1)
    r.draw(m, m.update(title))
    r.draw(m, m.update(title))                  # (the third row: CPU VS CPU)
    r.draw(m, m.update(M.FrameInput(activity=True, confirms={"p1": True, "p2": False})))
    assert m.state == M.SELECT and tags_of(m) == {"p1": "CPU1", "p2": "CPU2"}
    r.draw(m, [])
    for _ in range(2):
        r.draw(m, m.update(M.FrameInput(activity=True, confirms={"p1": True, "p2": False})))
    for _ in range(M.STAGE_LOCK):
        m.update(M.FrameInput())
    r.draw(m, m.update(M.FrameInput(activity=True, confirms={"p1": True, "p2": False})))
    assert m.state == M.ROUND_INTRO
    for _ in range(config.ROUND_INTRO_FRAMES + 30):
        r.draw(m, m.update(M.FrameInput()))
    assert m.state == M.FIGHT and r.tags["p1"] == "CPU1"


def test_random_shows_a_question_mark_then_whoever_it_rolled(surface):
    import random
    from brawl_ket import match as M
    from brawl_ket.render import silhouette
    r = Renderer(surface)
    m = M.Match(random.Random(1))
    m.state, m.picks = M.SELECT, {"p1": M.RANDOM_FIGHTER, "p2": 0}
    seen = set()
    for _ in range(60):                     # the silhouettes flick past
        r.draw(m, [])
        seen.add(pygame.image.tostring(surface, "RGB"))
    assert len(seen) > 1
    dark = silhouette("ROBERT", 1)
    assert max(max(dark.get_at((x, y))[:3]) for x in range(0, dark.get_width(), 4)
               for y in range(0, dark.get_height(), 4)) <= max(P.NIGHT)
    m._ready("p1")
    r.draw(m, [])                           # READY: the rolled fighter, as any pick
    assert m.fighter("p1") in M.ROSTER


# --- SUPERposition ----------------------------------------------------------------------------------


def test_the_super_bar_shows_each_half_in_its_colour(surface):
    from brawl_ket.fight import Fight
    from brawl_ket.render import SUPER_BAR_H, SUPER_BAR_Y, SUPER_HALF_W
    from brawl_ket.superpos import FULL
    fight = Fight({"p1": ROBERT, "p2": ROBERT})
    fight.meters["p1"].fill = {basis.Z_BASIS: FULL, basis.X_BASIS: FULL // 2}
    r = Renderer(surface)
    r.draw_fight(fight, [], {"p1": 0, "p2": 0})
    y = SUPER_BAR_Y + SUPER_BAR_H // 2
    row = [tuple(surface.get_at((x, y)))[:3] for x in range(0, INTERNAL_WIDTH // 2)]
    assert row.count(GREEN) >= SUPER_HALF_W - 4          # the green half, full
    assert SUPER_HALF_W // 2 - 4 <= row.count(PURPLE) <= SUPER_HALF_W // 2 + 4    # half the purple


def test_dos_bar_is_one_green_bar(surface):
    from brawl_ket.fight import Fight
    from brawl_ket.moves import CHARACTERS
    from brawl_ket.render import SUPER_BAR_H, SUPER_BAR_Y, SUPER_HALF_W
    from brawl_ket.superpos import FULL
    fight = Fight({"p1": CHARACTERS["DOS"], "p2": ROBERT})
    fight.meters["p1"].fill[basis.Z_BASIS] = FULL // 2
    r = Renderer(surface)
    r.draw_fight(fight, [], {"p1": 0, "p2": 0})
    y = SUPER_BAR_Y + SUPER_BAR_H // 2
    row = [tuple(surface.get_at((x, y)))[:3] for x in range(0, INTERNAL_WIDTH // 2)]
    assert SUPER_HALF_W - 4 <= row.count(GREEN) <= SUPER_HALF_W + 4    # half of the whole width, green
    assert PURPLE not in row


def test_a_full_bar_says_a_plus_b_for_a_fighter_with_a_super(surface):
    from brawl_ket.fight import Fight
    from brawl_ket.moves import CHARACTERS
    from brawl_ket.superpos import FULL
    r = Renderer(surface)
    seen = {}
    for name in ("DOS", "ROBERT"):
        from types import MappingProxyType
        from dataclasses import replace as _replace
        char = CHARACTERS[name] if name == "DOS" else _replace(ROBERT, extra=MappingProxyType({}))
        fight = Fight({"p1": char, "p2": ROBERT})
        fight.meters["p1"].fill = {basis.Z_BASIS: FULL, basis.X_BASIS: FULL}
        frames = []
        for _ in range(24):                             # it blinks: look over a whole cycle
            r.draw_fight(fight, [], {"p1": 0, "p2": 0})
            frames.append(surface.subsurface((0, 40, 300, 18)).copy())
        seen[name] = len({pygame.image.tostring(s, "RGB") for s in frames})
    assert seen["DOS"] > seen["ROBERT"]                  # (a fighter with no super: no A+B!)


def test_the_freeze_shows_the_call(surface):
    from brawl_ket.fight import Fight
    from brawl_ket.fighter import FighterInput
    from brawl_ket.moves import CHARACTERS
    from brawl_ket.superpos import FULL
    fight = Fight({"p1": CHARACTERS["DOS"], "p2": ROBERT})
    fight.meters["p1"].fill = {basis.Z_BASIS: FULL, basis.X_BASIS: FULL}
    r = Renderer(surface)
    r.draw_fight(fight, fight.step({"p1": FighterInput(a=True, b=True)}), {"p1": 0, "p2": 0})
    for _ in range(12):
        r.draw_fight(fight, fight.step({}), {"p1": 0, "p2": 0})
    from brawl_ket.render import CALL_Y
    assert fight.freeze > 0
    band = {tuple(surface.get_at((x, y)))[:3] for x in range(100, 540) for y in range(CALL_Y - 16, CALL_Y - 4)}
    assert P.GOLD in band                                # "SUPERposition!" in gold across the middle


def test_choose_your_fighter_lists_the_super_as_a_fourth_row(surface):
    import random
    from brawl_ket import match as M
    from brawl_ket.render import LIST_GAP, list_top
    from brawl_ket.moves import CHARACTERS
    r = Renderer(surface)
    m = M.Match(random.Random(1))
    m.state, m.picks = M.SELECT, {"p1": M.ROSTER.index(CHARACTERS["DOS"]), "p2": 0}
    r.draw(m, [])
    y = list_top(CHARACTERS["DOS"]) + 3 * LIST_GAP + 4
    row = {tuple(surface.get_at((x, y)))[:3] for x in range(20, 300)}
    assert P.GOLD in row                                 # "A+B" in gold, on the fourth line


def test_how_to_play_lists_a_plus_b():
    from brawl_ket.render import BUTTON_JOBS
    assert ("A+B", "SUPER: FULL BAR") in BUTTON_JOBS


def test_the_error_window_is_the_looks(surface):
    from brawl_ket.dos import BSOD_BLUE, draw_error_window
    surface.fill((0, 0, 0))
    win = draw_error_window(surface, (320, 200), "ROBERT")
    assert win.midbottom == (320, 200) and win.w >= 160
    assert tuple(surface.get_at((win.x + 2, win.y + 2)))[:3] == P.MIST            # the title bar
    assert tuple(surface.get_at((win.x + 3, win.centery)))[:3] == BSOD_BLUE         # the blue body
    body = {tuple(surface.get_at((x, y)))[:3] for x in range(win.x, win.right) for y in range(win.y + 14, win.y + 40)}
    assert P.WHITE in body                                                          # its white text


def test_a_frozen_rival_glitches_under_its_window_and_the_landing_flashes_blue(surface):
    from brawl_ket.config import SUPER_FREEZE
    from brawl_ket.dos import BSOD_BLUE
    from brawl_ket.fight import Fight
    from brawl_ket.fighter import FighterInput
    from brawl_ket.moves import BLUE_SCREEN, CHARACTERS
    from brawl_ket.superpos import FULL
    fight = Fight({"p1": CHARACTERS["DOS"], "p2": ROBERT}, seed=1)
    fight.fighters["p1"].x, fight.fighters["p2"].x = 250.0, 400.0
    fight.meters["p1"].fill = {basis.Z_BASIS: FULL, basis.X_BASIS: FULL}
    r = Renderer(surface)
    r.draw_fight(fight, fight.step({"p1": FighterInput(a=True, b=True)}))
    for _ in range(SUPER_FREEZE + BLUE_SCREEN.startup + 4):
        r.draw_fight(fight, fight.step({}))
    assert fight.fighters["p2"].glitch > 0 and "p1" in r.crashes
    above = {tuple(surface.get_at((400 + dx, FLOOR_Y - 180 + dy)))[:3] for dx in range(-60, 60, 3) for dy in range(0, 60, 3)}
    assert BSOD_BLUE in above                                   # the window over their head
    flashed = False
    for _ in range(60):
        events = fight.step({})
        r.draw_fight(fight, events)
        if any(e.kind == "bsod_land" for e in events):
            corner = tuple(surface.get_at((INTERNAL_WIDTH - 5, INTERNAL_HEIGHT - 5)))[:3]
            flashed = corner == BSOD_BLUE
            break
    assert flashed                                              # the whole screen, for that frame


@pytest.mark.parametrize("name", ["ROBERT", "BOHR", "PHOEBE", "ERWIN", "M-CUTIE", "ALICE & BOB"])
@pytest.mark.parametrize("side", ["p1", "p2"])
def test_every_super_draws_from_its_call_to_its_end(surface, name, side):
    from brawl_ket.fighter import FighterInput
    from brawl_ket.superpos import FULL
    chars = {"p1": CHARACTERS[name], "p2": ROBERT} if side == "p1" else {"p1": ROBERT, "p2": CHARACTERS[name]}
    fight = Fight(chars, seed=1)
    fight.fighters["p1"].x, fight.fighters["p2"].x = 260.0, 340.0
    fight.meters[side].fill = {basis.Z_BASIS: FULL, basis.X_BASIS: FULL}
    r = Renderer(surface)
    r.draw_fight(fight, fight.step({side: FighterInput(a=True, b=True)}))
    seen = set()
    for _ in range(220):
        r.draw_fight(fight, fight.step({}))
        seen.add(pygame.image.tostring(surface, "RGB")[::997])
    assert len(seen) > 30                                   # it moves


def test_the_beam_is_white_hot_in_the_middle(surface):
    from brawl_ket.config import SUPER_FREEZE
    from brawl_ket.fighter import FighterInput
    from brawl_ket.moves import COHERENT_BEAM
    from brawl_ket.superpos import FULL
    fight = Fight({"p1": CHARACTERS["PHOEBE"], "p2": ROBERT}, seed=1)
    fight.fighters["p1"].x, fight.fighters["p2"].x = 150.0, 560.0
    fight.meters["p1"].fill = {basis.Z_BASIS: FULL, basis.X_BASIS: FULL}
    r = Renderer(surface)
    r.draw_fight(fight, fight.step({"p1": FighterInput(a=True, b=True)}))
    for _ in range(SUPER_FREEZE + COHERENT_BEAM.startup + 10):
        r.draw_fight(fight, fight.step({}))
    assert min(tuple(surface.get_at((400, FLOOR_Y - 55)))[:3]) >= 230     # (the core is 240/255 opaque)


def test_the_fridge_lands_gold_on_the_locked_spot(surface):
    from brawl_ket.config import SUPER_FREEZE
    from brawl_ket.fighter import FighterInput
    from brawl_ket.moves import DILUTION_FRIDGE
    from brawl_ket.superart import GOLD_PLATE
    from brawl_ket.superpos import FULL
    fight = Fight({"p1": CHARACTERS["M-CUTIE"], "p2": ROBERT}, seed=1)
    fight.fighters["p1"].x, fight.fighters["p2"].x = 150.0, 450.0
    fight.meters["p1"].fill = {basis.Z_BASIS: FULL, basis.X_BASIS: FULL}
    r = Renderer(surface)
    r.draw_fight(fight, fight.step({"p1": FighterInput(a=True, b=True)}))
    for _ in range(SUPER_FREEZE + DILUTION_FRIDGE.startup + 2):
        r.draw_fight(fight, fight.step({}))
    area = {tuple(surface.get_at((x, y)))[:3] for x in range(380, 520, 2) for y in range(FLOOR_Y - 200, FLOOR_Y, 2)}
    assert GOLD_PLATE in area


def test_the_title_shows_the_cpus_level_in_its_colour(surface):
    import random
    from brawl_ket import match as M
    from brawl_ket.render import LEVEL_COLOURS
    r = Renderer(surface)
    m = M.Match(random.Random(1))
    seen = {}
    for level in range(3):
        m.level = level
        r.draw(m, [])
        seen[level] = {tuple(surface.get_at((x, y)))[:3] for x in range(200, 440, 2) for y in range(200, 290, 2)}
    assert LEVEL_COLOURS["EASY"] in seen[0] and LEVEL_COLOURS["BRUTAL"] in seen[2]


def test_a_one_time_pad_that_catches_nobody_flashes_both_kids(surface):
    from brawl_ket.config import SUPER_FREEZE
    from brawl_ket.fighter import FighterInput
    from brawl_ket.moves import ONE_TIME_PAD
    from brawl_ket.superpos import FULL
    fight = Fight({"p1": CHARACTERS["ALICE & BOB"], "p2": ROBERT}, seed=1)
    fight.fighters["p1"].x, fight.fighters["p2"].x = 200.0, 400.0     # out of its reach
    fight.meters["p1"].fill = {basis.Z_BASIS: FULL, basis.X_BASIS: FULL}
    r = Renderer(surface)
    r.draw_fight(fight, fight.step({"p1": FighterInput(a=True, b=True)}))
    flashed = set()
    for _ in range(SUPER_FREEZE + ONE_TIME_PAD.startup + 4):
        events = r_events = fight.step({})
        r.draw_fight(fight, r_events)
        if any(e.kind == "lock_miss" for e in events):
            flashed = {b for b in ("p1", "p1/bob") if r.body_flash[b][0] == P.WHITE}
    assert flashed == {"p1", "p1/bob"}


def test_a_whiff_sizzles():
    from brawl_ket import audio
    assert audio.EVENT_SOUNDS["lock_miss"] == "sizzle"


def bsod_fight(gap: float):
    from brawl_ket.fighter import FighterInput
    from brawl_ket.superpos import FULL
    fight = Fight({"p1": CHARACTERS["DOS"], "p2": ROBERT}, seed=1)
    fight.fighters["p1"].x, fight.fighters["p2"].x = 250.0, 250.0 + gap
    fight.meters["p1"].fill = {basis.Z_BASIS: FULL, basis.X_BASIS: FULL}
    return fight, {"p1": FighterInput(a=True, b=True)}


@pytest.mark.parametrize("gap", [60.0, 150.0])
def test_the_stopped_responding_window_shows_over_a_close_rival_for_the_whole_freeze(surface, gap):
    from brawl_ket.dos import BSOD_BLUE
    fight, ab = bsod_fight(gap)
    r = Renderer(surface)
    r.draw_fight(fight, fight.step(ab))
    shown = frozen = 0
    for _ in range(200):
        events = fight.step({})
        r.draw_fight(fight, events)
        if any(e.kind == "bsod_land" for e in events):
            break
        rival = fight.fighters["p2"]
        if rival.glitch > 0 and fight.freeze == 0:
            frozen += 1
            above = {tuple(surface.get_at((round(rival.x) + dx, FLOOR_Y - 175 + dy)))[:3]
                     for dx in range(-60, 60, 3) for dy in range(0, 40, 3)}
            shown += BSOD_BLUE in above
    assert frozen >= 35 and shown == frozen


def test_the_drop_turns_the_whole_screen_blue_with_the_crash_text_then_crash(surface):
    from brawl_ket.dos import BSOD_BLUE
    from brawl_ket.render import BSOD_SCREEN_FRAMES
    fight, ab = bsod_fight(150.0)
    r = Renderer(surface)
    r.draw_fight(fight, fight.step(ab))
    for _ in range(200):
        events = fight.step({})
        r.draw_fight(fight, events)
        if any(e.kind == "bsod_land" for e in events):
            break
    assert 25 <= BSOD_SCREEN_FRAMES <= 35
    blue = 0
    for n in range(BSOD_SCREEN_FRAMES + 10):
        if n:
            r.draw_fight(fight, fight.step({}))
        corners = {tuple(surface.get_at(p))[:3] for p in ((4, 4), (INTERNAL_WIDTH - 5, INTERNAL_HEIGHT - 5))}
        if corners == {BSOD_BLUE}:
            blue += 1
            text = {tuple(surface.get_at((x, y)))[:3] for x in range(100, 540, 2) for y in range(60, 200, 2)}
            assert P.WHITE in text                  # the big crash text
            assert not any(fx.text == "CRASH!" for fx in r.effects)
        elif blue:
            break
    assert BSOD_SCREEN_FRAMES - 2 <= blue <= BSOD_SCREEN_FRAMES
    assert any(fx.text == "CRASH!" for fx in r.effects)    # and then the burst


def test_the_bloch_sphere_is_drawn_100_px_across(surface):
    from brawl_ket.config import SUPER_FREEZE
    from brawl_ket.fighter import FighterInput
    from brawl_ket.moves import BLOCH_SPHERE
    from brawl_ket.render import BLOCH_R
    from brawl_ket.superpos import FULL
    assert 2 * BLOCH_R == BLOCH_SPHERE.hitbox.h
    fight = Fight({"p1": CHARACTERS["ROBERT"], "p2": ROBERT}, seed=1)
    fight.fighters["p1"].x, fight.fighters["p2"].x = 150.0, 560.0
    fight.meters["p1"].fill = {basis.Z_BASIS: FULL, basis.X_BASIS: FULL}
    r = Renderer(surface)
    r.draw_fight(fight, fight.step({"p1": FighterInput(a=True, b=True)}))
    for _ in range(SUPER_FREEZE + BLOCH_SPHERE.startup + 4):
        r.draw_fight(fight, fight.step({}))
    x = round(fight.fighters["p1"].x)
    light = P.lighten(BASIS_BODY[fight.fighters["p1"].basis], 0.55)
    rim = [y for dx in range(-30, 31, 2) for y in range(FLOOR_Y - 130, FLOOR_Y)
           if tuple(surface.get_at((x + dx, y)))[:3] == light]
    assert rim and FLOOR_Y - min(rim) >= 2 * BLOCH_R - 4         # its rim, about 100 px up
