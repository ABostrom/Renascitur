import gzip

import pytest

from renasci.core.calendar import Date
from renasci.io.runfolder import TABLES, RunFolder, cut, flush

from test_runfolder import CAL, Counter, Engine, Ruleset  # noqa: F401  (shared fixtures)


def engine():
    e = Engine(CAL, seed=1, rulesets=[(Date(1, 1, 0), Ruleset("c", 1, (Counter(),)))])
    e.cast("place", "t:world", {"count": 0})
    return e


def test_gzip_bytes_are_platform_independent(tmp_path):
    rf = RunFolder.create(tmp_path / "r", {})
    rf.write("events", [{"id": "x1"}])
    rf.close_segment()
    data = (tmp_path / "r" / "events" / "seg-00000.jsonl.gz").read_bytes()
    assert data[9] == 0xFF  # OS byte: "unknown", the same everywhere
    assert data[4:8] == b"\0\0\0\0"  # mtime 0


def test_rows_with_unicode_line_separators_survive(tmp_path):
    rf = RunFolder.create(tmp_path / "r", {})
    row = {"n": "a b\x85c d"}
    rf.write("events", [row])
    assert list(rf.read("events")) == [row]
    rf.close_segment()
    assert list(RunFolder.open(tmp_path / "r").read("events")) == [row]


def test_a_segment_in_both_forms_is_an_error_not_a_silent_choice(tmp_path):
    rf = RunFolder.create(tmp_path / "r", {})
    rf.write("events", [{"id": "x1"}])
    rf.close_segment()
    (tmp_path / "r" / "events" / "seg-00000.jsonl").write_text('{"id":"lost"}\n', encoding="utf-8")
    with pytest.raises(ValueError):
        list(rf.read("events"))


def test_open_recovers_from_a_close_interrupted_before_the_manifest(tmp_path):
    rf = RunFolder.create(tmp_path / "r", {})
    rf.write("events", [{"id": "x1"}])
    rf.write("hinges", [{"id": "h1"}])
    # simulate a crash: events gzipped, manifest not yet bumped, raw files still present
    raw = tmp_path / "r" / "events" / "seg-00000.jsonl"
    (tmp_path / "r" / "events" / "seg-00000.jsonl.gz").write_bytes(gzip.compress(raw.read_bytes()))
    again = RunFolder.open(tmp_path / "r")
    assert again.manifest["segments"] == 0
    assert [r["id"] for r in again.read("events")] == ["x1"]
    assert [r["id"] for r in again.read("hinges")] == ["h1"]


def test_open_finishes_a_close_interrupted_after_the_manifest(tmp_path):
    rf = RunFolder.create(tmp_path / "r", {})
    rf.write("events", [{"id": "x1"}])
    rf.close_segment()
    # simulate a leftover raw file whose gz and manifest bump already landed
    (tmp_path / "r" / "events" / "seg-00000.jsonl").write_text('{"id":"x1"}\n', encoding="utf-8")
    again = RunFolder.open(tmp_path / "r")
    assert [r["id"] for r in again.read("events")] == ["x1"]


def test_flush_keeps_the_engine_history_if_writing_fails(tmp_path):
    e = engine()
    e.run(until=Date(1, 1, 59))
    e.hinges.append({"bad": float("nan")})
    rf = RunFolder.create(tmp_path / "r", {})
    n = len(e.events)
    with pytest.raises((TypeError, ValueError)):
        flush(e, rf)
    assert len(e.events) == n
    assert list(rf.read("events")) == []


def test_entities_and_dropped_tables_are_written(tmp_path):
    assert "entities" in TABLES and "dropped" in TABLES
    e = engine()
    e.run(until=Date(1, 1, 0))
    rf = RunFolder.create(tmp_path / "r", {})
    flush(e, rf)
    ents = list(rf.read("entities"))
    assert ents == [{"id": "t:world", "kind": "place", "date": [1, 1, 0], "event": ents[0]["event"], "activation": ""}]
    assert e.dropped == []


def test_cut_flushes_then_closes_and_records_the_mark(tmp_path):
    e = engine()
    e.run(until=Date(1, 1, 59))
    rf = RunFolder.create(tmp_path / "r", {})
    index = cut(e, rf, at=Date(1, 1, 60))
    assert index == 0 and e.events == []
    assert rf.manifest["marks"] == [{"segment": 0, "before": [1, 1, 60]}]
    assert len(list(rf.read("events"))) == 3


def test_fork_copies_a_prefix_and_records_its_parent(tmp_path):
    rf = RunFolder.create(tmp_path / "a", {"seed": 1})
    for i in range(3):
        rf.write("events", [{"id": f"x{i}"}])
        rf.close_segment()
    child = RunFolder.fork(tmp_path / "a", tmp_path / "b", keep=2, meta={"ripple": "r1"})
    assert [r["id"] for r in child.read("events")] == ["x0", "x1"]
    assert child.manifest["parent"] == {"run": "a", "segments": 2}
    assert child.manifest["meta"] == {"ripple": "r1"}


def test_truncate_ignores_files_that_are_not_segments(tmp_path):
    rf = RunFolder.create(tmp_path / "r", {})
    rf.write("events", [{"id": "x0"}])
    rf.close_segment()
    (tmp_path / "r" / "events" / "desktop.ini").write_text("x", encoding="utf-8")
    rf.truncate(keep=0)
    assert (tmp_path / "r" / "events" / "desktop.ini").exists()
