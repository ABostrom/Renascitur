"""Feasibility (S2 spec §8, #62): S1's pass plus the people checks; infeasible pins are dropped, with reasons."""

import pytest

from renasci.core.calendar import Date
from renasci.people.races import Race
from renasci.people.vault import people_hook
from renasci.renascita import CAL, SCENARIO
from renasci.vault.feasibility import check, feasible
from renasci.vault.loader import load
from renasci.vault.pins import extract

START, END = Date(4, 10, 0), Date(4, 90, CAL.days_per_year - 1)
RACES = {r["id"]: Race.from_json(r) for r in SCENARIO["races"]}


def run(tmp_path, notes: dict, races=True):
    root = tmp_path / "v"
    (root / "People").mkdir(parents=True)
    (root / "Houses").mkdir()
    (root / "Races").mkdir()
    (root / "Races/Leonin.md").write_text("---\ntype: race\n---\n", encoding="utf-8")
    config = '[[types]]\nmatch = "People/*"\ntype = "character"\n[[types]]\nmatch = "Houses/*"\ntype = "house"\n'
    if races:
        config += '[races]\n"v:leonin" = "r:leonin"\n'
    (root / "vault.toml").write_text(config, encoding="utf-8")
    for name, fm in notes.items():
        (root / f"{name}.md").write_text(f"---\nrace: \"[[Leonin]]\"\n{fm}\n---\n", encoding="utf-8")
    vault = load(root)
    got = extract(vault, CAL, START, END, hooks=[people_hook])
    return got, check(got, vault, START, END, hooks=[people_hook], races=RACES, calendar=CAL)


def verdict(report, pid):
    return report["pins"][pid]["verdict"]


def test_a_plain_vault_is_all_ok(tmp_path):
    got, report = run(tmp_path, {"People/Dad": "born: 4A 1\nsex: m", "People/Mum": "born: 4A 2\nsex: f",
                                 "People/Kid": "born: 4A 30\nfather: \"[[Dad]]\"\nmother: \"[[Mum]]\""})
    assert verdict(report, "v:kid:born") == "ok"
    assert [p.id for p in feasible(got, report)] == [p.id for p in got.pins]


def test_a_mother_outside_her_fertile_years_is_infeasible(tmp_path):
    got, report = run(tmp_path, {"People/Old Mum": "born: 4A 1\nsex: f",
                                 "People/Late Kid": "born: 4A 80\nmother: \"[[Old Mum]]\""})
    assert verdict(report, "v:late-kid:born") == "infeasible"
    assert "fertile" in report["pins"]["v:late-kid:born"]["why"]
    assert "v:late-kid:born" not in {p.id for p in feasible(got, report)}


def test_a_father_too_young_to_marry_is_infeasible(tmp_path):
    _, report = run(tmp_path, {"People/Boy": "born: 4A 20\nsex: m\nfather: \"[[Gramps]]\"", "People/Gramps": "born: 4A 1",
                               "People/Baby": "born: 4A 25\nfather: \"[[Boy]]\""})
    assert verdict(report, "v:baby:born") == "infeasible" and "marry" in report["pins"]["v:baby:born"]["why"]


def test_without_race_data_the_age_checks_are_skipped_and_said_so(tmp_path):
    _, report = run(tmp_path, {"People/Old Mum": "born: 4A 1\nsex: f",
                               "People/Late Kid": "born: 4A 80\nmother: \"[[Old Mum]]\""}, races=False)
    assert verdict(report, "v:late-kid:born") == "ok"
    assert any(r["kind"] == "no_race_data" for r in report["reports"])


def test_died_before_born_and_lineage_cycles_are_infeasible(tmp_path):
    _, report = run(tmp_path, {"People/Backwards": "born: 4A 40\ndied: 4A 30\nhouse: \"[[House X]]\"\n"
                                                   "offices:\n  - {office: \"[[House X]]\", from: 4A 35}",
                               "Houses/House X": "founded: 4A 1",
                               "People/Egg": "born: 4A 30\nfather: \"[[Hen]]\"", "People/Hen": "born: 4A 31\nfather: \"[[Egg]]\""})
    assert any(f["kind"] == "died_before_born" for f in report["findings"])
    assert any(f["kind"] == "lineage_cycle" for f in report["findings"])
    for pid, v in report["pins"].items():
        if pid.startswith(("v:egg:", "v:hen:", "v:backwards:")):
            assert v["verdict"] == "infeasible", pid


def test_overlapping_reigns_and_a_reign_after_death_are_infeasible(tmp_path):
    _, report = run(tmp_path, {
        "Houses/House X": "founded: 4A 1",
        "People/A": "born: 4A 1\nhouse: \"[[House X]]\"\noffices:\n  - {office: \"[[House X]]\", from: 4A 20, to: 4A 40}",
        "People/B": "born: 4A 1\nhouse: \"[[House X]]\"\noffices:\n  - {office: \"[[House X]]\", from: 4A 30}",
        "People/C": "born: 4A 1\ndied: 4A 50\nhouse: \"[[House X]]\"\noffices:\n  - {office: \"[[House X]]\", from: 4A 60}",
    })
    assert verdict(report, "v:b:reign:v:house-x-head:1") == "infeasible"  # A still reigns until 4A 40
    assert verdict(report, "v:c:reign:v:house-x-head:1") == "infeasible"  # C is dead by 4A 60


def test_the_report_names_the_notes_involved(tmp_path):
    _, report = run(tmp_path, {"People/Old Mum": "born: 4A 1\nsex: f",
                               "People/Late Kid": "born: 4A 80\nmother: \"[[Old Mum]]\""})
    assert set(report["pins"]["v:late-kid:born"]["notes"]) == {"People/Late Kid", "People/Old Mum"}


def test_renasci_vault_check_reports_feasibility(tmp_path, capsys):
    from renasci.cli import main

    run(tmp_path, {"People/Old Mum": "born: 4A 1\nsex: f", "People/Late Kid": "born: 4A 80\nmother: \"[[Old Mum]]\""})
    assert main(["vault", "check", str(tmp_path / "v"), "--world", "fourth_age", "--from", "4A 10", "--to", "4A 90"]) == 0
    out = capsys.readouterr().out
    assert "infeasible" in out and "v:late-kid:born" in out


# ---------------------------------------------------------------- review regressions


def test_a_cycle_through_the_second_parent_is_found(tmp_path):
    _, report = run(tmp_path, {"People/Ann": "born: 4A 1\nsex: f",
                               "People/Kid": "born: ~4A 30\nmother: \"[[Ann]]\"\nfather: \"[[Zed]]\"",
                               "People/Zed": "born: ~4A 31\nfather: \"[[Kid]]\""}, races=False)
    assert any(f["kind"] == "lineage_cycle" for f in report["findings"])
    assert verdict(report, "v:kid:born") == verdict(report, "v:zed:born") == "infeasible"


def test_a_long_reign_overlaps_every_later_one_it_covers(tmp_path):
    _, report = run(tmp_path, {
        "Houses/House X": "founded: 4A 1",
        "People/A": "born: 4A 1\nhouse: \"[[House X]]\"\noffices:\n  - {office: \"[[House X]]\", from: 4A 20, to: 4A 80}",
        "People/B": "born: 4A 1\nhouse: \"[[House X]]\"\noffices:\n  - {office: \"[[House X]]\", from: 4A 30, to: 4A 35}",
        "People/C": "born: 4A 1\nhouse: \"[[House X]]\"\noffices:\n  - {office: \"[[House X]]\", from: 4A 50}",
    })
    assert verdict(report, "v:b:reign:v:house-x-head:1") == verdict(report, "v:c:reign:v:house-x-head:1") == "infeasible"
    # and the orderings that touch an infeasible reign go with it
    for pid, v in report["pins"].items():
        if ":before:" in pid and ("v:b:reign" in pid or "v:c:reign" in pid):
            assert v["verdict"] == "infeasible", pid


def test_a_birth_on_the_mothers_first_infertile_birthday_is_infeasible(tmp_path):
    _, report = run(tmp_path, {"People/Mum": "born: 4A 1 m1 d1\nsex: f",
                               "People/Kid": "born: 4A 47 m1 d1\nmother: \"[[Mum]]\""})
    assert verdict(report, "v:kid:born") == "infeasible"  # she turns 46 that day; fertile is 16-45


def test_vault_check_shows_the_reports_too(tmp_path, capsys):
    from renasci.cli import main

    run(tmp_path, {"People/Old Mum": "born: 4A 1\nsex: f", "People/Late Kid": "born: 4A 80\nmother: \"[[Old Mum]]\""},
        races=False)
    assert main(["vault", "check", str(tmp_path / "v"), "--world", "fourth_age", "--from", "4A 10", "--to", "4A 90"]) == 0
    assert "no_race_data" in capsys.readouterr().out
