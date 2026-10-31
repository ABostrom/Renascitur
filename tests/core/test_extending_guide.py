"""The extension map stays true: every pool is in it, and its example runs (#162)."""

import sys
from pathlib import Path

import pytest

from renasci import renascita
from renasci.core.calendar import Span
from renasci.core.pools import base, load

ROOT = Path(__file__).parents[2]
EXAMPLE = "ext_pilgrims"
NEEDS_ITS_OWN_WORLD = {"forcers", "disguises"}  # (each handles something a world may already handle)


@pytest.fixture
def example(monkeypatch):
    monkeypatch.syspath_prepend(str(ROOT / "examples" / "extensions"))
    yield EXAMPLE
    sys.modules.pop(EXAMPLE, None)


def test_the_guide_lists_every_pool():
    guide = (ROOT / "notes" / "extending.md").read_text(encoding="utf-8")
    assert [p for p in base() if f"| `{p}` |" not in guide] == []


def test_the_example_reaches_every_pool_it_can(example):
    found = load([example]).describe()
    assert [p for p in found if p not in NEEDS_ITS_OWN_WORLD and EXAMPLE not in found[p].values()] == []


def test_the_example_runs(example):
    e = renascita.new_engine(seed=3)
    e.extend([example])
    e.run(until=renascita.CAL.add(renascita.START, Span(years=6)))
    kinds = {x.type for x in e.events}
    assert {"pilgrim.tolled", "pilgrim.vowed", "pilgrim.blessed"} <= kinds
    assert e.check_conservation() == []
