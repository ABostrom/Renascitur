"""Families (S3 spec §4.4): who marries whom.

`people.marriage` (yearly) runs one market per region, inside `ctx.scope(region)`, over the
residents of the region's settlements. Each unmarried (or widowed) man of marriageable age enters
the market this year with some chance; he and every eligible woman are matched by S1's round-based
rendezvous `ctx.match`, never in list order, so one person more or less only changes the pairs that
person would have been part of.

- **Eligible:** active, unmarried, within the race's marriage ages.
- **Not kin:** no shared ancestor within `kin_degree` generations (default 2: no shared grandparent),
  and neither is the other's ancestor. Every hop reads the recorded `mother`/`father` fields.
- **Preferences:** a man weighs each woman by age gap, the same settlement, and the same race.
- **Residence** (`residence`, default "husband"): the wife moves to her husband's settlement.

Commoner spouses promoted from the masses arrive with aggregates (#71/#72).
"""

from __future__ import annotations

import math

from renasci.core.events import EventType
from renasci.core.systems import System
from renasci.people.life import world
from renasci.people.races import age_years

MARRIAGE = EventType("people.marriage", 1, roles={"spouse": (2, 2)}, payload={"commoner": "bool"})


def ancestors(ctx, person: str, depth: int) -> set[str]:
    """Known ancestors up to `depth` generations, through recorded parent fields."""
    out: set[str] = set()
    frontier = [person]
    for _ in range(depth):
        nxt = []
        for p in frontier:
            for parent in (ctx.get(p, "mother"), ctx.get(p, "father")):
                if parent and parent not in out:
                    out.add(parent)
                    nxt.append(parent)
        frontier = sorted(nxt)
    return out


class Marriage(System):
    name, cadence = "people.marriage", "yearly"
    reads = frozenset({"ids:settlement", "region", "residents", "sex", "race", "born", "spouse", "mother",
                       "father", "place", "status"})
    writes = frozenset({"spouse", "residents", "place"})
    event_types = (MARRIAGE,)

    def run(self, ctx):
        races, _, _ = world(ctx)
        kin_degree = int(ctx.params.get("kin_degree", 2))
        residence = ctx.params.get("residence", "husband")
        market = float(ctx.params.get("market_rate", 0.35))
        regions: dict[str, list[str]] = {}
        # Every settlement's region is read unscoped: regions are fixed. A system that ever moves a
        # settlement between regions would (rightly) make every market's inputs differ.
        for s in ctx.ids("settlement"):
            regions.setdefault(ctx.get(s, "region"), []).append(s)
        for region in sorted(regions):
            with ctx.scope(region):
                self._market(ctx, region, regions[region], races, kin_degree, residence, market)

    def _market(self, ctx, region, settlements, races, kin_degree, residence, market) -> None:
        men, women = [], []
        for s in settlements:
            for p in ctx.get(s, "residents"):
                if ctx.status(p) != "active" or ctx.get(p, "spouse") is not None:
                    continue
                lo, hi = races[ctx.get(p, "race")].marriage
                if lo <= age_years(ctx.calendar, ctx.get(p, "born"), ctx.today) <= hi:
                    (men if ctx.get(p, "sex") == "m" else women).append(p)
        if not men or not women:
            return
        seekers = {}
        lineage = {p: ancestors(ctx, p, kin_degree) for p in sorted(men + women)}
        for man in men:
            if not ctx.chance(market, "seek", owner=man):
                continue
            prefs = {}
            for woman in women:
                if (man in lineage[woman] or woman in lineage[man] or lineage[man] & lineage[woman]):
                    continue  # kin
                gap = abs(ctx.get(man, "born")[1] - ctx.get(woman, "born")[1])
                w = math.exp(-gap / 8.0)
                w *= 2.0 if ctx.get(man, "place") == ctx.get(woman, "place") else 1.0
                w *= 1.0 if ctx.get(man, "race") == ctx.get(woman, "race") else 0.1
                prefs[woman] = w
            if prefs:
                seekers[man] = prefs
        for man, woman in ctx.match("marriage", seekers, owner=region).items():
            ctx.emit("people.marriage", {"spouse": (man, woman)}, purpose="marriage", actor=man,
                     place=ctx.get(man, "place"), payload={"commoner": False})
            ctx.set(man, "spouse", woman)
            ctx.set(woman, "spouse", man)
            mover, stayer = (woman, man) if residence == "husband" else (man, woman)
            old, new = ctx.get(mover, "place"), ctx.get(stayer, "place")
            if old != new:
                ctx.set(old, "residents", [p for p in ctx.get(old, "residents") if p != mover])
                ctx.set(new, "residents", sorted(ctx.get(new, "residents") + [mover]))
                ctx.set(mover, "place", new)
