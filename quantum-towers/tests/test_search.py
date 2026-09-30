from quantum_towers.quantum import ACTIONS, State, apply_h, apply_t, apply_x, apply_y, apply_z, states_equal, zero_state
from quantum_towers.search import minimum_steps

_MINUS = apply_z(apply_h(zero_state()))  # |-> -- no single gate reaches it from |0>

_PLUS = apply_h(zero_state())


def test_minimum_steps_is_zero_when_already_at_target():
    start = zero_state()
    assert minimum_steps(start, start) == 0


def test_minimum_steps_is_one_for_a_single_gate_away():
    start = zero_state()
    target = apply_x(start)
    assert minimum_steps(start, target) == 1


def test_minimum_steps_finds_a_shortcut_not_just_the_generating_sequence():
    # A target built by the 3-gate walk X, Y, X (from |0>, no step a no-op)
    # is really just 2 steps away -- Y then Z lands on the exact same state
    # (-i|1>) -- even though "how it was generated" took 3 gates. The search
    # must find the real shortcut, not assume the generating walk's length
    # is optimal.
    zero = zero_state()
    target = apply_x(apply_y(apply_x(zero)))
    assert states_equal(target, apply_z(apply_y(zero)))  # sanity-check the shortcut claim itself
    assert minimum_steps(zero, target) == 2


def test_minimum_steps_for_a_two_gate_clifford_sequence():
    start = zero_state()
    assert minimum_steps(start, _MINUS) == 2


def test_minimum_steps_returns_none_when_capped_below_the_true_distance():
    start = zero_state()
    assert minimum_steps(start, _MINUS, max_depth=1) is None  # really 2 steps away


def test_minimum_steps_returns_none_for_a_state_outside_the_reachable_gate_set():
    # T is not one of the playable ACTIONS (search.py excludes it -- see
    # quantum.py), so a state that genuinely requires it is unreachable at
    # any depth, not just capped by max_depth.
    start = zero_state()
    target = apply_t(apply_h(start))
    assert minimum_steps(start, target) is None


def test_minimum_steps_returns_none_for_y_eigenstates():
    # |+i>/|-i> need a phase gate like S to reach from the other 4 cardinal
    # directions -- S was tried and removed (see quantum.py), so these stay
    # unreachable.
    start = zero_state()
    plus_i = State(1 / 2**0.5 + 0j, 1j / 2**0.5)
    assert minimum_steps(start, plus_i) is None


def test_minimum_steps_reaches_an_imaginary_phase_state_via_y():
    # Y(|0>) = i|1>, a genuinely different (and reachable) target from
    # X(|0>) = |1> now that global phase counts -- this is the concrete
    # target-level payoff of exact state equality.
    start = zero_state()
    target = apply_y(start)
    assert minimum_steps(start, target) == 1


def test_i_phase_states_are_unreachable_without_y():
    # The rigorous version of the claim above: with Y excluded entirely,
    # i|1> is not reachable at ANY depth, not just capped -- X, Z, H, and
    # RESET are all real-valued, so only Y can ever introduce an imaginary
    # component at all.
    gates_without_y = {name: fn for name, fn in ACTIONS.items() if name != "Y"}
    start = zero_state()
    target = State(0 + 0j, 1j)  # i|1>

    visited = [start]
    frontier = [start]
    for _ in range(6):
        next_frontier = []
        for state in frontier:
            for fn in gates_without_y.values():
                new_state = fn(state)
                assert not states_equal(new_state, target)
                if not any(states_equal(new_state, v) for v in visited):
                    visited.append(new_state)
                    next_frontier.append(new_state)
        frontier = next_frontier


def test_minimum_steps_reset_counts_as_a_single_step_from_anywhere():
    start = apply_h(apply_t(apply_h(zero_state())))  # some messy state
    target = zero_state()
    assert minimum_steps(start, target) == 1
