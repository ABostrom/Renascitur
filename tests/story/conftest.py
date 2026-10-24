"""The M4 run (S12 spec §1a), made once per test session from the committed recipe."""

from pathlib import Path

import pytest

RECIPE = Path(__file__).resolve().parents[2] / "recipes" / "m4.toml"


@pytest.fixture(scope="session")
def m4(tmp_path_factory):
    from renasci.cli import main

    out = tmp_path_factory.mktemp("m4")
    assert main(["run", str(RECIPE), "--out", str(out)]) == 0
    return out / "m4"


@pytest.fixture(scope="session")
def m4run(m4):
    from renasci.story.pack import Run

    return Run(m4)


@pytest.fixture(scope="session")
def m4_spared(tmp_path_factory):
    """The M4 run's variant where the night terrors spare the caravan leader (S12 §3: they tell the truth)."""
    from renasci.cli import main

    out = tmp_path_factory.mktemp("m4s")
    text = RECIPE.read_text(encoding="utf-8").replace('name = "m4"', 'name = "m4s"')
    text = text.replace('params = { script = "ward_failure" }', 'params = { script = "ward_failure", spare = "leader" }')
    assert 'spare = "leader"' in text
    recipe = out / "m4s.toml"
    recipe.write_text(text, encoding="utf-8")
    assert main(["run", str(recipe), "--out", str(out)]) == 0
    return out / "m4s"
