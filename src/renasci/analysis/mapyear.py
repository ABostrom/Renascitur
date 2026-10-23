"""The map as of a date (S4 spec §8, #81): a run's geography, with every change to it up to that date.

`geography_at(doc, deltas, date)` starts from the run's `geography.json` and replays the run's
state changes (`state_deltas`) to routes (their ends, days, kind, Vialux, open, bars: a route built mid-run
appears from its first), places and settlements (their region: a border moved) and regions (`within`).
It doesn't read the geography's planned `changes`: whatever changed the map in the run (the plan, or a
system) is in its state changes. The result is a geography without `changes`, as of the end of `date`.
"""

from __future__ import annotations

import copy

from renasci.core.calendar import Date

ROUTE_FIELDS = ("ends", "days", "kind", "vialux", "open", "barred")


def geography_at(doc: dict, deltas, date: Date) -> dict:
    out = copy.deepcopy({k: v for k, v in doc.items() if k != "changes"})
    routes = {r["id"]: r for r in out.get("routes", [])}
    places = {p["id"]: p for p in out.get("places", [])}
    regions = {r["id"]: r for r in out.get("regions", [])}
    new: dict[str, dict] = {}
    built = {d["entity"] for d in deltas if d["field"] == "ends" and d["entity"] not in routes}
    for d in deltas:
        if Date.from_json(d["date"]) > date:
            continue
        e, f, v = d["entity"], d["field"], d["new"]
        if e in routes and f in ROUTE_FIELDS:
            routes[e][f] = v
        elif e in places and f == "region":
            places[e]["region"] = v
        elif e in regions and f == "within":
            regions[e]["within"] = v
        elif e in built and f in ROUTE_FIELDS:
            new.setdefault(e, {"id": e})[f] = v  # (a route built in the run)
    for e, r in sorted(new.items()):
        if {"ends", "days", "kind"} <= set(r):
            out.setdefault("routes", []).append(r)
    return out
