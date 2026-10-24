"""One-line readings of events and claims, with names (S12 spec §2): what packs, chronicles and briefs say.

`Names(state, geography)` knows what everyone and everywhere is called. `reading(event, names)` reads an
event in one plain line ("Jory died at Lux Oescus, killed by Gwen"), from a template per event type; a
type with no template gets a generic line from its roles. Bookkeeping events (a season's population
step, minds and ties updated, a town's talk reinforced) read as None: they aren't story. Claims read
through their predicate (`beliefs.PREDICATES`), with an event named by its own reading's noun.
"""

from __future__ import annotations

BOOKKEEPING = {
    "people.population", "people.drives", "people.minds", "people.ties", "belief.reinforced", "belief.shares",
    "belief.faded", "engine.cast", "engine.cast_column", "lod.promote", "lod.demote", "people.scheme_replanned",
}


class Names:
    """What every entity and place in a run is called (a person's house after their name, when they have one)."""

    def __init__(self, state: dict, geography: dict | None = None):
        self.names: dict[str, str] = {p["id"]: p["name"] for p in (geography or {}).get("places", []) if p.get("name")}
        self.names |= {r["id"]: r["name"] for r in (geography or {}).get("regions", []) if r.get("name")}
        ents = {e["id"]: e for e in state.get("entities", [])}
        for i, e in ents.items():
            n = e["fields"].get("name")
            if n:
                self.names[i] = n
        self.house = {i: e["fields"].get("house") for i, e in ents.items() if e["kind"] == "person"}
        self.houses = {h for h in self.house.values() if h} | {i for i, e in ents.items() if e["kind"] == "house"}

    def __call__(self, ident) -> str:
        if not isinstance(ident, str):
            return str(ident)
        return self.names.get(ident, ident)

    def full(self, ident: str) -> str:
        """A person with their house ("Gwen of House Ridge"); a house as "House Ridge"."""
        if ident in self.houses:
            return f"House {self(ident)}"
        h = self.house.get(ident)
        return f"{self(ident)} of House {self(h)}" if h and self(h) != h else self(ident)


def _one(ev: dict, role: str):
    return (ev.get("roles", {}).get(role) or [None])[0]


def _at(ev: dict, n: Names) -> str:
    return f" at {n(ev['place'])}" if ev.get("place") else ""


def _death(ev, n):
    who, by = _one(ev, "deceased"), _one(ev, "killer")
    cause = str((ev.get("payload") or {}).get("cause") or "")
    if by:
        how = f", killed by {n.full(by)}"
    elif not cause or cause in n.names or ":" in cause:  # (an id as cause: the killer's hand is in the roles)
        how = ""
    elif cause.split()[0] in ("fell", "was", "died", "drowned", "took", "lost"):  # (a clause: "fell in a duel")
        return f"{n.full(who)} {cause}{_at(ev, n)}"
    else:  # (a noun: "night terrors", "a sudden illness", "old age")
        how = f", of {cause}"
    return f"{n.full(who)} died{_at(ev, n)}{how}"


def _action(ev, n):
    p = ev.get("payload") or {}
    who, whom = _one(ev, "actor"), _one(ev, "target")
    what = str(p.get("action") or "acted")
    verb, takes = VERBS.get(what, (what.lower(), True))
    obj = f" {n.full(whom)}" if whom and takes else ""
    outcome = p.get("outcome")
    if outcome in ("failure", "exposed"):  # (it didn't happen: they tried)
        tail = " and failed" if outcome == "failure" else ", and was found out"
        return f"{n.full(who)} tried to {TRIED.get(what, verb)}{obj}{tail}"
    return f"{n.full(who)} {verb}{obj}"


# (an action's verb, and whether it takes the target as its object; the "tried to" form for failures)
VERBS = {"Duel": ("fought a duel with", True), "Poison": ("poisoned", True), "Assassinate": ("had assassinated", True),
         "Court": ("courted", True), "Petition": ("petitioned against", True), "Shame": ("shamed", True),
         "Recruit": ("recruited", True), "CourtFavour": ("courted favour at court", False), "Flee": ("fled", False),
         "Confess": ("confessed", False), "Slander": ("slandered", True), "Frame": ("framed", True),
         "BearWitness": ("bore witness against", True)}
TRIED = {"Duel": "fight a duel with", "Poison": "poison", "Assassinate": "have assassinated", "Court": "court",
         "Petition": "petition against", "Shame": "shame", "Recruit": "recruit", "CourtFavour": "court favour at court",
         "Flee": "flee", "Confess": "confess", "Slander": "slander", "Frame": "frame", "BearWitness": "bear witness against"}
TIES = {"friend": "friends", "rival": "rivals", "enemy": "enemies", "mentor": "mentor and pupil", "lover": "lovers"}
AMBITION_ENDS = {"fulfilled": "fulfilled", "thwarted": "thwarted", "abandoned": "given up",
                 "died_unfulfilled": "unfulfilled when they died", "moot": "overtaken by events"}
SCHEME_ENDS = {"succeeded": "succeeded", "failed": "failed", "exposed": "was exposed", "abandoned": "was given up",
               "moot": "came to nothing"}

def _ties(kind) -> str:
    return TIES.get(kind, f"{kind or 'tied'}s")


TEMPLATES = {
    "people.birth": lambda ev, n: f"{', '.join(n.full(c) for c in ev['roles'].get('child', []))} "
                                  f"{'was' if len(ev['roles'].get('child', [])) == 1 else 'were'} born to "
                                  f"{n.full(_one(ev, 'mother'))}{(' and ' + n.full(_one(ev, 'father'))) if _one(ev, 'father') else ''}{_at(ev, n)}",
    "people.death": _death,
    "people.near_miss": lambda ev, n: f"{n.full(_one(ev, 'survivor'))} survived what should have killed them{_at(ev, n)}",
    "people.marriage": lambda ev, n: f"{n.full(ev['roles']['spouse'][0])} married {n.full(ev['roles']['spouse'][1])}{_at(ev, n)}",
    "people.succession": lambda ev, n: f"{n.full(_one(ev, 'successor'))} succeeded"
                                       f"{(' ' + n.full(_one(ev, 'predecessor'))) if _one(ev, 'predecessor') else ''}",
    "people.heir_named": lambda ev, n: f"{n.full(_one(ev, 'heir'))} was named heir to {n.full(_one(ev, 'holder'))}"
                                       if _one(ev, "heir") else f"{n.full(_one(ev, 'holder'))} had no heir",
    "people.house_extinct": lambda ev, n: f"House {n((ev.get('payload') or {}).get('house'))} ended with {n.full(_one(ev, 'last'))}",
    "people.action": _action,
    "people.ambition_formed": lambda ev, n: f"{n.full(_one(ev, 'owner'))} set out to "
                                            f"{(ev.get('payload') or {}).get('text') or 'pursue an ambition'}",
    "people.ambition_resolved": lambda ev, n: f"{n.full(_one(ev, 'owner'))}'s ambition was "
                                              f"{AMBITION_ENDS.get((ev.get('payload') or {}).get('status'), 'resolved')}",
    "people.scheme_begun": lambda ev, n: f"{n.full(_one(ev, 'owner'))} began a scheme"
                                         f"{(' against ' + n.full(_one(ev, 'target'))) if _one(ev, 'target') else ''}",
    "people.scheme_ended": lambda ev, n: f"{n.full(_one(ev, 'owner'))}'s scheme "
                                         f"{SCHEME_ENDS.get((ev.get('payload') or {}).get('state'), 'ended')}",
    "people.scheme_exposed": lambda ev, n: f"{n.full(_one(ev, 'owner'))}'s scheme was exposed",
    "people.tie_formed": lambda ev, n: f"{n.full(_one(ev, 'a'))} and {n.full(_one(ev, 'b'))} became "
                                       f"{_ties((ev.get('payload') or {}).get('kind'))}",
    "people.tie_ended": lambda ev, n: f"{n.full(_one(ev, 'a'))} and {n.full(_one(ev, 'b'))} were no longer "
                                      f"{_ties((ev.get('payload') or {}).get('kind'))}",
    "people.depart": lambda ev, n: f"{n.full(_one(ev, 'traveller'))} set out from {n(_one(ev, 'origin'))} for {n(_one(ev, 'destination'))}",
    "people.arrive": lambda ev, n: f"{n.full(_one(ev, 'traveller'))} arrived at {n(_one(ev, 'destination'))}",
    "ward.contract_lost": lambda ev, n: f"{n.full(_one(ev, 'loser'))} lost an ore contract to {n.full(_one(ev, 'winner'))}",
    "ward.sabotage": lambda ev, n: f"{n.full(_one(ev, 'ordered_by'))} had the ward-stones cracked",
    "ward.failure": lambda ev, n: f"the wards failed on the road{_at(ev, n)}, with {n.full(_one(ev, 'leader'))}'s caravan on it",
    "ward.testimony": lambda ev, n: f"{n.full(_one(ev, 'witness'))} bore witness to what happened to the wards",
    "geo.changed": lambda ev, n: f"the map changed{_at(ev, n)}: {(ev.get('payload') or {}).get('why') or 'a change'}",
    "belief.perceived": lambda ev, n: f"{n.full(_one(ev, 'holder'))} came to believe it",
    "belief.told": lambda ev, n: f"{n.full(_one(ev, 'teller'))} {'lied to' if (ev.get('payload') or {}).get('intent') == 'lie' else 'told'} "
                                 f"{n.full(_one(ev, 'holder'))}",
    "belief.corrected": lambda ev, n: f"{n.full(_one(ev, 'holder'))} learned the truth",
    "belief.heard": lambda ev, n: f"{n.full(_one(ev, 'holder'))} heard it as news from the road",
    "belief.news": lambda ev, n: f"news went out from {n(_one(ev, 'settlement'))}",
    "belief.news_arrived": lambda ev, n: f"news reached {n(_one(ev, 'settlement'))}",
    "belief.rumour": lambda ev, n: f"a rumour started in {n(_one(ev, 'settlement'))}",
}


def reading(ev: dict, names: Names, by_id: dict | None = None) -> str | None:
    """The event in one line, or None for bookkeeping. A belief event says what was believed, told or
    heard (its claim), naming an event in the claim by its noun (`by_id`: the run's events)."""
    if ev["type"] in BOOKKEEPING or ev["type"].startswith("ripple."):
        return None
    t = TEMPLATES.get(ev["type"])
    if t is not None:
        try:
            line = t(ev, names)
        except (KeyError, IndexError, TypeError):  # (an odd payload: the generic line)
            line = None
        if line:
            claim = (ev.get("payload") or {}).get("claim") if ev["type"].startswith("belief.") else None
            if isinstance(claim, dict) and claim.get("pred"):
                line += f": {claim_text(claim, names, by_id)}"
            return line[0].upper() + line[1:]
    who = "; ".join(f"{role} {', '.join(names.full(x) for x in xs)}" for role, xs in sorted(ev.get("roles", {}).items()) if xs)
    what = ev["type"].split(".", 1)[-1].replace("_", " ")
    return f"A {what}{_at(ev, names)}{(': ' + who) if who else ''}"


NOUNS = {"people.death": "the death", "people.birth": "the birth", "people.marriage": "the marriage",
         "people.action": "the deed", "people.succession": "the succession"}


def noun(ev: dict | None) -> str:
    """How a claim names an event: "the ward failure"."""
    if not ev:
        return "it"
    return NOUNS.get(ev["type"]) or f"the {ev['type'].split('.', 1)[-1].replace('_', ' ') if ev['type'].startswith('people.') else ev['type'].replace('.', ' ').replace('_', ' ')}"


def claim_text(claim: dict, names: Names, by_id: dict | None = None) -> str:
    """A claim with names (people by name and house; an event by its noun)."""
    from renasci.people.beliefs import PREDICATES

    a = claim["args"]
    pred = PREDICATES.get(claim["pred"])
    if claim["pred"] in ("caused", "fault"):
        ev = (by_id or {}).get(a.get("event"))
        who = names.full(a.get("by") or a.get("party")) if (a.get("by") or a.get("party")) in names.names else (a.get("by") or a.get("party"))
        return f"{who} caused {noun(ev)}" if claim["pred"] == "caused" else f"{noun(ev)} was the fault of {who}"
    if claim["pred"] == "killed":
        return f"{names.full(a['victim'])} was killed by {names.full(a['by'])}"
    if pred is not None:
        return pred.text(a, {k: names(k) for k in a.values() if isinstance(k, str)})
    return f"{claim['pred']}({', '.join(names(v) for v in a.values())})"
