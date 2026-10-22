"""Houses, offices and succession (S3 spec §5)."""

import copy

import pytest

from renasci.analysis.divergence import analyse
from renasci.core.calendar import Date
from renasci.core.ripples import Ripple
from renasci.kin import RACES, new_engine
from renasci.people.houses import RULES, line_of_succession

END = Date(1, 60, 359)

# A family: H holds the office. Children in birth order: d1 (f), s1 (m, dead), s2 (m).
# s1 left a son g. H's father F also had H's younger brother b, and b a daughter n.
TREE = {
    "F": {"sex": "m", "children": ["H", "b"], "status": "dead", "house": "h", "father": None},
    "H": {"sex": "m", "children": ["d1", "s1", "s2"], "status": "active", "house": "h", "father": "F"},
    "d1": {"sex": "f", "children": [], "status": "active", "house": "h", "father": "H"},
    "s1": {"sex": "m", "children": ["g"], "status": "dead", "house": "h", "father": "H"},
    "g": {"sex": "m", "children": [], "status": "active", "house": "h", "father": "s1"},
    "s2": {"sex": "m", "children": [], "status": "active", "house": "h", "father": "H"},
    "b": {"sex": "m", "children": ["n"], "status": "active", "house": "h", "father": "F"},
    "n": {"sex": "f", "children": [], "status": "active", "house": "other", "father": "b"},
}


def look(tree):
    return (lambda p, f: tree[p].get(f)), (lambda p: tree[p]["status"])


def test_male_preference_primogeniture_follows_lines_sons_first():
    get, status = look(TREE)
    assert line_of_succession(get, status, "H", "h", male_first=True) == ["g", "s2", "d1", "b"]


def test_absolute_primogeniture_ignores_sex():
    get, status = look(TREE)
    assert line_of_succession(get, status, "H", "h", male_first=False) == ["d1", "g", "s2", "b"]


def test_only_house_members_and_the_living_are_candidates():
    tree = copy.deepcopy(TREE)
    tree["b"]["house"] = "other"
    tree["n"]["house"] = "h"  # her father left the house, but she is in it
    get, status = look(tree)
    assert line_of_succession(get, status, "H", "h", male_first=True) == ["g", "s2", "d1", "n"]


def test_rules_are_named_classes():
    assert {"male_preference_primogeniture", "absolute_primogeniture"} <= set(RULES)


# ---------------------------------------------------------------- on the kin world


@pytest.fixture(scope="module")
def world():
    e = new_engine(people_per_settlement=20)
    e.full_reads = True
    e.run(until=END)
    return e


def test_every_house_has_a_living_holder_and_heir_or_is_extinct(world):
    store = world.store
    houses = store.ids("house")
    assert houses
    for h in houses:
        office = store.get(h, "headship")
        holder, heir = store.get(office, "holder"), store.get(office, "heir")
        if store.get(h, "extinct") is not None:
            assert holder is None
            continue
        assert holder and store.status(holder) == "active" and store.get(holder, "house") == h
        assert heir is None or (store.status(heir) == "active" and store.get(heir, "house") == h and heir != holder)


def test_a_holders_death_brings_a_succession(world):
    successions = [ev for ev in world.events if ev.type == "people.succession"]
    assert successions
    deaths = {ev.roles["deceased"][0]: ev.date for ev in world.events if ev.type == "people.death"}
    for ev in successions:
        (pred,) = ev.roles["predecessor"]
        assert pred in deaths and deaths[pred] <= ev.date
        assert ev.payload["abdication"] is False


def test_heirs_are_named_only_when_they_change(world):
    last: dict[str, object] = {}
    for ev in world.events:
        if ev.type == "people.heir_named":
            office, heir = ev.payload["office"], (ev.roles.get("heir") or (None,))[0]
            assert last.get(office, "unset") != heir
            last[office] = heir


def test_a_house_without_kin_dies_out():
    doomed = copy.deepcopy(RACES)
    for r in doomed:
        r["mortality"] = {"f": [1.0] * 20, "m": [1.0] * 20}
    e = new_engine(people_per_settlement=6, races=doomed)
    e.run(until=Date(1, 2, 359))
    assert all(e.store.get(h, "extinct") is not None for h in e.store.ids("house"))
    assert any(ev.type == "people.house_extinct" for ev in e.events)


def test_protecting_a_head_is_fully_explained(world):
    store = world.store
    first = next(ev for ev in world.events if ev.type == "people.succession")
    head = first.roles["predecessor"][0]
    died = next(ev.date for ev in world.events if ev.type == "people.death" and ev.roles["deceased"] == (head,))
    variant = new_engine(people_per_settlement=20, ripples=[
        Ripple("r1", "protect", Date(1, died.year, 0) if died.day else Date(1, died.year - 1, 0), head,
               {"until": [1, 60, 359]})])
    variant.full_reads = True
    variant.run(until=END)
    report = analyse(world.pending(), variant.pending(), world.store.to_json(), variant.store.to_json(),
                     ripples=["r1"])
    assert report["divergent_events"] > 0
    assert report["unexplained_events"] == report["unexplained_entities"] == report["unexplained_cells"] == 0, \
        report["unexplained"]
    assert store  # (the baseline is unchanged)


# ---------------------------------------------------------------- review fixes


def test_the_line_climbs_through_the_parent_the_house_comes_through():
    tree = {
        "M": {"sex": "f", "children": ["H", "a"], "status": "dead", "house": "h", "father": "X", "mother": None},
        "H": {"sex": "m", "children": [], "status": "active", "house": "h", "father": "P", "mother": "M"},
        "a": {"sex": "f", "children": ["c"], "status": "active", "house": "h", "father": "P", "mother": "M"},
        "c": {"sex": "m", "children": [], "status": "active", "house": "h", "father": "Q", "mother": "a"},
        "P": {"sex": "m", "children": ["H", "a"], "status": "active", "house": "other", "father": None, "mother": None},
    }
    get, status = look(tree)
    assert line_of_succession(get, status, "H", "h", male_first=True, via="mother") == ["a", "c"]


def test_ancestors_are_passed_through_not_chosen():
    tree = {
        "G": {"sex": "m", "children": ["U", "F"], "status": "dead", "house": "h", "father": None},
        "U": {"sex": "m", "children": ["c"], "status": "active", "house": "h", "father": "G"},
        "c": {"sex": "m", "children": [], "status": "active", "house": "h", "father": "U"},
        "F": {"sex": "m", "children": ["H", "b"], "status": "active", "house": "h", "father": "G"},
        "H": {"sex": "m", "children": [], "status": "active", "house": "h", "father": "F"},
        "b": {"sex": "m", "children": [], "status": "active", "house": "h", "father": "F"},
    }
    get, status = look(tree)
    assert line_of_succession(get, status, "H", "h", male_first=True) == ["b", "U", "c"]


def test_no_heir_is_named_for_a_dead_holder():
    e = new_engine(people_per_settlement=20)
    house = e.store.ids("house")[0]
    office = e.store.get(house, "headship")
    holder = e.store.get(office, "holder")
    ev, store, day = e.events[-1].id, e.store, Date(1, 1, 0)
    store.set_status(holder, "dead", day, ev)  # killed outside people.life: no succession follows
    store.set(store.get(holder, "spouse"), "spouse", None, day, ev)
    place = store.get(holder, "place")
    store.set(place, "residents", [p for p in store.get(place, "residents") if p != holder], day, ev)
    e.run(until=Date(1, 2, 359))
    assert not any(ev.type == "people.heir_named" and ev.roles["holder"] == (holder,) for ev in e.events
                   if ev.date >= Date(1, 1, 0) and ev.type != "engine.cast")


def test_a_title_that_is_not_a_headship_falls_vacant_without_ending_the_house():
    doomed = copy.deepcopy(RACES)
    for r in doomed:
        r["mortality"] = {"f": [1.0] * 20, "m": [1.0] * 20}
    e = new_engine(people_per_settlement=6, races=doomed)
    house = e.store.ids("house")[0]
    head = e.store.get(e.store.get(house, "headship"), "holder")
    e.cast("office", "t:Throne", {"name": "Throne", "holder": head, "heir": None,
                                  "rule": "male_preference_primogeniture", "house": house})
    e.store.set(head, "offices", sorted(e.store.get(head, "offices") + ["t:Throne"]), Date(1, 1, 0), e.events[-1].id)
    e.run(until=Date(1, 1, 359))
    vacant = [ev for ev in e.events if ev.type == "people.office_vacant"]
    extinct = [ev for ev in e.events if ev.type == "people.house_extinct"]
    assert [ev.payload["office"] for ev in vacant] == ["t:Throne"]
    assert all(ev.payload["house"] != "t:Throne" for ev in extinct)
    assert e.store.get("t:Throne", "holder") is None


def test_kin_heads_are_cast_with_their_house():
    e = new_engine(people_per_settlement=20)
    rows = {r["id"]: r for r in e.pending()["entities"]}
    for h in e.store.ids("house"):
        head = e.store.get(e.store.get(h, "headship"), "holder")
        cast = next(ev for ev in e.events if ev.type == "engine.cast" and ev.roles["subject"] == (head,))
        assert rows[head]["event"] == cast.id
        assert not [d for d in e.pending()["state_deltas"] if d["entity"] == head and d["old"] is not None]
