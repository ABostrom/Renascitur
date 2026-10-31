"""Trade (S9 spec §4, #125): goods flowing between neighbouring towns.

Only in a world whose crafts catalogue has `materials` (the system is added then). `trade.flows` (yearly,
after `people.crafts`; one scope per pair of neighbouring towns, by road, through taverns and landmarks but
stopping at the first town: `beliefs.neighbour_settlements`):

- for each material, goods flow **downhill**: from the town with more stock per head (masses and notables) to
  the one with less, a `RATE` of the gap toward the level they'd share, never past it (`flow`);
- the year's flow is capped by the road (`CAP` units a year, less the more days apart) and helped by merchants
  (notables whose job is `merchant`, at either end: each adds `MERCHANT` to the cap);
- **war cuts trade:** towns held by two realms at war with each other trade nothing;
- one `trade.flow` event per pair a year (what moved, which way), then the goods ledger: `traded_out` at the
  giver, `traded_in` at the taker, so the ledger still balances.

A coarse step moves N years of flow at once (the cap times N). The merchants' cut and S8's trade pull from
real flows (`trade: true`) are later.
"""

from __future__ import annotations

from renasci.core.events import EventType
from renasci.core.systems import System
from renasci.people.beliefs import neighbour_settlements
from renasci.people.population import masses

RATE, CAP, MERCHANT = 0.25, 40, 20
FLOW = EventType("trade.flow", 1, roles={"from": (1, 1), "to": (1, 1)}, payload={"moved": "json", "back": "json"})
EVENT_TYPES = (FLOW,)
READS = frozenset({"ids:settlement", "ids:route", "ends", "days", "open", "vialux", "residents", "job", "control",
                   "ids:relation", "a", "b", "kind", "stance", "pop:*", "stock:*", "goods:*"})
WRITES = frozenset({"stock:*", "goods:*"})


def flow(stock_a: int, pop_a: int, stock_b: int, pop_b: int, cap: int, years: int = 1) -> int:
    """How much goes from a to b in `years` (0 when b has as much per head): the share of the gap toward the level
    they'd share that `years` of `RATE` close, capped (pure)."""
    pop_a, pop_b = max(pop_a, 1), max(pop_b, 1)
    if stock_a * pop_b <= stock_b * pop_a:
        return 0
    level = (stock_a + stock_b) * pop_a // (pop_a + pop_b)  # (a's stock were they level per head)
    return max(0, min(cap, int((stock_a - level) * (1.0 - (1.0 - RATE) ** years))))


def at_war(ctx, a: str, b: str) -> bool:
    """Whether the realms holding two towns are at war with each other."""
    pa, pb = ctx.get(a, "control"), ctx.get(b, "control")
    if not pa or not pb or pa == pb:
        return False
    x, y = sorted((pa, pb))
    rid = f"rel:{x}|{y}"
    return ctx.exists(rid) and ctx.get(rid, "stance") == "war"


class Trade(System):
    name, cadence = "trade.flows", "yearly"
    priority = 6  # (after people.crafts' yields)
    reads, writes, event_types = READS, WRITES, EVENT_TYPES

    def run(self, ctx):
        self.step(ctx, 1)

    def coarse_fallback(self, ctx, years: int) -> None:
        self.step(ctx, years)

    def step(self, ctx, years: int) -> None:
        mats = sorted((ctx.params.get("crafts") or {}).get("materials") or {})
        if not mats:
            return
        pairs = set()
        for s in ctx.ids("settlement"):
            for t, days, _ in neighbour_settlements(ctx, s):
                pairs.add((min(s, t), max(s, t), days))
        for a, b, days in sorted(pairs):
            with ctx.scope(f"{a}|{b}"):
                self.exchange(ctx, a, b, days, mats, years)

    def exchange(self, ctx, a, b, days, mats, years) -> None:
        if at_war(ctx, a, b):
            return
        merchants = sum(1 for s in (a, b) for p in ctx.get(s, "residents") if ctx.get(p, "job") == "merchant")
        cap = int(years * (CAP + MERCHANT * merchants) / (1 + days / 10))
        heads = {s: (masses(ctx, s) if ctx.params.get("aggregates") else 0) + len(ctx.get(s, "residents")) for s in (a, b)}
        stock = {s: ctx.read_columns(s, [f"stock:{m}" for m in mats]) for s in (a, b)}
        moved, back = {}, {}
        for m in mats:
            sa, sb = int(stock[a][f"stock:{m}"]), int(stock[b][f"stock:{m}"])
            n = flow(sa, heads[a], sb, heads[b], cap, years)
            if n:
                moved[m] = n
                continue
            n = flow(sb, heads[b], sa, heads[a], cap, years)
            if n:
                back[m] = n
        if not moved and not back:
            return
        ctx.emit("trade.flow", {"from": (a,), "to": (b,)}, purpose=f"flow:{b}", actor=a, place=a,
                 payload={"moved": moved, "back": back})
        for giver, taker, goods in ((a, b, moved), (b, a, back)):
            if not goods:
                continue
            g = ctx.read_columns(giver, [c for m in goods for c in (f"stock:{m}", f"goods:{m}:traded_out")])
            ctx.write_columns(giver, {**{f"stock:{m}": int(g[f"stock:{m}"]) - n for m, n in goods.items()},
                                      **{f"goods:{m}:traded_out": int(g[f"goods:{m}:traded_out"]) + n for m, n in goods.items()}})
            h = ctx.read_columns(taker, [c for m in goods for c in (f"stock:{m}", f"goods:{m}:traded_in")])
            ctx.write_columns(taker, {**{f"stock:{m}": int(h[f"stock:{m}"]) + n for m, n in goods.items()},
                                      **{f"goods:{m}:traded_in": int(h[f"goods:{m}:traded_in"]) + n for m, n in goods.items()}})
