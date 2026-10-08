from error_invaders.game import PAULI


def test_pauli_product_of_two_different_errors_is_the_third():
    for a, b in (("X", "Z"), ("X", "Y"), ("Y", "Z")):
        (third,) = {"X", "Y", "Z"} - {a, b}
        assert PAULI[a + b] == third
        assert PAULI[b + a] == third


def test_a_ship_lost_with_no_lives_left_comes_back_next_wave():
    from error_invaders import game

    game.new_game(True)
    p1, p2 = game.g.players
    game.g.lives = 0
    p2.inv = 0  # past the spawn shield
    game.kill_player(p2)
    assert p2.out and not p2.alive and not p1.out
    assert not game.g.overDelay  # P1 plays on alone

    game.next_wave()
    assert not p2.out and p2.alive and p2.x == p2.homeX
    assert p2.inv > 0  # comes back safe for a moment
    assert game.g.lives == 0  # but with no lives to spare


def test_a_new_wave_leaves_both_ships_alone_when_nobody_is_out():
    from error_invaders import game

    game.new_game(True)
    p1, p2 = game.g.players
    p2.x = 100
    game.next_wave()
    assert p2.x == 100 and not p1.out and not p2.out
