"""Smoke tests: bot-against-bot fights render without errors."""

import pygame
import pytest

from brawl_ket import palette as P
from brawl_ket.bot import Bot
from brawl_ket.config import FLOOR_Y, INTERNAL_HEIGHT, INTERNAL_WIDTH
from brawl_ket.fight import Event, Fight
from brawl_ket.moves import TRIO
from brawl_ket.render import TAG_HI, TAG_LO, TAG_W, Renderer


@pytest.fixture
def surface():
    pygame.init()
    return pygame.Surface((INTERNAL_WIDTH, INTERNAL_HEIGHT))


def bot_frames(n, seed=1):
    """n frames of bot-against-bot TRIO fights, starting a new round when one ends."""
    fight, bots = None, {}
    for i in range(n):
        if fight is None or fight.over:
            fight = Fight({"p1": TRIO, "p2": TRIO})
            bots = {"p1": Bot("p1", seed + i), "p2": Bot("p2", seed + i + 1000)}
        yield fight, fight.step({k: b.input(fight) for k, b in bots.items()})


def test_600_bot_frames_draw(surface):
    r = Renderer(surface)
    kinds = set()
    for fight, events in bot_frames(600):
        r.draw_fight(fight, events)
        kinds |= {e.kind for e in events}
    assert {"hit", "logical"} <= kinds      # the effects were exercised


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


def test_code_tags_stay_on_their_own_side(surface):
    r = Renderer(surface)
    for p1_x, p2_x in ((300, 330), (330, 300), (320, 320), (600, 616), (24, 40)):
        fight = Fight({"p1": TRIO, "p2": TRIO})
        fight.fighters["p1"].x, fight.fighters["p2"].x = p1_x, p2_x
        r._reset()
        tags = tags_for(r, fight)
        a, b = tags["p1"][0], tags["p2"][0]
        assert abs(a - b) >= TAG_W - 1e-9, (p1_x, p2_x)        # even 60 px apart vertically
        if p1_x != p2_x:
            assert (a < b) == (p1_x < p2_x), (p1_x, p2_x)
        assert TAG_LO <= min(a, b) and max(a, b) <= TAG_HI, (p1_x, p2_x)


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
