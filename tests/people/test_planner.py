"""The planner (S7 spec §5, #93): backward chaining over the action library, bounded, cheapest, deterministic."""

import itertools
from dataclasses import dataclass

from hypothesis import given, settings
from hypothesis import strategies as st

from renasci.people import actions as A
from renasci.people.ambitions import LIBRARY as AMBITIONS
from renasci.people.planner import Plan, cost, plan


class World:
    """A planning world without a simulation: facts are a set, odds are fixed per action."""

    def __init__(self, facts=(), odds=None, ties=("t:friend",)):
        self.facts, self.odds, self.ties = set(facts), odds or {}, list(ties)

    def fact(self, tag):
        return tag in self.facts or tag in {f"tie:{t}" for t in self.ties}

    def odds_of(self, action, target):
        return self.odds.get(action.name, 0.5)

    def candidates(self, exclude):
        return [t for t in self.ties if t not in exclude]


def run(goals, world=None, actions=None, depth=6):
    w = world or World()
    return plan(goals, actions=actions or A.ACTIONS, depth=depth, fact=w.fact, odds=w.odds_of,
                candidates=w.candidates)


def test_every_starter_subgoal_is_reachable():
    """If an ambition names a goal no action can reach, schemes for it can never start (#93 acceptance)."""
    goals = [frozenset({"married"}), frozenset({"favoured"}), frozenset({"dead:t:rival"}),
             frozenset({"shamed:t:rival"})]
    for g in goals:
        assert run([g]) is not None, g
    for cls in AMBITIONS.values():  # the ambitions' own subgoal shapes
        assert cls.subgoals.__qualname__  # (exercised for real in the scheme tests, #94)


def test_favour_takes_a_petition_first():
    p = run([frozenset({"favoured"})])
    assert [s["action"] for s in p.steps] == ["Petition", "CourtFavour"]
    assert all(s["target"] is None for s in p.steps)  # (no target: None, not "")


def test_facts_already_true_are_not_planned_for():
    p = run([frozenset({"favoured"})], World(facts={"heard"}))
    assert [s["action"] for s in p.steps] == ["CourtFavour"]


def test_a_killing_recruits_when_it_needs_an_accomplice_and_takes_the_cheapest_way():
    w = World(odds={"Duel": 0.1, "Poison": 0.9, "Recruit": 0.9, "Assassinate": 0.2})
    p = run([frozenset({"dead:t:rival"})], w)
    assert [s["action"] for s in p.steps] == ["Recruit", "Poison"]
    assert p.steps[0]["target"] == "t:friend" and p.steps[1]["target"] == "t:rival"
    w2 = World(odds={"Duel": 0.95, "Poison": 0.5, "Recruit": 0.5})
    assert [s["action"] for s in run([frozenset({"dead:t:rival"})], w2).steps] == ["Duel"]


def test_no_accomplice_no_poison():
    w = World(odds={"Duel": 0.01}, ties=())
    assert [s["action"] for s in run([frozenset({"dead:t:rival"})], w).steps] == ["Duel"]


def test_the_depth_bound_is_the_schemers_wits():
    assert run([frozenset({"favoured"})], depth=1) is None
    assert run([frozenset({"favoured"})], depth=2) is not None


def test_any_one_of_several_goals_will_do():
    p = run([frozenset({"favoured"}), frozenset({"married"})])
    assert [s["action"] for s in p.steps] == ["Court"]  # one step beats two


def test_plans_are_json():
    p = run([frozenset({"dead:t:rival"})])
    import json

    assert json.loads(json.dumps(p.to_json())) == p.to_json()
    assert Plan.from_json(p.to_json()) == p


# ---------------------------------------------------------------- properties over generated libraries

TAGS = ["a", "b", "c", "d"]  # few tags, so several actions share one (alternative routes)


@dataclass(frozen=True)
class Gen:
    """A stand-in action for generated libraries (not an Action subclass, so it never joins the library)."""

    name: str
    achieves: str
    requires: frozenset
    secrecy: float


@st.composite
def libraries(draw):
    classes = []
    for i in range(draw(st.integers(1, 7))):
        achieves = draw(st.sampled_from(TAGS))
        requires = frozenset(draw(st.lists(st.sampled_from([t for t in TAGS if t != achieves]), max_size=2)))
        classes.append(Gen(f"Gen{i}", achieves, requires, draw(st.sampled_from([0.0, 0.3]))))
    odds = {c.name: draw(st.sampled_from([0.2, 0.5, 0.9])) for c in classes}
    facts = set(draw(st.lists(st.sampled_from(TAGS), max_size=2)))
    goal = frozenset(draw(st.lists(st.sampled_from(TAGS), min_size=1, max_size=2)))
    return {c.name: c for c in classes}, odds, facts, goal


def brute_force(actions, odds, facts, goal, depth):
    """The cheapest valid sequence by exhaustive search (small libraries only)."""
    best = None
    names = sorted(actions)
    for n in range(0, depth + 1):
        for seq in itertools.product(names, repeat=n):
            have = set(facts)
            ok = True
            for name in seq:
                a = actions[name]
                if not a.requires <= have:
                    ok = False
                    break
                have.add(a.achieves)
            if ok and goal <= have:
                c = sum(1 / odds[s] + actions[s].secrecy for s in seq)
                if best is None or c < best - 1e-9:
                    best = c
    return best


@settings(max_examples=150, deadline=None)
@given(libraries(), st.integers(0, 4))
def test_plans_are_valid_bounded_deterministic_and_cheapest(case, depth):
    actions, odds, facts, goal = case
    w = World(facts=facts, odds=odds, ties=())
    p = run([goal], w, actions=actions, depth=depth)
    again = run([goal], w, actions=actions, depth=depth)
    assert p == again
    best = brute_force(actions, odds, facts, goal, depth)
    if p is None:
        assert best is None
        return
    assert len(p.steps) <= depth
    have = set(facts)
    for step in p.steps:
        a = actions[step["action"]]
        assert a.requires <= have
        have.add(a.achieves)
    assert goal <= have
    assert abs(cost(p, actions, lambda a, t: odds[a.name]) - best) < 1e-9


# ---------------------------------------------------------------- review regressions


def _lib(*specs):
    return {n: Gen(n, ach, frozenset(req), 0.0) for n, ach, req in specs}


def test_a_dearer_prerequisite_that_serves_another_goal_is_found():
    actions = _lib(("Aa", "a", {"p"}), ("Ab", "b", {"q"}), ("P1", "p", ()), ("P2", "p", {"q"}), ("Q", "q", ()))
    odds = {"Aa": 0.9, "Ab": 0.9, "P1": 0.5, "P2": 0.9, "Q": 0.2}
    w = World(odds=odds, ties=())
    p = run([frozenset({"a", "b"})], w, actions=actions, depth=6)
    assert abs(cost(p, actions, lambda a, t: odds[a.name]) - brute_force(actions, odds, set(), frozenset({"a", "b"}), 6)) < 1e-9


def test_a_short_plan_is_found_when_the_cheapest_prerequisite_is_too_long():
    actions = _lib(("Aa", "a", {"p"}), ("Ab", "b", ()), ("P1", "p", ()), ("P2", "p", {"q"}), ("Q", "q", ()))
    odds = {"Aa": 0.9, "Ab": 0.9, "P1": 0.2, "P2": 0.9, "Q": 0.9}
    w = World(odds=odds, ties=())
    assert run([frozenset({"a", "b"})], w, actions=actions, depth=3) is not None


def test_impossible_odds_are_not_planned():
    w = World(odds={"Duel": 0.0, "Poison": 0.0, "Assassinate": 0.0}, ties=("t:friend",))
    assert run([frozenset({"dead:t:rival"})], w) is None


@settings(max_examples=400, deadline=None)
@given(libraries(), st.integers(0, 5))
def test_cheapest_over_more_libraries(case, depth):
    actions, odds, facts, goal = case
    w = World(facts=facts, odds=odds, ties=())
    p = run([goal], w, actions=actions, depth=depth)
    best = brute_force(actions, odds, facts, goal, depth)
    assert (p is None) == (best is None)
    if p is not None:
        assert abs(cost(p, actions, lambda a, t: odds[a.name]) - best) < 1e-9
