"""The S7 emergence test (S7 spec §10; epic #8): over a seeded century, in kin and the Fourth Age draft,
succession plots, court intrigue and vengeance emerge from drives, and the story finder finds sagas.
The test asserts the classes and their causes, not counts."""

import copy

import pytest

from renasci.analysis.stories import stories
from renasci.core.calendar import Date

YEARS = 100


def kin():
    from renasci.kin import SCENARIO, new_engine

    sc = copy.deepcopy(SCENARIO)  # kin's catalogue has one varied trait: every role reads it
    sc["params"]["traits"] = {"wits": "stature", "charm": "stature", "temper": "stature"}
    e = new_engine(scenario=sc)
    e.run(until=Date(1, YEARS, 359))
    return e


def fourth_age():
    from renasci import renascita

    e = renascita.new_engine()
    start = renascita.START
    e.run(until=Date(start.age, start.year + YEARS, 359))
    return e


@pytest.fixture(scope="module", params=[kin, fourth_age], ids=["kin", "fourth_age"])
def world(request):
    return request.param()


def causes(ev, kind):
    return {c.ref for c in ev.causes if c.kind == kind}


def test_a_succession_plot_is_schemed(world):
    store = world.store
    assert any(store.get(store.get(s, "ambition"), "class") == "Seize" for s in store.ids("scheme"))


def test_court_intrigue_courts_favour_for_standing(world):
    store = world.store
    assert any(ev.type == "people.action" and ev.payload["action"] == "CourtFavour"
               and any(store.get(a, "class") == "Standing" for a in causes(ev, "ambition"))
               for ev in world.events)


def test_vengeance_is_born_of_an_attributed_killing(world):
    killings = {ev.id for ev in world.events if ev.type == "people.death" and ev.roles.get("killer")}
    assert any(ev.type == "people.ambition_formed" and ev.payload["class"] == "Vengeance"
               and causes(ev, "event") & killings for ev in world.events)


def test_the_story_finder_finds_sagas(world):
    found = stories(world.pending()["events"], world.store.to_json())
    assert found["sagas"] and any(a["class"] in ("Seize", "Vengeance") for a in found["arcs"])
