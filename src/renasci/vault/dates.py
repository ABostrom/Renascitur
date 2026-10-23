"""Dates in the vault (S2 spec §5): age-relative, vague, or the timeline plugin's absolute years.

Every date becomes a **window** `(first day, last day)` in the engine's calendar:

```
date   := exact | range | circa
exact  := AGE YEAR [ "m" MONTH "d" DAY ]        4A 123 (the whole year), 4A 123 m3 d12 (that day)
range  := AGE YEAR ".." YEAR                    4A 120..140
circa  := "~" AGE YEAR                           ~4A 120: ± circa_years (default 5)
```

An integer is an **absolute** timeline year (the timeline plugin's `aat-event-start-date`), placed in an
age through the `AgeTable` (each age's first absolute year: `vault.toml`'s `[ages]`, or an era note's own
start date). Windows are clamped to their age, with a note saying so. A date that can't be read, or falls
in an age the calendar doesn't have, gives no window and a reason.
"""

from __future__ import annotations

import re

from renasci.core.calendar import Date

RANGE = re.compile(r"^(\S+)\s+(\d+)\s*\.\.\s*(\d+)$")
CIRCA = re.compile(r"^~\s*(\S+)\s+(\d+)$")
YEAR = re.compile(r"^(\S+)\s+(\d+)$")


class AgeTable:
    """Each age's first absolute timeline year, by abbreviation (`{"4A": 12001}`)."""

    def __init__(self, starts: dict[str, int]):
        self.starts = dict(starts)

    def place(self, absolute: int, calendar) -> tuple[str, int] | None:
        """(age abbreviation, year in that age) for an absolute year, or None."""
        best = None
        for abbrev, first in self.starts.items():
            if first <= absolute and (best is None or first > best[1]):
                best = (abbrev, first)
        if best is None:
            return None
        age = next((a for a in calendar.ages if a.abbrev == best[0]), None)
        year = absolute - best[1] + 1
        if age is None or (age.last_year is not None and year > age.last_year):
            return None
        return best[0], year


def _age(calendar, abbrev: str):
    return next((a for a in calendar.ages if a.abbrev == abbrev), None)


def _year_window(calendar, age, lo: int, hi: int) -> tuple[tuple[Date, Date], str | None]:
    top = age.last_year if age.last_year is not None else max(hi, 1)
    clamped_lo, clamped_hi = max(lo, 1), min(hi, top)
    note = None if (clamped_lo, clamped_hi) == (lo, hi) else f"clamped to {age.abbrev} {clamped_lo}..{clamped_hi}"
    return (Date(age.index, clamped_lo, 0), Date(age.index, clamped_hi, calendar.days_per_year - 1)), note


def parse_date(value, calendar, ages: AgeTable, circa_years: int = 5):
    """((first, last) or None, a problem or None). A clamped window comes with a problem saying so."""
    if isinstance(value, bool) or value is None:
        return None, f"not a date: {value!r}"
    if isinstance(value, int):
        placed = ages.place(value, calendar)
        if placed is None:
            return None, f"timeline year {value} is in no age the calendar has (vault.toml [ages])"
        value = f"{placed[0]} {placed[1]}"
    text = str(value).strip()
    for pattern, kind in ((RANGE, "range"), (CIRCA, "circa"), (YEAR, "year")):
        m = pattern.match(text)
        if not m:
            continue
        age = _age(calendar, m.group(1))
        if age is None:
            return None, f"{m.group(1)!r} is not an age of this calendar"
        if kind == "range":
            lo, hi = int(m.group(2)), int(m.group(3))
            if lo > hi:
                return None, f"{text!r}: the range runs backwards"
        elif kind == "circa":
            lo, hi = int(m.group(2)) - circa_years, int(m.group(2)) + circa_years
        else:
            lo = hi = int(m.group(2))
        window, note = _year_window(calendar, age, lo, hi)
        if window[0] > window[1]:
            return None, f"{text!r} is outside {age.abbrev}"
        return window, note
    try:  # a day: "4A 12 m3 d5"
        d = calendar.parse(text)
    except ValueError as err:
        return None, f"not a date: {text!r} ({err})"
    return (d, d), None
