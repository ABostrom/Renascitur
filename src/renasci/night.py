"""The night (S10 §5, #130): what's out there, and what keeps it out.

A town's **wards** (0..1) hold the dark back. They wear away every season, and people mend them. Mending takes hands: a
town that's sick, starving or still burying its dead has fewer to spare, so its wards fall. Nothing here knows about
plague or famine: it reads how the town stands (vision spec §2). A town whose wards fall below `failed` has a
`ward.failed`, unless something protects it (`ctx.guarded`).

A season's **dark** is `effective`: the base dark, the town's `danger` and any surge, by the season's length of night,
cut by the wards. It takes a share of the masses (`night.toll`), and now and then a notable, so the dead go where all the
dead go (`population.fell`), and the survivors have that to deal with too.

**Surges** come to a region on a keyed draw (`night.surge`), and add to each town's `aberrant` stock, which fades.

Roads, strikes on travellers, Lux Lapis, wardens and Sabotage are the rest of §5 and aren't built yet.

`params.night` turns it on; its values override `DEFAULT`.
"""

from __future__ import annotations

from renasci.core import stocks
from renasci.core.events import Cause, EventType
from renasci.core.systems import System
from renasci.people import houses, life, population
from renasci.people.races import BANDS

DEFAULT: dict = {"dark": 0.2, "toll": 0.02, "wards": 0.8, "decay": 0.04, "mend": 0.05, "failed": 0.3, "hands": 60,
                 "surge": 0.01, "surge_by": 1.0, "ebb": 0.5, "notable": 0.1,
                 "seasons": {"Winter": 1.5, "Summer": 0.5}}
# (the base dark; the share of the masses it can take a season; wards at the start; what they lose a season and what a
# whole town mends; below `failed` they've failed; the people it takes to keep them; a region's odds of a surge a season,
# what one adds and the share that fades a season; a notable's odds, at full dark; the night's length by season)
RESTORED = 2.0  # (failed wards are whole again at this many times `failed`)
SHAKES = 0.15  # (a dark this deep frightens those it spares)

SEASON = EventType("night.season", 1, roles={"settlement": (1, 1)}, payload={"wards": "float"})
TOLL = EventType("night.toll", 1, roles={"settlement": (1, 1)}, payload={"died": "int", "dark": "float"})
SURGE = EventType("night.surge", 1, roles={"settlement": (1, 1)}, payload={"region": "id"})
FAILED = EventType("ward.failed", 1, roles={"settlement": (1, 1)}, payload={"wards": "float"})
MENDED = EventType("ward.mended", 1, roles={"settlement": (1, 1)}, payload={"wards": "float"})


def effective(dark: float, danger: float, surge: float, night: float, wards: float) -> float:
    """How dark it is in a town this season, 0..1."""
    return min(1.0, (dark + danger + surge) * night * (1.0 - wards))


def strength(people: int, hands: int, ill: float, hunger: float, corpses: float) -> float:
    """The share of a whole town's mending this town can do, 0..1: enough people, fit, and not burying the dead."""
    if people <= 0:
        return 0.0
    return min(1.0, people / hands) * (1.0 - ill) * (1.0 - 0.5 * hunger) / (1.0 + corpses / people)


class Night(System):
    name, cadence = "night", "seasonal"
    priority = 3  # (after burial and sickness: it finds the town as they left it)
    feeds, uses = ("aberrant", "corpses", "dread", "faith"), ("aberrant", "corpses")
    reads = life.DIE_READS | stocks.READS | frozenset({"ids:settlement", "region", "danger", "wards", "ward_failed", "ill",
                                                       "hunger", "residents", "journey", "pop:*", "allele:*", "flow:*"})
    writes = life.DIE_WRITES | stocks.WRITES | frozenset({"wards", "ward_failed", "pop:*", "allele:*", "flow:*"})
    event_types = (SEASON, TOLL, SURGE, FAILED, MENDED, *life.DIE_EVENTS)

    def handle(self, ctx, activation):
        houses.handle_succession(ctx, activation)  # (the follow-up `life.die` schedules)

    def run(self, ctx):
        self.step(ctx, 1)

    def coarse_fallback(self, ctx, years: int) -> None:
        self.step(ctx, 4 * years)

    def step(self, ctx, seasons: int) -> None:
        cfg = {**DEFAULT, **(ctx.params.get("night") or {})}
        struck = {}
        for s in ctx.ids("settlement"):
            region = ctx.get(s, "region")
            if region not in struck:
                with ctx.scope(region):
                    struck[region] = ctx.chance(1.0 - (1.0 - cfg["surge"]) ** seasons, "surge", owner=region)
            with ctx.scope(s):
                self.town(ctx, s, cfg, seasons, struck[region], region)

    def town(self, ctx, s: str, cfg: dict, seasons: int, surges: bool, region) -> None:
        people = population.masses(ctx, s)
        if surges:
            ctx.emit("night.surge", {"settlement": (s,)}, purpose="surge", actor=s, place=s, payload={"region": region})
            stocks.add(ctx, s, "aberrant", cfg["surge_by"])
        wards = float(ctx.get(s, "wards") or 0.0)
        able = strength(people, cfg["hands"], float(ctx.get(s, "ill") or 0.0), float(ctx.get(s, "hunger") or 0.0),
                        stocks.level(ctx, s, "corpses"))
        now = round(max(0.0, min(cfg["wards"], wards + seasons * (cfg["mend"] * able - cfg["decay"]))), 6)
        if now != wards or stocks.level(ctx, s, "aberrant"):  # (either changes something, which needs an event)
            ctx.emit("night.season", {"settlement": (s,)}, purpose="wards", actor=s, place=s, payload={"wards": now})
            ctx.set(s, "wards", now)
        self.fails(ctx, s, cfg, now)
        length = 1.0 if seasons > 1 else float(cfg["seasons"].get(ctx.calendar.season_name(ctx.today), 1.0))
        dark = effective(cfg["dark"], float(ctx.get(s, "danger") or 0.0), stocks.level(ctx, s, "aberrant"), length, now)
        causes = stocks.because(ctx, s, "aberrant", 3)
        rate = min(1.0, seasons * cfg["toll"] * dark)
        if people > 0 and rate > 0.0:
            changes, died = population.kill(ctx, s, [rate] * BANDS, "night")
            if died:
                ev = ctx.emit("night.toll", {"settlement": (s,)}, purpose="toll", actor=s, place=s,
                              payload={"died": died, "dark": round(dark, 6)}, causes=causes)
                ctx.write_columns(s, changes)
                population.fell(ctx, s, died)
                self.notable(ctx, s, cfg, dark, seasons, ev.id)
        stocks.fade(ctx, s, "aberrant", cfg["ebb"])

    def fails(self, ctx, s: str, cfg: dict, wards: float) -> None:
        down = bool(ctx.get(s, "ward_failed"))
        if not down and wards < cfg["failed"] and not ctx.guarded(s):
            ev = ctx.emit("ward.failed", {"settlement": (s,)}, purpose="failed", actor=s, place=s, payload={"wards": wards},
                          causes=stocks.because(ctx, s, "corpses", 3))
            ctx.set(s, "ward_failed", ev.id)
        elif down and wards >= RESTORED * cfg["failed"]:
            ctx.emit("ward.mended", {"settlement": (s,)}, purpose="mended", actor=s, place=s, payload={"wards": wards},
                     causes=(Cause("event", ctx.get(s, "ward_failed")),))
            ctx.set(s, "ward_failed", None)

    def notable(self, ctx, s: str, cfg: dict, dark: float, seasons: int, toll: str) -> None:
        home = [p for p in sorted(ctx.get(s, "residents") or []) if not ctx.get(p, "journey")]
        if not home or not ctx.chance(1.0 - (1.0 - cfg["notable"] * dark) ** seasons, "notable", owner=s):
            return
        victim = ctx.choose("taken", home, owner=s)
        life.die(ctx, victim, s, "night terrors", causes=(Cause("event", toll),))
        if dark >= SHAKES:
            for p in sorted(set(home) - {victim}):
                stocks.add(ctx, p, "dread", 0.5)
