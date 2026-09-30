import random

from quantum_towers.quantum import states_equal, zero_state
from quantum_towers.targets import generate_target, generate_target_sequence


def test_generate_target_never_returns_a_no_op():
    rng = random.Random(1)
    previous = zero_state()
    for _ in range(200):
        target = generate_target(rng, previous)
        assert not states_equal(target, previous)
        previous = target


def test_generate_target_is_deterministic_given_a_seeded_rng():
    target_a = generate_target(random.Random(42), zero_state())
    target_b = generate_target(random.Random(42), zero_state())
    assert states_equal(target_a, target_b)


def test_generate_target_produces_variety():
    rng = random.Random(2)
    previous = zero_state()
    seen = set()
    for _ in range(50):
        target = generate_target(rng, previous)
        # Round to dedupe near-identical floats into "the same state" buckets.
        key = (round(target.a0.real, 3), round(target.a0.imag, 3), round(target.a1.real, 3), round(target.a1.imag, 3))
        seen.add(key)
        previous = target
    assert len(seen) > 3


def test_generate_target_sequence_has_the_requested_length():
    sequence = generate_target_sequence(random.Random(5), 10)
    assert len(sequence) == 10


def test_generate_target_sequence_each_entry_reachable_from_the_previous():
    sequence = generate_target_sequence(random.Random(6), 10)
    previous = zero_state()
    for target in sequence:
        assert not states_equal(target, previous)
        previous = target


def test_generate_target_sequence_is_deterministic_given_a_seeded_rng():
    sequence_a = generate_target_sequence(random.Random(7), 10)
    sequence_b = generate_target_sequence(random.Random(7), 10)
    for a, b in zip(sequence_a, sequence_b):
        assert states_equal(a, b)
