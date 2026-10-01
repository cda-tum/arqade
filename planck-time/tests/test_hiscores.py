import json

from planck_time import config
from planck_time.hiscores import Hiscores


def test_an_empty_table_takes_any_positive_score():
    hs = Hiscores(None)
    assert hs.entries == []
    assert hs.qualifies(1) and not hs.qualifies(0)


def test_entries_stay_sorted_and_the_table_is_capped():
    hs = Hiscores(None)
    for i, score in enumerate([300, 100, 500, 200]):
        hs.add(f"P{i}", score, 1)
    assert [e.score for e in hs.entries] == [500, 300, 200, 100]
    for i in range(config.HISCORE_SLOTS):
        hs.add("ZZZ", 1000 + i, 2)
    assert len(hs.entries) == config.HISCORE_SLOTS
    assert not hs.qualifies(1000)  # the lowest entry is 1000 now
    assert hs.qualifies(1001)


def test_add_returns_the_rank_and_ties_go_below():
    hs = Hiscores(None)
    hs.add("AAA", 500, 1)
    assert hs.add("BBB", 500, 1) == 1
    assert hs.add("CCC", 900, 1) == 0


def test_scores_survive_a_reload_and_a_broken_file_is_ignored(tmp_path):
    path = tmp_path / "scores.json"
    hs = Hiscores(path)
    hs.add("QBT", 1234, 3)
    again = Hiscores(path)
    assert [(e.name, e.score, e.level) for e in again.entries] == [("QBT", 1234, 3)]
    path.write_text("not json")
    assert Hiscores(path).entries == []
    path.write_text(json.dumps([{"name": "X"}]))
    assert Hiscores(path).entries == []
