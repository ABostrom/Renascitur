"""Campaigns, battles and sieges (S8 spec §8, #122 Part B): in a world with `campaigns`, a war is fought a
season at a time. Each side raises an army (a number, from its strength) at its seat; attackers march on
the enemy's nearest town by the army's roads, defenders march to relieve it; armies that meet fight a
battle, and an army before an undefended town besieges it until it falls. Coarse steps keep the yearly
draw."""

import copy

import pytest

from renasci import renascita
from renasci.core.calendar import Span

CAL, START = renascita.CAL, renascita.START
EMPIRE, CLANS = "v:test-empire", "v:test-clans"
HOUSES = [h["id"] for h in renascita.SCENARIO["houses"]]


def scenario(campaigns=True, balanced=False):
    sc = copy.deepcopy(renascita.SCENARIO)
    sc["polities"] = [
        {"id": EMPIRE, "name": "the Empire", "seat": "v:lions-rest", "members": HOUSES[:9], "control": ["v:pyrosia"],
         "ruler": f"{HOUSES[0]}-head", "government": "ruler"},
        {"id": CLANS, "name": "the Clans", "seat": "v:raining-bay", "members": HOUSES[10:],
         "control": ["v:flame-coast"] + (["v:ember-peaks", "v:lux-oescus"] if balanced else []),
         "ruler": f"{HOUSES[10]}-head", "government": "ruler"}]
    sc["relations"] = [{"a": EMPIRE, "b": CLANS, "stance": "hostile", "trust": -1.0}]
    sc["params"]["campaigns"] = campaigns
    return sc


def run(seed, years=25, campaigns=True, balanced=False):
    e = renascita.new_engine(seed=seed, scenario=scenario(campaigns, balanced))
    e.run(until=CAL.add(START, Span(years=years)))
    return e


@pytest.fixture(scope="module")
def campaigned():
    for seed in (5, 6, 7, 8):
        e = run(seed)
        if any(x.type == "polity.battle" for x in e.events) or any(x.type == "polity.siege" for x in e.events):
            return e
    raise AssertionError("no battle or siege in a war between bitter enemies, on four seeds")


def kinds(e, t):
    return [x for x in e.events if x.type == t]


def test_a_war_raises_an_army_for_each_side_at_its_seat(campaigned):
    declared = kinds(campaigned, "polity.war_declared")[0]
    war = declared.payload["war"]
    first = next(x for x in kinds(campaigned, "polity.campaign") if x.payload["war"] == war)
    armies = first.payload["armies"]
    assert set(armies) == {EMPIRE, CLANS}
    for polity, a in armies.items():
        assert a["size"] > 0 and a["raised"] >= a["size"]


def test_a_campaigning_war_has_no_yearly_draw(campaigned):
    assert not kinds(campaigned, "polity.war_year")


@pytest.fixture(scope="module")
def balanced():
    for seed in (5, 6, 7, 8):
        e = run(seed, balanced=True)
        if kinds(e, "polity.battle"):
            return e
    raise AssertionError("no battle between well-matched enemies, on four seeds")


def test_a_hopeless_army_stays_behind_its_walls(campaigned):
    for s in kinds(campaigned, "polity.siege"):  # (the weak side's army, shut in, is part of the garrison)
        assert s.roles["held_by"][0] != s.roles["besieger"][0]


def test_battles_are_fought_where_armies_meet_and_cost_both_sides(balanced):
    campaigned = balanced
    assert kinds(campaigned, "polity.battle")
    for b in kinds(campaigned, "polity.battle"):
        losses = b.payload["losses"]
        (w,), (l,) = b.roles["winner"], b.roles["loser"]
        season = next(x for x in kinds(campaigned, "polity.campaign") if x.date == b.date and x.payload["war"] == b.payload["war"])
        size = {p: a["size"] for p, a in season.payload["armies"].items()}
        assert size[w] and size[l] and losses[l] / size[l] > losses[w] / size[w]  # (the loser bleeds more, for its size)
        assert season.payload["armies"][w]["at"] == season.payload["armies"][l]["at"] == b.payload["place"]


def test_a_siege_that_falls_hands_the_town_over(campaigned):
    fell = [s for s in kinds(campaigned, "polity.siege") if s.payload["outcome"] == "fell"]
    for s in fell:
        changed = [x for x in kinds(campaigned, "geo.changed") if x.date == s.date
                   and x.payload["change"].get("place") == s.payload["place"]]
        assert changed and changed[0].payload["change"]["control"] == s.roles["besieger"][0]
    held = [s for s in kinds(campaigned, "polity.siege") if s.payload["outcome"] == "held"]
    assert all(s.payload["seasons"] >= 1 for s in held)


def test_every_war_ends_or_is_still_being_fought(campaigned):
    for w in campaigned.store.ids("war"):
        if campaigned.store.get(w, "ended") is None:
            assert campaigned.store.get(w, "armies")


def test_campaigns_are_deterministic():
    a, b = run(5, years=12), run(5, years=12)
    sig = lambda e: [(x.date, x.type, x.payload.get("place")) for x in e.events if x.type.startswith("polity.")]
    assert sig(a) == sig(b)


def test_without_campaigns_a_war_is_the_yearly_draw():
    for seed in (5, 6, 7, 8):
        e = run(seed, years=25, campaigns=False)
        if kinds(e, "polity.war_declared"):
            assert kinds(e, "polity.war_year") and not kinds(e, "polity.campaign")
            return
    raise AssertionError("no war on four seeds")


def test_a_coarse_span_fights_by_the_yearly_draw_and_a_focus_window_by_seasons():
    from renasci.core.engine import Engine
    from renasci.core.lod import Resolution, ResolutionPolicy
    from renasci.people.scenario import synthesise
    from renasci.people.world import people_ruleset

    window = (CAL.add(START, Span(years=10)), CAL.add(START, Span(years=14, days=359)))
    policy = ResolutionPolicy(default=Resolution.coarse(Span(years=5)), focus=[window])
    seen = set()
    for seed in (6, 7):  # (6: a war in a coarse span; 7: one inside the window)
        sc = scenario()
        e = Engine(CAL, seed=seed, rulesets=[(START, people_ruleset("fourth_age", sc))], resolution=policy)
        synthesise(e, sc, seed)
        e.run(until=CAL.add(START, Span(years=24, days=359)))
        for x in kinds(e, "polity.battle") + kinds(e, "polity.siege"):  # (seasons only inside the window)
            assert window[0] <= x.date <= window[1], x.date
            seen.add("season")
        for x in kinds(e, "polity.war_year"):  # (the yearly draw only outside it)
            assert not (window[0] <= x.date <= window[1]), x.date
            seen.add("year")
    assert seen == {"season", "year"}
