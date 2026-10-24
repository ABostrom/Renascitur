"""Cadet branches (S8 spec §3.5, #161): a large house's younger son founds a house of his own."""

import copy

import pytest

from renasci import kin, renascita
from renasci.core.calendar import Date, Span

END = Date(1, 60, 359)


def kin_world(**params):
    sc = copy.deepcopy(kin.SCENARIO)
    sc["params"].update(params)
    e = kin.new_engine(people_per_settlement=20, scenario=sc)
    e.run(until=END)
    return e


@pytest.fixture(scope="module")
def world():
    return kin_world(cadet_size=4, cadet_rate=0.5)


def cadets(e):
    return [h for h in e.store.ids("house") if e.store.get(h, "cadet_of")]


def test_cadets_are_off_unless_a_world_asks_for_them():
    assert cadets(kin_world()) == []


def test_a_large_houses_younger_son_founds_a_cadet_house(world):
    store = world.store
    found = [ev for ev in world.events if ev.type == "people.cadet_founded"]
    assert found and len(found) == len(cadets(world))
    for ev in found:
        house, parent = ev.payload["house"], ev.payload["parent"]
        (founder,), (head,) = ev.roles["founder"], ev.roles["head"]
        assert store.get(house, "cadet_of") == parent and store.get(house, "founded") == ev.date.to_json()
        assert founder in store.get(head, "children") and store.get(head, "house") == parent
        assert store.get(house, "seat") in store.ids("settlement")
        assert store.get(house, "rank") <= store.get(parent, "rank")
        assert "None" not in store.get(house, "name") and store.get(founder, "name") in store.get(house, "name")
        assert store.get(founder, "house") == house or store.status(founder) != "active"
        assert not founder.startswith("v:")
        office = store.get(house, "headship")
        assert store.get(office, "house") == house and store.get(office, "rule") == store.get(f"{parent}-head", "rule")


def test_a_cadet_house_keeps_its_line_like_any_house(world):
    store = world.store
    for h in cadets(world):
        office = store.get(h, "headship")
        holder = store.get(office, "holder")
        if store.get(h, "extinct") is not None:
            assert holder is None
            continue
        assert holder and store.status(holder) == "active" and store.get(holder, "house") == h


def test_a_cadet_inherits_its_parents_polity_and_factions():
    sc = renascita._scenario(None, polities=True)
    sc = copy.deepcopy(sc)
    sc["params"].update(cadet_size=3, cadet_rate=0.6)  # (the draft polities set 12)
    e = renascita.new_engine(seed=7, scenario=sc)
    e.run(until=renascita.CAL.add(renascita.START, Span(years=15)))
    store = e.store
    houses = cadets(e)
    assert houses
    for h in houses:
        parent = store.get(h, "cadet_of")
        for group in store.ids("polity") + store.ids("faction"):
            members = store.get(group, "members") or []
            assert (h in members) == (parent in members), (h, group)


def test_the_draft_polities_branch():
    assert renascita._scenario(None, polities=True)["params"]["cadet_size"] == 12
    assert "cadet_size" not in renascita._scenario(None).get("params", {})
