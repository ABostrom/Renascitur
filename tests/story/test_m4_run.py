"""Step 0 of the story layer (S12 spec §1a): beliefs can be turned on from a recipe, and the M4 recipe
(the Fourth Age with beliefs and the ward failure) is the run the story layer is built and tested on."""

import json

import pytest

from renasci.cli import main
from renasci.io.recipe import load_recipe, parse_recipe

BASE = '[run]\nname = "{name}"\nengine = "0.1.0"\nseed = 1\nworld = "fourth_age"\nend = "4A 3"\n\n'


def events(folder):
    from renasci.io.runfolder import RunFolder

    return list(RunFolder.open(folder).read("events"))


def test_a_recipe_can_turn_beliefs_on(tmp_path):
    (tmp_path / "b.toml").write_text(BASE.format(name="b") + '[world]\nbeliefs = true\n\n[[ripple]]\nid = "ward"\n'
                                     'kind = "inject"\ndate = "4A 2"\ntarget = "v:lux-oescus"\n'
                                     'params = { script = "ward_failure" }\n', encoding="utf-8")
    assert main(["run", str(tmp_path / "b.toml"), "--out", str(tmp_path / "runs")]) == 0
    types = {e["type"] for e in events(tmp_path / "runs" / "b")}
    assert "ward.failure" in types and "belief.told" in types


def test_without_it_there_are_no_beliefs(tmp_path):
    (tmp_path / "n.toml").write_text(BASE.format(name="n"), encoding="utf-8")
    assert main(["run", str(tmp_path / "n.toml"), "--out", str(tmp_path / "runs")]) == 0
    assert not any(e["type"].startswith("belief.") for e in events(tmp_path / "runs" / "n"))


def test_beliefs_must_be_true_or_false():
    raw = {"run": {"name": "x", "engine": "0.1.0", "seed": 1, "world": "fourth_age", "end": "4A 3"},
           "world": {"beliefs": "yes"}}
    with pytest.raises(ValueError):
        from renasci.worlds import get_world

        get_world("fourth_age").new_engine(1, **parse_recipe(raw).params)


def test_the_m4_recipe_is_the_fourth_age_with_beliefs_and_the_ward_failure():
    from pathlib import Path

    r = load_recipe(Path(__file__).resolve().parents[2] / "recipes" / "m4.toml")
    assert r.world == "fourth_age" and r.params.get("beliefs") is True
    assert [(x.kind, x.params.get("script")) for x in r.ripples] == [("inject", "ward_failure")]
