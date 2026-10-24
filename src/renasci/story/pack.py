"""Context packs (S12 spec §2, #115): one subject, from one point of view, as JSON a writer can use.

A **subject** is an arc or saga (from the run's `analysis/stories.json`), a person (over their life), an
event (it, its causes to depth 2 and its consequences to depth 3: the ward failure, a ripple's work, is
in no saga), or a claims topic (the event it's about, and every competing claim). Every event in a pack
brings its causes to depth 2, so the why travels with the what; bookkeeping events are left out.

A **point of view** is a filter. `omniscient` holds everything, secrets too, and each belief's verdict.
A **person** holds what they could know: events where they hold a role; public events where they lived
at the time (their residence over time, from the run's `place` changes); secret events only where a
belief of theirs walks back to them; and their beliefs as they stood at the end of the subject's span,
with no verdicts (they don't know which are true). Without beliefs in the world, nobody learns of
anything beyond their town, except the deaths and successions of their own house. A **house** is the
union of its members' (rival claims on one topic: the head's, else the firmest, then the lower key). A
**settlement** holds the public events there and its masses' talk as it stood then.

`build(run, subject, pov)` returns the pack; `renasci pack` writes it to `analysis/packs/` after the
schema check (`renasci.story.schema`). Same run, same bytes.
"""

from __future__ import annotations

import bisect
import gzip
import json
from pathlib import Path

from renasci.analysis.truth import Log, judge
from renasci.core.canon import canonical
from renasci.people import beliefs as B
from renasci.story.text import Names, claim_text, noun, reading
from renasci.story.trace import origin

SCHEMA = "renasci.pack/1"
CAUSE_DEPTH, CONSEQUENCE_DEPTH = 2, 3
SECRET = "secret"
KIN = ("mother", "father", "spouse", "children")
DELTA_FIELDS = ("place", "beliefs", "shares")


class Run:
    """A finished run, read once: events, state, state changes (where people lived, what they believed,
    what towns said, indexed by entity and field), stories, names. `Run(folder)` reads a run folder;
    `Run.of(...)` builds one from parts (tests)."""

    def __init__(self, folder):
        from renasci.io.runfolder import RunFolder

        folder = Path(folder)
        rf = RunFolder.open(folder)
        if rf.manifest["meta"].get("complete") is False:
            raise ValueError(f"{folder.name} hasn't finished")
        geo_file = folder / "geography.json"
        stories = folder / "analysis" / "stories.json"
        self._setup(folder.name, list(rf.read("events")),
                    json.loads(gzip.decompress((folder / "state.json.gz").read_bytes())),
                    (d for d in rf.read("state_deltas") if d["field"] in DELTA_FIELDS),
                    json.loads(stories.read_text(encoding="utf-8")) if stories.exists() else None,
                    json.loads(geo_file.read_text(encoding="utf-8")) if geo_file.exists() else None, rf.manifest)
        self.folder = folder

    @classmethod
    def of(cls, name, events, state, deltas, stories=None, geography=None) -> "Run":
        run = cls.__new__(cls)
        run._setup(name, list(events), state, deltas, stories, geography, {"engine": None, "meta": {}})
        run.folder = None
        return run

    def _setup(self, name, events, state, deltas, stories, geography, manifest):
        self.name, self.events, self.state, self.geography, self.manifest = name, events, state, geography, manifest
        self.by_id = {e["id"]: e for e in events}
        self.ents = {e["id"]: e for e in state["entities"]}
        self.names = Names(state, geography)
        self.history: dict[tuple[str, str], list[tuple[list, object, object]]] = {}
        for d in deltas:  # (in the order they happened)
            if d["field"] in DELTA_FIELDS:
                self.history.setdefault((d["entity"], d["field"]), []).append((d["date"], d.get("old"), d.get("new")))
        self.consequences: dict[str, list[str]] = {}
        self.involves: dict[str, list[str]] = {}
        self.died: dict[str, list] = {}
        for e in events:
            for kind, ref in e.get("causes") or []:
                if kind == "event":
                    self.consequences.setdefault(ref, []).append(e["id"])
            for members in (e.get("roles") or {}).values():
                for m in members:
                    self.involves.setdefault(m, []).append(e["id"])
            if e["type"] == "people.death":
                for p in e["roles"].get("deceased", []):
                    self.died.setdefault(p, e["date"])
        if stories is None:
            from renasci.analysis.stories import stories as find

            stories = find(events, state)
        self.stories = stories
        self.houses = {i: e["fields"]["house"] for i, e in self.ents.items()
                       if e["kind"] == "person" and e["fields"].get("house")}
        self.log = Log(events)

    def field_at(self, entity: str, field: str, date: list) -> object:
        """A field's value as it stood at the end of `date`: the last change on or before it; before its first
        change, what that change replaced; with no changes at all, the final state's."""
        changes = self.history.get((entity, field))
        if not changes:
            return self.ents.get(entity, {}).get("fields", {}).get(field)
        i = bisect.bisect_right([c[0] for c in changes], date)
        return changes[i - 1][2] if i else changes[0][1]

    def residence(self, person: str) -> list[tuple[list, str]]:
        """Where a person lived, over time: [(from date, place)]."""
        return [(d, new) for d, _, new in self.history.get((person, "place"), []) if new]

    def holders(self) -> list[str]:
        """Everyone whose beliefs ever changed."""
        return sorted({e for e, f in self.history if f == "beliefs"})


# ------------------------------------------------------------ subjects


def _subject_events(run: Run, kind: str, ident: str) -> tuple[dict, set[str], set[str]]:
    """(subject, its own events, its people)."""
    if kind in ("arc", "saga"):
        arcs = {a["id"]: a for a in run.stories["arcs"]}
        if kind == "saga":
            saga = next((s for s in run.stories["sagas"] if s["id"] == ident), None)
            if saga is None:
                raise ValueError(f"no saga {ident} in {run.name}")
            chosen = [arcs[a] for a in saga["arcs"] if a in arcs]
            title = saga["title"]
        else:
            if ident not in arcs:
                raise ValueError(f"no arc {ident} in {run.name}")
            chosen, title = [arcs[ident]], arcs[ident]["title"]
        evs, people = set(), set()
        for a in chosen:
            evs |= set(a.get("beats", [])) | {t["event"] for t in a.get("timeline", [])}
            if (a.get("born_of") or [None])[0] == "event":
                evs.add(a["born_of"][1])
            people |= set(a.get("people", []))
        return {"kind": kind, "id": ident, "title": title}, evs, people
    if kind == "person":
        if ident not in run.ents or run.ents[ident]["kind"] != "person":
            raise ValueError(f"no person {ident} in {run.name}")
        f = run.ents[ident]["fields"]
        people = {ident} | {k for r in KIN for k in ([f.get(r)] if r != "children" else (f.get(r) or [])) if k}
        evs = set(run.involves.get(ident, []))
        return {"kind": kind, "id": ident, "title": f"The life of {run.names.full(ident)}"}, evs, people
    if kind == "event":
        if ident not in run.by_id:
            raise ValueError(f"no event {ident} in {run.name}")
        evs, frontier = {ident}, [ident]
        for _ in range(CONSEQUENCE_DEPTH):
            frontier = [c for e in frontier for c in run.consequences.get(e, []) if c not in evs]
            evs |= set(frontier)
        people = {m for e in evs for ms in run.by_id[e].get("roles", {}).values() for m in ms if m in run.ents
                  and run.ents[m]["kind"] == "person"}
        return {"kind": kind, "id": ident, "title": reading(run.by_id[ident], run.names) or ident}, evs, people
    if kind == "topic":
        about = ident.split(":", 1)[1] if ":" in ident else ident
        if about in run.by_id:
            sub, evs, people = _subject_events(run, "event", about)
            title = f"Whose doing was {_noun(run, about)}?"
        else:  # (a "who killed X" topic: the person who died)
            sub, evs, people = _subject_events(run, "person", about)
            evs = {e for e in evs if run.by_id[e]["type"] == "people.death"} or evs
            title = f"Who killed {run.names.full(about)}?"
        return {"kind": "topic", "id": ident, "title": title}, evs, people
    raise ValueError(f"a subject is arc, saga, person, event or topic, not {kind!r}")


def _noun(run: Run, event: str) -> str:
    return noun(run.by_id.get(event))


def _with_causes(run: Run, evs: set[str]) -> set[str]:
    out, frontier = set(evs), list(evs)
    for _ in range(CAUSE_DEPTH):
        frontier = [ref for e in frontier for kind, ref in (run.by_id.get(e, {}).get("causes") or [])
                    if kind == "event" and ref in run.by_id and ref not in out]
        out |= set(frontier)
    return out


# ------------------------------------------------------------ points of view


def _members(run: Run, house: str) -> list[str]:
    return sorted(p for p, h in run.houses.items() if h == house)


def _knows(run: Run, person: str, ev: dict, believed_from: set[str]) -> bool:
    if any(person in ms for ms in (ev.get("roles") or {}).values()):
        return True
    if person in run.died and ev["date"] > run.died[person]:
        return False  # (the dead learn nothing more)
    if ev.get("visibility") == SECRET:
        return ev["id"] in believed_from
    if ev["type"] in ("people.death", "people.succession") and run.houses.get(person):
        house = run.houses[person]
        whose = ev["roles"].get("deceased", []) + ev["roles"].get("successor", []) + ev["roles"].get("predecessor", [])
        if any(run.houses.get(m) == house for m in whose):
            return True  # (a house's own deaths and successions are known everywhere)
    lived = [p for d, p in run.residence(person) if d <= ev["date"]]
    return bool(lived) and ev.get("place") == lived[-1]


def _until(run: Run, person: str, end: list) -> list:
    """The end of the span, or the person's death if it came first (their beliefs as they died with them)."""
    died = run.died.get(person)
    return min(end, died) if died else end


def _beliefs_of(run: Run, holder: str, end: list) -> dict:
    held = run.field_at(holder, "beliefs", end)
    return held if isinstance(held, dict) else {}


def _belief_rows(run: Run, holder: str, held: dict, verdicts: bool) -> list[dict]:
    rows = []
    for k, b in sorted(held.items()):
        row = {"holder": holder, "key": k, "claim": b["claim"], "conf": round(float(b["conf"]), 3),
               "text": claim_text(b["claim"], run.names, run.by_id),
               "origin": origin(run.by_id.get, b["from"]) if b.get("from") else None}
        if verdicts:
            row["truth"] = judge(b["claim"], run.events, run.houses, log=run.log)[0]
        rows.append(row)
    return rows


def _pov(run: Run, pov: str) -> tuple[dict, list[str] | None]:
    """The point of view: (its description, the people whose minds it reads; None for omniscient)."""
    if pov == "omniscient":
        return {"kind": "omniscient", "id": None, "name": "omniscient"}, None
    e = run.ents.get(pov)
    if e is None:
        raise ValueError(f"no {pov} in {run.name} to see from")
    if e["kind"] == "person":
        return {"kind": "person", "id": pov, "name": run.names.full(pov)}, [pov]
    if e["kind"] == "settlement":
        return {"kind": "settlement", "id": pov, "name": run.names(pov)}, []
    if pov in set(run.houses.values()) or e["kind"] == "house":
        return {"kind": "house", "id": pov, "name": f"House {run.names(pov)}"}, _members(run, pov)
    raise ValueError(f"{pov} is a {e['kind']}: a point of view is a person, a house or a settlement")


# ------------------------------------------------------------ the pack


def _person_row(run: Run, pid: str, roles: dict[str, set[str]]) -> dict:
    f = run.ents[pid]["fields"]
    died = next((run.by_id[e]["date"] for e in run.involves.get(pid, [])
                 if run.by_id[e]["type"] == "people.death" and pid in run.by_id[e]["roles"].get("deceased", [])), None)
    ties = []
    for t in f.get("ties") or []:
        te = run.ents.get(t, {}).get("fields", {})
        if te and not te.get("ended"):
            ties.append({"other": te["b"] if te.get("a") == pid else te.get("a"), "kind": te.get("kind")})
    return {"id": pid, "name": run.names(pid), "house": f.get("house"), "born": f.get("born"), "died": died,
            "traits": f.get("traits") or {}, "wants": f.get("wants") or [], "wound": f.get("wound"),
            "ties": sorted(ties, key=lambda x: (x["kind"] or "", x["other"] or "")), "roles": sorted(roles.get(pid, {"involved"}))}


ROLE_NAMES = {"owner": "lead", "target": "target", "deceased": "victim", "killer": "killer", "actor": "actor",
              "witness": "witness", "leader": "lead", "ordered_by": "schemer"}  # (no verdicts: a keeper is "involved")


def _told(run: Run, own: set[str]) -> set[str]:
    return {e for e in _with_causes(run, own) if reading(run.by_id[e], run.names, run.by_id)}


def _end(run: Run, evs: set[str]) -> list:
    return max((run.by_id[e]["date"] for e in evs), default=[0, 0, 0])


def end_of(run: Run, subject: tuple[str, str]) -> list:
    """The date a subject's beliefs are taken at, whatever the point of view: its last event's."""
    return _end(run, _told(run, _subject_events(run, *subject)[1]))


def build(run: Run, subject: tuple[str, str], pov: str = "omniscient") -> dict:
    sub, own, people = _subject_events(run, *subject)
    view, minds = _pov(run, pov)
    evs = _told(run, own)
    end = _end(run, evs)
    on_topic = subject[1] if subject[0] == "topic" else None

    def relevant(held: dict) -> dict:
        if on_topic:  # (a topic's pack: that question's claims, nothing else)
            return {k: b for k, b in held.items() if B.topic(b["claim"]) == on_topic}
        about = evs | people
        return {k: b for k, b in held.items() if set(v for v in b["claim"]["args"].values() if isinstance(v, str)) & about}

    beliefs: list[dict] = []
    if minds is None:  # (omniscient: what the subject's people believed about it, or, for a topic, everyone)
        for p in (run.holders() if on_topic else sorted(people)):
            beliefs += _belief_rows(run, p, relevant(_beliefs_of(run, p, _until(run, p, end))), verdicts=True)
    elif view["kind"] == "settlement":
        shares = run.field_at(pov, "shares", end)
        shares = shares if isinstance(shares, dict) else {}
        beliefs = [{"holder": pov, "key": k, "claim": s["claim"], "conf": round(float(s["share"]), 3),
                    "text": claim_text(s["claim"], run.names, run.by_id), "origin": None}
                   for k, s in sorted(shares.items()) if not on_topic or B.topic(s["claim"]) == on_topic]
        evs = {e for e in evs if run.by_id[e].get("visibility") != SECRET and run.by_id[e].get("place") == pov}
    else:
        heard: dict[str, dict] = {}
        for p in minds:
            held = relevant(_beliefs_of(run, p, _until(run, p, end))) if on_topic else _beliefs_of(run, p, _until(run, p, end))
            known = {origin(run.by_id.get, b["from"]) for b in held.values() if b.get("from")} | \
                    {b["from"] for b in held.values() if b.get("from")}
            evs_p = {e for e in evs if _knows(run, p, run.by_id[e], known)}
            heard[p] = {"held": held, "events": evs_p}
        evs = set().union(*(h["events"] for h in heard.values())) if heard else set()
        if view["kind"] == "person":  # (a person holds all their beliefs, rivals on one question included)
            for p, h in sorted(heard.items()):
                beliefs += _belief_rows(run, p, h["held"], verdicts=False)
        else:  # (a house speaks with one voice per question: the head's, else the firmest, then the lower key)
            chosen: dict[str, tuple] = {}
            head = _head(run, pov)
            for p, h in sorted(heard.items()):
                for k, b in h["held"].items():
                    t = B.topic(b["claim"])
                    rank = (p != head, -float(b["conf"]), k)
                    if t not in chosen or rank < chosen[t][0]:
                        chosen[t] = (rank, p, k, b)
            for _, p, k, b in sorted(chosen.values(), key=lambda x: x[2]):
                beliefs += _belief_rows(run, p, {k: b}, verdicts=False)
    roles: dict[str, set[str]] = {}
    for e in evs:
        for role, ms in run.by_id[e].get("roles", {}).items():
            for m in ms:
                if m in people:
                    roles.setdefault(m, set()).add(ROLE_NAMES.get(role, "involved"))
    for a in (x for x in run.stories["arcs"] if sub["kind"] in ("arc", "saga") and x["id"] in _arc_ids(run, sub)):
        roles.setdefault(a["owner"], set()).add("lead")
        if a.get("target"):
            roles.setdefault(a["target"], set()).add("target")
    events = []
    for e in sorted(evs, key=lambda i: (run.by_id[i]["date"], i)):
        ev = run.by_id[e]
        events.append({"id": e, "date": ev["date"], "type": ev["type"], "roles": ev.get("roles") or {},
                       "place": ev.get("place"), "text": reading(ev, run.names, run.by_id),
                       "causes": sorted(ref for kind, ref in (ev.get("causes") or []) if kind == "event" and ref in evs),
                       "secret": ev.get("visibility") == SECRET})
    shown = sorted(p for p in people if p in run.ents and (minds is None or any(
        p in ms for e in evs for ms in run.by_id[e].get("roles", {}).values()) or p in (minds or [])))
    places = sorted({ev["place"] for ev in events if ev.get("place")})
    pack = {"schema": SCHEMA, "run": run.name, "engine": run.manifest.get("engine"),
            "subject": sub, "pov": view,
            "span": [events[0]["date"], events[-1]["date"]] if events else None,
            "people": [_person_row(run, p, roles) for p in shown],
            "places": [{"id": p, "name": run.names(p)} for p in places],
            "events": events, "beliefs": beliefs, "timeline": [e["id"] for e in events],
            "threads": _threads(run, set(shown))}
    return json.loads(canonical(pack))


def _arc_ids(run: Run, sub: dict) -> set[str]:
    if sub["kind"] == "arc":
        return {sub["id"]}
    saga = next((s for s in run.stories["sagas"] if s["id"] == sub["id"]), None)
    return set(saga["arcs"]) if saga else set()


def _head(run: Run, house: str) -> str | None:
    office = run.ents.get(house, {}).get("fields", {}).get("headship")
    return run.ents.get(office, {}).get("fields", {}).get("holder") if office else None


def _threads(run: Run, people: set[str]) -> list[dict]:
    """What's still open at the end: schemes still running, grievances not taken up."""
    out = []
    for i, e in sorted(run.ents.items()):
        f = e["fields"]
        if e["kind"] == "scheme" and f.get("owner") in people and f.get("state") == "active":
            whom = f" against {run.names.full(f['target'])}" if f.get("target") else ""
            steps = ", ".join(s["action"] for s in f.get("plan") or [])
            out.append({"kind": "scheme", "text": f"{run.names.full(f['owner'])} is scheming{whom} ({steps})",
                        "people": sorted(x for x in (f["owner"], f.get("target")) if x), "events": [], "open": True})
    for p in sorted(people):
        for g in run.ents[p]["fields"].get("grievances") or []:
            if not g.get("answered"):
                out.append({"kind": "grievance", "text": f"{run.names.full(p)} holds a grievance against "
                            f"{run.names.full(g['against'])}", "people": sorted({p, g["against"]}),
                            "events": [g["event"]] if g.get("event") in run.by_id else [], "open": True})
    return sorted(out, key=lambda t: (t["kind"], t["text"]))
