"""The canon-check benchmark on the M4 run (S12 spec §4, #117): seeded recall is gated at 0.9; precision on
the unseeded set and recall on the held-out free prose are reported. And `renasci check-prose`."""

import json

import pytest

from renasci.story.bench import KINDS, PER_KIND, items, run_bench


@pytest.fixture(scope="module")
def bench(m4run):
    return run_bench(m4run)


def test_the_seeded_set_has_every_kind_and_is_the_same_each_time(m4run):
    first, again = items(m4run), items(m4run)
    assert first == again
    kinds = {it["kind"] for it in first["seeded"]}
    assert kinds == set(KINDS) and all(sum(1 for it in first["seeded"] if it["kind"] == k) <= PER_KIND for k in KINDS)
    assert len(first["seeded"]) >= 40 and len(first["unseeded"]) >= 40


def test_seeded_recall_is_at_least_nine_in_ten(bench):
    print(f"\ncanon-check bench: seeded recall {bench['recall']} ({bench['seeded']}), by kind {bench['by_kind']}; "
          f"unseeded precision {bench['precision']} ({bench['false_alarms']} false alarms of {bench['unseeded']})")
    assert bench["recall"] >= 0.9, bench["missed"]


def test_the_held_out_recall_is_reported(bench):
    if "heldout" not in bench:
        pytest.skip("the held-out prose lives in the repo's tests/fixtures")
    held = bench["heldout"]
    print(f"\ncanon-check held-out: recall {held['recall']} on {held['contradictions']} contradictions in "
          f"{held['sentences']} sentences, {held['false_alarms']} false alarms; missed: {held['missed']}")
    assert held["sentences"] >= 40 and 0 <= held["recall"] <= 1  # (reported, not gated)


def test_renasci_check_prose(m4, tmp_path, capsys):
    from renasci.cli import main

    prose = tmp_path / "tale.md"
    prose.write_text("# A tale\n\nIn 4A 9, Bessa of House Silverhand slew Hask of House Silverhand.\n\n"
                     "Ivor of House Sivis died in 4A 2.\n", encoding="utf-8")
    assert main(["check-prose", str(m4), str(prose)]) == 0
    out = capsys.readouterr().out
    assert "contradiction" in out.split("\n")[0]
    [report] = (m4 / "analysis" / "checks").glob("*.json")
    rep = json.loads(report.read_text(encoding="utf-8"))
    assert rep["counts"]["contradiction"] == 1 and rep["counts"]["consistent"] >= 1
    assert main(["check-prose", str(m4), str(prose), "--pov", "p:nobody"]) != 0
