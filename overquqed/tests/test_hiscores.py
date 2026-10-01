from overquqed import hiscores


def test_missing_or_corrupt_file_is_an_empty_table(tmp_path):
    assert hiscores.load(tmp_path / "nope.json") == {}
    bad = tmp_path / "bad.json"
    bad.write_text("{not json")
    assert hiscores.load(bad) == {}


def test_insert_keeps_top_five_sorted_and_reports_rank(tmp_path):
    data = {}
    for i, score in enumerate([50, 80, 20, 90, 70]):
        hiscores.insert(data, "lv", f"T{i}", score, 1)
    assert [r["score"] for r in hiscores.table(data, "lv")] == [90, 80, 70, 50, 20]
    assert not hiscores.qualifies(data, "lv", 10)
    assert hiscores.qualifies(data, "lv", 60)
    assert hiscores.insert(data, "lv", "NEW", 60, 2) == 3
    assert [r["score"] for r in hiscores.table(data, "lv")] == [90, 80, 70, 60, 50]


def test_equal_scores_rank_below_the_older_entry():
    data = {}
    hiscores.insert(data, "lv", "OLD", 50, 1)
    assert hiscores.insert(data, "lv", "OLD", 50, 1) == 1


def test_best_stars_only_go_up_and_zero_scores_do_not_qualify():
    data = {}
    assert hiscores.insert(data, "lv", "AAA", 0, 3) == -1
    hiscores.insert(data, "lv", "BBB", 10, 1)
    assert hiscores.best_stars(data, "lv") == 3


def test_round_trip_through_the_file(tmp_path):
    path = tmp_path / "s.json"
    data = {}
    hiscores.insert(data, "lv", "abc", 42, 2)
    hiscores.save(path, data)
    back = hiscores.load(path)
    assert hiscores.table(back, "lv") == [{"name": "ABC", "score": 42}]
