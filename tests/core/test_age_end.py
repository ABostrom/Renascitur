"""Nothing can happen past an age's last day: what's due then falls away, and the run still ends (#164)."""

from renasci.core.calendar import Age, AgeBoundaryError, Calendar, Date, Span
from renasci.core.engine import Engine
from renasci.core.systems import Ruleset, System
from renasci.people import travel

CAL = Calendar(ages=(Age(1, "1X", "Test", last_year=3),))


class Late(System):
    name, cadence, priority = "test.late", "yearly", 1
    reads, writes, event_types = frozenset(), frozenset(), ()

    def run(self, ctx):
        ctx.schedule(Span(years=3), "late", entity="t:late")

    def handle(self, ctx, activation):
        raise AssertionError("past the age's end")


def test_a_follow_up_past_the_age_falls_away_and_the_run_finishes():
    e = Engine(CAL, 1, [(Date(1, 1, 0), Ruleset("late", 1, (Late(),)))])
    e.run(until=Date(1, 3, CAL.days_per_year - 1))
    assert e.scheduler.peek() is None


def test_a_journey_that_would_end_past_the_age_is_not_begun(monkeypatch):
    class Calendar_:
        def add(self, today, span):
            raise AgeBoundaryError("past the end")

    class Ctx:
        calendar, today = Calendar_(), Date(1, 3, 350)

        def get(self, entity, name):
            return {"place": "here"}.get(name)

        def emit(self, *a, **kw):
            raise AssertionError("no journey to emit")

    monkeypatch.setattr(travel.geo, "path", lambda *a: (30, ["here", "there"]))
    assert travel.depart(Ctx(), "p", "there", "test") is None
