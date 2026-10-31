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
"""

from __future__ import annotations

import math

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
                   "yield_carry", "job:*", "stock:*", "goods:*"})
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
                        self.reap(ctx, s, r, weather[r], h["material"], spec, years)

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

        def reap(self, ctx, s, r, w, m, spec, years) -> None:
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
            workers = sum(int(masses.get(f"job:{j}", 0)) + notables.count(j) for j in jobs)
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
BEGAN = EventType("famine.began", 1, roles={"settlement": (1, 1)}, payload={"short": "float"})
ENDED = EventType("famine.ended", 1, roles={"settlement": (1, 1)}, payload={"since": "json"})
FAMINE_READS = frozenset({"ids:settlement", "residents", "race", "famine", "harvest", "hunger", "pop:*", "allele:*",
                          "flow:*", "stock:*", "goods:*"})
FAMINE_WRITES = frozenset({"famine", "hunger", "pop:*", "allele:*", "flow:*", "stock:*", "goods:*"})


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
