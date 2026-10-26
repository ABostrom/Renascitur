"""Materials, crafting and masterworks (S9 spec §3, #124): what towns yield, and the rare thing a master makes.

Only in a world whose `crafts` catalogue names `materials` (`{id: {name, by: [jobs], yield: {region | "*": per
worker a year}, value}}`) and object `types` (`{id: {name, material, cost}}`), with an optional `master_rate`.
The scenario casts, per settlement, `stock:<m>` and the goods ledger `goods:<m>:<flow>` (all ints): the
invariant, exact, is initial + produced + traded_in = stock + used + traded_out + destroyed (`balance`).

`people.crafts` (yearly, after `people.work`; one `ctx.scope(settlement)` per settlement):

1. **Yield:** each material's workers in the town (the masses in its `by` jobs, and notables holding them) times
   its yield for the town's region (`"*"` for anywhere) goes into stock (`goods.yield`, `produced`).
2. **Masterworks:** each maker (a notable whose job `makes` types), most skilled first, tries for a masterwork
   of the first type they make whose material the town has: a keyed draw (`act:craft`, so S1's favour reaches
   it) at `skill^3 x master_rate`. A success uses the type's `cost` of its material (`used`) and makes an
   **object** (`object.made`): its `type`, `material`, `maker`, `made` (date, place), `quality` (the maker's
   skill), `owner`, `place`, `deeds`, `fame`, `lost`. At most one a town a year.
3. **First owner:** a keyed pick among the town's grown notables, weighted by wealth and by a friendly tie to
   the maker (the maker may keep it): `object.given`; a buyer pays its price (`value x cost`, more for quality),
   or what wealth they have if less, to the maker. Yields carry their fractions year to year (`yield_carry`).

This system is the spec's `objects` system: the only writer of an object's fields (#126 adds what happens to
objects after). A coarse step yields N years and draws "a masterwork in N years".
"""

from __future__ import annotations

from renasci.core.events import Cause, EventType
from renasci.core.systems import System
from renasci.people.races import age_years
from renasci.relations import over

FLOWS = ("initial", "produced", "used", "traded_in", "traded_out", "destroyed")
MASTER_RATE = 0.05
ADULT = 16
TIE = 4.0  # (a friend of the maker is likelier to get it)

YIELD = EventType("goods.yield", 1, roles={"settlement": (1, 1)}, payload={"produced": "json"})
MADE = EventType("object.made", 1, roles={"maker": (1, 1), "object": (1, 1)},
                 payload={"type": "str", "material": "str", "quality": "float"})
GIVEN = EventType("object.given", 1, roles={"giver": (0, 1), "owner": (1, 1), "object": (1, 1)},
                  payload={"price": "float"})
EVENT_TYPES = (YIELD, MADE, GIVEN)
READS = frozenset({"ids:settlement", "residents", "region", "born", "job", "skills", "wealth", "ties", "a", "b",
                   "kind", "journey", "possessions", "yield_carry", "stock:*", "goods:*", "job:*"})
WRITES = frozenset({"stock:*", "goods:*", "new:object", "owner", "wealth", "possessions", "yield_carry"})
FRIENDLY = ("friend", "mentor", "lover")


def catalogue(ctx) -> dict:
    return ctx.params.get("crafts") or {}


def balance(store, settlement: str, material: str) -> int:
    """The goods ledger's imbalance for one material in one town (0 when it holds)."""
    g = {f: int(store.read_column(f"goods:{material}:{f}", [settlement])[0]) for f in FLOWS}
    stock = int(store.read_column(f"stock:{material}", [settlement])[0])
    return g["initial"] + g["produced"] + g["traded_in"] - (stock + g["used"] + g["traded_out"] + g["destroyed"])


def cast(engine, settlements: list[str], crafts: dict) -> None:
    """Every town's stock and goods ledger, empty at the start."""
    for m in sorted(crafts.get("materials") or {}):
        engine.cast_column(f"stock:{m}", "int64", settlements, [0] * len(settlements))
        for f in FLOWS:
            engine.cast_column(f"goods:{m}:{f}", "int64", settlements, [0] * len(settlements))


class Crafts(System):
    name, cadence = "people.crafts", "yearly"
    priority = 5  # (after people.work: this year's workers and skills)
    reads, writes, event_types = READS, WRITES, EVENT_TYPES

    def run(self, ctx):
        self.step(ctx, 1)

    def coarse_fallback(self, ctx, years: int) -> None:
        self.step(ctx, years)

    def step(self, ctx, years: int) -> None:
        cat = catalogue(ctx)
        for s in ctx.ids("settlement"):
            with ctx.scope(s):
                self.produce(ctx, s, cat, years)
                self.make(ctx, s, cat, years)

    def produce(self, ctx, s, cat, years) -> None:
        mats = cat.get("materials") or {}
        region = ctx.get(s, "region")
        jobs = sorted({j for m in mats.values() for j in m.get("by", [])})
        masses = ctx.read_columns(s, [f"job:{j}" for j in jobs]) if ctx.params.get("aggregates") and jobs else {}
        notables = [ctx.get(p, "job") for p in ctx.get(s, "residents") if not ctx.get(p, "journey")]
        made, carry = {}, dict(ctx.get(s, "yield_carry") or {})
        for m in sorted(mats):
            spec = mats[m]
            rate = float(spec.get("yield", {}).get(region, spec.get("yield", {}).get("*", 0.0)))
            workers = sum(int(masses.get(f"job:{j}", 0)) + notables.count(j) for j in spec.get("by", []))
            due = workers * rate * years + float(carry.get(m, 0.0))
            n = int(due)  # (whole units; the fraction carries to next year, so fine and coarse agree)
            carry[m] = round(due - n, 6)
            if n > 0:
                made[m] = n
        carry = {m: v for m, v in sorted(carry.items()) if v}
        if not made:
            if carry != (ctx.get(s, "yield_carry") or {}):
                ctx.emit("goods.yield", {"settlement": (s,)}, purpose="yield", actor=s, place=s, payload={"produced": {}})
                ctx.set(s, "yield_carry", carry)
            return
        ctx.emit("goods.yield", {"settlement": (s,)}, purpose="yield", actor=s, place=s, payload={"produced": made})
        ctx.set(s, "yield_carry", carry)
        now = ctx.read_columns(s, [c for m in made for c in (f"stock:{m}", f"goods:{m}:produced")])
        ctx.write_columns(s, {**{f"stock:{m}": int(now[f"stock:{m}"]) + n for m, n in made.items()},
                              **{f"goods:{m}:produced": int(now[f"goods:{m}:produced"]) + n for m, n in made.items()}})

    def make(self, ctx, s, cat, years) -> None:
        jobs, types = cat.get("jobs") or {}, cat.get("types") or {}
        rate = float(cat.get("master_rate", MASTER_RATE))
        makers = [p for p in ctx.get(s, "residents") if not ctx.get(p, "journey")
                  and (jobs.get(ctx.get(p, "job")) or {}).get("makes")]
        makers.sort(key=lambda p: (-float((ctx.get(p, "skills") or {}).get(ctx.get(p, "job"), 0.0)), p))
        for p in makers:
            job = ctx.get(p, "job")
            skill = float((ctx.get(p, "skills") or {}).get(job, 0.0))
            for t in jobs[job]["makes"]:
                spec = types.get(t)
                if spec is None:
                    continue
                m, cost = spec["material"], int(spec["cost"])
                if int(ctx.read_columns(s, [f"stock:{m}"])[f"stock:{m}"]) < cost:
                    continue
                if ctx.chance(over(min(1.0, skill ** 3 * rate), years), "act:craft", owner=p):
                    self.masterwork(ctx, s, p, t, spec, skill, cat)
                    return  # (one a town a year)
                break  # (one try a maker a year: their first type with material to hand)

    def masterwork(self, ctx, s, maker, t, spec, skill, cat) -> None:
        m, cost = spec["material"], int(spec["cost"])
        quality = round(min(1.0, max(0.01, skill)), 3)
        fields = {"name": None, "type": t, "material": m, "maker": maker, "made": [ctx.today.to_json(), s],
                  "quality": quality, "owner": None, "place": s, "deeds": [], "fame": 0.0, "lost": None}
        ev = ctx.emit("object.made", {"maker": (maker,)}, purpose=f"made:{t}", actor=maker, place=s,
                      payload={"type": t, "material": m, "quality": quality}, creates={"object": [("object", fields)]})
        obj = ev.roles["object"][0]
        now = ctx.read_columns(s, [f"stock:{m}", f"goods:{m}:used"])
        ctx.write_columns(s, {f"stock:{m}": int(now[f"stock:{m}"]) - cost, f"goods:{m}:used": int(now[f"goods:{m}:used"]) + cost})
        self.first_owner(ctx, s, maker, obj, m, cost, quality, cat, ev.id)

    def first_owner(self, ctx, s, maker, obj, material, cost, quality, cat, cause) -> None:
        grown = [p for p in sorted(ctx.get(s, "residents"))
                 if age_years(ctx.calendar, ctx.get(p, "born"), ctx.today) >= ADULT and not ctx.get(p, "journey")]
        tied = set()
        for t in ctx.get(maker, "ties") or []:
            if ctx.get(t, "kind") in FRIENDLY:
                tied |= {ctx.get(t, "a"), ctx.get(t, "b")}
        weights = [round(1.0 + float(ctx.get(p, "wealth") or 0.0) / 10.0 + (TIE if p in tied and p != maker else 0.0), 6)
                   for p in grown]
        owner = ctx.choose("owner", grown, owner=obj, weights=weights) if grown else maker
        value = float((cat.get("materials") or {}).get(material, {}).get("value", 1))
        asked = 0.0 if owner == maker else round(cost * (1.0 + quality) * value, 2)
        price = round(min(asked, float(ctx.get(owner, "wealth") or 0.0)), 2)  # (what they can pay, no more)
        ctx.emit("object.given", {"giver": (maker,) if owner != maker else (), "owner": (owner,), "object": (obj,)},
                 purpose="given", actor=obj, place=s, payload={"price": price}, causes=(Cause("event", cause),))
        ctx.set(obj, "owner", owner)
        ctx.set(owner, "possessions", sorted((ctx.get(owner, "possessions") or []) + [obj]))
        if price:
            ctx.set(owner, "wealth", round(float(ctx.get(owner, "wealth") or 0.0) - price, 2))
            ctx.set(maker, "wealth", round(float(ctx.get(maker, "wealth") or 0.0) + price, 2))
