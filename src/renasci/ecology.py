"""Climate and harvests (S10 spec §2, #127): each region's weather, a season at a time, and the food it lets
the farmers reap.

Only in a world with geography and a crafts catalogue whose materials include the harvest's (the `ecology`
param, `DEFAULT` for a start): `{"climate": {region | "*": {"spread"}}, "persist", "harvest": {"season",
"material"}}`. `ecology.climate` (seasonal; one scope per region, then one per settlement at harvest):

- **Weather:** each region's `climate` is two anomalies, `warm` and `wet`, in spreads from its usual: each
  season a keyed normal draw per region, a `persist` share of last season's carried on (a drought lasts:
  `anomaly`). Every season's weather is a `climate.season` event (its `kind` names a notable one: drought,
  flood, hard winter, heat), the cause of what the weather does.
- **Harvest:** at the harvest season, each settlement's workers of the harvest material (the masses in its
  `by` jobs, and notables holding them, not away) reap a year's yield of it, times the weather's `factor`
  (more for a kind year, less for a cold, a drought, a flood), into stock (S9's ledger: `produced`). Below
  `FAILED` it is `harvest.failed`, else `harvest.reaped`; either is caused by the region's weather. With
  ecology on, S9's yearly yield of that material stops (`people.crafts` skips it).
- **Blight** (the structural ripple's harvest form, through `geo.upheaval`): a region's `blight` (`factor`,
  how many `harvests` it spoils: those up to `until`, or just the next, and the event that brought it) caps
  the factor of its next harvests, and is their cause; each harvest spends one (a coarse step, its years').

Harvests carry their fractions year to year (S9's `yield_carry`), so fine and coarse agree.

A coarse step draws one season's weather and reaps N years at once when it covers a harvest: one year at that
weather, the rest at a usual year's `MEAN` (spec §7).

**Famine** (S10 §3, #129; with `ecology.famine`: `{"eat", "stores"}`, `FAMINE` for a start). Towns begin with
`stores` years of the harvest material (the ledger's `initial`). `ecology.famine` (seasonal, after the
weather; one scope per settlement): its people (masses and notables) eat `eat` a head a year, a season's share,
from stock (`used`; `goods.eaten`); stores past `keep` years' eating spoil (`destroyed`). Short of it, the `short` share left hungry kills the masses at
`hunger_rates` (the young and the old first: `population.kill`), and raises notables' hazards (`people.life`
reads the town's `hunger`: last season's, as `people.life` runs first; a fine season's only, so a coarse
step's dead are its masses'). A town is in famine from a season short by `BEGIN` (`famine.began`, caused by its
last harvest) until one short by no more than `END` (`famine.ended`). Trade (S9) carries food downhill to the
hungry by itself.

`ecology.burial` (seasonal, before the harvest; `{"burial": false}` turns it off): every death lies in the town's
`corpses` stock (`population.fell`). The town's able hands, fewer when hungry, bury what they can, up to `SPARE` of
them; the share they take is its `labour`, which comes off that season's harvest, as hunger does. What's left rots
by the season, slowly in winter. Time it didn't see (a coarse step) has done that work: only a season's share of the
pile is still lying, so a focus window doesn't open on years of ordinary dead. A coarse step takes no labour.

`ecology.disease` (seasonal; `{"disease": false}` turns it off; a list replaces the draft catalogue, `DISEASES`) reads
conditions and knows nothing of what made them. A town's chance of an outbreak rises with the dead lying per head,
and an outbreak cites them. In a town's `disease`, `{id: {sick, immune, event}}`: each season the susceptible catch it
(`catching`, more readily when hungry), the sick recover or die (`population.kill`), and a notable may die of it. A
town's sick share is its `ill`: the sick don't work or bury, so plague starves itself of hands. An outbreak ends when
nobody is sick. A town remembers: its `immunity`, `{id: [immune, tick]}`, fades by `wane` a season and is reckoned
when the next outbreak comes. A coarse step has no seasons, so a town it strikes has one wave and it's over.

A sick town sends it on: down each open route, and with each traveller on the road, a draw at its sick share (`ROADS`)
adds to the destination's `carried:<id>` stock. Each one brought has a chance of taking hold (`TAKES`), once, at the
destination's next step, and adds nothing to a town already sick: an
outbreak cites what carried it, so a plague's path can be walked town by town. Travel knows nothing of any of this.
"""

from __future__ import annotations

import math

from renasci.core import stocks
from renasci.core.calendar import Date
from renasci.core.events import Cause, EventType

PERSIST = 0.5  # (the share of last season's anomaly that carries)
FAILED = 0.6  # (a harvest below this share of a usual year has failed)
MEAN = 0.92  # (a harvest's mean factor at a spread of 1: a coarse step's years past its first)
NOTABLE = 1.5  # (an anomaly this many spreads out gets a name)
FAMINE: dict = {"eat": 0.8, "stores": 1.0, "keep": 1.5}  # (a head eats this much a year; towns start with a
# year's stores; what is kept past `keep` years' eating spoils)
HUNGER = 0.08  # (the masses' extra deaths a season, in a town short of all its food, in the hardiest bands)
FRAIL = 2.0  # (the young, under 5, and the old, 60 and over, die of it this many times as readily)
BURIAL: dict = {"bury": 4.0, "rot": 0.3, "winter": 0.05}  # (bodies a pair of hands buries a season; the share of
# what's left that rots away a season, and in a season that keeps them)
DISEASES: list = [{"id": "flux", "name": "the flux", "beta": 1.4, "lethality": 0.15, "duration": 2.0, "wane": 0.02,
                   "tires": 0.8, "base": 0.0005, "filth": 0.5}]  # (a draft: spread a season, who dies of it, seasons
# sick, the share of the immune who lose it a season, how its spread weakens each season as people learn to shun the
# sick, a town's odds of an outbreak, and how much the dead lying per head add)
MOST_LIKELY = 0.5  # (a town's odds of breeding an outbreak in a season never pass this; arrivals add their own)
SEED = 0.005  # (the share of a town first sick)
FEVERED = 1.0  # (a town short of all its food catches it this much more readily)
WAVE = 0.4  # (the share a coarse step's outbreak strikes)
ROADS = 2.0  # (the odds of it going down a road, or with a traveller, per share of the town sick)
TAKES = 0.3  # (the odds that one who brings it to a town starts an outbreak there)
ABLE = 0.6  # (the share of a town's people fit to work)
SPARE = 0.5  # (at most this share of the able are taken from their work to bury the dead)
WEAK = 0.5  # (how much of its strength a town short of all its food loses)
BEGIN, END = 0.25, 0.05  # (a famine begins with a season this short, and ends with one no shorter than this)
DEFAULT: dict = {"climate": {"*": {"spread": 1.0}}, "persist": PERSIST,
                 "harvest": {"season": "Autumn", "material": "food"}}

SEASON = EventType("climate.season", 1, roles={"region": (1, 1)},
                   payload={"warm": "float", "wet": "float", "kind": "str"})
REAPED = EventType("harvest.reaped", 1, roles={"settlement": (1, 1)}, payload={"produced": "int", "factor": "float"})
FAILED_TYPE = EventType("harvest.failed", 1, roles={"settlement": (1, 1)},
                        payload={"produced": "int", "factor": "float"})
EVENT_TYPES = (SEASON, REAPED, FAILED_TYPE)
READS = frozenset({"ids:region", "ids:settlement", "region", "climate", "blight", "residents", "job", "journey",
                   "yield_carry", "job:*", "stock:*", "goods:*", "labour", "hunger", "ill", "pop:*"})
WRITES = frozenset({"climate", "blight", "yield_carry", "harvest", "stock:*", "goods:*"})


def check(eco: dict, crafts: dict | None) -> None:
    """Refuse an ecology catalogue the systems couldn't run."""
    if not isinstance(eco, dict):
        raise ValueError("ecology is a catalogue: {climate, persist, harvest}")
    climate = eco.get("climate", {})
    if not isinstance(climate, dict) or not all(isinstance(v, dict) for v in climate.values()):
        raise ValueError("ecology.climate maps regions (or \"*\") to {spread}")
    for where, c in climate.items():
        s = c.get("spread", 1.0)
        if isinstance(s, bool) or not isinstance(s, (int, float)) or s < 0:
            raise ValueError(f"ecology.climate[{where!r}].spread must be a non-negative number, got {s!r}")
    p = eco.get("persist", PERSIST)
    if isinstance(p, bool) or not isinstance(p, (int, float)) or not 0 <= p < 1:
        raise ValueError(f"ecology.persist must be in [0, 1), got {p!r}")
    h = eco.get("harvest") or {}
    if not isinstance(h, dict) or h.get("season") not in ("Spring", "Summer", "Autumn", "Winter"):
        raise ValueError("ecology.harvest needs a season: Spring, Summer, Autumn or Winter")
    if h.get("material") not in ((crafts or {}).get("materials") or {}):
        raise ValueError(f"ecology.harvest's material {h.get('material')!r} isn't among the crafts materials")
    b = eco.get("burial", {})
    if b is not False and not isinstance(b, dict):
        raise ValueError("ecology.burial is {bury, rot, winter}, false for none, or absent for the defaults")
    for k, v in (b or {}).items():
        if k not in BURIAL or isinstance(v, bool) or not isinstance(v, (int, float)) or v < 0 \
                or (k != "bury" and v > 1):
            raise ValueError(f"ecology.burial.{k} must be one of {sorted(BURIAL)}: a non-negative number, a share "
                             f"for rot and winter; got {v!r}")
    d = eco.get("disease", [])
    if d is not False and not isinstance(d, list):
        raise ValueError("ecology.disease is a list of diseases, false for none, or absent for the draft")
    for x in d or []:
        if not isinstance(x, dict) or not x.get("id") or not x.get("name"):
            raise ValueError(f"a disease needs an id and a name, got {x!r}")
        for k in ("beta", "lethality", "duration", "wane", "tires", "base", "filth"):
            v = x.get(k)
            if isinstance(v, bool) or not isinstance(v, (int, float)) or v < 0 \
                    or (k in ("lethality", "wane", "tires", "base") and v > 1) or (k == "duration" and v < 1):
                raise ValueError(f"disease {x.get('id')!r}: bad {k}: {v!r}")
    ids = [x["id"] for x in d or []]
    if len(set(ids)) != len(ids):
        raise ValueError(f"disease ids must differ: {ids}")
    f = eco.get("famine")
    if f is not None:
        if not isinstance(f, dict):
            raise ValueError("ecology.famine is {eat, stores}")
        for k in ("eat", "stores", "keep"):
            v = f.get(k, FAMINE[k])
            if isinstance(v, bool) or not isinstance(v, (int, float)) or v < 0:
                raise ValueError(f"ecology.famine.{k} must be a non-negative number, got {v!r}")
        if f.get("keep", FAMINE["keep"]) < f.get("stores", FAMINE["stores"]):
            raise ValueError("ecology.famine.keep must be at least its stores (or the first stores spoil at once)")


def burying(dead: float, able: float, bury: float) -> tuple[float, float]:
    """A season's burial: the share of the able it takes, and the bodies they bury (pure). It can't take more than
    `SPARE` of them, so a town with too many dead leaves some lying."""
    if not dead or not able or not bury:
        return 0.0, 0.0
    hands = min(able * SPARE, dead / bury)
    return round(hands / able, 6), min(dead, hands * bury)


def able_share(labour: float, hunger: float, ill: float = 0.0) -> float:
    """The share of a town's work left once its dead, its hunger and its sick have had theirs (pure)."""
    return (1.0 - labour) * (1.0 - WEAK * hunger) * (1.0 - ill)


def outbreak_odds(spec: dict, dead: float, people: int) -> float:
    """A town's chance of an outbreak this season, from the dead lying per head (pure)."""
    filth = dead / people if people else 0.0
    return min(MOST_LIKELY, float(spec["base"]) + float(spec["filth"]) * filth)


def arrival_odds(carried: float) -> float:
    """A town's chance of an outbreak from those who have brought it since its last step (pure)."""
    return 1.0 - (1.0 - TAKES) ** carried


def catching(beta: float, sick: int, people: int, hunger: float) -> float:
    """A susceptible person's chance of catching it this season (pure)."""
    if not sick or not people:
        return 0.0
    return 1.0 - math.exp(-beta * (1.0 + FEVERED * hunger) * sick / people)


def tick(ctx) -> int:
    """The season, counted from the age's start: for reckoning what time has done since."""
    return ctx.today.year * 4 + ctx.calendar.season(ctx.today)


def remembered(immune: int, wane: float, seasons: int) -> int:
    """How many of a town's immune still are, `seasons` after it last counted them (pure)."""
    return int(immune * (1.0 - wane) ** max(0, seasons))


def disease_system():
    from renasci.core.systems import System
    from renasci.people import houses, life, population
    from renasci.people.races import BANDS

    class Disease(System):
        """Sickness in a town (see the module doc)."""

        name, cadence = "ecology.disease", "seasonal"
        priority = 2  # (after burial: what's still lying is what breeds it)
        reads = DISEASE_READS | life.DIE_READS
        writes = DISEASE_WRITES | life.DIE_WRITES
        event_types = (OUTBREAK, SEASON_SICK, ENDED_SICK, PASSED, *life.DIE_EVENTS)

        def handle(self, ctx, activation):
            houses.handle_succession(ctx, activation)  # (the follow-up `life.die` schedules)

        def run(self, ctx):
            self.step(ctx, 1)

        def coarse_fallback(self, ctx, years: int) -> None:
            self.step(ctx, 4 * years)

        def step(self, ctx, seasons: int) -> None:
            eco = ctx.params.get("ecology") or {}
            catalogue = eco.get("disease") if eco.get("disease") is not None else DISEASES
            for s in ctx.ids("settlement"):
                with ctx.scope(s):
                    state = dict(ctx.get(s, "disease") or {})
                    for spec in catalogue:
                        d = spec["id"]
                        people = population.masses(ctx, s)
                        if seasons > 1 and d in state:  # (coarse time doesn't carry an outbreak)
                            self.ended(ctx, s, state, d)
                        if d in state:
                            self.season(ctx, s, spec, state, people)
                        elif self.strikes(ctx, s, spec, people, seasons):
                            ev = ctx.emit("disease.outbreak", {"settlement": (s,)}, purpose=f"outbreak:{d}", actor=s,
                                          place=s, payload={"disease": d, "name": spec["name"]},
                                          causes=(*stocks.because(ctx, s, f"carried:{d}", 3),
                                                  *stocks.because(ctx, s, "corpses", 3)))
                            stocks.fade(ctx, s, f"carried:{d}", 1.0)
                            first = min(max(1, int(people * SEED)), people)
                            held, at = (ctx.get(s, "immunity") or {}).get(d, (0, 0))
                            kept = min(remembered(int(held), float(spec["wane"]), tick(ctx) - int(at)), people - first)
                            state[d] = {"sick": first, "immune": kept, "event": ev.id}
                            ctx.set(s, "disease", dict(state))
                            if seasons > 1:
                                self.wave(ctx, s, spec, state, people, ev.id)
                        elif stocks.level(ctx, s, f"carried:{d}"):  # (it came, and didn't take)
                            ctx.emit("disease.passed", {"settlement": (s,)}, purpose=f"passed:{d}", actor=s, place=s,
                                     payload={"disease": d}, causes=stocks.because(ctx, s, f"carried:{d}", 3))
                            stocks.fade(ctx, s, f"carried:{d}", 1.0)
                    people = population.masses(ctx, s)
                    ill = round(min(1.0, sum(v["sick"] for v in state.values()) / people), 6) if people else 0.0
                    if ill != float(ctx.get(s, "ill") or 0.0) and ctx.current_event:
                        ctx.set(s, "ill", ill)

        def strikes(self, ctx, s, spec, people, seasons) -> bool:
            if people <= 0:
                return False
            p = outbreak_odds(spec, stocks.level(ctx, s, "corpses"), people)
            brought = arrival_odds(stocks.level(ctx, s, f"carried:{spec['id']}"))
            return ctx.chance(1.0 - (1.0 - p) ** seasons * (1.0 - brought), f"outbreak:{spec['id']}", owner=s)

        def onward(self, ctx, s, spec, sick, people) -> None:
            """Who it goes with: the roads out, and those setting out (under this season's event)."""
            d, towns = spec["id"], set(ctx.ids("settlement"))
            ways = []
            for r in ctx.ids("route"):
                ends = ctx.get(r, "ends") or []
                if s in ends and ctx.get(r, "open") is not False:
                    ways += [e for e in ends if e != s and e in towns]
            ways += [ctx.get(p, "journey")["to"] for p in sorted(ctx.get(s, "residents") or []) if ctx.get(p, "journey")]
            for to in sorted(ways):
                if ctx.chance(min(1.0, ROADS * sick / people), f"carry:{d}:{to}", owner=s):
                    stocks.add(ctx, to, f"carried:{d}", 1.0)

        def wave(self, ctx, s, spec, state, people, event) -> None:
            changes, died = population.kill(ctx, s, [WAVE * float(spec["lethality"])] * BANDS, f"wave:{spec['id']}")
            ctx.emit("disease.season", {"settlement": (s,)}, purpose=f"wave:{spec['id']}", actor=s, place=s,
                     payload={"disease": spec["id"], "sick": 0, "new": int(people * WAVE), "died": died, "people": people},
                     causes=(Cause("event", event),))
            if died:
                ctx.write_columns(s, changes)
                population.fell(ctx, s, died)
            self.ended(ctx, s, state, spec["id"])

        def season(self, ctx, s, spec, state, people) -> None:
            d = spec["id"]
            now = state[d]
            hunger = float(ctx.get(s, "hunger") or 0.0)
            rng = ctx.rng(f"disease:{d}", s)
            sick = min(int(now["sick"]), people)
            immune = min(int(now["immune"]), people - sick)
            age = int(now.get("age", 0))
            odds = catching(float(spec["beta"]) * float(spec["tires"]) ** age, sick, people, hunger)
            new = rng.binomial(people - sick - immune, odds)
            out = rng.binomial(sick, 1.0 / float(spec["duration"]))
            rate = out * float(spec["lethality"]) / people if people else 0.0
            changes, died = population.kill(ctx, s, [rate] * BANDS, f"disease:{d}:dead") if out else ({}, 0)
            lost = rng.binomial(immune, float(spec["wane"]))
            ctx.emit("disease.season", {"settlement": (s,)}, purpose=f"sick:{d}", actor=s, place=s,
                     payload={"disease": d, "sick": sick + new - out, "new": new, "died": died, "people": people},
                     causes=(Cause("event", now["event"]),))
            stocks.fade(ctx, s, f"carried:{d}", 1.0)  # (it's here already: what's brought adds nothing)
            if died:
                ctx.write_columns(s, changes)
                population.fell(ctx, s, died)
            left = people - died
            state[d] = {**now, "age": age + 1, "sick": max(0, min(sick + new - out, left)),
                        "immune": max(0, min(immune + out - died - lost, left)), "event": now["event"]}
            if people:
                self.onward(ctx, s, spec, sick, people)
            over = not state[d]["sick"]
            if over:
                self.ended(ctx, s, state, d)
            else:
                ctx.set(s, "disease", dict(state))
            for p in sorted(ctx.get(s, "residents") or []):
                if ctx.status(p) == "active" and not ctx.get(p, "journey") \
                        and ctx.chance(odds * float(spec["lethality"]), f"plague:{d}", owner=p):
                    life.die(ctx, p, s, spec["name"], causes=(Cause("event", now["event"]),))

        def ended(self, ctx, s, state, d) -> None:
            ctx.emit("disease.ended", {"settlement": (s,)}, purpose=f"over:{d}", actor=s, place=s, payload={"disease": d},
                     causes=(Cause("event", state[d]["event"]),))
            ctx.set(s, "immunity", {**(ctx.get(s, "immunity") or {}), d: [int(state[d]["immune"]), tick(ctx)]})
            del state[d]
            ctx.set(s, "disease", dict(state))

    return Disease


def burial_system():
    from renasci.core.systems import System
    from renasci.people.population import masses

    class Burial(System):
        """The living and their dead (vision spec §1, #128): each town's able hands bury what they can, and every
        hand burying is one not working. What's left lies in `corpses`, rotting away by the season. It knows nothing
        of what killed them; whatever reads `corpses` or `labour` needs to know nothing of it."""

        name, cadence = "ecology.burial", "seasonal"
        priority = 1  # (before the harvest: who buries doesn't reap)
        reads = stocks.READS | frozenset({"ids:settlement", "residents", "hunger", "labour", "buried_at", "ill", "pop:*"})
        writes = stocks.WRITES | frozenset({"labour", "buried_at"})
        event_types = (BURIED,)

        def run(self, ctx):
            self.step(ctx, fine=True)

        def coarse_fallback(self, ctx, years: int) -> None:
            self.step(ctx, fine=False)

        def step(self, ctx, fine: bool) -> None:
            spec = {**BURIAL, **((ctx.params.get("ecology") or {}).get("burial") or {})}
            season = ctx.calendar.season(ctx.today)
            now = tick(ctx)
            rot = float(spec["winter" if season == 3 else "rot"])
            for s in ctx.ids("settlement"):
                with ctx.scope(s):
                    dead, was = stocks.level(ctx, s, "corpses"), float(ctx.get(s, "labour") or 0.0)
                    if not dead and not was:
                        continue
                    lying = dead / max(1, now - int(ctx.get(s, "buried_at") or now - 1))  # (see the module doc)
                    people = len(ctx.get(s, "residents")) + masses(ctx, s)
                    hunger = float(ctx.get(s, "hunger") or 0.0) if fine else 0.0
                    ill = float(ctx.get(s, "ill") or 0.0) if fine else 0.0
                    share, buried = burying(lying, people * ABLE * able_share(0.0, hunger, ill), float(spec["bury"]))
                    share = share if fine else 0.0
                    ctx.emit("burial.season", {"settlement": (s,)}, purpose="burial", actor=s, place=s,
                             payload={"buried": round(buried, 3), "left": round(lying - buried, 3), "labour": share},
                             causes=stocks.because(ctx, s, "corpses", 3))
                    if share != was:
                        ctx.set(s, "labour", share)
                    ctx.set(s, "buried_at", now)
                    stocks.take(ctx, s, "corpses", dead - lying + buried)
                    stocks.fade(ctx, s, "corpses", rot)

    return Burial


def stores(params: dict, heads: dict) -> dict:
    """A famine world's stores at the start ({material: {town: n}}: `stores` years of eating for its `heads`)."""
    eco = params.get("ecology") or {}
    if eco.get("famine") is None:
        return {}
    f = {**FAMINE, **eco["famine"]}
    return {eco["harvest"]["material"]: {s: math.ceil(n * f["eat"] * f["stores"]) for s, n in heads.items()}}


def hunger_rates(short: float, seasons: int = 1) -> list[float]:
    """The masses' extra death rate by band over `seasons`, for a town `short` (0..1) of its food (pure)."""
    from renasci.people.races import BANDS, BAND_YEARS

    def frail(b):
        return FRAIL if b * BAND_YEARS < 5 or b * BAND_YEARS >= 60 else 1.0

    return [round(1.0 - (1.0 - min(1.0, HUNGER * short * frail(b))) ** seasons, 6) for b in range(BANDS)]


def anomaly(last: float, shock: float, persist: float = PERSIST, spread: float = 1.0) -> float:
    """This season's anomaly from last season's and a standard normal shock: `persist` of the old carries, and
    the shock tops it up so a region's anomalies keep a spread of `spread` (pure)."""
    return persist * last + math.sqrt(1.0 - persist * persist) * spread * shock


def factor(warm: float, wet: float) -> float:
    """A harvest's share of a usual year's under this weather (pure): a little more in a kind year, less the
    drier or wetter it is and the colder (or, less, the hotter)."""
    f = 1.3 - 0.3 * abs(wet) - 0.2 * max(0.0, -warm) - 0.1 * max(0.0, warm)
    return round(max(0.0, min(1.3, f)), 4)


def kind(warm: float, wet: float, season: str) -> str:
    """A notable season's name ("" for an ordinary one)."""
    if wet <= -NOTABLE:
        return "drought"
    if wet >= NOTABLE:
        return "flood"
    if warm <= -NOTABLE:
        return "hard winter" if season == "Winter" else "cold"
    if warm >= NOTABLE:
        return "heat"
    return ""


def material(params: dict) -> str | None:
    """The material the harvest reaps, when ecology is on (S9's crafts skip its yearly yield)."""
    eco = params.get("ecology")
    return (eco.get("harvest") or {}).get("material") if eco else None


def harvest_day(calendar, season: str) -> int:
    """The day of the year a harvest comes: its season's first."""
    start = 0
    for name, days in calendar.seasons:
        if name == season:
            return start
        start += days
    raise ValueError(f"no season {season!r}")


def blight(ctx, factor: float, until: Date | None, event: str) -> dict:
    """A region's `blight` field for a ripple today: how many harvests it spoils (from the next, each up to
    `until`; just the next, without one)."""
    day = harvest_day(ctx.calendar, ctx.params["ecology"]["harvest"]["season"])
    first = ctx.today.year if ctx.today.day <= day else ctx.today.year + 1
    last = first if until is None else (until.year if until.day >= day else until.year - 1)
    return {"factor": float(factor), "harvests": max(1, last - first + 1), "event": event}


def climate_system():
    """The `ecology.climate` system (built on use)."""
    from renasci.core.systems import System

    class Climate(System):
        name, cadence = "ecology.climate", "seasonal"
        priority = 2
        reads, writes, event_types = READS, WRITES, EVENT_TYPES

        def run(self, ctx):
            self.step(ctx, 1, coarse=False)

        def coarse_fallback(self, ctx, years: int) -> None:
            self.step(ctx, years, coarse=True)

        def step(self, ctx, years: int, coarse: bool) -> None:
            eco = ctx.params["ecology"]
            season = ctx.calendar.season_name(ctx.today)
            h = eco["harvest"]
            harvest = coarse or season == h["season"]  # (a coarse step, from a year's start, reaps its years)
            weather = {}
            for r in sorted(ctx.ids("region")):
                with ctx.scope(r):
                    weather[r] = self.weather(ctx, r, eco, season)
                    if harvest:
                        weather[r]["blight"] = self.blighted(ctx, r, years)
            if not harvest:
                return
            spec = ((ctx.params.get("crafts") or {}).get("materials") or {})[h["material"]]
            for s in sorted(ctx.ids("settlement")):
                r = ctx.get(s, "region")
                if r in weather:
                    with ctx.scope(s):
                        self.reap(ctx, s, r, weather[r], h["material"], spec, years, coarse)

        def weather(self, ctx, r, eco, season) -> dict:
            c = eco.get("climate") or {}
            spread = float((c.get(r) or c.get("*") or {}).get("spread", 1.0))
            persist = float(eco.get("persist", PERSIST))
            last = ctx.get(r, "climate") or {}
            g = ctx.rng("weather", r)
            warm = round(anomaly(float(last.get("warm", 0.0)), float(g.normal()), persist, spread), 4)
            wet = round(anomaly(float(last.get("wet", 0.0)), float(g.normal()), persist, spread), 4)
            ev = ctx.emit("climate.season", {"region": (r,)}, purpose="season", actor=r,
                          payload={"warm": warm, "wet": wet, "kind": kind(warm, wet, season)})
            ctx.set(r, "climate", {"warm": warm, "wet": wet, "event": ev.id})
            return {"warm": warm, "wet": wet, "event": ev.id}

        def blighted(self, ctx, r, years) -> dict | None:
            """The blight on this step's harvest (its factor, how many of the step's years, its event), spending
            that many of the region's blighted harvests (after the season's weather event: its explanation)."""
            b = ctx.get(r, "blight")
            if not b or not b["harvests"]:
                return None
            k = min(int(b["harvests"]), years)
            ctx.set(r, "blight", {**b, "harvests": int(b["harvests"]) - k})
            return {"factor": float(b["factor"]), "years": k, "event": b["event"]}

        def reap(self, ctx, s, r, w, m, spec, years, coarse=False) -> None:
            from renasci.people import population

            f, causes = factor(w["warm"], w["wet"]), [Cause("event", w["event"])]
            if years > 1:  # (a coarse step: this weather's year, then usual ones)
                f = round((f + (years - 1) * MEAN) / years, 4)
            b = w.get("blight")
            if b:  # (a blighted harvest, or that share of a coarse step's)
                f = round((b["years"] * min(f, b["factor"]) + (years - b["years"]) * f) / years, 4)
                causes.append(Cause("event", b["event"]))
            rate = float(spec.get("yield", {}).get(r, spec.get("yield", {}).get("*", 0.0)))
            jobs = list(spec.get("by", []))
            masses = ctx.read_columns(s, [f"job:{j}" for j in jobs]) if ctx.params.get("aggregates") and jobs else {}
            notables = [ctx.get(p, "job") for p in ctx.get(s, "residents") if not ctx.get(p, "journey")]
            hands = sum(int(v) for v in masses.values())
            if hands:  # (the year's jobs were counted before this year's dead)
                every = list((ctx.params.get("crafts") or {}).get("jobs") or {})
                held = sum(int(v) for v in ctx.read_columns(s, [f"job:{j}" for j in every]).values())
                hands *= min(1.0, population.masses(ctx, s) / held)
            workers = hands + sum(notables.count(j) for j in jobs)
            if not coarse:  # (labour and hunger are a fine season's)
                workers *= able_share(float(ctx.get(s, "labour") or 0.0), float(ctx.get(s, "hunger") or 0.0),
                                      float(ctx.get(s, "ill") or 0.0))
            if not workers or not rate:
                return
            carry = dict(ctx.get(s, "yield_carry") or {})
            due = workers * rate * years * f + float(carry.get(m, 0.0))
            n = int(due)  # (whole units; the fraction carries to the next harvest)
            carry[m] = round(due - n, 6)
            ev = ctx.emit("harvest.failed" if f < FAILED else "harvest.reaped", {"settlement": (s,)}, purpose="harvest",
                     actor=s, place=s, payload={"produced": n, "factor": f}, causes=tuple(causes))
            ctx.set(s, "yield_carry", {k: v for k, v in sorted(carry.items()) if v})
            ctx.set(s, "harvest", ev.id)  # (the cause of a famine that follows)
            if n:
                now = ctx.read_columns(s, [f"stock:{m}", f"goods:{m}:produced"])
                ctx.write_columns(s, {f"stock:{m}": int(now[f"stock:{m}"]) + n,
                                      f"goods:{m}:produced": int(now[f"goods:{m}:produced"]) + n})

    return Climate


EATEN = EventType("goods.eaten", 1, roles={"settlement": (1, 1)},
                  payload={"eaten": "int", "need": "int", "short": "float", "died": "int", "spoiled": "int"})
BURIED = EventType("burial.season", 1, roles={"settlement": (1, 1)},
                   payload={"buried": "float", "left": "float", "labour": "float"})
OUTBREAK = EventType("disease.outbreak", 1, roles={"settlement": (1, 1)}, payload={"disease": "str", "name": "str"})
SEASON_SICK = EventType("disease.season", 1, roles={"settlement": (1, 1)},
                        payload={"disease": "str", "sick": "int", "new": "int", "died": "int", "people": "int"})
ENDED_SICK = EventType("disease.ended", 1, roles={"settlement": (1, 1)}, payload={"disease": "str"})
PASSED = EventType("disease.passed", 1, roles={"settlement": (1, 1)}, payload={"disease": "str"})
DISEASE_READS = stocks.READS | frozenset({"ids:settlement", "ids:route", "ends", "open", "residents", "race", "hunger", "disease", "ill", "journey", "immunity",
                                          "pop:*", "allele:*", "flow:*"})
DISEASE_WRITES = stocks.WRITES | frozenset({"disease", "ill", "immunity", "pop:*", "allele:*", "flow:*"})
BEGAN = EventType("famine.began", 1, roles={"settlement": (1, 1)}, payload={"short": "float"})
ENDED = EventType("famine.ended", 1, roles={"settlement": (1, 1)}, payload={"since": "json"})
FAMINE_READS = frozenset({"ids:settlement", "residents", "race", "famine", "harvest", "hunger", "pop:*", "allele:*",
                          "flow:*", "stock:*", "goods:*"}) | stocks.READS
FAMINE_WRITES = frozenset({"famine", "hunger", "pop:*", "allele:*", "flow:*", "stock:*", "goods:*"}) | stocks.WRITES


def famine_system():
    """The `ecology.famine` system (built on use)."""
    from renasci.core.systems import System
    from renasci.people import population

    class Famine(System):
        name, cadence = "ecology.famine", "seasonal"
        priority = 3  # (after the weather and the harvest)
        reads, writes, event_types = FAMINE_READS, FAMINE_WRITES, (EATEN, BEGAN, ENDED)

        def run(self, ctx):
            self.step(ctx, 1)

        def coarse_fallback(self, ctx, years: int) -> None:
            self.step(ctx, 4 * years)

        def step(self, ctx, seasons: int) -> None:
            eco = ctx.params["ecology"]
            f, m = {**FAMINE, **eco["famine"]}, eco["harvest"]["material"]
            for s in sorted(ctx.ids("settlement")):
                with ctx.scope(s):
                    self.eat(ctx, s, m, float(f["eat"]), float(f["keep"]), seasons)

        def eat(self, ctx, s, m, eat, keep, seasons) -> None:
            heads = population.masses(ctx, s) + len(ctx.get(s, "residents"))
            need = math.ceil(heads * eat * seasons / 4)
            if not need:  # (an emptied town: nobody left to starve)
                famine = ctx.get(s, "famine")
                if famine:
                    ctx.emit("famine.ended", {"settlement": (s,)}, purpose="famine", actor=s, place=s,
                             payload={"since": famine["since"]}, causes=(Cause("event", famine["event"]),))
                    ctx.set(s, "famine", None)
                    ctx.set(s, "hunger", 0.0)
                return
            g = ctx.read_columns(s, [f"stock:{m}", f"goods:{m}:used", f"goods:{m}:destroyed"])
            eaten = min(int(g[f"stock:{m}"]), need)
            short = round(1.0 - eaten / need, 4)
            spoiled = max(0, int(g[f"stock:{m}"]) - eaten - math.ceil(heads * eat * keep))
            changes, died = population.kill(ctx, s, hunger_rates(short, seasons), "hunger") if short else ({}, 0)
            ctx.emit("goods.eaten", {"settlement": (s,)}, purpose="eaten", actor=s, place=s,
                     payload={"eaten": eaten, "need": need, "short": short, "died": died, "spoiled": spoiled})
            population.fell(ctx, s, died)
            ctx.write_columns(s, {**changes, f"stock:{m}": int(g[f"stock:{m}"]) - eaten - spoiled,
                                  f"goods:{m}:used": int(g[f"goods:{m}:used"]) + eaten,
                                  f"goods:{m}:destroyed": int(g[f"goods:{m}:destroyed"]) + spoiled})
            hunger = short if seasons == 1 else 0.0  # (notables' hazard is a fine season's; a coarse step's dead
            if hunger or ctx.get(s, "hunger"):           # are its masses')
                ctx.set(s, "hunger", hunger)
            famine = ctx.get(s, "famine")
            if not famine and short >= BEGIN:
                harvest = ctx.get(s, "harvest")
                ev = ctx.emit("famine.began", {"settlement": (s,)}, purpose="famine", actor=s, place=s,
                              payload={"short": short}, causes=(Cause("event", harvest),) if harvest else ())
                ctx.set(s, "famine", {"since": ctx.today.to_json(), "event": ev.id})
            elif famine and short <= END:
                ctx.emit("famine.ended", {"settlement": (s,)}, purpose="famine", actor=s, place=s,
                         payload={"since": famine["since"]}, causes=(Cause("event", famine["event"]),))
                ctx.set(s, "famine", None)

    return Famine
