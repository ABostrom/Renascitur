"""Polities and control (S8 spec §2, #120): polities and factions from a scenario's data, checked; control
of settlements and places (apart from their region); a border is a route between two polities' places;
control changes through S4's dated changes and a structural ripple, and the map by year shows it."""

import copy

import pytest

from renasci import geo, polities, renascita
from renasci.analysis.mapyear import geography_at
from renasci.core.calendar import Date, Span
from renasci.core.ripples import Ripple

CAL, START = renascita.CAL, renascita.START
EMPIRE, CLANS = "v:test-empire", "v:test-clans"
HOUSES = [h["id"] for h in renascita.SCENARIO["houses"]]

POLITIES = [
    {"id": EMPIRE, "name": "the Empire", "kind": "empire", "government": "advised", "seat": "v:lions-rest",
     "members": HOUSES[:10], "control": ["v:pyrosia"], "draft": True},
    {"id": CLANS, "name": "the Clans", "kind": "clans", "government": "ruler", "seat": "v:raining-bay",
     "members": HOUSES[10:], "control": ["v:flame-coast", "v:foalswood"], "draft": True},
]
FACTIONS = [{"id": "v:test-bloc", "name": "the Old Bloc", "polity": EMPIRE, "kind": "bloc", "members": HOUSES[:3],
             "aims": ["peace"], "standing": 0.6}]


def scenario(**over):
    sc = copy.deepcopy(renascita.SCENARIO)
    sc["polities"], sc["factions"] = copy.deepcopy(POLITIES), copy.deepcopy(FACTIONS)
    sc.update(over)
    return sc


def test_a_good_scenario_has_no_findings():
    assert polities.check(scenario()) == []


def test_control_expands_regions_and_the_most_specific_claim_wins():
    control = polities.control_of(scenario())
    assert control["v:lions-rest"] == EMPIRE  # (in Pyrosia, by its province)
    assert control["v:raining-bay"] == CLANS and control["v:stormhome"] == CLANS  # (the Flame Coast: a nearer region)
    assert control["v:foalswood"] == CLANS  # (a place named outright, in the Empire's Ember Peaks)
    assert control["v:old-westgate"] == EMPIRE


@pytest.mark.parametrize("change, kind", [
    (lambda sc: sc["polities"][0].update(seat="v:nowhere"), "bad_seat"),
    (lambda sc: sc["polities"][1].update(seat="v:lions-rest"), "seat_not_held"),
    (lambda sc: sc["polities"][0]["control"].append("v:atlantis"), "unknown_control"),
    (lambda sc: sc["polities"][1]["control"].append("v:pyrosia"), "control_twice"),
    (lambda sc: sc["polities"][1]["members"].append(HOUSES[0]), "member_twice"),
    (lambda sc: sc["polities"][0]["members"].append("v:house-nobody"), "unknown_member"),
    (lambda sc: sc["factions"][0].update(polity="v:nope"), "unknown_polity"),
    (lambda sc: sc["factions"][0]["members"].append(HOUSES[11]), "faction_outsider"),
    (lambda sc: sc["factions"][0].update(standing=2), "bad_standing"),
    (lambda sc: sc["polities"].append(dict(sc["polities"][0])), "duplicate_id"),
])
def test_a_bad_scenario_is_refused(change, kind):
    sc = scenario()
    change(sc)
    assert kind in {f["kind"] for f in polities.check(sc)}


@pytest.fixture(scope="module")
def engine():
    e = renascita.new_engine(seed=3, scenario=scenario())
    return e


def test_polities_and_factions_are_cast_with_control_on_their_places(engine):
    s = engine.store
    assert s.get(EMPIRE, "seat") == "v:lions-rest" and s.get(EMPIRE, "members") == sorted(HOUSES[:10])
    assert s.get("v:test-bloc", "polity") == EMPIRE and s.get("v:test-bloc", "standing") == 0.6
    assert s.get("v:lions-rest", "control") == EMPIRE and s.get("v:raining-bay", "control") == CLANS
    assert s.get("v:foalswood", "control") == CLANS and s.get("v:foalswood", "region") == "v:ember-peaks"


def test_a_border_is_a_route_between_two_polities_places():
    sc = scenario()
    control = polities.control_of(sc)
    borders = polities.borders(sc["geography"]["routes"], control)
    assert borders and all(control[r["ends"][0]] != control[r["ends"][1]] for r in borders)
    assert all(r["id"] in {x["id"] for x in sc["geography"]["routes"]} for r in borders)


@pytest.mark.parametrize("change, kind", [
    (lambda sc: sc.update(polities=["x"]), "bad_id"),
    (lambda sc: sc["polities"][0].pop("id"), "bad_id"),
    (lambda sc: sc["polities"][0].update(control=[["x"]]), "bad_shape"),
    (lambda sc: sc["polities"][0].update(id=HOUSES[0]), "duplicate_id"),  # (already a house)
    (lambda sc: sc["polities"][1].update(control=[]), "seat_not_held"),  # (it claims nothing, not even its seat)
])
def test_malformed_data_is_a_finding_not_a_crash(change, kind):
    sc = scenario()
    change(sc)
    assert kind in {f["kind"] for f in polities.check(sc)}


def test_a_change_to_a_polity_that_doesnt_exist_is_refused_without_polities_too():
    sc = copy.deepcopy(renascita.SCENARIO)
    sc["geography"]["changes"] = [{"date": at(1), "place": "v:old-westgate", "control": "v:ghost"}]
    assert "unknown_control" in {f["kind"] for f in polities.check(sc)}


def test_a_scenario_without_polities_is_unchanged():
    assert polities.check(renascita.SCENARIO) == [] and polities.control_of(renascita.SCENARIO) == {}
    e = renascita.new_engine(seed=3)
    assert e.store.get("v:lions-rest", "control") is None


def at(years, days=0):
    return CAL.add(START, Span(years=years, days=days)).to_json()


def test_control_changes_on_its_date_and_the_map_by_year_shows_it():
    sc = scenario()
    sc["geography"]["changes"] = [{"date": at(1, 30), "place": "v:old-westgate", "control": CLANS, "why": "taken"},
                                  {"date": at(2), "place": "v:old-westgate", "region": "v:flame-coast",
                                   "control": EMPIRE, "why": "retaken, and the border redrawn"}]
    assert polities.check(sc) == [] and not [f for f in geo.check(sc["geography"]) if f["severity"] == "error"]
    e = renascita.new_engine(seed=3, scenario=sc)
    e.run(until=CAL.add(START, Span(years=3)))
    changed = [ev for ev in e.events if ev.type == "geo.changed"]
    assert [ev.payload["change"].get("control") for ev in changed] == [CLANS, EMPIRE]
    assert e.store.get("v:old-westgate", "control") == EMPIRE and e.store.get("v:old-westgate", "region") == "v:flame-coast"
    doc = polities.annotate(sc["geography"], sc)  # (the run's geography.json: with each place's starting control)
    rows = [d.to_json() for d in e.store.deltas]
    held = lambda date: next(p for p in geography_at(doc, rows, Date.from_json(date))["places"] if p["id"] == "v:old-westgate")
    assert held(at(1))["control"] == EMPIRE
    assert held(at(1, 100))["control"] == CLANS and held(at(1, 100))["region"] == "v:ember-peaks"
    assert held(at(2, 10))["control"] == EMPIRE and held(at(2, 10))["region"] == "v:flame-coast"


def test_a_control_change_must_name_a_polity():
    sc = scenario()
    sc["geography"]["changes"] = [{"date": at(1), "place": "v:old-westgate", "control": "v:nobody"}]
    assert "unknown_control" in {f["kind"] for f in polities.check(sc)}
    sc["geography"]["changes"] = [{"date": at(1), "place": "v:old-westgate"}]
    assert any(f["kind"] == "bad_change" for f in geo.check(sc["geography"]))


def test_a_structural_ripple_can_change_who_holds_a_place():
    ripple = Ripple(id="r", kind="structural", target="v:old-westgate", date=Date.from_json(at(1)),
                    params={"control": CLANS, "why": "a revolt"})
    e = renascita.new_engine(seed=3, scenario=scenario(), ripples=[ripple])
    e.run(until=CAL.add(START, Span(years=2)))
    assert e.store.get("v:old-westgate", "control") == CLANS
