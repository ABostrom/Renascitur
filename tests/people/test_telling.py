"""Telling, trust, drift, lies, correction and decay (S6 spec §6, #87)."""

import sys
from pathlib import Path

import pytest

from renasci.core.calendar import Span
from renasci.people import beliefs as B

sys.path.insert(0, str(Path(__file__).parent))
from test_beliefs import CAL, SEEN, START, emit_probe_event, engine, scenario, two_adults  # noqa: E402


def test_a_telling_is_believed_by_trust_and_traces_to_the_tellers_belief():
    def go(ctx):
        _, a, b, people = two_adults(ctx)
        ev = emit_probe_event(ctx, a)
        c = B.claim("killed", victim=people[2], by=b)
        B.hold(ctx, a, c, 0.9, ev.id)
        SEEN["took"] = B.tell(ctx, a, b, c, trust=0.7)
        SEEN.update(a=a, b=b, key=B.key(c), a_from=ctx.get(a, "beliefs")[B.key(c)]["from"],
                    heard=ctx.get(b, "beliefs")[B.key(c)])

    e = engine([(Span(days=1), go)])
    e.run(until=CAL.add(START, Span(days=3)))
    assert SEEN["took"] and SEEN["heard"]["conf"] == round(0.9 * 0.7, 3)
    told = next(ev for ev in e.events if ev.type == "belief.told")
    assert told.roles["teller"] == (SEEN["a"],) and told.payload["intent"] == "honest"
    assert any(c.kind == "event" and c.ref == SEEN["a_from"] for c in told.causes)


def test_a_lie_is_told_with_intent_and_the_hearer_cannot_tell():
    def go(ctx):
        _, a, b, people = two_adults(ctx)
        ev = emit_probe_event(ctx, a)
        c = B.claim("fault", event=ev.id, party="the ward-keeper")
        SEEN["took"] = B.tell(ctx, a, b, c, trust=0.8, conf=0.9, intent="lie", cause=ev.id)
        SEEN["heard"] = ctx.get(b, "beliefs")[B.key(c)]

    e = engine([(Span(days=1), go)])
    e.run(until=CAL.add(START, Span(days=3)))
    told = next(ev for ev in e.events if ev.type == "belief.told")
    assert SEEN["took"] and told.payload["intent"] == "lie"
    assert set(SEEN["heard"]) == {"claim", "conf", "since", "from", "heard"}  # (nothing about it being a lie)


def test_correction_overturns_a_firm_lie():
    def go(ctx):
        _, a, b, people = two_adults(ctx)
        ev = emit_probe_event(ctx, a)
        lie, truth_ = B.claim("killed", victim=people[2], by="a wasting illness"), B.claim("killed", victim=people[2], by=b)
        B.hold(ctx, a, lie, 0.95, ev.id)
        SEEN["told"] = B.hold(ctx, a, truth_, 0.6, ev.id)  # (rejected: the lie is firmer)
        SEEN["corrected"] = B.correct(ctx, a, truth_, ev.id)
        SEEN["beliefs"], SEEN["keys"] = ctx.get(a, "beliefs"), (B.key(lie), B.key(truth_))

    e = engine([(Span(days=1), go)])
    e.run(until=CAL.add(START, Span(days=3)))
    lie, truth_ = SEEN["keys"]
    assert SEEN["told"] is False and SEEN["corrected"]
    assert lie not in SEEN["beliefs"] and SEEN["beliefs"][truth_]["conf"] >= B.CORRECTION_CONF
    assert any(ev.type == "belief.corrected" for ev in e.events)


def test_a_killing_drifts_to_the_killers_house_and_keeps_its_lineage():
    def go(ctx):
        home = next(s for s in ctx.ids("settlement"))
        housed = next(p for p in ctx.ids("person", "active") if ctx.get(p, "house"))
        c = B.claim("killed", victim="p:x", by=housed)
        SEEN["drift"] = B.drift(ctx, c)
        SEEN["house"] = ctx.get(housed, "house")
        SEEN["cover"] = B.drift(ctx, B.claim("killed", victim="p:x", by="a wasting illness"))

    e = engine([(Span(days=1), go)])
    e.run(until=CAL.add(START, Span(days=3)))
    assert SEEN["drift"] == B.claim("killed", victim="p:x", by=SEEN["house"])
    assert SEEN["cover"] is None  # (an illness has no house to blame)


def test_decay_fades_what_nobody_repeats_one_step_a_year_and_drops_it_in_the_end():
    c = B.claim("killed", victim="p:1", by="p:2")
    beliefs = {B.key(c): {"claim": c, "conf": 0.45, "since": [4, 1, 0], "from": "x", "heard": [4, 1, 0]}}
    assert B.decayed(beliefs, today=[4, 5, 0])[B.key(c)]["conf"] == 0.45  # (within decay_years)
    year, seen = 12, []
    while beliefs:  # a yearly pass, applied year after year, takes one step each time
        beliefs = B.decayed(beliefs, today=[4, year, 0])
        seen.append(beliefs[B.key(c)]["conf"] if beliefs else None)
        year += 1
    assert seen == [0.35, 0.25, 0.15, None]


def run_gossip(years=3, seed=5, **params):
    sc = scenario()
    sc["params"] = {**sc["params"], **params}

    def seed_beliefs(ctx):  # every notable of the first settlement perceives something worth repeating
        home = ctx.ids("settlement")[0]
        people = [p for p in ctx.get(home, "residents") if ctx.status(p) == "active"]
        ev = emit_probe_event(ctx, people[0])
        for i, p in enumerate(people[:12]):
            B.hold(ctx, p, B.claim("killed", victim=people[-1 - i], by=people[i]), 0.9, ev.id)
        SEEN["home"] = home

    e = engine([(Span(days=1), seed_beliefs)], sc=sc, seed=seed)
    e.run(until=CAL.add(START, Span(years=years)))
    return e


def test_gossip_spreads_beliefs_among_co_residents_within_its_budget():
    e = run_gossip()
    told = [ev for ev in e.events if ev.type == "belief.told"]
    assert told
    by_season: dict = {}
    for ev in told:
        assert ev.place  # (where it was told: the settlement both live in)
        by_season[(ev.place, ev.date)] = by_season.get((ev.place, ev.date), 0) + 1
    assert max(by_season.values()) <= B.SETTLEMENT_TELLS


def test_every_belief_walks_back_to_where_it_began():
    e = run_gossip()
    by_id = {ev.id: ev for ev in e.events}
    checked = 0
    for p in e.store.ids("person"):
        for b in (e.store.get(p, "beliefs") or {}).values():
            ev = by_id[b["from"]]
            for _ in range(500):
                if ev.type != "belief.told":
                    break
                told_from = [c.ref for c in ev.causes if c.kind == "event"]
                assert len(told_from) == 1  # (a telling has exactly one source: the teller's belief)
                ev = by_id[told_from[0]]
            assert ev.type in ("belief.perceived", "belief.corrected"), ev.type
            checked += by_id[b["from"]].type == "belief.told"
    assert checked > 0  # (gossip made believers of people who never saw it)


def test_without_the_beliefs_param_nobody_gossips():
    e = engine([(Span(days=1), lambda ctx: None)], sc=scenario(beliefs=False))
    e.run(until=CAL.add(START, Span(years=2)))
    assert not any(ev.type.startswith("belief.") for ev in e.events)


def test_correction_never_lowers_a_firmer_belief():
    def go(ctx):
        _, a, b, people = two_adults(ctx)
        ev = emit_probe_event(ctx, a)
        c, rival = B.claim("killed", victim=people[2], by=b), B.claim("killed", victim=people[2], by=a)
        B.hold(ctx, a, c, 0.95, ev.id)
        B.hold(ctx, a, rival, 0.96, ev.id)  # (firmer: c halves to 0.475)
        B.correct(ctx, a, c, ev.id)
        SEEN["conf"] = ctx.get(a, "beliefs")[B.key(c)]["conf"]

    e = engine([(Span(days=1), go)])
    e.run(until=CAL.add(START, Span(days=3)))
    assert SEEN["conf"] >= 0.96


def test_a_belief_everyone_keeps_repeating_does_not_fade():
    e = run_gossip(years=14)
    faded_only = []
    for p in e.store.ids("person"):
        for b in (e.store.get(p, "beliefs") or {}).values():
            faded_only.append(b["heard"][1])
    assert any(e.events and y > 1 for y in faded_only)  # (re-hearing refreshed some beliefs past year 1)
    assert any(ev.type == "belief.reinforced" for ev in e.events)
