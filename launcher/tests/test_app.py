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

    def __call__(self, game, s, size):
        self.calls.append((game.package, s.fullscreen, size))
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
    run_frames(a)
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
    settings_screen.index = 3  # PLAYER 1 KEYS
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
