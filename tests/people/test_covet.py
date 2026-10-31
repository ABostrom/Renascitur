"""Coveting, stealing and destroying objects (S9 spec §5, #126 slice 2): a famous thing draws the envious,
whose plot is to steal it; a sacked town may lose what it held."""

import copy

from renasci import kin
from renasci.core.calendar import Date
from renasci.core.systems import Ruleset, System
from renasci.kin import START
from renasci.people import actions as A
from renasci.people import crafts, houses, travel
from renasci.people.actions import ACTIONS, perform
from renasci.people.ambitions import LIBRARY
from renasci.people.planner import holds

CATALOGUE = {
    "jobs": {
        "farmer": {"name": "farmer", "demand": 0.5, "income": 1.0},
        "miner": {"name": "miner", "demand": 0.2, "income": 1.5},
        "smith": {"name": "smith", "demand": 0.3, "income": 3.0, "makes": ["blade"]},
    },
    "materials": {"iron": {"name": "iron", "by": ["miner"], "yield": {"*": 0.5}, "value": 4}},
    "types": {"blade": {"name": "blade", "material": "iron", "cost": 3}},
    "master_rate": 2.0,
}
TRAITS = {"temper": "stature", "wits": "stature", "charm": "stature"}


def engine(crafty=True):
    sc = copy.deepcopy(kin.SCENARIO)
    if crafty:
        sc["params"]["crafts"] = copy.deepcopy(CATALOGUE)
    return kin.new_engine(seed=4, scenario=sc, traits=TRAITS)


def harness(e, fn, when, until):
    out = {}
    base = e.rulesets[0][1]

    class Harness(System):
        cadence = "on_demand"
        reads = A.READS | crafts.READS | LIBRARY["Covet"].reads | frozenset().union(*(a.reads for a in ACTIONS.values()))
        writes = A.WRITES | crafts.WRITES
        event_types = A.EVENT_TYPES + crafts.EVENT_TYPES

        def handle(self, ctx, activation):
            if activation.purpose == "succession":
                houses.handle_succession(ctx, activation)
            elif activation.purpose == "arrive":
                travel.arrive(ctx, activation)
            elif "value" not in out:
                out["value"] = fn(ctx)

    Harness.name = "test.harness"
    rs = Ruleset("t", 1, (Harness(),) + base.systems, params=dict(base.params, exposure_base=0.0), forcers=base.forcers)
    e.rulesets = [(START, rs)]
    e.register_event_types(rs.event_types())
    e.run_before(Date(1, 1, 1))
    e.schedule("test.harness", when, "act", entity="t:Hollow-1")
    e.run(until=until)
    return out.get("value")


def owned(ctx):
    for o in sorted(ctx.ids("object")):
        if ctx.get(o, "owner"):
            return o, ctx.get(o, "owner")
    raise AssertionError("no owned object yet")


def neighbour(ctx, person):
    from renasci.people.races import age_years

    return next(p for p in sorted(ctx.get(ctx.get(person, "place"), "residents"))
                if p != person and age_years(ctx.calendar, ctx.get(p, "born"), ctx.today) >= 18)


def kinds(e, t):
    return [x for x in e.events if x.type == t]


def test_a_famous_object_is_coveted_by_a_hot_blooded_neighbour():
    e = engine()

    def look(ctx):
        obj, owner = owned(ctx)
        other = neighbour(ctx, owner)
        before = LIBRARY["Covet"].eligible(ctx, other)
        e.store.set(obj, "fame", 0.75, ctx.today, "test")  # (made famous)
        e.store.set(other, "traits", {**e.store.get(other, "traits"), "stature": 0.95}, ctx.today, "test")
        after = LIBRARY["Covet"].eligible(ctx, other)
        return obj, before, after

    obj, before, after = harness(e, look, Date(1, 6, 100), Date(1, 6, 101))
    assert before is None and after is not None and after.target == obj


def test_stealing_takes_it_into_the_thiefs_hands():
    e = engine()

    def steal(ctx):
        obj, owner = owned(ctx)
        thief = neighbour(ctx, owner)
        was = holds(ctx, thief, f"holds:{obj}")
        out = perform(ctx, ACTIONS["Steal"], thief, obj, odds=1.0)
        return obj, owner, thief, was, out, holds(ctx, thief, f"holds:{obj}")

    obj, owner, thief, was, out, now = harness(e, steal, Date(1, 6, 100), Date(1, 6, 101))
    assert (was, out, now) == (False, "success", True)
    taken = next(x for x in kinds(e, "object.stolen") if x.roles["object"] == (obj,))
    assert taken.roles["thief"] == (thief,) and taken.roles["from"] == (owner,)
    assert obj in e.store.get(thief, "possessions") and obj not in (e.store.get(owner, "possessions") or [])


def test_a_destroyed_object_is_gone_for_good():
    e = engine()

    def burn(ctx):
        obj, owner = owned(ctx)
        crafts.destroy(ctx, obj, ctx.get(obj, "place"), None)
        return obj, owner

    obj, owner = harness(e, burn, Date(1, 6, 100), Date(1, 8, 0))
    assert e.store.status(obj) == "dead" and e.store.get(obj, "destroyed") and e.store.get(obj, "owner") is None
    assert obj not in (e.store.get(owner, "possessions") or [])
    assert len([x for x in kinds(e, "object.destroyed") if x.roles["object"] == (obj,)]) == 1


def test_a_world_without_crafts_covets_nothing():
    e = engine(crafty=False)
    e.run(until=Date(1, 4, 0))
    assert not [x for x in kinds(e, "people.ambition_formed") if x.payload["class"] == "Covet"]


def test_a_protected_object_survives_what_would_destroy_it():
    from renasci.core.ripples import Ripple

    probe = engine()
    target = {}

    def find(ctx):
        target["obj"] = owned(ctx)[0]

    harness(probe, find, Date(1, 6, 100), Date(1, 6, 101))
    obj = target["obj"]
    sc = copy.deepcopy(kin.SCENARIO)
    sc["params"]["crafts"] = copy.deepcopy(CATALOGUE)
    e = kin.new_engine(seed=4, scenario=sc, traits=TRAITS,
                       ripples=[Ripple("r1", "protect", Date(1, 6, 0), obj, {"until": [1, 9, 0]})])

    def burn(ctx):
        return crafts.destroy(ctx, obj, crafts.where(ctx, obj), None)

    assert harness(e, burn, Date(1, 6, 100), Date(1, 6, 101)) is False
    assert e.store.status(obj) == "active"
    spared = [x for x in kinds(e, "people.near_miss") if x.roles["survivor"] == (obj,)]
    assert spared and ("ripple", "r1") in {(c.kind, c.ref) for c in spared[0].causes}
