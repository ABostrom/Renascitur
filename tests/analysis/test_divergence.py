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


def test_a_within_valley_coupling_bug_is_caught():
    """Per-valley module-global grief: deaths it adds in scopes whose inputs still match are unexplained."""
    base = run(buggy="life")
    person, died = next((ev["roles"]["deceased"][0], ev["date"]) for ev in base[0]["events"]
                        if ev["type"] == "toy.death" and ev["place"] in VALLEYS["t:North"] and ev["date"][1] >= 2)
    ripple = Ripple("r1", "protect", Date(1, died[1] - 1, 0), person, {"until": [1, YEARS, 359]})
    variant = run(buggy="life", ripples=[ripple])
    report = analyse(base[0], variant[0], base[1], variant[1], ripples=["r1"])
    assert report["unexplained_events"] > 0, report


def test_shared_granary_does_not_explain_by_itself(baseline, doomed):
    """Value-aware: a granary write that is equal in both runs taints nothing."""
    person, died = doomed
    ripple = Ripple("r1", "protect", Date(1, died[1] - 1, 0), person, {"until": [1, YEARS, 359]})
    variant = run(ripples=[ripple])
    report = analyse(baseline[0], variant[0], baseline[1], variant[1], ripples=["r1"])
    assert report["tainted_scopes"] > 0
    assert not set(report["tainted_scope_names"]) & SOUTH  # equal granary writes in the South taint nothing


def test_toy_pins_are_honoured_and_ripples_stay_explained():
    """The spec's toy pins: Ada exists (cast by canon), and a fire happens in Brook in years 8-10."""
    from renasci.core.pins import Pin

    pins = [Pin("p_ada", "existence", subject="t:Ada", window=(Date(1, 1, 0), Date(1, YEARS, 0)),
                payload={"kind": "person", "fields": {"sex": "f", "born": -20, "village": "t:Ashford", "spouse": None}}),
            Pin("p_fire", "event", window=(Date(1, 8, 0), Date(1, 10, 0)),
                payload={"type": "toy.fire", "roles": {"village": ["t:Brook"]}})]
    base_engine = new_engine(people_per_village=16, pins=pins)
    base_engine.run(until=END)
    base = (base_engine.pending(), base_engine.store.to_json())
    assert base_engine.director.status == {"p_ada": "satisfied", "p_fire": "forced"}
    assert [s["action"] for s in base[0]["strain"]] == ["force"]

    target = next(ev["roles"]["deceased"][0] for ev in base[0]["events"]
                  if ev["type"] == "toy.death" and ev["place"] == "t:Cairn" and ev["date"][1] >= 3)
    variant_engine = new_engine(people_per_village=16, pins=pins,
                                ripples=[Ripple("r1", "doom", Date(1, 2, 0), target)])
    variant_engine.run(until=END)
    variant = (variant_engine.pending(), variant_engine.store.to_json())
    report = analyse(base[0], variant[0], base[1], variant[1], ripples=["r1"])
    assert report["divergent_events"] > 0
    assert report["unexplained_events"] == 0 and report["unexplained_entities"] == 0, report["unexplained"]


def test_scope_is_not_part_of_event_identity_for_divergence():
    """Runs from before event rows carried `scope` must still diff cleanly against newer ones."""
    import copy

    base = run()
    older = copy.deepcopy(base)
    for ev in older[0]["events"]:
        ev.pop("scope", None)
    report = analyse(older[0], base[0], older[1], base[1])
    assert report["divergent_events"] == 0


# ---------------------------------------------------------------- #56: what the diff page needs


def test_divergent_ids_are_listed_per_side(baseline, doomed):
    person, died = doomed
    ripple = Ripple("r1", "protect", Date(1, died[1] - 1, 0), person, {"until": [1, YEARS, 359]})
    variant = run(ripples=[ripple])
    report = analyse(baseline[0], variant[0], baseline[1], variant[1], ripples=["r1"])
    ids_a = {e["id"] for e in baseline[0]["events"]}
    ids_b = {e["id"] for e in variant[0]["events"]}
    d = report["divergent"]
    assert set(d["only_baseline"]) == ids_a - ids_b and set(d["only_variant"]) == ids_b - ids_a
    assert not set(d["changed"]) - (ids_a & ids_b)
    assert len(d["only_baseline"]) + len(d["only_variant"]) + len(d["changed"]) == report["divergent_events"]


def test_wave_cells_name_their_age_and_count_unexplained(baseline, doomed):
    person, died = doomed
    ripple = Ripple("r1", "protect", Date(1, died[1] - 1, 0), person, {"until": [1, YEARS, 359]})
    variant = run(ripples=[ripple])
    report = analyse(baseline[0], variant[0], baseline[1], variant[1], ripples=["r1"])
    assert all(w["age"] == 1 and w["unexplained"] == 0 for w in report["wave"])


def test_every_unexplained_item_is_listed_with_its_side(doomed):
    person, died = doomed
    ripple = Ripple("r1", "protect", Date(1, died[1] - 1, 0), person, {"until": [1, YEARS, 359]})
    base = run(buggy=True)
    variant = run(buggy=True, ripples=[ripple])
    report = analyse(base[0], variant[0], base[1], variant[1], ripples=["r1"])
    u = report["unexplained"]
    assert len(u["events"]) == report["unexplained_events"] > 0
    assert len(u["entities"]) == report["unexplained_entities"] and len(u["cells"]) == report["unexplained_cells"]
    ids_a = {e["id"] for e in base[0]["events"]}
    for e in u["events"]:
        assert e["side"] in ("baseline", "variant", "both")
        assert (e["side"] == "variant") == (e["id"] not in ids_a)
    assert all(c["side"] in ("baseline", "variant", "both") for c in u["entities"] + u["cells"])
    assert sum(w["unexplained"] for w in report["wave"]) == report["unexplained_events"]


def test_wave_places_events_without_a_place_by_their_scope(baseline):
    """Granary and move events have no `place`; the wave puts them where they were decided."""
    report = analyse(baseline[0], baseline[0], baseline[1], baseline[1])
    placed = {w["place"] for w in report["wave"]}
    assert "t:North" in placed or "t:South" in placed  # valley-scoped granary events
    unplaced = sum(w["total"] for w in report["wave"] if w["place"] is None)
    casts = sum(1 for e in baseline[0]["events"] if e["type"].startswith("engine."))
    assert unplaced == casts
