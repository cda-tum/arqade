"""HOW TO PLAY and the title's QUIT row: the card's dismissal rules, its demo
climb (replayed through the real rules), the loops driven headlessly with
scripted input and posted events, and the screen flow title -> tutorial ->
match."""

import os

import pygame
import pytest

from quantum_towers import config, main, tutorial
from quantum_towers.input import PlayerRawInput, set_keyboard_enabled
from quantum_towers.quantum import states_equal, zero_state
from quantum_towers.sound import silent

FRAME = 0.02  # seconds per frame, from the fake clock
QUIT = {"start": True, "select": True}
GRACE_FRAMES = round(tutorial.GRACE / FRAME) + 1


def _raw(**held) -> PlayerRawInput:
    buttons = {name: held.get(name, False) for name in config.ACTION_NAMES}
    return PlayerRawInput(
        button_held=buttons,
        up_held=held.get("up", False),
        start_held=held.get("start", False),
        select_held=held.get("select", False),
        confirm_held=held.get("confirm", False),
        down_held=held.get("down", False),
        back_held=held.get("back", False),
    )


class _FakeClock:
    def tick(self, _fps: int = 0) -> int:
        return round(FRAME * 1000)

    def get_fps(self) -> float:
        return 1 / FRAME


def _button(pad: int = 0, button: int = 1) -> pygame.event.Event:
    return pygame.event.Event(pygame.JOYBUTTONDOWN, joy=pad, instance_id=pad, button=button)


def _axis(pad: int = 0) -> pygame.event.Event:
    return pygame.event.Event(pygame.JOYAXISMOTION, joy=pad, instance_id=pad, axis=1, value=-1.0)


def _key() -> pygame.event.Event:
    return pygame.event.Event(pygame.KEYDOWN, key=pygame.K_g, mod=0, unicode="g", scancode=0)


@pytest.fixture
def screen(monkeypatch):
    """A headless display plus `script(frames)`: per frame, a dict of P1's held
    buttons, optionally with "events": a list posted for the next frame.
    After the script, the Start + Select quit combo."""
    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
    os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
    pygame.init()
    surface = pygame.display.set_mode((config.INTERNAL_WIDTH, config.INTERNAL_HEIGHT))
    set_keyboard_enabled(False)
    monkeypatch.setattr(main.pygame.time, "Clock", _FakeClock)

    def script(frames: list[dict]) -> None:
        it = iter(frames)

        def poll(_keys):
            frame = dict(next(it, QUIT))
            for event in frame.pop("events", []):
                pygame.event.post(event)
            return _raw(**frame), _raw()

        monkeypatch.setattr(main, "_poll_players", poll)

    yield surface, script
    set_keyboard_enabled(True)
    pygame.quit()


# --- Dismissal ----------------------------------------------------------------


def test_a_press_inside_the_grace_period_does_not_dismiss():
    card = tutorial.Dismissal()
    assert not card.update(0.1, True)
    assert not card.update(0.1, True)


def test_a_press_after_the_grace_period_dismisses():
    card = tutorial.Dismissal()
    assert not card.update(tutorial.GRACE, False)
    assert card.update(0.01, True)


def test_no_press_never_dismisses():
    card = tutorial.Dismissal()
    assert not any(card.update(0.5, False) for _ in range(100))


# --- the demo climb -----------------------------------------------------------


def test_the_demo_starts_on_the_ground_at_zero():
    frame = tutorial.demo_frame(0.0)
    assert frame.player.floor == 0
    assert states_equal(frame.player.state, zero_state())
    assert frame.pressed is None and not frame.stick_up


def test_the_demo_climbs_two_perfect_floors_with_a_stun_between():
    end = tutorial.demo_frame(tutorial.DEMO_LOOP - 0.01)
    assert end.player.floor == 2
    assert end.player.charges == 2  # both floors in the fewest presses
    stun_at = [at for at, move in tutorial.DEMO_SCRIPT if move == "UP"][1]
    stunned = tutorial.demo_frame(stun_at + 0.1)
    assert stunned.stun_progress is not None
    assert stunned.player.floor == 1


def test_the_demo_presses_nothing_while_stunned():
    ups = [at for at, move in tutorial.DEMO_SCRIPT if move == "UP"]
    stun_end = ups[1] + config.STUN_DURATION
    assert all(not ups[1] < at < stun_end for at, _move in tutorial.DEMO_SCRIPT)


def test_the_demo_lights_the_pressed_gate_and_the_stick():
    first_at, first = tutorial.DEMO_SCRIPT[0]
    assert tutorial.demo_frame(first_at + 0.05).pressed == first
    assert tutorial.demo_frame(first_at + tutorial.DEMO_PRESS + 0.05).pressed is None
    up_at = next(at for at, move in tutorial.DEMO_SCRIPT if move == "UP")
    assert tutorial.demo_frame(up_at + 0.05).stick_up


def test_the_demo_loops():
    a, b = tutorial.demo_frame(0.5), tutorial.demo_frame(0.5 + tutorial.DEMO_LOOP)
    assert a == b


def test_the_card_draws_in_both_modes(screen):
    surface, _script = screen
    for mode in ("1p", "2p"):
        card = tutorial.Card(mode)
        for t in (0.0, 1.0, 2.2, 3.3, 5.0):
            tutorial.draw_tutorial(surface, card, t, show_prompt=t < 1)


# --- run_tutorial -------------------------------------------------------------


def test_a_button_after_the_grace_period_starts_the_match(screen):
    surface, script = screen
    script([{}] * GRACE_FRAMES + [{"events": [_button()]}, {}])
    assert main.run_tutorial(surface, None, "2p") == "play"


def test_any_button_on_either_pad_counts(screen):
    surface, script = screen
    script([{}] * GRACE_FRAMES + [{"events": [_button(pad=1, button=5)]}, {}])
    assert main.run_tutorial(surface, None, "2p") == "play"


def test_presses_inside_the_grace_period_are_ignored(screen):
    surface, script = screen
    # Mashed while the card opens, then nothing: it runs into the quit combo.
    script([{"events": [_button()]}, {"events": [_button()]}] + [{}] * GRACE_FRAMES)
    assert main.run_tutorial(surface, None, "2p") == "quit"


def test_a_press_queued_before_the_card_opened_is_ignored(screen):
    surface, script = screen
    pygame.event.post(_button())  # the title's A, still in the queue
    script([{}] * GRACE_FRAMES)
    assert main.run_tutorial(surface, None, "2p") == "quit"


def test_the_stick_does_not_dismiss(screen):
    surface, script = screen
    script([{}] * GRACE_FRAMES + [{"up": True, "events": [_axis()]}, {"down": True}, {}])
    assert main.run_tutorial(surface, None, "1p") == "quit"


def test_keys_dismiss_only_with_the_keyboard_on(screen):
    surface, script = screen
    script([{}] * GRACE_FRAMES + [{"events": [_key()]}, {}])
    assert main.run_tutorial(surface, None, "2p") == "quit"  # --no-keyboard
    set_keyboard_enabled(True)
    script([{}] * GRACE_FRAMES + [{"events": [_key()]}, {}])
    assert main.run_tutorial(surface, None, "2p") == "play"


def test_the_idle_timeout_runs_on_the_card(screen, monkeypatch):
    monkeypatch.setattr(config, "IDLE_TIMEOUT_SECONDS", 0.5)
    surface, script = screen
    script([{}] * 100)
    assert main.run_tutorial(surface, None, "2p") == "idle"


def test_the_dismissing_button_does_not_fire_a_gate(screen):
    """Any button closes the card, gates included: one held into the match
    acts only once it has been let go and pressed again."""
    surface, script = screen
    script([{"X": True}] * 5 + [{}] + [{"X": True}, {}])
    _result, players = main.run_game(surface, None, silent(), show_fps=False)
    assert not states_equal(players["p1"].state, zero_state())  # one X only
    script([{"X": True}] * 5)
    _result, players = main.run_game(surface, None, silent(), show_fps=False)
    assert states_equal(players["p1"].state, zero_state())


# --- the title's QUIT -----------------------------------------------------------


def test_a_on_quit_quits(screen):
    surface, script = screen
    script([{}, {"down": True}, {}, {"confirm": True}])
    assert main.run_title_screen(surface, None, "2p") == "quit"


def test_start_on_quit_starts_the_last_player_count(screen):
    surface, script = screen
    script([{}, {"down": True}, {}, {"start": True}])
    assert main.run_title_screen(surface, None, "2p") == "2p"
    script([{}, {"down": True}, {}, {"down": True}, {}, {"start": True}])
    assert main.run_title_screen(surface, None, "1p") == "2p"


def test_b_on_the_title_does_not_quit(screen):
    surface, script = screen
    script([{}, {"down": True}, {}, {"back": True}, {}, {"back": True}, {}, {"up": True}, {}, {"confirm": True}])
    assert main.run_title_screen(surface, None, "2p") == "2p"


def test_the_title_selection_stops_at_the_ends(screen):
    surface, script = screen
    script([{}, {"up": True}, {}, {"up": True}, {}, {"confirm": True}])
    assert main.run_title_screen(surface, None, "2p") == "1p"
    script([{}] + [{"down": True}, {}] * 4 + [{"up": True}, {}, {"confirm": True}])
    assert main.run_title_screen(surface, None, "1p") == "2p"


# --- the flow -----------------------------------------------------------------


@pytest.fixture
def flow(monkeypatch):
    """run_flow with every screen stubbed: each returns the next of its
    scripted results and logs its call."""
    calls = []

    def run(titles, tutorials, games=(), solos=()):
        results = {"title": iter(titles), "tutorial": iter(tutorials),
                   "game": iter(games), "solo": iter(solos)}

        def title(_s, _w, mode, _sounds):
            calls.append(("title", mode))
            return next(results["title"])

        def tut(_s, _w, mode, _sounds):
            calls.append(("tutorial", mode))
            return next(results["tutorial"])

        def game(*_a):
            calls.append(("game",))
            return next(results["game"]), {}

        def solo_flow(*_a):
            calls.append(("solo",))
            return next(results["solo"])

        monkeypatch.setattr(main, "run_title_screen", title)
        monkeypatch.setattr(main, "run_tutorial", tut)
        monkeypatch.setattr(main, "run_game", game)
        monkeypatch.setattr(main, "run_solo_flow", solo_flow)
        main.run_flow(None, None, silent(), False, None)

    return run, calls


def test_every_match_from_the_title_gets_the_tutorial_first(flow):
    run, calls = flow
    run(["2p", "1p", "2p", "quit"], ["play"] * 3, games=["title", "idle"], solos=["done"])
    assert calls == [
        ("title", "2p"), ("tutorial", "2p"), ("game",),
        ("title", "2p"), ("tutorial", "1p"), ("solo",),
        ("title", "1p"), ("tutorial", "2p"), ("game",),
        ("title", "2p"),
    ]


def test_quit_on_the_title_ends_the_game(flow):
    run, calls = flow
    run(["quit"], [])
    assert calls == [("title", "2p")]


def test_an_idle_tutorial_goes_back_to_the_title(flow):
    run, calls = flow
    run(["2p", "quit"], ["idle"])
    assert calls == [("title", "2p"), ("tutorial", "2p"), ("title", "2p")]


def test_quitting_on_the_tutorial_ends_the_game(flow):
    run, calls = flow
    run(["1p"], ["quit"])
    assert calls == [("title", "2p"), ("tutorial", "1p")]
