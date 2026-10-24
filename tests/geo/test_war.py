"""War, coarse (S8 spec §5, Part A, #122): declared between hostile polities by their governments, allies
called, a yearly draw by strength that hands border places to the winner (the map by year shows it),
exhaustion and a peace sealed by a truce, or a polity that falls with its seat."""

import copy

import pytest

from renasci import renascita
from renasci.analysis.mapyear import geography_at
from renasci.core.calendar import Span

CAL, START = renascita.CAL, renascita.START
EMPIRE, CLANS, EMBER = "v:test-empire", "v:test-clans", "v:test-ember"
HOUSES = [h["id"] for h in renascita.SCENARIO["houses"]]


def scenario(relations=(), treaties=(), ember=False):
    sc = copy.deepcopy(renascita.SCENARIO)
    sc["polities"] = [
        {"id": EMPIRE, "name": "the Empire", "seat": "v:lions-rest", "members": HOUSES[:9], "control": ["v:pyrosia"],
         "ruler": f"{HOUSES[0]}-head", "government": "ruler"},
        {"id": CLANS, "name": "the Clans", "seat": "v:raining-bay", "members": HOUSES[10:], "control": ["v:flame-coast"],
         "ruler": f"{HOUSES[10]}-head", "government": "ruler"}]
    if ember:
        sc["polities"].append({"id": EMBER, "name": "the Ember Holds", "seat": "v:old-westgate", "members": [HOUSES[9]],
                               "control": ["v:ember-peaks"], "ruler": f"{HOUSES[9]}-head", "government": "ruler"})
    sc["relations"], sc["treaties"] = list(relations), list(treaties)
    return sc


ENEMIES = [{"a": EMPIRE, "b": CLANS, "stance": "hostile", "trust": -1.0}]


def run(sc, years, seed=5):
    e = renascita.new_engine(seed=seed, scenario=sc)
    e.run(until=CAL.add(START, Span(years=years)))
    return e


@pytest.fixture(scope="module")
def warred():
    for seed in (5, 6, 7, 8):
        e = run(scenario(ENEMIES), 30, seed)
        if any(ev.type == "polity.war_declared" for ev in e.events):
            return e
    raise AssertionError("no war between bitter enemies in 30 years, on four seeds")


def test_enemies_go_to_war(warred):
    declared = next(ev for ev in warred.events if ev.type == "polity.war_declared")
    war = declared.payload["war"]
    assert set(declared.roles["aggressor"]) | set(declared.roles["defender"]) == {EMPIRE, CLANS}
    assert warred.store.get(war, "started") == declared.date.to_json()
    assert any(ev.type == "polity.stance" and ev.payload["to"] == "war" for ev in warred.events)


def test_a_war_year_hands_border_places_to_the_winner_and_the_map_shows_it(warred):
    years = [ev for ev in warred.events if ev.type == "polity.war_year"]
    assert years
    taken = [ev for ev in years if ev.payload.get("place")]
    assert taken, "no place changed hands in the whole war"
    ev = taken[0]
    place, winner = ev.payload["place"], ev.roles["winner"][0]
    geo = warred.ruleset.params.get("geography") or renascita._scenario(scenario(ENEMIES))["geography"]
    from renasci import polities

    doc = polities.annotate(geo, scenario(ENEMIES))
    rows = [d.to_json() for d in warred.store.deltas]
    after = next(p for p in geography_at(doc, rows, ev.date)["places"] if p["id"] == place)
    assert after["control"] == winner


def test_a_war_ends_in_a_truce_or_a_fallen_polity(warred):
    ended = [ev for ev in warred.events if ev.type in ("polity.peace", "polity.fallen")]
    if not ended:  # (still at war at the end: exhaustion builds, though)
        war = next(ev for ev in warred.events if ev.type == "polity.war_declared").payload["war"]
        assert any(v > 0 for v in warred.store.get(war, "exhaustion").values())
        return
    if ended[0].type == "polity.peace":
        assert any(ev.type == "polity.treaty" and ev.payload["kind"] == "truce" and ev.date == ended[0].date
                   for ev in warred.events)


def test_an_ally_is_called_and_joins_or_betrays():
    for seed in (5, 6, 7, 8, 9, 10):
        e = run(scenario(ENEMIES, [{"kind": "alliance", "a": CLANS, "b": EMBER, "years": 40}], ember=True), 30, seed)
        declared = [ev for ev in e.events if ev.type == "polity.war_declared" and CLANS in ev.roles["defender"]]
        if declared:
            calls = [ev for ev in e.events if ev.type in ("polity.joined", "polity.treaty_broken")
                     and EMBER in (ev.roles.get("ally", ()) + ev.roles.get("by", ()))]
            assert calls, "the ally was never called"
            return
    pytest.skip("the Empire never attacked the Clans in these seeds")


def test_a_world_without_polities_has_no_war():
    e = renascita.new_engine(seed=5)
    e.run(until=CAL.add(START, Span(years=2)))
    assert not [ev for ev in e.events if ev.type.startswith("polity.war")]


def test_after_any_war_no_relation_is_left_at_war_and_the_fallen_are_inert():
    for seed in (5, 6, 7, 8):
        e = run(scenario(ENEMIES, [{"kind": "alliance", "a": CLANS, "b": EMBER, "years": 40}], ember=True), 30, seed)
        live = {ev.payload["war"] for ev in e.events if ev.type == "polity.war_declared"} - {
            w for w in e.store.ids("war") if e.store.get(w, "ended") is not None}
        at_war = {frozenset((e.store.get(w, "attackers")[0], e.store.get(w, "defenders")[0])) for w in live}
        for rid in e.store.ids("relation"):
            if e.store.get(rid, "stance") == "war":
                pair = {e.store.get(rid, "a"), e.store.get(rid, "b")}
                assert any(pair & set(e.store.get(w, "attackers")) and pair & set(e.store.get(w, "defenders"))
                           for w in live), f"{rid} at war with no live war (seed {seed})"
        fallen = {ev.roles["polity"][0]: ev.date for ev in e.events if ev.type == "polity.fallen"}
        for ev in e.events:
            if ev.type == "polity.war_declared":
                for p, when in fallen.items():
                    assert not (p in ev.roles["aggressor"] + ev.roles["defender"] and ev.date > when), \
                        f"{p} fell, then went to war (seed {seed})"
        del at_war
