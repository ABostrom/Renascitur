"""The canon-check benchmark (S12 spec §4): how much of what prose gets wrong the check finds.

**Seeded set:** claims true in the run, mutated by kind (`KINDS`: a wrong killer, a wrong victim who
lived, a wrong year, a wrong house, a swapped spouse, a dead person acting), a fixed number per kind
chosen by keyed draws (the candidates ordered by the digest of their key), rendered by the paraphrase
table (`renasci.story.paraphrase`), one sentence each. **Recall** is the share where the check finds a
contradiction. The same number of true claims per kind (a killing, a death's year, a member of a house,
a marriage, a person acting, a succession) are rendered the same way: a **false alarm** is a true sentence
with a contradiction or an ambiguous name in it.

People are rendered with what the prose would state to name them (their house, else their town), and
only claims whose people that names (with the year, where one is stated, as a tie-break) are drawn:
the check reports the rest as ambiguous, which is a different finding.

**Held-out set:** free prose with labelled contradictions (`tests/fixtures/heldout_prose.json`), written
once in a session about the M4 run. Its recall is reported, never gated.
"""

from __future__ import annotations

import json
from pathlib import Path

from renasci.core.canon import digest
from renasci.story import paraphrase
from renasci.story.check import check

KINDS = ("wrong_killer", "wrong_victim", "wrong_year", "wrong_house", "swapped_spouse", "dead_acting")
TRUE_KINDS = ("killed", "died_in", "member", "married", "alive_at", "ruled")
PER_KIND = 10
HELDOUT = Path(__file__).resolve().parents[3] / "tests" / "fixtures" / "heldout_prose.json"


class World:
    """What the benchmark needs of a run: who is who, and who prose could name."""

    def __init__(self, run):
        self.run = run
        cal = run.manifest["meta"]["calendar"]["ages"]
        self.age = {a["index"]: (a["abbrev"], a["name"]) for a in cal}
        self.people = {i: e["fields"] for i, e in run.ents.items() if e["kind"] == "person"}
        self.first, self.last = run.events[0]["date"][1], run.events[-1]["date"][1]

    def home(self, p) -> str | None:
        f = self.people[p]
        return f.get("place") or next((pl for _, pl in reversed(self.run.residence(p))), None)

    def towns(self, p) -> set:
        return {pl for _, pl in self.run.residence(p)} | ({self.people[p]["place"]} if self.people[p].get("place") else set())

    def alive(self, p, year) -> bool:
        born, died = self.people[p].get("born"), self.run.died.get(p)
        return (not born or born[1] <= year) and (not died or died[1] >= year)

    def nameable(self, p, year=None) -> bool:
        """Whether "Name of House H" (or "Name of Town") names `p` alone (the year as a tie-break)."""
        f = self.people[p]
        same = [q for q, g in self.people.items() if g["name"] == f["name"]]
        if f.get("house"):
            same = [q for q in same if self.people[q].get("house") == f["house"]]
        else:
            town = self.home(p)
            if not town:
                return False
            same = [q for q in same if not self.people[q].get("house") and town in self.towns(q)]
        if len(same) > 1 and year is not None:
            same = [q for q in same if self.alive(q, year)] or same
        return same == [p]

    def named(self, p, variant, first=False, house=None) -> str:
        f = self.people[p]
        h = house or f.get("house")
        return paraphrase.person(f["name"], self.run.names(h) if h else None,
                                 None if h else self.run.names(self.home(p)), variant, first)

    def date(self, year, age=4):
        abbrev, name = self.age[age]
        return (abbrev, name, year)


def _keyed(items, kind):
    return sorted(items, key=lambda x: digest([kind, x]))


def _kills(run) -> list[tuple]:
    from renasci.analysis.truth import judge

    out = []
    for e in run.events:
        if e["type"] != "people.death":
            continue
        v = e["roles"]["deceased"][0]
        killers = sorted(k for k in set(e["roles"].get("killer") or []) | {
            a for kind, ref in e.get("causes") or [] if kind == "event" and ref in run.by_id
            and run.by_id[ref]["type"] == "people.action" for a in run.by_id[ref]["roles"].get("actor", [])}
            if k in run.ents and judge({"pred": "killed", "args": {"victim": v, "by": k}}, run.events, log=run.log)[0] == "true")
        if killers:
            out.append((v, killers[0], e["date"][1]))
    return out


def items(run) -> dict[str, list[dict]]:
    """{"seeded": [{kind, text}], "unseeded": [{kind, text}]}: the benchmark's sentences, the same for a run."""
    w = World(run)
    kills = _kills(run)
    deaths = [(e["roles"]["deceased"][0], e["date"][1]) for e in run.events if e["type"] == "people.death"]
    marriages = [tuple(e["roles"]["spouse"]) for e in run.events if e["type"] == "people.marriage"]
    spouses = {p for m in marriages for p in m}
    living = sorted(p for p in w.people if p not in run.died)
    seeded, unseeded = [], []

    def take(kind, pool, make, out):
        n = 0
        for i, x in enumerate(_keyed(pool, kind)):
            got = make(x, int(digest([kind, x, "v"]), 16) % 997)
            if got:
                out.append({"kind": kind, "text": got, "key": list(x) if isinstance(x, tuple) else x})
                n += 1
            if n == PER_KIND:
                break

    def wrong_killer(k, v):
        victim, killer, year = k
        others = [p for p in _keyed(w.people, f"killer-{victim}") if p != killer and w.alive(p, year) and w.nameable(p, year)]
        if not (others and w.nameable(victim, year)):
            return None
        return paraphrase.render("killed", {"by": w.named(others[0], v, True), "victim": w.named(victim, v),
                                            "date": w.date(year)}, v)

    def wrong_victim(k, v):
        victim, killer, year = k
        alive = [p for p in _keyed(living, f"victim-{victim}") if w.nameable(p, year) and w.alive(p, year)]
        if not (alive and w.nameable(killer, year)):
            return None
        return paraphrase.render("killed", {"by": w.named(killer, v, True), "victim": w.named(alive[0], v),
                                            "date": w.date(year)}, v)

    def wrong_year(d, v):
        who, year = d
        if not w.nameable(who, year):
            return None
        off = year + 3 if year + 3 <= w.last else year - 3
        if off < w.first:
            return None
        return paraphrase.render("died_in", {"who": w.named(who, v, True), "date": w.date(off)}, v)

    def wrong_house(d, v):
        who, year = d
        h = w.people[who].get("house")
        if not h or not w.nameable(who, year):
            return None
        names_in = {hh: {g["name"] for g in w.people.values() if g.get("house") == hh} for hh in sorted(run.names.houses)}
        # (half the time a house with someone else of that name, who the prose then names instead; else one
        # with nobody of that name, and the house itself is the error)
        shared = v % 2 == 0
        other = next((hh for hh in _keyed(sorted(names_in), f"house-{who}") if hh != h
                      and (w.people[who]["name"] in names_in[hh]) == shared), None)
        if other is None:
            return None
        return paraphrase.render("died_in", {"who": w.named(who, v, True, house=other), "date": w.date(year)}, v)

    def swapped(m, v):
        a, b = m
        if not (w.nameable(a) and w.nameable(b)):
            return None
        c = next((p for p in _keyed(sorted(spouses), f"spouse-{a}") if p not in (a, b) and w.nameable(p)
                  and not any({a, p} == set(x) for x in marriages)), None)
        if c is None:
            return None
        return paraphrase.render("married", {"a": w.named(a, v, True), "b": w.named(c, v)}, v)

    def dead_acting(d, v):
        who, year = d
        if year + 2 > w.last or not w.nameable(who):  # (named without the year: the year would hide them)
            return None
        return paraphrase.render("alive_at", {"who": w.named(who, v, True), "date": w.date(year + 2)}, v)

    for kind, pool, make in (("wrong_killer", kills, wrong_killer), ("wrong_victim", kills, wrong_victim),
                             ("wrong_year", deaths, wrong_year), ("wrong_house", deaths, wrong_house),
                             ("swapped_spouse", marriages, swapped), ("dead_acting", deaths, dead_acting)):
        take(kind, pool, make, seeded)

    def t_killed(k, v):
        victim, killer, year = k
        if not (w.nameable(victim, year) and w.nameable(killer, year)):
            return None
        return paraphrase.render("killed", {"by": w.named(killer, v, True), "victim": w.named(victim, v), "date": w.date(year)}, v)

    def t_died(d, v):
        who, year = d
        return paraphrase.render("died_in", {"who": w.named(who, v, True), "date": w.date(year)}, v) if w.nameable(who, year) else None

    def t_member(d, v):
        who, year = d
        return t_died(d, v) if w.people[who].get("house") else None

    def t_married(m, v):
        a, b = m
        return paraphrase.render("married", {"a": w.named(a, v, True), "b": w.named(b, v)}, v) if w.nameable(a) and w.nameable(b) else None

    acts = sorted({(e["roles"]["actor"][0], e["date"][1]) for e in run.events if e["type"] == "people.action"})

    def t_acting(x, v):
        who, year = x
        return paraphrase.render("alive_at", {"who": w.named(who, v, True), "date": w.date(year)}, v) if w.nameable(who, year) else None

    succ = [(e["roles"]["successor"][0], (e.get("payload") or {}).get("office"), e["date"][1])
            for e in run.events if e["type"] == "people.succession" and e["roles"].get("successor")]

    def t_ruled(s, v):
        who, office, year = s
        house = run.ents.get(office, {}).get("fields", {}).get("house")
        if not house or not w.nameable(who, year):
            return None
        return paraphrase.render("ruled", {"who": w.named(who, v, True), "house": f"House {run.names(house)}", "date": w.date(year)}, v)

    for kind, pool, make in (("killed", kills, t_killed), ("died_in", deaths, t_died), ("member", deaths, t_member),
                             ("married", marriages, t_married), ("alive_at", acts, t_acting), ("ruled", succ, t_ruled)):
        take(kind, pool, make, unseeded)
    return {"seeded": seeded, "unseeded": unseeded}


def _found(run, text, lexicon) -> tuple[bool, bool]:
    rep = check(run, text, lexicon=lexicon)
    got = [c["finding"] for s in rep["sentences"] for c in s["claims"]]
    return "contradiction" in got, bool(sum(len(s["unresolved"]) for s in rep["sentences"]))


def run_bench(run) -> dict:
    """Recall on the seeded set (by kind), false alarms on the unseeded set, and the held-out recall."""
    from renasci.story.prose import Lexicon

    lex = Lexicon(run)
    sets = items(run)
    by_kind: dict[str, list[int]] = {}
    missed = []
    for it in sets["seeded"]:
        hit = _found(run, it["text"], lex)[0]
        by_kind.setdefault(it["kind"], [0, 0])
        by_kind[it["kind"]][0] += hit
        by_kind[it["kind"]][1] += 1
        if not hit:
            missed.append(it["text"])
    alarms = [it["text"] for it in sets["unseeded"] if any(_found(run, it["text"], lex))]
    seeded = sum(v[1] for v in by_kind.values())
    out = {"seeded": seeded, "recall": round(sum(v[0] for v in by_kind.values()) / max(seeded, 1), 3),
           "by_kind": {k: round(a / max(n, 1), 3) for k, (a, n) in sorted(by_kind.items())},
           "unseeded": len(sets["unseeded"]), "false_alarms": len(alarms),
           "precision": round(1 - len(alarms) / max(len(sets["unseeded"]), 1), 3), "missed": missed, "alarms": alarms}
    if HELDOUT.exists():
        held = json.loads(HELDOUT.read_text(encoding="utf-8"))
        labelled = [h for h in held["sentences"] if h["contradiction"]]
        caught = [h for h in labelled if _found(run, h["text"], lex)[0]]
        alarms_h = [h for h in held["sentences"] if not h["contradiction"] and _found(run, h["text"], lex)[0]]
        out["heldout"] = {"sentences": len(held["sentences"]), "contradictions": len(labelled),
                          "recall": round(len(caught) / max(len(labelled), 1), 3), "false_alarms": len(alarms_h),
                          "missed": [h["text"] for h in labelled if h not in caught]}
    return out
