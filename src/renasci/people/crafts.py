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

4. **Biographies** (S9 §5, #126), each object in its own scope:
   - an owner gone (dead): it passes to their heir (the eldest living child, else the spouse:
     `object.inherited`), unless they fell far from home (`life.die` notes `fell`: on a journey, in battle, a
     sack, a duel), where it may be lost (`lose_rate`); with no heir, it is lost where they fell
     (`object.lost`);
   - a lost object may be found by someone living where it lies (`find_rate`, likelier the more famous it is:
     `object.found`);
   - an owner's `exploits` (a duel won, a near miss survived: noted by S7 and `life.die`) become each of
     their objects' deeds (`object.deed`, `DEED_FAME` each); at `NAMED` fame a thing earns a name from where
     its last deed was done (`object.named`: "the Blade of Redcairn").
   Owners of objects are kept as notables (S3's LOD spares them).

This system is the spec's `objects` system: the only writer of an object's fields. A coarse step yields N years
and draws "a masterwork in N years" and "found in N years".
"""

from __future__ import annotations

from renasci.core.events import Cause, EventType
from renasci.core.systems import System
from renasci.people import beliefs
from renasci.people.races import age_years
from renasci.relations import over

FLOWS = ("initial", "produced", "used", "traded_in", "traded_out", "destroyed")
MASTER_RATE = 0.05
LOSE_RATE, FIND_RATE = 0.5, 0.05  # (an owner fallen far from home loses it there; a year's chance it's found)
DEED_FAME, NAMED = 0.25, 0.5  # (fame a deed brings; the fame at which a thing earns a name)
ADULT = 16
TIE = 4.0  # (a friend of the maker is likelier to get it)

YIELD = EventType("goods.yield", 1, roles={"settlement": (1, 1)}, payload={"produced": "json"})
MADE = EventType("object.made", 1, roles={"maker": (1, 1), "object": (1, 1)},
                 payload={"type": "str", "material": "str", "quality": "float"})
GIVEN = EventType("object.given", 1, roles={"giver": (0, 1), "owner": (1, 1), "object": (1, 1)},
                  payload={"price": "float"})
INHERITED = EventType("object.inherited", 1, roles={"from": (1, 1), "owner": (1, 1), "object": (1, 1)}, payload={},
                      dead_roles=("from",))
LOST = EventType("object.lost", 1, roles={"owner": (1, 1), "object": (1, 1)}, payload={"place": "id"},
                 dead_roles=("owner",))
FOUND = EventType("object.found", 1, roles={"finder": (1, 1), "object": (1, 1)}, payload={"place": "id"})
DEED = EventType("object.deed", 1, roles={"owner": (1, 1), "object": (1, 1)}, payload={"deed": "str", "kind": "str"})
NAMED_T = EventType("object.named", 1, roles={"object": (1, 1)}, payload={"name": "str"})
STOLEN = EventType("object.stolen", 1, roles={"thief": (1, 1), "from": (1, 1), "object": (1, 1)}, payload={})
DESTROYED = EventType("object.destroyed", 1, roles={"object": (1, 1)}, payload={"place": "json"})
UNEARTHED = EventType("object.unearthed", 1, roles={"finder": (1, 1), "object": (1, 1)}, payload={"place": "id"})
EVENT_TYPES = (YIELD, MADE, GIVEN, INHERITED, LOST, FOUND, DEED, NAMED_T, STOLEN, DESTROYED, UNEARTHED) \
    + beliefs.EVENT_TYPES
READS = frozenset({"ids:settlement", "residents", "region", "born", "job", "skills", "wealth", "ties", "a", "b",
                   "kind", "journey", "possessions", "yield_carry", "stock:*", "goods:*", "job:*",
                   "ids:object", "owner", "status", "fell", "children", "spouse", "place", "lost", "fame", "deeds",
                   "exploits", "name", "type"}) | beliefs.PERCEIVE_READS
WRITES = frozenset({"stock:*", "goods:*", "new:object", "owner", "wealth", "possessions", "yield_carry",
                    "place", "lost", "fame", "deeds", "exploits", "name", "status", "destroyed"}) \
    | beliefs.PERCEIVE_WRITES
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


def hand(ctx, o: str, frm: str | None, to: str | None) -> None:
    """An object moves from one holder to another (either may be None): their possessions follow. Only this
    module writes object fields; other systems call `take` and `destroy`."""
    if frm and ctx.exists(frm):
        ctx.set(frm, "possessions", [x for x in ctx.get(frm, "possessions") or [] if x != o])
    ctx.set(o, "owner", to)
    if to:
        ctx.set(to, "possessions", sorted((ctx.get(to, "possessions") or []) + [o]))
        ctx.set(o, "place", ctx.get(to, "place"))


def where(ctx, o: str) -> str | None:
    """Where an object is: with its owner, or where it lies."""
    owner = ctx.get(o, "owner")
    return ctx.get(owner, "place") if owner else ctx.get(o, "place")


def seen(ctx, event: str, place: str | None, participants, claim: dict, secret: bool = False) -> None:
    """Those in an object's event (and a town's bystanders) take its claim on (S6; only with beliefs)."""
    if beliefs.enabled(ctx):
        beliefs.perceive(ctx, event, place, [p for p in participants if p], claim, secret=secret)


def take(ctx, o: str, thief: str, cause: str | None) -> None:
    """A theft succeeded (S7's Steal): the object is the thief's. Only the thief knows: the town still believes
    the old owner has it."""
    frm = ctx.get(o, "owner")
    ev = ctx.emit("object.stolen", {"thief": (thief,), "from": (frm,), "object": (o,)}, purpose="stolen", actor=o,
                  place=ctx.get(o, "place"), causes=(Cause("event", cause),) if cause else (), visibility="secret")
    hand(ctx, o, frm, thief)
    seen(ctx, ev.id, None, [thief], beliefs.claim("owns", object=o, by=thief), secret=True)


def unearth(ctx, town: str, spec: dict, ripple: str) -> bool:
    """A planted object turns up in `town` (S1's plant ripple, S9 #126), found by someone living there."""
    grown = [p for p in sorted(ctx.get(town, "residents"))
             if age_years(ctx.calendar, ctx.get(p, "born"), ctx.today) >= ADULT and not ctx.get(p, "journey")]
    if not grown:
        return False
    finder = ctx.choose("finder", grown, owner=ripple)
    fields = {"name": spec.get("name"), "type": spec["type"], "material": spec["material"], "maker": None,
              "made": None, "quality": float(spec.get("quality", 0.5)), "owner": None, "place": town, "deeds": [],
              "fame": float(spec.get("fame", 0.0)), "lost": None}
    ev = ctx.emit("object.unearthed", {"finder": (finder,)}, purpose="unearthed", actor=town, place=town,
                  payload={"place": town}, creates={"object": [("object", fields)]})
    o = ev.roles["object"][0]
    hand(ctx, o, None, finder)
    seen(ctx, ev.id, town, [finder], beliefs.claim("owns", object=o, by=finder))
    return True


def destroy(ctx, o: str, place: str | None, cause: str | None) -> None:
    """An object is destroyed (a sack): gone for good (store status `dead`, `destroyed` its date)."""
    ctx.emit("object.destroyed", {"object": (o,)}, purpose="destroyed", actor=o, place=place,
             payload={"place": place}, causes=(Cause("event", cause),) if cause else ())
    hand(ctx, o, ctx.get(o, "owner"), None)
    ctx.set(o, "destroyed", ctx.today.to_json())
    ctx.set_status(o, "dead")


def place_name(ctx, place: str | None) -> str:
    """A place's name; without one, its id made readable ("v:raining-bay" -> "Raining Bay")."""
    if not place:
        return "nowhere"
    name = ctx.get(place, "name") if ctx.exists(place) else None
    return name or place.split(":", 1)[-1].replace("-", " ").title()


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
        self.biographies(ctx, cat, years)

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
        seen(ctx, ev.id, s, [maker], beliefs.claim("made", object=obj, by=maker))  # (after the making's own writes)
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
        given = ctx.emit("object.given", {"giver": (maker,) if owner != maker else (), "owner": (owner,), "object": (obj,)},
                         purpose="given", actor=obj, place=s, payload={"price": price}, causes=(Cause("event", cause),))
        ctx.set(obj, "owner", owner)
        ctx.set(owner, "possessions", sorted((ctx.get(owner, "possessions") or []) + [obj]))
        if price:
            ctx.set(owner, "wealth", round(float(ctx.get(owner, "wealth") or 0.0) - price, 2))
            ctx.set(maker, "wealth", round(float(ctx.get(maker, "wealth") or 0.0) + price, 2))
        seen(ctx, given.id, s, [owner, maker], beliefs.claim("owns", object=obj, by=owner))

    # ------------------------------------------------------------ biographies (S9 §5, #126)

    def biographies(self, ctx, cat, years) -> None:
        """What became of each object this year: an owner gone, a lost thing found, deeds done."""
        lose = float(cat.get("lose_rate", LOSE_RATE))
        find = float(cat.get("find_rate", FIND_RATE))
        owners = sorted({ctx.get(o, "owner") for o in ctx.ids("object")} - {None})
        for p in owners:  # (deeds first: one who did great things and then fell still gave them to what they bore)
            if ctx.get(p, "exploits"):
                with ctx.scope(p):
                    self.deeds(ctx, p)
        for o in ctx.ids("object"):
            if ctx.status(o) != "active":
                continue  # (destroyed)
            with ctx.scope(o):
                owner = ctx.get(o, "owner")
                if owner and ctx.status(owner) != "active":
                    self.bequeath(ctx, o, owner, lose)
                elif owner is None and ctx.get(o, "lost") is not None:
                    self.find(ctx, o, find, years)

    def _hand(self, ctx, o, frm, to) -> None:
        hand(ctx, o, frm, to)

    def bequeath(self, ctx, o, owner, lose) -> None:
        fell = ctx.get(owner, "fell") or {}
        where = fell.get("place") or ctx.get(o, "place")
        heir = next((c for c in [*(ctx.get(owner, "children") or []), ctx.get(owner, "spouse")]
                     if c and ctx.exists(c) and ctx.status(c) == "active"), None)
        if heir is None or (fell.get("away") and ctx.chance(lose, "lose", owner=o)):
            ev = ctx.emit("object.lost", {"owner": (owner,), "object": (o,)}, purpose="lost", actor=o, place=where,
                          payload={"place": where},
                          causes=(Cause("event", fell["event"]),) if fell.get("event") else ())
            self._hand(ctx, o, owner, None)
            ctx.set(o, "place", where)
            ctx.set(o, "lost", ctx.today.to_json())
            return
        ev = ctx.emit("object.inherited", {"from": (owner,), "owner": (heir,), "object": (o,)}, purpose="inherited",
                      actor=o, place=ctx.get(heir, "place"),
                      causes=(Cause("event", fell["event"]),) if fell.get("event") else ())
        self._hand(ctx, o, owner, heir)
        seen(ctx, ev.id, ctx.get(heir, "place"), [heir], beliefs.claim("owns", object=o, by=heir))

    def find(self, ctx, o, rate, years) -> None:
        place = ctx.get(o, "place")
        if not place or ctx.kind(place) != "settlement":
            return
        here = [p for p in sorted(ctx.get(place, "residents") or [])
                if age_years(ctx.calendar, ctx.get(p, "born"), ctx.today) >= ADULT and not ctx.get(p, "journey")]
        p = min(1.0, rate * (1.0 + 3.0 * float(ctx.get(o, "fame") or 0.0)))
        if not here or not ctx.chance(over(p, years), "find", owner=o):
            return
        finder = ctx.choose("finder", here, owner=o)
        ev = ctx.emit("object.found", {"finder": (finder,), "object": (o,)}, purpose="found", actor=o, place=place,
                      payload={"place": place})
        self._hand(ctx, o, None, finder)
        ctx.set(o, "lost", None)
        seen(ctx, ev.id, place, [finder], beliefs.claim("owns", object=o, by=finder))

    def deeds(self, ctx, person) -> None:
        exploits = list(ctx.get(person, "exploits") or [])
        for o in sorted(ctx.get(person, "possessions") or []):
            mine = [x for x in exploits if o in x.get("held", [])]  # (only what they bore when they did it)
            if not mine:
                continue
            fame = float(ctx.get(o, "fame") or 0.0)
            deeds = list(ctx.get(o, "deeds") or [])
            for x in mine:
                ctx.emit("object.deed", {"owner": (person,), "object": (o,)}, purpose=f"deed:{x['event']}", actor=o,
                         place=x.get("place"), payload={"deed": x["event"], "kind": x["kind"]},
                         causes=(Cause("event", x["event"]),))
                deeds.append(x["event"])
                fame = round(min(1.0, fame + DEED_FAME), 3)
            ctx.set(o, "deeds", deeds)
            ctx.set(o, "fame", fame)
            if fame >= NAMED and not ctx.get(o, "name"):
                at = mine[-1].get("place") or ctx.get(person, "place")
                name = f"the {str(ctx.get(o, 'type')).title()} of {place_name(ctx, at)}"
                ctx.emit("object.named", {"object": (o,)}, purpose="named", actor=o, place=at, payload={"name": name})
                ctx.set(o, "name", name)
        ctx.set(person, "exploits", [])
