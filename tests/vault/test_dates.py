"""Dates in the vault (S2 spec §5): the age table, exact and vague forms, absolute timeline years."""

import pytest

from renasci.core.calendar import Date
from renasci.renascita import CAL
from renasci.vault.dates import AgeTable, parse_date

LAST = CAL.days_per_year - 1


@pytest.mark.parametrize("text,lo,hi", [
    ("4A 123", (4, 123, 0), (4, 123, LAST)),
    ("4A 120..140", (4, 120, 0), (4, 140, LAST)),
    ("~4A 120", (4, 115, 0), (4, 125, LAST)),
    ("4A 3", (4, 3, 0), (4, 3, LAST)),
])
def test_written_dates_become_windows(text, lo, hi):
    window, problem = parse_date(text, CAL, AgeTable({}))
    assert problem is None and window == (Date(*lo), Date(*hi))


def test_a_day_is_a_one_day_window():
    window, _ = parse_date("4A 12 m3 d5", CAL, AgeTable({}))
    assert window[0] == window[1] == CAL.parse("4A 12 m3 d5")


def test_circa_is_clamped_to_its_age_with_a_problem():
    window, problem = parse_date("~4A 3", CAL, AgeTable({}))
    assert window == (Date(4, 1, 0), Date(4, 8, LAST)) and "clamped" in problem


def test_absolute_timeline_years_go_through_the_age_table():
    table = AgeTable({"4A": 12001})
    window, problem = parse_date(12010, CAL, table)
    assert problem is None and window == (Date(4, 10, 0), Date(4, 10, LAST))
    window, problem = parse_date(9000, CAL, table)
    assert window is None and "age" in problem


@pytest.mark.parametrize("text", ["4A", "4A 120..", "~", "fourth age", "9Z 3", "4A 140..120"])
def test_unreadable_dates_are_problems(text):
    window, problem = parse_date(text, CAL, AgeTable({}))
    assert window is None and problem
