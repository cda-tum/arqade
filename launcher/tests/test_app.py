from pathlib import Path

import pygame
import pytest

from arqade_launcher import app as appmod, catalog, runner, settings
from arqade_launcher.settings import Settings


def key(k, mod=0):
    return pygame.event.Event(pygame.KEYDOWN, key=k, mod=mod, unicode="")


class FakeRunner:
    def __init__(self, code=0):
        self.code = code
        self.calls = []
        self.configs = []  # (the input config, whether the menu's display was still up)

    def __call__(self, game, s, size, config=None):
        self.calls.append((game.package, s.fullscreen, size))
        self.configs.append((config, pygame.display.get_init()))
        return runner.Result(self.code, ["Traceback", "ValueError: boom"])


@pytest.fixture
def make_app(tmp_path):
    def make(**kwargs):
        run = kwargs.pop("run_game", FakeRunner())
        a = appmod.App(catalog.discover(), Settings(fullscreen=False), tmp_path / "s.json",
                       window_size=(960, 540), run_game=run, **kwargs)
        a.open_display()
        a.push(appmod.MenuScreen(a))
        a.step([], 1 / 60)
        return a, run
    return make


def run_frames(a, n=150):
    for _ in range(n):
        a.step([], 1 / 30)


def test_choose_and_play(make_app):
    a, run = make_app()
    a.step([key(pygame.K_RIGHT), key(pygame.K_RETURN)], 1 / 60)
    assert isinstance(a.screens[-1], appmod.LoadingScreen)
    run_frames(a)
    assert run.calls == [(a.games[1].package, False, (960, 540))]
    assert isinstance(a.screens[-1], appmod.MenuScreen)
    assert a.surface is not None  # the menu's window is back


def test_mapped_pad_keys_work_in_the_menu(make_app):
    a, run = make_app()
    a.step([key(pygame.K_d)], 1 / 60)  # P1 stick right
    a.step([key(pygame.K_n)], 1 / 60)  # P1 A
    run_frames(a)
    assert run.calls[0][0] == a.games[1].package


def test_carousel_wraps_around(make_app):
    a, _ = make_app()
    a.step([key(pygame.K_LEFT)], 1 / 60)
    assert a.screens[-1].selected == a.games[-1]


def test_input_right_after_a_game_is_ignored(make_app):
    a, run = make_app()
    a.step([key(pygame.K_RETURN)], 1 / 60)
    for _ in range(300):  # until the game has run; the grace period is real time
        if run.calls:
            break
        a.step([], 1 / 30)
    a.step([key(pygame.K_RETURN)], 1 / 60)  # e.g. still held from the game
    assert isinstance(a.screens[-1], appmod.MenuScreen)


def test_a_crash_is_reported(make_app):
    a, _ = make_app(run_game=FakeRunner(code=1))
    a.step([key(pygame.K_RETURN)], 1 / 60)
    run_frames(a)
    assert isinstance(a.screens[-1], appmod.ErrorScreen)
    assert a.screens[-1].reason == "ValueError: boom"


def test_escape_on_the_loading_card_cancels(make_app):
    a, run = make_app()
    a.step([key(pygame.K_RETURN)], 1 / 60)
    a.step([key(pygame.K_ESCAPE)], 1 / 60)
    run_frames(a)
    assert run.calls == []


def test_quit_asks_first(make_app):
    a, _ = make_app()
    a.step([key(pygame.K_ESCAPE)], 1 / 60)
    assert a.running and isinstance(a.screens[-1], appmod.QuitScreen)
    a.step([key(pygame.K_RETURN)], 1 / 60)
    assert not a.running


def test_kiosk_mode_has_no_quit_or_settings(make_app):
    a, _ = make_app(kiosk=True)
    a.step([key(pygame.K_ESCAPE), key(pygame.K_TAB), key(pygame.K_F11),
            pygame.event.Event(pygame.QUIT)], 1 / 60)
    assert a.running and len(a.screens) == 1 and not a.settings.fullscreen
    a.step([key(pygame.K_q, pygame.KMOD_LCTRL)], 1 / 60)
    assert not a.running


def test_rebinding_a_key_saves_it(make_app, tmp_path):
    a, _ = make_app()
    a.step([key(pygame.K_TAB)], 1 / 60)
    settings_screen = a.screens[-1]
    assert isinstance(settings_screen, appmod.SettingsScreen)
    settings_screen.index = [item[0] for item in settings_screen.items].index("PLAYER 1 KEYS")
    a.step([key(pygame.K_RETURN)], 1 / 60)
    keys_screen = a.screens[-1]
    assert isinstance(keys_screen, appmod.KeysScreen) and keys_screen.player == "p1"
    keys_screen.index = keys_screen.ROWS.index("a")
    a.step([key(pygame.K_RETURN)], 1 / 60)
    a.step([key(pygame.K_SPACE)], 1 / 60)  # captured, not treated as "confirm"
    assert a.settings.keys["p1"]["a"] == "space"
    assert settings.load(tmp_path / "s.json").keys["p1"]["a"] == "space"
    # ...and the menu now confirms with it too.
    assert a.key_intents[pygame.K_SPACE] == "confirm"


def test_assign_all_walks_through_every_action(make_app):
    a, _ = make_app()
    screen = appmod.KeysScreen(a, "p2")
    a.push(screen)
    a.step([key(pygame.K_RETURN)], 1 / 60)  # row 0: assign all
    letters = [pygame.K_a + i for i in range(len(settings.ACTIONS))]
    a.step([key(k) for k in letters], 1 / 60)
    assert screen.capture is None
    assert [a.settings.keys["p2"][act] for act in settings.ACTIONS] == [
        pygame.key.name(k) for k in letters]
    # Those letters were P1's in part; P1 lost them rather than sharing them.
    assert a.settings.keys["p1"]["left"] is None  # "a"


def test_escape_cannot_be_bound(make_app):
    a, _ = make_app()
    screen = appmod.KeysScreen(a, "p1")
    a.push(screen)
    screen.start_capture("a", False)
    a.step([key(pygame.K_ESCAPE)], 1 / 60)
    assert screen.capture is None and a.settings.keys["p1"]["a"] == "n"


def test_the_input_config_is_worked_out_before_the_menu_lets_go_of_the_display(make_app):
    a, run = make_app()
    a.play(a.games[0])
    config, display_up = run.configs[0]
    assert config == runner.input_config(a.settings)
    assert config["exit_key"] == pygame.K_ESCAPE and config["pads"]
    assert not display_up  # the game gets the display to itself


def test_f11_switches_display_and_remembers_it(make_app, tmp_path):
    a, _ = make_app()
    a.step([key(pygame.K_F11)], 1 / 60)
    assert a.settings.fullscreen
    assert settings.load(tmp_path / "s.json").fullscreen


def test_command_line_display_choice_is_not_saved(tmp_path):
    a = appmod.App([], Settings(fullscreen=False), tmp_path / "s.json", persisted_fullscreen=True)
    a.settings.show_fps = True
    a.save()
    stored = settings.load(tmp_path / "s.json")
    assert stored.fullscreen is True and stored.show_fps is True


@pytest.mark.parametrize("size", [(1920, 1080), (1366, 768), (800, 600)])
def test_every_screen_draws(make_app, size):
    a, _ = make_app()
    a.window_size = size
    a.open_display()
    game = a.games[0]
    for screen in (appmod.LoadingScreen(a, game), appmod.SettingsScreen(a),
                   appmod.KeysScreen(a, "p2"), appmod.QuitScreen(a),
                   appmod.ErrorScreen(a, game, runner.Result(1, []))):
        a.push(screen)
        a.draw()
        a.pop()
    a.draw()


def test_no_games_found(tmp_path):
    a = appmod.App([], Settings(fullscreen=False), None)
    a.open_display()
    a.push(appmod.MenuScreen(a))
    a.step([key(pygame.K_RETURN), key(pygame.K_RIGHT)], 1 / 60)
    assert len(a.screens) == 1


class FakePlayer:
    def __init__(self, path, size, crop=None, loop=True):
        self.path = path
        self.size = size
        self.closed = False
        self.done = False

    def frame(self):
        return pygame.Surface(self.size)

    def close(self):
        self.closed = True


@pytest.fixture
def reel(monkeypatch):
    from arqade_launcher import video

    monkeypatch.setattr(video, "available", lambda path: True)
    monkeypatch.setattr(video, "reels", lambda: [Path("reel_1.mp4"), Path("reel_2.mp4")])
    monkeypatch.setattr(video, "Player", FakePlayer)


def idle(a, seconds):
    for _ in range(int(seconds * 10)):
        a.step([], 0.1)


def test_attract_reel_after_idle_and_any_key_ends_it(make_app, reel):
    a, run = make_app()
    idle(a, appmod.ATTRACT_DELAY - 1)
    assert isinstance(a.screens[-1], appmod.MenuScreen)
    idle(a, 1.5)
    attract = a.screens[-1]
    assert isinstance(attract, appmod.AttractScreen)
    a.step([key(pygame.K_RETURN)], 1 / 60)
    # The key that woke the menu does nothing else: no game starts.
    assert isinstance(a.screens[-1], appmod.MenuScreen) and attract.player.closed
    run_frames(a)
    assert run.calls == []


def test_attract_plays_another_reel_when_one_ends(make_app, reel):
    a, _ = make_app()
    idle(a, appmod.ATTRACT_DELAY + 1)
    attract = a.screens[-1]
    first = attract.player
    first.done = True
    a.step([], 1 / 30)
    assert first.closed and attract.player is not first
    assert attract.player.path != first.path  # never the same reel twice in a row


def test_input_restarts_the_attract_countdown(make_app, reel):
    a, _ = make_app()
    idle(a, appmod.ATTRACT_DELAY - 5)
    a.step([key(pygame.K_RIGHT)], 1 / 60)
    idle(a, appmod.ATTRACT_DELAY - 5)
    assert isinstance(a.screens[-1], appmod.MenuScreen)


def test_attract_mode_can_be_switched_off(make_app, reel):
    a, _ = make_app()
    a.settings.attract = False
    idle(a, appmod.ATTRACT_DELAY + 5)
    assert isinstance(a.screens[-1], appmod.MenuScreen)


def test_no_attract_reel_without_video(make_app):
    a, _ = make_app()
    idle(a, appmod.ATTRACT_DELAY + 5)
    assert isinstance(a.screens[-1], appmod.MenuScreen)


def test_loading_card_spins_the_logo_and_stops_it(make_app, reel):
    a, run = make_app()
    a.step([key(pygame.K_RETURN)], 1 / 60)
    a.step([], 1 / 60)
    loading = a.screens[-1]
    assert isinstance(loading, appmod.LoadingScreen) and loading.spin is not None
    run_frames(a)
    assert run.calls and loading.spin.closed
