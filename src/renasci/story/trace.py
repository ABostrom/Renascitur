"""Where a belief came from (#107, S12 spec §1a): the Python twin of the Observatory's `provenance.trace`.

A belief records the event that put it in its holder's head. Walking back from there: a telling's cause
is the teller's own belief event, so the walk passes each telling in turn until it reaches what the
first holder perceived (and the event they saw), what exposed the truth (a correction), news that
arrived by road, or a lie (and the scheme's step that told it). An event's causes are its own plus its
activation's, sorted by id, so the walk picks the cause by kind, not position. Shared test vectors
(`tests/fixtures/traces.json`) keep the two implementations the same.
"""

from __future__ import annotations

MAX_STEPS = 24
BEHIND = ("belief.perceived", "belief.corrected")  # (one step on: what was seen, or what exposed it)


def _cause(e: dict, lookup) -> dict | None:
    causes = [c for c in (lookup(ref) for kind, ref in (e.get("causes") or []) if kind == "event") if c]
    honest = e["type"] == "belief.told" and (e.get("payload") or {}).get("intent") != "lie"
    if honest:
        return next((c for c in causes if c["type"].startswith("belief.")), causes[0] if causes else None)
    if e["type"] == "belief.heard":
        return next((c for c in causes if c["type"] == "belief.news_arrived"), causes[0] if causes else None)
    plain = [c for c in causes if not c["type"].startswith(("ripple.", "belief."))]
    unrippled = [c for c in causes if not c["type"].startswith("ripple.")]
    return (plain or unrippled or causes or [None])[0]


def trace(lookup, start: str) -> list[dict]:
    """The steps back from the belief event `start`: `[{event, lie, origin, more?}]` (see the module doc)."""
    steps: list[dict] = []
    seen: set[str] = set()
    e = lookup(start)
    while e and e["id"] not in seen:
        if len(steps) == MAX_STEPS:
            steps[-1]["more"] = True
            break
        seen.add(e["id"])
        belief = e["type"].startswith("belief.")
        lie = e["type"] == "belief.told" and (e.get("payload") or {}).get("intent") == "lie"
        step = {"event": e, "lie": lie, "origin": not belief or e["type"] == "belief.news_arrived"}
        steps.append(step)
        if step["origin"]:
            break
        nxt = _cause(e, lookup)
        if lie or e["type"] in BEHIND:
            if nxt and nxt["id"] not in seen:
                steps.append({"event": nxt, "lie": False, "origin": True})
            else:
                step["origin"] = True
            break
        if nxt is None:
            step["origin"] = True  # (nothing recorded before it)
        e = nxt
    return steps


def origin(lookup, start: str) -> str | None:
    """The event a belief walks back to (the last step's)."""
    steps = trace(lookup, start)
    return steps[-1]["event"]["id"] if steps else None
