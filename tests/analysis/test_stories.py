"""The story finder (S7 spec §9, #97): arcs from ambitions, sagas from direct links, titles, periods."""

import copy
import json

import pytest

from renasci.analysis.stories import MAX_ARCS, MAX_PEOPLE, partition, period, stories
from renasci.core.calendar import Date
from renasci.kin import SCENARIO, new_engine

END = Date(1, 60, 359)


@pytest.fixture(scope="module")
def world():
    sc = copy.deepcopy(SCENARIO)
    sc["params"]["traits"] = {"wits": "stature", "charm": "stature", "temper": "stature"}
    e = new_engine(scenario=sc)
    e.run(until=END)
    tables, state = e.pending(), e.store.to_json()
    e.found = stories(tables["events"], state)
    e.tables, e.state = tables, state
    return e


def test_every_ambition_is_an_arc_with_its_beats(world):
    arcs = {a["ambition"]: a for a in world.found["arcs"]}
    assert set(arcs) == set(world.store.ids("ambition"))
    events = {ev["id"]: ev for ev in world.tables["events"]}
    for amb, arc in arcs.items():
        assert arc["owner"] == world.store.get(amb, "owner") and arc["class"] == world.store.get(amb, "class")
        assert arc["beats"] and arc["beats"][0] == arc["formed_by"]
        dates = [tuple(events[b]["date"]) for b in arc["beats"]]
        assert dates == sorted(dates)
        own = {("ambition", amb)} | {("scheme", s) for s in arc["schemes"]}
        for b in arc["beats"][1:]:
            ev = events[b]
            causes = {tuple(c) for c in ev["causes"]}
            assert causes & own or amb in sum(ev["roles"].values(), []), (ev["type"], amb)


def test_arcs_have_salience_titles_and_spans(world):
    for arc in world.found["arcs"]:
        assert arc["title"] and "{" not in arc["title"]
        assert arc["salience"] > 0
        assert arc["span"][0] <= arc["span"][1]
    violent = [a for a in world.found["arcs"] if a["violent"]]
    calm = [a for a in world.found["arcs"] if not a["violent"] and a["class"] == "Marry"]
    if violent and calm:
        assert max(a["salience"] for a in violent) > max(a["salience"] for a in calm)


def test_sagas_join_linked_arcs_within_limits(world):
    sagas = world.found["sagas"]
    assert sagas
    arcs = {a["id"]: a for a in world.found["arcs"]}
    seen = set()
    for s in sagas:
        assert len(s["arcs"]) >= 2 and len(s["arcs"]) <= MAX_ARCS and len(s["people"]) <= MAX_PEOPLE
        assert not seen & set(s["arcs"])  # an arc belongs to one saga at most
        seen |= set(s["arcs"])
        assert s["title"] == max((arcs[a] for a in s["arcs"]), key=lambda a: (a["salience"], a["id"]))["title"]
        assert s["span"][0] == min(arcs[a]["span"][0] for a in s["arcs"])


def test_no_saga_swallows_a_house(world):
    """For every house with 4+ arcs, no saga holds arcs owned by more than half its notables alive in its span."""
    store = world.store
    arcs = {a["id"]: a for a in world.found["arcs"]}
    died = {ev["roles"]["deceased"][0]: ev["date"][1] for ev in world.tables["events"] if ev["type"] == "people.death"}
    for house in store.ids("house"):
        members = [p for p in store.ids("person") if store.get(p, "house") == house]
        if sum(1 for a in arcs.values() if a["owner"] in members) < 4:
            continue
        for s in world.found["sagas"]:
            lo, hi = s["span"]
            alive = [p for p in members if store.get(p, "born")[1] <= hi and died.get(p, 10**6) >= lo]
            owners = {arcs[a]["owner"] for a in s["arcs"]} & set(members)
            assert len(owners) <= len(alive) / 2, (house, s["id"], len(owners), len(alive))


def test_the_story_finder_is_deterministic(world):
    again = stories(world.tables["events"], world.state)
    assert json.dumps(again, sort_keys=True) == json.dumps(world.found, sort_keys=True)


def test_what_flows_through_a_period(world):
    got = period(world.found, 20, 30)
    assert got["arcs"] and all(a["span"][0] <= 30 and a["span"][1] >= 20 for a in got["arcs"])
    assert all(s["span"][0] <= 30 and s["span"][1] >= 20 for s in got["sagas"])
    assert got["arcs"] == sorted(got["arcs"], key=lambda a: (-a["salience"], a["id"]))


def test_splitting_drops_the_weakest_links_first():
    """A chain of 30 arcs held by weight-2 links, with one weight-5 pair: the parts fit, the pair survives."""
    nodes = [f"a{i:02}" for i in range(30)]
    edges = {(nodes[i], nodes[i + 1]): 2 for i in range(29)}
    edges[("a00", "a01")] = 5
    parts = partition(nodes, edges, fits=lambda part: len(part) <= 12)
    assert all(len(p) <= 12 for p in parts)
    assert any({"a00", "a01"} <= set(p) for p in parts)
    assert sorted(n for p in parts for n in p) == nodes


def test_renasci_stories_writes_the_analysis(tmp_path, capsys):
    from renasci.cli import main

    recipe = tmp_path / "kin.toml"
    recipe.write_text('[run]\nname = "kin"\nengine = "0.1.0"\nseed = 1234\nworld = "kin"\nend = "1K 15"\n'
                      'checkpoint_every_years = 5\n', encoding="utf-8")
    assert main(["run", str(recipe), "--out", str(tmp_path / "runs")]) == 0
    run = tmp_path / "runs" / "kin"
    assert main(["stories", str(run), "--from", "5", "--to", "10"]) == 0
    found = json.loads((run / "analysis" / "stories.json").read_text(encoding="utf-8"))
    assert found["run"] == "kin" and found["arcs"]
    assert "arcs" in capsys.readouterr().out


def test_splitting_a_large_dense_component_is_quick():
    import random
    import time

    rng = random.Random(7)
    nodes = [f"n{i:03}" for i in range(400)]
    edges = {}
    while len(edges) < 800:
        a, b = sorted(rng.sample(nodes, 2))
        edges[(a, b)] = rng.choice([2, 3, 5])
    start = time.perf_counter()
    parts = partition(nodes, edges, fits=lambda part: len(part) <= 12)
    assert time.perf_counter() - start < 10
    assert all(len(p) <= 12 for p in parts) and sorted(n for p in parts for n in p) == nodes


def test_a_killing_title_needs_the_death_to_name_the_blow():
    """A struck blow whose target lived (a guarded target) and died later of something else isn't a killing."""
    state = {"entities": [
        {"id": "amb", "kind": "ambition", "status": "active", "fields": {
            "owner": "o", "class": "Vengeance", "target": "t", "state": "died_unfulfilled", "formed": [1, 1, 0],
            "resolved": None, "born_of": ["event", "x0"]}},
        {"id": "o", "kind": "person", "status": "active", "fields": {"name": "Arn", "born": [1, -30, 0]}},
        {"id": "t", "kind": "person", "status": "dead", "fields": {"name": "Bel", "born": [1, -30, 0]}}]}
    events = [
        {"id": "f", "date": [1, 1, 0], "type": "people.ambition_formed", "roles": {"owner": ["o"], "ambition": ["amb"]},
         "causes": [], "payload": {"class": "Vengeance"}},
        {"id": "hit", "date": [1, 2, 0], "type": "people.action", "roles": {"actor": ["o"], "target": ["t"]},
         "causes": [["ambition", "amb"]], "payload": {"action": "Duel", "outcome": "success"}},
        {"id": "d", "date": [1, 30, 0], "type": "people.death", "roles": {"deceased": ["t"]}, "causes": [],
         "payload": {"age": 60, "cause": "old age"}}]
    arc = stories(events, state)["arcs"][0]
    assert "duel" not in arc["title"] and arc["title"] == "Arn's long revenge"
    events[2]["causes"] = [["event", "hit"]]
    assert stories(events, state)["arcs"][0]["title"] == "The fatal duel of Bel"
