import pytest
from hypothesis import given
from hypothesis import strategies as st

from renasci.core.calendar import Age, Calendar, Date
from renasci.core.choice import match, rank, rendezvous
from renasci.core.engine import Engine
from renasci.core.events import EventType
from renasci.core.systems import Ruleset, System

names = st.lists(st.text("abcdefgh", min_size=1, max_size=4), min_size=1, max_size=12, unique=True)

# ---------------------------------------------------------------- rendezvous


@given(names, st.integers(0, 10**6))
def test_removing_a_loser_never_changes_the_winner(cands, key):
    win = rendezvous([key], cands)
    for c in cands:
        if c != win:
            assert rendezvous([key], [x for x in cands if x != c]) == win


@given(names, st.integers(0, 10**6))
def test_adding_a_candidate_only_matters_if_it_wins(cands, key):
    win = rendezvous([key], cands)
    new = rendezvous([key], cands + ["zzzzz"])
    assert new in (win, "zzzzz")


@given(names, st.integers(0, 10**6))
def test_order_of_candidates_never_matters(cands, key):
    assert rendezvous([key], cands) == rendezvous([key], list(reversed(cands)))


def test_key_changes_the_winner_sometimes():
    cands = [f"c{i}" for i in range(20)]
    assert len({rendezvous([k], cands) for k in range(50)}) > 5


def test_weighted_rendezvous_respects_weights():
    cands = ["heavy", "light"]
    wins = sum(rendezvous([k], cands, weights=[9.0, 1.0]) == "heavy" for k in range(2000))
    assert 1650 < wins < 1950  # ~90%


def test_zero_weight_never_wins_and_bad_weights_fail():
    assert all(rendezvous([k], ["a", "b"], weights=[0.0, 1.0]) == "b" for k in range(100))
    with pytest.raises(ValueError):
        rendezvous([1], ["a", "b"], weights=[0.0, 0.0])
    with pytest.raises(ValueError):
        rendezvous([1], ["a"], weights=[1.0, 2.0])
    with pytest.raises(ValueError):
        rendezvous([1], ["a", "b"], weights=[1.0, float("nan")])


def test_empty_and_duplicate_candidates():
    assert rendezvous([1], []) is None
    with pytest.raises(ValueError):
        rendezvous([1], ["a", "a"])


@given(names, st.integers(0, 10**6))
def test_rank_is_a_stable_full_ordering(cands, key):
    ranked = rank([key], cands)
    assert sorted(ranked) == sorted(cands)
    assert ranked[0] == rendezvous([key], cands)


# ---------------------------------------------------------------- matching


def test_match_pairs_each_seeker_with_at_most_one_target():
    seekers = {f"s{i}": [f"t{j}" for j in range(5)] for i in range(5)}
    m = match([7], seekers)
    assert sorted(m) == sorted(seekers) and len(set(m.values())) == 5


def test_match_is_independent_of_dict_order():
    seekers = {f"s{i}": [f"t{j}" for j in range(4)] for i in range(6)}
    reordered = dict(reversed(list(seekers.items())))
    assert match([3], seekers) == match([3], reordered)


@given(st.integers(0, 10**5))
def test_unrelated_seeker_does_not_disturb_other_matches(key):
    # Two separate markets: a seeker joining market B never changes market A's pairs.
    a = {f"a{i}": [f"ta{j}" for j in range(3)] for i in range(3)}
    b = {f"b{i}": [f"tb{j}" for j in range(3)] for i in range(2)}
    before = match([key], {**a, **b})
    after = match([key], {**a, **b, "b9": [f"tb{j}" for j in range(3)]})
    assert {s: before[s] for s in a if s in before} == {s: after[s] for s in a if s in after}


def test_match_rejects_seekers_who_are_targets_of_themselves():
    with pytest.raises(ValueError):
        match([1], {"x": ["x"]})


# ---------------------------------------------------------------- through the engine: choose and chance

CAL = Calendar(ages=(Age(1, "1X", "Toy Age", last_year=50),))
DUEL = EventType("toy.duel", 1, roles={"winner": (1, 1)}, payload={})


class Duels(System):
    name, cadence = "toy.duels", "yearly"
    reads, writes = frozenset(), frozenset()
    event_types = (DUEL,)

    def run(self, ctx):
        pick = ctx.choose("champion", ["t:a", "t:b", "t:c"], owner="t:world")
        won = ctx.chance(0.5, "duel", owner=pick, stakes=0.8, roles={"duelist": [pick]})
        if won:
            ctx.emit("toy.duel", {"winner": (pick,)}, purpose="duel", actor=pick)


def make(seed=1):
    e = Engine(CAL, seed=seed, rulesets=[(Date(1, 1, 0), Ruleset("d", 1, (Duels(),)))])
    for p in ("t:world", "t:a", "t:b", "t:c"):
        e.cast("person", p, {})
    return e


def test_choose_and_chance_are_deterministic_and_seeded():
    runs = []
    for seed in (1, 1, 2):
        e = make(seed)
        e.run(until=Date(1, 20, 0))
        runs.append([(h["owner"], h["u"]) for h in e.hinges])
    assert runs[0] == runs[1] != runs[2]


def test_every_chance_with_stakes_records_a_hinge():
    e = make()
    e.run(until=Date(1, 5, 0))
    assert len(e.hinges) == 5
    h = e.hinges[0]
    assert {"id", "kind", "activation", "date", "system", "owner", "purpose", "occurrence", "p_base", "p",
            "adjusted_by", "u", "margin", "outcome", "stakes", "roles", "event"} == set(h)
    assert h["margin"] == pytest.approx(abs(h["u"] - h["p"]))
    assert h["outcome"] == (h["u"] < h["p"])


def test_chance_validates_probability():
    class Bad(Duels):
        def run(self, ctx):
            ctx.chance(1.5, "x", owner="t:a")

    e = Engine(CAL, seed=1, rulesets=[(Date(1, 1, 0), Ruleset("b", 1, (Bad(),)))])
    e.cast("person", "t:a", {})
    with pytest.raises(ValueError):
        e.run(until=Date(1, 1, 0))


# ---------------------------------------------------------------- review fixes

market = st.dictionaries(
    st.sampled_from([f"s{i}" for i in range(6)]),
    st.lists(st.sampled_from([f"t{j}" for j in range(4)]), min_size=1, max_size=4, unique=True),
    min_size=1,
)


@given(market, st.integers(0, 10**5))
def test_removing_an_unmatched_seeker_changes_nothing(seekers, key):
    m = match([key], seekers)
    for s in seekers:
        if s not in m:
            rest = {k: v for k, v in seekers.items() if k != s}
            assert match([key], rest) == m


@given(market, st.integers(0, 10**5))
def test_removing_an_unmatched_target_changes_nothing(seekers, key):
    m = match([key], seekers)
    taken = set(m.values())
    for t in sorted({t for ts in seekers.values() for t in ts} - taken):
        rest = {s: [x for x in ts if x != t] for s, ts in seekers.items()}
        rest = {s: ts for s, ts in rest.items() if ts}
        assert match([key], rest) == m


def test_the_review_counterexample_is_stable():
    seekers = {"s0": ["t0", "t1", "t2"], "s1": ["t0", "t2"], "s2": ["t0", "t1"], "s3": ["t0", "t1", "t2"]}
    m = match([25], seekers)
    if "s3" not in m:
        assert match([25], {k: v for k, v in seekers.items() if k != "s3"}) == m


def test_seekers_cannot_also_be_targets():
    with pytest.raises(ValueError):
        match([1], {"a": ["b"], "b": ["c"]})


def test_match_accepts_weights_on_both_sides():
    # every seeker strongly prefers t_near; t_near strongly prefers s_fav
    seekers = {f"s{i}": {"t_near": 50.0, "t_far": 1.0} for i in range(4)}
    seekers["s_fav"] = {"t_near": 50.0, "t_far": 1.0}
    accept = {"t_near": {"s_fav": 1000.0}}
    wins = sum(match([k], seekers, accept=accept).get("s_fav") == "t_near" for k in range(200))
    assert wins > 180


# ---------------------------------------------------------------- hinges: modifiers, linking, buffering

NOTE = EventType("toy.result", 1, roles={"subject": (1, 1)}, payload={})


class Roller(System):
    name, cadence = "toy.roller", "yearly"
    event_types = (NOTE,)

    def run(self, ctx):
        a = ctx.chance(0.5, "roll", owner="t:a", stakes=1.0)
        ctx.chance(0.5, "roll", owner="t:a", stakes=1.0)
        if a or True:
            ctx.emit("toy.result", {"subject": ("t:a",)}, purpose="roll", actor="t:a")
        ctx.choose("heir", ["t:a", "t:b", "t:c"], owner="t:a", stakes=0.9, roles={"house": ["t:a"]})


def roller_engine(**kw):
    e = Engine(CAL, seed=1, rulesets=[(Date(1, 1, 0), Ruleset("r", 1, (Roller(),)))], **kw)
    for p in ("t:a", "t:b", "t:c"):
        e.cast("person", p, {})
    return e


def test_hinges_have_ids_occurrences_and_link_to_the_next_event():
    e = roller_engine()
    e.run(until=Date(1, 1, 0))
    rolls = [h for h in e.hinges if h["purpose"] == "roll"]
    assert [h["occurrence"] for h in rolls] == [0, 1]
    assert len({h["id"] for h in rolls}) == 2
    result = next(ev for ev in e.events if ev.type == "toy.result")
    assert all(h["event"] == result.id for h in rolls)


def test_choose_records_a_hinge_with_runner_up_and_margin():
    e = roller_engine()
    e.run(until=Date(1, 1, 0))
    h = next(h for h in e.hinges if h["purpose"] == "heir")
    assert h["kind"] == "choice" and h["winner"] != h["runner_up"] and h["margin"] >= 0


def test_odds_hooks_adjust_p_and_are_recorded():
    e = roller_engine()

    def favour(ctx, p, purpose, owner):
        return (min(1.0, p + 0.4), "ripple:r1") if owner == "t:a" and purpose == "roll" else (p, None)

    e.odds_hooks.append(favour)
    e.run(until=Date(1, 1, 0))
    h = next(h for h in e.hinges if h["purpose"] == "roll")
    assert h["p_base"] == 0.5 and h["p"] == pytest.approx(0.9) and h["adjusted_by"] == ["ripple:r1"]


def test_hinges_from_a_failed_activation_are_discarded():
    class Boom(Roller):
        def run(self, ctx):
            ctx.chance(0.5, "roll", owner="t:a", stakes=1.0)
            raise RuntimeError("boom")

    e = Engine(CAL, seed=1, rulesets=[(Date(1, 1, 0), Ruleset("b", 1, (Boom(),)))])
    e.cast("person", "t:a", {})
    with pytest.raises(RuntimeError):
        e.run(until=Date(1, 1, 0))
    assert e.hinges == []
