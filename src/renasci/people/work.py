"""Jobs, skills and wealth (S9 spec §2, #123): what notables do for a living, how good they get at it, and
what it earns them; and what the masses of each town work at.

Only in a world whose params carry a `crafts` catalogue (`{"jobs": {id: {name, demand, income, makes?}}}`):
the system is added then, and the scenario casts a `job:<id>` column per settlement (the masses in each job).

`people.work` (yearly, one `ctx.scope(settlement)` per settlement):

- **A job at adulthood:** each resident of `ADULT` years or more without one takes one (`people.job`), a keyed
  draw weighted by what the town lacks of it (its `demand` share of the town's grown notables, less those who
  already hold it as the year began), by a parent's job (`KIN_LEAN`: a smith's child leans to the forge), and by house (a great house's
  children lean to its `HOUSE_JOBS`).
- **Skill and wealth:** a working notable's skill in their job grows (`GROW` a year, faster young and with wits,
  slower near mastery); their other skills fade (`FADE`); their `wealth` grows by the job's `income`. One
  `people.work` event a settlement explains the year's writes (none when nothing changes). Those on a journey
  pause.
- **The masses:** each `job:<id>` column moves `DRIFT` of the way toward its share of the town's masses (by
  demand), the shares summing exactly to the masses after each step.

A coarse step of N years does the same with N years of growth, income and drift.
"""

from __future__ import annotations

import math

from renasci.core.events import EventType
from renasci.core.systems import System
from renasci.people.ambitions import trait
from renasci.people.population import masses
from renasci.people.races import age_years

JOB = EventType("people.job", 1, roles={"worker": (1, 1)}, payload={"job": "str", "parent_job": "json"})
WORK = EventType("people.work", 1, roles={"settlement": (1, 1)}, payload={"workers": "int"})
EVENT_TYPES = (JOB, WORK)
ADULT = 16
GROW, FADE, DRIFT = 0.06, 0.98, 0.25
KIN_LEAN = 3.0
HOUSE_JOBS = {"steward": 2.0, "soldier": 2.0, "merchant": 1.5}
READS = frozenset({"ids:settlement", "residents", "born", "job", "skills", "wealth", "father", "mother", "house",
                   "traits", "journey", "pop:*", "job:*"})
WRITES = frozenset({"job", "skills", "wealth", "job:*"})


def jobs(ctx) -> dict:
    return (ctx.params.get("crafts") or {}).get("jobs") or {}


def shares(n: int, demand: dict[str, float]) -> dict[str, int]:
    """`n` people shared out by demand, summing exactly to `n` (largest remainders, ties by id)."""
    total = sum(demand.values())
    raw = {j: n * d / total for j, d in sorted(demand.items())}
    out = {j: int(x) for j, x in raw.items()}
    rest = n - sum(out.values())
    for j in sorted(raw, key=lambda j: (-(raw[j] - out[j]), j))[:rest]:
        out[j] += 1
    return out


class Work(System):
    name, cadence = "people.work", "yearly"
    priority = 4  # (before drives and ambitions read what people do)
    reads, writes, event_types = READS, WRITES, EVENT_TYPES

    def run(self, ctx):
        self.step(ctx, 1)

    def coarse_fallback(self, ctx, years: int) -> None:
        self.step(ctx, years)

    def step(self, ctx, years: int) -> None:
        catalogue = jobs(ctx)
        ids = sorted(catalogue)
        for s in ctx.ids("settlement"):
            with ctx.scope(s):
                residents = [p for p in ctx.get(s, "residents") if not ctx.get(p, "journey")]  # (the road pauses work)
                grown = [p for p in residents if age_years(ctx.calendar, ctx.get(p, "born"), ctx.today) >= ADULT]
                held = [ctx.get(p, "job") for p in grown]  # (as the year began: one newcomer's pick never sways another's)
                for p in grown:
                    if ctx.get(p, "job") is None:
                        self.take(ctx, p, catalogue, ids, held, len(grown))
                working = [p for p in grown if ctx.get(p, "job")]
                columns = self.masses(ctx, s, catalogue, ids, years)
                if not working and not columns:
                    continue
                ctx.emit("people.work", {"settlement": (s,)}, purpose="work", actor=s, place=s,
                         payload={"workers": len(working)})
                for p in working:
                    self.labour(ctx, p, catalogue, years)
                if columns:
                    ctx.write_columns(s, columns)

    def take(self, ctx, person, catalogue, ids, held, grown) -> str:
        """A job for one come of age (see the module doc)."""
        parents = [ctx.get(person, k) for k in ("father", "mother")]
        kin = {ctx.get(x, "job") for x in parents if x and ctx.exists(x)} - {None}
        house = ctx.get(person, "house")
        weights = []
        for j in ids:
            want = float(catalogue[j]["demand"]) * max(grown, 1)  # (the town's need for it)
            w = max(0.1, want - held.count(j))  # (what it lacks)
            if j in kin:
                w *= KIN_LEAN
            if house:
                w *= HOUSE_JOBS.get(j, 1.0)
            weights.append(round(w, 6))
        job = ctx.choose("job", ids, owner=person, weights=weights)
        ctx.emit("people.job", {"worker": (person,)}, purpose="job", actor=person,
                 payload={"job": job, "parent_job": sorted(kin)})
        ctx.set(person, "job", job)
        return job

    def labour(self, ctx, person, catalogue, years) -> None:
        job = ctx.get(person, "job")
        skills = dict(ctx.get(person, "skills") or {})
        age = age_years(ctx.calendar, ctx.get(person, "born"), ctx.today)
        youth = 1.5 if age < 30 else 1.0 if age < 50 else 0.5
        s = float(skills.get(job, 0.0))
        for _ in range(years):
            s += GROW * youth * (0.5 + trait(ctx, person, "wits")) * (1.0 - s)
        skills = {k: round(v * FADE ** years, 3) for k, v in skills.items() if k != job}
        skills = {k: v for k, v in skills.items() if v >= 0.01}
        skills[job] = round(min(1.0, s), 3)
        ctx.set(person, "skills", dict(sorted(skills.items())))
        income = float(catalogue.get(job, {}).get("income", 0.0)) * years
        ctx.set(person, "wealth", round(float(ctx.get(person, "wealth") or 0.0) + income, 2))

    def masses(self, ctx, s, catalogue, ids, years) -> dict | None:
        """The masses' new job columns, or None when nothing moves."""
        if not ctx.params.get("aggregates"):
            return None
        n = masses(ctx, s)
        now = ctx.read_columns(s, [f"job:{j}" for j in ids])
        target = shares(n, {j: float(catalogue[j]["demand"]) for j in ids})
        keep = (1.0 - DRIFT) ** years
        moved = {j: now[f"job:{j}"] * keep + target[j] * (1.0 - keep) for j in ids}
        new = shares(n, moved) if sum(moved.values()) > 0 else target
        if any(int(now[f"job:{j}"]) != new[j] for j in ids):
            return {f"job:{j}": new[j] for j in ids}
        return None


def cast(engine, settlements: list[str], counts: dict[str, int], catalogue: dict) -> None:
    """The masses' job columns at the start: each town's masses shared out by demand."""
    js = catalogue.get("jobs") or {}
    ids = sorted(js)
    if not ids:
        return
    split = {s: shares(counts.get(s, 0), {j: float(js[j]["demand"]) for j in ids}) for s in settlements}
    for j in ids:
        engine.cast_column(f"job:{j}", "int64", settlements, [split[s][j] for s in settlements])


def check(crafts) -> None:
    """Refuse a malformed catalogue (raises ValueError)."""
    if not isinstance(crafts, dict) or not isinstance(crafts.get("jobs"), dict) or not crafts["jobs"]:
        raise ValueError("crafts needs a non-empty `jobs` table")
    def number(x) -> bool:
        return not isinstance(x, bool) and isinstance(x, (int, float)) and math.isfinite(x)

    for j, spec in crafts["jobs"].items():
        if not isinstance(spec, dict):
            raise ValueError(f"job {j!r} must be a table, got {spec!r}")
        d, inc = spec.get("demand"), spec.get("income", 0)
        if not number(d) or d <= 0:
            raise ValueError(f"job {j!r}: demand must be a positive number, got {d!r}")
        if not number(inc) or inc < 0:
            raise ValueError(f"job {j!r}: income must be a number of at least 0, got {inc!r}")
