"""Types and their mapping (S2 spec §3, #59): vault.toml folder rules, type aliases, roles, status gates."""

from pathlib import Path

import pytest

from renasci.vault.config import Config, glob_match
from renasci.vault.loader import load
from renasci.vault.mapping import ROLES, role

FIXTURE = Path(__file__).parents[1] / "fixtures" / "vault"
REAL = Path(__file__).parents[2] / "docs"


@pytest.fixture(scope="module")
def vault():
    return load(FIXTURE)


@pytest.mark.parametrize("pattern,path,ok", [
    ("History/**", "History/Fourth Age/Night War", True),
    ("History/**", "History", False),
    ("History/*", "History/Fourth Age/Night War", False),
    ("History/*/The * Age", "History/Fourth Age/The Fourth Age", True),
    ("Realms/*/Societies/*/Characters/*", "Realms/R/Societies/E/Characters/Trelib", True),
    ("Realms/*/Societies/*/Characters/*", "Realms/R/Societies/E/Characters/Sub/Trelib", False),
    ("**/Characters/*", "Realms/R/Societies/E/Characters/Trelib", True),
    ("Images/**", "Images/crest", True),
    ("History/**/X", "History/X", True),
    ("**/X", "X", True),
    ("a/[Draft]/*", "a/[Draft]/n", True),  # brackets are just characters
    ("a/[Draft]/*", "a/D/n", False),
    ("(x)+/*", "(x)+/n", True),
])
def test_globs_take_a_star_as_one_segment_and_two_as_any_depth(pattern, path, ok):
    assert glob_match(pattern, path) is ok


def test_types_come_from_frontmatter_then_aliases_then_folder_rules_then_default(vault):
    n = vault.notes
    assert n["Realms/Renascita/Societies/Empire/Characters/Trelib Medani"].type_from == "frontmatter"
    assert n["Port Town"].type == "settlement" and n["Port Town"].type_from == "frontmatter"  # city -> settlement
    assert n["History/Fourth Age/The Fourth Age"].type == "era" and n["History/Fourth Age/The Fourth Age"].type_from == "folder"
    assert n["History/Fourth Age/Night War"].type == "event" and n["History/Fourth Age/Night War"].type_from == "folder"
    assert n["Lion's Rest"].type == "essay" and n["Lion's Rest"].type_from == "default"
    assert not any(f["kind"] == "unknown_type" and f["key"] == "Port Town" for f in vault.findings)


def test_the_mapping_table_row_by_row():
    assert {t for t, r in ROLES.items() if r == "pin_source"} == {"character", "house", "organisation", "event", "era"}
    assert {t for t, r in ROLES.items() if r == "place"} == {"settlement", "region", "continent", "landmark", "waterway",
                                                              "range"}
    assert {t for t, r in ROLES.items() if r == "claim_seed"} == {"chronicle", "myth"}
    assert {t for t, r in ROLES.items() if r == "ignored"} == {"essay", "index"}
    assert {t for t, r in ROLES.items() if r == "reference"} == {"race", "culture", "language", "deity", "faction",
                                                                 "artifact", "item", "resource", "technology",
                                                                 "cosmic-force", "tradition"}


def test_roles_and_status_gates(vault):
    n = vault.notes
    assert role(n["History/Fourth Age/Night War"]) == "pin_source"
    assert role(n["Port Town"]) == "place"
    assert role(n["Old Chronicle"]) == role(n["Prophecy of Ash"]) == "claim_seed"
    assert role(n["Races/Kyojin/Leonin/Leonin"]) == "reference"
    assert role(n["Lion's Rest"]) == "ignored"
    assert role(n["Draft Idea"]) == "draft"  # a draft event makes nothing


def test_ignored_paths_are_not_walked(vault):
    cfg = Config.load(FIXTURE)
    assert cfg.ignored("Images/anything") and not cfg.ignored("History/x")


def test_a_bad_config_is_an_error_with_its_reason(tmp_path):
    (tmp_path / "vault.toml").write_text('[[types]]\nmatch = "X/*"\ntype = "castle"\n', encoding="utf-8")
    with pytest.raises(ValueError, match="castle"):
        Config.load(tmp_path)


@pytest.mark.skipif(not (REAL / "vault.toml").is_file(), reason="no vault config in this checkout")
def test_the_real_vault_types_most_of_its_notes_by_folder():
    v = load(REAL)
    typed = sum(1 for n in v.notes.values() if n.type_from != "default")
    assert typed > 250, typed
    assert not any(f["kind"] == "unknown_type" for f in v.findings)
    houses = [n.title for n in v.notes.values() if n.type == "house"]
    assert len(houses) == 12 and "House Medani" in houses
    emperors = [n for n in v.notes.values() if n.type == "character" and ("Emperor" in n.title or "Empress" in n.title)]
    assert len(emperors) == 8


@pytest.mark.parametrize("toml,reason", [
    ('ignore = "Images/**"\n', "ignore"),
    ('ignore = [1]\n', "ignore"),
    ('[type_aliases]\nevent = "era"\n', "event"),
    ('[type_aliases]\ncity = 3\n', "city"),
    ('[[types]]\nmatch = ["X/*"]\ntype = "event"\n', "match"),
    ('[[types]]\nmatch = "X/*"\ntype = "event"\nwhen = 1\n', "when"),
])
def test_config_values_are_checked(tmp_path, toml, reason):
    (tmp_path / "vault.toml").write_text(toml, encoding="utf-8")
    with pytest.raises(ValueError, match=reason):
        Config.load(tmp_path)


def test_a_config_with_a_bom_reads(tmp_path):
    (tmp_path / "vault.toml").write_bytes(bytes([0xEF, 0xBB, 0xBF]) + b'ignore = ["X/**"]\n')
    assert Config.load(tmp_path).ignored("X/y")
