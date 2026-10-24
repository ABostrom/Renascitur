"""Canon checks (S12 spec §4, #117): prose read into claims (`renasci.story.prose`) and judged against a run.

**Judging.** The S6 predicates go through `truth.judge`, extended: a `killed` whose victim never died (in
the run) is false, not unknown; one dated to another year than the death is false; one that blames the
killer's house is half true. The new predicates read the event log and the final state:
- `married(a, b)`: a marriage event of the two;
- `died_in(who)` at a date: the death's year;
- `member(who, of)` / `lived_in(who, of)`: only made when no one of that name is of that house or town
  (so: false);
- `ruled(who, house)` from a date: the house's headship passed to them that year (or they held it when
  the run began);
- `alive_at(who)` at a date: born by that year and not dead before it.

**Verdicts**, by whether the author (`pov`) believed the claim:

|         | believed     | not believed                                     |
|---------|--------------|--------------------------------------------------|
| true    | consistent   | consistent if they could know it; else a **leak** |
| half    | consistent   | a **half** finding                               |
| false   | consistent (their account) | a **contradiction**                 |
| unknown | consistent   | an **invention**: listed, allowed                |

Omniscient believes nothing and can know everything. Mentions that didn't resolve are **ambiguous**
findings, with their candidates. `check(run, text, pov)` returns the report; `renasci check-prose`
writes it to `analysis/checks/<digest of the text>.json`.
"""

from __future__ import annotations

from renasci.analysis.truth import _agents, judge
from renasci.core.canon import canonical, digest_text
from renasci.story.pack import _head, _knows, _pov
from renasci.story.prose import Lexicon, extract

SCHEMA = "renasci.check/1"
ORDER = ("contradiction", "leak", "half", "ambiguous", "invention", "consistent")
MAX_TEXT = 256 * 1024


def _year(date) -> tuple | None:
    return tuple(date[:2]) if date and date[0] is not None else None


def verdict(run, claim: dict) -> tuple[str, list[str]]:
    """(true | false | half | unknown, the events it rests on)."""
    pred, a, when = claim["pred"], claim["args"], _year(claim.get("date"))
    deaths = run.log.deaths
    if pred == "killed":
        victim, by = a.get("victim"), a.get("by")
        if victim not in run.ents:
            return "unknown", []
        if not deaths.get(victim):
            return "false", []  # (they never died)
        death = deaths[victim][0]
        v, basis = judge({"pred": "killed", "args": {"victim": victim, "by": by}}, run.events, run.houses, log=run.log)
        if v == "false" and by in run.names.houses and any(
                judge({"pred": "killed", "args": {"victim": victim, "by": m}}, run.events, log=run.log)[0] == "true"
                for m, h in sorted(run.houses.items()) if h == by):
            v = "half"  # (the house, for what one of its own did)
        if when and tuple(death["date"][:2]) != when:
            v = "false"
        return v, basis
    if pred in ("caused", "fault"):
        return judge({"pred": pred, "args": a}, run.events, run.houses, log=run.log)
    if pred == "married":  # (the run's marriages, and the spouses it began with)
        x, y = a.get("a"), a.get("b")
        mine = [e for e in run.events if e["type"] == "people.marriage" and {x, y} & set(e["roles"].get("spouse", []))]
        both = [e["id"] for e in mine if {x, y} <= set(e["roles"].get("spouse", []))]
        spouse = {p: run.ents.get(p, {}).get("fields", {}).get("spouse") for p in (x, y)}
        if both or spouse[x] == y or spouse[y] == x:
            return "true", both
        if mine or spouse[x] or spouse[y]:
            return "false", [e["id"] for e in mine]  # (married, but to someone else)
        return "unknown", []
    if pred == "died_in":
        d = deaths.get(a.get("who"))
        if not d:
            return "false", []
        return ("true" if not when or tuple(d[0]["date"][:2]) == when else "false"), [d[0]["id"]]
    if pred in ("member", "lived_in"):
        return "false", []  # (made only when nobody of that name is of that house or town)
    if pred == "ruled":
        return _ruled(run, a.get("who"), a.get("house"), when, a.get("before"))
    if pred == "alive_at":
        f = run.ents.get(a.get("who"), {}).get("fields", {})
        born, d = f.get("born"), deaths.get(a.get("who"))
        if not when:
            return "unknown", []
        ok = (not born or tuple(born[:2]) <= when) and (not d or tuple(d[0]["date"][:2]) >= when)
        return ("true", []) if ok else ("false", [d[0]["id"]] if d and tuple(d[0]["date"][:2]) < when else [])
    return "unknown", []


def _ruled(run, who, house, when, before=None):
    office = run.ents.get(house, {}).get("fields", {}).get("headship")
    if not office:
        return "unknown", []
    succ = [e for e in run.events if e["type"] == "people.succession" and (e.get("payload") or {}).get("office") == office]
    first = (succ[0]["roles"].get("predecessor") or [None])[0] if succ else run.ents[office]["fields"].get("holder")
    began = {} if first is None else {first: tuple(run.events[0]["date"][:2])}
    after: dict[str, str | None] = {}
    for e in succ:
        for s in e["roles"].get("successor") or []:
            began.setdefault(s, tuple(e["date"][:2]))
            after.setdefault(s, (e["roles"].get("predecessor") or [None])[0])
    basis = [e["id"] for e in succ if who in (e["roles"].get("successor") or [])]
    if who not in began:
        return "false", [e["id"] for e in succ]
    if before is not None and after.get(who) != before:
        return "false", basis  # (they succeeded someone else)
    return ("true" if not when or began[who] == when or (who == first and when <= began[who]) else "false"), basis


# ------------------------------------------------------------ the author


class Author:
    """What a point of view believed (any claim it ever held, or a lie it told) and could know."""

    def __init__(self, run, pov: str):
        self.run, self.pov = run, pov
        self.view, minds = _pov(run, pov)
        self.minds = minds or []
        held: list[dict] = []
        if self.view["kind"] == "settlement":
            for _, old, new in run.history.get((pov, "shares"), []):
                for s in (new or {}).values():
                    held.append(s["claim"])
            held += [s["claim"] for s in (run.ents[pov]["fields"].get("shares") or {}).values()]
        for p in self.minds:
            for _, old, new in run.history.get((p, "beliefs"), []):
                held += [b["claim"] for b in (new or {}).values()]
            held += [b["claim"] for b in (run.ents[p]["fields"].get("beliefs") or {}).values()]
        tellers = set(self.minds) if self.view["kind"] == "person" else ({_head(run, pov)} if self.view["kind"] == "house" else set())
        held += [e["payload"]["claim"] for e in run.events if e["type"] == "belief.told"
                 and e["payload"].get("intent") == "lie" and tellers & set(e["roles"].get("teller", []))]
        self.held = {canonical({"pred": c["pred"], "args": c["args"]}) for c in held}
        self.origins = {b.get("from") for p in self.minds for b in (run.ents[p]["fields"].get("beliefs") or {}).values()} - {None}

    def believed(self, claim: dict) -> bool:
        return canonical({"pred": claim["pred"], "args": claim["args"]}) in self.held

    def could_know(self, claim: dict, basis: list[str]) -> bool:
        """Whether the author could know a claim: an event it rests on (for whose doing something was, an
        event that names them) is one they could know."""
        if self.view["kind"] == "omniscient" or not basis:
            return True
        evs = [self.run.by_id[e] for e in basis if e in self.run.by_id]
        if claim["pred"] in ("caused", "fault"):
            who = claim["args"].get("by") or claim["args"].get("party")
            named = [e for e in evs if who in _agents(e) or any(self.run.houses.get(m) == who for m in _agents(e))]
            evs = named or evs
        if self.view["kind"] == "settlement":
            return any(e.get("visibility") != "secret" and e.get("place") == self.pov for e in evs)
        return any(_knows(self.run, p, e, self.origins) for p in self.minds for e in evs)


def finding(v: str, believed: bool, knowable: bool) -> str:
    if believed:
        return "consistent"
    return {"true": "consistent" if knowable else "leak", "half": "half", "false": "contradiction",
            "unknown": "invention"}[v]


def check(run, text: str, pov: str = "omniscient", lexicon: Lexicon | None = None) -> dict:
    if len(text.encode("utf-8")) > MAX_TEXT:
        raise ValueError(f"the text is over {MAX_TEXT // 1024} KB")
    author = Author(run, pov)
    sentences = extract(run, text, lexicon)
    counts = dict.fromkeys(ORDER, 0)
    for s in sentences:
        for c in s["claims"]:
            v, basis = verdict(run, c)
            c["verdict"], c["events"] = v, sorted(set(basis))
            c["finding"] = finding(v, author.believed(c), author.could_know(c, c["events"]))
            counts[c["finding"]] += 1
        for u in s["unresolved"]:
            u["finding"] = "ambiguous"
            counts["ambiguous"] += 1
    return {"schema": SCHEMA, "run": run.name, "pov": author.view, "text": digest_text(text, 16),
            "counts": counts, "sentences": sentences}


def findings(report: dict) -> list[dict]:
    """Every finding but `consistent`, contradictions first, then in the text's order."""
    out = []
    for s in report["sentences"]:
        for c in s["claims"]:
            if c["finding"] != "consistent":
                out.append({"n": s["n"], "sentence": s["text"], **c})
        for u in s["unresolved"]:
            out.append({"n": s["n"], "sentence": s["text"], **u})
    return sorted(out, key=lambda f: (ORDER.index(f["finding"]), f["n"]))

