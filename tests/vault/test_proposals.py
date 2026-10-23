"""Proposals (S2 spec §9, #64): run-made notes as `canon: proposed`, never over an edit; promotion; stale.

A House Ardent world (as in test_casting), seed 1: Twin, a canon character, fathers a child in 4A 41. The
child is proposed, promoted, and becomes canon: the next run meets its birth pin.
"""

import shutil
import sys
from pathlib import Path

import pytest

from renasci.core.calendar import Date
from renasci.people.casting import canon_from
from renasci.people.vault import people_hook
from renasci.renascita import CAL, new_engine
from renasci.vault.feasibility import check, feasible
from renasci.vault.loader import load
from renasci.vault.pins import extract
from renasci.vault.proposals import propose, stale, write_proposal

sys.path.insert(0, str(Path(__file__).parent))
from test_casting import END, FIXTURE, START, scenario  # noqa: E402

CHILD = "e42900ab301eb29f6"


def cast_and_run(root, seed=1, until=Date(4, 45, 0)):
    sc = scenario()
    vault = load(root)
    found = extract(vault, CAL, START, END, hooks=[people_hook])
    report = check(found, vault, START, END, hooks=[people_hook], calendar=CAL)
    canon, _ = canon_from(found, vault, sc)
    e = new_engine(seed=seed, scenario=sc, pins=feasible(found, report), canon=canon)
    e.run(until=until)
    return e, vault


@pytest.fixture(scope="module")
def world(tmp_path_factory):
    root = tmp_path_factory.mktemp("prop") / "vault"
    shutil.copytree(FIXTURE, root)
    e, vault = cast_and_run(root)
    return root, e, vault


def proposal(world):
    root, e, vault = world
    return propose(e.store.to_json(), e.pending()["events"], CHILD, vault, CAL,
                   source={"run": "base", "state_hash": "abc"})


def test_a_run_person_with_canon_parents_becomes_a_proposed_character_note(world):
    rel, text, notes = proposal(world)
    assert rel.startswith("_proposed/character/")
    assert "canon: proposed" in text and "type: character" in text
    assert 'father: "[[Twin]]"' in text and "born: 4A 41" in text
    assert "generated_hash:" in text and "run: base" in text
    assert any("mother" in n for n in notes)  # the non-canon mother is named in the report, not linked


def test_the_writer_regenerates_an_untouched_proposal_but_never_overwrites_an_edit(world, tmp_path):
    root = tmp_path / "v"
    shutil.copytree(world[0], root)
    rel, text, _ = proposal(world)
    assert write_proposal(root, rel, text) == rel
    assert write_proposal(root, rel, text) == rel  # untouched: regenerated in place
    p = root / rel
    p.write_text(p.read_text(encoding="utf-8") + "\nMy own words.\n", encoding="utf-8")
    other = write_proposal(root, rel, text)
    assert other != rel and other.endswith("-2.md") and "My own words." in p.read_text(encoding="utf-8")


def test_a_promoted_proposal_round_trips_to_a_birth_pin_the_next_run_meets(world, tmp_path):
    root = tmp_path / "v"
    shutil.copytree(world[0], root)
    rel, text, _ = proposal(world)
    write_proposal(root, rel, text)
    assert not any(k.startswith("_proposed") for k in load(root).notes)  # still proposed: not canon
    p = root / rel
    p.write_text(p.read_text(encoding="utf-8").replace("canon: proposed", "canon: true"), encoding="utf-8")
    vault = load(root)
    key = next(k for k in vault.notes if k.startswith("_proposed"))
    assert ("promoted_in_proposed", key) in {(f["kind"], f["key"]) for f in vault.findings}
    e, _ = cast_and_run(root)
    cid = vault.notes[key].id
    assert e.director.status[f"{cid}:born"] in ("satisfied", "forced")
    assert e.director.bindings[cid] == CHILD  # the same child, now canon


def test_untouched_proposals_from_a_changed_or_missing_run_are_stale(world, tmp_path):
    root = tmp_path / "v"
    shutil.copytree(world[0], root)
    rel, text, _ = proposal(world)
    write_proposal(root, rel, text)
    runs = tmp_path / "runs"
    (runs / "base").mkdir(parents=True)
    (runs / "base" / "manifest.json").write_text('{"meta": {"state_hash": "abc"}}', encoding="utf-8")
    assert stale(root, runs) == []
    (runs / "base" / "manifest.json").write_text('{"meta": {"state_hash": "def"}}', encoding="utf-8")
    assert [s["path"] for s in stale(root, runs)] == [rel]
    shutil.rmtree(runs / "base")
    assert [s["why"] for s in stale(root, runs)] == ["its run base is gone"]
    p = root / rel
    p.write_text(p.read_text(encoding="utf-8") + "\nedited\n", encoding="utf-8")
    assert stale(root, runs) == []  # an edited proposal is Aaron's now, never listed


def test_renasci_vault_propose_and_stale(tmp_path, capsys):
    import json

    from renasci.cli import main

    vault = tmp_path / "vault"
    shutil.copytree(FIXTURE, vault)
    recipe = tmp_path / "base.toml"
    recipe.write_text(f'[run]\nname = "base"\nengine = "0.1.0"\nseed = 1234\nworld = "fourth_age"\nend = "4A 6"\n'
                      f'checkpoint_every_years = 3\n\n[vault]\npath = "{vault.as_posix()}"\n', encoding="utf-8")
    assert main(["run", str(recipe), "--out", str(tmp_path / "runs")]) == 0
    run = tmp_path / "runs" / "base"
    births = [json.loads(line) for line in __import__("gzip").open(next((run / "events").glob("*.gz")), "rt",
                                                                     encoding="utf-8")]
    child = next(e["roles"]["child"][0] for e in births if e["type"] == "people.birth")
    capsys.readouterr()
    assert main(["vault", "propose", str(run), child, str(vault)]) == 0  # a dry run
    out = capsys.readouterr().out
    assert "canon: proposed" in out and "--write" in out and not (vault / "_proposed").exists()
    assert main(["vault", "propose", str(run), child, str(vault), "--write"]) == 0
    assert list((vault / "_proposed" / "character").glob("*.md"))
    assert main(["vault", "stale", str(vault), "--runs", str(tmp_path / "runs")]) == 0
    assert "no stale proposals" in capsys.readouterr().out


# ---------------------------------------------------------------- review regressions


def fake_state(name="Daia", eid="e1", **fields):
    return {"entities": [{"id": eid, "kind": "person", "status": "active",
                          "fields": {"name": name, "born": [4, 41, 90], "sex": "f", **fields}}]}


def test_two_people_with_one_name_get_two_proposals_and_two_ids(world, tmp_path):
    root = tmp_path / "v"
    shutil.copytree(world[0], root)
    vault = load(root)
    a = propose(fake_state(eid="e1"), [], "e1", vault, CAL, source={"run": "r"})
    rel_a = write_proposal(root, a[0], a[1])
    b = propose(fake_state(eid="e2"), [], "e2", load(root), CAL, source={"run": "r"})
    rel_b = write_proposal(root, b[0], b[1])
    assert rel_a != rel_b and (root / rel_a).exists() and (root / rel_b).exists()
    ids = [line for t in (a[1], b[1]) for line in t.splitlines() if line.startswith("id: ")]
    assert len(set(ids)) == 2
    from renasci.vault.ids import assign
    assert not set(assign(load(root)).values()) & {i.split()[1] for i in ids}  # proposals' ids are reserved


def test_bound_canon_ids_link_and_canon_people_are_not_proposed_again(world):
    _, _, vault = world
    state = fake_state(eid="kid", mother="e42900ab301eb29f6")
    _, text, notes = propose(state, [], "kid", vault, CAL, source={"run": "r"},
                             bindings={"v:twin": "ent-twin", "v:heir": "e42900ab301eb29f6"})
    assert 'mother: "[[Heir]]"' in text and not notes
    with pytest.raises(ValueError, match="already canon"):
        propose(fake_state(eid="e42900ab301eb29f6"), [], "e42900ab301eb29f6", vault, CAL, source={"run": "r"},
                bindings={"v:heir": "e42900ab301eb29f6"})


def test_bookkeeping_events_and_events_without_people_are_not_proposed(world):
    _, _, vault = world
    for ev in ({"id": "x1", "type": "engine.cast_column", "date": [4, 40, 0], "roles": {}, "payload": {}},
               {"id": "x2", "type": "people.marriage", "date": [4, 40, 0], "roles": {}, "payload": {}}):
        with pytest.raises(ValueError):
            propose({"entities": []}, [ev], ev["id"], vault, CAL, source={"run": "r"})


@pytest.mark.parametrize("fm", ["canon: false", "canon: Proposed", "canon: proposed", ""])
def test_only_a_real_promotion_loads_from_proposed(tmp_path, fm):
    root = tmp_path / "v"
    (root / "_proposed" / "character").mkdir(parents=True)
    text = f"---\n{fm}\ntype: character\n---\nbody\n" if fm else "no frontmatter\n"
    (root / "_proposed" / "character" / "X.md").write_text(text, encoding="utf-8")
    assert "_proposed/character/X" not in load(root).notes


def test_a_promotion_loads(tmp_path):
    root = tmp_path / "v"
    (root / "_proposed" / "character").mkdir(parents=True)
    (root / "_proposed" / "character" / "X.md").write_text("---\ncanon: true\ntype: character\n---\n", encoding="utf-8")
    (root / "_proposed" / "character" / "Y.md").write_text("---\ntype: character\n---\n", encoding="utf-8")
    assert {"_proposed/character/X", "_proposed/character/Y"} <= set(load(root).notes)


def test_a_decomposed_name_is_untouched_when_regenerated(world, tmp_path):
    import unicodedata

    root = tmp_path / "v"
    shutil.copytree(world[0], root)
    rel, text, _ = propose(fake_state(name=unicodedata.normalize("NFD", "José")), [], "e1", load(root), CAL,
                           source={"run": "r"})
    assert write_proposal(root, rel, text) == write_proposal(root, rel, text)


def test_the_name_is_kept_in_the_frontmatter_whatever_the_filename(world):
    _, _, vault = world
    rel, text, _ = propose(fake_state(name='Al "the: Bold" / ?*.'), [], "e1", vault, CAL, source={"run": "r"})
    from renasci.vault.frontmatter import parse
    assert parse(text)[0]["name"] == 'Al "the: Bold" / ?*.'
    assert not rel.removesuffix(".md").endswith((".", " ")) and "?" not in rel
