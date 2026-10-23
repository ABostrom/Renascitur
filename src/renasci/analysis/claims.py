"""What a run's world believes, beside what happened (S13 world knowledge, #106; S6 spec §3, §11).

`claims_report(events, state, geography)` gathers every claim the run's beliefs carried (from `belief.*` events)
and, for each, what the Observatory shows next to the truth:
- `truth` and `basis`: judged offline against the event log (`renasci.analysis.truth`);
- `holders`: living, active notables holding it at the end; `shares`: its share of each settlement's masses;
- `parent`: the claim it drifted from, if it is a retelling's mutation; `lies`: times a lie of it was told
  and taken up;
- `first`: when it first entered anyone's head or a town's talk (null for a claim that only ever lived
  in a town's shares, set there directly); `text`: read out with the names of the people and houses in it.

Claims are grouped by **topic** (the question they answer: "who killed X?", "whose doing was E?"), each
topic naming what it is `about` (an event, or the one who died), with `holders` (holdings, summed over
its claims: one person can hold two rival claims) and `people` (the notables holding any of them). `renasci claims <run>` writes it to
`analysis/claims.json`.
"""

from __future__ import annotations

from renasci.analysis.truth import Log, judge
from renasci.people import beliefs as B

CLAIM_EVENTS = ("belief.perceived", "belief.told", "belief.corrected", "belief.heard", "belief.news",
                "belief.news_arrived")


def claims_report(events: list[dict], state: dict, geography: dict | None = None) -> dict:
    """The report; `geography` (the run's geography.json, if any) names its places."""
    ents = {e["id"]: e for e in state["entities"]}
    names = {p["id"]: p["name"] for p in (geography or {}).get("places", []) if p.get("name")}
    names.update({i: e["fields"]["name"] for i, e in ents.items() if e["fields"].get("name")})
    houses = {i: e["fields"]["house"] for i, e in ents.items() if e["kind"] == "person" and e["fields"].get("house")}
    by_id = {ev["id"]: ev for ev in events}
    found: dict[str, dict] = {}
    for ev in events:
        if ev["type"] not in CLAIM_EVENTS or not (ev.get("payload") or {}).get("key"):
            continue
        p = ev["payload"]
        c = found.setdefault(p["key"], {"key": p["key"], "claim": p["claim"], "first": ev["date"], "parent": None,
                                        "lies": 0})
        if p.get("drifted_from") and not c["parent"]:
            c["parent"] = p["drifted_from"]
        if ev["type"] == "belief.told" and p.get("intent") == "lie":
            c["lies"] += 1
    holders: dict[str, set[str]] = {}
    for i, e in ents.items():
        if e["kind"] == "person" and e["status"] == "active":
            for k, b in (e["fields"].get("beliefs") or {}).items():
                holders.setdefault(k, set()).add(i)
                found.setdefault(k, _unseen(k, b["claim"]))  # (held, though no event we read put it there)
    shares: dict[str, dict[str, float]] = {}
    for i, e in ents.items():
        for k, s in (e["fields"].get("shares") or {}).items() if e["kind"] == "settlement" else ():
            shares.setdefault(k, {})[i] = s["share"]
            found.setdefault(k, _unseen(k, s["claim"]))  # (a line set straight into a town's talk)
    log = Log(events)
    topics: dict[str, dict] = {}
    people: dict[str, set[str]] = {}
    for k, c in sorted(found.items()):
        claim = c["claim"]
        if claim["pred"] not in B.PREDICATES:
            continue  # (a predicate this engine no longer knows: an old run)
        verdict, basis = judge(claim, events, houses, log=log)
        t = B.topic(claim)
        people.setdefault(t, set()).update(holders.get(k, ()))
        args = claim["args"]
        about = args.get("event") or args.get("victim")
        kind = by_id[about]["type"] if about in by_id else "event" if args.get("event") else "person"
        topic = topics.setdefault(t, {"topic": t, "about": about, "about_type": kind,
                                      "about_name": _about(by_id.get(about), about, names), "claims": []})
        topic["claims"].append({**c, "truth": verdict, "basis": basis, "holders": len(holders.get(k, ())),
                                "shares": dict(sorted(shares.get(k, {}).items())),
                                "text": B.PREDICATES[claim["pred"]].text(args, names)})
    out = []
    for t in topics.values():
        t["claims"].sort(key=lambda c: (-c["holders"], -sum(c["shares"].values()), c["key"]))
        t["holders"] = sum(c["holders"] for c in t["claims"])
        t["people"] = len(people[t["topic"]])
        out.append(t)
    out.sort(key=lambda t: (-t["people"], -t["holders"], t["topic"]))
    return {"topics": out}


def _unseen(key: str, claim: dict) -> dict:
    return {"key": key, "claim": claim, "first": None, "parent": None, "lies": 0}


def _about(ev: dict | None, about: str, names: dict) -> str:
    """What a topic is about, read out: the one who died, or the event and where it happened."""
    if ev is None:
        return names.get(about, about)
    what = ev["type"].replace(".", " ").replace("_", " ")
    return f"the {what} at {names[ev['place']]}" if ev.get("place") in names else f"the {what}"
