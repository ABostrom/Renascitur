"""Stocks: quantities that build and drain, and that remember what filled them (vision spec §3, #162).

This is how one system reaches another without naming it. Whatever adds to a stock (`add`) is recorded by event;
a rule that later reads the stock can cite those events (`because`), so a chain nobody wrote still traces back. A
sack and a famine both fill a town's `corpses`, burial drains it, and an outbreak cites the deaths behind it.

An entity's stock lives in two fields: `level:<name>`, the level, and `why:<name>`, `{event: amount}`, the largest
`KEPT` contributions. (`stock:<material>` is S9's goods column, a different thing.) A draining stock shares the
loss across them in proportion. The record is a citation, not an account: past `KEPT` the smallest are forgotten,
the level stays whole, and its amounts are only good for ranking. Absent means empty, so only what has a history
carries one: moving nothing writes nothing, and a stock nearly gone (`FLOOR`) empties. A system using stocks adds
`READS` and `WRITES` to its own.

**Use.** Emit first, inside a `ctx.scope` per entity, so an add can't fall under a neighbour's event; add once per
event, because a small add past the cap is forgotten even if it recurs. Each change writes two fields, so seasonal
drains on many entities have a cost: skip what's empty.

Any entity can hold any stock: the module knows nothing of what a stock means.
"""

from __future__ import annotations

import math

from renasci.core.events import Cause

KEPT = 8  # (contributions remembered: the citation's cap, master §5's sampling of aggregates)
EPSILON = 1e-6  # (a contribution this small has faded out)
FLOOR = 1e-4  # (a stock drained below this is empty: fades would otherwise stall on the rounding, cited forever)

READS = frozenset({"level:*", "why:*"})
WRITES = frozenset({"level:*", "why:*"})


def level(ctx, entity: str, name: str) -> float:
    return float(ctx.get(entity, f"level:{name}") or 0.0)


def _check(name: str, amount: float) -> None:
    if not math.isfinite(amount) or amount < 0:
        raise ValueError(f"stock {name!r} moves by a finite, non-negative amount, got {amount}")


def _keep(sources: dict) -> dict:
    """The largest `KEPT`, in a settled order: ties break by event, so arrival order never shows."""
    largest = sorted(sources.items(), key=lambda s: (-s[1], s[0]))[:KEPT]
    return dict(sorted((e, round(a, 6)) for e, a in largest if a > EPSILON))


def _write(ctx, entity: str, name: str, value: float, sources: dict) -> None:
    ctx.set(entity, f"level:{name}", round(value, 6))
    ctx.set(entity, f"why:{name}", _keep(sources))


def add(ctx, entity: str, name: str, amount: float) -> None:
    """Add to a stock, under the event being written (emit first, as for any write)."""
    _check(name, amount)
    if not amount:
        return
    sources = dict(ctx.get(entity, f"why:{name}") or {})
    event = ctx.current_event
    sources[event] = sources.get(event, 0.0) + amount
    _write(ctx, entity, name, level(ctx, entity, name) + amount, sources)


def take(ctx, entity: str, name: str, amount: float) -> float:
    """Drain up to `amount`, shared across what filled it; returns what was taken. Nothing there, nothing written."""
    _check(name, amount)
    have = level(ctx, entity, name)
    if not have or not amount:
        return 0.0
    taken = have if have - amount < FLOOR else amount
    left = 1.0 - taken / have
    sources = {e: a * left for e, a in (ctx.get(entity, f"why:{name}") or {}).items()}
    _write(ctx, entity, name, have - taken, sources)
    return taken


def fade(ctx, entity: str, name: str, share: float) -> float:
    """Drain a share of what's there; returns what was taken."""
    return take(ctx, entity, name, level(ctx, entity, name) * share)


def because(ctx, entity: str, name: str, most: int = KEPT) -> tuple[Cause, ...]:
    """What filled this stock, as causes for an event that read it: the largest first."""
    sources = ctx.get(entity, f"why:{name}") or {}
    largest = sorted(sources.items(), key=lambda s: (-s[1], s[0]))[:most]
    return tuple(Cause("event", e) for e, _ in largest)
