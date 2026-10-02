"""Smoke tests: bot-against-bot fights render without errors."""

import pygame
import pytest

from brawl_ket import palette as P
from brawl_ket import shor
from brawl_ket.bot import Bot
from brawl_ket.config import FLOOR_Y, INTERNAL_HEIGHT, INTERNAL_WIDTH
from brawl_ket.fight import Event, Fight
from brawl_ket.moves import CHARACTERS, QUINT, TRIO
from brawl_ket.render import DANGER_BEAT, TAG_EDGE, TAG_HALF, Renderer

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
    assert {"hit", "logical"} <= kinds      # the effects were exercised


def test_the_shockwave_and_reencode_effects_draw_and_expire(surface):
    r = Renderer(surface)
    fight = Fight({"p1": QUINT, "p2": TRIO})
    r.draw_fight(fight, [])
    r.draw_fight(fight, [Event("shockwave", "p1", "Z", fight.fighters["p1"].x, FLOOR_Y),
                         Event("reencode", "p1")])
    kinds = {fx.kind for fx in r.effects}
    assert {"wave", "pulse"} <= kinds
    assert r.flash["p1"][0] is not None             # the lights flash as they are wiped
    # the wave is drawn along the floor, around where the slam landed, then in Z's colour
    x = round(fight.fighters["p1"].x)
    row = {tuple(surface.get_at((i, FLOOR_Y - 2)))[:3] for i in range(x - 50, x + 50)}
    assert P.WHITE in row                           # the white flash of the impact
    for _ in range(8):                              # and it spreads out to the shockwave's reach
        r.draw_fight(fight, [])
    far = {tuple(surface.get_at((i, j)))[:3] for i in range(x - 56, x - 30) for j in range(FLOOR_Y - 12, FLOOR_Y + 8)}
    assert far & {P.GATE["Z"], P.lighten(P.GATE["Z"], 0.35)}
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
    r.draw_fight(fight, [Event("hit", "p2", "X", 330, 220), Event("logical", "p1", "Z", 300, 250),
                         Event("corrected", "p1")])
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


def tags_for(r, fight):
    """Where the two code tags go for the fighters as they stand (heads straight over x)."""
    tags = {p: r._tag_place(p, fight.fighters[p], (fight.fighters[p].x, 150.0 + 60 * (p == "p1")))
            for p in ("p1", "p2")}
    r._separate(tags, fight)
    return tags


@pytest.mark.parametrize("chars", PAIRINGS, ids=lambda cs: "-".join(c.name for c in cs))
def test_code_tags_stay_on_their_own_side(surface, chars):
    r = Renderer(surface)
    h1 = h2 = TAG_HALF
    for p1_x, p2_x in ((300, 330), (330, 300), (320, 320), (600, 616), (24, 40), (616, 600)):
        fight = Fight({"p1": chars[0], "p2": chars[1]})
        fight.fighters["p1"].x, fight.fighters["p2"].x = p1_x, p2_x
        r._reset()
        tags = tags_for(r, fight)
        a, b = tags["p1"][0], tags["p2"][0]
        assert abs(a - b) >= h1 + h2 - 1e-9, (p1_x, p2_x)      # even 60 px apart vertically
        if p1_x != p2_x:
            assert (a < b) == (p1_x < p2_x), (p1_x, p2_x)
        lo, hi = TAG_HALF + TAG_EDGE, INTERNAL_WIDTH - TAG_HALF - TAG_EDGE
        for x in (a, b):
            assert lo - 1e-9 <= x <= hi + 1e-9, (p1_x, p2_x)
            assert x - TAG_HALF >= 0 and x + TAG_HALF <= INTERNAL_WIDTH


BLANK = (1, 2, 3)


def drawn_columns(surface, r, f, key, cx=320, cy=120):
    """Draw only key's tag, centred at cx on a blank surface; the x range of what was drawn."""
    surface.fill(BLANK)
    r._code_tag(key, f, [cx, cy, cx], 0, 0)
    xs = [x for x in range(INTERNAL_WIDTH) for y in range(cy - 24, cy + 28)
          if tuple(surface.get_at((x, y)))[:3] != BLANK]
    return min(xs), max(xs)


@pytest.mark.parametrize("char", list(CHARACTERS.values()), ids=lambda c: c.name)
def test_a_tag_is_drawn_inside_its_own_width(surface, char):
    r = Renderer(surface)
    fight = Fight({"p1": TRIO, "p2": char})
    f = fight.fighters["p2"]
    half = TAG_HALF
    left, right = drawn_columns(surface, r, f, "p2")
    assert 320 - half <= left and right <= 320 + half
    assert right >= 320 + half - 2           # the ring is the widest part: the width is not padded out
    f.code.apply_x(shor.HIGH, shor.A_COL)
    f.code.apply_z(shor.LOW)                 # danger in every row
    left, right = drawn_columns(surface, r, f, "p2")
    assert 320 - half <= left and right <= 320 + half
    r.flash["p2"] = (P.GOOD, 21)
    left, right = drawn_columns(surface, r, f, "p2")
    assert 320 - half <= left and right <= 320 + half


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


def colours_in_tag(surface, r, fight, key, frames):
    """Every colour drawn in a tag's rectangle, over `frames` frames."""
    seen = set()
    half = round(TAG_HALF)
    for _ in range(frames):
        r.draw_fight(fight, [])
        tag_y = r.tag_y[key]
        x = round(fight.fighters[key].x)
        area = pygame.Rect(x - half, round(tag_y) - 18, 2 * half, 42).clip(surface.get_rect())
        seen |= {tuple(surface.get_at((i, j)))[:3] for i in range(area.left, area.right)
                 for j in range(area.top, area.bottom)}
    return seen


@pytest.mark.parametrize("char", list(CHARACTERS.values()), ids=lambda c: c.name)
def test_the_danger_state_is_drawn_on_the_tag(surface, char):
    r = Renderer(surface)
    fight = Fight({"p1": TRIO, "p2": char})
    p2 = fight.fighters["p2"]
    safe = colours_in_tag(surface, r, fight, "p2", DANGER_BEAT * 2)
    assert P.ORANGE not in safe and P.shade(P.ORANGE, 0.6) not in safe
    p2.code.apply_x(shor.HIGH, shor.A_COL)   # one X in HIGH: a B there breaks the code
    danger = colours_in_tag(surface, r, fight, "p2", DANGER_BEAT * 2)
    assert P.ORANGE in danger                # the row's other cells pulse orange
    assert P.GATE[shor.X] in danger          # the lit cell
    p2.code.reset()
    p2.code.apply_z(shor.MID)                # a flipped row: a special at another height breaks it
    danger = colours_in_tag(surface, r, fight, "p2", DANGER_BEAT * 2)
    assert P.shade(P.ORANGE, 0.6) in danger  # the other rows' backing pulses
    assert P.GATE[shor.Z] in danger          # the flipped row's backing


def test_a_bot_fight_with_the_danger_state_draws(surface):
    r = Renderer(surface)
    danger_seen = False
    for fight, events in bot_frames(900):
        r.draw_fight(fight, events)
        danger_seen |= any(f.code.x_danger_rows() or f.code.z_danger_rows()
                           for f in fight.fighters.values())
    assert danger_seen


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


def test_the_grid_lights_an_x_cell_and_a_z_row(surface):
    from brawl_ket import shor
    r = Renderer(surface)
    fight = Fight({"p1": TRIO, "p2": TRIO})
    f = fight.fighters["p1"]
    f.code.apply_x(shor.HIGH, shor.B_COL)
    f.code.apply_z(shor.LOW)
    r.draw_fight(fight, [])
    r._tag_place("p1", f, (f.x, 200))
    surface.fill((0, 0, 0))
    r._code_tag("p1", f, (160, 120, 160), 0, 0)
    from brawl_ket.render import CELL, CELL_GAP, PLATE
    left, top = 160 - PLATE // 2, 120 - PLATE // 2
    x_cell = (left + 4 + 1 * (CELL + CELL_GAP) + 3, top + 4 + 3)          # (HIGH, B)
    z_back = (left + 3, top + 4 + 2 * (CELL + CELL_GAP) + 3)              # LOW row, left edge
    assert tuple(surface.get_at(x_cell))[:3] == P.GATE[shor.X]
    assert tuple(surface.get_at(z_back))[:3] == P.GATE[shor.Z]


def test_a_cancel_pops_its_cell_white_on_the_tag(surface):
    from brawl_ket import shor
    from brawl_ket.render import CELL, CELL_GAP, PLATE
    r = Renderer(surface)
    fight = Fight({"p1": TRIO, "p2": TRIO})
    r.draw_fight(fight, [Event("cancel", "p2", shor.X, 400, 200, shor.MID, shor.B_COL)])
    assert r.pops["p2"] and r.pops["p2"][0][:2] == (shor.MID, shor.B_COL)
    surface.fill((0, 0, 0))
    r._code_tag("p2", fight.fighters["p2"], (160, 120, 160), 0, 0)
    left, top = 160 - PLATE // 2, 120 - PLATE // 2
    cell = (left + 4 + shor.B_COL * (CELL + CELL_GAP) + 3, top + 4 + shor.MID * (CELL + CELL_GAP) + 3)
    assert tuple(surface.get_at(cell))[:3] == P.WHITE
    for _ in range(30):
        r.draw_fight(fight, [])
    assert r.pops["p2"] == []


def test_a_new_popup_replaces_an_older_one_beside_it(surface):
    # jab, jab: the cancel's I must not be drawn over the first jab's X!, still rising
    from brawl_ket import shor
    r = Renderer(surface)
    fight = Fight({"p1": TRIO, "p2": TRIO})
    r.draw_fight(fight, [Event("hit", "p2", shor.X, 400, 200, shor.HIGH, shor.A_COL)])
    for _ in range(10):
        r.draw_fight(fight, [])
    r.draw_fight(fight, [Event("cancel", "p2", shor.X, 404, 202, shor.HIGH, shor.A_COL),
                         Event("hit", "p1", shor.X, 100, 200, shor.HIGH, shor.A_COL)])
    assert sorted(fx.text for fx in r.effects if fx.kind == "popup") == ["I", "X!"]
    assert {fx.x for fx in r.effects if fx.kind == "popup"} == {404, 100}
