"""Cards (#165): a person, a thing or a town with a real past, from a finished run."""

import json

import pytest

from renasci.core.pools import base
from renasci.story import cards


@pytest.fixture(scope="module")
def generators():
    import renasci.story.cards  # noqa: F401

    return base().generators


def test_a_person_card_tells_their_life_from_the_run(m4run, generators):
    found = cards.generate(m4run, generators, "person", {}, seed=1)
    assert found["found"] > 10
    card = found["cards"][0]
    assert card["name"] and card["born"] and "kin" in card and "traits" in card
    for line in card["history"]:
        assert line["event"] in m4run.by_id  # (every line has an event behind it)


def test_the_same_seed_gives_the_same_card_and_another_a_different_one(m4run, generators):
    pick = lambda seed: cards.generate(m4run, generators, "person", {}, seed=seed)["cards"][0]["id"]  # noqa: E731
    assert pick(1) == pick(1)
    assert len({pick(s) for s in range(6)}) > 1


def test_filters_narrow_it(m4run, generators):
    every = cards.generate(m4run, generators, "person", {}, count=10_000)
    house = next(c["house"] for c in every["cards"] if c["house"])
    found = cards.generate(m4run, generators, "person", {"house": house}, count=10_000)
    assert 0 < found["found"] < every["found"]
    assert all(c["house"] == house for c in found["cards"])


def test_an_age_is_the_livings_at_the_runs_end(m4run, generators):
    found = cards.generate(m4run, generators, "person", {"age": "20-40"}, count=500)
    assert found["cards"]
    assert all(20 <= m4run.end_year - c["born"][1] <= 40 and c["status"] != "dead" for c in found["cards"])
    assert cards.generate(m4run, generators, "person", {"status": "dead"})["found"]


@pytest.mark.parametrize("text, span", [("30-50", (30, 50)), ("30", (30, 30)), ("30-", (30, float("inf")))])
def test_ages_read_as_they_should(text, span):
    assert cards.ages(text) == span


@pytest.mark.parametrize("text", ["old", "-30", "50-20", ""])
def test_a_bad_age_says_so(text):
    with pytest.raises(ValueError, match="--age"):
        cards.ages(text)


def test_filters_take_short_names():
    assert cards.named("r:dwarf", "dwarf") and cards.named("v:house-medani", "medani")
    assert cards.named("v:house-medani", "v:house-medani")
    assert not cards.named(None, "on") and not cards.named("v:house-medani", "e")


def things():
    from renasci.story.pack import Run

    def thing(i, status="active", **f):
        return {"id": i, "kind": "object", "status": status, "fields": {"type": "blade", "material": "iron", **f}}

    state = {"entities": [thing("a", name="the Blade", fame=0.7, lost=[4, 1, 0]), thing("b", fame=0.1),
                          thing("c", "dead", fame=0.9, destroyed=True)]}
    return Run.of("t", [{"id": "x1", "date": [4, 1, 0], "type": "object.made", "roles": {"object": ["a"]}, "causes": []}],
                  state, [])


def test_an_object_has_a_card_and_what_is_destroyed_is_not_offered(generators):
    run = things()
    every = cards.generate(run, generators, "object", {}, count=10)
    assert {c["id"] for c in every["cards"]} == {"a", "b"}
    found = cards.generate(run, generators, "object", {"fame": "0.5", "lost": "true"})
    assert [c["name"] for c in found["cards"]] == ["the Blade"] and found["cards"][0]["status"] == "active"


@pytest.mark.parametrize("wants, says", [({"lost": "yes"}, "--lost"), ({"fame": "abc"}, "--fame"), ({"fame": "nan"}, "--fame")])
def test_a_bad_filter_says_so(generators, wants, says):
    with pytest.raises(ValueError, match=says):
        cards.generate(things(), generators, "object", wants)


def test_a_long_life_says_how_much_it_left_out(m4run, generators):
    found = cards.generate(m4run, generators, "person", {}, count=10_000)
    longest = max(found["cards"], key=lambda c: c["told"])
    assert longest["told"] >= len(longest["history"]) and len(longest["history"]) <= cards.SHOWN
    assert not any(m4run.by_id[h["event"]]["type"].startswith("belief.") for c in found["cards"] for h in c["history"])


def test_when_nothing_fits_it_says_what_to_loosen(m4run, generators):
    found = cards.generate(m4run, generators, "person", {"house": "no-such-house", "age": "20-40"})
    assert found == {"found": 0, "cards": [], "closest": found["closest"]}
    assert found["closest"]["house"] > 0 and found["closest"]["age"] == 0


def test_a_filter_it_does_not_take_is_refused(m4run, generators):
    with pytest.raises(ValueError, match="takes"):
        cards.generate(m4run, generators, "person", {"fame": 1})
    with pytest.raises(ValueError, match="no generator"):
        cards.generate(m4run, generators, "dragon", {})


def test_a_town_has_a_card(m4run, generators):
    card = cards.generate(m4run, generators, "village", {}, seed=2)["cards"][0]
    assert card["kind"] == "settlement" and card["residents"] and card["people"]


def test_the_command_writes_json(m4, capsys):
    from renasci.cli import main

    assert main(["gen", "person", "--run", str(m4), "--seed", "3", "--count", "2"]) == 0
    out = json.loads(capsys.readouterr().out)
    assert len(out["cards"]) == 2


def test_the_command_refuses_nonsense(m4):
    from renasci.cli import main

    assert main(["gen", "dragon", "--run", str(m4)]) == 1
    assert main(["gen", "person", "--run", str(m4), "--count", "0"]) == 1
    assert main(["gen", "person", "--run", str(m4), "--where", "nope"]) == 1
    assert main(["gen", "person", "--run", str(m4), "--where", "fame=1"]) == 1  # (not a filter it takes)


def test_notable_puts_those_with_the_most_to_tell_first(m4run, generators):
    found = cards.generate(m4run, generators, "person", {}, count=5, notable=True)
    every = cards.generate(m4run, generators, "person", {}, count=10_000)
    tells = sorted(c["told"] for c in every["cards"])
    assert found["cards"][0]["told"] > tells[len(tells) // 2]


def test_the_command_saves_cards_for_the_forge(m4):
    from renasci.cli import main

    assert main(["gen", "person", "--run", str(m4), "--save", "--notable", "--where=age=20-"]) == 0  # (the job's line)
    assert json.loads((m4 / "analysis" / "cards" / "last.json").read_text(encoding="utf-8"))["cards"]
