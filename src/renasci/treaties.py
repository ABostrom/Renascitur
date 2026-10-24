"""Treaties between polities, and how a polity decides (S8 spec §3.3, §4; #121).

A `treaty` entity (`tr:<kind>:<a>|<b>:<signed: year.day>`, or `...:seeded`; a suffix if one is taken) has
`kind`, `a`, `b`, `signed`, `expires` (a date; none if it would outlast the age: it lasts the age),
`trust_at` (the relation's trust when it was signed), `event` (the signing), `ended` and `broken_by`; the
relation lists its live treaties. Kinds (`KINDS`, with their years):
- **truce:** no war while it lasts (war, #122, reads it, and only war breaks one);
- **alliance:** each joins the other's defensive wars (#122);
- **trade:** routes stay open, and trust grows a little each year it lasts.
(Vassalage comes with war's peace terms, #122; a dynastic marriage with S3's marriages, later.)

**The year** (each polity relation, in `polity.diplomacy` before drift, so what its treaties do lands in
this year's ledger, reading last year's stance and trust):
- **Expiry:** a treaty ends on its date (`polity.treaty_ended`).
- **Betrayal:** an alliance or a trade pact **sours** once trust has fallen `SOUR` below what it was at
  signing, and below zero; then either side may break it, its ruler deciding: `polity.treaty_broken`, a
  heavy entry in the relation's ledger.
- **Proposals:** between friends, trade; between allies, an alliance; between enemies, a truce. A keyed
  draw picks which side proposes; the proposer's **government decides** (`decide`), then the other side's:
  - `ruler`: the ruler alone, by the odds;
  - `advised`: the member houses' heads advise first (a `polity.council` event: who urged yes, who no),
    and the advice, weighed by the advisers' standing, moves the ruler's odds;
  - `council`: the heads vote, each by their standing, and the majority binds.

  A polity without a ruler in office decides nothing; a council with no heads, its ruler alone. Every draw
  and event is keyed by the relation, so one relation's year never shifts another's.
"""

from __future__ import annotations

from renasci.core.calendar import AgeBoundaryError, Date, Span
from renasci.core.events import Cause, EventType
from renasci.people.houses import _heads, standing

KINDS = {"truce": 10, "alliance": 15, "trade": 20}
PROPOSE = {"trade": ("friendly", "allied"), "alliance": ("allied",), "truce": ("hostile",)}
ODDS = {"trade": 0.3, "alliance": 0.2, "truce": 0.15}  # (a year, that a proposal is made)
SOUR = 0.4  # (how far below its signing trust a pact's relation must fall to sour it)
BREAK = 0.3  # (a year, times how sour: -1 trust breaks a soured pact 30% of the time)

TREATY = EventType("polity.treaty", 1, roles={"party": (2, 2)},
                   payload={"treaty": "str", "kind": "str", "expires": "json"})  # (str: it names the treaty it makes)
ENDED = EventType("polity.treaty_ended", 1, roles={"party": (2, 2)}, payload={"treaty": "id", "kind": "str"})
BROKEN = EventType("polity.treaty_broken", 1, roles={"by": (1, 1), "party": (2, 2)}, payload={"treaty": "id", "kind": "str"})
COUNCIL = EventType("polity.council", 1, roles={"adviser": (1, 1000)},
                    payload={"polity": "id", "motion": "str", "yes": "ids", "no": "ids", "binding": "bool"})
EVENT_TYPES = (TREATY, ENDED, BROKEN, COUNCIL)
READS = frozenset({"ids:treaty", "treaties", "expires", "ended", "broken_by", "government", "ruler", "holder",
                   "members", "headship", "status", "house", "rank", "favour", "a", "b", "trust_at", "event", "kind"})
WRITES = frozenset({"treaties", "new:treaty", "ended", "broken_by"})


def ruler(ctx, polity: str) -> str | None:
    """Who rules `polity` now (None: no one in office, or the polity has fallen)."""
    if ctx.get(polity, "ended") is not None:
        return None
    office = ctx.get(polity, "ruler")
    holder = ctx.get(office, "holder") if office else None
    return holder if holder and ctx.status(holder) == "active" else None


def decide(ctx, polity: str, motion: str, p: float, rid: str) -> tuple[bool, tuple]:
    """Whether `polity` agrees to `motion` (base odds `p`) in relation `rid`, as its government decides:
    (yes, the council's event as the cause, if it sat)."""
    who = ruler(ctx, polity)
    if who is None:
        return False, ()
    government = ctx.get(polity, "government") or "ruler"
    heads = _heads(ctx, polity) if government != "ruler" else []
    if not heads:  # (a ruler alone; or a council with nobody in it: the ruler, then)
        return ctx.chance(p, f"decide:{motion}:{rid}", owner=who), ()
    yes = [h for h in heads if ctx.chance(p, f"advise:{motion}:{rid}", owner=h)]
    no = [h for h in heads if h not in yes]
    ev = ctx.emit("polity.council", {"adviser": tuple(heads)}, purpose=f"council:{polity}:{motion}", actor=rid,
                  payload={"polity": polity, "motion": motion, "yes": yes, "no": no, "binding": government == "council"})
    because = (Cause("event", ev.id),)
    weigh = lambda side: sum(standing(ctx, h) for h in side)  # noqa: E731
    if government == "council":
        return weigh(yes) > weigh(no), because
    share = weigh(yes) / weigh(heads)  # (advice, weighed by the advisers' standing)
    return ctx.chance(max(0.0, min(1.0, p + 0.3 * (share - 0.5))), f"decide:{motion}:{rid}", owner=who), because


def _expires(calendar, today: Date, years: int):
    """The date a treaty ends; None if that's past the age's end (it lasts the age)."""
    try:
        return calendar.add(today, Span(years=years)).to_json()
    except AgeBoundaryError:
        return None


def tid(kind: str, a: str, b: str, when: str, taken=lambda i: False) -> str:
    x, y = sorted((a, b))
    base = f"tr:{kind}:{x}|{y}:{when}"
    ident, n = base, 2
    while taken(ident):
        ident, n = f"{base}:{n}", n + 1
    return ident


def sign(ctx, rid: str, kind: str, a: str, b: str, trust: float, causes=()) -> str:
    """A treaty signed today: its event's id."""
    ident = tid(kind, a, b, f"{ctx.today.year}.{ctx.today.day}", ctx.exists)
    expires = _expires(ctx.calendar, ctx.today, KINDS[kind])
    ev = ctx.emit("polity.treaty", {"party": (a, b)}, purpose=f"treaty:{kind}", actor=rid,
                  payload={"treaty": ident, "kind": kind, "expires": expires}, causes=causes)
    ctx.create("treaty", ident, {"kind": kind, "a": min(a, b), "b": max(a, b), "signed": ctx.today.to_json(),
                                 "expires": expires, "trust_at": float(trust), "event": ev.id, "ended": None,
                                 "broken_by": None})
    ctx.set(rid, "treaties", sorted((ctx.get(rid, "treaties") or []) + [ident]))
    return ev.id


def _end(ctx, rid: str, treaty: str) -> None:
    ctx.set(treaty, "ended", ctx.today.to_json())
    ctx.set(rid, "treaties", [t for t in ctx.get(rid, "treaties") or [] if t != treaty])


def year(ctx, rid: str, a: str, b: str, stance: str, trust: float, years: int = 1) -> list[dict]:
    """A polity relation's treaty year (or a coarse step of `years`: each draw for that many years at once):
    expiries, betrayals, proposals. Returns ledger entries to add (a pact's is a recurring pull)."""
    from renasci.relations import over

    entries = []
    for t in list(ctx.get(rid, "treaties") or []):
        exp, kind = ctx.get(t, "expires"), ctx.get(t, "kind")
        if exp is not None and Date.from_json(exp) <= ctx.today:
            ctx.emit("polity.treaty_ended", {"party": (a, b)}, purpose=f"ended:{t}", actor=rid,
                     payload={"treaty": t, "kind": kind})
            _end(ctx, rid, t)
            continue
        soured = kind != "truce" and trust < 0 and trust < float(ctx.get(t, "trust_at") or 0.0) - SOUR
        if soured:  # (either side may break it, its ruler deciding)
            for side in sorted((a, b)):
                who = ruler(ctx, side)
                if who and ctx.chance(over(min(1.0, BREAK * -trust), years), f"break:{t}", owner=who):
                    ev = ctx.emit("polity.treaty_broken", {"by": (side,), "party": (a, b)}, purpose=f"broken:{t}",
                                  actor=rid, payload={"treaty": t, "kind": kind})
                    ctx.set(t, "broken_by", side)
                    _end(ctx, rid, t)
                    entries.append({"kind": "betrayal", "event": ev.id})
                    break
        elif kind == "trade":  # (a pact that holds: a little more trust each year, its signing the cause)
            entries.append({"kind": "pact", "event": ctx.get(t, "event"), "recurring": True})
    kinds_held = {ctx.get(t, "kind") for t in ctx.get(rid, "treaties") or []}
    for kind, stances in PROPOSE.items():
        if stance not in stances or kind in kinds_held or not ctx.chance(over(ODDS[kind], years), f"propose:{kind}",
                                                                          owner=rid):
            continue
        first = ctx.choose(f"proposer:{kind}", [a, b], owner=rid)
        other = b if first == a else a
        p = max(0.05, min(0.95, 0.5 + trust)) if kind != "truce" else max(0.05, min(0.95, 0.3 - trust / 2))
        ok, why = decide(ctx, first, kind, p, rid)
        if not ok:
            continue
        ok2, why2 = decide(ctx, other, kind, p, rid)
        if ok2:
            entries.append({"kind": "treaty", "event": sign(ctx, rid, kind, a, b, trust, causes=why + why2)})
    return entries


def check(sc: dict) -> list[dict]:
    from renasci.polities import _f

    out = []
    pols = {p["id"] for p in sc.get("polities") or [] if isinstance(p, dict)}
    seen = set()
    for t in sc.get("treaties") or []:
        if not isinstance(t, dict) or t.get("kind") not in KINDS or not isinstance(t.get("a"), str) \
                or not isinstance(t.get("b"), str) or t["a"] not in pols or t["b"] not in pols or t["a"] == t["b"]:
            out.append(_f("bad_treaty", None, f"a treaty is {{kind: {'/'.join(KINDS)}, a, b: two polities, years?}}: {t!r}"))
            continue
        key = (t["kind"], frozenset((t["a"], t["b"])))
        if key in seen:
            out.append(_f("bad_treaty", t["a"], f"{t['a']} and {t['b']} have two {t['kind']} treaties"))
        seen.add(key)
        y = t.get("years", KINDS[t["kind"]])
        if isinstance(y, bool) or not isinstance(y, int) or y < 1:
            out.append(_f("bad_treaty", t["a"], f"a treaty's years must be a positive whole number, not {y!r}"))
    return out


SIGNED_AT = {"alliance": 0.75, "trade": 0.4, "truce": -0.75}  # (an old pact was signed in better days: its kind's)


def cast(engine, sc: dict, today) -> dict[str, list[str]]:
    """The scenario's treaties as entities: {relation id: [treaty ids]}. An old pact's trust at signing is
    its kind's usual (`SIGNED_AT`), whatever the relation has come to since."""
    from renasci.relations import rel_id

    out: dict[str, list[str]] = {}
    for t in sc.get("treaties") or []:
        ident = tid(t["kind"], t["a"], t["b"], "seeded")
        rid = rel_id(t["a"], t["b"])
        engine.cast("treaty", ident, {"kind": t["kind"], "a": min(t["a"], t["b"]), "b": max(t["a"], t["b"]),
                                      "signed": today.to_json(), "trust_at": SIGNED_AT[t["kind"]], "event": None,
                                      "expires": _expires(engine.calendar, today, t.get("years", KINDS[t["kind"]])),
                                      "ended": None, "broken_by": None})
        out.setdefault(rid, []).append(ident)
    return out
