"""Age-relative dates on a configurable calendar.

A date is (age, year, day-of-year). Ages are independent eras ("4A 37"); arithmetic never crosses
from one age into another. Month and season names are placeholders until a setting supplies them.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

UNITS = ("day", "month", "season", "year")


class AgeBoundaryError(ValueError):
    """Date arithmetic tried to run past the end of an age."""


@dataclass(frozen=True, order=True)
class Date:
    age: int
    year: int  # 1-based
    day: int  # 0-based day of year

    def to_json(self) -> list[int]:
        return [self.age, self.year, self.day]

    @classmethod
    def from_json(cls, data: list[int]) -> Date:
        age, year, day = data
        return cls(age, year, day)


@dataclass(frozen=True)
class Span:
    years: int = 0
    days: int = 0

    def __post_init__(self):
        if self.years < 0 or self.days < 0:
            raise ValueError(f"spans are never negative: {self}")


@dataclass(frozen=True)
class Age:
    index: int
    abbrev: str  # "4A"
    name: str  # "Fourth Age"
    last_year: int | None = None  # None: open-ended


DEFAULT_MONTHS = tuple((f"Month {i}", 30) for i in range(1, 13))
DEFAULT_SEASONS = (("Spring", 90), ("Summer", 90), ("Autumn", 90), ("Winter", 90))


@dataclass(frozen=True)
class Calendar:
    ages: tuple[Age, ...]
    months: tuple[tuple[str, int], ...] = DEFAULT_MONTHS
    seasons: tuple[tuple[str, int], ...] = DEFAULT_SEASONS
    _by_index: dict[int, Age] = field(init=False, repr=False, compare=False)
    _by_abbrev: dict[str, Age] = field(init=False, repr=False, compare=False)

    def __post_init__(self):
        dpy = sum(n for _, n in self.months)
        if sum(n for _, n in self.seasons) != dpy:
            raise ValueError("month and season lengths must fill the same year")
        object.__setattr__(self, "_by_index", {a.index: a for a in self.ages})
        object.__setattr__(self, "_by_abbrev", {a.abbrev: a for a in self.ages})

    @property
    def days_per_year(self) -> int:
        return sum(n for _, n in self.months)

    # ------------------------------------------------------------ validation

    def check(self, d: Date) -> Date:
        age = self._by_index.get(d.age)
        if age is None:
            raise ValueError(f"unknown age {d.age}")
        if d.year < 1 or not 0 <= d.day < self.days_per_year:
            raise ValueError(f"date out of range: {d}")
        if age.last_year is not None and d.year > age.last_year:
            raise AgeBoundaryError(f"{d} is past the end of {age.name} ({age.last_year})")
        return d

    # ------------------------------------------------------------ arithmetic

    def ordinal(self, d: Date) -> int:
        """Days since the start of the date's age."""
        return (d.year - 1) * self.days_per_year + d.day

    def from_ordinal(self, age: int, n: int) -> Date:
        year, day = divmod(n, self.days_per_year)
        return self.check(Date(age, year + 1, day))

    def add(self, d: Date, span: Span) -> Date:
        self.check(d)
        moved = Date(d.age, d.year + span.years, d.day)
        return self.from_ordinal(d.age, self.ordinal(moved) + span.days)

    def days_between(self, a: Date, b: Date) -> int:
        if a.age != b.age:
            raise AgeBoundaryError("days_between needs two dates in the same age")
        return self.ordinal(b) - self.ordinal(a)

    def start_of_next(self, d: Date, unit: str) -> Date:
        if unit == "day":
            return self.add(d, Span(days=1))
        if unit == "year":
            return self.check(Date(d.age, d.year + 1, 0))
        bounds = self._starts(self.months if unit == "month" else self.seasons)
        for start in bounds:
            if start > d.day:
                return Date(d.age, d.year, start)
        return self.check(Date(d.age, d.year + 1, 0))

    # ------------------------------------------------------------ parts of a year

    @staticmethod
    def _starts(parts) -> list[int]:
        starts, total = [], 0
        for _, n in parts:
            starts.append(total)
            total += n
        return starts

    @staticmethod
    def _index(parts, day: int) -> int:
        total = 0
        for i, (_, n) in enumerate(parts):
            total += n
            if day < total:
                return i
        raise ValueError(f"day {day} outside the year")

    def month(self, d: Date) -> int:
        return self._index(self.months, d.day)

    def season(self, d: Date) -> int:
        return self._index(self.seasons, d.day)

    def month_name(self, d: Date) -> str:
        return self.months[self.month(d)][0]

    def season_name(self, d: Date) -> str:
        return self.seasons[self.season(d)][0]

    def canonical_tick(self, d: Date) -> tuple[int, int, int]:
        """The coarse time key for randomness: (age, year, season)."""
        return (d.age, d.year, self.season(d))

    # ------------------------------------------------------------ text

    def format(self, d: Date, style: str = "year") -> str:
        head = f"{self._by_index[d.age].abbrev} {d.year}"
        if style == "year":
            return head
        if style == "season":
            return f"{head} {self.season_name(d)}"
        if style == "day":
            m = self.month(d)
            day_of_month = d.day - self._starts(self.months)[m]
            return f"{head} m{m + 1} d{day_of_month + 1}"
        raise ValueError(f"unknown format style {style!r}")

    _PATTERN = re.compile(r"^(\S+) (\d+)(?: m(\d+) d(\d+))?$")

    def parse(self, text: str) -> Date:
        match = self._PATTERN.match(text.strip())
        if not match:
            raise ValueError(f"cannot parse date {text!r}")
        abbrev, year, month, day = match.groups()
        age = self._by_abbrev.get(abbrev)
        if age is None:
            raise ValueError(f"unknown age {abbrev!r}")
        doy = 0
        if month is not None:
            m, dom = int(month) - 1, int(day) - 1
            if not (0 <= m < len(self.months) and 0 <= dom < self.months[m][1]):
                raise ValueError(f"no such day in the calendar: {text!r}")
            doy = self._starts(self.months)[m] + dom
        return self.check(Date(age.index, int(year), doy))
