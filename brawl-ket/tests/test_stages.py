"""The backdrops (stages.py): each one draws at the right size with its lights on screen,
a match picks one and keeps it for all its rounds, and the matches don't all look alike."""

from __future__ import annotations

import random

import pygame
import pytest

from brawl_ket import config
from brawl_ket import palette as P
from brawl_ket.fight import Fight
from brawl_ket.match import Match
from brawl_ket.moves import BOHR, PHOEBE
from brawl_ket.render import Renderer
from brawl_ket.stages import MARGIN, make_stage
from test_match import ko, to_fight

W, H = config.INTERNAL_WIDTH, config.INTERNAL_HEIGHT


@pytest.fixture(scope="module", autouse=True)
def _pygame():
    pygame.init()
    yield


@pytest.mark.parametrize("name", config.STAGES)
def test_every_stage_draws_with_its_lights_on_screen(name):
    surf, lights = make_stage(name)
    assert surf.get_size() == (W + 2 * MARGIN, H + 2 * MARGIN)
    screen = pygame.Rect(0, 0, W, H)
    for rect, colour in lights:
        assert screen.contains(rect), (name, rect)
        assert len(colour) == 3


@pytest.mark.parametrize("name", config.STAGES)
def test_every_stage_has_a_solid_floor_line(name):
    # the fighters' shadows sit on an ink band just above FLOOR_Y, the same in every room
    surf, _ = make_stage(name)
    y = config.FLOOR_Y + MARGIN - 3
    assert all(tuple(surf.get_at((x, y)))[:3] == P.INK for x in range(W + 2 * MARGIN)), name


def test_a_match_keeps_its_stage_for_every_round():
    m = Match(random.Random(3))
    to_fight(m)
    stage = m.stage
    assert stage in config.STAGES
    ko(m, "p2")
    assert m.stage == stage


def test_matches_and_demos_are_not_all_in_the_same_room():
    seen = set()
    for seed in range(20):
        m = Match(random.Random(seed))
        to_fight(m)
        seen.add(m.stage)
    assert len(seen) >= 3


def test_the_renderer_draws_a_fight_in_every_stage():
    surf = pygame.Surface((W, H))
    r = Renderer(surf)
    fight = Fight({"p1": PHOEBE, "p2": BOHR})
    for name in config.STAGES:
        r.use_stage(name)
        r.draw_fight(fight, [])
        assert r.stage_name == name
