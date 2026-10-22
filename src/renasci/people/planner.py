"""The planner (S7 spec §5): from an ambition's subgoals to a scheme's plan.

**Backward chaining** over the action library. A goal is a set of tags; a tag that is already a
**fact** needs nothing. For the first unmet tag (in sorted order), try each action (in name order)
whose `achieves` matches it, binding `{target}` from the tag ("dead:{target}" matches "dead:t:Arn") or,
for an action that only needs someone (`Recruit`: "tie:{target}"), from the accomplice **candidates**.
Its `requires` become subgoals, solved first; then the rest of the goal, with what the plan has
achieved so far counted as true.

- **Bounded:** at most `depth` steps (`2 + round(3 * wits)` for a schemer).
- **Cheapest:** cost is the sum over steps of `1/odds + secrecy`; ties break on the plan's canonical
  `(action, target)` steps. No draws: the same world gives the same plan.
- **Plans are data** (`Plan.to_json`), stored on the scheme record, replayable and explainable.

`plan(goals, actions, depth, fact, odds, candidates)` is pure: the world comes in as three functions.
`plan_for(ctx, owner, goals, scheme)` binds them to the simulation (recorded reads, through `Ctx`).
"""

from __future__ import annotations

from dataclasses import dataclass

from renasci.people.actions import ACTIONS, FAVOURED, HEARD
from renasci.people.ambitions import trait

EPS = 1e-9


@dataclass(frozen=True)
class Plan:
    steps: tuple  # ({"action": name, "target": id or None}, ...)

    def to_json(self) -> dict:
        return {"steps": [dict(s) for s in self.steps]}

    @classmethod
    def from_json(cls, data: dict) -> Plan:
        return cls(tuple(dict(s) for s in data["steps"]))


def _key(steps) -> tuple:
    return tuple((s["action"], s["target"] or "") for s in steps)


def _bind(pattern: str, tag: str):
    """The target that makes `pattern` read `tag`: ("", True) without a {target}; (None, False) if it can't."""
    if "{target}" not in pattern:
        return ("", pattern == tag)
    head, tail = pattern.split("{target}", 1)
    if tag.startswith(head) and tag.endswith(tail) and len(tag) > len(head) + len(tail):
        return (tag[len(head):len(tag) - len(tail)] if tail else tag[len(head):], True)
    return (None, False)


def cost(plan_: Plan, actions, odds) -> float:
    return sum(1.0 / max(odds(actions[s["action"]], s["target"]), 1e-3) + actions[s["action"]].secrecy
               for s in plan_.steps)


def plan(goals, *, actions=None, depth: int, fact, odds, candidates) -> Plan | None:
    """The cheapest plan reaching any one of `goals` (tag sets) in at most `depth` steps, or None."""
    actions = actions if actions is not None else ACTIONS
    names = sorted(actions)
    best = None
    for goal in sorted(goals, key=lambda g: tuple(sorted(g))):
        found = _solve(frozenset(goal), frozenset(), depth, actions, names, fact, odds, candidates,
                       exclude=frozenset(t.split(":", 1)[1] for t in goal if ":" in t))
        if found is not None and (best is None or (round(found[0], 9), _key(found[1])) < (round(best[0], 9), _key(best[1]))):
            best = found
    return None if best is None else Plan(best[1])


def _solve(goal, have, depth, actions, names, fact, odds, candidates, exclude):
    unmet = sorted(t for t in goal if t not in have and not fact(t))
    if not unmet:
        return (0.0, ())
    if depth <= 0:
        return None
    tag = unmet[0]
    best = None
    for name in names:
        action = actions[name]
        target, ok = _bind(action.achieves, tag)
        if not ok:
            continue
        if target == "" and any("{target}" in r for r in action.requires):
            targets = [c for c in candidates(exclude) if c not in exclude]  # someone to act on (an accomplice)
        else:
            targets = [target or None]
        for t in targets:
            requires = frozenset(r.replace("{target}", t) if t else r for r in action.requires)
            first = _solve(requires, have, depth - 1, actions, names, fact, odds, candidates, exclude)
            if first is None:
                continue
            step = {"action": name, "target": t}
            gained = have | {tag} | {_achieved(actions, s) for s in first[1]}
            rest = _solve(goal, gained, depth - 1 - len(first[1]), actions, names, fact, odds, candidates, exclude)
            if rest is None:
                continue
            here = 1.0 / max(odds(action, t), 1e-3) + action.secrecy
            total = first[0] + here + rest[0]
            steps = first[1] + (step,) + rest[1]
            if best is None or (round(total, 9), _key(steps)) < (round(best[0], 9), _key(best[1])):
                best = (total, steps)
    return best


def _achieved(actions, step) -> str:
    a = actions[step["action"]]
    return a.achieves.replace("{target}", step["target"]) if step["target"] and "{target}" in a.achieves else a.achieves


# ---------------------------------------------------------------- bound to the simulation


def plan_for(ctx, owner: str, goals, scheme: str | None = None) -> Plan | None:
    """A plan for `owner`, reading the world through `ctx` (every fact is a recorded read)."""

    def fact(tag: str) -> bool:
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
        if kind == "shamed":
            return ctx.exists(ref) and float(ctx.get(ref, "favour") or 0.0) < 0
        if kind == "accomplice":
            return bool(scheme and ctx.get(scheme, "accomplices"))
        return False

    def odds(action, target) -> float:
        return action.odds(ctx, owner, target, scheme)

    def candidates(exclude) -> list[str]:
        return [p for p in _people_of(ctx, owner) if p not in exclude and ctx.status(p) == "active"]

    depth = 2 + round(3 * trait(ctx, owner, "wits"))
    return plan(goals, depth=depth, fact=fact, odds=odds, candidates=candidates)


def _people_of(ctx, owner: str) -> list[str]:
    """Those the owner could ask: tie partners and the spouse, sorted."""
    out = set()
    for t in ctx.get(owner, "ties") or []:
        out.update({ctx.get(t, "a"), ctx.get(t, "b")})
    spouse = ctx.get(owner, "spouse")
    if spouse:
        out.add(spouse)
    out.discard(owner)
    return sorted(out)
