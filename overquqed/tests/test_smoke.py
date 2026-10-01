"""Headless smoke test: drive the real scenes with scripted input and make
sure every screen updates and draws without errors."""

import pygame
import pytest

from overquqed import config, game, levels
from overquqed.input import Input


class ScriptedInput(Input):
    """Input whose held actions come from a script instead of devices."""

    def __init__(self):
        super().__init__()
        self.next_held = {"p1": set(), "p2": set()}

    def update(self, dt):
        self.activity = any(self.next_held.values())
        self.keyboard_quit = False
        for p in ("p1", "p2"):
            held = set(self.next_held[p])
            self.pressed[p] = held - self.held[p]
            self.held[p] = held
            self.nav[p] = {d for d in ("left", "right", "up", "down") if d in self.pressed[p]}
        self.select_held_time = self.select_held_time + dt if any("select" in h for h in self.held.values()) else 0.0


@pytest.fixture
def app(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "HISCORE_FILE", tmp_path / "scores.json")
    pygame.init()
    surface = pygame.display.set_mode((config.INTERNAL_WIDTH, config.INTERNAL_HEIGHT))
    a = game.App(surface, None, True)
    a.inp = ScriptedInput()
    yield a  # no pygame.quit(): cached fonts must outlive a single test


def frames(app, n, p1=(), p2=()):
    for i in range(n):
        app.inp.next_held = {"p1": set(p1) if i == 0 else set(), "p2": set(p2) if i == 0 else set()}
        app.step(1 / 60, [])
        app.draw()


def test_full_menu_flow_into_every_level_and_out(app):
    frames(app, 30)
    assert type(app.scene).__name__ == "TitleScene"
    frames(app, 2, p1={"start"})
    assert type(app.scene).__name__ == "JoinScene"
    frames(app, 2, p2={"pick"})
    frames(app, 30)
    frames(app, 2, p1={"pick"})
    assert type(app.scene).__name__ == "LevelSelectScene"
    for i, lv in enumerate(levels.LEVELS):
        frames(app, 20)
        app.scene.index = i
        frames(app, 2, p1={"pick"})
        assert type(app.scene).__name__ == "RoundScene" and app.scene.level is lv
        frames(app, 240, p1={"down"}, p2={"up"})
        if lv.tutorial:
            # Start skips the tutorial straight to the results
            frames(app, 2, p1={"start"})
            assert type(app.scene).__name__ == "ResultsScene"
            frames(app, 90)
            frames(app, 2, p1={"pick"})
            assert type(app.scene).__name__ == "LevelSelectScene"
            continue
        # pause -> quit to menu
        frames(app, 2, p1={"start"})
        assert app.scene.paused
        frames(app, 2, p1={"down"})
        frames(app, 2, p1={"down"})
        frames(app, 2, p1={"pick"})
        assert type(app.scene).__name__ == "LevelSelectScene"


def test_round_runs_to_results_and_back(app, monkeypatch):
    from overquqed.round_scene import RoundScene

    rs = RoundScene(app, levels.SNACK_BAR, [0])
    app.switch(rs)
    rs.world.t = rs.level.duration - 0.5
    frames(app, 200)
    assert type(app.scene).__name__ == "ResultsScene"
    frames(app, 90)
    frames(app, 2, p1={"pick"})
    assert type(app.scene).__name__ == "LevelSelectScene"


def test_quit_combo_stops_the_app(app):
    app.inp.next_held = {"p1": {"start", "select"}, "p2": set()}
    app.step(1 / 60, [])
    assert not app.running


def test_idle_timeout_returns_to_title(app):
    from overquqed.scenes import LevelSelectScene

    app.switch(LevelSelectScene(app, [0]))
    for _ in range(int((config.IDLE_TIMEOUT + 1) * 60)):
        app.step(1 / 60, [])
    assert type(app.scene).__name__ == "TitleScene"


def test_attract_mode_starts_when_the_title_is_left_alone(app):
    for _ in range(int((config.ATTRACT_DELAY + 2) * 60)):
        app.step(1 / 60, [])
    app.draw()
    assert app.scene.demo is not None


def test_tutorial_can_be_completed_by_following_chef_ket(app):
    from overquqed.bot import Bot
    from overquqed.round_scene import RoundScene

    rs = RoundScene(app, levels.TUTORIAL, [0, 1])
    app.switch(rs)
    bot = Bot(rs.world)
    rs.chef_inputs = lambda inp: bot.update(1 / 60)
    beats = []
    for i in range(60 * 60):
        if app.scene is not rs:
            break
        beats.append(rs.tutorial.i)
        # read each line, then press A (the bot does the cooking)
        frames(app, 1, p2={"pick"} if i % 90 == 89 else set())
    assert type(app.scene).__name__ == "ResultsScene"
    assert rs.world.stats.delivered == 3
    assert max(beats) == len(__import__("overquqed.tutorial", fromlist=["SCRIPT"]).SCRIPT) - 1
    assert i < 60 * 60  # well under a minute of play


def test_start_skips_the_tutorial(app):
    from overquqed.round_scene import RoundScene

    app.switch(RoundScene(app, levels.TUTORIAL, [0]))
    frames(app, 10)
    frames(app, 2, p1={"start"})
    assert type(app.scene).__name__ == "ResultsScene"
