"""Smoke tests: bot-against-bot fights render without errors."""

import pygame
import pytest

from brawl_ket import palette as P
from brawl_ket import basis
from brawl_ket.basis import X_BASIS, Z_BASIS
from brawl_ket.bot import Bot
from brawl_ket.config import FLOOR_Y, INTERNAL_HEIGHT, INTERNAL_WIDTH
from brawl_ket.fight import Event, Fight
from brawl_ket.moves import CHARACTERS, QUINT, TRIO
from brawl_ket.render import BASIS_BODY, ERROR_COLOUR, GREEN, PURPLE, Renderer

PAIRINGS = [(a, b) for a in CHARACTERS.values() for b in CHARACTERS.values()]


@pytest.fixture
def surface():
    pygame.init()
    return pygame.Surface((INTERNAL_WIDTH, INTERNAL_HEIGHT))


def bot_frames(n, seed=1, chars=(TRIO, TRIO)):
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
    fight = Fight({"p1": QUINT, "p2": TRIO})
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
    fight = Fight({"p1": TRIO, "p2": TRIO})
    for wins in ({"p1": 0, "p2": 0}, {"p1": 1, "p2": 0}, {"p1": 1, "p2": 1}):
        r.draw_fight(fight, [], wins)


def test_effects_expire(surface):
    r = Renderer(surface)
    fight = Fight({"p1": TRIO, "p2": TRIO})
    r.draw_fight(fight, [Event("hit", "p2", "X", 330, 220), Event("block", "p1", "Z", 300, 250)])
    assert r.effects
    for _ in range(240):
        r.draw_fight(fight, [])
    assert not r.effects
    assert r.shake == 0


def test_the_floor_is_drawn_where_the_fighters_stand(surface):
    r = Renderer(surface)
    r.draw_fight(Fight({"p1": TRIO, "p2": TRIO}), [])
    # away from the fighters, just below FLOOR_Y is floor and just above it is wall
    xs = range(0, 150, 3)
    floor = {tuple(surface.get_at((x, FLOOR_Y + 3)))[:3] for x in xs} - {P.INK}
    wall = {tuple(surface.get_at((x, FLOOR_Y - 12)))[:3] for x in xs} - {P.INK}
    assert floor and wall and not floor & wall


BLANK = (1, 2, 3)


def test_a_cancel_blends_out_of_the_pose_drawn(surface):
    from brawl_ket.poses import EASE_FRAMES, POSES, lerp

    r = Renderer(surface)
    f = Fight({"p1": TRIO, "p2": TRIO}).fighters["p1"]
    jab, heavy = TRIO.moves["stand.A"], TRIO.moves["stand.B"]
    f.action, f.move, f.slot, f.frame = "attack", jab, "stand.A", jab.startup
    assert r._pose("p1", f) == POSES["jab_hit"]
    f.move, f.slot, f.frame = heavy, "stand.B", 0          # cancelled into the heavy
    assert r._pose("p1", f) == lerp(POSES["jab_hit"], POSES["heavy_wind"], 1 / EASE_FRAMES)
    f.move, f.slot, f.frame = jab, "stand.A", jab.startup   # and a jab into a jab: frame went back
    r._pose("p1", f)
    f.frame = 0
    assert r._pose("p1", f) == lerp(POSES["jab_hit"], POSES["jab_wind"], 1 / EASE_FRAMES)


def test_quint_is_drawn_broader_than_trio(surface):
    # the same pose (arms up, out of the way): across the chest, QUINT is far broader
    from brawl_ket.poses import POSES, joints
    from brawl_ket.render import draw_puppet

    widths = {}
    for c in (TRIO, QUINT):
        surface.fill(BLANK)
        pose = POSES["slam"]
        draw_puppet(surface, pose, c.build, (320, FLOOR_Y), 1, (64, 136, 248), P.GOLD)
        j = joints(pose, c.build, (320, FLOOR_Y), 1)
        chest = round(j["hip"][1] + 0.6 * (j["shoulder_f"][1] - j["hip"][1]))
        xs = [x for x in range(INTERNAL_WIDTH) if tuple(surface.get_at((x, chest)))[:3] != BLANK]
        widths[c.name] = max(xs) - min(xs) + 1
    assert widths["QUINT"] >= widths["TRIO"] * 1.6, widths


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
                getattr(inp, name)[player] = value
            r.draw(m, m.update(inp))
            seen.add((m.state, m.paused, m.attract is not None))

    step(config.ATTRACT_DELAY + 120)                # the title, then its demo
    step(confirms=("p1", True))
    step(confirms=("p1", True))                     # select
    step(confirms=("p1", True))
    step(nav=("p2", (1, 0)))
    step(confirms=("p2", True))
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
    assert states == {M.TITLE, M.SELECT, M.ROUND_INTRO, M.FIGHT, M.ROUND_END, M.MATCH_RESULT}
    assert (M.TITLE, False, True) in seen and (M.ROUND_INTRO, True, False) in seen


def test_a_new_popup_replaces_an_older_one_beside_it(surface):
    # jab, heavy: the heavy's Z! must not be drawn over the jab's X!, still rising
    r = Renderer(surface)
    fight = Fight({"p1": TRIO, "p2": TRIO})
    r.draw_fight(fight, [Event("hit", "p2", basis.X, 400, 200)])
    for _ in range(10):
        r.draw_fight(fight, [])
    r.draw_fight(fight, [Event("hit", "p2", basis.Z, 404, 202), Event("hit", "p1", basis.X, 100, 200)])
    assert {fx.x: fx.text for fx in r.effects if fx.kind == "popup"} == {404: "Z!", 100: "X!"}


def test_popups_started_in_the_same_frame_all_survive(surface):
    # only pop-ups from earlier frames are replaced, never one this frame's events just started
    r = Renderer(surface)
    fight = Fight({"p1": TRIO, "p2": TRIO})
    r.draw_fight(fight, [Event("hit", "p2", basis.X, 400, 200), Event("hit", "p1", basis.X, 410, 200)])
    assert sorted(fx.x for fx in r.effects if fx.kind == "popup") == [400, 410]


def body_pixels(surface, r, fight, key):
    """The colours drawn in a small box round the fighter's torso."""
    f = fight.fighters[key]
    x = round(f.x)
    return {tuple(surface.get_at((i, j)))[:3] for i in range(x - 4, x + 5) for j in range(FLOOR_Y - 90, FLOOR_Y - 60)}


def test_a_body_is_drawn_in_its_basis_colour(surface):
    r = Renderer(surface)
    fight = Fight({"p1": TRIO, "p2": QUINT})
    fight.fighters["p2"].basis = X_BASIS
    r.draw_fight(fight, [])
    assert GREEN in body_pixels(surface, r, fight, "p1") and PURPLE not in body_pixels(surface, r, fight, "p1")
    assert PURPLE in body_pixels(surface, r, fight, "p2") and GREEN not in body_pixels(surface, r, fight, "p2")
    assert BASIS_BODY == {Z_BASIS: GREEN, X_BASIS: PURPLE}
    assert ERROR_COLOUR[basis.X] == GREEN and ERROR_COLOUR[basis.Z] == PURPLE


def test_a_block_pings_in_the_attacks_colour(surface):
    r = Renderer(surface)
    fight = Fight({"p1": TRIO, "p2": TRIO})
    r.draw_fight(fight, [Event("block", "p2", basis.Z, 400, 200)])
    (ping,) = [fx for fx in r.effects if fx.kind == "ping"]
    assert ping.color == PURPLE and not [fx for fx in r.effects if fx.kind == "popup"]
    for _ in range(30):
        r.draw_fight(fight, [])
    assert not r.effects


def test_the_rings_under_the_feet_are_the_players_colours(surface):
    from brawl_ket.config import PLAYER_COLORS
    r = Renderer(surface)
    fight = Fight({"p1": TRIO, "p2": TRIO})
    r.draw_fight(fight, [])
    for key in ("p1", "p2"):
        x = round(fight.fighters[key].x)
        ring = {tuple(surface.get_at((i, j)))[:3] for i in range(x - 34, x + 35) for j in range(FLOOR_Y - 6, FLOOR_Y + 10)}
        assert PLAYER_COLORS[key] in ring, key


def test_the_badges_show_each_basis(surface):
    r = Renderer(surface)
    fight = Fight({"p1": TRIO, "p2": TRIO})
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
    fight = Fight({"p1": TRIO, "p2": TRIO})
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
        fight = Fight({"p1": TRIO, "p2": TRIO})
        fight.fighters["p2"].x = 600
        for i in range(3):
            r.draw_fight(fight, fight.step({"p1": FighterInput(down=down, **{button: i == 0})}))
        f = fight.fighters["p1"]
        assert f.action == "attack" and f.phase == "startup", button
        j = joints(r.pose_last["p1"], TRIO.build, (f.x, FLOOR_Y - f.y), f.facing)
        seen = limb_colours(surface, r, f, j, a, b)
        assert seen == {colour} or seen <= {colour, P.lighten(colour, 0.5)}, (button, down, seen)


def test_each_hud_shows_its_players_a_and_b_colours(surface):
    from brawl_ket.render import legend_colours
    fight = Fight({"p1": TRIO, "p2": TRIO})
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
    fight = Fight({"p1": TRIO, "p2": TRIO})
    fight.fighters["p2"].x = 600
    for i in range(TRIO.moves["stand.B"].startup + 3):
        r.draw_fight(fight, fight.step({"p1": FighterInput(b=i == 0)}))
    assert fight.fighters["p1"].phase == "active"
    assert len(r.trails["p1"]) >= 2
def test_the_teaching_text_is_ascii_capitals():
    from brawl_ket.render import CARD_LINES, HINT, RULE_LINES
    for text in (HINT, *RULE_LINES, *("".join(t for t, _ in parts) for parts in CARD_LINES)):
        assert text.isascii() and text == text.upper(), text


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

    from brawl_ket import match as M
    r = Renderer(surface)
    m = M.Match(random.Random(1))
    for kind in ("p1", "p1", "p2"):
        inp = M.FrameInput(activity=True)
        inp.confirms[kind] = True
        m.update(inp)
    assert m.state == M.ROUND_INTRO and m.hint
    r.draw(m, [])
