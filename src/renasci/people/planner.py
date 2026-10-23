"""The planner (S7 spec §5): from an ambition's subgoals to a scheme's plan.

**An exact search.** Actions are first *grounded*: each library action is bound to the targets it
could act on. A goal tag such as "dead:t:Arn" binds an action whose `achieves` is "dead:{target}";
an action that only needs *someone* ("tie:{target}", like `Recruit`) is bound to each accomplice
**candidate**. Only actions that matter are kept: those achieving a tag the goal needs, directly or
through the `requires` of another kept action (a backward closure).

Then a **uniform-cost search** (Dijkstra) over *what the plan has achieved so far*. A step is applicable
when its `requires` are facts or already achieved, and it adds its one `achieves` tag. Costs are
positive (`1/odds + secrecy`), so the first state that meets the goal is the cheapest plan. The step
count is bounded by `depth` (`2 + round(3 * wits)` for a schemer). Ties break on the plan's canonical
`(action, target)` steps. There are no draws: the same world gives the same plan.

A grounded action is dropped when its odds are 0, and when its `requires` already hold but `possible`
says no (an action whose prerequisites still lie ahead is judged when the scheme reaches it).

`plan(goals, ...)` is pure: the world comes in as functions. `plan_for(ctx, owner, goals, scheme)` binds
them to the simulation; every fact and every odds is a recorded read through `Ctx`, each asked once.
"""

from __future__ import annotations

import heapq
from dataclasses import dataclass

from renasci.people.actions import ACTIONS, FAVOURED, HEARD, SHAMED
from renasci.people.ambitions import trait


@dataclass(frozen=True)
class Plan:
    steps: tuple  # ({"action": name, "target": id or None}, ...)

    def to_json(self) -> dict:
        return {"steps": [dict(s) for s in self.steps]}

    @classmethod
    def from_json(cls, data: dict) -> Plan:
        return cls(tuple(dict(s) for s in data["steps"]))


def _bind(pattern: str, tag: str):
    """The target that makes `pattern` read `tag`: "" for a pattern without {target}; None if it can't."""
    if "{target}" not in pattern:
        return "" if pattern == tag else None
    head, tail = pattern.split("{target}", 1)
    if tag.startswith(head) and tag.endswith(tail) and len(tag) > len(head) + len(tail):
        return tag[len(head):len(tag) - len(tail)] if tail else tag[len(head):]
    return None


def _fill(tag: str, target: str | None) -> str:
    return tag.replace("{target}", target) if target and "{target}" in tag else tag


def cost(plan_: Plan, actions, odds) -> float:
    return sum(1.0 / odds(actions[s["action"]], s["target"]) + actions[s["action"]].secrecy for s in plan_.steps)


def plan(goals, *, actions=None, depth: int, fact, odds, candidates, possible=None) -> Plan | None:
    """The cheapest plan reaching any one of `goals` (tag sets) in at most `depth` steps, or None."""
    actions = actions if actions is not None else ACTIONS
    goals = [frozenset(g) for g in goals]
    facts: dict[str, bool] = {}
    odds_memo: dict[tuple, float] = {}

    def is_fact(tag):
        if tag not in facts:
            facts[tag] = bool(fact(tag))
        return facts[tag]

    def odds_of(name, target):
        key = (name, target)
        if key not in odds_memo:
            odds_memo[key] = float(odds(actions[name], target))
        return odds_memo[key]

    # Ground the actions that matter: a backward closure from every goal's tags.
    refs = sorted({t.split(":", 1)[1] for g in goals for t in g if ":" in t})
    people = [c for c in candidates(frozenset(refs)) if c not in refs]
    grounded: dict[tuple, tuple] = {}  # (name, target) -> (requires, achieves)
    todo = sorted({t for g in goals for t in g})
    needed: set[str] = set()
    while todo:
        tag = todo.pop()
        if tag in needed or is_fact(tag):
            continue
        needed.add(tag)
        for name in sorted(actions):
            a = actions[name]
            bound = _bind(a.achieves, tag)
            if bound is None:
                continue
            targets = people if bound == "" and any("{target}" in r for r in a.requires) else [bound or None]
            for t in targets:
                if (name, t) in grounded:
                    continue
                requires = frozenset(_fill(r, t) for r in a.requires)
                if odds_of(name, t) <= 0:
                    continue
                if possible is not None and all(is_fact(r) for r in requires) and not possible(a, t):
                    continue
                grounded[(name, t)] = (requires, _fill(a.achieves, t))
                todo.extend(sorted(r for r in requires if r not in needed))

    steps_by = sorted(grounded)  # deterministic expansion order

    def met(have):
        return any(all(t in have or is_fact(t) for t in g) for g in goals)

    # Uniform-cost search over achieved-tag sets, bounded by depth.
    start = frozenset()
    queue = [(0.0, (), start)]
    best_len: dict[frozenset, int] = {}
    while queue:
        c, key, have = heapq.heappop(queue)
        if met(have):
            return Plan(tuple({"action": n, "target": t or None} for n, t in key))
        n = len(key)
        if best_len.get(have, depth + 1) <= n:
            continue  # reached this state as cheaply (popped earlier) and no longer
        best_len[have] = n
        if n >= depth:
            continue
        for name, t in steps_by:
            requires, achieves = grounded[(name, t)]
            if achieves in have or is_fact(achieves):
                continue
            if all(r in have or is_fact(r) for r in requires):
                step = 1.0 / odds_of(name, t) + actions[name].secrecy
                heapq.heappush(queue, (round(c + step, 9), key + ((name, t or ""),), have | {achieves}))
    return None


# ---------------------------------------------------------------- bound to the simulation


def plan_for(ctx, owner: str, goals, scheme: str | None = None) -> Plan | None:
    """A plan for `owner`, reading the world through `ctx` (every fact is a recorded read)."""

    def fact(tag: str) -> bool:
        return holds(ctx, owner, tag, scheme)

    def odds(action, target) -> float:
        return action.odds(ctx, owner, target, scheme)

    def candidates(exclude) -> list[str]:
        return [p for p in _people_of(ctx, owner) if p not in exclude and ctx.status(p) == "active"]

    def possible(action, target) -> bool:
        return action.feasible(ctx, owner, target, scheme)

    depth = 2 + round(3 * trait(ctx, owner, "wits"))
    return plan(goals, depth=depth, fact=fact, odds=odds, candidates=candidates, possible=possible)


def holds(ctx, owner: str, tag: str, scheme: str | None = None) -> bool:
    """Whether a planner tag is true of the world for `owner` now (a recorded read)."""
    kind, _, ref = tag.partition(":")
    if kind == "tie":
        return ref in _people_of(ctx, owner)
    if kind == "heard":
        return float(ctx.get(owner, "favour") or 0.0) >= HEARD
    if kind == "favoured":
        return float(ctx.get(owner, "favour") or 0.0) >= FAVOURED
    if kind == "married":
        return ctx.get(owner, "spouse") is not None
    if kind == "dead":
        return ctx.exists(ref) and ctx.status(ref) == "dead"
    if kind == "shamed":  # in disgrace (Shame is how it gets there)
        return ctx.exists(ref) and float(ctx.get(ref, "favour") or 0.0) < SHAMED
    if kind == "accomplice":  # only a scheme has accomplices; a fresh plan recruits first
        return bool(scheme and ctx.get(scheme, "accomplices"))
    return False


def _people_of(ctx, owner: str) -> list[str]:
    """Those the owner could ask: tie partners (not enemies) and the spouse, sorted."""
    out = set()
    for t in ctx.get(owner, "ties") or []:
        if ctx.get(t, "kind") != "enemy":
            out.update({ctx.get(t, "a"), ctx.get(t, "b")})
    spouse = ctx.get(owner, "spouse")
    if spouse:
        out.add(spouse)
    out.discard(owner)
    return sorted(out)
