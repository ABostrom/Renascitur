"""Relations between polities, and between factions inside one (S8 spec §4, #121): stance, trust and a
ledger of what happened between them.

A `relation` entity (`rel:<a>|<b>`, the pair sorted) has `a`, `b`, `kind` (polity or faction), `stance`
(war, hostile, cold, neutral, friendly, allied), `trust` (−1…1), `treaties` and a `ledger`. Relations are
**sparse**: cast for polities that share a border and for a polity's factions, or a scenario's
`relations` (a starting stance and trust: old rivalries), and made on first contact.

**The ledger:** systems append what happens across the line with `across(ctx, x, y, kind, event)` (x and
y people: their polities, and their factions if they share a polity), each entry weighted by `WEIGHTS`:
- `people.life`'s killer branch: a killing ("killed");
- `people.schemes`' exposure: a plot laid bare ("exposed");
- `people.marriage`: a match between their houses ("marriage");
- border incidents (below).

Only worlds with polities do any of this, so other runs are untouched.

**Drift** (`polity.diplomacy`, yearly, each relation in its own scope): trust fades a little, then moves by
the ledger, by the trade along open border routes between two polities (at neutral or better: enemies
don't trade, they raid), and by enemies they share; the
ledger is cleared (a `polity.drift` event, caused by what was in it), and the stance follows trust
(`STANCES`); a change of stance is an event. War is set
by war, never by drift. **Border incidents:** each border route between cold or hostile polities may
see one a year (a raid, a skirmish): an event, and a ledger entry.
"""

from __future__ import annotations

from renasci.core.events import Cause, EventType
from renasci.core.systems import System

WEIGHTS = {"killed": -0.15, "exposed": -0.1, "marriage": 0.12, "incident": -0.1, "betrayal": -0.5, "treaty": 0.1,
           "pact": 0.015, "war": -0.12, "raid": -0.15}  # (pact: a trade treaty that holds, each year; with trade it settles under friendly)
STANCES = ((0.6, "allied"), (0.25, "friendly"), (-0.25, "neutral"), (-0.55, "cold"))  # else hostile
FADE = 0.9  # (trust a year on, before what happened that year)
TRADE = 0.012  # per open border route, up to TRADE_CAP a year: trade alone settles at neutral (10 x the cap, under
TRADE_CAP = 0.02  # friendly's 0.25); friendship and alliance are earned (marriages, treaties)
SHARED_ENEMY = 0.05
INCIDENT = {"cold": 0.08, "hostile": 0.25}  # per border route, a year (none at war: war has battles)
BAND = 0.05  # (hysteresis: a stance moves only when trust is this far past its threshold)
SETTLED = 0.005  # (a quiet year that moves trust less than this changes nothing: no drift event)
SEEDED = {"allied": 0.75, "friendly": 0.4, "neutral": 0.0, "cold": -0.4, "hostile": -0.75, "war": -0.9}

DRIFT = EventType("polity.drift", 1, roles={"party": (2, 2)}, payload={"relation": "id", "trust": "float", "moved": "float"})
STANCE = EventType("polity.stance", 1, roles={"party": (2, 2)}, payload={"relation": "id", "from": "str", "to": "str"})
INCIDENT_T = EventType("polity.incident", 1, roles={"party": (2, 2)}, payload={"relation": "id", "route": "id"})
EVENT_TYPES = (DRIFT, STANCE, INCIDENT_T)

NOTE_READS = frozenset({"ids:polity", "ids:faction", "members", "house", "place", "control", "polity", "ledger"})
NOTE_WRITES = frozenset({"ledger", "new:relation"})


def over(p: float, years: int) -> float:
    """The odds of at least one in `years` independent years at `p` a year (a coarse step's draw, S8 §7);
    exactly `p` for one year, so a fine year draws as it always did."""
    return p if years == 1 else 1.0 - (1.0 - p) ** years


def rel_id(a: str, b: str) -> str:
    x, y = sorted((a, b))
    return f"rel:{x}|{y}"


def stance_of(trust: float, current: str | None = None) -> str:
    """The stance for a trust; with `current`, only once trust is BAND past the threshold between them."""
    def plain(t):
        for floor, name in STANCES:
            if t >= floor:
                return name
        return "hostile"
    to = plain(trust)
    if current is None or current == to or current == "war":
        return to
    order = ["hostile", "cold", "neutral", "friendly", "allied"]
    if current not in order:
        return to
    up = order.index(to) > order.index(current)
    return to if plain(trust - BAND if up else trust + BAND) != current else current


def fields(a: str, b: str, kind: str, today, stance: str = "neutral", trust: float = 0.0) -> dict:
    x, y = sorted((a, b))
    return {"a": x, "b": y, "kind": kind, "stance": stance, "trust": float(trust), "treaties": [], "ledger": [],
            "since": today.to_json()}


def allegiance(ctx, person: str, houses_only: bool = False) -> tuple[str | None, list[str]]:
    """(the polity a person belongs to: their house's, else (unless `houses_only`) whoever holds where they
    live; their house's factions)."""
    house = ctx.get(person, "house")
    polity = None
    for p in ctx.ids("polity"):
        if house and house in (ctx.get(p, "members") or []):
            polity = p
            break
    if polity is None and not houses_only:
        place = ctx.get(person, "place")
        polity = ctx.get(place, "control") if place else None
    factions = [f for f in ctx.ids("faction") if house and house in (ctx.get(f, "members") or [])]
    return polity, factions


def note(ctx, a: str, b: str, kind: str, event: str, kind_of: str = "polity") -> None:
    """Something happened between `a` and `b` (polities, or factions): a ledger entry, the relation made if
    they had none."""
    if not a or not b or a == b:
        return
    rid = rel_id(a, b)
    if not ctx.exists(rid):
        ctx.create("relation", rid, fields(a, b, kind_of, ctx.today))
    ledger = list(ctx.get(rid, "ledger") or [])
    ledger.append({"kind": kind, "weight": WEIGHTS[kind], "event": event, "date": ctx.today.to_json()})
    ctx.set(rid, "ledger", ledger)


def across(ctx, x: str, y: str, kind: str, event: str) -> None:
    """Note what `x` did to `y` (or between them) for their polities and, inside one polity, their factions.
    A marriage counts only between great houses (both spouses of a member house), not commoners abroad.
    A world without polities: nothing (and nothing read but the polity ids)."""
    if not ctx.ids("polity") or not x or not y:
        return
    houses = kind == "marriage"
    (px, fx), (py, fy) = allegiance(ctx, x, houses), allegiance(ctx, y, houses)
    if px and py and px != py:
        note(ctx, px, py, kind, event)
    elif px and px == py:
        for f in fx:
            for g in fy:
                if f not in fy and g not in fx:  # (not their shared factions)
                    note(ctx, f, g, kind, event, "faction")


def cast(engine, sc: dict, today) -> None:
    """The relations a world starts with: polities that share a border, a polity's factions, and the
    scenario's `relations` (a starting stance and trust)."""
    from renasci.polities import borders, control_of

    made: dict[str, dict] = {}
    g = sc.get("geography") if isinstance(sc.get("geography"), dict) else {}
    for r in borders(g.get("routes", []), control_of(sc)):
        a, b = control_of(sc)[r["ends"][0]], control_of(sc)[r["ends"][1]]
        made.setdefault(rel_id(a, b), fields(a, b, "polity", today))
    by_polity: dict[str, list[str]] = {}
    for f in sc.get("factions") or []:
        by_polity.setdefault(f["polity"], []).append(f["id"])
    for fs in by_polity.values():
        for i, f in enumerate(sorted(fs)):
            for h in sorted(fs)[i + 1:]:
                made.setdefault(rel_id(f, h), fields(f, h, "faction", today))
    from renasci import treaties

    pacts = treaties.cast(engine, sc, today)
    kinds = {p["id"]: "polity" for p in sc.get("polities") or []} | {f["id"]: "faction" for f in sc.get("factions") or []}
    for r in sc.get("relations") or []:  # (a stance without a trust brings its own; with one, they agree)
        trust = float(r["trust"]) if "trust" in r else SEEDED[r.get("stance") or "neutral"]
        made[rel_id(r["a"], r["b"])] = fields(r["a"], r["b"], kinds[r["a"]], today, r.get("stance") or stance_of(trust), trust)
    for rid, ids in sorted(pacts.items()):  # (a seeded treaty's parties are related, if nothing else made them)
        if rid not in made:
            a, b = rid[len("rel:"):].split("|")
            made[rid] = fields(a, b, "polity", today)
        made[rid]["treaties"] = sorted(ids)
    for rid, f in sorted(made.items()):
        engine.cast("relation", rid, f)


def check(sc: dict) -> list[dict]:
    """A scenario's `relations`: between two polities, or two factions of one polity."""
    from renasci.polities import _f

    out = []
    pols = {p["id"] for p in sc.get("polities") or [] if isinstance(p, dict)}
    facs = {f["id"]: f.get("polity") for f in sc.get("factions") or [] if isinstance(f, dict)}
    seen = set()
    for r in sc.get("relations") or []:
        if not isinstance(r, dict) or not isinstance(r.get("a"), str) or not isinstance(r.get("b"), str):
            out.append(_f("bad_relation", None, f"a relation is {{a, b, stance?, trust?}} (a, b ids), not {r!r}"))
            continue
        a, b = r.get("a"), r.get("b")
        if frozenset((a, b)) in seen:
            out.append(_f("bad_relation", a, f"{a} and {b} are related twice"))
        seen.add(frozenset((a, b)))
        if a == b or not ((a in pols and b in pols) or (a in facs and b in facs and facs[a] == facs[b])):
            out.append(_f("bad_relation", a, f"{a!r} and {b!r} must be two polities, or two factions of one polity"))
        t = r.get("trust", 0.0)
        if isinstance(t, bool) or not isinstance(t, (int, float)) or not -1 <= t <= 1:
            out.append(_f("bad_relation", a, f"trust must be in [-1, 1], not {t!r}"))
        if r.get("stance") not in (None, "war", "hostile", "cold", "neutral", "friendly", "allied"):
            out.append(_f("bad_relation", a, f"stance {r.get('stance')!r} isn't a stance"))
        elif r.get("stance") not in (None, "war") and "trust" in r and isinstance(t, (int, float)) \
                and stance_of(float(t)) != r["stance"]:
            out.append(_f("bad_relation", a, f"stance {r['stance']} and trust {t} disagree (that trust is "
                                             f"{stance_of(float(t))})"))
    return out


def _border_routes(ctx, a: str, b: str) -> list[str]:
    out = []
    for route in ctx.ids("route"):
        ends = ctx.get(route, "ends")
        held = {ctx.get(e, "control") for e in ends}
        if held == {a, b}:
            out.append(route)
    return out


class Diplomacy(System):
    """Relations drift a year at a time, and border incidents happen (see the module doc)."""

    name, cadence, priority = "polity.diplomacy", "yearly", 1  # (after people.houses: rulers settled)
    from renasci import lines as _l, treaties as _t

    reads = frozenset({"ids:relation", "ids:route", "a", "b", "kind", "stance", "trust", "ledger", "ends", "control",
                       "open"}) | _t.READS | _l.READS
    writes = frozenset({"stance", "trust", "ledger", "news"}) | _t.WRITES | _l.WRITES
    event_types = EVENT_TYPES + _t.EVENT_TYPES + _l.EVENT_TYPES  # (a broken treaty's lines, #158)
    del _l, _t

    def run(self, ctx):
        self.step(ctx, 1)

    def coarse_fallback(self, ctx, years: int) -> None:
        """A coarse step of `years` (S8 §7): incidents drawn for each of its years; proposals and betrayals
        compounded (`over`: at least one in that many years; a government decides once, so they come a
        little rarer than fine); trust fades `FADE**years` and takes the recurring pull (trade, pacts, shared
        enemies) summed geometrically, so a quiet coarse step lands where the fine years would. The stance,
        expiries and what drives trade and incidents are read once, at the step's start (a band crossed
        and recovered mid-step is lost; a treaty ends on the step's date, not its own)."""
        self.step(ctx, years)

    def step(self, ctx, years: int) -> None:
        if type(years) is not int or years < 1:
            raise ValueError(f"a step is a whole number of years, at least one; got {years!r}")
        rels = ctx.ids("relation")
        for rid in rels:
            with ctx.scope(rid):
                self.drift(ctx, rid, rels, years)

    def drift(self, ctx, rid: str, rels, years: int = 1) -> None:
        a, b, kind = ctx.get(rid, "a"), ctx.get(rid, "b"), ctx.get(rid, "kind")
        stance, trust = ctx.get(rid, "stance"), float(ctx.get(rid, "trust") or 0.0)
        ledger = list(ctx.get(rid, "ledger") or [])
        if kind == "polity":  # (treaties: expiries, betrayals, proposals; what they do goes in this year's ledger)
            from renasci import treaties

            for e in treaties.year(ctx, rid, a, b, stance, trust, years):
                ledger.append({"kind": e["kind"], "weight": WEIGHTS[e["kind"]], "event": e["event"],
                               "date": ctx.today.to_json(), **({"recurring": True} if e.get("recurring") else {})})
        routes = _border_routes(ctx, a, b) if kind == "polity" else []
        if stance in INCIDENT:
            for route in routes:
                if ctx.get(route, "open") is False:
                    continue
                for y in range(years):  # (a coarse step: a draw for each of its years)
                    tag = f"incident:{route}" + (f":{y}" if y else "")
                    if not ctx.chance(INCIDENT[stance], tag, owner=rid):
                        continue
                    side = ctx.choose(tag, list(ctx.get(route, "ends")), owner=rid)  # (either side)
                    ev = ctx.emit("polity.incident", {"party": (a, b)}, purpose=tag, actor=rid,
                                  place=side, payload={"relation": rid, "route": route})
                    ledger.append({"kind": "incident", "weight": WEIGHTS["incident"], "event": ev.id,
                                   "date": ctx.today.to_json()})
        stances = {}  # (an enemy of both: a third party both are hostile to, or at war with)
        for other in rels:
            if other != rid and ctx.get(other, "kind") == kind:
                stances[frozenset((ctx.get(other, "a"), ctx.get(other, "b")))] = ctx.get(other, "stance")
        hostile = ("hostile", "war")
        thirds = {p for pair in stances for p in pair} - {a, b}
        shared = sum(1 for c in sorted(thirds) if stances.get(frozenset((a, c))) in hostile
                     and stances.get(frozenset((b, c))) in hostile)
        trading = stance not in ("cold", "hostile", "war")  # (enemies don't trade: they raid)
        trade = min(TRADE_CAP, TRADE * sum(1 for r in routes if ctx.get(r, "open") is not False)) if trading else 0.0
        once = sum(e["weight"] for e in ledger if not e.get("recurring"))  # (what happened, once)
        yearly = sum(e["weight"] for e in ledger if e.get("recurring")) + SHARED_ENEMY * shared + trade  # (a year's pull)
        moved = once + yearly * (1 - FADE ** years) / (1 - FADE)  # (years=1: once + yearly)
        new = round(max(-1.0, min(1.0, trust * FADE ** years + moved)), 6)
        if not ledger and abs(new - trust) < SETTLED:
            return  # (a quiet year that hardly moves it: settled, no event)
        why = tuple(sorted({Cause("event", e["event"]) for e in ledger if e.get("event")}, key=lambda c: c.ref))
        drifted = ctx.emit("polity.drift", {"party": (a, b)}, purpose="drift", actor=rid,
                           payload={"relation": rid, "trust": new, "moved": round(moved, 6)}, causes=why)
        ctx.set(rid, "trust", new)
        ctx.set(rid, "news", drifted.id)  # (the relation's latest: what a war, say, is declared over)
        if ledger:
            ctx.set(rid, "ledger", [])
        to = stance if stance == "war" else stance_of(new, stance)
        if to != stance:
            ctx.emit("polity.stance", {"party": (a, b)}, purpose="stance", actor=rid,
                     payload={"relation": rid, "from": stance, "to": to}, causes=why)
            ctx.set(rid, "stance", to)
