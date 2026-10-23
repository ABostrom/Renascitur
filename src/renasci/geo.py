"""Geography (S4 spec §2-4): a world's places, regions and routes, and the one way to find a path.

A world's geography is one JSON file: `regions` (`id`, `name`, optional `within`), `places` (`id`,
`name`, `kind`, `region`, optional `at` in map cells, for drawing only) and `routes` (`id`, `ends`,
`days`, `kind`, optional `vialux`). Ids are the vault's (`v:`) or the geography's own (`g:`; `t:` in
test worlds). `check` reports what's wrong as findings, never a crash (errors stop a run; a cut-off settlement
is only a warning), `load` refuses a file with errors, and `save` writes sorted keys with one record per line,
so a diff shows one changed place or route per line.

**Paths** are by `days` over open routes, Dijkstra, ties broken by the smaller list of place ids, so
the same routes always give the same path. `shortest`/`within` work on plain route records; `path`/
`reach` read the cast `route` entities through a `Ctx` (declare `READS`). The graph is small, so the
adjacency is rebuilt on every call.

**In a run** (`cast`): regions become `region` entities, places that aren't settlements `place`
entities and routes `route` entities (`open` as the file says, else true). Settlements are the scenario's to cast:
`check_scenario` makes sure the two agree.
"""

from __future__ import annotations

import heapq
import json
import re
from pathlib import Path

ID = re.compile(r"[vgt]:[^\s]+")
READS = frozenset({"ids:route", "ends", "days", "open"})
ROUTE_KINDS = ("road", "track", "river", "sea", "pass")
FIELDS = {"regions": ("id",), "places": ("id", "kind", "region"), "routes": ("id", "ends", "days", "kind")}


def _f(kind, ident, message, severity="error"):
    return {"kind": kind, "id": ident, "message": message, "severity": severity}


def _records(doc, out) -> dict[str, list[dict]]:
    """Each section's records, once the shapes are right (a bad shape is a finding, not a crash)."""
    if not isinstance(doc, dict):
        out.append(_f("bad_record", None, "a geography is a JSON object"))
        return {}
    sections = {}
    for section in FIELDS:
        value = doc.get(section, [])
        if not isinstance(value, list):
            out.append(_f("bad_record", None, f"{section} must be a list"))
            value = []
        good = []
        for rec in value:
            if isinstance(rec, dict):
                good.append(rec)
            else:
                out.append(_f("bad_record", None, f"{section} has {rec!r}, which isn't an object"))
        sections[section] = good
    return sections


def _str(value) -> bool:
    return isinstance(value, str)


def check(doc: dict) -> list[dict]:
    """Every problem with a geography, errors before the connectedness warning."""
    out: list[dict] = []
    sections = _records(doc, out)
    seen: set[str] = set()
    for section, needed in FIELDS.items():
        for rec in sections.get(section, []):
            ident = rec.get("id")
            for field in needed:
                if field not in rec:
                    out.append(_f("missing_field", ident, f"{section} entry {ident!r} has no {field!r}"))
            if not _str(ident) or not ID.fullmatch(ident):
                out.append(_f("bad_id", None, f"{ident!r} isn't a v:, g: or t: id"))
            elif ident in seen:
                out.append(_f("duplicate_id", ident, f"{ident} is used twice"))
            else:
                seen.add(ident)
    regions = {r["id"]: r for r in sections.get("regions", []) if _str(r.get("id"))}
    places = {p["id"] for p in sections.get("places", []) if _str(p.get("id"))}
    for r in regions.values():
        if r.get("within") is not None and not (_str(r["within"]) and r["within"] in regions):
            out.append(_f("unknown_region", r["id"], f"{r['id']} is within {r['within']!r}, which isn't a region"))
    for r in regions.values():  # follow `within` upward; only a walk back to the start is a cycle
        at, path = r.get("within"), [r["id"]]
        while _str(at) and at in regions and at not in path:
            path.append(at)
            at = regions[at].get("within")
        if at == r["id"]:
            out.append(_f("region_cycle", r["id"], f"{r['id']} is within itself ({' > '.join(path + [at])})"))
    for p in sections.get("places", []):
        if "region" in p and not (_str(p["region"]) and p["region"] in regions):
            out.append(_f("unknown_region", p.get("id"), f"{p.get('id')} is in {p['region']!r}, which isn't a region"))
        if "kind" in p and not _str(p["kind"]):
            out.append(_f("bad_kind", p.get("id"), f"{p.get('id')}'s kind must be a word, not {p['kind']!r}"))
    pairs: set[tuple] = set()
    for r in sections.get("routes", []):
        rid, ends, days = r.get("id"), r.get("ends"), r.get("days")
        if not (isinstance(ends, list) and len(ends) == 2 and all(map(_str, ends))):
            out.append(_f("bad_ends", rid, f"{rid}'s ends must be two place ids"))
            continue
        for end in ends:
            if end not in places:
                out.append(_f("unknown_place", rid, f"{rid} ends at {end!r}, which isn't a place"))
        if ends[0] == ends[1]:
            out.append(_f("self_route", rid, f"{rid} joins {ends[0]} to itself"))
        if "days" in r and (type(days) is not int or days < 1):
            out.append(_f("bad_days", rid, f"{rid}'s days must be a positive whole number, not {days!r}"))
        if "kind" in r and r["kind"] not in ROUTE_KINDS:
            out.append(_f("bad_kind", rid, f"{rid}'s kind must be one of {', '.join(ROUTE_KINDS)}, not {r['kind']!r}"))
        if "open" in r and not isinstance(r["open"], bool):
            out.append(_f("bad_open", rid, f"{rid}'s open must be true or false"))
        pair = (*sorted(ends), str(r.get("kind")))
        if pair in pairs:
            out.append(_f("duplicate_route", rid, f"{rid} repeats a {r.get('kind')} between {ends[0]} and {ends[1]}"))
        pairs.add(pair)
    if out:
        return out
    settlements = sorted(p["id"] for p in sections["places"] if p["kind"] == "settlement")
    if settlements:
        reached = within(sections["routes"], settlements[0], None)
        cut = [s for s in settlements if s not in reached]
        if cut:
            out.append(_f("disconnected", cut[0], f"no route from {settlements[0]} to {', '.join(cut)}", "warning"))
    return out


def _require(doc: dict, where) -> dict:
    bad = [f for f in check(doc) if f["severity"] == "error"]
    if bad:
        raise ValueError(f"{where}: " + "; ".join(f"{f['kind']}: {f['message']}" for f in bad))
    return doc


def load(path) -> dict:
    """A geography file, refused if it has errors."""
    return _require(json.loads(Path(path).read_text(encoding="utf-8")), path)


def dumps(doc: dict) -> str:
    """Sorted keys, two-space indent, one record per line inside each list."""
    def one(value):
        return json.dumps(value, sort_keys=True, ensure_ascii=False)

    parts = []
    for key in sorted(doc):
        value = doc[key]
        if isinstance(value, list) and value:
            body = ",\n".join(f"    {one(v)}" for v in value)
            parts.append(f"  {one(key)}: [\n{body}\n  ]")
        else:
            parts.append(f"  {one(key)}: {one(value)}")
    return "{\n" + ",\n".join(parts) + "\n}\n"


def save(path, doc: dict) -> None:
    Path(path).write_text(dumps(doc), encoding="utf-8", newline="\n")


# ------------------------------------------------------------ paths


def _adjacency(routes) -> dict[str, list[tuple[str, int]]]:
    adj: dict[str, list[tuple[str, int]]] = {}
    for r in routes:
        if r.get("open", True) is False:
            continue
        a, b = r["ends"]
        adj.setdefault(a, []).append((b, r["days"]))
        adj.setdefault(b, []).append((a, r["days"]))
    return adj


def _search(routes, start: str, goal: str | None, max_days: int | None):
    adj, done = _adjacency(routes), {}
    heap = [(0, [start])]
    while heap:
        days, path = heapq.heappop(heap)
        at = path[-1]
        if at in done:
            continue
        done[at] = (days, path)
        if at == goal:
            break
        for nxt, d in adj.get(at, ()):
            if nxt not in done and (max_days is None or days + d <= max_days):
                heapq.heappush(heap, (days + d, path + [nxt]))
    return done


def shortest(routes, a: str, b: str) -> tuple[int, list[str]] | None:
    """(days, [place ids from a to b]) by the fewest days, or None if there's no way."""
    return _search(routes, a, b, None).get(b)


def within(routes, a: str, max_days: int | None) -> dict[str, int]:
    """Every place reachable from `a` in at most `max_days` (any distance if None), with its days."""
    return {p: d for p, (d, _) in _search(routes, a, None, max_days).items()}


def _routes(ctx) -> list[dict]:
    return [{"ends": ctx.get(r, "ends"), "days": ctx.get(r, "days"), "open": ctx.get(r, "open")}
            for r in ctx.ids("route")]


def path(ctx, a: str, b: str) -> tuple[int, list[str]] | None:
    return shortest(_routes(ctx), a, b)


def reach(ctx, a: str, max_days: int | None) -> dict[str, int]:
    return within(_routes(ctx), a, max_days)


# ------------------------------------------------------------ in a run


def check_scenario(scenario: dict, doc: dict) -> list[dict]:
    """A scenario's settlements and the geography's must be the same set, in the same regions."""
    out = []
    ours = {s["id"]: s.get("region") for s in scenario.get("settlements", [])}
    theirs = {p["id"]: p["region"] for p in doc.get("places", []) if p["kind"] == "settlement"}
    if set(ours) != set(theirs):
        missing, extra = sorted(set(theirs) - set(ours)), sorted(set(ours) - set(theirs))
        out.append(_f("settlements_differ", None, f"settlements only in the geography: {missing}; "
                                                   f"only in the scenario: {extra}"))
    for s in sorted(set(ours) & set(theirs)):
        if ours[s] != theirs[s]:
            out.append(_f("region_differs", s, f"{s} is in {ours[s]} in the scenario but {theirs[s]} in the geography"))
    if "regions" in scenario:
        derived: dict[str, list[str]] = {}
        for s, r in sorted(theirs.items()):
            derived.setdefault(r, []).append(s)
        if {r: sorted(v) for r, v in scenario["regions"].items()} != derived:
            out.append(_f("regions_differ", None, "the scenario's regions don't match the geography's settlements"))
    return out


def attach(scenario: dict, base) -> dict:
    """A scenario whose `geography` names a file (relative to `base`) gets the loaded file in its place."""
    if isinstance(scenario.get("geography"), str):
        scenario["geography"] = load(Path(base) / scenario["geography"])
    return scenario


def cast(engine, doc: dict) -> None:
    """Cast regions, non-settlement places and routes (call before the run starts)."""
    for r in doc.get("regions", []):
        engine.cast("region", r["id"], {"name": r.get("name", r["id"]), "within": r.get("within")})
    for p in doc.get("places", []):
        if p["kind"] != "settlement":
            engine.cast("place", p["id"], {"name": p.get("name", p["id"]), "kind": p["kind"], "region": p["region"]})
    for r in doc.get("routes", []):
        engine.cast("route", r["id"], {"ends": list(r["ends"]), "days": r["days"], "kind": r["kind"],
                                       "vialux": bool(r.get("vialux", False)), "open": r.get("open", True)})
