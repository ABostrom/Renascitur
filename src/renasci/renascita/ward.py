"""The ward failure (S6 spec §10, #90): a scripted injection, the M2 golden scenario.

A ripple `{"kind": "inject", "target": <settlement>, "params": {"script": "ward_failure", "spare": null |
"leader"}}` on the Fourth Age plays it out in the target settlement (a Vialux town):

1. **The cast**, drawn from the world by keyed draws (so a baseline and its what-if, which see the same
   world before the ripple, draw the same people): a caravan leader of one Great House living there, the
   head of a rival house, the guild master (a notable of neither house), and a ward-keeper and two
   guards (commoners of the town).
2. **What happened** (truth): the rival loses an ore contract to the leader's house (`ward.contract_lost`);
   the rival's agents crack the ward-stones (`ward.sabotage`, **secret**); the wards fail on the road at
   night (`ward.failure`, public), and night terrors kill a guard and the leader, unless `spare` saves
   the leader.
3. **What people make of it:** each survivor saw part of it: sabotage (the rival's doing) or faulty
   stones (the guild's). The guild master knows better and **lies**: the ward-keeper misaligned the
   stones. He tells the town, with the guild's authority, and it becomes the town's official line (its
   share among the masses), which goes out on the Vialux as news.
4. **The witness:** a spared leader saw the sabotage. A season later they **bear witness** in public:
   evidence that corrects the lie for those who hear it, and the truth spreads from there.

The cast and the story are a draft of the vault's ward-failure, chosen from the world each run, not
canon. It needs `beliefs: true` in the world's params (without it, it injects nothing).
"""

from __future__ import annotations

from renasci.core.calendar import Span
from renasci.core.events import Cause, EventType
from renasci.core.ripples import Disguise
from renasci.people import beliefs, houses, life
from renasci.people.races import age_years

CONTRACT_LOST = EventType("ward.contract_lost", 1, roles={"winner": (1, 1), "loser": (1, 1)}, payload={})
SABOTAGE = EventType("ward.sabotage", 1, roles={"ordered_by": (1, 1)}, payload={}, visibility="secret")
FAILURE = EventType("ward.failure", 1, roles={"leader": (1, 1), "keeper": (1, 1), "guard": (0, 4)}, payload={})
TESTIMONY = EventType("ward.testimony", 1, roles={"witness": (1, 1)}, payload={})
EVENT_TYPES = (CONTRACT_LOST, SABOTAGE, FAILURE, TESTIMONY)

LIE_HEARERS, LIE_TRUST, LIE_SHARE = 6, 0.8, 0.5  # the guild's word, and how much of the town takes it up
WITNESS_HEARERS, WITNESS_DELAY_DAYS = 10, 90
SAW_SABOTAGE = 0.45  # a survivor's chance to have seen the sabotage rather than the faulty stones


def _adult(ctx, p) -> bool:
    return age_years(ctx.calendar, ctx.get(p, "born"), ctx.today) >= 18


class WardFailure(Disguise):
    """inject, scripted: the ward failure (see the module doc)."""

    name, handles = "renascita.ward_failure", "inject"
    reads = (life.DIE_READS | beliefs.PERCEIVE_READS | beliefs.ARRIVAL_READS | frozenset(
        {"ids:office", "ids:house", "holder", "house", "headship", "offices", "residents", "born", "place", "status",
         "spouse", "shares", "journey"}))
    writes = life.DIE_WRITES | beliefs.PERCEIVE_WRITES | frozenset({"shares"})
    event_types = tuple({t.name: t for t in EVENT_TYPES + life.DIE_EVENTS + beliefs.EVENT_TYPES}.values())

    def apply(self, ctx, ripple) -> bool:
        if ripple.params.get("script") != "ward_failure" or not beliefs.enabled(ctx):
            return False
        town = ripple.target
        cast = self._cast(ctx, town, ripple.id)
        if cast is None:
            return False
        leader, rival, master, keeper, guards = cast
        contract = ctx.emit("ward.contract_lost", {"winner": (leader,), "loser": (rival,)}, purpose="contract",
                            actor=town, place=town)
        sabotage = ctx.emit("ward.sabotage", {"ordered_by": (rival,)}, purpose="sabotage", actor=town, place=town,
                            causes=(Cause("event", contract.id),))
        failure = ctx.emit("ward.failure", {"leader": (leader,), "keeper": (keeper,), "guard": tuple(guards)},
                           purpose="failure", actor=town, place=town, causes=(Cause("event", sabotage.id),))
        spared = ripple.params.get("spare") == "leader"
        life.die(ctx, guards[-1], town, "night terrors", causes=(Cause("event", failure.id),))
        if not spared:
            life.die(ctx, leader, town, "night terrors", causes=(Cause("event", failure.id),))
        truth = beliefs.claim("caused", event=failure.id, by=rival)  # (retold, it becomes the rival's house)
        stones = beliefs.claim("fault", event=failure.id, party="the guild's stones")
        lie = beliefs.claim("fault", event=failure.id, party=keeper)
        survivors = [p for p in (leader, keeper, *guards) if ctx.status(p) == "active"]
        for p in survivors:  # each saw part of it
            if p == leader:
                beliefs.hold(ctx, p, truth, beliefs.PARTICIPANT_CONF, failure.id)  # (they saw who it was)
            elif ctx.chance(SAW_SABOTAGE, "saw", owner=f"{ripple.id}|{p}"):
                beliefs.hold(ctx, p, truth, 0.6, failure.id)
            else:
                beliefs.hold(ctx, p, stones, 0.5, failure.id)
        # The guild master knows better and lies: the town hears it with the guild's authority.
        beliefs.hold(ctx, master, truth, 0.7, failure.id, secret=True)
        townsfolk = sorted(r for r in ctx.get(town, "residents")
                           if ctx.status(r) == "active" and r not in (master, *survivors) and not ctx.get(r, "journey"))
        told = []
        for i in range(min(LIE_HEARERS, len(townsfolk))):
            h = ctx.choose(f"lie:{i}", [r for r in townsfolk if r not in told], owner=ripple.id)
            told.append(h)
            beliefs.tell(ctx, master, h, lie, LIE_TRUST, conf=0.9, intent="lie", cause=failure.id, place=town)
        shares = dict(ctx.get(town, "shares") or {})
        shares[beliefs.key(lie)] = {"claim": lie, "share": LIE_SHARE}  # (the official line)
        ctx.emit("belief.shares", {"settlement": (town,)}, purpose="official_line", actor=town,
                 payload={"claims": len(shares)}, causes=(Cause("event", failure.id),))
        ctx.set(town, "shares", beliefs._normalised(shares))
        if spared:
            ctx.schedule(Span(days=WITNESS_DELAY_DAYS), "testimony", entity=leader,
                         payload={"witness": leader, "town": town, "claim": truth, "failure": failure.id,
                                  "ripple": ripple.id})
        return True

    def handle(self, ctx, activation):
        if activation.purpose != "testimony":
            houses.handle_succession(ctx, activation)  # (the deaths it caused may vacate a seat)
            return
        p = activation.payload
        witness = p["witness"]
        if ctx.status(witness) != "active":
            return  # (the witness who never testified)
        town = ctx.get(witness, "place")  # (wherever they live now)
        with ctx.scope(town):
            said = ctx.emit("ward.testimony", {"witness": (witness,)}, purpose="testimony", actor=witness, place=town,
                            causes=(Cause("event", p["failure"]),))
            here = sorted(r for r in ctx.get(town, "residents")
                          if r != witness and ctx.status(r) == "active" and not ctx.get(r, "journey"))
            heard = []
            for i in range(min(WITNESS_HEARERS, len(here))):
                h = ctx.choose(f"witness:{i}", [r for r in here if r not in heard], owner=p["ripple"])
                heard.append(h)
                beliefs.correct(ctx, h, p["claim"], said.id)

    def _cast(self, ctx, town: str, owner: str):
        residents = sorted(r for r in ctx.get(town, "residents") if ctx.status(r) == "active" and _adult(ctx, r))
        housed = [r for r in residents if ctx.get(r, "house") and not ctx.get(r, "offices") and not ctx.get(r, "journey")]
        if not housed:
            return None
        leader = ctx.choose("leader", housed, owner=owner)
        house = ctx.get(leader, "house")
        heads = sorted({ctx.get(ctx.get(h, "headship"), "holder") for h in ctx.ids("house") if ctx.get(h, "headship")}
                       - {None})  # (the heads of the houses: a rival house's head ordered it)
        rivals = [h for h in heads if ctx.status(h) == "active" and ctx.get(h, "house") and ctx.get(h, "house") != house]
        if not rivals:
            return None
        rival = ctx.choose("rival", rivals, owner=owner)
        others = [r for r in residents if not ctx.get(r, "house") and r != leader and not ctx.get(r, "journey")]
        if len(others) < 4:
            return None
        master = ctx.choose("master", others, owner=owner)
        crew = [r for r in others if r != master]
        keeper = ctx.choose("keeper", crew, owner=owner)
        crew.remove(keeper)
        guards = []
        for i in range(2):
            g = ctx.choose(f"guard:{i}", crew, owner=owner)
            crew.remove(g)
            guards.append(g)
        return leader, rival, master, keeper, guards
