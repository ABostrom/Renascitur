"""A recipe's run name becomes a folder name: it must be one plain name, never a path (#57 review)."""

import pytest

from renasci import __version__
from renasci.io.recipe import parse_recipe
from renasci.io.runfolder import RunFolder


def recipe(name):
    return {"run": {"name": name, "engine": __version__, "seed": 1, "world": "toy", "end": "1X 2"}}


@pytest.mark.parametrize("name", ["base", "kin-latch1", "tiny_whatif.2", "A1"])
def test_plain_names_are_fine(name):
    assert parse_recipe(recipe(name)).name == name


@pytest.mark.parametrize("name", ["../esc", "a/b", "a\b", "C:/x", "/abs", "", ".hidden", "trailing.", "has space",
                                  "CON", "con", "nul.txt", "COM1", "lpt9", "x" * 65, 3])
def test_a_name_that_is_a_path_or_unsafe_folder_is_refused(name):
    with pytest.raises(ValueError, match="name"):
        parse_recipe(recipe(name))


def test_a_run_folder_must_be_directly_inside_its_parent(tmp_path):
    with pytest.raises(ValueError):
        RunFolder.create(tmp_path / "runs" / ".." / ".." / "esc", {})
