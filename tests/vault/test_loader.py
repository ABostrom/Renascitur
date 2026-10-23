"""The vault loader (S2 spec §2, #58): walk, frontmatter subset, links, records, normalisation, findings."""

import shutil
from pathlib import Path

import pytest

from renasci.vault.frontmatter import parse
from renasci.vault.loader import load

FIXTURE = Path(__file__).parents[1] / "fixtures" / "vault"
REAL = Path(__file__).parents[2] / "docs"


@pytest.fixture(scope="module")
def vault():
    return load(FIXTURE)


def kinds(v, key=None):
    return {(f["kind"], f["key"]) for f in v.findings if key is None or f["key"] == key}


# ---------------------------------------------------------------- the frontmatter subset


def test_scalars_lists_maps_and_link_scalars():
    fm, findings, lines, _ = parse(
        "---\nname: Arn\nage: 30\nalive: true\nnone:\nq: \"a: b\"\ns: 'x'\n"
        "flow: [a, \"b, c\", [[Link|Shown]]]\nblock:\n- one\n  - two\nlink: [[Some Note]]\nmap:\n  from: 4A 1\n  to: 4A 9\n"
        "offices:\n  - {office: \"[[House X]]\", from: 4A 1, to: 4A 30}\n---\nbody\n")
    assert not findings
    assert fm["name"] == "Arn" and fm["age"] == 30 and fm["alive"] is True and fm["none"] is None
    assert fm["q"] == "a: b" and fm["s"] == "x"
    assert fm["flow"] == ["a", "b, c", "[[Link|Shown]]"]
    assert fm["block"] == ["one", "two"]
    assert fm["link"] == "[[Some Note]]"
    assert fm["map"] == {"from": "4A 1", "to": "4A 9"}
    assert fm["offices"] == [{"office": "[[House X]]", "from": "4A 1", "to": "4A 30"}]
    assert lines["offices"] == 16


def test_beyond_the_subset_is_a_finding_and_the_rest_still_reads():
    fm, findings, _, _ = parse("---\nok: 1\nbroken: [unclosed\nweird: |\n  multi\nafter: 2\n---\nbody")
    assert fm["ok"] == 1 and fm["after"] == 2
    assert {f["field"] for f in findings} == {"broken", "weird"}


def test_no_frontmatter_is_fine():
    fm, findings, _, start = parse("just text\n")
    assert fm == {} and not findings and start == 0


# ---------------------------------------------------------------- the walk and the records


def test_the_walk_skips_dot_folders_and_proposals_and_attachments(vault):
    keys = set(vault.notes)
    assert "Races/Kyojin/Leonin/Leonin" in keys and "Lion's Rest" in keys
    assert not any(k.startswith((".obsidian", "_proposed")) for k in keys)
    assert all(not k.endswith(".png") for k in keys)
    assert "Draft Idea" in keys and vault.notes["Draft Idea"].status == "draft"
    assert vault.notes["Lion's Rest"].status == "canon" and vault.notes["Lion's Rest"].frontmatter == {}


def test_records_carry_title_type_and_lines(vault):
    n = vault.notes["Realms/Renascita/Societies/Empire/Characters/Trelib Medani"]
    assert n.title == "Trelib Medani" and n.type == "character" and n.type_from == "frontmatter"
    assert n.line_of["offices"] == 5
    assert vault.notes["Lion's Rest"].type == "essay" and vault.notes["Lion's Rest"].type_from == "default"


# ---------------------------------------------------------------- links


def test_links_resolve_by_path_stem_field_type_and_alias(vault):
    trelib = vault.notes["Realms/Renascita/Societies/Empire/Characters/Trelib Medani"]
    assert trelib.links["race"] == ["Races/Kyojin/Leonin/Leonin"]  # a stem collision settled by the field's type
    assert trelib.links["house"] == ["Realms/Renascita/Societies/Empire/Great Houses/House Medani"]
    assert trelib.links["offices"] == ["Realms/Renascita/Societies/Empire/Great Houses/House Medani"]
    assert "Races/Kyojin/Leonin/Leonin" in trelib.body_links  # a docs/ path link
    house = vault.notes["Realms/Renascita/Societies/Empire/Great Houses/House Medani"]
    assert house.links["seat"] == ["Lion's Rest"] and house.links["head"] == [trelib.key]
    assert "Realms/Renascita/Renascita" in vault.notes["Lion's Rest"].body_links  # a folder link: its folder note
    assert house.attachments == ["crest.png"]


def test_unresolved_and_ambiguous_links_are_findings(vault):
    found = kinds(vault)
    assert ("unresolved_link", "History/Fourth Age/Night War") in found  # Nowhere Town and a stale path
    assert ("ambiguous_link", "Lion's Rest") in found  # [[Leonin]] in a body: a race or a language
    assert ("ambiguous_link", "Realms/Renascita/Societies/Empire/Characters/Trelib Medani") in found  # alias Medani
    assert ("frontmatter_subset", "History/Fourth Age/Night War") in found


# ---------------------------------------------------------------- normalisation and the digest


def test_line_endings_and_a_bom_do_not_change_a_hash(tmp_path):
    shutil.copytree(FIXTURE, tmp_path / "v")
    a = load(tmp_path / "v")
    p = tmp_path / "v" / "Lion's Rest.md"
    p.write_bytes(b"\xef\xbb\xbf" + p.read_bytes().replace(b"\n", b"\r\n"))
    b = load(tmp_path / "v")
    assert a.notes["Lion's Rest"].hash == b.notes["Lion's Rest"].hash and a.digest == b.digest


def test_loading_is_deterministic(vault):
    again = load(FIXTURE)
    assert again.digest == vault.digest and again.to_json() == vault.to_json()


# ---------------------------------------------------------------- the real vault


@pytest.mark.skipif(not REAL.is_dir(), reason="no vault in this checkout")
def test_the_real_vault_loads_with_findings_but_no_errors():
    v = load(REAL)
    assert len(v.notes) > 400
    assert load(REAL).digest == v.digest
    counts = {}
    for f in v.findings:
        counts[f["kind"]] = counts.get(f["kind"], 0) + 1
    assert set(counts) <= {"unresolved_link", "ambiguous_link", "frontmatter_subset", "unknown_type"}, counts


def test_an_apostrophe_inside_a_plain_item_is_not_a_quote():
    fm, findings, _, _ = parse("---\naliases: [Cannith, Magnus' Rest Overseer]\nb: [Frontier's Edge]\n---\n")
    assert not findings and fm["aliases"] == ["Cannith", "Magnus' Rest Overseer"] and fm["b"] == ["Frontier's Edge"]


def test_renasci_vault_check_reports_without_writing(capsys, tmp_path):
    from renasci.cli import main

    shutil.copytree(FIXTURE, tmp_path / "v")
    before = {p: p.read_bytes() for p in (tmp_path / "v").rglob("*") if p.is_file()}
    assert main(["vault", "check", str(tmp_path / "v")]) == 0
    out = capsys.readouterr().out
    assert "notes" in out and "unresolved_link" in out and "Nowhere Town" in out
    assert {p: p.read_bytes() for p in (tmp_path / "v").rglob("*") if p.is_file()} == before
    assert main(["vault", "check", str(tmp_path / "v"), "--json"]) == 0
    import json

    data = json.loads(capsys.readouterr().out)
    assert data["digest"] and len(data["notes"]) == len(load(tmp_path / "v").notes)


# ---------------------------------------------------------------- review regressions


def write(tmp_path, files: dict) -> Path:
    root = tmp_path / "v"
    for name, text in files.items():
        p = root / name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(text.encode("utf-8") if isinstance(text, str) else text)
    return root


def test_quoted_values_in_flow_maps_and_escapes():
    fm, findings, _, _ = parse('---\noffices:\n  - {office: "[[HR]]", note: "first, and last", from: 4A 1}\n'
                               'q: "a \\"b\\" c"\ns: \'it\'\'s\'\n---\n')
    assert not findings
    assert fm["offices"] == [{"office": "[[HR]]", "note": "first, and last", "from": "4A 1"}]
    assert fm["q"] == 'a "b" c' and fm["s"] == "it's"


def test_keys_are_kept_verbatim_and_comments_and_blank_lines_are_fine():
    fm, findings, _, _ = parse("---\nbirth date: 4A 1\nkey.dot: x\ncolor: # just a comment\ntag: a #c\n"
                               "l:\n  - a\n\n  # a note\n  - b\n---\n")
    assert not findings
    assert fm["birth date"] == "4A 1" and fm["key.dot"] == "x" and fm["color"] is None and fm["tag"] == "a"
    assert fm["l"] == ["a", "b"]


def test_a_leading_horizontal_rule_is_not_frontmatter():
    fm, findings, _, start = parse("---\nSee [[Nowhere]] here.\n---\nbody\n")
    assert fm == {} and not findings and start == 0


def test_links_in_code_local_headings_and_escaped_pipes(tmp_path):
    root = write(tmp_path, {"A.md": "x `[[Ghost]]` y\n```\n[[Ghost2]]\n```\n[[#Heading]] and | [[B\|shown]] |\n",
                            "B.md": "b"})
    v = load(root)
    assert v.notes["A"].body_links == ["A", "B"] and not v.findings


def test_a_missing_vault_is_an_error_not_an_empty_vault(tmp_path):
    with pytest.raises(FileNotFoundError):
        load(tmp_path / "nope")


def test_only_lowercase_md_names_are_notes_and_names_are_unicode_normalised(tmp_path):
    import unicodedata

    root = write(tmp_path, {"Upper.MD": "x", "Café.md": "c",
                            "Link.md": unicodedata.normalize("NFD", "[[Café]] [[sound.ogg]]")})
    v = load(root)
    assert "Upper" not in v.notes
    assert v.notes["Link"].body_links == ["Café"] and v.notes["Link"].attachments == ["sound.ogg"]


def test_undecodable_text_is_a_finding(tmp_path):
    root = write(tmp_path, {"Bad.md": "caf\xe9".encode("cp1252")})
    assert {f["kind"] for f in load(root).findings} == {"not_utf8"}


def test_vault_check_json_is_utf8_whatever_the_console(tmp_path):
    import subprocess
    import sys

    root = write(tmp_path, {"Yōkuro.md": "[[Nō Such]]"})
    out = subprocess.run([sys.executable, "-m", "renasci.cli", "vault", "check", str(root), "--json"],
                         capture_output=True, env={**__import__("os").environ, "PYTHONIOENCODING": "cp1252"})
    assert out.returncode == 0, out.stderr
    import json

    assert json.loads(out.stdout.decode("utf-8"))["notes"][0]["title"] == "Yōkuro"
