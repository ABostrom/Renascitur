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


def test_the_twelve_great_houses_are_founded_at_their_seats():
    e = new_engine()
    houses = e.store.ids("house")
    assert len(houses) == 12
    seats = {h["id"]: h["seat"] for h in SCENARIO["houses"]}
    for h in houses:
        head = e.store.get(e.store.get(h, "headship"), "holder")
        assert e.store.get(head, "house") == h and e.store.get(h, "seat") == seats[h]
        assert e.store.get(head, "place") == seats[h]


def test_ten_years_of_the_fourth_age_keep_their_books(world):
    assert world.check_conservation() == []
    types = {ev.type for ev in world.events}
    assert {"people.birth", "people.death", "people.marriage", "people.population"} <= types


def test_it_is_a_world_recipes_can_name():
    w = get_world("fourth_age")
    assert w.calendar.format(Date(4, 1, 0)) == "4A 1"


# ---------------------------------------------------------------- review fixes


def test_names_and_seats_match_the_vault():
    from pathlib import Path

    vault = Path(__file__).parents[2] / "docs" / "Realms" / "Renascita"
    notes = {p.stem for p in vault.rglob("*.md")}
    for s in SCENARIO["settlements"]:
        assert s["name"] in notes, f"{s['name']} has no vault note"
    for h in SCENARIO["houses"]:
        assert f"House {h['name']}" in notes, f"House {h['name']} has no vault note"
    seat = {h["name"]: h["seat"] for h in SCENARIO["houses"]}
    assert seat["Sivis"] == seat["Kundarak"] == "v:lux-oescus" and seat["Orien"] == "v:port-ardere"
    race = {s["id"]: s["race"] for s in SCENARIO["settlements"]}
    assert race["v:lions-rest"] == "r:leonin" and race["v:magnus-rest"] == "r:dwarf"


def test_a_scenario_names_its_own_start():
    import copy

    later = copy.deepcopy(SCENARIO)
    later["start"] = [4, 100, 0]
    e = new_engine(scenario=later)
    assert e.start == Date(4, 100, 0)
    e.run(until=Date(4, 101, 359))
    assert e.check_conservation() == []


def test_a_checkpoint_replays_the_same_history():
    from renasci.core.canon import digest

    whole = new_engine()
    whole.run(until=Date(4, 8, 359))
    e = new_engine()
    at = Date(4, 5, 90)
    e.run_before(at)
    prefix = e.pending()["events"]
    e.clear_pending()
    restored = get_world("fourth_age").restore(e.checkpoint(at=at, segments=0), 1234)
    restored.run(until=Date(4, 8, 359))
    assert digest(prefix + restored.pending()["events"]) == digest(whole.pending()["events"])
    assert restored.state_hash() == whole.state_hash()
