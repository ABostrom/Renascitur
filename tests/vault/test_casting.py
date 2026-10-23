"""Casting (S2 spec §7, #63): canon placed into the synthesised world, births reserved, the log kept.

The fixture's House Ardent, cast into the Fourth Age draft (its first house renamed) starting 4A 40: Old
Ardent founded it and died in 4A 30; Bryn, his daughter, has held the headship since 4A 31; her son, the
Heir, is born in 4A 50.
"""

import copy
from pathlib import Path

import pytest

from renasci.core.calendar import Date
from renasci.people.casting import canon_from
from renasci.people.vault import people_hook
from renasci.renascita import CAL, SCENARIO, new_engine
from renasci.vault.feasibility import check, feasible
from renasci.vault.loader import load
from renasci.vault.pins import extract

FIXTURE = Path(__file__).parents[1] / "fixtures" / "vault_people"
START, END = Date(4, 40, 0), Date(4, 100, CAL.days_per_year - 1)


def scenario():
    sc = copy.deepcopy(SCENARIO)
    sc["start"] = START.to_json()
    sc["houses"][0]["id"] = "v:house-ardent"
    sc["houses"][0]["name"] = "Ardent"
    return sc


def canon_of(sc):
    vault = load(FIXTURE)
    found = extract(vault, CAL, START, END, hooks=[people_hook])
    report = check(found, vault, START, END, hooks=[people_hook], calendar=CAL)
    canon, log = canon_from(found, vault, sc)
    return canon, log, feasible(found, report)


@pytest.fixture(scope="module")
def cast():
    sc = scenario()
    canon, log, pins = canon_of(sc)
    e = new_engine(scenario=sc, pins=pins, canon=canon)
    return e, log


def test_the_holder_at_the_start_heads_the_house_under_their_canon_id(cast):
    e, log = cast
    assert e.store.get("v:house-ardent-head", "holder") == "v:bryn-ardent"
    assert e.store.get("v:bryn-ardent", "name") == "Bryn Ardent" and e.store.get("v:bryn-ardent", "sex") == "f"
    assert e.store.get("v:bryn-ardent", "born") == [4, 20, 0]
    assert e.store.get("v:bryn-ardent", "offices") == ["v:house-ardent-head"]
    assert log["v:bryn-ardent"] == {"status": "placed", "entity": "v:bryn-ardent", "as": "head of v:house-ardent"}


def test_a_canon_father_dead_before_the_start_is_a_dead_record_in_the_lineage(cast):
    e, log = cast
    assert e.store.status("v:old-ardent") == "dead" and e.store.get("v:bryn-ardent", "father") == "v:old-ardent"
    assert "v:bryn-ardent" in e.store.get("v:old-ardent", "children")
    assert log["v:old-ardent"]["status"] == "dead"
    assert e.store.get("v:twin", "father") == "v:old-ardent"  # a canon sibling, placed with the same father


def test_the_rest_of_the_family_is_synthesised_around_canon(cast):
    e, _ = cast
    family = [p for p in e.store.ids("person") if e.store.get(p, "house") == "v:house-ardent"]
    assert any(p.startswith("s:") for p in family) and "v:bryn-ardent" in family


def test_drawn_unplaced_and_reserved(cast):
    e, log = cast
    assert log["v:dorn-ardent"]["status"] == "drawn" and e.store.get("v:dorn-ardent", "house") == "v:house-ardent"
    assert log["v:cass"]["status"] == "placed" and e.store.exists("v:cass")
    assert log["v:heir"] == {"status": "reserved", "entity": None, "as": "born in the run"}
    assert not e.store.exists("v:heir")


def test_conservation_holds_with_canon_placed(cast):
    e, _ = cast
    assert e.rulesets[-1][1].conservation(e.store) == []


def test_a_reserved_birth_is_met_in_the_run(cast):
    e, _ = cast
    e.run(until=Date(4, 52, CAL.days_per_year - 1))
    assert e.director.status["v:heir:born"] in ("satisfied", "forced")
    heir = e.director.bindings["v:heir"]
    assert e.store.get(heir, "mother") == "v:bryn-ardent" and e.store.get(heir, "sex") == "m"


def test_casting_is_deterministic():
    sc = scenario()
    a, b = canon_of(sc), canon_of(sc)
    assert a[0] == b[0] and a[1] == b[1]
    assert new_engine(scenario=sc, canon=a[0]).state_hash() == new_engine(scenario=sc, canon=a[0]).state_hash()


# ---------------------------------------------------------------- runs cast from the vault


def test_a_recipe_with_a_vault_casts_it_and_a_replay_uses_the_same_canon(tmp_path, capsys):
    import json
    import shutil

    from renasci.cli import main

    vault = tmp_path / "vault"
    shutil.copytree(FIXTURE, vault)
    recipe = tmp_path / "base.toml"
    body = (f'[run]\nname = "{{name}}"\nengine = "0.1.0"\nseed = 1234\nworld = "fourth_age"\nend = "4A 12"\n'
            f'checkpoint_every_years = 4\n\n[vault]\npath = "{vault.as_posix()}"\n')
    recipe.write_text(body.format(name="base"), encoding="utf-8")
    assert main(["run", str(recipe), "--out", str(tmp_path / "runs")]) == 0
    run = tmp_path / "runs" / "base"
    canon = json.loads((run / "canon.json").read_text(encoding="utf-8"))
    casting = json.loads((run / "casting.json").read_text(encoding="utf-8"))
    assert casting["v:old-ardent"]["status"] == "placed" and canon["pins"]
    state = json.loads(__import__("gzip").decompress((run / "state.json.gz").read_bytes()))
    assert any(e["id"] == "v:old-ardent" for e in state["entities"])

    # the vault changes; a replay keeps the canon it was cast from, and says so
    (vault / "People" / "Old Ardent.md").write_text("---\nborn: 4A 2\n---\n", encoding="utf-8")
    variant = tmp_path / "variant.toml"
    variant.write_text(body.format(name="variant") + '\n[[ripple]]\nid = "r1"\nkind = "protect"\ndate = "4A 6"\n'
                       'target = "v:old-ardent"\nparams = { until = [4, 12, 359] }\n', encoding="utf-8")
    assert main(["replay", str(run), "--recipe", str(variant), "--out", str(tmp_path / "runs")]) == 0
    assert "the vault has changed" in capsys.readouterr().out
    assert json.loads((tmp_path / "runs" / "variant" / "canon.json").read_text(encoding="utf-8")) == canon
    assert main(["diff", str(run), str(tmp_path / "runs" / "variant")]) == 0


# ---------------------------------------------------------------- review regressions


def cast_copy(tmp_path, edits: dict, house2=False):
    import shutil

    root = tmp_path / "v"
    shutil.copytree(FIXTURE, root)
    for name, text in edits.items():
        (root / name).parent.mkdir(parents=True, exist_ok=True)
        (root / name).write_text(text, encoding="utf-8")
    sc = scenario()
    if house2:
        sc["houses"][1]["id"] = "v:house-bane"
        sc["houses"][1]["name"] = "Bane"
    vault = load(root)
    found = extract(vault, CAL, START, END, hooks=[people_hook])
    report = check(found, vault, START, END, hooks=[people_hook], calendar=CAL)
    canon, log = canon_from(found, vault, sc)
    return new_engine(scenario=sc, pins=feasible(found, report), canon=canon), canon, log


def test_canon_parents_are_linked_whatever_the_order_they_are_cast_in(tmp_path):
    e, _, _ = cast_copy(tmp_path, {
        "People/Kid.md": '---\nmother: "[[Cass]]"\nhouse: "[[House Ardent]]"\n---\n',  # drawn, mother placed
        "People/Mum.md": "---\nborn: 4A 2\ndied: 4A 30\nsex: f\n---\n",
        "People/Bryn Ardent.md": '---\nborn: 4A 20\nfather: "[[Old Ardent]]"\nmother: "[[Mum]]"\nsex: f\n'
                                 'house: "[[House Ardent]]"\noffices:\n  - {office: "[[House Ardent]]", from: 4A 31}\n---\n',
    })
    assert e.store.get("v:kid", "mother") == "v:cass" and "v:kid" in e.store.get("v:cass", "children")
    assert e.store.get("v:bryn-ardent", "mother") == "v:mum" and "v:bryn-ardent" in e.store.get("v:mum", "children")
    assert e.store.get("v:bryn-ardent", "father") == "v:old-ardent"


def test_a_head_whose_canon_father_heads_another_house_is_his_child(tmp_path):
    e, _, _ = cast_copy(tmp_path, {
        "Houses/House Bane.md": '---\nhead: "[[Cass]]"\n---\n',
        "People/Cass.md": '---\nborn: 4A 15\nfather: "[[Bryn Ardent]]"\nhouse: "[[House Bane]]"\n---\n',
    }, house2=True)
    assert e.store.get("v:house-bane-head", "holder") == "v:cass"
    assert e.store.get("v:cass", "father") == "v:bryn-ardent" and "v:cass" in e.store.get("v:bryn-ardent", "children")


def test_one_person_heads_one_house_only(tmp_path):
    e, canon, log = cast_copy(tmp_path, {"Houses/House Bane.md": '---\nhead: "[[Bryn Ardent]]"\n---\n'}, house2=True)
    assert list(canon["heads"].values()).count("v:bryn-ardent") == 1
    assert e.store.get("v:bryn-ardent", "house") == "v:house-ardent"
    assert e.store.get("v:house-bane-head", "holder") != "v:bryn-ardent"
    assert "only" in log["v:bryn-ardent"]["as"]


def test_no_synthesised_sibling_is_born_after_the_canon_father_died(cast):
    e, _ = cast
    died = Date(4, 30, 0)
    for p in e.store.get("v:old-ardent", "children"):
        assert Date.from_json(e.store.get(p, "born")) <= Date(4, 30, CAL.days_per_year - 1), p


def test_a_dead_parent_with_no_birth_date_is_born_before_their_children(tmp_path):
    e, _, _ = cast_copy(tmp_path, {
        "People/Mum.md": "---\ndied: 4A 30\nsex: f\n---\n",
        "People/Twin.md": '---\nborn: ~4A 25\nfather: "[[Old Ardent]]"\nmother: "[[Mum]]"\n---\n',
    })
    mum, twin = Date.from_json(e.store.get("v:mum", "born")), Date.from_json(e.store.get("v:twin", "born"))
    years = (CAL.ordinal(twin) - CAL.ordinal(mum)) // CAL.days_per_year if mum.age == twin.age else 0
    assert 16 <= years <= 45, (mum, twin)


def test_a_drawn_head_is_younger_than_their_canon_father(tmp_path):
    e, _, _ = cast_copy(tmp_path, {
        "Houses/House Ardent.md": '---\nhead: "[[Dorn Ardent]]"\nfounded: 4A 1\n---\n',
        "People/Dorn Ardent.md": '---\nfather: "[[Old Ardent]]"\nhouse: "[[House Ardent]]"\n---\n',
        "People/Bryn Ardent.md": '---\nborn: 4A 20\nfather: "[[Old Ardent]]"\nsex: f\nhouse: "[[House Ardent]]"\n---\n',
    })
    assert e.store.get("v:house-ardent-head", "holder") == "v:dorn-ardent"
    dorn, old = Date.from_json(e.store.get("v:dorn-ardent", "born")), Date.from_json(e.store.get("v:old-ardent", "born"))
    assert dorn > old


def test_the_log_names_a_head_as_head_even_without_a_house_field(tmp_path):
    _, _, log = cast_copy(tmp_path, {
        "People/Bryn Ardent.md": '---\nborn: 4A 20\nfather: "[[Old Ardent]]"\nsex: f\n'
                                 'offices:\n  - {office: "[[House Ardent]]", from: 4A 31}\n---\n'})
    assert log["v:bryn-ardent"]["as"] == "head of v:house-ardent"


def test_castable_drops_orderings_whose_pins_it_dropped():
    from renasci.core.pins import Pin
    from renasci.people.casting import castable

    w = (Date(4, 1, 0), Date(4, 2, 0))
    a = Pin("a", "event", window=w, payload={"type": "people.succession", "roles": {}, "office": "v:nowhere-head"})
    b = Pin("b", "event", window=w, payload={"type": "people.marriage", "roles": {}})
    o = Pin("a:before:b", "ordering", payload={"before": "a", "after": "b"})
    kept, dropped = castable([a, b, o], scenario())
    assert [p.id for p in kept] == ["b"] and {d["pin"] for d in dropped} == {"a", "a:before:b"}
