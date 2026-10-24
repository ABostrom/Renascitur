"""Offices beyond a house's headship (S8 spec §3, #120): offices scoped to a polity, filled by
appointment (the appointer's holder picks) or by election (the members' heads vote, weighted by standing,
as an event), a vacant office filled at the yearly pass, `legitimacy`, and a polity's ruler naming an office."""

import copy

import pytest

from renasci import kin, polities
from renasci.core.calendar import Date
from renasci.core.ripples import Ripple

HOUSES = ["t:House-Hollow", "t:House-Mere", "t:House-Ridge"]
REALM = "t:Realm"
SPEAKER, MARSHAL = "t:Speaker", "t:Marshal"


def scenario(**over):
    sc = copy.deepcopy(kin.SCENARIO)
    sc["polities"] = [{"id": REALM, "name": "the Realm", "kind": "kingdom", "government": "council",
                       "seat": "t:Hollow-1", "members": HOUSES, "control": ["t:Hollow", "t:Ridge", "t:Mere"],
                       "ruler": "t:House-Hollow-head"}]
    sc["offices"] = [
        {"id": SPEAKER, "name": "Speaker of the Realm", "scope": "polity", "polity": REALM, "rule": "election"},
        {"id": MARSHAL, "name": "Marshal of the Realm", "scope": "polity", "polity": REALM, "rule": "appointment",
         "appointer": "t:House-Hollow-head"},
    ]
    sc.update(over)
    return sc


def heads(e):
    return {e.store.get(f"{h}-head", "holder") for h in HOUSES}


@pytest.fixture(scope="module")
def run():
    e = kin.new_engine(seed=11, scenario=scenario())
    cast = {o: (e.store.get(o, "holder"), e.store.get(o, "legitimacy"), e.store.get(o, "scope")) for o in (SPEAKER, MARSHAL)}
    e.run(until=Date(1, 3, 359))
    return e, cast


def test_offices_are_cast_vacant_and_lawful(run):
    _, cast = run
    assert cast == {SPEAKER: (None, "lawful", "polity"), MARSHAL: (None, "lawful", "polity")}


def test_an_election_is_a_vote_of_the_members_heads(run):
    e, _ = run
    votes = [ev for ev in e.events if ev.type == "polity.vote" and ev.payload["office"] == SPEAKER]
    assert votes, "the speaker was never elected"
    first = votes[0]
    assert set(first.roles["voter"]) <= heads(e) | {v for ev in votes for v in ev.roles["voter"]}
    assert len(first.roles["voter"]) == 3 and first.roles["winner"][0] in first.payload["tally"]
    won = [ev for ev in e.events if ev.type == "people.succession" and ev.payload["office"] == SPEAKER]
    assert won and won[0].roles["successor"] == first.roles["winner"]
    assert first.id in [c.ref for c in won[0].causes if c.kind == "event"]  # (the vote caused it)


def test_an_appointment_is_the_appointers_pick(run):
    e, _ = run
    picked = [ev for ev in e.events if ev.type == "polity.appointed" and ev.payload["office"] == MARSHAL]
    hollow = {e.store.get("t:House-Hollow-head", "holder")} | {
        ev.roles["predecessor"][0] for ev in e.events if ev.type == "people.succession"
        and ev.payload["office"] == "t:House-Hollow-head" and ev.roles.get("predecessor")}
    assert picked and picked[0].roles["by"][0] in hollow  # (whoever headed House Hollow then)
    holder = e.store.get(MARSHAL, "holder")
    assert holder is not None and e.store.get(holder, "house") in HOUSES
    assert MARSHAL in (e.store.get(holder, "offices") or [])


def test_a_presumptive_heir_is_named(run):
    e, _ = run
    assert e.store.get(SPEAKER, "heir") not in (None, e.store.get(SPEAKER, "holder"))


def test_the_same_seed_votes_the_same(run):
    e, _ = run
    again = kin.new_engine(seed=11, scenario=scenario())
    again.run(until=Date(1, 3, 359))
    vote = lambda x: [(ev.date, ev.roles["winner"], ev.payload["tally"]) for ev in x.events if ev.type == "polity.vote"]
    assert vote(again) == vote(e)


def test_a_dead_speaker_is_replaced_by_a_new_vote():
    e = kin.new_engine(seed=11, scenario=scenario())
    e.run(until=Date(1, 1, 359))
    speaker = e.store.get(SPEAKER, "holder")
    doomed = kin.new_engine(seed=11, scenario=scenario(),
                            ripples=[Ripple(id="r", kind="doom", target=speaker, date=Date(1, 2, 10))])
    doomed.run(until=Date(1, 3, 359))
    assert doomed.store.status(speaker) == "dead"
    votes = [ev for ev in doomed.events if ev.type == "polity.vote" and ev.payload["office"] == SPEAKER]
    assert len(votes) >= 2 and doomed.store.get(SPEAKER, "holder") not in (None, speaker)


@pytest.mark.parametrize("seed", [11, 3, 5])
def test_an_office_whose_holder_and_appointer_die_together_is_filled_again(seed):
    """(An office id that sorts before its appointer's: its succession comes first, while the appointer's
    own office is still unsettled. It stands vacant, and is filled once the appointer's is.)"""
    sc = scenario()
    sc["offices"][1]["id"] = "t:Admiral"
    e = kin.new_engine(seed=seed, scenario=sc)
    e.run(until=Date(1, 1, 359))
    admiral, head = e.store.get("t:Admiral", "holder"), e.store.get("t:House-Hollow-head", "holder")
    ripples = [Ripple(id=f"r{i}", kind="doom", target=t, date=Date(1, 2, 10)) for i, t in enumerate(sorted({admiral, head}))]
    d = kin.new_engine(seed=seed, scenario=sc, ripples=ripples)
    d.run(until=Date(1, 5, 359))
    holder = d.store.get("t:Admiral", "holder")
    assert d.store.status(admiral) == "dead" and holder is not None and d.store.status(holder) == "active"


@pytest.mark.parametrize("change, kind", [
    (lambda sc: sc["offices"][0].update(rule="lottery"), "bad_rule"),
    (lambda sc: sc["offices"][1].pop("appointer"), "bad_appointer"),
    (lambda sc: sc["offices"][1].update(appointer="t:nobody-head"), "bad_appointer"),
    (lambda sc: sc["offices"][0].update(polity="t:Atlantis"), "unknown_polity"),
    (lambda sc: sc["offices"][0].update(scope="guild"), "bad_scope"),
    (lambda sc: sc["polities"][0].update(ruler="t:Throne"), "bad_ruler"),
    (lambda sc: sc["offices"][0].update(id="t:House-Hollow"), "duplicate_id"),
    (lambda sc: sc["offices"][0].update(scope="house", house="t:House-Hollow"), "bad_scope"),
    (lambda sc: sc["offices"][0].update(rule="male_preference_primogeniture"), "bad_rule"),
    (lambda sc: sc["offices"][0].update(rule=["election"]), "bad_shape"),
    (lambda sc: sc["offices"].append({"id": "t:Steward", "scope": "polity", "polity": REALM, "rule": "appointment",
                                      "appointer": "t:Marshal"}) or sc["offices"][1].update(appointer="t:Steward"),
     "bad_appointer"),
    (lambda sc: sc["polities"][0].update(members=HOUSES[1:]), "bad_ruler"),  # (its ruler's house isn't a member)
])
def test_bad_offices_are_refused(change, kind):
    sc = scenario()
    change(sc)
    assert kind in {f["kind"] for f in polities.check(sc)}


def test_a_scenario_without_offices_keeps_its_headships_as_they_were():
    e = kin.new_engine(seed=11)
    assert e.store.get("t:House-Hollow-head", "legitimacy") is None and e.store.get("t:House-Hollow-head", "scope") is None


def test_the_fourth_age_has_the_draft_empire_when_asked():
    from renasci import renascita

    e = renascita.new_engine(seed=3, polities=True)
    s = e.store
    assert s.get("v:firebrand-empire", "draft") is True and s.get("v:firebrand-empire", "government") == "advised"
    throne = s.get("v:firebrand-empire", "ruler")
    assert throne == "v:house-imperial-head" and s.get(throne, "holder") is not None
    assert all(s.get(t, "control") == "v:firebrand-empire" for t in ("v:lions-rest", "v:raining-bay", "v:old-westgate"))
    assert s.get("v:bloc-outliers", "members") == ["v:house-kundarak", "v:house-lyrandar", "v:house-phiarlan"]
    plain = renascita.new_engine(seed=3)
    assert not plain.store.exists("v:firebrand-empire") and plain.store.get("v:lions-rest", "control") is None
