"""Secede, Rally and Revolt (S8 spec §9, #158): a house seated in a governed town wants out; it rallies
another house to its side, then rises: a new realm at its seat, and a war to crush it."""

import copy

from renasci import renascita, war
from renasci.core.calendar import Span
from renasci.core.systems import Ruleset, System
from renasci.people import actions as A
from renasci.people import courts, houses, travel
from renasci.people.actions import ACTIONS, perform
from renasci.people.ambitions import LIBRARY
from renasci.people.planner import holds

CAL, START = renascita.CAL, renascita.START
EMPIRE, CLANS = "v:test-empire", "v:test-clans"
HOUSES = [h["id"] for h in renascita.SCENARIO["houses"]]
ORIEN, MEDANI, CANNITH = "v:house-orien", "v:house-medani", "v:house-cannith"  # (Port Ardere; the ruler's; the capital)


def scenario():
    sc = copy.deepcopy(renascita.SCENARIO)
    sc["polities"] = [
        {"id": EMPIRE, "name": "the Empire", "seat": "v:lions-rest", "members": HOUSES[:9], "control": ["v:pyrosia"],
         "ruler": f"{MEDANI}-head", "government": "ruler"},
        {"id": CLANS, "name": "the Clans", "seat": "v:raining-bay", "members": HOUSES[10:], "control": ["v:flame-coast"],
         "ruler": f"{HOUSES[10]}-head", "government": "ruler"}]
    return sc


def engine(seed=5):
    return renascita.new_engine(seed=seed, scenario=scenario())


def head(e, house):
    return e.store.get(f"{house}-head", "holder")


def harness(e, fn, days=1):
    out = {}
    base = e.rulesets[0][1]
    first = CAL.add(START, Span(days=1))

    class Harness(System):
        cadence = "on_demand"
        reads = (A.READS | LIBRARY["Secede"].reads | courts.READS | war.War.reads
                 | frozenset().union(*(a.reads for a in ACTIONS.values())) | {"cause"})
        writes = A.WRITES | courts.WRITES | war.War.writes
        event_types = A.EVENT_TYPES + courts.EVENT_TYPES + war.EVENT_TYPES

        def handle(self, ctx, activation):
            if activation.purpose == "succession":
                houses.handle_succession(ctx, activation)
            elif activation.purpose == "arrive":
                travel.arrive(ctx, activation)
            else:
                out["value"] = fn(ctx)

    Harness.name = "test.harness"
    rs = Ruleset("t", 1, (Harness(),) + base.systems, params=dict(base.params), forcers=base.forcers)
    e.rulesets = [(START, rs)]
    e.register_event_types(rs.event_types())
    e.run_before(first)
    e.schedule("test.harness", first, "act", entity=EMPIRE)
    e.run(until=CAL.add(first, Span(days=days)))
    return out.get("value")


def restless(e, person):  # (hot-blooded, and out of favour)
    e.store.set(person, "traits", {**e.store.get(person, "traits"), "temper": 0.95}, START, "test")
    e.store.set(person, "favour", -0.2, START, "test")


def test_a_restless_lord_of_a_governed_town_wants_out():
    e = engine()
    lord = head(e, ORIEN)
    restless(e, lord)
    f = harness(e, lambda ctx: LIBRARY["Secede"].eligible(ctx, lord))
    assert f is not None and f.target == EMPIRE


def test_neither_the_rulers_house_nor_one_seated_in_the_capital_secedes():
    for house in (MEDANI, CANNITH):
        e = engine()
        lord = head(e, house)
        restless(e, lord)
        assert harness(e, lambda ctx: LIBRARY["Secede"].eligible(ctx, lord)) is None, house


def test_a_revolt_makes_a_realm_at_the_seat_and_a_war_to_crush_it():
    e = engine()
    lord = head(e, ORIEN)
    assert harness(e, lambda ctx: perform(ctx, ACTIONS["Revolt"], lord, EMPIRE, odds=1.0)) == "success"
    store = e.store
    rose = next(x for x in e.events if x.type == "polity.seceded")
    new = rose.payload["polity"]
    assert rose.roles["leader"] == (lord,) and rose.roles["from"] == (EMPIRE,)
    assert store.get(new, "seat") == "v:port-ardere" and store.get(new, "members") == [ORIEN]
    assert store.get(new, "ruler") == f"{ORIEN}-head" and store.get(new, "seceded_from") == EMPIRE
    assert ORIEN not in store.get(EMPIRE, "members")
    assert store.get("v:port-ardere", "control") == new
    assert store.exists(f"rel:{CLANS}|{new}") or store.exists(f"rel:{new}|{CLANS}")  # (its neighbour across the sea road)
    declared = next(x for x in e.events if x.type == "polity.war_declared")
    assert declared.roles["aggressor"] == (EMPIRE,) and declared.roles["defender"] == (new,)
    assert ("event", rose.id) in {(c.kind, c.ref) for c in declared.causes}


def test_a_failed_revolt_is_treason_before_the_ruler():
    e = engine()
    lord = head(e, ORIEN)
    assert harness(e, lambda ctx: perform(ctx, ACTIONS["Revolt"], lord, EMPIRE, odds=0.0)) == "failure"
    trial = next(x for x in e.events if x.type == "polity.trial")
    assert trial.roles["accused"] == (lord,) and trial.roles["judge"] == (head(e, MEDANI),)


def test_only_a_house_head_of_a_governed_town_can_rise():
    e = engine()
    assert harness(e, lambda ctx: perform(ctx, ACTIONS["Revolt"], head(e, CANNITH), EMPIRE, odds=1.0)) == "impossible"
    e = engine()
    assert harness(e, lambda ctx: perform(ctx, ACTIONS["Revolt"], head(e, ORIEN), CLANS, odds=1.0)) == "impossible"


def test_a_crushed_revolt_returns_its_house_to_the_realm():
    e = engine()
    lord = head(e, ORIEN)

    def go(ctx):
        perform(ctx, ACTIONS["Revolt"], lord, EMPIRE, odds=1.0)
        new = next(p for p in ctx.ids("polity") if p not in (EMPIRE, CLANS))
        w = next(x for x in ctx.ids("war") if ctx.get(x, "defender") == new)
        war.War().fall(ctx, w, new, EMPIRE, ctx.get(w, "cause"))
        return new

    new = harness(e, go)
    assert e.store.get(new, "ended") is not None
    assert ORIEN in e.store.get(EMPIRE, "members") and e.store.get("v:port-ardere", "control") == EMPIRE
    assert e.store.get(new, "members") == []  # (a fallen realm holds no houses)


def test_rallied_is_a_house_head_won_to_the_scheme():
    e = engine()
    lord = head(e, ORIEN)
    sid = "sch:test"
    e.store.create("scheme", sid, {"owner": lord, "accomplices": [], "state": "active", "plan": [], "step": 0},
                   START, "test")

    def go(ctx):
        before = holds(ctx, lord, "rallied", sid)
        perform(ctx, ACTIONS["Rally"], lord, None, scheme=sid, odds=1.0)
        return before, holds(ctx, lord, "rallied", sid)

    assert harness(e, go) == (False, True)


def test_a_realm_left_to_itself_sees_a_house_rise_and_a_war_to_crush_it():
    e = engine(seed=5)
    e.run(until=CAL.add(START, Span(years=60)))
    rose = [x for x in e.events if x.type == "polity.seceded"]
    assert rose
    for r in rose:
        new = r.payload["polity"]
        war_on_it = [x for x in e.events if x.type == "polity.war_declared" and x.roles["defender"] == (new,)]
        assert war_on_it and ("event", r.id) in {(c.kind, c.ref) for c in war_on_it[0].causes}
        formed = [x for x in e.events if x.type == "people.ambition_formed" and x.payload["class"] == "Secede"
                  and x.roles["owner"] == r.roles["leader"]]
        assert formed  # (the rising was someone's ambition)
