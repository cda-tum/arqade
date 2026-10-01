import random

from gate_drop import config, levels


def test_the_error_count_grows_each_round_to_a_cap():
    assert [levels.errors_for_round(n) for n in (1, 2, 3, 5, 9)] == [4, 6, 8, 12, 12]


def test_layouts_fit_the_rules():
    for seed in range(50):
        count = 4 + seed % 9
        layout = levels.error_layout(random.Random(seed), count)
        assert len(layout) == count and len({pos for pos, _ in layout}) == count
        for (x, y), kind in layout:
            assert 0 <= x < config.COLS
            assert config.ROWS - config.ERROR_ROWS <= y < config.ROWS
            assert kind in config.PAULIS
        for x in range(config.COLS):
            wire = [kind for (cx, _y), kind in sorted(layout, key=lambda e: -e[0][1]) if cx == x]
            assert all(a != b for a, b in zip(wire, wire[1:])), wire


def test_the_same_seed_gives_the_same_layout():
    assert levels.error_layout(random.Random(3), 8) == levels.error_layout(random.Random(3), 8)
