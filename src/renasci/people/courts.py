"""Courts and exile (S8 spec §9, #158): a realm's ruler judges an exposed plot against an office holder.

`trial(ctx, accused, victim, event, grave=...)` holds one, in the activation that exposed the plot: the
court is the realm that controls where the accused lives (else the realm their house belongs to), and the
judge is its ruler's holder (no court for the ruler themselves, nor where the throne is empty). The
verdict is a keyed draw (`polity.trial`, owned by the scheme, else the accused):

- **pardon** leans on the accused's favour, a tie of friendship with the judge, and kinship;
- **fine** costs favour;
- **exile** grows with how `grave` the plot was (1 for a killing or a seizure, less for a shaming): the
  accused goes to the nearest settlement outside the realm (by road, else at once), and is `exiled`:
  barred from the realm's settlements while that judge holds the throne (`barred`, which Flee asks).
  With nowhere outside the realm to go, it is a fine;
- **execution** grows with gravity and the judge's temper, more so for a plot against the judge or their
  kin: a death, cause "executed", by the judge's hand (so a guarded accused survives: §3.4).

(A ruler's kin killed openly, rather than plotted against, isn't tried yet.)
"""

from __future__ import annotations

from renasci import geo
from renasci.core.events import Cause, EventType
from renasci.people import life, population, travel
from renasci.people.ambitions import trait

TRIAL = EventType("polity.trial", 1, roles={"accused": (1, 1), "judge": (1, 1), "victim": (0, 1)},
                  payload={"verdict": "str", "polity": "id"})
EVENT_TYPES = (TRIAL,) + life.DIE_EVENTS + travel.EVENT_TYPES
VERDICTS = ("pardon", "fine", "exile", "execution")
FINE = -0.3
BAR_READS = frozenset({"exiled", "control", "holder"})
READS = (BAR_READS | life.DIE_READS | travel.READS | population.COLUMN_READS
         | frozenset({"place", "house", "ids:polity", "members", "ended", "ruler", "favour", "ties", "a", "b", "kind",
                      "traits", "ids:settlement", "region"}))
WRITES = life.DIE_WRITES | travel.WRITES | frozenset({"favour", "exiled", "place", "residents"})


def court(ctx, person: str) -> tuple[str, str, str] | None:
    """(polity, its ruler's office, the judge) for a trial of `person`, or None."""
    place = ctx.get(person, "place")
    polity = ctx.get(place, "control") if place else None
    if polity is None:
        house = ctx.get(person, "house")
        polity = next((p for p in ctx.ids("polity") if house and house in (ctx.get(p, "members") or [])), None)
    if polity is None or ctx.get(polity, "ended") is not None:
        return None
    office = ctx.get(polity, "ruler")
    judge = ctx.get(office, "holder") if office else None
    if judge is None or judge == person or ctx.status(judge) != "active":
        return None
    return polity, office, judge


def _tie(ctx, a: str, b: str) -> str | None:
    for t in ctx.get(a, "ties") or []:
        if {ctx.get(t, "a"), ctx.get(t, "b")} == {a, b}:
            return ctx.get(t, "kind")
    return None


def weights(ctx, accused: str, victim: str | None, judge: str, grave: float) -> list[float]:
    """The verdicts' weights, in `VERDICTS` order."""
    tie = _tie(ctx, judge, accused)
    own = life.grieving(ctx, judge)
    pardon = 0.4 + max(0.0, float(ctx.get(accused, "favour") or 0.0)) + (1.0 if tie in ("friend", "mentor") else 0.0) \
        + (1.0 if accused in own else 0.0)
    exile = 0.3 + 0.7 * grave
    execution = grave * (0.2 + 0.8 * trait(ctx, judge, "temper")) + (0.6 * grave if victim == judge or victim in own else 0.0)
    return [round(w, 6) for w in (pardon, 1.0, exile, execution)]


def _abroad(ctx, person: str, polity: str) -> dict[str, float]:
    """Where an exile could go: settlements outside the realm, by road (weight: nearer first) or, in a world
    without routes, any of them."""
    home = ctx.get(person, "place")
    if travel.has_routes(ctx):
        reach = travel.destinations(ctx, home, 10 ** 6, person)
        return {s: 1.0 / d for s, d in reach.items() if ctx.get(s, "control") != polity}
    return {s: 1.0 for s in ctx.ids("settlement") if s != home and ctx.get(s, "control") != polity}


def trial(ctx, accused: str, victim: str | None, event: str | None, *, grave: float, verdict: str | None = None,
          scheme: str | None = None) -> str | None:
    """Try `accused` (see the module doc); the verdict, or None when there's no court. `verdict` fixes it
    (for tests)."""
    found = court(ctx, accused)
    if found is None or ctx.status(accused) != "active":
        return None
    polity, office, judge = found
    if verdict is None:
        verdict = ctx.choose("verdict", list(VERDICTS), owner=scheme or accused,
                             weights=weights(ctx, accused, victim, judge, grave), stakes=2.0,
                             roles={"accused": [accused], "judge": [judge]})
    to = None
    if verdict == "exile" and not ctx.get(accused, "journey"):
        abroad = _abroad(ctx, accused, polity)
        options = sorted(abroad)
        to = ctx.choose("exile", options, owner=scheme or accused, weights=[abroad[s] for s in options]) if options else None
        if to is not None and travel.has_routes(ctx) and geo.path(ctx, ctx.get(accused, "place"), to, accused) is None:
            to = None  # (in reach, but no road there today)
    if verdict == "exile" and to is None:
        verdict = "fine"  # (nowhere to send them)
    ev = ctx.emit("polity.trial", {"accused": (accused,), "judge": (judge,), "victim": (victim,) if victim else ()},
                  purpose="trial", actor=polity, place=ctx.get(accused, "place"),
                  payload={"verdict": verdict, "polity": polity},
                  causes=(Cause("event", event),) if event else ())
    causes = (Cause("event", ev.id),)
    if verdict == "fine":
        ctx.set(accused, "favour", round(max(-1.0, float(ctx.get(accused, "favour") or 0.0) + FINE), 2))
    elif verdict == "execution":
        life.die(ctx, accused, ctx.get(accused, "place"), "executed", killer=judge, causes=causes)
    elif verdict == "exile":
        ctx.set(accused, "exiled", {"polity": polity, "by": judge, "office": office, "since": ctx.today.to_json()})
        if travel.has_routes(ctx):
            travel.depart(ctx, accused, to, "exile", causes=causes)
        else:
            travel.relocate(ctx, accused, to)
    return verdict


def barred(ctx, person: str, settlement: str) -> bool:
    """Whether `person` is in exile from the realm that holds `settlement` (while the ruler who sent them
    away still holds the throne)."""
    ex = ctx.get(person, "exiled")
    return bool(ex) and ctx.get(settlement, "control") == ex["polity"] and ctx.get(ex["office"], "holder") == ex["by"]
