"""No unexplained divergence: compare a baseline run with a ripple run and explain every difference.

A difference is *explained* when it is reachable from the ripple through recorded causes,
participation, state changes or recorded reads. Taint starts at the ripple, then walks each run
in the order its activations ran:

- an activation is tainted if a cause is tainted or an unscoped read hit a tainted field;
- a scope (one village, one valley) is tainted if its activation is, or one of its reads hit a
  tainted field;
- an event is tainted if its scope or activation is, or a cause, a participant (as of then) or its
  source is;
- a tainted event taints everything it wrote: fields, column rows, created entities, pin statuses.

Events that exist only in the baseline (the death a ripple prevented) need baseline-side taint, so
both runs are walked, each seeding the other, until nothing new is tainted. Then every event and
every final entity that differs between the runs must be tainted in one of them. Anything else is
**unexplained**: a coupling the engine failed to record, which is a bug.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from renasci.core.canon import canonical


@dataclass
class Taint:
    events: set = field(default_factory=set)
    activations: set = field(default_factory=set)  # activation ids, and "<activation>#<scope>"
    fields: set = field(default_factory=set)  # (entity, field)
    entities: set = field(default_factory=set)

    def size(self) -> int:
        return len(self.events) + len(self.activations) + len(self.fields) + len(self.entities)

    def merge(self, other: Taint) -> None:
        self.events |= other.events
        self.activations |= other.activations
        self.fields |= other.fields
        self.entities |= other.entities


def _taint_run(history: dict, ripples: set[str], seed: Taint) -> Taint:
    t = Taint(set(seed.events), set(seed.activations), set(seed.fields), set(seed.entities))
    events = {e["id"]: e for e in history["events"]}

    by_event: dict[str, dict[str, list]] = {}
    for table, key in (("state_deltas", "event"), ("bulk_deltas", "event"), ("entities", "event"), ("pins", "event")):
        for row in history.get(table, []):
            if row.get(key):
                by_event.setdefault(row[key], {}).setdefault(table, []).append(row)
    rows_by_act: dict[str, list] = {}
    for row in history.get("reads", []):
        rows_by_act.setdefault(row["activation"], []).append(row)
    events_by_act: dict[str | None, list[str]] = {}
    for e in history["events"]:
        events_by_act.setdefault(e.get("activation"), []).append(e["id"])

    def read_tainted(read) -> bool:
        entity, fld = read
        if fld.startswith("ripple:") and fld[7:] in ripples:
            return True
        return (entity, fld) in t.fields

    def cause_tainted(kind, ref) -> bool:
        if kind == "ripple":
            return ref in ripples
        if kind == "event":
            return ref in t.events
        if kind == "activation":
            return ref in t.activations
        if kind == "pin":
            return (f"pin:{ref}", "status") in t.fields
        return False

    def taint_event(eid: str) -> None:
        t.events.add(eid)
        written = by_event.get(eid, {})
        for d in written.get("state_deltas", []):
            t.fields.add((d["entity"], d["field"]))
            t.entities.add(d["entity"])
        for b in written.get("bulk_deltas", []):
            for i in b["ids"]:
                t.fields.add((i, b["component"]))
                t.entities.add(i)
        for c in written.get("entities", []):
            t.fields.add((c["id"], "status"))
            t.fields.add((f"${c['kind']}", "ids"))
            t.entities.add(c["id"])
        for p in written.get("pins", []):
            t.fields.add((f"pin:{p['pin']}", "status"))

    def judge_event(eid: str, inherited: bool) -> None:
        e = events[eid]
        tainted = inherited or eid in t.events
        tainted = tainted or (e["source"][0] == "ripple" and e["source"][1] in ripples)
        tainted = tainted or any(cause_tainted(k, r) for k, r in e["causes"])
        tainted = tainted or any(m in t.entities for members in e["roles"].values() for m in members)
        if tainted:
            taint_event(eid)

    for eid in events_by_act.get(None, []):  # casting, before any activation
        judge_event(eid, False)

    for act in history.get("activations", []):
        a = act["activation"]
        act_t = a in t.activations or any(cause_tainted(k, r) for k, r in act["causes"])
        rows = rows_by_act.get(a, [])
        for row in rows:
            if row["scope"] is None and any(read_tainted(r) for r in row["reads"]):
                act_t = True
        if act_t:
            t.activations.add(a)
        listed = set()
        for row in rows:
            scope_key = f"{a}#{row['scope']}" if row["scope"] is not None else a
            scope_t = act_t or scope_key in t.activations or any(read_tainted(r) for r in row["reads"])
            if scope_t and row["scope"] is not None:
                t.activations.add(scope_key)
            for eid in row["events"]:
                listed.add(eid)
                judge_event(eid, scope_t)
        for eid in events_by_act.get(a, []):  # events recorded outside a ctx (e.g. a ripple's secret event)
            if eid not in listed:
                judge_event(eid, act_t)
    return t


def _entities(state: dict) -> dict[str, str]:
    return {e["id"]: canonical(e) for e in state["entities"]}


def _cells(state: dict) -> dict[tuple[str, str], object]:
    out = {}
    for name, col in state["columns"].items():
        for i, v in zip(col["ids"], col["data"]):
            out[(i, name)] = v
    return out


def analyse(baseline: dict, variant: dict, baseline_state: dict, variant_state: dict,
            ripples=(), max_rounds: int = 10) -> dict:
    """Compare two runs (history tables and final store snapshots) and explain their differences.

    `ripples` are the ripple ids that separate the runs. Returns counts, the unexplained items, and
    the causal wave (divergent events per place per year).
    """
    ripples = set(ripples)
    seed = Taint()
    for _ in range(max_rounds):
        ta, tb = _taint_run(baseline, ripples, seed), _taint_run(variant, ripples, seed)
        grown = Taint(set(seed.events), set(seed.activations), set(seed.fields), set(seed.entities))
        grown.merge(ta)
        grown.merge(tb)
        if grown.size() == seed.size():
            break
        seed = grown
    tainted = seed

    ev_a = {e["id"]: e for e in baseline["events"]}
    ev_b = {e["id"]: e for e in variant["events"]}
    divergent = sorted(i for i in set(ev_a) | set(ev_b)
                       if i not in ev_a or i not in ev_b or canonical(ev_a[i]) != canonical(ev_b[i]))
    unexplained_events = [i for i in divergent if i not in tainted.events]

    ent_a, ent_b = _entities(baseline_state), _entities(variant_state)
    divergent_entities = sorted(i for i in set(ent_a) | set(ent_b) if ent_a.get(i) != ent_b.get(i))
    unexplained_entities = [i for i in divergent_entities if i not in tainted.entities]
    cell_a, cell_b = _cells(baseline_state), _cells(variant_state)
    divergent_cells = sorted(k for k in set(cell_a) | set(cell_b) if cell_a.get(k) != cell_b.get(k))
    unexplained_cells = [list(k) for k in divergent_cells if k not in tainted.fields]

    wave: dict[tuple[int, str], list[int]] = {}
    for i in sorted(set(ev_a) | set(ev_b)):
        e = ev_b.get(i) or ev_a[i]
        key = (e["date"][1], e["place"] or "")
        cell = wave.setdefault(key, [0, 0])
        cell[1] += 1
        if i in divergent:
            cell[0] += 1

    describe = lambda i: {k: (ev_b.get(i) or ev_a[i])[k] for k in ("id", "date", "type", "roles", "activation")}
    return {
        "events": len(set(ev_a) | set(ev_b)),
        "divergent_events": len(divergent),
        "unexplained_events": len(unexplained_events),
        "divergent_entities": len(divergent_entities),
        "unexplained_entities": len(unexplained_entities),
        "divergent_cells": len(divergent_cells),
        "unexplained_cells": len(unexplained_cells),
        "unexplained": {"events": [describe(i) for i in unexplained_events[:20]],
                        "entities": unexplained_entities[:20], "cells": unexplained_cells[:20]},
        "wave": [{"year": y, "place": p or None, "divergent": d, "total": n} for (y, p), (d, n) in sorted(wave.items())],
    }
