"""Journeys along routes (S4 spec §5-6, #77): depart, the road, arrive; Flee, migration and presence."""

import copy

import pytest

from renasci import renascita
from renasci.core.calendar import Date, Span
from renasci.core.engine import Engine
from renasci.core.systems import Ruleset, System
from renasci.people import actions as A
from renasci.people import life, travel
from renasci.people.scenario import synthesise
from renasci.people.world import people_ruleset

START, CAL = renascita.START, renascita.CAL


def scenario(link_last=True, **params):
    """The Fourth Age's settlements in a line of 3-day roads (the last cut off unless `link_last`)."""
    sc = copy.deepcopy(renascita.SCENARIO)
    ids = [s["id"] for s in sc["settlements"]]
    pairs = list(zip(ids, ids[1:] if link_last else ids[1:-1]))
    sc["geography"] = {
        "regions": [{"id": r} for r in sorted({s["region"] for s in sc["settlements"]})],
        "places": [{"id": s["id"], "kind": "settlement", "region": s["region"]} for s in sc["settlements"]],
        "routes": [{"id": f"g:r{i}", "ends": [a, b], "days": 3, "kind": "road"} for i, (a, b) in enumerate(pairs)]}
    sc["params"] = {**sc["params"], "migration_rate": 0.0, **params}
    return sc


SEEN: dict = {}
PLAN: dict = {}  # what the probe does: {"day": Span, "do": callable(ctx)}


class Probe(System):
    """Runs PLAN's steps on their days (on_demand follow-ups of its first, daily-ish run)."""

    name, cadence, priority = "toy.probe", "yearly", 99
    reads = travel.READS | A.READS | life.DIE_READS | frozenset(
        {"ids:settlement", "ids:person", "residents", "place", "spouse", "offices", "born", "sex", "race", "status",
         "region", "capacity"}).union(*(a.reads for a in A.ACTIONS.values()))
    writes = travel.WRITES | life.DIE_WRITES | A.WRITES
    event_types = tuple({t.name: t for t in travel.EVENT_TYPES + life.DIE_EVENTS + A.EVENT_TYPES}.values())

    def run(self, ctx):
        if ctx.today != START:
            return
        for i, (after, _) in enumerate(PLAN["steps"]):
            ctx.schedule(after, "probe", entity="t:probe", payload={"i": i})

    def handle(self, ctx, activation):
        if activation.purpose == "arrive":
            travel.arrive(ctx, activation)
            return
        PLAN["steps"][activation.payload["i"]][1](ctx)


def engine(sc, steps, seed=7):
    PLAN["steps"] = steps
    SEEN.clear()
    rs = people_ruleset("fourth_age", sc)
    rs = Ruleset(rs.name, rs.version, rs.systems + (Probe(),), params=rs.params, forcers=rs.forcers,
                 disguises=rs.disguises, conservation=rs.conservation)
    e = Engine(renascita.CAL, seed=seed, rulesets=[(START, rs)])
    synthesise(e, sc, seed)
    return e, [(START, rs)]


def traveller(ctx, home):
    """An unmarried adult notable of `home` with no office."""
    return next(p for p in ctx.get(home, "residents") if ctx.get(p, "spouse") is None and not ctx.get(p, "offices")
                and A._adult(ctx, p))


def depart_two_hops(ctx):
    sc_ids = [s["id"] for s in renascita.SCENARIO["settlements"]]
    a, c = sc_ids[0], sc_ids[2]
    p, q = next((p, q) for p in ctx.get(a, "residents") for q in ctx.get(a, "residents")
                if p in A.Court()._free(ctx, q) and not ctx.get(p, "offices"))
    SEEN.update(person=p, suitor=q, a=a, c=c, courtable_before=True)
    SEEN["days"] = travel.depart(ctx, p, c, "test")
    SEEN["journey"] = dict(ctx.get(p, "journey"))


def look(key):
    def at(ctx):
        p = SEEN["person"]
        SEEN[key] = {"place": ctx.get(p, "place"), "journey": ctx.get(p, "journey"),
                     "in_a": p in ctx.get(SEEN["a"], "residents"), "in_c": p in ctx.get(SEEN["c"], "residents"),
                     "court": "suitor" in SEEN and p in A.Court()._free(ctx, SEEN["suitor"])}
    return at


def test_a_journey_departs_takes_the_routes_days_and_arrives():
    e, _ = engine(scenario(), [(Span(days=1), depart_two_hops), (Span(days=6), look("road")),
                               (Span(days=8), look("there"))])
    e.run(until=CAL.add(START, Span(days=20)))
    assert SEEN["days"] == 6 and SEEN["journey"]["path"][0] == SEEN["a"] and SEEN["journey"]["to"] == SEEN["c"]
    road, there = SEEN["road"], SEEN["there"]
    assert road["place"] == SEEN["a"] and road["in_a"] and not road["in_c"] and road["journey"]
    assert SEEN["courtable_before"] and not road["court"]  # courtable at home, not on the road
    assert there["place"] == SEEN["c"] and there["in_c"] and not there["in_a"] and there["journey"] is None
    dep = next(ev for ev in e.events if ev.type == "people.depart")
    arr = next(ev for ev in e.events if ev.type == "people.arrive")
    assert arr.date == CAL.add(dep.date, Span(days=6))
    assert any(c.kind == "event" and c.ref == dep.id for c in arr.causes)


def test_no_path_no_journey():
    def go(ctx):
        ids = [s["id"] for s in renascita.SCENARIO["settlements"]]
        p = traveller(ctx, ids[0])
        SEEN["days"] = travel.depart(ctx, p, ids[-1], "test")
        SEEN["journey"] = ctx.get(p, "journey")

    e, _ = engine(scenario(link_last=False), [(Span(days=1), go)])
    e.run(until=CAL.add(START, Span(days=3)))
    assert SEEN["days"] is None and SEEN["journey"] is None


def test_a_death_on_the_road_means_no_arrival():
    def kill(ctx):
        life.die(ctx, SEEN["person"], ctx.get(SEEN["person"], "place"), "a fall")

    e, _ = engine(scenario(), [(Span(days=1), depart_two_hops), (Span(days=3), kill), (Span(days=9), look("after"))])
    e.run(until=CAL.add(START, Span(days=20)))
    assert not SEEN["after"]["in_c"] and not any(ev.type == "people.arrive" for ev in e.events)
    assert SEEN["after"]["journey"] is None  # the death ends the journey
    death = next(ev for ev in e.events if ev.type == "people.death" and ev.roles["deceased"] == (SEEN["person"],))
    assert death.payload["cause"] == "a fall"


def test_a_checkpoint_mid_journey_arrives_on_the_same_day():
    steps = [(Span(days=1), depart_two_hops)]
    e, rulesets = engine(scenario(), steps)
    mid = CAL.add(START, Span(days=4))
    e.run_before(mid)
    e.clear_pending()
    cp = e.checkpoint(at=mid, segments=0)
    e.run(until=CAL.add(START, Span(days=20)))
    whole = next(ev for ev in e.events if ev.type == "people.arrive")
    r = Engine.restore(cp, renascita.CAL, rulesets, seed=7)
    r.run(until=CAL.add(START, Span(days=20)))
    again = next(ev for ev in r.events if ev.type == "people.arrive")
    assert (again.id, again.date) == (whole.id, whole.date) and r.state_hash() == e.state_hash()


def test_flee_crosses_regions_and_goes_by_road():
    def flee(ctx):
        ids = [s["id"] for s in renascita.SCENARIO["settlements"]]
        p = traveller(ctx, ids[0])
        region = ctx.get(ids[0], "region")
        SEEN["far"] = [s for s in A.Flee()._elsewhere(ctx, p) if ctx.get(s, "region") != region]
        A.Flee().succeed(ctx, p, None, None, None)
        SEEN["journey"] = ctx.get(p, "journey")
        SEEN["again"] = A.Flee().possible(ctx, p, None, None)

    e, _ = engine(scenario(flee_days=30), [(Span(days=1), flee)])
    e.run(until=CAL.add(START, Span(days=3)))
    assert SEEN["far"] and SEEN["journey"] and SEEN["journey"]["why"] == "flee"
    assert SEEN["again"] is False  # one journey at a time


def test_presence_adds_the_road_to_a_duel():
    def measure(ctx):
        ids = [s["id"] for s in renascita.SCENARIO["settlements"]]
        p, q = traveller(ctx, ids[0]), traveller(ctx, ids[2])
        near = next(x for x in ctx.get(ids[0], "residents") if x != p)
        SEEN.update(far=A.Duel().duration(ctx, p, q), near=A.Duel().duration(ctx, p, near),
                    letter=A.Petition().duration(ctx, p, q))

    e, _ = engine(scenario(), [(Span(days=1), measure)])
    e.run(until=CAL.add(START, Span(days=3)))
    assert SEEN == {"far": 30 + 6, "near": 30, "letter": A.Petition.duration_days}


def test_migration_moves_people_and_every_arrival_keeps_its_days():
    e = renascita.new_engine(seed=3, scenario=scenario(migration_rate=0.2))
    e.run(until=CAL.add(START, Span(years=3)))
    deps = {ev.roles["traveller"][0] + str(ev.date): ev for ev in e.events if ev.type == "people.depart"}
    arrs = [ev for ev in e.events if ev.type == "people.arrive"]
    assert arrs
    for arr in arrs:
        dep = next(d for d in deps.values() if any(c.ref == d.id for c in arr.causes))
        assert arr.date == CAL.add(dep.date, Span(days=dep.payload["days"]))
    assert e.store.get(arrs[0].roles["traveller"][0], "place") is not None


def test_without_geography_nobody_migrates_and_the_ruleset_is_unchanged():
    sc = copy.deepcopy(renascita.SCENARIO)
    sc.pop("geography")
    names = [s.name for s in people_ruleset("fourth_age", sc).systems]
    assert "people.migration" not in names
    assert "people.migration" in [s.name for s in people_ruleset("fourth_age", scenario()).systems]


def test_an_overdue_journey_is_completed_by_the_yearly_pass():
    def strand(ctx):  # a journey whose arrival was lost (a ruleset switch drops follow-ups)
        ids = [s["id"] for s in renascita.SCENARIO["settlements"]]
        p = traveller(ctx, ids[0])
        SEEN.update(person=p, a=ids[0], c=ids[1])
        ctx.emit("people.depart", {"traveller": (p,), "origin": (ids[0],), "destination": (ids[1],)},
                 purpose="depart", actor=p, payload={"days": 3, "why": "test"})
        ctx.set(p, "journey", {"from": ids[0], "to": ids[1], "path": [ids[0], ids[1]], "depart": ctx.today.to_json(),
                               "arrive": ctx.calendar.add(ctx.today, Span(days=3)).to_json(), "why": "test"})

    e, _ = engine(scenario(), [(Span(days=1), strand), (Span(years=1, days=10), look("later"))])
    e.run(until=CAL.add(START, Span(years=1, days=20)))
    assert SEEN["later"]["in_c"] and SEEN["later"]["journey"] is None


@pytest.mark.parametrize("bad", [{"flee_days": 0}, {"migration_rate": 2.0}])
def test_travel_params_are_checked(bad):
    with pytest.raises(ValueError):
        people_ruleset("fourth_age", scenario(**bad))


def test_a_flight_is_caused_by_the_attempt():
    def flee(ctx):
        ids = [s["id"] for s in renascita.SCENARIO["settlements"]]
        p = traveller(ctx, ids[0])
        SEEN["outcome"] = A.perform(ctx, A.Flee(), p, None, None, odds=1.0)

    e, _ = engine(scenario(), [(Span(days=1), flee)])
    e.run(until=CAL.add(START, Span(days=3)))
    attempt = next(ev for ev in e.events if ev.type == "people.action")
    dep = next(ev for ev in e.events if ev.type == "people.depart")
    assert SEEN["outcome"] == "success" and any(c.ref == attempt.id for c in dep.causes)


def test_an_unreachable_target_is_not_a_plan_and_not_an_attempt():
    def try_duel(ctx):
        ids = [s["id"] for s in renascita.SCENARIO["settlements"]]
        p, q = traveller(ctx, ids[0]), traveller(ctx, ids[-1])
        SEEN["feasible"] = A.Duel().feasible(ctx, p, q, None)
        SEEN["outcome"] = A.perform(ctx, A.Duel(), p, q)

    e, _ = engine(scenario(link_last=False), [(Span(days=1), try_duel)])
    e.run(until=CAL.add(START, Span(days=3)))
    assert SEEN == {"feasible": False, "outcome": "impossible"}


def test_migrants_go_where_there_is_room():
    def weigh(ctx):
        ids = [s["id"] for s in renascita.SCENARIO["settlements"]]
        crowded, empty = ids[0], ids[1]
        SEEN["crowded"] = travel._pull(ctx, crowded, 3)
        SEEN["empty"] = travel._pull(ctx, empty, 3)

    sc = scenario()
    sc["settlements"][0]["capacity"] = sc["settlements"][0]["masses"] + 100  # nearly full
    sc["settlements"][1]["capacity"] = (sc["settlements"][1]["masses"] + 100) * 10  # roomy
    e, _ = engine(sc, [(Span(days=1), weigh)])
    e.run(until=CAL.add(START, Span(days=3)))
    assert SEEN["empty"] > 3 * SEEN["crowded"]
