"""Schemes (S7 spec §6): an ambition pursued step by step.

A **scheme** is a store record (kind `scheme`): `owner`, `ambition`, `target` (the ambition's), `plan`
(the planner's steps, JSON), `step` (the next one's index), `retries`, `replans`, `accomplices`,
`state` (active, succeeded, failed, exposed, moot, confessed), `started`, `ended`. The ambition names
it in `scheme` while it runs; everyone it touches (target, accomplices) lists it in `plots`, which is
what spares them from fading into the masses (master spec §5.10).

`people.schemes` (yearly, per settlement scope, after ambitions) gives each adult's active, unplotted
ambition a keyed chance (`scheme_rate`, owned by the ambition) to become a scheme: the planner's
cheapest plan for its subgoals, begun by `people.scheme_begun`. Each step is a follow-up activation
caused by the scheme and its ambition, so **every event a step leads to traces back to both**.

A step, in the scheme's scope:

1. the owner is gone or the ambition ended -> **moot**; the dead and faded leave the accomplices
   (`people.accomplice_lost`);
2. a step whose `requires` no longer hold (its accomplice is gone, its favour lost) is impossible; else
   `perform` the step's action (draws owned by the scheme);
3. **success** -> the next step; when the ambition is met it is fulfilled and the scheme **succeeded**
   (a finished plan whose ambition isn't met yet, a seat that passes tomorrow, also succeeded: the yearly
   pass judges the ambition);
4. **failure** -> retry (the action's `retries`), then one **replan**, then **failed** (the ambition is
   thwarted); an impossible step goes straight to the replan;
5. **exposed** -> `people.scheme_exposed`: the ambition is thwarted; the owner loses favour (and takes a
   shame wound); the one plotted against (the step's victim, else the scheme's target) makes an enemy of
   the owner and holds the plot against them ("exposed"), and their kin hold it too ("threatened", which
   is how Protect is born).

Everyone a scheme touches lists it in `plots`: its target, its accomplices, and every victim its plan
names (a Seize plot's heirs).
"""

from __future__ import annotations

from renasci import relations
from renasci.core.calendar import Span
from renasci.core.events import Cause, EventType
from renasci.core.systems import System
from renasci.people import actions as A
from renasci.people import ambitions, beliefs, houses, minds, ties, travel
from renasci.people.ambitions import ADULT, classes, resolve
from renasci.people.life import add_grievance, grieving
from renasci.people.planner import holds, plan_for
from renasci.people.races import age_years

BEGUN = EventType("people.scheme_begun", 1, roles={"owner": (1, 1), "ambition": (1, 1), "target": (0, 1),
                                                   "scheme": (1, 1)}, payload={"steps": "int"})
REPLANNED = EventType("people.scheme_replanned", 1, roles={"scheme": (1, 1), "owner": (1, 1)},
                      payload={"steps": "int"})
ENDED = EventType("people.scheme_ended", 1, roles={"scheme": (1, 1), "owner": (1, 1)}, payload={"state": "str"},
                  dead_roles=("owner",))
EXPOSED = EventType("people.scheme_exposed", 1, roles={"scheme": (1, 1), "owner": (1, 1), "target": (0, 1)},
                    payload={"action": "str"})
LOST = EventType("people.accomplice_lost", 1, roles={"scheme": (1, 1), "accomplice": (1, 1)}, payload={},
                 dead_roles=("accomplice",))
EVENT_TYPES = (BEGUN, REPLANNED, ENDED, EXPOSED, LOST, ties.TIE_ENDED)
HARMS = ("dead:", "shamed:")

READS = frozenset({"owner", "ambition", "target", "plan", "step", "retries", "replans", "accomplices", "state",
                   "plots", "class", "grievances", "wound", "favour", "ties", "a", "b", "spouse", "mother", "father",
                   "children", "name", "place", "kind", "need"})
WRITES = frozenset({"need", "new:scheme", "plan", "step", "retries", "replans", "accomplices", "state", "ended", "plots",
                    "scheme", "grievances", "favour", "wound", "ties", "new:tie"})


def _plots(ctx, person: str, scheme: str, add: bool) -> None:
    have = set(ctx.get(person, "plots") or [])
    ctx.set(person, "plots", sorted(have | {scheme} if add else have - {scheme}))


def _victims(steps) -> set[str]:
    return {st["target"] for st in steps if st["target"] and A.ACTIONS[st["action"]].achieves.startswith(HARMS)}


def _involved(ctx, scheme: str) -> list[str]:
    target = ctx.get(scheme, "target")
    return sorted({*([target] if target else []), *(ctx.get(scheme, "accomplices") or []),
                   *_victims(ctx.get(scheme, "plan") or [])})


def begin(ctx, amb: str, owner: str) -> str | None:
    """Plan for an ambition; if there is a plan, the scheme begins and its first step is scheduled."""
    cls = classes(ctx)[ctx.get(amb, "class")]
    target = ctx.get(amb, "target")
    if target is not None and ctx.status(target) != "active":
        return None
    found = plan_for(ctx, owner, cls.subgoals(ctx, amb))
    if found is None or not found.steps:
        return None
    steps = found.to_json()["steps"]
    fields = {"owner": owner, "ambition": amb, "target": target, "plan": steps, "step": 0, "retries": 0,
              "replans": 0, "accomplices": [], "state": "active", "started": ctx.today.to_json(), "ended": None}
    event = ctx.emit("people.scheme_begun", {"owner": (owner,), "ambition": (amb,),
                                             "target": (target,) if target else ()},
                     purpose="scheme", actor=amb, payload={"steps": len(steps)},
                     causes=(Cause("ambition", amb),), creates={"scheme": [("scheme", fields)]})
    scheme = event.roles["scheme"][0]
    ctx.set(amb, "scheme", scheme)
    for person in _involved(ctx, scheme):
        _plots(ctx, person, scheme, True)
    _next(ctx, scheme)
    return scheme


def _next(ctx, scheme: str) -> None:
    """Schedule the current step, after its action's duration."""
    step = ctx.get(scheme, "plan")[ctx.get(scheme, "step")]
    days = A.ACTIONS[step["action"]].duration(ctx, ctx.get(scheme, "owner"), step["target"])
    ctx.schedule(Span(days=days), "step", entity=scheme,
                 payload={"scheme": scheme},
                 causes=(Cause("scheme", scheme), Cause("ambition", ctx.get(scheme, "ambition"))))


def end(ctx, scheme: str, state: str, causes=()) -> str:
    """The scheme ends: its record, the ambition's link, everyone's `plots`."""
    owner = ctx.get(scheme, "owner")
    event = ctx.emit("people.scheme_ended", {"scheme": (scheme,), "owner": (owner,)}, purpose=f"end:{state}",
                     actor=scheme, payload={"state": state}, causes=(Cause("scheme", scheme), *causes))
    if ctx.get(scheme, "state") == "active":  # (Confess sets its own state)
        ctx.set(scheme, "state", state)
    ctx.set(scheme, "ended", ctx.today.to_json())
    amb = ctx.get(scheme, "ambition")
    if ctx.get(amb, "scheme") == scheme:
        ctx.set(amb, "scheme", None)
    for p in _involved(ctx, scheme):
        _plots(ctx, p, scheme, False)
    return event.id


def _replan(ctx, scheme: str, owner: str, amb: str) -> str:
    """"replanned", "done" (the goals already hold: a seat that passes tomorrow) or "none"."""
    if int(ctx.get(scheme, "replans") or 0) >= 1:
        return "none"
    cls = classes(ctx)[ctx.get(amb, "class")]
    found = plan_for(ctx, owner, cls.subgoals(ctx, amb), scheme)
    if found is None:
        return "none"
    if not found.steps:
        return "done"
    steps = found.to_json()["steps"]
    ctx.emit("people.scheme_replanned", {"scheme": (scheme,), "owner": (owner,)}, purpose="replan", actor=scheme,
             payload={"steps": len(steps)})
    for person in _involved(ctx, scheme):
        _plots(ctx, person, scheme, False)
    ctx.set(scheme, "plan", steps)
    ctx.set(scheme, "step", 0)
    ctx.set(scheme, "retries", 0)
    ctx.set(scheme, "replans", int(ctx.get(scheme, "replans") or 0) + 1)
    for person in _involved(ctx, scheme):
        _plots(ctx, person, scheme, True)
    _next(ctx, scheme)
    return "replanned"


def _fail(ctx, scheme: str, owner: str, amb: str) -> None:
    outcome = _replan(ctx, scheme, owner, amb)
    if outcome == "done":
        end(ctx, scheme, "succeeded")  # the yearly pass judges the ambition
    elif outcome == "none":
        event = end(ctx, scheme, "failed")
        if ctx.get(amb, "state") == "active":
            resolve(ctx, amb, "thwarted", causes=(Cause("event", event),))


def _exposed(ctx, scheme: str, owner: str, amb: str, action: str, aimed_at: str | None) -> None:
    target = aimed_at if aimed_at in _victims([{"action": action, "target": aimed_at}]) else ctx.get(scheme, "target")
    victim = target if target and ctx.status(target) == "active" else None
    event = ctx.emit("people.scheme_exposed", {"scheme": (scheme,), "owner": (owner,),
                                               "target": (victim,) if victim else ()},
                     purpose="exposed", actor=scheme, payload={"action": action})
    # (S8 §4: the realms' ledger, before the revelations' own events, so the exposure explains it)
    relations.across(ctx, owner, victim or ctx.get(scheme, "target"), "exposed", event.id)
    if beliefs.enabled(ctx):  # (S6: exposed, the killings they hid come out)
        beliefs.reveal(ctx, owner, event.id, ctx.get(owner, "place"))
    A._favour(ctx, owner, -0.2)
    minds.wound(ctx, owner, "shame", event.id)
    if victim:
        turned = [t for t in ctx.get(victim, "ties") or [] if owner in (ctx.get(t, "a"), ctx.get(t, "b"))
                  and ctx.get(t, "kind") != "enemy"]
        for t in turned:  # a friend (or mentor, or rival) who plotted: the tie turns enemy, the victim is betrayed
            ties.end_tie(ctx, t, "betrayed")
        if turned:
            minds.wound(ctx, victim, "betrayal", event.id)
        ties.form_tie(ctx, owner, victim, "enemy", place=ctx.get(victim, "place"), causes=(Cause("event", event.id),))
        add_grievance(ctx, victim, owner, event.id, "exposed")
        for kin in grieving(ctx, victim):
            if kin != owner:
                add_grievance(ctx, kin, owner, event.id, "threatened")
    end(ctx, scheme, "exposed", causes=(Cause("event", event.id),))
    if ctx.get(amb, "state") == "active":
        resolve(ctx, amb, "thwarted", causes=(Cause("event", event.id),))


def step(ctx, scheme: str) -> None:
    """One step of a scheme (see the module doc)."""
    if ctx.get(scheme, "state") != "active":
        return
    owner, amb = ctx.get(scheme, "owner"), ctx.get(scheme, "ambition")
    if ctx.status(owner) != "active" or ctx.get(amb, "state") != "active" or ctx.get(amb, "scheme") != scheme:
        end(ctx, scheme, "moot")
        return
    cls = classes(ctx)[ctx.get(amb, "class")]
    if cls.satisfied(ctx, amb):  # the world got there first
        event = end(ctx, scheme, "succeeded")
        resolve(ctx, amb, "fulfilled", causes=(Cause("event", event),))
        return
    accomplices = ctx.get(scheme, "accomplices") or []
    for p in [p for p in accomplices if ctx.status(p) != "active"]:
        ctx.emit("people.accomplice_lost", {"scheme": (scheme,), "accomplice": (p,)}, purpose="lost", actor=scheme)
        ctx.set(scheme, "accomplices", [x for x in ctx.get(scheme, "accomplices") if x != p])
        _plots(ctx, p, scheme, False)
    plan = ctx.get(scheme, "plan")
    now = plan[ctx.get(scheme, "step")]
    action = A.ACTIONS[now["action"]]
    ready = all(holds(ctx, owner, r.replace("{target}", now["target"] or ""), scheme) for r in sorted(action.requires))
    outcome = A.perform(ctx, action, owner, now["target"], scheme) if ready else "impossible"
    for p in ctx.get(scheme, "accomplices") or []:  # whoever was won over is part of the plot now
        if scheme not in (ctx.get(p, "plots") or []):
            _plots(ctx, p, scheme, True)
    if outcome == "exposed":
        _exposed(ctx, scheme, owner, amb, action.name, now["target"])
    elif ctx.status(owner) != "active":  # (a lost duel)
        end(ctx, scheme, "moot")
    elif ctx.get(scheme, "state") != "active":  # a confession: the ambition is given up
        event = end(ctx, scheme, ctx.get(scheme, "state"))
        resolve(ctx, amb, "abandoned", causes=(Cause("event", event),))
    elif outcome == "impossible":
        _fail(ctx, scheme, owner, amb)
    elif outcome in ("failure", "foiled"):
        retries = int(ctx.get(scheme, "retries") or 0) + 1
        if retries <= action.retries:
            ctx.set(scheme, "retries", retries)
            _next(ctx, scheme)
        else:
            _fail(ctx, scheme, owner, amb)
    elif cls.satisfied(ctx, amb):
        event = end(ctx, scheme, "succeeded")
        resolve(ctx, amb, "fulfilled", causes=(Cause("event", event),))
    elif ctx.get(scheme, "step") + 1 >= len(plan):
        end(ctx, scheme, "succeeded")  # the plan is done; the yearly pass judges the ambition
    else:
        ctx.set(scheme, "step", ctx.get(scheme, "step") + 1)
        ctx.set(scheme, "retries", 0)
        _next(ctx, scheme)


class Schemes(System):
    name, cadence = "people.schemes", "yearly"
    priority = 7  # after ambitions (6)
    reads = (READS | A.READS | ambitions.Ambitions.reads | houses.READS
             | frozenset({"ids:settlement", "residents", "born", "status", "ambitions", "favour", "traits", "spouse",
                          "ties", "a", "b"}).union(*(a.reads for a in A.ACTIONS.values())) | relations.NOTE_READS)
    writes = WRITES | A.WRITES | ambitions.WRITES | houses.WRITES | ties.WRITES | relations.NOTE_WRITES
    event_types = EVENT_TYPES + A.EVENT_TYPES + ambitions.EVENT_TYPES + (ties.TIE_FORMED,)

    def run(self, ctx):
        rate = float(ctx.params.get("scheme_rate", 0.5))
        for s in ctx.ids("settlement"):
            with ctx.scope(s):
                for p in ctx.get(s, "residents"):
                    if age_years(ctx.calendar, ctx.get(p, "born"), ctx.today) < ADULT:
                        continue
                    for amb in list(ctx.get(p, "ambitions") or []):
                        if ctx.get(amb, "scheme") is None and ctx.get(amb, "state") == "active" \
                                and ctx.chance(rate, "plan", owner=amb):
                            begin(ctx, amb, p)

    def handle(self, ctx, activation):
        if activation.purpose == "succession":
            houses.handle_succession(ctx, activation)
            return
        if activation.purpose == "arrive":  # a Flee's journey (S4 §5)
            travel.arrive(ctx, activation)
            return
        if activation.purpose != "step":
            raise ValueError(f"{self.name} has no follow-up {activation.purpose!r}")
        scheme = activation.payload["scheme"]
        with ctx.scope(scheme):
            step(ctx, scheme)
