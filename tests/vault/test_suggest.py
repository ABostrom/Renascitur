"""`vault suggest` (S2 spec §5.3, #153): frontmatter from a fixed table of labelled body bullets."""

import shutil
from pathlib import Path

import pytest

from renasci.vault.loader import load
from renasci.vault.suggest import apply, suggest

REAL = Path(__file__).parents[2] / "docs"


def vault_of(tmp_path, notes: dict):
    root = tmp_path / "v"
    (root / "vault.toml").parent.mkdir(parents=True, exist_ok=True)
    (root / "vault.toml").write_text('[[types]]\nmatch = "Houses/*"\ntype = "house"\n[[types]]\nmatch = "People/*"\n'
                                     'type = "character"\n[[types]]\nmatch = "Races/*"\ntype = "race"\n'
                                     '[[types]]\nmatch = "Places/*"\ntype = "landmark"\n', encoding="utf-8")
    for name, text in notes.items():
        (root / name).parent.mkdir(parents=True, exist_ok=True)
        (root / name).write_text(text, encoding="utf-8")
    return root


NOTES = {
    "Houses/House Medani.md": "---\naliases: [Medani]\n---\n## Leadership\n- **Current Head**: [[Trelib Medani]]\n"
                              "- **Race**: [[Leonin]]\n\n## Headquarters\n- **City**: [[Lion’s Rest]]\n"
                              "- **Primary Seat**: [[Tower of Inquisition]]\n",
    "People/Trelib Medani.md": "## Affiliation\n- **House**: [[House Medani]]\n\n## Race\n- [[Leonin]]\n\n"
                               "Younger brother of [[Kheros]]. **House**: [[Not This]] in prose.\n",
    "People/Kheros.md": "## House Affiliation\n- [[House Medani]]\n\n## Race\n- [[Human]]\n",  # no Human note
    "People/Emperor.md": "- **Spouse**: **Empress Valeria** - a warrior queen.\n- **House**: [[House Medani]]\n",
    "People/Set Already.md": "---\nhouse: \"[[House Medani]]\"\n---\n- **House**: [[Other House]]\n",
    "Essay.md": "- **City**: [[Lion’s Rest]]\n- **House**: [[House Medani]]\n",  # an essay gets nothing
    "Races/Leonin.md": "", "Lion’s Rest.md": "", "Places/Tower of Inquisition.md": "",
}


def test_fields_by_note_type_from_bullets_and_sections(tmp_path):
    got, _ = suggest(load(vault_of(tmp_path, NOTES)))
    assert got["Houses/House Medani"] == {"head": "[[Trelib Medani]]", "seat": "[[Tower of Inquisition]]"}
    assert got["People/Trelib Medani"] == {"house": "[[House Medani]]", "race": "[[Leonin]]"}
    assert got["People/Kheros"] == {"house": "[[House Medani]]"}  # its race links to no note
    assert "Essay" not in got


def test_unresolved_links_are_skipped_and_reported(tmp_path):
    _, skipped = suggest(load(vault_of(tmp_path, NOTES)))
    assert any(s["key"] == "People/Kheros" and s["field"] == "race" and "[[Human]]" in s["why"] for s in skipped)


def test_never_prose_never_a_plain_name_never_over_a_set_field(tmp_path):
    got, _ = suggest(load(vault_of(tmp_path, NOTES)))
    assert got["People/Emperor"] == {"house": "[[House Medani]]"}
    assert "People/Set Already" not in got and "Not This" not in str(got)


def test_apply_only_adds_lines_and_a_second_pass_suggests_nothing(tmp_path):
    root = vault_of(tmp_path, NOTES)
    before = (root / "People/Trelib Medani.md").read_text(encoding="utf-8")
    got, _ = suggest(load(root))
    assert apply(load(root), got) == len(got)
    after = (root / "People/Trelib Medani.md").read_text(encoding="utf-8")
    assert after.endswith(before) and 'house: "[[House Medani]]"' in after
    v = load(root)
    assert v.notes["People/Trelib Medani"].links["house"] == ["Houses/House Medani"]
    assert suggest(v)[0] == {}


def test_a_note_with_unclosed_frontmatter_is_not_counted_as_written(tmp_path):
    root = vault_of(tmp_path, {"People/Open.md": "---\nrace: x\n- **House**: [[House Medani]]\n",
                               "Houses/House Medani.md": ""})
    got, _ = suggest(load(root))
    assert apply(load(root), got) == 0


def test_renasci_vault_suggest_is_a_dry_run_unless_told(tmp_path, capsys):
    from renasci.cli import main

    root = vault_of(tmp_path, NOTES)
    before = {p: p.read_bytes() for p in root.rglob("*.md")}
    assert main(["vault", "suggest", str(root)]) == 0
    out = capsys.readouterr().out
    assert '+house: "[[House Medani]]"' in out and "skipped" in out
    assert {p: p.read_bytes() for p in root.rglob("*.md")} == before
    assert main(["vault", "suggest", str(root), "--write"]) == 0
    assert suggest(load(root))[0] == {}


@pytest.mark.skipif(not REAL.is_dir(), reason="no vault in this checkout")
def test_the_real_vault_gets_suggestions_for_its_houses_and_characters(tmp_path):
    shutil.copytree(REAL, tmp_path / "docs", ignore=shutil.ignore_patterns(".obsidian", ".smart-connections"))
    got, _ = suggest(load(tmp_path / "docs"))
    houses = [k for k in got if k.endswith("/House Medani")]
    assert houses and set(got[houses[0]]) == {"head", "seat"}
    assert sum(1 for v in got.values() if "house" in v) >= 15
