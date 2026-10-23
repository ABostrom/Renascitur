import numpy as np
import pytest
from hypothesis import given
from hypothesis import strategies as st

from renasci.core.calendar import Date
from renasci.core.canon import canonical
from renasci.core.ids import cast_id, entity_id, event_id
from renasci.core.store import Store

D = Date(4, 37, 10)

# ---------------------------------------------------------------- canonical JSON


def test_canonical_sorts_keys_and_is_compact():
    assert canonical({"b": 1, "a": [1, 2]}) == '{"a":[1,2],"b":1}'


def test_canonical_normalises_negative_zero_and_keeps_exact_floats():
    assert canonical(-0.0) == "0.0"
    assert canonical(0.1 + 0.2) == "0.30000000000000004"


@pytest.mark.parametrize("bad", [float("nan"), float("inf"), {1, 2}, {1: "x"}, object()])
def test_canonical_rejects_non_json_values(bad):
    with pytest.raises((TypeError, ValueError)):
        canonical(bad)


def test_canonical_turns_dates_and_tuples_into_lists():
    assert canonical({"d": D, "t": (1, 2)}) == '{"d":[4,37,10],"t":[1,2]}'


# ---------------------------------------------------------------- ids


def test_ids_are_deterministic_and_prefixed():
    x = event_id("toy.births", "e1", "birth", D, 0)
    assert x == event_id("toy.births", "e1", "birth", D, 0)
    assert x.startswith("x") and len(x) == 17
    e = entity_id(x, "child", 0)
    assert e.startswith("e") and len(e) == 17
    assert e == entity_id(x, "child", 0)


@pytest.mark.parametrize(
    "other",
    [
        ("toy.deaths", "e1", "birth", D, 0),
        ("toy.births", "e2", "birth", D, 0),
        ("toy.births", "e1", "twin", D, 0),
        ("toy.births", "e1", "birth", Date(4, 37, 11), 0),
        ("toy.births", "e1", "birth", D, 1),
    ],
)
def test_every_event_key_part_matters(other):
    assert event_id(*other) != event_id("toy.births", "e1", "birth", D, 0)


def test_entity_ids_differ_by_role_and_ordinal():
    x = event_id("toy.births", "e1", "birth", D, 0)
    assert len({entity_id(x, "child", 0), entity_id(x, "child", 1), entity_id(x, "twin", 0)}) == 3


def test_cast_ids():
    assert cast_id("v", "unimus") == "v:unimus"
    assert cast_id("t", "Ada Millbrook") == "t:Ada Millbrook"
    with pytest.raises(ValueError):
        cast_id("q", "x")
    with pytest.raises(ValueError):
        cast_id("v", "")


# ---------------------------------------------------------------- records


def make_store():
    s = Store()
    s.create("person", "e2", {"name": "Bo"}, D, "x1")
    s.create("person", "e1", {"name": "Ada"}, D, "x1")
    s.create("place", "t:Millbrook", {}, D, "x0")
    return s


def test_ids_iterate_sorted_and_filter_by_status():
    s = make_store()
    assert s.ids("person") == ["e1", "e2"]
    s.set_status("e2", "dead", D, "x9")
    assert s.ids("person", status="active") == ["e1"]
    assert s.ids("person") == ["e1", "e2"]  # dead entities are kept, never deleted


def test_set_records_a_delta_with_old_and_new():
    s = make_store()
    s.set("e1", "spouse", "e2", D, "x5")
    s.set("e1", "spouse", None, Date(4, 40, 0), "x6")
    assert s.get("e1", "spouse") is None
    assert [d.to_json() for d in s.deltas] [-2:] == [
        {"date": [4, 37, 10], "entity": "e1", "field": "spouse", "old": None, "new": "e2", "event": "x5", "activation": ""},
        {"date": [4, 40, 0], "entity": "e1", "field": "spouse", "old": "e2", "new": None, "event": "x6", "activation": ""},
    ]


def test_writes_need_an_event():
    s = make_store()
    for bad in ("", None):
        with pytest.raises(ValueError):
            s.set("e1", "age", 3, D, bad)


def test_values_must_be_json():
    s = make_store()
    with pytest.raises((TypeError, ValueError)):
        s.set("e1", "friends", {"e2"}, D, "x1")


def test_duplicate_create_and_unknown_entity_are_errors():
    s = make_store()
    with pytest.raises(ValueError):
        s.create("person", "e1", {}, D, "x1")
    with pytest.raises(KeyError):
        s.set("nobody", "age", 3, D, "x1")


def test_status_must_be_known():
    with pytest.raises(ValueError):
        make_store().set_status("e1", "missing", D, "x1")


def test_create_and_status_changes_are_deltas_too():
    s = Store()
    s.create("person", "e1", {"name": "Ada"}, D, "x1")
    s.set_status("e1", "dormant", D, "x2")
    fields = [(d.field, d.old, d.new) for d in s.deltas]
    assert ("status", None, "active") in fields and ("status", "active", "dormant") in fields


def test_stored_values_cannot_be_mutated_from_outside():
    s = make_store()
    s.set("e1", "children", ["e3"], D, "x1")
    s.get("e1", "children").append("e4")
    assert s.get("e1", "children") == ["e3"]


# ---------------------------------------------------------------- components


def test_columns_align_with_sorted_ids_and_log_one_bulk_delta():
    s = Store()
    s.add_column("grain", "float64")
    s.write_column("grain", ["v2", "v1"], [5.0, 3.0], D, "x1")
    assert s.read_column("grain", ["v1", "v2"]).tolist() == [3.0, 5.0]
    s.write_column("grain", ["v1"], [4.0], D, "x2")
    assert s.read_column("grain", ["v1", "v2"]).tolist() == [4.0, 5.0]
    assert len(s.bulk_deltas) == 2
    b = s.bulk_deltas[-1].to_json()
    assert b["component"] == "grain" and b["ids"] == ["v1"] and b["event"] == "x2"
    assert isinstance(b["values_hash"], str)


def test_column_reads_return_copies():
    s = Store()
    s.add_column("grain", "float64")
    s.write_column("grain", ["v1"], [1.0], D, "x1")
    s.read_column("grain", ["v1"])[0] = 99.0
    assert s.read_column("grain", ["v1"]).tolist() == [1.0]


def test_column_write_validates_lengths_and_event():
    s = Store()
    s.add_column("grain", "float64")
    with pytest.raises(ValueError):
        s.write_column("grain", ["v1", "v2"], [1.0], D, "x1")
    with pytest.raises(ValueError):
        s.write_column("grain", ["v1"], [1.0], D, "")


# ---------------------------------------------------------------- JSON round trip


@given(st.lists(st.tuples(st.sampled_from(["e1", "e2", "e3"]), st.integers(-5, 5)), max_size=20))
def test_store_json_round_trip_is_exact(writes):
    s = make_store()
    s.create("person", "e3", {}, D, "x1")
    s.add_column("grain", "float64")
    for i, (e, v) in enumerate(writes):
        s.set(e, "score", v, D, f"x{i + 10}")
        s.write_column("grain", [e], [v / 3], D, f"x{i + 10}")
    again = Store.from_json(s.to_json())
    assert canonical(again.to_json()) == canonical(s.to_json())
    assert again.ids("person") == s.ids("person")


def test_store_json_is_independent_of_creation_order():
    a, b = Store(), Store()
    a.create("person", "e1", {}, D, "x1")
    a.create("person", "e2", {}, D, "x2")
    b.create("person", "e2", {}, D, "x2")
    b.create("person", "e1", {}, D, "x1")
    # deltas keep emission order (history); the state snapshot does not
    assert canonical(a.to_json()["entities"]) == canonical(b.to_json()["entities"])


def test_columns_serialise_as_plain_json_lists():
    s = Store()
    s.add_column("grain", "float64")
    s.write_column("grain", ["v1"], [np.float64(2.5)], D, "x1")
    col = s.to_json()["columns"]["grain"]
    assert col == {"dtype": "float64", "ids": ["v1"], "data": [2.5]}


# ---------------------------------------------------------------- review fixes


@pytest.mark.parametrize(
    "ids, values",
    [(["a"], [float("nan")]), (["a"], [float("inf")]), (["b"], [[1.0, 2.0]]), (["c"], ["x"])],
)
def test_failed_column_write_changes_nothing(ids, values):
    s = Store()
    s.add_column("pop", "float64")
    with pytest.raises((ValueError, TypeError)):
        s.write_column("pop", ids, values, D, "x1")
    assert s.to_json()["columns"]["pop"] == {"dtype": "float64", "ids": [], "data": []}
    assert s.bulk_deltas == []


@pytest.mark.parametrize("dtype", ["object", "U8", "complex128"])
def test_only_numeric_column_dtypes(dtype):
    with pytest.raises(ValueError):
        Store().add_column("c", dtype)


def test_lossy_int_column_writes_are_rejected():
    s = Store()
    s.add_column("n", "int64")
    with pytest.raises(ValueError):
        s.write_column("n", ["a"], [1.7], D, "x1")
    s.write_column("n", ["a"], [2.0], D, "x1")
    assert s.read_column("n", ["a"]).tolist() == [2]


def test_negative_zero_is_normalised_on_write():
    s = Store()
    s.add_column("g", "float64")
    s.write_column("g", ["a"], [-0.0], D, "x1")
    assert not np.signbit(s.read_column("g", ["a"])[0])


def test_status_is_a_reserved_field_name():
    s = Store()
    with pytest.raises(ValueError):
        s.create("person", "e1", {"status": "noble"}, D, "x1")
    s.create("person", "e1", {}, D, "x1")
    with pytest.raises(ValueError):
        s.set("e1", "status", "noble", D, "x1")


def test_snapshot_is_detached_from_the_store():
    s = make_store()
    snap = s.to_json()
    s.set("e1", "name", "Changed", D, "x2")
    assert snap["entities"][0]["fields"]["name"] == "Ada"
    snap["entities"][0]["fields"]["name"] = "Hacked"
    assert s.get("e1", "name") == "Changed"


@pytest.mark.parametrize(
    "call",
    [
        lambda s: s.set("e1", 3, "v", D, "x1"),
        lambda s: s.set("e1", "", "v", D, "x1"),
        lambda s: s.set("e1", "k", "v", (4, 1, 0), "x1"),
        lambda s: s.create(3, "e9", {}, D, "x1"),
        lambda s: s.create("person", "e9", {}, "4A 1", "x1"),
    ],
)
def test_bad_write_arguments_fail_immediately(call):
    with pytest.raises((TypeError, ValueError)):
        call(make_store())


@pytest.mark.parametrize(
    "call",
    [
        lambda: event_id("s", "e1", "p", D, 1.0),
        lambda: event_id("s", "e1", "p", D, True),
        lambda: event_id("s", "e1", "p", D, -1),
        lambda: event_id("s", None, "p", D, 0),
        lambda: event_id("s", "e1", "p", (4, 37, 10), 0),
        lambda: entity_id("x1234", "child", 1.0),
        lambda: entity_id("e1234", "child", 0),
        lambda: entity_id("x1234", "", 0),
    ],
)
def test_id_inputs_are_strict(call):
    with pytest.raises((TypeError, ValueError)):
        call()


def test_bulk_delta_records_its_activation():
    s = Store()
    s.add_column("g", "float64")
    s.write_column("g", ["a"], [1.0], D, "x1", activation="a1")
    assert s.bulk_deltas[-1].to_json()["activation"] == "a1"


def test_building_a_large_column_in_one_write():
    s = Store()
    s.add_column("g", "float64")
    ids = [f"p{i:05d}" for i in range(20000)][::-1]
    s.write_column("g", ids, [float(i) for i in range(20000)], D, "x1")
    assert s.read_column("g", ["p00000", "p19999"]).tolist() == [19999.0, 0.0]


def test_read_gives_an_independent_copy_and_the_canonical_text_it_was_read_from():
    """`read` is `get` plus the value's canonical text (one serialisation per read, #75), kept current
    across writes: the text always matches what `get` returns now."""
    s = make_store()
    s.set("e1", "kids", [{"name": "Cy", "age": 3}], D, "x5")
    value, text = s.read("e1", "kids")
    assert value == [{"name": "Cy", "age": 3}] and text == canonical(value)
    value.append("tampered")
    assert s.get("e1", "kids") == [{"name": "Cy", "age": 3}]
    s.set("e1", "kids", [], D, "x6")
    assert s.read("e1", "kids") == ([], "[]")
    assert s.read("e1", "name") == ("Ada", None)  # a plain scalar needs no text
    assert s.read("e1", "nothing", default=[1]) == ([1], "[1]")
