"""Journeys (S4 spec §5): a move between settlements takes the days its route says.

`depart(ctx, person, to, why)` finds the path (`renasci.geo.path`); with none, nothing happens. Else the
person's `journey` is set (`from`, `to`, `path`, `depart`, `arrive`, `why`), `people.depart` is
emitted, and an `arrive` follow-up is scheduled `days` later **for the calling system**, which hands it
to `arrive`. The traveller stays a resident of the origin on the road, so residents and population
flows change only on arrival and conservation holds throughout. On the road they aren't in the
marriage market, can't be courted, and can't set out again.

`arrive` does nothing if the person is no longer active (dead, or faded into the masses) or the journey
isn't the one it was scheduled for; else it moves them (residents, `place`, flows), clears the
journey and emits `people.arrive`, caused by the departure.

**Migration** (`people.migration`, yearly, only in a world with routes): each unmarried adult notable
with no office, no journey, no plot against them and no protection (a pin, a ripple) has a `migration_rate` chance (default 0.01) to set
out for a settlement within `flee_days` (default 30), nearer and emptier places likelier. The same pass
completes any journey whose arrival is overdue (its follow-up was dropped by a ruleset switch): a
repair, not a model; a switch to a ruleset without migration leaves such a traveller at home, on the road.
"""

from __future__ import annotations

from renasci import geo
from renasci.core.calendar import AgeBoundaryError, Date, Span
from renasci.core.events import EventType
from renasci.core.systems import System
from renasci.people import beliefs, population
from renasci.people.races import age_years

DEPART = EventType("people.depart", 1, roles={"traveller": (1, 1), "origin": (1, 1), "destination": (1, 1)},
                   payload={"days": "int", "why": "str"})
ARRIVE = EventType("people.arrive", 1, roles={"traveller": (1, 1), "origin": (1, 1), "destination": (1, 1)},
                   payload={"why": "str"})
EVENT_TYPES = (DEPART, ARRIVE) + beliefs.EVENT_TYPES  # (an arrival may tell what the traveller believes)
READS = geo.READS | frozenset({"journey", "place", "residents", "status", "flow:*"}) | beliefs.ARRIVAL_READS
WRITES = frozenset({"journey", "place", "residents", "flow:*"}) | beliefs.ARRIVAL_WRITES
FLEE_DAYS, MIGRATION_RATE, ADULT = 30, 0.01, 16


def has_routes(ctx) -> bool:
    return bool(ctx.ids("route"))


def destinations(ctx, home: str, max_days: int, who: str | None = None) -> dict[str, int]:
    """Settlements other than `home` within `max_days` by road, with their days (as `who` travels today,
    in a world with routing)."""
    settlements = set(ctx.ids("settlement"))
    return {p: d for p, d in sorted(geo.reach(ctx, home, max_days, who).items()) if p in settlements and p != home}


def depart(ctx, person: str, to: str, why: str, causes=()) -> int | None:
    """Set out for `to`; returns the journey's days, or None (no path, already there, already travelling, or no time left)."""
    if ctx.get(person, "journey"):
        return None
    home = ctx.get(person, "place")
    found = geo.path(ctx, home, to, person) if home != to else None
    if found is None:
        return None
    days, path = found
    try:
        arrive_on = ctx.calendar.add(ctx.today, Span(days=days))
    except AgeBoundaryError:  # (it would end past the age's last day: nobody sets out on it)
        return None
    ctx.emit("people.depart", {"traveller": (person,), "origin": (home,), "destination": (to,)}, purpose="depart",
             actor=person, place=home, payload={"days": days, "why": why}, causes=causes)
    ctx.set(person, "journey", {"from": home, "to": to, "path": path, "depart": ctx.today.to_json(),
                                "arrive": arrive_on.to_json(), "why": why})
    ctx.schedule(Span(days=days), "arrive", entity=person, payload={"person": person, "depart": ctx.today.to_json()})
    return days


def relocate(ctx, person: str, new: str) -> None:
    """Move at once, in a world without routes (the caller has emitted the event that moves them)."""
    home = ctx.get(person, "place")
    ctx.set(home, "residents", [p for p in ctx.get(home, "residents") if p != person])
    ctx.set(new, "residents", sorted(ctx.get(new, "residents") + [person]))
    ctx.set(person, "place", new)
    population.bump(ctx, home, out=1)
    population.bump(ctx, new, **{"in": 1})


def _move(ctx, person: str, journey: dict) -> None:
    old, new = ctx.get(person, "place"), journey["to"]
    ctx.emit("people.arrive", {"traveller": (person,), "origin": (old,), "destination": (new,)}, purpose="arrive",
             actor=person, place=new, payload={"why": journey["why"]})
    ctx.set(old, "residents", [p for p in ctx.get(old, "residents") if p != person])
    ctx.set(new, "residents", sorted(ctx.get(new, "residents") + [person]))
    ctx.set(person, "place", new)
    ctx.set(person, "journey", None)
    population.bump(ctx, old, out=1)
    population.bump(ctx, new, **{"in": 1})
    beliefs.on_arrival(ctx, person, new)  # (S6: a newcomer tells what they believe)


def arrive(ctx, activation) -> None:
    """The `arrive` follow-up `depart` scheduled (systems that start journeys route it here)."""
    person = activation.payload["person"]
    with ctx.scope(person):
        journey = ctx.get(person, "journey")
        if ctx.status(person) != "active" or not journey or journey["depart"] != activation.payload["depart"]:
            return
        _move(ctx, person, journey)


class Migration(System):
    name, cadence = "people.migration", "yearly"
    priority = 8  # after schemes (7)
    reads = READS | population.COLUMN_READS | frozenset(
        {"ids:settlement", "ids:route", "born", "spouse", "offices", "plots", "capacity"})
    writes = WRITES
    event_types = EVENT_TYPES

    def run(self, ctx):
        if not has_routes(ctx):
            return
        rate = float(ctx.params.get("migration_rate", MIGRATION_RATE))
        reach = int(ctx.params.get("flee_days", FLEE_DAYS))
        for s in ctx.ids("settlement"):
            with ctx.scope(s):
                for p in list(ctx.get(s, "residents")):
                    journey = ctx.get(p, "journey")
                    if journey:
                        if Date.from_json(journey["arrive"]) < ctx.today:  # its follow-up was lost
                            _move(ctx, p, journey)
                        continue
                    if (ctx.get(p, "spouse") is not None or ctx.get(p, "offices") or ctx.get(p, "plots")
                            or ctx.protected(p) or age_years(ctx.calendar, ctx.get(p, "born"), ctx.today) < ADULT):
                        continue
                    if not ctx.chance(rate, "migrate", owner=p):
                        continue
                    options = destinations(ctx, s, reach, p)
                    if not options:
                        continue
                    weights = [_pull(ctx, d, days) for d, days in options.items()]
                    to = ctx.choose("migrate", list(options), owner=p, weights=weights)
                    depart(ctx, p, to, "migration")

    def handle(self, ctx, activation):
        if activation.purpose != "arrive":
            raise ValueError(f"{self.name} has no follow-up {activation.purpose!r}")
        arrive(ctx, activation)


def _pull(ctx, settlement: str, days: int) -> float:
    """Nearer is likelier; so is room to live (a full settlement still draws a little). Capacity counts
    everyone, so the masses count too."""
    capacity = ctx.get(settlement, "capacity")
    people = len(ctx.get(settlement, "residents")) + (
        population.masses(ctx, settlement) if ctx.params.get("aggregates") else 0)
    room = 1.0 if not capacity else max(0.1, 1.0 - people / capacity)
    return room / days
