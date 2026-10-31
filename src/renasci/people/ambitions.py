"""Ambitions (S7 spec §3): what notables want, and how wanting ends.

An `Ambition` is a stateless class; a live ambition is a store record (kind `ambition`) naming it:
`owner`, `class`, `target`, `formed`, `state` (active, fulfilled, thwarted, abandoned, died_unfulfilled;
`status` is the store's own field), `resolved`, `scheme`, `born_of`. The owner lists their
active ambitions in `ambitions` and keeps `cooldowns` ({class: the year it may form again}).

`people.ambitions` (yearly, per settlement scope, after drives) for each adult resident:

1. **resolves** each active ambition: `satisfied` -> fulfilled; `moot` or no longer `eligible` ->
   abandoned (eligibility is deterministic, so no draw ever abandons an ambition by chance);
2. **forms** each class (in name order) that is eligible, past its cooldown and not already held, with
   a keyed chance of its `urge` (`owner=person`, `purpose=form:<class>`). The formation event is caused
   by what the ambition was born of (a drive, an event, a wound).

Death resolves every active ambition as `died_unfulfilled` (`on_death`, called by `life.die`).

**Traits by role:** classes read `wits`, `temper` and `charm` through the ruleset param `traits`
({role: trait name in the world's catalogue}); a role the world doesn't map reads 0.5 (§12).
"""

from __future__ import annotations

from dataclasses import dataclass

from renasci.core.events import Cause, EventType
from renasci.core.pools import pools
from renasci.core.systems import System
from renasci.people.races import age_years

SHAMED = -0.25  # (actions.SHAMED: in disgrace)
HUNGRY_RISING = 0.15  # (Secede's urge in a house whose seat is starving)

FORMED = EventType("people.ambition_formed", 1, roles={"owner": (1, 1), "ambition": (1, 1), "target": (0, 1)},
                   payload={"class": "str", "text": "str"})
RESOLVED = EventType("people.ambition_resolved", 1, roles={"owner": (1, 1), "ambition": (1, 1)},
                     payload={"status": "str"}, dead_roles=("owner",))
EVENT_TYPES = (FORMED, RESOLVED)
ADULT = 16


def trait(ctx, person: str, role: str) -> float:
    """A trait by its role (wits, temper, charm), through the world's mapping; 0.5 if unmapped."""
    name = (ctx.params.get("traits") or {}).get(role)
    if not name:
        return 0.5
    return float((ctx.get(person, "traits") or {}).get(name, 0.5))


@dataclass(frozen=True)
class Formation:
    target: str | None
    born_of: tuple[str, str]  # a cause: ("drive", "belonging"), ("event", id), ("wound", kind)


LIBRARY = pools.define("ambitions")  # (a class joins with `@LIBRARY.add`)


class Ambition:
    name = ""
    cooldown_years = 5
    reads: frozenset[str] = frozenset()

    def eligible(self, ctx, person) -> Formation | None:
        raise NotImplementedError

    def urge(self, ctx, person) -> float:
        return 0.3

    def subgoals(self, ctx, amb) -> list[frozenset[str]]:
        return []

    def satisfied(self, ctx, amb) -> bool:
        return False

    def moot(self, ctx, amb) -> bool:
        target = ctx.get(amb, "target")
        return target is not None and ctx.status(target) != "active"

    def keeps(self, ctx, amb) -> bool:
        """Whether the yearly pass keeps an unmet ambition: while a scheme pursues it, the scheme decides;
        otherwise while it is still eligible."""
        return ctx.get(amb, "scheme") is not None or self.eligible(ctx, ctx.get(amb, "owner")) is not None

    def formed(self, ctx, amb, formation: Formation) -> None:
        """Called once the record exists (Vengeance takes up its grievance here)."""

    def text(self, ctx, owner, target) -> str:
        return self.name.lower()


@LIBRARY.add
class Marry(Ambition):
    name, cooldown_years = "Marry", 3
    reads = frozenset({"spouse", "drives", "race", "born"})

    def eligible(self, ctx, person):
        from renasci.people.life import world

        races, _, _ = world(ctx)
        lo, hi = races[ctx.get(person, "race")].marriage
        age = age_years(ctx.calendar, ctx.get(person, "born"), ctx.today)
        belonging = (ctx.get(person, "drives") or {}).get("belonging", 1.0)
        if ctx.get(person, "spouse") is None and lo <= age <= hi and belonging < 0.5:
            return Formation(None, ("drive", "belonging"))
        return None

    def urge(self, ctx, person):
        return 0.6

    def subgoals(self, ctx, amb):
        return [frozenset({"married"})]

    def satisfied(self, ctx, amb):
        return ctx.get(ctx.get(amb, "owner"), "spouse") is not None

    def text(self, ctx, owner, target):
        return "find a spouse"


@LIBRARY.add
class Standing(Ambition):
    name, cooldown_years = "Standing", 6
    reads = frozenset({"house", "drives", "favour", "name"})

    def eligible(self, ctx, person):
        if ctx.get(person, "house") is None:
            return None
        status = (ctx.get(person, "drives") or {}).get("status", 1.0)
        if status < 0.6:
            return Formation(None, ("drive", "status"))
        return None

    def urge(self, ctx, person):
        return 0.1 + 0.3 * trait(ctx, person, "charm")

    def subgoals(self, ctx, amb):
        return [frozenset({"favoured"})]

    def satisfied(self, ctx, amb):
        return float(ctx.get(ctx.get(amb, "owner"), "favour") or 0.0) >= 0.5

    def text(self, ctx, owner, target):
        house = ctx.get(owner, "house")
        return f"raise House {ctx.get(house, 'name') or house} high at court"


@LIBRARY.add
class Seize(Ambition):
    """A succession plot: take the house's headship by removing those ahead in the line (up to three)."""

    name, cooldown_years = "Seize", 10
    reads = frozenset({"house", "headship", "holder", "rule", "children", "father", "mother", "sex", "status",
                       "drives", "traits", "offices", "extinct", "legitimacy", "deposed"})

    def _ahead(self, ctx, person):
        from renasci.people.houses import RULES

        house = ctx.get(person, "house")
        if house is None or ctx.get(house, "extinct") is not None:
            return None
        office = ctx.get(house, "headship")
        holder = ctx.get(office, "holder")
        if holder is None or holder == person or ctx.status(holder) != "active":
            return None
        line = RULES[ctx.get(office, "rule")].candidates(ctx, office, holder)
        if person not in line:
            return None
        return [holder] + line[:line.index(person)]

    def eligible(self, ctx, person):
        ahead = self._ahead(ctx, person)
        if not ahead or len(ahead) > 3:
            return None  # too far down the line to plot
        status = (ctx.get(person, "drives") or {}).get("status", 1.0)
        if trait(ctx, person, "temper") < 0.6 and status >= 0.5:
            return None  # content, or not hot-blooded enough
        return Formation(ahead[0], ("drive", "status"))

    def urge(self, ctx, person):
        return 0.05 + 0.25 * trait(ctx, person, "temper")

    def subgoals(self, ctx, amb):
        ahead = self._ahead(ctx, ctx.get(amb, "owner")) or []
        return [frozenset(f"dead:{p}" for p in ahead)] if ahead else []

    def satisfied(self, ctx, amb):
        owner = ctx.get(amb, "owner")
        house = ctx.get(owner, "house")
        return bool(house) and ctx.get(ctx.get(house, "headship"), "holder") == owner

    def moot(self, ctx, amb):  # the holder's death is the plot's aim; once no plot runs, a changed seat ends it
        if ctx.get(amb, "scheme") is not None:
            return False
        house = ctx.get(ctx.get(amb, "owner"), "house")
        return not house or ctx.get(ctx.get(house, "headship"), "holder") != ctx.get(amb, "target")

    def text(self, ctx, owner, target):
        house = ctx.get(owner, "house")
        return f"take the seat of House {ctx.get(house, 'name') or house}"


def throne(ctx, person: str) -> tuple[str, str] | None:
    """The first realm (by id) whose ruler's office `person` could plot to take: (polity, office). They must
    head or be heir to a member house; not of the ruler's own house (that's Seize), nor its holder; and the
    office isn't already seized, nor one canon names a successor to."""
    house = ctx.get(person, "house")
    if house is None:
        return None
    headship = ctx.get(house, "headship")
    if person not in (ctx.get(headship, "holder"), ctx.get(headship, "heir")):
        return None
    for polity in ctx.ids("polity"):
        office = ctx.get(polity, "ruler")
        if not office or ctx.get(polity, "ended") is not None or house not in (ctx.get(polity, "members") or []):
            continue
        holder = ctx.get(office, "holder")
        if holder is None or holder == person or ctx.status(holder) != "active" or ctx.get(office, "house") == house                 or ctx.get(holder, "house") == house or ctx.get(office, "legitimacy") == "seized"                 or ctx.succession_pinned(office):  # (a seized throne is the deposed line's to win back)
            continue
        return polity, office
    return None


@LIBRARY.add
class Usurp(Ambition):
    """Take a realm's ruling office (S8 §9): Seize's ambition, beyond one's own house. Its plot is a Coup."""

    name, cooldown_years = "Usurp", 15
    reads = frozenset({"house", "headship", "holder", "heir", "ids:polity", "ruler", "ended", "members", "status",
                       "drives", "traits", "deposed", "offices", "legitimacy"})

    def eligible(self, ctx, person):
        found = throne(ctx, person)
        if found is None:
            return None
        status = (ctx.get(person, "drives") or {}).get("status", 1.0)
        if trait(ctx, person, "temper") < 0.6 and status >= 0.5:
            return None  # content, or not hot-blooded enough
        return Formation(ctx.get(found[1], "holder"), ("drive", "status"))

    def urge(self, ctx, person):
        return 0.02 + 0.1 * trait(ctx, person, "temper")

    def subgoals(self, ctx, amb):
        return [frozenset({f"seized:{ctx.get(amb, 'target')}"})]

    def satisfied(self, ctx, amb):  # (they hold the office they took from its holder: `seized:<target>`)
        target = ctx.get(amb, "target")
        return any(ctx.get(o, "deposed") == target for o in ctx.get(ctx.get(amb, "owner"), "offices") or [])

    def moot(self, ctx, amb):  # (a plot under way decides; else the ruler gone, or no longer the ruler, ends it)
        if ctx.get(amb, "scheme") is not None:
            return False
        found = throne(ctx, ctx.get(amb, "owner"))
        return found is None or ctx.get(found[1], "holder") != ctx.get(amb, "target")

    def text(self, ctx, owner, target):
        return f"take the realm's rule from {ctx.get(target, 'name') or target}"


def ruled(ctx, person: str) -> str | None:
    """The realm `person` rules (holds its ruler's office), if any (the first by id). Someone who holds no
    office reads nothing more."""
    held = ctx.get(person, "offices") or []
    if not held:
        return None
    for polity in ctx.ids("polity"):
        if ctx.get(polity, "ruler") in held and ctx.get(polity, "ended") is None:
            return polity
    return None


def border_places(ctx, mine: str, other: str) -> list[str]:
    """`other`'s places at the end of a route whose far end `mine` holds: what a war with them would take."""
    out = set()
    for route in ctx.ids("route"):
        a, b = ctx.get(route, "ends")
        held = (ctx.get(a, "control"), ctx.get(b, "control"))
        if held == (mine, other):
            out.add(b)
        elif held == (other, mine):
            out.add(a)
    return sorted(out)


@LIBRARY.add
class Expand(Ambition):
    """A ruler wants a neighbour's border places (S8 §9): their plot is raids across the line, souring the
    relation to hostile, and the ambition itself is a casus belli (`war.casus_belli`). Won when a place
    claimed at its forming (`claims`) is held by the ruler's realm."""

    name, cooldown_years = "Expand", 12
    reads = frozenset({"ids:polity", "ruler", "holder", "ended", "ids:relation", "a", "b", "kind", "stance", "ids:route",
                       "ends", "control", "traits", "drives", "claims", "offices"})
    WANTING = ("cold", "hostile", "war")

    def _wanted(self, ctx, mine, other) -> bool:
        """Still a neighbour worth taking from: at odds, and bordering."""
        from renasci.relations import rel_id

        rid = rel_id(mine, other)
        return ctx.exists(rid) and ctx.get(rid, "stance") in self.WANTING and ctx.get(other, "ended") is None \
            and bool(border_places(ctx, mine, other))

    def _neighbour(self, ctx, person):
        mine = ruled(ctx, person)
        if mine is None:
            return None
        for rid in ctx.ids("relation"):
            if ctx.get(rid, "kind") != "polity" or ctx.get(rid, "stance") not in self.WANTING:
                continue
            a, b = ctx.get(rid, "a"), ctx.get(rid, "b")
            if mine not in (a, b):
                continue
            other = b if a == mine else a
            if self._wanted(ctx, mine, other):
                return mine, other
        return None

    def claims(self, ctx, mine, other):
        return border_places(ctx, mine, other)

    def eligible(self, ctx, person):
        found = self._neighbour(ctx, person)
        if found is None:
            return None
        status = (ctx.get(person, "drives") or {}).get("status", 1.0)
        if trait(ctx, person, "temper") < 0.6 and status >= 0.5:
            return None
        return Formation(found[1], ("drive", "status"))

    def urge(self, ctx, person):
        return 0.05 + 0.2 * trait(ctx, person, "temper")

    def formed(self, ctx, amb, formation):
        mine = ruled(ctx, ctx.get(amb, "owner"))
        ctx.set(amb, "claims", {"polity": mine, "places": self.claims(ctx, mine, formation.target)})

    def subgoals(self, ctx, amb):
        return [frozenset({f"hostile:{ctx.get(amb, 'target')}"})]

    def satisfied(self, ctx, amb):
        claims = ctx.get(amb, "claims") or {}
        return any(ctx.get(p, "control") == claims.get("polity") for p in claims.get("places") or [])

    def moot(self, ctx, amb):  # (the neighbour has fallen, or the owner no longer rules the realm that claimed)
        return ctx.get(ctx.get(amb, "target"), "ended") is not None \
            or ruled(ctx, ctx.get(amb, "owner")) != (ctx.get(amb, "claims") or {}).get("polity")

    def keeps(self, ctx, amb):  # (a plot under way decides; else while this neighbour is still at odds and bordering)
        if ctx.get(amb, "scheme") is not None:
            return True
        mine = (ctx.get(amb, "claims") or {}).get("polity")
        return bool(mine) and self._wanted(ctx, mine, ctx.get(amb, "target"))

    def text(self, ctx, owner, target):
        return f"take the borderlands of {ctx.get(target, 'name') or target}"


def governed(ctx, person: str) -> tuple[str, str] | None:
    """(the realm, the house) for a house head whose seat a realm governs but doesn't rule from: not the
    ruler's own house, nor seated in the realm's capital. A Secede ambition's ground."""
    house = ctx.get(person, "house")
    if house is None or ctx.get(ctx.get(house, "headship"), "holder") != person:
        return None
    seat = ctx.get(house, "seat")
    polity = ctx.get(seat, "control") if seat else None
    if polity is None or ctx.get(polity, "ended") is not None or house not in (ctx.get(polity, "members") or []):
        return None
    if seat == ctx.get(polity, "seat") or ctx.get(polity, "ruler") == ctx.get(house, "headship"):
        return None
    ruler = ctx.get(ctx.get(polity, "ruler"), "holder") if ctx.get(polity, "ruler") else None
    if ruler and ctx.get(ruler, "house") == house:  # (the ruler's own house, whatever office the realm is ruled by)
        return None
    return polity, house


@LIBRARY.add
class Secede(Ambition):
    """A house seated in a governed town wants out (S8 §9): its head, hot-blooded and out of favour (or
    wanting status), rallies another house (`Rally`) and rises (`Revolt`): a realm of its own at its seat,
    and a war to crush it. Won when the house is no longer the realm's."""

    name, cooldown_years = "Secede", 20
    reads = frozenset({"house", "headship", "holder", "seat", "control", "ended", "members", "ruler", "favour",
                       "traits", "drives", "famine"})

    def eligible(self, ctx, person):
        found = governed(ctx, person)
        if found is None:
            return None
        status = (ctx.get(person, "drives") or {}).get("status", 1.0)
        if trait(ctx, person, "temper") < 0.6 or (float(ctx.get(person, "favour") or 0.0) >= 0.0 and status >= 0.5):
            return None  # (hot-blooded, and slighted: out of favour, or wanting standing)
        return Formation(found[0], ("drive", "status"))

    def urge(self, ctx, person):
        hungry = 0.0
        if (ctx.params.get("ecology") or {}).get("famine") is not None:  # (a starving seat stirs it: S10 #129)
            seat = ctx.get(ctx.get(person, "house"), "seat")
            hungry = HUNGRY_RISING if seat and ctx.get(seat, "famine") else 0.0
        return 0.02 + 0.08 * trait(ctx, person, "temper") + hungry

    def subgoals(self, ctx, amb):
        return [frozenset({f"seceded:{ctx.get(amb, 'target')}"})]

    def satisfied(self, ctx, amb):
        house = ctx.get(ctx.get(amb, "owner"), "house")
        return bool(house) and house not in (ctx.get(ctx.get(amb, "target"), "members") or [])

    def moot(self, ctx, amb):
        return ctx.get(ctx.get(amb, "target"), "ended") is not None

    def text(self, ctx, owner, target):
        return f"break free of {ctx.get(target, 'name') or target}"


@LIBRARY.add
class Leave(Ambition):
    """A notable starving in a famine wants out (S10 §3, #129): unwed and holding no office (families and
    officers stay: S4), they flee (`Flee`) to a town within reach. Won once they live elsewhere; dropped when
    the famine ends."""

    name, cooldown_years = "Leave", 3
    reads = frozenset({"drives", "place", "famine", "spouse", "offices", "journey", "plots"})

    def eligible(self, ctx, person):
        from renasci.people.drives import Food

        if (ctx.params.get("ecology") or {}).get("famine") is None:
            return None
        home = ctx.get(person, "place")
        if not home or not ctx.get(home, "famine") or ctx.get(person, "spouse") or ctx.get(person, "offices") \
                or ctx.get(person, "journey"):  # (as Flee asks: one already on the road isn't fleeing)
            return None
        if ctx.get(person, "plots") or ctx.protected(person):  # (as Migration leaves them be)
            return None
        if (ctx.get(person, "drives") or {}).get("food", 1.0) > Food.STARVING:
            return None
        return Formation(home, ("drive", "food"))

    def urge(self, ctx, person):
        return 0.4

    def subgoals(self, ctx, amb):
        return [frozenset({"safe"})]

    def satisfied(self, ctx, amb):
        return ctx.get(ctx.get(amb, "owner"), "place") != ctx.get(amb, "target")

    def moot(self, ctx, amb):
        return not ctx.get(ctx.get(amb, "target"), "famine")

    def text(self, ctx, owner, target):
        return f"escape the famine in {ctx.get(target, 'name') or target}"


@LIBRARY.add
class Covet(Ambition):
    """Want a famous thing someone else holds (S9 §5, #126): one in one's own town, or one famous enough to be
    known everywhere. The plot is a theft (`Steal`). Only where crafts make objects, and only once a famous one
    exists (so it draws nothing before)."""

    name, cooldown_years = "Covet", 10
    reads = frozenset({"ids:object", "fame", "owner", "lost", "place", "status", "traits", "drives", "spouse",
                       "children", "father", "mother"})
    FAME, RENOWN = 0.5, 0.9  # (famous enough to covet; famous enough to be known beyond one's town)

    def _wanted(self, ctx, person):
        if not ctx.params.get("crafts"):
            return None
        from renasci.people.crafts import where

        here, best = ctx.get(person, "place"), None
        household = {ctx.get(person, k) for k in ("spouse", "father", "mother")} | set(ctx.get(person, "children") or [])
        for o in ctx.ids("object"):
            if ctx.status(o) != "active":
                continue
            owner, fame = ctx.get(o, "owner"), float(ctx.get(o, "fame") or 0.0)
            if owner in (None, person) or owner in household or ctx.status(owner) != "active" or fame < self.FAME \
                    or (where(ctx, o) != here and fame < self.RENOWN):
                continue  # (one's own household's things are one's own, near enough)
            if best is None or (fame, o) > best:
                best = (fame, o)
        return best[1] if best else None

    def eligible(self, ctx, person):
        o = self._wanted(ctx, person)
        if o is None:
            return None
        status = (ctx.get(person, "drives") or {}).get("status", 1.0)
        if trait(ctx, person, "temper") < 0.6 and status >= 0.5:
            return None
        return Formation(o, ("drive", "status"))

    def urge(self, ctx, person):
        return 0.03 + 0.1 * trait(ctx, person, "temper")

    def subgoals(self, ctx, amb):
        return [frozenset({f"holds:{ctx.get(amb, 'target')}"})]

    def keeps(self, ctx, amb):  # (while a plot runs; else while it's still this thing they want)
        if ctx.get(amb, "scheme") is not None:
            return True
        f = self.eligible(ctx, ctx.get(amb, "owner"))
        return f is not None and f.target == ctx.get(amb, "target")

    def satisfied(self, ctx, amb):
        return ctx.get(ctx.get(amb, "target"), "owner") == ctx.get(amb, "owner")

    def moot(self, ctx, amb):  # (destroyed, or lost to everyone)
        t = ctx.get(amb, "target")
        return ctx.status(t) != "active" or (ctx.get(amb, "scheme") is None and ctx.get(t, "lost") is not None)

    def text(self, ctx, owner, target):
        return f"have {ctx.get(target, 'name') or 'a famous ' + str(ctx.get(target, 'type'))}"


@LIBRARY.add
class Vengeance(Ambition):
    """Answer an attributed harm: the killer of one's kin, or whoever plotted against one."""

    name, cooldown_years = "Vengeance", 8
    kinds = ("killed", "exposed")
    reads = frozenset({"grievances", "status", "favour", "traits"})

    def _grievance(self, ctx, person):
        """The first grievance of this kind not yet taken up, against someone still here and not yet humbled."""
        for g in ctx.get(person, "grievances") or []:
            t = g["against"]
            if g.get("kind") in self.kinds and not g.get("answered") and t != person and ctx.exists(t) \
                    and ctx.status(t) == "active" and float(ctx.get(t, "favour") or 0.0) >= SHAMED:
                return g
        return None

    def eligible(self, ctx, person):
        g = self._grievance(ctx, person)
        return Formation(g["against"], ("event", g["event"])) if g else None

    def keeps(self, ctx, amb):  # its grievance is taken up: kept while the target is here to answer
        return ctx.status(ctx.get(amb, "target")) == "active"

    def formed(self, ctx, amb, formation):
        owner, (_, event) = ctx.get(amb, "owner"), formation.born_of
        ctx.set(owner, "grievances", [{**g, "answered": amb} if g["event"] == event and g["against"] == formation.target
                                      and not g.get("answered") else g for g in ctx.get(owner, "grievances") or []])

    def urge(self, ctx, person):
        return 0.15 + 0.35 * trait(ctx, person, "temper")

    def subgoals(self, ctx, amb):
        t = ctx.get(amb, "target")
        return [frozenset({f"dead:{t}"}), frozenset({f"shamed:{t}"})]

    def satisfied(self, ctx, amb):
        t = ctx.get(amb, "target")
        return ctx.status(t) == "dead" or float(ctx.get(t, "favour") or 0.0) < SHAMED

    def moot(self, ctx, amb):
        return False  # a target's death satisfies; nothing else ends a vendetta

    def text(self, ctx, owner, target):
        return f"avenge themselves on {ctx.get(target, 'name') or target}"


@LIBRARY.add
class Protect(Vengeance):
    """Strike first at whoever plotted against one's own (a kin's exposed plot)."""

    name, cooldown_years = "Protect", 8
    kinds = ("threatened",)

    def urge(self, ctx, person):
        return 0.1 + 0.2 * trait(ctx, person, "temper")

    def text(self, ctx, owner, target):
        return f"protect their own from {ctx.get(target, 'name') or target}"


@LIBRARY.add
class Ruin(Ambition):
    """Bring a rival or an enemy low: see them shamed (S6 §8, #98). Only in a world with beliefs, where
    shame can be had by testimony, slander or a frame as well as at court."""

    name, cooldown_years = "Ruin", 8
    reads = frozenset({"ties", "a", "b", "kind", "ended", "status", "favour", "born"})

    def eligible(self, ctx, person):
        if not ctx.params.get("beliefs"):
            return None
        for t in ctx.get(person, "ties") or []:
            if ctx.get(t, "ended") or ctx.get(t, "kind") not in ("rival", "enemy"):
                continue
            other = ctx.get(t, "b") if ctx.get(t, "a") == person else ctx.get(t, "a")
            if ctx.status(other) == "active" and float(ctx.get(other, "favour") or 0.0) >= SHAMED:
                return Formation(other, ("drive", "rivalry"))
        return None

    def urge(self, ctx, person):  # (rare: most rivals live with it)
        return 0.01 + 0.04 * trait(ctx, person, "temper")

    def subgoals(self, ctx, amb):
        return [frozenset({f"shamed:{ctx.get(amb, 'target')}"})]

    def satisfied(self, ctx, amb):
        return float(ctx.get(ctx.get(amb, "target"), "favour") or 0.0) < SHAMED

    def text(self, ctx, owner, target):
        return f"see {ctx.get(target, 'name') or target} brought low"


LIBRARY.freeze()


def classes(ctx) -> dict[str, Ambition]:
    """The ambition classes this world uses (the ruleset param `ambitions`, or every known class)."""
    names = ctx.params.get("ambitions")
    if not names:
        return dict(sorted(LIBRARY.items()))
    unknown = sorted(set(names) - set(LIBRARY))
    if unknown:
        raise ValueError(f"unknown ambition classes {unknown}; known: {sorted(LIBRARY)}")
    return {n: LIBRARY[n] for n in sorted(names)}


def resolve(ctx, amb: str, status: str, causes=()) -> None:
    """End an ambition: the event, the record, the owner's list and the cooldown."""
    owner = ctx.get(amb, "owner")
    event = ctx.emit("people.ambition_resolved", {"owner": (owner,), "ambition": (amb,)},
                     purpose=f"resolve:{status}", actor=amb, payload={"status": status},
                     causes=(Cause("ambition", amb), *causes))
    ctx.set(amb, "state", status)
    ctx.set(amb, "resolved", [ctx.today.to_json(), event.id])
    ctx.set(amb, "scheme", None)
    ctx.set(owner, "ambitions", [a for a in ctx.get(owner, "ambitions") or [] if a != amb])
    cls = ctx.get(amb, "class")
    known = classes(ctx)
    cooldown = known[cls].cooldown_years if cls in known else 5
    ctx.set(owner, "cooldowns", {**(ctx.get(owner, "cooldowns") or {}), cls: ctx.today.year + cooldown})


def on_death(ctx, person: str, death_event: str) -> None:
    """Every active ambition of the dead ends, caused by the death: unfulfilled, unless the world had
    already met it before the yearly pass noticed (married, then died, the same day)."""
    known = classes(ctx)
    for amb in list(ctx.get(person, "ambitions") or []):
        cls = known.get(ctx.get(amb, "class"))
        won = cls is not None and cls.satisfied(ctx, amb)
        resolve(ctx, amb, "fulfilled" if won else "died_unfulfilled", causes=(Cause("event", death_event),))


READS = frozenset({"ambitions", "cooldowns", "owner", "class", "target", "status", "state", "scheme"})
WRITES = frozenset({"ambitions", "cooldowns", "state", "resolved", "scheme", "new:ambition", "grievances", "claims"})


class Ambitions(System):
    name, cadence = "people.ambitions", "yearly"
    priority = 6  # after drives (5)
    reads = READS | frozenset({"ids:settlement", "residents", "born", "formed", "traits"}).union(
        *(a.reads for a in LIBRARY.values()))
    writes = WRITES
    event_types = EVENT_TYPES

    def run(self, ctx):
        library = classes(ctx)
        for s in ctx.ids("settlement"):
            with ctx.scope(s):
                for p in ctx.get(s, "residents"):
                    if age_years(ctx.calendar, ctx.get(p, "born"), ctx.today) < ADULT:
                        continue
                    self._resolve(ctx, p, library)
                    self._form(ctx, p, library)

    @staticmethod
    def _resolve(ctx, person, library):
        for amb in list(ctx.get(person, "ambitions") or []):
            cls = library.get(ctx.get(amb, "class"))
            if cls is None:
                resolve(ctx, amb, "abandoned")  # its class is no longer part of this world
            elif cls.satisfied(ctx, amb):
                resolve(ctx, amb, "fulfilled")
            elif cls.moot(ctx, amb) or not cls.keeps(ctx, amb):
                resolve(ctx, amb, "abandoned")

    @staticmethod
    def _form(ctx, person, library):
        held = {ctx.get(a, "class") for a in ctx.get(person, "ambitions") or []}
        cooldowns = ctx.get(person, "cooldowns") or {}
        for name, cls in library.items():
            if name in held or cooldowns.get(name, 0) > ctx.today.year:
                continue
            formation = cls.eligible(ctx, person)
            if formation is None or not ctx.chance(cls.urge(ctx, person), f"form:{name}", owner=person):
                continue
            fields = {"owner": person, "class": name, "target": formation.target, "formed": ctx.today.to_json(),
                      "state": "active", "resolved": None, "scheme": None, "born_of": list(formation.born_of)}
            event = ctx.emit("people.ambition_formed",
                             {"owner": (person,), "target": (formation.target,) if formation.target else ()},
                             purpose=f"form:{name}", actor=person,
                             payload={"class": name, "text": cls.text(ctx, person, formation.target)},
                             causes=(Cause(*formation.born_of),), creates={"ambition": [("ambition", fields)]})
            amb = event.roles["ambition"][0]
            ctx.set(person, "ambitions", sorted((ctx.get(person, "ambitions") or []) + [amb]))
            cls.formed(ctx, amb, formation)
