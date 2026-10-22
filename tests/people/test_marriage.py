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
    assert 0.7 * start <= len(alive) <= 1.8 * start  # neither dies out nor explodes (capacity is 2x the start)
    by_region = {}
    for p in alive:
        r = REGION_OF[e.store.get(p, "place")]
        by_region[r] = by_region.get(r, 0) + 1
    assert all(by_region.get(r, 0) >= 0.4 * start / 3 for r in ("t:Hollow", "t:Ridge", "t:Mere"))  # no region collapses
    children = sum(a < 15 for a in ages) / len(ages)
    old = sum(a >= 60 for a in ages) / len(ages)
    assert 0.15 <= children <= 0.55 and old <= 0.25 and max(ages) < 110


# ---------------------------------------------------------------- review fixes


@pytest.mark.parametrize("people, capacity, expected", [(5, 0, 0.0), (5, -3, 0.0), (0, 10, 1.5), (5, 10, 1.0),
                                                         (12, 10, 0.0), (5, None, 1.0)])
def test_crowding_handles_every_capacity(people, capacity, expected):
    from renasci.people.life import _crowding

    assert _crowding(people, capacity) == expected


def test_when_the_husband_moves_place_and_residents_agree():
    e = new_engine(people_per_settlement=12, residence="wife")
    e.run(until=Date(1, 25, 359))
    store = e.store
    moved = 0
    for ev in marriages(e):
        a, b = ev.roles["spouse"]
        husband, wife = (a, b) if store.get(a, "sex") == "m" else (b, a)
        if store.status(husband) == "active" and store.get(husband, "spouse") == wife:
            assert store.get(husband, "place") == store.get(wife, "place")
            assert husband in store.get(store.get(wife, "place"), "residents")
            moved += 1
    assert moved


@pytest.mark.parametrize("kw, message", [({"market_rate": "often"}, "market_rate"), ({"market_rate": True}, "market_rate"),
                                         ({"market_rate": 1.5}, "market_rate"), ({"kin_degree": -1}, "kin_degree"),
                                         ({"residence": "both"}, "residence")])
def test_world_params_are_checked(kw, message):
    from renasci.kin import CATALOGUE
    from renasci.people.life import world_params

    with pytest.raises(ValueError, match=message):
        world_params(RACES, CATALOGUE, **kw)
