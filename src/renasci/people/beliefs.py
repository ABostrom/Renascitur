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

**Telling** (§6, #87): `tell(ctx, teller, hearer, claim, trust)` passes a claim on; the hearer holds it
at the teller's confidence × `trust` (a `belief.told`, caused by the teller's belief, so every belief
walks back to where it began). `intent` says whether the teller meant it (`honest`) or not (`lie`); the
hearer's belief never says. `drift(ctx, claim)` is how a retelling mutates a claim (a killing pinned
on the killer's house), and the telling records what it drifted from. `correct` is public evidence: it
overrides confirmation bias and drops the rivals it beats. `decayed` fades what nobody repeats.

`Gossip` (seasonal, one scope per settlement) is who tells whom: notables living in the same settlement
and not on the road, along their ties (trust and closeness by kind) and in their household (kin trust),
the settlement's most salient beliefs first, at most `TELL_CAP` per teller and `SETTLEMENT_TELLS` per
settlement a season. A belief heard again is refreshed (`belief.reinforced`); once a year, what nobody
repeated for `DECAY_YEARS` fades a step (`belief.faded`).

All of this runs only in a world whose params say `beliefs: true` (`enabled`): elsewhere history is as
it was. Systems that may perceive declare `PERCEIVE_READS`, `PERCEIVE_WRITES` and `EVENT_TYPES`.
"""

from __future__ import annotations

from renasci.core.calendar import Date
from renasci.core.canon import digest
from renasci.core.events import Cause, EventType
from renasci.core.systems import System

BELIEF_CAP, WITNESS_CAP = 16, 3
PARTICIPANT_CONF, BYSTANDER_CONF, CORRECTION_CONF = 0.9, 0.5, 0.85
TELL_CAP, SETTLEMENT_TELLS, DRIFT_RATE = 2, 40, 0.08
DECAY_YEARS, DECAY_STEP, FORGET_BELOW = 10, 0.1, 0.1
TRUST = {"mentor": 0.8, "friend": 0.7, "lover": 0.7, "rival": 0.3, "enemy": 0.1, "kin": 0.8}
CLOSENESS_KIN = 0.5  # (household: spouse, parents and children living together)

PERCEIVED = EventType("belief.perceived", 1, roles={"holder": (1, 1)},
                      payload={"claim": "json", "key": "str", "conf": "float"})
TOLD = EventType("belief.told", 1, roles={"holder": (1, 1), "teller": (1, 1)},
                 payload={"claim": "json", "key": "str", "conf": "float", "intent": "str", "drifted_from": "str"})
CORRECTED = EventType("belief.corrected", 1, roles={"holder": (1, 1)},
                      payload={"claim": "json", "key": "str", "conf": "float"})
FADED = EventType("belief.faded", 1, roles={"settlement": (1, 1)}, payload={"faded": "int"})
REINFORCED = EventType("belief.reinforced", 1, roles={"settlement": (1, 1)}, payload={"people": "int"})
EVENT_TYPES = (PERCEIVED, TOLD, CORRECTED, FADED, REINFORCED)
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

    def drift(self, ctx, args: dict) -> dict | None:
        """How a retelling mutates the claim (new args), or None if it can't."""
        return None


def _house_of(ctx, who: str) -> str | None:
    """A person's house, for blaming the house instead of the person (a drift)."""
    if not ctx.exists(who) or ctx.kind(who) != "person":
        return None
    return ctx.get(who, "house")


class Killed(Predicate):
    """`by` killed `victim` (a person, or a cause like "a wasting illness")."""

    name, args, base_salience = "killed", ("victim", "by"), 0.8

    def topic(self, args):
        return f"killed:{args['victim']}"

    def text(self, args, names):
        return f"{names.get(args['victim'], args['victim'])} was killed by {names.get(args['by'], args['by'])}"

    def drift(self, ctx, args):  # "her son did it" becomes "House Ardent did it"
        house = _house_of(ctx, args["by"])
        return {**args, "by": house} if house else None


class Caused(Predicate):
    """`by` (a person or house) brought `event` about."""

    name, args, base_salience = "caused", ("event", "by"), 0.7

    def topic(self, args):
        return f"why:{args['event']}"

    def text(self, args, names):
        return f"{names.get(args['by'], args['by'])} caused it"

    def drift(self, ctx, args):
        house = _house_of(ctx, args["by"])
        return {**args, "by": house} if house else None


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


def drift(ctx, c: dict) -> dict | None:
    """The claim as a retelling might mutate it, or None."""
    args = PREDICATES[c["pred"]].drift(ctx, c["args"])
    return claim(c["pred"], **args) if args else None


def enabled(ctx) -> bool:
    return bool(ctx.params.get("beliefs"))


# ------------------------------------------------------------ holding


def _capped(beliefs: dict) -> dict:
    if len(beliefs) <= BELIEF_CAP:
        return beliefs
    keep = sorted(beliefs, key=lambda x: (-salience(beliefs[x]["claim"]) * beliefs[x]["conf"], x))[:BELIEF_CAP]
    return {x: beliefs[x] for x in keep}


def hold(ctx, person: str, c: dict, conf: float, cause_event: str, kind: str = "perceived",
         secret: bool = False, teller: str | None = None, extra: dict | None = None, place: str | None = None) -> bool:
    """Take on (or firm up) a belief; returns whether it changed.

    - Held at least as firmly already: nothing changes, and no event. Seeing it again (a perception)
      refreshes `heard`, which decay reads; that write is explained by the event seen, emitted just before.
    - A firmer rival in its topic: rejected (no event, nothing written).
    - Else taken on (a `belief.<kind>` event, secret if what it shows was), and its rivals halved; unless
      the cap would drop it at once, when nothing happens."""
    conf = round(min(1.0, max(0.0, conf)), 3)
    beliefs = dict(ctx.get(person, "beliefs") or {})
    k, t = key(c), topic(c)
    held = beliefs.get(k)
    if held is not None and held["conf"] >= conf:
        if kind == "perceived" and held.get("heard") != ctx.today.to_json():  # (seeing it again: explained by
            # the event seen; hearing it again from someone changes nothing and needs no event)
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
    roles = {"holder": (person,), **({"teller": (teller,)} if teller else {})}
    event = ctx.emit(f"belief.{kind}", roles, purpose=f"belief:{k}", actor=person, place=place,
                     payload={"claim": c, "key": k, "conf": conf, **(extra or {})},
                     causes=(Cause("event", cause_event),), visibility="secret" if secret else None)
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


# ------------------------------------------------------------ telling (#87)


def tell(ctx, teller: str, hearer: str, c: dict, trust: float, *, conf: float | None = None, intent: str = "honest",
         cause: str | None = None, drifted_from: str = "", place: str | None = None) -> bool:
    """`teller` tells `hearer` the claim; the hearer may take it on at `conf` (the teller's own confidence
    by default) × `trust`. Caused by the teller's belief (or `cause`, for a lie they don't hold)."""
    held = (ctx.get(teller, "beliefs") or {}).get(key(c)) or (ctx.get(teller, "beliefs") or {}).get(drifted_from)
    if conf is None:
        conf = held["conf"] if held else 0.0
    cause = cause or (held["from"] if held else None)
    if cause is None:
        raise ValueError(f"{teller} holds no {key(c)} to tell: say what caused the telling")
    return hold(ctx, hearer, c, conf * trust, cause, kind="told", teller=teller,
                extra={"intent": intent, "drifted_from": drifted_from}, place=place)


def correct(ctx, person: str, c: dict, cause_event: str, conf: float = CORRECTION_CONF) -> bool:
    """Public evidence (an exposure, testimony): it bypasses confirmation bias. The claim is held at least
    at `CORRECTION_CONF` (and as firmly as the firmest rival it replaces), and every rival in its topic is
    dropped. Returns whether anything changed."""
    beliefs = dict(ctx.get(person, "beliefs") or {})
    k, t = key(c), topic(c)
    rivals = [o for o, b in beliefs.items() if o != k and topic(b["claim"]) == t]
    held = (beliefs.get(k) or {}).get("conf", 0)
    conf = round(max(conf, CORRECTION_CONF, held, *(beliefs[o]["conf"] for o in rivals)), 3)
    if not rivals and held >= conf:
        return False
    after = {o: b for o, b in beliefs.items() if o not in rivals}
    after[k] = {"claim": c, "conf": conf, "since": (beliefs.get(k) or {}).get("since", ctx.today.to_json()),
                "from": "", "heard": ctx.today.to_json()}
    if k not in _capped(after):
        return False
    event = ctx.emit("belief.corrected", {"holder": (person,)}, purpose=f"correct:{k}", actor=person,
                     payload={"claim": c, "key": k, "conf": conf}, causes=(Cause("event", cause_event),))
    after[k] = {**after[k], "from": event.id}
    ctx.set(person, "beliefs", dict(sorted(_capped(after).items())))
    return True


def decayed(beliefs: dict, today) -> dict:
    """One year's fading: a belief not heard or seen again for more than `DECAY_YEARS` loses `DECAY_STEP`;
    below `FORGET_BELOW` it is forgotten. Applied once a year, so the loss is one step a year."""
    year = today[1] if not isinstance(today, Date) else today.year
    out = {}
    for k, b in beliefs.items():
        idle = year - b["heard"][1]
        conf = round(b["conf"] - DECAY_STEP, 3) if idle > DECAY_YEARS else b["conf"]
        if conf >= FORGET_BELOW:
            out[k] = {**b, "conf": conf} if conf != b["conf"] else b
    return out


def _listeners(ctx, teller: str, residents: set[str]) -> list[tuple[str, float, float]]:
    """(hearer, closeness, trust) for those the teller talks to at home: ties first, then household."""
    out: dict[str, tuple[float, float]] = {}
    for t in ctx.get(teller, "ties") or []:
        if ctx.get(t, "ended"):
            continue
        other = ctx.get(t, "b") if ctx.get(t, "a") == teller else ctx.get(t, "a")
        if other in residents:
            out[other] = (float(ctx.get(t, "strength") or 0.3), TRUST.get(ctx.get(t, "kind"), 0.4))
    family = [ctx.get(teller, "spouse"), ctx.get(teller, "mother"), ctx.get(teller, "father"),
              *(ctx.get(teller, "children") or [])]
    for k in family:
        if k and k in residents and k not in out:
            out[k] = (CLOSENESS_KIN, TRUST["kin"])
    return [(h, c, tr) for h, (c, tr) in sorted(out.items())]


class Gossip(System):
    """Who tells whom, each season (see the module doc). One scope per settlement: a season's tellings
    there share one budget, so each depends on the others (and the diff must see them together)."""

    name, cadence = "beliefs.gossip", "seasonal"
    priority = 9  # after minds (8)
    reads = frozenset({"ids:settlement", "residents", "beliefs", "journey", "status", "ties", "a", "b", "kind",
                       "strength", "ended", "spouse", "mother", "father", "children", "traits", "house"})
    writes = frozenset({"beliefs"})
    event_types = EVENT_TYPES

    def run(self, ctx):
        if not enabled(ctx):
            return
        from renasci.people.ambitions import trait  # (ambitions -> life -> beliefs: imported here)

        yearly = ctx.calendar.season(ctx.today) == 0  # the year's first season also fades what nobody repeated
        for s in ctx.ids("settlement"):
            with ctx.scope(s):
                residents = sorted(p for p in ctx.get(s, "residents")
                                   if ctx.status(p) == "active" and not ctx.get(p, "journey"))
                if yearly:
                    self._fade(ctx, s, residents)
                self._gossip(ctx, s, residents, trait)

    def _gossip(self, ctx, settlement: str, residents: list[str], trait) -> None:
        here = set(residents)
        candidates = []  # (-weight, teller, claim key): the settlement's most salient beliefs are told first
        for teller in residents:
            mine = ctx.get(teller, "beliefs") or {}
            top = sorted(mine, key=lambda k: (-salience(mine[k]["claim"]) * mine[k]["conf"], k))[:TELL_CAP]
            candidates += [(-salience(mine[k]["claim"]) * mine[k]["conf"], teller, k) for k in top]
        budget, again = SETTLEMENT_TELLS, {}
        for _, teller, k in sorted(candidates):
            if budget <= 0:
                break
            b = (ctx.get(teller, "beliefs") or {}).get(k)
            if b is None:
                continue  # (dropped this season by a rival someone told them)
            charm = trait(ctx, teller, "charm")
            for hearer, closeness, trust in _listeners(ctx, teller, here):
                if budget <= 0:
                    break
                p = closeness * salience(b["claim"]) * (0.5 + 0.5 * charm)
                if not ctx.chance(p, "tell", owner=f"{teller}|{hearer}|{k}"):
                    continue
                said, came_from = b["claim"], ""
                if ctx.chance(DRIFT_RATE, "drift", owner=f"{teller}|{hearer}|{k}"):
                    mutated = drift(ctx, said)
                    if mutated:
                        said, came_from = mutated, k
                if tell(ctx, teller, hearer, said, trust, conf=b["conf"], cause=b["from"], drifted_from=came_from,
                        place=settlement):
                    budget -= 1
                elif key(said) in (ctx.get(hearer, "beliefs") or {}):
                    again.setdefault(hearer, set()).add(key(said))  # (heard again: it doesn't fade)
        self._reinforce(ctx, settlement, again)

    def _reinforce(self, ctx, settlement: str, again: dict) -> None:
        today = ctx.today.to_json()
        stale = {p: ks for p, ks in again.items()
                 if any((ctx.get(p, "beliefs") or {}).get(k, {}).get("heard") != today for k in ks)}
        if not stale:
            return
        ctx.emit("belief.reinforced", {"settlement": (settlement,)}, purpose="reinforce", actor=settlement,
                 payload={"people": len(stale)})
        for p, ks in sorted(stale.items()):
            beliefs = dict(ctx.get(p, "beliefs") or {})
            for k in sorted(ks):
                if k in beliefs:
                    beliefs[k] = {**beliefs[k], "heard": today}
            ctx.set(p, "beliefs", beliefs)

    def _fade(self, ctx, settlement: str, residents: list[str]) -> None:
        changed = {}
        for p in residents:
            before = ctx.get(p, "beliefs") or {}
            after = decayed(before, ctx.today)
            if after != before:
                changed[p] = after
        if changed:
            ctx.emit("belief.faded", {"settlement": (settlement,)}, purpose="fade", actor=settlement,
                     payload={"faded": len(changed)})
            for p, after in sorted(changed.items()):
                ctx.set(p, "beliefs", after)
