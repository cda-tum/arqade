"""The single-player time trial, driven headlessly with scripted input: the
title's player-count choice, the solo run (solved with the BFS's own action
sequence), the initials entry and the fastest-clears table."""

import os
import random

import pygame
import pytest

from quantum_towers import config, fonts, main, screens, solo
from quantum_towers.input import PlayerRawInput, set_keyboard_enabled
from quantum_towers.quantum import ACTIONS, states_equal, zero_state
from quantum_towers.sound import Sounds
from quantum_towers.times import Entry, Times

FRAME = 0.02  # seconds per frame, from the fake clock
QUIT = {"start": True, "select": True}


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
        left_held=held.get("left", False),
        right_held=held.get("right", False),
    )


class _FakeClock:
    """Every frame lasts exactly FRAME seconds, however fast the test runs."""

    def tick(self, _fps: int = 0) -> int:
        return round(FRAME * 1000)

    def get_fps(self) -> float:
        return 1 / FRAME


class _NullSound:
    def play(self) -> None:
        pass


SOUNDS = Sounds(_NullSound(), _NullSound(), _NullSound())


@pytest.fixture
def screen(monkeypatch):
    """A headless display plus `script(frames, pad="p1")`, which feeds one dict
    of held buttons per frame to that pad (the other pad holds nothing), and
    then the Start + Select quit combo for as long as it is asked."""
    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
    os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
    pygame.init()
    surface = pygame.display.set_mode((config.INTERNAL_WIDTH, config.INTERNAL_HEIGHT))
    set_keyboard_enabled(False)
    monkeypatch.setattr(main.pygame.time, "Clock", _FakeClock)

    def script(frames: list[dict], pad: str = "p1") -> None:
        it = iter(frames)

        def poll(_keys):
            raw = _raw(**next(it, QUIT))
            return (raw, _raw()) if pad == "p1" else (_raw(), raw)

        monkeypatch.setattr(main, "_poll_players", poll)

    yield surface, script
    set_keyboard_enabled(True)
    pygame.quit()


# --- the title's choice ------------------------------------------------------


def test_title_starts_the_highlighted_choice(screen):
    surface, script = screen
    script([{}, {"confirm": True}])
    assert main.run_title_screen(surface, None, "2p") == "2p"
    script([{}, {"start": True}])
    assert main.run_title_screen(surface, None, "1p") == "1p"


def test_title_stick_moves_between_one_and_two_players(screen):
    surface, script = screen
    script([{}, {"up": True}, {}, {"start": True}])
    assert main.run_title_screen(surface, None, "2p") == "1p"
    script([{}, {"down": True}, {}, {"confirm": True}])
    assert main.run_title_screen(surface, None, "1p") == "2p"
    # A held stick only moves once.
    script([{}, {"down": True}, {"down": True}, {"down": True}, {}, {"confirm": True}])
    assert main.run_title_screen(surface, None, "1p") == "2p"


def test_title_waits_for_a_held_button_to_be_let_go(screen):
    surface, script = screen
    # A still held from QUIT TO TITLE, and a stick still pushed: neither acts
    # until let go.
    script([{"confirm": True, "up": True}] * 5 + [{}, {"start": True}])
    assert main.run_title_screen(surface, None, "2p") == "2p"


def test_title_quit_combo(screen):
    surface, script = screen
    script([])
    assert main.run_title_screen(surface, None, "2p") == "quit"


# --- the solo run ------------------------------------------------------------

TOWER = solo.equal_difficulty_tower(
    random.Random(7), config.TOWER_HEIGHT, config.SOLO_TOTAL_PRESSES
)
COUNTDOWN = [{}] * (round(config.SOLO_COUNTDOWN / FRAME) + 2)  # wait out 3, 2, 1
FINISH = [{}] * (round(config.SOLO_FINISH_DURATION / FRAME) + 10)  # wait out the banner


def _shortest(start, target) -> list[str]:
    """The BFS's own action sequence from start to target."""
    paths = [(start, [])]
    seen = [start]
    while paths:
        state, path = paths.pop(0)
        for name, action in ACTIONS.items():
            new = action(state)
            if states_equal(new, target):
                return path + [name]
            if not any(states_equal(new, s) for s in seen):
                seen.append(new)
                paths.append((new, path + [name]))
    raise AssertionError("unreachable")


def _floor_scripts() -> list[list[dict]]:
    """Per floor: each gate pressed and released, then a push up."""
    floors = []
    state = zero_state()
    for target in TOWER[: config.TOWER_HEIGHT]:
        frames = []
        for name in _shortest(state, target):
            frames += [{name: True}, {}]
            state = ACTIONS[name](state)
        floors.append(frames + [{"up": True}, {}])
    return floors


def _solve(floors: list[list[dict]]) -> list[dict]:
    return [frame for floor in floors for frame in floor]


@pytest.fixture
def run_solo(screen, monkeypatch):
    surface, script = screen
    monkeypatch.setattr(main.solo, "equal_difficulty_tower", lambda *_args, **_kw: TOWER)

    def run(frames: list[dict], pad: str = "p1", times: Times | None = None):
        script(frames, pad)
        return main.run_solo(surface, None, SOUNDS, False, times or Times(None))

    return run


def test_a_solved_tower_finishes_with_the_time(run_solo):
    solve = _solve(_floor_scripts())
    result, seconds = run_solo(COUNTDOWN + solve + FINISH)
    assert result == "done"
    # The clock starts at GO and stops on the top floor: about one frame per
    # scripted solve frame, give or take the frames either side.
    assert seconds == pytest.approx(len(solve) * FRAME, abs=3 * FRAME)


def test_either_pad_can_play(run_solo):
    result, _seconds = run_solo(COUNTDOWN + _solve(_floor_scripts()) + FINISH, pad="p2")
    assert result == "done"


def test_input_during_the_countdown_is_ignored(run_solo):
    # The solve pressed during the countdown does nothing, so the tower is
    # never climbed and the script runs into the quit combo.
    result, seconds = run_solo(_solve(_floor_scripts()))
    assert result == "quit"
    assert seconds == 0.0


def test_the_timer_freezes_while_paused(run_solo):
    floors = _floor_scripts()
    _result, plain = run_solo(COUNTDOWN + _solve(floors) + FINISH)
    pause = [{"start": True}] + [{}] * 100 + [{"start": True}]
    paused_floors = floors[:5] + [pause] + floors[5:]
    result, with_pause = run_solo(COUNTDOWN + _solve(paused_floors) + FINISH)
    assert result == "done"
    assert with_pause == pytest.approx(plain)


def test_a_wrong_confirm_stuns(run_solo):
    solve = _solve(_floor_scripts())
    wrong = [{"up": True}, {}]  # |0> is never the first target
    # Straight after the stun, the first gates are swallowed and the climb
    # never finishes.
    result, _seconds = run_solo(COUNTDOWN + wrong + solve)
    assert result == "quit"
    # Waiting the stun out works, at the cost of the time spent waiting.
    wait = [{}] * round(config.STUN_DURATION / FRAME)
    _result, plain = run_solo(COUNTDOWN + solve + FINISH)
    result, stunned = run_solo(COUNTDOWN + wrong + wait + solve + FINISH)
    assert result == "done"
    assert stunned == pytest.approx(plain + len(wrong + wait) * FRAME)


def test_quit_to_title_from_the_pause_menu(run_solo):
    result, _seconds = run_solo(COUNTDOWN + [{"start": True}, {}, {"down": True}, {}, {"confirm": True}])
    assert result == "title"


def test_the_idle_timeout_runs_during_a_solo_run(run_solo, monkeypatch):
    monkeypatch.setattr(config, "IDLE_TIMEOUT_SECONDS", 1.0)
    result, _seconds = run_solo(COUNTDOWN + [{}] * 200)
    assert result == "idle"


# --- initials ----------------------------------------------------------------


def test_name_entry_starts_at_aaa():
    entry = screens.NameEntry()
    assert entry.name == "AAA" and entry.pos == 0 and not entry.done


def test_name_entry_stick_up_and_down_change_the_letter_and_wrap():
    entry = screens.NameEntry()
    entry.update(0, -1, False, False)  # up: next letter
    assert entry.name == "BAA"
    entry.update(0, 1, False, False)
    entry.update(0, 1, False, False)  # down from A wraps to Z
    assert entry.name == "ZAA"


def test_name_entry_left_and_right_move_within_the_three_letters():
    entry = screens.NameEntry()
    entry.update(-1, 0, False, False)
    assert entry.pos == 0
    for _ in range(4):
        entry.update(1, 0, False, False)
    assert entry.pos == 2
    assert not entry.done


def test_name_entry_a_goes_on_and_finishes_on_the_last_letter_b_steps_back():
    entry = screens.NameEntry()
    entry.update(0, 0, True, False)
    entry.update(0, 0, True, False)
    assert entry.pos == 2 and not entry.done
    entry.update(0, 0, False, True)
    assert entry.pos == 1
    entry.update(0, 0, False, True)
    entry.update(0, 0, False, True)
    assert entry.pos == 0
    entry.update(0, 0, True, False)
    entry.update(0, 0, True, False)
    entry.update(0, 0, True, False)
    assert entry.done


def test_name_entry_reports_whether_anything_changed():
    entry = screens.NameEntry()
    assert not entry.update(0, 0, False, False)
    assert entry.update(0, -1, False, False)


def test_auto_repeat_fires_once_then_repeats_after_a_delay():
    repeat = screens.AutoRepeat(delay=0.25, interval=0.125)
    fired = [repeat.update(0.0625, 1) for _ in range(12)]  # 0.75 s held
    # At once, then after the delay, then every interval.
    assert [i for i, f in enumerate(fired) if f] == [0, 4, 6, 8, 10]
    assert repeat.update(0.0625, 0) == 0
    assert repeat.update(0.0625, -1) == -1  # a fresh push fires at once


def test_run_initials_saves_the_name_and_returns_the_rank(screen):
    surface, script = screen
    times = Times(None)
    times.add("ZZZ", 10.0)
    up, a = {"up": True}, {"confirm": True}
    script([{}, up, {}, up, {}, a, {}, {"right": True}, {}, up, {}, a, {}])
    result, rank = main.run_initials(surface, None, times, 20.0)
    assert result == "done"
    assert rank == 1
    assert [(e.name, e.seconds) for e in times.entries] == [("ZZZ", 10.0), ("CAB", 20.0)]


def test_run_initials_ignores_an_a_still_held_from_before(screen):
    surface, script = screen
    times = Times(None)
    script([{"confirm": True}] * 10 + [{}, {"confirm": True}, {}, {"confirm": True}, {}, {"confirm": True}])
    result, rank = main.run_initials(surface, None, times, 20.0)
    assert (result, rank) == ("done", 0)
    assert times.entries[0].name == "AAA"


def test_an_abandoned_initials_entry_is_saved_as_typed(screen, monkeypatch):
    monkeypatch.setattr(config, "IDLE_TIMEOUT_SECONDS", 1.0)
    surface, script = screen
    times = Times(None)
    script([{}, {"up": True}] + [{}] * 100)
    result, rank = main.run_initials(surface, None, times, 20.0)
    assert (result, rank) == ("idle", 0)
    assert times.entries[0].name == "BAA"


def test_run_initials_quit_combo(screen):
    surface, script = screen
    times = Times(None)
    script([])
    result, _rank = main.run_initials(surface, None, times, 20.0)
    assert result == "quit"


# --- the table ---------------------------------------------------------------


def _table_fonts():
    return fonts.load_font(16), fonts.load_font(10), fonts.load_font(8)


def test_times_table_draws(screen):
    surface, _script = screen
    entries = [Entry(f"P{i:02d}", 30.0 + i * 1.37) for i in range(config.TIMES_SLOTS)]
    frames = []
    for t in (0.0, 0.3):  # both halves of the new entry's blink
        screens.draw_times_table(surface, *_table_fonts(), entries, 3, t)
        frames.append(pygame.image.tobytes(surface, "RGB"))
    assert frames[0] != frames[1]  # the new entry blinks
    still = []
    for t in (0.0, 0.3):  # with no new entry, nothing blinks
        screens.draw_times_table(surface, *_table_fonts(), entries, None, t)
        still.append(pygame.image.tobytes(surface, "RGB"))
    assert still[0] == still[1]
    screens.draw_times_table(surface, *_table_fonts(), [], None, 0.0)


def test_times_table_returns_on_a_press_after_a_second(screen):
    surface, script = screen
    times = Times(None)
    times.add("AAA", 30.0)
    lock = round(config.TIMES_TABLE_LOCK / FRAME)
    # A press inside the first second does nothing.
    script([{}, {"confirm": True}] + [{}] * lock + [{"back": True}])
    assert main.run_times_table(surface, None, times, 0) == "done"
    script([{}] * 3 + [{"confirm": True}])
    assert main.run_times_table(surface, None, times, 0) == "quit"  # ran into the quit combo


def test_times_table_returns_by_itself(screen, monkeypatch):
    surface, script = screen
    script([{}] * (round(config.TIMES_TABLE_DURATION / FRAME) + 5))
    assert main.run_times_table(surface, None, Times(None), None) == "done"


# --- the flow after a run ----------------------------------------------------


@pytest.fixture
def flow(monkeypatch):
    calls = []

    def run(solo_result, times):
        monkeypatch.setattr(main, "run_solo", lambda *_a: solo_result)

        def initials(_surface, _window, _times, seconds):
            calls.append(("initials", seconds))
            return "done", 0

        def table(_surface, _window, _times, new_rank):
            calls.append(("table", new_rank))
            return "done"

        monkeypatch.setattr(main, "run_initials", initials)
        monkeypatch.setattr(main, "run_times_table", table)
        return main.run_solo_flow(None, None, SOUNDS, False, times)

    return run, calls


def test_a_qualifying_time_goes_to_initials_then_the_table(flow):
    run, calls = flow
    assert run(("done", 42.0), Times(None)) == "done"
    assert calls == [("initials", 42.0), ("table", 0)]


def test_a_slow_time_goes_straight_to_the_table(flow):
    run, calls = flow
    times = Times(None)
    for i in range(config.TIMES_SLOTS):
        times.add("AAA", 10.0 + i)
    assert run(("done", 99.0), times) == "done"
    assert calls == [("table", None)]


@pytest.mark.parametrize("result", ["quit", "idle", "title"])
def test_a_run_that_did_not_finish_skips_both(flow, result):
    run, calls = flow
    assert run((result, 0.0), Times(None)) == result
    assert calls == []


def test_initials_hint_says_done_on_the_last_letter():
    entry = screens.NameEntry()
    assert "A: NEXT" in screens.initials_hint(entry)
    entry.update(0, 0, True, False)
    entry.update(0, 0, True, False)
    assert "A: DONE" in screens.initials_hint(entry)
