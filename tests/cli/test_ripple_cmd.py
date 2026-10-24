"""`renasci ripple <run>`: author one ripple on a run and see what it does, without a recipe (#110).

It forks the run at the checkpoint before the ripple, with the run's own recipe plus the ripple (so a
branch of a branch keeps its parent's ripples), and diffs the new run against the one it came from."""

import json

import pytest

from renasci.cli import main

RECIPE = """
[run]
name = "base"
engine = "0.1.0"
seed = 1234
world = "toy"
end = "1X 6"
checkpoint_every_years = 2

[world]
people_per_village = 6
"""


@pytest.fixture(scope="module")
def runs(tmp_path_factory):
    tmp = tmp_path_factory.mktemp("ripple")
    (tmp / "base.toml").write_text(RECIPE, encoding="utf-8")
    assert main(["run", str(tmp / "base.toml"), "--out", str(tmp / "runs")]) == 0
    return tmp / "runs"


def manifest(runs, name):
    return json.loads((runs / name / "manifest.json").read_text(encoding="utf-8"))


def test_a_ripple_forks_the_run_and_diffs_it(runs):
    assert main(["ripple", str(runs / "base"), "--kind", "doom", "--target", "t:Brook-02", "--date", "1X 4",
                 "--out", str(runs)]) == 0
    m = manifest(runs, "base-doom1")
    assert m["meta"]["replayed_from"]["run"] == "base"
    assert m["meta"]["recipe"]["ripple"] == [{"id": "doom1", "kind": "doom", "date": "1X 4 m1 d1",
                                              "target": "t:Brook-02", "params": {}}]
    report = json.loads((runs / "base-doom1" / "analysis" / "divergence.json").read_text(encoding="utf-8"))
    assert report["runs"] == {"baseline": "base", "variant": "base-doom1"} and report["unexplained_events"] == 0


def test_a_branch_of_a_branch_keeps_its_parents_ripples(runs):
    if not (runs / "base-doom1").exists():
        test_a_ripple_forks_the_run_and_diffs_it(runs)
    assert main(["ripple", str(runs / "base-doom1"), "--kind", "protect", "--target", "t:Ashford-00",
                 "--date", "1X 5", "--params", '{"until": [1, 6, 359]}', "--name", "both", "--out", str(runs)]) == 0
    ripples = manifest(runs, "both")["meta"]["recipe"]["ripple"]
    assert [r["id"] for r in ripples] == ["doom1", "protect2"]
    assert manifest(runs, "both")["meta"]["replayed_from"]["run"] == "base-doom1"


@pytest.mark.parametrize("kind, params, target", [("smite", None, "t:Brook-02"), ("doom", "[1]", "t:Brook-02"),
                                                  ("doom", "{bad", "t:Brook-02"), ("protect", None, "t:Brook-02"),
                                                  ("doom", None, "t:Nobody-99")])  # (protect: no until; a typo)
def test_a_bad_ripple_is_refused(runs, kind, params, target):
    args = ["ripple", str(runs / "base"), "--kind", kind, "--target", target, "--date", "1X 4",
            "--name", "nope", "--out", str(runs)] + (["--params", params] if params else [])
    try:
        code = main(args)
    except SystemExit as e:  # (argparse refuses an unknown kind itself)
        code = e.code
    assert code != 0 and not (runs / "nope").exists()


def test_a_name_that_is_taken_is_refused_before_any_work(runs):
    (runs / "taken").mkdir(exist_ok=True)
    assert main(["ripple", str(runs / "base"), "--kind", "doom", "--target", "t:Brook-02", "--date", "1X 4",
                 "--name", "taken", "--out", str(runs)]) != 0
    assert list((runs / "taken").iterdir()) == []
