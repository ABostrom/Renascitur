"""Canon checks (S12 spec §4, #117) on a small synthetic world: each pattern, voice and date form; names
narrowed by what a sentence states, and ambiguous ones reported with candidates; ambiguous events;
`claims` blocks; the judging extensions; and each cell of the verdict table."""

import pytest

from renasci.story.check import check, findings
from renasci.story.pack import Run

CAL = {"ages": [{"abbrev": "4A", "index": 4, "last_year": 256, "name": "Fourth Age"}],
       "months": [[f"Month {i}", 30] for i in range(1, 13)],
       "seasons": [["Spring", 90], ["Summer", 90], ["Autumn", 90], ["Winter", 90]]}
FAULT = {"pred": "fault", "args": {"event": "x:fail", "party": "p:dain"}}


def ev(i, date, t, roles, place=None, causes=(), payload=None, secret=False):
    return {"id": i, "date": date, "type": t, "roles": roles, "place": place, "payload": payload or {},
            "causes": [["event", c] for c in causes], "visibility": "secret" if secret else "public"}


def person(i, name, born=(4, 1, 0), **fields):
    return {"id": i, "kind": "person", "status": "active", "fields": {"name": name, "born": list(born), **fields}}


def place(i, name, kind="settlement"):
    return {"id": i, "kind": kind, "status": "active", "fields": {"name": name}}


EVENTS = [
    ev("x:wed", [4, 1, 10], "people.marriage", {"spouse": ["p:cole", "p:isa"]}, "t:lux"),
    ev("x:sab", [4, 2, 0], "ward.sabotage", {"ordered_by": ["p:gwen"]}, "t:lux", secret=True),
    ev("x:fail", [4, 2, 0], "ward.failure", {"leader": ["p:cole"], "keeper": ["p:dain"]}, "t:lux", ["x:sab"]),
    ev("x:succ", [4, 3, 0], "people.succession", {"predecessor": ["p:old"], "successor": ["p:cara"]}, None,
       payload={"office": "o:k"}),
    ev("x:kill", [4, 5, 0], "people.death", {"deceased": ["p:jory"], "killer": ["p:gwen"]}, "t:lux",
       payload={"cause": "fell in a duel"}),
    ev("x:fail2", [4, 8, 0], "ward.failure", {"leader": ["p:cole2"], "keeper": ["p:dain"]}, "t:port"),
    ev("x:kill2", [4, 8, 10], "people.death", {"deceased": ["p:gwen"], "killer": ["p:cara"]}, "t:lux",
       payload={"cause": "fell in a duel"}),
    ev("x:orm", [4, 3, 0], "people.death", {"deceased": ["p:old"]}, "t:lux", payload={"cause": "night terrors"}),
]
STATE = {"entities": [
    person("p:cara", "Cara", house="h:k"), person("p:gwen", "Gwen", house="h:k"), person("p:jory", "Jory", house="h:k"),
    person("p:old", "Orm", house="h:k"), person("p:cara2", "Cara", house="h:s"),
    person("p:cole", "Cole", place="t:lux", spouse="p:isa"), person("p:cole2", "Cole", place="t:port"),
    person("p:isa", "Isa", place="t:lux", spouse="p:cole", beliefs={"c:1": {"claim": FAULT, "conf": 0.8, "from": "x:fail"}}),
    person("p:dain", "Dain", place="t:lux"),
    person("p:arn", "Arn", place="t:port", spouse="p:kesh"), person("p:kesh", "Kesh", place="t:port", spouse="p:arn"),
    {"id": "h:k", "kind": "house", "status": "active", "fields": {"name": "Kundarak", "headship": "o:k"}},
    {"id": "h:s", "kind": "house", "status": "active", "fields": {"name": "Sivis"}},
    {"id": "o:k", "kind": "office", "status": "active", "fields": {"holder": "p:cara", "house": "h:k"}},
    place("t:lux", "Lux Oescus"), place("t:port", "Port Ardere")]}
DELTAS = [{"date": [4, 1, 0], "entity": p, "field": "place", "old": None, "new": t}
          for p, t in (("p:cole", "t:lux"), ("p:isa", "t:lux"), ("p:dain", "t:lux"), ("p:cole2", "t:port"))]


@pytest.fixture(scope="module")
def run():
    r = Run.of("toy", EVENTS, STATE, DELTAS, stories={"arcs": [], "sagas": []})
    r.manifest = {"engine": None, "meta": {"calendar": CAL}}
    return r


def claims(run, text, pov="omniscient"):
    rep = check(run, text, pov)
    return [(c["pred"], c["verdict"], c["finding"]) for s in rep["sentences"] for c in s["claims"]], rep


@pytest.mark.parametrize("text", [
    "Gwen of House Kundarak killed Jory of House Kundarak in 4A 5.",
    "In 4A 5, Jory of House Kundarak was slain by Gwen of House Kundarak.",
    "Jory of House Kundarak died at Lux Oescus, killed by Gwen of House Kundarak, in the year 5 of the Fourth Age.",
    "In the 5th year of the Fourth Age Jory, of House Kundarak, fell at the hands of Gwen (House Kundarak).",
    "**4A 5.** House Kundarak's Gwen struck down Jory of House Kundarak.",
])
def test_a_killing_in_any_voice_and_date_form(run, text):
    got, _ = claims(run, text)
    assert ("killed", "true", "consistent") in got


@pytest.mark.parametrize("text, pred", [
    ("Cara of House Kundarak killed Jory of House Kundarak in 4A 5.", "killed"),  # (the wrong killer)
    ("Gwen of House Kundarak killed Jory of House Kundarak in 4A 7.", "killed"),  # (the wrong year)
    ("In 4A 6, Gwen of House Kundarak murdered Cole of Lux Oescus.", "killed"),  # (the victim never died)
    ("Jory of House Kundarak died in 4A 9.", "died_in"),
    ("Gwen of House Sivis killed Jory of House Kundarak in 4A 5.", "member"),  # (no Gwen of House Sivis)
    ("Cole of Port Ardere married Isa of Lux Oescus.", "married"),  # (the wrong Cole)
    ("In 4A 9, Jory of House Kundarak sailed for Port Ardere.", "alive_at"),  # (a dead man acting)
    ("Cara of House Kundarak became head of House Kundarak in 4A 7.", "ruled"),
    ("The ward failure at Lux Oescus was the fault of Dain.", "fault"),
])
def test_contradictions(run, text, pred):
    got, _ = claims(run, text)
    assert (pred, "false", "contradiction") in got, got


@pytest.mark.parametrize("text, pred", [
    ("Cole of Lux Oescus and Isa were married.", "married"),
    ("Cara of House Kundarak became head of House Kundarak in 4A 3.", "ruled"),
    ("Gwen of House Kundarak was behind the ward failure at Lux Oescus.", "caused"),
    ("In 4A 4, Jory of House Kundarak sailed for Port Ardere.", "alive_at"),
    ("Jory of House Kundarak died in 4A 5.", "died_in"),
])
def test_true_claims(run, text, pred):
    got, _ = claims(run, text)
    assert (pred, "true", "consistent") in got, got


def test_a_house_for_what_its_own_did_is_half(run):
    got, _ = claims(run, "The ward failure at Lux Oescus in 4A 2 was the doing of House Kundarak.")
    assert ("caused", "half", "half") in got


def test_ambiguous_names_and_events_come_with_candidates(run):
    _, rep = claims(run, "Cara killed Jory of House Kundarak in 4A 5. The ward failure was the fault of Dain.")
    amb = [f for f in findings(rep) if f["finding"] == "ambiguous"]
    assert {f["kind"] for f in amb} == {"person", "event"}
    cara = next(f for f in amb if f["kind"] == "person")
    assert {c["id"] for c in cara["candidates"]} == {"p:cara", "p:cara2"}
    got, _ = claims(run, "The ward failure at Port Ardere was the fault of Dain.")  # (narrowed by place)
    assert ("fault", "false", "contradiction") in got


def test_a_name_is_settled_by_its_first_mention(run):
    got, rep = claims(run, "Cara of House Kundarak became head of House Kundarak in 4A 3. Later Cara married Cole of Lux Oescus.")
    assert ("married", "false", "contradiction") in got and not [f for f in findings(rep) if f["finding"] == "ambiguous"]


def test_a_claims_block_is_read_exactly(run):
    text = '```claims\n{"pred": "killed", "args": {"victim": "p:jory", "by": "Gwen of House Kundarak"}}\n' \
           '{"pred": "died_in", "args": {"who": "p:jory"}, "date": "4A 6"}\n{"pred": "loved", "args": {"a": "p:isa"}}\n```\n'
    got, _ = claims(run, text)
    assert got == [("killed", "true", "consistent"), ("died_in", "false", "contradiction"), ("loved", "unknown", "invention")]


def test_the_verdict_table(run):
    lie = "The ward failure at Lux Oescus was the fault of Dain."
    assert claims(run, lie, "p:isa")[0] == [("fault", "false", "consistent")]  # (her account)
    assert claims(run, lie)[0] == [("fault", "false", "contradiction")]
    secret = "Gwen of House Kundarak was behind the ward failure at Lux Oescus."
    assert ("caused", "true", "leak") in claims(run, secret, "p:isa")[0]  # (the sabotage was secret)
    assert ("caused", "true", "consistent") in claims(run, secret)[0]
    assert ("caused", "half", "half") in claims(run, "The ward failure at Lux Oescus was the doing of House Kundarak.", "p:isa")[0]


@pytest.mark.parametrize("text", [
    "In 4A 5 Gwen of House Kundarak killed Jory of House Kundarak, and in 4A 8 Cara of House Kundarak killed Gwen of House Kundarak.",
    "- 4A 5: Gwen of House Kundarak killed Jory of House Kundarak\n- 4A 8: Cara of House Kundarak killed Gwen of House Kundarak\n",
    "| 4A 5 | Gwen of House Kundarak killed Jory of House Kundarak |\n|---|---|\n| 4A 8 | Cara of House Kundarak killed Gwen of House Kundarak |\n",
    "Gwen of House Kundarak, who killed Jory of House Kundarak in 4A 5, fell to Cara of House Kundarak in 4A 8.",
    "Gwen of House Kundarak, who had killed Jory of House Kundarak, fell to Cara of House Kundarak in 4A 8.",
    "In 4A 8, Cara of House Kundarak killed Jory of House Kundarak's killer, Gwen of House Kundarak.",
    "In 4A 9, Isa of Lux Oescus still grieved over Jory of House Kundarak's death.",
    "In 4A 5, Gwen of House Kundarak killed Jory of House Kundarak. Three years later Cara of House Kundarak killed Gwen of House Kundarak.",
    "Some said Cara of House Kundarak killed Jory of House Kundarak in 4A 5, but it was Gwen of House Kundarak.",
    "Arn of Port Ardere and Kesh of Port Ardere were married.",
    "The death of Orm of House Kundarak was the fault of the night terrors.",
    "﻿---\ntitle: Jory of House Kundarak died in 4A 3.\n---\nJory of House Kundarak died in 4A 5.\n",
])
def test_true_prose_raises_no_contradiction(run, text):
    got, rep = claims(run, text)
    assert not [c for c in got if c[2] == "contradiction"], (got, [s["text"] for s in rep["sentences"]])


def test_a_wrong_predecessor_and_a_wrong_town_are_contradictions(run):
    got, _ = claims(run, "Cara of House Kundarak succeeded Gwen of House Kundarak as head of House Kundarak in 4A 3.")
    assert ("ruled", "false", "contradiction") in got
    _, rep = claims(run, "Isa of Port Ardere married Cole of Lux Oescus.")
    town = [c for s in rep["sentences"] for c in s["claims"] if c["pred"] == "lived_in"]
    assert town and town[0]["args"] == {"who": "Isa", "of": "t:port"} and town[0]["finding"] == "contradiction"


def test_acting_is_no_leak_for_one_who_never_heard_of_the_death(run):
    got, _ = claims(run, "In 4A 4, Jory of House Kundarak spoke before the guild.", "t:port")
    assert got == [("alive_at", "true", "consistent")]


def test_a_claims_block_with_bad_values_is_reported_not_a_crash(run):
    text = '```claims\n{"pred": "killed", "args": {"victim": ["x"], "by": 3}, "date": 10}\n' \
           '{"pred": "died_in", "args": {"who": "p:jory"}, "date": ["4", 5]}\n```\n'
    rep = check(run, text)
    assert [len(s["unresolved"]) for s in rep["sentences"]] == [3, 1] and rep["counts"]["contradiction"] == 0


def test_the_report_names_the_text_by_its_digest_and_caps_it(run):
    rep = check(run, "Jory of House Kundarak died in 4A 5.")
    assert len(rep["text"]) == 32 and rep["counts"]["consistent"] == 1
    with pytest.raises(ValueError):
        check(run, "x" * (256 * 1024 + 1))
