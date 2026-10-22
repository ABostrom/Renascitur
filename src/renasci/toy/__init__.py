"""The toy world: just rich enough to test what is hard to get right.

Six villages in two valleys, a few hundred people. Not Renascita: nothing here is lore.

- `toy.life` (monthly): age, famine and infancy raise the risk of death. A guarded person survives
  as a near miss.
- `toy.marriage` (seasonal): a marriage market within each valley, preferring the same village.
- `toy.births` (seasonal): married women of age may have a child.
- `toy.granary` (seasonal): each valley shares one granary. Autumn harvests fill it, and every
  season eats from it. An empty granary means famine for the whole valley. **This shared resource
  is the locality test**: a change in one village reaches the others through the stores.
- `toy.migration` (yearly): people move between villages of their valley.

The two valleys never touch, so a ripple in one must leave the other byte-identical.

Villages keep a `residents` roster, so systems never list every person in the world: that would
couple the valleys through the listing alone. Batch systems work one village or valley at a time
inside `ctx.scope`, so divergence analysis can tell which unit a change touched.
"""

from __future__ import annotations

from renasci.core.calendar import Age, Calendar, Date, Span
from renasci.core.engine import Engine
from renasci.core.events import EventType
from renasci.core.pins import Forcer
from renasci.core.ripples import Disguise
from renasci.core.systems import Ruleset, System

CAL = Calendar(ages=(Age(1, "1X", "Toy Age", last_year=400),))
START = Date(1, 1, 0)
VALLEYS = {"t:North": ("t:Ashford", "t:Brook", "t:Cairn"), "t:South": ("t:Dale", "t:Elm", "t:Fen")}
VILLAGES = tuple(v for vs in VALLEYS.values() for v in vs)
VALLEY_OF = {v: valley for valley, vs in VALLEYS.items() for v in vs}

DEATH = EventType("toy.death", 1, roles={"deceased": (1, 1)}, payload={"cause": "str"})
NEAR_MISS = EventType("toy.near_miss", 1, roles={"survivor": (1, 1)}, payload={"cause": "str"})
MARRIAGE = EventType("toy.marriage", 1, roles={"spouse": (2, 2)}, payload={})
BIRTH = EventType("toy.birth", 1, roles={"mother": (1, 1), "child": (1, 1)}, payload={})
GRANARY = EventType("toy.granary", 1, roles={"valley": (1, 1)}, payload={"harvest": "float", "eaten": "float",
                                                                       "stock": "float", "famine": "bool"})
MOVE = EventType("toy.move", 1, roles={"mover": (1, 1), "from": (1, 1), "to": (1, 1)}, payload={})
FIRE = EventType("toy.fire", 1, roles={"village": (1, 1)}, payload={})


def _age(ctx, person) -> int:
    return ctx.today.year - ctx.get(person, "born")


def _remove_resident(ctx, village, person) -> None:
    ctx.set(village, "residents", [p for p in ctx.get(village, "residents") if p != person])


def _add_resident(ctx, village, person) -> None:
    ctx.set(village, "residents", sorted(ctx.get(village, "residents") + [person]))


def _die(ctx, person, village, cause) -> None:
    ctx.emit("toy.death", {"deceased": (person,)}, purpose="death", actor=person, place=village,
             payload={"cause": cause})
    ctx.set_status(person, "dead")
    _remove_resident(ctx, village, person)
    spouse = ctx.get(person, "spouse")
    if spouse:
        ctx.set(spouse, "spouse", None)


class Life(System):
    name, cadence = "toy.life", "monthly"
    reads = frozenset({"residents", "born", "famine", "spouse", "status"})
    writes = frozenset({"status", "residents", "spouse"})
    event_types = (DEATH, NEAR_MISS)

    def run(self, ctx):
        for v in VILLAGES:
            with ctx.scope(v):
                famine = ctx.get(VALLEY_OF[v], "famine")
                for p in ctx.get(v, "residents"):
                    age = _age(ctx, p)
                    hazard = 0.0008 + (0.004 if age < 2 else 0) + (0.006 if age > 55 else 0) + (0.012 if age > 70 else 0)
                    hazard += 0.01 if famine else 0
                    if ctx.chance(hazard, "death", owner=p, stakes=0.6, roles={"person": [p]}):
                        cause = "famine" if famine else ("old age" if age > 55 else "illness")
                        if ctx.guarded(p):
                            ctx.emit("toy.near_miss", {"survivor": (p,)}, purpose="near_miss", actor=p, place=v,
                                     payload={"cause": cause})
                        else:
                            _die(ctx, p, v, cause)


class Marriage(System):
    name, cadence = "toy.marriage", "seasonal"
    reads = frozenset({"residents", "born", "sex", "spouse"})
    writes = frozenset({"spouse"})
    event_types = (MARRIAGE,)

    def run(self, ctx):
        for valley, villages in VALLEYS.items():
            with ctx.scope(valley):
                men, women = [], []
                for v in villages:
                    for p in ctx.get(v, "residents"):
                        if ctx.get(p, "spouse") is None and 16 <= _age(ctx, p) <= 45:
                            (men if ctx.get(p, "sex") == "m" else women).append((p, v))
                if not men or not women:
                    continue
                seekers = {m: {w: (3.0 if wv == mv else 1.0) for w, wv in women} for m, mv in men}
                for a, b in ctx.match("marriage", seekers, owner=valley).items():
                    ctx.emit("toy.marriage", {"spouse": (a, b)}, purpose="marriage", actor=a)
                    ctx.set(a, "spouse", b)
                    ctx.set(b, "spouse", a)


class Births(System):
    name, cadence = "toy.births", "seasonal"
    reads = frozenset({"residents", "born", "sex", "spouse"})
    writes = frozenset({"new:person", "residents"})
    event_types = (BIRTH,)

    def run(self, ctx):
        for v in VILLAGES:
            with ctx.scope(v):
                for p in ctx.get(v, "residents"):
                    if ctx.get(p, "sex") != "f" or ctx.get(p, "spouse") is None or not 16 <= _age(ctx, p) <= 40:
                        continue
                    if ctx.chance(0.05, "birth", owner=p, stakes=0.3, roles={"mother": [p]}):
                        sex = "f" if ctx.chance(0.5, "sex", owner=p) else "m"
                        event = ctx.emit("toy.birth", {"mother": (p,)}, purpose="birth", actor=p, place=v,
                                         creates={"child": [("person", {"sex": sex, "born": ctx.today.year,
                                                                        "village": v, "spouse": None})]})
                        _add_resident(ctx, v, event.roles["child"][0])


class Granary(System):
    name, cadence = "toy.granary", "seasonal"
    reads = frozenset({"residents", "stock"})
    writes = frozenset({"stock", "famine"})
    event_types = (GRANARY,)

    def run(self, ctx):
        autumn = ctx.calendar.season(ctx.today) == 2
        for valley, villages in VALLEYS.items():
            with ctx.scope(valley):
                heads = sum(len(ctx.get(v, "residents")) for v in villages)
                harvest = 0.0
                if autumn:
                    for v in villages:
                        harvest += max(0.0, float(ctx.rng("harvest", entity=v).normal(1.0, 0.4))) \
                            * len(ctx.get(v, "residents"))
                eaten = heads * 0.25
                stock = float(ctx.read_column("stock", [valley])[0]) + harvest - eaten
                famine = stock < 0
                stock = max(0.0, stock)
                ctx.emit("toy.granary", {"valley": (valley,)}, purpose="granary", actor=valley,
                         payload={"harvest": harvest, "eaten": eaten, "stock": stock, "famine": famine})
                ctx.write_column("stock", [valley], [stock])
                ctx.set(valley, "famine", famine)


class Migration(System):
    name, cadence = "toy.migration", "yearly"
    reads = frozenset({"residents", "born"})
    writes = frozenset({"residents", "village"})
    event_types = (MOVE,)

    def destination(self, ctx, person, others):
        return ctx.choose("destination", others, owner=person)

    def run(self, ctx):
        for valley, villages in VALLEYS.items():
            with ctx.scope(valley):
                for v in villages:
                    for p in ctx.get(v, "residents"):
                        if _age(ctx, p) >= 16 and ctx.chance(0.03, "migrate", owner=p):
                            dest = self.destination(ctx, p, [x for x in villages if x != v])
                            ctx.emit("toy.move", {"mover": (p,), "from": (v,), "to": (dest,)}, purpose="move", actor=p)
                            _remove_resident(ctx, v, p)
                            _add_resident(ctx, dest, p)
                            ctx.set(p, "village", dest)


class _Counter:
    n = 0


class BuggyMigration(Migration):
    """The negative control: picks destinations with a counter shared across the whole world.

    A ripple that changes how many people move in one valley shifts every later pick in the other.
    Divergence analysis must report that as unexplained.
    """

    def run(self, ctx):
        for valley, villages in VALLEYS.items():
            with ctx.scope(valley):
                for v in villages:
                    for p in ctx.get(v, "residents"):
                        _Counter.n += 1  # one counter for the whole world: the bug
                        if _age(ctx, p) >= 16 and (_Counter.n * 2654435761) % 100 < 3:
                            dest = [x for x in villages if x != v][_Counter.n % 2]
                            ctx.emit("toy.move", {"mover": (p,), "from": (v,), "to": (dest,)}, purpose="move", actor=p)
                            _remove_resident(ctx, v, p)
                            _add_resident(ctx, dest, p)
                            ctx.set(p, "village", dest)


class Illness(Disguise):
    """doom, disguised: a sudden illness."""

    name, handles = "toy.illness", "doom"
    reads = frozenset({"village", "status", "spouse", "residents"})
    writes = frozenset({"status", "residents", "spouse"})
    event_types = (DEATH,)

    def apply(self, ctx, ripple):
        if ctx.status(ripple.target) != "active":
            return False
        _die(ctx, ripple.target, ctx.get(ripple.target, "village"), "sudden illness")
        return True


class FireDisguise(Disguise):
    """inject, disguised: a fire in a village."""

    name, handles = "toy.fire_disguise", "inject"
    event_types = (FIRE,)

    def apply(self, ctx, ripple):
        ctx.emit("toy.fire", {"village": (ripple.target,)}, purpose="fire", actor=ripple.target)
        return True


class FireForcer(Forcer):
    name, handles = "toy.fire_forcer", "toy.fire"
    event_types = (FIRE,)

    def force(self, ctx, pin):
        village = pin.payload.get("roles", {}).get("village", [VILLAGES[0]])[0]
        ctx.emit("toy.fire", {"village": (village,)}, purpose="forced_fire", actor=village)
        return True


def ruleset(buggy: bool = False) -> Ruleset:
    migration = BuggyMigration() if buggy else Migration()
    return Ruleset("toy", 1, (Life(), Marriage(), Births(), Granary(), migration),
                   forcers=(FireForcer(),), disguises=(Illness(), FireDisguise()))


def new_engine(seed: int = 1234, ripples=(), pins=(), buggy: bool = False, people_per_village: int = 24) -> Engine:
    """A fresh toy world at 1X 1, before anything runs."""
    _Counter.n = 0
    e = Engine(CAL, seed=seed, rulesets=[(START, ruleset(buggy))])
    e.cast_column("stock", "float64", list(VALLEYS), [60.0] * len(VALLEYS))
    for valley in VALLEYS:
        e.cast("place", valley, {"famine": False})
    for vi, v in enumerate(VILLAGES):
        people = [f"{v}-{i:02d}" for i in range(people_per_village)]
        e.cast("place", v, {"valley": VALLEY_OF[v], "residents": sorted(people)})
        for i, p in enumerate(people):
            e.cast("person", p, {"sex": "f" if i % 2 else "m", "born": 1 - (i * 7 + vi * 3) % 50,
                                 "village": v, "spouse": None})
    e.apply_pins(pins)
    e.apply_ripples(ripples)
    return e


def run(seed: int = 1234, years: int = 40, **kw) -> Engine:
    e = new_engine(seed, **kw)
    e.run(until=Date(1, years, CAL.days_per_year - 1))
    return e


__all__ = ["CAL", "START", "VALLEYS", "VILLAGES", "VALLEY_OF", "new_engine", "run", "ruleset", "Span"]
