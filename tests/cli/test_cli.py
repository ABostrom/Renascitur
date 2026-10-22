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


# ---------------------------------------------------------------- review fixes


def ripple_at(date, until="[1, 12, 359]"):
    return f'\n[[ripple]]\nid = "r1"\nkind = "protect"\ndate = "{date}"\ntarget = "t:Ashford-00"\nparams = {{ until = {until} }}\n'


def test_moving_a_ripple_later_replays_from_before_its_old_date(runs):
    tmp, out = runs
    early = write(tmp, "early", ripple_at("1X 6"))
    assert main(["run", str(early), "--out", str(out)]) == 0
    late = write(tmp, "late", ripple_at("1X 10"))
    assert main(["replay", str(out / "early"), "--recipe", str(late), "--out", str(out)]) == 0
    assert RunFolder.open(out / "late").manifest["parent"]["segments"] == 1  # the 1X 5 checkpoint


def test_replay_refuses_changes_other_than_ripples(runs):
    tmp, out = runs
    for name, edit in (("bigger", ("people_per_village = 12", "people_per_village = 20")),
                       ("cadence", ("checkpoint_every_years = 4", "checkpoint_every_years = 3")),
                       ("longer", ('end = "1X 12"', 'end = "1X 13"'))):
        path = tmp / f"{name}.toml"
        path.write_text(RECIPE.format(name=name, extra="").replace(*edit), encoding="utf-8")
        assert main(["replay", str(out / "base"), "--recipe", str(path), "--out", str(out)]) == 1, name


def test_unknown_world_params_are_rejected(tmp_path):
    path = tmp_path / "typo.toml"
    path.write_text(RECIPE.format(name="typo", extra="").replace("people_per_village", "peopel_per_village"),
                    encoding="utf-8")
    with pytest.raises(ValueError):
        load_recipe(path)


def test_a_replayed_run_can_itself_be_replayed(runs):
    tmp, out = runs
    first = write(tmp, "gen1", ripple_at("1X 9"))
    assert main(["replay", str(out / "base"), "--recipe", str(first), "--out", str(out)]) == 0
    assert (out / "gen1" / "checkpoints" / "1-5-0.json.gz").exists()
    second = write(tmp, "gen2", ripple_at("1X 9"))
    assert main(["replay", str(out / "gen1"), "--recipe", str(second), "--from", "1X 5", "--out", str(out)]) == 0


def test_incomplete_run_folders_are_refused(runs):
    tmp, out = runs
    rf = RunFolder.create(out / "broken", {"recipe": {}, "complete": False})
    assert rf.manifest["meta"]["complete"] is False
    assert main(["diff", str(out / "base"), str(out / "broken")]) == 1
    assert main(["inspect", str(out / "broken"), "--event", "x1"]) == 1


def test_diff_signals_unexplained_divergence_with_its_own_code(runs, monkeypatch):
    import renasci.cli as cli

    tmp, out = runs
    monkeypatch.setattr(cli, "analyse", lambda *a, **k: {"events": 1, "divergent_events": 1, "unexplained_events": 1,
                                                       "unexplained_entities": 0, "unexplained_cells": 0,
                                                       "unexplained": {"events": []}})
    assert main(["diff", str(out / "base"), str(out / "base")]) == 3


def test_ripples_missing_keys_are_a_clear_error(tmp_path):
    path = tmp_path / "r.toml"
    path.write_text(RECIPE.format(name="r", extra='\n[[ripple]]\nid = "r1"\nkind = "protect"\n'), encoding="utf-8")
    with pytest.raises(ValueError):
        load_recipe(path)


def test_inspect_needs_exactly_one_target_and_shows_field_changes(runs, capsys):
    tmp, out = runs
    with pytest.raises(SystemExit):
        main(["inspect", str(out / "base")])
    capsys.readouterr()
    assert main(["inspect", str(out / "base"), "--entity", "t:Ashford-01"]) == 0
    assert "state changes:" in capsys.readouterr().out


def test_bench_appends_a_row(tmp_path, capsys):
    import csv

    history = tmp_path / "history.csv"
    assert main(["bench", "--years", "3", "--people", "8", "--history", str(history), "--out", str(tmp_path / "b")]) == 0
    assert main(["bench", "--years", "3", "--people", "8", "--history", str(history), "--out", str(tmp_path / "b")]) == 0
    rows = list(csv.DictReader(history.open(encoding="utf-8")))
    assert len(rows) == 2
    assert set(rows[0]) == {"date", "commit", "engine", "python", "numpy", "world", "years", "people_start",
                            "people_peak", "events", "seconds", "years_per_s", "events_per_s", "run_mb"}
    assert int(rows[0]["events"]) > 0 and float(rows[0]["years_per_s"]) > 0 and float(rows[0]["run_mb"]) > 0
    assert rows[0]["events"] == rows[1]["events"]  # deterministic
    assert "years/s" in capsys.readouterr().out


def test_bench_never_deletes_a_folder_that_is_not_a_bench_run(tmp_path):
    keep = tmp_path / "precious"
    keep.mkdir()
    (keep / "notes.md").write_text("keep me", encoding="utf-8")
    assert main(["bench", "--years", "1", "--people", "4", "--out", str(keep),
                 "--history", str(tmp_path / "h.csv")]) == 1
    assert (keep / "notes.md").exists()
    assert main(["bench", "--years", "0", "--out", str(tmp_path / "b"), "--history", str(tmp_path / "h.csv")]) == 1


def test_bench_refuses_a_history_with_other_columns(tmp_path):
    history = tmp_path / "h.csv"
    history.write_text("date,something\n", encoding="utf-8")
    assert main(["bench", "--years", "1", "--people", "4", "--out", str(tmp_path / "b"),
                 "--history", str(history)]) == 1
