"""Stable ids (S2 spec §4, #60): the slug rule, assignment, the additive migration, identity across renames."""

import shutil
from pathlib import Path

import pytest

from renasci.vault.ids import assign, migrate, slug
from renasci.vault.loader import load

FIXTURE = Path(__file__).parents[1] / "fixtures" / "vault"


@pytest.mark.parametrize("title,expected", [
    ("House Medani", "house-medani"),
    ("Lion’s Rest", "lions-rest"),
    ("Magnus’ Rest", "magnus-rest"),
    ("Lion's Rest", "lions-rest"),
    ("Duo - Second Emperor", "duo-second-emperor"),
    ("Dürrenholt", "durrenholt"),
    ("Yōkuro no Ki", "yokuro-no-ki"),
    ("  The  (Old)  Gate!  ", "the-old-gate"),
])
def test_the_slug_rule(title, expected):
    assert slug(title) == expected


@pytest.fixture()
def vault_copy(tmp_path):
    shutil.copytree(FIXTURE, tmp_path / "v")
    return tmp_path / "v"


def test_every_note_that_isnt_an_essay_gets_a_unique_id_and_collisions_go_in_key_order(vault_copy):
    v = load(vault_copy)
    ids = assign(v)
    assert ids["Realms/Renascita/Societies/Empire/Great Houses/House Medani"] == "v:house-medani"
    assert ids["Languages/Leonin"] == "v:leonin" and ids["Races/Kyojin/Leonin/Leonin"] == "v:leonin-2"
    assert "Lion's Rest" not in ids  # an essay: no id
    assert "Draft Idea" in ids  # a draft still has an identity
    assert len(set(ids.values())) == len(ids)


def test_an_existing_id_is_kept_and_wins_its_slug(vault_copy):
    p = vault_copy / "Races/Kyojin/Leonin/Leonin.md"
    p.write_text(p.read_text(encoding="utf-8").replace("type: race", "type: race\nid: v:leonin"), encoding="utf-8")
    ids = assign(load(vault_copy))
    assert ids["Races/Kyojin/Leonin/Leonin"] == "v:leonin" and ids["Languages/Leonin"] == "v:leonin-2"


def test_the_config_can_prefer_an_id(vault_copy):
    with (vault_copy / "vault.toml").open("a", encoding="utf-8") as f:
        f.write('\n[ids]\n"Races/Kyojin/Leonin/Leonin" = "v:leonin-race"\n')
    assert assign(load(vault_copy))["Races/Kyojin/Leonin/Leonin"] == "v:leonin-race"


def test_duplicate_and_malformed_ids_are_findings(vault_copy):
    for name in ("Port Town.md", "Old Chronicle.md"):
        p = vault_copy / name
        p.write_text(p.read_text(encoding="utf-8").replace("---\n", "---\nid: v:same\n", 1), encoding="utf-8")
    p = vault_copy / "Prophecy of Ash.md"
    p.write_text(p.read_text(encoding="utf-8").replace("---\n", "---\nid: Not An Id\n", 1), encoding="utf-8")
    v = load(vault_copy)
    kinds = {(f["kind"], f["key"]) for f in v.findings}
    assert ("duplicate_id", "Port Town") in kinds and ("duplicate_id", "Old Chronicle") in kinds
    assert ("bad_id", "Prophecy of Ash") in kinds


def test_the_migration_shows_a_diff_then_only_adds_id_lines(vault_copy):
    before = {p: p.read_bytes() for p in vault_copy.rglob("*.md")}
    plan = migrate(load(vault_copy), write=False)
    assert plan and all(c["line"].startswith("id: v:") for c in plan)
    assert {p: p.read_bytes() for p in vault_copy.rglob("*.md")} == before  # a dry run writes nothing
    migrate(load(vault_copy), write=True)
    for p, old in before.items():
        new = p.read_bytes()
        if new != old:
            added = [ln for ln in new.decode("utf-8").splitlines() if ln not in old.decode("utf-8").splitlines()]
            assert all(ln.startswith("id: v:") or ln == "---" for ln in added), (p, added)
            assert (b"\r\n" in old) == (b"\r\n" in new)  # line endings kept
    v = load(vault_copy)
    assert all(n.id == assign(v)[k] for k, n in v.notes.items() if k in assign(v))
    assert migrate(v, write=False) == []  # idempotent


def test_a_note_without_frontmatter_gets_one(vault_copy):
    (vault_copy / "Bare.md").write_text("A plain note.\n", encoding="utf-8")
    with (vault_copy / "vault.toml").open("a", encoding="utf-8") as f:
        f.write('\n[[types]]\nmatch = "Bare"\ntype = "landmark"\n')
    migrate(load(vault_copy), write=True)
    assert (vault_copy / "Bare.md").read_text(encoding="utf-8") == "---\nid: v:bare\n---\nA plain note.\n"


def test_identity_survives_a_rename(vault_copy):
    migrate(load(vault_copy), write=True)
    old = vault_copy / "Realms/Renascita/Societies/Empire/Great Houses/House Medani.md"
    new = vault_copy / "Realms/Renascita/Societies/Empire/Great Houses/The House of Medani.md"
    old.rename(new)
    v = load(vault_copy)
    assert v.notes["Realms/Renascita/Societies/Empire/Great Houses/The House of Medani"].id == "v:house-medani"
    assert assign(v)["Realms/Renascita/Societies/Empire/Great Houses/The House of Medani"] == "v:house-medani"


def test_renasci_vault_ids_is_a_dry_run_unless_told(vault_copy, capsys):
    from renasci.cli import main

    before = {p: p.read_bytes() for p in vault_copy.rglob("*.md")}
    assert main(["vault", "ids", str(vault_copy)]) == 0
    out = capsys.readouterr().out
    assert "+id: v:house-medani" in out and "--write" in out
    assert {p: p.read_bytes() for p in vault_copy.rglob("*.md")} == before
    assert main(["vault", "ids", str(vault_copy), "--write"]) == 0
    assert load(vault_copy).notes["Realms/Renascita/Societies/Empire/Great Houses/House Medani"].id == "v:house-medani"


# ---------------------------------------------------------------- review regressions


def note(root, name, text):
    p = root / name
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(text.encode("utf-8"))
    return p


def placed(root):
    with (root / "vault.toml").open("a", encoding="utf-8") as f:
        f.write('\n[[types]]\nmatch = "Z/**"\ntype = "landmark"\n')


def test_an_empty_or_comment_only_frontmatter_gets_the_id_inside_it(tmp_path):
    root = tmp_path / "v"
    a = note(root, "Z/A.md", "---\n---\nbody\n")
    b = note(root, "Z/B.md", "---\n# just a comment\n---\nbody\n")
    placed(root)
    migrate(load(root), write=True)
    assert a.read_text(encoding="utf-8") == "---\nid: v:a\n---\nbody\n"
    assert b.read_text(encoding="utf-8") == "---\nid: v:b\n# just a comment\n---\nbody\n"


def test_a_note_with_any_id_field_or_unclosed_frontmatter_is_never_edited(tmp_path):
    root = tmp_path / "v"
    files = {n: note(root, f"Z/{n}.md", t) for n, t in
             {"Null": "---\nid:\n---\n", "Num": "---\nid: 12\n---\n", "Open": "---\nrace: x\nbody\n"}.items()}
    placed(root)
    before = {n: p.read_bytes() for n, p in files.items()}
    assert migrate(load(root), write=True) == []
    assert {n: p.read_bytes() for n, p in files.items()} == before


def test_every_stored_id_is_reserved_and_bad_ones_get_none(tmp_path):
    root = tmp_path / "v"
    note(root, "Z/Dup1.md", "---\nid: v:foo\n---\n")
    note(root, "Z/Dup2.md", "---\nid: v:foo\n---\n")
    note(root, "Z/Foo.md", "plain\n")
    placed(root)
    ids = assign(load(root))
    assert ids["Z/Foo"] == "v:foo-2" and "Z/Dup1" not in ids and "Z/Dup2" not in ids


def test_config_id_preferences_that_cannot_hold_are_findings(tmp_path):
    from renasci.vault.ids import check_ids

    root = tmp_path / "v"
    note(root, "Z/Alice.md", "---\nid: v:alice\n---\n")
    note(root, "Z/Bob.md", "plain\n")
    note(root, "Z/Carol.md", "plain\n")
    note(root, "Essay.md", "plain\n")
    placed(root)
    with (root / "vault.toml").open("a", encoding="utf-8") as f:
        f.write('\n[ids]\n"Z/Bob" = "v:alice"\n"Z/Carol" = "v:alice"\n"Z/Alice" = "v:other"\n"Nope" = "v:nope"\n'
                '"Essay" = "v:essay"\n')
    kinds = {(f["kind"], f["key"]) for f in check_ids(load(root))}
    assert {("id_preference", k) for k in ("Z/Bob", "Z/Carol", "Z/Alice", "Nope", "Essay")} <= kinds


def test_draft_essays_get_no_id(tmp_path):
    root = tmp_path / "v"
    note(root, "Notes/Musing.md", "---\nstatus: draft\n---\n")
    note(root, "Notes/Plan.md", "---\nstatus: draft\ntype: event\n---\n")
    ids = assign(load(root))
    assert "Notes/Musing" not in ids and ids["Notes/Plan"] == "v:plan"


@pytest.mark.parametrize("title,expected", [
    ("Þórr", "thorr"), ("Æthelred", "aethelred"), ("Ørsted", "orsted"), ("Straße", "strasse"),
    ("Đorđe", "dorde"), ("Łódź", "lodz"), ("Lion‘s Rest", "lions-rest"),
])
def test_slugs_keep_letters_that_dont_decompose(title, expected):
    assert slug(title) == expected


def test_a_name_with_no_slug_is_a_finding_not_v_note(tmp_path):
    from renasci.vault.ids import check_ids

    root = tmp_path / "v"
    note(root, "Z/神殿.md", "plain\n")
    placed(root)
    v = load(root)
    assert "Z/神殿" not in assign(v)
    assert ("no_slug", "Z/神殿") in {(f["kind"], f["key"]) for f in check_ids(v)}


def test_bom_crlf_and_no_trailing_newline_and_spaces_after_the_opener(tmp_path):
    root = tmp_path / "v"
    p = note(root, "Z/A.md", "")
    p.write_bytes(b"\xef\xbb\xbf---  \r\nrace: x\r\n---\r\nbody")
    placed(root)
    migrate(load(root), write=True)
    assert p.read_bytes() == b"\xef\xbb\xbf---  \r\nid: v:a\r\nrace: x\r\n---\r\nbody"
