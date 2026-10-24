"""The campaign brief (S12 spec §6, #119): a saga (or an event and what followed it) laid out for a game.

Built from the omniscient pack, as a fixed template, with every event cited as a footnote by its id:

1. **Premise:** the title, the span, and the latch point at the heart of it (the run's highest-ranked
   latch point among the subject's people or events: a death or a near miss where a small change would
   have mattered, and the what-if that tries it).
2. **What really happened**, for the GM: a paragraph a year, secrets included, the talk left out.
3. **What people believe:** each question's claims, how many of the subject's people hold each, and
   whether it is true; and each town's talk, as it stood at the end.
4. **Factions:** the houses involved (head, the head's wants, grievances held) and the towns.
5. **NPCs:** the subject's people still alive at the end of the span: wants, wound, a secret (a secret
   deed of theirs), a false belief they hold, ties.
6. **Hooks:** open schemes and grievances not taken up (the pack's threads), lies a truth could
   overturn (false claims held, with the events that tell the truth), and the latch points.
7. **Places:** a plain list.

Deterministic: same run, same bytes. `renasci brief` writes it to `analysis/briefs/`.
"""

from __future__ import annotations

import json

from renasci.analysis.truth import _agents, judge
from renasci.core.calendar import Calendar, Date
from renasci.core.canon import canonical
from renasci.people import beliefs as B
from renasci.story.pack import Run, _head, build
from renasci.story.text import claim_text, reading

SECTIONS = ("Premise", "What really happened", "What people believe", "Factions", "NPCs", "Hooks", "Places")
NPCS = 12
LATCH_HOOKS = 3


def _when(run: Run, date: list, style: str = "year") -> str:
    cal = run.manifest.get("meta", {}).get("calendar")
    return Calendar.from_json(cal).format(Date.from_json(date), style) if cal else f"{date[0]}:{date[1]}"


def _latch(run: Run) -> list[dict]:
    """The run's latch points, all of them (`renasci latch` keeps the top few of the whole run; a subject wants
    its own, however they rank)."""
    if run.folder is None:
        return []
    from renasci.analysis.latch import latch_points
    from renasci.io.runfolder import RunFolder

    cal = run.manifest.get("meta", {}).get("calendar")
    if not cal:
        return []
    return latch_points(run.events, list(RunFolder.open(run.folder).read("hinges")), run.state,
                        days_per_year=Calendar.from_json(cal).days_per_year, limit=10 ** 6)


class Who:
    """People as a GM can tell them apart, as of a date: "X of House H", a commoner by their town then ("Cole of
    Lux Oescus"), and, where that is still shared, their birth year (then their id)."""

    def __init__(self, run: Run, date: list | None):
        self.run = run
        base = {pid: self._base(pid, date) for pid, e in run.ents.items() if e["kind"] == "person"}
        seen: dict[str, list[str]] = {}
        for pid, label in base.items():
            seen.setdefault(label, []).append(pid)
        self.labels = {}
        for label, pids in seen.items():
            if len(pids) == 1:
                self.labels[pids[0]] = label
                continue
            years: dict[str, list[str]] = {}
            for pid in pids:
                born = run.ents[pid]["fields"].get("born")
                years.setdefault(f"{label} (b. {born[1]})" if born else label, []).append(pid)
            for y, ps in years.items():
                for pid in ps:
                    self.labels[pid] = y if len(ps) == 1 else f"{y} [{pid}]"

    def _base(self, pid, date):
        run = self.run
        if run.houses.get(pid):
            return run.names.full(pid)
        town = run.field_at(pid, "place", date) if date else None
        town = town or run.ents[pid]["fields"].get("place") or next((pl for _, pl in reversed(run.residence(pid))), None)
        return f"{run.names(pid)} of {run.names(town)}" if town else run.names(pid)

    def __call__(self, pid: str) -> str:
        return self.labels.get(pid) or self.run.names.full(pid)


def _head_at(run: Run, house: str, date: list | None) -> str | None:
    """Who held a house's headship at a date (the run's successions), else as it ended."""
    office = run.ents.get(house, {}).get("fields", {}).get("headship")
    if not office or not date:
        return _head(run, house)
    succ = [e for e in run.events if e["type"] == "people.succession" and (e.get("payload") or {}).get("office") == office]
    holder = (succ[0]["roles"].get("predecessor") or [None])[0] if succ else _head(run, house)
    for e in succ:
        if e["date"] <= date:
            holder = (e["roles"].get("successor") or [holder])[0]
    return holder


def _alive(run: Run, pid, date) -> bool:
    if not date or pid not in run.ents or run.ents[pid]["kind"] != "person":
        return True
    born, died = run.ents[pid]["fields"].get("born"), run.died.get(pid)
    return (not born or born <= date) and (not died or died > date)


def _threads(run: Run, people: set[str], end: list | None, who) -> list[dict]:
    """What was still open at the end of the span: schemes under way, grievances not taken up (their people
    alive then)."""
    out = []
    for i, e in sorted(run.ents.items()):
        f = e["fields"]
        if e["kind"] != "scheme" or f.get("owner") not in people or not _alive(run, f["owner"], end):
            continue
        started, ended = f.get("started"), f.get("ended")
        if end and (not started or started > end or (ended and ended <= end)):
            continue
        if not end and f.get("state") != "active":
            continue
        whom = f" against {who(f['target'])}" if f.get("target") else ""
        steps = ", ".join(s["action"] for s in f.get("plan") or [])
        out.append({"text": f"{who(f['owner'])} is scheming{whom} ({steps})", "events": [],
                    "people": sorted(x for x in (f["owner"], f.get("target")) if x)})
    for p in sorted(people):
        if not _alive(run, p, end):
            continue
        for g in run.ents[p]["fields"].get("grievances") or []:
            if g.get("answered") or (end and g.get("since") and g["since"] > end) or not _alive(run, g.get("against"), end):
                continue
            out.append({"text": f"{who(p)} holds a grievance against {who(g['against'])}", "people": sorted({p, g["against"]}),
                        "events": [g["event"]] if g.get("event") in run.by_id and (not end or run.by_id[g["event"]]["date"] <= end) else []})
    return sorted(out, key=lambda x: x["text"])


def _sentence(text: str) -> str:
    text = text.strip()
    return text[:1].upper() + text[1:] + ("" if text.endswith((".", "!", "?")) else ".")


def brief(run: Run, subject: tuple[str, str]) -> dict:
    """{"text": the Markdown brief, "npcs": [person ids], "pack": the omniscient pack, "latch": [points in scope]}."""
    pack = build(run, subject)
    names = run.names
    span = pack["span"]
    people = {p["id"]: p for p in pack["people"]}
    in_pack = set(pack["timeline"])
    cited: list[str] = []

    def cite(eid: str) -> str:
        if eid not in cited:
            cited.append(eid)
        return f"[^{eid}]"

    who = Who(run, span[1] if span else None)
    end = span[1] if span else None
    points = sorted((p for p in _latch(run) if p.get("person") in people or p.get("event") in in_pack),
                    key=lambda p: (not (span and span[0] <= p.get("date", []) <= span[1]),  # (the span's own first)
                                   p.get("rank", 99), -p.get("score", 0), p.get("kind", ""), p.get("person", "")))
    out = [f"# Campaign brief: {pack['subject']['title']}", "",
           f"*Generated from the run {run.name}, for the GM. Not canon.*", ""]

    # 1. premise
    out += ["## Premise", ""]
    when = f"from {_when(run, span[0])} to {_when(run, span[1])}" if span else "with no events"
    out.append(f"**{pack['subject']['title']}**, {when}: {len(pack['events'])} events, {len(people)} people.")
    if points:
        p = points[0]
        lead = "Before it began" if span and p["date"] < span[0] else "After it" if span and p["date"] > span[1] else "At its heart"
        out.append(f"\n{lead}: {who(p['person'])} {p['why']}, in {_when(run, p['date'])}"
                   f"{(' ' + cite(p['event'])) if p.get('event') in run.by_id else ''}. "
                   f"What if there had been {p['means']}?")
    out.append("")

    # 2. what really happened
    out += ["## What really happened", ""]
    years: dict[tuple, list[str]] = {}
    for ev in pack["events"]:
        if ev["type"].startswith("belief.") or not ev["text"]:
            continue
        mark = " (secret)" if ev["secret"] else ""
        years.setdefault(tuple(ev["date"][:2]), []).append(f"{_sentence(ev['text'])[:-1]}{mark}. {cite(ev['id'])}")
    for (age, year), lines in sorted(years.items()):
        out += [f"**{_when(run, [age, year, 0])}.** " + " ".join(lines), ""]
    if not years:
        out += ["Nothing that the record tells.", ""]

    # 3. what people believe
    out += ["## What people believe", ""]
    topics: dict[str, dict[str, dict]] = {}
    for b in pack["beliefs"]:
        key = canonical({"pred": b["claim"]["pred"], "args": b["claim"]["args"]})
        row = topics.setdefault(B.topic(b["claim"]), {}).setdefault(key, {"text": b["text"], "truth": b.get("truth"),
                                                                           "holders": []})
        row["holders"].append(b["holder"])
    lies = []
    for t in sorted(topics):
        for key, row in sorted(topics[t].items(), key=lambda kv: (-len(kv[1]["holders"]), kv[1]["text"])):
            held = sorted(set(row["holders"]))
            named = ", ".join(who(h) for h in held[:3]) + (f" and {len(held) - 3} more" if len(held) > 3 else "")
            living = [h for h in held if _alive(run, h, end)]
            dead = "" if len(living) == len(held) else f", {len(held) - len(living)} of them dead by then"
            out.append(f"- *{_sentence(row['text'])}* Held by {len(held)} ({named}{dead}): **{row['truth']}**.")
            if row["truth"] in ("false", "half") and living:  # (a lie only the dead held is no hook)
                lies.append((t, row, json.loads(key), living))
    talk = _talk(run, pack, span)
    out += [f"- In {names(town)}, the talk: *{_sentence(text)}* ({share:.0%} of the town)" for town, text, share in talk]
    if not topics and not talk:
        out.append("- Nobody here holds a view on it.")
    out.append("")

    # 4. factions
    out += ["## Factions", ""]
    houses = sorted({p["house"] for p in pack["people"] if p.get("house")})
    for h in houses:
        head = _head_at(run, h, end)
        f = run.ents.get(head, {}).get("fields", {}) if head else {}
        wants = "; to ".join(w.get("text") or w.get("kind") or str(w) if isinstance(w, dict) else str(w) for w in (f.get("wants") or [])[:3])
        griefs = sorted({f"{who(m)} against {who(g['against'])}" for m in people if run.houses.get(m) == h
                         and _alive(run, m, end) for g in run.ents[m]["fields"].get("grievances") or []
                         if not g.get("answered") and not (end and g.get("since") and g["since"] > end)
                         and _alive(run, g.get("against"), end)})
        out.append(f"- **House {names(h)}**: headed by {who(head) if head else 'no one'}"
                   f"{('; the head wants to ' + wants) if wants else ''}"
                   f"{('; grievances: ' + '; '.join(griefs[:5])) if griefs else ''}.")
    towns = [pl for pl in pack["places"] if run.ents.get(pl["id"], {}).get("kind") == "settlement"]
    for pl in towns:
        out.append(f"- **{pl['name']}** (a town): {sum(1 for e in pack['events'] if e.get('place') == pl['id'])} of the events.")
    if not houses and not towns:
        out.append("- None stand out.")
    out.append("")

    # 5. NPCs
    out += ["## NPCs", ""]
    weight = {pid: sum(1 for e in pack["events"] for ms in e["roles"].values() if pid in ms) for pid in people}
    alive = [pid for pid, p in people.items() if _alive(run, pid, end) and (end or not p["died"])]
    npcs = sorted(alive, key=lambda pid: (-weight[pid], pid))[:NPCS]
    for pid in npcs:
        p, f = people[pid], run.ents[pid]["fields"]
        bits = []
        if p.get("wants"):
            bits.append("wants to " + "; to ".join(w.get("text") or w.get("kind") or "something" if isinstance(w, dict) else str(w)
                                             for w in p["wants"][:3]))
        if p.get("wound") and not (isinstance(p["wound"], dict) and end and (p["wound"].get("since") or end) > end):
            bits.append(f"wound: {p['wound'].get('text') or p['wound'].get('kind') if isinstance(p['wound'], dict) else p['wound']}")
        deeds = [e for e in run.events if e.get("visibility") == "secret" and pid in _agents(e)
                 and not e["type"].startswith(("belief.", "ripple.")) and (not end or e["date"] <= end)]
        secret = next((e for e in deeds if e["id"] in in_pack), deeds[-1] if deeds else None)  # (the subject's own first)
        if secret and reading(secret, names, run.by_id):
            bits.append(f"secret: {reading(secret, names, run.by_id)} {cite(secret['id'])}")
        wrong = next((b["text"] for b in pack["beliefs"] if b["holder"] == pid and b.get("truth") == "false"), None)
        if wrong is None:  # (on the subject first; else any of theirs then)
            held = run.field_at(pid, "beliefs", end) if end else None
            wrong = next((claim_text(b["claim"], names, run.by_id) for k, b in sorted((held or {}).items())
                          if judge(b["claim"], run.events, run.houses, log=run.log)[0] == "false"), None)
        if wrong:
            bits.append(f"believes, wrongly, that {wrong}")
        ties = [f"{t['kind']} of {who(t['other'])}" for t in p.get("ties", []) if t.get("other") in run.ents][:3]
        if ties:
            bits.append("ties: " + "; ".join(ties))
        out.append(f"- **{who(pid)}**{(': ' + '; '.join(bits)) if bits else ''}.")
    if not npcs:
        out.append("- Nobody of note is left alive.")
    out.append("")

    # 6. hooks
    out += ["## Hooks", ""]
    threads = _threads(run, set(people), end, who)
    for th in threads:
        out.append(f"- {th['text']}." + "".join(f" {cite(e)}" for e in th["events"]))
    for t, row, claim, living in lies:
        truth = [e for e in judge(claim, run.events, run.houses, log=run.log)[1]
                 if e in run.by_id and not run.by_id[e]["type"].startswith(("ripple.", "belief."))]
        truth = sorted(truth, key=lambda e: (run.by_id[e]["date"], e))[:4]
        out.append(f"- A lie a truth could overturn: *{_sentence(row['text'])}* Held by {len(living)} still living"
                   + (f"; the truth is in {', '.join(cite(e) for e in truth)}." if truth else "."))
    for p in points[:LATCH_HOOKS]:
        out.append(f"- What if: {who(p['person'])} {p['why']} ({_when(run, p['date'])}); "
                   f"try {p['means']} (`{p['kind']}`).")
    if out[-1] == "":
        out.append("- No open threads.")
    out.append("")

    # 7. places
    out += ["## Places", ""] + [f"- {pl['name']}" for pl in pack["places"]] + ([] if pack["places"] else ["- None named."])
    out.append("")

    # footnotes
    for eid in cited:
        ev = run.by_id[eid]
        out.append(f"[^{eid}]: `{eid}`, {_when(run, ev['date'], 'season')}, {ev['type']}.")
    return {"text": "\n".join(out) + "\n", "npcs": npcs, "pack": pack, "latch": points, "threads": threads}


def _talk(run: Run, pack: dict, span) -> list[tuple[str, str, float]]:
    """Each of the subject's towns: its largest share on each question the pack's beliefs are about."""
    if not span:
        return []
    asked = {B.topic(b["claim"]) for b in pack["beliefs"]}
    out = []
    for pl in pack["places"]:
        shares = run.field_at(pl["id"], "shares", span[1])
        best: dict[str, tuple] = {}
        for k, s in sorted((shares or {}).items()):
            t = B.topic(s["claim"])
            if t in asked and (t not in best or s["share"] > best[t][0]):
                best[t] = (s["share"], claim_text(s["claim"], run.names, run.by_id))
        out += [(pl["id"], text, share) for t, (share, text) in sorted(best.items())]
    return out
