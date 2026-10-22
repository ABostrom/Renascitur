import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "helpers"))

from mini_world import CAL, START  # noqa: E402

from renasci.core.calendar import Date, Span  # noqa: E402
from renasci.core.engine import Engine  # noqa: E402
from renasci.core.lod import Resolution, ResolutionPolicy  # noqa: E402
from renasci.core.systems import Ruleset, System  # noqa: E402

# ---------------------------------------------------------------- policy


def test_policy_is_fine_by_default_and_in_focus_windows():
    p = ResolutionPolicy(default=Resolution.coarse(Span(years=1)),
                         focus=[(Date(1, 10, 0), Date(1, 20, 0))])
    assert p.at(Date(1, 5, 0)).kind == "coarse"
    assert p.at(Date(1, 10, 0)).kind == "fine" and p.at(Date(1, 20, 0)).kind == "fine"
    assert ResolutionPolicy().at(Date(1, 5, 0)) == Resolution.fine()


def test_policy_validates_windows_and_steps():
    with pytest.raises(ValueError):
        ResolutionPolicy(focus=[(Date(1, 9, 0), Date(1, 8, 0))])
    with pytest.raises(ValueError):
        Resolution.coarse(Span())
    with pytest.raises(ValueError):
        Resolution("medium")


def test_the_engine_refuses_coarse_policies_until_m5():
    coarse = ResolutionPolicy(default=Resolution.coarse(Span(years=1)))
    with pytest.raises(NotImplementedError):
        Engine(CAL, seed=1, rulesets=[(START, Ruleset("r", 1, ()))], resolution=coarse)
    Engine(CAL, seed=1, rulesets=[(START, Ruleset("r", 1, ()))], resolution=ResolutionPolicy())


def test_systems_declare_how_they_behave_when_coarse():
    class Bad(System):
        name, cadence = "x.bad", "yearly"
        coarse_ok = "yes"

    with pytest.raises(ValueError):
        Ruleset("r", 1, (Bad(),))

    class Good(System):
        name, cadence, coarse_ok = "x.good", "yearly", True

    assert Ruleset("r", 1, (Good(),)).get("x.good").coarse_ok


# ---------------------------------------------------------------- promote and demote


class Census(System):
    """Year 2: promote a named villager out of the village aggregate. Year 4: they fade back."""

    name, cadence = "x.census", "yearly"
    event_types = __import__("renasci.core.lod", fromlist=["EVENT_TYPES"]).EVENT_TYPES
    reads = frozenset({"headcount", "ids:person", "status"})
    writes = frozenset({"new:person", "status", "headcount"})

    def run(self, ctx):
        if ctx.today.year == 2:
            ctx.promote("t:village", "person", {"origin": "t:village"}, reason="hero", column="headcount")
        if ctx.today.year == 4:
            for p in ctx.ids("person", status="active"):
                ctx.demote(p, reason="faded", column="headcount", aggregate="t:village")


def census_engine():
    e = Engine(CAL, seed=1, rulesets=[(START, Ruleset("c", 1, (Census(),)))])
    e.cast("place", "t:village", {})
    e.cast_column("headcount", "int64", ["t:village"], [100])
    return e


def test_promotion_creates_an_individual_with_a_causal_id_and_conserves_the_count():
    e = census_engine()
    e.run(until=Date(1, 3, 0))
    promo = next(ev for ev in e.events if ev.type == "lod.promote")
    person = promo.roles["individual"][0]
    assert person.startswith("e") and e.store.kind(person) == "person"
    assert promo.roles["aggregate"] == ("t:village",) and promo.payload == {"reason": "hero"}
    assert e.store.read_column("headcount", ["t:village"]).tolist() == [99]


def test_demotion_keeps_the_record_dormant_and_returns_to_the_count():
    e = census_engine()
    e.run(until=Date(1, 5, 0))
    person = next(ev for ev in e.events if ev.type == "lod.promote").roles["individual"][0]
    assert e.store.status(person) == "dormant"
    assert any(ev.type == "lod.demote" for ev in e.events)
    assert e.store.read_column("headcount", ["t:village"]).tolist() == [100]


def test_promotion_from_an_empty_aggregate_fails():
    e = census_engine()
    e.store.write_column("headcount", ["t:village"], [0], START, "x0")
    with pytest.raises(ValueError):
        e.run(until=Date(1, 3, 0))


def test_rulesets_can_check_conservation():
    def conserve(store):
        n = int(store.read_column("headcount", ["t:village"])[0])
        active = len(store.ids("person", status="active"))
        return [] if n + active == 100 else [f"population changed: {n} + {active}"]

    e = Engine(CAL, seed=1, rulesets=[(START, Ruleset("c", 1, (Census(),), conservation=conserve))])
    e.cast("place", "t:village", {})
    e.cast_column("headcount", "int64", ["t:village"], [100])
    e.run(until=Date(1, 5, 0))
    assert e.check_conservation() == []
    e.store.write_column("headcount", ["t:village"], [50], Date(1, 5, 0), "x9")
    assert e.check_conservation() == ["population changed: 50 + 0"]


# ---------------------------------------------------------------- review fixes

from renasci.core.lod import EVENT_TYPES as LOD_TYPES  # noqa: E402


def test_resolution_and_coarse_declarations_are_in_the_recipe():
    policy = ResolutionPolicy(focus=[(Date(1, 5, 0), Date(1, 6, 0))])
    e = Engine(CAL, seed=1, rulesets=[(START, Ruleset("c", 1, (Census(),)))], resolution=policy)
    r = e.recipe()
    assert r["resolution"] == {"default": {"kind": "fine", "step": None}, "focus": [[[1, 5, 0], [1, 6, 0]]]}
    sysrow = r["rulesets"][0]["systems"][0]
    assert sysrow["coarse_ok"] is False and sysrow["coarse_fallback"] is None


def test_lod_events_must_be_declared():
    class Undeclared(Census):
        name = "x.undeclared"
        event_types = ()

    e = Engine(CAL, seed=1, rulesets=[(START, Ruleset("c", 1, (Undeclared(),)))])
    e.cast("place", "t:village", {})
    e.cast_column("headcount", "int64", ["t:village"], [100])
    from renasci.core.context import UndeclaredAccess

    with pytest.raises(UndeclaredAccess):
        e.run(until=Date(1, 3, 0))


def test_promote_checks_its_declarations_before_changing_anything():
    class NoColumnWrite(Census):
        name = "x.nocol"
        writes = frozenset({"new:person"})

    e = Engine(CAL, seed=1, rulesets=[(START, Ruleset("c", 1, (NoColumnWrite(),)))])
    e.cast("place", "t:village", {})
    e.cast_column("headcount", "int64", ["t:village"], [100])
    with pytest.raises(Exception):
        e.run(until=Date(1, 3, 0))
    assert e.store.ids("person") == []


def test_demote_refuses_the_dormant_and_needs_column_with_aggregate():
    class Twice(System):
        name, cadence = "x.twice", "yearly"
        reads = frozenset({"headcount", "status"})
        writes = frozenset({"new:person", "status", "headcount"})
        event_types = LOD_TYPES

        def run(self, ctx):
            if ctx.today.year == 2:
                p = ctx.promote("t:village", "person", {}, reason="hero", column="headcount", place="t:village")
                ctx.demote(p, reason="faded", column="headcount", aggregate="t:village")
                ctx.demote(p, reason="again", column="headcount", aggregate="t:village")

    e = Engine(CAL, seed=1, rulesets=[(START, Ruleset("c", 1, (Twice(),)))])
    e.cast("place", "t:village", {})
    e.cast_column("headcount", "int64", ["t:village"], [100])
    with pytest.raises(ValueError):
        e.run(until=Date(1, 3, 0))


def test_promote_takes_a_place_and_causes():
    from renasci.core.events import Cause

    class Placed(Census):
        name = "x.placed"

        def run(self, ctx):
            if ctx.today.year == 2:
                ctx.promote("t:village", "person", {}, reason="hero", column="headcount", place="t:village",
                            causes=(Cause("event", ctx._engine.events[0].id),))

    e = Engine(CAL, seed=1, rulesets=[(START, Ruleset("c", 1, (Placed(),)))])
    e.cast("place", "t:village", {})
    e.cast_column("headcount", "int64", ["t:village"], [100])
    e.run(until=Date(1, 3, 0))
    promo = next(ev for ev in e.events if ev.type == "lod.promote")
    assert promo.place == "t:village" and Cause("event", e.events[0].id) in promo.causes
