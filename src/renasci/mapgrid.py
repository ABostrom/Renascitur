"""The cell grid (S5 spec §3, #80): a world's map as 24-mile hexes, private, baked into its geography.

**Cells** are pointy-top hexes in odd-r offset rows (odd rows shifted half a cell right), `miles` across
their flats (24). Ids are `c:<col>,<row>`; neighbours come from the id, so adjacency is never stored. A
cell's centre, in miles from the map's top-left, is `centre(cell, miles)`; `at(x, y, grid)` is the cell
under a point.

**`grid.json`** (in the world's git-ignored `maps/<world>/private/`, like everything traced from the
private map): `{cols, rows, miles, days_per_cell, terrain: {kind: cost or null}, cells: {id: {terrain?,
region?}}}`. Only painted cells are listed; an unpainted cell is `plains` with no region. Water from the
import's mask is painted when the grid is made (`new_grid(..., land=mask)`).

**`layout.json`** (private too): `{places: {id: {cell, at?}}, routes: {id: {cells: [...]}}}`: where each
place stands and which cells each route crosses.

**Baking** (`bake`) is what reaches git: a land route's days are its cells' (each step the mean of the two
cells' costs, times days per cell, rounded up, at least 1); a sea or river route keeps its typed days (its
path is drawn, not walked); a place on a cell with a region takes that region. The baked geography has
no cells and no positions: the S4 file the sim already reads.
"""

from __future__ import annotations

import copy
import math

from renasci.geo import _f

TERRAIN = {"plains": 1.0, "forest": 1.5, "hills": 2.0, "mountains": 4.0, "marsh": 2.5, "desert": 1.8, "water": None}
MILES = 24
DAYS_PER_CELL = 1.2  # (24 miles at about 20 miles a day on foot; Q1)
ROW_MILES = MILES * math.sqrt(3) / 2  # (the distance between rows, for 24-mile cells)
WATER_KINDS = ("sea", "river")  # (routes whose path is drawn, not walked: their days are typed)


# ------------------------------------------------------------ cells


def cell(col: int, row: int) -> str:
    return f"c:{col},{row}"


def parse(cid: str) -> tuple[int, int]:
    col, row = cid[2:].split(",")
    return int(col), int(row)


def inside(col: int, row: int, grid: dict) -> bool:
    return 0 <= col < grid["cols"] and 0 <= row < grid["rows"]


def known(cid, grid: dict) -> bool:
    try:
        return isinstance(cid, str) and cid.startswith("c:") and inside(*parse(cid), grid)
    except ValueError:
        return False


def cells(grid: dict):
    return (cell(c, r) for r in range(grid["rows"]) for c in range(grid["cols"]))


_EVEN = ((1, 0), (-1, 0), (-1, -1), (0, -1), (-1, 1), (0, 1))
_ODD = ((1, 0), (-1, 0), (0, -1), (1, -1), (0, 1), (1, 1))


def near(cid: str, grid: dict) -> list[str]:
    col, row = parse(cid)
    return [cell(col + dc, row + dr) for dc, dr in (_ODD if row & 1 else _EVEN) if inside(col + dc, row + dr, grid)]


def centre(cid: str, miles: float = MILES) -> tuple[float, float]:
    col, row = parse(cid)
    radius = miles / math.sqrt(3)
    return miles * (col + 0.5 + 0.5 * (row & 1)), radius + row * 1.5 * radius


def _cube_round(q: float, r: float) -> tuple[int, int]:
    s = -q - r
    rq, rr, rs = round(q), round(r), round(s)
    dq, dr, ds = abs(rq - q), abs(rr - r), abs(rs - s)
    if dq > dr and dq > ds:
        rq = -rr - rs
    elif dr > ds:
        rr = -rq - rs
    return rq, rr


def _axial(col: int, row: int) -> tuple[int, int]:
    return col - (row - (row & 1)) // 2, row


def _offset(q: int, r: int) -> tuple[int, int]:
    return q + (r - (r & 1)) // 2, r


def at(x: float, y: float, grid: dict, as_tuple: bool = False):
    """The cell under a point (miles from the map's top-left), clamped to the grid."""
    miles = grid["miles"]
    radius = miles / math.sqrt(3)
    x0, y0 = x - miles / 2, y - radius
    q, r = _cube_round((math.sqrt(3) / 3 * x0 - y0 / 3) / radius, (2 / 3 * y0) / radius)
    col, row = _offset(q, r)
    col, row = min(max(col, 0), grid["cols"] - 1), min(max(row, 0), grid["rows"] - 1)
    return (col, row) if as_tuple else cell(col, row)


def line(a: str, b: str, grid: dict | None = None) -> list[str]:
    """The cells on a straight line from a to b (each next to the one before). A tie between two cells is
    nudged one way, or (with `grid`) the other when the first would leave the grid."""
    (qa, ra), (qb, rb) = _axial(*parse(a)), _axial(*parse(b))
    n = max(abs(qa - qb), abs(ra - rb), abs((qa + ra) - (qb + rb)))
    out = []
    for i in range(n + 1):
        t = i / n if n else 0.0
        for nudge in (1e-6, -1e-6):
            q, r = _cube_round(qa + (qb - qa) * t + nudge, ra + (rb - ra) * t + nudge)
            c = cell(*_offset(q, r))
            if grid is None or known(c, grid):
                break
        if not out or out[-1] != c:
            out.append(c)
    return out


def walk(a: str, b: str, grid: dict) -> list[str] | None:
    """The fewest-cells path from a to b over cells a road can cross (breadth first, neighbours in id
    order, so the same map always gives the same path); None if the water cuts them off."""
    if grid["terrain"].get(terrain(a, grid)) is None or grid["terrain"].get(terrain(b, grid)) is None:
        return None
    came = {a: None}
    frontier = [a]
    while frontier and b not in came:
        nxt = []
        for c in frontier:
            for n in sorted(near(c, grid), key=parse):
                if n not in came and grid["terrain"].get(terrain(n, grid)) is not None:
                    came[n] = c
                    nxt.append(n)
        frontier = nxt
    if b not in came:
        return None
    path = [b]
    while path[-1] != a:
        path.append(came[path[-1]])
    return path[::-1]


# ------------------------------------------------------------ the grid


def new_grid(miles_across: float, aspect: float, miles: int = MILES, land=None) -> dict:
    """A grid covering a map `miles_across` wide and `aspect` (height / width) tall. With `land` (the
    import's mask as a boolean array, True for land), every cell whose centre is on water is painted water."""
    row_miles = miles * math.sqrt(3) / 2
    g = {"cols": math.ceil(miles_across / miles), "rows": math.ceil(miles_across * aspect / row_miles), "miles": miles,
         "days_per_cell": round(DAYS_PER_CELL * miles / MILES, 4), "terrain": dict(TERRAIN), "cells": {}}
    if land is not None:
        h, w = land.shape
        for c in cells(g):
            x, y = centre(c, miles)
            fx, fy = x / miles_across, y / (miles_across * aspect)  # (an edge cell's centre may be off the map:
            if not land[min(max(int(fy * h), 0), h - 1), min(max(int(fx * w), 0), w - 1)]:  # it takes the edge's)
                g["cells"][c] = {"terrain": "water"}
    return g


def _malformed(grid) -> str | None:
    """What's wrong with a hand-edited grid's shape, if anything (so `check` reports it, not a crash)."""
    if not isinstance(grid, dict):
        return "the grid isn't a table"
    for k in ("cols", "rows", "miles", "days_per_cell"):
        v = grid.get(k)
        if isinstance(v, bool) or not isinstance(v, (int, float)) or v <= 0:
            return f"the grid's {k} must be a positive number, not {v!r}"
    if not isinstance(grid.get("terrain"), dict) or not isinstance(grid.get("cells"), dict) \
            or not all(isinstance(v, dict) for v in grid["cells"].values()):
        return "the grid needs a terrain table and a cells table of tables"
    return None


def terrain(cid: str, grid: dict) -> str:
    return grid["cells"].get(cid, {}).get("terrain", "plains")


def region(cid: str, grid: dict):
    return grid["cells"].get(cid, {}).get("region")


def days(path: list[str], grid: dict) -> int | None:
    """A land path's days (see the module doc), or None if it crosses impassable cells."""
    costs = [grid["terrain"].get(terrain(c, grid)) for c in path]
    if any(c is None for c in costs):
        return None
    total = sum((a + b) / 2 for a, b in zip(costs, costs[1:])) * grid["days_per_cell"]
    return max(1, math.ceil(total - 1e-9))


# ------------------------------------------------------------ checks and baking


def check(doc: dict, grid: dict, layout: dict) -> list[dict]:
    """Every problem with a map: errors first, then warnings (baked values the geography disagrees with)."""
    errors, warnings = [], []
    bad = _malformed(grid)
    if bad:
        return [_f("bad_grid", None, bad)]
    for kind, cost in grid["terrain"].items():
        if cost is not None and (isinstance(cost, bool) or not isinstance(cost, (int, float)) or cost <= 0):
            errors.append(_f("bad_terrain", kind, f"terrain {kind!r} costs {cost!r}: a positive number, or null"))
    regions = {r["id"]: r for r in doc.get("regions", [])}
    leaves = set(regions) - {r.get("within") for r in regions.values()}
    places = {p["id"]: p for p in doc.get("places", [])}
    routes = {r["id"]: r for r in doc.get("routes", [])}
    for cid, v in grid.get("cells", {}).items():
        if not known(cid, grid):
            errors.append(_f("unknown_cell", cid, f"painted cell {cid} is off the grid"))
            continue
        if "terrain" in v and v["terrain"] not in grid["terrain"]:
            errors.append(_f("unknown_terrain", cid, f"{cid} is painted {v['terrain']!r}, not a terrain kind"))
        if "region" in v:
            if v["region"] not in regions:
                errors.append(_f("unknown_region", cid, f"{cid} is painted {v['region']!r}, not a region"))
            elif v["region"] not in leaves:
                errors.append(_f("not_a_leaf", cid, f"{cid} is painted {v['region']}, which has regions within it"))
    at_cell = {}
    for pid, v in layout.get("places", {}).items():
        if pid not in places:
            errors.append(_f("unknown_place", pid, f"the layout places {pid}, which isn't in the geography"))
        elif not known(v.get("cell"), grid):
            errors.append(_f("unknown_cell", pid, f"{pid} stands on {v.get('cell')!r}, which isn't a cell"))
        else:
            at_cell[pid] = v["cell"]
    for pid, c in at_cell.items():
        p = places[pid]
        if p["kind"] == "settlement" and region(c, grid) is None:
            errors.append(_f("no_region", pid, f"{pid} stands on {c}, which has no region painted"))
        elif region(c, grid) is not None and p.get("region") != region(c, grid):
            warnings.append(_f("region_differs", pid, f"{pid} is in {p.get('region')} but stands in {region(c, grid)}",
                               "warning"))
    for rid, v in layout.get("routes", {}).items():
        if rid not in routes:
            errors.append(_f("unknown_route", rid, f"the layout draws {rid}, which isn't in the geography"))
            continue
        path, r = v.get("cells") or [], routes[rid]
        if not path:  # (no path drawn yet: the route keeps its typed days)
            continue
        bad = [c for c in path if not known(c, grid)]
        if bad:
            errors.append(_f("unknown_cell", rid, f"{rid}'s path has cells off the grid: {bad}"))
            continue
        if any(b not in near(a, grid) for a, b in zip(path, path[1:])):
            errors.append(_f("not_adjacent", rid, f"{rid}'s path jumps between cells that don't touch"))
        ends = [at_cell.get(e) for e in r["ends"]]
        if [path[0], path[-1]] not in (ends, ends[::-1]):
            errors.append(_f("path_ends", rid, f"{rid}'s path doesn't run from one end's cell to the other's"))
        if r.get("kind") in WATER_KINDS:
            continue
        derived = days(path, grid)
        if derived is None:
            errors.append(_f("path_in_water", rid, f"{rid} is a {r.get('kind')} over impassable cells"))
        elif derived != r["days"]:  # (the base days: a dated re-timing (#81) changes them later, in the run)
            warnings.append(_f("days_differ", rid, f"{rid} takes {r['days']} days; its cells say {derived}", "warning"))
    return errors + warnings


def bake(doc: dict, grid: dict, layout: dict) -> tuple[dict, list[dict]]:
    """The geography with what the map implies written in (see the module doc), and the check's findings.
    Nothing is baked from a map with errors: the geography comes back as it was."""
    findings = check(doc, grid, layout)
    if any(f["severity"] == "error" for f in findings):
        return copy.deepcopy(doc), findings
    out = copy.deepcopy(doc)
    for p in out.get("places", []):
        c = layout.get("places", {}).get(p["id"], {}).get("cell")
        if c and region(c, grid) is not None:
            p["region"] = region(c, grid)
    for r in out.get("routes", []):
        path = layout.get("routes", {}).get(r["id"], {}).get("cells")
        if path and r.get("kind") not in WATER_KINDS:
            r["days"] = days(path, grid)
    return out, [f for f in check(out, grid, layout) if f["kind"] not in ("days_differ", "region_differs")]


def regrid(grid: dict, layout: dict, miles: float) -> tuple[dict, dict]:
    """The same map on cells of another size: paint, places and paths move to the cells now under their
    old cells' centres, and paths are re-traced between them over land (by the fewest cells; straight
    where water cuts them off, which `check` reports). An explicit migration: nothing regenerates silently."""
    width, height = grid["cols"] * grid["miles"], grid["rows"] * grid["miles"] * math.sqrt(3) / 2
    g = {**copy.deepcopy(grid), "miles": miles, "cols": math.ceil(width / miles),
         "rows": math.ceil(height / (miles * math.sqrt(3) / 2)), "cells": {},
         "days_per_cell": round(grid["days_per_cell"] * miles / grid["miles"], 4)}
    def moved(c: str) -> str:
        return cell(*at(*centre(c, grid["miles"]), g, as_tuple=True))

    # Each old cell's paint goes to the new cell under its centre (as places do). Where several old cells
    # land on one new cell: its terrain is the commonest of theirs (unpainted counting as plains), and its
    # region the commonest of those painted (an unpainted cell has no say). Ties go to the lower name. A new
    # cell no old centre lands on (when refining) takes the old cell under its own centre.
    landed: dict[str, list[dict]] = {}
    for c in cells(grid):
        landed.setdefault(moved(c), []).append(grid["cells"].get(c, {}))

    def commonest(values: list[str]) -> str | None:
        counts: dict[str, int] = {}
        for v in values:
            counts[v] = counts.get(v, 0) + 1
        return min(counts, key=lambda v: (-counts[v], v)) if counts else None

    for c in cells(g):
        olds = landed.get(c) or [grid["cells"].get(at(*centre(c, miles), grid), {})]
        paint = {}
        land = commonest([o.get("terrain", "plains") for o in olds])
        if land != "plains":
            paint["terrain"] = land
        where = commonest([o["region"] for o in olds if o.get("region")])
        if where:
            paint["region"] = where
        if paint:
            g["cells"][c] = paint

    out = {"places": {pid: {**v, "cell": moved(v["cell"])} for pid, v in layout.get("places", {}).items()},
           "routes": {}}
    for rid, v in layout.get("routes", {}).items():
        path = [moved(c) for c in v.get("cells", [])]
        walked = path[:1]
        for a, b in zip(path, path[1:]):  # (over land where it can be: else straight, and the check says so)
            walked += (walk(a, b, g) or line(a, b, g))[1:]
        out["routes"][rid] = {**v, "cells": walked}
    return g, out
