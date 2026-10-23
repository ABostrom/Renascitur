"""Pins from the vault (S2 spec §6, #61): the core extraction and the people hook."""

from pathlib import Path

import pytest

from renasci.core.calendar import Date
from renasci.core.pins import feasibility
from renasci.people.vault import people_hook
from renasci.renascita import CAL
from renasci.vault.loader import load
from renasci.vault.pins import extract

FIXTURE = Path(__file__).parents[1] / "fixtures" / "vault_people"
START, END = Date(4, 10, 0), Date(4, 60, CAL.days_per_year - 1)


@pytest.fixture(scope="module")
def got():
    return extract(load(FIXTURE), CAL, START, END, hooks=[people_hook])


def pin(got, pid):
    return next(p for p in got.pins if p.id == pid)


def test_a_child_born_in_the_run_with_a_parent_is_a_birth_pin_that_binds_it(got):
    p = pin(got, "v:bryn-ardent:born")
    assert p.kind == "event" and p.payload["type"] == "people.birth"
    assert p.payload["roles"] == {"father": ["v:old-ardent"]}
    assert p.payload["bind"] == {"role": "child", "subject": "v:bryn-ardent", "fields": {"sex": "f"}}
    assert p.window == (Date(4, 20, 0), Date(4, 20, CAL.days_per_year - 1))
    assert pin(got, "v:twin:born").window == (Date(4, 20, 0), Date(4, 30, CAL.days_per_year - 1))  # ~4A 25


def test_placements_say_how_each_character_enters_the_run(got):
    assert got.placements["v:old-ardent"]["status"] == "placed"
    assert got.placements["v:unus"]["status"] == "placed"
    assert got.placements["v:bryn-ardent"]["status"] == "reserved"
    assert got.placements["v:cass"]["status"] == "unplaced"  # born in the run with no parent
    assert got.placements["v:dorn-ardent"]["status"] == "drawn"  # no birth date, but a house in the run
    assert got.placements["v:late"]["status"] == "out_of_scope"


def test_existence_pins_only_with_a_stated_window(got):
    alive = [p for p in got.pins if p.kind == "existence"]
    assert [p.id for p in alive] == ["v:old-ardent:alive"]  # Unus has no died: no pin, or he'd be guarded forever
    assert alive[0].window == (START, Date(4, 29, CAL.days_per_year - 1))  # to the day before the death window


def test_reigns_are_succession_event_pins_on_the_office_entity(got):
    r = pin(got, "v:bryn-ardent:reign:v:house-ardent-head:1")  # numbered per holder
    assert r.payload == {"type": "people.succession", "roles": {"successor": ["v:bryn-ardent"]},
                         "office": "v:house-ardent-head"}
    assert pin(got, "v:old-ardent:reign:v:house-ardent-head:1").window[0] == Date(4, 2, 0)
    assert any(r["kind"] == "unsupported" and "v:emperors" in r["message"] for r in got.reports)
    assert not any(p.payload.get("office") == "v:emperors" for p in got.pins)


def test_orderings_only_between_two_in_run_event_pins(got):
    orders = {p.id: p for p in got.pins if p.kind == "ordering"}
    assert set(orders) == {"v:bryn-ardent:born:before:v:wedding-of-bryn:event"}
    assert orders["v:bryn-ardent:born:before:v:wedding-of-bryn:event"].payload == {
        "before": "v:bryn-ardent:born", "after": "v:wedding-of-bryn:event"}
    # reign 1 lies before the run: its ordering with reign 2 is checked here, not pinned
    assert any(r["kind"] == "ordering_met" and "reign" in r["message"] for r in got.reports)
    assert any(f["kind"] == "infeasible_ordering" and f["key"] == "Events/Backwards" for f in got.findings)


def test_events_with_an_engine_type_are_pins_and_the_rest_are_unmodelled(got):
    w = pin(got, "v:wedding-of-bryn:event")
    assert w.payload == {"type": "people.marriage", "roles": {"spouse": ["v:bryn-ardent"]}}
    assert [u["id"] for u in got.unmodelled] == ["v:old-war"]
    assert got.unmodelled[0]["window"][0] == Date(4, 12, 0).to_json()  # from the timeline year 12012
    kinds = {(f["kind"], f["key"]) for f in got.findings}
    assert ("not_canon_participant", "Events/Bad Wedding") in kinds
    assert ("birth_from_event", "Events/Birth of Twin") in kinds  # births come from characters only
    assert not any(p.id.startswith("v:bad-wedding") or p.id.startswith("v:birth-of-twin") for p in got.pins)


def test_deaths_are_expectations_not_pins(got):
    assert {e["subject"]: e["kind"] for e in got.expectations} == {"v:old-ardent": "died"}


def test_the_pins_are_valid_and_feasible_to_s1(got):
    verdicts = feasibility(got.pins, START, END)
    assert verdicts["v:old-ardent:reign:v:house-ardent-head:1"] == "out_of_scope"
    assert verdicts["v:bryn-ardent:born"] == verdicts["v:bryn-ardent:born:before:v:wedding-of-bryn:event"] == "ok"
    assert all(v in ("ok", "out_of_scope") for v in verdicts.values()), verdicts


def test_extraction_is_deterministic(got):
    again = extract(load(FIXTURE), CAL, START, END, hooks=[people_hook])
    assert [p.to_json() for p in again.pins] == [p.to_json() for p in got.pins] and again.to_json() == got.to_json()


def test_renasci_vault_pins_prints_json(capsys):
    import json

    from renasci.cli import main

    assert main(["vault", "pins", str(FIXTURE), "--world", "fourth_age", "--from", "4A 10", "--to", "4A 60"]) == 0
    data = json.loads(capsys.readouterr().out)
    assert "v:bryn-ardent:born" in {p["id"] for p in data["pins"]} and data["placements"]


# ---------------------------------------------------------------- review regressions


def write(tmp_path, notes: dict):
    root = tmp_path / "v"
    (root / "People").mkdir(parents=True)
    (root / "Houses").mkdir()
    (root / "vault.toml").write_text('[[types]]\nmatch = "People/*"\ntype = "character"\n'
                                     '[[types]]\nmatch = "Houses/*"\ntype = "house"\n', encoding="utf-8")
    for name, fm in notes.items():
        (root / f"{name}.md").write_text(f"---\n{fm}\n---\n", encoding="utf-8")
    return extract(load(root), CAL, START, END, hooks=[people_hook])


def finding_kinds(got):
    return {(f["kind"], f["key"]) for f in got.findings}


def test_the_dead_are_not_placed_and_a_first_year_birth_counts_as_before_the_start(tmp_path):
    got = write(tmp_path, {"People/Gone": "born: 4A 1\ndied: 4A 5", "People/Founder": "born: 4A 10",
                           "People/Span": "born: 4A 8..12"})
    assert got.placements["v:gone"]["status"] == "dead"
    assert got.placements["v:founder"]["status"] == "placed"  # the run starts during their birth year
    assert got.placements["v:span"]["status"] == "placed"


def test_the_alive_pin_ends_the_day_before_the_death_window(tmp_path):
    got = write(tmp_path, {"People/Old": "born: 4A 1\ndied: 4A 30 m3 d5"})
    alive = next(p for p in got.pins if p.id == "v:old:alive")
    died = CAL.parse("4A 30 m3 d5")
    assert alive.window[1] == CAL.from_ordinal(died.age, CAL.ordinal(died) - 1)


def test_doomed_pins_are_findings_not_pins(tmp_path):
    got = write(tmp_path, {
        "People/Nobody": "offices:\n  - {office: \"[[House X]]\", from: 4A 30}",  # unplaced holder
        "Houses/House X": "founded: 4A 1",
        "People/Young": "born: 4A 40\nhouse: \"[[House X]]\"\noffices:\n  - {office: \"[[House X]]\", from: 4A 30}",
        "People/Mum": "born: 4A 50",
        "People/Kid": "born: 4A 45\nmother: \"[[Mum]]\"",  # a mother born after her child
        "People/Ghost": "born: 4A 1\ndied: 4A 20",
        "People/Posthumous": "born: 4A 30\nfather: \"[[Ghost]]\"",
        "People/Outsider": "born: 4A 1\noffices:\n  - {office: \"[[House X]]\", from: 4A 35}",  # not of House X
    })
    kinds = finding_kinds(got)
    assert ("doomed_reign", "People/Nobody") in kinds and ("doomed_reign", "People/Young") in kinds
    assert ("doomed_birth", "People/Kid") in kinds and ("doomed_birth", "People/Posthumous") in kinds
    assert ("outside_house", "People/Outsider") in kinds
    ids = {p.id for p in got.pins}
    assert not any(i.startswith(("v:nobody:reign", "v:young:reign", "v:kid:born", "v:posthumous:born")) for i in ids)


def test_orderings_are_not_duplicated_and_overlap_is_undetermined(tmp_path):
    got = write(tmp_path, {})
    root = tmp_path / "v"
    (root / "Events").mkdir()
    (root / "vault.toml").write_text('[[types]]\nmatch = "Events/*"\ntype = "event"\n', encoding="utf-8")
    (root / "Events/A.md").write_text('---\nengine: people.marriage\ndate: 4A 20\nbefore: "[[B]]"\n---\n', encoding="utf-8")
    (root / "Events/B.md").write_text('---\nengine: people.marriage\ndate: 4A 30\nafter: "[[A]]"\n---\n', encoding="utf-8")
    (root / "Events/Old.md").write_text('---\nengine: people.marriage\ndate: 4A 1..8\nbefore: "[[C]]"\n---\n', encoding="utf-8")
    (root / "Events/C.md").write_text('---\nengine: people.marriage\ndate: 4A 5..9\n---\n', encoding="utf-8")
    got = extract(load(root), CAL, START, END, hooks=[people_hook])
    orders = [p.id for p in got.pins if p.kind == "ordering"]
    assert orders.count("v:a:event:before:v:b:event") == 1
    assert any(r["kind"] == "ordering_undetermined" for r in got.reports)


def test_reigns_number_per_holder_and_windows_never_overlap_the_next(tmp_path):
    got = write(tmp_path, {
        "Houses/House X": "founded: 4A 1",
        "People/A": "born: 4A 1\nhouse: \"[[House X]]\"\noffices:\n  - {office: \"[[House X]]\", from: 4A 20..30}",
        "People/B": "born: 4A 1\nhouse: \"[[House X]]\"\noffices:\n  - {office: \"[[House X]]\", from: 4A 25}",
        "People/C": "born: 4A 1\nhouse: \"[[House X]]\"\noffices:\n  - {office: \"[[House X]]\", from: 4A 2}",
    })
    pins = {p.id: p for p in got.pins}
    a, b = pins["v:a:reign:v:house-x-head:1"], pins["v:b:reign:v:house-x-head:1"]
    assert a.window[1] <= b.window[1]
    assert got.holders == {"v:house-x-head": "v:c"}  # who holds each office when the run starts


def test_a_mistyped_age_is_a_finding_not_out_of_calendar(tmp_path):
    got = write(tmp_path, {"People/Typo": "born: 4a 20"})
    assert ("date", "People/Typo") in finding_kinds(got)
