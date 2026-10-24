"""Polities, factions and control (S8 spec §2, #120): who holds what.

A scenario may name `polities` and `factions`:

    "polities": [{"id": "v:empire", "name": "the Empire", "kind": "empire", "government": "advised",
                  "seat": <settlement>, "members": [<house>...], "control": [<region|place|settlement>...],
                  "draft": true}],
    "factions": [{"id": ..., "name": ..., "polity": <polity>, "kind": "bloc", "members": [<house>...],
                  "aims": ["peace"], "standing": 0.6}]

A polity's `control` claims regions (and so every place in them, down the `within` tree) and single places;
the most specific claim wins (a place named outright, else its nearest claimed region). Control is apart
from S4's `region`: provinces don't move when a town changes hands. A **border** is a route whose ends two
polities hold. Control changes through S4's dated changes (`{"place", "control"}`) and the structural
ripple, so the map by year (`analysis.mapyear`) shows it; a run's `geography.json` carries each place's
starting control (`annotate`).

`check(scenario)` lists what's wrong; `control_of` resolves the claims; `cast` makes the entities (the
scenario builder calls it, and writes `control` on settlements and places).
"""

from __future__ import annotations

import copy

from renasci.geo import ID

GOVERNMENTS = ("ruler", "advised", "council")  # (who decides war and peace: S8 §3.3)


def _f(kind: str, ident, message: str) -> dict:
    return {"kind": kind, "id": ident, "message": message, "severity": "error"}


def _map(sc: dict) -> tuple[dict, dict, set]:
    """(region -> its parent, place -> its region, settlement ids), from the geography or the scenario."""
    g = sc.get("geography") if isinstance(sc.get("geography"), dict) else None
    if g is not None:
        within = {r["id"]: r.get("within") for r in g.get("regions", [])}
        region = {p["id"]: p["region"] for p in g.get("places", [])}
    else:
        within = {r: None for r in sc.get("regions", {})}
        region = {}
    for s in sc.get("settlements", []):
        region.setdefault(s["id"], s.get("region"))
    return within, region, {s["id"] for s in sc.get("settlements", [])}


def control_of(sc: dict) -> dict[str, str]:
    """Each place's and settlement's holder: {id: polity}. Places nobody claims are left out."""
    claims = {c: p["id"] for p in sc.get("polities") or [] for c in p.get("control") or []}
    if not claims:
        return {}
    within, region, _ = _map(sc)
    out = {}
    for place, r in sorted(region.items()):
        if place in claims:
            out[place] = claims[place]
            continue
        seen = set()
        while r is not None and r not in seen:
            if r in claims:
                out[place] = claims[r]
                break
            seen.add(r)
            r = within.get(r)
    return out


def borders(routes, control: dict) -> list[dict]:
    """The routes whose ends two different polities hold."""
    return [r for r in routes if control.get(r["ends"][0]) and control.get(r["ends"][1])
            and control[r["ends"][0]] != control[r["ends"][1]]]


def _shape(sc: dict) -> list[dict]:
    """What would stop the checks below from reading the data at all."""
    out = []
    for key in ("polities", "factions"):
        recs = sc.get(key)
        if recs is None:
            continue
        if not isinstance(recs, list):
            out.append(_f("bad_shape", None, f"{key} must be a list"))
            continue
        for rec in recs:
            if not isinstance(rec, dict) or not isinstance(rec.get("id"), str) or not ID.fullmatch(rec["id"]):
                out.append(_f("bad_id", None, f"each of {key} needs a v:, g: or t: id: {rec!r}"))
                continue
            for field in ("control", "members", "aims"):
                v = rec.get(field)
                if v is not None and not (isinstance(v, list) and all(isinstance(x, str) for x in v)):
                    out.append(_f("bad_shape", rec["id"], f"{rec['id']}'s {field} must be a list of ids"))
    g = sc.get("geography")
    if isinstance(g, dict) and any(not isinstance(p, dict) or not isinstance(p.get("region"), (str, type(None)))
                                   for p in g.get("places", [])):
        out.append(_f("bad_shape", None, "the geography's places must each have a region"))
    return out


def check(sc: dict) -> list[dict]:
    out = _shape(sc)
    if out:
        return out
    pols, facs = sc.get("polities") or [], sc.get("factions") or []
    pids = {p["id"] for p in pols}
    g = sc.get("geography") if isinstance(sc.get("geography"), dict) else {}
    for i, c in enumerate(g.get("changes") or []):  # (with polities or without: a change hands a place to one)
        if isinstance(c, dict) and "control" in c and c["control"] is not None and c["control"] not in pids:
            out.append(_f("unknown_control", c.get("place"), f"change {i + 1} hands {c.get('place')} to "
                                                              f"{c['control']!r}, which isn't a polity"))
    if not pols and not facs:
        return out
    within, region, settlements = _map(sc)
    houses = {h["id"] for h in sc.get("houses", [])}
    taken = set(houses) | set(within) | set(region) | {r for r in (sc.get("regions") or {})}
    seen: set = set()
    for rec in [*pols, *facs]:
        if rec["id"] in seen:
            out.append(_f("duplicate_id", rec["id"], f"{rec['id']} is used twice"))
        elif rec["id"] in taken:
            out.append(_f("duplicate_id", rec["id"], f"{rec['id']} is already a house, region or place"))
        else:
            seen.add(rec["id"])
    claimed: dict = {}
    member_of: dict = {}
    for p in pols:
        if not isinstance(p, dict):
            continue
        pid = p.get("id")
        if p.get("government", "ruler") not in GOVERNMENTS:
            out.append(_f("bad_government", pid, f"{pid}'s government is one of {', '.join(GOVERNMENTS)}"))
        if p.get("seat") not in settlements:
            out.append(_f("bad_seat", pid, f"{pid}'s seat {p.get('seat')!r} isn't a settlement"))
        for c in p.get("control") or []:
            if c not in within and c not in region:
                out.append(_f("unknown_control", pid, f"{pid} controls {c!r}, which isn't a region or a place"))
            elif c in claimed:
                out.append(_f("control_twice", pid, f"{c} is claimed by {claimed[c]} and {pid}"))
            else:
                claimed[c] = pid
        for m in p.get("members") or []:
            if m not in houses:
                out.append(_f("unknown_member", pid, f"{pid}'s member {m!r} isn't a house"))
            elif m in member_of:
                out.append(_f("member_twice", pid, f"{m} belongs to {member_of[m]} and {pid}"))
            else:
                member_of[m] = pid
    if not [f for f in out if f["kind"] in ("unknown_control", "control_twice")]:
        control = control_of(sc)
        for p in pols:  # (a polity holds its own seat)
            if p.get("seat") in settlements and control.get(p["seat"]) != p["id"]:
                out.append(_f("seat_not_held", p["id"], f"{p['id']}'s seat {p['seat']} is held by "
                                                        f"{control.get(p['seat']) or 'nobody'}"))
    for f in facs:
        if not isinstance(f, dict):
            continue
        fid = f.get("id")
        if f.get("polity") not in pids:
            out.append(_f("unknown_polity", fid, f"{fid}'s polity {f.get('polity')!r} isn't a polity"))
            continue
        for m in f.get("members") or []:  # (houses, in the data: people join factions in a run)
            if m not in houses:
                out.append(_f("unknown_member", fid, f"{fid}'s member {m!r} isn't a house"))
            elif member_of.get(m) != f["polity"]:
                out.append(_f("faction_outsider", fid, f"{fid}'s member {m} isn't of {f['polity']}"))
        s = f.get("standing", 0.5)
        if isinstance(s, bool) or not isinstance(s, (int, float)) or not 0 <= s <= 1:
            out.append(_f("bad_standing", fid, f"{fid}'s standing must be in [0, 1], not {s!r}"))
    return out


def annotate(geography: dict, sc: dict) -> dict:
    """A geography with each place's starting `control` (for the run's geography.json and the map by year)."""
    control = control_of(sc)
    out = copy.deepcopy(geography)
    if control:
        for p in out.get("places", []):
            if p["id"] in control:
                p["control"] = control[p["id"]]
    return out


def cast(engine, sc: dict, today) -> None:
    """The polities and factions as entities."""
    for p in sc.get("polities") or []:
        engine.cast("polity", p["id"], {
            "name": p.get("name", p["id"]), "kind": p.get("kind", "polity"), "government": p.get("government", "ruler"),
            "seat": p["seat"], "ruler": p.get("ruler"), "members": sorted(p.get("members") or []),
            "founded": today.to_json(), "ended": None, "draft": bool(p.get("draft", False))})
    for f in sc.get("factions") or []:
        engine.cast("faction", f["id"], {
            "name": f.get("name", f["id"]), "polity": f["polity"], "kind": f.get("kind", "bloc"),
            "members": sorted(f.get("members") or []), "aims": list(f.get("aims") or []),
            "standing": float(f.get("standing", 0.5))})
