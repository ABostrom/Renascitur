"""A polity's derived stats (S8 spec §6, #156): what a pin, a chronicle or the Observatory can read.

Yearly (`polity.stats`, after war; and as its own coarse fallback), each polity that hasn't fallen gets:
- **strength:** the might `war.strength` counts (the people of the settlements it holds);
- **stability:** 0.3, plus 0.3 with a ruler in office, plus 0.2 when the office is lawfully held, less 0.2 for
  each unit of exhaustion in its worst live war, within [0, 1];
- **wealth:** a point for each settlement it holds, and half a point for each live trade treaty.

A `polity.stats` event comes only when they change. (Pins on them, `StatThreshold`, are future: S8 §6.)
"""

from __future__ import annotations

from renasci.core.events import EventType
from renasci.core.systems import System

STATS = EventType("polity.stats", 1, roles={"polity": (1, 1)},
                  payload={"strength": "int", "stability": "float", "wealth": "float"})


def derive(ctx, polity: str) -> dict:
    from renasci import treaties, war

    office = ctx.get(polity, "ruler")
    lord = treaties.ruler(ctx, polity)
    lawful = bool(office) and ctx.get(office, "legitimacy") in (None, "lawful")
    worst = max((max(ctx.get(w, "exhaustion").get(polity, 0.0), 0.0) for w in ctx.ids("war")
                 if ctx.get(w, "ended") is None and polity in ctx.get(w, "attackers") + ctx.get(w, "defenders")),
                default=0.0)
    stability = 0.3 + (0.3 if lord else 0.0) + (0.2 if lawful and lord else 0.0) - 0.2 * worst
    held = [s for s in ctx.ids("settlement") if ctx.get(s, "control") == polity]
    trade = sum(1 for r in ctx.ids("relation") if polity in (ctx.get(r, "a"), ctx.get(r, "b"))
                for t in ctx.get(r, "treaties") or [] if ctx.get(t, "kind") == "trade")
    return {"strength": war.strength(ctx, polity), "stability": round(max(0.0, min(1.0, stability)), 6),
            "wealth": float(len(held) + 0.5 * trade)}


class Stats(System):
    name, cadence, priority = "polity.stats", "yearly", 3  # (after polity.war)
    reads = frozenset({"ids:polity", "ids:war", "ids:settlement", "ids:relation", "ruler", "holder", "status",
                       "legitimacy", "ended", "exhaustion", "attackers", "defenders", "control", "residents", "a", "b",
                       "treaties", "kind", "strength", "stability", "wealth"})
    writes = frozenset({"strength", "stability", "wealth"})
    event_types = (STATS,)

    def coarse_fallback(self, ctx, years: int) -> None:
        self.run(ctx)

    def run(self, ctx):
        for polity in ctx.ids("polity"):
            with ctx.scope(polity):
                if ctx.get(polity, "ended") is not None:
                    continue
                now = derive(ctx, polity)
                if all(ctx.get(polity, k) == v for k, v in now.items()):
                    continue
                ctx.emit("polity.stats", {"polity": (polity,)}, purpose="stats", actor=polity, payload=now)
                for k, v in now.items():
                    ctx.set(polity, k, v)
