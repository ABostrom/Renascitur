"""The story finder (S7 spec §9): arcs from ambitions, sagas from the arcs that touch directly.

**Arcs.** One per ambition: how it was born (`formed_by`), its **beats** (every event caused by the
ambition or one of its schemes, or naming it), its outcome and its span in years. **Salience** comes
from the class's stakes, violent beats (a death, a blow struck), the people touched and the owner's
standing in their house.

**Sagas.** A weighted graph of arcs, with *direct* links only (long cause chains reach nearly everyone
within a century, master §5.2):

| Link | Weight |
|---|---|
| one arc's target is the other's owner | 3 |
| a shared beat | 2 |
| a direct cause edge between their beats | 1 |

Sagas are the components over links of weight 2 or more, of at least two arcs. A component that is too
big (more than `MAX_ARCS` arcs or `MAX_PEOPLE` people), or that would **swallow a house** (arcs owned by
more than half of a house's notables alive in its span, for a house with 4+ arcs), is split: the weakest
links go first; among equally weak links, the one between arcs furthest apart in years (a generation
apart before a decade apart), then the one that splits most evenly (`partition`). A saga takes the title of its most salient arc.

**Titles** come from per-class templates (`TITLES`, data); an arc whose blow killed someone is named
for the killing. `period(found, lo, hi)` answers "what flows through these years".

Pure: `stories(events, state)` takes the run's events and final state and returns JSON-ready data;
`renasci stories <run>` writes `analysis/stories.json`.
"""

from __future__ import annotations

STAKES = {"Seize": 3.0, "Vengeance": 2.0, "Protect": 2.0, "Standing": 1.5, "Marry": 1.0}
MAX_ARCS, MAX_PEOPLE = 12, 40
HOUSE_ARCS = 4  # a house with this many arcs is protected from being swallowed
KILLS = {"Poison": "poisoning", "Assassinate": "murder", "Duel": "fatal duel"}
TITLES = {
    "Marry": {"fulfilled": "The marriage of {owner}", "*": "{owner}'s courtship"},
    "Standing": {"fulfilled": "The rise of {owner} at court", "*": "{owner}'s bid for favour"},
    "Seize": {"fulfilled": "How {owner} took the seat of House {house}", "*": "{owner}'s plot for the seat of House {house}"},
    "Vengeance": {"fulfilled": "{owner}'s revenge on {target}", "*": "{owner}'s long revenge"},
    "Protect": {"*": "{owner} stands guard against {target}"},
    "*": {"*": "The {class} of {owner}"},
}


def stories(events: list[dict], state: dict) -> dict:
    """Arcs and sagas (JSON-ready, deterministic)."""
    ents = {e["id"]: e for e in state["entities"]}

    def get(entity, name):
        return (ents.get(entity) or {}).get("fields", {}).get(name)

    def kind(entity):
        return (ents.get(entity) or {}).get("kind")

    def full(person):
        if not person:
            return "someone"
        name = get(person, "name") or person
        house = get(person, "house")
        return f"{name} of House {get(house, 'name') or house}" if house else name

    by_id = {ev["id"]: ev for ev in events}
    schemes_of: dict[str, list[str]] = {}
    for e in state["entities"]:
        if e["kind"] == "scheme":
            schemes_of.setdefault(e["fields"]["ambition"], []).append(e["id"])
    owner_of_cause: dict[tuple, str] = {}
    for amb in (e["id"] for e in state["entities"] if e["kind"] == "ambition"):
        owner_of_cause[("ambition", amb)] = amb
        for s in schemes_of.get(amb, []):
            owner_of_cause[("scheme", s)] = amb

    beats: dict[str, list[str]] = {}
    for ev in events:
        mine = {owner_of_cause[tuple(c)] for c in ev["causes"] if tuple(c) in owner_of_cause}
        for members in ev["roles"].values():
            mine |= {m for m in members if kind(m) == "ambition"}
        for amb in mine:
            beats.setdefault(amb, []).append(ev["id"])

    def key(eid):
        return tuple(by_id[eid]["date"]), eid

    deaths = {ev["roles"]["deceased"][0]: ev for ev in events if ev["type"] == "people.death"}
    arcs = []
    for amb in sorted(e["id"] for e in state["entities"] if e["kind"] == "ambition"):
        mine = sorted(set(beats.get(amb, [])), key=key)
        formed = next((b for b in mine if by_id[b]["type"] == "people.ambition_formed"), None)
        if formed is not None:  # the formation leads
            mine = [formed] + [b for b in mine if b != formed]
        people = sorted({m for b in mine for ms in by_id[b]["roles"].values() for m in ms if kind(m) == "person"})
        violent, killed, struck = 0, None, set()
        for b in mine:
            ev = by_id[b]
            if ev["type"] == "people.action" and ev["payload"]["action"] in KILLS \
                    and ev["payload"]["outcome"] == "success":
                violent += 1  # a blow struck (a guarded target may yet live)
                struck.add(b)
                victim = (ev["roles"].get("target") or [None])[0]
                death = deaths.get(victim)
                if killed is None and death is not None and any(tuple(c) == ("event", b) for c in death["causes"]):
                    killed = (ev["payload"]["action"], victim)  # and the death names it
        for b in mine:  # deaths the arc led to by other means (a lost duel, the line delivering)
            ev = by_id[b]
            if ev["type"] == "people.death" and not any(c[0] == "event" and c[1] in struck for c in ev["causes"]):
                violent += 1
        owner, cls, state_ = get(amb, "owner"), get(amb, "class"), get(amb, "state")
        house = get(owner, "house")
        head = house and get(get(house, "headship"), "holder") == owner
        years = [by_id[b]["date"][1] for b in mine] or [get(amb, "formed")[1]]
        resolved = get(amb, "resolved")
        span = [get(amb, "formed")[1], max(years + ([resolved[0][1]] if resolved else []))]
        salience = STAKES.get(cls, 1.0) + 2.0 * violent + 0.1 * len(people) + (1.0 if head else 0.5 if house else 0.0)
        if killed:
            title = f"The {KILLS[killed[0]]} of {full(killed[1])}"
        else:
            templates = TITLES.get(cls, TITLES["*"])
            template = templates.get(state_, templates["*"])
            title = template.format(owner=full(owner), target=full(get(amb, "target")),
                                    house=get(house, "name") or house or "?", **{"class": cls})
        target = get(amb, "target")
        timeline = [{"event": b, "date": by_id[b]["date"], "type": by_id[b]["type"],
                     "turn": _turn(by_id[b], full, deaths)} for b in mine]
        progress = [{"scheme": sc, "state": get(sc, "state"), "step": get(sc, "step"), "steps": len(get(sc, "plan") or []),
                     "plan": [st["action"] for st in get(sc, "plan") or []]} for sc in sorted(schemes_of.get(amb, []))]
        arcs.append({"id": f"arc:{amb}", "ambition": amb, "owner": owner, "class": cls, "target": target,
                     "owner_name": full(owner), "target_name": full(target) if target else None,
                     "house": house, "house_name": get(house, "name") if house else None,
                     "outcome": state_, "born_of": get(amb, "born_of"), "formed_by": formed or (mine[0] if mine else None),
                     "beats": mine, "timeline": timeline, "schemes": sorted(schemes_of.get(amb, [])), "progress": progress,
                     "people": people, "span": span, "violent": violent, "salience": round(salience, 6), "title": title})

    return {"arcs": arcs, "sagas": _sagas(arcs, by_id, ents, deaths)}


def _turn(ev: dict, full, deaths) -> str | None:
    """A beat's line on the story river, if it is a turning point (a killing, a death, an exposure, a seat
    changing hands, the end)."""
    t, roles, pay = ev["type"], ev["roles"], ev["payload"]
    if t == "people.action" and pay["action"] in KILLS and pay["outcome"] == "success":
        victim = (roles.get("target") or [None])[0]
        died = victim in deaths and any(tuple(c) == ("event", ev["id"]) for c in deaths[victim]["causes"])
        return f"{pay['action']} on {full(victim)}" + ("" if died else " (survived)")
    if t == "people.death":
        return f"{full(roles['deceased'][0])} dies ({pay['cause']})"
    if t == "people.scheme_exposed":
        return "the plot is exposed"
    if t == "people.succession":
        return f"{full(roles['successor'][0])} takes the seat"
    if t == "people.ambition_resolved":
        return pay["status"].replace("_", " ")
    return None


def _sagas(arcs, by_id, ents, deaths) -> list[dict]:
    by_arc = {a["id"]: a for a in arcs}
    owned: dict[str, list[str]] = {}
    beat_of: dict[str, list[str]] = {}
    for a in arcs:
        owned.setdefault(a["owner"], []).append(a["id"])
        for b in a["beats"]:
            beat_of.setdefault(b, []).append(a["id"])
    edges: dict[tuple, int] = {}

    def link(x, y, w):
        if x != y:
            k = (min(x, y), max(x, y))
            edges[k] = edges.get(k, 0) + w

    for a in arcs:
        for other in owned.get(a["target"], []) if a["target"] else []:
            link(a["id"], other, 3)
    for b, holders in beat_of.items():
        for i, x in enumerate(holders):
            for y in holders[i + 1:]:
                link(x, y, 2)
    for b, holders in beat_of.items():  # a beat caused directly by another arc's beat
        for c in by_id[b]["causes"]:
            if c[0] == "event" and c[1] in beat_of:
                for x in holders:
                    for y in beat_of[c[1]]:
                        link(x, y, 1)

    strong = {k: w for k, w in edges.items() if w >= 2}
    houses: dict[str, list[str]] = {}
    for eid, e in ents.items():
        if e["kind"] == "person" and e["fields"].get("house"):
            houses.setdefault(e["fields"]["house"], []).append(eid)
    guarded = {h: ms for h, ms in houses.items() if sum(len(owned.get(m, [])) for m in ms) >= HOUSE_ARCS}

    def span(part):
        return min(by_arc[a]["span"][0] for a in part), max(by_arc[a]["span"][1] for a in part)

    def people(part):
        return sorted({p for a in part for p in by_arc[a]["people"]})

    def fits(part):
        if len(part) > MAX_ARCS or len(people(part)) > MAX_PEOPLE:
            return False
        lo, hi = span(part)
        owners = {by_arc[a]["owner"] for a in part}
        for members in guarded.values():
            alive = [p for p in members if (ents[p]["fields"].get("born") or [0, hi + 1])[1] <= hi
                     and (deaths[p]["date"][1] >= lo if p in deaths else ents[p]["status"] != "dead")]
            if len(owners & set(members)) > len(alive) / 2:
                return False
        return True

    def gap(edge):
        (a0, a1), (b0, b1) = by_arc[edge[0]]["span"], by_arc[edge[1]]["span"]
        return max(0, max(a0, b0) - min(a1, b1))

    nodes = sorted({n for k in strong for n in k})
    sagas = []
    for part in partition(nodes, strong, fits, gap=gap):
        if len(part) < 2:
            continue
        lead = max((by_arc[a] for a in part), key=lambda a: (a["salience"], a["id"]))
        sagas.append({"id": f"saga:{lead['ambition']}", "arcs": sorted(part), "people": people(part),
                      "span": list(span(part)), "salience": round(sum(by_arc[a]["salience"] for a in part), 6),
                      "title": lead["title"]})
    sagas.sort(key=lambda s: (-s["salience"], s["id"]))
    return sagas


def _components(nodes, edges) -> list[list[str]]:
    adj = {n: set() for n in nodes}
    for a, b in edges:
        adj[a].add(b)
        adj[b].add(a)
    seen, out = set(), []
    for n in sorted(nodes):
        if n in seen:
            continue
        stack, comp = [n], []
        seen.add(n)
        while stack:
            x = stack.pop()
            comp.append(x)
            for y in sorted(adj[x] - seen):
                seen.add(y)
                stack.append(y)
        out.append(sorted(comp))
    return out


def _bridges(part: list[str], edges) -> dict[tuple, int]:
    """For each bridge of the connected `part`, the size of the smaller side its removal leaves."""
    adj = {n: [] for n in part}
    for a, b in sorted(edges):
        adj[a].append(b)
        adj[b].append(a)
    root = part[0]
    order, low, size, parent = {root: 0}, {root: 0}, {root: 1}, {root: None}
    stack, out, n = [(root, iter(adj[root]))], {}, len(part)
    while stack:  # (iterative DFS: Tarjan's bridges, with subtree sizes)
        x, it = stack[-1]
        y = next(it, None)
        if y is None:
            stack.pop()
            p = parent[x]
            if p is not None:
                low[p] = min(low[p], low[x])
                size[p] += size[x]
                if low[x] > order[p]:
                    out[(min(p, x), max(p, x))] = min(size[x], n - size[x])
            continue
        if y not in order:
            order[y] = low[y] = len(order)
            size[y], parent[y] = 1, x
            stack.append((y, iter(adj[y])))
        elif y != parent[x]:
            low[x] = min(low[x], order[y])
    return out


def _split_edges(parts, edges):
    """Each part with the edges inside it."""
    where = {n: i for i, part in enumerate(parts) for n in part}
    inside = [{} for _ in parts]
    for k, w in edges.items():
        inside[where[k[0]]][k] = w
    return list(zip(parts, inside))


def partition(nodes, edges: dict[tuple, int], fits, gap=None) -> list[list[str]]:
    """Components of `nodes` over `edges`, each split until `fits(part)`: remove the weakest link (among
    those, the one with the widest `gap` in years, then the one that splits most evenly, then by id) and
    look again."""
    gap = gap or (lambda e: 0)
    out = []
    todo = _split_edges(_components(nodes, edges), edges)
    while todo:
        part, inside = todo.pop(0)
        if len(part) == 1 or fits(part):
            out.append(part)
            continue
        weakest = min(inside.values())
        split = _bridges(part, inside)
        k = min((e for e, w in inside.items() if w == weakest), key=lambda e: (-gap(e), -split.get(e, 0), e))
        del inside[k]
        if k in split:  # the part falls in two
            todo = _split_edges(_components(part, inside), inside) + todo
        else:
            todo.insert(0, (part, inside))
    return sorted(out)


def period(found: dict, lo: int, hi: int) -> dict:
    """The arcs and sagas active in years `lo`..`hi`, most salient first."""
    def active(x):
        return x["span"][0] <= hi and x["span"][1] >= lo

    return {"arcs": sorted((a for a in found["arcs"] if active(a)), key=lambda a: (-a["salience"], a["id"])),
            "sagas": [s for s in found["sagas"] if active(s)]}
