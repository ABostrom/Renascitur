"""What a run's world believes, beside what happened (S13 world knowledge, #106): analysis/claims.json."""

import copy
import json

import pytest

from renasci import renascita
from renasci.analysis.claims import claims_report
from renasci.core.calendar import Span
from renasci.core.ripples import Ripple


@pytest.fixture(scope="module")
def ward_run():
    sc = copy.deepcopy(renascita.SCENARIO)
    sc["params"]["beliefs"] = True
    when = renascita.CAL.add(renascita.START, Span(years=1))
    e = renascita.new_engine(seed=1, scenario=sc, ripples=[Ripple("ward", "inject", when, "v:lux-oescus",
                                                                  {"script": "ward_failure"})])
    e.run(until=renascita.CAL.add(when, Span(years=3)))
    events = [{"id": ev.id, "date": ev.date.to_json(), "type": ev.type,
               "roles": {k: list(v) for k, v in ev.roles.items()}, "causes": [[c.kind, c.ref] for c in ev.causes],
               "payload": ev.payload, "place": ev.place} for ev in e.events]
    return events, e.store.to_json()


def test_every_claim_is_judged_and_counted(ward_run):
    events, state = ward_run
    report = claims_report(events, state)
    failure = next(ev for ev in events if ev["type"] == "ward.failure")
    topic = next(t for t in report["topics"] if t["topic"] == f"why:{failure['id']}")
    assert topic["about"] == failure["id"] and topic["about_type"] == "ward.failure"
    verdicts = {c["truth"] for c in topic["claims"]}
    assert "false" in verdicts and ({"true", "half"} & verdicts)  # the lie, and the truth (or its drift)
    lie = next(c for c in topic["claims"] if c["lies"] > 0)
    assert lie["truth"] == "false" and lie["holders"] > 0
    assert sum(lie["shares"].values()) > 0 and lie["text"]
    assert all(c["key"].startswith("c:") and c["first"] for c in topic["claims"])


def test_drifted_claims_point_back_to_what_they_drifted_from(ward_run):
    events, state = ward_run
    report = claims_report(events, state)
    keys = {c["key"] for t in report["topics"] for c in t["claims"]}
    drifted = [c for t in report["topics"] for c in t["claims"] if c["parent"]]
    assert all(c["parent"] in keys for c in drifted)


def test_renasci_claims_writes_the_report(tmp_path):
    from renasci.cli import main

    out = tmp_path / "runs"
    base = tmp_path / "base.toml"
    base.write_text('[run]\nname = "base"\nengine = "0.1.0"\nseed = 1\nworld = "fourth_age"\nend = "4A 2"\n',
                    encoding="utf-8")
    assert main(["run", str(base), "--out", str(out)]) == 0
    assert main(["claims", str(out / "base")]) == 0
    report = json.loads((out / "base" / "analysis" / "claims.json").read_text(encoding="utf-8"))
    assert report["run"] == "base" and report["topics"] == []  # (no beliefs in this world: nothing claimed)


def _person(i, beliefs, status="active"):
    return {"id": i, "kind": "person", "status": status, "fields": {"name": i.upper(), "beliefs": beliefs}}


def test_a_claim_only_in_a_towns_shares_is_still_reported_and_people_are_counted_once():
    death = {"id": "d1", "date": [1, 0, 0], "type": "people.death", "roles": {"deceased": ["p:v"], "killer": ["p:k"]},
             "causes": [], "payload": {}}
    true = {"pred": "killed", "args": {"victim": "p:v", "by": "p:k"}}
    lie = {"pred": "killed", "args": {"victim": "p:v", "by": "p:x"}}
    told = {"id": "e1", "date": [1, 0, 1], "type": "belief.perceived", "roles": {}, "causes": [],
            "payload": {"key": "c:true", "claim": true}}
    state = {"entities": [
        _person("p:a", {"c:true": {"claim": true}, "c:lie": {"claim": lie}}),  # (holds both: one person)
        _person("p:b", {"c:true": {"claim": true}}),
        _person("p:v", {}, status="dead"),
        {"id": "t:x", "kind": "settlement", "status": "active",
         "fields": {"shares": {"c:lie": {"claim": lie, "share": 0.3}}}}]}
    topic = claims_report([death, told], state)["topics"][0]
    by_key = {c["key"]: c for c in topic["claims"]}
    assert by_key["c:lie"]["shares"] == {"t:x": 0.3} and by_key["c:lie"]["truth"] == "false"
    assert by_key["c:lie"]["first"] is None  # (never told to a notable: no date)
    assert topic["people"] == 2 and topic["holders"] == 3
