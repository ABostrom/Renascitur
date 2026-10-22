"""Populations as aggregates, and the level of detail between them and notables (S3 spec §8).

A settlement's masses are numeric columns keyed by the settlement id:

- `pop:<sex>:<band>`: how many, by sex and 5-year band (20 bands);
- `allele:<locus>:<variant>`: allele copies, always twice the count for each locus;
- `flow:<name>`: ledgers for conservation: `initial`, `born`, `died`, `promoted`, `demoted`, `in`, `out`.

`people.population` (seasonal) steps every settlement in its own scope, from one keyed stream per
settlement per season: deaths by band (binomial), births from the fertile bands (binomial, damped
by crowding), ageing once a year (a fifth of each band moves up). Dying copies leave by a
multivariate hypergeometric draw; newborn copies come from the survivors' frequencies. It logs one
`timeseries` row per settlement per year.

**Notables come and go.** `promote_person` samples someone from the counts (band, sex, birth date,
two copies per locus, all drawn from the settlement's stream for that reason) and lowers the counts
to match; their parents are unknown and their copies are founder stock of the settlement.
`demote_person` adds a notable back. `people.lod` (yearly) fades quiet commoners (no house, office,
spouse or young child, not guarded) back into the masses while a settlement has more notables than
its `notable_target`.

`conservation(catalogue)` checks every settlement: masses + resident notables equals
`initial + born - died + in - out`, and allele copies equal twice the masses.
"""

from __future__ import annotations

from renasci.core.events import EventType
from renasci.core.lod import EVENT_TYPES as LOD_TYPES
from renasci.core.systems import System
from renasci.people.races import BANDS, BAND_YEARS, age_years, band, quarterly

SEXES = ("f", "m")
BAND_COLUMNS = tuple(f"pop:{sex}:{b}" for sex in SEXES for b in range(BANDS))
FLOWS = ("initial", "born", "died", "promoted", "demoted", "in", "out")
FLOW_COLUMNS = tuple(f"flow:{f}" for f in FLOWS)
COLUMN_READS = frozenset({"pop:*", "allele:*", "flow:*"})

STEP = EventType("people.population", 1, roles={"settlement": (1, 1)}, payload={"born": "int", "died": "int"})


def band_column(sex: str, b: int) -> str:
    return f"pop:{sex}:{b}"


def allele_column(locus: str, variant: str) -> str:
    return f"allele:{locus}:{variant}"


def masses(ctx, settlement: str) -> int:
    return sum(int(v) for v in (ctx.read_column(c, [settlement])[0] for c in BAND_COLUMNS))


def bump(ctx, settlement: str, **flows: int) -> None:
    """Add to a settlement's ledgers (no-op in a world without aggregates)."""
    if ctx.params.get("aggregates"):
        _bump(ctx, settlement, **flows)


def _bump(ctx, settlement: str, **flows: int) -> None:
    ctx.write_columns(settlement, {f"flow:{k}": int(ctx.read_column(f"flow:{k}", [settlement])[0]) + n
                                   for k, n in sorted(flows.items())})


# ---------------------------------------------------------------- casting (deterministic, no draws)


def stable_bands(race, total: int) -> dict[str, list[int]]:
    """A starting age structure: survivorship from the race's life table, split by sex, rounded so
    the bands sum to exactly `total` (largest remainders first, ties by position)."""
    weights = []
    for sex in SEXES:
        alive = 1.0
        for b in range(BANDS):
            weights.append(alive)
            alive *= (1.0 - race.mortality[sex][b]) ** BAND_YEARS
    counts = _apportion(total, weights)
    return {"f": counts[:BANDS], "m": counts[BANDS:]}


def _apportion(total: int, weights: list[float]) -> list[int]:
    s = sum(weights)
    exact = [total * w / s for w in weights]
    out = [int(x) for x in exact]
    order = sorted(range(len(weights)), key=lambda i: (-(exact[i] - out[i]), i))
    for i in order[: total - sum(out)]:
        out[i] += 1
    return out


def cast_masses(engine, settlements: dict, catalogue, races) -> None:
    """Cast every settlement's columns. `settlements` maps id -> (race id, genome group, masses,
    notables): the ledger starts at masses + notables."""
    ids = sorted(settlements)
    bands = {s: stable_bands(races[settlements[s][0]], settlements[s][2]) for s in ids}
    for sex in SEXES:
        for b in range(BANDS):
            engine.cast_column(band_column(sex, b), "int64", ids, [bands[s][sex][b] for s in ids])
    for lo in catalogue.loci:
        copies = {s: _apportion(2 * settlements[s][2],
                                [catalogue.groups[settlements[s][1]][lo.id].get(v, 0.0) for v in lo.variants])
                  for s in ids}
        for i, v in enumerate(lo.variants):
            engine.cast_column(allele_column(lo.id, v), "int64", ids, [copies[s][i] for s in ids])
    for f in FLOWS:
        engine.cast_column(f"flow:{f}", "int64", ids,
                           [settlements[s][2] + settlements[s][3] if f == "initial" else 0 for s in ids])


# ---------------------------------------------------------------- the seasonal step


class Population(System):
    name, cadence = "people.population", "seasonal"
    priority = -2  # before births and deaths of notables
    reads = COLUMN_READS | {"ids:settlement", "race", "residents", "capacity"}
    writes = frozenset({"pop:*", "allele:*", "flow:*"})
    event_types = (STEP,)

    def run(self, ctx):
        from renasci.people.life import crowding, world

        races, catalogue, _ = world(ctx)
        married = float(ctx.params.get("married_share", 0.7))
        yearly = ctx.calendar.season(ctx.today) == 0
        for s in ctx.ids("settlement"):
            with ctx.scope(s):
                race = races[ctx.get(s, "race")]
                n = {c: int(ctx.read_column(c, [s])[0]) for c in BAND_COLUMNS}
                rng = ctx.rng("population", s)
                died = 0
                for sex in SEXES:
                    for b in range(BANDS):
                        d = rng.binomial(n[band_column(sex, b)], quarterly(race.mortality[sex][b]))
                        n[band_column(sex, b)] -= d
                        died += d
                total = sum(n.values())
                damp = crowding(total + len(ctx.get(s, "residents")), ctx.get(s, "capacity"))
                births = sum(rng.binomial(n[band_column("f", b)], quarterly(race.fertility[b]) * married * damp)
                             for b in range(BANDS))
                boys = rng.binomial(births, race.male)
                n[band_column("m", 0)] += boys
                n[band_column("f", 0)] += births - boys
                if yearly:
                    for sex in SEXES:
                        for b in range(BANDS - 2, -1, -1):  # from the top, so nobody moves twice
                            up = rng.binomial(n[band_column(sex, b)], 1.0 / BAND_YEARS)
                            n[band_column(sex, b)] -= up
                            n[band_column(sex, b + 1)] += up
                changes = dict(n)
                for lo in catalogue.loci:
                    cols = [allele_column(lo.id, v) for v in lo.variants]
                    copies = [int(ctx.read_column(c, [s])[0]) for c in cols]
                    copies = [c - r for c, r in zip(copies, rng.hypergeometric(copies, 2 * died))]
                    if births:
                        left = sum(copies)
                        copies = [c + a for c, a in zip(copies, rng.multinomial(2 * births, [c / left for c in copies]))]
                    changes.update(zip(cols, copies))
                ctx.emit("people.population", {"settlement": (s,)}, purpose="population", actor=s, place=s,
                         payload={"born": births, "died": died})
                for f, delta in (("born", births), ("died", died)):
                    changes[f"flow:{f}"] = int(ctx.read_column(f"flow:{f}", [s])[0]) + delta
                ctx.write_columns(s, changes)
                if yearly:
                    ctx.series(s, {"pop": {sex: [n[band_column(sex, b)] for b in range(BANDS)] for sex in SEXES},
                                   "notables": len(ctx.get(s, "residents"))})


# ---------------------------------------------------------------- promotion and demotion


def promote_person(ctx, settlement: str, reason: str, *, sex: str, ages: tuple[int, int]) -> str | None:
    """Pull one person of `sex`, aged within `ages`, out of the settlement's masses. None if there is
    nobody to pull. Draws come from the settlement's stream for this reason."""
    from renasci.people.genome import allele, phenotype
    from renasci.people.life import world

    races, catalogue, _ = world(ctx)
    race_id = ctx.get(settlement, "race")
    race = races[race_id]
    lo_b, hi_b = band(ages[0]), band(ages[1])
    counts = {b: int(ctx.read_column(band_column(sex, b), [settlement])[0]) for b in range(lo_b, hi_b + 1)}
    if not any(counts.values()):
        return None
    rng = ctx.rng(f"promote:{reason}", settlement)
    bands = sorted(counts)
    b = bands[rng.choice_index([counts[x] for x in bands])]
    low, high = max(b * BAND_YEARS, ages[0]), min(b * BAND_YEARS + BAND_YEARS - 1, ages[1])
    age = low + int(rng.integers(0, high - low + 1))
    day = int(rng.integers(0, ctx.calendar.days_per_year))
    born = [ctx.today.age, ctx.today.year - age - (1 if day > ctx.today.day else 0), day]
    take = {band_column(sex, b): 1}
    genome = {}
    for lo in catalogue.loci:
        cols = [allele_column(lo.id, v) for v in lo.variants]
        drawn = rng.hypergeometric([int(ctx.read_column(c, [settlement])[0]) for c in cols], 2)
        pair = [v for v, k in zip(lo.variants, drawn) for _ in range(k)]
        if rng.random() < 0.5:
            pair.reverse()
        genome[lo.id] = [allele(v, f"f:{settlement}") for v in pair]
        for c, k in zip(cols, drawn):
            if k:
                take[c] = take.get(c, 0) + k
    names = race.names[sex]
    fields = {"name": names[rng.choice_index([1.0] * len(names))], "sex": sex, "born": born, "race": race_id,
              "place": settlement, "house": None, "mother": None, "father": None, "children": [], "spouse": None,
              "genome": genome, "traits": phenotype(catalogue, genome, {}), "drives": {}, "ties": [],
              "last_birth": None, "offices": []}
    person = ctx.promote(settlement, "person", fields, reason=reason, columns=take, place=settlement)
    ctx.set(settlement, "residents", sorted(ctx.get(settlement, "residents") + [person]))
    _bump(ctx, settlement, promoted=1)
    return person


def demote_person(ctx, person: str, settlement: str, *, reason: str) -> None:
    """Fade a notable back into the settlement's masses: their band and allele copies are added back."""
    from renasci.people.genome import variant_of

    age = age_years(ctx.calendar, ctx.get(person, "born"), ctx.today)
    give = {band_column(ctx.get(person, "sex"), band(age)): 1}
    for locus, pair in sorted(ctx.get(person, "genome").items()):
        for c in pair:
            col = allele_column(locus, variant_of(c))
            give[col] = give.get(col, 0) + 1
    ctx.demote(person, reason=reason, aggregate=settlement, columns=give)
    ctx.set(settlement, "residents", [p for p in ctx.get(settlement, "residents") if p != person])
    _bump(ctx, settlement, demoted=1)


class Lod(System):
    """Fade quiet commoners back into the masses while a settlement has more notables than its target."""

    name, cadence = "people.lod", "yearly"
    reads = COLUMN_READS | {"ids:settlement", "residents", "notable_target", "house", "offices", "spouse", "children",
                            "born", "status", "sex", "genome"}
    writes = frozenset({"pop:*", "allele:*", "flow:*", "residents", "status"})
    event_types = LOD_TYPES

    def run(self, ctx):
        rate = float(ctx.params.get("demote_rate", 0.2))
        for s in ctx.ids("settlement"):
            with ctx.scope(s):
                residents = ctx.get(s, "residents")
                excess = len(residents) - int(ctx.get(s, "notable_target") or len(residents))
                for p in residents:
                    if excess <= 0:
                        break
                    if not self._quiet(ctx, p) or ctx.guarded(p):
                        continue
                    if ctx.chance(rate, "demote", owner=p):
                        demote_person(ctx, p, s, reason="quiet")
                        excess -= 1

    @staticmethod
    def _quiet(ctx, p: str) -> bool:
        if ctx.get(p, "house") is not None or ctx.get(p, "offices") or ctx.get(p, "spouse") is not None:
            return False
        return not any(ctx.status(c) == "active" and age_years(ctx.calendar, ctx.get(c, "born"), ctx.today) < 16
                       for c in ctx.get(p, "children") or [])


# ---------------------------------------------------------------- conservation


def conservation(catalogue):
    """A ruleset's `conservation(store)`: what doesn't add up, settlement by settlement."""
    def check(store) -> list[str]:
        problems = []
        for s in store.ids("settlement"):
            def col(name):
                return int(store.read_column(name, [s])[0])
            n = sum(col(c) for c in BAND_COLUMNS)
            if any(col(c) < 0 for c in BAND_COLUMNS):
                problems.append(f"{s}: a negative count")
            ledger = col("flow:initial") + col("flow:born") - col("flow:died") + col("flow:in") - col("flow:out")
            notables = len(store.get(s, "residents"))
            if n + notables != ledger:
                problems.append(f"{s}: {n} masses + {notables} notables != ledger {ledger}")
            for lo in catalogue.loci:
                copies = sum(col(allele_column(lo.id, v)) for v in lo.variants)
                if copies != 2 * n:
                    problems.append(f"{s}: {lo.id} has {copies} copies for {n} people")
        return problems
    return check
