"""SHORTER!'s answer is always the circuit with the fewest gates once identical
neighbours cancel (ties: the fewest as written), including the twist rounds,
where it is the one that looks longer."""

from planck_time.microgames.shorter import TWIST_FROM, Shorter


def written(circuit):
    return sum(len(w) for w in circuit)


def compiled(circuit):
    n = 0
    for wire in circuit:
        stack = []
        for kind, _redundant in wire:
            if stack and stack[-1] == kind:
                stack.pop()
            else:
                stack.append(kind)
        n += len(stack)
    return n


def test_the_answer_is_shortest_after_cancelling():
    for seed in range(200):
        for level in (0, 1, 2, 4):
            g = Shorter(seed, level, 4.0)
            a, d = g.circuits[g.short], g.circuits[1 - g.short]
            assert (compiled(a), written(a)) < (compiled(d), written(d)), (seed, level)


def test_twists_look_longer_but_compile_shorter_and_only_from_their_level():
    twists = 0
    for seed in range(200):
        assert not Shorter(seed, TWIST_FROM - 1, 4.0).twist
        g = Shorter(seed, TWIST_FROM, 4.0)
        if g.twist:
            twists += 1
            a, d = g.circuits[g.short], g.circuits[1 - g.short]
            assert written(a) > written(d) and compiled(a) < compiled(d)
    assert 50 < twists < 150
