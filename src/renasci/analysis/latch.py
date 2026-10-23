"""Latch points (S7 spec §8): the moments where a small change would have mattered, each a ready what-if.

Found after a run, from its tables and final state, and ranked by **potential** (`score` is the
potential over the best of its kind, so the two kinds interleave rather than one crowding out the other):

- **died unfulfilled**: a death that cut ambitions short. Potential: per ambition, its class stakes x
  (1 + youth) x (1 + its scheme's progress), plus half a point for every arc that touched the dead
  (ambitions aimed at them). The what-if is **protect** from the start of that year for ten years: a
  physician's care for an illness or old age, a second's intervention for a death by someone's hand.
- **near miss**: a death draw survived by a small margin (a hinge) by someone who later mattered.
  Potential: the hinge's stakes x how close it was against the odds (p / (p + margin): surviving a 30% draw
  by 0.01 is closer than surviving a 0.2% one by the same margin) x log(1 + the events they took part
  in afterwards: actions, ambitions, schemes, marriages, births, successions). The what-if is **doom** on that day: an illness.

`latch_points(...)` is pure; `renasci latch <run>` writes `analysis/latch.json` and `--launch N` replays
point N as a what-if and diffs it against the run.
"""

from __future__ import annotations

import math

from renasci.core.calendar import Date

STAKES = {"Seize": 3.0, "Vengeance": 2.0, "Protect": 2.0, "Standing": 1.5, "Marry": 1.0}
PROTECT_YEARS = 10
LIMIT = 25  # points kept in latch.json, per kind
VIOLENT = ("people.action",)
# What makes someone matter afterwards: the events a story is told from (not ties, drives or their own death).
STORY = ("people.action", "people.ambition_formed", "people.scheme_begun", "people.scheme_exposed", "people.marriage",
         "people.birth", "people.succession", "people.heir_named")


def latch_points(events: list[dict], hinges: list[dict], state: dict, *, days_per_year: int,
                 limit: int = LIMIT) -> list[dict]:
    """Ranked latch points (dicts, JSON-ready)."""
    entities = {e["id"]: e for e in state["entities"]}

    def field(entity, name):
        return (entities.get(entity) or {}).get("fields", {}).get(name)

    by_id = {ev["id"]: ev for ev in events}
    deaths = {ev["roles"]["deceased"][0]: ev for ev in events if ev["type"] == "people.death"}
    schemes_of: dict[str, list[dict]] = {}
    for e in entities.values():
        if e["kind"] == "scheme":
            schemes_of.setdefault(e["fields"]["ambition"], []).append(e["fields"])
    aimed_at: dict[str, int] = {}
    for e in entities.values():
        if e["kind"] == "ambition" and e["fields"].get("target"):
            aimed_at[e["fields"]["target"]] = aimed_at.get(e["fields"]["target"], 0) + 1

    points = []

    # ---- died unfulfilled: one point per death, summing the ambitions it cut short
    cut: dict[str, list[str]] = {}
    for ev in events:
        if ev["type"] == "people.ambition_resolved" and ev["payload"]["status"] == "died_unfulfilled":
            cut.setdefault(ev["roles"]["owner"][0], []).append(ev["roles"]["ambition"][0])
    for person, ambs in sorted(cut.items()):
        death = deaths.get(person)
        if death is None:
            continue
        age = int(death["payload"]["age"])
        youth = max(0.0, 1.0 - age / 70.0)
        score, why = 0.0, []
        for amb in sorted(ambs):
            cls = field(amb, "class")
            progress = max((s["step"] / len(s["plan"]) for s in schemes_of.get(amb, []) if s.get("plan")), default=0.0)
            score += STAKES.get(cls, 1.0) * (1.0 + youth) * (1.0 + progress)
            why.append(f"{cls}" + (f" ({round(progress * 100)}% through a scheme)" if progress else ""))
        arcs = aimed_at.get(person, 0)
        score += 0.5 * arcs
        violent = bool(death["roles"].get("killer")) or any(
            by_id.get(c[1], {}).get("type") in VIOLENT for c in death["causes"] if c[0] == "event")
        date = Date.from_json(death["date"])
        points.append({
            "kind": "died_unfulfilled", "person": person, "date": death["date"], "event": death["id"],
            "potential": round(score, 6), "ambitions": sorted(ambs), "age": age,
            "why": f"died at {age} ({death['payload']['cause']}) with {', '.join(why)} unfulfilled"
                   + (f"; {arcs} other ambition(s) aimed at them" if arcs else ""),
            "means": "a second's intervention" if violent else "a physician's care",
            "ripple": {"kind": "protect", "date": [date.age, date.year, 0], "target": person,
                       "params": {"until": [date.age, date.year + PROTECT_YEARS, days_per_year - 1]}},
        })

    # ---- near misses: a death draw survived narrowly, by someone who mattered afterwards
    later: dict[str, list[list[int]]] = {}
    for ev in events:
        if ev["type"] not in STORY:
            continue
        for members in ev["roles"].values():
            for m in members:
                later.setdefault(m, []).append(ev["date"])
    best: dict[str, dict] = {}
    for h in hinges:
        if h["kind"] != "chance" or h["purpose"] != "death" or h.get("outcome") is not False:
            continue
        person = h["owner"]
        after = sum(1 for d in later.get(person, []) if d > h["date"])
        if after == 0:
            continue
        closeness = h["p"] / (h["p"] + h["margin"]) if h["p"] + h["margin"] > 0 else 0.0
        score = h["stakes"] * closeness * math.log1p(after)
        prior = best.get(person)
        if prior is None or (-score, h["date"]) < (-prior["potential"], prior["date"]):  # (their closest call)
            best[person] = {
                "kind": "near_miss", "person": person, "date": h["date"], "hinge": h["id"],
                "potential": round(score, 6), "margin": round(h["margin"], 6), "after": after,
                "why": f"survived a death draw by {h['margin']:.3f} (p {h['p']:.3f}) and took part in {after} "
                       "later story events",
                "means": "an illness",
                "ripple": {"kind": "doom", "date": h["date"], "target": person, "params": {}},
            }
    points.extend(best.values())

    for kind in ("died_unfulfilled", "near_miss"):  # each kind on its own scale: its best is 1
        top = max((p["potential"] for p in points if p["kind"] == kind), default=0.0)
        for p in points:
            if p["kind"] == kind:
                p["score"] = round(p["potential"] / top, 6) if top else 0.0

    def order(p):
        return -p["score"], -p["potential"], p["date"], p["person"], p["kind"]

    kept = []
    for kind in ("died_unfulfilled", "near_miss"):  # each kind keeps its best, so neither crowds out the other
        kept += sorted((p for p in points if p["kind"] == kind), key=order)[:limit]
    points = sorted(kept, key=order)
    for i, p in enumerate(points, 1):
        p["rank"] = i
    return points
