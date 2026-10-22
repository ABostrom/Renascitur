import pytest
from hypothesis import given
from hypothesis import strategies as st

from renasci.core.rng import KeyedRng, OrdinalTable, Reshuffle

TICK = (4, 37, 1)



# ---------------------------------------------------------------- keys


def test_same_key_gives_same_draws():
    a, b = KeyedRng(1234), KeyedRng(1234)
    key = ("toy.life", "e1", "death", TICK, 0)
    assert list(a.stream(*key).random(8)) == list(b.stream(*key).random(8))


@pytest.mark.parametrize(
    "other",
    [
        ("toy.births", "e1", "death", TICK, 0),
        ("toy.life", "e2", "death", TICK, 0),
        ("toy.life", "e1", "illness", TICK, 0),
        ("toy.life", "e1", "death", (4, 37, 2), 0),
        ("toy.life", "e1", "death", TICK, 1),
    ],
)
def test_every_key_part_matters(other):
    rng = KeyedRng(1234)
    base = list(rng.stream("toy.life", "e1", "death", TICK, 0).random(4))
    assert list(rng.stream(*other).random(4)) != base


def test_seed_matters():
    key = ("toy.life", "e1", "death", TICK, 0)
    assert KeyedRng(1).stream(*key).random() != KeyedRng(2).stream(*key).random()


def test_streams_are_independent_of_each_other():
    rng = KeyedRng(7)
    k1 = ("s", "e1", "p", TICK, 0)
    k2 = ("s", "e2", "p", TICK, 0)
    alone = list(rng.stream(*k2).random(3))
    rng.stream(*k1).random(1000)  # heavy use of an unrelated stream
    assert list(rng.stream(*k2).random(3)) == alone


def test_key_parts_cannot_collide_by_concatenation():
    rng = KeyedRng(7)
    assert rng.key("ab", "c", "p", TICK, 0) != rng.key("a", "bc", "p", TICK, 0)


def test_golden_draws_pin_the_algorithm():
    # Changing these numbers changes every history: bump the engine version deliberately.
    s = KeyedRng(1234).stream("toy.life", "e1", "death", TICK, 0)
    assert [round(x, 12) for x in s.random(3)] == GOLDEN


GOLDEN = [0.896332548305, 0.402062458011, 0.465622569231]  # numpy 2.5 Philox; frozen


@pytest.mark.parametrize(
    "bad",
    [
        (None, "e1", "p", TICK, 0),
        ("s", None, "p", TICK, 0),
        ("s", "", "p", TICK, 0),
        ("s", "e1", "p", (4, 37), 0),
        ("s", "e1", "p", (4, 37.0, 1), 0),
        ("s", "e1", "p", TICK, -1),
        ("s", "e1", "p", TICK, True),
    ],
)
def test_bad_keys_are_rejected(bad):
    with pytest.raises((TypeError, ValueError)):
        KeyedRng(1).stream(*bad)


def test_seed_must_be_an_int():
    with pytest.raises(TypeError):
        KeyedRng(1.5)


# ---------------------------------------------------------------- stream methods


def test_stream_methods_are_deterministic():
    def sample(rng):
        s = rng.stream("s", "e1", "p", TICK, 0)
        return (
            s.random(),
            s.integers(0, 10, size=4).tolist(),
            s.normal(0.0, 1.0),
            s.choice_index([0.1, 0.0, 0.9]),
        )

    assert sample(KeyedRng(3)) == sample(KeyedRng(3))


def test_choice_index_never_picks_zero_weight():
    rng = KeyedRng(3)
    for i in range(200):
        assert rng.stream("s", f"e{i}", "p", TICK, 0).choice_index([0.0, 1.0, 0.0]) == 1


def test_choice_index_rejects_bad_weights():
    s = KeyedRng(3).stream("s", "e1", "p", TICK, 0)
    with pytest.raises(ValueError):
        s.choice_index([])
    with pytest.raises(ValueError):
        s.choice_index([0.0, 0.0])
    with pytest.raises(ValueError):
        s.choice_index([1.0, -0.5])


# ---------------------------------------------------------------- ordinals


def test_occurrences_count_per_exact_key():
    t = OrdinalTable()
    assert [t.next("s", "e1", "p", TICK) for _ in range(3)] == [0, 1, 2]
    assert t.next("s", "e2", "p", TICK) == 0
    assert t.next("s", "e1", "q", TICK) == 0
    assert t.next("s", "e1", "p", (4, 37, 2)) == 0
    assert t.next("s", "e1", "p", TICK) == 3


def test_closing_a_tick_discards_its_counts():
    t = OrdinalTable()
    t.next("s", "e1", "p", (4, 37, 1))
    t.next("s", "e1", "p", (4, 37, 2))
    t.close_before((4, 37, 2))
    assert t.to_json() == [["s", "e1", "p", [4, 37, 2], 1]]


@given(st.lists(st.tuples(st.sampled_from("ab"), st.sampled_from("xy"), st.integers(0, 3)), max_size=30))
def test_ordinal_table_json_round_trip(calls):
    t = OrdinalTable()
    for e, p, q in calls:
        t.next("s", e, p, (4, 1, q))
    again = OrdinalTable.from_json(t.to_json())
    assert again.to_json() == t.to_json()
    assert again.next("s", "a", "x", (4, 1, 0)) == t.next("s", "a", "x", (4, 1, 0))


def test_ordinal_json_is_sorted_regardless_of_call_order():
    a, b = OrdinalTable(), OrdinalTable()
    a.next("s", "e1", "p", TICK)
    a.next("s", "e2", "p", TICK)
    b.next("s", "e2", "p", TICK)
    b.next("s", "e1", "p", TICK)
    assert a.to_json() == b.to_json()


# ---------------------------------------------------------------- reshuffle slot


def test_reshuffle_changes_only_keys_at_or_after_its_tick():
    plain = KeyedRng(9)
    shuffled = KeyedRng(9, reshuffles=(Reshuffle((4, 100, 0), "b"),))
    before = ("s", "e1", "p", (4, 99, 3), 0)
    after = ("s", "e1", "p", (4, 100, 0), 0)
    assert plain.stream(*before).random() == shuffled.stream(*before).random()
    assert plain.stream(*after).random() != shuffled.stream(*after).random()


def test_latest_reshuffle_wins():
    rng = KeyedRng(9, reshuffles=(Reshuffle((4, 200, 0), "c"), Reshuffle((4, 100, 0), "b")))
    assert rng.salt_for((4, 150, 0)) == "b"
    assert rng.salt_for((4, 250, 0)) == "c"
    assert rng.salt_for((4, 50, 0)) == ""
