"""Ambitions and their lifecycle (S7 spec §3, §13; #91)."""

import copy

import pytest

from renasci.analysis.divergence import analyse
from renasci.core.calendar import Date, Span
from renasci.core.events import Cause
from renasci.core.ripples import Ripple
from renasci.kin import RACES, new_engine

END = Date(1, 40, 359)


@pytest.fixture(scope="module")
def world():
    e = new_engine()
    e.full_reads = True
    e.run(until=END)
    return e


def events(e, kind):
    return [ev for ev in e.events if ev.type == kind]


# ---------------------------------------------------------------- the S1/S3 additions


def test_scheme_is_a_cause_kind():
    assert Cause("scheme", "x1").kind == "scheme"


def test_a_follow_up_can_carry_extra_causes():
    from renasci.core.engine import Engine
    from renasci.core.events import EventType
    from renasci.core.systems import Ruleset, System
    from renasci.kin import CAL

    TICK = EventType("mini.tick", 1, roles={}, payload={})
    seen = {}

    class Chain(System):
        name, cadence = "mini.chain", "yearly"
        event_types = (TICK,)

        def run(self, ctx):
            ctx.schedule(Span(days=5), "later", entity="t:x", causes=(Cause("ambition", "a1"), Cause("scheme", "s1")))

        def handle(self, ctx, activation):
            seen["event"] = ctx.emit("mini.tick", {}, purpose="tick", actor="t:x")

    e = Engine(CAL, seed=1, rulesets=[(Date(1, 1, 0), Ruleset("c", 1, (Chain(),)))])
    e.cast("place", "t:x", {})
    e.run(until=Date(1, 1, 30))
    kinds = {(c.kind, c.ref) for c in seen["event"].causes}
    assert {("ambition", "a1"), ("scheme", "s1")} <= kinds


def test_a_killer_is_named_on_the_death():
    from renasci.people.life import DEATH

    assert "killer" in DEATH.roles and DEATH.roles["killer"] == (0, 1)


# ---------------------------------------------------------------- ambitions


def test_ambitions_form_with_their_reasons(world):
    formed = events(world, "people.ambition_formed")
    classes = {ev.payload["class"] for ev in formed}
    assert {"Marry", "Standing"} <= classes
    for ev in formed:
        a = ev.roles["ambition"][0]
        rec = world.store.get(a, "class")
        assert rec == ev.payload["class"] and world.store.get(a, "owner") == ev.roles["owner"][0]
        assert any(c.kind in ("drive", "event") for c in ev.causes)  # born of something


def test_a_marriage_fulfils_the_wish_to_marry(world):
    store = world.store
    fulfilled = [ev for ev in events(world, "people.ambition_resolved")
                 if ev.payload["status"] == "fulfilled" and store.get(ev.roles["ambition"][0], "class") == "Marry"]
    assert fulfilled
    wed = {}
    for ev in events(world, "people.marriage"):
        for p in ev.roles["spouse"]:
            wed.setdefault(p, []).append(ev.date)
    for ev in fulfilled:  # married on or before the day the wish was found fulfilled
        assert any(d <= ev.date for d in wed.get(ev.roles["owner"][0], []))


def test_death_leaves_ambitions_unfulfilled(world):
    store = world.store
    died = [ev for ev in events(world, "people.ambition_resolved") if ev.payload["status"] == "died_unfulfilled"]
    assert died
    deaths = {ev.roles["deceased"][0]: ev for ev in events(world, "people.death")}
    for ev in died:
        owner = ev.roles["owner"][0]
        assert owner in deaths and ("event", deaths[owner].id) in {(c.kind, c.ref) for c in ev.causes}
    for p in store.ids("person"):
        if store.status(p) != "active":
            assert not store.get(p, "ambitions")


def test_ambitions_follow_their_state_machine(world):
    store = world.store
    resolved = {}
    for ev in world.events:
        if ev.type == "people.ambition_resolved":
            a = ev.roles["ambition"][0]
            assert a not in resolved, "an ambition was resolved twice"
            resolved[a] = ev.payload["status"]
    for a in store.ids("ambition"):
        status = store.get(a, "state")
        assert (status == "active") == (a not in resolved)
        owner = store.get(a, "owner")
        assert (a in (store.get(owner, "ambitions") or [])) == (status == "active")


def test_cooldowns_hold(world):
    store = world.store
    last = {}
    for ev in world.events:
        if ev.type == "people.ambition_resolved":
            a = ev.roles["ambition"][0]
            last[(store.get(a, "owner"), store.get(a, "class"))] = ev.date
        elif ev.type == "people.ambition_formed":
            key = (ev.roles["owner"][0], ev.payload["class"])
            if key in last:
                assert ev.date.year - last[key].year >= 3  # every starter cooldown is at least three years


def test_a_demotion_abandons_the_wish(world):
    """A wish alone doesn't keep someone named (only an active scheme does, #94); fading abandons it."""
    demoted = {ev.roles["individual"][0]: ev.date for ev in events(world, "lod.demote")}
    for a in world.store.ids("ambition"):
        owner = world.store.get(a, "owner")
        if owner in demoted and world.store.get(owner, "status") == "dormant":
            assert world.store.get(a, "state") != "active"


def test_traits_default_to_average_when_the_world_lacks_them():
    from renasci.people.ambitions import trait

    class FakeCtx:
        params = {"traits": {"wits": "wits"}}

        def get(self, entity, field, default=None):
            return {"traits": {"stature": 0.7}}.get(field, default)

    assert trait(FakeCtx(), "p", "wits") == 0.5 and trait(FakeCtx(), "p", "charm") == 0.5


def test_a_protect_ripple_with_ambitions_is_fully_explained(world):
    death = next(ev for ev in events(world, "people.death") if 8 <= ev.date.year <= 25 and 20 <= ev.payload["age"] <= 45)
    variant = new_engine(ripples=[Ripple("r1", "protect", Date(1, death.date.year - 1, 0), death.roles["deceased"][0],
                                         {"until": [1, 40, 359]})])
    variant.full_reads = True
    variant.run(until=END)
    report = analyse(world.pending(), variant.pending(), world.store.to_json(), variant.store.to_json(), ripples=["r1"])
    assert report["divergent_events"] > 0
    assert report["unexplained_events"] == report["unexplained_entities"] == report["unexplained_cells"] == 0, \
        report["unexplained"]


def test_doomed_world_ambitions_all_die_with_their_owners():
    doomed = copy.deepcopy(RACES)
    for r in doomed:
        r["mortality"] = {"f": [1.0] * 20, "m": [1.0] * 20}
    e = new_engine(races=doomed)
    e.run(until=Date(1, 2, 359))
    for a in e.store.ids("ambition"):
        assert e.store.get(a, "state") != "active"


# ---------------------------------------------------------------- review fixes


def test_quiet_commoners_who_merely_wish_still_fade(world):
    assert events(world, "lod.demote"), "a wish alone (no active scheme) must not keep everyone named"


def test_traits_are_read_from_the_person_under_strict_declarations():
    import copy

    from renasci.kin import SCENARIO

    sc = copy.deepcopy(SCENARIO)
    sc["params"]["traits"] = {"charm": "constitution", "wits": "stature"}
    e = new_engine(scenario=sc)
    e.run(until=Date(1, 3, 359))  # strict mode: an undeclared read would raise
    assert events(e, "people.ambition_formed")


def test_unknown_ambition_classes_are_refused():
    from renasci.people.ambitions import classes

    class Ctx:
        params = {"ambitions": ["Marry", "Conquer"]}

    with pytest.raises(ValueError, match="Conquer"):
        classes(Ctx())


def test_the_death_flow_is_explained_by_the_death(world):
    deaths = {ev.id for ev in events(world, "people.death")}
    for d in world.pending()["bulk_deltas"]:
        if "flow:died" in (d.get("components") or [d.get("component")]):
            ev = next(e for e in world.events if e.id == d["event"])
            assert ev.type in ("people.death", "people.population", "engine.cast_column"), ev.type
    assert deaths
