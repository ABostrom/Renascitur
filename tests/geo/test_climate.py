"""Climate and harvests (S10 spec §2, #127): each region's weather a season at a time, and food reaped once a
year by it; a bad year is a failed harvest, and a ripple can blight one."""

import pytest

from renasci import ecology, renascita
from renasci.core.calendar import Date, Span
from renasci.core.ripples import Ripple
from renasci.people import crafts


def climate_world(seed=3, years=6, ripples=(), **ecology_params):
    sc = renascita._scenario(None, crafts=True)
    sc["params"]["ecology"] = {**ecology.DEFAULT, **ecology_params}
    e = renascita.new_engine(seed=seed, scenario=sc, ripples=ripples)
    e.run(until=renascita.CAL.add(renascita.START, Span(years=years)))
    return e


@pytest.fixture(scope="module")
def world():
    return climate_world()


def test_the_weather_is_drawn_every_season_for_every_region(world):
    seasons = [x for x in world.events if x.type == "climate.season"]
    regions = world.store.ids("region")
    assert {x.roles["region"][0] for x in seasons} == set(regions)
    per = {}
    for x in seasons:
        per.setdefault(x.roles["region"][0], []).append(x)
    assert all(len(v) >= 4 * 5 for v in per.values())  # (four seasons a year)
    for x in seasons:
        assert abs(x.payload["warm"]) < 6 and abs(x.payload["wet"]) < 6


def test_a_drought_lasts():
    assert ecology.anomaly(2.0, 0.0, persist=0.5, spread=1.0) == pytest.approx(1.0)  # (half of it carries)
    assert ecology.anomaly(0.0, 1.0, persist=0.0, spread=2.0) == pytest.approx(2.0)


def test_good_weather_feeds_and_bad_weather_fails():
    assert ecology.factor(0.0, 0.0) > 1.0
    assert ecology.factor(-0.5, 0.5) > ecology.FAILED
    assert ecology.factor(-1.5, -2.5) < ecology.FAILED  # (a cold drought)
    assert 0.0 <= ecology.factor(-9.0, 9.0) <= ecology.factor(0.0, 0.0)


def test_food_is_reaped_at_harvest_not_through_the_year(world):
    for x in world.events:
        if x.type == "goods.yield":
            assert "food" not in x.payload["produced"]  # (the harvest replaces S9's yearly food)
    reaped = [x for x in world.events if x.type in ("harvest.reaped", "harvest.failed")]
    assert reaped
    assert {renascita.CAL.season_name(x.date) for x in reaped} == {"Autumn"}
    by_id = {x.id: x for x in world.events}
    for x in reaped:  # (each caused by its region's weather this season)
        kinds = {by_id[c.ref].type for c in x.causes if c.kind == "event" and c.ref in by_id}
        assert "climate.season" in kinds


def test_the_ledger_still_balances_with_harvests(world):
    for s in world.store.ids("settlement"):
        assert crafts.balance(world.store, s, "food") == 0, s
    produced = sum(int(world.store.read_column("goods:food:produced", [s])[0]) for s in world.store.ids("settlement"))
    assert produced > 0


def test_a_harvest_fails_in_bad_weather_and_says_so():
    e = climate_world(seed=3, years=8, climate={"*": {"spread": 3.0}})  # (a wild climate: failures come)
    failed = [x for x in e.events if x.type == "harvest.failed"]
    assert failed
    assert all(x.payload["factor"] < ecology.FAILED for x in failed)


def test_a_blight_ripple_fails_a_region_harvest():
    town = "v:lux-oescus"
    base = climate_world(years=2)
    region = base.store.get(town, "region")
    r = Ripple("blight", "structural", Date(renascita.START.age, renascita.START.year, 30), region,
               {"harvest": True, "factor": 0.2, "why": "a blight on the wheat"})
    e = climate_world(years=2, ripples=[r])
    failed = [x for x in e.events if x.type == "harvest.failed" and x.roles["settlement"][0] == town]
    assert failed and failed[0].payload["factor"] <= 0.2
    by_id = {x.id: x for x in e.events}
    seen, todo = set(), [c.ref for c in failed[0].causes if c.kind == "event"]
    found_ripple = any(c.kind == "ripple" for c in failed[0].causes)
    while todo and not found_ripple:  # (it descends from the ripple)
        x = by_id.get(todo.pop())
        if x is None or x.id in seen:
            continue
        seen.add(x.id)
        found_ripple = any(c.kind == "ripple" for c in x.causes)
        todo += [c.ref for c in x.causes if c.kind == "event"]
    assert found_ripple
    later = [x for x in e.events if x.type in ("harvest.reaped", "harvest.failed")
             and x.roles["settlement"][0] == town and x.date.year > failed[0].date.year]
    assert all(x.payload["factor"] > 0.2 for x in later)  # (one harvest, unless it says until)


@pytest.mark.parametrize("params", [{"harvest": True}, {"harvest": True, "factor": 1.5},
                                    {"harvest": True, "factor": "low"}])
def test_a_harvest_ripple_needs_a_factor(params):
    with pytest.raises(ValueError):
        Ripple("r", "structural", renascita.START, "v:pyrosia", params).check()


def test_ecology_needs_the_harvest_material():
    sc = renascita._scenario(None, crafts=True)
    sc["params"]["ecology"] = {**ecology.DEFAULT, "harvest": {"season": "Autumn", "material": "mithril"}}
    with pytest.raises(ValueError):
        renascita.new_engine(seed=1, scenario=sc)


@pytest.mark.parametrize("step", [1, 3])
def test_a_coarse_step_reaps_its_years(step):
    from renasci.core.engine import Engine
    from renasci.core.lod import Resolution, ResolutionPolicy
    from renasci.people.scenario import synthesise

    sc = renascita._scenario(None, crafts=True)
    sc["params"]["ecology"] = dict(ecology.DEFAULT)
    e = Engine(renascita.CAL, seed=3, rulesets=renascita.rulesets(sc),
               resolution=ResolutionPolicy(default=Resolution.coarse(Span(years=step))))
    synthesise(e, sc, 3)
    e.run(until=renascita.CAL.add(renascita.START, Span(years=5, days=359)))
    reaped = [x for x in e.events if x.type in ("harvest.reaped", "harvest.failed")]
    assert len({x.date.year for x in reaped}) == 6 // step  # (once a step, at its start)
    for s in e.store.ids("settlement"):
        assert crafts.balance(e.store, s, "food") == 0, s


def test_a_blight_after_the_harvest_falls_on_next_years():
    town = "v:lux-oescus"
    region = climate_world(years=1).store.get(town, "region")
    r = Ripple("late", "structural", Date(renascita.START.age, renascita.START.year, 300), region,
               {"harvest": True, "factor": 0.1})
    e = climate_world(years=3, ripples=[r])
    h = {x.date.year: x.payload["factor"] for x in e.events
         if x.type.startswith("harvest.") and x.roles["settlement"][0] == town}
    assert h[renascita.START.year + 1] <= 0.1  # (the next harvest, not none)
    assert h[renascita.START.year + 2] > 0.1


def test_a_blight_in_a_coarse_step_still_falls():
    from renasci.core.engine import Engine
    from renasci.core.lod import Resolution, ResolutionPolicy
    from renasci.people.scenario import synthesise

    sc = renascita._scenario(None, crafts=True)
    sc["params"]["ecology"] = dict(ecology.DEFAULT)
    probe = climate_world(years=1)
    region = probe.store.get("v:lux-oescus", "region")
    e = Engine(renascita.CAL, seed=3, rulesets=renascita.rulesets(sc),
               resolution=ResolutionPolicy(default=Resolution.coarse(Span(years=5))))
    synthesise(e, sc, 3)
    e.apply_ripples([Ripple("b", "structural", Date(renascita.START.age, renascita.START.year + 1, 30), region,
                            {"harvest": True, "factor": 0.1})])
    e.run(until=renascita.CAL.add(renascita.START, Span(years=9, days=359)))
    blight = next(x.id for x in e.events if x.type == "geo.changed")
    hit = [x for x in e.events if x.type.startswith("harvest.") and any(c.ref == blight for c in x.causes)]
    assert hit and {x.date.year for x in hit} == {renascita.START.year + 5}  # (the next step: its year was reaped)
    assert all(x.payload["factor"] > 0.1 for x in hit)  # (one of its five years blighted, not all)


@pytest.mark.parametrize("until", ["4A 3", [4, 3], [renascita.START.age, renascita.START.year - 1, 0]])
def test_a_blight_until_must_be_a_date_after_it(until):
    with pytest.raises(ValueError):
        Ripple("r", "structural", renascita.START, "v:pyrosia", {"harvest": True, "factor": 0.5, "until": until}).check()
