"""Usurp and Coup (S8 spec §9, #158): a realm's notable plots to take its ruler's office, and a seized
office passes back to the deposed line when the usurper's own line can't hold it."""

import copy

import pytest

from renasci import kin
from renasci.core.calendar import Date
from renasci.core.ripples import Ripple
from renasci.core.systems import Ruleset, System
from renasci.kin import START
from renasci.people import actions as A
from renasci.people import houses
from renasci.people.actions import ACTIONS, perform
from renasci.people.ambitions import LIBRARY
from renasci.people.planner import holds

HOUSES = ["t:House-Hollow", "t:House-Mere", "t:House-Ridge"]
REALM, THRONE = "t:Realm", "t:House-Hollow-head"


def scenario():
    sc = copy.deepcopy(kin.SCENARIO)
    sc["polities"] = [{"id": REALM, "name": "the Realm", "kind": "kingdom", "government": "ruler",
                       "seat": "t:Hollow-1", "members": HOUSES, "control": ["t:Hollow", "t:Ridge", "t:Mere"],
                       "ruler": THRONE}]
    return sc


def engine(**kw):
    return kin.new_engine(seed=11, scenario=scenario(), traits={"temper": "stature"}, **kw)


def holder(e, office):
    return e.store.get(office, "holder")


def harness(e, fn, until=Date(1, 1, 2)):
    """Run `fn(ctx)` once, a day into the world (the people systems running beside it); return its result."""
    out = {}
    base = e.rulesets[0][1]  # (the world's own systems and params)

    class Harness(System):
        cadence = "on_demand"
        reads = A.READS | LIBRARY["Usurp"].reads | frozenset({"ambitions", "class", "drives"})
        writes = A.WRITES
        event_types = A.EVENT_TYPES

        def handle(self, ctx, activation):
            if activation.purpose == "succession":  # (a death's follow-up comes back to whoever killed)
                houses.handle_succession(ctx, activation)
            else:
                out["value"] = fn(ctx)

    Harness.name = "test.harness"
    rs = Ruleset("t", 1, (Harness(),) + base.systems, params=dict(base.params, exposure_base=0.0), forcers=base.forcers)
    e.rulesets = [(START, rs)]
    e.register_event_types(rs.event_types())
    e.run_before(Date(1, 1, 1))
    e.schedule("test.harness", Date(1, 1, 1), "act", entity=THRONE)
    e.run(until=until)
    return out["value"]


def coup(e, usurper, odds=1.0, until=Date(1, 1, 2)):
    king = holder(e, THRONE)
    return harness(e, lambda ctx: perform(ctx, ACTIONS["Coup"], usurper, king, odds=odds), until=until), king


def mere_head(e):
    return holder(e, "t:House-Mere-head")


def test_a_coup_seizes_the_rulers_office():
    e = engine()
    usurper = mere_head(e)
    outcome, king = coup(e, usurper)
    store = e.store
    assert outcome == "success"
    assert holder(e, THRONE) == usurper
    assert store.get(THRONE, "legitimacy") == "seized" and store.get(THRONE, "deposed") == king
    assert THRONE in store.get(usurper, "offices") and THRONE not in (store.get(king, "offices") or [])
    seized = next(ev for ev in e.events if ev.type == "polity.seized")
    assert seized.roles["usurper"] == (usurper,) and seized.roles["deposed"] == (king,)
    assert seized.payload == {"office": THRONE, "polity": REALM}
    action = next(ev for ev in e.events if ev.type == "people.action" and ev.payload["action"] == "Coup")
    assert ("event", action.id) in {(c.kind, c.ref) for c in seized.causes}
    assert store.status(king) == "active"  # (deposed, not killed)


def test_only_a_realms_notable_can_strike_at_its_ruler():
    e = engine()
    king = holder(e, THRONE)
    nobody = next(p for s in e.store.ids("settlement") for p in e.store.get(s, "residents")
                  if not e.store.get(p, "offices") and p != king and e.store.get(p, "house") not in HOUSES)
    assert harness(e, lambda ctx: perform(ctx, ACTIONS["Coup"], nobody, king, odds=1.0)) == "impossible"
    e2 = engine()
    other = mere_head(e2)
    ridge = holder(e2, "t:House-Ridge-head")
    assert harness(e2, lambda ctx: perform(ctx, ACTIONS["Coup"], other, ridge, odds=1.0)) == "impossible"  # (no throne)


def test_a_failed_coup_costs_the_usurper_favour():
    e = engine()
    usurper = mere_head(e)
    before = float(e.store.get(usurper, "favour") or 0.0)
    outcome, king = coup(e, usurper, odds=0.0)
    assert outcome == "failure" and holder(e, THRONE) == king
    assert float(e.store.get(usurper, "favour")) < before


def test_a_protected_ruler_foils_the_coup():
    probe = engine()
    king = holder(probe, THRONE)
    e = engine(ripples=[Ripple("r1", "protect", Date(1, 1, 0), king, {"until": [1, 5, 359]})])
    outcome, _ = coup(e, mere_head(e))
    assert outcome == "foiled" and holder(e, THRONE) == king
    foiled = next(ev for ev in e.events if ev.type == "polity.coup_foiled")
    assert foiled.roles["ruler"] == (king,)


def test_a_seized_office_is_the_usurpers_goal_met():
    e = engine()
    usurper = mere_head(e)
    king = holder(e, THRONE)

    def go(ctx):
        before = holds(ctx, usurper, f"seized:{king}")
        perform(ctx, ACTIONS["Coup"], usurper, king, odds=1.0)
        return before, holds(ctx, usurper, f"seized:{king}")

    assert harness(e, go) == (False, True)


def test_the_usurpers_death_restores_the_deposed():
    e = engine()
    usurper = mere_head(e)
    king = holder(e, THRONE)

    def go(ctx):
        perform(ctx, ACTIONS["Coup"], usurper, king, odds=1.0)
        heir = ctx.get(THRONE, "heir")  # (his own line can't hold another's house)
        perform(ctx, ACTIONS["Assassinate"], king, usurper, odds=1.0)
        return heir

    assert harness(e, go, until=Date(1, 1, 10)) == king
    assert e.store.status(usurper) == "dead"
    assert holder(e, THRONE) == king
    assert e.store.get(THRONE, "legitimacy") == "lawful" and e.store.get(THRONE, "deposed") is None


def test_usurp_forms_for_a_hot_tempered_notable_of_the_realm():
    e = engine()
    usurper = mere_head(e)
    king = holder(e, THRONE)
    usurp = LIBRARY["Usurp"]

    for p in (usurper, king):  # (hot-blooded)
        e.store.set(p, "traits", {**e.store.get(p, "traits"), "stature": 0.9}, START, "test")

    def judge(ctx):
        f = usurp.eligible(ctx, usurper)
        return f and f.target, usurp.eligible(ctx, king)

    mine, kings = harness(e, judge)
    assert mine == king
    assert kings is None  # (the ruler doesn't plot against themselves)


def test_a_world_without_polities_never_usurps():
    e = kin.new_engine(seed=11)
    usurp = LIBRARY["Usurp"]
    people = [p for s in e.store.ids("settlement") for p in e.store.get(s, "residents")][:30]
    assert harness(e, lambda ctx: [usurp.eligible(ctx, p) for p in people]) == [None] * len(people)


def test_a_realm_left_to_itself_sees_a_usurper_plot_and_strike():
    e = kin.new_engine(seed=3, scenario=scenario(), traits={"temper": "stature", "wits": "stature", "charm": "stature"})
    e.run(until=Date(1, 80, 359))
    store = e.store
    formed = [ev for ev in e.events if ev.type == "people.ambition_formed" and ev.payload["class"] == "Usurp"]
    seized = [ev for ev in e.events if ev.type == "polity.seized"]
    assert formed and seized
    plotters = {ev.roles["owner"][0] for ev in formed}
    assert {ev.roles["usurper"][0] for ev in seized} <= plotters
    for office in store.ids("office"):  # (whoever holds an office lists it, and only they do)
        h = store.get(office, "holder")
        if h is not None:
            assert office in store.get(h, "offices"), office
        if store.get(office, "legitimacy") == "seized":
            assert store.get(office, "deposed") and store.get(office, "deposed") != h


def test_a_seized_throne_is_not_struck_at_again_and_its_usurper_votes_once():
    from renasci.people.ambitions import throne

    e = engine()
    usurper = mere_head(e)
    ridge = holder(e, "t:House-Ridge-head")
    king = holder(e, THRONE)

    def go(ctx):
        before = throne(ctx, ridge)
        perform(ctx, ACTIONS["Coup"], usurper, king, odds=1.0)
        return before, throne(ctx, ridge), houses._heads(ctx, REALM)

    before, after, heads = harness(e, go)
    assert before == (REALM, THRONE) and after is None  # (the deposed line's to take back: Seize, not another coup)
    assert heads.count(usurper) == 1
