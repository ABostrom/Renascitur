"""Famine (S10 spec §3, #129): each season a town eats from its stores; short of food, the masses die of
hunger (the young and the old first) and notables' hazards rise, and the town is in famine until it eats again."""

import pytest

from renasci import ecology, renascita
from renasci.core.calendar import Date, Span
from renasci.core.ripples import Ripple
from renasci.people import crafts
from renasci.people.population import BAND_COLUMNS, band_column

TOWN = "v:lux-oescus"


def famine_world(seed=3, years=4, ripples=(), **famine):
    sc = renascita._scenario(None, crafts=True)
    sc["params"]["ecology"] = {**ecology.DEFAULT, "famine": {**ecology.FAMINE, **famine}}
    e = renascita.new_engine(seed=seed, scenario=sc, ripples=ripples)
    e.run(until=renascita.CAL.add(renascita.START, Span(years=years)))
    return e


def blighted(years=4, harvests=2):
    region = famine_world(years=0).store.get(TOWN, "region")
    until = [renascita.START.age, renascita.START.year + harvests - 1, 359]
    return famine_world(years=years, ripples=[Ripple("b", "structural", Date(renascita.START.age, renascita.START.year, 30),
                                                     region, {"harvest": True, "factor": 0.0, "until": until})])


@pytest.fixture(scope="module")
def fed():
    return famine_world()


@pytest.fixture(scope="module")
def starved():
    return blighted()


def test_towns_start_with_a_years_stores_and_eat_from_them(fed):
    for s in fed.store.ids("settlement"):
        assert int(fed.store.read_column("goods:food:initial", [s])[0]) > 0
        assert int(fed.store.read_column("goods:food:used", [s])[0]) > 0
        assert crafts.balance(fed.store, s, "food") == 0, s
    assert [x for x in fed.events if x.type == "goods.eaten"]


def test_a_fed_world_keeps_its_people(fed):
    assert fed.check_conservation() == []
    assert not [x for x in fed.events if x.type == "famine.began" and x.roles["settlement"][0] == TOWN]


def test_blighted_harvests_bring_famine_and_hunger_deaths(starved):
    began = [x for x in starved.events if x.type == "famine.began" and x.roles["settlement"][0] == TOWN]
    assert began
    eaten = [x for x in starved.events if x.type == "goods.eaten" and x.roles["settlement"][0] == TOWN]
    assert sum(x.payload["died"] for x in eaten) > 0
    assert all(x.payload["died"] == 0 for x in eaten if x.payload["short"] == 0)
    assert starved.check_conservation() == []  # (the dead leave the masses, their alleles with them)
    for s in starved.store.ids("settlement"):
        assert crafts.balance(starved.store, s, "food") == 0, s


def test_a_famine_is_caused_by_the_failed_harvest(starved):
    began = next(x for x in starved.events if x.type == "famine.began" and x.roles["settlement"][0] == TOWN)
    by_id = {x.id: x for x in starved.events}
    kinds = {by_id[c.ref].type for c in began.causes if c.kind == "event" and c.ref in by_id}
    assert "harvest.failed" in kinds


def test_a_famine_ends_when_the_town_eats_again():
    e = blighted(years=5, harvests=1)
    town = [x for x in e.events if x.type in ("famine.began", "famine.ended") and x.roles["settlement"][0] == TOWN]
    assert [x.type for x in town][:2] == ["famine.began", "famine.ended"]


def test_hunger_kills_the_young_and_the_old_first():
    rates = ecology.hunger_rates(1.0)
    assert rates[0] > rates[5] and rates[-1] > rates[5]
    assert all(0 < r <= 1 for r in rates)
    assert ecology.hunger_rates(0.0) == [0.0] * len(rates)


def test_without_famine_nobody_eats():
    sc = renascita._scenario(None, crafts=True)
    sc["params"]["ecology"] = dict(ecology.DEFAULT)
    e = renascita.new_engine(seed=3, scenario=sc)
    e.run(until=renascita.CAL.add(renascita.START, Span(years=1)))
    assert not [x for x in e.events if x.type == "goods.eaten"]
    assert int(e.store.read_column("goods:food:initial", [TOWN])[0]) == 0


def test_stores_past_their_keep_spoil(fed):
    eaten = [x for x in fed.events if x.type == "goods.eaten"]
    assert sum(x.payload["spoiled"] for x in eaten) > 0  # (a good year's surplus doesn't keep for ever)
    for s in fed.store.ids("settlement"):
        assert int(fed.store.read_column("goods:food:destroyed", [s])[0]) == sum(
            x.payload["spoiled"] for x in eaten if x.roles["settlement"][0] == s)


def test_an_empty_famine_catalogue_means_the_defaults():
    sc = renascita._scenario(None, crafts=True)
    sc["params"]["ecology"] = {**ecology.DEFAULT, "famine": {}}
    e = renascita.new_engine(seed=3, scenario=sc)
    assert int(e.store.read_column("goods:food:initial", [TOWN])[0]) > 0


def test_stores_must_keep():
    sc = renascita._scenario(None, crafts=True)
    sc["params"]["ecology"] = {**ecology.DEFAULT, "famine": {"stores": 2, "keep": 1.5}}
    with pytest.raises(ValueError):
        renascita.new_engine(seed=3, scenario=sc)


def test_a_coarse_step_reaps_usual_years_past_its_first_and_leaves_no_hunger():
    from renasci.core.engine import Engine
    from renasci.core.lod import Resolution, ResolutionPolicy
    from renasci.people.scenario import synthesise

    sc = renascita._scenario(None, crafts=True)
    sc["params"]["ecology"] = {**ecology.DEFAULT, "famine": {}}
    e = Engine(renascita.CAL, seed=3, rulesets=renascita.rulesets(sc),
               resolution=ResolutionPolicy(default=Resolution.coarse(Span(years=5))))
    synthesise(e, sc, 3)
    e.run(until=renascita.CAL.add(renascita.START, Span(years=9, days=359)))
    for x in e.events:
        if x.type.startswith("harvest."):
            assert x.payload["factor"] >= 0.8 * ecology.MEAN  # (one year's weather of five)
    assert all(not e.store.get(s, "hunger") for s in e.store.ids("settlement"))
    assert e.check_conservation() == []
