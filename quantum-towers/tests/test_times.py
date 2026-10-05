import json

from quantum_towers import config, times
from quantum_towers.times import Times


def test_an_empty_table_takes_any_positive_time():
    t = Times(None)
    assert t.entries == []
    assert t.qualifies(99.0) and not t.qualifies(0)


def test_entries_sort_fastest_first_and_the_table_is_capped():
    t = Times(None)
    for i, seconds in enumerate([30.0, 10.0, 50.0, 20.0]):
        t.add(f"P{i}", seconds)
    assert [e.seconds for e in t.entries] == [10.0, 20.0, 30.0, 50.0]
    for i in range(config.TIMES_SLOTS):
        t.add("ZZZ", 5.0 + i)
    assert len(t.entries) == config.TIMES_SLOTS
    assert [e.seconds for e in t.entries][-1] == 13.0  # the earlier 10.0 is still in
    assert not t.qualifies(13.0)
    assert t.qualifies(12.9)


def test_add_returns_the_rank_and_ties_go_below():
    t = Times(None)
    t.add("AAA", 20.0)
    assert t.add("BBB", 20.0) == 1
    assert t.add("CCC", 12.0) == 0


def test_a_full_table_rejects_a_slower_time():
    t = Times(None)
    for i in range(config.TIMES_SLOTS):
        t.add("AAA", 10.0 + i)
    assert t.add("BBB", 99.0) == -1
    assert len(t.entries) == config.TIMES_SLOTS


def test_a_missing_or_broken_file_gives_an_empty_table(tmp_path):
    assert Times(tmp_path / "nope.json").entries == []
    bad = tmp_path / "bad.json"
    bad.write_text("{not json")
    assert Times(bad).entries == []
    wrong = tmp_path / "wrong.json"
    wrong.write_text('[{"name": "AAA"}]')
    assert Times(wrong).entries == []


def test_a_save_then_load_round_trips(tmp_path):
    path = tmp_path / "times.json"
    t = Times(path)
    t.add("AAA", 41.25)
    t.add("BBB", 38.5)
    again = Times(path)
    assert [(e.name, e.seconds) for e in again.entries] == [("BBB", 38.5), ("AAA", 41.25)]


def test_format_time_matches_the_timer():
    assert Times.format_time(7.25) == "0:07.25"
    assert Times(None).format_time(63.0) == "1:03.00"


def test_loading_drops_times_that_are_not_finite_and_positive(tmp_path):
    path = tmp_path / "times.json"
    path.write_text(
        '[{"name": "NAN", "seconds": NaN}, {"name": "INF", "seconds": Infinity},'
        ' {"name": "NEG", "seconds": -3.0}, {"name": "ZER", "seconds": 0},'
        ' {"name": "OK!", "seconds": 12.5}]'
    )
    assert [(e.name, e.seconds) for e in Times(path).entries] == [("OK!", 12.5)]


def test_loading_an_unsorted_oversized_file_sorts_and_truncates(tmp_path):
    path = tmp_path / "times.json"
    seconds = [float(s) for s in (14, 3, 9, 11, 1, 7, 13, 2, 12, 5, 8, 4, 10, 6)]
    path.write_text(json.dumps([{"name": f"P{i:02d}", "seconds": s} for i, s in enumerate(seconds)]))
    entries = Times(path).entries
    assert [e.seconds for e in entries] == [float(s) for s in range(1, config.TIMES_SLOTS + 1)]


def test_a_failing_save_is_ignored(tmp_path):
    path = tmp_path / "missing-dir" / "times.json"  # the directory does not exist
    t = Times(path)
    assert t.add("AAA", 20.0) == 0
    assert [e.name for e in t.entries] == ["AAA"]
    assert not path.exists()


def test_the_save_is_atomic(tmp_path, monkeypatch):
    path = tmp_path / "times.json"
    t = Times(path)
    t.add("AAA", 20.0)
    before = path.read_text()

    def broken_replace(_src, _dst):
        raise OSError("disk full")

    monkeypatch.setattr(times.os, "replace", broken_replace)
    t.add("BBB", 10.0)
    assert path.read_text() == before  # the old table is untouched
    assert sorted(p.name for p in tmp_path.iterdir()) == ["times.json"]  # no temp file left
