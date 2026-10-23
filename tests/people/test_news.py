"""News along routes (S6 spec §7, #79): travellers tell on arrival; widely held claims travel by road."""

import sys
from pathlib import Path

from renasci import renascita
from renasci.core.calendar import Span
from renasci.people import beliefs as B
from renasci.people import travel

sys.path.insert(0, str(Path(__file__).parent))
import test_travel as T  # noqa: E402

START, CAL = renascita.START, renascita.CAL
IDS = [s["id"] for s in renascita.SCENARIO["settlements"]]


def test_a_traveller_tells_what_they_believe_where_they_arrive():
    def go(ctx):
        p = T.traveller(ctx, IDS[0])
        days = travel.depart(ctx, p, IDS[1], "test")
        dep = ctx._engine.events[-1].id  # (the departure, to explain the belief)
        c = B.claim("killed", victim="p:x", by="p:y")
        B.hold(ctx, p, c, 0.9, dep)
        T.SEEN.update(person=p, key=B.key(c), days=days)

    e, _ = T.engine(T.scenario(beliefs=True), [(Span(days=1), go)])
    e.run(until=CAL.add(START, Span(days=10)))
    told = [ev for ev in e.events if ev.type == "belief.told" and ev.roles["teller"] == (T.SEEN["person"],)]
    assert told and all(ev.place == IDS[1] for ev in told)
    hearers = [ev.roles["holder"][0] for ev in told]
    assert all(e.store.get(h, "place") == IDS[1] for h in hearers)


def test_widely_held_news_travels_each_road_once_at_the_roads_speed():
    def spread(ctx):  # everyone in the first settlement comes to believe the same thing
        dep = ctx.emit("people.depart", {"traveller": (T.traveller(ctx, IDS[0]),), "origin": (IDS[0],),
                                         "destination": (IDS[1],)}, purpose="probe", actor=IDS[0],
                       payload={"days": 0, "why": "probe"})
        c = B.claim("killed", victim="p:x", by="p:y")
        for p in ctx.get(IDS[0], "residents"):
            if ctx.status(p) == "active":
                B.hold(ctx, p, c, 1.0, dep.id)
        T.SEEN["key"] = B.key(c)

    e, _ = T.engine(T.scenario(beliefs=True), [(Span(days=1), spread)])
    e.run(until=CAL.add(START, Span(years=2)))
    out = [ev for ev in e.events if ev.type == "belief.news" and ev.payload["key"] == T.SEEN["key"]]
    arrived = [ev for ev in e.events if ev.type == "belief.news_arrived" and ev.payload["key"] == T.SEEN["key"]]
    assert out and arrived
    first = out[0]
    assert first.roles["settlement"] == (IDS[0],) and first.payload["to"] == IDS[1]
    landed = next(ev for ev in arrived if ev.roles["settlement"] == (IDS[1],))
    assert landed.date == CAL.add(first.date, Span(days=3))  # the road's days
    assert len([ev for ev in out if ev.roles["settlement"] == (IDS[0],) and ev.payload["to"] == IDS[1]]) == 1
    assert T.SEEN["key"] in (e.store.get(IDS[1], "shares") or {})
    assert T.SEEN["key"] in e.store.get(IDS[0], "news_sent")


def test_the_vialux_carries_the_official_line_and_wild_roads_drift_more():
    assert B.news_drift(vialux=True) == 0.0
    assert B.news_drift(vialux=False) == 2 * B.DRIFT_RATE
    assert B.news_trust(vialux=True) > B.news_trust(vialux=False)


def test_without_routes_no_news_travels():
    sc = T.scenario(beliefs=True)
    sc.pop("geography")
    e, _ = T.engine(sc, [(Span(days=1), lambda ctx: None)])
    e.run(until=CAL.add(START, Span(years=1)))
    assert not any(ev.type.startswith("belief.news") for ev in e.events)


def with_waypoint():
    """Settlements 0 and 1 joined only through a tavern (2 + 3 days, Vialux then road); the rest as before."""
    sc = T.scenario(beliefs=True)
    g = sc["geography"]
    g["places"].append({"id": "g:tavern", "kind": "tavern", "region": g["places"][0]["region"]})
    g["routes"] = [r for r in g["routes"] if set(r["ends"]) != {IDS[0], IDS[1]}]
    g["routes"] += [{"id": "g:to-tavern", "ends": [IDS[0], "g:tavern"], "days": 2, "kind": "road", "vialux": True},
                    {"id": "g:from-tavern", "ends": ["g:tavern", IDS[1]], "days": 3, "kind": "road"}]
    return sc


def test_news_passes_through_a_waypoint_to_the_next_settlement():
    def spread(ctx):
        dep = ctx.emit("people.depart", {"traveller": (T.traveller(ctx, IDS[0]),), "origin": (IDS[0],),
                                         "destination": (IDS[1],)}, purpose="probe", actor=IDS[0],
                       payload={"days": 0, "why": "probe"})
        c = B.claim("killed", victim="p:x", by="p:y")
        for p in ctx.get(IDS[0], "residents"):
            if ctx.status(p) == "active":
                B.hold(ctx, p, c, 1.0, dep.id)
        T.SEEN["key"] = B.key(c)

    e, _ = T.engine(with_waypoint(), [(Span(days=1), spread)])
    e.run(until=CAL.add(START, Span(years=2)))  # (it used to crash: news landed at the tavern)
    out = [ev for ev in e.events if ev.type == "belief.news" and ev.payload["to"] == IDS[1]]
    landed = [ev for ev in e.events if ev.type == "belief.news_arrived" and ev.roles["settlement"] == (IDS[1],)]
    assert out and landed and not out[0].payload["vialux"]  # (one leg off the Vialux: not the official line)
    assert landed[0].date == CAL.add(out[0].date, Span(days=5))
    assert e.store.get("g:tavern", "shares") is None


def test_the_nearest_settlements_by_road_through_waypoints():
    def look(ctx):
        T.SEEN["near"] = B.neighbour_settlements(ctx, IDS[0])

    e, _ = T.engine(with_waypoint(), [(Span(days=1), look)])
    e.run(until=CAL.add(START, Span(days=3)))
    assert T.SEEN["near"] == [(IDS[1], 5, False)]
