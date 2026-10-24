"""The coarse fallbacks of S8 Part A (spec §7, #156), each tested on its own (the engine can't run coarse
yet, #157): a coarse step of N years stands in for N fine ones. And the derived stats (§6)."""

import copy

import pytest

from renasci import renascita
from renasci.core.calendar import Span
from renasci.core.engine import Engine
from renasci.core.systems import Ruleset
from renasci.people.scenario import synthesise
from renasci.people.world import people_ruleset
from renasci.relations import Diplomacy, over, rel_id
from renasci.war import War

CAL, START = renascita.CAL, renascita.START
EMPIRE, CLANS = "v:test-empire", "v:test-clans"
HOUSES = [h["id"] for h in renascita.SCENARIO["houses"]]


def scenario(relations):
    sc = copy.deepcopy(renascita._scenario(None))
    sc["polities"] = [
        {"id": EMPIRE, "name": "the Empire", "seat": "v:lions-rest", "members": HOUSES[:10], "control": ["v:pyrosia"],
         "ruler": f"{HOUSES[0]}-head", "government": "ruler"},
        {"id": CLANS, "name": "the Clans", "seat": "v:raining-bay", "members": HOUSES[10:], "control": ["v:flame-coast"],
         "ruler": f"{HOUSES[10]}-head", "government": "ruler"}]
    sc["relations"] = list(relations)
    return sc


def coarsely(cls, every):
    """`cls`, run as its coarse fallback once every `every` years (and not between)."""
    class Coarse(cls):
        def run(self, ctx):
            if (ctx.today.year - START.year) % every == 0:
                self.coarse_fallback(ctx, every)
    return Coarse()


def engine(sc, swap=None, seed=5):
    rs = people_ruleset("fourth_age", sc)
    systems = tuple(swap if swap is not None and s.name == swap.name else s for s in rs.systems)
    e = Engine(CAL, seed=seed, rulesets=[(START, Ruleset(rs.name, rs.version, systems, params=rs.params, forcers=rs.forcers,
                                                        disguises=rs.disguises, conservation=rs.conservation))])
    synthesise(e, sc, seed)
    return e


def test_over_is_exact_for_a_year_and_compounds():
    assert over(0.08, 1) == 0.08 and over(0.1, 5) == pytest.approx(1 - 0.9 ** 5)


def test_a_coarse_step_of_drift_lands_where_the_fine_years_would():
    sc = scenario([{"a": EMPIRE, "b": CLANS, "stance": "friendly", "trust": 0.4}])
    fine, coarse = engine(sc), engine(sc, coarsely(Diplomacy, 5))
    until = CAL.add(START, Span(years=4, days=359))
    fine.run(until=until)
    coarse.run(until=until)
    rid = rel_id(EMPIRE, CLANS)
    assert coarse.store.get(rid, "trust") == pytest.approx(fine.store.get(rid, "trust"), abs=0.05)


def test_a_coarse_war_step_fights_a_draw_for_each_of_its_years():
    sc = scenario([{"a": EMPIRE, "b": CLANS, "stance": "hostile", "trust": -1.0}])
    for seed in (5, 6, 7, 8, 9):
        e = engine(sc, coarsely(War, 5), seed)
        e.run(until=CAL.add(START, Span(years=29)))
        years = [ev for ev in e.events if ev.type == "polity.war_year"]
        if years:
            war = years[0].payload["war"]
            first = [ev for ev in years if ev.payload["war"] == war and ev.date == years[0].date]
            assert len(first) > 1 or e.store.get(war, "ended") == years[0].date.to_json()  # (more than one draw a step)
            assert len({ev.id for ev in years}) == len(years)  # (each notional year its own event)
            return
    pytest.skip("no coarse war in these seeds")


def test_a_step_is_at_least_a_year():
    for system in (Diplomacy(), War()):
        with pytest.raises(ValueError):
            system.step(None, 0)


def test_each_polity_gets_its_derived_stats():
    e = engine(scenario([]))
    e.run(until=CAL.add(START, Span(years=1)))
    for p in (EMPIRE, CLANS):
        assert e.store.get(p, "strength") > 0 and 0 <= e.store.get(p, "stability") <= 1 and e.store.get(p, "wealth") >= 1
    assert e.store.get(EMPIRE, "wealth") > e.store.get(CLANS, "wealth")  # (it holds more of Pyrosia)
    assert [ev for ev in e.events if ev.type == "polity.stats"]
