import random

from dataclasses import replace

from quantum_towers.player import PlayerState, apply_action, confirm_climb, knockback, new_player
from quantum_towers.quantum import State, states_equal, zero_state
from quantum_towers.search import minimum_steps
from quantum_towers.targets import generate_target_sequence


def _sequence(seed: int, count: int = 20) -> list[State]:
    return generate_target_sequence(random.Random(seed), count)


def test_new_player_starts_at_floor_zero_in_zero_state():
    player = new_player(_sequence(1))
    assert player.floor == 0
    assert states_equal(player.state, zero_state())
    assert player.press_count == 0
    assert player.charges == 0


def test_new_player_minimum_steps_matches_a_real_search():
    player = new_player(_sequence(2))
    expected = minimum_steps(zero_state(), player.current_target)
    assert player.minimum_steps_for_floor == expected


def test_new_player_with_shared_target_sequence_gives_identical_targets_to_both_players():
    # The whole point of a shared sequence: neither player's puzzles should
    # be randomly easier or harder than the other's.
    target_sequence = _sequence(42)
    p1 = new_player(target_sequence)
    p2 = new_player(target_sequence)
    assert p1.current_target == p2.current_target
    assert p1.next_target == p2.next_target


def test_apply_action_updates_state_and_increments_press_count():
    from quantum_towers.quantum import apply_x

    player = new_player(_sequence(3))
    result = apply_action(player, "X")
    assert states_equal(result.state, apply_x(player.state))
    assert result.press_count == player.press_count + 1
    assert result.floor == player.floor


def test_apply_action_never_advances_the_floor_even_when_it_matches_the_target():
    # Matching the target no longer auto-climbs -- confirm_climb (pushing
    # up) is required. A gate press alone, however lucky, must not advance.
    from quantum_towers.quantum import apply_x

    start = zero_state()
    target = apply_x(start)
    player = PlayerState(
        floor=0, state=start, current_target=target, next_target=zero_state(),
        press_count=0, minimum_steps_for_floor=1, charges=0,
    )
    result = apply_action(player, "X")
    assert states_equal(result.state, target)
    assert result.floor == 0
    assert result.current_target == target
    assert result.charges == 0


def test_confirm_climb_on_non_matching_state_returns_the_player_unchanged_and_fails():
    player = new_player(_sequence(4))
    result, advanced = confirm_climb(player, _sequence(4))
    assert advanced is False
    assert result == player


def test_confirm_climb_on_matching_state_advances_a_floor_and_succeeds():
    from quantum_towers.quantum import apply_x

    start = zero_state()
    target = apply_x(start)
    player = PlayerState(
        floor=0, state=target, current_target=target, next_target=zero_state(),
        press_count=1, minimum_steps_for_floor=1, charges=0,
    )
    result, advanced = confirm_climb(player, _sequence(5))
    assert advanced is True
    assert result.floor == 1
    assert result.press_count == 0  # reset for the new floor


def test_confirm_climb_awards_a_charge_when_solved_in_minimum_steps():
    from quantum_towers.quantum import apply_x

    start = zero_state()
    target = apply_x(start)
    player = PlayerState(
        floor=0, state=target, current_target=target, next_target=zero_state(),
        press_count=1, minimum_steps_for_floor=1, charges=0,
    )
    result, advanced = confirm_climb(player, _sequence(5))
    assert result.charges == 1


def test_confirm_climb_awards_no_charge_above_minimum_steps():
    from quantum_towers.quantum import apply_x

    start = zero_state()
    target = apply_x(start)
    player = PlayerState(
        floor=0, state=target, current_target=target, next_target=zero_state(),
        press_count=3,  # took 3 presses to eventually land here, not minimal
        minimum_steps_for_floor=1, charges=0,
    )
    result, advanced = confirm_climb(player, _sequence(5))
    assert result.floor == 1
    assert result.charges == 0


def test_confirm_climb_pulls_next_target_from_the_shared_sequence():
    from quantum_towers.quantum import apply_h, apply_x

    start = zero_state()
    target = apply_x(start)
    stale_next = apply_h(start)  # a real, reachable state -- just a placeholder here
    target_sequence = _sequence(7)
    player = PlayerState(
        floor=0, state=target, current_target=target, next_target=stale_next,
        press_count=1, minimum_steps_for_floor=1, charges=0,
    )
    result, advanced = confirm_climb(player, target_sequence)
    assert states_equal(result.current_target, stale_next)  # promoted
    assert result.next_target == target_sequence[2]  # new floor is 1 -> looked up index 2
    assert result.minimum_steps_for_floor == minimum_steps(result.state, result.current_target)


def test_confirm_climb_advancing_gives_identical_next_target_for_both_players_on_shared_sequence():
    from quantum_towers.quantum import apply_x

    target_sequence = _sequence(3)
    start = zero_state()
    target = apply_x(start)
    player = PlayerState(
        floor=0, state=start, current_target=target, next_target=zero_state(),
        press_count=0, minimum_steps_for_floor=1, charges=0,
    )
    r1, advanced1 = confirm_climb(apply_action(player, "X"), target_sequence)
    r2, advanced2 = confirm_climb(apply_action(player, "X"), target_sequence)
    assert advanced1 and advanced2
    assert r1.current_target == r2.current_target
    assert r1.next_target == r2.next_target


def test_knockback_drops_floor_by_the_given_amount():
    player = new_player(_sequence(11))
    player = replace(player, floor=10)
    result = knockback(player, floors=3, rng=random.Random(12))
    assert result.floor == 7


def test_knockback_never_drops_below_floor_zero():
    player = new_player(_sequence(13))
    player = replace(player, floor=2)
    result = knockback(player, floors=3, rng=random.Random(14))
    assert result.floor == 0


def test_knockback_keeps_the_players_qubit_state_unchanged():
    from quantum_towers.quantum import apply_h

    player = new_player(_sequence(15))
    messy_state = apply_h(player.state)
    player = replace(player, floor=5, state=messy_state)
    result = knockback(player, floors=3, rng=random.Random(16))
    assert result.state == messy_state


def test_knockback_generates_fresh_targets_and_resets_press_count():
    player = new_player(_sequence(17))
    player = replace(player, floor=5, press_count=2, minimum_steps_for_floor=99)
    result = knockback(player, floors=3, rng=random.Random(18))
    assert result.press_count == 0
    assert result.minimum_steps_for_floor == minimum_steps(result.state, result.current_target)


def test_knockback_leaves_charges_untouched():
    player = new_player(_sequence(19))
    player = replace(player, floor=5, charges=2)
    result = knockback(player, floors=3, rng=random.Random(20))
    assert result.charges == 2
