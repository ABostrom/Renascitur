import pytest
from hypothesis import given
from hypothesis import strategies as st

from renasci.core.calendar import Age, AgeBoundaryError, Calendar, Date, Span

CAL = Calendar(ages=(Age(4, "4A", "Fourth Age"), Age(1, "1X", "Toy Age", last_year=300)))


def dates(age=4, max_year=500):
    return st.builds(
        Date,
        st.just(age),
        st.integers(min_value=1, max_value=max_year),
        st.integers(min_value=0, max_value=CAL.days_per_year - 1),
    )


# ---------------------------------------------------------------- ordering


def test_dates_order_by_age_then_year_then_day():
    assert Date(1, 900, 359) < Date(4, 1, 0)
    assert Date(4, 1, 359) < Date(4, 2, 0)
    assert Date(4, 2, 3) < Date(4, 2, 4)


@given(dates(), dates())
def test_ordering_matches_ordinal(a, b):
    assert (a < b) == (CAL.ordinal(a) < CAL.ordinal(b))


def test_date_rejects_day_outside_the_year():
    with pytest.raises(ValueError):
        CAL.check(Date(4, 1, 360))
    with pytest.raises(ValueError):
        CAL.check(Date(4, 0, 0))
    with pytest.raises(ValueError):
        CAL.check(Date(9, 1, 0))


# ---------------------------------------------------------------- arithmetic


@given(dates(), st.integers(min_value=0, max_value=5000))
def test_adding_days_moves_the_ordinal_by_that_many(d, n):
    assert CAL.ordinal(CAL.add(d, Span(days=n))) == CAL.ordinal(d) + n


@given(dates(), st.integers(min_value=0, max_value=200))
def test_adding_years_keeps_the_day_of_year(d, n):
    later = CAL.add(d, Span(years=n))
    assert (later.year, later.day) == (d.year + n, d.day)


@given(dates(), st.integers(0, 3000), st.integers(0, 3000))
def test_addition_is_monotonic(d, a, b):
    lo, hi = sorted((a, b))
    assert CAL.add(d, Span(days=lo)) <= CAL.add(d, Span(days=hi))


@given(dates(), dates())
def test_days_between_inverts_add(a, b):
    lo, hi = sorted((a, b))
    assert CAL.add(lo, Span(days=CAL.days_between(lo, hi))) == hi


def test_arithmetic_never_crosses_an_age_boundary():
    with pytest.raises(AgeBoundaryError):
        CAL.add(Date(1, 300, 359), Span(days=1))
    assert CAL.add(Date(1, 299, 359), Span(days=1)) == Date(1, 300, 0)


def test_spans_are_never_negative():
    with pytest.raises(ValueError):
        Span(days=-1)


# ---------------------------------------------------------------- months, seasons, ticks


def test_month_and_season_of_a_date():
    d = Date(4, 37, 75)  # day 75: month 3 (days 60-89), season 1 (days 0-89)
    assert CAL.month(d) == 2
    assert CAL.season(d) == 0
    assert CAL.season(Date(4, 37, 90)) == 1


def test_canonical_tick_is_age_year_season():
    assert CAL.canonical_tick(Date(4, 37, 89)) == (4, 37, 0)
    assert CAL.canonical_tick(Date(4, 37, 90)) == (4, 37, 1)
    assert CAL.canonical_tick(Date(4, 37, 359)) == (4, 37, 3)


@pytest.mark.parametrize(
    "unit, start, expected",
    [
        ("day", Date(4, 1, 5), Date(4, 1, 6)),
        ("month", Date(4, 1, 5), Date(4, 1, 30)),
        ("month", Date(4, 1, 30), Date(4, 1, 60)),
        ("season", Date(4, 1, 5), Date(4, 1, 90)),
        ("year", Date(4, 1, 5), Date(4, 2, 0)),
        ("year", Date(4, 1, 0), Date(4, 2, 0)),
    ],
)
def test_start_of_next(unit, start, expected):
    assert CAL.start_of_next(start, unit) == expected


def test_placeholder_names_are_configurable():
    cal = Calendar(
        ages=(Age(4, "4A", "Fourth Age"),),
        months=tuple((f"Moon {i}", 30) for i in range(1, 13)),
        seasons=(("Thaw", 90), ("Sun", 90), ("Ember", 90), ("Frost", 90)),
    )
    assert cal.format(Date(4, 37, 95), "season") == "4A 37 Sun"
    assert cal.month_name(Date(4, 37, 95)) == "Moon 4"


def test_month_and_season_lengths_must_fill_the_year():
    with pytest.raises(ValueError):
        Calendar(ages=(Age(4, "4A", "Fourth Age"),), months=(("Only", 30),))


# ---------------------------------------------------------------- formatting


@pytest.mark.parametrize(
    "style, text",
    [("year", "4A 37"), ("season", "4A 37 Spring"), ("day", "4A 37 m3 d16")],
)
def test_format(style, text):
    assert CAL.format(Date(4, 37, 75), style) == text


@given(dates())
def test_day_format_round_trips(d):
    assert CAL.parse(CAL.format(d, "day")) == d


def test_parse_year_only_means_first_day():
    assert CAL.parse("4A 37") == Date(4, 37, 0)
    assert CAL.parse("1X 120") == Date(1, 120, 0)


def test_parse_rejects_unknown_age():
    with pytest.raises(ValueError):
        CAL.parse("7Z 3")


@given(dates())
def test_json_round_trip(d):
    assert Date.from_json(d.to_json()) == d
    assert d.to_json() == [d.age, d.year, d.day]


# ---------------------------------------------------------------- review fixes


def test_start_of_next_rejects_unknown_units():
    for bad in ("months", "week", ""):
        with pytest.raises(ValueError):
            CAL.start_of_next(Date(4, 1, 5), bad)


@pytest.mark.parametrize("bad", [(4, 1.0, 2), (4, 1, 2.5), (True, 1, 0), ("4", 1, 0)])
def test_date_fields_must_be_exact_ints(bad):
    with pytest.raises(TypeError):
        Date(*bad)
    with pytest.raises(TypeError):
        Date.from_json(list(bad))


def test_canonical_tick_validates_the_date():
    with pytest.raises(ValueError):
        CAL.canonical_tick(Date(4, 1, -5))


def test_canonical_tick_is_fixed_quarters_not_the_season_table():
    # Renaming or resizing seasons (lore) must never change RNG keys.
    lopsided = Calendar(
        ages=(Age(4, "4A", "Fourth Age"),),
        seasons=(("Long", 200), ("Short", 160)),
    )
    for day in (0, 89, 90, 179, 180, 269, 270, 359):
        d = Date(4, 7, day)
        assert lopsided.canonical_tick(d) == CAL.canonical_tick(d) == (4, 7, day // 90)


@given(dates())
def test_year_and_season_formats_parse_to_their_first_day(d):
    assert CAL.parse(CAL.format(d, "year")) == Date(d.age, d.year, 0)
    season_start = Date(d.age, d.year, CAL.season(d) * 90)
    assert CAL.parse(CAL.format(d, "season")) == season_start


@pytest.mark.parametrize(
    "kwargs",
    [
        dict(ages=(Age(1, "1A", "a"), Age(1, "2A", "b"))),  # duplicate index
        dict(ages=(Age(1, "1A", "a"), Age(2, "1A", "b"))),  # duplicate abbrev
        dict(ages=(Age(1, "1 A", "a"),)),  # unparseable abbrev
        dict(ages=(Age(1, "1A", "a"),), months=(), seasons=()),  # empty year
        dict(ages=(Age(1, "1A", "a"),), months=(("a", 0), ("b", 360))),  # zero-length month
        dict(ages=()),  # no ages
    ],
)
def test_bad_calendar_config_is_rejected(kwargs):
    with pytest.raises(ValueError):
        Calendar(**kwargs)
