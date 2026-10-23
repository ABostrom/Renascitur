"""Claims, beliefs and perception (S6 spec §2, §4, §5; #86).

**Claims are values**, never store entities: `{"pred": name, "args": {role: id}}`, keyed by the digest of
that canonical value (`c:<digest>`), so the same statement made in two places is one claim. A
**predicate** class says what a claim is about (`topic`: claims in one topic compete), how much people
care to repeat it (`salience`), and how to read it out (`text`). Whether a claim is true is judged
offline, against the event log (`renasci.analysis.truth`), never here.

A notable's **beliefs** are a field, `{claim key: {claim, conf, since, from, heard}}`:
- `hold(ctx, person, claim, conf, cause_event, kind)` takes a belief on when it is new or firmer than
  the one held (a `belief.<kind>` event, caused by `cause_event`), and halves the rivals in its topic.
  A belief already held at least as firmly is only **reinforced** (`heard`), with no event. At most
  `BELIEF_CAP` beliefs are kept, the least salient and least sure dropped first.
- `perceive(ctx, event, settlement, participants, claim)`: those in an event believe it firmly
  (`PARTICIPANT_CONF`); a public event is also seen by up to `WITNESS_CAP` bystanders of its settlement,
  less surely (`BYSTANDER_CONF`); a secret one by its participants only. Bystanders may be shown a
  different claim (a death's cover, for instance).

All of this runs only in a world whose params say `beliefs: true` (`enabled`): elsewhere history is as
it was. Systems that may perceive declare `PERCEIVE_READS`, `PERCEIVE_WRITES` and `EVENT_TYPES`.
"""

from __future__ import annotations

from renasci.core.canon import canonical, digest
from renasci.core.events import Cause, EventType

BELIEF_CAP, WITNESS_CAP = 16, 3
PARTICIPANT_CONF, BYSTANDER_CONF = 0.9, 0.5

PERCEIVED = EventType("belief.perceived", 1, roles={"holder": (1, 1)},
                      payload={"claim": "json", "key": "str", "conf": "float"})
EVENT_TYPES = (PERCEIVED,)
PERCEIVE_READS = frozenset({"beliefs", "residents", "status"})
PERCEIVE_WRITES = frozenset({"beliefs"})


class Predicate:
    """What a kind of claim says. Subclass with a `name` and the `args` it takes."""

    name = ""
    args: tuple[str, ...] = ()
    base_salience = 0.5

    def topic(self, args: dict) -> str:
        raise NotImplementedError

    def salience(self, args: dict) -> float:
        return self.base_salience

    def text(self, args: dict, names: dict) -> str:
        raise NotImplementedError


class Killed(Predicate):
    """`by` killed `victim` (a person, or a cause like "a wasting illness")."""

    name, args, base_salience = "killed", ("victim", "by"), 0.8

    def topic(self, args):
        return f"killed:{args['victim']}"

    def text(self, args, names):
        return f"{names.get(args['victim'], args['victim'])} was killed by {names.get(args['by'], args['by'])}"


class Caused(Predicate):
    """`by` (a person or house) brought `event` about."""

    name, args, base_salience = "caused", ("event", "by"), 0.7

    def topic(self, args):
        return f"why:{args['event']}"

    def text(self, args, names):
        return f"{names.get(args['by'], args['by'])} caused it"


class Fault(Predicate):
    """`event` was `party`'s fault (blame without agency: "the stones were faulty")."""

    name, args, base_salience = "fault", ("event", "party"), 0.6

    def topic(self, args):
        return f"why:{args['event']}"  # (the same question as `caused`: whose doing was it?)

    def text(self, args, names):
        return f"it was the fault of {names.get(args['party'], args['party'])}"


def predicates() -> dict[str, Predicate]:
    found, todo = {}, list(Predicate.__subclasses__())
    while todo:
        cls = todo.pop()
        todo.extend(cls.__subclasses__())
        if cls.name:
            found[cls.name] = cls()
    return found


PREDICATES = predicates()


def claim(pred: str, **args) -> dict:
    p = PREDICATES.get(pred)
    if p is None:
        raise ValueError(f"no predicate {pred!r}; known: {sorted(PREDICATES)}")
    if set(args) != set(p.args) or not all(isinstance(v, str) and v for v in args.values()):
        raise ValueError(f"{pred} takes {p.args} as strings, got {args}")
    return {"pred": pred, "args": dict(sorted(args.items()))}


def key(c: dict) -> str:
    return "c:" + digest(c, size=8)


def topic(c: dict) -> str:
    return PREDICATES[c["pred"]].topic(c["args"])


def salience(c: dict) -> float:
    return PREDICATES[c["pred"]].salience(c["args"])


def enabled(ctx) -> bool:
    return bool(ctx.params.get("beliefs"))


# ------------------------------------------------------------ holding


def _capped(beliefs: dict) -> dict:
    if len(beliefs) <= BELIEF_CAP:
        return beliefs
    keep = sorted(beliefs, key=lambda x: (-salience(beliefs[x]["claim"]) * beliefs[x]["conf"], x))[:BELIEF_CAP]
    return {x: beliefs[x] for x in keep}


def hold(ctx, person: str, c: dict, conf: float, cause_event: str, kind: str = "perceived",
         secret: bool = False) -> bool:
    """Take on (or firm up) a belief; returns whether it changed.

    - Held at least as firmly already: only reinforced (`heard`, no event). The write is explained by the
      activation's last event, which is the one that told or showed it, or one emitted just after it.
    - A firmer rival in its topic: rejected (no event, nothing written).
    - Else taken on (a `belief.<kind>` event, secret if what it shows was), and its rivals halved; unless
      the cap would drop it at once, when nothing happens."""
    conf = round(min(1.0, max(0.0, conf)), 3)
    beliefs = dict(ctx.get(person, "beliefs") or {})
    k, t = key(c), topic(c)
    held = beliefs.get(k)
    if held is not None and held["conf"] >= conf:
        if held.get("heard") != ctx.today.to_json():
            beliefs[k] = {**held, "heard": ctx.today.to_json()}
            ctx.set(person, "beliefs", beliefs)
        return False
    if any(other != k and topic(b["claim"]) == t and b["conf"] > conf for other, b in beliefs.items()):
        return False  # (confirmation bias: a firmer belief in the same question wins)
    after = dict(beliefs)
    for other, b in list(after.items()):
        if other != k and topic(b["claim"]) == t:
            after[other] = {**b, "conf": round(b["conf"] / 2, 3)}
    after[k] = {"claim": c, "conf": conf, "since": (held or {}).get("since", ctx.today.to_json()),
                "from": "", "heard": ctx.today.to_json()}
    after = _capped(after)
    if k not in after:
        return False
    event = ctx.emit(f"belief.{kind}", {"holder": (person,)}, purpose=f"belief:{k}", actor=person,
                     payload={"claim": c, "key": k, "conf": conf}, causes=(Cause("event", cause_event),),
                     visibility="secret" if secret else None)
    after[k] = {**after[k], "from": event.id}
    ctx.set(person, "beliefs", dict(sorted(after.items())))
    return True


def perceive(ctx, event: str, settlement: str | None, participants, claim: dict, *, secret: bool = False,
             bystander_claim: dict | None = None, also: tuple[str, ...] = (), exclude=()) -> list[str]:
    """Those in `event` believe `claim` firmly; for a public event, up to `WITNESS_CAP` bystanders of
    `settlement` (and anyone in `also`, such as the victim's kin) believe `bystander_claim` (else
    `claim`) less surely. Nobody in `exclude` (those who know better: a secret killer) is a bystander.
    Returns everyone who perceived it, in order."""
    seen = []
    for p in participants:
        if p and ctx.status(p) == "active":
            hold(ctx, p, claim, PARTICIPANT_CONF, event, secret=secret)
            seen.append(p)
    if secret or settlement is None:
        return seen
    skip = set(seen) | set(exclude)
    also = tuple(a for a in also if a not in skip)
    pool = sorted(r for r in ctx.get(settlement, "residents") if r not in skip and ctx.status(r) == "active")
    bystanders = []
    for i in range(min(WITNESS_CAP, len(pool))):
        w = ctx.choose(f"witness:{i}", [r for r in pool if r not in bystanders], owner=event)
        if w is None:
            break
        bystanders.append(w)
    for w in [*bystanders, *(a for a in also if a not in seen and a not in bystanders)]:
        if ctx.status(w) == "active":
            hold(ctx, w, bystander_claim or claim, BYSTANDER_CONF, event)
            seen.append(w)
    return seen
