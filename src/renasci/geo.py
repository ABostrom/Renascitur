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

import copy
import heapq
import json
import math
import re
from dataclasses import dataclass
from pathlib import Path

ID = re.compile(r"[vgt]:[^\s]+")
READS = frozenset({"ids:route", "ends", "days", "open", "kind", "vialux", "barred", "travels", "marks"})
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
        if "barred" in r and not (isinstance(r["barred"], list) and all(map(_str, r["barred"]))):
            out.append(_f("bad_barred", rid, f"{rid}'s barred must be a list of marks (e.g. [\"stained\"])"))
        pair = (*sorted(ends), str(r.get("kind")))
        if pair in pairs:
            out.append(_f("duplicate_route", rid, f"{rid} repeats a {r.get('kind')} between {ends[0]} and {ends[1]}"))
        pairs.add(pair)
    if isinstance(doc, dict):
        out += _check_changes(doc.get("changes"), places, regions, {r.get("id") for r in sections.get("routes", [])})
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


# ------------------------------------------------------------ the map by year (S4 §8, #81)

# A geography's optional `changes`: dated, each one of
#   {"date": [age, year, day], "route": <id>, "open": bool and/or "days": int, "why": str}
#   {"date": ..., "build": <a route record>, "why": ...}
#   {"date": ..., "place": <place id>, "region": <region id>, "why": ...}   (a border moves)
# They happen on their dates in a run (`MapHistory`); the map as of a date is rebuilt from the run's state
# changes (`renasci.analysis.mapyear`), so whatever else changes the map later (a war) shows up too.
CHANGE_KEYS = ("route", "build", "place")


def _check_changes(changes, places, regions, routes) -> list[dict]:
    out: list[dict] = []
    if changes is None:
        return out
    if not isinstance(changes, list):
        return [_f("bad_change", None, "changes must be a list")]
    built = set()
    dated = []
    for i, c in enumerate(changes):
        where = f"change {i + 1}"
        if not isinstance(c, dict):
            out.append(_f("bad_change", None, f"{where} isn't a table"))
            continue
        d = c.get("date")
        if not (isinstance(d, list) and len(d) == 3 and all(type(x) is int for x in d)):
            out.append(_f("bad_change", None, f"{where}'s date must be [age, year, day], not {d!r}"))
            continue
        dated.append((d, i, c))
    for d, i, c in sorted(dated, key=lambda x: (x[0], x[1])):  # (in the order they happen: a road is built first)
        where = f"change {i + 1}"
        if "why" in c and not _str(c["why"]):
            out.append(_f("bad_change", None, f"{where}'s why must be text"))
        what = [k for k in CHANGE_KEYS if k in c]
        if len(what) != 1:
            out.append(_f("bad_change", None, f"{where} needs exactly one of {', '.join(CHANGE_KEYS)}"))
            continue
        if what == ["route"]:
            if c["route"] not in routes | built:
                out.append(_f("bad_change", c["route"], f"{where} changes {c['route']!r}, which isn't a route"))
            if "open" not in c and "days" not in c:
                out.append(_f("bad_change", c["route"], f"{where} must set open or days"))
            if "open" in c and not isinstance(c["open"], bool):
                out.append(_f("bad_change", c["route"], f"{where}'s open must be true or false"))
            if "days" in c and (type(c["days"]) is not int or c["days"] < 1):
                out.append(_f("bad_change", c["route"], f"{where}'s days must be a positive whole number"))
        elif what == ["build"]:
            r = c["build"]
            ok = (isinstance(r, dict) and _str(r.get("id")) and ID.fullmatch(r["id"]) and r["id"] not in routes | built
                  and isinstance(r.get("ends"), list) and len(r["ends"]) == 2 and all(e in places for e in r["ends"])
                  and r["ends"][0] != r["ends"][1] and type(r.get("days")) is int and r["days"] >= 1
                  and r.get("kind") in ROUTE_KINDS)
            if not ok:
                out.append(_f("bad_change", None, f"{where} builds a route that isn't a new route between two places"))
            else:
                built.add(r["id"])
        elif c["place"] not in places or c.get("region") not in regions:
            out.append(_f("bad_change", c.get("place"), f"{where} must move a place into a region"))
    return out


def map_history():
    """The `MapHistory` system class (made on first use: geo itself doesn't need the engine)."""
    from renasci.core.calendar import AgeBoundaryError, Date, Span
    from renasci.core.events import EventType
    from renasci.core.systems import System

    changed = EventType("geo.changed", 1, roles={"site": (1, 2)}, payload={"why": "str", "change": "json"})

    class MapHistory(System):
        """Each of the geography's dated `changes` (the ruleset param `map_changes`) on its date."""

        name, cadence, priority = "geo.map", "seasonal", -5  # (before journeys and people that season)
        reads = frozenset({"ids:route", "ends"})
        writes = frozenset({"new:route", "open", "days", "region"})
        event_types = (changed,)

        def run(self, ctx):
            """This season's changes: today's now, later ones by one follow-up per day (each day's in the
            list's order). The follow-ups are scheduled first, so none is caused by a change made today."""
            try:
                nxt = ctx.calendar.start_of_next(ctx.today, "season")
            except AgeBoundaryError:  # (the age's last season)
                nxt = None
            days: dict = {}
            for i, c in enumerate(ctx.params.get("map_changes") or []):
                when = Date.from_json(c["date"])
                if when == ctx.today or (ctx.today < when and (nxt is None or when < nxt)):
                    days.setdefault(when, []).append(i)
            for when, idx in sorted(days.items()):
                if when != ctx.today:
                    ctx.schedule(Span(days=ctx.calendar.days_between(ctx.today, when)), "map", payload={"i": idx})
            for i in days.get(ctx.today, ()):
                self._apply(ctx, ctx.params["map_changes"][i])

        def handle(self, ctx, activation):
            for i in activation.payload["i"]:
                self._apply(ctx, ctx.params["map_changes"][i])

        def _apply(self, ctx, c):
            why = c.get("why", "")
            if "build" in c:
                r = c["build"]
                ctx.emit("geo.changed", {"site": tuple(r["ends"])}, purpose="map", actor=r["ends"][0],
                         place=r["ends"][0], payload={"why": why, "change": c})
                ctx.create("route", r["id"], {"ends": list(r["ends"]), "days": r["days"], "kind": r["kind"],
                                              "vialux": bool(r.get("vialux", False)), "open": r.get("open", True),
                                              **({"barred": list(r["barred"])} if r.get("barred") else {})})
            elif "route" in c:
                ends = ctx.get(c["route"], "ends")
                ctx.emit("geo.changed", {"site": (c["route"],)}, purpose="map", actor=c["route"], place=ends[0],
                         payload={"why": why, "change": c})
                for f in ("open", "days"):
                    if f in c:
                        ctx.set(c["route"], f, c[f])
            else:
                ctx.emit("geo.changed", {"site": (c["place"],)}, purpose="map", actor=c["place"], place=c["place"],
                         payload={"why": why, "change": c})
                ctx.set(c["place"], "region", c["region"])

    return MapHistory


# ------------------------------------------------------------ routing (S4 §8, #78)

# A route's `days` are days on foot in fair weather, walking by day. With the world param `routing`, a
# traveller's journey is costed by mode, season, the Vialux and their marks; without it (M1) every journey
# takes the file's days. The numbers are a draft (world data: a world's `routing` table overrides them).
ROUTING: dict = {
    "modes": {  # land kinds each mode can take, and the factor on their days (a kind left out: can't)
        "foot": {"road": 1.0, "track": 1.0, "pass": 1.0},
        "horse": {"road": 0.5, "track": 0.6, "pass": 0.8},
        "cart": {"road": 1.2, "track": 1.6},
        "army": {"road": 1.5, "track": 2.0, "pass": 2.5},
    },
    "water": {"river": 1.0, "sea": 1.0},  # by boat: any traveller takes passage
    "seasons": {  # by season name, a factor on a kind's days, or null: closed
        "pass": {"Winter": None, "Spring": 1.5},
        "track": {"Spring": 1.3, "Winter": 1.5},
        "road": {"Winter": 1.2},
        "sea": {"Winter": 1.5},
    },
    "vialux": 0.6,  # lit at night and safe: a day's walk goes on past dusk
    "default_mode": "foot",
}


@dataclass(frozen=True)
class Travel:
    """Who is travelling, how and when: a mode in the routing table, a season name, and the marks they
    carry (a route `barred` to a mark is closed to them)."""

    mode: str
    season: str
    marks: frozenset = frozenset()


def _factor(x, where) -> float | None:
    if x is None:
        return None
    if isinstance(x, bool) or not isinstance(x, (int, float)) or x <= 0:
        raise ValueError(f"routing: {where} must be a positive number or null, not {x!r}")
    return float(x)


def _table(x, where) -> dict:
    if not isinstance(x, dict):
        raise ValueError(f"routing: {where} must be a table, not {x!r}")
    return x


def routing_table(value) -> dict:
    """The routing table for the world param `routing`: true (or an empty table) for the defaults, or a table
    whose entries replace the defaults' by mode, kind or season. In a mode, a kind set to null is one the
    mode can't take. Refused (ValueError) if malformed."""
    if value is True:
        value = {}
    _table(value, "the table")
    unknown = set(value) - set(ROUTING)
    if unknown:
        raise ValueError(f"routing: unknown entries {sorted(unknown)}; known: {sorted(ROUTING)}")
    t = copy.deepcopy(ROUTING)
    for mode, kinds in _table(value.get("modes", {}), "modes").items():
        merged = {**t["modes"].get(mode, {}), **_table(kinds, f"modes.{mode}")}
        t["modes"][mode] = {k: x for k, x in merged.items() if x is not None}
    t["water"].update(_table(value.get("water", {}), "water"))
    for kind, seasons in _table(value.get("seasons", {}), "seasons").items():
        t["seasons"][kind] = {**t["seasons"].get(kind, {}), **_table(seasons, f"seasons.{kind}")}
    t["vialux"] = value.get("vialux", t["vialux"])
    t["default_mode"] = value.get("default_mode", t["default_mode"])
    for kind, x in t["water"].items():
        if kind not in ROUTE_KINDS or _factor(x, f"water.{kind}") is None:
            raise ValueError(f"routing: water.{kind} must be a route kind with a positive factor")
    for mode, kinds in t["modes"].items():
        for kind, x in kinds.items():
            if kind not in ROUTE_KINDS or kind in t["water"]:
                raise ValueError(f"routing: modes.{mode}.{kind} must be a land route kind (water is by boat)")
            _factor(x, f"modes.{mode}.{kind}")
    for kind, seasons in t["seasons"].items():
        if kind not in ROUTE_KINDS:
            raise ValueError(f"routing: seasons.{kind} isn't a route kind")
        for season, x in seasons.items():
            _factor(x, f"seasons.{kind}.{season}")
    if _factor(t["vialux"], "vialux") is None or t["vialux"] > 1:
        raise ValueError("routing: vialux must be a factor in (0, 1]")
    if not isinstance(t["default_mode"], str) or t["default_mode"] not in t["modes"]:
        raise ValueError(f"routing: default_mode {t['default_mode']!r} isn't a mode")
    return t


def cost(route: dict, travel: Travel | None, table: dict | None) -> float | None:
    """A route's days for this traveller (the file's days with no traveller), or None: they can't take it."""
    if route.get("open", True) is False:
        return None
    if travel is None or table is None:
        return route["days"]
    kind = route.get("kind", "road")
    if travel.marks & set(route.get("barred") or ()):
        return None
    if kind in table["water"]:
        x = table["water"][kind]
    else:
        x = (table["modes"].get(travel.mode) or {}).get(kind)
    if x is None:
        return None
    seasons = table["seasons"].get(kind) or {}
    if travel.season in seasons:
        if seasons[travel.season] is None:
            return None
        x *= seasons[travel.season]
    if route.get("vialux") and kind not in table["water"]:  # (the lit road, not the boats)
        x *= table["vialux"]
    return route["days"] * x


# ------------------------------------------------------------ paths


def _adjacency(routes, travel=None, table=None) -> dict[str, list[tuple[str, float]]]:
    adj: dict[str, list[tuple[str, float]]] = {}
    for r in routes:
        d = cost(r, travel, table)
        if d is None:
            continue
        a, b = r["ends"]
        adj.setdefault(a, []).append((b, d))
        adj.setdefault(b, []).append((a, d))
    return adj


def _days(d) -> int:
    """Whole days: part of a day rounds up (a costed path's float, or the file's int unchanged)."""
    return d if isinstance(d, int) else max(1, math.ceil(d - 1e-9)) if d > 0 else 0


def _search(routes, start: str, goal: str | None, max_days: int | None, travel=None, table=None):
    adj, done = _adjacency(routes, travel, table), {}
    heap = [(0, [start])]
    while heap:
        days, path = heapq.heappop(heap)
        at = path[-1]
        if at in done:
            continue
        done[at] = (_days(days), path)
        if at == goal:
            break
        for nxt, d in adj.get(at, ()):
            if nxt not in done and (max_days is None or _days(days + d) <= max_days):
                heapq.heappush(heap, (days + d, path + [nxt]))
    return done


def shortest(routes, a: str, b: str, travel: Travel | None = None,
             table: dict | None = None) -> tuple[int, list[str]] | None:
    """(days, [place ids from a to b]) by the fewest days, or None if there's no way. With a traveller
    and a routing table, by their days (part days round up)."""
    return _search(routes, a, b, None, travel, table).get(b)


def within(routes, a: str, max_days: int | None, travel: Travel | None = None,
           table: dict | None = None) -> dict[str, int]:
    """Every place reachable from `a` in at most `max_days` (any distance if None), with its days."""
    return {p: d for p, (d, _) in _search(routes, a, None, max_days, travel, table).items()}


def _routes(ctx, routed: bool = False) -> list[dict]:
    """The routes as `cost` reads them (their kind, Vialux and bars only when routing: an M1 run reads
    just what it always did)."""
    out = []
    for r in ctx.ids("route"):
        rec = {"ends": ctx.get(r, "ends"), "days": ctx.get(r, "days"), "open": ctx.get(r, "open")}
        if routed:
            rec.update(kind=ctx.get(r, "kind"), vialux=ctx.get(r, "vialux"), barred=ctx.get(r, "barred"))
        out.append(rec)
    return out


def traveller(ctx, who: str | None) -> tuple[Travel | None, dict | None]:
    """How `who` travels today, in a world with `routing` (their `travels` mode, else the table's
    default; their `marks`); (None, None) without routing or a traveller, so the file's days apply."""
    table = ctx.params.get("routing")
    if not table or who is None:
        return None, None
    names = {n for n, _ in ctx.calendar.seasons}
    odd = sorted({s for seasons in table["seasons"].values() for s in seasons} - names)
    if odd:
        raise ValueError(f"routing: seasons {odd} aren't this calendar's ({', '.join(sorted(names))})")
    mode = ctx.get(who, "travels") or table["default_mode"]
    if mode not in table["modes"]:
        raise ValueError(f"{who} travels by {mode!r}, which isn't a mode in the routing table")
    return Travel(mode, ctx.calendar.season_name(ctx.today), frozenset(ctx.get(who, "marks") or ())), table


def path(ctx, a: str, b: str, who: str | None = None) -> tuple[int, list[str]] | None:
    """The way from a to b; for `who` in a world with routing, by how they travel today."""
    travel, table = traveller(ctx, who)
    return shortest(_routes(ctx, travel is not None), a, b, travel, table)


def reach(ctx, a: str, max_days: int | None, who: str | None = None) -> dict[str, int]:
    travel, table = traveller(ctx, who)
    return within(_routes(ctx, travel is not None), a, max_days, travel, table)


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
                                       "vialux": bool(r.get("vialux", False)), "open": r.get("open", True),
                                       **({"barred": list(r["barred"])} if r.get("barred") else {})})
