"""Review fixes for #48: same-day ordering, born entities, forcer follow-ups, guarding, traces."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "helpers"))
sys.path.insert(0, str(Path(__file__).parent))

from test_pins import COMET, DEATH, Reaper, ComChanger, sky_engine  # noqa: E402

from mini_world import CAL, START  # noqa: E402

from renasci.core.calendar import Date, Span  # noqa: E402
from renasci.core.engine import Engine  # noqa: E402
from renasci.core.events import Cause, EventType  # noqa: E402
from renasci.core.pins import Forcer, Pin, feasibility  # noqa: E402
from renasci.core.systems import Ruleset, System  # noqa: E402


class TwoComets(System):
    name, cadence = "mini.two", "yearly"
    event_types = (COMET,)

    def run(self, ctx):
        if ctx.today.year == 4:
            ctx.emit("mini.comet", {}, purpose="first", actor="t:sky")
            ctx.emit("mini.comet", {}, purpose="second", actor="t:sky")


def test_same_day_events_keep_their_order_and_each_satisfies_one_pin():
    e = sky_engine(systems=(TwoComets(),))
    w = (Date(1, 3, 0), Date(1, 6, 0))
    e.apply_pins([Pin("a", "event", window=w, payload={"type": "mini.comet"}),
                  Pin("b", "event", window=w, payload={"type": "mini.comet"}),
                  Pin("o", "ordering", payload={"before": "a", "after": "b"})])
    e.run(until=Date(1, 8, 0))
    assert e.director.status == {"a": "satisfied", "b": "satisfied", "o": "satisfied"}
    assert e.director.strain == []


BIRTH = EventType("mini.born", 1, roles={"child": (1, 1)}, payload={})


class Stork(System):
    name, cadence = "mini.stork", "yearly"
    writes = frozenset({"new:person"})
    event_types = (BIRTH,)

    def run(self, ctx):
        if ctx.today.year == 3:
            ctx.emit("mini.born", {}, purpose="born", actor="t:sky", creates={"child": [("person", {})]})


def stork_engine(extra=()):
    e = Engine(CAL, seed=1, rulesets=[(START, Ruleset("s", 1, (Stork(), *extra), forcers=(ComChanger(),)))])
    e.cast("place", "t:sky", {})
    return e


def born_id():
    probe = stork_engine()
    probe.run(until=Date(1, 4, 0))
    return next(ev.roles["child"][0] for ev in probe.events if ev.type == "mini.born")


def test_existence_of_a_born_entity_is_met_by_its_creating_event_inside_the_window():
    child = born_id()
    e = stork_engine()
    e.apply_pins([Pin("p", "existence", subject=child, window=(Date(1, 2, 0), Date(1, 5, 0)))])
    e.run(until=Date(1, 8, 0))
    assert e.director.status["p"] == "satisfied" and e.director.strain == []


def test_a_born_entity_created_outside_the_window_violates():
    child = born_id()
    e = stork_engine()
    e.apply_pins([Pin("p", "existence", subject=child, window=(Date(1, 4, 0), Date(1, 5, 0)))])
    e.run(until=Date(1, 8, 0))
    assert e.director.status["p"] == "violated"


def test_born_entities_take_part_in_orderings():
    child = born_id()
    e = stork_engine(extra=(__import__("test_pins").Sky(),))
    e.apply_pins([Pin("p", "existence", subject=child, window=(Date(1, 2, 0), Date(1, 5, 0))),
                  Pin("c", "event", window=(Date(1, 3, 0), Date(1, 6, 0)), payload={"type": "mini.comet"}),
                  Pin("o", "ordering", payload={"before": "p", "after": "c"})])
    e.run(until=Date(1, 8, 0))
    assert e.director.status["o"] == "satisfied" and e.director.strain == []


def test_existence_pins_on_born_ids_need_a_window():
    assert feasibility([Pin("p", "existence", subject="eabc")], START, Date(1, 9, 0))["p"] == "infeasible"


class FollowingForcer(Forcer):
    name = "mini.following_forcer"
    event_types = (COMET, EventType("mini.aftermath", 1, roles={}, payload={}))
    handles = "mini.comet"

    def force(self, ctx, pin):
        ctx.emit("mini.comet", {}, purpose="forced", actor="t:sky")
        ctx.schedule(Span(days=3), "aftermath", entity="t:sky")
        return True

    def handle(self, ctx, activation):
        ctx.emit("mini.aftermath", {}, purpose="aftermath", actor="t:sky")


def test_a_forcer_can_schedule_follow_ups():
    e = sky_engine(systems=(), forcers=(FollowingForcer(),))
    e.apply_pins([Pin("p", "event", window=(Date(1, 3, 0), Date(1, 6, 0)), payload={"type": "mini.comet"})])
    e.run(until=Date(1, 8, 0))
    assert any(ev.type == "mini.aftermath" for ev in e.events) and e.dropped == []


def test_guard_protects_open_existence_and_event_role_members():
    class KingKiller(System):
        name, cadence = "mini.kk", "yearly"
        reads, writes = frozenset({"status"}), frozenset({"status"})
        event_types = (DEATH,)

        def run(self, ctx):
            if ctx.today.year == 2 and ctx.status("t:king") == "active" and not ctx.guarded("t:king"):
                ctx.emit("mini.death", {"deceased": ("t:king",)}, purpose="death", actor="t:king")
                ctx.set_status("t:king", "dead")

    crowning = EventType("mini.crowning", 1, roles={"king": (1, 1)}, payload={})
    e = Engine(CAL, seed=1, rulesets=[(START, Ruleset("k", 1, (KingKiller(),)))])
    e.cast("person", "t:king", {})
    e.registry.register(crowning)
    e.apply_pins([Pin("crown", "event", window=(Date(1, 5, 0), Date(1, 6, 0)),
                      payload={"type": "mini.crowning", "roles": {"king": ["t:king"]}})])
    e.run(until=Date(1, 3, 0))
    assert e.store.status("t:king") == "active"


def test_a_guarded_near_miss_is_caused_by_the_pin_and_recorded_as_a_read():
    e = Engine(CAL, seed=1, rulesets=[(START, Ruleset("r", 1, (Reaper(),)))])
    e.apply_pins([Pin("p_ada", "existence", subject="t:Ada", window=(START, Date(1, 10, 0)),
                      payload={"kind": "person", "fields": {}})])
    e.run(until=Date(1, 5, 0))
    near = next(ev for ev in e.events if ev.type == "mini.near_miss")
    assert Cause("pin", "p_ada") in near.causes
    from renasci.core.canon import digest

    assert any(["t:Ada", "guard", digest("pin:p_ada")] in r["reads"] for r in e.reads)
    assert e.director.strain[0]["event"] == near.id


def test_default_feasibility_end_is_the_last_day_of_the_age():
    e = Engine(CAL, seed=1, rulesets=[(START, Ruleset("e", 1, ()))])
    late = Pin("late", "event", window=(Date(1, 60, 100), Date(1, 60, 200)), payload={"type": "engine.cast"})
    assert e.apply_pins([late])["late"] == "ok"
