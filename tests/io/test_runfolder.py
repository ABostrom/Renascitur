import gzip
import json

import pytest

from renasci.core.calendar import Age, Calendar, Date
from renasci.core.engine import Engine
from renasci.core.events import EventType
from renasci.core.systems import Ruleset, System
from renasci.io.runfolder import TABLES, RunFolder, flush


def test_create_writes_a_manifest_and_refuses_to_overwrite(tmp_path):
    rf = RunFolder.create(tmp_path / "r1", {"seed": 1})
    m = json.loads((tmp_path / "r1" / "manifest.json").read_text(encoding="utf-8"))
    assert m["format"] == 1 and m["meta"] == {"seed": 1} and m["segments"] == 0
    assert set(m["tables"]) == set(TABLES)
    with pytest.raises(FileExistsError):
        RunFolder.create(tmp_path / "r1", {})
    assert rf.path == tmp_path / "r1"


def test_rows_round_trip_in_order_across_segments(tmp_path):
    rf = RunFolder.create(tmp_path / "r", {})
    rf.write("events", [{"id": "x1"}, {"id": "x2"}])
    rf.close_segment()
    rf.write("events", [{"id": "x3"}])
    assert [r["id"] for r in rf.read("events")] == ["x1", "x2", "x3"]
    again = RunFolder.open(tmp_path / "r")
    assert [r["id"] for r in again.read("events")] == ["x1", "x2", "x3"]


def test_closed_segments_are_gzipped_and_every_line_is_canonical_json(tmp_path):
    rf = RunFolder.create(tmp_path / "r", {})
    rf.write("events", [{"b": 1, "a": [1.5, None]}])
    rf.close_segment()
    gz = tmp_path / "r" / "events" / "seg-00000.jsonl.gz"
    assert gz.exists() and not (tmp_path / "r" / "events" / "seg-00000.jsonl").exists()
    line = gzip.decompress(gz.read_bytes()).decode("utf-8").splitlines()[0]
    assert line == '{"a":[1.5,null],"b":1}'


def test_unknown_tables_and_non_json_rows_are_rejected(tmp_path):
    rf = RunFolder.create(tmp_path / "r", {})
    with pytest.raises(ValueError):
        rf.write("gossip", [{}])
    with pytest.raises((TypeError, ValueError)):
        rf.write("events", [{"x": float("nan")}])


def test_truncate_drops_later_segments(tmp_path):
    rf = RunFolder.create(tmp_path / "r", {})
    for i in range(3):
        rf.write("events", [{"id": f"x{i}"}])
        rf.close_segment()
    rf.write("events", [{"id": "open"}])
    rf.truncate(keep=2)
    assert [r["id"] for r in rf.read("events")] == ["x0", "x1"]
    assert rf.manifest["segments"] == 2
    rf.write("events", [{"id": "x2b"}])
    assert [r["id"] for r in RunFolder.open(tmp_path / "r").read("events")] == ["x0", "x1", "x2b"]


def test_identical_writes_give_identical_bytes(tmp_path):
    for name in ("a", "b"):
        rf = RunFolder.create(tmp_path / name, {"seed": 3})
        rf.write("events", [{"id": "x1", "v": 0.1}])
        rf.close_segment()
    for rel in ("manifest.json", "events/seg-00000.jsonl.gz"):
        assert (tmp_path / "a" / rel).read_bytes() == (tmp_path / "b" / rel).read_bytes()


# ---------------------------------------------------------------- flushing an engine

CAL = Calendar(ages=(Age(1, "1X", "Toy Age", last_year=50),))
TICK = EventType("toy.tick", 1, roles={"subject": (1, 1)}, payload={"n": "int"})


class Counter(System):
    name, cadence = "toy.counter", "monthly"
    reads, writes = frozenset({"count"}), frozenset({"count"})
    event_types = (TICK,)

    def run(self, ctx):
        n = ctx.get("t:world", "count") + 1
        ctx.chance(0.5, "flip", owner="t:world", stakes=0.1)
        ctx.emit("toy.tick", {"subject": ("t:world",)}, payload={"n": n}, purpose="tick", actor="t:world")
        ctx.set("t:world", "count", n)


def test_flush_moves_engine_history_into_tables(tmp_path):
    e = Engine(CAL, seed=1, rulesets=[(Date(1, 1, 0), Ruleset("c", 1, (Counter(),)))])
    e.cast("place", "t:world", {"count": 0})
    e.hinge_margin = 1.0
    e.run(until=Date(1, 1, 359))
    n_events = len(e.events)
    rf = RunFolder.create(tmp_path / "r", {})
    flush(e, rf)
    assert e.events == [] and e.store.deltas == [] and e.hinges == [] and e.reads == []
    events = list(rf.read("events"))
    assert len(events) == n_events == 13  # cast + 12 ticks
    assert sum(1 for _ in rf.read("participants")) == 13
    assert any(r["entity"] == "t:world" and r["field"] == "count" for r in rf.read("state_deltas"))
    assert len(list(rf.read("hinges"))) == 12
    assert all(set(r) == {"event", "kind", "ref"} for r in rf.read("causes"))
    assert e.causes.has(events[-1]["id"])  # the index is state, not history: it stays
