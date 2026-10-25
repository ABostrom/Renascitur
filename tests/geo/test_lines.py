"""Official lines (S8 spec §9, #158): each side's account of a war or a broken treaty (`started`, `won`,
`betrayed`), spread through its own settlements' talk, and judged true or false against the log."""

import copy

import pytest

from renasci import renascita
from renasci.analysis.truth import judge
from renasci.core.calendar import Span
from renasci.people import beliefs

CAL, START = renascita.CAL, renascita.START
EMPIRE, CLANS = "v:test-empire", "v:test-clans"
HOUSES = [h["id"] for h in renascita.SCENARIO["houses"]]


def scenario(believing=True):
    sc = copy.deepcopy(renascita.SCENARIO)
    sc["polities"] = [
        {"id": EMPIRE, "name": "the Empire", "seat": "v:lions-rest", "members": HOUSES[:9], "control": ["v:pyrosia"],
         "ruler": f"{HOUSES[0]}-head", "government": "ruler"},
        {"id": CLANS, "name": "the Clans", "seat": "v:raining-bay", "members": HOUSES[10:], "control": ["v:flame-coast"],
         "ruler": f"{HOUSES[10]}-head", "government": "ruler"}]
    sc["relations"] = [{"a": EMPIRE, "b": CLANS, "stance": "hostile", "trust": -1.0}]
    sc["params"]["beliefs"] = believing
    return sc


def test_the_new_predicates():
    c = beliefs.claim("started", war="war:x", by=EMPIRE)
    assert beliefs.topic(c) == "started:war:x"
    assert beliefs.topic(beliefs.claim("won", war="war:x", by=CLANS)) == "won:war:x"
    assert beliefs.topic(beliefs.claim("betrayed", treaty="tr:1", by=CLANS)) == "betrayed:tr:1"
    with pytest.raises(ValueError):
        beliefs.claim("started", war="war:x")


def ev(i, type_, roles, payload):
    return {"id": i, "type": type_, "roles": roles, "payload": payload, "causes": []}


def test_the_log_judges_who_started_won_and_betrayed():
    log = [ev("e1", "polity.war_declared", {"aggressor": [EMPIRE], "defender": [CLANS]}, {"war": "war:x"}),
           ev("e2", "polity.peace", {"winner": [CLANS], "loser": [EMPIRE]}, {"war": "war:x"}),
           ev("e3", "polity.treaty_broken", {"by": [CLANS], "party": [CLANS, EMPIRE]}, {"treaty": "tr:1"}),
           ev("e0", "polity.war_declared", {"aggressor": [EMPIRE], "defender": [CLANS]}, {"war": "war:y"}),
           ev("e4", "polity.fallen", {"polity": [CLANS], "victor": [EMPIRE]}, {"war": "war:y"})]
    assert judge(beliefs.claim("started", war="war:x", by=EMPIRE), log) == ("true", ["e1"])
    assert judge(beliefs.claim("started", war="war:x", by=CLANS), log) == ("false", ["e1"])
    assert judge(beliefs.claim("won", war="war:x", by=EMPIRE), log) == ("false", ["e2"])
    assert judge(beliefs.claim("won", war="war:y", by=EMPIRE), log) == ("true", ["e4"])
    assert judge(beliefs.claim("betrayed", treaty="tr:1", by=CLANS), log) == ("true", ["e3"])
    assert judge(beliefs.claim("won", war="war:z", by=EMPIRE), log) == ("unknown", [])


def test_an_allys_fall_doesnt_decide_who_won():
    log = [ev("e1", "polity.war_declared", {"aggressor": [EMPIRE], "defender": [CLANS]}, {"war": "war:x"}),
           ev("e2", "polity.fallen", {"polity": ["v:ally"], "victor": [EMPIRE]}, {"war": "war:x"}),
           ev("e3", "polity.peace", {"winner": [CLANS], "loser": [EMPIRE]}, {"war": "war:x"})]
    assert judge(beliefs.claim("won", war="war:x", by=CLANS), log) == ("true", ["e3"])


@pytest.fixture(scope="module")
def warred():
    for seed in (5, 6, 7, 8):
        e = renascita.new_engine(seed=seed, scenario=scenario())
        e.run(until=CAL.add(START, Span(years=25)))
        if any(x.type == "polity.war_declared" for x in e.events):
            return e
    raise AssertionError("no war between bitter enemies, on four seeds")


def test_each_side_blames_the_other_for_the_war(warred):
    declared = next(x for x in warred.events if x.type == "polity.war_declared")
    war, (agg,), (dfn,) = declared.payload["war"], declared.roles["aggressor"], declared.roles["defender"]
    lines = {x.roles["polity"][0]: x for x in warred.events if x.type == "polity.line"
             and x.payload["claim"]["pred"] == "started" and x.payload["claim"]["args"]["war"] == war}
    assert lines[agg].payload["claim"]["args"]["by"] == dfn  # (the aggressor's line: they provoked it)
    assert lines[dfn].payload["claim"]["args"]["by"] == agg
    assert ("event", declared.id) in {(c.kind, c.ref) for c in lines[agg].causes}


def test_a_line_is_told_in_its_own_towns_and_held_by_its_ruler(warred):
    line = next(x for x in warred.events if x.type == "polity.line")
    (polity,) = line.roles["polity"]
    c = line.payload["claim"]
    k = beliefs.key(c)
    told = [x for x in warred.events if x.type == "belief.perceived" and x.payload["key"] == k
            and ("event", line.id) in {(cc.kind, cc.ref) for cc in x.causes}]
    assert told  # (the ruler took it on)
    towns = [s for s in warred.store.ids("settlement") if warred.store.get(s, "control") == polity]
    assert towns


def test_a_world_without_beliefs_has_no_lines():
    e = renascita.new_engine(seed=5, scenario=scenario(believing=False))
    e.run(until=CAL.add(START, Span(years=10)))
    assert not [x for x in e.events if x.type == "polity.line"]
