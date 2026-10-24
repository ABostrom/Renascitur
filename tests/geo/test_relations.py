"""Relations between polities and factions (S8 spec §4, #121): sparse relations cast for neighbours and a
polity's factions (or seeded); a ledger of what happens across the line (a killing); yearly drift into a
stance, with border incidents between cold or hostile neighbours."""

import copy

import pytest

from renasci import kin, polities, renascita
from renasci.core.calendar import Date, Span
from renasci.core.engine import Engine
from renasci.core.systems import Ruleset, System
from renasci.people import life
from renasci.people.scenario import synthesise
from renasci.people.world import people_ruleset
from renasci.relations import rel_id

CAL, START = renascita.CAL, renascita.START
EMPIRE, CLANS = "v:test-empire", "v:test-clans"
HOUSES = [h["id"] for h in renascita.SCENARIO["houses"]]


def scenario(relations=()):
    sc = copy.deepcopy(renascita.SCENARIO)
    sc["polities"] = [
        {"id": EMPIRE, "name": "the Empire", "seat": "v:lions-rest", "members": HOUSES[:10], "control": ["v:pyrosia"]},
        {"id": CLANS, "name": "the Clans", "seat": "v:raining-bay", "members": HOUSES[10:], "control": ["v:flame-coast"]}]
    sc["factions"] = [{"id": "v:bloc-a", "name": "A", "polity": EMPIRE, "members": HOUSES[:3]},
                      {"id": "v:bloc-b", "name": "B", "polity": EMPIRE, "members": HOUSES[3:6]}]
    sc["relations"] = list(relations)
    return sc


def run(sc, years):
    e = renascita.new_engine(seed=5, scenario=sc)
    e.run(until=CAL.add(START, Span(years=years)))
    return e


def test_neighbours_and_a_realms_factions_start_with_relations():
    e = renascita.new_engine(seed=5, scenario=scenario())
    rid = rel_id(EMPIRE, CLANS)
    assert e.store.get(rid, "stance") == "neutral" and e.store.get(rid, "kind") == "polity"
    assert e.store.get(rel_id("v:bloc-a", "v:bloc-b"), "kind") == "faction"
    assert sorted(e.store.ids("relation")) == sorted([rid, rel_id("v:bloc-a", "v:bloc-b")])


def test_old_enemies_see_border_incidents_and_friends_dont():
    hostile = run(scenario([{"a": EMPIRE, "b": CLANS, "stance": "hostile", "trust": -0.9}]), 6)
    incidents = [ev for ev in hostile.events if ev.type == "polity.incident"]
    assert incidents and all(set(ev.roles["party"]) == {EMPIRE, CLANS} for ev in incidents)
    assert hostile.store.get(rel_id(EMPIRE, CLANS), "trust") < 0
    friendly = run(scenario([{"a": EMPIRE, "b": CLANS, "stance": "friendly", "trust": 0.3}]), 6)
    assert not [ev for ev in friendly.events if ev.type == "polity.incident"]
    assert friendly.store.get(rel_id(EMPIRE, CLANS), "trust") > 0.1  # (trade along the open border keeps it warm)


def test_trade_alone_never_makes_allies_and_quiet_years_settle():
    e = run(scenario(), 40)
    rid = rel_id(EMPIRE, CLANS)
    assert e.store.get(rid, "stance") in ("neutral", "cold", "hostile") or [
        ev for ev in e.events if ev.type == "people.marriage"]  # (friendship is earned: a marriage, a treaty)
    assert e.store.get(rid, "trust") < 0.25 or e.store.get(rid, "stance") != "neutral"
    drifts = [ev for ev in e.events if ev.type == "polity.drift" and ev.payload["relation"] == rid]
    assert len(drifts) < 40  # (not one every year: a quiet relation settles)


def test_a_seeded_stance_brings_its_trust_and_a_raid_doesnt_warm_it():
    e = run(scenario([{"a": EMPIRE, "b": CLANS, "stance": "hostile"}]), 1)
    assert e.store.get(rel_id(EMPIRE, CLANS), "stance") == "hostile"
    assert "bad_relation" in {f["kind"] for f in polities.check(scenario([{"a": EMPIRE, "b": CLANS, "stance": "friendly",
                                                                           "trust": -0.5}]))}
    assert "bad_relation" in {f["kind"] for f in polities.check(scenario([{"a": EMPIRE, "b": CLANS},
                                                                          {"a": CLANS, "b": EMPIRE}]))}
    lone = copy.deepcopy(renascita.SCENARIO)
    lone["relations"] = [{"a": "x", "b": "y"}]
    assert "bad_relation" in {f["kind"] for f in polities.check(lone)}


@pytest.mark.parametrize("bad", [{"a": EMPIRE, "b": EMPIRE}, {"a": EMPIRE, "b": "v:bloc-a"},
                                 {"a": EMPIRE, "b": CLANS, "trust": 3}, {"a": EMPIRE, "b": CLANS, "stance": "smitten"}])
def test_bad_relations_are_refused(bad):
    assert "bad_relation" in {f["kind"] for f in polities.check(scenario([bad]))}


# ---------------------------------------------------------------- the ledger, on the kin world

REALMS = [
    {"id": "t:Hollowmark", "name": "Hollowmark", "seat": "t:Hollow-1", "members": ["t:House-Hollow"], "control": ["t:Hollow"]},
    {"id": "t:Ridgeland", "name": "Ridgeland", "seat": "t:Ridge-1", "members": ["t:House-Ridge", "t:House-Mere"],
     "control": ["t:Ridge", "t:Mere"]}]


class Feud(System):
    """(A test system: in the first year, three of House Ridge are killed by a man of House Hollow.)"""

    name, cadence, priority = "test.feud", "yearly", -10
    reads = life.DIE_READS | frozenset({"ids:person", "place"})
    writes = life.DIE_WRITES
    event_types = life.DIE_EVENTS

    def run(self, ctx):
        if ctx.today.year != 1:
            return
        people = [p for p in ctx.ids("person") if ctx.status(p) == "active"]
        killer = next(p for p in people if ctx.get(p, "house") == "t:House-Hollow")
        victims = [p for p in people if ctx.get(p, "house") == "t:House-Ridge" and not ctx.get(p, "offices")][:3]
        for v in victims:
            life.die(ctx, v, ctx.get(v, "place"), "murdered", killer=killer)


def test_killings_across_the_line_fill_the_ledger_and_turn_the_stance():
    sc = kin.scenario()
    sc["polities"] = copy.deepcopy(REALMS)
    rs = people_ruleset("kin", sc)
    e = Engine(kin.CAL, seed=3, rulesets=[(kin.START, Ruleset(rs.name, rs.version, (*rs.systems, Feud()), params=rs.params,
                                                             forcers=rs.forcers, disguises=rs.disguises,
                                                             conservation=rs.conservation))])
    synthesise(e, sc, 3)
    e.run(until=Date(1, 1, 359))
    rid = rel_id("t:Hollowmark", "t:Ridgeland")
    assert e.store.exists(rid)  # (made on first contact: they share no road)
    assert e.store.get(rid, "trust") == pytest.approx(-0.45) and e.store.get(rid, "stance") == "cold"
    turned = [ev for ev in e.events if ev.type == "polity.stance"]
    assert turned and {c.ref for c in turned[0].causes} >= {ev.id for ev in e.events if ev.type == "people.death"
                                                            and ev.roles.get("killer")}


def test_a_world_without_polities_has_no_relations():
    e = kin.new_engine(seed=3)
    e.run(until=Date(1, 2, 0))
    assert not e.store.ids("relation") and not [ev for ev in e.events if ev.type.startswith("polity.")]


# ---------------------------------------------------------------- treaties (part 2)

def ruled(relations=(), treaties=(), government="advised"):
    sc = scenario(relations)
    sc["polities"][0].update(ruler=f"{HOUSES[0]}-head", government=government)
    sc["polities"][1].update(ruler=f"{HOUSES[10]}-head", government="ruler")
    sc["treaties"] = list(treaties)
    return sc


def test_friends_sign_a_trade_treaty_after_the_council_advises():
    e = run(ruled([{"a": EMPIRE, "b": CLANS, "stance": "friendly"}]), 10)
    signed = [ev for ev in e.events if ev.type == "polity.treaty"]
    assert signed and signed[0].payload["kind"] in ("trade", "alliance")
    tid = signed[0].payload["treaty"]
    assert tid in e.store.get(rel_id(EMPIRE, CLANS), "treaties") or e.store.get(tid, "ended") is not None
    advice = [ev for ev in e.events if ev.type == "polity.council" and ev.payload["polity"] == EMPIRE]
    assert advice and len(advice[0].roles["adviser"]) >= 2  # (the Empire's member heads)
    assert any(c.ref == advice[0].id for c in signed[0].causes) or any(
        any(c.ref == a.id for c in signed[0].causes) for a in advice)


def test_a_seeded_truce_ends_at_its_expiry():
    e = run(ruled(treaties=[{"kind": "truce", "a": EMPIRE, "b": CLANS, "years": 2}]), 4)
    ended = [ev for ev in e.events if ev.type == "polity.treaty_ended"]
    assert ended and ended[0].date.year == START.year + 2
    assert not e.store.get(rel_id(EMPIRE, CLANS), "treaties")


def test_a_soured_pact_is_broken_and_the_betrayal_costs_trust():
    e = run(ruled([{"a": EMPIRE, "b": CLANS, "stance": "hostile", "trust": -0.9}],
                  [{"kind": "alliance", "a": EMPIRE, "b": CLANS, "years": 30}]), 10)
    broken = [ev for ev in e.events if ev.type == "polity.treaty_broken"]
    assert broken, "nobody broke a pact between enemies in ten years"
    tid = broken[0].payload["treaty"]
    assert e.store.get(tid, "broken_by") == broken[0].roles["by"][0]
    drift = next(ev for ev in e.events if ev.type == "polity.drift" and ev.date >= broken[0].date)
    assert any(c.ref == broken[0].id for c in drift.causes)  # (the betrayal is in that year's ledger)


@pytest.mark.parametrize("bad", [{"kind": "marriage-of-convenience", "a": EMPIRE, "b": CLANS},
                                 {"kind": "truce", "a": EMPIRE, "b": EMPIRE}, {"kind": "truce", "a": EMPIRE, "b": CLANS, "years": 0}])
def test_bad_treaties_are_refused(bad):
    assert "bad_treaty" in {f["kind"] for f in polities.check(ruled(treaties=[bad]))}


def test_a_truce_isnt_soured_by_hostility_only_war_breaks_it():
    e = run(ruled([{"a": EMPIRE, "b": CLANS, "stance": "hostile", "trust": -1.0}],
                  [{"kind": "truce", "a": EMPIRE, "b": CLANS, "years": 30}]), 8)
    assert not [ev for ev in e.events if ev.type == "polity.treaty_broken"]


def test_a_treaty_outlasting_the_age_lasts_the_age_and_ids_never_collide():
    from renasci import treaties
    from renasci.core.calendar import Date

    assert treaties._expires(CAL, Date(4, 250, 0), 20) is None
    assert treaties._expires(CAL, Date(4, 5, 0), 20) == [4, 25, 0]
    taken = {"tr:truce:a|b:1.0", "tr:truce:a|b:1.0:2"}
    assert treaties.tid("truce", "b", "a", "1.0", taken.__contains__) == "tr:truce:a|b:1.0:3"
    assert "bad_treaty" in {f["kind"] for f in polities.check(ruled(treaties=[
        {"kind": "trade", "a": EMPIRE, "b": CLANS}, {"kind": "trade", "a": CLANS, "b": EMPIRE}]))}
    assert "bad_treaty" in {f["kind"] for f in polities.check(ruled(treaties=[{"kind": "trade", "a": [EMPIRE], "b": CLANS}]))}
