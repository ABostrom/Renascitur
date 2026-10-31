"""Gods (S11 #131): cast with a mark that makes them want, on the path everything that wants shares."""

import pytest

from renasci import renascita, truths
from renasci.core.calendar import Span
from renasci.people.ambitions import LIBRARY
from renasci.story.text import Names, reading

PANTHEON = [{"id": "g:ash", "name": "Ash", "rivals": ["g:dawn"], "power": 1.0},
            {"id": "g:dawn", "name": "Dawn", "rivals": ["g:ash"], "power": 1.0}]


def world(seed=3, years=25):
    sc = truths.apply(renascita.SCENARIO, {"pantheon": PANTHEON})
    e = renascita.new_engine(seed=seed, scenario=sc)
    e.run(until=renascita.CAL.add(renascita.START, Span(years=years)))
    return e


@pytest.fixture(scope="module")
def run():
    return world()


def of(e, kind):
    return [x for x in e.events if x.type == kind]


def test_a_world_without_gods_has_none():
    e = renascita.new_engine(seed=3)
    assert e.store.ids("deity") == [] and not any(s.get("divine.power") for _, s in e.rulesets)


def test_a_god_wants_on_the_path_a_sword_does(run):
    formed = {x.payload["class"] for x in of(run, "people.ambition_formed") if x.roles["owner"][0].startswith("g:")}
    assert formed >= {"Champion", "Spread"}


def test_a_god_blesses_and_curses_and_it_costs_power(run):
    assert of(run, "deity.blessed") and of(run, "deity.omen")
    assert all(0.0 <= run.store.get(g, "power") <= 1.0 for g in ("g:ash", "g:dawn"))


def test_a_gods_curse_falls_on_a_rivals_champion(run):
    cursed = of(run, "deity.cursed")
    assert cursed
    chosen = {run.store.get(a, "target") for a in run.store.ids("ambition") if run.store.get(a, "class") == "Champion"}
    assert {x.roles["person"][0] for x in cursed} <= chosen


def test_only_gods_are_offered_a_gods_ambition():
    assert LIBRARY["Champion"].held_by == ("deity",) and "deity" not in LIBRARY["Marry"].held_by


def test_a_god_is_an_agent_by_the_mark_it_is_cast_with(run):

    assert run.store.get("g:ash", "acquired")[0]["id"] == "divine"


def test_gods_replay_the_same():
    a, b = world(years=6), world(years=6)
    assert [x.id for x in a.events] == [x.id for x in b.events]


def test_it_reads_in_words(run):
    ev = of(run, "deity.blessed")[0]
    row = {"type": ev.type, "roles": {k: list(v) for k, v in ev.roles.items()}, "payload": {}}
    assert "blessed" in reading(row, Names({"entities": []}))


def test_a_rival_must_be_a_god():
    with pytest.raises(ValueError, match="rival"):
        truths.apply(renascita.SCENARIO, {"pantheon": [{"id": "g:a", "name": "A", "rivals": ["g:b"]}]})


def test_the_world_still_balances(run):
    assert run.check_conservation() == []


class Stub:
    """Just enough of a ctx."""

    def __init__(self, fields, dead=()):
        self.fields, self.dead = fields, dead

    def get(self, entity, name):
        return self.fields.get((entity, name))

    def status(self, entity):
        return "dead" if entity in self.dead else "active"


RIVAL = {("g:a", "rivals"): ["g:b"], ("g:b", "ambitions"): ["am"], ("am", "class"): "Champion", ("am", "target"): "p",
         ("g:a", "acquired"): []}


def test_a_god_does_not_go_after_a_dead_champion():
    assert LIBRARY["Smite"].eligible(Stub(RIVAL, dead=("p",)), "g:a") is None


def test_a_god_stays_with_its_chosen_until_they_are_gone():
    ctx = Stub({("am", "target"): "p"}, dead=("p",))
    assert LIBRARY["Champion"].moot(ctx, "am") and LIBRARY["Champion"].keeps(ctx, "am")
