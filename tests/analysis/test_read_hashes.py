"""#151: reads are kept as one digest per scope by default; `full_reads` keeps every row (analysis runs)."""

import json

import pytest

from renasci.analysis.divergence import analyse
from renasci.cli import main
from renasci.core.calendar import Date
from renasci.core.context import reads_digest
from renasci.core.ripples import Ripple
from renasci.toy import VALLEYS, new_engine

END = Date(1, 30, 359)


def run(full=False, **kw):
    e = new_engine(people_per_village=16, **kw)
    e.full_reads = full
    e.run(until=END)
    return e.pending(), e.store.to_json()


@pytest.fixture(scope="module")
def runs():
    """Baseline and a protect replay, each recorded both ways, plus the buggy pair hash-only."""
    base_h, base_f = run(), run(full=True)
    for ev in base_f[0]["events"]:
        if ev["type"] == "toy.death" and ev["place"] in VALLEYS["t:North"] and 4 <= ev["date"][1] <= 15:
            person, died = ev["roles"]["deceased"][0], ev["date"]
            break
    ripple = Ripple("r1", "protect", Date(1, died[1] - 1, 0), person, {"until": [1, 30, 359]})
    return {"base": (base_h, base_f), "protected": (run(ripples=[ripple]), run(full=True, ripples=[ripple])),
            "buggy": (run(buggy=True), run(buggy=True, ripples=[ripple]))}


def test_default_rows_are_digests_and_full_rows_digest_the_same(runs):
    (hashed, _), (full, _) = runs["base"]
    assert hashed["reads"] and all("reads" not in r and {"digest", "n"} <= set(r) for r in hashed["reads"])
    assert all("reads" in r for r in full["reads"])
    by_key = {(r["activation"], r["scope"]): r for r in hashed["reads"]}
    for r in full["reads"]:
        h = by_key[(r["activation"], r["scope"])]
        assert h["digest"] == reads_digest(r["reads"]) and h["n"] == len(r["reads"]) and h["events"] == r["events"]


def test_events_and_state_do_not_depend_on_how_reads_are_kept(runs):
    (hashed, s1), (full, s2) = runs["base"]
    assert hashed["events"] == full["events"] and s1 == s2


def test_digests_are_much_smaller(runs):
    (hashed, _), (full, _) = runs["base"]
    size = lambda rows: len(json.dumps(rows))  # noqa: E731
    assert size(hashed["reads"]) * 3 < size(full["reads"])


@pytest.mark.parametrize("base_full, variant_full", [(False, False), (True, False), (False, True), (True, True)])
def test_a_protect_ripple_is_explained_however_reads_were_kept(runs, base_full, variant_full):
    base, variant = runs["base"][base_full], runs["protected"][variant_full]
    report = analyse(base[0], variant[0], base[1], variant[1], ripples=["r1"])
    assert report["divergent_events"] > 0
    assert report["unexplained_events"] == report["unexplained_entities"] == report["unexplained_cells"] == 0


def test_the_planted_bug_is_caught_from_digests_alone(runs):
    base, variant = runs["buggy"]
    report = analyse(base[0], variant[0], base[1], variant[1], ripples=["r1"])
    assert report["unexplained_events"] > 0 or report["unexplained_entities"] > 0


def test_the_recipe_flag_keeps_full_reads(tmp_path):
    recipe = tmp_path / "r.toml"
    recipe.write_text("""
[run]
name = "{n}"
engine = "0.1.0"
seed = 1234
world = "toy"
end = "1X 2"
{extra}
[world]
people_per_village = 4
""".format(n="full", extra="full_reads = true"), encoding="utf-8")
    assert main(["run", str(recipe), "--out", str(tmp_path / "runs")]) == 0
    from renasci.io.runfolder import RunFolder

    rows = list(RunFolder.open(tmp_path / "runs" / "full").read("reads"))
    assert rows and all("reads" in r for r in rows)
    bad = tmp_path / "bad.toml"
    bad.write_text(recipe.read_text(encoding="utf-8").replace("full_reads = true", 'full_reads = "yes"'),
                   encoding="utf-8")
    assert main(["run", str(bad), "--out", str(tmp_path / "runs2")]) != 0  # reported, not run


# ---------------------------------------------------------------- review fixes


def test_the_report_says_how_reads_were_kept(runs):
    full, hashed = runs["base"][1], runs["base"][0]
    assert analyse(full[0], full[0], full[1], full[1])["reads"] == "full"
    assert analyse(hashed[0], hashed[0], hashed[1], hashed[1])["reads"] == "digest"
    assert analyse(full[0], hashed[0], full[1], hashed[1])["reads"] == "mixed"


def test_a_replay_may_change_full_reads_and_diff_warns_about_digests(tmp_path, capsys):
    text = """
[run]
name = "{n}"
engine = "0.1.0"
seed = 1234
world = "toy"
end = "1X 4"
checkpoint_every_years = 2
{extra}
[world]
people_per_village = 4
{ripple}
"""
    ripple = '[[ripple]]\nid = "r1"\nkind = "doom"\ndate = "1X 3"\ntarget = "t:Brook-02"\n'
    base, variant = tmp_path / "b.toml", tmp_path / "v.toml"
    base.write_text(text.format(n="base", extra="", ripple=""), encoding="utf-8")
    variant.write_text(text.format(n="var", extra="full_reads = true", ripple=ripple), encoding="utf-8")
    out = tmp_path / "runs"
    assert main(["run", str(base), "--out", str(out)]) == 0
    assert main(["replay", str(out / "base"), "--recipe", str(variant), "--out", str(out)]) == 0
    capsys.readouterr()
    main(["diff", str(out / "base"), str(out / "var")])
    printed = capsys.readouterr().out
    report = json.loads((out / "var" / "analysis" / "divergence.json").read_text(encoding="utf-8"))
    assert report["reads"] in ("digest", "mixed") and "full_reads" in printed
