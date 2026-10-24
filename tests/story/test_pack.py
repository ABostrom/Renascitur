"""Context packs (S12 spec §2, #115), on the M4 run: every subject kind and point of view fits the schema,
the same run gives the same bytes, and a point of view holds only what it could know."""

import json

import pytest

from renasci.core.canon import canonical
from renasci.story.pack import build
from renasci.story.schema import PACK, validate


def failure(run):
    return next(e for e in run.events if e["type"] == "ward.failure")


def subjects(run):
    saga = run.stories["sagas"][0]
    claims_topic = next(e for e in run.events if e["type"] == "belief.perceived")
    from renasci.people.beliefs import topic

    return [("saga", saga["id"]), ("arc", saga["arcs"][0]), ("person", run.stories["arcs"][0]["owner"]),
            ("event", failure(run)["id"]), ("topic", topic(claims_topic["payload"]["claim"]))]


def test_every_subject_kind_from_every_point_of_view_fits_the_schema(m4run):
    fail = failure(m4run)
    keeper = fail["roles"]["keeper"][0]
    for subject in subjects(m4run):
        for pov in ("omniscient", keeper, m4run.houses[fail["roles"]["leader"][0]], "v:lux-oescus"):
            pack = build(m4run, subject, pov)
            assert validate(pack, PACK) == [], (subject, pov, validate(pack, PACK)[:3])


def test_the_same_run_gives_the_same_bytes(m4run):
    s = subjects(m4run)[0]
    assert canonical(build(m4run, s)) == canonical(build(m4run, s))


def test_an_omniscient_pack_has_the_secrets_and_the_verdicts(m4run):
    pack = build(m4run, ("event", failure(m4run)["id"]))
    assert any(e["secret"] and e["type"] == "ward.sabotage" for e in pack["events"])  # (a cause, depth 2)
    assert pack["beliefs"] and all("truth" in b for b in pack["beliefs"])
    assert {b["truth"] for b in pack["beliefs"]} >= {"false"}  # (the guild's lie)


def test_a_person_sees_only_what_they_could_know(m4run):
    fail = failure(m4run)
    keeper = fail["roles"]["keeper"][0]
    pack = build(m4run, ("event", fail["id"]), keeper)
    by_id = m4run.by_id
    for e in pack["events"]:
        ev = by_id[e["id"]]
        mine = any(keeper in ms for ms in ev["roles"].values())
        assert mine or not e["secret"] or e["id"] in {b["origin"] for b in pack["beliefs"]}, e["text"]
    assert all("truth" not in b for b in pack["beliefs"])  # (they don't know which of their beliefs are true)
    assert all(b["holder"] == keeper for b in pack["beliefs"])


def test_someone_from_another_town_does_not_see_the_failure(m4run):
    fail = failure(m4run)
    far = next(p for p, e in sorted(m4run.ents.items()) if e["kind"] == "person"
               and all(place != "v:lux-oescus" for _, place in m4run.residence(p))
               and m4run.houses.get(p) not in {m4run.houses.get(m) for ms in fail["roles"].values() for m in ms}
               and not any(p in ms for ms in fail["roles"].values()))
    pack = build(m4run, ("event", fail["id"]), far)
    assert fail["id"] not in pack["timeline"]


def test_a_town_sees_its_public_events_and_its_talk(m4run):
    pack = build(m4run, ("event", failure(m4run)["id"]), "v:lux-oescus")
    assert pack["events"] and all(e["place"] == "v:lux-oescus" and not e["secret"] for e in pack["events"])
    assert any("fault" in b["text"] for b in pack["beliefs"])  # (the official line, in the town's talk)


def test_a_house_holds_one_claim_per_question(m4run):
    from renasci.people.beliefs import topic

    fail = failure(m4run)
    house = m4run.houses[fail["roles"]["leader"][0]]
    pack = build(m4run, ("event", fail["id"]), house)
    topics = [topic(b["claim"]) for b in pack["beliefs"]]
    assert len(topics) == len(set(topics))


@pytest.mark.parametrize("change", [lambda p: p.pop("events"), lambda p: p.update(extra=1),
                                    lambda p: p["pov"].update(kind="god"), lambda p: p.update(span="soon"),
                                    lambda p: p["events"].append({"id": 3})])
def test_a_broken_pack_is_refused(m4run, change):
    pack = json.loads(canonical(build(m4run, ("event", failure(m4run)["id"]))))
    change(pack)
    assert validate(pack, PACK)


def test_unknown_subjects_and_points_of_view_are_refused(m4run):
    for subject, pov in [(("saga", "saga:nope"), "omniscient"), (("event", "xnope"), "omniscient"),
                         (("event", failure(m4run)["id"]), "p:nobody")]:
        with pytest.raises(ValueError):
            build(m4run, subject, pov)


def test_renasci_pack_writes_a_valid_pack(m4):
    from renasci.cli import main

    from renasci.story.pack import Run

    fail = failure(Run(m4))
    assert main(["pack", str(m4), "--event", fail["id"], "--pov", "v:lux-oescus"]) == 0
    written = list((m4 / "analysis" / "packs").glob("event-*--v_lux-oescus.json"))
    assert len(written) == 1 and validate(json.loads(written[0].read_text(encoding="utf-8")), PACK) == []
    assert main(["pack", str(m4)]) != 0  # (no subject)
