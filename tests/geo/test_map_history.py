"""The map by year (S4 spec §8, #81): a geography's dated `changes` (a road built or closed, a place
changing hands) happen on their dates in the run, and the map as of any date is rebuilt from the run."""

import copy

import pytest

from renasci import geo, renascita
from renasci.analysis.mapyear import geography_at
from renasci.core.calendar import Date, Span

CAL, START = renascita.CAL, renascita.START
DOC = renascita.SCENARIO["geography"]
ROUTE = DOC["routes"][0]["id"]
TOWN = next(p["id"] for p in DOC["places"] if p["kind"] == "settlement")
OTHER = next(r["id"] for r in DOC["regions"] if r["id"] != next(p["region"] for p in DOC["places"] if p["id"] == TOWN))
A, B = sorted(p["id"] for p in DOC["places"] if p["kind"] == "settlement")[:2]


def at(years, days=0):
    return CAL.add(START, Span(years=years, days=days)).to_json()


CHANGES = [
    {"date": at(1, 40), "route": ROUTE, "open": False, "why": "a landslide"},
    {"date": at(2, 10), "build": {"id": "g:new-road", "ends": [A, B], "days": 1, "kind": "road"}, "why": "a new road"},
    {"date": at(2, 200), "place": TOWN, "region": OTHER, "why": "a border moves"},
    {"date": at(3), "route": ROUTE, "open": True, "days": 9, "why": "reopened, the long way round"},
]


@pytest.fixture(scope="module")
def run():
    sc = copy.deepcopy(renascita.SCENARIO)
    sc["geography"] = {**copy.deepcopy(DOC), "changes": CHANGES}
    e = renascita.new_engine(seed=3, scenario=sc)
    e.run(until=CAL.add(START, Span(years=4)))
    return e, sc["geography"]


def test_each_change_happens_on_its_date(run):
    e, _ = run
    changed = [ev for ev in e.events if ev.type == "geo.changed"]
    assert [ev.date.to_json() for ev in changed] == [c["date"] for c in CHANGES]
    assert [ev.payload["why"] for ev in changed] == [c["why"] for c in CHANGES]
    assert e.store.get(ROUTE, "open") is True and e.store.get(ROUTE, "days") == 9
    assert e.store.get("g:new-road", "ends") == [A, B]
    assert e.store.get(TOWN, "region") == OTHER


def test_the_map_as_of_any_date_is_rebuilt_from_the_run(run):
    e, doc = run
    rows = _deltas(e)
    before = geography_at(doc, rows, Date.from_json(at(1)))
    closed = geography_at(doc, rows, Date.from_json(at(2)))
    built = geography_at(doc, rows, Date.from_json(at(2, 100)))
    moved = geography_at(doc, rows, Date.from_json(at(3, 5)))
    assert route(before, ROUTE).get("open", True) is True and route(before, "g:new-road") == {}
    assert route(closed, ROUTE)["open"] is False
    assert route(built, "g:new-road")["ends"] == [A, B]
    assert place(built, TOWN)["region"] != OTHER and place(moved, TOWN)["region"] == OTHER
    assert route(moved, ROUTE)["days"] == 9 and route(moved, ROUTE)["open"] is True
    assert "changes" not in moved  # (a map, not its plan)
    assert not geo.check({k: v for k, v in moved.items()})


def route(g, rid):
    return next((r for r in g["routes"] if r["id"] == rid), None) or {}


def place(g, pid):
    return next(p for p in g["places"] if p["id"] == pid)


def _deltas(e):
    """The run's state deltas as the run folder keeps them (the test reads them off the engine)."""
    return [d.to_json() for d in e.store.deltas]


def test_changes_on_one_day_happen_in_the_lists_order_and_none_causes_another():
    sc = copy.deepcopy(renascita.SCENARIO)
    day = at(1, 45)
    sc["geography"] = {**copy.deepcopy(DOC), "changes": [
        {"date": at(1), "route": ROUTE, "days": 4, "why": "first"},  # (on a season's first day: applied directly)
        {"date": day, "build": {"id": "g:x", "ends": [A, B], "days": 2, "kind": "road"}, "why": "built"},
        {"date": day, "route": "g:x", "open": False, "why": "and closed at once"}]}
    e = renascita.new_engine(seed=3, scenario=sc)
    e.run(until=CAL.add(START, Span(years=2)))
    changed = [ev for ev in e.events if ev.type == "geo.changed"]
    assert [ev.payload["why"] for ev in changed] == ["first", "built", "and closed at once"]
    assert e.store.get("g:x", "open") is False
    first = changed[0].id
    assert not any(c.kind == "event" and c.ref == first for ev in changed[1:] for c in ev.causes)


def test_a_change_to_a_road_before_it_is_built_is_a_finding():
    early = {"date": at(1), "route": "g:x", "open": False}
    build = {"date": at(2), "build": {"id": "g:x", "ends": [A, B], "days": 2, "kind": "road"}}
    assert any(f["kind"] == "bad_change" for f in geo.check({**DOC, "changes": [build, early]}))
    assert not geo.check({**DOC, "changes": [early | {"date": at(3)}, build]})


def test_the_ages_last_season_runs():
    from renasci.core.calendar import Date

    age = next(a for a in CAL.ages if a.index == START.age)
    last = CAL.add(Date(START.age, age.last_year, 0), Span(days=CAL.days_per_year - 10))
    sc = copy.deepcopy(renascita.SCENARIO)
    sc["geography"] = {**copy.deepcopy(DOC), "changes": [{"date": at(1), "route": ROUTE, "days": 4}]}
    rs = renascita.ruleset(sc)
    mh = next(s for s in rs.systems if s.name == "geo.map")
    calls = []

    class Ctx:
        calendar, today, params = CAL, last, rs.params

        def schedule(self, *a, **k):
            calls.append(a)

    mh.run(Ctx())  # (no change pending, and no crash past the age's end)
    assert calls == []


@pytest.mark.parametrize("bad, kind", [
    ({"date": "soon", "route": ROUTE, "open": False}, "bad_change"),
    ({"date": at(1), "route": "g:nowhere", "open": False}, "bad_change"),
    ({"date": at(1), "route": ROUTE}, "bad_change"),
    ({"date": at(1), "place": TOWN, "region": "g:atlantis"}, "bad_change"),
    ({"date": at(1), "build": {"id": "g:x", "ends": [A, "t:nowhere"], "days": 1, "kind": "road"}}, "bad_change"),
])
def test_a_bad_change_is_a_finding(bad, kind):
    assert any(f["kind"] == kind for f in geo.check({**DOC, "changes": [bad]}))
