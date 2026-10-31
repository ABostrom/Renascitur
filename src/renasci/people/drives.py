"""Drives (S3 spec §7): how sated each notable's basic needs are, from 0 (desperate) to 1 (sated).

A drive is a class with a `name`, the fields it `reads`, and `level(ctx, person, settlement)`. The
starter set reads only what exists so far; deeper systems (food and harvests in S10, violence in S7
and S8) will feed them later without changing their shape.

- `food`: how crowded the settlement is (masses + notables against its capacity, or notables alone in a
  world without aggregates); in a famine world (S10 #129), no more than `Food.STARVING` while the town is in
  famine.
- `safety`: one minus the settlement's `danger` (0 when unset).
- `belonging`: a spouse, living children, and the strength of one's ties.
- `status`: one's house and its rank, offices held, and being an heir is S7's to add.

`people.drives` (yearly, one `ctx.scope(settlement)` per settlement) recomputes every resident's
drives, quantised to 0.05, and writes them only when they changed, so they can be read as of any date
from `state_deltas`. S7 forms ambitions from them.
"""

from __future__ import annotations

from renasci.core.events import EventType
from renasci.core.systems import System

UPDATE = EventType("people.drives", 1, roles={"settlement": (1, 1)}, payload={"changed": "int"})


def _q(x: float) -> float:
    return round(min(max(x, 0.0), 1.0) * 20) / 20


class Drive:
    name = ""
    reads: frozenset[str] = frozenset()

    def level(self, ctx, person: str, settlement: str) -> float:
        raise NotImplementedError


class Food(Drive):
    name, reads = "food", frozenset({"capacity", "residents", "pop:*", "famine"})
    STARVING = 0.2  # (a famine's hunger: S10 #129)

    def level(self, ctx, person, settlement):
        from renasci.people.population import masses

        capacity = ctx.get(settlement, "capacity")
        level = 1.0
        if capacity:
            people = len(ctx.get(settlement, "residents")) + (masses(ctx, settlement) if ctx.params.get("aggregates") else 0)
            level = 1.2 - people / capacity  # comfortable below ~40% full, hungry when full
        if (ctx.params.get("ecology") or {}).get("famine") is not None and ctx.get(settlement, "famine"):
            level = min(level, self.STARVING)
        return level


class Safety(Drive):
    name, reads = "safety", frozenset({"danger"})

    def level(self, ctx, person, settlement):
        return 1.0 - float(ctx.get(settlement, "danger") or 0.0)


class Belonging(Drive):
    name, reads = "belonging", frozenset({"spouse", "children", "status", "ties", "strength"})

    def level(self, ctx, person, settlement):
        x = 0.1 + (0.4 if ctx.get(person, "spouse") else 0.0)
        x += min(0.3, 0.1 * sum(1 for c in ctx.get(person, "children") or [] if ctx.status(c) == "active"))
        x += min(0.3, 0.15 * sum(ctx.get(t, "strength") for t in ctx.get(person, "ties") or []))
        return x


class Status(Drive):
    name, reads = "status", frozenset({"house", "rank", "offices", "favour"})

    def level(self, ctx, person, settlement):
        house = ctx.get(person, "house")
        x = 0.2
        if house:
            rank = int(ctx.get(house, "rank") or 0)
            x += 0.3 + 0.2 * rank / (rank + 2)
        x += 0.3 * min(1, len(ctx.get(person, "offices") or []))
        x += 0.3 * float(ctx.get(person, "favour") or 0.0)  # court favour (S7 CourtFavour)
        return x


DRIVES: dict[str, Drive] = {d.name: d for d in (Food(), Safety(), Belonging(), Status())}


class Drives(System):
    name, cadence = "people.drives", "yearly"
    priority = 5  # after the year's ties and successions settle
    reads = frozenset({"ids:settlement", "residents", "drives"}).union(*(d.reads for d in DRIVES.values()))
    writes = frozenset({"drives"})
    event_types = (UPDATE,)

    def run(self, ctx):
        for s in ctx.ids("settlement"):
            with ctx.scope(s):
                fresh = {}
                for p in ctx.get(s, "residents"):
                    now = {name: _q(d.level(ctx, p, s)) for name, d in sorted(DRIVES.items())}
                    if now != (ctx.get(p, "drives") or {}):
                        fresh[p] = now
                if not fresh:
                    continue
                ctx.emit("people.drives", {"settlement": (s,)}, purpose="drives", actor=s, place=s,
                         payload={"changed": len(fresh)})
                for p, now in sorted(fresh.items()):
                    ctx.set(p, "drives", now)
