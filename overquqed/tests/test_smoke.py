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
        for p in ("p1", "p2"):
            held = set(self.next_held[p])
            self.pressed[p] = held - self.held[p]
            self.held[p] = held
            self.nav[p] = {d for d in ("left", "right", "up", "down") if d in self.pressed[p]}
        # a button (not a stick direction) that went down this frame
        self.any_button = any(self.pressed[p] - {"left", "right", "up", "down"} for p in ("p1", "p2"))
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
        assert type(app.scene).__name__ == "HowToPlayScene"
        frames(app, 30)
        frames(app, 2, p2={"pick"})
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


def test_a_new_high_score_is_posted_to_the_page(app, monkeypatch):
    from overquqed import scenes
    from overquqed.round_scene import RoundScene

    posted = []
    monkeypatch.setattr(scenes.web, "post_score", lambda *a: posted.append(a))
    rs = RoundScene(app, levels.SNACK_BAR, [0])
    rs.world.score = 321
    app.switch(scenes.ResultsScene(app, rs))
    for _ in range(3):
        frames(app, 2, p1={"pick"})
        frames(app, 2)
    assert posted == [("overquqed", "snackbar", 321, "AAA")]
    assert app.hiscores["snackbar"]["scores"][0] == {"name": "AAA", "score": 321}


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


# --- title menu: PLAY / QUIT -------------------------------------------------------


def test_a_on_quit_leaves_the_game(app):
    frames(app, 10)
    frames(app, 2, p2={"down"})
    assert app.scene.index == 1  # QUIT, the last row
    frames(app, 2, p1={"use"})  # B on the title does not quit
    assert app.running
    frames(app, 1, p1={"pick"})
    assert not app.running


def test_start_plays_even_with_quit_selected(app):
    app.scene.index = 1
    frames(app, 2, p2={"start"})
    assert app.running and type(app.scene).__name__ == "JoinScene"
    assert app.scene.joined == [1]


def test_a_on_play_joins_and_the_stick_wraps(app):
    frames(app, 2, p1={"up"})
    assert app.scene.index == 1
    frames(app, 2, p1={"down"})
    assert app.scene.index == 0
    frames(app, 2, p1={"pick"})
    assert type(app.scene).__name__ == "JoinScene"


def test_attract_demo_resets_the_title_to_play(app):
    app.scene.index = 1
    for _ in range(int((config.ATTRACT_DELAY + 1) * 60)):
        app.step(1 / 60, [])
    assert app.scene.demo is not None and app.scene.index == 0
    frames(app, 1, p1={"pick"})  # waking it with A never quits
    assert app.running and type(app.scene).__name__ == "JoinScene"


# --- HOW TO PLAY card ---------------------------------------------------------------


def _to_card(app, level=levels.SNACK_BAR, players=(0, 1)):
    from overquqed.scenes import LevelSelectScene

    app.switch(LevelSelectScene(app, list(players)))
    frames(app, 20)
    app.scene.index = levels.LEVELS.index(level)
    frames(app, 1, p1={"pick"})
    assert type(app.scene).__name__ == "HowToPlayScene"
    return app.scene


def test_card_ignores_presses_in_its_first_moments(app):
    card = _to_card(app)
    frames(app, 1, p1={"start"})  # the confirm's bounce, at ~0.03 s
    assert app.scene is card
    frames(app, 30)
    frames(app, 1, p2={"swap"})  # any button, even one the menus don't use
    assert type(app.scene).__name__ == "RoundScene"


def test_stick_does_not_dismiss_the_card(app):
    card = _to_card(app)
    frames(app, 60)
    for d in ("up", "down", "left", "right"):
        frames(app, 3, p1={d}, p2={d})
    assert app.scene is card


def test_card_comes_before_every_kitchen_including_training_day(app):
    for lv in levels.LEVELS:
        card = _to_card(app, lv)
        assert card.level is lv
        frames(app, 30)
        frames(app, 1, p1={"pick"})
        assert app.scene.level is lv and type(app.scene).__name__ == "RoundScene"


def test_dismissing_press_does_not_act_in_the_round(app):
    _to_card(app)
    frames(app, 30)
    # dismiss with B and keep holding it: no station work until it is let go
    app.inp.next_held = {"p1": {"use"}, "p2": set()}
    app.step(1 / 60, [])
    rs = app.scene
    assert type(rs).__name__ == "RoundScene"
    for _ in range(5):
        app.step(1 / 60, [])
        assert not rs.chef_inputs(app.inp)[0].use
    app.inp.next_held = {"p1": set(), "p2": set()}
    app.step(1 / 60, [])
    app.inp.next_held = {"p1": {"use"}, "p2": set()}
    app.step(1 / 60, [])
    assert rs.chef_inputs(app.inp)[0].use
    assert not rs.paused


def test_start_on_the_card_starts_and_does_not_pause(app):
    _to_card(app)
    frames(app, 30)
    app.inp.next_held = {"p1": {"start"}, "p2": set()}
    for _ in range(10):
        app.step(1 / 60, [])
    assert type(app.scene).__name__ == "RoundScene" and not app.scene.paused


def test_restart_skips_the_card(app):
    _to_card(app)
    frames(app, 30)
    frames(app, 1, p1={"pick"})
    rs = app.scene
    frames(app, 2, p1={"start"})
    assert rs.paused
    frames(app, 2, p1={"down"})
    frames(app, 2, p1={"pick"})  # RESTART
    assert type(app.scene).__name__ == "RoundScene" and app.scene is not rs


def test_quit_combo_and_idle_timeout_work_on_the_card(app):
    _to_card(app)
    for _ in range(int((config.IDLE_TIMEOUT + 1) * 60)):
        app.step(1 / 60, [])
        app.inp.next_held = {"p1": set(), "p2": set()}
    assert type(app.scene).__name__ == "TitleScene"
    _to_card(app)
    app.inp.next_held = {"p1": set(), "p2": {"start", "select"}}
    app.step(1 / 60, [])
    assert not app.running


def test_card_demo_kitchen_serves_both_orders_and_loops():
    from overquqed.howto import DEMO_LOOP, DemoKitchen

    pygame.init()
    demo = DemoKitchen()
    captions = set()
    served = 0
    for _ in range(int(DEMO_LOOP * 60) - 1):
        demo.update(1 / 60)
        captions.add(demo.caption()[0])
        served = demo.world.stats.delivered
    assert served == 2  # the bot cooks both orders well inside one loop
    assert {"A", "B"} <= captions
    demo.update(2 / 60)
    assert demo.t < 0.1 and len(demo.world.orders.orders) == 2  # and it starts over


def test_in_the_browser_quit_goes_back_to_the_title(app, monkeypatch):
    """Start + Select tells the page and returns to the title instead of ending."""
    import asyncio

    sent = []
    browser = {"on": True}
    monkeypatch.setattr(game.runtime, "is_browser", lambda: browser["on"])
    monkeypatch.setattr(game.web, "post_event", lambda kind, game_id: sent.append(kind))
    frames = {"n": 0}
    real_flip = pygame.display.flip

    def flip():
        real_flip()
        frames["n"] += 1
        assert frames["n"] < 100, "the loop didn't end"
        app.inp.next_held["p1"] = {"start", "select"} if 5 <= frames["n"] < 10 else set()
        if frames["n"] == 40:  # a browser has no window to close, so stop being one to end the test
            browser["on"] = False
            pygame.event.post(pygame.event.Event(pygame.QUIT))

    monkeypatch.setattr(pygame.display, "flip", flip)
    asyncio.run(app.run())
    assert sent == [game.web.QUIT] and frames["n"] >= 40
