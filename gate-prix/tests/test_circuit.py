import math
import random

import pytest

from gate_prix import circuit
from gate_prix.circuit import GATES, Circuit

S = 1 / math.sqrt(2)


def close(a, b, tol=1e-9):
    return abs(a - b) < tol


def same_state(a, b):
    """Equal up to a global phase."""
    overlap = a[0].conjugate() * b[0] + a[1].conjugate() * b[1]
    return close(abs(overlap), 1.0)


def test_gates_are_the_four_paulis_and_h():
    assert set(GATES) == {"H", "X", "Y", "Z"}


def test_h_on_zero_is_plus():
    a, b = circuit.apply((1 + 0j, 0j), "H")
    assert close(a.real, S) and close(b.real, S)
    assert close(a.imag, 0) and close(b.imag, 0)


def test_y_on_zero_is_i_one():
    a, b = circuit.apply((1 + 0j, 0j), "Y")
    assert close(abs(a), 0)
    assert close(b.real, 0) and close(b.imag, 1)


def test_x_on_zero_is_one_and_z_leaves_zero():
    assert same_state(circuit.apply((1 + 0j, 0j), "X"), (0j, 1 + 0j))
    assert same_state(circuit.apply((1 + 0j, 0j), "Z"), (1 + 0j, 0j))


def test_z_on_plus_is_minus():
    plus = (S + 0j, S + 0j)
    a, b = circuit.apply(plus, "Z")
    assert close(a.real, S) and close(b.real, -S)


@pytest.mark.parametrize("gate", GATES)
@pytest.mark.parametrize("start", [(1 + 0j, 0j), (0j, 1 + 0j), (S + 0j, S * 1j), (0.6 + 0j, 0.8j)])
def test_every_gate_is_its_own_inverse(gate, start):
    twice = circuit.apply(circuit.apply(start, gate), gate)
    assert same_state(twice, start)


@pytest.mark.parametrize("gate", GATES)
def test_gates_keep_the_state_normalised(gate):
    a, b = circuit.apply((0.6 + 0j, 0.8j), gate)
    assert close(abs(a) ** 2 + abs(b) ** 2, 1.0)


def test_run_empty_is_zero():
    assert circuit.run([]) == (1 + 0j, 0j)


def test_run_applies_in_order_and_treats_none_as_identity():
    assert same_state(circuit.run(["H", "Z", "H"]), (0j, 1 + 0j))  # HZH = X
    assert same_state(circuit.run(["H", None, "Z", None, "H"]), (0j, 1 + 0j))
    assert same_state(circuit.run([None, None]), (1 + 0j, 0j))


def test_bloch_of_zero_is_plus_z():
    x, y, z = circuit.bloch((1 + 0j, 0j))
    assert close(x, 0) and close(y, 0) and close(z, 1)


def test_bloch_of_one_is_minus_z():
    assert close(circuit.bloch((0j, 1 + 0j))[2], -1)


def test_bloch_of_plus_is_plus_x():
    x, y, z = circuit.bloch(circuit.run(["H"]))
    assert close(x, 1) and close(y, 0) and close(z, 0)


def test_bloch_of_plus_i_is_plus_y():
    x, y, z = circuit.bloch((S + 0j, S * 1j))
    assert close(x, 0) and close(y, 1) and close(z, 0)


def test_bloch_ignores_global_phase():
    a = circuit.bloch(circuit.run(["Y"]))
    b = circuit.bloch((0j, 1 + 0j))
    assert all(close(p, q) for p, q in zip(a, b))


def test_random_target_has_the_right_length_and_alphabet():
    target = circuit.random_target(random.Random(1), 24)
    assert len(target) == 24
    assert set(target) <= set(GATES)


def test_random_target_never_repeats_a_gate_in_a_row():
    for seed in range(1000):
        target = circuit.random_target(random.Random(seed), 24)
        assert all(a != b for a, b in zip(target, target[1:])), seed


def test_random_target_uses_every_gate_across_seeds():
    seen = set()
    for seed in range(50):
        seen.update(circuit.random_target(random.Random(seed), 24))
    assert seen == set(GATES)


def test_random_target_is_deterministic_for_a_seed():
    assert circuit.random_target(random.Random(7), 24) == circuit.random_target(random.Random(7), 24)


def test_hamming_counts_differences_and_empties():
    target = ["H", "X", "Y", "Z"]
    assert circuit.hamming(["H", "X", "Y", "Z"], target, 4) == 0
    assert circuit.hamming(["H", "Z", "Y", "X"], target, 4) == 2
    assert circuit.hamming(["H", None, "Y", "Z"], target, 4) == 1  # empty differs
    assert circuit.hamming([None, None, None, None], target, 4) == 4


def test_hamming_looks_only_at_the_first_upto_slots():
    target = ["H", "X", "Y", "Z"]
    assert circuit.hamming(["H", "X", "X", "X"], target, 2) == 0
    assert circuit.hamming(["H", "Z", "X", "X"], target, 2) == 1


def test_hamming_counts_slots_not_yet_filled_as_empty():
    target = ["H", "X", "Y", "Z"]
    assert circuit.hamming(["H"], target, 4) == 3


def test_a_fresh_circuit_is_empty():
    c = Circuit(["H", "X", "Y"])
    assert c.target == ["H", "X", "Y"]
    assert c.slots == [None, None, None]
    assert c.streak == 0
    assert c.results == [None, None, None]


def test_take_right_gate_returns_true_and_grows_the_streak():
    c = Circuit(["H", "X", "Y"])
    assert c.take(0, "H") is True
    assert c.streak == 1
    assert c.take(1, "X") is True
    assert c.streak == 2
    assert c.slots[:2] == ["H", "X"]
    assert c.results[:2] == [True, True]


def test_take_wrong_gate_returns_false_records_it_and_resets_the_streak():
    c = Circuit(["H", "X", "Y"])
    c.take(0, "H")
    assert c.take(1, "Z") is False
    assert c.streak == 0
    assert c.slots[1] == "Z"
    assert c.results[1] is False
    assert c.take(2, "Y") is True
    assert c.streak == 1  # starts again from zero


def test_take_none_is_a_missed_row_wrong_and_resets_the_streak():
    c = Circuit(["H", "X", "Y"])
    c.take(0, "H")
    assert c.take(1, None) is False
    assert c.slots[1] is None
    assert c.results[1] is False
    assert c.streak == 0


def test_taking_a_filled_slot_again_is_a_programming_error():
    c = Circuit(["H", "X", "Y"])
    c.take(0, "H")
    with pytest.raises(ValueError):
        c.take(0, "H")


def test_a_missed_row_also_counts_as_filled():
    c = Circuit(["H", "X", "Y"])
    c.take(0, None)
    with pytest.raises(ValueError):
        c.take(0, "H")


def test_slots_must_be_filled_in_order():
    c = Circuit(["H", "X", "Y"])
    with pytest.raises(ValueError):
        c.take(1, "X")
    c.take(0, "H")
    with pytest.raises(ValueError):
        c.take(2, "Y")


def test_taking_past_the_end_is_an_error():
    c = Circuit(["H"])
    c.take(0, "H")
    with pytest.raises(ValueError):
        c.take(1, "X")


def test_qec_with_nothing_filled_returns_none():
    assert Circuit(["H", "X"]).qec() is None


def test_qec_with_no_mistake_returns_none():
    c = Circuit(["H", "X", "Y"])
    c.take(0, "H")
    c.take(1, "X")
    assert c.qec() is None


def test_qec_repairs_the_most_recent_wrong_slot():
    c = Circuit(["H", "X", "Y", "Z"])
    c.take(0, "Z")  # wrong
    c.take(1, "Y")  # wrong
    c.take(2, "Y")  # right
    assert c.qec() == 1
    assert c.slots[1] == "X"
    assert c.results[1] is True
    assert c.qec() == 0  # then the earlier one
    assert c.slots[0] == "H"
    assert c.qec() is None


def test_qec_repairs_an_empty_slot():
    c = Circuit(["H", "X", "Y"])
    c.take(0, "H")
    c.take(1, None)
    assert c.qec() == 1
    assert c.slots[1] == "X"
    assert c.results[1] is True


def test_qec_ignores_slots_not_yet_filled():
    c = Circuit(["H", "X", "Y"])
    c.take(0, "H")
    assert c.qec() is None
    assert c.slots == ["H", None, None]


def test_qec_does_not_touch_the_streak():
    c = Circuit(["H", "X", "Y"])
    c.take(0, "Z")
    c.take(1, "X")
    assert c.streak == 1
    c.qec()
    assert c.streak == 1
    c.take(2, "Y")
    assert c.streak == 2


def test_qec_fixes_the_circuits_hamming_distance():
    target = ["H", "X", "Y", "Z"]
    c = Circuit(target)
    c.take(0, "H")
    c.take(1, "H")
    assert circuit.hamming(c.slots, target, 4) == 3  # one wrong, two unfilled
    c.qec()
    assert circuit.hamming(c.slots, target, 2) == 0
