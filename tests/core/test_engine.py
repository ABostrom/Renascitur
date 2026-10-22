import pytest

from renasci.core.calendar import Age, Calendar, Date, Span
from renasci.core.canon import canonical
from renasci.core.engine import Engine, UndeclaredAccess
from renasci.core.events import Cause, EventType
from renasci.core.systems import Ruleset, System

CAL = Calendar(ages=(Age(1, "1X", "Toy Age", last_year=50),))
TICK = EventType("toy.tick", 1, roles={"subject": (1, 1)}, payload={"n": "int"})
NOTE = EventType("toy.note", 1, roles={"subject": (1, 1)}, payload={})


class Counter(System):
    """Monthly: bump the world's counter and record why."""

    name, cadence = "toy.counter", "monthly"
    reads, writes = frozenset({"count"}), frozenset({"count"})
    event_types = (TICK,)

    def run(self, ctx):
        n = ctx.get("t:world", "count") + 1
        ctx.emit("toy.tick", {"subject": ("t:world",)}, payload={"n": n}, purpose="tick", actor="t:world")
        ctx.set("t:world", "count", n)


class Yearly(System):
    name, cadence, priority = "toy.yearly", "yearly", 5
    reads, writes = frozenset({"count"}), frozenset({"yearly"})
    event_types = (NOTE,)

    def run(self, ctx):
        ctx.emit("toy.note", {"subject": ("t:world",)}, purpose="note", actor="t:world")
        ctx.set("t:world", "yearly", ctx.get("t:world", "count"))
        ctx.schedule(Span(days=10), "follow", entity="t:world", payload={"k": 1})

    def handle(self, ctx, activation):
        ctx.emit("toy.note", {"subject": ("t:world",)}, purpose="followup", actor="t:world")


def world(engine):
    engine.cast("place", "t:world", {"count": 0, "yearly": 0})


def make(rulesets=None, seed=1, strict=True):
    rulesets = rulesets or [(Date(1, 1, 0), Ruleset("toy", 1, (Counter(), Yearly())))]
    e = Engine(CAL, seed=seed, rulesets=rulesets, strict=strict)
    world(e)
    return e


# ---------------------------------------------------------------- running


def test_cadences_run_and_leave_events_and_deltas():
    e = make()
    e.run(until=Date(1, 2, 359))
    assert e.store.get("t:world", "count") == 24
    types = [ev.type for ev in e.events]
    assert types.count("toy.tick") == 24
    assert types.count("toy.note") == 4  # 2 yearly + 2 follow-ups


def test_follow_ups_carry_the_emitting_event_as_a_cause():
    e = make()
    e.run(until=Date(1, 1, 359))
    note = next(ev for ev in e.events if ev.type == "toy.note" and ev.date == Date(1, 1, 0))
    follow = next(ev for ev in e.events if ev.date == Date(1, 1, 10))
    assert Cause("event", note.id) in follow.causes


def test_runs_are_deterministic_and_seed_independent_here():
    a, b = make(), make()
    a.run(until=Date(1, 3, 0))
    b.run(until=Date(1, 3, 0))
    assert canonical([ev.to_json() for ev in a.events]) == canonical([ev.to_json() for ev in b.events])
    assert canonical(a.store.to_json()) == canonical(b.store.to_json())


def test_run_can_be_continued_in_pieces():
    whole, parts = make(), make()
    whole.run(until=Date(1, 3, 0))
    parts.run(until=Date(1, 1, 200))
    parts.run(until=Date(1, 3, 0))
    assert [ev.id for ev in whole.events] == [ev.id for ev in parts.events]


def test_events_are_indexed_and_writes_name_their_event():
    e = make()
    e.run(until=Date(1, 1, 31))
    assert all(d.event in {ev.id for ev in e.events} or d.event.startswith("x") for d in e.store.deltas)
    assert e.causes.has(e.events[0].id)


# ---------------------------------------------------------------- the context enforces the rules


class Sneaky(System):
    name, cadence = "toy.sneaky", "yearly"
    reads, writes = frozenset(), frozenset({"count"})
    event_types = (EventType("toy.sneak", 1, roles={"subject": (1, 1)}, payload={}),)

    def run(self, ctx):
        ctx.get("t:world", "count")  # undeclared read


class NoEvent(System):
    name, cadence = "toy.noevent", "yearly"
    reads, writes = frozenset(), frozenset({"count"})

    def run(self, ctx):
        ctx.set("t:world", "count", 1)


class WrongWrite(System):
    name, cadence = "toy.wrongwrite", "yearly"
    reads, writes = frozenset(), frozenset()
    event_types = (EventType("toy.w", 1, roles={"subject": (1, 1)}, payload={}),)

    def run(self, ctx):
        ctx.emit("toy.w", {"subject": ("t:world",)}, purpose="w", actor="t:world")
        ctx.set("t:world", "count", 1)


@pytest.mark.parametrize("system, error", [(Sneaky, UndeclaredAccess), (WrongWrite, UndeclaredAccess), (NoEvent, ValueError)])
def test_ctx_enforces_reads_writes_and_events(system, error):
    e = make([(Date(1, 1, 0), Ruleset("bad", 1, (system(),)))])
    with pytest.raises(error):
        e.run(until=Date(1, 1, 0))


def test_lenient_mode_allows_undeclared_reads():
    e = make([(Date(1, 1, 0), Ruleset("bad", 1, (Sneaky(),)))], strict=False)
    e.run(until=Date(1, 1, 0))


def test_actual_reads_are_recorded_per_activation():
    e = make()
    e.run(until=Date(1, 1, 0))
    rows = e.reads
    assert rows and all(set(r) == {"activation", "scope", "reads", "events"} for r in rows)
    counter = next(r for r in rows if ["t:world", "count"] in [k[:2] for k in r["reads"]])
    assert counter["activation"].startswith("a")


# ---------------------------------------------------------------- randomness through the context


class Dice(System):
    name, cadence = "toy.dice", "monthly"
    reads, writes = frozenset(), frozenset({"roll"})
    event_types = (EventType("toy.roll", 1, roles={"subject": (1, 1)}, payload={"v": "float"}),)

    def run(self, ctx):
        v = float(ctx.rng("roll", entity="t:world").random())
        ctx.emit("toy.roll", {"subject": ("t:world",)}, payload={"v": v}, purpose="roll", actor="t:world")
        ctx.set("t:world", "roll", v)


def test_rng_is_keyed_and_seeded():
    rs = [(Date(1, 1, 0), Ruleset("dice", 1, (Dice(),)))]
    a, b, c = make(rs, seed=1), make(rs, seed=1), make(rs, seed=2)
    for x in (a, b, c):
        x.run(until=Date(1, 1, 359))
    rolls = lambda x: [ev.payload["v"] for ev in x.events if ev.type == "toy.roll"]
    assert rolls(a) == rolls(b) != rolls(c)
    assert len(set(rolls(a))) == 12


# ---------------------------------------------------------------- rulesets


def test_ruleset_switch_at_a_date():
    rs = [
        (Date(1, 1, 0), Ruleset("early", 1, (Counter(),))),
        (Date(1, 3, 0), Ruleset("late", 1, (Yearly(),))),
    ]
    e = make(rs)
    e.run(until=Date(1, 4, 359))
    ticks = [ev.date for ev in e.events if ev.type == "toy.tick"]
    notes = [ev.date for ev in e.events if ev.type == "toy.note"]
    assert max(ticks) < Date(1, 3, 0)
    assert min(notes) == Date(1, 3, 0)
    assert e.ruleset.name == "late"


def test_rulesets_must_start_at_the_first_date_and_be_ordered():
    with pytest.raises(ValueError):
        Engine(CAL, seed=1, rulesets=[])
    with pytest.raises(ValueError):
        Engine(CAL, seed=1, rulesets=[(Date(1, 3, 0), Ruleset("a", 1, ())), (Date(1, 2, 0), Ruleset("b", 1, ()))])


def test_system_declarations_are_checked():
    class Bad(System):
        name, cadence = "toy.bad", "hourly"

    with pytest.raises(ValueError):
        Ruleset("r", 1, (Bad(),))
    with pytest.raises(ValueError):
        Ruleset("r", 1, (Counter(), Counter()))


# ---------------------------------------------------------------- review fixes

CAL2 = Calendar(ages=(Age(1, "1X", "Toy Age", last_year=2), Age(2, "2X", "Next Age")))


def make2(rulesets, strict=True):
    e = Engine(CAL2, seed=1, rulesets=rulesets, strict=strict)
    world(e)
    return e


def test_a_system_carried_across_an_age_boundary_keeps_running():
    rs = [(Date(1, 1, 0), Ruleset("a", 1, (Counter(),))), (Date(2, 1, 0), Ruleset("b", 1, (Counter(),)))]
    e = make2(rs)
    e.run(until=Date(2, 1, 359))
    assert sum(1 for ev in e.events if ev.type == "toy.tick" and ev.date.age == 2) == 12


def test_a_system_can_leave_and_come_back():
    rs = [
        (Date(1, 1, 0), Ruleset("in", 1, (Yearly(),))),
        (Date(1, 1, 100), Ruleset("out", 1, ())),
        (Date(1, 1, 200), Ruleset("back", 1, (Yearly(),))),
    ]
    e = make(rs)
    e.run(until=Date(1, 2, 359))
    notes = sorted(ev.date for ev in e.events if ev.type == "toy.note" and ev.payload == {})
    # day 0 run + day 10 follow-up; restarted at day 200 (+ follow-up day 210); then year 2 (+ follow-up)
    assert notes == [Date(1, 1, 0), Date(1, 1, 10), Date(1, 1, 200), Date(1, 1, 210), Date(1, 2, 0), Date(1, 2, 10)]


class YearlyOnDemand(Yearly):
    cadence = "on_demand"


def test_a_system_whose_cadence_changes_restarts_its_chain():
    rs = [(Date(1, 1, 0), Ruleset("a", 1, (YearlyOnDemand(),))), (Date(1, 2, 0), Ruleset("b", 1, (Yearly(),)))]
    e = make(rs)
    e.run(until=Date(1, 3, 359))
    assert [ev.date for ev in e.events if ev.type == "toy.note" and ev.date.day == 0] == [Date(1, 2, 0), Date(1, 3, 0)]
    rs = [(Date(1, 1, 0), Ruleset("a", 1, (Yearly(),))), (Date(1, 2, 0), Ruleset("b", 1, (YearlyOnDemand(),)))]
    e = make(rs)
    e.run(until=Date(1, 3, 359))
    assert [ev.date for ev in e.events if ev.type == "toy.note" and ev.date.day == 0] == [Date(1, 1, 0)]


class Lister(System):
    name, cadence = "toy.lister", "yearly"
    reads, writes = frozenset({"ids:person", "status"}), frozenset()

    def run(self, ctx):
        ctx.ids("person", status="active")


def test_listing_ids_records_every_status_it_looked_at():
    e = make([(Date(1, 1, 0), Ruleset("l", 1, (Lister(),)))])
    e.cast("person", "t:a", {})
    e.cast("person", "t:b", {})
    e.run(until=Date(1, 1, 0))
    reads = [k[:2] for k in e.reads[0]["reads"]]
    assert ["t:a", "status"] in reads and ["t:b", "status"] in reads and ["$person", "ids"] in reads


DEATH = EventType("toy.death", 1, roles={"deceased": (1, 1)}, payload={})


class Reaper(System):
    """Kills everyone in the skip list's complement, one event per person."""

    name, cadence = "toy.reaper", "yearly"
    reads, writes = frozenset({"ids:person", "status"}), frozenset({"status"})
    event_types = (DEATH,)
    skip = ()

    def run(self, ctx):
        for p in ctx.ids("person", status="active"):
            if p in self.skip:
                continue
            ctx.emit("toy.death", {"deceased": (p,)}, purpose="death", actor=p)
            ctx.set_status(p, "dead")


def test_event_ids_do_not_shift_when_an_earlier_event_is_skipped():
    def run(skip):
        reaper = Reaper()
        reaper.skip = skip
        e = make([(Date(1, 1, 0), Ruleset("r", 1, (reaper,)))])
        for p in ("t:a", "t:b", "t:c"):
            e.cast("person", p, {})
        e.run(until=Date(1, 1, 0))
        return {ev.roles["deceased"][0]: ev.id for ev in e.events if ev.type == "toy.death"}

    assert run(())["t:c"] == run(("t:a",))["t:c"]


def test_emit_requires_an_explicit_actor():
    class NoActor(Counter):
        def run(self, ctx):
            ctx.emit("toy.tick", {"subject": ("t:world",)}, payload={"n": 1}, purpose="tick")

    e = make([(Date(1, 1, 0), Ruleset("n", 1, (NoActor(),)))])
    with pytest.raises(TypeError):
        e.run(until=Date(1, 1, 0))


def test_writes_and_events_name_their_activation_and_follow_ups_their_parent():
    e = make()
    e.run(until=Date(1, 1, 10))
    tick = next(ev for ev in e.events if ev.type == "toy.tick")
    assert tick.activation and tick.activation.startswith("a")
    delta = next(d for d in e.store.deltas if d.field == "count" and d.event == tick.id)
    assert delta.activation == tick.activation
    follow = next(ev for ev in e.events if ev.date == Date(1, 1, 10))
    assert any(c.kind == "activation" for c in follow.causes)


def test_engine_can_schedule_any_system():
    e = make([(Date(1, 1, 0), Ruleset("o", 1, (YearlyOnDemand(),)))])
    e.run(until=Date(1, 1, 0))
    e.schedule("toy.yearly", Date(1, 1, 5), "follow", entity="t:world")
    e.run(until=Date(1, 1, 5))
    assert any(ev.date == Date(1, 1, 5) for ev in e.events)


def test_params_cannot_be_mutated_through_ctx():
    class Mutator(Counter):
        def run(self, ctx):
            ctx.params["x"] = 99

    rs = Ruleset("m", 1, (Mutator(),), params={"x": 1})
    e = make([(Date(1, 1, 0), rs)])
    e.run(until=Date(1, 1, 30))
    assert rs.params == {"x": 1}


def test_exists_and_kind_are_recorded_reads():
    class Prober(System):
        name, cadence = "toy.prober", "yearly"
        reads = frozenset({"status"})

        def run(self, ctx):
            assert ctx.exists("t:world") and ctx.kind("t:world") == "place"
            assert not ctx.exists("t:nowhere")

    e = make([(Date(1, 1, 0), Ruleset("p", 1, (Prober(),)))])
    e.run(until=Date(1, 1, 0))
    reads = [k[:2] for k in e.reads[0]["reads"]]
    assert ["t:world", "status"] in reads and ["t:nowhere", "status"] in reads


def test_engine_remembers_which_ruleset_is_active():
    rs = [(Date(1, 1, 0), Ruleset("a", 1, ())), (Date(1, 2, 0), Ruleset("b", 1, ()))]
    e = make(rs)
    e.run(until=Date(1, 2, 0))
    assert e.ruleset_index == 1


# ---------------------------------------------------------------- scoped reads and the activations table


class Scoped(System):
    name, cadence = "toy.scoped", "yearly"
    reads = frozenset({"count"})
    writes = frozenset({"count"})
    event_types = (TICK,)

    def run(self, ctx):
        ctx.get("t:world", "count")  # unscoped: applies to everything this activation does
        for v in ("t:a", "t:b"):
            with ctx.scope(v):
                n = ctx.get(v, "count")
                ctx.emit("toy.tick", {"subject": (v,)}, payload={"n": n + 1}, purpose="tick", actor=v)
                ctx.set(v, "count", n + 1)


def test_reads_are_recorded_per_scope_with_the_events_they_informed():
    e = make([(Date(1, 1, 0), Ruleset("s", 1, (Scoped(),)))])
    e.cast("place", "t:a", {"count": 0})
    e.cast("place", "t:b", {"count": 0})
    e.run(until=Date(1, 1, 0))
    rows = {r["scope"]: r for r in e.reads}
    keys = lambda row: [k[:2] for k in row["reads"]]  # noqa: E731
    assert keys(rows[None]) == [["t:world", "count"]] and rows[None]["events"] == []
    a_tick = next(ev.id for ev in e.events if ev.type == "toy.tick" and ev.roles["subject"] == ("t:a",))
    assert keys(rows["t:a"]) == [["t:a", "count"]] and rows["t:a"]["events"] == [a_tick]
    assert keys(rows["t:b"]) == [["t:b", "count"]]
    from renasci.core.canon import digest

    assert rows["t:a"]["reads"][0][2] == digest(0)  # the value seen is recorded too


def test_scopes_do_not_nest():
    class Nested(Scoped):
        name = "toy.nested"

        def run(self, ctx):
            with ctx.scope("t:a"):
                with ctx.scope("t:b"):
                    pass

    e = make([(Date(1, 1, 0), Ruleset("n", 1, (Nested(),)))])
    with pytest.raises(ValueError):
        e.run(until=Date(1, 1, 0))


def test_every_dispatched_activation_is_listed_in_order():
    e = make()
    e.run(until=Date(1, 1, 59))
    acts = e.pending()["activations"]
    assert [a["system"] for a in acts[:2]] == ["toy.counter", "toy.yearly"]
    assert all(set(a) == {"activation", "system", "date", "causes"} for a in acts)
    assert len({a["activation"] for a in acts}) == len(acts)
