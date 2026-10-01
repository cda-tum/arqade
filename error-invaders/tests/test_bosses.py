import random

from error_invaders import bosses
from error_invaders.game import Obj, pauli_hit


def test_a_boss_every_third_wave_cycling_through_all_five():
    fights = [bosses.boss_for_wave(n, "easy") for n in range(1, 31)]
    assert [f is not None for f in fights[:6]] == [False, False, True, False, False, True]
    kinds = [f[0] for f in fights if f]
    assert kinds == bosses.ORDER * 2
    assert [f[1] for f in fights if f] == [0] * 5 + [1] * 5
    assert bosses.boss_for_wave(3, "hard") == bosses.boss_for_wave(3, "easy")


def test_boss_rush_is_all_bosses():
    assert [bosses.boss_for_wave(n, "rush") for n in range(1, 7)] == \
        [(k, 0) for k in bosses.ORDER] + [(bosses.ORDER[0], 1)]


def test_pauli_hit_follows_the_game_rules():
    assert pauli_hit("X", "X", False) == ("kill", None)
    assert pauli_hit("Z", "all", True) == ("kill", None)
    assert pauli_hit("X", "Z", False) == ("block", None)
    assert pauli_hit("Y", "X", False) == ("convert", "Z")
    assert pauli_hit("Y", "Z", False) == ("convert", "X")
    assert pauli_hit("X", "Z", True) == ("convert", "Y")
    assert pauli_hit("Z", "Y", True) == ("convert", "X")


def test_every_single_error_has_its_own_syndrome():
    qubits = bosses.lattice_qubits()
    syndromes = [q[2] for q in qubits]
    assert len(set(syndromes)) == len(syndromes)
    for x, y, checks in qubits:
        assert len(checks) in (1, 2)
        if len(checks) == 1:   # only the left and right boundaries
            (c, r), = checks
            assert c in (0, bosses.PC - 1)


def test_splitting_the_chain_keeps_every_segment_in_place():
    random.seed(1)
    K = bosses.K
    n = 8
    # a path that runs right, then down a bit (mid-descent at the head)
    path = [(300 - k * bosses.STEP, bosses.C_TOP) for k in range(n * K + 1)]
    path = [(300, bosses.C_TOP + 9), (300, bosses.C_TOP + 6), (300, bosses.C_TOP + 3)] + path
    path = path[:(n - 1) * K + 1]
    ch = Obj(segs=[Obj(col="X", i=i) for i in range(n)], path=path, dir=1, down=30.0)
    pos = {s.i: path[i * K] for i, s in enumerate(ch.segs)}
    for cut in (0, 3, n - 1):
        parts = bosses.split_chain(ch, cut)
        seen = {}
        for p in parts:
            for i, s in enumerate(p.segs):
                seen[s.i] = p.path[i * K]
        assert seen == {i: v for i, v in pos.items() if i != cut}
    back = bosses.split_chain(ch, 0)[0]
    assert back.dir == 1 and back.down == 0     # its head is on a row, moving right
