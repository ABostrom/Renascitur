"""The war-prone golden (S8 spec §12, Part B, #160): the Firebrand Empire and the draft Frontier Clans, 4A 1–40,
with beliefs and campaigns, over a fixed seed set. Wars emerge (never forced), each with a cause chain;
the map by year shows borders changing; a treaty is broken somewhere in the set; and each side's official
line on a war blames the other, so the two capitals disagree.

(A ripple on a commander's battle odds waits for commanders; the chronicles' disagreement for S12.)
"""

import pytest

from renasci import renascita
from renasci.analysis.truth import judge
from renasci.core.calendar import Span

SEEDS = (4, 5)
EMPIRE, CLANS = "v:firebrand-empire", "v:draft-frontier-clans"


@pytest.fixture(scope="module")
def runs():
    out = {}
    for seed in SEEDS:
        e = renascita.new_engine(seed=seed, polities="frontier", beliefs=True)
        e.run(until=renascita.CAL.add(renascita.START, Span(years=40)))
        out[seed] = e
    return out


def kinds(e, t):
    return [x for x in e.events if x.type == t]


def test_the_frontier_is_a_draft_merged_only_when_asked():
    sc = renascita._scenario(None, polities="frontier")
    assert {p["id"] for p in sc["polities"]} == {EMPIRE, CLANS}
    assert all(s.get("draft") for s in sc["settlements"] if s["id"].startswith("v:draft-"))
    assert sc["params"]["campaigns"] is True
    plain = renascita._scenario(None, polities=True)
    assert CLANS not in {p["id"] for p in plain["polities"]} and "campaigns" not in plain["params"]
    with pytest.raises(ValueError):
        renascita._scenario(None, polities="everyone")


def test_wars_emerge_in_every_seed_each_with_a_cause(runs):
    for seed, e in runs.items():
        declared = kinds(e, "polity.war_declared")
        assert declared, seed
        for d in declared:
            assert d.causes, (seed, d.id)  # (the relation's news, a council, a casus belli, a rising)


def test_the_map_by_year_shows_borders_changing(runs):
    for seed, e in runs.items():
        moved = [x for x in kinds(e, "geo.changed") if "control" in x.payload["change"]]
        assert moved, seed


def test_a_treaty_is_broken_somewhere_in_the_set(runs):
    assert any(kinds(e, "polity.treaty_broken") for e in runs.values())


def test_the_two_capitals_tell_the_war_differently(runs):
    for seed, e in runs.items():
        log = [x.to_json() for x in e.events]
        for d in kinds(e, "polity.war_declared"):
            war = d.payload["war"]
            told = {x.roles["polity"][0]: x.payload["claim"] for x in kinds(e, "polity.line")
                    if x.payload["claim"]["pred"] == "started" and x.payload["claim"]["args"]["war"] == war}
            if len(told) < 2:
                continue  # (a side that fell the day it was attacked tells nothing)
            a, b = sorted(told)
            assert told[a]["args"]["by"] == b and told[b]["args"]["by"] == a, (seed, war)
            verdicts = {judge(c, log)[0] for c in told.values()}
            assert verdicts == {"true", "false"}  # (one side tells the truth of it, the other doesn't)
            return
    raise AssertionError("no war in the set had both sides' lines")
