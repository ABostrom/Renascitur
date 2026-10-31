"""Every death meets at one point (vision spec §7): corpses are the sum of a town's dead, whatever killed them."""

import pytest

from renasci import ecology, renascita
from renasci.core.calendar import Span


def scenario(**eco):
    sc = renascita._scenario(None, crafts=True)
    sc["params"]["ecology"] = {**ecology.DEFAULT, "famine": {}, **eco}
    return sc


def run(sc, seed=3, years=6):
    e = renascita.new_engine(seed=seed, scenario=sc)
    e.run(until=renascita.CAL.add(renascita.START, Span(years=years)))
    return e


def corpses(e, s):
    return float(e.store.get(s, "level:corpses") or 0.0)


@pytest.fixture(scope="module")
def world():
    return run(scenario(burial={"bury": 0, "rot": 0, "winter": 0}))  # (nobody clears them: the sum shows)


def test_a_towns_corpses_are_all_its_dead(world):
    towns = world.store.ids("settlement")
    assert sum(corpses(world, s) for s in towns) > 0
    for s in towns:
        assert corpses(world, s) == int(world.store.read_column("flow:died", [s])[0]), s


def test_the_living_bury_their_dead_and_it_costs_them_work():
    e = run(scenario(), years=3)
    buried = [x for x in e.events if x.type == "burial.season"]
    assert buried and any(x.payload["buried"] > 0 and x.payload["labour"] > 0 for x in buried)
    assert all(corpses(e, s) < int(e.store.read_column("flow:died", [s])[0]) for s in e.store.ids("settlement"))
    assert e.check_conservation() == []


def test_a_burial_cites_the_deaths_it_clears():
    e = run(scenario(), years=2)
    buried = next(x for x in e.events if x.type == "burial.season" and x.payload["buried"])
    types = {x.id: x.type for x in e.events}
    assert {types[c.ref] for c in buried.causes if c.kind == "event"} & {"people.population", "people.death"}


def test_with_burial_off_no_town_keeps_corpses():
    e = run(scenario(burial=False), years=2)
    assert not [x for x in e.events if x.type == "burial.season"]
    assert all(e.store.get(s, "level:corpses") is None for s in e.store.ids("settlement"))


def test_coarse_years_leave_no_false_disaster_behind_them():
    from renasci.core.engine import Engine
    from renasci.core.lod import Resolution, ResolutionPolicy
    from renasci.people.scenario import synthesise

    sc = scenario()
    e = Engine(renascita.CAL, seed=3, rulesets=renascita.rulesets(sc),
               resolution=ResolutionPolicy(default=Resolution.coarse(Span(years=5))))
    synthesise(e, sc, 3)
    e.run(until=renascita.CAL.add(renascita.START, Span(years=16)))
    buried = [x for x in e.events if x.type == "burial.season"]
    assert buried and all(x.payload["left"] == 0 and x.payload["labour"] == 0 for x in buried)
    assert all(not e.store.get(s, "labour") for s in e.store.ids("settlement"))


def test_burying_takes_hands_in_proportion_up_to_a_limit():
    assert ecology.burying(0.0, 100.0, 4.0) == (0.0, 0.0)
    assert ecology.burying(40.0, 100.0, 4.0) == (0.1, 40.0)
    share, buried = ecology.burying(4000.0, 100.0, 4.0)
    assert share == ecology.SPARE and buried == 200.0  # (too many: some lie unburied)
    assert ecology.burying(40.0, 100.0, 0.0) == (0.0, 0.0)


def test_who_buries_or_starves_does_not_reap():
    assert ecology.able_share(0.0, 0.0) == 1.0
    assert ecology.able_share(0.5, 0.0) == 0.5
    assert ecology.able_share(0.5, 1.0) == 0.25


def test_burial_is_checked():
    with pytest.raises(ValueError, match="burial"):
        ecology.check({**ecology.DEFAULT, "burial": 3}, renascita._scenario(None, crafts=True)["params"]["crafts"])
    ecology.check({**ecology.DEFAULT, "burial": False}, renascita._scenario(None, crafts=True)["params"]["crafts"])
    crafts = renascita._scenario(None, crafts=True)["params"]["crafts"]
    with pytest.raises(ValueError, match="burial.bury"):
        ecology.check({**ecology.DEFAULT, "burial": {"bury": -1}}, crafts)
    with pytest.raises(ValueError, match="burial.rot"):
        ecology.check({**ecology.DEFAULT, "burial": {"rot": 3}}, crafts)
