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
