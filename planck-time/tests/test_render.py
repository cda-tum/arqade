"""Smoke tests: every screen and every microgame renders without errors,
in single player and versus, paused or not."""

import random

import pygame
import pytest
from arqade_common.input import KEYBOARD, PAD, LastDevice

from planck_time import config
from planck_time import palette as P
from planck_time import session as S
from planck_time.hiscores import Hiscores
from planck_time.microgames import PlayerInput
from planck_time.pixel import control_hint, outlined, set_buttons
from planck_time.render import Renderer
from planck_time.session import FrameInput, Session

DT = 1 / 60


@pytest.fixture
def surface():
    pygame.init()
    return pygame.Surface((config.INTERNAL_WIDTH, config.INTERNAL_HEIGHT))


def begin(s, r):
    """Start a run from the title and get past the HOW TO PLAY card, drawing it."""
    r.draw(s, s.update(DT, FrameInput(activity=True, confirms={"p1": True, "p2": False})), DT)
    assert s.state == S.TUTORIAL
    for _ in range(round(1.0 / DT)):
        r.draw(s, s.update(DT, FrameInput(activity=True)), DT)
    r.draw(s, s.update(DT, FrameInput(activity=True, presses={"p1": True, "p2": False})), DT)
    assert s.state == S.INTRO


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
    begin(s, r)
    seen = drive(s, r, 60, play=lambda g: g.bot())  # every microgame, well played
    assert {S.INTRO, S.PLAY, S.RESULT, S.SPEED_UP} <= seen
    seen = drive(s, r, 60, play=lambda g: PlayerInput())  # then run out of lives
    assert (S.GAME_OVER if mode == 1 else S.MATCH_RESULT) in seen


def devices(p1, p2):
    """Players on these devices, as if each had pressed something on it."""
    d = LastDevice(p1)
    d._devices["p2"] = p2
    return d


@pytest.mark.parametrize("on", ((KEYBOARD, KEYBOARD), (KEYBOARD, PAD), (PAD, KEYBOARD)))
@pytest.mark.parametrize("mode", (1, 2))
def test_a_whole_run_renders_with_keyboard_players(surface, mode, on):
    s = Session(random.Random(mode), Hiscores(None))
    s.mode = mode
    r = Renderer(surface, devices(*on))
    begin(s, r)
    drive(s, r, 30, play=lambda g: g.bot())  # keycaps in the intros and in every microgame's hint
    seen = drive(s, r, 60, play=lambda g: PlayerInput())
    assert (S.GAME_OVER if mode == 1 else S.MATCH_RESULT) in seen


def test_a_hint_names_a_keyboard_players_key_as_a_keycap(surface):
    def pixels(img):
        return pygame.image.tobytes(img, "RGBA")
    try:
        set_buttons({"a": "A", "stick": "STICK", "keys": ""})
        pad = control_hint("{a} WHEN THEY MATCH", 8, P.WHITE)
        assert pixels(pad) == pixels(outlined("A WHEN THEY MATCH", 8, P.WHITE))  # pads: as it always was
        set_buttons({"a": "B", "stick": "WASD", "keys": "yes"})
        keys = control_hint("{a} WHEN THEY MATCH", 8, P.WHITE)
        text = outlined("B WHEN THEY MATCH", 8, P.WHITE)
        assert keys.get_height() > text.get_height() and keys.get_width() > text.get_width()  # the cap round B
    finally:
        set_buttons({"a": "A", "stick": "STICK", "keys": ""})


def test_title_attract_name_entry_and_hiscores_render(surface):
    s = Session(random.Random(0), Hiscores(None))
    r = Renderer(surface)
    assert S.TITLE in drive(s, r, config.ATTRACT_DELAY + 6, inp=lambda: FrameInput(activity=False))
    assert s.attract
    s.mode = 1
    begin(s, r)
    seen = drive(s, r, 50, play=lambda g: g.bot() if s.score == 0 else PlayerInput())  # 0 never qualifies
    assert S.NAME_ENTRY in seen
    for _ in range(3):
        r.draw(s, s.update(DT, FrameInput(activity=True, confirms={"p1": True, "p2": False})), DT)
    assert S.HISCORES in drive(s, r, 1.0)


@pytest.mark.parametrize("on", ((PAD, PAD), (KEYBOARD, KEYBOARD), (KEYBOARD, PAD)))
def test_pause_menu_renders(surface, on):
    s = Session(random.Random(0), Hiscores(None))
    s.mode = 2
    r = Renderer(surface, devices(*on))
    begin(s, r)
    drive(s, r, config.PAUSE_GRACE + 0.05)
    s.update(DT, FrameInput(activity=True, pauses={"p1": True, "p2": False}))
    assert s.paused
    r.draw(s, [], DT)


@pytest.mark.parametrize("mode", (1, 2))
def test_the_boss_card_intro_and_fight_render(surface, mode):
    s = Session(random.Random(4), Hiscores(None))
    s.mode = mode
    r = Renderer(surface)
    begin(s, r)
    s.toward_boss = config.BOSS_EVERY
    seen = set()
    for _ in range(round(40 / DT)):
        fi = FrameInput(activity=True)
        if s.state == S.PLAY:
            fi.players = {p: g.bot() for p, g in s.games.items()} | {
                p: PlayerInput() for p in S.PLAYERS if p not in s.games}
        r.draw(s, s.update(DT, fi), DT)
        if s.state == S.BOSS_CARD:
            assert s.next_boss is not None and s.next_boss.BOSS_NAME
        seen.add((s.state, s.boss))
        if s.boss and s.state == S.RESULT:
            break
    assert {(S.BOSS_CARD, False), (S.INTRO, True), (S.PLAY, True), (S.RESULT, True)} <= seen
