"""Hard truths (#165): a world that starts with what you chose to keep."""

import gzip
import json
import textwrap

import pytest

from renasci import renascita, truths
from renasci.core.calendar import Span

VILLAGE = {"id": "v:ashfall", "name": "Ashfall", "kind": "village", "region": "v:flame-coast", "masses": 300,
           "near": [{"to": "v:port-ardere", "days": 3}]}
RUIN = {"id": "v:old-keep", "name": "the Old Keep", "kind": "ruin", "region": "v:flame-coast",
        "near": [{"to": "v:port-ardere", "days": 2}]}
BLADE = {"id": "t:thirsting", "name": "the Thirsting Blade", "type": "blade", "material": "iron", "place": "v:old-keep",
         "fame": 1.0, "from": "the Third Age"}
DOC = {"places": [VILLAGE, RUIN], "objects": [BLADE]}


def engine(doc=DOC, seed=3):
    sc = truths.apply(renascita._scenario(None, crafts=True), doc)
    return renascita.new_engine(seed=seed, scenario=sc)


def years(e, n):
    e.run(until=renascita.CAL.add(renascita.START, Span(years=n)))
    return e


def test_a_kept_village_is_a_town_with_people_and_a_road():
    e = engine()
    assert "v:ashfall" in e.store.ids("settlement")
    assert e.store.get("v:ashfall", "residents") and int(e.store.read_column("pop:m:3", ["v:ashfall"])[0]) >= 0
    assert "g:v:ashfall--v:port-ardere" in e.store.ids("route")
    years(e, 3)
    assert [x for x in e.events if x.type == "people.population" and x.place == "v:ashfall"]
    assert e.check_conservation() == []


def test_a_ruin_is_a_place_nobody_lives():
    e = engine()
    assert "v:old-keep" not in e.store.ids("settlement")
    assert e.store.get("v:old-keep", "residents") is None


def test_a_sword_lies_lost_until_someone_a_road_away_finds_it():
    e = engine()
    assert e.store.get("t:thirsting", "lost") is not None and e.store.get("t:thirsting", "owner") is None
    assert e.store.get("t:thirsting", "origin") == "the Third Age"
    years(e, 30)
    found = [x for x in e.events if x.type == "object.found" and x.roles["object"] == ("t:thirsting",)]
    assert found and e.store.get("t:thirsting", "owner")


def test_a_truth_replays_the_same():
    a, b = years(engine(), 2), years(engine(), 2)
    assert [x.id for x in a.events] == [x.id for x in b.events]


@pytest.mark.parametrize("doc, says", [
    ({"towns": []}, "truth file"),
    ({"places": [{**VILLAGE, "region": "v:nowhere"}]}, "region"),
    ({"places": [{**VILLAGE, "id": "v:lions-rest"}]}, "new"),
    ({"places": [{**VILLAGE, "kind": "castle"}]}, "kind"),
    ({"places": [{**VILLAGE, "near": [{"to": "v:nowhere", "days": 3}]}]}, "road"),
    ({"objects": [{**BLADE, "type": "spoon"}]}, "crafts"),
    ({"objects": [{**BLADE, "material": "starlight"}]}, "made of"),
    ({"objects": [{**BLADE, "place": "v:nowhere"}]}, "nowhere"),
    ({"places": None}, "truth file"),
    ({"places": [{**VILLAGE, "race": "r:nothing"}]}, "race"),
    ({"places": [{**VILLAGE, "masses": -1}]}, "masses"),
])
def test_a_truth_the_world_cannot_hold_is_refused(doc, says):
    with pytest.raises(ValueError, match=says):
        truths.apply(renascita._scenario(None, crafts=True), doc)


def recipe(path, name, file):
    path.write_text(textwrap.dedent(f"""
        [run]
        name = "{name}"
        engine = "0.1.0"
        seed = 3
        world = "fourth_age"
        end = "4A 3"

        [world]
        crafts = true
        truths = "{file}"
    """), encoding="utf-8")
    return str(path)


def state(folder):
    return json.loads(gzip.decompress((folder / "state.json.gz").read_bytes()))


def test_the_loop_a_recipe_names_a_truth_file_and_a_run_keeps_into_one(tmp_path):
    from renasci.cli import main

    file = tmp_path / "world.json"
    file.write_text(json.dumps(DOC), encoding="utf-8")
    out = tmp_path / "runs"
    assert main(["run", recipe(tmp_path / "a.toml", "a", "world.json"), "--out", str(out)]) == 0
    entities = {x["id"] for x in state(out / "a")["entities"]}
    assert {"v:ashfall", "t:thirsting"} <= entities

    kept = tmp_path / "next.json"
    assert main(["keep", str(out / "a"), "t:thirsting", "--to", str(kept)]) == 0
    assert main(["keep", str(out / "a"), "t:thirsting", "--to", str(kept)]) == 1  # (once)
    entry = json.loads(kept.read_text(encoding="utf-8"))["objects"][0]
    assert entry["name"] == "the Thirsting Blade" and entry["from"] == "a" and entry["id"] == "t:the-thirsting-blade"
    assert (out / "a" / "truths.json").read_bytes() == file.read_bytes()


def test_a_town_cannot_be_kept_into_the_world_it_is_in():
    state = {"entities": [{"id": "v:x", "kind": "settlement", "status": "active", "fields": {}}]}
    with pytest.raises(ValueError, match="isn't built yet"):
        truths.keep(state, "v:x", "a")


def test_a_kept_thing_can_join_the_run_that_made_it(tmp_path):
    state = {"entities": [{"id": "e1", "kind": "object", "status": "active",
                           "fields": {"name": None, "type": "blade", "material": "iron", "place": "v:lions-rest",
                                      "owner": "p"}},
                          {"id": "p", "kind": "person", "status": "active", "fields": {"place": "v:port-ardere"}}]}
    section, entry = truths.keep(state, "e1", "a")
    assert section == "objects" and entry["id"] == "t:blade-e1" and entry["place"] == "v:port-ardere"
    assert entry["id"] != "e1"  # (a re-run may make e1 again)
    file = tmp_path / "t.json"
    truths.add(file, section, entry)
    with pytest.raises(ValueError, match="already"):
        truths.add(file, section, entry)
    truths.apply(renascita._scenario(None, crafts=True), truths.load(file))


def test_what_lies_in_a_ruin_can_be_found_where_beliefs_are_held():
    sc = truths.apply(renascita._scenario(None, crafts=True, beliefs=True), DOC)
    e = renascita.new_engine(seed=3, scenario=sc)
    years(e, 30)
    assert [x for x in e.events if x.type == "object.found"]


def test_a_village_of_no_masses_still_has_room():
    sc = truths.apply(renascita._scenario(None, crafts=True), {"places": [{**VILLAGE, "masses": 0}]})
    assert next(s for s in sc["settlements"] if s["id"] == "v:ashfall")["capacity"] > 0


def replay_recipe(tmp_path, name, file):
    return recipe(tmp_path / f"{name}.toml", name, file)


def test_a_replay_uses_the_runs_own_truths_and_refuses_an_edit(tmp_path, monkeypatch):
    from renasci.cli import main

    file = tmp_path / "world.json"
    file.write_text(json.dumps(DOC), encoding="utf-8")
    out = tmp_path / "runs"
    path = recipe(tmp_path / "a.toml", "a", "world.json").replace('end = "4A 3"', "")
    text = (tmp_path / "a.toml").read_text(encoding="utf-8").replace("[run]\n", "[run]\ncheckpoint_every_years = 1\n")
    (tmp_path / "a.toml").write_text(text, encoding="utf-8")
    assert main(["run", path, "--out", str(out)]) == 0
    again = tmp_path / "b.toml"
    again.write_text(text.replace('name = "a"', 'name = "b"'), encoding="utf-8")
    file.unlink()  # (the run still has its own)
    assert main(["replay", str(out / "a"), "--recipe", str(again), "--from", "4A 2", "--out", str(out)]) == 0
    file.write_text(json.dumps({"places": [VILLAGE]}), encoding="utf-8")
    again.write_text(text.replace('name = "a"', 'name = "c"'), encoding="utf-8")
    assert main(["replay", str(out / "a"), "--recipe", str(again), "--from", "4A 2", "--out", str(out)]) == 1
