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
- `started(war, by)`: the war's declaration names `by` its aggressor. `won(war, by)`: its peace names `by`
  the winner, or a fall ended it with `by` the victor. `betrayed(treaty, by)`: its breaking names `by`.
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


def _killed(by_id, events, args, deaths=None):
    if deaths is None:
        deaths = [e for e in events if e["type"] == "people.death" and args["victim"] in (e["roles"].get("deceased") or [])]
    else:
        deaths = deaths.get(args["victim"], [])
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


class Log:
    """An event log indexed once, for judging many claims against it (`judge(..., log=Log(events))`)."""

    def __init__(self, events):
        self.events = list(events)
        self.by_id = _index(self.events)
        self.deaths: dict[str, list[dict]] = {}
        for e in self.events:
            if e["type"] == "people.death":
                for v in e["roles"].get("deceased") or []:
                    self.deaths.setdefault(v, []).append(e)


def judge(claim: dict, events, houses: dict | None = None, log: Log | None = None) -> tuple[str, list[str]]:
    log = log or Log(events)
    events, by_id = log.events, log.by_id
    houses = houses or {}
    pred, args = claim["pred"], claim["args"]
    if pred == "killed":
        return _killed(by_id, events, args, log.deaths)
    if pred == "caused":
        return _caused(by_id, args, also_stated=False, houses=houses)
    if pred == "fault":
        return _caused(by_id, args, also_stated=True, houses=houses)
    if pred in WAR_FACTS:
        return _war_fact(events, pred, args)
    if pred in ("owns", "made"):
        return _object_fact(events, pred, args)
    return "unknown", []


OWNING = {"object.given": "owner", "object.inherited": "owner", "object.found": "finder", "object.stolen": "thief",
          "object.unearthed": "finder", "object.lost": None, "object.destroyed": None}


def _object_fact(events, pred, args):
    """`made`: the object's making names `by`. `owns`: its latest change of hands names `by` (lost or destroyed:
    nobody)."""
    o, last = args["object"], None
    for e in events:
        if o not in (e["roles"].get("object") or []):
            continue
        if pred == "made" and e["type"] == "object.made":
            return ("true" if args["by"] in (e["roles"].get("maker") or []) else "false"), [e["id"]]
        if pred == "owns" and e["type"] in OWNING:
            last = e
    if last is None:
        return "unknown", []
    role = OWNING[last["type"]]
    return ("true" if role and args["by"] in (last["roles"].get(role) or []) else "false"), [last["id"]]


# (pred: [(event type, the payload field naming the war or treaty, the role naming who)])
WAR_FACTS = {"started": [("polity.war_declared", "war", "aggressor")],
             "won": [("polity.peace", "war", "winner"), ("polity.fallen", "war", "victor")],
             "betrayed": [("polity.treaty_broken", "treaty", "by")]}


def _war_fact(events, pred, args):
    what = args.get("war") or args.get("treaty")
    leaders = set()  # (a war's aggressor and defender: only a leader's fall ends it, not an ally's)
    for e in events:
        if e["type"] == "polity.war_declared" and (e.get("payload") or {}).get("war") == what:
            leaders = set(e["roles"].get("aggressor") or []) | set(e["roles"].get("defender") or [])
    for e in events:
        for kind, field, role in WAR_FACTS[pred]:
            if e["type"] != kind or (e.get("payload") or {}).get(field) != what:
                continue
            if kind == "polity.fallen" and not set(e["roles"].get("polity") or []) & leaders:
                continue
            return ("true" if args["by"] in (e["roles"].get(role) or []) else "false"), [e["id"]]
    return "unknown", []
