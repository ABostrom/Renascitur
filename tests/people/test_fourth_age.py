"""The provisional Fourth Age scenario (#73): it synthesises, runs, and keeps its books."""

import pytest

from renasci.core.calendar import Date
from renasci.renascita import SCENARIO, new_engine
from renasci.worlds import get_world


@pytest.fixture(scope="module")
def world():
    e = new_engine()
    e.run(until=Date(4, 10, 359))
    return e


def test_it_is_marked_as_a_draft():
    assert SCENARIO["draft"] is True and "PROVISIONAL" in SCENARIO["about"]


def test_the_twelve_great_houses_are_founded_at_the_capital():
    e = new_engine()
    houses = e.store.ids("house")
    assert len(houses) == 12
    for h in houses:
        head = e.store.get(e.store.get(h, "headship"), "holder")
        assert e.store.get(head, "house") == h and e.store.get(h, "seat") == "v:lions-rest"


def test_ten_years_of_the_fourth_age_keep_their_books(world):
    assert world.check_conservation() == []
    types = {ev.type for ev in world.events}
    assert {"people.birth", "people.death", "people.marriage", "people.population"} <= types


def test_it_is_a_world_recipes_can_name():
    w = get_world("fourth_age")
    assert w.calendar.format(Date(4, 1, 0)) == "4A 1"
