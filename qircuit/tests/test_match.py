import random

import pytest

from qircuit import config, racers, tutorial
from qircuit.match import COUNTDOWN, MATCH_END, MENU_ROWS, RACE, SELECT, TITLE, TUTORIAL, FrameInput, Match, controls_for

DT = 1 / 60


def fresh() -> Match:
    return Match(random.Random(0))


def step(m: Match, **kw) -> list:
    return m.update(DT, FrameInput(activity=True, **kw))


def skip_card(m: Match) -> list:
    for _ in range(round(tutorial.LOCK / DT) + 1):
        step(m)
    events = step(m, any_button=True)
    assert m.state == COUNTDOWN
    return events


def to_race(m: Match) -> None:
    step(m, confirm=True)
    assert m.state == SELECT
    step(m, pause=True)  # Start: go with whatever everyone is on
    assert m.state == TUTORIAL
    skip_card(m)
    for _ in range(round(config.COUNTDOWN / DT) + 2):
        step(m)
    assert m.state == RACE


# --- the title ---------------------------------------------------------------------------------

def test_the_title_picks_players_bots_level_track_and_the_lead_to_win():
    m = fresh()
    assert (m.humans, m.bots, m.level, m.target) == (
        config.DEFAULT_HUMANS, config.DEFAULT_BOTS, config.DEFAULT_LEVEL, config.TARGET_DEFAULT)
    step(m, nav=(1, 0))
    assert m.humans == 2
    for _ in range(4):
        step(m, nav=(0, 1))
    step(m, nav=(1, 0))
    assert m.target == config.TARGET_CHOICES[(config.TARGET_CHOICES.index(config.TARGET_DEFAULT) + 1) % 3]


def test_alone_there_is_always_at_least_one_bot():
    m = fresh()
    m.row = 1
    for _ in range(20):
        step(m, nav=(-1, 0))
        assert 1 <= m.bots <= config.MAX_RACERS - 1


def test_bots_race_behind_the_title():
    m = fresh()
    for _ in range(180):
        step(m)
    assert m.demo is not None and max(b.v for b in m.demo.race.bodies) > 50


def test_controls_are_up_faster_down_slower_left_and_right_a_wire():
    inp = FrameInput(held={("stick", 0): frozenset({"up", "right"})}, pressed={("stick", 0): frozenset({"right"})})
    c = controls_for(2, "p1", inp)
    assert c.throttle and not c.brake and c.right and not c.left
    assert controls_for(1, "p1", FrameInput(held={("pad", 1): frozenset({"down"})})).brake  # alone: either pad


# --- the racer select ---------------------------------------------------------------------------

def to_select(humans: int = 1) -> Match:
    m = fresh()
    m.humans = humans
    m.bots = 2
    step(m, confirm=True)
    return m


def test_each_person_moves_their_own_cursor_and_locks_in_with_a():
    m = to_select(2)
    p1 = m.picks["p1"]
    step(m, pressed={("stick", 0): frozenset({"right"})})
    assert m.picks["p1"] == p1 + 1
    step(m, pad_a=(True, True))
    assert m.locked == {"p1", "p2"}
    for _ in range(round(0.7 / DT)):
        step(m)
    assert m.state == TUTORIAL and m.race.racer_keys["p1"] == racers.ROSTER[m.picks["p1"]].key


def test_b_with_nobody_locked_in_goes_back_and_three_people_start_with_start():
    m = to_select(1)
    step(m, pad_a=(True, False))
    step(m, back=True, pad_b=(True, False))  # unlocks first
    assert m.state == SELECT
    step(m, back=True, pad_b=(True, False))
    assert m.state == TITLE
    m = to_select(3)
    step(m, pad_a=(True, True))
    assert not m.locked
    step(m, pause=True)
    assert m.state == TUTORIAL


def test_bots_get_racers_nobody_else_is_on():
    m = to_select(2)
    m.bots = 6
    step(m, pause=True)
    keys = list(m.race.racer_keys.values())
    assert len(set(keys)) == 8


# --- the race: resets and the lead --------------------------------------------------------------

def leave_behind(m: Match, player: str) -> None:
    """Put a player's racer far behind the camera."""
    race = m.race
    for b in race.bodies_of(player):
        b.p = b.reach = race.leader().p - 900
        b.v = 0


def wait_out(m: Match) -> list:
    events = []
    for _ in range(round(config.OUT_DELAY / DT) + 2):
        events += step(m)
    return events


def test_falling_off_the_screen_puts_a_racer_back_in_at_the_back_of_the_pack():
    m = fresh()
    to_race(m)
    for _ in range(60):
        step(m)
    leave_behind(m, "cpu1")
    assert "reset" not in [e.kind for e in step(m)]
    assert "reset" in [e.kind for e in wait_out(m)]
    race, cam = m.race, m.pack.camera
    b = race.front("cpu1")
    x, y, _ = race.pose(b)
    assert cam.on_screen(x, y, b.z, -config.RESET_INSET + 0.05)  # well inside the screen
    assert b.p <= m.pack.lead_body().p - 2 * config.CAR_LEN and b.v > 50 and b.ghost > 0


def test_a_copy_on_screen_saves_its_player_the_reset():
    m = fresh()
    to_race(m)
    race = m.race
    lead = race.leader()
    copy = race._body("cpu2", lead.p - 20, (lead.lane + 2) % 4)
    race.bodies.append(copy)
    for b in race.bodies_of("cpu2"):
        if b is not copy:
            b.p = b.reach = lead.p - 900
    events = wait_out(m)
    assert "reset" not in [e.kind for e in events] and race.bodies_of("cpu2") == [copy]


def test_the_leader_scores_and_the_lead_changes_hands_only_once_clear():
    m = fresh()
    to_race(m)
    for _ in range(120):
        step(m)
    pack, race = m.pack, m.race
    holder = pack.holder
    assert holder is not None and sum(m.lead_time.values()) == pytest.approx(race.time, abs=1.5)
    other = next(p for p in m.players if p != holder)
    front = race.front(holder)
    for b in race.bodies_of(other):
        b.p, b.v, b.lane, b.u = front.p + config.LEAD_MARGIN / 2, front.v, (front.lane + 2) % 4, float((front.lane + 2) % 4)
    step(m)
    assert pack.holder == holder  # not clear yet
    for b in race.bodies_of(other):
        b.p = front.p + 3 * config.LEAD_MARGIN
    events = step(m)
    assert pack.holder == other and "lead" in [e.kind for e in events]
    before = m.lead_time[other]
    for _ in range(30):
        step(m)
    assert m.lead_time[other] > before


def test_the_last_seconds_tick_and_first_to_the_target_wins_and_a_rematches_with_the_same_racers():
    m = fresh()
    to_race(m)
    keys = dict(m.racer_of)
    for _ in range(120):
        step(m)
    for p in m.players:  # whoever leads from here wins (P1 cruises along too, untouched)
        m.pack.lead_time[p] = m.target - 2.5
    events = []
    for _ in range(round(12 / DT)):  # the lead may change hands a few times on the way
        if m.state != RACE:
            break
        events += step(m)
    assert m.state == MATCH_END and m.winner == m.pack.holder and m.lead_time[m.winner] >= m.target
    assert [e.kind for e in events].count("tick") >= 2 and "match_won" in [e.kind for e in events]
    for _ in range(round(config.RESULT_LOCK / DT) + 1):
        step(m)
    step(m, confirm=True)
    assert m.state == COUNTDOWN and m.racer_of == keys and all(v == 0 for v in m.lead_time.values())


# --- pause and idle --------------------------------------------------------------------------------

def test_start_pauses_and_quit_to_title_leaves():
    m = fresh()
    to_race(m)
    step(m, pause=True)
    assert m.paused
    t = m.race.time
    step(m)
    assert m.race.time == t
    step(m, nav=(0, 1))
    step(m, pick=True)
    assert m.state == TITLE and not m.paused


def test_the_idle_timeout_reaches_the_title_even_paused():
    m = fresh()
    to_race(m)
    step(m, pause=True)
    for _ in range(round(config.IDLE_TIMEOUT / 0.5) + 1):
        m.update(0.5, FrameInput())
    assert m.state == TITLE


# --- QUIT on the title ------------------------------------------------------------------------------

def on_quit() -> Match:
    m = fresh()
    step(m, nav=(0, -1))  # up from the first row wraps round to the last
    assert MENU_ROWS[m.row] == "QUIT" and MENU_ROWS[-1] == "QUIT"
    return m


def test_a_on_quit_quits_at_once():
    m = on_quit()
    step(m, confirm=True, pick=True)
    assert m.quit and m.state == TITLE


def test_start_on_quit_still_starts_and_b_and_the_stick_never_quit():
    m = on_quit()
    before = (m.humans, m.bots, m.level, m.track_index, m.target)
    step(m, nav=(1, 0))
    step(m, back=True)
    assert not m.quit and (m.humans, m.bots, m.level, m.track_index, m.target) == before
    step(m, confirm=True, pause=True, pick=True)  # Start and A at once: Start wins
    assert not m.quit and m.state == SELECT


def test_a_on_any_other_row_goes_on():
    m = fresh()
    step(m, confirm=True, pick=True)
    assert not m.quit and m.state == SELECT


# --- the HOW TO PLAY card ---------------------------------------------------------------------------

def to_card(humans: int = 1) -> Match:
    m = to_select(humans)
    step(m, pause=True)
    assert m.state == TUTORIAL and m.tutorial is not None
    return m


def test_the_card_comes_between_the_select_and_the_countdown():
    m = to_card()
    for _ in range(round(10 / DT)):  # it waits however long it takes
        step(m)
    assert m.state == TUTORIAL and m.race.time == 0
    events = skip_card(m)
    assert m.tutorial is None and {"confirm", "beep"} <= {e.kind for e in events}


def test_presses_in_its_first_moment_and_the_stick_do_not_dismiss_it():
    m = to_card()
    step(m, any_button=True)
    assert m.state == TUTORIAL  # the press that started the match, or its bounce
    for _ in range(round(tutorial.LOCK / DT) + 1):
        step(m)
    step(m, nav=(1, 0), held={("stick", 0): frozenset({"up"})}, pressed={("stick", 0): frozenset({"up"})})
    assert m.state == TUTORIAL
    step(m, any_button=True)
    assert m.state == COUNTDOWN


def test_start_on_the_card_dismisses_it_and_does_not_pause():
    m = to_card()
    for _ in range(round(tutorial.LOCK / DT) + 1):
        step(m)
    step(m, any_button=True, pause=True, confirm=True)
    assert m.state == COUNTDOWN and not m.paused


def test_a_rematch_skips_the_card_but_a_new_match_after_quit_to_title_shows_it():
    m = fresh()
    to_race(m)
    m.pack.lead_time[m.race.players[0]] = m.target
    m.pack.holder = m.race.players[0]
    step(m)
    assert m.state == MATCH_END
    for _ in range(round(config.RESULT_LOCK / DT) + 1):
        step(m)
    step(m, confirm=True)
    assert m.state == COUNTDOWN
    step(m, pause=True)
    step(m, nav=(0, 1))
    step(m, pick=True)  # QUIT TO TITLE
    assert m.state == TITLE
    step(m, confirm=True)
    step(m, pause=True)
    assert m.state == TUTORIAL


def test_the_idle_timeout_reaches_the_title_from_the_card():
    m = to_card()
    for _ in range(round(config.IDLE_TIMEOUT / 0.5) + 1):
        m.update(0.5, FrameInput())
    assert m.state == TITLE and m.tutorial is None


@pytest.mark.parametrize("track_index", [0, 1, 2])
def test_the_demo_passes_and_takes_the_lead_on_every_track_and_loops(track_index):
    m = fresh()
    m.track_index = track_index
    step(m, confirm=True)
    step(m, pause=True)
    demo = m.tutorial
    assert demo.race.racer_keys["p1"] == m.racer_of["p1"]
    seen = []
    for _ in range(round((tutorial.LOOP - 0.1) / DT)):
        step(m)
        if demo.phase not in seen:
            seen.append(demo.phase)
    assert seen == ["draft", "pass", "lead"]
    assert demo.pack.lead_time["p1"] > 1.5  # long enough to see its seconds count
    for _ in range(round(0.2 / DT)):
        step(m)
    assert demo.phase == "draft" and demo.t < 0.2  # and over again


# --- the racer select through the real input path (a cabinet regression) ---------------------------

class FakePad:
    """A cabinet pad: raw buttons held, the stick centred."""

    def __init__(self) -> None:
        self.down: set[int] = set()

    def get_numbuttons(self) -> int:
        return 12

    def get_button(self, b: int) -> bool:
        return b in self.down

    def get_numaxes(self) -> int:
        return 2

    def get_axis(self, i: int) -> float:
        return 0.0

    def get_numhats(self) -> int:
        return 0


def press_raw(m: Match, inp, pads: list, pad: int, raw: int) -> None:
    """Press a raw button on one pad for a frame, then let go, through Input
    and FrameInput into the match, as on the cabinet."""
    for down in (True, False):
        if down:
            pads[pad].down.add(raw)
        else:
            pads[pad].down.discard(raw)
        inp.update(DT)
        m.update(DT, inp.frame_input())


@pytest.mark.parametrize("humans,pad", [(1, 0), (1, 1), (2, 0), (2, 1)])
def test_a_locks_in_the_racer_under_the_cursor_and_does_not_move_it(humans, pad):
    """On the cabinet, A (raw 1) is also "right" on the face buttons, which
    steer like W A S D in a race: in the select it moved the cursor one racer
    to the right before locking in, so you got the racer next to yours."""
    import pygame

    from qircuit.input import Input

    pygame.init()
    inp = Input()
    pads = [FakePad(), FakePad()]
    inp.joysticks = pads
    m = to_select(humans)
    player = "p1" if humans == 1 or pad == 0 else "p2"
    before = dict(m.picks)
    press_raw(m, inp, pads, pad, config.INPUT_CONFIG["system"]["confirm_buttons"][0])
    assert player in m.locked and m.picks == before
    press_raw(m, inp, pads, pad, config.INPUT_CONFIG["system"]["back_buttons"][0])  # B unlocks, nothing moves
    assert player not in m.locked and m.picks == before and m.state == SELECT
    for raw in config.INPUT_CONFIG["pads"][pad]["buttons"]["up"] + config.INPUT_CONFIG["pads"][pad]["buttons"]["left"]:
        press_raw(m, inp, pads, pad, raw)  # X and Y don't steer the cursor either: the stick does
    assert m.picks == before


def test_with_three_people_the_button_player_still_steers_with_the_buttons():
    import pygame

    from qircuit.input import Input

    pygame.init()
    inp = Input()
    pads = [FakePad(), FakePad()]
    inp.joysticks = pads
    m = to_select(3)
    p3 = m.picks["p3"]
    press_raw(m, inp, pads, 0, config.INPUT_CONFIG["pads"][0]["buttons"]["right"][0])  # A: P3's "right"
    from qircuit.match import SELECT_COLS

    n = len(racers.ROSTER)
    col = (p3 % SELECT_COLS + 1) % SELECT_COLS
    assert m.picks["p3"] == min(n - 1, (p3 // SELECT_COLS) * SELECT_COLS + col) and not m.locked
