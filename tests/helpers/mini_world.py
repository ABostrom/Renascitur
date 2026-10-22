"""A tiny world that exercises every engine feature replay must preserve: randomness, entity
creation, status changes, numeric columns, follow-ups, hinges and a ruleset switch."""

from renasci.core.calendar import Age, Calendar, Date, Span
from renasci.core.engine import Engine
from renasci.core.events import EventType
from renasci.core.systems import Ruleset, System

CAL = Calendar(ages=(Age(1, "1X", "Toy Age", last_year=60),))
START = Date(1, 1, 0)
BIRTH = EventType("mini.birth", 1, roles={"parent": (1, 1), "child": (1, 1)}, payload={})
DEATH = EventType("mini.death", 1, roles={"deceased": (1, 1)}, payload={})
HARVEST = EventType("mini.harvest", 1, roles={"village": (1, 1)}, payload={"grain": "float"})
FEAST = EventType("mini.feast", 1, roles={"village": (1, 1)}, payload={"part": "str"})
VILLAGES = ("t:Eastvale", "t:Millbrook")


class Births(System):
    name, cadence = "mini.births", "monthly"
    reads, writes = frozenset({"ids:person", "status", "village"}), frozenset({"new:person"})
    event_types = (BIRTH,)

    def run(self, ctx):
        for p in ctx.ids("person", status="active"):
            if ctx.chance(0.03, "birth", owner=p, stakes=0.2):
                ctx.emit("mini.birth", {"parent": (p,)}, purpose="birth", actor=p,
                         creates={"child": [("person", {"village": ctx.get(p, "village")})]})


class Deaths(System):
    name, cadence = "mini.deaths", "monthly"
    reads, writes = frozenset({"ids:person", "status"}), frozenset({"status"})
    event_types = (DEATH,)

    def run(self, ctx):
        for p in ctx.ids("person", status="active"):
            if ctx.chance(0.02, "death", owner=p, stakes=0.5):
                ctx.emit("mini.death", {"deceased": (p,)}, purpose="death", actor=p)
                ctx.set_status(p, "dead")


class Granary(System):
    name, cadence = "mini.granary", "seasonal"
    reads, writes = frozenset({"grain"}), frozenset({"grain"})
    event_types = (HARVEST,)

    def run(self, ctx):
        for v in VILLAGES:
            amount = float(max(0.0, ctx.rng("harvest", entity=v).normal(100.0, 20.0)))
            ctx.emit("mini.harvest", {"village": (v,)}, payload={"grain": amount}, purpose="harvest", actor=v)
            ctx.write_column("grain", [v], [float(ctx.read_column("grain", [v])[0]) * 0.5 + amount])


class Feasts(System):
    name, cadence = "mini.feasts", "yearly"
    event_types = (FEAST,)

    def run(self, ctx):
        for v in VILLAGES:
            ctx.emit("mini.feast", {"village": (v,)}, payload={"part": "begin"}, purpose="feast", actor=v)
            ctx.schedule(Span(days=30), "feast_end", entity=v)

    def handle(self, ctx, activation):
        v = activation.entity
        ctx.emit("mini.feast", {"village": (v,)}, payload={"part": "end"}, purpose="feast_end", actor=v)


MARRIAGE = EventType("mini.marriage", 1, roles={"spouse": (2, 2)}, payload={})
ELECTION = EventType("mini.election", 1, roles={"village": (1, 1), "headman": (1, 1)}, payload={})


class Society(System):
    """Yearly: a marriage market across the two villages, and each village elects a headman."""

    name, cadence = "mini.society", "yearly"
    reads = frozenset({"ids:person", "status", "village", "spouse"})
    writes = frozenset({"spouse", "headman"})
    event_types = (MARRIAGE, ELECTION)

    def run(self, ctx):
        single = [p for p in ctx.ids("person", status="active") if ctx.get(p, "spouse") is None]
        east = [p for p in single if ctx.get(p, "village") == VILLAGES[0]]
        west = [p for p in single if ctx.get(p, "village") == VILLAGES[1]]
        if west:
            pairs = ctx.match("marriage", {p: west for p in east}, owner="t:world")
            for a, b in pairs.items():
                ctx.emit("mini.marriage", {"spouse": (a, b)}, purpose="marriage", actor=a)
                ctx.set(a, "spouse", b)
                ctx.set(b, "spouse", a)
        for v in VILLAGES:
            people = [p for p in ctx.ids("person", status="active") if ctx.get(p, "village") == v]
            head = ctx.choose("headman", people, owner=v, stakes=0.7, roles={"village": [v]})
            if head:
                ctx.emit("mini.election", {"village": (v,), "headman": (head,)}, purpose="election", actor=v)
                ctx.set(v, "headman", head)


EARLY = Ruleset("mini.early", 1, (Births(), Deaths(), Granary(), Feasts(), Society()))
LATE = Ruleset("mini.late", 1, (Births(), Deaths(), Granary()))
RULESETS = [(START, EARLY), (Date(1, 20, 0), LATE)]
SEED = 7


def new_engine(reshuffles=()) -> Engine:
    e = Engine(CAL, seed=SEED, rulesets=RULESETS, reshuffles=reshuffles)
    e.cast_column("grain", "float64", VILLAGES, [0.0] * len(VILLAGES))
    for v in VILLAGES:
        e.cast("place", v, {})
    e.cast("place", "t:world", {})
    for i in range(30):
        e.cast("person", f"t:p{i:02d}", {"village": VILLAGES[i % 2]})
    return e
