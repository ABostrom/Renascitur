"""Marriage (S3 spec §4.4) and a population that holds up over 250 years (#66's deferred check)."""

import pytest

from renasci.analysis.divergence import analyse
from renasci.core.calendar import Date
from renasci.core.ripples import Ripple
from renasci.kin import REGION_OF, RACES, new_engine
from renasci.people.races import Race, age_years

END = Date(1, 40, 359)
RACE = {r["id"]: Race.from_json(r) for r in RACES}


@pytest.fixture(scope="module")
def world():
    e = new_engine(people_per_settlement=12)
    e.full_reads = True
    e.run(until=END)
    return e


def marriages(e):
    return [ev for ev in e.events if ev.type == "people.marriage"]


def ancestors(store, person, depth):
    out, frontier = set(), {person}
    for _ in range(depth):
        frontier = {p for x in frontier for p in (store.get(x, "mother"), store.get(x, "father")) if p}
        out |= frontier
    return out


def test_people_marry(world):
    assert len(marriages(world)) > 10


def test_marriages_join_eligible_unrelated_people(world):
    store = world.store
    for ev in marriages(world):
        a, b = ev.roles["spouse"]
        assert {store.get(a, "sex"), store.get(b, "sex")} == {"f", "m"}
        for p in (a, b):
            lo, hi = RACE[store.get(p, "race")].marriage
            assert lo <= age_years(world.calendar, store.get(p, "born"), ev.date) <= hi
        assert a not in ancestors(store, b, 2) and b not in ancestors(store, a, 2)
        assert not ancestors(store, a, 2) & ancestors(store, b, 2)  # no shared grandparent or closer


def test_the_wife_moves_to_her_husband(world):
    store = world.store
    for ev in marriages(world):
        a, b = ev.roles["spouse"]
        husband, wife = (a, b) if store.get(a, "sex") == "m" else (b, a)
        if store.status(husband) == "active" and store.status(wife) == "active" and store.get(wife, "spouse") == husband:
            assert store.get(wife, "place") == store.get(husband, "place")
            assert wife in store.get(store.get(husband, "place"), "residents")


def test_the_widowed_can_marry_again(world):
    counts = {}
    for ev in marriages(world):
        for p in ev.roles["spouse"]:
            counts[p] = counts.get(p, 0) + 1
    assert max(counts.values()) >= 2


def test_markets_are_regional_and_a_ripple_stays_in_its_region(world):
    death = next(ev for ev in world.events if ev.type == "people.death" and 10 <= ev.date.year <= 20
                 and 20 <= ev.payload["age"] <= 40)
    target = death.roles["deceased"][0]
    region = REGION_OF[death.place]
    variant = new_engine(people_per_settlement=12, ripples=[
        Ripple("r1", "protect", Date(1, death.date.year - 1, 0), target, {"until": [1, 40, 359]})])
    variant.full_reads = True
    variant.run(until=END)
    report = analyse(world.pending(), variant.pending(), world.store.to_json(), variant.store.to_json(),
                     ripples=["r1"])
    assert report["divergent_events"] > 0
    assert report["unexplained_events"] == report["unexplained_entities"] == report["unexplained_cells"] == 0
    scopes = {ev["id"]: ev["scope"] for ev in world.pending()["events"] + variant.pending()["events"]}
    d = report["divergent"]
    touched = {scopes[i] for i in d["only_baseline"] + d["only_variant"] + d["changed"]} - {None}
    assert touched and all(REGION_OF.get(s, s) == region for s in touched)


def test_a_population_holds_up_over_250_years():
    e = new_engine(people_per_settlement=20)  # smaller closed markets run out of unrelated partners
    start = len(e.store.ids("person"))
    e.run(until=Date(1, 250, 359))
    alive = [p for p in e.store.ids("person") if e.store.status(p) == "active"]
    ages = [age_years(e.calendar, e.store.get(p, "born"), Date(1, 250, 359)) for p in alive]
    assert 0.5 * start <= len(alive) <= 3 * start  # neither dies out nor explodes
    children = sum(a < 15 for a in ages) / len(ages)
    old = sum(a >= 60 for a in ages) / len(ages)
    assert 0.15 <= children <= 0.55 and old <= 0.25 and max(ages) < 110
