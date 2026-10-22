"""No unexplained divergence: compare a baseline run with a ripple run and explain every difference.

The engine records, for every activation and every scope inside it (one village, one valley), each
field it read and a digest of the value it saw. Determinism means that code which saw the same
inputs makes the same decisions. So:

- **A scope is tainted** when a value it read differs between the two runs (as seen at that moment,
  in each run), or when it exists in only one run because something explained made it.
- **An event is explained** if it came from a tainted scope, from a ripple, or from a tainted cause
  (a tainted event, activation or scope; a ripple; a pin whose history differs).
- **A final difference in state** (an entity's field, a column cell) is explained if the event that
  last wrote it, in either run, is tainted.

Anything that differs and is not explained is **unexplained**: the code depended on something it did
not read through the engine (a module global, `hash()`, a shared counter). That is a bug.

Limitation: the scope is the unit of explanation. If a scope's inputs differ, everything it did is
explained, including a list-order coupling *within* that scope. Use scopes as fine as the decisions.
"""

from __future__ import annotations

from renasci.core.canon import canonical
from renasci.core.context import reads_digest

# Unexplained events described in full (roots first). Counts and the divergent id lists are never cut.
DETAIL_LIMIT = 1000


class _Run:
    """One run's history, indexed for the comparison."""

    def __init__(self, history: dict):
        # `scope` says where an event was emitted (metadata added in #54); it is not part of what happened.
        self.events = {e["id"]: {k: v for k, v in e.items() if k != "scope"} for e in history["events"]}
        # Where an event happened, for the wave: its place, else the scope that decided it.
        self.where = {e["id"]: e.get("place") or e.get("scope") for e in history["events"]}
        self.order = [a["activation"] for a in history.get("activations", [])]
        self.activations = {a["activation"]: a for a in history.get("activations", [])}
        self.scope_of: dict[str, tuple[str, str | None]] = {}
        # Per scope: (reads by key, or None when only a digest was kept; the row, for its digest).
        self.seen: dict[tuple[str, str | None], tuple[dict | None, dict]] = {}
        for row in history.get("reads", []):
            key = (row["activation"], row["scope"])
            self.seen[key] = ({(r[0], r[1]): r[2] for r in row["reads"]} if "reads" in row else None, row)
            for eid in row["events"]:
                self.scope_of[eid] = key
        for eid, e in self.events.items():  # events recorded outside a ctx belong to their activation
            self.scope_of.setdefault(eid, (e.get("activation") or "", None))
        self.writer: dict[tuple[str, str], str] = {}  # the last event to write each field or cell
        for dlt in history.get("state_deltas", []):
            self.writer[(dlt["entity"], dlt["field"])] = dlt["event"]
        for b in history.get("bulk_deltas", []):
            for i in b["ids"]:
                self.writer[(i, b["component"])] = b["event"]
        self.pin_history: dict[str, list] = {}
        for p in history.get("pins", []):
            self.pin_history.setdefault(p["pin"], []).append(p["status"])


def _differs(seen_a: tuple, seen_b: tuple) -> bool:
    """Did the scope see different inputs?

    With full reads on both sides, only reads made in both runs count: deterministic code diverges
    first at a shared read whose value differs, and a read made in only one run follows a decision
    that already differed. With a digest on either side (#151) the test is coarser: any difference
    in what the scope read taints it. That can hide a bug that changes only *which* fields a scope
    reads, so the exit test runs with full reads."""
    (a, row_a), (b, row_b) = seen_a, seen_b
    if a is not None and b is not None:
        return any(a[k] != b[k] for k in a.keys() & b.keys())
    return _digest(row_a) != _digest(row_b)


def _digest(row: dict) -> str:
    return row["digest"] if "reads" not in row else reads_digest(row["reads"])


def _reads_mode(*histories: dict) -> str:
    """How the compared runs kept their reads: "full" (exact analysis), "digest" or "mixed"."""
    kinds = {"reads" in row for h in histories for row in h.get("reads", [])}
    return "full" if kinds <= {True} else "digest" if kinds == {False} else "mixed"


def analyse(baseline: dict, variant: dict, baseline_state: dict, variant_state: dict, ripples=()) -> dict:
    """Compare two runs (history tables and final store snapshots) and explain their differences.

    `ripples` are the ripple ids that separate the runs. Returns counts, the divergent event ids per
    side, every unexplained item with the side it is on ("baseline", "variant" or "both"), and the
    causal wave (divergent, unexplained and total events per age-year per place).
    """
    ripples = set(ripples)
    a, b = _Run(baseline), _Run(variant)

    differing_pins = {p for p in set(a.pin_history) | set(b.pin_history) if a.pin_history.get(p) != b.pin_history.get(p)}
    tainted_scopes = {k for k in sorted(set(a.seen) & set(b.seen)) if _differs(a.seen[k], b.seen[k])}
    tainted_events: set[str] = set()
    explained_acts: set[str] = set()  # activations (or "a#scope") that exist in one run for an explained reason

    def cause_tainted(kind, ref) -> bool:
        if kind == "ripple":
            return ref in ripples
        if kind == "event":
            return ref in tainted_events
        if kind == "activation":
            act, _, scope = ref.partition("#")
            return ref in explained_acts or act in explained_acts or (act, scope or None) in tainted_scopes
        if kind == "pin":
            return ref in differing_pins
        return False

    def act_explained(run: _Run, act: str) -> bool:
        if act in explained_acts:
            return True
        info = run.activations.get(act)
        return info is not None and any(cause_tainted(k, r) for k, r in info["causes"])

    changed = True
    while changed:
        changed = False
        for run, other in ((a, b), (b, a)):
            for act in run.order:
                if act not in other.activations and act not in explained_acts and act_explained(run, act):
                    explained_acts.add(act)
                    changed = True
            for eid, e in run.events.items():
                if eid in tainted_events:
                    continue
                act, scope = run.scope_of[eid]
                if ((act, scope) in tainted_scopes or (act, None) in tainted_scopes
                        or act in explained_acts
                        or (e["source"][0] == "ripple" and e["source"][1] in ripples)
                        or any(cause_tainted(k, r) for k, r in e["causes"])):
                    tainted_events.add(eid)
                    changed = True

    ev_a, ev_b = a.events, b.events
    divergent = sorted(i for i in set(ev_a) | set(ev_b)
                       if i not in ev_a or i not in ev_b or canonical(ev_a[i]) != canonical(ev_b[i]))
    unexplained_events = [i for i in divergent if i not in tainted_events]

    def side(i, in_a, in_b) -> str:
        return "both" if i in in_a and i in in_b else "baseline" if i in in_a else "variant"

    def explained_write(key) -> bool:
        return a.writer.get(key) in tainted_events or b.writer.get(key) in tainted_events

    ents_a = {e["id"]: e for e in baseline_state["entities"]}
    ents_b = {e["id"]: e for e in variant_state["entities"]}
    divergent_entities, unexplained_entities = [], []
    for i in sorted(set(ents_a) | set(ents_b)):
        ea, eb = ents_a.get(i), ents_b.get(i)
        if canonical(ea) == canonical(eb):
            continue
        divergent_entities.append(i)
        fa = dict((ea or {}).get("fields", {}), status=(ea or {}).get("status"))
        fb = dict((eb or {}).get("fields", {}), status=(eb or {}).get("status"))
        if any(canonical(fa.get(f)) != canonical(fb.get(f)) and not explained_write((i, f))
               for f in sorted(set(fa) | set(fb))):
            unexplained_entities.append(i)

    def cells(state):
        return {(i, name): v for name, col in state["columns"].items() for i, v in zip(col["ids"], col["data"])}

    ca, cb = cells(baseline_state), cells(variant_state)
    divergent_cells = sorted(k for k in set(ca) | set(cb) if ca.get(k) != cb.get(k))
    unexplained_cells = [list(k) for k in divergent_cells if not explained_write(k)]

    wave: dict[tuple[int, int, str], list[int]] = {}
    div, unexpl = set(divergent), set(unexplained_events)
    for i in sorted(set(ev_a) | set(ev_b)):
        e = ev_b.get(i) or ev_a[i]
        cell = wave.setdefault((e["date"][0], e["date"][1], b.where.get(i) or a.where.get(i) or ""), [0, 0, 0, 0])
        cell[0] += i in div
        cell[1] += i in unexpl
        cell[2] += 1
        cell[3] += i in div and i not in ev_b

    def is_root(i):
        e = ev_b.get(i) or ev_a[i]
        return not any(k == "event" and r in unexpl for k, r in e["causes"])

    detailed = sorted(unexplained_events, key=lambda i: not is_root(i))[:DETAIL_LIMIT]

    def describe(i):
        return {**{k: (ev_b.get(i) or ev_a[i])[k] for k in ("id", "date", "type", "place", "roles", "causes", "activation")},
                "side": side(i, ev_a, ev_b)}

    return {
        "reads": _reads_mode(baseline, variant),
        "events": len(set(ev_a) | set(ev_b)),
        "divergent_events": len(divergent),
        "unexplained_events": len(unexplained_events),
        "divergent_entities": len(divergent_entities),
        "unexplained_entities": len(unexplained_entities),
        "divergent_cells": len(divergent_cells),
        "unexplained_cells": len(unexplained_cells),
        "tainted_scopes": len(tainted_scopes),
        "tainted_scope_names": sorted({s for _, s in tainted_scopes if s is not None}),
        "divergent": {"only_baseline": [i for i in divergent if i not in ev_b],
                      "only_variant": [i for i in divergent if i not in ev_a],
                      "changed": [i for i in divergent if i in ev_a and i in ev_b]},
        "unexplained": {"events": [describe(i) for i in detailed],
                        "entities": [{"id": i, "side": side(i, ents_a, ents_b)} for i in unexplained_entities],
                        "cells": [{"id": i, "column": c, "side": side((i, c), ca, cb)} for i, c in unexplained_cells]},
        "wave": [{"age": g, "year": y, "place": p or None, "divergent": d, "unexplained": u, "total": n,
                  "only_baseline": ob}
                 for (g, y, p), (d, u, n, ob) in sorted(wave.items())],
    }
