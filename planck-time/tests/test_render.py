"""Smoke tests: every screen and every microgame renders without errors,
in single player and versus, paused or not."""

import random

import pygame
import pytest

from planck_time import config
from planck_time import session as S
from planck_time.hiscores import Hiscores
from planck_time.microgames import PlayerInput
from planck_time.render import Renderer
from planck_time.session import FrameInput, Session

DT = 1 / 60


@pytest.fixture
def surface():
    pygame.init()
    return pygame.Surface((config.INTERNAL_WIDTH, config.INTERNAL_HEIGHT))


def drive(s, r, seconds, play=lambda g: g.bot(), inp=None):
    seen = set()
    for _ in range(round(seconds / DT)):
        fi = inp() if inp else FrameInput(activity=True)
        if s.state == S.PLAY and not inp:
            fi.players = {p: play(g) for p, g in s.games.items()} | {
                p: PlayerInput() for p in S.PLAYERS if p not in s.games}
        r.draw(s, s.update(DT, fi), DT)
        seen.add(s.state)
    return seen


@pytest.mark.parametrize("mode", (1, 2))
def test_a_whole_run_renders(surface, mode):
    s = Session(random.Random(mode), Hiscores(None))
    s.mode = mode
    r = Renderer(surface)
    r.draw(s, [], DT)
    s.update(DT, FrameInput(activity=True, confirms={"p1": True, "p2": False}))
    seen = drive(s, r, 60, play=lambda g: g.bot())  # every microgame, well played
    assert {S.INTRO, S.PLAY, S.RESULT, S.SPEED_UP} <= seen
    seen = drive(s, r, 60, play=lambda g: PlayerInput())  # then run out of lives
    assert (S.GAME_OVER if mode == 1 else S.MATCH_RESULT) in seen


def test_title_attract_name_entry_and_hiscores_render(surface):
    s = Session(random.Random(0), Hiscores(None))
    r = Renderer(surface)
    assert S.TITLE in drive(s, r, config.ATTRACT_DELAY + 6, inp=lambda: FrameInput(activity=False))
    assert s.attract
    s.mode = 1
    s.update(DT, FrameInput(activity=True, confirms={"p1": True, "p2": False}))
    seen = drive(s, r, 50, play=lambda g: g.bot() if s.score == 0 else PlayerInput())  # 0 never qualifies
    assert S.NAME_ENTRY in seen
    for _ in range(3):
        r.draw(s, s.update(DT, FrameInput(activity=True, confirms={"p1": True, "p2": False})), DT)
    assert S.HISCORES in drive(s, r, 1.0)


def test_pause_menu_renders(surface):
    s = Session(random.Random(0), Hiscores(None))
    s.mode = 2
    r = Renderer(surface)
    s.update(DT, FrameInput(activity=True, confirms={"p1": True, "p2": False}))
    s.update(DT, FrameInput(activity=True, pauses={"p1": True, "p2": False}))
    assert s.paused
    r.draw(s, [], DT)
