"""Smoke tests: bot-against-bot fights render without errors."""

import pygame
import pytest

from brawl_ket import palette as P
from brawl_ket.bot import Bot
from brawl_ket.config import FLOOR_Y, INTERNAL_HEIGHT, INTERNAL_WIDTH
from brawl_ket.fight import Event, Fight
from brawl_ket.moves import TRIO
from brawl_ket.render import Renderer


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
