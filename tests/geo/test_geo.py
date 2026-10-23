"""The geography file, its checks and paths (S4 spec §2-4, #76)."""

import copy
import json

import pytest

from renasci import geo

DOC = {
    "about": "a test world",
    "regions": [{"id": "g:land"}, {"id": "g:north", "name": "North", "within": "g:land"},
                {"id": "g:south", "name": "South", "within": "g:land"}],
    "places": [
        {"id": "t:a", "name": "A", "kind": "settlement", "region": "g:north"},
        {"id": "t:b", "name": "B", "kind": "settlement", "region": "g:north"},
        {"id": "t:c", "name": "C", "kind": "settlement", "region": "g:south"},
        {"id": "t:d", "name": "D", "kind": "settlement", "region": "g:south"},
        {"id": "g:ruin", "name": "Ruin", "kind": "ruin", "region": "g:south", "at": [3.0, 4.5]},
    ],
    "routes": [
        {"id": "g:a--b", "ends": ["t:a", "t:b"], "days": 2, "kind": "road", "vialux": True},
        {"id": "g:b--c", "ends": ["t:b", "t:c"], "days": 3, "kind": "road"},
        {"id": "g:a--ruin", "ends": ["t:a", "g:ruin"], "days": 2, "kind": "track"},
        {"id": "g:ruin--c", "ends": ["g:ruin", "t:c"], "days": 3, "kind": "track"},
        {"id": "g:c--d", "ends": ["t:c", "t:d"], "days": 4, "kind": "river"},
    ],
}


def errors(doc):
    return [f for f in geo.check(doc) if f["severity"] == "error"]


def broken(change):
    doc = copy.deepcopy(DOC)
    change(doc)
    return [f["kind"] for f in errors(doc)]


def test_a_good_file_has_no_findings():
    assert geo.check(DOC) == []


@pytest.mark.parametrize("change, kind", [
    (lambda d: d["places"].append({"id": "t:a", "kind": "landmark", "region": "g:north"}), "duplicate_id"),
    (lambda d: d["places"].append({"id": "x:odd", "kind": "landmark", "region": "g:north"}), "bad_id"),
    (lambda d: d["places"][0].update(region="g:nowhere"), "unknown_region"),
    (lambda d: d["regions"][0].update(within="g:north"), "region_cycle"),
    (lambda d: d["routes"][0].update(ends=["t:a", "t:zz"]), "unknown_place"),
    (lambda d: d["routes"][0].update(ends=["t:a", "t:a"]), "self_route"),
    (lambda d: d["routes"][0].update(days=0), "bad_days"),
    (lambda d: d["routes"][0].update(days=1.5), "bad_days"),
    (lambda d: d["routes"].append(dict(DOC["routes"][0], id="g:a--b-2")), "duplicate_route"),
    (lambda d: d["places"][0].pop("kind"), "missing_field"),
])
def test_each_rule_has_its_error(change, kind):
    assert kind in broken(change)


def test_a_second_route_of_another_kind_is_fine():
    doc = copy.deepcopy(DOC)
    doc["routes"].append({"id": "g:a--b-sea", "ends": ["t:b", "t:a"], "days": 1, "kind": "sea"})
    assert errors(doc) == []


def test_settlements_cut_off_are_a_warning_not_an_error():
    doc = copy.deepcopy(DOC)
    doc["routes"] = [r for r in doc["routes"] if r["id"] != "g:c--d"]
    found = geo.check(doc)
    assert [f["kind"] for f in found] == ["disconnected"] and found[0]["severity"] == "warning"


def test_save_and_load_round_trip_byte_for_byte(tmp_path):
    p = tmp_path / "world.json"
    geo.save(p, DOC)
    first = p.read_bytes()
    geo.save(p, geo.load(p))
    assert p.read_bytes() == first
    lines = first.decode("utf-8").splitlines()
    assert sum(1 for line in lines if '"id": "g:' in line and "routes" not in line) >= 5  # one record per line


def test_load_refuses_a_file_with_errors(tmp_path):
    doc = copy.deepcopy(DOC)
    doc["routes"][0]["days"] = -1
    p = tmp_path / "bad.json"
    p.write_text(json.dumps(doc), encoding="utf-8")
    with pytest.raises(ValueError, match="bad_days"):
        geo.load(p)


def test_shortest_path_by_days_with_ties_broken_by_id():
    routes = DOC["routes"]
    assert geo.shortest(routes, "t:a", "t:c") == (5, ["t:a", "g:ruin", "t:c"])  # "g:ruin" < "t:b"
    assert geo.shortest(routes, "t:a", "t:d") == (9, ["t:a", "g:ruin", "t:c", "t:d"])
    assert geo.shortest(routes, "t:a", "t:a") == (0, ["t:a"])


def test_closed_routes_are_avoided_and_unreachable_is_none():
    routes = [dict(r, open=r["id"] != "g:a--ruin") for r in DOC["routes"]]
    assert geo.shortest(routes, "t:a", "t:c") == (5, ["t:a", "t:b", "t:c"])
    cut = [dict(r, open=r["id"] != "g:c--d") for r in DOC["routes"]]
    assert geo.shortest(cut, "t:a", "t:d") is None


def test_within_bounds_the_days():
    assert geo.within(DOC["routes"], "t:a", 4) == {"t:a": 0, "t:b": 2, "g:ruin": 2}
    assert geo.within(DOC["routes"], "t:a", 5)["t:c"] == 5


def test_a_scenario_must_name_the_same_settlements_in_the_same_regions():
    sc = {"settlements": [{"id": s, "region": r} for s, r in
                          (("t:a", "g:north"), ("t:b", "g:north"), ("t:c", "g:south"), ("t:d", "g:south"))]}
    assert geo.check_scenario(sc, DOC) == []
    fewer = {"settlements": sc["settlements"][:3]}
    assert [f["kind"] for f in geo.check_scenario(fewer, DOC)] == ["settlements_differ"]
    moved = copy.deepcopy(sc)
    moved["settlements"][0]["region"] = "g:south"
    assert [f["kind"] for f in geo.check_scenario(moved, DOC)] == ["region_differs"]
    sc_regions = dict(sc, regions={"g:north": ["t:a"], "g:south": ["t:c", "t:d", "t:b"]})
    assert "regions_differ" in [f["kind"] for f in geo.check_scenario(sc_regions, DOC)]


def test_cast_into_an_engine_and_read_paths_through_ctx():
    from renasci.core.calendar import Age, Calendar, Date
    from renasci.core.engine import Engine
    from renasci.core.systems import Ruleset, System

    seen = {}

    class Probe(System):
        name, cadence = "toy.probe", "yearly"
        reads = geo.READS

        def run(self, ctx):
            seen["path"] = geo.path(ctx, "t:a", "t:d")
            seen["reach"] = geo.reach(ctx, "t:a", 4)

    cal = Calendar(ages=(Age(1, "1X", "Toy Age", last_year=5),))
    e = Engine(cal, seed=1, rulesets=[(Date(1, 1, 0), Ruleset("toy", 1, (Probe(),)))])
    geo.cast(e, DOC)
    assert sorted(e.store.ids("route")) == sorted(r["id"] for r in DOC["routes"])
    assert e.store.get("g:ruin", "kind") == "ruin" and e.store.get("g:north", "within") == "g:land"
    assert e.store.get("g:b--c", "open") is True and e.store.get("g:a--b", "vialux") is True
    assert e.store.get("g:b--c", "vialux") is False
    assert "t:a" not in e.store.ids("place")  # settlements are the scenario's to cast
    e.run(until=Date(1, 1, 10))
    assert seen["path"] == (9, ["t:a", "g:ruin", "t:c", "t:d"])
    assert seen["reach"] == {"t:a": 0, "t:b": 2, "g:ruin": 2}


@pytest.mark.parametrize("doc", [
    [], {"places": "t:a"}, {"places": ["t:a"]}, {"regions": [{"id": "g:r", "within": ["g:x"]}]},
    {"regions": [{"id": "g:r"}], "places": [{"id": "t:a", "kind": "settlement", "region": ["g:r"]}]},
    {"regions": [{"id": "g:r"}], "places": [{"id": "t:a", "kind": ["x"], "region": "g:r"}]},
    {"routes": [{"id": "g:x", "ends": [["t:a"], "t:b"], "days": 1, "kind": "road"}]},
])
def test_malformed_files_are_findings_not_crashes(doc):
    assert errors(doc)


def test_a_route_kind_must_be_one_the_engine_knows():
    assert "bad_kind" in broken(lambda d: d["routes"][0].update(kind="teleport"))


def test_only_regions_on_the_cycle_are_reported_in_one():
    doc = copy.deepcopy(DOC)
    doc["regions"] += [{"id": "g:x", "within": "g:y"}, {"id": "g:y", "within": "g:x"}, {"id": "g:z", "within": "g:x"}]
    assert sorted(f["id"] for f in errors(doc) if f["kind"] == "region_cycle") == ["g:x", "g:y"]


def test_a_route_closed_in_the_file_is_cast_closed():
    from renasci.core.calendar import Age, Calendar, Date
    from renasci.core.engine import Engine
    from renasci.core.systems import Ruleset

    doc = copy.deepcopy(DOC)
    doc["routes"][0]["open"] = False
    e = Engine(Calendar(ages=(Age(1, "1X", "Toy Age", last_year=5),)), seed=1,
               rulesets=[(Date(1, 1, 0), Ruleset("toy", 1, ()))])
    geo.cast(e, doc)
    assert e.store.get("g:a--b", "open") is False and e.store.get("g:b--c", "open") is True
