import json
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "helpers"))

from mini_world import CAL, RULESETS, SEED, VILLAGES, new_engine  # noqa: E402

from renasci.core.calendar import Date  # noqa: E402
from renasci.core.canon import digest  # noqa: E402
from renasci.core.engine import Engine  # noqa: E402
from renasci.io.checkpoint import load_checkpoint, save_checkpoint  # noqa: E402

END = Date(1, 30, 359)
CHILD = Path(__file__).parent.parent / "helpers" / "replay_child.py"


@pytest.fixture(scope="module")
def continuous():
    e = new_engine()
    e.run(until=END)
    rows = e.pending()
    return {"events": rows["events"], "hinges": rows["hinges"], "state_hash": e.state_hash()}


def test_the_mini_world_is_lively(continuous):
    types = [ev["type"] for ev in continuous["events"]]
    for t in ("mini.birth", "mini.death", "mini.harvest", "mini.feast"):
        assert types.count(t) > 5, t


def test_emit_can_create_the_entities_it_names():
    e = new_engine()
    e.run(until=Date(1, 5, 0))
    births = [ev for ev in e.events if ev.type == "mini.birth"]
    assert births
    child = births[0].roles["child"][0]
    assert child.startswith("e") and e.store.kind(child) == "person"
    created = next(r for r in e.store.created if r["id"] == child)
    assert created["event"] == births[0].id


# ---------------------------------------------------------------- checkpoint basics


def test_checkpoint_needs_flushed_history_and_round_trips(tmp_path):
    e = new_engine()
    e.run_before(Date(1, 3, 0))
    with pytest.raises(ValueError):
        e.checkpoint()
    e.clear_pending()
    cp = e.checkpoint()
    assert cp["header"]["date"] == [1, 3, 0] and cp["header"]["format"] == 1
    save_checkpoint(tmp_path / "c.json.gz", cp)
    assert load_checkpoint(tmp_path / "c.json.gz") == json.loads(json.dumps(cp))
    restored = Engine.restore(cp, CAL, RULESETS, seed=SEED)
    assert restored.state_hash() == e.state_hash()


def test_restore_refuses_a_different_recipe():
    e = new_engine()
    e.run_before(Date(1, 2, 0))
    e.clear_pending()
    cp = e.checkpoint()
    with pytest.raises(ValueError):
        Engine.restore(cp, CAL, RULESETS, seed=SEED + 1)
    with pytest.raises(ValueError):
        Engine.restore(cp, CAL, RULESETS[:1], seed=SEED)
    bad = json.loads(json.dumps(cp))
    bad["header"]["format"] = 99
    with pytest.raises(ValueError):
        Engine.restore(bad, CAL, RULESETS, seed=SEED)


def test_state_hash_ignores_pending_history_but_not_state():
    a, b = new_engine(), new_engine()
    a.run(until=Date(1, 2, 0))
    b.run(until=Date(1, 2, 0))
    b.clear_pending()
    assert a.state_hash() == b.state_hash()
    b.run(until=Date(1, 2, 1))
    assert a.state_hash() != b.state_hash() or not b.events


# ---------------------------------------------------------------- replay equivalence (fresh processes)

POSITIONS = [Date(1, 1, 30), Date(1, 2, 0), Date(1, 4, 95), Date(1, 9, 180), Date(1, 15, 1),
             Date(1, 20, 0), Date(1, 24, 300), Date(1, 30, 0)]


@pytest.mark.parametrize("at", POSITIONS, ids=lambda d: f"{d.year}-{d.day}")
def test_replay_from_a_checkpoint_matches_the_continuous_run(at, continuous, tmp_path):
    e = new_engine()
    e.run_before(at)
    prefix = e.pending()
    e.clear_pending()
    save_checkpoint(tmp_path / "c.json.gz", e.checkpoint())
    out = tmp_path / "out.json"
    subprocess.run([sys.executable, str(CHILD), str(tmp_path / "c.json.gz"), "1", str(END.year), str(END.day),
                    str(out)], check=True)
    child = json.loads(out.read_text(encoding="utf-8"))
    events = prefix["events"] + child["events"]
    hinges = prefix["hinges"] + child["hinges"]
    assert digest(events) == digest(continuous["events"])
    assert digest(hinges) == digest(continuous["hinges"])
    assert child["state_hash"] == continuous["state_hash"]


def test_villages_have_grain(continuous):
    e = new_engine()
    e.run(until=Date(1, 2, 0))
    assert all(x > 0 for x in e.store.read_column("grain", list(VILLAGES)))
