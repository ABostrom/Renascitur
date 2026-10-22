"""Races: how a people lives and dies. World data (JSON), checked on load.

```json
{"id": "k:folk",
 "mortality": {"f": [0.05, 0.004, ...], "m": [...]},   // annual death probability per 5-year band, 20 bands
 "fertility": [0, 0, 0, 0.12, 0.25, ...],                // annual birth probability for a married woman, per band
 "fertile": [16, 45],                                     // a mother's ages, inclusive
 "spacing_days": 540,                                     // the shortest gap between a mother's births
 "marriage": [16, 50],                                    // ages at which one may marry (S3 #67)
 "twins": 0.012, "male": 0.51,                            // per birth
 "names": {"f": ["Ama", ...], "m": ["Bran", ...]}}
```

Bands are five years wide: band 0 is ages 0-4, band 19 is 95 and over. Draws happen each season,
so `quarterly(annual)` gives the per-season probability that compounds to the annual one.
"""

from __future__ import annotations

import json
from dataclasses import dataclass

from renasci.core.canon import canonical

BANDS = 20
BAND_YEARS = 5


def band(age_years: int) -> int:
    return min(max(age_years, 0) // BAND_YEARS, BANDS - 1)


def quarterly(annual: float) -> float:
    """The per-season probability that compounds to `annual` over four seasons."""
    return 1.0 - (1.0 - annual) ** 0.25


def _probabilities(label: str, values, n: int) -> tuple[float, ...]:
    if not isinstance(values, list) or len(values) != n:
        raise ValueError(f"{label} must list {n} probabilities")
    out = []
    for v in values:
        if isinstance(v, bool) or not isinstance(v, (int, float)) or not 0 <= v <= 1:
            raise ValueError(f"{label}: {v!r} is not a probability")
        out.append(float(v))
    return tuple(out)


def _age_range(label: str, r) -> tuple[int, int]:
    if not (isinstance(r, list) and len(r) == 2 and all(type(x) is int for x in r) and 0 <= r[0] <= r[1]):
        raise ValueError(f"{label} must be [min, max] ages")
    return r[0], r[1]


@dataclass(frozen=True)
class Race:
    id: str
    mortality: dict  # {"f": (20 probabilities), "m": (...)}
    fertility: tuple[float, ...]
    fertile: tuple[int, int]
    spacing_days: int
    marriage: tuple[int, int]
    twins: float
    male: float
    names: dict  # {"f": (...), "m": (...)}

    def __hash__(self):
        return hash(self.id)

    @classmethod
    def from_json(cls, data: dict) -> Race:
        data = json.loads(canonical(data))
        rid = data.get("id")
        if not isinstance(rid, str) or not rid:
            raise ValueError(f"a race needs an id, got {rid!r}")
        mortality = {sex: _probabilities(f"{rid} mortality {sex}", data.get("mortality", {}).get(sex), BANDS)
                     for sex in ("f", "m")}
        fertility = _probabilities(f"{rid} fertility", data.get("fertility"), BANDS)
        spacing = data.get("spacing_days", 0)
        if type(spacing) is not int or spacing < 0:
            raise ValueError(f"{rid} spacing_days must be a non-negative int")
        twins, male = (_probabilities(f"{rid} {k}", [data.get(k, d)], 1)[0] for k, d in (("twins", 0.0), ("male", 0.5)))
        names = {}
        for sex in ("f", "m"):
            pool = data.get("names", {}).get(sex)
            if not isinstance(pool, list) or not pool or not all(isinstance(n, str) and n for n in pool):
                raise ValueError(f"{rid} needs a non-empty list of {sex} names")
            names[sex] = tuple(pool)
        return cls(rid, mortality, fertility, _age_range(f"{rid} fertile", data.get("fertile")), spacing,
                   _age_range(f"{rid} marriage", data.get("marriage", [16, 60])), twins, male, names)


def age_years(calendar, born, today) -> int:
    """Whole years from `born` ([age, year, day], the year may be 0 or less: before the age's year 1)
    to `today`. Both must be in the same age (ages across an age boundary come with M7a)."""
    b_age, b_year, b_day = born
    if b_age != today.age:
        raise ValueError(f"born {born} is in another age than {today}; cross-age ages arrive with M7a")
    days = (today.year - b_year) * calendar.days_per_year + (today.day - b_day)
    return days // calendar.days_per_year


def days_since(calendar, then, today) -> int:
    t_age, t_year, t_day = then
    if t_age != today.age:
        raise ValueError(f"{then} is in another age than {today}")
    return (today.year - t_year) * calendar.days_per_year + (today.day - t_day)
