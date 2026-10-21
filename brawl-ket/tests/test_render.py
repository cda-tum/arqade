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
                                  RULE_LINES, TRAITS)
    parts = (*CARD_LINES, *LESSON_LINES)
    for text in (HINT, ANY_BUTTON, *RULE_LINES, *CLASSICAL_LINES, *TRAITS.values(), *GOAL_LINES, *(job for _b, job in BUTTON_JOBS),
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
    inp.nav["p1"] = (0, 1)
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


def test_superposed_erwin_is_two_boxes_drawn_from_cached_sprites(surface):
    from brawl_ket.erwin import FADE_STEPS, HOLO_PHASES, holo_sprite
    from brawl_ket.stages import MARGIN
    holo_sprite.cache_clear()
    r = Renderer(surface)
    fight = boxed_fight(r)
    # every box sprite is built as the fight starts (a hitch on the cabinet otherwise, the first
    # time she boxes), all of them fit the cache, and drawing her boxed builds nothing new
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


def test_blue_screen_turns_his_face_blue_and_rings_out_green(surface):
    from brawl_ket.dos import BSOD
    from brawl_ket.moves import DOS
    r = Renderer(surface)
    fight = dos_frames(r, {"down": True, "x": True}, DOS.moves["crouch.X"].startup + 2)
    dos = fight.fighters["p1"]
    assert dos.phase == "active"
    x = round(dos.x)
    face = {tuple(surface.get_at((i, j)))[:3] for i in range(x - 30, x + 31, 2) for j in range(FLOOR_Y - 150, FLOOR_Y - 60)}
    assert BSOD in face
    ring = {tuple(surface.get_at((i, FLOOR_Y - 55)))[:3] for i in range(x + 30, x + 80)}
    assert ring & {GREEN, P.lighten(GREEN, 0.35), P.WHITE}


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
    for name in ("ROBERT", "BOHR", "PHOEBE"):
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
    assert PURPLE in seen               # ERWIN on the right: DOS, last in the roster, can't be purple
