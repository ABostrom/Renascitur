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

**Grievances follow belief** (§8, #155): taking on (or being corrected to) a firm belief that someone
killed one's own (spouse, parent, child) holds it against them, right or wrong: a frame makes a feud
with the wrong person (and so the wrong house). Only a person is held to account (a claim drifted onto a
house names nobody to avenge), only for someone truly dead, never by one who knew it in secret (an
accomplice), and a correction adds its grievance beside any earlier one. `life.die`'s known-killer rule
gives way to this in a world with beliefs (`beliefs: true`).

**Secrets** (§5, #89): a belief taken on from a secret event is marked `secret`. Gossip never tells it;
it only **leaks**, a season's small chance (`LEAK_ACCOMPLICE`, or `LEAK_ACTOR` for the one who did it), to
someone the holder talks to, who holds it openly. Leaks come before the season's gossip and outside its
budget (they're rare). A kept secret doesn't fade. When a schemer is **exposed**, `reveal` brings out the
killings they hid: public evidence that corrects the cover for bystanders and the victim's kin.

**The masses** (§9, #88): each settlement's `shares` (`{claim key: {claim, share}}`, the share of its
masses holding each claim) move each season a step (`MASSES_FOLLOW`) toward its notables' mean confidence
(secrets aside), are scaled down within a topic so they never sum past 1, dropped under `SHARE_FLOOR`,
and capped at `SHARE_CAP` (`shares_step`, pure).

**News by road** (§7, #79): a traveller arriving tells residents what they believe (`on_arrival`). A
claim whose share in a settlement reaches `NEWS_THRESHOLD` goes out once along each open route
(`news_sent`), arriving after the route's days: it raises the destination's share by `NEWS_WEIGHT` and
one resident there hears it (`belief.heard`). News goes settlement to settlement: through a tavern or a
landmark on the way to the next settlement (`neighbour_settlements`), over the summed days; it is the
Vialux's official line (no drift, more trust) only if every leg was Vialux; wild roads drift twice as
often (`news_drift`, `news_trust`).

All of this runs only in a world whose params say `beliefs: true` (`enabled`): elsewhere history is as
it was. Systems that may perceive declare `PERCEIVE_READS`, `PERCEIVE_WRITES` and `EVENT_TYPES`.
"""

from __future__ import annotations

import math

from renasci.core.calendar import Date, Span
from renasci.core.canon import digest
from renasci.core.events import Cause, EventType
from renasci.core.systems import System

BELIEF_CAP, WITNESS_CAP = 16, 3
PARTICIPANT_CONF, BYSTANDER_CONF, CORRECTION_CONF = 0.9, 0.5, 0.85
TELL_CAP, SETTLEMENT_TELLS, DRIFT_RATE = 2, 40, 0.08
LEAK_ACTOR, LEAK_ACCOMPLICE = 0.02, 0.08  # a season's chance that a secret slips out (S6 §5)
MASSES_FOLLOW, SHARE_CAP, SHARE_FLOOR = 0.25, 12, 0.01  # belief shares among the masses (S6 §9)
NEWS_THRESHOLD, NEWS_WEIGHT, STRANGER_TRUST, VIALUX_TRUST = 0.3, 0.15, 0.4, 0.1  # news by road (S6 §7)
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
SHARES = EventType("belief.shares", 1, roles={"settlement": (1, 1)}, payload={"claims": "int"})
HEARD = EventType("belief.heard", 1, roles={"holder": (1, 1)},
                  payload={"claim": "json", "key": "str", "conf": "float"})  # (news from the road)
NEWS = EventType("belief.news", 1, roles={"settlement": (1, 1)},
                 payload={"claim": "json", "key": "str", "to": "str", "route": "str", "vialux": "bool"})
NEWS_ARRIVED = EventType("belief.news_arrived", 1, roles={"settlement": (1, 1)},
                         payload={"claim": "json", "key": "str", "from": "str", "drifted_from": "str"})
EVENT_TYPES = (PERCEIVED, TOLD, CORRECTED, FADED, REINFORCED, SHARES, NEWS, NEWS_ARRIVED, HEARD)
# What telling a newcomer's tale touches (travel.arrive declares these for the systems that handle arrivals).
ARRIVAL_READS = frozenset({"beliefs", "residents", "status", "journey", "ties", "a", "b", "kind", "strength",
                           "ended", "spouse", "mother", "father", "children", "grievances"})
ARRIVAL_WRITES = frozenset({"beliefs", "grievances"})
GRIEVANCE_CONF = 0.5  # how sure the kin must be of who killed their own to hold it against them (§8)
PERCEIVE_READS = frozenset({"beliefs", "residents", "status", "grievances", "mother", "father", "spouse", "children"})
PERCEIVE_WRITES = frozenset({"beliefs", "grievances"})


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
                "from": "", "heard": ctx.today.to_json(), **({"secret": True} if secret else {})}
    after = _capped(after)
    if k not in after:
        return False
    roles = {"holder": (person,), **({"teller": (teller,)} if teller else {})}
    event = ctx.emit(f"belief.{kind}", roles, purpose=f"belief:{k}", actor=person, place=place,
                     payload={"claim": c, "key": k, "conf": conf, **(extra or {})},
                     causes=(Cause("event", cause_event),), visibility="secret" if secret else None)
    after[k] = {**after[k], "from": event.id}
    ctx.set(person, "beliefs", dict(sorted(after.items())))
    if not secret:  # (one who knew it in secret was in on it: no grievance against a co-conspirator)
        _grieve(ctx, person, c, conf, event.id)
    return True


def perceive(ctx, event: str, settlement: str | None, participants, claim: dict, *, secret: bool = False,
             bystander_claim: dict | None = None, also: tuple[str, ...] = (), exclude=(),
             also_conf: float = BYSTANDER_CONF) -> list[str]:
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
    for w in bystanders:
        if ctx.status(w) == "active":
            hold(ctx, w, bystander_claim or claim, BYSTANDER_CONF, event)
            seen.append(w)
    for w in (a for a in also if a not in seen):  # (the victim's kin: they hear of it surely)
        if ctx.status(w) == "active":
            hold(ctx, w, bystander_claim or claim, also_conf, event)
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
    if not rivals and held >= conf and not (beliefs.get(k) or {}).get("secret"):
        return False  # (nothing to correct; but a secret made public is a change: it's no secret now)
    was_secret = bool((beliefs.get(k) or {}).get("secret"))
    after = {o: b for o, b in beliefs.items() if o not in rivals}
    after[k] = {"claim": c, "conf": conf, "since": (beliefs.get(k) or {}).get("since", ctx.today.to_json()),
                "from": "", "heard": ctx.today.to_json()}
    if k not in _capped(after):
        return False
    event = ctx.emit("belief.corrected", {"holder": (person,)}, purpose=f"correct:{k}", actor=person,
                     payload={"claim": c, "key": k, "conf": conf}, causes=(Cause("event", cause_event),))
    after[k] = {**after[k], "from": event.id}
    ctx.set(person, "beliefs", dict(sorted(_capped(after).items())))
    if not was_secret:
        _grieve(ctx, person, c, conf, event.id)
    return True


def decayed(beliefs: dict, today) -> dict:
    """One year's fading: a belief not heard or seen again for more than `DECAY_YEARS` loses `DECAY_STEP`;
    below `FORGET_BELOW` it is forgotten. Applied once a year, so the loss is one step a year."""
    year = today[1] if not isinstance(today, Date) else today.year
    out = {}
    for k, b in beliefs.items():
        if b.get("secret"):  # (nobody repeats a secret to its keeper; it isn't forgotten while kept)
            out[k] = b
            continue
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
                       "strength", "ended", "spouse", "mother", "father", "children", "traits", "house", "shares",
                       "news_sent", "ids:route", "ends", "days", "vialux", "open", "grievances"})
    writes = frozenset({"beliefs", "shares", "news_sent", "grievances"})
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
                self._masses(ctx, s, residents)

    def _gossip(self, ctx, settlement: str, residents: list[str], trait) -> None:
        here = set(residents)
        candidates = []  # (-weight, teller, claim key): the settlement's most salient beliefs are told first
        budget, again = SETTLEMENT_TELLS, {}
        for teller in residents:
            mine = ctx.get(teller, "beliefs") or {}
            budget -= self._leak(ctx, settlement, teller, mine, here)
            open_ = {k: b for k, b in mine.items() if not b.get("secret")}  # (secrets are never gossip)
            top = sorted(open_, key=lambda k: (-salience(open_[k]["claim"]) * open_[k]["conf"], k))[:TELL_CAP]
            candidates += [(-salience(open_[k]["claim"]) * open_[k]["conf"], teller, k) for k in top]
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

    def _leak(self, ctx, settlement: str, teller: str, mine: dict, here: set[str]) -> int:
        """A secret slipping out: told to one of those the holder talks to. Returns how many leaked."""
        leaked = 0
        for k in sorted(k for k, b in mine.items() if b.get("secret")):
            b = mine[k]
            rate = LEAK_ACTOR if b["claim"]["args"].get("by") == teller else LEAK_ACCOMPLICE
            if not ctx.chance(rate, "leak", owner=f"{teller}|{k}"):
                continue
            listeners = _listeners(ctx, teller, here)
            to = ctx.choose("leak", [h for h, _, _ in listeners], owner=f"{teller}|{k}") if listeners else None
            if to is None:
                continue
            trust = next(tr for h, _, tr in listeners if h == to)
            leaked += tell(ctx, teller, to, b["claim"], trust, conf=b["conf"], cause=b["from"], intent="leak",
                           place=settlement)
        return leaked

    def _masses(self, ctx, settlement: str, residents: list[str]) -> None:
        before = ctx.get(settlement, "shares") or {}
        after = shares_step(before, {p: ctx.get(p, "beliefs") or {} for p in residents})
        if shares_changed(before, after):
            ctx.emit("belief.shares", {"settlement": (settlement,)}, purpose="shares", actor=settlement,
                     payload={"claims": len(after)})
            ctx.set(settlement, "shares", after)
        self._send_news(ctx, settlement, ctx.get(settlement, "shares") or {})

    def _send_news(self, ctx, settlement: str, shares: dict) -> None:
        """A widely held claim goes out once to each neighbouring settlement by road, through any taverns
        or landmarks on the way (§7). `news_sent` remembers where each claim went (claims no longer in the
        shares are forgotten, so a claim that comes back can travel again)."""
        before = ctx.get(settlement, "news_sent") or {}
        sent = {k: list(v) for k, v in before.items() if k in shares}
        neighbours = neighbour_settlements(ctx, settlement) if any(
            s["share"] >= NEWS_THRESHOLD for s in shares.values()) else []
        out = []
        for k in sorted(shares):
            if shares[k]["share"] < NEWS_THRESHOLD:
                continue
            for to, days, vialux in neighbours:
                if to not in sent.get(k, []):
                    out.append((k, to, days, vialux))
                    sent[k] = sorted([*sent.get(k, []), to])
        if not out and sent == before:
            return
        for k, to, days, vialux in out:
            ctx.emit("belief.news", {"settlement": (settlement,)}, purpose=f"news:{k}:{to}", actor=settlement,
                     payload={"claim": shares[k]["claim"], "key": k, "to": to, "route": f"{settlement}>{to}",
                              "vialux": vialux})
            ctx.schedule(Span(days=days), "news", entity=to,
                         payload={"claim": shares[k]["claim"], "key": k, "from": settlement,
                                  "route": f"{settlement}>{to}", "vialux": vialux})
        if not out:  # (only forgetting: still needs an event to explain the write)
            ctx.emit("belief.news", {"settlement": (settlement,)}, purpose="news:forget", actor=settlement,
                     payload={"claim": {}, "key": "", "to": "", "route": "", "vialux": False})
        ctx.set(settlement, "news_sent", dict(sorted(sent.items())))

    def handle(self, ctx, activation):
        if activation.purpose != "news":
            raise ValueError(f"{self.name} has no follow-up {activation.purpose!r}")
        p = activation.payload
        to = activation.entity
        with ctx.scope(to):
            said, came_from = p["claim"], ""
            if ctx.chance(news_drift(p["vialux"]), "news_drift", owner=f"{p['from']}|{to}|{p['key']}"):
                mutated = drift(ctx, said)
                if mutated:
                    said, came_from = mutated, p["key"]
            k = key(said)
            arrived = ctx.emit("belief.news_arrived", {"settlement": (to,)}, purpose=f"news_in:{k}", actor=to,
                               payload={"claim": said, "key": k, "from": p["from"], "drifted_from": came_from})
            shares = dict(ctx.get(to, "shares") or {})
            boosted = dict(shares)
            boosted[k] = {"claim": said, "share": (shares.get(k) or {}).get("share", 0.0) + NEWS_WEIGHT}
            ctx.set(to, "shares", _normalised(boosted))
            here = sorted(r for r in ctx.get(to, "residents") if ctx.status(r) == "active" and not ctx.get(r, "journey"))
            hearer = ctx.choose("news_hearer", here, owner=f"{p['from']}|{to}|{k}") if here else None
            if hearer:  # (a stranger's news, as far as it's trusted)
                hold(ctx, hearer, said, news_trust(p["vialux"]), arrived.id, kind="heard")

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


def reveal(ctx, owner: str, cause_event: str, settlement: str | None) -> list[str]:
    """`owner` is exposed: every killing they hid (their secret beliefs that they killed someone, not only
    this scheme's) comes out as public evidence, correcting the cover for up to `WITNESS_CAP` people of `settlement` and the
    victim's kin. The owner's own belief stops being a secret. Returns the claims revealed."""
    from renasci.people.life import grieving  # (life -> beliefs: imported here)

    mine = dict(ctx.get(owner, "beliefs") or {})
    hidden = sorted(k for k, b in mine.items()
                    if b.get("secret") and b["claim"]["pred"] == "killed" and b["claim"]["args"]["by"] == owner)
    if hidden:  # (first, so the write is explained by the exposure itself)
        ctx.set(owner, "beliefs", {k: ({kk: v for kk, v in b.items() if kk != "secret"} if k in hidden else b)
                                   for k, b in mine.items()})
    for k in hidden:
        c = mine[k]["claim"]
        pool = sorted(r for r in (ctx.get(settlement, "residents") if settlement else [])
                      if r != owner and ctx.status(r) == "active")
        told = []
        for i in range(min(WITNESS_CAP, len(pool))):
            w = ctx.choose(f"reveal:{i}", [r for r in pool if r not in told], owner=f"{cause_event}|{k}")
            if w is None:
                break
            told.append(w)
        kin = [p for p in grieving(ctx, c["args"]["victim"]) if p != owner and ctx.status(p) == "active"]
        for p in [*told, *(x for x in kin if x not in told)]:
            correct(ctx, p, c, cause_event)  # (an accomplice among them knew already: no longer a secret)
    return hidden


def shares_step(shares: dict, people: dict) -> dict:
    """One season of the masses (§9): `shares` moved toward the mean confidence of `people` (each a
    notable's beliefs; secrets aside) in each claim, scaled within each topic to sum to at most 1,
    dropped under `SHARE_FLOOR`, capped at `SHARE_CAP`. Pure."""
    n = max(1, len(people))
    claims, sums = {}, {}
    for beliefs in people.values():
        for k, b in beliefs.items():
            if b.get("secret"):
                continue
            claims[k] = b["claim"]
            sums[k] = sums.get(k, 0.0) + b["conf"]
    for k, s in shares.items():
        claims.setdefault(k, s["claim"])
    moved, target = {}, {}
    for k in sorted(claims):
        old = shares.get(k, {}).get("share", 0.0)
        target[k] = sums.get(k, 0.0) / n
        moved[k] = old + MASSES_FOLLOW * (target[k] - old)
    by_topic: dict[str, list[str]] = {}
    for k in moved:
        by_topic.setdefault(topic(claims[k]), []).append(k)
    for ks in by_topic.values():
        total = sum(moved[k] for k in ks)
        if total > 1:
            for k in ks:
                moved[k] /= total
    # Rounded down, so a topic never sums past 1; dropped only when the share and where it is heading are
    # both under the floor (a claim a few hold must be able to take hold, starting small).
    kept = {k: math.floor(min(1.0, max(0.0, v)) * 1e4) / 1e4 for k, v in moved.items()
            if v >= SHARE_FLOOR or target[k] >= SHARE_FLOOR}
    kept = {k: v for k, v in kept.items() if v > 0}
    top = sorted(kept, key=lambda k: (-kept[k], k))[:SHARE_CAP]
    return {k: {"claim": claims[k], "share": kept[k]} for k in sorted(top)}


SHARE_STEP = 0.005  # a move smaller than this isn't written (shares converge slowly; this bounds the writes)


def shares_changed(before: dict, after: dict) -> bool:
    """Whether a settlement's shares changed enough to write: a claim came or went, or one moved by
    `SHARE_STEP` or more."""
    if set(before) != set(after):
        return True
    return any(abs(after[k]["share"] - before[k]["share"]) >= SHARE_STEP for k in after)



def news_drift(vialux: bool) -> float:
    """The chance news drifts on the road: never on the Vialux (the official line), twice the usual off it."""
    return 0.0 if vialux else 2 * DRIFT_RATE


def news_trust(vialux: bool) -> float:
    """How far a stranger's news is trusted: more when it came by the Vialux."""
    return STRANGER_TRUST + (VIALUX_TRUST if vialux else 0.0)


def _normalised(shares: dict) -> dict:
    """Shares scaled within each topic to sum to at most 1 (rounded down) and capped, as `shares_step` does."""
    by_topic: dict[str, list[str]] = {}
    for k, s in shares.items():
        by_topic.setdefault(topic(s["claim"]), []).append(k)
    out = {}
    for ks in by_topic.values():
        total = sum(shares[k]["share"] for k in ks)
        for k in ks:
            v = shares[k]["share"] / total if total > 1 else shares[k]["share"]
            out[k] = {"claim": shares[k]["claim"], "share": math.floor(min(1.0, max(0.0, v)) * 1e4) / 1e4}
    out = {k: s for k, s in out.items() if s["share"] > 0}
    top = sorted(out, key=lambda k: (-out[k]["share"], k))[:SHARE_CAP]  # (news can be crowded out at once)
    return {k: out[k] for k in sorted(top)}


def on_arrival(ctx, person: str, settlement: str) -> None:
    """A traveller arriving tells residents what they believe (§7): their `TELL_CAP` most salient open
    beliefs, to those they know there first and then to strangers, up to `TELL_CAP` hearers."""
    if not enabled(ctx):
        return
    mine = {k: b for k, b in (ctx.get(person, "beliefs") or {}).items() if not b.get("secret")}
    if not mine:
        return
    here = sorted(r for r in ctx.get(settlement, "residents")
                  if r != person and ctx.status(r) == "active" and not ctx.get(r, "journey"))
    known = sorted(_listeners(ctx, person, set(here)), key=lambda x: (-x[1], -x[2], x[0]))  # (closest first)
    hearers = [(h, tr) for h, _, tr in known][:TELL_CAP]
    strangers = [r for r in here if r not in {h for h, _ in hearers}]
    while len(hearers) < TELL_CAP and strangers:
        s = ctx.choose(f"stranger:{len(hearers)}", strangers, owner=f"arrive|{person}")
        strangers.remove(s)
        hearers.append((s, STRANGER_TRUST))
    top = sorted(mine, key=lambda k: (-salience(mine[k]["claim"]) * mine[k]["conf"], k))[:TELL_CAP]
    for k in top:
        for h, trust in hearers:
            tell(ctx, person, h, mine[k]["claim"], trust, conf=mine[k]["conf"], cause=mine[k]["from"], place=settlement)


def neighbour_settlements(ctx, settlement: str) -> list[tuple[str, int, bool]]:
    """The settlements next to `settlement` by road: [(settlement, days, all on the Vialux)], each by its
    quickest way over open routes, passing through places that aren't settlements (taverns, landmarks)
    but stopping at the first settlement reached. Ties go to the smaller path of place ids."""
    import heapq

    towns = set(ctx.ids("settlement"))
    edges: dict[str, list[tuple[str, int, bool]]] = {}
    for r in ctx.ids("route"):
        if not ctx.get(r, "open"):
            continue
        a, b = ctx.get(r, "ends")
        days, vialux = int(ctx.get(r, "days")), bool(ctx.get(r, "vialux"))
        edges.setdefault(a, []).append((b, days, vialux))
        edges.setdefault(b, []).append((a, days, vialux))
    best: dict[str, tuple[int, list[str], bool]] = {}
    heap = [(0, [settlement], True)]
    while heap:
        days, path, vialux = heapq.heappop(heap)
        at = path[-1]
        if at in best:
            continue
        best[at] = (days, path, vialux)
        if at != settlement and at in towns:
            continue  # (news stops at the first settlement: it travels on from there with its own share)
        for nxt, d, v in edges.get(at, ()):
            if nxt not in best:
                heapq.heappush(heap, (days + d, [*path, nxt], vialux and v))
    return [(s, best[s][0], best[s][2]) for s in sorted(best) if s != settlement and s in towns]


def _grieve(ctx, person: str, c: dict, conf: float, event: str) -> None:
    """A firm belief that someone killed one's own: the grievance, held once per killer and victim."""
    if c["pred"] != "killed" or conf < GRIEVANCE_CONF:
        return
    victim, by = c["args"]["victim"], c["args"]["by"]
    if by == person or not ctx.exists(by) or ctx.kind(by) != "person" or not ctx.exists(victim)             or ctx.status(victim) != "dead":  # (a lie that someone living was killed grieves nobody)
        return
    kin = {ctx.get(victim, "spouse"), ctx.get(victim, "mother"), ctx.get(victim, "father"),
           *(ctx.get(victim, "children") or [])}
    if person not in kin:
        return
    held = ctx.get(person, "grievances") or []
    if any(g["against"] == by and g.get("about") == victim for g in held):
        return
    ctx.set(person, "grievances", [*held, {"against": by, "event": event, "kind": "killed", "about": victim,
                                           "since": ctx.today.to_json()}])
