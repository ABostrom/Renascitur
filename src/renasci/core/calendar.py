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

    def __post_init__(self):
        # Exact ints only: 37.0 or True would hash differently from 37 inside RNG keys.
        for name in ("age", "year", "day"):
            value = getattr(self, name)
            if type(value) is not int:
                raise TypeError(f"Date.{name} must be an int, got {value!r}")

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
        if not self.ages:
            raise ValueError("a calendar needs at least one age")
        if len({a.index for a in self.ages}) != len(self.ages):
            raise ValueError("age indexes must be unique")
        if len({a.abbrev for a in self.ages}) != len(self.ages):
            raise ValueError("age abbreviations must be unique")
        if any(not a.abbrev or any(c.isspace() for c in a.abbrev) for a in self.ages):
            raise ValueError("age abbreviations must be non-empty with no whitespace")
        if not self.months or not self.seasons:
            raise ValueError("a calendar needs months and seasons")
        if any(n <= 0 for _, n in self.months + self.seasons):
            raise ValueError("month and season lengths must be positive")
        dpy = sum(n for _, n in self.months)
        if sum(n for _, n in self.seasons) != dpy:
            raise ValueError("month and season lengths must fill the same year")
        object.__setattr__(self, "_by_index", {a.index: a for a in self.ages})
        object.__setattr__(self, "_by_abbrev", {a.abbrev: a for a in self.ages})
        object.__setattr__(self, "_days_per_year", sum(n for _, n in self.months))  # read on every date sum

    @property
    def days_per_year(self) -> int:
        return self._days_per_year

    # ------------------------------------------------------------ JSON (run manifests, the Observatory)

    def to_json(self) -> dict:
        return {"ages": [{"index": a.index, "abbrev": a.abbrev, "name": a.name, "last_year": a.last_year}
                         for a in self.ages],
                "months": [[n, d] for n, d in self.months], "seasons": [[n, d] for n, d in self.seasons]}

    @classmethod
    def from_json(cls, data: dict) -> "Calendar":
        return cls(ages=tuple(Age(a["index"], a["abbrev"], a["name"], a["last_year"]) for a in data["ages"]),
                   months=tuple((n, d) for n, d in data["months"]), seasons=tuple((n, d) for n, d in data["seasons"]))

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
        """The first day of the next `unit`. Raises AgeBoundaryError past the age's last year;
        the scheduler treats that as the end of the run for that cadence."""
        if unit not in UNITS:
            raise ValueError(f"unknown unit {unit!r}; expected one of {UNITS}")
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
        """The coarse time key for randomness: (age, year, quarter).

        Quarters are fixed fractions of the year, not the named seasons, so renaming or resizing
        seasons in a setting never changes RNG keys.
        """
        self.check(d)
        return (d.age, d.year, d.day * 4 // self.days_per_year)

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

    _PATTERN = re.compile(r"^(\S+) ([0-9]+)(?: m([0-9]+) d([0-9]+)| (.+))?$")  # ASCII digits, like the JS port

    def parse(self, text: str) -> Date:
        """Parse any `format` style. Year and season forms give the first day of that period."""
        match = self._PATTERN.match(text.strip())
        if not match:
            raise ValueError(f"cannot parse date {text!r}")
        abbrev, year, month, day, season = match.groups()
        age = self._by_abbrev.get(abbrev)
        if age is None:
            raise ValueError(f"unknown age {abbrev!r}")
        doy = 0
        if season is not None:
            names = [name for name, _ in self.seasons]
            if season not in names:
                raise ValueError(f"unknown season {season!r} in {text!r}")
            doy = self._starts(self.seasons)[names.index(season)]
        elif month is not None:
            m, dom = int(month) - 1, int(day) - 1
            if not (0 <= m < len(self.months) and 0 <= dom < self.months[m][1]):
                raise ValueError(f"no such day in the calendar: {text!r}")
            doy = self._starts(self.months)[m] + dom
        return self.check(Date(age.index, int(year), doy))
