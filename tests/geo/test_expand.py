"""Expand and Raid (S8 spec §9, #158): a ruler who wants a neighbour's border places raids across the line,
souring the relation, and their ambition is a casus belli that makes war likelier."""

import copy

from renasci import renascita, war
from renasci.core.calendar import Date, Span
from renasci.core.systems import Ruleset, System
from renasci.people import actions as A
from renasci.people import houses, travel
from renasci.people.actions import ACTIONS, perform
from renasci.people.ambitions import LIBRARY
from renasci.people.planner import holds
from renasci.relations import rel_id

CAL, START = renascita.CAL, renascita.START
EMPIRE, CLANS = "v:test-empire", "v:test-clans"
HOUSES = [h["id"] for h in renascita.SCENARIO["houses"]]
REL = rel_id(EMPIRE, CLANS)


def scenario(stance="cold", trust=-0.4):
    sc = copy.deepcopy(renascita.SCENARIO)
    sc["polities"] = [
        {"id": EMPIRE, "name": "the Empire", "seat": "v:lions-rest", "members": HOUSES[:9], "control": ["v:pyrosia"],
         "ruler": f"{HOUSES[0]}-head", "government": "ruler"},
        {"id": CLANS, "name": "the Clans", "seat": "v:raining-bay", "members": HOUSES[10:], "control": ["v:flame-coast"],
         "ruler": f"{HOUSES[10]}-head", "government": "ruler"}]
    sc["relations"] = [{"a": EMPIRE, "b": CLANS, "stance": stance, "trust": trust}]
    return sc


def engine(seed=5, **kw):
    return renascita.new_engine(seed=seed, scenario=scenario(**kw))


def ruler(e, polity):
    return e.store.get(e.store.get(polity, "ruler"), "holder")


def harness(e, fn, days=1):
    out = {}
    base = e.rulesets[0][1]
    first = CAL.add(START, Span(days=1))

    class Harness(System):
        cadence = "on_demand"
        reads = A.READS | LIBRARY["Expand"].reads | war.CASUS_READS
        writes = A.WRITES | frozenset({"claims"})
        event_types = A.EVENT_TYPES

        def handle(self, ctx, activation):
            if activation.purpose == "succession":
                houses.handle_succession(ctx, activation)
            elif activation.purpose == "arrive":
                travel.arrive(ctx, activation)
            else:
                out["value"] = fn(ctx)

    Harness.name = "test.harness"
    rs = Ruleset("t", 1, (Harness(),) + base.systems, params=dict(base.params), forcers=base.forcers)
    e.rulesets = [(START, rs)]
    e.register_event_types(rs.event_types())
    e.run_before(first)
    e.schedule("test.harness", first, "act", entity=EMPIRE)
    e.run(until=CAL.add(first, Span(days=days)))
    return out.get("value")


def hot(e, person):  # (hot-blooded, so the ambition is open to them)
    e.store.set(person, "traits", {**e.store.get(person, "traits"), "temper": 0.95}, START, "test")


def test_a_hot_tempered_ruler_wants_a_cold_neighbours_border():
    e = engine()
    king = ruler(e, EMPIRE)
    hot(e, king)
    expand = LIBRARY["Expand"]
    f = harness(e, lambda ctx: expand.eligible(ctx, king))
    assert f is not None and f.target == CLANS


def test_no_expansion_at_peace_nor_for_one_who_doesnt_rule():
    e = engine(stance="friendly", trust=0.4)
    king = ruler(e, EMPIRE)
    hot(e, king)
    assert harness(e, lambda ctx: LIBRARY["Expand"].eligible(ctx, king)) is None
    e = engine()
    lord = e.store.get(f"{HOUSES[1]}-head", "holder")  # (a great lord, not the ruler)
    hot(e, lord)
    assert harness(e, lambda ctx: LIBRARY["Expand"].eligible(ctx, lord)) is None


def test_a_raid_is_a_border_incident_in_the_ledger():
    e = engine()
    king = ruler(e, EMPIRE)
    assert harness(e, lambda ctx: perform(ctx, ACTIONS["Raid"], king, CLANS, odds=1.0)) == "success"
    raid = next(ev for ev in e.events if ev.type == "polity.raid")
    assert raid.roles["raider"] == (king,) and set(raid.roles["party"]) == {EMPIRE, CLANS}
    assert raid.payload["relation"] == REL and raid.payload["route"] in e.store.ids("route")
    assert any(entry["kind"] == "raid" and entry["event"] == raid.id for entry in e.store.get(REL, "ledger"))


def test_only_a_ruler_raids_a_neighbour_they_border():
    e = engine()
    king = ruler(e, CLANS)
    nobody = e.store.get(f"{HOUSES[1]}-head", "holder")
    assert harness(e, lambda ctx: perform(ctx, ACTIONS["Raid"], nobody, CLANS, odds=1.0)) == "impossible"
    e = engine()
    assert harness(e, lambda ctx: perform(ctx, ACTIONS["Raid"], ruler(e, EMPIRE), EMPIRE, odds=1.0)) == "impossible"
    assert king  # (the clans have a ruler)


def test_hostility_is_a_planner_fact():
    e = engine(stance="hostile", trust=-0.8)
    king = ruler(e, EMPIRE)
    assert harness(e, lambda ctx: (holds(ctx, king, f"hostile:{CLANS}"), holds(ctx, king, f"hostile:{EMPIRE}"))) \
        == (True, False)
    e = engine()
    assert harness(e, lambda ctx: holds(ctx, ruler(e, EMPIRE), f"hostile:{CLANS}")) is False


def test_an_expanding_ruler_is_a_casus_belli():
    e = engine()
    king = ruler(e, EMPIRE)
    assert harness(e, lambda ctx: war.casus_belli(ctx, EMPIRE, CLANS)) is None
    e = engine()
    king = ruler(e, EMPIRE)
    hot(e, king)  # (so the yearly pass keeps the ambition)
    amb = "amb:test"
    e.store.create("ambition", amb, {"owner": king, "class": "Expand", "target": CLANS, "state": "active",
                                     "scheme": None, "claims": {"polity": EMPIRE, "places": []}}, START, "test")
    e.store.set(king, "ambitions", [amb], START, "test")
    assert harness(e, lambda ctx: war.casus_belli(ctx, EMPIRE, CLANS)) == amb


def test_expansion_is_won_when_a_claimed_place_changes_hands():
    e = engine()
    king = ruler(e, EMPIRE)
    expand = LIBRARY["Expand"]
    places = harness(e, lambda ctx: expand.claims(ctx, EMPIRE, CLANS))
    assert places and all(e.store.get(p, "control") == CLANS for p in places)
    e.store.create("ambition", "amb:test", {"owner": king, "class": "Expand", "target": CLANS, "state": "active",
                                            "scheme": None, "claims": {"polity": EMPIRE, "places": places}}, START, "test")
    view = _View(e)
    assert expand.satisfied(view, "amb:test") is False
    e.store.set(places[0], "control", EMPIRE, START, "test")  # (taken in a war)
    assert expand.satisfied(view, "amb:test") is True


class _View:
    """The store read as a ctx would (enough for `satisfied`)."""

    def __init__(self, e):
        self.get = e.store.get


def test_a_bitter_border_left_to_itself_sees_expansion_and_raids():
    found = None
    for seed in (5, 6, 7):
        e = engine(seed=seed)
        e.run(until=CAL.add(START, Span(years=40)))
        formed = [ev for ev in e.events if ev.type == "people.ambition_formed" and ev.payload["class"] == "Expand"]
        raids = [ev for ev in e.events if ev.type == "polity.raid"]
        if formed and raids:
            found = (formed, raids)
            break
    assert found, "no Expand and raid on three seeds"
    formed, raids = found
    assert {ev.roles["raider"][0] for ev in raids} <= {ev.roles["owner"][0] for ev in formed}
