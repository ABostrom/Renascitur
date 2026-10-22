"""Scenario synthesis (S3 spec §9, #73): a starting world from a scenario JSON, a seed and canon."""

import copy

import pytest

from renasci.core.calendar import Date
from renasci.kin import CAL, SCENARIO, new_engine
from renasci.people.houses import line_of_succession
from renasci.people.population import BAND_COLUMNS
from renasci.people.races import Race, age_years

START = Date(1, 1, 0)


@pytest.fixture(scope="module")
def world():
    return new_engine()


def test_synthesis_is_deterministic_and_seeded():
    assert new_engine().state_hash() == new_engine().state_hash()
    assert new_engine(seed=99).state_hash() != new_engine().state_hash()


def test_every_settlement_gets_its_masses_and_commoners(world):
    store = world.store
    for spec in SCENARIO["settlements"]:
        s = spec["id"]
        assert sum(int(store.read_column(c, [s])[0]) for c in BAND_COLUMNS) == spec["masses"]
        commoners = [p for p in store.get(s, "residents") if store.get(p, "house") is None]
        assert len(commoners) >= spec["commoners"]  # (plus husbands married into a house's women)
    assert world.check_conservation() == []


def test_commoners_have_spread_ages_and_adult_couples(world):
    store = world.store
    race = {r["id"]: Race.from_json(r) for r in SCENARIO["races"]}
    ages = []
    for p in store.ids("person"):
        if store.status(p) != "active":
            continue
        age = age_years(CAL, store.get(p, "born"), START)
        ages.append(age)
        spouse = store.get(p, "spouse")
        if spouse:
            assert store.get(spouse, "spouse") == p and age >= race[store.get(p, "race")].marriage[0]
    assert len(set(ages)) > 30


def test_houses_are_families(world):
    store = world.store
    race = {r["id"]: Race.from_json(r) for r in SCENARIO["races"]}
    for spec in SCENARIO["houses"]:
        house = spec["id"]
        office = store.get(house, "headship")
        head = store.get(office, "holder")
        assert 30 <= age_years(CAL, store.get(head, "born"), START) <= 55
        assert store.get(head, "house") == house and store.get(head, "offices") == [office]
        father = store.get(head, "father")
        assert father and store.status(father) == "dead" and head in store.get(father, "children")
        line = line_of_succession(store.get, store.status, head, house, male_first=True)
        assert line, f"{house} has nobody to succeed"
        for child in store.get(head, "children"):
            mother = store.get(child, "mother")
            r = race[store.get(mother, "race")]
            assert r.fertile[0] <= age_years(CAL, store.get(mother, "born"), Date(*store.get(child, "born"))) <= r.fertile[1]
            assert store.get(child, "father") == head


def test_children_inherit_from_their_parents(world):
    store = world.store
    for p in store.ids("person"):
        mother, father = store.get(p, "mother"), store.get(p, "father")
        if mother and father:
            for locus, (m, f) in store.get(p, "genome").items():
                assert m in store.get(mother, "genome")[locus] and f in store.get(father, "genome")[locus]


def test_a_scenario_with_more_houses_and_settlements_is_just_data():
    bigger = copy.deepcopy(SCENARIO)
    bigger["settlements"].append({**bigger["settlements"][0], "id": "t:Extra", "region": "t:Hollow"})
    bigger["regions"]["t:Hollow"] = bigger["regions"]["t:Hollow"] + ["t:Extra"]
    bigger["houses"].append({"id": "t:House-Extra", "name": "Extra", "seat": "t:Extra", "rank": 1,
                             "rule": "absolute_primogeniture"})
    e = new_engine(scenario=bigger)
    assert e.store.exists("t:House-Extra") and e.store.get("t:House-Extra-head", "rule") == "absolute_primogeniture"
    e.run(until=Date(1, 5, 359))
    assert e.check_conservation() == []
