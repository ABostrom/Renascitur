import json

import pytest

from renasci.cli import main
from renasci.io.recipe import load_recipe
from renasci.io.runfolder import RunFolder

RECIPE = """
[run]
name = "{name}"
engine = "0.1.0"
seed = 1234
world = "toy"
end = "1X 12"
checkpoint_every_years = 4

[world]
people_per_village = 12
{extra}
"""

PROTECT = """
[[ripple]]
id = "r1"
kind = "protect"
date = "1X 5"
target = "t:Ashford-00"
params = { until = [1, 12, 359] }
"""


def write(tmp_path, name, extra=""):
    path = tmp_path / f"{name}.toml"
    path.write_text(RECIPE.format(name=name, extra=extra), encoding="utf-8")
    return path


# ---------------------------------------------------------------- recipes


def test_recipes_load_and_validate(tmp_path):
    r = load_recipe(write(tmp_path, "base", PROTECT))
    assert r.name == "base" and r.seed == 1234 and r.world == "toy"
    assert [x.id for x in r.ripples] == ["r1"] and r.ripples[0].date.year == 5
    bad = tmp_path / "bad.toml"
    bad.write_text('[run]\nname="x"\nengine="0.1.0"\nseed=1\nworld="toy"\nend="1X 2"\nmystery=1\n', encoding="utf-8")
    with pytest.raises(ValueError):
        load_recipe(bad)
    wrong = tmp_path / "wrong.toml"
    wrong.write_text(RECIPE.format(name="w", extra="").replace('"0.1.0"', '"9.9"'), encoding="utf-8")
    with pytest.raises(ValueError):
        load_recipe(wrong)


# ---------------------------------------------------------------- run, replay, diff, inspect


@pytest.fixture(scope="module")
def runs(tmp_path_factory):
    tmp = tmp_path_factory.mktemp("cli")
    out = tmp / "runs"
    assert main(["run", str(write(tmp, "base")), "--out", str(out)]) == 0
    return tmp, out


def test_run_writes_a_folder_with_checkpoints_and_state(runs):
    tmp, out = runs
    rf = RunFolder.open(out / "base")
    assert rf.manifest["segments"] >= 3
    assert [m["before"] for m in rf.manifest["marks"]] == [[1, 5, 0], [1, 9, 0]]
    assert sorted(p.name for p in (out / "base" / "checkpoints").iterdir()) == ["1-5-0.json.gz", "1-9-0.json.gz"]
    assert (out / "base" / "state.json.gz").exists()
    assert rf.manifest["meta"]["recipe"]["run"]["name"] == "base"
    assert any(e["type"] == "toy.birth" for e in rf.read("events"))


def test_replay_with_a_new_ripple_forks_from_the_right_checkpoint_and_diffs_clean(runs, capsys):
    tmp, out = runs
    variant = write(tmp, "protected", PROTECT)
    assert main(["replay", str(out / "base"), "--recipe", str(variant), "--out", str(out)]) == 0
    rf = RunFolder.open(out / "protected")
    assert rf.manifest["parent"] == {"run": "base", "segments": 1}  # forked at the 1X 5 checkpoint
    capsys.readouterr()
    assert main(["diff", str(out / "base"), str(out / "protected")]) == 0
    report = json.loads((out / "protected" / "analysis" / "divergence.json").read_text(encoding="utf-8"))
    assert report["unexplained_events"] == 0 and report["unexplained_entities"] == 0
    assert "unexplained" in capsys.readouterr().out


def test_replay_without_changes_reproduces_the_run(runs):
    tmp, out = runs
    same = write(tmp, "again")
    assert main(["replay", str(out / "base"), "--recipe", str(same), "--from", "1X 9", "--out", str(out)]) == 0
    a = list(RunFolder.open(out / "base").read("events"))
    b = list(RunFolder.open(out / "again").read("events"))
    assert a == b


def test_replay_refuses_a_changed_recipe(runs):
    tmp, out = runs
    changed = tmp / "changed.toml"
    changed.write_text(RECIPE.format(name="changed", extra="").replace("seed = 1234", "seed = 99"), encoding="utf-8")
    assert main(["replay", str(out / "base"), "--recipe", str(changed), "--out", str(out)]) != 0


def test_inspect_prints_an_event_with_its_causes(runs, capsys):
    tmp, out = runs
    birth = next(e for e in RunFolder.open(out / "base").read("events") if e["type"] == "toy.birth")
    capsys.readouterr()
    assert main(["inspect", str(out / "base"), "--event", birth["id"]]) == 0
    text = capsys.readouterr().out
    assert birth["id"] in text and "toy.birth" in text
    child = birth["roles"]["child"][0]
    assert main(["inspect", str(out / "base"), "--entity", child]) == 0
    assert child in capsys.readouterr().out
