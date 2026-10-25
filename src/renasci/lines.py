"""Official lines (S8 spec §9, #158): a realm's own account of a war or a broken treaty.

When a war is declared each side blames the other (`started(war, by)`); at peace each side claims the
victory (`won(war, by)`), and the victor of a fall does; a broken treaty is the other side's betrayal
(`betrayed(treaty, by)`). `official(ctx, polity, claim, cause)` puts the line about: a `polity.line`
event, the claim given `SHARE` of the masses in every settlement the realm holds (`beliefs.seeded`, as a
planted rumour), and the ruler taking it on firmly. From there it travels as any talk does: news by road
carries it across the border, where the other side's line already answers the same question. Lines are
partisan, not true; `analysis.truth` judges them against the log. Only in a world with beliefs.
"""

from __future__ import annotations

from renasci.core.events import Cause, EventType
from renasci.people import beliefs

SHARE, CONF = 0.4, 0.9

LINE = EventType("polity.line", 1, roles={"polity": (1, 1)}, payload={"claim": "json", "key": "str"})
EVENT_TYPES = (LINE,) + beliefs.EVENT_TYPES
READS = (frozenset({"ids:settlement", "control", "shares", "ended", "ruler", "holder", "status"})
         | beliefs.PERCEIVE_READS)
WRITES = frozenset({"shares"}) | beliefs.PERCEIVE_WRITES


def official(ctx, polity: str, claim: dict, cause: str | None) -> None:
    """`polity` tells its side of it (see the module doc)."""
    if not beliefs.enabled(ctx) or not polity or ctx.get(polity, "ended") is not None:
        return
    k = beliefs.key(claim)
    ev = ctx.emit("polity.line", {"polity": (polity,)}, purpose=f"line:{k}", actor=polity,
                  payload={"claim": claim, "key": k}, causes=(Cause("event", cause),) if cause else ())
    for s in ctx.ids("settlement"):
        if ctx.get(s, "control") == polity:
            ctx.set(s, "shares", beliefs.seeded(ctx.get(s, "shares") or {}, claim, SHARE))
    from renasci.treaties import ruler  # (treaties tells lines of its betrayals)

    who = ruler(ctx, polity)
    if who:
        beliefs.hold(ctx, who, claim, CONF, ev.id)


def betrayal(ctx, parties, treaty: str, cause: str) -> None:
    """A broken treaty: each side says the other broke faith (the breaker too: it was driven to it)."""
    for side in sorted(parties):
        other = next((p for p in parties if p != side), None)
        if other:
            official(ctx, side, beliefs.claim("betrayed", treaty=treaty, by=other), cause)
