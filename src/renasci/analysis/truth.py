"""Whether a claim is true, judged against a finished run's events (S6 spec §3). Never used in a run.

`judge(claim, events, houses=None) -> (verdict, basis)`: `true`, `false`, `half` or `unknown` (the log
says nothing either way), with the ids of the events it rests on (empty when unknown). `half`: the claim
blames the agent's house for what the agent did (`houses`: person -> house, from the run's final state).

- `killed(victim, by)`: the victim's death names its killer, or one of the death's own causes is a
  successful action aimed at the victim (a poisoning behind "a wasting illness"): its actor. With neither,
  the death's stated cause. Whoever set things moving further back didn't strike the blow.
- `caused(event, by)`: `by` is an agent (actor, killer, the one who ordered it) of the event or of an
  event among its causes, up to `DEPTH` steps back. Victims and bystanders are never agents.
- `fault(event, party)`: as `caused`, or the party is the event's stated cause.
"""

from __future__ import annotations


AGENT_ROLES = ("actor", "killer", "ordered_by")
DEPTH = 3


def _index(events):
    return {e["id"]: e for e in events}


def _agents(e) -> set[str]:
    roles = e.get("roles") or {}
    return {m for r in AGENT_ROLES for m in roles.get(r) or []}


def _ancestry(by_id, eid, depth: int = DEPTH) -> list[dict]:
    """The event and the events among its causes, up to `depth` steps back (each once)."""
    out, todo, seen = [], [(eid, 0)], set()
    while todo:
        cur, d = todo.pop(0)
        if cur in seen or cur not in by_id:
            continue
        seen.add(cur)
        e = by_id[cur]
        out.append(e)
        if d < depth:
            todo.extend((ref, d + 1) for kind, ref in (e.get("causes") or []) if kind == "event")
    return out


def _killed(by_id, events, args):
    deaths = [e for e in events if e["type"] == "people.death" and args["victim"] in (e["roles"].get("deceased") or [])]
    if not deaths:
        return "unknown", []
    death = deaths[0]
    killers = set(death["roles"].get("killer") or [])
    for kind, ref in death.get("causes") or []:  # (the blow itself, not whatever led to it)
        e = by_id.get(ref) if kind == "event" else None
        if e and e["type"] == "people.action" and (e.get("payload") or {}).get("outcome") == "success" \
                and args["victim"] in (e["roles"].get("target") or []):
            killers |= set(e["roles"].get("actor") or [])
    if not killers and (death.get("payload") or {}).get("cause"):
        killers = {death["payload"]["cause"]}
    return ("true" if args["by"] in killers else "false"), [death["id"]]


def _caused(by_id, args, also_stated: bool, houses: dict):
    if args["event"] not in by_id:
        return "unknown", []
    chain = _ancestry(by_id, args["event"])
    who = set().union(*(_agents(e) for e in chain))
    if also_stated:
        who |= {(e.get("payload") or {}).get("cause") for e in chain} - {None}
    who_arg = args.get("by") or args.get("party")
    if who_arg in who:
        return "true", [e["id"] for e in chain]
    if any(houses.get(w) == who_arg for w in who):
        return "half", [e["id"] for e in chain]  # (the house, for what one of its own did)
    return "false", [e["id"] for e in chain]


def judge(claim: dict, events, houses: dict | None = None) -> tuple[str, list[str]]:
    events = list(events)
    houses = houses or {}
    by_id = _index(events)
    pred, args = claim["pred"], claim["args"]
    if pred == "killed":
        return _killed(by_id, events, args)
    if pred == "caused":
        return _caused(by_id, args, also_stated=False, houses=houses)
    if pred == "fault":
        return _caused(by_id, args, also_stated=True, houses=houses)
    return "unknown", []
