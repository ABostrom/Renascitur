"""The S1 exit test: a ripple run differs from its baseline only in ways the ripple explains."""

import pytest

from renasci.analysis.divergence import analyse
from renasci.core.calendar import Date
from renasci.core.canon import canonical, digest
from renasci.core.ripples import Ripple
from renasci.toy import VALLEYS, new_engine

YEARS = 30
END = Date(1, YEARS, 359)
SOUTH = set(VALLEYS["t:South"]) | {"t:South"}


def run(**kw):
    e = new_engine(people_per_village=16, **kw)
    e.run(until=END)
    return e.pending(), e.store.to_json()


@pytest.fixture(scope="module")
def baseline():
    return run()


@pytest.fixture(scope="module")
def doomed(baseline):
    """A North villager who dies in the baseline, and when."""
    events, _ = baseline
    for ev in events["events"]:
        if ev["type"] == "toy.death" and ev["place"] in VALLEYS["t:North"] and 4 <= ev["date"][1] <= 15:
            return ev["roles"]["deceased"][0], ev["date"]
    pytest.fail("no North death to protect")


def south_events(history):
    rows = [r for r in history["reads"] if r["scope"] in SOUTH]
    ids = {i for r in rows for i in r["events"]}
    return [canonical(e) for e in history["events"] if e["id"] in ids]


def test_identical_runs_have_no_divergence(baseline):
    again = run()
    report = analyse(baseline[0], again[0], baseline[1], again[1])
    assert report["divergent_events"] == 0 and report["divergent_entities"] == 0


def test_a_protect_ripple_has_zero_unexplained_divergence(baseline, doomed):
    person, died = doomed
    ripple = Ripple("r1", "protect", Date(1, died[1] - 1, 0), person, {"until": [1, YEARS, 359]})
    variant = run(ripples=[ripple])
    report = analyse(baseline[0], variant[0], baseline[1], variant[1], ripples=["r1"])
    assert report["divergent_events"] > 0, "the ripple should change something"
    assert report["unexplained_events"] == 0, report["unexplained"]
    assert report["unexplained_entities"] == 0, report["unexplained"]
    assert report["unexplained_cells"] == 0, report["unexplained"]
    assert south_events(variant[0]) == south_events(baseline[0]), "the other valley must be untouched"


def test_a_doom_ripple_has_zero_unexplained_divergence(baseline):
    target = "t:Brook-03"
    variant = run(ripples=[Ripple("r2", "doom", Date(1, 3, 100), target)])
    report = analyse(baseline[0], variant[0], baseline[1], variant[1], ripples=["r2"])
    assert report["divergent_events"] > 0
    assert report["unexplained_events"] == 0 and report["unexplained_entities"] == 0, report["unexplained"]
    assert south_events(variant[0]) == south_events(baseline[0])


def test_the_negative_control_is_caught(doomed):
    """A world-wide shared counter couples the valleys; the analysis must flag it."""
    person, died = doomed
    base = run(buggy=True)
    ripple = Ripple("r1", "protect", Date(1, died[1] - 1, 0), person, {"until": [1, YEARS, 359]})
    variant = run(buggy=True, ripples=[ripple])
    report = analyse(base[0], variant[0], base[1], variant[1], ripples=["r1"])
    assert report["unexplained_events"] > 0 or report["unexplained_entities"] > 0


def test_the_wave_counts_divergence_by_place_and_year(baseline, doomed):
    person, died = doomed
    ripple = Ripple("r1", "protect", Date(1, died[1] - 1, 0), person, {"until": [1, YEARS, 359]})
    variant = run(ripples=[ripple])
    report = analyse(baseline[0], variant[0], baseline[1], variant[1], ripples=["r1"])
    assert sum(w["divergent"] for w in report["wave"]) == report["divergent_events"]
    assert all(w["divergent"] == 0 for w in report["wave"] if w["place"] in SOUTH)


def test_toy_runs_are_deterministic(baseline):
    again = run()
    assert digest(again[0]) == digest(baseline[0]) and digest(again[1]) == digest(baseline[1])


def test_analysis_from_run_folders_matches_memory(baseline, doomed, tmp_path):
    from renasci.io.runfolder import TABLES, RunFolder

    person, died = doomed
    ripple = Ripple("r1", "protect", Date(1, died[1] - 1, 0), person, {"until": [1, YEARS, 359]})
    variant = run(ripples=[ripple])
    folders = []
    for name, (history, _) in (("a", baseline), ("b", variant)):
        rf = RunFolder.create(tmp_path / name, {})
        rf.write_many(history)
        rf.close_segment()
        folders.append({t: list(RunFolder.open(tmp_path / name).read(t)) for t in TABLES})
    from_disk = analyse(folders[0], folders[1], baseline[1], variant[1], ripples=["r1"])
    in_memory = analyse(baseline[0], variant[0], baseline[1], variant[1], ripples=["r1"])
    assert from_disk == in_memory
