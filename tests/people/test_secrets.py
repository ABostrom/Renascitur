"""Secret events: kept, leaked, exposed (S6 spec §5, #89)."""

import sys
from pathlib import Path

import pytest

from renasci.core.calendar import Span
from renasci.people import actions as A
from renasci.people import beliefs as B

sys.path.insert(0, str(Path(__file__).parent))
from test_beliefs import CAL, SEEN, START, engine, scenario, two_adults  # noqa: E402


def poison(ctx):
    home, a, b, people = two_adults(ctx)
    SEEN["outcome"] = A.perform(ctx, A.ACTIONS["Poison"], a, b, odds=1.0)
    SEEN.update(a=a, b=b, home=home, truth=B.key(B.claim("killed", victim=b, by=a)),
                cover=B.key(B.claim("killed", victim=b, by="a wasting illness")))


def holders(e, key):
    return sorted(p for p in e.store.ids("person") if key in (e.store.get(p, "beliefs") or {}))


def test_a_secret_truth_is_marked_secret_and_stays_with_those_who_know(monkeypatch):
    monkeypatch.setattr(B, "LEAK_ACTOR", 0.0)
    monkeypatch.setattr(B, "LEAK_ACCOMPLICE", 0.0)
    e = engine([(Span(days=1), poison)])
    e.run(until=CAL.add(START, Span(years=3)))
    if SEEN["outcome"] != "success":
        pytest.skip("this seed didn't poison")
    assert e.store.get(SEEN["a"], "beliefs")[SEEN["truth"]].get("secret") is True
    assert holders(e, SEEN["truth"]) == [SEEN["a"]]  # three years of gossip, and nobody else knows
    assert holders(e, SEEN["cover"])  # while the cover spreads


def poison_by_a_spouse(ctx):  # a poisoner with someone at home to let it slip to
    home, _, b, people = two_adults(ctx)
    married = [p for p in people if ctx.get(p, "spouse") in people and p != b and ctx.get(p, "spouse") != b]
    a = max(married, key=lambda p: (ctx.get(p, "born"), p))  # (the youngest: alive to let it slip)
    SEEN["outcome"] = A.perform(ctx, A.ACTIONS["Poison"], a, b, odds=1.0)
    SEEN.update(a=a, b=b, home=home, truth=B.key(B.claim("killed", victim=b, by=a)))


def test_a_secret_leaks_and_the_one_told_holds_it_openly(monkeypatch):
    monkeypatch.setattr(B, "LEAK_ACTOR", 1.0)
    e = engine([(Span(days=1), poison_by_a_spouse)])
    e.run(until=CAL.add(START, Span(days=200)))  # (the first seasons' gossip: before age takes anyone)
    if SEEN["outcome"] != "success":
        pytest.skip("this seed didn't poison")
    leaks = [ev for ev in e.events if ev.type == "belief.told" and ev.payload["intent"] == "leak"]
    assert leaks
    hearer = leaks[0].roles["holder"][0]
    assert leaks[0].roles["teller"] == (SEEN["a"],)
    assert not (e.store.get(hearer, "beliefs") or {}).get(SEEN["truth"], {}).get("secret")


def test_exposing_a_schemer_reveals_the_killings_they_hid():
    def expose(ctx):
        ev = ctx.emit("people.action", {"actor": (SEEN["a"],)}, purpose="probe-exposed", actor=SEEN["a"],
                      payload={"action": "Probe", "outcome": "exposed"})
        SEEN["revealed"] = B.reveal(ctx, SEEN["a"], ev.id, SEEN["home"])

    e = engine([(Span(days=1), poison), (Span(days=40), expose)])
    e.run(until=CAL.add(START, Span(days=60)))
    if SEEN["outcome"] != "success":
        pytest.skip("this seed didn't poison")
    assert SEEN["revealed"] == [SEEN["truth"]]
    knew = holders(e, SEEN["truth"])
    assert len(knew) > 1
    for p in knew:
        assert SEEN["cover"] not in (e.store.get(p, "beliefs") or {})  # (corrected: the cover is gone)
    assert any(ev.type == "belief.corrected" for ev in e.events)


def test_a_hidden_killing_is_not_forgotten_while_it_stays_hidden():
    c = B.claim("killed", victim="p:1", by="p:2")
    beliefs = {B.key(c): {"claim": c, "conf": 0.9, "since": [4, 1, 0], "from": "x", "heard": [4, 1, 0], "secret": True}}
    assert B.decayed(beliefs, today=[4, 60, 0]) == beliefs


def test_revealing_clears_the_secret_for_an_accomplice_who_already_knew():
    def go(ctx):
        home, a, b, people = two_adults(ctx)
        ev = ctx.emit("people.action", {"actor": (a,)}, purpose="probe", actor=a,
                      payload={"action": "Probe", "outcome": "success"}, visibility="secret")
        c = B.claim("killed", victim=b, by=a)
        B.hold(ctx, a, c, 0.9, ev.id, secret=True)
        B.hold(ctx, people[2], c, 0.9, ev.id, secret=True)  # (an accomplice)
        out = ctx.emit("people.action", {"actor": (a,)}, purpose="probe-exposed", actor=a,
                       payload={"action": "Probe", "outcome": "exposed"})
        B.correct(ctx, people[2], c, out.id)
        SEEN.update(acc=people[2], key=B.key(c))

    e = engine([(Span(days=1), go)])
    e.run(until=CAL.add(START, Span(days=3)))
    assert not e.store.get(SEEN["acc"], "beliefs")[SEEN["key"]].get("secret")
