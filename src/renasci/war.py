"""War, coarse (S8 spec §5, Part A of #122): enough for M5's civilisations; campaigns and battles are Part B.

**Declaring war** (`polity.war`, yearly, after diplomacy; each polity relation in its own scope): at
hostile stance, each side's ruler, in turn, may propose war, the likelier the lower the trust (`DECLARE`);
the government decides (`treaties.decide`). A live truce makes it rarer, and breaking it to go to war is
a betrayal (in the ledger). `polity.war_declared` (caused by the relation's latest news) makes a `war`
entity (`war:<a>|<b>:<year>`: `aggressor`, `defender`, `attackers`, `defenders`, `started`, `ended`,
`outcome`, `exhaustion`, `cause`) and sets the relation to war. **Allies** are called: each of the
defender's allies (a live alliance) decides whether to join (`polity.joined`: it's at war with every
attacker then); one who refuses breaks the alliance, a betrayal.

**A war's year** (each live war, in its own scope): one draw by strength (`strength`: the people of each
side's settlements), a `polity.war_year` event naming the winner and the loser:
- a border place of the loser's (one end of a route whose other end the winning side holds) changes hands
  through S4's dated-change machinery (`geo.apply_change`, `{place, control}`), so the map by year shows
  it. A seat is taken only when it is the last place on the front, and not while a pin guards its ruler
  (S8 §3.4);
- the loser's ruler may fall in battle (`life.die`; a guarded ruler survives, a near miss);
- exhaustion builds, more on the loser's side, and the war is in every cross-side relation's ledger.

**Peace:** a side exhausted (`EXHAUSTED`) sues for peace: `polity.peace`, a truce signed between the
aggressor and the defender, the war ended with the less exhausted side as the winner, and every
cross-side relation back to hostile. A polity left holding **no settlement falls** (`polity.fallen`): its
places go to the victor, its treaties end, and its wars too where it led a side (an ally just leaves).
A fallen polity has no ruler (`treaties.ruler`): it declares, decides and betrays nothing.
"""

from __future__ import annotations

from renasci import geo, treaties
from renasci.core.events import Cause, EventType
from renasci.core.systems import System
from renasci.people import houses, life
from renasci.relations import WEIGHTS, fields, rel_id

DECLARE = 0.12  # (a year, times how bitter: trust -1 is a 12% chance a ruler proposes war)
TRUCE_SHAME = 0.25  # (a truce makes declaring that much rarer)
JOIN = 0.7  # (an ally's odds of honouring the call)
FALL = 0.08  # (a year, that a loser's ruler falls in battle)
EXHAUSTED = 1.0
WON, LOST = 0.1, 0.25  # (exhaustion a year)

DECLARED = EventType("polity.war_declared", 1, roles={"aggressor": (1, 1), "defender": (1, 1)},
                     payload={"war": "str", "relation": "id"})
JOINED = EventType("polity.joined", 1, roles={"ally": (1, 1), "side": (1, 1)}, payload={"war": "id"})
YEAR = EventType("polity.war_year", 1, roles={"winner": (1, 1), "loser": (1, 1)}, payload={"war": "id", "place": "json"})
PEACE = EventType("polity.peace", 1, roles={"winner": (1, 1), "loser": (1, 1)}, payload={"war": "id"})
FALLEN = EventType("polity.fallen", 1, roles={"polity": (1, 1), "victor": (1, 1)}, payload={"war": "id"})
STANCE = EventType("polity.stance", 1, roles={"party": (2, 2)}, payload={"relation": "id", "from": "str", "to": "str"})
EVENT_TYPES = (DECLARED, JOINED, YEAR, PEACE, FALLEN, STANCE, geo.changed_type(), *treaties.EVENT_TYPES,
               *life.DIE_EVENTS)


def strength(ctx, polity: str) -> int:
    """A polity's might, coarsely: the people of the settlements it holds (and one for each settlement)."""
    return sum(1 + len(ctx.get(s, "residents") or []) for s in ctx.ids("settlement") if ctx.get(s, "control") == polity)


def _holds(ctx, polity: str, kinds=("settlement", "place")) -> list[str]:
    return [p for kind in kinds for p in ctx.ids(kind) if ctx.get(p, "control") == polity]


def _front(ctx, loser: str, winners: set) -> dict[str, str]:
    """The loser's border places, each with who holds the other end: {place: winner}."""
    out: dict[str, str] = {}
    for route in ctx.ids("route"):
        if ctx.get(route, "open") is False:
            continue
        x, y = ctx.get(route, "ends")
        for mine, theirs in ((x, y), (y, x)):
            held = ctx.get(theirs, "control")
            if ctx.get(mine, "control") == loser and held in winners:
                out.setdefault(mine, held)
    return dict(sorted(out.items()))


def _ledger(ctx, rid: str, kind: str, event: str) -> None:
    ledger = list(ctx.get(rid, "ledger") or [])
    ledger.append({"kind": kind, "weight": WEIGHTS[kind], "event": event, "date": ctx.today.to_json()})
    ctx.set(rid, "ledger", ledger)


def _set_stance(ctx, a: str, b: str, to: str, causes=()) -> None:
    """The pair's stance, now `to`. Two polities with no relation yet (an ally and an attacker who never met)
    get one at that stance, made by the event just emitted (the joining)."""
    rid = rel_id(a, b)
    if not ctx.exists(rid):
        ctx.create("relation", rid, fields(a, b, "polity", ctx.today, to))
        return
    was = ctx.get(rid, "stance")
    if was != to:
        ctx.emit("polity.stance", {"party": tuple(sorted((a, b)))}, purpose="stance", actor=rid,
                 payload={"relation": rid, "from": was, "to": to}, causes=causes)
        ctx.set(rid, "stance", to)


class War(System):
    """Wars declared, fought a year at a time, and ended (see the module doc)."""

    name, cadence, priority = "polity.war", "yearly", 2  # (after polity.diplomacy)
    reads = (frozenset({"ids:relation", "ids:war", "ids:settlement", "ids:place", "ids:route", "kind", "stance",
                        "trust", "news", "aggressor", "defender", "attackers", "defenders", "ended", "exhaustion",
                        "seat", "residents", "ends", "open", "control", "place", "started", "ledger"})
             | treaties.READS | geo.CHANGE_READS | life.DIE_READS)
    writes = (frozenset({"stance", "new:war", "new:relation", "attackers", "defenders", "ended", "outcome",
                         "exhaustion", "control", "ledger"})
              | treaties.WRITES | geo.CHANGE_WRITES | life.DIE_WRITES)
    event_types = EVENT_TYPES

    def handle(self, ctx, activation):
        """A ruler fallen in battle: their offices pass on (the follow-up `life.die` schedules)."""
        houses.handle_succession(ctx, activation)

    def run(self, ctx):
        for rid in ctx.ids("relation"):
            with ctx.scope(rid):
                if ctx.get(rid, "kind") == "polity" and ctx.get(rid, "stance") == "hostile":
                    self.declare(ctx, rid)
        for war in ctx.ids("war"):
            with ctx.scope(war):
                if ctx.get(war, "ended") is None:
                    self.fight(ctx, war)

    # ------------------------------------------------------------ going to war

    def declare(self, ctx, rid: str) -> None:
        a, b, trust = ctx.get(rid, "a"), ctx.get(rid, "b"), float(ctx.get(rid, "trust") or 0.0)
        if ctx.get(a, "ended") is not None or ctx.get(b, "ended") is not None:
            return
        truces = [t for t in ctx.get(rid, "treaties") or [] if ctx.get(t, "kind") == "truce"]
        p = DECLARE * max(0.0, -trust) * (TRUCE_SHAME if truces else 1.0)
        for side in sorted((a, b)):
            if p <= 0 or not ctx.chance(min(1.0, p), f"propose:war:{side}", owner=rid):
                continue
            ok, why = treaties.decide(ctx, side, "war", 0.8, rid)
            if not ok:
                continue
            other = b if side == a else a
            ident = f"war:{min(a, b)}|{max(a, b)}:{ctx.today.year}"
            news = ctx.get(rid, "news")
            ev = ctx.emit("polity.war_declared", {"aggressor": (side,), "defender": (other,)}, purpose="war",
                          actor=rid, payload={"war": ident, "relation": rid},
                          causes=why + ((Cause("event", news),) if news else ()))
            ctx.create("war", ident, {"aggressor": side, "defender": other, "attackers": [side], "defenders": [other],
                                      "started": ctx.today.to_json(), "ended": None, "outcome": None,
                                      "exhaustion": {side: 0.0, other: 0.0}, "cause": ev.id})
            for t in truces:  # (a truce broken to go to war: a betrayal)
                broke = ctx.emit("polity.treaty_broken", {"by": (side,), "party": (a, b)}, purpose=f"broken:{t}",
                                 actor=rid, payload={"treaty": t, "kind": "truce"})
                ctx.set(t, "broken_by", side)
                treaties._end(ctx, rid, t)
                _ledger(ctx, rid, "betrayal", broke.id)
            _set_stance(ctx, a, b, "war", (Cause("event", ev.id),))
            self.call_allies(ctx, ident, other, side)
            return

    def call_allies(self, ctx, war: str, defender: str, aggressor: str) -> None:
        for rid in ctx.ids("relation"):
            if ctx.get(rid, "kind") != "polity" or defender not in (ctx.get(rid, "a"), ctx.get(rid, "b")):
                continue
            ally = ctx.get(rid, "b") if ctx.get(rid, "a") == defender else ctx.get(rid, "a")
            if ally == aggressor or ctx.get(ally, "ended") is not None:
                continue
            for t in list(ctx.get(rid, "treaties") or []):
                if ctx.get(t, "kind") != "alliance":
                    continue
                ok, why = treaties.decide(ctx, ally, f"join:{war}", JOIN, rid)
                if ok:
                    joined = ctx.emit("polity.joined", {"ally": (ally,), "side": (defender,)}, purpose=f"join:{war}",
                                      actor=war, payload={"war": war}, causes=why)
                    ctx.set(war, "defenders", sorted(set(ctx.get(war, "defenders")) | {ally}))
                    ctx.set(war, "exhaustion", {**ctx.get(war, "exhaustion"), ally: 0.0})
                    for enemy in ctx.get(war, "attackers"):  # (the ally is at war with every attacker now)
                        _set_stance(ctx, ally, enemy, "war", (Cause("event", joined.id),))
                else:  # (an ally who won't come: the alliance is broken, a betrayal)
                    broke = ctx.emit("polity.treaty_broken", {"by": (ally,), "party": (ctx.get(rid, "a"), ctx.get(rid, "b"))},
                                     purpose=f"broken:{t}", actor=rid, payload={"treaty": t, "kind": "alliance"}, causes=why)
                    ctx.set(t, "broken_by", ally)
                    treaties._end(ctx, rid, t)
                    _ledger(ctx, rid, "betrayal", broke.id)
                break

    # ------------------------------------------------------------ a war's year

    def fight(self, ctx, war: str) -> None:
        sides = {k: [p for p in ctx.get(war, k) if ctx.get(p, "ended") is None] for k in ("attackers", "defenders")}
        if not sides["attackers"] or not sides["defenders"]:  # (a side has fallen: nothing left to fight)
            self._end(ctx, war, (sides["attackers"] or sides["defenders"] or [None])[0])
            return
        might = {p: strength(ctx, p) for k in sides for p in sides[k]}
        total = {k: sum(might[p] for p in v) + 1 for k, v in sides.items()}  # (+1: a war of the empty still ends)
        won = "attackers" if ctx.chance(total["attackers"] / (total["attackers"] + total["defenders"]), "war_year",
                                        owner=war) else "defenders"
        lost = "defenders" if won == "attackers" else "attackers"
        winner = ctx.choose("winner", sides[won], owner=war, weights=[might[p] + 1 for p in sides[won]])
        loser = ctx.choose("loser", sides[lost], owner=war, weights=[might[p] + 1 for p in sides[lost]])
        front = _front(ctx, loser, set(sides[won]))
        seat, lord = ctx.get(loser, "seat"), treaties.ruler(ctx, loser)
        if seat in front and (len(front) > 1 or (lord and ctx.protected(lord))):  # (the capital falls last; never
            front.pop(seat)                                                        # a pinned ruler's: S8 §3.4)
        place = ctx.choose("taken", list(front), owner=war) if front else None
        year = ctx.emit("polity.war_year", {"winner": (winner,), "loser": (loser,)}, purpose="war_year", actor=war,
                        place=place, payload={"war": war, "place": place})
        ex = dict(ctx.get(war, "exhaustion"))
        for p in sides[won]:
            ex[p] = round(ex.get(p, 0.0) + WON, 6)
        for p in sides[lost]:
            ex[p] = round(ex.get(p, 0.0) + LOST, 6)
        ctx.set(war, "exhaustion", ex)
        for x in sides["attackers"]:  # (the war, in every cross-side relation's ledger: no fading while it lasts)
            for y in sides["defenders"]:
                if ctx.exists(rel_id(x, y)):
                    _ledger(ctx, rel_id(x, y), "war", year.id)
        if place:
            geo.apply_change(ctx, {"place": place, "control": front[place], "why": f"taken in {war}"})
        if lord and ctx.chance(FALL, "falls", owner=war):
            life.die(ctx, lord, ctx.get(lord, "place"), "fell in battle", causes=(Cause("event", year.id),))
        if not _holds(ctx, loser, ("settlement",)):
            self.fall(ctx, war, loser, front.get(place) or winner, year.id)
        elif max(ex.get(p, 0.0) for k in sides for p in sides[k]) >= EXHAUSTED:
            self.peace(ctx, war, sides, ex, year.id)

    def peace(self, ctx, war: str, sides: dict, ex: dict, why: str) -> None:
        tired = {k: max(ex.get(p, 0.0) for p in v) for k, v in sides.items()}
        won = "attackers" if tired["attackers"] < tired["defenders"] else "defenders"
        aggressor, defender = ctx.get(war, "aggressor"), ctx.get(war, "defender")
        winner, loser = (aggressor, defender) if won == "attackers" else (defender, aggressor)
        made = ctx.emit("polity.peace", {"winner": (winner,), "loser": (loser,)}, purpose="peace", actor=war,
                        payload={"war": war}, causes=(Cause("event", why),))
        self._end(ctx, war, winner)
        rid = rel_id(aggressor, defender)
        treaties.sign(ctx, rid, "truce", aggressor, defender, float(ctx.get(rid, "trust") or 0.0),
                      causes=(Cause("event", made.id),))
        for x in sides["attackers"]:
            for y in sides["defenders"]:
                _set_stance(ctx, x, y, "hostile", (Cause("event", made.id),))

    def fall(self, ctx, war: str, loser: str, victor: str, why: str) -> None:
        """`loser` holds no settlement: it falls. Its places go to `victor`, its treaties end, and its wars
        too where it led a side."""
        ctx.emit("polity.fallen", {"polity": (loser,), "victor": (victor,)}, purpose="fallen", actor=war,
                 payload={"war": war}, causes=(Cause("event", why),))
        ctx.set(loser, "ended", ctx.today.to_json())
        for w in ctx.ids("war"):
            if ctx.get(w, "ended") is None and loser in (ctx.get(w, "aggressor"), ctx.get(w, "defender")):
                self._end(ctx, w, victor if w == war else None)
        for rid in ctx.ids("relation"):
            if loser in (ctx.get(rid, "a"), ctx.get(rid, "b")):
                for t in list(ctx.get(rid, "treaties") or []):
                    treaties._end(ctx, rid, t)
                if ctx.get(rid, "stance") == "war":
                    ctx.set(rid, "stance", "hostile")
        for p in _holds(ctx, loser):
            geo.apply_change(ctx, {"place": p, "control": victor, "why": f"{loser} fell"})

    def _end(self, ctx, war: str, outcome: str | None) -> None:
        ctx.set(war, "ended", ctx.today.to_json())
        ctx.set(war, "outcome", outcome)
