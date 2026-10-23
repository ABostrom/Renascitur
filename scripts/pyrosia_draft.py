"""Write the provisional Pyrosia geography (S4 spec §7, #76): places from the vault, routes by hand.

Names and ids are the vault's (`v:` slugs, as `renasci vault ids` would give them); kinds, regions for
the locations and every route are a draft. Travel days are placeholders, and nothing here comes from the
private Inkarnate map (no positions). The one route the vault describes is the Vialux between Lion's Rest
and Lux Oescus, past The Bright Tavern.
"""
from pathlib import Path

from renasci import geo

PROVINCES = [("v:ashen-plains", "Ashen Plains"), ("v:ashgatar", "Ashgatar"), ("v:burnt-reach", "Burnt Reach"),
             ("v:ember-peaks", "Ember Peaks"), ("v:flame-coast", "Flame Coast"), ("v:frontiers-edge", "Frontier's Edge")]
CITIES = [("v:lions-rest", "Lion’s Rest", "v:ashen-plains"), ("v:lux-oescus", "Lux Oescus", "v:ashen-plains"),
          ("v:port-ardere", "Port Ardere", "v:ashen-plains"), ("v:magnus-rest", "Magnus’ Rest", "v:ashen-plains"),
          ("v:old-westgate", "Old Westgate", "v:ember-peaks"), ("v:raining-bay", "Raining Bay", "v:flame-coast")]
# (id, name, kind, region, the place it hangs off, days to it)
LOCATIONS = [
    ("v:gatherhold", "Gatherhold", "landmark", "v:ashen-plains", "v:lions-rest", 1),
    ("v:the-den", "The Den", "landmark", "v:ashen-plains", "v:lions-rest", 1),
    ("v:tower-of-inquisition", "Tower of Inquisition", "landmark", "v:ashen-plains", "v:lions-rest", 1),
    ("v:vedkyar-enclave", "Vedkyar Enclave", "landmark", "v:ashen-plains", "v:lions-rest", 1),
    ("v:vigilants-watch", "Vigilants Watch", "landmark", "v:ashen-plains", "v:lions-rest", 1),
    ("v:korunda-gate", "Korunda Gate", "landmark", "v:ashen-plains", "v:lux-oescus", 1),
    ("v:the-labyrinth", "The Labyrinth", "landmark", "v:ashen-plains", "v:lux-oescus", 1),
    ("v:cannith-tower", "Cannith Tower", "landmark", "v:ashen-plains", "v:magnus-rest", 1),
    ("v:cascadia", "Cascadia", "town", "v:ashen-plains", "v:magnus-rest", 2),  # a settlement note, not peopled yet
    ("v:foalswood", "Foalswood", "landmark", "v:ember-peaks", "v:old-westgate", 1),
    ("v:journeys-home", "Journey’s Home", "landmark", "v:ashen-plains", "v:port-ardere", 1),
    ("v:stormhome", "Stormhome", "landmark", "v:flame-coast", "v:raining-bay", 1),
    ("v:the-serpentine-citadel", "The Serpentine Citadel", "fortress", "v:flame-coast", "v:raining-bay", 1),
    ("v:candle-keep", "Candle Keep", "keep", "v:ashen-plains", "v:lux-oescus", 3),
    ("v:obsidian-fotress", "Obsidian Fotress", "fortress", "v:ashen-plains", "v:lions-rest", 4),
    ("v:the-forge-of-souls", "The Forge of Souls", "landmark", "v:ashen-plains", "v:magnus-rest", 3),
    ("v:the-ruins-of-baldurs-gate", "The Ruins of Baldur's Gate", "ruin", "v:ashen-plains", "v:port-ardere", 3),
    ("v:the-ruins-of-elturel", "The Ruins of Elturel", "ruin", "v:ashen-plains", "v:lux-oescus", 4),
    ("v:yokuro-no-ki", "Yōkuro no Ki", "landmark", "v:pyrosia", "v:raining-bay", 4),
]
# (a, b, days, kind, vialux): placeholders, enough to join every city
ROADS = [
    ("v:lions-rest", "v:the-bright-tavern", 2, "road", True),
    ("v:the-bright-tavern", "v:lux-oescus", 2, "road", True),
    ("v:lux-oescus", "v:port-ardere", 5, "road", False),
    ("v:lux-oescus", "v:magnus-rest", 6, "road", False),
    ("v:lions-rest", "v:magnus-rest", 7, "track", False),
    ("v:port-ardere", "v:old-westgate", 6, "road", False),
    ("v:port-ardere", "v:raining-bay", 4, "sea", False),
    ("v:old-westgate", "v:raining-bay", 5, "road", False),
    ("v:magnus-rest", "v:old-westgate", 8, "pass", False),
]


def draft() -> dict:
    places = [{"id": i, "name": n, "kind": "settlement", "region": r} for i, n, r in CITIES]
    places.append({"id": "v:the-bright-tavern", "name": "The Bright Tavern", "kind": "tavern", "region": "v:ashen-plains"})
    places += [{"id": i, "name": n, "kind": k, "region": r} for i, n, k, r, _, _ in LOCATIONS]
    routes = [(a, b, d, k, v) for a, b, d, k, v in ROADS]
    routes += [(at, i, d, "track", False) for i, _, _, _, at, d in LOCATIONS]
    return {
        "draft": True,
        "about": ("PROVISIONAL Pyrosia geography (S4, #76). Places and names come from the vault; kinds, the "
                  "locations' regions and every route are a draft, travel days are placeholders, and none of it "
                  "is canon. No positions: the Observatory lays the graph out (review queue #150)."),
        "regions": [{"id": "v:pyrosia", "name": "Pyrosia"}]
                   + [{"id": i, "name": n, "within": "v:pyrosia"} for i, n in PROVINCES],
        "places": places,
        "routes": [{"id": f"g:{a[2:]}--{b[2:]}" + ("" if k in ("road", "track") else f"-{k}"), "ends": [a, b],
                    "days": d, "kind": k, **({"vialux": True} if v else {})} for a, b, d, k, v in routes],
    }


if __name__ == "__main__":
    out = Path(__file__).parents[1] / "src" / "renasci" / "renascita" / "pyrosia.json"
    doc = draft()
    found = geo.check(doc)
    if found:
        raise SystemExit("\n".join(f["message"] for f in found))
    geo.save(out, doc)
    print(f"written {len(doc['places'])} places, {len(doc['routes'])} routes")
