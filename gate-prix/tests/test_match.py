"""The match flow: title, attract, countdown, race, pause, result, idle."""

import random

import pytest

from gate_prix import config
from gate_prix.match import (COUNTDOWN, PAUSED, RACE, RESULT, TITLE, Cue, FrameInput, Match,
                             PlayerInput)

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


def run(m: Match, seconds: float, inp: FrameInput = IDLE) -> list:
    events = []
    for _ in range(round(seconds / DT)):
        events += m.update(DT, inp)
    return events


def cues(events, kind=None):
    return [e for e in events if isinstance(e, Cue) and (kind is None or e.kind == kind)]


def started(mode=1, seed=1) -> Match:
    """A match whose race has just begun (after the countdown)."""
    m = Match(random.Random(seed))
    if mode == 2:
        m.update(DT, DOWN)
    m.update(DT, START)
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


def test_the_title_starts_at_one_player_and_the_stick_picks_up_or_down():
    m = Match(random.Random(1))
    assert m.state == TITLE and m.mode == 1
    events = m.update(DT, DOWN)
    assert m.mode == 2 and cues(events, "blip")
    events = m.update(DT, frame(p2={"nav": (0, 1), "stick": (0, 1)}))  # down again: still 2
    assert m.mode == 2 and not cues(events, "blip")
    events = m.update(DT, frame(p2={"nav": (0, -1)}))  # up, on either pad: 1 PLAYER
    assert m.mode == 1 and cues(events, "blip")
    m.update(DT, frame(p1={"nav": (1, 0), "stick": (1, 0)}))  # sideways: no choice
    assert m.mode == 1


def held_diagonal(dx: int, dy: int, lag: int, seconds: float = 2.0):
    """Frames of a stick held on a diagonal through the real auto-repeat, the y axis
    crossing its threshold `lag` frames after x (as a real stick's two axes do)."""
    from gate_prix.input import AutoRepeat

    rx, ry = AutoRepeat(), AutoRepeat()
    for k in range(round(seconds / DT)):
        x, y = dx, dy if k >= lag else 0
        yield frame(p1={"nav": (rx.update(DT, x), ry.update(DT, y)), "stick": (x, y),
                        "steer": float(x)})


@pytest.mark.parametrize("dx, dy, want", [(1, -1, 1), (-1, 1, 2), (1, 1, 2), (-1, -1, 1)])
@pytest.mark.parametrize("lag", [0, 2, 5])
def test_a_held_diagonal_picks_one_mode(dx, dy, want, lag):
    m = Match(random.Random(1))
    modes, blips = [], 0
    for inp in held_diagonal(dx, dy, lag):
        blips += len(cues(m.update(DT, inp), "blip"))
        modes.append(m.mode)
    changes = sum(1 for a, b in zip(modes, modes[1:]) if a != b)
    assert modes[-1] == want and changes <= 1 and blips <= 1, (modes[:12], blips)


def test_two_pads_held_opposite_ways_settle_on_p1s_choice():
    m = Match(random.Random(1))
    modes = []
    for _ in range(120):
        m.update(DT, frame(p1={"stick": (0, 1)}, p2={"stick": (0, -1), "nav": (0, -1)}))
        modes.append(m.mode)
    assert set(modes) == {2}


def test_a_held_stick_stays_on_its_choice():
    """Auto-repeated steps of a held stick must not flicker between the two modes."""
    m = Match(random.Random(1))
    modes, blips = [], 0
    for k in range(60):  # a second held down, a step every few frames
        events = m.update(DT, frame(p1={"nav": (0, 1) if k % 7 == 0 else (0, 0),
                                        "steer": 0.0}) if k % 7 else DOWN)
        modes.append(m.mode)
        blips += len(cues(events, "blip"))
    assert set(modes) == {2} and blips == 1


def test_the_input_that_stops_the_attract_race_does_not_change_the_mode():
    m = Match(random.Random(1))
    run(m, config.ATTRACT_DELAY + 0.5)
    assert m.attract
    events = m.update(DT, DOWN)
    assert not m.attract and m.mode == 1 and not cues(events, "blip")
    m.update(DT, DOWN)
    assert m.mode == 2


@pytest.mark.parametrize("button", ["a", "start"])
def test_a_or_start_begins_the_countdown_with_the_chosen_players(button):
    for mode in (1, 2):
        m = Match(random.Random(1))
        if mode == 2:
            m.update(DT, DOWN)
        m.update(DT, frame(p2={button: True, "held": True}))
        assert m.state == COUNTDOWN
        assert m.race.players == mode and not m.attract


def test_the_attract_race_runs_after_3_s_untouched_and_any_input_stops_it():
    m = Match(random.Random(1))
    run(m, config.ATTRACT_DELAY - 0.1)
    assert m.race is None
    run(m, 0.2)
    assert m.state == TITLE and m.attract and m.race is not None
    race = m.race
    assert race.players == 2 and race.finish_all
    assert set(m.bots) == {r.car.id for r in race.racers}  # bots drive P1 and P2 too
    assert all(m.bots[p].skill == config.ATTRACT_SKILL for p in ("p1", "p2"))
    events = run(m, 2.0)
    assert race.time > 1.5 and not events  # the attract race is silent
    m.update(DT, frame(p2={"steer": 0.5}))
    assert m.state == TITLE and not m.attract and m.race is None


def test_start_during_the_attract_race_begins_a_real_race():
    m = Match(random.Random(1))
    run(m, config.ATTRACT_DELAY + 1)
    m.update(DT, START)
    assert m.state == COUNTDOWN and not m.attract and m.race.players == 1


def test_a_finished_attract_race_is_followed_by_another():
    m = Match(random.Random(1))
    run(m, config.ATTRACT_DELAY + 0.1)
    first = m.race
    first.over = True
    m.update(DT, IDLE)
    assert m.attract and m.race is not first


# --- The countdown ---------------------------------------------------------------------------


def test_the_countdown_beeps_3_2_1_then_go_and_the_cars_wait_for_it():
    m = Match(random.Random(1))
    events = m.update(DT, START)
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
    m = Match(random.Random(1))
    m.update(DT, START)
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
    assert m.state == COUNTDOWN


# --- Idle ------------------------------------------------------------------------------------


@pytest.mark.parametrize("paused", [False, True])
def test_a_minute_untouched_goes_back_to_the_title_at_one_player(paused):
    m = started(mode=2)
    m.update(DT, START if paused else frame(p1={"steer": 0.1}))
    run(m, config.IDLE_TIMEOUT - 1.0)
    assert m.state != TITLE
    run(m, 1.1)
    assert m.state == TITLE and m.mode == 1 and m.race is None


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


def test_a_finished_player_is_driven_on_by_a_bot():
    m = started()
    finish(m, "p1")
    run(m, 0.1)
    assert "p1" in m.bots
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


def test_the_circuit_check_shows_a_banner_for_the_player():
    m = started()
    p1 = m.race.racer("p1")
    for slot in range(config.ROWS_PER_LAP * 2):
        p1.circuit.take(slot, None if slot < 3 else p1.circuit.target[slot])
    p1.next_row = config.ROWS_PER_LAP * 2
    p1.next_box = m.race.box_index(2 * m.race.lap_length)
    p1.laps = 1
    p1.car.z = 2 * m.race.lap_length - 20
    run(m, 0.1)
    banner = m.banner("p1", "check")
    assert banner is not None and banner.value == 3
    run(m, config.CHECK_BANNER)
    assert m.banner("p1", "check") is None


def test_a_held_input_has_no_presses():
    inp = frame(p1={"a": True, "b": True, "start": True, "select": True, "nav": (1, 0),
                    "steer": 0.4, "brake": 1.0, "held": True})
    held = inp.held_only()
    p = held.players["p1"]
    assert not (p.a or p.b or p.start or p.select) and p.nav == (0, 0)
    assert p.steer == 0.4 and p.brake == 1.0 and p.held and held.activity
