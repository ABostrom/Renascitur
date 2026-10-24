"""The chronicle's rules, exactly (S12 spec §3), on a small synthetic run: a death told as the author's
claim (never the truth and then the claim), a lie told outside what the author saw, a house speaking
with its head's voice, a title that gives nothing away, and front matter that no name can break."""

import pytest

from renasci.story.chronicle import chronicle
from renasci.story.pack import Run
from renasci.vault.frontmatter import parse

TRUTH = {"pred": "killed", "args": {"victim": "p:v", "by": "p:k"}}
LIE = {"pred": "killed", "args": {"victim": "p:v", "by": "p:x"}}


def ev(i, date, t, roles=None, place=None, causes=(), payload=None, secret=False):
    return {"id": i, "date": date, "type": t, "roles": roles or {}, "place": place, "payload": payload or {},
            "causes": [["event", c] for c in causes], "visibility": "secret" if secret else "public"}


def person(i, name, **fields):
    return {"id": i, "kind": "person", "status": "active", "fields": {"name": name, **fields}}


EVENTS = [
    ev("x:death", [1, 1, 10], "people.death", {"deceased": ["p:v"], "killer": ["p:k"]}, "t:here", payload={"cause": "p:k"}),
    ev("x:lie", [1, 2, 0], "belief.told", {"teller": ["p:a"], "holder": ["p:b"]}, "t:here",
       payload={"claim": LIE, "intent": "lie", "key": "c:2", "conf": 0.7}),
    ev("x:far", [1, 6, 0], "test.happening", {"who": ["p:k"]}, "t:there", ["x:death"]),
]
HOUSE = {"id": "h:1", "kind": "house", "status": "active", "fields": {"name": "One", "headship": "o:1"}}
STATE = {"entities": [person("p:a", "Ama", house="h:1"), person("p:h", "Hal", house="h:1"), person("p:b", "Bryn"),
                      person("p:k", "Kel"), person("p:v", "Vey"), person("p:x", 'Xan "the\rinjected: yes'),
                      HOUSE, {"id": "o:1", "kind": "office", "status": "active", "fields": {"holder": "p:h"}},
                      {"id": "t:here", "kind": "settlement", "status": "active", "fields": {"name": "Here"}},
                      {"id": "t:there", "kind": "settlement", "status": "active", "fields": {"name": "There"}}]}
KNOWS = {"c:1": {"claim": TRUTH, "conf": 0.9, "from": "x:death"}}
DELTAS = [
    {"date": [1, 1, 0], "entity": p, "field": "place", "old": None, "new": "t:here"} for p in ("p:a", "p:h", "p:b")
] + [{"date": [1, 1, 10], "entity": p, "field": "beliefs", "old": None, "new": KNOWS} for p in ("p:a", "p:h")]


@pytest.fixture()
def run():
    return Run.of("toy", EVENTS, STATE, DELTAS, stories={"arcs": [], "sagas": []})


def body(doc):
    return "\n".join(line for line in doc["text"].split("\n") if line.startswith("**"))


def test_a_liar_tells_the_death_their_way_and_only_their_way(run):
    doc = chronicle(run, ("event", "x:death"), "p:a")  # (the lie was told after what Ama saw of it)
    assert "killed by Xan" in body(doc) and "Kel" not in body(doc)
    assert [d["event"] for d in doc["divergence"]] == ["x:death"]
    assert doc["divergence"][0]["truth"] == ["x:death"]  # (the death itself names the real killer)


def test_the_title_gives_nothing_away(run):
    doc = chronicle(run, ("event", "x:death"), "p:a")
    assert "Kel" not in doc["text"]


def test_a_house_speaks_with_its_heads_voice(run):
    doc = chronicle(run, ("event", "x:death"), "h:1")  # (the head holds the truth; a member's lie isn't theirs)
    assert "Kel" in body(doc) and "Xan" not in body(doc) and doc["divergence"] == []


def test_no_name_breaks_the_front_matter(run):
    text = chronicle(run, ("event", "x:death"), "p:a")["text"]
    for t in (text, text.replace("\r\n", "\n").replace("\r", "\n")):  # (as the vault loader normalises it)
        fm, findings = parse(t)[:2]
        assert findings == [] and "injected" not in fm and fm["source"]["run"] == "toy"
