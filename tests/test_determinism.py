"""Determinism hazards: set iteration, hash randomisation, threads, and versions (spec §3.14)."""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from renasci.core.determinism import check_environment, find_set_iteration, versions

ROOT = Path(__file__).parent.parent
SIM_CODE = [ROOT / "src" / "renasci" / "core", ROOT / "src" / "renasci" / "io"]


# ---------------------------------------------------------------- the static check


@pytest.mark.parametrize(
    "code",
    [
        "for x in {1, 2}: pass",
        "for x in set(names): pass",
        "for x in frozenset(names): pass",
        "ys = [y for y in {a for a in names}]",
        "ys = list(set(names))",
        "ys = tuple(set(names))",
        "for x in a | set(b): pass",
        "for x in set(a) - set(b): pass",
    ],
)
def test_the_checker_flags_set_iteration(code):
    assert find_set_iteration(code)


@pytest.mark.parametrize(
    "code",
    [
        "for x in sorted({1, 2}): pass",
        "ys = sorted(set(names))",
        "ok = x in set(names)",
        "n = len(set(names))",
        "for x in set(names):  # determinism: ok (order does not matter here)\n    pass",
    ],
)
def test_the_checker_allows_safe_uses(code):
    assert not find_set_iteration(code)


def test_simulation_code_never_iterates_a_set():
    problems = []
    for folder in SIM_CODE:
        for path in sorted(folder.rglob("*.py")):
            for line in find_set_iteration(path.read_text(encoding="utf-8")):
                problems.append(f"{path.relative_to(ROOT)}:{line}")
    assert problems == []


# ---------------------------------------------------------------- environment and versions


def test_blas_is_single_threaded():
    check_environment()
    for var in ("OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "OMP_NUM_THREADS"):
        assert os.environ[var] == "1"


def test_check_environment_fails_when_threads_are_allowed(monkeypatch):
    monkeypatch.setenv("OPENBLAS_NUM_THREADS", "8")
    with pytest.raises(RuntimeError):
        check_environment()


def test_versions_name_python_and_numpy():
    v = versions()
    assert v["python"].startswith("3.12") and v["numpy"].startswith("2.5") and "engine" in v


# ---------------------------------------------------------------- hash randomisation across processes

PROGRAM = """
import json, sys
sys.path.insert(0, {helpers!r})
from mini_world import new_engine
from renasci.core.calendar import Date
from renasci.core.canon import digest
e = new_engine()
e.run(until=Date(1, 12, 359))
print(json.dumps({{"history": digest(e.pending(), size=16), "state": e.state_hash()}}))
"""


def test_runs_match_across_hash_seeds():
    code = PROGRAM.format(helpers=str(ROOT / "tests" / "helpers"))
    results = []
    for seed in ("0", "1", "12345"):
        env = dict(os.environ, PYTHONHASHSEED=seed)
        out = subprocess.run([sys.executable, "-c", code], env=env, capture_output=True, text=True, check=True)
        results.append(json.loads(out.stdout))
    assert results[0] == results[1] == results[2]


def test_versions_are_part_of_the_recipe_and_the_manifest(tmp_path, monkeypatch):
    sys.path.insert(0, str(ROOT / "tests" / "helpers"))
    from mini_world import new_engine

    from renasci.io.runfolder import RunFolder

    assert new_engine().recipe()["versions"] == versions()
    assert RunFolder.create(tmp_path / "r", {}).manifest["versions"] == versions()


def test_the_engine_refuses_to_start_with_threaded_blas(monkeypatch):
    sys.path.insert(0, str(ROOT / "tests" / "helpers"))
    from mini_world import new_engine

    monkeypatch.setenv("MKL_NUM_THREADS", "4")
    with pytest.raises(RuntimeError):
        new_engine()
