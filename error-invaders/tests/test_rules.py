from error_invaders.game import PAULI


def test_pauli_product_of_two_different_errors_is_the_third():
    for a, b in (("X", "Z"), ("X", "Y"), ("Y", "Z")):
        (third,) = {"X", "Y", "Z"} - {a, b}
        assert PAULI[a + b] == third
        assert PAULI[b + a] == third
