"""The point-of-view rules, exactly (S12 spec §2), on a small synthetic run: what a person could know,
what the dead stop learning, beliefs as they stood then, and rival claims kept."""

import pytest

from renasci.story.pack import Run, build
from renasci.story.text import Names, reading

CLAIM = {"pred": "killed", "args": {"victim": "p:v", "by": "p:k"}}
RIVAL = {"pred": "killed", "args": {"victim": "p:v", "by": "p:x"}}


def ev(i, date, t, roles=None, place=None, causes=(), payload=None, secret=False):
    return {"id": i, "date": date, "type": t, "roles": roles or {}, "place": place, "payload": payload or {},
            "causes": [["event", c] for c in causes], "visibility": "secret" if secret else "public"}


def person(i, name, **fields):
    return {"id": i, "kind": "person", "status": "active", "fields": {"name": name, **fields}}


EVENTS = [
    ev("x:root", [1, 1, 10], "test.happening", {"who": ["p:k"]}, "t:here"),
    ev("x:secret", [1, 2, 0], "test.plot", {"who": ["p:k"]}, "t:here", ["x:root"], secret=True),
    ev("x:hidden", [1, 2, 5], "test.plot", {"who": ["p:k"]}, "t:here", ["x:root"], secret=True),
    ev("x:saw", [1, 2, 10], "belief.perceived", {"holder": ["p:a"]}, "t:here", ["x:secret"], {"claim": CLAIM, "key": "c:1"}),
    ev("x:later", [1, 6, 0], "test.happening", {"who": ["p:k"]}, "t:here", ["x:root"]),
    ev("x:away", [1, 2, 0], "test.happening", {"who": ["p:k"]}, "t:there", ["x:root"]),
    ev("x:died", [1, 3, 0], "people.death", {"deceased": ["p:b"]}, "t:here", ["x:root"], {"cause": "old age"}),
]
STATE = {"entities": [person("p:a", "Ama"), person("p:b", "Bryn"), person("p:k", "Kel"), person("p:v", "Vey"),
                      person("p:x", "Xan"),
                      {"id": "t:here", "kind": "settlement", "status": "active", "fields": {"name": "Here"}},
                      {"id": "t:there", "kind": "settlement", "status": "active", "fields": {"name": "There"}}]}
HELD = {"c:1": {"claim": CLAIM, "conf": 0.6, "from": "x:saw"}, "c:2": {"claim": RIVAL, "conf": 0.3, "from": "x:saw"}}
DELTAS = [
    {"date": [1, 1, 0], "entity": "p:a", "field": "place", "old": None, "new": "t:here"},
    {"date": [1, 1, 0], "entity": "p:b", "field": "place", "old": None, "new": "t:here"},
    {"date": [1, 2, 10], "entity": "p:a", "field": "beliefs", "old": None, "new": HELD},
]


@pytest.fixture()
def run():
    return Run.of("toy", EVENTS, STATE, DELTAS, stories={"arcs": [], "sagas": []})


def seen(run, pov):
    return set(build(run, ("event", "x:root"), pov)["timeline"])


def test_a_person_knows_their_town_their_part_and_a_secret_their_belief_walks_back_to(run):
    got = seen(run, "p:a")
    assert {"x:root", "x:later", "x:saw", "x:secret"} <= got  # (their town; their own belief; its origin)
    assert "x:hidden" not in got and "x:away" not in got  # (a secret nothing led them to; another town)


def test_the_dead_learn_nothing_more(run):
    got = seen(run, "p:b")
    assert "x:root" in got and "x:died" in got and "x:later" not in got


def test_beliefs_are_as_they_stood_then_not_as_they_ended(run):
    assert run.field_at("p:a", "beliefs", [1, 1, 0]) is None  # (before their first belief)
    assert run.field_at("p:a", "beliefs", [1, 9, 0]) == HELD


def test_a_person_keeps_rival_claims_on_one_question(run):
    pack = build(run, ("event", "x:root"), "p:a")
    assert sorted(b["key"] for b in pack["beliefs"]) == ["c:1", "c:2"]
    assert all("truth" not in b for b in pack["beliefs"])


def test_an_omniscient_pack_sees_everything(run):
    assert {"x:root", "x:secret", "x:hidden", "x:away", "x:later"} <= seen(run, "omniscient")


def readings():
    n = Names(STATE)
    return lambda e: reading(e, n)


@pytest.mark.parametrize("event, text", [
    (ev("t1", [1, 1, 0], "people.tie_formed", {"a": ["p:a"], "b": ["p:b"]}, payload={"kind": "enemy"}), "Ama and Bryn became enemies"),
    (ev("t2", [1, 1, 0], "people.death", {"deceased": ["p:a"]}, payload={"cause": "fell in a duel"}), "Ama fell in a duel"),
    (ev("t3", [1, 1, 0], "people.death", {"deceased": ["p:a"]}, "t:here", payload={"cause": "old age"}), "Ama died at Here, of old age"),
    (ev("t4", [1, 1, 0], "people.action", {"actor": ["p:a"], "target": ["p:b"]}, payload={"action": "Poison", "outcome": "failure"}),
     "Ama tried to poison Bryn and failed"),
    (ev("t5", [1, 1, 0], "people.action", {"actor": ["p:a"], "target": ["p:b"]}, payload={"action": "Flee", "outcome": "success"}), "Ama fled"),
    (ev("t6", [1, 1, 0], "people.ambition_resolved", {"owner": ["p:a"]}, payload={"status": "died_unfulfilled"}),
     "Ama's ambition was unfulfilled when they died"),
])
def test_readings(event, text):
    assert readings()(event) == text
