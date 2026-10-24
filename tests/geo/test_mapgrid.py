"""The cell grid (S5 spec §3, #80): 24-mile hex cells (pointy-top, odd-r offset), ids `c:<col>,<row>`,
neighbours from the id; terrain and regions painted on cells; route days and settlement regions derived
from the cells and baked into the geography the sim reads."""

import copy
import math

import pytest

from renasci import mapgrid as G


def grid(cols=6, rows=5, cells=None):
    return {"cols": cols, "rows": rows, "miles": 24, "days_per_cell": 1.2, "terrain": dict(G.TERRAIN),
            "cells": cells or {}}


DOC = {
    "regions": [{"id": "g:land"}, {"id": "g:north", "within": "g:land"}, {"id": "g:south", "within": "g:land"}],
    "places": [{"id": "t:a", "kind": "settlement", "region": "g:north"},
               {"id": "t:b", "kind": "settlement", "region": "g:north"},
               {"id": "t:c", "kind": "settlement", "region": "g:south"}],
    "routes": [{"id": "g:a--b", "ends": ["t:a", "t:b"], "days": 9, "kind": "road"},
               {"id": "g:b--c", "ends": ["t:b", "t:c"], "days": 4, "kind": "sea"}],
}
GRID = grid(cells={"c:0,0": {"region": "g:north"}, "c:1,0": {"region": "g:north"},
                   "c:2,0": {"region": "g:north", "terrain": "hills"}, "c:3,0": {"region": "g:north"},
                   "c:5,4": {"region": "g:south"}, "c:4,2": {"terrain": "water"}})
LAYOUT = {"places": {"t:a": {"cell": "c:0,0"}, "t:b": {"cell": "c:3,0"}, "t:c": {"cell": "c:5,4"}},
          "routes": {"g:a--b": {"cells": ["c:0,0", "c:1,0", "c:2,0", "c:3,0"]},
                     "g:b--c": {"cells": ["c:3,0", "c:3,1", "c:4,2", "c:4,3", "c:5,4"]}}}  # (a sea lane: drawn, not walked)


def test_ids_round_trip_and_neighbours_follow_odd_r_offset_rows():
    assert G.cell(3, 4) == "c:3,4" and G.parse("c:3,4") == (3, 4)
    g = grid()
    assert sorted(G.near("c:2,2", g)) == sorted(["c:1,2", "c:3,2", "c:1,1", "c:2,1", "c:1,3", "c:2,3"])  # (even row)
    assert sorted(G.near("c:2,1", g)) == sorted(["c:1,1", "c:3,1", "c:2,0", "c:3,0", "c:2,2", "c:3,2"])  # (odd row)
    assert sorted(G.near("c:0,0", g)) == ["c:0,1", "c:1,0"]  # (a corner)
    for c in G.cells(g):  # (neighbourhood is symmetric)
        assert all(c in G.near(n, g) for n in G.near(c, g))


def test_a_cells_centre_is_found_back_from_its_position():
    g = grid(20, 15)
    for c in ("c:0,0", "c:7,3", "c:19,14", "c:4,9"):
        x, y = G.centre(c, 24)
        assert G.at(x, y, g) == c
        assert G.at(x + 5, y - 4, g) == c  # (well inside the hex: 24 miles across the flats)


def test_terrain_is_painted_else_plains():
    assert G.terrain("c:2,0", GRID) == "hills" and G.terrain("c:1,0", GRID) == "plains"
    assert G.terrain("c:4,2", GRID) == "water"


def test_a_land_routes_days_are_its_steps_mean_cost_times_days_per_cell_rounded_up():
    # plains-plains 1.0, plains-hills 1.5, hills-plains 1.5: 4.0 x 1.2 = 4.8, so 5
    assert G.days(["c:0,0", "c:1,0", "c:2,0", "c:3,0"], GRID) == 5
    assert G.days(["c:0,0", "c:1,0"], GRID) == 2  # (1.2 rounds up)
    assert G.days(["c:0,0"], GRID) == 1  # (a place to itself: at least a day)
    assert G.days(["c:3,0", "c:4,2"], GRID) is None  # (a land path into the water: impassable)


def test_baking_writes_land_days_and_settlement_regions_and_keeps_sea_days():
    doc, findings = G.bake(DOC, GRID, LAYOUT)
    assert not [f for f in findings if f["severity"] == "error"]
    routes = {r["id"]: r for r in doc["routes"]}
    assert routes["g:a--b"]["days"] == 5 and routes["g:b--c"]["days"] == 4
    assert {p["id"]: p["region"] for p in doc["places"]} == {"t:a": "g:north", "t:b": "g:north", "t:c": "g:south"}
    assert not any("cell" in p or "at" in p for p in doc["places"]) and not any("cells" in r for r in doc["routes"])
    assert DOC["routes"][0]["days"] == 9  # (the input is untouched)


def test_a_repainted_city_moves_region_on_bake():
    g = copy.deepcopy(GRID)
    g["cells"]["c:3,0"]["region"] = "g:south"
    doc, _ = G.bake(DOC, g, LAYOUT)
    assert next(p for p in doc["places"] if p["id"] == "t:b")["region"] == "g:south"


def errors(doc=DOC, g=GRID, layout=LAYOUT):
    return {f["kind"] for f in G.check(doc, g, layout) if f["severity"] == "error"}


@pytest.mark.parametrize("change, kind", [
    (lambda d, g, l: l["places"]["t:a"].update(cell="c:99,0"), "unknown_cell"),
    (lambda d, g, l: l["routes"]["g:a--b"].update(cells=["c:0,0", "c:2,0", "c:3,0"]), "not_adjacent"),
    (lambda d, g, l: l["routes"]["g:a--b"].update(cells=["c:1,0", "c:2,0", "c:3,0"]), "path_ends"),
    (lambda d, g, l: g["cells"]["c:1,0"].update(terrain="water"), "path_in_water"),
    (lambda d, g, l: g["cells"]["c:1,0"].update(region="g:atlantis"), "unknown_region"),
    (lambda d, g, l: g["cells"]["c:1,0"].update(region="g:land"), "not_a_leaf"),
    (lambda d, g, l: g["cells"]["c:0,0"].pop("region"), "no_region"),
    (lambda d, g, l: g["cells"]["c:1,0"].update(terrain="lava"), "unknown_terrain"),
    (lambda d, g, l: l["routes"].update({"g:nope": {"cells": ["c:0,0"]}}), "unknown_route"),
])
def test_each_check_has_its_finding(change, kind):
    d, g, l = copy.deepcopy(DOC), copy.deepcopy(GRID), copy.deepcopy(LAYOUT)
    change(d, g, l)
    assert kind in errors(d, g, l)


def test_a_good_map_has_no_errors_and_stale_days_are_a_warning():
    assert errors() == set()
    warnings = [f for f in G.check(DOC, GRID, LAYOUT) if f["severity"] == "warning"]
    assert [f["kind"] for f in warnings] == ["days_differ"] and warnings[0]["id"] == "g:a--b"  # (9 typed, 5 derived)


def test_a_new_grid_covers_the_map_at_24_miles_a_cell():
    g = G.new_grid(miles_across=1200, aspect=0.75)
    assert g["cols"] == 50 and g["rows"] == math.ceil(1200 * 0.75 / G.ROW_MILES)
    assert g["days_per_cell"] == 1.2 and g["cells"] == {}


def test_water_from_a_mask_is_painted_into_a_new_grid():
    import numpy as np

    mask = np.ones((60, 80), dtype=bool)
    mask[:, :20] = False  # (the west quarter is sea)
    g = G.new_grid(miles_across=480, aspect=0.75, land=mask)
    water = {c for c, v in g["cells"].items() if v.get("terrain") == "water"}
    assert "c:0,5" in water and "c:15,5" not in water and all(G.parse(c)[0] < 6 for c in water)


def test_regrid_keeps_places_paths_and_paint_on_the_cells_now_under_them():
    g2, l2 = G.regrid(GRID, LAYOUT, miles=12)  # (twice as fine)
    assert g2["miles"] == 12 and g2["cols"] == 12 and g2["rows"] == 10
    old = G.centre("c:0,0", 24)
    new = G.centre(l2["places"]["t:a"]["cell"], 12)
    assert math.dist(old, new) <= 12  # (the new cell under the old centre)
    path = l2["routes"]["g:a--b"]["cells"]
    assert path[0] == l2["places"]["t:a"]["cell"] and path[-1] == l2["places"]["t:b"]["cell"]
    assert all(b in G.near(a, g2) for a, b in zip(path, path[1:]))  # (re-traced: still a walkable path)
    assert any(v.get("terrain") == "hills" for v in g2["cells"].values())
    assert any(v.get("region") == "g:south" for v in g2["cells"].values())
    assert not G.check(DOC, g2, l2) or {f["severity"] for f in G.check(DOC, g2, l2)} == {"warning"}


def test_the_cli_makes_a_grid_from_an_import_then_checks_and_bakes_a_geography(tmp_path):
    import json

    pytest.importorskip("PIL")
    import sys
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).parent))
    from test_map_import import draw

    from renasci import geo, mapimport
    from renasci.cli import main

    maps = tmp_path / "maps"
    mapimport.import_map(draw(tmp_path / "m.png"), maps / "toyland" / "private", water=[(100, 700)], marker=(800, 600),
                         base_width=400, mask_width=200, marker_width=1000)
    assert main(["map", "grid", "--world", "toyland", "--maps", str(maps), "--miles-across", "480"]) == 0
    g = json.loads((maps / "toyland" / "private" / "grid.json").read_text(encoding="utf-8"))
    assert g["cols"] == 20 and any(v.get("terrain") == "water" for v in g["cells"].values())
    assert main(["map", "grid", "--world", "toyland", "--maps", str(maps), "--miles-across", "480"]) != 0  # (made once)

    centre = "c:10,7"  # (on the island)
    g["cells"][centre] = {"region": "g:north"}
    g["cells"]["c:11,7"] = {"region": "g:north"}
    (maps / "toyland" / "private" / "grid.json").write_text(json.dumps(g), encoding="utf-8")
    (maps / "toyland" / "private" / "layout.json").write_text(json.dumps(
        {"places": {"t:a": {"cell": centre}, "t:b": {"cell": "c:11,7"}},
         "routes": {"g:a--b": {"cells": [centre, "c:11,7"]}}}), encoding="utf-8")
    doc = {"regions": [{"id": "g:north"}], "places": [{"id": "t:a", "kind": "settlement", "region": "g:north"},
                                                      {"id": "t:b", "kind": "settlement", "region": "g:north"}],
           "routes": [{"id": "g:a--b", "ends": ["t:a", "t:b"], "days": 7, "kind": "road"}]}
    file = tmp_path / "toyland.json"
    geo.save(file, doc)
    assert main(["map", "check", "--world", "toyland", "--maps", str(maps), "--geography", str(file)]) == 0
    assert main(["map", "bake", "--world", "toyland", "--maps", str(maps), "--geography", str(file)]) == 0
    assert json.loads(file.read_text(encoding="utf-8"))["routes"][0]["days"] == 7  # (a dry run without --write)
    assert main(["map", "bake", "--world", "toyland", "--maps", str(maps), "--geography", str(file), "--write"]) == 0
    assert json.loads(file.read_text(encoding="utf-8"))["routes"][0]["days"] == 2


def test_coarsening_keeps_a_settlements_painted_cell_under_it():
    for col in range(10):
        for row in range(10):
            g = grid(10, 10, cells={G.cell(col, row): {"region": "g:north"}})
            layout = {"places": {"t:a": {"cell": G.cell(col, row)}}, "routes": {}}
            doc = {"regions": [{"id": "g:north"}], "places": [{"id": "t:a", "kind": "settlement", "region": "g:north"}],
                   "routes": []}
            g2, l2 = G.regrid(g, layout, miles=48)
            assert G.region(l2["places"]["t:a"]["cell"], g2) == "g:north", (col, row)
            assert not [f for f in G.check(doc, g2, l2) if f["severity"] == "error"]


def test_a_regridded_path_goes_round_the_water_not_through_it():
    water = {G.cell(c, r): {"terrain": "water"} for c in range(3, 6) for r in range(0, 6)}
    g = grid(10, 8, cells=water)
    path = [G.cell(1, 7)] + [G.cell(c, 7) for c in range(2, 9)]  # (along the south shore, below the lake)
    layout = {"places": {"t:a": {"cell": path[0]}, "t:b": {"cell": path[-1]}}, "routes": {"g:a--b": {"cells": path}}}
    doc = {"regions": [], "places": [{"id": "t:a", "kind": "landmark", "region": "g:x"},
                                     {"id": "t:b", "kind": "landmark", "region": "g:x"}],
           "routes": [{"id": "g:a--b", "ends": ["t:a", "t:b"], "days": 9, "kind": "road"}]}
    for miles in (12, 36, 48):
        g2, l2 = G.regrid(g, layout, miles=miles)
        walked = l2["routes"]["g:a--b"]["cells"]
        assert all(G.terrain(c, g2) != "water" for c in walked), miles
        assert all(b in G.near(a, g2) for a, b in zip(walked, walked[1:])), miles


def test_a_line_stays_on_the_grid_along_the_right_edge():
    g = grid(9, 8)
    for a in G.cells(g):
        for b in G.cells(g):
            assert all(G.known(c, g) for c in G.line(a, b, g)), (a, b)


def test_a_new_grid_from_an_all_water_mask_is_all_water():
    import numpy as np

    g = G.new_grid(miles_across=480, aspect=0.75, land=np.zeros((60, 80), dtype=bool))
    assert all(G.terrain(c, g) == "water" for c in G.cells(g))


def test_an_empty_path_is_no_path_and_a_bad_grid_is_reported_not_a_crash():
    layout = {**LAYOUT, "routes": {"g:a--b": {"cells": []}}}
    assert errors(layout=layout) == set()
    assert "bad_grid" in errors(g={"cols": 3})
    assert "bad_terrain" in errors(g={**GRID, "terrain": {**GRID["terrain"], "hills": -1}})


def test_a_dated_retiming_does_not_hide_drift_in_the_base_days():
    doc = {**DOC, "changes": [{"date": [1, 2, 0], "route": "g:a--b", "days": 20}]}
    assert "days_differ" in {f["kind"] for f in G.check(doc, GRID, LAYOUT)}
