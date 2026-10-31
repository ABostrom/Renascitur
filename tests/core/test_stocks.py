import pytest

from renasci.core import stocks
from renasci.core.calendar import Age, Calendar, Date, Span
from renasci.core.engine import Engine
from renasci.core.events import EventType
from renasci.core.systems import Ruleset, System


class Fake:
    """Just enough of a ctx: fields in a dict, and the event being written under."""

    def __init__(self):
        self.fields, self.current_event = {}, "e0"

    def get(self, entity, field, default=None):
        return self.fields.get((entity, field), default)

    def set(self, entity, field, value):
        self.fields[(entity, field)] = value


def filled(*amounts):
    ctx = Fake()
    for i, amount in enumerate(amounts):
        ctx.current_event = f"e{i}"
        stocks.add(ctx, "town", "corpses", amount)
    return ctx


def refs(ctx, **kw):
    return [c.ref for c in stocks.because(ctx, "town", "corpses", **kw)]


def test_a_stock_builds_and_starts_empty():
    ctx = filled(3.0, 2.0)
    assert stocks.level(ctx, "town", "corpses") == 5.0
    assert stocks.level(ctx, "town", "nothing") == 0.0


def test_a_stock_says_what_filled_it_largest_first():
    ctx = filled(1.0, 5.0, 2.0)
    causes = stocks.because(ctx, "town", "corpses")
    assert [c.ref for c in causes] == ["e1", "e2", "e0"] and all(c.kind == "event" for c in causes)


def test_ties_break_by_event_so_order_of_arrival_never_shows():
    a, b = Fake(), Fake()
    for ctx, order in ((a, ("e1", "e2")), (b, ("e2", "e1"))):
        for event in order:
            ctx.current_event = event
            stocks.add(ctx, "town", "corpses", 1.0)
    assert refs(a) == refs(b) == ["e1", "e2"]


def test_one_event_adding_twice_counts_once():
    ctx = filled(1.0)
    stocks.add(ctx, "town", "corpses", 2.0)
    assert refs(ctx) == ["e0"] and stocks.level(ctx, "town", "corpses") == 3.0


def test_taking_shares_the_loss_across_what_filled_it():
    ctx = filled(6.0, 2.0)
    assert stocks.take(ctx, "town", "corpses", 4.0) == 4.0
    assert stocks.level(ctx, "town", "corpses") == 4.0
    assert ctx.fields[("town", "why:corpses")] == {"e0": 3.0, "e1": 1.0}


def test_taking_more_than_there_is_takes_what_there_is():
    ctx = filled(2.0)
    assert stocks.take(ctx, "town", "corpses", 5.0) == 2.0
    assert stocks.level(ctx, "town", "corpses") == 0.0 and refs(ctx) == []


def test_draining_nothing_writes_nothing():
    ctx = Fake()
    assert stocks.take(ctx, "town", "corpses", 3.0) == 0.0 and stocks.fade(ctx, "town", "corpses", 0.5) == 0.0
    stocks.add(ctx, "town", "corpses", 0.0)
    assert ctx.fields == {}
    ctx = filled(0.00005)
    before = dict(ctx.fields)
    assert stocks.take(ctx, "town", "corpses", 0.0) == 0.0 and ctx.fields == before


def test_a_fading_stock_reaches_empty_and_stops_citing():
    ctx = filled(100.0)
    for _ in range(400):
        stocks.fade(ctx, "town", "corpses", 0.25)
    assert stocks.level(ctx, "town", "corpses") == 0.0 and refs(ctx) == []


@pytest.mark.parametrize("bad", [float("nan"), float("inf")])
def test_a_non_finite_amount_is_refused(bad):
    with pytest.raises(ValueError, match="corpses"):
        stocks.take(filled(5.0), "town", "corpses", bad)


def test_a_stock_is_not_a_goods_column():
    ctx = filled(1.0)
    assert ("town", "level:corpses") in ctx.fields and not any(f.startswith("stock:") for _, f in ctx.fields)
    assert not any(n.startswith("stock:") for n in stocks.READS | stocks.WRITES)


def test_a_stock_fades_by_a_share():
    ctx = filled(8.0)
    stocks.fade(ctx, "town", "corpses", 0.25)
    assert stocks.level(ctx, "town", "corpses") == 6.0
    assert ctx.fields[("town", "why:corpses")] == {"e0": 6.0}


def test_the_record_is_capped_at_the_largest_and_the_level_stays_whole():
    ctx = filled(*[float(i + 1) for i in range(stocks.KEPT + 5)])
    assert stocks.level(ctx, "town", "corpses") == sum(i + 1 for i in range(stocks.KEPT + 5))
    assert len(ctx.fields[("town", "why:corpses")]) == stocks.KEPT
    assert refs(ctx)[0] == f"e{stocks.KEPT + 4}"


def test_a_citation_can_ask_for_fewer():
    assert len(refs(filled(1.0, 2.0, 3.0), most=2)) == 2


def test_a_negative_amount_is_refused():
    with pytest.raises(ValueError, match="corpses"):
        filled(-1.0)
    with pytest.raises(ValueError, match="corpses"):
        stocks.take(filled(1.0), "town", "corpses", -1.0)


NOTED = EventType("test.noted", 1, roles={"thing": (1, 1)}, payload={})
FELL = EventType("test.fell", 1, roles={"thing": (0, 1)}, payload={})
TOLD = EventType("test.told", 1, roles={"thing": (0, 1)}, payload={})


def test_a_follow_up_can_cite_a_stock_filled_by_the_event_it_follows():
    class Again(System):
        name, cadence, priority = "test.again", "yearly", 1
        reads = stocks.READS | frozenset({"ids:thing"})
        writes = stocks.WRITES | frozenset({"new:thing"})
        event_types = (NOTED,)

        def run(self, ctx):
            ev = ctx.emit("test.noted", {}, purpose="note", actor="t:pile", creates={"thing": [("thing", {})]})
            thing = ev.roles["thing"][0]
            stocks.add(ctx, thing, "corpses", 1.0)
            ctx.schedule(Span(days=1), "later", entity=thing, causes=stocks.because(ctx, thing, "corpses"))

        def handle(self, ctx, activation):
            pass

    cal = Calendar(ages=(Age(1, "1X", "Test", last_year=5),))
    Engine(cal, 1, [(Date(1, 1, 0), Ruleset("again", 1, (Again(),)))]).run(until=Date(1, 2, 0))


class Pile(System):
    name, cadence, priority = "test.pile", "yearly", 1
    reads = stocks.READS | frozenset({"ids:thing"})
    writes = stocks.WRITES | frozenset({"new:thing"})
    event_types = (NOTED, FELL, TOLD)

    def run(self, ctx):
        things = ctx.ids("thing")
        if not things:
            ctx.emit("test.noted", {}, purpose="note", actor="t:pile", creates={"thing": [("thing", {})]})
            return
        if ctx.today.year == 2 and not stocks.level(ctx, things[0], "corpses"):
            ctx.emit("test.fell", {"thing": (things[0],)}, purpose="fall", actor=things[0])
            stocks.add(ctx, things[0], "corpses", 3.0)
        if ctx.today.year == 3:
            ctx.emit("test.told", {"thing": (things[0],)}, purpose="tell", actor=things[0],
                     causes=stocks.because(ctx, things[0], "corpses"))


def test_in_a_real_run_an_event_cites_what_filled_the_stock():
    cal = Calendar(ages=(Age(1, "1X", "Test", last_year=5),))
    e = Engine(cal, 1, [(Date(1, 1, 0), Ruleset("pile", 1, (Pile(),)))])
    e.run(until=Date(1, 4, 0))
    fell = next(x for x in e.events if x.type == "test.fell")
    told = next(x for x in e.events if x.type == "test.told")
    assert fell.id in [c.ref for c in told.causes]
    assert ("event", fell.id) in e.causes.ancestors(("event", told.id))
