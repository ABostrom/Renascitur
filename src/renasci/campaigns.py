"""Campaigns, battles and sieges (S8 spec §8, Part B of #122): a war fought a season at a time.

Only in a world whose params say `campaigns: true` (the system is added then); `polity.war` then declares
and makes peace as before, but leaves the fighting of a fine year to this system. A coarse step keeps the
yearly draw (`War.step`): a campaign is the fine-grained story of a war.

Each season, for each live war (`polity.campaigns`, seasonal, `ctx.scope(war)`):

1. **Armies:** each side's polities have an army (`armies` on the war: `{polity: {size, raised, at,
   target, siege}}`). One not yet raised is raised at its seat: `LEVY` of its strength (`war.strength`),
   at least one company. Levies are numbers, not people.
2. **Marches:** an army with at least the strength of the enemy's strongest takes the offensive, making for
   the enemy's nearest settlement (by the army's roads, S4's `army` mode in a world with routing) and
   keeping that target while the enemy holds it; one with `RELIEVE` of it marches to relieve its own town
   that army threatens; one weaker holds at its seat. An army goes as far along the way as a season's
   `SEASON_DAYS` take it. The season is one `polity.campaign` event (every army's place and size), before
   anything is written.
3. **Battles:** armies of the two sides in one place fight (`polity.battle`), unless one is under
   `SHUT_IN` of the other and in a town its side holds: then it stays behind the walls. A keyed draw by
   numbers, the side holding the place fighting from its walls (its seat `DEFENCE_SEAT`, another town
   `DEFENCE_TOWN`); the loser loses `LOSS_LOSE` of its men and falls back to its seat, the winner
   `LOSS_WIN`. Exhaustion: the loser `EX_LOSE`, the winner `EX_WIN`.
4. **Sieges:** an army before an enemy town with no enemy army in the field there besieges it
   (`polity.siege`): each season a keyed draw, likelier the longer it lasts and the bigger the army against
   the garrison (the town's people, and any army shut in). A fall hands the town over
   (`geo.apply_change`) and loses the army inside; a polity left with no settlement falls (`War.fall`).
5. **Peace:** every side tires `EX_SEASON` a season; a side exhausted, or an army routed (below `ROUTED` of
   what it raised), brings peace (`War.peace`).

(Razing, a commander and a ruler in the field, supply and levy losses among the masses are next.)
"""

from __future__ import annotations

from renasci import geo, lines
from renasci.core.events import Cause, EventType
from renasci.core.systems import System
from renasci.war import EVENT_TYPES as WAR_EVENTS, EXHAUSTED, War, strength

SEASON_DAYS = 90
LEVY = 0.2
DEFENCE_SEAT, DEFENCE_TOWN = 1.6, 1.25
LOSS_WIN, LOSS_LOSE = 0.1, 0.25
EX_WIN, EX_LOSE, EX_SEASON = 0.03, 0.15, 0.02
ROUTED = 0.15
SHUT_IN = 0.3  # (an army this much smaller than its foe, in a town its side holds, stays behind the walls)
RELIEVE = 0.6  # (a defender marches to relieve a town only with at least this much of the attacker's strength)
SIEGE = 0.2

CAMPAIGN = EventType("polity.campaign", 1, roles={"party": (2, 64)}, payload={"war": "id", "armies": "json"})
BATTLE = EventType("polity.battle", 1, roles={"winner": (1, 1), "loser": (1, 1)},
                   payload={"war": "id", "place": "id", "losses": "json"})
SIEGE_T = EventType("polity.siege", 1, roles={"besieger": (1, 1), "held_by": (1, 1)},
                    payload={"war": "id", "place": "id", "seasons": "int", "outcome": "str"})
EVENT_TYPES = (CAMPAIGN, BATTLE, SIEGE_T) + WAR_EVENTS + lines.EVENT_TYPES


def enabled(ctx) -> bool:
    return bool(ctx.params.get("campaigns"))


def way(ctx, a: str, b: str) -> tuple[int, list[str]] | None:
    """An army's way from a to b: by the army's days in a world with routing, else the routes' own."""
    table = ctx.params.get("routing")
    travel = None
    if table and "army" in table.get("modes", {}):
        travel = geo.Travel("army", ctx.calendar.season_name(ctx.today))
    return geo.shortest(geo._routes(ctx, travel is not None), a, b, travel, table if travel else None)


def _advance(ctx, at: str, target: str | None) -> str:
    """As far toward `target` as a season's march goes (whole legs only)."""
    if not target or target == at:
        return at
    found = way(ctx, at, target)
    if found is None:
        return at
    days, path = found
    if days <= SEASON_DAYS:
        return target
    reached = at
    for node in path[1:]:
        leg = way(ctx, at, node)
        if leg is None or leg[0] > SEASON_DAYS:
            break
        reached = node
    return reached


def _nearest(ctx, at: str, towns: list[str]) -> str | None:
    best = None
    for t in sorted(towns):
        found = way(ctx, at, t)
        if found is not None and (best is None or found[0] < best[0]):
            best = (found[0], t)
    return best[1] if best else None


class Campaigns(System):
    """A war's seasons (see the module doc)."""

    name, cadence, priority = "polity.campaigns", "seasonal", 3  # (after polity.war's yearly declarations)
    reads = War.reads | geo.READS | frozenset({"armies"})
    writes = War.writes | frozenset({"armies"})
    event_types = EVENT_TYPES

    def handle(self, ctx, activation):
        War().handle(ctx, activation)

    def coarse_fallback(self, ctx, years: int) -> None:
        """A coarse step: the war is fought by `polity.war`'s yearly draws; armies in the field go home (a
        fine season after it raises them afresh)."""
        if not enabled(ctx):
            return
        for war in ctx.ids("war"):
            with ctx.scope(war):
                if ctx.get(war, "ended") is None and ctx.get(war, "armies"):
                    party = tuple(sorted(set(ctx.get(war, "attackers")) | set(ctx.get(war, "defenders"))))
                    ctx.emit("polity.campaign", {"party": party}, purpose="disband", actor=war,
                             payload={"war": war, "armies": {}})
                    ctx.set(war, "armies", {})

    def run(self, ctx):
        if not enabled(ctx):
            return
        for war in ctx.ids("war"):
            with ctx.scope(war):
                if ctx.get(war, "ended") is None:
                    self.season(ctx, war)

    def season(self, ctx, war: str) -> None:
        sides = {k: [p for p in ctx.get(war, k) if ctx.get(p, "ended") is None] for k in ("attackers", "defenders")}
        if not sides["attackers"] or not sides["defenders"]:  # (a side has fallen elsewhere)
            W = War()
            W._end(ctx, war, (sides["attackers"] or sides["defenders"] or [None])[0])
            W._stand_down(ctx, [war], None)
            return
        towns = {k: [s for s in ctx.ids("settlement") if ctx.get(s, "control") in v] for k, v in sides.items()}
        armies = {p: dict(a) for p, a in (ctx.get(war, "armies") or {}).items() if p in sides["attackers"] + sides["defenders"]}
        for p in sides["attackers"] + sides["defenders"]:
            if p not in armies:
                size = max(1, round(LEVY * strength(ctx, p)))
                armies[p] = {"size": size, "raised": size, "at": ctx.get(p, "seat"), "target": None, "siege": 0}
        enemy = {"attackers": "defenders", "defenders": "attackers"}

        def home(p, k):  # (its seat while its side holds it, else the nearest town it still holds)
            seat = ctx.get(p, "seat")
            return seat if seat in towns[k] else (_nearest(ctx, armies[p]["at"], towns[k]) or armies[p]["at"])

        threat = {}  # (each side's strongest army: what the other side must reckon with)
        for k in sides:
            top = max(sides[k], key=lambda p: (armies[p]["size"], p))
            threat[k] = top
        for k in ("attackers", "defenders"):  # (attackers first: defenders answer their targets)
            foe = threat[enemy[k]]
            for p in sides[k]:
                a = armies[p]
                if a["size"] >= armies[foe]["size"]:  # (the edge: on the enemy's nearest town)
                    if a["target"] not in towns[enemy[k]]:
                        a["target"], a["siege"] = _nearest(ctx, a["at"], towns[enemy[k]]), 0
                elif a["size"] >= RELIEVE * armies[foe]["size"] and armies[foe]["target"] in towns[k]:
                    a["target"] = armies[foe]["target"]  # (enough to relieve the threatened town)
                else:
                    a["target"] = home(p, k)  # (hold at home)
        for p in sorted(armies):
            before = armies[p]["at"]
            armies[p]["at"] = _advance(ctx, before, armies[p]["target"])
            if armies[p]["at"] != before:
                armies[p]["siege"] = 0
        party = tuple(sorted(armies))
        ev = ctx.emit("polity.campaign", {"party": party}, purpose="campaign", actor=war,
                      payload={"war": war, "armies": armies})
        ex = dict(ctx.get(war, "exhaustion") or {})
        last = ev.id
        fought, shut = set(), set()
        for p in sorted(sides["attackers"]):  # battles where armies meet
            for q in sorted(sides["defenders"]):
                if armies[p]["at"] != armies[q]["at"] or p in fought or q in fought:
                    continue
                small, big = sorted((p, q), key=lambda x: (armies[x]["size"], x))
                if armies[small]["size"] < SHUT_IN * armies[big]["size"]                         and ctx.get(armies[small]["at"], "control") in sides["attackers" if small in sides["attackers"] else "defenders"]:
                    shut.add(small)  # (too few to take the field: behind the walls, part of the garrison)
                    fought.add(small)
                    continue
                last = self.battle(ctx, war, p, q, armies, ex, last)
                fought |= {p, q}
                for x in (p, q):  # (a beaten army falls back to a town its side still holds)
                    if armies[x]["target"] is None:
                        armies[x]["at"] = home(x, "attackers" if x in sides["attackers"] else "defenders")
        for k in ("attackers", "defenders"):  # sieges of enemy towns left undefended
            for p in sorted(sides[k]):
                here = armies[p]["at"]
                holder = ctx.get(here, "control")
                inside = [q for q in sides[enemy[k]] if armies[q]["at"] == here]
                if p in fought or holder not in sides[enemy[k]] or ctx.get(war, "ended") is not None                         or any(q not in shut for q in inside):
                    continue
                last = self.siege(ctx, war, p, holder, armies[p], last, [armies[q] for q in inside]) or last
        if ctx.get(war, "ended") is not None:
            ctx.set(war, "armies", {})
            return
        for k in sides:  # (an ally that fell this season is out of it)
            sides[k] = [p for p in sides[k] if ctx.get(p, "ended") is None]
        armies = {p: a for p, a in armies.items() if p in sides["attackers"] + sides["defenders"]}
        for p in armies:
            ex[p] = round(ex.get(p, 0.0) + EX_SEASON, 6)
        ctx.set(war, "armies", armies)
        ctx.set(war, "exhaustion", ex)
        routed = any(a["size"] < ROUTED * a["raised"] for a in armies.values())
        if routed or max(ex.get(p, 0.0) for k in sides for p in sides[k]) >= EXHAUSTED:
            War().peace(ctx, war, sides, ex, last)
            ctx.set(war, "armies", {})

    def battle(self, ctx, war, att, dfn, armies, ex, cause) -> str:
        a, d = armies[att], armies[dfn]
        place = a["at"]
        home = ctx.get(place, "control")  # (whoever holds the field fights from its walls)
        defence = DEFENCE_SEAT if home and place == ctx.get(home, "seat") else DEFENCE_TOWN
        if home not in (att, dfn):
            defence = 1.0
        a_strength, d_strength = a["size"] * (defence if home == att else 1.0), d["size"] * (defence if home == dfn else 1.0)
        p = a_strength / (a_strength + d_strength) if a_strength + d_strength else 0.5
        won = ctx.chance(p, f"battle:{att}:{dfn}", owner=war, stakes=2.0)
        winner, loser = (att, dfn) if won else (dfn, att)
        losses = {winner: round(armies[winner]["size"] * LOSS_WIN), loser: max(1, round(armies[loser]["size"] * LOSS_LOSE))}
        ev = ctx.emit("polity.battle", {"winner": (winner,), "loser": (loser,)}, purpose=f"battle:{place}", actor=war,
                      place=place, payload={"war": war, "place": place, "losses": dict(sorted(losses.items()))},
                      causes=(Cause("event", cause),))
        for side, n in losses.items():
            armies[side]["size"] = max(0, armies[side]["size"] - n)
        armies[loser]["target"], armies[loser]["siege"] = None, 0  # (season() sends it home)
        ex[loser] = round(ex.get(loser, 0.0) + EX_LOSE, 6)
        ex[winner] = round(ex.get(winner, 0.0) + EX_WIN, 6)
        return ev.id

    def siege(self, ctx, war, att, holder, army, cause, inside=()) -> str:
        place = army["at"]
        army["siege"] = int(army.get("siege") or 0) + 1
        garrison = 5 + len(ctx.get(place, "residents") or []) + sum(a["size"] for a in inside)
        p = min(0.9, SIEGE * army["siege"] * army["size"] / (army["size"] + garrison))
        fell = ctx.chance(p, f"siege:{place}", owner=war, stakes=1.5)
        ev = ctx.emit("polity.siege", {"besieger": (att,), "held_by": (holder,)}, purpose=f"siege:{place}", actor=war,
                      place=place, payload={"war": war, "place": place, "seasons": army["siege"],
                                            "outcome": "fell" if fell else "held"}, causes=(Cause("event", cause),))
        if fell:
            geo.apply_change(ctx, {"place": place, "control": att, "why": f"taken by siege in {war}"})
            army["target"], army["siege"] = None, 0
            for a in inside:  # (an army shut in a town that falls is lost with it)
                a["size"] = 0
            if not any(ctx.get(s, "control") == holder for s in ctx.ids("settlement")):
                War().fall(ctx, war, holder, att, ev.id)
        return ev.id
