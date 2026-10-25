"""Courts and exile (S8 spec §9, #158): an exposed plot against an office holder goes to trial before the
realm's ruler; the verdict is a pardon, a fine, exile or execution; an exile can't come home while that
ruler reigns."""

import copy

from renasci import kin
from renasci.core.calendar import Date
from renasci.core.ripples import Ripple
from renasci.core.systems import Ruleset, System
from renasci.kin import START
from renasci.people import actions as A
from renasci.people import courts, houses, travel

HOUSES = ["t:House-Hollow", "t:House-Mere", "t:House-Ridge"]
REALM, THRONE = "t:Realm", "t:House-Hollow-head"
TRAITS = {"temper": "stature", "wits": "stature", "charm": "stature"}


def scenario(control=("t:Hollow", "t:Mere")):  # (Ridge lies outside the realm: somewhere to be exiled to)
    sc = copy.deepcopy(kin.SCENARIO)
    sc["polities"] = [{"id": REALM, "name": "the Realm", "kind": "kingdom", "government": "ruler",
                       "seat": "t:Hollow-1", "members": HOUSES, "control": list(control), "ruler": THRONE}]
    return sc


def engine(**kw):
    return kin.new_engine(seed=11, scenario=scenario(**kw.pop("sc", {})), traits=TRAITS, **kw)


def harness(e, fn, until=Date(1, 1, 2)):
    out = {}
    base = e.rulesets[0][1]

    class Harness(System):
        cadence = "on_demand"
        reads = A.READS | courts.READS
        writes = A.WRITES | courts.WRITES
        event_types = A.EVENT_TYPES + courts.EVENT_TYPES

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
    e.run_before(Date(1, 1, 1))
    e.schedule("test.harness", Date(1, 1, 1), "act", entity=THRONE)
    e.run(until=until)
    return out.get("value")


def holder(e, office):
    return e.store.get(office, "holder")


def accused_and_victim(e):
    """A Mere notable who plotted against the Ridge head (an office holder)."""
    return holder(e, "t:House-Mere-head"), holder(e, "t:House-Ridge-head")


def trials(e):
    return [ev for ev in e.events if ev.type == "polity.trial"]


def test_a_plot_against_an_office_holder_is_tried_before_the_ruler():
    e = engine()
    accused, victim = accused_and_victim(e)
    king = holder(e, THRONE)
    harness(e, lambda ctx: courts.trial(ctx, accused, victim, None, grave=1.0, verdict="fine"))
    (t,) = trials(e)
    assert t.roles["accused"] == (accused,) and t.roles["judge"] == (king,) and t.roles["victim"] == (victim,)
    assert t.payload == {"verdict": "fine", "polity": REALM}


def test_the_verdict_is_a_keyed_draw_and_the_same_seed_judges_the_same():
    def judge():
        e = engine()
        accused, victim = accused_and_victim(e)
        harness(e, lambda ctx: courts.trial(ctx, accused, victim, None, grave=1.0))
        return trials(e)[0].payload["verdict"]

    assert judge() == judge() in courts.VERDICTS


def test_a_fine_costs_favour_and_a_pardon_nothing():
    e = engine()
    accused, victim = accused_and_victim(e)
    before = float(e.store.get(accused, "favour") or 0.0)
    harness(e, lambda ctx: courts.trial(ctx, accused, victim, None, grave=0.3, verdict="fine"))
    assert float(e.store.get(accused, "favour")) < before
    e = engine()
    harness(e, lambda ctx: courts.trial(ctx, accused, victim, None, grave=0.3, verdict="pardon"))
    assert float(e.store.get(accused, "favour") or 0.0) == before and e.store.status(accused) == "active"


def test_execution_is_a_death_by_the_rulers_hand():
    e = engine()
    accused, victim = accused_and_victim(e)
    king = holder(e, THRONE)
    harness(e, lambda ctx: courts.trial(ctx, accused, victim, None, grave=1.0, verdict="execution"))
    death = next(ev for ev in e.events if ev.type == "people.death" and ev.roles["deceased"] == (accused,))
    assert death.payload["cause"] == "executed" and death.roles["killer"] == (king,)
    assert ("event", trials(e)[0].id) in {(c.kind, c.ref) for c in death.causes}


def test_a_guarded_accused_survives_the_sentence():
    probe = engine()
    accused, victim = accused_and_victim(probe)
    e = engine(ripples=[Ripple("r1", "protect", Date(1, 1, 0), accused, {"until": [1, 5, 359]})])
    harness(e, lambda ctx: courts.trial(ctx, accused, victim, None, grave=1.0, verdict="execution"))
    assert e.store.status(accused) == "active"
    assert any(ev.type == "people.near_miss" for ev in e.events)


def test_exile_sends_them_out_of_the_realm_and_bars_their_return():
    e = engine()
    accused, victim = accused_and_victim(e)
    king = holder(e, THRONE)
    home = e.store.get(accused, "place")

    def go(ctx):
        courts.trial(ctx, accused, victim, None, grave=1.0, verdict="exile")
        return courts.barred(ctx, accused, home)

    assert harness(e, go, until=Date(1, 2, 0)) is True
    place = e.store.get(accused, "place")
    assert e.store.get(place, "control") != REALM and not e.store.get(accused, "journey")
    assert e.store.get(accused, "exiled") == {"polity": REALM, "by": king, "office": THRONE, "since": [1, 1, 1]}


def test_with_nowhere_outside_the_realm_exile_becomes_a_fine():
    e = engine(sc={"control": ("t:Hollow", "t:Mere", "t:Ridge")})
    accused, victim = accused_and_victim(e)
    harness(e, lambda ctx: courts.trial(ctx, accused, victim, None, grave=1.0, verdict="exile"))
    assert trials(e)[0].payload["verdict"] == "fine" and not e.store.get(accused, "exiled")


def test_the_ruler_is_not_tried_in_their_own_court():
    e = engine()
    king = holder(e, THRONE)
    _, victim = accused_and_victim(e)
    assert harness(e, lambda ctx: courts.trial(ctx, king, victim, None, grave=1.0)) is None
    assert trials(e) == []


def test_a_realm_left_to_itself_holds_trials():
    e = kin.new_engine(seed=5, scenario=scenario(), traits=TRAITS)
    e.run(until=Date(1, 80, 359))
    held = trials(e)
    assert held
    exposed = {ev.id: ev for ev in e.events if ev.type == "people.scheme_exposed"}
    for t in held:
        assert {c.ref for c in t.causes if c.kind == "event"} & set(exposed)  # (every trial follows an exposure)
