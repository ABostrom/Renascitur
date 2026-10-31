"""Object biographies (S9 spec §5, #126): what happens to a masterwork after it is made. It passes to its
owner's heir, is lost where an owner falls far from home and found by someone there, and earns deeds, fame and
at last a name from what its owner does with it."""

import copy

import pytest

from renasci import kin
from renasci.core.calendar import Date
from renasci.core.systems import Ruleset, System
from renasci.kin import START
from renasci.people import actions as A
from renasci.people import crafts, houses, life, travel
from renasci.people.actions import ACTIONS, perform

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


def engine(**over):
    sc = copy.deepcopy(kin.SCENARIO)
    sc["params"]["crafts"] = {**copy.deepcopy(CATALOGUE), **over}
    return kin.new_engine(seed=4, scenario=sc)


def run(e, until):
    e.run(until=until)
    return e


def kinds(e, t):
    return [x for x in e.events if x.type == t]


@pytest.fixture(scope="module")
def lived():
    return run(engine(), Date(1, 40, 359))


def test_an_owners_death_passes_the_object_to_their_heir(lived):
    store = lived.store
    inherited = kinds(lived, "object.inherited")
    assert inherited
    for x in inherited:
        (dead,), (heir,), (obj,) = x.roles["from"], x.roles["owner"], x.roles["object"]
        assert store.status(dead) == "dead"
        kin_of = {*store.get(dead, "children"), store.get(dead, "spouse")}
        assert heir in kin_of
    for o in store.ids("object"):  # (nobody gone holds anything: an object is held by the living, or lost)
        owner = store.get(o, "owner")
        assert (owner is None) == (store.get(o, "lost") is not None)
        if owner:
            assert o in store.get(owner, "possessions")
            if store.status(owner) != "active":  # (only one who died since this year's pass)
                died = next(x for x in kinds(lived, "people.death") if x.roles["deceased"] == (owner,))
                assert died.date.year == 40


def test_owners_are_kept_as_notables(lived):
    ever = {(x.roles.get("owner") or x.roles.get("finder"))[0] for x in lived.events
            if x.type in ("object.given", "object.inherited", "object.found")}
    demoted = {x.roles["individual"][0] for x in kinds(lived, "lod.demote")}
    assert ever and not (ever & demoted)


def harness(e, fn, when, until):
    """Run `fn(ctx)` once at `when` (the people systems running beside it); return its result."""
    out = {}
    base = e.rulesets[0][1]

    class Harness(System):
        cadence = "on_demand"
        reads = A.READS | crafts.READS
        writes = A.WRITES | crafts.WRITES
        event_types = A.EVENT_TYPES

        def handle(self, ctx, activation):
            if activation.purpose == "succession":
                houses.handle_succession(ctx, activation)
            elif activation.purpose == "arrive":
                travel.arrive(ctx, activation)
            elif "value" not in out:
                out["value"] = fn(ctx)

    Harness.name = "test.harness"
    rs = Ruleset("t", 1, (Harness(),) + base.systems, params=dict(base.params), forcers=base.forcers)
    e.rulesets = [(START, rs)]
    e.register_event_types(rs.event_types())
    e.run_before(Date(1, 1, 1))
    e.schedule("test.harness", when, "act", entity="t:Hollow-1")
    e.run(until=until)
    return out.get("value")


def owned(ctx):
    """The first object with an owner, and its owner."""
    for o in sorted(ctx.ids("object")):
        if ctx.get(o, "owner"):
            return o, ctx.get(o, "owner")
    raise AssertionError("no owned object yet")


def test_an_object_is_lost_where_its_owner_fell_far_from_home_and_found_there():
    e = engine(lose_rate=1.0, find_rate=1.0)

    def fell(ctx):
        obj, owner = owned(ctx)
        life.die(ctx, owner, ctx.get(owner, "place"), "fell in battle")
        return obj, owner

    obj, owner = harness(e, fell, Date(1, 6, 100), Date(1, 9, 359))
    lost = next(x for x in kinds(e, "object.lost") if x.roles["object"] == (obj,))
    found = next(x for x in kinds(e, "object.found") if x.roles["object"] == (obj,))
    assert lost.roles["owner"] == (owner,) and lost.date < found.date
    assert e.store.get(obj, "owner") == found.roles["finder"][0] and e.store.get(obj, "lost") is None


def test_deeds_bring_fame_and_at_last_a_name():
    e = engine()

    def duels(ctx):
        obj, owner = owned(ctx)
        from renasci.people.races import age_years

        foes = [p for p in ctx.get(ctx.get(owner, "place"), "residents")
                if p != owner and age_years(ctx.calendar, ctx.get(p, "born"), ctx.today) >= 18][:2]
        return obj, [perform(ctx, ACTIONS["Duel"], owner, f, odds=1.0) for f in foes]

    obj, outcomes = harness(e, duels, Date(1, 6, 100), Date(1, 7, 359))
    assert outcomes == ["success", "success"]
    deeds = [x for x in kinds(e, "object.deed") if x.roles["object"] == (obj,)]
    assert len(deeds) == 2 and e.store.get(obj, "fame") >= crafts.NAMED
    named = next(x for x in kinds(e, "object.named") if x.roles["object"] == (obj,))
    assert e.store.get(obj, "name") == named.payload["name"] and named.payload["name"].startswith("the Blade of ")
    assert ":" not in named.payload["name"]  # (a place's name, not its id)
