"""Disease (S10 §4, #128): it reads conditions and knows nothing of what made them."""

import pathlib

import pytest

from renasci import ecology, renascita
from renasci.core.calendar import Span


def scenario(disease=None, **eco):
    sc = renascita._scenario(None, crafts=True)
    sc["params"]["ecology"] = {**ecology.DEFAULT, "famine": {}, **eco}
    if disease is not None:
        sc["params"]["ecology"]["disease"] = disease
    return sc


def run(sc, seed=3, years=6):
    e = renascita.new_engine(seed=seed, scenario=sc)
    e.run(until=renascita.CAL.add(renascita.START, Span(years=years)))
    return e


def of(e, t):
    return [x for x in e.events if x.type == t]


STRIKES = [{**ecology.DISEASES[0], "base": 0.3, "filth": 0.0}]  # (one will come, whatever the town's state)


@pytest.fixture(scope="module")
def struck():
    return run(scenario(disease=STRIKES))


def test_an_outbreak_runs_its_course_and_kills(struck):
    assert of(struck, "disease.outbreak") and of(struck, "disease.season")
    assert sum(x.payload["died"] for x in of(struck, "disease.season")) > 0
    assert of(struck, "disease.ended")
    assert struck.check_conservation() == []


def test_a_towns_sick_and_immune_never_outnumber_it(struck):
    from renasci.people.population import BAND_COLUMNS

    for s in struck.store.ids("settlement"):
        people = sum(int(struck.store.read_column(c, [s])[0]) for c in BAND_COLUMNS)
        for v in (struck.store.get(s, "disease") or {}).values():
            assert v["sick"] + v["immune"] <= people


def test_a_town_remembers_a_plague():
    assert ecology.remembered(1000, 0.02, 0) == 1000
    assert ecology.remembered(1000, 0.1, 2) == 810
    e = run(scenario(disease=STRIKES), years=10)
    ended = [s for s in e.store.ids("settlement") if e.store.get(s, "immunity")]
    assert ended and all(e.store.get(s, "immunity")["flux"][0] > 0 for s in ended)


def test_a_notable_can_die_of_it():
    e = run(scenario(disease=[{**STRIKES[0], "lethality": 0.9}]), years=8)
    assert [x for x in of(e, "people.death") if x.payload["cause"] == "the flux"]


def test_the_dead_lying_raise_the_odds_of_an_outbreak():
    spec = {"base": 0.001, "filth": 0.5}
    assert ecology.outbreak_odds(spec, 0.0, 1000) == 0.001
    assert ecology.outbreak_odds(spec, 200.0, 1000) == pytest.approx(0.101)
    assert ecology.outbreak_odds(spec, 1e9, 1000) <= ecology.MOST_LIKELY


def test_hunger_makes_it_spread_faster():
    fed, hungry = ecology.catching(1.4, 50, 1000, 0.0), ecology.catching(1.4, 50, 1000, 1.0)
    assert 0 < fed < hungry < 1
    assert ecology.catching(1.4, 0, 1000, 1.0) == 0.0
    assert ecology.catching(1.4, 50, 0, 1.0) == 0.0


def test_unburied_dead_breed_plague_and_buried_dead_do_not():
    bred = [{**ecology.DISEASES[0], "base": 0.0, "filth": 2.0}]
    lying = run(scenario(disease=bred, burial={"bury": 0, "rot": 0, "winter": 0}), years=4)
    cleared = run(scenario(disease=bred, burial={"bury": 1e9, "rot": 1, "winter": 1}), years=4)
    assert of(lying, "disease.outbreak") and not of(cleared, "disease.outbreak")


def test_an_outbreak_cites_the_deaths_behind_it():
    bred = [{**ecology.DISEASES[0], "base": 0.0, "filth": 2.0}]
    e = run(scenario(disease=bred, burial={"bury": 0, "rot": 0, "winter": 0}), years=4)
    types = {x.id: x.type for x in e.events}
    out = of(e, "disease.outbreak")[0]
    assert {types[c.ref] for c in out.causes if c.kind == "event"} & {"people.population", "people.death", "goods.eaten"}


def test_one_who_brings_it_may_start_it():
    assert ecology.arrival_odds(0.0) == 0.0
    assert ecology.arrival_odds(1.0) == pytest.approx(ecology.TAKES)
    assert ecology.arrival_odds(1.0) < ecology.arrival_odds(3.0) < 1


def test_a_plague_walks_the_roads_and_its_path_can_be_read():
    e = run(scenario(disease=[{**STRIKES[0], "base": 0.02}]), years=10)
    by_id = {x.id: x for x in e.events}
    spread = [x for x in of(e, "disease.outbreak") for c in x.causes
              if c.kind == "event" and c.ref in by_id and by_id[c.ref].type == "disease.season"
              and by_id[c.ref].roles["settlement"] != x.roles["settlement"]]
    assert spread


def test_the_carried_is_spent_whether_it_takes_or_not():
    e = run(scenario(disease=[{**STRIKES[0], "base": 0.02}]), years=10)
    assert of(e, "disease.passed")
    for s in e.store.ids("settlement"):
        assert (e.store.get(s, "level:carried:flux") or 0.0) < 4  # (a season's worth at most: nothing piles up)


def test_the_sick_cannot_work():
    assert ecology.able_share(0.0, 0.0, 0.5) == 0.5


def test_a_towns_ill_share_tracks_its_sick_and_clears():
    e = run(scenario(disease=STRIKES), years=10)
    for s in e.store.ids("settlement"):
        assert bool(e.store.get(s, "ill")) == bool(e.store.get(s, "disease"))


def test_off_means_off():
    e = run(scenario(disease=False), years=2)
    assert not of(e, "disease.outbreak") and not of(e, "disease.season")


def test_coarse_years_still_know_plague():
    from renasci.core.engine import Engine
    from renasci.core.lod import Resolution, ResolutionPolicy
    from renasci.people.scenario import synthesise

    sc = scenario(disease=STRIKES)
    e = Engine(renascita.CAL, seed=3, rulesets=renascita.rulesets(sc),
               resolution=ResolutionPolicy(default=Resolution.coarse(Span(years=5))))
    synthesise(e, sc, 3)
    e.run(until=renascita.CAL.add(renascita.START, Span(years=16)))
    assert of(e, "disease.outbreak") and of(e, "disease.ended")
    assert sum(x.payload["died"] for x in of(e, "disease.season")) > 0
    assert all(not e.store.get(s, "disease") for s in e.store.ids("settlement"))
    assert e.check_conservation() == []


def test_a_catalogue_is_checked():
    crafts = renascita._scenario(None, crafts=True)["params"]["crafts"]
    with pytest.raises(ValueError, match="disease"):
        ecology.check({**ecology.DEFAULT, "disease": 3}, crafts)
    with pytest.raises(ValueError, match="id and a name"):
        ecology.check({**ecology.DEFAULT, "disease": [{"id": "x"}]}, crafts)
    with pytest.raises(ValueError, match="differ"):
        ecology.check({**ecology.DEFAULT, "disease": [ecology.DISEASES[0], ecology.DISEASES[0]]}, crafts)
    with pytest.raises(ValueError, match="lethality"):
        ecology.check({**ecology.DEFAULT, "disease": [{**ecology.DISEASES[0], "lethality": 2}]}, crafts)


def test_nothing_that_kills_names_disease():
    src = pathlib.Path(ecology.__file__).parent
    for name in ("campaigns.py", "war.py", "people/population.py", "people/life.py"):
        assert "disease" not in (src / name).read_text(encoding="utf-8")
