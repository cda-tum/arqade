import random
import time

from quantum_towers import config
from quantum_towers.quantum import states_equal, zero_state
from quantum_towers.solo import Timer, equal_difficulty_tower, minimum_total

FLOORS = config.TOWER_HEIGHT
EXTRA = 2


def test_every_tower_has_exactly_the_pinned_minimum_total():
    for seed in range(200):
        tower = equal_difficulty_tower(random.Random(seed), FLOORS, config.SOLO_TOTAL_PRESSES)
        assert len(tower) == FLOORS + EXTRA
        assert minimum_total(tower[:FLOORS]) == config.SOLO_TOTAL_PRESSES


def test_no_target_repeats_its_predecessor():
    for seed in range(50):
        tower = equal_difficulty_tower(random.Random(seed), FLOORS, config.SOLO_TOTAL_PRESSES)
        previous = zero_state()
        for target in tower:
            assert not states_equal(target, previous)
            previous = target


def test_the_same_seed_gives_the_same_tower():
    a = equal_difficulty_tower(random.Random(7), FLOORS, config.SOLO_TOTAL_PRESSES)
    b = equal_difficulty_tower(random.Random(7), FLOORS, config.SOLO_TOTAL_PRESSES)
    assert a == b
    c = equal_difficulty_tower(random.Random(8), FLOORS, config.SOLO_TOTAL_PRESSES)
    assert a != c


def test_minimum_total_of_nothing_is_zero_and_counts_the_first_floor_from_zero():
    assert minimum_total([]) == 0
    tower = equal_difficulty_tower(random.Random(3), 4, 8)
    assert minimum_total(tower[:4]) == 8


def test_generation_is_fast():
    start = time.perf_counter()
    for seed in range(50):
        equal_difficulty_tower(random.Random(seed), FLOORS, config.SOLO_TOTAL_PRESSES)
    assert time.perf_counter() - start < 2.0


def test_the_timer_formats_minutes_seconds_and_hundredths():
    t = Timer()
    t.update(7.25)
    assert t.format() == "0:07.25"
    t = Timer()
    t.update(63.0)
    assert t.format() == "1:03.00"
    assert Timer().format() == "0:00.00"


def test_the_timer_freezes_while_paused():
    t = Timer()
    t.update(2.0)
    t.paused = True
    t.update(5.0)
    assert t.seconds == 2.0
    t.paused = False
    t.update(1.5)
    assert t.seconds == 3.5
