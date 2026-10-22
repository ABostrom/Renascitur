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
    for t in ("mini.birth", "mini.death", "mini.harvest", "mini.feast", "mini.marriage", "mini.election"):
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
        e.checkpoint(at=Date(1, 3, 0), segments=0)
    e.clear_pending()
    cp = e.checkpoint(at=Date(1, 3, 0), segments=0)
    assert cp["header"]["date"] == [1, 3, 0] and cp["header"]["format"] == 2
    save_checkpoint(tmp_path / "c.json.gz", cp)
    assert load_checkpoint(tmp_path / "c.json.gz") == json.loads(json.dumps(cp))
    restored = Engine.restore(cp, CAL, RULESETS, seed=SEED)
    assert restored.state_hash() == e.state_hash()


def test_restore_refuses_a_different_recipe():
    e = new_engine()
    e.run_before(Date(1, 2, 0))
    e.clear_pending()
    cp = e.checkpoint(at=Date(1, 2, 0), segments=0)
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
    save_checkpoint(tmp_path / "c.json.gz", e.checkpoint(at=at, segments=0))
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


# ---------------------------------------------------------------- review fixes

from mini_world import BIRTH, DEATH, START  # noqa: E402

from renasci.core.calendar import Age, Calendar  # noqa: E402
from renasci.core.systems import Ruleset, System  # noqa: E402


def checkpoint_at(at):
    e = new_engine()
    e.run_before(at)
    e.clear_pending()
    return e, e.checkpoint(at=at, segments=3)


def test_failed_birth_leaves_no_orphan_child():
    class KillThenBirth(System):
        name, cadence = "mini.bad", "yearly"
        reads = frozenset({"village"})
        writes = frozenset({"status", "new:person"})
        event_types = (BIRTH, DEATH)

        def run(self, ctx):
            ctx.emit("mini.death", {"deceased": ("t:p00",)}, purpose="death", actor="t:p00")
            ctx.set_status("t:p00", "dead")
            ctx.emit("mini.birth", {"parent": ("t:p00",)}, purpose="birth", actor="t:p00",
                     creates={"child": [("person", {"village": "t:Eastvale"})]})

    e = Engine(CAL, seed=1, rulesets=[(START, Ruleset("bad", 1, (KillThenBirth(),)))])
    e.cast("person", "t:p00", {})
    with pytest.raises(ValueError):
        e.run(until=START)
    assert e.store.ids("person") == ["t:p00"]
    assert [r["id"] for r in e.store.created] == ["t:p00"]


def test_restore_detects_recipe_changes_beyond_names_and_versions():
    _, cp = checkpoint_at(Date(1, 2, 0))
    changed = [(d, Ruleset(rs.name, rs.version, rs.systems, params={"fertility": 2})) for d, rs in RULESETS]
    with pytest.raises(ValueError):
        Engine.restore(cp, CAL, changed, seed=SEED)
    other_cal = Calendar(ages=(Age(1, "1X", "Toy Age", last_year=99),))
    with pytest.raises(ValueError):
        Engine.restore(cp, other_cal, RULESETS, seed=SEED)
    with pytest.raises(ValueError):
        Engine.restore(cp, CAL, RULESETS, seed=SEED, strict=False)


def test_reshuffle_order_in_the_recipe_does_not_matter():
    from renasci.core.rng import Reshuffle

    r1, r2 = Reshuffle((1, 40, 0), "a"), Reshuffle((1, 50, 0), "b")
    e = new_engine(reshuffles=(r1, r2))
    e.run_before(Date(1, 1, 30))
    e.clear_pending()
    cp = e.checkpoint(at=Date(1, 1, 30), segments=0)
    Engine.restore(cp, CAL, RULESETS, seed=SEED, reshuffles=(r2, r1))


def test_checkpoint_refuses_odds_hooks_and_stateful_systems():
    e = new_engine()
    e.run_before(Date(1, 1, 30))
    e.clear_pending()
    e.odds_hooks.append(lambda ctx, p, purpose, owner: (p, None))
    with pytest.raises(ValueError):
        e.checkpoint(at=Date(1, 1, 30), segments=0)

    class Stateful(System):
        name, cadence = "mini.stateful", "yearly"

        def run(self, ctx):
            self.seen = True

    s = Engine(CAL, seed=1, rulesets=[(START, Ruleset("s", 1, (Stateful(),)))])
    s.run(until=START)
    s.clear_pending()
    with pytest.raises(ValueError):
        s.checkpoint(at=Date(1, 1, 1), segments=0)


def test_checkpoint_records_its_date_and_run_folder_mark():
    _, cp = checkpoint_at(Date(1, 2, 45))
    assert cp["header"]["date"] == [1, 2, 45] and cp["header"]["segments"] == 3


def test_checkpoint_date_must_be_the_run_position():
    e = new_engine()
    e.run_before(Date(1, 2, 0))
    e.clear_pending()
    with pytest.raises(ValueError):
        e.checkpoint(at=Date(1, 1, 200), segments=0)  # activations after 1-1-200 already ran
    with pytest.raises(ValueError):
        e.checkpoint(at=Date(1, 3, 0), segments=0)  # activations before 1-3-0 have not run


def test_a_restored_engine_cannot_cast_and_knows_its_date():
    e, cp = checkpoint_at(Date(1, 2, 0))
    r = Engine.restore(cp, CAL, RULESETS, seed=SEED)
    with pytest.raises(ValueError):
        r.cast("person", "t:late", {})


def test_checkpoint_holds_only_the_open_quarter_of_ordinals():
    _, cp = checkpoint_at(Date(1, 2, 0))
    assert all(row[3] >= [1, 2, 0] for row in cp["state"]["ordinals"])


def test_replay_matches_every_table(continuous, tmp_path):
    at = Date(1, 12, 100)
    e = new_engine()
    e.run_before(at)
    prefix = e.pending()
    e.clear_pending()
    r = Engine.restore(e.checkpoint(at=at, segments=0), CAL, RULESETS, seed=SEED)
    r.run(until=END)
    rest = r.pending()
    whole = new_engine()
    whole.run(until=END)
    full = whole.pending()
    for table in full:
        assert digest(prefix[table] + rest[table]) == digest(full[table]), table
