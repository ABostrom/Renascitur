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
    assert rows and all(set(r) == {"activation", "reads"} for r in rows)
    counter = next(r for r in rows if ["t:world", "count"] in r["reads"])
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
