"""The belief trace in Python matches the Observatory's (#107; shared vectors, S12 spec §1a)."""

import json
from pathlib import Path

import pytest

from renasci.story.trace import origin, trace

VECTORS = json.loads((Path(__file__).resolve().parents[1] / "fixtures" / "traces.json").read_text(encoding="utf-8"))
BY_ID = {e["id"]: e for e in VECTORS["log"]}


@pytest.mark.parametrize("case", VECTORS["cases"], ids=lambda c: c["from"])
def test_the_shared_vectors(case):
    steps = trace(BY_ID.get, case["from"])
    assert [s["event"]["id"] for s in steps] == case["ids"], case["why"]
    assert [s["origin"] for s in steps] == case["origin"]
    assert [s["lie"] for s in steps] == case["lie"]
    assert origin(BY_ID.get, case["from"]) == case["ids"][-1]
