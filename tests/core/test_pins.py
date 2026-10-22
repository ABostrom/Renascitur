import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "helpers"))

from mini_world import CAL, DEATH, RULESETS, SEED, START, VILLAGES, new_engine  # noqa: E402

from renasci.core.calendar import Date  # noqa: E402
from renasci.core.canon import digest  # noqa: E402
from renasci.core.engine import Engine  # noqa: E402
from renasci.core.events import EventType  # noqa: E402
from renasci.core.pins import Forcer, Pin, feasibility  # noqa: E402
from renasci.core.systems import Ruleset, System  # noqa: E402

RUN = (START, Date(1, 30, 359))

# ---------------------------------------------------------------- feasibility


def test_feasibility_classifies_pins():
    pins = [
        Pin("p_ok", "event", window=(Date(1, 5, 0), Date(1, 6, 0)), payload={"type": "mini.feast"}),
        Pin("p_late", "event", window=(Date(1, 80, 0), Date(1, 81, 0)), payload={"type": "mini.feast"}),
        Pin("p_lineage", "lineage", subject="t:x"),
        Pin("p_bad", "event", window=(Date(1, 9, 0), Date(1, 8, 0)), payload={"type": "mini.feast"}),
    ]
    assert feasibility(pins, *RUN) == {"p_ok": "ok", "p_late": "out_of_scope", "p_lineage": "unsupported",
                                       "p_bad": "infeasible"}


def test_ordering_cycles_are_infeasible():
    a = Pin("a", "event", window=(Date(1, 2, 0), Date(1, 9, 0)), payload={"type": "mini.feast"})
    b = Pin("b", "event", window=(Date(1, 2, 0), Date(1, 9, 0)), payload={"type": "mini.feast"})
    order = [Pin("o1", "ordering", payload={"before": "a", "after": "b"}),
             Pin("o2", "ordering", payload={"before": "b", "after": "a"})]
    result = feasibility([a, b, *order], *RUN)
    assert result["o1"] == result["o2"] == "infeasible"


def test_ordering_against_disjoint_windows_is_infeasible():
    a = Pin("a", "event", window=(Date(1, 8, 0), Date(1, 9, 0)), payload={"type": "mini.feast"})
    b = Pin("b", "event", window=(Date(1, 2, 0), Date(1, 3, 0)), payload={"type": "mini.feast"})
    o = Pin("o", "ordering", payload={"before": "a", "after": "b"})
    assert feasibility([a, b, o], *RUN)["o"] == "infeasible"


def test_pins_validate_their_shape():
    with pytest.raises(ValueError):
        Pin("x", "prophecy")
    with pytest.raises(ValueError):
        Pin("x", "event", window=(START, START))  # an event pin needs a type
    with pytest.raises(ValueError):
        Pin("x", "existence")  # needs a subject


# ---------------------------------------------------------------- casting existence pins


def test_existence_pins_with_cast_ids_are_cast_up_front():
    e = new_engine()
    e.apply_pins([Pin("p_ada", "existence", subject="t:Ada", payload={"kind": "person", "fields": {"village": VILLAGES[0]}})])
    assert e.store.kind("t:Ada") == "person"
    assert e.director.status["p_ada"] == "satisfied"


# ---------------------------------------------------------------- guard


class Reaper(System):
    """Kills t:Ada in year 3 unless the director guards her; a guarded death becomes a near miss."""

    name, cadence = "mini.reaper", "yearly"
    reads, writes = frozenset({"status"}), frozenset({"status"})
    event_types = (DEATH, EventType("mini.near_miss", 1, roles={"survivor": (1, 1)}, payload={}))

    def run(self, ctx):
        if ctx.today.year == 3 and ctx.status("t:Ada") == "active":
            if ctx.guarded("t:Ada"):
                ctx.emit("mini.near_miss", {"survivor": ("t:Ada",)}, purpose="near_miss", actor="t:Ada")
            else:
                ctx.emit("mini.death", {"deceased": ("t:Ada",)}, purpose="death", actor="t:Ada")
                ctx.set_status("t:Ada", "dead")


def reaper_engine():
    e = Engine(CAL, seed=1, rulesets=[(START, Ruleset("r", 1, (Reaper(),)))])
    return e


def test_guard_turns_a_fatal_outcome_into_a_near_miss_and_logs_strain():
    e = reaper_engine()
    e.apply_pins([Pin("p_ada", "existence", subject="t:Ada", window=(START, Date(1, 10, 0)),
                      payload={"kind": "person", "fields": {}})])
    e.run(until=Date(1, 5, 0))
    assert e.store.status("t:Ada") == "active"
    assert any(ev.type == "mini.near_miss" for ev in e.events)
    assert [s["action"] for s in e.director.strain] == ["guard"]


def test_no_guard_after_the_pin_window():
    e = reaper_engine()
    e.apply_pins([Pin("p_ada", "existence", subject="t:Ada", window=(START, Date(1, 2, 0)),
                      payload={"kind": "person", "fields": {}})])
    e.run(until=Date(1, 5, 0))
    assert e.store.status("t:Ada") == "dead" and e.director.strain == []


# ---------------------------------------------------------------- event pins: observe, force, violate

COMET = EventType("mini.comet", 1, roles={}, payload={})


class Sky(System):
    """Year 4 sees a comet, naturally."""

    name, cadence = "mini.sky", "yearly"
    event_types = (COMET,)

    def run(self, ctx):
        if ctx.today.year == 4:
            ctx.emit("mini.comet", {}, purpose="comet", actor="t:sky")


class ComChanger(Forcer):
    name = "mini.comet_forcer"
    event_types = (COMET,)
    handles = "mini.comet"

    def force(self, ctx, pin):
        ctx.emit("mini.comet", {}, purpose="forced_comet", actor="t:sky")
        return True


def sky_engine(systems=(Sky(),), forcers=(ComChanger(),)):
    e = Engine(CAL, seed=1, rulesets=[(START, Ruleset("s", 1, tuple(systems), forcers=tuple(forcers)))])
    e.cast("place", "t:sky", {})
    return e


def test_a_naturally_met_event_pin_is_only_observed():
    e = sky_engine()
    e.apply_pins([Pin("p_comet", "event", window=(Date(1, 3, 0), Date(1, 6, 0)), payload={"type": "mini.comet"})])
    e.run(until=Date(1, 8, 0))
    assert e.director.status["p_comet"] == "satisfied" and e.director.strain == []


def test_an_unmet_event_pin_is_forced_at_its_deadline_with_a_pin_cause():
    e = sky_engine(systems=())
    e.apply_pins([Pin("p_comet", "event", window=(Date(1, 3, 0), Date(1, 6, 0)), payload={"type": "mini.comet"})])
    e.run(until=Date(1, 8, 0))
    forced = [ev for ev in e.events if ev.type == "mini.comet"]
    assert len(forced) == 1 and forced[0].date == Date(1, 6, 0)
    assert e.causes.ancestors(("event", forced[0].id)) == [("activation", forced[0].activation), ("pin", "p_comet")] or \
        ("pin", "p_comet") in e.causes.ancestors(("event", forced[0].id))
    assert e.director.status["p_comet"] == "forced"
    assert [s["action"] for s in e.director.strain] == ["force"]


def test_an_unforceable_pin_is_violated_and_the_run_continues():
    e = sky_engine(systems=(), forcers=())
    e.apply_pins([Pin("p_comet", "event", window=(Date(1, 3, 0), Date(1, 6, 0)), payload={"type": "mini.comet"})])
    e.run(until=Date(1, 8, 0))
    assert e.director.status["p_comet"] == "violated"
    assert [s["action"] for s in e.director.strain] == ["violated"]


def test_ordering_pins_are_checked():
    e = sky_engine()
    a = Pin("a", "event", window=(Date(1, 3, 0), Date(1, 6, 0)), payload={"type": "mini.comet"})
    b = Pin("b", "event", window=(Date(1, 1, 0), Date(1, 2, 0)), payload={"type": "mini.comet"})  # forced at 1-2-0
    e.apply_pins([a, b, Pin("o", "ordering", payload={"before": "a", "after": "b"})])
    e.run(until=Date(1, 8, 0))
    assert e.director.status["o"] == "infeasible"  # windows make a-before-b impossible: classified at load


# ---------------------------------------------------------------- the promotion no-op


def test_promoting_a_natural_event_and_rerunning_changes_nothing():
    base = new_engine()
    base.run(until=Date(1, 10, 0))
    history = base.pending()
    feast = next(ev for ev in base.events if ev.type == "mini.feast" and ev.date.year == 6)
    pin = Pin("p_feast", "event", window=(Date(1, 5, 100), Date(1, 6, 100)),
              payload={"type": "mini.feast", "roles": {"village": [feast.roles["village"][0]]}})
    again = new_engine()
    again.apply_pins([pin])
    again.run(until=Date(1, 10, 0))
    assert digest(again.pending()["events"]) == digest(history["events"])
    assert again.director.strain == [] and again.director.status["p_feast"] == "satisfied"


def test_pins_are_part_of_the_recipe_and_survive_checkpoints():
    e = sky_engine()
    e.apply_pins([Pin("p_comet", "event", window=(Date(1, 3, 0), Date(1, 6, 0)), payload={"type": "mini.comet"})])
    e.run_before(Date(1, 5, 0))
    e.clear_pending()
    cp = e.checkpoint(at=Date(1, 5, 0), segments=0)
    assert cp["header"]["recipe"]["pins"]
    r = Engine.restore(cp, CAL, e.rulesets, seed=1, pins=e.director.pins)
    assert r.director.status == e.director.status
    with pytest.raises(ValueError):
        Engine.restore(cp, CAL, e.rulesets, seed=1)  # pins missing from the recipe
