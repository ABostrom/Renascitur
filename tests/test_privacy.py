"""The private map stays private (S5 spec §1): the Inkarnate image and everything traced from it are
git-ignored, so a careless `git add -A` can't publish them (the repo is public)."""

import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
PRIVATE = ["images/Renascitur.png", "maps/pyrosia/private/base.png", "maps/pyrosia/private/layout.json",
           "src/renasci/renascita/pyrosia.json.bak"]


@pytest.mark.skipif(shutil.which("git") is None or not (ROOT / ".git").exists(), reason="needs git and the repo")
@pytest.mark.parametrize("path", PRIVATE)
def test_the_private_map_and_its_layers_are_ignored(path):
    done = subprocess.run(["git", "check-ignore", "-q", path], cwd=ROOT)
    assert done.returncode == 0, f"{path} isn't git-ignored"


@pytest.mark.skipif(shutil.which("git") is None or not (ROOT / ".git").exists(), reason="needs git and the repo")
def test_the_private_map_is_not_tracked():
    tracked = subprocess.run(["git", "ls-files", "images/Renascitur.png", "maps/*/private"], cwd=ROOT,
                             capture_output=True, text=True).stdout.strip()
    assert tracked == ""
