"""Hard truths: what a world starts with (vision spec §5, #165). Define a world slowly: generate things, keep what's
good, and re-run around it.

A truth file is plain JSON, written by hand or kept from a run (`renasci keep`), and named by a recipe (`[world] truths =
"my_world.json"`). It holds **starting truths**, added to the scenario before anything runs, so nothing has to be
forced and they cost the sim nothing:

    {"places": [{"id": "v:ashfall", "name": "Ashfall", "kind": "village", "region": "v:flame-coast",
                 "masses": 200, "near": [{"to": "v:port-ardere", "days": 3}]},
                {"id": "v:old-keep", "name": "the Old Keep", "kind": "ruin", "region": "v:ember-peaks",
                 "near": [{"to": "v:magnus-rest", "days": 4}]}],
     "objects": [{"id": "t:thirsting-blade", "name": "the Thirsting Blade", "type": "blade", "material": "iron",
                  "place": "v:old-keep", "fame": 0.5, "from": "the Third Age"}]}

A **village** is a settlement: people, trades, a past of its own from here on. A **ruin** is a place nobody lives; what
lies there waits for someone from a town a road away. An **object** lies lost where it is put, and the world's rule
for lost things applies: someone may find it, and its story starts there. `from` is where it came from: another
run, or an older age, which is how ages hand down to each other.

A run keeps a copy of its truth file (`truths.json`), as it keeps its canon: a replay uses that copy, and refuses a file
that has changed since. `renasci keep` gives what it keeps an id of its own, so a re-run that makes the same thing again
makes a twin, not a clash. It keeps objects; a town is already in the world it came from.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

VILLAGE = {"masses": 200, "commoners": 5, "notable_target": 8}


def load(path) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def check(doc: dict, scenario: dict) -> None:
    """Refuse a truth file the scenario can't hold, naming what's wrong."""
    if not isinstance(doc, dict) or set(doc) - {"about", "places", "objects"} \
            or not all(isinstance(doc.get(k, []), list) for k in ("places", "objects")):
        raise ValueError("a truth file is {about, places: [...], objects: [...]}")
    geography = scenario.get("geography")
    known = {p["id"] for p in (geography or {}).get("places", [])}
    regions = {r["id"] for r in (geography or {}).get("regions", [])}
    mine = [p.get("id") for p in doc.get("places", [])]
    if len(set(mine)) != len(mine) or set(mine) & known:
        raise ValueError(f"truths: place ids must be new: {sorted(set(mine) & known) or mine}")
    if doc.get("places") and not geography:
        raise ValueError("truths: places need a world with a map")
    for p in doc.get("places", []):
        if p.get("kind") not in ("village", "ruin") or not p.get("id") or not p.get("name"):
            raise ValueError(f"truths: a place has an id, a name and a kind (village or ruin): {p!r}")
        if p.get("region") not in regions:
            raise ValueError(f"truths: {p['id']} is in no known region: {p.get('region')!r}")
        if p.get("race") is not None and p["race"] not in {r["id"] for r in scenario.get("races", [])}:
            raise ValueError(f"truths: {p['id']} has an unknown race: {p['race']!r}")
        if not isinstance(p.get("masses", 0), int) or p.get("masses", 0) < 0:
            raise ValueError(f"truths: {p['id']}'s masses must be a whole number, not {p.get('masses')!r}")
        for n in p.get("near", []):
            if n.get("to") not in known | set(mine) or not isinstance(n.get("days"), int) or n["days"] < 1:
                raise ValueError(f"truths: {p['id']} has a bad road: {n!r}")
    crafts = (scenario.get("params") or {}).get("crafts") or {}
    ids = [o.get("id") for o in doc.get("objects", [])]
    if len(set(ids)) != len(ids):
        raise ValueError(f"truths: object ids must differ: {ids}")
    for o in doc.get("objects", []):
        if not o.get("id") or o.get("type") not in (crafts.get("types") or {}):
            raise ValueError(f"truths: an object has an id and a type the world's crafts know: {o!r}")
        if o.get("material") not in (crafts.get("materials") or {}):
            raise ValueError(f"truths: {o['id']} is made of something the world doesn't know: {o.get('material')!r}")
        if o.get("place") not in known | set(mine):
            raise ValueError(f"truths: {o['id']} lies nowhere known: {o.get('place')!r}")


def apply(scenario: dict, doc: dict) -> dict:
    """The scenario with these truths in it."""
    check(doc, scenario)
    sc = {**scenario}
    if doc.get("places"):
        g = sc["geography"]
        places, routes = list(g["places"]), list(g["routes"])
        settlements, regions = list(sc["settlements"]), {k: list(v) for k, v in sc["regions"].items()}
        for p in doc["places"]:
            village = p["kind"] == "village"
            places.append({"id": p["id"], "name": p["name"], "region": p["region"],
                           "kind": "settlement" if village else "ruin"})
            routes += [{"id": f"g:{p['id']}--{n['to']}", "ends": [p["id"], n["to"]], "days": n["days"], "kind": "road"}
                       for n in p.get("near", [])]
            if village:
                settlements.append(_village(p, settlements))
                regions[p["region"]] = [*regions.get(p["region"], []), p["id"]]
        sc.update(settlements=settlements, regions=regions, geography={**g, "places": places, "routes": routes})
    if doc.get("objects"):
        sc["objects"] = [*(sc.get("objects") or []), *doc["objects"]]
    return sc


def _village(p: dict, settlements: list) -> dict:
    kin = next((s for s in settlements if s["region"] == p["region"]), settlements[0])
    masses = int(p.get("masses", VILLAGE["masses"]))
    return {"id": p["id"], "name": p["name"], "region": p["region"], "race": p.get("race", kin["race"]),
            "genome_group": kin["genome_group"], "masses": masses, "commoners": VILLAGE["commoners"],
            "capacity": (masses + VILLAGE["commoners"]) * 3, "notable_target": VILLAGE["notable_target"], "danger": float(p.get("danger", 0.0))}


def object_fields(o: dict, start: list) -> dict:
    """What a truth's object is cast with: lying lost, with nobody's name on it yet."""
    return {"name": o.get("name"), "type": o["type"], "material": o["material"], "maker": None, "made": None,
            "quality": float(o.get("quality", 0.8)), "owner": None, "place": o["place"], "deeds": [],
            "fame": float(o.get("fame", 0.0)), "lost": start, "origin": o.get("from")}


def keep(state: dict, entity: str, run: str) -> tuple[str, dict]:
    """A truth from a finished run: (the section it goes in, the entry)."""
    records = {e["id"]: e for e in state["entities"]}
    found = records.get(entity)
    if found is None:
        raise ValueError(f"{entity} isn't in that run's final state")
    if found.get("kind") != "object":
        raise ValueError(f"keeping a {found.get('kind')} isn't built yet: objects are")
    if found.get("status") != "active":
        raise ValueError(f"{entity} no longer exists in that run")
    f = found["fields"]
    owner = records.get(f.get("owner"))
    place = (owner["fields"].get("place") if owner else None) or f["place"]
    slug = re.sub(r"[^a-z0-9]+", "-", str(f.get("name") or f"{f['type']}-{entity}").lower()).strip("-")
    return "objects", {"id": f"t:{slug}", "name": f.get("name"), "type": f["type"], "material": f["material"],
                       "quality": f.get("quality", 0.8), "fame": f.get("fame", 0.0), "place": place, "from": run}


def add(path, section: str, entry: dict) -> None:
    """Write a kept truth into a truth file, making it if it's new."""
    target = Path(path)
    doc = load(target) if target.exists() else {}
    have = doc.setdefault(section, [])
    if any(x.get("id") == entry["id"] for x in have):
        raise ValueError(f"{entry['id']} is already in {target}")
    have.append(entry)
    target.write_text(json.dumps(doc, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
