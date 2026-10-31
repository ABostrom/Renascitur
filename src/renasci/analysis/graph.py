"""The possible graph: what can lead to what, across all runs (#162, vision spec §7).

A run's `CauseIndex` says what did cause what. This says what could, read from what the code declares. Strict mode
holds reads, writes and emits to their declarations; `feeds` is hand-written, so the engine records what each system
really touched (`Engine.fed`) and a test holds them together:

- **influence** (implicit): a system writes a field and another reads it; a system moves a stock (`System.feeds`) and
  another uses it (`System.uses`), or a mark needs it. These are the emergent routes: nothing names what it reaches.
- **emit** (implicit): a system to the event types it declares.
- **plan** (implicit): an action requires a goal, and achieves one.
- **trigger** (implicit): a reaction, from the event it answers to the events it emits.
- **explicit:** `Link`s, authored for what code can't show (the `links` pool). They describe; they change nothing. To
  drive behaviour, write a reaction.

Fields many systems touch (`COMMON`) join everything to everything, so they're left out unless asked for. Most wildcard
declarations name no one field and are left out; the masses and goods (`pop:*`, `stock:*`, `goods:*`) are one node each.
An event has no edges out of its own, so a route from one starts from what emits it. A route is what's possible, not
how likely: `overlay` adds what a run actually did, by direct cause only.

Nodes are `kind:name`: `system:ecology.famine`, `event:famine.began`, `field:hunger`, `stock:corpses`, `action:Flee`,
`goal:safe`, `mark:haunted`, `reaction:mourn`.
"""

from __future__ import annotations

from collections import Counter, deque
from dataclasses import dataclass

COMMON = frozenset({"status", "residents", "place", "born", "name", "kind", "house", "ids", "race", "sex", "job",
                    "spouse", "children", "father", "mother", "region", "owner", "holder", "offices", "ties", "a", "b",
                    "journey", "state", "class", "target", "ended", "members", "seat", "headship", "cooldowns", "rule", "ambitions", "scheme",
                    "ruler", "control", "ends", "beliefs", "grievances", "ledger", "heir", "extinct", "deposed", "need",
                    "exploits", "legitimacy"})
GROUPED = ("pop:*", "stock:*", "goods:*")  # (wildcards that are one thing to the reader)


@dataclass(frozen=True)
class Link:
    """An authored link: `cause` and `effect` are nodes, or bare event types. It describes, and changes nothing."""

    cause: str
    effect: str
    why: str = ""
    weight: float | None = None

    @property
    def name(self) -> str:
        return f"{self.cause} -> {self.effect}"


@dataclass(frozen=True)
class Edge:
    a: str
    b: str
    kind: str
    origin: str = "code"
    why: str = ""
    weight: float | None = None


def node(text: str) -> str:
    return text if ":" in text.split(".")[0] else f"event:{text}"


def _tag(tag: str) -> str:
    return tag.split(":")[0]


def build(rulesets, pools, include_common: bool = False) -> list[Edge]:
    edges: set[Edge] = set()

    def field(name: str) -> str | None:
        if name in GROUPED:
            return f"field:{name[:-2]}"
        if name.endswith("*") or name.startswith(("ids:", "new:")) or (name in COMMON and not include_common):
            return None
        return f"field:{name}"

    for rs in rulesets:
        for s in (*rs.systems, *rs.disguises, *rs.forcers):
            me = f"system:{s.name}"
            for t in s.event_types:
                edges.add(Edge(me, f"event:{t.name}", "emit"))
            for f in filter(None, map(field, s.writes)):
                edges.add(Edge(me, f, "influence"))
            for f in filter(None, map(field, s.reads)):
                edges.add(Edge(f, me, "influence"))
            for name in getattr(s, "feeds", ()):
                edges.add(Edge(me, f"stock:{name}", "influence"))
            for name in getattr(s, "uses", ()):
                edges.add(Edge(f"stock:{name}", me, "influence"))
    entries = lambda pool: pools[pool].items() if pool in pools else ()  # noqa: E731
    for _, action in entries("actions"):
        me = f"action:{action.name}"
        for tag in action.requires:
            edges.add(Edge(f"goal:{_tag(tag)}", me, "plan"))
        if action.achieves:
            edges.add(Edge(me, f"goal:{_tag(action.achieves)}", "plan"))
    for key, mark in entries("marks"):
        me = f"mark:{key}"
        for need in mark.needs:
            edges.add(Edge({"fame": "field:fame", "skill": "field:skills"}.get(need, f"stock:{need}"), me, "influence"))
        for name in mark.gives:
            edges.add(Edge(me, "field:traits" if "person" in mark.fits else f"field:{name}", "influence"))
    for key, r in entries("reactions"):
        me = f"reaction:{key}"
        edges.add(Edge(f"event:{r.on}", me, "trigger", pools.reactions.sources()[key]))
        for t in r.emits:
            edges.add(Edge(me, f"event:{t}", "trigger", pools.reactions.sources()[key]))
    for key, link in entries("links"):
        edges.add(Edge(node(link.cause), node(link.effect), "explicit", pools.links.sources()[key], link.why, link.weight))
    return sorted(edges, key=lambda e: (e.a, e.b, e.kind))


def route(edges: list[Edge], start: str, goal: str, kinds=None) -> list[Edge] | None:
    """A shortest way from one node to another, by `kinds` of edge if given."""
    out: dict[str, list[Edge]] = {}
    for e in edges:
        if kinds is None or e.kind in kinds:
            out.setdefault(e.a, []).append(e)
    came: dict[str, Edge] = {}
    seeds = [start]
    if start.startswith("event:") and start not in out:  # (an event happens where what emits it is)
        seeds += [e.a for e in edges if e.b == start and e.kind == "emit"]
    todo, seen = deque(seeds), set(seeds)
    while todo:
        at = todo.popleft()
        if at == goal:
            path = []
            while at not in seeds:
                path.append(came[at])
                at = came[at].a
            return path[::-1]
        for e in out.get(at, ()):
            if e.b not in seen:
                seen.add(e.b)
                came[e.b] = e
                todo.append(e.b)
    return None


def emergent(edges: list[Edge], start: str, goal: str) -> list[Edge] | None:
    """A way that nothing authored: through what systems share."""
    return route(edges, start, goal, {"influence", "emit"})


def check(edges: list[Edge], facts=()) -> dict:
    """What looks wrong: goals neither an action nor the world (`facts`, the `goals` pool) can make true, and links with
    nothing behind them."""
    made = {e.b for e in edges if e.kind == "plan" and e.a.startswith("action:")}
    needed = {e.a for e in edges if e.kind == "plan" and e.a.startswith("goal:")}
    known = {e.a for e in edges if e.kind != "explicit"} | {e.b for e in edges if e.kind != "explicit"}
    implicit = [e for e in edges if e.kind != "explicit"]
    worldly = {f"goal:{g}" for g in facts}
    problems = {"goals_nothing_achieves": sorted(needed - made - worldly), "links_to_nothing": [], "links_without_a_route": []}
    for e in edges:
        if e.kind == "explicit":
            if e.a not in known or e.b not in known:
                problems["links_to_nothing"].append(f"{e.a} -> {e.b}")
            elif route(implicit, e.a, e.b) is None:
                problems["links_without_a_route"].append(f"{e.a} -> {e.b}")
    return problems


def overlay(rows, edges: list[Edge]) -> dict:
    """What a run did: how often one event type caused another, and which links never showed. `rows` are event rows."""
    rows = list(rows)
    types = {r["id"]: r["type"] for r in rows}
    fired: Counter = Counter()
    for r in rows:
        for kind, ref in r.get("causes") or []:
            if kind == "event" and ref in types:
                fired[(types[ref], r["type"])] += 1
    links = [(e.a, e.b) for e in edges if e.kind == "explicit" and e.a.startswith("event:") and e.b.startswith("event:")]
    return {"fired": [{"cause": a, "effect": b, "count": n} for (a, b), n in sorted(fired.items())],
            "links_never_seen": [f"{a} -> {b}" for a, b in links if not fired.get((a[6:], b[6:]))]}


def text(path: list[Edge]) -> str:
    return "\n".join(f"{e.a}  --{e.kind}-->  {e.b}" for e in path)
