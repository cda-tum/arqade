"""The match flow: title (and QUIT), the HOW TO PLAY card, attract, countdown, race, pause,
result, idle."""

import random

import pytest

from gate_prix import config
from gate_prix.race import Shot
from gate_prix.match import (AIMED, COUNTDOWN, HEARD, HOWTO, PAUSED, RACE, RESULT, TITLE, Cue,
                             FrameInput,
                             Match, PlayerInput)

DT = 1 / 60


def frame(p1=None, p2=None) -> FrameInput:
    """A frame's input; any field given counts as activity."""
    players = {"p1": PlayerInput(**(p1 or {})), "p2": PlayerInput(**(p2 or {}))}
    return FrameInput(players, activity=bool(p1 or p2))


IDLE = FrameInput()
A = frame(p1={"a": True, "held": True})
B = frame(p1={"b": True, "held": True})
START = frame(p1={"start": True, "held": True})
DOWN = frame(p1={"nav": (0, 1)})
HELD = frame(p1={"held": True})
X = frame(p2={"button": True})  # a button that is none of A, B, Start, Select
UP = frame(p1={"nav": (0, -1)})
RIGHT = frame(p1={"nav": (1, 0), "stick": (1, 0)})
LEFT = frame(p1={"nav": (-1, 0), "stick": (-1, 0)})


def run(m: Match, seconds: float, inp: FrameInput = IDLE) -> list:
    events = []
    for _ in range(round(seconds / DT)):
        events += m.update(DT, inp)
    return events


def cues(events, kind=None):
    return [e for e in events if isinstance(e, Cue) and (kind is None or e.kind == kind)]


def fresh(seed=1) -> Match:
    """A match just launched, with nothing held: its first frame lets the title go."""
    m = Match(random.Random(seed))
    m.update(DT, IDLE)
    return m


def through_card(m: Match, inp: FrameInput = X) -> list:
    """Past the HOW TO PLAY card: its guard, then a press."""
    assert m.state == HOWTO
    events = run(m, config.HOWTO_GUARD + DT)
    events += m.update(DT, inp)
    assert m.state == COUNTDOWN
    return events


def tap(m: Match, inp: FrameInput) -> list:
    """One push of the stick (or a press), then let go."""
    events = m.update(DT, inp)
    m.update(DT, IDLE)
    return events


def begun(mode=1, seed=1) -> Match:
    """A match whose countdown has just begun (past the title and the card)."""
    m = fresh(seed)
    if mode == 2:
        tap(m, RIGHT)  # PLAYERS 2
    m.update(DT, START)
    through_card(m)
    return m


def started(mode=1, seed=1) -> Match:
    """A match whose race has just begun (after the countdown)."""
    m = begun(mode, seed)
    run(m, config.COUNTDOWN + DT)
    assert m.state == RACE
    return m


def finish(m: Match, car_id: str) -> None:
    """Put a car just short of the line on its last lap."""
    race = m.race
    r = race.racer(car_id)
    r.next_row = len(race.rows)
    r.next_box = len(race.box_lines)
    r.laps = config.LAPS - 1
    r.car.z = config.LAPS * race.lap_length - 20.0
    r.car.speed = config.TOP_SPEED


# --- The title -------------------------------------------------------------------------------


def settings(m: Match) -> tuple:
    return m.mode, m.bot_count, m.level


def test_the_title_starts_at_one_player_five_easy_bots_and_steps_through_four_rows():
    m = fresh(1)
    assert m.state == TITLE and settings(m) == (1, 5, "EASY") and m.title_index == 0
    assert config.TITLE_ITEMS == ("PLAYERS", "BOTS", "LEVEL", "QUIT")
    events = m.update(DT, DOWN)
    assert m.title_index == 1 and cues(events, "blip")
    events = tap(m, frame(p2={"nav": (0, 1), "stick": (0, 1)}))  # down again: LEVEL
    assert m.title_index == 2 and cues(events, "blip")
    tap(m, DOWN)
    assert m.title_index == 3  # QUIT, the last row
    events = m.update(DT, DOWN)  # clamped: no wrap round to the top
    assert m.title_index == 3 and not cues(events, "blip")
    events = m.update(DT, frame(p2={"nav": (0, -1)}))  # up, on either pad
    assert m.title_index == 2 and cues(events, "blip")
    for _ in range(3):
        m.update(DT, UP)  # clamped at the top too
    assert m.title_index == 0
    assert settings(m) == (1, 5, "EASY")  # moving between the rows changes no value


def test_left_and_right_change_the_highlighted_rows_value_clamped():
    m = fresh(1)
    # PLAYERS: 1 or 2, and a full field stays full (5 bots alone, 4 with two)
    events = tap(m, RIGHT)
    assert settings(m) == (2, 4, "EASY") and cues(events, "blip")
    events = tap(m, RIGHT)
    assert settings(m) == (2, 4, "EASY") and not cues(events, "blip")  # clamped, silent
    tap(m, LEFT)
    assert settings(m) == (1, 5, "EASY")
    # BOTS: 0 up to 6 - players
    tap(m, DOWN)
    for _ in range(7):
        tap(m, LEFT)
    assert m.bot_count == 0  # 1 player alone: a time trial
    tap(m, RIGHT)
    tap(m, RIGHT)
    assert m.bot_count == 2
    tap(m, UP)
    tap(m, RIGHT)
    assert settings(m) == (2, 2, "EASY")  # not a full field: kept as it was
    tap(m, DOWN)
    for _ in range(5):
        tap(m, RIGHT)
    assert m.bot_count == 4  # 2 players: at most 4 bots
    tap(m, UP)
    tap(m, LEFT)
    assert settings(m) == (1, 5, "EASY")  # full again: 5 with one player
    # LEVEL: EASY (the default), TOUGH, BRUTAL
    tap(m, DOWN)
    tap(m, DOWN)
    tap(m, LEFT)
    assert m.level == "EASY"  # clamped
    tap(m, RIGHT)
    assert m.level == "TOUGH"
    tap(m, RIGHT)
    tap(m, RIGHT)
    assert m.level == "BRUTAL"
    # QUIT has no value
    tap(m, DOWN)
    events = tap(m, RIGHT)
    assert m.title_index == 3 and settings(m) == (1, 5, "BRUTAL") and not cues(events)


def held(dx: int, dy: int, lag: int = 0, seconds: float = 2.0):
    """Frames of a stick held (on a diagonal, with dx and dy) through the real auto-repeat,
    the y axis crossing its threshold `lag` frames after x (as a real stick's two axes do)."""
    from gate_prix.input import AutoRepeat

    rx, ry = AutoRepeat(), AutoRepeat()
    for k in range(round(seconds / DT)):
        x, y = dx, dy if k >= lag else 0
        yield frame(p1={"nav": (rx.update(DT, x), ry.update(DT, y)), "stick": (x, y),
                        "steer": float(x)})


@pytest.mark.parametrize("dx, dy, start, want", [(1, -1, 1, 0), (-1, 1, 1, 2), (1, 1, 0, 1),
                                                  (-1, -1, 2, 1), (1, 1, 2, 3)])
@pytest.mark.parametrize("lag", [0, 2, 5])
def test_a_held_diagonal_moves_one_row_up_or_down_and_never_a_value(dx, dy, start, want, lag):
    """The sideways repeats never move the menu, and a held push moves it one row. Only a
    push straight sideways changes a value: a diagonal's x is the stick's slop."""
    m = fresh(1)
    for _ in range(start):
        tap(m, DOWN)
    rows = []
    for inp in held(dx, dy, lag):
        m.update(DT, inp)
        rows.append(m.title_index)
    steps = [b - a for a, b in zip(rows, rows[1:]) if a != b]
    assert rows[-1] == want and all(d == (1 if dy > 0 else -1) for d in steps), rows[:20]
    if lag == 0:
        assert settings(m) == (1, 5, "EASY")


def test_two_pads_held_opposite_ways_follow_p1():
    m = fresh(1)
    m.update(DT, DOWN)
    rows = []
    for k in range(120):
        m.update(DT, frame(p1={"stick": (0, 1), "nav": (0, 1) if k % 7 == 0 else (0, 0)},
                           p2={"stick": (0, -1), "nav": (0, -1) if k % 5 == 0 else (0, 0)}))
        rows.append(m.title_index)
    assert set(rows) == {2}


def held_down(m: Match, seconds: float, dx: int = 0, dy: int = 1) -> int:
    """Hold P1's stick (down) through the real auto-repeat; returns the blips."""
    blips = sum(len(cues(m.update(DT, inp), "blip")) for inp in held(dx, dy, 0, seconds))
    m.update(DT, IDLE)  # let go
    return blips


def test_a_held_stick_moves_one_row_per_push():
    """A push held for 2 s from PLAYERS lands on BOTS, never runs on; each further push one
    row more, and on QUIT it stays (no wrap)."""
    m = fresh(1)
    for want in (1, 2, 3):
        assert held_down(m, 2.0) == 1 and m.title_index == want
    assert held_down(m, 2.0) == 0 and m.title_index == 3


def test_a_held_sideways_push_changes_a_value_one_step():
    m = fresh(1)
    tap(m, DOWN)
    assert held_down(m, 2.0, dx=-1, dy=0) == 1 and m.bot_count == 4
    assert held_down(m, 2.0, dx=-1, dy=0) == 1 and m.bot_count == 3
    assert held_down(m, 2.0, dx=1, dy=0) == 1 and m.bot_count == 4


def test_an_attract_race_resets_the_rows_for_the_next_visitor():
    m = fresh(1)
    tap(m, RIGHT)  # 2 players
    tap(m, DOWN)
    tap(m, LEFT)  # 3 bots
    tap(m, DOWN)
    tap(m, RIGHT)  # TOUGH
    assert settings(m) == (2, 3, "TOUGH") and m.title_index == 2
    run(m, config.ATTRACT_DELAY + 0.5)
    assert m.attract and settings(m) == (1, 5, "EASY") and m.title_index == 0


@pytest.mark.parametrize("button", [A, START])
def test_a_title_left_on_quit_offers_players_once_the_attract_race_runs(button):
    """The next visitor's first press (A, most likely) starts a match, never quits."""
    m = fresh(1)
    tap(m, RIGHT)  # 2 players
    for _ in range(3):
        tap(m, DOWN)
    assert m.title_index == 3
    run(m, config.ATTRACT_DELAY + 1.0)
    assert m.attract and m.title_index == 0  # back on PLAYERS
    events = m.update(DT, button)
    assert not m.quit_requested and not cues(events, "quit")
    assert m.state == HOWTO and settings(m) == (1, 5, "EASY")  # the attract race reset them


def test_a_on_quit_quits_at_once():
    m = fresh(1)
    for _ in range(3):
        tap(m, DOWN)
    assert not m.quit_requested
    events = m.update(DT, A)
    assert m.quit_requested and cues(events, "quit") and m.state == TITLE


def test_start_never_quits_it_begins_the_race_as_set_from_quit():
    m = fresh(1)
    tap(m, RIGHT)  # 2 players
    tap(m, DOWN)
    tap(m, LEFT)  # 3 bots
    tap(m, DOWN)
    tap(m, RIGHT)
    tap(m, LEFT)  # EASY again
    tap(m, DOWN)  # QUIT
    events = m.update(DT, START)
    assert not m.quit_requested and not cues(events, "quit")
    assert m.state == HOWTO and m.title_index == 0 and settings(m) == (2, 3, "EASY")
    through_card(m)
    assert m.race.players == 2 and len(m.race.racers) == 5
    assert {d.level for d in m.drivers.values()} == {"EASY"} and len(m.drivers) == 3


@pytest.mark.parametrize("row", [0, 1, 2])
def test_a_on_any_row_but_quit_begins_the_race(row):
    m = fresh(1)
    for _ in range(row):
        tap(m, DOWN)
    m.update(DT, A)
    assert m.state == HOWTO and not m.quit_requested


@pytest.mark.parametrize("mode, players", [(1, 1), (2, 2)])
def test_no_bots_is_a_time_trial_alone_or_a_duel(mode, players):
    m = fresh(1)
    if mode == 2:
        tap(m, RIGHT)
    tap(m, DOWN)
    for _ in range(5):
        tap(m, LEFT)
    m.update(DT, START)
    through_card(m)
    assert [r.car.id for r in m.race.racers] == ["p1", "p2"][:players]
    assert m.drivers == {}


def test_b_on_the_title_does_nothing():
    m = fresh(1)
    m.update(DT, DOWN)
    events = m.update(DT, B)
    assert m.state == TITLE and m.title_index == 1 and not m.quit_requested and not events


def test_the_attract_race_never_picks_quit():
    m = fresh(1)
    run(m, config.ATTRACT_DELAY + 30.0)
    assert m.attract and m.title_index == 0 and not m.quit_requested


@pytest.mark.parametrize("inp", [DOWN, RIGHT])
def test_the_input_that_stops_the_attract_race_changes_nothing(inp):
    m = fresh(1)
    run(m, config.ATTRACT_DELAY + 0.5)
    assert m.attract
    events = m.update(DT, inp)
    assert not m.attract and m.title_index == 0 and settings(m) == (1, 5, "EASY")
    assert not cues(events, "blip")
    m.update(DT, IDLE)
    tap(m, RIGHT)
    assert m.mode == 2


@pytest.mark.parametrize("button", ["a", "start"])
def test_a_or_start_shows_the_card_then_the_countdown_with_the_chosen_field(button):
    for mode in (1, 2):
        m = fresh(1)
        if mode == 2:
            tap(m, RIGHT)
        events = m.update(DT, frame(p2={button: True, "held": True}))
        assert m.state == HOWTO and m.race is None and cues(events, "select")
        through_card(m)
        assert m.race.players == mode and not m.attract
        assert len(m.race.racers) == config.CARS  # the bots fill the field
        assert {d.level for d in m.drivers.values()} == {"EASY"}  # the default level


# --- The HOW TO PLAY card --------------------------------------------------------------------


def test_the_card_ignores_presses_in_its_first_moment_then_any_button_goes_on():
    m = fresh(1)
    m.update(DT, START)
    for inp in (A, START, B, X):  # mashed during the guard: nothing
        m.update(DT, inp)
        assert m.state == HOWTO
    run(m, config.HOWTO_GUARD)
    for inp in (frame(p1={"steer": 1.0, "nav": (1, 0), "stick": (1, 0)}),
                frame(p2={"brake": 1.0, "nav": (0, 1), "stick": (0, 1)})):
        m.update(DT, inp)  # the stick doesn't
        assert m.state == HOWTO
    events = m.update(DT, frame(p2={"select": True, "held": True}))  # any button, either pad
    assert m.state == COUNTDOWN and cues(events, "count")
    assert not cues(events, "pause") and m.t == 0.0  # the press did nothing else


@pytest.mark.parametrize("name", ["a", "b", "start", "select", "button"])
def test_every_button_dismisses_the_card(name):
    m = fresh(1)
    m.update(DT, START)
    run(m, config.HOWTO_GUARD + DT)
    m.update(DT, frame(p1={name: True, "held": True}))
    assert m.state == COUNTDOWN


def test_the_idle_timeout_runs_on_the_card():
    m = fresh(1)
    m.update(DT, DOWN)
    m.update(DT, A)
    run(m, config.IDLE_TIMEOUT + DT)
    assert m.state == TITLE and m.mode == 1 and m.title_index == 0


def test_a_rematch_skips_the_card():
    m = started()
    finish(m, "p1")
    run(m, config.FINISH_DELAY + config.RESULT_LOCK + 0.2)
    m.update(DT, A)
    assert m.state == COUNTDOWN


def test_the_attract_race_runs_after_3_s_untouched_and_any_input_stops_it():
    m = fresh(1)
    run(m, config.ATTRACT_DELAY - 0.1)
    assert m.race is None
    run(m, 0.2)
    assert m.state == TITLE and m.attract and m.race is not None
    race = m.race
    assert race.players == 0 and race.finish_all and len(race.racers) == config.ATTRACT_BOTS
    assert set(m.drivers) == {r.car.id for r in race.racers}  # bots only: nobody drives
    assert {d.level for d in m.drivers.values()} == {config.ATTRACT_LEVEL} == {"TOUGH"}
    assert m.players == () and len(m.viewed) == 2 and set(m.viewed) <= set(m.drivers)
    assert all(v.startswith("cpu") for v in m.viewed)  # neutral colours, CPU names
    events = run(m, 2.0)
    assert race.time > 1.5 and not events  # the attract race is silent
    m.update(DT, frame(p2={"steer": 0.5}))
    assert m.state == TITLE and not m.attract and m.race is None


def test_start_during_the_attract_race_begins_a_real_race():
    m = fresh(1)
    run(m, config.ATTRACT_DELAY + 1)
    m.update(DT, START)
    assert m.state == HOWTO and not m.attract and m.race is None
    through_card(m)
    assert m.race.players == 1


def test_a_finished_attract_race_is_followed_by_another():
    m = fresh(1)
    run(m, config.ATTRACT_DELAY + 0.1)
    first = m.race
    first.over = True
    m.update(DT, IDLE)
    assert m.attract and m.race is not first


# --- The countdown ---------------------------------------------------------------------------


def test_the_countdown_beeps_3_2_1_then_go_and_the_cars_wait_for_it():
    m = fresh(1)
    m.update(DT, START)
    events = through_card(m)
    assert [c.value for c in cues(events, "count")] == [3]
    assert m.countdown == 3
    events = run(m, config.COUNTDOWN - 2 * DT)
    assert [c.value for c in cues(events, "count")] == [2, 1]
    assert m.state == COUNTDOWN and m.race.time == 0.0
    z = [r.car.z for r in m.race.racers]
    events = run(m, 3 * DT)
    assert cues(events, "go") and m.state == RACE
    run(m, 0.5)
    assert all(r.car.z > z0 for r, z0 in zip(m.race.racers, z))


# --- Driving ---------------------------------------------------------------------------------


def test_the_players_steer_their_own_cars():
    m = started(mode=2)
    run(m, 2.0)  # up to speed: the steering rate grows with it
    p1, p2 = m.race.racer("p1"), m.race.racer("p2")
    x1, x2 = p1.car.x, p2.car.x
    run(m, 0.5, frame(p1={"steer": -1.0}, p2={"steer": 1.0}))
    assert p1.car.x < x1 - 0.2 and p2.car.x > x2 + 0.2


def test_one_player_drives_with_either_pad():
    m = started(mode=1)
    run(m, 2.0)
    p1 = m.race.racer("p1")
    x = p1.car.x
    run(m, 0.5, frame(p2={"steer": 1.0}))
    assert p1.car.x > x + 0.2


def test_the_brake_slows_the_car():
    m = started()
    run(m, 2.5)
    fast = m.race.racer("p1").car.speed
    run(m, 1.0, frame(p1={"brake": 1.0}))
    assert m.race.racer("p1").car.speed < fast * 0.7


def test_an_item_is_used_on_the_press_of_a_not_while_it_is_held():
    m = started()
    p1 = m.race.racer("p1")
    p1.item = "SPLIT"
    events = m.update(DT, A)
    assert [e for e in events if getattr(e, "kind", None) == "item" and e.car == "p1"]
    p1.item = "QEC"
    run(m, 0.5, HELD)
    assert p1.item == "QEC"  # held, not pressed again: still there
    m.update(DT, A)
    assert p1.item is None


def test_race_events_of_the_players_reach_the_sound_and_the_hud():
    m = started()
    p1 = m.race.racer("p1")
    row = m.race.rows[0]
    right = next(a for a in row.arches if a.right)
    p1.car.z, p1.car.x, p1.car.speed = row.z - 50.0, right.offset, config.TOP_SPEED
    events = m.update(DT, IDLE)
    assert [e for e in events if getattr(e, "kind", None) == "right" and e.car == "p1"]


def place(m: Match, car_id: str, z: float, x: float) -> None:
    car = m.race.racer(car_id).car
    car.z = car.prev_z = z
    car.x = car.prev_x = x
    car.speed = m.race.racer("p1").car.speed


def bumps_of(events):
    return sorted((e.car, e.value) for e in events if getattr(e, "kind", None) == "bump")


def test_a_bots_own_cues_stay_silent():
    """The sound policy: a bot's drifts, turbos, streaks, boxes, items, laps and checks never
    reach the sound or the HUD; only bumps and hits (HEARD) a player can see do."""
    m = started()
    events = run(m, 25.0, frame(p1={"steer": 0.0}))
    race_events = [e for e in events if not isinstance(e, Cue)]
    assert race_events
    for e in race_events:
        assert e.car == "p1" or (e.kind in AIMED and e.value == "p1") or e.kind in HEARD, e


def test_a_bump_with_a_person_sounds_on_their_side():
    m = started()
    run(m, 2.0)
    p1 = m.race.racer("p1").car
    for i, car_id in enumerate(("cpu2", "cpu3", "cpu4", "cpu5")):  # out of the way
        place(m, car_id, p1.z - 60_000.0 - 3000.0 * i, 0.0)
    place(m, "cpu1", p1.z + 100.0, p1.x + 0.1)
    # both sides of P1's bump (one sound: a frame's sounds play once)
    assert bumps_of(m.update(DT, IDLE)) == [("cpu1", "p1"), ("p1", "cpu1")]


@pytest.mark.parametrize("ahead, heard", [(3000.0, True), (-800.0, True),
                                          (config.HEAR_AHEAD + 2000.0, False),
                                          (-config.HEAR_BEHIND - 1500.0, False)])
def test_what_happens_to_a_bot_sounds_when_a_player_can_see_it(ahead, heard):
    """A bump between two bots, and a bot's MEASURE hitting another, sound as they would
    for a person, when it happens in a player's view (or just behind them)."""
    m = started()
    run(m, 2.0)
    p1 = m.race.racer("p1").car
    place(m, "p1", p1.z, -0.8)
    for i, car_id in enumerate(("cpu3", "cpu4", "cpu5")):
        place(m, car_id, p1.z + 70_000.0 + 3000.0 * i, 0.0)
    place(m, "cpu1", p1.z + ahead, 0.3)
    place(m, "cpu2", p1.z + ahead + 100.0, 0.4)  # cpu1 runs into it
    want = [("cpu1", "cpu2"), ("cpu2", "cpu1")] if heard else []
    assert bumps_of(m.update(DT, IDLE)) == want
    place(m, "cpu2", p1.z + ahead, 0.9)
    m.race.shots.append(Shot("cpu2", "cpu1", config.MEASURE_FLIGHT))  # landing now
    events = m.update(DT, IDLE)
    hits = [(e.car, e.value) for e in events if getattr(e, "kind", None) == "collapse"]
    assert hits == ([("cpu1", "cpu2")] if heard else [])
    assert m.race.racer("cpu1").car.spinning  # it was hit either way


# --- Pause -----------------------------------------------------------------------------------


def test_start_pauses_and_everything_freezes():
    m = started()
    run(m, 1.0)
    t = m.race.time
    events = m.update(DT, frame(p2={"start": True, "held": True}))  # either pad
    assert m.state == PAUSED and cues(events, "pause") and m.pause_index == 0
    run(m, 2.0)
    assert m.race.time == t


@pytest.mark.parametrize("button", ["b", "start"])
def test_b_or_start_resumes(button):
    m = started()
    m.update(DT, START)
    m.update(DT, IDLE)
    m.update(DT, frame(p1={button: True, "held": True}))
    assert m.state == RACE


def test_the_pause_menu_moves_with_the_stick_and_a_picks():
    m = started()
    m.update(DT, START)
    m.update(DT, A)  # RESUME
    assert m.state == RACE
    m.update(DT, START)
    m.update(DT, DOWN)
    assert config.PAUSE_ITEMS[m.pause_index] == "QUIT TO TITLE"
    m.update(DT, DOWN)  # wraps round
    assert m.pause_index == 0
    m.update(DT, frame(p1={"nav": (0, -1)}))
    events = m.update(DT, A)
    assert m.state == TITLE and m.race is None and cues(events, "title")


def test_a_resumed_a_press_does_not_use_an_item():
    m = started()
    p1 = m.race.racer("p1")
    p1.item = "QEC"
    m.update(DT, START)
    m.update(DT, A)  # picks RESUME
    run(m, 0.2, frame(p1={"held": True}))
    assert m.state == RACE and p1.item == "QEC"


def test_start_also_pauses_the_countdown():
    m = begun()
    m.update(DT, IDLE)
    m.update(DT, START)
    assert m.state == PAUSED
    t = m.t
    run(m, 2.0)
    m.update(DT, B)
    assert m.state == COUNTDOWN and m.t == pytest.approx(t, abs=DT)


def test_the_title_waits_for_the_buttons_to_be_let_go_after_quit_to_title():
    m = started(mode=2)
    m.update(DT, START)
    m.update(DT, DOWN)
    m.update(DT, A)
    assert m.state == TITLE and m.mode == 2  # the mode is kept
    # the A that picked QUIT TO TITLE (still held, or mashed) starts nothing
    run(m, 0.5, A)
    assert m.state == TITLE
    m.update(DT, IDLE)
    m.update(DT, A)
    assert m.state == HOWTO


# --- Idle ------------------------------------------------------------------------------------


@pytest.mark.parametrize("paused", [False, True])
def test_a_minute_untouched_goes_back_to_the_title_at_one_player(paused):
    m = started(mode=2)
    m.update(DT, START if paused else frame(p1={"steer": 0.1}))
    run(m, config.IDLE_TIMEOUT - 1.0)
    assert m.state != TITLE
    m.level = "BRUTAL"
    run(m, 1.1)
    assert m.state == TITLE and settings(m) == (1, 5, "EASY") and m.race is None


def test_touching_anything_keeps_the_race_going():
    m = started()
    for _ in range(3):
        run(m, config.IDLE_TIMEOUT - 5)
        m.update(DT, frame(p1={"steer": 0.3}))
    assert m.state == RACE


# --- The finish and the result ---------------------------------------------------------------


def test_one_player_finishing_shows_the_result_after_a_moment():
    m = started()
    finish(m, "p1")
    run(m, 0.1)
    assert m.state == RACE and m.banner("p1", "finish").value == 1
    run(m, config.FINISH_DELAY)
    assert m.state == RESULT
    rows = m.results
    assert [r.car for r in rows][0] == "p1" and rows[0].place == 1 and rows[0].player
    assert len(rows) == config.CARS
    assert (rows[0].label, rows[0].colour) == ("P1", "p1")
    bots = {(r.label, r.colour) for r in rows[1:]}  # the bots by their names and colours
    assert bots == {(f"CPU{i + 1}", c) for i, c in enumerate(config.CPU_COLORS)}


def test_a_finished_player_is_driven_on_by_the_ai():
    m = started()
    finish(m, "p1")
    run(m, 0.1)
    assert m.drivers["p1"].level == config.AUTOPILOT_LEVEL
    p1 = m.race.racer("p1")
    x = p1.car.x
    run(m, 1.0, frame(p1={"steer": 1.0}))  # ignored
    assert abs(p1.car.x - x) < 0.5 and p1.car.speed > 0.5 * config.TOP_SPEED


def test_two_players_race_until_both_have_finished():
    m = started(mode=2)
    finish(m, "p1")
    run(m, config.FINISH_DELAY + 1)
    assert m.state == RACE
    finish(m, "p2")
    run(m, config.FINISH_DELAY + 0.2)
    assert m.state == RESULT
    assert [r.car for r in m.results if r.player] == ["p1", "p2"]


def test_the_second_player_gets_a_grace_time_after_the_first_finishes():
    m = started(mode=2)
    finish(m, "p1")
    run(m, config.FINISH_GRACE - 1)
    assert m.state == RACE
    run(m, 1 + config.FINISH_DELAY + 0.2, frame(p1={"steer": 0.1}))
    assert m.state == RESULT
    p2 = next(r for r in m.results if r.car == "p2")
    assert p2.time is None  # placed where it was


def test_the_result_holds_each_players_circuit_accuracy():
    m = started()
    p1 = m.race.racer("p1")
    for slot in range(config.SLOTS):
        p1.circuit.take(slot, p1.circuit.target[slot] if slot % 4 else None)
    finish(m, "p1")
    run(m, config.FINISH_DELAY + 0.2)
    row = m.results[0]
    assert row.right == config.SLOTS - config.SLOTS // 4


def test_the_result_shows_the_check_as_the_number_right():
    m = started()
    p1 = m.race.racer("p1")
    p1.check = 4  # what the CIRCUIT CHECK found: 4 wrong
    finish(m, "p1")
    run(m, 0.1)
    row = next(r for r in m.results if r.car == "p1")
    assert row.check == 4 and row.check_right == config.CHECK_SLOTS - 4 == 12
    cpu = next(r for r in m.results if not r.player)
    assert cpu.check is None and cpu.check_right is None


def test_a_measure_that_hits_reaches_the_shooters_sound_too():
    m = started()
    p1 = m.race.racer("p1")
    p1.item = "MEASURE"
    target = m.race.measure_target("p1")  # a CPU on the grid ahead
    assert target is not None and not target.player
    events = m.update(DT, A)
    events += run(m, config.MEASURE_FLIGHT + 0.1)
    assert [e for e in events if getattr(e, "kind", None) == "collapse"
            and e.car == target.car.id and e.value == "p1"]


def test_the_result_keeps_each_players_circuit_as_it_was_at_the_finish():
    m = started()
    p1 = m.race.racer("p1")
    for slot in range(config.SLOTS):
        p1.circuit.take(slot, None)
    finish(m, "p1")
    run(m, 0.1)
    row = m.results[0]
    assert row.right == 0 and row.slots == (None,) * config.SLOTS
    assert row.results == (False,) * config.SLOTS
    p1.circuit.qec()  # anything after the freeze changes nothing in the result
    assert m.results[0].results == (False,) * config.SLOTS


def test_the_result_ignores_a_mashed_a_then_a_rematches():
    m = started(mode=2)
    finish(m, "p1")
    finish(m, "p2")
    run(m, config.FINISH_DELAY + 0.2)
    assert m.state == RESULT
    old = m.race
    m.update(DT, A)
    assert m.state == RESULT
    run(m, config.RESULT_LOCK)
    m.update(DT, A)
    assert m.state == COUNTDOWN and m.race is not old and m.race.players == 2


def test_b_on_the_result_goes_to_the_title():
    m = started()
    finish(m, "p1")
    run(m, config.FINISH_DELAY + config.RESULT_LOCK + 0.2)
    m.update(DT, B)
    assert m.state == TITLE and m.mode == 1


# --- Banners ---------------------------------------------------------------------------------


def to_the_check(m: Match, car_id: str = "p1", wrong: int = 3):
    """Fill a player's circuit (the first `wrong` slots missed) and put the car just short of
    the line into the final lap."""
    race = m.race
    r = race.racer(car_id)
    for slot in range(config.SLOTS):
        r.circuit.take(slot, None if slot < wrong else r.circuit.target[slot])
    r.next_row = len(race.rows)
    r.next_box = race.box_index(2 * race.lap_length)
    r.laps = 1
    r.car.z = 2 * race.lap_length - 20
    r.car.speed = config.TOP_SPEED
    return r


def test_the_circuit_check_freezes_only_that_players_view_while_the_car_drives_on():
    m = started()
    p1 = to_the_check(m)
    p1.item = "QEC"
    events = run(m, 0.1)
    assert [e.value for e in events if getattr(e, "kind", None) == "check"] == [3]
    assert m.frozen("p1") and p1.check_wait > 0
    x, z, t = p1.car.x, p1.car.z, m.race.time
    # the pad does nothing while frozen: the car drives straight on, the item stays held
    run(m, 0.5, frame(p1={"steer": 1.0, "a": True, "held": True}))
    assert m.race.time == pytest.approx(t + 0.5)  # the race runs on
    assert p1.car.x == pytest.approx(x, abs=0.01) and p1.item == "QEC"
    assert p1.car.z - z == pytest.approx(0.5 * config.TOP_SPEED, rel=0.02)
    run(m, config.CHECK_FREEZE - 0.5)
    assert not m.frozen("p1") and p1.car.boost > 0  # the warp
    run(m, 0.3, frame(p1={"steer": 1.0}))
    assert p1.car.x > x + 0.3


def test_in_2p_the_check_freezes_only_the_player_who_crossed():
    m = started(mode=2)
    to_the_check(m, "p1")
    run(m, 0.1)
    assert m.frozen("p1") and not m.frozen("p2")
    p2 = m.race.racer("p2")
    x = p2.car.x
    run(m, 0.3, frame(p2={"steer": 1.0}))
    assert p2.car.x > x + 0.03  # still slow off the grid, but steering


def at_row(m: Match, x_of) -> None:
    """Put P1 just before its next row, at x_of(row)."""
    p1 = m.race.racer("p1")
    row = m.race.rows[p1.next_row]
    p1.car.z, p1.car.x, p1.car.speed = row.z - 50.0, x_of(row), config.TOP_SPEED


def test_each_row_flashes_right_gate_wrong_gate_or_missed_near_the_car():
    for seed in range(1, 60):  # a race whose second row has a decoy
        m = started(seed=seed)
        if len(m.race.rows[1].arches) > 1:
            break
    at_row(m, lambda row: next(a.offset for a in row.arches if a.right))
    m.update(DT, IDLE)
    flash = m.banner("p1", "gate")
    assert flash is not None and flash.value == ("right", 1)
    assert flash.time == pytest.approx(config.FLASH_TIME, abs=1.5 * DT)
    at_row(m, lambda row: next(a.offset for a in row.arches if not a.right))
    m.update(DT, IDLE)
    assert m.banner("p1", "gate").value == ("wrong", 1)  # one flash at a time
    assert len([b for b in m.banners["p1"] if b.kind == "gate"]) == 1
    at_row(m, lambda row: 1.9)
    m.update(DT, IDLE)
    assert m.banner("p1", "gate").value == ("miss", 2)
    run(m, config.FLASH_TIME)
    assert m.banner("p1", "gate") is None


def through_box(m: Match, car_id: str = "p1") -> list:
    """Drive a player through a box of its next box line (one still there)."""
    race = m.race
    r = race.racer(car_id)
    z, k = race.box_lines[r.next_box]
    j = next(j for j in range(len(race.track.boxes[k][1])) if race.box_present(k, j))
    r.car.z, r.car.x, r.car.speed = z - 50.0, race.track.boxes[k][1][j], config.TOP_SPEED
    return m.update(DT, IDLE)


def rematch(m: Match) -> None:
    finish(m, "p1")
    run(m, config.FINISH_DELAY + config.RESULT_LOCK + 0.2)
    m.update(DT, A)
    run(m, config.COUNTDOWN + DT)
    assert m.state == RACE


def test_the_first_pickup_of_each_item_shows_how_to_use_it_once_a_session():
    m = started()
    m.race.roll_item = lambda place, **kw: "SPLIT"
    through_box(m)
    tip = m.banner("p1", "tip")
    assert tip is not None and tip.value == "SPLIT"
    run(m, config.TIP_TIME)
    assert m.banner("p1", "tip") is None
    m.race.racer("p1").item = None
    through_box(m)
    assert m.race.racer("p1").item == "SPLIT" and m.banner("p1", "tip") is None  # seen
    m.race.racer("p1").item = None
    m.race.roll_item = lambda place, **kw: "QEC"
    through_box(m)
    assert m.banner("p1", "tip").value == "QEC"
    # a rematch is the same visitor: no tips again
    rematch(m)
    m.race.roll_item = lambda place, **kw: "SPLIT"
    through_box(m)
    assert m.banner("p1", "tip") is None
    # a minute untouched means someone new: the tips come back
    run(m, config.IDLE_TIMEOUT + 0.1)
    assert m.state == TITLE
    m.update(DT, START)
    through_card(m)
    run(m, config.COUNTDOWN + DT)
    m.race.roll_item = lambda place, **kw: "SPLIT"
    through_box(m)
    assert m.banner("p1", "tip").value == "SPLIT"


def test_each_player_gets_their_own_item_tips():
    m = started(mode=2)
    m.race.roll_item = lambda place, **kw: "QEC"
    through_box(m, "p1")
    assert m.banner("p1", "tip").value == "QEC"
    through_box(m, "p2")
    assert m.banner("p2", "tip").value == "QEC"


def test_a_button_held_at_launch_does_not_start_a_match():
    m = Match(random.Random(1))
    assert m.title_wait
    for k in range(40):  # held down from the launch, mashed too
        m.update(DT, frame(p1={"a": k % 3 == 0, "start": k % 5 == 0, "held": True}))
        assert m.state == TITLE
    m.update(DT, IDLE)  # let go
    m.update(DT, A)
    assert m.state == HOWTO


def test_a_held_input_has_no_presses():
    inp = frame(p1={"a": True, "b": True, "start": True, "select": True, "nav": (1, 0),
                    "steer": 0.4, "brake": 1.0, "held": True})
    held = inp.held_only()
    p = held.players["p1"]
    assert not (p.a or p.b or p.start or p.select or p.button) and p.nav == (0, 0)
    assert p.steer == 0.4 and p.brake == 1.0 and p.held and held.activity


def test_every_box_pops_its_item_up_over_the_car():
    m = started()
    m.race.roll_item = lambda place, **kw: "MEASURE"
    through_box(m)
    reveal = m.banner("p1", "reveal")
    assert reveal is not None and reveal.value == "MEASURE"
    run(m, config.REVEAL_TIME)
    assert m.banner("p1", "reveal") is None
    run(m, config.TIP_TIME)
    m.race.racer("p1").item = None
    through_box(m)  # seen before: no tip, but the item still pops up
    assert m.banner("p1", "reveal").value == "MEASURE" and m.banner("p1", "tip") is None


def test_lap_2_and_the_final_lap_get_their_banners():
    m = started()
    r = m.race.racer("p1")
    r.next_row = config.ROWS_PER_LAP
    r.next_box = m.race.box_index(m.race.lap_length)
    r.car.z = m.race.lap_length - 20
    run(m, 0.1)
    assert m.banner("p1", "lap").value == 2 and m.banner("p1", "final") is None
    to_the_check(m)
    run(m, 0.1)
    final = m.banner("p1", "final")
    assert final is not None and final.value == config.LAPS and m.banner("p1", "lap") is None
    assert m.frozen("p1")  # the renderer shows it once the check's freeze is over
    run(m, config.CHECK_FREEZE + config.FINAL_BANNER)
    assert m.banner("p1", "final") is None
