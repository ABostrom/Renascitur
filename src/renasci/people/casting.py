"""Casting (S2 spec §7): the vault's canon people, as the input S3's synthesis places at the start.

`canon_from(extraction, vault, scenario)` turns the people hook's placements into `synthesise`'s `canon`:

- **placed** and **drawn** characters are cast with their canon ids. A placed one keeps the earliest day
  of its `born` window; a drawn one gets an age drawn at synthesis (never canon). Race goes through
  `vault.toml`'s `[races]`; home is the note's `home` if the scenario has that settlement, else the house's
  seat, else the scenario's first settlement.
- each scenario house's **head** is the office holder at the start (`extraction.holders`), else the house
  note's `head:`, if that character is cast alive. The head takes the synthesised head's place.
- canon **parents who died before the start** are cast as dead records when a cast child names them, so
  lineages hold; **reserved** characters are born in the run by their birth pins; **unplaced** and
  out-of-scope ones aren't cast.

It also returns the **casting log** (`casting.json` in a run folder): for every canon character, how it
was cast (`placed`, `drawn`, `dead`, `reserved`, `unplaced`, `out_of_scope`), the entity it became, and as
what (head, member, commoner, dead record).
"""

from __future__ import annotations

CAST = ("placed", "drawn")


def canon_from(extraction, vault, scenario: dict) -> tuple[dict, dict]:
    """(canon for `synthesise`, the casting log)."""
    houses = {h["id"]: h for h in scenario["houses"]}
    settlements = {s["id"] for s in scenario["settlements"]}
    scenario_races = {r["id"] for r in scenario["races"]}
    places = extraction.placements
    by_id = {}
    from renasci.vault.ids import assign

    for key, cid in assign(vault).items():
        by_id[cid] = key

    cast = {cid for cid, p in places.items() if p["status"] in CAST}
    needed_dead = {pid for cid in cast for pid in places[cid].get("parents", {}).values()
                   if pid in places and places[pid]["status"] == "dead"}

    def record(cid: str) -> dict:
        p = places[cid]
        note = vault.notes[p["key"]]
        home = vault.resolve(note.frontmatter["home"]) if isinstance(note.frontmatter.get("home"), str) else None
        home_id = _id_of(vault, home)
        race = vault.config.races.get(p.get("race"))
        born = p["born"][0] if p.get("born") and p["status"] in ("placed", "dead") else None
        return {"name": note.frontmatter.get("name") if isinstance(note.frontmatter.get("name"), str) else note.title,
                "sex": p.get("sex"), "born": born, "died": p["died"][0] if p.get("died") else None,
                "race": race if race in scenario_races else None,
                "house": p["house"] if p.get("house") in houses else None,
                "home": home_id if home_id in settlements else None,
                "father": p["parents"].get("father"), "mother": p["parents"].get("mother"),
                "status": "dead" if p["status"] == "dead" else "alive"}

    people = {cid: record(cid) for cid in sorted(cast | needed_dead)}
    for c in people.values():  # parents that aren't cast aren't named
        for k in ("father", "mother"):
            if c[k] not in people:
                c[k] = None

    heads: dict[str, str] = {}
    also: dict[str, list[str]] = {}  # someone named head of more than one house heads the first only
    for house in sorted(houses):
        holder = extraction.holders.get(f"{house}-head")
        if holder not in cast:
            note = vault.notes.get(by_id.get(house, ""))
            link = vault.resolve(note.frontmatter["head"], {"character"}) \
                if note is not None and isinstance(note.frontmatter.get("head"), str) else None
            holder = _id_of(vault, link)
        if holder in cast and holder in heads.values():
            also.setdefault(holder, []).append(house)
        elif holder in cast:
            heads[house] = holder
    for cid, house in ((c, h) for h, c in heads.items()):
        people[cid]["house"] = house  # a head belongs to the house they head

    log = {}
    for cid, p in sorted(places.items()):
        status = p["status"]
        if status in CAST:
            house = people[cid]["house"]
            what = (f"head of {house}" if heads.get(house) == cid else f"member of {house}" if house
                    else f"commoner at {people[cid]['home'] or scenario['settlements'][0]['id']}")
            if cid in also:
                what += f" (named head of {', '.join(also[cid])} too: heads {house} only)"
            if p.get("house") and p["house"] not in houses:
                what += f" ({p['house']} is not in the scenario)"
            log[cid] = {"status": status, "entity": cid, "as": what}
        elif status == "dead":
            log[cid] = ({"status": "dead", "entity": cid, "as": "a dead record (a cast child's parent)"}
                        if cid in people else {"status": "dead", "entity": None, "as": "died before the run"})
        elif status == "reserved":
            log[cid] = {"status": "reserved", "entity": None, "as": "born in the run"}
        else:
            log[cid] = {"status": status, "entity": None,
                        "as": "not cast: no way into the run yet" if status == "unplaced" else "outside the run"}
    return {"people": people, "heads": heads}, log


def _id_of(vault, key):
    if key is None:
        return None
    from renasci.vault.ids import assign

    return assign(vault).get(key)


def castable(pins, scenario: dict) -> tuple[list, list[dict]]:
    """The pins a world built from `scenario` can hold, and the rest with why: a reign of an office the
    scenario has no house for would name an entity that never exists."""
    offices = {f"{h['id']}-head" for h in scenario["houses"]}
    kept, dropped = [], []
    for p in pins:
        office = p.payload.get("office") if p.kind == "event" else None
        if office is not None and office not in offices:
            dropped.append({"pin": p.id, "why": f"{office} is not an office of the scenario's houses"})
        else:
            kept.append(p)
    gone = {d["pin"] for d in dropped}
    for p in [p for p in kept if p.kind == "ordering"]:  # an ordering goes with its pins
        if p.payload["before"] in gone or p.payload["after"] in gone:
            kept.remove(p)
            dropped.append({"pin": p.id, "why": "one of its pins was dropped"})
    return kept, dropped
